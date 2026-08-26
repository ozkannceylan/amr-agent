# EVIDENCE_LOCALIZATION_V3.md — the absolute pose, over the frozen map

F3 Task 2. `nav2_amcl` and `nav2_map_server` over the map F3 Task 1
built, froze and scored; AMCL owns `map` → `odom` on top of F2's
`odom` → `base_link`; and the pose that comes out is scored **absolutely**
against ground truth, through the committed registration, with nothing
anchored to anything.

Everything below was measured on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050) on **2026-08-26**, headless, on the
**default estimator arm** (`wheel+imu`), against the committed grid
`maps/warehouse_v3` (md5 `735cdbc6…`). Every figure names the instrument
that produced it.

**The dry set is what this task is accepted on** (owner ruling,
2026-08-26). The slippery set is a stretch measurement, run because it is
cheap and because EVIDENCE_FUSION.md §8.5's debt figure deserves its
answer; **not one
parameter was moved to improve it**, and §7 says what it found.

---

## 0. The answer, before the working

| | |
|---|---|
| **instrument floor** (registration residual, EVIDENCE_MAP_V3 §6.4) | **rms 0.0291 m, MAX 0.1179 m** |
| **DRY, absolute END error**, 5 runs | **0.0382 – 0.1954 m** (median 0.0395) |
| **DRY, absolute rms over the run** | **0.0846 – 0.2436 m** |
| **DRY, absolute END heading error** | **0.0020 – 0.0315 rad** (0.11° – 1.81°) |
| **THE DEBT — dry `straight`**, along-track | EKF **+0.489 / +0.475 / +0.476 m** → absolute **−0.021 / −0.022 / −0.164 m** = **95.7 % / 95.4 % / 65.6 % removed** |
| **THE DEBT — wet `straight`**, along-track | EKF **+1.062 m per 11.0 m** → absolute **+0.176 / −0.305 m** = **83.4 % / 71.3 % removed** |
| **what it cost, jump statistics** | 17 – 44 corrections per run; step **mean 0.027 – 0.084 m**, **median 0.019 – 0.047 m**, **WORST single 0.2591 m dry / 0.4927 m wet** |
| **what it costs the rig** | amcl **5.00 %** of one core, map_server **3.00 %**, against the estimator's **12.00 %**; RTF mean **0.9984** |
| comparison row, DIFFERENT FLOOR AND RIG | m5_ver1 AMCL: rms 0.124 m, max 0.263 m, final 0.093 m, on a floor of 0.1411 m |

**Three of the five dry runs end BELOW the instrument floor's MAX.** That
is stated as a limit and not as a boast: 0.0382 m, 0.0387 m and 0.0395 m
are figures at the resolution of the ruler, and what they say is *the
localiser is not the thing being measured there* — not that it is that
good.

**The debt is paid on the dry floor and mostly paid on the wet one.**
EVIDENCE_FUSION.md §8.5 handed F3 a number: **+1.06 m of along-track
error per 11 m driven on a wet floor**, growing without bound, and
untouchable by any line of `ekf.yaml` because both of that filter's
inputs are rates. Against a map it comes down to **+0.18 m / −0.30 m**.
On the dry floor the same debt (+0.48 m per 11.6 m) comes down to
**−0.02 m** on two runs of three.

**And there is one thing it does NOT do, measured and stated in §9.**
While the vehicle is *moving down a corridor*, the absolute pose carries
a steady **along-track** offset — 0.28 – 0.47 m dry, up to 0.97 m wet —
which collapses as the vehicle decelerates. Cross-track is 0.02 – 0.10 m
throughout. That offset is why the `rms over the run` column is four to
six times the `END error` column on `straight`, and it is the honest
subject of §9.

### What was built

| artifact | what it is |
|---|---|
| `m5v3.sh start --localize` | three more children, two lifecycle transitions, an md5 gate on the frozen map, a seeded initial pose and a bringup gate — §1 |
| `amcl.yaml` | what the LOCALISER does. Every value argued from the model, from F2's MEASURED error, from the map's own measured support, or from the seed — §4 |
| `tools/localization_health.py` | did it come up **localised**, or come up merely alive? — §3 |
| `tools/map_register.py support` | every beam of a recorded drive placed on the map from the TRUE pose. It is where `sigma_hit` and `z_rand` came from — §4.2 |
| `tools/evidence_core.py` + `tests/test_localization_core.py` | the three-transform arithmetic, and 46 tests that reach it with no simulator — §5 |
| `tools/sensor_evidence.py` | two more recorded streams, a third session label, and the absolute score — §5 |
| `m5_ver3/logs/evidence/drive-*-2026082?-23*` | the eight scored sessions — §11 |

---

## 1. What is up, and what owns which edge

### 1.1 Nine children, and the three that are new

`bash m5_ver3/m5v3.sh start --headless --localize`, measured:

```
  world      ALIVE   lasertf    ALIVE   bridge     ALIVE
  imgbridge  ALIVE   odom       ALIVE   imutf      ALIVE
  ekf        ALIVE   map_server ALIVE   amcl       ALIVE
9 alive, 0 dead.
  traction   nominal  slip compliance 7.0 / 7.0 on drive_wheel rear_wheel_left rear_wheel_right
  arm        wheel+imu  m5_ver3/ekf.yaml alone (no --rf2o, no --fuse)
  loc        amcl@735cdbc6  m5_ver3/amcl.yaml, m5_ver3/maps/warehouse_v3
             (registration verified at bringup), map -> odom owned by amcl
```

**`lasertf` is not new and it is not optional here, and that was
measured rather than reasoned.** The nav lidar's static transform used to
belong to the `--rf2o` block; it is hoisted out because AMCL needs it for
a *different* reason. AMCL subscribes its scan through a
`tf2_ros::MessageFilter` keyed on the odom frame, and the scan is stamped
`nav_lidar_link` — so until `odom → base_link → nav_lidar_link` closes,
**not one scan is released**. Measured on this rig with the child absent
(§3.2): `amcl` logs

```
[INFO] [amcl]: Message Filter dropping message: frame 'nav_lidar_link'
       at time 27.260 for reason 'discarding message because the queue is full'
```

every two and a half seconds, publishes **no** pose, broadcasts **no**
transform, and `status` reads **every child ALIVE**.

### 1.2 Two publishers on `/tf`, two disjoint edges

F3 global constraint 15 says this phase adds **exactly one** transform.
It is captured rather than asserted:

| check | without `--localize` | with `--localize` |
|---|---|---|
| `ros2 topic info /tf` | **Publisher count: 1** | **Publisher count: 2** |
| `tf2_echo map odom` | `Invalid frame ID "map" … frame does not exist` | `At time 41.196  Translation: [-0.100, -0.104, 0.000]` |
| `ros2 topic list \| grep -E '^/(map\|amcl_pose\|initialpose\|particle_cloud)$'` | **(none)** | all four |
| the estimator's `world_frame` | `odom` | `odom` — unchanged |

The second publisher is AMCL and the edge it owns is `map` → `odom`. The
estimator's own `world_frame` is the odom frame in both columns
(`ekf.yaml`), so it publishes `odom` → `base_link` and cannot become the
other edge's owner even by accident.

### 1.3 The OFF path is not merely equivalent — it is the same

`start` without `--localize`, verified on the rig after the arm was
wired:

| check | result |
|---|---|
| children | **6 alive, 0 dead** — `world bridge imgbridge odom imutf ekf`. No `lasertf`, no `map_server`, no `amcl`. |
| `status` | `arm wheel+imu`, `loc none  no --localize: nothing publishes map -> odom and this stack has no absolute pose` |
| localisation topics on the graph | **nothing** |
| publishers of `/tf` | **1** |
| the estimator's command line | character for character EVIDENCE_FUSION.md §9.3's: `ekf_node --ros-args -r __node:=m5v3_ekf --params-file …/ekf.yaml -p use_sim_time:=true -p frequency:=50.0 -p map_frame:=map -p odom_frame:=odom -p base_link_frame:=base_link -p world_frame:=odom -p odom0:=/m5v3/wheel_odom -p imu0:=/forklift/gz/imu -r /odometry/filtered:=/m5v3/odometry/filtered` |
| `amcl.yaml` | never named on any command line, never read |

The whole `--localize` block in `start()` is inside one `if`, and
`config.yaml`'s `localization:` keys are in `REQUIRED_KEYS` for the same
reason `fuse:`'s are: a config that has lost a key is refused by its
dotted name at load, on every arm, which is a claim about the FILE and
not about the run.

### 1.4 The freeze, enforced before anything is started

F3 constraint 16 says the map is frozen once scored, and a freeze is a
mechanism. `check_frozen_map()` runs in `start()` **before** the GPU
preflight, before ROS is sourced and before a single child is spawned:

| it checks | against | what it prevents |
|---|---|---|
| `maps/<name>/` exists and carries the grid, its yaml and `registration.yaml` | `config.yaml` `map.dir`, `map.name` | a bringup that discovers the artifact is missing halfway up |
| md5 of `<name>.pgm` | `registration.yaml` `map_md5` | a run against a **rebuilt** grid: a rebuilt map has its own rotation from the building, so every absolute figure would be off by the difference and nothing downstream would notice |
| md5 of `<name>.yaml` | `registration.yaml` `map_yaml_md5` | the same, through the file that carries the resolution, the origin and the two thresholds — and which no consumer of the registration ever hashes |

The refusal names both hashes and ends `NOTHING WAS STARTED`.

**The pose graph is deliberately not hashed here.** `<name>.posegraph`
and `.data` are 62.5 MB and **nothing on this arm reads them** — AMCL
localises in the grid. `build.txt` is their record, and F3 Task 3's arm,
which does read them, is where their check belongs.

**And it is checked a second time, differently, at the other end.**
`map_register.load_registration()` re-hashes the grid at the moment the
transform is USED — in the bringup gate and in `analyse`. The first check
says nothing was *started* against a stale map; the second says no
*number* was produced through one. And a third, in `analyse`, compares
the **session's own** `loc=amcl@<md5>` label against the grid that is
committed now: a session recorded before a rebuild passes the first two
and fails that one.

### 1.5 Two lifecycle nodes, driven, and the order that works

Both nodes are nav2 lifecycle nodes. Started and left UNCONFIGURED they
subscribe nothing, advertise nothing and publish no transform, while
logging nothing that reads as an error — the silent failure
`sim/launch/warehouse_slam.launch.py` recorded for `slam_toolbox` and
`agv/forklift/launch/localization.launch.py` recorded for these two.
`m5v3.sh` drives them itself, as `tools/build_map.sh` drives the mapper,
so one process is one log and one refusal that names it:

```
  map_server configure ok
  map_server activate ok
  amcl configure ok
  amcl activate ok
```

**The order is `map_server` ALL THE WAY UP first.** AMCL's `on_activate`
waits for a map on the latched topic and an INACTIVE `map_server` never
publishes one, so configuring AMCL first leaves it blocked in a
transition with no error at all.

**There is no nav2 `lifecycle_manager`, and both nodes run with
`bond_heartbeat_period: 0.0`.** A bond is a heartbeat with a deadline and
a deadline starves at the real-time factors a simulation reaches; a
manager that declares a healthy node dead is worse than no manager. Left
at its default the bond is a heartbeat to nobody.

**The wait is on the node appearing and each transition is checked.**
`ros2 lifecycle set` against a node not yet on the graph fails
immediately with *Node not found*, which under a sleep-and-hope would be
a bringup reporting success over an unconfigured localiser.

---

## 2. The initial pose, and what is NOT claimed

**The bringup tells AMCL where it is, once, and that is an honest label
rather than a capability.** What goes out on `/initialpose` is
`vehicle.spawn` — the pose `m5v3.sh` spawned the truck at — carried into
the map frame **through the committed registration**, which is the same
transform every score in this file passes through:

```
  loc: amcl@735cdbc6 seeded at map (-0.0793, -0.1458) yaw +0.00326
       = world (-17.000, +10.000) yaw +3.14159 through the committed registration
```

That the spawn pose lands 0.166 m from the map's own origin is not an
error: the map frame IS the odom frame of the mapping run and that odom
frame is the vehicle at spawn, so the offset is the registration's own
`t` against the true spawn pose — 0.11 m and 0.20 m, which
EVIDENCE_MAP_V3.md §6.3 states from the other side.

**It is the measurement harness and not the vehicle.** On a real forklift
there is no world frame and no world→map transform; there is an operator
typing a pose into a screen, and that is exactly what this stands in for.
`agv/forklift/launch/localization.launch.py` makes the same split and
keeps the conversion out of the vehicle's own launch file.

**The prior's uncertainty is the operator's and not the simulator's.**
The harness knows the spawn pose exactly; a prior that *said* so would be
a claim no field bringup can make, and it would start the filter so
peaked that its first scan could not move it. So the covariance published
is nav2's own figure for an RViz *2D Pose Estimate*: 0.25 m² each way
(0.50 m) and 0.06854 rad² (15°).

**It is a MESSAGE and not the `set_initial_pose` parameter, and the
reason is measured.** With `set_initial_pose: false` and no message, AMCL
processes **no scan**, publishes **no pose** and broadcasts **no
transform** — with the scanner's static transform PRESENT and **zero**
message-filter drops, so it is the seed and not the geometry that is
missing. What it logs, every two seconds, is

```
[WARN] [amcl]: AMCL cannot publish a pose or update the transform.
       Please set the initial pose...
```
Two things follow. The first thing this localiser ever says is its answer
to a seed the bringup can point at, rather than an answer to a parameter
that was already there; and the gate in §3 can subscribe *before* the
seed goes out, which is the whole of why it can read anything at all.

**One measured wrinkle, stated rather than hidden.** AMCL answers the
seed with

```
[INFO] [amcl]: initialPoseReceived
[WARN] [amcl]: Failed to transform initial pose in time (Lookup would require
       extrapolation into the future. Requested time 271.702000 but the latest
       data is at time 271.694000, when looking up transform from frame
       [base_link] to frame [odom])
[INFO] [amcl]: Setting pose (271.704000): -0.079 -0.146 0.003
```

That lookup exists to integrate any odometry between the message's stamp
and now. It fails by **8 ms**, every time, because AMCL's own `now()`
runs ahead of the last transform a 50 Hz publisher put on the graph — no
stamp the gate could choose would change that. It falls back to the
identity, which is the *right* answer here: the truck has not moved since
it was spawned, so there is no intervening odometry to integrate. The
`Setting pose` line carries the gate's exact three numbers.

