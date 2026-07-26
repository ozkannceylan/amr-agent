# warehouse_bringup.launch.py - M3 bringup for the amr-agent project.
#
# One launch file that:
#   1. starts the Gazebo (gz sim) server with sim/worlds/warehouse.sdf,
#      headless by default (gui:=true adds the gz GUI client),
#   2. bridges /clock from Gazebo to ROS,
#   3. spawns the Robotnik RB-KAIROS by including the UNMODIFIED vendor
#      launch robotnik_gazebo_ignition/launch/spawn_robot.launch.py, which
#      itself starts:
#        - robot_state_publisher (via robotnik_description),
#        - the ros_gz_sim "create" entity spawner,
#        - a ros_gz_bridge for the onboard sensors (lidars, IMU, cameras),
#        - ros2_control controller spawners (joint_state_broadcaster +
#          robotnik_base_control mecanum controller via gz_ros2_control).
#
# Resulting key ROS topics (robot_id default "robot"):
#   /clock
#   /robot/robot_description                  (robot_state_publisher)
#   /robot/joint_states, /tf, /tf_static
#   /robot/front_laser/scan, /robot/rear_laser/scan   (safety lidars)
#   /robot/imu/data
#   /robot/robotnik_base_control/cmd_vel      (TwistStamped command in)
#   /robot/robotnik_base_control/cmd_vel_unstamped (Twist command in)
#   /robot/robotnik_base_control/odom         (odometry out)
#
# Usage (after sourcing /opt/ros/jazzy and the Robotnik workspace):
#   ros2 launch sim/launch/warehouse_bringup.launch.py
#   ros2 launch sim/launch/warehouse_bringup.launch.py gui:=true
#   ros2 launch sim/launch/warehouse_bringup.launch.py robot_id:=agv1 x:=-10.0 y:=-6.0

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
    os.path.join(_THIS_DIR, '..', 'worlds', 'warehouse.sdf')
)


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'world', default_value=_DEFAULT_WORLD,
        description='Absolute path to the world SDF file'))
    ld.add_action(DeclareLaunchArgument(
        'gui', default_value='false',
        description='Also start the Gazebo GUI client (headless if false)'))
    ld.add_action(DeclareLaunchArgument(
        'robot_id', default_value='robot',
        description='Robot namespace / entity name'))
    # Spawn pose: open area south of rack row B, clear of racks and stations.
    ld.add_action(DeclareLaunchArgument(
        'x', default_value='-10.0', description='Spawn X [m]'))
    ld.add_action(DeclareLaunchArgument(
        'y', default_value='-6.0', description='Spawn Y [m]'))
    ld.add_action(DeclareLaunchArgument(
        'z', default_value='0.15', description='Spawn Z [m]'))

    world = LaunchConfiguration('world')
    gui = LaunchConfiguration('gui')
    robot_id = LaunchConfiguration('robot_id')

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

    # /clock bridge (Gazebo -> ROS).
    ld.add_action(Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='gz_clock_bridge',
        output='screen',
        arguments=['/clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock'],
    ))

    # RB-KAIROS spawn via the unmodified vendor launch (robot description +
    # robot_state_publisher + entity create + sensor bridge + ros2_control
    # controller spawners). run_rviz:=False keeps the bringup headless.
    ld.add_action(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(
            get_package_share_directory('robotnik_gazebo_ignition'),
            'launch', 'spawn_robot.launch.py')),
        launch_arguments={
            'robot': 'rbkairos',
            'robot_model': 'rbkairos',
            'robot_id': robot_id,
            'x': LaunchConfiguration('x'),
            'y': LaunchConfiguration('y'),
            'z': LaunchConfiguration('z'),
            'run_rviz': 'False',
            'use_sim_time': 'True',
        }.items(),
    ))

    return ld
