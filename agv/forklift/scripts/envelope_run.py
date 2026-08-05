#!/usr/bin/env python3
"""envelope_run.py - the measurement harness for the envelope gate, and
the ROS 2 topic double that stands in for the PLC.

WHAT IT DOES
  `run`      plays one scripted scenario: it publishes the envelope at
             20 Hz as the bridge would, publishes a known command into
             the velocity smoother, records what every stage of the chain
             did, and prints the measurement the scenario exists for.
  `analyse`  re-scores a recording without re-running it.

WHAT IT IS NOT. It is not part of the vehicle. It is an INSTRUMENT: it
publishes no transform, plans nothing and corrects nothing, and the only
thing in this stack allowed to read ground truth is this file, exactly as
nav2_run.py records for the Nav2 measurements.

IT IS NOT AN OPC UA CLIENT AND IT IS NOT THE BRIDGE. No PLC is connected
at M5. This file publishes the six section 12.10 topics directly, which
is what the brief means by "a ROS 2 topic double": the shape of the
envelope on the vehicle's side of the bridge, with none of the bridge's
transport. What it therefore does NOT measure is the envelope's real age
on arrival - that measurement needs the bridge and is ADR 0014's own open
item.

THE DOUBLE IS NOT A MODEL OF THE PLC EITHER. It contains no formation
logic, no interlock and no latch. It publishes the values a scenario
tells it to publish, and the one interesting thing it can do is STOP
PUBLISHING, which is the failure the freshness window exists for.

===================== WHAT EACH SCENARIO MEASURES =====================

  enable-drop   observation 1: enable drops while the vehicle is moving
  stale         observation 2: the double stops publishing - link dead,
                not a commanded stop
  clamp         observation 3: commanded against emitted at four ceilings
  release       observation 4: the gate opens under a smoother that has
                been ramping while the vehicle was held at zero. Run
                twice, OPEN_LOOP and CLOSED_LOOP, everything else equal
  passthrough   observation 5: the residual the gate adds when it is
                doing nothing
  permit-drop   observation 6: the fixed-equipment / station permit
  mode          the readback of ADR 0014 D5.3, and the release of the
                actuator topics to the teleop path

THREE RECORDINGS PER RUN, and they are separate files on purpose. Two of
the six observations are LATENCIES between two messages, and a 50 Hz
sample of a state variable cannot measure a latency finer than its own
period:

  <csv>            50 Hz sampled state, for distances and profiles
  <csv>.gate.csv   EVERY /cmd_vel_gated message, at arrival
  <csv>.pub.csv    EVERY envelope publication this double made
  <csv>.sm.csv     EVERY /cmd_vel_smoothed message, at arrival

EVERY FIGURE THIS FILE PRINTS COMES WITH ITS n. A figure from a single
instance of an event is printed as an observation with n = 1 and never as
a bound (docs/LESSONS.md 2026-08-04).

Usage (after sourcing /opt/ros/jazzy/setup.bash), against a running
warehouse bringup and envelope.launch.py:

  python3 agv/forklift/scripts/envelope_run.py run \\
      --scenario enable-drop --csv /tmp/enable-drop.csv
  python3 agv/forklift/scripts/envelope_run.py analyse \\
      --scenario enable-drop --csv /tmp/enable-drop.csv
"""

import argparse
import csv
import math
import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))

_STATE_TOPIC = '/forklift/envelope/gate_state'

_RUN_FIELDS = [
    't_sim',
    'gt_x', 'gt_y', 'gt_yaw', 'gt_v',      # GROUND TRUTH, the instrument's
    'est_v',                                # the EKF's estimate
    'cmd_v', 'cmd_w',                       # what this harness commanded
    'sm_v', 'sm_w',                         # /cmd_vel_smoothed
    'gate_v', 'gate_w', 'gate_age',         # /cmd_vel_gated and its age
    'traction', 'steer',                    # /forklift/cmd/*
    'env_enable', 'env_ceiling', 'env_permit', 'env_mode',  # what we publish
    'env_publishing',                       # 1 while the double publishes
    'mode_applied', 'heartbeat', 'gate_state',
]


def load_config(path):
    import yaml
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


# --------------------------------------------------------------------------- #
# the scenarios: a timeline of (t_rel_s, action, argument)
#
# `cmd` sets the commanded twist, `enable`/`ceiling`/`permit`/`mode` set an
# envelope element, `publish` switches the double on or off, `end` stops.
# --------------------------------------------------------------------------- #

