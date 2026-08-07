# VALIDATION — M5, the safety chain end to end

> ## THIS DOCUMENT BELONGS TO F-COLLECTIVE SIGNATURE `29FD2C52`
>
> **Every figure below was measured on 2026-08-07 against the program now on
> the CPU.** The previous issue of this document was measured against
> `50573CD9` and **not one of its figures survives here**: each was either
> re-measured against `29FD2C52` or deleted. If you are holding a number from
> the earlier issue, it is a number about a program that is not running.
>
> The signature changed because `plc/forklift/TIA-FIX-PROCEDURE.md` ran to
> 63/63 on 2026-08-07: three F-program constants moved, the standard program
> gained two mirror copies, a third permissive conjunct and a teleop speed
> clamp, and the server interface gained two leaves.

**What this document is.** The record of the whole chain run against the fixed
safety program. It is written to be narrated from: each section says what was
asked, what was observed, the numbers with their n, and a plain verdict. Where
something is proven it says so; where it is not, it says that in the same voice.

**Run identity.** 2026-08-07, 06:35–07:40 UTC. CPU `1513F-1 PN` on PLCSIM
Advanced instance `safecell3`, project `safe_amr`, collective F-signature
`29FD2C52` (offline = online, recorded at step 22 of the fix procedure).
**Nothing was downloaded, compiled or changed in TIA for this run and no
project was opened.**

**No layer in this run is a double.** The stand-in writer is
`bridge/standin_writer/standin_writer.ps1` against the real PLCSIM Advanced
API; the CPU is the real CPU; the HMI is `hmi/hmi_server.py` with its real OPC
UA session; the scanners are two `gpu_lidar` devices in Gazebo and the field
evaluation is `agv/forklift/scripts/field_evaluation.py`; the speed readings
are `safe_speed_channels.py` on the simulated shaft carried by
`safe_speed_link.py`; the vehicle is the Gazebo model with its own estimator
and its STO contactor; the bridge is `bridge/run_bridge.py` on the committed
`bridge/config/bridge.yaml`, unedited for this run. The only thing replaced
anywhere is the **operator's keyboard**: the HMI page's `POST /control` loop and
the writer's console are driven from files so a command can be held steady for
a measured interval unattended. Both go through the committed code paths, with
the committed payload, the committed vocabulary and the committed refusals.

---

## The claim boundary, and it applies to every number below

This project claims **PLr targets only**. **No Performance Level, Category,
SIL or PFH is claimed, achieved or implied anywhere in this document**, for any
function, layer or figure. The whole safety *input* path is a labelled
stand-in: the scanner verdict is Python arithmetic over rendered depth images,
it reaches the safety program as **standard data** written by an engineering
process over a TCP link, and the encoder is one simulated shaft read twice.
None of that buys integrity, and no reaction time here is a figure any machine
is characterised by.

**Two rules govern every claim below.**

1. **Stillness is not evidence.** A stopped process and a genuine inhibit are
   indistinguishable by motion (LESSONS 2026-08-06). Every claim that something
   did *not* happen carries a **positive control in the same run**, and where a
   run lost its control it is discarded below rather than repaired.
2. **Every figure states its n**, and where a figure is one draw it says so.

---

## The verdicts at a glance

| | Verdict | n |
|---|---|---|
| **The shaft-doubt band is closed** (§3.1) | **PROVEN** — 30.0 s of creep inside the old band, 0 demands | 1 run, 262 F-samples |
| **The scanner stops the vehicle** (§1.1, §5) | **PROVEN** | 3 latches, 2 with the transition sample recorded |
| **The scanner SLOWS the vehicle in teleop** (§1.2) | **PROVEN — new, and it is what F4 was for** | 3 trips |
| **The torque-off demand reaches the plant** (§6.2) | **PROVEN LIVE against the CPU**, no double anywhere | 6 episodes, 95 475 refused commands |
| **The e-stop stops it** (§2) | **PROVEN** | latency n = 3; operator-to-standstill n = 2 |
| **Everything latches; recovery is a monitored reset with the cause gone** (§0.3, §2) | **PROVEN** | 9 accepted, 3 refused with the cause standing |
| **The boot state** (§0.1) | **MEASURED**, two new rows | 100 samples |
| **SS1's second stage** (§6.1) | **MEASURED** | 2 |
| **AT-10, over-limit → demand** (§6.1) | **NOT RE-MEASURABLE** — the clamp now keeps the vehicle inside the limit, so the limit was never exceeded | 0 |
| **An autonomous mission** (§3.2) | **NOT ACHIEVED**, and the cause has moved | 2 attempts |
| **Safety during an autonomous run** (§4) | **NOT RUN** — blocked by §3.2 | 0 |

---

## 0. What was standing before anything was asked of it — MEASURED

The chain was brought up in this order, and the order is load-bearing:
stand-in writer → Gazebo arena and vehicle → field evaluation → obstacle zone →
speed channels and their carrier → envelope gate and vehicle I/O → bridge →
HMI.

### 0.1 The cold controller, read before any client wrote anything

Read over the CPU's own OPC UA server with
`bridge/tools/observe_safety_mirrors.py`, **with no writer, no bridge and no
HMI running** — 100 samples at 5 Hz over 20.0 s, every one identical
(`bridge/evidence/m5-68-mirrors-boot0.csv.gz`):

