"""step1_world.launch.py - the plant, and only the plant.

Five processes: the world server, one spawn, one bridge, the unit
translator and the STO contactor.

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
  ros2 launch m5_ver2/step1/gazebo/step1_world.launch.py
"""

import os
import sys

import yaml
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch_ros.actions import Node

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", "..", ".."))

_WORLD = os.path.join(_REPO, "sim", "worlds", "warehouse.sdf")
_MODEL = os.path.join(_REPO, "agv", "forklift", "model.sdf")
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
# bridge and both scripts keep running, and every ROS topic the Step 3
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
            "step1_world.launch.py: no such file: {}".format(_path))

with open(_CONFIG, "r", encoding="utf-8") as _handle:
    _TOPICS = yaml.safe_load(_handle)["topics"]

# '[' gz to ROS, ']' ROS to gz.
#
# JOINT STATES AND ODOMETRY ARE DELIBERATELY NOT BRIDGED. Nothing in
# m5_ver2/step1/ consumes linear_speed, fork_height or joint_states, and a
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


def generate_launch_description():
    ld = LaunchDescription()

    # --headless-rendering is the honest flag here: -s alone still opens a
    # GLX connection when DISPLAY is set (sim/setup/WSL_ENVIRONMENT.md 4.7).
    ld.add_action(ExecuteProcess(
        cmd=["gz", "sim", "-s", "-r", "--headless-rendering",
             "-v", "2", _WORLD],
        name="gz_server",
        output="screen",
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
        name="step1_bridge",
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
