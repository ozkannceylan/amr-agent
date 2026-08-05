# m5-34 — force the arrival heading inside the window

    brief:               docs/briefs/m5-34-arrival-heading-forcing.md
    status:              done — design delivered; no code written, no run taken
    files_changed:
      - agv/forklift/ARRIVAL-GEOMETRY.md   (new section 9, appended; sections 1-8 untouched)
      - docs/reports/m5-34-arrival-heading-forcing.md   (this file)
    invariants_touched:  none. Every change the design names is inside agv/,
                         below the smoother, in the process command chain;
                         nothing touches a safety path, a tolerance, or a
                         layer boundary.
    open_questions:      three, listed below
    next_suggested:      a build brief implementing ARRIVAL-GEOMETRY.md §9.6
                         verbatim — two file edits, one bench check, one
                         five-repeat run

---

## 1. The result, in one paragraph

All three m5-33 mechanisms are dispatched, two fixed and one converted into
the measurement it was missing, and both levers are derived rather than
chosen. The headline finding is mechanism 1: **the terminal stall is not a
plant property — it is a deadlock among three committed parameters**, and
the vehicle never received the 0.015 m/s at all. The closed-loop smoother's
from-rest ceiling is `max_accel × Δt` scaled by curvature
(min(0.025, 0.0238/κ) m/s), which at r1's recorded steer of 1.072 rad gives
0.0136 m/s — the recorded 0.015 — and that sits **below the converter's
0.02 m/s creep deadband**, so the converter publishes zero traction, the
plant never moves, the EKF measures zero, and the smoother stays pinned
forever. Every recorded symptom of r1 (steer held, traction zero, truth
frozen 20 s, refusal counter frozen at 5) is reproduced by this loop, and
the "minimum executable speed" the brief asked for is now a formula, not a
mystery: from rest the chain's floor at full lock is 0.0067 m/s, and the
creep deadband must sit below it. Fix: `creep_speed_mps 0.02 → 0.005`, the
admissible window derived (0.002 < creep < 0.0067).

## 2. The three mechanisms, each dispatched

1. **Terminal stall — FIXED** (§9.1). Deadlock derivation above, matched to
   r1 number by number; one derived line in `config.yaml`; bench-checkable
   in minutes before any simulator run; falsifier registered.
2. **Go-around returns with unconstrained heading — FIXED by capacity, not
   by a checker** (§9.2). A heading-checked return fails relation (A) by
   regress: satisfiability at staging needs yaw_tol < 0.25/R_endgame =
   0.096–0.119 rad, *tighter* than the 8.594° window the station leg cannot
   yet be forced inside. Instead the retry is provisioned: the measured
   worst return heading (−28.56°) needs d ≥ R·θ₀ + 2√(R·e₀) + lookahead =
   3.59 m, so d = 3.0 was under-provisioned by 0.6 m and the chosen
   d = 4.5 covers it with 0.9 m margin. The §9.1 fix is also load-bearing
   here — r1's go-around died of the same deadlock, not of heading.
