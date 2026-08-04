# localization.launch.py - the vehicle's localization stack.
#
# TWO NODES. `nav2_map_server/map_server` serves the FROZEN committed grid,
# and `nav2_amcl/amcl` localises the vehicle in it. Both read
# agv/forklift/amcl.yaml, where every non-default carries its reason.
#
# THIS IS THE VEHICLE'S STACK AND IT LIVES IN agv/. It is started AGAINST a
# bringup that is already running; it starts no plant, no vehicle, no bridge
# and no estimator. Those are sim/launch/warehouse_bringup.launch.py's, and
# a second copy of them here would give this repository two bringups for one
# world - the same drift that file's own header refuses.
#
#   terminal 1:  ros2 launch sim/launch/warehouse_bringup.launch.py
#   terminal 2:  ros2 launch agv/forklift/launch/localization.launch.py \
#                    initial_pose_x:=... initial_pose_y:=... \
#                    initial_pose_yaw:=...
#
# WHAT IT REFERENCES OUTSIDE agv/, AND HOW. Exactly one thing: the map. The
# `map` argument defaults to sim/maps/warehouse/warehouse.yaml, which is
# READ and never written. sim/maps/warehouse/ owns the grid, its .yaml and
# its registration (invariant 10); this file consumes the first two and does
# not touch the third at all - see "THE INITIAL POSE IS IN THE MAP FRAME"
# below for why that matters.
#
# WHAT PUBLISHES WHAT ON /tf, AND WHY THE COUNT IS TWO
#
#   forklift/odom -> forklift/base_link   the EKF, and only the EKF
#   map           -> forklift/odom        amcl, and only amcl
#
#   Two publishers, two DISJOINT edges. A bringup alone shows one publisher;
#   a bringup plus this launch shows two. If a run ever shows two publishers
#   of the SAME edge, the tf listener silently takes whichever message
#   arrived last and the pose becomes a coin toss - which is why the count
#   and the edge list are captured in the evidence rather than asserted.
#
# THE INITIAL POSE IS IN THE MAP FRAME, AND THAT IS NOT AN OVERSIGHT
#
#   AMCL is told where it starts in the frame of the map it is given, which
#   is what an operator does in the field and all a real vehicle could ever
#   know. There is no world frame on a real forklift and there is no
#   T(world -> map) on one either.
#
#   In THIS simulation a world frame exists, because the reference the
#   scorer uses is the simulator's own pose. Converting a world pose into a
#   map pose is therefore a MEASUREMENT-HARNESS job, and it is done in
#   agv/forklift/scripts/localization_run.py (`map-pose`), which reaches the
#   committed transform through the module that derived it. Deliberately not
#   here: putting that conversion in the vehicle's launch file would make
#   the vehicle's own bringup depend on a transform that exists only because
#   this is a simulation.
#
# use_sim_time IS SET ON BOTH NODES AND IT IS NOT OPTIONAL. Every message in
# this stack is stamped with the simulation clock. A node left on the system
# clock differences two clocks, asks tf2 for a transform ~1.8e9 s in the
# future and is told the transform does not exist - which reads as a missing
# publisher or a broken TF tree and is neither. amcl.yaml sets it too, so
# neither a launch-arg mistake nor a params-file mistake alone can leave a
# node on the wrong clock.
#
# BOTH NODES ARE LIFECYCLE NODES AND MUST BE TRANSITIONED. This is the
# silent failure mode sim/launch/warehouse_slam.launch.py records for
# slam_toolbox and it applies identically here: started and left
# UNCONFIGURED, `amcl` subscribes to no scan, advertises no /amcl_pose and
# publishes no transform, while logging nothing that looks wrong. The
# transitions below are chained on the observed state, not on a delay:
# map_server is activated first and amcl is configured only once map_server
# reports active, because amcl blocks in on_activate waiting for a map that
# an inactive map_server never publishes.
#
# NO nav2 lifecycle_manager. Same reason warehouse_slam.launch.py gives: a
# bond heartbeat starves at the real time factors this host reaches, and a
# manager that declares a healthy node dead is worse than no manager.
#
# THIS FILE CONTAINS NO CONTROL LOGIC. No sequencing, no interlock, no
# timer, no latch, no threshold. The protective stop is onboard and
# hardwired and appears in no launch file (invariant 1).

import os

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, EmitEvent, LogInfo,
                            RegisterEventHandler)
from launch.conditions import IfCondition
from launch.events import matches_action
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState

from lifecycle_msgs.msg import Transition

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_REPO_ROOT = os.path.normpath(os.path.join(_FORKLIFT_DIR, '..', '..'))

