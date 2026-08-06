# vehicle.launch.py - bring up one simulated forklift and its vehicle nodes.
#
# What this launch starts:
#   1. the Gazebo (gz sim) server on a world, headless by default,
#   2. one spawn of agv/forklift/model.sdf into that world,
#   3. one ros_gz_bridge carrying every topic this directory owns,
#   3b. a SECOND, switchable ros_gz_bridge carrying the simulator's
#      ground-truth odom -> base_link transform onto /tf. RETIRED: it is
#      off by default since the EKF took that edge over, and asking for
#      both is a launch-time refusal, not a warning,
#   4. scripts/wheel_odometry.py, scripts/imu_gate.py and
#      robot_localization's ekf_node - the vehicle's own motion estimate,
#      and the SOLE publisher of forklift/odom -> forklift/base_link,
#   5. scripts/sensor_tf.py, the static TF for the four sensor frames,
#   6. scripts/forklift_io.py and scripts/obstacle_zone.py.
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
                            IncludeLaunchDescription, OpaqueFunction)
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
_TF_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'sensor_tf.py')
_FIELD_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'field_evaluation.py')
_WHEEL_ODOM_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'wheel_odometry.py')
_IMU_GATE_SCRIPT = os.path.join(_FORKLIFT_DIR, 'scripts', 'imu_gate.py')
_EKF_YAML = os.path.join(_FORKLIFT_DIR, 'ekf.yaml')

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
    '{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'.format(
        _TOPICS['gz_safety_scanner_front_measurement']),
    '{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan'.format(
        _TOPICS['gz_safety_scanner_rear_measurement']),
    '{}@sensor_msgs/msg/Imu[gz.msgs.IMU'.format(_TOPICS['gz_imu']),
]

# WHAT IS AND IS NOT ON THAT LIST, PER CHANNEL.
#
# Each safety scanner models a device with TWO outputs: a safe one and a
# separate NON-SAFE MEASUREMENT channel provided for HMI, diagnostics and
# process use. The gz scan IS the measurement channel.
#
#   front measurement channel  bridged, because a process consumer exists
#                              for it: obstacle_zone.py, whose plane this
#                              is (owner ruling, 2026-07-30)
#   rear measurement channel   BRIDGED 2026-08-06 (m5-12b), under the name
#                              config.yaml reserved for it. The rule did
#                              not change - a channel is bridged when
#                              something on the process side consumes it -
#                              what changed is that the consumer now
#                              exists: scripts/field_evaluation.py needs
#                              BOTH devices, because the protective
#                              verdict is the union of the two and the
#                              fork direction is the rear device's to
#                              watch
#   either SAFE channel        NEVER a topic, on either transport, under
#                              any path. It is derived by field
#                              evaluation from the same rays as the
#                              measurement channel and reaches the
#                              F-program off the process network
#
# BRIDGING THE REAR MEASUREMENT CHANNEL IS NOT A SAFE CHANNEL APPEARING ON
# THE NETWORK. It is the same non-safe distance profile its front twin
# already carried; what field_evaluation.py DERIVES from the two of them
# is the safe-shaped verdict, and that verdict has no topic and crosses
# one dedicated TCP link to the stand-in writer instead
# (plc/forklift-safety/SPEC.md section 7.2). The prohibition that matters
# is likewise unchanged: no scanner channel feeds a NAVIGATION consumer,
# and the navigation lidar remains the only input SLAM, AMCL and the
# costmaps get.
#
# BY WHICH PATH the safe channel reaches the F-program was DESIGN INTENT
# and is now settled, and nothing on the bridge list above depends on the
# answer either way. ADR 0011 decision 2 named configured F-I/O (an
# ET 200SP F-DI parameterised as the scanner's OSSD pair) driven by tag
# name through the S7-PLCSIM Advanced API. plc/forklift-safety/
# FIO-FEASIBILITY.md ran that probe in the tool and the named fallback is
# what stands: the standard-DB stand-in of plc/forklift-safety/SPEC.md,
# written by the stand-in writer, labelled a stand-in wherever it appears.
# This launch file bridges no safe channel under either answer.
#
# THE odom -> base_link TRANSFORM IS NOT ON THAT LIST. It has a bridge
# node of its own, below, because it is INTERIM and the second node is
# the switch that retires it. See the block above that node.
#
# Bridging a measurement channel is not a safety signal on the process
# network, and it is not a navigation consumer of a safety scanner either
# - what ADR 0011 forbids is SLAM, AMCL or a costmap fed from one of
# these, and the navigation lidar remains the only input any of those
# gets.

