"""m6_world.launch.py - the plant, and only the plant.

Eight processes: the world server, one bridge, and for EACH of the two
vehicles a spawn, the unit translator and the STO contactor. A ninth,
the Gazebo GUI client, is started only by `gui:=true` and nothing in the
command path reads it.

ONE WORLD, TWO VEHICLES, AND THE ONE PLACE THE DIFFERENCE LIVES
  Every per-vehicle name and pose below comes from the VEHICLES table in
  ipc/status_contract.py, through contract(vid). This file imports that
  module ENV-FREE and has to keep doing so: VEHICLE names ONE vehicle
  and this process serves both, so reading a per-vehicle module constant
  here would bind the whole launch to whichever vehicle the shell
  happened to name.

  What it spawns are the DERIVED models under m6/vehicles/<vid>/,
  written by tools/instantiate_vehicle.py. The shared sources spell every
  gz topic absolutely under /forklift/, so two spawns of one file would
  share every terminal - one steer command driving both trucks. The
  derived files are git-ignored build products, so a missing one is a
  refusal at import that NAMES the tool, and never a fallback to the
  source: that fallback would start, look like a launch, and be wrong in
  exactly the way this file exists to prevent.

WHY NOT agv/forklift/launch/vehicle.launch.py
  That file also starts safe_speed_link.py, field_evaluation.py,
  obstacle_zone.py and the EKF - the old M5 OPC UA safety path. Running it
  would put a second process on the PLC and break the single-writer rule.
  Its arguments could switch most of that off, but Step 1's isolation would
  then rest on a dozen toggles being right.

WHY THE BRIDGE CARRIES THE ACTUATOR TERMINALS AND NOT THE COMMAND TOPICS
  Each derived model.sdf's joint controllers listen on
  /<vid>/gz/actuator/*_cmd, and that vehicle's sto_contactor.py is the
  only publisher of those. Bridging the terminals puts the contactor
  INSIDE the path rather than beside it: with its latch open, nothing any
  ROS publisher does reaches the plant.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  ros2 launch m6/gazebo/m6_world.launch.py
  ros2 launch m6/gazebo/m6_world.launch.py gui:=true
"""

import os
import sys

import yaml
from launch import LaunchDescription
from launch.actions import (DeclareLaunchArgument, ExecuteProcess,
                            OpaqueFunction)
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))

# STEP 5'S OWN WORLD, NOT sim/worlds/warehouse.sdf. Owner instruction
# 2026-08-12: the source world's aisles trip the protective field while
# driving. warehouse_ver2.sdf is this directory's open relayout (no
# building columns, no row C, 6.50 m main aisle); the source world stays
# untouched, exactly as forklift_ver2/model.sdf leaves agv/'s model alone.
# The world NAME inside the file stays "warehouse", so _WORLD_NAME and
# every /world/warehouse/* topic hold. ONE world for both vehicles: the
# plant is the only thing they share.
_WORLD = os.path.join(_HERE, "warehouse_ver2.sdf")
_SCRIPTS = os.path.join(_REPO, "agv", "forklift", "scripts")
_IO_SCRIPT = os.path.join(_SCRIPTS, "forklift_io.py")
_STO_SCRIPT = os.path.join(_SCRIPTS, "sto_contactor.py")

# sim/worlds/warehouse.sdf line 206. The spawn POSES are no longer here:
# they are two of the per-vehicle differences the VEHICLES table owns (f1
# keeps the pose sim/launch/warehouse_bringup.launch.py declares at
# 229-232, which is what step5 spawned at).
_WORLD_NAME = "warehouse"

# From ipc/status_contract.py, which is the one home for the topic names
# config.yaml has never heard of AND for the vehicle table. Spelling
# either again here is how a rename breaks the bridge and the subscriber
# differently.
sys.path.insert(0, os.path.join(_HERE, "..", "ipc"))
import status_contract                                    # noqa: E402

_VIDS = tuple(sorted(status_contract.VEHICLES))

# THIS TREE'S OWN MODEL (built in Step 2), NOT agv/forklift/model.sdf: it
# carries the three microScan3 scanners, and agv/'s carries the old
# front/rear pair at 5.5 m and is never modified. What gets spawned is one
# DERIVATION of it per vehicle, under m6/vehicles/<vid>/, beside the
# config.yaml derived from agv/forklift/config.yaml.
_VEHICLES_DIR = os.path.normpath(os.path.join(_HERE, "..", "vehicles"))
_VEHICLE_MODELS = {vid: os.path.join(_VEHICLES_DIR, vid, "model.sdf")
                   for vid in _VIDS}
