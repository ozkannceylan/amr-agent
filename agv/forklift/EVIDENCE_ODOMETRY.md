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

---

# 13. The gate leaked in the idle AFTER a drive — brief m5-07e

## 13.1 The finding, and why section 12's idles missed it

Section 12 measured the gate over a 60 s idle and a 240 s idle and
reported the fused heading holding at **0.00°** over both. Both of those
idles were taken **at bringup, before the vehicle had ever moved.**

`docs/reports/m5-08d-remap-and-registration.md` §9 item 4 measured the
same vehicle in the other regime — idle **after** a drive — with the
ground-truth position frozen at 0.0000 m, and found **+2.02° over a
200.4 s idle**, against **+0.01° over the 26.8 s pre-drive idle** of the
same run. 92–97 % of the gyro samples suppressed, not 100 %. It named a
likely cause — drive-encoder dither under a settled suspension — and
marked it **unconfirmed**.

That regime is the one an AMCL dwell test sits in, and at 0.61 °/min a
two-minute dwell would hand the localizer more than a degree of heading
error from the estimator alone. So the question was not whether to
mitigate it but **what it actually was.**

## 13.2 The instrument

`scripts/check_odometry.py --phase postidle`. It drives the SAME
`_PROFILE` as `--phase fusion`, commands the stop, and then records the
idle at full rate:

| stream | rate | what it settles |
|---|---|---|
| `/forklift/joint_states` | 500 Hz | which axis moves, to the sub-count residual |
| `/forklift/wheel_standstill` | 50 Hz | every re-arm, and the arrival gaps the gate times out on |
| `/forklift/imu` | 100 Hz | the bias, and what would have been integrated |
| `/forklift/imu_gated` | ≤100 Hz | exactly which samples reached the filter |
| `/tf` | 50 Hz | the fused heading |
| `/forklift/odom_filtered` | 50 Hz | the filter's own yaw-rate state |

It reads **no ground truth** for any of that, for section 12.3's reason.
`--truth` adds one further stream used by **section 7 only**, which asks
a question no encoder can answer and is discussed in 13.6.

The headline attribution is a three-way split of the fused heading
change: increments taken while a gated sample was in flight, increments
within 0.20 s of a burst ending, and increments with the gate closed and
settled. **A leak in the third bucket is the filter integrating a stale
twist. A leak in the first is the gate admitting samples.** That split
is what separates two hypotheses that look identical in a single number.

Raw per-sample series and verbatim harness output, in `evidence/`:

| file | md5 | the run |
|---|---|---|
| `m5-07e-postidle-before.csv.gz` | `c495b197ae9fe1ea7de5a73a3a39f565` | 210 s post-drive idle, m5-07d's rule |
| `m5-07e-postidle-after.csv.gz` | `5fe1aa8a1023c459ac7e86a93d76af06` | 220 s post-drive idle, this brief's rule, with the truth reference |
| `m5-07e-baseA.log` | `8b0542f5d20c8f0176205f9f6fc49d14` | the before idle, harness output |
| `m5-07e-fixA.log` | `385ff52793d75c3ebb5f502a19186220` | a 210 s after-idle taken before section 7 learned to split the coast; kept because it is an independent repeat of the headline |
| `m5-07e-fixB.log` | `873d4aded9e425e9ce44b60aa2c32aab` | the 220 s after idle, the run 13.7 quotes |
| `m5-07e-fusBEFORE.log` | `189138ba28cbee353b54b7a6a42f45e7` | the route, m5-07d's rule |
| `m5-07e-fusAFTER.log` | `1526190718a13471a29fd61063a8b203` | the route, this brief's rule |

Both CSVs were **gzipped after their writers were confirmed gone**, never
under a live writer (LESSONS 2026-07-28). `.gitattributes` already
carries `*.gz -text`.

**The two after-idles agree.** `fixA` (210 s) and `fixB` (220 s) are
separate runs of the same build: −0.1797 and −0.1796 °/min over the whole
idle, 98.47 % suppressed in both.

## 13.3 Four candidates, each ruled in or out by a measurement

One run: `--phase postidle --idle 210`, seed 1, the code as m5-07d left
it. It reproduces m5-08d's finding — **−2.1110° over 209.97 s =
−0.6032 °/min**, against m5-08d's +2.02° / 0.61 °/min on a fresh bias
draw of the other sign.

| candidate | measurement | verdict |
|---|---|---|
| the gate's freshness window lapsing, so it failed open | largest gap between two verdicts **0.0300 s**, against the 0.2000 s timeout | **OUT.** It never came close |
| the EKF integrating a stale twist through velocity decay | of the −2.1110°, **−0.0121° (0.6 %)** accrued with the gate closed and settled; −0.0336° (1.6 %) in the 0.20 s relaxation tails; **−2.0653° (97.8 %)** with a gyro sample actually being fused | **OUT** as the mechanism. It is a 0.6 % tail on the real one |
| the 0.50 s arming window at the stop transition | the first burst ends at t_stop **+0.806 s** and cost **−0.3290°**; the remaining 209.2 s cost **−1.7820°** | **IN, but 16 %.** It is a fixed cost per stop and it is not the term that scales with dwell length |
| encoder counts still settling after a drive | see below | **IN — and not the axis m5-08d named** |

### The drive encoder is not dithering. It is not moving at all.

Over the 210 s idle the drive count changed 144 times — **and every one
of them is inside the first 0.296 s**, the vehicle coasting to a stop
after the command. For the following **209.7 s the drive count did not
change once**, and its sub-count residual held to

```
parked drive wheel, sub-count residual
  mean  -0.256049   min  -0.256049   max  -0.256049
  pk-pk  3.842e-09 count = 5.893e-12 rad of wheel = 7.107e-13 m of tread
```

Four parts in a billion of one count. There is no dither, the wheel is
not parked near a boundary, and **m5-08d's stated hypothesis is ruled
out by direct measurement.** Replaying the recorded joint series through
a drive-only verdict gives 99.62 % suppression and a predicted leak of
−0.119°, against the −2.155° the real rule produced.

### It is the STEER axis, one count at a time

```
                                          drive      steer
distinct counts visited                     145         28
count CHANGES (each re-armed the window)    144         53
count excursion, max - min                  859         27
count NET change, last - first              859         -2
```

Clustering every count change into bursts and asking which axis starts
each one:

```
20 bursts of encoder activity over the idle
   started by the drive axis   1     (the 0.296 s coast)
   started by the steer axis  19
```

The steer axis **relaxes after a drive.** It swept 27 counts — 2.373° —
across the idle: a 4.1 s transient of about one count every 0.2 s
starting at t+11.3 s, and then **isolated single counts roughly every
eleven seconds** for the rest of the window (gaps of 9.9, 10.4, 11.8,
15.4, 65.0, 16.2, 12.7, 11.6, 11.5, 12.2 s).

That is the whole mechanism. `update_standstill` required **both counts
to be identical to the pair recorded when the hold began**, so each of
those single steer counts discarded however long the vehicle had been
standing and made the verdict false for a fresh 0.50 s window. The
arithmetic closes:

