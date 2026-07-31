# Brief m5-09 — purge the retired vehicle platform's residue

```
gate:                M5
agent:               infra (owner-approved 2026-07-30, cross-cutting)
goal:                nothing in the repository still carries the retired
                     RB-KAIROS / Robotnik platform as live content.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md D1
                      (the platform retirement),
                      docs/adr/0002-vehicle-platform.md (superseded, NEVER
                      edited), docs/TODO.md, assets/CREDITS.md,
                      sim/scenarios/config/nav2_params.yaml,
                      sim/scenarios/DEFERRED.md, sim/setup/install.sh]
deliverable:         the residue removed or re-labelled across the repository
done_when:           an independent whitespace-normalised sweep for the
                     platform's names — RB-KAIROS, RB KAIROS, rb_kairos,
                     rb-kairos, Robotnik, robotnik, ROBOTNIK, summit, and the
                     frame/topic prefixes those configs used
                     (robot_base_footprint, /robot/front_laser,
                     /robot/rear_laser, robotnik_base_control) — returns only
                     hits that are deliberately kept, each of which is listed
                     in the report with the reason; every removal is justified
                     in the report against ADR 0010 D1; and nothing that is
                     history by convention has been touched.
forbidden:           [editing docs/adr/** (an accepted ADR is never edited —
                      ADR 0002 stays as written and is superseded, not
                      amended), docs/briefs/**, docs/reports/**,
                      docs/LESSONS.md; deleting or altering assets/CREDITS.md's
                      third-party licence text without the ruling below;
                      removing a file that another live document still
                      references without also fixing that reference;
                      committing (the orchestrator commits)]
```

## What is residue and what is not

**Residue — remove or rewrite:**

- `sim/scenarios/config/nav2_params.yaml` is entirely platform-shaped:
  `nav2_amcl::OmniMotionModel`, `scan_topic: /robot/front_laser/scan` and
  `/robot/rear_laser/scan`, `robot_base_frame: robot_base_footprint`,
  `odom_topic: /robot/robotnik_base_control/odom`, NavFn planner. The owner has
  ruled it is **not a migration candidate**: the forklift's Nav2 configuration
  is written from scratch in a later brief (tricycle kinematics, one navigation
  lidar, its own frame tree). Delete it rather than leave a config that
  describes a vehicle this project does not have — and say in the report that
  the replacement is m5-10's, so nobody reads the deletion as a gap.
- `sim/scenarios/DEFERRED.md`'s platform narrative: the parked navigation work
  resumes on the forklift, so the document should describe what is parked
  (a scenario) without describing a vehicle that no longer exists.
- `sim/setup/install.sh`: m5-07 already put the Robotnik path behind
  `ROBOTNIK=1`, default off. Decide whether a retired platform deserves an
  opt-in path at all, and if you remove it, remove it whole — script,
  workspace reference, package list.
- Any other live prose that describes the vehicle gate as RB-KAIROS work.

**Not residue — leave alone:**

- `docs/adr/0002-vehicle-platform.md` and every other ADR, brief, report and
  the LESSONS file. These are the record of how the decision was made. ADR 0002
  is superseded by ADR 0010 D1; superseded is not deleted.
- The `/opt/m3-feasibility/ws` workspace is outside the repository. Mention it
  in the report if it is still referenced by tracked files, but do not chase
  it — this brief is about the repository.

## The one item the owner has not ruled

`assets/rb-kairos-gazebo.png` and its reproduced BSD-3-Clause notice in
`assets/CREDITS.md` illustrate nothing after ADR 0010 D1, but they are an
**attribution artifact**: removing them removes a credit that was given
because the project once used that work. Do **not** delete them. Instead
prepare both options in the report — a one-line "no longer used, retired by
ADR 0010 D1" note beside the existing credit, versus removal of image and
notice together — and leave the file as it stands with the note option applied
only if it can be done without touching the licence text itself. The owner
rules the rest.

## Method

Sweep by subject, not by remembered phrasing, and normalise whitespace before
matching — a name can wrap across a line break, and this repository has been
bitten by exactly that. Treat the list above as a starting point that you
verify by independent search, never as exhaustive. For each hit, read the
surrounding sentence for dependency: a statement whose *scope* rests on the
retired platform can be stale even when the platform's name has been removed
from it.

Do not commit. Leave files modified/deleted and write your report to
docs/reports/m5-09-rbkairos-residue-purge.md, listing every path touched, every
kept hit with its reason, and the CREDITS options.