_VEHICLE_CONFIGS = {vid: os.path.join(_VEHICLES_DIR, vid, "config.yaml")
                    for vid in _VIDS}

# THE PATHS, CHECKED AT IMPORT, FOR THE SAME REASON THE CONFIG IS.
# A wrong path here does not stop the launch: gz or `create` dies, the
# bridge and both scripts keep running, and every ROS topic the Step 5
# check looks for still EXISTS - the contactor publishes the terminals
# whether or not anything subscribes to them. The graph would then look
# correct while the truck did not move, which is precisely the two-causes
# ambiguity this file exists to remove, arriving through a different door.
# So a missing file is a refusal at import, naming the path, the way a
# missing config key already is.
for _path in (_WORLD, _IO_SCRIPT, _STO_SCRIPT):
    if not os.path.isfile(_path):
        raise FileNotFoundError(
            "m6_world.launch.py: no such file: {}".format(_path))
# The derived pair gets a refusal of its own, because "no such file" is
# the wrong answer about a build product: it is not missing, it has not
# been MADE, and what the operator needs is the command that makes it.
for _vid in _VIDS:
    for _path in (_VEHICLE_MODELS[_vid], _VEHICLE_CONFIGS[_vid]):
        if not os.path.isfile(_path):
            raise FileNotFoundError(
                "m6_world.launch.py: no derived file for {}: {} "
                "(run tools/instantiate_vehicle.py --all)"
                .format(_vid, _path))

# '[' gz to ROS, ']' ROS to gz.
#
# ONE BRIDGE PROCESS CARRIES BOTH VEHICLES. Every argument in the loop
# below is a fully namespaced topic - /f1/... or /f2/... - so a second
# bridge would buy nothing but a second thing to start, stop and sweep.
#
# JOINT STATES ARE DELIBERATELY NOT BRIDGED (odometry joined the bridge in
# Step 5, below). Nothing in m6/ consumes linear_speed,
# fork_height or joint_states, and a bridged channel with no consumer is a
# claim the run does not make. The cost is that forklift_io logs "waiting
# for source data: joint_states=False, odom=False" every 5 s for the life
# of every run - and it still says odom=False after Step 5's bridge,
# because forklift_io subscribes to topics.odom (/<vid>/odom), which is
# the RENAMED ROS name and not the gz one this file opens. That warning is
# EXPECTED and harmless: it gates only the two derived state scalars and
# the fork target seed, never the traction or steer command path.
#
# WHERE EACH NAME COMES FROM. The gz names config.yaml owns are read from
# the DERIVED config.yaml, so the /<vid>/ prefix in the bridge and the
# prefix inside that vehicle's model.sdf can only ever be the same
# rewrite. The three safety scanners belong to forklift_ver2/model.sdf,
# which config.yaml has never heard of, so they come from contract(vid) -
# the one home for the names config.yaml does not own.
_BRIDGE_ARGS = []
_CLOCK_TOPIC = None
for _vid in _VIDS:
    with open(_VEHICLE_CONFIGS[_vid], "r", encoding="utf-8") as _handle:
        _T = yaml.safe_load(_handle)["topics"]
    # /clock IS THE WORLD'S, NOT A VEHICLE'S, so it is bridged ONCE, after
    # the loop. It carries no /forklift/ prefix, so the rewrite leaves it
    # alone in every derived config and all of them must agree: two clocks
    # on one world would be two opinions about now.
    if _CLOCK_TOPIC is None:
        _CLOCK_TOPIC = _T["clock"]
    elif _T["clock"] != _CLOCK_TOPIC:
        raise ValueError(
            "m6_world.launch.py: one world, one clock, but {} says {} "
            "and another says {}".format(_vid, _T["clock"], _CLOCK_TOPIC))
    _c = status_contract.contract(_vid)
    # The three safety scanners, gz -> ROS. sensor_msgs/msg/LaserScan is
    # the ROS side of gz.msgs.LaserScan; the topic keeps its gz name so a
    # gz topic list and a ros2 topic list read as one namespace.
    _scans = tuple(_c["scan_topic"].format(n)
                   for n in ("back", "left", "right"))
    _BRIDGE_ARGS += [
        "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
            _T["gz_actuator_steer_cmd"]),
        "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
            _T["gz_actuator_traction_cmd"]),
        # STEP 5 OPENED TWO CHANNELS STEP 4 LEFT CLOSED. Both producers
        # have sat in forklift_ver2/model.sdf since Step 2; nothing
        # consumed them, so bridging them would have been a claim the run
        # did not make. Step 5 consumes both: nav_node navigates on the
        # ground-truth odom (spec: owner ruling, the lidar guards rather
        # than localises) and guards on the nav lidar.
        #
        # KNOWN LIMITATION, M6.1: THE TF FRAME IDS INSIDE THESE ODOMETRY
        # MESSAGES ARE NOT NAMESPACED. The OdometryPublisher writes
        # frame_id "forklift/odom" and child_frame_id "forklift/base_link"
        # with NO leading slash, so instantiate_vehicle.py's /forklift/ ->
        # /<vid>/ rewrite cannot see them and both vehicles publish the
        # same two frame names on their own topics. It is inert today and
        # that was checked rather than assumed: nothing in m6/ipc/
        # reads header.frame_id or child_frame_id (nav_node takes only the
        # pose), nothing publishes TF and there is no robot_state_
        # publisher. M6.2+ must namespace the frames in the derived model
        # BEFORE the first consumer appears - a TF tree, an EKF or a Nav2
        # stack would silently join the two trucks into one.
        "{}@nav_msgs/msg/Odometry[gz.msgs.Odometry".format(_T["gz_odom"]),
        "{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan".format(
            _T["gz_scan_nav"]),
        # The drive shaft's two reading channels, gz -> ROS. Both are
        # JointStatePublisher systems on drive_wheel_joint: one shaft, two
        # readings, a single-channel TESTED system and never a
        # two-channel one.
        "{}@sensor_msgs/msg/JointState[gz.msgs.Model".format(
            _T["gz_drive_speed_read_a"]),
        "{}@sensor_msgs/msg/JointState[gz.msgs.Model".format(
            _T["gz_drive_speed_read_b"]),
    ] + ["{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan".format(t)
         for t in _scans]
