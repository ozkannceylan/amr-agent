# M3 bringup evidence

Date: 2026-07-26. Host: project container, Ubuntu 24.04, ROS 2 Jazzy,
Gazebo Harmonic (gz-sim-vendor), headless (no GPU, ogre2 on CPU).

Command under test:

```
source /opt/ros/jazzy/setup.bash
source /opt/m3-feasibility/ws/install/setup.bash
ros2 launch /home/user/amr-agent/sim/launch/warehouse_bringup.launch.py
```

## 1. Robot entity created in the world

`gz model --list` against the running server:

```
Available models:
    - Floor
    - WallNorth
    - WallSouthWest
    - WallSouthEast
    - WallEast
    - WallWest
    - DoorGap
    - RackA1
    - RackA2
    - RackA3
    - RackB1
    - RackB2
    - RackB3
    - ConveyorStation
    - ChargerStation
    - robot
```

Launch log (no `[ERROR]` / `process has died` lines in the whole log):

```
[spawner-6] Configured and activated joint_state_broadcaster
[spawner-6] Configured and activated robotnik_base_control
```

`ros2 control list_controllers -c /robot/controller_manager`:

```
robotnik_base_control   robotnik_controllers/RBKairosController        active
joint_state_broadcaster joint_state_broadcaster/JointStateBroadcaster  active
```

## 2. /clock ticking

`ros2 topic echo /clock --once`:

```
clock:
  sec: 4
  nanosec: 260000000
```

`ros2 topic hz /clock` showed ~6 Hz wall-time (sim publishes one clock
message per 20 ms sim step, i.e. real-time factor ~0.12 with all sensors
rendered on CPU). Sim time advances monotonically.

## 3. /scan publishing (front safety lidar)

`ros2 topic echo /robot/front_laser/scan --once`:

```
header:
  stamp: {sec: 4, nanosec: 560000000}
  frame_id: robot_front_laser_link
angle_min: -2.0999999046325684
angle_max: 2.0999999046325684
angle_increment: 0.015613382682204247
range_min: 0.05000000074505806
range_max: 10.0
ranges:
- 9.961706161499023
...
```

Finite ranges < range_max confirm the gpu_lidar is actually rendering
against the warehouse geometry (walls/racks), not returning empty scans.
`/robot/rear_laser/scan` is bridged by the same vendor bridge.

## 4. /odom present and closed-loop drive test

Topic list (excerpt):

```
/clock
/robot/front_laser/scan
/robot/rear_laser/scan
/robot/joint_states
/robot/robotnik_base_control/cmd_vel
/robot/robotnik_base_control/cmd_vel_unstamped
/robot/robotnik_base_control/odom
/tf
/tf_static
```

Initial odom: `position.x: 0.0`. After publishing
`geometry_msgs/Twist {linear: {x: 0.5}}` at 10 Hz on
`/robot/robotnik_base_control/cmd_vel_unstamped` for 40 s wall time:

```
header:
  stamp: {sec: 16, nanosec: 160000000}
  frame_id: robot_odom
child_frame_id: robot_base_footprint
pose.pose.position:
  x: 2.628239999933924
  y: 5.7e-08
```

The mecanum base moves under ros2_control (gz_ros2_control +
robotnik_controllers) and odometry integrates. `/tf` carries
robot_base_link -> wheel transforms from joint_state_broadcaster.
