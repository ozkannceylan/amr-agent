# m5-ver3 — what this build is

The **sensor-fusion showcase vehicle**. One forklift, real instrument
profiles, an estimate that is scored against ground truth rather than
handed it. Owner decision **AMR-DEC-003** (vault, 2026-08-25); branch
`m5-ver3`; phase ledger `tasks/TODO.md` § *m5-ver3*; the research it is
built on is `docs/reports/m5v3-01..04.md` (SLAM/localisation SOTA, Nav2
for a tricycle, simulation realism and cameras, fusion architecture).

It is **not** a fleet. M6 is the fleet and stays the fleet: four trucks,
VDA 5050, a manager, a floor, a PLC. This track takes M6's plant back
down to ONE truck so that everything the vehicle *perceives* can be made
honest — and whether any of it ever rejoins the fleet is a separate
decision, not an assumption in this tree.

---

## What it inherits, and how

| Thing | Where it comes from | How |
|---|---|---|
| The floor | `m6/gazebo/warehouse_ver3.sdf` | **By reference.** Never copied, never edited. |
| The vehicle | `m6/gazebo/forklift_ver2/model.sdf` | **Forked** into `gazebo/forklift_ver3/model.sdf` — byte-identical but for the model name and a provenance header. |
| The spawn pose | `m6/ipc/status_contract.py` `VEHICLES["f1"]` | Copied into `config.yaml` as a value, with the floor check that validates it (see below). |

**Why the floor is referenced and the vehicle is forked.** Two files that
start identical and then drift are two files, and a figure measured on
one of them is a claim about neither. The floor will not drift — this
track has no reason to move a rack — so it is read where it lives. The
vehicle *will* drift, and hard: phase F1 replaces its ideal sensors with
instrument profiles and takes the ground-truth odometry away. m6's
published figures are measured on `forklift_ver2`, so that file is not
this track's to touch.

**The vehicle has drifted, and F1.5 is where the plant itself moved.**
Phase F1 replaced the ideal sensors and kept the ground truth beside the
new estimate; phase **F1.5** (owner-approved 2026-08-26) then changed the
*physics*: the two rear wheels carry `gz-sim-wheel-slip-system` now, so
the truck delivers 1.005 of its kinematic yaw at creep where it delivered
0.410. Any figure on this track taken before 2026-08-26 that involves a
**corner** is a figure about a different plant, and the three evidence
files say so where it happens. `EVIDENCE_LATERAL_TUNE.md` is the record.

**Nothing outside `m5_ver3/` is modified by this track.** Not `m6/`, not
`m5_ver2/`, not `m5/`, `agv/`, `sim/`, `plc/`, `hmi/`, `fleet/`,
`bridge/` or `docs/adr/`. Reading them is expected; writing to them is
not.

---

## The two rules the scripts enforce

### 1. Isolation — this stack cannot join, or be joined by, another

| | m5-ver3 | m6 | step5 |
|---|---|---|---|
| `GZ_PARTITION` | **`m5v3`** | `m6` | `m5demo` |
| `ROS_DOMAIN_ID` | **`97`** | `96` | — |

Both are set on every child. `GZ_PARTITION` is the one that scopes
**Gazebo** — gz transport is not DDS, so `ROS_DOMAIN_ID` isolates only the
ROS side — and it is also what decides **what `stop` may kill**:
`m5v3.sh`'s `ours()` reads a candidate process's own environment and the
sweep skips anything that does not carry `GZ_PARTITION=m5v3`. Measured
(EVIDENCE_BRINGUP.md 6): a gz server running in partition `m6` is
nominated by the same command-line pattern and survives an `m5v3.sh stop`
untouched.

Neither value is overridable from the environment. They live in
`config.yaml` and are read by `start`, `stop` and `status` alike, so the
three cannot disagree about which graph this is.

### 2. The GPU is mandatory, and the refusal is the point

Every launch exports

