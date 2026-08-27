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

**And since F3 there is a THIRD graph, which is not a stack at all.**
`tools/build_map.sh` replays a recorded bag into `slam_toolbox`, and that
bag carries `/tf` — the EKF's `odom → base_link`. Replayed onto domain 97
it would be a **second publisher of an edge that has exactly one owner**,
and tf2 does not refuse that: it carries whichever message arrived last.
So the offline replay lives on `isolation.map_ros_domain_id` (**98**),
with no `GZ_PARTITION` at all because there is no simulator in it, and
`build_map.sh` refuses if the two domain numbers are ever made equal. The
live stack can be up or down; the replay cannot reach it either way.

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
├── EVIDENCE_MAP_V3.md    F3 Task 1's: the commissioning drive, the
│                         offline SLAM run that consumed it, the wall fit
│                         against warehouse_ver3's TRUE geometry, and the
│                         absolutely-scored map that came out
├── EVIDENCE_LOCALIZATION_V3.md  F3 Task 2's: AMCL over that frozen
│                         map, every parameter argued from a
│                         measurement, and the ABSOLUTE pose scored
│                         against ground truth through the committed
│                         registration - dry and wet, with the debt
│                         F2 handed over and what the corrections cost
│                         in jitter. F3 Task 3 adds §13: the SECOND
│                         localiser - slam_toolbox's localization mode
│                         over the same frozen pose graph - the A/B the
│                         published research could not settle, and the
│                         recommendation that closes the phase
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
├── slam.yaml             what the MAPPER does, and ekf.yaml's split a
│                         third time. Read only by tools/build_map.sh,
│                         never by anything the live stack runs - and
│                         NOT EDITED BY THE ARM BELOW, because it is an
│                         input the frozen map's build.txt hashes
├── slam_loc.yaml         what the LOCALISER slam_toolbox ships does,
│                         read only by `--localize slam`. It is
│                         slam.yaml RE-ARGUED for a node that tracks in
│                         a frozen graph rather than one that builds
│                         one, and it is a FILE of its own rather than a
│                         second block for the reason its header opens
│                         with - ekf.yaml / ekf_rf2o.yaml's split, one
│                         layer down
├── nav2.yaml             what the PLANNER, the CONTROLLER, the two
│                         COSTMAPS, the BT NAVIGATOR and the BEHAVIOUR
│                         SERVER do, and ekf.yaml's split a SIXTH time.
│                         Read only by --nav. Every number derived from
│                         a measurement this track already took, and the
│                         three addresses two SUB-NODE costmaps cannot
│                         be handed on a command line are CHECKED back
│                         against config.yaml before anything starts
├── collision_monitor.yaml    what the COLLISION MONITOR watches and what
│                         it does about it, and it is ekf.yaml's split a
│                         SEVENTH time. Read only by --monitor. Two
│                         VELOCITY POLYGON sets - a stop and a slowdown -
│                         whose every vertex is a body edge off
│                         model.sdf's own hull plus a MEASURED stopping
│                         distance, and tests/test_collision_monitor_
│                         params.py recomputes all ten of them from
│                         config.yaml. IT IS NOT A SAFETY FUNCTION and
│                         the file opens with nav2's own words for it
├── behavior_trees/
│   └── navigate_to_pose_tricycle_v3.xml
│                         the tricycle tree: no Spin, no BackUp, no
│                         DriveOnHeading. Clear the costmaps, wait,
│                         replan - and if it still cannot plan, STOP
│                         AND REPORT. Since F4 Task 2.5 the whole of it
│                         sits inside a `<Timeout>` NAVIGATION BUDGET -
│                         335 s, derived in config.yaml nav.budget and
│                         recomputed by tests/test_nav2_params.py - so a
│                         goal that cannot be reached ABORTS instead of
│                         driving 130 m
├── smoother.yaml         what the VELOCITY SMOOTHER limits, and to what, and
│                         it is ekf.yaml's split a FIFTH time. Read only by
│                         the `smoother` child - which is not an arm and is
│                         started on every bringup. Four of its six numbers
│                         are DERIVED from config.yaml's navcmd: block and
│                         tests/test_smoother_params.py recomputes every one
│                         of them. Its `feedback` is the CRIB'S RULING
│                         REVERSED on an A/B measured here
│                         (EVIDENCE_NAV_V3.md 6.3)
├── amcl.yaml             what the OTHER LOCALISER does, and ekf.yaml's split a
│                         FOURTH time - two nodes addressed in one file,
│                         both greped for before anything starts. Every
│                         value argued from the model, from F2's MEASURED
│                         error, from the map's own measured support, or
│                         from the seed. Read only by --localize amcl
├── maps/
│   └── warehouse_v3/     THE FROZEN MAP. grid (.pgm + .yaml), pose graph
│                         (.posegraph + .data), build.txt and the
│                         committed registration.yaml. A rebuild is a NEW
│                         directory and never an overwrite
├── m5v3.sh               start [--headless] [--slippery] [--rf2o|--fuse]
│                         [--localize] | stop | status
├── gazebo/
│   └── forklift_ver3/
│       └── model.sdf     the forked vehicle
├── logs/                 ONE DIRECTORY PER BRINGUP, `run-<stamp>/`, one
│   │                     file per child by name inside it (git-ignored).
│   │                     Until F4's closing wave every bringup TRUNCATED
│   │                     the last one's logs, and EVIDENCE_NAV_V3.md
│   │                     17.3 and 17.4 are what that cost: two runs
│   │                     aborted with error_code 205 and the planner
│   │                     log that named the refusal was gone before
│   │                     anybody read the evidence. `start` records the
│   │                     directory in the state file, `status` and
│   │                     `stop` read it back, `stop` prints it, and
│   │                     paths.log_keep_runs bounds how many are kept
│   └── evidence/         one directory per recorded session, CSVs
│                         (untracked). It is a SIBLING of the run
│                         directories and the prune can never reach it
├── EVIDENCE_NAV_V3.md    F4's: the COMMAND PATH, measured with no Nav2 in
│                         the room - the datasheet, the conversion checked
│                         three ways, the slew at the terminals, the
│                         smoother A/B, what the plant delivered and what
│                         a stop costs. 14-15 are Task 2's nav arm and
│                         its thirteen goals; 16 is Task 2.5's
│                         DIAGNOSIS - why one goal in five arrived, the
│                         critic that never scored, the two-sided proof,
│                         the ladder, the re-measured set and the
│                         fail-fast. 17-20 are Task 3's: the DRIVING
│                         CASES (a goal re-tasked mid-path, a station
│                         approach, a Reeds-Shepp reverse leg and the
│                         corner-heavy leg x3), the FLIP experiment on
│                         the other localiser, the COLLISION MONITOR,
│                         and the PHASE VERDICT with the F5 handoff
├── nodes/
│   ├── wheel_odom_core.py   the estimate, as arithmetic. --selftest
│   ├── wheel_odometry.py    the rclpy shell around it. Wiring only.
│   ├── rf2o_twist_core.py   what the laser odometry's output has to have
│   │                        done to it before a filter may read it, as
│   │                        arithmetic. --selftest
│   ├── rf2o_twist.py        the rclpy shell around it. Wiring only.
│   ├── cmd_vel_tricycle_core.py  a body twist becomes a steer angle and a
│   │                        tread speed, as arithmetic - the INVERSE of what
│   │                        wheel_odom_core integrates, same signs, cited.
│   │                        --selftest
│   └── cmd_vel_tricycle.py  the rclpy shell around it. Wiring, a clock and
│                            a ramp. IDLE until something commands
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
    ├── localization_health.py  did the LOCALISER come up LOCALISED, or
    │                     come up merely alive? It subscribes, seeds and
    │                     then reads - in that order, because amcl
    │                     publishes one pose per seed with the truck
    │                     standing still. m5v3.sh refuses on it
    ├── drive_route.py    drive one of config.yaml's profiles, open loop
    ├── drive_twist.py    drive one of config.yaml's TWIST profiles through
    │                     the WHOLE COMMAND PATH and score what came out at
    │                     the terminals. record (needs ROS) | analyse (needs
    │                     nothing) | describe. drive_route's sibling and not
    │                     its second mode - that file speaks gz and imports
    │                     no rclpy at all
    ├── navcmd_health.py  is the command path a LINE, or three processes
    │                     that have never spoken to each other? One ZERO
    │                     twist in at the top and one read off the GZ side
    │                     of the traction terminal. m5v3.sh refuses on it
    ├── evidence_core.py  the arithmetic behind EVIDENCE_SENSORS.md
    ├── sensor_evidence.py  record (needs ROS) | analyse (needs nothing)
    ├── build_map.sh      the OFFLINE slam run: a recorded bag, a mapper
    │                     and two transforms, on a ROS domain of its own
    ├── map_core.py       the arithmetic behind EVIDENCE_MAP_V3.md - the
    │                     grid, the wall fit, the rigid transform and the
    │                     world's own rectangles. --selftest
    ├── nav_health.py     did the NAV ARM come up able to PLAN, or come
    │                     up merely active? SIX lifecycle nodes - each
    │                     costmap is one of its own inside its server -
    │                     and then ONE trivial compute_path_to_pose,
    │                     because an ACTIVE server over an EMPTY costmap
    │                     plans nothing and says nothing about it.
    │                     It commands no motion. m5v3.sh refuses on it
    ├── drive_goal.py     send Nav2 a GOAL and score what the truck did.
    │                     describe | record --goal G | analyse. It
    │                     publishes exactly ONE thing - an action goal -
    │                     and records the controller's own output, both
    │                     terminals, both tf edges, EVERY plan with its
    │                     poses, and the action's feedback. `analyse`
    │                     needs nothing. drive_twist's sibling: that one
    │                     drives a table that cannot respond, this one
    │                     measures the response.
    │                       F4 Task 2.5 added THREE things to it: a
    │                     goal-relative WATCHDOG that abandons a run
    │                     which has stopped closing on its goal and
    │                     names it `outcome=no_progress` in the session;
    │                     CURVATURE FOLLOWING, the gain of the commanded
    │                     yaw rate on the one the plan's own curvature
    │                     required, which is the figure the deviation
    │                     cannot give; and the approach CORRIDOR, what
    │                     each candidate goal box would have cost in
    │                     arrival heading
    ├── monitor_demo.py   THE COLLISION MONITOR'S OWN BENCH, F4 Task 3.
    │                     describe | record | obstacle place|remove |
    │                     analyse. It spawns a 2.40 m box into the
    │                     RUNNING world through gz's own /create, drives
    │                     a CONSTANT twist at the top of the command
    │                     path, and scores the RATIO of the two streams
    │                     either side of the monitor. A twist and not a
    │                     goal, because a speed that changes for a
    │                     controller's own reasons makes that ratio a
    │                     measurement of nothing - and it REFUSES a
    │                     `nav=on` stack, because a controller and a
    │                     bench on one /cmd_vel is a race
    └── map_register.py   derive | show | clearance | support. Needs
                          nothing. `support` places every beam of a
                          recorded drive on the frozen map from the TRUE
                          pose, which is where amcl.yaml's sigma_hit and
                          z_rand come from
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
| `m5v3.sh start` | GPU preflight, then the world, one `forklift_ver3`, both bridges, the wheel-odometry node, the static IMU transform, the EKF, **the command path** and a Gazebo **window**. |
| `m5v3.sh start --headless` | The same without the window. **Use this for anything being measured** — every figure in the three evidence files was taken this way. |
| `m5v3.sh start --slippery` | **A different plant from the same model file.** After the truck is spawned, every wheel's slip compliance is overridden through gz-sim's own `wheel_slip` service to `config.yaml`'s `slippery:` values — `model.sdf` is not edited and no variant of it is generated. Longitudinal slip at cruise goes from 0.95 % to 6.18 %. Combines with `--headless`, in either order. |
| `m5v3.sh start --rf2o` | **A DIFFERENT ESTIMATOR ON THE SAME PLANT**, which is `--slippery`'s mirror image. Three more children — the nav lidar's static transform, `rf2o_laser_odometry_node` matching consecutive scans, and the relay that puts a MEASURED covariance on its twist and corrects two frame errors upstream does not — plus a second `--params-file` giving the filter an `odom1` it fuses `vx` and `vyaw` from. Default OFF, and without it the stack is the six children `EVIDENCE_FUSION.md` §9.3 measured, off one unchanged parameter file. Build the package first with `tools/install_rf2o.sh`. Combines with the other two flags, in any order. |
| `m5v3.sh start --fuse` | **A DIFFERENT ESTIMATOR, IN THE FILTER'S PLACE.** `fuse`'s `fixed_lag_smoother_node` goes up and the `ekf` child does **not** — six children either way, with `fuse` where `ekf` was. It fuses the SAME channels off the SAME two topics (wheel twist `vx`, `vy`, `vyaw` + gyro yaw rate) and publishes its own `odom` → `base_link`, on `topics.fuse_odometry_filtered` and never on the shipping address. Where `--rf2o` adds a sensor, this replaces the estimator, so the two are **mutually exclusive and refused together by name**. Vendor it first with `tools/install_fuse.sh`. Default OFF, and `EVIDENCE_FUSION.md` §11 is the A/B that says why. Combines with `--headless` and `--slippery`. |
| `m5v3.sh start --localize [amcl\|slam]` | **A LAYER ABOVE THE ESTIMATOR, AND THE FIRST THING ON THIS TRACK THAT KNOWS WHERE THE VEHICLE IS.** Whichever localiser is named becomes the **sole publisher of `map` → `odom`**, the one edge F3 adds; the estimator keeps `odom` → `base_link` and neither can become the other. **The two are never alive together** — the exclusion is a `case` with two branches, not two flags — and the value is optional (`localization.default_arm` says which it means without one). **`amcl`** is three more children: the nav lidar's static transform, `nav2_map_server` serving the FROZEN GRID, and `nav2_amcl` localising in it, seeded by a MESSAGE on `/initialpose`. **`slam`** is two: that same static transform and `slam_toolbox`'s `localization_slam_toolbox_node`, which deserialises the FROZEN POSE GRAPH, rasters its own grid onto `/map` (so no `map_server`) and is seeded by the `map_start_pose` PARAMETER. Either way the artifacts THAT arm opens are md5-checked **before anything is started** — the grid against the committed registration, the pose graph against `build.txt` — a rebuilt map is a new artifact, never an overwrite; every lifecycle node is driven to ACTIVE by this script; and a gate refuses a localiser which came up merely alive. **No kidnapped-robot recovery is claimed on either arm.** Combines with all three flags above. `EVIDENCE_LOCALIZATION_V3.md` is what both produced, and §13 is the A/B. **§13.10 IS F4's CONSUMPTION CONTRACT**: consume `map` -> `base_link` off `/tf` on the `amcl` arm, and size the controller's corridor on the PEAKS rather than the means - moving along-track offset up to **0.523 m dry / 1.250 m wet**, worst single `map` -> `odom` step **0.2591 m dry / 0.4927 m wet**, worst heading step **0.0764 rad**, all of it against an instrument floor of **rms 0.0291 m / MAX 0.1179 m** below which no figure is a measurement of the localiser. **AND §13.10a AND §13.10b AMEND THE JUMP HALF OF THAT CONTRACT, TWICE**: those steps were measured OPEN LOOP. With a controller closing a loop on the same arm §13.10a measured **0.8310 m — 3.21×**; F4 Task 3's own case set then moved it again to **1.1919 m — 4.60×**, and measured the OTHER arm's for the first time at **0.8845 m** (§13.10b). Both were runs that ARRIVED down the longest route in the goal table, which is that addendum's own finding — the ROUTE sorts the worst correction and the driving does not. The heading half has held through all three, at 0.0641 rad and then 0.0355. **SIZE A JUMP ALLOWANCE ON 1.20 m DRY ON THE `amcl` ARM AND 0.89 m DRY ON `slam`** — the bound is ARM-SPECIFIC now, and **§13.10b establishes no maximum**: three measurements over three tasks have gone 0.2591 → 0.8310 → 1.1919 as the corpus grew, every one of them on the longest route there was, so a phase that drives a longer one should expect to move it again. |
| `m5v3.sh start --localize --nav` | **THE LAYER THAT DECIDES WHERE THE VEHICLE GOES, F4 Task 2, AND THE FIRST FLAG HERE THAT DEPENDS ON ANOTHER.** Five more children - nav2's `planner_server` (`SmacPlannerHybrid`, `REEDS_SHEPP`, a 1.25 m turning radius DERIVED from the worst corner this plant actually delivered), `controller_server` (`MPPI` with `AckermannConstraints`), `bt_navigator` on a TRICYCLE TREE with no `Spin` and no `BackUp`, `behavior_server` running only `wait`, and ONE `nav_lifecycle_manager` for the four with its BOND SWITCHED OFF at both ends. Costmaps: global = the frozen grid the `--localize` arm is already serving (**no second `map_server`**), local = a rolling window on the nav lidar - and the obstacle layer is honest only because `footprint_clearing_enabled` removes the three pieces of this truck the scanner can see, which is MEASURED (`EVIDENCE_NAV_V3.md` §14.4). **It is REFUSED without `--localize` by name**: the global costmap's activation BLOCKS until `map` -> `base_link` resolves. It adds a PUBLISHER to the top of a command path that is already there and changes nothing about it (F4 constraint 18). `status` and every recorded session say `nav=on@<nav2.yaml md5>`; `analyse` refuses a set that mixes two of them. SIXTEEN processes headless on the `amcl` arm, seventeen with a window. |
| `m5v3.sh start --monitor` | **A LINK IN THE COMMAND PATH RATHER THAN A LAYER OVER IT, F4 TASK 3.** One more child: `nav2_collision_monitor` between the velocity smoother and the tricycle converter, with the CONVERTER'S INPUT remapped onto its output - so the line becomes `/cmd_vel` -> smoother -> `/cmd_vel_smoothed` -> **collision_monitor** -> `/cmd_vel_monitored` -> converter -> the terminals, and without the flag the converter reads the smoother through an identity remap and NOTHING about the path changes. Two **velocity-polygon** sets, a stop and a slowdown, sized off the REAL footprint hull and the MEASURED stopping distances (1.05 m from 0.700 m/s, 0.25 m from the 0.300 m/s transit ceiling) and selected by the INCOMING command's own speed. Every zone starts at a BODY EDGE, because the nav scanner sees three pieces of this truck and this node has no footprint clearing. It **depends on no other flag** and combines with all of them; it also starts `lasertf`, without which it cannot transform a scan and publishes NOTHING - which on this arm is a CUT COMMAND PATH, and it cost a whole demonstration run to find (EVIDENCE_NAV_V3.md 19.5). **IT IS NOT A SAFETY FUNCTION**: nav2's own words are that it "does not provide hard real-time safety certifications", it does not replace a safety-rated PLC, and it sees NOTHING below the nav lidar's 1.80 m scan plane - not a pallet, not a load, not a person. Default OFF, and EVIDENCE_NAV_V3.md 19.8 is why. `status` and every recorded session say `monitor=on@<md5>`. |
| `tools/monitor_demo.py` | **THE GUARD'S OWN BENCH.** `describe` prints every polygon and where the box goes and needs nothing; `record` spawns the box, drives the path and scores it; `obstacle place` and `obstacle remove` are the same two gz calls for the CLOSED-loop run `record` refuses to make; `analyse` needs no ROS. |
| `tools/nav_health.py` | Did the NAV ARM come up able to **PLAN**? SIX lifecycle nodes - each costmap is one of its own inside its server - and then ONE trivial `compute_path_to_pose`, because a server that is ACTIVE over an EMPTY costmap plans nothing and says nothing about it. It commands NO motion. **`start --nav` runs it for you.** |
| `tools/drive_goal.py` | **THE DRIVEN GOAL'S OWN BENCH, F4 Task 2.** `describe`, `record --goal G` and `analyse`. It publishes exactly ONE thing - a `navigate_to_pose` goal, carried into the map frame by the committed registration - and records the controller's own `/cmd_vel`, both terminals, both `/tf` edges, EVERY `/plan` with its poses and the action's feedback. `analyse` scores the arrival **twice** (the ground truth, and what the stack BELIEVED - which is the only one the goal checker ever saw), the deviation from the plan STANDING AT THE TIME, the steer activity, the cusps, the controller frequency, the real-time factor and every `map` -> `odom` correction with what the controller did about it. It needs no ROS and it **refuses a stack whose state file says `nav=off`**. |
| `tools/drive_twist.py` | **THE COMMAND PATH'S OWN BENCH, F4 Task 1.** `describe`, `record --profile P` and `analyse` - a config-tabled TWIST profile published into `/cmd_vel`, through the velocity smoother and the tricycle converter, with every joint of the chain recorded: what was commanded, what the smoother made of it, what each terminal carried, what the axes did and what the truck did. `analyse` needs no ROS. It **REFUSES a table** the converter would have to clamp (unless the row says `expect_clamp`), which is `drive_route.py`'s own line between a table and a live command. |
| `tools/navcmd_health.py` | Did the COMMAND PATH come up as a LINE? It publishes ONE zero twist - the only command that cannot move this vehicle - and reads the answer off the **gz side** of the traction terminal, four hops away. Every other check on the stack is satisfied by three processes that have never spoken to each other. **`start` runs it for you.** |
| `m5v3.sh status` | Each child by name, ALIVE or DEAD, with its log, **which traction the running plant is on**, **which estimator arm is up** and **which absolute layer**. Exit 0 only if every one is alive. |
| `m5v3.sh stop` | Ends this partition's stack, and nothing else. |
| `tools/rtf_probe.sh` | 30 s real-time-factor sample of the world that is already running. |
| `tools/noise_probe.sh scan\|depth <topic>` | Temporal spread of every reading on one sensor topic, vehicle **at rest**. Is the noise the SDF configures actually on the wire? |
| `tools/slip_bench.sh` | Drives the traction terminal at cruise, forward then astern, and reports slip against the commanded and the achieved wheel rate. |
| `tools/install_rf2o.sh` | Builds `rf2o_laser_odometry` from source, at `config.yaml`'s **pinned commit**, into a colcon workspace under `$HOME`. No sudo at any point, idempotent, refuses by name, and writes a manifest of what it fetched beside the build. Run once; `start --rf2o` refuses by name if it has not been. |
| `tools/install_fuse.sh` | Fetches the nine `fuse` packages at `config.yaml`'s **pinned versions** and unpacks them into a prefix under `$HOME`. `apt-get download` + `dpkg-deb -x`, never `apt-get install`: the packages are in the Jazzy archive and this rig has no sudo. Idempotent through a probe that loads a `fuse_models` plugin, refuses by name, `ldd`-checks what it unpacked, and writes a manifest beside the tree. Run once; `start --fuse` refuses by name if it has not been. |
| `tools/localization_health.py` | Did the LOCALISER come up **localised**, or come up merely alive? **On the `amcl` arm** it subscribes to the pose topic, publishes the bringup's initial pose, and reads back the filter's own first answer — **in that order**, because with the truck standing still AMCL publishes exactly one pose per seed and a reader that arrived late would wait for a second that never comes. Two checks: the covariance against a ceiling, and the pose against the seed — and the second is the one the first cannot make, because a localiser that never heard the seed answers from nav2's own prior, which carries the same 0.25 m². **On the `slam` arm all three of those change and every one of the changes is measured** (`EVIDENCE_LOCALIZATION_V3.md` §13.2): it sends **no** seed (that node reads `map_start_pose` on its configure transition, and seeding it here would make the check below a check on the gate); it reads the `map` → `odom` **edge** composed onto the estimator's, because that node's pose topic is travel-gated and publishes **nothing** at rest; and the covariance check therefore **does not run**, which the gate prints rather than passing silently. `evidence_core`'s four localiser tables are where those differences live, and each **refuses** an arm it has never heard of. **`start --localize` runs it for you.** |
| `tools/ekf_health.py` | One bounded read of **the ACTIVE arm's** output, and a refusal if its covariance is over `ekf.startup_check.covariance_max`. It reads the `arm=` line `start` has already written and picks the topic from it (`evidence_core.fused_topic_key`), so one gate covers both estimators. **`start` runs it for you** — it exists because `ekf_node` can diverge during its first cycles and stay ALIVE, at rate, saying nothing (`EVIDENCE_FUSION.md` §8.6, §9). On the `--fuse` arm the first messages carry a covariance of 36 zeros, which no ceiling can fail, so there it gates on the **pose** against `evidence.analyse.fused_sanity_m` instead and prints which check it ran (§11.2c). |
| `tools/drive_route.py <profile>` | Drives one of `config.yaml`'s profiles — `straight`, `square`, `aisle`, `corner_creep`, `mapping` — open loop, on the plant's own clock. It drives; it records nothing. **`mapping` is F3's and is not a bench manoeuvre**: 227.0 m over the whole of `m6/ipc/route.py`'s road graph, nine 90° corners, 774.7 s, at one speed from end to end, so an offline SLAM run has a recording to build a map from. |
| `tools/sensor_evidence.py record --static\|--drive P [--bag]` | Captures one run into `logs/evidence/<session>/`: one headered CSV per stream. `--drive` starts `drive_route.py` itself, so one command is one complete run. It stamps the session with **which plant it was taken on** and refuses if the stack cannot say, and it refuses **before the drive** if the filter has already diverged. `--bag` ALSO writes a rosbag2 of `/clock`, the nav scan and `/tf` into the same session — the container an OFFLINE consumer needs, off by default because nothing in EVIDENCE_SENSORS or EVIDENCE_FUSION reads it. Needs ROS. |
| `tools/sensor_evidence.py analyse [session…]` | Every table in `EVIDENCE_SENSORS.md` and `EVIDENCE_FUSION.md`, from those CSVs — including the EKF scored against the same truth as the raw estimate, and the two subtracted. **Needs no ROS and no Gazebo** — it runs on the Windows python. |
| `tools/build_map.sh <session>` | **The map, built OFFLINE from a recording and frozen.** `slam_toolbox`'s sync node reads a bag `record --bag` wrote — no world, no truck, no live anything — and the products are `maps/<name>/<name>.{pgm,yaml,posegraph,data}` plus a `build.txt` of md5s. It runs on `isolation.map_ros_domain_id` and **refuses if that equals the live domain**, because the bag carries `/tf` and a replay on the live graph would be a second publisher of `odom → base_link`. It **refuses an output directory that already exists**: a rebuild is a new artifact, never an overwrite. |
| `tools/map_register.py derive [--write]` | Fits the map's walls to `warehouse_ver3`'s TRUE geometry, prints **the instrument floor first**, then the ABSOLUTE score — spans measured inside the map against the world's own dimensions, which no registration can flatter. `--write` commits `registration.yaml`; without it nothing is written. Needs nothing. |
| `tools/map_register.py clearance <session>` | Sweeps a recorded drive's **ground truth** along the world's own obstacle rectangles and reports the worst gap and what it was to. It is the measurement `config.yaml`'s corridor arithmetic is a prediction of. |
| `tools/map_register.py support <session>` | Places every beam of a recorded drive on the frozen map **from the ground-truth pose** and reports what the grid explains of it and what it does not. It is where `amcl.yaml`'s `sigma_hit` and `z_rand` come from — measured, before the first scored run, rather than chosen. |

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

