#!/usr/bin/env python3
"""abort_node.py — C2 abort classifier. Publish Proposal only.

    python3 m8/m8_nodes/abort_node.py

A clean frame publishes nothing. `proceed` is not an output. ROS
imports live in main().
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core.abort import propose as propose_abort            # noqa: E402
from m8_core.selfmask import from_mast_joint                  # noqa: E402
from m8_core.topics import (                                  # noqa: E402
    CAM_DEPTH,
    CAM_INFO,
    JOINT_STATE,
    MAST_JOINT,
    PROPOSAL,
)
from m8_core.wire import decode_depth_32fc1, dumps_proposal   # noqa: E402
from m8_nodes.io import frame_from_buffer                     # noqa: E402
from m8_nodes.tag_target import kwargs_for, read_tag          # noqa: E402


def proposal_json_from_depth(depths, width, height, sim_stamp,
                             frame_id="pallet_cam_optical",
                             fx=None, fy=None, cx=None, cy=None,
                             self_mask=None, tag=None):
    from m8_core.pocket import DEFAULT_FX, DEFAULT_FY
    frame = frame_from_buffer(
        depths, width, height, sim_stamp, frame_id,
        fx=DEFAULT_FX if fx is None else fx,
        fy=DEFAULT_FY if fy is None else fy,
        cx=cx, cy=cy)
    # A tag can only NARROW. No tag, or a stale one, and this is `{}` -
    # the tagless envelope the C1/C2 numbers were measured with.
    proposal = propose_abort(frame, self_mask=self_mask,
                             **kwargs_for(tag, sim_stamp))
    if proposal is None:
        return None
    return dumps_proposal(proposal)


def main():
    try:
        import struct

        import rclpy
        from rclpy.node import Node
        from rclpy.time import Time
        from sensor_msgs.msg import CameraInfo, Image, JointState
        from std_msgs.msg import String
        from tf2_ros import Buffer, TransformListener
    except ImportError as exc:
        sys.stderr.write(
            "abort_node needs rclpy (vehicle graph): {}\n".format(exc))
        sys.exit(2)

    class AbortNode(Node):
        def __init__(self):
            super().__init__("m8_abort")
            self._fx = self._fy = self._cx = self._cy = None
            self._mask = None
            self._buf = Buffer()
            self._tf = TransformListener(self._buf, self)
            self._pub = self.create_publisher(String, PROPOSAL, 10)
            self.create_subscription(CameraInfo, CAM_INFO, self._cb_info, 10)
            self.create_subscription(Image, CAM_DEPTH, self._cb_depth, 10)
            self.create_subscription(JointState, JOINT_STATE,
                                     self._cb_joints, 10)
            self.get_logger().info(
                "shadow C2: {} + {} → {} (abort Proposal or silence)".format(
                    CAM_DEPTH, JOINT_STATE, PROPOSAL))

        def _cb_info(self, msg):
            if len(msg.k) >= 6:
                self._fx = float(msg.k[0])
                self._fy = float(msg.k[4])
                self._cx = float(msg.k[2])
                self._cy = float(msg.k[5])

        def _cb_joints(self, msg):
            """Where the truck's own forks are, from its own joint state.

            The mask is rebuilt on every message and carries THAT
            message's stamp, so its age is the reading's age and not the
            node's. A message without `mast_joint` in it leaves the last
            mask alone: it will go stale on its own, which is the
            behaviour wanted, and a silent zero would put the mask at the
            bottom stop while the forks were up.
            """
            try:
                index = list(msg.name).index(MAST_JOINT)
            except ValueError:
                return
            if index >= len(msg.position):
                return
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            self._mask = from_mast_joint(float(msg.position[index]), stamp)

        def _cb_depth(self, msg):
            if msg.encoding not in ("32FC1", "32FC1;"):
                return
            try:
                depths = decode_depth_32fc1(
                    bytes(msg.data), msg.width, msg.height, msg.step)
            except (ValueError, struct.error):
                return
            stamp = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            tag = read_tag(self._buf, Time.from_msg(msg.header.stamp),
                           self._fx, self._fy, self._cx, self._cy,
                           stamp=stamp)
            text = proposal_json_from_depth(
                depths, msg.width, msg.height, stamp,
                msg.header.frame_id or "pallet_cam_optical",
                self._fx, self._fy, self._cx, self._cy,
                self_mask=self._mask, tag=tag)
            if text is None:
                return
            out = String()
            out.data = text
            self._pub.publish(out)

    rclpy.init()
    node = AbortNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
