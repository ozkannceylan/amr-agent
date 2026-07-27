# Performance level scenarios — ISO 13849 method applied to this cell

Companion to `docs/safety/SRS.md`. The SRS names the safety functions and one
performance-level target line. This document shows the **method** that produces
such a line: for twelve concrete demand situations, hazard → risk graph → PLr →
covering safety function → architecture → validation test → acceptance test.

---

## 0. What this document is, and is not

The honesty section of the SRS (§5) is binding here, word for word. Restated so
that no reader has to go looking for it:

| Claim | Status in this document |
|---|---|
| Certification | **None.** Nothing here is certified, assessed or approved by anyone. |
| Validation to ISO 13849-2 | **Not performed.** The tests below are written *in the style of* ISO 13849-2 test cases — stimulus, observation, pass criterion, fault addressed. No fault list has been worked through exhaustively, no fault exclusion has been justified against the standard's tables, and no test has been executed on hardware. |
| SISTEMA / quantified PL | **None.** No MTTF<sub>D</sub>, DC<sub>avg</sub>, CCF score or PFH<sub>D</sub> figure exists in this project. Every PL written below is a *target* derived from a risk graph, never a computed achieved PL. |
| Certified components | **None procured.** Architectures assume safety-rated devices of the class normally used for this duty. Which device, from which vendor, at which PL, is not decided and not modelled. |
| Real-time timing | Millisecond figures are design requirements for real hardware. PLCSIM Advanced and Gazebo verify **logic, ordering, latching, independence and reset behaviour**; times measured there are plausibility evidence only. |
| Risk assessment | The risk-graph inputs below are **engineering judgement on a described cell**, not the output of a machine-specific risk assessment with a real layout, real speeds and real masses. On real hardware every parameter would be re-derived. |

What this document *does* claim: that the chain from a described hazard to a
verifiable reaction is followed correctly and consistently, twelve times, with
every judgement written down where a reader can disagree with it.

**Gate numbering.** Gate references follow the SRS, which was written before
ADR 0004 renumbered the gates. Under the current numbering
(`docs/roadmap.md`) the safety layer is **M9**, the simulated vehicle is M5/M6
and the demonstration is M10. The SRS's own numbers are left untouched here;
the discrepancy is recorded in this task's report, not fixed by this document.

---

## 1. Method

### 1.1 The chain, once

graph LR
    H["Hazard situation<br/>described, not assumed"] --> RG["Risk graph<br/>S, F, P"]
    RG --> PLR["PLr<br/>required performance level"]
    PLR --> SF["Covering SF<br/>from SRS §3"]
    SF --> ARCH["Category + architecture<br/>SRS §5 target line"]
    ARCH --> VT["Validation test<br/>ISO 13849-2 style"]
    VT --> AT["Acceptance test<br/>SRS §4 traceability"]

Every scenario below walks this chain exactly once and stops. A scenario that
needed two safety functions to reach its safe state would be a scenario
described too broadly; each maps to exactly one SF, and cross-references any
other SF that is live at the same time without claiming it.

### 1.2 The risk graph (ISO 13849-1, Annex A)

| Parameter | Value | Meaning used here |
|---|---|---|
| **S** — severity of injury | S1 | Slight, normally reversible: bruising, abrasion, superficial laceration |
| | S2 | Serious, normally irreversible, including death: crushing, entanglement, fracture, amputation, burn |
| **F** — frequency and/or duration of exposure | F1 | Seldom to less often, and/or short exposure |
| | F2 | Frequent to continuous, and/or long exposure |
| **P** — possibility of avoiding the hazard | P1 | Possible under specific conditions: the hazard is visible, slow, or approached deliberately |
| | P2 | Scarcely possible: no warning, no escape route, or the person is already committed |

Resulting required performance level:

| S | F | P | PLr |
|---|---|---|---|
| S1 | F1 | P1 | a |
| S1 | F1 | P2 | b |
| S1 | F2 | P1 | b |
| S1 | F2 | P2 | c |
| S2 | F1 | P1 | c |
| S2 | F1 | P2 | d |
| S2 | F2 | P1 | d |
| S2 | F2 | P2 | e |

**F is about the person, not the fault.** F asks how often, and for how long,
a person is exposed to the hazard zone. It is not the duration of a fault, not
the duty cycle of the machine and not the frequency of the demand. This
distinction is made explicitly because it is the one most often got wrong, and
because two scenarios below (SC-03, SC-11) invite the mistake.

### 1.3 PLr is a floor

A PLr is the minimum the safety function must reach. Implementing above it is
normal and is not an error — in this cell every F-CPU function shares one
architecture (two-channel F-I/O, PROFIsafe, F-CPU), so a function whose PLr is
c is nevertheless built at the same Category 3 / PL d as its neighbours. SC-09
is the worked example. What is *not* permitted is implementing below the
floor, or adjusting a parameter until the floor drops to what was convenient.

### 1.4 Boundaries binding every scenario

| # | Boundary | Source |
|---|---|---|
| N1 | **No reaction in this document traverses the network.** Every reaction chain is hardwired, PROFIsafe F-I/O, or the vehicle's onboard inhibit. MQTT, OPC UA and the VPN appear only *after* the fact, as read-only mirrors that report a state a safety function has already reached. A scenario whose reaction needed a message would be a wrongly designed scenario. | Invariant 1; SRS B1 |
| N2 | **The safety instance is the F-CPU one.** SC-01, SC-02, SC-03, SC-07, SC-08, SC-10 and SC-11 touch equipment that the M3 demonstration cell also models. The demonstration cell has **no F-CPU**, and its red mushroom is a **process stop** in the standard program (ADR 0004; `opcua-nodes.md` §9.6). Every scenario below is about the F-CPU instance of the equipment. Nothing here is demonstrated by the M3 cell and nothing in the M3 cell may be recorded, labelled or presented as any of it. | ADR 0004 |
| N3 | **Supervision loss is not a safety function.** SF-09 carries no SIL/PL claim. SC-12 exists to show where the method stops, not to smuggle it in. | Invariant 2; SRS B2 |
| N4 | **Every reaction is correct with the standard program in STOP.** Each validation test therefore carries the B3 case explicitly or inherits it from its acceptance test. | Invariant 7; SRS B3 |
| N5 | **Wire NC, program NO.** Every safety and stop device below is wired normally closed and read as normally open. A broken wire, pulled connector or dead device *is* the tripped state. SC-03 exists to make this visible. | CLAUDE.md §9; SRS §2 |

