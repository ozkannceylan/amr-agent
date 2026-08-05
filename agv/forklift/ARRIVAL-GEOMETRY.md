# ARRIVAL-GEOMETRY.md — a derived, deterministic arrival for a steered vehicle

Research document, brief m5-32. **This file contains no configuration and
proposes no parameter edit.** It derives the constraint a conjunctive arrival
test must satisfy on this vehicle, surveys how steered vehicles actually
arrive on a pose, and phases a plan whose first phase fits inside M5. A later
brief implements from it.

Everything measured is quoted from the committed evidence
(`EVIDENCE_NAV2.md` §3/§5/§8, `docs/TODO.md` "Measured numbers a later
session should not re-derive", report m5-31); nothing measured is re-derived
here. Every external claim carries a source, a version and a verification
date, and is graded (§5).

---

## 1. The problem, restated as one inequality

The goal checker (`SimpleGoalChecker`, `xy_goal_tolerance: 0.25` m,
`yaw_goal_tolerance: 0.15` rad = 8.594°) requires position **and** heading
inside tolerance **at the same controller tick**. This vehicle steers and
cannot rotate in place, so heading is bought with travel. m5-31 measured the
price: **2.1–2.6 m of travel per radian** of heading change in the endgame,
so one yaw tolerance of correction costs 0.32–0.39 m against a 0.25 m
position box. Proven, not argued: r4 spent 55.9 s inside the position circle
and 47.1 s inside the heading window with **zero samples inside both**.

The owner's ruling: fix it upstream — the vehicle arrives already aligned —
and fix it deterministically. Widening the yaw tolerance is ruled out; it
hides the geometry rather than removing it.

## 2. The derivation — the spine of this document

### 2.1 The relation

Consider a vehicle standing at the goal position with a heading error Δθ and
a minimum turning radius R. The shortest motion that changes heading by Δθ
is an arc of radius R; the arc length is R·Δθ and the vehicle's displacement
over it is the chord

    c(Δθ) = 2 R sin(Δθ/2) ≈ R·Δθ        (small-angle form, error < 1 % below 30°)

A correction of one full yaw tolerance therefore displaces the vehicle by at
least R·yaw_tol. For the vehicle to fix its heading **without leaving the
position circle**, that displacement must fit inside the circle. The
satisfiability condition for the conjunctive test is:

    xy_tol  >  R × yaw_tol            … (A)

with R the radius the vehicle **actually achieves in closed loop**, not the
mechanical datasheet number.

### 2.2 What (A) assumes, and where it stops holding

1. **Single arc, executed exactly.** (A) counts one arc at constant R with
   no entry or exit transient. The real steer axis slews at 2.0 rad/s
   (`model.sdf` `steer_joint` `<velocity>`), so reaching the stop from
   centre costs 0.65 s of uncommanded-curvature travel before the arc even
   begins. Every transient adds displacement (A) does not count, so (A) is
   a **necessary condition, never a sufficient one**.
2. **The chord direction is not free.** The arc's displacement direction is
   fixed by the current heading, so a correction that must ALSO return to a
   particular position needs composed arcs — an S-curve or a reverse cusp —
   and each composition multiplies travel. This is exactly why the measured
   endgame cost (2.1–2.6 m/rad, m5-31 §8.3) exceeds the single-arc tightest
   measured radius (1.291 m): the controller is not executing minimal
   Reeds-Shepp corrections, it is oscillating between fixing position and
   fixing heading.
3. **Small angle.** Above Δθ ≈ 30° use the chord form 2R·sin(Δθ/2); the
   linear form over-counts (conservatively) there.
4. **Perfect self-knowledge.** The checker evaluates the *believed* pose.
   The localizer's own error consumes part of both tolerances: measured
   clean-traverse rms 0.042 m position / 0.78° heading, and up to 0.115 m /
   1.66° in non-shuffling runs (m5-31 §8.5). Any margin (A) leaves must be
   larger than that consumption.
5. **The latch.** `stateful: true` latches position once satisfied, but the
   latch is reset by every replan (1 Hz from the tree). m5-31 e1 proved the
   latch is not the mechanism — with replans cut tenfold the vehicle parked
   2.7 cm out and pointed 47° away for 85 s — so (A) must hold at a single
   tick regardless of latching.

### 2.3 The three values of R this vehicle has, each honest

| R | value | source | status |
|---|---|---|---|
| Mechanical minimum, rear-axle midpoint | **0.280 m** = L/tan(δ_max) = 1.05/tan(1.31) | `model.sdf` (named authority): drive wheel x = +0.55, rear axle x = −0.50 → wheelbase L = 1.05 m; steer stop ±1.31 rad | Physics ceiling. Unreachable in closed loop: the planner deliberately reserves steer authority (nav2.yaml plans at R = 1.05 m) and the controller understeers |
| Tightest arc measured in closed loop | **1.291 m** (commanded 1.05 m, achieved 1.291 m, 23 % understeer) | `EVIDENCE_NAV2.md` §3.3; `docs/TODO.md` "smallest measured arc radius 1.29 m" | The best single arc the vehicle has ever demonstrated |
| Effective endgame cost | **2.1–2.6 m/rad** (median instantaneous radius 1.05–2.21 m) | m5-31 §8.3, measured over every endgame sample of eight runs | What the committed controller stack actually pays when correcting near a goal |

### 2.4 The committed pair, evaluated against (A)

R × yaw_tol with yaw_tol = 0.15 rad, against xy_tol = 0.25 m:

| R used | R × yaw_tol | margin (xy_tol − R·yaw_tol) | verdict |
|---|---|---|---|
| 0.280 m (mechanical) | 0.042 m | **+0.208 m** | passes trivially — **this is why the pair looked plausible on paper**; the paper vehicle does not exist in closed loop |
| 1.291 m (tightest measured arc) | 0.194 m | **+0.056 m** | nominally passes, but the +0.056 m margin is *smaller than the localizer's own 0.042–0.115 m position rms* (assumption 4), and assumption 1's transients are uncounted — marginal at best, and only for a perfectly executed single arc |
| 2.1–2.6 m/rad (measured endgame) | 0.315–0.390 m | **−0.065 to −0.140 m** | **fails by 1.26–1.56×** (~1.5×, as m5-31 stated). The correction is larger than the box |

**Conclusion of the derivation.** Against every R the vehicle has
demonstrated in closed loop, the committed pair fails or grazes (A). Two
designs are internally consistent:

- **(i)** resize the pair until (A) holds with a margin that also covers
  assumption 4 — yaw widening is ruled out by the owner, and widening xy to
  cover the endgame R means xy_tol > 0.39 m + localization, i.e. ≥ 0.5 m,
  which is no longer a station arrival; **or**
- **(ii)** make the endgame unnecessary: deliver the heading **on the
  approach**, so that position and heading become true simultaneously and
  no correction manoeuvre ever runs. This is the owner's ruling, and it is
  what every measured clean run already did: both clean traverses arrived
  turning 1.5–1.6° in the endgame, and every run arriving inside 8.6°
  finished at once (m5-31 §8.3).

Design (ii) does not repeal (A): (A) still governs the **failure branch**.
When an approach misses, the vehicle must not attempt an in-circle
correction (A) proves impossible — the correct response is a **go-around**:
retreat and re-approach. §4.2 shows industry and Nav2's own docking server
both do exactly this.

## 3. What the committed stack already guarantees, verified locally

**The plan already ends aligned.** SmacPlannerHybrid's Reeds-Shepp analytic
expansion connects the search to the exact goal pose. Verified from the
committed artifact, not from documentation: the terminal point of
`evidence/m5-31-a_straight-r2-plan.json` (`first_plan_map[-1]`) is
(7.0846, 12.5333, **yaw 0.000**) against goal yaw 0.000, with the last
0.29 m at ≤ 2.03°. The plan is deterministic and identical in all nine runs
of the m5-31 session. **Planning is not the problem; delivery is.**

**The controller has no terminal-heading authority.** RegulatedPurePursuit
is a path tracker. Its rotate-to-heading feature is (a) kinematically
impossible here and (b) mutually exclusive with reversing — the installed
library carries the literal refusal string: *"Both use_rotate_to_heading
and allow_reversing parameter cannot be set to true."*
(`libnav2_regulated_pure_pursuit_controller.so`, nav2 1.3.12, read
2026-08-05). RPP delivers whatever heading the last metre of tracking
happens to give, and m5-31 measured that to be the run-to-run variable:
arrival headings −16° to +37° on an identical plan from an identical
believed start.

**The checker inventory of this installation** (nav2_controller 1.3.12
`plugins.xml`, read 2026-08-05): `SimpleGoalChecker` (xy + yaw),
`StoppedGoalChecker` (adds velocity-at-rest), and `PositionGoalChecker` —
*"Goal checker that only checks XY position and ignores orientation"*.
Multiple goal checkers are configurable and selectable per goal: the
`FollowPath` BT node has a `goal_checker_id` input port and a
`GoalCheckerSelector` BT action exists (`nav2_tree_nodes.xml`, read
2026-08-05), symmetric with the `ControllerSelector`/`PlannerSelector`
pair the committed tree already uses. A staging goal can therefore be
checked position-only while the final goal keeps the tight pair — **without
touching the final tolerances**.

**Not in this build:** the Smac `goal_heading_mode` parameter (relax/
bidirectional terminal heading) does not exist in the installed 1.3.12
planner (symbol sweep of `libnav2_smac_planner.so`, 2026-08-05); it is a
later-distribution feature and is not available to lean on.

## 4. The survey — how steered vehicles actually arrive

### 4.1 Nav2's intended answer: the docking server, and it is already installed

`opennav_docking` 1.3.12 is **installed on the showcase machine** (dpkg,
2026-08-05 — it arrived with the m5-21/m5-26 system Nav2; using it is a new
*active component*, not a new dependency). Its workflow, from the installed
artifacts and the project README (fetched 2026-08-05):

1. Navigate (via Nav2, normal planner/controller) to a **staging pose** —
   a pose offset back from the dock along the dock's approach axis
   (`staging_x_offset_`, `staging_yaw_offset_` in the installed
   `simple_charging_dock.hpp` / `simple_non_charging_dock.hpp`; README
   default 0.7 m, chosen "close enough to detect the dock, far enough that
   imperfect localization still detects it").
2. Detect the dock and enter a **sensor-guided final approach** — a smooth
   pose-stabilizing control law (installed `controller.hpp` carries
   `k_phi_, k_delta_, beta_, lambda_, slowdown_radius_, v_linear_min/max_`,
   the Park & Kuipers graceful-motion parameter set), with the dock pose
   refined by perception during the approach, and `dock_backwards`
   supported.
3. On failure, **return to the staging pose and try again**, up to
   `max_retries` (default 3). The installed core library carries the
   literal string *"Returned to staging pose, attempting docking again."*

This is the productized form of exactly the m5-31 problem — and it
separates the two ideas this document needs: the **staging pose + straight
final approach + go-around retry** (pure geometry, usable now, uses only
the localizer) from **dock perception** (a local sensor closing on the
station, which is what buys ±cm accuracy). The brief's constraint — no
solution may require the vehicle to know its pose better than the localizer
tells it — permits the first today and defers the second, and
`nav2.yaml`'s own no-docking-claim note (0.263 m belief vs the ±1 cm
industrial figure) already said the perception half is M6's.

### 4.2 The staged-pose / approach-corridor pattern, and what the offset is chosen from

The pattern: plan to a **staging pose** offset distance d back along the
goal heading; then drive a short, fresh, straight final leg. The final
leg's plan starts where the vehicle actually stands (near-zero cross-track
by construction), so tracking has nothing left to correct into the last
metre — which is the measured mechanism of both clean runs (r2 tracked
0.09 m off-centre and arrived at +2.17°; r1 tracked 0.41 m off and arrived
turning).