### A KIDNAPPED-ROBOT RECOVERY IS NOT CLAIMED. ANYWHERE.

`amcl.yaml` runs with `recovery_alpha_slow` and `recovery_alpha_fast` at
**zero** and `set_initial_pose` false. This arm is **seeded once and
tracks**. It cannot find itself from nothing, it was never asked to, and
no figure in this file is evidence that it could.

That is a position rather than an omission, and the reason is this floor.
The rack block repeats every **5.75 m** (EVIDENCE_MAP_V3.md §9), so a
particle injected one bay along scores very nearly as well as the truth —
augmented-MCL recovery could relocate the filter to an *equally likely
wrong* pose and produce an error curve with a clean jump in it that reads
as a recovery. With it off, a divergence stays visible as a divergence.

---

## 3. The bringup gate, both directions

`tools/localization_health.py` asks the question `ekf_health.py` cannot:
that gate asks whether the ESTIMATOR is still an estimator; this one asks
whether the LOCALISER knows where it is.

### 3.1 It has to publish before it can read, and the ORDER is the design

AMCL publishes on `amcl_pose` when the particle filter **resamples**, or
when publication is forced. With the truck standing at spawn it never
resamples — `update_min_d` is 0.25 m and nothing has commanded the
vehicle. What forces a publication is an initial pose. So there is
exactly **one message per seed**, and a reader that subscribed *after*
the seed would wait for a second one that never comes, hit its timeout,
and refuse a stack that is perfectly healthy.

```
subscribe → wait for BOTH ends to be discovered → seed → read
```

Both counts are checked before the seed goes out: `get_subscription_count()`
on `/initialpose` says AMCL is listening, and `count_publishers()` on
`/amcl_pose` says AMCL is advertising and this node has found it. A
re-seed at `localization.startup_check.reseed_s` (10 s) covers the case
that discovery reports a match a beat before the transport can carry one;
the printed line says how many went out.

### 3.2 The passing direction, eight times, and one refusing

**PASSING** — every one of the eight scored bringups:

```
  loc: healthy, worst covariance 0.233737 against a ceiling of 1  (/amcl_pose)
       pose map (-0.1004, -0.1041) yaw -0.00759 - 0.0467 m from the seed, bound 0.5
       = world (-16.979, +9.958) yaw +3.13074. registration residual rms 0.0291 m,
         MAX 0.1179 m - no figure at or below the MAX is a measurement of the localiser
       ONE seed, one answer. This arm TRACKS from a known start; it does not
       relocalise from nothing and no kidnapped-robot recovery is claimed.
```

**REFUSING** — the same two nodes brought up over the same map with the
`lasertf` child absent, both lifecycle transitions returning success and
both nodes reporting `active [3]`:

```
localization_health: REFUSED at check 'the localiser answered inside 30s'
                     owned by: /amcl_pose (config.yaml localization.startup_check.timeout_s)
                               and m5_ver3/amcl.yaml
                     3 seed(s) went out on /initialpose and nothing came back.
                     NOTHING ABOUT THIS LOOKS WRONG FROM ANY OTHER ANGLE: both nodes
                     are ALIVE, both lifecycle transitions returned success, and the
                     estimator underneath is sane. What a silent amcl means is one of:
                       - it never received a scan it could transform …
                       - it never received a map …
                       - it never received this seed …
```

and `amcl.log` confirms the first of the three. **Exit 1**, verified
separately against a stopped stack, which `m5v3.sh` turns into a bringup
refusal naming the log.

### 3.3 Two checks, because one would not do

| check | ceiling | what it catches | why the other one cannot |
|---|---|---|---|
| worst covariance entry | `covariance_max` **1.0** | a filter that came up on a **global** prior — a uniform belief over this 48 m hall has a variance of 48²/12 = 192 m² | — |
| distance from the **seed** | `pose_tolerance_m` **0.50 m** | a filter that never **received** the seed | nav2_amcl's own untouched prior carries the **same 0.25 m²** the bringup seeds with, so a localiser answering from it passes any covariance ceiling while sitting at the map origin |

Measured across the eight bringups the first read is **0.218 – 0.254**
against the ceiling of 1.0, and the pose lands **0.047 m** from the seed
against the bound of 0.50 — the filter's own first correction, which is
exactly what a passing gate should show. The ceiling sits four times
above the seed and two hundred times below the failure.

Both refusals are exercised in **both** directions by
`tests/test_localization_core.py` without a simulator, on the arithmetic
in `evidence_core` (`require_worst_under`, `require_pose_near`).

---

## 4. `amcl.yaml` — every parameter, and what it was argued from

Every value was fixed **before the first scored run**, from one of
exactly four sources, and this file records the order so the claim is
checkable. Where a value equals nav2's default it is written anyway and
marked DEFAULT-KEPT, because a default that decides a measurement is a
choice too. **Nothing was tuned against a localisation result** — §9 is
the finding that most obviously invites it, and it was recorded rather
than tuned away.

### 4.1 The motion model — from what F2 MEASURED

`nav2_amcl::DifferentialMotionModel`. This is a tricycle: one steered,
driven wheel leading, two passive wheels trailing. It cannot translate
sideways, which is exactly the constraint this model encodes and exactly
the one `OmniMotionModel` removes.

> **The thing that looks like a counter-argument, and is not.**
> `base_link` on this truck stands 0.50 m FORWARD of the rear axle, so it
> genuinely *has* a lateral velocity — `d·yaw_rate`, the whole reason
> `ekf.yaml` fuses the wheel odometry's `vy` (EVIDENCE_FUSION.md §4).
> That does not reach here. This model decomposes an odometry DELTA into
> rotate–translate–rotate, which represents any planar motion exactly,
> including an arc taken about a point half a metre astern. What it
> constrains is the NOISE structure, and that is still right: this
> vehicle's lateral displacement is *determined* by its rotation and is
> not free.

nav2 ships **0.2 on all five** alphas. Each alpha is a variance ratio, so
0.2 is a 1σ of 0.447 — **45 % of every distance and 45 % of every turn**.
That is not this vehicle. What this model has to swallow is the error of
**F2's EKF**, and F2 measured it:

| alpha | what it scales | derived from | value | nav2 |
|---|---|---|---|---|
| `alpha1` | rotation noise per unit **rotation** | wet `square`: EKF heading error **0.7014 rad on 6.0192 rad delivered = 11.65 %** → 0.1165² | **0.014** | 0.2 |
| `alpha2` | rotation noise per unit **translation** (rad²/m²) | `straight` turns nothing, so its whole heading error is this term: EKF **≈0.072 rad over 11.02 m = 0.0065 rad/m** → 0.0065² | **0.00005** | 0.2 |
| `alpha3` | translation noise per unit **translation** | **the debt**: wet `straight` path error **+9.62 %** → 0.0962² = 0.00926 | **0.010** | 0.2 |
| `alpha4` | translation noise per unit **rotation** (m²/rad²) | wet `square`: EKF cross-track **0.3521 m over 6.0192 rad = 0.0585 m/rad** → 0.0585² | **0.0035** | 0.2 |
| `alpha5` | — | **absent**: it is the OmniMotionModel's strafe term and `DifferentialMotionModel` never reads it | — | 0.2 |

