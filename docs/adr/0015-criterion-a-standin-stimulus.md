# ADR 0015: M5 criterion (a) after the F-I/O probe — the automated standard-DB stand-in stimulus, and the amended criterion

Status:        accepted (owner ruling 2026-08-04, recorded 2026-08-05)

What this ADR does, stated before anything else:

- It **supersedes two claims inside ADR 0011 D2**
  (`docs/adr/0011-sensored-autonomy-architecture.md`): the assertion that
  taking the named fallback **"changes no gate criterion"**, and the fallback's
  stated mechanism — the standard-DB stand-in *"driven by Modify from a watch
  table"*. Both are wrong, each shown wrong by a different piece of evidence,
  and both are named below rather than quietly dropped. **The rest of ADR 0011
  stands**: D1 (the vehicle's onboard safety controller), D3 (the motion
  envelope, as refined by ADR 0012 D1), D4 (the monitoring plane), D5 (the
  claim boundary), and the evidence table F1–F12 are untouched. D2's primary
  path — configured F-I/O stimulated by the API — remains the correct design
  for a real installation; what is superseded is its availability here and its
  fallback's description, not its architecture.
- It **amends roadmap M5 criterion (a)**. The amended text is quoted in full in
  the Decision and lands in `docs/roadmap.md` in the same round as this ADR.
  No other criterion of the M5 row changes, and no other gate's row changes.
- **Invariants 1–13 are untouched.** The stand-in path runs entirely inside the
  simulation host — an API write into the CPU's data, this project's stand-in
  for wiring — and never touches MQTT, OPC UA or the VPN, so invariant 1 holds
  on this path the same way it held on the F-I/O design. No invariant names
  the F-I/O path, the stimulus mechanism or the criterion text.
- No accepted ADR is edited; CLAUDE.md §8 forbids it. Forward pointers live
  here and in `docs/roadmap.md`.

Every figure in this ADR is quoted from a named project report with its units.
No external vendor source is newly cited; where a vendor fact is used (F5, F6)
it is used through ADR 0011's pinned evidence table, verified 2026-07-30 there.

---

Context:

**What was tried, in order.**

1. **ADR 0011 D2 (accepted 2026-07-30)** made the F-I/O input path conditional
   — settled in the tool by the first M5 brief — and named a fallback: the
   standard-DB stand-in of `plc/forklift-safety/SPEC.md` §7, driven by *Modify*
   from a TIA watch table. D2 asserted the fallback was *"inert by
   construction"* and its preamble that the ADR settles the architecture
   *"without changing the gate's criteria."*
2. **The adversarial architecture review**
   (`docs/reports/m5-judge-architecture-review.md`, finding 1, SEVERE) found
   that assertion wrong in the fallback branch: roadmap M5 criterion (a)
   requires that the scanner's *"signals reach the F-CPU safety program's
   F-blocks"*, and under watch-table *Modify* a human watches the Gazebo
   intrusion and types the value — the scanner's signal reaches nothing. The
   owner deferred the blocker until the probe returned a verdict rather than
   pre-deciding it.
3. **The probe ran — m5-03** (`docs/reports/m5-03-fio-probe-run.md`;
   procedure and verdict `plc/forklift-safety/FIO-FEASIBILITY.md` §7, filled
   at the tool by the owner 2026-08-04). Verdict: **`ADR 0011 D2 fallback`**.
   The findings that matter here, each from that report:
   - The configured ET 200SP F-DI compiled, downloaded and ran with safety
     mode activated — and **never left passivation**: `QBAD` = `PASS_OUT` = 1
     at rest and after STOP→RUN, `ACK_REQ` never rose so no acknowledgement
     was ever offered, `DIAG` = `16#00`, and both modules read *"Module
     exists. OK"* online. The F-driver holds the channel fail-safe without
     declaring a fault anywhere a diagnostic reader would look.
   - The API's by-name write to the F-channel **returned without error and
     read `True` back through the API for the full 60 s hold — while the TIA
     watch table read `FALSE` for the same 60 s**. Writer's view and
     consumer's view never agreed for a single sample: the API writes a
     process image the F-driver overwrites.
   - **Fail-safe tags cannot be modified from the engineering connection at
     all in permanent safety mode.** The tool refuses verbatim: *"Debugging of
     fail-safe tags is not allowed in permanent safety mode. (2206:000002)"*.
     So **D2's named fallback could not have run as written**: its stated
     mechanism was never exercised under the conditions the demonstration
     would impose, and the refusal closes the whole class of designs that
     stimulate F-data by *Modify* (LESSONS 2026-08-04). The fallback's
     "inertness" was a claim about a different configuration.