### 1.5 How to read one scenario

The hazard paragraph is what a reader must accept for the rest to follow. The
risk-graph table gives one sentence per parameter and, where a parameter is
genuinely arguable, says which way and what the alternative would cost. The
validation test says what is forced, what must be observed and what makes it a
pass. The last row lands on an SRS acceptance test, so no scenario ends in a
document that does not exist.

---

## 2. Scenarios

### SC-01 — Cell e-stop demanded mid-transfer, operator at the nip point

**Hazard.** A pallet has jammed at the entry to the transfer conveyor. The
conveyor is running and continues to drive the pallet against the obstruction.
The operator, standing at the transfer station, reaches in to free the load.
The in-running nip between the driven roller and the pallet edge draws the
hand in; the pallet mass means the drive does not stall. The e-stop mushroom
at the transfer station is the last-resort measure once the hand is already
committed.

| Field | Content |
|---|---|
| **S** | **S2** — an in-running nip loaded by a pallet produces crushing or degloving of the hand; not reversible. |
| **F** | **F2** — clearing a jam at the transfer station is a routine task performed several times per shift, so exposure is frequent. |
| **P** | **P1** — the conveyor runs at low speed, the operator is standing and unrestrained, and the button is within arm's reach; avoidance is possible under those specific conditions. *Arguable*: once the hand is in the nip, avoidance is over — the P1 rests entirely on the button being reachable by the free hand, which is a layout precondition, not a property of the function. If the layout cannot guarantee it, P2 applies and PLr rises to e, which would mean redesigning the guarding rather than the e-stop. |
| **PLr** | **d** (S2, F2, P1) |
| **Covering SF** | **SF-01** — cell e-stop chain. F-CPU de-energizes all fixed-equipment enabling outputs; conveyor stop category 0; ≤ 100 ms. |
| **Architecture** | SRS §5 target: **Category 3, PL d**. Two-channel NC mushroom heads on F-I/O with discrepancy monitoring, PROFIsafe to the F-CPU, hardwired de-energization of the enabling outputs. Cat 3 means a single fault does not lose the function and is detected where reasonably practicable — see SC-03 for the fault case. |
| **Network** | None. Button → F-I/O → PROFIsafe → F-CPU → hardwired output. `Safety/EStopActive` is written afterwards for the dashboard and is in no causal chain (N1). |
| **Validation test** | *Stimulus:* conveyor running under a transfer; force one e-stop channel open. *Observation:* conveyor enabling output and contactor output both read 0 within 100 ms of the forced edge, traced in PLCSIM Advanced; `EStopActive` = 1. *Repeat with the standard CPU program in STOP.* *Fault addressed:* none — this is the demand test, not the fault test. *Pass:* both outputs at 0 inside the window, in both program states. *Fail:* any output non-zero, or the 100 ms exceeded, or a dependency on the standard program. |
| **Maps to** | **AT-01 (a), (b)** |

---

### SC-02 — Cell e-stop demanded with the cell at rest: unexpected start-up

**Hazard.** Between transfers the cell is idle but *enabled* — the standard
program may command the next transfer at any moment on a handshake from the
fleet layer. A technician steps in to inspect the door drive linkage, back
turned to the conveyor, hands inside the equipment envelope. Nothing is
moving, so nothing warns him. The e-stop is the means by which he secures the
equipment before entering, and the means by which a colleague stops it if it
starts while he is inside.

| Field | Content |
|---|---|
| **S** | **S2** — the door drive and conveyor nip are the same mechanical hazards as SC-01; a start-up onto hands inside the envelope crushes. |
| **F** | **F1** — inspection and adjustment access is occasional, planned, and short compared with production time. Contrast SC-01, which is the same equipment with F2 because jam clearing is routine. |
| **P** | **P2** — an unexpected start-up gives no warning, the technician's back is turned and his hands are already inside the envelope; avoidance is scarcely possible. |
| **PLr** | **d** (S2, F1, P2) |
| **Covering SF** | **SF-01** — same function, different demand context. The latch is what matters here: `EStopActive` is a **level** that survives, so the equipment cannot re-enable while the technician is inside, and release of the button alone restores nothing (SRS §2, no auto-resume). |
| **Architecture** | SRS §5 target: **Category 3, PL d**. Unchanged from SC-01 — one function, one architecture, two demand contexts reaching the same floor by different routes. |
| **Network** | None. The fleet manager's `EStopActive` mirror stops it *assigning* work, which is process convenience; the technician's protection is the de-energized output, not the fleet manager's cooperation (N1). |
| **Validation test** | *Stimulus:* cell idle and enabled; actuate e-stop; then command a transfer from the standard program; then release the button without a reset. *Observation:* enabling outputs stay at 0 throughout; `TransferReady` never asserts; releasing the button does not re-energize anything. *Fault addressed:* none; this is the latch-integrity test. *Pass:* no output energizes at any point in the sequence. *Fail:* any output energizing on button release, or a transfer command being accepted. |
| **Maps to** | **AT-01 (d)**, the no-restart-on-release observation. AT-01's sub-tests are written around a demand *in motion*; the at-rest start-up-inhibit observation above (transfer commanded with the latch set, and refused) extends AT-01 rather than being one of its listed cases. The plc agent should carry it as an added observation when AT-01 is authored at the safety gate. |

---

### SC-03 — Single fault: one e-stop channel broken before the demand

**Hazard.** A conductor in the e-stop loop is severed — cable-carrier fatigue,
a connector pulled during maintenance, a crushed strand. Nobody is hurt by the
break itself. The hazard is that the break is **silent**, and the next time
SC-01's demand arrives the operator presses a button that does nothing. This
scenario is the demand of SC-01 with the safety function already dead, and it
is the reason Category 3 is claimed rather than Category 1.

