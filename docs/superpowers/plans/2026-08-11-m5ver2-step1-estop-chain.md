# m5_ver2 Step 1 — E-Stop Chain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Teleoperate the existing Gazebo forklift from a tkinter HMI joystick where the drive enable comes from the real safety PLC in S7-PLCSIM Advanced, and where pressing e-stop stops the truck through both a command zero and a plant-level torque removal.

**Architecture:** One Windows process (`step1.py`) is the sole writer to PLCSIM Advanced instance `PLC_2`; it streams `{estop_healthy, motor, ts}` over UDP :5100 to WSL. In WSL, `plc_link.py` republishes that as `/plc/status` and `/forklift/safety/torque_off_demand`. `hmi_node.py` draws a joystick and an e-stop lamp. `cmd_gate.py` forwards the joystick to `/forklift/cmd/*` only while `motor` is true and publishes continuous zeros otherwise. The existing `forklift_io.py` and `sto_contactor.py` are reused unmodified; the contactor is the unbypassable interlock at the model's own inputs.

**Tech Stack:** Python 3.12, pythonnet (Windows, 64-bit) for the PLCSIM Advanced Runtime API, rclpy on ROS 2 Jazzy, Gazebo Harmonic 8.11, tkinter, stdlib UDP, pytest 7.4.4.

**Spec:** `docs/superpowers/specs/2026-08-11-m5ver2-step1-estop-chain-design.md`

## Global Constraints

Every task's requirements implicitly include this section.

- **Single-writer rule.** Exactly one process — `step1.py` on Windows — opens the PLCSIM Advanced API. No ROS node, no test, no helper script may open it.
- **Fail-safe direction.** On any exception, timeout or shutdown, boolean PLC inputs are written `False` and the vehicle command is zeroed.
- **The PLC program is ground truth.** Never change PLC logic, tags or addresses. Never invent a tag name. Tag names are case-sensitive and may contain hyphens (`E-Stop`).
- **PLCSIM instance name is `PLC_2`.** API DLL directory is `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0`. API error `-4` (`DoesNotExist`) means the instance is not running or the name mismatches — report it, never work around it.
- **The bridge must hold `PF_OSSD=True`, `WF_Clear=True`, `ENC_A=0`, `ENC_B=0` every cycle**, or `Motor` can never energise.
- **Nothing is copied from the existing tree.** `sim/worlds/warehouse.sdf`, `agv/forklift/model.sdf`, `agv/forklift/config.yaml`, `agv/forklift/scripts/forklift_io.py` and `agv/forklift/scripts/sto_contactor.py` are used where they are, unmodified.
- **No topic name is a literal.** Every ROS and gz topic name is read from `agv/forklift/config.yaml` under `topics:`. The two exceptions, which that file does not own, are `/plc/status` and `/hmi/cmd_vel`.
- **Target < 150 lines per file.** Plain Python run with `python3`. No colcon package, no classes without need.
- **Every shell that runs `gz` must source `/opt/ros/jazzy/setup.bash` first.** There is no `/usr/bin/gz` on this machine.
- **Repo root in WSL:** `/mnt/c/Users/ozkan/projects/amr-agent`. On Windows: `C:\Users\ozkan\projects\amr-agent`.
- **Do not begin Step 2.** When Task 8 is done, print the validation checklist and stop.

## File Structure

| File | Responsibility |
|---|---|
| `m5_ver2/CLAUDE.md` | Working agreements, PLC ground truth verbatim, port map. Every later step reads this instead of re-deriving context. |
| `m5_ver2/step1/windows/step1.py` | The only PLC writer. 20 ms loop, terminal commands, UDP transmit. |
| `m5_ver2/step1/ros2/plc_link.py` | UDP :5100 receiver. Publishes `/plc/status` and the torque-off demand. |
| `m5_ver2/step1/ros2/cmd_gate.py` | Enable-gated command forwarding, continuous zeros when inhibited. |
| `m5_ver2/step1/ros2/hmi_node.py` | tkinter joystick and e-stop lamp. |
| `m5_ver2/step1/gazebo/step1_world.launch.py` | gz + spawn + bridge + `forklift_io.py` + `sto_contactor.py`. |
| `m5_ver2/step1/tests/conftest.py` | Puts `ros2/` and `windows/` on `sys.path` for the tests. |
| `m5_ver2/step1/tests/test_plc_link.py` | Staleness and JSON-parse behaviour. |
| `m5_ver2/step1/tests/test_cmd_gate.py` | Gate decision and clamping. |
| `m5_ver2/step1/tests/test_hmi_node.py` | Knob-to-Twist mapping, lamp text. |
| `m5_ver2/step1/step1.sh` | `start` / `stop`, idempotent, PIDs in `.step1_pids`. |
| `m5_ver2/step1/README_step1.md` | Run order, CONFIG, validation checklist. |

Every node file keeps its decision logic in module-level pure functions and its rclpy wiring in a `main()` guarded by `if __name__ == '__main__':`. That is what makes the tests possible without a running ROS graph, and it is the reason no test in this plan needs a fixture beyond `conftest.py`.

**Tests run in WSL with ROS sourced:**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/ -v
```

## Reference values, already established

Do not re-derive these. They were read out of the tree on 2026-08-11.

| Thing | Value | Where it lives |
|---|---|---|
| World name | `warehouse` | `sim/worlds/warehouse.sdf:206` |
| Spawn pose | `x=-3.00 y=-5.50 z=0.05 yaw=0.0` | `sim/launch/warehouse_bringup.launch.py:229-232` |
| Speed limit | `1.50` m/s | `config.yaml` `limits.traction_speed_max_mps` |
| Steer limit | `1.31` rad | `config.yaml` `model.steer_limit_rad` |
| Gate output topics | `topics.cmd_traction_speed`, `topics.cmd_steer_angle` | `config.yaml:1036-1037` |
| Contactor input | `topics.gz_traction_cmd`, `topics.gz_steer_cmd` | `config.yaml:811-812` |
| Contactor output / bridge | `topics.gz_actuator_traction_cmd`, `topics.gz_actuator_steer_cmd` | `config.yaml:834-835` |
| Demand topic | `topics.safety_torque_off_demand` | `config.yaml:1186` |
| Applied topic | `topics.safety_torque_off_applied` | `config.yaml:1187` |
| Clock topic | `topics.clock` | `config.yaml:806` |
| WSL guest IP today | `172.19.180.72` | `wsl hostname -I` — auto-discovered, never hard-coded |

---

### Task 1: `m5_ver2/CLAUDE.md` and the directory skeleton

**Files:**
- Create: `m5_ver2/CLAUDE.md`
- Create: `m5_ver2/step1/windows/`, `m5_ver2/step1/ros2/`, `m5_ver2/step1/gazebo/`, `m5_ver2/step1/tests/` (directories)

**Interfaces:**
- Consumes: nothing.
- Produces: `m5_ver2/CLAUDE.md`, which every later task and every later step reads instead of re-deriving the PLC context.

- [ ] **Step 1: Write `m5_ver2/CLAUDE.md`**

It must contain three things and nothing else:

1. The **Global Constraints** section of this plan, as the working agreements.
2. The **entire** "PLC ground truth" section of the spec, verbatim — the platform paragraph, the pythonnet boilerplate, the three non-obvious simulation facts, the full tag table (all ten rows), and the safety-program behaviour bullets. Copy it from `docs/superpowers/specs/2026-08-11-m5ver2-step1-estop-chain-design.md` §3, do not paraphrase.
3. The port map:

```markdown
| Port | Direction | Payload | Step |
|---|---|---|---|
| 5100 | Windows -> WSL | PLC state JSON {"estop_healthy","motor","ts"} @ 20 Hz | Step 1 |
| 5101 | WSL -> Windows | simulated sensors (distance, speed) | later |
```

- [ ] **Step 2: Create the four directories**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
mkdir -p m5_ver2/step1/windows m5_ver2/step1/ros2 m5_ver2/step1/gazebo m5_ver2/step1/tests
```

