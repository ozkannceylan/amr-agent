#!/usr/bin/env python3
"""steer_bench.py - the steer axis, commanded against achieved, measured
on the plant with no controller anywhere in the loop.

WHY THIS EXISTS
  EVIDENCE_NAV2.md section 11.2 shows that steer commands below about two
  degrees produce almost no yaw, pooled over ten committed Nav2 runs. That
  measurement infers the achieved steer from the BODY's yaw rate, so it
  cannot say which of two things is happening:

      (a) the steer JOINT never reaches the commanded angle, or
      (b) the joint reaches it and the BODY does not yaw, which is tyre
          slip at the rear axle.

  The fix is different for each, so the two are separated here by reading
  the joint angle itself out of /forklift/joint_states while the same
  command is applied.

WHAT IT DRIVES, AND WHAT IT DELIBERATELY BYPASSES
  It publishes straight onto the model's own command inputs,

      /forklift/gz/steer_cmd      std_msgs/Float64  [rad]
      /forklift/gz/traction_cmd   std_msgs/Float64  [rad/s at the wheel]

  so neither cmd_vel_to_tricycle.py nor forklift_io.py nor the smoother
  nor Nav2 is in the loop. Anything this bench measures is the PLANT.

  It is a measurement harness. It is not a controller, it closes no loop,
  it reads no goal and it is never started by a launch file that
  navigates.

TWO PHASES, AND THE ORDER MATTERS
  1. STANDSTILL. Traction zero, the steer stepped through the same
     angles. model.sdf's own comment says a wheel steered while standing
     scrubs against the floor at roughly 400 N m, so this is the phase the
     integral clamp was sized for and the phase most likely to stick.
  2. ROLLING. Traction held at the bench speed, the steer stepped through
     the same angles with alternating sign so the vehicle stays inside the
     arena. This is the regime the Nav2 runs live in.

Usage (after sourcing /opt/ros/jazzy/setup.bash, with a simulator up):
  python3 agv/forklift/scripts/steer_bench.py --csv out.csv [--speed 0.6]
"""

import argparse
import csv
import math
import os
import sys

import rclpy
import yaml
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import QoSProfile
from sensor_msgs.msg import JointState
from std_msgs.msg import Float64

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))

#: The angles stepped, in degrees. Chosen to straddle the +-2 deg band
#: section 11.2 measured and to reach well past it on both sides, so the
#: curve has unity gain at each end and the band is bracketed rather than
#: assumed.
_ANGLES_DEG = [0.5, 1.0, 1.5, 2.0, 3.0, 5.0, 10.0, 20.0]

_STEER_JOINT = 'steer_joint'


def yaw_of(q):
    return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                      1.0 - 2.0 * (q.y * q.y + q.z * q.z))


def wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


