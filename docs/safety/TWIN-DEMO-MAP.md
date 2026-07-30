# The forklift twin demonstration, mapped onto the SRS

Addendum to `docs/safety/SRS.md` and `docs/safety/PL-SCENARIOS.md` for the early
cell-scope opening of **ADR 0009**. It **adds nothing**: no safety function, no
acceptance test, no risk-graph parameter, no PLr, no PL value, no timing figure.
It states which existing SRS text the twin instantiates, which acceptance
sub-cases the demonstration exercises and which it defers, and the wording that
keeps the recording true.

| Document | What it fixes | Relation to this one |
|---|---|---|
| `docs/safety/SRS.md` §3, §4, §5 | The functions, their ATs, the PL targets, the honesty section | **Contract.** If this addendum disagrees, the SRS wins and this one is corrected |
| `docs/safety/PL-SCENARIOS.md` | The risk-graph derivations behind every PLr quoted below | **Contract.** No parameter is re-derived here |
| `docs/adr/0009-*.md` | Scope (D1), gate bounds (D2), coupling (D3), fallback (D4), ISO 13849 basis and wording discipline (D5) | **Binding** |
| `docs/adr/0010-milestone-restructure-forklift-first.md` | The gate order every reference here uses, and what M5 now contains (D2, D7) | **Binding** |
| `docs/roadmap.md` row M5 | The gate criterion this work does **not** close | **Binding** |

**Gate numbers.** ADR 0010 extends ADR 0009 rather than superseding it: what
that ADR opened early as cell-scope content on the twin is now M5's own subject
matter, and M5 absorbs the vehicle chain with it, so **one gate — M5, on the
forklift twin — carries both the safety layer and autonomy** (ADR 0010 D2, D7).
AT-01, AT-07 and AT-08 therefore land at M5, and so do AT-02, AT-03 and AT-04,
which this addendum does not touch (NC-1). SRS §4 carries the per-function
landing gate; the AT identifiers are unaffected and are used here exactly as the
SRS writes them.

---

## 1. What the twin is

| # | Statement |
|---|---|
| **T1** | One teleoperated forklift plant in Gazebo, every motion setpoint formed by the **standard** program (ADR 0008 D1). The machine guarded here is PLC-commanded plant, not an autonomous vehicle — the cell chain is the correct chain, and there is no onboard safety layer to be the other one. |
| **T2** | The safety demand **forms inside the CPU and stays there** (ADR 0009 D3.1). What leaves the CPU is a process consequence and a read-only mirror. |
| **T3** | Every F-input is an **engineering stand-in** for a hardwired, safety-rated device that does not exist in this project (§5.2). |
| **T4** | **The reaction path is not instantiated.** SF-01 and SF-07 de-energize hardwired outputs; this plant has no output to de-energize. The observable stop is the standard program dropping its motion permissive and zeroing its three setpoints, which then travel to the plant over OPC UA and the bridge. That is a **process consequence of the demand**, never the safety reaction. |
| **T5** | The F-run of 2026-07-29 is evidence that the **F-logic executes** — a latch formed, held after its cause cleared, and raised a reset-required flag. It satisfies no acceptance sub-case: the input was network-fed, the acknowledgement was a level rather than the monitored edge, and the standard program ran throughout (ADR 0009, context and alternatives). It is not counted anywhere below. |

---

## 2. The three functions

