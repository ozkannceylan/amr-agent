#!/usr/bin/env python3
"""TEST HARNESS — drives the commissioning HMI and watches the server.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

It plays two roles at once, both from outside the HMI process:

* **the operator**, by posting control positions to the HMI's own loopback
  `/control` endpoint — the same endpoint the browser posts to, so what is
  exercised is the real path and not a stub; and
* **an independent observer**, by opening its OWN OPC UA session to the same
  server and reading the nodes back. Nothing it reports comes from the HMI's
  session, so "the write landed" is the server's answer and not the HMI's.

It never contacts PLCSIM Advanced: a non-loopback endpoint is refused outright,
on the precedent of `bridge/tools/check_forklift_slots.py`.

The checks, each named for the rule it tests:

    J   the write allowlist refuses a config that names anything else
    UI  the page is served and references nothing outside itself
    B   joystick and fork map to the three Real requests in their declared
        units (`opcua-nodes.md` §10.4)
    A   all six nodes written EVERY cycle regardless of change (§10.4, §10.8 H1)
        — proven by overwriting a node from this session and watching the HMI
        repair it, which a write-on-change client would never do
    C   deadman: release writes zeros immediately
    D   HmiTeleopRequest is a LEVEL, asserted and withdrawn (§10.4)
    E   HmiResetRequest is momentary: TRUE for one write cycle, then FALSE
    F   the heartbeat advances every cycle
    M   the metrics panel reads Input/Output/Status/Link and nothing else
    G   session lost and regained: the counter is NOT reset (§10.8 H4) and the
        requests come back at rest rather than at the standing demand
    I   clean shutdown: NO farewell value, the server retains the last written
        values and the heartbeat simply stops (§10.8 H5)
    H   backend fault: one final zeros write attempt lands, heartbeat stops
    K   no node outside the six appears as a write in the HMI's log

Run (from the repository root):
    ~/amr-hmi-venv/bin/python hmi/tools/check_hmi_writes.py \
        --endpoint opc.tcp://127.0.0.1:4847/amr-agent/celldouble/ \
        --hmi http://127.0.0.1:8089 --config hmi/config-double.yaml \
        --double-cmd "<command that starts the bridge test double on 4847>"
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from asyncua import Client, ua

HERE = Path(__file__).resolve().parent
HMI_DIR = HERE.parent

HMI_NODES = ("HmiTractionRequest", "HmiSteerRequest", "HmiForkRequest",
             "HmiTeleopRequest", "HmiResetRequest")
OTHER_FORKLIFT_NODES = (
    ("Input", "ForkliftForkHeight"), ("Input", "ForkliftLinearSpeed"),
    ("Input", "ForkliftObstacleInStopZone"), ("Input", "ForkliftObstacleMinDistance"),
    ("Output", "ForkliftTractionSpeedRef"), ("Output", "ForkliftSteerAngleRef"),
    ("Output", "ForkliftForkSpeedRef"), ("Status", "ForkliftTeleopActive"),
    ("Status", "ForkliftObstacleStopActive"), ("Status", "ForkliftSpeedLimitActive"),
    ("Status", "ForkliftResetRequired"), ("Link", "HmiLinkOk"),
)
#: `opcua-nodes.md` §10.4's declared engineering range, mirrored here to form the
#: harness's EXPECTATION only. The value in force is `hmi_server.py`'s constant.
STEER_MAX_RAD = 1.31

FAILURES: list[str] = []


def ok(message: str) -> None:
    print(f"   ok   {message}", flush=True)


def bad(message: str) -> None:
    FAILURES.append(message)
    print(f"   FAIL {message}", flush=True)


def check(condition: bool, message: str) -> bool:
    (ok if condition else bad)(message)
    return bool(condition)


def near(a, b, tol=2e-5) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def head(title: str) -> None:
    print(f"\n{title}", flush=True)


# --------------------------------------------------------------------------- #

def post_control(base: str, **payload) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{base}/control", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        response.read()


def get_state(base: str) -> dict:
    with urllib.request.urlopen(f"{base}/state", timeout=3) as response:
        return json.loads(response.read())


def get_page(base: str) -> str:
    with urllib.request.urlopen(f"{base}/", timeout=3) as response:
        return response.read().decode("utf-8")


def state_is(base: str, wanted: str) -> bool:
    try:
        return get_state(base)["session"]["state"] == wanted
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError):
        return False


async def until(predicate, timeout: float = 6.0, poll: float = 0.05):
    """Poll a synchronous predicate to completion. Bounded, foreground, no
    detached wait (LESSONS 2026-07-27)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        await asyncio.sleep(poll)
    return None