| Field | Content |
|---|---|
| **S** | **S2** — the exposure is SC-01's exposure; the fault changes nothing about the injury, only about whether it happens. |
| **F** | **F2** — the exposure is SC-01's, i.e. jam clearing several times per shift. **Not** the frequency of the wire break: F asks how often the *person* is in the hazard zone (§1.2). Deriving F from the fault rate would be the classic error and would understate the risk. |
| **P** | **P1** — inherited from SC-01, unchanged. The fault does not alter the operator's ability to step back. |
| **PLr** | **d** (S2, F2, P1) — necessarily identical to SC-01, because a PLr is a property of the hazard, not of the failure mode. What the fault changes is the *architecture* needed to hold that PLr, not the PLr itself. |
| **Covering SF** | **SF-01**, in its fault-tolerant aspect. |
| **Architecture** | SRS §5 target: **Category 3, PL d**, and this is the scenario that pays for it. Three mechanisms, in order of what each buys: **(1) Polarity.** Wire NC, program NO (N5) — the broken conductor drops the signal to 0, which the program reads as *tripped*. The fault therefore produces the safe reaction instead of hiding behind it. This is not fault tolerance, it is fault *direction*, and it is free. **(2) Redundancy.** Two channels; the loss of one does not lose the function. **(3) Diagnosis.** Discrepancy monitoring between the channels: the two channels disagreeing for longer than the permitted window is a detected fault, flagged and latched, so the single fault is announced rather than accumulated. Category 3 requires that a single fault not lead to loss of the function and, where reasonably practicable, be detected — all three mechanisms are needed to say that sentence honestly. |
| **Network** | None. Discrepancy detection is inside the F-CPU. The fault is *reported* to the dashboard afterwards, and a dashboard that never renders it changes nothing about the reaction (N1). |
| **Validation test** | *Stimulus:* with the cell enabled, force **one** of the two e-stop channels to 0 and leave the other closed. *Observation:* (a) the enabling outputs de-energize — the single fault produced the safe reaction, not a silent loss; (b) a discrepancy fault is flagged and **latched**; (c) restoring the forced channel does **not** clear the fault or re-enable the outputs without a monitored reset per SF-08; (d) repeat with the standard program in STOP — behaviour unchanged (N4). *Fault addressed:* open circuit in one channel of a two-channel input, per the conductor-fault class of the ISO 13849-2 fault lists. No fault exclusion is claimed for the wiring; none is justified in this project. *Pass:* all four observations. *Fail:* outputs remaining energized on a single-channel break — which would mean the polarity is inverted somewhere, the single most dangerous defect this test can find. |
| **Maps to** | **AT-01 (c)** |

---

### SC-04 — Vehicle e-stop where the scanner cannot see: pinch against fixed structure

**Hazard.** The safety laser scanner monitors a horizontal plane roughly a
hand's width above the floor, ahead of the vehicle. A pallet overhanging the
vehicle's envelope at chest height, or reverse travel where scanner coverage is
reduced, creates a hazard the protective field does not contain: a person
between the load and a rack upright, being closed on by a mass the scanner has
already declared clear. The onboard e-stop is what exists for the hazards
outside the field geometry — which is the entire reason a vehicle carries one
when SF-03 already stops it.

| Field | Content |
|---|---|
| **S** | **S2** — crushing between a loaded vehicle and a fixed steel upright; irreversible. |
| **F** | **F1** — the specific geometry (overhanging load at body height, or reverse travel with a person in the path) is occasional rather than continuous; routine aisle sharing is SC-05's F2, and is covered by the field. |
| **P** | **P2** — the person is between the load and a fixed structure with no escape direction, and the scanner's silence means no automatic stop is coming. Scarcely avoidable by the person; the e-stop must be reachable by that person or a bystander. |
| **PLr** | **d** (S2, F1, P2) |
| **Covering SF** | **SF-02** — vehicle e-stop. Stop category 0 / STO: safe torque off on both traction drives, mechanical brake engaged, via the hardwired inhibit; torque removed ≤ 200 ms. |
| **Architecture** | SRS §5 target: **Category 3, PL d**. Two-channel NC e-stop into the onboard safety system, dual-channel STO path into the drives, brake released only by an energized enable. Note the honest limit: **SF-02 does not cover this hazard automatically** — it requires a human to press a button. The scenario shows why SF-03 alone is not a complete personnel-protection argument, not that SF-02 detects anything. |
| **Network** | None, and this is the sharpest case: the vehicle may be mid-order, mid-message, or with the broker down. The chain is button → onboard safety system → STO. `safetyState.eStop` = `MANUAL` is published afterwards if a broker happens to be listening (N1). |
| **Validation test** | *Stimulus:* vehicle driving a Nav2 path at nominal speed with the protective field reporting clear; assert the simulated e-stop input. *Observation:* the drive command is cut at the hardware-abstraction level, **below** Nav2 — verified by continuing to publish Nav2 velocity commands during the stop and observing no motion; vehicle reaches standstill within the platform's braking distance; `safetyState.eStop` = `MANUAL` in the next state message. Releasing the button alone does not restore motion; reset plus a fresh goal does. *Fault addressed:* none; this is the demand and the architecture-placement test. *Pass:* all observations, and specifically that the inhibit demonstrably acts below the navigation stack — Nav2 is bypassed, not asked. *Fail:* any evidence that the stop was executed by Nav2 declining to publish, which would put a non-safety component in the chain. |
| **Maps to** | **AT-02** |

---

### SC-05 — Protective field violated at nominal speed

**Hazard.** A person steps out from between two racks into an aisle a loaded
vehicle is traversing at nominal speed. There is no fixed guard — the aisle is
shared by design. The whole personnel-protection argument for the moving
vehicle rests on the scanner protective field being dimensioned so that the
vehicle reaches standstill before it reaches the person, at the speed the
selected field set is valid for.

