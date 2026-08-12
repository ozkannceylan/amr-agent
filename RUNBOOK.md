# RUNBOOK — the F-PLC safety loop, start to finish

One page, in the order you actually do things. Two machines share the work:
**Windows** runs TIA Portal, S7-PLCSIM Advanced and the one process allowed to
write to the PLC; **WSL2** runs Gazebo, ROS 2 and the vehicle stack.

Nothing below claims or implies an achieved Performance Level, Category, SIL
or PFH. The scanners' measurement channels, the encoder readings and the
PLCSIM Advanced API stand in for field wiring; the F-logic they drive is real
STEP 7 Safety, running on a simulated 1516F CPU.

---

## 0. Prerequisites (once)

**Windows**
- TIA Portal V20 with STEP 7 Safety V20, and the project holding the safety
  program this repo is built against. [`safety_summary.pdf`](safety_summary.pdf)
  is that program's Safety Administration printout — collective F-signature
  `F2C00E69`, F-OB `FOB_RTG1` cyclic at 100 ms. If your download's signature
  differs, you are running a different program than this runbook describes.
- S7-PLCSIM Advanced 6.0 (API DLLs under
  `C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\6.0`).
- 64-bit Python 3 with `pythonnet` (`pip install pythonnet`).

**WSL2 (Ubuntu 24.04)**
- ROS 2 Jazzy with the Gazebo vendor packages and `ros_gz`
  (`source /opt/ros/jazzy/setup.bash` is assumed by every command below).
- This repo at `/mnt/c/Users/<you>/projects/amr-agent`.

## 1. The PLC half (Windows, by hand)

1. Start a PLCSIM Advanced instance named **`PLC_2`** from the PLCSIM Advanced
   Control Panel. The name matters: the writer connects by it, and API error
   `-4 (DoesNotExist)` means the instance is not running or is named
   something else.
2. From TIA Portal, download the standard and safety program and put the CPU
   in **RUN**.

Tag names and addresses are the contract and never change:

| Tag | Addr | Meaning |
|---|---|---|
| `E-Stop` | %I0.0 | True = chain healthy, False = pressed |
| `PF_OSSD` / `_right` / `_left` | %I0.1 / .3 / .5 | protective field clear, per scanner |
| `WF_Clear` / `_right` / `_left` | %I0.2 / .4 / .6 | warning field clear, per scanner |
| `Acknowledge` | %I15.0 | reset, rising edge required |
| `ENC_A` / `ENC_B` | %IW100 / %IW102 | encoder channels, mm/s |
| `Motor` | %Q9.0 | the drive enable — the F-program's verdict |
| `CASE_B0` / `CASE_B1` | %Q9.1 / .2 | monitoring case, binary |
| `V_Limit` | %MW100 | speed ceiling mm/s (1500 fields clear, 300 warned) |

## 2. The vehicle half (WSL)

```bash
cd /mnt/c/Users/<you>/projects/amr-agent
./m5_ver2/step4/step4.sh start            # --headless for no Gazebo window
```

This brings up, in its own `GZ_PARTITION=step4`: the open warehouse world and
the forklift (three safety scanners, navigation lidar, IMU, two encoder
reading heads), the gz↔ROS bridge, the actuator contactor, the vehicle I/O
node, and the five step-4 nodes — `plc_link`, `cmd_gate`, `field_eval`,
`encoder_link`, `sensor_link` — plus the teleoperation HMI window. Logs land
in `m5_ver2/step4/logs/`, one file per process.

The Gazebo window opens only after the scanners are live (deliberate — see
the launch file), so expect it a few seconds behind the HMI.

## 3. The writer (Windows)

```bash
python m5_ver2\step4\windows\step4.py
```

This is **the only process that writes to the PLC** — it plays the field
devices, 50 times a second: e-stop state, six scanner verdicts, two encoder
words in; `Motor`, the case bits and `V_Limit` back out to the vehicle. Its
panel carries the e-stop buttons, RESET, and the encoder fault injectors.

**Everything fails toward a stop.** Close the panel, kill either link, or
let any process die: the affected inputs are written False (encoders to an
implausible 0/3000 pair), the F-program latches, and the vehicle side zeros
its command within 0.28 s on its own staleness rule.

## 4. First motion — the acknowledge ritual

`Motor` is OFF at every fresh start with nothing wrong. That is `ACK_NEC`:
after CPU startup, and after every trip (including the trip values every
`step4.py` exit writes), the ESTOP1 latches hold until one `Acknowledge`
rising edge arrives.