| Node | Value | Note |
|---|---|---|
| `Forklift/Safety/EStopDemand` | `True` | |
| `Forklift/Safety/ZoneStopDemand` | `True` | |
| `Forklift/Safety/SafetyResetRequired` | `True` | |
| `Forklift/Safety/SpeedMonitorDemand` | `False` | **new leaf, this signature** |
| `Forklift/Safety/TorqueOffDemand` | `True` | **new leaf — it boots demanding** |
| `Forklift/Envelope/ForkliftMotionEnable` | `False` | |
| `Forklift/Envelope/ForkliftSpeedCeiling` | `0.0` | |
| `Forklift/Envelope/ForkliftEquipmentPermit` | `False` | |
| `Forklift/ProcessStop/ForkliftProcessStopActive` | `True` | |
| `Forklift/Status/ForkliftResetRequired` | `True` | |
| `Forklift/Mode/ForkliftDriveModeActive` | `0` (None) | |

**n = 100 samples, 0 transitions.**

**That is the designed boot state and it is worth saying out loud:** a cold cell
starts with every demand latched, torque removed and nothing permitted, and it
takes a deliberate operator sequence to open. Nothing in this run started
permissive. **`TorqueOffDemand` booting `TRUE` is the vehicle booting deaf**,
and it is intended (`opcua-nodes.md` §11.6 start values).

**Six leaves, no `_1`.** `bridge/tools/probe_server_paths.py` browsed
`Forklift/Safety/` and read back exactly six children — `EStopDemand`,
`SafetyResetFault`, `SafetyResetRequired`, `SpeedMonitorDemand`,
`TorqueOffDemand`, `ZoneStopDemand` — against the four the previous signature
advertised. `Link/BridgeLinkOk` is still not addressable (`BadNoMatch`), which
is unchanged and is carried in §7.

### 0.2 One thing the boot read that is NOT a start value, and it matters

`Forklift/Input/ForkliftObstacleInStopZone` read **`False`** in that capture,
and `Forklift/Warning/ForkliftWarningFieldOccupied` read **`True`**. Neither is
a fresh verdict and neither is a DB start value being displayed: **no client
had written anything**, so both nodes were holding the last value written by
the *previous session's* bridge, across a download that did not move their DB
layout.

One of the two is holding in the **permissive** direction. **"Not yet written"
is not "clear."** The instrument that separates the two cases is
`Link/BridgeHeartbeat` advancing, and in that capture it read `0` for all 100
samples. Nothing in this run rests on either value; it is recorded because a
lamp fed from either node between sessions would have been lying.

### 0.3 What it took to open the cell, and both halves were needed

Two things had to be true before a monitored reset was accepted, and the first
attempt failed for want of them:

1. **The e-stop circuit had to be closed at the writer.** The writer boots with
   `EStopCircuitClosed = False` — open, the fail-safe pre-connection state, and
   *wire NC, program NO* makes an open circuit a demand. A first reset attempt
   with the circuit still open changed **nothing**: 940 samples over 94 s, **0
   transitions on any of the 21 state columns**. **A reset cannot clear a cause
   that is still standing**, and that is the discipline working, recorded as a
   measurement rather than asserted.
2. **The HMI's process stop had to be released.** `ForkliftProcessStopActive`
   stood `True` from the boot state and the standard program forms no permit
   under it.

**The bridge's own startup rule R3 was satisfied without incident**, because
`obstacle_zone.py` was started before the bridge: the heartbeat was withheld for
1.7 s while 7 of 7 configured inputs had no real plant sample yet, each named in
the bridge's log, and began advancing at 1 the moment the last arrived.

**`SpeedChainSeen` cost nothing this session.** The fix procedure's step 26 had
read it `FALSE` after the download's STOP → RUN, and no speed source had run
between that step and this run, so the chain was cold when the carrier came up.

**And the warning-field hazard was planned into the order rather than met.**
The field evaluation was started before any reset was attempted, so
`WarningFieldClear` was already `True` (writer log, 06:40:55.920) and the
reduced limit was not in force.

With the e-stop closed, the process stop released and the field source live, one
monitored reset at the writer (`reset pulse 2000`) with the HMI reset request
held across the same interval cleared everything:

| t [s] into capture | UTC | What changed |
|---|---|---|
| 11.902 | 06:49:27.838 | `ForkliftEquipmentPermit` `False` → `True`; `ForkliftResetRequired` `True` → `False`; `ForkliftProcessStopActive` `True` → `False` |
| 13.903 | 06:49:29.838 | `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired` and **`TorqueOffDemand`** all `True` → `False`, **in the same 100 ms sample** |

The `TorqueOffDemand` row is new to this signature: the SS1 sequencer's second
stage releasing is now visible as a node, and it is the first time this project
has watched torque restored from the controller's own view.

**Across the whole session, 9 monitored resets were accepted and 3 were refused
with their cause still standing** — this first attempt (e-stop circuit open),
one with the protective field still occupied after the vehicle had driven into
it, and §2's (circuit open again).

---

## 1. V1 — the scanner: does it slow, and does it stop?

### 1.1 It stops — PROVEN

Three protective latches were formed this session, all in teleoperation with the
operator's command held: run `v1r1` (0.5 of full scale), run `v5r1` (**1.0, full
scale**, §5) and run `at10r1` (a full-lock turn, §6.3). **Two of the three have
the transition sample recorded**; `v1r1`'s stop fell in a gap between two
captures, so that run proves the stop by its before-and-after state and
**contributes no timing or distance figure**.

The fully recorded one is `v5r1` and it is §5's table. In summary, read off the
CPU's own OPC UA server at 20 Hz (`bridge/evidence/m5-68-mirrors-v5r1.csv.gz`):

| t [s] | UTC | `ObstacleMinDistance` [m] | `TractionSpeedRef` | plant [m/s] | `ZoneStopDemand` |
|---|---|---|---|---|---|
| 42.203 | 07:17:20.177 | 1.514 | 0.20 | 0.200 | False |
| **42.253** | **07:17:20.227** | **1.514** | **0.0** | 0.200 | **True** |
| 42.402 | 07:17:20.377 | 1.474 | 0.0 | 0.055 | True |
| **42.502** | **07:17:20.477** | **1.468** | **0.0** | **0.0** | True |
| 43.203 | 07:17:21.178 | 1.468 | 0.0 | 0.0 | True + **`TorqueOffDemand` True** |

