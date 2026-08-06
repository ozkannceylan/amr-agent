#!/usr/bin/env python3
"""Measurements for the STO contactor and the plant's torque removal (m5-50).

Four phases, and each one exists because agv/forklift/PLANT-CHANGE-INVENTORY.md
section 9 names it:

  endtoend    command published on /forklift/gz/traction_cmd -> the drive
              shaft observably turning. Run BEFORE the model change with
              --label baseline and AFTER it with --label contactor; the
              difference between the two is the cost of the added hop.
              Reports wall latency, sim latency and the run's RTF, because
              a wall-clock hop and a simulated stop distance are not the
              same currency.

  passthrough the hop measured directly: every value published on the
              command topic against the value that appears on the
              terminal, matched in order. Residual and per-message
              latency, n stated. This is the number the inventory's
              class-(i) figures actually turn on.

  observable  the deliverable of the design spec section 5. A positive
              control, then torque off, then a command that produces
              nothing, then the ENVELOPE REOPENING and still nothing, then
              release and a positive control at the other end.

  deafness    the observable's middle three steps only, for re-running.

EVERY NO-MOTION OBSERVATION HERE CARRIES A POSITIVE CONTROL IN THE SAME
RUN. After the contactor exists, "the vehicle did not move" has a second
cause - a contactor that is open when it should be closed, or a node that
is not running at all - and stillness alone no longer distinguishes a
correct refusal from a dead path (PLANT-CHANGE-INVENTORY.md section 8).
A phase whose positive control fails is DISCARDED, not repaired.
"""

import argparse
import json
import math
import os
import statistics
import sys
import time

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(
    os.path.join(_THIS_DIR, '..', 'config.yaml'))

_DRIVE_JOINT = 'drive_wheel_joint'


def _load(path):
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


def _fmt(value, digits=4):
    if value is None:
        return 'n/a'
    return '{:.{d}f}'.format(value, d=digits)


