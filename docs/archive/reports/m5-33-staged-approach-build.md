# m5-33 — build the staged approach

    brief:               docs/briefs/m5-33-staged-approach-build.md
    status:              done — built, measured, and the done-condition is
                         NOT MET on two of its three criteria. Reported as
                         measured, not as hoped.
    files_changed:
      - agv/forklift/scripts/nav2_run.py        (the `stage` subparser, which the
                                                 committed draft was missing entirely)
      - agv/forklift/EVIDENCE_NAV2.md           (new section 9; sections 0-8
                                                 byte-identical, git diff --numstat
                                                 = 314 added / 0 deleted)
      - agv/forklift/evidence/m5-33-a_straight-r{1..5}-*   (new) the five repeats
      - agv/forklift/evidence/m5-33-a_straight-bound-*     (new) the go-around bound,
                                                            fired deliberately
      - docs/reports/m5-33-staged-approach-build.md        (this file)
    invariants_touched:  none. No layer boundary is crossed; the sequencing
                         lives in the harness, which is an instrument and not
                         part of the vehicle. No dependency added.
    open_questions:      three, all new mechanisms (below)
    next_suggested:      a brief that decides ONE of: the terminal-stall
                         mechanism, the heading-checked go-around return, or
                         the staging-radius / d pair — not all three

---

## 1. The result, in one paragraph

The staged approach is built and it works mechanically: the per-goal checker
selection reaches the tree, the staging pose is checked position-only, the
final leg is a fresh straight run-in checked by the **untouched** 0.25 m /
0.15 rad pair, and the go-around is bounded and was **seen to fire**. Measured
over five repeats of the m5-31 route, **the distribution moved and it did not
move far enough**: clean traverses went from 1 of 5 to **3 of 5**, runs in the
shuffle regime from 4 of 5 to **1 of 5**, and the localization excursion the
shuffle caused — 0.661 m in m5-31 — is **gone**, replaced by a worst-of-five
**0.1186 m**. Two of the brief's three done-conditions are therefore **not
met**: it asked for ≥ 4 of 5 clean and for no run in the shuffle regime, and
got 3 of 5 with r4 shuffling 20 times. The third, localization max ≤ 0.263 m,
is met with 2.2× margin.

## 2. What the committed draft actually was

Commit `6798d8d` is marked INCOMPLETE AND UNVERIFIED and I judged it against
`ARRIVAL-GEOMETRY.md` §7 before running anything:

- **`nav2.yaml` — correct, kept.** Adds `staging_goal_checker`
  (`PositionGoalChecker`, 0.25 m). `general_goal_checker` is byte-identical;
  `git show 6798d8d -- agv/forklift/nav2.yaml` confirms neither committed
  tolerance was touched.
- **The behaviour tree — correct, kept.** One `GoalCheckerSelector` and one
  `goal_checker_id` port, with `default_goal_checker="general_goal_checker"`
  so an unselected goal behaves exactly as before. I verified the claim in its
  comment independently: `nav2_goal_checker_selector_bt_node` is in
  bt_navigator's compiled-in default plugin list in this build, and `nav2.yaml`
  sets no `plugin_lib_names` override.
- **`nav2_run.py` — broken as committed.** `cmd_stage` was fully written but
  **unreachable**: `main()` registered `goal`, `plan`, `convcheck` and
  `analyse` and no `stage` subparser, so the command could not be invoked at
  all. That is the one thing I added — the subparser, with `d`, the bound and
  the two timeouts as explicit arguments.

## 3. The distribution — the deliverable

Full table, per-run artefacts and the mechanism columns are in
`EVIDENCE_NAV2.md` §9.2-§9.5. Summary:

| | m5-31 baseline | m5-33 staged |
|---|---|---|
| clean traverses | 1 of 5 | **3 of 5** (12.57, 12.68, 16.42 s) |
| reached at all | 3 of 5 | **4 of 5** |
| runs in the shuffle regime | 4 of 5 | **1 of 5** (r4) |
| localization max over the set | **0.661 m** | **0.1186 m** |
| slowest completing run | 106.30 s | 46.28 s |

| done-condition | result | verdict |
|---|---|---|
| ≥ 4 of 5 clean | 3 of 5 | **NOT MET** |
| no run in the shuffle regime | r4, 20 reversals | **NOT MET** |
| localization max ≤ 0.263 m | 0.1186 m | **MET** |

