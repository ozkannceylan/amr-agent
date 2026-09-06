#!/usr/bin/env python3
"""slot_state_node.py — C3 slot table. Publish Proposal only.

    python3 m8/m8_nodes/slot_state_node.py

Reporting only. The vehicle does not act. ROS imports live in main().
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core.slot import propose as propose_slot              # noqa: E402
from m8_core.topics import CAM_DEPTH, CAM_INFO, PROPOSAL      # noqa: E402
from m8_core.wire import decode_depth_32fc1, dumps_proposal   # noqa: E402
from m8_nodes.io import frame_from_buffer                     # noqa: E402


def proposal_json_from_depth(depths, width, height, sim_stamp,
                             frame_id="pallet_cam_optical",
                             fx=None, fy=None, cx=None, cy=None):
    from m8_core.pocket import DEFAULT_FX, DEFAULT_FY
    frame = frame_from_buffer(
        depths, width, height, sim_stamp, frame_id,
        fx=DEFAULT_FX if fx is None else fx,
        fy=DEFAULT_FY if fy is None else fy,
        cx=cx, cy=cy)
    return dumps_proposal(propose_slot(frame))


def main():
    try:
        import struct

        import rclpy
        from rclpy.node import Node
        from sensor_msgs.msg import CameraInfo, Image
        from std_msgs.msg import String
    except ImportError as exc:
        sys.stderr.write(
            "slot_state_node needs rclpy (vehicle graph): {}\n".format(exc))
        sys.exit(2)

    class SlotState(Node):
        def __init__(self):
            super().__init__("m8_slot_state")
            self._fx = self._fy = self._cx = self._cy = None
            self._pub = self.create_publisher(String, PROPOSAL, 10)
            self.create_subscription(CameraInfo, CAM_INFO, self._cb_info, 10)
            self.create_subscription(Image, CAM_DEPTH, self._cb_depth, 10)
            self.get_logger().info(
                "shadow C3: {} → {} (slot Proposal only)".format(
                    CAM_DEPTH, PROPOSAL))

        def _cb_info(self, msg):
            if len(msg.k) >= 6:
                self._fx = float(msg.k[0])
                self._fy = float(msg.k[4])
                self._cx = float(msg.k[2])
                self._cy = float(msg.k[5])

        def _cb_depth(self, msg):
            if msg.encoding not in ("32FC1", "32FC1;"):
                return
            try:
                depths = decode_depth_32fc1(
                    bytes(msg.data), msg.width, msg.height, msg.step)
            except (ValueError, struct.error):
                return
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            text = proposal_json_from_depth(
                depths, msg.width, msg.height, stamp,
                msg.header.frame_id or "pallet_cam_optical",
                self._fx, self._fy, self._cx, self._cy)
            out = String()
            out.data = text
            self._pub.publish(out)

    rclpy.init()
    node = SlotState()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
