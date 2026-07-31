#!/usr/bin/env python3
"""wheel_odometry.py - the vehicle's own motion estimate, from its own wheels.

WHAT THIS NODE IS
  A dead-reckoning integrator. It reads the forklift's joint states -
  the drive wheel's angle and the steer axis's angle, and nothing else -
  passes them through two modelled encoders, integrates them through
  tricycle kinematics, and publishes the result as one nav_msgs/Odometry.

      /forklift/joint_states  ->  /forklift/odom_wheel
                              ->  /forklift/wheel_standstill

THE SECOND OUTPUT, AND WHY IT IS HERE
  `wheel_standstill` is one boolean: both encoder counts have been
  unchanged for the window in config.yaml's `standstill:` block. It is
  published from this node and from no other because this node owns the
  encoder model (invariant 10) - a consumer that re-derived "is it
  moving" from the raw joint angles would be quantising the same signal
  a second time with its own idea of the count grid.

  It is a MEASUREMENT, not a command and not a machine state. It says
  the wheels are not turning. It does not say the vehicle is enabled,
  parked, safe or stopped, it inhibits nothing and it latches nothing
  (invariants 1 and 9). Its one consumer is scripts/imu_gate.py, which
  uses it to decide whether the gyro's yaw rate is a rotation
  measurement or a reading of the device's bias.

WHAT THIS NODE IS NOT, AND THIS IS THE IMPORTANT PART
  It is NOT the vehicle's pose. It is ONE SENSOR'S OPINION of it, in
  exactly the sense the IMU's yaw rate is another, and it is published so
  that the EKF can fuse the two. A dead-reckoning pose has unbounded
  error by construction; this node says so in its own covariance and the
  EKF is configured to fuse its TWIST and never its POSE.

  It therefore PUBLISHES NO TRANSFORM. forklift/odom -> forklift/base_link
  has exactly one owner and that owner is the EKF (invariant 10). A
  second publisher of that edge is the failure the whole two-phase
  odometry plan exists to prevent, and the cheapest way to guarantee it
  cannot happen is for this file to contain no transform broadcaster at
  all. It does not.

  It reads NO ground truth. /forklift/odom and /forklift/gz/tf_ground_truth
  are the simulator's own pose and this node has never heard of them. An
  estimator that reads ground truth is not an estimator.

  It is not a safety function and not a real-time controller. A late
  cycle here degrades an estimate; it inhibits nothing and latches
  nothing (invariants 1 and 9).

THE KINEMATICS, WRITTEN OUT
  Geometry from model.sdf: the single steered wheel is also the driven
  wheel and leads at x = +0.55; the two passive wheels trail on an axle
  at x = -0.50. So the wheelbase is L = 1.05 m and base_link stands
  d = +0.50 m FORWARD of the rear axle midpoint R. The steer axis passes
  through the wheel centre, so there is no castor trail and the steer
  angle IS the wheel heading.

  Let delta be the steer angle, v_w the drive wheel's tread speed, and
  psi the vehicle heading. The rear wheels cannot slide sideways, so the
  velocity of R is purely longitudinal; call it v_R. The drive wheel's
  contact point sits at R + (L, 0) in the body frame, so its velocity is

      v_D = (v_R, 0) + psidot * zhat x (L, 0) = (v_R, psidot * L)

  and the drive wheel cannot slide sideways either, so v_D must lie
  along its own heading (cos delta, sin delta) with magnitude v_w:

      v_R    = v_w * cos(delta)
      psidot = v_w * sin(delta) / L

  base_link is a different point of the same rigid body, at R + (d, 0):

      v_Bx = v_R
      v_By = d * psidot

  THAT LATERAL TERM IS REAL AND IT IS NOT AN ERROR. base_link genuinely
  moves sideways whenever the vehicle turns, because it is not on the
  rear axle. Reporting v_By = 0, which is what differential-drive
  odometry copied onto a tricycle does, tells the filter the body is not
  doing something it is doing.

  Integration is EXACT over each cycle rather than Euler. With v_w and
  delta held over an interval the rear axle midpoint travels a circular
  arc, so with s = v_w * dt * cos(delta) and dpsi = v_w * dt * sin(delta) / L:

      psi' = psi + dpsi
      R'   = R + (s/dpsi) * (sin(psi') - sin(psi),
                             cos(psi)  - cos(psi'))     if dpsi != 0
      R'   = R + s * (cos(psi + dpsi/2), sin(psi + dpsi/2))  otherwise

  and base_link is placed on the result: B = R + d * (cos psi', sin psi').
  The straight-line branch is the limit of the arc branch and the node
  switches between them on a magnitude test, so no step divides by a
  yaw increment near zero.

THE ERROR MODEL, AND WHERE IT LIVES
  Every error term is a named constant in config.yaml's `odometry:`
  block with its derivation beside it. Nothing is written inline here.
  Three terms, and one deliberate absence:

    drive encoder quantisation   1024 ppr in quadrature = 4096 counts/rev
    steer encoder quantisation   12-bit absolute        = 4096 counts/rev
    steer zero offset            one count; a calibration cannot do better
    NO SLIP TERM                 the physics engine already produces slip
                                 and inventing a second one would be the
                                 move the brief's honesty rule forbids

  The encoders are modelled the way encoders behave: the ABSOLUTE angle
  is snapped onto the count grid and then differenced. Snapping the
  difference instead would discard the residue every cycle and integrate
  a systematic short-fall.

Usage (after sourcing /opt/ros/jazzy/setup.bash; use /usr/bin/python3 in
the session container, per sim/setup/CONTAINER_TOOLCHAIN.md section 3.3):

  python3 agv/forklift/scripts/wheel_odometry.py [--config PATH] \
      --ros-args -p use_sim_time:=true

  use_sim_time IS MANDATORY under simulation. Every joint state is
  stamped with the simulation clock; a node on the system clock computes
  an interval between two clocks and integrates nonsense.
"""

