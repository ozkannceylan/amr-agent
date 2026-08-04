# Safety requirements specification — warehouse cell and vehicle

Gate M2. Covers the F-CPU safety program (cell side) and the onboard safety
system (vehicle side). Every function has a trigger, a reaction with a
performance target, a safe state, a reset behavior and one executable
acceptance test.

**Gate references.** They follow the gate order of ADR 0010
(`docs/adr/0010-milestone-restructure-forklift-first.md`, accepted) **as amended
by ADR 0013**, which places the vendor-portability gate after M6 and M7 and
deliberately **assigns it no number**; `docs/roadmap.md` numbers it **M8**,
because that document is the single source for gate numbering, and it is the live
order any disagreement is settled against. The transfer-station F-CPU functions
(SF-01, SF-07, the cell instance of SF-08) and the vehicle-side behaviors are
verified together at **M5**, on the forklift twin; the vehicle functions the
sensored gate adds (SF-10, SF-11) land there with them; the fixed-equipment
functions that arrive with the stations (SF-05, SF-06) and the supervision
boundary pin (SF-09) are verified at **M6**. Section 4 gives the per-function
landing gate.

## 1. Scope and boundaries

### 1.1 What is a safety function here

A safety function is a reaction executed **only** by:

- the **F-CPU safety program**, acting on its own F-I/O over PROFIsafe and
  hardwired channels, or
- the **onboard vehicle safety system** (safety laser scanner, bumper, e-stop
  button, STO path), acting through its hardwired inhibit into the drive
  system.

Everything else — standard PLC program, fleet manager, MQTT broker, OPC UA
link, VDA 5050 client, Nav2 — is **process or degraded-mode behavior** and may
never be part of a safety function's causal chain.

### 1.2 Boundary statements (binding)

| # | Statement | Source |
|---|---|---|
| B1 | **Safety never traverses the network.** No trigger, reaction or reset of any SF in this document uses MQTT, OPC UA or VPN. The `Safety/` OPC UA nodes and VDA 5050 `safetyState` are read-only informational mirrors; no client decision may substitute for a safety function. | Invariant 1; opcua-nodes.md §4 |
| B2 | **Loss of network is degraded mode, not a safety event.** Supervision loss is handled by vehicle software (controlled stop, SF-09) and by the standard PLC program (handshake to defined idle) — **outside** the safety program. No SIL/PL claim attaches to it. | Invariant 2; handshake-tables.md §1 |
| B3 | **The safety program stays correct if the standard program halts or misbehaves.** Every SF in section 3 must reach its safe state with the standard CPU program stopped; acceptance tests for F-CPU functions include this case. | Invariant 7 |
| B4 | **Cell and vehicle safety are independent chains.** The cell e-stop does not stop vehicles; vehicles carry their own chain (SF-02/SF-03). Neither chain depends on the other, on the fleet manager, or on any shared computed "cell safe" flag. | Invariants 1, 7; handshake-tables.md §6 |

### 1.3 Arm safety — out of scope

**Out of scope — arm integration removed from the roadmap (ADR 0010 D5).** The
arm gate is removed entirely, not parked, and the RB-KAIROS mobile manipulator
that brought an arm into the model (ADR 0002) is retired as the vehicle
platform (ADR 0010 D1). No arm exists in the plant this project builds on, and
arm safety functions are **not specified here**.

The ID block **SF-20 … SF-29** stays **reserved**: the ids are kept and never
reissued to another function, so the record of what was scoped and then removed
is not silently lost. Its expected contents, recorded while the arm gate
existed (base-stationary interlock as a precondition for arm motion, separate
base/arm safety zones per ADR 0002), stand as record only and are not a
requirement on any gate. No SF below claims to cover arm motion.

## 2. Conventions

