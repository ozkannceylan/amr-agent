#!/usr/bin/env python3
"""TEST HARNESS — the two kernels of brief m4f-07b, against the PLC LOGIC DOUBLE.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

Two behaviours, demonstrated end to end through the HMI's own loopback endpoints:

    K1  §10.8 H6 — the operator's page is watched, and what is watched is the
        page. The page's `GET /state` poll is killed while the BACKEND STAYS
        ALIVE; all five requests go to rest while the write cycle and the
        heartbeat CONTINUE; nothing latches in the PLC; and recovery is a
        RELEASE, not a resume — the three Reals are carried again on the page's
        next post, each Bool only once that page has been seen to send it low.

    K2  `plc/forklift/SPEC.md` §11 T5.4, steps 5.4.2–5.4.9, driven entirely from
        the operator's own control endpoint. The reset is ASSERTED AND HELD
        across the moment the obstacle zone clears: the latch stands for as long
        as it is held, and clears only on a fresh edge after a real release.
        `docs/reports/m4f-08-commissioning-scenarios.md` finding 3 recorded that
        this could not be produced from the page at all; it can now.

Three processes, three roles, and the separation is the point:

    this harness   plays the BRIDGE and the PLANT — it advances
                   `DemoCell/Link/BridgeHeartbeat` and writes the four
                   `Forklift/Input/` nodes. It also plays the PAGE, through the
                   HMI's loopback HTTP endpoints, including the page's own 5 Hz
                   `GET /state`, which is the H6 beacon. It never writes an
                   `Hmi` node: those are the HMI's, and the two writable sets are
                   disjoint by construction.
    the HMI        plays the OPERATOR's side of the wire — the five requests and
                   `HmiHeartbeat`, and nothing else.
    the double     plays the PLC. It owns every verdict.

Nothing observed here is evidence about the TIA Portal build. It is a rehearsal
and any divergence resolves toward TIA and `SPEC.md`, never toward the double.

Run (from the repository root):
    ~/amr-hmi-venv/bin/python hmi/tools/check_hmi_h6_and_reset.py \\
        --double-cmd "<bridge venv python> plc/forklift/double/server.py"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from asyncua import Client, ua

HERE = Path(__file__).resolve().parent
HMI_DIR = HERE.parent

F = ua.VariantType.Float
B = ua.VariantType.Boolean
U = ua.VariantType.UInt16

#: The page's poll period, `hmi/static/index.html`; the backend derives its H6
#: window as five of these. The harness only has to poll like the page.
PAGE_POLL_S = 0.200

#: What the harness writes, standing in for the bridge (`opcua-nodes.md` §10.5).
PLANT_INPUTS = (
    ("ForkliftForkHeight", F),
    ("ForkliftLinearSpeed", F),
    ("ForkliftObstacleInStopZone", B),
    ("ForkliftObstacleMinDistance", F),
)

HMI_NODES = ("HmiTractionRequest", "HmiSteerRequest", "HmiForkRequest",
             "HmiTeleopRequest", "HmiResetRequest")
OUTPUTS = ("ForkliftTractionSpeedRef", "ForkliftSteerAngleRef",
           "ForkliftForkSpeedRef")
STATUS = ("ForkliftTeleopActive", "ForkliftObstacleStopActive",
          "ForkliftSpeedLimitActive", "ForkliftResetRequired")

FAILURES: list[str] = []


def ok(message: str) -> None:
    print(f"   ok   {message}", flush=True)


def bad(message: str) -> None:
    FAILURES.append(message)
    print(f"   FAIL {message}", flush=True)


def check(condition, message: str) -> bool:
    (ok if condition else bad)(message)
    return bool(condition)


def note(message: str) -> None:
    print(f"        {message}", flush=True)


def head(title: str) -> None:
    print(f"\n{title}", flush=True)


def near(a, b, tol=2e-3) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def post_control(base: str, **payload) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{base}/control", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        response.read()


def get_state(base: str) -> dict:
    with urllib.request.urlopen(f"{base}/state", timeout=3) as response:
        return json.loads(response.read())


class PageBeacon:
    """The browser's unconditional `GET /state` at 5 Hz — the H6 beacon.

    `freeze()` stops the poll while this harness and the HMI both keep running,
    which is what a crashed, frozen, closed or disconnected browser looks like
    from inside the backend. It is the one thing H6 exists to catch.
    """

    def __init__(self, base: str, period: float = PAGE_POLL_S) -> None:
        self.base = base
        self.period = period
        self.polls = 0
        self._enabled = True
        self._alive = True
        self._thread = threading.Thread(target=self._loop, name="page-beacon",
                                        daemon=True)

    def start(self) -> "PageBeacon":
        self._thread.start()
        return self

    def _loop(self) -> None:
        while self._alive:
            if self._enabled:
                try:
                    with urllib.request.urlopen(f"{self.base}/state", timeout=1.0) as r:
                        r.read()
                    self.polls += 1
                except (urllib.error.URLError, OSError):
                    pass
            time.sleep(self.period)

    def freeze(self) -> None:
        self._enabled = False

    def thaw(self) -> None:
        self._enabled = True

    def stop(self) -> None:
        self._alive = False


class Cell:
    """The harness's own OPC UA session: it writes the plant image and the bridge
    heartbeat, and reads everything back — including the five `Forklift/Hmi/`
    nodes, so every "the HMI wrote X" below is the SERVER's answer and not the
    HMI's own report of itself."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.client: Client | None = None
        self.nodes: dict[str, object] = {}
        self.heartbeat = 0
        self.state = {
            "ForkliftForkHeight": 0.20,
            "ForkliftLinearSpeed": 0.0,
            "ForkliftObstacleInStopZone": False,
            "ForkliftObstacleMinDistance": 3.50,
        }
        self._run = False

    async def connect(self, retries: int = 60) -> None:
        last = None
        for _ in range(retries):
            try:
                client = Client(url=self.endpoint)
                client.name = "amr-agent-hmi-h6-harness"
                await client.connect()
                break
            except Exception as exc:  # noqa: BLE001 - the double may still be starting
                last = exc
                await asyncio.sleep(0.25)
        else:
            raise RuntimeError(f"harness could not connect to {self.endpoint}: {last}")
        idx_si = await client.get_namespace_index(
            "http://www.siemens.com/simatic-s7-opcua")
        idx = await client.get_namespace_index("http://DemoCell")
        objects = client.nodes.objects
        base = [f"{idx_si}:ServerInterfaces", f"{idx}:DemoCell"]

        async def child(*parts):
            return await objects.get_child(base + [f"{idx}:{p}" for p in parts])

        for name, _ in PLANT_INPUTS:
            self.nodes[name] = await child("Forklift", "Input", name)
        for name in HMI_NODES:
            self.nodes[name] = await child("Forklift", "Hmi", name)
        for name in OUTPUTS:
            self.nodes[name] = await child("Forklift", "Output", name)
        for name in STATUS:
            self.nodes[name] = await child("Forklift", "Status", name)
        self.nodes["HmiHeartbeat"] = await child("Forklift", "Link", "HmiHeartbeat")
        self.nodes["HmiLinkOk"] = await child("Forklift", "Link", "HmiLinkOk")
        self.nodes["BridgeHeartbeat"] = await child("Link", "BridgeHeartbeat")
        self.nodes["BridgeLinkOk"] = await child("Link", "BridgeLinkOk")
        self.client = client

    async def write_inputs(self) -> None:
        for name, vtype in PLANT_INPUTS:
            await self.nodes[name].write_value(
                ua.DataValue(ua.Variant(self.state[name], vtype)))

    async def pump(self, period: float = 0.05) -> None:
        """The bridge's cycle: the plant image, then the heartbeat."""
        self._run = True
        while self._run:
            await self.write_inputs()
            self.heartbeat = (self.heartbeat + 1) % 65536
            await self.nodes["BridgeHeartbeat"].write_value(
                ua.DataValue(ua.Variant(self.heartbeat, U)))
            await asyncio.sleep(period)

    async def read(self, *names) -> dict:
        values = await self.client.read_values([self.nodes[n] for n in names])
        return dict(zip(names, values))

    async def requests(self) -> dict:
        return await self.read(*HMI_NODES, "HmiHeartbeat")

    async def verdicts(self) -> dict:
        return await self.read(*STATUS, *OUTPUTS, "HmiLinkOk", "BridgeLinkOk")

    async def close(self) -> None:
        self._run = False
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None


