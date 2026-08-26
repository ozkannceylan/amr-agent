# EVIDENCE — m5-ver3 fusion: the odom-frame EKF (F2 Task 1), the slip scenario (F2 Task 2, §8), the `ax` reversal (§9) and the laser-odometry arm (F2 Task 3, §10)

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

**And what F2 Task 2 added on top, all of it §8's:**

| Tool | What it answers | New there |
|---|---|---|
| `m5v3.sh start --slippery` | a floor the truck cannot grip, from the SAME model file, through gz's own `wheel_slip` service | ● |
| `config.yaml` `slippery:` + `paths.traction_file` | the override's two values, and which plant the running stack is on | ● |
| `tools/sensor_evidence.py` | stamps every session with its plant and **refuses to record without one**; refuses to read two plants into one document; refuses a diverged filter before the drive is spent | extended |
| `tools/evidence_core.py` | `track_error()` / `track_error_of()` / `travel_projection()` — the end error split ALONG the direction of travel; `diverged_at()` / `require_not_diverged()` — a broken filter told from a drifting one. Suite 106 → **138** tests, selftest 22 → **26** checks | extended |

**And what F2 Task 3 added on top, all of it §10's:**

| Tool | What it answers | New there |
|---|---|---|
| `m5v3.sh start --rf2o` | a THIRD estimator on the same plant - `rf2o_laser_odometry` matching consecutive nav-lidar scans - behind a flag that is off by default | ● |
| `tools/install_rf2o.sh` | how that package reproduces: from source, in the user's own `$HOME`, at a pinned commit, without root | ● |
| `nodes/rf2o_twist.py` + `nodes/rf2o_twist_core.py` | the four things upstream publishes that a filter may not be handed as they stand, and the arithmetic that fixes three of them | ● |
| `m5_ver3/ekf_rf2o.yaml` | what the arm is fused from - `vx` and `vyaw` only - in a file the default stack never reads | ● |
| `config.yaml` `rf2o:` + the `arm=` line | the pin, the measured covariance, and which ESTIMATOR the running stack is | ● |
| `m5v3.sh` `check_rf2o_transform()` | did the scan matcher find out where it is bolted? A refusal, beside §9.4's covariance gate | ● |
| `tools/sensor_evidence.py` | stamps every session with its ARM as well as its plant, refuses to record without one, and refuses to read two arms into one document | extended |
| the suite | 148 → **194** tests; a fourth selftest, `rf2o_twist_core --selftest`, **22/22** | extended |

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

**The IMU contributes ONE entry and has no orientation to contribute.**
`model.sdf` sets `<enable_orientation>false</enable_orientation>` because
gz derives an IMU's orientation from the link's pose in the simulator —
ground truth wearing a sensor's name. `imu0_config` fuses `vyaw` (the
gyro's z axis) and refuses all three orientation entries.

> **IT FUSED TWO UNTIL F2 TASK 2, AND `ax` WAS THE SECOND.** Every table
> in §2, §3 and §4 was measured with the accelerometer channel fused;
> §9 is the reversal, the measurement that forced it, and the same
> figures re-measured on the shipping filter. Those sections are **kept
> as the reversed ruling's record**, exactly as §4 keeps the refused-`vy`
> column, and each says so where it starts.

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

> **THIS SECTION IS THE `ax`-FUSED FILTER'S, AND THAT FILTER NO LONGER
> SHIPS.** F2 Task 2 measured the IMU's acceleration channel making
> `ekf_node` diverge during its first cycles and the ruling that fused it
> was reversed (§8.6, §9). Everything below stands as measured — the runs
> happened, the filter ran, and every one of the thirteen fused streams
> passes §9's covariance gate — but the **shipping** figures are §9.3's,
> re-measured on `wz`-only. This section is kept for the reason §4 keeps
> the refused-`vy` column: a ruling that was reversed on a measurement is
> worth more where it happened than tidied away.

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

**CHECKED AGAINST §8.6's BOUND, 2026-08-26 (F2 Task 2).** That task
measured `ekf_node` diverging at startup on most bringups of this stack
and added a check for it; every one of the thirteen fused streams below
passes, with the largest distance any of them reaches from its own origin
being **12.13 m** against a bound of 100 m. **The figures in this section
are figures about a filter that ran.** What §8.6 puts in question is
whether they can be *reproduced* on this rig today, which is a different
statement and is made there.

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

**CORRECTED BY MEASUREMENT 2026-08-26 (F2 Task 2) — THAT SPREAD IS THREE
RUNS' AND THE PLANT'S IS WIDER.** The paragraph above is right about the
mechanism and understates it. Over **all six** post-F1.5 nominal `square`
runs this track has recorded, the delivered turn is **+5.9060 to
+6.3124 rad** — 0.41 rad, three times the range quoted here — and the raw
end error tracks it out to **1.1161 m** on the run that turned +6.1438
(§9.3). So `square`'s raw end error is not a figure that reproduces run
to run **at all**, and any before/after fraction taken from a single
square carries that spread underneath it. `straight` (2.6 mm over ten
runs) and `corner_creep` (0.2 mm over four) are the profiles that repeat,
and they are where a claim about the ESTIMATOR should be made.

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

> **AND THE SECOND REVERSAL WENT THE OTHER WAY.** This section records a
> channel ruled OUT and then ruled back IN on a measurement; §9 records
> one ruled IN and then ruled back OUT on another. Both sit in this
> track's ruling ledger,
> `.superpowers/sdd/2026-08-26-m5v3-f2-fusion/progress.md`. The tables
> below were all taken with `ax` fused.

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

**F2 Task 2 measured the two halves apart and put a number on the one
that is handed over.** §8.5 splits every end error into along-track and
cross-track in the ground truth's own frame: fusion moves cross-track by
up to 68 % and along-track by **1.5 percentage points across four runs**,
which is nothing. On the slippery plant of §8 that untouchable half is
**+1.02 to +1.06 m over 11 m**, more than double this section's figure.

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

**As F2 Task 1 left it:**

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

**EXTENDED BY F2 TASK 2 to 138 and 26** — see §8 for what each addition
is for:

```
$ python -m pytest m5_ver3/tests/ -q
138 passed

$ python m5_ver3/tools/evidence_core.py --selftest
26/26 checks passed

$ python m5_ver3/nodes/wheel_odom_core.py --selftest
12/12 checks passed
```

19 for the along/cross-track split and the travel sense it is taken in
(`track_error`, `track_error_of`, `travel_projection`), 6 for the
divergence bound (`diverged_at`, `require_not_diverged`) and 13 in a new
file, `tests/test_sensor_evidence_traction.py`, for the traction label —
the one piece of logic that decides whether two recordings may be read
into one document. The selftest gained the two checks that would have
caught the two ways this task got its own arithmetic wrong: an
along-track split taken on the nose of a truck that drives forks-trailing
(every sign reversed), and a broken filter told apart from a drifting one
by the reader instead of by a bound.

**The two tests that exist because a comparison is the easiest thing in
this file to flatter:**

- *a filter that made it worse reads NEGATIVE and is never clamped* — a
  fraction floored at zero would have published §3.1's run 3 and all of
  §4's `vy`-false column as "no improvement", which is a different and
  flattering claim about the same measurement.
- *the yaw is compared by MAGNITUDE and keeps its SIGN* — −1.73 rad
  becoming +0.02 rad is 98.8 % removed and not 101 %, and the signs are
  what say **which way** each estimate was wrong.

---

## 8. The slip scenario — why fusion earns its keep, and where it does not (F2 Task 2)

Everything under this heading was measured on **2026-08-26**, on the rig
named at the top of this file, with the stack **stopped and restarted
before every run** and every session recorded headless. It answers one
question: on a floor the truck cannot grip, **the gyro keeps the heading
honest while the wheel odometry lies about distance** — how much of each,
before and after fusion, and what fusion cannot touch.

**Two plants and one model file.** `gazebo/forklift_ver3/model.sdf` is
byte-identical between the two columns of every table below; the
difference is three service calls made after the truck is spawned. §8.1
is the mechanism and the control that proves it is the same thing as
editing the model. §8.6 is a defect in `ekf_node` that this task found
while trying to measure the rest, and it governs how the sessions here
were obtained.

### 8.1 The mechanism: a runtime override, and the reply is checked

F2's constraint 12 gives a ladder — investigate a runtime override first,
generate a model variant only if the override provably fails. **It does
not fail.** gz-sim 8.11's `UserCommands` system advertises

```
/world/warehouse/wheel_slip            gz.msgs.WheelSlipParametersCmd -> gz.msgs.Boolean
/world/warehouse/wheel_slip/blocking   gz.msgs.WheelSlipParametersCmd -> gz.msgs.Boolean
```

on every world this stack starts (`gz service -l`, partition `m5v3`).
`m5v3.sh start --slippery` calls the **blocking** variant once per wheel
after the spawn and before any bridge is opened, so no consumer ever sees
a message from the un-overridden plant.

**Three things make the reply worth believing, and each is measured.**

| # | Check | Measured |
|---|---|---|
| 1 | The **blocking** endpoint returns only after the command has run inside the simulation loop and found the entity | `forklift_ver3::drive_wheel` → `data: true` |
| 2 | A link the model does not carry comes back **empty** — and `gz service` still exits **0** | `forklift_ver3::no_such_wheel` → *(no output)*, `rc=0`; `no_such_model::rear_wheel_right` → *(no output)*, `rc=0` |
| 3 | The override at the model's own value reproduces the model's own slip | §8.2 row 1 |

Check 2 is why `m5v3.sh` tests the reply's **text** and never the exit
status, and why the refusal says an empty reply is how this service
reports an entity it could not find. Check 3 is the control: **the same
7.0 applied through the service gives 0.95434 % where the model's own
7.0 gives 0.95299 %** — 0.00135 percentage points apart, inside the
0.003 pp run-to-run repeatability `EVIDENCE_LATERAL_TUNE.md` §3.1 already
established for this bench. The runtime path and the SDF path are the
same physics.

**The wheels are read out of the model and not listed anywhere else.**
`m5v3.sh`'s `wheel_links()` greps `<wheel link_name="...">` out of
`model.sdf` — the WheelSlip plugin's own element, and the only place that
attribute appears in that file — so the override cannot come to name a
different set of wheels from the plugin it is overriding. The applied
count is compared against the found count and a wheel that replies
anything but `data: true` is a refusal naming the log, the model and the
half-overridden state it leaves behind.

**The values are in EFFECT space, and the file says so three times.**
`EVIDENCE_LATERAL_TUNE.md` §3.1 measured that on this rig the element
named `<slip_compliance_lateral>` is the one that governs the wheel's
**longitudinal** slip. The same swap is in this message's two fields,
because they reach the same code. Both are therefore set to the **same**
number — which is also what `wheel_slip:` ships, and for the measured
reason that every setting making one direction of a contact stiffer than
the other brought back the heading dependence of `EVIDENCE_SENSORS.md`
§4.2. Six equal compliances. **The normal forces are not overridden**:
the truck's weight did not change, only the floor under it.

**The label is a mechanism.** `start` writes `paths.traction_file` on
every bringup — nominal ones included, so a nominal run cannot inherit
yesterday's slippery answer; `stop` deletes it; `status` prints it;
`record` copies it into `session.txt` and **refuses to record without
it**; and `analyse` **refuses a set of sessions that mixes the two
plants**, naming both groups and printing the two commands that would
have been right. A slippery run that reached §3's tables unlabelled would
not look like a failure. It would look like a row.

### 8.2 The ladder

Every row is one `stop` / edit `config.yaml`'s `slippery:` / fresh
`start --headless --slippery` cycle, and one `tools/slip_bench.sh` at the
0.7 m/s cruise **from the spawn pose** (`EVIDENCE_LATERAL_TUNE.md` §6.2
says why that sentence is here). `slip_cmd` is
`(commanded tread speed − ground truth speed) / commanded tread speed`;
forward and astern are both driven and both reported, because an
asymmetry between them is how this bench says it measured a wall rather
than a tyre.