| Convention | Rule |
|---|---|
| Wire NC, program NO | All safety and stop devices are wired **normally closed** and read in the program as **normally open** contacts. A broken wire, unplugged connector or dead sensor drops the signal to 0, which is the tripped state — the fault stops the machine instead of masking the demand. |
| Monitored reset | After any latched safety stop, restart requires a separate, deliberate, **monitored** reset (SF-08): edge-triggered so a stuck or bridged button never counts, manual, local. Reset removes the latch only; it never starts motion. On restart the program re-reads all sensor states and decides from current reality, never from stale sequence state. |
| Edge vs level | Edges capture events (the reset actuation); levels capture conditions (e-stop tripped, field violated, door closed). A state that must survive a restart is always a level. No SF trigger or safe-state latch is edge-based. |
| Actuation path | Safety functions act only through hardwired outputs and PROFIsafe F-I/O (cell) or the hardwired STO/brake path (vehicle). The standard program and every network link are bypassed by design. |
| No auto-resume | Latched safety stops (SF-01, SF-02, SF-05, SF-06, SF-07, SF-10) never release themselves. The single documented exception is the protective field (SF-03), where **release of the inhibit** is automatic after the field clears — see SF-03 for the justification; motion restart is still a fresh command, never a resumed one. **SF-11 holds no latch of its own**: it is the sequenced stop path, and the safe state it reaches is released by the reset rule of the function that demanded it. A stop path with its own latch would give one reaction two owners. |

## 3. Safety functions

### SF-01 Cell e-stop chain

| Field | Specification |
|---|---|
| ID | SF-01 |
| Trigger | Any cell e-stop mushroom button actuated (two at the transfer station, one at the cell entrance; two-channel NC, discrepancy-monitored by the F-CPU). |
| Reaction | F-CPU de-energizes all fixed-equipment enabling outputs: conveyor drive **stop category 0** (immediate power removal; low inertia, no controlled ramp needed), door drive stop category 0 (sliding door, self-holding, no gravity hazard), charger contactor opened. Target: outputs de-energized ≤ **100 ms** after button contact opens (including PROFIsafe worst-case delay). |
| Safe state | All fixed-equipment power/enabling outputs off; `EStopActive` latched (level). Vehicles are **not** stopped by this function — the cell e-stop has no path to any vehicle (B1, B4). Vehicles inside the cell are protected by their own chain (SF-02, SF-03); operationally the fleet manager sees the `EStopActive` mirror and stops assigning orders, which is process behavior, not part of this SF. |
| Reset | Latched until: all buttons unlatched → monitored reset per SF-08 → standard program re-reads equipment state before any new handshake. No auto-resume. |
| Acceptance test | **AT-01** (PLCSIM Advanced, M5): (a) With conveyor running in a transfer, force one e-stop channel open → conveyor enabling output 0 and contactor output 0 within 100 ms of the forced edge (trace via PLCSIM Advanced tag trace); `EStopActive` mirror = 1. (b) Repeat with the **standard CPU program in STOP** → same outputs de-energize (B3). (c) Open only one of the two channels → trip plus discrepancy fault. (d) Release button without reset → outputs stay off. Pass: all four observations. |

### SF-02 Vehicle e-stop

| Field | Specification |
|---|---|
| ID | SF-02 |
| Trigger | Onboard e-stop button actuated (two-channel NC into the onboard safety system). |
| Reaction | **Stop category 0 / STO**: safe torque off on both traction drives and mechanical brake engaged, via the hardwired inhibit path. Target: torque removed ≤ **200 ms** after button contact opens. No network element is in this chain (B1). |
| Safe state | Drives torque-free, brake engaged, vehicle at standstill; VDA `safetyState.eStop` reports `MANUAL` (report-only, after the fact). |
| Reset | Latched until button unlatched → onboard monitored reset per SF-08 (edge-triggered, at the vehicle). After reset the vehicle software re-reads localization and order state; motion resumes only on a fresh navigation command. |
| Acceptance test | **AT-02** (Gazebo, M5): While the vehicle drives a Nav2 path at nominal speed, assert the simulated e-stop input → the simulated safety node cuts the drive command at the hardware-abstraction level (below Nav2, which is bypassed, not asked), vehicle decelerates to standstill within the platform's braking distance, and `safetyState.eStop` = `MANUAL` in the next `state` message. Nav2 command messages published during the stop have no effect. Releasing the button alone does not restore motion; reset + new goal does. Pass: all observations; the inhibit demonstrably acts below the navigation stack. |

