# VALIDATION — M5, the safety chain end to end

**What this document is.** The record of the first run of the whole chain
against the finished safety program. It is written to be narrated from: each
section says what was asked, what was observed, the numbers, and a plain
verdict. Where something is proven it says so; where it is not, it says that
in the same voice.

**Run identity.** 2026-08-06, evening. CPU `1513F-1 PN` on PLCSIM Advanced
instance `safecell3`, collective F-signature `50573CD9`, 360/360 build steps.
Nothing was downloaded, compiled or changed in TIA for this run.

**No layer in this run is a double.** The stand-in writer is
`bridge/standin_writer/standin_writer.ps1` against the real PLCSIM API; the
CPU is the real CPU; the HMI is `hmi/hmi_server.py` with its real OPC UA
session; the scanners are two `gpu_lidar` devices in Gazebo and the field
evaluation is `agv/forklift/scripts/field_evaluation.py`; the vehicle is the
Gazebo model with its own estimator and its STO contactor. The only thing
replaced anywhere is the *operator's keyboard*: the HMI page's request loop
and the writer's console are driven from files so that a command can be held
steady for a measured interval unattended. Both go through the committed
code paths, with the committed vocabulary and the committed refusals.

---

## The claim boundary, and it applies to every number below

This project claims **PLr targets only**. **No Performance Level, Category,
SIL or PFH is claimed, achieved or implied anywhere in this document**, for
any function, layer or figure. The whole safety *input* path is a labelled
stand-in: the scanner verdict is Python arithmetic over rendered depth
images, it reaches the safety program as **standard data** written by an
engineering process over a TCP link, and the encoder is one simulated shaft
read twice. None of that buys integrity, and no reaction time here is a
figure any machine is characterised by.

---

## 0. What was standing before anything was asked of it

The chain was brought up in this order: stand-in writer → Gazebo arena and
vehicle → field evaluation → envelope gate and vehicle I/O → bridge → HMI →
speed channels and their carrier.

At first contact the controller read, over its own OPC UA server:

| Node | Value |
|---|---|
| `Forklift/Safety/EStopDemand` | `True` |
| `Forklift/Safety/ZoneStopDemand` | `True` |
| `Forklift/Safety/SafetyResetRequired` | `True` |
| `Forklift/Envelope/ForkliftMotionEnable` | `False` |
| `Forklift/ProcessStop/ForkliftProcessStopActive` | `True` |

**That is the designed boot state and it is worth saying out loud:** a cold
cell starts with every demand latched and nothing permitted, and it takes a
deliberate operator sequence to open. Nothing in this run started permissive.

**Two things had to be true before any reset could be accepted, and both cost
a first attempt.** They are recorded because they are properties of the
design, not accidents of the run:

1. **The bridge withholds its own heartbeat until every configured input
   carries a real plant sample** (startup rule R3). With
   `obstacle_zone.py` not running, two of the seven inputs had never been
   sampled, the heartbeat stayed at 0, the standard program's bridge-link
   latch stood, and `ForkliftResetRequired` could not clear. The bridge said
   so in its own log, by name, every cycle.
2. **The F-program refused the monitored reset while the speed chain was
   stale.** `SpeedChainSeen` was `TRUE` from the previous session and both
   freshness sequences were frozen, so `SpeedStaleNow` was `TRUE`,
   `SpeedCauseGone` was `FALSE`, and the reset was correctly refused. It was
   accepted the moment the encoder channels and their carrier were running
   and both sequences advanced. **A reset that clears a cause nobody has
   fixed is the failure mode; this is the opposite of it.**

With both satisfied, one monitored reset at the writer and one at the HMI
cleared all latches together: `EStopDemand`, `ZoneStopDemand` and
`SafetyResetRequired` fell to `False` **in the same 100 ms sample**, and
`ForkliftEquipmentPermit` came up.

---

## 1. V1 — the scanner: does it slow, and does it stop?

*(the slowing leg is recorded in §1.2 and is mode-dependent — read both
halves)*