| SF | SRS text instantiated | On the twin | PLr floor, and where it is derived | SRS §5 target |
|---|---|---|---|---|
| **SF-01** cell e-stop chain | Trigger: *"Any cell e-stop mushroom button actuated … two-channel NC, discrepancy-monitored by the F-CPU"*. Reaction: *"F-CPU de-energizes all fixed-equipment enabling outputs … stop category 0 … ≤ 100 ms"* — **not instantiated** (T4). Safe state: *"`EStopActive` latched (level)"*. Reset: *"Latched until: all buttons unlatched → monitored reset per SF-08"*, no auto-resume | A **single-channel** simulated e-stop F-input, read wire-NC / program-NO, latching `EStopDemand` in F-data; the standard permissive drops and all three setpoints go to `0.0`. The SRS's equipment list — conveyor, door, charger — does not exist on this plant, and neither does the second channel | **d** — SC-01 (S2, F2, P1) and SC-02 (S2, F1, P2); SC-03 is the single-fault scenario Category 3 is claimed for | **Category 3, PL d** |
| **SF-07** zone monitoring, **as a pattern** | Trigger: *"Presence detected in the monitored … zone (safety-rated zone device … on F-I/O) while any fixed equipment in that zone … is enabled"*. Reaction: *"conveyor **stop category 1** (ramp ≤ 500 ms then power removal) … initiated ≤ 100 ms after detection"* — **not instantiated** (T4). Reset: zone clear restores the permission, *"but a trip during an active transfer latches"* | A **marked arena zone** the forklift is driven into, signalled by a zone F-input stand-in, latching `ZoneStopDemand`. Two substitutions, named: the equipment guarded is the twin's own drive, not a conveyor, and what the zone detects is the **machine**, not a person. The twin therefore instantiates the **pattern** — zone occupied → F-latch → motion refused → reset required — and not the hazard SC-10 describes. The latch is unconditional here: there is no transfer to be "active" | **d** — SC-10 (S2, F1, P2) | **Category 3, PL d** |
| **SF-08** monitored reset, **cell instance** | Trigger: *"Operator actuates the reset device … after the cause of a latched SF has been cleared"*. Reaction: *"signal must rise, be held between 0.2 s and 3 s, and the latch releases on the falling edge"*; high at power-up or longer than 3 s is a stuck actuator, rejected with a reset-fault; *"Reset while any SF trigger is still present is ignored"*. Safe state: *"Reset never energizes anything"* | A reset device stand-in on an **F-input** — never a client write (§6 R1). It clears the F-latches only; motion returns solely on a fresh teleop enable edge. The 2026-07-29 build's level acknowledgement becomes the monitored edge (ADR 0009, consequences) | **d for the hazard** — SC-11 (S2, F1, P2). The hazard is **held by SF-07** at Category 3 / PL d, not by the reset | **PL c**, adequate because a reset starts nothing |

**The PL line, said once.** The twin **derives nothing**: it introduces no hazard
and exposes no person, so no risk graph applies to it. Every figure above is
quoted from the SRS §5 target line and its `PL-SCENARIOS.md` derivation, as the
design target of the function whose logic is being modelled. A PLr is a property
of the hazard, not of the instance demonstrating it, and it is a **floor** —
SF-08's PL c under SC-11's PLr d is correct, not a gap, because the hazard is
held by SF-07 (`PL-SCENARIOS.md` §1.3, SC-11 architecture row). No parameter is
re-argued here and no gap is closed by re-arguing one.

---

## 3. Acceptance sub-cases: in scope, deferred

Nothing below is passed. **In scope** means the T6 demonstration procedure
exercises it; **deferred** means it lands at M5 proper — the F-I/O half of that
gate, where the forklift's safety scanners are wired into the F-CPU's F-blocks
(ADR 0010 D2) — on real F-I/O outputs.

| Sub-case | The SRS sub-case, in brief | On the twin | Status |
|---|---|---|---|
| **AT-01 (a)** | Force one e-stop channel open mid-transfer → enabling and contactor outputs 0 within 100 ms, `EStopActive` = 1 | Assert the e-stop stand-in while the forklift is driving → `EStopDemand` latches, permissive drops, three setpoints `0.0`, mirror rises, model stops | **in scope**, as logic and ordering only. No output is de-energized (T4) and the 100 ms figure is **not measured** (SRS §5) |
| **AT-01 (b)** | Repeat with the **standard CPU program in STOP** (B3) | — | **deferred.** The twin's observable consequence is produced *by* the standard program, so halting it removes the observable instead of testing it. That the demand's *formation* needs no standard code is architecture (ADR 0009 D3.2), not this sub-case |
| **AT-01 (c)** | Open only one of the two channels → trip **plus discrepancy fault** | — | **deferred.** One stand-in channel, no second channel, no discrepancy monitoring. SC-03 is not exercised, so **no Category is demonstrated** on the twin |
| **AT-01 (d)** | Release the button without reset → outputs stay off | Release the e-stop stand-in → the demand latch holds, motion does not return, `SafetyResetRequired` stays 1 | **in scope** |
| **AT-07 (a)** | Force the zone input occupied during an active transfer → ramp-and-stop within 100 ms + 500 ms ramp, `ProtectiveStopActive` = 1 | Drive the forklift into the marked zone → `ZoneStopDemand` latches, permissive drops, three setpoints `0.0`, mirror rises | **in scope**, as logic and ordering only. No ramp and no power removal: **no stop category is demonstrated**, and no timing is claimed |
| **AT-07 (b)** | Clear the zone → no restart without an SF-08 reset | Reverse out of the zone → the latch holds, the setpoints stay `0.0` | **in scope.** This is the sub-case the 2026-07-29 run resembles and is **not** that run (T5) |
| **AT-07 (c)** | With the zone occupied, request a transfer → `TransferReady` never asserts | With the demand standing, a **fresh teleop enable edge** returns no motion and no setpoint | **in scope.** The inhibiting duty, the half most easily left untested (`PL-SCENARIOS.md` SC-08 on the same shape) |
| **AT-07 (d)** | Standard program in STOP, repeat (a) | — | **deferred**, for AT-01 (b)'s reason |
| **AT-08 (a)** | Hold the reset input high permanently → latch stays, **reset-fault flagged** | Hold the reset stand-in asserted → no latch clears, for as long as it is held; a signal already high at power-up is rejected the same way | **in scope**, both halves. The upper bound and the power-up rejection are what make it a reset *fault* rather than merely a non-event |
| **AT-08 (b)** | Pulse 0→1→0 within 100 ms (< 0.2 s) → rejected | — | **deferred.** Rejecting a too-short actuation requires a stimulus with controlled sub-0.2 s timing; a hand-driven stand-in at the engineering interface cannot produce one. It moves into scope if, and only if, the F-spec's stimulus strategy provides timed injection |
| **AT-08 (c)** | Valid pulse with the trigger still present → rejected | Actuate the reset with the e-stop or the zone stand-in still asserted → refused, `SafetyResetRequired` stays 1 | **in scope.** SC-11's rejection aspect — the scenario SF-08 exists for |
| **AT-08 (d)** | Clear the cause, valid pulse → latch releases **on the falling edge**, `SafetyResetRequired` 1→0, **no output energizes** | Clear the cause, actuate the reset → latches clear, mirror falls, **and the machine does not move**: motion returns only on a separate fresh enable edge | **in scope.** The falling-edge release is in scope with the monitored sequence; the 0.2 s–3 s window is **not measured**. "Nothing energizes" is the load-bearing observation |

