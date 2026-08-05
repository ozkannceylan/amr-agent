# m5-38 — why the vehicle leaves a straight corridor, and whether it can be removed

    brief:               the m5-38 dispatch prompt (no file in docs/briefs/)
    status:              done — cause found, named and proven at three
                         independent levels; removability demonstrated over
                         five repeats. The fix is NOT applied, and that is a
                         decision requested, not an omission.
    files_changed:
      - agv/forklift/EVIDENCE_NAV2.md              (new section 11; sections
                                                    0-10 byte-identical, one
                                                    append-only diff hunk,
                                                    527 added / 0 deleted)
      - agv/forklift/scripts/steer_bench.py        (new) the plant harness
      - agv/forklift/evidence/m5-38-steer-bench-{a,b,c,d,e}.{csv,txt}  (new)
      - agv/forklift/evidence/m5-38-a_straight-r{1..5}-*               (new)
      - agv/forklift/evidence/m5-38-offline-cross-track.txt            (new)
      - agv/forklift/evidence/m5-38-exp-model.diff                     (new)
      - docs/reports/m5-38-cross-track-diagnosis.md                    (this)
    invariants_touched:  none. Everything measured or written is inside
                         agv/, below the smoother, in the process command
                         chain. No safety path, no tolerance, no layer
                         boundary, no dependency. plc/ and bridge/ were not
                         touched.
    open_questions:      five, listed below
    next_suggested:      one brief that RULES on applying the one-line plant
                         change and, if applied, re-qualifies the committed
                         motion evidence — not another arrival brief

---

## 1. The answer, in one paragraph

**The steer axis has no proportional authority over the tyre's reaction
moment at small angles.** `model.sdf`'s steer PID gives `6000 · e` N·m and
its own comment records the tyre's scrub reaction as "roughly 400 N m for
this vehicle", so the proportional term only breaks it above
`e = 400/6000 = 3.8 deg`. Below that the joint moves only as the integral
winds up, which takes of the order of **ten seconds**. RPP's corrections on
a straight leg are **1 to 2.5 deg** and the leg lasts **8 to 9 s**, so the
vehicle executes essentially none of them: **a straight leg is open-loop in
yaw.** Whatever heading error it enters with is HELD, and a held heading
error integrates into cross-track at `sin θ` per metre — 0.10 m/m at the
5.7 deg the failing runs held. The drift **can** be removed; the lever is
the one number that sets the threshold.

## 2. The sign, which the brief asked for first — and it halved the search

**The sign is not consistent: 6 negative, 4 positive over the ten committed
runs, mean 0.71 standard errors from zero against a mean magnitude of
0.084 m/m.** That killed the entire bias family in one measurement — no
steer trim, no estimator heading bias, no converter sign asymmetry, no
left/right model asymmetry can produce a reproducible magnitude with a
coin-flip sign. It reframed the question from "what is pushing the vehicle
off the line" to **"why does the correction not bring it back"**, which is
where the cause actually was.

## 3. Three independent measurements, one number

| level | instrument | result |
|---|---|---|
| **the ten committed Nav2 runs** | achieved steer inferred from ground-truth yaw, pooled, lag identified by sweep | `ach/cmd` = 1.00 above 15 deg, **0.03 at 1.2 deg**, 0.31 at 2.0, 0.82 at 3.1 |
| **the plant, directly** | `steer_bench.py` on the model's own command inputs, reading the steer joint out of `/forklift/joint_states` | a 2 deg step **held 14 s** reaches 1.66 deg and is still climbing; body follows joint to **1 %**, so tyre slip is exonerated |
| **`model.sdf`'s own arithmetic** | 400 N·m scrub / `p_gain` 6000 | predicted knee **3.8 deg**, integral windup **7.6 s** at a 2 deg error |

The mechanism was isolated by **a one-variable A/B on grip**, which is the
part of this worth keeping: `sim/worlds/forklift_arena.sdf` gives the drive
wheel no traction (5.000 rad/s commanded, 0.005 m/s achieved) while the
warehouse drives at 0.600 m/s. Same model, same gains, same hold, same
sequence: **without grip the axis reaches every commanded angle including
0.5 deg inside 1.4 s; with grip it reaches none of the small ones.** The
resisting moment is contact-borne, not the joint's own damping and not the
controller.

