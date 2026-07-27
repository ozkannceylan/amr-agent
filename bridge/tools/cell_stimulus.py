#!/usr/bin/env python3
"""TEST SCAFFOLDING — operator-panel stimulus and product-pose observer.

The demonstration cell has no physics for the three pushbuttons: they are ROS
topics that "a human, a test script or the m3-04 bridge drives exactly as it
will drive real wired contacts" (sim/README.md). Nothing in the cell publishes
them on its own, so an evidence run needs a stand-in for the human at the
panel. That is all this file is.

It is stimulus, not part of the bridge and not part of the cell:

* it publishes the three `/cell/panel/*` contacts on a scripted timeline,
  exactly as `ros2 topic pub` would;
* it logs `/cell/product_box/pose` (ground truth, deliberately NOT a PLC
  signal — opcua-nodes.md §9.8) so that "the belt actually moved the product"
  is observable headless.

It writes no OPC UA node, holds no bridge state, and applies no logic to any
cell signal.

    python3 bridge/tools/cell_stimulus.py \
        --script "0:stop=true,0:process_stop=true,0:start=false,20:start=true" \
        --duration 120 --pose-log /tmp/pose.csv
"""

from __future__ import annotations

import argparse
import csv
import time

import rclpy
from geometry_msgs.msg import PoseArray
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState, LaserScan
from std_msgs.msg import Bool

CONTACTS = {
    "start": "/cell/panel/start",
    "stop": "/cell/panel/stop",
    "process_stop": "/cell/panel/process_stop",
}


class Stimulus(Node):
    def __init__(self, script: list[tuple[float, str, bool]], pose_log: str | None) -> None:
        super().__init__("cell_panel_stimulus")
        qos = QoSProfile(history=HistoryPolicy.KEEP_LAST, depth=1,
                         reliability=ReliabilityPolicy.RELIABLE,
                         durability=DurabilityPolicy.VOLATILE)
        self._pubs = {name: self.create_publisher(Bool, topic, qos) for name, topic in CONTACTS.items()}
        self._script = sorted(script)
        self._done = 0
        self._t0 = time.monotonic()
        self._state: dict[str, bool | None] = {name: None for name in CONTACTS}
        self._last_refresh = 0.0
        self._pose_log = pose_log
        self._rows: list[list] = []
        self._last_pose_x = None
        self._last_belt = (None, None)
        self._last_range = None
        self.create_subscription(PoseArray, "/cell/product_box/pose", self._on_pose, 10)
        self.create_subscription(JointState, "/cell/conveyor/joint_state", self._on_joint, 10)
        self.create_subscription(LaserScan, "/cell/product_sensor/scan", self._on_scan, 10)
        self.create_timer(0.05, self._tick)
        if pose_log:
            with open(pose_log, "w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow(["wall_s", "sim_s", "box_x", "belt_pos", "belt_vel", "range"])

    def _on_pose(self, msg: PoseArray) -> None:
        if not msg.poses:
            return
        self._last_pose_x = msg.poses[0].position.x
        sim = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e9
        if self._pose_log:
            with open(self._pose_log, "a", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerow([
                    round(time.monotonic() - self._t0, 3), round(sim, 3),
                    round(self._last_pose_x, 4),
                    self._last_belt[0], self._last_belt[1], self._last_range])

    def _on_joint(self, msg: JointState) -> None:
        if "belt_joint" in msg.name:
            i = list(msg.name).index("belt_joint")
            self._last_belt = (round(msg.position[i], 4), round(msg.velocity[i], 4))

    def _on_scan(self, msg: LaserScan) -> None:
        if len(msg.ranges):
            self._last_range = round(float(msg.ranges[0]), 4)

    def _tick(self) -> None:
        now = time.monotonic() - self._t0
        while self._done < len(self._script) and self._script[self._done][0] <= now:
            _, name, value = self._script[self._done]
            self._state[name] = value
            self._publish(name, value)
            self.get_logger().info(f"t={now:6.2f}s  panel {name} := {value}")
            self._done += 1
        # A contact is a LEVEL, and a ROS topic is not retained: a single
        # publish made before the subscriber has been discovered is simply
        # lost. Real wired contacts are re-read every PLC scan, so the
        # stimulus republishes the current level once a second. The bridge
        # writes bools on change, so a republished identical level produces
        # no OPC UA write — which is itself part of what the evidence shows.
        if now - self._last_refresh >= 1.0:
            self._last_refresh = now
            for name, value in self._state.items():
                if value is not None:
                    self._publish(name, value)

    def _publish(self, name: str, value: bool) -> None:
        msg = Bool()
        msg.data = value
        self._pubs[name].publish(msg)


def parse_script(text: str) -> list[tuple[float, str, bool]]:
    out = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        when, assignment = item.split(":", 1)
        name, value = assignment.split("=", 1)
        out.append((float(when), name.strip(), value.strip().lower() == "true"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="panel stimulus + pose observer (TEST SCAFFOLDING)")
    parser.add_argument("--script", default="0:stop=true,0:process_stop=true,0:start=false")
    parser.add_argument("--duration", type=float, default=60.0)
    parser.add_argument("--pose-log", default=None)
    args = parser.parse_args()

    rclpy.init()
    node = Stimulus(parse_script(args.script), args.pose_log)
    end = time.monotonic() + args.duration
    try:
        while rclpy.ok() and time.monotonic() < end:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
