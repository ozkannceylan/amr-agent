# EVIDENCE — m5-ver3 fusion: the odom-frame EKF (F2 Task 1)

Every number below was measured on this rig on **2026-08-26**, and the
instrument that produced it is named beside it. A *configured* figure is
what `ekf.yaml`, `config.yaml` or `gazebo/forklift_ver3/model.sdf` asks
for; a *measured* figure came off this plant through a named tool, in a
named session. The two columns are never mixed.

**The rig.** WSL2 on Windows 11 · Ubuntu 24.04.4 LTS · 13th Gen Intel
Core i9-13900H, 20 threads · NVIDIA GeForce RTX 4050 Laptop GPU ·
gz-sim **8.11.0** · ROS 2 **Jazzy** · `robot_localization` **3.8.3**
(`ros-jazzy-robot-localization`, installed on the rig, not vendored).
Repository at `/mnt/c/Users/ozkan/projects/amr-agent`, branch `m5-ver3`.
Every session below was taken under `./m5_ver3/m5v3.sh start --headless`
with the GPU preflight passed (`gpu: D3D12 (NVIDIA GeForce RTX 4050
Laptop GPU)`), **the stack stopped and restarted before every drive**, and
nothing else running on the machine.

**What is new here, and what is only extended.**

| Tool | What it answers | New here |
|---|---|---|
| `robot_localization ekf_node` | the fused estimate, `/m5v3/odometry/filtered`, and `odom` → `base_link` | ● |
| `m5_ver3/ekf.yaml` | what is fused and what is refused, entry by entry | ● |
| `tools/sensor_evidence.py record` | now captures the fused stream beside the raw one and the truth | extended |
| `tools/sensor_evidence.py analyse` | scores the fused stream and **subtracts the two**, with no ROS | extended |
| `tools/evidence_core.py` | `compare_drift()`, `sdf_link_pose()` — the new arithmetic. Suite 82 → **106** tests, selftest 16 → **22** checks | extended |

**The preamble the tables below cannot be read without.**

**The wheel odometry's POSE IS NOT FUSED and its own message says so.**
`nodes/wheel_odometry.py` publishes a pose covariance of **1000.0 on all
six axes** — a deliberate do-not-fuse flag, because a dead-reckoned pose
has unbounded error and no honest fixed number exists for it
(`config.yaml`, `wheel_odom.covariance.unused`). `ekf.yaml`'s
`odom0_config` is the second, independent refusal: the six pose flags are
`false`, so a filter configured against this stack cannot fuse that pose
however the covariance is edited.

**Two entries of fifteen are true on the twist**, and that is the whole
of what the wheel odometry contributes:

```
   x     y     z    roll  pitch  yaw    vx    vy    vz   vroll vpitch vyaw   ax   ay   az
 false false false false false false  TRUE  false false false false TRUE  false false false
```

`vy` is `false` **by owner ruling**, and §4 measures what that costs on
this vehicle. It is not a noise channel: `wheel_odom_core.py` computes
`vy = d · yaw_rate` with `d = 0.50 m`, the lateral velocity `base_link`
genuinely has because it stands half a metre forward of the rear axle,
and that file's own header warns that dropping the term *"quietly drops
the lateral term and there is no symptom until something fuses the
twist."* This is that something.

**The IMU contributes two entries and has no orientation to contribute.**
`model.sdf` sets `<enable_orientation>false</enable_orientation>` because
gz derives an IMU's orientation from the link's pose in the simulator —
ground truth wearing a sensor's name. `imu0_config` fuses `vyaw` (the
gyro's z axis) and `ax`, and refuses all three orientation entries.

**Ground truth is the reference and never an input.**
`/forklift/gz/odom` appears in no `odomN`, `poseN` or `twistN` entry of
`ekf.yaml`, and there is exactly one `odom0` and one `imu0` in that file,
so there is nowhere for a third input to hide (F2 global constraint 13).

---

## 1. The filter is up, and it is the stack's sixth child

**Instrument:** `./m5_ver3/m5v3.sh start --headless`, `status`,
`ros2 topic hz`, `ros2 run tf2_ros tf2_echo`.

```
m5-ver3: partition m5v3, domain 97
  world      ALIVE   pid 80576   logs/world.log
  bridge     ALIVE   pid 80658   logs/bridge.log
  imgbridge  ALIVE   pid 80664   logs/imgbridge.log
  odom       ALIVE   pid 80674   logs/odom.log
  imutf      ALIVE   pid 80686   logs/imutf.log
  ekf        ALIVE   pid 80730   logs/ekf.log
6 alive, 0 dead.
```

