# Report m5-07e — the leak is the steer axis, and the test was the wrong shape

```
brief:               docs/briefs/m5-07e-gate-leak.md
status:              done
files_changed:       agv/forklift/scripts/wheel_odometry.py
                     agv/forklift/scripts/check_odometry.py
                     agv/forklift/config.yaml
                     agv/forklift/ekf.yaml          (comment only)
                     agv/forklift/scripts/imu_gate.py (comment only)
                     agv/forklift/launch/vehicle.launch.py (comment only)
                     agv/forklift/README.md
                     agv/forklift/EVIDENCE_ODOMETRY.md   (new section 13)
                     agv/forklift/evidence/              (new directory:
                       two gzipped per-sample series and five verbatim
                       harness logs, before and after)
                     docs/reports/m5-07e-gate-leak.md
invariants_touched:  none. Invariant 10 again shaped the split: the
                     standstill verdict is still formed by the node that
                     owns the encoder model and by no other, and the
                     harness's ground-truth reference is reported in its
                     own section and enters no verdict
open_questions:      six, below
next_suggested:      the AMCL dwell brief can be written; budget 0.33 deg
                     of estimator heading if the dwell begins at the stop
                     and 0.00 deg if it begins more than 16 s after it
```

## The number the brief asked for

**A 220 s post-drive idle, seed 1, same world, same profile, same stop.**

| | before | after |
|---|---|---|
| fused heading over the whole idle | **−2.1110° / 209.97 s** | **−0.6585° / 219.98 s** |
| **over the idle after t+20 s** | **−0.8550° over 190 s (−0.2701 °/min)** | **+0.000000° over 200 s** |
| gyro samples admitted after t+20 s | 647 | **0** |
| suppressed | 93.14 % | 98.47 % |

The last gate opening of the run ends at **t+15.414 s**. For the
following 204.6 s no gyro sample reaches the filter and the fused heading
does not move at all.

**The leak changed kind, not only size.** It was a rate that grew with
how long the vehicle stood there. It is now a fixed cost paid once per
stop, inside the first sixteen seconds, and nothing afterwards — a
two-minute dwell and a twenty-minute dwell cost the same.

## The mechanism, and it is not the axis m5-08d named

Four candidates, one measurement each (`--phase postidle`, which drives
`_PROFILE` and then records the idle at full rate):

| candidate | measurement | verdict |
|---|---|---|
| the gate's freshness window lapsing | largest verdict gap **0.0300 s** against a 0.2000 s timeout | **OUT** |
| the EKF integrating a stale twist | **0.6 %** of the heading change accrued with the gate closed and settled; **97.8 %** with a gyro sample actually being fused | **OUT** as the mechanism |
| the 0.50 s arming window at the stop | first burst ends at t+0.806 s and cost −0.3290°; the remaining 209.2 s cost −1.7820° | **IN, 16 %**, and fixed per stop |
| encoder counts still settling | below | **IN — the STEER axis** |

**The drive encoder is not dithering; it is not moving.** All 144 of its
count changes are inside the first **0.296 s** — the vehicle coasting to
a stop. Over the next 209.7 s the count does not change once and its
sub-count residual holds to **3.842e-9 of a count**. m5-08d's stated
hypothesis is ruled out by direct measurement.

**The steer axis relaxes after a drive.** It swept 27 counts (2.373°)
across the idle: a 4.1 s transient at t+11.3 s, then **isolated single
counts roughly every eleven seconds**. Of 20 bursts of encoder activity,
**19 were started by the steer axis and one by the drive**. Each single
steer count discarded however long the vehicle had been standing and
re-opened the gyro gate for a fresh 0.50 s window. The arithmetic closes
to the measurement within 1 %.

**Why m5-07d's idles were clean:** at bringup every joint sits exactly at
its spawn value under no load, so neither axis moves. The steer term's
cost was invisible for exactly as long as nobody drove first.

## The defect is the shape of the test

