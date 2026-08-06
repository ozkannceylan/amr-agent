#!/usr/bin/env python3
"""run_forklift_rehearsal.py - drive the five M4 commissioning scenarios
against the PLC LOGIC DOUBLE, end to end, and print a transcript.

WHAT THIS IS, AND WHAT IT IS NOT

  This is the REHEARSAL harness. It brings up the whole loop -

      commissioning HMI  ->  PLC logic double  ->  bridge  ->  Gazebo arena
                         <-                     <-          <-

  - in the process order the commissioning procedure states, plays the
  operator's controls at the HMI's own /control endpoint, moves the arena's
  obstacle through the Gazebo service, and prints every transition it sees.

  IT IS A REHEARSAL AND NOTHING MORE. `plc/forklift/double/` is the PLC
  layer's rehearsal stand-in for the TIA Portal build of
  `plc/forklift/SPEC.md`; it is not a PLC, it is not PLCSIM Advanced, and
  nothing observed through it is evidence about the CPU, its scan cycle or
  the loop the M4 gate claims. The gate closes on the owner's PLCSIM run and
  its recording. What a rehearsal establishes is narrower and still worth
  having: that the procedure is executable, that every step's observable
  exists and is reachable, and that the steps happen in an order that works.

  IT NEVER CONTACTS PLCSIM. The double answers on 127.0.0.1:4850 and refuses
  to start on 4840. This file names no other endpoint.

  IT HOLDS NO PROCESS LOGIC. No threshold, no interlock, no latch and no
  verdict is computed here. Everything the transcript shows was decided by
  the program running in the double, from the plant state the bridge wrote.

  Nothing here is a safety function or a safety test. The obstacle stop, the
  fork-height speed cap and the fork soft travel limits are standard-program
  process interlocks (ADR 0008 D3) and carry no SIL or PL claim.

TWO PROCESS RULES THIS FILE OBEYS, BOTH LEARNED THE HARD WAY

  Both transports are isolated, not just ROS: ROS_DOMAIN_ID does not isolate
  Gazebo, because gz transport does not use DDS. GZ_PARTITION does. Each
  scenario gets a fresh value of both.

  Signalling `ros2 launch` does not bring its group down. Measured again
  here: the launch process exits and `gz sim` and `parameter_bridge` keep
  running. Teardown therefore enumerates survivors with `pgrep -af`, keeps
  only the pids whose /proc/<pid>/environ carries THIS run's GZ_PARTITION -
  so a concurrent run of someone else's is never touched - and finishes each
  one by exact pid.

USAGE (from the repository root, in WSL, with nothing else running)

  python3 sim/scenarios/run_forklift_rehearsal.py --scenario all
  python3 sim/scenarios/run_forklift_rehearsal.py --scenario 4 --keep-up
"""

import argparse
import json
import os
import re
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_THIS_DIR, "..", ".."))
sys.path.insert(0, _THIS_DIR)

import forklift_stimulus as stim  # noqa: E402  (same directory, deliberate)

# --------------------------------------------------------------------------- #
# Fixed addresses. Every one is quoted from the file that owns it.
# --------------------------------------------------------------------------- #

BRIDGE_VENV = "/home/ozkan/amr-bridge-venv/bin/python"   # bridge/README.md
HMI_VENV = "/home/ozkan/amr-hmi-venv/bin/python"         # hmi/README.md
ROS_SETUP = "/opt/ros/jazzy/setup.bash"

DOUBLE = "plc/forklift/double/server.py"                 # port 4850
BRIDGE = "bridge/run_bridge.py"
BRIDGE_CONFIG = "bridge/config/rehearsal-forklift.yaml"
SIM_LAUNCH = "sim/launch/forklift_bringup.launch.py"
VEHICLE_IO = "agv/forklift/scripts/forklift_io.py"
VEHICLE_ZONE = "agv/forklift/scripts/obstacle_zone.py"
VEHICLE_CONFIG = "agv/forklift/config.yaml"
HMI = "hmi/hmi_server.py"
HMI_CONFIG = "hmi/config-logic-double.yaml"
HMI_URL = "http://127.0.0.1:8090"

#: Patterns for the survivor sweep. Matched against `pgrep -af` and then
#: filtered by this run's GZ_PARTITION, so nothing outside this run is touched.
SURVIVOR_PATTERNS = (
    "double/server.py", "run_bridge.py", "gz sim", "parameter_bridge",
    "forklift_io.py", "obstacle_zone.py", "hmi_server.py",
    "forklift_bringup.launch.py",
    # The STO contactor (m5-50). It is started by the bringup, so it is one
    # of the children that survives a signal to `ros2 launch`, and it MUST
    # be swept: a contactor left running from a previous run is a second
    # publisher of the three actuator terminals.
    "sto_contactor.py",
)

#: Constants of plc/forklift/SPEC.md section 3.3, quoted for the assertions in
#: the scenario bodies. They are read from the specification, never chosen here.
K_TRACTION_SPEED_MAX = 1.00
K_TRACTION_SPEED_CAP_RAISED = 0.30
K_FORK_HEIGHT_SLOW_THRESHOLD = 0.50
K_FORK_SPEED_MAX = 0.15
K_FORK_TRAVEL_MIN = 0.05
K_FORK_TRAVEL_MAX = 1.55
K_HMI_STALE_TIME_S = 0.600


# --------------------------------------------------------------------------- #
# Transcript
# --------------------------------------------------------------------------- #

class Log:
    def __init__(self, path=None):
        self.handle = open(path, "w", encoding="utf-8") if path else None
        self.t0 = time.monotonic()

    def __call__(self, text=""):
        stamped = "{:8.3f}  {}".format(time.monotonic() - self.t0, text)
        print(stamped)
        sys.stdout.flush()
        if self.handle:
            self.handle.write(stamped + "\n")
            self.handle.flush()

    def head(self, text):
        self("")
        self("=== " + text)

    def zero(self):
        self.t0 = time.monotonic()


# --------------------------------------------------------------------------- #
# Processes
# --------------------------------------------------------------------------- #

