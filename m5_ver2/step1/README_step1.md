# Step 1 — E-Stop chain end to end

Teleoperate the Gazebo forklift from an HMI joystick whose **drive enable comes
from the real safety PLC** in S7-PLCSIM Advanced. The PLC contributes exactly one
bit — `Motor` — and the motion command never passes through it. The standard
program is deliberately out of the command path: with it in, a forklift that
stopped could be a safety demand *or* `V_Limit` collapsing to 300 mm/s, and Step 1
exists to remove that ambiguity.

> Something looks wrong? Read **[Not a bug](#not-a-bug)** before you debug it.

## Run order

The PLC goes first. The vehicle side cannot be enabled without it.

| # | Where | Do this |
|---|---|---|
| 1 | Windows | Start PLCSIM Advanced instance **`PLC_2`** from the Control Panel, download the program from TIA Portal, CPU in RUN. |
| 2 | WSL | `cd /mnt/c/Users/ozkan/projects/amr-agent` |
| 3 | WSL | `./m5_ver2/step1/step1.sh start` — takes ~7 s. Do **not** source ROS first; the script does it. |
| 4 | WSL | Read the four pid lines it prints. `WARNING: <name> exited during startup` sends you to that log in `m5_ver2/step1/logs/`. |
| 5 | Windows | `cd C:\Users\ozkan\projects\amr-agent` |
| 6 | Windows | `python m5_ver2\step1\windows\step1.py` — **64-bit Python** (pythonnet). It prints `streaming PLC state to <wsl-ip>:5100`. |
| 7 | Windows | Type **`a`**, Enter. Once. `Motor` goes True, the HMI lamp turns neutral, the line under it reads `Drive enable: ON`. |
| 8 | HMI window | Drag the joystick. The forklift drives. |
| 9 | Windows | Finished: type **`q`**. It writes the trip values on the way out. |
| 10 | WSL | `./m5_ver2/step1/step1.sh stop` |

**`q` before `stop`, in that order.** `stop` is not a brake — Gazebo's joint
controllers hold their last setpoint, so killing the stack under a moving truck
only leaves it moving (measured once at 14.8 m on a standing command). The e-stop
is the brake.

Neither script touches PLCSIM. Only you stop the PLC, from the Control Panel.

### What `step1.py` accepts on stdin

| Command | Effect |
|---|---|
| `es0` | press the e-stop — `E-Stop` written `False` |
| `es1` | release — `E-Stop` written `True`. Does **not** re-enable; see [Not a bug](#not-a-bug). |
| `a` | 300 ms `Acknowledge` pulse (a rising edge) |
| `q` | quit through the same trip path an exception takes |

### Two things `step1.sh` does that are easy to miss

- **`start` runs every process under `setsid`**, so the stack survives closing the
  terminal you started it from. Before that, closing it killed five of six and
  left `gz sim` alone in a live simulator.
- **`stop` validates the PID file before it signals anything.** Each recorded pid
  must still have `m5_ver2/step1` in its `/proc/<pid>/cmdline`, and each candidate
  must carry this stack's `GZ_PARTITION`. A second stack you have running — an M5
  demo in partition `m5demo` — cannot be taken down by it, even after a reboot has
  recycled the recorded pids.

## Not a bug

Everything in this table is deliberate. None of it should be "fixed".

| What you see | Why it is correct |
|---|---|
| **The HMI window opens RED — "E-Stop Active", "Drive enable: OFF" — before `step1.py` is running.** This is the single most likely thing to be misread as a fault. | Nothing is publishing `/plc/status` yet. `hmi_node.py` and `cmd_gate.py` each apply a staleness rule (`STATUS_STALE_S`), and a display that has been told nothing shows the **safe** state, not a comfortable one. A lamp reading "E-Stop Inactive" before the PLC has said anything would be claiming a healthy chain on no evidence. It turns neutral within a tick of `step1.py` starting. |
| `Motor` is OFF at a fresh start with nothing tripped, and one `a` is required before anything moves. | `ACK_NEC = true` in the ESTOP1 blocks: one `Acknowledge` rising edge is required after PLC startup before `Motor` can ever be True. You also need it after **every** `step1.py` run, because `q` and every exception write `E-Stop`, `PF_OSSD`, `WF_Clear` False on the way out — that trip latches too. |
| After `es1` the lamp goes neutral **but the forklift stays stopped** and the line still reads `Drive enable: OFF`. | The ESTOP1 latch. A demand latches; the input returning to healthy does not re-enable it. That disagreement between the lamp and the enable line *is* the latch made visible, and showing it is a Step 1 goal. `a` restores motion, on the next joystick message — invisible, because the HMI publishes at 20 Hz continuously. |
| Steering still responds while traction is dead. | Deliberate. If the joystick went dead too, you could not tell a safety stop from a broken HMI — which is the one thing this window exists to distinguish. `angular.z` is therefore a steer *angle*, commanded directly, with no bicycle geometry anywhere in Step 1. |
| `forklift_io` logs `waiting for source data: joint_states=False, odom=False` every 5 s, forever. | `joint_states` and odometry are deliberately not bridged — nothing in `m5_ver2/step1/` consumes them. The warning gates only two derived state scalars and the fork target seed, never the traction or steer command path. |
| No Gazebo window appears. | `gz sim` runs `-s --headless-rendering`: server only, by design. The HMI is the only window. The spawn is confirmed by `Entity creation successful.` in `logs/world.log`. |
| `logs/plc_link.log` and `logs/cmd_gate.log` end in an `rclpy.executors.ExternalShutdownException` traceback. | That is what a clean SIGTERM looks like in these nodes — `step1.sh stop` sent it. It is the house pattern in `agv/`, and it appears *after* the node's normal startup line, not instead of it. |
| `logs/world.log` is full of yellow `XML Element[gz_frame_id] ... not defined in SDF` and `libEGL warning: egl: failed to create dri2 screen`. | Both come from parsing `model.sdf` and from `--headless-rendering`. They are properties of the model file and the render flag, not of this run, and nothing in the command path reads them. |

## The `/hmi/cmd_vel` field contract

**This is not standard `Twist`.** It is a deliberate deviation, stated in the
docstring of both `hmi_node.py` and `cmd_gate.py`.

| Field | Carries | Range | Limit comes from |
|---|---|---|---|
| `linear.x` | traction speed **[m/s]** | ±1.50 | `limits.traction_speed_max_mps` |
| `angular.z` | steer **angle [rad]** — *not* a yaw rate | ±1.31 | `model.steer_limit_rad` |

Why an angle: the bicycle relation `delta = atan(L*w/v)` is undefined at `v = 0`,
so a proper `Twist` would leave a stopped forklift unsteerable — exactly the state
an e-stop test puts it in, and exactly when you need to be able to tell a safety
stop from a dead joystick. Both limits are read from `agv/forklift/config.yaml` at
startup, never copied as literals.

Dragging right steers right, which is a **negative** `angular.z` under REP-103.

## CONFIG

Verified against the code. Each constant has exactly one home.

| File | Name | Value | Note |
|---|---|---|---|
| `windows/step1.py` | `PLC_INSTANCE` | `"PLC_2"` | error `-4` (`DoesNotExist`) = instance not running, or the name differs |
| | `API_DLL_DIR` | `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0` | |
| | `UDP_TARGET` | `None` | `None` → first token of `wsl.exe hostname -I`. WSL2 here is **NAT, not mirrored**: `127.0.0.1` does not reach the guest, and the guest IP is reassigned on every WSL restart. A string overrides the discovery. |
| | `UDP_PORT` | `5100` | |
| | `CYCLE_S` | `0.02` | 20 ms loop, so ~50 Hz on the wire. The port map's "20 Hz" is `plc_link`'s republish rate, not this one. |
| | `ACK_PULSE_S` | `0.30` | |
| | `STATUS_EVERY` | `10` | status line printed every 10th cycle (~5 Hz) |
| `ros2/plc_link.py` | `BIND_ADDR` | `"0.0.0.0"` | |
| | `UDP_PORT` | `5100` | |
| | `STALE_S` | `0.28` | **this node's own UDP timeout.** Deliberately not a multiple of the 0.05 s tick: 5 ticks must not trip and 6 must, with margin at both ends. Do not round it to 0.25 or 0.30. |
| | `PUBLISH_HZ` | `20.0` | it republishes at 20 Hz even when the link is dead — silence here would be a moving vehicle |
| `ros2/status_contract.py` | `STATUS_TOPIC` | `"/plc/status"` | |
| | `STATUS_STALE_S` | `0.25` | **the ROS-side timeout on `/plc/status`**, shared by the gate and the HMI so the screen and the vehicle stop trusting a silent status at the same instant |
| `ros2/cmd_gate.py` | `ZERO_HZ` | `10.0` | load-bearing on the 0.45 s budget below — do not lower it |
| | `HMI_TOPIC` | `"/hmi/cmd_vel"` | |
| `ros2/hmi_node.py` | `PUBLISH_HZ` | `20.0` | |
| | `SPIN_MS` | `4` | tkinter's pump period. Throughput only: at 20 ms `/hmi/cmd_vel` measured 16.5 Hz against a declared 20. |
| | `KNOB_RADIUS_PX` | `100.0` | |
| | `LAMP_RED` / `LAMP_NEUTRAL` | `#c62828` / `#455a64` | |
| `step1.sh` | `GZ_PARTITION` | `step1` | exported to every child; it is what scopes `stop`. Overridable from the environment. |
| | `ROS_DOMAIN_ID` | `91` | does **not** isolate Gazebo — gz transport is not DDS |

**`STALE_S` (0.28) and `STATUS_STALE_S` (0.25) are two different constants on two
different clocks.** `STALE_S` is `plc_link`'s timeout on UDP datagrams arriving
from Windows; `STATUS_STALE_S` is the timeout the gate and the HMI apply to the
`/plc/status` topic. They are not interchangeable, and merging them breaks the
timing budget. `is_stale()` therefore takes its window as a required argument.

No ROS or gz topic name is a literal anywhere in Step 1 except `/plc/status` and
`/hmi/cmd_vel`; the rest are read from `agv/forklift/config.yaml`.

## How to see the torque removal

The HMI deliberately shows two indicators and no more, so the second stage of the
stop — `sto_contactor.py` opening its latch at the plant's own inputs — is checked
from the command line instead:

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=step1 ROS_DOMAIN_ID=91
ros2 topic echo /forklift/safety/torque_off_applied
```

`True` while inhibited, `False` when the drive is enabled. The terminal the model
actually listens on is `/forklift/gz/actuator/traction_cmd` — echo that one to see
the command reaching the plant.

## Measured, so you know what good looks like

| Event | Measured |
|---|---|
| `/hmi/cmd_vel` publish rate | 20.01 Hz |
| Forklift drives (positive control) | 2.847 m in 8 s at 0.4 m/s commanded |
| Vehicle stops after the PLC link dies (`step1.py` killed) | detected in ≤ 350 ms; budget < 0.45 s end to end |
| Vehicle stops after `plc_link` itself dies | ≤ 295 ms; budget < 0.35 s |
| HMI display returns to the safe state | 301 ms |

Unit tests: `55 passed, 0 skipped`.

```bash
cd /mnt/c/Users/ozkan/projects/amr-agent
source /opt/ros/jazzy/setup.bash
python3 -m pytest m5_ver2/step1/tests/ -q
```

A **skip** is a failure here: it means a module did not import and its tests
silently did not run.

## Validation checklist

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
