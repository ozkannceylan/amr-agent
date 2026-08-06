# forklift_bringup.launch.py - M4 forklift arena bringup for amr-agent.
#
# One headless-by-default launch that puts the vehicle in
# sim/worlds/forklift_arena.sdf and on the wire.
#
# THIS FILE NO LONGER STATES A BRIDGE TABLE, AND THAT IS THE POINT OF ITS
# CURRENT SHAPE.
#
#   Until 2026-08-06 it carried its OWN copy of the ros_gz_bridge argument
#   list, written literally so that "this launch file states the whole
#   interface it carries". That copy drifted, exactly as a second copy of a
#   contract does, and the drift was not visible: brief m5-50 moved
#   model.sdf's three joint controllers off /forklift/gz/{steer,traction,
#   fork}_cmd and onto three ACTUATOR TERMINALS behind an STO contactor
#   (agv/forklift/scripts/sto_contactor.py). agv/forklift/launch/
#   vehicle.launch.py was updated in the same brief. This file was not, so a
#   vehicle brought up through here bridged three topics the model had
#   stopped listening on, started no contactor, and was DEAF at the plant -
#   with a clean log, every expected ROS topic present, and no error
#   anywhere. It bit a real run (docs/reports/m5-50-brake-and-torque-off.md,
#   request 2).
#
#   So the two lists were made ONE rather than the copy corrected. This file
#   now INCLUDES agv/forklift/launch/vehicle.launch.py, which is the single
#   place the vehicle's ROS/gz interface is written, and adds what sim/
#   actually owns: which world, where to stand in it, and which of the
#   vehicle's optional processes an arena run wants. That is the same
#   argument warehouse_bringup.launch.py already made when it stopped
#   copying THIS file's table ("a bridge table that exists twice is a bridge
#   table that drifts"), applied one layer further down.
#
#   Consequence worth knowing before debugging: every topic, remap, message
#   type and bridge-name question about this launch is answered in
#   agv/forklift/launch/vehicle.launch.py and agv/forklift/config.yaml. This
#   file owns no topic name and no message type, and it must never gain one.
#
# WHAT RUNS, THEREFORE:
#
#   1. the Gazebo (gz sim) server on sim/worlds/forklift_arena.sdf, headless
#      unless gui:=true,
#   2. one spawn of agv/forklift/model.sdf into it,
#   3. one ros_gz_bridge, named `forklift_bridge`, carrying every topic the
#      vehicle owns - INCLUDING the three actuator terminals and the rear
#      safety scanner's measurement channel, both of which this file's old
#      copy predated,
#   4. THE STO CONTACTOR, agv/forklift/scripts/sto_contactor.py. It is the
#      only publisher of the three actuator terminals, so without it nothing
#      any ROS node publishes reaches the plant. It is on by default and
#      `sto_contactor:=false` is a deliberate request for a vehicle that
#      cannot move. IT IS A STAND-IN for the hardwired onboard inhibit: no
#      Category, no Performance Level, no SIL, no PFH (ADR 0011 D5), and it
#      forms no demand - the demand is the F-program's (invariant 10),
#   5. optionally (estimator:=true) the vehicle's own pose estimate:
#      sensor_tf.py, wheel_odometry.py, imu_gate.py and the
#      robot_localization EKF, all four or none.
#
# WHY `estimator` DEFAULTS FALSE HERE AND TRUE IN THE WAREHOUSE BRINGUP.
# This is the M4 commissioning bringup and M4 carries no navigation claim
# (ADR 0008 D5); it ran without a transform tree through a closed gate, and
# turning one on by default would change what that gate's launch starts.
# M5's warehouse bringup needs one and asks for it. The argument exists so
# an arena run CAN have the same stack the warehouse one does, which is what
# docs/TODO.md's sim/ item asked for - the arena bringup no longer lacks the
# IMU bridge, the wheel odometry, the EKF, the IMU gate or the standstill
# config key, because it no longer has a second copy of any of them.
#
# THE "ALL FOUR OR NONE" RULE IS NOT RESTATED HERE, IT IS PASSED THROUGH.
# agv/forklift/ekf.yaml names /forklift/imu_gated as imu0, a topic only
# imu_gate.py publishes, and imu_gate.py gates on a verdict only
# wheel_odometry.py publishes, so a partial start is a silently different
# estimator wearing the same node name. vehicle.launch.py REFUSES the
# partial combinations outright; this file simply has no argument that can
# ask for one.
#
# WHAT DELIBERATELY DOES NOT RUN HERE:
#
#   the two vehicle process nodes. forklift_io.py and obstacle_zone.py turn
#     a raw joint value into an engineering unit and only mean something
#     with the PLC path behind them, so they are started by the harness that
#     starts that path (sim/scenarios/run_forklift_rehearsal.py, stack.sh)
#     or by agv/forklift/launch/vehicle.launch.py directly. `nodes:=false`
#     is passed to the include explicitly rather than left to a default.
#
#   the fixed-equipment cell. sim/worlds/cell.sdf and its bringup are M3 and
#     are untouched by this file. The coupled cell plus vehicle scenario is
#     roadmap M6 work (AT-07 coupled, ADR 0010) and neither world includes
#     the other.
#
#   the PLC, the bridge process and the HMI. Under ADR 0008 every command
#     reaches the simulation through HMI -> PLC standard program -> bridge,
#     and every state report returns the same way. Those are bridge/, plc/
#     and hmi/ processes; this launch only puts the plant on the wire.
#
#   Nav2, AMCL, a map and any VDA 5050 client. SLAM is launched separately
#     by sim/launch/warehouse_slam.launch.py against a running bringup, and
#     Nav2 by agv/forklift/launch/navigation.launch.py.
#
#   the ground-truth odom -> base_link TF bridge. vehicle.launch.py carries
#     it behind `ground_truth_tf`, retired 2026-07-31 and off by default
#     there; this file passes no such argument and declares none, so the
#     EKF is the only publisher of that edge in any run started here and
#     there is nothing anyone can pass to add a second (invariant 10).
#
# THIS FILE CONTAINS NO CONTROL LOGIC. No sequencing, no interlock, no
# timer, no latch, no debounce, no threshold. Every one of those belongs to
# the PLC (invariants 5, 6 and 9), and the protective stop is onboard and
# hardwired and appears in no launch file (invariant 1). The STO contactor
# above is not a counter-example: it is a stand-in for wiring, started here
# and specified nowhere in this directory.
#
# NOTE ON THE TWO SCAN TOPICS. All three scanners on the model are gpu_lidar
# sensors, so the world MUST load gz-sim-sensors-system with a render engine.
# forklift_arena.sdf does; gz's stock empty.sdf does not, and on it the
# bridge advertises the scan topics and nothing ever arrives on either.
#
# NOTE ON THE SILENT FAILURE THIS FILE HAS NOW HAD TWICE. A ros_gz_bridge
# entry for a gz topic that nobody publishes logs `Creating GZ->ROS Bridge`
# exactly as a working one does: no error, no warning, no data. It bridged
# /forklift/gz/scan for one round after m5-04 deleted that sensor
# (sim/setup/CONTAINER_TOOLCHAIN.md section 6), and it bridged the three
# retired command topics after m5-50 moved them. Both times the only symptom
# was silence. Deleting the second copy removes the mechanism; the check
# that this file works is still a MOVED VEHICLE, never a clean-looking log
# and never a node list - a stopped contactor and a genuine torque-off
# produce the identical stillness (docs/LESSONS.md 2026-08-06).
#
# Usage (after sourcing /opt/ros/jazzy/setup.bash). Isolate BOTH transports
# whenever another simulation may be running: ROS_DOMAIN_ID does not isolate
# Gazebo, because gz transport does not use DDS. GZ_PARTITION does.
#
#   export GZ_PARTITION=myrun ROS_DOMAIN_ID=42
#   ros2 launch /path/to/sim/launch/forklift_bringup.launch.py
#   ros2 launch /path/to/sim/launch/forklift_bringup.launch.py gui:=true
#   ros2 launch /path/to/sim/launch/forklift_bringup.launch.py estimator:=true