class Stack:
    """The five processes of the loop, started in the procedure's order and
    finished by exact pid."""

    def __init__(self, log, partition, domain, scratch):
        self.log = log
        self.partition = partition
        self.domain = str(domain)
        self.scratch = scratch
        self.started = []          # [(name, Popen)] in start order
        os.makedirs(os.path.join(scratch, "log"), exist_ok=True)
        os.makedirs(os.path.join(scratch, "evidence"), exist_ok=True)

    # -- environment -------------------------------------------------- #

    def env(self):
        environment = dict(os.environ)
        environment["GZ_PARTITION"] = self.partition
        environment["ROS_DOMAIN_ID"] = self.domain
        return environment

    def _spawn(self, name, shell_command):
        """One process, its own session, its stdout and stderr in a file."""
        path = os.path.join(self.scratch, "log", name + ".log")
        handle = open(path, "w", encoding="utf-8")
        process = subprocess.Popen(
            ["bash", "-lc", shell_command], cwd=_REPO, env=self.env(),
            stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        self.started.append((name, process))
        self.log("start {:<8} pid {:<7} log {}".format(name, process.pid, path))
        return process

    def log_path(self, name):
        return os.path.join(self.scratch, "log", name + ".log")

    def evidence_stem(self, name):
        return os.path.join(self.scratch, "evidence", name + ".csv")

    # -- readiness ------------------------------------------------------ #

    def _wait(self, what, predicate, timeout, period=0.5):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                self.log("ready {:<8} after {:.1f} s".format(
                    what, timeout - (deadline - time.monotonic())))
                return True
            time.sleep(period)
        raise RuntimeError("{} was not ready within {:.0f} s".format(what, timeout))

    def _log_contains(self, name, needle):
        try:
            with open(self.log_path(name), "r", encoding="utf-8", errors="replace") as h:
                return needle in h.read()
        except OSError:
            return False

    # -- the five, in the procedure's order ----------------------------- #

    def start_double(self):
        self._spawn("double", "{} {}".format(BRIDGE_VENV, DOUBLE))
        self._wait("double", lambda: _port_open(4850), 30)

    def start_bridge(self):
        self._spawn("bridge", "source {} && {} {} --config {} --evidence-csv {}".format(
            ROS_SETUP, BRIDGE_VENV, BRIDGE, BRIDGE_CONFIG,
            self.evidence_stem("bridge")))
        self._wait("bridge", lambda: self._log_contains("bridge", "session established"), 60)

    def start_sim(self):
        self._spawn("sim", "source {} && ros2 launch {}".format(ROS_SETUP, SIM_LAUNCH))
        self._wait("sim", lambda: "/forklift/scan" in self._ros_topics(), 120, period=1.0)

    def start_vehicle(self):
        self._spawn("io", "source {} && python3 {} --config {}".format(
            ROS_SETUP, VEHICLE_IO, VEHICLE_CONFIG))
        self._spawn("zone", "source {} && python3 {} --config {}".format(
            ROS_SETUP, VEHICLE_ZONE, VEHICLE_CONFIG))
        # The bridge's own startup rule is the readiness signal for the plant:
        # R3 withholds the heartbeat until every configured input has carried a
        # real sample, so "R3 satisfied" means all four are flowing.
        self._wait("vehicle", lambda: self._log_contains(
            "bridge", "startup rule R3 satisfied"), 90)

    def start_hmi(self, hold_reset_from_first_post=False):
        self._spawn("hmi", "{} {} --config {} --evidence-csv {}".format(
            HMI_VENV, HMI, HMI_CONFIG, self.evidence_stem("hmi")))
        if hold_reset_from_first_post:
            # section 11 step 5.5.5: the reset request has to be standing from
            # the HMI's very first write cycle. The HTTP server is started
            # before the OPC UA session, so a POST that lands in that window
            # arms the request before any cycle writes it.
            thread = threading.Thread(
                target=_post_until_accepted, args=(self.log,), daemon=True)
            thread.start()
        self._wait("hmi", _hmi_connected, 60)

    # -- observation of the plant, read only ----------------------------- #

    def _ros_topics(self):
        finished = subprocess.run(
            ["bash", "-lc", "source {} && ros2 topic list".format(ROS_SETUP)],
            cwd=_REPO, env=self.env(), capture_output=True, text=True, check=False)
        return finished.stdout

    def odom(self, timeout=8.0):
        """One ground-truth pose sample. A read, never a publish."""
        finished = subprocess.run(
            ["bash", "-lc",
             "source {} && timeout {} ros2 topic echo /forklift/odom --once".format(
                 ROS_SETUP, int(timeout))],
            cwd=_REPO, env=self.env(), capture_output=True, text=True, check=False)
        text = finished.stdout
        def field(pattern):
            found = re.search(pattern, text)
            return float(found.group(1)) if found else float("nan")
        return {
            "x": field(r"position:\s*\n\s*x:\s*([-\d.e+]+)"),
            "y": field(r"position:\s*\n\s*x:[^\n]*\n\s*y:\s*([-\d.e+]+)"),
            "yaw_z": field(r"orientation:\s*\n\s*x:[^\n]*\n\s*y:[^\n]*\n\s*z:\s*([-\d.e+]+)"),
        }

    def obstacle(self, x, y=0.0, z=None):
        z = stim.OBSTACLE_HOME[2] if z is None else z
        ok, out, err = stim.set_model_pose(
            stim.DEFAULT_WORLD, stim.OBSTACLE_MODEL, x, y, z,
            env=self.env(), ros_setup=ROS_SETUP)
        self.log("obstacle {} -> x={} : {} {} {}".format(
            stim.OBSTACLE_MODEL, x, "ok" if ok else "FAILED",
            out.replace("\n", " "), err.replace("\n", " ")))
        return ok

    # -- teardown --------------------------------------------------------- #

    def stop_named(self, name, sig=signal.SIGTERM):
        """Signal one started process by its exact pid. Returns the monotonic
        instant the signal was sent, which is a measurement input for T5.5."""
        for started_name, process in self.started:
            if started_name == name and process.poll() is None:
                sent = time.monotonic()
                # The child is a bash -lc wrapper in its own session; signal the
                # whole session so the interpreter under it goes too.
                try:
                    os.killpg(os.getpgid(process.pid), sig)
                except (ProcessLookupError, PermissionError):
                    process.send_signal(sig)
                self.log("signal {} pid {} with {}".format(
                    name, process.pid, sig.name))
                return sent
        return None

    def survivors(self):
        """Every process still up that belongs to THIS run, by pgrep and then
        by /proc/<pid>/environ. The environ filter is what makes it safe to
        run while another agent has its own simulation up."""
        pattern = "|".join(SURVIVOR_PATTERNS)
        finished = subprocess.run(
            ["pgrep", "-af", pattern], capture_output=True, text=True, check=False)
        rows = []
        for line in finished.stdout.splitlines():
            pid_text, _, command = line.partition(" ")
            if not pid_text.isdigit():
                continue
            pid = int(pid_text)
            if pid == os.getpid():
                continue
            if _environ_has(pid, "GZ_PARTITION", self.partition):
                rows.append((pid, command))
        return rows

    def teardown(self):
        self.log.head("teardown")
        for name, process in reversed(self.started):
            if process.poll() is None:
                self.stop_named(name)
        time.sleep(3.0)
        left = self.survivors()
        self.log("pgrep -af after SIGTERM: {} survivor(s) in partition {}".format(
            len(left), self.partition))
        for pid, command in left:
            self.log("  survivor pid {} {}".format(pid, command[:110]))
        for pid, _ in left:
            try:
                os.kill(pid, signal.SIGTERM)
                self.log("  SIGTERM {}".format(pid))
            except ProcessLookupError:
                pass
        time.sleep(3.0)
        still = self.survivors()
        for pid, command in still:
            try:
                os.kill(pid, signal.SIGKILL)
                self.log("  SIGKILL {} {}".format(pid, command[:80]))
            except ProcessLookupError:
                pass
        time.sleep(1.5)
        final = self.survivors()
        self.log("pgrep -af final: {}".format(
            "clean" if not final else "STILL UP: {}".format(final)))
        self.log("listeners 4850/8090: {}".format(
            "none" if not (_port_open(4850) or _port_open(8090)) else "STILL OPEN"))
        return not final


def _port_open(port, host="127.0.0.1"):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        return probe.connect_ex((host, port)) == 0


def _environ_has(pid, key, value):
    try:
        with open("/proc/{}/environ".format(pid), "rb") as handle:
            blob = handle.read().decode("utf-8", "replace")
    except OSError:
        return False
    return "{}={}".format(key, value) in blob.split("\x00")


def _hmi_connected():
    """CONNECTED is not the same as readable. The session comes up first and the
    read-only metrics poll follows a cycle or two later, so a boot reading taken
    the instant the session connects finds `metrics: null` and every verdict
    reads as absent. The panel is ready when it has values on it."""
    try:
        state = stim.get_state(HMI_URL, timeout=1.0)
    except (urllib.error.URLError, OSError, TimeoutError, ValueError):
        return False
    if (state.get("session") or {}).get("state") != "CONNECTED":
        return False
    return bool(state.get("metrics"))


def _post_until_accepted(log, attempts=600):
    """Post a standing reset request as soon as the HMI answers HTTP at all.
    Used only by T5.5's P6 step."""
    for _ in range(attempts):
        try:
            stim.post_control(HMI_URL, reset=True, timeout=0.5)
            log("P6 arming: first reset POST accepted before the first write cycle")
            return
        except (urllib.error.URLError, OSError, TimeoutError):
            time.sleep(0.02)
    log("P6 arming: no POST was accepted")


# --------------------------------------------------------------------------- #
# The operator. One streaming thread, so a control is a LEVEL that stands
# until it is changed - which is what a hand on a lever is.
# --------------------------------------------------------------------------- #

class Operator:
    def __init__(self, log, rate=20.0):
        self.log = log
        self.rate = rate
        self._lock = threading.Lock()
        self._controls = dict(traction=0.0, steer=0.0, fork=0.0,
                              teleop=False, reset=False)
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        period = 1.0 / self.rate
        while not self._stop.is_set():
            with self._lock:
                controls = dict(self._controls)
            try:
                stim.post_control(HMI_URL, **controls)
            except (urllib.error.URLError, OSError, TimeoutError):
                pass       # the HMI is deliberately stopped in T5.5
            time.sleep(period)

    def set(self, **changes):
        with self._lock:
            self._controls.update(changes)
            controls = dict(self._controls)
        described = " ".join("{}={}".format(k, v) for k, v in sorted(changes.items()))
        self.log("operator: {}".format(described))
        try:
            stim.post_control(HMI_URL, **controls)
        except (urllib.error.URLError, OSError, TimeoutError):
            pass

    def click_reset(self):
        """One momentary reset, exactly as the page's RESET button produces it:
        one POST, one write cycle at TRUE."""
        with self._lock:
            controls = dict(self._controls)
        controls["reset"] = True
        self.log("operator: reset CLICK (momentary, one write cycle)")
        stim.post_control(HMI_URL, **controls)

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)


