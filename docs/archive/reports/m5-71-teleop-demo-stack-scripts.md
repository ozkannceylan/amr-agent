# m5-71 — one command up, one command down, for the teleop + safety demo

    brief:               docs/briefs/m5-71-teleop-demo-stack-scripts.md
    status:              done — demonstrated end to end against the live CPU,
                         not asserted
    invariants_touched:  none. The scripts start existing processes with their
                         existing configuration files and implement no behaviour.

## The one-line answer

**`./demo.sh up` and `./demo.sh down` exist, were run from a cold machine, and
the whole demonstration was driven through them: bring-up in ~30 s with every
readiness check on an observable, a teleoperated vehicle at 0.600 m/s, the
warning slowdown, the protective stop, the torque-off demand, the e-stop and
the monitored reset that recovers each — then a teardown that verified itself
clean on both sides of the seam.** Two defects were found by running rather
than by reading, and one of them is `stack.sh`'s and is left as a request.

## What was built

| File | What |
|---|---|
| `demo.sh` | **The deliverable.** `up`, `down`, `status`, `check`. Repo root, new file; `stack.sh` is untouched |
| `RUNBOOK.md` | One page, repo root, in the owner's order, including how to make each safety function act and the reset that recovers it |

`demo.sh` inherits `stack.sh`'s mechanisms deliberately — setsid process groups
with one PID file each, the command-line token check that makes a recycled PID
read as down, the zombie-aware liveness test, and the survivor sweep filtered
by this run's `GZ_PARTITION` out of `/proc/<pid>/environ`. **`SURVIVOR_PATTERNS`
is `stack.sh`'s eight entries reproduced verbatim and then extended** with
fourteen M5 processes; nothing was removed.

## The composition, and the one judgement call in it

The teleop stack is **one** `agv/forklift/launch/vehicle.launch.py` (world and
spawn pose passed, from `sim/launch/warehouse_bringup.launch.py`) plus
`envelope_gate.py`, `run_bridge.py` and `hmi_server.py`.

Two facts forced that shape and both are worth recording:

1. **`field_evaluation`, `safe_speed` and `safe_speed_link` are unreachable
   through either bringup file.** `warehouse_bringup` and `forklift_bringup`
   both pass an explicit argument list to `vehicle.launch.py` and none of the
   three is in it, so through them the field evaluation and the speed channels
   never start — and those two *are* the safety half. `safe_speed` also starts
   a second `ros_gz_bridge` the scripts cannot run without. The only committed
   file that declares all of them, and refuses their invalid combinations, is
   `vehicle.launch.py`.
2. **`envelope.launch.py` cannot be used here, for an invariant-10 reason.**
   It also starts `cmd_vel_to_tricycle.py`, which publishes
   `/forklift/cmd/steer_angle` and `/forklift/cmd/traction_speed` — *the same
   two topics the bridge publishes from the PLC's setpoints*. In autonomy that
   is the point; in teleoperation it is a second publisher on the PLC's own
   setpoints, and a converter that republishes a held command at a fixed rate
   (LESSONS 2026-08-04) would keep issuing one after the PLC withdrew it. So
   `envelope_gate.py` runs alone, with the command line
   `envelope.launch.py` gives it. It is not optional: it publishes two of the
   bridge's seven configured inputs, so without it R3 never completes.

The spawn pose is **parsed out of `warehouse_bringup.launch.py`** rather than
copied, and a failed parse is a hard stop — m5-69 moved that pose for a
measured reason and a copy would be a second place to forget.

## The seam: which side is whose, and how it is checked

The Windows half is the owner's, and `up` **refuses to begin** until it has
observed it. `check` (also `up`'s first act) asks one PowerShell call for four
facts: `powershell.exe` reachable, the PLCSIM Advanced runtime instance
process, the writer's named mutex `Global\amr-standin-writer` held (opened
with `TryOpenExisting`, so the probe cannot take it), and both 45015 and 45016
listening. If the writer is absent, `up` **prints the exact command and waits
for it** — observed working: `ok the stand-in writer is up on both listeners
(after 10s)`. If no `powershell.exe` is reachable at all, `up` refuses rather
than declaring a WSL-only stack ready.

**The writer is not started by the script, and that is a design decision, not
an omission.** It needs a real console: `estop open` / `estop close` /
`reset pulse 2000` are typed at its window, and a script-started writer logs
`operator console = UNAVAILABLE`. Starting it from `demo.sh` would produce a
demonstration in which no safety function can be made to act.