def scenario_table(name, args):
    drive = args.speed
    settle = 2.0

    if name == 'enable-drop':
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', args.ceiling),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', (drive, 0.0)),
            (10.0, 'enable', False),
            (16.0, 'end', None),
        ]
    if name == 'permit-drop':
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', args.ceiling),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', (drive, 0.0)),
            (10.0, 'permit', False),
            (16.0, 'end', None),
        ]
    if name == 'stale':
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', args.ceiling),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', (drive, 0.0)),
            (10.0, 'publish', False),
            (16.0, 'end', None),
        ]
    if name == 'supervise':
        # THE DEPLOYED CHAIN, not this harness's command. Nav2's own
        # controller_server publishes /cmd_vel; this file publishes the
        # ENVELOPE ONLY and records. Used with a goal sent by
        # scripts/nav2_run.py.
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', args.ceiling),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (args.drop_at, 'enable', False),
            (args.duration, 'end', None),
        ]
    if name == 'clamp':
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', 0.60),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', (0.60, 0.0)),
            (5.0, 'ceiling', 0.40),
            (8.0, 'ceiling', 0.20),
            (11.0, 'ceiling', 0.10),
            (14.0, 'end', None),
        ]
    if name == 'release':
        # The gate is CLOSED from the start and the controller commands a
        # cruise into it: the smoother is left ramping against a vehicle
        # that is not moving. The release at t = 10 is the event.
        return [
            (0.0, 'enable', False), (0.0, 'ceiling', args.ceiling),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', (drive, 0.0)),
            (10.0, 'enable', True),
            (16.0, 'end', None),
        ]
    if name == 'passthrough':
        # A command that is always well under the ceiling, and never
        # constant, so a gate that quietly rounded or delayed would show.
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', 1.00),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', 'profile'),
            (14.0, 'end', None),
        ]
    if name == 'mode':
        return [
            (0.0, 'enable', True), (0.0, 'ceiling', args.ceiling),
            (0.0, 'permit', True), (0.0, 'mode', 2),
            (settle, 'cmd', (drive, 0.0)),
            (8.0, 'mode', 1),
            (12.0, 'mode', 2),
            (18.0, 'end', None),
        ]
    raise SystemExit('unknown scenario: {}'.format(name))


# --------------------------------------------------------------------------- #
# the node
# --------------------------------------------------------------------------- #