| Claim | Measured |
|---|---|
| `/m5v3/odometry/filtered` is published | **50.002 Hz** of wall clock (`ros2 topic hz`, 51-sample window), **50.0000 Hz** of the plant's own sim stamps over every drive session below |
| against a configured | `config.yaml` `ekf.frequency_hz` = **50.0** |
| `odom` → `base_link` is on `/tf` | present, `tf2_echo odom base_link` at 1 Hz returns a transform at every sim instant it is asked for |
| the transform moves | yaw **+0.009 rad** at t+26 s with the vehicle standing still — the fused gyro bias, §2.5 |
| `dt` between filter outputs | `dt_med` **0.02000 s**, `dt_max` **0.02200 s** over 2009 samples of a 40 s run |

`dt_max` is **one cycle in 2009 arriving 2 ms late**, which is one
physics step of the world it is riding. It is reported rather than
rounded away: at 50 Hz an output that slips a step is 1 ms of extra
staleness on a transform, against a vehicle covering 14 mm per cycle at
its 0.7 m/s cruise.

**`logs/ekf.log` carries exactly one line for a whole session** —
`Waiting for clock to start...`, printed once at construction before
`/clock` reaches it. No `Failed to meet update rate` appears in any of
the eight drive sessions. That silence is not entirely good news, and
§2.2 and §2.6 are why.

---

## 2. Six things measured about `robot_localization` on THIS plant

Each of these was measured before the filter was wired into `m5v3.sh`,
by running `ekf_node` by hand against a live stack, because each of them
changes what the configuration has to say.

### 2.1 The covariances that decide the blend are on the wire, and they are the model's

**Instrument:** `ros2 topic echo /forklift/gz/imu --once`, domain 97,
vehicle at rest.

`agv/forklift/ekf.yaml` (read-only prior art, another track) asserts that
"the IMU's is filled by gz from the noise stddev declared in model.sdf".
On **this** bridge, with **this** ros_gz, that is true — measured rather
than inherited:

| Channel | `model.sdf` σ | σ² | **On the wire** | Match |
|---|---|---|---|---|
| `angular_velocity_covariance[0,4,8]` | 0.001745 rad/s | 3.04502500e-06 | **3.0450250960711855e-06** | 3.2e-08 |
| `linear_acceleration_covariance[0,4]` | 0.01076 m/s² | 1.15777600e-04 | **1.1577759869396687e-04** | 1.1e-08 |
| `linear_acceleration_covariance[8]` | 0.01278 m/s² | 1.63328400e-04 | **1.6332839732058346e-04** | 1.6e-08 |

The last column is the relative difference, and it is **not zero** — the
wire values are the declared σ² to about **one part in 10⁸**, which is a
`float32` round-trip of the stddev and not a rounding of the tables here.
Taking the square root back out gives 0.001745000028, 0.010759999939 and
0.012779999895 against 0.001745, 0.01076 and 0.01278. Said plainly: the
bridge carries the model's numbers, through a 32-bit field.

So the weighting between the two sensors is set by two
datasheet-derived numbers and by no hand in `ekf.yaml`: the wheel
odometry's twist covariances come from `config.yaml`'s
`wheel_odom.covariance` block (F1's measured quantiser dither,
`EVIDENCE_SENSORS.md` §3), the IMU's come from `model.sdf` through the
bridge. `ekf.yaml` carries **no covariance of any kind** and leaves
`process_noise_covariance` and `initial_estimate_covariance` at the
package defaults, which is prior art's ruling and is kept for its reason:
they are the two knobs a drift figure is most easily flattered with.

**What the covariance does NOT contain, stated rather than hidden.** The
gyro's figure is its **white noise only**. `model.sdf` also declares
`bias_mean 0.002618 rad/s` with `bias_stddev 0.0`, which fixes the
magnitude and lets gz draw the **sign** per run. §2.5 measures that draw
on five runs and §3.1 shows it deciding whether fusion helps or hurts a
straight line.

### 2.2 Without a transform for `imu_link`, the filter drops the IMU and says NOTHING

**Instrument:** `ekf_node` by hand against a live stack, vehicle at rest,
sampling `/odometry/filtered`; run twice, with and without
`ros2 run tf2_ros static_transform_publisher`.

