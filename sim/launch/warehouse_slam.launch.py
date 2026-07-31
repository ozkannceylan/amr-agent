# warehouse_slam.launch.py - slam_toolbox online_async over the warehouse.
#
# ONE NODE. It starts `async_slam_toolbox_node` with
# sim/config/slam_toolbox_warehouse.yaml against a warehouse bringup that is
# ALREADY RUNNING, and it starts nothing else. The plant, the vehicle, the
# IMU bridge and the estimator are sim/launch/warehouse_bringup.launch.py's;
# putting them here too would give this repository two bringups for one
# world, which is exactly the drift warehouse_bringup.launch.py's own header
# refuses for bridge tables.
#
#   terminal 1:  ros2 launch sim/launch/warehouse_bringup.launch.py
#   terminal 2:  ros2 launch sim/launch/warehouse_slam.launch.py
#
# WHY online_async AND NOT online_sync. `online_sync` processes each scan
# inside its subscription callback. Rendering here is llvmpipe software
# rasterisation (sim/setup/CONTAINER_TOOLCHAIN.md section 4.6), the real
# time factor is well under 1, and a scan match that overruns the 0.1 s scan
# period stalls the callback; the queue then grows without bound and the
# node stops keeping up rather than dropping scans. `online_async` runs the
# matcher off the callback thread and drops what it cannot keep up with,
# which is the correct degradation for a mapping run.
#
# use_sim_time IS SET HERE AND IT IS NOT OPTIONAL. Every message in this
# stack is stamped with the simulation clock. A node left on the system
# clock differences two clocks, asks tf2 for a transform ~1.8e9 s in the
# future and is told the transform does not exist - which reads as a missing
# publisher or a broken TF tree and is neither. The same applies to anything
# else started beside this: a recorder, a map saver client, `ros2 topic hz`.
#
# WHAT THIS NODE PUBLISHES ON /tf, AND WHAT IT DOES NOT. It publishes
# map -> forklift/odom. It does NOT publish forklift/odom ->
# forklift/base_link: that edge belongs to the EKF (agv/forklift/ekf.yaml,
# invariant 10) and this node reads it. So a bringup plus this launch shows
# TWO publishers on /tf carrying two DISJOINT edges, and the bringup alone
# shows one. sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md section 3 captures both
# counts rather than asserting them.
#
# WHAT REACHES THIS NODE. One topic: /forklift/scan, the navigation lidar at
# z = 1.80 m. No safety scanner channel, and no ground truth - not
# /forklift/odom (which is the simulator's own pose despite its name), not
# /forklift/gz/tf_ground_truth, and nothing derived from either. The pose
# prior this node corrects is the EKF's drifting estimate and nothing else.
#
# SAVING THE TWO ARTIFACTS, once the route has been driven:
#
#   ros2 service call /slam_toolbox/save_map slam_toolbox/srv/SaveMap \
#       "{name: {data: '/abs/path/warehouse'}}"
#   ros2 service call /slam_toolbox/serialize_map \
#       slam_toolbox/srv/SerializePoseGraph \
#       "{filename: '/abs/path/warehouse'}"
#
# The first writes warehouse.pgm + warehouse.yaml, which is what AMCL
# consumes. The second writes warehouse.posegraph + warehouse.data, which is
# what lets mapping RESUME rather than restart. Both are wanted; neither
# substitutes for the other.
#
# THE NODE IS A LIFECYCLE NODE AND MUST BE TRANSITIONED, AND THIS IS THE
# SILENT FAILURE OF THIS FILE. In slam_toolbox 2.8.5 on Jazzy,
# `async_slam_toolbox_node` is a LifecycleNode. Started as a plain Node it
# comes up UNCONFIGURED and stays there: it logs
# `Node using stack size 40000000`, exits nothing, warns nothing, creates
# no subscription to the scan, advertises no /map and publishes no
# transform. The only visible difference between that and a working node is
# that `ros2 topic list` shows /slam_toolbox/transition_event and nothing
# else of it. This file was written with a plain Node first and produced
# exactly that; sim/setup/CONTAINER_TOOLCHAIN.md section 4.7 had already
# recorded the same state without naming the cause.
#
# So the two lifecycle transitions below are not boilerplate copied from
# the vendor launch file - they are the difference between a mapping run
# and a 3-minute drive that maps nothing. The CHECK that this file works is
# that /map and /slam_toolbox/graph_visualization appear on
# `ros2 topic list` and that map -> forklift/odom appears on /tf, never a
# clean-looking log.
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
from launch.substitutions import (AndSubstitution, LaunchConfiguration,
                                  NotSubstitution)
from launch_ros.actions import LifecycleNode
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState

from lifecycle_msgs.msg import Transition

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_PARAMS = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'config', 'slam_toolbox_warehouse.yaml'))


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'params_file', default_value=_DEFAULT_PARAMS,
        description='Absolute path to the slam_toolbox parameter file. Its '
                    'non-default values each carry their reason in the file.'))
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='Read the clock from /clock. Leaving this false against '
                    'a simulation produces "missing transform" errors that '
                    'look like a TF bug and are not one.'))
    ld.add_action(DeclareLaunchArgument(
        'autostart', default_value='true',
        description='Configure and activate the node from here. FALSE LEAVES '
                    'IT UNCONFIGURED AND SILENT - it will map nothing and '
                    'report nothing. Ignored when use_lifecycle_manager is '
                    'true.'))
    ld.add_action(DeclareLaunchArgument(
        'use_lifecycle_manager', default_value='false',
        description='Let a Nav2 lifecycle_manager own the transitions '
                    'instead. Off here because no Nav2 stack runs against '
                    'this world yet (m5-10), and because a bond heartbeat '
                    'starves at the real time factors this host reaches '
                    '(sim/README.md).'))

    autostart = LaunchConfiguration('autostart')
    use_lifecycle_manager = LaunchConfiguration('use_lifecycle_manager')

    slam = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        namespace='',
        output='screen',
        parameters=[
            LaunchConfiguration('params_file'),
            {
                'use_sim_time': LaunchConfiguration('use_sim_time'),
                'use_lifecycle_manager': use_lifecycle_manager,
            },
        ],
    )
    ld.add_action(slam)

    # unconfigured -> inactive
    ld.add_action(EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam),
            transition_id=Transition.TRANSITION_CONFIGURE),
        condition=IfCondition(
            AndSubstitution(autostart,
                            NotSubstitution(use_lifecycle_manager))),
    ))

    # inactive -> active, once the node reports it reached inactive. Chained
    # on the state transition rather than on a delay, because a delay long
    # enough to be safe is a delay nobody can justify.
    ld.add_action(RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam,
            start_state='configuring',
            goal_state='inactive',
            entities=[
                LogInfo(msg='slam_toolbox configured; activating'),
                EmitEvent(event=ChangeState(
                    lifecycle_node_matcher=matches_action(slam),
                    transition_id=Transition.TRANSITION_ACTIVATE)),
            ],
        ),
        condition=IfCondition(
            AndSubstitution(autostart,
                            NotSubstitution(use_lifecycle_manager))),
    ))

    return ld
