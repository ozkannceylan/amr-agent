# CELL_EVIDENCE.md — verified headless run of the M3 demonstration cell

Date of run: **2026-07-27** (08:09:33 UTC)
Host: Linux 6.18.5 x86_64, container, CPU only, **no display**
ROS 2 Jazzy, Gazebo Sim 8.11.0 (Harmonic, `ros-jazzy-gz-sim-vendor`), Python 3.12.3

Everything below is copied from one continuous run of

```
source /opt/ros/jazzy/setup.bash
ros2 launch /home/user/amr-agent/sim/launch/cell_bringup.launch.py
```

with a scratch sampler node driving the commands. The sampler is a test
stimulus, not part of the cell: it holds persistent publishers on
`/cell/conveyor/cmd_speed` and the three `/cell/panel/*` contacts and
persistent subscribers on the state topics, so nothing in the capture
depends on late-joining discovery. Every command it sends is a plain
`std_msgs` publish that a human can reproduce with `ros2 topic pub`.

Summary of the four required checks:

| Check | Result |
|---|---|
| World spawns headless with no ERROR lines | PASS — 0 error lines, 0 warning lines |
| ROS 2 conveyor command visibly moves the product | PASS — box travelled −1.000 m → +0.654 m, then reversed |
| Product sensor changes state on arrival AND on departure | PASS — 1.440 m → 0.540 m → 1.440 m, plus a reverse re-block |
| Start / Stop / process-stop topics exist and accept publishes | PASS — all three echoed back on both the ROS and the gz side |

---

## 1. Bringup

```
$ ros2 launch /home/user/amr-agent/sim/launch/cell_bringup.launch.py
(bringup ready after 2 s wall clock)

$ gz model --list

Requesting state for world [cell]...

Available models:
    - Floor
    - Conveyor
    - ProductBox
    - ProductSensor
    - SensorReflector
    - OperatorPanel
```

No vehicle model is present, by design (ADR 0004).

```
$ ros2 topic list
/cell/conveyor/cmd_speed
/cell/conveyor/joint_state
/cell/panel/process_stop
/cell/panel/start
/cell/panel/stop
/cell/product_box/pose
/cell/product_sensor/scan
/clock
/parameter_events
/rosout
```

Types and bridge direction. A cell→PLC signal shows the bridge as the
publisher; a PLC→cell signal shows the bridge as the subscriber.

```
$ ros2 topic info <each cell topic>
--- /cell/conveyor/cmd_speed
Type: std_msgs/msg/Float64
Publisher count: 0
Subscription count: 1
--- /cell/conveyor/joint_state
Type: sensor_msgs/msg/JointState
Publisher count: 1
Subscription count: 0
--- /cell/product_sensor/scan
Type: sensor_msgs/msg/LaserScan
Publisher count: 1
Subscription count: 0
--- /cell/panel/start
Type: std_msgs/msg/Bool
Publisher count: 0
Subscription count: 1
--- /cell/panel/stop
Type: std_msgs/msg/Bool
Publisher count: 0
Subscription count: 1
--- /cell/panel/process_stop
Type: std_msgs/msg/Bool
Publisher count: 0
Subscription count: 1
--- /cell/product_box/pose
Type: geometry_msgs/msg/PoseArray
Publisher count: 1
Subscription count: 0
--- /clock
Type: rosgraph_msgs/msg/Clock
Publisher count: 1
Subscription count: 0
```

## 2. Message shapes, belt clear

These are the exact payloads the m3-04 bridge will read. Note that the
product sensor publishes a **range**, not a detected bit.

```
$ ros2 topic echo /cell/product_sensor/scan --once
header:
  stamp:
    sec: 5
    nanosec: 942000000
  frame_id: ProductSensor/post/beam
angle_min: 0.0
angle_max: 0.0
angle_increment: .nan
time_increment: 0.0
scan_time: 0.0
range_min: 0.05000000074505806
range_max: 3.0
ranges:
- 1.4400883913040161
intensities:
- 0.0
---
$ ros2 topic echo /cell/conveyor/joint_state --once
header:
  stamp:
    sec: 6
    nanosec: 904000000
  frame_id: ''
name:
- belt_joint
position:
- 2.6360220287926264e-22
velocity:
- -2.5662092570399454e-29
effort:
- 0.0
---
$ ros2 topic echo /cell/product_box/pose --once
header:
  stamp:
    sec: 7
    nanosec: 900000000
  frame_id: cell
poses:
- position:
    x: -1.0
    y: 1.4350543815152838e-21
    z: 0.6099999996080039
  orientation:
    x: 7.8081214023154e-21
    y: 1.1070482727764305e-21
    z: 4.104340941157815e-21
    w: 1.0
---
```

`angle_increment: .nan` is expected for a single-sample lidar (Gazebo divides
the zero angular span by zero remaining samples). Only `ranges[0]` is used.

## 3. Publish rates