| Field | Content |
|---|---|
| **S** | **S2** — a loaded AMR at nominal speed against a person: crushing against a rack, or the wheel over a foot; irreversible. |
| **F** | **F2** — aisles are shared continuously with pedestrian traffic throughout the shift; this is the defining exposure of the whole cell. |
| **P** | **P1** — in an open aisle the vehicle is visible and audible on approach and the person has lateral escape room. *Arguable, and this is the parameter most worth arguing:* a person stepping out from a blind rack gap has neither, which is P2 and PLr **e**. The honest response to that is not to re-argue the parameter — it is that the protective field must be dimensioned for the braking distance at the field set's valid speed, so that the person does not need to avoid anything. P1 is claimed on the layout precondition of open sight lines; where the layout cannot give them, the field, not the parameter, is what changes. |
| **PLr** | **d** (S2, F2, P1) |
| **Covering SF** | **SF-03** — protective field stop. Stop category 1 (SS1-t): controlled deceleration at maximum service braking, then STO and brake at standstill or at the 1 s limit, whichever comes first. |
| **Architecture** | SRS §5 target: **Category 3, PL d**. Safety laser scanner with two-channel OSSD outputs into the onboard safety system, speed-dependent field-set selection, dual-channel STO. The protective field's dimensioning is part of the safety function: a field too small for the valid speed is a design fault no architecture recovers from. |
| **Network** | None. Scanner → onboard safety system → drive inhibit. `safetyState.fieldViolation` is a report (N1). |
| **Validation test** | *Stimulus:* vehicle travelling at nominal speed; spawn an obstacle into the protective field. *Observation:* deceleration begins in the next control cycle; standstill is reached **inside** the field's dimensioned boundary; `fieldViolation` = true. Remove the obstacle: the inhibit releases only after the 2 s clear time, and motion resumes only on a fresh Nav2 command, never a resumed one. Repeat with the obstacle reaching the bumper: the stop **latches** and survives obstacle removal until an SF-08 reset. *Fault addressed:* none; this is the demand and stop-distance test. *Pass:* stop distance inside the field, no resume before the clear time, bumper latch confirmed. *Fail:* standstill outside the field boundary — which invalidates the field dimensioning, not the function. |
| **Maps to** | **AT-03** |

---

### SC-06 — Contact at creep speed, warning field occupied: the scenario with no PL claim

**Hazard.** A person walks toward a vehicle and enters the warning field. The
vehicle drops to creep (≤ 0.3 m/s). The person continues and makes contact
before, or as, the protective field trips. The injury at 0.3 m/s with free
space behind the person is a bruise, not a crush — the speed reduction exists
precisely so that the protective field, sized for creep, is large enough
relative to the braking distance to stop in time.

| Field | Content |
|---|---|
| **S** | **S1** — contact at 0.3 m/s with the protective field live underneath it: bruising, reversible. *Arguable, and the arguing matters:* S1 holds **only** while there is free space behind the person. Against a rack upright or a wall, the same 0.3 m/s crushes and S2 applies, giving PLr d — a floor this function does **not** meet. The design response is a layout precondition (no creep-speed approach into a dead end), and where the layout cannot give it, SF-03 alone must carry the case, which it does. |
| **F** | **F2** — same continuous aisle sharing as SC-05. |
| **P** | **P1** — a person walking toward a vehicle that has visibly slowed can stop walking; avoidance is possible. |
| **PLr** | **b** (S1, F2, P1) |
| **Covering SF** | **SF-04** — warning-field speed reduction. Speed limited to ≤ 0.3 m/s while the warning field is occupied. Level-based, automatic release after 2 s clear. |
| **Architecture** | **No PL is claimed, and PLr b is therefore not met by this function.** The SRS declares SF-04 safety-related but informative (SRS §3, SF-04 honesty row; §5): the speed reduction is implemented in vehicle software as scanner field output → Nav2 speed limit, and on real hardware would be safety-rated only with safety-rated speed monitoring (SLS) on a safety-rated channel. This project has neither. The honest position is stated as a chain of three sentences: *the derived floor for this hazard is PLr b; SF-04 does not meet it; the hazard is covered instead by SF-03 at PL d, whose protective field is dimensioned for the case where the speed reduction fails entirely.* SF-04 is a comfort and throughput measure that happens to reduce risk, not a measure the safety case leans on. |
| **Network** | None in the backing function. SF-04 itself runs in vehicle software — which is exactly why it carries no claim — but it is onboard, and its failure degrades to SF-03, never to a network dependency (N1). |
| **Validation test** | *Stimulus:* place an obstacle in the warning field only. *Observation:* commanded and actual speed drop to ≤ 0.3 m/s within one field-report cycle; the protective field is not violated; no stop occurs. Clear the field: nominal speed returns after 2 s. **Then the test that matters:** disable the speed-reduction handler entirely and drive at full speed into the same scenario — SF-03 must still stop the vehicle inside the protective field. *Fault addressed:* total loss of SF-04, treated not as a fault to be detected but as a condition the backing function must survive. That is the only defensible way to use an unrated function in a safety argument. *Pass:* all three observations, and specifically the third. *Fail:* the third observation failing, which would mean the safety case had quietly come to depend on unrated software. |
| **Maps to** | **AT-04** |

---

### SC-07 — Safety door opened while a transfer is running

**Hazard.** The safety door separates the aisle from the transfer conveyor and
is the guard for the conveyor's mechanical hazards. An operator opens it during
a running transfer — to retrieve a dropped label, to straighten a load — and
reaches through onto a moving pallet and a driven roller.