```
  0.8 s (the coast)  +  4.6 s (the 11-15 s transient)
                     +  18 x 0.5 s (isolated single counts)   = 13.9 s
  measured verdict-false time                                   14.384 s
  measured gate-open time                                       14.230 s
  x the measured bias -0.1498 deg/s                            -2.13 deg
  measured fused heading change                                -2.111 deg
```

**Why section 12's idles were clean:** at bringup every joint sits
exactly at its spawn value under no load, so neither axis moves and the
verdict is never re-armed. The steer term's cost was invisible for
exactly as long as nobody drove first. `config.yaml` said the term
"costs nothing during an idle, when neither moves"; that sentence was
true of the only idles that had been measured and false of the regime
that matters.

## 13.4 The defect is the SHAPE of the test, not its threshold

The old test asked whether both counts had been unchanged **since a
reference instant that receded for as long as the vehicle stood still.**
That is a statement about **total displacement over an unbounded
interval**, and no axis of a real machine satisfies it for ever: any
creep, however slow, eventually crosses a count, and the whole held
interval is then thrown away.

What the consumer needs at each sample is *"the body is not rotating
now"*, and that is a **rate** — a displacement over a **fixed** window.
Asking for a total was asking for more than the physics needs and more
than the machine can give.

Replaying the recorded 210 s joint series through candidate rules, which
costs nothing because the counts are already on disk. **This table is
checkable from the committed artifacts and needs no simulator** —
`--phase replay` is the instrument, and the rows below are its output:

```
zcat agv/forklift/evidence/m5-07e-postidle-before.csv.gz > /tmp/before.csv
/usr/bin/python3 agv/forklift/scripts/check_odometry.py \
    --phase replay --csv /tmp/before.csv
```

**The leak column is PREDICTED, not measured**: gate-open seconds times
the measured bias, which is what the filter would integrate if it took
each admitted sample at face value. The filter blends, so the live figure
differs — −0.505° predicted here against −0.659° measured over the longer
idle in 13.7. The **ranking** is what the table is for.

| rule | suppressed | gate open | predicted leak |
|---|---|---|---|
| **R0** as shipped: both exact, receding reference | 93.15 % | 14.386 s | −2.155° (−0.616 °/min) |
| R1 same, ±1 count band on both | 96.11 % | 8.162 s | −1.222° (−0.349 °/min) |
| R2 same, ±2 count band on both | 97.00 % | 6.296 s | −0.943° (−0.269 °/min) |
| R3 trailing window, both exact | 93.15 % | 14.382 s | −2.154° (−0.615 °/min) |
| **R4 trailing window, drive exact, steer ≤1 count** | **98.40 %** | **3.370 s** | **−0.505° (−0.144 °/min)** |
| R5 trailing window, drive exact, steer ≤2 | 99.46 % | 1.130 s | −0.169° (−0.048 °/min) |
| R7 trailing window, drive exact, no steer term | 99.62 % | 0.794 s | −0.119° (−0.034 °/min) |

Two of those rows are worth reading twice. **R3 is R0**: making the
window trailing while keeping exact equality changes nothing, so the
receding reference is not the defect on its own. And **R1/R2, the
obvious band fix, barely help**: a band absorbs dither, and this is not
dither — it is monotonic creep, which walks out of any fixed band and
re-arms anyway.

**The replay is validated against the live run.** Replaying the *shipped*
rule over the counts recorded by the *after* run gives 98.47 % suppressed
and 3.374 s of gate-open time; that run measured **98.47 % and 3.270 s
live**. Replaying *m5-07d's* rule over the same after-run counts gives
14.988 s and −2.246°, an independent second observation of the defect on
a different run from the one in 13.3.

## 13.5 What was changed

**`StandstillWindow`, at module scope in `wheel_odometry.py`, with no ROS
in it.** The verdict is now the **spread of each count over a trailing
`window_s`**:

| axis | test | what it is |
|---|---|---|
| drive | spread **= 0** counts over the window | **the bound.** `\|Δψ\| ≤ (tread travelled)/L` is true precisely because the count did not change, so its tolerance is zero — and it is a module constant, `DRIVE_TOLERANCE_COUNTS`, not an entry in `config.yaml`, because a tolerance of N counts multiplies the permitted body rotation by (N+1) and one count would take the bound from 0.0202 °/s to 0.0404 °/s = 2.4 °/min of **real** rotation the gate would then hide |
| steer | spread **≤ 1** count over the window | **a rate guard, and it carries no bound.** The tolerance is the **one count of zero uncertainty this file already declares for that encoder** (`steer_zero_offset_rad`): a calibration cannot resolve the steer zero better than one count, so demanding the reading be *identical* asks the axis to hold to a precision the vehicle's own model of it does not claim |

One count across a 0.50 s window is a steer rate of **0.176 °/s**. The
axis's own declared maximum is 2.0 rad/s (`model.sdf`, `steer_joint`
`<velocity>`), so any commanded steer motion exceeds it by three orders
of magnitude and opens the gate at once; the measured post-drive
relaxation is 0.09 counts/s, twenty times under it.

Every uncertainty still resolves to "not standing still", and now does so
by throwing the count history away rather than by setting a flag, so no
verdict can form again until a fresh window of samples exists. A gap in
the joint states longer than the window, and a clock that runs backwards,
both clear it — the second was already handled, the first was not.

**It is exercised without a simulator.** `--phase static` section 6 drives
`StandstillWindow` through eight count series whose answer is known,
including the defect itself. The old defect cost a 210 s live run to
find; the next one costs a table (LESSONS 2026-07-29).

```
=== 6. the standstill verdict, driven through count series ============
  [PASS] a vehicle whose counts never move reads standstill
  [PASS] the verdict waits the whole window before it forms   (first true at 0.5000 s)
  [PASS] a steer axis creeping one count every 11 s stays standstill   (100.0%)
  [PASS] a DRIVE axis creeping one count every 11 s does not   (95.8% - the gate opens around each count)
  [PASS] a steer axis slewing at 0.035 rad/s opens the gate   (0.0%, at 11.4 counts per window)
  [PASS] a joint-state gap longer than the window clears the verdict
  [PASS] a clock that runs backwards clears the verdict
  [PASS] the drive tolerance is zero, which is the bound itself
```

`--phase static` now passes **31 checks, 0 failed** (was 23).

## 13.6 The steer term's premise, measured

The steer count is in the verdict because "a parked forklift steering on
the spot is the one manoeuvre in which the drive encoder could stay still
while the contact patch slides" (section 12.2). That is a claim about the
world, and truth is the only instrument for it, so `--phase postidle
--truth` records the simulator's pose — **as a reference, in its own
section, entering no verdict this phase computes.**

Over the 220 s post-fix idle the steer axis swept **2.3730°** with the
drive count held throughout, and the body:

| from t_stop + 0.800 s, one window after the drive wheel stopped | |
|---|---|
| TRUE position excursion | **0.001568 m** |
| TRUE heading, largest excursion | **0.001750°** |
| TRUE heading, net over 219.17 s | **+0.001471°** |