**Observed.** The protective verdict opened the zone channel at the writer, the
F-program latched `ZoneStopDemand`, the standard program dropped
`ForkliftTeleopActive` and drove the traction setpoint to `0.0` **in the same
50 ms sample**, the vehicle stopped **0.25 s later**, and the SS1 sequencer took
torque off **0.95 s after the demand**. The distance never changed again for the
remaining 40 s of the recording.

**The latch holds and nothing resumes by itself.** The operator's full command
was **never released** and the vehicle stayed stopped. Recovery required a
monitored reset with the field clear.

**n.** 3 latches; 1 measurement of the stopping interval and the standstill
distance. Those two are **one draw**, from one approach, at one speed, along one
heading, against one obstacle.

### 1.2 It SLOWS — PROVEN, and this is new

The previous issue of this document recorded, correctly for that build, that the
warning field did **not** slow a teleoperated vehicle: the ceiling bounded the
autonomous envelope only. `plc/forklift/SPEC.md` §14.17, applied in this
signature, puts the warning ceiling into the teleop setpoint. **It works, and it
was observed three times.**

| Run | operator's request | speed held | at the warning trip | speed after the clamp | time to comply |
|---|---|---|---|---|---|
| `v5r1` | **1.0, full scale** | 1.000 m/s | `TractionSpeedRef` 1.0 → **0.20** in the **same 50 ms sample** as `WarningFieldOccupied` going `True` | **0.200 m/s** | **0.40 s** |
| `v1r1` | 0.5 | 0.500 m/s | 0.5 → **0.10**, same 100 ms sample | 0.100 m/s | 0.30 s |
| `v2r3` | 0.25 | 0.250 m/s | 0.25 → **0.05** | 0.050 m/s | ≈ 0.25 s |

*(`v2r3`'s capture did not carry the `ForkliftWarningFieldOccupied` column, so
its clamp is recorded by the setpoint change alone and no same-sample claim is
made for it. The two same-sample claims above are `v5r1` at 20 Hz and `v1r1` at
10 Hz.)*

**Read the second column before quoting the third.** The clamp bounds the
**scale**, not the request: the delivered speed is *the operator's normalised
request × `WARNING_SPEED_CEILING` (0.20 m/s)*. **At full command it is exactly
0.20 m/s** — the figure the fix was specified to produce — and at half command
it is 0.10 m/s. A showcase clip must therefore be a **full-command** clip if the
narration says "it drops to 0.20".

**No `SpeedMonitorDemand` formed in any of the three.** That is the other half
of what F4 bought: the F-side limit selector goes to 300 mm/s the moment the
warning field is occupied, and the standard program complies well inside the
`SPEED_LIMIT_ONSET_MAX` budget of 2.30 s — 0.40 s at worst, measured. **Slowing
replaced latching**, which is exactly the choice `m5-59` §3 argued.

**n = 3 trips.** One at full command.

### 1.3 The control case — the object outside both contours

At startup, with the racks in view and the vehicle at rest, the field evaluation
logged both verdicts clear in its own words — *"warning field CLEAR — both
devices report the warning field clear (front 0 ray(s) inside, rear 0)"* — and
the controller read `ZoneStopDemand` `False` and `ForkliftWarningFieldOccupied`
`False` for the whole of the `reset0` capture: **940 samples, 0 transitions**.
**The scanners see the world and say nothing about it until something crosses a
contour.**

---

## 2. V2 — the e-stop — PROVEN

The cell e-stop, through the real chain: the writer opens
`SafetyInputStandIn.EStopCircuitClosed` (wire NC, program NO — an open circuit
is the demand), the F-program latches `EStopDemand`, the standard program
withdraws the setpoint, the plant stops. **The operator's forward command was
still being posted throughout**, at the page's own 5 Hz.

| | run `v2r1` | run `v2r3` |
|---|---|---|
| speed held before the demand | 0.250 m/s | 0.050 m/s (clamped by the warning field) |
| operator opens the circuit (writer log, UTC) | 07:20:18.393 | 07:24:04.996 |
| `EStopDemand` `TRUE` at the OPC UA server | 07:20:18.464 | 07:24:05.037 |
| circuit → demand | **71 ms** | **41 ms** |
| `TeleopActive` `FALSE` and `TractionSpeedRef` `0.0` | same 50 ms sample as the demand | same 50 ms sample |
| plant speed reads `0.0` | 07:20:18.664 | 07:24:05.237 |
| **operator's action → standstill** | **271 ms** | **241 ms** |

A third opening, in run `v2r2`, gave **79 ms** circuit → demand. **The
circuit → demand figure is n = 3; the operator-to-standstill figure is n = 2,
and the two draws are at different speeds**, so they are two observations and
not a repeat.

**Run `v2r2`'s e-stop leg is discarded, not repaired.** Its mode-request edge
was consumed before the drive command, so `ForkliftTeleopActive` never came up
and **the vehicle was not moving when the circuit opened**. A stop observed
under those conditions is indistinguishable from a machine that was already
still, and this document does not report it as a stop. What that run *does*
carry is listed below, because none of it depends on prior motion.

These figures are observed through the writer's 50 ms cycle, the F-cycle, the
standard cycle, OPC UA and the bridge, at a 50 ms polling period. They are the
**chain's** end-to-end latency in this simulation. They are not a machine's
stopping performance and they carry no integrity claim of any kind.