## Two defects found by running, both fixed in `demo.sh`

**1. `ros2 topic echo` against a cold CLI daemon fails in 1.1 s and looks like
a timeout.** The first `up` reported *"NOTHING PUBLISHED on
/forklift/mode/applied within 120s"*. Measured immediately afterwards: that
topic was publishing at **20.007 Hz**, and against a cold daemon
`ros2 topic echo --once` prints `does not appear to be published yet / Could
not determine the type for the passed topic` and **exits 1 in 1.102 s**. A
one-shot wait therefore reports a 120 s timeout after one second. This is the
2026-08-05 daemon-cache lesson in a new place, and it is the brief's own
hazard arriving inverted. `wait_topic` is now a retry loop to the deadline
that prints the tool's actual last error on failure.

**2. A Windows process sweep matched itself.** `stop_writer` matches on the
command line containing `standin_writer.ps1` — and the probe's *own* command
line contains that string, so it found two processes where one existed. `$PID`
is now excluded. The failure was caught because the verification is
independent of the action: the mutex and the two ports were checked separately
and correctly reported `STILL HELD` / `STILL LISTENING` while the kill had
matched nothing useful.

## What was observed, in order

Cold machine, PLCSIM instance `safecell3` read back from the API as
`OperatingState = Run` (read only; nothing in TIA was started, stopped or
changed, and no project was opened).

