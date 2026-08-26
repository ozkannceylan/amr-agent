#!/usr/bin/env python3
"""rf2o_twist.py - the ROS shell around rf2o_twist_core. Wiring only.

    python3 m5_ver3/nodes/rf2o_twist.py

m5v3.sh starts it as the stack child `rf2ocov`, and ONLY when
`m5v3.sh start --rf2o` was given; it writes logs/rf2ocov.log. Run it by
hand against a stack that is already up and it behaves the same.

    /m5v3/rf2o/odom_raw   ->   /m5v3/rf2o/odom   ->  ekf_node's odom1
    /forklift/gz/scan_nav ->

WHAT IT DOES, AND IT IS ALL IT DOES. One message in, one message out,
with four things changed and everything else copied:

    the frame the numbers  rotated by the scan aperture's own centre
    are in                 bearing, which on this plant is pi - rf2o
                           assumes the window is symmetric about the
                           sensor's x axis and this one is not
    twist.linear.x         from the SCANNER's forward speed to
                           base_link's, through the lever arm upstream
                           does not correct
    the twist covariance   from rf2o's 36 zeros to config.yaml's
                           rf2o.covariance, which is MEASURED
                           (EVIDENCE_FUSION.md 10.2)
    the pose covariance    to 1000.0 on all six axes, the do-not-fuse
                           flag nodes/wheel_odometry.py raises on its own
                           dead-reckoned pose and for the same reason

Every decision that could be wrong about any of them is in
nodes/rf2o_twist_core.py, where pytest reaches it with no rclpy and no
simulator; what is here is subscriptions, message assembly and refusals.
That module's header is the argument for the relay existing at all.

WHY IT SUBSCRIBES TO THE SCAN, WHICH IT DOES NOT MEASURE ANYTHING FROM.
It reads two numbers out of the first message and never looks at a range:
`angle_min` and `angle_max`, which give the bearing rf2o's frame is
rotated from the scanner's by. That could have been a constant in
config.yaml beside the mount - and it is deliberately not, because it is
a property of the MESSAGE rf2o consumed rather than of the vehicle, and
reading it off the same wire is the difference between a correction that
is derived and one that is asserted. Until that message arrives the relay
publishes NOTHING and says so, which is nodes/wheel_odometry.py's held
steer angle exactly: a skipped sample is free, and integrating against a
value that has not arrived is not.

WHY NOT JUST POINT ekf_node AT rf2o's OWN TOPIC.
robot_localization takes each measurement's covariance out of the
MESSAGE - there is no per-sensor override parameter, by design, because a
covariance is the sensor's statement about itself. rf2o makes no such
statement: `publish()` never assigns one. A zero variance on a fused
channel is not read as "unknown", it is replaced with a very small
number, so the arm would arrive trusted far above the wheel odometry it
exists to be compared with. And it would arrive with its sign inverted.

IT NEVER SUBSCRIBES THE GROUND TRUTH, exactly as nodes/wheel_odometry.py
does not, and the same rule is why the rf2o child itself is started with
`init_pose_from_topic` set EMPTY: that parameter's upstream default is
`/base_pose_ground_truth`, so leaving it alone would put a ground-truth
subscription inside an estimator (F2 global constraint 13). Neither file
contains a subscription to /forklift/gz/odom.

IT BROADCASTS NO TRANSFORM. odom -> base_link has exactly one owner on
this track and it is ekf_node. rf2o would broadcast that edge itself -
its `publish_tf` parameter defaults TRUE - which is why m5v3.sh passes it
false, and why the frame this relay stamps on the pose it forwards is
frames.rf2o_odom and not frames.odom: a second opinion about an edge must
not be able to wear that edge's name even by accident.

WHY THE ROS IMPORTS ARE INSIDE main(). This track's pytest runs on the
owner's Windows python, where there is no rclpy, and the suite's conftest
puts this directory on sys.path - nodes/wheel_odometry.py's header
carries the whole argument and this file copies its shape.
"""
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
for _sub in (_HERE, os.path.normpath(os.path.join(_HERE, os.pardir, "tools"))):
    if _sub not in sys.path:
        sys.path.insert(0, _sub)