async def until_async(coro_factory, timeout: float = 6.0, poll: float = 0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = await coro_factory()
        if value is not None:
            return value
        await asyncio.sleep(poll)
    return None


class Observer:
    """This harness's own OPC UA session — never the HMI's."""

    def __init__(self, endpoint: str) -> None:
        self.endpoint = endpoint
        self.client: Client | None = None
        self.nodes: dict[str, object] = {}

    async def connect(self, retries: int = 40) -> None:
        last = None
        for _ in range(retries):
            try:
                client = Client(url=self.endpoint)
                client.name = "amr-agent-hmi-harness-observer"
                await client.connect()
                break
            except Exception as exc:  # noqa: BLE001 - the double may still be starting
                last = exc
                await asyncio.sleep(0.25)
        else:
            raise RuntimeError(f"observer could not connect to {self.endpoint}: {last}")
        idx_si = await client.get_namespace_index(
            "http://www.siemens.com/simatic-s7-opcua")
        idx = await client.get_namespace_index("http://DemoCell")
        objects = client.nodes.objects
        prefix = [f"{idx_si}:ServerInterfaces", f"{idx}:DemoCell", f"{idx}:Forklift"]

        async def child(*parts):
            return await objects.get_child(prefix + [f"{idx}:{p}" for p in parts])

        for name in HMI_NODES:
            self.nodes[name] = await child("Hmi", name)
        self.nodes["HmiHeartbeat"] = await child("Link", "HmiHeartbeat")
        for folder, name in OTHER_FORKLIFT_NODES:
            self.nodes[name] = await child(folder, name)
        self.client = client

    async def read(self, *names) -> dict:
        values = await self.client.read_values([self.nodes[n] for n in names])
        return dict(zip(names, values))

    async def read_all_hmi(self) -> dict:
        return await self.read(*HMI_NODES, "HmiHeartbeat")

    async def overwrite(self, name: str, value, vtype) -> None:
        await self.nodes[name].write_value(ua.DataValue(ua.Variant(value, vtype)))

    async def close(self) -> None:
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001 - teardown is best effort
                pass
            self.client = None


async def settle(observer: Observer, cycles: float = 4.0, period: float = 0.1) -> dict:
    await asyncio.sleep(cycles * period)
    return await observer.read_all_hmi()


def doctor_config(source: Path, target: Path) -> None:
    """Rewrite the write table so it names an `Output/` node — a config that
    tries to give this client a write permission the code does not grant."""
    lines = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("HmiResetRequest:"):
            line = ('    ForkliftTractionSpeedRef:    '
                    '["Forklift", "Output", "ForkliftTractionSpeedRef"]')
        lines.append(line)
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------- #

async def run(args: argparse.Namespace, double: DoubleControl) -> int:
    print(f"HMI write harness — server {args.endpoint}, HMI {args.hmi}")
    print("The server is the BRIDGE TEST DOUBLE. It runs no standard program, so every "
          "Forklift/Status/ node and HmiLinkOk hold their start values for the whole "
          "run: that is the honest answer, not a defect. The second evidence pass, "
          "against the PLC logic double, is where the lamps move.")

    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    # ---- J: the allowlist, before anything is started --------------------- #
    head("J. the write allowlist refuses a configuration naming anything else")
    doctored = scratch / "hmi-config-doctored.yaml"
    doctor_config(Path(args.config), doctored)
    proc = subprocess.run([args.python, str(HMI_DIR / "hmi_server.py"),
                           "--config", str(doctored)],
                          capture_output=True, text=True, timeout=60)
    refusal = [line for line in (proc.stdout + proc.stderr).strip().splitlines() if line]
    check(proc.returncode != 0,
          f"the HMI refuses to start on that configuration — exit {proc.returncode}")
    check(any("write set" in line or "ForkliftTractionSpeedRef" in line
              for line in refusal),
          f"and says why — {refusal[-1] if refusal else '(no output)'}")

    double.start()
    observer = Observer(args.endpoint)
    await observer.connect()

    log_path = scratch / "hmi-run.log"
    log = open(log_path, "w", encoding="utf-8")
    hmi = subprocess.Popen(
        [args.python, str(HMI_DIR / "hmi_server.py"), "--config", args.config]
        + (["--evidence-csv", args.evidence_csv] if args.evidence_csv else []),
        stdout=log, stderr=subprocess.STDOUT)
    try:
        if not check(bool(await until(lambda: state_is(args.hmi, "CONNECTED"), 20)),
                     "the HMI reached CONNECTED against the double"):
            return 1
        state = get_state(args.hmi)
        print(f"        session timeout requested "
              f"{state['session']['requested_session_timeout_ms']:.0f} ms, granted "
              f"{state['session']['granted_session_timeout_ms']:.0f} ms")

        head("UI. the page is served and references nothing outside itself")
        page = get_page(args.hmi)
        check("<title>amr-agent forklift commissioning HMI</title>" in page,
              f"GET / serves the operator page — {len(page)} bytes")
        externals = [token for token in ("http://", "https://", "<link ", "<img ",
                                         "@import", "url(", "srcset", "<script src")
                     if token in page]
        check(not externals,
              "no external stylesheet, font, image, script or @import in the page — "
              + (", ".join(externals) if externals else "none of the eight tokens found"))

        # ---- B: the joystick and fork mapping ----------------------------- #
        head("B. the joystick and the fork buttons map to the three Real requests (§10.4)")
        post_control(args.hmi, traction=0.62, steer=-0.5, fork=1.0, teleop=False)
        values = await settle(observer)
        check(near(values["HmiTractionRequest"], 0.62),
              f"HmiTractionRequest is the joystick's Y as a fraction — "
              f"{values['HmiTractionRequest']}")
        check(near(values["HmiSteerRequest"], -0.5 * STEER_MAX_RAD),
              f"HmiSteerRequest is the joystick's X in rad, X * {STEER_MAX_RAD} — "
              f"{values['HmiSteerRequest']}")
        check(near(values["HmiForkRequest"], 1.0),
              f"HmiForkRequest is the fork button as a fraction — "
              f"{values['HmiForkRequest']}")

        # ---- A: every cycle, regardless of change ------------------------- #
        head("A. all six nodes are written EVERY cycle regardless of change (§10.4, H1)")
        before = await observer.read_all_hmi()
        await observer.overwrite("HmiTractionRequest", -0.9, ua.VariantType.Float)
        overwritten = (await observer.read("HmiTractionRequest"))["HmiTractionRequest"]
        check(near(overwritten, -0.9),
              f"another client overwrote HmiTractionRequest on the server — {overwritten}")
        started = time.monotonic()
        repaired = await until_async(
            lambda: _repaired(observer, "HmiTractionRequest", 0.62), 3.0, 0.01)
        check(repaired is not None,
              f"the HMI rewrote its own value with no operator action — {repaired} after "
              f"{round((time.monotonic() - started) * 1000)} ms; a write-on-change client "
              f"would have left the overwrite standing")
        after = await observer.read_all_hmi()
        check(after["HmiHeartbeat"] != before["HmiHeartbeat"],
              f"and the heartbeat advanced across the same window — "
              f"{before['HmiHeartbeat']} -> {after['HmiHeartbeat']}")

        # ---- C: the deadman ------------------------------------------------ #
        head("C. release writes zeros immediately (the deadman)")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=False)
        values = await settle(observer, cycles=3)
        check(near(values["HmiTractionRequest"], 0.0)
              and near(values["HmiSteerRequest"], 0.0)
              and near(values["HmiForkRequest"], 0.0),
              f"all three Real requests read zero — {values['HmiTractionRequest']}, "
              f"{values['HmiSteerRequest']}, {values['HmiForkRequest']}")

        # ---- D: teleop is a level ------------------------------------------ #
        head("D. HmiTeleopRequest is a level, asserted and withdrawn (§10.4)")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=True)
        values = await settle(observer, cycles=3)
        check(values["HmiTeleopRequest"] is True, f"asserted — {values['HmiTeleopRequest']}")
        await asyncio.sleep(0.5)
        values = await observer.read_all_hmi()
        check(values["HmiTeleopRequest"] is True,
              f"and still asserted half a second later with no operator action — a level, "
              f"not an edge — {values['HmiTeleopRequest']}")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=False)
        values = await settle(observer, cycles=3)
        check(values["HmiTeleopRequest"] is False,
              f"withdrawn by writing FALSE — {values['HmiTeleopRequest']}")

        # ---- E: reset is momentary ----------------------------------------- #
        head("E. HmiResetRequest is momentary: TRUE for one write cycle, then FALSE")
        samples: list[tuple[bool, int]] = []
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=False, reset=True)
        t0 = time.monotonic()
        while time.monotonic() - t0 < 1.0:
            reading = await observer.read("HmiResetRequest", "HmiHeartbeat")
            samples.append((reading["HmiResetRequest"], reading["HmiHeartbeat"]))
            await asyncio.sleep(0.01)
        true_samples = [s for s in samples if s[0] is True]
        heartbeats = {s[1] for s in true_samples}
        check(bool(true_samples),
              f"the pulse was observed TRUE on the server — {len(true_samples)} of "
              f"{len(samples)} samples over 1.0 s")
        check(len(heartbeats) <= 2,
              f"and it spanned {len(heartbeats)} heartbeat value(s) — one write cycle, "
              f"sampled across a 100 ms cycle boundary")
        check(samples[-1][0] is False,
              f"and it reads FALSE again afterwards, so the PLC sees the node low between "
              f"presses and can arm its edge per link session (§10.8 P6) — {samples[-1][0]}")

        # ---- F: the heartbeat ---------------------------------------------- #
        head("F. the heartbeat advances every cycle (H1)")
        first = await observer.read("HmiHeartbeat")
        await asyncio.sleep(2.0)
        second = await observer.read("HmiHeartbeat")
        delta = (second["HmiHeartbeat"] - first["HmiHeartbeat"]) % 65536
        check(delta > 0, f"the counter changed over 2.0 s — {first['HmiHeartbeat']} -> "
                         f"{second['HmiHeartbeat']}, {delta} increments")
        state = get_state(args.hmi)
        print(f"        HMI-reported write RTT last {state['write']['rtt_last_ms']} ms, "
              f"median of 10 {state['write']['rtt_median10_ms']} ms; measured cycle "
              f"period {state['write']['period_ms_measured']} ms "
              f"(target {state['write']['period_ms_target']} ms)")
        print(f"        heartbeat {state['heartbeat']['value']} after "
              f"{state['write']['cycles']} write cycles; last good write "
              f"{state['session']['since_last_good_write_ms']} ms ago")

        # ---- M: the metrics panel ------------------------------------------ #
        head("M. the metrics panel reads Input/Output/Status/Link and nothing else")
        await observer.overwrite("ForkliftForkHeight", 1.23, ua.VariantType.Float)
        await observer.overwrite("ForkliftLinearSpeed", -0.44, ua.VariantType.Float)
        await observer.overwrite("ForkliftObstacleMinDistance", 2.75, ua.VariantType.Float)
        await observer.overwrite("ForkliftObstacleInStopZone", False, ua.VariantType.Boolean)
        seen = await until(lambda: _metric(args.hmi, "ForkliftForkHeight", 1.23), 3.0)
        state = get_state(args.hmi)
        metrics = state["metrics"] or {}
        check(seen is not None,
              f"ForkliftForkHeight reached the panel — {metrics.get('ForkliftForkHeight')}")
        check(near(metrics.get("ForkliftLinearSpeed"), -0.44),
              f"ForkliftLinearSpeed — {metrics.get('ForkliftLinearSpeed')}")
        check(near(metrics.get("ForkliftObstacleMinDistance"), 2.75),
              f"ForkliftObstacleMinDistance — {metrics.get('ForkliftObstacleMinDistance')}")
        check("ForkliftTractionSpeedRef" in metrics,
              f"ForkliftTractionSpeedRef is on the panel beside the measured speed — "
              f"{metrics.get('ForkliftTractionSpeedRef')}")
        lamp_names = ("ForkliftTeleopActive", "ForkliftObstacleStopActive",
                      "ForkliftSpeedLimitActive", "ForkliftResetRequired", "HmiLinkOk")
        check(all(key in metrics for key in lamp_names),
              "the four status lamps and HmiLinkOk are on the panel — "
              + ", ".join(f"{k}={metrics.get(k)}" for k in lamp_names))
        check(not any(key in metrics for key in HMI_NODES),
              "and no Forklift/Hmi/ node is read back into the display — the requests are "
              "this client's output, not its state")
        check(state["metrics_age_ms"] is not None and state["metrics_age_ms"] < 600,
              f"the panel is polled at 5 Hz — age {state['metrics_age_ms']} ms")

        # ---- G: disconnect and reconnect ------------------------------------ #
        head("G. session lost and regained (§10.8 H4, H5 on reconnect)")
        post_control(args.hmi, traction=1.0, steer=1.0, fork=-1.0, teleop=True)
        standing = await settle(observer, cycles=4)
        check(near(standing["HmiTractionRequest"], 1.0),
              f"a full traction demand is standing before the loss — "
              f"{standing['HmiTractionRequest']}")
        heartbeat_before = standing["HmiHeartbeat"]
        await observer.close()
        double.stop()
        check(bool(await until(lambda: state_is(args.hmi, "RECONNECTING"), 8)),
              f"the HMI reports RECONNECTING while the server is gone — "
              f"{get_state(args.hmi)['session']['reason']}")
        check(get_state(args.hmi)["heartbeat"]["running"] is False,
              "and the heartbeat is not advancing, because there is nowhere to write it")
        double.start()
        check(bool(await until(lambda: state_is(args.hmi, "CONNECTED"), 25)),
              "the HMI reconnected on its own, with no operator action")
        observer = Observer(args.endpoint)
        await observer.connect()
        regained = await settle(observer, cycles=8)
        check(near(regained["HmiTractionRequest"], 0.0)
              and near(regained["HmiSteerRequest"], 0.0)
              and near(regained["HmiForkRequest"], 0.0)
              and regained["HmiTeleopRequest"] is False,
              f"and the requests come back AT REST, not at the standing demand — "
              f"{regained['HmiTractionRequest']}, {regained['HmiSteerRequest']}, "
              f"{regained['HmiForkRequest']}, teleop={regained['HmiTeleopRequest']}")
        check(regained["HmiHeartbeat"] > heartbeat_before,
              f"the counter is NOT reset across the reconnect (H4) — {heartbeat_before} "
              f"before the loss, {regained['HmiHeartbeat']} after, and the double came "
              f"back up with its own start value 0")

        # ---- I: clean shutdown --------------------------------------------- #
        head("I. clean shutdown writes NO farewell value; the heartbeat stops (H5)")
        post_control(args.hmi, traction=0.35, steer=0.25, fork=0.0, teleop=True)
        held = await settle(observer, cycles=5)
        hmi.send_signal(signal.SIGTERM)
        hmi.wait(timeout=20)
        await asyncio.sleep(1.0)
        after_kill = await observer.read_all_hmi()
        await asyncio.sleep(1.5)
        later = await observer.read_all_hmi()
        check(after_kill["HmiHeartbeat"] == later["HmiHeartbeat"],
              f"the heartbeat is frozen after the kill — {after_kill['HmiHeartbeat']}, "
              f"then {later['HmiHeartbeat']} 1.5 s later")
        check(near(after_kill["HmiTractionRequest"], held["HmiTractionRequest"])
              and after_kill["HmiTeleopRequest"] is True,
              f"and the requests RETAIN their last written values — HmiTractionRequest "
              f"{after_kill['HmiTractionRequest']}, HmiTeleopRequest "
              f"{after_kill['HmiTeleopRequest']}. That is exactly why §10.8 exists: a "
              f"stopped HMI is not detectable from the requests alone")
    finally:
        if hmi.poll() is None:
            hmi.terminate()
            try:
                hmi.wait(timeout=10)
            except subprocess.TimeoutExpired:
                hmi.kill()
        log.close()

    # ---- H: the backend-fault path ----------------------------------------- #
    head("H. backend fault: one final zeros write attempt lands, then the heartbeat stops")
    fault_log = scratch / "hmi-fault.log"
    handle = open(fault_log, "w", encoding="utf-8")
    faulted = subprocess.Popen(
        [args.python, str(HMI_DIR / "hmi_server.py"), "--config", args.config,
         "--inject-fault-after-s", "5.0"],
        stdout=handle, stderr=subprocess.STDOUT)
    try:
        await until(lambda: state_is(args.hmi, "CONNECTED"), 20)
        post_control(args.hmi, traction=-0.8, steer=0.9, fork=1.0, teleop=True)
        standing = await settle(observer, cycles=5)
        check(near(standing["HmiTractionRequest"], -0.8),
              f"a demand is standing when the fault is injected — "
              f"{standing['HmiTractionRequest']}")
        check(bool(await until(lambda: state_is(args.hmi, "DOWN"), 15)),
              "the HMI reports DOWN — "
              + str(get_state(args.hmi)["session"]["reason"]))
        zeroed = await observer.read_all_hmi()
        check(near(zeroed["HmiTractionRequest"], 0.0)
              and near(zeroed["HmiSteerRequest"], 0.0)
              and near(zeroed["HmiForkRequest"], 0.0)
              and zeroed["HmiTeleopRequest"] is False,
              f"the final zeros write LANDED on the server — "
              f"{zeroed['HmiTractionRequest']}, {zeroed['HmiSteerRequest']}, "
              f"{zeroed['HmiForkRequest']}, teleop={zeroed['HmiTeleopRequest']}")
        frozen = zeroed["HmiHeartbeat"]
        await asyncio.sleep(2.0)
        still = await observer.read_all_hmi()
        check(still["HmiHeartbeat"] == frozen,
              f"and the heartbeat stopped and stayed stopped — {frozen}, then "
              f"{still['HmiHeartbeat']} 2.0 s later")
        check(get_state(args.hmi)["heartbeat"]["running"] is False,
              "the HMI says so itself, on the banner the operator is looking at")
    finally:
        if faulted.poll() is None:
            faulted.terminate()
            try:
                faulted.wait(timeout=10)
            except subprocess.TimeoutExpired:
                faulted.kill()
        handle.close()

    # ---- K: the six, and only the six -------------------------------------- #
    head("K. the HMI touched the six HMI-writable nodes and nothing else")
    log_text = (log_path.read_text(encoding="utf-8", errors="replace")
                + fault_log.read_text(encoding="utf-8", errors="replace"))
    strays = sorted({name for _, name in OTHER_FORKLIFT_NODES if name in log_text})
    check(not strays,
          "no Forklift/Input/, Output/ or Status/ node name appears anywhere in the "
          "HMI's log — " + (", ".join(strays) if strays else "none of the twelve"))
    print("        (the read set is resolved by browse path from config; the write set is "
          "the code-side allowlist in hmi_server.py, and check J shows the process "
          "refuses to start when a config names anything else)")

    await observer.close()
    print(f"\n{'FAILURES: ' + str(len(FAILURES)) if FAILURES else 'no failures'}")
    for failure in FAILURES:
        print(f"  - {failure}")
    print(f"HMI stdout/stderr:      {log_path}")
    print(f"fault run stdout/stderr: {fault_log}")
    return 1 if FAILURES else 0


