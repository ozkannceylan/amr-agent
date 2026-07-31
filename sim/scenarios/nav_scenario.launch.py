# nav_scenario.launch.py - navigation stack of the PARKED navigation
# scenario (brief m3-02). NOT current work: see sim/scenarios/DEFERRED.md.
#
# The vehicle platform this file was written against was retired by
# ADR 0010 D1. Its Nav2 parameter file was deleted by m5-09 because it is
# not a migration candidate; the forklift's Nav2 configuration is written
# from scratch at m5-10 (tricycle kinematics, one navigation lidar, its own
# frame tree). Consequently:
#   - params_file has NO default and must be passed explicitly; there is no
#     parameter file in this repository that this node set can run against;
#   - the node set below (NavFn planner, DWB controller, spin/backup
#     behaviors) and the cmd_vel remap are retired-platform values kept as
#     the record of the parked scenario, not as this project's interface.
# Whether this file survives migration is decided at m5-10 briefing.
#
# Runs the Nav2 stack against an ALREADY RUNNING m3-01 bringup
# (sim/launch/warehouse_bringup.launch.py). It does not start Gazebo or the
# robot itself; keeping the two launches separate leaves the verified m3-01
# bringup untouched.
#
# Nodes (all in the global namespace, lifecycle-managed, autostarted):
#   map_server        serves sim/scenarios/maps/map.yaml (generated from the
#                     world geometry by tools/make_map.py)
#   amcl              localizes on the retired platform's front scan topic,
#                     retired frame tree
#   planner_server    NavFn global planner
#   controller_server DWB local planner, cmd_vel remapped to the retired
#                     platform's controller input (Twist on cmd_vel_unstamped)
#   behavior_server   spin / backup / wait recoveries (same cmd_vel remap)
#   bt_navigator      NavigateToPose behavior tree
#   lifecycle_manager autostart, bond_timeout 0 (heartbeats starve at the
#                     container's ~0.1 real-time factor)
#
# Usage (parked; the vendor workspace this needed is no longer provisioned
# by sim/setup/install.sh, so this cannot be run as it stands):
#   ros2 launch sim/scenarios/nav_scenario.launch.py params_file:=<abs path>
# Arguments: params_file:=<abs path>  (REQUIRED)  map:=<abs path to map.yaml>

import os

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MAP = os.path.join(_THIS_DIR, 'maps', 'map.yaml')

# No default parameter file. config/nav2_params.yaml was deleted by m5-09
# (ADR 0010 D1) and is not replaced in place; m5-10 writes the forklift's
# Nav2 configuration from scratch.

# Nav2 publishes cmd_vel (Twist, enable_stamped_cmd_vel false); the retired
# platform's base controller consumed Twist on cmd_vel_unstamped. Retired
# value, kept as record; m5-10 decides the forklift's command topic.
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
        'params_file',
        description='Absolute path to the Nav2 parameters file (REQUIRED: '
                    'the retired platform\'s file was deleted by m5-09, '
                    'ADR 0010 D1)'))
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
