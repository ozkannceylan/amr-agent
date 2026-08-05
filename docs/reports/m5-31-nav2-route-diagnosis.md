# m5-31 — why the Nav2 route does not complete on the showcase machine

    brief:               docs/briefs/m5-31-nav2-route-diagnosis.md
    status:              done
    files_changed:
      - agv/forklift/EVIDENCE_NAV2.md                          (appended section 8; sections 0-7 byte-identical, git diff --numstat = 385 added / 0 deleted)
      - agv/forklift/evidence/m5-31-a_straight-r{1..5}-*       (new) five baseline runs, unchanged configuration
      - agv/forklift/evidence/m5-31-a_straight-e1_slowreplan-* (new) the replan-rate experiment
      - agv/forklift/evidence/m5-31-a_straight-e2_yaw060-*     (new) yaw tolerance, one line
      - agv/forklift/evidence/m5-31-a_straight-e3_yaw060b-*    (new) the same, repeated
      - agv/forklift/evidence/m5-31-a_straight-e4_xy045-*      (new) xy tolerance, one line
      - agv/forklift/evidence/m5-31-experiment-bt-slowreplan.xml (new) the tree e1 used
      - docs/reports/m5-31-nav2-route-diagnosis.md             (this file)
    invariants_touched:  none. Nothing measured here crosses a layer boundary; no
                         parameter, launch file, tree or node in agv/ was edited.
    open_questions:      five, and one correction to a committed open question (below)
    next_suggested:      a brief that decides what a "reached" goal means for a
                         non-holonomic vehicle — the tolerance pair, or an approach
                         corridor that controls the arrival heading

---

## 1. The finding, in one paragraph

**There is no regression and there is no platform defect.** The committed
13.40 s / 0.183 m result reproduces on WSL: run r2 gave **13.21 s and 0.156 m,
tracking three times tighter than the committed run**, with nothing changed.
What the five repeats show is that the route's outcome is a **draw** — 1 clean
traverse, 2 completions after 69-94 s of recovery, 2 timeouts at 120 s — and
that the container's own history said the same thing all along (4 attempts:
one 13.40 s success, one 240 s non-completion, at the same parameters). The
committed figure is one draw quoted as a result.

**The cause of every non-completion is named and demonstrated.** The goal
checker requires `xy_goal_tolerance 0.25 m` **and** `yaw_goal_tolerance
0.15 rad` at the same controller tick. Measured over every sample of every run,
each condition is satisfied for tens of seconds and the two are **never
satisfied together** in any run that failed — r4 spent 55.9 s inside the
position circle and 47.1 s inside the heading window with 0 samples inside
both. The reason they cannot be brought together is geometric and was measured
rather than argued: in the endgame this vehicle pays **2.1-2.6 m of travel per
radian** of heading change, so correcting one yaw tolerance costs ~0.32-0.39 m
of travel against a 0.25 m position box. **The correction is larger than the
box it has to stay inside.** The run therefore either completes on the approach
itself or does not complete at all, and the discriminator is the heading the
approach happens to deliver: every run arriving inside 8.6 deg finished at once,
every run arriving outside it did not.

## 2. Two hypotheses killed before anything was changed

- **Real-time factor / wall-clock loop rates.** WSL measures RTF 0.996-1.001
  bare and with the full stack up. The container's is recoverable from the
  **committed** `m5-10-a_straight-stack.txt`: 13 replans spanning 12.6 s of wall
  clock inside a run spanning 13.39 s of simulation time — **RTF ~1.0 there
  too**. Falsified. The 4-core / 20-core clue is real but it is not acting
  through timing.
- **Belief degrading during the long pre-goal dwell.** WSL issues its goals at
  t_sim 150-183 against the container's 45-48. Measured at the instant of goal
  acceptance, the believed pose is **0.000 m / 0.00 deg off truth in every run
  on both platforms**, and r2 — which stood longest, 178.82 s — produced the
  best run of the session. Falsified, with a positive control.

## 3. The confirmation, run as an experiment and NOT applied

Three one-variable runs, each against a `/tmp` copy of `nav2.yaml` differing by
**exactly one line** (verified by `diff` after the run), passed in with
`params_file:=`. Nothing in `agv/` was edited.

| | change | result |
|---|---|---|
| e2 | `yaw_goal_tolerance` 0.15 -> 0.60 | SUCCEEDED **15.01 s** on the approach, 5.752 m |
| e3 | the same, repeated | SUCCEEDED **13.71 s** on the approach, 5.559 m |
| e4 | `xy_goal_tolerance` 0.25 -> 0.45 | SUCCEEDED 31.06 s after one correction manoeuvre |

**e2 completed with a believed heading error of 8.642 deg — 0.048 deg outside
the committed tolerance.** Under the committed configuration that identical
approach would have been rejected and would have entered the shuffle. The
margin is not small; it is negative by a rounding error.

A fourth experiment (e1) falsified the intermediate hypothesis that the
`stateful: true` latch was being reset by the tree's 1 Hz replan: with the
replan rate cut tenfold (11 resets instead of 116) the vehicle **parked 2.7 cm
from the goal and stayed there pointing 47 deg away for 85 s**. Position was
never the binding term.