| Field | Content |
|---|---|
| **S** | **S2** — the conveyor nip and the moving pallet, the same hazards as SC-01; crushing. |
| **F** | **F2** — the door is the routine access to the transfer station and transfers run continuously; exposure is frequent. |
| **P** | **P1** — the conveyor runs at low speed and the pallet's approach is visible through the door opening as the operator reaches in; avoidance is possible under those conditions. *Arguable:* a door opening onto a blind approach would be P2 and PLr e, which would mean the door is the wrong guard for that geometry — a machine-design conclusion, not a parameter conclusion. |
| **PLr** | **d** (S2, F2, P1) |
| **Covering SF** | **SF-05** — door interlock, in its **stopping** aspect. The F-CPU removes the conveyor transfer enable on loss of closed-and-locked: stop category 1, ramp ≤ 500 ms then power removal, enable removed ≤ 100 ms after loss of the signal. |
| **Architecture** | SRS §5 target: **Category 3, PL d**. Two-channel NC door safety position switch on F-I/O, **independent of the standard program's `DoorClosed` process sensor** — the process sensor and the safety switch are two devices, and the SF depends only on the second. That independence is what makes N4 satisfiable at all. |
| **Network** | None. Switch → F-I/O → PROFIsafe → F-CPU → conveyor enable. The door *process* sequencing (the `PassageRequest` handshake) continues to run over the network and is irrelevant to the reaction (N1). |
| **Validation test** | *Stimulus:* transfer running; force the door safety switch open. *Observation:* the conveyor enable drops within 100 ms; `SafetyDoorClosed` = 0; `ProtectiveStopActive` = 1; the drive ramps to zero within 500 ms and power is then removed. Re-close the switch: the conveyor does **not** restart by itself. Repeat with the standard program in STOP (N4). *Fault addressed:* none; demand test. Note that the independence from the process sensor is what is really under test in the STOP repetition. *Pass:* all observations. *Fail:* a restart on door closure, or any dependence on the standard program. |
| **Maps to** | **AT-05 (a), (b), (d)** |

---

### SC-08 — Door open, transfer requested: the start-up that must not happen

**Hazard.** The conveyor is stopped and the door is open. An operator is
hand-loading a carton into the transfer station, arm through the opening. The
fleet layer's next order arrives and the standard program, seeing its own
process conditions satisfied, attempts to start the transfer. The hazard here
is not a machine that fails to stop — it is a machine that **starts**, which an
interlock that only stops would not prevent.

| Field | Content |
|---|---|
| **S** | **S2** — arm inside the equipment envelope at the conveyor nip; crushing. |
| **F** | **F1** — hand-loading with the door open between cycles is an occasional, short task, unlike SC-07's continuous routine access. |
| **P** | **P2** — an unexpected start-up gives no warning and the arm is already committed inside the opening; scarcely avoidable. Contrast SC-07's P1, where the machine was already moving and therefore visible. **A moving machine can be seen; a starting one cannot.** |
| **PLr** | **d** (S2, F1, P2) — the same floor as SC-07 by the opposite route, which is the point of carrying both. |
| **Covering SF** | **SF-05** — door interlock, in its **inhibiting** aspect: "inhibits any start while the door is not confirmed closed". The SF is one function with two duties, and a design that implemented only the stop would pass SC-07 and kill someone in SC-08. |
| **Architecture** | SRS §5 target: **Category 3, PL d**, unchanged. The inhibit is the same enable signal in its de-energized state — the conveyor enable is formed from the cycle-running flag **AND** the interlocks (CLAUDE.md §9), never from the start request. An actuator driven from a request rather than from an enable is the defect this scenario detects. |
| **Network** | None in the inhibit. The order arriving over MQTT and the handshake over OPC UA are exactly the process traffic that must **not** be able to overcome the interlock; the network's inability to start the conveyor is what is being demonstrated (N1). |
| **Validation test** | *Stimulus:* door safety switch open, conveyor stopped; request a transfer through the normal handshake. *Observation:* `TransferReady` never asserts; the conveyor enable never energizes; the request is refused by the interlock, not merely delayed by the standard program's sequence. Then close the door: a transfer becomes possible only after an SF-08 reset if a stop had latched, and in any case only on a fresh command. *Fault addressed:* none; this is the inhibit test, and it is the half of SF-05 most easily left untested. *Pass:* no enable at any point with the door unconfirmed. *Fail:* the enable energizing even briefly, including a single scan cycle, which would indicate the actuator is driven from the request rather than the permissive. |
| **Maps to** | **AT-05 (c)** |

---

### SC-09 — Charge contactor closes with no vehicle docked: live contacts

**Hazard.** The charging station's contacts are exposed conductive parts inside
the docking pocket. With no vehicle docked they are accessible: to a cleaner's
cloth, to a dropped tool, to a hand checking why a vehicle failed to charge.
If the contactor can close without a confirmed docked vehicle, those contacts
are live and the traction battery's charger is behind them.

| Field | Content |
|---|---|
| **S** | **S2** — a short across the contacts from a high-current DC source produces an arc and a burn hazard, and at the battery voltages used on this class of vehicle an electric-shock hazard cannot be excluded at specification time. *Arguable:* if the platform's charge voltage were fixed and confirmed at or below the conventional touch-voltage limit in a dry environment, S1 could be argued and PLr would fall to **a** — i.e. no dedicated safety function would be required at all. S2 is retained because the platform voltage is not fixed at spec time, and choosing the lower severity would mean the safety requirement depends on a decision nobody has made yet. |
| **F** | **F1** — a person is at the charging contacts only during cleaning or fault-finding: occasional and short. |
| **P** | **P1** — the hazard is static rather than approaching, access into the docking pocket is deliberate rather than incidental, and the station carries a charging indicator; avoidance is possible under those specific conditions. *Arguable:* if that indicator is a process lamp driven by the standard program, it is not trustworthy for avoidance and P2 applies, giving PLr d. The argument is worth noting and does not change the design — see the architecture row. |
| **PLr** | **c** (S2, F1, P1) |
| **Covering SF** | **SF-06** — charger interlock, in its **permissive** aspect. The contactor may close only while the F-CPU's own docked-position confirmation is present **and** the standard program is commanding a charge. `ChargeRequest` over OPC UA is a process precondition seen by the standard program; it is never sufficient and never reaches the F-CPU. |
| **Architecture** | SRS §5 target: **Category 3, PL d** — *above* the derived floor of PLr c, and deliberately so. SF-06 is implemented on the same F-CPU, the same PROFIsafe segment and the same two-channel F-I/O as SF-01, because building one interlock on a separate, cheaper, lower-category subsystem would add an architecture to maintain and verify in order to save nothing. **PLr is a floor** (§1.3): exceeding it is a correct outcome, and it is also why the P1/P2 argument above is bounded — either parameter choice is already satisfied by what is built. |
| **Network** | None in the permissive. The docked-position switch is F-I/O and independent of the standard program's `ChargerVehicleDocked` diagnostic; `ChargeRequest` arrives over OPC UA and is one term of the *standard* program's command, which is itself only one term of the F-CPU's AND (N1). |
| **Validation test** | *Stimulus:* command a charge with the docked-position input absent. *Observation:* the contactor output stays at 0 for the full duration of the command. Then confirm docking and command again: the contactor closes. Then force the docked input away while charging: the contactor output reaches 0 within 100 ms and **latches**; restoring docking without a reset does not re-close it. Repeat the trip case with the standard program in STOP (N4). *Fault addressed:* none; permissive and trip demand tests. The AND is what is under test — a design that closed on `ChargeRequest` alone would pass every other test in this document. *Pass:* all four observations. *Fail:* the contactor closing on any subset of the permissive. |
| **Maps to** | **AT-06 (a), (b), (c), (d)** |

