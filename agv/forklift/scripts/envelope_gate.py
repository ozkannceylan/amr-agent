#!/usr/bin/env python3
"""envelope_gate.py - the vehicle-side enforcer of the PLC's motion
envelope, and the one place a commanded motion can be refused or bounded
before it reaches the actuators.

WHAT THIS NODE IS

  The gate of ADR 0014 seam (b), sitting BELOW the velocity smoother:

      controller_server -> /cmd_vel -> velocity_smoother
        -> /cmd_vel_smoothed -> [THIS NODE] -> /cmd_vel_gated
          -> cmd_vel_to_tricycle.py -> /forklift/cmd/*
            -> forklift_io.py -> the gz joint commands

  It consumes the three envelope elements the PLC publishes and the drive
  mode in force (opcua-nodes.md section 12.4, section 12.3), and it
  enforces the seam (b) gate law:

      enable false, or the envelope stale  ->  controlled stop, on this
                                               vehicle's own deceleration
                                               ramp
      enable true                          ->  pass the command through,
                                               CLAMPED to the speed
                                               ceiling

  and it reports back what it is applying (section 12.6), which is what
  makes the PLC's supervision a check rather than a claim (ADR 0014 D5.3).

WHY IT SITS BELOW THE SMOOTHER, WHICH IS THE DESIGN DECISION
  A gate ABOVE the smoother is a gate the smoother can ramp past: with
  the link dead the smoother would go on integrating from its own last
  command and emit a value the gate never saw. ADR 0014 seam (b) states
  it as a rule - "a gate above the smoother is a gate the smoother can
  ramp past; a gate that needs the link is a permission that lapses
  exactly when it matters most" - and this node is where that rule is
  implemented.

  Below the smoother the gate is what the drive actually receives, and it
  is why nav2.yaml runs the smoother CLOSED_LOOP: a smoother limiting
  acceleration against its OWN last command, with the vehicle held at
  zero by this gate, keeps ramping away from reality and hands over a
  step at release. Measured both ways in EVIDENCE_ENVELOPE.md section 6.

WHAT THIS NODE IS NOT

  IT IS NOT A SAFETY FUNCTION, and no reaction it performs is one. Loss
  of the envelope is a DEGRADED MODE, not a safety event (invariant 2,
  opcua-nodes.md section 12.1). The protective stop, the e-stop chain and
  safe torque off are onboard and hardwired, they owe nothing to this
  node, and no message on any topic here can trigger, release or delay
  one (invariant 1). No PL, SIL, Category or PFH is claimed for anything
  in this file (ADR 0011 D5).

  IT IS NOT AN OPC UA CLIENT and never becomes one (section 12.1). It
  reads ROS 2 topics the bridge republishes, which is what keeps
  invariant 11's layer adjacency intact. No velocity, ceiling or motion
  command of any granularity leaves the vehicle through this node
  (ADR 0014 D1).

  IT IS NOT A CONTROLLER. It plans nothing, corrects nothing and closes
  no loop. Given a permissive envelope and a command under the ceiling it
  emits the command it was handed, unchanged (measured, section 7).

  IT IS NOT REAL TIME. Its deadlines are the vehicle's own and are best
  effort; nothing with a deterministic timing requirement lives here
  (invariant 9).

=========================== THE GATE LAW ===========================

Evaluated every cycle, and on every command that arrives while passing:

  permissive := envelope_fresh
                AND mode_in_force == Autonomous
                AND motion_enable
                AND equipment_permit
                AND ceiling_valid

  permissive     -> out = clamp(command, ceiling)
  not permissive -> out ramps to zero at `envelope.stop_decel_mps2` and
                    is then held at zero

EVERY TERM IS TESTED AFFIRMATIVELY, and the fault is taken in the ELSE
(LESSONS 2026-07-27). A value that has never been received is NOT fresh,
so the boot state is the non-permissive one: "not yet told" is not
"permitted" (section 12.3 M3, section 12.6 V2 one layer out).

THE FOUR CONSERVATIVE READINGS, each taken because section 12 specifies
the datum and not this consumer's reaction to it. Every one of them can
only ever make the gate MORE restrictive, all four are listed in
EVIDENCE_ENVELOPE.md section 2, and each is raised in the m5-11 report:

  (a) EQUIPMENT PERMIT FALSE STOPS THE VEHICLE. Section 12.4 defines the
      permit as the PLC's statement that the equipment it owns is ready
      to be acted on, and section 12.5 Z4 records that at M5 its term set
      is empty. Neither says what a consumer does with it. The permissive
      reading - "it bounds only the act of engaging equipment, so drive
      on" - would have the vehicle moving under a supervisor that has
      stated no readiness, and its cold start is FALSE precisely because
      an unstated readiness is not a granted one. So it is a term of the
      gate law.

  (b) A CEILING OUTSIDE ITS WINDOW IS NON-PERMISSIVE, not a bound to
      clamp. That one section 12.4 does state, and it is implemented as
      stated; it is listed here because it is the same shape as the
      others.

  (c) AN UNDEFINED MODE VALUE IS A FAULT, not a mode. Section 12.3 says
      so; the reaction - stop - is this layer's.

  (d) MODE Teleop RELEASES THE TOPIC RATHER THAN COMMANDING ZERO ON IT.
      See "THE TWO COMMAND PATHS" below.

===================== THE CONTROLLED STOP, AND WHY IT RAMPS =====================

ADR 0014 seam (b): "enable false, or envelope stale -> controlled stop ON
THE VEHICLE'S OWN DECELERATION RAMP". So the gate does not step its
output to zero. It reduces the magnitude of the emitted twist at
`envelope.stop_decel_mps2` and SCALES BOTH COMPONENTS BY THE SAME FACTOR,
which preserves the curvature exactly: with w = v tan(delta) / L, scaling
v and w together leaves delta unchanged, so the vehicle decelerates ALONG
THE ARC IT WAS ALREADY ON rather than straightening into something nobody
commanded. That is the same argument cmd_vel_to_tricycle.py makes for its
traction clamp, applied here.

The ramp is this node's own and does not depend on the smoother running:
the case the gate exists for is the one where the layer above is dead.

BELOW `navigation.zero_speed_mps` THE REMAINDER IS DROPPED TO ZERO. That
threshold is the vehicle's own standstill threshold, derived in
config.yaml from one drive-encoder count, and it is READ rather than
re-derived here (invariant 10). A pure yaw request (v = 0, w != 0) has no
speed magnitude to ramp and is zeroed in one step - the vehicle is not
moving along the ground, so there is nothing to lurch, and the converter
refuses in-place rotation in any case.

================== THE TWO COMMAND PATHS, AND THE SILENT STATE ==================

opcua-nodes.md section 12.9 leaves the arbitration to this layer: "which
topic reaches the actuators, and how the change of source is made without
a step in the command, is agv/'s design (m5-11)". Two sources exist:

  Teleop      the PLC forms every setpoint and the bridge republishes
              them straight onto /forklift/cmd/* (section 10.6, C1). The
              autonomous chain must NOT be publishing then: the converter
              writes the same two topics, and two publishers on one
              actuator topic is two owners of one datum (invariant 10).

  Autonomous  this chain, gated here.

So the gate, on leaving Autonomous, first ramps its output to zero on the
same controlled ramp - the change of source without a step - and only
when it is AT zero and the mode in force is Teleop does it FALL SILENT,
publishing nothing until the mode returns. Falling silent immediately
would leave forklift_io.py republishing the last command it was handed at
20 Hz, which is a vehicle driving on a stale value.

In mode None, and while the mode is unknown, the gate does NOT fall
silent: it holds an explicit zero, because in neither of those states is
another owner known to be writing.

THE REPORT BACK (section 12.6, ADR 0014 D5.3)

  /forklift/mode/applied      what control law this node is applying NOW,
                              in the section 12.3 encoding. It is a
                              READBACK and never a second answer to "what
                              mode is the machine in" (M1, M4).
  /forklift/vehicle/heartbeat this node's own cycle counter, UInt16,
                              wrapping. Its only meaning is "the
                              vehicle's control layer completed a cycle
                              recently".

`mode/applied` follows the ADOPT WINDOW and not the request: it changes
when the gate has ACTUALLY adopted the law, which for the release to
teleop is when the output has reached zero. A readback that echoed the
command the instant it arrived would report a state the machine had not
reached, which is the defect LESSONS 2026-07-31 records one layer up.

Usage (after sourcing /opt/ros/jazzy/setup.bash):

  python3 agv/forklift/scripts/envelope_gate.py \\
      [--config PATH] [--cmd-in /cmd_vel_smoothed] \\
      [--cmd-out /cmd_vel_gated] [--ros-args ...]

  python3 agv/forklift/scripts/envelope_gate.py --self-check
"""

