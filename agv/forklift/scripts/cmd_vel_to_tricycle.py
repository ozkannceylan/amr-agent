#!/usr/bin/env python3
"""cmd_vel_to_tricycle.py - the one place a body twist becomes a steer
angle and a drive-wheel speed.

WHAT THIS NODE IS
  A kinematic converter, and nothing else.

      /cmd_vel_smoothed  geometry_msgs/Twist   (v = linear.x [m/s],
                                                w = angular.z [rad/s],
                                                expressed at base_link)
          ->  /forklift/cmd/steer_angle     std_msgs/Float64  [rad]
          ->  /forklift/cmd/traction_speed  std_msgs/Float64  [m/s of
                                                               DRIVE-WHEEL
                                                               TREAD]

  It holds no path, no pose, no goal and no error signal. It closes no
  loop. Give it the same twist twice and it emits the same pair twice.

WHAT THIS NODE IS NOT
  It is not a controller: it corrects nothing, because it measures
  nothing.
  It is not the envelope gate. m5-11 owns that, it sits between the
  smoother and this node (ADR 0014 seam (b): "below the smoother"), and
  its insertion needs no edit here - the input topic is an argument.
  It is not a safety function. Nothing here inhibits motion, latches a
  fault or performs a stop; a refused command is a command not issued.
  The protective stop, the e-stop chain and safe torque off are onboard
  and hardwired and no message on any of these topics can trigger or
  release one (invariant 1).
  It is not real time. The physical loop closes in the joint controllers,
  so a late callback here costs smoothness and nothing else
  (invariant 9).

============================ THE GEOMETRY ============================

The vehicle (agv/forklift/model.sdf): ONE steered, driven wheel LEADING at
x = +0.55, TWO passive wheels TRAILING on an axle at x = -0.50. So

    L  = wheelbase                     = 0.55 - (-0.50) = 1.05 m
    d  = base_link ahead of rear axle  = 0.50 m
    r  = drive wheel radius            = 0.12 m
    delta_max = steer stop             = 1.31 rad (75.06 deg)

THE ONE FACT THAT MAKES THE ALGEBRA EASY, AND IT IS NOT AN APPROXIMATION.
The rear axle midpoint R is the only point of a tricycle whose velocity is
purely longitudinal, because the two passive wheels cannot slide sideways.
base_link B stands a distance d FORWARD of R, purely along +x. For a rigid
body,

    v_B = v_R + omega x (B - R),   with (B - R) = (d, 0, 0)
        = (v_R, 0, 0) + (0, d*omega, 0)

so the x components of v_B and v_R are IDENTICAL and only a lateral term
appears. Therefore

    v  ==  linear.x at base_link  ==  the rear axle's longitudinal speed
    w  ==  angular.z              ==  the body yaw rate, the same at every
                                      point of a rigid body

and the d = 0.50 m offset drops out of the conversion entirely. It does
NOT drop out of odometry, where it is the reason scripts/wheel_odometry.py
places base_link on the rear axle pose rather than integrating base_link
directly.

THE BICYCLE RELATION. The instantaneous centre of rotation lies on the
line of the rear axle. Writing the steer angle delta,

    w = v * tan(delta) / L                                            (1)

and the driven wheel, being steered by delta, rolls along its own heading
at

    v_D = v / cos(delta)                                              (2)

THE CONVERSION, WHICH IS (1) AND (2) SOLVED FOR THE TWO ACTUATORS:

    delta = atan( L * w / v )         = atan2(L*w*sign(v), |v|)       (3)
    v_D   = v / cos(delta)                                            (4)

(3) is written as an atan2 of (L*w*sign(v), |v|) so that it returns a
value in (-pi/2, +pi/2) with the correct sign and never divides by v.
It is correct in REVERSE without a second case: substituting (1) into (3)
gives atan(tan(delta)) = delta for v of either sign. Driving backwards
with the wheel steered to port yields w < 0, which is the vehicle yawing
the other way - which is what a vehicle reversing on lock actually does.

/forklift/cmd/traction_speed CARRIES v_D AND NOT v, and that is a contract
this node did not invent: scripts/forklift_io.py publishes
`speed / wheel_radius` onto the gz joint command, so the number it is
given IS the wheel's tread speed. The same convention is what
scripts/wheel_odometry.py inverts. Feeding it v instead would under-drive
every turn by cos(delta) - 3.6 % at 15 deg, 29 % at the tightest arc the
planner may emit.

=================== THE TWO PLACES THE GEOMETRY STOPS ===================

1. THE STEER STOP. If |delta| from (3) exceeds delta_max the pair (v, w)
   is not executable. The angle is clamped, and clamping the angle DOES
   NOT preserve the requested curvature - the vehicle turns less sharply
   than asked. That is a real deviation, so it is COUNTED and logged
   rather than absorbed. With nav2.yaml's minimum turning radius of
   1.05 m the PLANNER never asks for more than 45 deg, so a clamp is
   never the plan. It is the CONTROLLER correcting hard, and it was
   measured: on the goal approach, where RPP is inside the tolerance
   circle and cannot rotate in place, it demanded the full 75.06 deg stop
   (EVIDENCE_NAV2.md section 5.1). So a clamp is expected at the end of a
   goal and unexpected in mid-aisle, and it is logged either way.

2. THE TRACTION LIMIT. v_D from (4) may exceed the vehicle's traction
   limit even when v does not, because 1/cos(delta) grows without bound.
   Clamping v_D IS curvature preserving, and that is worth stating
   because it is not obvious: from (1) and (2),
   w = v_D * sin(delta) / L and v = v_D * cos(delta), so scaling v_D with
   delta held scales v and w TOGETHER and the arc is unchanged. The
   vehicle simply drives the same path more slowly. So this clamp is
   applied silently by design, while the one above is not.

======================= ROTATION IN PLACE IS REFUSED =======================

Below `navigation.creep_speed_mps` the ratio w/v is not a curvature the
controller meant. If the yaw rate is nonetheless above
`navigation.yawrate_refusal_radps`, the request is an in-place rotation:
one steered wheel standing a wheelbase ahead of the rear axle cannot turn
the body without travelling, so there is NO (delta, v_D) that produces it.

The node then publishes zero traction and HOLDS the steer axis where it
is. It does not:
  - fabricate a wheel speed, because that would be driving a vehicle
    somewhere nobody asked it to go;
  - swing the steer to full lock "in the direction of the request",
    because a vehicle that visibly responds to an impossible command is
    a vehicle whose logs lie;
  - re-centre the steer, because re-centring is itself a motion command
    the caller did not issue, and it is the wrong pre-position for the
    cusp that usually follows.

A REFUSAL IS COUNTED ONLY AT A STANDSTILL, below
`navigation.zero_speed_mps`. Between that and the creep deadband the
request is executable and the converter simply declines to act on a
curvature it cannot resolve; that is reported at INFO and is not a
refusal. See `_below_creep`.

The refusal is COUNTED and reported on
/forklift/nav/tricycle_refusals (std_msgs/UInt32, monotonic). A nonzero
count means something upstream is commanding a differential base - which
is why agv/forklift/behavior_trees/navigate_to_pose_tricycle.xml removes
nav2's Spin recovery, and why this counter is the check that it stayed
removed.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 agv/forklift/scripts/cmd_vel_to_tricycle.py \
      [--config PATH] [--cmd-topic /cmd_vel_smoothed] [--ros-args ...]
"""

