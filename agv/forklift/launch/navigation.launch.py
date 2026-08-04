# navigation.launch.py - the vehicle's Nav2 stack.
#
# FIVE LIFECYCLE NODES AND TWO PLAIN ONES.
#
#   nav2_planner/planner_server         SmacPlannerHybrid, Reeds-Shepp
#   nav2_controller/controller_server   RegulatedPurePursuit
#   nav2_behaviors/behavior_server      `wait` and nothing that moves
#   nav2_bt_navigator/bt_navigator      the TRICYCLE behaviour tree
#   nav2_velocity_smoother              CLOSED_LOOP on the EKF's odometry
#   scripts/cmd_vel_to_tricycle.py      Twist -> (steer angle, drive speed)
#   scripts/forklift_io.py              engineering units -> gz joint cmds
#
# Every non-default parameter, with its reason, is in agv/forklift/nav2.yaml.
# This file starts processes and transitions lifecycles; it holds no tuning.
#
# WHAT IT IS STARTED AGAINST. A bringup and a localization stack that are
# ALREADY RUNNING. It starts no plant, no vehicle, no estimator and no
# localizer, exactly as localization.launch.py starts none of the bringup's:
#
#   terminal 1:  ros2 launch sim/launch/warehouse_bringup.launch.py \
#                    x:=<X> y:=<Y> yaw:=<YAW>
#   terminal 2:  ros2 launch agv/forklift/launch/localization.launch.py \
#                    initial_pose_x:=<mx> initial_pose_y:=<my> \
#                    initial_pose_yaw:=<myaw>
#   terminal 3:  ros2 launch agv/forklift/launch/navigation.launch.py
#
# WHY forklift_io.py IS STARTED HERE AND NOT BY THE BRINGUP. The bringup
# says in its own header that it deliberately does not start it, because at
# M4 that node only meant something with the PLC path behind it. Under
# autonomy it is the ONLY path from an engineering-unit command to a joint,
# so a navigation launch without it produces a stack that plans, follows,
# publishes commands and never moves - with nothing in any log that reads
# as wrong. It is switchable (`io:=false`) for exactly one case: a run
# where something else already owns the actuator path.
#
# ADR 0014 D1: THE LOOP CLOSES ONBOARD. Nothing started here is an OPC UA
# client, nothing here reads or writes a PLC node, and no velocity leaves
# the vehicle's own ROS graph. The chain is
#
#   controller_server -> /cmd_vel -> velocity_smoother
#     -> /cmd_vel_smoothed -> [m5-11's envelope gate] -> the converter
#       -> /forklift/cmd/* -> forklift_io -> gz
#
# THE GATE'S INSERTION POINT IS THE `cmd_topic` ARGUMENT. m5-11 starts its
# node subscribing to /cmd_vel_smoothed and publishing, say,
# /cmd_vel_gated, and launches this file with cmd_topic:=/cmd_vel_gated.
# No file in this directory changes. The envelope gate is NOT anticipated
# here in any other way: no enable, no ceiling and no freshness window
# appears in this launch or in nav2.yaml.
#
# GROUND TRUTH REACHES NOTHING STARTED HERE. /forklift/odom is the
# simulator's own pose of the model despite its name (config.yaml carries
# the standing rename request). The smoother's feedback, the controller's
# odometry and the BT's speed all name /forklift/odom_filtered, the EKF's
# estimate. The one exception is forklift_io.py, which subscribes to
# /forklift/odom to publish /forklift/linear_speed - a process readout that
# steers nothing and predates this file.
#
# NEITHER SAFETY SCANNER APPEARS ANYWHERE IN THIS STACK. nav2.yaml's
# costmaps name no scan topic at all (see its local_costmap header for the
# measured reason), and the navigation lidar is the only sensor the
# localizer consumes.
#
# use_sim_time IS SET ON EVERY NODE AND IN nav2.yaml. A node left on the
# system clock differences two clocks, asks tf2 for a transform ~1.8e9 s in
# the future and is told the transform does not exist, which reads as a
# missing publisher and is not one.
#
# EVERY LIFECYCLE HANDLER IS REGISTERED BEFORE THE FIRST TRANSITION IS
# EMITTED. That ordering is localization.launch.py's, and it is there for a
# measured reason: `launch` executes actions in order, an OnStateTransition
# handler only begins matching when its RegisterEventHandler action runs,
# and a node whose configure completes faster than the launch can register
# the next handler has its transition go unheard and the chain stops dead
# with nothing in the log that reads as an error. That race cost a run
# (EVIDENCE_LOCALIZATION.md section 3). sim/launch/warehouse_slam.launch.py
# still carries the original ordering; that is a request to sim/ and NOT a
# change made here.
#
# NO nav2 lifecycle_manager, for the same reason localization.launch.py
# gives: a bond heartbeat starves at the real time factors this host
# reaches, and a manager that declares a healthy node dead is worse than no
# manager. The transitions below are chained on OBSERVED state.
#
# THE ORDER THE FIVE ARE BROUGHT UP IN, AND WHY IT IS NOT ARBITRARY.
# bt_navigator is activated LAST. It creates action clients for
# ComputePathToPose, FollowPath and Wait when its tree is first ticked; a
# goal accepted before the three servers are active fails on a service
# timeout that reads like a missing node. planner and controller each build
# a costmap and the planner additionally builds a 201 x 201 heuristic
# lookup table, which measured ~4.8 s on this host - so "the launch printed
# no errors" is not the check. The check is that
# /navigate_to_pose/_action/status exists AND the log line at the end of
# this file has appeared.
#
# THIS FILE CONTAINS NO CONTROL LOGIC. No sequencing, no interlock, no
# timer, no latch, no threshold. The protective stop is onboard and
# hardwired and appears in no launch file (invariant 1).