2.373° of steer sweep produced 0.0018° of body rotation — three orders of
magnitude smaller, and at the floor of what the reference resolves. **On
this vehicle, in this simulator, on this floor, steer-axis motion with
the drive count held does not turn the body.** The kinematics say why:
the steer axis passes through the wheel centre, so there is no castor
trail, and rotating the wheel about it translates the contact point by
zero — while a body rotation of Δψ requires the drive wheel centre to
trace an arc of Δψ·L.

**That is a measurement and not a licence to delete the term.** It says
nothing about a real tyre with a finite contact patch, and the failure
the term was named for is not the one it detects anyway: a vehicle towed
or pushed bodily rotates with **both** counts held, and no encoder on
this machine sees that at all (12.8, and open question 2 of m5-07d). The
term is kept, demoted from an exact-equality test to a rate guard, and
described as a guard rather than as part of the bound.

## 13.7 The re-measurement, over 220 s

`--phase postidle --idle 220 --truth`, seed 1, the same world, the same
profile, the same stop.

| | before (m5-07d's rule) | after |
|---|---|---|
| idle measured | 209.97 s | 219.98 s |
| gyro samples suppressed | 93.14 % | **98.47 %** |
| separate openings of the gate | 19 | **9** |
| gate-open time | 14.230 s | **3.270 s** |
| **fused heading, whole idle** | **−2.1110°** | **−0.6585°** |
| as a rate over the whole idle | −0.6032 °/min | −0.1796 °/min |

**But the rate is the wrong summary of the second column, and this is the
result.** Split the idle at t+20 s:

| | before | after |
|---|---|---|
| fused heading over the first 20 s | −1.2559° | −0.6585° |
| **fused heading over the REST of the idle** | **−0.8550° over 190 s (−0.2701 °/min)** | **+0.000000° over 200 s (0.0000 °/min)** |
| gyro samples admitted after t+20 s | 647 | **0** |

**The last gate opening of the whole run ends at t+15.414 s. For the
following 204.6 s not one gyro sample reaches the filter and the fused
heading does not move at all.** Every one of the nine openings, with what
each cost:

```
   start      end    len_s   fused_deg   true_deg    err_deg
   0.004    0.804    0.800     -0.3326    -0.2196    -0.1130   <- the coast
  11.494   13.094    1.600     -0.2031     0.0007    -0.2038   <- the steer
  13.154   13.354    0.200     -0.0437     0.0001    -0.0438      axis's
  13.454   13.644    0.190     -0.0424     0.0001    -0.0425      post-drive
  13.784   13.944    0.160     -0.0314     0.0001    -0.0314      relaxation
  14.134   14.284    0.150     -0.0290     0.0001    -0.0291      transient
  14.514   14.614    0.100     -0.0132     0.0000    -0.0133
  14.934   14.994    0.060     -0.0060     0.0000    -0.0060
  15.404   15.414    0.010     -0.0028     0.0000    -0.0028
                    3.270 s total
```

and the estimator's error, against truth, accrued epoch by epoch:

```
  [  0.80,  5.00)  fused  -0.0064  true  +0.0000  error  -0.0064 deg
  [  5.00, 20.00)  fused  -0.3259  true  +0.0009  error  -0.3268 deg
  [ 20.00, 60.00)  fused  +0.0000  true  -0.0021  error  +0.0021 deg
  [ 60.00,120.00)  fused  +0.0000  true  -0.0006  error  +0.0006 deg
  [120.00,220.00)  fused  +0.0000  true  +0.0032  error  -0.0032 deg
```

**The leak has changed kind, not only size.** It was a rate that grew
with how long the vehicle stood there; it is now a **fixed cost paid once
per stop, inside the first sixteen seconds, and nothing afterwards.** A
two-minute dwell and a twenty-minute dwell now cost the same.

The first row of that table is also not all estimator error. The vehicle
**coasts 0.138 m** after the stop command and genuinely turns −0.2196°
doing it; the gate is correctly open, and the filter is tracking real
motion. Of the −0.3326°, **−0.1130° is estimator error and the rest is
the vehicle.**

## 13.8 The residual, stated as a bound

| | |
|---|---|
| **worst case, a dwell beginning at the stop command** | **−0.331° of heading error**, accrued in the first 16 s, then flat |
| a dwell beginning 20 s after the stop | **0.000°**, measured over 200 s |
| as a rate over the parked interval, if quoted that way | −0.0907 °/min over 219.17 s — **and quoting it that way is wrong**, because the error does not accrue at a rate |
| **for the AMCL dwell test** | a two-minute dwell inside a degenerate aisle costs **at most 0.33°** of estimator heading, and **0.00°** if the dwell starts more than 16 s after the vehicle last moved |

Against the brief's premise — "at 0.61 °/min a two-minute dwell hands
AMCL over a degree from the estimator alone" — a two-minute dwell now
costs **0.33° at worst and 0.00° if it does not begin in the settling
window.** The dwell test measures the localizer.

**Where the residual is, exactly.** All of it is the steer axis's
post-drive relaxation transient at t+11.5 s to t+15.4 s, where the axis
moves at up to **3 counts per 0.50 s window (0.53 °/s)** and correctly
exceeds the 1-count rate tolerance. Nothing was done about it, on
purpose: an axis moving at half a degree per second **is** motion, the
gate opening for it is the conservative direction, and a tolerance chosen
to swallow it would have been a number fitted to make this table look
better. `config.yaml`'s tolerance is derived from the encoder's stated
calibration limit and from nothing in this measurement.

## 13.9 The drift while moving, re-shown on the same profile

The gate must not touch the moving case. `--phase fusion`, seed 1, same
world, same `_PROFILE`, **both runs taken in this session** — the
before-run from a scratch tree holding `git show HEAD:` versions of
`wheel_odometry.py`, `config.yaml` and `check_odometry.py`, so the two
differ in the standstill rule and in nothing else.

| | before | after |
|---|---|---|
| **drift accumulated WHILE MOVING** | **−12.8941° over 110.76 s** | **−12.7800° over 110.74 s** |
| gyro samples on `/forklift/imu` | 12100 | 12100 |
| gyro samples on `/forklift/imu_gated` | 11077 | 11076 |
| verdict-true time over the recorded window | 10.20 s | 10.22 s |
| path length | 106.494 m | 106.494 m |

The difference is **0.1141°**. The expected white-noise random walk over
the same interval is `σ_gyro·√(Δt·T) = 1.745e-3·√(0.01·110.74) =
0.1052°`, so it is **1.08 σ** — the same noise floor section 12.4
reported at 0.95 σ, and it could not have been otherwise: **one gyro
sample in 12 100 differs between the two runs.** While the vehicle moves
the drive count changes by thousands per window, the spread test fails
instantly, the gate is open for every sample of the drive, and the filter
is fed exactly what it was fed before.

For reference, section 12.4's figure for the same seed in an earlier
session was −12.8761°, 0.018° from this session's before-run.

## 13.10 What did NOT change, checked rather than asserted

| file | md5 as this section was written | |
|---|---|---|
| `model.sdf` | `b04706c41a379abf5b54f409843f8f98` | **byte-identical to sections 0 and 12.6.** Every datasheet noise figure is untouched: the gyro's 0.001745 rad/s white noise, its 0.002618 rad/s bias, the accelerometer's two |
| `ekf.yaml` | `356afa12db9393e89bf92c6fbdbc07eb` | **comment only, and that is checked rather than claimed**: `yaml.safe_load` of this file and of `git show HEAD:` of it compare **equal**. No covariance, no `process_noise_covariance`, no `initial_estimate_covariance`, no sensor config, no topic name |
| `config.yaml` | `155fa00a23d1dedf2cb5bf95425535b5` | one new key, `standstill.steer_tolerance_counts: 1`, and the `standstill:` prose. Comparing the parsed documents key by key, **`standstill` is the only top-level key that differs** — `odometry`, `model`, `limits`, `imu`, `obstacle`, `frames`, `qos`, `logging`, `rates`, `spawn` and `topics` are all unchanged, so no derived covariance and no error-model number moved |
| `scripts/imu_gate.py` | `50f7594017b157157870c61a9c2c5521` | **docstring only, no behaviour.** The gate was never the defect: its freshness test was ruled out by measurement in 13.3 and not touched |
| `launch/vehicle.launch.py` | `c6448e01b46134ee03359966960b3172` | **comment only.** No node, argument, default or exclusivity check changed |
| `scripts/wheel_odometry.py` | `c641e9573888305d6a01e7cccb5faa2d` | `StandstillWindow` added and the verdict delegated to it. The kinematics, the encoder model, the integration and the published covariances are untouched |
| `scripts/check_odometry.py` | `fdd215616e022248313372533cd69536` | `--phase postidle`, `--phase replay`, `--truth`, `--csv`, and static section 6. **No existing phase's arithmetic changed**; `--phase static`'s original 23 checks all still pass, and the phase now runs 31 |
| `README.md` | `2ef4dfc5cb77cc7b9852fc8f63a3b64a` | the `/forklift/wheel_standstill` and `imu_gate` rows of the contract table, re-worded to the rate test |

- **No bias is estimated and nothing is carried into motion.** The change
  is to *which intervals* a measurement is offered in, exactly as
  section 12.6 said of the original. `StandstillWindow` holds encoder
  counts and timestamps and no gyro quantity of any kind.
- **No ground truth reaches an estimator.** `--truth` is a flag on the
  measurement harness, off by default, reported in its own section,
  entering no verdict. Sections 2–6 of the phase are identical with it
  and without it.
- **`_PROFILE` is unchanged**, which is what makes 13.9 a comparison.
- **No dependency was added.** `collections` is in the standard library.

## 13.11 Reproducing this

```
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<n>
cd <repo>

/usr/bin/python3 agv/forklift/scripts/check_odometry.py --print-world > /tmp/flat.sdf

# the post-drive idle. It drives _PROFILE first, so it is ~340 s of
# simulated time; the pre-drive idle is --phase idle and is a different
# question.
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1 &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase postidle \
    --idle 220 --truth --csv agv/forklift/evidence/postidle.csv

# the moving drift, on the same profile
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1 &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase fusion

# the verdict itself, with no ROS and no simulator
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase static

# 13.4's rule comparison, from the committed series, also with no ROS
zcat agv/forklift/evidence/m5-07e-postidle-before.csv.gz > /tmp/before.csv
/usr/bin/python3 agv/forklift/scripts/check_odometry.py \
    --phase replay --csv /tmp/before.csv
```

The before-column of 13.7 and 13.9 is the same commands against a tree
built with `git show HEAD:agv/forklift/{scripts/wheel_odometry.py,
scripts/check_odometry.py,config.yaml}` copied over a copy of
`agv/forklift/`; `launch/vehicle.launch.py` resolves every path from its
own location, so the copy is self-contained.

**Isolate both transports.** `ROS_DOMAIN_ID` does not isolate gz, because
gz transport is not DDS (LESSONS 2026-07-27). Every run here was headless,
driven to completion in the foreground, and every process confirmed gone
with `pgrep -af` afterwards. **No RTF figure was taken and none is
quoted** (LESSONS 2026-07-30).

## 13.12 What section 13 does not cover

- **One stop, one posture, one seed.** Flat ground, forks down, steer
  commanded straight, `--seed 1`. The steer relaxation's size and the
  16 s it lasts are properties of *this* stop; a stop from a turn, on a
  ramp, or with a raised load rocking on the tyres is not measured, and
  the fixed per-stop cost of 13.8 is a measurement of one of them.
- **The residual is not fixed, only bounded and located.** 13.8 states
  where it is and why it was left.
- **The steer term is now a guard with no bound behind it**, and
  13.6 says so. It fires on steer rate. It does not detect the failure
  it was named for, and neither did the exact-equality version.
- **Gross drive-wheel skid is still the one credible way the mechanism is
  wrong** (12.8). Nothing here changes or tests it.
- **Nothing about the map, and nothing about AMCL.** This measures the
  estimator standing still. Whether 0.33° per stop is acceptable to a
  dwell test is the AMCL brief's criterion to state, not this one's.
- **Container only.** Every figure is from the project session container.
  The owner's WSL2 host has never run this configuration.

---

# 14. THE POST-DRIVE IDLE ON THE NEW PLANT - 2026-08-05 (m5-40)

**Sections 1-13 above are untouched and byte-identical.** They are
container runs on the plant that carried steer `p_gain` 6000, and they stay
exactly as they were committed.

m5-40 applied the steer-gain change ruled by the owner (`model.sdf` steer
`p_gain` 6000 -> 60000; `EVIDENCE_NAV2.md` section 12).
`agv/forklift/PLANT-CHANGE-INVENTORY.md` classifies **section 13 alone** in
this file as affected, and it says exactly why: sections 1-12's drift
figures are properties of the error model and the gyro bias, reconciled in
closed form by the file itself and commanded at steer angles (0 and
+/-20.1 deg) far above even the old plant's 3.8 deg knee, whereas section
13 measures **the steer axis's own post-drive relaxation against the tyre
contact** - which is the mechanism whose stiffness the change multiplies by
ten. The inventory called the direction of change unknown and refused to
predict it. This section measures it.

**Every heading below was written before the run that fills it.**

## 14.1 What is re-measured, and what is not

**Re-measured**: section 13's *measured* quantities - the steer axis's
post-drive sweep, the gate openings it causes, the fused heading they move,
and the per-stop cost section 13.8 states as a bound.

**Not re-measured, and not in question**: section 13's *rules*. The
trailing-rate window, the drive-exact / steer-within-one-count verdict, the
demotion of the steer term from an equality test to a rate guard, and the
reasoning in 13.4 and 13.6 are plant-independent design, and the plant
change gives no reason to revisit any of them. Nothing in `config.yaml`,
`wheel_odometry.py` or `check_odometry.py` is touched by this section.

**Also not re-measured**: `EVIDENCE_LOCALIZATION.md`'s AMCL handover
figures (+0.5389 deg and +0.548 deg at two stops), which that file's
section 10 item 2 asks to be restated as a range or re-derived. They are a
different instrument reading a related mechanism, and re-deriving them
needs that file's own route re-driven on the new plant - inventory item 6,
still open. What this section supplies is the odometry half of the
interpretation, which is what the inventory scheduled.

## 14.2 The new plant, same recipe

`--phase postidle --idle 220 --truth`, seed 1, the same world
(`--print-world` into `/tmp/flat.sdf`), the same `_PROFILE`, the same stop.
Artefacts: `evidence/m5-40-postidle.{csv.gz,txt}`. Three checks, none failed.

| | section 13, old plant, container | **m5-40, new plant, WSL** |
|---|---|---|
| idle measured | 219.98 s | 219.97 s |
| **steer axis swept over the idle** | **2.3730 deg** | **0.1758 deg** |
| distinct steer counts visited / changes | - | 3 / 4, excursion 2 counts, net 0 |
| gyro samples suppressed | 98.47 % | **99.64 %** (21920 of 22000) |
| **separate openings of the gate** | **9** | **1** |
| **gate-open time** | **3.270 s** | **0.790 s** (0.36 % of the window) |
| **fused heading, whole idle** | **-0.6585 deg** | **-0.1076 deg** |
| as a rate over the whole idle | -0.1796 deg/min | -0.0293 deg/min |
| fused heading after the settling window | +0.000000 deg over 200 s | **-0.0009 deg over 219.2 s** |
| verdict true for | - | 99.65 % of the window, largest gap 0.0220 s against a 0.200 s timeout |

**The relaxation transient is gone, and that is the whole result.** Section
13.7's nine gate openings are one opening followed by eight, from t+11.5 s
to t+15.4 s, that section 13.8 names outright: *"All of it is the steer
axis's post-drive relaxation transient at t+11.5 s to t+15.4 s, where the
axis moves at up to 3 counts per 0.50 s window."* On the new plant **there
is no second opening at all.** The axis sweeps 0.1758 deg over the whole
idle instead of 2.3730 deg - it is held, which is what ten times the
proportional authority against a relaxing scrub moment predicts - and never
again exceeds the 1-count rate tolerance after the coast.

The single remaining opening is the coast, and section 13 already accounts
for that one as mostly real vehicle motion rather than estimator error:

| the one opening | |
|---|---|
| ends at | t_stop + 0.798 s |
| fused heading gained inside it | **-0.1067 deg** (99.2 % of the idle's total) |
| fused heading over the remaining 219.2 s | **-0.0009 deg** (0.8 %) |
| gate closed and quiet | **0.0000 deg** |
| the vehicle's own coast | 0.1403 m, drive wheel stops at t_stop + 0.284 s |

**Truth, as a reference section entering no verdict** (section 13.6's
premise, re-measured):

| from t_stop + 0.784 s, one window after the drive wheel stopped | old plant | **new plant** |
|---|---|---|
| steer axis swept | 2.3730 deg | **0.1758 deg** |
| TRUE position excursion | 0.001568 m | **0.000001 m** |
| TRUE heading, largest excursion | 0.001750 deg | **0.000030 deg** |
| **estimator error accrued while the wheel was provably parked** | - | **-0.001241 deg over 219.17 s = -0.000340 deg/min** |

Section 13.6's conclusion is therefore unchanged and slightly stronger: a
steer sweep with the drive count held does not turn this body, and the
sweep is now an order of magnitude smaller as well.

## 14.3 The one-variable A/B against the old plant, on this machine

Section 14.2 compares a WSL run against container figures, which is two
variables (`docs/LESSONS.md` 2026-08-05, entry 108: a comparison across two
environments is a first attempt, not a second). So the same recipe was run
again on this machine with **only the plant changed** - `model:=` pointing
at `git show HEAD:agv/forklift/model.sdf`, byte-verified identical to HEAD,
steer `p_gain` 6000, mast unchanged at 60000. Artefacts:
`evidence/m5-40-postidle-oldplant.{csv.gz,txt}`.

| | section 13, old plant, **container** | **old plant, WSL** | **new plant, WSL** |
|---|---|---|---|
| **steer axis swept** | **2.3730 deg** | **2.3730 deg** | **0.1758 deg** |
| separate gate openings | 9 | **9** | **1** |
| gate-open time | 3.270 s | 3.320 s | **0.790 s** |
| gyro samples suppressed | 98.47 % | 98.46 % | **99.64 %** |
| verdict true for | - | 98.47 % | 99.65 % |
| fused heading, whole idle | -0.6585 deg | -0.6933 deg | **-0.1076 deg** |
| first burst ends at | - | t_stop + 0.790 s | t_stop + 0.798 s |
| heading gained inside the first burst | - | -0.3128 deg | -0.1067 deg |
| **heading gained over the remaining 219.2 s** | - | **-0.3805 deg** | **-0.0009 deg** |
| gate CLOSED and quiet, the filter turning with no measurement | - | -0.0018 deg | **0.0000 deg** |
| the vehicle's own coast | 0.138 m | 0.1082 m | 0.1403 m |
| **estimator error while the wheel was provably parked** | - | **-0.382055 deg over 219.17 s** | **-0.001241 deg over 219.17 s** |
| as a rate over the parked interval | - | -0.104575 deg/min | **-0.000340 deg/min** |

**The old plant reproduces itself on this machine to four decimal places on
the quantity that matters** - the steer sweep is 2.3730 deg in the
container and 2.3730 deg here - so section 13's platform caveat ("Container
only. The owner's WSL2 host has never run this configuration") is retired
by this run, and the plant is the only variable left standing between the
two columns.

**The transient is a plant effect and nothing else.** Nine openings become
one, 2.3730 deg of sweep becomes 0.1758 deg, and the estimator error
accrued while the wheel is parked falls by a factor of **308**. This is the
inventory's open direction settled: it predicted "a stiffer hold plausibly
creeps less" and refused to assert it; it creeps less, by two orders of
magnitude.

## 14.4 The per-stop cost, restated

Section 13.8 states the bound this replaces:

> **worst case, a dwell beginning at the stop command: -0.331 deg of
> heading error, accrued in the first 16 s, then flat**; a dwell beginning
> 20 s after the stop: 0.000 deg.

`docs/LESSONS.md` 2026-08-04 (entry 94) already ruled that figure a sample
rather than a bound - one stop, one posture, one seed - and TODO carries it
with that caveat. **It stays a sample here**; what changes is its value and
its shape, and the shape is now simpler because there is only one gate
opening to account for.

| | old plant (WSL A/B) | **new plant** |
|---|---|---|
| a dwell beginning **at the stop command** | -0.6933 deg of fused heading, of which the vehicle really turned -0.1911 deg | **-0.1076 deg of fused heading, of which the vehicle really turned -0.0158 deg** |
| **estimator error over such a dwell** (fused minus true) | **-0.502 deg** | **-0.092 deg** |
| a dwell beginning **after the settling window** | -0.382 deg over 219 s | **-0.0012 deg over 219 s** |
| the settling window itself | ends at t + 15.4 s (section 13.7's last opening) | **ends at t + 0.798 s** |

**Three statements, each with its n.**

1. **A dwell that begins at the stop costs about -0.09 deg of estimator
   heading on this plant** (n = 1 stop, seed 1, flat ground, forks down,
   steer straight - the same single instance section 13.12 lists, so the
   same caveat applies unchanged).
2. **A dwell that begins after the vehicle has settled costs nothing
   measurable**: -0.0012 deg over 219 s, which is 0.4 % of the old plant's
   -0.382 deg and at the floor of what this instrument resolves.
3. **The settling window shrinks from ~16 s to under 1 s**, and what
   remains of it is the vehicle's own coast rather than the steer axis
   relaxing. That is the practically useful half: a route that stops and
   dwells no longer has to wait out a relaxation transient before its
   estimator is quiet.

**What this does NOT settle.** `EVIDENCE_LOCALIZATION.md`'s +0.5389 deg
EKF-handover figure and its +0.548 deg second stop are AMCL-side
measurements on the old plant, and they are not re-derived here (14.1).
This section removes the odometry-side mechanism that was the leading
candidate for explaining them; whether the AMCL figures move with it is
that file's measurement to take, on its own route.

## 14.5 How this section was run

**Measured alone, checked rather than remembered.** Both runs refuse to
start unless `pgrep -c -f` over the process pattern returns 0, print load,
`/dev/shm` count and a UTC timestamp, gate bring-up on `/forklift/odom`
appearing rather than on a sleep, and verify the count after teardown.
New plant: 0 before, 0 after, load 0.37, `/dev/shm` 690,
`2026-08-05T21:35:49Z` to `21:41:43Z`. Old plant: 0 before, 0 after, load
1.18, `/dev/shm` 722, `21:42:56Z` to `21:48:49Z`. Both drivers print the
committed model's `<p_gain>` lines before bring-up, so each artefact
records which plant it ran on.

**Both transports isolated on every run.** `GZ_PARTITION=m540postidle` /
`ROS_DOMAIN_ID=99` for the new plant, `m540postidleold` / `89` for the old
one - `gz transport` is not DDS and the ROS variable does not isolate the
simulator (`docs/LESSONS.md` 2026-07-27). Headless, `DISPLAY` and
`WAYLAND_DISPLAY` unset. **No RTF figure was taken and none is quoted.**

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m540postidle ROS_DOMAIN_ID=99      # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY

/usr/bin/python3 agv/forklift/scripts/check_odometry.py --print-world > /tmp/flat.sdf
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase postidle \
    --idle 220 --truth --csv agv/forklift/evidence/m5-40-postidle.csv   # gzipped after the run,
    #                                                     the writer confirmed gone first

# THE ONE ARGUMENT THAT DIFFERS FOR 14.3, and it is the whole A/B:
#   git show HEAD:agv/forklift/model.sdf > /tmp/m5-40-oldplant.sdf
#   ros2 launch ... model:=/tmp/m5-40-oldplant.sdf
```

`check_odometry.py`, `wheel_odometry.py`, `config.yaml`, `ekf.yaml` and
`launch/vehicle.launch.py` are byte-identical to their committed form.
The only file this brief changed in `agv/` that any run above reads is
`model.sdf` itself.

---

# 15. THE SAFE-SPEED READING CHANNELS — 2026-08-06 (m5-48)

**One shaft, read twice, and the two numbers the F-program's
cross-comparison needs derived from the noise those readings actually
have.** The headline is two figures and their `n`:

| | Value | Derived from |
|---|---|---|
| **discrepancy threshold** | **0.0308 m/s** | 4 × the measured σ of the channel difference, 13 200 paired samples over 660.0 s |
| **discrepancy time** | **200 ms** | the measured longest run of excursions above that threshold on the F-program's own 100 ms grid: **0 samples of 6 600** |

**Its honest name is a SINGLE-CHANNEL TESTED SYSTEM** — one shaft, one
measured quantity, two readings of it, which is what a real safe encoder
is (`docs/safety/SLS-STANDARDS-BASIS.md` F4). It is **never** called a
two-channel system: both readings die together with the shaft they read.
The **motion-present check** that covers that hole is a **STAND-IN** for
the mechanical fault exclusion a real system argues on the coupling, and
is labelled one everywhere it appears.

**No claim of any kind attaches to anything in this section.** No
Category, no Performance Level, no SIL, no PFH (ADR 0011 D5). The
readings reach the F-program as **standard data** over the process path.
Nothing here latches, limits, inhibits or stops anything; the protective
stop, the e-stop chain and safe torque off are onboard and hardwired
(invariant 1).

| Item | Value |
|---|---|
| Date | **2026-08-06**, owner's WSL, CEST |
| Brief | m5-48, task 2 of the re-ordered M5 closure plan |
| Host | WSL2, kernel `5.15.167.4-microsoft-standard-WSL2`, `nproc` 20, 15.8 GiB |
| Simulator | `gz sim --version` → **8.11.0**, headless (`-r -s`) |
| ROS | Jazzy, `rmw_fastrtps_cpp` |
| World | `sim/worlds/warehouse.sdf`, `world_name:=warehouse`, unedited |
| Isolation | `GZ_PARTITION=m548meas` **and** `ROS_DOMAIN_ID=64` on every run — gz transport is not DDS |
| Machine state | checked before each timed run and recorded in it: no simulator, no bridge, no vehicle node running; load average 0.06 or lower at bring-up |
| Runs | **three** full profiles, 660 s each: `20260806a`, `b`, `c`. `c` is the run of the committed tree and is what every figure below is quoted from unless a spread across all three is given |

## 15.1 The plant change, classified before it was made

`model.sdf` has a history — the 2026-08-05 steer-gain change required the
whole re-qualification round of `PLANT-CHANGE-INVENTORY.md` — so this
edit was classified by that file's method **before** it was made.

**What the edit is.** Two additional `JointStatePublisher` instances on
`drive_wheel_joint`, on `/forklift/gz/drive_speed/read_a` and `read_b`.
Nothing else: no link, joint, inertial, geometry, sensor, gain, limit,
mass or existing topic changed.

**What it touches, physically: nothing, and here is why.**
`JointStatePublisher` is a read-only post-update system — it publishes
joint state and writes nothing the physics integrates. The
joint-position and joint-velocity components it requires are **already
created for this same joint** by the instance that publishes
`/forklift/gz/joint_state`, so the edit does not even add a component.
By the inventory's own classification rule — *a figure is affected iff
its value depends on the change, directly or through the trajectory the
vehicle followed while the figure was taken* — **every figure in every
evidence file in this directory is class U**, because none of them
depends on how many read-only publishers exist.

**The one class that is not settled by that argument, and was measured
instead.** An additive edit can still move a figure derived from machine
load, because two more topics publish at the physics rate. So the
simulator's own real-time factor was measured with and without the two
systems, **alternating**, three captures of 60 s each:

| | run 1 | run 2 | run 3 | mean |
|---|---|---|---|---|
| without the two reads | 0.9902 | 0.9895 | 0.9913 | **0.9903** |
| with them | 0.9886 | 0.9892 | 0.9930 | **0.9903** |

n = 613 stats samples per capture; medians 0.9993–0.9997 in all six.
**No measurable cost**, and the two means agree to four decimals. The
probe world for this A/B is `model.sdf` spliced into a minimal world with
physics, user-commands and scene-broadcaster only — **no rendering
sensors** — so it isolates the two publishers rather than characterising
a full vehicle world. Stated rather than left as a hidden condition.

**What the edit does cost, measured on the other side of the bridge.**
The two reads publish at the world rate — `ros2 topic hz` reported
**500.011 Hz**, min 0.001 s, max 0.004 s, window 5510 — so bridging them
is real traffic. One `parameter_bridge` process carrying the joint-state
topic alone averaged **4.6 %** of one core; the same process carrying
all three averaged **7.6 %**. About three percentage points of one core,
n = 1 each, average-since-start CPU. That measured cost is why the
bridge and the node are behind `safe_speed:=true` rather than on by
default — and forgetting the argument is safe, because a missing reading
reads to the F-program as a demand.

## 15.2 What makes the two readings differ, and what deliberately does not

The plant hands both channels **the same number**, because it is the same
shaft. That is the design's point: the channels observe one physical
quantity, so a divergence is a channel fault and not an ambiguity between
two estimates.

Everything that makes the readings differ is the **reading head**,
modelled in `scripts/safe_speed_channels.py` and parameterised in
`config.yaml`'s `safe_speed:` block:

| Term | Value | Where it comes from |
|---|---|---|
| resolution | 4096 counts/rev, count = 1.53398e-3 rad = 0.1850 mm of tread | a **design value** of the commonest catalogue class. **No datasheet is quoted for it**, here or anywhere |
| mounting phase | drawn once per run, uniform over one count, per head | two heads on one disc sit at their own grid positions and no assembly resolves that to better than a count. It de-correlates the two heads' **quantisation** |
| read jitter | zero-mean Gaussian on the angle, σ = **one count**, drawn per head per sample | the smallest defensible non-zero figure, on the same reasoning `odometry.steer_zero_offset_rad` already uses in this file. A **design value**, not fitted |
| calibrated radius | 0.1206 m | its own parameter, equal today to the process encoder's and belonging to a different device. A radius error is **common mode** and cancels from the comparison — correctly, since both heads read one shaft through one radius |

**The channels are not filtered.** A filter would trade this noise for
lag in the one measurement SLS exists to make promptly. The noise is
rejected by the **discrepancy time** instead — which is precisely why
that time has to be derived from the noise and may not be picked.

**Predicted before it was measured**, from those parameters alone:
σ per channel = r·√2·σ_read/dt = 0.1206 × 1.4142 × 1.53398e-3 / 0.05 =
**5.23e-3 m/s**, and the difference √2 times that = **7.40e-3 m/s**.

## 15.3 The drive, and that it drove

`scripts/safe_speed_bench.py --drive`, five repetitions of a five-speed
profile — 0.05, 0.10, 0.30, 0.60, 1.00 m/s, each forward then astern,
segment length capped at 4 m of excursion — with 30 s of rest before and
40 s after, and a ground-truth re-centre between pairs so a 660 s profile
does not walk into the racking.

**50 segments, 0 held or blocked.** Achieved/commanded ran 0.96 to 1.00
across the whole range, from ground truth, per segment:

```
   L1 fwd 0.05  cmd +0.05 m/s   8.0 s  moved 0.397 m  achieved 0.050 m/s  ach/cmd 1.00
   L1 fwd 0.30  cmd +0.30 m/s   8.0 s  moved 2.382 m  achieved 0.298 m/s  ach/cmd 0.99
   L5 rev 1.00  cmd -1.00 m/s   4.0 s  moved 3.819 m  achieved 0.958 m/s  ach/cmd 0.96
```

The achieved column exists because a kinematic check that does not
retrace its segments cannot tell a followed command from a blocked one
(`docs/LESSONS.md` 2026-08-04). Full table:
`evidence/encoder/m5-48-drive-20260806c.txt`.

## 15.4 The measurement, and the derivation

**Channel noise**, against the noise-free speed over the same window (a
reference column written to the CSV and read by nothing on the vehicle):

| | run a | run b | run c |
|---|---|---|---|
| n (paired rows) | 13 220 | 13 223 | **13 200** |
| σ channel A | 0.005410 | 0.005383 | **0.005438** |
| σ channel B | 0.005458 | 0.005474 | **0.005464** |
| σ of the difference | 0.007740 | 0.007659 | **0.007696** |

against the 5.23e-3 and 7.40e-3 predicted in §15.2 — the model behaves
as its parameters say it should, within 4 %, three times. Means are zero
to six decimals: the heads add noise, not bias.

**The noise does not depend on speed**, which matters because one
threshold has to serve the whole range. By ground-truth body-speed band,
run c:

| band | n | σ of the difference |
|---|---|---|
| 0.00–0.02 m/s | 6165 | 0.007731 |
| 0.02–0.20 | 3266 | 0.007667 |
| 0.20–0.45 | 1643 | 0.007694 |
| 0.45–0.80 | 1357 | 0.007635 |
| 0.80–2.00 | 769 | 0.007670 |

**As the F-program sees it.** The F-OB runs at 100 ms
(`plc/forklift-safety/SPEC.md` §4.3) and these publish at 20 Hz, so the
monitor samples every second row: n = 6600, σ = 0.007687 m/s, **lag-1
autocorrelation −0.0105**. Consecutive F-samples are independent draws,
which is what makes a *run* of exceedances rare rather than expected —
and it is measured rather than assumed, because if the noise were
correlated the whole run-length derivation below would be wrong.

**How long noise excursions actually last** — the measurement the
discrepancy time is derived from, run c:

| threshold | exceeding samples | longest run | as time |
|---|---|---|---|
| 1 σ = 0.007696 | 1492 of 6600 | 6 | 0.600 s |
| 2 σ = 0.015392 | 198 | 2 | 0.200 s |
| 3 σ = 0.023088 | 11 | 1 | 0.100 s |
| **4 σ = 0.030783** | **0** | **0** | — |
| 5 σ = 0.038479 | 0 | 0 | — |

**The derivation, in one line each.**

1. **Threshold = 4 σ of the difference = 0.0308 m/s.** Four and not
   three because three still produced 11 single-sample exceedances in
   6600, and every one of those would be a nuisance demand under a
   two-cycle time; four produced none, in each of the three runs
   (0.030962 / 0.030638 / 0.030783 — the spread is 1 %).
2. **Time = 200 ms**, two F-cycles: the longest measured run above the
   threshold is **0 samples**, so the floor rather than the measurement
   sets it — and the floor is two cycles, because a single sample must
   never be able to demand on its own.
3. **It is not rounded.** Rounding up would buy nuisance immunity the
   measurement already shows is not needed, at the cost of detection;
   rounding down the reverse. The measured value needs neither.

**What the threshold costs in detection, said plainly.** A channel that
freezes while the vehicle runs shows a difference equal to the speed
itself, so the comparison sees a frozen channel only **above 0.0308 m/s**
of tread speed — about a tenth of the 0.3 m/s SLS regime. Below that the
cross-comparison is blind to a frozen channel, and what covers that
regime is the motion-present stand-in, not this threshold. The two
mechanisms are complementary by construction and neither is a substitute
for the other.

**A real fault is caught in one discrepancy time.** A frozen, dead or
diverging channel holds the difference above the threshold continuously
rather than in single samples, so the demand forms after 200 ms — two
F-cycles — with no dependence on the noise statistics above.

## 15.5 The motion-present stand-in, and the statistic that was measured rather than assumed

**A first version failed, and the failure is worth recording** because it
would have been invisible in review. The observation was written to read
the **median** of the per-ray range change between consecutive
navigation scans, the median being chosen for robustness against a person
or a truck crossing the field of view. Measured against ground truth over
run **a**'s 6538 sustained-motion samples it read **0.072 of the body speed with a
worst case of 0.00024**, and **1037 of those samples reported NOT MOVING
while the vehicle was driving**.

The mechanism is geometric, not statistical: a straight wall parallel to
the direction of travel returns the *same* range profile from every point
along it — `r(theta) = d / sin(theta)`, with no dependence on position —
so in an aisle a **majority** of usable rays do not change at all while
the vehicle drives. The median of the changes is therefore a measurement
of the degenerate majority.

**And the robustness the median was chosen for was the wrong direction to
optimise.** An object crossing the view makes the observation say MOVING
while the vehicle stands, which costs a withheld standstill confirmation
that SS1 pays for with its timeout. Missing real motion is the failure
that corroborates a lying encoder. The statistic is therefore chosen for
**sensitivity**, and its nuisance mode is the benign one.

Five statistics were logged per tick and scored on **sustained** regimes
only — 6535 moving samples, 5644 at rest, run c — because a row taken
while the vehicle accelerates away from rest measures the lag and not the
statistic:

| statistic | worst at rest | worst while moving | separation |
|---|---|---|---|
| median | 0.000000 | 0.000024 | — |
| q75 | 0.000002 | 0.000126 | 53× |
| q90 | 0.000010 | 0.002608 | 274× |
| **q95** | **0.000014** | **0.088928** | **6217×** |
| max | 0.000038 | 0.159931 | 4193× |

**q95 is what the node reads.** At the slowest speed the profile drove,
0.05 m/s, its worst observed rate was 0.088928 m/s — 1.78 times the body
speed — and across the whole range the ratio ran 0.715 to 25.3.

**The threshold, 0.0014 m/s**, sits between the two measured bounds:
**98× above** the worst sustained-rest value and **64× below** the worst
sustained-motion value, and **none** of the 6535 sustained-motion samples
reads as stopped at it. At the worst measured ratio (0.715, the highest
speed band) it corresponds to a body speed of 0.0020 m/s, which is where
`navigation.zero_speed_mps` already puts zero — **and that conversion is
an extrapolation below 0.05 m/s**, the slowest speed driven, stated as
one rather than quoted as a detection limit.

**The floor it sits above is the simulation's, not a real device's.**
`model.sdf` declares no range noise on the navigation lidar, so a
stationary vehicle in a static world produces range changes of exactly
zero and the 0.0000143 m/s above is scan-timing residue. A real
installation's floor is its rangefinder's noise, which is larger, and
this threshold would be set by measuring it on the device.

**The two lags, and they are asymmetric on purpose.** Over 50 motion
onsets in run c, **none undetected**:

| | min | median | max |
|---|---|---|---|
| onset → verdict MOVING | 0.000 s | 0.000 s | **0.050 s** |
| stop → verdict STOPPED | 0.500 s | 0.550 s | 0.600 s |

Prompt to say moving, late to say stopped — the direction that matters,
and the release lag is the configured 0.50 s hold plus a scan. The nine
sustained-motion samples that read NOT MOVING in run c all sit inside
that 50 ms onset window; they are the lag, not a missed detection.

**Every uncertainty resolves to MOVING.** No scan, a scan older than
0.30 s, fewer than 36 usable ray pairs, an empty horizon: all of them
publish `motion_present` `TRUE` with `motion_observation_valid` `FALSE`,
so a consumer can tell *observed moving* from *could not observe* while
both remain the same demand. A beyond-range return is a measurement of
clear space and not missing data — it simply carries no information about
how far anything moved, so it yields no ray pair rather than a
comfortable one. Over run c the observation could not be made in **2 of
13 222** ticks, both at bring-up before a second scan existed.

## 15.6 What this section does not establish

- **No integrity claim.** Not a Category, not a Performance Level, not a
  SIL, not a PFH, not a diagnostic-coverage figure — for the channels,
  for the comparison, for the stand-in, or for anything downstream.
- **The two readings are not two channels of a redundant architecture.**
  They share the shaft, the joint, the simulator's own number and the
  physics that produced it. Everything they do not share is modelled in
  one Python file.
- **The motion-present check is a stand-in for a fault exclusion**, not a
  substitute for one and not what a standard requires.
- **The discrepancy constants belong to the F-program, which does not
  exist yet.** They are derived here and are *requested* into
  `plc/forklift-safety/SPEC.md`; nothing in `agv/` consumes them, and no
  file in this directory implements a cross-comparison.
- **No transport for these readings is specified here.** How they reach
  the F-program is the next brief's; this directory publishes topics.
- **A frozen channel below 0.0308 m/s of tread speed is not detected by
  the comparison**, by construction — §15.4 states the figure rather than
  leaving it to be discovered.

## 15.7 Reproducing this

```bash
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=m548meas ROS_DOMAIN_ID=64      # BOTH, every run
unset DISPLAY WAYLAND_DISPLAY

# no ROS, no simulator - the head model and the observation
python3 agv/forklift/scripts/safe_speed_channels.py --selftest

# the run. ONE CSV PER SESSION, unique name per start: the node
# truncates at open, so a shared path destroys the earlier run
ros2 launch agv/forklift/launch/vehicle.launch.py \
    world:=sim/worlds/warehouse.sdf world_name:=warehouse \
    safe_speed:=true \
    safe_speed_csv:=agv/forklift/evidence/encoder/m5-48-channels-STAMP.csv \
    nodes:=false wheel_odom:=false imu_gate:=false ekf:=false
python3 agv/forklift/scripts/safe_speed_bench.py --drive --loops 5

# no ROS, no simulator - the whole derivation, printed with its arithmetic
python3 agv/forklift/scripts/safe_speed_bench.py \
    --analyse agv/forklift/evidence/encoder/m5-48-channels-STAMP.csv
```

`ekf:=false wheel_odom:=false` because the estimator is not in this
question and the launch refuses a filter with no odometry source; the
ground-truth column the CSV records comes from `/forklift/odom`, which is
the simulator's own pose and is **written to the CSV and read by
nothing**.

The seed is **not** fixed. Each run draws its head phases and jitter
afresh and logs the seed at start-up (`901305242` for run c), which is
what makes three runs three draws rather than one repeated — and the
three σ figures of §15.4 agreeing to 1 % is the statement that matters.
`--seed` exists for the case where a single run must be replayed.

Committed alongside: `evidence/encoder/m5-48-channels-20260806{a,b,c}.csv.gz`,
`m5-48-drive-*.txt`, `m5-48-analyse-*.txt`. Run **a** predates the
statistic instrumentation, so its analysis prints no §7 table.

The three CSVs were gzipped **after** the writer was confirmed gone —
`pgrep` empty, not assumed — and verified with `gzip -t`
(`docs/LESSONS.md` 2026-07-28 and 2026-07-30, where a live file was
compressed under its writer and the halves of one stream were mistaken
for copies). `--analyse` reads the plain `.csv`, so a re-analysis
`gunzip -k`s first. Each run has its own name: a repeat that reuses its
predecessor's filenames destroys the comparison it exists to make.