import argparse
import math
import os
import sys

import yaml

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_CONFIG = os.path.normpath(os.path.join(_THIS_DIR, '..', 'config.yaml'))

#: State of the gate, published as a diagnostic of THIS node. It is not a
#: vehicle state and not a PLC datum, so it is named here rather than in
#: config.yaml's `topics:` contract table - the pattern
#: cmd_vel_to_tricycle.py uses for its refusal counter.
_STATE_TOPIC = '/forklift/envelope/gate_state'

STATE_PASSING = 0    # permissive: the command is passed, clamped
STATE_STOPPING = 1   # non-permissive: ramping the output down to zero
STATE_HOLD_ZERO = 2  # non-permissive and at zero: publishing zero
STATE_SILENT = 3     # at zero and the PLC owns the actuator topics

_STATE_NAMES = {
    STATE_PASSING: 'PASSING',
    STATE_STOPPING: 'STOPPING',
    STATE_HOLD_ZERO: 'HOLD_ZERO',
    STATE_SILENT: 'SILENT (teleop owns /forklift/cmd/*)',
}


def load_config(path):
    """Read the named-constant file. Every value this node uses is in it."""
    with open(path, 'r', encoding='utf-8') as handle:
        return yaml.safe_load(handle)


# --------------------------------------------------------------------------- #
# The two pieces of arithmetic, kept free of ROS and of node state so that
# they are checkable without a simulator (`--self-check`).
# --------------------------------------------------------------------------- #