- [ ] **Step 3: Verify the tag table survived the copy**

Run:
```bash
grep -c '%I0\.0\|%I0\.1\|%I0\.2\|%I15\.0\|%IW100\|%IW102\|%Q9\.0\|%Q9\.1\|%Q9\.2\|%MW100' m5_ver2/CLAUDE.md
```
Expected: `10`. A lower number means a tag row was dropped in the copy.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/CLAUDE.md
git commit -m "docs(m5_ver2): the context file every later step reads

Working agreements, the PLC ground truth verbatim and the port map, so no
later step has to re-derive the tag table or rediscover that API writes to
inputs persist across cycles."
```

---

### Task 2: `windows/step1.py` — the only PLC writer

**Files:**
- Create: `m5_ver2/step1/windows/step1.py`
- Test: `m5_ver2/step1/tests/conftest.py`, `m5_ver2/step1/tests/test_step1.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the UDP wire format that Task 3 parses — a JSON object with exactly the keys `estop_healthy` (bool), `motor` (bool), `ts` (float). Also produces the module-level pure functions `resolve_udp_target(configured)` and `status_payload(estop_healthy, motor, ts)`.

- [ ] **Step 1: Write `tests/conftest.py`**

```python
"""Put the node directories on sys.path so the tests can import them.

The Step 1 tree is deliberately not a package (m5_ver2/CLAUDE.md: no colcon
package, plain files run with python3), so there is nothing to install and
the tests reach the modules by path instead.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("ros2", "windows"):
    _path = os.path.normpath(os.path.join(_HERE, "..", _sub))
    if _path not in sys.path:
        sys.path.insert(0, _path)
```

- [ ] **Step 2: Write the failing test**

`m5_ver2/step1/tests/test_step1.py`:

```python
"""step1.py's pure functions. Nothing here opens the PLCSIM API."""
import json

import pytest

step1 = pytest.importorskip("step1")


def test_status_payload_has_exactly_the_three_wire_keys():
    raw = step1.status_payload(True, False, 12.5)
    msg = json.loads(raw.decode())
    assert set(msg) == {"estop_healthy", "motor", "ts"}
    assert msg["estop_healthy"] is True
    assert msg["motor"] is False
    assert msg["ts"] == 12.5


def test_status_payload_emits_real_json_booleans_not_strings():
    msg = json.loads(step1.status_payload(False, True, 0.0).decode())
    assert isinstance(msg["estop_healthy"], bool)
    assert isinstance(msg["motor"], bool)


def test_resolve_udp_target_honours_an_explicit_string():
    assert step1.resolve_udp_target("10.0.0.5") == "10.0.0.5"


def test_resolve_udp_target_takes_the_first_token_of_the_wsl_reply():
    # `wsl.exe hostname -I` answers with the eth0 address first and may
    # append the docker bridge. Only the first is reachable from Windows.
    assert step1._first_token("172.19.180.72 172.17.0.1 \n") == "172.19.180.72"


def test_first_token_rejects_empty_output():
    with pytest.raises(RuntimeError):
        step1._first_token("   \n")
```

- [ ] **Step 3: Run the test to verify it fails**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
python3 -m pytest m5_ver2/step1/tests/test_step1.py -v
```
Expected: collection is **skipped** (`importorskip`) because `step1.py` does not exist yet. That skip is the failing state for this task — once the file exists the tests run for real.

- [ ] **Step 4: Write `windows/step1.py`**

```python
"""step1.py - the ONLY process that writes to the safety PLC.

Runs on Windows, on 64-bit Python, against S7-PLCSIM Advanced instance
"PLC_2". Every 20 ms it writes the field-device picture the safety program
needs and reads back the one output that matters.

WHY PF_OSSD, WF_Clear AND THE ENCODERS ARE WRITTEN EVERY CYCLE
  Motor is the AND of three ESTOP1 enables. Two of them watch the
  protective field and the encoder cross-check, so unless this loop holds
  those healthy the drive enable can never energise, no matter what the
  e-stop button does. They are not Step 1's subject; they are its
  precondition.

THE FAIL DIRECTION
  Any exception, `q`, or Ctrl-C leaves through the same `finally`: E-Stop,
  PF_OSSD and WF_Clear are written False. The vehicle side then sees the
  link go quiet and fails safe on its own 0.5 s rule.

Usage (Windows, 64-bit Python, PLCSIM Advanced already in RUN):
  python m5_ver2\\step1\\windows\\step1.py
"""

import json
import socket
import subprocess
import sys
import threading
import time

# ----------------------------- CONFIG -----------------------------
PLC_INSTANCE = "PLC_2"
API_DLL_DIR = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0"
UDP_TARGET = None      # None -> ask `wsl.exe hostname -I`. A string overrides.
UDP_PORT = 5100
CYCLE_S = 0.02         # 20 ms
ACK_PULSE_S = 0.30
# ------------------------------------------------------------------


def _first_token(text):
    """First whitespace-separated token, which is the WSL eth0 address.

    `wsl.exe hostname -I` may append the docker bridge address; only the
    first one is reachable from Windows.
    """
    parts = text.split()
    if not parts:
        raise RuntimeError("`wsl.exe hostname -I` returned no address")
    return parts[0]


def resolve_udp_target(configured=UDP_TARGET):
    """The WSL guest IP, discovered rather than hard-coded.

    WSL2 here is NAT, not mirrored, so 127.0.0.1 does not reach the guest,
    and the guest's address is reassigned on every WSL restart. Discovering
    it each run is the difference between a script that works and one that
    breaks silently next week.
    """
    if configured:
        return configured
    out = subprocess.check_output(
        ["wsl.exe", "hostname", "-I"], text=True, timeout=10)
    return _first_token(out)


def status_payload(estop_healthy, motor, ts):
    """The wire format plc_link.py parses. Three keys, no more."""
    return json.dumps({
        "estop_healthy": bool(estop_healthy),
        "motor": bool(motor),
        "ts": float(ts),
    }).encode()


def connect_plc():
    """CreateInterface, with the -4 case reported rather than worked around."""
    sys.path.append(API_DLL_DIR)
    import clr
    clr.AddReference("Siemens.Simatic.Simulation.Runtime.Api.x64")
    from Siemens.Simatic.Simulation.Runtime import (
        SimulationRuntimeManager, ETagListDetails)
    try:
        plc = SimulationRuntimeManager.CreateInterface(PLC_INSTANCE)
    except Exception as exc:
        raise SystemExit(
            "Cannot reach PLCSIM Advanced instance '{}': {}\n"
            "If this is error -4 (DoesNotExist), the instance is not running "
            "or the name differs. Start it from the PLCSIM Advanced Control "
            "Panel and download the program from TIA Portal.".format(
                PLC_INSTANCE, exc))
    plc.UpdateTagList(ETagListDetails.IOM)
    return plc