class Bench(object):
    """One node, several phases. Waits are DEADLINE POLLS on a steady
    clock and never a blocking sleep inside a callback: the harness must
    not stall the executor of the graph it is observing
    (LESSONS 2026-07-29)."""

    def __init__(self, cfg, args):
        import rclpy
        from geometry_msgs.msg import Twist
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from rosgraph_msgs.msg import Clock
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Bool, Float64, UInt16

        self.cfg = cfg
        self.args = args
        topics = cfg['topics']
        self.topics = topics

        self.node = Node('sto_bench')
        qos = QoSProfile(depth=cfg['qos']['depth'])

        self.Float64 = Float64
        self.Bool = Bool
        self.UInt16 = UInt16
        self.Twist = Twist

        # ---- what the bench drives ----
        self.pub_traction = self.node.create_publisher(
            Float64, topics['gz_traction_cmd'], qos)
        self.pub_demand = self.node.create_publisher(
            Bool, topics['safety_torque_off_demand'], qos)
        self.pub_enable = self.node.create_publisher(
            Bool, topics['envelope_motion_enable'], qos)
        self.pub_ceiling = self.node.create_publisher(
            Float64, topics['envelope_speed_ceiling'], qos)
        self.pub_permit = self.node.create_publisher(
            Bool, topics['envelope_equipment_permit'], qos)
        self.pub_mode = self.node.create_publisher(
            UInt16, topics['mode_in_force'], qos)
        self.pub_cmd_vel = self.node.create_publisher(
            Twist, topics['cmd_vel_smoothed'], qos)

        # ---- what the bench watches ----
        self.wheel_vel = None
        self.wheel_stamp_s = None
        self.wheel_arrived_mono = None
        self.node.create_subscription(
            JointState, topics['joint_states'], self.cb_joint_state, qos)

        # GROUND TRUTH. The bridge remaps the model's odometry onto
        # /forklift/odom and its joint feedback onto /forklift/joint_states,
        # so these are the ROS-side names and not the gz ones; reading the
        # gz names here would have subscribed to nothing and every
        # observation would have read 'did not move'.
        self.pose = None
        self.node.create_subscription(
            Odometry, topics['odom'], self.cb_gz_odom, qos)

        self.sim_s = None
        self.node.create_subscription(Clock, topics['clock'], self.cb_clock,
                                      qos)

        self.applied = None
        self.node.create_subscription(
            Bool, topics['safety_torque_off_applied'],
            self.cb_torque_off_applied, qos)

        # The two witnesses that separate "the chain went quiet" from "the
        # plant went deaf": the converter's tricycle setpoint and the
        # command actually published at the plant boundary.
        self.cmd_traction_seen = 0
        self.cmd_traction_last = None
        self.node.create_subscription(
            Float64, topics['cmd_traction_speed'],
            self.cb_cmd_traction_speed, qos)
        self.plant_cmd_seen = 0
        self.plant_cmd_last = None
        self.node.create_subscription(
            Float64, topics['gz_traction_cmd'], self.cb_plant_cmd, qos)

        # Terminal side, present only after the model change.
        self.terminal = []
        self.node.create_subscription(
            Float64, topics['gz_actuator_traction_cmd'],
            self.cb_terminal, qos)

        self.sent = []

    # ---- callbacks (cb_*, the rclpy shadowing rule) --------------------

    def cb_joint_state(self, msg):
        if _DRIVE_JOINT not in msg.name:
            return
        index = msg.name.index(_DRIVE_JOINT)
        if index < len(msg.velocity):
            self.wheel_vel = msg.velocity[index]
            self.wheel_stamp_s = (msg.header.stamp.sec
                                  + msg.header.stamp.nanosec * 1e-9)
            self.wheel_arrived_mono = time.monotonic()

    def cb_gz_odom(self, msg):
        self.pose = (msg.pose.pose.position.x, msg.pose.pose.position.y)

    def cb_clock(self, msg):
        self.sim_s = msg.clock.sec + msg.clock.nanosec * 1e-9

    def cb_torque_off_applied(self, msg):
        self.applied = bool(msg.data)

    def cb_cmd_traction_speed(self, msg):
        self.cmd_traction_seen += 1
        self.cmd_traction_last = float(msg.data)

    def cb_plant_cmd(self, msg):
        self.plant_cmd_seen += 1
        self.plant_cmd_last = float(msg.data)

    def cb_terminal(self, msg):
        self.terminal.append((time.monotonic(), float(msg.data)))

    # ---- plumbing ------------------------------------------------------

    def spin(self, seconds):
        import rclpy
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.005)

    def spin_until(self, predicate, timeout_s):
        import rclpy
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            rclpy.spin_once(self.node, timeout_sec=0.002)
            if predicate():
                return True
        return False

    def traction(self, value):
        msg = self.Float64()
        msg.data = float(value)
        self.pub_traction.publish(msg)
        self.sent.append((time.monotonic(), float(value)))

    def demand(self, value):
        msg = self.Bool()
        msg.data = bool(value)
        self.pub_demand.publish(msg)

    def envelope(self, permissive, ceiling=0.60):
        enable = self.Bool()
        enable.data = bool(permissive)
        self.pub_enable.publish(enable)
        permit = self.Bool()
        permit.data = bool(permissive)
        self.pub_permit.publish(permit)
        top = self.Float64()
        top.data = float(ceiling)
        self.pub_ceiling.publish(top)
        mode = self.UInt16()
        mode.data = int(self.cfg['envelope']['mode_autonomous'])
        self.pub_mode.publish(mode)

    def cmd_vel(self, vx):
        msg = self.Twist()
        msg.linear.x = float(vx)
        self.pub_cmd_vel.publish(msg)

    def moved(self, origin):
        if self.pose is None or origin is None:
            return None
        return math.hypot(self.pose[0] - origin[0], self.pose[1] - origin[1])

    def rest(self, seconds=2.0):
        """Command zero and wait for the shaft to stop. Returns the
        residual wheel rate so a run can say what 'at rest' meant."""
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.traction(0.0)
            self.spin(0.1)
        return self.wheel_vel

    # ---- phases --------------------------------------------------------

    def phase_endtoend(self, trials, step_radps, detect_radps):
        """Command published -> shaft observably turning. The same
        instrument before and after the plant change."""
        rows = []
        rtf_samples = []
        for trial in range(trials):
            self.rest(1.5)
            wall0 = time.monotonic()
            sim0 = self.sim_s
            self.traction(step_radps)
            hit = self.spin_until(
                lambda: (self.wheel_vel is not None
                         and abs(self.wheel_vel) >= detect_radps), 5.0)
            wall1 = self.wheel_arrived_mono
            sim1 = self.wheel_stamp_s
            if not hit or wall1 is None or sim0 is None or sim1 is None:
                rows.append({'trial': trial + 1, 'detected': False})
                self.traction(0.0)
                continue
            rows.append({
                'trial': trial + 1,
                'detected': True,
                'wall_s': wall1 - wall0,
                'sim_s': sim1 - sim0,
                'wheel_radps': self.wheel_vel,
            })
            if wall1 - wall0 > 0:
                rtf_samples.append((sim1 - sim0) / (wall1 - wall0))
            self.traction(0.0)
            self.spin(0.4)
        self.rest(1.0)

        good = [r for r in rows if r.get('detected')]
        result = {
            'phase': 'endtoend',
            'label': self.args.label,
            'n_attempted': trials,
            'n_detected': len(good),
            'step_radps': step_radps,
            'detect_radps': detect_radps,
            'rows': rows,
        }
        if good:
            walls = [r['wall_s'] for r in good]
            sims = [r['sim_s'] for r in good]
            result['wall_mean_s'] = statistics.fmean(walls)
            result['wall_min_s'] = min(walls)
            result['wall_max_s'] = max(walls)
            result['sim_mean_s'] = statistics.fmean(sims)
            result['sim_min_s'] = min(sims)
            result['sim_max_s'] = max(sims)
        if rtf_samples:
            result['rtf_mean'] = statistics.fmean(rtf_samples)
        return result

    def phase_passthrough(self, seconds, hz):
        """The hop itself: value in against value out, matched in order."""
        self.terminal = []
        self.sent = []
        period = 1.0 / hz
        deadline = time.monotonic() + seconds
        index = 0
        # A command that is NEVER CONSTANT, for the reason section 7 of
        # EVIDENCE_ENVELOPE gives: a constant command hides rounding,
        # quantisation, holding and re-publication all four.
        while time.monotonic() < deadline:
            value = 1.5 * math.sin(2.0 * math.pi * index / 37.0)
            self.traction(value)
            index += 1
            self.spin(period)
        self.spin(0.5)
        self.traction(0.0)
        self.spin(0.3)

        sent = list(self.sent)
        got = list(self.terminal)
        pairs = []
        j = 0
        for t_sent, value in sent:
            while j < len(got) and got[j][0] < t_sent:
                j += 1
            if j >= len(got):
                break
            pairs.append((value, got[j][1], got[j][0] - t_sent))
            j += 1
        residuals = [abs(a - b) for a, b, _ in pairs]
        lat = [d for _, _, d in pairs]
        result = {
            'phase': 'passthrough',
            'n_sent': len(sent),
            'n_terminal': len(got),
            'n_pairs': len(pairs),
            'max_residual': max(residuals) if residuals else None,
            'exact_matches': sum(1 for r in residuals if r == 0.0),
            'hop_mean_s': statistics.fmean(lat) if lat else None,
            'hop_max_s': max(lat) if lat else None,
            'hop_min_s': min(lat) if lat else None,
        }
        return result

    def phase_observable(self, run_deafness_only=False):
        steps = []
        step_radps = self.args.step_radps
        move_threshold_m = 0.10
        still_threshold_m = 0.02
        still_wheel_radps = 0.20

        def record(name, passed, detail):
            steps.append({'step': name, 'pass': bool(passed),
                          'detail': detail})
            print('  {:<28} {}  {}'.format(
                name, 'PASS' if passed else 'FAIL', detail))

        self.envelope(False)
        self.demand(False)
        self.rest(2.0)
        self.spin(0.5)

        if not run_deafness_only:
            # ---- O1 positive control, torque present -------------------
            origin = self.pose
            deadline = time.monotonic() + 3.0
            while time.monotonic() < deadline:
                self.traction(step_radps)
                self.spin(0.05)
            travelled = self.moved(origin)
            self.rest(2.0)
            record('O1 positive control', travelled is not None
                   and travelled > move_threshold_m,
                   'moved {} m under a direct plant command (needs > {} m)'
                   .format(_fmt(travelled), move_threshold_m))

        # ---- O2 assert the demand ---------------------------------------
        self.applied = None
        self.demand(True)
        seen = self.spin_until(lambda: self.applied is True, 2.0)
        record('O2 torque-off applied', seen,
               'contactor reported applied={} within 2 s'
               .format(self.applied))

        # ---- O3 deaf to a direct plant command ---------------------------
        origin = self.pose
        self.cmd_traction_seen = 0
        self.plant_cmd_seen = 0
        deadline = time.monotonic() + 4.0
        while time.monotonic() < deadline:
            self.traction(step_radps)
            self.spin(0.05)
        travelled = self.moved(origin)
        wheel = self.wheel_vel
        record('O3 deaf, direct command',
               travelled is not None and travelled < still_threshold_m
               and wheel is not None and abs(wheel) < still_wheel_radps,
               'moved {} m with {} commands delivered to the plant '
               'boundary, shaft {} rad/s'
               .format(_fmt(travelled), self.plant_cmd_seen, _fmt(wheel)))

        # ---- O4 the envelope reopens, and it still produces nothing ------
        #
        # THE STEP THE WHOLE DESIGN TURNS ON. The envelope is driven fully
        # permissive and a Twist is fed through the real chain, so the
        # command is FORMED and REACHES the plant boundary - the witness
        # counters below are what say so. If the vehicle still does not
        # move, the deafness is the plant's and not a silent chain's.
        origin = self.pose
        self.cmd_traction_seen = 0
        self.plant_cmd_seen = 0
        deadline = time.monotonic() + 6.0
        while time.monotonic() < deadline:
            self.envelope(True)
            self.cmd_vel(0.40)
            self.spin(0.05)
        travelled = self.moved(origin)
        formed = self.cmd_traction_seen
        at_boundary = self.plant_cmd_seen
        last = self.plant_cmd_last
        record('O4 deaf on envelope reopen',
               travelled is not None and travelled < still_threshold_m
               and formed > 0 and at_boundary > 0
               and last is not None and abs(last) > 0.0,
               'moved {} m while the converter formed {} setpoints and {} '
               'commands reached the plant boundary, last {} rad/s'
               .format(_fmt(travelled), formed, at_boundary, _fmt(last)))
        self.cmd_vel(0.0)
        self.envelope(False)
        self.spin(0.5)

        # ---- O5 release, and no auto-resume ------------------------------
        self.applied = None
        self.demand(False)
        released = self.spin_until(lambda: self.applied is False, 2.0)
        origin = self.pose
        self.spin(2.0)          # silence: no command published by anyone
        crept = self.moved(origin)
        record('O5 release, no auto-resume', released and crept is not None
               and crept < still_threshold_m,
               'contactor reported applied={} and the vehicle crept {} m '
               'in 2 s during which no non-zero command was published by '
               'anyone'.format(self.applied, _fmt(crept)))

        if not run_deafness_only:
            # ---- O6 positive control at the other end -------------------
            #
            # DRIVEN THROUGH THE ENVELOPE CHAIN, exactly as O4 was, and
            # for a reason: the strongest possible control for O4 is the
            # SAME command producing motion once the demand has fallen.
            # A direct plant command would be a weaker control and, with
            # forklift_io publishing its own zero setpoint at 20 Hz, it
            # would also be contesting the terminal - the first attempt
            # of this run measured 0.0666 m that way and it was the
            # harness competing with the chain, not the plant.
            origin = self.pose
            deadline = time.monotonic() + 6.0
            while time.monotonic() < deadline:
                self.envelope(True)
                self.cmd_vel(0.40)
                self.spin(0.05)
            travelled = self.moved(origin)
            self.cmd_vel(0.0)
            self.envelope(False)
            self.rest(2.0)
            record('O6 positive control after', travelled is not None
                   and travelled > move_threshold_m,
                   'moved {} m on the SAME permissive envelope and the '
                   'SAME Twist that produced nothing at O4 (needs > {} m)'
                   .format(_fmt(travelled), move_threshold_m))

        return {
            'phase': 'deafness' if run_deafness_only else 'observable',
            'steps': steps,
            'all_pass': all(s['pass'] for s in steps),
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', default=_DEFAULT_CONFIG)
    parser.add_argument('--phase', required=True,
                        choices=['endtoend', 'passthrough', 'observable',
                                 'deafness'])
    parser.add_argument('--label', default='',
                        help='free text recorded with the result, e.g. '
                             'baseline or contactor')
    parser.add_argument('--trials', type=int, default=12)
    parser.add_argument('--step-radps', type=float, default=4.0)
    parser.add_argument('--detect-radps', type=float, default=0.50)
    parser.add_argument('--seconds', type=float, default=12.0)
    parser.add_argument('--hz', type=float, default=20.0)
    parser.add_argument('--json', default='',
                        help='write the result here as JSON')
    known, rest = parser.parse_known_args(argv)

    cfg = _load(known.config)

    import rclpy
    rclpy.init(args=rest)
    bench = Bench(cfg, known)
    try:
        # Let discovery finish before anything is published: a command
        # emitted into an unfinished graph is a command the plant never
        # sees (LESSONS 2026-07-28).
        bench.spin(2.0)
        if known.phase == 'endtoend':
            result = bench.phase_endtoend(
                known.trials, known.step_radps, known.detect_radps)
        elif known.phase == 'passthrough':
            result = bench.phase_passthrough(known.seconds, known.hz)
        else:
            result = bench.phase_observable(
                run_deafness_only=(known.phase == 'deafness'))
    finally:
        bench.node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass

    print(json.dumps(result, indent=2, default=str))
    if known.json:
        with open(known.json, 'w', encoding='utf-8') as handle:
            json.dump(result, handle, indent=2, default=str)
    if 'all_pass' in result:
        return 0 if result['all_pass'] else 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