```
GALLIUM_DRIVER=d3d12
MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

and then **refuses to start anything at all** unless `glxinfo -B` reports
a renderer naming NVIDIA. Measured on this rig: without the exports the
renderer is `llvmpipe (LLVM 20.1.2, 256 bits)`; with them it is
`D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`.

There is no CPU fallback and there must never be one. Software
rasterisation does not fail — it measures a *different machine*, and
every figure taken under it wears this rig's name while describing
something else. A render problem is diagnosed, never downgraded.

---

## The tree

```
m5_ver3/
├── CONTEXT.md            this file
├── EVIDENCE_BRINGUP.md   Task 1's measured numbers, instrument by instrument
├── EVIDENCE_MODEL_V3.md  F1 Task 2's: every sensor, datasheet to delivered
├── EVIDENCE_SENSORS.md   F1 Task 4's: what the plant DELIVERS, and what the
│                         wheel odometry is worth against ground truth
├── EVIDENCE_LATERAL_TUNE.md  F1.5's: where the corner's yaw was being lost,
│                         the WheelSlip ladder that fixed it, and the
│                         before/after of everything the fix could break
├── EVIDENCE_FUSION.md     F2 Task 1's: the EKF against the raw wheel
│                         odometry against the truth, profile by profile.
│                         F2 Task 2 adds §8: the same three streams on a
│                         floor the truck cannot grip, and the filter's
│                         own startup divergence, measured. §9 is the
│                         `ax` reversal and the bringup gate it left
│                         behind; §10 is the OPTIONAL laser-odometry arm
│                         and whether it pays for its CPU. F2 Task 4 adds
│                         §11: a SECOND ESTIMATOR - fuse's factor graph -
│                         on the same inputs, and the A/B that decided
│                         which one ships
├── config.yaml           every constant the scripts obey - the one home
├── ekf.yaml              what the FILTER fuses and what it refuses. A ROS
│                         parameter file, which config.yaml is not and may
│                         not become - the split is argued in both files
├── ekf_rf2o.yaml         the OPTIONAL arm's overlay and NOTHING else. A
│                         SECOND --params-file, passed only by --rf2o, so
│                         the default stack reads one unchanged file
├── fuse.yaml             what the FACTOR GRAPH fuses and what it refuses,
│                         and it is ekf.yaml's split applied to the second
│                         estimator. Read only by --fuse; on that arm
│                         ekf.yaml is not read at all
├── m5v3.sh               start [--headless] [--slippery] [--rf2o|--fuse]
│                         | stop | status
├── gazebo/
│   └── forklift_ver3/
│       └── model.sdf     the forked vehicle
├── logs/                 one file per child, by name (git-ignored)
│   └── evidence/         one directory per recorded session, CSVs (untracked)
├── nodes/
│   ├── wheel_odom_core.py   the estimate, as arithmetic. --selftest
│   ├── wheel_odometry.py    the rclpy shell around it. Wiring only.
│   ├── rf2o_twist_core.py   what the laser odometry's output has to have
│   │                        done to it before a filter may read it, as
│   │                        arithmetic. --selftest
│   └── rf2o_twist.py        the rclpy shell around it. Wiring only.
├── tests/                pytest, no ROS anywhere - runs on the Windows python
└── tools/
    ├── _common.sh        sourced: refuse(), the config reader, source_ros()
    ├── install_rf2o.sh   rf2o_laser_odometry from source, at a PINNED
    │                     commit, into the user's own $HOME, without sudo
    ├── install_fuse.sh   the nine `fuse` debs, at PINNED versions, into
    │                     a prefix under $HOME, without sudo. apt-get
    │                     download + dpkg-deb -x, never apt-get install
    ├── _common.py        imported: the same three things for python
    ├── rtf_probe.sh      real-time factor of the RUNNING world
    ├── noise_probe.sh    is the configured sensor noise on the wire
    ├── slip_bench.sh     slip at steady cruise, forward and astern
    ├── ekf_health.py     did the FILTER come up, or come up broken? One
    │                     bounded read at bringup; m5v3.sh refuses on it
    ├── drive_route.py    drive one of config.yaml's profiles, open loop
    ├── evidence_core.py  the arithmetic behind EVIDENCE_SENSORS.md
    └── sensor_evidence.py  record (needs ROS) | analyse (needs nothing)
