# Report m5-07b — the `odom → base_link` transform

```
brief:               docs/briefs/m5-07b-odom-tf.md
status:              done
files_changed:       agv/forklift/model.sdf
                     agv/forklift/config.yaml
                     agv/forklift/launch/vehicle.launch.py
                     agv/forklift/README.md
                     agv/forklift/scripts/check_sensor_frames.py
                     agv/forklift/scripts/check_odom_tf.py   (new)
                     agv/forklift/EVIDENCE_ODOM_TF.md        (new)
                     docs/reports/m5-07b-odom-tf.md
invariants_touched:  none. Invariant 10 is the reason for the shape of the
                     answer rather than something the answer strains
open_questions:      seven, below; three are requests to sim/, one to the
                     SLAM brief, one to the realistic-odometry brief
next_suggested:      the realistic-odometry brief can start against a
                     working chain: `ground_truth_tf:=false` is the whole
                     retirement, and the frames do not change
```

## Configuration, not a node, and it was checked before anything was written

`gz-sim`'s `OdometryPublisher` **already publishes the transform**. Probed
against the unmodified model, before any edit: it advertises
`gz.msgs.Pose_V` on `/model/Forklift/pose`, carrying `frame_id`
`forklift/odom` and `child_frame_id` `forklift/base_link` — verbatim, not
re-scoped. So no node was written, and the publishing-side change is
**one SDF element**, `<tf_topic>`.

Two reasons it is set explicitly rather than left at the default:

- the default name is **model-scoped** and moves if the model is spawned
  under another name, which is precisely what `model.sdf`'s own COMMAND
  TOPICS rule refuses for every other system in the file;
- the name is where the stream is labelled: `/forklift/gz/tf_ground_truth`.

A node was rejected for the reason the brief named. It would have had to
recompute a pose from joint states, producing a **second answer to one
question** differing by its own integration error, with nothing to say
which is right — the failure invariant 10 exists to prevent. The ROS side
is one bridge entry, `tf2_msgs/msg/TFMessage[gz.msgs.Pose_V`, remapped
onto `/tf`. `ros2 topic info /tf --verbose` reports **`Publisher count:
1`**, which is that claim measured rather than argued.

## The numbers

| Figure | Value |
|---|---|
| **Rate** | **20.000 Hz**, measured from the transform stamps over 14.95 s of simulated time, 300 transforms. `model.sdf` *declares* 20 Hz; the checker compares the two rather than quoting one |
| **Continuity** | largest gap **0.0500 s**, equal to the nominal period, across the whole driven arc and the stop |
| **Residual vs the ground-truth odometry topic** | **max 0.000e+00 m, RMS 0.000e+00 m, max 6.661e-16 rad**, over **253 paired samples**, looked up through a real `tf2` buffer at each odometry message's own stamp |
| **Motion** | path **3.989 m**, yaw swept **0.7781 rad (44.6°)** — the transform moved with the vehicle in translation and rotation |
| Wall-clock arrival, second instrument | `ros2 topic hz /tf` → 19.5–20.0 Hz. A different measurement on a different clock; **not** an RTF figure, and none was taken |

The residual bounds the **transport** — bridge conversion, listener,
buffer, interpolation — because both sides are the same simulator pose.
It is not an odometry-error figure and there is no odometry error to
measure. The `6.661e-16 rad` is double-precision noise in the
quaternion-to-yaw conversion.

**The one independent witness of real motion**: over that 3.989 m arc the
drive wheel turned 33.871 rad = **4.065 m of tread**, out of the physics
engine rather than the odometry system. The **0.076 m** difference is
slip, and **this transform carries none of it**. That is the clearest
single measurement of what the realistic-odometry brief exists to
introduce.

## The frame names actually published

```
map (absent, checked)  ←  forklift/odom  ←  forklift/base_link
                                              ├── nav_lidar_link
                                              ├── safety_scanner_front_link
                                              └── safety_scanner_rear_link
```

`forklift/odom` and `forklift/base_link` carry the model prefix; the
three sensor frames do not. That asymmetry is Gazebo's — the parent pair
is what the `OdometryPublisher` puts in its messages, each sensor frame
is what its `<gz_frame_id>` puts in its scan header — and renaming either
side stops the lookups resolving. A `slam_toolbox` / Nav2 configuration
is therefore pointed at `odom_frame: forklift/odom`, `base_frame` and
`robot_base_frame`: `forklift/base_link`. `map` does not exist and its
name is **not** decided here.

The whole chain was resolved through a real `TransformListener` buffer
and captured with `tf2_echo` (`EVIDENCE_ODOM_TF.md` §4), including
`forklift/odom → nav_lidar_link`, which is the composite lookup a SLAM
node actually performs.

## The owner's scope correction, and what it changed here

The ruling of 2026-07-31 — IMU, wheel odometry with slip and noise, EKF,
and **the EKF owns `odom → base_link`** — landed while this brief ran. It
is addressed in four ways, all inside `agv/`:

1. **The transform is published, and labelled interim everywhere it
   appears**: `model.sdf`, `config.yaml`, the launch file, `README.md`
   and the first paragraph of `EVIDENCE_ODOM_TF.md`. Nothing written
   reads as though ground truth is the permanent answer.
2. **The ground-truth stream is named.** The transform topic is
   **`/forklift/gz/tf_ground_truth`** (config key `gz_tf_ground_truth`),
   and the bridge node carrying it is
   **`forklift_ground_truth_tf_bridge`**. Those are the names the
   follow-up and localisation briefs should cite. A checker asserts the
   name contains `ground_truth`, so it cannot quietly revert.
