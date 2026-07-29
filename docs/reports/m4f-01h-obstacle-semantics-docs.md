# Report m4f-01h — obstacle semantics in the interface documents

```
brief:               docs/briefs/m4f-01h-obstacle-semantics-docs.md
status:              done
files_changed:       [docs/interfaces/opcua-nodes.md, docs/interfaces/bridge-design.md]
invariants_touched:  none
open_questions:      none
next_suggested:      plc/forklift/SPEC.md and sim/README.md carry the same superseded phrase per
                     74c7d5f's own report and are outside this agent's write scope; both already
                     show modified in the working tree, so that correction looks to be under way
                     on another agent's tree
```

## What changed

`docs/interfaces/opcua-nodes.md` §10.5 — the `ForkliftObstacleInStopZone` row and the polarity-note
bullet beneath it now state the three-class rule `74c7d5f` implemented (clear / distance / invalid),
give the precise fail-safe trigger list (no scan, stale beyond 0.50 s, structurally unusable, or a
sector with no sample in either valid class), and say explicitly that a beyond-range, clear scan
never sets `TRUE` on its own. Both cite `74c7d5f`. The adjacent `ForkliftObstacleMinDistance` row was
left untouched: it already states the sensor and plausibility windows (0.10…8.00 m / 0.05…8.10 m)
that give "beyond-range reads as `range_max`, inside the window" its concrete number, and its own
claims — the `0.0` sentinel pairs with the fail-safe — were not wrong, only silent on the new
clear-range behaviour, so it was left alone rather than expanded (the brief's own inputs name only the
`ForkliftObstacleInStopZone` row and the polarity note as needing correction).

`docs/interfaces/bridge-design.md` row 12 (§4.7) — the `Conversion` cell now states the same
fail-safe list, says a beyond-range return is `CLEAR` evidence at `range_max`, and cites `74c7d5f`.

One location beyond the two the brief names was corrected. `opcua-nodes.md` §10.10's ROS 2 topic map
carries a second row for the same node, and it restated the old rule in fewer words — "the scan is
invalid or stale", with no "non-finite" — which would not have matched a literal search for the
brief's quoted phrase. Read next to the now-fixed §10.5 it directly contradicted it, inside the one
document this agent is responsible for keeping internally consistent. Per the done_when's sweep
("across both files", not scoped to a section number) and LESSONS 2026-07-27 (enumerated locations
are a starting point, not exhaustive) and 2026-07-29 (a restatement in different words survives a
literal-phrase fix and a prior sweep's enumeration must not bound a later brief's done_when), it was
corrected too — minimally, pointing at §10.5 rather than repeating the rule a third time.

## Verification against done_when

- Both locations state: a beyond-range return (`inf` or `>= range_max`) is `CLEAR` evidence at
  `range_max`; the fail-safe (`TRUE`, `0.0`) fires only on a missing, stale (>0.50 s) or structurally
  unusable scan, or a sector with no sample in either valid class; never on an open horizon. Both
  cite `74c7d5f`.
- Whitespace-normalised sweep for `invalid, non-finite or stale` and `no-data` across both files: the
  only remaining hits are the "no-data sentinel" phrase on `ForkliftObstacleMinDistance` in both
  files, describing the `0.0` sentinel value for that Real — accurate, and not the trigger-condition
  rule that was fixed.
- `git diff --stat` for the two files: 2 files, 7 insertions, 5 deletions, confined to the four
  edited cells (three in `opcua-nodes.md`, one in `bridge-design.md`). Nothing else in either
  document changed — no thresholds, no other node rows, no other section.
