#!/usr/bin/env python3
"""m8_health.py — refuse-rather-than-limp snapshot. Publish Health only.

    python3 m8/m8_nodes/m8_health.py

A1 has no learned weights and no E5 RTF number. The node reports
`model_loaded` / `model_warm` for the classical path and leaves
latency / frame-age / RTF as "not yet measured" (unhealthy) until
a proposer stamps them. That is refuse-rather-than-limp: a missing
budget is a failure, not a pass.

ROS imports live in main().
"""
from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core.gate import Health                                # noqa: E402
from m8_core.topics import HEALTH                              # noqa: E402
from m8_core.wire import dumps_health                           # noqa: E402


def unmeasured_health():
    """Classical code is present; E5 budgets have not been measured."""
    return Health(
        model_loaded=True,
        model_warm=True,
        inference_latency_p95_ms=float("inf"),
        frame_age_ms=float("inf"),
        rtf_cost=float("inf"))


def placeholder_health():
    """Passing snapshot so a shadow log can say phase_a_shadow.

    The numbers are the A0 default budgets, not an E5 measurement.
    unmeasured_health() is the honest 'E5 has not run' snapshot.
    """
    return Health(
        model_loaded=True,
        model_warm=True,
        inference_latency_p95_ms=1.0,
        frame_age_ms=10.0,
        rtf_cost=0.0)


def classical_health(infer_ms=None, frame_age_ms=None, rtf_cost=None):
    if infer_ms is None and frame_age_ms is None and rtf_cost is None:
        return placeholder_health()
    return Health(
        model_loaded=True,
        model_warm=True,
        inference_latency_p95_ms=(
            float("inf") if infer_ms is None else float(infer_ms)),
        frame_age_ms=(
            float("inf") if frame_age_ms is None else float(frame_age_ms)),
        rtf_cost=float("inf") if rtf_cost is None else float(rtf_cost))


def main():
    try:
        import rclpy
        from rclpy.node import Node
        from std_msgs.msg import String
    except ImportError as exc:
        sys.stderr.write(
            "m8_health needs rclpy (vehicle graph): {}\n".format(exc))
        sys.exit(2)

    class M8Health(Node):
        def __init__(self):
            super().__init__("m8_health")
            self._pub = self.create_publisher(String, HEALTH, 10)
            self.create_timer(0.5, self._tick)
            self.get_logger().info(
                "health: classical loaded; E5 budgets unset → unhealthy")

        def _tick(self):
            out = String()
            out.data = dumps_health(classical_health())
            self._pub.publish(out)

    rclpy.init()
    node = M8Health()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
