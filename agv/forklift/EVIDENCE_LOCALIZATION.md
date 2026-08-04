# EVIDENCE — AMCL against the frozen warehouse map, measured absolutely

**Brief m5-08e.** The vehicle localizes itself in the committed warehouse
grid with `nav2_amcl`, and the localization error is measured **absolutely**
— carried into the world frame through the committed registration, with the
instrument's floor stated beside every figure and no per-run anchoring
anywhere.

| Item | Value |
|---|---|
| Date | **2026-08-04** |
| Under test | `agv/forklift/launch/localization.launch.py` + `agv/forklift/amcl.yaml`, `nav2_amcl` 1.3.12 / `nav2_map_server`, ROS 2 Jazzy |
| Map | `sim/maps/warehouse/warehouse.pgm` md5 `a663163036c5890937f9045bcf559e72`, **frozen and read only** |
| Registration | `sim/maps/warehouse/warehouse_registration.yaml`, θ = −0.453511°, t = (+6.029223, +5.541460) m |
| **FLOOR** | **residual rms 0.0404 m, MAX 0.1411 m** |
| Reference | `/forklift/odom` — the simulator's own pose of the model, **exact**, consumed by the scorer only |
| Scorer | `sim/scenarios/tools/mapping_evidence.py analyse --score absolute` and `agv/forklift/scripts/localization_run.py analyse`, cross-checked against each other |
| Host | project session container, Ubuntu 24.04, kernel 6.18.5, 4 cores, headless |

---

## The four measurements, in one table

Every figure is an **absolute** world-frame error of `map -> base_link`,
taken through the committed registration with **no per-run anchoring**, and
stated beside the **0.141 m floor**.

| | measurement | headline | vs the 0.141 m floor |
|---|---|---|---|
| **(a)** | steady state, full mapping route (107.68 m, 179.0 s) | **rms 0.124 m**, max **0.263 m**, final 0.093 m | rms **at the instrument's resolution**; max is 1.9 × floor and is a real measurement |
| **(b)** | convergence from a prior **1.166 m and 10.000° wrong** | at/below the floor after **13.81 m** of driving; **final 0.007 m** | **converged to the instrument's resolution** |
| **(c)** | DWELL, 128.7 s stationary in East A | before **0.289 m**, during mean **0.282 m**, after exit **0.348 m**; **growth over the dwell −0.007 m** | 2.0 – 2.6 × floor throughout; the growth is **below the floor** — the dwell itself cost nothing measurable |
| **(d)** | REVERSE, East A fork first, 8.52 m | **rms 0.053 m**, max **0.105 m**, final 0.079 m | **every figure at the instrument's resolution** — no measurable penalty |

**The dwell against the estimator's own bound** (`m5-07e`: at most 0.33° for
a dwell beginning at the stop, 0.000° after 16 s of settling): the EKF handed
AMCL **+0.539°** from the stop command — **1.6 × the bound, exceeded** — and
**+0.0000° from stop + 16 s onward over 114.0 s** — **the flat half of the
bound confirmed exactly**. AMCL made **one** correction in 130 s and **none
at all** once the vehicle was truly at rest.

**Both scorers agree on all five runs.** `mapping_evidence.py analyse
--score absolute` (committed, `sim/`) and `localization_run.py analyse`
(`agv/`) implement `p_world = R(−θ)(p_map − t)` independently and return
identical rms, max, final and final heading for every recording in §5–§8.

---

## 0. The floor, and the rule this file follows

The registration's residual **MAX is 0.141 m**. It is the largest
perpendicular distance between a wall point in the committed grid and where
the committed transform says that wall is. No rigid transform fits this grid
to this building better than that, because the grid carries 0.33° of
internal shear and a rigid transform cannot absorb shear
(`docs/reports/m5-08d-remap-and-registration.md` §5).

> **Any figure at or below 0.141 m is reported as "at the instrument's
> resolution". It is never reported as a smaller number, and no claim in
> this file rests on a difference below that value.**

That rule is applied by the tool, not by the reader:
`localization_run.py analyse` prints every error through one function that
substitutes the phrase whenever the value is at or below the floor.

**Why absolutely and not anchored.** An anchored score rigidly carries the
estimate's first sample onto truth, so its error curve starts at zero by
construction and a *consistently wrong* AMCL scores near zero. For a
localizer that is circular (`docs/reports/m5-08c-slam-judge.md` finding 2).
Every figure below goes through the committed `T(world → map)`, which was
fitted to the map's walls before any run in this file existed and contains
no figure from any of them.

---

## 1. Wiring — what reaches AMCL and what does not

```
  /forklift/scan  ──────────────┐         navigation lidar, z = 1.80 m,
  (nav_lidar, 360 rays, 10 Hz)  │         360 rays over 360 deg
                                ▼
  /tf: forklift/odom ────────► AMCL ────► /tf: map -> forklift/odom
       -> forklift/base_link   (+ frozen committed grid from map_server)
       (the EKF, sole publisher)

  /forklift/odom  ────────────► the SCORER, and nothing else
  (GROUND TRUTH, exact)
```

**Two inputs, and that is the whole list.**

- **`/forklift/scan`** — the navigation lidar. `amcl.yaml` names exactly one
  scan topic.
- **`forklift/odom → forklift/base_link`** on `/tf` — the EKF's estimate
  (`agv/forklift/ekf.yaml`), which fuses the tricycle wheel odometry with
  the gated gyro. The EKF is the **sole** publisher of that edge.

