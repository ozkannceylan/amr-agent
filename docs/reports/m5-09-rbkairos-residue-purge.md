# Report m5-09 — purge the retired vehicle platform's residue

```
brief:               docs/briefs/m5-09-rbkairos-residue-purge.md
status:              done
files_changed:       assets/CREDITS.md
                     docs/PLAN.md
                     docs/TODO.md
                     docs/interfaces/bridge-design.md
                     sim/README.md
                     sim/scenarios/DEFERRED.md
                     sim/scenarios/config/nav2_params.yaml   (DELETED)
                     sim/scenarios/nav_scenario.launch.py
                     sim/scenarios/run_scenario.py
                     sim/setup/CONTAINER_TOOLCHAIN.md
                     sim/setup/WSL_ENVIRONMENT.md
                     sim/setup/install.sh
invariants_touched:  none
open_questions:      5, below
next_suggested:      Rule on the CREDITS options and on the three parked
                     files m5-09 could not rule on (OQ1, OQ2), then open
                     m5-10 with an empty Nav2 config as its stated premise.
```

## Method

Swept by subject, not by phrasing. A script walked every tracked file
(`git ls-files`, 544 files), normalised all whitespace to single spaces so a
name wrapping across a line break still matches (LESSONS 2026-07-27,
2026-07-29), and matched case-insensitively on `rb[\s_-]*kairos`, `robotnik`,
`kairos`, `summit`, `robot_base_footprint`, `front_laser`, `rear_laser`,
`robotnik_base_control`, `omni[\s_-]*motion`, plus filename matches and a
separate pass for `/robot/`, `robot_odom`, `rbkairos` and `mecanum`.

The brief's list was treated as a starting point. The independent sweep found
**48 files**, of which the brief named 5. Each hit was read in its surrounding
sentence for dependency, not just for the string.

The rule applied to every hit:

- **Remove** a mention that presents the platform as current — an install
  step, a run procedure, a topic/frame/controller name asserted as this
  project's interface, a config value, a package list.
- **Keep** a mention that states the platform is retired, or that names a
  parked artifact as belonging to it — the name as the object of a
  retirement statement, not as a live fact.

## Removals, each against ADR 0010 D1

**`sim/scenarios/config/nav2_params.yaml` — deleted.** Entirely shaped by the
retired vehicle: `OmniMotionModel`, its scan/odometry/command topics, its
frame tree, its footprint. The owner ruled it is not a migration candidate.
**This deletion is not a gap.** The forklift's Nav2 configuration is written
from scratch at **m5-10** (tricycle kinematics, one navigation lidar, its own
frame tree, SmacPlannerHybrid/RPP with Spin/BackUp removed) — nothing was lost
that m5-10 would have started from. Stated in that form in `DEFERRED.md`,
`sim/README.md`, `docs/PLAN.md` and here, so it cannot be read as a gap.

**`sim/setup/install.sh` — the opt-in path removed whole.** m5-07 had put
steps 4-6 behind `ROBOTNIK=1`, default off. A retired platform does not get an
installation path: the flag was *executable* content that cloned five vendor
repositories and installed closed-source controller debs for a vehicle this
project does not have. Removed whole, as the brief required: the three steps,
the `ROBOTNIK` and `ROBOTNIK_WS` variables, the `ROBOTNIK_PKGS` list (five
`ros2_control` packages, absent from the verified container), the opt-in
branch and its log lines, and the final "source the workspace" instruction.
Verified: `bash -n` passes, no residue string remains, `i/lf w/lf
attr/text eol=lf`, ASCII-clean.

**`sim/README.md` — 45 hits to 1.** Removed setup steps 4 and 5 (the vendor
clone and the controller debs), the "Running the bringup" procedure, "Design
choice: vendor spawn path with ros2_control", "Expected evidence after
bringup" (a topic list asserted as this project's), the three-terminal
navigation run procedure, and "Nav2 configuration notes" (which documented the
deleted file and asserted the retired frame tree). Replaced by one section,
**"The parked warehouse navigation scenario"**, that states the retirement and
tables what remains and why. The single surviving hit is my own prose
describing what the deleted config *was* ("omni motion model").

**`sim/scenarios/DEFERRED.md` — rewritten** to describe a parked *scenario*
rather than a vehicle: what m5-09 removed, what that means for the two
remaining code files, and that `maps/` + `tools/make_map.py` are
vehicle-independent (rasterized from world geometry, so they survive the
platform change).

**Prose elsewhere:** `docs/PLAN.md` item 10 no longer points at the deleted
file; `docs/TODO.md`'s M5-carried item no longer frames the work as a
"platform migration off RB-KAIROS" (after this brief there is no platform to
migrate off).

