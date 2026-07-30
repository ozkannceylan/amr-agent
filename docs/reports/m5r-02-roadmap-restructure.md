# Report m5r-02 — roadmap restructure per ADR 0010

```
brief:               docs/briefs/m5r-02-roadmap-restructure.md
status:              done
files_changed:       docs/roadmap.md (revised, uncommitted)
invariants_touched:  none. Gate order is not an invariant. Invariants 1 and 11
                     appear only as the two readings ADR 0010 D6 records as
                     open, restated as open and not resolved.
open_questions:      two open (1 and 3 below); question 2 was closed by
                     orchestrator ruling during the run and the edit is applied.
                     The four ADR 0010 D6 decisions are carried into the roadmap
                     as open, not raised again here
next_suggested:      the safety-spec sweep of docs/safety/SRS.md — its
                     traceability "Verified at gate" column is still on the
                     ADR 0004 numbering and is now two rounds stale
```

## What changed

The gate table now runs M0–M7. **M0–M4 rows are byte-identical** to the previous
version — `git diff` shows no line touching them. The three new rows carry the
brief's substance; wording was tightened only where the brief allowed it
(D6 references written as `D6(a)`/`D6(b)` to match the ADR's own labels, B4's
parenthetical restored from the old M10 row so the boundary statement is not
reduced to its name, SF-05/06 named as the functions behind the fixed-equipment
F-I/O).

Prose, all rewritten rather than number-substituted:

- **Status line.** M4 is the current gate, **closing**, on the owner's recorded
  commissioning showcase plus the m4f-09 verification.
- **Gate-order paragraph.** Rebuilt around ADR 0010 as the head of the
  0004 → 0007 → 0008 chain, naming what it supersedes (ADR 0008 D1's order,
  ADR 0002's platform selection) and what survives (ADR 0008 D2/D3/D4,
  ADR 0007's showcase rule).
- **ADR 0009 paragraph.** Rewritten from "opened early under a fallback rule" to
  "extended, not superseded — the early content becomes M5's own subject matter,
  and the fallback rule retires when M4 closes".
- **Feasibility paragraph.** The old line said M5's first brief must settle
  F-CPU-on-PLCSIM feasibility before any safety logic is written. That has been
  overtaken in fact: ADR 0009's context records the checkpoint as substantially
  closed on 2026-07-29 and the F-program spec is written. The paragraph now says
  what is closed and what is not — the formal acceptance procedure, which is M5
  work.
- **Recordings paragraph.** Commissioning at M4, safety + autonomy at M5, fleet
  at M6, end-to-end demonstration at M7, plus the note that the demonstration is
  no longer a gate of its own.
- **Safety-completeness paragraph.** Cell-scope SF-01/07/08-cell **and** the
  vehicle chain SF-02/03/04/08-vehicle at M5; SF-09 and SF-05/06 at M6;
  SF-20…29 out of scope. Boundary statements restated under the new numbers:
  B1 at M5 and again at M6, B2 at M6, B3 at M5 for SF-01/07/08 and at M6 for
  SF-05/06, B4 at M7.
- **Open-decisions paragraph, new.** All four D6 items with their owner and
  briefing point, stated as open. None is resolved, including (b), which is
  written as the reading it is.
- **Renumbering paragraph.** Three rounds as prose about a mapping. The
  ADR 0007 and ADR 0008 rounds keep their history; the ADR 0010 round is
  described as a collapse rather than a shift, with the arm gate removed and the
  Hermes gate unparked into M7.
- **Filename note.** m4-00-hermes-survey.* → M7; m5a-* named as the ADR 0009
  round whose content is now M5's; m5r-* named as this round; the parked m3-*
  navigation sim files → M5, with "parked unverified" kept so the parking is not
  lost in the renumber.
- M0–M3 closure lines are kept verbatim.

Only the four gate numbers M8–M12 that remain in the file sit inside the
renumbering-history paragraph, where they name past rounds. Verified by search
over the finished file, not by relying on the edit list.

## Consistency

- **docs/PLAN.md** was rewritten in parallel this round and agrees: M4 closing,
  the same three gate summaries, the same four open decisions, the same filename
  mapping. No disagreement to report.
- **docs/TODO.md** already carries the new numbering (M5 carried items, pre-M6
  deep-research, pre-M7 Hermes decisions, SF-05/06 with the stations at M6). No
  disagreement to report.
- **ADR 0007 §2** states its landing points under the numbers of its own round.
  It is accepted and not edited; the roadmap restates the mapping under the new
  numbers, which is the mechanism ADR 0010 D7 prescribes.

No external vendor source is cited, so no verification date or pinned ref is
recorded. ADR 0002's 2026-07-26 vendor findings are not restated anywhere in the
file — they retire with the platform.

## Open questions

1. **docs/safety/SRS.md §4 traceability is two rounds stale.** Its "Verified at
   gate" column still reads M7/M3/M9-era numbers from the ADR 0004 order (SF-01
   at M7, SF-09 at M4, SF-20…29 at M9), so it now disagrees with the roadmap by
   more than the ADR 0010 shift. That file is the safety-spec agent's, briefed
   as m5r-05; flagging the size of the gap here so the sweep is not scoped to
   ADR 0010's delta alone.
2. **CLOSED by orchestrator ruling during this run.** The M5 row's item (b)
   originally named no acceptance-test numbers, following the brief. The
   orchestrator ruled that AT-01, AT-07 and AT-08 go in: they were named
   explicitly in the old M5 row, so naming them preserves the existing
   strictness rather than adding any, and it makes (b) symmetric with (d) and
   with the M6 criterion. Applied — item (b) now reads "the SRS cell-scope
   functions SF-01, SF-07 and SF-08 pass their acceptance tests AT-01, AT-07
   and AT-08 on PLCSIM Advanced …".
3. **Nothing in the roadmap now names the RB-KAIROS retirement as work.** The
   platform migration is a TODO line pointing at M5 briefing; the roadmap states
   the retirement as a fact of the gate order. That is the correct division, but
   it means no gate criterion asserts the old platform's artifacts are removed
   from the tree.

## Scope

Nothing outside docs/roadmap.md and this report was touched. No ADR was edited,
no D6 decision resolved, no deadline stated, no commit made — the file is left
modified in the working tree for the orchestrator to commit by pathspec.