def main():
    state = {"estop": True, "ack_until": 0.0, "run": True}

    def reader():
        print("commands: es0 (press e-stop) | es1 (release) | a (ack) | q")
        while state["run"]:
            try:
                cmd = input().strip().lower()
            except EOFError:
                state["run"] = False
                return
            if cmd == "es0":
                state["estop"] = False
            elif cmd == "es1":
                state["estop"] = True
            elif cmd == "a":
                state["ack_until"] = time.monotonic() + ACK_PULSE_S
            elif cmd == "q":
                state["run"] = False

    target = resolve_udp_target()
    print("streaming PLC state to {}:{}".format(target, UDP_PORT))
    plc = connect_plc()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    threading.Thread(target=reader, daemon=True).start()

    try:
        while state["run"]:
            now = time.monotonic()
            plc.WriteBool("PF_OSSD", True)
            plc.WriteBool("WF_Clear", True)
            plc.WriteInt16("ENC_A", 0)
            plc.WriteInt16("ENC_B", 0)
            plc.WriteBool("E-Stop", state["estop"])
            plc.WriteBool("Acknowledge", now < state["ack_until"])

            motor = plc.ReadBool("Motor")
            estop_healthy = plc.ReadBool("E-Stop")
            tx.sendto(status_payload(estop_healthy, motor, now),
                      (target, UDP_PORT))
            print("\rE-Stop={:<5} Motor={:<5} ack={:<5}   ".format(
                str(estop_healthy), str(motor), str(now < state["ack_until"])),
                end="", flush=True)
            time.sleep(CYCLE_S)
    finally:
        print("\nshutting down: writing the trip values")
        for tag in ("E-Stop", "PF_OSSD", "WF_Clear"):
            try:
                plc.WriteBool(tag, False)
            except Exception as exc:
                print("could not trip {}: {}".format(tag, exc))
        tx.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Run the tests to verify they pass**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
python3 -m pytest m5_ver2/step1/tests/test_step1.py -v
```
Expected: 5 passed. If they still skip, `conftest.py` is not putting `windows/` on the path.

- [ ] **Step 6: Prove the wire format reaches WSL**

This is an end-to-end check of Task 2's only external contract, and it does not need the PLC. In WSL:

```bash
python3 -c "
import socket, json
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind(('0.0.0.0', 5100)); s.settimeout(20)
d, a = s.recvfrom(256)
m = json.loads(d.decode())
assert set(m) == {'estop_healthy','motor','ts'}, m
print('OK', m, 'from', a)
"
```

Then, on Windows, with PLCSIM Advanced in RUN:

```
python m5_ver2\step1\windows\step1.py
```

Expected in WSL: `OK {'estop_healthy': True, 'motor': False, 'ts': ...} from ('172.19.176.1', ...)`.
Expected on Windows: a status line updating in place, `Motor=False` until `a` is typed once, then `Motor=True`.

If `Motor` never goes True after `a`, do not change this file — read `m5_ver2/CLAUDE.md`'s safety-program section and check `PF_OSSD`/`ENC_*` are being written.

- [ ] **Step 7: Commit**

```bash
git add m5_ver2/step1/windows/step1.py m5_ver2/step1/tests/conftest.py m5_ver2/step1/tests/test_step1.py
git commit -m "feat(m5_ver2): step1.py, the only writer to the safety PLC

20 ms loop holding the field-device picture the safety program needs, with
the e-stop and acknowledge under terminal control, streaming state to the
vehicle side over UDP 5100.

The UDP target is discovered from wsl.exe hostname -I rather than written
down: WSL2 here is NAT, so 127.0.0.1 does not reach the guest and the
guest's address changes on every restart."
```

---

### Task 3: `ros2/plc_link.py` — the vehicle side of the link

**Files:**
- Create: `m5_ver2/step1/ros2/plc_link.py`
- Test: `m5_ver2/step1/tests/test_plc_link.py`

**Interfaces:**
- Consumes: the UDP wire format from Task 2 — `{"estop_healthy": bool, "motor": bool, "ts": float}` on port 5100.
- Produces: `/plc/status` (`std_msgs/String`, the same three-key JSON) and the torque-off demand (`std_msgs/Bool`, `not motor`) on `topics.safety_torque_off_demand`. Also the module-level pure functions `parse_status(data)`, `is_stale(last_rx_s, now_s, stale_s)` and the constant `FAILSAFE`.

- [ ] **Step 1: Write the failing test**

`m5_ver2/step1/tests/test_plc_link.py`:

```python
"""plc_link.py's pure functions. No ROS graph is started."""
import pytest

plc_link = pytest.importorskip("plc_link")


def test_parse_status_reads_a_good_packet():
    msg = plc_link.parse_status(b'{"estop_healthy": true, "motor": true, "ts": 3.0}')
    assert msg == {"estop_healthy": True, "motor": True, "ts": 3.0}


def test_parse_status_rejects_malformed_json():
    assert plc_link.parse_status(b'{not json') is None


def test_parse_status_rejects_a_packet_missing_a_required_key():
    # A truncated or future-format packet must not be read as healthy.
    assert plc_link.parse_status(b'{"estop_healthy": true}') is None


def test_failsafe_is_tripped_in_both_fields():
    assert plc_link.FAILSAFE["estop_healthy"] is False
    assert plc_link.FAILSAFE["motor"] is False


def test_is_stale_is_false_inside_the_window():
    assert plc_link.is_stale(10.0, 10.4, 0.5) is False


def test_is_stale_is_true_at_the_window():
    assert plc_link.is_stale(10.0, 10.5, 0.5) is True


def test_is_stale_is_true_before_the_first_packet():
    # last_rx of None means nothing has ever arrived.
    assert plc_link.is_stale(None, 10.0, 0.5) is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/test_plc_link.py -v
```
Expected: skipped, because `plc_link.py` does not exist.

- [ ] **Step 3: Write `ros2/plc_link.py`**

```python
"""plc_link.py - the vehicle side of the PLC link.

Binds UDP :5100, republishes what step1.py sends as two ROS topics:

    /plc/status                            std_msgs/String  (the JSON)
    topics.safety_torque_off_demand        std_msgs/Bool    (= not motor)

WHY IT NEVER GOES QUIET
  sto_contactor.py latches on an OBSERVED True and releases on an OBSERVED
  False, so a demand link that stops speaking leaves the contactor closed.
  That is correct in its own layer - it refuses to put a safety reaction on
  network silence - but it means the failure has to be SAID rather than
  implied. So when the link goes stale this node keeps publishing at 20 Hz,
  with motor False and the demand True. Silence here would be a moving
  vehicle.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step1/ros2/plc_link.py
"""

import json
import os
import socket
import time

import rclpy
import yaml
from rclpy.node import Node
from std_msgs.msg import Bool, String

# ----------------------------- CONFIG -----------------------------
BIND_ADDR = "0.0.0.0"
UDP_PORT = 5100
STALE_S = 0.5
PUBLISH_HZ = 20.0
STATUS_TOPIC = "/plc/status"
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))

_REQUIRED_KEYS = {"estop_healthy", "motor", "ts"}

#: What the vehicle is told when the link is stale or has never spoken.
FAILSAFE = {"estop_healthy": False, "motor": False, "ts": 0.0}


def parse_status(data):
    """Decode one datagram, or None if it is not a packet we trust.

    A packet missing a key is rejected rather than defaulted: defaulting
    `motor` would be inventing an enable.
    """
    try:
        msg = json.loads(data.decode())
    except (ValueError, UnicodeDecodeError):
        return None
    if not isinstance(msg, dict) or not _REQUIRED_KEYS.issubset(msg):
        return None
    return msg


def is_stale(last_rx_s, now_s, stale_s=STALE_S):
    """True when nothing has arrived within the window, or ever."""
    if last_rx_s is None:
        return True
    return (now_s - last_rx_s) >= stale_s


def load_topics(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)["topics"]


