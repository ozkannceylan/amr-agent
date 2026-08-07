# warehouse_bringup.launch.py - M5 autonomy bringup for amr-agent.
#
# Starts sim/worlds/warehouse.sdf headless, spawns the in-house forklift
# (agv/forklift/model.sdf) into it and bridges the vehicle's topics.
#
# WHAT CHANGED, AND WHY THIS FILE IS A THIN WRAPPER.
#
#   This file used to spawn the Robotnik RB-KAIROS through that vendor's
#   spawn_robot.launch.py. RB-KAIROS is retired as the vehicle platform by
#   ADR 0010 D1, the vendor workspace is no longer provisioned by
#   sim/setup/install.sh, and the owner ruled on 2026-07-30 that M5's SLAM
#   and Nav2 autonomy runs in the warehouse world rather than in the M4
#   commissioning arena. So the vendor spawn path is gone and the vehicle
#   this file puts in the world is the forklift.
#
#   The bringup then becomes "the M4 forklift bringup, pointed at a
#   different world", and that is exactly what it is written as: it includes
#   forklift_bringup.launch.py and overrides the world and the spawn pose.
#   The alternative was a second copy of the bridge table, and a bridge
#   table that exists twice is a bridge table that drifts. There is ONE
#   topic contract for this vehicle (agv/forklift/README.md), one launch
#   file that states it (forklift_bringup.launch.py), and this file adds a
#   world and a place to stand.
#
#   Consequence worth knowing before debugging: every topic, remap and
#   parameter question about this launch is answered TWO files down, in
#   agv/forklift/launch/vehicle.launch.py and agv/forklift/config.yaml.
#   forklift_bringup.launch.py stopped stating a bridge table of its own on
#   2026-08-06, for the reason written in its header: its copy had drifted
#   off the actuator topics and produced a vehicle that was deaf at the
#   plant with a clean log.
#
# WHAT THIS FILE ADDS THAT THE M4 BRINGUP DOES NOT: THE ESTIMATOR STACK.
#
#   M5 is the gate where the vehicle localises itself, and a localisation
#   consumer needs a transform tree. So this file ASKS FOR four agv/-owned
#   processes that the M4 bringup leaves off, with `estimator:=true`:
#
#   IT NO LONGER STARTS THEM ITSELF, AND THAT CHANGED ON 2026-08-06.
#   Until then this file spawned the four processes with its own
#   ExecuteProcess and Node actions - a second copy of a process list that
#   agv/forklift/launch/vehicle.launch.py already stated, kept in step by
#   hand. That is the same shape as the bridge table this file had already
#   refused to copy, and the same shape as the one that made a vehicle deaf
#   at the plant when m5-50 moved the actuator topics and only one of the
#   two copies followed. So the copy is gone: `estimator` is passed down to
#   forklift_bringup.launch.py, which passes it to vehicle.launch.py, which
#   is the single place these four are declared, argued for and REFUSED in
#   their invalid combinations. The four are:
#
#     scripts/sensor_tf.py       /tf_static, one transform per sensor frame,
#                                read out of model.sdf so it cannot drift
#                                from the geometry
#     scripts/wheel_odometry.py  tricycle dead reckoning from the vehicle's
#                                own joint states. Publishes an Odometry
#                                message, a standstill verdict, and NO
#                                transform
#     scripts/imu_gate.py        the IMU as a ROTATION sensor: every sample
#                                forwarded unchanged onto
#                                /forklift/imu_gated EXCEPT while the wheel
#                                odometry reports both encoder counts held
#     robot_localization ekf_node with agv/forklift/ekf.yaml
#                                the fusion of those two, and THE SOLE
#                                PUBLISHER of
#                                forklift/odom -> forklift/base_link
#
#   THE GATE IS THE FOURTH PROCESS AND IT WAS MISSING UNTIL 2026-07-31.
#   It is not an optional refinement here: agv/forklift/ekf.yaml names
#   `imu0: /forklift/imu_gated`, which is a topic only imu_gate.py
#   publishes. Started without it, the EKF found no publisher on its IMU
#   input, logged nothing about it, and ran on wheel odometry alone - a
#   different estimator wearing the same node name, with the same single
#   /tf publisher and the same topic list. That is why there is NO
#   argument below that starts the EKF without the gate: `estimator`
#   starts all four or none. The one configuration in which the gate is
#   present and permanently ineffective (no wheel odometry, so no
#   standstill verdict, so a gate that fails open for ever) cannot be
#   asked for here either, because there is no argument for it.
#
#   WHAT THE GATE IS FOR, in one line, because a launch file should say
#   why it starts a process: a tricycle cannot rotate without its drive
#   wheel travelling, so a held encoder count bounds the body rotation at
#   0.0101 deg and a gyro reading taken in that condition is bias, not
#   rotation. Integrating it turned the m5-08b map 2.0 deg off the
#   building because the stack idled for twenty seconds before the drive
#   (docs/reports/m5-08c-slam-judge.md finding 1;
#   agv/forklift/EVIDENCE_ODOMETRY.md section 12 measures the fix at
#   0.0000 deg over both a 60 s and a 240 s idle).
#
#   THE GROUND-TRUTH TF BRIDGE IS NOT STARTED HERE AND HAS NO ARGUMENT.
#   agv/forklift/launch/vehicle.launch.py carries a switchable bridge for
#   the simulator's own odom -> base_link, retired 2026-07-31 and off by
#   default there; this file does not carry it at all. That is deliberate
#   and it is the strongest form of invariant 10 available to a launch
#   file: forklift_bringup.launch.py passes `ground_truth_tf:=false`
#   explicitly rather than inheriting a default, so the ONLY publisher of
#   that edge in this whole bringup is the EKF, and there is no argument
#   anyone can pass here to add a second one. A run of this
#   launch is expected to show `Publisher count: 1` on /tf until a mapping
#   or localisation node is started beside it (which then adds the DISJOINT
#   edge map -> forklift/odom, and nothing else).
#
#   ALL THREE CARRY use_sim_time EXPLICITLY. Every message in this stack is
#   stamped with the simulation clock; a node on the system clock
#   differences two clocks, asks tf2 for a transform ~1.8e9 s in the future
#   and is told the transform does not exist. That reads as a missing
#   publisher rather than as a misconfigured node and it is not a TF bug.
#   The same applies to anything launched BESIDE this file - SLAM, AMCL,
#   Nav2, a recorder - which is why sim/launch/warehouse_slam.launch.py
#   sets it too.
#
# WHAT DELIBERATELY DOES NOT RUN HERE: forklift_io.py and obstacle_zone.py
# (the two process nodes, which need the PLC path to be meaningful), the
# PLC, the bridge process, the HMI, Nav2 and SLAM. Same reasons as
# forklift_bringup.launch.py. This file puts a plant, a vehicle and the
# vehicle's own pose estimate on the wire; SLAM is launched separately
# against it by sim/launch/warehouse_slam.launch.py, and Nav2 is m5-10.
#
# THIS FILE CONTAINS NO CONTROL LOGIC. No sequencing, no interlock, no
# timer, no latch, no threshold. The protective stop is onboard and
# hardwired and appears in no launch file (invariant 1).
#
# Topics (authoritative table: agv/forklift/README.md):
#
#   /clock                                        rosgraph_msgs/Clock
#   /forklift/gz/actuator/{steer,traction,fork}_cmd  std_msgs/Float64  (in)
#       THE ACTUATOR TERMINALS, which is what model.sdf's joint controllers
#       listen on since m5-50. They are NOT what a vehicle node publishes:
#       the stack still publishes /forklift/gz/{steer,traction,fork}_cmd and
#       agv/forklift/scripts/sto_contactor.py is the only thing that joins
#       the two. A gz topic list therefore shows the terminals and never the
#       commands, which is the right way round.
#   /forklift/scan                                sensor_msgs/LaserScan
#       the NAVIGATION lidar, 360 ranges over 360 deg, 10 Hz, z = 1.80 m
#   /forklift/safety_scanner_front/measurement    sensor_msgs/LaserScan
#   /forklift/safety_scanner_rear/measurement     sensor_msgs/LaserScan
#       the two safety scanners' NON-SAFE measurement channels, z = 0.15 m.
#       Neither is a safe channel; the safe channel has no topic on either
#       transport, ever (agv/forklift/README.md)
#   /forklift/odom                                nav_msgs/Odometry, 20 Hz
#       GROUND TRUTH. The name does not say so; agv/forklift/config.yaml
#       has the standing rename request. Nothing that estimates or maps
#       may read it.
#   /forklift/joint_states                        sensor_msgs/JointState
#   /forklift/imu                                 sensor_msgs/Imu, 100 Hz
#   /forklift/odom_wheel                          nav_msgs/Odometry, 50 Hz
#       one sensor's opinion, no transform
#   /forklift/wheel_standstill                    std_msgs/Bool, 50 Hz
#       the wheel odometry's own verdict: both encoder counts unchanged
#   /forklift/imu_gated                           sensor_msgs/Imu, <= 100 Hz
#       the IMU as a rotation sensor. THE TOPIC ekf.yaml FUSES
#   /forklift/odom_filtered                       nav_msgs/Odometry, 50 Hz
#       THE ESTIMATE, and the owner of odom -> base_link
#   /tf                                           tf2_msgs/TFMessage
#       forklift/odom -> forklift/base_link, from the EKF and nothing else
#   /tf_static                                    tf2_msgs/TFMessage
#       base_link -> the four sensor frames, from sensor_tf.py
#
# Usage (after sourcing /opt/ros/jazzy/setup.bash). Isolate BOTH transports
# whenever another simulation may be running: ROS_DOMAIN_ID does not isolate
# Gazebo, because gz transport does not use DDS. GZ_PARTITION does.
#
#   export GZ_PARTITION=myrun ROS_DOMAIN_ID=42
#   ros2 launch /path/to/sim/launch/warehouse_bringup.launch.py
#   ros2 launch /path/to/sim/launch/warehouse_bringup.launch.py gui:=true
#   ros2 launch /path/to/sim/launch/warehouse_bringup.launch.py x:=-9.80 y:=-7.70
#
# The check that this file works is `ros2 topic hz` on each bridged ROS
# topic, never a clean-looking log: a ros_gz_bridge entry for a gz topic
# that nobody publishes logs `Creating GZ->ROS Bridge` exactly as a working
# one does (sim/setup/CONTAINER_TOOLCHAIN.md section 6).

