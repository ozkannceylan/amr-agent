# EVIDENCE — the first build, running again without PLCSIM

**2026-08-21.** The PLCSIM Advanced trial has expired. This file records the
first build's stack running **as if the CPU existed**: the same 49-variable
address space, the same boot signature, the same monitored reset, the same
demands latching — served by [`virtual_plc/`](virtual_plc/), a software
stand-in that is **not a PLC and carries no safety integrity** (the same
sentence the stand-in writer said about itself).

Four artefacts, four transcripts. Everything below is copied from the runs,
not paraphrased.

## 1. Unit tests — the F-program and standard-program models (22 passed)

```
$ python -m pytest m5\m5_ver1\virtual_plc\test_virtual_plc.py -q
......................                                                   [100%]
22 passed, 1 warning in 0.43s
```

What they pin: the boot signature (both demands latch, torque off within 1 s,
speed monitor unarmed); a dead writer reads as an open world; the monitored
reset's full window (short press refused, over-long hold faults, boot press
faults, reset refused while a cause stands); the speed monitor's four causes
(discrepancy, frozen sequences, over-limit after the 2.3 s onset, shaft
doubt); the SS1 sequencer (torque off at a corroborated standstill vs by the
1 s timer); the safety coupling (a standing demand blocks teleop; the six
mirrors follow the F-statics every cycle); the teleop happy path and the
0.20 m/s warning ceiling; the writer role (commands, refusals, link
ownership, the stale reaper, Int16 range refusal, the pulse deadline).

## 2. Smoke test — the virtual PLC over the wire (9/9)

The virtual PLC running on Windows; the client on loopback. The command file
drove the e-stop and the monitored reset; the HMI's cycle was replayed over
OPC UA.

```
PASS namespaces resolve -- si=2 if=3
PASS all 43 browse paths resolve (the six mirrors did)
PASS boot signature: demands latched, torque off, speed monitor unarmed --
     {'EStopDemand': True, 'ZoneStopDemand': True, 'SafetyResetRequired': True,
      'SafetyResetFault': False, 'SpeedMonitorDemand': False, 'TorqueOffDemand': True}
PASS field link :45015 and speed link :45016 accepted the writer's wire protocol
PASS command file: estop close + reset pulse 300 cleared every demand --
     {'EStopDemand': False, 'ZoneStopDemand': False, 'SafetyResetRequired': False,
      'TorqueOffDemand': False}
PASS standard program: the boot latches cleared on the reset edge
PASS mode arbiter: TELEOP in force -- 1
PASS teleop energizes and the setpoint leaves zero --
     TeleopActive=True TractionSpeedRef=0.500
PASS estop open: the demand latches and motion dies --
     EStopDemand=True TeleopActive=False Ref=0.000
---
SMOKE PASS: 9/9 checks passed
```

## 3. The full stack, headless in WSL — `demo.sh up --headless` (READY in 42 s)

The virtual-PLC-era [`demo.sh`](demo.sh) generated its bridge/HMI configs
into the runtime dir (endpoint `opc.tcp://172.19.176.1:4841`, the Windows
host read back from the WSL default route), passed the Windows pre-flight on
the virtual PLC's own surface, and brought up the recorded composition:

```
pre-flight: the Windows side
  ok    powershell.exe  /mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe
  ok    virtual PLC is serving OPC UA on 4841 (m5/m5_ver1/virtual_plc -
  ok      a software stand-in, NOT a PLC, no safety integrity)
  ok    stand-in writer up: mutex Global\amr-standin-writer held,
  ok      listening on 45015 (field) and 45016 (speed)
---------------------------------------------------------------------
1/5 plant, vehicle, field evaluation, speed channels
  ok    simulation clock (gz server)  (/clock carried a message after 3s)
  ok    navigation lidar  (/forklift/scan carried a message after 4s)
  ok    obstacle_zone.py  (/forklift/obstacle/min_distance carried a message after 4s)
  ok    forklift_io.py  (/forklift/fork_height carried a message after 4s)
  ok    field_evaluation.py (warning verdict)  (/forklift/warning_field/occupied carried a message after 3s)
  ok    safe_speed_channels.py (reading head A)  (/forklift/drive_speed/channel_a carried a message after 2s)
2/5 envelope gate
  ok    envelope_gate.py (mode applied)  (/forklift/mode/applied carried a message after 5s)
3/5 bridge (OPC UA client of the CPU)
  ok    bridge session established (the CPU is in RUN and reachable)  (after 2s)
  ok    bridge startup rule R3 satisfied (all 7 inputs carry a real sample)  (after 3s)
5/5 HMI
  ok    HMI session CONNECTED with metrics on the page  (after 0s)

The controller's own view at this moment (read over OPC UA, not asserted):
    TorqueOffDemand        True
    EStopDemand            True
    ZoneStopDemand         True
    SpeedMonitorDemand     False
    SafetyResetRequired    True
    SafetyResetFault       False
    MotionEnable           False
    SpeedCeiling           0.0
    WarningFieldOccupied   False
    ProcessStopActive      True
    TeleopActive           False
    HmiLinkOk              True
---------------------------------------------------------------------
READY.
```

