#!/usr/bin/env python3
"""obstacle_zone.py - forward stop-zone evaluator for the forklift.

WHAT THIS NODE IS
  A reader of one scan that answers one question at a fixed rate: is
  anything inside the forward sector closer than the stop distance?

      /forklift/safety_scanner_front/measurement
                     -> /forklift/obstacle/in_stop_zone   [std_msgs/Bool]
                     -> /forklift/obstacle/min_distance   [std_msgs/Float64]

WHICH CHANNEL IT READS, AND WHY THAT IS NOT A LAYER VIOLATION
  The device class the front scanner models emits TWO outputs: a safe one
  (OSSD pair, or safe bits over PROFIsafe) and a separate NON-SAFE
  MEASUREMENT channel its datasheet provides for HMI, diagnostics and
  process use while stating it must not be used for safety-related tasks.
  This node reads the SECOND one. A process function consuming a device's
  process output is what that output exists for; what ADR 0011 forbids is
  a safety scanner feeding a NAVIGATION consumer - SLAM, AMCL, a costmap
  - and that prohibition is untouched here. The navigation lidar remains
  the only SLAM input, on /forklift/scan, and this node does not read it.

  It does not read it for a physical reason as well as an architectural
  one: the navigation lidar's plane is z = 1.80 m, where a pallet, a
  crate and the arena's 0.60 m walls are all invisible. This channel's
  plane is z = 0.15 m, which is the low plane the M4 commissioning
  showcase demonstrated.

WHAT THIS NODE IS NOT
  IT IS NOT A SAFETY FUNCTION AND MUST NEVER BE PRESENTED AS ONE, and
  reading a safety scanner's measurement channel does not make it one.
  It is Python, it reads a rendered scan that has crossed a bridge, and
  it publishes on a network: no integrity, no OSSD, no fault reaction, no
  diagnostic coverage. The protective stop, the e-stop chain and safe
  torque off are onboard, hardwired and independent of every topic named
  above (invariant 1). What this node produces is a process comfort zone:
  an input to speed and to order execution, at the same integrity level
  as any other process signal. The OSSD-equivalent verdict derived from
  the same device is a different signal, on a different path, and it is
  not computed here.

WHERE THE SECTOR POINTS
  The sector is centred on the driving direction OF THE VEHICLE, but the
  angles in a scan are measured in the SENSOR's frame, and this sensor
  sits on a chassis corner at a mount yaw of +45 deg. The centre is
  therefore obstacle.sector_centre_rad, which config.yaml derives as
  minus that mount yaw, and scripts/check_sensor_frames.py checks it
  against model.sdf. A centre of zero would watch the diagonal 15..75 deg
  off the bow and report it as "straight ahead".

THREE CLASSES OF SAMPLE, AND WHY THE MIDDLE ONE IS NOT MISSING DATA
  A rangefinder answers "how far" with three different kinds of answer,
  and only the last of them is an absence:

    CLEAR     +inf, or a finite range at or beyond range_max. The beam
              went out and nothing came back inside the sensor's window.
              That is a measurement: the path is clear to range_max. It
              is valid, it contributes range_max, and it never triggers
              the fail-safe.
    DISTANCE  a finite range inside [range_min, range_max). The thing
              the sector is watched for.
    INVALID   NaN, -inf, or a range below range_min. Not an answer.

  Both valid classes are recognised by affirmative comparisons, so a NaN,
  which makes every comparison false, reaches neither and lands in
  INVALID rather than passing as a measurement. This is the same rule the
  PLC layer applies to every Real it reads.

WIRE NC, PROGRAM NO, CARRIED INTO THE VEHICLE LAYER
  CLAUDE.md section 9 asks stop devices to be wired so that losing the
  signal stops the machine. The network equivalent here: absence of DATA
  is an obstacle. A scan that is missing, stale, structurally unusable,
  or whose sector holds no sample in EITHER valid class, publishes

      in_stop_zone = True      min_distance = obstacle.unknown_distance_m

  Never the clear state. But absence of an ECHO is not absence of data. A
  forward sector that is entirely beyond range publishes

      in_stop_zone = False     min_distance = scan.range_max

  A dead sensor and a garbage sensor still stop the machine; an open
  horizon does not. Conflating the two was a real defect: on 2026-07-29 a
  teleop run took a process stop every time the heading opened up, with a
  healthy 10 Hz scan behind the verdict.

  min_distance in that case is the SCAN's range_max, not a constant of
  this node, so it follows the sensor the model declares. The consumer's
  plausibility window has to contain it: docs/interfaces/opcua-nodes.md
  section 10.5 gives 0.05 to 8.10 m against this scanner's 0.10 to
  5.50 m.

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


#: A sample either measures a distance, measures that the path is clear to
#: the end of the sensor's window, or is not an answer at all.
CLASS_DISTANCE = 'distance'
CLASS_CLEAR = 'clear'
CLASS_INVALID = 'invalid'


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def wrap_angle(angle):
    """Fold an angle onto (-pi, pi], so a sector can straddle the seam.

    The scan of a corner-mounted sensor runs to +-137.5 deg and the
    sector centre is -45 deg, so (angle - centre) reaches +182.5 deg and
    must fold, or samples on the far edge of the aperture would test as
    if they were behind the vehicle.
    """
    return (angle + math.pi) % (2.0 * math.pi) - math.pi


def in_sector(angle, centre, half_width):
    """Is this sample's bearing inside the watched sector?"""
    return abs(wrap_angle(angle - centre)) <= half_width