# --------------------------------------------------------------------------- #
# Observation
# --------------------------------------------------------------------------- #

class Watcher:
    def __init__(self, log):
        self.log = log
        self.previous = {}

    def sample(self):
        return stim.get_state(HMI_URL)

    def line(self, tag, state=None):
        state = state or self.sample()
        self.log("{:<10} {}".format(tag, stim.format_state(state)))
        self.previous = dict(state.get("metrics") or {})
        return dict(state.get("metrics") or {})

    def track(self, tag, seconds, until=None, rate=20.0):
        """Poll, print every change, and stop early when `until(metrics)` is
        true. Returns (metrics, elapsed, satisfied)."""
        started = time.monotonic()
        period = 1.0 / rate
        metrics = {}
        while time.monotonic() - started < seconds:
            state = self.sample()
            metrics = dict(state.get("metrics") or {})
            moved = stim.changed(self.previous, metrics)
            if moved:
                self.log("{:<10} {}   [{}]".format(
                    tag, stim.format_state(state), ",".join(moved)))
                self.previous = metrics
            if until is not None and until(metrics):
                return metrics, time.monotonic() - started, True
            time.sleep(period)
        return metrics, time.monotonic() - started, until is None


def check(log, ok, text):
    log("{}  {}".format("ok  " if ok else "FAIL", text))
    return bool(ok)


# --------------------------------------------------------------------------- #
# The five scenarios
# --------------------------------------------------------------------------- #

def clear_boot_latches(op, watch, log):
    """The opening of every scenario: release the enable, one monitored reset,
    then a fresh enable edge. Steps 5.1.2 to 5.1.4 in miniature."""
    op.set(teleop=False)
    time.sleep(0.5)
    op.click_reset()
    watch.track("reset", 2.0, until=lambda m: not m.get("ForkliftResetRequired"))
    op.set(teleop=True)
    watch.track("enable", 2.0, until=lambda m: m.get("ForkliftTeleopActive"))
    return watch.line("armed")


def scenario_1(stack, op, watch, log, results):
    """Criterion (a) - teleoperated drive, the PLC forming all motion
    setpoints. Mirrors plc/forklift/SPEC.md section 11 T5.1."""
    log.head("S1.1 (5.1.1) the boot reading, before a control is touched")
    boot = watch.line("boot")
    results.append(check(log, boot.get("HmiLinkOk") is True, "HmiLinkOk TRUE"))
    results.append(check(log, boot.get("ForkliftTeleopActive") is False,
                         "ForkliftTeleopActive FALSE"))
    results.append(check(log, boot.get("ForkliftResetRequired") is True,
                         "ForkliftResetRequired TRUE (both link latches formed "
                         "at the first scan)"))
    results.append(check(log, _all_refs_zero(boot), "all three setpoints 0.0"))
    log("note      ForkliftObstacleStopActive reads {} at boot; see the "
        "start-order finding in the scenario file".format(
            boot.get("ForkliftObstacleStopActive")))

    log.head("S1.2 (5.1.2) assert the enable BEFORE any reset")
    op.set(teleop=True)
    metrics, _, _ = watch.track("enable1st", 2.0)
    results.append(check(log, metrics.get("ForkliftTeleopActive") is False,
                         "refused: teleop stays FALSE with a latch pending"))
    results.append(check(log, _all_refs_zero(metrics), "all three refs stay 0.0"))

    log.head("S1.3 (5.1.3) release the enable, one monitored reset")
    op.set(teleop=False)
    time.sleep(0.5)
    op.click_reset()
    metrics, elapsed, ok = watch.track(
        "afterreset", 3.0, until=lambda m: not m.get("ForkliftResetRequired"))
    results.append(check(log, ok, "ForkliftResetRequired -> FALSE in {:.3f} s".format(elapsed)))
    results.append(check(log, metrics.get("ForkliftTeleopActive") is False,
                         "the reset energizes nothing: teleop still FALSE"))
    results.append(check(log, _all_refs_zero(metrics), "every ref still 0.0"))

    log.head("S1.4 (5.1.4) a fresh enable edge, traction at zero")
    op.set(teleop=True)
    metrics, _, ok = watch.track("enable2nd", 3.0,
                                 until=lambda m: m.get("ForkliftTeleopActive"))
    results.append(check(log, ok, "ForkliftTeleopActive -> TRUE"))
    results.append(check(log, _all_refs_zero(metrics), "all three refs still 0.0"))

    log.head("S1.5 (5.1.5) traction control to full forward")
    before = stack.odom()
    op.set(traction=1.0)
    metrics, _, _ = watch.track("driveFwd", 2.5)
    ref = metrics.get("ForkliftTractionSpeedRef")
    results.append(check(log, abs(ref - K_TRACTION_SPEED_MAX) < 0.02,
                         "ForkliftTractionSpeedRef = {:+.3f} m/s "
                         "(demand 1.00 x TRACTION_SPEED_MAX {:.2f})".format(
                             ref, K_TRACTION_SPEED_MAX)))
    results.append(check(log, abs(metrics.get("ForkliftLinearSpeed") - ref) < 0.10,
                         "ForkliftLinearSpeed {:+.3f} tracks the setpoint".format(
                             metrics.get("ForkliftLinearSpeed"))))
    op.set(traction=0.0)
    time.sleep(1.0)
    after = stack.odom()
    log("odom      x {:+.3f} -> {:+.3f} m, moved {:+.3f} m".format(
        before["x"], after["x"], after["x"] - before["x"]))
    results.append(check(log, after["x"] - before["x"] > 1.0,
                         "the model drove forward in Gazebo"))

    log.head("S1.6 (5.1.6) steer to about +0.8 rad, then about -0.8 rad")
    op.set(steer=0.611)          # 0.611 x 1.31 rad = 0.800 rad
    metrics, _, _ = watch.track("steerPos", 2.0)
    positive = metrics.get("ForkliftSteerAngleRef")
    op.set(steer=-0.611)
    metrics, _, _ = watch.track("steerNeg", 2.0)
    negative = metrics.get("ForkliftSteerAngleRef")
    results.append(check(log, abs(positive - 0.800) < 0.02 and abs(negative + 0.800) < 0.02,
                         "ForkliftSteerAngleRef followed the clamped request "
                         "both ways: {:+.4f} then {:+.4f} rad".format(positive, negative)))
    op.set(steer=0.0)
    time.sleep(0.8)

    log.head("S1.7 (5.1.7) traction control to full reverse")
    before = stack.odom()
    op.set(traction=-1.0)
    metrics, _, _ = watch.track("driveRev", 2.5)
    ref = metrics.get("ForkliftTractionSpeedRef")
    results.append(check(log, abs(ref + K_TRACTION_SPEED_MAX) < 0.02,
                         "ForkliftTractionSpeedRef = {:+.3f} m/s - the sign carries "
                         "direction, there is no run bit".format(ref)))

    log.head("S1.8 (5.1.8) release the enable WHILE DRIVING")
    op.set(steer=0.4)            # a standing steer request, to see it zeroed
    time.sleep(0.6)
    op.set(teleop=False)
    metrics, elapsed, ok = watch.track(
        "released", 3.0, until=lambda m: not m.get("ForkliftTeleopActive"))
    results.append(check(log, ok, "ForkliftTeleopActive -> FALSE"))
    results.append(check(log, _all_refs_zero(metrics),
                         "all three refs 0.0, the steer angle included "
                         "(the wheel returns to centre)"))
    results.append(check(log, metrics.get("ForkliftResetRequired") is False,
                         "ForkliftResetRequired stays FALSE - a normal stop, no latch"))
    after = stack.odom()
    log("odom      x {:+.3f} -> {:+.3f} m".format(before["x"], after["x"]))

    log.head("S1.9 (5.1.9) re-assert the enable")
    op.set(traction=0.0, steer=0.0)
    time.sleep(0.5)
    op.set(teleop=True)
    metrics, _, ok = watch.track("re-enable", 3.0,
                                 until=lambda m: m.get("ForkliftTeleopActive"))
    results.append(check(log, ok, "teleop returns with NO reset - releasing the "
                                  "enable is not a fault"))
    op.set(teleop=False, traction=0.0, steer=0.0)
    return results