**The positive controls.** In `v2r1` the identical command held the vehicle at
0.250 m/s for 11.5 s immediately before the demand. In `v2r3` the identical
command drove it at 0.250 m/s for 8.8 s immediately before. In `v2r2`, after
recovery, the identical command moved it again at 0.250 m/s. Stillness is not
being read as evidence in either reported run.

**Nothing resumes by itself, and the reset discipline holds.** Three separate
observations:

- In `v2r1`, `estop close` alone — the circuit restored, no reset — left
  `EStopDemand` `TRUE` for the following **12.0 s**, until a reset was actuated.
  **Restoring the device is not a reset.**
- In `v2r2`, a monitored reset was actuated **while the circuit was still
  open**. It was refused: `EStopDemand` and `SafetyResetRequired` both stayed
  `TRUE` for the following **22.2 s**. **A reset cannot clear a cause that is
  still standing.**
- In both runs the circuit was then closed and the reset actuated again, and the
  latches cleared **2.12 s** (`v2r1`) and **2.14 s** (`v2r2`) after the
  actuation began — the 1.5 s hold plus the release plus a cycle. **Cleared on
  the release, with the cause gone — not on the press.**

### 2.1 What the e-stop deliberately does NOT do, observed three times

**`TorqueOffDemand` did not form on any e-stop**, in any of the three openings,
across 12–26 s of standing demand each. That is not a gap: it is the
specification. `plc/forklift-safety/SPEC.md` gives `Ss1Demand` as
`ZoneStopDemand OR SpeedMonitorDemand` and says of `EStopDemand` — *"deliberately
absent: the cell e-stop stops no vehicle (SRS B4, owner ruling 2026-08-06)"*.
The vehicle is stopped by the standard program withdrawing the setpoint, and the
cell's e-stop is a cell function.

**Say this on stage, because the mirrors will show it.** The e-stop stops the
vehicle; it does not remove its torque. The protective field does both.

---

## 3. V3 — the shaft-doubt band, and the autonomous mission

### 3.1 The band is closed — PROVEN, and this is the run that opened all the others

Against `50573CD9` a healthy vehicle creeping at 0.02 m/s latched
`ShaftDoubtNow` → `SpeedMonitorDemand` → `Ss1Demand` → `TorqueOffDemand` within
five seconds, because the F-side near-zero window `SPEED_STANDSTILL_MAX` was
50 mm/s while the vehicle's motion observation called it moving above ≈ 2 mm/s.
Every speed in that gap read as *moving with a still shaft*, and Nav2's
from-rest speed of 25 mm/s is inside it. The fix session took the window to
**15 / −15 mm/s** (`plc/forklift-safety/SPEC.md` §11.1b).

**The reproduction was re-run exactly as specified and it does not reproduce.**
Run `creep1`, one continuous recording, two independent witnesses that cannot
echo each other: the CPU's OPC UA server at 10 Hz
(`bridge/evidence/m5-68-mirrors-creep1.csv.gz`) and the F-program's own statics
through the PLCSIM Advanced API
(`bridge/evidence/m5-68-consumer-creep1.log.gz`), which the OPC UA server does
not publish at all.

The operator held a 0.02 m/s teleop creep for **30.0 s** (`TractionSpeedRef`
`0.02` from 06:51:08.574 to 06:51:38.575; plant `LinearSpeed` `0.020` across the
same interval; ground truth moved the vehicle 0.595 m, which is 0.0198 m/s).

**The precondition was met — this is the control that makes the negative mean
something.** Over the creep window, **n = 262 samples** of the F-program's own
statics:

| Reading | min | max | mean | median |
|---|---|---|---|---|
| `SpeedReadingA` \|mm/s\| | 0 | 37 | 19.8 | 18.0 |
| `SpeedReadingB` \|mm/s\| | 4 | 33 | 18.8 | 18.0 |

- samples with **at least one** reading in the old 15–26 mm/s band: **250 of 262**
- samples with **both** readings in it: **176 of 262**
- samples with both readings inside the **new** window (< 15 mm/s): **7 of 262**

The vehicle spent the run squarely inside the band that used to stop it.

**And the demand did not form:**

| F-program static | TRUE in |
|---|---|
| `ShaftDoubtNow` | **6 of 262 samples** |
| `ShaftDoubtTimer.Q` | **0 of 262** |
| `SpeedMonitorDemand` | **0 of 262** |
| `Ss1Demand` | **0 of 262** |
| `TorqueOffDemand` | **0 of 262** |
| `SpeedOverLimitNow` | 0 of 262 |
| `SpeedStaleNow` | 0 of 262 |
| `SpeedDiscrepantNow` | 0 of 262 |
| `MotionPresentValid` | **262 of 262** |

**The positive control is inside the same run, and it is better than an external
one.** `ShaftDoubtNow` *did* assert three times — at 17.059 s, 27.565 s and
39.115 s of the consumer capture — for **115 ms, 112 ms and 465 ms**. The doubt
term is alive, evaluated every F-cycle and still capable of forming; what changed
is that it no longer *holds* for the 1 s `SHAFT_DOUBT_TIME`, so the timer never
expires and no demand is latched. This is not a monitor that has gone quiet: it
is a monitor whose window no longer contains a healthy vehicle. That the chain
can still run to completion on this build is shown independently in §6.3, where
a shaft-doubt demand did form and did reach torque-off.

**Verdict: PROVEN. The band is closed.** n = 1 run, 262 F-program samples, 30.0 s
of continuous creep inside the old band, 0 demands.

**What this does not cover**, and it is on the record rather than fixed:
`plc/forklift-safety/SPEC.md` §11.1b's own not-covered table stands, and §6.3
below is one of its rows arriving in a live run.

### 3.2 The autonomous mission — NOT ACHIEVED, and the cause has moved

**The band is no longer what stops a mission.** Two attempts were made and
neither reached the failure the previous issue described.