class PlcLink(Node):

    def __init__(self):
        super().__init__("plc_link")
        topics = load_topics()
        self.pub_status = self.create_publisher(String, STATUS_TOPIC, 10)
        self.pub_demand = self.create_publisher(
            Bool, topics["safety_torque_off_demand"], 10)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((BIND_ADDR, UDP_PORT))
        self.sock.setblocking(False)

        self.last_rx = None
        self.last_msg = dict(FAILSAFE)
        self.create_timer(1.0 / PUBLISH_HZ, self.tick)
        self.get_logger().info(
            "bound {}:{}, publishing {} and {}".format(
                BIND_ADDR, UDP_PORT, STATUS_TOPIC,
                topics["safety_torque_off_demand"]))

    def drain(self):
        """Take the newest datagram and discard any backlog."""
        newest = None
        while True:
            try:
                data = self.sock.recv(512)
            except BlockingIOError:
                break
            parsed = parse_status(data)
            if parsed is not None:
                newest = parsed
        return newest

    def tick(self):
        now = time.monotonic()
        fresh = self.drain()
        if fresh is not None:
            self.last_msg, self.last_rx = fresh, now
        if is_stale(self.last_rx, now):
            self.last_msg = dict(FAILSAFE)

        self.pub_status.publish(String(data=json.dumps(self.last_msg)))
        self.pub_demand.publish(Bool(data=not self.last_msg["motor"]))


def main():
    rclpy.init()
    node = PlcLink()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/test_plc_link.py -v
```
Expected: 7 passed.

- [ ] **Step 5: Prove it fails safe with no sender**

Terminal A:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 m5_ver2/step1/ros2/plc_link.py
```

Terminal B:
```bash
source /opt/ros/jazzy/setup.bash
timeout 3 ros2 topic echo /forklift/safety/torque_off_demand
```
Expected: a stream of `data: true` — nothing is sending, so the demand is asserted.

Then, with Terminal A still running, send one healthy packet from Terminal B and watch the demand drop for half a second:
```bash
python3 -c "
import socket, json, time
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
for _ in range(40):
    s.sendto(json.dumps({'estop_healthy': True, 'motor': True, 'ts': 0.0}).encode(),
             ('127.0.0.1', 5100))
    time.sleep(0.02)
"
```
Expected: `data: false` while the loop runs, `data: true` within 0.5 s of it stopping.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step1/ros2/plc_link.py m5_ver2/step1/tests/test_plc_link.py
git commit -m "feat(m5_ver2): plc_link.py, the vehicle side of the PLC link

Republishes the UDP state as /plc/status and as the torque-off demand the
STO contactor consumes.

It keeps publishing when the link goes stale rather than falling silent.
The contactor latches on an observed True, so an unspoken failure would
leave the plant enabled - the failure has to be said out loud."
```

---

### Task 4: `ros2/cmd_gate.py` — the enable gate

**Files:**
- Create: `m5_ver2/step1/ros2/cmd_gate.py`
- Test: `m5_ver2/step1/tests/test_cmd_gate.py`

**Interfaces:**
- Consumes: `/hmi/cmd_vel` (`geometry_msgs/Twist`, produced by Task 5) and `/plc/status` (`std_msgs/String`, produced by Task 3). Reuses `plc_link.parse_status` and `plc_link.is_stale` by import — they are the same two decisions and must not be written twice.
- Produces: `topics.cmd_traction_speed` and `topics.cmd_steer_angle` (`std_msgs/Float64`), which `forklift_io.py` consumes. Also the module-level pure function `gated_command(linear_x, angular_z, motor_ok, speed_max, steer_max)` returning `(traction_mps, steer_rad)`.

- [ ] **Step 1: Write the failing test**

`m5_ver2/step1/tests/test_cmd_gate.py`:

```python
"""cmd_gate.py's gate decision. No ROS graph is started."""
import pytest

cmd_gate = pytest.importorskip("cmd_gate")

SPEED_MAX = 1.50
STEER_MAX = 1.31


def test_enabled_gate_passes_a_command_through():
    assert cmd_gate.gated_command(
        0.8, 0.4, True, SPEED_MAX, STEER_MAX) == (0.8, 0.4)


def test_inhibited_gate_zeroes_both_axes():
    assert cmd_gate.gated_command(
        0.8, 0.4, False, SPEED_MAX, STEER_MAX) == (0.0, 0.0)


def test_inhibited_gate_zeroes_steer_as_well_as_traction():
    # Steering a truck that is not allowed to move is still motion at the
    # steer joint, and the brief's zero is a zero Twist, not a zero speed.
    _, steer = cmd_gate.gated_command(0.0, 1.31, False, SPEED_MAX, STEER_MAX)
    assert steer == 0.0


def test_speed_is_clamped_to_the_vehicle_limit():
    traction, _ = cmd_gate.gated_command(9.0, 0.0, True, SPEED_MAX, STEER_MAX)
    assert traction == SPEED_MAX


def test_reverse_speed_is_clamped_symmetrically():
    traction, _ = cmd_gate.gated_command(-9.0, 0.0, True, SPEED_MAX, STEER_MAX)
    assert traction == -SPEED_MAX


def test_steer_is_clamped_to_the_mechanical_stop():
    _, steer = cmd_gate.gated_command(0.0, 5.0, True, SPEED_MAX, STEER_MAX)
    assert steer == STEER_MAX


def test_clamp_is_symmetric_and_leaves_interior_values_alone():
    assert cmd_gate.clamp(0.5, 1.31) == 0.5
    assert cmd_gate.clamp(-0.5, 1.31) == -0.5
    assert cmd_gate.clamp(2.0, 1.31) == 1.31
    assert cmd_gate.clamp(-2.0, 1.31) == -1.31


def test_motor_is_read_out_of_the_status_json():
    assert cmd_gate.motor_from_status(
        '{"estop_healthy": true, "motor": true, "ts": 1.0}') is True
    assert cmd_gate.motor_from_status(
        '{"estop_healthy": true, "motor": false, "ts": 1.0}') is False


def test_unparseable_status_is_read_as_inhibited():
    assert cmd_gate.motor_from_status("{garbage") is False
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/test_cmd_gate.py -v
```
Expected: skipped, because `cmd_gate.py` does not exist.

- [ ] **Step 3: Write `ros2/cmd_gate.py`**

```python
"""cmd_gate.py - stage 1 of the stop: the command is zeroed.

Forwards the HMI joystick to the vehicle's engineering-unit command topics
while the safety program says Motor, and publishes continuous zeros when it
does not.

CONTINUOUS ZEROS, NOT ONE ZERO
  A single zero leaves a simulated vehicle coasting: forklift_io.py
  republishes steer and traction on receipt only, so one zero is one
  message and then silence. The gate therefore keeps publishing zeros at
  10 Hz for as long as the inhibit lasts.

THE /hmi/cmd_vel FIELD CONTRACT, WHICH IS NOT STANDARD Twist
  linear.x   traction speed  [m/s]   +-1.50  (limits.traction_speed_max_mps)
  angular.z  STEER ANGLE     [rad]   +-1.31  (model.steer_limit_rad)

  angular.z carries an ANGLE, not a yaw rate. The bicycle relation the
  nav2-era converter uses, delta = atan(L*w/v), is undefined at v = 0, and
  a forklift that cannot be steered while stopped would make an e-stop
  test ambiguous: the operator could not tell a safety stop from a dead
  joystick. Step 1 needs steering visibly alive while traction is
  inhibited, so the angle is commanded directly and no geometry is
  computed anywhere in this file.

THIS IS NOT THE ONLY INTERLOCK, AND NOT THE LAST ONE
  sto_contactor.py removes torque at the plant's own inputs and cannot be
  bypassed by any ROS publisher. This gate is the controlled stop above it.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m5_ver2/step1/ros2/cmd_gate.py
"""

import os

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import Float64, String

import plc_link

# ----------------------------- CONFIG -----------------------------
ZERO_HZ = 10.0
HMI_TOPIC = "/hmi/cmd_vel"
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))


def clamp(value, limit):
    """Symmetric clamp to +-limit."""
    return max(-limit, min(limit, value))


def gated_command(linear_x, angular_z, motor_ok, speed_max, steer_max):
    """The whole gate decision: (traction [m/s], steer [rad])."""
    if not motor_ok:
        return (0.0, 0.0)
    return (clamp(linear_x, speed_max), clamp(angular_z, steer_max))


