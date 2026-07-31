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
#   parameter question about this launch is answered in
#   forklift_bringup.launch.py, including the note on why the rear safety
#   scanner's measurement channel is deliberately not bridged.
#
# WHAT THIS FILE ADDS THAT THE M4 BRINGUP DOES NOT: THE ESTIMATOR STACK.
#
#   M5 is the gate where the vehicle localises itself, and a localisation
#   consumer needs a transform tree. So this file additionally starts three
#   agv/-owned processes, exactly as agv/forklift/launch/vehicle.launch.py
#   starts them:
#
#     scripts/sensor_tf.py       /tf_static, one transform per sensor frame,
#                                read out of model.sdf so it cannot drift
#                                from the geometry
#     scripts/wheel_odometry.py  tricycle dead reckoning from the vehicle's
#                                own joint states. Publishes an Odometry
#                                message and NO transform
#     robot_localization ekf_node with agv/forklift/ekf.yaml
#                                the fusion of that with the IMU, and THE
#                                SOLE PUBLISHER of
#                                forklift/odom -> forklift/base_link
#
#   THE GROUND-TRUTH TF BRIDGE IS NOT STARTED HERE AND HAS NO ARGUMENT.
#   agv/forklift/launch/vehicle.launch.py carries a switchable bridge for
#   the simulator's own odom -> base_link, retired 2026-07-31 and off by
#   default there; this file does not carry it at all. That is deliberate
#   and it is the strongest form of invariant 10 available to a launch
#   file: the M4 launch this one includes bridges no transform either, so
#   the ONLY publisher of that edge in this whole bringup is the EKF, and
#   there is no argument anyone can pass to add a second one. A run of this
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
#   /forklift/gz/steer_cmd, traction_cmd, fork_cmd  std_msgs/Float64  (in)
#   /forklift/scan                                sensor_msgs/LaserScan
#       the NAVIGATION lidar, 360 ranges over 360 deg, 10 Hz, z = 1.80 m
#   /forklift/safety_scanner_front/measurement    sensor_msgs/LaserScan
#       the front safety scanner's NON-SAFE measurement channel, z = 0.15 m
#   /forklift/odom                                nav_msgs/Odometry, 20 Hz
#       GROUND TRUTH. The name does not say so; agv/forklift/config.yaml
#       has the standing rename request. Nothing that estimates or maps
#       may read it.
#   /forklift/joint_states                        sensor_msgs/JointState
#   /forklift/imu                                 sensor_msgs/Imu, 100 Hz
#   /forklift/odom_wheel                          nav_msgs/Odometry, 50 Hz
#       one sensor's opinion, no transform
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
import sys

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            IncludeLaunchDescription)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..'))
_DEFAULT_WORLD = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'worlds', 'warehouse.sdf'))
_FORKLIFT_BRINGUP = os.path.join(_THIS_DIR, 'forklift_bringup.launch.py')

# The estimator is agv/'s, in every file. This launch starts it; it does not
# own it, does not copy a parameter out of it and does not restate a frame
# name. If any of the four paths below stops existing, that is agv/'s change
# to make and this file's to follow.
_FORKLIFT_DIR = os.path.join(_REPO_ROOT, 'agv', 'forklift')
_MODEL_SDF = os.path.join(_FORKLIFT_DIR, 'model.sdf')
_CONFIG_YAML = os.path.join(_FORKLIFT_DIR, 'config.yaml')
_TF_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'sensor_tf.py')
_WHEEL_ODOM_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'wheel_odometry.py')
_EKF_YAML = os.path.join(_FORKLIFT_DIR, 'ekf.yaml')

# Spawn pose. The dock aisle south of rack row C runs along y = -5.50; x =
# -6.00 puts the vehicle in the open west half of it, facing +x, with the
# central cross aisle ahead and both charging bays behind its right shoulder.
# The vehicle's plan envelope there is x in [-7.875, -5.140], y in [-6.020,
# -4.980]: clear of rack row C's south face at y = -3.80, of the building
# column at (-4.60, -7.00) and of both charge bay outlines, which end at
# y = -6.10 and are paint in any case. Overridable per run: a scenario that
# wants a different start pose passes it rather than editing this file.
_SPAWN_X = '-6.00'
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
        'estimator', default_value='true',
        description='Start the vehicle\'s own pose estimate: sensor_tf.py, '
                    'wheel_odometry.py and the robot_localization EKF. The '
                    'EKF is the sole publisher of forklift/odom -> '
                    'forklift/base_link and there is no argument here that '
                    'adds a second one. Set false only to bring up the bare '
                    'plant, which then has no transform tree and cannot '
                    'carry SLAM, AMCL or Nav2.'))

    # The M4 bringup carries the world server, the single spawn and the one
    # bridge that states the vehicle's whole topic contract. Everything this
    # file adds is which world and where to stand.
    ld.add_action(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(_FORKLIFT_BRINGUP),
        launch_arguments={
            'world': LaunchConfiguration('world'),
            'name': LaunchConfiguration('name'),
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'z': LaunchConfiguration('z'),
            'yaw': LaunchConfiguration('yaw'),
            'gui': LaunchConfiguration('gui'),
            'use_sim_time': LaunchConfiguration('use_sim_time'),
        }.items(),
    ))

    # ---- the vehicle's own motion estimate, three processes ----
    #
    # Started here and owned by agv/. The two scripts are invoked with the
    # interpreter running this launch file, which is /usr/bin/python3 under
    # `ros2 launch`; the container's /usr/local/bin/python3 is 3.11 and has
    # no rclpy (sim/setup/CONTAINER_TOOLCHAIN.md section 3.3).
    #
    # use_sim_time is passed to all three and is not optional. See the
    # header.
    estimator = LaunchConfiguration('estimator')

    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _TF_SCRIPT, '--model', _MODEL_SDF],
        name='sensor_tf',
        output='screen',
        condition=IfCondition(estimator),
    ))
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _WHEEL_ODOM_SCRIPT, '--config', _CONFIG_YAML,
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='wheel_odometry',
        output='screen',
        condition=IfCondition(estimator),
    ))
    ld.add_action(Node(
        package='robot_localization',
        executable='ekf_node',
        name='forklift_ekf',
        output='screen',
        parameters=[_EKF_YAML, {'use_sim_time': True}],
        remappings=[('odometry/filtered', '/forklift/odom_filtered')],
        condition=IfCondition(estimator),
    ))

    return ld