The bridged IMU is stamped `frame_id: imu_link` (`model.sdf`'s
`<gz_frame_id>`), and `robot_localization` transforms every sample into
`base_link_frame` before fusing it.

| | `twist.angular.z` at rest | `pose.orientation.z` after ~20 s | `twist.linear.x` at rest | log says |
|---|---|---|---|---|
| **no** `base_link` → `imu_link` | **0.0** exactly | **0.0** exactly | **0.0** exactly | *nothing at all* |
| **with** the static transform | **−5.06e-05 rad/s** | −0.00252 → **−0.00725** | **−5.76e-04 m/s** | *nothing at all* |

**The filter runs, publishes at its configured rate, emits a transform,
and has silently discarded an entire sensor.** There is no warning, no
error and no diagnostic in `logs/ekf.log` in either case. This is the
strongest argument in this file for the stack's shape: `imutf` is a child
of `m5v3.sh` with its own log and its own line in `status`, so a
transform that failed to start is a **DEAD** child and a non-zero exit
from `start`, rather than a filter quietly running on one sensor.

The mount itself is `model.sdf`'s `imu_link` pose, `(-0.50, 0, 0.25)`,
copied into `config.yaml` as `vehicle.imu_mount` because a shell cannot
read XML — and **diffed against the model on every `analyse` run**
(`evidence_core.sdf_link_pose`, five unit tests), exactly as the sensor
rates already are. No disagreement was printed on any session here.

### 2.3 Gravity removal kills the accelerometer channel on this device

**Instrument:** the same by-hand `ekf_node`, static transform present,
`imu0_remove_gravitational_acceleration` flipped.

`robot_localization` removes gravity by rotating `(0,0,g)` by the IMU's
**own** orientation quaternion, and falls back to the filter's estimated
attitude only when the message marks its orientation absent the REP-145
way, with `orientation_covariance[0] = -1`. This device marks nothing:

```
orientation:            x: 0.0  y: 0.0  z: 0.0  w: 0.0
orientation_covariance: [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
```

A quaternion of length **zero**. `robot_localization` finds it
un-normalised, normalises it, and divides by zero.

| `imu0_remove_gravitational_acceleration` | `twist.linear.x` at rest | log |
|---|---|---|
| `true` | **0.0 exactly** — the acceleration channel is dead | `An input was not normalized, this should NOT happen, but will normalize` — **once** |
| `false` | **−5.76e-04 m/s** — `ax` is being fused | *nothing* |

The gyro carries on working in both cases. So the failure is **silent,
partial, and looks like a working filter** — one INFO-adjacent warning at
startup and a filter that has lost half its IMU. `ekf.yaml` sets it
`false`, and nothing is lost by that: gravity is entirely in `az` on a
level vehicle on a flat floor, `az` is not fused and `two_d_mode` holds
it at zero, and the channel that **is** fused has no gravity in it to
remove.

### 2.4 The lever arm is not corrected, and the arithmetic says how much that is

The IMU sits **0.50 m behind `base_link`** (§2.2). `robot_localization`
**rotates** an IMU's angular velocity and linear acceleration into
`base_link` and does **not** correct for the offset — there is a `@todo`
in its own source saying so. Two consequences, and they are not the same
size:

- **Angular velocity: no error at all.** A rigid body has one angular
  velocity, at every point of it. `vyaw` — the channel this whole phase
  exists for — is untouched by the lever arm.
- **Acceleration: a real term, and it lands on the axis that IS fused.**
  For a mounting straight behind the origin, `ω×(ω×r)` works out to
  `+ω²d` along body **+x** — so the centripetal term is on **`ax`** —
  while the tangential term `α×r` is `−αd` on **`ay`**, which
  `imu0_config` does not fuse. Measured peak yaw rate on this plant:
  **0.2687 rad/s** on `square` and 0.2062 on `corner_creep` (the gyro's
  own z channel over the whole run), so `ω²d` peaks at **0.0361 m/s²**
  and **0.0213 m/s²**. That is **3.4×** the accelerometer's own noise σ
  of 0.01076 and **1.8×** its modelled 0.0196 m/s² bias: a real
  systematic term on a fused channel, present only while the vehicle
  turns.

This is stated rather than corrected because correcting it would mean a
node between the bridge and the filter, and this task's job was to
measure what the off-the-shelf filter does with this plant's sensors.

### 2.5 The gyro bias is drawn per run, and the draw is measured