---

### SC-10 — Presence in the transfer zone during a transfer, entered from the vehicle opening

**Hazard.** The transfer station's zone cannot be fully guarded: vehicles must
drive into it, so one side is an opening. A person walks in through that
opening — to retrieve a fallen carton, to inspect a pallet — while a transfer
is running. They approach the conveyor from behind, out of the aisle
operator's view and out of the door-interlock's scope, because the door is
correctly closed.

| Field | Content |
|---|---|
| **S** | **S2** — the conveyor nip and moving load; crushing. |
| **F** | **F1** — entering the transfer zone on foot through the vehicle opening is occasional; the routine access is the door side, which is SC-07. |
| **P** | **P2** — the person enters behind the running equipment, with the machine out of their line of sight and them out of everyone else's; there is no cue that would prompt avoidance. |
| **PLr** | **d** (S2, F1, P2) |
| **Covering SF** | **SF-07** — zone monitoring. F-CPU protective stop of the fixed equipment in the zone: conveyor stop category 1, ramp ≤ 500 ms then power removal, initiated ≤ 100 ms after detection. |
| **Architecture** | SRS §5 target: **Category 3, PL d**. Safety-rated zone device (light curtain or scanner field) on F-I/O, two-channel, PROFIsafe to the F-CPU. **Vehicles in the zone are not stopped by this function** (SRS B4): a person near a vehicle is protected by SF-03, on the vehicle's own independent chain. The fleet manager may reroute using the `ProtectiveStopActive` and `ZoneAOccupied` mirrors, which is process behaviour and no part of this SF. |
| **Network** | None. Zone device → F-I/O → PROFIsafe → F-CPU → conveyor enable. The two chains — cell and vehicle — never meet, and there is no computed "cell safe" flag anywhere that both consult (N1, SRS B4). |
| **Validation test** | *Stimulus:* transfer running; force the zone-device input to occupied. *Observation:* the conveyor ramps and stops within 100 ms plus the 500 ms ramp; `ProtectiveStopActive` = 1. Clear the zone: no restart without an SF-08 reset. With the zone occupied, request a transfer: `TransferReady` never asserts. Repeat with the standard program in STOP (N4). *Fault addressed:* none; demand and inhibit test. *Pass:* all four observations. *Fail:* a restart on zone clearance, which is the auto-resume defect. |
| **Maps to** | **AT-07 (a), (b), (c), (d)** |

---

### SC-11 — Reset demanded while the hazard is still present

**Hazard.** SF-07 has tripped: someone walked into the transfer zone and the
conveyor stopped. They are still in there, kneeling behind the conveyor,
retrieving what they came for, invisible from the panel. The operator at the
panel sees a stopped machine and a reset button, and presses it. This is the
scenario in which a wrong reset design kills someone, and it is the reason the
reset is specified as tightly as it is.

| Field | Content |
|---|---|
| **S** | **S2** — the person is inside the zone at the conveyor; a restart crushes. |
| **F** | **F1** — the coincidence of a zone trip with a second person still inside is occasional. *Arguable:* in a busy cell where trips are frequent and two people work the station, F2 is defensible and PLr rises to e — at which point the honest response is not a better reset button but a zone the operator can see into before resetting, i.e. a layout requirement. |
| **P** | **P2** — the person inside has no line of sight to the panel, no warning that a reset is being pressed, and no time to leave; the operator has no line of sight to the person. Neither party can avoid what the other is doing. |
| **PLr** | **d** (S2, F1, P2) |
| **Covering SF** | **SF-08** — monitored reset, in its **rejection** aspect: a reset while any SF trigger is still present is ignored. |
| **Architecture** | **This is the scenario where the mapping needs care, and it presents better honestly than tidily.** The SRS targets **PL c** for SF-08, not the PL d this hazard derives. That is correct, for a reason worth saying out loud: *the reset button is not what keeps the person alive.* The zone device is still occupied, so SF-07 — Category 3, PL d, unchanged and live — holds the inhibit regardless of what the panel does. SF-08's own worst credible failure is that it releases a latch it should not have released, and per the SRS a reset "never energizes anything; it clears latches only", so a spuriously released latch still leaves the SF-07 permissive absent and the conveyor stopped. PL c is adequate for a function that cannot, by construction, start anything. Three design rules do the work, and all three come from CLAUDE.md §9: **(1) Wire NC, program NO** — a shorted or broken reset line reads as *not resetting*, never as a reset. **(2) Edge, not level** — the latch releases on the **falling** edge of a signal held between 0.2 s and 3 s; a taped-down button, a bridged terminal or a signal high at power-up is a stuck actuator, is rejected, and raises a reset-fault. A level-based reset would make every safety stop momentary. **(3) No auto-resume** — the reset clears the latch and nothing else; every subsequent actuator start is a fresh command formed from **re-read** sensor states, so even a valid reset with the person still inside starts nothing. |
| **Network** | None, and this is the one users most want to break. `SafetyResetRequired` is a read-only mirror; no OPC UA client, no fleet manager, no dashboard button can clear a latch. The reset input is a local, manual, monitored contact and there is no second path to it (N1). |
| **Validation test** | *Stimulus:* trip SF-07 with the zone device, leave the zone occupied, then apply a valid 1 s reset pulse at the panel. *Observation:* the reset is **rejected** — the latch does not clear and `SafetyResetRequired` stays 1. Then, still with the zone occupied, hold the reset input high permanently: the latch stays and a reset-fault is flagged. Then pulse 0→1→0 within 100 ms: rejected as below the 0.2 s minimum. Then clear the zone and apply a valid pulse: the latch releases **exactly on the falling edge**, `SafetyResetRequired` goes 1→0, and **no output energizes as a consequence of the reset alone** — verified by observing the conveyor enable remains 0 until the standard program issues a fresh start. *Fault addressed:* short-circuit and stuck-at-1 on the reset input, addressed by the hold-window rejection rather than by an exclusion. *Pass:* all four observations, and especially the last: an output that energizes on reset is the defect this whole function exists to prevent. *Fail:* any latch release while a trigger is present, or any actuation caused by the reset itself. |
| **Maps to** | **AT-08 (a), (b), (c), (d)**; the still-inhibited conveyor is cross-checked by **AT-07 (b)** |