**The WET figures are the ones used**, because one file serves both
plants: `--localize --slippery` reads exactly this file, and a noise
model that could not represent the wet floor's error would put the truth
outside its own particle cloud on the runs that need it most. The dry
error then sits at about half a sigma, which is where a motion model
should put a well-behaved input.

`alpha2` is the one nav2's default is most wrong about: 0.2 would let a
particle's heading wander 0.447 rad over a single metre of straight
driving, which is **68 times** what this vehicle's gyro-corrected heading
actually does.

`alpha4` is partly double-counted with `alpha1` and that is the safe
direction, stated: most of a cross-track error on a turning profile *is*
the heading error rotating the trajectory (EVIDENCE_FUSION.md §8.5 says
so where it explains why `straight` is the profile the split is stated
on). A motion model that is slightly generous costs a slightly wider
particle cloud; one that is too tight puts the truth outside it.

### 4.2 The sensor model — MEASURED off the map, not chosen

nav2's likelihood field weighs one beam as

```
z_hit · exp(−d² / 2·sigma_hit²)  +  z_rand / laser_max_range
```

with `d` the distance from the endpoint to the nearest occupied cell.
Both terms are statements about **this map** and **this sensor**, so both
were measured — `tools/map_register.py support`, which places every beam
of a recorded drive on the frozen grid **from the ground-truth pose** (an
instrument's reading of a reference, never an input to anything the
vehicle runs).

Over the whole mapping drive — 60 scans, 48 660 beams, 45 210 usable:

| | beams | share of usable |
|---|---|---|
| **EXPLAINED** — a mapped surface within 0.30 m | 42 237 | **93.42 %** |
| **UNEXPLAINED** | 2 973 | **6.58 %** |
|   … landing on FREE floor | 2 958 | 6.54 % |
|   … landing in UNKNOWN space | **15** | **0.03 %** |
|   … off the raster | 0 | 0.00 % |
| endpoint-to-surface distance, explained beams | **rms 0.0292 m**, mean 0.0236 m, worst 0.2993 m | |

and on a `straight` recorded on the route these runs actually drive:
**7.37 % unexplained at an rms of 0.0240 m**.

| parameter | value | derived from | nav2 |
|---|---|---|---|
| `sigma_hit` | **0.029** | the measured rms of `d` with the pose right | 0.2 |
| `z_rand` | **0.074** | the measured unexplained share, the larger of the two readings | 0.5 |
| `z_hit` | **0.926** | 1 − z_rand | 0.5 |

`sigma_hit` is **not a datasheet sum and does not need to be** — it
already contains everything that puts a return away from a mapped
surface: the sensor's 0.02 m white noise, its 0.02 m per-run bias draw,
the 0.05 m cell the map is rastered on, and the map's own internal shear.
That it lands within a millimetre of the registration's residual rms
(0.0291 m) is a coincidence of two different measurements of the same
grid, and it is worth saying so rather than presenting it as a
derivation.

nav2's shipped 0.5/0.5 would charge **seven times** the measured share of
the scan to noise, which flattens the posterior and throws away the map
this phase spent a task building.

> **The risk `sigma_hit: 0.029` carries, stated.** A sigma this tight
> means a pose more than about 3σ — 0.09 m — out of position gets a small
> weight in every beam at once, so a filter that is badly wrong cannot
> climb back. That is the same property that makes it accurate when it is
> right, and it is why recovery is OFF and honest rather than on and
> pretending.

**`z_short`, `z_max` and `lambda_short` are deliberately absent**, and
the reason is not preference. They are the BEAM model's parameters and
`nav2_amcl::LikelihoodFieldModel::sensorFunction` reads **neither**: its
whole per-beam weight is the two terms above. Writing them would be three
numbers that decide nothing. The question they exist to answer — what
happens to a return the map cannot explain — **is** answered here, by
`z_rand`, and it was measured.

### 4.3 The beam count, and the vehicle seeing itself

`max_beams: 271`, against nav2's 60. The arithmetic is exact: the scan is
811 beams over 270°, and nav2 subsamples with
`step = (count − 1)/(max_beams − 1)`, so 271 gives `step = 810/270 = 3`
and keeps beam 0, 3, 6 … 810 — **one beam per degree**, none weighted
twice and no part of the aperture unsampled.

*Not 60*, because `sim/worlds/WAREHOUSE_LANDMARKS.md` §5 measured on the
m5_ver1 floor that in a long aisle "the only along-aisle information in
the scan is carried by ten rays or fewer", and one ray in thirteen of ten
rays is under one. *Not all 811*, because a likelihood field treats beams
as independent and a wall's returns are not — sampling one surface three
times over makes the posterior three times more peaked than the
information in it — and because the cost is linear (§10).

**`laser_min_range` is the sensor's own 0.05 m and that is a RULING.**
This vehicle's nav lidar **sees itself**. Measured over a `corner_creep`
recording — a 163° turn, so a return at a constant range cannot be the
room:

```
beams with a CONSTANT range through a 163 deg turn: 49
  bearing index span 286 - 398   (140.3 deg - 177.7 deg)
  range span 0.602 - 1.476 m
```

against a control beam on the same recording that swings 3.58 – 24.75 m.
Those 49 beams of 811 are **6.0 %** of the scan and about **6.5 %** of
usable returns — which is essentially the whole of the 6.54 %
"unexplained, on free floor" above. They are the overhead guard and the
mast in the scanner's own aperture, and no map of a warehouse can ever
explain them.

Raising `laser_min_range` above them would remove them — **and it would
also remove genuine returns.** The mapping drive came within **1.0732 m**
of an obstacle (EVIDENCE_MAP_V3, `map_register.py clearance`) while the
vehicle's own structure returns out to **1.476 m**. The two populations
**overlap**, so no min-range can separate them on this truck. They are
carried by `z_rand` instead, which was derived from them.

### 4.4 The filter, and the update thresholds

| parameter | value | argued from |
|---|---|---|
| `min_particles` | **500** | this bringup SEEDS with a 0.50 m prior rather than localising globally, so the set has one job: represent that prior finely enough that its own sampling noise is not the error reported. σ/√N = 0.50/√500 = **0.022 m** — half a map cell, a fifth of the floor's MAX. Monte-Carlo noise cannot be what limits a score here. |
| `max_particles` | **2000** | a CPU bound: 2000 × 271 at 15 Hz measured **5.00 %** of one core (§10). KLD collapses towards the floor once the posterior is tight, so this is what the filter is *allowed* to spend. |
| `pf_err` / `pf_z` | 0.05 / 0.99 | DEFAULT-KEPT. Nothing measured on this floor argues for moving them; moving them to improve a score is the tuning this file refuses. |
| `resample_interval` | **1** | DEFAULT-KEPT, on this filter's own update rate: sample impoverishment is an argument about filters that update at sensor rate, and this one updates **1.0 – 2.1 times a second** (measured, §8), not 15. |
| `update_min_d` / `update_min_a` | **0.25 m / 0.2 rad** | DEFAULT-KEPT and **derived**: over 0.25 m of travel F2's measured along-track error accumulates **10.6 mm dry and 24 mm wet**, both UNDER the map's own residual rms of 0.0291 m. A finer threshold would correct against distances this map cannot resolve, at 15 Hz, for a full filter update each time. |
| `recovery_alpha_slow/fast` | **0.0 / 0.0** | §2. |
| `transform_tolerance` | 1.0 s | DEFAULT-KEPT: it must exceed the interval between broadcasts, which is one scan period (1/15 s), so this is fifteen periods of margin. |
| `save_pose_rate` | 0.5 | DEFAULT-KEPT **and not by choice** — 0.0 was wanted and does not work: nav2_amcl computes `1.0/save_pose_rate` with no guard and the CONFIGURE transition dies with *Input t_sec is too large or too small for tf2::Duration* (reproduced on the m5_ver1 rig, `agv/forklift/amcl.yaml`). `always_reset_initial_pose: true` is what makes the saved pose harmless. |

