# vehicle_image.launch.py - EVERYTHING THE VEHICLE'S OWN COMPUTER RUNS.
#
# ADR 0016 Phase 1. There are now two sides to a run, and this is the vehicle
# one:
#
#   the SIM side      Gazebo, the world, and nothing else. No ROS vehicle node
#                     runs there and it joins no DDS domain at all, because gz
#                     transport is not DDS. It is the warehouse floor.
#
#   the VEHICLE IMAGE (this file) the vehicle's gz bridges INCLUDING /clock,
#                     sensor TF, wheel odometry, the gyro gate, the EKF, the
#                     map server and AMCL, the whole Nav2 stack, the envelope
#                     gate, the Twist->tricycle converter and forklift_io -
#                     all of it inside THIS vehicle's own DDS domain.
#
# On a real forklift the two are two machines and nobody has to be told so.
# Here the separation is made real by the domain: a process outside it cannot
# see, publish into or accidentally subscribe to this vehicle's graph. The
# boundary fails CLOSED, like a separate machine's, and not open like a naming
# convention (ADR 0016 D1). EVIDENCE_VEHICLE_IMAGE.md section 3 is that
# boundary being demonstrated by failing to cross it.
#
# THE IDENTITY IS INJECTED, NOT COMPILED IN. Serial number, spawn pose and
# initial pose come from vehicles/<serial>.yaml; the domain comes from
# vehicles/allocation.yaml, which is the single owner of the serial -> domain
# mapping. No per-vehicle string appears in this file or in any node it starts
# (ADR 0016 D2, invariant 10).
#
# HOW TO START IT, AND WHY NOT DIRECTLY
#
#   python3 agv/forklift/scripts/vehicle_image.py --vehicle F001
#
# That launcher is the stand-in for the systemd unit a real vehicle would run
# (ADR 0016 D5). It exists because ROS_DOMAIN_ID has to be set BEFORE
# `ros2 launch` starts: launch_ros' own node is what transitions the seven
# lifecycle nodes below, so it has to be in the same domain as they are, and a
# domain set from inside the launch would leave it outside. Starting this file
# by hand still works - `ROS_DOMAIN_ID=<the allocated one> ros2 launch ...` -
# and starting it with the WRONG domain, or none, is a refusal rather than a
# vehicle that comes up healthy in somebody else's graph.
#
# WHAT IT DOES NOT START, AND THAT LIST IS THE POINT
#
#   no Gazebo server        the sim side owns the world (`server:=false`
#                           below). One world, one GZ_PARTITION, shared,
#                           exactly as one warehouse floor is shared
#   no second vehicle       Phase 1 is one vehicle behind a real wall; two is
#                           Phase 2, and it needs model.sdf's fixed gz topic
#                           names to become per-instance values first
#   no bridge, no fleet,    those cross the boundary and each crossing is
#   no HMI, no OPC UA       named in ADR 0016 D3. None of them is here
#
# GZ_PARTITION IS NOT SET HERE AND IS NOT PER-VEHICLE. It is the SIMULATOR's
# boundary and the world is shared, so every vehicle image and the sim side
# run in ONE partition, inherited from the environment. ROS_DOMAIN_ID isolates
# DDS and GZ_PARTITION isolates gz transport; they are different transports
# and one does not do the other's job (docs/LESSONS.md 2026-07-27).
#
# THIS FILE CONTAINS NO CONTROL LOGIC AND NO TUNING. It starts processes and
# passes an identity. Every threshold, gain and window is in config.yaml,
# nav2.yaml, amcl.yaml or ekf.yaml, and the protective stop is onboard and
# hardwired and appears in no launch file (invariant 1).

import os
import sys

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription, LogInfo, OpaqueFunction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_FORKLIFT_DIR = os.path.normpath(os.path.join(_THIS_DIR, '..'))
_SCRIPTS_DIR = os.path.join(_FORKLIFT_DIR, 'scripts')

# One reader of the allocation table, shared with the launcher. See its
# module docstring for why every failure of the lookup is a refusal.
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)
import vehicle_identity  # noqa: E402

_VEHICLE_LAUNCH = os.path.join(_THIS_DIR, 'vehicle.launch.py')
_LOCALIZATION_LAUNCH = os.path.join(_THIS_DIR, 'localization.launch.py')
_NAVIGATION_LAUNCH = os.path.join(_THIS_DIR, 'navigation.launch.py')


def _scoped(include, condition=None):
    """Include a launch file in its OWN launch-configuration scope.

    THIS IS NOT TIDINESS. IT IS A MEASURED DEFECT, FOUND ON THE FIRST RUN OF
    THIS FILE. `IncludeLaunchDescription` on Jazzy does NOT scope launch
    configurations: its `execute` returns the SetLaunchConfiguration actions
    followed by the included description, with no push/pop around them. And
    `DeclareLaunchArgument` only applies its default when the configuration is
    not already set. So when one launch file is included after another and
    both declare an argument of the SAME NAME, the second silently inherits
    the first one's value.

    localization.launch.py and navigation.launch.py both declare
    `params_file`. Included plainly and in that order, Nav2's planner,
    controller, behaviour server and smoother were all started with
    amcl.yaml - a file that says nothing about any of them. There was no
    error: every node came up, the planner reported
    `GridBased of type nav2_navfn_planner::NavfnPlanner` (nav2's DEFAULT, not
    this vehicle's SmacPlannerHybrid) and the costmaps waited 60 s for
    `base_link`, the DEFAULT frame, which does not exist on this vehicle. A
    stack running entirely on defaults looks exactly like a stack running on
    its parameter file until you read what it says it loaded.

    A GroupAction with `scoped=True` pushes and pops the configuration stack
    around the include, so each included file resolves its own defaults. The
    alternative - passing every colliding argument explicitly from here -
    would copy the two parameter-file paths into a third file and is exactly
    the duplication invariant 10 forbids.
    """
    return GroupAction([include], scoped=True, condition=condition)


