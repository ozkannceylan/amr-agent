# cell_bringup.launch.py - M3 fixed-equipment cell bringup for amr-agent.
#
# One headless-by-default launch that:
#   1. starts the Gazebo (gz sim) server with sim/worlds/cell.sdf,
#   2. starts one ros_gz_bridge carrying every cell signal in both
#      directions, plus /clock.
#
# There is no robot here and none belongs here (ADR 0004).
#
# THIS FILE CONTAINS NO CONTROL LOGIC. The bridge is a type translator: it
# moves a value across the ROS/gz boundary and changes nothing else. No
# sequencing, no interlock, no timer, no latch, no debounce, no threshold.
# Every one of those belongs to the PLC (invariants 5, 6 and 9).
#
# Signals (full table with meaning and direction: sim/README.md):
#
#   PLC -> cell (actuator commands)
#     /cell/conveyor/cmd_speed      std_msgs/Float64      belt velocity [m/s]
#
#   cell -> PLC (raw device state)
#     /cell/conveyor/joint_state    sensor_msgs/JointState  belt encoder
#     /cell/product_sensor/scan     sensor_msgs/LaserScan   photo-eye range [m]
#     /cell/panel/start             std_msgs/Bool           Start contact (NO)
#     /cell/panel/stop              std_msgs/Bool           Stop contact (NC)
#     /cell/panel/process_stop      std_msgs/Bool           process-stop contact (NC)
#
#   diagnostic only, not a PLC signal
#     /cell/product_box/pose        geometry_msgs/PoseArray product pose
#     /clock                        rosgraph_msgs/Clock     sim time
#
# The three panel contacts have no simulated physics. They are created by
# this bridge as ROS -> gz signals so a human, a test script or (later) the
# m3-04 bridge process can drive them exactly as it will drive a real
# panel's wired contacts.
#
# NOTE ON THE RED BUTTON: /cell/panel/process_stop is a PROCESS stop. It is
# not a safety function, carries no safety integrity, and must never be
# presented as one. The safety e-stop chain is hardwired to the F-CPU and
# never crosses the network (invariant 1, ADR 0004).
#
# Usage (after sourcing /opt/ros/jazzy/setup.bash):
#   ros2 launch /home/user/amr-agent/sim/launch/cell_bringup.launch.py
#   ros2 launch /home/user/amr-agent/sim/launch/cell_bringup.launch.py gui:=true

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

from ament_index_python.packages import get_package_share_directory

# The world ships in this repository next to the launch file, so resolve it
# relative to this file instead of a package share directory.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_WORLD = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'worlds', 'cell.sdf')
)

# gz topic name -> ROS message type -> gz message type.
#   '['  gz to ROS   (device state read by the PLC)
#   ']'  ROS to gz   (actuator command written by the PLC)
_BRIDGE_ARGS = [
    # simulation clock
    '/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock',

    # conveyor: raw velocity command in, raw encoder out
    '/cell/conveyor/cmd_speed@std_msgs/msg/Float64]gz.msgs.Double',
    '/cell/conveyor/joint_state@sensor_msgs/msg/JointState[gz.msgs.Model',

    # product sensor: raw range across the belt (no threshold applied here)
    '/cell/product_sensor/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan',

    # operator panel contacts (raw contact state, no debounce, no latch)
    '/cell/panel/start@std_msgs/msg/Bool]gz.msgs.Boolean',
    '/cell/panel/stop@std_msgs/msg/Bool]gz.msgs.Boolean',
    '/cell/panel/process_stop@std_msgs/msg/Bool]gz.msgs.Boolean',

    # diagnostic: product pose, so belt transport is observable without a GUI
    '/model/ProductBox/pose@geometry_msgs/msg/PoseArray[gz.msgs.Pose_V',
]


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'world', default_value=_DEFAULT_WORLD,
        description='Absolute path to the cell world SDF file'))
    ld.add_action(DeclareLaunchArgument(
        'gui', default_value='false',
        description='Also start the Gazebo GUI client (headless if false)'))

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')

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

    # One bridge for every cell signal. The PosePublisher's gz topic name is
    # fixed by the plugin, so it is remapped on the ROS side into /cell/*.
    ld.add_action(Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='cell_bridge',
        output='screen',
        arguments=_BRIDGE_ARGS,
        remappings=[('/model/ProductBox/pose', '/cell/product_box/pose')],
    ))

    return ld