**`update_min_d` is also what makes a standing vehicle get no correction
at all**: `map` → `odom` is held and re-broadcast, and whatever the
odometry does during a dwell passes through to the absolute pose
unopposed. That is a property of this configuration and it is stated
rather than hidden.

---

## 5. The instrument: how an absolute score is taken here

An absolute pose on this stack is **three transforms deep**, and a figure
is wrong if any one of them is composed the wrong way round:

```
map → base_link  =  (map → odom)  ∘  (odom → base_link)
world pose       =  registration⁻¹ ( map → base_link )
```

| transform | where it comes from | rate |
|---|---|---|
| `map` → `odom` | AMCL, off `/tf`, **as a consumer of this stack would read it** | 15.15 Hz (measured; re-broadcast on every scan) |
| `odom` → `base_link` | F2's estimator, the same pose it publishes on `topics.odometry_filtered` | 50 Hz |
| world ← map | the **committed** registration, derived once in F3 Task 1 and frozen | once |

**Two of the three are near a half turn**, and at a half turn a rotation
is very nearly its own inverse — so applying one the wrong way round
leaves every magnitude EXACTLY right and puts the answer on the other
side of the map. That is `SpawnFrame`'s trap, one frame further out.
`tests/test_localization_core.py` runs every transform case at a **quarter
turn as well**, where the sign is visible, and
`evidence_core.py --selftest` carries the half-turn round trip and the
"is it a product or a sum" check for an operator on the rig.

**Nothing is anchored.** No initial offset is removed, no per-run
constant is fitted, the estimate is not brought onto the truth at its
first sample. That is global constraint 5, and it is the m5_ver1
lineage's own withdrawn figure: `WAREHOUSE_SLAM_EVIDENCE.md` §12.8 — an
error measured by anchoring at the first sample is zero at the anchor **by
construction**, and an estimator that is consistently 0.3 m wrong scores
near zero.

**The parent is interpolated, and that is what tf2 does rather than an
approximation of it.** A listener asking for a transform between two
stamped messages gets a linear interpolation of the two, so that is what
the composition does; the STEPS are counted separately, on the parent's
own samples, before any interpolation touches them (§8). A hole in the
parent wider than `localization.analyse.map_gap_s` (1.0 s, fifteen scan
periods) is a **refusal** and not a straight line drawn through the
stretch of the run where the absolute pose was unknown.

**And the score is taken in the WORLD frame**, so the printed `dx`/`dy`
are metres in the building. Every figure the scorer returns is a
distance, an angle, or a projection of one onto the other, so a rigid
transform applied to both sides changes none of them — the frame buys
readability, not a number.

### Two recorded streams, and only one of them is required

| stream | what it is | required before the run? |
|---|---|---|
| `map_odom.csv` | `map` → `odom` off `/tf`, matched on **both** frame names | **yes** — AMCL re-broadcasts it on every scan, so its absence means the localiser is not broadcasting |
| `amcl_pose.csv` | the filter's own pose and the three live covariance entries | **no** — AMCL publishes when the filter RESAMPLES, and a filter whose vehicle is standing at spawn never does |

`amcl_pose` is checked **after** the drive instead: a localised drive that
produced not one pose is a localiser that never corrected, and every
absolute figure from it would be the seed re-broadcast for the length of
the run — a session that looks perfect from every other angle, with the
edge on `/tf` at 15 Hz and every CSV full.

### The third label

`loc=amcl@735cdbc6` joins `traction=` and `arm=` on the state file, in
`status`, in every `session.txt`, and in a third mixed-set refusal.
Demonstrated on two real sessions that agree in traction and in arm:

```
sensor_evidence: REFUSED at check 'every session in this analyse is off the SAME absolute layer'
                 2 different absolute layers are in this set:
                   amcl@735cdbc6 - 1 session(s): drive-straight-20260826-230652
                   none          - 1 session(s): drive-straight-20260826-232555
```

The md5 half is not decoration: it is what refuses a set half-recorded
against a rebuilt grid, and what refuses to score any session through a
registration that no longer belongs to it.

---

## 6. THE DRY SET — the headline

Five sessions, `straight` × 3, `square`, `corner_creep`. Nominal plant,
`wheel+imu` arm, `--localize`, headless, the stack stopped and started
before every one, `drive_route.py` exited **0** on all five.

### 6.1 The absolute pose against the ground truth

**Read every figure against the floor: rms 0.0291 m, MAX 0.1179 m.**

| session | profile | **END error** | rms over run | worst | along-track | cross-track | END heading |
|---|---|---|---|---|---|---|---|
| `…230652` | `straight` | **0.0395 m** | 0.2436 m | 0.5321 m | −0.0210 | −0.0334 | +0.0020 rad |
| `…230809` | `straight` | **0.0387 m** | 0.2157 m | 0.4540 m | −0.0217 | −0.0320 | −0.0169 rad |
| `…230930` | `straight` | **0.1651 m** | 0.2204 m | 0.4569 m | −0.1639 | −0.0203 | −0.0148 rad |
| `…231047` | `square` | **0.1954 m** | 0.1359 m | 0.2070 m | +0.1652 | −0.1044 | −0.0251 rad |
| `…231218` | `corner_creep` | **0.0382 m** | 0.0846 m | 0.1915 m | −0.0169 | +0.0343 | −0.0315 rad |

**Three of the five END errors are below the instrument floor's MAX**, and
what that means is that the ruler and not the localiser is what those
three figures describe.

**The `rms over run` column is four to six times the `END error` column on
`straight`, and one and a half times it on the corners.** That is not
noise and it is not a bad end sample — it is a systematic offset present
only while the vehicle is moving, and §9 is the measurement of it.

### 6.2 THE DEBT — what the map bought, along-track

EVIDENCE_FUSION.md §5 and §8.5 handed F3 one number and named it
unreachable: the along-track error, which grows without bound because
both of the filter's inputs are *rates*, and which fusion moved by **1.5
percentage points across four runs** — nothing.

| session | profile | raw wheel odom | **F2's EKF** | **ABSOLUTE** | removed |
|---|---|---|---|---|---|
| `…230652` | `straight` | +0.4838 m | **+0.4890 m** | **−0.0210 m** | **95.7 %** |
| `…230809` | `straight` | +0.4805 m | **+0.4753 m** | **−0.0217 m** | **95.4 %** |
| `…230930` | `straight` | +0.4828 m | **+0.4764 m** | **−0.1639 m** | **65.6 %** |
| `…231047` | `square` | +0.6340 m | **+0.4908 m** | **+0.1652 m** | **66.3 %** |
| `…231218` | `corner_creep` | +0.1283 m | **+0.0475 m** | **−0.0169 m** | **64.5 %** |

