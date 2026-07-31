# EVIDENCE — the vehicle's own motion estimate, and what it drifts

**The measured drift is 5.2 m of position and 17.2° of heading over a
106.49 m path with 1449.8° of total turning.** That is the answer, it is
larger than convenient, and section 7 says which term produced it.

**Sections 1–11 are brief m5-07c's run and are unchanged. Section 12 is
brief m5-07d's, and it changed one thing:** the estimator no longer
integrates gyro bias while the vehicle is standing still. Read in one
line, the difference is

| | over the idle | while driving |
|---|---|---|
| before | **−7.70° per minute** of standing there | −12.98° over the route |
| after | **0.00° per minute** | −12.88° over the route |

and the right-hand column is the point: **the drift while moving did not
improve**, by 0.10° over 110.74 s of driving, which is 0.95 of the
white-noise random walk expected over the same interval. That drift is
the phenomenon gate M5 exists to correct and it is still there, at full
size. What is gone is a heading error that depended on how long somebody
waited before pressing go.

Until brief m5-07c the forklift's pose came from Gazebo: perfect,
drift-free, and useless as a test of anything downstream. This document
records the run in which that stopped being true — an IMU on the model, a
wheel odometry computed from the vehicle's own joint states through
tricycle kinematics, and an EKF fusing them and owning
`forklift/odom → forklift/base_link`. Gazebo's pose is still published and
is now the **reference** these numbers are measured against.

| Item | Value |
|---|---|
| Date | **2026-07-31**, container run, UTC |
| Brief | `docs/briefs/m5-07c-realistic-odometry.md` |
| Host | project container, Ubuntu 24.04.4, kernel 6.18.5, `nproc` 4 |
| Simulator | `gz sim --versions` → `8.11.0` |
| ROS | Jazzy, `rmw_fastrtps_cpp` |
| Filter | `ros-jazzy-robot-localization` `3.8.3-1noble.20260615.152020` |
| Isolation | `GZ_PARTITION` and `ROS_DOMAIN_ID` both set, unique per run, headless throughout |
| RTF | **not measured and none is quoted** (LESSONS 2026-07-30) |
| `model.sdf` | md5 `b04706c41a379abf5b54f409843f8f98` |
| `config.yaml` | md5 `cdb8040252c0d71b43685687d8fb54ec` |
| `ekf.yaml` | md5 `da93e469fb357fab5bfa7f7ea5cd107f` |
| `scripts/wheel_odometry.py` | md5 `4acdb572352876a13bcccc0dcdcf94cf` |
| `scripts/check_odometry.py` | md5 `1a56ef3a1600014855f54d83dd91a62a` |

**Those five md5s are the files as brief m5-07c left them, and four of
them have since changed.** Section 12 carries its own table of the files
as m5-07d left them, and `model.sdf` appears in both with the same
digest, which is the check that the noise model was not touched.

---

## 1. The honesty rule, and what it cost

The brief's rule was to choose the noise parameters from what the
modelled hardware would plausibly do, state where each number came from,
and then report the resulting drift **whatever it is**.

Every number in section 2 is derived from one datasheet, read on the day.
Not one of them was moved after a result was seen. `check_odometry.py`
recomputes each derivation from the datasheet figure and fails if the SDF
disagrees, so the provenance is a check rather than a claim (section 3.1).

The result is a 17.2° heading error, which is a large number, and the
most important sentence in this document is that **fusing the IMU made
heading worse than the wheel odometry alone** (8.8°). That is reported
rather than corrected, because correcting it means changing the filter's
weighting, and that is tuning. Section 7 gives the mechanism, with the
arithmetic measured rather than argued.

---

## 2. The IMU noise model, and where each number came from

The modelled device is a **Bosch Sensortec BMI088**, a 6-axis MEMS IMU of
the class an AGV of this size carries. All figures from
**BST-BMI088-DS000-19, revision 1.9, 01/2024**, tables 4 (accelerometer)
and 5 (gyroscope), read 2026-07-31.

| SDF element | Value | Where it came from |
|---|---|---|
| gyro `stddev` | `0.001745` rad/s | The datasheet's own **Output Noise** row: `0.1 °/s rms, BW = 47 Hz (@ 0.014 °/s/√Hz)`. No arithmetic — the sensor is declared at that condition (100 Hz ODR). `0.1 °/s = 1.745e-3 rad/s` |
| gyro `bias_mean` | `0.002618` rad/s | **TCO `±0.015 °/s per K`** × a stated **10 K** excursion = `0.15 °/s`. See "the bias that is not the datasheet's" below |
| gyro `bias_stddev` | `0` | Fixes the bias **magnitude** across runs. gz still draws its **sign** at random, which section 7 makes use of |
| accel `stddev` x, y | `0.01076` m/s² | Noise density **160 µg/√Hz (x, y)** × √47 Hz × g = `1.097e-3 g` |
| accel `stddev` z | `0.01278` m/s² | Noise density **190 µg/√Hz (z)** × √47 Hz × g |
| accel `bias_mean` | `0.01961` m/s² | **TCO `< 0.2 mg/K`** × 10 K = `2 mg` |

**The bias that is not the datasheet's, and why.** The datasheet's
zero-rate offset is `±1 °/s`, measured with *"slow and fast offset
cancellation off"*. Using it raw would model a device nobody deploys:
every AGV integration estimates the stationary gyro bias at power-up. What
survives that estimate is the temperature change since it, so the modelled
bias is the **TCO term**. The 10 K excursion is the one judgement call in
this table — a device calibrated at power-up in an unheated hall and run
through a shift — and it is stated rather than buried. The same argument
retires the accelerometer's 20 mg zero-g offset in favour of its TCO.

**What is deliberately NOT modelled, stated rather than omitted.** The
datasheet publishes no Allan-variance bias instability, so **no in-run
bias random walk is modelled**: `<dynamic_bias_stddev>` is absent, not
zero by accident. The modelled bias is constant within a run. A real
device's is not, so **every drift figure here is a lower bound**.
Inventing a random-walk number to close that gap would have been a
fabricated datum, which is worse than a stated limitation.

---

## 3. The IMU alone, before anything consumed it

`--phase imu`, `GZ_PARTITION=m507c_imu`, `ROS_DOMAIN_ID=65`, stack
launched with `nodes:=false tf:=false wheel_odom:=false ekf:=false` — the
simulator, the spawn and the bridge and nothing else. The vehicle was left
12 s of simulated time to settle before sampling, because a model dropped
0.05 m onto the floor is still ringing and a noise figure taken through
that is a measurement of the suspension.