**And since F3 Task 2 there is a THIRD LABEL, because there is a third
independent question.** `--localize` does not change the plant, does not
add a sensor to the estimator and does not swap the estimator: it puts a
LAYER above it that knows where the vehicle *is*. So `loc=` is a line of
its own beside `traction=` and `arm=`, written by every bringup —
`none`, or `amcl@<map md5>` — printed by `status`, copied into every
session by `record`, and `analyse` refuses a set that mixes a localised
run with an unlocalised one. All four combinations are legitimate runs.
  **THE LABEL CARRIES THE MAP's md5 AND THAT IS NOT DECORATION.** Every
  absolute figure is a map pose carried into the building by ONE grid's
  registration, and a rebuilt map has its own rotation from the building
  (F3 constraint 16). Without the md5 half, two grids' scores could sit
  in one table with nothing in the numbers to say so — and the same
  eight characters are what let `analyse` refuse to score a session
  through a registration that no longer belongs to it.
  **AND SINCE F3 TASK 3 THE LOCALISER HALF HAS TWO VALUES, WHICH IS THE
  SAME ARGUMENT ONE STEP FURTHER ALONG.** `loc=amcl@735cdbc6` and
  `loc=slam@4bb88852` are two runs on the same floor, the same
  estimator, the same profiles and the same build of the same map, with
  CSVs of identical shape — nothing but the label can tell them apart,
  and one of each in one table would read as one localiser with a wide
  spread rather than as the A/B it destroyed. `analyse` refuses that mix
  by name too. **The md5s are of DIFFERENT FILES**: AMCL localises in
  the grid, whose hash the registration carries; slam_toolbox
  deserialises the pose graph, whose hash is in `build.txt` beside it.
  `evidence_core.loc_md5_artifact()` is the one place that says which,
  and it refuses a localiser it has never heard of.
  **AND `none` IS A VALUE WHERE A MISSING LINE IS NOT.** A stack brought
  up without the flag writes `loc=none`; a state file with no `loc=` line
  was written by a script older than this arm. The two are different
  facts and neither is inferred from the other, which is the traction
  label's own rule twice removed.

