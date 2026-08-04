#!/usr/bin/env python3
"""imu_gate.py - the gyro is a rotation sensor only while the vehicle rotates.

WHAT THIS NODE IS
  A one-decision gate on the IMU stream.

      /forklift/imu  +  /forklift/wheel_standstill  ->  /forklift/imu_gated

  It forwards every IMU message unchanged, except while the wheel
  odometry's standstill verdict is true and fresh, when it forwards
  nothing. `ekf.yaml` names the gated topic as `imu0`, so the filter
  sees the gyro exactly as before whenever the vehicle is moving and
  does not see it at all while the wheels say the vehicle is not.

WHY THAT IS PHYSICS AND NOT A CONVENIENCE
  A MEMS gyro's output is rate + bias + noise, and nothing in the
  device separates the three. When the encoders report no motion the
  rate term is known independently to be zero - a tricycle's centre of
  rotation lies on its rear axle line and its drive wheel does not, so
  the body cannot turn without the drive wheel travelling (the
  arithmetic is in config.yaml's `standstill:` block, which bounds the
  body rotation over a held count at 0.0101 deg). The verdict is a RATE
  over a trailing window, not a total since the last count change; this
  file does not form it and does not need to know, but brief m5-07e
  changed which intervals it is true in and EVIDENCE_ODOMETRY.md
  section 13 says by how much. What the gyro reports
  in that condition is therefore bias, and integrating it produces
  heading the vehicle does not have. Declining to treat it as a
  rotation measurement is what a real installation does, under the name
  zero-velocity update, and it is the one interval in which the vehicle
  has independent evidence about the truth of the rate.

WHAT IT DELIBERATELY DOES NOT DO
  IT DOES NOT ESTIMATE THE BIAS, AND IT DOES NOT CARRY ANYTHING INTO
  MOTION. The standstill interval is enough to observe the bias and
  subtract it afterwards, which is the other half of what a real
  installation does - and it would improve the drift while moving,
  which is the phenomenon brief m5-07d exists to preserve and gate M5
  exists to correct. This gate changes what happens while the vehicle
  is still and nothing else. When the gate is open, byte for byte, the
  filter is fed what it was fed before this file existed.

  IT DOES NOT REWRITE A MESSAGE. A republished sample with a zeroed
  yaw rate would be a reading this vehicle never took, indistinguishable
  downstream from one it did. The gate suppresses instead, so a gap in
  `/forklift/imu_gated` means "the gate was closed" and can mean
  nothing else. Nothing else on this vehicle consumes the IMU, and the
  filter needs no message in order to keep its heading: the wheel
  odometry's own yaw rate, zero by construction while the counts hold,
  arrives at 50 Hz throughout.

  IT IS NOT A SAFETY FUNCTION AND NOT A REAL-TIME CONTROLLER. It
  degrades an estimate at worst. It inhibits nothing, latches nothing
  and commands nothing; the protective stop and safe torque off are
  onboard and hardwired and appear in no Python file in this directory
  (invariants 1 and 9).

  IT READS NO GROUND TRUTH. Its two inputs are the vehicle's own IMU
  and the vehicle's own encoder verdict.

HOW IT FAILS
  OPEN, in every direction. No verdict yet, a verdict older than
  `standstill.verdict_timeout_s`, a clock that ran backwards - each
  forwards the IMU, which is the behaviour this vehicle had before the
  gate existed. A gate stuck open costs the drift that is already
  measured and documented; a gate stuck closed would hide a real
  rotation from the filter, and that is the failure worth designing
  against.

Usage (after sourcing /opt/ros/jazzy/setup.bash; use /usr/bin/python3 in
the session container, per sim/setup/CONTAINER_TOOLCHAIN.md section 3.3):

  python3 agv/forklift/scripts/imu_gate.py [--config PATH] \
      --ros-args -p use_sim_time:=true

  use_sim_time IS MANDATORY under simulation. The freshness test below
  compares a message stamp against the node's clock, and a node on the
  system clock finds every simulated stamp about 1.8e9 s stale and
  gates nothing, for ever, silently.
"""

