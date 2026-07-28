# Report m3-32 — outstanding rows for the re-specified case-D tests

brief:               docs/briefs/m3-32-outstanding-rows.md
status:              done
files_changed:       [bridge/EVIDENCE_LATENCY.md, docs/reports/m3-32-outstanding-rows.md]  (nothing committed)
invariants_touched:  none
open_questions:
  - T4.6b needs the step-20 dwell to be reachable, and §B.13 F1 (the presence
    verdict never asserting) still blocks it. So the m3-29 rebuild alone does not
    make item 11 runnable; the F1 fix is a precondition for it, not only for
    T2.2–T2.4. Recorded in the row itself.
  - The as-run table's denominator stays **twelve** — the §11 T4 list as it stood
    when that accounting was written. The spec now lists thirteen. The two are
    reconciled in prose immediately below the table rather than by growing the
    count, per LESSONS 2026-07-28 (61).
next_suggested:      Owner TIA session: download the m3-29 build, capture the SPEC revision with the download (§B.12 item 13), then run T4.6 / T4.6b / T4.7 and record the freeze-to-latch time as a number.

---

## What was changed, and what was deliberately not

Accounting only. **No measured figure, count, timestamp or verdict was altered**
anywhere in the file; `git diff` is four hunks, all in §B.7 and §B.12, and every
number that was in the file before is in it unchanged.

### §B.12 — four new owner-outstanding rows

| # | Row | Why it is outstanding |
|---|---|---|
| 10 | T4.6 as re-specified (D ii, mid-motion), elapsed freeze-to-latch time recorded as a number against the ≤ 3.2 s bound | postdates the run; the old step **failed** here on the m3-05 build; needs the m3-29 rebuild plus Group 4 (`PositionRef`, `PositionFrozen`, `PositionWindowTimer.ET`) |
| 11 | T4.6b (D i, at rest), latch within `DRIVE_FAULT_DELAY`, `PositionFrozen` staying `FALSE` | did not exist at run time; needs the m3-29 rebuild **and** the dwell, which F1 still blocks |
| 12 | T4.7 as inverted — the reset **refused** while the frozen image claims motion | pass condition inverted after the run; the old step was attempted and found not executable; can only follow a T4.6 that actually latches |
| 13 | Rebuild baseline — the SPEC revision the downloaded program was built to, captured **with** the evidence | Section B's figures are all against the m3-05 build; the m3-29 download moves that baseline and items 9–12 are defined against it |

### §B.7 — annotation, not renumbering

* The as-run rows for **4.6** and **4.7** keep their as-run verdicts (`ran —
  failed`, `attempted, not executable`) and gain a *superseded by m3-29* clause
  pointing at the new §B.12 items. Nothing was renumbered or deleted, and no row
  was added to that table.
* Two paragraphs were added after the table: one stating what m3-29 changed
  (T4.6 became mid-motion, T4.6b was added, T4.7 was inverted, all three needing
  the rebuild), and one stating explicitly that the rows are annotated rather
  than renumbered, that the twelve rows are the list as it stood at writing time,
  and that the now-thirteen-step list is reconciled by outstanding rows and not
  by a larger denominator.
* The "T4.7 could not be executed" paragraph gained one sentence recording that
  the step has since been inverted, so the paragraph reads as the non-execution
  of the *old* step.

### One stale request closed

The tail of the "No pass claim over all twelve T4 steps" paragraph asked `plc/`
for the same accounting on §11's *"Pass: all twelve"* line. At HEAD that line
reads **"Pass: all thirteen"** and carries, in the same place, the caveat that
thirteen is the specified list rather than a claim about a run and that a step
added after a run gains an outstanding row. The paragraph now records the
request as satisfied instead of still asking for it. Its own figures — seven
ran, one failed, one not executable, four not run — are untouched.

## Sources read

`plc/demo-cell/SPEC.md` §11 was read **only at HEAD** (`git show
HEAD:plc/demo-cell/SPEC.md`, HEAD = `eb3ebd4`, which contains m3-29's
`f445981`); the working-tree copy was never opened, since a sibling agent is
editing it. `docs/reports/m3-29-case-d-rearm.md` supplied the bound (≤ 3.2 s,
never sooner than ≈2.1 s), the implementation delta the rebuild consists of, and
the two requests this brief satisfies.