**Ground truth reaches neither.** `/forklift/odom` is the simulator's own
pose of the model despite its name (`agv/forklift/config.yaml` carries the
standing rename request). It appears in `amcl.yaml`: no. In `ekf.yaml`: no.
In the localization launch: no. It is subscribed by
`mapping_evidence.py record`, which writes a CSV, publishes no topic and
broadcasts no transform.

**The reference is exact.** It is the pose the physics engine holds for the
model, not an estimate of it, so it carries no error of its own. Every
figure in this file is therefore attributable **entirely to the localization
chain** — lidar → AMCL, EKF → AMCL, against the frozen grid — and not
partly to the instrument that measured it. The one exception is the
registration residual, which is stated as the floor and is the reason the
floor exists.

**Neither safety scanner reaches AMCL.**
`/forklift/safety_scanner_front/measurement` is a **non-safe measurement
channel** of a device whose safe channel is not on either transport at all
(`agv/forklift/README.md`); the rear channel is not even bridged. A
localizer that consumed one would suggest a safety device carries a process
function. `amcl.yaml` names one scan topic and it is the navigation lidar.

**Two publishers on `/tf`, two disjoint edges** — captured per run, never
asserted:

```
forklift/odom -> forklift/base_link   forklift_ekf
map           -> forklift/odom        amcl
```

A second publisher of *the same* edge would make the pose a coin toss (the
listener takes whichever message arrived last), so the count and the edge
list are in every run's record below.

---

## 2. The motion model — `nav2_amcl::DifferentialMotionModel`

This vehicle is a **tricycle**: one steered, driven wheel leading, two
passive wheels trailing (`agv/forklift/model.sdf`). **It cannot translate
sideways.** Its rear axle midpoint has purely longitudinal velocity, which
is exactly the constraint the differential motion model encodes.

`nav2_amcl::OmniMotionModel` removes that constraint: it adds an independent
lateral translation noise term, so its particles spread into poses this
vehicle cannot reach, and AMCL becomes free to explain a scan with a
sideways slip that never happened. The retired RB-KAIROS platform
(ADR 0010 D1) *was* a genuine omni base and the omni model was correct for
it; the choice is written out here so it is a decision on the record rather
than an inheritance from a platform that is gone.

The differential model is also the `nav2` default. That is a coincidence and
not the reason, and `amcl.yaml` says so where the parameter is set.

---

## 3. Every AMCL non-default, one sentence each

Values below equal to the nav2 default are marked **DEFAULT-KEPT** and still
listed when the default matters to a measurement, because a default that
shapes a result is a choice too. **Nothing here was tuned against a result:**
every value was fixed before the first scored run, from the sensor's own
datasheet (`model.sdf`), from the frame strings the messages carry
(`config.yaml`), or from a measurement published by somebody else
(`sim/worlds/WAREHOUSE_LANDMARKS.md`). The run order in §5–§8 is the check.

| Parameter | nav2 default | Here | Why |
|---|---|---|---|
| `robot_model_type` | `DifferentialMotionModel` | `nav2_amcl::DifferentialMotionModel` | §2 — a tricycle cannot translate sideways; written out because the retired platform's omni model is gone for a reason. |
| `base_frame_id` | `base_footprint` | `forklift/base_link` | The string the messages actually carry (`model.sdf` OdometryPublisher, mirrored in `config.yaml frames:`). |
| `odom_frame_id` | `odom` | `forklift/odom` | Same; the EKF publishes this exact string as the parent of base_link. |
| `global_frame_id` | `map` | `map` | DEFAULT-KEPT — the frame the committed map and its registration are expressed in. |
| `scan_topic` | `scan` | `/forklift/scan` | The navigation lidar, and the only sensor topic in the file; neither safety scanner is offered. |
| `laser_min_range` | `-1.0` | `0.10` | The sensor's own minimum, quoted from `model.sdf` `nav_lidar <range>`. |
| `laser_max_range` | `100.0` | `8.00` | The sensor's own maximum. A max range twelve times the real one changes which returns count as "saw nothing". |
| `max_beams` | `60` | `180` | AMCL subsamples 360 rays evenly, so the default keeps one in six. `WAREHOUSE_LANDMARKS.md` §5 measured that across the east half "the only along-aisle information in the scan is carried by ten rays or fewer" — one-in-six of ten rays is under two. One in two keeps the measurement possible. Set before the first run from that published measurement, not moved after. |
| `set_initial_pose` | `false` | `true` | The runs are unattended: no RViz, no operator, so the prior is a parameter and is stated per run. |
| `initial_pose.{x,y,yaw}` | `0,0,0` | per run | §4. |
| `always_reset_initial_pose` | `false` | `true` | The stated prior becomes the only thing a filter reset can start from; without it a reset silently re-initialises from the last saved pose and the convergence test measures nothing. |
| `save_pose_rate` | `0.5` | `0.5` | DEFAULT-KEPT **and not by choice** — see the finding below. |
| `alpha1`…`alpha5` | `0.2` | `0.2` | DEFAULT-KEPT. Deriving them from this vehicle's encoder model would be a second statement of a quantity `ekf.yaml` already owns (invariant 10), and fitting them to a result is the tuning this brief forbids. |
| `update_min_d` / `update_min_a` | `0.25` / `0.2` | same | DEFAULT-KEPT **and load-bearing for the dwell**: a standing vehicle gets no filter update, so map→odom is held and whatever the odometry does passes through unopposed. That is the mechanism the dwell measures, so it is not lowered to make the dwell look better. |
| `recovery_alpha_slow` / `_fast` | `0.0` / `0.0` | same | DEFAULT-KEPT (recovery **disabled**), deliberately. In an aisle with no along-track information a randomly injected particle one bay along scores as well as the truth, so recovery could relocate the filter to an equally-likely wrong pose and the error curve would show a clean jump that reads as a recovery. Off, a divergence stays visible. |
| `do_beamskip` | `false` | `false` | DEFAULT-KEPT. Beam skipping discards rays that disagree with the particle majority — in a degenerate aisle that is a way to discard exactly the ten rays that carry the along-aisle information. |
| `laser_model_type`, `z_*`, `sigma_hit`, `lambda_short`, `laser_likelihood_max_dist` | — | defaults | DEFAULT-KEPT. Nothing measured about this world argues for moving them and moving them to improve a figure is forbidden. |
| `min_particles` / `max_particles` / `pf_err` / `pf_z` / `resample_interval` | — | defaults | DEFAULT-KEPT. 500–2000 particles with KLD resampling. |
| `tf_broadcast` / `transform_tolerance` | `true` / `1.0` | same | DEFAULT-KEPT. AMCL owns map→forklift/odom and publishes it. |
| `use_sim_time` | — | `true` | Everywhere, in the params file **and** on both nodes from the launch, so neither a launch-arg mistake nor a params mistake alone can leave a node on the wrong clock. |