| # | What was asked | What happened |
|---|---|---|
| `v3r1` | goal world (−1.0, −3.0) from the spawn pose, envelope confirmed open first (`ForkliftMotionEnable` `True`, ceiling 0.60 m/s, `ForkliftDriveModeActive` `2`) | Goal **ACCEPTED**. **0 plans published** in 100 s. The vehicle never moved, and **no safety demand formed at any point** — the envelope stayed open for the whole attempt. The vehicle's start pose is at the very corner of the committed grid (map ≈ (0.03, 0.04) on a 30.3 × 20.5 m map), and the planner runs `allow_unknown false` with a footprint whose inscribed radius is 0.769 m, so the start straddles the grid boundary and no path exists from it |
| `v3r2` | the vehicle repositioned to world (4.0, 0.0) — map ≈ (10.03, 5.51), well inside the grid — with the pose read back, AMCL re-seeded, latches cleared and the envelope reopened | **The goal was never issued.** `/navigate_to_pose` had gone: `planner_server`, `bt_navigator` and the three vehicle-side processes had died between the mode entry and the send, and two relaunch attempts did not bring the action server back inside the session. **This attempt produced no result and is reported as not run, not as a failure to navigate** |

**So the honest position is narrower and more useful than before.** The
threshold band that stopped every mission in its first metre is gone (§3.1). The
mission is now blocked by two things that are not safety at all: **a start pose
outside the region the committed planner will plan from**, and **this machine's
inability to hold the autonomy stack up beside Gazebo, the bridge, the HMI and
PLCSIM**. Neither was measured as a safety behaviour and neither is claimed as
one.

**The autonomous envelope itself was observed working**, three times, and that is
worth separating from the mission: `ForkliftDriveModeActive` `2`,
`ForkliftMotionEnable` `True` and `ForkliftSpeedCeiling` `0.60` came up together
in the same 100 ms sample on each entry, and in `v3r1` the ceiling was seen
falling **0.60 → 0.20 in the same sample** as `ForkliftWarningFieldOccupied`
going `True`, and returning to 0.60 when it cleared. The envelope, the mode
arbitration and the warning ceiling are all live in autonomous mode. What has
not been shown is a vehicle driving under it.

### 3.3 The capacity finding, and it cost this session two runs

`field_evaluation.py` requires a scan younger than 0.30 s on its own steady clock
and reads anything older as an intrusion. Under the load of launching Nav2 beside
Gazebo, the bridge, the HMI and PLCSIM, the 10 Hz scan stream stalls past that
window. Counted from the node's own log over the whole session: **16 intrusion
transitions, of which 3 are genuine** — the three protective stops of §1.1 — and
**13 are fail-safe trips on freshness**, 5 of those reporting *"the simulation
clock has not advanced for 0.3–0.4 s"*, each lasting 20–50 ms. In the same
session the writer recorded **13 motion-observation gaps** — *"no MOT line for
250 ms"* — and under the Nav2 launch the combination latched
`ZoneStopDemand`, `SpeedMonitorDemand` and `TorqueOffDemand` while the vehicle
stood still, which is what refused the first autonomous mode entry.

**The nodes are behaving correctly** — a scanner that has stopped talking must
read as occupied, and an unobservable vehicle must read as moving. What is being
reported is that **this machine cannot feed them reliably while the autonomy
stack starts**. It is a simulation-capacity finding and it bounds what one
recorded take can contain.

---

## 4. V4 — safety while driving under Nav2 — NOT RUN

The test as written requires the vehicle to be **driving under Nav2** when an
object enters the protective field. No Nav2 mission moved the vehicle this
session (§3.2), so the test was not staged and **no result is claimed for it**.

What *is* known about the two halves it would have joined, both measured above:

- **The protective field stops the vehicle and takes its torque off** — §1.1,
  §5, three latches, and the torque-off reaches the contactor (§6.2);
- **The autonomous envelope is published, is withdrawn on a demand, and carries
  the warning ceiling** — §3.2, three mode entries and one live 0.60 → 0.20
  ceiling change under autonomous mode.

Joining the two now needs a start pose inside the planner's region and enough
machine to hold the stack up — **not a program change**. That is a smaller gap
than the previous issue reported, and it is not a safety gap.

---

## 5. V5 — the operator drives at a wall — PROVEN, n = 1 at full command

**This is the owner's own test and it is the strongest result in the set.** The
operator holds a full-scale forward command from the real HMI page and drives
straight at a rack. **The command is never released.**

Run `v5r1`, one continuous 20 Hz recording of the CPU's own view
(`bridge/evidence/m5-68-mirrors-v5r1.csv.gz`), from a staged start at world
(2.000, −5.500) read back before the run.

| | `v5r1` |
|---|---|
| operator's request | **1.0, full scale, held throughout** |
| speed reached and held | **1.000 m/s**, reached 0.40 s after the setpoint |
| distance driven under that command before anything intervened | **10.83 m** (world x 2.000 → 12.832, ground truth) |
| distance at which the **warning** field occupied | **3.467 m** |
| `TractionSpeedRef` 1.0 → **0.20** | **the same 50 ms sample** as the warning trip |
| speed through the warning field | **0.200 m/s** — reached 0.40 s after the trip, held for 8.50 s |
| distance at which `ZoneStopDemand` latched | **1.514 m** |
| `TeleopActive` `False`, `TractionSpeedRef` → `0.0` | **the same 50 ms sample** as the demand |
| **closest approach** | **1.468 m** |
| stopping distance after the trip | **0.046 m** |
| time from trip to standstill | **0.25 s** |
| `TorqueOffDemand` `True` | **0.95 s** after the demand |
| operator's command at standstill | **still held**, for the remaining 40 s |