**The debt is paid.** On the profile it was stated on — `straight`, the
one that separates distance from heading because it does not turn — the
map removes **95.7 %, 95.4 % and 65.6 %** of an error that F2 could not
touch at all. The two 95 % runs end **0.021 m** out along-track, which is
below the map's own residual rms.

**And the heading comes with it, on the runs that had one.** The one
figure F2 *could* reach was heading, by about a quarter on a good draw of
the gyro bias. The map takes every dry run to **0.0020 – 0.0315 rad**
(0.11° – 1.81°):

| session | raw | EKF | **ABSOLUTE** | removed |
|---|---|---|---|---|
| `…230652` `straight` | −0.0577 | −0.0158 | **+0.0020** | 87.2 % |
| `…230809` `straight` | −0.0575 | −0.0762 | **−0.0169** | 77.9 % |
| `…230930` `straight` | −0.0573 | −0.0785 | **−0.0148** | 81.2 % |
| `…231047` `square` | +0.6488 | +0.4788 | **−0.0251** | **94.8 %** |
| `…231218` `corner_creep` | +0.0156 | −0.0161 | **−0.0315** | **−96.2 %** |

**The `corner_creep` row is a percentage of nothing and is printed
rather than dropped.** That run's EKF drew a gyro bias that opposed the
wheel odometry's heading error and landed at **0.92°**; the map's answer
is **1.80°**. Read as a fraction that is a 96 % regression; read in
radians it is two figures a hair apart, both inside what this
configuration does on every other run, and neither of them a heading
error anything would notice. The profiles where the fraction means
something are the ones that HAVE a heading error to remove, and on
`square` — 0.6488 rad raw, 0.4788 after fusion — the map removes
**94.8 %** of it.

| session | profile | raw end error | EKF end error | **ABSOLUTE end error** |
|---|---|---|---|---|
| `…230652` | `straight` | 0.5807 | 0.4897 | **0.0395** |
| `…230809` | `straight` | 0.5767 | 0.6764 | **0.0387** |
| `…230930` | `straight` | 0.5774 | 0.6942 | **0.1651** |
| `…231047` | `square` | 0.6786 | 0.5452 | **0.1954** |
| `…231218` | `corner_creep` | 0.1941 | 0.1337 | **0.0382** |

*(The two `straight` runs where the EKF is WORSE than the raw estimate are
the gyro bias-draw lottery EVIDENCE_FUSION.md §3.4 measured, not a
regression: which way the heading goes is drawn per run.)*

### 6.3 The path error, and what an absolute pose does to it

| session | raw | EKF | **ABSOLUTE** |
|---|---|---|---|
| `…230652` `straight` | +4.22 % | +4.22 % | +6.06 % |
| `…230809` `straight` | +4.21 % | +4.21 % | +5.90 % |
| `…230930` `straight` | +4.24 % | +4.24 % | **+0.33 %** |
| `…231047` `square` | +10.47 % | +10.48 % | +9.36 % |
| `…231218` `corner_creep` | +7.64 % | +7.64 % | +8.59 % |

**The path-error row is the one to read carefully, and it is the honest
place to say what an absolute layer is not.** F2's own path error passes
from input to output unchanged to a hundredth of a percentage point, which
is what a filter over two rate sensors must do. AMCL's does not: it wanders
between +0.33 % and +9.36 %, because a *corrected* trajectory is the odometry
plus a train of discrete steps and the steps add length of their own. **Path
length is not a figure this arm improves and it is not one to read as an
accuracy** — the position error is. §8 is where the steps are measured
directly.

---

## 7. THE WET SET — recorded, not tuned

Three sessions on the slippery plant (`--slippery`, slip compliance
16.0/16.0), same everything else. **Not one parameter was moved for
them**, before or after (owner ruling, 2026-08-26): they are a stretch
measurement and what they found is recorded as it came.

| session | profile | **END error** | rms | worst | along-track | cross-track | END heading |
|---|---|---|---|---|---|---|---|
| `…231331` | `straight` | **0.1772 m** | 0.5657 m | 1.1076 m | +0.1762 | −0.0192 | +0.0024 rad |
| `…231453` | `straight` | **0.3067 m** | 0.5297 m | 1.2581 m | −0.3046 | −0.0360 | +0.0013 rad |
| `…231613` | `square` | **0.3067 m** | 0.2019 m | 0.3604 m | +0.2990 | −0.0682 | −0.0421 rad |

### THE HEADLINE THIS TASK WAS SET

| | |
|---|---|
| what F2 handed over (EVIDENCE_FUSION.md §8.5) | **+1.055 to +1.058 m of along-track error per 11.02 m driven, wet** — unbounded, and untouchable by any line of `ekf.yaml` |
| measured again here, on the same profile | EKF along-track **+1.0618 / +1.0617 m** |
| **against the map** | **+0.1762 m / −0.3046 m** |
| **paid** | **83.4 % / 71.3 %** |
| residual, against the instrument floor | **0.18 – 0.30 m** against a MAX of **0.1179 m** — 1.5× to 2.6× the floor, so it IS a measurement of the localiser |
| the wet `square`, for completeness | EKF **+1.0394 m** → **+0.2990 m**, **71.2 %** |

**The debt is mostly paid on the wet floor and it is not paid to the
floor.** The residual is a real localiser error, not an instrument
artefact, and the two `straight` runs disagree in *sign* (+0.18 and
−0.30), which says it is not a bias either — it is where the run happened
to be when the corrections stopped.

**The wet floor costs the dynamic offset dearly**, and that is §9's
subject: `rms over run` is 0.53 – 0.57 m on the wet `straight` against
0.22 – 0.24 m dry, and the ratio (2.5×) is the **odometry's** own error
ratio (9.63 % / 4.22 % = 2.28×) rather than any property of the localiser.

**Dry performance is proven; the wet residual is recorded for a future
challenge phase.** No ladder was run, no parameter was hunted, and §12
names what a task that wanted to move it would measure first.

---

## 8. What the correction COST — jump statistics

An absolute localiser pays its debt in **discontinuities**: a particle
filter's answer moves in steps and `map` → `odom` moves with it, so a
controller reading `map` → `base_link` sees the vehicle teleport. This is
the number the deferred question turns on — whether the absolute pose
needs a second filter smoothing it — and it is measured rather than
assumed either way.

**A repeat is not a correction.** AMCL re-sends the edge on every scan
whether or not the filter updated, so only a broadcast that *differs*
from the one before it is counted. Counting broadcasts would report a
correction rate of 15 Hz and a mean correction of zero, which is the
smoothest possible localiser and a complete fiction.