The old verdict asked whether both counts had been unchanged **since a
reference instant that receded for as long as the vehicle stood**. That
is a statement about total displacement over an unbounded interval, and
no axis of a real machine satisfies it for ever. What the consumer needs
at each sample is *"the body is not rotating now"* — a **rate**.

Replaying the recorded counts through candidate rules showed the obvious
fix does not work: a ±1 or ±2 count **band** only reaches −0.349 / −0.269
°/min, because a band absorbs dither and this is monotonic creep, which
walks out of any band. Making the window trailing while keeping exact
equality changes nothing at all (−0.615 °/min, i.e. no change).

**What was implemented.** `StandstillWindow`, at module scope with no ROS
in it, testing the **spread of each count over a trailing 0.50 s
window**:

- **drive: spread = 0.** This *is* the bound — `|Δψ| ≤ (tread)/L` holds
  precisely because the count did not change. Its tolerance is a module
  constant, `DRIVE_TOLERANCE_COUNTS`, and not a `config.yaml` entry,
  because N counts of tolerance multiply the permitted body rotation by
  (N+1) and one count would let the gate hide **2.4 °/min of real
  rotation**.
- **steer: spread ≤ 1 count.** A rate guard, carrying no bound. The
  tolerance is **the one count of zero uncertainty `config.yaml` already
  declares for that encoder** — a calibration cannot resolve the steer
  zero better than one count, so demanding the reading be *identical*
  asks the axis to hold to a precision the vehicle's own model does not
  claim. It permits 0.176 °/s, against the axis's declared maximum of
  2.0 rad/s and a measured relaxation of 0.09 counts/s.

The threshold is derived from the encoder's stated calibration limit and
from nothing in the measurement it improves.

## The honesty rules, kept and checked

- **No bias is estimated and nothing is carried into motion.**
  `StandstillWindow` holds encoder counts and timestamps and no gyro
  quantity of any kind.
- **`model.sdf` md5 is byte-identical** to the one m5-07c and m5-07d
  recorded. Every datasheet noise figure is untouched. No covariance, no
  `process_noise_covariance`, no `initial_estimate_covariance` moved;
  `ekf.yaml`'s parsed parameters are unchanged and its edit is comment
  only.
- **No ground truth reaches an estimator.** `--phase postidle --truth` is
  a harness flag, off by default, reported in its own section, entering
  no verdict. Sections 2–6 of the phase are identical with and without it.
- **Moving drift unchanged, re-shown on the same profile**, both runs
  taken **in this session** — the before-run from a scratch tree holding
  `git show HEAD:` versions of the three changed files, so the two differ
  in the standstill rule and nothing else:

  | | before | after |
  |---|---|---|
  | drift while moving | **−12.8941° over 110.76 s** | **−12.7800° over 110.74 s** |
  | gated gyro samples during the route | 11 077 of 12 100 | 11 076 of 12 100 |

  The difference is **0.1141°** against a white-noise random walk of
  `1.745e-3·√(0.01·110.74) = 0.1052°` — **1.08 σ**, and one gyro sample
  in 12 100 differs between the runs.

- **The verdict is now exercised with no simulator.** `--phase static`
  section 6 drives `StandstillWindow` through eight count series
  including the defect itself; the phase goes from 23 to **31 checks, 0
  failed**. The old defect cost a 210 s live run to find.

## The residual, bounded

| | |
|---|---|
| dwell beginning at the stop command | **−0.331° of estimator heading error**, all inside the first 16 s, then flat |
| dwell beginning >16 s after the stop | **0.000°**, measured over 200 s |
| for a two-minute AMCL dwell | **at most 0.33°**, and 0.00° if it does not begin in the settling window |

All of the residual is the steer axis's relaxation transient at t+11.5 s
to t+15.4 s, where the axis moves at up to 3 counts per window
(**0.53 °/s**) and correctly exceeds the rate tolerance. It was left
there deliberately: half a degree per second **is** motion, opening for
it is the conservative direction, and a tolerance chosen to swallow it
would have been a number fitted to make the table look better.