### 1.1 It stops — PROVEN

Run `at11r1`, one continuous recording, two independent witnesses: the CPU's
OPC UA server at 10 Hz (`mirrors-at11r1.csv`) and the F-program's own
statics read through the PLCSIM API (`consumer-at11r1.log`). Neither can
echo the other: the OPC UA server does not publish `SafetyInputStandIn` or
`InstF_Forklift_Safety` at all.

The operator held a full forward teleop command and drove at a rack.

| t [s] | obstacle distance [m] | `TractionSpeedRef` | plant speed [m/s] | `ZoneStopDemand` |
|---|---|---|---|---|
| 4.5 | 3.355 | 0.5 | 0.0 | False |
| 5.0 | 3.234 | 0.5 | 0.500 | False |
| 6.7 | 2.384 | 0.5 | 0.500 | False |
| 7.8 | 1.834 | 0.5 | 0.500 | False |
| 8.3 | 1.584 | 0.5 | 0.500 | False |
| **8.9** | **1.331** | **0.0** | **0.0** | **True** |
| 19.5 | 1.331 | 0.0 | 0.0 | True |

**Observed.** The protective verdict opened the zone channel at the writer,
the F-program latched `ZoneStopDemand`, the standard program dropped
`ForkliftTeleopActive` and drove the traction setpoint to `0.0` in the same
scan, and the vehicle stopped. **Standstill at 1.331 m from the obstacle,
against a 1.35 m protective boundary** — 0.019 m inside the contour, on the
correct side of it. The distance never changed again for the remaining 10.6 s
of the recording.

**The positive control is inside the same run** (this is the rule that makes
the result mean anything — a stopped process and a real stop look identical).
The identical command, from the identical page, moved the vehicle at 0.500 m/s
across **1.903 m in 3.9 s** immediately beforehand (obstacle distance 3.234 m
at t = 5.0 to 1.331 m at t = 8.9). Motion under that command is not in doubt;
the stop is attributable to the field.

**The latch holds.** The operator's command was released at 8.9 s and the
vehicle stayed stopped with `ZoneStopDemand` and `SafetyResetRequired` both
`True` for the rest of the recording. Recovery required a monitored reset;
nothing resumed by itself.

**n.** The zone latch and its stop were observed **3 times** across this
session (the boot state, run `at11r1`, and the V5 repeat in §5). The 1.331 m
standstill figure is **one** measurement, from one approach at one speed
along one heading; it is an observation, not a bound.

### 1.2 It slows — NOT PROVEN AS ASKED, and the reason is structural

The brief asked for: warning field occupied → the standard program drops the
ceiling to 0.20 m/s → the vehicle slows.

**What the program actually does.** `plc/forklift/SPEC.md` §14.16 applies
`WARNING_SPEED_CEILING` = 0.20 m/s to `ForkliftSpeedCeiling`, and that node
is the **autonomous** envelope. In **teleop** the setpoint is formed as
`tractionDemand × speedCap` and the warning ceiling is not a term in it. So:

> **In teleoperation the warning field does not slow the vehicle. It slows the
> vehicle in autonomous mode only.** The teleop protection against an
> obstacle is the protective field's stop, not a speed reduction.

That is a true statement about the build, not a defect found in it — but it
is not what the brief's V1 sentence assumed, and a showcase must not say
"the scanner slows it down" over a teleop clip.

The slowing leg is therefore an **autonomous-mode** measurement and is
recorded in §4 with V4.

### 1.3 The control case — the object outside both contours

`ObstacleMinDistance` read 3.355 m at rest with the racks in view, the
protective verdict read **clear** and the warning verdict read **clear**, and
neither channel produced a verdict: `ZoneStopDemand` `False`,
`ForkliftWarningFieldOccupied` `False`, for the whole idle period. The field
evaluation logged the reason in its own words — *"both devices report the
warning field clear (front 0 ray(s) inside, rear 0)"*. **The scanners see the
world and say nothing about it until something crosses a contour.**