def _vehicle_image(context, *args, **kwargs):
    serial = LaunchConfiguration('vehicle').perform(context).strip()
    vehicles_dir = LaunchConfiguration('vehicles_dir').perform(context).strip()

    identity = vehicle_identity.load_identity(serial, vehicles_dir or None)
    # Refuses unless the environment we were handed IS this vehicle's domain.
    # Checked before a single process starts.
    domain = vehicle_identity.check_environment_domain(identity)

    actions = [LogInfo(msg=(
        '\n---- vehicle image ----\n{}\n'
        '{} in force            {}\n'
        'GZ_PARTITION           {}\n'
        '-----------------------').format(
            identity.describe(), vehicle_identity.DOMAIN_ENV, domain,
            os.environ.get('GZ_PARTITION', '(unset - the sim side and this '
                                           'vehicle must share one)')))]

    # ---- the plant-facing half: spawn, bridges (incl. /clock), estimator ----
    #
    # vehicle.launch.py already states this vehicle's whole topic contract in
    # one bridge table, so the vehicle image INCLUDES it rather than restating
    # it. A bridge table that exists twice is a bridge table that drifts.
    #
    #   server:=false   the sim side started the world; this is a machine
    #                   arriving on a floor that already exists
    #   nodes:=true     forklift_io and obstacle_zone are the vehicle's own
    #                   process nodes, so they belong to the image. The Nav2
    #                   include below therefore runs with io:=false - exactly
    #                   one publisher of the raw joint commands
    actions.append(_scoped(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(_VEHICLE_LAUNCH),
        launch_arguments={
            'server': 'false',
            'world_name': LaunchConfiguration('world_name'),
            'x': repr(identity.spawn['x_m']),
            'y': repr(identity.spawn['y_m']),
            'z': repr(identity.spawn['z_m']),
            'yaw': repr(identity.spawn['yaw_rad']),
            'nodes': 'true',
            'tf': 'true',
            'wheel_odom': 'true',
            'imu_gate': 'true',
            'ekf': 'true',
        }.items(),
    )))

    # ---- localization: the frozen map and AMCL ----
    #
    # The initial pose is in the MAP frame, which is what an operator gives a
    # real vehicle and all a real vehicle could know. The per-vehicle config
    # carries it as a derived value and says which command derived it; the
    # world -> map conversion stays out of the vehicle's bringup, because it
    # exists only because this is a simulation.
    actions.append(_scoped(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(_LOCALIZATION_LAUNCH),
        launch_arguments={
            'initial_pose_x': repr(identity.initial_pose['x_m']),
            'initial_pose_y': repr(identity.initial_pose['y_m']),
            'initial_pose_yaw': repr(identity.initial_pose['yaw_rad']),
        }.items(),
    ), condition=IfCondition(LaunchConfiguration('localization'))))

    # ---- navigation: Nav2, the envelope gate, the converter ----
    #
    # io:=false because the include above already started forklift_io. Two of
    # them would be two publishers of the model's raw joint commands, which is
    # invariant 10's failure case on the actuator path and produces no error
    # anywhere.
    actions.append(_scoped(IncludeLaunchDescription(
        PythonLaunchDescriptionSource(_NAVIGATION_LAUNCH),
        launch_arguments={
            'io': 'false',
        }.items(),
    ), condition=IfCondition(LaunchConfiguration('navigation'))))

    return actions


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'vehicle', default_value='F001',
        description='Serial number of the vehicle to start. It selects '
                    'vehicles/<serial>.yaml and is looked up in '
                    'vehicles/allocation.yaml for the DDS domain. It is the '
                    'VDA 5050 serialNumber, so the vehicle has one identity '
                    'and not an internal second one.'))
    ld.add_action(DeclareLaunchArgument(
        'vehicles_dir', default_value='',
        description='Directory holding allocation.yaml and the per-vehicle '
                    'config files. Empty uses agv/forklift/vehicles/.'))
    ld.add_action(DeclareLaunchArgument(
        'world_name', default_value='',
        description='Name of the <world> element to spawn into. Empty lets '
                    'the spawn discover it from the running sim side, which '
                    'stays correct when the sim side changes world.'))
    ld.add_action(DeclareLaunchArgument(
        'localization', default_value='true',
        description='Start the map server and AMCL. FALSE gives a vehicle '
                    'that estimates its own motion and does not know where '
                    'it is on a map - which is the m5-07 configuration, not '
                    'a degraded autonomous one.'))
    ld.add_action(DeclareLaunchArgument(
        'navigation', default_value='true',
        description='Start Nav2, the envelope gate and the converter. FALSE '
                    'leaves the plant and the estimator up with nothing that '
                    'can command motion.'))

    ld.add_action(OpaqueFunction(function=_vehicle_image))
    return ld