def clamp_to_ceiling(v, w, ceiling_mps):
    """Bound the MAGNITUDE of ground speed to the ceiling, preserving the
    commanded arc.

    Returns (v_out, w_out, clamped).

    The ceiling is unsigned and bounds the magnitude in either direction
    (opcua-nodes.md section 12.4 E2), so the sign of v survives: a reverse
    command is bounded, never reversed and never blocked.

    BOTH COMPONENTS ARE SCALED BY THE SAME FACTOR. Scaling v alone would
    change w/v, which the converter reads as the steer angle, so a clamp
    would silently re-curve the path. Scaling together holds delta and the
    vehicle drives the same arc more slowly. Clamping a command is NOT
    blocking it: section 4 observation 3 measures exactly this.
    """
    speed = abs(v)
    if speed <= ceiling_mps:
        return v, w, False
    factor = ceiling_mps / speed
    return v * factor, w * factor, True


def ramp_towards_zero(v, w, decel_mps2, dt_s, zero_speed_mps):
    """One step of the controlled stop, curvature preserving.

    Returns (v_out, w_out). The magnitude falls by decel * dt; both
    components are scaled by the same factor so the arc is unchanged. A
    request with no ground speed to ramp (|v| under the standstill
    threshold) goes to zero in one step: there is no motion along the
    ground to decelerate.
    """
    speed = abs(v)
    if speed <= zero_speed_mps:
        return 0.0, 0.0
    target = speed - decel_mps2 * dt_s
    if target <= zero_speed_mps:
        return 0.0, 0.0
    factor = target / speed
    return v * factor, w * factor