4. **Owner ruling 2026-08-04 — both remedies, not one** (recorded in
   `docs/TODO.md` under the m5-03 heading): the stand-in is upgraded to an
   **automated, API-driven standard-DB stimulus**, labelled a stand-in
   everywhere and carrying the Siemens S015 validity check visibly in the
   F-code, **and** roadmap criterion (a) is **amended by ADR** to state what
   that stand-in can actually demonstrate. The ruling's own caution: the API
   path to a *standard* DB was at that moment plausible but unproven — the
   probe had only ever written an F-channel.
5. **The proof ran — m5-03b**
   (`docs/reports/m5-03b-standin-stimulus-proof.md`, 2026-08-04). The API
   write to `SafetyInputStandIn` was verified **in the consumer's view** — the
   F-block's own instance data, which the API never writes; only the F-program
   does, by copying the stand-in inside the F-runtime group:
   - `WriteBool` returned in **4.4 ms**; the F-block instance
     (`InstF_Forklift_Safety.EStopCircuitClosed`) followed **80.4 ms** later —
     inside one F-OB cycle, `FOB_RTG1` being OB123 at 100 ms.
   - The **monitored reset ran on API-written data**: the button held
     **1000 ms** — inside the in-force window, `ResetHoldMinTimer.PT` =
     200 ms, `ResetHoldMaxTimer.PT` = 3000 ms, both read from the running
     CPU — and on release the demands cleared **37.0 ms** later, edge-triggered
     as specified. Closing a circuit alone cleared nothing: no auto-resume.
   - Reopening the E-stop circuit re-asserted `EStopDemand` **79.1 ms** later,
     with `ZoneStopDemand` correctly staying clear — per-circuit
     discrimination, which cannot be an echo of the write.
   - **A second, independent witness**: the run was repeated against the CPU's
     own OPC UA server (`opc.tcp://192.168.53.1:4840`), a different protocol
     on a different stack, **which does not expose `SafetyInputStandIn` at
     all** — so nothing it sees can be an echo of the writer's process image;
     the only route from an API write to a mirror change runs through the
     F-program. 52 505 polls over 30 s (~0.57 ms sampling interval) agreed
     with the API view on every transition and every non-transition: demands
     cleared on the mirror **41 ms** after reset release, re-asserted
     **114 ms** after the circuit reopened, returned **94 ms** after restore.
   - **Caveat carried, not waived**: the run is on the probe copy
     `safe_amr_FIOPROBE`. Evidence is qualified by the environment that
     produced it (LESSONS 2026-07-27), so the sequence **repeats on the
     working project `safe_amr` before the gate cites it**.

**Why the criterion had to move and not just the stimulus.** Criterion (a) as
written says the scanner's signals reach the F-CPU safety program's F-blocks —
phrasing that, read against the build, implies the configured F-I/O path. That
path is now **proven unavailable on this installation** (TIA Portal V21,
S7-PLCSIM Advanced V7.0, safety system version V2.8 — the m5-03 environment
block). A criterion that names a path the tool cannot provide is unfailable in
the wrong way: no work can meet it, so the gate either fails on tool
limitations the architecture already disclosed (ADR 0011 F4/F5), or the
criterion is quietly re-read — which CLAUDE.md §10 forbids. Conversely a
criterion rewritten to merely describe what m5-03b built would be unfailable in
the other way. The amendment below is written to stay a test.