Ground truth also shows the first 0.804 s is not all error: the vehicle
**coasts 0.138 m** after the stop command and genuinely turns −0.2196°
doing it, so of that burst's −0.3326° only **−0.1130°** is the estimator.

## The steer term's premise, measured

Recorded as a reference, in its own section: over the post-fix idle the
steer axis swept **2.3730°** with the drive count held, and the body
moved **0.001568 m** and turned **0.001750°** — three orders of magnitude
smaller, at the floor of what the reference resolves. The kinematics say
why: the steer axis passes through the wheel centre, so rotating the
wheel about it translates the contact point by zero.

**That is not a licence to delete the term**, and it was not deleted. It
says nothing about a real tyre with a finite contact patch, and the
failure it was named for is not the one it detects: a vehicle towed or
pushed bodily rotates with **both** counts held, and no encoder on this
machine sees that at all.

## Open questions

1. **One stop, one posture, one seed.** Flat ground, forks down, steer
   commanded straight, `--seed 1`. The steer relaxation's size, and the
   16 s it lasts, are properties of *this* stop. A stop out of a turn, on
   a ramp, or with a raised load rocking on the tyres is not measured,
   and the "0.33° per stop" bound is a measurement of one of them.
2. **The residual is bounded and located, not removed.** If the AMCL
   dwell criterion turns out to need better than 0.33° at a dwell that
   begins immediately after a stop, the lever is the steer relaxation
   itself — the steer controller's gains in `model.sdf` — and that is a
   change to the vehicle model, not to the gate. It should be a decision,
   not a side effect.
3. **The steer term is now explicitly a guard with no bound behind it.**
   Whether a term that neither bounds body rotation nor detects the skid
   it was named for should be in the verdict at all is a design question
   this brief deliberately did not settle unilaterally. Removing it
   measures −0.034 °/min on this data, against −0.180 °/min as shipped.
4. **Gross drive-wheel skid is still the one credible way the mechanism
   is wrong** (m5-07d open question 2). Unchanged, untested, and the
   steer term never covered it.
5. **`sim/` still cannot bring this stack up.** `sim/launch/
   forklift_bringup.launch.py` has no IMU bridge, no wheel odometry, no
   EKF and no `imu_gate` (m5-07c OQ 3, m5-07d OQ 5). It now also needs
   the `standstill.steer_tolerance_counts` key if it ever loads a copied
   `config.yaml`. `agv/forklift/launch/vehicle.launch.py` is the working
   reference. The `/forklift/odom` → `/forklift/odom_ground_truth` rename
   request also still stands.
6. **Container only.** Every figure here is from the project session
   container. The owner's WSL2 host has never run this configuration.

## Notes

- **Nothing outside `agv/` and this report was written.** No commit, no
  staging, no branch. The orchestrator commits by pathspec; the new
  directory `agv/forklift/evidence/` needs adding explicitly.
- **The two per-sample series are gzipped** (14 MB → 2.3 MB). Both
  writers were confirmed gone before compression, never compressed under
  a live writer (LESSONS 2026-07-28); each run wrote its own uniquely
  named CSV, none shared a path. `.gitattributes` already carries
  `*.gz -text`.
- **No dependency was added.** `collections` is in the standard library.
- Runs were isolated on **both** transports (`GZ_PARTITION` and
  `ROS_DOMAIN_ID`, unique per run), headless, driven to completion in the
  foreground with bounded polling, and every process confirmed gone with
  `pgrep -af` after each. Measurement runs were **serialised**, never
  concurrent (LESSONS 2026-07-30). **No RTF figure was taken and none is
  quoted.**
- The full evidence, with every table above in its raw form, the replayed
  rule comparison and the reproduce recipe, is
  `agv/forklift/EVIDENCE_ODOMETRY.md` section 13.