def _self_check():
    """Exercise the two functions above against hand-computed values.

    It proves the arithmetic, not the node: what the node does with a
    stale envelope is measured in the simulator and is in
    EVIDENCE_ENVELOPE.md, because a unit test of a fail-safe is a test of
    the branch its author remembered.
    """
    failures = []

    def check(name, got, want, tol=1e-9):
        if not all(abs(g - w) <= tol for g, w in zip(got, want)):
            failures.append('{}: got {} want {}'.format(name, got, want))

    # Under the ceiling: passed through EXACTLY, and the flag is false.
    v, w, cl = clamp_to_ceiling(0.30, 0.10, 0.60)
    check('under ceiling', (v, w), (0.30, 0.10))
    if cl:
        failures.append('under ceiling: reported clamped')

    # Over the ceiling: magnitude bounded, curvature w/v held.
    v, w, cl = clamp_to_ceiling(0.60, 0.20, 0.30)
    check('over ceiling', (v, w), (0.30, 0.10))
    if not cl:
        failures.append('over ceiling: did not report clamped')
    if abs((w / v) - (0.20 / 0.60)) > 1e-12:
        failures.append('over ceiling: curvature changed')

    # Reverse is bounded, not reversed and not blocked.
    v, w, cl = clamp_to_ceiling(-0.90, 0.30, 0.30)
    check('reverse ceiling', (v, w), (-0.30, 0.10))

    # A zero ceiling permits no motion at all (E2).
    v, w, cl = clamp_to_ceiling(0.50, 0.20, 0.0)
    check('zero ceiling', (v, w), (0.0, 0.0))

    # The ramp: 0.50 m/s^2 for 0.05 s takes 0.025 m/s off, curvature held.
    v, w = ramp_towards_zero(0.40, 0.20, 0.50, 0.05, 0.002)
    check('ramp step', (v, w), (0.375, 0.1875))
    if abs((w / v) - (0.20 / 0.40)) > 1e-12:
        failures.append('ramp step: curvature changed')

    # The last step lands exactly on zero rather than on an epsilon.
    v, w = ramp_towards_zero(0.01, 0.005, 0.50, 0.05, 0.002)
    check('ramp final', (v, w), (0.0, 0.0))

    # Reverse decelerates towards zero rather than through it.
    v, w = ramp_towards_zero(-0.40, 0.20, 0.50, 0.05, 0.002)
    check('ramp reverse', (v, w), (-0.375, 0.1875))

    # A pure yaw request has no ground speed to ramp.
    v, w = ramp_towards_zero(0.0, 0.50, 0.50, 0.05, 0.002)
    check('ramp pure yaw', (v, w), (0.0, 0.0))

    for line in failures:
        print('FAIL ' + line)
    print('self-check: {}'.format('PASS' if not failures else 'FAIL'))
    return 0 if not failures else 1


# --------------------------------------------------------------------------- #
# the node
# --------------------------------------------------------------------------- #