**Deriving d from this vehicle's numbers** (not tuned):

- The vehicle arrives at the staging pose with a position error up to the
  staging tolerance plus localization: e₀ ≈ 0.25 + 0.10 ≈ 0.35 m
  (position-only staging check at the committed 0.25 m, clean-run
  localization rms ≤ 0.10 m).
- Removing a lateral offset e₀ with two opposed arcs of radius R needs
  longitudinal distance x ≈ 2·√(R·e₀) (standard lane-change geometry,
  e₀ ≪ R). With R = 1.291 m: x = 2·√(1.291 × 0.35) = **1.34 m**.
- Tracking then needs a straight tail to converge and centre the steer:
  one lookahead distance, **1.60 m** (`lookahead_dist`, nav2.yaml).

    d  ≥  2·√(R·e₀) + lookahead  =  1.34 + 1.60  ≈  **3.0 m**

Checked against the brief's §6 corridor constraint: the corridor lies
**along** the approach axis, so it consumes aisle *length*, not the
0.356 m lateral pinch budget. Where a station cannot be given 3.0 m of
straight run-in (a pinched or cornered approach), that station's approach
is a **fleet-routing constraint to hand to M6**, exactly as the brief
anticipates — the fleet manager places the staging node; the vehicle does
not improvise one.

