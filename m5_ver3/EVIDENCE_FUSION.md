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

**Three entries of fifteen are true on the twist**, and that is the whole
of what the wheel odometry contributes:

```
   x     y     z    roll  pitch  yaw    vx    vy    vz   vroll vpitch vyaw   ax   ay   az
 false false false false false false  TRUE  TRUE  false false false TRUE  false false false
```

**`vy` was `false` in the first cut of this file and was ruled back in on
the measurement in §4**, which is kept rather than deleted. It is not a
noise channel: `wheel_odom_core.py` computes `vy = d · yaw_rate` with
`d = 0.50 m`, the lateral velocity `base_link` genuinely has because it
stands half a metre forward of the rear axle, and that file's own header
warns that dropping the term *"quietly drops the lateral term and there
is no symptom until something fuses the twist."* §4 is that something,
measured: refusing it cost **+0.90 m of end error** on a 163° turn and
**doubled the rms** over a square.

**Fusing `vy` is still twist-only.** The six pose flags stay `false` and
the node's covariance of 1000 still says do-not-fuse; F2 global
constraint 13 governs the POSE and never excluded a velocity component.

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
| `…-085033` | straight 1 (shipped) | **−0.002618** rad/s | — |
| `…-085135` | straight 2 (shipped) | **+0.002462** rad/s | — |
| `…-085238` | straight 3 (shipped) | **+0.002656** rad/s | — |
| `…-085338` | square (shipped) | **−0.002544** rad/s | — |
| `…-085450` | corner_creep (shipped) | **+0.002764** rad/s | — |

Magnitude against `model.sdf`'s configured `bias_mean 0.002618`: the
eleven gyro draws read **0.94–1.07** of it, and **five are positive and
six negative**. **The sign is not repeatable and a consumer may not
assume it** — which `EVIDENCE_SENSORS.md` §2 established at rest, and
which §3.1 and §3.4 below show deciding the *direction* of what fusion
buys on eleven of the thirteen runs in this file.

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

**These are the SHIPPED configuration's runs — `vy` fused.** The five
sessions are `…085033`, `…085135`, `…085238`, `…085338`, `…085450`,
recorded after the flag was flipped. §4 keeps the refused-`vy` set beside
them.

`analyse` refuses a drive session whose first ground-truth sample is more
than 0.05 m or 0.02 rad from `vehicle.spawn`; all thirteen sessions in
this file read **exactly** `(-17.000000, 10.000000) yaw 3.141590`,
0.0000 m and 0.00000 rad off.

### 3.0 The raw wheel odometry did not move, and that is the control

Two new children on a stack whose figures are all taken under a real-time
factor is a change to the plant until it is shown not to be — and an EKF
configuration flag must not be able to reach the estimate that feeds it
at all. The raw wheel-odometry row is the same estimator, the same
settings and the same instrument across **all thirteen F2 sessions and
both `vy` settings**:

| Profile | runs | raw end error, min–max | **spread** | as % of truth path | raw end heading spread |
|---|---|---|---|---|---|
| `straight` | 7 | 0.5800 – 0.5826 m | **2.6 mm** | 5.0022 – 5.0095 % (0.0073 pp) | **0.0003 rad** |
| `corner_creep` | 3 | 0.1941 – 0.1943 m | **0.2 mm** | 4.8924 – 4.8953 % (0.0029 pp) | **0.0006 rad** |
| `square` | 3 | 0.6724 – 0.6831 m | 10.7 mm | 8.9230 – 9.0614 % (0.138 pp) | 0.1247 rad |

**`straight` and `corner_creep` repeat to 2.6 mm and 0.2 mm, and the `vy`
flag is nowhere in them** — it is a property of the filter, and the raw
estimate never passes through the filter. Against F1.5's own re-measured
figures (`EVIDENCE_SENSORS.md` §3): straight 0.5778 m, square 0.6712 m,
corner_creep 0.1945 m.

**`square`'s wider spread is the PLANT and not the instrument**, and the
normalised column is what shows it. That profile's *delivered* turn
varies between runs — **+6.2082, +6.2875, +6.3012 rad** — because it is
an open-loop table of held commands and the contact solver does not
repeat a four-corner manoeuvre to the milliradian. The raw end error
tracks it: the run that turned 0.093 rad short (`…083626`) is the run
whose raw heading error reads +0.6476 instead of ≈+0.523. As a fraction
of the distance travelled the raw estimate is **8.92–9.06 %** on all
three.