class SteerBench(Node):
    """Steps the steer axis and records what the joint and the body did."""

    def __init__(self, cfg, speed_mps, hold_s, settle_frac, profile='sweep',
                 angles_deg=None, long_hold_s=20.0):
        super().__init__('steer_bench')
        self.profile = profile
        self.angles_deg = angles_deg or list(_ANGLES_DEG)
        self.long_hold_s = long_hold_s
        topics = cfg['topics']
        self.wheel_radius_m = cfg['model']['wheel_radius_m']
        self.hold_s = hold_s
        self.settle_frac = settle_frac
        self.speed_mps = speed_mps

        qos = QoSProfile(depth=cfg['qos']['depth'])
        self.pub_steer = self.create_publisher(
            Float64, topics['gz_steer_cmd'], qos)
        self.pub_traction = self.create_publisher(
            Float64, topics['gz_traction_cmd'], qos)

        # Callbacks are named cb_* so that none of them can shadow an
        # rclpy Node attribute (docs/LESSONS.md 2026-07-27).
        self.create_subscription(
            JointState, topics['joint_states'], self.cb_joint_states, qos)
        self.create_subscription(
            Odometry, topics['odom'], self.cb_odom, qos)

        self.joint_rad = None
        self.pose = None
        self.rows = []
        self.schedule = self._build_schedule()
        self.step_i = 0
        self.step_started = None
        self.done = False

        self.timer = self.create_timer(0.05, self.cb_tick)

    def _build_schedule(self):
        """(label, phase, steer_deg, tread_mps, hold_s).

        The rolling phase alternates sign so the vehicle tracks roughly
        along its start heading instead of spiralling into a wall; the
        deadband is symmetric under test, so alternating also probes both
        sides of it rather than one.
        """
        if self.profile == 'hold':
            # ONE step, held long enough to separate a slow arrival from a
            # refusal to arrive. A rate limit or a lag arrives late; a
            # torque threshold never arrives at all, and the only way to
            # tell them apart is to wait.
            sched = [('settle', 'standstill', 0.0, 0.0, 3.0)]
            for a in self.angles_deg:
                sched.append(('standhold+%.1f' % a, 'standstill', a, 0.0,
                              self.long_hold_s))
                sched.append(('standzero', 'standstill', 0.0, 0.0, 3.0))
            sched.append(('spinup', 'rolling', 0.0, self.speed_mps, 2.0))
            for a in self.angles_deg:
                sched.append(('rollhold+%.1f' % a, 'rolling', a,
                              self.speed_mps, self.long_hold_s))
            sched.append(('stop', 'standstill', 0.0, 0.0, 1.0))
            return sched

        sched = [('settle', 'standstill', 0.0, 0.0, 3.0)]
        for a in self.angles_deg:
            sched.append(('stand+%.1f' % a, 'standstill', a, 0.0, self.hold_s))
            sched.append(('stand-%.1f' % a, 'standstill', -a, 0.0, self.hold_s))
        sched.append(('recentre', 'standstill', 0.0, 0.0, 2.0))
        sched.append(('spinup', 'rolling', 0.0, self.speed_mps, 2.0))
        for a in self.angles_deg:
            sched.append(('roll+%.1f' % a, 'rolling', a, self.speed_mps,
                          self.hold_s))
            sched.append(('roll-%.1f' % a, 'rolling', -a, self.speed_mps,
                          self.hold_s))
        sched.append(('stop', 'standstill', 0.0, 0.0, 1.0))
        return sched

    def now_s(self):
        return self.get_clock().now().nanoseconds * 1e-9

    def cb_joint_states(self, msg):
        if _STEER_JOINT in msg.name:
            self.joint_rad = msg.position[msg.name.index(_STEER_JOINT)]

    def cb_odom(self, msg):
        p = msg.pose.pose
        self.pose = (p.position.x, p.position.y, yaw_of(p.orientation))

    def cb_tick(self):
        if self.done:
            return
        t = self.now_s()
        if self.step_started is None:
            if self.pose is None or self.joint_rad is None:
                return          # wait for both feeds before starting
            self.step_started = t
            self.get_logger().info(
                'steer_bench: %d steps, bench speed %.3f m/s, hold %.1f s'
                % (len(self.schedule), self.speed_mps, self.hold_s))

        label, phase, steer_deg, tread, hold = self.schedule[self.step_i]
        if t - self.step_started >= hold:
            self.step_i += 1
            self.step_started = t
            if self.step_i >= len(self.schedule):
                self.done = True
                self._stop()
                return
            label, phase, steer_deg, tread, hold = self.schedule[self.step_i]

        out = Float64()
        out.data = math.radians(steer_deg)
        self.pub_steer.publish(out)
        out = Float64()
        out.data = tread / self.wheel_radius_m
        self.pub_traction.publish(out)

        if self.pose is not None and self.joint_rad is not None:
            x, y, yaw = self.pose
            self.rows.append({
                't': '%.4f' % t, 'step': label, 'phase': phase,
                'cmd_deg': '%.4f' % steer_deg,
                'joint_deg': '%.4f' % math.degrees(self.joint_rad),
                'x': '%.6f' % x, 'y': '%.6f' % y,
                'yaw': '%.6f' % yaw,
                'elapsed': '%.3f' % (t - self.step_started)})

    def _stop(self):
        for _ in range(10):
            out = Float64()
            out.data = 0.0
            self.pub_traction.publish(out)
        self.get_logger().info('steer_bench: schedule complete')


