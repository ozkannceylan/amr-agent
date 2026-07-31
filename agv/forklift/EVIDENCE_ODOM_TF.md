# EVIDENCE — `odom → base_link`, the vehicle's motion estimate

**Read this first, because every figure below depends on it.** The
transform recorded here is **Gazebo's ground truth**. It is the
simulator's own pose for the model, republished as a transform. It
carries **no wheel slip, no encoder quantisation and no heading drift** —
none, not "a little" — and a real vehicle's `odom → base_link` drifts
without bound. A reader who assumes realistic odometry would misread
every localisation figure that follows this file.

**It is also interim.** The owner ruled on 2026-07-31 that odometry
becomes realistic: an IMU joins the model, wheel odometry is computed
from the joint states with slip and noise modelled, and an EKF fuses the
two. **The EKF then owns `odom → base_link`**, and this ground-truth
stream keeps publishing in a different and permanent role — the
**reference** that localisation error is measured against. Section 6 is
the seam, demonstrated live rather than promised.

Why that second phase is not optional: with ground-truth odometry the
degenerate aisle stretches `m5-08` measured cannot bite, AMCL has nothing
to correct, and any "error against ground truth" figure is circular —
AMCL scored against its own input.

**Every block below is quoted from the output of the command named above
it.** No number in this file was computed by hand, and no figure appears
that no tool printed (LESSONS 2026-07-27).

| Item | Value |
|---|---|
| Date | **2026-07-31**, 08:53 UTC |
| Environment | **Session container**, not the owner's WSL host: Ubuntu 24.04.4, ROS 2 Jazzy, Gazebo Sim 8.11.0, `/usr/bin/python3` 3.12.3, headless, software rasteriser. Versions are `sim/setup/CONTAINER_TOOLCHAIN.md` |
| Isolation | `GZ_PARTITION=m507bodom`, `ROS_DOMAIN_ID=72`, `QT_QPA_PLATFORM=offscreen`. Both transports, because `ROS_DOMAIN_ID` does not isolate Gazebo (LESSONS 2026-07-27) |
| Repository state | `HEAD 28e12f0`, plus this brief's uncommitted working tree |
| World | `sim/worlds/forklift_arena.sdf`, unmodified and not owned here; spawn `x=-6.0, y=-6.0, yaw=0` — a clear lane, no obstacle on the driven arc |
| Under test | `model.sdf`'s `OdometryPublisher`, `config.yaml`, `launch/vehicle.launch.py`, `scripts/check_odom_tf.py` as this brief leaves them |
| Not measured | **No real-time factor.** Another agent may be running the simulator, so no RTF figure is taken (LESSONS 2026-07-30) |

**This is container evidence.** The owner's WSL host has never run this
configuration and nothing here is evidence about it.

---

## 1. The question asked before anything was written: config or node?

The brief's own constraint — invariant 10, one owner per datum — makes
the cheap answer the correct one **if** gz-sim can publish the transform
itself. It can, and it already was. Probed against the **unmodified**
model, before any edit:

`gz topic -l | grep -Ei "odom|pose|tf"`

```
/forklift/gz/odom
/model/Forklift/odometry_with_covariance
/model/Forklift/pose
/world/forklift_arena/dynamic_pose/info
/world/forklift_arena/pose/info
```

`gz topic -i -t /model/Forklift/pose`

```
Publishers [Address, Message Type]:
  tcp://192.0.2.2:34913, gz.msgs.Pose_V
```

`gz topic -e -t /model/Forklift/pose -n 1`

```
pose {
  header {
    stamp {
      sec: 9
      nsec: 944000000
    }
    data {
      key: "frame_id"
      value: "forklift/odom"
    }
    data {
      key: "child_frame_id"
      value: "forklift/base_link"
    }
  }
  position {
    x: -5.9999999999999716
    y: -6
  }
  orientation {
    x: 3.1190859893472086e-10
    y: 7.3875059896128433e-10
    z: -6.565108971838445e-19
    w: 1
  }
}
```

Three findings, and they decided the shape of the work:

1. **`OdometryPublisher` publishes the transform whether or not you ask
   it to.** No node is needed, and no node was written. A node would have
   been a second computation of a pose the simulator already knows —
   exactly the second source invariant 10 exists to prevent.
2. **The default topic name is model-scoped**: `/model/Forklift/pose`. It
   moves if the model is spawned under another name, which is what
   `model.sdf`'s COMMAND TOPICS note refuses for every other system in
   the file. So `<tf_topic>` is set explicitly. That is the entire code
   change on the publishing side: **one SDF element**.