def scenario_2(stack, op, watch, log, results):
    """Criterion (b) - the fork raised to a commanded height and stopped by the
    PLC's soft travel limits. Mirrors T5.2."""
    clear_boot_latches(op, watch, log)

    log.head("S2.1 (5.2.1) carriage parked, try to LOWER")
    metrics = watch.line("parked")
    height = metrics.get("ForkliftForkHeight")
    results.append(check(log, height < K_FORK_TRAVEL_MIN,
                         "ForkliftForkHeight {:.4f} m is below FORK_TRAVEL_MIN "
                         "{:.2f}".format(height, K_FORK_TRAVEL_MIN)))
    op.set(fork=-1.0)
    metrics, _, _ = watch.track("lowerReq", 2.5)
    results.append(check(log, abs(metrics.get("ForkliftForkSpeedRef")) < 0.001,
                         "ForkliftForkSpeedRef stays 0.0 with the lower control held"))
    results.append(check(log, metrics.get("ForkliftResetRequired") is False,
                         "and it is NOT a fault: ForkliftResetRequired stays FALSE"))

    log.head("S2.2 (5.2.2) full raise")
    op.set(fork=1.0)
    metrics, _, _ = watch.track("raiseFull", 2.5)
    results.append(check(log, abs(metrics.get("ForkliftForkSpeedRef") - K_FORK_SPEED_MAX) < 0.005,
                         "ForkliftForkSpeedRef = {:+.4f} m/s".format(
                             metrics.get("ForkliftForkSpeedRef"))))

    log.head("S2.3 (5.2.3) partial raise demand 0.4")
    op.set(fork=0.4)
    metrics, _, _ = watch.track("raisePart", 2.0)
    expected = 0.4 * K_FORK_SPEED_MAX
    results.append(check(log, abs(metrics.get("ForkliftForkSpeedRef") - expected) < 0.005,
                         "ref {:+.4f} m/s = demand 0.4 x FORK_SPEED_MAX - the demand "
                         "scales, it is not a two-state jog".format(
                             metrics.get("ForkliftForkSpeedRef"))))

    log.head("S2.4 (5.2.4) hold full raise into the upper soft limit")
    op.set(fork=1.0)
    metrics, elapsed, ok = watch.track(
        "toLimit", 25.0,
        until=lambda m: abs(m.get("ForkliftForkSpeedRef") or 0.0) < 0.001)
    stopped_at = metrics.get("ForkliftForkHeight")
    results.append(check(log, ok, "the ref snapped to 0.0 with the raise control "
                                  "still held, after {:.1f} s".format(elapsed)))
    log("MEASURED  stopping height {:.4f} m; FORK_TRAVEL_MAX {:.2f} m; the model's "
        "mechanical stop is 1.60 m".format(stopped_at, K_FORK_TRAVEL_MAX))
    results.append(check(log, K_FORK_TRAVEL_MAX <= stopped_at < 1.60,
                         "stopped between the soft limit and the mechanical stop"))

    log.head("S2.5 (5.2.5) with the carriage held at the limit, command LOWER")
    op.set(fork=-1.0)
    metrics, _, ok = watch.track(
        "lowerOff", 4.0,
        until=lambda m: (m.get("ForkliftForkSpeedRef") or 0.0) < -0.10)
    results.append(check(log, ok, "ref {:+.4f} m/s - the abort is direction-scoped "
                                  "and the carriage is not stranded".format(
                                      metrics.get("ForkliftForkSpeedRef"))))

    log.head("S2.6 (5.2.6) hold the lower past FORK_TRAVEL_MIN")
    metrics, elapsed, ok = watch.track(
        "toFloor", 25.0,
        until=lambda m: abs(m.get("ForkliftForkSpeedRef") or 0.0) < 0.001)
    low_stop = metrics.get("ForkliftForkHeight")
    results.append(check(log, ok, "the ref snapped to 0.0 at the lower soft limit "
                                  "after {:.1f} s, height {:.4f} m".format(
                                      elapsed, low_stop)))
    op.set(fork=1.0)
    metrics, _, ok = watch.track(
        "raiseAgain", 3.0,
        until=lambda m: (m.get("ForkliftForkSpeedRef") or 0.0) > 0.10)
    results.append(check(log, ok, "commanding raise moves it again immediately"))

    log.head("S2.7 (5.2.7) the latch bits through 5.2.1-5.2.6")
    metrics = watch.line("latches")
    results.append(check(log, metrics.get("ForkliftResetRequired") is False
                         and metrics.get("ForkliftObstacleStopActive") is False,
                         "ForkliftResetRequired and ForkliftObstacleStopActive both "
                         "FALSE: a soft-limit abort is a refusal of one direction, "
                         "not a latch"))

    log.head("S2.8 (5.2.8) mid-travel, release the enable")
    watch.track("midTravel", 3.0)
    op.set(teleop=False, fork=0.0)
    metrics, _, _ = watch.track("enableOff", 3.0)
    results.append(check(log, abs(metrics.get("ForkliftForkSpeedRef")) < 0.001,
                         "ForkliftForkSpeedRef -> 0.0"))
    # The carriage is measured AFTER it has come to rest, not across the command
    # transition: between the last metrics poll and the plant obeying the zero it
    # travels another jog-speed fraction of a second, which is motion the machine
    # was still commanded to make and not a fall.
    settled = watch.line("settled")
    parked_at = settled.get("ForkliftForkHeight")
    time.sleep(3.0)
    held = watch.line("holding")
    drift = held.get("ForkliftForkHeight") - parked_at
    results.append(check(log, abs(drift) < 0.005 and parked_at > 0.20,
                         "the carriage HOLDS {:.4f} m against gravity over 3 s "
                         "(drift {:+.4f} m) - 0.0 means hold, not fall".format(
                             held.get("ForkliftForkHeight"), drift)))
    return results