### 3.1 `straight` × 3 — and the answer depends on which way the bias fell

23.5 s of profile, ≈11.6 m, no steer input at all, **18.5 s of it
moving**. The wheel odometry's heading error here is its **steer bias**
carried through: +0.005 rad of believed steer that is not there
(`config.yaml` predicts 3.33 mrad/s at 0.7 m/s; the ramps run slower, and
the measured −0.058 rad is what that comes to).

| Run | gyro bias draw | raw end error | **EKF end error** | raw end heading | **EKF end heading** | heading removed |
|---|---|---|---|---|---|---|
| 1 `…085033` | **−0.002618** | 0.5808 m | **0.6213 m** | −0.0577 rad | **−0.0688 rad** | **−19.2 %** |
| 2 `…085135` | **+0.002462** | 0.5800 m | **0.4997 m** | −0.0576 rad | **−0.0223 rad** | **+61.3 %** |
| 3 `…085238` | **+0.002656** | 0.5826 m | **0.5010 m** | −0.0579 rad | **−0.0229 rad** | **+60.4 %** |

| Run | raw rms | EKF rms | raw worst | EKF worst | raw path | EKF path |
|---|---|---|---|---|---|---|
| 1 | 0.5240 m | 0.5425 m | 0.8026 m | 0.8197 m | +4.22 % | +4.23 % |
| 2 | 0.5240 m | **0.4905 m** | 0.8019 m | **0.7748 m** | +4.22 % | +4.23 % |
| 3 | 0.5256 m | **0.4919 m** | 0.8033 m | **0.7750 m** | +4.21 % | +4.21 % |

**The sign of what fusion buys on a straight line is the sign of that
run's gyro bias draw, and it went both ways in three runs.** The wheel
odometry's heading error is **negative** on every run (the steer bias
turns it one way, and that is deterministic to 0.0003 rad across seven
runs). A **positive** bias draw opposes it and the fused heading is
pulled towards truth; a **negative** draw adds to it and the fused
heading is pushed further out. §3.4 is the same reading over all thirteen
runs.

**A three-run convention is what made it visible.** One run would have
published "fusion removes 60 % of the straight-line heading error" and
been wrong about the vehicle. This is not a defect in the filter and it
is not corrected here: it is what fusing an **uncompensated** MEMS gyro
with a **biased** steer encoder does — two systematic errors, neither of
which any diagonal covariance can represent, and the filter is blending
their *noise* models. `ekf.yaml` says so at the top of the file; this is
the measurement of it.

### 3.2 `square` — four hard corners, and the heading is what fusion is for

Session `drive-square-20260826-085338`, 40.9 s of profile (**37.9 s
moving**), gyro bias draw −0.002544 rad/s. The plant turned
**+6.3012 rad** — 0.018 rad past a full turn (2π = 6.283185), so this
profile returns to within a degree of its **starting heading**.

| Figure | ground truth | raw wheel odom | **EKF** | removed | of raw |
|---|---|---|---|---|---|
| path | 7.5499 m | 8.2883 m (**+9.78 %**) | 8.2890 m (**+9.79 %**) | — | — |
| turned | +6.3012 rad | +6.8241 rad | +6.6881 rad | — | — |
| **end error** | — | **0.6831 m** | **0.5448 m** | +0.1383 m | **20.2 %** |
| **END HEADING** | — | **+0.5229 rad** | **+0.3862 rad** | +0.1367 rad | **26.1 %** |
| rms over run | — | 0.4003 m | **0.3100 m** | +0.0904 m | **22.6 %** |
| worst | — | 0.7038 m | **0.5557 m** | +0.1481 m | **21.0 %** |
| closure | 0.1019 m | 0.6570 m | **0.5256 m** | — | — |

**This is the headline of the phase.** The gyro removes **26.1 % of the
four-corner heading error** and the filter is better than its own input
on **every one of the four figures** — end error, heading, rms and worst
— by 20–26 %. Its path error now **matches** the raw estimate's to
0.01 pp (+9.79 % against +9.78 %), which is the signature of a filter
that has the vehicle's lateral velocity: with `vy` refused this same
column read **−12.62 %**, a path 12 % *short* (§4).

The 26 % ceiling is set by an honesty this track already committed to:
the wheel odometry's `vyaw` covariance is derived from its **steer bias
alone**, because the scrub error that dominates a corner is not readable
at the shaft and `config.yaml` refuses to invent a term for it — so at a
corner this filter believes the wheel odometry's yaw rate more than that
reading deserves. `ekf.yaml` states the consequence beside the
configuration; it is not tuned around.