### Finding — `save_pose_rate: 0.0` bricks the node, silently

The intent was `save_pose_rate: 0.0`, to stop AMCL writing its current pose
back into its own `initial_pose_*` parameters. **That value does not work.**
`nav2_amcl` 1.3.12 computes `save_pose_period_ = tf2::durationFromSec(1.0 /
save_pose_rate)` with no guard, so zero produces an infinite period and the
CONFIGURE transition throws:

```
[amcl] [ERROR] Caught exception in callback for transition 10
[amcl] [ERROR] Original error: Input t_sec is too large or too small for tf2::Duration
[amcl] [WARN]  Callback returned ERROR during the transition: configure
[amcl] [FATAL] Lifecycle node amcl does not have error state implemented
```

The node then sits UNCONFIGURED: no scan subscription, no `/amcl_pose`, no
transform, and nothing in the log that looks like a localization failure.
**Reproduced in isolation** before the diagnosis was accepted, outside this
stack and with no simulator:

```
$ ros2 run nav2_amcl amcl --ros-args -p save_pose_rate:=0.0
$ ros2 lifecycle set /amcl configure
  -> Original error: Input t_sec is too large or too small for tf2::Duration
$ ros2 run nav2_amcl amcl --ros-args -p save_pose_rate:=0.5
$ ros2 lifecycle set /amcl configure
  Transitioning successful
```

The property that was wanted is bought instead with
`always_reset_initial_pose: true`, which makes the stated prior the only
thing a filter reset can start from.

### Finding — a launch-ordering race that costs a run, silently

`sim/launch/warehouse_slam.launch.py` emits its first lifecycle transition
**before** registering the handlers that chain the rest. `launch` executes
actions in order, and an `OnStateTransition` handler only begins matching
when its `RegisterEventHandler` action executes — so a node whose configure
completes faster than the launch can register the next handler has its
transition event go unheard and the chain simply stops.

That is not hypothetical. `map_server` configure is a yaml parse and a
606 × 410 PGM read: **26 ms**. Written in the same order, three runs of this
launch chained correctly and **the fourth stopped dead** after
`Read map ... 606 X 410` — map_server INACTIVE, amcl never configured, and
**nothing in either log that reads as an error**. `slam_toolbox` never
exposed this because its configure is slow enough to lose the race the other
way.

`localization.launch.py` therefore registers **every** handler before
emitting the first transition. Measured after the change, with no simulator
at all — six launches, six `ROS_DOMAIN_ID`s:

```
run 1: amcl active after 1s      run 4: amcl active after 1s
run 2: amcl active after 1s      run 5: amcl active after 1s
run 3: amcl active after 1s      run 6: amcl active after 1s
lifecycle chain: 6 passed, 0 failed of 6
```

plus the three full-stack runs of §7 and §8. **`sim/launch/warehouse_slam.launch.py`
carries the original ordering and is a request to `sim/`, not a change made
here** (§10, open question 10).

---

## 4. The initial pose, and what it is not

AMCL is given its prior **in the map frame**, which is all a real vehicle
could ever know: there is no world frame on a forklift and no
`T(world → map)` on one either. The prior comes from the **spawn pose**,
which is a launch argument — a commanded quantity, the digital equivalent of
"the truck is parked in bay 2 and bay 2 is here" — carried into the map
frame by `localization_run.py map-pose`, which reaches the committed
transform through `register_map.py`, the module that derived it
(invariant 10). **It does not come from the ground-truth stream**, which is
subscribed by the scorer only.

The conversion deliberately lives in the measurement harness and **not** in
`localization.launch.py`: putting it in the vehicle's own bringup would make
the vehicle depend on a transform that exists only because this is a
simulation.

### The by-construction caveat, stated before any figure is read