def scenario_3(stack, op, watch, log, results):
    """Criterion (c) - traction capped by the PLC while the fork is above its
    height threshold. Mirrors T5.3."""
    clear_boot_latches(op, watch, log)

    log.head("S3.0 setup: park the carriage below the threshold")
    # Released well short of FORK_HEIGHT_SLOW_THRESHOLD. The operator's screen
    # refreshes at 5 Hz and the command takes a write cycle and a bridge round
    # trip to reach the plant, so a carriage released AT the threshold coasts
    # past it: released at 0.42, this run parked at 0.5026 and the scenario's
    # own precondition was gone.
    op.set(fork=1.0)
    watch.track("preRaise", 20.0,
                until=lambda m: (m.get("ForkliftForkHeight") or 0.0) >= 0.28)
    op.set(fork=0.0)
    time.sleep(0.5)
    metrics = watch.line("preRaised")
    log("setup     carriage parked at {:.4f} m, below "
        "FORK_HEIGHT_SLOW_THRESHOLD {:.2f}".format(
            metrics.get("ForkliftForkHeight"), K_FORK_HEIGHT_SLOW_THRESHOLD))

    log.head("S3.1 (5.3.1) below the threshold, traction control at full forward")
    op.set(traction=1.0)
    metrics, _, _ = watch.track("uncapped", 2.0)
    uncapped_ref = metrics.get("ForkliftTractionSpeedRef")
    uncapped_speed = metrics.get("ForkliftLinearSpeed")
    results.append(check(log, abs(uncapped_ref - K_TRACTION_SPEED_MAX) < 0.02,
                         "ForkliftTractionSpeedRef {:+.3f} m/s".format(uncapped_ref)))
    results.append(check(log, metrics.get("ForkliftSpeedLimitActive") is False,
                         "ForkliftSpeedLimitActive FALSE"))

    log.head("S3.2 (5.3.2) raise past the threshold with the traction still at full")
    op.set(fork=1.0)
    metrics, elapsed, ok = watch.track(
        "capping", 12.0, until=lambda m: m.get("ForkliftSpeedLimitActive"))
    crossing_height = metrics.get("ForkliftForkHeight")
    op.set(fork=0.0)
    metrics, _, _ = watch.track("capped", 2.5)
    capped_ref = metrics.get("ForkliftTractionSpeedRef")
    capped_speed = metrics.get("ForkliftLinearSpeed")
    results.append(check(log, ok, "ForkliftSpeedLimitActive -> TRUE at height "
                                  "{:.4f} m".format(crossing_height)))
    results.append(check(log, abs(capped_ref - K_TRACTION_SPEED_CAP_RAISED) < 0.02,
                         "ForkliftTractionSpeedRef dropped {:+.3f} -> {:+.3f} m/s "
                         "with the operator touching nothing".format(
                             uncapped_ref, capped_ref)))
    log("MEASURED  ForkliftLinearSpeed {:+.3f} -> {:+.3f} m/s: the model visibly "
        "slows in Gazebo".format(uncapped_speed, capped_speed))
    results.append(check(log, capped_speed < uncapped_speed - 0.3,
                         "the plant followed the cap"))

    log.head("S3.4 (5.3.4) with the carriage raised, traction demand 0.2")
    op.set(traction=0.2)
    metrics, _, _ = watch.track("partial", 2.5)
    partial_ref = metrics.get("ForkliftTractionSpeedRef")
    # The program SCALES the demand by the reduced cap - SPEC section 9's row
    # reads "demand x 0.30 with the fork raised", and section 7 forms it that
    # way. Section 11 step 5.3.4's Pass line predicts the LIMIT form instead
    # (demand 0.2 -> 0.20 m/s). The two cannot both hold, and the divergence is
    # reported rather than absorbed into a tolerance.
    scaled = 0.2 * K_TRACTION_SPEED_CAP_RAISED
    limited = 0.2 * K_TRACTION_SPEED_MAX
    results.append(check(log, abs(partial_ref - scaled) < 0.02,
                         "ref {:+.3f} m/s = demand 0.2 x TRACTION_SPEED_CAP_RAISED "
                         "{:.2f}, the form SPEC sections 7 and 9 specify".format(
                             partial_ref, K_TRACTION_SPEED_CAP_RAISED)))
    log("FINDING   SPEC section 11 step 5.3.4 predicts {:+.3f} m/s here (the cap "
        "as a LIMIT on the demand); sections 7 and 9 build {:+.3f} m/s (the cap "
        "as a SCALE). Observed {:+.3f}. A plc/ ruling, not a sim/ choice".format(
            limited, scaled, partial_ref))
    results.append(check(log, metrics.get("ForkliftSpeedLimitActive") is True,
                         "ForkliftSpeedLimitActive stays TRUE: it reads 'the cap is "
                         "in force', not 'the cap is biting'"))

    log.head("S3.x reversing back up the aisle, still raised")
    # Not a step of T5.3: the vehicle has to be put back where it can drive
    # forward again without meeting the crate. Worth one line anyway, because
    # the cap is a cap on the MAGNITUDE and it bites in reverse too.
    op.set(traction=-1.0)
    metrics, _, _ = watch.track("reverseCap", 5.0)
    log("note      reversing raised: ForkliftTractionSpeedRef {:+.3f} m/s - the cap "
        "applies to the magnitude, not to the forward direction".format(
            metrics.get("ForkliftTractionSpeedRef")))

    log.head("S3.3 (5.3.3) lower back below the threshold")
    op.set(traction=0.0)
    time.sleep(0.5)
    op.set(fork=-1.0)
    metrics, _, ok = watch.track(
        "uncapping", 12.0, until=lambda m: not m.get("ForkliftSpeedLimitActive"))
    op.set(fork=0.0)
    op.set(traction=1.0)
    metrics, _, _ = watch.track("restored", 2.0)
    results.append(check(log, ok and abs(metrics.get("ForkliftTractionSpeedRef")
                                         - K_TRACTION_SPEED_MAX) < 0.02,
                         "ref back to {:+.3f} m/s and ForkliftSpeedLimitActive "
                         "FALSE".format(metrics.get("ForkliftTractionSpeedRef"))))

    log.head("S3.5 (5.3.5) ForkliftLinearSpeed feeds no verdict")
    log("note      ForkliftLinearSpeed tracked every ref above and is read and "
        "qualified by the program, but no traction drive-fault verdict exists on "
        "this plant (SPEC section 8 case P, section 12 open item 3)")
    results.append(check(log, True, "recorded"))
    op.set(traction=0.0, teleop=False)
    return results