```
$ ros2 topic hz /cell/product_sensor/scan
average rate: 30.234
	min: 0.027s max: 0.039s std dev: 0.00137s window: 279
average rate: 30.227
	min: 0.027s max: 0.039s std dev: 0.00137s window: 310
$ ros2 topic hz /cell/conveyor/joint_state
average rate: 498.886
	min: 0.000s max: 0.016s std dev: 0.00031s window: 5001
average rate: 498.499
	min: 0.000s max: 0.016s std dev: 0.00037s window: 5496
$ ros2 topic hz /cell/product_box/pose
average rate: 9.979
	min: 0.099s max: 0.110s std dev: 0.00117s window: 96
average rate: 9.982
	min: 0.099s max: 0.110s std dev: 0.00111s window: 107
```

The belt encoder runs at the physics rate (500 Hz) because gz's
`JointStatePublisher` has no rate parameter. Decimating it to the PLC scan
rate is the bridge's decision, not the world's.

## 4. Operator panel contacts, ROS → gz round trip

gz-side listeners were attached **before** any publish:

```
$ stdbuf -oL gz topic -e -t /cell/panel/start          (background)
$ stdbuf -oL gz topic -e -t /cell/panel/stop           (background)
$ stdbuf -oL gz topic -e -t /cell/panel/process_stop   (background)
```

Each contact was then toggled true → false from a persistent ROS publisher
and read back on the ROS side:

```
  step  contact        published   ROS readback
  ----------------------------------------------------
     1  start          True        start=True
     2  start          False       start=False
     3  stop           True        stop=True
     4  stop           False       stop=False
     5  process_stop   True        process_stop=True
     6  process_stop   False       process_stop=False
```

The same two values arrived on the Gazebo side of the bridge. gz prints an
empty message for a `false` proto3 field, so each capture is `data: true`
followed by a blank message:

```
--- gz topic -e -t /cell/panel/start
    data: true

--- gz topic -e -t /cell/panel/stop
    data: true

--- gz topic -e -t /cell/panel/process_stop
    data: true

```

`/cell/panel/process_stop` is a **process** stop. It is not a safety
function and is not part of any safety chain (invariant 1, ADR 0004).

## 5. Conveyor transport and product sensor transitions

`beltPos`/`beltVel` are `/cell/conveyor/joint_state`, `range` is
`/cell/product_sensor/scan` `ranges[0]`, `boxX` is
`/cell/product_box/pose`. Every `-->` line is a `std_msgs/Float64` publish
on `/cell/conveyor/cmd_speed`.

```
sim_t[s]  beltPos[m]  beltVel[m/s]  range[m]   boxX[m]   event
------------------------------------------------------------------------------
  69.578     0.000      0.000      1.440    -1.000   idle, belt clear
--> ros2 publish /cell/conveyor/cmd_speed = 0.15
  72.588     0.451      0.150      1.440    -0.563   running forward
  75.594     0.902      0.150      1.440    -0.113   running forward
  78.602     1.353      0.150      0.540     0.352   BEAM BLOCKED  product entered the beam
  80.608     1.654      0.150      1.440     0.652   BEAM CLEAR    product left the beam
--> ros2 publish /cell/conveyor/cmd_speed = 0.0
  83.608     1.654      0.000      1.440     0.654   belt stopped
--> ros2 publish /cell/conveyor/cmd_speed = -0.15 (reverse)
  83.808     1.624     -0.150      0.540     0.626   BEAM BLOCKED  product re-entered the beam in reverse
  86.810     1.624     -0.000      0.540     0.624   belt stopped, product standing in the beam
RESULT: forward_block=True forward_clear=True reverse_block=True -> PASS
```

What this shows, line by line:

- The belt only moves after a ROS 2 command arrives, and it stops when
  `0.0` is commanded. Commanded 0.15 m/s, measured `beltVel` 0.150 m/s.
- The product is **carried** by the belt, not teleported: `boxX` tracks
  `beltPos` with a constant −1.00 m offset for the whole run, i.e. the box
  rides the belt without slipping.
- The beam reads **1.440 m** clear (emitter to reflector) and **0.540 m**
  blocked (emitter to the near face of the box). Both the falling and the
  rising transition are captured.
- Reversing the sign of the same command reverses transport and drives the
  beam back into the blocked state, so the command is a signed raw
  velocity with no direction logic in the world.

## 6. Simulation performance

```
$ gz topic -e -t /stats -n 1
sim_time {
  sec: 90
  nsec: 96000000
}
real_time {
  sec: 93
  nsec: 64322126
}
iterations: 45048
real_time_factor: 1.0015142896058842
step_size {
  nsec: 2000000
}
```

Real time factor ≈ 1.0 headless, 2 ms fixed step. Unlike
`warehouse.sdf` (~0.1 RTF), this world renders one single-ray lidar
instead of two 270-sample scanners and an RGBD camera, so it runs at
wall-clock speed. That matters for M3: latency measured against this
world is not distorted by a slow simulator.

## 7. Log hygiene

```
error lines in the launch log:  0
warning lines in the launch log: 0
```

Clean start, no SDF warnings, no missing-plugin messages.