3. **The frame ids are carried verbatim** — `forklift/odom` and
   `forklift/base_link`, exactly as `<odom_frame>` and
   `<robot_base_frame>` declare them. gz-sim does **not** re-scope them
   when they are set explicitly, and the brief was right to require this
   be checked rather than assumed.

The ROS side is one bridge entry,
`tf2_msgs/msg/TFMessage[gz.msgs.Pose_V`, remapped onto `/tf`.

---

## 2. The graph, and who publishes the edge

`ros2 topic list`

```
/clock
/forklift/cmd/fork_speed
/forklift/cmd/steer_angle
/forklift/cmd/traction_speed
/forklift/fork_height
/forklift/gz/fork_cmd
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd
/forklift/joint_states
/forklift/linear_speed
/forklift/obstacle/in_stop_zone
/forklift/obstacle/min_distance
/forklift/odom
/forklift/safety_scanner_front/measurement
/forklift/scan
/parameter_events
/rosout
/tf
/tf_static
```

`ros2 topic info /tf --verbose`

```
Type: tf2_msgs/msg/TFMessage

Publisher count: 1

Node name: forklift_ground_truth_tf_bridge
Node namespace: /
```

`ros2 node list`

```
/forklift_bridge
/forklift_ground_truth_tf_bridge
/forklift_io
/obstacle_zone
/sensor_tf
```

**Publisher count 1 is the invariant-10 claim, measured.** One node
publishes `odom → base_link`, it is a bridge rather than an estimator,
and its name says which source it carries.

---

## 3. Rate, continuity and the residual

`/usr/bin/python3 agv/forklift/scripts/check_odom_tf.py --live --drive`,
section 4 (sections 1–3 are the static agreement checks and are quoted in
§5):

```
== 4. the running graph ====================================================
ok    /tf carries forklift/odom -> forklift/base_link            5 transform(s) in the first 30 s
      driving: 3 s at 0.50 m/s, steer +0.00 rad; 6 s at 0.50 m/s, steer +0.30 rad; 3 s at 0.50 m/s, steer +0.00 rad; 2 s at 0.00 m/s, steer +0.00 rad
ok    the transform is published continuously                    largest gap 0.0500 s against a nominal period of 0.0500 s
      MEASURED rate 20.000 Hz over 14.95 s of simulated time, 300 transforms; interval min 0.0500 s max 0.0500 s mean 0.0500 s
ok    the measured rate is the declared one within 5 %           20.000 Hz measured vs 20.0 Hz declared in model.sdf
ok    nothing else publishes on /tf                              one edge only
ok    the odometry topic names the same frames as the transform  forklift/odom -> forklift/base_link
      these are the strings a Nav2 / slam_toolbox configuration is pointed at: odom_frame "forklift/odom", base_frame "forklift/base_link"
ok    tf2 resolves forklift/odom -> forklift/base_link           
ok    tf2 resolves forklift/odom -> nav_lidar_link               
ok    tf2 resolves forklift/odom -> safety_scanner_front_link    
ok    tf2 resolves forklift/odom -> safety_scanner_rear_link     
ok    map is absent, as expected before SLAM runs                "map" passed to lookupTransform argument target_frame does not exist.
ok    the simulation clock reaches a consumer of this tree       node clock reads 32.798 s with use_sim_time - /clock is bridged
ok    a consumer on simulation time resolves it at "now"         asked at the node's own now minus one period
      the same lookup from a node left on the SYSTEM clock would ask for a stamp 1.785e+09 s ahead of the newest transform and fail: every consumer of this tree needs use_sim_time
      forklift/odom -> forklift/base_link         xyz [-2.604 -4.165 +0.000]  yaw +0.7771 rad (+44.52 deg)
      forklift/odom -> nav_lidar_link             xyz [-1.931 -4.065 +1.800]  yaw +0.7771 rad (+44.52 deg)
      forklift/odom -> safety_scanner_front_link  xyz [-2.420 -3.354 +0.150]  yaw +1.5625 rad (+89.52 deg)
      forklift/odom -> safety_scanner_rear_link   xyz [-2.787 -4.977 +0.150]  yaw -1.5791 rad (-90.48 deg)
      transform start (-6.000, -6.000) yaw -0.0000 rad -> end (-2.604, -4.165) yaw +0.7771 rad
ok    the transform moved with the vehicle                       path 3.989 m, yaw swept 0.7781 rad (44.6 deg)
      drive wheel turned 33.871 rad = 4.065 m of tread against 3.989 m of transform path: the +0.076 m difference is slip, which THIS transform does not carry
ok    the transform agrees with the odometry topic               253 paired sample(s), 0 outside the buffer: max 0.000e+00 m, RMS 0.000e+00 m, max 6.661e-16 rad
      that residual is a TRANSPORT figure, not an odometry-error figure: both sides are the same simulator pose, one through the odometry message and one through the transform

RESULT: PASS (29 check(s), 0 failing)
```