---

## 2. V2 — the e-stop — PROVEN, n = 2

The cell e-stop, through the real chain: the writer opens
`SafetyInputStandIn.EStopCircuitClosed` (wire NC, program NO — an open
circuit is the demand), the F-program latches `EStopDemand`, the standard
program withdraws the setpoint, the plant stops. **The operator's forward
command was still being posted throughout**, at the page's own 5 Hz.

| | run `v2r1` | run `v2r2` |
|---|---|---|
| speed held before the demand | 0.250 m/s | 0.250 m/s |
| operator opens the circuit (writer log, UTC) | 18:32:21.413 | 18:33:44.799 |
| `EStopDemand` `TRUE` at the OPC UA server | 18:32:21.473 | 18:33:44.928 |
| circuit → demand | **60 ms** | **129 ms** |
| `TeleopActive` `FALSE` and `TractionSpeedRef` `0.0` | same 50 ms sample as the demand | same 50 ms sample |
| plant speed reads `0.0` | 18:32:21.62 | 18:33:45.05 |
| **operator's action → standstill** | **≈ 207 ms** | **≈ 250 ms** |

Both figures are observed at a 50 ms polling period through the writer's
50 ms cycle, the F-cycle, the standard cycle, OPC UA and the bridge. They are
the **chain's** end-to-end latency in this simulation, and they are not a
machine's stopping performance and carry no integrity claim of any kind.

**The positive control is in each run.** The identical command held the
vehicle at 0.250 m/s for 3.9 s immediately before each e-stop, and in `v2r2`
the identical command moved it again at 0.250 m/s for 6.2 s after recovery.
Stillness is not being read as evidence here: the same command is shown
moving the vehicle on both sides of the inhibit.

**Nothing resumes by itself, and the reset discipline holds.** Three separate
observations:

- In `v2r1`, `estop close` alone — the circuit restored, no reset — left
  `EStopDemand` `TRUE` for the remaining 15 s of the recording. **Restoring
  the device is not a reset.**
- In `v2r2`, a monitored reset was actuated **while the circuit was still
  open**. It was refused: `EStopDemand` and `SafetyResetRequired` both stayed
  `TRUE` for the following 12.6 s. **A reset cannot clear a cause that is
  still standing.**
- The circuit was then closed and the same reset actuated again: all latches
  cleared at 18:34:02.728, 1.62 s after the actuation began, which is the
  1.5 s hold plus one cycle. **Cleared on the release, with the cause gone —
  not on the press.**

---

## 3. V3 — an autonomous mission — NOT ACHIEVED, and the cause is diagnosed

**Can a goal be given?** Yes. **Does the vehicle drive it?** No — it moves and
then the safety layer latches a demand, correctly, on a signature a healthy
vehicle produces every time it starts from rest. That is the honest answer and
the cause is named below.

### The attempts, all of them

| # | what was asked | what happened |
|---|---|---|
| r1 | goal in **world** coordinates | `ABORTED` at once — *"Start Coordinates … was outside bounds"*. **This run is discarded, not repaired**: the seed and the goal were given in world coordinates and the map frame is offset from the world by the committed registration (`sim/maps/warehouse/warehouse_registration.yaml`, θ = −0.0079 rad, t = (6.029, 5.541)). The mistake was the operator's, not the stack's |
| r2 | world (−3, 7) → (+3, 7), converted | Goal **accepted**, path planned, then *"Failed to make progress"*, vehicle did not move. The envelope was closed at the PLC: a field-evaluation fail-safe trip (below) had latched `ZoneStopDemand` |
| r3 | world (−3, 7) → (+5, 7), envelope confirmed open first (`MotionEnable` `True`, ceiling 0.60 m/s) | Goal **accepted**, path planned and re-planned continuously, **vehicle moved 0.227 m**, then at t = 8.3 s a safety demand latched, the envelope was withdrawn, the gate ramped to zero, and Nav2 went on replanning against a vehicle it could no longer move |