| # | compliance (both keys, EFFECT space) | applied by | forward | astern | **mean slip at cruise** | verdict |
|---|---|---|---|---|---|---|
| 0 | 7.0 / 7.0 | *model.sdf, no override* | 0.95550 % | 0.95048 % | **0.95299 %** | the nominal plant — the reference, not a candidate |
| 1 | 7.0 / 7.0 | `--slippery` | 0.95346 % | 0.95522 % | **0.95434 %** | **the mechanism control** — 0.00135 pp from row 0 |
| 2 | 12.0 / 12.0 | `--slippery` | 3.17749 % | 3.19263 % | **3.18506 %** | rejected: 3.19 % does not clear the 5 % the brief asks for |
| 3 | **16.0 / 16.0** | `--slippery` | 6.16768 % | 6.18977 % | **6.17873 %** | **ACCEPTED** |
| 4 | 20.0 / 20.0 | `--slippery` | 9.74487 % | 9.77062 % | **9.75774 %** | rejected: clears the bar twice over, and nothing asked for that |
| 5 | 40.0 / 40.0 | `--slippery` | 28.24009 % | 28.16399 % | **28.20204 %** | rejected: 0.70 m/s commanded delivers 0.50 m/s of ground — a different vehicle, not a wet patch |

**Why 16.0 and not 20.0.** The requirement is a floor, not a target:
`straight` must show **more than 5 %** longitudinal slip and the truck
must still finish its profiles. Row 3 is the **lowest row that clears
it**, with 24 % of margin over the bar. Every further point of slip is a
larger departure from the plant every other figure in this file, in
`EVIDENCE_SENSORS.md` and in `EVIDENCE_LATERAL_TUNE.md` was measured on,
and buys nothing the question needs. Row 4 is not wrong; it is
unmotivated, and a value chosen past a requirement is a value chosen for
its look.

**The response is markedly non-linear, which is why there is a ladder and
not an interpolation.** Slip per unit of compliance runs 0.136, 0.266,
0.386, 0.488 and 0.705 %/unit across rows 0–5: doubling the compliance
from 7 to 16 multiplies the slip by **6.5**. A value predicted from row 0
by proportion would have been 2.2 % and would have missed the bar
entirely.

### 8.3 The accepted plant, and that the truck can still drive on it

**Longitudinal slip at the 0.7 m/s cruise: 0.95299 % → 6.17873 %**, a
factor of 6.5, on all three wheels, with the normal forces and every
other property of the vehicle unchanged.

**Drivable, and the floor check is the one `config.yaml`'s `square:`
block already specifies.** The slippery `square` finishes — `drive_route`
exits 0 on every run below — and the bound is the rear axle's worst
position plus the whole 1.50 m envelope radius at every bearing at once,
which is a bound and not a reconstruction:

| | rear axle, x | rear axle, y | envelope bound, y max | margin to `WallNorth` at y = 14.00 |
|---|---|---|---|---|
| nominal `square` (`…085338`) | −16.9820 … −15.3150 | 9.9298 … 11.6515 | 13.1515 | **0.8485 m** |
| slippery `square` (`…110235`) | −17.2314 … −15.3735 | 9.9955 … 11.7357 | 13.2357 | **0.7643 m** |
| slippery `square` (`…095306`) | −17.2861 … −15.3613 | 9.9955 … 11.8018 | 13.3018 | **0.6982 m** |

The slippery path is **wider**, and the reason is in the same runs' own
numbers rather than assumed: the plant delivers **5.985** and **6.022
rad** of turn over the four corners against the nominal **6.301 rad**, so
each corner comes out long and the square opens up. The fork tips — the
point that sizes this profile — reach y = 12.639 and 12.665 slippery
against **12.740** nominal, so the tips are if anything **further** from
the wall; the axle-envelope bound above is the conservative one and the
worse of the two slippery runs still leaves **0.70 m**.

**What "drivable" is not.** It is not "the run completed": an open-loop
table of held commands completes whatever the truck does, which is why
`EVIDENCE_LATERAL_TUNE.md` §6.2 has a bench that measured a wall. It is
the ground truth staying inside the corridor, which is what the table
above reads, and the vehicle still reaching a steady cruise, which is
what §8.2's `slip_bench` rows read — 0.6567 m/s of ground at a 0.7000 m/s
command, against row 5's 0.5026 m/s.

### 8.4 What slip does to the wheel odometry, before any filter touches it

**This half of the claim needs no EKF at all**, which is why it is stated
first and separately: it is a property of dead reckoning, and every
figure is `sensor_evidence.py analyse`'s, on the same instrument and the
same absolute spawn-frame transform as §3.

#### `straight` — the tyre creeps and only the DISTANCE moves

Four runs against five. The no-slip column is `…085033`, `…085135`,
`…085238` (§3.1's own runs, re-analysed with this task's added columns)
plus `…103638`, a fourth taken today and carrying the traction label; the
slippery column is `…095639`, `…095748`, `…095853`, `…110130`, `…110416`.

| figure | no slip, ×4 | **slippery 16.0, ×5** | change |
|---|---|---|---|
| ground-truth path | 11.5871 – 11.6443 m | 10.8467 – 11.0367 m | the truck covers **less ground for the same commands** |
| estimate's path | 12.0764 – 12.1347 m | 11.8769 – 12.0966 m | **the same distance** — the wheel turned the same |
| **path error** | **+4.21 … +4.23 %** | **+9.50 … +9.64 %** | **×2.28** |
| end error | 0.5800 – 0.5826 m | 1.0709 – 1.1052 m | ×1.89 |
| **ALONG-track** | **+0.4834 … +0.4844 m** | **+1.0244 … +1.0567 m** | **×2.17** |
| **CROSS-track** | **−0.3204 … −0.3237 m** | **−0.3120 … −0.3242 m** | **unchanged** |
| **end heading** | **−0.0576 … −0.0579 rad** | **−0.0569 … −0.0579 rad** | **unchanged** |
| rms over run | 0.5217 – 0.5256 m | 1.0090 – 1.0452 m | ×1.98 |

**The two columns that do not move are the measurement.** Longitudinal
slip is a lie about how far a revolution carries the truck; the wheel
odometry's heading comes from integrating the STEER angle and not the
tread, so it does not feel the tyre creeping at all. Cross-track and end
heading are inside their own no-slip run-to-run spread — 0.0032 m and
0.0010 rad — while the along-track error more than doubles. **That is
"the wheel odometry lies about distance" as an isolated reading**, and it
is why the split was worth adding to the instrument: the end-error row alone (×1.87) mixes the two and understates
the one that actually moved.

**Predicted before it was measured, and it lands.** The estimate's path
over the truth's is `k / (1 − s)` with `s` the cruise slip and `k`
everything else the estimator gets wrong (the believed radius, the count
grid). From the no-slip runs, `k = 1.0422 × (1 − 0.0095299) = 1.03224`.
At `s = 0.0617873` that gives **+10.02 %**, against a measured **+9.50 to
+9.64 %**. The 0.4 pp gap is the profile's ramps: `slip_bench` measures at
a steady 0.7 m/s and `straight` spends 4 s of its 18.5 s of motion below
that, where the slip is smaller.

#### `square` — slip takes the heading too, and the reason is the plant

One run against two: `…085338` against `…110235` and `…095306`.

| figure | no slip | **slippery 16.0** | **slippery 16.0** |
|---|---|---|---|
| session | `…085338` | `…110235` | `…095306` |
| ground truth: path | 7.5499 m | 6.8839 m | 6.9445 m |
| ground truth: **turn delivered** | **+6.3012 rad** | **+6.0224 rad** | **+5.9847 rad** |
| ground truth: closure | 0.1019 m | 0.5976 m | 0.7034 m |
| estimate's path | 8.2883 m | 8.2137 m | 8.2676 m |
| **path error** | **+9.78 %** | **+19.32 %** | **+19.05 %** |
| end error | 0.6831 m | 1.3144 m | 1.2845 m |
| ALONG-track | +0.6284 m | +1.2651 m | +1.2292 m |
| CROSS-track | −0.2679 m | −0.3567 m | −0.3731 m |
| **end heading error** | **+0.5229 rad** | **+0.8641 rad** | **+0.8423 rad** |
| rms over run | 0.4003 m | 0.7008 m | 0.6934 m |

**Here the heading DOES move, and it is not the estimator that changed.**
The plant delivers **6.0224** and **5.9847 rad** of turn where it
delivered 6.3012 — a compliant contact patch scrubs more, so each corner
comes out long — and the wheel odometry, which believes its steer angle,
goes on reporting the turn the geometry promises. **The yaw the plant did
not take is almost exactly the yaw error that appeared**: 0.2788 rad
missing against 0.3412 rad of extra heading error on `…110235`, and
0.3165 against 0.3194 on `…095306`.

**So the two profiles ask different questions of the filter**, and that
is exactly what §8.5 needs them for: on `straight`, slip is a pure
distance lie and the gyro has nothing new to correct; on `square`, slip
adds a heading error on top of the distance lie, and the gyro is the only
thing on this vehicle that observes it.

### 8.5 What fusion fixes, what it does not, and the F3 handoff

> **THE FUSED COLUMNS BELOW ARE THE `ax`-FUSED FILTER'S.** §9.3 is the
> same measurement on the shipping filter, and the reading does not
> change: the along-track column still moves by nothing and the
> cross-track column still follows the heading. Kept for §3's reason.

**The two halves of a dead-reckoned position error have different cures,
and the split added by this task measures them apart.**

#### `straight` — the profile that isolates them

`straight` ends on its starting heading, so along-track *is* the distance
lie and cross-track *is* the heading lie, with no mixing between them.
Six runs, four nominal and two slippery, every column `analyse`'s own
`removed`:

| run | plant | **along-track** | cross-track | end heading |
|---|---|---|---|---|
| `…085033` | nominal | **+0.2 %** | −21.7 % | −19.2 % |
| `…085135` | nominal | **−1.2 %** | +68.2 % | +61.3 % |
| `…085238` | nominal | **−0.8 %** | +65.5 % | +60.4 % |
| `…103638` | nominal | **+0.3 %** | −24.3 % | −20.8 % |
| `…110130` | **slippery** | **+0.2 %** | −28.9 % | −23.0 % |
| `…110416` | **slippery** | **−0.4 %** | +71.5 % | +63.4 % |

**Cross-track moves with the heading — run for run, sign for sign, to
within a few percentage points — and along-track does not move at all.**
Across six runs and both plants the along-track column spans **1.5
percentage points**; the cross-track column spans **100**. The gyro
observes heading, so heading is what fusion reaches; nothing on this
vehicle observes distance, so the distance error passes through the
filter untouched, on the dry floor and the wet one alike.

**Which way the heading goes is the bias draw and not the plant.** §3.4
measured that lottery on the nominal plant; the two slippery runs above
drew one of each — `…110130` got a bias that added to the wheel
odometry's heading error (−28.9 %) and `…110416` got one that opposed it
(+71.5 %) — on a heading error slip did not change. **Slip does not
touch this column at all**, which is the point of §8.4's second-to-last
row.

#### `square` — the profile that HAS a heading error, and what slip does to the bargain

| figure | nominal raw | nominal EKF | removed | **slippery raw** | **slippery EKF** | **removed** |
|---|---|---|---|---|---|---|
| **end heading** | +0.5229 rad | +0.3862 rad | **26.1 %** | **+0.8641 rad** | **+0.6554 rad** | **24.1 %** |
| end error | 0.6831 m | 0.5448 m | 20.2 % | 1.3144 m | 1.0657 m | 18.9 % |
| along-track | +0.6284 m | +0.4900 m | 22.0 % | +1.2651 m | +1.0058 m | 20.5 % |
| cross-track | −0.2679 m | −0.2381 m | 11.1 % | −0.3567 m | −0.3521 m | 1.3 % |
| rms over run | 0.4003 m | 0.3100 m | 22.6 % | 0.7008 m | 0.5571 m | 20.5 % |
| **path error** | **+9.78 %** | **+9.79 %** | — | **+19.32 %** | **+19.33 %** | — |