### The four numbers a reader should take from that block

| Figure | Value | What it is |
|---|---|---|
| **Rate** | **20.000 Hz** | measured from the transform stamps over 14.95 s of simulated time, 300 transforms. Not quoted from `model.sdf` — `model.sdf` *declares* 20 Hz, and the check compares the two |
| **Continuity** | **largest gap 0.0500 s** | equal to the nominal period. No missed cycle in the whole drive, moving or stopped |
| **Residual vs the odometry topic** | **max 0.000e+00 m, RMS 0.000e+00 m, max 6.661e-16 rad**, over **253 paired samples** | the transform, looked up through a real `tf2` buffer at each odometry message's own stamp, against that message's pose |
| **Motion** | **path 3.989 m, yaw swept 0.7781 rad (44.6°)** | the transform moved with the vehicle, translation and rotation both |

**What the residual does and does not mean.** Both sides of it are the
*same* simulator pose: one travelled as `nav_msgs/Odometry`, the other as
a `Pose_V` converted to `TFMessage`, through the bridge, a
`TransformListener` and a `tf2` buffer with interpolation. So the figure
bounds the **transport**: a dropped message paired against the wrong
stamp, a truncated field, a lagging bridge or a mis-set child frame would
all show here. It is **not** an odometry-error figure, and there is no
odometry error to measure — see the top of this file. The `6.661e-16 rad`
is double-precision noise in the quaternion-to-yaw conversion, `3.8e-14`
degrees.

**Why the drive covered 3.989 m and not 6 m.** The drive legs are timed
on the **wall** clock (12 s of commanded motion at 0.5 m/s) while the
path is measured on the **simulation** clock, and how much simulated time
a wall-clock second buys depends on what else is running on the machine.
An earlier run of the identical profile covered `5.819 m`. Nothing about
the transform changes with it: every check above is against **measured**
motion, never against an expected distance. No RTF figure is derived from
this and none should be.

**The slip line is the one genuinely independent witness.** The drive
wheel's own angle comes out of the physics engine, not out of the
odometry system: `33.871 rad × 0.12 m = 4.065 m` of tread against
`3.989 m` of transform path. **That +0.076 m gap over 4 m is the slip a
real wheel odometry would have to carry, and this transform does not
carry it.** It is the clearest single measurement of what phase 2 exists
to introduce.

### `ros2 topic hz /tf` — a second instrument, on the other clock

```
average rate: 20.010
	min: 0.049s max: 0.051s std dev: 0.00026s window: 22
average rate: 19.812
	min: 0.049s max: 0.070s std dev: 0.00301s window: 42
average rate: 19.487
	min: 0.049s max: 0.098s std dev: 0.00672s window: 61
average rate: 19.621
	min: 0.049s max: 0.098s std dev: 0.00583s window: 82
average rate: 19.611
	min: 0.049s max: 0.098s std dev: 0.00542s window: 102
average rate: 19.658
	min: 0.049s max: 0.098s std dev: 0.00499s window: 122
```

`topic hz` measures **arrival** on the wall clock; the 20.000 Hz above is
the **stamp** rate on the simulation clock. The two are different
measurements of different things and both are reported. The wall figure
is a property of this loaded container on this afternoon, it is **not** a
real-time factor, and no gate criterion should ever be written against
it.

---

## 4. The chain, captured rather than asserted

`ros2 run tf2_ros tf2_echo forklift/odom forklift/base_link` — the
moving edge, read the way Nav2 reads it, vehicle stationary:

```
[INFO] [tf2_echo]: Waiting for transform forklift/odom ->  forklift/base_link: Invalid frame ID "forklift/odom" passed to canTransform argument target_frame - frame does not exist
[INFO] [tf2_echo]: Waiting for transform forklift/odom ->  forklift/base_link: Invalid frame ID "forklift/odom" passed to canTransform argument target_frame - frame does not exist
At time 0.400000000
- Translation: [-6.000, -6.000, 0.000]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, -0.000, 1.000]
- Rotation: in RPY (radian) [0.000, 0.000, -0.000]
- Rotation: in RPY (degree) [0.000, 0.000, -0.000]
- Matrix:
  1.000  0.000  0.000 -6.000
 -0.000  1.000 -0.000 -6.000
 -0.000  0.000  1.000  0.000
  0.000  0.000  0.000  1.000
At time 1.400000000
- Translation: [-6.000, -6.000, 0.000]
```

`ros2 run tf2_ros tf2_echo forklift/odom nav_lidar_link` — **the whole
chain in one lookup**: the moving edge from `/tf` composed with the
static sensor edge from `/tf_static`, which is what a SLAM node actually
asks for when it transforms a scan:

```
At time 6.600000000
- Translation: [-5.450, -6.400, 1.800]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, -0.000, 1.000]
- Rotation: in RPY (radian) [0.000, 0.000, -0.000]
- Rotation: in RPY (degree) [0.000, 0.000, -0.000]
- Matrix:
  1.000  0.000  0.000 -5.450
 -0.000  1.000 -0.000 -6.400
 -0.000  0.000  1.000  1.800
  0.000  0.000  0.000  1.000
```

`-5.450 = -6.000 + 0.550` and `-6.400 = -6.000 - 0.400` and `1.800`: the
navigation lidar's mount offset from `model.sdf`, added to the vehicle
pose by `tf2` and not by anyone's arithmetic.

### The tree, and the frame names actually published

```
  map                     absent — no SLAM, no AMCL yet. Checked, not assumed:
   |                      lookupTransform("map", ...) raises "does not exist"
   |
  forklift/odom           <odom_frame>. INTERIM SOURCE: the simulator's
   |                      ground truth, 20 Hz, on /tf
   |
  forklift/base_link      <robot_base_frame>
   |
   +-- nav_lidar_link                  /tf_static, from sensor_tf.py
   +-- safety_scanner_front_link       /tf_static, from sensor_tf.py
   +-- safety_scanner_rear_link        /tf_static, from sensor_tf.py
```

**The names are `forklift/odom` and `forklift/base_link`, with the model
prefix, and the sensor frames have none.** That asymmetry is Gazebo's,
not a choice made here: the parent pair is what `model.sdf`'s
`OdometryPublisher` puts in its messages, and each sensor frame is what
that sensor's `<gz_frame_id>` puts in its own scan header. Renaming
either side to tidy it stops the lookups resolving.

**What a Nav2 / slam_toolbox configuration must therefore say:**

| Parameter | Value |
|---|---|
| `slam_toolbox`: `odom_frame` | `forklift/odom` |
| `slam_toolbox`: `base_frame` | `forklift/base_link` |
| `slam_toolbox`: `map_frame`, and Nav2 `global_frame` | **not decided here.** `map` today; whether it becomes `forklift/map` is the SLAM brief's, and M6's four vehicles will force the question |
| Nav2: `robot_base_frame` | `forklift/base_link` |
| every consumer: `use_sim_time` | **`true`, mandatory** — see below |

**`use_sim_time` is not optional and the failure is disguised.** Every
message here is stamped with the simulation clock. A consumer left on the
system clock asks for a transform `1.785e+09` s newer than the newest one
it holds, gets nothing, and reports a *missing transform* rather than a
misconfigured node. `tf2_monitor` shows the same trap from the other
side, reporting `Net delay avg = 3.4e+08` s for a tree whose real
publishing interval is 50 ms. `tf2_echo` is immune only because it looks
up at time zero, meaning "latest available".

**And a transform is available when the buffer says so, not when the
publisher starts.** Both `tf2_echo` runs above print
`Invalid frame ID ... frame does not exist` twice before resolving. That
is m5-06 open question 5, unchanged and inherited: **a consumer of this
tree waits for the transform, bounded, and does not assume one at
start-up.**

---

## 5. The static agreement checks

`/usr/bin/python3 agv/forklift/scripts/check_odom_tf.py`, sections 1–3,
which need no simulator:

```
== 1. model.sdf owns the transform, and owns it once =======================
ok    model.sdf declares exactly one OdometryPublisher           1 found
ok    it names its transform topic explicitly                    tf_topic = '/forklift/gz/tf_ground_truth' (without it the name is the model-scoped default and moves with the spawn name)
ok    it publishes the transform from the same pose as the odometry topic odom_topic = '/forklift/gz/odom'
ok    the transform is planar, like the vehicle                  <dimensions> = '2'
      declared publish frequency 20 Hz - a DECLARATION; section 4 measures what arrives
ok    <robot_base_frame> is the parent of the sensor frames      forklift/base_link vs sensor_tf parent forklift/base_link
ok    the sensor transforms do not also claim the base frame as a child children: ['nav_lidar_link', 'safety_scanner_front_link', 'safety_scanner_rear_link']
ok    no script in this directory broadcasts a moving transform  broadcasters found: {'sensor_tf.py': ['StaticTransformBroadcaster']}

== 2. config.yaml mirrors the two names ====================================
ok    config topics.gz_tf_ground_truth == model.sdf <tf_topic>   /forklift/gz/tf_ground_truth vs /forklift/gz/tf_ground_truth
ok    the gz name says which source this transform comes from    /forklift/gz/tf_ground_truth - after the EKF lands there are two pose streams and the reference must be named
ok    config topics.tf is /tf                                    /tf - the only topic a TransformListener reads
ok    config frames.base == model.sdf <robot_base_frame>         forklift/base_link vs forklift/base_link

== 3. launch/vehicle.launch.py carries it onto /tf, switchably =============
ok    the transform bridge carries it, gz -> ROS                 /forklift/gz/tf_ground_truth@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V
ok    it is remapped onto /tf                                    /forklift/gz/tf_ground_truth -> /tf
ok    it is on its own bridge node, so it can be switched off    not mixed into the main bridge list
ok    the switch is a declared launch argument                   ground_truth_tf, default 'true' - set false when the EKF owns the edge
```

The last check in section 1 is the one worth naming: **no script in this
directory broadcasts a moving transform.** The only broadcaster in
`scripts/` is `sensor_tf.py`'s *static* one, and its children are the
three sensor links. Nothing here recomputes a pose.

### Regression: the sensor frames still agree

`check_sensor_frames.py --live --timeout 25`, section 6, unchanged by
this brief:

```
== 6. the running graph ====================================================
ok    /tf_static carries every sensor frame                      received: ['nav_lidar_link', 'safety_scanner_front_link', 'safety_scanner_rear_link']
ok    published transform for nav_lidar_link matches model.sdf   parent forklift/base_link d_xyz 0.00e+00 m d_quat 0.00e+00
ok    published transform for safety_scanner_front_link matches model.sdf parent forklift/base_link d_xyz 0.00e+00 m d_quat 0.00e+00
ok    published transform for safety_scanner_rear_link matches model.sdf parent forklift/base_link d_xyz 0.00e+00 m d_quat 0.00e+00
ok    tf2 resolves forklift/base_link -> nav_lidar_link          
ok    tf2 resolves forklift/base_link -> safety_scanner_front_link 
ok    tf2 resolves forklift/base_link -> safety_scanner_rear_link 
ok    /forklift/safety_scanner_front/measurement header.frame_id is the published frame safety_scanner_front_link vs safety_scanner_front_link
      /forklift/safety_scanner_front/measurement: 275 samples, [-137.5, +137.5] deg, range [0.10, 5.50] m
ok    /forklift/scan header.frame_id is the published frame      nav_lidar_link vs nav_lidar_link
      /forklift/scan: 360 samples, [-180.0, +180.0] deg, range [0.10, 8.00] m

RESULT: PASS (28 check(s), 0 failing)
```

---

## 6. The seam: where the EKF plugs in, demonstrated

This is the handover to the realistic-odometry brief, and it is a
**switch that was run**, not a plan that was written.

### What changes, in four lines

| | Today (phase 1) | After the EKF (phase 2) |
|---|---|---|
| Who publishes `odom → base_link` | `forklift_ground_truth_tf_bridge`, carrying `/forklift/gz/tf_ground_truth` | **the EKF node**, publishing `/tf` directly |
| How this one is retired | — | `ground_truth_tf:=false` on `vehicle.launch.py`. **No edit.** |
| What the EKF consumes | — | the IMU topic and the wheel odometry computed from `/forklift/joint_states` — **not** this ground-truth stream |
| What the ground-truth stream becomes | the estimate | the **reference**: `/forklift/gz/odom` → `/forklift/odom` keeps publishing, and localisation error is measured against it |