A run that starts from an exact prior and has not yet moved scores **exactly
zero** — the world → map → world round trip is the identity, and AMCL does
not run its filter at all until the vehicle has moved `update_min_d`. This
was confirmed rather than assumed, on a parked 44.8 s recording at the dwell
start pose: rms, max, mean, min, first and final all `0.000 m`, and one
stationary phase.

**That zero is not a measurement of AMCL and is not quoted as one anywhere
in this file.** The measurement begins when the vehicle moves. It is
recorded here because a reader who saw it in a table without this paragraph
would reasonably conclude the instrument was broken.

| Case | Vehicle spawn (base_link, world) | AMCL prior (map frame) | Prior error |
|---|---|---|---|
| (a) steady state | (−6.00, −5.50) yaw 0 | (−0.014123, +0.089123) yaw −0.007915 | exact |
| (b) convergence | (−9.00, −5.50) yaw 0 | (−2.014029, −0.487131) yaw +0.166618 | **+1.000 m x, −0.600 m y, +10.000° — 1.166 m and 10.000° WRONG, deliberately** |
| (c) dwell | (−4.50, +7.00) yaw 0 | (+1.584770, +12.576859) yaw −0.007915 | exact |
| (d) reverse | (+9.50, +7.00) yaw 0 | (+15.584331, +12.466046) yaw −0.007915 | exact |

---

## 5. (a) Steady state over the full mapping route

**The route is the committed one, driven unmodified.**
`sim/scenarios/warehouse_mapping_route.py` — the same 10-waypoint circuit
that built the map — was executed as committed, read only, nothing edited.
It completed in **179.0 s of simulation time over 9 legs**, against the
178.9 s of the mapping run that produced the grid
(`docs/reports/m5-08d-remap-and-registration.md` §3): the same drive.

The route driver closes its own loop on ground truth, as its header states,
because a stated route has to be reproducible to the centimetre. **That is
the driver, not an estimator.** It publishes two raw joint commands and no
pose, no transform and no odometry; nothing it publishes reaches AMCL or the
EKF.

```
GZ_PARTITION=m508e_a_route   ROS_DOMAIN_ID=62   headless
spawn (-6.00, -5.50) yaw 0    AMCL prior exact (§4)
1882 samples, 1880 with a map pose, 187.3 s of simulation time,
107.68 m of ground-truth path, 918.0 deg of turning
```

`/tf`, captured not asserted:

```
  Publisher count: 2
    amcl            map           -> forklift/odom        : 101 msgs / 12 s
    forklift_ekf    forklift/odom -> forklift/base_link   : 461 msgs / 12 s
  /tf_static  Publisher count: 1   sensor_tf
  VERDICT: 2 publisher(s) on /tf: amcl, forklift_ekf
```

### The figures, each beside the floor

| | absolute error of `map -> base_link` | vs floor |
|---|---|---|
| **rms over the whole recording** | **0.124 m** | **at the instrument's resolution** (floor 0.141 m) |
| **max** | **0.263 m** | 1.9 × floor — a real measurement |
| mean | 0.106 m | at the instrument's resolution |
| median (p50) | 0.093 m | at the instrument's resolution |
| p90 / p95 / p99 | 0.214 / 0.238 / 0.254 m | above the floor |
| final | 0.093 m | at the instrument's resolution |
| mean over the moving phase only | 0.108 m | at the instrument's resolution |
| heading, final | −1.23° | — |
| heading, rms / max | 1.44° / 4.52° | — |

**496 of 1880 scored samples (26.4 %) lie above the floor.** The other 74 %
do not, and about those samples this instrument says only that AMCL was
within its resolution — not that it was better.

- The **max, 0.263 m**, is at t = 158.6 s at ground truth (−0.09, +0.17):
  the W8 corner, where the route leaves aisle B and turns south into the
  central cross aisle. It is a corner, not a straight.
- The **max heading error, 4.52°**, is at t = 32.1 s at (+12.23, −4.07) —
  the W2→W3 corner at the east end. Both extremes are turns.

### The three named degenerate stretches, from the committed scorer

`mapping_evidence.py analyse --score absolute`, extents read out of
`WAREHOUSE_LANDMARKS.md` §5 at run time:

| stretch | pass | samples | seconds | entry along-x | exit along-x | growth | max across-y | heading at exit |
|---|---|---|---|---|---|---|---|---|
| **East A** | 1 | 63 | 6.2 s | −0.085 m | +0.002 m | **+0.087 m** | 0.060 m | −1.69° |
| **East B** | 1 | 50 | 4.9 s | −0.104 m | −0.029 m | +0.076 m | 0.031 m | +0.02° |
| **East B** | 2 | 50 | 4.8 s | −0.132 m | +0.020 m | **+0.151 m** | 0.035 m | −0.39° |
| **East dock** | 1 | 70 | 6.8 s | +0.045 m | +0.002 m | −0.043 m | 0.138 m | +2.44° |

Every crossing is **under seven seconds**, at 0.80 m/s, with a good heading
and without stopping. That is exactly the criticism
`docs/reports/m5-08c-slam-judge.md` finding 3 makes of this route: it never
lets the degeneracy bite. Which is why §7 and §8 exist.

### The two scorers agree

The same CSV read by the committed `mapping_evidence.py analyse --score
absolute` and by `localization_run.py analyse`, which implement
`p_world = R(−θ)(p_map − t)` independently:

| | mapping_evidence.py | localization_run.py |
|---|---|---|
| rms | 0.124 m | 0.124 m |
| max | 0.263 m | 0.263 m |
| final | 0.093 m | 0.093 m |
| final heading | −1.23° | −1.23° |

Both load the transform through `register_map.load_registration()`, which
verified the grid md5 in each run. Neither anchors anything.

## 6. (b) Convergence from a deliberately wrong initial pose

**The offset, stated.** AMCL was told the vehicle stood **+1.000 m** further
along x, **−0.600 m** across, and **+10.000°** rotated from where it
actually was — **1.166 m and 10.000° wrong**, applied in the map frame,
which is the frame the prior is given in. The spawn is
(−9.00, −5.50) yaw 0 in the dock aisle's well-conditioned west half; the
prior handed to the launch is (−2.014029, −0.487131) yaw +0.166618 in map
coordinates, against a true (−3.014029, +0.112869) yaw −0.007915.

The offset is **not** covariance-matched to the prior: `initial_cov_*` stays
at the nav2 defaults (σ = 0.5 m, 15°), so 1.166 m is about 2.3 σ out. That
was chosen so the answer would be a measurement rather than a formality; it
was not adjusted afterwards.

**The drive.** `localization_run.py drive --profile converge`, 34.0 s of
simulation time, **17.59 m** of ground-truth path: 5 s straight, a
symmetric +3 s / −6 s / +3 s weave at 0.12 rad, 5 s straight, then 8 s
stopped. The weave is there for heading observability — a filter driven dead
straight is given very little to separate a heading error from a lateral
one — and it returns both heading and lateral offset to zero by
construction. **The driver subscribes to nothing**: it plays a timed profile
and has no feedback path of any kind, so it cannot bend towards a pose that
scores better.

```
GZ_PARTITION=m508e_b_converge   ROS_DOMAIN_ID=64   headless
406 samples, 405 with a map pose, 40.1 s of simulation time
/tf: 2 publishers (amcl, forklift_ekf), edges disjoint
```

### The first figure is the check that the injection worked

The first scored sample reads **1.166 m and +10.000°** — the injected offset
to three decimal places, and it holds *exactly* constant for the whole 6.4 s
the vehicle stands still before moving. AMCL does not run its filter below
`update_min_d`, so a parked filter is a frozen filter. The measurement
starts at t = 6.5 s.

### Convergence, against distance travelled

| | | vs floor |
|---|---|---|
| error at the prior | **1.166 m**, +10.000° | 8.3 × floor |
| worst heading error reached | **11.48°** at 2.1 m travelled | the filter got *worse* in heading before it got better |
| below 0.60 m and stays | **4.26 m** travelled (t = 12.4 s) | — |
| below 0.30 m and stays | **6.22 m** travelled (t = 14.8 s) | — |
| below 0.20 m and stays | **7.14 m** travelled (t = 16.0 s) | — |
| **at or below the floor and stays** | **13.81 m travelled (t = 24.3 s)** | **converged to the instrument's resolution** |
| final, at rest | **0.007 m**, −0.090° | **at the instrument's resolution** (floor 0.141 m) |
| rms over the whole recording | 0.618 m | dominated by the deliberate error it starts from |
| mean / max over the moving phase | 0.385 m / 1.169 m | — |

```
 t[s]  travel[m]   err[m]   heading[deg]
  6.5      0.00     1.166      10.000     <- prior, frozen while parked
  8.9      1.46     1.051      10.636
  9.6      2.06     1.000      11.453     <- heading worst
 12.0      3.94     0.690       5.371
 14.3      5.82     0.353       1.467
 16.7      7.70     0.124       0.966
 19.8     10.21     0.144       2.300
 24.6     14.05     0.134       2.819
 29.4     17.59     0.070       1.045     <- last moving sample
 30.2     17.59     0.006      -0.090     <- first sample after the stop
```

**The correction is gradual, not a jump.** The largest single step in
`map -> forklift/odom` over the whole run is well under the filter's own
resolution and no step reads as a relocation. With `recovery_alpha_*`
disabled (§3) there is no random-particle injection available, so this is
the KLD-resampled cloud walking onto the truth over 14 m of driving, and it
is visible as such rather than as a teleport.

**The residual +1° to +3° heading wobble between 10 m and 15 m travelled is
the weave**, and it is on the record rather than smoothed: the filter tracks
a turning vehicle slightly late. It settles to −0.09° within 0.8 s of the
stop.

## 7. (c) The DWELL in East A

**The stretch.** East A is the **worst** of the three named degenerate
stretches: *Aisle A, y = +7.00, x ∈ [+2.0, +7.0], worst pose (+7.00, +7.00),
aniso 0.034* (`sim/worlds/WAREHOUSE_LANDMARKS.md` §5). Both aisle walls are
flat loaded racking; across the whole east half "the only along-aisle
information in the scan is carried by ten rays or fewer".

**The drive.** `localization_run.py drive --profile dwell`: approach East A
from the well-conditioned west half at 0.80 m/s, stop, stand for 130 s of
commanded dwell, drive on east, stop. 160.2 s of simulation time, 14.56 m of
path.

**Where it actually stood** — from ground truth, not from the profile:
base_link at **(+6.061, +6.955)**, heading −0.256°, with the **navigation
lidar at (+6.609, +6.553)** — inside the [+2.0, +7.0] extent and 0.39 m
short of the worst pose. Ground truth then moved **0.00000 m and 0.000000°**
for the whole stationary phase, so "the vehicle is standing still" is a fact
here and not a verdict.