import argparse
import math
import os
import sys

import yaml

# ROS IS IMPORTED IN main(), NOT HERE, and that is deliberate. The
# kinematics and the encoder model below are plain arithmetic, and
# scripts/check_odometry.py's static phase drives them through motions
# with a closed-form answer on a machine with no ROS at all. A module
# level `import rclpy` would make the one check that needs no simulator
# the one check that needs a whole distribution. Same pattern, same
# reason, as scripts/sensor_tf.py's --print.

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))

#: Below this yaw increment the arc integration is replaced by its own
#: straight-line limit. 1e-9 rad over a 0.02 s cycle is 5e-8 rad/s, far
#: under any rate this vehicle can produce, so the branch is chosen by
#: numerical conditioning and never by physics.
_STRAIGHT_EPS_RAD = 1e-9


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def quantise(value, step):
    """Snap a reading onto an encoder's count grid.

    Rounds to nearest, which is what a comparator-based encoder edge does,
    rather than truncating, which would add a half-count systematic bias
    to every reading in one direction.
    """
    return round(value / step) * step


def yaw_to_quaternion(yaw):
    """(x, y, z, w) for a rotation about z only."""
    return (0.0, 0.0, math.sin(yaw * 0.5), math.cos(yaw * 0.5))


def _make_node_class(Node, Odometry, QoSProfile, JointState, Bool):
    """Build the node class once ROS is importable.

    A closure rather than a module-level class, so that this file's
    arithmetic can be imported and exercised with no ROS present.
    """

    class WheelOdometry(Node):
        """Tricycle dead reckoning from the forklift's own joint states."""

        def __init__(self, cfg):
            super().__init__('wheel_odometry')

            model = cfg['model']
            odo = cfg['odometry']
            topics = cfg['topics']
            frames = cfg['frames']

            # ---- geometry, mirrored from model.sdf ----
            self.wheelbase_m = float(model['wheelbase_m'])
            # base_link stands this far FORWARD of the rear axle midpoint.
            self.base_ahead_of_axle_m = -float(model['rear_axle_offset_m'])
            self.drive_joint = model['drive_joint_name']
            self.steer_joint = model['steer_joint_name']

            # ---- the error model ----
            self.rolling_radius_m = float(odo['rolling_radius_m'])
            self.drive_step_rad = 2.0 * math.pi / float(
                odo['drive_encoder_counts_per_rev'])
            self.steer_step_rad = 2.0 * math.pi / float(
                odo['steer_encoder_counts_per_rev'])
            self.steer_zero_offset_rad = float(odo['steer_zero_offset_rad'])
            self.steer_limit_rad = float(model['steer_limit_rad'])

            self.period_s = 1.0 / float(odo['publish_hz'])
            self.timeout_s = float(odo['joint_state_timeout_s'])
            self.var_vx = float(odo['vx_variance'])
            self.var_vy = float(odo['vy_variance'])
            self.var_vyaw = float(odo['vyaw_variance'])
            self.var_pose_unused = float(odo['pose_variance_unused'])
            self.throttle_s = float(cfg['logging']['throttle_s'])

            self.odom_frame = frames['odom']
            self.base_frame = frames['base']

            # ---- the standstill verdict ----
            still = cfg['standstill']
            self.standstill_window_s = float(still['window_s'])
            self.standstill_uses_steer = bool(still['include_steer_axis'])

            qos = QoSProfile(depth=cfg['qos']['depth'])
            self.pub_odom = self.create_publisher(
                Odometry, topics['odom_wheel'], qos)
            self.pub_standstill = self.create_publisher(
                Bool, topics['wheel_standstill'], qos)
            self.sub_joint_states = self.create_subscription(
                JointState, topics['joint_states'], self.cb_joint_states, qos)
            self.timer_integrate = self.create_timer(
                self.period_s, self.cb_integrate)

            # Latest sample held for the integration cycle. Held as a tuple so
            # a half-written sample can never be read: it is replaced, never
            # mutated in place.
            self.sample = None            # (t_s, drive_rad, steer_rad)
            self.last_sample = None       # the previous integrated sample

            # Standstill detection state. `held_counts` is the pair of
            # ENCODER COUNTS the wheels have been sitting on, and
            # `held_since_s` the stamp at which they were first seen there.
            # The verdict is a duration test on that pair, evaluated at the
            # 500 Hz the joint states arrive at rather than at the 50 Hz this
            # node integrates, so a single count between two integration
            # cycles cannot pass unseen.
            self.held_counts = None
            self.held_since_s = None
            self.standstill = False

            # Integrated state: the REAR AXLE MIDPOINT in the odom frame, plus
            # the heading. base_link is derived from it at publication time, so
            # the offset is applied in exactly one place.
            self.axle_x_m = 0.0
            self.axle_y_m = 0.0
            self.yaw_rad = 0.0
            # Twist of the last cycle, body frame.
            self.vx_mps = 0.0
            self.vy_mps = 0.0
            self.vyaw_rps = 0.0

            self.get_logger().info(
                'wheel_odometry up: wheelbase {:.3f} m, base_link {:+.3f} m of '
                'the rear axle, rolling radius {:.4f} m (physics rolls on '
                '{:.4f}), drive step {:.3e} rad, steer step {:.3e} rad, steer '
                'zero offset {:+.3e} rad, publishing {} at {:.1f} Hz, NO '
                'transform'.format(
                    self.wheelbase_m, self.base_ahead_of_axle_m,
                    self.rolling_radius_m, float(model['wheel_radius_m']),
                    self.drive_step_rad, self.steer_step_rad,
                    self.steer_zero_offset_rad, topics['odom_wheel'],
                    1.0 / self.period_s))
            self.get_logger().info(
                'standstill verdict on {}: both encoder counts unchanged for '
                '{:.3f} s ({}), which bounds body rotation at {:.4f} deg/s. '
                'It is an estimator input and inhibits nothing'.format(
                    topics['wheel_standstill'], self.standstill_window_s,
                    'drive and steer' if self.standstill_uses_steer
                    else 'drive only',
                    math.degrees(self.rolling_radius_m * self.drive_step_rad
                                 / self.wheelbase_m
                                 / self.standstill_window_s)))

        # ------------------------------------------------------------------ #
        # Input. Named cb_* so it cannot shadow an rclpy Node attribute.
        # ------------------------------------------------------------------ #

        def cb_joint_states(self, msg):
            """Hold the newest usable joint state, stamped on ITS OWN clock.

            The stamp is the message's, not this node's: the integration
            interval must be the interval the simulator actually advanced, and
            under simulation those are different quantities.
            """
            if self.drive_joint not in msg.name or self.steer_joint not in msg.name:
                self.clear_standstill()
                self.get_logger().warn(
                    'joint state carries {} but this node needs {} and {}'.format(
                        list(msg.name), self.drive_joint, self.steer_joint),
                    throttle_duration_sec=self.throttle_s)
                return
            i_drive = msg.name.index(self.drive_joint)
            i_steer = msg.name.index(self.steer_joint)
            if i_drive >= len(msg.position) or i_steer >= len(msg.position):
                self.clear_standstill()
                return

            drive_rad = msg.position[i_drive]
            steer_rad = msg.position[i_steer]

            # Affirmative plausibility, per the project rule: state the window
            # a real reading lies in and treat anything else as a fault. A
            # negated test would let a NaN through, because every comparison
            # against a NaN is false (LESSONS 2026-07-27).
            drive_ok = -1e12 < drive_rad < 1e12
            margin = self.steer_limit_rad + 0.05
            steer_ok = -margin < steer_rad < margin
            if not (drive_ok and steer_ok):
                self.clear_standstill()
                self.get_logger().warn(
                    'implausible joint state ignored: {}={}, {}={}'.format(
                        self.drive_joint, drive_rad, self.steer_joint, steer_rad),
                    throttle_duration_sec=self.throttle_s)
                return

            stamp = msg.header.stamp
            t_s = stamp.sec + stamp.nanosec * 1e-9
            self.sample = (t_s, drive_rad, steer_rad)
            self.update_standstill(t_s, drive_rad, steer_rad)

        # ------------------------------------------------------------------ #
        # The standstill verdict.
        # ------------------------------------------------------------------ #

        def clear_standstill(self):
            """Anything that is not a usable joint state opens the gate.

            The two failure directions are not symmetric. A verdict stuck
            FALSE costs exactly the drift this vehicle had before the gate
            existed; a verdict stuck TRUE would hide a real rotation from
            the filter. So every uncertainty - a missing joint, a short
            message, an implausible angle, a clock that ran backwards -
            resolves to "not standing still".
            """
            self.held_counts = None
            self.held_since_s = None
            self.standstill = False

        def update_standstill(self, t_s, drive_rad, steer_rad):
            """Have both encoder counts held still for the whole window?

            The counts, not the angles. An encoder reports a count, and two
            angles inside one count are the same reading as far as the
            vehicle can tell - which is the point: the test has to be the
            one the real device could actually perform.
            """
            counts = (round(drive_rad / self.drive_step_rad),
                      round((steer_rad + self.steer_zero_offset_rad)
                            / self.steer_step_rad)
                      if self.standstill_uses_steer else 0)

            if self.held_counts != counts or self.held_since_s is None:
                # A count moved. The gate opens on this sample, with no
                # window and no filtering: distrusting the standstill is
                # instantaneous, trusting it takes the full window.
                self.held_counts = counts
                self.held_since_s = t_s
                self.standstill = False
                return

            held_s = t_s - self.held_since_s
            if held_s < 0.0:
                # The clock went backwards (a simulator reset). Re-arm
                # rather than measure a negative duration.
                self.held_since_s = t_s
                self.standstill = False
                return
            self.standstill = held_s >= self.standstill_window_s

        # ------------------------------------------------------------------ #
        # Integration.
        # ------------------------------------------------------------------ #

        def cb_integrate(self):
            """One dead-reckoning step, then publish."""
            # THE VERDICT IS PUBLISHED FIRST, ABOVE EVERY EARLY RETURN
            # BELOW. Its consumer times it out and fails open, so a
            # verdict that stops arriving is read as "moving" - which is
            # right when the joint states have stopped, and wrong when the
            # vehicle is standing still with a settled integrator. Every
            # cycle emits one, whatever the integrator then decides to do.
            verdict = Bool()
            verdict.data = bool(self.standstill)
            self.pub_standstill.publish(verdict)

            sample = self.sample
            if sample is None:
                self.get_logger().warn(
                    'no joint state yet, nothing to integrate',
                    throttle_duration_sec=self.throttle_s)
                return

            if self.last_sample is None:
                # First sample seeds the encoders and moves nothing. Starting
                # this node cannot itself produce a displacement.
                self.last_sample = sample
                return

            t_now, drive_now, steer_now = sample
            t_prev, drive_prev, _ = self.last_sample
            dt_s = t_now - t_prev

            if dt_s <= 0.0:
                # Same sample again, or the clock went backwards (a simulator
                # reset). Integrate nothing; a repeated sample is not motion.
                return
            if dt_s > self.timeout_s:
                # A gap. Do NOT integrate across it: the joint angle difference
                # over an unobserved interval is real, but the twist it implies
                # is not, and an integrator that fills gaps invents distance.
                self.get_logger().warn(
                    'joint state gap of {:.3f} s exceeds the {:.3f} s timeout; '
                    'the interval is skipped and the estimate has lost the '
                    'displacement across it'.format(dt_s, self.timeout_s),
                    throttle_duration_sec=self.throttle_s)
                self.last_sample = sample
                return

            # ---- through the two encoders ----
            # The drive encoder is incremental: quantise the ABSOLUTE angle at
            # both ends and difference the quantised values, so the residue
            # carries into the next cycle exactly as a count register does.
            drive_q_now = quantise(drive_now, self.drive_step_rad)
            drive_q_prev = quantise(drive_prev, self.drive_step_rad)
            d_wheel_rad = drive_q_now - drive_q_prev

            # The steer encoder is absolute, and its zero is out by the one
            # count no calibration can resolve. The vehicle reads the sum and
            # has no way to know the offset is there.
            steer_meas_rad = quantise(steer_now + self.steer_zero_offset_rad,
                                      self.steer_step_rad)

            # ---- tricycle kinematics ----
            tread_m = self.rolling_radius_m * d_wheel_rad
            s_axle_m = tread_m * math.cos(steer_meas_rad)
            d_yaw_rad = tread_m * math.sin(steer_meas_rad) / self.wheelbase_m

            yaw_prev = self.yaw_rad
            yaw_next = yaw_prev + d_yaw_rad

            if abs(d_yaw_rad) > _STRAIGHT_EPS_RAD:
                radius = s_axle_m / d_yaw_rad
                self.axle_x_m += radius * (math.sin(yaw_next) - math.sin(yaw_prev))
                self.axle_y_m += radius * (math.cos(yaw_prev) - math.cos(yaw_next))
            else:
                mid = yaw_prev + 0.5 * d_yaw_rad
                self.axle_x_m += s_axle_m * math.cos(mid)
                self.axle_y_m += s_axle_m * math.sin(mid)

            self.yaw_rad = math.atan2(math.sin(yaw_next), math.cos(yaw_next))

            self.vx_mps = s_axle_m / dt_s
            self.vyaw_rps = d_yaw_rad / dt_s
            self.vy_mps = self.base_ahead_of_axle_m * self.vyaw_rps

            self.last_sample = sample
            self.publish(t_now)

        def publish(self, t_s):
            """One nav_msgs/Odometry, pose of base_link, twist in the body frame."""
            msg = Odometry()
            msg.header.stamp.sec = int(t_s)
            msg.header.stamp.nanosec = int(round((t_s - int(t_s)) * 1e9))
            msg.header.frame_id = self.odom_frame
            msg.child_frame_id = self.base_frame

            # base_link is placed on the integrated rear axle pose here, in the
            # one place the offset is applied.
            msg.pose.pose.position.x = (
                self.axle_x_m + self.base_ahead_of_axle_m * math.cos(self.yaw_rad))
            msg.pose.pose.position.y = (
                self.axle_y_m + self.base_ahead_of_axle_m * math.sin(self.yaw_rad))
            msg.pose.pose.position.z = 0.0
            qx, qy, qz, qw = yaw_to_quaternion(self.yaw_rad)
            msg.pose.pose.orientation.x = qx
            msg.pose.pose.orientation.y = qy
            msg.pose.pose.orientation.z = qz
            msg.pose.pose.orientation.w = qw

            msg.twist.twist.linear.x = self.vx_mps
            msg.twist.twist.linear.y = self.vy_mps
            msg.twist.twist.angular.z = self.vyaw_rps

            # THE POSE COVARIANCE IS DELIBERATELY USELESS. Dead reckoning has
            # unbounded pose error and no fixed number describes it, so this
            # message says the pose is worth nothing and the EKF is configured
            # to fuse the twist only. The twist covariances are the derived
            # ones from config.yaml.
            pose_cov = [0.0] * 36
            for i in (0, 7, 14, 21, 28, 35):
                pose_cov[i] = self.var_pose_unused
            msg.pose.covariance = pose_cov

            twist_cov = [0.0] * 36
            twist_cov[0] = self.var_vx
            twist_cov[7] = self.var_vy
            twist_cov[14] = self.var_pose_unused
            twist_cov[21] = self.var_pose_unused
            twist_cov[28] = self.var_pose_unused
            twist_cov[35] = self.var_vyaw
            msg.twist.covariance = twist_cov

            self.pub_odom.publish(msg)

    return WheelOdometry


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Tricycle wheel odometry for one forklift. Publishes an '
                    'estimate and no transform.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    args, ros_argv = parser.parse_known_args(argv)

    cfg = load_config(args.config)

    # Imported here, not at module scope, so the arithmetic above can be
    # exercised on a machine with no ROS installed.
    import rclpy
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from sensor_msgs.msg import JointState
    from std_msgs.msg import Bool

    node_class = _make_node_class(Node, Odometry, QoSProfile, JointState, Bool)

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
