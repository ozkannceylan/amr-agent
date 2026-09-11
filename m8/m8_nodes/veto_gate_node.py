#!/usr/bin/env python3
"""veto_gate_node.py — Phase A shadow gate. Refuse all, log all.

    python3 m8/m8_nodes/veto_gate_node.py

Subscribes /m8/proposal and /m8/health. Publishes /m8/verdict and
/m8/log. Never publishes a consumer command (R1: shadow). ROS imports
live in main().
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core.gate import Gate, Health                          # noqa: E402
from m8_core.topics import HEALTH, LOG, PROPOSAL, VERDICT      # noqa: E402
from m8_core.wire import (                                     # noqa: E402
    dumps_verdict, loads_health, loads_proposal)


def evaluate_json(gate, proposal_text, now_s, health=None):
    """Pure entry the tests call. Returns (verdict_json, log_row)."""
    proposal = loads_proposal(proposal_text)
    verdict = gate.evaluate(proposal, float(now_s), health)
    return dumps_verdict(verdict), verdict.log_row()


def main():
    try:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import String
    except ImportError as exc:
        sys.stderr.write(
            "veto_gate_node needs rclpy (vehicle graph): {}\n".format(exc))
        sys.exit(2)

    class VetoGate(Node):
        def __init__(self):
            super().__init__("m8_veto_gate")
            self._gate = Gate(phase="A")
            self._health = Health()
            self._pub_v = self.create_publisher(String, VERDICT, 10)
            self._pub_log = self.create_publisher(String, LOG, 10)
            self.create_subscription(String, PROPOSAL, self._cb_proposal, 20)
            self.create_subscription(String, HEALTH, self._cb_health, 10)
            self.get_logger().info(
                "Phase A gate: refuse all, log all. {} → {}".format(
                    PROPOSAL, VERDICT))

        def _cb_health(self, msg):
            try:
                self._health = loads_health(msg.data)
            except (ValueError, KeyError, TypeError):
                self._health = Health()

        def _cb_proposal(self, msg):
            now = self.get_clock().now().nanoseconds * 1e-9
            try:
                text, _row = evaluate_json(
                    self._gate, msg.data, now, self._health)
            except (ValueError, KeyError, TypeError) as exc:
                self.get_logger().warn("proposal refused as invalid: {}".format(exc))
                return
            out = String()
            out.data = text
            self._pub_v.publish(out)
            log = String()
            log.data = text
            self._pub_log.publish(log)

    rclpy.init()
    node = VetoGate()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