# THE RETIRED INTERIM MOTION ESTIMATE. THE SWITCH WAS THROWN ON
# 2026-07-31 AND THIS NODE IS NOW OFF BY DEFAULT.
#
# model.sdf's OdometryPublisher publishes odom -> base_link as
# gz.msgs.Pose_V, from the same simulator pose that fills
# /forklift/gz/odom. That is GROUND TRUTH: no wheel slip, no encoder
# quantisation, no drift. Between briefs m5-07b and m5-07c it was the
# vehicle's only motion estimate, because nothing on board could produce
# one and SLAM cannot start without one, so it was bridged onto /tf as a
# SCAFFOLD, behind this switch, so that retiring it would be a launch
# argument rather than an edit.
#
# Brief m5-07c landed the IMU, the wheel odometry and the EKF that fuses
# them. THE EKF NOW OWNS odom -> base_link. `ground_truth_tf` therefore
# defaults to FALSE, the node below does not run, and /tf carries exactly
# one publisher of that edge. The gz topic keeps publishing and is now the
# REFERENCE that estimator error is measured against, which was the whole
# reason the EKF was worth building: measured against its own input, an
# estimator cannot be wrong.
#
# One datum, one owner, at any instant (invariant 10). A default is not a
# guarantee, so the handover is enforced rather than documented: the
# _refuse_two_transform_sources check below aborts the launch outright if
# both this bridge and the EKF are asked for. Two publishers of one edge
# on /tf is the failure this whole separation exists to prevent, and it
# is the kind that produces a jittering robot and no error message.
#
# WHAT IT IS STILL FOR. `ground_truth_tf:=true ekf:=false` is a
# deliberate, exclusive configuration and it is how the m5-07b evidence
# is reproduced. It is not a fallback for a misbehaving EKF: a stack that
# navigates on ground truth is not demonstrating navigation.
#
# The remap onto /tf is not cosmetic: /tf is the only topic a
# TransformListener reads, and the moving transform has to arrive there
# while the STATIC sensor transforms arrive on /tf_static from
# sensor_tf.py. Two topics, two halves of one tree.
_TF_BRIDGE_ARGS = [
    '{}@tf2_msgs/msg/TFMessage[gz.msgs.Pose_V'.format(
        _TOPICS['gz_tf_ground_truth']),
]
_TF_BRIDGE_REMAPS = [
    (_TOPICS['gz_tf_ground_truth'], _TOPICS['tf']),
]

# Feedback keeps the gz name on the gz side and gets the vehicle-facing name
# on the ROS side. Commands are NOT remapped: the same name on both sides is
# what makes them recognisable as the model's raw inputs.
_BRIDGE_REMAPS = [
    (_TOPICS['gz_joint_state'], _TOPICS['joint_states']),
    (_TOPICS['gz_odom'], _TOPICS['odom']),
    (_TOPICS['gz_scan_nav'], _TOPICS['scan']),
    (_TOPICS['gz_safety_scanner_front_measurement'],
     _TOPICS['safety_scanner_front_measurement']),
    (_TOPICS['gz_safety_scanner_rear_measurement'],
     _TOPICS['safety_scanner_rear_measurement']),
    (_TOPICS['gz_imu'], _TOPICS['imu']),
]


