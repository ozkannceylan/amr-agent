# Report m5-08c — adversarial review of the SLAM mapping run

```
brief:               docs/briefs/m5-08c-slam-judge.md
status:              done
files_changed:       docs/reports/m5-08c-slam-judge.md (this file only)
invariants_touched:  none (read only)
open_questions:      one, for the owner: rebuild the map square to the
                     building (heading anchor / zero-velocity update)
                     before AMCL, or register the committed map as-is and
                     carry its ~2 deg rotation. Finding 1 needs one of the
                     two before the AMCL brief is written.
next_suggested:      a one-deliverable pre-AMCL brief: a wall-registration
                     tool that derives and commits T(world->map) from the
                     committed grid with its residual stated; then the AMCL
                     brief written against findings 1-3.
```

## Verdict

The map is real, its dimensions are right, the parameter file is honest,
and the transform story holds — those attacks failed and are shown failing
in the last section. What does **not** hold is the foundation the AMCL
*measurement* is about to be built on: the committed grid is rotated about
2.0 deg from the building and internally sheared by ~0.4 deg, the only
world-to-map transform on record (−2.82 deg) does not match the artifact it
describes, the raw data behind every quoted number was left in `/tmp` and
is gone, and the instrument that produced the headline figures zeroes
initial error by construction — which is correct for a mapping drift figure
and circular for a localisation one. Three findings block the AMCL brief.
None of them requires re-driving the mapping run.

Everything below marked **measured here** was computed in this review
directly from the committed `sim/maps/warehouse/warehouse.pgm` (P5,
614 × 421, verified md5 `8c48cc4e...`), by scanning for occupied cells and
least-squares fitting the four longest straight lines in the grid. No
simulator was run.

---

## Blocking findings

### 1. BLOCKS AMCL — there is no usable world→map transform, and the one number on record is wrong for the artifact

**Claim attacked:** `WAREHOUSE_SLAM_EVIDENCE.md` §5 (lines 209–211): the
map frame "sits at (−6.009, −5.500) in the world and is rotated **−2.82°**
from it", reused in §9 (lines 500–504) as the cos-correction angle for the
span check.

**Measured here, from the committed grid alone:**

| line fitted | points | angle from grid axis | fit rms |
|---|---|---|---|
| east wall (rightmost occupied per row) | 360 rows | **+1.83 deg** | 0.32 px |
| west wall (leftmost occupied per row) | 297 rows | **+1.77 deg** | 0.71 px |
| south wall (bottom-most occupied per column) | 257 cols | **−2.21 deg** | 0.60 px |

A rigid rotation makes all three magnitudes equal. They are not:

- the artifact's mean rotation from the building is **≈ 2.0 deg**, not
  2.82 deg. The −2.82 deg is the frame relation *at the first sample of
  the drive*, taken from a single sample by `anchor()`
  (`sim/scenarios/tools/mapping_evidence.py` lines 315–349); the grid is
  drawn from all 327 graph nodes and does not inherit that instant. The
  0.6–1.0 deg gap is consistent with the parked-EKF drift (finding 4)
  accumulating between slam_toolbox's first scan and the anchor sample,
  which is exactly why the two numbers cannot substitute for each other;
- the grid is **internally sheared ~0.4 deg**: its east/west walls are not
  perpendicular to its south wall. No rigid transform fits this grid to
  `warehouse.sdf` better than ~0.1–0.2 m across the 30 m hall. That is the
  floor under any world-frame localisation number measured against this
  artifact, and it is consistent with (and explained by) the run's 0.185 m
  rms trajectory error.

**Concrete failure scenario:** the AMCL brief converts ground truth into
the map frame using the prose −2.82 deg. At the east wall, 21 m from the
anchor, the transform error alone contributes 0.2–0.3 m — larger than the
error AMCL will likely produce, of the same order as the gate criterion,
and of constant sign, so it does not average out. The gate number would be
a measurement of this report's prose, not of AMCL.