**This is where fusion earns its keep, and the fraction is not the
reading — the metres are.** The gyro removes about a quarter of the
heading error on both plants (26.1 % dry, 24.1 % wet), but slip made that
error 65 % bigger, so what the same quarter is worth grows from
**0.137 rad to 0.209 rad**. On the profile that has a heading error, the
worse the floor, the more the gyro is carrying.

**And the row that does not move is the whole of §8.5's other half.**
The path error is reproduced from the filter's input to **one hundredth
of a percentage point** on both plants — +9.78 → +9.79 % dry, +19.32 →
+19.33 % wet. A filter cannot make its input's distance error go away,
and one whose path *shortens* is losing motion rather than correcting it
(§4, reading 3).

**Why along-track improves 20.5 % here and 0.2 % on `straight`, stated
because it looks like a contradiction and is not.** The split is taken at
the ground truth's END course. On a profile that turns 6 rad, a heading
error rotates the estimate's whole trajectory, so the end-position error
resolved on that final axis carries a heading component in BOTH of its
parts. **The split separates distance from heading only on a run that
does not turn** — which is exactly why `straight` is the profile the
claim is stated on, and why the path-error row is carried beside it: that
one needs no frame at all.

#### The honest handoff, and it is F3's by name

**The residual this phase cannot remove is the along-track error**, and
on the slippery plant it is **+1.055 to +1.058 m over 11.02 m of travel
— +9.62 % of path** on `straight`, and **+1.006 m on +19.33 %** of a
6.88 m `square`. It grows without bound with distance driven, and no line
of `ekf.yaml` changes that: both of this filter's inputs are **rates**,
and the integral of a biased rate is a pose whose error has no ceiling.
The accelerometer cannot correct a distance (its own bias
double-integrates to 98 m over 100 s unaided) and the gyro says nothing
about distance at all.

Bounding it needs a measurement of where the vehicle actually **is**,
which means something **outside** the vehicle: **F3's map and AMCL**,
stacking `map` → `odom` on the transform this phase publishes. Nothing in
F2 observes absolute position, and `ekf.yaml`'s `world_frame` is the odom
frame precisely so that this filter cannot quietly become that edge's
owner. **The number F3 is being handed is +1.06 m of along-track error
per 11 m driven on a wet floor, and it is the number to score `map` →
`odom` against.**

### 8.6 THE FILTER DIVERGES AT STARTUP, SILENTLY, AND THE CHANNEL IS MEASURED

**This is a defect in the F2 Task 1 deliverable, found by Task 2 while
trying to measure it, and it is recorded before the tables it governs
rather than after them.**

On **2026-08-26 from about 09:50 onward**, `robot_localization`'s
`ekf_node` — the same binary, the same `ekf.yaml`, the same committed
code that produced §3's thirteen sessions that morning — **blows up
during its first cycles on most bringups of this stack**. It does so on
the nominal plant and the slippery one alike, and it says **nothing at
all**.

**The signature, captured off the wire from before the child starts**
(one bringup, subscriber attached ahead of `start`, sim-time stamps):

| EKF output | sim | x [m] | vx [m/s] | pose covariance `xx` |
|---|---|---|---|---|
| first | 10.210 | 0 | 0 | 5.00001e-4 |
| **second** | 10.230 | **−1.33917e+48** | **−1.58214e+50** | **2.42253e+84** |
| third | 10.252 | −3.34259e+48 | −1.54222e+50 | 1.36916e+86 |
| … | … | saturates at −5.7379e+48 | decays back to sane over ~8 s | 2.9127e+87 |

One 20 ms cycle takes the covariance from 5e-4 to **2.4e84** and the
velocity state to **1.6e50**. The position saturates and then never
moves again for the rest of the run while the **yaw carries on working
normally** — so the published pose is a plausible-looking heading bolted
to a position 5.7e48 m from the origin.

**What it is NOT.** Every candidate that would make this a data problem
was measured and excluded on the same rig:

- **The clock never goes backwards**: 0 inversions in 15 480 `/clock`
  messages over a bringup.
- **The accelerometer is clean**: `ax` over a whole run reads
  −0.0209 to +0.0550 m/s² — a bias plus noise, exactly the model's
  profile — with `linear_acceleration_covariance[0]` a constant
  1.15778e-4 and `angular_velocity_covariance[8]` a constant 3.04503e-6
  on every message, including the first.
- **It is not the wheel odometry's `vy`** (F2 Task 1's reversed ruling,
  the last thing to change in this filter).
- **It is not the initial covariance**, at either of two values.
- **It is not the filter's own rate.**

**What it IS — the ladder, every row a run of fresh bringups on the
committed code, counting how many published a first pose outside 100 m
of the origin:**

| Configuration | bringups | diverged |
|---|---|---|
| shipped `ekf.yaml` | 11 | **11** |
| shipped, on a WSL cold-booted seconds before | 3 | 2 |
| shipped, `frequency` 20 Hz instead of 50 | 3 | 3 |
| shipped, `initial_estimate_covariance` 1e-6 | 3 | 2 |
| shipped, `initial_estimate_covariance` 1e-3 | 4 | 4 |
| shipped, a 10 s delay before the `ekf` child | 5 | 3 |
| shipped, `odom0_config[7]` (**`vy`**) dropped | 4 | 4 |
| shipped + `debug: true` (the node runs ~30× slower) | 3 | **0** |
| **`imu0_config[12]` (`ax`) dropped, everything else shipped** | **4** | **0** |

**Thirteen of fourteen on the shipped configuration; zero of four with
the accelerometer channel out.**

> **HOW STRONG THAT IS, MEASURED LATER AND WEAKER THAN THIS SECTION
> IMPLIES: §9.2.** Every row of this ladder is UN-PAIRED, and the base
> rate drifts by an order of magnitude through the day. The `ax` row is
> 0 of 4 against a bracketed 87 % — p ≈ 3e-4 on n = 4 — and the
> interleaved follow-up that would have settled it came back **null**
> (0 of 6 against 0 of 6, in a window where the rate had collapsed).
> Read this table as *suggestive*, not as proof, and read §9.2 before
> quoting it.

**AND THE RATE MOVES THROUGH THE DAY, which is stated so that two lucky
bringups are not read as a refutation.** The eleven-for-eleven row was
taken between 09:50 and 10:20; by 11:00 the three sessions of §8.7 cost
**4, 1 and 2** bringups, and a fourth had not landed in six. Whatever
sets the odds is not identified — it is not the WSL's uptime (a machine
cold-booted seconds before still gave 2 of 3), not the machine's memory
(12 GiB free), and not the plant (the IMU at rest is identical on both,
mean ±0.0195 m/s² and sd 0.0103). What does NOT move is the ladder: with
`ax` out, four of four bringups were clean, and the eleven-row table
above was taken as consecutive sets rather than cherry-picked. **The
claim is that this configuration fails often and silently, not that it
fails every time** — and a filter that starts correctly two times in
three is not a filter this track can publish figures from without the
check §8.6 added. **The best candidate is the IMU's
linear-acceleration channel** - the two configurations that stop it are
the one that removes `ax` and the one that makes the node thirty times
slower - and whatever it is, it is a numerical instability rather than
bad data. §9.2 is how strong that candidacy is once the drifting base
rate is accounted for, and the answer is *suggestive, not proven*. What
IS solid is the discriminator between a clean bringup and a diverged
one: **how soon the filter's first CORRECTION lands after its first
PREDICT** — clean runs correct three
cycles in with the covariance grown to ~4.6e-3, diverged runs correct on
the next cycle with it still at 5.0e-4.

**THIS SECTION FOUND IT; §9 IS WHAT WAS DONE ABOUT IT.** As first
written, this section changed nothing: the ruling that fused `ax` was
T1's brief, and reversing another task's ruling is not an implementer's
call. It was put to the controller with the table above, and **reversed
on this measurement** — the same precedent as the `vy` reversal of §4 and
the opposite direction. §9 is the reversal, the reconciliation this
section could not do, and the shipping filter's own figures. The ruling
ledger for this track is
`.superpowers/sdd/2026-08-26-m5v3-f2-fusion/progress.md`.

**What this gate DID change is that the failure can no longer reach a
table.** `EVIDENCE_FUSION.md` §2.6 named three ways this filter fails
silently; this is the fourth, and the first that produces *numbers*
rather than an absence of them. Two guards were added, both on
`evidence_core.diverged_at()`, both tested without a simulator:

- **`record` checks the filter with the truck standing still at the
  spawn pose, before the drive is spent.** Nothing has moved, so the
  fused estimate must still be at the origin of its own odom frame. A
  diverged filter is refused there, naming the check, and no run is
  driven.
- **`analyse` refuses to score a session whose fused stream left the
  building**, naming the sample and the bound. `config.yaml`'s
  `evidence.analyse.fused_sanity_m` is **100.0** m — the floor's longest
  diagonal is 57.7 m and the worst end error ever measured on this track
  is 1.29 m, so the bound has seventy-seven times the headroom of the
  largest honest figure while the failure misses it by **forty-five
  orders of magnitude**.

**How the sessions in §8.3–§8.5 were obtained, stated plainly.** Each was
taken by bringing the stack up, reading the filter's pose with the truck
at rest, and **stopping and starting again if it had diverged** — the
retry counts are in §8.7. That is not selection among measurements: a
bringup in which the filter blew up before the vehicle moved is a
bringup that failed, in the same class as a child that died during
startup, and this stack already refuses those. No run was ever discarded
after it was driven, and no run was discarded for what it measured.

### 8.7 The capture

All sessions are under `m5_ver3/logs/evidence/` and all are untracked.
Every one was taken headless, from a stack stopped and started for it, and
every one carries its traction in `session.txt` — the four re-analysed
`…0850xx`/`…085338` runs are §3's own and predate the label, which
`analyse` reports as *unrecorded* rather than reading as nominal.

| Session | profile | traction | `drive_route` | fused stream |
|---|---|---|---|---|
| `drive-straight-20260826-085033` | straight | *unrecorded* (nominal by provenance) | 0 | sane |
| `drive-straight-20260826-085135` | straight | *unrecorded* (nominal by provenance) | 0 | sane |
| `drive-straight-20260826-085238` | straight | *unrecorded* (nominal by provenance) | 0 | sane |
| `drive-square-20260826-085338` | square | *unrecorded* (nominal by provenance) | 0 | sane |
| `drive-straight-20260826-103638` | straight | **nominal 7.0 / 7.0** | 0 | sane |
| `drive-straight-20260826-095639` | straight | **slippery 16.0 / 16.0** | 0 | **DIVERGED** |
| `drive-straight-20260826-095748` | straight | **slippery 16.0 / 16.0** | 0 | **DIVERGED** |
| `drive-straight-20260826-095853` | straight | **slippery 16.0 / 16.0** | 0 | **DIVERGED** |
| `drive-square-20260826-095306` | square | **slippery 16.0 / 16.0** | 0 | **DIVERGED** |
| `drive-straight-20260826-110130` | straight | **slippery 16.0 / 16.0** | 0 | sane |
| `drive-straight-20260826-110416` | straight | **slippery 16.0 / 16.0** | 0 | sane |
| `drive-square-20260826-110235` | square | **slippery 16.0 / 16.0** | 0 | sane |

The four **DIVERGED** rows are §8.6, and they are kept rather than
deleted: their ground truth and their raw wheel odometry are four of the
five slippery `straight`/`square` runs §8.4 is measured on, and `analyse`
prints exactly those and withholds the rest. The three **sane** rows are
where §8.5's fused columns come from, and the bringups each one cost are
**4, 1 and 2** — with a fourth run, a second slippery `square`, still
being retried when this section was written. That is the incidence of
§8.6 as it stood on the afternoon of 2026-08-26, from the other side.

**Reproducing any row of §8.4 needs no simulator**, exactly as §6 says of
§3 — and it needs one command per plant, because the tool will not read
the two into one document:

```
python3 m5_ver3/tools/sensor_evidence.py analyse \
    m5_ver3/logs/evidence/drive-straight-20260826-095639
```

Asked for a mixed set it refuses, names both groups and prints the two
commands that would have been right. Asked for a session whose filter
diverged it prints the ground truth and the raw wheel odometry, withholds
every fused figure, and **exits non-zero**.