**Why nine sections of diagnosis missed it.** It sits two stages below the
envelope gate, between a steer angle command and a steer joint. Nothing
above the converter can observe it — which is exactly why the gate's
pass-through residual of zero was never in tension with it.

**Why every previous lever failed, and none could have worked.** Staging
(§9) fixed the entry heading, which the deadband then holds instead of
correcting. Lengthening the leg (§10) added metres to an open-loop
integrator. Widening a tolerance (refused twice by the owner) would have
accepted the error. §10.5's puzzle — the worst staging heading arriving
clean and the best missing by 17 deg — is precisely what an open-loop leg
predicts.

## 4. Removability, proven the way the brief specified

`p_gain` 6000 → **60000** moves the threshold to 0.38 deg, below every
command RPP forms on a straight leg. It is the gain `model.sdf` already
gives the mast joint, so the model's gains stay in one family. On the bench
a 2 deg command goes from **5 % executed to 76 %** inside 1.4 s, with no
hunting at the stops.

**Five repeats, same route, same protocol as §8-§10, one variable against
§10** (the harder `d = 4.5` geometry, deliberately):

| criterion | result | verdict |
|---|---|---|
| ≥ 4 of 5 clean | **5 of 5** | **MET** |
| no shuffle regime | **0 of 5**, and *not* by construction — no miss abort fired | **MET** |
| localization max ≤ 0.263 m | **0.1523 m** worst (0.0718 / 0.1068 / 0.1082 / 0.1315 / 0.1523) | **MET** |

Entry headings −3.34, +2.23, −2.19, −0.57, +1.86 deg, against §10's +17 to
+33. Zero go-arounds against §10's four.

**The measurement that matters more than the outcome column** is the rate
itself, because an outcome column could be luck and this cannot: mean
|cross-track rate| falls from **0.0791 / 0.0893 m/m** (§9 / §10) to
**0.0134 m/m**, and terminal cross-track collapses from a 1.13 m scatter
across ten baseline runs to **+0.028 to +0.056 m** across five. And r1 is
the row that proves the loop is closed rather than merely quiet: it began
its leg at **+0.174 m** and *converged* to +0.048 m. **Under the committed
plant no run ever converged** — the error only ever grew.

## 5. Applying it is a separate decision, and this is the request

**`agv/forklift/model.sdf` is byte-identical**; line 1002 still reads
`<p_gain>6000.0</p_gain>`, verified after the last run. The experiment ran
from a `/tmp` copy differing by one diffed line, passed with `model:=` —
the §8.4 pattern, evidence rather than an applied change. Three reasons,
the first binding:

1. **`model.sdf` is the vehicle plant and every committed motion figure in
   `agv/` and `sim/` is qualified by it** — `EVIDENCE_ODOMETRY.md`,
   `EVIDENCE_LOCALIZATION.md`, `EVIDENCE_NAV2.md` §1-§10, the arena and
   warehouse evidence, and the recorded M4 commissioning showcase. Applying
   this inside a diagnosis brief would silently re-qualify all of them.
2. The gains it changes are recorded in `model.sdf` as **measured**, with a
   documented instability at the opposite end. A ten-fold change deserves
   its own bracketing.
3. A plant change is cross-layer and this agent owns one layer; `sim/`
   re-measures against this model and does not know it moved.

**The honest options for the ruling**: (i) apply and re-measure the
affected evidence, (ii) apply and mark the affected figures as taken on the
prior plant, or (iii) leave it and accept the arrival distribution.

## 6. Files outside my scope that this work needs — requested, not created

- **`sim/`**: the arena floor gives the drive wheel **no traction**
  (5.000 rad/s commanded against 0.005 m/s of travel, measured twice).
  Every `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` figure involving traction,
  steering effort or tyre behaviour is qualified by this, and it should be
  ruled on by the agent that owns the world.
- **`sim/`**: if the plant change is applied, `warehouse_bringup.launch.py`
  should forward a `model` argument explicitly rather than relying on the
  unscoped launch configuration this brief exploited.
