"""Put m8/ on sys.path so the suite imports m8_core as a plain package.

m8 is not a colcon package in A0. H0 is `pytest m8/tests` on a machine
that has never sourced ROS. This file reaches no rclpy import.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

_REPO = os.path.normpath(os.path.join(_M8, os.pardir))