---

## 4. Non-claims

| # | The twin does **not** claim |
|---|---|
| **NC-1** | **SF-02, SF-03, SF-04 and the vehicle instance of SF-08 are out of scope** at this gate (ADR 0009 D1). A vehicle-shaped machine stopping when a zone is entered is **not** SF-03: this plant has no safety laser scanner, no protective or warning field, no STO, no bumper and no onboard safety layer at all. They land at **M5**, with the safety scanners and the navigation stack the forklift acquires there (ADR 0010 D2, D7) — the same gate as the cell-scope functions above, no longer a later one. |
| **NC-2** | **No achieved PL, anywhere.** Every figure in §2 is a design target derived from judgement about a described cell. No SISTEMA model, no MTTF<sub>D</sub>, DC<sub>avg</sub>, CCF or PFH<sub>D</sub>, no certified component, no ISO 13849-2 validation (SRS §5; `PL-SCENARIOS.md` §0, §5). Simulation demonstrates **acceptance-test logic**. |
| **NC-3** | **No Category is demonstrated.** Category 3 is a claim about single faults, redundancy and diagnosis; the twin has one stand-in channel and no diagnostics, and AT-01 (c) is deferred. |
| **NC-4** | **No safety-rated input exists.** Every F-input is an engineering stand-in (§5.2). The demonstration shows what the safety program does with an input, never how the input arrives. |
| **NC-5** | **No safety reaction path exists** (T4). No de-energization, no stop category, no measured time. Millisecond figures stay design requirements for real hardware. |
| **NC-6** | **Nothing here is an acceptance test passed, and nothing closes M5** (ADR 0009 D1, D2.3). The M5 criterion additionally requires each AT with its B3 sub-case, the same reactions with the bridge stopped and the OPC UA session down, and the read-only mirrors — and, since ADR 0010 D2 widened M5 to carry autonomy on this same twin, the vehicle-chain tests AT-02, AT-03 and AT-04 with the inhibit demonstrably acting below the navigation stack, closed by a **recorded safety + autonomy showcase**. |
| **NC-7** | **The M3 demonstration cell is unchanged.** Its red mushroom stays a **process stop** (ADR 0004; `PL-SCENARIOS.md` N2). Sharing a CPU with an F-runtime group does not make it part of one, and nothing in that cell may be recorded or labelled as any SF. |
| **NC-8** | **The lidar obstacle stop and the process reset stay standard-program process logic** (ADR 0008 D3; ADR 0009 D1). The obstacle stop is not SF-07 and not SF-03; the process reset is not SF-08. They never share a tag name, a node, a lamp or a sentence with the F-layer. |
| **NC-9** | **Link loss stays degraded mode, not a safety event** (invariant 2; SRS B2). The twin's HMI- and bridge-link latches are process logic and are not SF-09 either. |

---

## 5. Wording

### 5.1 What the recording must say

Three statements, spoken as well as written, on a cell where a viewer can see
both kinds of reaction at once (ADR 0009 D5).

> **On the demand.** "This is the F-CPU forming a safety demand — the logic of
> SF-01 of the safety requirements specification, running in the safety program.
> The demand forms inside the CPU. Nothing on the network created it, and no
> client can clear it. What you see stopping in the simulation is the *process
> consequence*: the standard program drops the motion permissive and zeroes its
> setpoints. On real equipment the reaction is a hardwired de-energization from
> the F-I/O, and that path does not exist on this plant."