import os
import sys

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent,
                            ExecuteProcess, LogInfo, RegisterEventHandler)
from launch.conditions import IfCondition
from launch.events import matches_action
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState

from lifecycle_msgs.msg import Transition

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))

_DEFAULT_PARAMS = os.path.join(_FORKLIFT_DIR, 'nav2.yaml')
_DEFAULT_CONFIG = os.path.join(_FORKLIFT_DIR, 'config.yaml')
_DEFAULT_BT = os.path.join(
    _FORKLIFT_DIR, 'behavior_trees', 'navigate_to_pose_tricycle.xml')
_CONVERTER = os.path.join(_FORKLIFT_DIR, 'scripts', 'cmd_vel_to_tricycle.py')
_FORKLIFT_IO = os.path.join(_FORKLIFT_DIR, 'scripts', 'forklift_io.py')


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'params_file', default_value=_DEFAULT_PARAMS,
        description='Absolute path to the Nav2 parameter file. Every '
                    'non-default value in it carries its reason.'))
    ld.add_action(DeclareLaunchArgument(
        'bt_xml', default_value=_DEFAULT_BT,
        description='Absolute path to the navigate-to-pose behaviour tree. '
                    'The default removes nav2\'s Spin and BackUp '
                    'recoveries; the file says why. Passed ABSOLUTE '
                    'because bt_navigator resolves the string as a path '
                    'and a relative one resolves against the working '
                    'directory of whoever ran the launch.'))
    ld.add_action(DeclareLaunchArgument(
        'config_file', default_value=_DEFAULT_CONFIG,
        description='agv/forklift/config.yaml, the named-constant file the '
                    'two Python nodes read.'))
    ld.add_action(DeclareLaunchArgument(
        'cmd_topic', default_value='/cmd_vel_smoothed',
        description='Twist topic the tricycle converter subscribes to. '
                    'THIS IS m5-11\'s INSERTION POINT: point it at the '
                    'envelope gate\'s output and the gate sits below the '
                    'smoother exactly as ADR 0014 seam (b) specifies, with '
                    'no edit to this file, to nav2.yaml or to the '
                    'converter.'))
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Read the clock from /clock. Leaving this false '
                    'against a simulation produces "missing transform" '
                    'errors that look like a TF bug and are not one.'))
    ld.add_action(DeclareLaunchArgument(
        'autostart', default_value='true',
        description='Configure and activate the five lifecycle nodes from '
                    'here. FALSE LEAVES THEM UNCONFIGURED AND SILENT: '
                    'no action server, no costmap, no /cmd_vel, and '
                    'nothing in any log that reads as wrong.'))
    ld.add_action(DeclareLaunchArgument(
        'io', default_value='true',
        description='Also start scripts/forklift_io.py, the engineering-'
                    'unit to joint-command translator. TRUE by default '
                    'because the warehouse bringup deliberately does not '
                    'start it, and without it this stack plans, follows, '
                    'publishes commands and never moves.'))
    ld.add_action(DeclareLaunchArgument(
        'converter', default_value='true',
        description='Also start scripts/cmd_vel_to_tricycle.py. FALSE only '
                    'for a run where something else owns the conversion; '
                    'nav2 emits a body twist and nothing else in this '
                    'repository turns one into a steer angle.'))

    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')
    params_file = LaunchConfiguration('params_file')

    # ---------------------------------------------------------------- #
    # the five lifecycle nodes
    # ---------------------------------------------------------------- #

    planner = LifecycleNode(
        package='nav2_planner', executable='planner_server',
        name='planner_server', namespace='', output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
    )
    ld.add_action(planner)

    controller = LifecycleNode(
        package='nav2_controller', executable='controller_server',
        name='controller_server', namespace='', output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
    )
    ld.add_action(controller)

    behaviors = LifecycleNode(
        package='nav2_behaviors', executable='behavior_server',
        name='behavior_server', namespace='', output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
    )
    ld.add_action(behaviors)

    smoother = LifecycleNode(
        package='nav2_velocity_smoother', executable='velocity_smoother',
        name='velocity_smoother', namespace='', output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
    )
    ld.add_action(smoother)

    bt_navigator = LifecycleNode(
        package='nav2_bt_navigator', executable='bt_navigator',
        name='bt_navigator', namespace='', output='screen',
        parameters=[
            params_file,
            {
                'use_sim_time': use_sim_time,
                # ABSOLUTE, and it overrides nav2.yaml's bare filename on
                # purpose: bt_navigator treats the string as a path.
                'default_nav_to_pose_bt_xml': LaunchConfiguration('bt_xml'),
            },
        ],
    )
    ld.add_action(bt_navigator)

    # ---------------------------------------------------------------- #
    # the two plain nodes
    #
    # Invoked with the interpreter running this launch file, which is
    # /usr/bin/python3 under `ros2 launch`; the container's
    # /usr/local/bin/python3 is 3.11 and has no rclpy
    # (sim/setup/CONTAINER_TOOLCHAIN.md section 3.3).
    # ---------------------------------------------------------------- #

    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _CONVERTER,
             '--config', LaunchConfiguration('config_file'),
             '--cmd-topic', LaunchConfiguration('cmd_topic'),
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='cmd_vel_to_tricycle',
        output='screen',
        condition=IfCondition(LaunchConfiguration('converter')),
    ))

    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _FORKLIFT_IO,
             '--config', LaunchConfiguration('config_file'),
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='forklift_io',
        output='screen',
        condition=IfCondition(LaunchConfiguration('io')),
    ))

    # ---------------------------------------------------------------- #
    # HANDLERS FIRST, EMIT LAST. See the header.
    # ---------------------------------------------------------------- #

    def _on_configured(node, label, then):
        """inactive -> active for `node`, chained on the observed
        transition rather than on a delay."""
        return RegisterEventHandler(
            OnStateTransition(
                target_lifecycle_node=node,
                start_state='configuring', goal_state='inactive',
                entities=[
                    LogInfo(msg='{} configured; activating'.format(label)),
                    EmitEvent(event=ChangeState(
                        lifecycle_node_matcher=matches_action(node),
                        transition_id=Transition.TRANSITION_ACTIVATE)),
                ] + list(then),
            ),
            condition=IfCondition(autostart),
        )

    def _configure(node):
        return EmitEvent(event=ChangeState(
            lifecycle_node_matcher=matches_action(node),
            transition_id=Transition.TRANSITION_CONFIGURE))

    # planner configured -> activate it, and configure the controller.
    ld.add_action(_on_configured(
        planner, 'planner_server', [_configure(controller)]))
    ld.add_action(_on_configured(
        controller, 'controller_server', [_configure(behaviors)]))
    ld.add_action(_on_configured(
        behaviors, 'behavior_server', [_configure(smoother)]))
    ld.add_action(_on_configured(
        smoother, 'velocity_smoother', [_configure(bt_navigator)]))
    # bt_navigator LAST: its tree creates action clients for the three
    # servers above, so it must not be activated before they answer.
    ld.add_action(_on_configured(bt_navigator, 'bt_navigator', []))

    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=bt_navigator,
            start_state='activating', goal_state='active',
            entities=[LogInfo(
                msg='Nav2 active. The check that this launch worked is that '
                    '/navigate_to_pose/_action/status is on `ros2 topic '
                    'list` and that a goal is ACCEPTED - never a '
                    'clean-looking log. A refused goal is a RESULT, not a '
                    'failure of this launch: the planner is configured with '
                    'allow_unknown false and a footprint padded by the '
                    'measured localization error, and it is meant to refuse '
                    'what it cannot reach.')],
        ),
        condition=IfCondition(autostart),
    ))

    # unconfigured -> inactive, planner_server. LAST ACTION IN THE FILE, so
    # that every handler above is already listening when it completes.
    ld.add_action(EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(planner),
            transition_id=Transition.TRANSITION_CONFIGURE),
        condition=IfCondition(autostart),
    ))

    return ld