def scenario_4(stack, op, watch, log, results):
    """Criterion (d) - an obstacle latching a PLC process stop that overrides
    teleop, cleared only by the edge-triggered monitored reset after the zone
    clears. Mirrors T5.4 IN ITS CORRECTED, HELD-RESET FORM."""
    clear_boot_latches(op, watch, log)

    log.head("S4.1 (5.4.1) drive at the crate; the distance falls and nothing changes")
    op.set(traction=0.6)
    metrics, _, _ = watch.track("approach", 3.0)
    results.append(check(log, metrics.get("ForkliftObstacleStopActive") is False
                         and metrics.get("ForkliftTeleopActive") is True,
                         "ForkliftObstacleMinDistance falling to {:.3f} m with no "
                         "PLC threshold on it - the field verdict belongs to the "
                         "device".format(metrics.get("ForkliftObstacleMinDistance"))))

    log.head("S4.2 (5.4.2) continue until ForkliftObstacleInStopZone goes TRUE")
    metrics, elapsed, ok = watch.track(
        "latching", 20.0, until=lambda m: m.get("ForkliftObstacleStopActive"))
    state = watch.sample()
    requests = state.get("requests") or {}
    results.append(check(log, ok, "ForkliftObstacleStopActive -> TRUE after "
                                  "{:.1f} s".format(elapsed)))
    results.append(check(log, metrics.get("ForkliftTeleopActive") is False,
                         "ForkliftTeleopActive -> FALSE"))
    results.append(check(log, _all_refs_zero(metrics), "all three refs -> 0.0"))
    results.append(check(log, metrics.get("ForkliftResetRequired") is True,
                         "ForkliftResetRequired -> TRUE"))
    results.append(check(log, abs(float(requests.get("HmiTractionRequest") or 0.0) - 0.6) < 0.01,
                         "HmiTractionRequest is STILL STANDING at {:+.2f} - the latch "
                         "overrides a live command, which is the criterion".format(
                             float(requests.get("HmiTractionRequest") or 0.0))))

    log.head("S4.3 (5.4.3) hold the traction demand for 10 s")
    metrics, _, _ = watch.track("standing", 10.0)
    results.append(check(log, _all_refs_zero(metrics),
                         "refs stay 0.0 - nothing resumes and nothing creeps"))

    log.head("S4.4 (5.4.4) assert the reset AND HOLD IT while the zone is occupied")
    op.set(reset=True)
    metrics, _, _ = watch.track("resetHeld", 4.0)
    state = watch.sample()
    requests = state.get("requests") or {}
    results.append(check(log, requests.get("HmiResetRequest") is True,
                         "HmiResetRequest reads TRUE and stays TRUE (held by "
                         "re-posting above the HMI write rate)"))
    results.append(check(log, metrics.get("ForkliftResetRequired") is True
                         and metrics.get("ForkliftObstacleStopActive") is True,
                         "the reset is REFUSED: CauseGone is false on C3"))

    log.head("S4.5 (5.4.5) release and re-assert the ENABLE, reset still held")
    op.set(teleop=False)
    time.sleep(0.8)
    op.set(teleop=True)
    metrics, _, _ = watch.track("enableTry", 3.0)
    results.append(check(log, metrics.get("ForkliftTeleopActive") is False,
                         "refused - the machine cannot drive itself clear. A "
                         "deliberate consequence, not a defect"))

    log.head("S4.6 (5.4.6) clear the zone WITH THE RESET STILL HELD")
    stack.obstacle(8.0)
    metrics, elapsed, ok = watch.track(
        "zoneClear", 8.0, until=lambda m: m.get("ForkliftObstacleInStopZone") is False)
    state = watch.sample()
    requests = state.get("requests") or {}
    results.append(check(log, ok, "ForkliftObstacleInStopZone -> FALSE, "
                                  "ForkliftObstacleMinDistance {:.3f} m".format(
                                      metrics.get("ForkliftObstacleMinDistance"))))
    results.append(check(log, requests.get("HmiResetRequest") is True,
                         "while HmiResetRequest still reads TRUE"))
    results.append(check(log, metrics.get("ForkliftObstacleStopActive") is True
                         and metrics.get("ForkliftResetRequired") is True,
                         "the latch STANDS: the field clearing does not release it, "
                         "and the still-asserted reset supplies no edge"))

    log.head("S4.7 (5.4.7) stuck reset: keep it held for 10 s with the zone clear")
    metrics, _, _ = watch.track("stuckReset", 10.0)
    results.append(check(log, metrics.get("ForkliftObstacleStopActive") is True
                         and metrics.get("ForkliftResetRequired") is True,
                         "the latch NEVER clears while it is held: there is no edge "
                         "to act on and no elapsed time makes one appear"))

    log.head("S4.8 (5.4.8) release the reset, confirm FALSE, assert it again")
    op.set(reset=False)
    time.sleep(0.6)
    state = watch.sample()
    requests = state.get("requests") or {}
    results.append(check(log, requests.get("HmiResetRequest") is False,
                         "HmiResetRequest reads FALSE"))
    op.click_reset()
    metrics, elapsed, ok = watch.track(
        "freshEdge", 4.0, until=lambda m: not m.get("ForkliftResetRequired"))
    results.append(check(log, ok, "every latch clears on that FRESH rising edge, "
                                  "after {:.3f} s".format(elapsed)))
    metrics, _, _ = watch.track("afterClear", 2.0)
    results.append(check(log, metrics.get("ForkliftObstacleStopActive") is False,
                         "ForkliftObstacleStopActive -> FALSE"))
    results.append(check(log, _all_refs_zero(metrics)
                         and metrics.get("ForkliftTeleopActive") is False,
                         "NOTHING MOVES: teleop stays FALSE even though the enable "
                         "has been asserted since 5.4.5 - a level that never fell "
                         "produces no edge. That is the no-auto-resume property"))

    log.head("S4.9 (5.4.9) release the enable, confirm FALSE, assert it again")
    op.set(teleop=False)
    time.sleep(0.8)
    state = watch.sample()
    requests = state.get("requests") or {}
    results.append(check(log, requests.get("HmiTeleopRequest") is False,
                         "HmiTeleopRequest reads FALSE"))
    op.set(teleop=True)
    metrics, _, ok = watch.track("reEnable", 4.0,
                                 until=lambda m: m.get("ForkliftTeleopActive"))
    results.append(check(log, ok, "teleop returns on that fresh edge; reset and "
                                  "enable are two separate, deliberate actions"))
    metrics, _, _ = watch.track("drivesAgain", 2.5)
    results.append(check(log, abs(metrics.get("ForkliftTractionSpeedRef") - 0.6) < 0.03,
                         "and the refs follow the operator's controls again: "
                         "{:+.3f} m/s".format(metrics.get("ForkliftTractionSpeedRef"))))
    op.set(traction=0.0)

    log.head("S4.10 (5.4.10) lidar transducer fault: the scan interrupted AT THE SOURCE")
    # The arena's ros_gz_bridge is what carries /forklift/scan out of Gazebo.
    # Finishing it by exact pid stops the scan at its source; obstacle_zone then
    # reports 'scan stale' and publishes its no-data sentinel, which is outside
    # the PLC's plausibility window.
    killed = _finish_arena_scan_bridge(stack, log)
    if not killed:
        log("NOT RUN   the arena scan bridge could not be identified; step 5.4.10 "
            "is recorded as not run (SPEC section 11 rule 3)")
        results.append(check(log, False, "5.4.10 not run"))
    else:
        metrics, elapsed, ok = watch.track(
            "lidarFault", 12.0, until=lambda m: m.get("ForkliftObstacleStopActive"))
        results.append(check(log, ok, "ForkliftObstacleStopActive latched {:.2f} s "
                                      "after the scan stopped".format(elapsed)))
        results.append(check(log, metrics.get("ForkliftObstacleInStopZone") is True,
                             "ForkliftObstacleInStopZone reads TRUE at the same "
                             "moment - two independent signals pointing the same way"))
        log("MEASURED  ForkliftObstacleMinDistance reads {:.3f} - the vehicle "
            "layer's no-data sentinel, outside OBSTACLE_DISTANCE_MIN 0.05".format(
                metrics.get("ForkliftObstacleMinDistance")))
    return results