### 3.1 The model-level IMU system, measured rather than assumed

`gz`'s IMU sensor publishes nothing unless a system creates it, and the
usual placement is the world file. **This model carries the system
itself**, and that was verified against a world that has no IMU system of
its own — `sim/worlds/forklift_arena.sdf`, whose plugin list is Physics,
UserCommands, SceneBroadcaster and Sensors:

```
$ gz topic -l | grep imu
/forklift/gz/imu
$ gz topic -e -t /forklift/gz/imu -n 1
  ...
entity_name: "Forklift::imu_link::imu"
angular_velocity { x: 0.00278  y: 0.00274  z: -0.00336 }
angular_velocity_covariance { data: 3.0450251e-06 ... }
linear_acceleration { x: 0.0313  y: 0.0194  z: 9.8265 }
```

So **no world file has to be edited to give this vehicle an IMU**. The
sensor travels with the model into the arena, the warehouse and any world
a later gate adds. Contrast the three scanners, which go silent in a world
that forgot `gz-sim-sensors-system`.

Note `angular_velocity_covariance` = `3.0450e-06` = `0.001745²`: gz fills
the message covariance from the SDF's declared stddev. That single fact
sets the EKF's weighting, and section 7 is about what it leaves out.

### 3.2 The measured noise, against what was declared

```
  [PASS] measured rate matches the declared 100 Hz   (100.000 Hz over 24.99 s of simulated time, 2500 samples)
  [PASS] header.frame_id is the published IMU frame   (imu_link vs imu_link)

  channel                        mean       stddev  declared sd declared bias
  angular.x [rad/s]          0.002616     0.001785     0.001745     0.002618
  angular.y [rad/s]          0.002694     0.001765     0.001745     0.002618
  angular.z [rad/s]          0.002588     0.001754     0.001745     0.002618
  linear.x [m/s^2]           0.019719     0.010690     0.010760     0.019610
  linear.y [m/s^2]           0.019421     0.010959     0.010760     0.019610
  linear.z [m/s^2]           9.780779     0.013255     0.012780     0.019610

  [PASS] gyro x/y/z sample stddev is the declared white noise
  [PASS] gyro x/y/z mean is the declared bias, sign drawn by gz
  [PASS] the accelerometer reads 1 g at rest   (|a| = 9.7808 m/s^2)
```

Every sample standard deviation lands within 2.3 % of the declaration and
every mean lands on the declared bias. **All three gyro axes drew a
positive bias in this run**; the fusion run of section 6 drew a negative
one on z, which is gz's random sign and not a change in the model.

**The `|a|` figure reconciles exactly and is worth one line, because it
looks like a discrepancy.** `9.7808` against `g = 9.80665` is not sensor
error: the test world declares no `<gravity>`, so gz's default
`0 0 -9.8` applies, and `9.8 − 0.0196` (the z bias, drawn negative) is
`9.7804`; the x and y biases add the rest in quadrature. The simulator's
gravity is 9.8, not 9.80665.

### 3.3 The orientation trap — a finding, and a hazard for later briefs

`model.sdf` sets `<enable_orientation>false</enable_orientation>` because
**gz derives an IMU's orientation from the link's pose in the simulator**.
It is ground truth wearing a sensor's name, and a real strapdown IMU with
no magnetometer cannot produce an absolute heading at all. Consuming it
would put ground truth back into the estimator through the side door.

What the bridged ROS message actually carries, measured:

```
  [note] orientation quaternion as bridged: (0.000, 0.000, 0.000, 0.000);
         orientation_covariance[0] = 0.000
```

**Both halves of that are wrong in a dangerous direction.** The quaternion
is `(0,0,0,0)`, which is not a rotation at all — it is the protobuf
default, because the field is unset. And `orientation_covariance[0]` is
`0.0`, whereas the ROS convention for "this message carries no
orientation" is **`-1`**. Zero means *known exactly*. So a consumer that
follows the convention will read an invalid quaternion as a perfectly
known orientation.

Nothing on this vehicle does: `ekf.yaml` sets all three orientation flags
false, which is the second and independent refusal. It is recorded here as
an **open question for `sim/`** — the gap is in the gz→ROS bridge's
conversion, not in this directory — and as a warning to any later brief
that adds an IMU consumer.

### 3.4 The whole default stack, in a project world

The measurement runs are on a flat test world (section 9), so the stack
was also brought up once with **default arguments** on
`sim/worlds/forklift_arena.sdf`, `GZ_PARTITION=m507c_arena`,
`ROS_DOMAIN_ID=74`, to confirm nothing here depends on that world.

```
$ ros2 topic list
  ... /forklift/imu  /forklift/odom  /forklift/odom_filtered
      /forklift/odom_wheel  /forklift/scan  /tf  /tf_static ...

$ ros2 topic hz /forklift/imu             -> average rate: 100.006
$ ros2 topic hz /forklift/odom_wheel      -> min 0.019 s max 0.024 s, window 51
$ ros2 topic hz /forklift/odom_filtered   -> min 0.019 s max 0.021 s, window 51
```

`check_odometry.py --phase imu` passed all 11 checks there (this run drew
a **negative** z bias: gyro z mean `−0.002672` against the declared
`0.002618`), and `check_sensor_frames.py --live` passed 33 checks
including the new frame:

```
ok  /tf_static carries every sensor frame   received: ['imu_link', 'nav_lidar_link',
                                            'safety_scanner_front_link', 'safety_scanner_rear_link']
ok  published transform for imu_link matches model.sdf   parent forklift/base_link d_xyz 0.00e+00 m
ok  tf2 resolves forklift/base_link -> imu_link
```

`sensor_tf.py` needed no edit to publish the IMU frame: it enumerates
every `<sensor>` on a fixed child of `base_link` out of `model.sdf`, so
adding a sensor adds its transform.

---

## 4. The wheel odometry alone, against a known motion

Two verifications, in the order the brief required: the kinematics against
closed-form answers with no simulator at all, then the whole thing against
a driven run.

### 4.1 Closed form, `--phase static`, no ROS and no simulator