3. **Lateral-by-construction — RULED OUT as a cause claim, converted into
   instrumentation** (§9.3). The lateral-offset inference is not
   resurrected (the brief's burden is a measurement). What follows from
   "lateral by construction" is only the S-curve term already inside the d
   formula. The genuinely missing measurement is named: the five-repeat
   table has **no staging-stop heading column**, so the entry-heading
   variance is unattributable; the build records it per run.

## 3. The levers, and which one the geometry favours

Lever 1 (constrain heading at staging) is executable only as a conjunctive
staging check, which the regress arithmetic above refuses; its geometric
form (arrive along the axis) is lever 2 applied one leg earlier, at the
same corridor cost with indirect benefit. **The geometry favours lever 2**:
d = 2√(R·e₀) + 2×lookahead = 1.34 + 3.20 → **4.5 m** — the tail sized at
two lookaheads instead of the 1.04 that d = 3.0 left after the S-curve.
Under the linearised pure-pursuit settling model (flagged as a model), the
extra 1.5 m attenuates entry-heading error by e^(−1.5/1.6) = 0.39: r4's
+16.94° maps to ≈ +7°, inside the window. Corridor check: it consumes
aisle length, not the 0.356 m lateral pinch budget; route A fits (staging
moves to (−3.5, +7.0) with the start at (−4.5, +7.0)); the general rule —
no 2.35 m pinch may overlap the ≈1.5 m S-curve zone after staging, where
lateral excursion reaches e₀ ≈ 0.35 m — is the fleet-placement constraint
§4.2 already hands to M6, unchanged by the longer d.

The miss branch is also completed (§9.5): m5-33 built the go-around but no
miss *detector*, which is why r4 shuffled 20 reversals to a lucky finish.
The harness aborts an approach at first circle entry outside 8.594° (the
5-of-5 discriminator) or at the second post-entry reversal (clean runs
measured 0–1; the shuffle threshold is 3), then go-arounds. Stated plainly
in the design so the pre-registered test is not gamed: this makes
"no shuffle regime" partly true by construction, which is design (ii)'s
explicit contract — an aborted run is scored NOT clean, so the ≥4/5
criterion can still fail honestly.

## 4. The prediction, registered before the run

Point prediction 5 of 5 first-approach clean; pass at ≥4 of 5. Per m5-33
run: r2/r3/r5-analogues clean with entries within ±6°; the r4-analogue
clean at ≈ +7° (this row is the settling model's test); the r1-analogue
shows no stall anywhere, and any residual miss aborts immediately and
completes via one provisioned go-around. Four falsifiers are registered in
§9.7, each naming the derivation it would kill. One build, one five-repeat
run: two file edits (`config.yaml` one line, `nav2_run.py stage` aborts +
staging-heading column), one invocation change (`--d 4.5`), one pre-run
converter bench check.

## 5. Scope and discipline

No code was written; no run was taken; nothing was committed and no branch
was created. `plc/` was not touched. No tolerance was widened —
`general_goal_checker` stays 0.25 m / 0.15 rad and the design adds no
heading check anywhere, having refused one by arithmetic. No dependency;
`opennav_docking` untouched. The one confound is stated in §9.4 rather
than left to be discovered: at d = 4.5 the staging leg on route A shrinks
to 1.0 m, so staging scatter will likely be smaller than m5-33's — the
per-run staging columns keep the comparison honest and d was sized for the
worst-case e₀ = 0.35 regardless.

## 6. Open questions

1. `creep_speed_mps` is read by the converter in every mode, not only
   under Nav2; the 0.005 value is derived for this chain's smoother
   parameters. If a later brief changes `max_accel` or the smoother rate,
   the §9.1 window must be re-derived — the comment the build writes into
   `config.yaml` should carry the formula, not just the number.
2. If a run enters outside 8.594° at d = 4.5, the settling model is
   falsified and the staging-heading column decides the follow-up: either
   the variance enters at staging (then the lever is the leg *into*
   staging) or it is generated on the leg (then it is a tracking
   question, likely the understeer-at-small-angles measurement §8 item 2
   already asks for).
3. `docs/LESSONS.md` (I cannot write it), one entry earned here:
   *2026-08-05 | A 20 s terminal stall was recorded as the vehicle
   possibly sitting below its breakaway speed at full lock | The plant
   had received zero all along: the closed-loop smoother's from-rest
   output (max_accel × Δt scaled by curvature) fell below the converter's
   creep deadband, which zeroed traction, which kept the measured twist
   at zero, which kept the smoother pinned — three individually correct
   parameters forming a permanent deadlock | When a command chain
   contains both a feedback-limited stage and a deadband stage, derive
   the feedback stage's from-rest floor and check it clears every
   downstream deadband; a plant that "does not respond" may be a plant
   that was never commanded.*