### 3.3 `corner_creep` — one sustained corner, and the plant is already honest

Session `drive-corner_creep-20260826-085450`, 22 s of profile (**17 s
moving**), one 0.785 rad steer held for 14 s at 0.3 m/s, gyro bias draw
**+0.002764 rad/s**. The plant turned **+2.8519 rad** = 163°, so this
profile ends nowhere near its starting heading.

| Figure | ground truth | raw wheel odom | **EKF** | removed | of raw |
|---|---|---|---|---|---|
| path | 3.9673 m | 4.2704 m (**+7.64 %**) | 4.2708 m (**+7.65 %**) | — | — |
| turned | +2.8519 rad | +2.8675 rad | +2.8813 rad | — | — |
| end error | — | **0.1941 m** | **0.1918 m** | +0.0023 m | **1.2 %** |
| END HEADING | — | **+0.0156 rad** | **+0.0309 rad** | −0.0153 rad | **−98.1 %** |
| rms over run | — | 0.1594 m | 0.1590 m | +0.0004 m | **0.3 %** |
| worst | — | 0.2115 m | 0.2121 m | −0.0005 m | **−0.2 %** |

**There is almost nothing here for a gyro to remove, and on this run's
bias draw it added instead.** F1.5 retuned this plant so the truck takes
1.005 of its kinematic yaw at creep (`EVIDENCE_LATERAL_TUNE.md`), so the
raw estimate's heading is already only **0.0156 rad** out over a 163°
turn — smaller than what a 0.0026 rad/s bias contributes over 17 s of
motion. This run drew a **positive** bias against a **positive** raw
error, so the two added: +0.0156 → +0.0309 rad. The two earlier
`corner_creep` runs drew **negative** biases and improved by 53.7 % and
64.0 % (§4). Position is a wash either way — 1.2 % better on end error,
0.3 % on rms — which is the honest reading of a filter on a profile whose
input was already nearly right.

**F2 Task 2's slippery variant is where this profile is supposed to
separate the two estimates**, because scrub is exactly the error dead
reckoning cannot see and a gyro can. On a floor with no slip left in it,
there is nothing to see.

### 3.4 The rule, over all thirteen runs

Every drive session in this file, with the sign of its gyro bias draw
against the sign of the raw estimate's heading error:

| Profile | raw heading error | runs | draws that **OPPOSE** it | draws that **ADD** to it |
|---|---|---|---|---|
| `straight` | **negative**, ≈−0.058 rad | 7 | +0.002617 → +60.7 % · +0.002588 → +58.9 % · +0.002462 → +61.3 % · +0.002656 → +60.4 % | −0.002789 → −19.9 % · −0.002729 → −19.0 % · −0.002618 → −19.2 % |
| `corner_creep` | **positive**, ≈+0.015 rad | 3 | −0.002633 → +53.7 % · −0.002673 → +64.0 % | +0.002764 → −98.1 % |
| `square` | **positive**, ≈+0.52 rad | 3 | −0.002670 → +26.2 % · −0.002544 → **+26.1 %** | +0.002571 → **+15.3 %** |

**Twelve of thirteen: the gyro helps when its per-run bias draw opposes
the wheel odometry's heading error and hurts when it adds — and the
thirteenth is the one that shows why that is not the rule.** The
exception is in the table above: `square`'s +0.002571 draw **added** to a
positive heading error and the gyro **still removed 15.3 %** of it,
because on that profile the error being corrected is five times what the
bias can reach. So the sign is not what decides; the **ratio** is, and
the sign only decides when that ratio is near 1 — a 0.0026 rad/s bias
integrated over the seconds the profile is moving, against the raw error
it is being blended with:

| Profile | moving | bias × time | raw heading error | ratio |
|---|---|---|---|---|
| `straight` | 18.5 s | 0.048 rad | 0.058 rad | **0.83** — comparable, so the sign decides |
| `corner_creep` | 17.0 s | 0.044 rad | 0.016 rad | **2.8** — the bias dominates, so the sign decides |
| `square` | 37.9 s | 0.099 rad | 0.523 rad | **0.19** — the real error dominates, so the gyro helps **whichever way the draw fell** (+15.3 % to +26.2 %) |