def _build_node(cfg, cmd_in, cmd_out):
    import rclpy
    from geometry_msgs.msg import Twist
    from rclpy.node import Node
    from rclpy.qos import QoSProfile
    from std_msgs.msg import Bool, Float64, UInt16

    class EnvelopeGate(Node):
        """The envelope gate. One node, one job: bound or refuse the
        commanded motion, and say what it is applying."""

        def __init__(self):
            super().__init__('envelope_gate')

            env = cfg['envelope']
            topics = cfg['topics']

            self.stale_window_s = env['stale_window_s']
            self.command_timeout_s = env['command_timeout_s']
            self.stop_decel_mps2 = env['stop_decel_mps2']
            self.period_s = 1.0 / env['publish_hz']
            self.ceiling_max_mps = env['ceiling_max_mps']
            self.mode_none = env['mode_none']
            self.mode_teleop = env['mode_teleop']
            self.mode_autonomous = env['mode_autonomous']
            # READ, not re-derived: the vehicle's own standstill threshold
            # is one datum with one owner (invariant 10).
            self.zero_speed_mps = cfg['navigation']['zero_speed_mps']
            self.throttle_s = cfg['logging']['throttle_s']

            qos = QoSProfile(depth=cfg['qos']['depth'])

            self.pub_cmd = self.create_publisher(Twist, cmd_out, qos)
            self.pub_mode_applied = self.create_publisher(
                UInt16, topics['mode_applied'], qos)
            self.pub_heartbeat = self.create_publisher(
                UInt16, topics['vehicle_heartbeat'], qos)
            self.pub_state = self.create_publisher(UInt16, _STATE_TOPIC, qos)

            self.sub_cmd = self.create_subscription(
                Twist, cmd_in, self.cb_cmd_vel, qos)
            self.sub_enable = self.create_subscription(
                Bool, topics['envelope_motion_enable'],
                self.cb_motion_enable, qos)
            self.sub_ceiling = self.create_subscription(
                Float64, topics['envelope_speed_ceiling'],
                self.cb_speed_ceiling, qos)
            self.sub_permit = self.create_subscription(
                Bool, topics['envelope_equipment_permit'],
                self.cb_equipment_permit, qos)
            self.sub_mode = self.create_subscription(
                UInt16, topics['mode_in_force'], self.cb_mode_in_force, qos)

            # Every held value starts at the NON-PERMISSIVE reading and
            # every stamp starts at None, which is "never received" and
            # not "received long ago": a boot must not be able to age into
            # freshness (section 12.6 V2's polarity, one layer out).
            self.enable = False
            self.ceiling_mps = 0.0
            self.permit = False
            self.mode_in_force = self.mode_none
            self.t_enable = None
            self.t_ceiling = None
            self.t_permit = None
            self.t_mode = None
            self.t_cmd = None

            self.cmd_v = 0.0
            self.cmd_w = 0.0
            self.out_v = 0.0
            self.out_w = 0.0
            self.state = STATE_HOLD_ZERO
            self.mode_applied = self.mode_none
            self.heartbeat = 0

            self.t_last_step = None
            self.t_last_publish = None
            # FALSE until an explicit zero has actually gone out on the
            # wire. The release to the teleop path waits for it.
            self.zero_published = False
            self.clamps = 0
            self.stops = 0

            self.timer = self.create_timer(self.period_s, self.cb_cycle)

            self.get_logger().info(
                'envelope_gate up: {} -> {}; freshness window {:.3f} s, '
                'stop ramp {:.2f} m/s^2, ceiling window 0.00-{:.2f} m/s, '
                'output {:.1f} Hz. THE ENVELOPE IS A PERMISSION, NOT A '
                'COMMAND: this node can prevent motion and can never cause '
                'it. It is not a safety function (invariant 2).'.format(
                    cmd_in, cmd_out, self.stale_window_s,
                    self.stop_decel_mps2, self.ceiling_max_mps,
                    1.0 / self.period_s))

        # -------------------------------------------------------------- #
        # Callbacks are named cb_* so that none can shadow an rclpy Node
        # attribute (docs/LESSONS.md 2026-07-27).
        # -------------------------------------------------------------- #

        def _now_s(self):
            return self.get_clock().now().nanoseconds * 1e-9

        def cb_motion_enable(self, msg):
            self.enable = bool(msg.data)
            self.t_enable = self._now_s()

        def cb_speed_ceiling(self, msg):
            self.ceiling_mps = float(msg.data)
            self.t_ceiling = self._now_s()

        def cb_equipment_permit(self, msg):
            self.permit = bool(msg.data)
            self.t_permit = self._now_s()

        def cb_mode_in_force(self, msg):
            self.mode_in_force = int(msg.data)
            self.t_mode = self._now_s()

        def cb_cmd_vel(self, msg):
            v, w = msg.linear.x, msg.angular.z
            if not (math.isfinite(v) and math.isfinite(w)):
                self.get_logger().warn(
                    'command is not finite (v={}, w={}); it is discarded '
                    'and the gate keeps its own last command, which ages '
                    'out through the command timeout'.format(v, w))
                return
            self.cmd_v, self.cmd_w = v, w
            self.t_cmd = self._now_s()
            # Emitted immediately while passing, so the gate adds no
            # latency to the permissive path. The cycle timer owns the
            # ramp and the held zero.
            self._step(self._now_s())

        def cb_cycle(self):
            now = self._now_s()
            self.heartbeat = (self.heartbeat + 1) % 65536
            hb = UInt16()
            hb.data = self.heartbeat
            self.pub_heartbeat.publish(hb)
            # While PASSING the command itself has already been emitted by
            # its own callback, so a tick that lands inside the same
            # period would only duplicate it on the wire. The ramp and the
            # held zero are the timer's, and they are never skipped.
            if (self.state == STATE_PASSING
                    and self.t_last_publish is not None
                    and (now - self.t_last_publish) < 0.9 * self.period_s):
                return
            self._step(now)

        # -------------------------------------------------------------- #
        # the gate law
        # -------------------------------------------------------------- #

        def _fresh(self, stamp, now):
            """Affirmative: a value is fresh only if it has been received
            AND is inside the window. Never received is never fresh."""
            return stamp is not None and (now - stamp) <= self.stale_window_s

        def _envelope_fresh(self, now):
            return (self._fresh(self.t_enable, now)
                    and self._fresh(self.t_ceiling, now)
                    and self._fresh(self.t_permit, now)
                    and self._fresh(self.t_mode, now))

        def _ceiling_valid(self):
            # Affirmative, so a NaN falls through to the fault branch
            # (LESSONS 2026-07-27).
            return (math.isfinite(self.ceiling_mps)
                    and 0.0 <= self.ceiling_mps <= self.ceiling_max_mps)

        def _mode_valid(self):
            return self.mode_in_force in (
                self.mode_none, self.mode_teleop, self.mode_autonomous)

        def _reason(self, now):
            """The first failing term, for the log. Order is the gate
            law's, so the reason is the one a reader would check first."""
            if not self._envelope_fresh(now):
                return 'envelope stale (or never received)'
            if not self._mode_valid():
                return 'mode in force is {}, which is not a defined mode' \
                    .format(self.mode_in_force)
            if self.mode_in_force != self.mode_autonomous:
                return 'mode in force is {}, not Autonomous'.format(
                    self.mode_in_force)
            if not self.enable:
                return 'motion enable is FALSE'
            if not self._ceiling_valid():
                return 'speed ceiling {} is outside 0.00-{:.2f} m/s'.format(
                    self.ceiling_mps, self.ceiling_max_mps)
            if not self.permit:
                return 'equipment permit is FALSE'
            return 'permissive'

        def _step(self, now):
            """One evaluation of the gate law, and one output."""
            if self.t_last_step is None:
                dt = self.period_s
            else:
                dt = now - self.t_last_step
                # A clock that has not advanced (paused simulator) must
                # not produce a zero-length ramp step that reads as a
                # completed stop; a clock that jumped must not take the
                # whole jump out of the ramp in one go.
                if dt <= 0.0:
                    dt = 0.0
                elif dt > 10.0 * self.period_s:
                    dt = 10.0 * self.period_s
            self.t_last_step = now

            permissive = (self._envelope_fresh(now)
                          and self._mode_valid()
                          and self.mode_in_force == self.mode_autonomous
                          and self.enable
                          and self._ceiling_valid()
                          and self.permit)

            command_fresh = (self.t_cmd is not None
                             and (now - self.t_cmd) <= self.command_timeout_s)

            previous = self.state

            if permissive and command_fresh:
                v, w, clamped = clamp_to_ceiling(
                    self.cmd_v, self.cmd_w, self.ceiling_mps)
                if clamped:
                    self.clamps += 1
                    self.get_logger().info(
                        'clamped to the ceiling: commanded {:+.4f} m/s, '
                        'emitting {:+.4f} m/s at ceiling {:.4f}; the arc is '
                        'unchanged and the vehicle drives it slower'.format(
                            self.cmd_v, v, self.ceiling_mps),
                        throttle_duration_sec=self.throttle_s)
                self.out_v, self.out_w = v, w
                self.state = STATE_PASSING
            else:
                self.out_v, self.out_w = ramp_towards_zero(
                    self.out_v, self.out_w, self.stop_decel_mps2, dt,
                    self.zero_speed_mps)
                at_zero = (self.out_v == 0.0 and self.out_w == 0.0)
                if not at_zero:
                    self.state = STATE_STOPPING
                elif (self._fresh(self.t_mode, now)
                        and self.mode_in_force == self.mode_teleop
                        and self.zero_published):
                    # The PLC owns /forklift/cmd/* in Teleop. Release the
                    # topic rather than command a zero onto it.
                    #
                    # AND THE RELEASE IS ONE MESSAGE LATE BY CONSTRUCTION.
                    # `zero_published` is the guard: the gate falls silent
                    # only AFTER an explicit zero has gone out. Without it
                    # the last command on the wire is the final ramp step,
                    # which is small and nonzero, and forklift_io.py
                    # republishes its held command at 20 Hz forever - the
                    # first version of this node released at the ramp's
                    # last step and the vehicle crept at 0.0250 m/s for
                    # the whole silence, 0.0852 m in 3.3 s (measured,
                    # EVIDENCE_ENVELOPE.md section 9).
                    self.state = STATE_SILENT
                else:
                    self.state = STATE_HOLD_ZERO

            if previous == STATE_PASSING and self.state != STATE_PASSING:
                self.stops += 1
                self.get_logger().warn(
                    'GATE CLOSED after {} stop(s): {}. Ramping to zero at '
                    '{:.2f} m/s^2. This is a degraded mode, not a safety '
                    'function (invariant 2).'.format(
                        self.stops, self._reason(now), self.stop_decel_mps2))
            elif previous != STATE_PASSING and self.state == STATE_PASSING:
                self.get_logger().info(
                    'gate open: envelope fresh, mode Autonomous, enable '
                    'TRUE, permit TRUE, ceiling {:.3f} m/s'.format(
                        self.ceiling_mps))

            self._publish(now)

        def _publish(self, now):
            # mode applied follows the ADOPT WINDOW, not the request.
            if self.state == STATE_SILENT:
                applied = self.mode_teleop
            elif (self._fresh(self.t_mode, now)
                    and self.mode_in_force == self.mode_autonomous):
                applied = self.mode_autonomous
            elif self.state in (STATE_STOPPING,):
                # Still winding down the autonomous law it was applying.
                applied = self.mode_applied
            else:
                applied = self.mode_none
            self.mode_applied = applied

            msg = UInt16()
            msg.data = int(applied)
            self.pub_mode_applied.publish(msg)

            state = UInt16()
            state.data = int(self.state)
            self.pub_state.publish(state)

            if self.state == STATE_SILENT:
                # Publishing nothing IS the release. Logged once per
                # entry, not every cycle.
                if self.t_last_publish is not None:
                    self.get_logger().info(
                        'released /forklift/cmd/* to the teleop path: the '
                        'gate is at zero and the mode in force is Teleop, '
                        'so the PLC forms every setpoint (section 12.9 C1) '
                        'and this chain publishes nothing.')
                    self.t_last_publish = None
                return

            out = Twist()
            out.linear.x = float(self.out_v)
            out.angular.z = float(self.out_w)
            self.pub_cmd.publish(out)
            self.t_last_publish = now
            self.zero_published = (self.out_v == 0.0 and self.out_w == 0.0)

    return EnvelopeGate()


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)

    parser = argparse.ArgumentParser(
        description='The vehicle-side envelope gate (ADR 0014 seam (b)).')
    parser.add_argument('--config', default=_DEFAULT_CONFIG)
    parser.add_argument('--cmd-in', default=None,
                        help='Twist topic from the velocity smoother. '
                             'Default: config.yaml topics.cmd_vel_smoothed')
    parser.add_argument('--cmd-out', default=None,
                        help='Gated Twist topic the converter subscribes '
                             'to. Default: config.yaml topics.cmd_vel_gated')
    parser.add_argument('--self-check', action='store_true',
                        help='Run the arithmetic checks and exit. Needs no '
                             'ROS, no simulator and no envelope.')
    known, ros_args = parser.parse_known_args(argv)

    if known.self_check:
        return _self_check()

    cfg = load_config(known.config)
    cmd_in = known.cmd_in or cfg['topics']['cmd_vel_smoothed']
    cmd_out = known.cmd_out or cfg['topics']['cmd_vel_gated']

    import rclpy
    rclpy.init(args=[sys.argv[0]] + ros_args)
    node = _build_node(cfg, cmd_in, cmd_out)
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