_BRIDGE_ARGS.insert(
    0, "{}@rosgraph_msgs/msg/Clock[gz.msgs.Clock".format(_CLOCK_TOPIC))

# The GUI gate waits for the back scanner of EVERY vehicle - the reason is
# the long note in generate_launch_description(). Both spawns are
# requested by the same launch, so waiting for the second costs nothing
# and closes the same race for its beams that waiting for the first
# closes for f1's.
_GUI_GATE_TOPICS = tuple(
    status_contract.contract(vid)["scan_topic"].format("back")
    for vid in _VIDS)


def _gz_server(context, *args, **kwargs):
    """The world server. -s is server-only; the GUI is a second process.

    Built in a function rather than declared, because --headless-rendering
    has to be ABSENT from the command line when the GUI is wanted rather
    than present with a false value - the same reason
    agv/forklift/launch/vehicle.launch.py:246-279 builds its server line in
    one. With the GUI off it stays: -s alone still opens a GLX connection
    when DISPLAY is set (sim/setup/WSL_ENVIRONMENT.md 4.7), so it is the
    honest flag for a run that claims to be headless. With the GUI on, the
    remaining argument list is exactly what vehicle.launch.py's `-r -s `
    produces, which is this repo's proven GUI configuration.
    """
    cmd = ["gz", "sim", "-s", "-r"]
    if LaunchConfiguration("gui").perform(context).lower() != "true":
        cmd.append("--headless-rendering")
    cmd += ["-v", "2", _WORLD]
    return [ExecuteProcess(cmd=cmd, name="gz_server", output="screen")]


