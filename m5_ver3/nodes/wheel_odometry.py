#!/usr/bin/env python3
"""wheel_odometry.py - the ROS shell around wheel_odom_core. Wiring only.

    python3 m5_ver3/nodes/wheel_odometry.py

m5v3.sh starts it as a stack child and it writes logs/odom.log; run it by
hand against a stack that is already up and it behaves the same.

WHAT IT DOES, AND IT IS ALL IT DOES. It subscribes the drive shaft's
reading channel A and the plant's joint state, hands both to
wheel_odom_core one sample at a time, and publishes what comes back as one
nav_msgs/Odometry. Every decision that could be wrong about the estimate
is in that file, where pytest can reach it without a simulator; what is
here is subscriptions, unit plumbing, message assembly and refusals.

    /forklift/gz/drive_speed/read_a  ->  /m5v3/wheel_odom
    /forklift/gz/joint_state         ->

THE DRIVE CHANNEL IS THE CLOCK AND THE STEER IS A HELD VALUE. read_a is
what an encoder-driven odometry ticks on, so the core runs once per
message on it and the newest steer angle is used as it stands. Both
topics are published once per physics iteration, so "newest" is at worst
one step old.
  A STALE STEER SKIPS THE SAMPLE RATHER THAN INTEGRATING AGAINST IT, and
  skipping is FREE IN DISTANCE. The count grid is absolute, so the next
  accepted sample differences against the last accepted one and the
  travel in between is still there; what a skip costs is resolution in
  time, which is the honest thing for it to cost.

IT PUBLISHES ON EVERY INPUT SAMPLE. That is roughly 493 Hz of wall clock
against this world's 500 Hz step, and it is deliberate: a quantiser that
skips samples is a different device, and the POSE does not care about the
rate anyway because the grid is absolute and quantisation therefore does
not accumulate in position. What it costs is the TWIST - at 2 ms the
velocity is 22 % quantiser dither, and config.yaml's covariance.vx
comment carries that arithmetic and the number F2 needs if its EKF cannot
live with it. The node does not hide the cost; it publishes it.

TWO HEARTBEATS, AND THE SECOND EXISTS BECAUSE THE FIRST CANNOT REACH THE
FAILURE IT WAS WRITTEN FOR. heartbeat() rides the OUTPUT - it is called
after publish(), on the plant's own clock, and it is what makes
logs/odom.log readable as a run rather than as a banner. But the state an
operator most needs this log for is an estimator that is ALIVE and
publishing NOTHING: a dead steer topic leaves the held angle at None and
every drive sample is skipped for ever, and on that path publish() is
never reached, so the one line that would have said so never prints.
alive() is the second heartbeat and it is a TIMER, on the MACHINE's own
monotonic clock and not the plant's, so it ticks whether or not there is
a world running. It says nothing while the publish count is moving. When
the count stops it prints the counters and NAMES THE REASON - nothing on
either input, a joint state that carries no position for the steer joint,
no steer reading accepted yet, or a steer reading too old to integrate
against - and escalates from info to warn once the silence has lasted
longer than a bringup takes.
  ITS WARN STREAM IS BOUNDED IN TOTAL AND NOT ONLY IN RATE. A watchdog
  that prints one line every 5 s for ever writes 17 280 identical lines
  into a log an operator will open once, and the line they need - the
  FIRST one, with the reason in it - is then the hardest one in the file
  to find. So the full cadence is capped (alive_warn_max) and what
  follows is one line per alive_warn_backoff_s. It never goes silent:
  a watchdog that stops printing makes its last line's timestamp look
  like the moment the fault ended. alive_tick() below is that decision,
  as a function of six numbers, and tests/test_wheel_odometry_shell.py
  is where it is checked - because the state it decides in is a state no
  test can put a live node into.

IT NEVER SUBSCRIBES THE GROUND TRUTH, and that is a rule and not an
oversight. /forklift/gz/odom is the simulator's own pose - no slip, no
quantisation, no drift - and on this track it is an INSTRUMENT that this
estimate is scored AGAINST. An estimator that reads ground truth is not an
estimator, and the cheapest way to guarantee this one cannot is for the
file to contain no subscription to it. It does not.

IT BROADCASTS NO TRANSFORM. odom -> base_link has exactly one owner, and
since F2 Task 1 that owner EXISTS: robot_localization's ekf_node, started
by m5v3.sh as the child named `ekf`, which fuses this node's twist with
the IMU. A second publisher of that edge is the failure the whole
two-phase odometry plan exists to prevent (ver2 invariant 10), so this
file contains no transform broadcaster at all - and the frame NAMES it
stamps on its messages now live in config.yaml's frames: block, where the
filter reads the same two strings.

WHAT IT IS NOT. Not the vehicle's pose - one sensor's opinion of it,
published so F2's filter can fuse it with the IMU. Not a safety function
and not a real-time controller: a late callback here degrades an estimate,
inhibits nothing and latches nothing.

WHY THE ROS IMPORTS ARE INSIDE main(). This track's pytest runs on the
owner's Windows python, where there is no rclpy, and the suite's conftest
puts this directory on sys.path. Since F2 Task 1 the suite DOES import
this module - tests/test_wheel_odometry_shell.py exercises the pure
helpers below, alive_tick() first among them - so the property is no
longer theoretical: an rclpy import at the top of this file stops the
whole suite collecting, on a machine that can never fix it. agv/forklift/scripts/safe_speed_channels.py
takes the ROS types as arguments for the same reason and this file copies
the shape.
"""
import collections
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in (_HERE, os.path.normpath(os.path.join(_HERE, os.pardir, "tools"))):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import _common                                        # noqa: E402
import wheel_odom_core                                # noqa: E402