### SF-03 Vehicle protective stop — scanner protective field

| Field | Specification |
|---|---|
| ID | SF-03 |
| Trigger | Object detected in the protective field of **either** safety laser scanner — from M5 the forklift carries **two**, at diagonal chassis corners, whose apertures cover the full circle **by union** (`agv/forklift/EVIDENCE_SENSOR_COVERAGE.md`) — with the monitoring case / field set selected by the onboard safety system according to safely measured speed and direction; or bumper contact. |
| Coverage boundary | **The protective argument leans on the union of the two apertures and on nothing else.** Per-device coverage is not the union. The **measured** residual sectors where the union does not reach — load occlusion in the fork direction (**R3**, 39.9°), the close-range carriage shadow (**R1**, 5.0° at 2 m), the tine-crossing window (**R2**) — are **not covered by this function**, and are carried by SF-10's speed limit instead; the derivation is `PL-SCENARIOS.md` **SC-13**. Reduced field plus creep speed is a **risk reduction**, never the elimination of a sector. **R8**, the rear device's self-return band, costs the pair no coverage and is a constraint on that device's **field geometry**, not on this function's coverage. |
| Reaction | **Stop category 1 (SS1-t)**, executed through the one shared stop path of **SF-11**: controlled deceleration at maximum service braking, then STO + brake at standstill or at the SS1 time limit (≤ **1 s**), whichever comes first. Justification for cat 1 over cat 2/SS2: an AGV on a level floor needs no active holding torque (the mechanical brake holds), removing power at standstill gives a deterministic safe state, and SS2 would require safety-rated standstill monitoring that buys nothing on this platform. Protective field dimensioning must cover the braking distance at the speed the field set is valid for. |
| Safe state | Vehicle at standstill, torque off, brake engaged, scanner still monitoring; `safetyState.fieldViolation` = true (report-only). |
| Reset | **Automatic release of the inhibit** when the protective field has been clear for ≥ **2 s**. This is the documented exception to the no-auto-resume rule and follows normal AGV protective-field practice (ISO 3691-4 style): the detection zone remains continuously monitored, so releasing the inhibit reintroduces no hazard. Motion restart is still a **separate fresh command** formed by the navigation stack from current sensor state — the vehicle never continues a stale motion command; bumper trips (physical contact) do latch and require the SF-08 onboard reset. |
| Acceptance test | **AT-03** (Gazebo, M5): (a) Spawn an obstacle into the protective field of the moving vehicle → deceleration begins in the next control cycle, standstill before the field's dimensioned boundary, `fieldViolation` = true. (b) Remove the obstacle → inhibit releases after the 2 s clear time, vehicle resumes only after Nav2 issues a fresh command. (c) Repeat with the obstacle entering the bumper: stop latches and survives obstacle removal until reset. (d) **Two-scanner and residual observation.** Repeat the intrusion against the **second** scanner's field → the same stop executes, with no second stop path. Then, with a load on the tines and the vehicle travelling fork-first, place a target in the **measured** load-direction residual (bearings 164.5–204.4° at 2.0 m, `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` R3) → **neither** protective field reports it, and the reduced monitoring case with its ≤ 0.3 m/s SLS limit is in force (cross-check AT-10); move the same target outside the residual → the field trips and (a) executes. The negative observation is **observed in the run**, never inferred from the geometry document. Pass: stop distance inside the field, no resume before 2 s clear, bumper latch behavior confirmed, and (d) demonstrated in one run. |

### SF-04 Scanner warning field — speed reduction

