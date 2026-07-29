# Report m5a-08 — the marked safety zone and the T6 scenario

```
brief:               docs/briefs/m5a-08-arena-zone-and-t6.md
status:              done
files_changed:       sim/worlds/forklift_arena.sdf (+57 lines, 0 removed)
                     sim/scenarios/forklift_commissioning.md (+248 lines, 0 removed)
                     docs/reports/m5a-08-arena-zone-and-t6.md (this file)
invariants_touched:  none
```

## What it is

`sim/worlds/forklift_arena.sdf` gains one new static, visual-only model,
`SafetyZoneMarking` — a 3.00 x 3.00 painted outline on open floor centred at
`(x=-2.00, y=0.00)`, same technique as the existing `AisleMarking` /
`PalletZoneMarking` (four edge strips, no collision, 6 mm proud of the floor,
plain box + material, no mesh/texture/shadow). It sits on the drive aisle,
reachable from the spawn pose after ~2.5 m of straight travel and 2.05 m clear
of `AisleCrate`'s near face, so the zone-crossing scenario never interacts
with the M4 obstacle scenario. The `<physics>` block and every pre-existing
`<model>` element are byte-identical (`git diff --numstat`: 57 insertions, 0
deletions).

`sim/scenarios/forklift_commissioning.md` gains a new `## 12. T6 (M5, early)`
section; sections 1–11 are byte-identical (248 insertions, 0 deletions). It
opens with the fallback sentence, states which of the 26
`plc/forklift-safety/SPEC.md` §9.1 steps need only PLCSIM + the two TIA watch
tables (18 of 26) versus the full M4 stack (8), ties the zone-trip steps to
the new marking's exact geometry, mirrors all 26 steps in a
Step/Needs/Stimulus/Observable/AT table, and closes with a recording
checklist carrying the `docs/safety/TWIN-DEMO-MAP.md` §5.1/§5.3 wording
discipline (the stand-in sentence, the say/never-say table), the
outstanding-sub-case table (R5), and the non-claims recap.

## Validation performed

- The arena change was loaded in headless `gz sim` (Gazebo Harmonic) inside
  WSL2 Ubuntu, isolated on `GZ_PARTITION=m5a08valid` — a partition confirmed
  free by `pgrep`/`/proc/<pid>/environ` before use. `gz model --list` returned
  all 13 arena models including `SafetyZoneMarking` in the expected position;
  the log carried 0 `ERROR` and 0 `WARN` lines. The validation process was
  terminated afterward by its own pid; a second, unrelated `gz sim` process
  already running under a different partition (another agent's session) was
  identified by the same environment filter and left untouched.
- Both files were re-checked after every edit: `git ls-files --eol` reads
  `i/lf w/lf` with 0 CR bytes on both; the step table has exactly 26
  well-formed rows (`awk -F'|'` field-count check); backtick and `**` counts
  are even (balanced) across the new section.
- `git diff --numstat` on both files shows insertions only, 0 deletions,
  satisfying "no rehearsal transcript or existing figure changes."

## Corrections made against live concurrent state

Two claims in an early draft were caught and corrected against the actual
current repository content rather than the brief's inputs list, because
concurrent work had moved past what `plc/forklift-safety/SPEC.md` itself
could know when it was written:

1. The mirror node group is **not** an open interface decision. It was
   resolved while this brief was in progress: `docs/interfaces/opcua-nodes.md`
   §11 (report `m5a-06`, status done) fixes it as
   `Forklift/Safety/{EStopDemand,ZoneStopDemand,SafetyResetRequired,SafetyResetFault}`
   on the `DemoCell` interface. The section now cites that resolution directly
   and states correctly that `CauseGone` is deliberately not a node (§11.7).
2. The HMI safety banner and lamps (`docs/briefs/m5a-07-hmi-safety-lamps.md`)
   have **not** landed — verified by direct grep of the current
   `hmi/static/index.html` and `hmi/hmi_server.py` (zero matches for any of
   the four mirror names or a safety banner). The section states this
   precisely, names the brief, and is explicit that the existing HMI banner
   and lamps are the standard-program process signals and must not be read as
   a safety indication.

A third, more consequential gap surfaced from the same check: `plc/forklift/SPEC.md`
(the standard program) does not yet carry the F-side permissive term either —
`docs/briefs/m5a-05-teleop-permissive-delta.md` is not yet closed, confirmed
by grep (zero references to `EStopDemand`/`ZoneStopDemand` in that file).
Without it, every **std**-needs row of T6 would read as a false negative — no
reaction to any F-demand — even with the F-program itself in RUN and both
stand-in circuits proven open. The new section's precondition list states
this explicitly and names the brief, so the gap is not discovered mid-run.

## Interpretation of "forbidden: physics or model changes"

Read as "no change to the `<physics>` block and no change to any pre-existing
`<model>` element," not as "add no model at all" — the latter reading would
make the deliverable (a new floor marking, which `done_when` requires) 
impossible. The diff adds exactly one new `<model>`; nothing pre-existing
changed. Flagged here for the verifier to confirm the reading.

## Consequence noted, not fixed (outside this brief's two-file deliverable)

Adding `SafetyZoneMarking` changes what `gz model --list` reports: 12 arena
models becomes 13, and the evidence doc's "13 models listed" (12 arena + the
spawned vehicle) becomes 14. `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` lines 42
and 75 were captured before this marking existed and are not touched here —
restating a `gz model --list` figure without an owner-executed re-run would
itself be exactly the kind of unread tool-derived claim ADR 0006 forbids.

## Git

Per this agent's standing rule, the working tree is left as-is; nothing was
committed. Concurrent, unrelated changes are present in the tree from other
agents (`bridge/config/bridge-double-forklift.yaml`, four untracked
`hmi/evidence/*` files as of this writing) — a bare commit would sweep them
in. The exact pathspec-scoped command for the orchestrator:

```
git commit sim/worlds/forklift_arena.sdf sim/scenarios/forklift_commissioning.md docs/reports/m5a-08-arena-zone-and-t6.md -m "feat(sim): add the safety zone and the F-layer scenario"
```

Repo-local git identity is already `Ozkan Ceylan` / `ozkannceylan@gmail.com`
(checked, not changed).

```
open_questions:
  1. Whether "forbidden: physics or model changes" was correctly read as "no
     changes to the physics block or to pre-existing models" rather than "add
     no model at all" (the latter would make the deliverable impossible).
  2. sim/worlds/FORKLIFT_ARENA_EVIDENCE.md's model-list figures (12 arena /
     13 total) are now stale by one; not re-measured here, needs an
     owner-executed gz model --list against a real bringup, not a re-statement.
  3. sim/README.md's one-line descriptions of forklift_arena.sdf and
     forklift_commissioning.md do not yet mention the safety zone marking or
     the T6 section; not touched here, outside this brief's exact two-file
     deliverable.
  4. T6's std-needs rows (8 of 26) cannot show their specified reaction until
     docs/briefs/m5a-05-teleop-permissive-delta.md lands in
     plc/forklift/SPEC.md; the F-only rows (18 of 26) are unaffected and are
     already runnable once the F-program itself is in RUN.
  5. The HMI safety banner/lamps of docs/briefs/m5a-07-hmi-safety-lamps.md had
     not landed as of this writing; the new section names the gap and treats
     the TIA watch table as the sole F-side instrument until it does.

next_suggested: once m5a-05 and m5a-07 close, re-read this file's "instrument
gap" and precondition wording against their actual outcomes rather than
assuming it still matches — both were written against a live, moving state.
```
