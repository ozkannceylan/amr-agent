# Report m5-08e — AMCL against the frozen map, measured absolutely

```
brief:               docs/briefs/m5-08e-amcl-localization.md
status:              done
files_changed:       agv/forklift/amcl.yaml                    (new)
                     agv/forklift/launch/localization.launch.py (new)
                     agv/forklift/scripts/localization_run.py   (new)
                     agv/forklift/EVIDENCE_LOCALIZATION.md      (new)
                     agv/forklift/evidence/                     (29 new files:
                       five run recordings, their leg marks, the captured /tf
                       publisher lists, and both scorers' verbatim output,
                       plus the parked baseline)
                     agv/forklift/README.md                     (What is here)
                     docs/reports/m5-08e-amcl-localization.md   (this file)
                     NOTHING outside agv/ and this report. sim/ was read and
                     run, never edited. Nothing staged, nothing committed.
invariants_touched:  none. Invariant 10 shaped three decisions: the map and
                     its registration keep one owner and are consumed read
                     only; the world->map transform is reached through
                     register_map.py rather than parsed or copied; and AMCL
                     becomes the SOLE publisher of map -> forklift/odom
                     beside the EKF's sole ownership of
                     forklift/odom -> forklift/base_link
open_questions:      eleven, in EVIDENCE_LOCALIZATION.md section 10. The
                     load-bearing ones: the 0.141 m floor swallows 74 % of
                     the route run and every reverse figure; m5-07e's 0.33°
                     per-stop bound is EXCEEDED at this stop (+0.539°, 1.6x)
                     while its 0.000°-after-16 s half is confirmed exactly;
                     and two requests to sim/ (a launch-ordering race in
                     warehouse_slam.launch.py, and no seed argument on
                     warehouse_bringup.launch.py)
next_suggested:      Nav2 planning and control over this localization
                     (m5-10), or a seeded A/B of the reverse traversal once
                     the bringup carries a seed argument
```

---

## The four measurements, each beside the 0.141 m floor

| | measurement | headline | vs floor |
|---|---|---|---|
| **(a)** | steady state, full committed mapping route, 107.68 m / 179.0 s | **rms 0.124 m**, max **0.263 m**, final 0.093 m | rms **at the instrument's resolution**; max 1.9 × floor and a real measurement |
| **(b)** | convergence from a prior **1.166 m and 10.000° wrong** | at/below the floor after **13.81 m** driven; **final 0.007 m** | **converged to the instrument's resolution** |
| **(c)** | DWELL, **128.7 s** stationary in East A | before **0.289 m**, during mean **0.282 m**, after exit **0.348 m**, **growth over the dwell −0.007 m** | 2.0–2.6 × floor throughout; the growth is **below the floor** |
| **(d)** | REVERSE, East A **fork first**, 8.52 m | **rms 0.053 m**, max **0.105 m**, final 0.079 m | **every figure at the instrument's resolution** |

No figure at or below 0.141 m is quoted as a smaller number anywhere; the
tool substitutes the phrase "at the instrument's resolution" itself, so the
rule cannot be applied inconsistently by a reader. Every figure is scored
**absolutely** through the committed `warehouse_registration.yaml` with **no
per-run anchoring**; the grid md5 was verified by
`register_map.load_registration()` on every scoring pass, and no
registration/map mismatch occurred.

**Both scorers agree on all five recordings.** `sim/scenarios/tools/
mapping_evidence.py analyse --score absolute` and
`agv/forklift/scripts/localization_run.py analyse` implement
`p_world = R(−θ)(p_map − t)` independently and return identical rms, max,
final and final heading for every run.

## The dwell, with the estimator's own bound beside it

AMCL made **one** correction in the 130 s dwell — at stop + 0.18 s, while
the vehicle was still coasting — and **none at all** once the vehicle was
truly at rest: `map -> forklift/odom` holds **one single distinct value**
for 128.7 s. That is `update_min_d: 0.25` behaving exactly as documented,
and it means every millimetre of pose movement during a dwell arrives from
underneath AMCL.

Apportioned over the window `m5-07e` states its bound for (from the stop
command, 130.0 s):

```
total heading, map -> base_link      -0.1796 deg
of which AMCL, map -> odom           -0.7185 deg  (0.1353 m, 1 correction)
of which the EKF, odom -> base_link  +0.5389 deg  <- WHAT AMCL WAS HANDED
real body rotation, ground truth     +0.0003 deg
```

| | m5-07e bound | measured here |
|---|---|---|
| EKF heading from the stop command | **≤ 0.33°** | **+0.539° — EXCEEDED, 1.6 ×** |
| EKF heading from stop + 16 s onward | **0.000°** | **+0.0000° over 114.0 s — confirmed exactly** |
| where the cost lands | inside the first 16 s | **all of it by stop + 1.07 s** |

Reported as measured rather than reconciled. `m5-07e` open question 1
already scopes 0.33° to one stop; this is a different stop (0.80 m/s
straight-line, different world, fresh bias draw) and it cost 1.6 × as much.
A **second, independent instance in the same run** corroborates the size:
the profile's final stop cost the EKF **+0.548°**, again with zero AMCL
corrections. **The bound should be restated as a range over stops or
re-derived — a request to whoever owns it, not a change made here.**

Position-wise the dwell cost nothing measurable: **0.289 m entering,
0.282 m leaving, 128.7 s later**, a change of −7 mm which is below the
floor. What puts the vehicle 0.28 m out is *getting* to East A, not
standing in it.

## The reverse test