## Dependency fixes — references my own deletions broke

These are the "fix the reference" cases the brief's `forbidden` list names.
None were in the brief's location list; all were found by reading hits for
dependency.

| File | The dependency |
|---|---|
| `sim/scenarios/nav_scenario.launch.py` | `_DEFAULT_PARAMS` pointed at the deleted file. `params_file` is now a **required** argument with no default, documented as such. |
| `sim/scenarios/run_scenario.py` | its generated evidence template named the deleted file as the params source; now names the launch argument. |
| `sim/setup/CONTAINER_TOOLCHAIN.md` §5.2, §5.3 | a dated record of what `install.sh` said. Not rewritten — a dated **superseding note** was appended to each item, because the record of the 2026-07-30 verification stays true and only its "now says" claim died. |
| `sim/setup/WSL_ENVIRONMENT.md` §3.1 | cited `install.sh` §4-§6, sections that no longer exist. |
| `sim/setup/WSL_ENVIRONMENT.md` §finding 1 | claimed "`install.sh` already places the Robotnik workspace at `/opt/m3-feasibility/ws`". The finding (never build on `/mnt/c`) stands; only its supporting sentence died. |
| `docs/interfaces/bridge-design.md` item 15 | quoted `sim/README.md`'s heading verbatim as "the text now in force". I changed that heading, so the quote was updated. |
| `docs/TODO.md` sim item | line pointers `sim/README.md:50` / `DEFERRED.md:28` drifted to `:51` / `:51`. |

One incidental correction, disclosed: `sim/README.md` step 3's package list
had also been missing `ros-jazzy-slam-toolbox` since m5-07. I was editing that
exact code block to remove the five `ros2_control` packages, and leaving a
known-wrong list beside a fresh edit is the half-fix LESSONS 2026-07-27 warns
about, so it was added in the same block.

## Kept hits, each with its reason

**Historical record — never edited (brief `forbidden`), 27 files:** all of
`docs/adr/**` (including ADR 0002, which is superseded by ADR 0010 D1, not
deleted or amended), `docs/briefs/**`, `docs/reports/**`, `docs/LESSONS.md`.
Not touched, not counted below.

| Hit | Reason kept |
|---|---|
| `docs/roadmap.md:19` | *is* the retirement statement ("RB-KAIROS is retired and the in-house forklift is the vehicle platform from M5 onward"). Removing the name would remove the record of the decision. |
| `docs/safety/SRS.md:45` | §1.3 "Arm safety — out of scope": names the platform as the thing that brought an arm into the model and states it is retired. A retirement statement. |
| `assets/rb-kairos-gazebo.png` and the BSD-3-Clause block in `assets/CREDITS.md` | attribution artifact; owner has not ruled. Options below. |
| `docs/interfaces/vda5050-subset.md:261-262` | `typeSpecification.seriesName` is still defined as RB-KAIROS per ADR 0002. This is **live contract content and genuinely stale**, but redefining it means choosing the forklift's series name and `agvKinematic` — an interface contract decision, not plumbing, and infra does not take those. The owner has already routed it: `docs/TODO.md` interface section carries it as M6 briefing work, "a field-value change, not a renumber" (m5r-08 OQ1). Left for that brief. |
| `docs/TODO.md:143` | the tracker for the row above. Correctly framed as open work. |
| `docs/interfaces/bridge-design.md:869` (item 8) | narrative of how a heading was corrected, citing ADR 0010's retirement. A record of a decision. |
| `sim/setup/CONTAINER_TOOLCHAIN.md:319` | the dated record of what `install.sh` said on 2026-07-30, now carrying a superseding note. Evidence, not instruction. |
| `sim/scenarios/nav_scenario.launch.py:56`, `sim/scenarios/run_scenario.py:81` | the retired command and odometry topics, in the parked scenario's two remaining code files. The owner ruled on the Nav2 config only; changing these means deciding the forklift's topics, which is m5-10's. Both files now carry headers saying the values are retired-platform record, not this project's interface, and neither can run. Raised as OQ1. |
| `sim/launch/warehouse_bringup.launch.py` (16), `sim/worlds/BRINGUP_EVIDENCE.md` (17), `sim/worlds/warehouse.sdf:22` | **not touched — a concurrent agent held `sim/launch/` and `sim/worlds/` for the whole of this brief** (their edits to the three `.sdf` files are in the tree). This is real residue, not a judgement call. Raised as OQ2 and queued in `docs/TODO.md`. |

