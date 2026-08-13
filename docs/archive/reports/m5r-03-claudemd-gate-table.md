# Report m5r-03 — CLAUDE.md section 6 gate table per ADR 0010

```
brief:               docs/briefs/m5r-03-claudemd-gate-table.md
status:              done
files_changed:       [CLAUDE.md (section 6 only, uncommitted),
                      docs/reports/m5r-03-claudemd-gate-table.md]
invariants_touched:  none
open_questions:      see below (one, on the "M4 reads as the current gate"
                     criterion)
next_suggested:      Verifier check that CLAUDE.md section 6, docs/roadmap.md
                     (m5r-02) and README (m5r-04) agree on the M0-M7 set once
                     all three land.
```

## What changed

Section 6's table replaced rows M3-M8 (the pre-ADR-0004 original, three
renumber rounds stale) with the ADR 0010 rows M3-M7, using the summaries the
brief supplied, verbatim. Rows M0-M2 are unchanged. Diff is +8/-6 lines, all
inside section 6.

Two sentences were added between the table and the closing sentence, stating
that the rows are summaries and that docs/roadmap.md carries the full criteria
and is the live order (ADR 0010). This makes the summary/criterion split the
brief describes legible in the file itself.

Verification performed:

- `grep -o 'M[0-9]|M1[0-2]'` over the whole file: gate numbers now appear only
  at lines 174-181 (the table). Line 142 (`gate: M2`, the section 5 brief-format
  example) and line 244 (`ZoneAOccupied, not M12`, the PLC memory-marker
  example) are untouched, as the brief instructed.
- No arm row and no Hermes row exist; the old table never carried either, and
  none was introduced.
- The three number-free sentences around the table ("Work proceeds gate by
  gate...", "Do not start a gate before the previous one is verified.",
  "Current gate is tracked in docs/roadmap.md...") are byte-identical, confirmed
  by the diff showing them as context lines.
- `git diff --numstat` equals `git diff --ignore-cr-at-eol --numstat` (8/6 both
  ways) and `git ls-files --eol` reports `i/lf w/lf`, so the change is real
  content and introduces no line-ending drift.
- Section 6 is ASCII-clean.
- Not committed and not staged. No file outside CLAUDE.md and this report was
  read-modified.

## Open questions

1. **"M4 reads as the current gate" was satisfied by content, not by a status
   marker.** No "current" / "closing" annotation was added to the M4 row. Two
   reasons: (a) the same section's kept-verbatim sentence says the current gate
   is tracked in docs/roadmap.md and updated only as part of closing a gate, so
   a marker in CLAUDE.md would contradict the sentence it sits beside and would
   go stale at the next gate close (the LESSONS 2026-07-27 failure mode where
   PLAN, TODO and roadmap disagree); (b) the short rows the brief supplied carry
   no marker, and the brief asked for them verbatim. As written, M4 reads as the
   current gate in that its row is the last of the unchanged M0-M4 set and
   M5-M7 are the forward program, with the status itself living one file away.
   If the orchestrator intended an explicit marker in CLAUDE.md, that is a
   one-line follow-up, but it should be ruled deliberately, since it puts gate
   status into the contract file for the first time.

## Not done, by scope

The section 5 roster (no infra row, no hmi write path stated beyond `hmi/`),
the section 3 topology and the section 4 layout were left exactly as they are,
per the brief's forbidden list. Any drift there is a separate owner
conversation.