import argparse
import os
import sys

import yaml

# ROS is imported in main(), not here, so that the decision function
# below can be exercised with no ROS present - the same pattern, and the
# same reason, as scripts/wheel_odometry.py.

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def gate_is_open(standstill, verdict_age_s, timeout_s):
    """Should this IMU sample be forwarded to the filter?

    Written affirmatively, so that the answer for a missing or stale
    verdict falls out of the structure rather than out of a negation:
    the gate CLOSES only on a verdict that is both true and fresh, and
    everything else is open.
    """
    fresh = (verdict_age_s is not None
             and 0.0 <= verdict_age_s <= timeout_s)
    return not (bool(standstill) and fresh)


def _make_node_class(Node, Imu, Bool, QoSProfile):
    """Build the node class once ROS is importable."""

    class ImuGate(Node):
        """Forward the IMU except while the wheels say the vehicle is still."""

        def __init__(self, cfg):
            super().__init__('imu_gate')

            topics = cfg['topics']
            self.timeout_s = float(cfg['standstill']['verdict_timeout_s'])
            self.throttle_s = float(cfg['logging']['throttle_s'])

            qos = QoSProfile(depth=cfg['qos']['depth'])
            self.pub_imu = self.create_publisher(Imu, topics['imu_gated'], qos)
            self.sub_imu = self.create_subscription(
                Imu, topics['imu'], self.cb_imu, qos)
            self.sub_standstill = self.create_subscription(
                Bool, topics['wheel_standstill'], self.cb_standstill, qos)

            # Latest verdict and the time it was received, on the node's own
            # clock. The Bool message carries no stamp of its own, so the
            # freshness test is "how long since one arrived" rather than
            # "how old is the one that did" - which is the honest reading
            # of an unstamped message and needs use_sim_time to mean
            # anything under simulation.
            self.standstill = False
            self.verdict_at_ns = None

            # Counters, for the log line and for the harness. They are
            # diagnostics and nothing reads them to make a decision.
            self.forwarded = 0
            self.suppressed = 0
            self.last_open = True

            self.get_logger().info(
                'imu_gate up: {} -> {}, closed while {} is true and younger '
                'than {:.3f} s, FAIL OPEN otherwise. It suppresses; it never '
                'rewrites a sample, and it estimates no bias'.format(
                    topics['imu'], topics['imu_gated'],
                    topics['wheel_standstill'], self.timeout_s))

        # ------------------------------------------------------------------ #
        # Input. Named cb_* so it cannot shadow an rclpy Node attribute.
        # ------------------------------------------------------------------ #

        def cb_standstill(self, msg):
            self.standstill = bool(msg.data)
            self.verdict_at_ns = self.get_clock().now().nanoseconds

        def cb_imu(self, msg):
            age_s = None
            if self.verdict_at_ns is not None:
                age_s = (self.get_clock().now().nanoseconds
                         - self.verdict_at_ns) * 1e-9

            is_open = gate_is_open(self.standstill, age_s, self.timeout_s)
            if is_open != self.last_open:
                self.get_logger().info(
                    'gyro gate {} after {} forwarded / {} suppressed'.format(
                        'OPEN - the wheels are turning' if is_open
                        else 'CLOSED - the encoders report no motion, so the '
                             'gyro is reading its own bias',
                        self.forwarded, self.suppressed))
                self.last_open = is_open

            if not is_open:
                self.suppressed += 1
                return
            self.forwarded += 1
            # Forwarded UNCHANGED. No field is touched, including the
            # covariance: the filter must see exactly what the device
            # produced whenever the vehicle is moving.
            self.pub_imu.publish(msg)

    return ImuGate


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Gate the IMU stream on the wheel odometry standstill '
                    'verdict. Suppresses; never rewrites.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    args, ros_argv = parser.parse_known_args(argv)

    cfg = load_config(args.config)

    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from sensor_msgs.msg import Imu
    from std_msgs.msg import Bool

    node_class = _make_node_class(Node, Imu, Bool, QoSProfile)

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = node_class(cfg)
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
