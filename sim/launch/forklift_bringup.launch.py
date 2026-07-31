# forklift_bringup.launch.py - M4 forklift commissioning bringup for amr-agent.
#
# One headless-by-default launch that:
#   1. starts the Gazebo (gz sim) server with sim/worlds/forklift_arena.sdf,
#   2. spawns agv/forklift/model.sdf into it once,
#   3. starts one ros_gz_bridge carrying /clock, the vehicle's three raw
#      joint commands (ROS -> gz) and its four feedback topics (gz -> ROS).
#
# WHAT DELIBERATELY DOES NOT RUN HERE:
#
#   the two vehicle nodes. forklift_io.py and obstacle_zone.py are owned by
#     agv/forklift/launch/vehicle.launch.py, which starts them together with
#     its own server, spawn and bridge. This file is the sim/ side: a world,
#     a spawn and a transport bridge, nothing that turns a raw joint value
#     into an engineering unit. Run the vehicle nodes against this world by
#     launching that file with world:=<this world> and server:=false, or by
#     running the scripts directly.
#
#   the fixed-equipment cell. sim/worlds/cell.sdf and its bringup are M3 and
#     are untouched by this file. The coupled cell plus vehicle scenario is
#     roadmap M6 work (AT-07 coupled, ADR 0010) and neither world includes
#     the other.
#
#   the PLC, the bridge process and the HMI. Under ADR 0008 every command
#     reaches the simulation through HMI -> PLC standard program -> bridge,
#     and every state report returns the same way. Those are bridge/, plc/
#     and hmi/ processes; this launch only puts the plant on the wire.
#
#   Nav2, AMCL, a map and any VDA 5050 client. The forklift carries no
#     navigation claim at M4 (ADR 0008 D5; ADR 0010 D1/D2 give it a
#     navigation stack at M5, which this file does not anticipate).
#
# THIS FILE CONTAINS NO CONTROL LOGIC. The bridge is a type translator: it
# moves a value across the ROS/gz boundary and changes nothing else. No
# sequencing, no interlock, no timer, no latch, no debounce, no threshold.
# Every one of those belongs to the PLC (invariants 5, 6 and 9), and the
# protective stop is onboard and hardwired and appears in no launch file
# (invariant 1).
#
# Topics (authoritative table: agv/forklift/README.md, which this file
# reads and does not edit):
#
#   ROS -> gz (raw joint commands, same name on both sides on purpose)
#     /forklift/gz/steer_cmd      std_msgs/Float64    steer angle    [rad]
#     /forklift/gz/traction_cmd   std_msgs/Float64    wheel rate     [rad/s]
#     /forklift/gz/fork_cmd       std_msgs/Float64    carriage travel [m]
#
#   gz -> ROS (feedback, renamed on the ROS side)
#     /forklift/scan                            sensor_msgs/LaserScan
#         the NAVIGATION lidar, from /forklift/gz/scan_nav.
#         360 ranges over 360 deg, 10 Hz, plane z = 1.80 m.
#     /forklift/safety_scanner_front/measurement   sensor_msgs/LaserScan
#         the front safety scanner's NON-SAFE MEASUREMENT CHANNEL, from
#         /forklift/gz/safety_scanner_front/measurement.
#         275 ranges over 275 deg, 10 Hz, plane z = 0.15 m.
#     /forklift/odom              nav_msgs/Odometry       ground truth, 20 Hz
#     /forklift/joint_states      sensor_msgs/JointState  physics rate
#
#   infrastructure
#     /clock                      rosgraph_msgs/Clock     sim time
#
# NOT BRIDGED, ON PURPOSE: /forklift/gz/safety_scanner_rear/measurement.
# agv/forklift/README.md rules that a measurement channel goes onto the
# process network when something on that network consumes it and not
# before, and nothing consumes the rear one yet. This launch file follows
# that ruling rather than bridging "everything the model publishes"; when
# a consumer appears, agv/ names the ROS topic and this file adds the row.
#
# WHAT "measurement" IN A TOPIC NAME MEANS, because a reader will meet the
# word here before they meet the contract. The device class modelled emits
# two outputs: a safe channel (the protective-field verdict, an OSSD pair
# on a real device) and a separate non-safe measurement channel that the
# datasheet provides for HMI, diagnostics and process use while stating it
# must not be used for safety-related tasks. Only the second one is a
# topic. agv/forklift/README.md states the naming rule this file obeys:
# every channel a subscriber can reach is a measurement channel and says
# `measurement` in its name, and the safe channel has no topic on either
# transport, ever. Nothing bridged below is a safety signal, whatever the
# device it came from is called (invariant 1).
#
# NOTE ON /forklift/joint_states. gz's JointStatePublisher has no working
# rate parameter and publishes once per physics iteration, so this topic
# arrives at the world's ~500 Hz and not at a chosen rate. It is bridged
# as-is: decimating it here would be the bridge deciding what a consumer
# needs, and the vehicle nodes already rate-limit everything they derive
# from it. The measured bridged rate is recorded with every other topic's:
# worlds/FORKLIFT_ARENA_EVIDENCE.md section 3 for the M4 topic set, and
# setup/CONTAINER_TOOLCHAIN.md section 6.2 for the set below.
#
# NOTE ON THE TWO SCAN TOPICS. All three scanners on the model are gpu_lidar
# sensors, so the world MUST load gz-sim-sensors-system with a render engine.
# forklift_arena.sdf does; gz's stock empty.sdf does not, and on it this
# bridge advertises both topics and nothing ever arrives on either.
#
# NOTE ON THE SILENT FAILURE THIS FILE ONCE HAD. A ros_gz_bridge entry for a
# gz topic that nobody publishes logs `Creating GZ->ROS Bridge` exactly as a
# working one does: no error, no warning, no data. This file bridged
# /forklift/gz/scan for one round after m5-04 deleted that sensor, and the
# only symptom was silence (CONTAINER_TOOLCHAIN.md section 6). So every name
# below is quoted from agv/forklift/README.md AND was confirmed against
# `gz topic -l` on a running server, and the check that this file works is
# `ros2 topic hz` on each bridged ROS topic, never a clean-looking log.
#
# Usage (after sourcing /opt/ros/jazzy/setup.bash). Isolate BOTH transports
# whenever another simulation may be running: ROS_DOMAIN_ID does not isolate
# Gazebo, because gz transport does not use DDS. GZ_PARTITION does.
#
#   export GZ_PARTITION=myrun ROS_DOMAIN_ID=42
#   ros2 launch /path/to/sim/launch/forklift_bringup.launch.py
#   ros2 launch /path/to/sim/launch/forklift_bringup.launch.py gui:=true

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