**AND SINCE F4 TASK 1 THERE IS A COMMAND PATH, WHICH IS NOT AN ARM.**
`nav2_velocity_smoother` (`smoother`) and `nodes/cmd_vel_tricycle.py`
(`navcmd`) go up on **every** bringup, in that order, after the
estimator: `/cmd_vel` → the smoother → `/cmd_vel_smoothed` → the
converter → `model.sdf`'s own two motor terminals, over two ROS → gz
bridge lines. One line, no bypass, and no ground truth in it (F4
constraint 18). They are not behind a flag for three reasons — the path
has to be verifiable with no Nav2 in the room, F4 Task 2's `--nav` arm
stacks a planner on top of a path that is already there, and **the pair
costs 4.4 % of one core idle and publishes nothing at all** until a twist
arrives. That last one is a mechanism and not a courtesy: the converter
publishes its first message when its first command arrives and stops
again once it has left a standing zero, which is what keeps
`tools/drive_route.py` and `tools/slip_bench.sh` — both of which drive
the same two terminals from the gz side, where the last write wins —
working exactly as they did. `EVIDENCE_NAV_V3.md` is what the path
delivers, and §6.3 is the one ruling it reversed: the velocity smoother
ships `OPEN_LOOP` against the crib's `CLOSED_LOOP`, because a limiter
closed on THIS track's deliberately bad estimate inherits its lag.

