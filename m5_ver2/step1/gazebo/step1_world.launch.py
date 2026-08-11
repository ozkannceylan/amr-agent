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

with open(_CONFIG, "r", encoding="utf-8") as _handle:
    _TOPICS = yaml.safe_load(_handle)["topics"]

# '[' gz to ROS, ']' ROS to gz.
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
