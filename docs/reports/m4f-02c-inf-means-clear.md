# Report m4f-02c — beyond-range returns mean clear, not absent

```
brief:               docs/briefs/m4f-02c-inf-means-clear.md
status:              done
files_changed:       [agv/forklift/scripts/obstacle_zone.py,
                      agv/forklift/README.md,
                      agv/forklift/EVIDENCE_MODEL.md]
invariants_touched:  none
open_questions:      see below, four
next_suggested:      Sweep the "invalid, non-finite or stale" phrasing out of the
                     interface and PLC documents, and retire the arena's
                     empty-sector workaround in sim/ — five locations listed below.
```

## What changed

`evaluate()` sorts every sample in the ±30° sector into three classes instead of
testing one affirmative validity condition:

| Class | Sample | Contributes | Fail-safe |
|---|---|---|---|
| `CLEAR` | `+inf`, or finite ≥ `range_max` | `range_max` | never |
| `DISTANCE` | finite in `[range_min, range_max)` | that range | via the 1.20 m threshold only |
| `INVALID` | `NaN`, `-inf`, below `range_min` | nothing | only if nothing else in the sector is valid |

Both valid classes are affirmative comparisons tested in that order, so a `NaN`
reaches neither and is `INVALID` — the rule LESSONS 2026-07-27 asks for. The
fail-safe (`in_stop_zone` TRUE, `min_distance` 0.0) now fires on no scan, a scan
older than 0.50 s, a structurally unusable scan, or a sector with no sample in
**either** valid class. A whole sector of beyond-range returns publishes
`False / 8.000`, and `8.000` is the **scan's own** `range_max`, not a constant of
the node. One new reason string, `sector clear beyond range`, so the log says
which kind of clear it is. No threshold, no timeout and no sector angle moved.

## How it was verified

Fault matrix re-run against the node as its own process, real messages on the
real topics, no Gazebo: **21 cases, PASS, 0 failing**. Two rows changed
expectation — `all samples +inf` and `all above range_max`, both now
`False / 8.000` — and four rows were added, of which `inf sector, obstacle 0.8`
returning `True / 0.800` is the one that proves an open horizon does not blind
the detector. `all samples NaN`, `all samples -inf`, `all below range_min`,
`empty ranges`, both unusable windows and `publisher stopped 3 s` are still
`True / 0.000`. The transcript in `EVIDENCE_MODEL.md` §6.1 was re-generated from
the file as committed and diffed against the document: identical, 22 lines.

Two headless Gazebo runs on the minimal world of §0 then put the same question
to a rendered scan, and each captured message was evaluated under **both** the
rule as committed at `ce7153b` and the new one:

- facing open space — `0 DISTANCE, 61 CLEAR, 0 INVALID`; old rule `True / 0.000`
  (`no valid sample in sector`), new rule `False / 8.000`. That is the teleop
  false stop reproduced and removed on one real message.
- facing the wall — `51 DISTANCE, 10 CLEAR, 0 INVALID`; both rules `False / 3.180`,
  the same wall range §5 measured, so the distance path is untouched.

`EVIDENCE_MODEL.md` is append-only for this change: 179 lines added, **0
removed**; the 06:15–07:05 transcript stands as run.

Isolation: `GZ_PARTITION=m4f02c`, `ROS_DOMAIN_ID=71`, my own gz server, headless.
Nothing was published into, and no pid was signalled outside, this run; the
unrelated stack live on another partition and domain was verified intact
afterwards. Cleanup matched pids by their `GZ_PARTITION` in `/proc/<pid>/environ`
rather than by command-line pattern.

## Requested outside agv/ — five locations, none edited here

The old semantics were quoted verbatim in other layers' documents. Swept by
subject, not by remembered phrasing:

| Where | What is now wrong | Owner |
|---|---|---|
| `docs/interfaces/opcua-nodes.md` §10.5, the `ForkliftObstacleInStopZone` row and the polarity note under it | "the vehicle layer publishes `TRUE` whenever the scan is **invalid, non-finite or stale**" — a non-finite `+inf` now publishes `FALSE` | interface |
| `docs/interfaces/bridge-design.md` §, mapping row 12 | same phrase, "`TRUE` = object in the field, or the scan is invalid, non-finite or stale" | interface |
| `plc/forklift/SPEC.md` §5 note and the §13 watch-table row for `ForkliftObstacleInStopZone` | same phrase, twice | plc |
| `sim/README.md`, "**An empty forward sector is a no-data condition, not a clear path**" | The paragraph is now false, and the workaround it justifies — never push the crate further than the scanner can see it — is no longer needed | sim |
| `sim/scenarios/forklift_commissioning.md` §, the arithmetic rule for clearing the zone | Same workaround. The `MEASURED` line later in that file is an as-run record of the old behaviour and should stay | sim |

Not affected, checked rather than assumed: `run_forklift_rehearsal.py` S4.10 kills
the scan bridge at the source, which still yields `scan stale` and `0.0`;
`plc/forklift/SPEC.md`'s `0.10 … 8.00 with a usable scan` row already admits the
new `8.00`; `model.sdf`, `config.yaml` and `launch/vehicle.launch.py` carry no
statement that depends on the validity rule.

## Open questions

1. **A below-`range_min` return is skipped, not treated as an obstacle.** `-inf`
   and anything under `range_min` are `INVALID`, and an `INVALID` sample is
   ignored whenever some other sample in the sector is valid — pre-existing
   behaviour, unchanged here, but newly reachable: `inf sector, one below min`
   returns `False / 8.000`. On a scanner that reports too-close that way, that
   ray is the most non-permissive thing the sensor can say. Worth checking the
   ROS `LaserScan` out-of-range convention (REP 117, not read offline during this
   run) and deciding whether below-min should instead read as an obstacle at
   `range_min`. Owner call; not implemented, because the brief pins below-min as
   invalid.
2. **`min_distance`'s clear value couples two documents.** It is the scan's
   `range_max`, so `model.sdf`'s `<range><max>` (8.00) must stay inside the
   consumer's plausibility window (0.05 … 8.10). Raising the scanner past 8.10
   without moving the window would make a clear horizon read at the PLC as a
   transducer fault — the same class of mistake as this one, one layer along.
   Nothing enforces the relation today; it is written into the node, the README
   and the evidence, and no code checks it.
3. **The brief cites §10.4 for that plausibility window; it is §10.5.** §10.4 is
   `Forklift/Hmi/`. The substance is unaffected — 8.00 is inside 0.05 … 8.10 —
   but the citation in the brief and in any document derived from it is off by
   one section.
4. **The running vehicle node predates this change.** The `obstacle_zone.py`
   process live at the time of writing loaded the old file at start; it has to be
   restarted to pick the fix up. Nothing in this change touched it.