**So: a goal can be given and is accepted; a mission does not complete.**
The owner has ruled autonomy a prototype, and this is where the prototype
stands tonight.

### Why r3 stopped — the shaft-doubt band, and it is reproducible on demand

The latch was **not** a field intrusion and **not** an over-limit. It was
`ShaftDoubtNow` → `SpeedMonitorDemand`. Reproduced deliberately, with the
F-program's own statics recorded (`bridge/evidence/m5-58-consumer-creep-shaftdoubt.log`):

the vehicle was held in teleop at a **0.02 m/s creep**, a speed it executed
correctly — the two encoder channels read **15–26 mm/s** throughout — and:

| t [ms] | F-program state |
|---|---|
| 3 766.8 | `MotionPresent` `TRUE`, `MotionPresentValid` `TRUE`, `SpeedNearZero` `TRUE`, **`ShaftDoubtNow` `TRUE`** |
| 4 795.1 | `ShaftDoubtTimer.Q`, **`SpeedMonitorDemand` latched**, `Ss1Demand`, `TorqueOffDemand` |

**The mechanism, stated as a number.** The motion-present observation calls
the vehicle *moving* above **1.4 mm/s**; the speed monitor calls a reading
*near zero* below **30.8 mm/s**. Between those two thresholds a **perfectly
healthy vehicle is, by construction, "seen moving while the shaft reads
still" — which is exactly the shared-shaft failure the test exists to catch.**
Every speed in 1.4 … 30.8 mm/s is inside that band.

**And that is precisely where Nav2 starts.** The closed-loop velocity
smoother's from-rest output is **0.025 m/s** (measured on this stack in this
run, and the same figure `docs/LESSONS.md` records for 2026-08-05). So every
mission that starts from rest passes through the band, holds it for longer
than `SHAFT_DOUBT_TIME`, and latches. The autonomous mission is not blocked by
Nav2, by the envelope or by the scanner — it is blocked by a threshold pair.

This is a **specification finding, not a build defect**: the F-program does
exactly what `plc/forklift-safety/SPEC.md` §11 says. What is missing is that
the two thresholds were derived independently, in two different documents, and
nobody derived the window between them. It is the same shape as the
2026-08-05 smoother/converter deadband lesson, one layer up.

### The other thing that stops a mission — fail-safe trips on scan staleness

`field_evaluation.py` requires a scan younger than 0.30 s on its own steady
clock and reads anything older as an intrusion. With the full stack running on
this machine — Gazebo software-rendering three lidars, plus Nav2, AMCL, the
bridge, the HMI and PLCSIM Advanced — the 10 Hz scan stream stalls past that
window intermittently. Counted from the node's own log over this session:
**7 fail-safe trips**, each lasting 30–160 ms, at intervals of roughly 30 s to
6 minutes. Two of them latched `ZoneStopDemand` and closed the envelope, and
one of those is why r2 could not move.

**The node is behaving correctly** — a scanner that has stopped talking must
read as occupied, and this is the design working. What is being reported is
that **this machine cannot feed it reliably while everything else runs**. It
is a simulation-capacity finding and it belongs on the record because it
bounds what a recorded showcase can show in one take.

---

## 4. V4 — safety while driving under Nav2 — NOT RUN

The test as written requires the vehicle to be **driving under Nav2** when an
object enters the protective field. No Nav2 mission on this machine kept the
vehicle moving long enough to stage an intrusion into it (§3), so the test was
not run and **no result is claimed for it**.

What *is* known about the two halves it would have joined:

- **The envelope is withdrawn while Nav2 is still asking for motion** — this
  was observed, in r3 and in r2: the planner kept publishing a path and the
  controller kept commanding 0.6 m/s while `ForkliftMotionEnable` was `False`,
  and the envelope gate held its output at zero (`gate_state = 2`,
  `HOLD_ZERO`). Nav2's own response is to replan indefinitely and eventually
  report *"Failed to make progress"*; it does not fight the gate and it does
  not stop asking.