### 8.8 What this section did not do

- **It did not rule on `ax`.** §8.6 is a finding with a measurement
  attached, not a change. `ekf.yaml` is untouched by this task.
- **It did not re-measure `corner_creep` under slip.** `straight` and
  `square` are what the brief names and what the two halves of the claim
  need; a third profile would have been a third of the rig time for a
  reading neither half is missing.
- **It did not tune the slippery values for a nicer table.** The ladder
  is in §8.2 with its rejected rows, the acceptance was the requirement's
  own floor, and the chosen row is the lowest one that clears it.
- **It did not touch `model.sdf`, `ekf.yaml`, or anything outside
  `m5_ver3/`.** Constraint 12's first rung held, so the generated-variant
  branch was never taken.

---

## 9. The `ax` reversal — the ruling, the paradox, and the shipping filter

**F2 Task 2 continued, 2026-08-26.** §8.6 measured `ekf_node` diverging
at startup and named the channel; the controller reversed the T1 ruling
that fused it on that measurement, the same way the `vy` ruling was
reversed *into* the filter a day earlier and in the opposite direction.
Both reversals live in this track's ruling ledger,
`.superpowers/sdd/2026-08-26-m5v3-f2-fusion/progress.md`. This section is
what changed, what it cost, and the one question §8.6 could not answer.

**The change is one entry.** `imu0_config`'s thirteenth flag — `ax` —
is `false`. The IMU now contributes `vyaw` and nothing else; the wheel
odometry still contributes `vx`, `vy` and `vyaw`; nothing else in
`ekf.yaml` moved, and `model.sdf` is untouched.

**The architecture agrees with the measurement, which is why the reversal
is cheap.** `vx` is measured **directly at 500 Hz** by a wheel odometry
whose own `vx` covariance is derived from measured quantiser dither
(2.3383e-2). An acceleration channel on top of that is a redundant
predictor between corrections that arrive every 2 ms — and §5 already
said the accelerometer cannot correct a **distance** on this stack, its
own 0.01961 m/s² bias double-integrating to 98 m over 100 s unaided.
§2.3 and §2.4 record the two other ways this same channel misbehaves on
this device: gravity removal kills it outright (a zero-length quaternion
normalised into a division by zero), and an uncorrected lever arm puts up
to 0.0361 m/s² — 3.4σ of the accelerometer's own noise — onto exactly
this axis whenever the vehicle turns.

### 9.1 The paradox: the same tree does both, and that is measured

§8.6 left one question open, and it is the one that decides whether §3's
tables can be believed at all: **if the shipped configuration diverges on
13 of 14 bringups, how did T1 record thirteen consecutive sessions whose
filters all ran?**

| Question | Answer | How it was measured |
|---|---|---|
| Did the divergence **post-date a change**? | **No.** | `cc7fe8e` — the exact tree that produced §3's tables — checked out into a clean `git worktree` and started six times: **6 of 6 diverged**. The shipped tree `d7f5ba7`, restored with `git stash`, diverged too. The only runtime difference between the two commits is a `grep` that runs before anything is started. |
| Does it **self-reset**? | **No.** | In all six diverged sessions the recorder's **first** sample is already outside the bound (`diverged_at` returns **0**, not a later index), and the position is still saturated 2 555 samples later. |
| Does the recorder's stream **start after a re-convergence**? | **No.** | Same measurement: sample 0 of `ekf_odom.csv` reads 1e47 in every diverged session. There is no healthy prefix and no healthy suffix. |
| Did T1's thirteen starts **land in the 1-in-14**? | **No — the RATE moved.** | Thirteen consecutive clean bringups at a 13/14 failure rate has probability (1/14)¹³ ≈ **7e-16**. The rate in T1's window was near zero, not lucky. |
| **Are any of T1's published figures contaminated?** | **No.** | Every one of the thirteen fused streams in §3 and §4 passes the bound, and the largest distance any of them reaches from its own origin is **12.13 m** on a `straight` run that drove 11.6 m. Not one published cell is a diverged filter's. |

**So the honest verdict is: the code is not the variable and the rate
is.** Measured through the day, on the same repository and the same
machine:

| Window | Configuration | bringups | diverged |
|---|---|---|---|
| 08:28 – 08:54 | shipped, `ax` fused (T1's own sessions) | 13 | **0** |
| 09:50 – 10:22 | shipped, `ax` fused | 11 | **11** |
| 10:23 (WSL cold-booted seconds before) | shipped, `ax` fused | 3 | 2 |
| 11:2x | `cc7fe8e`, `ax` fused, isolated worktree | 6 | **6** |
| 11:4x | shipped, `ax` fused | 3 | **0** |

**What sets the rate is not identified, and the candidates that were
excluded are excluded by measurement**, not by argument: it is not the
WSL's uptime (a machine cold-booted seconds earlier still gave 2 of 3);
not free memory (12 GiB); not the plant (`--slippery` and nominal behave
alike, and the IMU at rest is identical on both — mean ±0.0195 m/s²,
sd 0.0103); not the **per-run IMU bias sign draw**, which gz redraws
every run and which correlates with nothing (**3 of 12** diverged with a
positive `ax` bias against **3 of 11** with a negative one, over the 23
recorded sessions); and not anything visible in a recorded session at all
— the clean and diverged sets overlap completely in first-clock sim time
(7.31–14.81 s against 8.22–12.04), in first-EKF sim time and in
real-time factor (0.9991–1.0100 against 0.9994–1.0064).

**It is a race inside the filter's own first cycles that leaves no trace
in any recorded stream**, which is precisely why §9.4 exists: the only
way to know is to ask the filter, at bringup, every time.

### 9.2 How strong is the `ax` attribution? Weaker than §8.6 implied

**§8.6 said "it is the IMU's linear-acceleration channel". This section
says how confident that is, and the answer is: supported, not proven.**
The measurement that was meant to settle it came back null, and a null
that is filed rather than dropped is the only kind worth having.

**The problem is that the base rate drifts.** §9.1's table is the
warning: the same `ax`-fused configuration measured 0 of 13, then 11 of
11, then 6 of 6, then 0 of 3, across one morning on one machine. Every
row of §8.6's elimination ladder was taken **un-paired** — one
configuration for a few bringups, then the next — so each row carries
whatever the ambient rate was in its own few minutes.

**What the ladder does have is a bracket.** Grouping every `ax`-**fused**
set run between roughly 09:50 and 11:25 — eleven shipped, three
cold-booted, three at `initial_estimate_covariance` 1e-6, four at 1e-3,
four with `vy` dropped, three at 20 Hz, five with a 10 s delay, four with
a 25 s delay, four with the child started before the bridges, six on
`cc7fe8e` — gives **41 diverged of 47 bringups, 87 %**. The single
`ax`-**dropped** set in that same window, run between the 1e-6 set and
the 1e-3 set, gave **0 of 4**. Against an 87 % rate, four clean in a row
has probability **≈ 3e-4**.

**And the paired test that would have settled it is null.** Because a
bracket is weaker than an interleave, the two arms were alternated
bringup by bringup in one window — `ax` fused, `ax` dropped, twelve
bringups:

| Arm | bringups | diverged |
|---|---|---|
| `imu0_config[12]` **true** (`ax` fused) | 6 | **0** |
| `imu0_config[12]` **false** (shipping) | 6 | **0** |

**Zero and zero.** The ambient rate had collapsed by the time the paired
test ran — the same window in which three solo `ax`-fused bringups also
came up clean — so the experiment designed to discriminate had **nothing
to discriminate**. It does not support the attribution and it does not
refute it. It says the window was quiet.

**So the honest state of the claim, in one line each:**

- **The reversal is right regardless**, and not because of this
  attribution: `vx` is measured directly at 500 Hz with an honestly
  derived covariance, the acceleration channel is a redundant predictor
  between corrections 2 ms apart, §5 already said it cannot correct a
  distance here, and §9.3 measures that removing it **costs nothing**.
  A channel that buys nothing measurable and is *suspected* of a
  catastrophic failure is not a channel to keep.
- **The attribution itself is suggestive and under-powered.** 0 of 4
  against a bracketed 87 % is p ≈ 3e-4 on n = 4; the paired follow-up is
  null. Anybody re-opening this should interleave, and should do it in a
  window where the ambient rate is first *shown* to be non-zero.
- **And dropping `ax` is in any case a mitigation and not a cure.** The
  first bringup of §9.5's evidence batch — shipping filter, `ax` already
  out — was **refused by the gate of §9.4**, and the bringup after it was
  clean. One in fifteen shipping bringups after the reversal still
  diverged.

**Which is why the gate is the part of this that does not depend on being
right.** §9.4 asks the filter at every bringup whether it is still one.
That check is correct whether the cause is `ax`, something `ax` makes
more likely, or something neither of us has named — and it is what makes
a wrong attribution survivable instead of expensive.

### 9.3 The shipping filter, re-measured — and what the reversal cost

**Eight sessions, all on the shipping configuration, all 2026-08-26,
stack stopped and started for each, every one carrying its traction
label.** The dry standard set is `straight` ×3, `square` and
`corner_creep`; the slippery set is `straight` ×2 and `square`. The
question this table has to answer first is not "is the filter better" —
it is **"did anything move at all"**.

#### The raw wheel odometry did not move, and that is the control

An `ekf.yaml` flag must not be able to reach the estimator that feeds the
filter. §3.0 made this check across thirteen sessions and two `vy`
settings; it is made again here across the reversal:

| Profile | figure | `ax` fused (§3, §8.4) | **`ax` dropped (shipping)** | verdict |
|---|---|---|---|---|
| `straight` | raw end error | 0.5800 – 0.5826 m (7 runs) | **0.5807 – 0.5821 m** (3) | inside, spread **2.6 mm** over all ten |
| | raw path error | +4.21 … +4.23 % | **+4.22 %** | inside |
| | raw end heading | −0.0576 … −0.0579 rad | **−0.0577 … −0.0578** | inside |
| `straight`, slippery | raw end error | 1.0709 – 1.1052 m (5) | **1.1040 – 1.1050 m** (2) | inside |
| | raw path error | +9.50 … +9.64 % | **+9.62 … +9.63 %** | inside |
| `corner_creep` | raw end error | 0.1941 – 0.1943 m (3) | **0.1943 m** | inside, to the digit |
| | raw path error | +7.64 … +7.65 % | **+7.64 %** | inside |
| `square` | raw end error | 0.6724 – 0.6831 m (3) | **1.1161 m** | **OUTSIDE — and it is the PLANT** |

**The `square` row is a correction to §3.0's own claim, not a regression,
and the correction is measured.** That profile is an open-loop table of
held commands and its *delivered* turn does not repeat; §3.0 said so and
quoted the spread of its own three runs, **+6.2082 to +6.3012 rad**.
Over **all six** post-F1.5 nominal squares this track has recorded the
delivered turn is **+5.9060 to +6.3124 rad** — nearly **0.41 rad** of
spread, three times what §3.0 published. Today's run delivered
**+6.1438 rad**, comfortably inside that, and its bigger raw end error is
the arithmetic consequence: the truck turned less, the estimator went on
believing its steer angle, and the heading error grew to +0.7342 rad. So
`square`'s raw end error is **not a figure that reproduces run to run on
this plant at all**, and any before/after fraction taken from a single
one of them has that spread underneath it. The `straight` and
`corner_creep` rows — which do repeat, to 2.6 mm and to the digit — are
where the reversal's "did anything move" question is actually answered.

#### And the fused estimate did not move either

`straight` is the profile that separates the two halves. `removed` is
`analyse`'s own column; the `ax`-fused rows are §8.5's, reproduced here
beside the shipping ones:

| run | plant | `ax` | **along-track** | cross-track | end heading |
|---|---|---|---|---|---|
| `…085033` | dry | fused | **+0.2 %** | −21.7 % | −19.2 % |
| `…085135` | dry | fused | **−1.2 %** | +68.2 % | +61.3 % |
| `…085238` | dry | fused | **−0.8 %** | +65.5 % | +60.4 % |
| `…103638` | dry | fused | **+0.3 %** | −24.3 % | −20.8 % |
| `…113225` | dry | **dropped** | **+0.5 %** | −24.4 % | −20.5 % |
| `…113330` | dry | **dropped** | **−1.0 %** | +70.1 % | +62.7 % |
| `…113435` | dry | **dropped** | **−1.0 %** | +69.7 % | +62.5 % |
| `…110130` | wet | fused | **+0.2 %** | −28.9 % | −23.0 % |
| `…110416` | wet | fused | **−0.4 %** | +71.5 % | +63.4 % |
| `…113755` | wet | **dropped** | **+0.3 %** | −30.7 % | −23.9 % |
| `…113903` | wet | **dropped** | **+0.2 %** | −22.7 % | −19.9 % |

**The two arms are indistinguishable.** Dropping the accelerometer
channel changed the along-track column by nothing (both arms sit inside
±1.2 percentage points of zero) and left the cross-track/heading pair
doing exactly what §3.4's bias-draw lottery says it does: the runs that
drew a gyro bias opposing the wheel odometry's heading error removed
60–70 % of it in **both** arms, and the runs that drew one adding to it
made it 19–31 % worse in **both** arms. **The reversal cost nothing
measurable**, which is what the architecture predicted: `vx` is measured
directly at 500 Hz, so the acceleration channel was a redundant predictor
between corrections 2 ms apart.

**`corner_creep`, the profile the gyro helps most on**: raw end error
0.1943 m → EKF 0.1512 m, **22.2 % removed**, heading +0.0155 → −0.0077
rad (**50.4 %**), against the `ax`-fused set's +53.7 %, +64.0 % and
−98.1 % — the same lottery, the same range.

**`square`, dry, on the shipping filter**: heading +0.7342 → +0.6116 rad,
**16.7 % removed**; end error 1.1161 → 0.9377 m, **16.0 %**; rms 0.6013 →
0.4997 m, **16.9 %**; path error **+10.77 % → +10.78 %**, untouched as
always. The `ax`-fused square removed 26.1 % of a heading error that
started at +0.5229 rad. **The two fractions are not comparable and the
spread above is why** — the plant handed the two runs different corners.
What is comparable, and what does not move, is the path-error row.

**`square`, slippery, is the one pair the plant DID match**, and it is
worth stating because it is the only place the two arms differ by more
than a percentage point:

| | `ax` fused (`…110235`) | **shipping (`…114011`)** |
|---|---|---|
| ground truth: turn delivered | +6.0224 rad | **+6.0192 rad** |
| raw end heading error | +0.8641 rad | **+0.8471 rad** |
| **heading removed** | **24.1 %** | **17.2 %** |
| end error removed | 18.9 % | 16.0 % |
| path error | +19.32 → +19.33 % | **+19.14 → +19.14 %** |

Same corner to 0.003 rad, same raw heading error to 0.017 rad, and
**24.1 % against 17.2 %**. That is a 7 pp gap on one pair, and it is
**inside the per-run spread §3.4 already measured for this figure**: on
`square` the gyro helps whichever way its bias draw fell, and T1's three
runs removed **+15.3 %, +26.1 % and +26.2 %**. Both of today's numbers
sit in that band. With one run per arm the honest statement is that this
profile's fraction is drawn from a wide distribution and two samples
cannot separate the arms — the profiles that *can*, because they repeat,
are `straight` and `corner_creep`, and they show no difference at all.

#### What the slip scenario's headline reads on the shipping filter

Every claim of §8 survives the reversal unchanged:

| claim | `ax` fused | **shipping** |
|---|---|---|
| slip moves along-track and not heading (`straight`, raw) | along ×2.17, cross and heading unchanged | **along +0.4835 → +1.0554 m (×2.18), cross −0.3216 → −0.3239, heading −0.0577 → −0.0579** |
| fusion cannot reach along-track | +0.2 / −0.4 % | **+0.3 / +0.2 %** |
| fusion reaches cross-track | −28.9 / +71.5 % | **−30.7 / −22.7 %** |
| the path error passes straight through | +9.64 → +9.65 % | **+9.62 → +9.62 %** |

### 9.4 The gate: a filter that explodes may never again report ALIVE

**`m5v3.sh start` now asks the filter whether it is still one**, once,
after every child is confirmed alive and while the truck is still
standing where it was spawned. `tools/ekf_health.py` reads **one**
message off `/m5v3/odometry/filtered` and refuses the bringup if the
largest magnitude anywhere in its covariance is over
`config.yaml`'s `ekf.startup_check.covariance_max`.

**Why a covariance and not a pose.** A pose far from the origin is
ambiguous at bringup — a truck may legitimately have been driven — but a
covariance is not: this filter starts at ~1e-9 on its diagonal and a
healthy one is at 0.08–0.23 when this runs. **And not the `xx` diagonal
alone**: a diverged message on this stack reads 5.74e87 on `xx` and
−5.08e91 off it, so a gate reading `covariance[0]` would be reading the
smaller of the two by four orders of magnitude.

**The ceiling is derived, not chosen.** Measured over six bringups of the
shipping configuration with the truck at spawn, the worst entry reads
**0.08244 to 0.22776**. The pose covariance grows at the process noise's
0.05 per second while nothing aids position, so a stack reaching this
line a minute late would read about 3 — which is why the ceiling is not
1.0. **100.0** is 440× the largest healthy reading and the failure misses
it by **eighty-two orders of magnitude**.

**Bounded, because the failure mode next door is a hang.**
`ros2 topic echo --once` waits for its message for ever, so a filter that
published nothing at all would hang the bringup in silence rather than
refuse it — `tools/noise_probe.sh`'s lesson, learned there by hanging the
probe. `ekf.startup_check.timeout_s` is 20 s and a read that times out is
its own refusal, naming the topic.

**Verified in both directions on this rig:**

| | Result |
|---|---|
| shipping filter, healthy | `ekf: healthy, worst covariance 0.22464 against a ceiling of 100` — bringup continues, exit 0 |
| ceiling temporarily lowered to 0.001, real message from a real filter | `ekf_health: REFUSED at check 'the filter came up without diverging'` … *"the largest entry is 0.1116"*, then `m5v3: REFUSED at check 'the filter came up sane, and not merely alive'`, `THE STACK IS INCOMPLETE`, **exit 1** — and `status` still reports **6 alive, 0 dead**, which is the whole point |
| a captured diverged message (5.74e87 / −5.08e91) | refused by `evidence_core.require_covariance_under()` in the suite, no simulator |
| an **empty** read | refused, not passed as "covariance 0, healthy" — a gate that failed open on a silent topic would fail open on exactly the case it exists for |

**The parse is not in the shell.** `evidence_core.worst_covariance()`
handles both spellings `ros2 topic echo` produces (a YAML block sequence
and an inline list), takes magnitudes so a negative off-diagonal is read
at its size, and refuses a message with no covariance in it. Ten tests,
no ROS, no Gazebo.

**And it is not a temporary measure.** The channel that made the filter
fragile is gone, and this gate stays: an instability that was silent once
is a thing this stack asks about out loud from now on, so a later change
cannot reintroduce it and be found out three tables later. §9.2 is why
that is not hypothetical.

### 9.5 The capture, the suite, and what this section did not do

**Eight sessions, all on the shipping filter, all untracked under
`m5_ver3/logs/evidence/`, all headless, `drive_route` exit 0 on every
one, and every fused stream sane:**

| Session | profile | traction |
|---|---|---|
| `drive-straight-20260826-113225` | straight | nominal 7.0 / 7.0 |
| `drive-straight-20260826-113330` | straight | nominal 7.0 / 7.0 |
| `drive-straight-20260826-113435` | straight | nominal 7.0 / 7.0 |
| `drive-square-20260826-113540` | square | nominal 7.0 / 7.0 |
| `drive-corner_creep-20260826-113659` | corner_creep | nominal 7.0 / 7.0 |
| `drive-straight-20260826-113755` | straight | **slippery 16.0 / 16.0** |
| `drive-straight-20260826-113903` | straight | **slippery 16.0 / 16.0** |
| `drive-square-20260826-114011` | square | **slippery 16.0 / 16.0** |

**Nine bringups produced those eight sessions.** The ninth is §9.2's: the
first bringup of the batch was refused by §9.4's gate, on the shipping
filter, and no run was driven on it.

**The suite**, extended again by this section:

```
$ python -m pytest m5_ver3/tests/ -q
148 passed

$ python m5_ver3/tools/evidence_core.py --selftest
26/26 checks passed

$ python m5_ver3/nodes/wheel_odom_core.py --selftest
12/12 checks passed
```

138 → **148**: ten for `worst_covariance()` and
`require_covariance_under()`, the parse and the comparison behind §9.4's
gate. The ones that matter are the two that would let a gate fail OPEN —
*an empty read is refused rather than passing the ceiling*, because a
topic nobody publishes on echoes nothing and "no numbers, so the worst is
zero, so the filter is healthy" is the exact failure this gate exists to
catch; and *the worst covariance is the largest magnitude and not the
first entry*, because a diverged message on this stack is four orders of
magnitude bigger off the diagonal than on it.

**What this section did not do:**

- **It did not identify what sets the divergence rate.** §9.1 lists what
  was excluded by measurement and says plainly that the cause is not
  identified. The gate does not need it identified; it needs it asked
  about.
- **It did not re-measure `aisle`**, or the `--static` captures, or
  anything in `EVIDENCE_SENSORS.md` or `EVIDENCE_MODEL_V3.md`. Those are
  the plant's and the raw estimator's, and §9.3's control shows the raw
  estimator did not move.
- **It did not delete the `ax`-fused tables.** §2, §3, §4 and §8 stand as
  the reversed ruling's record, each labelled where it starts, for the
  reason §4 was kept when the `vy` ruling went the other way.
- **It did not touch `model.sdf`.** The plant is byte-identical to F1.5's.

## 10. The laser-odometry arm — the third opinion, and whether it pays (F2 Task 3)

**A scan matcher on the nav lidar, behind a flag, measured against §9.3.**
`rf2o_laser_odometry` estimates the vehicle's planar motion by aligning
consecutive scans. It is the only estimator this stack has ever carried
that observes the **floor**: the wheel odometry observes a shaft, the IMU
observes the chassis, and neither can tell that the tyre is creeping.
§8.5's headline — *"nothing on this stack observes distance, so fusion
cannot reach the along-track error"* — is a claim about a stack with two
sensors in it, and this section is the third.

> **EVERY FIGURE IN §10 IS OFF A DIFFERENT ESTIMATOR FROM EVERY FIGURE
> ABOVE IT.** `m5v3.sh start --rf2o` is a **different filter** on the
> same plant, exactly as `--slippery` is the same filter on a different
> plant, and it is labelled by the same mechanism: `start` writes
> `arm=wheel+imu+rf2o` to `paths.traction_file`, `status` prints it,
> `record` copies it into every `session.txt` and **refuses to record
> without it**, and `analyse` **refuses a set of sessions that mixes the
> two arms**, naming both groups and printing the two commands that
> would have been right. §9.3's eight sessions carry no `arm=` line at
> all — the label did not exist — and they are reported as
> *"unrecorded (session predates F2 Task 3's arm label)"* rather than as
> `wheel+imu`, for the reason §8's `UNLABELLED` gives: a label is worth
> something only because it was READ off the running stack.

**The package, pinned.** MAPIRlab/rf2o_laser_odometry, branch `ros2`,
commit **`b38c68e46387b98845ecbfeb6660292f967a00d3`** (that branch's tip
on 2026-08-26; authored 2023-04-28). It is **not in the Jazzy archive for
any distribution**, so there was nothing to `apt-get` and
`m6/tools/install_broker.sh`'s vendoring shape had nothing to vendor.
`tools/install_rf2o.sh` is how it reproduces — no sudo at any point, a
colcon workspace under the user's own `$HOME`
(`config.yaml` `rf2o.workspace`), idempotent, refusing by name at every
step, and writing a manifest beside the build that records what it
fetched. **Nothing had to be vendored and no `sudo` was attempted:**
every dependency the package names was already on the rig — `ament_cmake`
and `eigen3_cmake_module` under `/opt/ros/jazzy`, Eigen's headers at
`/usr/include/eigen3`, Boost's headers, `colcon`, `cmake` 3.28.3 and
`g++` 13.3.0. Clean build, `-DCMAKE_BUILD_TYPE=Release`, **21.8 s**; a
second run of the script prints `already installed` and rebuilds nothing.

---

### 10.1 What rf2o actually publishes on this plant — four defects, measured

**None of the four is reachable from a parameter.** The node declares
seven and not one of them is about any of these. `nodes/rf2o_twist.py` —
the stack child `rf2ocov` — is the smallest honest thing between the scan
matcher and the filter, and `nodes/rf2o_twist_core.py` holds every
decision it makes as arithmetic a test can reach without a simulator.

#### (a) The frame its numbers are in is rotated by π from the scan's

`rf2o` builds its point cloud with beam bearings running from `-fovh/2`
to `+fovh/2` about the sensor's own x axis — it computes
`fovh = |angle_max - angle_min|` and **never reads `angle_min`**.
`forklift_ver3`'s nav lidar is a 270° window from **+0.7853982** to
**+5.4977871 rad**, centred on model −x *on purpose*, so that the blind
90° points astern and the truck drives into the full aperture
(`model.sdf` argues it where the numbers are, and
`EVIDENCE_MODEL_V3.md` §4 checks the offset window against known world
geometry). Read off the wire:

```
angle_min: 0.7853981852531433   angle_max: 5.497786998748779
angle_increment: 0.005817763973027468   frame_id: nav_lidar_link
```

So rf2o's whole solution is the true one turned by the window's centre
bearing, **π**. Measured on `drive-straight-20260826-123131`: the truck
driving **forwards** at a ground-truth body `vx` of **−0.6948 m/s** —
forward is `base_link` −x on this vehicle, which is why the wheel
odometry reads **−0.7473** — was published by rf2o as
`twist.linear.x = +0.58`. Right magnitude, wrong sign, because
cos(π) = −1.

**The correction is exact and it is derived, not asserted.** The relay
reads `angle_min` and `angle_max` off the **same message rf2o consumed**
and rotates by `0.5·(angle_min + angle_max)` — which is **0.0 for every
lidar written the conventional symmetric way**, so the correction is the
identity on any plant that never had this problem. It publishes nothing
until that first scan has arrived and says so in its log:

```
aperture 0.7853982 .. 5.4977870 rad (270.0 deg wide), centred on +3.1415926 rad = +180.0 deg
rf2o's own frame is therefore rotated +180.0 deg from nav_lidar_link, and every twist
and pose it publishes is turned back by that before it leaves here
```

**Verified against the ground truth on all eight A/B sessions**, not
merely reasoned about — the sign of the corrected `vx` against the sign
of the truth's body `vx`, over every sample where the truck was actually
moving:

| session | profile | paired samples, \|truth\| > 0.2 m/s | signs agree |
|---|---|---|---|
| `…124609` `…124717` `…124823` | dry `straight` | 386 each | **386 / 386, three times** |
| `…124929` | dry `square` | 258 | **258 / 258** |
| `…125046` | dry `corner_creep` | 329 | **329 / 329** |
| `…125244` `…125347` | wet `straight` | 403 each | **403 / 403, twice** |
| `…125451` | wet `square` | 226 | **226 / 226** |

#### (b) The covariance is 36 zeros, and a zero is not read as "unknown"

`publish()` default-constructs the message and assigns position,
orientation, `linear.x`, `linear.y` and `angular.z` — and nothing else.
Read off the wire with `ros2 topic echo --once /m5v3/rf2o/odom_raw`:
**all 36 entries of the pose covariance and all 36 of the twist
covariance are `0.0`.**

`robot_localization` takes each measurement's covariance out of the
MESSAGE — there is no per-sensor override parameter, by design — and it
does **not** treat a zero variance on a channel it has been configured to
fuse as "ignore this". §10.2 measures which of the two it does.

#### (c) The published `linear.x` is the SCANNER's forward speed

Upstream computes `lin_speed = acu_trans(0,2) / dt`, where `acu_trans` is
the accumulated scan-to-scan transform **in the laser's frame**, and then
stamps the message `child_frame_id: base_frame_id`. The POSE it publishes
*is* composed through the mount
(`robot_pose_ = laser_pose_ * laser_pose_on_robot_inv_`); the TWIST is
not. The scanner stands **0.55 m forward and 0.40 m to starboard** of
`base_link`, so in a turn the two speeds differ by `yaw_rate · mount_y`:
at §2.4's measured peak yaw rate of 0.2687 rad/s that is **0.1075 m/s**
of forward speed the vehicle does not have — **15 % of cruise**, and a
BIAS across the whole of a corner rather than noise about it. The relay
applies the rigid-body relation, **after** the frame rotation and not
before (the two orders differ by twice the term).

#### (d) `twist.linear.y` is a hard-coded `0.0`, so it is not fused

Upstream computes a local lateral velocity (`kai_loc_(1)`) and then
writes a literal zero into the message instead. **Measured: all 912
samples of a 60 s `--static` capture read exactly 0.0**, and so does
every sample of every drive. The lateral half of the lever arm needs the
scanner's OWN `vy`, which never leaves that process, so no arithmetic
outside it can reconstruct `base_link`'s.

**So `ekf_rf2o.yaml` leaves this arm's `vy` flag `false`, and that is not
§4's ruling reversed.** `base_link` genuinely translates sideways at
`d · yaw_rate` in every turn and the wheel odometry's `vy` channel is
still fused for exactly that reason. What is refused here is a **hard-
coded constant wearing a measurement's name**: fusing it would be fusing
an assertion that this vehicle never moves sideways, against a filter
that already knows better from a source that computes it. Recovering it
would need a patched rf2o, which is a later task's `rf2o.commit` and not
a number invented in a relay.

```
   x     y     z    roll  pitch  yaw    vx    vy    vz   vroll vpitch vyaw   ax   ay   az
 false false false false false false  TRUE false false false false TRUE  false false false
```

#### And what does NOT need correcting: the yaw rate

A constant rotation of the frame does not change an angular velocity, and
neither does a lever arm — so the relay passes `angular.z` through
untouched. That it is right to is **measured against the ground truth
rather than argued**, on every sample where the truck was actually
turning:

| session | paired samples, \|truth\| > 0.05 rad/s | signs agree | mean rf2o / truth |
|---|---|---|---|
| dry `square` `…124929` | 543 | **543 / 543** | **0.9943** |
| dry `corner_creep` `…125046` | 287 | **287 / 287** | **1.0004** |
| wet `square` `…125451` | 565 | **565 / 565** | **0.9881** |

**rf2o's yaw rate is the best single channel on this vehicle.** Over a
whole dry `square` its integrated turn is **−0.65 %** against the ground
truth's +6.2200 rad, where the wheel odometry's is **+10.7 %**. It is
also the channel this filter weights *least* — see §10.6.

#### (e) …and one that is not rf2o's, but is fatal on this stack

**rf2o looks up `base_link` ← the scan's frame EXACTLY ONCE**, in the
handler for its first scan, and on a failed lookup it logs the exception
and then **carries on with the default-constructed transform**. There is
no retry.

Measured on this rig on 2026-08-26 with the arm's children spawned
*after* the bridges, which is where they were first put: rf2o came up at
a moment when scans were already flowing, its first scan arrived
**106 ms** later, and the latched `/tf_static` message had not reached
its listener yet —

```
[ERROR] [...] [CLaserOdometry2DNode]: "base_link" passed to lookupTransform argument
                                       target_frame does not exist.
[INFO]  [...] [CLaserOdometry2D]: Got first Laser Scan .... Configuring node
```

— and for the rest of that session `Laser odom [x,y,yaw]` and
`Robot-base odom [x,y,yaw]` printed **identical numbers**, which is what
an identity mount looks like. Nothing else was wrong: the child was
alive, the topic was at rate, the relay was forwarding, the filter was
fusing, `status` read **9 alive, 0 dead**.

**Two changes, and the second one is the mechanism.**
- **The arm is spawned BEFORE the bridges.** There is then no scan
  publisher at all while rf2o comes up, so it sits in
  `Waiting for laser_scans` through the bridge, the image bridge, the
  wheel odometry and the IMU transform — **ten seconds of real work, not
  a sleep** — and the static transform is long since in its buffer when
  the first scan arrives. A jump in `/clock` does not undo it: tf2 stores
  static transforms in a cache whose `clearList()` is a no-op, which is
  why they answer for any query time in the first place.
- **`m5v3.sh` reads the child's log and refuses.** `rf2o_laser_odometry`
  contains **exactly one `RCLCPP_ERROR` in the whole package**
  (`src/CLaserOdometry2DNode.cpp:125`, at the pinned commit) and it is
  inside that catch block — so an `[ERROR]` line in `logs/rf2o.log` **is**
  that lookup having failed, whatever tf2's wording for the particular
  failure was. `check_rf2o_transform()` runs after the dead-child check
  and beside §9.4's covariance gate, and refuses the bringup by name.
  Grepping the *message text* would have tied the check to one of tf2's
  several exception strings; the ERROR level is the property that holds.

> **The twist would have survived it, and that is not a reason to let it
> pass.** rf2o's `lin_speed` and `ang_speed` are both computed from the
> scan-to-scan increment and are independent of the mount, so THIS phase
> — which fuses twist only — would not measurably have noticed. A stack
> that publishes a wrong thing nobody currently reads is a trap set for
> whoever reads it next.

With the ordering fixed, `Laser odom` and `Robot-base odom` differ by
exactly the mount, and `logs/rf2o.log` carries **0 ERROR lines** on every
one of the eight A/B bringups:

```
Laser odom      [x,y,yaw]=[0.582632 -0.381852 0.000431]
Robot-base odom [x,y,yaw]=[0.032459  0.017911 0.000431]
```

---

### 10.2 The covariance, derived — and the control that shows it matters

**Both readings are of rf2o's OWN output and neither touches the ground
truth**, so F2 global constraint 13 holds inside the calibration and not
only at run time. `tools/noise_probe.sh` takes the plant's own sensor
noise by exactly this instrument, at rest, for exactly this reason.

| channel | at rest, 912 samples over 60 s | at cruise, 231 samples | **SHIPPED** |
|---|---|---|---|
| `vx` | **2.6403e-03** (sd 0.0514 m/s) | 2.2663e-03 | **2.6403e-03** |
| `vyaw` | **9.3723e-05** (sd 0.00968 rad/s) | 2.5445e-05 | **9.3723e-05** |
| `vy` | 0.0 exactly, 912 of 912 | 0.0 exactly | not fused |

- **at rest** — the temporal spread of the whole twist over a 60 s
  `record --static` (`static-rest-20260826-124015`). The reference is
  that the truck is not moving, which is a fact about the experiment and
  not a signal.
- **at cruise** — the residual of the same channel about a **2 s moving
  mean of itself**, over the steady window of a `straight` run
  (`drive-straight-20260826-124323`, the window where the wheel odometry
  is within 5 % of its own peak, sim 222.33 – 237.57 s). The reference is
  the signal's own local level.
- **the larger of the two is taken**, per channel — the honest direction.

**For scale:** the wheel odometry's own `vx` covariance is **2.3383e-2**
(sd 0.153 m/s, F1's measured quantiser dither at 2 ms), so this filter is
told rf2o's forward speed is **8.9× more precise**. Its `vyaw` covariance
is 1.1111e-5 and the IMU's gyro is 3.045e-6, so rf2o's yaw rate is the
**least** trusted of the three by 8× and 31×.

> **WHAT THESE NUMBERS DELIBERATELY DO NOT CONTAIN.** A covariance
> describes DISPERSION. rf2o also has a large **scale error** on this
> plant — §10.5's table — and that is a BIAS, which no covariance can
> express and which this block does not inflate itself to disguise. That
> is `wheel_odom.covariance`'s own ruling applied again: it derives its
> `vyaw` from the steer bias alone and refuses to invent a term for the
> tyre scrub that actually dominates a corner, *"because inventing one
> would be a hand in the weighting."* A gain fitted against the ground
> truth would have made this arm's own error vanish into a constant and
> left nothing to A/B.

#### The control: a zero covariance is BELIEVED, not ignored

**A second `ekf_node`, on the same live stack, at the same time,
identical to the shipping filter in every parameter except which rf2o
topic it reads.** It publishes to a topic of its own and broadcasts no
transform, so it cannot disturb what it is measured beside. Both filters
saw the same 500 Hz wheel odometry, the same IMU and the same drive.

| | reads | twist covariance | x after an 11.601 m forward `straight` |
|---|---|---|---|
| ground truth | — | — | **11.601 m travelled** (world −17.000 → −5.399) |
| shipping filter | `/m5v3/rf2o/odom` (the relay) | **measured**, above | **−11.606 m** — 5 mm out |
| control | `/m5v3/rf2o/odom_raw` (rf2o's own) | **36 zeros** | **+6.032 m** — *the wrong way* |

**Both defects land in that one row.** The control's estimate is dragged
**backwards by more than half the true distance** by a 15 Hz sensor,
against a 500 Hz wheel odometry saying the opposite — which is not what a
filter that ignored an unset covariance would produce, and settles §10.1(b)
by measurement. And it is dragged backwards rather than merely short,
which is §10.1(a) with the correction taken out.

> `robot_localization` says **nothing at WARN or above** about either.
> The control node's entire log for the run is one *"Waiting for clock to
> start…"* and two *"Failed to meet update rate"* — the substitution it
> makes for a zero variance is at DEBUG. This is §2.6 again: the filter
> is silent about what it is being fed.

---

### 10.3 The default stack is not merely equivalent to §9.3's — it is the same

**`start` without `--rf2o` was verified inert, on the rig, after the arm
was built and wired:**

| check | result |
|---|---|
| children | **6 alive, 0 dead** — `world bridge imgbridge odom imutf ekf`. No `lasertf`, no `rf2o`, no `rf2ocov`. |
| `status` | `arm  wheel+imu  m5_ver3/ekf.yaml alone (no --rf2o)` |
| rf2o topics on the graph | `ros2 topic list \| grep rf2o` → **nothing** |
| the filter's command line | **one** `--params-file`, `m5_ver3/ekf.yaml`, and **no `odom1`** — character for character §9.3's |
| `ekf_rf2o.yaml` | never named on any command line, never read |

That last row is why the overlay is a **separate file** rather than a
block inside `ekf.yaml`. `ekf_node` auto-declares every override it is
handed, so an `odom1:` line sitting in the shipping parameter file would
be *found* by `robot_localization`'s sensor loop and the arm would be on
by default with the flag doing nothing. Kept apart, the OFF path reads
one unchanged file and the ON path reads two — a difference anybody can
check with `ls` and a diff rather than by reasoning about rclcpp's
parameter loading. With the flag, the same command line gains exactly two
arguments:

```
--params-file .../m5_ver3/ekf.yaml
--params-file .../m5_ver3/ekf_rf2o.yaml        <- only with --rf2o
-p odom1:=/m5v3/rf2o/odom                      <- only with --rf2o
-p use_sim_time:=true  -p frequency:=50.0  ...
```

**§9.4's covariance gate still gates the start with the arm live.** Every
bringup in this section ran it: `ekf: healthy, worst covariance 0.0942 –
0.20604 against a ceiling of 100`, the same band as §9.4's measured
0.08244 – 0.22776, and it **refused** bringups in this section too — see
§10.7.

---

### 10.4 What the arm costs this rig

**The instrument is `/proc/<pid>/stat` fields 14 and 15** — `utime` and
`stime`, the process's own accumulated user and system CPU time in clock
ticks (`getconf CLK_TCK` = 100 here). Read before and after a bounded
interval and differenced, that is exactly the CPU seconds that process
spent, with no sampling error and nothing inferred from a load average.
Divided by the scans delivered in the same interval it is the per-scan
cost. **`ros2 run` forks the executable**, so the pid `m5v3.sh` records
for `ekf` and `bridge` is an idle python wrapper and these are the real
children, found by pattern and filtered by `GZ_PARTITION`.

| process | truck AT REST, 60.238 s | truck DRIVING a `square`, 35.186 s |
|---|---|---|
| `rf2o_laser_odometry_node` | 5.130 s — **8.52 % of one core** | 2.920 s — **8.30 % of one core** |
| `rf2o_twist.py` (the relay) | 1.020 s — 1.69 % | 0.580 s — 1.65 % |
| `ekf_node` | 7.100 s — 11.79 % | 4.130 s — 11.74 % |
| `wheel_odometry.py` | 16.240 s — 26.96 % | 9.500 s — 27.00 % |
| `parameter_bridge` | 9.350 s — 15.52 % | 5.490 s — 15.60 % |
| `image_bridge` | 1.800 s — 2.99 % | 1.000 s — 2.84 % |
| gz server (`world`) | 47.350 s — 78.59 % | — |

**Per scan, at 15.15 Hz delivered:** `5.130 / (60.238 × 15.15)` =
**5.62 ms** at rest and `2.920 / (35.186 × 15.15)` = **5.48 ms** while
driving. **The cost does not depend on the motion**, which is the
algorithm and not a coincidence: it runs a fixed 5-level coarse-to-fine
pyramid with 5 IRLS iterations per level on every scan, whatever the
vehicle is doing.

**The whole arm against the same stack without it**, measured back to
back on the same bringup pair:

| | `wheel+imu` | `wheel+imu+rf2o` | delta |
|---|---|---|---|
| `rf2o_laser_odometry_node` | — | 8.52 % | **+8.52 pp** |
| `rf2o_twist.py` | — | 1.69 % | **+1.69 pp** |
| `ekf_node` (a third sensor to fuse) | 10.45 % | 11.79 % | **+1.34 pp** |
| `wheel_odometry.py` | 26.74 % | 26.96 % | +0.22 pp |
| `parameter_bridge` | 14.60 % | 15.52 % | +0.92 pp |
| **the arm, total** | | | **≈ 11.6 % of one core** |

**11.6 % of one core is 0.58 % of this 20-thread machine, and the
real-time factor cannot see it** (`tools/rtf_probe.sh`, 30 s, 296
samples each, back to back):

| | mean RTF | median | floor | ceiling |
|---|---|---|---|---|
| `wheel+imu` | 0.9991 | 0.9999 | 0.9531 | 1.0504 |
| `wheel+imu+rf2o` | 0.9988 | 0.9999 | 0.9498 | 1.0126 |

**And the GPU pays nothing at all**, which is worth saying because it is
the resource `EVIDENCE_MODEL_V3.md` §6 measured the 3D lidar costing
0.999 → 0.85 of. The nav lidar was **already bridged and already
rendering** before this arm existed — gz renders a sensor while something
subscribes, and `parameter_bridge` has subscribed to it since F1. This
arm adds a ROS-side consumer of a stream that was already being produced.

**Delivered rate: every scan is used.** `analyse`'s own rate table, over
the eight A/B sessions: `rf2o_odom` at **15.1372 – 15.3066 Hz** of sim
time against the nav lidar's 15.1515, `dt_max = dt_med = 0.066 s`, and
the row count matches `scan_nav`'s to within one message on every
session. `rf2o.freq_hz` is 30 — twice the scan rate — because rf2o's main
loop consumes at most one buffered scan per pass; the cost of the extra
passes is a `WARN` line and a predicate.

---

### 10.5 The A/B — does scan-matching odometry pay for its CPU here?

**The `wheel+IMU` columns are §9.3's and were NOT re-run.** The `+rf2o`
columns are eight fresh sessions on the same profiles, same plants, same
tool, one bringup per drive, taken 2026-08-26 12:46 – 12:55.

#### The control first: the raw wheel odometry did not move

An arm the filter fuses must not be able to reach the estimator that
feeds it. §3.0 made this check across two `vy` settings and §9.3 across
the `ax` reversal; here it is across the third sensor:

| profile | figure | `wheel+imu` (§9.3) | **`+rf2o`** | verdict |
|---|---|---|---|---|
| dry `straight` | raw end error | 0.5807 – 0.5821 m (3) | **0.5796 – 0.5807 m** (3) | inside, spread **2.5 mm** over all six |
| | raw path error | +4.22 % | **+4.22 … +4.23 %** | inside |
| | raw end heading | −0.0577 … −0.0578 rad | **−0.0576 rad** ×3 | inside |
| wet `straight` | raw end error | 1.1040 – 1.1050 m (2) | **1.0972 – 1.1019 m** (2) | inside |
| | raw path error | +9.62 … +9.63 % | **+9.56 … +9.58 %** | inside |
| dry `corner_creep` | raw end error | 0.1943 m | **0.1943 m** | inside, to the digit |
| dry / wet `square` | raw end error | 1.1161 / 1.3057 m | **0.6914 / 1.3063 m** | wet inside; **dry OUTSIDE — and it is the PLANT** |

The dry `square` row is §9.3's own caveat again and not a regression:
that profile is an open-loop table of held commands and its **delivered
turn does not repeat**. §9.3 measured +5.9060 to +6.3124 rad across six
runs; today's delivered **+6.2200 rad** against §9.3's **+6.1438**, and
the raw end error follows it. `straight` and `corner_creep` — which do
repeat, to 2.5 mm and to the digit — are where "did anything move" is
actually answered, and nothing did.

#### The row that has never moved before

**§8.5's headline and §9.3's control both say the same thing about the
path-error row: fusion passes it straight through, because nothing on the
stack observes distance.** Here is that row on both arms:

| profile | plant | `wheel+imu` raw → EKF | **`+rf2o` raw → EKF** |
|---|---|---|---|
| `straight` | dry | +4.22 → **+4.22 %** | +4.23 → **+1.30 %** |
| | | | +4.22 → **+1.36 %** |
| | | | +4.22 → **+1.51 %** |
| `square` | dry | +10.77 → **+10.78 %** | +10.56 → **+8.40 %** |
| `corner_creep` | dry | +7.64 → **+7.64 %** | +7.63 → **+6.67 %** |
| `straight` | **wet** | +9.63 → **+9.63 %** | +9.58 → **+5.63 %** |
| | | +9.62 → **+9.62 %** | +9.56 → **+5.71 %** |
| `square` | **wet** | +19.14 → **+19.14 %** | +19.14 → **+15.20 %** |

**Eight rows, and the third sensor moves every one of them.** It is the
first time anything on this track has.

#### The along-track error, which is what that row buys

`analyse`'s own `removed` column, magnitudes, a negative meaning the
filter made it worse:

| profile | plant | session | ALONG-track | CROSS-track | end heading | rms | end error |
|---|---|---|---|---|---|---|---|
| `straight` | dry | §9.3 `…113225` | +0.5 % | −24.4 % | −20.5 % | −4.0 % | −7.8 % |
| | | §9.3 `…113330` | −1.0 % | +70.1 % | +62.7 % | +6.5 % | +14.3 % |
| | | §9.3 `…113435` | −1.0 % | +69.7 % | +62.5 % | +6.5 % | +14.2 % |
| | | **`…124609`** | **+99.6 %** | −28.7 % | −24.2 % | **+37.8 %** | +28.9 % |
| | | **`…124717`** | **+96.5 %** | +82.1 % | +67.8 % | **+63.6 %** | +89.7 % |
| | | **`…124823`** | **+97.9 %** | −18.1 % | −20.0 % | **+40.7 %** | +34.7 % |
| `square` | dry | §9.3 `…113540` | +17.4 % | +8.2 % | +16.7 % | +16.9 % | +16.0 % |
| | | **`…124929`** | **+27.8 %** | +7.7 % | +25.8 % | **+28.4 %** | +25.0 % |
| `corner_creep` | dry | §9.3 `…113659` | +47.2 % | +7.3 % | +50.4 % | +13.0 % | +22.2 % |
| | | **`…125046`** | **−34.0 %** | +41.4 % | **−104.1 %** | +17.3 % | +1.1 % |
| `straight` | **wet** | §9.3 `…113755` | +0.3 % | −30.7 % | −23.9 % | −1.2 % | −2.7 % |
| | | §9.3 `…113903` | +0.2 % | −22.7 % | −19.9 % | −0.9 % | −2.0 % |
| | | **`…125244`** | **+54.1 %** | +67.2 % | +60.3 % | **+40.4 %** | +55.1 % |
| | | **`…125347`** | **+55.0 %** | −19.5 % | −20.4 % | **+37.1 %** | +44.4 % |
| `square` | **wet** | §9.3 `…114011` | +16.8 % | +2.4 % | +17.2 % | +16.1 % | +15.6 % |
| | | **`…125451`** | **+23.8 %** | +4.3 % | +24.5 % | **+24.9 %** | +22.0 % |

**Read the ALONG-track column and nothing else, and the answer is
unambiguous.** Three dry `straight`s: **+0.5 / −1.0 / −1.0 %** becomes
**+99.6 / +96.5 / +97.9 %**. Two wet `straight`s: **+0.3 / +0.2 %**
becomes **+54.1 / +55.0 %**. The rms column follows it — dry `straight`
**−4.0 / +6.5 / +6.5 %** becomes **+37.8 / +63.6 / +40.7 %** — because on
a straight run the along-track error IS most of the error.

**The cross-track and heading columns are unchanged in character**, and
they should be: they are §3.4's gyro-bias lottery, whose sign is drawn
per run and which this arm does not touch. Both arms have runs at
+60 – 82 % and runs at −18 – −31 %, and the rf2o runs are drawn from the
same distribution.

**`corner_creep` is the one profile the arm makes worse**, and by the
biggest single margin in the table: −34.0 % along-track and −104.1 % on
the heading, on a run whose end error nevertheless came out 1.1 % better.
That is the profile with the smallest travel (3.97 m), the slowest speed
and the largest sustained yaw rate — where the lever-arm term is the
largest fraction of the signal and where the wheel odometry was already
nearly right (raw end error 0.1943 m, a quarter of `straight`'s). **The
arm has the least to add there and the most to disturb.**

#### And rf2o ON ITS OWN, which is why the fused numbers are what they are

| session | profile | rf2o `vx` / truth `vx`, mean over the run | rf2o's own end displacement vs truth | rf2o's own integrated turn vs truth |
|---|---|---|---|---|
| `…124609` | dry `straight` | **0.8263** | −17.20 % | — |
| `…124717` | dry `straight` | **0.8307** | −17.63 % | — |
| `…124823` | dry `straight` | **0.8365** | −16.25 % | — |
| `…124929` | dry `square` | 0.8688 | (wanders) | **−0.65 %** |
| `…125046` | dry `corner_creep` | 0.9047 | +46.08 % | **+0.17 %** |
| `…125244` | wet `straight` | 0.8409 | −16.82 % | — |
| `…125347` | wet `straight` | 0.8494 | −16.44 % | — |
| `…125451` | wet `square` | 0.8512 | (wanders) | **−1.14 %** |

**rf2o under-reports this vehicle's forward speed by 9.5 – 17.4 %.** Its
own dead-reckoned pose is worse than the wheel odometry's on a straight
(−17 % against +4.2 %) and far worse on a `square`, where its path length
runs to +86 – 87 % because its internal lateral estimate wanders. **Its
yaw, by contrast, is the most accurate on the vehicle** — under 1.2 % of
integrated turn on every profile that has one.

> **SO THE ALONG-TRACK RESULT ON `straight` IS PARTLY A CANCELLATION, AND
> IT HAS TO BE READ THAT WAY.** The wheel odometry runs **+4.22 %** long
> and rf2o runs **≈ −17 %** short. The filter blended them to
> **+1.3 … +1.5 %**, which solves for rf2o carrying about **13 %** of the
> effective weight on distance — the variance ratio (8.9 : 1 in rf2o's
> favour) pulled back by the sample-rate ratio (500 Hz against 15). Two
> biases of opposite sign at that weight land near zero **on this
> vehicle, at this speed, on this floor**. Change the believed wheel
> radius, or the floor's geometry, or the cruise speed, and the same
> honest covariance lands somewhere else. **What is robust is the
> direction and not the magnitude**: rf2o is the only channel here that
> observes the world, so it is the only one that can pull the distance
> anywhere at all — and on the WET plant, where the wheel odometry is
> 9.6 % long for a reason no calibration can remove, it removed **54 –
> 55 %** of an error the two-sensor filter could not touch by 0.3 %.

---

### 10.6 The verdict

**`docs/reports/m5v3-04` predicted little steady-state gain on a low-slip
floor, with the slip scenario as the arm's chance to earn its place. That
is half right and the half it got wrong is the more interesting one.**

**Confirmed:** on the dry `corner_creep`, which is this track's
low-slip, well-behaved profile, the arm is a **net loss** — −34 % on
along-track and −104 % on heading. On the dry `square` it is a modest
gain over an arm that was already gaining (27.8 % against 17.4 %).

**Refuted:** the arm's gain on the dry `straight` is not small. It is the
**along-track error going to zero**, +0.5 % → +99.6 %, on a profile with
no slip in it at all. The prediction assumed the wheel odometry's dry
error was small; it is not — it is the deliberate **+1.5 % believed
radius** compounding to +4.22 % of path, and that is a *systematic*
error, not a slip. Anything that observes the world removes it, wet floor
or dry.

**Where it earns its place is exactly where §8.5 said the stack had a
hole.** That section closes with an honest handoff — *"nothing on this
stack observes distance… fusion cannot reach along-track… that is F3's"*
— and this arm reaches it, on the plant where it matters most: **54 –
55 % of the wet `straight`'s along-track error removed, against 0.3 %.**

**And it costs almost nothing on this rig.** 11.6 % of one core, 0.58 %
of the machine, 5.5 ms per scan, no GPU at all, and a real-time factor
that cannot tell the two arms apart (0.9991 against 0.9988).

#### Ship-on or ship-off?

**SHIP IT OFF BY DEFAULT — and the reason is not the CPU.** Three
reasons, in the order they matter:

1. **It is not a general result yet.** The `straight` headline rests on
   two biases of opposite sign cancelling at a weight nobody chose (the
   box above). Until the arm's own **−17 % scale error** is understood —
   is it the aperture, the range-flow regularisation on a floor whose
   long walls give little longitudinal parallax, the 25 m range against a
   48 × 32 m arena? — a default-on arm is a default-on cancellation.
2. **It makes one of the five profiles worse**, and it is the profile a
   forklift spends its time in: a slow sustained corner into a pallet.
3. **It is one bringup old.** §9.3's baselines are the product of a phase
   of shaking out; this arm has eight sessions and one afternoon.

**What would make it ship-on**, in the order a later task should attack
it:

- **Fuse the yaw and not the distance.** rf2o's yaw rate is the most
  accurate channel on this vehicle (0.65 – 1.14 % of integrated turn) and
  this filter weights it **31× below the gyro**, because its measured
  dispersion is 31× the gyro's white noise — while the gyro's covariance
  contains no term for its per-run bias, which is the error that actually
  dominates a heading (`ekf.yaml`, and §2.5 measured the draw). An arm
  configured `vyaw`-only, with a covariance that accounted for the gyro's
  bias honestly, is a different and probably better experiment.
- **Find the −17 %.** A scale error that repeats to ±1 % across eight
  sessions is a *systematic* and therefore a fixable one. It is not a
  gain to fit; it is a question to answer.
- **Then re-run this table.**

---

### 10.7 The capture, the suite, and what this section did not do

**Eight A/B sessions, all on the `wheel+imu+rf2o` arm, all 2026-08-26,
all untracked under `m5_ver3/logs/evidence/`, all headless, one bringup
per drive, `drive_route` exit 0 on every one and every fused stream
sane:**

| Session | profile | traction | arm |
|---|---|---|---|
| `drive-straight-20260826-124609` | straight | nominal 7.0 / 7.0 | wheel+imu+rf2o |
| `drive-straight-20260826-124717` | straight | nominal 7.0 / 7.0 | wheel+imu+rf2o |
| `drive-straight-20260826-124823` | straight | nominal 7.0 / 7.0 | wheel+imu+rf2o |
| `drive-square-20260826-124929` | square | nominal 7.0 / 7.0 | wheel+imu+rf2o |
| `drive-corner_creep-20260826-125046` | corner_creep | nominal 7.0 / 7.0 | wheel+imu+rf2o |
| `drive-straight-20260826-125244` | straight | **slippery 16.0 / 16.0** | wheel+imu+rf2o |
| `drive-straight-20260826-125347` | straight | **slippery 16.0 / 16.0** | wheel+imu+rf2o |
| `drive-square-20260826-125451` | square | **slippery 16.0 / 16.0** | wheel+imu+rf2o |

**Two more sessions produced §10.2's covariance and are NOT in any table
above**, because they were recorded before that covariance was set and so
came off a filter weighted differently: `static-rest-20260826-124015` and
`drive-straight-20260826-124323`. The `arm=` label cannot tell them apart
from the eight — it names the sensors, not their weights — so they are
named here instead.

**§9.4's gate refused bringups in this batch too.** The captured tail of
the run log shows the first slippery `straight` taking **four bringups,
three of them refused** by the covariance gate on `the filter came up
without diverging`; the earlier runs' attempts scrolled out of the
captured log and are not claimed.

**So the obvious question was asked properly: does the third sensor make
the filter less likely to start?** §9.2's ruling is that an un-paired
ladder measures the day and not the configuration, because the
divergence rate on this rig drifts by an order of magnitude through one,
so this was run **interleaved** — sixteen bringups, alternating arms, in
one window, the instrument being `m5v3.sh start`'s own exit status:

| arm | refused by §9.4's gate | worst covariance at the gate, across the eight |
|---|---|---|
| `wheel+imu` | **0 of 8** | 0.08496 – 0.20772 |
| `wheel+imu+rf2o` | **0 of 8** | 0.09144 – 0.23772 |

**That is a NULL result and it is reported as one**, exactly as §9.2's
interleaved test was (0 of 6 against 0 of 6): the rate had collapsed
again in that window, so sixteen healthy bringups separate nothing. What
it does establish is the second column — **the arm does not move the
covariance the gate reads**, which sits in §9.4's measured healthy band
of 0.08244 – 0.22776 either way, so the ceiling of 100 is as far from
both arms as it was from one.

**The suite:**

```
$ python -m pytest m5_ver3/tests/ -q
194 passed

$ python m5_ver3/tools/evidence_core.py --selftest
26/26 checks passed

$ python m5_ver3/nodes/wheel_odom_core.py --selftest
12/12 checks passed

$ python m5_ver3/nodes/rf2o_twist_core.py --selftest
22/22 checks passed
```

148 → **194**: twenty-three for `nodes/rf2o_twist_core.py` — the aperture
rotation, the lever arm, the order the two are applied in, the non-finite
guard and the covariance-absence test — and thirteen for the arm label
and the mixed-set refusal it shares a mechanism with. **The one that
matters most is `test_the_rotation_is_applied_BEFORE_the_lever_arm`**:
the two orders differ by twice the lever-arm term, and on this plant —
where the rotation is π and therefore its own inverse — getting it
backwards produces a plausible number on every profile.

**What this section did not do:**

- **It did not patch rf2o.** The pin is upstream's tree, unmodified;
  every correction is outside it, in a relay whose arithmetic is tested.
  Recovering the lateral velocity upstream throws away would need a
  patch, and that is a later task's `rf2o.commit`.
- **It did not identify the −17 % scale error.** §10.6 names it as the
  first thing to attack and does not guess at it here.
- **It did not re-run §9.3.** Those figures are cited, not reproduced,
  and the arm label is the mechanism that stops the two sets being read
  into one document by accident.
- **It did not touch `model.sdf`, the floor, or any figure in
  `EVIDENCE_SENSORS.md` / `EVIDENCE_MODEL_V3.md`.** The plant is
  byte-identical to F1.5's and §10.5's control shows the raw estimator
  did not move.
- **It did not measure `aisle`**, or a `--static` capture on the shipping
  covariance, or the arm at any other lidar rate.