That is the honest scope of this phase's headline. **Fusion removes a
quarter of the heading error on the profile that HAS a heading error**,
and on profiles whose heading was already good to a few milliradians it
substitutes one unmodelled systematic term for another, with a sign drawn
at model load. Nothing in `ekf.yaml` estimates that bias, and the comment
beside `imu0_config` says so.

---

## 4. What refusing `vy` cost — the ruling that was reversed

**This section records a wrong turn, and it is kept rather than tidied
away.** The first cut of `ekf.yaml` refused the wheel odometry's `vy`, on
the rationale that *"the tricycle cannot move laterally and the measured
`vy` is quantiser noise"*. That rationale is wrong for this node; the
cost was predicted from the kinematics and then measured on the same
profiles with the same instrument; and the ruling was **reversed on the
measurement**. §3 above is the shipped configuration. This is what the
refused one did.

**Why `vy` is not noise.** `wheel_odom_core.py` computes

```
vy = base_offset_m * yaw_rate          # d = 0.50 m, exactly
```

The rear axle midpoint is the only point of a tricycle whose velocity is
purely longitudinal, and `base_link` stands half a metre in **front** of
it — so `base_link` genuinely translates sideways in every turn, and that
term is a kinematic identity rather than a measurement of anything noisy.
`robot_localization`'s motion model is **omnidirectional and knows
nothing about `d`**, so this channel is the only way the filter learns
about that motion at all. With `vy` unobserved it integrates `base_link`
**as though it were the rear axle** — which is precisely the failure
`nodes/wheel_odom_core.py`'s own header warns about.

**The prediction, written before the runs.** The resulting position error
is `d·|û(ψ_end) − û(ψ₀)|`: it **cancels** on a profile that ends on its
starting heading and reaches `2d = 1.00 m` on one that ends reversed. For
`corner_creep`'s 2.8508 rad that is **0.9894 m**.

| Profile | figure | raw wheel odom | **`vy` REFUSED** | **`vy` FUSED (shipped)** |
|---|---|---|---|---|
| `straight` | end error | 0.5800 – 0.5826 m | 0.5080 / 0.5090 / 0.6393 m | 0.6213 / 0.4997 / 0.5010 m |
| | rms | 0.5240 – 0.5256 m | 0.4946 / 0.4935 / 0.5506 m | 0.5425 / 0.4905 / 0.4919 m |
| `square` | path error | +9.78 % | **−12.62 %** | **+9.79 %** |
| | end error | 0.6724 / 0.6831 m | 0.4515 m (−32.8 %) | 0.5448 m (−20.2 %) |
| | END HEADING | +0.5269 / +0.5229 rad | +0.3887 rad (−26.2 %) | +0.3862 rad (−26.1 %) |
| | rms | 0.3956 / 0.4003 m | **0.7838 m (+98 %)** | **0.3100 m (−22.6 %)** |
| | worst | 0.6920 / 0.7038 m | **1.3251 m (+92 %)** | **0.5557 m (−21.0 %)** |
| `corner_creep` | path error | +7.65 / +7.64 % | **−0.39 %** | **+7.65 %** |
| | end error | 0.1943 / 0.1941 m | **1.0565 m (+444 %)** | **0.1918 m (−1.2 %)** |
| | rms | 0.1594 m | **0.6768 m (+325 %)** | **0.1590 m (−0.3 %)** |
| | worst | 0.2115 m | **1.0640 m (+403 %)** | **0.2121 m (+0.2 %)** |

**Four readings, and they agree with the prediction.**

1. **The predicted offset is there and it is the right size.** Comparing
   the two filters on `corner_creep`: 1.0565 m refused against 0.1557 m
   fused on the paired A/B run — a **0.9008 m** gap against the formula's
   **0.9894 m** ceiling. The formula assumes the whole offset is still
   owed at the end; the measurement lands **9 % under** it because the
   profile's heading history is not one clean arc. Right size, right
   sign, which is what was being tested.
2. **`square` hides it in the end error and shows it in the rms.** That
   profile returns to within a degree of its starting heading, so
   `d·û(ψ)` comes back to where it started and the **end** error barely
   feels it — the refused-`vy` run even reads *better* on that one figure
   (0.4515 against 0.5448 m). Over the run it is not hidden at all: the
   rms **doubles** and the worst error **nearly doubles**. A reader with
   only the end error would have drawn the opposite conclusion, which is
   why this instrument prints four figures and not one.
