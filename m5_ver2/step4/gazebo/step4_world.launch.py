"""step4_world.launch.py - the plant, and only the plant.

Five processes: the world server, one spawn, one bridge, the unit
translator and the STO contactor. A sixth, the Gazebo GUI client, is
started only by `gui:=true` and nothing in the command path reads it.

WHY NOT agv/forklift/launch/vehicle.launch.py
  That file also starts safe_speed_link.py, field_evaluation.py,
  obstacle_zone.py and the EKF - the old M5 OPC UA safety path. Running it
  would put a second process on the PLC and break the single-writer rule.
  Its arguments could switch most of that off, but Step 1's isolation would
  then rest on a dozen toggles being right.

WHY THE BRIDGE CARRIES THE ACTUATOR TERMINALS AND NOT THE COMMAND TOPICS
  model.sdf's joint controllers listen on /forklift/gz/actuator/*_cmd, and
  sto_contactor.py is the only publisher of those. Bridging the terminals
  puts the contactor INSIDE the path rather than beside it: with its latch
  open, nothing any ROS publisher does reaches the plant.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  ros2 launch m5_ver2/step4/gazebo/step4_world.launch.py
  ros2 launch m5_ver2/step4/gazebo/step4_world.launch.py gui:=true
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
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))

_WORLD = os.path.join(_REPO, "sim", "worlds", "warehouse.sdf")
# STEP 2'S OWN MODEL, NOT agv/forklift/model.sdf. It carries the three
# microScan3 scanners; agv/'s carries the old front/rear pair at 5.5 m and
# is never modified. The path is local to this directory, so the guard
# below is what turns a typo into a refusal instead of a forklift that
# spawns with the wrong sensors and looks right until Task 4 reads it.
_MODEL = os.path.join(_HERE, "forklift_ver2", "model.sdf")
_CONFIG = os.path.join(_REPO, "agv", "forklift", "config.yaml")
_SCRIPTS = os.path.join(_REPO, "agv", "forklift", "scripts")
_IO_SCRIPT = os.path.join(_SCRIPTS, "forklift_io.py")
_STO_SCRIPT = os.path.join(_SCRIPTS, "sto_contactor.py")

# sim/worlds/warehouse.sdf line 206, and the spawn pose that
# sim/launch/warehouse_bringup.launch.py declares (lines 229-232).
_WORLD_NAME = "warehouse"
_SPAWN = {"x": "-3.00", "y": "-5.50", "z": "0.05", "yaw": "0.0"}

# THE FOUR PATHS, CHECKED AT IMPORT, FOR THE SAME REASON THE CONFIG IS.
# A wrong path here does not stop the launch: gz or `create` dies, the
# bridge and both scripts keep running, and every ROS topic the Step 4
# check looks for still EXISTS - the contactor publishes the terminals
# whether or not anything subscribes to them. The graph would then look
# correct while the truck did not move, which is precisely the two-causes
# ambiguity this file exists to remove, arriving through a different door.
# So a missing file is a refusal at import, naming the path, the way a
# missing config key already is. _CONFIG needs no entry: open() below
# raises FileNotFoundError naming it.
for _path in (_WORLD, _MODEL, _IO_SCRIPT, _STO_SCRIPT):
    if not os.path.isfile(_path):
        raise FileNotFoundError(
            "step4_world.launch.py: no such file: {}".format(_path))

with open(_CONFIG, "r", encoding="utf-8") as _handle:
    _TOPICS = yaml.safe_load(_handle)["topics"]

# '[' gz to ROS, ']' ROS to gz.
#
# JOINT STATES AND ODOMETRY ARE DELIBERATELY NOT BRIDGED. Nothing in
# m5_ver2/step4/ consumes linear_speed, fork_height or joint_states, and a
# bridged channel with no consumer is a claim the run does not make. The
# cost is that forklift_io logs "waiting for source data:
# joint_states=False, odom=False" every 5 s for the life of every Step 1
# run. That warning is EXPECTED and harmless: it gates only the two derived
# state scalars and the fork target seed, never the traction or steer
# command path.
_BRIDGE_ARGS = [
    "{}@rosgraph_msgs/msg/Clock[gz.msgs.Clock".format(_TOPICS["clock"]),
    "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
        _TOPICS["gz_actuator_steer_cmd"]),
    "{}@std_msgs/msg/Float64]gz.msgs.Double".format(
        _TOPICS["gz_actuator_traction_cmd"]),
]

# The three safety scanners, gz -> ROS. sensor_msgs/msg/LaserScan is the
# ROS side of gz.msgs.LaserScan; the topic keeps its gz name so a gz topic
# list and a ros2 topic list read as one namespace.
#
# THE ONE PLACE THESE THREE NAMES LIVE. Every other topic in this file comes
# from config.yaml, because agv/forklift/model.sdf owns those. These three
# belong to forklift_ver2/model.sdf, which config.yaml has never heard of,
# so putting them there would be inventing a key in a file this step is
# forbidden to modify.
# From ros2/status_contract.py, which is the one home for the four
# topic names config.yaml has never heard of. Spelling them again here
# is how a rename breaks the bridge and the subscriber differently.
sys.path.insert(0, os.path.join(_HERE, "..", "ros2"))
import status_contract                                    # noqa: E402

_SCAN_TOPICS = tuple(
    status_contract.SCAN_TOPIC.format(n)
    for n in ("back", "left", "right"))
_BRIDGE_ARGS += [
    "{}@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan".format(t)
    for t in _SCAN_TOPICS
]

# The drive shaft's two reading channels, gz -> ROS. Both are
# JointStatePublisher systems on drive_wheel_joint: one shaft, two
# readings, a single-channel TESTED system and never a two-channel one.
# These names ARE in config.yaml, so they come from there.
_BRIDGE_ARGS += [
    "{}@sensor_msgs/msg/JointState[gz.msgs.Model".format(
        _TOPICS["gz_drive_speed_read_a"]),
    "{}@sensor_msgs/msg/JointState[gz.msgs.Model".format(
        _TOPICS["gz_drive_speed_read_b"]),
]


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
    #   and `gz sim` in step4.sh's PATTERNS nominates it.
    ld.add_action(ExecuteProcess(
        cmd=["gz", "sim", "-g", "-v", "2"],
        name="gz_gui",
        output="screen",
        condition=IfCondition(LaunchConfiguration("gui")),
    ))

    ld.add_action(Node(
        package="ros_gz_sim",
        executable="create",
        name="spawn_forklift",
        output="screen",
        arguments=[
            "-world", _WORLD_NAME,
            "-file", _MODEL,
            # A DELIBERATE LITERAL, AND NOT THE NAME config.yaml OWNS
            # (config.yaml:26, model.name: Forklift). Nothing breaks: the gz
            # topic names are name-independent by design, because every gz
            # system in model.sdf states its topic explicitly - config.yaml
            # :24-25 says exactly that. Tree tooling keyed on the model name
            # WOULD mismatch, but none of it runs in Step 1 and the plan's
            # verification greps depend on this value, so it stays.
            "-name", "forklift",
            "-x", _SPAWN["x"],
            "-y", _SPAWN["y"],
            "-z", _SPAWN["z"],
            "-Y", _SPAWN["yaw"],
            "-allow_renaming", "false",
        ],
    ))

    ld.add_action(Node(
        package="ros_gz_bridge",
        executable="parameter_bridge",
        name="step4_bridge",
        output="screen",
        arguments=_BRIDGE_ARGS,
    ))

    # The two reused vehicle nodes, started exactly as
    # agv/forklift/launch/vehicle.launch.py starts them - the contactor
    # carries use_sim_time, forklift_io does not.
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _STO_SCRIPT, "--config", _CONFIG,
             "--ros-args", "-p", "use_sim_time:=true"],
        name="sto_contactor",
        output="screen",
    ))
    ld.add_action(ExecuteProcess(
        cmd=[sys.executable, _IO_SCRIPT, "--config", _CONFIG],
        name="forklift_io",
        output="screen",
    ))

    return ld