import _common                                        # noqa: E402
import evidence_core as _core                         # noqa: E402
import rf2o_twist_core                                # noqa: E402
# THE COVARIANCE LAYOUT HAS ONE HOME AND IT IS THE OTHER SHELL'S.
# covariance_diagonal() turns six numbers into ROS's row-major 6x6, which
# is message assembly and therefore a shell's job on this track - and two
# copies of a mechanism drift the way two copies of a value do
# (tools/_common.sh's own argument). Importing it here is a shell reading
# a shell, at one layer, and nodes/wheel_odometry.py imports no ROS at
# module scope so this costs nothing.
import wheel_odometry                                 # noqa: E402

TOOL = "rf2o_twist"

# MAINTENANCE OBLIGATION: a key read below is a key listed here. Refused
# by its DOTTED name before a single subscription is made.
REQUIRED_KEYS = (
    "topics.rf2o_odom_raw", "topics.rf2o_odom", "topics.scan_nav",
    "frames.base_link", "frames.rf2o_odom", "frames.nav_lidar",
    "vehicle.model",
    "vehicle.nav_lidar_mount.x", "vehicle.nav_lidar_mount.y",
    "vehicle.nav_lidar_mount.z",
    "rf2o.covariance.vx", "rf2o.covariance.vyaw", "rf2o.covariance.unused",
    "rf2o.aperture_sin_epsilon",
    "rf2o.qos_depth", "rf2o.log_every_s",
)


def mount_from_model(cfg):
    """The scanner's mount, READ OFF THE PLANT and checked against the copy.

    THE CORRECTION THIS NODE APPLIES IS A GEOMETRY CLAIM, so it is made
    against the file that decides the geometry rather than against a
    number typed into config.yaml. model.sdf owns nav_lidar_link's pose;
    config.yaml carries a copy because a SHELL cannot read XML and
    m5v3.sh has to put the same offset on /tf_static. A copy that has
    gone stale would move this correction and nothing downstream would
    look wrong - so it is diffed here, once, at startup, and a
    disagreement is a refusal naming both numbers.

    IT IS THE SAME IDIOM AS THE EKF PARAMETER FILE'S NODE-NAME GREP: a
    coupling written down is not a coupling checked.
    """
    model = os.path.join(_common.REPO, cfg.s("vehicle.model"))
    link = cfg.s("frames.nav_lidar")
    try:
        pose = _core.sdf_link_pose(model, link)
    except _core.EvidenceError as exc:
        cfg.refuse("the model declares " + link, model, str(exc))
    copied = (cfg.f("vehicle.nav_lidar_mount.x"),
              cfg.f("vehicle.nav_lidar_mount.y"),
              cfg.f("vehicle.nav_lidar_mount.z"))
    for index, axis in enumerate("xyz"):
        if abs(copied[index] - pose[index]) > 1e-9:
            cfg.refuse(
                "config.yaml's nav_lidar_mount.{} is the model's".format(axis),
                "{} and {} (vehicle.nav_lidar_mount)".format(model,
                                                             _common.CONFIG),
                "the model mounts {} at {} on that axis".format(
                    link, pose[index]),
                "config.yaml says {}".format(copied[index]),
                "this node's lever-arm correction is that offset; a stale "
                "copy would",
                "make it a plausible number about a scanner that is "
                "somewhere else.")
    if not rf2o_twist_core.mount_rotation_is_zero(pose[3:]):
        cfg.refuse(
            "the nav lidar is bolted square to the vehicle", model,
            "{}'s <pose> carries a rotation {}".format(link, pose[3:]),
            "nodes/rf2o_twist_core.py's base_vx() adds two scalars, which "
            "is the",
            "rigid-body relation ONLY when the scanner LINK's x axis is "
            "base_link's.",
            "With a rotated mount that correction is a number about "
            "nothing, and",
            "rf2o's own lin_speed is a component of a velocity in a frame "
            "this stack",
            "never sees. It is refused rather than corrected because "
            "correcting it needs",
            "the scanner's own vy, which rf2o hard-codes to 0.0.",
            "(This is NOT the aperture rotation this node DOES correct - "
            "that one is",
            "inside the sensor and is read off the scan message.)")
    return pose


