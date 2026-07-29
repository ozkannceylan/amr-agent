# Report m5a-01 — ADR 0009, early cell-scope opening of the safety layer

brief:               docs/briefs/m5a-01-adr-0009-early-safety.md
status:              done
files_changed:       docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md (new), docs/reports/m5a-01-adr-0009-early-safety.md (this file). Nothing else touched — roadmap.md (m5a-02), PLAN.md, TODO.md, CLAUDE.md, docs/safety/, docs/interfaces/, plc/ and every earlier ADR are unchanged, per the brief's forbidden list. One pathspec-scoped commit of exactly these two files, repo-local owner identity, no bare commit; other agents were writing in the tree at the time.
invariants_touched:  none. Invariant 1 is honoured by construction and stated as such (D3.1: the demand forms inside the CPU; nothing on the network is between a demand's cause and its reaction). Invariant 7 is stated in the direction that matters (D3.2: the F-program reads nothing the standard program writes, so a standard-program halt cannot break it; the standard program's dependency is a permissive whose failure mode is motion refused). Invariant 10 is the one the observed build currently breaks — the F-program writes status tags the standard teleop FB also owns — and the ADR fixes the resolution as architecture (F-data plus a standard-program mirror copy) rather than leaving it to discovery. Gate order is ADR 0008's, not a CLAUDE.md §2 invariant, so the departure of D2 is a ruled exception rather than an invariant change.

## What the ADR records

Five decisions, accepted 2026-07-29, plus a context section carrying the live
facts.

**Context — the tool observation, dated and read back.** The 1513F-1 PN
(6ES7 513-1FM03-0AB0) project compiled with its F-runtime group present (main
safety block calling the F-FBD block with its instance DB), downloaded, CPU in
RUN; the `DemoCell` server interface compiled and served; the bridge connected
over OPC UA with a verified two-way round trip (ROS-published input read in the
watch table, watch-table output modify seen on the ROS topic); and the F-program
executing end to end — a zone signal set the F-latch, the latch **held after the
signal cleared**, and the reset-required flag rose. The ADR states plainly what
that closes (the compile / RUN / F-logic-executes checkpoint, substantially) and
what it does not (the formal acceptance procedure), and it names the three
reasons the run is not an acceptance test: network-fed zone input, level reset
acknowledgement, standard program running throughout.

**D1 — Scope.** SF-01, the cell instance of SF-08, and the SF-07 pattern as a
marked arena zone, each an instantiation of an existing SRS function. SF-02/03/04
and the vehicle instance of SF-08 stay at M6, SF-09 at M7, SF-05/06 at M9, the
arm functions at M11. Two boundaries inside the twin are drawn explicitly: the
lidar obstacle stop stays process logic and is not SF-07 (ADR 0008 D3 stands),
and the M4 row's process reset is not SF-08.

**D2 — Gate discipline.** The departure from CLAUDE.md §6 is recorded as an
owner ruling with four bounds: M4's criteria unchanged, nothing early-opened
cited as M4 evidence, nothing early-opened closing M5, and the wording "M5's
cell-scope core is being built early" rather than "M5 is open".

**D3 — Coupling.** Demand forms inside the CPU; standard program consumes
F-data and the F-program never reads teleop state; OPC UA carries process
consequences plus a read-only `Safety/` mirror group written by the standard
program. A diagram shows the safety path beginning and ending inside the CPU
box.

**D4 — Fallback.** M4's five behaviours and its showcase are quoted as
unchanged. The fallback is required to be **inert by construction** — clear-reading
F-data flags, mirrors rendering as "not present", the scenario section opening
with its own precondition — on the ground that a fallback needing a document
edit to take effect is not a fallback. The live trigger narrows to the formal
acceptance procedure and the three build gaps.

**D5 — ISO 13849 basis.** A table maps SF-01 → SC-01/02/03, SF-07 → SC-10,
SF-08 → SC-11 with the PLr floors and SRS §5 targets as they already stand,
including SC-11's PLr d being held by SF-07 rather than by the reset. No new SF,
PLr or PL value. Simulation demonstrates acceptance-test logic and claims no
achieved PL; the simulated F-input is labelled an engineering stand-in.

The build gaps from the owner's 2026-07-29 state are carried as consequences
with their resolutions fixed as architecture: the dual-writer conflict (F outputs
move to F-data, standard copies to mirrors, F never writes the standard status
group again), the network-fed zone input (moves to the simulated F-I/O channel —
and cannot satisfy the M5 session-down criterion in its present form), and the
level reset (must become the monitored edge SF-08 specifies).

## open_questions

1. **The m5a-04 brief says F-LAD; the CPU is running F-FBD.** The observed build
   implements `F_Forklift_Safety` in **F-FBD**, and the briefing note for m5a-04
   also says F-FBD is the owner's language, while the m5a-04 brief text reads
   "F-LAD, not SCL" and "described element-by-element" in F-LAD. Language is a
   specification question, not an architecture one, so ADR 0009 lists it under
   what it does not decide — but the brief and the running program disagree, and
   a spec written in the other language costs the owner a re-transliteration.
   Worth ruling before m5a-04 is dispatched.
2. **TODO.md still carries the F-layer checkpoint as pending, in two places.**
   The "owner — URGENT" block reads "F-layer checkpoint (ADR 0009
   abort-to-fallback trigger, ~15 min): Safety Advanced licence present; an empty
   F-project compiles; the F-runtime group reaches RUN", and the "owner — M5
   entry, carried" block still reads "No M5 brief until they exist". Both are
   substantially answered by the 2026-07-29 observation, and the second is now
   contradicted by eight issued M5 briefs. TODO.md is outside this agent's write
   scope; requested rather than edited.
3. **PLAN.md's M5 block states the superseded version of the same fact** — "the
   remaining feasibility checkpoint (Safety licence compile, F-runtime RUN) is
   the abort-to-fallback trigger" — which ADR 0009 now narrows to the formal
   acceptance procedure. PLAN.md is in this agent's write scope but not in this
   brief's deliverable or its commit pathspec, so it is reported, not edited. It
   should not be left to disagree with the ADR across a verifier run.
4. **The M5 roadmap criterion and the current F-input channel are incompatible
   as built.** The criterion requires the three reactions to execute "with the
   bridge stopped and the OPC UA session down"; an F-input fed from a
   network-written standard tag cannot. This is not a criterion problem — it is
   the reason m5a-04 §7 must specify a simulated F-I/O / engineering stimulus
   rather than reuse the tag the 2026-07-29 run used.
5. **One recording will contain two visually identical stops.** The lidar
   process stop and the zone safety demand both stop the same machine. D1 and D5
   require them named apart everywhere, but nothing enforces it; whoever briefs
   the showcase should treat the spoken naming as an exit item, not as a caption.
6. **The interface check after the CPU swap is only partly closed.** The bridge
   round trip proves the `DemoCell` interface serves the nodes it exercised; it
   does not prove every tag, the derived URI, or the access-control state
   survived the *Change device*. TODO's urgent item stands as written.
7. **The `Safety/` group's home is an interface decision with an ADR 0006
   consequence.** If the mirrors land on a new server interface rather than on
   `DemoCell`, that interface's *name* is the namespace URI. m5a-06 as briefed
   extends `DemoCell`, which avoids it; recorded so the constraint is not
   rediscovered.

next_suggested:      m5a-02 (arch-docs, small) — the roadmap note, then let the orchestrator reconcile PLAN.md's M5 block and TODO.md's two feasibility items against ADR 0009 in the same wave, before the F-LAD/F-FBD language question is ruled and m5a-04 is dispatched.