- **`docs/LESSONS.md`** (I cannot write it), three entries earned here:
  - *2026-08-05 | A drift of 0.10 m per metre on a straight line was hunted
    as a bias — a steer trim, an estimator offset, a converter sign
    asymmetry | The signed rate was 6 negative and 4 positive over ten runs
    with a mean 0.71 standard errors from zero, so no bias could produce
    it; the reproducible quantity was the MAGNITUDE, and the cause was a
    symmetric deadband that amplifies a disturbance instead of injecting
    one | Establish the SIGN of a drift before its magnitude: a consistent
    sign is a bias and a coin-flip sign is a lost correction, and the two
    have disjoint cause families.*
  - *2026-08-05 | The vehicle's failure to turn was attributed to the
    controller, the estimator and the Twist conversion in turn, all of
    which measured clean | The loss was in the plant, between a steer angle
    command and a steer joint: proportional authority 6000·e against a
    400 N·m tyre scrub, so nothing under 3.8 deg executed and a straight
    leg — the only regime whose commands all sit under it — was open-loop
    in yaw | When a controller's small corrections have no effect, measure
    the actuator's static curve against the load it works into before
    tuning anything above it; a plant that executes large commands
    faithfully proves nothing about small ones.*
  - *2026-08-05 | The steer joint's tracking was measured in the arena and
    came out unity at every angle, half a degree included | The arena floor
    gives the drive wheel no traction at all — 5.000 rad/s of wheel against
    0.005 m/s of travel — so the axis was being measured with its load
    disconnected, and the same measurement in the warehouse collapsed to
    3 % | An actuator is characterised against the load it actually works
    into; a bench that removes the load measures the actuator's ceiling and
    calls it its behaviour. The accident became the controlled A/B that
    named the cause, but only once the missing traction was noticed.*

## 7. Discipline

No commit, no branch; the working tree carries the changes for the
orchestrator's pathspec. **Sections 0-10 of `EVIDENCE_NAV2.md` are
byte-identical** — `git diff -U0` produces exactly one hunk,
`@@ -1896,0 +1897,527 @@`, 527 added and **0 deleted**. The dated §11 with
all its headings was written **before the first run**, and every run's row
was appended the moment that run existed, before the next was launched.

**No tolerance was widened.** `xy_goal_tolerance: 0.25` and
`yaw_goal_tolerance: 0.15` are untouched. No dependency was added,
`opennav_docking` was not activated, and `plc/` and `bridge/` were not
touched — the modifications standing in `plc/` were there at session start
and are the owner's.

**Measured alone, enforced rather than remembered.** Every run refuses to
start unless the process-pattern count is zero, prints load, `/dev/shm`
count and a UTC timestamp, gates each bring-up stage on a topic appearing,
and verifies the count after teardown. All five route runs and all five
bench runs started at zero and ended at zero. `GZ_PARTITION` **and**
`ROS_DOMAIN_ID` were isolated on every run. Per-run starting load is
recorded in §11.7 as the one uncontrolled between-run difference; it does
not order the outcomes.

## 8. Open questions

1. Whether to apply the one-line plant change, and which of the three
   re-qualification options in §5 to take. This is the ruling the next
   brief needs.
2. Whether `d` returns to 3.0 in the same round. §10.6 item 2 stands; 4.5
   was used here only to keep the comparison one variable.
3. Whether `p_gain` 60000 is the right value or merely a sufficient one.
   It was derived from `model.sdf`'s own 400 N·m figure and confirmed by
   measurement, but no upper bracket was taken — the stability ceiling is
   inferred from the absence of hunting at ±20 deg, not from a sweep.
4. Whether the residual collapse below 0.5 deg (still 0.09-0.23 of
   commanded after the change) matters. At 0.009 m/m it is a twelfth of the
   failing rate, but it is a floor and nobody has asked what depends on it.
5. The go-around's `"Start occupied"` precondition and the inflation-radius
   warning are untouched and remain open. Neither fired here, because no
   run needed a go-around — which is not the same as either being fixed.