**AND SINCE F4 TASK 2 THERE IS A NAV ARM, WHICH IS THE FIRST FLAG HERE
THAT DEPENDS ON ANOTHER.** `--nav` puts nav2's planner
(`SmacPlannerHybrid`, `REEDS_SHEPP`), controller (`MPPI` with
`AckermannConstraints`), BT navigator (on a tricycle tree with **no
`Spin` and no `BackUp`**) and behaviour server (running only `wait`)
over the localised stack, with **one lifecycle manager** for the four —
the only nav2 lifecycle manager on this track, and its bond is switched
off at both ends, which is the whole reason the argument that refused
one for the localiser does not refuse this one. Five children,
`m5_ver3/nav2.yaml`, `m5_ver3/behavior_trees/`.
  **IT IS REFUSED WITHOUT `--localize`, BY NAME, AND THE REASON IS
  MECHANICAL.** The global costmap's frame is `map` and
  `Costmap2DROS::on_activate` BLOCKS until it can transform
  `map` → `base_link`; with no localiser nothing publishes `map` →
  `odom` at all, so that transition never returns and five processes sit
  ALIVE for ever with nothing in any log that reads as an error. The
  same fact is also an ORDERING: the five go up **after** the localiser
  has been driven to ACTIVE, which is why `assert_children_alive` is a
  function called twice rather than a block.
  **NAV2's FORWARD IS THIS TRUCK's REVERSE**, because the forks are at
  model −x, and `nav2.yaml` section (D) is the four parameters that
  reach. **The footprint is COMPUTED off `model.sdf`** — the convex hull
  of every collision and visual, tines included — and **grown per axis**,
  +0.54 m along track and +0.11 m across it, because F3's measured error
  is anisotropic by five times and `footprint_padding` cannot say that.
  **The label is `nav=`**, a fourth line on the state file carrying
  `nav2.yaml`'s own md5, and `analyse` refuses a set that mixes two of
  them — which it did, five ways, during the task that wrote it.
  `EVIDENCE_NAV_V3.md` §14–§15 is the arm and the first driven goals,
  and §15.2 is the ladder of aborted runs each of that file's
  derivations came off.
  **AND §16 IS WHY ONE GOAL IN FIVE ARRIVED, AND WHAT IT TOOK.**
  `PathAlignCritic` — the heaviest critic in the file and the only
  one that penalises deviation ALONG the path — **never scored on
  any control tick of any run in §15**, because its gate is a path
  index and the prediction horizon could not reach it: 0 of 1000
  plans. The horizon is a DISTANCE and `time_steps` is a COUNT, and
  §15.2 rung 11's speed drop had quietly cut it from 1.96 m to
  0.84 m — under the vehicle's own 1.25 m turning radius. Four
  parameters move: `time_steps` 56 → **134**, `prune_distance` 2.0
  → **2.5**, `offset_from_furthest` 20 → **12**,
  `use_path_orientations` → **true**. **Ten arrivals in eleven**
  against one in five, the headline goal **6 of 6** — and
  `ring_corner` **2 of 3**, which is the residual §16.4c names and
  does not pretend to have fixed. §16 also adds the FAIL-FAST: a
  goal-relative watchdog in the bench and a 335 s budget in the
  tree, so a goal that cannot be reached is a named failure in
  30 s rather than 130 m and 459 plans.