import os

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORLD = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'worlds', 'warehouse.sdf'))
_FORKLIFT_BRINGUP = os.path.join(_THIS_DIR, 'forklift_bringup.launch.py')

# NO agv/ PATH IS RESOLVED HERE ANY MORE. The model, the config, the three
# scripts and ekf.yaml were named in this file until 2026-08-06, which made
# it a second place that had to know where agv/ keeps things. It now names
# exactly one path, the M4 bringup beside it, and every agv/ path is
# resolved by agv/forklift/launch/vehicle.launch.py from its own location.

# Spawn pose. The dock aisle south of rack row C runs along y = -5.50, and
# the vehicle stands in it facing +x, with the central cross aisle ahead and
# both charging bays behind its right shoulder. Overridable per run: a
# scenario that wants a different start pose passes it rather than editing
# this file.
#
# x WAS -6.00 UNTIL m5-69, AND -6.00 IS A POSE NO MISSION CAN START FROM.
#
#   The world is open there - the argument this comment used to make, that
#   the plan envelope x in [-7.875, -5.140] y in [-6.020, -4.980] is clear
#   of rack row C's south face, of the column at (-4.60, -7.00) and of both
#   charge-bay outlines, is still TRUE OF THE WORLD. It was the wrong
#   question. Nav2 does not plan against sim/worlds/warehouse.sdf. It plans
#   against sim/maps/warehouse/warehouse.pgm, the SLAM grid, and THE GRID
#   DOES NOT COVER THAT CORNER: 21.6 % of it is unmapped, and the dock
#   aisle's mapped free space begins at x = -5.00. At x = -6.00 the
#   vehicle's padded footprint outline crosses 36 unmapped cells and its
#   inscribed circle has 0.430 m of clearance against a 0.769 m inscribed
#   radius, so the pose is invalid at 55 of 72 headings and fits at NONE.
#
#   Measured, not argued: `nav2_run.py plan` against a bare map_server and
#   planner_server returns 205 START_OCCUPIED in 0.014 s from (-6.00,
#   -5.50) and SUCCEEDED in 0.007 s from the pose below. m5-68's mission
#   attempt is that refusal, seen from the far end as 0 plans in 100 s.
#   The full geometry is agv/forklift/EVIDENCE_NAV2.md section 13 and is
#   re-derivable with
#
#     python3 agv/forklift/scripts/start_pose_check.py pose --x -6 --y -5.5
#
#   x = -3.00 is chosen for MARGIN, not for the shortest move that works.
#   It stands 2.00 m east of the first valid pose in this aisle, carries
#   1.972 m of inscribed clearance - the local maximum along y = -5.50 -
#   and lies in the grid's one large passable component, so it is not a
#   pose a 0.661 m localisation excursion can push back out of the map.
#   THE PLANNER'S allow_unknown STAYS false. Moving the vehicle into the
#   mapped building is the fix; letting it plan through space nothing has
#   ever seen is a different decision and not this file's to take.
_SPAWN_X = '-3.00'
_SPAWN_Y = '-5.50'
_SPAWN_Z = '0.05'
_SPAWN_YAW = '0.0'


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'world', default_value=_DEFAULT_WORLD,
        description='Absolute path to the warehouse world SDF file'))
    ld.add_action(DeclareLaunchArgument(
        'name', default_value='Forklift',
        description='Name the model is spawned under'))
    ld.add_action(DeclareLaunchArgument(
        'x', default_value=_SPAWN_X, description='Spawn x [m]'))
    ld.add_action(DeclareLaunchArgument(
        'y', default_value=_SPAWN_Y, description='Spawn y [m]'))
    ld.add_action(DeclareLaunchArgument(
        'z', default_value=_SPAWN_Z, description='Spawn z [m]'))
    ld.add_action(DeclareLaunchArgument(
        'yaw', default_value=_SPAWN_YAW, description='Spawn yaw [rad]'))
    ld.add_action(DeclareLaunchArgument(
        'gui', default_value='false',
        description='Also start the Gazebo GUI client (headless if false)'))
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Run the bridge on simulation time from /clock'))
    ld.add_action(DeclareLaunchArgument(
        'seed', default_value='',
        description='Noise seed passed to gz sim, fixing the sign and value '
                    'each sensor bias is drawn with, so a before-and-after '
                    'measurement compares two runs of one vehicle rather '
                    'than two draws. Empty (the default) leaves the draw '
                    'random, which is what a real device does and what every '
                    'demonstration uses. Added 2026-08-06: its absence is '
                    'why m5-10\'s forward control was handed 8x more heading '
                    'drift than its reverse pass and the confound had to be '
                    'named instead of removed.'))
    ld.add_action(DeclareLaunchArgument(
        'estimator', default_value='true',
        description='Start the vehicle\'s own pose estimate: sensor_tf.py, '
                    'wheel_odometry.py, imu_gate.py and the '
                    'robot_localization EKF. ALL FOUR OR NONE - the EKF '
                    'fuses /forklift/imu_gated, which only imu_gate.py '
                    'publishes, and imu_gate.py gates on a verdict only '
                    'wheel_odometry.py publishes, so a partial start is a '
                    'silently different estimator. The EKF is the sole '
                    'publisher of forklift/odom -> forklift/base_link and '
                    'there is no argument here that adds a second one. Set '
                    'false only to bring up the bare plant, which then has '
                    'no transform tree and cannot carry SLAM, AMCL or '
                    'Nav2.'))

    # THE ONE INCLUDE, AND THE WHOLE OF THIS FILE'S BODY. The M4 bringup
    # carries the world server, the single spawn, the one bridge that states
    # the vehicle's topic contract, the STO contactor and the four estimator
    # processes. Everything this file adds is which world, where to stand,
    # and that an M5 run wants the estimator.
    #
    # Scoped, because IncludeLaunchDescription does not scope launch
    # configurations and DeclareLaunchArgument skips its default when the
    # configuration is already set (docs/LESSONS.md 2026-08-05). Every
    # argument the include is meant to receive is listed explicitly.
    #
    # `sto_contactor` is NOT passed and is not declared here. It defaults
    # true in the M4 bringup, and a launch file whose purpose is autonomy
    # has no business offering an argument that makes the plant unreachable.
    ld.add_action(GroupAction(
        scoped=True,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(_FORKLIFT_BRINGUP),
            launch_arguments={
                'world': LaunchConfiguration('world'),
                'name': LaunchConfiguration('name'),
                'x': LaunchConfiguration('x'),
                'y': LaunchConfiguration('y'),
                'z': LaunchConfiguration('z'),
                'yaw': LaunchConfiguration('yaw'),
                'gui': LaunchConfiguration('gui'),
                'seed': LaunchConfiguration('seed'),
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'estimator': LaunchConfiguration('estimator'),
            }.items(),
        )],
    ))

    return ld
