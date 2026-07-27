#!/usr/bin/env python3
"""Launcher: run the bridge without touching PYTHONPATH.

    source /opt/ros/jazzy/setup.bash
    /opt/amr-bridge-venv/bin/python bridge/run_bridge.py --config bridge/config/bridge.yaml

The interpreter must be one that can import BOTH rclpy (from the ROS 2
installation, via the sourced setup.bash) and asyncua (pinned in
requirements.txt). See README.md, "How to run it".
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from amr_bridge.main import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