**The dwell is long enough.** The ground-truth-stationary phase is
**128.7 s**, against the ≥ 120 s the brief asks for. The commanded dwell is
130.0 s; the 1.3 s difference is the coast, below.

```
GZ_PARTITION=m508e_c_dwell   ROS_DOMAIN_ID=65   headless
spawn (-4.50, +7.00) yaw 0   AMCL prior exact (§4)
1683 samples, all 1683 with a map pose, 166.1 s of simulation time
/tf: 2 publishers (amcl, forklift_ekf), edges disjoint
```

### Before, during, after — each beside the floor

| | absolute error | vs floor (0.141 m) |
|---|---|---|
| **BEFORE** — last moving sample, on arrival in the stretch | **0.289 m** | **2.0 × floor** |
| **DURING** — entry / mean / max / exit over 128.7 s | **0.289 / 0.282 / 0.289 / 0.282 m** | **2.0 × floor** |
| **growth over the dwell** | **−0.0070 m over 128.7 s** | below the floor — **at the instrument's resolution; the dwell cost nothing measurable in position** |
| **AFTER** — entry / max / exit | **0.282 / 0.362 / 0.348 m** | 2.0 – 2.6 × floor |
| heading, dwell entry → exit | −0.719° | — |

The 10.56 m approach from an exact prior to 0.289 m of error is itself the
measurement of how much East A costs: the route run (§5) crossed this same
stretch in 6.2 s and grew +0.087 m of along-aisle error doing it. Standing
in it adds nothing further.

### The apportionment — what AMCL did, and what it was handed

The reported pose is `map -> base_link`, and exactly two publishers move it.
Both windows are given, because they are not the same window and they do not
give the same number:

**Window A — from the stop command (130.0 s).** This is the window
`docs/reports/m5-07e-gate-leak.md` states its bound over: *"a dwell
beginning at the stop"*.

```
    total heading, map -> base_link      -0.1796 deg
    of which AMCL, map -> odom           -0.7185 deg  (0.1353 m, 1 correction)
    of which the EKF, odom -> base_link  +0.5389 deg  <- WHAT AMCL WAS HANDED
    real body rotation, ground truth     +0.0003 deg
```

**Window B — the ground-truth-stationary phase (128.7 s)**, which begins
0.86 s later, once the vehicle has finished coasting **0.136 m** past the
stop command:

```
    total heading, map -> base_link      -0.7185 deg
    of which AMCL, map -> odom           +0.0000 deg  (0.0000 m, 0 corrections)
    of which the EKF, odom -> base_link  -0.7185 deg  <- WHAT AMCL WAS HANDED
    real body rotation, ground truth     +0.0000 deg
```

**AMCL made exactly one correction in the whole 130 s**, at stop + 0.18 s,
while the vehicle was still coasting: 0.1353 m and −0.7185°. From the moment
the vehicle was actually at rest it made **none at all** — `map -> odom`
holds **one single distinct value** for 128.7 s, bit-frozen. That is
`update_min_d: 0.25` doing exactly what §3 says it does, and it means
**every millimetre and every degree of pose movement during a dwell arrives
from underneath AMCL, not from AMCL.**

### Beside it: the estimator's own dwell cost bound

> `docs/reports/m5-07e-gate-leak.md`: **at most 0.33°** for a dwell
> beginning at the stop, **0.000°** for one beginning more than 16 s after
> it — "for a two-minute AMCL dwell: at most 0.33°, and 0.00° if it does not
> begin in the settling window."

Measured here, over the same window the bound is stated for:

| | m5-07e bound | this dwell |
|---|---|---|
| EKF heading, from the stop command | **≤ 0.33°** | **+0.539°** — **exceeded, 1.6 ×** |
| EKF heading, from stop + 16 s onward | **0.000°** | **+0.0000° over 114.0 s** — **confirmed exactly** |
| where the cost lands | inside the first 16 s | **all of it by stop + 1.07 s** |

**The "flat after settling" half of the bound is confirmed to the last
digit and the "0.33° at the stop" half is not.** Reported as measured
rather than reconciled. `m5-07e` open question 1 already says what this
means: *"One stop, one posture, one seed… the 0.33° per stop bound is a
measurement of one of them."* This is a different stop — a 0.80 m/s
straight-line stop in a different world, on a fresh bias draw — and it cost
1.6 × the figure that stop produced. A **second, independent instance in
this same run** corroborates the size: the final stop of the profile cost
the EKF **+0.548°** over its 8 s window, with AMCL again making zero
corrections.

**What that means for the dwell result, said plainly.** Of the 0.28 m the
vehicle is wrong by while it stands in East A, **none of it accrued during
the dwell** — the error entering and leaving is the same to within 7 mm,
which is below the floor. The heading movement during the dwell was handed
to AMCL by the estimator underneath it and is bounded at about half a degree
per stop, arriving in the first second and then exactly flat however long
the vehicle stands. **A two-minute dwell in the world's worst degenerate
aisle is not what puts this vehicle 0.28 m out. Getting there is.**

## 8. (d) The REVERSE traversal of East A, fork first

**Fork first *is* backwards on this vehicle.** `model.sdf` states
"+x forward, the driving direction, the steer and drive end"; the mast sits
at x = −0.78 and the fork tines beyond it. So a fork-first traversal is a
**negative traction command**, and the committed route has never driven one:
it crosses East A west to east, facing and moving +x.