TOOL = "wheel_odometry"

# MAINTENANCE OBLIGATION: a key read below is a key listed here. Refused
# by its DOTTED name before a single subscription is made, so a
# config.yaml that has been reorganised stops the node at startup instead
# of in the middle of a measured run.
REQUIRED_KEYS = (
    "topics.drive_speed_read_a", "topics.joint_state", "topics.wheel_odom",
    "vehicle.wheelbase_m", "vehicle.wheel_radius_m",
    "vehicle.rear_axle_offset_m",
    "wheel_odom.counts_per_rev", "wheel_odom.wheel_radius_scale",
    "wheel_odom.steer_bias_rad",
    "wheel_odom.drive_joint_name", "wheel_odom.steer_joint_name",
    "frames.odom", "frames.base_link",
    "wheel_odom.qos_depth", "wheel_odom.steer_stale_s",
    "wheel_odom.log_every_s",
    "wheel_odom.alive_every_s", "wheel_odom.alive_warn_after_s",
    "wheel_odom.alive_warn_max", "wheel_odom.alive_warn_backoff_s",
    "wheel_odom.covariance.vx", "wheel_odom.covariance.vy",
    "wheel_odom.covariance.vyaw", "wheel_odom.covariance.unused",
)


def stamp_to_s(stamp):
    """A builtin_interfaces/Time as seconds. Sim time, because /clock is
    bridged and the plant stamps these messages from it."""
    return float(stamp.sec) + float(stamp.nanosec) * 1e-9


def joint_index(msg, name):
    """Where `name` sits in a JointState, or None.

    None is not an error here - it is what the caller turns into ONE
    refusal with the message's own name list in it. A node that silently
    read index 0 instead would produce a plausible odometry of the wrong
    joint.
    """
    try:
        return list(msg.name).index(name)
    except ValueError:
        return None


def covariance_diagonal(diagonal):
    """A row-major 6x6 covariance from its six diagonal entries.

    ROS's axis order is (x, y, z, roll, pitch, yaw). Everything off the
    diagonal is zero, which is a claim in itself and config.yaml's
    covariance: block is where it is argued.
    """
    out = [0.0] * 36
    for i, value in enumerate(diagonal):
        out[i * 6 + i] = float(value)
    return out


#: What one tick of the watchdog does: whether it speaks at all, at which
#: level, and whether the line it speaks is a BACKED-OFF one (which the
#: line says out loud, so a reader knows there were suppressed ticks
#: between it and the one before).
AliveTick = collections.namedtuple("AliveTick", "speak level backed_off")