---

Decision:

### D1 — The M5 input path is the **automated API-driven standard-DB stand-in**; watch-table *Modify* is retired as a stimulus for gate evidence

The scanner's simulated signal enters the F-program by exactly one mechanism:
the vehicle-side field evaluation writes the three Bools of
`SafetyInputStandIn` (a **standard** DB) **through the S7-PLCSIM Advanced API
by tag name, with no human in the loop**. The F-program reads the stand-in
inside its F-runtime group, as `plc/forklift-safety/SPEC.md` §7 already has it.

*Modify* from a watch table is retired as a stimulus for any gate evidence:
the probe showed the engineering connection cannot modify fail-safe data at
all in permanent safety mode (`2206:000002`, m5-03), and the judge review had
already shown a hand-driven stimulus fails criterion (a)'s substance — a human
typing a value is not a scanner signal reaching anything. Watch tables remain
what they are everywhere else in this project: a **reading** instrument.

Verification discipline, from the two runs and binding on M5 evidence: a write
on this path is proven **in the consumer's view** — the F-block instance data —
never in the writer's read-back (LESSONS 2026-08-04, the m5-03 API/watch-table
divergence), and the gate's evidence carries at least one witness that cannot
see the written datum (the m5-03b pattern: the CPU's OPC UA server, which does
not expose the stand-in DB).

### D2 — Roadmap M5 criterion (a) is amended to the following text

> (a) a safety laser scanner is added to the model and its simulated signal
> reaches the F-CPU safety program's F-blocks through the **labelled
> standard-DB stand-in** `SafetyInputStandIn`, written **by the S7-PLCSIM
> Advanced API by tag name with no human in the loop** — configured F-I/O is
> not used, because the m5-03 probe proved the simulated F-DI stays passivated
> on this installation (ADR 0015) — and F-logic demonstrably executes on it: a
> protective-field intrusion in Gazebo trips an F-latched stop that overrides
> teleop and autonomous motion **with no hand at a watch table anywhere in the
> chain**, the demand and its clearance are read in the **consumer's view**
> (the F-block instance data) and corroborated on an **independent witness
> that does not expose the stand-in DB** (the CPU's own OPC UA `Safety/`
> mirrors), and the stop is cleared only by the edge-triggered monitored reset
> after the field clears; the stand-in carries the **S015 validity check
> visibly in the F-code**, is **named a stand-in in the showcase narration
> wherever the path is described**, and demonstrates **F-logic execution
> only — no safety integrity, no PL, Category, SIL or PFH** (ADR 0011 D5, F6)

What keeps it a test the work can fail, item by item: the chain must be
automated end to end (one hand on one watch table fails it); the intrusion
must originate in the Gazebo field evaluation, not in a test script poking the
DB directly; the demand must be read in the F-block instance data, not in the
writer's read-back (the m5-03 failure mode, excluded by construction); the
independent witness must corroborate every transition; the stop must override
**both** modes; the reset must be the monitored, edge-triggered one and
nothing else may clear the latch; and the S015 check and the stand-in
labelling must be visible in the artifact, not asserted in prose. Each of
those is observable and each can come out wrong.

What it deliberately no longer requires: that the signal traverse configured
F-I/O. That requirement is not weakened by wording — it is removed, named, and
replaced by the honest statement of the path that exists, because m5-03
settled in the tool that the F-I/O path does not.

Criteria (b)–(e) of the M5 row are unchanged. None of them names the input
path: (b) is about acceptance tests and mirrors, (c)–(d) about sensors, SLAM
and Nav2, (e) about the HMI and the showcase. The showcase sentence already
carries the D5 narration duties this amendment leans on.

### D3 — What is superseded in ADR 0011 D2, said plainly