**Instrument:** `evidence_core.mean()` over the **pre-roll** window of
each drive session — 400 IMU samples with the truck standing at the spawn
pose, before `drive_route.py` is started.

| Session | profile | **gyro z bias, this run** | accel x bias |
|---|---|---|---|
| `…-082850` | straight 1 | **+0.002617** rad/s | −0.020404 m/s² |
| `…-083007` | straight 2 | **+0.002588** rad/s | +0.019985 m/s² |
| `…-083112` | straight 3 | **−0.002789** rad/s | −0.018866 m/s² |
| `…-083216` | square | **−0.002670** rad/s | +0.019177 m/s² |
| `…-083330` | corner_creep | **−0.002633** rad/s | +0.019175 m/s² |
| `…-083525` | straight (A/B) | **−0.002729** rad/s | −0.018866 m/s² |

Magnitude against `model.sdf`'s configured `bias_mean 0.002618`: the six
draws read 0.99–1.07 of it. **The sign is not repeatable and a consumer
may not assume it** — which `EVIDENCE_SENSORS.md` §2 established at rest,
and §3.1 below shows deciding the *direction* of what fusion buys.

### 2.6 `ekf_node` is silent about an input that never arrives

**Instrument:** `ekf_node` by hand with `odom0` pointed at
`/m5v3/wheel_odom_TYPO`, a topic nobody publishes, 30 s.

```
[INFO] [1787724686.269166586] [m5v3_ekf]: Waiting for clock to start...
[INFO] [1787724716.101569124] [rclcpp]: signal_handler(SIGINT/SIGTERM)
```

That is the **whole** log. The node starts, advertises, publishes a
transform and never says that half its configuration addresses nothing.
`sensor_timeout` produces no message either; it governs whether a
measurement contributes, not whether anybody is told.

**So this stack does not rely on the filter's log, and says so rather
than wrapping the filter in bespoke monitoring.** Three instruments
answer "is the filter actually being fed", and all three are already
here:

1. `m5v3.sh status` — the child by name, ALIVE or DEAD, exit 0 only if
   every one is alive.
2. `ros2 topic hz /m5v3/odometry/filtered` — an output at 50 Hz proves
   the filter is cycling, and nothing more.
3. **`sensor_evidence.py record`** — `ekf_odom` is a REQUIRED stream, so
   a run recorded against a filter that is not publishing is refused by
   the stream's own name inside `evidence.wait_first_s`, before a single
   figure is timed. A missing input topic upstream of the filter shows up
   the same way, one stream earlier.

`print_diagnostics` is left **false** for the same reason it is not
relied on: there is no diagnostic aggregator on this stack, and
information written to nobody is not an instrument.

---

## 3. Drift, per profile: raw wheel odometry vs EKF vs ground truth

**Instrument:** `sensor_evidence.py record --drive <profile>` then
`analyse`, five sessions, stack restarted before each. Both estimates are
scored against the **same** ground truth by the **same** function
(`evidence_core.score_drift`) through the **same** spawn-frame transform
(`SpawnFrame`, `p' = R(−ψ₀)·(p − p₀)`, ψ₀ = π). **Every score is
ABSOLUTE**: no initial offset is removed and no per-run constant is
fitted.

`analyse` refuses a drive session whose first ground-truth sample is more
than 0.05 m or 0.02 rad from `vehicle.spawn`; all eight sessions read
**exactly** `(-17.000000, 10.000000) yaw 3.141590`, 0.0000 m and
0.00000 rad off.

### 3.0 The raw wheel odometry did not move, and that is the control

Adding two children to a stack whose figures are all measured under a
real-time factor is a change to the plant until it is shown not to be.
The raw wheel-odometry row is the same estimator, the same settings and
the same instrument as F1.5's re-measured table
(`EVIDENCE_SENSORS.md` §3), and it repeats:

| Profile | figure | F1.5, no EKF in the stack | **F2 Task 1, EKF running** |
|---|---|---|---|
| `straight` | path error | +4.23 % | **+4.22 %** (all three runs) |
| | end error | 0.5778 m | **0.5806 / 0.5806 / 0.5808 m** |
| | end heading | −0.0574 rad | **−0.0576 / −0.0577 / −0.0577 rad** |
| `square` | path error | +9.78 % | **+9.78 %** |
| | end error | 0.6712 m | **0.6724 m** |
| | end heading | +0.5291 rad | **+0.5269 rad** |
| `corner_creep` | path error | +7.65 % | **+7.65 %** |
| | end error | 0.1945 m | **0.1943 m** |
| | end heading | +0.0156 rad | **+0.0150 rad** |