import argparse
import math
import os
import sys

import rclpy
import yaml
from geometry_msgs.msg import Twist
from rclpy.node import Node
from rclpy.qos import QoSProfile
from std_msgs.msg import Float64, UInt32

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))

#: The refusal counter's topic. It is a diagnostic of THIS node and is not
#: a vehicle state, so it is named here rather than in config.yaml's
#: `topics:` contract table.
_REFUSAL_TOPIC = '/forklift/nav/tricycle_refusals'


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def twist_to_tricycle(v, w, wheelbase_m, steer_limit_rad, traction_max_mps):
    """The whole conversion, as a pure function of the geometry.

    Returns (steer_rad, drive_speed_mps, steer_clamped, traction_clamped).

    Kept free of ROS and of node state on purpose: it is the one piece of
    this file that is a claim about the vehicle rather than about plumbing,
    and a claim should be checkable without a simulator. `--self-check`
    exercises it against the forward model.
    """
    # (3), written so nothing divides by v.
    numerator = wheelbase_m * w * (1.0 if v >= 0.0 else -1.0)
    steer = math.atan2(numerator, abs(v))

    steer_clamped = False
    if steer > steer_limit_rad:
        steer, steer_clamped = steer_limit_rad, True
    elif steer < -steer_limit_rad:
        steer, steer_clamped = -steer_limit_rad, True

    # (4). cos(delta) cannot be zero: steer_limit_rad < pi/2 by
    # construction (1.31 < 1.5708) and the clamp above has already been
    # applied.
    drive = v / math.cos(steer)

    traction_clamped = False
    if drive > traction_max_mps:
        drive, traction_clamped = traction_max_mps, True
    elif drive < -traction_max_mps:
        drive, traction_clamped = -traction_max_mps, True

    return steer, drive, steer_clamped, traction_clamped