```
=== 4. the integrator against motions with a closed-form answer =======
  [PASS] 10 s at 1 m/s straight: 10 m of travel, no heading change   (x 10.500000000 (= 10 + d), y 0.000e+00, yaw 0.000e+00)
  [PASS] one full circle at steer 0.35 rad returns to its start   (closes at (+0.0000, +0.0000) m, yaw +0.0000 rad, radius 2.876 m)
  [PASS] the integrator agrees with the ideal vehicle it models   (max component difference 5.90e-12)

=== 5. the error model, on the same closed-form motions ===============
  [note] over the 110 m profile, with an IDEAL no-slip vehicle, the ERROR MODEL ALONE
         produces 3.197 m of position error and +8.843 deg of heading error
```

The kinematics are exact to 5.9e-12 over a full circle. **The error model
alone — no slip, no IMU, no physics — already produces 8.843° of heading
error over the profile**, and section 5 measures 8.84° live. The heading
error of this vehicle's wheel odometry is therefore almost entirely the
one-count steer zero offset, and it is predictable in advance.

### 4.2 The error model, and the one term that is absent

| Term | Value | Source |
|---|---|---|
| drive encoder | 4096 counts/rev | 1024 ppr incremental read in quadrature, the commonest catalogue resolution. Step `1.534e-3` rad = **0.184 mm of tread** |
| steer encoder | 4096 counts/rev | 12-bit single-turn absolute, likewise. Step `1.534e-3` rad = **0.0879°** |
| steer zero offset | `1.534e-3` rad | **One count.** No calibration resolves better than one count, so the residual *is* one count. Deliberately the smallest defensible value, because this term dominates |
| rolling radius | `0.1206` m vs the physics' `0.12` | A loaded PU drive tyre's effective rolling radius is **smaller** than its free radius, so a vehicle calibrated on a free tyre over-reports distance by 0.5 % |
| **wheel slip** | **not modelled** | The physics engine already produces it. Adding a slip term would invent an error the simulation already has |

The rolling-radius error's **sign is the pessimistic one on purpose**:
slip already makes the wheel over-turn relative to the ground, so an
over-reporting radius **compounds** with slip instead of cancelling it.
The other sign would have flattered the result by half a per cent with
nothing in the output to show it.

### 4.3 Slip, separated from the geometry that is mistaken for it

`--phase wheel`, `GZ_PARTITION=m507c_wheel`, `ROS_DOMAIN_ID=66`,
`wheel_odom:=true ekf:=false`.

```
=== 3. slip, separated from the cos(delta) geometry ===================
  drive wheel tread turned          109.997 m
  base_link path (ground truth)     106.490 m
  rear axle path (ground truth)     105.450 m
  rear axle path predicted from
    tread * cos(steer), no slip     105.404 m

  NAIVE "slip" = (tread - base_link path) / path   +3.29 %
  REAL  slip   = (predicted - true) rear axle path -0.04 %
```

**This corrects a reading in the previous brief's report.** `m5-07b`
measured 4.065 m of tread over a 3.989 m path and called the 0.076 m
difference slip. Most of it is not. A steered drive wheel travels a
**longer** path than the axle it pushes, by `1/cos δ`, and `base_link` is
offset 0.50 m from that axle again, so a tread-versus-path comparison
counts geometry as slip. Corrected for `cos δ`, the physics engine's real
longitudinal slip over 105 m of this profile is **−0.04 %** — the rolling
constraint holds almost exactly at 1 m/s on `mu = 1.0`.

That is a finding in its own right: **the modelled encoder and calibration
errors, not the simulator's contact model, are what this vehicle's
odometry drifts on.**

### 4.4 The measured drift of the wheel odometry

```
=== 4. the wheel odometry alone, against ground truth =================
   after [m]   position [m]  heading [deg]
       10.63         0.5396         1.8644
       26.61         0.8976         8.7541
       53.25         2.2446        17.5500
       79.88         4.2382        11.9249
      106.49         5.2373         8.8356   <- final
```

**5.24 m of position error and +8.84° of heading over 106.49 m.**

Reproducibility across the three driven runs that recorded it —
`m507c_wheel`, `m507c_fuse2`, `m507c_f4` — is 5.2373 / 5.2468 / 5.2373 m
and 8.836 / 8.890 / 8.836°, a spread under 0.2 %. The wheel odometry is
deterministic because none of its error terms is stochastic.

**The heading error does not cancel between opposite turns, and this is
why the manoeuvre set has both.** The odometry computes
`Δψ = s·sin(δ + offset)/L`. For a left turn `sin(0.35 + off) > sin(0.35)`,
so positive yaw is over-estimated; for a right turn
`sin(−0.35 + off) > sin(−0.35)`, so negative yaw is **under**-estimated.
Both errors are positive. A steer zero offset **accumulates across turns
of opposite sign**, which a single-direction profile would have hidden —
the mid-run 17.55° at the end of the left turn is partly, but only partly,
walked back by the right one.

---

## 5. The manoeuvre set, stated with the drift it produced

Printed by the harness on every run, so a drift figure is never separated
from the motion that produced it. Times are **simulation** seconds; each
leg's steer angle is commanded 1 s before its speed so the vehicle is not
driving through the steer slew.

```
    settle         3.0 s  speed +0.00 m/s  steer +0.000 rad
    straight 1    10.0 s  speed +1.00 m/s  steer +0.000 rad
    turn left     40.0 s  speed +1.00 m/s  steer +0.350 rad
    straight 2    10.0 s  speed +1.00 m/s  steer +0.000 rad
    turn right    40.0 s  speed +1.00 m/s  steer -0.350 rad
    straight 3    10.0 s  speed +1.00 m/s  steer +0.000 rad
    stop           5.0 s  speed +0.00 m/s  steer +0.000 rad
```

What the vehicle actually did, from ground truth:

```
  path length            106.490 m
  heading swept, TOTAL   25.303 rad  (1449.8 deg, 4.03 turns)
  heading swept, net     +0.169 rad  (+9.7 deg) - near zero because the two sustained turns oppose
  simulated duration     120.95 s
  final truth pose       (+30.680, +3.468) m, yaw +0.1691 rad
```

**Both sweeps are reported and the pair is the point.** The net sweep is
near zero because the turns oppose; quoting it alone would read as "the
vehicle barely turned" and hide 1449.8° of turning, which is what the
estimator actually had to survive. The steer angle 0.35 rad gives a turn
radius `L/tan δ = 2.88 m` — tight enough to load the tyre laterally,
wide enough that the vehicle is not scrubbing on the spot.

**The world is flat, empty and 200 m square**, emitted by
`check_odometry.py --print-world` and quoted in full in section 9. An
odometry drift measurement wants an unobstructed floor, and 106 m of
driving does not fit inside the arena's walls.