- **The protective field stops the vehicle** — proven three times, but every
  time in teleoperation (§1.1, §5).

Joining the two is one run away and needs the §3 threshold-band finding
resolved first.

---

## 5. V5 — the operator drives at a wall — PROVEN, n = 3

**This is the owner's own test and the strongest result in the set.** The
operator holds a full-scale forward command from the real HMI page and drives
straight at a rack. The command is never released.

| | `at11r1` | `v5r2` | `v5r3` |
|---|---|---|---|
| operator's request | 0.5 (of full scale) | **1.0, full** | **1.0, full** |
| speed reached and held | 0.500 m/s | 1.000 m/s | 1.000 m/s |
| distance at which the **warning** field occupied | not reached in this approach | 3.499 m | 3.499 m |
| speed through the warning field | — | **1.000 m/s, unchanged** | **1.000 m/s, unchanged** |
| distance at which `ZoneStopDemand` latched | ≤ 1.584 m (100 ms sampling) | 1.458 m | 1.499 m |
| `TractionSpeedRef` → `0.0` | same 50 ms sample | same 50 ms sample | same 50 ms sample |
| **closest approach** | **1.331 m** | **1.108 m** | **1.159 m** |
| stopping distance after the trip | ≈ 0.25 m | **0.350 m** | **0.340 m** |
| time from trip to standstill | ≤ 0.30 s | 0.45 s | 0.40 s |
| operator's command at standstill | still held | still held | still held |

**Verdict: the operator cannot crash the vehicle.** At full command, from
1.000 m/s, it stopped **1.11 m and 1.16 m short** of the obstacle, twice,
with the command still being posted. The two full-speed runs agree to
0.05 m in closest approach and to 0.01 m in stopping distance.

**Positive control, in each run.** The same command drove the vehicle 19–20 m
across the floor at 1.000 m/s in the seconds before each stop. The vehicle was
demonstrably not merely parked.

**The warning field did not slow it, and this is §1.2 confirmed live.** In
both full-speed runs `ForkliftWarningFieldOccupied` went `True` at 3.499 m and
the vehicle went on at 1.000 m/s to the protective boundary, because in teleop
the setpoint does not pass through `ForkliftSpeedCeiling`. **In a teleop clip,
the scanner does not slow the vehicle — it stops it.** Say that, not the
other thing.

**One honest note on what these figures are.** They are the whole chain's
behaviour in this simulation, at this scan rate, on this machine, against a
flat rack face at zero approach angle. They are not a stopping performance,
they are not a safety distance calculation, and they support no PL, Category,
SIL or PFH claim.

---

## 6. The speed monitor and the stop sequencer — AT-10 and AT-11

### 6.1 The monitor demands on a limit exceeded — PROVEN

In run `at11r1` the vehicle was held at 0.50 m/s while the F-side speed limit
in force was 300 mm/s. Read off the F-program's own statics:

| t [ms] | what changed | readings A / B [mm/s] |
|---|---|---|
| 4 891.7 | `SpeedOverLimitNow` `TRUE` | 496 / 507 |
| 5 026.9 | `SpeedOverLimitTimer.Q`, then **`SpeedMonitorDemand` latched**, `Ss1Demand` `TRUE` | 503 / 496 |
| 5 185.6 | `SafetyResetRequired` and its mirror set | 507 / 507 |
| 6 181.5 | **`TorqueOffDemand` `TRUE`** — the SS1 sequencer's second stage | 507 / 503 |

Over-limit to latched demand: **135 ms** at a 135 ms sampling resolution,
against a specified `SPEED_OVERLIMIT_TIME` of 200 ms. Demand to torque-off:
**1 155 ms**, against a specified `SS1_TIME_MAX` of 1 s. Both consistent with
the specification; neither is a measurement of a machine's reaction time.
**n = 1** for these two intervals.

### 6.2 The demand did not reach the plant — THE MOST IMPORTANT FINDING IN THIS DOCUMENT