| Step | Observed |
|---|---|
| `check`, no writer | `FAIL stand-in writer NOT fully up (mutex=False 45015=False 45016=False)` — the refusal works |
| `up`, writer absent | printed the writer command, waited, proceeded 10 s after the writer appeared |
| bring-up | `/clock` 5 s, `/forklift/scan` 2 s, `obstacle_zone` 4 s, `forklift_io` 3 s, `field_evaluation` 3 s, `safe_speed_channels` 3 s, `mode/applied` 1 s, `session established` 1 s, `R3 satisfied` 2 s, HMI CONNECTED 0 s. **~30 s total**, idle machine |
| boot state, **read from the CPU** | `TorqueOffDemand True`, `EStopDemand True`, `ZoneStopDemand True`, `SpeedMonitorDemand True`, `SafetyResetRequired True`, `ProcessStopActive True` |
| monitored reset | `EquipmentPermit False->True` and `ProcessStopActive True->False` at 3.102 s; then **all five demands including `TorqueOffDemand` cleared in the same 50 ms sample** at 5.202 s |
| drive | `TeleopActive True`, `TractionSpeedRef 0.600`, **`ForkliftLinearSpeed 0.600 m/s`** — the positive control |
| **warning slowdown** | mid-drive and unscripted: `WarningFieldOccupied False->True`, reference `0.600 -> 0.120` (0.20 x command), vehicle complied to 0.120 m/s **with the command still held** |
| **e-stop** | `estop open` while moving: `EStopDemand False->True`, reference to `0.0`, `TeleopActive` dropped, speed `0.120 -> 0.0`. `TorqueOffDemand` did **not** form — as specified |
| **protective stop** | driving on: `ZoneStopDemand False->True`, `TeleopActive` dropped, reference `0.0`, vehicle stopped; **`TorqueOffDemand` formed 0.80 s later** (SS1's second stage) |
| **reset refused** | with the field still occupied, a full monitored reset changed nothing — `ZoneStopDemand` and `TorqueOffDemand` stayed TRUE. The field evaluation logged `INTRUSION — front: field not clear` throughout |
| **reset accepted** | vehicle repositioned with `set_pose` **and read back** (`[-3.000000 -5.500000]`); the next reset cleared `ZoneStopDemand`, `SafetyResetRequired` and `TorqueOffDemand` together, and the vehicle drove at 0.600 m/s again |
| `down` (partial stack) | 13 survivors found and swept — `gz sim`, two `parameter_bridge`, the four estimator processes, `sto_contactor`, `forklift_io`, `obstacle_zone`, `field_evaluation`, both safe-speed processes. This is exactly what `ros2 launch` leaves behind |
| `down` (full stack) | all five components on SIGTERM, one survivor needing SIGKILL, `no survivor process`, `ros2 daemon stopped`, no listener on 8088 or 8089, `/dev/shm swept`, writer stopped, **mutex free, 45015 and 45016 free** |
| independent verification, **not by `demo.sh`** | `pgrep` for the whole pattern set: nothing. `ss -ltnH`: only systemd-resolved and one unrelated 127.0.0.1:5345. `/dev/shm`: two lttng entries. 14 280 MB available (14 285 MB when the machine was handed over). Windows: `netstat` shows neither port, mutex `False`, zero writer processes |

**One behaviour the RUNBOOK now carries because it cost a run here:** after any
latch, a *standing* drive-mode request is not a re-entry. With the request held
across the reset, teleop never became active and the vehicle sat still with
everything else looking correct; with a fresh **None -> Teleop** edge it became
active in 0.6 s. This is m5-58 OQ2 arriving in a bring-up procedure.

## files_changed

| File | Status |
|---|---|
| `demo.sh` | new, repo root |
| `RUNBOOK.md` | new, repo root |
| `docs/reports/m5-71-teleop-demo-stack-scripts.md` | this report |

`stack.sh`, `plc/`, `agv/`, `bridge/`, `hmi/`, `sim/`, `viz/` and every config
file were **read and never written**. No dependency added. Nothing committed,
no branch. **Nothing in TIA Portal or PLCSIM Advanced was started, stopped,
downloaded, compiled or changed**; the only contact with either was two
read-only API calls (`RegisteredInstanceInfo`, `OperatingState`) to read back
the instance name rather than assume it. **No PL, Category, SIL or PFH is
claimed or implied anywhere in either file.**

Two untracked artefacts were written by the committed nodes themselves as a
side effect of running, as in m5-68 and m5-69:
`agv/forklift/evidence/field_evaluation/*.log` and a `speed-link/` sibling.
They are `agv/`'s to rule on and were left in place.

## Requests — work this brief could not do

| # | Request | Owner | Blocking? |
|---|---|---|---|
| 1 | **`stack.sh`'s environment guard cannot pass on this machine.** It runs `command -v gz` in the bare shell, but `gz` ships in the ROS overlay (`/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`) and does not exist until `setup.bash` is sourced. `stack.sh start` therefore dies with *"gz not on PATH"* on a machine where Gazebo works. `demo.sh` asks the sourced shell instead. One-line fix, but `stack.sh` is M4's gate artefact and editing it is a separate decision | infra, on an owner ruling | No — `demo.sh` is the M5 path |
| 2 | **`demo.sh` needs its executable bit set at commit time.** `core.filemode` is `false` on this checkout, so git will record `100644`. Commit it with `git update-index --add --chmod=+x demo.sh`, or the owner types `bash demo.sh` | orchestrator | No |
| 3 | **The monitoring service is off by default** (`--monitor` turns it on). `viz/monitor/service.py` prints that each context carries its own ROS domain, so whether it sees a run isolated by `ROS_DOMAIN_ID` was not established here, and the HMI treats it as optional. Somebody should settle it before a take that wants the map pane | `viz/` | No |
| 4 | **`docs/TODO.md` m4f-10's "readiness timeouts uncalibrated" item is answered for the M5 path** (every wait is now on an observable, with measured elapsed figures above) and still open for `stack.sh` | orchestrator | No |

## open_questions

1. **The protective stop that cannot be reset is a real stage hazard.** After
   stopping in front of an obstacle the vehicle is torque-off, so it cannot
   reverse out, and the reset is correctly refused while the field is
   occupied. The recovery is to move the obstacle or reposition the vehicle.
   The RUNBOOK carries it; whether the showcase should be staged to avoid it
   is a directing decision.
2. **Both contours reported intrusion at that stop** — front *and* rear,
   nearest rear return 2.908 m. Whether that is the aisle's real geometry or
   m5-68 finding 9's simulation-capacity effect was not investigated; it is
   `agv/` or `sim/` work either way.
3. **The bring-up figures are one idle draw.** ~30 s total on a machine with
   nothing else on it. m5-69 measured 6.1x under load, and the deadlines here
   are set generously for that rather than tuned to these numbers. They are
   observed values, not bounds.
4. **`SpeedChainSeen` was never exercised.** It is cleared only by a cold CPU
   start, which is the owner's action in PLCSIM, so `demo.sh` reports the fact
   at teardown and does nothing about it.

## next_suggested

Have the owner walk `RUNBOOK.md` once, on the real machine, with the writer in
a visible console rather than a hidden one — the only part of the procedure
not exercised here is a human's hands on the two keyboards at the same time,
which is precisely the step the monitored reset depends on.