def cmd_run(args):
    import rclpy
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Bool, Float64, UInt16

    cfg = load_config(args.config)
    topics = cfg['topics']
    timeline = scenario_table(args.scenario, args)

    class EnvelopeRun(Node):

        def __init__(self):
            super().__init__('envelope_run')
            qos = QoSProfile(depth=cfg['qos']['depth'])

            self.pub_enable = self.create_publisher(
                Bool, topics['envelope_motion_enable'], qos)
            self.pub_ceiling = self.create_publisher(
                Float64, topics['envelope_speed_ceiling'], qos)
            self.pub_permit = self.create_publisher(
                Bool, topics['envelope_equipment_permit'], qos)
            self.pub_mode = self.create_publisher(
                UInt16, topics['mode_in_force'], qos)
            self.pub_cmd = self.create_publisher(Twist, args.cmd_topic, qos)

            self.create_subscription(Odometry, topics['odom'],
                                     self.cb_ground_truth, qos)
            self.create_subscription(Odometry, topics['odom_filtered'],
                                     self.cb_odom_filtered, qos)
            self.create_subscription(Twist, topics['cmd_vel_smoothed'],
                                     self.cb_smoothed, qos)
            self.create_subscription(Twist, topics['cmd_vel_gated'],
                                     self.cb_gated, qos)
            self.create_subscription(Float64, topics['cmd_traction_speed'],
                                     self.cb_traction, qos)
            self.create_subscription(Float64, topics['cmd_steer_angle'],
                                     self.cb_steer, qos)
            self.create_subscription(UInt16, topics['mode_applied'],
                                     self.cb_mode_applied, qos)
            self.create_subscription(UInt16, topics['vehicle_heartbeat'],
                                     self.cb_heartbeat, qos)
            self.create_subscription(UInt16, _STATE_TOPIC,
                                     self.cb_gate_state, qos)

            self.t0 = None
            self.finished = False

            self.env = {'enable': False, 'ceiling': 0.0,
                        'permit': False, 'mode': 0}
            self.publishing = True
            self.cmd = (0.0, 0.0)
            self.cmd_profile = False

            self.gt = (0.0, 0.0, 0.0, 0.0)
            self.est_v = 0.0
            self.sm = (0.0, 0.0)
            self.gate = (0.0, 0.0)
            self.t_gate = None
            self.traction = 0.0
            self.steer = 0.0
            self.mode_applied = -1
            self.heartbeat = -1
            self.gate_state = -1

            self.rows = []
            self.gate_rows = []
            self.pub_rows = []
            self.sm_rows = []
            self.pending = list(timeline)

            self.create_timer(1.0 / cfg['envelope']['publish_hz'],
                              self.cb_publish_cycle)
            self.create_timer(0.02, self.cb_record_cycle)

        # -- callbacks, cb_* (docs/LESSONS.md 2026-07-27) --------------- #

        def _t(self):
            now = self.get_clock().now().nanoseconds * 1e-9
            if self.t0 is None:
                self.t0 = now
            return now - self.t0

        def cb_ground_truth(self, msg):
            p = msg.pose.pose
            yaw = math.atan2(
                2.0 * (p.orientation.w * p.orientation.z),
                1.0 - 2.0 * (p.orientation.z ** 2))
            self.gt = (p.position.x, p.position.y, yaw,
                       msg.twist.twist.linear.x)

        def cb_odom_filtered(self, msg):
            self.est_v = msg.twist.twist.linear.x

        def cb_smoothed(self, msg):
            self.sm = (msg.linear.x, msg.angular.z)
            self.sm_rows.append((self._t(), msg.linear.x, msg.angular.z))

        def cb_gated(self, msg):
            self.gate = (msg.linear.x, msg.angular.z)
            t = self._t()
            self.t_gate = t
            self.gate_rows.append((t, msg.linear.x, msg.angular.z))

        def cb_traction(self, msg):
            self.traction = msg.data

        def cb_steer(self, msg):
            self.steer = msg.data

        def cb_mode_applied(self, msg):
            self.mode_applied = msg.data

        def cb_heartbeat(self, msg):
            self.heartbeat = msg.data

        def cb_gate_state(self, msg):
            self.gate_state = msg.data

        # -- the double, and the scripted command ---------------------- #

        def cb_publish_cycle(self):
            t = self._t()
            self._advance(t)
            if self.finished:
                return

            if args.scenario == 'supervise':
                # Nav2 owns /cmd_vel in this scenario. Publishing one here
                # would be a second writer of the same datum.
                self._publish_envelope(t)
                return

            v, w = self.cmd
            if self.cmd_profile:
                # Never constant, always inside the ceiling: a gate that
                # rounded, held or delayed would show up as a residual.
                v = 0.20 + 0.06 * math.sin(2.0 * math.pi * t / 5.0)
                w = 0.05 * math.sin(2.0 * math.pi * t / 3.0)
            msg = Twist()
            msg.linear.x = float(v)
            msg.angular.z = float(w)
            self.pub_cmd.publish(msg)
            self.cmd = (v, w) if not self.cmd_profile else (v, w)
            self._publish_envelope(t)

        def _publish_envelope(self, t):
            if not self.publishing:
                return
            b = Bool()
            b.data = bool(self.env['enable'])
            self.pub_enable.publish(b)
            f = Float64()
            f.data = float(self.env['ceiling'])
            self.pub_ceiling.publish(f)
            p = Bool()
            p.data = bool(self.env['permit'])
            self.pub_permit.publish(p)
            m = UInt16()
            m.data = int(self.env['mode'])
            self.pub_mode.publish(m)
            self.pub_rows.append((t, int(self.env['enable']),
                                  float(self.env['ceiling']),
                                  int(self.env['permit']),
                                  int(self.env['mode'])))

        def _advance(self, t):
            while self.pending and self.pending[0][0] <= t:
                _, action, value = self.pending.pop(0)
                if action == 'end':
                    self.finished = True
                    return
                if action == 'cmd':
                    if value == 'profile':
                        self.cmd_profile = True
                    else:
                        self.cmd = value
                elif action == 'publish':
                    self.publishing = bool(value)
                    self.get_logger().warn(
                        'DOUBLE STOPPED PUBLISHING at t = {:.3f} s. The '
                        'link is dead; nothing commanded a stop.'.format(t))
                else:
                    self.env[action] = value
                    self.get_logger().info(
                        'envelope: {} := {} at t = {:.3f} s'.format(
                            action, value, t))

        def cb_record_cycle(self):
            t = self._t()
            if self.finished:
                return
            gate_age = -1.0 if self.t_gate is None else (t - self.t_gate)
            self.rows.append([
                round(t, 4),
                self.gt[0], self.gt[1], self.gt[2], self.gt[3],
                self.est_v,
                self.cmd[0], self.cmd[1],
                self.sm[0], self.sm[1],
                self.gate[0], self.gate[1], round(gate_age, 4),
                self.traction, self.steer,
                int(self.env['enable']), float(self.env['ceiling']),
                int(self.env['permit']), int(self.env['mode']),
                int(self.publishing),
                self.mode_applied, self.heartbeat, self.gate_state,
            ])

    rclpy.init(args=[sys.argv[0]])
    node = EnvelopeRun()
    try:
        while rclpy.ok() and not node.finished:
            rclpy.spin_once(node, timeout_sec=0.05)
    except KeyboardInterrupt:
        pass

    _write(args.csv, _RUN_FIELDS, node.rows)
    _write(args.csv + '.gate.csv', ['t', 'v', 'w'], node.gate_rows)
    _write(args.csv + '.pub.csv',
           ['t', 'enable', 'ceiling', 'permit', 'mode'], node.pub_rows)
    _write(args.csv + '.sm.csv', ['t', 'v', 'w'], node.sm_rows)
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()

    print('recorded {} state rows, {} gated messages, {} envelope '
          'publications, {} smoothed messages'.format(
              len(node.rows), len(node.gate_rows), len(node.pub_rows),
              len(node.sm_rows)))
    return analyse(args)