**What to change before AMCL:** either (a) commit a registration: a small
read-only tool that fits the grid's walls against `warehouse.sdf` (the
fits above are ~40 lines of stdlib Python) and writes
`T(world->map)` next to `warehouse.yaml` with its residual stated; or
(b) rebuild the map square to the building (owner decision, see finding 4)
and register the rebuild. Note the transform is **per map**: the gyro bias
sign is drawn per run, so any regenerated map needs re-registration — which
is the argument for committing the tool, not just the number.

Also material: `/tmp/run.csv`, the slam log and the route log — the source
of every number in `WAREHOUSE_SLAM_EVIDENCE.md` — were not committed and
no longer exist. Nothing in the run is recomputable; only the artifact
itself can be re-measured, which is what this review did.

### 2. BLOCKS AMCL — the mapping run's instrument is circular if reused for localisation

**Claim attacked:** that 0.185 m rms / 0.014 m final, produced by
`mapping_evidence.py analyse`, is a measurement method the localisation
brief can inherit.

**How the figures were actually computed** (attack line 1 of the brief):
`record` samples the latest `/forklift/odom` message (gazebo ground truth)
against the latest `map -> base_link` tf at 10 Hz wall; `analyse` trims the
parked segments, then `anchor()` applies the rigid SE(2) transform that
carries the estimate's **first drive sample** exactly onto truth
(lines 315–349). Consequences:

- **initial error is zero by construction**, and any constant offset or
  rotation of the estimate is absorbed into the anchor and vanishes. For
  *mapping* that is the right quantity (drift-since-start; the file says
  so honestly). For *localisation* it is circular: an AMCL that is
  consistently 0.3 m wrong — wrong transform, wrong origin, converged into
  the wrong part of a shallow basin — scores near zero;
- **the anchor is one sample.** Yaw noise in that single map->base_link
  sample rotates the entire error curve: 0.3 deg at the route's ~22 m
  lever arm is 0.11 m. The 0.185 m rms and 0.358 m max carry O(0.1 m) of
  instrument uncertainty from that one sample. The final 0.014 m does
  *not* — see finding 5 for why that makes it the least informative number
  of the run.

**Concrete failure scenario:** the AMCL brief reuses `record`/`analyse`
as-is, anchors AMCL's pose at its first sample, and reports 0.05 m
"localisation error" while the vehicle is 0.3 m off in the map frame for
the whole run. The gate closes on a number that measured precision and
called it accuracy.

**What to change before AMCL:** the AMCL evidence tool must score
**absolute** error — AMCL's `map -> base_link` against truth carried
through the *pre-registered, committed* transform of finding 1 — with no
per-run anchoring anywhere. Stamp-pair the two streams rather than
latest-vs-latest (finding 6).

### 3. BLOCKS the AMCL brief's test design — the degeneracy was never given the chance to bite, and AMCL has less to fall back on than SLAM did

**Claim attacked:** "the three degenerate stretches were crossed
successfully; the finding is a 5 m dead-reckoning budget" (report §"The
prediction, answered by name"; evidence §5).

**What the run actually established, checked against its own tables:** the
vehicle entered every stretch with an along-x error of 0.015–0.137 m and a
heading error of about −1 deg (evidence §5 stretch table), crossed each in
5–7 s at 0.80 m/s, never stopped, never reversed, and the first loop
closure of the run came *after* two of the three crossings. So each
crossing tested: *dead reckoning over ≤ 5.5 m, at cruise, from a
near-perfect prior*. The report's narrowed finding — an odometry budget,
sufficient for a single traverse, with dwell explicitly untested — is the
correct reading and **survives**. What does not survive is any broader
use of "crossed successfully":

- the "budget" rests on four crossings at one speed with benign entry
  state; the worst EKF along-x growth observed was 0.217 m over 4 m
  (5.4%/m of travel), which at picking speed with a degraded prior is not
  obviously inside anything;
- the run outran the condition the prediction named:
  `WAREHOUSE_LANDMARKS.md` §9.4's first candidate ("never held still long
  enough for drift to show") applies verbatim, and the evidence says so;
