# nav_scenario.launch.py - M3 navigation stack for the amr-agent project
# (brief m3-02).
#
# Runs the Nav2 stack against an ALREADY RUNNING m3-01 bringup
# (sim/launch/warehouse_bringup.launch.py). It does not start Gazebo or the
# robot itself; keeping the two launches separate leaves the verified m3-01
# bringup untouched.
#
# Nodes (all in the global namespace, lifecycle-managed, autostarted):
#   map_server        serves sim/scenarios/maps/map.yaml (generated from the
#                     world geometry by tools/make_map.py)
#   amcl              localizes on /robot/front_laser/scan,
#                     frames map -> robot_odom -> robot_base_footprint
#   planner_server    NavFn global planner
#   controller_server DWB local planner, cmd_vel remapped to the vendor
#                     controller input (Twist on cmd_vel_unstamped)
#   behavior_server   spin / backup / wait recoveries (same cmd_vel remap)
#   bt_navigator      NavigateToPose behavior tree
#   lifecycle_manager autostart, bond_timeout 0 (heartbeats starve at the
#                     container's ~0.1 real-time factor)
#
# Usage (after sourcing /opt/ros/jazzy and the Robotnik workspace, with the
# warehouse bringup already running):
#   ros2 launch sim/scenarios/nav_scenario.launch.py
# Arguments: params_file:=<abs path>  map:=<abs path to map.yaml>

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PARAMS = os.path.join(_THIS_DIR, 'config', 'nav2_params.yaml')
_DEFAULT_MAP = os.path.join(_THIS_DIR, 'maps', 'map.yaml')

# Nav2 publishes cmd_vel (Twist, enable_stamped_cmd_vel false); the vendor
# robotnik_base_control consumes Twist on cmd_vel_unstamped.
_CMD_VEL_REMAP = ('cmd_vel', '/robot/robotnik_base_control/cmd_vel_unstamped')

_LIFECYCLE_NODES = [
    'map_server',
    'amcl',
    'planner_server',
    'controller_server',
    'behavior_server',
    'bt_navigator',
]


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'params_file', default_value=_DEFAULT_PARAMS,
        description='Absolute path to the Nav2 parameters file'))
    ld.add_action(DeclareLaunchArgument(
        'map', default_value=_DEFAULT_MAP,
        description='Absolute path to the map yaml'))

    params_file = LaunchConfiguration('params_file')
    map_yaml = LaunchConfiguration('map')

    ld.add_action(Node(
        package='nav2_map_server', executable='map_server',
        name='map_server', output='screen',
        parameters=[params_file, {'yaml_filename': map_yaml}]))

    ld.add_action(Node(
        package='nav2_amcl', executable='amcl',
        name='amcl', output='screen',
        parameters=[params_file]))

    ld.add_action(Node(
        package='nav2_planner', executable='planner_server',
        name='planner_server', output='screen',
        parameters=[params_file]))

    ld.add_action(Node(
        package='nav2_controller', executable='controller_server',
        name='controller_server', output='screen',
        parameters=[params_file],
        remappings=[_CMD_VEL_REMAP]))

    ld.add_action(Node(
        package='nav2_behaviors', executable='behavior_server',
        name='behavior_server', output='screen',
        parameters=[params_file],
        remappings=[_CMD_VEL_REMAP]))

    ld.add_action(Node(
        package='nav2_bt_navigator', executable='bt_navigator',
        name='bt_navigator', output='screen',
        parameters=[params_file]))

    ld.add_action(Node(
        package='nav2_lifecycle_manager', executable='lifecycle_manager',
        name='lifecycle_manager_navigation', output='screen',
        parameters=[{
            'use_sim_time': True,
            'autostart': True,
            'bond_timeout': 0.0,
            'node_names': _LIFECYCLE_NODES,
        }]))

    return ld