Two claims, each with the evidence that killed it:

1. **"The fallback is inert by construction. It is the path the project
   already runs"** — and, by the preamble, taking it **changes no gate
   criterion**. Wrong twice. The judge review showed the manual fallback
   cannot satisfy criterion (a) at all; and m5-03 showed its stated mechanism
   — *Modify* on fail-safe-adjacent data under permanent safety mode — is
   refused outright by the tool, so the fallback as written could not even
   run. "We already do this" was a claim about a different configuration, and
   it was never exercised under the conditions the primary path would have
   imposed (LESSONS 2026-08-04). A named fallback is tested against the gate
   criterion in the same breath as it is named (LESSONS 2026-07-30); this ADR
   exists because that was not done.
2. **The fallback's mechanism itself.** The standard-DB stand-in survives —
   it is the input path — but its stimulus is the automated API write of D1,
   never *Modify*. `plc/forklift-safety/SPEC.md` §7's *Modify* mechanism and
   its §2 checkpoint F3 are rewritten by the m5-15 F-program spec brief
   against this ADR, not silently.

Everything else in ADR 0011 D2 stands: the primary path remains the correct
design where the tool supports it, the F6 consequence (standard tags are
unsafe; S015; disclosure not protection) is confirmed and now load-bearing,
and D2's closing statement — **the fallback does not reopen D1** — holds:
which controller the F-program *is* does not depend on how its inputs are
stimulated. Only the input path is a stand-in.

---

Consequences:

**The distinction the whole amendment turns on, stated once.** The automated
stand-in path **does** deliver: a stimulus with **no human in the loop**, a
signal that **reaches the F-program's F-blocks**, and **F-logic that
demonstrably executes on it** — multi-step, edge-triggered, per-circuit
discriminating logic, proven in the consumer's view and on an independent
witness (m5-03b). It **does not** deliver: **any safety integrity
whatsoever**. The path is a **standard DB**. ADR 0011 F6 is unchanged —
standard tags are explicitly not fail-safe data, TIA's S015 requires a
process-specific validity check per F-runtime group, and TIA's mechanism is
disclosure rather than protection. ADR 0011 D5's claim boundary is untouched:
PLr targets only, never an achieved PL, Category, SIL or PFH, and every M5
artifact on this path says which side of that line it sits on.

What becomes harder:

- **The labelling burden is now permanent, not conditional.** F6's consequence
  — the stand-in labelled wherever it appears, the S015 check visible in the
  F-code — was D2's burden *if* the fallback was taken. It is taken. Every
  document, caption, watch-table screenshot and spoken line inherits it
  (FIO-FEASIBILITY §6, now binding on m5-15).
- **Evidence on this path is evidence about logic only.** The F-I/O behaviour
  clauses of ADR 0011 F5 do not even apply — there is no simulated F-I/O in
  the chain — so nothing measured here says anything about passivation,
  reintegration or device behaviour, and each artifact must say so.
- **The gate cannot cite m5-03b as it stands.** The proof ran on the probe
  copy `safe_amr_FIOPROBE`; it repeats on the working project `safe_amr`
  before criterion (a) evidence cites it, and the probe copy is deleted per
  FIO-FEASIBILITY §0.1 rule 3.
- **A retired conditional is written into several committed documents.**
  ADR 0011 D2's condition propagated correctly after the judge review
  (m5-j2), and those documents now state a pending verdict that is in, or a
  *Modify* mechanism that is retired. A conditional decision propagates with
  its condition attached, and its **resolution** propagates the same way
  (LESSONS 2026-07-30): the sweep list is in the m5-20 report, and each
  document is corrected under its own layer's brief.
- **The stimulus becomes a deliverable.** Someone must build and own the
  vehicle-side writer that drives `SafetyInputStandIn` from the field
  evaluation; that is design work for the m5-15 spec round, not a side effect.

What becomes easier:

- **Criterion (a) is decidable again.** Before this ADR it named a path the
  installation cannot provide; the gate could only fail on it or re-read it.
  Now it names the path that exists and stays failable on seven observable
  points.
- **The demonstration is stronger than the fallback ADR 0011 assumed.** The
  judge's "worse branch" — a hand-driven stimulus laundered as the scanner
  path — is structurally excluded: there is no hand in the chain, and the
  two-witness discipline makes writer-echo evidence impossible.
- **AT-08 (b) moves into reach.** TWIN-DEMO-MAP defers the sub-0.2 s reset
  rejection *"if, and only if, the F-spec's stimulus strategy provides timed
  injection"* — the automated stimulus held a reset for a commanded 1000 ms
  (m5-03b), so timed injection exists; whether the sub-case lands is the
  safety-spec agent's call, not this ADR's.
- **The next reader gets the whole story in one document**: what was tried
  (F-I/O), what failed and how it failed silently (passivation with clean
  diagnostics), what the named fallback turned out to be (unrunnable as
  written), what replaced it (the automated stand-in, proven twice), and what
  the replacement does not buy (any integrity at all).

What this ADR does **not** decide: the vehicle-side writer's design, its rate
and its failure behaviour (m5-15 round); the field evaluation's geometry
(m5-12); whether AT-08 (b) enters scope (safety-spec); the wording of
`plc/forklift-safety/SPEC.md` §7's rewrite (m5-15); and anything about
criteria (b)–(e), the fleet layer or later gates.

Relationship to the ADRs this one stands on:

| ADR | Relationship |
|---|---|
| **0011** sensored autonomy architecture | **Partially superseded.** D2's "changes no gate criterion" / "inert by construction" fallback claims and the fallback's *Modify* mechanism are superseded by D1/D3 here. D2's primary-path design, its feasibility discipline and its "does not reopen D1" clause stand as record. D1, D3, D4, D5 and F1–F12 are untouched |
| **0012** envelope composition | Untouched. Its "what it does not decide" list left the criterion-(a) tension *"deliberately open pending m5-03's verdict"* — this ADR closes it |
| **0014** motion control locus | Untouched. Its open-item list names the m5-03 verdict as pending input; it is in, and nothing in D1–D3 here reaches motion control |
| **0010** milestone restructure | The gate order and numbering are untouched. D2's statement of M5's content stands; only the M5 row's criterion (a) text changes, by this ADR, in `docs/roadmap.md` — the single source for gate criteria |

---

Alternatives:

- **Keep criterion (a) as written** — rejected. m5-03 proved no work can meet
  it on this installation: the simulated F-DI passivates permanently and
  declares no fault. A criterion that cannot be met as written is reported as
  such, never redefined by reading (CLAUDE.md §10) — this ADR is that report,
  with the owner's ruling on it.
- **Keep the manual watch-table fallback and label it honestly** — rejected
  twice over. The judge review showed it fails the criterion's substance (a
  human types the value; the scanner's signal reaches nothing), and m5-03
  showed the tool refuses fail-safe *Modify* outright in permanent safety mode
  (`2206:000002`) — the fallback as ADR 0011 D2 wrote it could not run at all.
- **Rewrite the criterion to describe what m5-03b built** — rejected. A
  criterion that describes the build is a test the work cannot fail, which
  quietly closes the gate the day it is written. The amended text instead
  demands seven observables the showcase run can miss.
- **Present the stand-in as the safety path, since F-logic runs on it** —
  rejected. ADR 0011 F6: standard tags are unsafe and TIA's mechanism is
  disclosure, not protection. The criterion therefore carries the non-claim
  inside its own text rather than in a footnote.
- **Defer the amendment to gate verification** — rejected. That is the judge
  review's concrete failure scenario: the contradiction was decidable now, and
  discovering it at m5-19 would cost the gate a verification round and invite
  exactly the laundering the labelling discipline exists to prevent.
