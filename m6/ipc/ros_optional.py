"""rclpy and message types, or stand-ins when the overlay is absent.

Native CI (ADR 0017 Phase 2) collects tests of this tree's pure
functions without /opt/ros. Each node's `main()` still requires a
sourced Jazzy overlay and calls `require()` before `rclpy.init()`.

When the overlay IS sourced this module is a pass-through: the names
are the real rclpy objects, and the live `python3 m6/ipc/*.py` entry
points behave as they did before. When it is not, `Node` is `object`
so `object.__new__(CmdGate)` in the tests still builds a skeleton,
message types are small stand-ins with the same attribute shapes the
skeleton tests publish, and `available` is False.
"""
available = False
rclpy = None
Node = object
DurabilityPolicy = None
QoSProfile = None


class _Axis:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.z = 0.0


class _Twist:
    def __init__(self, **_kwargs):
        self.linear = _Axis()
        self.angular = _Axis()


class _DataMsg:
    """std_msgs/String, Bool, Float64 - the tests and nodes use .data."""

    def __init__(self, data=None, **kwargs):
        self.data = kwargs.get("data", data)


class _Empty:
    def __init__(self, **_kwargs):
        pass


Twist = _Twist
Odometry = _Empty
JointState = _Empty
LaserScan = _Empty
Bool = _DataMsg
Float64 = _DataMsg
String = _DataMsg
Image = _Empty

try:
    import rclpy as _rclpy
    from geometry_msgs.msg import Twist as _TwistMsg
    from nav_msgs.msg import Odometry as _Odometry
    from rclpy.node import Node as _Node
    from rclpy.qos import DurabilityPolicy as _DurabilityPolicy
    from rclpy.qos import QoSProfile as _QoSProfile
    from sensor_msgs.msg import Image as _Image
    from sensor_msgs.msg import JointState as _JointState
    from sensor_msgs.msg import LaserScan as _LaserScan
    from std_msgs.msg import Bool as _Bool
    from std_msgs.msg import Float64 as _Float64
    from std_msgs.msg import String as _String
except ImportError:
    pass
else:
    available = True
    rclpy = _rclpy
    Node = _Node
    DurabilityPolicy = _DurabilityPolicy
    QoSProfile = _QoSProfile
    Twist = _TwistMsg
    Odometry = _Odometry
    JointState = _JointState
    LaserScan = _LaserScan
    Bool = _Bool
    Float64 = _Float64
    String = _String
    Image = _Image


def require():
    """Refuse to start a node without the Jazzy overlay."""
    if not available:
        raise SystemExit("source /opt/ros/jazzy/setup.bash first")