---

## 6. The fused estimate, and the transform it owns

`--phase fusion`, `GZ_PARTITION=m507c_f4`, `ROS_DOMAIN_ID=70`, default
launch arguments.

```
  [PASS] exactly one publisher of forklift/odom -> forklift/base_link   (1 publisher(s) of /tf: ['forklift_ekf'])
  [PASS] the EKF transform was published on /tf   (6050 transforms recorded)
  [PASS] a tf2 consumer on simulation time resolves the edge at "now"   (140705 successful lookups; last error: none)

  EKF (odom -> base_link) error against ground truth
   after [m]   position [m]  heading [deg]
       10.63         0.7795        -4.9013
       26.61         0.4916        -6.1014
       53.25         1.5276        -8.1814
       79.88         2.7200       -12.4762
      106.49         5.2129       -17.1811   <- final
```

Confirmed independently on the live graph:

```
$ ros2 topic info /tf --verbose
Publisher count: 1
Node name: forklift_ekf
```

**The interim source is retired in the same change.**
`ground_truth_tf` now defaults to `false`, and the exclusivity is
enforced rather than documented — `launch/vehicle.launch.py` refuses to
start with both sources on:

```
$ ros2 launch .../vehicle.launch.py ground_truth_tf:=true
[ERROR] [launch]: ekf:=true and ground_truth_tf:=true would both publish
forklift/odom -> forklift/base_link. Exactly one source owns that edge
(CLAUDE.md invariant 10). ...

$ ros2 launch .../vehicle.launch.py wheel_odom:=false
[ERROR] [launch]: ekf:=true with wheel_odom:=false starts a filter with no
odometry source. It would publish a transform built from the IMU yaw rate
alone, which is a heading with no position in it at all ...
```

That matters because **tf2 does not complain about two publishers of one
edge**: the listener takes whichever message arrived last, so the symptom
is a pose that alternates between drifting and perfect, with no error
anywhere.

**The error is measured from `/tf` messages, not from buffer lookups at
the reference's stamp, and the reason is worth recording.** A lookup at
the reference message's own stamp fails, correctly: the reference arrives
at `t` and the estimate for `t` has not been published yet, so tf2 raises
an extrapolation error rather than inventing a pose. Retrying at "latest"
would silently compare poses from different instants and report the timing
offset as drift. So the transforms are recorded as published, with their
own stamps, and paired afterwards. The tf2 buffer still earns its place —
it answers whether a real consumer resolves the edge at all, which it did
140 705 times.

---

## 7. Did fusing the IMU help? No, and here is the mechanism

```
                               position [m]    heading [deg]
  wheel odometry alone               5.2373           8.8356
  EKF, wheels + gyro                 5.2129         -17.1811

  WHY, MEASURED RATHER THAN ASSERTED:
  mean gyro z over the run     -0.001184 rad/s  (12100 samples)
  the vehicle's own mean yaw rate  +0.001398 rad/s (ground truth)
  the difference, the BIAS     -0.002582 rad/s  (model.sdf declares 0.002618, sign drawn by gz)
  bias x duration              -0.3123 rad = -17.89 deg
  EKF heading error            -0.2999 rad = -17.18 deg
```

**The filter is tracking the gyro, and the gyro's uncompensated bias
integrates straight into heading.** `bias × duration` predicts −17.89°;
the measured error is −17.18°. Position error is essentially unchanged
(5.21 m against 5.24 m) because the two heading errors happen to be
comparable in magnitude over this profile.

Three things put the filter there, and none of them is a defect:

1. **The message covariance carries white noise only.** gz fills
   `angular_velocity_covariance` from the SDF's declared `stddev`
   (`3.045e-06`), not from the bias. A real driver does not know its
   device's live bias either, so this is what an honest integration gets.
2. **The IMU is corrected twice as often.** 100 Hz against the wheel
   odometry's 50 Hz.
3. **The process noise is the package default.** `ekf.yaml` sets no
   `process_noise_covariance`, deliberately: it is the knob a drift figure
   is most easily flattered with. The default on yaw rate is large enough
   that the estimate follows whichever measurement came last.

**The sign is random per run and the magnitude is not.** gz draws the
bias sign at start-up, so three fusion runs gave heading errors of
−17.18°, −16.41° and +19.85° — magnitude 16–20°, sign whatever was drawn.
Anyone reproducing this should expect the sign to differ and the magnitude
not to.

**What would fix it, and why it is not fixed here.** Either declaring the
bias in the covariance the filter is given — `σ = √(1.745e-3² +
2.618e-3²) = 3.146e-3` rad/s, which would move the weighting to the
wheels — or estimating the bias on board with a zero-velocity update
whenever the vehicle stops, which is what real installations do. Both are
changes to how much the filter believes a sensor, i.e. tuning, and the
brief put the tuning argument in the SLAM brief. **The number is the
deliverable.**

**Half of that paragraph has since been answered, and the half that was
answered is not the half that changes this number.** Brief m5-07d landed
the second option's *first* half — the vehicle now recognises standstill
and stops offering the gyro's yaw rate to the filter in that condition —
and deliberately not its second half, the bias estimate that would be
carried into motion. The covariance was not touched either. So **every
figure in this section still stands as the drift while moving**, and
section 12.4 re-measures it on the same route to show that it does.

---

## 8. Does this exercise the degenerate aisles?

`sim/worlds/WAREHOUSE_LANDMARKS.md` §5 names three stretches, 4.0–5.5 m
long, where the scan carries almost no along-aisle information and
"odometry, not the scan, will be doing most of the work along x".

```
  measured position error      5.2129 m over 106.49 m
  pro rata over the longest
  degenerate stretch, 5.5 m    0.2692 m
```

**Yes, comfortably — and the answer is really about heading, not
position.** Three readings, in increasing order of usefulness:

- **Position, pro rata.** ~0.27 m of accumulated error across a 5.5 m
  degenerate stretch. That is an order of magnitude, not a prediction:
  dead-reckoning error grows with heading error, so it is superlinear in
  distance and depends on the manoeuvres, not only on how far the vehicle
  went. It is quoted with that caveat and should not be quoted without it.
- **Heading is the term that will bite.** A 17° heading error at the
  entrance to a 3.80 m aisle points the scan at the wrong wall. Even the
  wheel-only 8.8° is far outside anything a scan matcher recovers from as
  a prior. `WAREHOUSE_LANDMARKS.md` §9.4 warned that a SLAM run coming out
  *better* than predicted probably means odometry carried it; the opposite
  now applies, and **odometry will not carry this vehicle across a
  degenerate stretch on heading alone.**