3. **The seam is a switch that was run, not a paragraph.** The transform
   has its **own bridge node** behind the launch argument
   **`ground_truth_tf`** (default `true`). `EVIDENCE_ODOM_TF.md` §6 is
   the same stack launched with `ground_truth_tf:=false`: the node, the
   topic and the frame are all gone, so the EKF will be the **only**
   publisher of that edge. The EKF consumes the IMU and wheel odometry
   from `/forklift/joint_states` — **not** this stream — and **no frame
   name changes**, which is why `<odom_frame>` and `<robot_base_frame>`
   are written explicitly.
4. **The caveat is sharpened into the two-phase plan**, including the
   reason: with ground-truth odometry the degenerate aisle stretches
   `m5-08` measured cannot bite, AMCL has nothing to correct, and any
   "error against ground truth" figure is circular.

**One part of point 2 this directory could not complete.** `/forklift/odom`
also carries ground truth and its name does not say so, but it is a
cross-layer contract — `sim/launch/forklift_bringup.launch.py` bridges
it, `sim/scenarios/run_forklift_rehearsal.py` reads it — so renaming it
from here would break a layer this brief may not edit. Open question 1.

## Two findings that belong to every future consumer of this tree

- **`use_sim_time:=true` is mandatory, and the failure is disguised.**
  Every message is stamped with the simulation clock; a consumer on the
  system clock asks for a transform **1.785e+09 s** newer than any it
  holds, gets nothing, and reports a *missing transform* rather than a
  misconfigured node. `tf2_monitor` shows the same trap from the other
  side, reporting a net delay of `3.4e+08` s for a tree publishing every
  50 ms. `check_odom_tf.py` now checks that a consumer on simulation time
  resolves the transform at its own "now".
- **Wait for the transform, bounded.** m5-06 open question 5, confirmed
  again: both `tf2_echo` captures print `frame does not exist` twice
  before resolving. Nav2 and SLAM must wait, not assume.

## Open questions

1. **Request to `sim/` and to the realistic-odometry brief: `/forklift/odom`
   is ground truth and does not say so.** When the EKF lands,
   `/forklift/odom` is the name the **estimate** should carry and the
   ground-truth stream should move to `/forklift/odom_ground_truth`
   (gz side `/forklift/gz/odom_ground_truth`). That rename touches
   `sim/launch/forklift_bringup.launch.py`, `sim/launch/warehouse_bringup.launch.py`,
   `sim/scenarios/run_forklift_rehearsal.py` and `agv/forklift/scripts/forklift_io.py`,
   so it is one coordinated brief, not a unilateral edit. **Not doing it
   leaves two pose streams and one ambiguous name.**
2. **Request to `sim/`: a stack brought up through
   `sim/launch/forklift_bringup.launch.py` still has no
   `odom → base_link`.** That file bridges `/forklift/gz/odom` but knows
   nothing of `/forklift/gz/tf_ground_truth`, so SLAM under it will fail
   for want of the transform. The fix is one bridge entry
   (`tf2_msgs/msg/TFMessage[gz.msgs.Pose_V`) remapped onto `/tf`, ideally
   behind the same `ground_truth_tf` switch so the two launch files
   retire it together.
3. **To the SLAM brief: the `map` frame name is undecided.** `map` today
   is the default everything expects, but the parent pair here is
   prefixed (`forklift/odom`) and M6 puts four vehicles on one graph. A
   fleet-wide `map` with per-vehicle `forklift_N/odom` is the usual
   answer; it is a naming decision, not an implementation detail, and it
   is cheapest to take before a map exists.
4. **Unaddressed: the sensor frames are unprefixed, and four vehicles
   will collide on them.** `nav_lidar_link` is what the scan header
   carries, set by `<gz_frame_id>`; four forklifts publish four
   transforms with that one child name. Fixing it means the frame ids in
   `model.sdf` become spawn-dependent, which is a model-templating
   decision for M6, and nothing in M5 forces it.
5. **The drive distance varies with machine load and that is expected.**
   The drive legs are timed on the wall clock while the path is measured
   on the simulation clock; an earlier run of the identical profile
   covered 5.819 m against this run's 3.989 m. Every check is against
   measured motion, never an expected distance. **No RTF figure is
   derived from it and none should be** — another agent may be running
   the simulator (LESSONS 2026-07-30).
6. **Container evidence only.** The owner's WSL host has never run this
   configuration.
7. **Repeated, still open from m5-06:** the arena has almost nothing at
   the navigation lidar's 1.80 m plane, so SLAM in
   `sim/worlds/forklift_arena.sdf` will have little to map;
   `sim/worlds/warehouse.sdf` (racks 2.0 m, walls 2.5 m) is the world
   that suits it. This brief drove in the arena because a clear lane, not
   a rich one, is what a transform check needs.

## Notes

- **No dependency added.** `ros_gz_bridge` already ships the
  `tf2_msgs/msg/TFMessage` ↔ `gz.msgs.Pose_V` pair (checked in the
  installed library, not assumed), and `tf2_ros` was already in use by
  `sensor_tf.py`. Nothing was installed.
- **Nothing outside `agv/forklift/` and this report was written.** `sim/`,
  `plc/`, `hmi/` and `bridge/` were read where needed and left alone; the
  items above are requests.
- No static `odom → base_link` was published, no second source of the
  transform was introduced, no sensor pose and no kinematic value was
  touched. `check_sensor_frames.py` was extended by one loop (it now
  sweeps `<tf_topic>` as well as `<topic>` and `<odom_topic>`, or a topic
  the model publishes would sit outside the contract check) and re-runs
  PASS at 19 static and 28 live checks, unchanged.
- Runs were isolated on **both** transports, `GZ_PARTITION=m507bodom` and
  `ROS_DOMAIN_ID=72`, headless, and every process was confirmed gone
  afterwards.
- Nothing committed, nothing staged, no branch created.
