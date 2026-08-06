#!/usr/bin/env python3
"""Read-only witness of the envelope chain's vehicle end. TEST INSTRUMENT.

It subscribes and it does **nothing else**: no publisher, no service, no
parameter it offers, and no value it computes that any other node consumes. It
exists so that a run's claim — "a PLC-formed envelope reached the gate and the
vehicle stopped" — is a recording rather than a memory, and so that the
envelope's arrival on the vehicle side can be timed against the same run's
ground-truth speed.

What it records, one CSV row per sample of any of them:

  * the four topics the bridge republishes from `Forklift/Mode/` and
    `Forklift/Envelope/` (`opcua-nodes.md` §12.10);
  * the two the vehicle publishes back;
  * `/cmd_vel_gated` — what the gate is letting through;
  * `/cmd_vel_smoothed` — what the navigation stack is asking for;
  * `/forklift/odom` — the simulator's own pose of the model, the ground truth
    for "did the vehicle actually stop".

It is not part of any bridge run and nothing in the bridge imports it.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
    python3 bridge/tools/observe_envelope_chain.py --csv <path> --seconds 120
"""

from __future__ import annotations

import argparse
import csv
import time

import rclpy
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_msgs.msg import Bool, Float64, UInt16


class EnvelopeChainWitness(Node):
    def __init__(self, writer, started_ns: int) -> None:
        super().__init__("envelope_chain_witness")
        self._writer = writer
        self._t0 = started_ns
        qos = QoSProfile(depth=10)

        # Callbacks are cb_* in this project: rclpy.node.Node owns attributes
        # such as self._clock and a colliding name is silently shadowed
        # (LESSONS 2026-07-27).
        self.create_subscription(
            UInt16, "/forklift/mode/in_force",
            lambda m: self.cb_row("mode_in_force", m.data), qos)
        self.create_subscription(
            Bool, "/forklift/envelope/motion_enable",
            lambda m: self.cb_row("motion_enable", int(m.data)), qos)
        self.create_subscription(
            Float64, "/forklift/envelope/speed_ceiling",
            lambda m: self.cb_row("speed_ceiling", m.data), qos)
        self.create_subscription(
            Bool, "/forklift/envelope/equipment_permit",
            lambda m: self.cb_row("equipment_permit", int(m.data)), qos)
        self.create_subscription(
            UInt16, "/forklift/mode/applied",
            lambda m: self.cb_row("mode_applied", m.data), qos)
        self.create_subscription(
            UInt16, "/forklift/vehicle/heartbeat",
            lambda m: self.cb_row("vehicle_heartbeat", m.data), qos)
        self.create_subscription(
            Twist, "/cmd_vel_smoothed",
            lambda m: self.cb_row("cmd_smoothed_vx", m.linear.x), qos)
        self.create_subscription(
            Twist, "/cmd_vel_gated",
            lambda m: self.cb_row("cmd_gated_vx", m.linear.x), qos)
        self.create_subscription(
            Odometry, "/forklift/odom",
            lambda m: self.cb_row("odom_vx", m.twist.twist.linear.x), qos)

    def cb_row(self, signal: str, value) -> None:
        # CLOCK_MONOTONIC on this host, differenced only against itself
        # (bridge-design.md §9.1 C1/C2). No sim time is differenced here.
        now = time.monotonic_ns()
        self._writer.writerow(
            [f"{(now - self._t0) / 1e9:.4f}", signal, value])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", required=True)
    parser.add_argument("--seconds", type=float, default=120.0)
    args = parser.parse_args()

    # Exclusive create: a witness must never truncate an earlier capture
    # (LESSONS 2026-07-28).
    with open(args.csv, "x", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["t_s", "signal", "value"])
        rclpy.init()
        started = time.monotonic_ns()
        node = EnvelopeChainWitness(writer, started)
        deadline = started + int(args.seconds * 1e9)
        try:
            while rclpy.ok() and time.monotonic_ns() < deadline:
                rclpy.spin_once(node, timeout_sec=0.2)
                handle.flush()
        finally:
            node.destroy_node()
            rclpy.shutdown()
    print(f"witness finished: {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