def _make_node_class(Node, Odometry, LaserScan, QoSProfile):
    """Build the node class once the ROS types are in hand - the shape
    nodes/wheel_odometry.py uses, and for its reason."""

    class Rf2oTwistNode(Node):

        def __init__(self, cfg):
            super().__init__("m5v3_rf2o_twist")
            self.cfg = cfg
            pose = mount_from_model(cfg)
            self.mount_x, self.mount_y = pose[0], pose[1]
            self.base_frame = cfg.s("frames.base_link")
            self.rf2o_frame = cfg.s("frames.rf2o_odom")
            self.log_every_s = cfg.f("rf2o.log_every_s")

            unused = cfg.f("rf2o.covariance.unused")
            # THE POSE IS UNUSED IN ALL SIX AXES. rf2o integrates its own
            # scan-matched dead reckoning and this node forwards that
            # pose - rotated into the scanner's frame, so that the
            # recorded stream means something - with 1000.0 on every axis
            # as a do-not-fuse flag (config.yaml rf2o.covariance.unused),
            # the same flag nodes/wheel_odometry.py raises on its own.
            # ekf_rf2o.yaml's six false pose flags are the SECOND
            # refusal, because a flag is not a mechanism.
            self._pose_cov = wheel_odometry.covariance_diagonal([unused] * 6)
            # vy IS `unused` AND NOT A MEASURED NUMBER, and that is the
            # one entry here worth reading twice. rf2o writes a literal
            # 0.0 into twist.linear.y - measured, all 912 samples of a
            # 60 s capture - while the vehicle's real lateral velocity is
            # d*yaw_rate and is nowhere near zero in a turn (ekf.yaml
            # odom0_config). Publishing a covariance for a hard-coded
            # constant would be inviting somebody to fuse it.
            self._twist_cov = wheel_odometry.covariance_diagonal([
                cfg.f("rf2o.covariance.vx"), unused,
                unused, unused, unused,
                cfg.f("rf2o.covariance.vyaw")])

            # THE APERTURE'S CENTRE BEARING, HELD UNTIL THE SCAN SAYS.
            # None means no scan has arrived yet and nothing may be
            # published: without it this node does not know which way
            # rf2o's x axis points, and a guess would be a sign.
            self._centre_rad = None
            self._in = 0
            self._published = 0
            self._dropped = 0
            self._skipped_no_scan = 0
            self._last_drop = None
            self._last_log_t = None

            qos = QoSProfile(depth=cfg.i("rf2o.qos_depth"))
            self.pub = self.create_publisher(
                Odometry, cfg.s("topics.rf2o_odom"), qos)
            # THE SCAN FIRST, so the aperture can be known before the
            # first relayed sample rather than one message later.
            self.create_subscription(
                LaserScan, cfg.s("topics.scan_nav"), self.cb_scan, qos)
            self.create_subscription(
                Odometry, cfg.s("topics.rf2o_odom_raw"), self.cb_raw, qos)

            self.get_logger().info(
                "rf2o twist relay up: {} -> {}".format(
                    cfg.s("topics.rf2o_odom_raw"), cfg.s("topics.rf2o_odom")))
            self.get_logger().info(
                "lever arm from {} ({:+.3f}, {:+.3f}) read out of {} - "
                "vx gains yaw_rate x {:+.3f}".format(
                    cfg.s("frames.nav_lidar"), self.mount_x, self.mount_y,
                    cfg.s("vehicle.model"), self.mount_y))
            self.get_logger().info(
                "twist covariance vx {:.6g}, vyaw {:.6g} (MEASURED, "
                "config.yaml rf2o.covariance); vy and the whole pose carry "
                "{:g} as a do-not-fuse flag".format(
                    cfg.f("rf2o.covariance.vx"), cfg.f("rf2o.covariance.vyaw"),
                    unused))
            self.get_logger().info(
                "waiting for {} to say where its aperture is centred - "
                "rf2o assumes the middle of the window is the sensor's x "
                "axis and never reads angle_min".format(
                    cfg.s("topics.scan_nav")))
            self.get_logger().info(
                "this node reads NO ground truth and broadcasts NO "
                "transform - see the file header for both reasons")

        # ---------------------------- inputs --------------------------

        def cb_scan(self, msg):
            centre = rf2o_twist_core.scan_centre_rad(msg.angle_min,
                                                     msg.angle_max)
            if self._centre_rad is not None:
                # A SCANNER DOES NOT REPOINT ITSELF MID-RUN, and if this
                # one did, every sample already relayed would be in a
                # different frame from every sample after it - which is
                # a thing no reader of the CSV could see. Refused rather
                # than followed.
                if abs(centre - self._centre_rad) > 1e-12:
                    self.cfg.refuse(
                        "the scan's aperture does not move mid-run",
                        self.cfg.s("topics.scan_nav"),
                        "it opened centred on {:.7f} rad and now reads "
                        "{:.7f}".format(self._centre_rad, centre),
                        "every sample relayed so far was rotated by the "
                        "first of those.")
                return
            self._centre_rad = centre
            self.get_logger().info(
                "aperture {:.7f} .. {:.7f} rad ({:.1f} deg wide), centred "
                "on {:+.7f} rad = {:+.1f} deg".format(
                    msg.angle_min, msg.angle_max,
                    math.degrees(abs(msg.angle_max - msg.angle_min)),
                    centre, math.degrees(centre)))
            # IS THE CORRECTION THIS NODE IS ABOUT TO APPLY EXACT ON
            # THIS APERTURE? A refusal, here, once, on the first scan -
            # before a single sample has been relayed.
            #   WHAT IT GUARDS. decide()'s rotation computes
            #   `vx*cos(c) - vy*sin(c)`, and the vy it gets is
            #   upstream's hard-coded 0.0 rather than the scanner's real
            #   lateral speed, which never leaves that process. So the
            #   `-vy*sin(c)` term is always missing and the answer is
            #   right only where it vanishes - sin(c) = 0, an aperture
            #   centred on 0 or pi. This plant's is centred on pi on
            #   purpose (model.sdf) and clears the epsilon by ~19x.
            #   WHY IT IS A REFUSAL AND NOT A WARNING. On any other
            #   aperture the leak is a BIAS on the one channel this arm
            #   contributes, through every turn, and there is nothing
            #   downstream that could see it: the twist is at rate, the
            #   covariance is the measured one, `status` reads nine
            #   alive and every table would print. It is the shape of
            #   failure check_rf2o_transform() exists for, one frame in.
            #   IT IS CHECKED ON THE WIRE AND NOT ON model.sdf, because
            #   the aperture that matters is the one rf2o is reading.
            epsilon = self.cfg.f("rf2o.aperture_sin_epsilon")
            if not rf2o_twist_core.aperture_is_recoverable(centre, epsilon):
                self.cfg.refuse(
                    "this aperture is one the frame correction is exact "
                    "on",
                    "{} and {} (rf2o.aperture_sin_epsilon)".format(
                        self.cfg.s("topics.scan_nav"), _common.CONFIG),
                    "the window is centred on {:+.7f} rad, whose |sin| "
                    "is {:.6g}".format(centre, abs(math.sin(centre))),
                    "against a ceiling of {:g}.".format(epsilon),
                    "rf2o publishes a hard-coded 0.0 for its own lateral "
                    "velocity, so the",
                    "`- vy*sin(centre)` term of the rotation back into "
                    "the scanner's frame is",
                    "ALWAYS MISSING. It only cancels where sin(centre) "
                    "is zero - an aperture",
                    "centred on 0 (symmetric, the correction is the "
                    "identity) or on pi (this",
                    "plant's). Here it does not cancel, and what leaks "
                    "through is the SCANNER's",
                    "unknown lateral speed, landing on the fused forward "
                    "speed as a bias through",
                    "every turn that no instrument on this stack could "
                    "attribute.",
                    "NOTHING HAS BEEN RELAYED. Recovering it needs rf2o's "
                    "own vy, which means a",
                    "patched rf2o at a new rf2o.commit and a re-measure - "
                    "not a number invented",
                    "here. EVIDENCE_FUSION.md 10.1(a) and "
                    "nodes/rf2o_twist_core.py's header.")
            if abs(centre) < 1e-12:
                self.get_logger().info(
                    "that is a conventionally symmetric window, so the "
                    "frame correction is the identity and only the lever "
                    "arm is applied")
            else:
                self.get_logger().info(
                    "rf2o's own frame is therefore rotated {:+.1f} deg "
                    "from {}, and every twist and pose it publishes is "
                    "turned back by that before it leaves here".format(
                        math.degrees(centre), self.cfg.s("frames.nav_lidar")))

        def cb_raw(self, msg):
            self._in += 1
            if self._centre_rad is None:
                # THE SCAN HAS NOT ARRIVED YET. Skipping is free: the
                # next sample carries the whole twist again, because a
                # twist is a rate and not an increment. Guessing the
                # aperture would not be free - on this plant it would be
                # a sign.
                self._skipped_no_scan += 1
                return
            # THE INCOMING COVARIANCE IS CHECKED BEFORE IT IS REPLACED,
            # every message. rf2o publishes 36 zeros at the pinned
            # commit; the day it publishes something else - a newer pin,
            # a fork, a patch - that is the author's own statement about
            # their estimator and this node may not silently write over
            # it. Refused by name rather than warned about: a warning in
            # a child's log is a warning nobody reads until the tables
            # are already published.
            try:
                absent = rf2o_twist_core.covariance_is_absent(
                    list(msg.twist.covariance))
            except ValueError as exc:
                self.cfg.refuse(
                    "the incoming twist covariance is a 6x6",
                    self.cfg.s("topics.rf2o_odom_raw"), str(exc))
            if not absent:
                self.cfg.refuse(
                    "rf2o still publishes no twist covariance of its own",
                    "{} (rf2o.commit) and {}".format(
                        _common.CONFIG, self.cfg.s("topics.rf2o_odom_raw")),
                    "the incoming message carries a NON-ZERO twist "
                    "covariance:",
                    "  {}".format(list(msg.twist.covariance)),
                    "config.yaml's rf2o.covariance is a MEASURED stand-in "
                    "for a number",
                    "the pinned revision does not produce "
                    "(EVIDENCE_FUSION.md 10.2). If the",
                    "upstream node now produces one, that is its own "
                    "statement about its own",
                    "estimator and overwriting it would make every A/B "
                    "figure a claim about",
                    "which of the two was used - which the tables could "
                    "not say.")
            out = rf2o_twist_core.decide(
                float(msg.twist.twist.linear.x),
                float(msg.twist.twist.linear.y),
                float(msg.twist.twist.angular.z),
                self._centre_rad, self.mount_y)
            if not out.publish:
                self._dropped += 1
                self._last_drop = out.reason
                return
            self.publish(msg, out)

        # ---------------------------- output --------------------------

        def publish(self, msg, out):
            fixed = Odometry()
            # THE STAMP IS THE INPUT'S. rf2o stamps its message with the
            # time of the SCAN it last used, which is sim time off the
            # bridged clock; re-stamping here would hand the filter a
            # measurement dated when python got round to it.
            fixed.header.stamp = msg.header.stamp
            # AND THE FRAME IS NOT rf2o's `odom`. m5v3.sh starts the
            # child with odom_frame_id = frames.rf2o_odom already, so
            # this is a copy rather than a rename - but it is spelled
            # from config.yaml here too, because a message on this topic
            # must never be able to claim the edge ekf_node owns.
            fixed.header.frame_id = self.rf2o_frame
            fixed.child_frame_id = self.base_frame
            # THE POSE IS TURNED BY THE SAME ANGLE AS THE TWIST, and it
            # is not fused either way. rf2o's position is in its own
            # rotated frame, so forwarding it raw would put a stream in
            # the evidence whose x runs backwards - the one number a
            # reader would take at face value because the covariance
            # says nobody is using it. The HEADING is untouched: a
            # constant rotation of the reference frame does not change
            # how far the vehicle has turned since it started.
            x, y = rf2o_twist_core.rotate(msg.pose.pose.position.x,
                                          msg.pose.pose.position.y,
                                          self._centre_rad)
            fixed.pose.pose.position.x = x
            fixed.pose.pose.position.y = y
            fixed.pose.pose.orientation = msg.pose.pose.orientation
            fixed.pose.covariance = self._pose_cov
            fixed.twist.twist.linear.x = out.vx
            # LEFT AT ZERO, WHICH IS WHAT ARRIVED. Upstream hard-codes
            # linear.y to 0.0 and the lateral half of the lever arm needs
            # the scanner's own vy, which never leaves that process - so
            # there is nothing here to correct and nothing to invent.
            # ekf_rf2o.yaml does not fuse it.
            fixed.twist.twist.linear.y = 0.0
            fixed.twist.twist.angular.z = out.yaw_rate
            fixed.twist.covariance = self._twist_cov
            self.pub.publish(fixed)
            self._published += 1
            self.heartbeat(msg, out)

        def heartbeat(self, msg, out):
            """One line in logs/rf2ocov.log every log_every_s of SIM time.

            It exists so the child's log is readable as a run rather than
            as a banner: what came in, what went out, what the two
            corrections moved, and how many samples were skipped or
            dropped and why - which is nodes/wheel_odometry.py's
            heartbeat and the same argument.
            """
            t_s = (float(msg.header.stamp.sec)
                   + float(msg.header.stamp.nanosec) * 1e-9)
            if self._last_log_t is None:
                self._last_log_t = t_s
                return
            if t_s - self._last_log_t < self.log_every_s:
                return
            self._last_log_t = t_s
            self.get_logger().info(
                "t {:.2f} | in {} out {} dropped {} skipped {} (no scan "
                "yet) | rf2o vx {:+.4f} -> base vx {:+.4f} | vyaw "
                "{:+.4f}{}".format(
                    t_s, self._in, self._published, self._dropped,
                    self._skipped_no_scan, msg.twist.twist.linear.x, out.vx,
                    out.yaw_rate,
                    "" if self._last_drop is None
                    else " | last drop: " + self._last_drop))

    return Rf2oTwistNode


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    try:
        import rclpy
        from nav_msgs.msg import Odometry
        from rclpy.executors import ExternalShutdownException
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from sensor_msgs.msg import LaserScan
    except ImportError as exc:
        _common.refuse(
            TOOL, "rclpy is importable", _common.CONFIG + " (paths.ros_setup)",
            "python3 could not import ROS 2: {}".format(exc),
            "this node runs INSIDE WSL with /opt/ros/jazzy sourced -",
            "m5v3.sh sources it before it spawns this child. See CONTEXT.md.")

    rclpy.init(args=argv)
    node = _make_node_class(Node, Odometry, LaserScan, QoSProfile)(cfg)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # SIGTERM out of spin(), which is how m5v3.sh's stop ends this
        # child - nodes/wheel_odometry.py's note carries the whole story.
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
