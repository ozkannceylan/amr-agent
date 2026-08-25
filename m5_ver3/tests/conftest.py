"""Put this track's node and tool directories on sys.path.

m5-ver3 is deliberately not a colcon package - CONTEXT.md: plain files run
with python3 - so there is nothing to install and the tests reach the
modules by path, exactly as m6/tests/conftest.py does for m6's.

NO ROS IS IMPORTED FROM ANYWHERE THIS FILE REACHES, and that is the whole
point of the split the modules are written to. nodes/wheel_odom_core.py is
pure arithmetic; nodes/wheel_odometry.py is the rclpy shell around it and
keeps every ROS import inside its own main(). So this suite collects and
passes on a Windows python with no rclpy in it, which is the python the
owner runs pytest under.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in ("nodes", "tools"):
    _path = os.path.normpath(os.path.join(_HERE, "..", _sub))
    if _path not in sys.path:
        sys.path.insert(0, _path)