def _write(path, fields, rows):
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        writer.writerows(rows)


def _read(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return [dict(r) for r in csv.DictReader(handle)]


# --------------------------------------------------------------------------- #
# analysis
# --------------------------------------------------------------------------- #

def _f(row, key):
    return float(row[key])


def _path_length(rows, t_from, t_to):
    total = 0.0
    prev = None
    for r in rows:
        t = _f(r, 't_sim')
        if t < t_from or t > t_to:
            continue
        p = (_f(r, 'gt_x'), _f(r, 'gt_y'))
        if prev is not None:
            total += math.hypot(p[0] - prev[0], p[1] - prev[1])
        prev = p
    return total


def _first(rows, predicate):
    for r in rows:
        if predicate(r):
            return r
    return None


def _stop_report(rows, gate_rows, t_event, label, decel_setting):
    """The controlled stop, measured from three places at once.

    THE SPEED-ACHIEVEMENT COLUMN IS THE POINT (docs/LESSONS.md
    2026-08-04): a stop and a collision look identical in a distance
    figure alone, so the speed at the event and the profile after it are
    printed, and the deceleration measured from ground truth is compared
    with the ramp the gate was configured with.
    """
    out = []
    v_at_event = None
    for r in rows:
        if _f(r, 't_sim') <= t_event:
            v_at_event = _f(r, 'gt_v')
    out.append('  ground speed at the event      : {:+.4f} m/s'.format(
        v_at_event if v_at_event is not None else float('nan')))

    # The REACTION is the first emitted command below the one in force at
    # the event; the first ZERO is the end of the ramp, and reporting only
    # the second would read the whole controlled stop as latency.
    v_before = None
    for r in gate_rows:
        if _f(r, 't') <= t_event:
            v_before = _f(r, 'v')
    if v_before is not None:
        first_react = _first(
            gate_rows,
            lambda r: _f(r, 't') > t_event
            and abs(_f(r, 'v')) < abs(v_before) - 1e-12)
        if first_react is not None:
            out.append('  first REDUCED gated command    : t = {:.4f} s, '
                       '{:.4f} s after the event ({:+.4f} -> {:+.4f} m/s)'
                       .format(_f(first_react, 't'),
                               _f(first_react, 't') - t_event,
                               v_before, _f(first_react, 'v')))

    first_zero_cmd = _first(
        gate_rows, lambda r: _f(r, 't') > t_event and abs(_f(r, 'v')) == 0.0)
    if first_zero_cmd is not None:
        out.append('  first ZERO gated command       : t = {:.4f} s, '
                   '{:.4f} s after the event'.format(
                       _f(first_zero_cmd, 't'),
                       _f(first_zero_cmd, 't') - t_event))
        if v_before:
            out.append('  mean decel of the EMITTED ramp : {:.4f} m/s^2 '
                       '(|{:+.4f}| m/s over {:.4f} s; the gate is set to '
                       '{:.2f})'.format(
                           abs(v_before)
                           / (_f(first_zero_cmd, 't') - t_event),
                           v_before, _f(first_zero_cmd, 't') - t_event,
                           decel_setting))
    else:
        out.append('  first ZERO gated command       : NONE in the run')

    # The emitted profile between the event and zero: a ramp or a step.
    steps = [r for r in gate_rows if _f(r, 't') >= t_event
             and (first_zero_cmd is None
                  or _f(r, 't') <= _f(first_zero_cmd, 't'))]
    if len(steps) >= 2:
        deltas = [abs(_f(steps[i + 1], 'v') - _f(steps[i], 'v'))
                  for i in range(len(steps) - 1)]
        gaps = [_f(steps[i + 1], 't') - _f(steps[i], 't')
                for i in range(len(steps) - 1)]
        # Per-pair rates are computed only over gaps of at least half a
        # gate period: two messages a millisecond apart divide a real
        # step by a meaningless interval and print an implied
        # deceleration of tens of m/s^2 that no vehicle ever saw.
        rates = [d / g for d, g in zip(deltas, gaps) if g >= 0.025]
        out.append('  emitted commands in the stop   : n = {}, largest '
                   'single step {:.4f} m/s'.format(len(steps), max(deltas)))
        if rates:
            out.append('  per-step decel (gaps >= 25 ms) : max {:.4f}, '
                       'mean {:.4f} m/s^2 over n = {} steps (the gate is '
                       'set to {:.2f})'.format(
                           max(rates), sum(rates) / len(rates), len(rates),
                           decel_setting))

    thresholds = [0.01, 0.002]
    for thr in thresholds:
        row = _first(rows, lambda r: _f(r, 't_sim') > t_event
                     and abs(_f(r, 'gt_v')) <= thr)
        if row is None:
            out.append('  standstill (|v| <= {:.3f} m/s)  : not reached in '
                       'the run'.format(thr))
            continue
        t_stop = _f(row, 't_sim')
        out.append('  standstill (|v| <= {:.3f} m/s)  : t = {:.3f} s, '
                   '{:.3f} s after the event, {:.4f} m travelled'.format(
                       thr, t_stop, t_stop - t_event,
                       _path_length(rows, t_event, t_stop)))
    return out


def analyse(args):
    rows = _read(args.csv)
    gate_rows = _read(args.csv + '.gate.csv')
    pub_rows = _read(args.csv + '.pub.csv')
    sm_rows = _read(args.csv + '.sm.csv')
    cfg = load_config(args.config)
    decel = cfg['envelope']['stop_decel_mps2']
    window = cfg['envelope']['stale_window_s']

    print('')
    print('=== scenario {} ==='.format(args.scenario))
    print('run {} state rows over {:.2f} s of simulated time'.format(
        len(rows), _f(rows[-1], 't_sim') if rows else 0.0))

    if args.scenario in ('enable-drop', 'permit-drop', 'supervise'):
        key = 'permit' if args.scenario == 'permit-drop' else 'enable'
        edge = _first(pub_rows, lambda r: int(r[key]) == 0)
        if edge is None:
            print('the {} never went FALSE in the recording'.format(key))
            return 1
        t_event = _f(edge, 't')
        print('the {} FALSE was first PUBLISHED at t = {:.4f} s'.format(
            key, t_event))
        for line in _stop_report(rows, gate_rows, t_event, key, decel):
            print(line)

    elif args.scenario == 'stale':
        t_event = _f(pub_rows[-1], 't')
        print('the double\'s LAST envelope publication: t = {:.4f} s '
              '(nothing commanded a stop; the link simply died)'
              .format(t_event))
        print('the vehicle-side freshness window      : {:.3f} s '
              '(config.yaml envelope.stale_window_s)'.format(window))
        for line in _stop_report(rows, gate_rows, t_event, 'stale', decel):
            print(line)
        first_zero = _first(gate_rows,
                            lambda r: _f(r, 't') > t_event
                            and abs(_f(r, 'v')) == 0.0)
        first_ramp = _first(gate_rows,
                            lambda r: _f(r, 't') > t_event
                            and abs(_f(r, 'v')) < abs(_f(gate_rows[0], 'v'))
                            and True)
        if first_zero is not None:
            print('  detection latency vs the window: first zero at '
                  '{:.4f} s after the last message, against a {:.3f} s '
                  'window + a {:.4f} s ramp from the speed above'.format(
                      _f(first_zero, 't') - t_event, window,
                      _f(first_zero, 't') - t_event - window))

    elif args.scenario == 'clamp':
        print('')
        print('{:>10} {:>6} {:>12} {:>12} {:>12} {:>10}'.format(
            'ceiling', 'n', 'commanded', 'emitted', 'emitted max',
            'ratio'))
        print('-' * 68)
        segments = []
        last = None
        for r in pub_rows:
            c = _f(r, 'ceiling')
            if last is None or c != last:
                segments.append([c, _f(r, 't'), None])
                if len(segments) > 1:
                    segments[-2][2] = _f(r, 't')
                last = c
        if segments:
            segments[-1][2] = _f(rows[-1], 't_sim')
        for ceiling, t_from, t_to in segments:
            # 1.0 s of settling after a ceiling change is discarded: the
            # smoother above is still ramping and the comparison is about
            # the gate, not about the ramp.
            pairs = _pair(sm_rows, gate_rows, t_from + 1.0, t_to)
            if not pairs:
                continue
            cmd = [p[0] for p in pairs]
            out = [p[1] for p in pairs]
            print('{:>10.3f} {:>6} {:>12.4f} {:>12.4f} {:>12.4f} '
                  '{:>10.4f}'.format(
                      ceiling, len(pairs), sum(cmd) / len(cmd),
                      sum(out) / len(out), max(out),
                      (sum(out) / len(out)) / (sum(cmd) / len(cmd))
                      if sum(cmd) else float('nan')))

    elif args.scenario == 'release':
        edge = _first(pub_rows, lambda r: int(r['enable']) == 1)
        t_event = _f(edge, 't')
        print('the gate was RELEASED (enable TRUE first published) at '
              't = {:.4f} s'.format(t_event))
        before = [r for r in sm_rows if _f(r, 't') <= t_event]
        after = [r for r in gate_rows if _f(r, 't') > t_event]
        last_gate_before = [r for r in gate_rows if _f(r, 't') <= t_event]
        if before:
            print('  SMOOTHED command at release    : {:+.4f} m/s  <-- what '
                  'the smoother had wound up to while the vehicle was held '
                  'at zero'.format(_f(before[-1], 'v')))
        if last_gate_before:
            print('  gated command just before      : {:+.4f} m/s'.format(
                _f(last_gate_before[-1], 'v')))
        if after:
            print('  gated command just after       : {:+.4f} m/s'.format(
                _f(after[0], 'v')))
            print('  THE STEP AT RELEASE            : {:+.4f} m/s '
                  '(n = 1 event)'.format(
                      _f(after[0], 'v')
                      - (_f(last_gate_before[-1], 'v')
                         if last_gate_before else 0.0)))
        # The acceleration that step produced, from ground truth.
        window_s = 1.0
        seg = [r for r in rows if t_event <= _f(r, 't_sim')
               <= t_event + window_s]
        if len(seg) >= 2:
            dv = _f(seg[-1], 'gt_v') - _f(seg[0], 'gt_v')
            dt = _f(seg[-1], 't_sim') - _f(seg[0], 't_sim')
            print('  ground-truth accel over {:.1f} s : {:+.4f} m/s^2 '
                  '({:+.4f} -> {:+.4f} m/s)'.format(
                      window_s, dv / dt, _f(seg[0], 'gt_v'),
                      _f(seg[-1], 'gt_v')))
            peak = max(
                (abs(_f(seg[i + 1], 'gt_v') - _f(seg[i], 'gt_v'))
                 / max(1e-6, _f(seg[i + 1], 't_sim') - _f(seg[i], 't_sim')))
                for i in range(len(seg) - 1))
            print('  peak sampled accel (50 Hz)     : {:.4f} m/s^2'.format(
                peak))

    elif args.scenario == 'passthrough':
        pairs = _pair(sm_rows, gate_rows, 3.0, _f(rows[-1], 't_sim'))
        resid = [abs(p[1] - p[0]) for p in pairs]
        lat = [p[2] for p in pairs]
        print('  matched pairs                  : n = {}'.format(len(pairs)))
        if resid:
            print('  |gated - smoothed|             : max {:.3e} m/s, '
                  'mean {:.3e} m/s'.format(max(resid),
                                           sum(resid) / len(resid)))
            print('  exact matches                  : {} of {}'.format(
                sum(1 for x in resid if x == 0.0), len(resid)))
            print('  gate latency (smoothed -> gated): max {:.4f} s, '
                  'mean {:.4f} s'.format(max(lat), sum(lat) / len(lat)))

    elif args.scenario == 'mode':
        print('  mode in force / applied / gate state, at each change:')
        last = None
        for r in rows:
            key = (r['env_mode'], r['mode_applied'], r['gate_state'])
            if key != last:
                print('    t = {:>7.3f} s  in force {}  applied {}  state '
                      '{}  gated v {:+.4f}  traction {:+.4f}'.format(
                          _f(r, 't_sim'), r['env_mode'], r['mode_applied'],
                          r['gate_state'], _f(r, 'gate_v'),
                          _f(r, 'traction')))
                last = key
        gaps = [(_f(gate_rows[i + 1], 't') - _f(gate_rows[i], 't'),
                 _f(gate_rows[i], 't'))
                for i in range(len(gate_rows) - 1)]
        if gaps:
            worst = max(gaps)
            print('  longest silence on the gated topic: {:.3f} s, '
                  'beginning t = {:.3f} s'.format(worst[0], worst[1]))

    # The readback is printed for EVERY scenario: ADR 0014 D5.3 asks the
    # gate's evidence to exercise it, not to mention it.
    hb = [int(r['heartbeat']) for r in rows if int(r['heartbeat']) >= 0]
    if hb:
        moved = sum(1 for i in range(len(hb) - 1) if hb[i + 1] != hb[i])
        print('  readback: heartbeat moved {} times over {} samples, last '
              '{}; mode applied ended {}'.format(
                  moved, len(hb), hb[-1], rows[-1]['mode_applied']))
    return 0


def _pair(sm_rows, gate_rows, t_from, t_to):
    """Match each gated message to the smoothed message in force when it
    was emitted. Returns (smoothed_v, gated_v, latency_s).

    The pairing is causal: the smoothed message must PRECEDE the gated
    one. A gated message with no smoothed message before it is dropped
    rather than matched to the next one.
    """
    pairs = []
    j = 0
    sm = [(float(r['t']), float(r['v'])) for r in sm_rows]
    for g in gate_rows:
        tg, vg = float(g['t']), float(g['v'])
        if tg < t_from or tg > t_to:
            continue
        while j + 1 < len(sm) and sm[j + 1][0] <= tg:
            j += 1
        if not sm or sm[j][0] > tg:
            continue
        pairs.append((sm[j][1], vg, tg - sm[j][0]))
    return pairs


def main():
    parser = argparse.ArgumentParser(
        description='Envelope double and measurement harness (m5-11).')
    sub = parser.add_subparsers(dest='command', required=True)

    for name in ('run', 'analyse'):
        p = sub.add_parser(name)
        p.add_argument('--scenario', required=True)
        p.add_argument('--csv', required=True)
        p.add_argument('--config', default=_DEFAULT_CONFIG)
        p.add_argument('--speed', type=float, default=0.40,
                       help='the commanded cruise speed [m/s]')
        p.add_argument('--ceiling', type=float, default=0.60,
                       help='the permissive ceiling [m/s]')
        p.add_argument('--drop-at', type=float, default=12.0,
                       help='`supervise` only: when the enable goes FALSE')
        p.add_argument('--duration', type=float, default=45.0,
                       help='`supervise` only: how long to record')
        p.add_argument('--cmd-topic', default='/cmd_vel',
                       help='where the harness publishes its command. The '
                            'default is the SMOOTHER\'s input, so the whole '
                            'chain under the controller is exercised.')

    args = parser.parse_args()
    if args.command == 'run':
        return cmd_run(args)
    return analyse(args)


if __name__ == '__main__':
    sys.exit(main())