**EIGHT children by default, ELEVEN with `--rf2o`, eight again with
`--fuse`, ELEVEN with `--localize amcl`, TEN with `--localize slam`,
SIXTEEN with `--localize amcl --nav` and SEVENTEEN with `--monitor` on
top of that** - the last flag adds `collision_monitor`, and on a stack
with no localiser and no nav arm it adds `lasertf` as well, which is
NINE
(six, nine, six, nine and eight of them before F4 Task 1 added the two
above) —
`--fuse` swaps a child rather than adding one, so the count is unchanged
and `fuse` stands where `ekf` did, while `--localize` adds three on one
arm and two on the other.
`status` names them all back: the
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
(`EVIDENCE_FUSION.md` §10.1). **With `--localize` there are three more
again**: that same `lasertf` — AMCL needs it for a different reason and
there is one of it — plus `nav2_map_server` (`map_server`) and
`nav2_amcl` (`amcl`). Those two go up AFTER the estimator rather than
before the bridges, and that is the opposite ordering for the opposite
reason: AMCL's scan subscription is a tf2 `MessageFilter`, which QUEUES
what it cannot yet transform, so it has nothing to lose by starting late
— while `map_server` has a 1712 × 1196 grid to read and AMCL blocks in
`on_activate` waiting for it, which makes the two lifecycle transitions
the slow part of that arm. **With `--localize slam` there are TWO more
instead**: the same `lasertf`, and `slam_toolbox`'s
`localization_slam_toolbox_node` (`slam_loc`) — and there is no
`map_server` because that node deserialises the pose graph itself and
rasters its own grid onto `/map`, which is the same service for the same
downstream consumer out of a different artifact. Its CONFIGURE
transition is where a 48.7 MB pose graph is read off disk, so the slow
part of that arm is one transition rather than four. **No broker, no
fleet manager, no HMI, no
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