One honest caveat, so the corridor is not oversold: the m5-31 route was
*already* a 5.5 m straight and still delivered ±37° arrivals in bad draws.
The corridor is necessary but the load-bearing changes are (a) the final
leg **starting fresh at the staging pose** (near-zero initial cross-track,
against r1's 0.41 m mid-route build-up), and (b) the **go-around** replacing
the endgame shuffle when an approach still misses. A miss then costs one
bounded re-approach (~30–40 s) instead of 69–120 s of the one manoeuvre §2
proves cannot terminate.

### 4.3 Industrial AGV and forklift practice

Consistent shape across the industrial literature (graded C except where
noted, §5): map-grade localization is used to reach an **approach zone**,
never as the docking instrument; the final approach is a **straight,
slowed, sensor-guided segment** entered from a staged position; docking
repeatability of ~±10 mm is bought with local sensing (reflector/laser
triangulation, QR/marker, or pallet-edge detection), not with a better map
pose; and a detected misalignment triggers a **re-docking attempt** — back
out, re-approach — not an in-place correction. NIST's review of AGV docking
research (NISTIR 8140, 2016) is the survey-of-record for the field
[located 2026-08-05; title/abstract level]. This matches the project's own
committed position (`nav2.yaml`: no docking claim at 0.263 m belief error)
and confirms the phase split: geometry now, local sensing at M6.

### 4.4 Ackermann versus tricycle, for this problem

**Nothing differs in kind.** Both reduce to the bicycle model: one
equivalent steered axle at wheelbase L, curvature κ = tan(δ)/L, minimum
radius R = L/tan(δ_max), no rotation in place, Reeds-Shepp reachability.
Relation (A) depends only on (R_effective, cannot-rotate-in-place), so
every conclusion here transfers between the two unchanged.

What differs is **degree and dress**:

- **Steer range.** This tricycle's single steered wheel reaches ±75.06°,
  giving R_mech = 0.28 m; a typical Ackermann front axle stops near
  30–35° (R_mech ≈ 1.4–1.8×L) because the linkage and inner-wheel geometry
  bind first. An Ackermann vehicle of this size would fail (A) *harder* at
  the same tolerance pair — the owner's instinct that a real forklift
  shares this problem is correct, with margin.
- **Which end steers.** Real counterbalance trucks steer the rear axle and
  carry the load over the front (drive) axle; this model steers and drives
  the front single wheel with the load aft. That mirrors the geometry
  end-for-end and changes nothing in (A) — the steered end is simply where
  the cusp-rich manoeuvring happens, which is why fork-first station
  approaches at M6 will want the same staged straight leg in reverse
  (`dock_backwards` exists for exactly this).
- **The Reeds-Shepp planner cares only about R**, not about which axle
  steers: the committed plans transfer to an Ackermann vehicle with
  R ≥ 1.05 m as-is.

## 5. Sources, graded

| # | Source | Version / ref | Read | Grade |
|---|---|---|---|---|
| S1 | `nav2_controller` `plugins.xml` (checker inventory incl. `PositionGoalChecker`), `nav2_tree_nodes.xml` (`goal_checker_id` port, `GoalCheckerSelector`) | ros-jazzy 1.3.12-1noble.20260615, installed on the showcase machine | 2026-08-05 | **A** — installed source of the exact binaries in force |
| S2 | `libnav2_regulated_pure_pursuit_controller.so` literal: rotate-to-heading ∧ reversing rejected | 1.3.12 | 2026-08-05 | **A** |
| S3 | `libnav2_smac_planner.so` symbol sweep: analytic_expansion_* present, `goal_heading_mode` absent in this build | 1.3.12 | 2026-08-05 | **A** |
| S4 | `opennav_docking` installed: package 1.3.12; `staging_x_offset_`/`staging_yaw_offset_` (dock headers); `k_phi/k_delta/beta/lambda` (controller.hpp); staging/retry/`dock_backwards` strings (`libopennav_docking_core.so`) | 1.3.12 | 2026-08-05 | **A** |
| S5 | Committed plan artifact terminal heading = goal heading exactly | `evidence/m5-31-a_straight-r2-plan.json` | 2026-08-05 | **A** — this repository's own measurement |
| S6 | VDA 5050 specification, `allowedDeviationXY`/`allowedDeviationTheta` and `finePositioning` semantics (quoted §6) | 2.1.0, tag `2.1.0` commit `511d01d`, `VDA5050_EN.md` via raw.githubusercontent | 2026-08-05 | **B** — official spec text, fetched not diffed |
| S7 | opennav_docking README: workflow, staging default 0.7 m, staging-offset guidance, `max_retries` 3 | github.com/open-navigation/opennav_docking, `main` (unpinned) | 2026-08-05 | **B** — project documentation |
| S8 | NISTIR 8140, *Review of Research for Docking Automatic Guided Vehicles* (NIST, 2016) | nvlpubs.nist.gov | located 2026-08-05, **not read in full** | **B** for existence/scope; claims not individually load-bearing here |
| S9 | Trade/industry articles: ~±10 mm reflector-laser docking repeatability, two-stage global→local approach, perpendicular-approach re-docking | automatedwarehouseonline.com, fabrico.io, aitenrobot.com, PMC fuzzy-docking paper | 2026-08-05, snippet level | **C** — `[snippet]`-graded per the ADR 0016 rule; used for the shape of practice only, no number from them is load-bearing |
| S10 | Park & Kuipers graceful-motion control law as the family behind S4's parameter names | background knowledge, corroborated by the installed header's exact parameter set | — | **C** — attribution only; nothing rests on it |

No claim in §2 rests on anything below grade A: the derivation uses only
`model.sdf`, `nav2.yaml`, and committed measurements.

## 6. The contract already has the vocabulary

`docs/interfaces/vda5050-subset.md` §4, committed since M1, order topic,
`nodePosition`:

> | nodePosition.allowedDeviationXY | number ≥ 0 | no | Arrival tolerance radius in m |
> | nodePosition.allowedDeviationTheta | number, ±π | no | Arrival orientation tolerance |

And the standard itself (VDA 5050 2.1.0, S6): *"The AGV decides on its own,
when a node should count as traversed. Generally, the AGV's control point
should be within the node's `allowedDeviationXY` and its orientation within
`allowedDeviationTheta`."* For tighter-than-deviation positioning the
standard provides the predefined action `finePositioning` (currently in this
project's not-supported list, §6 of the subset — a deliberate M6 candidate).

**Everything proposed here is expressible in the standard, with nothing
invented:**

- The tolerance pair per station is `allowedDeviationXY` /
  `allowedDeviationTheta` on the station node — the fleet manager owns it,
  the vehicle maps it onto its goal checker. Relation (A) becomes the
  vehicle's *acceptance rule*: a node whose deviation pair violates (A) for
  this vehicle's R is reported as an order error rather than attempted —
  the factsheet's kinematic fields are where a fleet manager would learn R.
- The **staging pose is just a node**: a VDA 5050 order is a sequence of
  nodes, so the fleet manager places the penultimate node 3.0 m before the
  station on the approach axis with a loose deviation pair, and the station
  node carries the tight pair. The staged approach is therefore not an
  extension at all — it is what orders are for, **and M6 gets it free**.
- The sensor-guided ±cm final approach, when it comes, is `finePositioning`.

## 7. The plan, phased

House style of report m5-22 §4: one observable done-condition per phase,
files touched, an explicit does-NOT list, owner-decision markers, and the
predicted effect on the m5-31 failure distribution (5 runs: 1 clean,
2 recovered in 69–94 s, 2 timed out).

### Phase 0 — the owner's definition of "reached" (decision, no work)

**OWNER DECISION.** The tolerance pair for a station arrival, stated as a
pair against (A), not term by term. Recommended: **keep 0.25 m / 0.15 rad
as the final checker** — under the staged design the conjunction is
satisfied on the approach (design (ii), §2.4), so the pair no longer needs
to satisfy (A) *provided* the miss branch is a go-around, never an endgame.
The alternative (resize until (A) holds) requires xy ≥ ~0.5 m and is
recommended against. This ruling is one sentence and gates nothing in
Phase 1's build; it gates the evidence wording.

### Phase 1 — staged approach with go-around (INSIDE M5)

**What.** Arrival becomes deterministic by construction, using only the
localizer:

1. A staging pose is computed from the goal: offset **d = 3.0 m** (derived
   §4.2) back along the goal heading, same heading.
2. Goal 1: NavigateToPose to the staging pose, checked **position-only**
   (`PositionGoalChecker`, installed, S1), selected per-goal via
   `GoalCheckerSelector` exactly as the committed tree already selects
   controller and planner.
3. Goal 2: NavigateToPose to the station pose — a fresh, ~straight 3 m leg
   from a standing start with near-zero initial cross-track — checked by
   the committed tight pair, untouched.
4. **Missed approach = go-around**: if goal 2 fails or times out (bounded,
   ~40 s not 120 s), return to the staging pose and re-approach, at most
   N = 2 times, then report failure honestly. No in-circle correction is
   ever attempted, because §2 proves it cannot terminate.

**Where.** The sequencing lives in the goal-sending layer
(`scripts/nav2_run.py`, which m5-31 §8.7 item 5 already wants to grow a
repeat argument) — not in Nav2 internals. Files touched by the
implementing brief: `scripts/nav2_run.py` (staging/approach/retry logic),
`behavior_trees/navigate_to_pose_tricycle.xml` (add `GoalCheckerSelector`,
one line, mirroring the two selectors already present), `nav2.yaml` (one
added checker instance block; **no committed tolerance changes**),
`EVIDENCE_NAV2.md` (new section). At M6 the same sequencing is the VDA 5050
client's node-by-node order execution — the harness logic is written to be
lifted, not kept.

**Does NOT:** widen any final tolerance; touch RPP, Smac, AMCL, EKF, the
footprint or the padding; add perception; claim docking accuracy; add a
dependency (every mechanism is in the installed 1.3.12 stack, S1); require
pose knowledge beyond the localizer.

**Done when:** five repeats of route A through the staged sequence, and
(a) the distribution moves from 1/2/2 to ≥4 clean of 5 with any non-clean
run ending in a bounded go-around rather than a shuffle; (b) the mechanism
column — believed heading at first entry into the position circle — is
inside 8.594° on every clean run, which is the m5-31 discriminator
explaining *why* the distribution moved; (c) no run shows the shuffle
regime, verified by localization max staying ≤ 0.263 m (the figure
`footprint_padding` is derived from), which closes m5-31's second-order
finding for the arrival case.

**Predicted effect on the distribution, by mechanism:** the two timeouts
and two 69–94 s recoveries were all endgame shuffles entered from a
misaligned arrival; the staged final leg reproduces the conditions of the
two measured clean arrivals (fresh straight leg, near-zero cross-track →
arrival heading 1.5–3.9° in every measured instance), and any residual miss
costs one ~30–40 s go-around instead. The 0.661 m localization excursion
disappears with the shuffle that caused it. This is a prediction from
measured mechanisms; the five repeats are the test, and the pass criterion
is the distribution, not one run.

**Honest cost:** roughly half a day including the five-repeat evidence run
— the script logic is small, the runs dominate. Not padded, and not
smaller than that.

### Phase 2 — speak the fleet contract's language (M5 tail / M6 seam)

Map `nodePosition.allowedDeviationXY/Theta` → goal-checker selection in the
VDA 5050 client node, and the staging pose → a penultimate order node
placed by the fleet manager (§6). Vehicle-side acceptance rule: reject a
node pair violating (A) for this vehicle's R. Files: the client node,
`docs/interfaces/vda5050-subset.md` (one note row; interface agent's file —
**requested, not edited by agv**). Does NOT: extend the standard; every
field already exists in the committed subset. Done when an order carrying
deviation fields drives the same staged arrival Phase 1 measured, with no
harness in the loop. Effect on distribution: none beyond Phase 1 — this
phase moves the mechanism to its contractual home so M6 inherits it.

### Phase 3 — sensor-guided station approach (M6, owner decision)

**OWNER DECISION** (two: activating the docking server as a new running
component, and the perception source). Adopt `opennav_docking` (installed,
S4) per station: staging pose from the same d derivation, dock plugin
closing on station-local features, `dock_backwards` for fork-first,
`max_retries` as the productized go-around. Only here may ±cm figures be
claimed (S9's industrial practice; `nav2.yaml`'s no-docking-claim note
retires here and not before). VDA 5050 expression: `finePositioning`
(moves from the not-supported list — an interface brief). Effect on
distribution: replaces the Phase 1 final leg's map-referenced accuracy
(bounded by the 0.141 m instrument floor) with station-referenced accuracy;
the arrival *reliability* question is already closed by Phase 1.

## 8. Measurements to take, not estimated

Named per the brief's rule — nothing below is guessed at in this document:

1. **Arrival-heading distribution of the staged final leg** (n ≥ 5) — the
   Phase 1 acceptance measurement itself.
2. **Understeer at small steer angles.** The 23 % figure was measured at
   the tightest arc; the final leg lives at near-zero curvature, where the
   understeer ratio is unmeasured.
3. **The leading reverse primitive on a 3 m leg.** Every committed plan on
   the straight route opens with a 0.092 m Reeds-Shepp reverse; whether it
   appears at the staging end of a short final leg, and whether it
   disturbs the first metre, is a measurement, not an assumption.
4. **Go-around cost** — wall-clock of one full retreat-and-re-approach, so
   the timeout budget for goal 2 is set from a number rather than the
   120 s inherited from route runs.
5. **Staging arrival scatter** — the actual e₀ distribution at the staging
   pose under `PositionGoalChecker`, which either confirms d = 3.0 m or
   re-derives it through the same formula with the measured e₀.

---

## 9. Forcing the arrival (m5-34 design)

This section is the m5-34 design and, unlike §1–§8, it **does** name the
two values a build changes. It takes m5-33's three named mechanisms
(report m5-33 §5, `EVIDENCE_NAV2.md` §9.6) and fixes or rules out each
one, then derives the lever from the §2/§4.2 relations. Everything quoted
is a committed measurement; everything derived shows its arithmetic; every
prediction is registered before the run so the five repeats can falsify
the design rather than merely report it.

### 9.1 Mechanism 1 — the terminal stall is a DEADLOCK, derived and matched

The brief asked whether the vehicle can physically execute 0.015 m/s at
near-full lock. The answer is that **the plant never received that
command at all**. The stall is a closed loop between three committed
parameters, none of them wrong alone:

1. **The smoother's from-rest ceiling.** `velocity_smoother` is
   `CLOSED_LOOP` on the EKF and limits acceleration against the
   *measured* twist. From rest, its output per 20 Hz tick can exceed the
   measurement by at most `max_accel × Δt`: **0.025 m/s** linear and
   **0.0238 rad/s** angular. With `scale_velocities: true` the whole
   twist is scaled by the most restrictive axis, so at commanded
   curvature κ the linear output from rest is pinned at

       v_pinned(κ) = min(0.025, 0.0238/κ)  m/s.

2. **The converter's creep deadband.** `cmd_vel_to_tricycle.py` publishes
   **zero traction** for any |v| below `creep_speed_mps = 0.02`
   (config.yaml), holding the steer axis. This is the below-creep branch,
   not a refusal — which is exactly why r1's refusal counter stayed
   frozen at 5.

3. **The loop.** Zero traction → the plant does not move → the EKF
   measures zero → the smoother stays pinned at v_pinned → the converter
   keeps zeroing. **Permanent**, until a timeout cancels the leg.

The deadlock arms whenever the vehicle is at rest and the commanded
curvature satisfies v_pinned(κ) < 0.02, i.e.

    κ > 0.0238 / 0.02 = 1.19 1/m   ⇔   steer > atan(1.19 × 1.05) = 51.3°.

**Matched against r1, number by number.** r1 stalled with the steer at
+1.072 rad (61.4° > 51.3°, armed): κ = tan(1.072)/1.05 = 1.75 1/m, so
v_pinned = 0.0238/1.75 = **0.0136 m/s** — the recorded held cmd_v of
**0.015 m/s**, within one sample quantum. Steer held (below-creep branch
holds the axis), traction zero (truth frozen 20 s), refusals frozen (the
INFO branch, |v| = 0.015 > `zero_speed_mps` 0.002). Every recorded
symptom of §9.1 (B) of the evidence is reproduced. r1's go-around leg
(752 of 945 samples at rest) is the same deadlock re-armed: the leg
begins at rest with the steer near lock, which is precisely the arming
condition. The `min_approach_linear_velocity: 0.05` question the m5-33
report raised is answered: RPP's 0.05 never reaches the plant — the
smoother's from-rest ceiling forms the 0.015, and the converter's
deadband turns it into zero.

**The minimum executable command, stated as the rule** (LESSONS
2026-07-28: granted = min(request, cap), never one observed value): from
rest at curvature κ the tightest command this chain can pass to the plant
is v_pinned(κ); at the mechanical lock κ_max = tan(1.31)/1.05 =
3.57 1/m, giving a floor of **0.0067 m/s**. The converter's deadband must
sit *below* that floor or the chain deadlocks at rest for every steer
angle beyond 51.3°.

**The fix — one derived line.** `creep_speed_mps: 0.02 → 0.005` in
`agv/forklift/config.yaml`. The admissible window is derived, not tuned:

    zero_speed_mps (0.002)  <  creep  <  a_wz·Δt / κ_max  (0.0067)

0.005 keeps the refusal semantics untouched (`zero_speed_mps` and
`yawrate_refusal_radps` unchanged, so a Spin still counts as a refusal
and nothing else does) and makes the deadlock unreachable at *any* steer
angle: the armed region κ > 0.0238/0.005 = 4.76 1/m lies beyond the
mechanical κ_max = 3.57. Risk, stated: commands in the 0.005–0.02 band
now steer-and-creep instead of holding. That band's curvature is no
longer noise — `scale_velocities: true` preserves the commanded ratio —
and the steer axis's own 2.0 rad/s slew filters jitter; the build
verifies the deadband change on the converter bench (feed 0.015 m/s at
κ = 1.75: the committed file must publish zero traction, the changed
file a nonzero pair) before any simulator run.

**Ruling: FIXED** (design; the build measures). Falsifier registered:
any run showing ground truth frozen ≥ 5 s while cmd_v is nonzero means
this derivation missed the mechanism.

### 9.2 Mechanism 2 — the go-around restores its precondition by CAPACITY, not by a checker

The measured go-around returned to staging at **−28.56°**
(`EVIDENCE_NAV2.md` §9.4) because the return leg is checked
position-only. Two candidate fixes, one of which the geometry refuses:

- **A heading-checked return fails relation (A) by regress.** For a
  conjunctive check at staging to be satisfiable it needs
  yaw_tol < xy_tol / R_endgame = 0.25 / (2.1…2.6) = **0.096–0.119 rad
  (5.5–6.8°)** — *tighter* than the 8.594° window the final leg cannot
  yet be forced inside. Requiring at staging what cannot be delivered at
  the station is the same problem moved 3 m, with a smaller box. Ruled
  out by arithmetic.
- **Provision the retry instead.** The final-leg length must absorb the
  worst return heading. Extending §4.2's formula with the heading term
  (one arc of R·θ₀ to shed the initial heading, §2.1):

      d  ≥  R·θ₀ + 2·√(R·e₀) + lookahead
         =  1.291 × 0.4985  +  2·√(1.291 × 0.35)  +  1.60
         =  0.64 + 1.34 + 1.60  =  **3.59 m**      (θ₀ = 28.56° measured)

  d = 3.0 m is **under-provisioned for the measured worst return by
  0.6 m** — the retry began worse than the first attempt because the leg
  it re-runs was never sized for a bad entry heading. The d chosen in
  §9.4 (4.5 m) covers 3.59 m with 0.9 m margin, so the re-approach is
  provisioned for the worst measured return heading **without any
  heading check anywhere**.

The stall fix (§9.1) is also load-bearing here: r1's go-around did not
fail for want of heading — it never moved, because the return leg starts
at rest with the steer near lock, the deadlock's exact arming state.

**Ruling: FIXED**, by the §9.1 deadband change plus the §9.4 staging
distance. Falsifier registered: a go-around run whose re-approach enters
the position circle with a *larger* heading error than its first attempt.

### 9.3 Mechanism 3 — what "lateral by construction" implies, and the measurement that is actually missing

m5-33 tested the obvious inference — larger lateral offset causes the
miss — and it is **not supported at n = 5** (r2: 0.231 m off, clean). It
is not resurrected here. What *does* follow from "the staging residual is
lateral by construction" is already inside the d formula: every final leg
contains an S-curve of length 2·√(R·e₀) before its straight tail begins,
so e₀ buys leg length, and the tail — not e₀ — is what converges the
heading. The variance that decides the outcome is the **entry heading**,
and its source is unattributed because one input to the final leg was
never recorded: **§9.2's five-repeat table has no staging-stop heading
column.** The vehicle arrives at staging with an unconstrained,
unmeasured heading (the one instance on record, the bound run, measured
−2.11°), and whether the final leg's entry-heading spread is inherited
from that or generated by tracking is unknowable from the committed data.

**Ruling: RULED OUT as a cause claim (no new evidence, per the brief);
converted into instrumentation.** The build records the staging-stop
heading (believed and truth) per run, exactly as the bound run already
did, so the next analysis can attribute the entry-heading variance
instead of arguing about it. The burden is a measurement; this is the
measurement.

### 9.4 The two levers, derived — and the geometry favours the longer leg

**Lever 1, constrain the heading at staging.** Its checker form is ruled
out by the §9.2 regress arithmetic. Its geometric form — arrive at
staging *along the axis* so the heading is right without being checked —
is achievable only by giving the leg into staging a straight in-line
tail, which is the same mechanism as lever 2 applied one leg earlier: it
lengthens the corridor without lengthening the leg that actually delivers
the station heading. Same cost, indirect benefit. Not chosen.

**Lever 2, lengthen the final leg.** The leg decomposes as S-curve +
straight tail. At d = 3.0 the tail is 3.0 − 1.34 = **1.66 m ≈ 1.04
lookaheads**, and it delivered an entry-heading spread of −1.8…+16.9°.
Sizing the tail at **two lookaheads** (the linearised pure-pursuit
settling constant is the lookahead distance — a model, flagged as such,
not a measurement):

    d  =  2·√(R·e₀) + 2 × lookahead  =  1.34 + 3.20  =  4.54  →  **d = 4.5 m**

Under that model the extra 1.5 m of tail attenuates entry-heading error
by e^(−1.5/1.6) = 0.39: r4's +16.94° maps to ≈ +6.6° and r1's +10.87°
to ≈ +4.3°, both inside 8.594°. The three clean entries (−1.46, −1.78,
+5.44°) can only shrink. **This is the registered prediction the run
tests, and its failure mode is informative**: any entry outside 8.594° at
d = 4.5 falsifies the settling model, and the §9.3 staging-heading column
then says whether the residual variance enters at staging or is generated
on the leg.

**The corridor still fits.** The corridor lies along the approach axis
and consumes aisle length, not the lateral pinch budget (§4.2). Two
statements, kept separate:

- *Route A:* staging moves from (−2.0, +7.0) to (−3.5, +7.0); the run's
  start is (−4.5, +7.0), so the corridor exists and the staging leg
  shrinks to 1.0 m. No column pinch lies on route A.
- *In general:* the S-curve zone — the first ≈1.5 m after staging —
  carries lateral excursion up to e₀ ≈ 0.35 m (r1 measured 0.58 m peak
  to peak), which exceeds the 2.35 m pinches' **0.356 m total** budget.
  So the placement rule a 4.5 m corridor imposes is: **no pinch may
  overlap the S-curve zone**, and the straight tail may cross a pinch
  only at normal tracking error (clean-run rms 0.051 m). This is the
  fleet-routing constraint §4.2 already hands to M6 — lengthening d
  moves the S-curve zone 1.5 m further from the station, it does not
  change the rule.

One confound stated now rather than discovered later: the 1.0 m staging
leg from an aligned standing start will land at staging with less scatter
and a straighter heading than m5-33's 2.5 m leg did. The run therefore
tests forcing under a *smaller* e₀ than m5-33's; the per-run staging
columns (§9.3) are what keep the comparison honest, and the d formula
was sized for e₀ = 0.35 regardless, so the design does not depend on the
easier draw.

### 9.5 The miss branch, completed — abort instead of shuffle

§2.4's design (ii) states that on a miss "no in-circle correction is ever
attempted", and m5-33 built the go-around but not the **miss detector**:
r4 entered at +16.94° and was left to shuffle 20 reversals to a lucky
completion, because nothing declared the miss until the 45 s timeout.
The detector is derivable from the committed measurements:

- **Entry-heading abort.** The §8.3 discriminator is 5-of-5 with no
  exception across m5-33: an entry outside 8.594° does not complete
  cleanly. So at the first sample inside the position circle, if the
  believed heading error exceeds the yaw window, the harness cancels the
  approach and go-arounds immediately.
- **Reversal abort.** Backstop for a within-window entry that degrades:
  cancel at the **second** commanded direction reversal after first
  circle entry. Derived from the measured clean-run counts (0 and 1
  reversal in §8.2's clean traverses; 0, 1, 0 in m5-33's) and below the
  pre-registered shuffle threshold of 3.

Stated plainly so the pre-registered shuffle test is not gamed: these
aborts make "no leg in the shuffle regime" true partly **by
construction**, and that is the design's intent — the shuffle is the
in-circle correction §2 proves cannot terminate, and design (ii)'s
contract is that it is never attempted. An aborted approach is **not
clean** and is scored as a go-around run; the ≥4-of-5-clean criterion is
untouched by the aborts and can still fail honestly. The aborts live in
the harness (`nav2_run.py stage`), the same instrument layer m5-33's
sequencing lives in; at M6 this is the VDA 5050 client's per-node
retry decision, and it is written to be lifted.

### 9.6 The build, exactly, and the one run

Changes (all inside `agv/`, no tolerance touched, no dependency, no
`opennav_docking`, no BT or `nav2.yaml` edit):

| file | change |
|---|---|
| `agv/forklift/config.yaml` | `creep_speed_mps: 0.02 → 0.005`, comment updated with the §9.1 window derivation |
| `agv/forklift/scripts/nav2_run.py` | `stage`: entry-heading abort and 2-reversal abort on approach legs (§9.5); record staging-stop believed+truth heading per run (§9.3); no new subcommand |
| invocation | `--d 4.5` (the argument exists; no code change) |

Pre-run bench check (minutes, no simulator): converter fed 0.015 m/s at
κ = 1.75 — committed file publishes zero traction, changed file a
nonzero pair. This confirms the §9.1 mechanism before any run spends an
hour on it.

Then **one five-repeat run** of route A, the §9.3 chain of
`EVIDENCE_NAV2.md`, same isolation discipline (`GZ_PARTITION` +
`ROS_DOMAIN_ID`, machine verified alone, serialized, torn down to zero),
each row written as it lands. `--max-go-arounds 2`,
`--approach-timeout 45` unchanged (a clean 4.5 m leg costs ≈ 9.5 s; the
timeout is now the backstop behind the aborts, not the detector).

### 9.7 The registered prediction — which runs, and why

Against m5-33's five, mechanism by mechanism:

| m5-33 run | was | predicted at d = 4.5 + creep fix + aborts | why |
|---|---|---|---|
| r2, r3, r5 | clean, entries −1.46/−1.78/+5.44° | **clean**, entries within ±6° | longer tail only shrinks a small entry error |
| r4 | reached through a 20-reversal shuffle, entry +16.94° | **clean**, entry ≈ +7° | the tail doubles from 1.04 to 1.97 lookaheads; settling model §9.4 |
| r1 | stalled 20 s, go-around deadlocked, FAILED | **no stall anywhere** (deadlock unreachable, §9.1); if the entry still misses, an immediate abort and **one provisioned go-around** to REACHED | creep fix + §9.2 capacity |

Predicted distribution: **5 of 5 first-approach clean** is the point
prediction; the done-conditions pass at ≥ 4 of 5 clean, **zero legs in
the shuffle regime** (aborts, §9.5 — scored honestly), localization max
≤ 0.263 m (no shuffle regime → expect ≈ 0.12 m as m5-33 measured).

Falsifiers, each naming the derivation it kills:

1. Any final-leg entry outside 8.594° → the §9.4 settling model is
   wrong; read the staging-heading column to locate the variance.
2. Ground truth frozen ≥ 5 s with nonzero cmd_v → the §9.1 deadlock
   derivation missed the mechanism.
3. A re-approach entering worse than its first attempt → the §9.2
   capacity argument is wrong.
4. A clean-shaped run killed by an abort (entry inside window, < 2
   reversals, cancelled anyway) → the §9.5 thresholds are mis-derived.