def tricycle_to_twist(steer_rad, drive_speed_mps, wheelbase_m):
    """The FORWARD model, (1) and (2) read the other way.

    v = v_D cos(delta),  w = v_D sin(delta) / L.

    It exists so that the conversion can be checked by round trip instead
    of by inspection, which is what `--self-check` does. It is the same
    relation scripts/wheel_odometry.py integrates, stated here
    independently rather than imported, because a round trip through one
    author's algebra proves nothing.
    """
    v = drive_speed_mps * math.cos(steer_rad)
    w = drive_speed_mps * math.sin(steer_rad) / wheelbase_m
    return v, w


class CmdVelToTricycle(Node):
    """geometry_msgs/Twist -> (steer angle, drive-wheel speed)."""

    def __init__(self, cfg, cmd_topic):
        super().__init__('cmd_vel_to_tricycle')
        self.cfg = cfg

        model = cfg['model']
        limits = cfg['limits']
        nav = cfg['navigation']
        topics = cfg['topics']

        self.wheelbase_m = model['wheelbase_m']
        self.steer_limit_rad = model['steer_limit_rad']
        self.traction_max_mps = limits['traction_speed_max_mps']
        self.creep_speed_mps = nav['creep_speed_mps']
        self.zero_speed_mps = nav['zero_speed_mps']
        self.yawrate_refusal_radps = nav['yawrate_refusal_radps']
        self.throttle_s = cfg['logging']['throttle_s']

        qos = QoSProfile(depth=cfg['qos']['depth'])

        self.pub_steer = self.create_publisher(
            Float64, topics['cmd_steer_angle'], qos)
        self.pub_traction = self.create_publisher(
            Float64, topics['cmd_traction_speed'], qos)
        self.pub_refusals = self.create_publisher(UInt32, _REFUSAL_TOPIC, qos)

        self.sub_cmd_vel = self.create_subscription(
            Twist, cmd_topic, self.cb_cmd_vel, qos)

        # The steer angle last COMMANDED, which is what a below-creep
        # request holds. Seeded to None, not to zero: until something has
        # been commanded, the axis is wherever the simulator left it and
        # publishing a zero would be this node moving the wheel on
        # startup.
        self.last_steer_rad = None

        self.refusals = 0
        self.steer_clamps = 0
        self.traction_clamps = 0

        self.get_logger().info(
            'cmd_vel_to_tricycle up: {} -> ({}, {}); L = {:.3f} m, '
            'steer stop +-{:.4f} rad ({:.2f} deg), traction limit '
            '{:.2f} m/s, creep deadband {:.3f} m/s'.format(
                cmd_topic, topics['cmd_steer_angle'],
                topics['cmd_traction_speed'], self.wheelbase_m,
                self.steer_limit_rad, math.degrees(self.steer_limit_rad),
                self.traction_max_mps, self.creep_speed_mps))

    # ------------------------------------------------------------------ #
    # Callbacks are named cb_* so that none of them can shadow an rclpy
    # Node attribute (docs/LESSONS.md 2026-07-27).
    # ------------------------------------------------------------------ #

    def cb_cmd_vel(self, msg):
        v = msg.linear.x
        w = msg.angular.z

        if not (math.isfinite(v) and math.isfinite(w)):
            self.get_logger().warn(
                'cmd_vel is not finite (v={}, w={}), ignored'.format(v, w))
            return

        # A lateral request is meaningless on a vehicle with no lateral
        # degree of freedom. It is reported, not silently dropped: it means
        # something upstream believes this base is holonomic.
        if abs(msg.linear.y) > 0.0:
            self.get_logger().warn(
                'cmd_vel carries linear.y = {:+.4f} m/s; this vehicle has '
                'no lateral degree of freedom and the term is discarded'
                .format(msg.linear.y),
                throttle_duration_sec=self.throttle_s)

        if abs(v) < self.creep_speed_mps:
            self._below_creep(v, w)
            return

        steer, drive, steer_clamped, traction_clamped = twist_to_tricycle(
            v, w, self.wheelbase_m, self.steer_limit_rad,
            self.traction_max_mps)

        if steer_clamped:
            self.steer_clamps += 1
            # Not curvature preserving: say so, with both curvatures.
            self.get_logger().warn(
                'steer clamped to {:+.4f} rad; requested v={:+.3f} m/s '
                'w={:+.4f} rad/s implies curvature {:+.3f} 1/m and the '
                'clamp delivers {:+.3f} 1/m'.format(
                    steer, v, w, w / v if v != 0.0 else float('nan'),
                    math.tan(steer) / self.wheelbase_m),
                throttle_duration_sec=self.throttle_s)
        if traction_clamped:
            # Curvature preserving, so this is information and not a
            # warning: the vehicle drives the same arc more slowly.
            self.traction_clamps += 1
            self.get_logger().info(
                'drive-wheel speed clamped to {:+.3f} m/s; the arc is '
                'unchanged and the vehicle drives it slower'.format(drive),
                throttle_duration_sec=self.throttle_s)

        self.last_steer_rad = steer
        self._publish(steer, drive)

    def _below_creep(self, v, w):
        """|v| is under the creep deadband: the requested curvature is not
        a number the controller meant.

        WHAT COUNTS AS A REFUSAL, AND WHY IT IS NARROWER THAN THIS BAND.
        A refusal means the request has NO (delta, v_D) at all, which is
        true only when the vehicle is asked to turn while STOPPED. A
        request of v = 0.004 m/s with w = 0.003 rad/s is a 1.29 m radius
        at a crawl - perfectly executable - and the converter declines it
        only because it is 2 mm/s from a standstill and the ratio is
        noise. Counting that as a refusal made the counter useless: the
        first measured run reported 27 "rotation in place" refusals for a
        goal that was reached, every one of them the tail of a
        deceleration through this band. The counter exists to prove that
        nothing upstream is commanding a differential base (nav2's Spin
        sends v = 0 exactly), so it counts only requests at a standstill.
        """
        if abs(v) <= self.zero_speed_mps and \
                abs(w) > self.yawrate_refusal_radps:
            self.refusals += 1
            self.get_logger().warn(
                'ROTATION IN PLACE REFUSED: v={:+.4f} m/s (at a standstill, '
                'under {:.4f} m/s) with w={:+.4f} rad/s. A tricycle cannot '
                'turn its body without its drive wheel travelling; '
                'commanding zero traction and holding the steer axis. '
                'refusals={}'.format(
                    v, self.zero_speed_mps, w, self.refusals),
                throttle_duration_sec=self.throttle_s)
        elif abs(w) > self.yawrate_refusal_radps:
            self.get_logger().info(
                'below the {:.3f} m/s creep deadband at v={:+.4f} m/s with '
                'w={:+.4f} rad/s: holding the steer axis and stopping. This '
                'is NOT a refusal - the request was executable and the '
                'vehicle was {:.0f} mm/s from rest.'.format(
                    self.creep_speed_mps, v, w, 1000 * abs(v)),
                throttle_duration_sec=self.throttle_s)

        # Zero traction either way. The steer is held, not re-centred: see
        # the module docstring.
        steer = self.last_steer_rad
        if steer is None:
            # Nothing has been commanded yet, so there is no held angle to
            # publish and publishing one would be this node moving the
            # wheel. Emit the stop only.
            out = Float64()
            out.data = 0.0
            self.pub_traction.publish(out)
            self._publish_refusals()
            return
        self._publish(steer, 0.0)

    def _publish(self, steer_rad, drive_mps):
        steer_msg = Float64()
        steer_msg.data = float(steer_rad)
        self.pub_steer.publish(steer_msg)

        drive_msg = Float64()
        drive_msg.data = float(drive_mps)
        self.pub_traction.publish(drive_msg)

        self._publish_refusals()

    def _publish_refusals(self):
        msg = UInt32()
        msg.data = self.refusals
        self.pub_refusals.publish(msg)