**Positive control, in the same run.** The same command, from the same page,
drove the vehicle **10.83 m at 1.000 m/s** in the seconds before the stop. The
vehicle was demonstrably not merely parked, and the stop is attributable to the
field.

**The warning field DID slow it, and that is the change from the previous
issue.** The vehicle met the warning contour at 1.000 m/s, fell to 0.200 m/s in
0.40 s, crossed the remaining 1.95 m at the reduced speed and stopped 1.47 m
short of the obstacle with 0.046 m of overshoot after the trip. **Slow first,
then stop** is now the true sentence, in teleoperation, at full command.

**One honest note on what these figures are.** They are the whole chain's
behaviour in this simulation, at this scan rate, on this machine, against one
obstacle at zero approach angle, unladen, with the steering straight. They are
**one draw**. They are not a stopping performance, not a safety distance
calculation, and they support no PL, Category, SIL or PFH claim.

---

## 6. The speed monitor, the SS1 sequencer, and the demand reaching the plant

### 6.1 AT-10 — the over-limit could not be re-measured, and the reason is the fix working

`SpeedOverLimitNow` was **FALSE in every sample** of the `at10r1` capture of the
F-program's own statics (`bridge/evidence/m5-68-consumer-at10r1.log.gz`, 684
rows over 100 s), and no over-limit was observed in any other run this session.

The reason is structural. Against `50573CD9` the 300 mm/s limit was permanently
enforced, because nothing sent the `WARN` line, so any drive above 0.30 m/s
latched. In this signature the limit is selected **only while the warning field
is occupied**, and in that same condition the standard program clamps the teleop
setpoint to `WARNING_SPEED_CEILING` — measured at **0.40 s** against a
`SPEED_LIMIT_ONSET_MAX` budget of **2.30 s** (§1.2). **The vehicle no longer
reaches the limit that would demand.** The previous issue's over-limit-to-demand
interval therefore has no successor figure, and none is invented here.

**SS1's second stage was measured, twice.** `Ss1Demand` is set in the same
F-sample as its cause, and `TorqueOffDemand` follows it:

| Run | cause | demand → torque-off |
|---|---|---|
| `v5r1` | `ZoneStopDemand` (protective field) | **0.95 s** |
| `at10r1` | `ZoneStopDemand` (protective field) | **1.016 s** |

Against a specified `SS1_TIME_MAX` of 1 s. **n = 2.** Neither is a measurement
of a machine's reaction time.

### 6.2 The demand REACHES THE PLANT — PROVEN LIVE, and this is what F1 was for

The previous issue's most important finding was that the F-program's SS1 demand
reached neither the standard program nor the vehicle. **It now reaches the
vehicle, and it was measured against the CPU with no double anywhere in the
path.** Four independent observations, in the order the signal travels:

1. **There is a mirror node.** `Forklift/Safety/` advertises **six** leaves, not
   four; `SpeedMonitorDemand` and `TorqueOffDemand` read back with their types,
   read-only at the server. Browsed and read on the controller in force.
2. **The bridge resolves it.** The committed `bridge/config/bridge.yaml`,
   **unedited for this run**, resolved **22 of 22** nodes and logged *"all 22
   resolved node DataTypes match the node model"*. The §11.6 optional-node
   tolerance — which existed because the leaf did not exist — **was not
   exercised**, and that is the correct outcome.
3. **There is a publisher.** `ros2 topic info -v
   /forklift/safety/torque_off_demand` on the running graph reports
   **publisher count 1** (`forklift_plc_bridge`) and **subscription count 1**
   (`sto_contactor`). The subscriber that had waited since m5-50 has a speaker.
4. **The plant acts on it.** `sto_contactor` — the vehicle's torque-off stand-in,
   its own committed node — opened its latch on the demand **6 times** this
   session and logged, in its own words, *"TORQUE OFF: latch OPEN. Traction
   terminal driven to 0.000 rad/s and held … Every command is now refused,
   including a permissive envelope."* Five of the six episodes closed with a
   count of what they refused:

   | episode | commands refused at the traction terminal |
   |---|---|
   | 1 | 17 646 |
   | 2 | 33 038 |
   | 3 | 23 415 |
   | 4 | 9 096 |
   | 5 | 12 280 |
   | **total** | **95 475** |

   and `/forklift/safety/torque_off_applied` read `true` while the demand stood.
   Each episode closed with *"TORQUE RESTORED: latch CLOSED"* when the demand
   fell.

**The positive control is in the same run as the strongest episode.** In `v5r1`
the identical command, from the identical page, drove the vehicle **10.83 m at
1.000 m/s while `TorqueOffDemand` was `False`**, and in the same recording the
demand went `True` and the traction terminal was driven to zero with the command
still held. The deafness is not being inferred from a vehicle that happened to be
still.

> **So, stated plainly, and this is what the showcase must now say:**
>
> The F-program's SS1 stop sequencer is built, correct, observable on the CPU
> **and coupled to the vehicle**. Its torque-off demand crosses the mirror, the
> server, the bridge and the topic, and the contactor opens on it. The previous
> issue's *"SLS and SS1 are not coupled today"* is **superseded and no longer
> true.**

**One half of F1 was NOT isolated this session, and it is stated rather than
glossed.** The standard program's third permissive conjunct — `SpeedMonitorDemand`
in `#safetyDemandClear` — was never observed standing **alone**. Both runs that
produced a standing `SpeedMonitorDemand` (`deaf1`, `deaf2`) also had the standard
program's own obstacle latch standing, because the manoeuvre that produced the
demand also brought the vehicle inside the process stop zone. In `deaf1` a
full-scale reverse command was then held for **25 s** and produced **0 motion
samples and no setpoint at all** — but with two inhibits standing the refusal is
over-determined, and this document does not attribute it to the new conjunct.
`deaf2` reached the same over-determined state and its refusal leg was not run.
**What is proven is the path to the contactor**, above; the conjunct's own
isolation is owed and is named in §7.

