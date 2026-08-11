# m5_ver2 Step 1 — E-Stop chain end-to-end (Gazebo + HMI + real F-PLC)

Design, 2026-08-11. Approved by the owner before implementation.

## 1. Goal, and the one thing under test

Teleoperate the existing Gazebo forklift from an HMI joystick, where the drive
enable comes from the **real safety PLC** running in S7-PLCSIM Advanced.

The thing under test is the **safety chain only**: E-Stop demand, the ESTOP1
latch, and acknowledge. The motion command does **not** pass through the PLC in
Step 1 — the PLC contributes exactly one bit, `Motor`.

This is deliberate and it is the reason the design looks the way it does. The
previous milestone teleoperated *through* the PLC standard program. If the
standard program sat in the command path here, a forklift that stopped would be
ambiguous: safety demand, or `V_Limit` collapsing to 300 mm/s? Step 1 removes
that ambiguity by removing the standard program from the path. Standard-program
integration is a later step.

## 2. Non-negotiable working agreements

Recorded verbatim in `m5_ver2/CLAUDE.md`, which is the file every later step
reads instead of re-deriving this context.

1. Small steps. Step 1 only. Nothing scaffolded beyond the reserved port map.
   When done, print the validation checklist and stop.
2. The PLC program is ground truth and is maintained by the owner in TIA
   Portal. Never propose changing PLC logic, tags or addresses. Never invent
   tag names.
3. **Single-writer rule**: exactly one process (`step1.py` on Windows) writes to
   the PLC. No other component may open the PLCSIM Advanced API.
4. **Fail-safe direction**: on any exception, timeout or shutdown, boolean PLC
   inputs are written `False` (trip) and the vehicle command is zeroed.
5. Simplicity over architecture: plain Python run with `python3`, `rclpy` for
   ROS 2 nodes, `tkinter` for the HMI, stdlib UDP for transport. No colcon
   package, no web stack, no rosbridge, no classes without need. Target
   <150 lines per file.
6. Items marked "by design" in §9 are not bugs and must not be fixed.

## 3. PLC ground truth

Platform: TIA Portal, CPU 1516F-3 PN/DP, simulated in S7-PLCSIM Advanced.
The instance is started from the PLCSIM Advanced Control Panel by the owner.

**Instance name: `PLC_2`.** Confirmed by the owner on 2026-08-11. Three stale
names exist in the tree and none of them is the F-PLC under test:
`plcsim_api.py` says `v20`, `demo.sh`/`RUNBOOK.md` assume `safecell3`, and the
Step 1 brief said `PLC_1`. `m5-plc-debug/plc_bridge.py` is the file that agrees,
and its tag set matches the table below exactly.

If the API throws error `-4` (`DoesNotExist`), the instance is not running or
the name mismatches. Report it; do not work around it.

Access is through the PLCSIM Advanced Runtime API via pythonnet, 64-bit Python
on Windows. Known-good boilerplate:

```python
import sys, clr
sys.path.append(r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0")
clr.AddReference("Siemens.Simatic.Simulation.Runtime.Api.x64")
from Siemens.Simatic.Simulation.Runtime import SimulationRuntimeManager, ETagListDetails
plc = SimulationRuntimeManager.CreateInterface("PLC_2")
plc.UpdateTagList(ETagListDetails.IOM)
plc.WriteBool("E-Stop", True); plc.ReadBool("Motor"); plc.WriteInt16("ENC_A", 0)
```

Facts about this simulation that are not obvious:

- API writes to inputs **persist across PLC cycles** — the API plays the role of
  the field devices. TIA watch and force tables cannot drive inputs; the API is
  the only way. Reading an input back returns the process image, which is valid.
- Fail-safe 1oo2 channel pairs collapse to a single process-image bit in
  simulation. F-DI discrepancy behaviour is not simulated.
- Tag names are case-sensitive and may contain hyphens (`E-Stop`).

### 3.1 Tag table (addresses fixed, never rename)

| Tag         | Addr    | Type | Meaning                                           |
|-------------|---------|------|---------------------------------------------------|
| E-Stop      | %I0.0   | Bool | True = healthy (NC chain closed), False = pressed |
| PF_OSSD     | %I0.1   | Bool | True = protective field clear (OSSD high)         |
| WF_Clear    | %I0.2   | Bool | True = warning field clear                        |
| Acknowledge | %I15.0  | Bool | Reset button, rising edge required                |
| ENC_A       | %IW100  | Int  | Encoder channel A, mm/s                           |
| ENC_B       | %IW102  | Int  | Encoder channel B, mm/s                           |
| Motor       | %Q9.0   | Bool | Drive enable from the safety program (the output) |
| CASE_B0     | %Q9.1   | Bool | Monitoring-case bit 0                             |
| CASE_B1     | %Q9.2   | Bool | Monitoring-case bit 1                             |
| V_Limit     | %MW100  | Int  | Speed ceiling mm/s, computed in standard OB1      |