Every figure repeats to **≤3 mm and ≤0.0022 rad**. The `straight` × 3
spread of the raw end error is **0.2 mm** over 11.6 m. The two new
children cost the plant nothing measurable, and every difference in the
tables below is the filter and not the load.

### 3.1 `straight` × 3 — and the answer depends on which way the bias fell

23.5 s of profile, ≈11.6 m, no steer input at all. The wheel odometry's
heading error here is its **steer bias** carried through: +0.005 rad of
believed steer that is not there, integrated over the **18.5 s** the
profile is actually moving (`config.yaml` predicts 3.33 mrad/s at
0.7 m/s; the ramps run slower, and the measured −0.0577 rad is what that
comes to).

| Run | gyro bias draw | raw end error | **EKF end error** | raw end heading | **EKF end heading** | heading removed |
|---|---|---|---|---|---|---|
| 1 `…082850` | **+0.002617** | 0.5806 m | **0.5080 m** | −0.0576 rad | **−0.0227 rad** | **60.7 %** |
| 2 `…083007` | **+0.002588** | 0.5806 m | **0.5090 m** | −0.0577 rad | **−0.0237 rad** | **58.9 %** |
| 3 `…083112` | **−0.002789** | 0.5808 m | **0.6393 m** | −0.0577 rad | **−0.0691 rad** | **−19.9 %** |

| Run | raw rms | EKF rms | raw worst | EKF worst | raw path | EKF path |
|---|---|---|---|---|---|---|
| 1 | 0.5244 m | **0.4946 m** | 0.8020 m | **0.7780 m** | +4.22 % | +4.23 % |
| 2 | 0.5156 m | **0.4935 m** | 0.8023 m | **0.7768 m** | +4.22 % | +4.22 % |
| 3 | 0.5236 m | **0.5506 m** | 0.8009 m | **0.8269 m** | +4.22 % | +4.23 % |

**The sign of what fusion buys on a straight line is the sign of that
run's gyro bias draw, and it went both ways in three runs.** The wheel
odometry's heading error is **negative** on every run (the steer bias
turns it one way, and that is deterministic to 0.0001 rad). A
**positive** bias draw opposes it and the fused heading is pulled towards
truth; a **negative** draw adds to it and the fused heading is pushed
further out. Run 3 is the second case, and so is the A/B `straight` of
§4 (bias −0.002729, heading −19.0 %): **four straight-type runs, four
times the sign of the gain equals the sign of the draw.**

This is not a defect in the filter and it is not corrected here. It is
what fusing an **uncompensated** MEMS gyro with a **biased** steer
encoder does: two systematic errors, neither of which any diagonal
covariance can represent, and the filter is blending their *noise*
models. `ekf.yaml` says so at the top of the file; this is the
measurement of it. **A three-run convention is what made it visible** —
one run would have published "fusion removes 60 % of the straight-line
heading error" and been wrong about the vehicle.

The **magnitudes** are not symmetric (run 1 moves +0.0349 rad, run 3
moves −0.0114 rad) and this file does not claim to explain that; the
sign is the claim.

### 3.2 `square` — four hard corners, and the heading is what fusion is for

Session `drive-square-20260826-083216`, 40.9 s of profile, gyro bias draw
−0.002670 rad/s. The plant turned **+6.2875 rad** — 0.0043 rad **past** a
full turn (2π = 6.283185), so this profile returns to within a quarter of
a degree of its **starting heading**, which matters for §4.

| Figure | ground truth | raw wheel odom | **EKF** | removed | of raw |
|---|---|---|---|---|---|
| path | 7.5352 m | 8.2723 m (**+9.78 %**) | 6.5846 m (**−12.62 %**) | — | — |
| turned | +6.2875 rad | +6.8144 rad | +6.6773 rad | — | — |
| **end error** | — | **0.6724 m** | **0.4515 m** | +0.2208 m | **32.8 %** |
| **END HEADING** | — | **+0.5269 rad** | **+0.3887 rad** | +0.1382 rad | **26.2 %** |
| rms over run | — | 0.3956 m | 0.7838 m | −0.3882 m | **−98.1 %** |
| worst | — | 0.6920 m | 1.3251 m | −0.6331 m | **−91.5 %** |
| closure | 0.0995 m | 0.5925 m | 0.3563 m | — | — |

