# vehicle.launch.py - bring up one simulated forklift and its vehicle nodes.
#
# What this launch starts:
#   1. the Gazebo (gz sim) server on a world, headless by default,
#   2. one spawn of agv/forklift/model.sdf into that world,
#   3. one ros_gz_bridge carrying every topic this directory owns,
#   4. scripts/forklift_io.py and scripts/obstacle_zone.py.
#
# THE WORLD IS NOT OWNED HERE. agv/ owns a vehicle, not a warehouse, so the
# world is an argument. Its default is gz's stock empty.sdf, which is enough
# to drive and lift but has NO gz-sim-sensors-system, so the scanner stays
# silent on it. Any world that must produce /forklift/scan has to load
#
#   <plugin filename="gz-sim-sensors-system"
#           name="gz::sim::systems::Sensors">
#     <render_engine>ogre2</render_engine>
#   </plugin>
#
# exactly as sim/worlds/cell.sdf does. EVIDENCE_MODEL.md quotes the minimal
# world used to verify the scanner. The model now carries THREE gpu_lidars,
# so a world without that plugin loses all three at once, and a world with
# it pays for all three.
#
# NO CONTROL LOGIC LIVES HERE. The bridge is a type translator and this file
# is process wiring. Sequencing, interlocks and stop decisions belong to the
# PLC and to the fleet layer (invariants 5, 6 and 9), and the protective
# stop is onboard and hardwired and appears in no launch file (invariant 1).
#
# Every topic name below is read from config.yaml. None is written here, so
# the contract table in README.md has one source.
#
# Usage (after sourcing /opt/ros/jazzy/setup.bash), isolating both
# transports as docs/LESSONS.md requires when a simulation may already run:
#
#   GZ_PARTITION=myrun ROS_DOMAIN_ID=61 \
#     ros2 launch agv/forklift/launch/vehicle.launch.py
#   GZ_PARTITION=myrun ROS_DOMAIN_ID=61 \
#     ros2 launch agv/forklift/launch/vehicle.launch.py world:=/path/to/world.sdf

import os
import sys

import yaml

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            IncludeLaunchDescription)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

# This directory ships the model, the constants and the two scripts, so
# resolve all four from this file rather than from a package share path.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_MODEL_SDF = os.path.join(_FORKLIFT_DIR, 'model.sdf')
_CONFIG_YAML = os.path.join(_FORKLIFT_DIR, 'config.yaml')
_IO_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'forklift_io.py')
_ZONE_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'obstacle_zone.py')

with open(_CONFIG_YAML, 'r', encoding='utf-8') as _handle:
    _CFG = yaml.safe_load(_handle)

_TOPICS = _CFG['topics']
_SPAWN = _CFG['spawn']

# gz topic name -> ROS message type -> gz message type.
#   '['  gz to ROS   (feedback the vehicle reads)
#   ']'  ROS to gz   (raw joint command the model consumes)
_BRIDGE_ARGS = [
    '{}@rosgraph_msgs/msg/Clock[gz.msgs.Clock'.format(_TOPICS['clock']),

    '{}@std_msgs/msg/Float64]gz.msgs.Double'.format(_TOPICS['gz_steer_cmd']),
    '{}@std_msgs/msg/Float64]gz.msgs.Double'.format(_TOPICS['gz_traction_cmd']),
    '{}@std_msgs/msg/Float64]gz.msgs.Double'.format(_TOPICS['gz_fork_cmd']),

    '{}@sensor_msgs/msg/JointState[gz.msgs.Model'.format(_TOPICS['gz_joint_state']),
    '{}@nav_msgs/msg/Odometry[gz.msgs.Odometry'.format(_TOPICS['gz_odom']),
    '{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'.format(_TOPICS['gz_scan_nav']),
]

# The two safety scanners are NOT in the list above and that is deliberate.
# They model a device whose real output is an OSSD pair on copper, and the
# simulation analogue of that path is the PLCSIM Advanced API into the
# F-program (ADR 0011 decision 2), not a ROS topic. Bridging them would put
# a safety device's measurement channel on the process network, where any
# node could subscribe and quietly become a consumer of it. Their gz topic
# names are still a contract and still live in config.yaml.