| session | plant | broadcasts | **corrections** | per second | mean step | median step | **WORST step** | worst heading step |
|---|---|---|---|---|---|---|---|---|
| `…230652` `straight` | dry | 613 | 43 | 1.06 | 0.0470 m | 0.0301 m | **0.2591 m** | 0.0079 rad |
| `…230809` `straight` | dry | 612 | 43 | 1.07 | 0.0495 m | 0.0320 m | **0.1737 m** | 0.0096 rad |
| `…230930` `straight` | dry | 633 | 43 | 1.03 | 0.0284 m | 0.0193 m | **0.1049 m** | 0.0120 rad |
| `…231047` `square` | dry | 782 | 44 | 0.85 | 0.0314 m | 0.0288 m | **0.0725 m** | 0.0585 rad |
| `…231218` `corner_creep` | dry | 483 | 17 | 0.53 | 0.0271 m | 0.0244 m | **0.0592 m** | 0.0182 rad |
| `…231331` `straight` | wet | 627 | 43 | 1.04 | 0.0449 m | 0.0302 m | **0.1237 m** | 0.0066 rad |
| `…231453` `straight` | wet | 630 | 43 | 1.04 | 0.0838 m | 0.0465 m | **0.4927 m** | 0.0056 rad |
| `…231613` `square` | wet | 792 | 44 | 0.84 | 0.0412 m | 0.0352 m | **0.1111 m** | 0.0764 rad |

**The reading, for whoever has to decide.**

- **Typical is small.** The median step is **19 – 47 mm** on every run,
  dry and wet: half of all corrections are under a map cell.
- **The tail is not.** The worst single step is **0.0592 – 0.2591 m dry**
  and **0.4927 m wet**. A half-metre jump is not something a path
  follower absorbs quietly.
- **The rate is about one a second** (0.53 – 1.07 Hz), because the filter
  updates on distance travelled and these profiles are slow.
- **The heading steps are largest on the profiles that turn** (0.058 and
  0.076 rad on the two `square`s against 0.006 – 0.012 rad on
  `straight`), which is the filter correcting the heading where the
  heading is what went wrong.

**What this does NOT settle**, stated because the temptation is to read it
as settled: this is the size of the steps, not their effect on a
controller. Nothing on this track consumes `map` → `base_link` yet.
Whether a 0.49 m step matters is a question about a following controller,
and that is F4's to answer with a controller in the loop.

---

## 9. The dynamic along-track offset — measured, and NOT tuned away

The `rms over run` column of §6.1 is four to six times the `END error`
column on `straight`. That is one finding and it deserves its own
section.

### 9.1 What it looks like

Every value below is the absolute pose against ground truth, at each of
the filter's own updates, on the dry `straight` `…230652`. `dx` is along
the direction of travel; `dy` is across it.

| truth x | dx | dy |
|---|---|---|
| −16.802 | **+0.109** | −0.066 |
| −15.705 | **+0.311** | −0.052 |
| −14.527 | **+0.417** | −0.046 |
| −13.208 | **+0.380** | −0.056 |
| −11.844 | **+0.371** | −0.036 |
| −10.471 | **+0.265** | −0.048 |
| −9.096 | **+0.301** | −0.049 |
| −7.720 | **+0.502** | −0.023 |
| −6.169 | **+0.090** | −0.036 |
| −5.576 (stopped) | **−0.016** | −0.033 |

and on the wet `straight` `…231331` the same shape, larger: `dx` rises to
**+0.965 m** at cruise and ends at **+0.210 m**.

**Cross-track is 0.02 – 0.08 m for the whole of every run.** The entire
offset is ALONG the direction of travel, it builds over the cruise, and
it collapses over the final metre and a half — which is the profile's
deceleration ramp, on all four `straight` runs.

### 9.2 It scales with the ODOMETRY's error, not with speed

| profile | plant | mean speed | rms over run | the odometry's own path error |
|---|---|---|---|---|
| `straight` | dry | 0.294 m/s | 0.216 – 0.244 m | +4.22 % |
| `straight` | **wet** | 0.273 m/s | **0.530 – 0.566 m** | **+9.63 %** |
| `square` | dry | 0.148 m/s | 0.136 m | +10.47 % |
| `square` | **wet** | 0.136 m/s | **0.202 m** | +19.13 % |
| `corner_creep` | dry | 0.129 m/s | 0.085 m | +7.64 % |

**The two `straight` rows are the decisive pair.** Same profile, same
speed to 8 %, and the offset is **2.4× larger on the wet floor**
(0.548 m against 0.230 m, run means) — while the odometry's own error is
**2.28× larger** (9.63 % against 4.22 %). A fixed time lag would have
given the same offset at the same speed; this does not. **The absolute
pose is being carried along by its own motion model in the direction the
scan cannot correct it.**

The filter says so itself. From `amcl_pose`'s covariance, at the end of
each run:

| session | `cov_xx` (along) | `cov_yy` (across) | ratio |
|---|---|---|---|
| `…230652` `straight` | 0.0568 → σ **0.24 m** | 0.000244 → σ **0.016 m** | **15×** |
| `…230809` `straight` | 0.0314 → σ 0.18 m | 0.000273 → σ 0.017 m | 11× |
| `…231331` `straight` **wet** | 0.0989 → σ **0.31 m** | 0.000437 → σ 0.021 m | 15× |
| `…231047` `square` | 0.0076 → σ 0.087 m | 0.0167 → σ 0.13 m | 0.7× |
| `…231218` `corner_creep` | 0.0429 → σ 0.21 m | 0.0047 → σ 0.069 m | 3× |

On `straight` the filter's own along-track 1σ is **eleven to fifteen
times** its cross-track 1σ, and the measured error splits the same way.
On the profiles that TURN, the anisotropy collapses — `square`'s is 0.7×
— because turning rotates the weakly-observed direction into a
well-observed one. **AMCL knows which direction it is unsure about, and it
is right.**

### 9.3 What it is, and what it is not

This is the m5_ver1 aisle lesson on a bigger floor. Driving down a
corridor, the surfaces that constrain the CROSS-track direction are the
racks and walls four metres either side; the ones that constrain
ALONG-track are tens of metres ahead and astern, seen at shallow
incidence, and are exactly the returns gz-sim issue #2743 makes least
accurate. The scan therefore pins the cross-track error at the
instrument's resolution and leaves the along-track error to be argued
between a weak observation and a motion model that is (correctly) told
the odometry is good to 10 % of distance.

**Two mechanisms are consistent with the measurement and this file does
not choose between them**:

- **(a) an equilibrium.** The odometry adds along-track error at
  `speed × path-error` (0.012 m/s dry, 0.026 m/s wet) and the filter pulls
  back at a rate limited by the observation's weight against the motion
  prior; the offset settles where the two balance, and collapses when the
  vehicle decelerates and the source stops.
- **(b) a feature.** The along-track information arrives at discrete
  landmarks and the last 1.5 m of this route happens to contain one.

The measurement that separates them is the same profile driven at two
speeds, or driven to a stop at a different place. **It was not run**, and
nothing was changed to make the number smaller.

### 9.4 What a later task would move first, and why it is not moved here

`alpha3` (0.010, a 1σ of 10 % of distance) is a *zero-mean* noise model
standing in for a *systematic* +4.2 %/+9.6 % over-reading. A zero-mean
prior can only remove a bias gradually. Raising `alpha3`, or lowering
`update_min_d`, would let the filter pull harder — and both would be
**tuned against this result**, which is the one thing `amcl.yaml`'s header
forbids. They are named here as the first two things a task that wanted
this number smaller should put on a ladder, with the cost each buys
(a wider particle cloud; more filter updates per metre and more CPU)
measured rather than assumed.

**And the figure that is NOT affected by any of this is the one §6 leads
with.** The END error is taken with the vehicle at rest, after the
corrections have closed the gap, and it is 0.038 – 0.195 m dry.

---

## 10. What the arm costs this rig