**The headline and the warning are in the same table.** The gyro removes
**26.2 % of the four-corner heading error** and **32.8 % of the end
position error** — and the filter's **rms doubles** and its path comes
out **12.6 % SHORT** where the raw estimate is 9.8 % long. A path that is
short is the signature of a missing lateral velocity, not of a noisy one:
§4.

### 3.3 `corner_creep` — one sustained corner, and the plant is already honest

Session `drive-corner_creep-20260826-083330`, 22 s of profile, one
0.785 rad steer held for 14 s at 0.3 m/s, gyro bias draw −0.002633 rad/s.
The plant turned **+2.8508 rad** = 163°, so this profile ends **nowhere
near** its starting heading.

| Figure | ground truth | raw wheel odom | **EKF** | removed | of raw |
|---|---|---|---|---|---|
| path | 3.9697 m | 4.2731 m (**+7.65 %**) | 3.9540 m (**−0.39 %**) | — | — |
| turned | +2.8508 rad | +2.8659 rad | +2.8460 rad | — | — |
| end error | — | **0.1943 m** | **1.0565 m** | −0.8621 m | **−443.6 %** |
| **END HEADING** | — | **+0.0150 rad** | **−0.0070 rad** | +0.0081 rad | **53.7 %** |
| rms over run | — | 0.1594 m | 0.6768 m | −0.5174 m | **−324.6 %** |
| worst | — | 0.2115 m | 1.0640 m | −0.8524 m | **−403.0 %** |

**There was almost no corner heading error left to remove, and the filter
removed half of what there was.** F1.5 retuned this plant so the truck
takes 1.005 of its kinematic yaw at creep (`EVIDENCE_LATERAL_TUNE.md`);
the raw estimate's heading is already only **0.0150 rad** out over a 163°
turn, and the EKF takes it to **−0.0070 rad**. That is 53.7 % of a
number that was already small — and it is the honest reading of the
gyro's value on a floor with no slip in it. **F2 Task 2's slippery
variant is where this column is supposed to earn its keep**, because
scrub is exactly the error dead reckoning cannot see and a gyro can.

**And the position figures are catastrophic, by a mechanism that was
predicted before it was measured.** −0.86 m of end error, four times the
rms. §4.

---

## 4. What refusing `vy` costs, measured both ways

`ekf.yaml` fuses the wheel odometry's `vx` and `vyaw` and **refuses
`vy`**, by owner ruling (F2 Task 1 brief). This section is the same
filter, the same profiles and the same instrument with the single flag
`odom0_config[7]` flipped to `true`, so the ruling can be re-decided
against a measurement rather than against an argument.

**The prediction, written from the kinematics before the runs.**
`base_link` stands `d = 0.50 m` forward of the rear axle, so its
body-frame velocity is `(v_rear, d·ω)` — the `vy` term is a **kinematic
identity**, not noise. `robot_localization`'s motion model is
omnidirectional and knows nothing about `d`, so with `vy` unobserved the
filter integrates `base_link` **as though it were the rear axle**. The
resulting position error is `d·|û(ψ_end) − û(ψ₀)|`: it **cancels** on a
profile that ends on its starting heading and reaches `2d = 1.00 m` on
one that ends reversed. For `corner_creep`'s 2.8508 rad that predicts
**0.99 m**.

| Profile | figure | raw wheel odom | **EKF, `vy` FALSE (as ruled)** | **EKF, `vy` TRUE** |
|---|---|---|---|---|
| `straight` | end error | 0.5806 m | 0.5080 m | 0.6198 m ¹ |
| | rms | 0.5244 m | 0.4946 m | 0.5421 m ¹ |
| `square` | path error | +9.78 % | **−12.62 %** | **+12.25 %** |
| | end error | 0.6724 / 0.6777 m | **0.4515 m** (−32.8 %) | **0.5897 m** (−13.0 %) |
| | END HEADING | +0.5269 / +0.6476 rad | **+0.3887 rad** (−26.2 %) | **+0.5485 rad** (−15.3 %) |
| | rms | 0.3956 / 0.3984 m | **0.7838 m** (**+98 %**) | **0.3430 m** (−13.9 %) |
| | worst | 0.6920 / 0.7049 m | **1.3251 m** (**+92 %**) | **0.6095 m** (−13.5 %) |
| `corner_creep` | path error | +7.65 / +7.64 % | **−0.39 %** | **+7.67 %** |
| | end error | 0.1943 m | **1.0565 m** (**+444 %**) | **0.1557 m** (−19.9 %) |
| | END HEADING | +0.0150 / +0.0155 rad | −0.0070 rad (−53.7 %) | −0.0056 rad (−64.0 %) |
| | rms | 0.1594 m | **0.6768 m** (**+325 %**) | **0.1410 m** (−11.5 %) |
| | worst | 0.2115 m | **1.0640 m** (**+403 %**) | **0.1885 m** (−10.9 %) |