async def _repaired(observer: Observer, name: str, expected: float):
    value = (await observer.read(name))[name]
    return value if near(value, expected) else None


def _metric(base: str, name: str, expected: float):
    try:
        metrics = get_state(base)["metrics"] or {}
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return None
    return metrics.get(name) if near(metrics.get(name), expected) else None


class DoubleControl:
    """Starts and stops the test double, so check G can end a session."""

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
        time.sleep(2.0)

    def stop(self) -> None:
        if self.proc is None:
            return
        try:
            os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
            self.proc.wait(timeout=10)
        except (ProcessLookupError, PermissionError, subprocess.TimeoutExpired):
            self.proc.kill()
        self.proc = None
        time.sleep(1.0)


def main() -> int:
    parser = argparse.ArgumentParser(description="drive the HMI, watch the server")
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--hmi", default="http://127.0.0.1:8089")
    parser.add_argument("--config", default=str(HMI_DIR / "config-double.yaml"))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--scratch", default="/tmp/amr-hmi")
    parser.add_argument("--evidence-csv", default=None)
    parser.add_argument("--double-cmd", required=True,
                        help="shell command that starts the test double; the harness "
                             "owns its lifetime, because check G ends a session")
    args = parser.parse_args()

    host = urlparse(args.endpoint).hostname or ""
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"REFUSED: {args.endpoint} is not loopback. This harness runs against a "
              f"test double only; the live PLCSIM endpoint is the owner's to drive.")
        return 3

    double = DoubleControl(args.double_cmd)
    try:
        return asyncio.run(run(args, double))
    finally:
        double.stop()


if __name__ == "__main__":
    sys.exit(main())