- **Rate matters more than total.** Over the 10 m of `straight 1` the
  wheel odometry accumulates 0.54 m and 1.86°; a degenerate stretch is
  half that length. The vehicle enters the stretch with whatever error it
  already had, and adds roughly `0.05 m` and `0.19°` per metre of it.

So the drift is **not** too small to exercise them, which was the
finding the brief warned might come back. It is arguably on the large
side, which is the other finding the brief said would be interesting —
and it is exactly the condition real installations answer with
reflectors or fiducials. That choice is a localisation decision and it is
not taken here.

---

## 9. The world these runs used, and why it is not in this repository

`model.sdf` is a plain `<model>` and worlds belong to `sim/`, so the world
below is emitted by the harness itself — `check_odometry.py
--print-world` — rather than kept as a file. One source, no copy to age.
It is deliberately empty: it carries physics, a light and a 200 m floor,
and **no sensors system and no IMU system**, which is what makes section
3.1's claim testable.

```xml
<sdf version="1.8">
  <world name="odometry_flat">
    <physics type="ode">
      <max_step_size>0.002</max_step_size>
      <real_time_factor>1.0</real_time_factor>
      <real_time_update_rate>500</real_time_update_rate>
    </physics>
    <plugin name="gz::sim::systems::Physics"
            filename="libgz-sim-physics-system.so"/>
    <plugin name="gz::sim::systems::UserCommands"
            filename="libgz-sim-user-commands-system.so"/>
    <plugin name="gz::sim::systems::SceneBroadcaster"
            filename="libgz-sim-scene-broadcaster-system.so"/>
    <light name="sun" type="directional"> ... </light>
    <model name="Floor">   <!-- static 200 x 200 x 0.1 box, mu 1.0 --> ... </model>
  </world>
</sdf>
```

The three scanners are silent on it, which costs these runs nothing: no
scan reaches any estimator in this document.

---

## 10. Reproducing this

```
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<n>
cd <repo>

# no simulator, no ROS
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase static

# the test world
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --print-world > /tmp/flat.sdf

# the IMU alone
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat nodes:=false tf:=false wheel_odom:=false ekf:=false &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase imu --settle 12 --sample 25

# the wheel odometry alone
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat wheel_odom:=true ekf:=false &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase wheel

# the fusion, and the transform it owns
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase fusion
```

Each driven phase takes ~121 s of simulated time. **Isolate both
transports**: `ROS_DOMAIN_ID` does not isolate gz, because gz transport is
not DDS (LESSONS 2026-07-27). Every process was confirmed gone after each
run with `ps -eo pid,args`, never with `pgrep -f`, which matches its own
invoking shell.

---

## 11. What this evidence does not cover

- **Container only.** The owner's WSL host has never run this
  configuration, and `robot_localization` has never been checked there.
- **One floor, one speed, one steer angle.** Every figure is at 1.0 m/s
  on `mu = 1.0`. Slip came out at −0.04 %; a heavier load, a faster
  manoeuvre or a lower friction coefficient would change that term and
  nothing here bounds by how much.
- **No in-run gyro bias walk**, per section 2. The drift is a lower bound.
- **The fork is never raised.** A raised load moves the centre of mass and
  changes the tyre loading; no run here did it.
- **Nothing about SLAM or AMCL.** This document measures the input those
  will be given. What they do with it is the next brief's.
- **Nothing about standing still.** Every figure above is over a driven
  profile, and the two parked segments inside it were treated as part of
  the run. Section 12 is what happened when somebody measured the
  standing case on its own.

---

# 12. STANDING STILL — brief m5-07d

## 12.1 The finding this answers, and where the number came from

`docs/reports/m5-08c-slam-judge.md` finding 4 measured the committed
warehouse map as **rotated ≈ 2.0° from the building**, by least-squares
fitting the three longest walls in the committed grid. It attributed the
rotation to this estimator integrating the gyro's bias through the idle
between bringup and the first drive command — roughly **0.13 °/s over
about 20 s**, and it noted the discarded four-minute-idle map at ≈ 20°
as the confirming slope.

Three things make that a defect rather than a characteristic:

1. the map's orientation is a function of **how long someone waited**;
2. gz draws the bias sign per run, so **every rebuild gets a different
   angle, of a different sign**, and nothing downstream may ever
   hard-code one;