def classify_sample(sample, range_min, range_max):
    """Put one range into one of the three classes above.

    Both valid classes are affirmative comparisons, tested in order, so a
    NaN reaches neither and is INVALID; so does -inf, and so does anything
    below range_min. +inf fails the first test and passes the second,
    which is the whole point: no echo is a clear path, not a missing one.

    The caller has already established that range_min and range_max are
    finite and ordered. That is what makes a sample bounded between them
    necessarily finite, and it is why no isfinite() call is needed here.
    """
    if range_min <= sample and sample < range_max:
        return CLASS_DISTANCE
    if sample >= range_max:
        return CLASS_CLEAR
    return CLASS_INVALID


class ObstacleZone(Node):
    """Fixed-rate forward stop-zone evaluator for one planar scanner."""

    def __init__(self, cfg):
        super().__init__('obstacle_zone')
        self.cfg = cfg

        obstacle = cfg['obstacle']
        topics = cfg['topics']

        self.sector_half_angle_rad = obstacle['sector_half_angle_rad']
        self.sector_centre_rad = obstacle['sector_centre_rad']
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
        # The source is the front safety scanner's NON-SAFE MEASUREMENT
        # channel. The key is named for the channel and not for a generic
        # "scan", so that changing which channel this process function
        # consumes is a visible edit here rather than a quiet edit of a
        # topic string somewhere else.
        self.source_topic = topics['safety_scanner_front_measurement']
        self.sub_scan = self.create_subscription(
            LaserScan, self.source_topic, self.cb_scan, qos)

        self.timer_evaluate = self.create_timer(
            self.evaluate_period_s, self.cb_evaluate)

        self.get_logger().info(
            'obstacle_zone up: source {} (non-safe measurement channel), '
            'sector {:.4f} +-{:.4f} rad in the scan frame, stop distance '
            '{:.2f} m, scan timeout {:.2f} s, rate {:.1f} Hz'.format(
                self.source_topic, self.sector_centre_rad,
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
        # cannot classify a sample, so the scan is unusable, not clear.
        window_ok = (math.isfinite(scan.range_min)
                     and math.isfinite(scan.range_max)
                     and scan.range_min < scan.range_max)
        if not window_ok:
            return True, self.unknown_distance_m, 'scan range window unusable'

        if not scan.ranges or not math.isfinite(scan.angle_increment) \
                or scan.angle_increment == 0.0:
            return True, self.unknown_distance_m, 'scan geometry unusable'

        nearest = None      # smallest DISTANCE-class sample in the sector
        clear_seen = False  # the sector produced at least one CLEAR sample
        for index, sample in enumerate(scan.ranges):
            angle = scan.angle_min + index * scan.angle_increment
            if not in_sector(angle, self.sector_centre_rad,
                             self.sector_half_angle_rad):
                continue
            sample_class = classify_sample(
                sample, scan.range_min, scan.range_max)
            if sample_class == CLASS_DISTANCE:
                if nearest is None or sample < nearest:
                    nearest = sample
            elif sample_class == CLASS_CLEAR:
                clear_seen = True

        # The fail-safe fires only when the sector yielded nothing in
        # EITHER valid class: a dead or a garbage sensor. An open horizon
        # yields CLEAR samples and is a measurement, not an absence.
        if nearest is None and not clear_seen:
            return True, self.unknown_distance_m, 'no valid sample in sector'

        if nearest is None:
            # Every sample in the sector went out and came back with
            # nothing inside the window, so the nearest thing the sensor
            # could have seen is at range_max. That is the measurement,
            # and it is the scan's own number rather than one of ours.
            return False, scan.range_max, 'sector clear beyond range'

        if nearest <= self.stop_distance_m:
            return True, nearest, 'obstacle in sector'
        return False, nearest, 'sector clear'


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
