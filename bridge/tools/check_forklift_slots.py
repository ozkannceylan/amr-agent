#!/usr/bin/env python3
"""Check that the bridge carries the forklift signal group, both ways, against
the test double — brief m4f-06, `bridge-design.md` §2.1, §4.7–§4.10, §6.1, §8.1.

What it drives, and what stands in for what:

* the **bridge** is the real one, started as a child process through
  `run_bridge.py` with a committed config. Nothing in `amr_bridge/` is stubbed,
  imported differently or special-cased for a test;
* the **server** is the test double, whose lifecycle this harness owns so it can
  be warm-restarted on cue (`bridge-design.md` §10);
* the **plant** is this file: a ROS 2 node publishing the sources of every
  configured input and subscribing to every command topic. It is stimulus, in
  the standing of `tools/cell_stimulus.py` — it publishes exactly what the
  Gazebo cell and the vehicle layer publish, on the topic names
  `opcua-nodes.md` §10.10 fixes, and it applies no logic to any signal;
* the **PLC's setpoints** are hand-written through the double's S1 back door.
  A human writing a number, not PLC logic.

The four claims it establishes, each printed as its own check:

  A. every input slot of the configured set carries a ROS value into its node —
     the four forklift slots included, and the field bit **uninverted** in both
     directions (§4.7 row 12);
  B. every output slot republishes node changes to its ROS topic — the
     conveyor's plus the three `Forklift/Output/*Ref` (§4.8), all in one cycle
     phase;
  C. a server restart under a surviving session rewrites **every configured
     input**, with the count taken from the bridge's own log line and from its
     evidence file, not from this harness's arithmetic (§8.1, LESSONS
     2026-07-27 on quoting counts);
  D. R3 counts the **configured** set: a forklift-only run reaches its heartbeat
     on four inputs, having subscribed to no `/cell/*` topic at all (§6.1) — and
     across the whole run the six nodes of §4.10 never move on the server.

Run it against the test double only, never against PLCSIM: it kills and restarts
its server, and an owner session may be live on the commissioned endpoint.

    export ROS_DOMAIN_ID=<a free one>
    source /opt/ros/jazzy/setup.bash
    "$VENV/bin/python" bridge/tools/check_forklift_slots.py
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import re
import signal
import subprocess
import sys
import threading
import time
from typing import Callable, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import rclpy  # noqa: E402
from asyncua import Client  # noqa: E402
from rclpy.executors import SingleThreadedExecutor  # noqa: E402
from rclpy.node import Node  # noqa: E402
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy  # noqa: E402
from sensor_msgs.msg import JointState, LaserScan  # noqa: E402
from std_msgs.msg import Bool, Float64  # noqa: E402

from amr_bridge import config as config_mod  # noqa: E402

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: What the plant publishes, per input node. Values are chosen to be unmistakable
#: on a read-back — none of them is a start value of either group (§6.3, §10.9),
#: so "the node holds the plant's value" and "the node holds its start value"
#: can never be confused.
PLANT_VALUES: dict[str, object] = {
    "ConveyorBeltPosition": 1.25,
    "ConveyorBeltSpeed": 0.35,
    "ProductSensorRange": 0.42,
    "PanelStartPressed": False,
    "PanelResetPressed": False,
    "PanelStopCircuitClosed": True,
    "PanelProcessStopCircuitClosed": True,
    "ForkliftForkHeight": 0.84,
    "ForkliftLinearSpeed": -0.62,
    # FALSE = no object in the stop field. The DB start value is TRUE (§10.9),
    # so publishing FALSE makes the restart test sharp: a reverted server holds
    # the non-permissive TRUE, and write-on-change would never repair it.
    "ForkliftObstacleInStopZone": False,
    "ForkliftObstacleMinDistance": 3.75,
}

#: Second values, for the "both ways" half of claim A.
PLANT_VALUES_B: dict[str, object] = {
    "ForkliftForkHeight": 0.11,
    "ForkliftLinearSpeed": 1.37,
    "ForkliftObstacleInStopZone": True,
    "ForkliftObstacleMinDistance": 0.05,
}

#: Setpoints written by hand into the double's `Output/` nodes (S1), and the
#: topic each must reach. Two rounds, so a stale republish cannot pass for a
#: fresh one.
SETPOINTS_A = {
    "ConveyorSpeedCommand": 0.15,
    "ForkliftTractionSpeedRef": 0.55,
    "ForkliftSteerAngleRef": -0.90,
    "ForkliftForkSpeedRef": 0.12,
}
SETPOINTS_B = {
    "ConveyorSpeedCommand": -0.05,
    "ForkliftTractionSpeedRef": -0.25,
    "ForkliftSteerAngleRef": 1.05,
    # 0.0 means HOLD, and the bridge translates it into nothing: it publishes
    # 0.0 (§4.8 row 16).
    "ForkliftForkSpeedRef": 0.0,
}

#: The six nodes of §4.10. Served by the double, writable, and never to be
#: touched by the bridge in either direction.
HMI_GROUP_START = {
    "HmiTractionRequest": 0.0,
    "HmiSteerRequest": 0.0,
    "HmiForkRequest": 0.0,
    "HmiTeleopRequest": False,
    "HmiResetRequest": False,
    "HmiHeartbeat": 0,
}


class Checks:
    def __init__(self) -> None:
        self.failures = 0
        self.total = 0

    def ok(self, passed: bool, statement: str, detail: str = "") -> None:
        self.total += 1
        if passed:
            print(f"   ok   {statement}" + (f" — {detail}" if detail else ""), flush=True)
        else:
            self.failures += 1
            print(f"   FAIL {statement}" + (f" — {detail}" if detail else ""), flush=True)

    def result(self) -> int:
        print(f"\n{self.total} checks, {self.total - self.failures} passed, "
              f"{self.failures} failed", flush=True)
        print("RESULT:", "PASS" if self.failures == 0 else f"FAIL ({self.failures})")
        return 1 if self.failures else 0


async def await_until(predicate: Callable[[], bool], timeout_s: float, what: str) -> tuple[bool, float]:
    """Bounded foreground polling. Never a detached wait (LESSONS 2026-07-27)."""
    started = time.monotonic()
    while (time.monotonic() - started) < timeout_s:
        if predicate():
            return True, time.monotonic() - started
        await asyncio.sleep(0.05)
    print(f"        (timed out after {timeout_s:.1f}s waiting for {what})", flush=True)
    return False, time.monotonic() - started


# ---------------------------------------------------------------------------- #
# The plant: a ROS 2 node publishing what Gazebo and the vehicle layer publish
# ---------------------------------------------------------------------------- #


class Plant(Node):
    """Stimulus, not part of the bridge and not part of either plant.

    It publishes the sources of the configured inputs on the topic names of
    `opcua-nodes.md` §9.9 and §10.10, and records what arrives on the command
    topics. It holds no bridge state, writes no OPC UA node and applies no logic
    to any value it publishes or receives.
    """

    def __init__(self, cfg: config_mod.Config) -> None:
        super().__init__("plant_stimulus")
        self._cfg = cfg
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.VOLATILE)
        self.values = dict(PLANT_VALUES)
        #: topic key -> (value, monotonic ns) of the last command received.
        self.received: dict[str, tuple[float, int]] = {}
        self._pubs: dict[str, object] = {}
        self._joint_pub = None
        self._scan_pub = None

        for group in cfg.signal_groups:
            topics = cfg.topics(group.name)
            if group.name == "cell":
                self._joint_pub = self.create_publisher(JointState, topics["joint_state"], qos)
                self._scan_pub = self.create_publisher(LaserScan, topics["product_scan"], qos)
            for node_key, topic_key, _kind in group.scalar_inputs:
                self._pubs[node_key] = self.create_publisher(
                    Bool if isinstance(self.values[node_key], bool) else Float64,
                    topics[topic_key], qos)
            for node_key, topic_key, kind in group.outputs:
                # `SignalGroup.outputs` carries (node key, topic key, kind)
                # since the envelope group (config.py, 1842c42): a group may
                # publish a `UInt16` output and this plant subscribes `Float64`
                # only. Both configurations this harness loads are REAL-only, so
                # rather than widen the plant silently, refuse a kind it cannot
                # represent — a harness that cannot apply its stimulus fails
                # loud instead of testing nothing (LESSONS 2026-08-06).
                if kind != config_mod.REAL:
                    raise SystemExit(
                        f"check_forklift_slots: output slot {node_key} is of kind "
                        f"{kind!r}; this harness subscribes std_msgs/Float64 only and "
                        "would have measured a topic nobody publishes on. Extend the "
                        "plant before configuring a non-Real output into it.")
                self.create_subscription(
                    Float64, topics[topic_key],
                    lambda msg, key=topic_key: self.cb_command(key, msg), qos)

    def cb_command(self, topic_key: str, msg: Float64) -> None:
        self.received[topic_key] = (float(msg.data), time.monotonic_ns())

    def publish_once(self) -> None:
        """One sample of every configured source. 10 Hz, the rate both plants
        publish at; the bridge's cycle is 20 Hz, so nothing is decimated."""
        if self._joint_pub is not None:
            msg = JointState()
            msg.name = [self._cfg.ros["joint_name"]]
            msg.position = [float(self.values["ConveyorBeltPosition"])]
            msg.velocity = [float(self.values["ConveyorBeltSpeed"])]
            self._joint_pub.publish(msg)
        if self._scan_pub is not None:
            scan = LaserScan()
            scan.ranges = [float(self.values["ProductSensorRange"])]
            self._scan_pub.publish(scan)
        for node_key, publisher in self._pubs.items():
            value = self.values[node_key]
            if isinstance(value, bool):
                msg = Bool()
                msg.data = bool(value)
            else:
                msg = Float64()
                msg.data = float(value)
            publisher.publish(msg)