**F3's map is FROZEN, and the freeze is a mechanism rather than a
promise.** `maps/warehouse_v3/` holds a grid, a pose graph, a `build.txt`
naming the session and the parameters it came from, and a
`registration.yaml` that carries the **md5 of the .pgm it was fitted to**.
`map_register.load_registration()` refuses a registration whose grid has
changed underneath it, and `build_map.sh` refuses to write into a
directory that already exists — so a rebuilt map is a new artifact under
a new name, and nothing downstream can carry the old rotation across it.
A rebuilt map has its own rotation from the building; that is the whole
reason, and `EVIDENCE_MAP_V3.md` is where the two are compared if there
is ever a second.

**The map is built from the REAL sensor chain and the REAL estimate, and
the ground truth is not in the bag.** What `slam_toolbox` corrects is
F2's EKF — which drifts 9.86 m of position and 23.4° of heading over the
225.0 m of the mapping drive — off the TiM571-profile nav lidar with its
noise and its per-run bias draw. `/forklift/gz/odom` is deliberately
absent from `evidence.bag.topics`: it is a measurement reference (F2
global constraint 13) and a bag that carried it into a SLAM run would be
one careless remap away from being the thing the map was built on.

**DDS discovery on this rig has failed before.** Mid-session on
2026-08-25 the WSL multicast path died and FastDDS discovery went with it;
m6 works around it with a unicast profile at `m6/tools/fastdds_loopback.xml`
(exported as `FASTRTPS_DEFAULT_PROFILES_FILE`). This track does **not**
carry one — a bare `ros2 topic pub` / `echo` pair was verified working on
domain 97 before Task 1's measurements, and three participants is a long
way from the ~40 that made m6's default initial-peer range too small. If
bridged topics start going missing at boot, that file is the first thing
to try, not a mystery.