3. the mitigation on record was a sentence in a procedure ("drive
   promptly"), enforced by nothing.

**Measured here, and it reproduces exactly.** With the vehicle commanded
to rest and the estimator as m5-07c left it, the fused heading moved
**−7.70° per minute of idle** (section 12.3). The judge's 8 °/min was
right.

## 12.2 The mechanism, and why it is legitimate rather than convenient

### What was added

One node, `scripts/imu_gate.py`, and one boolean.

```
/forklift/joint_states ──► wheel_odometry.py ──► /forklift/odom_wheel ──┐
                                            └──► /forklift/wheel_standstill
                                                          │             │
/forklift/imu ─────────────────► imu_gate.py ◄────────────┘             │
                                     └──► /forklift/imu_gated ──► forklift_ekf
                                                                        ▲
                                                                        └┘
```

`wheel_odometry.py` publishes one extra topic: both encoder counts have
been unchanged for `standstill.window_s` (0.50 s). `imu_gate.py`
forwards every IMU message unchanged **except** while that verdict is
true and fresh, when it forwards none. `ekf.yaml` names the gated topic
as `imu0`. Nothing else changed.

### Why the wheels are evidence about the gyro

A MEMS gyro's output is `rate + bias + noise` and no part of the device
separates the three. The wheels separate them, for this vehicle, by
geometry:

> A tricycle's instantaneous centre of rotation lies on the line of its
> rear axle, because the two passive wheels cannot slide sideways. The
> drive wheel's contact point is **not** on that line — it stands one
> wheelbase in front of it. Writing the drive wheel's velocity in the
> body frame, `v_D = (v_R, ψ̇·L)`, so `|v_D| ≥ |ψ̇|·L`, which integrates
> to `|Δψ| ≤ (tread travelled) / L`.

One drive encoder count is `2π/4096 × 0.1206 m = 1.850e-4 m` of tread,
so **a count that does not change bounds the body rotation over that
interval at `1.850e-4 / 1.05 = 1.762e-4 rad = 0.0101°`.** The harness
computes that bound from `config.yaml` and prints it on every idle run
rather than quoting it.

So the rate term is known to be zero to within 0.0101°, independently of
the gyro. What the gyro reports in that condition is bias. Declining to
offer it to the filter as a rotation measurement is the **zero angular
rate update** every inertial navigator implements, and the reason it is
standard is exactly this one: standstill is the only interval in which a
dead-reckoning vehicle has independent knowledge of the truth of a rate.

**The steer count is in the test too**, although the bound does not need
it. A parked forklift can steer on the spot, and a steered wheel
scrubbing against the floor is the one manoeuvre in which the drive
encoder could hold while the contact patch slides. Requiring both counts
means "no wheel is moving at all", which is stronger than the bound needs
and costs nothing during an idle, when neither moves.

### Why it is a node and not a parameter

The brief's instruction was to prefer configuration to code. **The
package has no such configuration, and this was checked before the node
was written.** `robot_localization` 3.8.3
(`3.8.3-1noble.20260615.152020`), the exact build installed here:

```
$ strings /opt/ros/jazzy/lib/librl_lib.so | grep -iE 'zero|stationar|standstill|still'
...
zero_altitude
```

`zero_altitude` belongs to `navsat_transform` and is about altitude. The
filter's whole parameter set — `frequency`, `sensor_timeout`,
`two_d_mode`, `transform_time_offset`, the four frame names, the per
sensor `odomN_*` / `imuN_*` families, `use_control` and its limits and
gains, `process_noise_covariance`, `initial_estimate_covariance`,
`dynamic_process_noise_covariance`, `smooth_lagged_data`,
`history_length`, `reset_on_time_jump`, `permit_corrected_publication`,
`predict_to_current_time`, `disabled_at_startup`, `publish_tf`,
`publish_acceleration`, `gravitational_acceleration` — contains no
stationary handling of any kind. Two near misses were considered by name
and rejected:

| candidate | what it actually does | why not |
|---|---|---|
| `dynamic_process_noise_covariance` | scales the process noise by the robot's velocity | it changes how fast the estimate's uncertainty grows, not whether a measurement is fused. At rest it makes the filter trust its own prediction more, which **slows** the integration of the bias and does not stop it — and it is a change to the noise model, which brief m5-07d forbids |
| `ToggleFilterProcessing` service, with `disabled_at_startup` | freezes the entire filter until another service call | it freezes **position** as well as heading on the strength of one boolean, and re-enabling rides on a service call that can be lost. The failure mode is a filter frozen while the vehicle drives, which is worse than the drift it would prevent |

So the mechanism is one node outside the filter, and the filter's own
configuration changed by exactly one string: `imu0`, from
`/forklift/imu` to `/forklift/imu_gated`.

### Two design choices worth stating, because both could have gone the other way

**It suppresses; it does not rewrite.** A republished sample carrying a
zeroed yaw rate would be a reading this vehicle never took, and nothing
downstream could tell it from one it did. The gate publishes nothing
instead, so a gap in `/forklift/imu_gated` means "the gate was closed"
and can mean nothing else. The filter needs no special handling for the
gap: an absent measurement is simply not fused, and the wheel odometry's
own yaw rate — exactly `0.0` while the counts hold, because
`Δψ = tread·sin δ / L` with `tread = 0` — keeps arriving at 50 Hz and is
the only yaw-rate measurement in that interval.

**It estimates no bias, and carries nothing into motion.** The standstill
interval is long enough to observe the bias and subtract it afterwards,
which is the other half of what a real installation does. That was not
done, deliberately: it would reduce the drift while moving, which is the
phenomenon this gate exists to expose. When the gate is open the filter
is fed, byte for byte, what it was fed before this file existed.

**It fails open, in every direction.** No verdict yet, a verdict older
than `standstill.verdict_timeout_s`, a clock that ran backwards, a
missing joint, an implausible angle — each forwards the IMU. A gate stuck
open costs the drift that is already measured and documented in sections
1–11; a gate stuck closed would hide a real rotation from the filter,
and that is the failure worth designing against. The launch refuses the
one configuration in which the gate would run and be permanently
ineffective:

```
$ ros2 launch .../vehicle.launch.py wheel_odom:=false
[ERROR] [launch]: imu_gate:=true with wheel_odom:=false starts the gyro gate
with nothing to publish the standstill verdict it gates on. The gate fails
open, so the stack would run with the gate present and permanently
ineffective - which looks like a working stationary correction and is not
one. Run imu_gate:=false, or leave the wheel odometry on.
```

**It is not a safety function.** It gates one measurement channel of one
estimator. It inhibits no actuator, latches nothing and commands nothing;
the protective stop and safe torque off are onboard and hardwired and
appear in no Python file in this directory (invariants 1 and 9).

**One datum, one owner.** The standstill verdict is formed by
`wheel_odometry.py`, which already owns the encoder model, and by nothing
else. A gate that re-derived "is it moving" from the raw joint angles
would be quantising the same signal a second time with its own idea of
the count grid (invariant 10). `check_odometry.py` reads the verdict off
the topic for the same reason.

## 12.3 The idle hold, measured

`--phase idle`, seed 1, vehicle commanded to rest (`speed 0`, `steer 0`
published through `forklift_io.py`, so the command is delivered rather
than merely absent), 60 simulated seconds after a 10 s settle.

**No ground truth is read in this phase**, and that is structural rather
than careful. The question is whether a number moved while nothing
happened: the vehicle's own encoders establish that nothing happened, its
own gyro says what would have been integrated, and the fused heading is
compared with **itself** at the start of the window. There is nothing for
the simulator's pose to contribute.

| | `imu_gate:=false` | `imu_gate:=true` |
|---|---|---|
| distinct drive encoder counts in the window | **1** | **1** |
| distinct steer encoder counts | **1** | **1** |
| ⇒ body rotation bounded at | 0.0101° | 0.0101° |
| raw gyro z, mean over the window | −0.002621 rad/s (−0.1502 °/s) | −0.002618 rad/s (−0.1500 °/s) |
| raw gyro z, integrated over the window | −9.0086° | −8.9980° |
| standstill verdict true for | 100.0 % | 100.0 % |
| gyro samples offered to the filter | 6000 of 6000 (no gate) | **0 of 6000** |
| **fused heading, net change over 60.0 s** | **−7.7047°** | **0.0000°** |
| largest excursion from the start | −7.7047° | 0.0000° |
| **per minute of idle** | **−7.71 °/min** | **0.00 °/min** |

The left column reproduces the judge's 8 °/min from the artifact, and the
right column is the deliverable. **The gate's window is longer than the
idle that produced the committed map's error** — 60 s against the ≈ 20 s
finding 4 attributes it to — so the hold is demonstrated over three times
the interval that caused the problem.

**And over four minutes**, which is the discarded map's idle:

```
--phase idle --idle 240, imu_gate:=true, seed 1

  [PASS] the drive encoder reported exactly one count all window   (1 distinct counts over 240.00 s)
  [PASS] the steer encoder reported exactly one count all window   (1 distinct counts)
  standstill verdict true for        100.0 % of the window
  fused heading at the start of the window   -0.001043 rad
  fused heading at the end                   -0.001043 rad

                                            [rad]        [deg]
  net change over the window             0.000000       0.0000
  largest excursion from the start       0.000000       0.0000
  the gyro would have given             -0.624684     -35.7918

  window length                  239.98 simulated seconds
```

**0.000000 rad is what the instrument printed, and it means the value did
not change at the resolution the transform carries** — the transform is
not frozen, it is republished: 11 477 transforms were recorded over those
240 s, at the filter's 50 Hz, while 120 000 joint states and 24 000 gyro
samples arrived. The mechanism for the exactness is not luck: while the
counts hold, the wheel odometry's yaw rate is the literal float `0.0`
rather than a small number, so the filter's yaw-rate state settles onto
zero and its heading has nothing left to integrate.

**The residual −0.001043 rad the window starts from is the gate's own
cost, and it is the window length.** `0.002618 rad/s × 0.40 s`, against a
`standstill.window_s` of 0.50 s less the filter's own start-up: the gate
closes only after both counts have held for the full window, so every
stop pays up to half a second of ungated gyro. That is the conservative
direction and it is deliberate — **the gate opens on the first count of
motion and closes only after the window**, so it is late to trust a
standstill and instantaneous to distrust one.

## 12.4 The drift while moving, re-measured on the same route

`--phase fusion`, seed 1, the **same** `_PROFILE` and the same flat world
as sections 5–7. Both columns are runs of this build; the left one sets
`imu_gate:=false`, which remaps the filter back onto the raw IMU and is
the m5-07c configuration exactly.

| | `imu_gate:=false` | `imu_gate:=true` |
|---|---|---|
| path length | 106.494 m | 106.490 m |
| heading swept, total | 1449.8° | 1449.8° |
| simulated duration | 120.95 s | 120.95 s |
| bias drawn this run | −0.002611 rad/s | −0.002611 rad/s |
| wheel odometry alone, final | 5.2291 m / +8.8139° | 5.2662 m / +8.9280° |
| EKF final, **whole run** | 5.0619 m / −17.0501° | 3.2929 m / −12.9381° |
| seconds the wheels were reported still | 10.22 s | 10.22 s |
| gyro samples on `/forklift/imu`, as printed | 12 100 | 12 100 |
| gyro samples on `/forklift/imu_gated`, as printed | 0 — the gate node is not running and the launch remaps the filter onto the raw topic, so the filter was offered all 12 100 | **11 076** — 1 024 suppressed |
| heading error at the **first moving** sample | −3.2865° | −0.0596° |
| heading error at the **last moving** sample | −16.2629° | −12.9357° |
| **drift accumulated WHILE MOVING** | **−12.9765°** over 110.74 s | **−12.8761°** over 110.74 s |

The left column reproduces m5-07c's headline: 5.06 m / −17.05° here
against 5.21 m / −17.18° there, over the same 106.49 m and 1449.8°, with
a bias of −0.002611 rad/s here against −0.002582 there. Different draws
of the same distribution, same route, same answer.

### The moving drift did not improve, and here is the whole arithmetic

The whole-run heading error splits into three intervals, taken from the
vehicle's own standstill verdict and not from the profile's nominal
timings:

| | before the drive | while moving | after the drive | total |
|---|---|---|---|---|
| `imu_gate:=false` | −3.2865° | **−12.9765°** | −0.7871° | −17.0501° |
| `imu_gate:=true` | −0.0596° | **−12.8761°** | −0.0024° | −12.9381° |
| difference | 3.2269° | **0.1004°** | 0.7847° | 4.1120° |

**4.0116° of the 4.1120° improvement is in the two standing intervals**,
which is what a stationary correction is supposed to do and all it is
supposed to do. The remaining **0.1004° is the moving column**, and it is
not a reduction in drift — it is run-to-run noise, of exactly the
expected size:

```
sigma = sigma_gyro * sqrt(dt * T) = 1.745e-3 rad/s * sqrt(0.01 s * 110.74 s)
      = 1.836e-3 rad = 0.1052 deg
```

The two runs are not bit-identical — the seed fixes the bias draw, not
the thread scheduling that consumes the noise stream — so the white
noise integrates to a different random walk in each. **0.1004° is 0.95 of
one standard deviation of that walk.** There is no reduction to attribute
a mechanism to, and by construction there could not be: while the gate is
open the filter receives the raw message unchanged, and the gate was open
for every sample of the drive. The counters say so directly — **1 024
suppressed samples at 100 Hz is 10.24 s, against 10.22 s of verdict-true
time**, and the gate's own log shows exactly two transitions in the whole
121 s route:

```
[imu_gate] gyro gate CLOSED - the encoders report no motion, so the gyro is reading its own bias   after 52 forwarded / 0 suppressed
[imu_gate] gyro gate OPEN - the wheels are turning                                                 after 52 forwarded / 2399 suppressed
[imu_gate] gyro gate CLOSED - the encoders report no motion, so the gyro is reading its own bias   after 11128 forwarded / 2399 suppressed
```

No flapping, no closure inside the drive.

### The position error DID improve, by 1.77 m, and that is not the same claim

`5.0619 m → 3.2929 m`. It has one mechanism and it is not reduced drift
while moving: **the ungated run began driving with its heading already
−3.29° wrong**, and a heading offset present at the start rotates the
whole subsequent path about the start point. The final pose is 30.88 m
from the origin (`√(30.684² + 3.474²)`), so removing 3.2269° of initial
offset moves the end point by

```
30.88 m * 0.05632 rad = 1.739 m
```

against a measured 1.769 m — a 2 % agreement, from geometry alone with no
free parameter. **The vehicle drifts exactly as far as it did; it now
starts from where it is pointing.** Anyone quoting these figures should
quote the moving column, which is the one gate M5 is about.

## 12.5 Why the two columns are a comparison

`gz` draws each sensor's bias — **including its sign** — from a global
generator at model load, so two runs of the same stack get different
biases and the m5-07c evidence records three fusion runs at −17.18°,
−16.41° and +19.85°. A before-and-after taken from two such runs would be
a comparison of two dice.

`launch/vehicle.launch.py` therefore gained a `seed` argument, which
passes `--seed` to `gz sim`. It is a **measurement facility and nothing
on the vehicle reads it**: the default is empty, which restores the random
draw, and that is what every demonstration uses, because the sign a real
device wakes up with is not knowable in advance either. Verified here
before it was relied on:

| seed | drawn gyro z bias |
|---|---|
| 4242 | +0.002625, +0.002579 rad/s (two runs) |
| 1 | −0.002626 rad/s, and −0.002611 in both section 12.4 runs |
| 2 | +0.002516 rad/s |
| 3 | +0.002723 rad/s |

The sign follows the seed; the residual spread within one seed is the
sample mean's own white-noise uncertainty (`1.745e-3/√N`). **Seed 1 was
chosen because it draws the negative sign, the same sign as m5-07c's
headline**, so the before-and-after reads in the same direction as the
number it is being compared with.

## 12.6 What did NOT change, checked rather than asserted

| | |
|---|---|
| `model.sdf` | md5 `b04706c41a379abf5b54f409843f8f98` — **identical to section 0's**. Every datasheet-derived noise figure is untouched: the gyro's 0.001745 rad/s white noise, its 0.002618 rad/s bias, the accelerometer's two, all still exactly as m5-07c derived them |
| the message covariances | untouched. The gyro's is still the white noise only, and the gate forwards every field of every message it forwards unchanged, including that one |
| `config.yaml`'s `odometry:` covariances | `vx_variance`, `vy_variance`, `vyaw_variance`, `pose_variance_unused` — not one edited. The new constants are in their own `standstill:` block and none of them is a variance |
| `ekf.yaml` | still sets **no** `process_noise_covariance` and **no** `initial_estimate_covariance`. One line changed: `imu0` |
| ground truth | still reaches no estimator. `imu_gate.py` subscribes to the vehicle's own IMU and the vehicle's own encoder verdict, and to nothing else; `--phase idle` subscribes to no ground-truth topic at all |
| the route | `_PROFILE` is byte-identical to the one sections 5–7 ran |

Files as brief m5-07d left them:

| file | md5 |
|---|---|
| `model.sdf` | `b04706c41a379abf5b54f409843f8f98` (unchanged) |
| `config.yaml` | `f908c8f3a9911c1a089c4cde763499d8` |
| `ekf.yaml` | `05ebbdb17613d03e0b0465cae31d4e4c` |
| `scripts/wheel_odometry.py` | `8d63bba694000f0d0b0bf68d98967b2b` |
| `scripts/imu_gate.py` | `297ea24c328fd8c5605fd8600472d4c6` (new) |
| `scripts/check_odometry.py` | `9a1b0441f24476bc2f5400de77ee1cbc` |
| `launch/vehicle.launch.py` | `7dd66be25a715eb002cf7e71d96b9010` |

Environment for every run in this section, read from the machine that
produced them:

| Item | Value |
|---|---|
| Date | **2026-07-31**, container run, UTC |
| Brief | `docs/briefs/m5-07d-stationary-handling.md` |
| Host | project container, Ubuntu 24.04.4, kernel 6.18.5, `nproc` 4 |
| Simulator | `gz sim --versions` → `8.11.0` |
| ROS | Jazzy, `rmw_fastrtps_cpp` |
| Filter | `ros-jazzy-robot-localization` `3.8.3-1noble.20260615.152020` |
| Isolation | `GZ_PARTITION` **and** `ROS_DOMAIN_ID` both set, unique per run, headless throughout |
| Noise seed | `seed:=1` on every run quoted in 12.3 and 12.4 |
| RTF | **not measured and none is quoted** (LESSONS 2026-07-30) |

## 12.7 Reproducing this

```
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<n>
cd <repo>

/usr/bin/python3 agv/forklift/scripts/check_odometry.py --print-world > /tmp/flat.sdf

# the idle hold, gated (the shipped configuration)
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1 &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase idle --idle 60

# the same idle, ungated (the m5-07c configuration)
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1 imu_gate:=false &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase idle --idle 60

# the route, both ways. ~121 s of simulated time each
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1 [imu_gate:=false] &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase fusion
```

`nodes:=true` is the default and the driven and idle phases both need it:
`forklift_io.py` is what turns `/forklift/cmd/traction_speed` into the
model's raw input, and with `nodes:=false` the profile commands motion
that never happens. The harness now says so rather than dividing by a
zero path length, which is how that was found.

**Isolate both transports.** `ROS_DOMAIN_ID` does not isolate gz, because
gz transport is not DDS (LESSONS 2026-07-27). Every process was confirmed
gone after each run with `ps -eo pid,args`.

## 12.8 What section 12 does not cover

- **Only this vehicle's kinematics.** The bound in 12.2 is a tricycle
  argument. A differential-drive or omnidirectional vehicle needs its own,
  and on an omnidirectional platform a held drive encoder does **not**
  bound body rotation at all.
- **No gross drive-wheel skid.** The bound assumes the drive wheel rolls.
  A vehicle being slid bodily across a floor — towed, pushed, or on ice —
  could rotate with both counts held, and the gate would suppress a real
  rotation. It is the one credible way this mechanism is wrong, it is not
  reachable by any commanded motion in this simulation, and nothing here
  tests it.
- **The bias is not observed and not compensated.** Every drift figure in
  sections 1–11 still stands as the drift while moving, and the in-run
  bias walk is still not modelled (section 2), so all of them are still
  lower bounds.
- **Container only.** The owner's WSL host has still never run this
  configuration.
- **One idle posture.** The vehicle stood on flat ground with the forks
  down and the steer straight. A stop on a ramp, or with a raised load
  rocking on the tyres, is not tested.
- **Nothing about the map.** This section measures the estimator. Whether
  a rebuilt map now comes out square to the building is the SLAM brief's
  measurement, not this one's, and the registration finding 1 of
  `m5-08c` asks for is still needed either way — a SLAM map's frame is
  legitimately its own even when its heading no longer drifts.