class PlantRunner:
    """The plant node plus its executor thread and its 10 Hz publish loop."""

    def __init__(self, cfg: config_mod.Config) -> None:
        self.node = Plant(cfg)
        self._executor = SingleThreadedExecutor()
        self._executor.add_node(self.node)
        self._thread = threading.Thread(target=self._executor.spin, daemon=True)
        self._stop = threading.Event()
        self._pump = threading.Thread(target=self._loop, daemon=True)

    def _loop(self) -> None:
        while not self._stop.is_set():
            self.node.publish_once()
            time.sleep(0.1)

    def start(self) -> None:
        self._thread.start()
        self._pump.start()

    def stop(self) -> None:
        self._stop.set()
        self._pump.join(timeout=2.0)
        self._executor.shutdown()
        self.node.destroy_node()


# ---------------------------------------------------------------------------- #
# The double and the bridge, as child processes
# ---------------------------------------------------------------------------- #


class Double:
    def __init__(self, python: str, script: str, endpoint: str, workdir: str) -> None:
        self._python = python
        self._script = script
        self.endpoint = endpoint
        self.workdir = workdir
        self.warm_restart_file = os.path.join(workdir, "warm_restart_trigger")
        self.command_file = os.path.join(workdir, "setpoints")
        self.observe_stem = os.path.join(workdir, "double-observe.csv")
        self._log_path = os.path.join(workdir, "double.log")
        self._proc: Optional[subprocess.Popen] = None
        self.starts = 0

    async def start(self) -> None:
        self.starts += 1
        for path in (self.command_file, self.warm_restart_file):
            if os.path.exists(path):
                os.remove(path)
        log = open(self._log_path, "a", encoding="utf-8")
        log.write(f"\n===== double start {self.starts} at {time.strftime('%H:%M:%S')} =====\n")
        log.flush()
        self._proc = subprocess.Popen(
            [self._python, self._script,
             "--endpoint", self.endpoint,
             "--observe-csv", self.observe_stem,
             "--command-file", self.command_file,
             "--warm-restart-file", self.warm_restart_file],
            stdout=log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            if await _endpoint_reachable(self.endpoint):
                return
            await asyncio.sleep(0.2)
        raise TimeoutError(f"the double never came up on {self.endpoint}")

    def set_setpoints(self, values: dict[str, float]) -> None:
        """S1 scaffolding: a human writing setpoints into the PLC's output nodes."""
        with open(self.command_file, "w", encoding="utf-8") as handle:
            handle.write("\n".join(f"{name}={value}" for name, value in values.items()) + "\n")

    def warm_restart(self) -> None:
        with open(self.warm_restart_file, "w", encoding="utf-8") as handle:
            handle.write("1\n")

    async def stop(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.send_signal(signal.SIGINT)
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=5)
        self._proc = None

    def observe_files(self) -> list[str]:
        stem, ext = os.path.splitext(self.observe_stem)
        directory = os.path.dirname(stem) or "."
        return [os.path.join(directory, name) for name in sorted(os.listdir(directory))
                if name.startswith(os.path.basename(stem)) and name.endswith(ext)]

    def observe_rows(self, latest_only: bool = False) -> list[dict]:
        rows: list[dict] = []
        for path in (self.observe_files()[-1:] if latest_only else self.observe_files()):
            with open(path, newline="", encoding="utf-8") as handle:
                rows.extend(csv.DictReader(handle))
        return rows


class Bridge:
    """The real bridge process. Its log is this harness's primary instrument:
    every count quoted below is read out of it (LESSONS 2026-07-27)."""

    def __init__(self, python: str, config_path: str, workdir: str, name: str) -> None:
        self._python = python
        self.config_path = config_path
        self.name = name
        self.log_path = os.path.join(workdir, f"bridge-{name}.log")
        self.evidence_stem = os.path.join(workdir, f"latency-{name}.csv")
        self._proc: Optional[subprocess.Popen] = None
        self.returncode: Optional[int] = None

    def start(self) -> None:
        log = open(self.log_path, "w", encoding="utf-8")
        env = dict(os.environ, PYTHONUNBUFFERED="1")
        self._proc = subprocess.Popen(
            [self._python, os.path.join(HERE, "run_bridge.py"),
             "--config", self.config_path,
             "--evidence-csv", self.evidence_stem],
            stdout=log, stderr=subprocess.STDOUT, env=env)

    def stop(self) -> None:
        if self._proc is not None:
            if self._proc.poll() is None:
                self._proc.send_signal(signal.SIGINT)
                try:
                    self._proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self._proc.kill()
                    self._proc.wait(timeout=5)
            self.returncode = self._proc.returncode
        self._proc = None

    @property
    def alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def log(self) -> str:
        try:
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as handle:
                return handle.read()
        except FileNotFoundError:
            return ""

    def log_line(self, pattern: str) -> Optional[str]:
        """The last log line matching a pattern, or None."""
        found = [line for line in self.log().splitlines() if re.search(pattern, line)]
        return found[-1] if found else None

    def log_count(self, pattern: str) -> int:
        return sum(1 for line in self.log().splitlines() if re.search(pattern, line))

    def evidence_files(self) -> list[str]:
        stem, ext = os.path.splitext(self.evidence_stem)
        directory = os.path.dirname(stem) or "."
        return [os.path.join(directory, name) for name in sorted(os.listdir(directory))
                if name.startswith(os.path.basename(stem)) and name.endswith(ext)]

    def evidence_rows(self, event: str, name: str = "") -> list[dict]:
        rows: list[dict] = []
        for path in self.evidence_files():
            with open(path, newline="", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row["event"] == event and (not name or row["name"] == name):
                        rows.append(row)
        return rows


async def _endpoint_reachable(endpoint: str) -> bool:
    client = Client(url=endpoint, timeout=2)
    try:
        await client.connect()
    except Exception:
        return False
    try:
        await client.disconnect()
    except Exception:
        pass
    return True


class ServerView:
    """An INDEPENDENT read-only session on the double: what the server holds,
    rather than anything the bridge's session is carrying. Paths come from the
    bridge's own addressing helper, so none is duplicated here."""

    def __init__(self, cfg: config_mod.Config) -> None:
        self._cfg = cfg
        self._client: Optional[Client] = None
        self._indices: dict[str, int] = {}

    async def __aenter__(self) -> "ServerView":
        self._client = Client(url=self._cfg.opcua["endpoint"], timeout=4)
        await self._client.connect()
        self._indices = {key: await self._client.get_namespace_index(uri)
                         for key, uri in self._cfg.namespace_uris.items()}
        return self

    async def __aexit__(self, *exc) -> None:
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass

    async def read(self, key: str) -> object:
        path = [f"{self._indices[ns]}:{name}" for ns, name in self._cfg.browse_path(key)]
        node = await self._client.nodes.objects.get_child(path)
        return await node.read_value()

    async def read_inputs(self) -> dict[str, object]:
        values = {key: await self.read(key) for key in self._cfg.input_keys}
        values[config_mod.HEARTBEAT_KEY] = await self.read(config_mod.HEARTBEAT_KEY)
        return values

    async def read_relative(self, *elements: str) -> object:
        """Read a node by its path under the interface node, for nodes that are
        deliberately in no configuration: the six of §4.10, and the cell group
        during a forklift-only run. This harness is the only place in the
        repository that addresses them."""
        assert self._client is not None
        path = [f"{self._indices[ns]}:{name}" for ns, name in self._cfg.interface_path]
        path += [f"{self._indices[config_mod.NS_INTERFACE]}:{name}" for name in elements]
        node = await self._client.nodes.objects.get_child(path)
        return await node.read_value()


def _same(got: object, want: object) -> bool:
    if isinstance(want, bool) or isinstance(got, bool):
        return bool(got) == bool(want)
    return got is not None and abs(float(got) - float(want)) < 1e-5


def _image_diff(values: dict[str, object], expected: dict[str, object]) -> str:
    return "; ".join(f"{key}={values.get(key)!r} (wanted {want!r})"
                     for key, want in expected.items() if not _same(values.get(key), want))


# ---------------------------------------------------------------------------- #
# Phase A — both groups configured
# ---------------------------------------------------------------------------- #


async def phase_both(checks: Checks, args, workdir: str) -> None:
    cfg = config_mod.load(args.config_both)
    endpoint = cfg.opcua["endpoint"]
    print(f"\n=== PHASE A — both groups, {os.path.basename(cfg.path)} ===", flush=True)
    print(f"    {cfg.describe()}", flush=True)

    double = Double(args.python, args.double, endpoint, workdir)
    bridge = Bridge(args.python, cfg.path, workdir, "both")
    plant = PlantRunner(cfg)
    try:
        await double.start()
        plant.start()
        bridge.start()
        print(f"    bridge log {bridge.log_path}", flush=True)

        async with ServerView(cfg) as server:
            # ---------------------------------------------------------------- #
            print("\nA0. startup — R3 counts the configured set (§6.1)", flush=True)
            started, waited = await await_until(
                lambda: bridge.log_line(r"startup rule R3 satisfied") is not None, 60.0,
                "the heartbeat to start")
            line = bridge.log_line(r"startup rule R3 satisfied")
            checks.ok(started and line is not None,
                      "the heartbeat begins only once every configured input has carried "
                      "a real sample", f"after {waited:.1f}s")
            if line:
                print(f"        {line.strip()}", flush=True)
                counted = re.search(r"all (\d+) input nodes of the configured set \(([^)]+)\)", line)
                checks.ok(
                    counted is not None and int(counted.group(1)) == len(cfg.input_keys),
                    "the count in the bridge's own log is the configured set's, not a literal",
                    f"log says {counted.group(1)} input nodes for {counted.group(2)}"
                    if counted else "no count in the line")
            described = bridge.log_line(r"configured signal set:")
            checks.ok(described is not None and "27 nodes touched" in (described or ""),
                      "the run states its configured set at startup (§2.1 G3)",
                      described.split("configured signal set:")[-1].strip() if described else "")

            # ---------------------------------------------------------------- #
            print("\nA. every configured input slot carries a ROS value into its node "
                  "(§4.1, §4.7)", flush=True)
            await asyncio.sleep(0.6)          # a dozen cycles
            values = await server.read_inputs()
            diff = _image_diff(values, PLANT_VALUES)
            checks.ok(not diff,
                      f"an independent read-only session sees all {len(cfg.input_keys)} "
                      "published values on their nodes",
                      diff or f"BridgeHeartbeat={values[config_mod.HEARTBEAT_KEY]}")
            for key in ("ForkliftForkHeight", "ForkliftLinearSpeed",
                        "ForkliftObstacleMinDistance", "ForkliftObstacleInStopZone"):
                checks.ok(_same(values[key], PLANT_VALUES[key]),
                          f"{key} carried unchanged", f"{values[key]!r}")

            print("\nA'. the same slots carry a SECOND value, and the field bit both "
                  "ways, uninverted (§4.7 row 12)", flush=True)
            plant.node.values.update(PLANT_VALUES_B)
            await asyncio.sleep(1.0)
            values = await server.read_inputs()
            for key, want in PLANT_VALUES_B.items():
                checks.ok(_same(values[key], want),
                          f"{key} followed the plant to its second value",
                          f"{values[key]!r} (was {PLANT_VALUES[key]!r})")
            checks.ok(_same(values["ForkliftObstacleInStopZone"], True),
                      "publishing TRUE on /forklift/obstacle/in_stop_zone writes TRUE — "
                      "the non-permissive polarity is NOT inverted in transport",
                      f"{values['ForkliftObstacleInStopZone']!r}")
            # Back to FALSE, so the restart test below is a real repair.
            plant.node.values.update(PLANT_VALUES)
            await asyncio.sleep(1.0)
            values = await server.read_inputs()
            checks.ok(_same(values["ForkliftObstacleInStopZone"], False),
                      "and publishing FALSE writes FALSE again — a level, not an edge",
                      f"{values['ForkliftObstacleInStopZone']!r}")

            # ---------------------------------------------------------------- #
            print("\nB. every output slot republishes node changes to its ROS topic "
                  "(§4.2, §4.8)", flush=True)
            for round_name, setpoints in (("first", SETPOINTS_A), ("second", SETPOINTS_B)):
                plant.node.received.clear()
                double.set_setpoints(setpoints)
                topics = cfg.output_topic_keys
                delivered, waited = await await_until(
                    lambda: all(
                        topic in plant.node.received
                        and _same(plant.node.received[topic][0], setpoints[key])
                        for key, topic in topics.items()),
                    15.0, f"the {round_name} setpoints to reach their topics")
                for key, topic in topics.items():
                    got = plant.node.received.get(topic)
                    checks.ok(got is not None and _same(got[0], setpoints[key]),
                              f"{key} -> {cfg.topics(cfg.group_of(key))[topic]} = "
                              f"{setpoints[key]} ({round_name} round)",
                              f"received {got[0]!r}" if got else "nothing received")
                if delivered:
                    spread = (max(v[1] for v in plant.node.received.values())
                              - min(v[1] for v in plant.node.received.values())) / 1e6
                    print(f"        all four arrived within {spread:.1f} ms of each other "
                          f"({waited:.1f}s after the setpoints were written)", flush=True)

            # ---------------------------------------------------------------- #
            if args.soak > 0:
                print(f"\n    steady state: {args.soak:.0f} s at 20 Hz with all "
                      f"{len(cfg.input_keys)} slots live, so the figures below rest on a "
                      "run rather than on a handful of cycles", flush=True)
                await asyncio.sleep(args.soak)

            # ---------------------------------------------------------------- #
            print("\nC. a server restart under a surviving session rewrites EVERY "
                  "configured input (§8.1, §7.3 case E)", flush=True)
            before_restart = await server.read_inputs()
            checks.ok(not _image_diff(before_restart, PLANT_VALUES),
                      "before the restart the server holds the plant's values",
                      _image_diff(before_restart, PLANT_VALUES))
            reconnects_before = len(bridge.evidence_rows("session", "broken"))

            # The witness has a residual window this run MEASURES rather than
            # assumes. The bridge compares the heartbeat it reads at step 0 with
            # the value it wrote at step 4 of the previous cycle; a revert that
            # lands BETWEEN those two operations is erased by the bridge's own
            # step-4 write, so the next read-back compares equal and the revert
            # is invisible — while the level signals, which write-on-change does
            # not repeat, stay at their start values. Observed in this very run
            # on 2026-07-29 (see the report). So a revert is triggered until one
            # is caught, and the number of masked ones is reported: a single
            # trigger would make this check a coin toss and would hide the
            # property instead of stating it.
            restart_pattern = r"the server restarted under a live session"
            rewrite_pattern = r"input image rewritten after cache invalidation"
            masked = 0
            detected = False
            latency = 0.0
            triggered_ns = time.monotonic_ns()
            for attempt in range(1, int(args.restart_attempts) + 1):
                seen_restarts = bridge.log_count(restart_pattern)
                seen_rewrites = bridge.log_count(rewrite_pattern)
                triggered_ns = time.monotonic_ns()
                double.warm_restart()
                print(f"        S5 warm restart {attempt}: every node back to its start "
                      "value in place, sessions left up", flush=True)
                detected, latency = await await_until(
                    lambda: bridge.log_count(restart_pattern) > seen_restarts, 3.0,
                    "the heartbeat read-back to notice the revert")
                if detected:
                    await await_until(
                        lambda: bridge.log_count(rewrite_pattern) > seen_rewrites, 3.0,
                        "the input image to be rewritten")
                    break
                masked += 1
                print("        that revert was masked by the bridge's own heartbeat write "
                      "in the same cycle; triggering another", flush=True)
                await asyncio.sleep(1.0)
            checks.ok(detected, "the bridge detected the restart from its own heartbeat "
                                "reading back a value it did not write",
                      f"{latency * 1000:.0f} ms after trigger {attempt}; {masked} earlier "
                      f"revert(s) masked (§8.1 restart residual — larger than the design's "
                      f"one-in-65536; see the m4f-06 report)")
            line = bridge.log_line(rewrite_pattern)
            checks.ok(detected and line is not None, "the write cache was invalidated and the "
                                                     "image rewritten in one cycle")
            if line:
                print(f"        {line.strip()}", flush=True)
                counted = re.search(r"(\d+) of (\d+) configured input nodes", line)
                checks.ok(
                    counted is not None
                    and counted.group(1) == counted.group(2) == str(len(cfg.input_keys)),
                    "the count in the log is every input of the configured set",
                    f"log says {counted.group(1)} of {counted.group(2)}"
                    if counted else "no count in the line")
            full = f"{len(cfg.input_keys)}/{len(cfg.input_keys)}"
            flushed, _ = await await_until(
                lambda: any(row["value"] == full
                            for row in bridge.evidence_rows("session", "input_image_rewritten")),
                10.0, "the evidence file to be flushed")
            rows = [row for row in bridge.evidence_rows("session", "input_image_rewritten")
                    if row["value"] == full]
            checks.ok(flushed and bool(rows),
                      f"the rewrite is in the bridge's evidence file as {full}",
                      rows[-1]["note"] if rows else "no such row")
            # The first row of a session is the connect-time invalidation, which
            # writes whatever the slots already hold — 0 of 11 when the bridge
            # reaches the server before the plant's first sample. It is R1 doing
            # its job, and it is why the row checked above is matched by value.
            print("        input_image_rewritten rows in the evidence file: "
                  + ", ".join(row["value"] for row in
                              bridge.evidence_rows("session", "input_image_rewritten")),
                  flush=True)
            checks.ok(len(bridge.evidence_rows("session", "broken")) == reconnects_before,
                      "no session was lost, so nothing but the read-back could have "
                      "noticed (§7.3 case E)",
                      f"{len(bridge.evidence_rows('session', 'broken'))} broken-session row(s)")
            after = await server.read_inputs()
            diff = _image_diff(after, PLANT_VALUES)
            checks.ok(not diff,
                      "an independent session sees the whole image repaired — the two stop "
                      "circuits and the forklift field bit included",
                      diff or f"repaired {(time.monotonic_ns() - triggered_ns) / 1e6:.0f} ms "
                              "after the trigger")

            # ---------------------------------------------------------------- #
            print("\nD1. the six nodes of §4.10 never moved on the server", flush=True)
            for name, start in HMI_GROUP_START.items():
                value = await server.read_relative(
                    "Forklift", "Link" if name == "HmiHeartbeat" else "Hmi", name)
                checks.ok(_same(value, start),
                          f"Forklift/{'Link' if name == 'HmiHeartbeat' else 'Hmi'}/{name} "
                          "still holds its start value", f"{value!r}")
            log = bridge.log()
            leaked = [name for name in HMI_GROUP_START if name in log]
            checks.ok(not leaked,
                      "not one of the six appears anywhere in the bridge's log — not "
                      "written, not read, not logged (§4.10)",
                      f"leaked: {leaked}" if leaked else "none of "
                      + ", ".join(HMI_GROUP_START))
            checks.ok("HmiLinkOk" in log,
                      "while HmiLinkOk IS logged: the PLC's verdict on the other client is "
                      "a diagnostic the bridge may read, and the distinction is visible "
                      "in the log")
    finally:
        bridge.stop()
        plant.stop()
        await double.stop()
    checks.ok(bridge.returncode == 0,
              "the bridge ran to the end of the phase and stopped cleanly on SIGINT — no "
              "farewell value, nothing zeroed (§7.3 B)",
              f"exit status {bridge.returncode}")
    summarise(bridge, cfg, "PHASE A")


# ---------------------------------------------------------------------------- #
# Phase B — the forklift group alone
# ---------------------------------------------------------------------------- #


def summarise(bridge: Bridge, cfg: config_mod.Config, title: str) -> None:
    """Figures out of the finished evidence file — the run's own numbers, as the
    recorder wrote them. Nothing here is computed twice or rounded into a
    claim: medians of the rows that exist, and the counters the bridge kept."""
    print(f"\n{title} figures, from {', '.join(os.path.basename(f) for f in bridge.evidence_files())}",
          flush=True)

    def median_ms(event: str, name: str = "") -> str:
        values = sorted(int(row["interval_ns"]) for row in bridge.evidence_rows(event, name)
                        if row["interval_ns"])
        if not values:
            return "-"
        return f"{values[len(values) // 2] / 1e6:.2f} ms (n={len(values)})"

    print(f"        cycle interval R1            {median_ms('R1', 'cycle')}", flush=True)
    print(f"        heartbeat read-back RB       {median_ms('read_rt', config_mod.HEARTBEAT_KEY)}",
          flush=True)
    print("        per input slot — L2 write round trip:", flush=True)
    for key in cfg.input_keys:
        print(f"          {key:<30} {median_ms('L2', key)}", flush=True)
    print("        per output slot — L5 read-response to publish:", flush=True)
    for key, topic in cfg.output_topic_keys.items():
        print(f"          {key:<30} {median_ms('L5', topic)}", flush=True)
    r3 = {row["name"]: row["value"] for row in bridge.evidence_rows("R3")}
    if r3:
        print("        R3 samples received/written per slot: "
              + ", ".join(f"{key} {value}" for key, value in r3.items()), flush=True)
    counters = {row["name"]: row["value"] for row in bridge.evidence_rows("counter")}
    kept = {key: value for key, value in counters.items() if value not in ("0", "")}
    if kept:
        print("        counters: " + ", ".join(f"{key}={value}" for key, value in kept.items()),
              flush=True)


async def phase_forklift_only(checks: Checks, args, workdir: str) -> None:
    cfg = config_mod.load(args.config_forklift)
    endpoint = cfg.opcua["endpoint"]
    print(f"\n=== PHASE B — forklift only, {os.path.basename(cfg.path)} ===", flush=True)
    print(f"    {cfg.describe()}", flush=True)

    double = Double(args.python, args.double, endpoint, workdir)
    bridge = Bridge(args.python, cfg.path, workdir, "forklift-only")
    plant = PlantRunner(cfg)          # publishes the four forklift topics and no other
    try:
        await double.start()
        plant.start()
        bridge.start()
        async with ServerView(cfg) as server:
            started, waited = await await_until(
                lambda: bridge.log_line(r"startup rule R3 satisfied") is not None, 60.0,
                "the heartbeat to start on four inputs")
            line = bridge.log_line(r"startup rule R3 satisfied")
            checks.ok(started, "a forklift-only run reaches its heartbeat with no /cell/* "
                               "topic published at all", f"after {waited:.1f}s")
            if line:
                print(f"        {line.strip()}", flush=True)
                counted = re.search(r"all (\d+) input nodes of the configured set \(([^)]+)\)", line)
                checks.ok(counted is not None and counted.group(1) == "4"
                          and counted.group(2) == "forklift",
                          "R3 counted FOUR inputs — the configured set, not the seven of "
                          "the cell group (§6.1)",
                          f"log says {counted.group(1)} for {counted.group(2)}"
                          if counted else "no count")
            described = bridge.log_line(r"configured signal set:")
            checks.ok(described is not None and "13 nodes touched" in (described or "")
                      and "write allowlist 5 keys" in (described or ""),
                      "13 nodes touched and a 5-key allowlist — §2.1's forklift-only row, "
                      "the shared heartbeat included",
                      described.split("—")[-1].strip() if described else "")
            resolved = bridge.log_line(r"session established, \d+ nodes resolved")
            checks.ok(resolved is not None and " 13 nodes resolved" in (resolved or ""),
                      "and the session resolved exactly those 13",
                      resolved.strip() if resolved else "")

            await asyncio.sleep(1.0)
            values = await server.read_inputs()
            diff = _image_diff(values, {key: PLANT_VALUES[key] for key in cfg.input_keys})
            checks.ok(not diff, "the four forklift nodes carry the plant's values", diff)

            # G1 — the cell group contributes nothing: this double started fresh,
            # so its cell inputs must still hold their start values.
            untouched = True
            details = []
            for name, start in (("ConveyorBeltPosition", 0.0), ("ConveyorBeltSpeed", 0.0),
                                ("ProductSensorRange", 0.0), ("PanelStopCircuitClosed", False),
                                ("PanelProcessStopCircuitClosed", False)):
                value = await server.read_relative("Input", name)
                details.append(f"{name}={value!r}")
                untouched = untouched and _same(value, start)
            checks.ok(untouched,
                      "every DemoCell/Input/ node still holds its start value: a group "
                      "absent from the config contributes nothing (§2.1 G1)",
                      ", ".join(details))
            described = bridge.log_line(r"configured signal set:") or ""
            checks.ok("cell" not in described.split("—")[0],
                      "the cell group is named nowhere in this run's configured set",
                      described.split("configured signal set:")[-1].split("—")[0].strip())

            if args.soak > 0:
                print(f"\n    steady state: {args.soak / 2:.0f} s at 20 Hz on the four "
                      "forklift slots", flush=True)
                await asyncio.sleep(args.soak / 2)
    finally:
        bridge.stop()
        plant.stop()
        await double.stop()

    summarise(bridge, cfg, "PHASE B")

    print("\nE. per-session evidence naming (§9.4, LESSONS 2026-07-28)", flush=True)
    files = bridge.evidence_files()
    checks.ok(len(files) == 1 and os.path.basename(files[0]) != os.path.basename(bridge.evidence_stem),
              "the --evidence-csv argument is a stem; the file written names the session",
              os.path.basename(files[0]) if files else "no file")


# ---------------------------------------------------------------------------- #


async def run(args: argparse.Namespace) -> int:
    # The bridge child reads the config FILE, so the endpoint under test is the
    # one written there and cannot be overridden from here. Both files name the
    # double, on two ports, so the second phase never waits on the first port.
    endpoints = [config_mod.load(path).opcua["endpoint"]
                 for path in (args.config_both, args.config_forklift)]
    if any(endpoint.startswith("opc.tcp://192.168.") for endpoint in endpoints):
        print("refusing to run against what looks like the commissioned PLCSIM endpoint; "
              "this harness restarts its server (bridge-design.md §10)")
        return 2
    os.makedirs(args.workdir, exist_ok=True)
    checks = Checks()
    print("bridge forklift signal group — brief m4f-06")
    print(f"  endpoints {', '.join(endpoints)}  (TEST DOUBLE, started by this harness)")
    print(f"  workdir  {args.workdir}")
    print(f"  ROS_DOMAIN_ID={os.environ.get('ROS_DOMAIN_ID', '(unset)')}")

    rclpy.init(args=None)
    try:
        await phase_both(checks, args, args.workdir)
        await phase_forklift_only(checks, args, args.workdir)
    finally:
        rclpy.shutdown()
    return checks.result()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="check that the bridge carries the forklift signal group both ways")
    parser.add_argument("--config-both",
                        default=os.path.join(HERE, "config", "bridge-double-both.yaml"))
    parser.add_argument("--config-forklift",
                        default=os.path.join(HERE, "config", "bridge-double-forklift.yaml"))
    parser.add_argument("--workdir", default="/tmp/amr-forklift-slots")
    parser.add_argument("--soak", type=float, default=20.0,
                        help="seconds of steady 20 Hz operation with every configured slot "
                             "live, between the output checks and the restart check")
    parser.add_argument("--restart-attempts", type=int, default=8,
                        help="how many reverts to trigger before giving up on catching one. "
                             "A revert that lands between the cycle's read-back and its own "
                             "heartbeat write is masked by that write, so the number of "
                             "masked ones is a measurement, not a flake")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--double",
                        default=os.path.join(HERE, "test_double", "plc_test_double.py"))
    return asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