# The world ships in this repository next to the launch file, and the model
# ships in agv/forklift/, so resolve both relative to this file instead of a
# package share directory.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..'))
_DEFAULT_WORLD = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'worlds', 'forklift_arena.sdf')
)
_DEFAULT_MODEL = os.path.join(_REPO_ROOT, 'agv', 'forklift', 'model.sdf')

# Spawn pose. The arena's drive aisle runs along y = 0; -6.00 puts the
# vehicle in the open west half of it, facing +x, with the whole aisle and
# the stop-zone crate ahead of it. Overridable per run: a scenario that
# wants a different start pose passes it rather than editing this file.
_SPAWN_X = '-6.00'
_SPAWN_Y = '0.00'
_SPAWN_Z = '0.05'
_SPAWN_YAW = '0.0'

# gz topic name -> ROS message type -> gz message type.
#   '['  gz to ROS   (feedback produced by the model)
#   ']'  ROS to gz   (raw joint command consumed by the model)
#
# Every name below is quoted from the contract table in
# agv/forklift/README.md. They are written literally rather than imported
# from agv/forklift/config.yaml so that this launch file states the whole
# interface it carries, in the same shape as cell_bringup.launch.py.
_BRIDGE_ARGS = [
    # simulation clock
    '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',

    # raw joint commands into the model (no ramp, no clamp, no interlock)
    '/forklift/gz/steer_cmd@std_msgs/msg/Float64]gz.msgs.Double',
    '/forklift/gz/traction_cmd@std_msgs/msg/Float64]gz.msgs.Double',
    '/forklift/gz/fork_cmd@std_msgs/msg/Float64]gz.msgs.Double',

    # navigation lidar: raw ranges at z = 1.80 m. This is the vehicle's SLAM,
    # AMCL and costmap input, and no safety scanner channel joins it there.
    '/forklift/gz/scan_nav@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',

    # front safety scanner, NON-SAFE MEASUREMENT CHANNEL, at z = 0.15 m: raw
    # ranges, no zone, no threshold and no field evaluation applied here. The
    # safe channel is not on this list because it is not a topic at all.
    ('/forklift/gz/safety_scanner_front/measurement'
     '@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'),

    # ground-truth odometry: simulation feedback, not a localisation solution
    '/forklift/gz/odom@nav_msgs/msg/Odometry[gz.msgs.Odometry',

    # joint position and rate for the three driven joints, at physics rate
    '/forklift/gz/joint_state@sensor_msgs/msg/JointState[gz.msgs.Model',
]

