# m5-33 — build the staged approach

    gate:                M5 (criterion (d))
    agent:               agv-ros2
    goal:                The vehicle arrives on a goal pose already aligned, by driving a straight final leg from a derived staging pose, and misses become a bounded go-around instead of an endless endgame correction.
    invariants_touched:  none
    inputs:
      - agv/forklift/ARRIVAL-GEOMETRY.md — **the authority, especially §7.** Build what it specifies
      - docs/reports/m5-32-arrival-geometry-research.md — the derivation and the survey behind it
      - docs/reports/m5-31-nav2-route-diagnosis.md — the failure distribution you must move
      - agv/forklift/nav2.yaml, behavior_trees/navigate_to_pose_tricycle.xml, launch/navigation.launch.py
      - agv/forklift/scripts/nav2_run.py — the harness
      - agv/forklift/EVIDENCE_NAV2.md §8 — how the five-repeat run was done; match it
      - docs/LESSONS.md
    deliverable:         the staged approach in agv/, and a dated section in agv/forklift/EVIDENCE_NAV2.md
    done_when:           A five-repeat run of the same straight route gives **at least 4 of 5 clean traverses**, with **no run entering the shuffle regime**, and localization max **≤ 0.263 m** across the set. Report the distribution, not a best run.
    forbidden:
      - widening `xy_goal_tolerance` or `yaw_goal_tolerance` — the owner ruled against it and the whole design exists to avoid it. The final checker keeps **0.25 m / 0.15 rad** untouched
      - adding a dependency — every mechanism Phase 1 needs is in the installed nav2 1.3.12
      - activating `opennav_docking` — that is Phase 3 and an owner decision at M6
      - building Phase 2's VDA 5050 deviation mapping — deferred to the M6 client brief
      - reporting a single clean run as success; the done-condition is distributional on purpose
      - editing committed sections of any EVIDENCE file; add a dated section
      - running while another agent holds the simulator — check, and say what you checked

---

## 1. What you are building

From `ARRIVAL-GEOMETRY.md` §7:

1. a **staging pose** 3.0 m back along the goal heading — the distance is
   **derived** (`2·√(R·e₀)` plus one lookahead) from committed numbers, so do not
   round it to taste;
2. a **fresh straight final leg** from staging to goal;
3. the **final checker unchanged** at 0.25 m / 0.15 rad — the point of the design
   is that the vehicle now *satisfies* the tight pair rather than the pair being
   relaxed to meet it;
4. a **bounded go-around** on a miss: return to staging and re-approach, a fixed
   number of times, then fail honestly.

The staging leg itself does not need the tight pair. `PositionGoalChecker`,
`GoalCheckerSelector` and per-goal `goal_checker_id` are all in the installed
nav2 1.3.12 — the research verified this against the installed package, not
against documentation. Use them.

## 2. Two things the research already settled — do not re-litigate them

- **Planning was never the problem.** The committed plan artifact terminates at
  exactly the goal heading. If your first instinct is to change the planner,
  that instinct is already falsified.
- **The controller has no terminal-heading authority.** Rotate-to-heading is
  mutually excluded with reversing in the installed binary. So terminal heading
  has to come from the route, which is what the staging pose is for.

## 3. Prove it the way the failure was proved

m5-31 measured **1 clean, 2 recovered, 2 timed out of 5**. That distribution is
the thing you are moving, and a single good run means nothing against it — that
is precisely the mistake that cost this project two sessions.

So: run the **same five repeats, the same way** §8 did, and report the same
shape. Include, per run, whether it entered the shuffle regime, and the
localization max. If the distribution does not move, say so plainly — a failed
attempt honestly reported is worth more than a tuned one.

## 4. Watch for two specific things

- **The go-around must be bounded and visible.** An unbounded retry is the same
  failure wearing a new name. Say what the bound is and show it firing.
- **The shuffle degrades localization to 0.661 m** (m5-31), 2.5× the figure
  `footprint_padding: 0.27` derives from. If the staged approach removes the
  shuffle, that exposure goes with it — check whether it did, and say so.

## 5. Working discipline

- **Write into the evidence as each run lands.** Create the dated section with
  its headings before your first run.
- **Measure alone**, and record when you ran.
- **Do not commit.** The orchestrator commits by pathspec.
- Read `docs/LESSONS.md` first. Two are yours: a bound from one instance is a
  sample, and a motion check that does not retrace its segments cannot tell a
  followed arc from a blocked one.
