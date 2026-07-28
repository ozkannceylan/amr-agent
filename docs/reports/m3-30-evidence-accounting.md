# Report m3-30 — evidence accounting corrections from the m3-28 review

brief:               docs/briefs/m3-30-evidence-accounting.md
status:              done
files_changed:       [bridge/EVIDENCE_LATENCY.md, docs/reports/m3-30-evidence-accounting.md]  (nothing committed; `plc/demo-cell/SPEC.md` also shows modified in the tree — that is the concurrent sibling agent, not this brief)
invariants_touched:  none
open_questions:
  - `SPEC.md` §11 T4's **"Pass: all twelve"** line is the pass claim the brief's
    `done_when` targets, and it lives in `plc/`, outside this agent's write
    scope. Section B now states that no all-twelve claim is backed by this
    evidence and requests the corresponding `plc/` change; it needs a `plc`
    brief. Same for T1's **"Pass: all six"**, which counts T1.4 — a step §B.13
    F1 records as failed (m3-28 finding 2, labelling gap 1). This brief did not
    cover T1 and nothing in Section B was changed for it.
  - Three §B figures beyond the two the brief enumerated also reproduced from
    no committed file. They were corrected under the same rule; see "Scope
    note" below. If the orchestrator wanted the enumerated list treated as
    exhaustive, the three extra corrections are the ones to review.
next_suggested:      One `plc` brief to re-derive `SPEC.md` §11's T1 and T4 pass lines from the as-run record (T4 → the new §B.7 roster; T1 → §B.13 F1), in the same commit as the F2 §6.6/§7 revision if that is still open.

---

## What was changed, and why each change is accounting rather than measurement

**1. T4.11 is now accounted for, in both places the brief allowed.**

- New `§B.7` subsection **"T4 as-run accounting — seven of the twelve steps
  ran"**: a twelve-row table of `SPEC.md` §11 T4 as this run executed it
  (ran / attempted-not-executable / not run) with a pointer to where each is
  recorded, derived from the run rather than from the scenario table as it
  stands today.
- New **`§B.12` item 9** for T4.11 as owner-outstanding, with its reason: it
  postdates the run (m3-27 added it), and it needs both a narrowed-constant
  TIA recompile and a program built to the m3-27 spec, where the build in RUN
  was m3-05.
- The roster ends with the explicit statement that **no pass claim over all
  twelve T4 steps is supported by this evidence** — seven ran, one of those
  failed (T4.6/F2), one was attempted and found not executable (T4.7), four
  did not run (T4.5, T4.8, T4.9b, T4.11).

The `"Pass: all twelve"` string itself is in `plc/demo-cell/SPEC.md` §11, not
in any `bridge/` file. It is requested in the evidence text and in
`open_questions` above, not made.

**2. §B.13's un-reproducible figures now carry provenance or are named as
run observations.** Every replacement figure was read out of the committed
CSVs — `evidence/plc-observe-2026-07-27-plcsim-main.csv.gz` (observer, clock
`t_mono_s`, 0.1 s quantised) and `evidence/latency-2026-07-27-plcsim-caseD.csv.gz`
(bridge #3). No run was repeated and no figure that already reproduced was
touched.

| Figure as written | Status | Now |
|---|---|---|
| F1 "1.4401 → 0.5400 at t=47.10 … until t=48.92 — **1.8 s**" | reproduces from no committed file | block stated as **2.11 s** with the rule and rows named: first blocked sample t=47.0044, last t=49.1175, first clear t=49.2179, 22 consecutive rows at `0.5400331616401672`. The old reading is kept, marked as not reproducing, and noted as conservative |
| F1 soft-limit abort at "**t=54.96**" | reproduces from no committed file | **t=54.7600**, the single row carrying `2.4123001098632812` (the run's maximum) with the three status transitions. Old reading marked in the same note |
| F2 "travelled **from 0.3093**" → ≈0.62 m | real value, wrong role | the armed reference is the motion-start position, bracketed **0.0477–0.0618 m** by the 0.1 s sampling, giving ≈**0.87 m**. 0.3093 named as `Input/ConveyorBeltPosition` at t=358.7713, a mid-motion sample ≈1.9 s after motion start |

**3. Scope note — three further corrections of the same class**, found by
sweeping §B rather than trusting the enumerated list (LESSONS 2026-07-27 on
enumerated briefs, and LESSONS 2026-07-27 on applying a rule to every signal of
the same kind). All are attribution, none changes a measured conclusion:

- **The case-D heartbeat pair "767 → 1251"**, in both `§B.7`'s case D row and
  `§B.13` F2. It does not name the window's endpoints, and **767 is not a
  heartbeat value at all** — it is the index of the freezing
  `ConveyorBeltPosition` write in the caseD session file. The heartbeat reads
  **750** in the freezing row (t=363.3057) and **1268** in the drop row
  (t=389.7431); 1268 is also bridge #3's `heartbeat_writes` counter, its last
  write. 1251 is a genuine heartbeat value, but from 0.85 s before the drop.
- Two short **provenance paragraphs** added, one to F1 and one to F2, naming
  the file, the column, the clock and its quantisation for every timestamp in
  those findings — the gap that produced all of the above (a §B.13 timestamp
  never said which clock it was on).

Everything m3-28 reproduced digit for digit was left alone: L7's six samples,
§B.3's rates and per-session R1 figures, the 4537 / 1352 heartbeat freezes, the
0.50 / 0.51 s `HEARTBEAT_STALE_TIME` readings, the +36.0 / +39.0 / +8.9 s
no-auto-resume intervals, the 11.79 s / 0.0 s session-reaping figures, the
0.9273 / 0.1500 freeze values and the 26 s undetected window. I re-checked the
no-auto-resume and heartbeat-freeze figures against the observer CSV while
sweeping and they reproduce; they are unchanged.

## What this brief did not do

- No file outside `bridge/` was edited. `plc/demo-cell/SPEC.md` was read only at
  its committed revision (`git show HEAD:`), never from the working tree.
- Nothing was re-run: the only execution was reading the committed gzipped CSVs.
- No code, no config, no dependency change. Nothing committed.
- Sections A and C are untouched, as is `EVIDENCE_SIGNAL_LOSS.md` (checked: it
  carries no T4 pass claim, so nothing there counts T4.11).