In the same run, with `SpeedMonitorDemand`, `Ss1Demand` and
`TorqueOffDemand` all standing `TRUE` from 6.2 s, **the vehicle carried on at
0.500 m/s for a further 2.4 s and 1.2 m**, and stopped only when the
*protective field* — a different function entirely — latched
`ZoneStopDemand` at 8.9 s.

The mechanism is not subtle and was confirmed three ways:

1. **There is no mirror node.** `Forklift/Safety/` publishes exactly four
   leaves — `EStopDemand`, `ZoneStopDemand`, `SafetyResetRequired`,
   `SafetyResetFault`. `SpeedMonitorDemand` and `TorqueOffDemand` are absent.
   Read back off the controller in force.
2. **There is no publisher.** `ros2 topic info -v
   /forklift/safety/torque_off_demand` on the running graph reports
   **publisher count 0, subscription count 1** — the subscriber being
   `sto_contactor`, the vehicle's torque-off stand-in. It is listening and
   nothing is speaking.
3. **The specification says so.** `plc/forklift-safety/SPEC.md` §11.2's
   "who implements what" table assigns *"the standard program's copy
   statements and its permissive term gaining the new demand"* to
   `plc/forklift/SPEC.md`'s standard-side brief. That brief has not been
   written. The two mirror nodes are likewise an outstanding request of the
   interface agent.

**So, stated plainly, and this is what the showcase must say:**

> The F-program's SLS monitoring and its SS1 stop sequencer are **built,
> correct and observable on the CPU**. Their demand **does not yet reach the
> vehicle**: it is coupled to neither the standard program's motion permissive
> nor any node, topic or output the plant can see. The e-stop and the
> protective-field stop **are** coupled and **do** stop the vehicle. SLS and
> SS1 are not, today.

This is a wiring gap between two owned layers, not a defect in either. It is
one mirror-node pair, one copy statement and one permissive conjunct — all
three already named in the specifications — and it needs a `plc/` brief and an
`interface` brief.

### 6.3 The torque-off "deafness" test cannot be run yet

The brief asks for the vehicle to be **deaf to commands after torque removal,
even with the envelope reopened**. That test presumes the demand reaches the
contactor. It does not (§6.2), so the observation available today is the
opposite one: **with `TorqueOffDemand` standing, the same command still moved
the vehicle at 0.500 m/s** — measured, in run `at11r1` and again in the
`at11` window before it (140 samples at up to 0.500 m/s across the 14 s the
command was held).

That is reported as the result it is. `agv/forklift/EVIDENCE_STO.md`'s
existing claim — that the contactor really does make the plant deaf — is
about the contactor driven directly, and is not contradicted here; what is
missing is the path from the F-program to it.

---

## 7. What this run also found, and what is owed

| # | Finding | Owner |
|---|---|---|
| 1 | `SpeedMonitorDemand` / `TorqueOffDemand` reach neither the standard program nor the vehicle (§6.2) | `plc/` standard-side brief + `interface` (two mirror nodes) |
| 2 | Nothing sends the `WARN` line on the 45015 field link, so the F-side limit selector `WarningFieldClear` is permanently `FALSE`, the 300 mm/s SLS limit is permanently enforced, and the full 0.60 m/s ceiling cannot be used without tripping it. `field_evaluation.py` is the specified sender (`plc/forklift-safety/SPEC.md` §11.2) and does not implement it | `agv/` |
| 3 | `bridge/config/bridge.yaml` did not carry the §13 warning group; the node exists on the controller in force and the group was added for this run after probing the server | done here (`bridge/`) |
| 4 | The warning-field speed reduction is autonomous-mode only (§1.2, confirmed live in §5). Whether teleop should also be reduced is a design question, not a defect | `plc/` — a question, not a request |
| 5 | **The shaft-doubt band** (§3): a healthy vehicle between 1.4 mm/s and 30.8 mm/s reads as *moving with a still shaft* and latches a demand, and Nav2's from-rest speed of 25 mm/s is inside it. Two thresholds derived in two documents with nobody deriving the window between them | `plc/` and `agv/` jointly — one admissible window, stated in one place |
| 6 | The field evaluation fail-safe trips on scan staleness roughly every 30 s – 6 min when the whole stack runs on this machine (§3). Correct behaviour, insufficient simulation capacity | `sim/` — a capacity finding for the showcase, not a program change |
| 7 | After a safety latch, entering a drive mode again needs a **fresh** mode-request edge; holding the request through the latch does not re-enter. Observed twice. Correct restart discipline, worth writing down because it will look like a fault on stage | note only |