# Feedback keeps its gz name on the gz side and takes the vehicle-facing
# name on the ROS side, so a consumer does not have to know it came from a
# simulator. Commands are NOT remapped: the same name on both sides is what
# makes them recognisable as the model's raw inputs.
#
# The measurement channel keeps the word `measurement` on both sides. Only
# the /gz/ segment is dropped, because the rule in agv/forklift/README.md is
# that a reachable channel says so in its name, and a rename that quietly
# lost the word would be this file editing the contract.
_BRIDGE_REMAPS = [
    ('/forklift/gz/scan_nav', '/forklift/scan'),
    ('/forklift/gz/safety_scanner_front/measurement',
     '/forklift/safety_scanner_front/measurement'),
    ('/forklift/gz/odom', '/forklift/odom'),
    ('/forklift/gz/joint_state', '/forklift/joint_states'),
]


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'world', default_value=_DEFAULT_WORLD,
        description='Absolute path to the arena world SDF file'))
    ld.add_action(DeclareLaunchArgument(
        'world_name', default_value='',
        description='Name of the <world> element the model is spawned into. '
                    'Empty lets the spawn discover it from the running '
                    'server, which stays correct when world:= is overridden'))
    ld.add_action(DeclareLaunchArgument(
        'model', default_value=_DEFAULT_MODEL,
        description='Absolute path to the forklift model SDF (agv/ owns it)'))
    ld.add_action(DeclareLaunchArgument(
        'name', default_value='Forklift',
        description='Name the model is spawned under. The gz topic names do '
                    'not depend on it: model.sdf states every topic '
                    'explicitly'))
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

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    use_sim_time = LaunchConfiguration('use_sim_time')

    ros_gz_sim_launch = os.path.join(
        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')

    # Gazebo server, headless, running immediately (-r -s).
    ld.add_action(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ros_gz_sim_launch),
        launch_arguments={
            'gz_args': ['-r -s ', world],
            'on_exit_shutdown': 'true',
        }.items(),
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

    # One spawn of the vehicle. agv/forklift/model.sdf is a plain <model>,
    # so the arena does not reference agv/ anywhere and the vehicle does not
    # reference a world.
    ld.add_action(Node(
        package='ros_gz_sim',
        executable='create',
        name='spawn_forklift',
        output='screen',
        arguments=[
            '-world', LaunchConfiguration('world_name'),
            '-file', LaunchConfiguration('model'),
            '-name', LaunchConfiguration('name'),
            '-x', LaunchConfiguration('x'),
            '-y', LaunchConfiguration('y'),
            '-z', LaunchConfiguration('z'),
            '-Y', LaunchConfiguration('yaw'),
            '-allow_renaming', 'false',
        ],
    ))

    # One bridge for every topic the arena carries.
    ld.add_action(Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='forklift_arena_bridge',
        output='screen',
        arguments=_BRIDGE_ARGS,
        remappings=_BRIDGE_REMAPS,
        parameters=[{'use_sim_time': use_sim_time}],
    ))

    return ld