async def until(coro_factory, timeout=8.0, poll=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = await coro_factory()
        if value:
            return value
        await asyncio.sleep(poll)
    return None


async def wait_for(cell: Cell, name: str, wanted, timeout=8.0):
    async def probe():
        reading = await cell.read(name)
        return reading if reading[name] == wanted else None
    return await until(probe, timeout)


def hmi_connected(base: str) -> bool:
    try:
        return get_state(base)["session"]["state"] == "CONNECTED"
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError):
        return False


def rest(base: str, **overrides) -> None:
    """One post carries all five values; naming them all every time is what the
    page does and it keeps every step's full control set visible in this file."""
    payload = {"traction": 0.0, "steer": 0.0, "fork": 0.0,
               "teleop": False, "reset": False}
    payload.update(overrides)
    post_control(base, **payload)


# --------------------------------------------------------------------------- #

async def run(args, double) -> int:
    print(f"HMI H6 + held-reset harness — server {args.endpoint} (PLC LOGIC DOUBLE), "
          f"HMI {args.hmi}")
    print("Roles: this harness plays the bridge, the plant AND the page; the HMI plays "
          "the operator's side of the wire; the double plays the PLC and owns every "
          "verdict. Nothing here is evidence about the TIA Portal build.")
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    double.start()
    cell = Cell(args.endpoint)
    await cell.connect()
    await cell.write_inputs()
    pump = asyncio.create_task(cell.pump())

    log_path = scratch / "hmi-h6-run.log"
    log = open(log_path, "w", encoding="utf-8")
    hmi = subprocess.Popen(
        [args.python, str(HMI_DIR / "hmi_server.py"), "--config", args.config]
        + (["--evidence-csv", args.evidence_csv] if args.evidence_csv else []),
        stdout=log, stderr=subprocess.STDOUT)
    beacon = PageBeacon(args.hmi).start()
    try:
        # ---- K0: the loop is up ------------------------------------------- #
        head("K0. the loop is up: both links, latches cleared, teleop enabled, driving")
        if not check(bool(await until(
                lambda: asyncio.sleep(0, result=hmi_connected(args.hmi)), 25)),
                "the HMI reached CONNECTED against the logic double"):
            return 1
        check(bool(await wait_for(cell, "HmiLinkOk", True, 10)),
              "HmiLinkOk went TRUE once the HMI's counter had been seen to change")
        check((await cell.read("BridgeLinkOk"))["BridgeLinkOk"] is True,
              "BridgeLinkOk is TRUE too — teleop needs both (§10.8 P7)")
        rest(args.hmi, reset=True)
        await asyncio.sleep(0.3)
        rest(args.hmi)
        cleared = await wait_for(cell, "ForkliftResetRequired", False, 8)
        check(bool(cleared), "the boot latches cleared on the reset's rising edge")
        rest(args.hmi, teleop=True)
        check(bool(await wait_for(cell, "ForkliftTeleopActive", True, 8)),
              "and teleop came up on the separate rising edge of the enable")
        rest(args.hmi, traction=0.60, teleop=True)
        check(bool(await until(
            lambda: _ref(cell, "ForkliftTractionSpeedRef", 0.60), 8)),
            "the machine is driving — ForkliftTractionSpeedRef 0.60 m/s")

        # ---- K1: H6, the page dies under a healthy backend ----------------- #
        head("K1. §10.8 H6 — the page's poll stops while the BACKEND STAYS ALIVE")
        before = await cell.requests()
        page_before = get_state(args.hmi)["page"]
        note(f"before: HmiTractionRequest {before['HmiTractionRequest']:.3f}, "
             f"HmiTeleopRequest {before['HmiTeleopRequest']}, page state "
             f"{page_before['state']}, window {page_before['stale_after_ms']} ms "
             f"= {page_before['poll_period_ms']} ms poll x 5")
        killed_at = time.monotonic()
        beacon.freeze()          # the browser crashed with the joystick held
        dropped = await until(lambda: _all_at_rest(cell), 5.0, 0.02)
        elapsed_ms = round((time.monotonic() - killed_at) * 1000)
        check(bool(dropped),
              f"all five requests went to rest {elapsed_ms} ms after the page went "
              f"quiet, against a 1000 ms UI_POLL_STALE_TIME — the enable included")
        note(f"at rest on the server: " + ", ".join(
            f"{k}={_fmt(v)}" for k, v in (dropped or {}).items() if k in HMI_NODES))
        hb_a = (await cell.read("HmiHeartbeat"))["HmiHeartbeat"]
        await asyncio.sleep(1.0)
        hb_b = (await cell.read("HmiHeartbeat"))["HmiHeartbeat"]
        check(hb_a != hb_b,
              f"and the HEARTBEAT KEPT RUNNING across the drop — {hb_a} -> {hb_b} over "
              f"1.0 s. The process is healthy and keeps saying so; what is gone is the "
              f"page")
        verdict = await cell.verdicts()
        check(verdict["HmiLinkOk"] is True,
              f"HmiLinkOk is still TRUE — the PLC was told nothing new "
              f"({verdict['HmiLinkOk']})")
        check(verdict["ForkliftResetRequired"] is False,
              f"NOTHING LATCHED: ForkliftResetRequired is FALSE, so no reset is owed "
              f"for a page that went away ({verdict['ForkliftResetRequired']})")
        check(verdict["ForkliftTeleopActive"] is False
              and near(verdict["ForkliftTractionSpeedRef"], 0.0)
              and near(verdict["ForkliftSteerAngleRef"], 0.0)
              and near(verdict["ForkliftForkSpeedRef"], 0.0),
              f"the machine stopped anyway, and the PLC decided it from requests at "
              f"rest — teleop {verdict['ForkliftTeleopActive']}, refs "
              f"{verdict['ForkliftTractionSpeedRef']}, "
              f"{verdict['ForkliftSteerAngleRef']}, {verdict['ForkliftForkSpeedRef']}")
        # This diagnostic GET is itself a request from "the page", so it ends the
        # stale condition on arrival — which is the rule working, not a flaw in
        # it. What survives the request, and is what the checks are made on, is
        # the drop counter and the two arming flags: recovery is a release.
        state = get_state(args.hmi)
        note(f"page section as the backend renders it: {json.dumps(state['page'])}")
        check(state["session"]["state"] == "CONNECTED" and state["page"]["drops"] == 1,
              f"the backend is healthy and says so on the operator's own banner — "
              f"session {state['session']['state']}, page {state['page']['state']} "
              f"after {state['page']['age_ms']} ms, drops {state['page']['drops']}")
        check(state["page"]["teleop_armed"] is False
              and state["page"]["reset_armed"] is False,
              f"and both Bools are disarmed until the page is seen to send them low — "
              f"teleop_armed {state['page']['teleop_armed']}, reset_armed "
              f"{state['page']['reset_armed']}")

        # ---- K1 recovery: a release, never a resume ------------------------ #
        head("K1r. recovery is a RELEASE, not a resume")
        beacon.thaw()
        rest(args.hmi, traction=0.30, teleop=True, reset=True)   # page thaws asserted
        await asyncio.sleep(0.5)
        thawed = await cell.requests()
        check(near(thawed["HmiTractionRequest"], 0.30),
              f"the three Reals are carried again on the page's very first post — "
              f"HmiTractionRequest {thawed['HmiTractionRequest']}")
        check(thawed["HmiTeleopRequest"] is False and thawed["HmiResetRequest"] is False,
              f"but NEITHER Bool is, even though the page posted both TRUE — a page "
              f"that thaws with the enable still asserted must not produce a rising "
              f"edge no operator made — teleop {thawed['HmiTeleopRequest']}, reset "
              f"{thawed['HmiResetRequest']}")
        rest(args.hmi, traction=0.30)                            # both seen low
        await asyncio.sleep(0.4)
        rest(args.hmi, traction=0.30, reset=True)                # reset re-armed
        await asyncio.sleep(0.4)
        rearmed = await cell.requests()
        check(rearmed["HmiResetRequest"] is True,
              f"once the page had been seen to send it low, the reset is carried again "
              f"— {rearmed['HmiResetRequest']}")
        rest(args.hmi, traction=0.30)
        await asyncio.sleep(0.4)
        rest(args.hmi, traction=0.30, teleop=True)               # enable re-armed
        await asyncio.sleep(0.4)
        rearmed = await cell.requests()
        check(rearmed["HmiTeleopRequest"] is True,
              f"and so is the enable — {rearmed['HmiTeleopRequest']}")
        back = await wait_for(cell, "ForkliftTeleopActive", True, 8)
        check(bool(back),
              "teleop returned with NO monitored reset demanded of the operator: "
              "nothing had latched, so nothing had to be cleared")
        note(f"page section now: {json.dumps(get_state(args.hmi)['page'])}")

        # ---- K2: SPEC §11 T5.4, from the operator's own screen ------------- #
        head("K2. SPEC §11 T5.4 5.4.2-5.4.9 — the reset HELD across the zone clearing")
        rest(args.hmi, traction=0.60, teleop=True)
        check(bool(await until(
            lambda: _ref(cell, "ForkliftTractionSpeedRef", 0.60), 8)),
            "5.4.1 driving at a steady traction demand — ref 0.60 m/s")
        cell.state["ForkliftObstacleInStopZone"] = True
        latched = await wait_for(cell, "ForkliftObstacleStopActive", True, 8)
        check(bool(latched), "5.4.2 ForkliftObstacleStopActive latched")
        verdict = await cell.verdicts()
        standing = await cell.requests()
        check(verdict["ForkliftTeleopActive"] is False
              and near(verdict["ForkliftTractionSpeedRef"], 0.0)
              and verdict["ForkliftResetRequired"] is True,
              f"teleop dropped, all three refs 0.0, ForkliftResetRequired TRUE — "
              f"{verdict['ForkliftTractionSpeedRef']}, "
              f"{verdict['ForkliftSteerAngleRef']}, {verdict['ForkliftForkSpeedRef']}")
        check(near(standing["HmiTractionRequest"], 0.60),
              f"while HmiTractionRequest is STILL STANDING at "
              f"{standing['HmiTractionRequest']} — the latch overrides a live command")

        note("5.4.3 holding the traction control for 10 s, posting NOTHING — the page's "
             "GET /state poll is the only traffic, and it is what keeps the request "
             "carried (§10.8 H6)")
        await asyncio.sleep(10.0)
        held = await cell.requests()
        verdict = await cell.verdicts()
        check(near(held["HmiTractionRequest"], 0.60)
              and near(verdict["ForkliftTractionSpeedRef"], 0.0),
              f"after 10 s of silence the demand still stands at "
              f"{held['HmiTractionRequest']} and the ref is still "
              f"{verdict['ForkliftTractionSpeedRef']} — nothing resumed and nothing crept")

        # 5.4.4 assert the reset and LEAVE IT ASSERTED. One post; the backend
        # rewrites the level every cycle from here until the release at 5.4.8.
        rest(args.hmi, traction=0.60, teleop=True, reset=True)
        await asyncio.sleep(0.5)
        samples = []
        for _ in range(20):
            samples.append((await cell.read("HmiResetRequest"))["HmiResetRequest"])
            await asyncio.sleep(0.05)
        check(all(samples),
              f"5.4.4 HmiResetRequest reads TRUE on the server in {sum(samples)} of "
              f"{len(samples)} samples over 1.0 s — the reset is HELD, which is what "
              f"m4f-08 finding 3 said the page could not produce")
        verdict = await cell.verdicts()
        check(verdict["ForkliftObstacleStopActive"] is True
              and verdict["ForkliftResetRequired"] is True,
              f"and it is REFUSED while the obstacle is still in the zone: "
              f"ForkliftObstacleStopActive {verdict['ForkliftObstacleStopActive']}, "
              f"ForkliftResetRequired {verdict['ForkliftResetRequired']} — causeGone is "
              f"false on C3")

        # 5.4.5 attempt to drive out: release and re-assert THE ENABLE, not the
        # reset, which stays asserted — every post carries the held reset level.
        rest(args.hmi, traction=0.60, teleop=False, reset=True)
        await asyncio.sleep(0.4)
        rest(args.hmi, traction=0.60, teleop=True, reset=True)
        await asyncio.sleep(0.6)
        verdict = await cell.verdicts()
        during = await cell.read("HmiResetRequest")
        check(verdict["ForkliftTeleopActive"] is False and during["HmiResetRequest"] is True,
              f"5.4.5 the enable is refused while a latch stands, so the machine cannot "
              f"drive itself clear — ForkliftTeleopActive "
              f"{verdict['ForkliftTeleopActive']} — and the reset stayed asserted "
              f"across both posts ({during['HmiResetRequest']}), so the hold is unbroken")

        cell.state["ForkliftObstacleInStopZone"] = False   # 5.4.6, control untouched
        await until(lambda: _field_clear(cell), 5.0)
        await asyncio.sleep(1.0)
        during = await cell.read("HmiResetRequest", "ForkliftObstacleInStopZone")
        verdict = await cell.verdicts()
        check(during["ForkliftObstacleInStopZone"] is False
              and during["HmiResetRequest"] is True,
              f"5.4.6 the zone cleared with the reset STILL ASSERTED — zone "
              f"{during['ForkliftObstacleInStopZone']}, HmiResetRequest "
              f"{during['HmiResetRequest']}")
        check(verdict["ForkliftObstacleStopActive"] is True
              and verdict["ForkliftResetRequired"] is True,
              f"and the latch STANDS: the field clearing does not release it, and the "
              f"still-asserted reset supplies no edge — the edge it did produce "
              f"happened while the cause was still standing")

        note("5.4.7 stuck reset: 10 more seconds with the zone clear and the button "
             "still down")
        await asyncio.sleep(10.0)
        verdict = await cell.verdicts()
        stuck = await cell.read("HmiResetRequest")
        check(stuck["HmiResetRequest"] is True
              and verdict["ForkliftObstacleStopActive"] is True
              and verdict["ForkliftResetRequired"] is True,
              f"the latch NEVER clears for as long as it is held — HmiResetRequest "
              f"{stuck['HmiResetRequest']}, ForkliftObstacleStopActive "
              f"{verdict['ForkliftObstacleStopActive']}, ForkliftResetRequired "
              f"{verdict['ForkliftResetRequired']}. No elapsed time makes an edge appear")

        rest(args.hmi, traction=0.60, teleop=True)          # 5.4.8 release
        released = await until(lambda: _low(cell, "HmiResetRequest"), 5.0)
        check(bool(released),
              "5.4.8 released — HmiResetRequest reads FALSE on the server")
        rest(args.hmi, traction=0.60, teleop=True, reset=True)   # the fresh edge
        cleared = await wait_for(cell, "ForkliftResetRequired", False, 8)
        check(bool(cleared),
              "and on that FRESH rising edge every latch clears — ForkliftResetRequired "
              "FALSE")
        await asyncio.sleep(0.5)
        verdict = await cell.verdicts()
        check(verdict["ForkliftObstacleStopActive"] is False,
              f"ForkliftObstacleStopActive cleared with it — "
              f"{verdict['ForkliftObstacleStopActive']}")
        check(verdict["ForkliftTeleopActive"] is False
              and near(verdict["ForkliftTractionSpeedRef"], 0.0),
              f"and NOTHING MOVED: teleop is still FALSE though the enable has been "
              f"asserted throughout, because a level that never fell produces no edge — "
              f"ref {verdict['ForkliftTractionSpeedRef']}")

        rest(args.hmi, traction=0.60)                       # 5.4.9 release the enable
        await until(lambda: _low(cell, "HmiTeleopRequest"), 5.0)
        rest(args.hmi, traction=0.60, teleop=True)
        driving = await until(
            lambda: _ref(cell, "ForkliftTractionSpeedRef", 0.60), 8)
        check(bool(driving),
              "5.4.9 released and re-asserted, the enable produces a real edge, teleop "
              "returns and the refs follow the operator again — 0.60 m/s")
        rest(args.hmi)
    finally:
        beacon.stop()
        if hmi.poll() is None:
            hmi.terminate()
            try:
                hmi.wait(timeout=10)
            except subprocess.TimeoutExpired:
                hmi.kill()
        log.close()

    note(f"the page beacon polled GET /state {beacon.polls} times, at "
         f"{PAGE_POLL_S * 1000:.0f} ms, except while it was deliberately frozen for K1")
    cell._run = False
    try:
        await asyncio.wait_for(pump, timeout=3.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pump.cancel()
    await cell.close()
    print(f"\n{'FAILURES: ' + str(len(FAILURES)) if FAILURES else 'no failures'}")
    for failure in FAILURES:
        print(f"  - {failure}")
    print(f"HMI stdout/stderr: {log_path}")
    return 1 if FAILURES else 0


def _fmt(value):
    return f"{value:.3f}" if isinstance(value, float) else str(value)


async def _ref(cell: Cell, name: str, expected: float):
    reading = await cell.read(name)
    return reading if near(reading[name], expected) else None


async def _low(cell: Cell, name: str):
    reading = await cell.read(name)
    return reading if reading[name] is False else None


async def _field_clear(cell: Cell):
    reading = await cell.read("ForkliftObstacleInStopZone")
    return reading if reading["ForkliftObstacleInStopZone"] is False else None


async def _all_at_rest(cell: Cell):
    reading = await cell.requests()
    at_rest = (near(reading["HmiTractionRequest"], 0.0)
               and near(reading["HmiSteerRequest"], 0.0)
               and near(reading["HmiForkRequest"], 0.0)
               and reading["HmiTeleopRequest"] is False
               and reading["HmiResetRequest"] is False)
    return reading if at_rest else None


class DoubleControl:
    def __init__(self, command: str | None) -> None:
        self.command = command
        self.proc: subprocess.Popen | None = None

    def start(self) -> None:
        if not self.command or self.proc is not None:
            return
        self.proc = subprocess.Popen(self.command, shell=True,
                                     stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL,
                                     start_new_session=True)
        time.sleep(3.0)

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            self.proc.wait(timeout=10)
        except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
            self.proc.kill()
        self.proc = None


def main() -> int:
    parser = argparse.ArgumentParser(
        description="demonstrate §10.8 H6 and the held reset against the PLC logic "
                    "double")
    parser.add_argument("--endpoint", default="opc.tcp://127.0.0.1:4850/")
    parser.add_argument("--hmi", default="http://127.0.0.1:8090")
    parser.add_argument("--config", default=str(HMI_DIR / "config-logic-double.yaml"))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--scratch", default="/tmp/amr-hmi")
    parser.add_argument("--evidence-csv", default=None)
    parser.add_argument("--double-cmd", required=True)
    args = parser.parse_args()

    host = urlparse(args.endpoint).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"REFUSED: {args.endpoint} is not loopback. This harness runs against a "
              f"double only; the live PLCSIM endpoint is the owner's to drive.")
        return 3

    double = DoubleControl(args.double_cmd)
    try:
        return asyncio.run(run(args, double))
    finally:
        double.stop()


if __name__ == "__main__":
    sys.exit(main())