> **On the numbers.** "Category 3 and PL d are the design target the
> specification sets for this function, derived from the cell hazard in the PL
> scenarios. They are a target for real hardware. Nothing here is a measured,
> validated or achieved performance level, and no Category is demonstrated by a
> simulation."

> **On the inputs — the stand-in sentence, to be used as written.** "The inputs
> that trip this demand are engineering stand-ins. In a simulated cell there is
> no wiring, so the value a safety-rated device would put on a hardwired
> two-channel F-input — the e-stop, the zone device, the reset — is written into
> the F-input image from outside the CPU over a software interface. What is
> demonstrated is what the safety program does with the input, never how the
> input arrives; the stand-in carries no category, no performance level and no
> claim."

### 5.2 The stand-in rule, stated once so no document has to restate it

A stand-in is a substitute for **wiring**, not a substitute for a safety input.
Two consequences follow, and both are binding:

1. **It carries no claim.** Not a Category, not a PL, not a channel count, not a
   diagnostic coverage. Wherever a stand-in appears — spec, watch table, HMI
   text, scenario step, recording — it is labelled as one.
2. **A stand-in fed over the network is doubly disqualified.** The 2026-07-29 run
   drove the F-block from a standard tag written over OPC UA. That form is an
   engineering stand-in and is **never** called the safety path; it is also
   unable to satisfy the M5 criterion at all, since a reaction whose input
   arrives over OPC UA cannot execute with the session down. The F-inputs move to
   the simulated F-I/O / engineering interface (ADR 0009, consequences), and that
   interface is not the `DemoCell` process interface any cell client can write.

### 5.3 Say, never say

| Say | Never say |
|---|---|
| "F-CPU safety demand", "the logic of SF-01", "the SF-07 **pattern**" | "SF-07" bare for the marked zone; the twin instantiates the pattern, not the transfer-station function |
| "e-stop" **only** for the F-side stand-in device and its demand | "emergency stop" or "e-stop" for anything on the standard side — the M3 panel mushroom, the lidar obstacle stop, the HMI process banner. That naming discipline (ADR 0004; `opcua-nodes.md` §10.1) is unchanged and now matters more, because a correct use exists one cabinet away |
| "the obstacle stop is standard-program process logic, not a safety function" | "protective stop" for the lidar latch; "the safety system saw the obstacle" |
| "the demand formed inside the CPU; the network carried the consequence" | "the safety signal came over the network"; "the safety system stopped it over OPC UA" |
| "design target", "derived floor", "instantiates the acceptance-test logic" | "PL d achieved", "SIL", "certified", "validated", "safety-rated", "the machine is safe" |
| "the first F-run showed the latch holding — evidence that the F-logic executes" | "AT-07 passed", "the acceptance test passed", "M5 is open", "the safety layer is complete" |
| "a reset is required, and it starts nothing" | "the reset restarts the machine" — the reset clears latches; motion needs a separate fresh enable edge |

---

## 6. Rules this addendum places on the downstream specs

| # | Rule | Source |
|---|---|---|
| **R1** | The SF-08 instance's reset is an **F-input device stand-in, never a client write**. No OPC UA client, no HMI button and no dashboard clears an F-latch. | SRS SF-08; `PL-SCENARIOS.md` SC-11 network row; ADR 0009 D3.3 |
| **R2** | F-inputs are driven at the simulated F-I/O / engineering interface, never through a process node a cell client can write. | ADR 0009, consequences; §5.2 |
| **R3** | One writer per tag: F outputs live in F-data, the standard program copies them to the read-only `Safety/` mirrors, and the F-program writes no standard status tag. | Invariant 10; ADR 0009 D3.3 and consequences |
| **R4** | The zone F-input and the lidar obstacle bit never share a name, a node, a lamp or a sentence. Two ways to say "stop" now exist on one machine, and this is where the project's central claim is most likely to be misread. | ADR 0009 D1, consequences |
| **R5** | Every sub-case marked **deferred** in §3 stays an outstanding row wherever the demonstration is recorded. A deferred sub-case is never absorbed into a pass count, and a pass count is derived from what was actually run. | LESSONS 2026-07-28 |
| **R6** | If the F-layer is not ready, every item here is dropped and the M4 teleop demonstration stands alone, its criteria unchanged. | ADR 0009 D4 |

---

## 7. What this addendum does not change

`SRS.md` and `PL-SCENARIOS.md` are untouched by it. No SF number, no AT
identifier, no acceptance sub-case, no risk-graph parameter, no PLr and no PL
target is created, edited or narrowed here — where a sub-case is not exercised on
the twin it is **deferred**, which leaves the SRS text standing and the work
outstanding. The safety layer is not complete and M5 is not open (ADR 0009 D1).
