#!/usr/bin/env python3
"""pocket_pose_node.py — C1 classical pocket pose. Publish Proposal only.

    python3 m8/m8_nodes/pocket_pose_node.py

Subscribes the on-truck D455 depth stream, runs m8_core.pocket, publishes
JSON on /m8/proposal. Does not command the dock. Does not republish the
image (R3). ROS imports live in main() so pytest never needs rclpy.
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core.pocket import propose as propose_pocket          # noqa: E402
from m8_core.selfmask import from_mast_joint                 # noqa: E402
from m8_core.topics import (                                 # noqa: E402
    CAM_DEPTH,
    CAM_INFO,
    JOINT_STATE,
    MAST_JOINT,
    PROPOSAL,
)
from m8_core.wire import decode_depth_32fc1, dumps_proposal  # noqa: E402
from m8_nodes.io import frame_from_buffer                    # noqa: E402
from m8_nodes.tag_target import read_tag                     # noqa: E402


def proposal_json_from_depth(depths, width, height, sim_stamp,
                             frame_id="pallet_cam_optical",
                             fx=None, fy=None, cx=None, cy=None,
                             self_mask=None, tag=None):
    """Pure entry the tests call. Returns JSON or None."""
    from m8_core.pocket import DEFAULT_FX, DEFAULT_FY
    frame = frame_from_buffer(
        depths, width, height, sim_stamp, frame_id,
        fx=DEFAULT_FX if fx is None else fx,
        fy=DEFAULT_FY if fy is None else fy,
        cx=cx, cy=cy)
    # C1 takes the tag in four places and gets ONE of them here, for the
    # reason `m8_nodes.tag_target.as_kwargs` sets out: this rig's tag is
    # the DOCK MARKER on the bay back panel, not a pallet tag.
    #
    #   expected_range  YES - the marker range less the 0.82 m a staged
    #                   pallet stands in front of the panel. This is the
    #                   window, and narrowing it also puts the truck's
    #                   own forks outside it at staging and at 1.5 m.
    #   tag_u, tag_v    NO - they would seed the candidate choice onto
    #                   the marker board, which is 0.73 m above the
    #                   pallet and a different object.
    #   tag_z           NO - it is the depth of the MARKER, so a pose
    #                   delta measured against it would read 0.85 m off
    #                   on every frame. The delta stays against the
    #                   fitted face, as it was.
    tag_kw = {}
    if tag is not None and not tag.is_stale(sim_stamp):
        tag_kw = {"expected_range": tag.face_range_m}
    proposal = propose_pocket(frame, self_mask=self_mask, **tag_kw)
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
            "pocket_pose_node needs rclpy (vehicle graph), not the "
            "H0 python: {}\n".format(exc))
        sys.exit(2)

    class PocketPose(Node):
        def __init__(self):
            super().__init__("m8_pocket_pose")
            self._fx = None
            self._fy = None
            self._cx = None
            self._cy = None
            self._mask = None
            self._buf = Buffer()
            self._tf = TransformListener(self._buf, self)
            self._pub = self.create_publisher(String, PROPOSAL, 10)
            self.create_subscription(CameraInfo, CAM_INFO, self._cb_info, 10)
            self.create_subscription(Image, CAM_DEPTH, self._cb_depth, 10)
            self.create_subscription(JointState, JOINT_STATE,
                                     self._cb_joints, 10)
            self.get_logger().info(
                "shadow C1: {} → {} (Proposal JSON only)".format(
                    CAM_DEPTH, PROPOSAL))

        def _cb_info(self, msg):
            if len(msg.k) >= 6:
                self._fx = float(msg.k[0])
                self._fy = float(msg.k[4])
                self._cx = float(msg.k[2])
                self._cy = float(msg.k[5])

        def _cb_joints(self, msg):
            """Where the truck's own forks are - see m8_core.selfmask."""
            try:
                index = list(msg.name).index(MAST_JOINT)
            except ValueError:
                return
            if index >= len(msg.position):
                return
            t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
            self._mask = from_mast_joint(float(msg.position[index]), t)

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
    node = PocketPose()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
