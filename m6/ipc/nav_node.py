"""nav_node.py - the ROS shell around nav_core. Wiring only.

Pose is the bridged GROUND-TRUTH odometry (spec: owner ruling - the nav
lidar guards, it does not localise). The scan feeds one number, the
travel-sector minimum. A stale /plc/status is treated as Motor False
here for the same reason cmd_gate does: silence is a demand.

A scan or odom that STOPS parks the autopilot: no pose means no command
(zeros flow), and a stale scan reads as guard_min 0.0 - the HOLD band -
rather than as a clear road. The safe direction, same as every Step 4
display rule.
"""
import json
import math
import time

import yaml

import avoid
from ros_optional import (
    DurabilityPolicy, LaserScan, Node, Odometry, QoSProfile, String, Twist,
    rclpy, require)
import follower
import nav_core
from status_contract import (
    AUTO_CMD_TOPIC, AUTO_GOAL_TOPIC, AUTO_ROUTE_TOPIC, AUTO_STATE_TOPIC,
    CONFIG_PATH, FIELDS_TOPIC, MODE_TOPIC, STATUS_STALE_S,
    STATUS_TOPIC, is_stale,
    parse_status, speed_limit_mm_s)

# ----------------------------- CONFIG -----------------------------
TICK_HZ = 20.0
STATE_EVERY = 2          # /auto/state every 2nd tick -> 10 Hz
SENSOR_STALE_S = 0.5     # odom at 20 Hz, scan at 10 Hz: 0.5 s is dead
# ------------------------------------------------------------------