3. **The path length is the tell that needs no reference.** With `vy`
   refused the filter's path comes out **12.6 % short** on `square` and
   **0.4 % short** on `corner_creep`, where the raw estimate it is built
   from is 9.8 % and 7.6 % **long**. A filter cannot make its input's
   distance error disappear — nothing it fuses observes distance (§5) —
   so a path that shortens is a filter losing motion, not correcting it.
   With `vy` fused the column reads +9.79 % and +7.65 %: the raw
   estimate's own figures, to 0.01 pp.
4. **The heading is untouched by the flag, exactly as it should be.**
   `square`'s heading improvement is **26.2 %** refused and **26.1 %**
   fused. `vy` is a translation channel; it moves position and leaves the
   yaw alone, and the measurement says so to a tenth of a percentage
   point. That is also why §3's headline did not move when the ruling
   did.

**The refused-`vy` sessions are kept in §6** and re-analysable with the
same command as every other row in this file. Reproducing that column
needs one edit — `odom0_config`'s eighth entry — and nothing else.

## 5. What fusion cannot fix, and the F3 handoff

**Every figure in §3 still grows without bound, and no line of `ekf.yaml`
changes that.** Both inputs are *rates*. The filter integrates them, and
the integral of a biased rate is a pose whose error has no ceiling:

- **Along-track distance is the wheel odometry's, and it is 4.2 % long by
  design.** The believed radius is 1.5 % large and the encoder is a
  1024-line grid; the accelerometer cannot correct a distance (its own
  bias double-integrates to 98 m over 100 s unaided), and the gyro says
  nothing about distance at all. The EKF's `straight` path error is
  **+4.21 to +4.23 %**, which is the raw estimate's, unchanged, on every
  run — and on `square` and `corner_creep` it is +9.79 % and +7.65 %
  against the raw estimate's +9.78 % and +7.64 %. **A filter cannot make
  its input's distance error go away**, and one whose path *shortens* is
  losing motion rather than correcting it (§4, reading 3).
- **Heading is bounded only by which way the bias fell.** §3.1, §3.4.
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

Thirteen drive sessions, all under `m5_ver3/logs/evidence/` and all
untracked. The stack was stopped and restarted before every one, so each
begins from the spawn pose; `drive_route.py` exited **0** on all thirteen.
The `vy` column is `odom0_config`'s eighth entry: **the five `true` rows
at the bottom are the shipped configuration and §3's tables**, the three
marked A/B are the pair that decided the ruling, and the five `false`
rows are §4's.

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
| `drive-straight-20260826-085033` | straight 1 | **true** | 2013 | `4058b44936a82caee8e96c0fae2c93eb` |
| `drive-straight-20260826-085135` | straight 2 | **true** | 2015 | `397dc0f625dc60198e036d77aa71ae53` |
| `drive-straight-20260826-085238` | straight 3 | **true** | 2014 | `7bb626ce240876e28beeb1fefb2cf603` |
| `drive-square-20260826-085338` | square | **true** | 2554 | `1682c2bd0ab978a337b1e30a37afa2ef` |
| `drive-corner_creep-20260826-085450` | corner_creep | **true** | 1556 | `081cf14fa7357f518b1df9380b67b4ff` |

**Delivered rates over a drive, ROS side** (`analyse`, shipped session
`…-085033`; the plant's own sim stamps):

```
  stream             samples     hz_sim    hz_wall  of conf     dt_med     dt_max     rtf
  clock                20143   500.0000   500.2218             0.00200    0.00200  1.0004
  odom_truth             805    20.0000    19.9943             0.05000    0.05000  0.9997
  wheel_odom           20137   500.0000   499.9810             0.00200    0.00200  1.0000
  ekf_odom              2013    50.0000    49.9942             0.02000    0.02200  0.9999
  joint_state          20134   500.0000   499.9730             0.00200    0.00200  0.9999
  drive_read_a         20134   500.0000   499.9918             0.00200    0.00200  1.0000
  scan_nav               610    15.1515    15.1488             0.06600    0.06600  0.9998
  imu                   4027   100.0000    99.9854             0.01000    0.01000  0.9999
  depth                  610    15.1515    15.1539             0.06600    0.06600  1.0002
  cam_info               610    15.1515    15.1486             0.06600    0.06600  0.9998
```

`rtf` **0.9997–1.0002** on every stream with the two new children up and
the third twist channel fused, and `dt_max = dt_med` on nine of the ten —
**not one message lost** on any bridged stream over the run. The tenth is
the filter's own output and its one late cycle is §1. **Fusing `vy` cost
the filter nothing measurable**: same 50.0000 Hz, same `dt_max`.

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
