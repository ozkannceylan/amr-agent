#!/usr/bin/env python3
"""nav2_adapter_node.py - the rclpy shell around the adapter's cores.

    python3 m6_ver2/nav2_adapter/nav2_adapter_node.py --vid f1 \\
        --world-frame f1/forklift/odom \\
        --ros-args -r __ns:=/f1 -r tf:=/tf -r tf_static:=/tf_static

WIRING ONLY, AND THE WORD IS LOAD-BEARING. Every decision that could be
WRONG about what this truck does lives in a pure module beside this one
- nav2_state (which word goes on the wire and when), nav2_legs (where
the goals go), nav2_cmd (what a twist becomes at the terminals),
nav2_pose (where the truck is believed to be), nav2_watch (when to
declare it stuck) - because a decision inside an rclpy callback is a
decision no test can reach without a simulator. What is HERE is
subscriptions, an action client, two timers, message assembly and the
order in which the cores are called.

WHAT IT REPLACES. m6/ipc/nav_node.py + nav_core.py + follower.py are
retired as the MOTION ENGINE; the fleet layer above them (vda_agent,
vda_orders, the HMI, cmd_mux, cmd_gate, forklift_io, sto_contactor) is
not modified at all. So this node has to present the byte-identical
`/[vid]/auto/*` contract while a per-truck nav2 stack does the driving
underneath (SPEC_ADAPTER.md, AMR-DEC-006).

---- EVERY ROS NAME THIS FILE OWNS, AND WHY IT IS SPELT THAT WAY ----

The node runs under `--ros-args -r __ns:=/<vid>`, so EVERY name below
that is written RELATIVE resolves to `/<vid>/...` - which is exactly
what m6/ipc/status_contract.contract(vid) says the fleet layer uses.
`wiring()` is the whole table and `--selftest` prints it beside
contract(vid)'s own answer, so a namespace that stopped being applied
is a diff and not a mystery.
  THE TWO ABSOLUTE ONES ARE ABSOLUTE ON PURPOSE. `/tf` is SHARED - one
  tree for four trucks (AMR-DEC-006) - and it is reached by the
  RELATIVE name `tf` plus the `-r tf:=/tf` remap every child carries,
  because a namespaced node publishes and subscribes `/<vid>/tf`
  otherwise and the four trees never meet. The EKF's own output topic
  is taken from config.yaml, where it is already absolute and already
  carries the truck.

---- NO rclpy AT MODULE SCOPE, AND THAT IS THE TESTABILITY SEAM ----

Every ROS import is inside main(). The module therefore imports on the
owner's Windows python, where `import rclpy` fails, and
tests/test_adapter_shell.py exercises the wiring table and the tick
logic against a FAKE node - which is the same trick
m5_ver3/tools/drive_goal.py uses and the reason this package's suite
runs at all. The node CLASS is built inside a factory for the same
reason: a class that inherits from rclpy.node.Node cannot be defined
without rclpy.

---- THE CLOCK, STATED ----
Staleness is measured on time.monotonic(), which is what every other
reader of this contract uses (status_contract.is_stale, cmd_gate,
nav_node). MESSAGE STAMPS are the node's ROS clock, which is sim time -
the world publishes /clock and every child on this stack runs
use_sim_time. The two are not mixed: one answers "has this gone quiet",
the other answers "when did this happen in the simulation".
"""
import argparse
import collections
import json
import math
import os
import sys
import time

import _donors                                            # noqa: F401

import follower                                           # noqa: E402
import nav2_cmd                                           # noqa: E402
import nav2_legs                                          # noqa: E402
import nav2_pose                                          # noqa: E402
import nav2_state                                         # noqa: E402
import nav2_watch                                         # noqa: E402
from status_contract import (STATUS_STALE_S, contract,     # noqa: E402
                             is_stale, parse_status,
                             speed_limit_mm_s)

TOOL = "nav2_adapter"

#: 20 Hz out, 10 Hz state - nav_node.py's cadence, kept because the HMI
#: and vda_agent were both written against it.
TICK_HZ = 20.0
STATE_EVERY = 2

#: Every dotted key this file reads. MAINTENANCE OBLIGATION (the same
#: one m5_ver3/tools/_common.py carries): a key read below is a key
#: listed here, or a reorganised config reaches the first callback and
#: fails there instead of being refused by its dotted name at boot.
REQUIRED_KEYS = (
    "frames.map", "frames.odom", "frames.base_link",
    "topics.scan_nav", "topics.odometry_filtered",
    "topics.cmd_vel_smoothed", "topics.speed_limit",
    "map.dir", "map.name", "map.registration.file",
    "vehicle.wheelbase_m", "vehicle.steer_limit_rad",
    "navcmd.steer_command_limit_rad", "navcmd.speed_max_mps",
    "navcmd.creep_speed_mps", "navcmd.zero_speed_mps",
    "navcmd.yawrate_refusal_radps", "navcmd.command_timeout_s",
    "nav.bt_xml", "nav.bt_xml_rpp", "nav.bt_xml_station",
    "nav.watchdog.required_closing_m", "nav.watchdog.closing_allowance_s",
)


