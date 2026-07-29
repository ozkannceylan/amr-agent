#!/usr/bin/env python3
"""forklift_io.py - engineering-unit command and state node for the forklift.

WHAT THIS NODE IS
  A unit translator and a slew limiter, and nothing else. It turns three
  vehicle-side commands in engineering units into the raw joint commands
  model.sdf listens on, and it turns two bridged feedback messages into two
  plain scalars other vehicle software can read.

      /forklift/cmd/traction_speed  [m/s]  -> /forklift/gz/traction_cmd [rad/s]
      /forklift/cmd/steer_angle     [rad]  -> /forklift/gz/steer_cmd    [rad]
      /forklift/cmd/fork_speed      [m/s]  -> /forklift/gz/fork_cmd     [m]

      /forklift/joint_states  -> /forklift/fork_height   [m]
      /forklift/odom          -> /forklift/linear_speed  [m/s]

WHAT THIS NODE IS NOT
  It is not a safety function. Nothing here inhibits motion, latches a
  fault or performs a stop. Protective stop, e-stop and safe torque off are
  onboard and hardwired, and no message on any of these topics can trigger
  or release one (invariant 1). It is also not a real-time controller: the
  physical loop closing happens in the joint controllers, so a late timer
  here degrades smoothness and nothing else (invariant 9).

  It holds no fleet state, speaks no VDA 5050 and knows no order. It is the
  layer under that.

TWO REPUBLICATION POLICIES, ON PURPOSE
  Steer and traction are published on receipt only. Their safe value is
  zero, so if the simulator is restarted under this node the joints sit at
  centred and stopped until something commands again.
  The fork target is republished every cycle, because its safe value is
  hold, not zero, and a lift that silently returns to the floor on a
  restart would be the wrong failure direction.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 agv/forklift/scripts/forklift_io.py [--config PATH] [--ros-args ...]
"""

import argparse
import math
import os
import sys
import time

import rclpy
import yaml
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

# The config ships next to this directory, so resolve it from this file
# rather than from a package share path or the caller's working directory.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def clamp(value, low, high):
    """Bound a value to [low, high]. Written affirmatively, so a NaN input
    falls through both comparisons and is returned unchanged rather than
    silently becoming a limit; callers reject NaN before calling."""
    if value < low:
        return low
    if value > high:
        return high
    return value