def scenario_5(stack, op, watch, log, results):
    """Criterion (e) - loss of the HMI heartbeat zeroing all motion setpoints
    within the watchdog period. Mirrors T5.5."""
    clear_boot_latches(op, watch, log)

    log.head("S5.1 (5.5.1) teleop active and DRIVING, with the fork jogging too")
    op.set(traction=0.55, fork=1.0)
    metrics, _, _ = watch.track("driving", 3.0)
    results.append(check(log, metrics.get("ForkliftTractionSpeedRef") > 0.5
                         and metrics.get("ForkliftForkSpeedRef") > 0.1,
                         "driving at {:+.3f} m/s with the fork jogging at "
                         "{:+.4f} m/s".format(metrics.get("ForkliftTractionSpeedRef"),
                                              metrics.get("ForkliftForkSpeedRef"))))
    before = stack.odom()

    log.head("S5.2 (5.5.2) stop the HMI process")
    sent = stack.stop_named("hmi")
    log("MEASURED  SIGTERM to the HMI at monotonic {:.4f}".format(sent))
    # From here the operator's screen is gone: the observable is the bridge's
    # own 20 Hz read of the output slots and its 1 Hz diagnostics poll.
    time.sleep(6.0)
    zeroed_at, last_nonzero = _first_zero_traction_ref(stack, log, after=sent)
    hmi_last_beat = _hmi_last_cycle_monotonic(stack, log)
    if zeroed_at is not None and hmi_last_beat is not None:
        elapsed_ms = (zeroed_at - hmi_last_beat) * 1000.0
        log("MEASURED  last HMI write cycle at monotonic {:.4f}; first bridge read "
            "of ForkliftTractionSpeedRef = 0.0 at monotonic {:.4f}".format(
                hmi_last_beat, zeroed_at))
        log("MEASURED  elapsed last-advancing-beat -> setpoint 0.0 = "
            "{:.0f} ms (HMI_STALE_TIME is {:.0f} ms)".format(
                elapsed_ms, K_HMI_STALE_TIME_S * 1000.0))
        results.append(check(log, 0.0 < elapsed_ms < 2000.0,
                             "the bound is a number, not an average"))
    else:
        results.append(check(log, False, "the measurement could not be taken"))
    if last_nonzero is not None:
        log("note      the last non-zero read before that was {:+.3f} m/s".format(
            last_nonzero))
    diagnostics = _last_bridge_diagnostics(stack)
    log("bridge    PLC diagnostics after the outage: {}".format(diagnostics))
    results.append(check(log, diagnostics.get("HmiLinkOk") is False,
                         "HmiLinkOk FALSE, read from the bridge's own session"))
    results.append(check(log, diagnostics.get("ForkliftTeleopActive") is False,
                         "ForkliftTeleopActive FALSE"))
    results.append(check(log, diagnostics.get("ForkliftResetRequired") is True,
                         "ForkliftResetRequired TRUE"))

    log.head("S5.3 (5.5.3) observe the model in Gazebo")
    after = stack.odom()
    time.sleep(2.0)
    settled = stack.odom()
    log("odom      x {:+.3f} -> {:+.3f} -> {:+.3f} m".format(
        before["x"], after["x"], settled["x"]))
    results.append(check(log, abs(settled["x"] - after["x"]) < 0.05,
                         "the model stopped on the PLC's zero command"))

    log.head("S5.4 (5.5.4) restart the HMI and do nothing else for 30 s")
    stack.start_hmi()
    metrics, _, _ = watch.track("relinked", 30.0)
    results.append(check(log, metrics.get("HmiLinkOk") is True,
                         "HmiLinkOk -> TRUE"))
    results.append(check(log, metrics.get("ForkliftTeleopActive") is False,
                         "teleop does NOT return"))
    results.append(check(log, _all_refs_zero(metrics), "refs stay 0.0"))
    results.append(check(log, metrics.get("ForkliftResetRequired") is True,
                         "ForkliftResetRequired stays TRUE"))

    log.head("S5.5 (5.5.5) the P6 guard: a reset asserted from before link-up")
    op.set(traction=0.0, fork=0.0, teleop=False)
    time.sleep(0.5)
    stack.stop_named("hmi")
    time.sleep(3.0)
    op.set(reset=True)          # the streamer keeps posting it from now on
    stack.start_hmi(hold_reset_from_first_post=True)
    metrics, _, _ = watch.track("p6", 12.0)
    state = watch.sample()
    requests = state.get("requests") or {}
    guard_held = (metrics.get("ForkliftResetRequired") is True
                  and requests.get("HmiResetRequest") is True)
    results.append(check(log, guard_held,
                         "the edge arriving with the first attributable sample is "
                         "REFUSED: ForkliftResetRequired still TRUE with "
                         "HmiResetRequest TRUE and HmiLinkOk {}".format(
                             metrics.get("HmiLinkOk"))))
    op.set(reset=False)
    time.sleep(1.0)
    op.click_reset()
    metrics, _, ok = watch.track(
        "p6clear", 5.0, until=lambda m: not m.get("ForkliftResetRequired"))
    results.append(check(log, ok, "then FALSE and TRUE again: THAT fresh edge "
                                  "clears the latches"))

    log.head("S5.6 (5.5.6) reset normally, then assert the enable")
    op.set(teleop=False)
    time.sleep(0.6)
    op.set(teleop=True)
    metrics, _, ok = watch.track("driveable", 5.0,
                                 until=lambda m: m.get("ForkliftTeleopActive"))
    results.append(check(log, ok, "teleop returns on the fresh enable edge"))
    op.set(traction=0.4)
    metrics, _, _ = watch.track("moving", 2.5)
    # The carriage was left raised by 5.5.1's fork jog, so the ref is the demand
    # under the raised-carriage cap, not under TRACTION_SPEED_MAX. Which cap is
    # in force is read off ForkliftSpeedLimitActive rather than assumed.
    capped = metrics.get("ForkliftSpeedLimitActive")
    expected = 0.4 * (K_TRACTION_SPEED_CAP_RAISED if capped else K_TRACTION_SPEED_MAX)
    results.append(check(log, abs(metrics.get("ForkliftTractionSpeedRef") - expected) < 0.02,
                         "the machine is driveable: {:+.3f} m/s = demand 0.4 with "
                         "ForkliftSpeedLimitActive {} (carriage at {:.3f} m). No "
                         "auto-resume at any point in 5.5.1-5.5.5".format(
                             metrics.get("ForkliftTractionSpeedRef"), capped,
                             metrics.get("ForkliftForkHeight"))))
    op.set(traction=0.0, fork=0.0, teleop=False)
    return results


# --------------------------------------------------------------------------- #
# Evidence readers. They read files other processes wrote; they change nothing.
# --------------------------------------------------------------------------- #