### 6.3 A demand the narrowed window still forms — observed twice, and it is a §11.1b row arriving

In `at10r1` and again in `deaf2`, `ShaftDoubtNow` held for **1.43 s** and
**> 1 s** respectively and latched `SpeedMonitorDemand`. Both times the vehicle
was **decelerating to rest out of a slow full-lock turn**: the shaft readings fell
below the new 15 mm/s window while the vehicle's lidar-derived motion observation
still read *moving*, and the disagreement outlasted `SHAFT_DOUBT_TIME`.

This is not a defect and it is not a surprise: it is
`plc/forklift-safety/SPEC.md` §11.1b's own not-covered row — *"a teleop operator
sustaining below ≈ 15 mm/s of tread can still produce a false demand"* — reached
here by a stop transient rather than by a sustained creep. **It did not occur in
the stop from 0.200 m/s** (`v5r1`), where the deceleration crossed the window too
quickly. **n = 2**, both out of full-lock turns at body speeds below 0.10 m/s.

**Worth briefing an operator before it is seen on stage**: creeping to a halt on
full lock can cost a monitored reset.

---

## 7. What this run found, and what is owed

| # | Finding | Owner |
|---|---|---|
| 1 | **F1 is closed at the plant** (§6.2) — six leaves, publisher count 1, contactor latching, 95 475 refused commands. **The standard-side permissive conjunct was not isolated**: every standing `SpeedMonitorDemand` this session was accompanied by a process obstacle latch. One run, in open floor, with a shaft-doubt demand and nothing else standing, would close it | `plc/` + whoever runs the next session |
| 2 | **F2 is closed** (§3.1) — the reproduction does not reproduce, with its control | closed |
| 3 | **F3 is closed** (§1.2, §0.3) — `WarningFieldClear` moves in both directions and the limit selector follows it | closed |
| 4 | **F4 is closed** (§1.2, §5) — the warning ceiling reaches the teleop setpoint, at full command it is 0.20 m/s, and it complies in 0.40 s against a 2.30 s budget | closed |
| 5 | **`ForkliftStatus.ForkliftSpeedLimitActive` read `False` in every sample of every run**, including the three in which the teleop clamp was demonstrably in force. Whatever that node reports, it is **not** the teleop warning clamp, so it cannot be the lamp `m5-59` §3 recommends for it. An operator sees a sluggish vehicle and no reason | `plc/` (what the node means) then `hmi/` (the lamp) |
| 6 | **A demand forms on the stop transient out of a full-lock creep** (§6.3), n = 2. A §11.1b not-covered row, reached in a live run | `plc/` + `agv/` — note, not a change |
| 7 | **The protective contour is a straight corridor and a turn escapes it** (§8's narration answer). After a full-lock turn the vehicle came to rest **0.29 m** from an obstacle on the process channel, with the protective field having stopped it only after the turn brought the object inside the corridor. The contour models a vehicle going straight, not a vehicle sweeping | `agv/` — a field-geometry question, and it bounds what may be claimed |
| 8 | **The autonomous start pose must lie inside the planner's region** (§3.2). The committed spawn is at the corner of the committed grid, so `SmacPlannerHybrid` with `allow_unknown false` publishes no plan from it. Nothing to fix in the safety layers | `sim/` + `agv/` |
| 9 | **This machine cannot hold the autonomy stack up beside the rest** (§3.3) — 13 fail-safe intrusions and 13 motion-observation gaps in one session against 3 genuine intrusions, and one cluster of them latched three demands while the vehicle stood still | `sim/` — a capacity finding for the showcase |
| 10 | **`Link/BridgeLinkOk` is still not addressable** on the controller in force (`BadNoMatch`), so the only bridge-liveness instrument any client has is the raw heartbeat counter | `plc/` + `interface` — unchanged from m5-62 |
| 11 | **Input-class nodes hold the previous session's values between sessions** (§0.2), one of them in the permissive direction | note only; the instrument is the heartbeat |

---

## 8. Summary — what a showcase may say, and what it may not

**May say, with evidence in this document:**

- the safety scanner **slows** the vehicle to **0.20 m/s** at full command and
  then **stops** it — measured, in teleoperation, with the command held
  throughout (§1.2, §5);
- the **torque-off demand reaches the vehicle**: the F-program demands it, it
  crosses the mirror, the server, the bridge and the topic, and the contactor
  refuses every command at the traction terminal — 6 episodes, 95 475 commands
  refused, with the same command moving the same vehicle 10.83 m at 1.000 m/s in
  the same run with the demand absent (§6.2);
- the **e-stop** stops it, in 241–271 ms operator-to-standstill, and it
  deliberately does **not** remove torque (§2);
- **every stop latches**, and recovery is a monitored reset with the cause gone —
  restoring the device is not a reset, and a reset with the cause standing is
  refused (§0.3, §2);
- the **shaft-doubt band is closed**: a healthy vehicle can now creep at 0.02 m/s
  for 30 s inside the readings that used to stop it, and nothing forms (§3.1);
- the cell **starts refusing everything** — every demand latched, torque off,
  nothing permitted — and takes a deliberate operator sequence to open (§0.1);
- the whole chain is real end to end — Gazebo scanner → field evaluation →
  stand-in writer → F-program → mirrors → OPC UA → bridge → vehicle → HMI — with
  **no double anywhere** (§ opening).

**May not say:**

- that an autonomous mission completes — **none did** (§3.2);
- that safety was demonstrated during autonomous driving — **not run** (§4);
- that the SLS limit was seen to demand on an over-limit — **the vehicle no
  longer reaches the limit**, so the AT-10 interval has no figure in this
  signature (§6.1);
- that the standard program's new permissive conjunct was isolated — **it was
  not** (§6.2, finding 1);
- **any** Performance Level, Category, SIL or PFH, for any function, ever.

### 8.1 The narration question, answered — the "operator cannot crash it" sentence

**The sentence under review is the unqualified one**, which the vault safety
review's finding F1 said needs a direction qualifier. It is deliberately not
written out here in its bare form, because the bare form is the thing this
section rules against; the supported form is at the end of the section.

**Can that sentence now be said without a direction qualifier? No. It still needs
one — but the qualifier has changed, and it is now a small, evidenced one rather
than an open gap.**

**What the review's finding F1 asked for has been supplied.** The two couplings
it named as missing are present and measured: teleoperation **is** slowed by the
warning field (§1.2, three trips, 0.20 m/s at full command), and the safety
layer's torque-off demand **does** reach the plant (§6.2, six episodes at the
contactor). The reason the sentence was unsupported — that SF-10 reached nothing
while teleop was not slowed — no longer holds.