def _gz_server(context, *args, **kwargs):
    """The gz server, with an optional noise seed.

    WHY A SEED ARGUMENT EXISTS. gz draws each sensor's bias - including
    its SIGN - from a global generator at model load, so two runs of the
    same stack get different gyro biases and a drift figure cannot be
    compared with the one before it. `gz sim --seed` fixes that draw, which
    is what makes a before-and-after measurement of an estimator change
    honest rather than a comparison of two dice. It is a MEASUREMENT
    facility and nothing on the vehicle reads it: leaving it empty, which
    is the default and what every demonstration uses, restores the random
    draw, and the sign a real device wakes up with is not knowable anyway.
    """
    server_on = LaunchConfiguration('server').perform(context).lower() == 'true'
    if not server_on:
        return []
    seed = LaunchConfiguration('seed').perform(context).strip()
    world = LaunchConfiguration('world').perform(context)
    gz_args = '-r -s '
    if seed:
        gz_args += '--seed {} '.format(seed)
    ros_gz_sim_launch = os.path.join(
        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
    return [IncludeLaunchDescription(
        PythonLaunchDescriptionSource(ros_gz_sim_launch),
        launch_arguments={
            'gz_args': gz_args + world,
            'on_exit_shutdown': 'true',
        }.items(),
    )]


def _estimator_filter(context, *args, **kwargs):
    """The EKF node, whose IMU input depends on whether the gate runs.

    ekf.yaml names /forklift/imu_gated as imu0, because the gated stream
    is what the filter is meant to fuse. With `imu_gate:=false` that topic
    has no publisher, and a filter silently running on wheel odometry
    alone is a different estimator wearing the same name - so this
    function REMAPS the filter back onto the raw IMU instead. That is the
    m5-07c configuration exactly, and it is how the before-and-after
    measurement in EVIDENCE_ODOMETRY.md section 12 is reproduced: one
    launch argument, no edit to a parameter file, and no run in which the
    filter quietly lost a sensor.
    """
    if LaunchConfiguration('ekf').perform(context).lower() != 'true':
        return []
    gate_on = LaunchConfiguration('imu_gate').perform(context).lower() == 'true'
    remaps = [('odometry/filtered', _TOPICS['odom_filtered'])]
    if not gate_on:
        remaps.append((_TOPICS['imu_gated'], _TOPICS['imu']))
    return [Node(
        package='robot_localization',
        executable='ekf_node',
        name='forklift_ekf',
        output='screen',
        parameters=[_EKF_YAML, {'use_sim_time': True}],
        remappings=remaps,
    )]


def _refuse_two_transform_sources(context, *args, **kwargs):
    """Abort the launch rather than put two publishers on one TF edge.

    `ekf` and `ground_truth_tf` both end up publishing
    forklift/odom -> forklift/base_link. Two publishers of one transform
    is invariant 10's failure case and tf2 does not complain about it: the
    listener takes whichever message arrived last, so the symptom is a
    vehicle that jitters between a perfect pose and a drifting one, with
    no error anywhere. A default is not a guarantee, so this is checked.
    """
    ekf_on = LaunchConfiguration('ekf').perform(context).lower() == 'true'
    wheel_on = LaunchConfiguration('wheel_odom').perform(
        context).lower() == 'true'
    gt_on = LaunchConfiguration('ground_truth_tf').perform(
        context).lower() == 'true'
    if ekf_on and not wheel_on:
        raise RuntimeError(
            'ekf:=true with wheel_odom:=false starts a filter with no '
            'odometry source. It would publish a transform built from the '
            'IMU yaw rate alone, which is a heading with no position in it '
            'at all - and it would still be the only publisher of that '
            'edge, so nothing downstream would notice.')
    gate_on = LaunchConfiguration('imu_gate').perform(context).lower() == 'true'
    if gate_on and not wheel_on:
        raise RuntimeError(
            'imu_gate:=true with wheel_odom:=false starts the gyro gate with '
            'nothing to publish the standstill verdict it gates on. The gate '
            'fails open, so the stack would run with the gate present and '
            'permanently ineffective - which looks like a working stationary '
            'correction and is not one. Run imu_gate:=false, or leave the '
            'wheel odometry on.')
    if ekf_on and gt_on:
        raise RuntimeError(
            'ekf:=true and ground_truth_tf:=true would both publish '
            'forklift/odom -> forklift/base_link. Exactly one source owns '
            'that edge (CLAUDE.md invariant 10). Use ekf:=true (the '
            'default, the vehicle estimating its own pose) or '
            'ekf:=false ground_truth_tf:=true (the retired m5-07b '
            'configuration, for reproducing that evidence only).')
    return []


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
    ld.add_action(DeclareLaunchArgument(
        'tf', default_value='true',
        description='Publish /tf_static for the three sensor frames. '
                    'Separate from "nodes" because SLAM and Nav2 need the '
                    'transforms even when the two process nodes are off.'))
    ld.add_action(DeclareLaunchArgument(
        'ground_truth_tf', default_value='false',
        description='Bridge the simulator ground-truth odom -> base_link '
                    'transform onto /tf. RETIRED 2026-07-31: the EKF owns '
                    'that edge now, so this defaults to false and the '
                    'ground-truth stream stays only as the reference '
                    'estimator error is measured against. Setting it true '
                    'requires ekf:=false and the launch refuses otherwise.'))
    ld.add_action(DeclareLaunchArgument(
        'wheel_odom', default_value='true',
        description='Start scripts/wheel_odometry.py, the vehicle\'s '
                    'tricycle dead reckoning. It publishes an estimate and '
                    'NO transform. Separate from "ekf" so the odometry can '
                    'be verified on its own before a filter consumes it, '
                    'which is this gate\'s sequencing rule.'))
    ld.add_action(DeclareLaunchArgument(
        'ekf', default_value='true',
        description='Start the robot_localization EKF fusing the wheel '
                    'odometry with the IMU. It is the sole publisher of '
                    'forklift/odom -> forklift/base_link, and it needs '
                    'wheel_odom:=true.'))
    ld.add_action(DeclareLaunchArgument(
        'imu_gate', default_value='true',
        description='Start scripts/imu_gate.py, which stops offering the '
                    'gyro\'s yaw rate to the filter while both encoder '
                    'counts are unchanged - the interval in which that '
                    'reading is bias and not rotation. Setting it false '
                    'remaps the filter back onto the raw IMU and reproduces '
                    'the m5-07c configuration exactly; it does not leave the '
                    'filter without an IMU.'))
    ld.add_action(DeclareLaunchArgument(
        'field_evaluation', default_value='false',
        description='Start scripts/field_evaluation.py, the protective- and '
                    'warning-field evaluation of '
                    'agv/forklift/FIELD-EVALUATION.md phases 1 and 2. It is a '
                    'MODEL of what a safety-rated scanner does internally, '
                    'feeding a STAND-IN FOR WIRING, and it is not a safety '
                    'function: no Category, no Performance Level, no SIL, no '
                    'PFH (ADR 0011 D5). The PROTECTIVE verdict publishes no '
                    'topic - it crosses one dedicated TCP link to the '
                    'stand-in writer, which has to be listening on the '
                    'Windows host, and that is why this is off by default. '
                    'The WARNING verdict is process data and does have a '
                    'topic, /forklift/warning_field/occupied, published at '
                    'the evaluation tick so that its absence is visible.'))
    ld.add_action(DeclareLaunchArgument(
        'seed', default_value='',
        description='Noise seed passed to gz sim, fixing the sign and value '
                    'each sensor bias is drawn with. Empty (the default) '
                    'leaves the draw random, which is what a real device '
                    'does. It exists so a before-and-after measurement of '
                    'the estimator compares two runs of one vehicle rather '
                    'than two draws.'))

    # `world` and `server` are not resolved here: _gz_server reads both,
    # because the seed has to change the command line rather than a
    # substitution inside it.
    world_name = LaunchConfiguration('world_name')
    model = LaunchConfiguration('model')
    config = LaunchConfiguration('config')
    name = LaunchConfiguration('name')
    gui = LaunchConfiguration('gui')
    nodes = LaunchConfiguration('nodes')
    tf = LaunchConfiguration('tf')
    ground_truth_tf = LaunchConfiguration('ground_truth_tf')
    wheel_odom = LaunchConfiguration('wheel_odom')
    imu_gate = LaunchConfiguration('imu_gate')

    # Checked before anything starts, so a misconfiguration is a refusal
    # and not a running stack with two answers to one question.
    ld.add_action(OpaqueFunction(function=_refuse_two_transform_sources))

    ros_gz_sim_launch = os.path.join(
        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')

    # Gazebo server, headless, running immediately (-r -s). Built in a
    # function rather than declared, because the optional --seed has to be
    # absent from the command line entirely when no seed is asked for.
    ld.add_action(OpaqueFunction(function=_gz_server))

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

    # The interim ground-truth motion estimate, on its own bridge node so
    # that the EKF of the next brief retires it with ground_truth_tf:=false
    # rather than with an edit. See the block above _TF_BRIDGE_ARGS.
    ld.add_action(Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='forklift_ground_truth_tf_bridge',
        output='screen',
        arguments=_TF_BRIDGE_ARGS,
        remappings=_TF_BRIDGE_REMAPS,
        condition=IfCondition(ground_truth_tf),
    ))

    # ---- the vehicle's own motion estimate, in two processes ----
    #
    # THE ONLY PUBLISHER OF forklift/odom -> forklift/base_link IS THE EKF.
    # wheel_odometry.py publishes an Odometry message and NO transform;
    # it is one sensor's opinion, like the IMU, and the EKF fuses the two.
    #
    # BOTH CARRY use_sim_time EXPLICITLY, and it is not optional. Every
    # message in this stack is stamped with the simulation clock. A node
    # on the system clock differences two clocks, asks tf2 for a transform
    # 1.8e9 s in the future and is told the transform does not exist -
    # which reads as a missing publisher rather than as a misconfigured
    # node, and cost brief m5-07b a debugging session (its report, "two
    # findings that belong to every future consumer of this tree").
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _WHEEL_ODOM_SCRIPT, '--config', config,
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='wheel_odometry',
        output='screen',
        condition=IfCondition(wheel_odom),
    ))
    # THE GYRO GATE, between the bridge's IMU and the filter. It publishes
    # /forklift/imu_gated, which is the topic ekf.yaml names, and it
    # forwards every sample unchanged except while the wheel odometry
    # reports the wheels standing still - the drive count's spread zero
    # and the steer count's at most one over a trailing 0.50 s window.
    # It carries use_sim_time for the
    # same reason the two nodes above do, and for one more: its freshness
    # test compares a simulated stamp against its own clock, and on the
    # system clock it would find every verdict 1.8e9 s stale and gate
    # nothing, silently, for ever.
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _IMU_GATE_SCRIPT, '--config', config,
             '--ros-args', '-p', 'use_sim_time:=true'],
        name='imu_gate',
        output='screen',
        condition=IfCondition(imu_gate),
    ))
    ld.add_action(OpaqueFunction(function=_estimator_filter))

    # Static TF for the three sensor frames, read out of the model file
    # itself so the transforms cannot drift from the geometry. It takes
    # the model path rather than the config path for that reason: there
    # is no second copy of a pose anywhere in this launch file.
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _TF_SCRIPT, '--model', model],
        name='sensor_tf',
        output='screen',
        condition=IfCondition(tf),
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

    # ---- the protective-field evaluation (m5-12 phase 1) ----
    #
    # OFF BY DEFAULT, AND DELIBERATELY SO. This node dials a TCP link to
    # the stand-in writer on the Windows host; in every run that is not
    # exercising the safety chain there is no writer to dial, and a node
    # logging a refused connection once a second in every M4 and M5 run
    # would be noise nobody reads. Asking for it explicitly also means the
    # criterion-(a) evidence records the argument that turned it on rather
    # than inheriting a default.
    #
    # IT PUBLISHES NOTHING. The protective verdict has no ROS topic on
    # either transport (owner ruling m5-06, checked by
    # scripts/check_sensor_frames.py section 4); it crosses one dedicated
    # link, as a real device's OSSD pair crosses only its own copper. So
    # turning this node on adds no topic to the graph and takes nothing
    # away from obstacle_zone.py, which keeps reading the front
    # measurement channel untouched.
    #
    # use_sim_time is not optional here. The freshness rule compares a
    # simulated stamp against this node's own clock; on the system clock
    # every scan would read 1.8e9 s stale and the verdict would sit at
    # INTRUSION for ever, which is the safe direction but is not an
    # evaluation.
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _FIELD_SCRIPT, '--config', config,
             '--model', model, '--ros-args', '-p', 'use_sim_time:=true'],
        name='field_evaluation',
        output='screen',
        condition=IfCondition(LaunchConfiguration('field_evaluation')),
    ))

    return ld
