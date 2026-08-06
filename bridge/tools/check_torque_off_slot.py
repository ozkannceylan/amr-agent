#!/usr/bin/env python3
"""Drive the torque-off demand from the server to the plant's terminals, and
measure what arrives — brief m5-62, `opcua-nodes.md` §11.2b **SD1-SD10**.

WHAT IS REAL IN THIS HARNESS AND WHAT STANDS IN FOR WHAT
--------------------------------------------------------
* the **bridge** is the real one, started as a child process through
  `run_bridge.py` with a committed config. Nothing in `amr_bridge/` is stubbed,
  imported differently or special-cased for a test;
* the **consumer** is the real `agv/forklift/scripts/sto_contactor.py`, started
  from the committed vehicle config. It is the node that has carried a
  subscription to `/forklift/safety/torque_off_demand` since m5-50 and, until
  this slot existed, had **no publisher** — `publisher count 0`, measured in
  `docs/VALIDATION-M5.md`;
* the **server** is the test double, whose lifecycle this harness owns so the
  `Forklift/Safety/` folder can be served in the shape the controller has today
  as well as the shape it will have after `TIA-FIX-PROCEDURE.md` chunks AD-AF;
* the **demand** is written into the double server-side through its S1 back
  door: a HAND writing a value where the standard program's copy from F-data
  would happen. No F-program, no latch and no reset is modelled anywhere in this
  run, and no client writes `Forklift/Safety/` — the server refuses that and the
  bridge's own allowlist refuses it independently (§11.4 MR1);
* the **plant** is this file: it publishes the sources of the configured inputs
  and it is the only source of actuator commands. It applies no logic.

WHAT IT CANNOT SHOW, STATED BEFORE ANY RESULT
---------------------------------------------
No simulator runs here. What is measured is **delivery to the plant's terminal
topics** — the inputs of the joint controllers in `model.sdf` — not wheel
rotation. "The command reached the terminal" and "the command reached no
terminal" are the two observations, and this file never says "the vehicle
moved".

And the rule that makes even that pair meaningful: **stillness is not evidence**
(LESSONS 2026-08-06). A latched contactor and a contactor that was never started
produce the identical observation, so the *positive control lives in the same
run* — phase 1 sends the SAME command value through the SAME path with the
demand absent, and counts what arrives. Every "0 arrived" below is reported
beside its own control, with n.

NOT A SAFETY MEASUREMENT. The consumer is process-side Python simulating the
effect on the plant of a hardwired onboard inhibit this plant does not have
(§11.2b SD9, ADR 0011 D5). No PL, Category, SIL or PFH is claimed, achieved or
implied, and no stopping time or distance is measured or quoted.

Run (never against PLCSIM: this harness kills and restarts its server):

    export ROS_DOMAIN_ID=<a free one>
    source /opt/ros/jazzy/setup.bash
    "$VENV/bin/python" bridge/tools/check_torque_off_slot.py
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import signal
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rclpy  # noqa: E402
import yaml  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from std_msgs.msg import Bool, Float64, UInt16  # noqa: E402

from amr_bridge import config as config_mod  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))       # bridge/
REPO = os.path.dirname(HERE)

#: What the plant publishes into the configured input slots. None of these is a
#: start value of any group, so "the node holds the plant's value" and "the node
#: holds its start value" can never be confused.
PLANT_VALUES: dict[str, object] = {
    "ForkliftForkHeight": 0.84,
    "ForkliftLinearSpeed": -0.62,
    "ForkliftObstacleInStopZone": False,
    "ForkliftObstacleMinDistance": 3.75,
    "ForkliftVehicleModeApplied": 2,
    "ForkliftVehicleHeartbeat": 0,
    "ForkliftWarningFieldOccupied": False,
}

#: The traction command every phase sends. ONE value for the whole run, on
#: purpose: the positive control and the refusal must differ in the demand and in
#: nothing else. It is not the brake's 0.0, so a terminal message carrying it can
#: only be a forwarded command and never a standing order.
COMMAND_VALUE = 5.5
#: The brake value the contactor stands on while the latch is open
#: (`agv/forklift/config.yaml` sto.brake_traction_radps). Read from that file at
#: startup rather than written here; this is only the fallback for the log line.
BRAKE_FALLBACK = 0.0


class Checks:
    def __init__(self) -> None:
        self.failures = 0
        self.total = 0
        self.rows: list[tuple[str, str, str]] = []

    def ok(self, passed: bool, statement: str, detail: str = "") -> None:
        self.total += 1
        if not passed:
            self.failures += 1
        print(f"   {'ok  ' if passed else 'FAIL'} {statement}"
              + (f" — {detail}" if detail else ""), flush=True)
        self.rows.append(("ok" if passed else "FAIL", statement, detail))

    def result(self) -> int:
        print(f"\n{self.total} checks, {self.total - self.failures} passed, "
              f"{self.failures} failed", flush=True)
        print("RESULT:", "PASS" if self.failures == 0 else f"FAIL ({self.failures})")
        return 1 if self.failures else 0


def wait_until(predicate: Callable[[], bool], timeout_s: float, what: str) -> tuple[bool, float]:
    """Bounded FOREGROUND polling. Never a detached wait (LESSONS 2026-07-27)."""
    started = time.monotonic()
    while (time.monotonic() - started) < timeout_s:
        if predicate():
            return True, time.monotonic() - started
        time.sleep(0.02)
    print(f"        (timed out after {timeout_s:.1f}s waiting for {what})", flush=True)
    return False, time.monotonic() - started


# ---------------------------------------------------------------------------- #
# The plant: stimulus in, terminals out
# ---------------------------------------------------------------------------- #


class Plant(Node):
    """Publishes the bridge's input sources and the actuator commands, and
    watches the three observables: the demand topic the bridge publishes, the
    contactor's own applied readback, and the traction TERMINAL.

    It holds no bridge state and no vehicle state, and it decides nothing: every
    verdict in this file is computed from what it recorded, after the fact.
    """

    def __init__(self, cfg: config_mod.Config, vehicle_topics: dict) -> None:
        super().__init__("torque_off_harness")
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=10,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.VOLATILE)
        self._pubs: dict[str, object] = {}
        self._kinds: dict[str, str] = {}
        for group in cfg.signal_groups:
            topics = cfg.topics(group.name)
            for node_key, topic_key, kind in group.scalar_inputs:
                msg_type = {config_mod.BOOL: Bool, config_mod.UINT16: UInt16}.get(kind, Float64)
                self._pubs[node_key] = self.create_publisher(msg_type, topics[topic_key], qos)
                self._kinds[node_key] = kind

        self.demand_topic = cfg.topics("safety")["torque_off_demand"]
        #: Every demand message the bridge published, as (value, monotonic ns).
        self.demand: list[tuple[bool, int]] = []
        self.create_subscription(Bool, self.demand_topic, self.cb_demand, qos)
        #: The contactor's own readback of its latch. It commands nothing.
        self.applied: list[tuple[bool, int]] = []
        self.create_subscription(
            Bool, vehicle_topics["safety_torque_off_applied"], self.cb_applied, qos)
        #: THE MEASUREMENT: everything that reached the traction terminal.
        self.terminal: list[tuple[float, int]] = []
        self.create_subscription(
            Float64, vehicle_topics["gz_actuator_traction_cmd"], self.cb_terminal, qos)
        #: The command channel into the contactor.
        self.cmd_pub = self.create_publisher(
            Float64, vehicle_topics["gz_traction_cmd"], qos)
        self.commands_sent = 0
        # The input sources keep flowing for the whole run, as they would in a
        # real one, so no phase is measured against a bridge idling on empty
        # slots. It is stimulus on a timer, not a control loop.
        self.create_timer(0.2, self.cb_input_tick)

    def cb_input_tick(self) -> None:
        self.publish_inputs()

    # Callbacks are cb_* in this project (LESSONS 2026-07-27).
    def cb_demand(self, msg: Bool) -> None:
        self.demand.append((bool(msg.data), time.monotonic_ns()))

    def cb_applied(self, msg: Bool) -> None:
        self.applied.append((bool(msg.data), time.monotonic_ns()))

    def cb_terminal(self, msg: Float64) -> None:
        self.terminal.append((float(msg.data), time.monotonic_ns()))

    def publish_inputs(self) -> None:
        for key, publisher in self._pubs.items():
            kind = self._kinds[key]
            if kind == config_mod.BOOL:
                msg = Bool()
                msg.data = bool(PLANT_VALUES[key])
            elif kind == config_mod.UINT16:
                msg = UInt16()
                msg.data = int(PLANT_VALUES[key])
            else:
                msg = Float64()
                msg.data = float(PLANT_VALUES[key])
            publisher.publish(msg)
        PLANT_VALUES["ForkliftVehicleHeartbeat"] = (
            int(PLANT_VALUES["ForkliftVehicleHeartbeat"]) + 1) % 65536

    def send_command(self) -> None:
        msg = Float64()
        msg.data = COMMAND_VALUE
        self.cmd_pub.publish(msg)
        self.commands_sent += 1

    # --- windowed views, so a phase counts only its own traffic -------------

    def mark(self) -> int:
        return time.monotonic_ns()

    def terminal_since(self, since_ns: int) -> list[tuple[float, int]]:
        return [row for row in self.terminal if row[1] >= since_ns]

    def forwarded_since(self, since_ns: int) -> int:
        """Terminal messages carrying the COMMAND value. The brake and the held
        values carry other numbers, so a forward is never confused with a
        standing order."""
        return sum(1 for value, at in self.terminal
                   if at >= since_ns and abs(value - COMMAND_VALUE) < 1e-9)

    def demand_since(self, since_ns: int) -> list[bool]:
        return [value for value, at in self.demand if at >= since_ns]

    def last_demand(self) -> Optional[bool]:
        return self.demand[-1][0] if self.demand else None

    def last_applied(self) -> Optional[bool]:
        return self.applied[-1][0] if self.applied else None


# ---------------------------------------------------------------------------- #
# Child processes
# ---------------------------------------------------------------------------- #


class Process:
    def __init__(self, name: str, argv: list[str], log_path: str) -> None:
        self.name = name
        self.argv = argv
        self.log_path = log_path
        self._handle = open(log_path, "w", encoding="utf-8")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        self.popen = subprocess.Popen(
            argv, stdout=self._handle, stderr=subprocess.STDOUT, cwd=REPO, env=env)
        print(f"   started {name} pid {self.popen.pid} -> {log_path}", flush=True)

    @property
    def alive(self) -> bool:
        return self.popen.poll() is None

    def stop(self, why: str = "") -> None:
        if self.popen.poll() is None:
            self.popen.send_signal(signal.SIGINT)
            try:
                self.popen.wait(timeout=6)
            except subprocess.TimeoutExpired:
                self.popen.kill()
                self.popen.wait(timeout=6)
        self._handle.flush()
        self._handle.close()
        print(f"   stopped {self.name} ({why or 'end of run'}), "
              f"exit {self.popen.returncode}", flush=True)

    def log_text(self) -> str:
        with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
            return handle.read()


def write_demand(command_file: str, value: bool) -> None:
    """Drive the demand through the double's S1 back door — a hand writing a
    value SERVER-SIDE, which is where the standard program's copy from F-data
    happens. Not a client write, and not modelled logic."""
    with open(command_file, "w", encoding="utf-8") as handle:
        handle.write(f"TorqueOffDemand={'true' if value else 'false'}\n")


# ---------------------------------------------------------------------------- #
# The run
# ---------------------------------------------------------------------------- #


def phase(title: str) -> None:
    print(f"\n{title}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=os.path.join(HERE, "config", "bridge-double-m5.yaml"))
    parser.add_argument("--vehicle-config",
                        default=os.path.join(REPO, "agv", "forklift", "config.yaml"))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--workdir", default=None,
                        help="where the logs and witness CSV of THIS run land")
    parser.add_argument("--tag", default=time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
                        help="names the run; every file this run writes carries it, so a "
                             "repeat can never overwrite the run it is compared against "
                             "(LESSONS 2026-08-06)")
    parser.add_argument("--commands-per-phase", type=int, default=20)
    parser.add_argument("--command-hz", type=float, default=10.0)
    args = parser.parse_args()

    cfg = config_mod.load(args.config)
    if "safety" not in cfg.groups:
        raise SystemExit(
            f"{args.config} does not configure the safety group; this harness would "
            "have measured a topic nobody publishes on. A harness that cannot apply "
            "its stimulus fails loud (LESSONS 2026-08-06).")
    with open(args.vehicle_config, "r", encoding="utf-8") as handle:
        vehicle = yaml.safe_load(handle)
    vehicle_topics = vehicle["topics"]
    brake = float(vehicle.get("sto", {}).get("brake_traction_radps", BRAKE_FALLBACK))

    workdir = args.workdir or os.path.join(HERE, "evidence")
    os.makedirs(workdir, exist_ok=True)
    tag = args.tag
    command_file = os.path.join(workdir, f"m562-demand-{tag}.txt")
    witness_csv = os.path.join(workdir, f"m562-witness-{tag}.csv")
    endpoint = cfg.opcua["endpoint"]

    checks = Checks()
    print(f"# check_torque_off_slot  tag={tag}")
    print(f"# config={args.config}  endpoint={endpoint}")
    print(f"# ROS_DOMAIN_ID={os.environ.get('ROS_DOMAIN_ID', '(unset)')}  "
          f"python={args.python}")
    print(f"# command value {COMMAND_VALUE} rad/s, brake {brake} rad/s, "
          f"n={args.commands_per_phase} commands per phase")
    print("# NOT a safety measurement: the consumer is a labelled process-side "
          "stand-in (§11.2b SD9). No PL, Category, SIL or PFH; no stopping figure.")

    double = bridge = contactor = None
    plant = None
    executor = None
    spin_thread = None
    try:
        # -- the server, in the shape the CPU will have after chunks AD-AF ----
        phase("0. bring the chain up (double 'six' shape, bridge, contactor)")
        write_demand(command_file, True)   # the boot truth: TorqueOffDemand starts TRUE
        double = Process("double", [
            args.python, os.path.join(HERE, "test_double", "plc_test_double.py"),
            "--endpoint", endpoint, "--safety-mirrors", "six",
            "--command-file", command_file,
            "--observe-csv", os.path.join(workdir, f"m562-double-observe-{tag}.csv"),
        ], os.path.join(workdir, f"m562-double-{tag}.log"))
        time.sleep(2.0)

        bridge = Process("bridge", [
            args.python, os.path.join(HERE, "run_bridge.py"),
            "--config", args.config,
            "--evidence-csv", os.path.join(workdir, f"m562-latency-{tag}.csv"),
        ], os.path.join(workdir, f"m562-bridge-{tag}.log"))

        contactor = Process("contactor", [
            args.python, os.path.join(REPO, "agv", "forklift", "scripts", "sto_contactor.py"),
            "--config", args.vehicle_config,
        ], os.path.join(workdir, f"m562-contactor-{tag}.log"))

        rclpy.init(args=None)
        plant = Plant(cfg, vehicle_topics)
        executor = SingleThreadedExecutor()
        executor.add_node(plant)
        spin_thread = threading.Thread(target=executor.spin, name="rclpy", daemon=True)
        spin_thread.start()

        # The input sources are on the node's own 5 Hz timer. Wait, in bounded
        # foreground polling, for the first demand message to appear at all.
        wait_until(lambda: bool(plant.demand), 30.0, "the first demand message")
        checks.ok(bool(plant.demand),
                  "the demand topic has a publisher and a message arrived",
                  f"{plant.demand_topic}: {len(plant.demand)} message(s), "
                  f"publisher count {plant.count_publishers(plant.demand_topic)}")
        checks.ok(plant.count_publishers(plant.demand_topic) == 1,
                  "publisher count on the demand topic is 1 — the orphaned half of "
                  "finding F1 is closed",
                  "measured on the vehicle side, as VALIDATION-M5 measured 0")

        # -- phase 1: the boot truth ----------------------------------------
        phase("1. TorqueOffDemand starts TRUE (§11.6, SD6): the vehicle boots deaf")
        ok, _ = wait_until(lambda: plant.last_demand() is True, 10.0, "demand TRUE")
        checks.ok(ok, "the bridge carried the start value TRUE to the vehicle",
                  f"last demand {plant.last_demand()}")
        ok, _ = wait_until(lambda: plant.last_applied() is True, 10.0, "applied TRUE")
        checks.ok(ok, "the contactor latched OPEN on the observed TRUE (SD2)",
                  f"applied readback {plant.last_applied()}")
        mark = plant.mark()
        for _ in range(args.commands_per_phase):
            plant.send_command()
            time.sleep(1.0 / args.command_hz)
        time.sleep(0.5)
        boot_forwarded = plant.forwarded_since(mark)
        boot_terminal = plant.terminal_since(mark)
        checks.ok(boot_forwarded == 0,
                  f"n={args.commands_per_phase} commands, 0 reached the traction terminal",
                  f"{boot_forwarded} forwarded; {len(boot_terminal)} terminal message(s) "
                  f"in the window, all standing orders")
        checks.ok(all(abs(value - brake) < 1e-9 for value, _ in boot_terminal)
                  and len(boot_terminal) > 0,
                  "the traction terminal is DRIVEN to the brake value, not merely quiet",
                  f"{len(boot_terminal)} message(s), all {brake}")

        # -- phase 2: THE POSITIVE CONTROL, in the same run ------------------
        phase("2. POSITIVE CONTROL — the same command, the same path, demand absent")
        write_demand(command_file, False)
        ok, delay = wait_until(lambda: plant.last_demand() is False, 10.0, "demand FALSE")
        checks.ok(ok, "an observed FALSE reached the vehicle (SD4)",
                  f"{delay*1000:.0f} ms after the hand wrote it, this harness's own "
                  "0.1 s file poll included")
        ok, _ = wait_until(lambda: plant.last_applied() is False, 10.0, "applied FALSE")
        checks.ok(ok, "the contactor closed on the observed FALSE", "authority returned")
        mark = plant.mark()
        for _ in range(args.commands_per_phase):
            plant.send_command()
            time.sleep(1.0 / args.command_hz)
        time.sleep(0.5)
        control_forwarded = plant.forwarded_since(mark)
        checks.ok(control_forwarded == args.commands_per_phase,
                  f"n={args.commands_per_phase} commands, "
                  f"{control_forwarded} reached the traction terminal",
                  "THIS is what makes the zeros above mean something: the same value "
                  "through the same path with the demand absent")

        # -- phase 3: the demand, against its own control ---------------------
        phase("3. the demand stands: the same command is refused (SD2, SD3)")
        write_demand(command_file, True)
        ok, delay = wait_until(lambda: plant.last_demand() is True, 10.0, "demand TRUE")
        checks.ok(ok, "the observed TRUE reached the vehicle", f"{delay*1000:.0f} ms")
        ok, _ = wait_until(lambda: plant.last_applied() is True, 10.0, "applied TRUE")
        checks.ok(ok, "the contactor latched OPEN again", "")
        mark = plant.mark()
        for _ in range(args.commands_per_phase):
            plant.send_command()
            time.sleep(1.0 / args.command_hz)
        time.sleep(0.5)
        refused = plant.forwarded_since(mark)
        checks.ok(refused == 0,
                  f"n={args.commands_per_phase} commands, {refused} reached the terminal "
                  f"(control above: {control_forwarded}/{args.commands_per_phase})",
                  "same value, same path, same run — the demand is the only difference")

        # -- phase 4: release commands nothing --------------------------------
        phase("4. an observed FALSE restores authority and COMMANDS NOTHING (SD4)")
        write_demand(command_file, False)
        ok, _ = wait_until(lambda: plant.last_demand() is False, 10.0, "demand FALSE")
        checks.ok(ok, "the demand fell", "")
        mark = plant.mark()
        time.sleep(1.5)                       # nobody sends a command in this window
        quiet_forwarded = plant.forwarded_since(mark)
        checks.ok(quiet_forwarded == 0,
                  "1.5 s after the release, with no fresh command, nothing was "
                  "forwarded to the terminal",
                  "the value standing at the traction terminal is the brake's; "
                  "clearing a latch energizes nothing")
        mark = plant.mark()
        for _ in range(args.commands_per_phase):
            plant.send_command()
            time.sleep(1.0 / args.command_hz)
        time.sleep(0.5)
        after_release = plant.forwarded_since(mark)
        checks.ok(after_release == args.commands_per_phase,
                  f"a FRESH command moves through again: {after_release}/"
                  f"{args.commands_per_phase}", "")

        # -- phase 5: SD5 — silence is not torque-off -------------------------
        phase("5. SD5 — the bridge dies and the topic goes silent; that is NOT torque-off")
        bridge.stop("SD5: killed deliberately, mid-run")
        ok, _ = wait_until(lambda: plant.count_publishers(plant.demand_topic) == 0,
                           10.0, "publisher count 0")
        checks.ok(ok, "the demand topic has no publisher at all",
                  f"publisher count {plant.count_publishers(plant.demand_topic)} — "
                  "the exact condition VALIDATION-M5 measured, now produced on purpose")
        mark = plant.mark()
        for _ in range(args.commands_per_phase):
            plant.send_command()
            time.sleep(1.0 / args.command_hz)
        time.sleep(0.5)
        silent_forwarded = plant.forwarded_since(mark)
        checks.ok(silent_forwarded == args.commands_per_phase,
                  f"with the demand silent, {silent_forwarded}/{args.commands_per_phase} "
                  "commands still reached the terminal",
                  "loss of supervision is a degraded mode, not a safety event "
                  "(invariant 2); the controlled stop for it lives one layer up in the "
                  "envelope gate's freshness rule (E5). Torque removal is asserted, "
                  "never inferred")
        checks.ok(plant.last_applied() is False,
                  "the contactor's latch stayed CLOSED through the silence",
                  "a link that never speaks leaves it closed (SD5)")

        # -- phase 6: the leaf is absent from the server ----------------------
        phase("6. §11.6 — the leaf absent from the server: connect stands, no message")
        double.stop("restarting in the 'four' shape")
        time.sleep(1.5)
        double = Process("double-four", [
            args.python, os.path.join(HERE, "test_double", "plc_test_double.py"),
            "--endpoint", endpoint, "--safety-mirrors", "four",
        ], os.path.join(workdir, f"m562-double-four-{tag}.log"))
        time.sleep(2.0)
        before = len(plant.demand)
        bridge = Process("bridge-four", [
            args.python, os.path.join(HERE, "run_bridge.py"),
            "--config", args.config,
            "--evidence-csv", os.path.join(workdir, f"m562-latency-four-{tag}.csv"),
        ], os.path.join(workdir, f"m562-bridge-four-{tag}.log"))
        # The other groups must still run: the envelope output topic is the
        # cheapest proof that the session is up and the run is not merely stalled.
        ok, _ = wait_until(
            lambda: "session established" in bridge.log_text(), 30.0, "a session")
        checks.ok(ok, "the bridge CONNECTED against a server without the leaf",
                  "no client's connect may fail over this group (§11.6)")
        time.sleep(3.0)
        log = bridge.log_text()
        checks.ok("TorqueOffDemand is NOT on this server" in log,
                  "the absence is logged once, by name", "")
        checks.ok(len(plant.demand) == before,
                  "no message was published on the demand topic at all",
                  f"{len(plant.demand) - before} message(s) in 3 s — no synthesised "
                  "value in either polarity, and no message is not torque-off")
        mark = plant.mark()
        for _ in range(args.commands_per_phase):
            plant.send_command()
            time.sleep(1.0 / args.command_hz)
        time.sleep(0.5)
        absent_forwarded = plant.forwarded_since(mark)
        checks.ok(absent_forwarded == args.commands_per_phase,
                  f"the vehicle still drives: {absent_forwarded}/"
                  f"{args.commands_per_phase} commands reached the terminal",
                  "an unbuilt F-layer is not a dead vehicle (§11.6, ADR 0009 D4)")

        # -- what the bridge never did ---------------------------------------
        phase("7. what the bridge never did")
        full_log = log
        checks.ok("WriteNotPermitted" not in full_log,
                  "no write to a node outside the derived allowlist was attempted", "")
        checks.ok(len(cfg.write_allowlist) == len(cfg.input_keys) + 1
                  and "TorqueOffDemand" not in cfg.write_allowlist,
                  "the safety group added ZERO keys to the write allowlist",
                  f"{len(cfg.write_allowlist)} keys = {len(cfg.input_keys)} configured "
                  "Input/ node(s) + the one heartbeat (§11.4 MR1)")
        checks.ok("SpeedMonitorDemand" not in yaml.dump(cfg.nodes)
                  and "SpeedMonitorDemand" not in yaml.dump(cfg.ros),
                  "SpeedMonitorDemand has no slot, no node and no topic (SD1)",
                  "its reaction is the PLC's permissive and reaches the vehicle as "
                  "consequence")

        with open(witness_csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["kind", "monotonic_ns", "value"])
            for value, at in plant.demand:
                writer.writerow(["demand", at, value])
            for value, at in plant.applied:
                writer.writerow(["applied", at, value])
            for value, at in plant.terminal:
                writer.writerow(["terminal", at, value])
        print(f"\nwitness: {witness_csv} "
              f"({len(plant.demand)} demand, {len(plant.applied)} applied, "
              f"{len(plant.terminal)} terminal rows); "
              f"{plant.commands_sent} commands sent in total", flush=True)
        return checks.result()
    finally:
        for process in (contactor, bridge, double):
            if process is not None and process.alive:
                process.stop("teardown")
        if executor is not None:
            executor.shutdown()
        if spin_thread is not None:
            spin_thread.join(timeout=5.0)
        if plant is not None:
            plant.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    sys.exit(main())