¹ the `vy`-true `straight` drew a **negative** gyro bias (−0.002729), so
it is §3.1's second case and is not comparable with the `vy`-false
straights that drew positive ones. On a straight line `ω ≈ 0` and
therefore `vy = d·ω ≈ 0`, so this flag cannot be what moved it — which is
itself the control: **the flag changes nothing on a profile with no
corner in it.**

**Three readings, and they agree with the prediction.**

1. **The predicted offset is there and it is the right size.**
   `corner_creep`'s end error moves 1.0565 → 0.1557 m when `vy` is fused:
   **0.9008 m**, against the formula's **0.9894 m**. The formula is a
   ceiling — it assumes the whole offset is still owed at the end — and
   the measurement lands **9 % under** it, because the profile's heading
   history is not one clean arc and part of the offset is spent before
   the run stops. It is the right size and the right sign, which is what
   was being tested.
2. **`square` hides it in the end error and shows it in the rms.** That
   profile turns +6.2875 rad — within 0.0043 rad of a full turn — so
   `d·û(ψ)` returns to where it started and the **end** error barely
   feels it (0.4515 vs 0.5897 m, and the `vy`-false run happens to read
   *better*). Over the run it is not hidden at all: the rms **doubles**
   and the worst error **nearly doubles**. A reader with only the end
   error would have drawn the opposite conclusion, which is why this
   instrument prints four figures and not one.
3. **`vy` true makes every figure on every cornering profile better than
   the raw estimate it was built from; `vy` false does not.** With the
   flag on, the filter beats raw dead reckoning on end error, heading,
   rms and worst, on both cornering profiles. With it off, it beats raw
   on heading and loses on rms and worst.

**The shipped configuration is `vy` FALSE, as ruled.** The measurement is
recorded here so the ruling can be revisited on one line of `ekf.yaml`,
and this file makes no claim about which the owner should choose. What it
does claim, with numbers: on this vehicle `vy` is **not** a noise channel
and refusing it costs **0.90 m of end error on a 163° turn** and
**doubles the rms over a square**.

---

## 5. What fusion cannot fix, and the F3 handoff

**Every figure in §3 still grows without bound, and no line of `ekf.yaml`
changes that.** Both inputs are *rates*. The filter integrates them, and
the integral of a biased rate is a pose whose error has no ceiling:

- **Along-track distance is the wheel odometry's, and it is 4.2 % long by
  design.** The believed radius is 1.5 % large and the encoder is a
  1024-line grid; the accelerometer cannot correct a distance (its own
  bias double-integrates to 98 m over 100 s unaided), and the gyro says
  nothing about distance at all. The EKF's `straight` path error is
  **+4.22 to +4.23 %**, which is the raw estimate's, unchanged, on every
  run.
- **Heading is bounded only by which way the bias fell.** §3.1.
- **Nothing here observes an absolute position**, because nothing here
  is *outside* the vehicle. The odom frame is where the truck switched
  on, and a continuous, jump-free, drifting estimate is exactly what an
  odom frame is *for* (REP-105).

That is the honest handoff: **F3's map and localisation are what bound
these errors**, and this transform is what they stack on. `map` → `odom`
is not published by anything in this phase — `ekf.yaml`'s `world_frame`
is the odom frame, so the filter emits exactly one transform and cannot
quietly become that edge's owner.

---

## 6. The capture

Eight drive sessions, all under `m5_ver3/logs/evidence/` and all
untracked. The stack was stopped and restarted before every one, so each
begins from the spawn pose; `drive_route.py` exited **0** on all eight.