_DEFAULT_PARAMS = os.path.join(_FORKLIFT_DIR, 'amcl.yaml')
#: READ ONLY, and owned by sim/maps/warehouse/. The grid this launch serves
#: is the committed one; a run against a rebuilt grid is a stop-and-report,
#: because the registration the scorer uses is bound to one grid md5.
_DEFAULT_MAP = os.path.join(
    _REPO_ROOT, 'sim', 'maps', 'warehouse', 'warehouse.yaml')


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'map', default_value=_DEFAULT_MAP,
        description='Absolute path to the map YAML. READ ONLY: the grid and '
                    'its registration are owned by sim/maps/warehouse/ and '
                    'nothing here writes either. The registration is bound '
                    'to this grid\'s md5, so a rebuilt map invalidates every '
                    'score taken against it.'))
    ld.add_action(DeclareLaunchArgument(
        'params_file', default_value=_DEFAULT_PARAMS,
        description='Absolute path to the AMCL parameter file. Its '
                    'non-default values each carry their reason in the '
                    'file.'))
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Read the clock from /clock. Leaving this false against '
                    'a simulation produces "missing transform" errors that '
                    'look like a TF bug and are not one.'))
    ld.add_action(DeclareLaunchArgument(
        'autostart', default_value='true',
        description='Configure and activate both nodes from here. FALSE '
                    'LEAVES THEM UNCONFIGURED AND SILENT - amcl will '
                    'subscribe to no scan, publish no transform and report '
                    'nothing wrong.'))
    ld.add_action(DeclareLaunchArgument(
        'set_initial_pose', default_value='true',
        description='Seed the filter from the three numbers below instead '
                    'of waiting for an /initialpose message. These runs are '
                    'unattended, so there is nobody to send one.'))
    ld.add_action(DeclareLaunchArgument(
        'initial_pose_x', default_value='0.0',
        description='Initial pose x, IN THE MAP FRAME, metres. Not the '
                    'world frame: see the header.'))
    ld.add_action(DeclareLaunchArgument(
        'initial_pose_y', default_value='0.0',
        description='Initial pose y, IN THE MAP FRAME, metres.'))
    ld.add_action(DeclareLaunchArgument(
        'initial_pose_yaw', default_value='0.0',
        description='Initial pose yaw, IN THE MAP FRAME, radians. The map '
                    'is rotated from the building by the committed '
                    'registration, so this is NOT the world heading.'))

    use_sim_time = LaunchConfiguration('use_sim_time')
    autostart = LaunchConfiguration('autostart')

    # ---- the frozen map ----
    map_server = LifecycleNode(
        package='nav2_map_server',
        executable='map_server',
        name='map_server',
        namespace='',
        output='screen',
        parameters=[
            LaunchConfiguration('params_file'),
            {
                'use_sim_time': use_sim_time,
                'yaml_filename': LaunchConfiguration('map'),
            },
        ],
    )
    ld.add_action(map_server)

    # ---- the localiser ----
    amcl = LifecycleNode(
        package='nav2_amcl',
        executable='amcl',
        name='amcl',
        namespace='',
        output='screen',
        parameters=[
            LaunchConfiguration('params_file'),
            {
                'use_sim_time': use_sim_time,
                'set_initial_pose': LaunchConfiguration('set_initial_pose'),
                'initial_pose.x': LaunchConfiguration('initial_pose_x'),
                'initial_pose.y': LaunchConfiguration('initial_pose_y'),
                'initial_pose.z': 0.0,
                'initial_pose.yaw': LaunchConfiguration('initial_pose_yaw'),
            },
        ],
    )
    ld.add_action(amcl)

    # EVERY HANDLER IS REGISTERED BEFORE THE FIRST TRANSITION IS EMITTED,
    # AND THAT ORDER IS THE FIX FOR A RACE THAT COST A RUN.
    #
    # `launch` processes actions in order. A LifecycleNode's own
    # transition-event subscription is created when its action executes,
    # which is above; but an OnStateTransition handler only starts matching
    # when its RegisterEventHandler action executes. With the configure
    # event emitted BEFORE the handlers were registered - which is how
    # sim/launch/warehouse_slam.launch.py is written - a node whose
    # configure completes faster than the launch can register the next
    # handler has its transition event go unheard, and the chain simply
    # stops.
    #
    # That is not hypothetical here. `map_server` configure is a yaml parse
    # and a 606x410 PGM read; it took 26 ms. Three runs chained correctly
    # and the fourth stopped dead after "Read map ... 606 X 410", with
    # map_server INACTIVE, amcl never configured, and NOTHING in either log
    # that reads as an error. slam_toolbox never exposed this because its
    # configure is slow enough to lose the race the other way.
    #
    # So: handlers first, emit last.

    # inactive -> active, map_server. Chained on the observed transition
    # rather than on a delay, because a delay long enough to be safe is a
    # delay nobody can justify.
    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=map_server,
            start_state='configuring', goal_state='inactive',
            entities=[
                LogInfo(msg='map_server configured; activating'),
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(map_server),
                    transition_id=Transition.TRANSITION_ACTIVATE)),
            ],
        ),
        condition=IfCondition(autostart),
    ))

    # map_server active -> configure amcl. ORDER MATTERS AND THIS IS WHY:
    # amcl's on_activate waits for a map on the latched `map` topic, and an
    # inactive map_server never publishes one. Configuring amcl before
    # map_server is active leaves it blocked in a transition with no error.
    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=map_server,
            start_state='activating', goal_state='active',
            entities=[
                LogInfo(msg='map_server active; configuring amcl'),
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(amcl),
                    transition_id=Transition.TRANSITION_CONFIGURE)),
            ],
        ),
        condition=IfCondition(autostart),
    ))

    # inactive -> active, amcl
    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=amcl,
            start_state='configuring', goal_state='inactive',
            entities=[
                LogInfo(msg='amcl configured; activating'),
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(amcl),
                    transition_id=Transition.TRANSITION_ACTIVATE)),
            ],
        ),
        condition=IfCondition(autostart),
    ))

    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=amcl,
            start_state='activating', goal_state='active',
            entities=[LogInfo(
                msg='amcl active: map -> forklift/odom is now published by '
                    'amcl and by nothing else. The check that this launch '
                    'worked is that /amcl_pose and /particle_cloud appear on '
                    '`ros2 topic list` and that map -> forklift/odom appears '
                    'on /tf - never a clean-looking log.')],
        ),
        condition=IfCondition(autostart),
    ))

    # unconfigured -> inactive, map_server. LAST, so that every handler
    # above is already listening when this transition completes.
    ld.add_action(EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(map_server),
            transition_id=Transition.TRANSITION_CONFIGURE),
        condition=IfCondition(autostart),
    ))

    return ld
