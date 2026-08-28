#!/usr/bin/env python3
"""detected_dock.py - AprilTag TF → PoseStamped for SimpleNonChargingDock.

    python3 m5_ver3/nodes/detected_dock.py

Jazzy apriltag_msgs 2.0.2 has no pose field. apriltag_ros broadcasts
TF `map` → `apriltag.tag_frame`. SimpleNonChargingDock subscribes
`detected_dock_pose` (geometry_msgs/PoseStamped) and applies
external_detection_translation_* itself.

THIS NODE DOES NOT INVENT A POSE. No TF, no message. A furniture pose
published here would be a fake detection; Task 2 is forbidden from
that. The plugin's INITIAL_PERCEPTION timeout is what names a miss.

WHY THE ROS IMPORTS ARE INSIDE main(). Pytest on Windows has no rclpy.
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in (_HERE, os.path.normpath(os.path.join(_HERE, os.pardir, "tools"))):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import _common                                        # noqa: E402

TOOL = "detected_dock"
REQUIRED_KEYS = (
    "topics.detected_dock_pose",
    "frames.map",
    "apriltag.tag_frame",
    "docking.detected_node_name",
    "docking.detected_rate_hz",
)


def main():
    try:
        import rclpy
        from geometry_msgs.msg import PoseStamped
        from rclpy.node import Node
        from tf2_ros import Buffer, TransformListener
    except ImportError as exc:
        cfg = _common.load_config(TOOL, REQUIRED_KEYS)
        cfg.refuse("rclpy and tf2_ros are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   str(exc))

    cfg = _common.load_config(TOOL, REQUIRED_KEYS)

    class DetectedDock(Node):
        def __init__(self):
            super().__init__(cfg.s("docking.detected_node_name"))
            self._map = cfg.s("frames.map")
            self._tag = cfg.s("apriltag.tag_frame")
            self._buf = Buffer()
            TransformListener(self._buf, self)
            self._pub = self.create_publisher(
                PoseStamped, cfg.s("topics.detected_dock_pose"), 10)
            period = 1.0 / float(cfg.s("docking.detected_rate_hz"))
            self.create_timer(period, self._tick)

        def _tick(self):
            try:
                tf = self._buf.lookup_transform(
                    self._map, self._tag, rclpy.time.Time())
            except Exception:
                return
            msg = PoseStamped()
            msg.header = tf.header
            msg.header.frame_id = self._map
            msg.pose.position.x = tf.transform.translation.x
            msg.pose.position.y = tf.transform.translation.y
            msg.pose.position.z = tf.transform.translation.z
            msg.pose.orientation = tf.transform.rotation
            self._pub.publish(msg)

    rclpy.init()
    node = DetectedDock()
    try:
        rclpy.spin(node)
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
