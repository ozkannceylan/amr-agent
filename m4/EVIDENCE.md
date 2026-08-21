# M4 Evidence — the commissioning cell, re-run against the virtual PLC

One page of proof that the Milestone-4 forklift commissioning cell still
runs today: the forklift arena in Gazebo (headless), `forklift_io.py`,
`obstacle_zone.py`, the bridge, and the HMI — all against the **virtual
PLC** (`m5/m5_ver1/virtual_plc/`) standing in for the expired PLCSIM
Advanced trial. The five gate criteria from `m4/README.md` are exercised
through the operator's own surfaces: the HMI's `POST /control` and
`GET /state`, the writer's command file, and the T5.4 obstacle stimulus
itself (`sim/scenarios/forklift_stimulus.py`).

## What ran

| Piece | Role |
|---|---|
| `m5/m5_ver1/virtual_plc/virtual_plc.py --no-console --command-file C:\Temp\m4_cmds` | the CPU: M5-commissioned build (section-7 core = the M4 program) |
| `m4/run_commissioning.sh start` | WSL stack: arena + `forklift_io` + `obstacle_zone` + warning-clear publisher + bridge + HMI |
| `m4/verify_commissioning.py --command-file C:\Temp\m4_cmds` | the exercise, from Windows, through the HMI's HTTP API |

The bridge config is `m4/bridge.forklift.virtual.yaml` — the M4-era
`forklift` group **plus the `warning` group**, because the commissioned
CPU's section 14.17 reads `ForkliftWarningFieldOccupied`. The exercise
drives the warning field clear so the M4-era speed caps are the ones on
show. This is the documented divergence: the M4 CPU had no warning field.

## Console log — fresh CPU, 2026-08-22

```
PASS boot: the F-program's demands stand (the M5-era CPU's signature) -- {"EStopDemand": true, "ZoneStopDemand": true, "SafetyResetRequired": true, "TorqueOffDemand": null}
PASS the monitored reset cleared every demand and every latch -- {"EStopDemand": false, "ZoneStopDemand": false, "ForkliftResetRequired": false, "ForkliftProcessStopActive": false}
PASS mode arbiter: TELEOP in force (section 14.8 — the M5 addition) -- DriveModeActive=1
PASS (a) teleop drive: the vehicle moves under the PLC's setpoint -- TeleopActive=True Ref=0.30000001192092896 LinearSpeed=0.30000001192092896
PASS (b) the fork rises on command -- ForkHeight=1.583033800125122
PASS (b) the soft travel limit zeroes the setpoint while the demand stands -- height=1.583 ForkSpeedRef=0.0 (FORK_TRAVEL_MAX 1.55)
PASS (c) fork above 0.50 m: traction capped at 0.30 m/s, limit lamp on -- Ref=0.30000001192092896 SpeedLimitActive=True
PASS (c) fork back below 0.50 m: the cap lifts -- ForkHeight=0.4225113093852997
PASS (d) the crate in the stop zone: latch, override, zeroed setpoints -- ObstacleStopActive=True MinDistance=1.0126429796218872
PASS (d) reset refused while the cause stands
PASS (d) crate clear + fresh reset edge: latches clear, nothing resumes
PASS (e) HMI dead: its link verdict drops and the setpoints die -- HmiLinkOk=False Ref=0.0 TeleopActive=False ResetRequired=True
---
COMMISSIONING PASS: 12/12 checks passed
```

Notes on the numbers:

- **(a)** the request is an axis; the PLC multiplies by
  `TRACTION_SPEED_MAX` (1.00 m/s), so 0.3 in → 0.3 m/s out, and the
  measured `ForkliftLinearSpeed` matches the setpoint.
- **(b)** the fork climbs at `FORK_SPEED_MAX` 0.15 m/s; the PLC zeroes
  the setpoint the scan it sees `ForkHeight >= 1.55`, and Gazebo's
  integration carries the joint to 1.583 before it stops — the criterion
  is the zeroed setpoint with the demand still standing, and it held.
- **(c)** `TRACTION_SPEED_CAP_RAISED` is 0.30 m/s with the fork above
  `FORK_HEIGHT_SLOW_THRESHOLD` 0.50 m; the cap lifts when the fork comes
  back down.
- **(d)** the vehicle drove at 0.8 m/s from the spawn end of the aisle;
  the zone tripped at 1.01 m from the crate face (`OBSTACLE_STOP_DISTANCE`
  1.20 m), the latch stood, the reset was refused while the crate stood,
  and a fresh reset edge after `--to-x 8.0` cleared everything with no
  auto-resume.
- **(e)** the HMI was SIGTERMed; within the 500 ms heartbeat window plus
  one scan, `HmiLinkOk` fell and the traction setpoint died with it —
  read directly off the PLC over OPC UA, the watch table's role.

## Regression

The M4 exercise runs against the same virtual PLC build as M3 and
M5 ver1. After the M4 run, the M5 ver1 smoke test still passes against
this binary — see `m5/m5_ver1/EVIDENCE.md` (the smoke suite is the
regression net for all three milestones' shares of the CPU).

## What is not reproduced

- **The real F-CPU.** The M4 CPU was a standard-only S7-1516; the virtual
  PLC runs the M5-commissioned build. The boot demands, the monitored
  reset, and the mode arbiter are F-program behavior the M4 operator
  never saw — the exercise names them as such rather than hiding them.
- **The T5 watch-table captures.** The 2026-08-16 rehearsal's evidence is
  the showcase video (`assets/teleop-showcase.mp4`) and the T5 report in
  `docs/commissioning/`; this file is the *today* evidence.
- **GUI windows.** Everything above ran headless; the HMI was driven
  through its own HTTP API, which is what the page itself uses.
