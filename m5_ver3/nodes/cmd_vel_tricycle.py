#!/usr/bin/env python3
"""cmd_vel_tricycle.py - the ROS shell around cmd_vel_tricycle_core.
Wiring only.

    python3 m5_ver3/nodes/cmd_vel_tricycle.py

m5v3.sh starts it as a stack child and it writes logs/navcmd.log; run it
by hand against a stack that is already up and it behaves the same.

WHAT IT DOES, AND IT IS ALL IT DOES. It subscribes the velocity
smoother's output, hands each twist to cmd_vel_tricycle_core, ramps the
answer at the plant's own actuator limits and publishes the pair onto
model.sdf's two motor terminals. Every decision that could be WRONG about
the conversion is in that file, where pytest reaches it without a
simulator; what is here is subscriptions, a clock, a ramp, message
assembly and refusals. It is nodes/wheel_odometry.py's shape, one layer
down the same split.

    /cmd_vel_smoothed  ->  /forklift/gz/actuator/steer_cmd     [rad]
    /speed_limit       ->  /forklift/gz/actuator/traction_cmd  [rad/s]
    /forklift/gz/joint_state (ONE message, at startup - see the seed)
                       ->  /m5v3/navcmd/status

THE TERMINALS ARE REACHED THROUGH THE BRIDGE AND NOT THROUGH gz. Those
two topic names are model.sdf's own and this node publishes
std_msgs/Float64 on the ROS side of them; m5v3.sh's parameter bridge
carries each to gz.msgs.Double in the ROS -> gz direction. That is why
the addresses in config.yaml need no second spelling: a terminal has one
name and the bridge maps it to itself.
  tools/drive_route.py AND tools/slip_bench.sh ADDRESS THE SAME TWO
  TERMINALS FROM THE GZ SIDE, and both are still correct. gz transport
  takes the last write, so the two must never be commanding at once -
  which is exactly why this node PUBLISHES NOTHING UNTIL IT IS ENGAGED.

=========================== ENGAGEMENT ===========================

An idle converter is a subscriber and nothing else. It publishes its
first message when its first command arrives, and it stops publishing
again once it has brought the vehicle to a standing zero after the
commands stop (config.yaml navcmd.disengage_ticks).

  IT IS NOT POLITENESS, IT IS THE PLANT. model.sdf's JointController
  holds its last order FOR EVER - measured in m6, a truck ran 14.8 m on
  one after its publisher died - so a stack child publishing zeros twenty
  times a second would overwrite every command the two gz-side benches
  put on the same terminals. Making the converter a `--nav`-gated child
  would have solved that too, and it would have cost the property this
  shape buys: the path EXISTS on every arm, so it can be verified open
  loop with no Nav2 anywhere, and F4 Task 2's `--nav` arm can assume it.

  THE STANDING ZERO IS STILL LEFT BEHIND. tools/drive_route.py's exit
  rule, for its reason: a silent terminal on this model is a standing
  ORDER, not an absence, and a standing zero is what pins the shaft. It
  is not a brake for a safety purpose and nothing here is a safety
  function - protective stop, e-stop and safe torque off are onboard and
  hardwired, and no message on any of these topics can trigger or release
  one.

============================== THE SEED ==============================

The steer ramp has to start FROM somewhere, and until the plant has said
where the axis is there is nothing to start from. So this node takes
exactly ONE message off the joint state, reads the steer joint's
position, seeds the limiter with it and THEN DESTROYS THE SUBSCRIPTION.
That channel runs at the world's own physics rate (about 493 Hz measured,
EVIDENCE_SENSORS.md 1.2) and this node needs one sample of it, ever.

  UNSEEDED, THE FIRST COMMAND IS ADOPTED RATHER THAN RAMPED FROM ZERO,
  and the log says so when it happens. Ramping from zero would assume a
  centred wheel, which nothing has claimed; and the plant's own 2.0 rad/s
  limit still applies to whatever this publishes, so the cost of the one
  unshaped tick is bounded by the axis and not by this file.

========================== THE CLOCK ==========================

use_sim_time, and the ramp is integrated on the PLANT's clock rather than
the machine's. A ramp measured against a wall clock would deliver a
different acceleration at every real-time factor, which is the difference
between a repeatable manoeuvre and one that has to be re-measured every
run - tools/drive_route.py's whole schedule is built on the same
argument.
  A LATE TICK RAMPS ONE NOMINAL PERIOD AND NEVER THE WHOLE GAP.
  agv/forklift/scripts/forklift_io.py's command cycle does the same
  (`step_s = min(elapsed, command_period_s)`) and for the same reason:
  under-travel is the conservative direction, and a paused world stamps
  the same instant twice.

WHY THE ROS IMPORTS ARE INSIDE main(). This track's pytest runs on the
owner's Windows python, where there is no rclpy, and the suite's conftest
puts this directory on sys.path - tests/test_smoother_params.py reads
this file, and tests/test_cmd_vel_tricycle_shell.py imports it. An rclpy
import at the top would stop the whole suite collecting on a machine that
can never fix it. nodes/wheel_odometry.py takes the ROS types as
arguments for the same reason and this file copies the shape.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in (_HERE, os.path.normpath(os.path.join(_HERE, os.pardir, "tools"))):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import _common                                        # noqa: E402
import cmd_vel_tricycle_core as core                   # noqa: E402

TOOL = "cmd_vel_tricycle"

# MAINTENANCE OBLIGATION: a key read below is a key listed here - AND THE
# CONVERSE. Refused by its DOTTED name before a single subscription is
# made, so a config.yaml that has been reorganised stops this node at
# startup rather than in the middle of a measured run.
REQUIRED_KEYS = (
    "topics.cmd_vel_smoothed", "topics.speed_limit", "topics.joint_state",
    "topics.steer_cmd", "topics.traction_cmd", "topics.navcmd_status",
    "vehicle.wheelbase_m", "vehicle.wheel_radius_m",
    "vehicle.rear_axle_offset_m",
    "vehicle.steer_limit_rad", "vehicle.steer_rate_limit_radps",
    "wheel_odom.steer_joint_name",
    "navcmd.rate_hz", "navcmd.speed_max_mps", "navcmd.accel_mps2",
    "navcmd.steer_command_limit_rad", "navcmd.creep_speed_mps",
    "navcmd.zero_speed_mps", "navcmd.yawrate_refusal_radps",
    "navcmd.command_timeout_s", "navcmd.disengage_ticks",
    "navcmd.qos_depth", "navcmd.status_every_s", "navcmd.log_throttle_s",
)


def joint_position(msg, name):
    """One joint's position out of a JointState, or None.

    None is not an error here: it is what the caller turns into a seed
    that never arrived, which is a different fact from a seed of zero.
    """
    try:
        index = list(msg.name).index(name)
    except ValueError:
        return None
    if index >= len(msg.position):
        return None
    value = msg.position[index]
    return value if math.isfinite(value) else None


def status_pairs(counters, limit_mps, engaged, steer_rad, wheel_mps):
    """The status message's body, as an ordered list of (key, value).

    PURE, so tests/test_cmd_vel_tricycle_shell.py can read what this node
    would say without a graph to say it on. The grammar is key=value
    because that is the grammar this track already reads state in -
    paths.traction_file, `status`, `sensor_evidence.py record`.
    """
    out = [("engaged", "true" if engaged else "false")]
    out.extend((name, str(counters[name])) for name in sorted(counters))
    out.append(("speed_limit_mps",
                "none" if limit_mps is None else "{:.6f}".format(limit_mps)))
    out.append(("steer_rad",
                "none" if steer_rad is None else "{:+.6f}".format(steer_rad)))
    out.append(("wheel_mps", "{:+.6f}".format(wheel_mps)))
    return out


def status_level(counters, DiagnosticStatus):
    """OK, or WARN with a reason - and the reason is a COUNTER.

    A REFUSAL IS THE LOUD ONE and a clamp is not. A nonzero refusal count
    means something upstream is commanding a differential base, which on
    this vehicle is a design error rather than a hard manoeuvre; nav2's
    Spin sends v = 0 exactly, which is why F4 Task 2's behaviour tree
    removes it and why this counter is the check that it stayed removed.
    A STEER CLAMP IS THE OTHER ONE, because the curvature ceiling stands
    inside the mechanical stop: a twist clamped at the ceiling can never
    reach the stop, so a steer clamp on this stack is a bug and not a
    manoeuvre.
    """
    if counters["refusals"] or counters["steer_clamps"]:
        return DiagnosticStatus.WARN
    return DiagnosticStatus.OK


def _make_node_class(Node, Twist, Float64, JointState, SpeedLimit,
                     DiagnosticStatus, KeyValue, QoSProfile):
    """Build the node class once the ROS types are in hand.

    The types are arguments rather than module-level imports so that this
    file can be read, linted and imported by a suite that has no rclpy.
    """

    class CmdVelTricycleNode(Node):

        def __init__(self, cfg):
            super().__init__("m5v3_cmd_vel_tricycle")
            self.cfg = cfg
            self.wheelbase_m = cfg.f("vehicle.wheelbase_m")
            # d, the distance base_link stands FORWARD of the rear axle.
            # config.yaml records the rear axle's x IN base_link (-0.50),
            # so the sign flips here and once only - which is
            # wheel_odom_core.__init__'s own line, one layer down. It is
            # not in the conversion at all (the header says why); it is
            # here so a lateral term can be REPORTED against the value it
            # almost certainly is.
            self.base_offset_m = -cfg.f("vehicle.rear_axle_offset_m")
            self.wheel_radius_m = cfg.f("vehicle.wheel_radius_m")
            self.steer_limit_rad = cfg.f("vehicle.steer_limit_rad")
            self.steer_command_limit_rad = cfg.f(
                "navcmd.steer_command_limit_rad")
            # ONE PLACE FOR THE CURVATURE, and it is the core's. Three
            # consumers want tan(1.25)/1.05 and a second spelling of it
            # is a second opinion about the plant's tightest arc.
            self.curvature_max_1pm = core.curvature_max(
                self.steer_command_limit_rad, self.wheelbase_m)
            self.speed_max_mps = cfg.f("navcmd.speed_max_mps")
            self.creep_speed_mps = cfg.f("navcmd.creep_speed_mps")
            self.zero_speed_mps = cfg.f("navcmd.zero_speed_mps")
            self.yawrate_refusal_radps = cfg.f("navcmd.yawrate_refusal_radps")
            self.rate_hz = cfg.f("navcmd.rate_hz")
            self.period_s = 1.0 / self.rate_hz
            self.command_timeout_s = cfg.f("navcmd.command_timeout_s")
            self.disengage_ticks = cfg.i("navcmd.disengage_ticks")
            self.throttle_s = cfg.f("navcmd.log_throttle_s")
            self.steer_joint = cfg.s("wheel_odom.steer_joint_name")

            self.limiter = core.CommandLimiter(
                steer_rate_limit_radps=cfg.f("vehicle.steer_rate_limit_radps"),
                traction_accel_mps2=cfg.f("navcmd.accel_mps2"))

            self._engaged = False
            self._cmd = None                 # the last (v, w) heard
            self._cmd_t = None               # ...and when, on the plant's clock
            self._tick_t = None
            self._zero_ticks = 0
            self._limit_mps = None
            self._seeded = False
            self._warned_unseeded = False
            self.counters = dict(
                commands=0, published=0, engagements=0, timeouts=0,
                curvature_clamps=0, steer_clamps=0, traction_clamps=0,
                refusals=0, declines=0, speed_limits=0, not_finite=0,
                lateral_terms=0)

            qos = QoSProfile(depth=cfg.i("navcmd.qos_depth"))
            self.pub_steer = self.create_publisher(
                Float64, cfg.s("topics.steer_cmd"), qos)
            self.pub_traction = self.create_publisher(
                Float64, cfg.s("topics.traction_cmd"), qos)
            self.pub_status = self.create_publisher(
                DiagnosticStatus, cfg.s("topics.navcmd_status"), qos)

            self.create_subscription(
                Twist, cfg.s("topics.cmd_vel_smoothed"), self.cb_cmd_vel, qos)
            self.create_subscription(
                SpeedLimit, cfg.s("topics.speed_limit"),
                self.cb_speed_limit, qos)
            # THE SEED, AND IT IS DESTROYED AFTER ONE MESSAGE. See the
            # header: this node needs one sample of a 493 Hz channel,
            # ever, and paying for the rest of it would be a subscription
            # that costs the RTF every figure on this track is measured
            # against.
            self._seed_sub = self.create_subscription(
                JointState, cfg.s("topics.joint_state"), self.cb_seed, qos)

            self._DiagnosticStatus = DiagnosticStatus
            self._KeyValue = KeyValue
            self._Float64 = Float64

            self.create_timer(self.period_s, self.cb_tick)
            self.create_timer(cfg.f("navcmd.status_every_s"), self.cb_status)

            self.get_logger().info(
                "cmd_vel tricycle converter up: {} -> ({}, {}); L {:.3f} m, "
                "r {:.4f} m".format(
                    cfg.s("topics.cmd_vel_smoothed"), cfg.s("topics.steer_cmd"),
                    cfg.s("topics.traction_cmd"), self.wheelbase_m,
                    self.wheel_radius_m))
            self.get_logger().info(
                "limits: tread |v_w| <= {:.3f} m/s, accel {:.3f} m/s^2, "
                "steer |d| <= {:.4f} rad COMMANDED ({:.4f} rad mechanical), "
                "curvature |k| <= {:.6f} 1/m (R {:.4f} m), steer slew "
                "{:.3f} rad/s".format(
                    self.speed_max_mps, cfg.f("navcmd.accel_mps2"),
                    self.steer_command_limit_rad, self.steer_limit_rad,
                    self.curvature_max_1pm, 1.0 / self.curvature_max_1pm,
                    self.limiter.steer_rate_limit_radps))
            self.get_logger().info(
                "SIGNS: forward travel is a NEGATIVE linear.x, a NEGATIVE "
                "tread and a NEGATIVE wheel rate; positive steer is "
                "driver-right, which in base_link is a NEGATIVE angular.z. "
                "nodes/wheel_odom_core.py's header owns all three.")
            self.get_logger().info(
                "IDLE UNTIL COMMANDED: nothing is published on either "
                "terminal until a twist arrives, so tools/drive_route.py "
                "and tools/slip_bench.sh keep the gz side to themselves.")
            self.get_logger().info(
                "{} is a DEMONSTRATED INTERFACE and not a safety claim. "
                "Nothing on this path inhibits motion or latches a fault."
                .format(cfg.s("topics.speed_limit")))

        # -------------------------------------------------------------
        # Callbacks are named cb_* so none of them can shadow an rclpy
        # Node attribute (docs/LESSONS.md 2026-07-27).
        # -------------------------------------------------------------

        def now_s(self):
            """The PLANT's clock, in seconds. See the header."""
            return self.get_clock().now().nanoseconds * 1e-9

        def cb_seed(self, msg):
            if self._seeded:
                return
            position = joint_position(msg, self.steer_joint)
            if position is None:
                return
            self.limiter.steer_rad = float(position)
            self._seeded = True
            self.get_logger().info(
                "steer axis seeded at {:+.6f} rad from {}; the joint-state "
                "subscription is closed - one sample was all it was for."
                .format(position, self.cfg.s("topics.joint_state")))
            # DESTROYED AND NOT LEFT SPINNING. It is a ~493 Hz channel.
            self.destroy_subscription(self._seed_sub)
            self._seed_sub = None

        def cb_speed_limit(self, msg):
            limit = core.speed_limit_mps(
                bool(msg.percentage), msg.speed_limit, self.speed_max_mps)
            if limit == self._limit_mps:
                return
            self._limit_mps = limit
            self.counters["speed_limits"] += 1
            self.get_logger().info(
                "SPEED LIMIT {} on {} (percentage={}, value={:.4f}). It is "
                "applied to the WHOLE twist, so the arc is unchanged and "
                "the vehicle drives it slower. This is a demonstrated "
                "interface, not a safety function.".format(
                    "LIFTED - no limit" if limit is None
                    else "{:.4f} m/s".format(limit),
                    self.cfg.s("topics.speed_limit"),
                    bool(msg.percentage), msg.speed_limit))

        def cb_cmd_vel(self, msg):
            self.counters["commands"] += 1
            if abs(msg.linear.y) > 0.0:
                # A LATERAL TERM IS DISCARDED AND REPORTED WITH ITS
                # RESIDUAL, and the residual is the whole of the message.
                # base_link stands d = 0.50 m FORWARD of the rear axle, so
                # this vehicle genuinely HAS a lateral velocity of
                # d * yaw_rate whenever it turns - it is the term
                # nodes/wheel_odom_core.py publishes and the EKF fuses,
                # and a CLOSED_LOOP smoother COPIES IT THROUGH from the
                # estimate (measured on this rig 2026-08-27, in isolation
                # on domain 99: with that feedback and a zero
                # acceleration limit on the lateral axis, a measured vy
                # of 0.0200 m/s comes out as 0.0200 m/s whatever is
                # commanded). smoother.yaml ships OPEN_LOOP, so on
                # today's stack the term can only have been PUT there -
                # which is what makes the residual below the right thing
                # to print and the wrong thing to threshold.
                #   SO A WARNING WOULD BE WRONG ABOUT ITS OWN SUBJECT.
                #   The crib warns here because "something upstream
                #   believes this base is holonomic"; on THIS chain the
                #   commonest cause is the vehicle turning. What
                #   distinguishes the two is the RESIDUAL against
                #   d * angular.z, which is printed rather than
                #   thresholded - a threshold here would need a number
                #   nothing has measured.
                self.counters["lateral_terms"] += 1
                self.get_logger().info(
                    "cmd_vel carries linear.y = {:+.4f} m/s. This vehicle "
                    "has no lateral degree of freedom and the CONVERSION "
                    "discards it; d*angular.z is {:+.4f} m/s, so the "
                    "residual is {:+.4f} m/s. A residual near zero is the "
                    "vehicle turning (base_link stands {:+.2f} m from the "
                    "rear axle); a large one is something upstream that "
                    "believes this base is holonomic.".format(
                        msg.linear.y, self.base_offset_m * msg.angular.z,
                        msg.linear.y - self.base_offset_m * msg.angular.z,
                        self.base_offset_m),
                    throttle_duration_sec=self.throttle_s)
            self._cmd = (msg.linear.x, msg.angular.z)
            self._cmd_t = self.now_s()
            if not self._engaged:
                self._engaged = True
                self._zero_ticks = 0
                self._tick_t = None
                self.counters["engagements"] += 1
                if not self._seeded and not self._warned_unseeded:
                    self._warned_unseeded = True
                    self.get_logger().warn(
                        "ENGAGED WITH NO SEED: nothing has arrived on {} "
                        "carrying joint '{}', so the first steer command "
                        "is ADOPTED rather than ramped - there is no held "
                        "angle to ramp from. The plant's own {:.1f} rad/s "
                        "axis limit still applies to it.".format(
                            self.cfg.s("topics.joint_state"),
                            self.steer_joint,
                            self.limiter.steer_rate_limit_radps))
                self.get_logger().info(
                    "ENGAGED on a command from {}: this node is now "
                    "publishing to {} and {}.".format(
                        self.cfg.s("topics.cmd_vel_smoothed"),
                        self.cfg.s("topics.steer_cmd"),
                        self.cfg.s("topics.traction_cmd")))

        def cb_tick(self):
            if not self._engaged:
                return
            now = self.now_s()
            # A LATE TICK RAMPS ONE NOMINAL PERIOD AND NEVER THE WHOLE
            # GAP - forklift_io.py's command cycle, for its reason.
            elapsed = self.period_s if self._tick_t is None \
                else now - self._tick_t
            self._tick_t = now
            dt_s = min(max(elapsed, 0.0), self.period_s)

            timed_out = (self._cmd_t is None
                         or now - self._cmd_t > self.command_timeout_s)
            if timed_out:
                if self._cmd is not None:
                    self.counters["timeouts"] += 1
                    self.get_logger().warn(
                        "no command on {} for {:.3f} s of plant time: "
                        "ramping the traction to a standing zero at "
                        "{:.3f} m/s^2 and HOLDING the steer axis. The "
                        "smoother's own dead-man is longer than this one."
                        .format(self.cfg.s("topics.cmd_vel_smoothed"),
                                now - (self._cmd_t or now),
                                self.limiter.traction_accel_mps2),
                        throttle_duration_sec=self.throttle_s)
                    self._cmd = None
                target_steer, target_wheel = None, 0.0
            else:
                target_steer, target_wheel = self.convert(*self._cmd)

            steer, wheel = self.limiter.step(dt_s, target_steer, target_wheel)
            self.publish(steer, wheel)

            if timed_out and wheel == 0.0:
                self._zero_ticks += 1
                if self._zero_ticks >= self.disengage_ticks:
                    self._engaged = False
                    self._zero_ticks = 0
                    self.get_logger().info(
                        "DISENGAGED: the traction terminal is left at a "
                        "standing zero and the steer axis at {:+.6f} rad. "
                        "Nothing more is published until a command "
                        "arrives, so the gz-side benches have the "
                        "terminals back.".format(
                            steer if steer is not None else float("nan")))
            else:
                self._zero_ticks = 0

        def convert(self, v, w):
            """One twist, limited and converted. Counters live here."""
            v, w = core.apply_speed_limit(v, w, self._limit_mps)
            out = core.twist_to_tricycle(
                v, w, wheelbase_m=self.wheelbase_m,
                steer_limit_rad=self.steer_limit_rad,
                curvature_max_1pm=self.curvature_max_1pm,
                traction_max_mps=self.speed_max_mps,
                creep_speed_mps=self.creep_speed_mps,
                zero_speed_mps=self.zero_speed_mps,
                yawrate_refusal_radps=self.yawrate_refusal_radps)
            if out.refused:
                if "not finite" in out.reason:
                    self.counters["not_finite"] += 1
                else:
                    self.counters["refusals"] += 1
                self.get_logger().warn(
                    "COMMAND REFUSED: {}. Commanding zero traction and "
                    "HOLDING the steer axis - re-centring would be a "
                    "motion nobody asked for. refusals={}".format(
                        out.reason, self.counters["refusals"]),
                    throttle_duration_sec=self.throttle_s)
            elif out.steer_rad is None:
                self.counters["declines"] += 1
                self.get_logger().info(
                    "{} This is NOT a refusal - the request was "
                    "executable and the vehicle was {:.0f} mm/s from "
                    "rest.".format(out.reason, 1000.0 * abs(v)),
                    throttle_duration_sec=self.throttle_s)
            if out.curvature_clamped:
                # NOT curvature preserving: say so, with both curvatures.
                self.counters["curvature_clamps"] += 1
                self.get_logger().warn(
                    "CURVATURE CLAMPED: {}. The measured ceiling is "
                    "{:.6f} 1/m (steer {:.4f} rad, the hardest this plant "
                    "has been driven at). clamps={}".format(
                        out.reason, self.curvature_max_1pm,
                        self.steer_command_limit_rad,
                        self.counters["curvature_clamps"]),
                    throttle_duration_sec=self.throttle_s)
            if out.steer_clamped:
                # THE BACKSTOP FIRED, which on this stack cannot happen
                # from a twist: the measured ceiling stands inside the
                # mechanical stop. So this is a bug report, not a note.
                self.counters["steer_clamps"] += 1
                self.get_logger().warn(
                    "MECHANICAL STEER STOP REACHED at {:+.4f} rad. The "
                    "commanded ceiling ({:.4f} rad) stands INSIDE it, so "
                    "a twist cannot get here - check "
                    "navcmd.steer_command_limit_rad against "
                    "vehicle.steer_limit_rad.".format(
                        out.steer_rad, self.steer_command_limit_rad),
                    throttle_duration_sec=self.throttle_s)
            if out.traction_clamped:
                # Curvature preserving, so this is information and not a
                # warning: the vehicle drives the same arc more slowly.
                self.counters["traction_clamps"] += 1
                self.get_logger().info(
                    "{}. clamps={}".format(
                        out.reason, self.counters["traction_clamps"]),
                    throttle_duration_sec=self.throttle_s)
            return out.steer_rad, out.wheel_mps

        def publish(self, steer_rad, wheel_mps):
            """THE STEER GOES FIRST AND THEN THE TRACTION, every time.

            tools/drive_route.py's rule and its reason: the other order
            would run the truck at the new speed on the old steer angle
            for as long as the second publish takes, which on a corner is
            the difference between an arc and a corner cut.
            """
            if steer_rad is not None:
                msg = self._Float64()
                msg.data = float(steer_rad)
                self.pub_steer.publish(msg)
            msg = self._Float64()
            # THE TRUE RADIUS, because this is a command to the PLANT.
            msg.data = core.wheel_rate_radps(wheel_mps, self.wheel_radius_m)
            self.pub_traction.publish(msg)
            self.counters["published"] += 1

        def cb_status(self):
            """The counters, on the wire, engaged or not.

            IT IS A HEARTBEAT AS WELL AS A DIAGNOSTIC. A converter that is
            ALIVE and has never heard a command looks exactly like one
            whose subscription is misspelt, and `status` cannot tell them
            apart - this can, and tools/navcmd_health.py reads it at
            bringup for exactly that reason.
            """
            msg = self._DiagnosticStatus()
            msg.name = "m5v3_cmd_vel_tricycle"
            msg.hardware_id = self.cfg.s("topics.traction_cmd")
            msg.level = status_level(self.counters, self._DiagnosticStatus)
            msg.message = (
                "engaged" if self._engaged else "idle - nothing published")
            msg.values = [
                self._KeyValue(key=key, value=value)
                for key, value in status_pairs(
                    self.counters, self._limit_mps, self._engaged,
                    self.limiter.steer_rad, self.limiter.wheel_mps)]
            self.pub_status.publish(msg)

    return CmdVelTricycleNode


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    try:
        import rclpy
        from diagnostic_msgs.msg import DiagnosticStatus, KeyValue
        from geometry_msgs.msg import Twist
        from nav2_msgs.msg import SpeedLimit
        from rclpy.executors import ExternalShutdownException
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from sensor_msgs.msg import JointState
        from std_msgs.msg import Float64
    except ImportError as exc:
        _common.refuse(
            TOOL, "rclpy and nav2_msgs are importable",
            _common.CONFIG + " (paths.ros_setup)",
            "python3 could not import what this node needs: {}".format(exc),
            "this node runs INSIDE WSL with /opt/ros/jazzy sourced -",
            "m5v3.sh sources it before it spawns this child. nav2_msgs is",
            "where nav2_msgs/SpeedLimit lives and it ships with the nav2",
            "family; without it the envelope hook has no message type.",
            "See CONTEXT.md - this stack lives inside WSL.")

    rclpy.init(args=argv)
    node_class = _make_node_class(Node, Twist, Float64, JointState, SpeedLimit,
                                  DiagnosticStatus, KeyValue, QoSProfile)
    node = node_class(cfg)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # SIGTERM is how this node is normally ended - m5v3.sh's stop
        # sweeps it with TERM and rclpy raises that out of spin(). An
        # operator's Ctrl-C is the same event under another name, so the
        # two are caught together and neither is an error.
        pass
    finally:
        node.get_logger().info(
            "cmd_vel tricycle converter down: {}".format(
                ", ".join("{} {}".format(v, k)
                          for k, v in sorted(node.counters.items()))))
        # WHAT THIS NODE DOES NOT DO ON THE WAY OUT: publish a standing
        # zero. If it was ENGAGED it has already been ramping to one and
        # a final unramped zero would be a step; if it was IDLE the
        # terminals belong to whatever else is driving them, and stamping
        # a zero on somebody else's command is exactly the collision the
        # engagement rule exists to prevent. `m5v3.sh stop` ends the
        # simulator, which is the only stop this stack owns.
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