import os

from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, GroupAction,
                            IncludeLaunchDescription)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration

# The world ships in this repository next to the launch file; the vehicle,
# its model and its launch file ship in agv/forklift/. Resolve all of them
# relative to this file instead of a package share directory.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.normpath(os.path.join(_THIS_DIR, '..', '..'))
_DEFAULT_WORLD = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'worlds', 'forklift_arena.sdf')
)
_FORKLIFT_DIR = os.path.join(_REPO_ROOT, 'agv', 'forklift')
_DEFAULT_MODEL = os.path.join(_FORKLIFT_DIR, 'model.sdf')
_VEHICLE_LAUNCH = os.path.join(_FORKLIFT_DIR, 'launch', 'vehicle.launch.py')

# Spawn pose. The arena's drive aisle runs along y = 0; -6.00 puts the
# vehicle in the open west half of it, facing +x, with the whole aisle and
# the stop-zone crate ahead of it. Overridable per run: a scenario that
# wants a different start pose passes it rather than editing this file.
_SPAWN_X = '-6.00'
_SPAWN_Y = '0.00'
_SPAWN_Z = '0.05'
_SPAWN_YAW = '0.0'


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        'world', default_value=_DEFAULT_WORLD,
        description='Absolute path to the arena world SDF file'))
    ld.add_action(DeclareLaunchArgument(
        'world_name', default_value='',
        description='Name of the <world> element the model is spawned into. '
                    'Empty lets the spawn discover it from the running '
                    'server, which stays correct when world:= is overridden'))
    ld.add_action(DeclareLaunchArgument(
        'model', default_value=_DEFAULT_MODEL,
        description='Absolute path to the forklift model SDF (agv/ owns it)'))
    ld.add_action(DeclareLaunchArgument(
        'name', default_value='Forklift',
        description='Name the model is spawned under. The gz topic names do '
                    'not depend on it: model.sdf states every topic '
                    'explicitly'))
    ld.add_action(DeclareLaunchArgument(
        'x', default_value=_SPAWN_X, description='Spawn x [m]'))
    ld.add_action(DeclareLaunchArgument(
        'y', default_value=_SPAWN_Y, description='Spawn y [m]'))
    ld.add_action(DeclareLaunchArgument(
        'z', default_value=_SPAWN_Z, description='Spawn z [m]'))
    ld.add_action(DeclareLaunchArgument(
        'yaw', default_value=_SPAWN_YAW, description='Spawn yaw [rad]'))
    ld.add_action(DeclareLaunchArgument(
        'gui', default_value='false',
        description='Also start the Gazebo GUI client (headless if false)'))
    ld.add_action(DeclareLaunchArgument(
        'seed', default_value='',
        description='Noise seed passed to gz sim, fixing the sign and value '
                    'each sensor bias is drawn with. Empty (the default) '
                    'leaves the draw random, which is what a real device '
                    'does. It is a MEASUREMENT facility: nothing on the '
                    'vehicle reads it, and it exists so a before-and-after '
                    'measurement compares two runs of one vehicle rather '
                    'than two draws.'))
    ld.add_action(DeclareLaunchArgument(
        'sto_contactor', default_value='true',
        description='Start agv/forklift/scripts/sto_contactor.py. '
                    'model.sdf\'s joint controllers listen on the three '
                    'ACTUATOR TERMINALS and this node is their only '
                    'publisher, so false leaves the plant with no command '
                    'source at all and the vehicle does not move whatever '
                    'anything publishes. It is a STAND-IN for the hardwired '
                    'onboard inhibit and not a safety function: no Category, '
                    'no Performance Level, no SIL, no PFH (ADR 0011 D5).'))
    ld.add_action(DeclareLaunchArgument(
        'estimator', default_value='false',
        description='Start the vehicle\'s own pose estimate: sensor_tf.py, '
                    'wheel_odometry.py, imu_gate.py and the '
                    'robot_localization EKF. ALL FOUR OR NONE - a partial '
                    'start is a silently different estimator, and '
                    'vehicle.launch.py refuses the partial combinations '
                    'outright. FALSE here, unlike the warehouse bringup, '
                    'because M4 carries no navigation claim and ran through '
                    'a closed gate without a transform tree; set it true for '
                    'anything that needs one (SLAM, AMCL, Nav2).'))
    ld.add_action(DeclareLaunchArgument(
        'nodes', default_value='false',
        description='Start forklift_io.py and obstacle_zone.py. FALSE here: '
                    'they only mean something with the PLC path behind them, '
                    'so the harness that starts that path starts them '
                    '(sim/scenarios/run_forklift_rehearsal.py, stack.sh).'))
    ld.add_action(DeclareLaunchArgument(
        'use_sim_time', default_value='true',
        description='ACCEPTED FOR CALLER COMPATIBILITY AND NOT CONSUMED. '
                    'Every node agv/forklift/launch/vehicle.launch.py starts '
                    'carries use_sim_time explicitly and its bridge takes no '
                    'such parameter, so there is nothing here to set. It is '
                    'declared so that existing callers and recorded recipes '
                    'passing use_sim_time:=true do not fail, and setting it '
                    'false changes nothing - which is why it is documented '
                    'as inert rather than quietly honoured.'))

    estimator = LaunchConfiguration('estimator')

    # THE ONE INCLUDE. Scoped, so that a launch configuration set by a
    # caller (warehouse_bringup.launch.py includes this file) cannot leak
    # into the vehicle launch and set an argument nobody passed:
    # IncludeLaunchDescription does not scope, and DeclareLaunchArgument
    # skips its default when the configuration is already set
    # (docs/LESSONS.md 2026-08-05). Everything the vehicle launch is meant
    # to receive is listed explicitly below.
    #
    # `estimator` fans out to the four arguments vehicle.launch.py declares
    # separately. It is one argument here on purpose: the four are not
    # independently useful and three of the twelve combinations are refused
    # by that file, so this layer does not offer them.
    ld.add_action(GroupAction(
        scoped=True,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(_VEHICLE_LAUNCH),
            launch_arguments={
                'world': LaunchConfiguration('world'),
                'world_name': LaunchConfiguration('world_name'),
                'model': LaunchConfiguration('model'),
                'name': LaunchConfiguration('name'),
                'x': LaunchConfiguration('x'),
                'y': LaunchConfiguration('y'),
                'z': LaunchConfiguration('z'),
                'yaw': LaunchConfiguration('yaw'),
                'gui': LaunchConfiguration('gui'),
                'seed': LaunchConfiguration('seed'),
                'server': 'true',
                'sto_contactor': LaunchConfiguration('sto_contactor'),
                'nodes': LaunchConfiguration('nodes'),
                'tf': estimator,
                'wheel_odom': estimator,
                'imu_gate': estimator,
                'ekf': estimator,
                'ground_truth_tf': 'false',
            }.items(),
        )],
    ))

    return ld
