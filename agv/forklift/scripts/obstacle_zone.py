#!/usr/bin/env python3
"""obstacle_zone.py - forward stop-zone evaluator for the forklift scanner.

WHAT THIS NODE IS
  A reader of /forklift/scan that answers one question at a fixed rate:
  is anything inside the forward sector closer than the stop distance?

      /forklift/scan -> /forklift/obstacle/in_stop_zone   [std_msgs/Bool]
                     -> /forklift/obstacle/min_distance   [std_msgs/Float64]

WHAT THIS NODE IS NOT
  IT IS NOT A SAFETY FUNCTION AND MUST NEVER BE PRESENTED AS ONE. It is
  Python, it reads a scan that has crossed a bridge, and it publishes on a
  network. The protective stop, the e-stop chain and safe torque off are
  onboard, hardwired and independent of every topic named above
  (invariant 1). What this node produces is a process comfort zone: an
  input to speed and to order execution, at the same integrity level as
  any other process signal.

WIRE NC, PROGRAM NO, CARRIED INTO THE VEHICLE LAYER
  CLAUDE.md section 9 asks stop devices to be wired so that losing the
  signal stops the machine. The network equivalent here: absence of data
  IS an obstacle. A scan that is missing, stale, structurally unusable, or
  that contains no valid sample in the sector, publishes

      in_stop_zone = True      min_distance = obstacle.unknown_distance_m

  Never the clear state. A sample is counted only by an affirmative test,
  finite AND inside the scan's own [range_min, range_max] window, so a NaN
  fails every comparison and lands in the obstacle branch rather than
  passing as a measurement.

  Staleness is judged against this node's own monotonic clock at the
  moment of receipt, never against the publisher's header stamp. A
  watchdog that trusts the timestamp of the thing it is watching is not a
  watchdog, and on this host CLOCK_REALTIME steps by design.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 agv/forklift/scripts/obstacle_zone.py [--config PATH] [--ros-args ...]
"""

import argparse
import math
import os
import sys
import time

import rclpy
import yaml
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool, Float64

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


class ObstacleZone(Node):
    """Fixed-rate forward stop-zone evaluator for one planar scanner."""

    def __init__(self, cfg):
        super().__init__('obstacle_zone')
        self.cfg = cfg

        obstacle = cfg['obstacle']
        topics = cfg['topics']

        self.sector_half_angle_rad = obstacle['sector_half_angle_rad']
        self.stop_distance_m = obstacle['stop_distance_m']
        self.scan_timeout_s = obstacle['scan_timeout_s']
        self.unknown_distance_m = obstacle['unknown_distance_m']
        self.evaluate_period_s = 1.0 / cfg['rates']['obstacle_publish_hz']
        self.throttle_s = cfg['logging']['throttle_s']

        qos = QoSProfile(depth=cfg['qos']['depth'])

        self.last_scan = None
        self.last_scan_received_s = None
        self.last_reported = None

        self.pub_in_stop_zone = self.create_publisher(
            Bool, topics['obstacle_in_stop_zone'], qos)
        self.pub_min_distance = self.create_publisher(
            Float64, topics['obstacle_min_distance'], qos)
        self.sub_scan = self.create_subscription(
            LaserScan, topics['scan'], self.cb_scan, qos)

        self.timer_evaluate = self.create_timer(
            self.evaluate_period_s, self.cb_evaluate)

        self.get_logger().info(
            'obstacle_zone up: sector +-{:.4f} rad, stop distance {:.2f} m, '
            'scan timeout {:.2f} s, rate {:.1f} Hz'.format(
                self.sector_half_angle_rad, self.stop_distance_m,
                self.scan_timeout_s, cfg['rates']['obstacle_publish_hz']))

    # ---------------------------------------------------------------- #
    # Callbacks are named cb_* so that none of them can shadow an rclpy
    # Node attribute.
    # ---------------------------------------------------------------- #

    def cb_scan(self, msg):
        """Take the scan and stamp its arrival with the local monotonic
        clock. The header stamp is deliberately not used for age."""
        self.last_scan = msg
        self.last_scan_received_s = time.monotonic()

    def cb_evaluate(self):
        """Publish the verdict and the distance, every cycle, unconditionally."""
        in_zone, distance, reason = self.evaluate()

        zone_msg = Bool()
        zone_msg.data = in_zone
        self.pub_in_stop_zone.publish(zone_msg)

        distance_msg = Float64()
        distance_msg.data = distance
        self.pub_min_distance.publish(distance_msg)

        if reason != self.last_reported:
            self.last_reported = reason
            self.get_logger().info(
                'in_stop_zone={} min_distance={:.3f} reason={}'.format(
                    in_zone, distance, reason))
        elif in_zone:
            self.get_logger().warn(
                'stop zone occupied: min_distance={:.3f} reason={}'.format(
                    distance, reason),
                throttle_duration_sec=self.throttle_s)

    # ---------------------------------------------------------------- #
    # Evaluation. Separated from publication so the decision is one
    # function with one return contract: (in_stop_zone, distance, reason).
    # ---------------------------------------------------------------- #

    def evaluate(self):
        if self.last_scan is None or self.last_scan_received_s is None:
            return True, self.unknown_distance_m, 'no scan received'

        age_s = time.monotonic() - self.last_scan_received_s
        if age_s > self.scan_timeout_s:
            return True, self.unknown_distance_m, 'scan stale'

        scan = self.last_scan

        # Plausibility of the scan's own validity window, before any range
        # is tested against it. A window that is itself NaN or inverted
        # cannot qualify a sample, so the scan is unusable, not clear.
        window_ok = (math.isfinite(scan.range_min)
                     and math.isfinite(scan.range_max)
                     and scan.range_min < scan.range_max)
        if not window_ok:
            return True, self.unknown_distance_m, 'scan range window unusable'

        if not scan.ranges or not math.isfinite(scan.angle_increment) \
                or scan.angle_increment == 0.0:
            return True, self.unknown_distance_m, 'scan geometry unusable'

        minimum = None
        for index, sample in enumerate(scan.ranges):
            angle = scan.angle_min + index * scan.angle_increment
            if abs(angle) > self.sector_half_angle_rad:
                continue
            # Affirmative validity: finite AND inside the window. A NaN
            # fails isfinite and both comparisons, so it can never be
            # counted as a measurement.
            valid = (math.isfinite(sample)
                     and scan.range_min <= sample
                     and sample <= scan.range_max)
            if not valid:
                continue
            if minimum is None or sample < minimum:
                minimum = sample

        if minimum is None:
            return True, self.unknown_distance_m, 'no valid sample in sector'

        if minimum <= self.stop_distance_m:
            return True, minimum, 'obstacle in sector'
        return False, minimum, 'sector clear'


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Forward stop-zone evaluator for the forklift scanner.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    args, ros_argv = parser.parse_known_args(argv)

    cfg = load_config(args.config)

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = ObstacleZone(cfg)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