Fork first **is** backwards on this vehicle (`model.sdf`: +x is the drive
end; the mast sits at x = −0.78). The asymmetry is not the scan's field of
view — the lidar returns 360° — but the two mast rails, which span
z = 0.05…2.05 m and so cut the sensor's own z = 1.80 m plane, blanking
**9 of the 360 rays** in two arcs at +149.90…+154.53° and
+173.56…+177.71°, all pointing backwards, in an aisle where ten rays or
fewer carry all the along-aisle information.

A **forward control** was added and run — the exact mirror, same 8.52 m of
the same aisle at the same 0.60 m/s, same heading, same exact prior, 84
scored samples each — because the committed route's East A pass runs at
0.80 m/s after 75 m of driving and so cannot separate direction from
history.

| | REVERSE (fork first) | FORWARD control |
|---|---|---|
| rms / max / final | **0.053 / 0.105 / 0.079 m** | 0.118 / 0.176 / 0.176 m |
| East A along-x growth | +0.031 m | −0.094 m |
| EKF handed AMCL over the traverse | +0.356° | +2.921° |

**Every reverse figure is at or below the floor.** The claim that supports
is exactly *"driving East A fork first produced no measurable localization
penalty"* — not that reversing is better. The confound is named rather than
omitted: the bringup exposes no seed, the two runs drew different gyro
biases, and the forward pass was handed 8 × more heading drift to absorb.

## Two defects found, both with a reproduction

1. **`save_pose_rate: 0.0` bricks `nav2_amcl` silently.**
   `durationFromSec(1.0/0.0)` throws in the CONFIGURE transition; the node
   then sits UNCONFIGURED with no scan subscription, no `/amcl_pose`, no
   transform, and nothing in the log that reads as a localization failure.
   Reproduced in isolation with no simulator (0.0 fails, 0.5 configures).
   The property that value was for is bought with
   `always_reset_initial_pose: true` instead.

2. **A launch-ordering race that costs a run, silently.** Emitting the first
   lifecycle transition *before* registering the handlers that chain the
   rest — which is how `sim/launch/warehouse_slam.launch.py` is written —
   loses the transition event when a node configures faster than the launch
   can register the next handler. `map_server` configure is 26 ms; three
   runs chained and **the fourth stopped dead** after `Read map ...
   606 X 410`, with nothing in either log that reads as an error.
   `localization.launch.py` registers every handler before emitting
   anything: **6 of 6** clean lifecycle chains measured afterwards with no
   simulator, plus three full-stack runs.

## Method notes

- **Ground truth reaches no estimator.** It is in `amcl.yaml`: no. In
  `ekf.yaml`: no. In the launch: no. It is subscribed by the scorer, which
  writes a file and publishes nothing. The evidence states it is **exact**
  simulation truth, so every error figure is attributable entirely to the
  localization chain.
- **Neither safety scanner reaches AMCL.** One scan topic is named and it is
  the navigation lidar.
- **The motion model is `nav2_amcl::DifferentialMotionModel`**, written out
  and justified: a tricycle cannot translate sideways, and the omni model
  the retired RB-KAIROS needed would let particles do what this vehicle
  cannot. It is also the nav2 default; the file says that is a coincidence
  and not the reason.
- **The initial pose is a launch argument carried into the map frame**, not
  a ground-truth sample. The conversion lives in the measurement harness
  and deliberately **not** in the vehicle's launch, because a real forklift
  has no world frame. §4 of the evidence records the by-construction zero
  an exact prior produces before the vehicle moves, measured on a parked
  44.8 s baseline, so nobody reads it as a result.
- **The three profile drives subscribe to nothing at all** — no ground
  truth, no EKF, no `/amcl_pose`, no scan. They play a timed profile, so
  there is no feedback path of any kind from the run into the stimulus.
  Run (a) uses the committed route driver unmodified, which does close its
  loop on truth as its own header states, and which publishes only two raw
  joint commands.
- **Every AMCL non-default is recorded with one sentence**, and values equal
  to the nav2 default are recorded too, marked DEFAULT-KEPT, where the
  default shapes a measurement (`update_min_d`, `recovery_alpha_*`,
  `do_beamskip`, the alphas). **Nothing was tuned against a result**: every
  value was fixed before the first scored run from `model.sdf`,
  `config.yaml` or `WAREHOUSE_LANDMARKS.md`.
- **Isolation.** Every run headless, unique `GZ_PARTITION` **and**
  `ROS_DOMAIN_ID`, serialised — never two simulators at once — driven to
  completion in the foreground with bounded polling, every process confirmed
  gone with `pgrep -af` afterwards. No RTF figure was taken and none is
  quoted. `use_sim_time` is set in the params file and on both nodes from
  the launch, so neither mistake alone can leave a node on the wrong clock.
- **No dependency was added.** `nav2_amcl` and `nav2_map_server` are already
  installed in the toolchain; the harness is standard-library Python plus
  `rclpy` and `yaml`, both already used by this directory.

## Requests to other agents

- **To `sim/`:** move `warehouse_slam.launch.py`'s `EmitEvent` below its
  `RegisterEventHandler` actions. It carries the race above and has not been
  bitten only because `slam_toolbox`'s configure is slow — a timing
  accident, whose failure mode is a mapping run that maps nothing while
  logging nothing wrong.
- **To `sim/`:** give `warehouse_bringup.launch.py` a `seed` argument, as
  `agv/forklift/launch/vehicle.launch.py` already has. Without it no two
  runs against this world can be compared on the odometry they were handed,
  which is the confound in measurement (d).
- **To whoever owns the `m5-07e` dwell bound:** 0.33° per stop is exceeded
  at 1.6 × by a second stop. Restate it as a range, or re-derive it over
  more than one stop.
- **Standing, unchanged:** the `/forklift/odom` → `/forklift/odom_ground_truth`
  rename (`m5-07b`, `m5-07c`, `m5-07e`).
