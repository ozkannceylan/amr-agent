#!/usr/bin/env python3
"""TEST HARNESS — the HMI against the PLC LOGIC DOUBLE, lamps and metrics moving.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI.         #
    #############################################################

The second evidence pass. The first (`check_hmi_writes.py`) runs against the
bridge test double, which serves the address space but runs no program, so every
`Forklift/Status/` node and `HmiLinkOk` hold their start values for a whole run.
Here the server is `plc/forklift/double/`, the PLC layer's rehearsal stand-in for
the TIA build of `plc/forklift/SPEC.md`, so **real §7 logic answers**: the
fork-height speed cap, the obstacle latch, the monitored reset and the HMI
heartbeat watchdog. That is what makes the lamps and the metrics move.

Three processes, three roles, and the separation is the point:

    this harness   plays the BRIDGE and the PLANT — it advances
                   `DemoCell/Link/BridgeHeartbeat` and writes the four
                   `Forklift/Input/` nodes, which is what the bridge does
                   (`opcua-nodes.md` §10.5). It never writes an `Hmi` node.
    the HMI        plays the OPERATOR, over its own loopback HTTP endpoint. It
                   writes the five requests and `HmiHeartbeat`, and nothing else.
    the double     plays the PLC. It owns every verdict.

Nothing observed here is evidence about the TIA Portal build. It is a rehearsal
and any divergence resolves toward TIA and `SPEC.md`, never toward the double.

Run (from the repository root):
    ~/amr-hmi-venv/bin/python hmi/tools/check_hmi_teleop_loop.py \
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

#: What the harness writes, standing in for the bridge (`opcua-nodes.md` §10.5,
#: §9.7). It writes NO `Forklift/Hmi/` node and no `Forklift/Link/HmiHeartbeat`:
#: those are the HMI's, and the two writable sets are disjoint by construction.
PLANT_INPUTS = (
    ("Forklift", "Input", "ForkliftForkHeight", F),
    ("Forklift", "Input", "ForkliftLinearSpeed", F),
    ("Forklift", "Input", "ForkliftObstacleInStopZone", B),
    ("Forklift", "Input", "ForkliftObstacleMinDistance", F),
)
#: Relative to the DemoCell interface node, as everywhere in opcua-nodes.md.
BRIDGE_HEARTBEAT = ("Link", "BridgeHeartbeat", U)

WATCHED = ("ForkliftTeleopActive", "ForkliftObstacleStopActive",
           "ForkliftSpeedLimitActive", "ForkliftResetRequired", "HmiLinkOk",
           "ForkliftTractionSpeedRef", "ForkliftSteerAngleRef",
           "ForkliftForkSpeedRef")
LAMPS = ("ForkliftTeleopActive", "ForkliftObstacleStopActive",
         "ForkliftSpeedLimitActive", "ForkliftResetRequired", "HmiLinkOk")

FAILURES: list[str] = []


def ok(message: str) -> None:
    print(f"   ok   {message}", flush=True)


def bad(message: str) -> None:
    FAILURES.append(message)
    print(f"   FAIL {message}", flush=True)


def check(condition, message: str) -> bool:
    (ok if condition else bad)(message)
    return bool(condition)


def near(a, b, tol=1e-3) -> bool:
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def head(title: str) -> None:
    print(f"\n{title}", flush=True)


def post_control(base: str, **payload) -> None:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(f"{base}/control", data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=3) as response:
        response.read()


def get_state(base: str) -> dict:
    with urllib.request.urlopen(f"{base}/state", timeout=3) as response:
        return json.loads(response.read())


def panel(base: str) -> dict:
    try:
        return get_state(base).get("metrics") or {}
    except (urllib.error.URLError, OSError, json.JSONDecodeError):
        return {}


async def panel_shows(base: str, key: str, wanted, tol=2e-3, timeout=3.0):
    """Wait, bounded, for the HMI's display to carry a value.

    The panel is polled at 5 Hz, so it is up to one poll period behind the
    server. That lag is the display's, not the write path's: the write cycle
    runs at 10 Hz and is measured separately.
    """
    deadline = time.monotonic() + timeout
    seen = None
    while time.monotonic() < deadline:
        seen = panel(base).get(key)
        if seen == wanted or (isinstance(wanted, float) and near(seen, wanted, tol)):
            return seen
        await asyncio.sleep(0.05)
    return None


class PlantAndBridge:
    """The harness's own session. It writes what the bridge writes and reads the
    PLC's verdicts back; it never touches a `Forklift/Hmi/` node."""

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
        self._transitions: list[str] = []
        self._last: dict = {}

    async def connect(self, retries: int = 60) -> None:
        last = None
        for _ in range(retries):
            try:
                client = Client(url=self.endpoint)
                client.name = "amr-agent-hmi-harness-plant"
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

        for group, folder, name, _ in PLANT_INPUTS:
            self.nodes[name] = await child(group, folder, name)
        self.nodes["BridgeHeartbeat"] = await child(*BRIDGE_HEARTBEAT[:2])
        for name in ("ForkliftTractionSpeedRef", "ForkliftSteerAngleRef",
                     "ForkliftForkSpeedRef"):
            self.nodes[name] = await child("Forklift", "Output", name)
        for name in ("ForkliftTeleopActive", "ForkliftObstacleStopActive",
                     "ForkliftSpeedLimitActive", "ForkliftResetRequired"):
            self.nodes[name] = await child("Forklift", "Status", name)
        self.nodes["HmiLinkOk"] = await child("Forklift", "Link", "HmiLinkOk")
        self.nodes["BridgeLinkOk"] = await child("Link", "BridgeLinkOk")
        self.client = client

    async def write_inputs(self) -> None:
        """R3's shape: every configured input carries a real sample BEFORE the
        heartbeat starts, so no verdict is formed from a start value."""
        for _, _, name, vtype in PLANT_INPUTS:
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

    def stop(self) -> None:
        self._run = False

    async def read(self, *names) -> dict:
        values = await self.client.read_values([self.nodes[n] for n in names])
        return dict(zip(names, values))

    async def verdicts(self) -> dict:
        reading = await self.read(*WATCHED, "BridgeLinkOk")
        changed = {k: v for k, v in reading.items()
                   if self._last.get(k, object()) != v}
        if changed and self._last:
            self._transitions.append(
                f"        {time.strftime('%H:%M:%S')} "
                + "  ".join(f"{k}={_fmt(v)}" for k, v in sorted(changed.items())))
        self._last = reading
        return reading

    async def close(self) -> None:
        self.stop()
        if self.client is not None:
            try:
                await self.client.disconnect()
            except Exception:  # noqa: BLE001
                pass
            self.client = None