**The asymmetry is real, and it is not the scan's field of view.** The
navigation lidar returns 360°. What is asymmetric is where it *sits* —
(+0.55, −0.40) in base_link, 0.55 m towards the drive end and 0.40 m off the
mast centreline — and what stands beside it. The two mast rails are
0.09 × 0.09 boxes at x = −0.78, y = ±0.30, spanning **z = 0.05 to 2.05 m**,
so they cut straight through the sensor's own **z = 1.80 m** plane:

| occluder | range from the sensor | occluded arc, body frame | width |
|---|---|---|---|
| `mast_rail_left` | 1.503 m | +149.90° … +154.53° | 4.63° |
| `mast_rail_right` | 1.334 m | +173.56° … +177.71° | 4.15° |

**9 of the 360 rays, all of them pointing backwards.** Driving fork first
puts that blind pair of sectors on the space the vehicle is entering, in an
aisle where `WAREHOUSE_LANDMARKS.md` §5 has already measured that ten rays
or fewer carry all the along-aisle information.

### The control, because "no penalty" needs something to compare against

The committed route's East A pass is **not** a fair control: it runs at
0.80 m/s and arrives after ~75 m of driving, so any difference could be the
direction *or* the history. So a **`forward` profile** was added and run —
the exact mirror of the reverse pass, sample for sample: the same 8.52 m of
the same aisle at the same 0.60 m/s, the same body heading, the same exact
prior, the same 8.2–8.3 s inside the stretch, 84 scored samples in each.
The only thing that differs is the sign of the traction command.

```
REVERSE   GZ_PARTITION=m508e_d_reverse  ROS_DOMAIN_ID=66  spawn (+9.50,+7.00) yaw 0
          truth (+9.500,+7.000) -> (+0.979,+7.000): -8.52 m in x, heading held at 0
FORWARD   GZ_PARTITION=m508e_d_forward  ROS_DOMAIN_ID=67  spawn (+1.00,+7.00) yaw 0
          truth (+1.000,+7.000) -> (+9.519,+6.973): +8.52 m in x
```

### The figures, each beside the floor

| | **REVERSE, fork first** | FORWARD control | floor |
|---|---|---|---|
| whole-run rms | **0.053 m** — at the instrument's resolution | 0.118 m — at the instrument's resolution | 0.141 m |
| whole-run max | **0.105 m** — at the instrument's resolution | 0.176 m — above the floor | 0.141 m |
| final, at rest | **0.079 m** — at the instrument's resolution | 0.176 m — above the floor | 0.141 m |
| heading rms / max | 0.861° / 2.542° | 1.094° / 2.308° | — |
| **East A** entry / exit along-x | +0.030 / +0.061 m | +0.005 / −0.089 m | — |
| **East A** growth through the stretch | **+0.031 m** | −0.094 m | — |
| **East A** max across-y | 0.058 m | 0.058 m | — |
| heading at stretch exit | −0.64° | −1.05° | — |
| samples / seconds in the stretch | 84 / 8.3 s | 84 / 8.2 s | — |

**Every figure of the reverse pass is at or below the floor.** The claim
this supports is therefore exactly this and no more:

> **Driving East A fork first produced no measurable localization penalty.
> Every error figure of the reverse traversal sits at the instrument's
> resolution, so this instrument cannot resolve any difference between the
> two directions at this scale.**

It is **not** evidence that reversing is *better*, and the reason is on the
record rather than left out:

### The confound, named

The two runs draw a **fresh gyro bias each** — no seed is exposed by the
bringup — and the odometry they handed AMCL was not comparable:

| over the 14.2 s traverse | REVERSE | FORWARD |
|---|---|---|
| EKF handed AMCL (odom → base_link heading) | **+0.356°** | **+2.921°** |
| AMCL's own correction (map → odom heading) | −0.883° | −3.608° |
| AMCL's own correction (map → odom position) | 0.117 m | 0.404 m |
| corrections applied | 28 | 28 |
| real body rotation (ground truth) | +0.000° | −0.195° |

The forward pass was handed **8 × more heading drift** to absorb and it
absorbed it, ending 0.176 m out — just above the floor. The reverse pass got
the easier draw. So the right reading of the table above is that AMCL held
the vehicle inside, or barely outside, the instrument's resolution in both
directions while being handed very different odometry, and that reversing
did not break it. A seeded, repeated comparison is what would turn "no
measurable penalty" into a quantified one; that is §9's open question 3.

## 9. The committed artifacts, and how to reproduce

Every figure above is recomputable from files in `agv/forklift/evidence/`:

| file | what it is |
|---|---|
| `m5-08e-<case>-run.csv` | the raw 10 Hz recording — ground truth, EKF, `map -> base_link`, `map -> odom`, per sample |
| `m5-08e-<case>-marks.csv` | the drive profile's leg boundaries in simulation time |
| `m5-08e-a_route-legs.csv` | the committed route driver's own leg log |
| `m5-08e-<case>-publishers.txt` | the captured `/tf` publisher count and edge list |
| `m5-08e-<case>-analyse.txt` | `localization_run.py analyse` verbatim |
| `m5-08e-<case>-analyse-mapping_evidence.txt` | `mapping_evidence.py analyse --score absolute` verbatim |
| `m5-08e-parked-baseline-run.csv` | the parked recording behind §4's by-construction caveat |