class ForkliftIo(Node):
    """Command translation and state derivation for one forklift."""

    def __init__(self, cfg):
        super().__init__('forklift_io')
        self.cfg = cfg

        model = cfg['model']
        limits = cfg['limits']
        rates = cfg['rates']
        topics = cfg['topics']

        self.wheel_radius_m = model['wheel_radius_m']
        self.steer_limit_rad = model['steer_limit_rad']
        self.fork_min_m = model['fork_travel_min_m']
        self.fork_max_m = model['fork_travel_max_m']
        self.mast_joint_name = model['mast_joint_name']

        self.traction_speed_max = limits['traction_speed_max_mps']
        self.fork_speed_max = limits['fork_speed_max_mps']

        self.command_period_s = 1.0 / rates['io_command_hz']
        self.state_period_s = 1.0 / rates['io_publish_hz']
        self.throttle_s = cfg['logging']['throttle_s']

        qos = QoSProfile(depth=cfg['qos']['depth'])

        # Integrated fork target and its measured feedback. The target is
        # seeded from the first measurement so that starting this node
        # never moves the carriage.
        self.fork_speed_cmd_mps = 0.0
        self.fork_target_m = None
        self.fork_height_m = None
        self.linear_speed_mps = None

        # Monotonic, never the wall clock: the WSL host steps CLOCK_REALTIME
        # and an integration interval measured against it would be wrong.
        self.last_integration_s = time.monotonic()

        self.pub_gz_steer = self.create_publisher(
            Float64, topics['gz_steer_cmd'], qos)
        self.pub_gz_traction = self.create_publisher(
            Float64, topics['gz_traction_cmd'], qos)
        self.pub_gz_fork = self.create_publisher(
            Float64, topics['gz_fork_cmd'], qos)
        self.pub_fork_height = self.create_publisher(
            Float64, topics['fork_height'], qos)
        self.pub_linear_speed = self.create_publisher(
            Float64, topics['linear_speed'], qos)

        self.sub_cmd_traction = self.create_subscription(
            Float64, topics['cmd_traction_speed'], self.cb_cmd_traction_speed, qos)
        self.sub_cmd_steer = self.create_subscription(
            Float64, topics['cmd_steer_angle'], self.cb_cmd_steer_angle, qos)
        self.sub_cmd_fork = self.create_subscription(
            Float64, topics['cmd_fork_speed'], self.cb_cmd_fork_speed, qos)
        self.sub_joint_states = self.create_subscription(
            JointState, topics['joint_states'], self.cb_joint_states, qos)
        self.sub_odom = self.create_subscription(
            Odometry, topics['odom'], self.cb_odom, qos)

        self.timer_command = self.create_timer(
            self.command_period_s, self.cb_command_cycle)
        self.timer_state = self.create_timer(
            self.state_period_s, self.cb_state_cycle)

        self.get_logger().info(
            'forklift_io up: wheel radius {:.3f} m, steer limit +-{:.3f} rad, '
            'fork travel {:.2f} to {:.2f} m, fork rate limit {:.3f} m/s'.format(
                self.wheel_radius_m, self.steer_limit_rad,
                self.fork_min_m, self.fork_max_m, self.fork_speed_max))

    # ---------------------------------------------------------------- #
    # Command inputs. Callbacks are named cb_* so that none of them can
    # shadow an rclpy Node attribute.
    # ---------------------------------------------------------------- #

    def cb_cmd_traction_speed(self, msg):
        """Ground speed [m/s] to wheel spin rate [rad/s]."""
        if not math.isfinite(msg.data):
            self.get_logger().warn('traction speed command is not finite, ignored')
            return
        speed = clamp(msg.data, -self.traction_speed_max, self.traction_speed_max)
        out = Float64()
        out.data = speed / self.wheel_radius_m
        self.pub_gz_traction.publish(out)

    def cb_cmd_steer_angle(self, msg):
        """Steer angle [rad], clamped to the mechanical stop and passed on."""
        if not math.isfinite(msg.data):
            self.get_logger().warn('steer angle command is not finite, ignored')
            return
        out = Float64()
        out.data = clamp(msg.data, -self.steer_limit_rad, self.steer_limit_rad)
        self.pub_gz_steer.publish(out)

    def cb_cmd_fork_speed(self, msg):
        """Fork rate request [m/s]. Held, then integrated by the command
        cycle. A zero request is not an actuator command, it is the
        instruction to stop moving the target, which is what makes the
        carriage hold its height."""
        if not math.isfinite(msg.data):
            self.get_logger().warn('fork speed command is not finite, ignored')
            return
        self.fork_speed_cmd_mps = clamp(
            msg.data, -self.fork_speed_max, self.fork_speed_max)

    # ---------------------------------------------------------------- #
    # Feedback inputs.
    # ---------------------------------------------------------------- #

    def cb_joint_states(self, msg):
        """Pick the mast joint out of the bridged joint state."""
        if self.mast_joint_name not in msg.name:
            return
        index = msg.name.index(self.mast_joint_name)
        if index >= len(msg.position):
            return
        value = msg.position[index]
        if not math.isfinite(value):
            return
        self.fork_height_m = value
        if self.fork_target_m is None:
            # Seed the target from the measurement, so this node starting
            # up cannot itself command a movement.
            self.fork_target_m = clamp(value, self.fork_min_m, self.fork_max_m)

    def cb_odom(self, msg):
        """Forward ground speed [m/s] from the bridged odometry twist,
        which the odometry publisher expresses in the vehicle body frame."""
        value = msg.twist.twist.linear.x
        if not math.isfinite(value):
            return
        self.linear_speed_mps = value

    # ---------------------------------------------------------------- #
    # Cycles.
    # ---------------------------------------------------------------- #

    def cb_command_cycle(self):
        """Integrate the fork rate request into a slew-limited position
        target and republish it."""
        now = time.monotonic()
        elapsed = now - self.last_integration_s
        self.last_integration_s = now

        # A late cycle integrates one nominal period, never the whole gap.
        # Under-travel is the conservative direction for a lift.
        step_s = min(elapsed, self.command_period_s)

        if self.fork_target_m is None:
            # No joint state yet, so the carriage position is unknown and
            # there is nothing safe to command. Say so, do not guess.
            self.get_logger().warn(
                'no joint state yet, fork target not seeded',
                throttle_duration_sec=self.throttle_s)
            return

        self.fork_target_m = clamp(
            self.fork_target_m + self.fork_speed_cmd_mps * step_s,
            self.fork_min_m, self.fork_max_m)

        out = Float64()
        out.data = self.fork_target_m
        self.pub_gz_fork.publish(out)

    def cb_state_cycle(self):
        """Publish the two derived state scalars.

        Each topic starts on the first real sample from its source. Nothing
        fabricates a value before the model is up: a height of zero would
        be indistinguishable from a genuinely lowered carriage."""
        if self.fork_height_m is None or self.linear_speed_mps is None:
            self.get_logger().warn(
                'waiting for source data: joint_states={}, odom={}'.format(
                    self.fork_height_m is not None,
                    self.linear_speed_mps is not None),
                throttle_duration_sec=self.throttle_s)

        if self.fork_height_m is not None:
            out = Float64()
            out.data = self.fork_height_m
            self.pub_fork_height.publish(out)

        if self.linear_speed_mps is not None:
            out = Float64()
            out.data = self.linear_speed_mps
            self.pub_linear_speed.publish(out)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Forklift command translation and state derivation node.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    args, ros_argv = parser.parse_known_args(argv)

    cfg = load_config(args.config)

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = ForkliftIo(cfg)
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