# --------------------------------------------------------------------------- #
# --self-check: the conversion against the forward model, no ROS, no simulator
# --------------------------------------------------------------------------- #

def self_check(cfg):
    """Round-trip every case that matters and print the table.

    THE CHECK IS A ROUND TRIP, NOT AN ASSERTION ABOUT ONE NUMBER: for each
    (v, w) the conversion produces (delta, v_D), and the independently
    written forward model turns (delta, v_D) back into (v', w'). If the
    algebra is right, v' == v and w' == w to floating point wherever no
    limit was hit, and the table says exactly where a limit was hit and
    which of the two survived it.
    """
    L = cfg['model']['wheelbase_m']
    dmax = cfg['model']['steer_limit_rad']
    vmax = cfg['limits']['traction_speed_max_mps']

    cases = [
        ('straight ahead', 0.60, 0.0),
        ('straight astern', -0.60, 0.0),
        ('R = 1.05 m left, the planner\'s tightest arc', 0.60, 0.60 / 1.05),
        ('R = 1.05 m right', 0.60, -0.60 / 1.05),
        ('R = 1.05 m left, IN REVERSE', -0.60, -0.60 / 1.05),
        ('R = 2.10 m left', 0.60, 0.60 / 2.10),
        ('R = 5.00 m right, a gentle aisle correction', 0.60, -0.60 / 5.00),
        ('mechanical limit, R = 0.280 m', 0.60, 0.60 / 0.2802),
        ('BEYOND the steer stop, R = 0.20 m', 0.60, 0.60 / 0.20),
        ('creep, R = 1.05 m', 0.05, 0.05 / 1.05),
        ('fast + tight: drive speed above the traction limit',
         1.40, 1.40 / 1.05),
    ]

    print('Twist -> tricycle, checked by round trip through an '
          'independently written forward model')
    print('L = {:.4f} m   steer stop +-{:.4f} rad ({:.3f} deg)   '
          'traction limit {:.2f} m/s'.format(
              L, dmax, math.degrees(dmax), vmax))
    print('')
    header = ('{:<44} {:>8} {:>9} | {:>9} {:>8} | {:>9} {:>9} | {}'
              .format('case', 'v[m/s]', 'w[rad/s]', 'delta[deg]', 'vD[m/s]',
                      "v'[m/s]", "w'[rad/s]", 'limit'))
    print(header)
    print('-' * len(header))

    worst = 0.0
    for label, v, w in cases:
        steer, drive, sc, tc = twist_to_tricycle(v, w, L, dmax, vmax)
        vb, wb = tricycle_to_twist(steer, drive, L)
        limit = []
        if sc:
            limit.append('STEER CLAMPED')
        if tc:
            limit.append('drive clamped')
        note = ', '.join(limit) if limit else 'none'
        print('{:<44} {:>8.3f} {:>9.4f} | {:>9.3f} {:>8.3f} | '
              '{:>9.4f} {:>9.4f} | {}'.format(
                  label, v, w, math.degrees(steer), drive, vb, wb, note))
        if not (sc or tc):
            worst = max(worst, abs(vb - v), abs(wb - w))

    print('')
    print('largest round-trip residual over the UNLIMITED cases: '
          '{:.3e}'.format(worst))
    print('')
    print('The two limits, read from the table:')
    print('  STEER CLAMPED is NOT curvature preserving - compare the')
    print("    requested w against w' on that row.")
    print('  drive clamped IS curvature preserving - v and w both fall by')
    print("    the same factor, so w'/v' still equals w/v.")
    ok = worst < 1e-12
    print('')
    print('VERDICT: {}'.format(
        'round trip exact to {:.1e}'.format(worst) if ok
        else 'round trip residual {:.3e} - THE ALGEBRA IS WRONG'.format(worst)))
    return 0 if ok else 1


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        description='Body twist to tricycle steer angle and drive speed.')
    parser.add_argument('--config', default=_DEFAULT_CONFIG,
                        help='named-constant file (default: %(default)s)')
    parser.add_argument('--cmd-topic', default=None,
                        help='input Twist topic (default: config.yaml '
                             'topics.cmd_vel_smoothed). The envelope gate '
                             'of m5-11 is inserted by pointing this at its '
                             'output instead.')
    parser.add_argument('--self-check', action='store_true',
                        help='round-trip the conversion against the forward '
                             'model and exit. No ROS, no simulator.')
    args, ros_argv = parser.parse_known_args(argv)

    cfg = load_config(args.config)

    if args.self_check:
        return self_check(cfg)

    cmd_topic = args.cmd_topic or cfg['topics']['cmd_vel_smoothed']

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    node = CmdVelToTricycle(cfg, cmd_topic)
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.get_logger().info(
            'cmd_vel_to_tricycle down: {} rotation-in-place refusals, '
            '{} steer clamps, {} drive-speed clamps'.format(
                node.refusals, node.steer_clamps, node.traction_clamps))
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
