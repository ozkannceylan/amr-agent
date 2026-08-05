# m5-20 — amend M5 criterion (a) by ADR

    gate:                M5
    agent:               arch-docs
    goal:                A new ADR records the owner's 2026-08-04 ruling on roadmap M5 criterion (a), states what the automated stand-in stimulus demonstrates and what it does not, and the M5 roadmap row is rewritten to match it.
    invariants_touched:  none expected — but see §4
    inputs:
      - docs/roadmap.md (the M5 row, criterion (a))
      - docs/adr/0011-sensored-autonomy-architecture.md (D2, D5, F6)
      - docs/adr/0012-envelope-composition.md
      - docs/adr/0014-motion-control-locus.md
      - plc/forklift-safety/FIO-FEASIBILITY.md (§6 and §7)
      - docs/reports/m5-03-fio-probe-run.md
      - docs/reports/m5-03b-standin-stimulus-proof.md
      - docs/reports/m5-judge-architecture-review.md
      - docs/TODO.md (the m5-03 heading — the ruling and its three-part definition of done)
      - docs/LESSONS.md
    deliverable:         docs/adr/0015-<short-title>.md, plus the amended M5 row in docs/roadmap.md
    done_when:           The ADR is written in the CLAUDE.md §8 format, the M5 row's criterion (a) reads what the evidence can actually demonstrate, and every claim in the ADR cites the report or document it comes from. A reader who knows nothing of this session can tell from the ADR alone what was tried, what failed, what replaced it and what the replacement does not buy.
    forbidden:
      - editing docs/adr/0011 or any other accepted ADR — supersede, never edit (CLAUDE.md §8)
      - writing outside docs/adr/, docs/roadmap.md and docs/PLAN.md
      - inventing a measurement; every figure is quoted from a named report with its units
      - softening the claim boundary, or letting any wording imply an achieved PL, SIL or PFH
      - restating the M5 criterion so that it merely describes what was built (a criterion is a test the work can fail)

---

## 1. What happened, in order — verify each against the inputs

1. ADR 0011 **D2** made the F-I/O path conditional and named a fallback: the
   standard-DB stand-in of `plc/forklift-safety/SPEC.md` §7, driven by *Modify*
   from a watch table. D2 asserted the fallback **changes no gate criterion**.
2. The **m5-judge architecture review** found that assertion wrong in the
   fallback branch: roadmap M5 criterion (a) says the scanner's *"signals reach
   the F-CPU safety program's F-blocks"*, and under watch-table Modify a human
   types the value and the scanner's signal reaches nothing. The owner deferred
   the blocker until the probe returned a verdict.
3. **m5-03** ran the probe. Verdict `ADR 0011 D2 fallback`. Two findings matter
   here and both are in the report: the configured F-DI never left passivation
   with no acknowledgement reachable, and **fail-safe tags cannot be modified
   from the engineering connection at all in permanent safety mode**
   (`2206:000002`) — so **D2's own named fallback could not have run as
   written.**
4. **Owner ruling 2026-08-04: both remedies, not one.** Automate the stimulus
   *and* amend the criterion.
5. **m5-03b** proved the automated stimulus, twice, and the second witness
   matters: the run was repeated against the CPU's own OPC UA server, which does
   not expose the written DB at all. Quote the figures from that report.

## 2. What the ADR must decide, and say plainly

**The decision** is the owner's ruling in 1–5 above. Your job is to record it so
it binds, not to re-take it.

State, in the Consequences section, the distinction the whole amendment turns
on. The stand-in path **does** deliver: an automated stimulus with no human in
the loop, a signal that reaches the F-program's F-blocks, and F-logic that
demonstrably executes on it. It **does not** deliver: any safety integrity. The
path is a standard DB; ADR 0011 **F6** is unchanged — standard tags are unsafe,
TIA's S015 requires a process-specific validity check per F-runtime group, and
TIA's mechanism is disclosure rather than protection. ADR 0011 **D5**'s claim
boundary is untouched.

Say explicitly that **D2's "changes no gate criterion" is superseded** and why.
An ADR that quietly drops a wrong claim teaches the next reader nothing.

## 3. The roadmap row

Rewrite criterion (a) of the M5 row so it is **a test the work can fail**, and so
it is honest about the path. It must still require that the scanner's simulated
signal reach the F-program and drive F-logic — that part was proven — while not
claiming an F-I/O path that does not exist on this installation. Name the
stand-in as a stand-in in the criterion itself, not only in a footnote.

Check whether criteria (b)–(e) of the same row depend on (a)'s wording. If any
do, say so in the report; change only what the ruling reaches.

## 4. Two things to check, and stop if either is true

1. **If amending the criterion would touch an architecture invariant**, write the
   ADR as *proposed*, state the conflict, and stop (CLAUDE.md §8).
2. **A conditional decision propagates with its condition attached** (LESSONS
   2026-07-30). ADR 0011 D2's conditionality was dropped from four downstream
   documents and survived only in the roadmap. Sweep for statements that depend
   on D2's *scope* — not only for occurrences of a string — and list in your
   report every document that now says something the m5-03 verdict falsifies.
   Do not edit them; you do not own them. List them.

## 5. Working discipline

- Read `docs/LESSONS.md` before you start. Entry 2026-07-30 on conditional
  decisions and entry 2026-08-04 on the fallback that could not run are directly
  yours.
- **Do not commit.** The orchestrator commits by pathspec.
- Write `docs/reports/m5-20-criterion-a-amendment.md` in the CLAUDE.md §5 report
  format when done. Keep it short.