## 4. Ruling on the committed figures — the second half of the deliverable

Full table in `EVIDENCE_NAV2.md` section 8.6. Summary:

- **Still stands, re-measured:** the whole section 5.5 planner bench, every row
  exactly (5.693 / 2.000 / 6.106 / 6.003 / 10.254 m, same cusps, same reverse
  percentages, D refused) — **the planner is deterministic and is not the
  variable**; the plan for case A (5.693 m, 71 points, 1 cusp, 1.6 % reverse) in
  all nine runs; the 0.092 m leading reverse primitive; the 0.141 m instrument
  floor; and section 5.1's 240 s non-completion, which is the majority case here.
- **Superseded:** case A's single "SUCCEEDED 13.40 s / 0.183 m" is superseded as
  a result by the five-run distribution; localization max **0.263 -> 0.661 m**
  and heading **4.52 -> 11.32 deg**, both during the recovery shuffle only, with
  a clean traverse measuring **better** than committed (0.042 m rms, 0.096 m
  max).
- **Unverified on this platform:** cases B, B', C and D as drives; the section 3.3
  conversion check as a run; the five section 1 parameter probes; the
  `lookahead_dist` 1.20 -> 1.60 comparison; section 2's footprint and aisle
  budget (both computed, not measured); section 5.5's planning times.

## 5. Open questions

1. **Section 6 item 1 of `EVIDENCE_NAV2.md` is dimensioned wrongly and section 8
   says so in place.** It states the vehicle "has no small move that closes a
   0.3 m gap". The measurement is the opposite: the position gap is closed
   routinely (r4 reached 0.047 m, e1 reached 0.027 m); the **heading** is what
   cannot be brought in. The committed text was not edited — it is a committed
   measurement's conclusion — and the correction is written in section 8.3 with
   its evidence.
2. **Which term pays.** `xy_tol > R_endgame x yaw_tol` must hold; with R
   measured at 2.1-2.6 m/rad the committed pair fails it by ~1.5x. Both e2 and
   e4 restore it. Which one is correct is a decision about what a "reached" goal
   means for a fork truck at a station, and it belongs to the owner, not to a
   tuning pass. **Not decided and not applied here.**
3. **The upstream fix is the arrival heading, not the tolerance.** Widening the
   checker hides the cause; the vehicle still arrives turning because RPP is
   correcting cross-track error into the last metre. An approach corridor — the
   final segment driven straight along the goal heading — would fix it, and
   lives in the behaviour tree or a plan post-processor, not in `nav2.yaml`.
4. **`footprint_padding: 0.27` no longer covers the localization error it is
   derived from, during recovery** (0.661 m measured against the 0.263 m it was
   dimensioned from). Fixing 2 or 3 removes the regime; growing the padding is
   the alternative and costs aisle clearance (section 2.1).
5. **The other three section 5 cases were not driven here** and are marked
   unverified. If criterion (d) is to cite them, they need a run on this
   platform.

**Two requests outside `agv/`, made here rather than actioned:**

- **`sim/` (or a harness brief): `EVIDENCE_NAV2.md` section 7's planner-bench
  recipe is incomplete.** `planner_server` **fails to activate** without a TF
  tree, and every route then returns `205 START_OCCUPIED`, which reads like a
  map fault and is not one. The two `static_transform_publisher` lines that make
  it work are recorded in section 8.8. The recipe itself is in a file this brief
  may edit, and it was left alone because section 7 is committed content; the
  working form is in section 8.8 instead.
- **`docs/LESSONS.md` (I cannot write it), two entries earned here:**
  - *2026-08-05 | A route that had "succeeded in 13.40 s" was treated as a
    result and its failure elsewhere as a regression | Five repeats on the
    reported-broken platform gave 1 clean run, 2 late ones and 2 timeouts, and
    the original platform's own committed history was 1 success in 4 at the same
    parameters — the figure was one draw from a distribution that straddles the
    acceptance criterion | A pass/fail figure is quoted with its repeat count;
    a criterion a run can only just meet is reported as a margin, not as a pass,
    and one draw is never the evidence a gate rests on.*
  - *2026-08-05 | A goal checker's two tolerances were each derived, correctly,
    from the localizer's own measured error | On a vehicle that cannot rotate in
    place the two are coupled: correcting one yaw tolerance costs ~2.4 m of
    travel per radian, more displacement than the position tolerance allows, so
    the pair was jointly unreachable and the vehicle could satisfy either but
    never both | Tolerances on a non-holonomic vehicle are dimensioned as a
    PAIR against the turning geometry (xy_tol > R x yaw_tol), not term by term
    against the sensor.*

## 6. Scope

No commit, no branch. Working tree carries `agv/forklift/EVIDENCE_NAV2.md`
(append only) and 37 new files under `agv/forklift/evidence/` prefixed
`m5-31-`. Nothing else in the repository was written. No dependency was added;
everything used is `ros2`, `gz`, and the committed harnesses. No Nav2, AMCL,
EKF, smoother, tree or launch value in `agv/` was changed, and the machine was
verified idle before the first run and torn down to zero processes after each.