def summarise(rows, wheelbase_m, settle_frac):
    """Per step: commanded angle, the JOINT's settled angle, and the angle
    the BODY's yaw rate implies. The three columns are the experiment."""
    by = {}
    for r in rows:
        by.setdefault((r['step'], r['phase']), []).append(r)

    out = []
    for (label, phase), rs in by.items():
        if label in ('settle', 'recentre', 'spinup', 'stop', 'standzero'):
            continue
        hold = float(rs[-1]['elapsed'])
        keep = [r for r in rs if float(r['elapsed']) >= settle_frac * hold]
        if len(keep) < 4:
            continue
        cmd = float(keep[0]['cmd_deg'])
        joint = sum(float(r['joint_deg']) for r in keep) / len(keep)

        body = float('nan')
        dt = float(keep[-1]['t']) - float(keep[0]['t'])
        dyaw = wrap(float(keep[-1]['yaw']) - float(keep[0]['yaw']))
        dx = float(keep[-1]['x']) - float(keep[0]['x'])
        dy = float(keep[-1]['y']) - float(keep[0]['y'])
        ds = math.hypot(dx, dy)
        speed = ds / dt if dt > 0 else 0.0
        # The achieved speed is carried into the table on purpose: a step
        # the vehicle was BLOCKED for must be visibly held rather than
        # silently scored as an arc (docs/LESSONS.md 2026-08-04).
        if dt > 0 and speed > 0.05:
            y0 = float(keep[0]['yaw'])
            f = 1.0 if dx * math.cos(y0) + dy * math.sin(y0) > 0 else -1.0
            v = ds / dt * f
            body = math.degrees(math.atan(wheelbase_m * (dyaw / dt) / v))
        out.append((phase, cmd, joint, body, speed, len(keep)))

    order = {'standstill': 0, 'rolling': 1}
    out.sort(key=lambda r: (order[r[0]], r[1]))
    return out


def print_summary(summary):
    print('')
    print('%-11s %9s %11s %11s %9s %9s %8s'
          % ('phase', 'cmd[deg]', 'JOINT[deg]', 'BODY[deg]',
             'joint/cmd', 'body/cmd', 'v[m/s]'))
    print('-' * 74)
    for phase, cmd, joint, body, speed, n in summary:
        jr = ('%.3f' % (joint / cmd)) if abs(cmd) > 1e-6 else '-'
        br = ('%.3f' % (body / cmd)) if abs(cmd) > 1e-6 and body == body \
            else '-'
        print('%-11s %9.3f %11.3f %11.3f %9s %9s %8.3f'
              % (phase, cmd, joint, body, jr, br, speed))
    print('')
    print('READING IT. joint/cmd near 1 with body/cmd near 0 puts the')
    print('deadband in the TYRE. joint/cmd near 0 puts it in the ACTUATOR.')
    print('Both near 1 means the deadband is not in the plant at all and')
    print('the search moves back up the chain.')


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(
        description='Steer axis commanded against achieved, on the plant.')
    ap.add_argument('--config', default=_DEFAULT_CONFIG)
    ap.add_argument('--csv', required=True)
    ap.add_argument('--speed', type=float, default=0.6,
                    help='bench tread speed [m/s] for the rolling phase')
    ap.add_argument('--hold', type=float, default=2.0,
                    help='seconds held at each step')
    ap.add_argument('--settle-frac', type=float, default=0.5,
                    help='fraction of each hold discarded as transient')
    ap.add_argument('--profile', default='sweep', choices=('sweep', 'hold'),
                    help='sweep: the whole static curve. hold: one angle '
                         'held long, which separates a slow arrival from a '
                         'refusal to arrive')
    ap.add_argument('--angles', default=None,
                    help='comma separated angles in degrees')
    ap.add_argument('--long-hold', type=float, default=20.0,
                    help='seconds per step in the hold profile')
    args, ros_argv = ap.parse_known_args(argv)

    with open(args.config, 'r', encoding='utf-8') as h:
        cfg = yaml.safe_load(h)

    rclpy.init(args=[sys.argv[0]] + ros_argv)
    angles = ([float(a) for a in args.angles.split(',')]
              if args.angles else None)
    node = SteerBench(cfg, args.speed, args.hold, args.settle_frac,
                      args.profile, angles, args.long_hold)
    node.set_parameters([rclpy.parameter.Parameter(
        'use_sim_time', rclpy.Parameter.Type.BOOL, True)])
    try:
        while rclpy.ok() and not node.done:
            rclpy.spin_once(node, timeout_sec=0.1)
    except KeyboardInterrupt:
        pass

    rows = node.rows
    wheelbase_m = cfg['model']['wheelbase_m']
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

    if rows:
        with open(args.csv, 'w', newline='', encoding='utf-8') as h:
            w = csv.DictWriter(h, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print('wrote %d samples to %s' % (len(rows), args.csv))
        print_summary(summarise(rows, wheelbase_m, args.settle_frac))
    else:
        print('NO SAMPLES: the bench never saw both /forklift/joint_states '
              'and the ground-truth odometry')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