def vehicle_config(vid, tool=TOOL, required_keys=REQUIRED_KEYS):
    """This truck's DERIVED config, read by the donor's own reader.

    THE SEAM, NAMED ONCE FOR THE WHOLE PACKAGE (m6_ver2/truck.sh says
    the same thing about wheel_odometry.py). m5_ver3/tools/_common.py
    binds `CONFIG` to the donor's config.yaml at import and opens it at
    CALL time, so rebinding the module attribute before load_config()
    points that reader - its YAML walk, its dotted-key check and its
    refusal grammar - at m6_ver2/vehicles/<vid>/config.yaml, which is a
    counted rewrite of that very file (SPEC_NAMESPACING.md 3). It is
    not an edit of the donor (AMR-DEC-006 freezes it) and it is not a
    vendored copy; a second config reader in this tree would be a
    second answer to the question "which truck is this".

    nav2_seed.py calls this rather than growing a reader of its own,
    for that reason and one more: the seed exists to gate THIS node, so
    a seed that read a different file would gate a different truck.
    """
    import _common                                        # m5_ver3/tools
    path = os.path.join(_donors.REPO, "m6_ver2", "vehicles", vid,
                        "config.yaml")
    if not os.path.isfile(path):
        _common.refuse(
            tool, "this truck's derived config exists",
            "m6_ver2/tools/instantiate_truck.py (SPEC_NAMESPACING.md 3)",
            "{} is not there. The per-vid tree is a gitignored BUILD "
            "PRODUCT.".format(path),
            "derive it: python3 m6_ver2/tools/instantiate_truck.py --all")
    _common.CONFIG = path
    return _common.load_config(tool, list(required_keys))


# ----------------------------------------------------------------------
# THE WIRING TABLE. One row per ROS name this node owns, and it is DATA
# rather than a sequence of create_* calls so that --selftest and the
# suite can read it without a graph. `address` is resolved against the
# config at build time; relative addresses are left relative on purpose
# (see the header).
# ----------------------------------------------------------------------
Wire = collections.namedtuple("Wire", "kind label msg address depth latched")


def wiring(cfg, vid):
    """Every subscription, publication and action this node creates."""
    names = contract(vid)
    return (
        # ---- what the fleet layer says to this truck ----
        Wire("sub", "route", "std_msgs/String", "auto/route", 10, False),
        Wire("sub", "goal", "std_msgs/String", "auto/goal", 10, False),
        # LATCHED, because the HMI publishes the mode once and a node
        # that started afterwards would otherwise never learn it -
        # and `mode != auto` is a refusal door.
        Wire("sub", "mode", "std_msgs/String", "hmi/mode", 1, True),
        Wire("sub", "status", "std_msgs/String", "plc/status", 10, False),
        # ---- what the stack underneath says ----
        # THE LAST TWIST IN THE COMMAND PATH. Relative, so truck.sh's
        # `-r cmd_vel_smoothed:=<monitor output>` can insert the
        # collision monitor without this file knowing.
        Wire("sub", "cmd_vel_smoothed", "geometry_msgs/Twist",
             "cmd_vel_smoothed", 10, False),
        # THE SHARED TREE. Relative + the `-r tf:=/tf` remap every child
        # carries; see the header.
        Wire("sub", "tf", "tf2_msgs/TFMessage", "tf", 50, False),
        # The EKF's own output, for the BODY TWIST that rides on
        # /<vid>/est/odom - vda_agent's `driving` flag reads it, and a
        # differenced pose would make a standing truck look alive on
        # localisation noise.
        Wire("sub", "filtered", "nav_msgs/Odometry",
             cfg.s("topics.odometry_filtered"), 10, False),
        # REPORTING ONLY (Decision 1): follower.sector_min on the raw
        # bridged scan, for /auto/state.guard_min, which the HMI draws.
        # The RAW scan and not the masked one, deliberately:
        # sector_min applies follower.SELF_MASK itself.
        Wire("sub", "scan", "sensor_msgs/LaserScan",
             cfg.s("topics.scan_nav"), 10, False),
        # ---- what this truck says back ----
        Wire("pub", "cmd", "geometry_msgs/Twist", "auto/cmd_vel", 10, False),
        Wire("pub", "state", "std_msgs/String", "auto/state", 10, False),
        # THE FIREWALL'S OUTPUT (Decision 4): the ESTIMATE in m6 world
        # coordinates. /<vid>/gz/odom ground truth is consumed by
        # nothing in this file.
        Wire("pub", "est", "nav_msgs/Odometry", "est/odom", 10, False),
        # The PLC's permission, republished for the controller to PLAN
        # at. Absolute in config and already carrying the truck.
        Wire("pub", "speed_limit", "nav2_msgs/SpeedLimit",
             cfg.s("topics.speed_limit"), 10, False),
        # ---- and the one action ----
        Wire("action", "navigate", "nav2_msgs/NavigateToPose",
             "navigate_to_pose", 0, False),
    ) + (
        # Named here so --selftest can print what the fleet layer
        # believes these resolve to, beside what this node asked for.
        Wire("expect", "auto/cmd_vel", "", names["auto_cmd_topic"], 0, False),
        Wire("expect", "auto/state", "", names["auto_state_topic"], 0, False),
        Wire("expect", "auto/route", "", names["auto_route_topic"], 0, False),
        Wire("expect", "auto/goal", "", names["auto_goal_topic"], 0, False),
        Wire("expect", "hmi/mode", "", names["mode_topic"], 0, False),
        Wire("expect", "plc/status", "", names["status_topic"], 0, False),
    )