---

### SC-12 — Supervision lost mid-order: where the method stops

**Hazard.** The MQTT broker dies while a vehicle is executing an order. The
vehicle is in an aisle, loaded, with people around. It is now unsupervised: no
fleet manager knows where it is going, and no new order or cancellation can
reach it.

This scenario exists to mark a boundary, and it is deliberately the one
scenario in this document with **no risk-graph derivation and no PLr**.

| Field | Content |
|---|---|
| **Risk graph** | **Not applied.** Not because the risk is zero, but because the risk graph derives the required performance of a *safety function*, and the reaction to supervision loss is not one. Applying it here would produce a PL figure attached to a broker, a network and a Python process — which is precisely the claim invariant 1 exists to forbid. |
| **What the hazards actually are** | The hazards present during the outage are SC-04's and SC-05's: a person in the vehicle's path, a person pinched against a structure. They are unchanged by the broker's death, and they are covered, unchanged, by **SF-02 and SF-03** — both wholly onboard, both live throughout the outage, neither able to notice that a broker exists. |
| **What SF-09 is** | A **degraded-mode behaviour**, not a safety function (SRS SF-09; B2). The VDA 5050 client detects loss of supervision and the vehicle performs a controlled stop through normal Nav2 deceleration, keeps its order data, and removes no torque. Target: stop initiated within one watchdog period. That target is a **quality** requirement, not a safety requirement, and carries no SIL or PL claim. |
| **Why it may resume automatically** | Every other latched stop in this document requires a monitored manual reset. This one resumes by itself when supervision returns and the fleet manager has resynchronized — permitted precisely *because* it is not a safety stop. The asymmetry is not an inconsistency; it is the definition of the boundary. Reading the automatic resume as a lapse would mean having read SF-09 as a safety function. |
| **The error this prevents** | Promoting supervision loss to a safety event is an attractive mistake: it looks conservative. It is the opposite. It makes the safety case depend on network availability and latency, so that a broker restart, a certificate expiry or a switch reboot becomes a safety-relevant event — and a safety argument that degrades when a Docker container restarts is not a safety argument (invariants 1, 2). |
| **Validation test** | *Stimulus:* kill the MQTT broker while the vehicle executes an order. *Observation:* the vehicle decelerates to a controlled stop within the watchdog period, keeps its order, and the `connection` last-will fires. **Then, during the outage, trip the simulated protective field.** *This is the observation the scenario exists for:* SF-03 must still stop the vehicle, with no broker, no fleet manager and no network — demonstrating that the safety functions never depended on any of them. Restore the broker: the vehicle resumes after fleet resync **without** an operator reset. *Fault addressed:* none; this is an independence demonstration, not a fault test. *Pass:* all three observations. *Fail:* SF-03 failing or degrading during the outage, which would mean a safety function had acquired a network dependency somewhere. |
| **Maps to** | **AT-09** |

---

## 3. Coverage

### 3.1 Safety function coverage

Every safety function in SRS §3 is exercised by at least one scenario, and the
three functions with two distinct duties carry two scenarios each so that both
duties are tested.

| SF | Function | Scenarios | Why more than one, where applicable |
|---|---|---|---|
| SF-01 | Cell e-stop chain | SC-01, SC-02, SC-03 | Demand in motion; demand at rest against unexpected start-up; the single-fault case that Category 3 is claimed for |
| SF-02 | Vehicle e-stop | SC-04 | — |
| SF-03 | Protective field stop | SC-05 | Also the backing function for SC-06 and the independence demonstration in SC-12 |
| SF-04 | Warning-field speed reduction | SC-06 | — |
| SF-05 | Door interlock | SC-07, SC-08 | Stopping duty and inhibiting duty; a design meeting only the first passes SC-07 and fails SC-08 lethally |
| SF-06 | Charger interlock | SC-09 | — |
| SF-07 | Zone monitoring | SC-10 | Also the function that actually holds the hazard in SC-11 |
| SF-08 | Monitored reset | SC-11 | — |
| SF-09 | *Supervision watchdog — not a safety function* | SC-12 | Carried to mark the boundary; no PLr, no PL claim |
| SF-20…29 | *Reserved: arm safety* | none | Out of scope until the arm gate (SRS §1.3) |

### 3.2 Risk-graph parameter coverage

| Parameter | Value | Scenarios | Exercised |
|---|---|---|---|
| S | S1 | SC-06 | yes |
| S | S2 | SC-01…05, SC-07…11 | yes |
| F | F1 | SC-02, SC-04, SC-08, SC-09, SC-10, SC-11 | yes |
| F | F2 | SC-01, SC-03, SC-05, SC-06, SC-07 | yes |
| P | P1 | SC-01, SC-03, SC-05, SC-06, SC-07, SC-09 | yes |
| P | P2 | SC-02, SC-04, SC-08, SC-10, SC-11 | yes |