def motor_from_status(json_text):
    """Read `motor` out of a /plc/status payload. Anything unreadable is
    inhibited: a gate that cannot understand the PLC does not pass."""
    msg = plc_link.parse_status(json_text.encode())
    if msg is None:
        return False
    return bool(msg["motor"])


def load_config(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class CmdGate(Node):

    def __init__(self):
        super().__init__("cmd_gate")
        cfg = load_config()
        topics = cfg["topics"]
        self.speed_max = float(cfg["limits"]["traction_speed_max_mps"])
        self.steer_max = float(cfg["model"]["steer_limit_rad"])

        self.pub_traction = self.create_publisher(
            Float64, topics["cmd_traction_speed"], 10)
        self.pub_steer = self.create_publisher(
            Float64, topics["cmd_steer_angle"], 10)

        # A gate that has not heard from the PLC does not pass a command.
        self.motor_ok = False
        self.cmd = (0.0, 0.0)

        self.create_subscription(String, "/plc/status", self.cb_status, 10)
        self.create_subscription(Twist, HMI_TOPIC, self.cb_cmd, 10)
        self.create_timer(1.0 / ZERO_HZ, self.tick)
        self.get_logger().info(
            "speed limit {:.2f} m/s, steer stop +-{:.2f} rad".format(
                self.speed_max, self.steer_max))

    def cb_status(self, msg):
        was = self.motor_ok
        self.motor_ok = motor_from_status(msg.data)
        if was != self.motor_ok:
            self.get_logger().info(
                "drive enable {}".format("ON" if self.motor_ok else "OFF"))

    def cb_cmd(self, msg):
        self.cmd = (msg.linear.x, msg.angular.z)
        self.publish()

    def tick(self):
        """The 10 Hz floor. While inhibited this is what keeps the zeros
        coming; while enabled cb_cmd publishes faster and this is harmless."""
        if not self.motor_ok:
            self.publish()

    def publish(self):
        traction, steer = gated_command(
            self.cmd[0], self.cmd[1], self.motor_ok,
            self.speed_max, self.steer_max)
        self.pub_traction.publish(Float64(data=traction))
        self.pub_steer.publish(Float64(data=steer))


def main():
    rclpy.init()
    node = CmdGate()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/test_cmd_gate.py -v
```
Expected: 9 passed.

- [ ] **Step 5: Prove the gate blocks and passes on a live graph**

Terminal A:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 m5_ver2/step1/ros2/cmd_gate.py
```

Terminal B — publish a command with no PLC status at all:
```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub -r 20 /hmi/cmd_vel geometry_msgs/msg/Twist \
  '{linear: {x: 1.0}, angular: {z: 0.5}}' &
timeout 3 ros2 topic echo /forklift/cmd/traction_speed
```
Expected: `data: 0.0` throughout. No PLC, no motion.

Terminal C — now say the PLC is enabled:
```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub -r 20 /plc/status std_msgs/msg/String \
  '{data: "{\"estop_healthy\": true, \"motor\": true, \"ts\": 1.0}"}' &
timeout 3 ros2 topic echo /forklift/cmd/traction_speed
```
Expected: `data: 1.0`. Kill the `/plc/status` publisher and confirm it returns to `0.0`.

Clean up: `kill %1` in each terminal that backgrounded a publisher.

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step1/ros2/cmd_gate.py m5_ver2/step1/tests/test_cmd_gate.py
git commit -m "feat(m5_ver2): cmd_gate.py, stage one of the stop

Forwards the joystick while the safety program says Motor and publishes
continuous zeros when it does not - continuous, because forklift_io
republishes on receipt only and a single zero would leave the truck
coasting.

angular.z carries a steer ANGLE rather than a yaw rate, so the truck can
be steered while stopped. Under the bicycle relation delta is undefined at
v=0, and a dead joystick during an e-stop test cannot be told apart from
the stop itself."
```

---

### Task 5: `ros2/hmi_node.py` — joystick and lamp

**Files:**
- Create: `m5_ver2/step1/ros2/hmi_node.py`
- Test: `m5_ver2/step1/tests/test_hmi_node.py`

**Interfaces:**
- Consumes: `/plc/status` (`std_msgs/String`, from Task 3).
- Produces: `/hmi/cmd_vel` (`geometry_msgs/Twist`) at 20 Hz, in the field contract Task 4 consumes. Also the module-level pure functions `knob_to_twist(dx, dy, radius, speed_max, steer_max)`, `lamp_state(estop_healthy)` and `enable_text(motor)`.

- [ ] **Step 1: Write the failing test**

`m5_ver2/step1/tests/test_hmi_node.py`:

```python
"""hmi_node.py's mapping and labels. No window is opened."""
import pytest

hmi_node = pytest.importorskip("hmi_node")

R = 100.0
SPEED_MAX = 1.50
STEER_MAX = 1.31


def test_centre_is_a_full_stop():
    assert hmi_node.knob_to_twist(0.0, 0.0, R, SPEED_MAX, STEER_MAX) == (0.0, 0.0)


def test_dragging_up_drives_forward():
    # Canvas y grows DOWNWARD, so "up" is a negative dy.
    linear, _ = hmi_node.knob_to_twist(0.0, -R, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(SPEED_MAX)


def test_dragging_down_drives_in_reverse():
    linear, _ = hmi_node.knob_to_twist(0.0, R, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(-SPEED_MAX)


def test_dragging_right_steers_right_which_is_negative_z():
    # REP-103: positive z is counter-clockwise, so a right turn is negative.
    _, angular = hmi_node.knob_to_twist(R, 0.0, R, SPEED_MAX, STEER_MAX)
    assert angular == pytest.approx(-STEER_MAX)


def test_dragging_left_steers_left_which_is_positive_z():
    _, angular = hmi_node.knob_to_twist(-R, 0.0, R, SPEED_MAX, STEER_MAX)
    assert angular == pytest.approx(STEER_MAX)


def test_a_drag_beyond_the_ring_saturates_rather_than_exceeding():
    linear, angular = hmi_node.knob_to_twist(
        5 * R, -5 * R, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(SPEED_MAX)
    assert angular == pytest.approx(-STEER_MAX)


def test_half_deflection_is_half_command():
    linear, _ = hmi_node.knob_to_twist(0.0, -R / 2, R, SPEED_MAX, STEER_MAX)
    assert linear == pytest.approx(SPEED_MAX / 2)


def test_lamp_is_red_and_says_active_when_the_chain_is_broken():
    colour, text = hmi_node.lamp_state(False)
    assert text == "E-Stop Active"
    assert colour == hmi_node.LAMP_RED


def test_lamp_is_neutral_and_says_inactive_when_the_chain_is_healthy():
    colour, text = hmi_node.lamp_state(True)
    assert text == "E-Stop Inactive"
    assert colour == hmi_node.LAMP_NEUTRAL


def test_the_enable_line_is_separate_from_the_lamp():
    # The latch is exactly the state where these two disagree, and showing
    # that disagreement is a Step 1 goal.
    assert hmi_node.enable_text(True) == "Drive enable: ON"
    assert hmi_node.enable_text(False) == "Drive enable: OFF"
```

- [ ] **Step 2: Run the test to verify it fails**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/test_hmi_node.py -v
```
Expected: skipped, because `hmi_node.py` does not exist.

- [ ] **Step 3: Write `ros2/hmi_node.py`**

```python
"""hmi_node.py - the operator's window: a joystick and an e-stop lamp.

THE LAMP AND THE ENABLE LINE ARE SEPARATE, AND THAT IS THE POINT
  The lamp reads the e-stop chain; the line under it reads the drive
  enable. After a release without an acknowledge they DISAGREE - lamp
  inactive, enable OFF - and that disagreement IS the ESTOP1 latch. Making
  it visible is a Step 1 goal, not a display quirk.

THE FIELD CONTRACT ON /hmi/cmd_vel, WHICH IS NOT STANDARD Twist
  linear.x   traction speed  [m/s]   +-1.50  (limits.traction_speed_max_mps)
  angular.z  STEER ANGLE     [rad]   +-1.31  (model.steer_limit_rad)

  See cmd_gate.py for why an angle and not a yaw rate.

Usage (after sourcing /opt/ros/jazzy/setup.bash; WSLg provides DISPLAY):
  python3 m5_ver2/step1/ros2/hmi_node.py
"""

import json
import math
import os
import tkinter as tk

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from std_msgs.msg import String

# ----------------------------- CONFIG -----------------------------
PUBLISH_HZ = 20.0
SPIN_MS = 20              # tkinter's after() period for pumping rclpy
KNOB_RADIUS_PX = 100.0
HMI_TOPIC = "/hmi/cmd_vel"
LAMP_RED = "#c62828"
LAMP_NEUTRAL = "#455a64"
# ------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_YAML = os.path.normpath(
    os.path.join(_HERE, "..", "..", "..", "agv", "forklift", "config.yaml"))


def knob_to_twist(dx, dy, radius, speed_max, steer_max):
    """Knob offset in pixels -> (linear.x [m/s], angular.z [rad]).

    Canvas y grows downward, so dragging up is a negative dy and has to be
    negated to mean forward. Dragging right steers right, which is a
    NEGATIVE angular.z under REP-103 (positive z is counter-clockwise).
    """
    nx = max(-1.0, min(1.0, dx / radius))
    ny = max(-1.0, min(1.0, dy / radius))
    return (-ny * speed_max, -nx * steer_max)


def lamp_state(estop_healthy):
    """(colour, text) for the lamp. Healthy is not an alarm colour."""
    if estop_healthy:
        return (LAMP_NEUTRAL, "E-Stop Inactive")
    return (LAMP_RED, "E-Stop Active")


def enable_text(motor):
    return "Drive enable: {}".format("ON" if motor else "OFF")


def load_config(path=CONFIG_YAML):
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


class Hmi(Node):

    def __init__(self, root):
        super().__init__("hmi_node")
        cfg = load_config()
        self.speed_max = float(cfg["limits"]["traction_speed_max_mps"])
        self.steer_max = float(cfg["model"]["steer_limit_rad"])

        self.pub = self.create_publisher(Twist, HMI_TOPIC, 10)
        self.create_subscription(String, "/plc/status", self.cb_status, 10)
        self.knob = (0.0, 0.0)
        self.create_timer(1.0 / PUBLISH_HZ, self.publish)

        self.root = root
        root.title("Step 1 - forklift teleoperation")
        cx = cy = KNOB_RADIUS_PX + 20

        self.canvas = tk.Canvas(root, width=2 * cx, height=2 * cy,
                                bg="#eceff1", highlightthickness=0)
        self.canvas.pack(padx=10, pady=10)
        self.canvas.create_oval(cx - KNOB_RADIUS_PX, cy - KNOB_RADIUS_PX,
                                cx + KNOB_RADIUS_PX, cy + KNOB_RADIUS_PX,
                                outline="#90a4ae", width=2)
        self.dot = self.canvas.create_oval(cx - 14, cy - 14, cx + 14, cy + 14,
                                           fill="#37474f", outline="")
        self.centre = (cx, cy)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        self.lamp = tk.Label(root, text="E-Stop Inactive", fg="white",
                             bg=LAMP_NEUTRAL, font=("TkDefaultFont", 16, "bold"),
                             padx=16, pady=10)
        self.lamp.pack(fill="x", padx=10)
        self.enable = tk.Label(root, text=enable_text(False),
                               font=("TkDefaultFont", 11))
        self.enable.pack(pady=(6, 12))

    def on_drag(self, event):
        cx, cy = self.centre
        dx, dy = event.x - cx, event.y - cy
        dist = math.hypot(dx, dy)
        if dist > KNOB_RADIUS_PX:               # keep the dot on the ring
            dx, dy = dx * KNOB_RADIUS_PX / dist, dy * KNOB_RADIUS_PX / dist
        self.knob = (dx, dy)
        self.canvas.coords(self.dot, cx + dx - 14, cy + dy - 14,
                           cx + dx + 14, cy + dy + 14)

    def on_release(self, _event):
        """Release snaps to centre and the next publish is a zero."""
        cx, cy = self.centre
        self.knob = (0.0, 0.0)
        self.canvas.coords(self.dot, cx - 14, cy - 14, cx + 14, cy + 14)

    def cb_status(self, msg):
        try:
            state = json.loads(msg.data)
        except ValueError:
            state = {"estop_healthy": False, "motor": False}
        colour, text = lamp_state(bool(state.get("estop_healthy")))
        self.lamp.configure(bg=colour, text=text)
        self.enable.configure(text=enable_text(bool(state.get("motor"))))

    def publish(self):
        linear, angular = knob_to_twist(
            self.knob[0], self.knob[1], KNOB_RADIUS_PX,
            self.speed_max, self.steer_max)
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = angular
        self.pub.publish(msg)


def main():
    rclpy.init()
    root = tk.Tk()
    node = Hmi(root)

    def pump():
        rclpy.spin_once(node, timeout_sec=0.0)
        root.after(SPIN_MS, pump)

    root.after(SPIN_MS, pump)
    try:
        root.mainloop()
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/test_hmi_node.py -v
```
Expected: 10 passed.

- [ ] **Step 5: Open the window and check the lamp both ways**

Terminal A:
```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 m5_ver2/step1/ros2/hmi_node.py
```
Expected: a window with a joystick ring, a neutral lamp reading "E-Stop Inactive", and "Drive enable: OFF" under it.

Terminal B:
```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub -r 5 /plc/status std_msgs/msg/String \
  '{data: "{\"estop_healthy\": false, \"motor\": false, \"ts\": 1.0}"}'
```
Expected: the lamp turns red and reads "E-Stop Active". Ctrl-C, then republish with `estop_healthy: true, motor: false` and confirm the lamp goes neutral **while the enable line stays OFF** — that is the latch display working.

Drag the knob and confirm `/hmi/cmd_vel` moves:
```bash
timeout 3 ros2 topic echo /hmi/cmd_vel
```

- [ ] **Step 6: Commit**

```bash
git add m5_ver2/step1/ros2/hmi_node.py m5_ver2/step1/tests/test_hmi_node.py
git commit -m "feat(m5_ver2): hmi_node.py, the joystick and the e-stop lamp

The lamp reads the chain and the line under it reads the drive enable.
They disagree exactly when the ESTOP1 latch is holding - released but not
acknowledged - and showing that disagreement is the point of the window."
```

---

### Task 6: `gazebo/step1_world.launch.py` — the simulation

**Files:**
- Create: `m5_ver2/step1/gazebo/step1_world.launch.py`

**Interfaces:**
- Consumes: `topics.cmd_traction_speed` and `topics.cmd_steer_angle` from Task 4, via `forklift_io.py`; and the torque-off demand from Task 3, via `sto_contactor.py`.
- Produces: a running `warehouse` world with the forklift spawned, the actuator terminals bridged into gz, and `topics.safety_torque_off_applied` published.

- [ ] **Step 1: Write `gazebo/step1_world.launch.py`**

```python
"""step1_world.launch.py - the plant, and only the plant.

Five processes: the world server, one spawn, one bridge, the unit
translator and the STO contactor.

WHY NOT agv/forklift/launch/vehicle.launch.py
  That file also starts safe_speed_link.py, field_evaluation.py,
  obstacle_zone.py and the EKF - the old M5 OPC UA safety path. Running it
  would put a second process on the PLC and break the single-writer rule.
  Its arguments could switch most of that off, but Step 1's isolation would
  then rest on a dozen toggles being right.

WHY THE BRIDGE CARRIES THE ACTUATOR TERMINALS AND NOT THE COMMAND TOPICS
  model.sdf's joint controllers listen on /forklift/gz/actuator/*_cmd, and
  sto_contactor.py is the only publisher of those. Bridging the terminals
  puts the contactor INSIDE the path rather than beside it: with its latch
  open, nothing any ROS publisher does reaches the plant.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  ros2 launch m5_ver2/step1/gazebo/step1_world.launch.py
"""

import os
import sys

import yaml
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))

_WORLD = os.path.join(_REPO, "sim", "worlds", "warehouse.sdf")
_MODEL = os.path.join(_REPO, "agv", "forklift", "model.sdf")
_CONFIG = os.path.join(_REPO, "agv", "forklift", "config.yaml")
_SCRIPTS = os.path.join(_REPO, "agv", "forklift", "scripts")
_IO_SCRIPT = os.path.join(_SCRIPTS, "forklift_io.py")
_STO_SCRIPT = os.path.join(_SCRIPTS, "sto_contactor.py")

# sim/worlds/warehouse.sdf line 206, and the spawn pose that
# sim/launch/warehouse_bringup.launch.py declares (lines 229-232).
_WORLD_NAME = "warehouse"
_SPAWN = {"x": "-3.00", "y": "-5.50", "z": "0.05", "yaw": "0.0"}

with open(_CONFIG, "r", encoding="utf-8") as _handle:
    _TOPICS = yaml.safe_load(_handle)["topics"]

# '[' gz to ROS, ']' ROS to gz.
_BRIDGE_ARGS = [
    "{}@rosgraph_msgs/msg/Clock[gz.msgs.Clock".format(_TOPICS["clock"]),
    "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
        _TOPICS["gz_actuator_steer_cmd"]),
    "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
        _TOPICS["gz_actuator_traction_cmd"]),
]


def generate_launch_description():
    ld = LaunchDescription()

    # --headless-rendering is the honest flag here: -s alone still opens a
    # GLX connection when DISPLAY is set (sim/setup/WSL_ENVIRONMENT.md 4.7).
    ld.add_action(ExecuteProcess(
        cmd=["gz", "sim", "-s", "-r", "--headless-rendering", "-v", "2", _WORLD],
        name="gz_server",
        output="screen",
    ))

    ld.add_action(Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_forklift",
        output="screen",
        arguments=[
            "-world", _WORLD_NAME,
            "-file", _MODEL,
            "-name", "forklift",
            "-x", _SPAWN["x"],
            "-y", _SPAWN["y"],
            "-z", _SPAWN["z"],
            "-Y", _SPAWN["yaw"],
            "-allow_renaming", "false",
        ],
    ))

    ld.add_action(Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="step1_bridge",
        output="screen",
        arguments=_BRIDGE_ARGS,
    ))

    # The two reused vehicle nodes, started exactly as
    # agv/forklift/launch/vehicle.launch.py starts them - the contactor
    # carries use_sim_time, forklift_io does not.
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _STO_SCRIPT, "--config", _CONFIG,
             "--ros-args", "-p", "use_sim_time:=true"],
        name="sto_contactor",
        output="screen",
    ))
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _IO_SCRIPT, "--config", _CONFIG],
        name="forklift_io",
        output="screen",
    ))

    return ld
```

- [ ] **Step 2: Launch it and confirm the world and the forklift came up**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step1 ROS_DOMAIN_ID=91
ros2 launch m5_ver2/step1/gazebo/step1_world.launch.py
```
Expected in the log: `Loading SDF world file[.../sim/worlds/warehouse.sdf]`, then the spawn succeeding. A log full of X-display exceptions is normal here and is not a fault.

- [ ] **Step 3: Confirm the contactor is publishing the terminals**

In a second shell with the same `GZ_PARTITION` and `ROS_DOMAIN_ID`:
```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step1 ROS_DOMAIN_ID=91
ros2 topic list | grep -E 'actuator|torque_off'
gz topic -l | grep actuator
```
Expected: `/forklift/gz/actuator/steer_cmd`, `/forklift/gz/actuator/traction_cmd`, `/forklift/safety/torque_off_applied` and `/forklift/safety/torque_off_demand` on the ROS side, and the two actuator topics on the gz side.

- [ ] **Step 4: Drive it by hand, with no gate and no PLC**

This is the **positive control**. Without it, "the forklift did not move" has two causes and stillness cannot tell them apart.

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step1 ROS_DOMAIN_ID=91
ros2 topic pub -r 20 /forklift/safety/torque_off_demand std_msgs/msg/Bool '{data: false}' &
ros2 topic pub -r 20 /forklift/cmd/traction_speed std_msgs/msg/Float64 '{data: 0.4}' &
sleep 5
gz topic -e -t /world/warehouse/pose/info -n 1 | grep -A3 'name: "forklift"'
kill %1 %2
```
Expected: the forklift's x/y has changed from the spawn pose. If it has not, stop and fix this before Task 7 — every later test depends on the truck being able to move at all.

- [ ] **Step 5: Commit**

```bash
git add m5_ver2/step1/gazebo/step1_world.launch.py
git commit -m "feat(m5_ver2): step1_world.launch.py, the plant and only the plant

Five processes: world, spawn, bridge, unit translator, STO contactor. The
bridge carries the actuator terminals rather than the command topics, which
is what puts the contactor inside the command path instead of beside it.

Every topic name is read from agv/forklift/config.yaml; none is a literal."
```

---

### Task 7: `step1.sh` — one command up, one command down

**Files:**
- Create: `m5_ver2/step1/step1.sh`

**Interfaces:**
- Consumes: every file from Tasks 3 to 6.
- Produces: `m5_ver2/step1/.step1_pids`, and a running stack of the launch plus the three Step 1 nodes.

- [ ] **Step 1: Write `step1.sh`**

```bash
#!/usr/bin/env bash
# step1.sh - bring the Step 1 vehicle side up and down.
#
# It does NOT touch PLCSIM Advanced or step1.py. Those are the owner's, on
# the Windows side, and the single-writer rule is the reason this script
# has no way to start them.
#
# GZ_PARTITION and ROS_DOMAIN_ID are set on every child so a concurrent M5
# demo cannot be joined by accident. A shared graph would put the old
# stack's publishers on the same command topics as this one.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STEP1="$REPO/m5_ver2/step1"
PIDFILE="$STEP1/.step1_pids"
LOGDIR="$STEP1/logs"
ROS_SETUP="/opt/ros/jazzy/setup.bash"

export GZ_PARTITION="${GZ_PARTITION:-step1}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-91}"

start() {
    if [ -f "$PIDFILE" ] && kill -0 $(head -1 "$PIDFILE") 2>/dev/null; then
        echo "already running (see $PIDFILE). Run '$0 stop' first."
        return 1
    fi
    [ -f "$ROS_SETUP" ] || { echo "no $ROS_SETUP"; return 1; }
    mkdir -p "$LOGDIR"
    : > "$PIDFILE"

    # shellcheck disable=SC1090
    source "$ROS_SETUP"

    spawn() {
        local name="$1"; shift
        "$@" > "$LOGDIR/$name.log" 2>&1 &
        echo "$!" >> "$PIDFILE"
        echo "  $name pid $!"
    }

    echo "starting the Step 1 vehicle side (partition $GZ_PARTITION, domain $ROS_DOMAIN_ID)"
    spawn world  ros2 launch "$STEP1/gazebo/step1_world.launch.py"
    sleep 5
    spawn plc_link python3 "$STEP1/ros2/plc_link.py"
    spawn cmd_gate python3 "$STEP1/ros2/cmd_gate.py"
    spawn hmi      python3 "$STEP1/ros2/hmi_node.py"

    echo
    echo "up. Now start PLCSIM Advanced instance PLC_2, then on Windows:"
    echo "  python m5_ver2\\step1\\windows\\step1.py"
    echo "logs: $LOGDIR"
}

stop() {
    if [ ! -f "$PIDFILE" ]; then
        echo "nothing to stop."
    else
        while read -r pid; do
            [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "  killed $pid"
        done < "$PIDFILE"
        rm -f "$PIDFILE"
        sleep 2
    fi

    # ros2 launch does not bring its children down when signalled, so the
    # survivors are swept by name. Every pattern here is a process THIS
    # script starts; nothing else in the repo is matched.
    for pat in "step1_world.launch.py" "gz sim" "parameter_bridge" \
               "forklift_io.py" "sto_contactor.py" \
               "plc_link.py" "cmd_gate.py" "hmi_node.py"; do
        pkill -f "$pat" 2>/dev/null && echo "  swept $pat"
    done
    echo "down."
}

case "${1:-}" in
    start|--start) start ;;
    stop|--stop)   stop ;;
    *) echo "usage: $0 start|stop"; exit 2 ;;
esac
```

- [ ] **Step 2: Make it executable and check it parses**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
chmod +x m5_ver2/step1/step1.sh
bash -n m5_ver2/step1/step1.sh && echo "SYNTAX OK"
```
Expected: `SYNTAX OK`. If it reports `syntax error near unexpected token $'do\r'`, the file was checked out CRLF — the repo `.gitattributes` should prevent that; fix the checkout, not the file.

- [ ] **Step 3: Test start, double start, stop, double stop**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
./m5_ver2/step1/step1.sh start
./m5_ver2/step1/step1.sh start        # expect: "already running", exit non-zero
./m5_ver2/step1/step1.sh stop
./m5_ver2/step1/step1.sh stop         # expect: "nothing to stop.", no error
```

- [ ] **Step 4: Confirm no orphans survive**

```bash
pgrep -af "gz sim|parameter_bridge|forklift_io.py|sto_contactor.py|plc_link.py|cmd_gate.py|hmi_node.py" || echo "NO ORPHANS"
```
Expected: `NO ORPHANS`.

- [ ] **Step 5: Add the log directory to .gitignore and commit**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
printf 'm5_ver2/step1/logs/\nm5_ver2/step1/.step1_pids\n' >> .gitignore
git add m5_ver2/step1/step1.sh .gitignore
git commit -m "feat(m5_ver2): step1.sh, one command up and one down

Idempotent both ways. It pins GZ_PARTITION and ROS_DOMAIN_ID so a
concurrent M5 demo cannot join this graph and put a second publisher on
the command topics.

It cannot start PLCSIM or step1.py, and that is the single-writer rule
expressed as a missing feature rather than as a comment."
```

---

### Task 8: `README_step1.md` and the validation run

**Files:**
- Create: `m5_ver2/step1/README_step1.md`

**Interfaces:**
- Consumes: everything.
- Produces: the run procedure and the checklist the owner executes.

- [ ] **Step 1: Write `README_step1.md`**

It must contain, in this order:

1. **What Step 1 is**, in three sentences: teleoperation gated by the real safety PLC; the PLC contributes one bit; the standard program is deliberately not in the command path.
2. **Run order**, as a numbered list — and the order matters:
   1. Owner starts PLCSIM Advanced instance `PLC_2` from the Control Panel and downloads the program from TIA Portal.
   2. `./m5_ver2/step1/step1.sh start` in WSL.
   3. `python m5_ver2\step1\windows\step1.py` on Windows, in 64-bit Python.
   4. Type `a` once. The forklift can now be driven.
   5. `./m5_ver2/step1/step1.sh stop` when finished. It does not stop the PLC; only the owner can, from PLCSIM.
3. **The CONFIG values**, copied from §8 of the spec, with the note that `UDP_TARGET = None` auto-discovers the WSL IP because WSL2 here is NAT and the address changes on every restart.
4. **The `/hmi/cmd_vel` field contract table** — `linear.x` is m/s, `angular.z` is a steer **angle** in rad, not a yaw rate — and one sentence on why.
5. **Three things that are by design and are not bugs**, quoting spec §9: the acknowledge required at startup; the latch after `es1`; and steering staying live while traction is inhibited.
6. **How to see the torque removal**, since the HMI deliberately does not show it:
   ```bash
   source /opt/ros/jazzy/setup.bash
   export GZ_PARTITION=step1 ROS_DOMAIN_ID=91
   ros2 topic echo /forklift/safety/torque_off_applied
   ```
7. **The validation checklist** from Step 2 below, verbatim.

- [ ] **Step 2: Put the checklist at the end of the README**

```
[x] UDP echo Windows->Linux verified before build   (design section 4)
[ ] step1.sh start brings up Gazebo (warehouse + forklift) and HMI
[ ] Startup: lamp inactive, Motor OFF, `a` required once, then teleop works
[ ] es0: forklift stops under held joystick, lamp red
[ ] es1 without a: lamp inactive, forklift still stopped (latch visible)
[ ] a: motion restored
[ ] Bridge kill test: fail-safe stop within 0.5 s
[ ] step1.sh stop kills everything, no orphan processes
```

- [ ] **Step 3: Run the whole test suite once more**

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/ -v
```
Expected: 31 passed, 0 skipped. A skip here means a module failed to import and its tests silently did not run.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step1/README_step1.md
git commit -m "docs(m5_ver2): how to run Step 1, and what is not a bug

Run order with the PLC first, the CONFIG values, the non-standard Twist
contract, and the three by-design behaviours an operator would otherwise
report as faults - the startup acknowledge, the ESTOP1 latch, and steering
staying live while traction is inhibited."
```

- [ ] **Step 5: Print the validation checklist and STOP**

Print the checklist from Step 2 to the user and ask them to run it and report results.

**Do not begin Step 2 of the project.**

---

## Self-Review

**Spec coverage.** Every spec section maps to a task: §2 agreements and §3 ground truth → Task 1; §4 environment → already verified, recorded in Task 2 Step 6; §5.1 direct mapping → Task 4; §5.2 reference in place → the Global Constraints and every launch path; §5.3 contactor → Task 6; §5.4 dedicated launch → Task 6; §6.1 port map → Task 1; §7.1 → Task 2; §7.2 → Task 3; §7.3 → Task 5; §7.4 → Task 4; §7.5 field contract → Tasks 4 and 5 tests; §7.6 → Task 6; §8 CONFIG → Tasks 2, 3, 4 and the README; §9 acceptance → Task 8 checklist; §10 out of scope → nothing implements them; §11 checklist → Task 8.

**Type consistency.** `parse_status` returns `dict | None` in Task 3 and is consumed that way by `motor_from_status` in Task 4. `is_stale(last_rx_s, now_s, stale_s)` keeps its signature. `gated_command` returns `(traction, steer)` in that order everywhere. `knob_to_twist` returns `(linear_x, angular_z)` in that order. `LAMP_RED` and `LAMP_NEUTRAL` are defined in `hmi_node.py` and referenced by its tests only.

**Known coupling, stated rather than hidden.** `cmd_gate.py` imports `plc_link` for `parse_status`. That works because `conftest.py` and the runtime both put `ros2/` on `sys.path`, and it is deliberate: the two files must agree on what an untrustworthy packet is, and duplicating that decision is how they would drift apart.

**Test count.** Task 2 adds 5, Task 3 adds 7, Task 4 adds 9, Task 5 adds 10. Total 31, which is the number Task 8 Step 3 expects.