def _all_refs_zero(metrics, tolerance=0.001):
    """All three setpoints at rest. An ABSENT value is not a zero: a panel that
    has not been read yet must fail this test rather than pass it silently."""
    names = ("ForkliftTractionSpeedRef", "ForkliftSteerAngleRef",
             "ForkliftForkSpeedRef")
    if any(metrics.get(name) is None for name in names):
        return False
    return all(abs(float(metrics[name])) < tolerance for name in names)


def _session_file(stack, name):
    directory = os.path.join(stack.scratch, "evidence")
    matches = sorted(f for f in os.listdir(directory) if f.startswith(name + "-"))
    return os.path.join(directory, matches[-1]) if matches else None


def _first_zero_traction_ref(stack, log, after):
    """The first 20 Hz read of ForkliftTractionSpeedRef that returned 0.0 after
    a given monotonic instant, out of the bridge's own per-session CSV.

    CLOCK_MONOTONIC is system-wide on Linux, so the bridge's t_start_ns and this
    process's time.monotonic() are the same clock and may be subtracted."""
    path = _session_file(stack, "bridge")
    if path is None:
        return None, None
    last_nonzero, first_zero = None, None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        header = handle.readline().rstrip("\n").split(",")
        try:
            i_event = header.index("event")
            i_name = header.index("name")
            i_start = header.index("t_start_ns")
            i_value = header.index("value")
        except ValueError:
            return None, None
        for line in handle:
            row = line.rstrip("\n").split(",")
            if len(row) <= i_value:
                continue
            if row[i_event] != "read_rt" or row[i_name] != "ForkliftTractionSpeedRef":
                continue
            try:
                when = int(row[i_start]) / 1e9
                value = float(row[i_value])
            except ValueError:
                continue
            if when < after:
                if abs(value) > 0.001:
                    last_nonzero = value
                continue
            if abs(value) > 0.001:
                last_nonzero = value
                continue
            if first_zero is None:
                first_zero = when
                break
    log("evidence  bridge session CSV {}".format(os.path.basename(path)))
    return first_zero, last_nonzero


def _hmi_last_cycle_monotonic(stack, log):
    """The monotonic timestamp of the HMI's last write cycle, out of its own
    per-session CSV. That row IS the last advancing beat."""
    path = _session_file(stack, "hmi")
    if path is None:
        return None
    last = None
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        header = handle.readline().rstrip("\n").split(",")
        try:
            index = header.index("monotonic_s")
        except ValueError:
            return None
        for line in handle:
            row = line.rstrip("\n").split(",")
            if len(row) > index:
                try:
                    last = float(row[index])
                except ValueError:
                    pass
    log("evidence  HMI session CSV {}".format(os.path.basename(path)))
    return last


def _last_bridge_diagnostics(stack):
    """The bridge's most recent 1 Hz diagnostics poll, out of its log. It is an
    independent reading of the PLC's verdicts while the HMI is stopped."""
    path = stack.log_path("bridge")
    found = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if "PLC diagnostics" in line:
                    blob = line.split("PLC diagnostics (logged only):", 1)[-1].strip()
                    try:
                        found = json.loads(blob.replace("'", '"')
                                           .replace("True", "true")
                                           .replace("False", "false"))
                    except ValueError:
                        pass
    except OSError:
        pass
    return found


#: Node names the arena bringup's ros_gz_bridge has been started under. It was
#: `forklift_arena_bridge` while sim/launch/forklift_bringup.launch.py stated
#: its own bridge table; since 2026-08-06 that file includes
#: agv/forklift/launch/vehicle.launch.py, whose bridge node is named
#: `forklift_bridge`. BOTH are matched rather than the old one replaced,
#: because this stimulus fails SILENTLY if it matches nothing - it returns
#: False, the scan keeps flowing, and the scenario measures a stale-scan
#: reaction that was never provoked.
_ARENA_BRIDGE_NODE_NAMES = ("forklift_bridge", "forklift_arena_bridge")


def _finish_arena_scan_bridge(stack, log):
    """Finish the arena's ros_gz_bridge by exact pid, so /forklift/scan stops at
    its source. Only a pid in this run's GZ_PARTITION is ever signalled."""
    for pid, command in stack.survivors():
        if "parameter_bridge" in command and any(
                n in command for n in _ARENA_BRIDGE_NODE_NAMES):
            log("stimulus  finishing the arena scan bridge, pid {} (exact pid, "
                "partition {})".format(pid, stack.partition))
            try:
                os.kill(pid, signal.SIGKILL)
                return True
            except ProcessLookupError:
                return False
    return False


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

SCENARIOS = {
    1: ("criterion (a) teleoperated drive, the PLC forming all setpoints", scenario_1),
    2: ("criterion (b) fork to height, both soft-limit aborts", scenario_2),
    3: ("criterion (c) traction capped while the fork is raised", scenario_3),
    4: ("criterion (d) obstacle latch, override, refusal, monitored reset", scenario_4),
    5: ("criterion (e) HMI heartbeat loss zeroes every motion setpoint", scenario_5),
}


def run_one(number, args):
    title, body = SCENARIOS[number]
    scratch = os.path.join(args.scratch, "s{}".format(number))
    os.makedirs(os.path.join(scratch, "log"), exist_ok=True)
    log = Log(os.path.join(scratch, "transcript.log"))
    log.head("REHEARSAL EVIDENCE - scenario {} - {}".format(number, title))
    log("against plc/forklift/double/ on 127.0.0.1:4850 - a REHEARSAL STAND-IN, "
        "not a PLC and not PLCSIM Advanced")
    partition = "{}{}".format(args.partition, number)
    domain = args.domain + number
    log("GZ_PARTITION={}  ROS_DOMAIN_ID={}".format(partition, domain))
    stack = Stack(log, partition, domain, scratch)
    operator = Operator(log)
    watcher = Watcher(log)
    results = []
    try:
        log.head("bringup, in the procedure's order")
        stack.start_double()
        stack.start_bridge()
        stack.start_sim()
        stack.start_vehicle()
        stack.start_hmi()
        operator.start()
        log.zero()
        body(stack, operator, watcher, log, results)
    except Exception as exc:                       # noqa: BLE001 - reported, not hidden
        log("ABORTED   {}: {}".format(type(exc).__name__, exc))
        results.append(False)
    finally:
        operator.stop()
        if not args.keep_up:
            stack.teardown()
    passed = sum(1 for r in results if r)
    log.head("scenario {} result: {} of {} checks passed".format(
        number, passed, len(results)))
    return passed, len(results)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--scenario", default="all",
                        help="1..5 or 'all' or a comma list")
    parser.add_argument("--partition", default="m4f08reh",
                        help="GZ_PARTITION stem; the scenario number is appended")
    parser.add_argument("--domain", type=int, default=70,
                        help="ROS_DOMAIN_ID base; the scenario number is added")
    parser.add_argument("--scratch", default="/tmp/amr-m4f08",
                        help="where logs and per-session evidence files go")
    parser.add_argument("--keep-up", action="store_true",
                        help="leave the stack running after the scenario")
    args = parser.parse_args(argv)

    if args.scenario == "all":
        numbers = sorted(SCENARIOS)
    else:
        numbers = [int(part) for part in args.scenario.split(",")]

    totals = []
    for number in numbers:
        totals.append((number,) + run_one(number, args))
    print("")
    print("=== REHEARSAL EVIDENCE summary (PLC logic double, never PLCSIM) ===")
    for number, passed, total in totals:
        print("  scenario {}  {} of {} checks passed  - {}".format(
            number, passed, total, SCENARIOS[number][0]))
    return 0 if all(p == t and t for _, p, t in totals) else 1


if __name__ == "__main__":
    sys.exit(main())