def alive_tick(silent_s, warn_after_s, warns, warn_max, backoff_s,
               last_warn_s):
    """One watchdog tick, decided. Pure - no clock, no logger, no node.

    THE SHAPE, AND THE ARGUMENT FOR IT. The failure this watchdog exists
    for - a node ALIVE and publishing nothing - does not clear itself,
    so its output is a stream with no end. Three regimes, and each is
    answering a different reader:

      silence < warn_after_s        INFO, every tick. A stack coming up
                                    is silent, and a fault called on a
                                    normal bringup teaches the operator
                                    to ignore the line (m6's escalation
                                    rule). Bounded by warn_after_s
                                    itself: three ticks, not a stream.
      the next warn_max ticks       WARN, every tick. This is the minute
                                    an operator is actually reading the
                                    log - `m5v3.sh status` said ALIVE
                                    and they opened odom.log - and
                                    nothing in it may be throttled.
      after that                    WARN, one line per backoff_s. The
                                    reason has been stated warn_max
                                    times by now; what is left to say is
                                    "still", and "still" is worth one
                                    line every few minutes.

    IT NEVER FALLS SILENT, and that is the one thing a cap must not do.
    A log that stops has a last line whose timestamp reads like the
    moment the fault ended, and the next reader dates the failure from
    it. The backoff keeps the statement current at 12 lines an hour
    against 720.

    last_warn_s is the silent_s AT WHICH THE LAST WARN WAS SPOKEN, on
    the same clock as silent_s, or None if none has been. Measuring the
    interval against the line that reached the log - and not against the
    tick that was suppressed, nor against the cap - is what makes the
    output exactly one line per backoff_s for as long as it lasts.
    """
    if silent_s < warn_after_s:
        return AliveTick(speak=True, level="info", backed_off=False)
    if warns < warn_max:
        return AliveTick(speak=True, level="warn", backed_off=False)
    if last_warn_s is None or silent_s - last_warn_s >= backoff_s:
        return AliveTick(speak=True, level="warn", backed_off=True)
    return AliveTick(speak=False, level="warn", backed_off=True)


def seconds_to_stamp(Time, t_s):
    """Seconds as a builtin_interfaces/Time.

    THE OUTPUT CARRIES THE INPUT'S OWN STAMP, never the node's wall
    clock: the estimate is a statement about the instant the shaft was
    read, and re-stamping it on publication would hand F2's filter a
    measurement dated when python got round to it.
    """
    out = Time()
    whole = math.floor(t_s)
    out.sec = int(whole)
    out.nanosec = int(round((t_s - whole) * 1e9))
    if out.nanosec >= 1000000000:      # a stamp that rounded up to the
        out.sec += 1                   # next second is that second
        out.nanosec -= 1000000000
    return out