All six parameter values are exercised, and no value is carried by a single
contrived scenario except S1, which is carried by SC-06 — the one scenario
whose severity is genuinely low, and whose S1 is explicitly conditional on a
layout precondition stated in its own table.

### 3.3 PLr distribution

| PLr | Scenarios | Note |
|---|---|---|
| a | none | Reached only at S1/F1/P1, where a dedicated safety function is not the proportionate measure |
| b | SC-06 | Derived, and deliberately **not met** by SF-04; carried by SF-03 instead |
| c | SC-09 | Derived floor, **exceeded** by the shared Category 3 / PL d architecture (§1.3) |
| d | SC-01…05, SC-07, SC-08, SC-10, SC-11 | The dominant outcome |
| e | none | See below |

A d-dominated distribution is the expected result for this machine, not a sign
of a flattened analysis: an AGV cell's characteristic hazards are crushing
between masses (S2) in continuously shared space (F2), and that pairing reaches
d as soon as avoidance is anything less than certain.

**PLr e is not reached, and four scenarios say where it would be.** SC-01,
SC-05, SC-07 and SC-11 each identify the parameter that would push them to e —
a button out of reach, a blind rack gap, a door onto a blind approach, a zone
the operator cannot see into before resetting — and in all four the response
written down is a change to the *machine* (layout, field dimensioning, choice
of guard, sight lines), never a re-argued parameter. That is the
correct use of a risk graph: when it lands on e, it is telling you the
guarding is wrong, not that the control system needs to be better.

### 3.4 Single-fault behaviour

Category 3 is a claim about single faults, so at least one scenario must
exercise one rather than assert it. **SC-03** does: a broken conductor in one
channel of the two-channel e-stop loop, with the pass criterion being that the
fault produces the safe reaction, is detected by discrepancy monitoring, and
latches until a monitored reset. It also names the three mechanisms separately
— polarity, redundancy, diagnosis — because only the combination supports the
Category 3 sentence.

Two further scenarios test fault behaviour without being fault-injection
tests: **SC-06** requires the safety case to survive the *total* loss of an
unrated function, and **SC-11** rejects a stuck-at-1 reset input by the
hold-window rule rather than by claiming a fault exclusion for it.

No exhaustive fault list has been applied. §0 says so, and this section does
not quietly retract it.

### 3.5 Network independence

Every scenario's reaction row reads "none". That is not a formatting artefact —
it is the single check that matters most for this architecture, so it is stated
per scenario rather than once. Twelve scenarios, twelve reaction chains, zero
messages: button or sensor → hardwired or F-I/O → PROFIsafe or onboard inhibit
→ de-energized output. The network appears in this document only as read-only
mirrors written after the fact, and in SC-08 and SC-12 as the thing being
demonstrated *powerless*.

---

## 4. Mapping — scenario to safety function to acceptance test

| Scenario | Title | SF | PLr | Target (SRS §5) | AT |
|---|---|---|---|---|---|
| SC-01 | E-stop mid-transfer at the nip point | SF-01 | d | Cat 3, PL d | AT-01 (a), (b) |
| SC-02 | E-stop at rest, unexpected start-up | SF-01 | d | Cat 3, PL d | AT-01 (d) *(+ one added observation, see SC-02)* |
| SC-03 | Single fault: broken e-stop channel | SF-01 | d | Cat 3, PL d | AT-01 (c) |
| SC-04 | Vehicle e-stop where the scanner cannot see | SF-02 | d | Cat 3, PL d | AT-02 |
| SC-05 | Protective field violated at nominal speed | SF-03 | d | Cat 3, PL d | AT-03 |
| SC-06 | Contact at creep speed | SF-04 | b | **no PL claimed**; carried by SF-03 | AT-04 |
| SC-07 | Door opened during a running transfer | SF-05 | d | Cat 3, PL d | AT-05 (a), (b), (d) |
| SC-08 | Door open, transfer requested | SF-05 | d | Cat 3, PL d | AT-05 (c) |
| SC-09 | Charge contactor with no vehicle docked | SF-06 | c | Cat 3, PL d (exceeds floor) | AT-06 (a)–(d) |
| SC-10 | Presence in the transfer zone | SF-07 | d | Cat 3, PL d | AT-07 (a)–(d) |
| SC-11 | Reset demanded with the hazard present | SF-08 | d *(hazard)* | PL c for SF-08; hazard held by SF-07 at PL d | AT-08 (a)–(d), cross-check AT-07 (b) |
| SC-12 | Supervision lost mid-order | SF-09 *(not a safety function)* | **not applied** | none — no SIL/PL claim | AT-09 |

Every scenario maps to exactly one SF and at least one acceptance test in
SRS §4. No scenario introduces a safety function, a reaction, a timing figure
or a mirror node that the SRS does not already define; where this document adds
anything, it adds a justification, not a requirement.

---

## 5. What this document still does not establish

Repeated at the end because a reader who skipped §0 will read this:

- No PL is **achieved** anywhere in this project. Every figure above is a
  target derived from judgement about a described cell.
- No MTTF<sub>D</sub>, DC<sub>avg</sub>, CCF or PFH<sub>D</sub> has been
  estimated, and no SISTEMA model exists. Category 3 and PL d appear together
  here as a design intent pairing, not as a computed result — and the pairing
  is not automatic: Category 3 alone reaches PL d only at adequate MTTF<sub>D</sub>
  and diagnostic coverage, neither of which is quantified here.
- No fault list from ISO 13849-2 has been applied exhaustively, and no fault
  exclusion has been justified against its tables. SC-03 exercises one fault
  because Category 3 demands at least one demonstration; it is not a validation.
- No component has been selected, procured or certified.
- No test in this document has been run. The validation tests are
  specifications for the acceptance tests in SRS §4, which are executed at
  their own gates.
- The hazard descriptions are engineering judgement about a described cell,
  not the output of a machine-specific risk assessment. On real hardware, with
  real masses, speeds, sight lines and access frequencies, every S, F and P
  above would be re-derived, and some of them would change.