def load_config(path=CONFIG_PATH):
    """The two gz source names come from the file that owns them.

    topics.gz_odom and topics.gz_scan_nav, read the way encoder_link.py
    reads the drive-speed pair. The launch file bridges them from the
    same keys; a literal here would give one name two sources, and a
    rename would then break the bridge and this subscriber differently.
    """
    with open(path, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def yaw_from_quat(z, w):
    return 2.0 * math.atan2(z, w)


class NavNode(Node):

    def __init__(self):
        super().__init__("nav_node")
        topics = load_config()["topics"]
        self.core = nav_core.NavCore()
        self.pose = None
        self.pose_rx = None
        self.fwd_guard = 0.0
        self.rev_guard = 0.0
        # None until the first scan, and None is what the escalation
        # reads as "no picture of the world" - the same thing a stale
        # scan gives it.
        self.buckets = None
        self.guard_rx = None
        # The three SAFETY scanners' closest return, off the same report
        # the field evaluation publishes. 0.0 until one arrives, which is
        # the creep end of the scale - see cb_fields.
        self.field_min = 0.0
        self.field_rx = None
        self.motor = False
        self.v_limit = 300
        self.status_rx = None
        self.ticks = 0
        self.pub_cmd = self.create_publisher(Twist, AUTO_CMD_TOPIC, 10)
        self.pub_state = self.create_publisher(String, AUTO_STATE_TOPIC, 10)
        latched = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, MODE_TOPIC, self.cb_mode, latched)
        self.create_subscription(String, AUTO_GOAL_TOPIC, self.cb_goal, 10)
        self.create_subscription(
            String, AUTO_ROUTE_TOPIC, self.cb_route, 10)
        self.create_subscription(
            Odometry, topics["gz_odom"], self.cb_odom, 10)
        self.create_subscription(
            LaserScan, topics["gz_scan_nav"], self.cb_scan, 10)
        self.create_subscription(String, STATUS_TOPIC, self.cb_status, 10)
        self.create_subscription(String, FIELDS_TOPIC, self.cb_fields, 10)
        self.create_timer(1.0 / TICK_HZ, self.tick)

    def cb_mode(self, msg):
        self.core.on_mode(msg.data)

    def cb_goal(self, msg):
        if self.pose is None:
            self.core.note = "goal refused: no pose yet"
            return
        self.core.on_goal(msg.data, self.pose[:2])

    def cb_route(self, msg):
        if self.pose is None:
            self.core.note = "route refused: no pose yet"
            return
        try:
            req = json.loads(msg.data)
            self.core.on_route(
                req["points"], req.get("arrive_m"), req.get("label", ""))
        except (ValueError, KeyError, TypeError):
            self.core.note = "route refused: unreadable request"

    def cb_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.pose = (p.x, p.y, yaw_from_quat(q.z, q.w))
        self.pose_rx = time.monotonic()

    def cb_scan(self, msg):
        # BOTH ENDS, EVERY SCAN. The phase is nav_core's to decide and
        # it decides after this callback has run, so reducing the scan
        # to one number here would be guessing which way the truck is
        # about to go. Two cheap passes, no guess.
        lo, hi = max(msg.range_min, 0.05), msg.range_max
        self.fwd_guard = follower.sector_min(
            msg.ranges, msg.angle_min, msg.angle_increment, lo, hi)
        self.rev_guard = follower.sector_min(
            msg.ranges, msg.angle_min, msg.angle_increment, lo, hi,
            forward=False)
        # THE SAME SCAN, KEPT AS A SHAPE AND NOT ONLY AS A NUMBER. The
        # two calls above answer "how close in the direction of travel";
        # this one answers "where is there floor", which is what the
        # escalation needs the moment the first answer is "too close".
        # One extra pass over 360 numbers at 10 Hz.
        self.buckets = avoid.buckets(
            msg.ranges, msg.angle_min, msg.angle_increment, lo, hi)
        self.guard_rx = time.monotonic()

    def cb_fields(self, msg):
        """The closest return any SAFETY scanner has, for the speed
        policy's fourth band (follower.FIELD_SLOW_M).

        IT READS THE DISTANCE AND NOT THE VERDICT, because by the time
        the verdict flips V_Limit has already flipped with it and the
        wheels are already too fast - which is the whole failure this
        band exists to prevent. `d` is what field_eval measured on the
        sample it decided on; a device it could not measure reports
        0.000 with its field violated, and 0.0 lands in the creep band,
        which is the direction to fail in.
        """
        try:
            report = json.loads(msg.data)
            self.field_min = min(
                float(report[name]["d"])
                for name in ("back", "left", "right"))
        except (ValueError, KeyError, TypeError):
            self.field_min = 0.0
        self.field_rx = time.monotonic()

    def cb_status(self, msg):
        state = parse_status(msg.data.encode())
        self.status_rx = time.monotonic()
        self.motor = bool(state["motor"]) if state else False
        self.v_limit = speed_limit_mm_s(
            state.get("v_limit") if state else None)

    def tick(self):
        now = time.monotonic()
        if self.pose is None or is_stale(self.pose_rx, now, SENSOR_STALE_S):
            self.pub_cmd.publish(Twist())
            return
        dead = is_stale(self.guard_rx, now, SENSOR_STALE_S)
        fwd = 0.0 if dead else self.fwd_guard
        rev = 0.0 if dead else self.rev_guard
        motor = self.motor and not is_stale(
            self.status_rx, now, STATUS_STALE_S)
        # A FIELDS REPORT THAT STOPPED READS AS 0.0, THE CREEP END. The
        # field evaluation publishes at 10 Hz and fails safe on its own
        # side; here its silence may only ever make this truck slower.
        stale_fields = is_stale(self.field_rx, now, SENSOR_STALE_S)
        field = 0.0 if stale_fields else self.field_min
        linear, steer = self.core.step(
            self.pose, fwd, rev, motor, self.v_limit, field,
            # A DEAD SCAN OFFERS NO FLOOR. `dead` already zeroes both
            # guards above; handing the last good buckets over with it
            # would let the escalation drive on a picture of the world
            # that stopped arriving, which is the one thing worse than
            # standing still.
            buckets=None if dead else self.buckets, now=now)
        msg = Twist()
        msg.linear.x = linear
        msg.angular.z = steer
        self.pub_cmd.publish(msg)
        self.ticks += 1
        if self.ticks % STATE_EVERY == 0:
            # Report the guard actually in force, not the other end's.
            self.pub_state.publish(String(data=self.core.state_json(
                self.pose, rev if self.core.reversing else fwd)))


def main():
    require()
    rclpy.init()
    node = NavNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