1. HMI window up, writer panel up, both links live (the panel's status line
   updates; the HMI lamp leaves its red "no data" state).
2. Press **RESET** on the writer panel once. `MOTOR ENABLED` lights.
3. Drag the HMI joystick. `linear` is traction speed, `angular` is the steer
   **angle**. Release recentres to zero.

## 5. What to demonstrate

| Function | Do | Expect | Recover |
|---|---|---|---|
| E-stop | **PUSH EMERGENCY STOP** while driving | Motor drops at once; vehicle coasts to rest under the held-zero terminal | **RELEASE**, then **RESET** — release alone must NOT re-enable, and doesn't |
| Protective field | drive toward a rack face | at 1.0 m (case 1) the scanner's verdict goes False, the F-program latches, the truck stops and stays stopped | back away is refused too — use `home` (below), then **RESET** |
| Warning field | approach until the HMI field lamp turns WARNING | `V_Limit` drops 1500 → 300; commanding more than 0.3 m/s now trips the speed monitor | slow down, or clear the field and **RESET** if tripped |
| Encoder cross-check | press **OFFSET A** while driving | ENC_A reads +400 mm/s against ENC_B, 8× the 50 mm/s limit — fault, stop | **OK**, then **RESET** |
| Encoder freeze | press **FREEZE A**, then drive | channel A holds its last value; the fault trips as soon as real speed departs from it | **OK**, then **RESET** |
| Dead link | close the writer mid-drive | vehicle command zeroed within 0.28 s; on restart, everything is latched | restart writer, **RESET** |

All six scanner verdicts reach the F-DI: block any scanner's view close
enough and its own ESTOP1 instance drops `Motor` — back, right and left each
latch independently.

## 6. Putting the vehicle back

A protective stop is not self-clearing, and a truck stopped nose-to-rack
cannot drive out of its own field. Without restarting anything:

```bash
./m5_ver2/step4/step4.sh home
```

teleports the forklift to its spawn pose and **clears no latch** — it says so
in its own output. The PLC state is untouched; **RESET** on the panel is
still the only acknowledge.

## 7. Seeing the beams

In the Gazebo window: the *Visualize lidar* panel (docked right) → press the
refresh button → pick a topic. Entry zero is the **back** scanner's
measurement channel; the navigation lidar is `/forklift/gz/scan_nav`. The
fans draw anchored on the vehicle; drawing is a GUI affair and nothing in the
command or safety path reads it.

## 8. Shutdown

1. Close the writer panel (its exit writes the trip values — that latch is
   expected, see §4).
2. `./m5_ver2/step4/step4.sh stop` — signals exactly the processes this run
   started, sweeps survivors by partition, and never touches PLCSIM or TIA.

## 9. When something looks wrong

| Symptom | Reading |
|---|---|
| Writer exits with API error `-4` | the PLCSIM instance is not running or is not named `PLC_2` — start it from the Control Panel; do not rename anything |
| `MOTOR STOPPED` with everything healthy | the latch. One **RESET** after every writer start is part of the design, not a fault |
| HMI opens all-red before the writer runs | correct: a display that has been told nothing shows the safe state; it clears within a tick of the writer starting |
| `forklift_io` logs `waiting for source data` every 5 s | expected forever: joint states and odometry are deliberately not bridged in this stack |
| Real-time factor well under 1 with the window open | the window is rendered in software on this machine; headless runs hold ~1.0 and nothing in the command path reads the clock rate |
| Topics exist but nothing moves | check `GZ_PARTITION` — the stack lives in `step4`, and a shell without it is looking at a different bus |
| A scanner shows PROTECTIVE in open space | it is looking at something real — the fields are 1.0/2.2/4.5 m by monitoring case, and case 3 (unreadable case) reaches 4.5 m. The vehicle's own structure is masked; see `field_eval.py`'s `SELF_MUTE` for how the mask was measured |

## 10. The wire, for reference

| Port | Direction | Payload |
|---|---|---|
| 5100 | Windows → WSL | `estop_healthy, motor, case, v_limit, ts` |
| 5101 | WSL → Windows | `pf, wf, pf_right, wf_right, pf_left, wf_left, enc_a, enc_b, ts` |

Both are JSON over UDP across the WSL/Windows seam; both sides apply their
own staleness rule, and silence on either wire is a demanded stop, never a
held value.