`/opt/m3-feasibility/ws` is outside the repository. After this brief **no
tracked file creates or sources it**; `sim/README.md` and `install.sh` were
its only creators. `sim/setup/WSL_ENVIRONMENT.md` still names it once, inside
a parenthetical recording that it *used to be* provisioned there. Not chased
further, per the brief.

## The CREDITS ruling — both options, prepared

`assets/rb-kairos-gazebo.png` is referenced by **no live document** — not the
public README, not `sim/`, only `assets/CREDITS.md` itself and the `TODO.md`
line tracking this very question. Removal is therefore self-contained.

**Applied now (the note option, as the brief instructs):** one line on the
table row, marking the image "**No longer used — the platform was retired by
ADR 0010 D1**" and "Retained as an attribution artifact pending the owner's
ruling". The reproduced BSD-3-Clause licence text was **not touched**. The
`CREDITS.md` closing paragraph already carried a retirement sentence.

**Option A — keep (currently in force).** Leave image, credit, source-commit
table and licence block; the row now says it is unused. *For:* the credit was
given because the project once used that work, and a licence notice withdrawn
after the fact is a worse look than an unused asset. Honest about history.
*Against:* one orphan binary and ~45 lines of third-party licence text in a
portfolio repository that no longer uses either.

**Option B — remove image and notice together.** Delete
`assets/rb-kairos-gazebo.png`, the table row, the `## rb-kairos-gazebo.png`
section (source-commit table + BSD-3-Clause block) and the closing paragraph;
delete the `docs/TODO.md` residue line. *For:* nothing remains that the
attribution attaches to, so the notice has nothing to notice; the assets
directory then contains only this project's own captures. *Against:*
irreversible in the working tree (recoverable from history); the BSD-3-Clause
obligation applies to redistribution, and once the image is gone there is no
redistribution — so removing both together is licence-clean, but removing the
notice **without** the image would not be.

Both are one edit. **Do not do half of B.** The image and the notice are one
unit: the notice exists because the image redistributes the vendor's mesh and
material assets.

## Open questions

1. **The parked scenario's two remaining code files.** The owner's reasoning
   for deleting `nav2_params.yaml` — "not a migration candidate, m5-10 writes
   it from scratch" — applies verbatim to `nav_scenario.launch.py` (NavFn/DWB/
   spin-backup node set, which m5-10 explicitly replaces) and to
   `run_scenario.py`'s odometry subscription. m5-09 did **not** extend the
   ruling: the brief named one file. Neither can run. Recommend deciding
   keep-or-delete at m5-10 briefing; queued in `docs/TODO.md`.
2. **`sim/launch/warehouse_bringup.launch.py` and
   `sim/worlds/BRINGUP_EVIDENCE.md`** are the retired vehicle's bringup and
   its evidence, and are the largest remaining concentration of residue (33
   hits). A concurrent agent held both directories, so m5-09 could not touch
   them. This needs one follow-up brief. Queued in `docs/TODO.md`.
3. **`vda5050-subset.md`'s `seriesName`** is live contract content still
   naming the retired platform. Deliberately left to the M6 interface brief
   the owner already scheduled — but it means the done_when's "only
   deliberately kept hits" includes one hit that is stale rather than
   historical. Flagging so the verifier does not read it as an oversight.
4. **Brief-ID collision.** `docs/PLAN.md` item 9 lists "m5-09 agv — AMCL
   against the frozen map", while this brief is also `m5-09`. Two different
   deliverables share an id. Not fixed here (it is a plan decision); worth
   renumbering before the verifier reads PLAN against the report directory.
5. **A pre-existing TODO item was left open on purpose.** `sim/README.md`
   still lists `EVIDENCE_NAV.md` without "(generated by the first run)"
   (m5r-07 OQ6). It is a separate tracked item and bundling it would have
   broken one-brief-one-deliverable; its line pointers were refreshed instead.

## Verification

Re-ran the identical whitespace-normalised sweep after the edits. Excluding
the historical record, every remaining hit is in the kept table above.
`bash -n sim/setup/install.sh` passes; `python3 -m py_compile` passes on both
edited Python files; `git ls-files --eol` confirms `i/lf w/lf` with
`eol=lf` on all three executable files; the edited shell and Python files are
ASCII-clean.

Nothing is staged. The deletion is left as an unstaged ` D` in the working
tree so that a concurrent agent's index is not disturbed (LESSONS 2026-07-27:
under concurrency the orchestrator commits by pathspec). The three modified
`sim/worlds/*.sdf` files in `git status` are the concurrent agent's, not mine.