def _fmt(value):
    return f"{value:.3f}" if isinstance(value, float) else str(value)


async def until(coro_factory, timeout=8.0, poll=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = await coro_factory()
        if value:
            return value
        await asyncio.sleep(poll)
    return None


async def wait_verdict(plant: PlantAndBridge, name: str, wanted, timeout=8.0):
    async def probe():
        reading = await plant.verdicts()
        return reading if reading[name] == wanted else None
    return await until(probe, timeout)


# --------------------------------------------------------------------------- #

async def run(args, double) -> int:
    print(f"HMI teleop-loop harness — server {args.endpoint} (PLC LOGIC DOUBLE), "
          f"HMI {args.hmi}")
    print("Roles: this harness plays the bridge and the plant, the HMI plays the "
          "operator, the double plays the PLC and owns every verdict. Nothing here is "
          "evidence about the TIA Portal build.")
    scratch = Path(args.scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    double.start()
    plant = PlantAndBridge(args.endpoint)
    await plant.connect()
    await plant.write_inputs()
    pump = asyncio.create_task(plant.pump())

    log_path = scratch / "hmi-logic-run.log"
    log = open(log_path, "w", encoding="utf-8")
    hmi = subprocess.Popen(
        [args.python, str(HMI_DIR / "hmi_server.py"), "--config", args.config]
        + (["--evidence-csv", args.evidence_csv] if args.evidence_csv else []),
        stdout=log, stderr=subprocess.STDOUT)
    try:
        # ---- P0: the links form ------------------------------------------- #
        head("P0. both link verdicts form, and the HMI's is FALSE until the counter moves")
        first = await plant.verdicts()
        check(first["HmiLinkOk"] is False,
              f"HmiLinkOk is FALSE before the HMI has written anything — "
              f"{first['HmiLinkOk']}. 'Not yet proven stale' is not 'alive' (§10.8 P2)")
        if not check(bool(await until(lambda: asyncio.sleep(0, result=_connected(args.hmi)),
                                      25)),
                     "the HMI reached CONNECTED against the logic double"):
            return 1
        got = await wait_verdict(plant, "HmiLinkOk", True, 10)
        check(bool(got), "HmiLinkOk went TRUE once the HMI's counter had been seen to "
                         "change — the PLC's verdict on this client's heartbeat")
        check((await plant.read("BridgeLinkOk"))["BridgeLinkOk"] is True,
              "BridgeLinkOk is TRUE too — teleop needs both, and they are independent "
              "watchdogs on independent clients (§10.8 P7)")
        state = await plant.verdicts()
        check(state["ForkliftResetRequired"] is True,
              f"ForkliftResetRequired is TRUE out of the boot window — both link-lost "
              f"latches were set while the verdicts were FALSE — "
              f"{state['ForkliftResetRequired']}")
        check(await panel_shows(args.hmi, "ForkliftResetRequired", True) is True,
              "and the HMI's RESET REQUIRED banner is showing it, read from the node "
              "rather than recomputed")

        # ---- P1: the monitored reset --------------------------------------- #
        head("P1. the monitored reset clears the latches and energizes nothing")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=False, reset=True)
        cleared = await wait_verdict(plant, "ForkliftResetRequired", False, 8)
        check(bool(cleared),
              "ForkliftResetRequired went FALSE on the rising edge of HmiResetRequest")
        after = await plant.verdicts()
        check(after["ForkliftTeleopActive"] is False,
              f"and NOTHING energized: ForkliftTeleopActive is still FALSE — "
              f"{after['ForkliftTeleopActive']}")
        check(near(after["ForkliftTractionSpeedRef"], 0.0)
              and near(after["ForkliftSteerAngleRef"], 0.0)
              and near(after["ForkliftForkSpeedRef"], 0.0),
              f"and all three setpoints are still 0.0 — "
              f"{after['ForkliftTractionSpeedRef']}, {after['ForkliftSteerAngleRef']}, "
              f"{after['ForkliftForkSpeedRef']}")

        # ---- P2: the enable ------------------------------------------------- #
        head("P2. a separate rising edge of HmiTeleopRequest enables teleop")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=True)
        enabled = await wait_verdict(plant, "ForkliftTeleopActive", True, 8)
        check(bool(enabled), "ForkliftTeleopActive went TRUE — the PLC's verdict, not "
                             "the HMI's request echoed back")
        check(await panel_shows(args.hmi, "ForkliftTeleopActive", True) is True,
              "the HMI's teleop lamp followed it")

        # ---- P3: driving ---------------------------------------------------- #
        head("P3. the joystick moves the PLC's setpoints (HMI -> PLC -> plant)")
        post_control(args.hmi, traction=0.60, steer=-0.50, fork=0.0, teleop=True)
        moved = await until(
            lambda: _ref_reached(plant, "ForkliftTractionSpeedRef", 0.60), 8)
        check(bool(moved),
              f"ForkliftTractionSpeedRef = 0.60 m/s — the request 0.60 scaled by the "
              f"PLC's TRACTION_SPEED_MAX; the HMI never knew the maximum")
        reading = await plant.verdicts()
        check(near(reading["ForkliftSteerAngleRef"], -0.655, 2e-3),
              f"ForkliftSteerAngleRef = {reading['ForkliftSteerAngleRef']:.4f} rad — the "
              f"joystick's X at -0.50 of the declared engineering range")
        plant.state["ForkliftLinearSpeed"] = 0.58
        await asyncio.sleep(0.6)
        panel_now = panel(args.hmi)
        check(near(panel_now.get("ForkliftTractionSpeedRef"), 0.60, 2e-3)
              and near(panel_now.get("ForkliftLinearSpeed"), 0.58, 2e-3),
              f"the metrics panel shows the reference beside the measurement — ref "
              f"{panel_now.get('ForkliftTractionSpeedRef'):.3f} m/s, measured "
              f"{panel_now.get('ForkliftLinearSpeed'):.3f} m/s")

        # ---- P4: the fork-height speed cap ---------------------------------- #
        head("P4. raising the carriage caps the traction setpoint (process logic in the PLC)")
        plant.state["ForkliftForkHeight"] = 0.90
        capped = await wait_verdict(plant, "ForkliftSpeedLimitActive", True, 8)
        check(bool(capped),
              "ForkliftSpeedLimitActive went TRUE with the carriage above the cap height")
        reading = await plant.verdicts()
        check(reading["ForkliftTractionSpeedRef"] < 0.60,
              f"and the traction setpoint was reduced below what the operator asked for "
              f"— {reading['ForkliftTractionSpeedRef']:.3f} m/s against a request that "
              f"still reads 0.60")
        lamp = await panel_shows(args.hmi, "ForkliftSpeedLimitActive", True)
        height = await panel_shows(args.hmi, "ForkliftForkHeight", 0.90)
        check(lamp is True and height is not None,
              f"the HMI's speed-limit lamp is on and the height reads {height} m")

        # ---- P5: the obstacle latch ----------------------------------------- #
        head("P5. an obstacle in the stop field latches a PROCESS stop over a live command")
        plant.state["ForkliftObstacleInStopZone"] = True
        latched = await wait_verdict(plant, "ForkliftObstacleStopActive", True, 8)
        check(bool(latched), "ForkliftObstacleStopActive latched")
        reading = await plant.verdicts()
        check(reading["ForkliftTeleopActive"] is False,
              "ForkliftTeleopActive dropped in the same call")
        check(near(reading["ForkliftTractionSpeedRef"], 0.0)
              and near(reading["ForkliftSteerAngleRef"], 0.0)
              and near(reading["ForkliftForkSpeedRef"], 0.0),
              f"all three setpoints went to 0.0, the steer angle included — "
              f"{reading['ForkliftTractionSpeedRef']}, "
              f"{reading['ForkliftSteerAngleRef']}, {reading['ForkliftForkSpeedRef']}")
        requests = get_state(args.hmi)["requests"]
        check(near(requests["HmiTractionRequest"], 0.60),
              f"while the operator's request is STILL STANDING at "
              f"{requests['HmiTractionRequest']} — the latch overrides a live command, "
              f"which is the whole point of the request/outcome split")
        check(reading["ForkliftResetRequired"] is True,
              "and ForkliftResetRequired is TRUE again")
        check(await panel_shows(args.hmi, "ForkliftObstacleStopActive", True) is True,
              "the HMI's large stop banner is up, driven by the node")

        # ---- P6: the field clears, the latch does not ----------------------- #
        head("P6. the field clearing does not release the latch; this machine does not "
             "resume by itself")
        plant.state["ForkliftObstacleInStopZone"] = False
        await asyncio.sleep(1.0)
        reading = await plant.verdicts()
        check(reading["ForkliftObstacleStopActive"] is True,
              f"the field is clear and the latch is still standing — "
              f"{reading['ForkliftObstacleStopActive']}")

        # ---- P7: the release-and-reassert conflation ------------------------ #
        head("P7. §10.7's conflation: an enable held through the reset produces no edge")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=True, reset=True)
        cleared = await wait_verdict(plant, "ForkliftResetRequired", False, 8)
        check(bool(cleared), "the reset cleared the latches with ENABLE still asserted")
        await asyncio.sleep(0.6)
        reading = await plant.verdicts()
        check(reading["ForkliftTeleopActive"] is False,
              f"and teleop did NOT come back: no rising edge, so the machine stays "
              f"stopped — {reading['ForkliftTeleopActive']}")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=False)
        await asyncio.sleep(0.4)
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=True)
        reenabled = await wait_verdict(plant, "ForkliftTeleopActive", True, 8)
        check(bool(reenabled),
              "released and re-asserted, the enable produces a real edge and teleop "
              "returns — release ENABLE, press RESET, assert ENABLE again")

        # ---- P8: the fork jog ------------------------------------------------ #
        head("P8. the fork buttons move the fork setpoint")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=1.0, teleop=True)
        jogging = await until(
            lambda: _nonzero(plant, "ForkliftForkSpeedRef"), 8)
        check(bool(jogging),
              f"ForkliftForkSpeedRef went non-zero while the FORK UP button was held — "
              f"{jogging}")
        post_control(args.hmi, traction=0.0, steer=0.0, fork=0.0, teleop=True)
        await asyncio.sleep(0.6)
        reading = await plant.verdicts()
        check(near(reading["ForkliftForkSpeedRef"], 0.0),
              f"and back to 0.0 on release, which the plant holds against gravity — "
              f"{reading['ForkliftForkSpeedRef']}")

        # ---- P9: the HMI watchdog -------------------------------------------- #
        head("P9. stopping the HMI is a degraded mode with a PLC-owned controlled stop")
        plant.state["ForkliftForkHeight"] = 0.20   # carriage back down, cap released
        await wait_verdict(plant, "ForkliftSpeedLimitActive", False, 8)
        post_control(args.hmi, traction=0.55, steer=0.0, fork=0.0, teleop=True)
        await until(lambda: _ref_reached(plant, "ForkliftTractionSpeedRef", 0.55), 8)
        driving = await plant.verdicts()
        check(driving["ForkliftTeleopActive"] is True
              and driving["ForkliftTractionSpeedRef"] > 0.5,
              f"the machine is being driven when the HMI is stopped — "
              f"ForkliftTractionSpeedRef {driving['ForkliftTractionSpeedRef']:.3f} m/s")
        killed_at = time.monotonic()
        hmi.send_signal(signal.SIGTERM)
        # Await the exit WITHOUT blocking the event loop: a synchronous wait here
        # stalls this harness's own bridge pump, BridgeHeartbeat goes stale too,
        # and the drop stops being attributable to the HMI link alone.
        while hmi.poll() is None and time.monotonic() - killed_at < 20:
            await asyncio.sleep(0.02)
        dropped = await wait_verdict(plant, "HmiLinkOk", False, 5)
        elapsed_ms = round((time.monotonic() - killed_at) * 1000)
        check(bool(dropped),
              f"HmiLinkOk went FALSE {elapsed_ms} ms after the HMI stopped — the "
              f"heartbeat stopped changing and the PLC's stale timer expired")
        reading = await plant.verdicts()
        check(reading["ForkliftTeleopActive"] is False
              and near(reading["ForkliftTractionSpeedRef"], 0.0)
              and near(reading["ForkliftSteerAngleRef"], 0.0)
              and near(reading["ForkliftForkSpeedRef"], 0.0),
              f"teleop dropped and every setpoint went to 0.0 in the PLC's mandatory "
              f"ELSE — {reading['ForkliftTractionSpeedRef']}, "
              f"{reading['ForkliftSteerAngleRef']}, {reading['ForkliftForkSpeedRef']}")
        check(reading["ForkliftResetRequired"] is True,
              "and the loss LATCHED: a returning heartbeat will not by itself restore "
              "teleop")
        standing = await plant.read("ForkliftTractionSpeedRef")
        print(f"        the HMI's last requests are still on the server, retained; the "
              f"machine stopped anyway, because the PLC decided it "
              f"(ForkliftTractionSpeedRef {standing['ForkliftTractionSpeedRef']})")
    finally:
        if hmi.poll() is None:
            hmi.terminate()
            try:
                hmi.wait(timeout=10)
            except subprocess.TimeoutExpired:
                hmi.kill()
        log.close()

    head("Transitions observed on the server, in order")
    for line in plant._transitions:
        print(line)

    plant.stop()
    try:
        await asyncio.wait_for(pump, timeout=3.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pump.cancel()
    await plant.close()
    print(f"\n{'FAILURES: ' + str(len(FAILURES)) if FAILURES else 'no failures'}")
    for failure in FAILURES:
        print(f"  - {failure}")
    print(f"HMI stdout/stderr: {log_path}")
    return 1 if FAILURES else 0


def _connected(base: str) -> bool:
    try:
        return get_state(base)["session"]["state"] == "CONNECTED"
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError):
        return False


async def _ref_reached(plant: PlantAndBridge, name: str, expected: float):
    reading = await plant.verdicts()
    return reading if near(reading[name], expected, 2e-3) else None


async def _nonzero(plant: PlantAndBridge, name: str):
    reading = await plant.verdicts()
    return reading[name] if abs(reading[name]) > 1e-6 else None


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
        description="drive the HMI against the PLC logic double")
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