The boot table is the recorded demo's boot table: torque off, both demands
latched, reset required — and `WarningFieldOccupied False`, because the real
field evaluation in WSL was already feeding the virtual PLC's field link.

## 4. The drive — `drive_demo.py` (5/5)

The demo's first two minutes, replayed through the same two surfaces (the
writer's command file, the HMI's `POST /control`):

```
PASS boot: demands latched, process stop active
PASS the monitored reset cleared every demand and every latch
PASS mode arbiter: TELEOP in force -- DriveModeActive=1
PASS deadman on, traction 0.3: the vehicle MOVES in the warehouse --
     TeleopActive=True Ref=0.30000001192092896 LinearSpeed=0.30000001192092896
PASS estop open: the demand latches and motion dies --
     EStopDemand=True TeleopActive=False Ref=0.0
---
DRIVE PASS: 5/5 checks passed
```

`ForkliftLinearSpeed` is the PLC's own node, written by the bridge from the
Gazebo plant: the command path HMI → virtual PLC → bridge → Gazebo carried a
real 0.3 m/s.

## 5. Teardown — `demo.sh down` (verified clean, including the virtual PLC)

```
  ok    hmi / bridge / envelope / plant stopped on SIGTERM
  ok    no survivor process in partition m5demo
  ok    ros2 daemon stopped
  ok    no listener on 127.0.0.1:8088 / 8089
  ok    /dev/shm swept: 130 entries -> 2
the Windows side
  stopped writer pid 44968            <- the virtual PLC, matched by its
                                         command line (VIRTUAL-PLC ERA 4)
  ok    the stand-in writer is gone
  ok    Global\amr-standin-writer is free
  ok    nothing listening on 45015 / 45016
DOWN, AND VERIFIED CLEAN
```

## 6. The virtual PLC's own session log (excerpt)

`virtual_plc/logs/virtual-plc-20260821T220620Z-pid44968.log` — one file per
session, never truncated, the writer's rule:

```
22:06:21 | START     | OPC UA serving 49 nodes at opc.tcp://0.0.0.0:4841
22:06:50 | SPEEDLINK | up: speed source ('172.19.180.72', 42078) connected
22:06:51 | LINK      | up: field-evaluation client ('172.19.180.72', 39230) connected;
                        the zone channel now belongs to the field and is held FALSE
                        until its first ZONE line
22:08:30 | OPERATOR  | estop close -> EStopCircuitClosed := True
22:08:32 | OPERATOR  | reset pulse 2000 -> ResetButtonPressed := True now, False after
                        2000 ms (the F-program judges the hold)
22:08:34 | OPERATOR  | reset pulse elapsed -> ResetButtonPressed := False
22:08:39 | OPERATOR  | estop open -> EStopCircuitClosed := False
22:08:51 | LINK      | down (the field evaluation closed the connection);
                        ZoneDeviceCircuitClosed driven FALSE (open) AND
                        WarningFieldClear driven FALSE -- loss of the field source
                        reads as intrusion and as warning-occupied, never as a clear field
```

## What this evidence does NOT claim

- No safety integrity. The F-side is a behavioural model; the inputs are
  software; the runtime is CPython. The recorded demo had the same property
  (its F-inputs came from a PowerShell script) — see
  [PLC-PROGRAM.md](PLC-PROGRAM.md) §4.
- No cycle-time fidelity claim. The models run at the nominal 20/50/100 ms
  cadences with measured-period timers; nothing here proves hard real-time
  behaviour, exactly as PLCSIM Advanced proved none.
- The one deliberate difference from the commissioned surface: the OPC UA
  port is **4841**, not 4840 — the host's OPC UA Local Discovery Server owns
  4840, and the commissioned `192.168.53.1:4840` belonged to PLCSIM
  Advanced's virtual NIC, which no longer exists.
