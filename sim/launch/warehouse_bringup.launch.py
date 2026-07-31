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
# WHAT DELIBERATELY DOES NOT RUN HERE: the two vehicle nodes, the PLC, the
# bridge process, the HMI, and Nav2 / SLAM. Same list, same reasons, as
# forklift_bringup.launch.py. This file puts a plant and a vehicle on the
# wire; SLAM and Nav2 are m5-10 work and are launched separately against
# this world.
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
#   /forklift/joint_states                        sensor_msgs/JointState
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
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORLD = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'worlds', 'warehouse.sdf'))
_FORKLIFT_BRINGUP = os.path.join(_THIS_DIR, 'forklift_bringup.launch.py')

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

    return ld