#: THE THREE REMAPS m6_ver2/truck.sh PUTS ON EVERY CHILD, named here so
#: --selftest can show what the relative addresses above actually
#: resolve to. `tf`/`tf_static` are the shared-tree pair: without them a
#: namespaced node publishes on /<vid>/tf and the four trees never meet.
NS_REMAPS = (("__ns", "/<vid>"), ("tf", "/tf"), ("tf_static", "/tf_static"))


def own_args(argv):
    """This program's arguments: everything before `--ros-args`.

    rcl's own argument block belongs to rclpy.init and argparse must
    never see it - `-r __ns:=/f1` is not an option this file has heard
    of, and argparse's answer to that is exit 2 before a single line of
    this node has run. Split HERE rather than with
    rclpy.utilities.remove_ros_args so that --selftest works on a
    python with no ROS on it at all.
    """
    argv = list(argv)
    return argv[:argv.index("--ros-args")] if "--ros-args" in argv else argv


def _parser():
    parser = argparse.ArgumentParser(
        description="the nav2 adapter: m6's /auto contract on top of a "
                    "per-truck m5v3 nav2 stack. Wiring only.")
    parser.add_argument("--vid", help="f1..f4 - m6/ipc/status_contract's "
                                      "own ids")
    parser.add_argument(
        "--world-frame",
        help="the frame /<vid>/est/odom is stamped with. REQUIRED and "
             "without a default: the estimate is published on a shared "
             "tree with per-truck prefixed frames, so an unnamed frame "
             "is a message four trucks would answer to. truck.sh "
             "passes model.sdf's own rewritten <odom_frame>.")
    parser.add_argument("--selftest", action="store_true",
                        help="import, build the wiring table and print "
                             "it. No ROS, no graph, no spin.")
    return parser