---

## 8. Summary — what a showcase may say, and what it may not

**May say, with evidence in this document:**

- the safety scanner **stops** the vehicle, and an operator holding a full
  command at a wall cannot crash it — 3 runs, closest approach 1.11–1.33 m;
- the **e-stop** stops it, in ≈ 0.21–0.25 s end to end, 2 runs, and nothing
  resumes by itself: restoring the device is not a reset, and a reset with the
  cause still standing is refused;
- **every stop latches**, and recovery is a monitored reset with the cause gone;
- the **speed monitor** demands on a limit exceeded and the **SS1 sequencer**
  runs to torque-off, on the CPU, at the specified times;
- the whole chain is real end to end — Gazebo scanner → field evaluation →
  stand-in writer → F-program → mirrors → OPC UA → bridge → vehicle → HMI —
  with no double anywhere;
- the cell **starts refusing everything** and takes a deliberate sequence to open.

**May not say:**

- that SLS or SS1 stops the vehicle — **they do not reach it** (§6.2);
- that the scanner *slows* the vehicle in a teleop clip — **it does not** (§1.2, §5);
- that an autonomous mission completes — **none did** (§3);
- that safety was demonstrated during autonomous driving — **not run** (§4);
- **any** Performance Level, Category, SIL or PFH, for any function, ever.

---

## 9. The evidence, and how to re-read it

All of it is in `bridge/evidence/`, one file per run, named for the run that
produced it and never reused (LESSONS 2026-08-06).

| File | What |
|---|---|
| `m5-58-mirrors-<run>.csv.gz` | The CPU's own view over OPC UA at 10–20 Hz: 23 nodes, one row per sample. `at11`, `at11r1`, `v2r1`, `v2r2`, `v3r3`, `v5r2`, `v5r3` |
| `m5-58-transitions-<run>.log` | The watched transitions of the same runs, with wall-clock stamps |
| `m5-58-consumer-at11r1.log` | The F-program's own statics through the PLCSIM API during `at11r1` — the AT-10 / SS1 timings of §6.1 |
| `m5-58-consumer-creep-shaftdoubt.log` | The deliberate reproduction of the §3 shaft-doubt band |
| `m5-58-writer-console.log` | The stand-in writer's whole session: every operator action, every field verdict, every speed-link event, with UTC stamps that the CSVs above are read against |

**Two witnesses, and they cannot echo each other.** The CSVs are read by an
OPC UA client off the server interface; the consumer logs are read by a
PLCSIM Advanced API client off `SafetyInputStandIn` and
`InstF_Forklift_Safety`, which the OPC UA server does not publish at all.
Where both are quoted for one event, they are two measurements.

**One instrument note that nearly cost a false finding.** A display that
truncated numeric strings to twelve characters rendered `-6.58672215e-05`
as `-6.586722156`, which reads as an impossible −6.6 m/s on a 1.5 m/s
vehicle. It was caught by counting how many samples exceeded the traction
limit — zero, in every run — before anything was written down. **Never
truncate a number for display; format it as a number.**

---

**The three things standing between this document and a complete one** are
finding 1 (couple the speed monitor to the plant), finding 5 (the threshold
band that stops every mission at its first metre) and finding 2 (the missing
`WARN` sender). All three are small, all three are named in specifications
that already exist, and none of them is a design that has to change.