def generate_launch_description():
    ld = LaunchDescription()

    ld.add_action(DeclareLaunchArgument(
        "gui", default_value="false",
        description="Also start the Gazebo GUI client (headless if false)"))

    ld.add_action(OpaqueFunction(function=_gz_server))

    # THE GUI CLIENT, AND WHY IT IS A DIRECT `gz sim -g` AND NOT
    # ros_gz_sim's gz_sim.launch.py, WHICH IS WHAT agv/ AND sim/ USE.
    #   Those two files start the SERVER through that wrapper as well, so
    #   using it for the client keeps one mechanism. This file does not: it
    #   runs gz directly, and routing only the client through the wrapper
    #   would give the two halves of one simulator two different launch
    #   paths. The wrapper's own service is exporting
    #   GZ_SIM_{SYSTEM_PLUGIN,RESOURCE}_PATH scraped from every installed
    #   ROS package's manifest; Step 1 hands gz absolute paths to a world
    #   and a model that export nothing, so that scrape buys nothing here.
    #   And agv/ passes it on_exit_shutdown:=true, which would make closing
    #   this window tear down the server, the bridge and the contactor
    #   underneath a running e-stop test. One process, one command line,
    #   and `gz sim` in m6.sh's PATTERNS nominates it.
    #
    # THE GUI WAITS FOR THE SCANNERS, OR THE BEAMS ANCHOR AT THE ORIGIN.
    #   Measured 2026-08-12 on gz-sim 8.11.0. GuiRunner discards every
    #   /world/*/state message that arrives before its initial state_async
    #   response is processed (GuiRunner.cc:283), and the SensorTopic
    #   components VisualizeLidar anchors on (VisualizeLidar.cc:271) are
    #   created by the render thread a beat AFTER the spawn. A GUI started
    #   with the server therefore snapshots the world without SensorTopic,
    #   the one-time change that would deliver it lands in the discard
    #   window, nothing ever rebroadcasts it, and the plugin's entity
    #   lookup fails for the life of the GUI ("could not be found",
    #   printed once) - the fan then draws at the visual's default pose,
    #   the world origin, and no refresh recovers it. Gating the client on
    #   the back scanner's topic being advertised puts the sensors - and
    #   their SensorTopic components, created before the advert - inside
    #   the GUI's initial snapshot, which a late GUI receives in full.
    #   m5-73's world_pose repair aimed at a field this plugin never
    #   reads; the anchor is the ECM lookup above, and ordering is what
    #   fixes it.
    #   WITH TWO VEHICLES THE GATE WAITS FOR BOTH, and it has to: the race
    #   is per model, so a GUI let in after f1's scanners advertised but
    #   before f2's would draw f2's three fans at the world origin.
    ld.add_action(ExecuteProcess(
        cmd=["bash", "-c",
             "until {}; do sleep 0.5; done; sleep 2; "
             "exec gz sim -g -v 2".format(
                 " && ".join("gz topic -l 2>/dev/null | grep -qF '{}'"
                             .format(t) for t in _GUI_GATE_TOPICS))],
        name="gz_gui",
        output="screen",
        condition=IfCondition(LaunchConfiguration("gui")),
    ))

    ld.add_action(Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="m6_bridge",
        output="screen",
        arguments=_BRIDGE_ARGS,
    ))

    # ONE LOOP FOR THE WHOLE VEHICLE SIDE: three processes per vehicle,
    # all three pointed at that vehicle's DERIVED config. The two reused
    # vehicle nodes are started exactly as
    # agv/forklift/launch/vehicle.launch.py starts them - the contactor
    # carries use_sim_time, forklift_io does not - with one addition, a
    # __node remap, so two instances of one script do not both call
    # themselves sto_contactor and make `ros2 node list` a riddle. Both
    # scripts parse_known_args and hand the rest to rclpy, so the remap
    # travels the road --ros-args already travels.
    for vid in _VIDS:
        c = status_contract.contract(vid)
        vcfg = _VEHICLE_CONFIGS[vid]
        ld.add_action(Node(
            package="ros_gz_sim",
            executable="create",
            name="spawn_forklift_{}".format(vid),
            output="screen",
            arguments=[
                "-world", _WORLD_NAME,
                "-file", _VEHICLE_MODELS[vid],
                # THE MODEL NAME IS THE VEHICLE ID, and a deliberate
                # literal rather than the name config.yaml owns
                # (config.yaml:26, model.name: Forklift). Nothing breaks:
                # the gz topic names are name-independent by design,
                # because every gz system in model.sdf states its topic
                # explicitly - config.yaml:24-25 says exactly that. What
                # DOES read this name is anything addressing ONE truck
                # through a gz service, and with two of them that is no
                # longer optional: m6.sh's home and tools/rtf_spike.sh
                # both spell forklift_<vid>, so the three must agree.
                "-name", "forklift_{}".format(vid),
                "-x", c["spawn"]["x"],
                "-y", c["spawn"]["y"],
                "-z", c["spawn"]["z"],
                "-Y", c["spawn"]["yaw"],
                "-allow_renaming", "false",
            ],
        ))
        ld.add_action(ExecuteProcess(
            cmd=[sys.executable, _STO_SCRIPT, "--config", vcfg,
                 "--ros-args", "-p", "use_sim_time:=true",
                 "-r", "__node:=sto_contactor_{}".format(vid)],
            name="sto_contactor_{}".format(vid),
            output="screen",
        ))
        ld.add_action(ExecuteProcess(
            cmd=[sys.executable, _IO_SCRIPT, "--config", vcfg,
                 "--ros-args",
                 "-r", "__node:=forklift_io_{}".format(vid)],
            name="forklift_io_{}".format(vid),
            output="screen",
        ))

    return ld