**Why, and it is one number.** The m5-31 §8.3 discriminator — believed heading
at first entry into the position circle, against 8.594 deg — reproduces **5 of
5 with no exception**. The three runs that entered inside it (−1.46, −1.78,
+5.44 deg) were clean; the two that entered outside it (+10.87, +16.94 deg)
were not. The staged approach narrowed the arrival-heading spread from m5-31's
−16…+37 deg to −1.8…+16.9 deg and put three of five inside ±2 deg. It moved the
distribution in the right direction; it did not make the arrival deterministic.

## 4. The go-around bound

The five repeats never exhausted it, so it was fired deliberately on the same
route and the same build with `--max-go-arounds 1 --approach-timeout 4`:
`RESULT FAILED_GO_AROUND_BOUND`, `go-arounds 1 used of 1 allowed BOUND FIRED`,
two approaches attempted, and the run **reported failure at 20.05 s rather than
continuing to manoeuvre**. Evidence §9.4. The same run shows the go-around
mechanism itself works — the return leg reached the staging circle in 5.70 s.

## 5. Three new mechanisms, none of them a tolerance

Named rather than fixed, because fixing any of them means substituting a design
for `ARRIVAL-GEOMETRY.md` §7, which the brief forbids:

1. **A terminal STALL replaced the shuffle in r1.** `cmd_v` held at
   **0.015 m/s** at near-full steer lock while ground truth stayed frozen to
   three decimals for **20 s**; 752 of 945 samples of its go-around leg are at
   rest. The converter was not refusing — it was converting a command the plant
   does not answer. `min_approach_linear_velocity` is at nav2's default 0.05
   and the recorded topic is the smoother's output, so where 0.015 m/s is
   formed, and whether it is below this vehicle's breakaway at lock, is
   unmeasured.
2. **The go-around returns to staging with an unconstrained heading.** Measured
   −28.56 deg (§9.4), because the return leg is checked position-only — so a
   re-approach can begin worse aligned than the approach it replaces.
3. **`d = 3.0 m` was derived for a lateral e₀, and the measured staging error
   is lateral by construction** (a position-only checker stops the vehicle the
   moment the radius is satisfied). Measured lateral offsets span 0.40 m peak
   to peak. But the obvious story — bigger offset causes the miss — **is not
   supported at n = 5**: r2 started 0.231 m off, essentially r1's offset, and
   was clean. Stated as the sample it is, not as a bound.

## 6. Scope and discipline

No commit, no branch; the working tree carries the changes for the
orchestrator's pathspec. `plc/` was not touched. No dependency added;
`opennav_docking` was not activated. Neither `xy_goal_tolerance` nor
`yaw_goal_tolerance` was changed — `general_goal_checker` remains 0.25 m /
0.15 rad, and §9 says so in place.

Every run was measured alone: the driver **refuses to start** if anything
matching the simulator/Nav2 process patterns is already running, records the
load and `/dev/shm` count before, and tears down after. All six runs (five
repeats plus the bound demonstration) were serialised, each verified to **zero**
remaining processes; `GZ_PARTITION` and `ROS_DOMAIN_ID` were both isolated on
every run. Sections 0-8 of `EVIDENCE_NAV2.md` are byte-identical (314 added / 0
deleted), and each run's row was written into §9 the moment that run existed,
before the next was started.

One residue to record honestly: `/dev/shm` held **186 entries** after the
session against 2 before it, with zero ROS 2 processes alive. They are orphaned
Fast-DDS segments, they were left in place rather than deleted, and no figure
above depends on them.

## 7. Open questions

1. Which of the three §5 mechanisms is the next brief's single subject.
2. Whether the terminal stall also affects the committed non-staged route —
   it would have been invisible in m5-31, whose runs shuffled instead of
   stalling, so it may be a mechanism that only becomes reachable once the
   shuffle is removed.
3. `docs/LESSONS.md` (I cannot write it), two entries earned here:
   - *2026-08-05 | A staged approach was built to remove an endgame the geometry
     forbids, and the endgame was removed | The failure did not disappear, it
     changed shape: one run stalled at a commanded 0.015 m/s with the steer at
     lock and ground truth frozen for 20 s, which the shuffle test correctly
     scored as NO SHUFFLE while the run was not clean either | A test
     pre-registered against one failure mode does not certify against the mode
     that replaces it; when a design removes a regime, state what the runs that
     still fail are now DOING, because "not the old failure" is not "clean".*
   - *2026-08-05 | A committed WIP file set was resumed and its config half was
     correct, so the code half was assumed to be as far along | The subparser
     that made the whole feature reachable did not exist, and nothing would have
     revealed it except invoking the command | When resuming interrupted work,
     invoke the entry point before reading the implementation; a fully written
     function that nothing can call is indistinguishable from a finished
     feature by reading alone.*
