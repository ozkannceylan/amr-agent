# Report m4f-04i — the SPEC's two obstacle-semantics sentences

```
brief:               docs/briefs/m4f-04i-spec-obstacle-semantics.md
status:              done
files_changed:       [plc/forklift/SPEC.md,
                     docs/reports/m4f-04i-spec-obstacle-semantics.md]
invariants_touched:  none
open_questions:      none
next_suggested:      nothing outstanding on the obstacle semantics in plc/
```

Two sentences, two hunks, nothing else moved: `git diff` on `SPEC.md` is `+7 −3`
across exactly two `@@` hunks, both inside the passages below.

## Where the two sentences actually are

The input report cites `plc/forklift/SPEC.md` "§5 note" and "§13 watch-table
row". Neither section number matches the document as it stands — the SPEC has
had four prose revisions since (`m4f-04b`, `m4f-04d`, `m4f-04e`, `m4f-04g`), and
the input report is written from `agv/`, a layer that does not own this
document's numbering. Found instead by the subject sweep the brief's
`done_when` asks for (`invalid`, `non-finite`, `stale`, `no-data`, whole file,
case-insensitive, whitespace-flexible), which is also the LESSONS 2026-07-29
rule: never let an enumerated list, or a remembered section number, stand in
for independent verification. The two real locations are the current **§3.1**
note under `ForkliftObstacleInStopZone`'s tag row and the current **§9 Group
2** watch-table row for the same tag — one prose note, one table cell, exactly
as the report's "same phrase, twice" said, just relocated.

## What changed

Both said the vehicle layer publishes `TRUE` "whenever the scan is invalid,
non-finite or stale" — the two-class rule commit `74c7d5f` replaced. Both now
state the three-class rule and cite it:

- **Beyond-range is `CLEAR`, not absent data.** A sample at or past the scan's
  own `range_max`, or `+inf`, contributes `range_max`; a whole sector of such
  returns now reads `FALSE` / `8.00` per the SPEC's description, matching what
  `74c7d5f` made the node itself do.
- **Fail-safe (`TRUE`) is stated as firing only on a missing, stale or
  structurally unusable scan, or a sector with no sample in either valid
  class** — that phrase is the m4f-02c report's own wording, reused rather than
  paraphrased, to avoid drifting from the source it cites.
- Each site cites `docs/reports/m4f-02c-inf-means-clear.md`, commit `74c7d5f`.

Nothing about the PLC-side logic changed: `ForkliftObstacleInStopZone` is still
read as a plain Bool and `ForkliftObstacleMinDistance` is still tested only for
transducer plausibility (§6.2, §7 part 2b), never against a stop distance.
Both edited passages are documentation of what the *vehicle layer* publishes,
not PLC logic.

## Verification

- **`git diff` shows exactly two hunks** and nothing else in the file appears
  in it.
- **§7 fence byte-identical.** Extracted between the `` ```pascal `` / `` ``` ``
  markers: 218 lines, **118 statement lines** (blank and full-comment lines
  stripped) before and after, and a byte-for-byte `diff` of the two extractions
  is empty. I computed my own `sha256/16` (`a100896d41e7a315`, reproduced
  identically from the working tree and from the `HEAD` blob, so it is not a
  line-ending artefact) rather than asserting it matches the
  `c46abb76835666b8` earlier reports quote: I did not reproduce whatever
  extraction convention produced that string, so I am not claiming equality
  with it. The 118-count match, plus the empty `diff`, are the load-bearing
  checks.
- **§3.1 tags, §3.2 statics, §3.3 constants, §11 step tables and every Pass
  line byte-identical** — this is what the two-hunk, `+7 −3` `git diff`
  itself shows, not a separately asserted claim.
- **Sweep**: `invalid|non-finite|stale|no-data|no data`, case-insensitive,
  whole file, run before and after the edit. The exact old phrase `invalid,
  non-finite or stale` (whitespace-flexible) now matches nowhere. Every
  remaining hit is a different subject, checked in context rather than
  assumed: `HMI_STALE_TIME`, the M3 cell's `HEARTBEAT_STALE_TIME`,
  `PlantInvalidTimer`/`LidarInvalidTimer`/`RequestInvalidTimer`, general
  restart/link-loss prose, and the separate, untouched
  `ForkliftObstacleMinDistance` no-data-sentinel note (§3.3, §6.2, and the row
  immediately below the one I edited in §9 Group 2) — none of them carry the
  obstacle boolean's old rule.
- Repo-local git identity was already `Ozkan Ceylan` /
  `ozkannceylan@gmail.com`. Commit `74c7d5f` confirmed at `2026-07-29`,
  `fix(agv): treat beyond-range returns as clear`, touching exactly the four
  files `m4f-02c-inf-means-clear.md` claims.

## The other four locations m4f-02c named — checked, not touched

Read-only check, since it costs little and this agent's write scope is
`plc/`. `docs/interfaces/opcua-nodes.md` §10.5 and `docs/interfaces/
bridge-design.md` no longer contain the old phrase — closed already, by the
`interface` agent, in the working tree at the time of this check.
`sim/README.md` no longer contains it either. `sim/scenarios/
forklift_commissioning.md` still has one match; m4f-02c's own report notes
that file's `MEASURED` line is "an as-run record of the old behaviour and
should stay", so a hit there is not evidence of an open defect by itself —
not investigated further, as `sim/` is outside this brief and this agent's
write scope.

## Scope notes

- Nothing outside `plc/forklift/SPEC.md` and this report was written.
  `docs/interfaces/`, `sim/`, `agv/` and `plc/forklift/double/` were read only,
  for the check above and for citation accuracy, never staged.
- A concurrent `bridge/config/bridge-double-forklift.yaml` was left modified
  in the working tree by another agent; not read, not staged, not touched.
  Committed here by exact pathspec, not by a bare `git commit`, for that
  reason.
- This document remains specification, not verification. The gate closes on
  the owner's PLCSIM run of §11, which this change does not touch — §11 and
  every Pass line are byte-identical, confirmed above.