def _make_node_class(Node, JointState, Odometry, QoSProfile, Time, Clock,
                     ClockType):
    """Build the node class once the ROS types are in hand.

    The types are arguments rather than module-level imports so that this
    file can be read, linted and put on sys.path by a suite that has no
    rclpy - see the header.
    """

    class WheelOdometryNode(Node):

        def __init__(self, cfg):
            super().__init__("m5v3_wheel_odometry")
            self.cfg = cfg
            self.core = wheel_odom_core.WheelOdometry(
                wheelbase_m=cfg.f("vehicle.wheelbase_m"),
                wheel_radius_m=cfg.f("vehicle.wheel_radius_m"),
                rear_axle_offset_m=cfg.f("vehicle.rear_axle_offset_m"),
                counts_per_rev=cfg.i("wheel_odom.counts_per_rev"),
                wheel_radius_scale=cfg.f("wheel_odom.wheel_radius_scale"),
                steer_bias_rad=cfg.f("wheel_odom.steer_bias_rad"))
            self.drive_joint = cfg.s("wheel_odom.drive_joint_name")
            self.steer_joint = cfg.s("wheel_odom.steer_joint_name")
            # THE FRAME NAMES ARE frames:'s AND NOT THIS BLOCK'S SINCE
            # F2. They were this node's alone while nothing on the track
            # broadcast a transform; the EKF now stamps the same two
            # names on odom -> base_link, and one name with two writers
            # is one place for it to live.
            self.odom_frame = cfg.s("frames.odom")
            self.base_frame = cfg.s("frames.base_link")
            self.steer_stale_s = cfg.f("wheel_odom.steer_stale_s")
            self.log_every_s = cfg.f("wheel_odom.log_every_s")
            self.alive_every_s = cfg.f("wheel_odom.alive_every_s")
            self.alive_warn_after_s = cfg.f("wheel_odom.alive_warn_after_s")
            self.alive_warn_max = cfg.i("wheel_odom.alive_warn_max")
            self.alive_warn_backoff_s = cfg.f(
                "wheel_odom.alive_warn_backoff_s")

            self._Time = Time
            unused = cfg.f("wheel_odom.covariance.unused")
            # The pose is unused in all six axes, on purpose: a
            # dead-reckoned pose has unbounded error and no fixed number
            # is honest for it. config.yaml says so where the value is.
            self._pose_cov = covariance_diagonal([unused] * 6)
            self._twist_cov = covariance_diagonal([
                cfg.f("wheel_odom.covariance.vx"),
                cfg.f("wheel_odom.covariance.vy"),
                unused, unused, unused,
                cfg.f("wheel_odom.covariance.vyaw")])

            self._steer_rad = None
            self._steer_t = None
            self._published = 0
            self._skipped_stale = 0
            self._skipped_no_steer = 0
            self._last_log_t = None
            # THE ARRIVAL COUNTERS, and they are not the skip counters.
            # A skip counter can only rise once a message has arrived, so
            # on a dead topic every one of them stays at zero and says
            # the same nothing as a node that was never started. These
            # three separate "no message" from "a message this node could
            # not use", which is the whole of what alive() has to tell an
            # operator apart.
            self._drive_msgs = 0
            self._steer_msgs = 0
            self._steer_no_position = 0
            # alive()'s own state, on the machine's clock. _alive_t is
            # the last instant the OUTPUT was seen moving, and it starts
            # at construction so the first silence is measured from a
            # real moment rather than from zero.
            self._alive_published = 0
            self._alive_t = time.monotonic()
            # The warn stream's own state, and it is reset with _alive_t:
            # a silence that ends and a NEW one that begins are two
            # faults, and the second one gets its full cadence back.
            self._alive_warns = 0
            self._alive_last_warn_s = None
            self._alive_suppressed = 0

            qos = QoSProfile(depth=cfg.i("wheel_odom.qos_depth"))
            self.pub = self.create_publisher(
                Odometry, cfg.s("topics.wheel_odom"), qos)
            self.create_subscription(
                JointState, cfg.s("topics.joint_state"), self.cb_steer, qos)
            # LAST, so the drive channel cannot tick before the steer
            # subscription exists and spend the first samples counting
            # itself as steer-less.
            self.create_subscription(
                JointState, cfg.s("topics.drive_speed_read_a"),
                self.cb_drive, qos)

            self.get_logger().info(
                "wheel odometry up: L {:.3f} m, r {:.4f} m believed "
                "({:.3f} m x {:.4f}), {} counts/rev, steer bias "
                "{:+.4f} rad".format(
                    self.core.wheelbase_m, self.core.odom_radius_m,
                    cfg.f("vehicle.wheel_radius_m"),
                    cfg.f("wheel_odom.wheel_radius_scale"),
                    self.core.encoder.counts_per_rev,
                    self.core.steer_bias_rad))
            self.get_logger().info(
                "drive {} on {} | steer {} on {} | out {} ({} -> {})".format(
                    self.drive_joint, cfg.s("topics.drive_speed_read_a"),
                    self.steer_joint, cfg.s("topics.joint_state"),
                    cfg.s("topics.wheel_odom"),
                    self.odom_frame, self.base_frame))
            # THE ONE CLOCK IN THIS FILE THAT IS NOT THE PLANT'S, and
            # that is the point of it: a timer on sim time stops when the
            # world stops, and a world that has stopped is one of the
            # states this timer exists to report. It is passed EXPLICITLY
            # rather than left to the node's default, because that
            # default follows a use_sim_time parameter which anything on
            # the graph may set.
            #   STEADY_TIME AND NOT SYSTEM_TIME, corrected 2026-08-26.
            #   This line read `Clock()`, which is SYSTEM_TIME, while
            #   every comment around it - and the docstring of alive()
            #   itself - promised the machine's own MONOTONIC clock. The
            #   two differ exactly when it matters: WSL's wall clock is
            #   stepped by the host on resume and by NTP, and a watchdog
            #   whose cadence is a settable clock can fire a hundred
            #   ticks at once or none for an hour, on a stack that has
            #   done nothing. silent_s below is time.monotonic() and
            #   always was; this makes the TIMER agree with it.
            self.create_timer(
                self.alive_every_s, self.alive,
                clock=Clock(clock_type=ClockType.STEADY_TIME))

            self.get_logger().info(
                "this node reads NO ground truth and broadcasts NO "
                "transform - see the file header for both reasons")
            self.get_logger().info(
                "alive check every {:g} s of steady clock, warning after "
                "{:g} s with no estimate published, then {} warns at that "
                "cadence and one per {:g} s after".format(
                    self.alive_every_s, self.alive_warn_after_s,
                    self.alive_warn_max, self.alive_warn_backoff_s))

        # ---------------------------- inputs --------------------------

        def cb_steer(self, msg):
            self._steer_msgs += 1
            index = joint_index(msg, self.steer_joint)
            if index is None:
                self.cfg.refuse(
                    "the joint state carries " + self.steer_joint,
                    self.cfg.s("topics.joint_state") +
                    " (published by m5_ver3/gazebo/forklift_ver3/model.sdf)",
                    "the message names: {}".format(list(msg.name)),
                    "config.yaml wheel_odom.steer_joint_name reads "
                    "{!r}".format(self.steer_joint))
            if index >= len(msg.position):
                # THE MESSAGE NAMED THE JOINT AND CARRIED NO ANGLE FOR
                # IT, which is not a refusal - a JointState is allowed to
                # publish names without positions and the next one may
                # well carry both - but it is not nothing either: a plant
                # that only ever does this leaves the held steer at None
                # for ever and every drive sample is then skipped. It is
                # COUNTED so alive() can name it as the reason, which is
                # the difference between a silent return and a silent
                # node.
                self._steer_no_position += 1
                return
            self._steer_rad = float(msg.position[index])
            self._steer_t = stamp_to_s(msg.header.stamp)

        def cb_drive(self, msg):
            self._drive_msgs += 1
            index = joint_index(msg, self.drive_joint)
            if index is None:
                self.cfg.refuse(
                    "the drive reading carries " + self.drive_joint,
                    self.cfg.s("topics.drive_speed_read_a") +
                    " (published by m5_ver3/gazebo/forklift_ver3/model.sdf)",
                    "the message names: {}".format(list(msg.name)),
                    "config.yaml wheel_odom.drive_joint_name reads "
                    "{!r}".format(self.drive_joint))
            if index >= len(msg.position):
                # THE POSITION FIELD IS THE INPUT AND THERE IS NO
                # FALLBACK TO VELOCITY. Integrating a rate into a
                # position and then quantising THAT would be a different
                # instrument wearing this one's name, and nothing here
                # may quietly become it. gz's JointStatePublisher fills
                # position; a message without one is a plant that changed.
                self.cfg.refuse(
                    "the drive reading carries a joint POSITION",
                    self.cfg.s("topics.drive_speed_read_a"),
                    "the message has {} name(s) and {} position(s)".format(
                        len(msg.name), len(msg.position)),
                    "this node quantises the shaft ANGLE onto the count "
                    "grid, which is what a real disc is bolted to;",
                    "it does not integrate a rate into a position and "
                    "call the result an encoder.")
            t_s = stamp_to_s(msg.header.stamp)

            if self._steer_rad is None:
                self._skipped_no_steer += 1
                return
            if abs(t_s - self._steer_t) > self.steer_stale_s:
                self._skipped_stale += 1
                return

            est = self.core.update(t_s, float(msg.position[index]),
                                   self._steer_rad)
            if est is None:
                return
            self.publish(est)
            self.heartbeat(est)

        # ---------------------------- output --------------------------

        def publish(self, est):
            out = Odometry()
            out.header.stamp = seconds_to_stamp(self._Time, est.t_s)
            out.header.frame_id = self.odom_frame
            out.child_frame_id = self.base_frame
            out.pose.pose.position.x = est.x
            out.pose.pose.position.y = est.y
            qz, qw = wheel_odom_core.yaw_to_quaternion(est.yaw)
            out.pose.pose.orientation.z = qz
            out.pose.pose.orientation.w = qw
            out.pose.covariance = self._pose_cov
            out.twist.twist.linear.x = est.vx
            out.twist.twist.linear.y = est.vy
            out.twist.twist.angular.z = est.yaw_rate
            out.twist.covariance = self._twist_cov
            self.pub.publish(out)
            self._published += 1

        def heartbeat(self, est):
            """One line in the child's log every log_every_s of SIM time.

            It exists so that logs/odom.log is readable as a run rather
            than as a startup banner followed by silence: where the
            estimate thinks it is, how many samples it published, and how
            many it dropped and why.
            """
            if self._last_log_t is None:
                self._last_log_t = est.t_s
                return
            if est.t_s - self._last_log_t < self.log_every_s:
                return
            self._last_log_t = est.t_s
            self.get_logger().info(
                "t {:.2f} | x {:+.3f} y {:+.3f} yaw {:+.4f} | "
                "vx {:+.3f} vyaw {:+.4f} | count {} | published {} | "
                "skipped {} (no steer) + {} (stale steer)".format(
                    est.t_s, est.x, est.y, est.yaw, est.vx, est.yaw_rate,
                    est.count, self._published,
                    self._skipped_no_steer, self._skipped_stale))

        # --------------------------- liveness -------------------------

        def why_silent(self):
            """The one sentence a reader of odom.log needs, in the order
            the causes have to be ruled out.

            IT IS A DIAGNOSIS AND NOT A GUESS. Every branch below is
            decided by a counter this node kept itself; none of them
            infers anything from the absence of another. The order runs
            from the plant outwards - no message at all, then a message
            this node could not use, then a reading too old to use -
            because that is the order an operator would check them in.
            """
            if self._drive_msgs == 0 and self._steer_msgs == 0:
                return ("neither input has delivered a message - the "
                        "bridge or the world is the place to look, not "
                        "this node")
            if self._drive_msgs == 0:
                return "nothing has arrived on " + self.cfg.s(
                    "topics.drive_speed_read_a")
            if self._steer_msgs == 0:
                return "nothing has arrived on " + self.cfg.s(
                    "topics.joint_state")
            if self._steer_rad is None:
                if self._steer_no_position:
                    return ("{} joint states named {} and carried no "
                            "position for it".format(
                                self._steer_no_position, self.steer_joint))
                return "no steer reading has been accepted yet"
            if self._skipped_stale:
                return ("the held steer reading is older than {:g} s "
                        "against the drive stamp".format(self.steer_stale_s))
            return ("both inputs are arriving and nothing is coming out - "
                    "read the counters")

        def alive(self):
            """The node's own pulse, on the machine's clock.

            IT IS SILENT WHILE THE OUTPUT MOVES. A run that is working
            already has heartbeat()'s line every log_every_s of sim time,
            and a second cadence over the top of it would only make that
            one harder to read. This one speaks exactly when the other
            cannot: the publish count has not moved since the last tick.

            INFO FIRST, WARN AFTER, THEN LESS OFTEN. A stack coming up is
            silent for as long as the world takes to advertise, and
            calling that a fault would teach the operator to ignore the
            line - which is the one thing a watchdog may not do (m6's own
            escalation rule). So the first ticks are info and the level
            rises only once the silence has outlasted a bringup; and
            because the fault it reports does not clear itself, the warn
            cadence is capped and backs off rather than running for ever.
            alive_tick() holds that decision and the tests hold it to it.

            THE COUNTERS ARE THIS FUNCTION'S; THE DECISION IS NOT. What
            is left here is reading a clock, formatting a line and
            calling a logger - which is the same split as the rest of
            this file, and for the same reason.
            """
            now = time.monotonic()
            if self._published != self._alive_published:
                # THE OUTPUT MOVED. A silence that ends and a new one
                # that begins are two faults, so the warn budget resets
                # with the clock: the second fault gets its full cadence
                # and is not throttled by the first one's history.
                self._alive_published = self._published
                self._alive_t = now
                self._alive_warns = 0
                self._alive_last_warn_s = None
                self._alive_suppressed = 0
                return
            silent_s = now - self._alive_t
            tick = alive_tick(
                silent_s=silent_s, warn_after_s=self.alive_warn_after_s,
                warns=self._alive_warns, warn_max=self.alive_warn_max,
                backoff_s=self.alive_warn_backoff_s,
                last_warn_s=self._alive_last_warn_s)
            if not tick.speak:
                self._alive_suppressed += 1
                return
            line = ("NO ESTIMATE PUBLISHED for {:.1f} s of steady clock: "
                    "{} | published {} | drive msgs {} | steer msgs {} "
                    "({} with no position) | skipped {} (no steer yet) + "
                    "{} (stale steer)".format(
                        silent_s, self.why_silent(), self._published,
                        self._drive_msgs, self._steer_msgs,
                        self._steer_no_position, self._skipped_no_steer,
                        self._skipped_stale))
            if tick.backed_off:
                # THE SUPPRESSED TICKS ARE NAMED IN THE LINE THAT
                # FOLLOWS THEM. A reader who sees a five-minute gap
                # between two identical lines has to be told the gap is
                # this watchdog's doing and not the fault pausing.
                line += (" | backed off: {} tick(s) suppressed, one line "
                         "per {:g} s while this lasts".format(
                             self._alive_suppressed,
                             self.alive_warn_backoff_s))
                self._alive_suppressed = 0
            if tick.level == "warn":
                self._alive_warns += 1
                self._alive_last_warn_s = silent_s
                self.get_logger().warn(line)
            else:
                self.get_logger().info(line)

    return WheelOdometryNode


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    try:
        import rclpy
        from builtin_interfaces.msg import Time
        from nav_msgs.msg import Odometry
        from rclpy.clock import Clock, ClockType
        from rclpy.executors import ExternalShutdownException
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from sensor_msgs.msg import JointState
    except ImportError as exc:
        _common.refuse(
            TOOL, "rclpy is importable", _common.CONFIG + " (paths.ros_setup)",
            "python3 could not import ROS 2: {}".format(exc),
            "this node runs INSIDE WSL with /opt/ros/jazzy sourced -",
            "m5v3.sh sources it before it spawns this child. See CONTEXT.md.")

    rclpy.init(args=argv)
    node_class = _make_node_class(Node, JointState, Odometry, QoSProfile,
                                  Time, Clock, ClockType)
    node = node_class(cfg)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # SIGTERM IS HOW THIS NODE IS NORMALLY ENDED, AND IT COMES OUT OF
        # spin(), NOT OUT OF THE TEARDOWN BELOW. m5v3.sh's stop sweeps
        # this child with TERM, rclpy turns that into an
        # ExternalShutdownException, and leaving it uncaught put a
        # traceback at the end of EVERY clean stop - which is the exact
        # failure the guard under `finally` was written to prevent, one
        # frame too low to prevent it. An operator's Ctrl-C on a node run
        # by hand is the same event under another name, so the two are
        # caught together and neither is an error.
        pass
    finally:
        node.destroy_node()
        # rclpy.shutdown() is guarded because a node killed by the stack
        # sweep can reach here with the context already torn down, and an
        # exception from the teardown would be the last line in the log -
        # pointing the operator at the shutdown instead of at the reason.
        try:
            rclpy.shutdown()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