The instrument is EVIDENCE_FUSION.md §10.4's: `/proc/<pid>/stat` fields
14 and 15 (`utime` + `stime`), sampled either side of one `straight`
drive, 32.2 s of wall.

| process | % of one core |
|---|---|
| `amcl` (2000 particles × 271 beams at 15 Hz) | **5.00 %** |
| `map_server` (serving one latched grid) | **3.00 %** |
| `ekf_node`, for scale, on the same window | **12.00 %** |

| | |
|---|---|
| real-time factor with the arm up | mean **0.9984**, median 0.9999, floor 0.7987 (`tools/rtf_probe.sh`, 296 samples over 30 s) |
| AMCL message-filter drops during the drive | **0** |
| `map` → `odom` delivered rate | **15.15 Hz** — one per scan |
| `amcl_pose` delivered rate | **0.53 – 2.11 Hz** — one per filter update |

**The localiser is the cheapest thing on this stack that does real work.**
It costs less than half the estimator, the real-time factor cannot see
it, and the whole arm — three children — adds 8 % of one core.

---

## 11. The capture

Eight scored sessions plus one unlocalised control, all under
`m5_ver3/logs/evidence/` and all untracked. The stack was stopped and
restarted before every one, so each begins from the spawn pose;
`drive_route.py` exited **0** on all nine.

| session | profile | plant | loc | `amcl_pose` rows | `map_odom` rows | scan rows |
|---|---|---|---|---|---|---|
| `drive-straight-20260826-230652` | `straight` | nominal | `amcl@735cdbc6` | 43 | 613 | 613 |
| `drive-straight-20260826-230809` | `straight` | nominal | `amcl@735cdbc6` | 43 | 612 | 638 |
| `drive-straight-20260826-230930` | `straight` | nominal | `amcl@735cdbc6` | 43 | 633 | 631 |
| `drive-square-20260826-231047` | `square` | nominal | `amcl@735cdbc6` | 44 | 782 | 782 |
| `drive-corner_creep-20260826-231218` | `corner_creep` | nominal | `amcl@735cdbc6` | 17 | 483 | 499 |
| `drive-straight-20260826-231331` | `straight` | **slippery** | `amcl@735cdbc6` | 43 | 627 | 627 |
| `drive-straight-20260826-231453` | `straight` | **slippery** | `amcl@735cdbc6` | 43 | 630 | 658 |
| `drive-square-20260826-231613` | `square` | **slippery** | `amcl@735cdbc6` | 44 | 792 | 792 |
| `drive-straight-20260826-232555` | `straight` | nominal | **`none`** | — | — | 611 |

The last row is the control that makes §5's third refusal a demonstration
rather than a unit test, and it is also the check that the recorder
subscribes nothing on the default arm: ten streams, and neither
localisation CSV in the directory.

Every figure here is re-derivable with **no ROS and no Gazebo**:

```
python3 m5_ver3/tools/sensor_evidence.py analyse m5_ver3/logs/evidence/drive-straight-20260826-230652
python3 m5_ver3/tools/map_register.py support   m5_ver3/logs/evidence/drive-mapping-20260826-174815
```

### The suite

| | before | after |
|---|---|---|
| `pytest m5_ver3/tests` | 321 | **385** |
| `tools/evidence_core.py --selftest` | 30 | **35** |
| `tools/map_core.py --selftest` | 6 | **8** (and the count is now counted rather than typed) |
| `nodes/wheel_odom_core.py --selftest` | 12 | 12 |
| `nodes/rf2o_twist_core.py --selftest` | 24 | 24 |

The 64 new tests are `tests/test_localization_core.py` (**46**: the map
frame, the composition, the world-frame score, the jump statistics, the
two gate checks and the map's support of a scan) and
`tests/test_sensor_evidence_loc.py` (**18**: the third label, its grammar
and its refusal).

### The refusals this task added, and how each was exercised

| refusal | exercised |
|---|---|
| `--localize` without the frozen map, or with a grid whose md5 has moved | the md5 comparison is a two-line `sed`/`md5sum` in `check_frozen_map()`; the PASSING direction ran on every localised bringup in this file |
| `amcl.yaml` not addressed to both node names | `check_amcl_params()`, both names, before anything starts |
| a lifecycle transition that did not succeed | `localize_lifecycle()`, per node per transition, on every localised bringup |
| a localiser that came up merely alive | §3.2, both directions, exit 1 verified |
| a drive on the localised arm that produced no `amcl_pose` | post-drive check in `record()` |
| a session scored through a registration that no longer belongs to it | `analyse`, on the session's own `loc=` md5 |
| a set mixing localised and unlocalised sessions | §5, on two real sessions |
| a gap in `map` → `odom` wider than 1.0 s | `compose_rows()`, tested |

---

## 12. What this is not

Stated rather than left to be discovered.

**It cannot find itself.** No kidnapped-robot recovery, no global
localisation. Both recovery alphas are zero, `set_initial_pose` is false,
and the bringup hands the filter its answer. §2 carries the argument
(a rack pitch of 5.75 m makes a recovered pose one bay along
indistinguishable from the truth) but the honest summary is shorter: this
arm **tracks**, and every figure here is a tracking figure.

**The along-track error while moving is a real limitation and it is not
tuned.** §9. The END errors this file leads with are taken at rest.

**The wet residual is recorded and not chased.** §7. 0.18 – 0.30 m of
along-track error survives on the slippery plant, against a floor of
0.118 m, and no parameter was moved to reduce it.

**Path length is not improved and is not an accuracy.** §6.3. A corrected
trajectory is the odometry plus a train of steps, and the steps add
length; the position error is the figure, the path error is not.

**One map, one day, one rig — and one batch, run in order.** Eight scored
sessions on 2026-08-26, all against `warehouse_v3` md5 `735cdbc6…`, all on
the default estimator arm. **They were driven sequentially and NOT
interleaved: the five dry runs first, then the three slippery ones**, each
with the stack stopped and restarted. F2's divergence protocol (F3 global
constraint 17) allows a bringup-failure, divergence-rate or
convergence-rate claim only from an interleaved batch, and **no such claim
is made anywhere in this file** — nothing here counts bringups, failures
or time-to-converge. What the shape does bear on is every dry-against-wet
comparison: §7's debt percentages and §9.2's "decisive pair" are two
groups of runs taken minutes apart rather than alternately, so anything
that drifted over those twenty minutes sits inside them. Nothing here says
what AMCL does on the `--rf2o` or `--fuse` arms, and nothing here is a
second opinion about the map.

**The jump statistics are sizes, not consequences.** §8. Nothing consumes
`map` → `base_link` yet, so whether a 0.49 m step matters is a question
about a controller and F4 is where it gets answered.

**The two mechanisms behind §9 were not separated.** The experiment that
would separate them — the same profile at two speeds, or stopped in a
different place — was not run.

**The sensor model was derived from ONE recording of each kind.** §4.2's
`sigma_hit` and `z_rand` come from the whole mapping drive and one
`straight`; a third floor or a second lidar would need the measurement
repeated, not the numbers carried across.

**And the localiser has not been compared with anything.** F3 Task 3 puts
`slam_toolbox`'s localization mode over the same frozen pose graph and
runs the same sets through the same instrument. What is here is one arm,
measured; which one *ships* is that task's to argue.
