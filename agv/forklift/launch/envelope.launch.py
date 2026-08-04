# envelope.launch.py - the envelope gate's own measurement stack.
#
# WHAT IT STARTS, AND WHY IT IS NOT navigation.launch.py
#
#   nav2_velocity_smoother          the SAME node with the SAME nav2.yaml
#                                   block the Nav2 work measured, with one
#                                   parameter overridable from the command
#                                   line: `feedback`
#   scripts/envelope_gate.py        the node under test
#   scripts/cmd_vel_to_tricycle.py  pointed at the GATE's output
#   scripts/forklift_io.py          engineering units -> gz joint commands
#
# The planner, the controller, the behaviour server, the behaviour tree and
# AMCL are DELIBERATELY ABSENT. Not one of the six acceptance observations
# needs a plan: they need a known command, a known envelope and the chain
# BELOW the smoother, which is exactly what this file starts. Driving them
# from a goal would make every figure depend on what the controller
# happened to demand at that instant, and the open-loop / closed-loop
# comparison needs the two runs to differ in ONE thing.
#
#   The chain here is the deployed chain from /cmd_vel down. What is
#   replaced is only what produces /cmd_vel: scripts/envelope_run.py
#   publishes it on a script instead of controller_server publishing it
#   from a plan.
#
# THE feedback ARGUMENT IS THE MEASUREMENT OF section 3.2 OF THE BRIEF.
# nav2.yaml pins the smoother CLOSED_LOOP because ADR 0014 seam (b)
# specifies it; `feedback:=OPEN_LOOP` restores nav2's own default so the
# two can be run with everything else equal. It exists for the comparison
# and for nothing else, and the file that carries the decision is
# nav2.yaml, not this one.
#
# WHAT IT IS STARTED AGAINST. A warehouse bringup that is ALREADY RUNNING,
# and nothing else:
#
#   terminal 1:  ros2 launch sim/launch/warehouse_bringup.launch.py \
#                    x:=-4.5 y:=7.0 yaw:=0.0
#   terminal 2:  ros2 launch agv/forklift/launch/envelope.launch.py
#   terminal 3:  python3 agv/forklift/scripts/envelope_run.py run \
#                    --scenario enable-drop --csv <path>
#
# NO PLC, NO BRIDGE, NO OPC UA. Nothing started here is an OPC UA client
# and nothing reads or writes a PLC node. The envelope arrives as the six
# ROS 2 topics of opcua-nodes.md section 12.10 and is published by a
# double (ADR 0014 D1, invariant 11).
#
# THIS FILE CONTAINS NO CONTROL LOGIC. No sequencing, no interlock, no
# timer, no latch, no threshold. The gate's own constants are in
# agv/forklift/config.yaml, its ramp is in its own file, and the
# protective stop is onboard and hardwired and appears in no launch file
# (invariant 1).

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
_GATE = os.path.join(_FORKLIFT_DIR, 'scripts', 'envelope_gate.py')
_CONVERTER = os.path.join(_FORKLIFT_DIR, 'scripts', 'cmd_vel_to_tricycle.py')
_FORKLIFT_IO = os.path.join(_FORKLIFT_DIR, 'scripts', 'forklift_io.py')


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'params_file', default_value=_DEFAULT_PARAMS,
        description='Nav2 parameter file. Only its velocity_smoother '
                    'block is read by this launch.'))
    ld.add_action(DeclareLaunchArgument(
        'config_file', default_value=_DEFAULT_CONFIG,
        description='agv/forklift/config.yaml, the named-constant file the '
                    'three Python nodes read.'))
    ld.add_action(DeclareLaunchArgument(
        'feedback', default_value='CLOSED_LOOP',
        description='velocity_smoother feedback. CLOSED_LOOP is what '
                    'nav2.yaml pins and what ADR 0014 seam (b) specifies. '
                    'OPEN_LOOP is nav2\'s own default and exists here ONLY '
                    'for the gate-release comparison.'))
    ld.add_action(DeclareLaunchArgument(
        'io', default_value='true',
        description='Also start forklift_io.py. The warehouse bringup '
                    'deliberately does not, and without it this stack '
                    'publishes commands and never moves.'))

    smoother = LifecycleNode(
        package='nav2_velocity_smoother', executable='velocity_smoother',
        name='velocity_smoother', namespace='', output='screen',
        parameters=[
            LaunchConfiguration('params_file'),
            {
                'use_sim_time': True,
                'feedback': LaunchConfiguration('feedback'),
            },
        ],
    )
    ld.add_action(smoother)

    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _GATE,
             '--config', LaunchConfiguration('config_file'),
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='envelope_gate', output='screen',
    ))

    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _CONVERTER,
             '--config', LaunchConfiguration('config_file'),
             '--cmd-topic', '/cmd_vel_gated',
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='cmd_vel_to_tricycle', output='screen',
    ))

    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _FORKLIFT_IO,
             '--config', LaunchConfiguration('config_file'),
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='forklift_io', output='screen',
        condition=IfCondition(LaunchConfiguration('io')),
    ))

    # HANDLER FIRST, EMIT LAST - localization.launch.py's ordering, kept
    # for its measured reason: a transition that completes before its
    # handler is registered goes unheard and the chain stops dead with
    # nothing in the log that reads as an error.
    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=smoother,
            start_state='configuring', goal_state='inactive',
            entities=[
                LogInfo(msg='velocity_smoother configured; activating'),
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(smoother),
                    transition_id=Transition.TRANSITION_ACTIVATE)),
            ],
        ),
    ))
    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=smoother,
            start_state='activating', goal_state='active',
            entities=[LogInfo(
                msg='envelope stack active. The check is that '
                    '/cmd_vel_gated exists AND that it carries zero until '
                    'an envelope is published: the gate boots '
                    'NON-PERMISSIVE, and a vehicle that moves before any '
                    'envelope has been seen is the defect this stack '
                    'exists to catch.')],
        ),
    ))
    ld.add_action(EmitEvent(event=ChangeState(
        lifecycle_node_matcher=matches_action(smoother),
        transition_id=Transition.TRANSITION_CONFIGURE)))

    return ld