Cases: `a_route`, `b_converge`, `c_dwell`, `d_reverse`, `d_forward`.

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<unique>     # BOTH, always

# 1. plant + vehicle + estimator (headless)
ros2 launch sim/launch/warehouse_bringup.launch.py x:=<X> y:=<Y> yaw:=0.0

# 2. where AMCL is told it is, in the MAP frame
python3 agv/forklift/scripts/localization_run.py map-pose --x <X> --y <Y> --yaw 0.0

# 3. the localization stack
ros2 launch agv/forklift/launch/localization.launch.py \
    initial_pose_x:=<mx> initial_pose_y:=<my> initial_pose_yaw:=<myaw>

# 4. capture, then drive
/usr/bin/python3 sim/scenarios/tools/mapping_evidence.py publishers --seconds 12
/usr/bin/python3 sim/scenarios/tools/mapping_evidence.py record --csv run.csv --seconds 100000 &
/usr/bin/python3 agv/forklift/scripts/localization_run.py drive \
    --profile {dwell|reverse|forward|converge} --marks marks.csv
#   or, for (a):  /usr/bin/python3 sim/scenarios/warehouse_mapping_route.py

# 5. score, both ways
python3 agv/forklift/scripts/localization_run.py analyse --csv run.csv --marks marks.csv
python3 sim/scenarios/tools/mapping_evidence.py analyse --csv run.csv --score absolute
```

Every run above was headless, isolated on **both** transports with a unique
`GZ_PARTITION` **and** `ROS_DOMAIN_ID`, driven to completion in the
foreground with bounded polling, **serialised — never two simulators at
once** (`docs/LESSONS.md` 2026-07-30), and every process confirmed gone with
`pgrep -af` afterwards. No RTF figure was taken and none is quoted.

---

## 10. What this evidence does not establish

1. **The floor swallows most of it.** 74 % of the route run's samples, and
   *every* figure of the reverse pass, sit at or below 0.141 m. About those
   samples this instrument says only that AMCL was within its resolution —
   **not that it was better**. A localization criterion tighter than
   ~0.14 m is not measurable through this map by this method, and the way
   to change that is to reduce the grid's 0.33° internal shear, which means
   changing the mapping (`m5-08d` open questions 2 and 3).

2. **`m5-07e`'s 0.33° per-stop bound does not hold at this stop.** Measured
   +0.539° over the window the bound is stated for, 1.6 ×. The bound's other
   half — 0.000° after 16 s — is confirmed exactly, twice. `m5-07e` open
   question 1 already scopes the figure to one stop; this is the second
   stop, and it is larger. **The bound should be restated as a range over
   stops, or re-derived.** This is a finding about the estimator, not about
   AMCL, and it is a request to whoever owns that bound rather than a change
   made here.

3. **The reverse comparison is one run against one run, with an
   uncontrolled gyro bias draw.** The bringup exposes no seed, so the two
   passes were handed odometry that differed by 8 × in heading drift (§8).
   The claim made is only "no measurable penalty". Turning it into a
   quantified statement needs a seeded, repeated A/B, which needs a seed
   argument on the bringup — **a request to `sim/`, not a change made
   here.**

4. **One run per case, no repetition, fresh bias draw each.** Nothing here
   is a distribution. Every number is one sample of one run.

5. **The dwell is one dwell, at one pose, in one stretch.** It stood
   0.39 m short of East A's worst pose, at a heading held straight, with the
   forks down and no load. A dwell out of a turn, on a slope, or with a
   raised load rocking on the tyres is not measured.

6. **AMCL was given an exact prior in three of the four cases.** That is
   what a parked vehicle in a known bay gets, and §4 states the
   by-construction zero it produces before the vehicle moves. It also means
   these runs do **not** measure global relocalization from no prior at all,
   which is a different capability (`recovery_alpha_*` is deliberately off,
   §3).

7. **Container only.** Every figure here is from the project session
   container. The owner's WSL2 host has never run this stack, and this
   evidence is qualified by the environment that produced it
   (`docs/LESSONS.md` 2026-07-27).

8. **Nothing here is Nav2.** This is localization only: `map_server` and
   `amcl`. No planner, no controller, no costmap, no behaviour tree. The
   vehicle in these runs is driven by a stimulus, not by an autonomy stack.

9. **The recorder still pairs latest-with-latest**, not stamp-with-stamp
   (`m5-08c` finding 6, ~16–32 mm at 0.80 m/s). Untouched here: it is below
   the floor, and it becomes worth fixing only if the floor comes down.

10. **To `sim/`: `warehouse_slam.launch.py` carries the launch-ordering race
    of §3.** It emits its configure transition before registering the
    handler that chains the activation. It has not bitten there because
    `slam_toolbox`'s configure is slow — but that is a timing accident, not
    a guarantee, and the failure mode is a mapping run that maps nothing
    while logging nothing wrong. Moving its `EmitEvent` below its
    `RegisterEventHandler` actions is a two-line change in a file this
    directory does not own. **A request, not a change.**

11. **To `sim/`: `warehouse_bringup.launch.py` exposes no sensor-noise
    seed.** `agv/forklift/launch/vehicle.launch.py` carries one; the
    warehouse bringup does not, so every run in this file drew a fresh gyro
    bias and no two runs can be compared on the odometry they were handed
    (§8's confound, open question 3). **A request, not a change.**