Nothing else moves. **The frame names do not change** — that is why
`<odom_frame>` and `<robot_base_frame>` are written explicitly in
`model.sdf` rather than left to defaults: the EKF takes over the same
edge, between the same two frames, and every consumer configuration
written today stays correct.

### The switch, run

Second launch of the identical stack with `ground_truth_tf:=false`:

`ros2 node list`

```
/forklift_bridge
/forklift_io
/obstacle_zone
/sensor_tf
```

`ros2 topic info /tf --verbose`

```
Unknown topic '/tf'
```

`ros2 run tf2_ros tf2_echo forklift/odom forklift/base_link`, 10 s:

```
[INFO] [tf2_echo]: Waiting for transform forklift/odom ->  forklift/base_link: Invalid frame ID "forklift/odom" passed to canTransform argument target_frame - frame does not exist
[INFO] [tf2_echo]: Waiting for transform forklift/odom ->  forklift/base_link: Invalid frame ID "forklift/odom" passed to canTransform argument target_frame - frame does not exist
[INFO] [tf2_echo]: Waiting for transform forklift/odom ->  forklift/base_link: Invalid frame ID "forklift/odom" passed to canTransform argument target_frame - frame does not exist
```

`check_odom_tf.py --live`, section 4 only:

```
== 4. the running graph ====================================================
FAIL  /tf carries forklift/odom -> forklift/base_link            0 transform(s) in the first 12 s
FAIL  the transform is published continuously                    fewer than two transforms received
ok    nothing else publishes on /tf                              one edge only
ok    the odometry topic names the same frames as the transform  forklift/odom -> forklift/base_link
FAIL  tf2 resolves forklift/odom -> forklift/base_link           "forklift/odom" passed to lookupTransform argument target_frame does not exist.
FAIL  tf2 resolves forklift/odom -> nav_lidar_link               "forklift/odom" passed to lookupTransform argument target_frame does not exist.
FAIL  tf2 resolves forklift/odom -> safety_scanner_front_link    "forklift/odom" passed to lookupTransform argument target_frame does not exist.
FAIL  tf2 resolves forklift/odom -> safety_scanner_rear_link     "forklift/odom" passed to lookupTransform argument target_frame does not exist.
ok    map is absent, as expected before SLAM runs                "map" passed to lookupTransform argument target_frame does not exist.
ok    the simulation clock reaches a consumer of this tree       node clock reads 61.796 s with use_sim_time - /clock is bridged
FAIL  a consumer on simulation time resolves it at "now"         "forklift/odom" passed to lookupTransform argument target_frame does not exist.
FAIL  the transform agrees with the odometry topic               no odometry sample could be paired with a transform

RESULT: FAIL (27 check(s), 8 failing)
```

**That FAIL is the evidence, and it is the intended result of this
capture.** With the switch off the edge is gone completely — no node, no
topic, no frame — so when the EKF publishes it, the EKF is the *only*
publisher and invariant 10 holds across the handover instead of being
argued about afterwards. The odometry *topic* is untouched by the switch
(`ok` on the frame-names line above): the reference survives, only the
transform is handed over. The same run is also the negative control for
every `ok` in §3 — those checks can fail, and they fail on exactly the
right rows.

---

## 7. What this does not establish

1. **Nothing about odometry realism.** This transform is ground truth. It
   has no drift, no slip and no noise, and it is **not** what the vehicle
   will run on after the next brief. Any localisation figure measured
   against it is measured against a perfect reference and must say so, or
   it is circular.
2. **Nothing about SLAM or Nav2.** No map was built and no localisation
   ran. What is established is that the *chain those need* resolves.
3. **Nothing about the `map` frame.** It does not exist, its name is not
   decided, and the four-vehicle case of M6 has not been considered here.
4. **Nothing about the owner's WSL host.** Container evidence only.
5. **No real-time factor, and no render-cost figure.** Deliberately not
   measured: another agent may be running the simulator.
6. **Nothing about `sim/`'s own launch files.**
   `sim/launch/forklift_bringup.launch.py` bridges `/forklift/gz/odom`
   but knows nothing of the transform topic, so a stack brought up
   through **that** file still has no `odom → base_link`. That is a
   request in `docs/reports/m5-07b-odom-tf.md`, not a change made here.
7. **Nothing about a fleet.** One vehicle, one tree. Four forklifts on
   one graph would each publish `nav_lidar_link` unprefixed, and that
   collision is unaddressed.