### 3.2 Safety program behaviour (already implemented and validated in TIA)

- Three ESTOP1 instances: e-stop button, protective field, speed/encoder
  monitor (cross-check `|ENC_A - ENC_B| > 50` → fault; ceiling 2800 mm/s).
  `Motor` is the AND of all three enables.
- ESTOP1 semantics: **a demand latches.** The input returning to healthy does
  *not* re-enable; a rising edge on `Acknowledge` is required. `ACK_NEC=true`
  also means one `Acknowledge` is required after PLC startup before `Motor` can
  ever be True.
- For `Motor` to be True, all of these must hold: `E-Stop=True`, `PF_OSSD=True`,
  encoder channels plausible (equal, < 2800), and an `Acknowledge` edge after
  the last demand. **Therefore the Step 1 bridge must constantly hold
  `PF_OSSD=True`, `WF_Clear=True`, `ENC_A=0`, `ENC_B=0`, or `Motor` can never
  energise.**
- Case bits binary-encode monitoring case 1..3 (01/10/11); pattern 00 is
  deliberately invalid. `V_Limit` is 1500 when `WF_Clear` else 300. Both are
  irrelevant to Step 1 and are consumed in later steps.

## 4. Verified environment

Measured on 2026-08-11, not assumed.

| Fact | Value | How it was established |
|---|---|---|
| Sim host | WSL2 Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic 8.11 | `sim/setup/WSL_ENVIRONMENT.md` |
| WSL networking | **NAT** (no `.wslconfig`, so not mirrored) | `$USERPROFILE\.wslconfig` absent |
| WSL guest IP | `172.19.180.72` | `wsl hostname -I` |
| Windows host as seen from WSL | `172.19.176.1` | source address of the probe below |
| UDP Windows → WSL :5100 | **works, no firewall block** | probe sent from Windows, received in WSL: `GOT b'{"probe":"step1"}' from ('172.19.176.1', 59540)` |
| PLCSIM API versions present | 3.0, 4.0, 4.1, 5.0, 6.0, 7.0 | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API` |

**The `127.0.0.1` shortcut is not available.** The brief allowed for it under
mirrored networking; this machine is NAT, so Windows must address the guest IP
explicitly. That IP is reassigned on every WSL restart, which is why §8 makes
the target auto-discovered rather than hard-coded.

The reverse direction (WSL → Windows `172.19.176.1`, reserved port 5101) is
**not exercised in Step 1** and is not known to work — Windows Firewall
commonly blocks inbound traffic from the WSL NAT subnet. That is a later step's
problem and must be verified then, not assumed from this result.

## 5. The vehicle, and why the command path is shaped as it is

The forklift is a **tricycle**, not a differential base. `agv/forklift/model.sdf`
drives it through two gz plugins:

```
/forklift/gz/actuator/steer_cmd      gz-sim-joint-position-controller-system
/forklift/gz/actuator/traction_cmd   gz-sim-joint-controller-system
```

`agv/forklift/scripts/forklift_io.py` is the engineering-unit translator that
feeds them. It is **a unit translator and a slew limiter, and nothing else** —
its own header says so, it holds no PLC connection and performs no safety
function. It is therefore safe to reuse and does not touch the single-writer
rule.

```
/forklift/cmd/traction_speed  [m/s]  -> /forklift/gz/.../traction_cmd  [rad/s]
/forklift/cmd/steer_angle     [rad]  -> /forklift/gz/.../steer_cmd     [rad]
```

### 5.1 Decision: cmd_gate maps directly; the nav2-era converter is not used

`agv/forklift/scripts/cmd_vel_to_tricycle.py` converts a proper `Twist` to the
tricycle pair with the bicycle relation `delta = atan(L*w/v)`, `v_D = v/cos(delta)`.
It is correct and validated, and it is **the wrong tool here**, because at
standstill `v = 0` leaves `delta` undefined: the joystick would not steer a
stopped forklift.

That failure mode lands exactly on the behaviour under test. After `es0` the
forklift stops; if the joystick were also dead in that state, the operator
cannot tell a safety stop from an unresponsive HMI. Step 1 needs steering to
stay visibly alive while traction is inhibited.

So `cmd_gate` maps the joystick to the two engineering-unit values directly and
publishes them. No bicycle geometry is computed anywhere in Step 1.

### 5.2 Decision: reference existing assets in place, do not copy

`m5_ver2/step1/` copies nothing. A thin launch file points at
`sim/worlds/warehouse.sdf`, `agv/forklift/model.sdf`,
`agv/forklift/scripts/forklift_io.py` and `agv/forklift/config.yaml` where they
already are.

The brief proposed copying the Gazebo assets into `m5_ver2/step1/gazebo/`. That
was rejected once `forklift_io.py` was reused in place: a half-copied tree is
worse than either extreme, and a duplicated 1350-line `model.sdf` means every
future model fix has to be applied twice or silently diverges. The cost accepted
is that `m5_ver2/step1/` is not independently portable.

### 5.3 Decision: `sto_contactor.py` runs, and is the interlock

`forklift_io.py` does **not** publish the model's actuator terminals. It
publishes the stack-side names, and `agv/forklift/scripts/sto_contactor.py` is
the **only** publisher of the terminals `model.sdf` actually listens on:

```
/forklift/gz/steer_cmd     ->  /forklift/gz/actuator/steer_cmd
/forklift/gz/traction_cmd  ->  /forklift/gz/actuator/traction_cmd
/forklift/gz/fork_cmd      ->  /forklift/gz/actuator/fork_cmd
```

It is a plain ROS node — `std_msgs/Bool` in on
`/forklift/safety/torque_off_demand`, `std_msgs/Bool` out on
`/forklift/safety/torque_off_applied`, no OPC UA, no PLC connection. It is
reused **unmodified**, and `plc_link.py` gains one publisher to feed it.

Two reasons this is not optional:

1. **Without it nothing publishes the terminals and the forklift cannot move
   at all.** The alternative — having `ros_gz_bridge` rename the stack-side
   topics onto the terminals — would work, and would silently undo the reason
   m5-50 moved the interlock to the model's own inputs: five committed
   publishers address the stack-side names directly, so an interlock in any
   command node is bypassable and an interlock at the model's inputs is not.
2. It makes the stop **two-stage**, which is what the E-Stop chain actually
   is. `cmd_gate` performs the controlled stop (zeros the command);
   `sto_contactor` removes torque at the plant (latches open, drives the
   traction terminal to a standing zero, holds steer at its last value).

Note its fail direction, which differs from everything else in Step 1 and is
correct there: it latches on an **observed True** and releases on an **observed
False**, so a demand link that never speaks leaves it *closed*. Step 1 is still
fail-safe on link loss because `plc_link.py` does not go silent — on staleness
it actively publishes `motor=False`, and therefore `torque_off_demand=True`.

### 5.4 Decision: a dedicated launch file, not `vehicle.launch.py`

`agv/forklift/launch/vehicle.launch.py` also starts `safe_speed_link.py`,
`field_evaluation.py`, `obstacle_zone.py` and the EKF — the old M5 OPC UA
safety path. Running it would put a second process on the PLC and break the
single-writer rule. Its launch arguments could in principle switch most of that
off, but Step 1's isolation would then depend on a dozen toggles being right. A
dedicated launch file that starts five named things is the honest version.

## 6. Architecture

Six processes. One writes to the PLC.

```
WINDOWS                              │  WSL2 (ROS 2 Jazzy)
                                     │
  PLCSIM Advanced, instance "PLC_2"  │
    ▲ writes     │ reads             │
    │            ▼                   │
  step1.py ──────UDP :5100──────────►│  plc_link.py
    ▲ stdin: es0 | es1 | a | q       │      │
                                     │      ├── /plc/status ──► hmi_node.py (lamp)
                                     │      │                ─► cmd_gate.py
                                     │      │
                                     │      └── /forklift/safety/torque_off_demand
                                     │                       (Bool, = not motor)
                                     │                            │
                                     │  hmi_node.py               │
                                     │      │ /hmi/cmd_vel        │
                                     │      ▼                     │
                                     │  cmd_gate.py   ◄─ STAGE 1: zero on !motor
                                     │      │ /forklift/cmd/traction_speed
                                     │      │ /forklift/cmd/steer_angle
                                     │      ▼
                                     │  forklift_io.py   (units + slew)
                                     │      │ /forklift/gz/traction_cmd
                                     │      │ /forklift/gz/steer_cmd
                                     │      ▼
                                     │  sto_contactor.py ◄─ STAGE 2: latch open ◄┘
                                     │      │ /forklift/gz/actuator/*_cmd
                                     │      ▼
                                     │  ros_gz_bridge → gz sim → forklift moves
```

### 6.1 Port map (fixed for the whole project; only 5100 is implemented)

| Port | Direction | Payload | Step |
|---|---|---|---|
| 5100 | Windows → WSL | PLC state JSON `{"estop_healthy", "motor", "ts"}` @ 20 Hz | **Step 1** |
| 5101 | WSL → Windows | simulated sensors (distance, speed) | later |

## 7. Components

All paths relative to `m5_ver2/`.

| File | ~Lines | Responsibility |
|---|---|---|
| `CLAUDE.md` | — | §2 agreements, §3 PLC ground truth verbatim, §6.1 port map |
| `step1/windows/step1.py` | 130 | The only PLC writer |
| `step1/ros2/plc_link.py` | 70 | UDP :5100 → `/plc/status` |
| `step1/ros2/hmi_node.py` | 140 | tkinter joystick + E-stop lamp |
| `step1/ros2/cmd_gate.py` | 90 | Enable-gated command forwarding |
| `step1/gazebo/step1_world.launch.py` | 80 | gz + spawn + `ros_gz_bridge` + `forklift_io.py` + `sto_contactor.py` |
| `step1/step1.sh` | 90 | `start` / `stop`, PIDs in `.step1_pids` |
| `step1/README_step1.md` | — | Run order, CONFIG, validation checklist |

### 7.1 `windows/step1.py`

64-bit Python on Windows. 20 ms loop. Every cycle writes, unconditionally:

```
PF_OSSD  = True          WF_Clear = True
ENC_A    = 0             ENC_B    = 0
E-Stop   = <state>       Acknowledge = <pulse>
```

`PF_OSSD`/`WF_Clear`/`ENC_*` are held at their healthy values every cycle
because §3.2 makes them a precondition for `Motor` ever energising.

Reads back `Motor` and `E-Stop`, prints one status line (carriage-return
updated, not scrolling), and streams `{"estop_healthy", "motor", "ts"}` to
UDP :5100 at 20 Hz.

A daemon terminal thread accepts:

| Command | Effect |
|---|---|
| `es0` | press e-stop — `E-Stop` written `False` |
| `es1` | release — `E-Stop` written `True` (does *not* re-enable; see §9.3) |
| `a`   | 300 ms `Acknowledge` pulse (rising edge) |
| `q`   | quit through the same shutdown path as an exception |

`ts` is `time.monotonic()`-derived. Wall clock is not used: the Windows host and
the WSL guest are not clock-synchronised (`w32time` is stopped —
`sim/setup/WSL_ENVIRONMENT.md` §5 item 3), so a wall-clock timestamp crossing
the boundary would be wrong by seconds.

### 7.2 `ros2/plc_link.py`

Binds `0.0.0.0:5100`. Publishes two topics, both at 20 Hz:

| Topic | Type | Value |
|---|---|---|
| `/plc/status` | `std_msgs/String` | the JSON as received |
| `/forklift/safety/torque_off_demand` | `std_msgs/Bool` | `not motor` |

If no packet arrives for **0.3 s** (`STALE_S`), it publishes
`estop_healthy=False, motor=False` and therefore `torque_off_demand=True` — and
keeps publishing, so a late subscriber still learns the failure and
`sto_contactor.py`, which latches only on an observed True, actually sees the
demand.

**Why 0.3 s and not the 0.5 s originally written here.** §9 item 5 requires the
*vehicle* to stop within 0.5 s of the link dying, and detection is only the
first term of that. Staleness is evaluated on tick boundaries, so the link's own
detection latency is `STALE_S + 1/PUBLISH_HZ`, and the gate then needs up to one
of its own zero-ticks:

| Term | Value | Source |
|---|---|---|
| `STALE_S` | 0.30 | this file |
| `+ 1/PUBLISH_HZ` | 0.05 | plc_link's 20 Hz tick |
| `+ 1/ZERO_HZ` | 0.10 | cmd_gate's 10 Hz zero floor |
| **worst case** | **0.45 s** | inside the 0.5 s requirement |

At `STALE_S = 0.5` the first term alone was 0.55 s, so the requirement was
unachievable in every case, not merely usually missed — measured at 523 ms
before the change. At the sender's ~50 Hz, 0.3 s is 15 datagrams, so this still
tolerates a long burst of loss before tripping.

The demand topic name is read from `agv/forklift/config.yaml`
(`topics.safety_torque_off_demand`), not written as a literal.

### 7.3 `ros2/hmi_node.py`

tkinter, and nothing else:

- **Joystick**: a canvas the operator drags. Release snaps the knob to centre
  and publishes zero. Publishes `/hmi/cmd_vel` (`geometry_msgs/Twist`) at 20 Hz
  while the window is open. Axis convention, stated so it is not guessed:

  | Drag | Normalised | Published |
  |---|---|---|
  | up | `y = +1` | `linear.x = +1.50` (forward) |
  | down | `y = -1` | `linear.x = -1.50` (reverse) |
  | right | `x = +1` | `angular.z = -1.31` (steer right) |
  | left | `x = -1` | `angular.z = +1.31` (steer left) |

  The sign flip on the steer axis is REP-103: positive z is counter-clockwise,
  and a driver pushing the stick right expects to turn right. Whether that
  actually turns the model right depends on the `steer_joint` axis direction in
  `model.sdf`; confirm on the first run and, if inverted, fix it here rather
  than in the model.
- **Lamp**: reads `/plc/status`. Red with the text **"E-Stop Active"** when
  `estop_healthy` is False; neutral with **"E-Stop Inactive"** otherwise.
- **Secondary line**: **"Drive enable: ON/OFF"**, from `motor`.

The lamp and the secondary line are separate on purpose. Their disagreement —
lamp inactive, drive enable OFF — is the ESTOP1 latch made visible, and showing
it is a Step 1 goal (§9.3).

### 7.4 `ros2/cmd_gate.py`

Subscribes `/hmi/cmd_vel` and `/plc/status`.

- `motor == True` → forward to `/forklift/cmd/traction_speed` and
  `/forklift/cmd/steer_angle`.
- `motor == False`, **or** `/plc/status` stale, **or** `/plc/status` never
  received → publish zero on both topics **continuously at 10 Hz**, not once.
  Continuous zeros, because a single zero lets the simulated vehicle coast.

Initial state is `motor = False`. A gate that has not yet heard from the PLC
must not pass a command.

### 7.5 The `/hmi/cmd_vel` field contract

A deliberate deviation from `Twist` semantics. It is written in the docstring of
both `hmi_node.py` and `cmd_gate.py`, and in `README_step1.md`.

| Field | Carries | Range | Source of the limit |
|---|---|---|---|
| `linear.x` | traction speed **[m/s]** | ±1.50 | `limits.traction_speed_max_mps` |
| `angular.z` | steer **angle [rad]** — *not* yaw rate | ±1.31 | `model.steer_limit_rad` |

Both limits are read from `agv/forklift/config.yaml` at startup, not
copied as literals, so a change to the vehicle stays in one place.
`model.wheelbase_m` (1.05) is *not* read: no geometry is computed here.

### 7.6 `gazebo/step1_world.launch.py`

Starts exactly five things:

1. `gz sim` on `sim/worlds/warehouse.sdf`
2. spawn `agv/forklift/model.sdf` at the same pose `sim/launch/warehouse_bringup.launch.py` uses
3. one `ros_gz_bridge` carrying `/clock` and the **actuator terminals**
   (`topics.gz_actuator_steer_cmd`, `topics.gz_actuator_traction_cmd`) — the
   bridge carries the terminals, never the stack-side command names
4. `agv/forklift/scripts/forklift_io.py --config agv/forklift/config.yaml`
5. `agv/forklift/scripts/sto_contactor.py --config agv/forklift/config.yaml`

**Resolved: both topic names were real and neither was stale.** `config.yaml`
defines both families — `topics.gz_steer_cmd` = `/forklift/gz/steer_cmd` (what
`forklift_io.py` publishes) and `topics.gz_actuator_steer_cmd` =
`/forklift/gz/actuator/steer_cmd` (what `model.sdf` listens on). They are the
two ends of `sto_contactor.py`, not a naming error. Every topic name in the
launch file is read from `config.yaml`; none is written as a literal.

Every shell that runs `gz` must source `/opt/ros/jazzy/setup.bash` first — there
is no `/usr/bin/gz` on this machine (`sim/setup/WSL_ENVIRONMENT.md` §4.1).

## 8. CONFIG

A `CONFIG` dict at the top of each transport file.

```python
# step1/windows/step1.py
PLC_INSTANCE = "PLC_2"
API_DLL_DIR  = r"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0"
UDP_TARGET   = None       # None -> first token of `wsl.exe hostname -I`
UDP_PORT     = 5100
CYCLE_S      = 0.02       # 20 ms
ACK_PULSE_S  = 0.30

# step1/ros2/plc_link.py
BIND_ADDR = "0.0.0.0"
UDP_PORT  = 5100
STALE_S   = 0.3       # see the latency budget in section 7.2

# step1/ros2/cmd_gate.py
ZERO_HZ     = 10.0
# Resolved from __file__, so the tree can be cloned anywhere:
#   <this file>/../../../agv/forklift/config.yaml
CONFIG_YAML = None        # None -> the path above; a string overrides it
```

`UDP_TARGET = None` auto-discovers the guest IP by running `wsl.exe hostname -I`
once at startup. Hard-coding `172.19.180.72` would work today and break silently
at the next WSL restart. An explicit string overrides the discovery.

## 9. Expected behaviour (acceptance semantics)

1. **Fresh start.** HMI opens, lamp shows "E-Stop Inactive", but `Motor` is OFF
   and the forklift does not move — the startup acknowledge is pending.
   **By design.** Typing `a` once in `step1.py` turns `Motor` ON; the joystick
   now drives.
2. **`es0`.** Within ~100 ms `Motor` goes OFF, the lamp turns red "E-Stop
   Active", and the forklift stops **even while the joystick is held**. Both
   stages act: `cmd_gate` zeros the command, and `sto_contactor` latches open
   and drives the traction terminal to a standing zero.
   `/forklift/safety/torque_off_applied` reads `True`.
3. **`es1`.** The lamp returns to "E-Stop Inactive" **but `Motor` stays OFF and
   the forklift still does not move.** This is the ESTOP1 latch. **By design,
   not a bug.** Making this state visible — lamp inactive, drive enable OFF — is
   a Step 1 goal. `torque_off_applied` stays `True`.
4. **`a`.** `Motor` ON, `torque_off_demand` falls, the contactor releases, and
   teleoperation works again. Motion resumes only on a fresh command, because
   the value standing at the terminal is the brake's — `hmi_node.py` publishes
   at 20 Hz continuously, so this is immediate and invisible to the operator.
   It is stated here so that a one-cycle delay is not mistaken for a fault.
5. **Kill `step1.py` while driving.** Within 0.5 s `plc_link` fails safe: it
   publishes `motor=False` and `torque_off_demand=True`, the gate zeroes the
   command, the contactor latches open, the forklift stops, the lamp shows red.

## 10. Out of scope for Step 1

Named so they are not built by accident:

- The PLC standard program in the command path. `V_Limit` and `CASE_B0/B1` are
  read by nothing in Step 1.
- Port 5101 and any WSL → Windows traffic.
- Nav2, SLAM, the EKF, the envelope gate, `cmd_vel_to_tricycle.py`,
  `safe_speed_link.py`, `obstacle_zone.py`, `field_evaluation.py`.
- The fork/mast axis. `sto_contactor.py` forwards `fork_cmd` as it always has;
  nothing in Step 1 publishes it, so the mast stays where it is.
- Showing `/forklift/safety/torque_off_applied` on the HMI. The lamp and the
  drive-enable line are the two the brief specifies and the HMI stays at two.
  The topic is verified from the command line instead —
  `ros2 topic echo /forklift/safety/torque_off_applied` — and `README_step1.md`
  says so.
- Any change to `plc/`, to TIA Portal content, or to the existing M5 tree.

## 11. Validation checklist

Printed at the end of implementation. The owner runs it and reports results.

Item 1 is **already satisfied** by the probe recorded in §4 and is listed only
so the checklist stands on its own.

```
[x] UDP echo Windows->Linux verified before build   (see section 4)
[ ] step1.sh start brings up Gazebo (warehouse + forklift) and HMI
[ ] Startup: lamp inactive, Motor OFF, `a` required once, then teleop works
[ ] es0: forklift stops under held joystick, lamp red
[ ] es1 without a: lamp inactive, forklift still stopped (latch visible)
[ ] a: motion restored
[ ] Bridge kill test: fail-safe stop within 0.5 s
[ ] step1.sh stop kills everything, no orphan processes
```

Step 2 is not begun until the owner has run this list.