```

**`config.yaml` is the one home for every constant.** No behavioural
number is written inline in a script on this track. A partition, a pose,
a topic or a timing budget that has to move moves there, once, and both
scripts move with it.
  **`ekf.yaml` is the one file beside it, and the split is by OWNERSHIP
  rather than by convenience.** `robot_localization`'s `ekf_node` reads a
  ROS *parameter* file — a top-level node name, a `ros__parameters:`
  mapping, fifteen-entry boolean arrays — and `config.yaml` is not one
  and is not bent into one. So `config.yaml` keeps the topics, the
  frames, the output rate and the path to the other file, `m5v3.sh`
  passes all of those on the filter's command line, and `ekf.yaml` holds
  what is FUSED and what is REFUSED and nothing else. **No number is in
  both**, and each file's header says which one owns what.

**`m5v3.sh` orchestrates processes and holds no logic of its own.** Every
child writes its own log under `logs/`, named for the child, and `status`
reports the same children back by name with ALIVE or DEAD. Every refusal
names the check that failed and the file that owns the answer it tested
against — including a child that died on its way up, which is a refusal
with a non-zero exit and not a warning printed above the word "up."

**`tools/_common.sh` is sourced, never executed.** It is the three things
both scripts do before they can do anything of their own: `refuse()` in
one voice, one reader of `config.yaml` that checks required keys by their
dotted names, and `source_ros()`. Two copies of a mechanism drift exactly
the way two copies of a value do.

---

## Running it

The rig is **WSL Ubuntu 24.04**, ROS 2 Jazzy at `/opt/ros/jazzy`,
gz-sim 8.11.0. The repository is visible inside WSL at
`/mnt/c/Users/ozkan/projects/amr-agent`. From Windows:

```bash
wsl -e bash -lc 'cd /mnt/c/Users/ozkan/projects/amr-agent && ./m5_ver3/m5v3.sh start'
```

| Command | What it does |
|---|---|
| `m5v3.sh start` | GPU preflight, then the world, one `forklift_ver3`, both bridges, the wheel-odometry node, the static IMU transform, the EKF and a Gazebo **window**. |
| `m5v3.sh start --headless` | The same without the window. **Use this for anything being measured** — every figure in the three evidence files was taken this way. |
| `m5v3.sh start --slippery` | **A different plant from the same model file.** After the truck is spawned, every wheel's slip compliance is overridden through gz-sim's own `wheel_slip` service to `config.yaml`'s `slippery:` values — `model.sdf` is not edited and no variant of it is generated. Longitudinal slip at cruise goes from 0.95 % to 6.18 %. Combines with `--headless`, in either order. |
| `m5v3.sh start --rf2o` | **A DIFFERENT ESTIMATOR ON THE SAME PLANT**, which is `--slippery`'s mirror image. Three more children — the nav lidar's static transform, `rf2o_laser_odometry_node` matching consecutive scans, and the relay that puts a MEASURED covariance on its twist and corrects two frame errors upstream does not — plus a second `--params-file` giving the filter an `odom1` it fuses `vx` and `vyaw` from. Default OFF, and without it the stack is the six children `EVIDENCE_FUSION.md` §9.3 measured, off one unchanged parameter file. Build the package first with `tools/install_rf2o.sh`. Combines with the other two flags, in any order. |
| `m5v3.sh start --fuse` | **A DIFFERENT ESTIMATOR, IN THE FILTER'S PLACE.** `fuse`'s `fixed_lag_smoother_node` goes up and the `ekf` child does **not** — six children either way, with `fuse` where `ekf` was. It fuses the SAME channels off the SAME two topics (wheel twist `vx`, `vy`, `vyaw` + gyro yaw rate) and publishes its own `odom` → `base_link`, on `topics.fuse_odometry_filtered` and never on the shipping address. Where `--rf2o` adds a sensor, this replaces the estimator, so the two are **mutually exclusive and refused together by name**. Vendor it first with `tools/install_fuse.sh`. Default OFF, and `EVIDENCE_FUSION.md` §11 is the A/B that says why. Combines with `--headless` and `--slippery`. |
| `m5v3.sh status` | Each child by name, ALIVE or DEAD, with its log, **which traction the running plant is on** and **which estimator arm is up**. Exit 0 only if every one is alive. |
| `m5v3.sh stop` | Ends this partition's stack, and nothing else. |
| `tools/rtf_probe.sh` | 30 s real-time-factor sample of the world that is already running. |
| `tools/noise_probe.sh scan\|depth <topic>` | Temporal spread of every reading on one sensor topic, vehicle **at rest**. Is the noise the SDF configures actually on the wire? |
| `tools/slip_bench.sh` | Drives the traction terminal at cruise, forward then astern, and reports slip against the commanded and the achieved wheel rate. |
| `tools/install_rf2o.sh` | Builds `rf2o_laser_odometry` from source, at `config.yaml`'s **pinned commit**, into a colcon workspace under `$HOME`. No sudo at any point, idempotent, refuses by name, and writes a manifest of what it fetched beside the build. Run once; `start --rf2o` refuses by name if it has not been. |
| `tools/install_fuse.sh` | Fetches the nine `fuse` packages at `config.yaml`'s **pinned versions** and unpacks them into a prefix under `$HOME`. `apt-get download` + `dpkg-deb -x`, never `apt-get install`: the packages are in the Jazzy archive and this rig has no sudo. Idempotent through a probe that loads a `fuse_models` plugin, refuses by name, `ldd`-checks what it unpacked, and writes a manifest beside the tree. Run once; `start --fuse` refuses by name if it has not been. |
| `tools/ekf_health.py` | One bounded read of **the ACTIVE arm's** output, and a refusal if its covariance is over `ekf.startup_check.covariance_max`. It reads the `arm=` line `start` has already written and picks the topic from it (`evidence_core.fused_topic_key`), so one gate covers both estimators. **`start` runs it for you** — it exists because `ekf_node` can diverge during its first cycles and stay ALIVE, at rate, saying nothing (`EVIDENCE_FUSION.md` §8.6, §9). On the `--fuse` arm the first messages carry a covariance of 36 zeros, which no ceiling can fail, so there it gates on the **pose** against `evidence.analyse.fused_sanity_m` instead and prints which check it ran (§11.2c). |
| `tools/drive_route.py <profile>` | Drives one of `config.yaml`'s profiles — `straight`, `square`, `aisle`, `corner_creep` — open loop, on the plant's own clock. It drives; it records nothing. |
| `tools/sensor_evidence.py record --static\|--drive P` | Captures one run into `logs/evidence/<session>/`: one headered CSV per stream. `--drive` starts `drive_route.py` itself, so one command is one complete run. It stamps the session with **which plant it was taken on** and refuses if the stack cannot say, and it refuses **before the drive** if the filter has already diverged. Needs ROS. |
| `tools/sensor_evidence.py analyse [session…]` | Every table in `EVIDENCE_SENSORS.md` and `EVIDENCE_FUSION.md`, from those CSVs — including the EKF scored against the same truth as the raw estimate, and the two subtracted. **Needs no ROS and no Gazebo** — it runs on the Windows python. |

`start` exits **non-zero** if any child died during startup, naming the
child and its log; what survived is left running, because the operator's
next command is `stop`.

**Since F2 Task 2 there are TWO PLANTS and one model file, and every
measured thing has to say which it was taken on.** `--slippery` changes
the *physics* after the spawn — gz-sim 8.11's UserCommands system
advertises `/world/<world>/wheel_slip/blocking`, and `m5v3.sh` calls it
once per wheel with `config.yaml`'s `slippery:` values, checking the
reply for each. `gazebo/forklift_ver3/model.sdf` is **byte-identical**
between the two runs; the difference is three service calls, and the
committed model stays the one plant anybody reading it sees. F2's
constraint 12 allows a generated model variant if the runtime override
provably cannot be made to work — it can, and `EVIDENCE_FUSION.md` §8.1
is the measurement, including the control that shows a 7.0 override
reproducing the model's own 0.95 % slip to 0.0014 percentage points.
  **The label is a mechanism and not a convention.** `start` writes
  `paths.traction_file` on every bringup, nominal ones included; `stop`
  deletes it; `status` prints it; `sensor_evidence.py record` copies it
  into every session and **refuses to record without it**; and `analyse`
  **refuses a set of sessions that mixes the two plants**, naming both
  groups. A slippery run that reached the no-slip tables unlabelled
  would not look like a failure — it would look like a row — and that is
  the whole reason the chain exists.

**And since F2 Task 3 there are TWO ESTIMATORS as well, labelled by the
same chain and for the same reason.** `--rf2o` is `--slippery`'s mirror
image: it changes the ESTIMATE where that changes the PLANT, and the
failure it could cause is identical — a run of one arm sitting in the
other's table, on the same floor, from the same model file, driving the
same profiles, publishing on the same fused topic, writing CSVs of the
same shape into a directory of the same name. So `start` writes `arm=` to
the same state file on every bringup, `status` prints it, `record` copies
it into every session and refuses without it, and `analyse` refuses a set
of sessions that mixes the two arms. **The two labels are independent
questions and there are two refusals**: a set can be all-nominal and
still be half `wheel+imu` and half `wheel+imu+rf2o`, which is the mix
`EVIDENCE_FUSION.md` §10's whole A/B would be destroyed by.

**And since F2 Task 4 there are THREE arms on that one label, because
the third one changes the ESTIMATOR rather than its inputs.** `--fuse`
replaces `robot_localization`'s `ekf_node` with `fuse`'s fixed-lag
smoother — a factor graph over a 0.5 s window, re-solved with Ceres 20
times a second — fusing exactly the same channels off exactly the same
two topics. The `ekf` child is **not spawned**, because both publish
`odom` → `base_link` and tf2 has no notion of two authorities for one
edge; `--rf2o` and `--fuse` are therefore **mutually exclusive and
refused together by name**, before anything is read.
  **Its label puts the estimator in front of a colon — `fuse:wheel+imu`
  — and that is a grammar rather than a spelling.** The two older labels
  name a SENSOR SET on an estimator that was never in question; this one
  holds the sensor set and varies the estimator, so `fuse:wheel+imu`
  beside `wheel+imu` reads as the A/B it is. `tools/evidence_core.py`'s
  `fused_topic_key()` parses that grammar to decide **which topic** an
  instrument should read, because the two arms publish their fused
  estimate at different addresses — and it **refuses** an estimator it
  has never heard of rather than defaulting to the shipping filter's
  address, where the symptom would be an empty stream and not an error.

**Six children by default, NINE with `--rf2o`, and six again with
`--fuse`** — that flag swaps a child rather than adding one, so the
count is unchanged and `fuse` stands where `ekf` did. `status` names
them all back: the
gz server (`world`), `ros_gz_bridge`'s `parameter_bridge` (`bridge`),
`ros_gz_image`'s `image_bridge` (`imgbridge`), `nodes/wheel_odometry.py`
(`odom`), the static `base_link` → `imu_link` transform (`imutf`) and
`robot_localization`'s `ekf_node` (`ekf`) — plus the gated GUI client
(`gui`) when there is a window, which is the seventh process `m5v3.sh`'s
own usage text counts. With `--rf2o` there are three more, and they go up
BEFORE the bridges rather than after: the static `base_link` →
`nav_lidar_link` transform (`lasertf`), `rf2o_laser_odometry_node`
(`rf2o`) and `nodes/rf2o_twist.py` (`rf2ocov`). **The ordering is
measured and not tidy** — rf2o looks up the scanner's mount exactly once,
on its first scan, and carries on with a garbage transform if the lookup
fails, so it is started while there is no scan publisher at all and the
latched transform has ten seconds of real work to arrive in
(`EVIDENCE_FUSION.md` §10.1). **No broker, no fleet manager, no HMI, no
PLC link** — that absence is the phase, not an omission. Nothing here
touches PLCSIM Advanced or anything on the Windows side.

**The two newest children are one filter and the geometry it cannot work
without.** `ekf` fuses the wheel odometry's TWIST (`vx`, `vy` and yaw
rate, never its pose — the node publishes a covariance of 1000 there as
a do-not-fuse flag) with the IMU's yaw rate, and
publishes `/m5v3/odometry/filtered` plus **the first transform this stack
has ever emitted, `odom` → `base_link`**. F3's `map` → `odom` stacks on
top of it, and nothing in F2 may become that edge's owner — so the
filter's `world_frame` IS the odom frame and it publishes exactly one
transform. `imutf` publishes where the IMU is bolted, and it is a child
of its own rather than a line in the filter's configuration because it is
a different claim: `robot_state_publisher` would own it if this track
carried a URDF. Without it `robot_localization` **drops the entire IMU
and logs nothing at all** — measured on this rig, `EVIDENCE_FUSION.md`
§2.2.

### What is bridged, and one word about odometry

| Topic | Direction | Configured rate | Carried by |
|---|---|---|---|
| `/clock` | gz → ROS | 500 Hz | parameter bridge |
| `/forklift/gz/odom` | gz → ROS | 20 Hz | parameter bridge |
| `/forklift/gz/scan_nav` | gz → ROS | 15 Hz | parameter bridge |
| `/forklift/gz/imu` | gz → ROS | 100 Hz | parameter bridge |
| `/forklift/gz/cam/camera_info` | gz → ROS | 15 Hz | parameter bridge |
| `/forklift/gz/joint_state` | gz → ROS | 500 Hz | parameter bridge |
| `/forklift/gz/drive_speed/read_a` | gz → ROS | 500 Hz | parameter bridge |
| `/forklift/gz/cam/depth_image` | gz → ROS | 15 Hz | **image bridge** |

The two **joint** channels arrived with F1 Task 3 and are the estimator's
two inputs. They are `JointStatePublisher` systems and not sensors, so
their rate is the world's own physics step — one message per iteration —
and `EVIDENCE_SENSORS.md` §1.2 measures both delivering 500.0000 Hz of
sim time with `dt_max = dt_med`, not one message lost over 60 s.

**What is deliberately NOT bridged:** `/forklift/gz/points3d` (the 3D
lidar), both point clouds, the camera's colour image, and
`/forklift/gz/drive_speed/read_b`. The first four still have no ROS
consumer — F2 Task 1's EKF fuses the IMU and the wheel odometry and
nothing that renders — gz renders a sensor only while something
subscribes to it, and
`EVIDENCE_MODEL_V3.md` §6 measures what subscribing to the 3D lidar
costs: mean RTF 0.999 → 0.85. `read_b` is different — it is the same
shaft read a second time, and cross-comparing the two heads is the PLC's
function and lives in m6 (`config.yaml`, `topics.drive_speed_read_a`).
The delivered rates for every one of these, both sides, are §2 of the
same file.

`/forklift/gz/odom` is the model's `OdometryPublisher` — **ground truth,
and a measurement reference ONLY**. No wheel slip, no encoder
quantisation, no drift. On this track it is an *instrument*, never an
input. **F1 kept it**, and keeping it was the point: F1 added the wheel
odometry *beside* it and scored one against the other (`EVIDENCE_SENSORS.md`
§3), which is not a thing a phase can do having deleted its own reference.
**F2 Task 1 built the fused estimate that replaces it as the thing
anything would navigate on** — `/m5v3/odometry/filtered`, scored against
this same reference in `EVIDENCE_FUSION.md` — and the ground truth stays
bridged, still an instrument, still never an input to any estimator (F2
global constraint 13). The EKF's own configuration carries no `odomN` or
`poseN` entry naming it and there is exactly one of each in that file, so
there is nowhere for a third to hide. The bridge line in `m5v3.sh` says
so where it is opened.

---

## Five things worth knowing before the next phase

**The EKF fuses THREE twist components, and the third one was ruled out
and then ruled back in on a measurement.** `ekf.yaml` fuses the wheel
odometry's `vx`, **`vy`** and `vyaw`. `vy` is not a noise channel on this
vehicle — it is `d · yaw_rate` with `d = 0.50 m`, the lateral velocity
`base_link` genuinely has because it stands half a metre forward of the
rear axle, and `robot_localization`'s motion model does not know `d`, so
that channel is the only way the filter learns about it at all. The first
cut of `ekf.yaml` refused it on a rationale that was wrong ("the measured
`vy` is quantiser noise"); the cost was predicted from the kinematics,
then measured on the same profiles with the same instrument — **+0.90 m
of end error on `corner_creep`'s 163° turn and a doubled rms on
`square`** — and the ruling was reversed on that measurement.
`EVIDENCE_FUSION.md` §4 keeps the whole before/after, because a wrong
turn that has been measured is worth more than one that has been tidied
away. **It is still twist-only**: the six pose flags are false and the
node's own covariance of 1000 still says do-not-fuse. F2 global
constraint 13 governs the POSE and never excluded a velocity component.

**A third estimator exists, it is OFF, and the reason it is off is in the
numbers rather than in the cost.** `--rf2o` matches consecutive nav-lidar
scans and is the first thing on this track that observes the FLOOR —
which is why it is also the first thing that has ever moved the
**path-error row**, the one §8.5 handed to F3 as unreachable: **+9.63 %
→ +5.63 %** on the slippery `straight`, against the two-sensor filter's
+9.63 % → +9.63 %. It costs **11.6 % of one core** and the real-time
factor cannot see it. It ships **off** anyway, for three reasons in
`EVIDENCE_FUSION.md` §10.6: its own forward speed is 9.5–17.4 % low and
the dry `straight` headline is partly two opposite biases cancelling at a
weight nobody chose; it makes `corner_creep` — a slow sustained corner,
which is what a forklift does — measurably worse; and it is eight
sessions old against a baseline that is a phase old. **Its yaw rate is
the most accurate channel on this vehicle** (under 1.2 % of integrated
turn) and this filter weights it 31× below the gyro, which is the first
thing a later task should change.

**A SECOND ESTIMATOR exists too, it is also OFF, and what it measured is
an architecture answer rather than a number.** `--fuse` runs `fuse`'s
fixed-lag smoother — a factor graph over a 0.5 s window, re-solved with
Ceres 20 times a second — **instead of** `ekf_node`, on exactly the same
channels off exactly the same two topics. On every accuracy figure that
repeats it is **the same estimator**: on the one `square` the plant
handed both arms the same corner it removed **15.56 %** of the end error
against the filter's **15.55 %**, and 17.14 % of the heading against
17.25 %. It costs **36.5 % of one core against 10.4 %**, its honest
output latency is **37.5 ms against 1.46 ms** (one optimisation period —
and `predict_to_current_time` hides that behind a motion-model
extrapolation that puts **28 mm of jitter into a straight line and half
a metre into a square**), and the first messages it publishes carry a
covariance of 36 zeros, which cost the bringup gate a second instrument.
`EVIDENCE_FUSION.md` §11 is the whole A/B and §11.6 is the
recommendation: **`robot_localization` stays the default.** The reason
is not the CPU — it is that a factor graph's advantage is constraints an
EKF cannot represent (out-of-order measurements, loop closures,
landmarks seen twice) and **two in-order twist sensors give it none of
them**. The place to try it again is F3's `map` → `odom`, which is that
problem; this stack is not.

**A spawn pose has to be checked against the floor, not against the map.**
Task 1 was handed the pose `(-3.00, -5.50)` and measured it spawning the
truck's forks 0.875 m inside a rack leg: that pose belongs to
`warehouse_ver2`, and M6.6's relayout put `RackSW3` across it. The model's
forks reach `x = -1.875` in its own frame, and *that* number — not the
look of the floor plan — is what a candidate pose has to clear.
`EVIDENCE_BRINGUP.md` 7 carries the whole measurement.

**DDS discovery on this rig has failed before.** Mid-session on
2026-08-25 the WSL multicast path died and FastDDS discovery went with it;
m6 works around it with a unicast profile at `m6/tools/fastdds_loopback.xml`
(exported as `FASTRTPS_DEFAULT_PROFILES_FILE`). This track does **not**
carry one — a bare `ros2 topic pub` / `echo` pair was verified working on
domain 97 before Task 1's measurements, and three participants is a long
way from the ~40 that made m6's default initial-peer range too small. If
bridged topics start going missing at boot, that file is the first thing
to try, not a mystery.