- **AMCL's situation is strictly worse than the mapper's**: no pose
  graph, no loop closure, the same ten grazing rays (of which the
  vehicle's own mast consumes 9/360 with zero information), and a
  particle filter whose along-x spread in a shallow basin is exactly the
  untested case.

**Concrete failure scenario:** the AMCL gate is measured on the same
moving circuit, passes, and the first docking manoeuvre that dwells 60 s
in East A walks along-x with nothing in the gate evidence having bounded
it — the reflector/fiducial decision (`WAREHOUSE_LANDMARKS.md` §9.2) gets
taken on evidence that never contained the case it exists for.

**What to change:** the AMCL brief must contain, as a named measurement,
a dwell-and-reverse case inside at least one named stretch (stop ≥ 60 s,
reverse, re-enter), and the reflector/fiducial decision must cite its
result. This blocks the *brief*, not the map.

---

## Non-blocking findings

### 4. The committed map IS affected by the parked-EKF drift — measured in the artifact, not inferred

The brief asked whether the committed map inherits the ~0.0023 rad/s
parked heading integration. **Yes, measured here: ~2.0 deg of rotation
from the building** (finding 1's wall fits), from the ~20 s between
bringup and drive plus the pre-anchor gap — consistent with 0.13 deg/s
over that window. Scale: 8 deg/min of idle; the discarded four-minute-idle
map at ~20 deg confirms the slope. The committed map's rotation is *within*
what the recorded procedure ("drive promptly", evidence §8) intends, and a
SLAM map's frame is legitimately its own — AMCL localises in it without
caring. It is non-blocking **only if** finding 1's registration is done;
unregistered, it is the mechanism behind the blocking problem. Two
residual points: the mitigation is procedural (a sentence in §10),
enforced by nothing; and every rebuild draws a new random rotation, so
nothing downstream may ever hard-code this map's angle.

### 5. The 0.014 m final error is the run's least informative number and should not lead the AMCL evidence

The route is a closed circuit; the final sample sits at the anchor point,
where single-sample anchor rotation error (finding 2) contributes ~zero by
geometry; and closures 7–10 fired at t ≈ 162–163 s pinning precisely the
end-of-run chain onto the start-of-run chain, 15 s before the end
(evidence §6). 0.014 m therefore measures "loop closure closed the loop at
the point everything is anchored to" — near-tautology. The rms (0.185 m)
and max (0.358 m) are the load-bearing statistics, they are present and
correctly computed as drift-since-start, and the evidence pairs them with
the final figure rather than hiding them — so this is a headline-ordering
finding, not an integrity one. The AMCL evidence must not inherit the
pattern.

### 6. The recorder pairs latest-with-latest, not stamp-with-stamp

`cmd_record` (mapping_evidence.py lines 232–266) writes the most recent
truth *message* against a tf lookup at `Time()` (latest). At 0.80 m/s a
20–40 ms skew is 16–32 mm folded into every moving sample — small against
0.185 m, but it is instrument floor, and `agv/forklift/EVIDENCE_ODOMETRY.md`
§6 records both the correct technique (record stamped, pair afterwards)
and why. If the AMCL brief wants a tighter number, the recorder needs the
same treatment.

### 7. Housekeeping verified, one gap

Verified here: all four artifact md5s match the evidence doc;
`.gitattributes` now carries `*.posegraph -text` and
`sim/maps/**/*.data -text` (commit `db9d54b`), so report open question 1
is already resolved and can be closed in TODO; the deleted
`sim/scenarios/maps/` has no remaining consumers that run. The gap: as
noted under finding 1, the run's CSV/logs were not preserved, so the
evidence is testimony plus the artifact — adequate this time only because
the artifact could be re-measured.

---

## Attacks that failed, shown

Per the brief's rule that "sound" is only acceptable with the failed
attacks on display:

- **The artifact metadata (attack 4).** Verified against the committed
  files and `warehouse.sdf` independently: P5, 614 × 421, maxval 255;
  `resolution: 0.050`; `mode: trinary`, `negate: 0`, thresholds
  0.65/0.196 — the nav2 map_server/AMCL defaults; origin
  `[-9.596, -4.803, 0]` is the lower-left corner in the *map* frame,
  which is the convention AMCL expects (the 0 yaw is correct — the map's
  rotation from the *world* does not belong in this file). Origin
  placement reconciles with the map frame sitting at the vehicle's start
  pose: hall extent from world (−6.009, −5.500) rotated ~2 deg lands the
  lower-left corner where the yaml says. **Interior span, measured here
  perpendicular to the fitted walls: 30.046 m east-west against a true
  30.00 m — inside one cell**, confirming the evidence's span check by an
  independent method (its cos-correction used the wrong angle, 2.82 deg
  for ~2.0 deg; the effect is 0.01–0.02 m and changes nothing).
- **Mast ghosts in the grid.** `min_laser_range: 0.10` does admit the
  vehicle's 9 mast rays into the map input. Attack: looked for a trail of
  self-returns along the driven path. Found 219 small occupied clusters
  (118 single cells); sampled locations fall *inside the racking* — the
  partially-observed structure behind empty west bays the evidence's §9
  wedge explanation predicts — not along aisle centrelines. No trail. The
  attack failed.
- **The parameters (attack 5).** Each of the six non-defaults traces to a
  measurement that predates the run: sensor limits from `model.sdf`
  (0.10/8.00), node gating from the 10 Hz sensor and the basin widths in
  `WAREHOUSE_LANDMARKS.md` §5, buffer length from the 8 m horizon,
  `loop_search_maximum_distance` 6.0 from the 5.21 m of
  `EVIDENCE_ODOMETRY.md`. The flattering knobs — correlation windows,
  penalties, response thresholds — are all at shipped defaults, and the
  file says which run property would have exposed tuning (the 6.0 bought
  nothing; error never exceeded 0.358 m). The stated hole — aliasing
  untested between 3 m and 6 m (`slam_toolbox_warehouse.yaml` lines
  170–177) — is guarded by default response thresholds and no false
  closure appeared (largest map->odom step 0.166 m against a 2.30 m bay
  pitch signature). Nothing here contradicts the no-tuning declaration.
- **The transform story (attack 6).** The shape of the claim is right and
  was captured, not asserted: one publisher/one edge with the bringup
  alone; +2 publishers *both* named slam_toolbox with SLAM up; the edge
  set grew by exactly the disjoint `map -> forklift/odom`
  (evidence §3). The lifecycle trap is documented in three places and the
  launch emits configure/activate with an `OnStateTransition` handler
  (`warehouse_slam.launch.py` lines 145–172); the stated success check is
  `/map` appearing, not a clean log. The invariant-10 note that later
  checks must count edges, not publishers, is correct and worth keeping.
- **The route as hidden circularity (attack 3).** The driver publishes
  exactly two raw joint-command topics and subscribes truth only for
  path-following; no truth reaches an estimator; the evidence states, in
  four places, that the run is not M4 command-path evidence, and no file
  claims otherwise. What the route cannot show — a human's wander, entry
  with a degraded prior, dwell, reversing, other speeds — is finding 3's
  substance and is already conceded in §11.
- **The loop-closure count.** One Ceres solve per `CorrectPoses` per
  successful `TryCloseLoop` is slam_toolbox's actual call structure; the
  count is of printed lines; the clock mapping is a centred least-squares
  fit whose numerical trap (uncentred epoch arithmetic) the tool itself
  documents; the deserialize-verification solve is excluded by the route
  window and reported as excluded. Sound.
- **The EKF numbers' internal consistency.** 4.295 m / +23.64 deg over
  179 s reconciles with the declared 0.002618 rad/s bias
  (0.0026 × 179 s ≈ 27 deg, sign drawn positive this run) and with the
  two parked segments agreeing at ~0.0023 rad/s; the previous route's
  −17.18 deg was a different route, duration and drawn sign. No
  contradiction.

## Method note

All grid measurements in this review: parse the committed PGM directly
(stdlib only), classify cells (0 occupied / 205 unknown / 254 free —
histogram 6 490 / 64 081 / 187 923), take extreme occupied cells per
row/column, least-squares fit the four longest lines, and measure spans
perpendicular to the fitted walls. Fit residuals 0.32–0.71 px confirm the
lines are walls, not noise. Nothing was launched; the forbidden list's
measurement clause was not needed.