# ----------------------------------------------------------------------
# THE ADAPTER. It takes a NODE rather than being one, which is what
# lets the suite drive a whole tick against a fake.
# ----------------------------------------------------------------------
class Adapter(object):
    """The order the cores are called in, and nothing else.

    Every branch below either calls a core or moves a message. If a
    line of arithmetic appears here that is not a distance or a message
    field, it is in the wrong file.
    """

    def __init__(self, node, msgs, cfg, vid, world_frame, clock_s=None):
        self.node = node
        self.msgs = msgs
        self.cfg = cfg
        self.vid = vid
        self.world_frame = world_frame
        self.base_frame = cfg.s("frames.base_link")
        self.map_frame = cfg.s("frames.map")
        self.odom_frame = cfg.s("frames.odom")
        #: The wall clock the staleness rules run on. Injected so the
        #: suite can step time instead of sleeping.
        self._now = clock_s or time.monotonic

        self.state = nav2_state.NavState()
        self.limits = nav2_cmd.limits_from_config({
            "wheelbase_m": cfg.f("vehicle.wheelbase_m"),
            "steer_limit_rad": cfg.f("vehicle.steer_limit_rad"),
            "steer_command_limit_rad": cfg.f("navcmd.steer_command_limit_rad"),
            "traction_max_mps": cfg.f("navcmd.speed_max_mps"),
            "creep_speed_mps": cfg.f("navcmd.creep_speed_mps"),
            "zero_speed_mps": cfg.f("navcmd.zero_speed_mps"),
            "yawrate_refusal_radps": cfg.f("navcmd.yawrate_refusal_radps"),
        })
        # THE COMMITTED REGISTRATION, WITH ITS GRID CHECKED UNDERNEATH
        # IT. load_frame refuses a transform whose .pgm was rebuilt: at
        # warehouse_v3's half turn the wrong rotation leaves every
        # magnitude exactly right and puts the truck on the other side
        # of the building.
        self.frame = nav2_pose.load_frame(os.path.join(
            _donors.REPO, cfg.s("map.dir"), cfg.s("map.name"),
            cfg.s("map.registration.file")))
        # THE THREE TREES, KEYED BY THE NAME nav2_legs.CLASS_TREE USES.
        # The dict is built from that table rather than typed out, so a
        # leg class that names a fourth tree is a KeyError on the config
        # key at BOOT - refused by its dotted name by load_config - and
        # not a goal forty metres into a drive carrying a path
        # bt_navigator cannot open.
        self.trees = dict(
            (key, os.path.join(_donors.REPO, cfg.s(key)))
            for _controller, key in nav2_legs.CLASS_TREE.values())
        self.command_timeout_s = cfg.f("navcmd.command_timeout_s")
        self.required_closing_m = cfg.f("nav.watchdog.required_closing_m")
        self.closing_allowance_s = cfg.f("nav.watchdog.closing_allowance_s")

        # ---- what has arrived, and when ----
        self.map_odom = None
        self.odom_base = None
        self.odom_base_rx = None
        self.body_twist = (0.0, 0.0)
        self.smoothed = (0.0, 0.0)
        self.smoothed_rx = None
        self.guard_min = float("inf")
        self.guard_rx = None
        self.motor = False
        self.v_limit = None
        self.status_rx = None
        #: THE LAST STEER ANGLE THIS NODE PUT ON THE WIRE, which is what
        #: nav2_cmd's `angular_z is None` means: "HOLD THE STEER AXIS".
        #: It starts at 0.0 because that is where the world spawns the
        #: axis - the adapter has no steer feedback and must not invent
        #: one - and every message published below sets it, so it is
        #: never a guess about anything except the boot instant.
        self.held_steer_rad = 0.0

        # ---- the leg queue and the goal generation ----
        self.legs = []
        self.leg_i = 0
        self.watch = None
        self.handle = None
        #: EVERY GOAL CARRIES ONE, and a result whose generation is not
        #: the current one is DROPPED. A preempted leg comes back
        #: ABORTED - nav2 displaces the running goal itself - and read
        #: as a failure it would latch BLOCKED on a truck that is
        #: driving perfectly (SPEC_ADAPTER.md Decision 2).
        self.generation = 0
        #: A LEG HELD BACK UNTIL THE SERVER IS IDLE AGAIN, and it exists
        #: because nav2 has TWO doors and this file has to pick the
        #: right one. See _advance_to(): a preemption that changes the
        #: behaviour tree is REFUSED by bt_navigator, so a leg whose
        #: class differs from the one in flight waits for the cancelled
        #: goal's result instead of racing it.
        self.pending_leg = None
        self.ticks = 0
        self.pubs = {}
        self.action = None

    # -------------------------- construction --------------------------

    def build(self, rows):
        """Create every publisher, subscription and action in `rows`."""
        for row in rows:
            if row.kind == "pub":
                self.pubs[row.label] = self.node.create_publisher(
                    self.msgs.type_of(row.msg), row.address,
                    self.msgs.qos(row.depth, row.latched))
            elif row.kind == "sub":
                self.node.create_subscription(
                    self.msgs.type_of(row.msg), row.address,
                    getattr(self, "cb_" + row.label),
                    self.msgs.qos(row.depth, row.latched))
            elif row.kind == "action":
                self.action = self.msgs.action_client(
                    self.node, self.msgs.type_of(row.msg), row.address)
        self.node.create_timer(1.0 / TICK_HZ, self.tick)

    # ---------------------------- the inputs ----------------------------

    def cb_mode(self, msg):
        self.state.on_mode(msg.data)
        self._follow_state()

    def cb_goal(self, msg):
        """The HMI's station GO, and the ONE cancel door."""
        accepted = self.state.on_goal(msg.data, self._world_xy())
        if accepted:
            self._start_route()
        else:
            self._follow_state()

    def cb_route(self, msg):
        """The VDA agent's released polyline.

        THE UNREADABLE-REQUEST REFUSAL LIVES HERE AND NOT IN THE CORE,
        because it is about JSON on a wire rather than about a route -
        nav_node.py drew the line in the same place and the string is
        pinned against nav2_state's copy by the suite.
        """
        try:
            request = json.loads(msg.data)
            points = request["points"]
            arrive_m = request.get("arrive_m")
            label = request.get("label", "")
        except (ValueError, KeyError, TypeError):
            self.state.note = nav2_state.ROUTE_REFUSED_UNREADABLE
            return
        if not self.state.on_route(points, arrive_m, label):
            return
        # AN EXTENSION CONTINUES, IT DOES NOT CHURN (Decision 2):
        # _start_route keeps the in-flight goal when its leg end
        # survives the re-split, which it does by rule - vda_agent
        # keeps the base of a route it extends.
        self._start_route()

    def cb_status(self, msg):
        state = parse_status(msg.data.encode())
        self.status_rx = self._now()
        self.motor = bool(state["motor"]) if state else False
        limit = speed_limit_mm_s(state.get("v_limit") if state else None)
        if limit != self.v_limit:
            self.v_limit = limit
            self._publish_speed_limit(limit)

    def cb_cmd_vel_smoothed(self, msg):
        self.smoothed = (msg.linear.x, msg.angular.z)
        self.smoothed_rx = self._now()

    def cb_filtered(self, msg):
        self.body_twist = (msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def cb_scan(self, msg):
        lo, hi = max(msg.range_min, 0.05), msg.range_max
        self.guard_min = follower.sector_min(
            msg.ranges, msg.angle_min, msg.angle_increment, lo, hi,
            forward=not self.state.reversing)
        self.guard_rx = self._now()

    def cb_tf(self, msg):
        """The two edges, matched on BOTH frame names.

        drive_goal.on_tf's zero-order-hold idiom: the anchor is HELD
        between AMCL's corrections and the child is whatever the EKF
        published last, so the composed pose is as fresh as the fast
        edge. Matching on the parent alone would accept another truck's
        edge - all four hang under one `map`.
        """
        for transform in msg.transforms:
            parent = transform.header.frame_id.lstrip("/")
            child = transform.child_frame_id.lstrip("/")
            sample = self.msgs.tf_sample(transform)
            if parent == self.map_frame and child == self.odom_frame:
                self.map_odom = sample
            elif parent == self.odom_frame and child == self.base_frame:
                self.odom_base = sample
                self.odom_base_rx = self._now()

    # ---------------------------- the tick ----------------------------

    def tick(self):
        now = self._now()
        world = self._believe(now)
        self._safety(now)
        if world is not None:
            self._drive(now, world)
        self._publish_cmd(now)
        if world is not None:
            self._publish_est(world)
        self.ticks += 1
        if self.ticks % STATE_EVERY == 0:
            self._publish_state(world, now)

    def _believe(self, now):
        """The composed pose in m6 world coordinates, or None."""
        sample = nav2_pose.compose(self.map_odom, self.odom_base)
        if sample is None:
            self.state.set_pose_ok(
                False, nav2_state.NOTE_LOCALISER_NOT_READY)
            return None
        health = nav2_pose.pose_health(now, self.odom_base_rx)
        self.state.set_pose_ok(health == nav2_pose.FRESH,
                               nav2_state.NOTE_POSE_STALE)
        if health == nav2_pose.CANCEL:
            # A BELIEF NOBODY IS UPDATING IS NOT A BELIEF. The route is
            # HELD for resume; only the goal goes.
            self._abandon_goal()
        if health != nav2_pose.FRESH:
            return None
        return nav2_pose.to_world(self.frame, sample.x, sample.y, sample.yaw)

    def _safety(self, now):
        """Motor False or a silent PLC. Cancel, hold, resume."""
        motor = self.motor and not is_stale(self.status_rx, now,
                                            STATUS_STALE_S)
        if not motor:
            if self.state.state not in (nav2_state.IDLE,
                                        nav2_state.SAFETY_STOP):
                self._abandon_goal()
                self.state.safety_stop()
            return
        if self.state.resume():
            # THE ROUTE WAS HELD, so there is a leg to re-send and no
            # operator ritual to perform.
            self._send_leg(self.leg_i)

    def _drive(self, now, world):
        """Preempt, watch and arrive - all three are core calls."""
        if self.state.state != nav2_state.EN_ROUTE or not self.legs:
            return
        leg = self.legs[self.leg_i]
        distance = math.dist(world[:2], leg.end)
        # A LEG ALREADY WAITING IS NOT PREEMPTED AGAIN. The distance is
        # still inside P for every tick of the cancel window, and a
        # second cancel would bump the generation the pending send is
        # waiting on.
        if self.pending_leg is None \
                and nav2_legs.should_preempt(distance, leg.final) \
                and self.leg_i + 1 < len(self.legs):
            self._advance_to(self.leg_i + 1)
            return
        if self.watch is not None:
            stalled = self.watch.step(now, distance)
            if stalled is not None:
                self._abandon_goal()
                self.state.block(nav2_watch.blocked_note_no_progress(stalled))
                return
        if self.state.check_arrival(world[:2]):
            self._abandon_goal()

    # ------------------------- the leg runner -------------------------

    def _start_route(self):
        """Split what the state machine accepted, and drive it.

        THE SPLIT COMES AFTER THE ACCEPTANCE AND BEFORE ANY TICK, so
        the wire never sees the moment in between: `/auto/state` is
        published by tick() alone, and both mutations happen inside one
        callback. A polyline the leg runner cannot split is refused as
        malformed, which leaves IDLE + a note + no goal - the shape
        every other refusal on this contract has.
        """
        try:
            legs = nav2_legs.plan_legs(self.state.route)
        except nav2_legs.Nav2LegsError:
            self.state.cancel(nav2_state.ROUTE_REFUSED_MALFORMED)
            self._abandon_goal()
            return
        running = (self.legs[self.leg_i].end
                   if self.handle is not None and self.legs else None)
        self.legs = legs
        if running is not None:
            for index, leg in enumerate(legs):
                if leg.end == running:
                    # THE IN-FLIGHT GOAL SURVIVED THE RE-SPLIT, so
                    # nothing stops and `executing` never flickers.
                    self.leg_i = index
                    return
        self._send_leg(0)

    def _advance_to(self, index):
        """Leg `index` starts - through whichever of nav2's two doors
        this transition is allowed to use.

        NAV2 REFUSES A PREEMPTION THAT CHANGES THE BEHAVIOUR TREE, and
        it says so in one line (nav2 1.3.12, measured live 2026-09-02):

          "Preemption request was rejected since the requested BT XML
           file is not the same as the one that the current goal is
           executing. Preemption with a new BT is invalid since it would
           require cancellation of the previous goal instead of true
           preemption. Cancel the current goal and send a new action
           request if you want to use a different BT XML file. For now,
           continuing to track the last goal until completion."

        The NEW goal is then aborted with an empty result (error_code
        0), the OLD goal keeps running, and the adapter - correctly by
        its own rules - reads that abort as a nav2 failure and latches
        BLOCKED. SPEC_ADAPTER.md Decision 2 asks for BOTH rolling
        preemption AND a per-leg-class tree, and those two meet at the
        transit -> station-spur boundary, which is the last leg of EVERY
        route: the order died there, 1.49 m from the spur foot, on the
        first run that got this far.

        So the tree decides the door. Same tree: true preemption, which
        is what P = 1.5 m was measured for and what keeps the truck
        moving. Different tree: nav2's own instruction, in its own
        order - cancel, and send when the server reports the old goal
        finished (_on_result), never on a timer. The truck decelerates
        into the spur foot, which is where a tricycle turning into a
        4.00 m bay off the ring band was going to slow down anyway.
        """
        if self.handle is None \
                or self.legs[index].tree_key == self.legs[self.leg_i].tree_key:
            self._send_leg(index)
            return
        self.pending_leg = index
        handle, self.handle = self.handle, None
        # THE WATCH IS LEFT RUNNING ON PURPOSE. It is measuring the
        # distance to the leg end the truck is still approaching, so it
        # stays the backstop if the cancelled goal's result never
        # arrives at all - which would otherwise be a silent stop.
        self.generation += 1
        handle.cancel_goal_async()

    def _send_pending(self):
        """The held leg, now that nav2 has finished with the last one."""
        index, self.pending_leg = self.pending_leg, None
        if index is not None:
            self._send_leg(index)

    def _send_leg(self, index):
        """One NavigateToPose goal, with a generation on it."""
        if not self.legs:
            return
        self.leg_i = index
        leg = self.legs[index]
        self.generation += 1
        generation = self.generation
        self.watch = nav2_watch.ClosingWatch(self.required_closing_m,
                                             self.closing_allowance_s)
        goal = self.msgs.nav_goal(
            frame_id=self.map_frame,
            stamp=self.node.get_clock().now().to_msg(),
            map_pose=self.frame.to_map(leg.end[0], leg.end[1],
                                       nav2_legs.leg_yaw(leg)),
            behavior_tree=self.trees[leg.tree_key])
        future = self.action.send_goal_async(goal)
        future.add_done_callback(
            lambda done, gen=generation: self._on_accepted(done, gen))

    def _on_accepted(self, done, generation):
        handle = done.result()
        if generation != self.generation:
            return
        if not handle.accepted:
            # A REFUSED GOAL HAS NO ERROR CODE, and the note table's
            # third row exists for exactly that: a number the operator
            # can look up beats an empty WHY.
            self.state.block(nav2_watch.blocked_note_for_error(-1))
            return
        self.handle = handle
        handle.get_result_async().add_done_callback(
            lambda result, gen=generation: self._on_result(result, gen))

    def _on_result(self, done, generation):
        """A preempted leg's ABORTED is not a failure. See `generation`."""
        if generation != self.generation:
            # THE OLD GOAL IS OFF THE SERVER, which is the one fact
            # _advance_to's cancel branch is waiting for. Displaced,
            # cancelled or aborted makes no difference here: what the
            # next goal needs is an idle bt_navigator, and this message
            # IS nav2 saying so.
            self._send_pending()
            return
        self.handle = None
        result = done.result()
        status, error_code = self.msgs.result_of(result)
        if status == self.msgs.CANCELED:
            return
        if status != self.msgs.SUCCEEDED:
            self.state.block(nav2_watch.blocked_note_for_error(error_code))
            return
        leg = self.legs[self.leg_i] if self.legs else None
        if leg is None or not leg.final:
            return
        if self.state.state == nav2_state.ARRIVED:
            return
        # SUCCEEDED SHORT OF arrive_m: report the miss and STOP. A
        # re-sent 0.4 m goal is inside this vehicle's turning circle and
        # m5v3 measured what that produces - the S7 orbit, a stable ring
        # round a station the truck can never reach.
        world = self._world_xy()
        known = world is not None and self.state.route
        distance = (math.dist(world, self.state.route[-1]) if known
                    else float("inf"))
        self.state.block(nav2_watch.arrived_short_note(distance,
                                                       self.state.arrive_m))

    def _abandon_goal(self):
        """Cancel whatever is running. The ROUTE is not touched here."""
        self.watch = None
        # AND THE LEG THAT WAS WAITING TO GO OUT. A cancel, a refusal or
        # a SAFETY-STOP that left a pending leg behind would send it the
        # moment the cancelled goal's result landed - a goal nobody
        # asked for, after the door that asked for it had closed.
        self.pending_leg = None
        handle, self.handle = self.handle, None
        self.generation += 1
        if handle is not None:
            handle.cancel_goal_async()

    def _follow_state(self):
        """The state machine dropped the route; the goal goes with it."""
        if self.state.route is None and (self.handle is not None or self.legs):
            self._abandon_goal()
            self.legs, self.leg_i = [], 0

    # ---------------------------- the outputs ----------------------------

    def _publish_cmd(self, now):
        """Zeros flow in every posture but EN-ROUTE, and they FLOW.

        cmd_gate's staleness rule is the reason the stream never stops:
        silence is a demand, and a stopped publisher is a different
        message from a zero.

        AND EVERY FIELD THAT GOES OUT IS A float. `angular_z` is None
        whenever the answer is "HOLD THE STEER AXIS" - nav2_cmd's own
        note says so, and says the shell republishes the last angle it
        sent. The donor's shell holds that axis by NOT PUBLISHING its
        steer terminal, which a plant with two Float64 terminals can do;
        this wire carries traction and steer in ONE Twist and a stopped
        stream is cmd_gate's staleness demand, so the hold has to be
        spelled as a number. Measured live 2026-09-02: assigning the
        None straight through aborts the process inside rosidl
        (`geometry_msgs__msg__vector3__convert_from_py`, PyFloat_Check),
        on the first sub-creep twist of the first leg - which is every
        standing start.
        """
        message = self.msgs.twist()
        if self.state.state == nav2_state.EN_ROUTE \
                and not is_stale(self.smoothed_rx, now,
                                 self.command_timeout_s):
            command = nav2_cmd.translate(
                self.smoothed[0], self.smoothed[1], self.limits,
                None if self.v_limit is None
                else nav2_cmd.limit_mps_from_v_limit(self.v_limit))
            message.linear.x = float(command.linear_x)
            # ZERO WOULD CENTRE THE WHEEL, which is a motion nobody
            # commanded and, at a stop inside a station spur, a motion
            # into the rack.
            if command.angular_z is not None:
                self.held_steer_rad = float(command.angular_z)
            message.angular.z = self.held_steer_rad
            self.state.reversing = command.reversing
        else:
            # THE ZEROS ARE A COMMAND TOO. Outside EN-ROUTE the contract
            # is zeros on both fields (SPEC_ADAPTER.md Decision 3), so
            # the axis IS being told to centre and the held angle is
            # that: this attribute is always the last angle sent, never
            # the last angle wanted.
            self.held_steer_rad = 0.0
            self.state.reversing = False
        self.pubs["cmd"].publish(message)

    def _publish_est(self, world):
        rows = nav2_pose.odometry_rows(
            self.node.get_clock().now().nanoseconds / 1e9, world,
            self.body_twist, self.world_frame, self.base_frame)
        self.pubs["est"].publish(self.msgs.odometry(rows))

    def _publish_state(self, world, now):
        # A SCAN THAT STOPPED HAS NO MEASUREMENT, and `guard_min` is
        # REPORTING ONLY here (Decision 1), so it goes out as JSON null
        # - which is what nav_core already emits for an infinite guard.
        # nav_node's 0.0 was the safe direction for a SPEED POLICY that
        # no longer exists on this path.
        guard = (float("inf")
                 if is_stale(self.guard_rx, now, nav2_pose.SENSOR_STALE_S)
                 else self.guard_min)
        pose = world if world is not None else (None, None, None)
        self.pubs["state"].publish(
            self.msgs.string(self.state.state_json(pose, guard)))

    def _publish_speed_limit(self, v_limit_mm_s):
        """The PLC's permission, so the controller PLANS at it.

        Three layers all pointing the same way: the controller plans at
        the permission, nav2_cmd clamps the twist at source, and
        cmd_gate still has the last word. Two ceilings on one quantity
        is a min(), which is idempotent.
        """
        row = nav2_cmd.speed_limit_message(v_limit_mm_s)
        self.pubs["speed_limit"].publish(self.msgs.speed_limit(row))

    # ------------------------------ helpers ------------------------------

    def _world_xy(self):
        sample = nav2_pose.compose(self.map_odom, self.odom_base)
        if sample is None:
            return None
        pose = nav2_pose.to_world(self.frame, sample.x, sample.y, sample.yaw)
        return (pose[0], pose[1])


# ----------------------------------------------------------------------
# THE ROS SIDE. Everything below this line needs rclpy and nothing above
# it does.
# ----------------------------------------------------------------------
def _messages():
    """The message types, the QoS profiles and the four assemblers.

    ONE OBJECT, BUILT ONCE, AND IT IS WHAT THE SUITE FAKES. Every ROS
    type this node touches is reached through it, so a test can drive a
    whole tick with plain python objects and still exercise the real
    ordering.
    """
    import rclpy                                          # noqa: F401
    from action_msgs.msg import GoalStatus
    from geometry_msgs.msg import Twist
    from nav_msgs.msg import Odometry
    from nav2_msgs.action import NavigateToPose
    from nav2_msgs.msg import SpeedLimit
    from rclpy.action import ActionClient
    from rclpy.qos import DurabilityPolicy, QoSProfile
    from sensor_msgs.msg import LaserScan
    from std_msgs.msg import String
    from tf2_msgs.msg import TFMessage

    types = {
        "std_msgs/String": String,
        "geometry_msgs/Twist": Twist,
        "nav_msgs/Odometry": Odometry,
        "sensor_msgs/LaserScan": LaserScan,
        "tf2_msgs/TFMessage": TFMessage,
        "nav2_msgs/SpeedLimit": SpeedLimit,
        "nav2_msgs/NavigateToPose": NavigateToPose,
    }

    class Messages(object):
        SUCCEEDED = GoalStatus.STATUS_SUCCEEDED
        CANCELED = GoalStatus.STATUS_CANCELED

        def type_of(self, name):
            return types[name]

        def qos(self, depth, latched):
            if latched:
                return QoSProfile(
                    depth=depth,
                    durability=DurabilityPolicy.TRANSIENT_LOCAL)
            return QoSProfile(depth=depth)

        def action_client(self, node, action_type, name):
            return ActionClient(node, action_type, name)

        def tf_sample(self, transform):
            t = transform.transform.translation
            r = transform.transform.rotation
            stamp = transform.header.stamp
            return nav2_pose.TfSample(
                t=stamp.sec + stamp.nanosec / 1e9, x=t.x, y=t.y,
                # YAW FROM THE QUATERNION'S z/w, which is planar by
                # construction on this stack: the EKF is two_d_mode and
                # AMCL's edge is a 2D pose.
                yaw=2.0 * math.atan2(r.z, r.w))

        def string(self, data):
            return String(data=data)

        def twist(self):
            return Twist()

        def odometry(self, rows):
            message = Odometry()
            message.header.frame_id = rows["header"]["frame_id"]
            stamp = rows["header"]["stamp_s"]
            message.header.stamp.sec = int(stamp)
            message.header.stamp.nanosec = int((stamp - int(stamp)) * 1e9)
            message.child_frame_id = rows["child_frame_id"]
            position = rows["pose"]["position"]
            message.pose.pose.position.x = position["x"]
            message.pose.pose.position.y = position["y"]
            orientation = rows["pose"]["orientation"]
            message.pose.pose.orientation.z = orientation["z"]
            message.pose.pose.orientation.w = orientation["w"]
            message.twist.twist.linear.x = rows["twist"]["linear"]["x"]
            message.twist.twist.angular.z = rows["twist"]["angular"]["z"]
            return message

        def speed_limit(self, row):
            message = SpeedLimit()
            message.speed_limit = row["speed_limit"]
            message.percentage = row["percentage"]
            return message

        def nav_goal(self, frame_id, stamp, map_pose, behavior_tree):
            goal = NavigateToPose.Goal()
            goal.behavior_tree = behavior_tree
            goal.pose.header.frame_id = frame_id
            goal.pose.header.stamp = stamp
            goal.pose.pose.position.x = map_pose[0]
            goal.pose.pose.position.y = map_pose[1]
            goal.pose.pose.orientation.z = math.sin(map_pose[2] / 2.0)
            goal.pose.pose.orientation.w = math.cos(map_pose[2] / 2.0)
            return goal

        def result_of(self, result):
            code = getattr(result.result, "error_code", -1)
            return result.status, code

    return Messages()


def _selftest(args):
    """The wiring table, printed. No graph, no spin, no simulator."""
    vid = args.vid or "f1"
    cfg = vehicle_config(vid)
    rows = wiring(cfg, vid)
    fails = []
    print("nav2_adapter wiring for {} (namespace /{})".format(vid, vid))
    for row in rows:
        if row.kind == "expect":
            continue
        resolved = (row.address if row.address.startswith("/")
                    else "/{}/{}".format(vid, row.address))
        note = ""
        if row.address in ("tf", "tf_static"):
            # The one row whose namespaced form is NOT where it lands.
            note = "  -> /{} (truck.sh -r {}:=/{})".format(
                row.address, row.address, row.address)
        print("  {:7s} {:18s} {:26s} {}{}".format(
            row.kind, row.label, resolved, row.msg, note))
    expected = dict((row.label, row.address) for row in rows
                    if row.kind == "expect")
    print("what the fleet layer reads (status_contract.contract):")
    for label in sorted(expected):
        mine = "/{}/{}".format(vid, label)
        ok = mine == expected[label]
        if not ok:
            fails.append(label)
        print("  {}  {:26s} {}".format("pass" if ok else "FAIL",
                                       expected[label], mine))
    # Every callback the table names has to exist, or build() would
    # raise inside a constructor at bringup instead of here.
    adapter_methods = [row.label for row in rows if row.kind == "sub"]
    for label in adapter_methods:
        if not hasattr(Adapter, "cb_" + label):
            fails.append("cb_" + label)
            print("FAIL  Adapter has no cb_{}".format(label))
    print("remaps truck.sh puts on this child: {}".format(
        " ".join("-r {}:={}".format(a, b) for a, b in NS_REMAPS)))
    print("cores: state={} legs={} cmd={} pose={} watch={}".format(
        nav2_state.__name__, nav2_legs.__name__, nav2_cmd.__name__,
        nav2_pose.__name__, nav2_watch.__name__))
    print("{} rows, {} problems".format(len(rows), len(fails)))
    return 1 if fails else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = _parser().parse_args(own_args(argv))
    if args.selftest:
        return _selftest(args)
    parser = _parser()
    if not args.vid:
        parser.error("--vid is required (m6_ver2/truck.sh passes it)")
    if not args.world_frame:
        parser.error(
            "--world-frame is required and has no default: the estimate "
            "rides a shared /tf tree with per-truck prefixed frames "
            "(AMR-DEC-006), so an unnamed frame is a message four "
            "trucks would answer to")
    cfg = vehicle_config(args.vid)
    try:
        import rclpy
        from rclpy.executors import ExternalShutdownException
        from rclpy.node import Node
    except ImportError as exc:
        import _common
        _common.refuse(
            TOOL, "rclpy is importable", "{} (paths.ros_setup)".format(
                _common.CONFIG),
            "python3 could not import ROS 2: {}".format(exc),
            "this node runs INSIDE WSL with /opt/ros/jazzy sourced -",
            "m6_ver2/truck.sh sources it before it spawns this child.")
    rclpy.init(args=sys.argv)
    # use_sim_time ARRIVES AS A `-p` FROM truck.sh, which is this
    # track's idiom for every other child on the stack: a fact about
    # THIS STACK (there is a bridged /clock) rather than about this
    # node, set where the stack is decided.
    node = Node("nav2_adapter")
    adapter = Adapter(node, _messages(), cfg, args.vid, args.world_frame)
    adapter.build(wiring(cfg, args.vid))
    node.get_logger().info(
        "nav2 adapter up on /{}: {} legs table, arrive_m {:.2f}, "
        "watchdog {:.2f} m / {:.0f} s, world frame {}".format(
            args.vid, "/".join(nav2_legs.CLASS_TREE),
            follower.ARRIVE_M, adapter.required_closing_m,
            adapter.closing_allowance_s, args.world_frame))
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        # SIGTERM IS HOW THIS NODE IS NORMALLY ENDED - truck.sh's stop
        # sweeps it with TERM - and an uncaught ExternalShutdownException
        # would put a traceback at the end of every clean stop.
        pass
    finally:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:                                 # pragma: no cover
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