# Feedback keeps the gz name on the gz side and gets the vehicle-facing name
# on the ROS side. Commands are NOT remapped: the same name on both sides is
# what makes them recognisable as the model's raw inputs.
_BRIDGE_REMAPS = [
    (_TOPICS['gz_joint_state'], _TOPICS['joint_states']),
    (_TOPICS['gz_odom'], _TOPICS['odom']),
    (_TOPICS['gz_scan_nav'], _TOPICS['scan']),
]


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'world', default_value='empty.sdf',
        description='World the vehicle is spawned into. A bare name is '
                    'resolved from the gz resource path; a path is used as '
                    'given. The world must load gz-sim-sensors-system for '
                    'the scanner to publish.'))
    ld.add_action(DeclareLaunchArgument(
        'world_name', default_value='',
        description='Name of the <world> element. Empty lets the spawn '
                    'discover it from the running server.'))
    ld.add_action(DeclareLaunchArgument(
        'model', default_value=_MODEL_SDF,
        description='Absolute path to the forklift model SDF'))
    ld.add_action(DeclareLaunchArgument(
        'config', default_value=_CONFIG_YAML,
        description='Absolute path to the named-constant file'))
    ld.add_action(DeclareLaunchArgument(
        'name', default_value=_CFG['model']['name'],
        description='Name the model is spawned under'))
    ld.add_action(DeclareLaunchArgument(
        'x', default_value=str(_SPAWN['x_m']), description='Spawn x [m]'))
    ld.add_action(DeclareLaunchArgument(
        'y', default_value=str(_SPAWN['y_m']), description='Spawn y [m]'))
    ld.add_action(DeclareLaunchArgument(
        'z', default_value=str(_SPAWN['z_m']), description='Spawn z [m]'))
    ld.add_action(DeclareLaunchArgument(
        'yaw', default_value=str(_SPAWN['yaw_rad']), description='Spawn yaw [rad]'))
    ld.add_action(DeclareLaunchArgument(
        'gui', default_value='false',
        description='Also start the Gazebo GUI client (headless if false)'))
    ld.add_action(DeclareLaunchArgument(
        'server', default_value='true',
        description='Start the gz server here. Set false to spawn into a '
                    'server someone else already started.'))
    ld.add_action(DeclareLaunchArgument(
        'nodes', default_value='true',
        description='Start forklift_io and obstacle_zone'))

    world = LaunchConfiguration('world')
    world_name = LaunchConfiguration('world_name')
    model = LaunchConfiguration('model')
    config = LaunchConfiguration('config')
    name = LaunchConfiguration('name')
    gui = LaunchConfiguration('gui')
    server = LaunchConfiguration('server')
    nodes = LaunchConfiguration('nodes')

    ros_gz_sim_launch = os.path.join(
        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')

    # Gazebo server, headless, running immediately (-r -s).
    ld.add_action(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ros_gz_sim_launch),
        launch_arguments={
            'gz_args': ['-r -s ', world],
            'on_exit_shutdown': 'true',
        }.items(),
        condition=IfCondition(server),
    ))

    # Optional GUI client attaching to the running server.
    ld.add_action(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ros_gz_sim_launch),
        launch_arguments={
            'gz_args': '-g',
            'on_exit_shutdown': 'true',
        }.items(),
        condition=IfCondition(gui),
    ))

    # One spawn of the model file. It is a plain <model>, so it can be
    # dropped into any world without that world including agv/ anywhere.
    ld.add_action(Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_forklift',
        output='screen',
        arguments=[
            '-world', world_name,
            '-file', model,
            '-name', name,
            '-x', LaunchConfiguration('x'),
            '-y', LaunchConfiguration('y'),
            '-z', LaunchConfiguration('z'),
            '-Y', LaunchConfiguration('yaw'),
            '-allow_renaming', 'false',
        ],
    ))

    # One bridge for every topic this directory owns.
    ld.add_action(Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='forklift_bridge',
        output='screen',
        arguments=_BRIDGE_ARGS,
        remappings=_BRIDGE_REMAPS,
    ))

    # The two vehicle nodes. They are plain scripts on purpose: this
    # directory is not a colcon package and adding one would be a build
    # system decision, not a vehicle decision.
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _IO_SCRIPT, '--config', config],
        name='forklift_io',
        output='screen',
        condition=IfCondition(nodes),
    ))
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _ZONE_SCRIPT, '--config', config],
        name='obstacle_zone',
        output='screen',
        condition=IfCondition(nodes),
    ))

    return ld