| Field | Specification |
|---|---|
| ID | SF-04 |
| Trigger | Object detected in the scanner's warning field (larger than the protective field). |
| Reaction | Vehicle speed limited to creep (≤ **0.3 m/s**) while the warning field is occupied, so that a person continuing toward the vehicle is met by a protective field sized for the reduced speed. |
| Safe state | Not a stop; the safe state remains SF-03's, which backs this function up unconditionally. |
| Reset | Automatic: full speed permitted again when the warning field has been clear for ≥ 2 s. Level-based, no latch. |
| Honesty | On real hardware this is safety-rated only if speed is monitored by a safety-rated channel (SLS). **This project implements it in vehicle software (scanner field output → Nav2 speed limit) and claims it as safety-related but informative — no PL is claimed.** The safety-rated protection remains SF-03 alone, whose protective field must be dimensioned for the worst case that the speed reduction *fails*. **SF-10 does not change this row.** SF-10 is speed-limit *enforcement* and is selected in the **reduced-detection** monitoring case (SF-03's coverage-boundary row; SC-13), which is not the warning-field case. SF-04 still only *requests* a speed. Whether the warning-field case should also select an SLS limit is a monitoring-case design question, recorded as open in `PL-SCENARIOS.md` SC-06 and not decided here. |
| Acceptance test | **AT-04** (Gazebo, M5): Place an obstacle in the warning field only → commanded and actual speed drop to ≤ 0.3 m/s within one field-report cycle; protective field not violated; no stop. Clear the field → nominal speed resumes after 2 s. Then verify the backup claim: disable the speed-reduction handler and drive at full speed into the same scenario → SF-03 still stops the vehicle inside the protective field. Pass: all three observations. |

### SF-05 Door interlock

| Field | Specification |
|---|---|
| ID | SF-05 |
| Trigger | Door safety position switch (two-channel NC, F-I/O — independent of the standard program's `DoorClosed` process sensor) does not confirm closed-and-locked **while** the conveyor transfer zone behind it is enabled. |
| Reaction | F-CPU removes the conveyor transfer enable: conveyor drive **stop category 1** (controlled ramp ≤ 500 ms, then power removal) if running, and inhibits any start while the door is not confirmed closed. Target: enable removed ≤ **100 ms** after loss of the closed-and-locked signal. |
| Safe state | Conveyor cannot run while the door is open; `SafetyDoorClosed` mirror = 0. The door *process* sequencing (PassageRequest handshake) is unaffected in its own right — this SF only guarantees the conveyor side. |
| Reset | Interlock is a **level**: closing and locking the door restores the *permission* automatically, but if the SF tripped a running conveyor, that stop latches and requires monitored reset per SF-08 before the standard program may start a new transfer. No auto-resume of the interrupted transfer. |
| Acceptance test | **AT-05** (PLCSIM Advanced, M6): (a) With a transfer running, force the door safety switch open → conveyor enable drops within 100 ms, `SafetyDoorClosed` = 0, `ProtectiveStopActive` = 1. (b) Re-close the switch → conveyor does not restart by itself; only after SF-08 reset does the standard program accept a new transfer. (c) With door open, request a transfer → `TransferReady` never asserts. (d) Repeat (a) with the standard program in STOP → enable still drops (B3). Pass: all four. |

### SF-06 Charger interlock

| Field | Specification |
|---|---|
| ID | SF-06 |
| Trigger (permissive) | The charge contactor may close **only** while the F-CPU's own docking confirmation (safety-relevant docked-position switch on F-I/O, independent of the standard program's `ChargerVehicleDocked` diagnostic) is present **and** the standard program is commanding a charge. `ChargeRequest` over OPC UA is a process precondition seen by the standard program; it is never sufficient and never reaches the F-CPU. |
| Trigger (trip) | Loss of docking confirmation, charger fault input, or cell e-stop (SF-01) while the contactor is closed. |
| Reaction | Contactor opened ≤ **100 ms** after loss of any permissive; contactor never closes without the full permissive AND. Exposed contacts are dead whenever no vehicle is confirmed docked. |
| Safe state | Contactor open, charge circuit dead. |
| Reset | Permissive is a level (re-dock restores permission), but a **trip while charging** latches and requires SF-08 monitored reset plus a completely new charge handshake with a new token (handshake-tables.md §5); the interrupted charge never resumes. |
| Acceptance test | **AT-06** (PLCSIM Advanced, M6): (a) Command a charge without the docked-position input → contactor output stays 0. (b) With docking confirmed and charge commanded, contactor closes; then force the docked input away → contactor output 0 within 100 ms and latched. (c) Restore docking without reset → contactor stays open. (d) Repeat (b) with the standard program in STOP → contactor opens (B3). Pass: all four. |

### SF-07 Zone monitoring — transfer station area

| Field | Specification |
|---|---|
| ID | SF-07 |
| Trigger | Presence detected in the monitored transfer-station zone (safety-rated zone device — light curtain or scanner field — on F-I/O) while any fixed equipment in that zone (conveyor) is enabled. |
| Reaction | F-CPU protective stop of the fixed equipment in the zone: conveyor **stop category 1** (ramp ≤ 500 ms then power removal). Target: stop initiated ≤ **100 ms** after detection. Vehicles in or near the zone are **not** stopped by this function (B4) — a person near a vehicle is protected by SF-03; the fleet manager may reroute using the `ProtectiveStopActive` / `ZoneAOccupied` mirrors, which is process behavior. |
| Safe state | Zone equipment stopped and inhibited while presence persists; `ProtectiveStopActive` = 1. |
| Reset | Zone clear restores the *permission* (level), but a trip during an active transfer latches: monitored reset per SF-08, then a new handshake. No auto-resume of the interrupted transfer. |
| Acceptance test | **AT-07** (PLCSIM Advanced, M5; coupled Gazebo scenario at M6): (a) During an active transfer, force the zone-device input to "occupied" → conveyor ramp-and-stop within 100 ms + 500 ms ramp, `ProtectiveStopActive` = 1. (b) Clear the zone → no restart without SF-08 reset. (c) With the zone occupied, request a transfer → `TransferReady` never asserts. (d) Standard program in STOP, repeat (a) → stop still executes (B3). Pass: all four. |

### SF-08 Monitored reset (cell and vehicle instances)

| Field | Specification |
|---|---|
| ID | SF-08 |
| Trigger | Operator actuates the reset device (cell: reset button at the F-CPU panel; vehicle: onboard reset button) after the cause of a latched SF has been cleared. |
| Reaction | Reset is accepted only as a **monitored edge sequence**: signal must rise, be held between **0.2 s and 3 s**, and the latch releases on the **falling edge** (button release). A signal high longer than 3 s, or high at power-up/restart, is a stuck-or-bridged actuator: the reset is rejected and a reset-fault is flagged until the signal returns to 0. Reset while any SF trigger is still present is ignored. |
| Safe state | Reset never energizes anything. It clears latches only; every actuator start afterwards is a separate deliberate command formed by the standard program (or vehicle navigation) from **freshly re-read** sensor states. `SafetyResetRequired` mirror: 1 while any latch is pending, 0 after successful reset. |
| Reset | Not applicable (this is the reset function itself). Its failure modes fail safe: no valid edge sequence → latches stay latched. |
| Acceptance test | **AT-08** (PLCSIM Advanced, M5): After tripping SF-01: (a) hold reset input high permanently → latch stays, reset-fault flagged. (b) Pulse 0→1→0 within 100 ms (< 0.2 s) → rejected. (c) Valid pulse (1 s) with the e-stop still tripped → rejected. (d) Clear e-stop, valid pulse → latch releases exactly on the falling edge, `SafetyResetRequired` 1→0, and **no output energizes** as a consequence of the reset alone. Pass: all four. |

### SF-09 Vehicle supervision watchdog — boundary pin, NOT a safety function

| Field | Specification |
|---|---|
| ID | SF-09 *(listed to pin the boundary; carries **no SIL/PL claim** and lives entirely outside the safety program)* |
| Trigger | VDA 5050 client node detects loss of supervision (MQTT broker connectivity lost / heartbeat timeout, vda5050-subset.md §7). |
| Reaction | **Degraded mode, executed by vehicle software**: controlled stop via normal Nav2 deceleration, order data kept, no torque removal, no safety actuation. Target (quality, not safety): stop initiated within one watchdog period (proposed 5 s, fleet-layer configuration). |
| Safe state | Not a safe state in the safety sense — a *defined process state*: vehicle stationary, holding its order, onboard safety (SF-02/SF-03) fully live throughout. |
| Reset | Automatic resume when supervision returns and the fleet manager has resynchronized (handshake-tables.md §1, §5). Permitted precisely because this is not a safety stop. |
| Acceptance test | **AT-09** (Gazebo + broker, M6): Kill the MQTT broker while the vehicle executes an order → vehicle decelerates to a controlled stop within the watchdog period, keeps the order, `connection` last-will fires. During the outage, trip the simulated protective field → SF-03 still acts (independence from network, B1/B2). Restore the broker → vehicle resumes after fleet resync, without operator reset. Pass: all three. |

### SF-10 Safely limited speed (SLS) — vehicle

| Field | Specification |
|---|---|
| ID | SF-10 |
| Trigger | The vehicle's **own safely measured speed** exceeds the limit in force for the monitoring case the onboard safety system has selected. The **reduced-detection** case — a load in the fork direction, where the protective field's coverage of that direction is reduced (SF-03 coverage boundary; `PL-SCENARIOS.md` SC-13) — selects **≤ 0.3 m/s**, the cap ISO 3691-4 places on a truck whose personnel-detection means are muted (ADR 0011 F11, quoted as the practice the model follows, **never as a conformity statement**). |
| Speed source | Two channels of speed **and direction** measured on the vehicle's own traction drive and cross-compared **inside the vehicle's onboard safety system**. It is **never** `cmd_vel`, the odometry topic, VDA `state.velocity`, the HMI's displayed speed, or the PLC's envelope speed ceiling. The envelope ceiling is a **process** value: the PLC forms it and does not enforce it, the enforcing gate runs on the vehicle, and this function is the compelling backstop beneath both (ADR 0014 D5). A safety function that took its measurement over OPC UA would traverse the network (B1); one that took its **limit** from the process ceiling would be checking a supervisor's word against itself. **This function and SF-11 are modelled in their entirety**: there is no drive, no encoder pair and no safety-rated measurement channel in this project, and §5 with §5.1 governs every word of both rows. |
| Reaction | Demand **SF-11** (SS1): monitored controlled deceleration, then STO + brake at standstill or at the SS1 time limit, whichever comes first. |
| Safe state | Vehicle at standstill, torque off, brake engaged; the SLS trip **latched**. VDA `safetyState` reports it only after the fact, if a broker is listening (B1). |
| Reset | Latched. Released only by the onboard monitored reset per SF-08, after the measured speed is inside the limit. No auto-resume; motion restarts only on a fresh navigation command. |
| Acceptance test | **AT-10** (Gazebo, M5): With the reduced load-direction monitoring case in force and the SLS limit at 0.3 m/s: (a) command a speed above the limit through the navigation stack → the safety model's own measured speed crosses the limit, SF-11 is demanded, the vehicle reaches standstill and torque is removed. (b) Return the commanded speed below the limit → the trip does **not** release; the SF-08 onboard reset releases it, and motion resumes only on a fresh navigation command. (c) Repeat (a) with the PLC's envelope speed ceiling set **above** the SLS limit → the SLS limit does not move and the trip still occurs; no process value reaches this function (B1). (d) Repeat (a) with the bridge stopped and the OPC UA session down → unchanged (B1, B3). Pass: all four. |

### SF-11 SS1 stop sequencing — the vehicle's one category 1 stop path

| Field | Specification |
|---|---|
| ID | SF-11 |
| Trigger | Any category 1 stop demand on the vehicle. SF-03's protective field and bumper, and SF-10's speed-limit trip, both enter **this** path. There is exactly one such path: a second would give one reaction two owners, and the second one is the one nobody tests. |
| Reaction | **SS1-t.** The SS1 timer starts at the **demand**, never at the observed start of deceleration. Controlled deceleration at maximum service braking is commanded and **monitored**; STO and the mechanical brake are applied at standstill **or at the SS1 time limit (≤ 1 s), whichever comes first**. A deceleration that is never achieved therefore ends in STO at the limit rather than in an unbounded wait — which is the whole difference between a category 1 stop and a category 2 stop wearing the wrong name. |
| Safe state | Drives torque-free, brake engaged, vehicle at standstill. |
| Reset | **None of its own.** SF-11 holds no latch; the safe state it reaches is released by the reset rule of the function that demanded it — SF-03's automatic release after 2 s field-clear (bumper trips excepted), SF-10's SF-08 monitored reset. |
| Acceptance test | **AT-11** (Gazebo, M5): (a) At nominal speed, violate the protective field **with the modelled deceleration disabled** → STO and brake are applied **at the SS1 time limit**, not withheld pending a standstill that never arrives. (b) Repeat with deceleration working → STO is applied **at standstill, earlier than the limit**; (a) and (b) together demonstrate "whichever comes first" rather than asserting it. (c) Repeat with SF-10 as the demanding function instead of SF-03 → the same single sequence executes and no second stop path appears. (d) After each, the latch behavior is the demanding function's and not SF-11's. Pass: all four. |

## 4. Traceability

Mirror nodes are **informational only** (opcua-nodes.md §4; vda5050-subset.md
`safetyState`); they appear here so dashboards can be checked against the SF
that feeds them, never as part of any safety path.

| SF | Function | Informational mirrors | Acceptance test | Verified at gate |
|---|---|---|---|---|
| SF-01 | Cell e-stop chain | OPC `Safety/EStopActive` | AT-01 | M5 |
| SF-02 | Vehicle e-stop | VDA `safetyState.eStop` | AT-02 | M5 (sim behavior and review, one gate) |
| SF-03 | Protective field stop | VDA `safetyState.fieldViolation` | AT-03 | M5 |
| SF-04 | Warning field speed reduction | none (internal; visible in `state.velocity`) | AT-04 | M5 |
| SF-05 | Door interlock | OPC `Safety/SafetyDoorClosed`, `ProtectiveStopActive` | AT-05 | M6 |
| SF-06 | Charger interlock | OPC `Charger/ChargerContactorClosed` (process mirror) | AT-06 | M6 |
| SF-07 | Zone monitoring | OPC `Safety/ProtectiveStopActive`, `Cell/ZoneAOccupied` (process) | AT-07 | M5 (coupled Gazebo scenario at M6) |
| SF-08 | Monitored reset | OPC `Safety/SafetyResetRequired` | AT-08 | M5 (cell and vehicle instances, one gate) |
| SF-09 | Supervision watchdog *(not a safety function)* | VDA `connection`, `Cell/CellHeartbeatFleet` | AT-09 | M6 |
| SF-10 | Safely limited speed (SLS) | **none coined here.** Any mirror is `docs/interfaces/opcua-nodes.md`'s to name under invariant 10, and that document already refuses an SLS or safe-speed node by name (§12.12, on the §11.7 rule): a mirror, if one is ever wanted, is a read-only status of the **standard** program, requested rather than created here | AT-10 | M5 |
| SF-11 | SS1 stop sequencing | **none coined here**, same rule as SF-10 | AT-11 | M5 |
| SF-20…29 | *Reserved: arm safety — ids kept, never reissued* | — | — | **out of scope — arm integration removed from the roadmap (ADR 0010 D5)** |

Worked hazard-to-PLr derivations for these functions, and the validation tests
behind each acceptance test above, are in `docs/safety/PL-SCENARIOS.md`.

## 5. Honesty — what a simulated portfolio project can and cannot claim

This project runs in PLCSIM Advanced and Gazebo. Therefore:

- **PL/SIL figures are design intent, not certified claims.** Design targets:
  PL d, Category 3 (ISO 13849-1) for SF-01, SF-02, SF-03, SF-05, SF-06, SF-07,
  SF-10 and SF-11 — in line with typical AGV/cell practice per ISO 3691-4 — and
  PL c for SF-08. The edition read against is **ISO 13849-1:2023**, the fourth;
  EN ISO 13849-1:2015 is withdrawn (ADR 0011 F12). No validation to
  ISO 13849-2, no SISTEMA calculation, no certified components exist here; on
  real hardware these numbers would have to be re-derived from a risk
  assessment and the actual component data.
- **Simulated timing is not real-time.** The millisecond targets in section 3
  are design requirements for real hardware. Acceptance tests in PLCSIM
  Advanced/Gazebo verify **logic, ordering, latching, independence (B3) and
  reset behavior**, and measure times in simulation time as plausibility
  evidence only.
- **The onboard safety system in Gazebo is a functional model**, not a
  certified safety controller: a simulated node that reads the simulated
  scanner/bumper/e-stop and gates the drive command below Nav2. It demonstrates
  the architecture (inhibit below the navigation stack, independence from the
  network), not a rated safety loop.
- **SF-04 is deliberately claimed as informative** (see its table); the
  honest safety claim for personnel detection rests on SF-03 alone.
- What the project *does* claim: correct **separation of concerns** — every
  safety reaction here is executable with the network dead and the standard
  program halted, and nothing in the fleet, MQTT or OPC UA layers can create,
  prevent or reset a safety action.

### 5.1 The claim boundary (ADR 0011 D5), reproduced in full

This list is landed here, once, because it is the section a reader of any safety
claim in this project passes through. It is binding on this document, on
`docs/safety/PL-SCENARIOS.md`, on `docs/safety/TWIN-DEMO-MAP.md` and on every
artifact, recording and narration of every gate.

**The following are claims this project must never make, in this or any later
gate, while it remains hardware-free:**

1. An **achieved PL**, an achieved **Category**, or an achieved **SIL** for its
   own chain.
2. Any **PFH**, **MTTF<sub>D</sub>**, **DC<sub>avg</sub>** or **CCF** figure for
   its own chain.
3. **"certified"**, **"compliant with"**, **"TÜV assessed"**, **"CE marked"**.
4. **"validated per ISO 13849-2"**.
5. A **verified response time**, **stopping distance** or **protective field
   length**.
6. **"safety functions tested"** without **"in simulation, against a model"**.
7. **Any reproduction of a component's datasheet safety figure as if it were
   this system's result.** Where a modelled device's published figures appear in
   this project — the safety laser scanner class of ADR 0011 F8, quoted once in
   `PL-SCENARIOS.md` SC-13 — they are the **modelled component's data** and
   carry that sentence beside them.

**No acceptance is claimed either.** The TIA Portal **safety acceptance test**
and the **program signature** presuppose real F-hardware, so neither is claimed,
implied or reported here or in any M5 artifact.

Two consequences of the list, stated so they are not re-derived:

- **Every PL and Category figure in this document is a target. Every PLr in
  `PL-SCENARIOS.md` is a floor derived from a risk graph. Neither is a result**,
  and a target above its floor (SF-06 over SC-09's PLr c) is a correct outcome,
  not a discrepancy.
- **ISO 3691-4's 0.3 m/s cap for muted personnel detection** (ADR 0011 F11) is
  the practice the model follows, not a conformity statement, and it is written
  that way wherever SF-04 and SF-10 quote it.