| Session | profile | `vy` | `ekf_odom` rows | md5 of `ekf_odom.csv` |
|---|---|---|---|---|
| `drive-straight-20260826-082850` | straight 1 | false | 2009 | `6e130573b25eb979151d0bfe35a2e153` |
| `drive-straight-20260826-083007` | straight 2 | false | 2018 | `7f1b243fc030f07252fcb198376709d3` |
| `drive-straight-20260826-083112` | straight 3 | false | 2015 | `e5ee5d1d634ac3ebcb427c925105545d` |
| `drive-square-20260826-083216` | square | false | 2554 | `eabbb2a0fe9a9a239195a1b7b1013b06` |
| `drive-corner_creep-20260826-083330` | corner_creep | false | 1557 | `8f236d56436fc27d1d70205b8411db2d` |
| `drive-straight-20260826-083525` | straight (A/B) | **true** | 2010 | `17305c2911a0567b6baf492d4826aa5a` |
| `drive-square-20260826-083626` | square (A/B) | **true** | 2619 | `3a6a4acbc083e0492d39d82a812d0fbf` |
| `drive-corner_creep-20260826-083739` | corner_creep (A/B) | **true** | 1558 | `9da95872d7c6435544b71fe21abbff63` |

**Delivered rates over a drive, ROS side** (`analyse`, session
`…-082850`; the plant's own sim stamps):

```
  stream             samples     hz_sim    hz_wall  of conf     dt_med     dt_max     rtf
  clock                20171   500.0000   501.8108             0.00200    0.00200  1.0036
  odom_truth             803    20.0000    19.9898             0.05000    0.05000  0.9995
  wheel_odom           20090   500.0000   499.8360             0.00200    0.00200  0.9997
  ekf_odom              2009    50.0000    49.9761             0.02000    0.02200  0.9995
  joint_state          20087   500.0000   499.8583             0.00200    0.00200  0.9997
  drive_read_a         20087   500.0000   499.8727             0.00200    0.00200  0.9997
  scan_nav               608    15.1515    15.1446             0.06600    0.06600  0.9995
  imu                   4018   100.0000    99.9620             0.01000    0.01000  0.9996
  depth                  608    15.1515    15.1447             0.06600    0.06600  0.9995
  cam_info               609    15.1515    15.1435             0.06600    0.06600  0.9995
```

`rtf` **0.9995–0.9997** on every stream with the two new children up, and
`dt_max = dt_med` on nine of the ten — **not one message lost** on any
bridged stream over the run. The tenth is the filter's own output and its
one late cycle is §1.

**Reproducing any row of this file needs no simulator.** The CSVs are
where the tables come from and `analyse` runs on a python with no ROS:

```
python3 m5_ver3/tools/sensor_evidence.py analyse \
    m5_ver3/logs/evidence/drive-square-20260826-083216
```

**The seven F1 drive sessions still read**, and `analyse` says plainly
what is not in them rather than refusing them or scoring around it:

```
--- straight : NO FUSED ESTIMATE IN THIS SESSION ---
  ekf_odom.csv is not in this capture. It was recorded before F2 Task 1
  added the EKF child, and the figures above are the raw wheel odometry's
  exactly as EVIDENCE_SENSORS.md 3 published them. Nothing is missing from
  this run; the filter had not been built when it was driven.
```

Re-derived from `drive-straight-20260825-231657` with today's tool:
11.5935 m of truth path, 12.0839 m of estimate, **+4.23 %**, end error
**0.5800 m**, rms 0.5241 m, worst 0.8016 m, heading −0.0575 rad — every
figure `EVIDENCE_SENSORS.md` §3 published, to the digit.

---

## 7. The suite

```
$ python -m pytest m5_ver3/tests/ -q
106 passed

$ python m5_ver3/tools/evidence_core.py --selftest
22/22 checks passed

$ python m5_ver3/nodes/wheel_odom_core.py --selftest
12/12 checks passed
```

82 tests before this phase, **106** after: 12 for the watchdog throttle
and the shell's other pure helpers, 12 for `compare_drift()` and
`sdf_link_pose()`. The selftest went from 16 checks to 22.

**The two tests that exist because a comparison is the easiest thing in
this file to flatter:**

- *a filter that made it worse reads NEGATIVE and is never clamped* — a
  fraction floored at zero would have published §3.1's run 3 and all of
  §4's `vy`-false column as "no improvement", which is a different and
  flattering claim about the same measurement.
- *the yaw is compared by MAGNITUDE and keeps its SIGN* — −1.73 rad
  becoming +0.02 rad is 98.8 % removed and not 101 %, and the signs are
  what say **which way** each estimate was wrong.