**What has not changed, and what the qualifier must now say.** Three things, in
descending order of how likely they are to be seen on stage:

1. **It was measured going straight, once.** The full-command stop is **n = 1**,
   on one heading, at zero approach angle, against one flat obstacle, **unladen**,
   with the steering straight. A single approach is an observation, not a bound.
2. **A turn escapes the contour.** The protective field is a straight corridor
   in the vehicle frame — x −3.225…2.210 m, half width 0.55 m — and it models a
   vehicle going straight. In `at10r1` the vehicle turned at full lock and came
   to rest **0.29 m** from an object on the process channel; the field stopped it
   only once the turn had swung the object into the corridor. **The guarantee is
   weakest exactly where an operator manoeuvres**, and no run in this session
   measured a stop out of a turn.
3. **The tread-versus-body residual is untouched.** The clamp bounds *body*
   speed; the F-side limit is on *tread* speed. `m5-59` §3 records that beyond
   ≈ 48° of steer a compliant 0.20 m/s body speed is over the monitored limit,
   and 39.9° is the load-direction residual the SRS carries on SF-10. **This
   session did not exercise it** — at full lock the clamp held the vehicle so far
   below the ceiling that `SpeedOverLimitNow` never formed (§6.1) — so it is
   neither confirmed nor cleared here.

**So the sentence the owner should say is this one, and it is now fully
supported by §5:**

> *"Driving straight at an obstacle, with the command held down, the operator
> cannot crash the vehicle: it slowed itself to 0.20 m/s at 3.47 m and stopped
> 1.47 m short, and it stayed stopped."*

and **not** the unqualified form. The word that carries the qualifier is
**straight**, and it is carried by a measurement rather than by a caveat.

---

## 9. The evidence, and how to re-read it

All of it is in `bridge/evidence/`, one file per run, named for the run that
produced it and never reused (LESSONS 2026-08-06). **Every writer was stopped
and verified gone before anything was archived** (LESSONS 2026-07-28,
2026-08-06), and every archive passes `gzip -t`.

| File | What |
|---|---|
| `m5-68-mirrors-<run>.csv.gz` | The CPU's own view over OPC UA at 10–20 Hz: 25 nodes, one row per sample, **including the two new mirrors**. Runs `boot0`, `reset0`, `reset1`, `reset2`, `creep1`, `mode2`, `v1r1`, `v1r1b`, `back1`, `v5r1`, `v2r1`, `v2r2`, `v2r3`, `at10r1`, `deaf1`, `deaf2`, `v3r1`, `v3r2` |
| `m5-68-page-<run>.csv.gz` | The operator's own view: what was requested, and what `GET /state` served back, at 5 Hz |
| `m5-68-consumer-creep1.log.gz` | The F-program's own statics through the PLCSIM Advanced API during the shaft-doubt reproduction — §3.1's table |
| `m5-68-consumer-at10r1.log.gz` | The same, during the full-lock run — §6.1's `SpeedOverLimitNow` reading and §6.3's demand |
| `m5-68-writer-console-nocycle.log.gz` | The stand-in writer's whole session: every operator action, every field verdict, every speed-link event, UTC-stamped, with the per-cycle lines stripped |
| `m5-68-field-evaluation.log.gz` | The field evaluation's own verdicts and its reasons in its own words — §3.3's count |
| `m5-68-sto-contactor.log.gz` | The contactor's six torque-off episodes and their refusal counts — §6.2 |
| `m5-68-bridge-console.log.gz` | The bridge's session: R3, the 22 resolved nodes, the QoS readbacks |
| `m5-68-plan-v3r1.json.gz` | The first mission attempt's plan record |

`bridge/tools/summarize_mirrors.py` reads any of the mirror captures back:
transitions, a time window row by row, or a per-column first/last/distinct
summary — which is how every "it did not change" claim above is read off a
capture rather than asserted.

**Two witnesses, and they cannot echo each other.** The CSVs are read by an OPC
UA client off the server interface; the consumer logs are read by a PLCSIM
Advanced API client off `SafetyInputStandIn` and `InstF_Forklift_Safety`, which
the OPC UA server does not publish at all. Where both are quoted for one event,
they are two measurements.

**Not archived, deliberately.** The bridge's own 20 Hz latency capture for this
session is 233 MB and no figure in this document rests on it; it stays outside
the repository.

---

**The three things standing between this document and a complete one** are the
autonomous mission (§3.2 — a start pose and a machine, not a program), safety
during that mission (§4), and the isolation of the standard program's third
permissive conjunct (§6.2, finding 1). **None of the three is a safety defect,
and none of them needs TIA.**
