"""m8_shadow.launch.py — Phase A1 shadow. Proposals only; gate refuses all.

Does not start Gazebo. Does not start a dock consumer. Does not start
the speed arbiter (Phase E) or m8_gated (Phase B+).

The five A1 shells are plain python3 files, same pattern as
m5_ver3/nodes/*. ROS 2 launch is optional glue; pytest reads this
file as text and does not import it.
"""
import os

from launch import LaunchDescription
from launch.actions import ExecuteProcess, LogInfo

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
_NODES = os.path.join(_M8, "m8_nodes")

# Keep this list equal to m8_core.topics.A1_NODE_FILES.
A1_NODE_FILES = (
    "pocket_pose_node.py",
    "abort_node.py",
    "slot_state_node.py",
    "veto_gate_node.py",
    "m8_health.py",
)


def generate_launch_description():
    actions = [LogInfo(msg=(
        "M8 shadow: C1/C2/C3 publish Proposals; Phase A gate refuses "
        "all; F-PLC is orthogonal; frames stay on the truck"))]
    for name in A1_NODE_FILES:
        actions.append(ExecuteProcess(
            cmd=["python3", os.path.join(_NODES, name)],
            output="screen",
            name=os.path.splitext(name)[0]))
    return LaunchDescription(actions)
