#!/usr/bin/env python3
"""monitor_demo.py - put a box in front of the truck and watch the guard.

    python3 m5_ver3/tools/monitor_demo.py describe          # needs nothing
    python3 m5_ver3/tools/monitor_demo.py record            # needs ROS
    python3 m5_ver3/tools/monitor_demo.py analyse           # needs nothing

WHAT IT IS FOR. F4 Task 3 puts `nav2_collision_monitor` between the
velocity smoother and the tricycle converter, and this is the instrument
that says what that node actually did. A 2.40 m box is spawned into the
running world, a constant twist is driven at the top of the command
path, and every joint of the chain is recorded on either side of the
monitor:

    this bench          -> topics.cmd_vel          (the COMMANDER)
      velocity_smoother -> topics.cmd_vel_smoothed (the monitor's IN)
        collision_monitor -> topics.cmd_vel_monitored (its OUT)
          cmd_vel_tricycle -> topics.steer_cmd + topics.traction_cmd
    and beside them topics.collision_monitor_state (what it SAYS it did)
    and topics.odom_ground_truth (what the TRUCK did)

THE MEASUREMENT IS THE RATIO OF TWO ADJACENT STREAMS. `cmd_vel_smoothed`
is what the monitor was handed and `cmd_vel_monitored` is what it passed
on; their ratio is 1.0 when it is doing nothing, `slowdown_ratio` when it
is slowing and 0.0 when it is stopping. Everything else this file
reports - where the truck stopped, how big the gap was, how long the
release took - is that ratio read against the ground truth.

=======================================================================
IT IS NOT A SAFETY DEMONSTRATION AND NOTHING HERE IS A SAFETY FUNCTION
=======================================================================
nav2's own documentation for the node under test, quoted verbatim:

    "does not provide hard real-time safety certifications"

It does not replace a safety-rated PLC. It complements the F-PLC; it is
not the F-PLC. Protective stop, e-stop and safe torque off are onboard
and hardwired in the plant this models, and nothing on this path can
trigger or release one. What is measured below is a CONVENIENCE function
reading a 15 Hz scan over a DDS graph in a simulator.
  AND IT WATCHES ONE PLANE. The nav lidar sits at z = 1.80 m and the two
safety scanners at z = 0.15 m are not bridged to ROS at all, so a
pallet, a dropped load and a person are invisible to this node. The
demonstration box is 2.40 m tall FOR THAT REASON and the height is
stated rather than arranged quietly.

WHY IT DRIVES A TWIST RATHER THAN A GOAL. tools/drive_goal.py measures a
closed loop, where the speed is the controller's business and changes
for reasons of its own; here the commanded speed has to be a CONSTANT or
the ratio above is not a measurement of anything. It is
tools/drive_twist.py's argument (a table that cannot respond) applied to
a node that responds - and, like that bench, it is the ONLY publisher on
topics.cmd_vel while it runs, which is why `--nav` is refused: a
controller and a bench on one address is a race, not an experiment
(F4 constraint 18).

WHAT LEAVING IT IS. Every exit path publishes ONE standing zero and then
removes the box. The zero is the same command drive_twist.py ends its
own profiles with; the box is removed because a world left with an
obstacle in the north ring leg would silently change the next driven
goal on this rig.
"""
import argparse
import collections
import datetime
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as ec                            # noqa: E402

TOOL = "monitor_demo"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.ros_domain_id",
    "world.name",
    "topics.cmd_vel", "topics.cmd_vel_smoothed", "topics.cmd_vel_monitored",
    "topics.collision_monitor_state",
    "topics.steer_cmd", "topics.traction_cmd", "topics.odom_ground_truth",
    "vehicle.spawn.x", "vehicle.spawn.y",
    "monitor.params_file", "monitor.node_name",
    "monitor.geometry.fork_tip_x_m", "monitor.geometry.counterweight_x_m",
    "monitor.geometry.half_width_m", "monitor.geometry.lateral_margin_m",
    "monitor.speeds.transit_mps", "monitor.speeds.cruise_mps",
    "monitor.stop_m.transit", "monitor.stop_m.cruise",
    "monitor.slowdown_m.transit", "monitor.slowdown_m.cruise",
    "monitor.slowdown_ratio", "monitor.min_points",
    "monitor.obstacle.name", "monitor.obstacle.size_x_m",
    "monitor.obstacle.size_y_m", "monitor.obstacle.size_z_m",
    "monitor.obstacle.x_m", "monitor.obstacle.y_m",
    "monitor.demo.speed_mps", "monitor.demo.approach_s",
    "monitor.demo.release_s", "monitor.demo.settle_s",
    "monitor.demo.rate_hz",
    "evidence.dir", "evidence.wait_first_s",
    "timing.spawn_service_timeout_ms",
    "paths.traction_file",
)

#: nav2_msgs/CollisionMonitorState's own action codes. They are the
#: node's and not this file's, which is why they are spelled here rather
#: than in config.yaml: an enum in a message definition is not a
#: behavioural constant this track owns.
ACTIONS = {0: "DO_NOTHING", 1: "STOP", 2: "SLOWDOWN", 3: "APPROACH",
           4: "LIMIT"}

STREAMS = collections.OrderedDict((
    ("cmd_vel", ("t_s", "v_mps", "w_radps")),
    ("cmd_vel_smoothed", ("t_s", "v_mps", "w_radps")),
    ("cmd_vel_monitored", ("t_s", "v_mps", "w_radps")),
    ("steer_cmd", ("t_s", "steer_rad")),
    ("traction_cmd", ("t_s", "wheel_radps")),
    ("ground_truth", ("t_s", "x", "y", "yaw", "vx")),
    ("state", ("t_s", "action", "polygon_id")),
))

#: The one stream that may be empty, and only because of what it means.
#: The monitor publishes its state on every processing cycle, so an
#: empty `state` is a monitor that never processed anything - which is a
#: finding and not a fault in the reader.
ALLOW_EMPTY = ("state",)


# ----------------------------------------------------------------------
# the arithmetic, and it needs no ROS
# ----------------------------------------------------------------------

def polygon_depths(cfg):
    """The four zone depths and the half width, off config.yaml alone.

    THE ONE PLACE THE POLYGONS ARE COMPUTED, and
    tests/test_collision_monitor_params.py checks
    collision_monitor.yaml's own vertices against exactly this. A
    polygon edited in the yaml and not here is a test failure rather
    than a quiet divergence.
    """
    return {
        "fork_tip": cfg.f("monitor.geometry.fork_tip_x_m"),
        "counterweight": cfg.f("monitor.geometry.counterweight_x_m"),
        "half_width": (cfg.f("monitor.geometry.half_width_m")
                       + cfg.f("monitor.geometry.lateral_margin_m")),
        "stop_transit": cfg.f("monitor.stop_m.transit"),
        "stop_cruise": cfg.f("monitor.stop_m.cruise"),
        "slowdown_transit": cfg.f("monitor.slowdown_m.transit"),
        "slowdown_cruise": cfg.f("monitor.slowdown_m.cruise"),
    }


def rectangle(near_x, depth, half_width, forward):
    """One zone as four vertices in base_link, the way nav2 reads them.

    `forward` is FORKS-FIRST, which is base_link -x on this vehicle and
    nav2's own REVERSE. The rectangle runs from a BODY EDGE outward and
    never encloses the hull, which is what keeps the three self-returns
    the nav scanner sees out of every polygon in this file
    (EVIDENCE_NAV_V3.md 14.4).
    """
    far = near_x - depth if forward else near_x + depth
    return [(near_x, half_width), (far, half_width),
            (far, -half_width), (near_x, -half_width)]


def gap_to_obstacle(x, y, yaw, box_x, box_y, box_sx, box_sy, fork_tip_x):
    """Metres from the FORK TIPS to the near face of the box, along x.

    A SCALAR AND NOT A DISTANCE BETWEEN CENTRES, because the polygon is
    a rectangle in front of the tines and the number that matters is how
    much of it is left. The demo drives due east down a straight leg
    with the forks leading, so the near face is the box's own -x face
    and this is a subtraction; a run that had turned would need the
    polygon test itself, and this file does not pretend otherwise.
    """
    tip_x = x + math.cos(yaw + math.pi) * abs(fork_tip_x)
    return (box_x - box_sx / 2.0) - tip_x


def phases(state_rows):
    """[(action, t_first, t_last, n)] - the run as a list of phases.

    THE INSTRUMENT THE WHOLE DEMONSTRATION IS SCORED BY. The monitor
    publishes one state per cycle; what a reader wants is the three or
    four RUNS of them - clear, slowing, stopped, clear again - with the
    instant of each handover, because those instants are what get
    compared against the polygon depths.
    """
    out = []
    for t, action, _poly in state_rows:
        code = int(action)
        if out and out[-1][0] == code:
            out[-1][2] = float(t)
            out[-1][3] += 1
        else:
            out.append([code, float(t), float(t), 1])
    return [tuple(row) for row in out]


def ratio_at(in_rows, out_rows, t, span_s):
    """(mean out / mean in) over [t, t+span_s), or None.

    THE RATIO IS TAKEN OVER A WINDOW AND NOT AT A SAMPLE. The two
    streams are published by two nodes at their own moments, so a
    sample-to-sample division would be reading one node's jitter as the
    other's behaviour.
    """
    def mean(rows):
        inside = [abs(row[1]) for row in rows if t <= row[0] < t + span_s]
        return sum(inside) / len(inside) if inside else None
    top, bottom = mean(out_rows), mean(in_rows)
    if top is None or bottom is None or bottom == 0.0:
        return None
    return top / bottom


# ----------------------------------------------------------------------
# the world, and the box in it
# ----------------------------------------------------------------------

def box_sdf(cfg):
    """The demonstration obstacle as one SDF string.

    IT IS BUILT HERE AND NOT KEPT AS A FILE, because it is not a model
    this track owns - it is four numbers out of config.yaml wrapped in
    the least SDF gz will accept. And it is STATIC: a box with mass that
    the truck could push is a collision experiment, and this is a
    monitor experiment.
    """
    sx = cfg.f("monitor.obstacle.size_x_m")
    sy = cfg.f("monitor.obstacle.size_y_m")
    sz = cfg.f("monitor.obstacle.size_z_m")
    name = cfg.s("monitor.obstacle.name")
    return (
        '<?xml version="1.0"?><sdf version="1.9">'
        '<model name="{n}"><static>true</static>'
        '<link name="body"><collision name="c"><geometry><box><size>'
        '{x} {y} {z}</size></box></geometry></collision>'
        '<visual name="v"><geometry><box><size>{x} {y} {z}</size></box>'
        '</geometry><material><ambient>0.8 0.2 0.1 1</ambient>'
        '<diffuse>0.8 0.2 0.1 1</diffuse></material></visual>'
        '</link></model></sdf>'.format(n=name, x=sx, y=sy, z=sz))


def gz_call(cfg, service, reqtype, req):
    """One gz-transport service call, captured and matched.

    THE REPLY IS CAPTURED AND MATCHED, NEVER PIPED INTO A `grep -q` -
    m5v3.sh's spawn_truck() rule and its measured reason. `data: true`
    says the REQUEST was accepted and never that the world is now what
    the caller wanted, so the caller checks the world afterwards.
    """
    cmd = ["gz", "service", "-s", service,
           "--reqtype", reqtype, "--reptype", "gz.msgs.Boolean",
           "--timeout", str(cfg.s("timing.spawn_service_timeout_ms")),
           "--req", req]
    try:
        reply = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=30).stdout
    except Exception as exc:                      # pragma: no cover
        return "gz service failed: {}".format(exc)
    return reply


def spawn_box(cfg):
    x = cfg.f("monitor.obstacle.x_m")
    y = cfg.f("monitor.obstacle.y_m")
    z = cfg.f("monitor.obstacle.size_z_m") / 2.0
    req = ('sdf: "{sdf}", name: "{n}", allow_renaming: false, '
           'pose: {{position: {{x: {x}, y: {y}, z: {z}}}}}').format(
               sdf=box_sdf(cfg).replace('"', '\\"'),
               n=cfg.s("monitor.obstacle.name"), x=x, y=y, z=z)
    return gz_call(cfg, "/world/{}/create".format(cfg.s("world.name")),
                   "gz.msgs.EntityFactory", req)


def remove_box(cfg):
    req = 'name: "{}", type: MODEL'.format(cfg.s("monitor.obstacle.name"))
    return gz_call(cfg, "/world/{}/remove".format(cfg.s("world.name")),
                   "gz.msgs.Entity", req)


# ----------------------------------------------------------------------
# describe
# ----------------------------------------------------------------------

def describe(cfg):
    d = polygon_depths(cfg)
    print("=== m5v3 collision monitor ===")
    print("")
    print("IT IS NOT A SAFETY FUNCTION. nav2's own words for this node,")
    print("verbatim: it \"does not provide hard real-time safety")
    print("certifications\". It does not replace a safety-rated PLC. It")
    print("complements the F-PLC; it is not the F-PLC.")
    print("")
    print("body       fork tips x = {:+.3f}   counterweight x = {:+.3f}"
          .format(d["fork_tip"], d["counterweight"]))
    print("           half width {:.3f} = hull {:.3f} + {:.3f} of scanner "
          "noise (3 sigma)".format(
              d["half_width"], cfg.f("monitor.geometry.half_width_m"),
              cfg.f("monitor.geometry.lateral_margin_m")))
    print("")
    print("zone                       depth   from      to        (base_link x)")
    for label, near, depth, forward in (
            ("STOP     forks transit", d["fork_tip"], d["stop_transit"], True),
            ("STOP     forks cruise", d["fork_tip"], d["stop_cruise"], True),
            ("STOP     c/w   transit", d["counterweight"], d["stop_transit"],
             False),
            ("STOP     c/w   cruise", d["counterweight"], d["stop_cruise"],
             False),
            ("SLOWDOWN forks transit", d["fork_tip"], d["slowdown_transit"],
             True),
            ("SLOWDOWN forks cruise", d["fork_tip"], d["slowdown_cruise"],
             True),
            ("SLOWDOWN c/w   transit", d["counterweight"],
             d["slowdown_transit"], False),
            ("SLOWDOWN c/w   cruise", d["counterweight"],
             d["slowdown_cruise"], False)):
        poly = rectangle(near, depth, d["half_width"], forward)
        print("  {:<24} {:.2f} m  {:+.3f}   {:+.3f}".format(
            label, depth, poly[0][0], poly[1][0]))
    print("")
    print("slowdown   x {:.6f}  = transit {:.3f} / cruise {:.3f}".format(
        cfg.f("monitor.slowdown_ratio"), cfg.f("monitor.speeds.transit_mps"),
        cfg.f("monitor.speeds.cruise_mps")))
    print("trigger    {} scan points inside a zone".format(
        cfg.s("monitor.min_points")))
    print("")
    print("obstacle   {} - {} x {} x {} m at ({:+.2f}, {:+.2f}), STATIC"
          .format(cfg.s("monitor.obstacle.name"),
                  cfg.s("monitor.obstacle.size_x_m"),
                  cfg.s("monitor.obstacle.size_y_m"),
                  cfg.s("monitor.obstacle.size_z_m"),
                  cfg.f("monitor.obstacle.x_m"),
                  cfg.f("monitor.obstacle.y_m")))
    print("           IT IS 2.40 m TALL BECAUSE THE SCAN PLANE IS 1.80 m. "
          "A shorter box")
    print("           is invisible to this node and the demonstration "
          "would measure")
    print("           nothing. The two safety scanners that WOULD see a "
          "pallet sit at")
    print("           z = 0.15 m and are not bridged to ROS at all.")
    print("")
    tips = cfg.f("vehicle.spawn.x") + abs(d["fork_tip"])
    face = cfg.f("monitor.obstacle.x_m") - cfg.f("monitor.obstacle.size_x_m") / 2.0
    print("approach   fork tips start at x = {:+.3f}, the box's near face "
          "is at {:+.3f}".format(tips, face))
    print("           so the gap at t0 is {:.3f} m and the drive is "
          "{:+.3f} m/s".format(face - tips, -cfg.f("monitor.demo.speed_mps")))
    print("           (NEGATIVE is forks-first, which is nav2's REVERSE "
          "and this")
    print("           truck's ordinary direction of travel)")
    return 0


# ----------------------------------------------------------------------
# record
# ----------------------------------------------------------------------

def record(cfg):
    try:
        import time

        import rclpy
        from geometry_msgs.msg import Twist
        from nav2_msgs.msg import CollisionMonitorState
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
        from rclpy.qos import QoSProfile
        from std_msgs.msg import Float64
    except ImportError as exc:
        cfg.refuse("rclpy, nav2_msgs and gz are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced. "
                   "`analyse` needs neither.")

    describe(cfg)
    print("")

    # THE LABEL CHAIN, AND THE ONE REFUSAL THIS BENCH ADDS TO IT. A
    # stack with `monitor=off` has no such node on it, so every figure
    # below would be the command path relaying itself - which looks
    # exactly like a monitor watching an empty floor.
    state_path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(state_path):
        cfg.refuse("the stack said which plant it is", state_path,
                   "there is no state file, so this stack was not started "
                   "by 'm5v3.sh start'.",
                   "An unlabelled session is worse than none.")
    with open(state_path, encoding="utf-8") as handle:
        stack = ec.parse_state_file(handle.read())
    if stack.get("monitor", "off") == "off":
        cfg.refuse("the running stack has a collision monitor in its "
                   "command path", state_path,
                   "its monitor= line reads `off`, so nothing sits "
                   "between the smoother and the",
                   "converter and every ratio this bench computes would "
                   "be 1.0 by construction.",
                   "  bash m5_ver3/m5v3.sh stop",
                   "  bash m5_ver3/m5v3.sh start --headless --monitor")
    if stack.get("nav", "off") != "off":
        cfg.refuse("nothing else is publishing on the command path",
                   state_path + " and " + _common.CONFIG + " (topics.cmd_vel)",
                   "its nav= line reads `{}`, so a controller_server is "
                   "alive and".format(stack["nav"]),
                   "subscribed to the same address this bench publishes "
                   "on. Two publishers on",
                   "one topic is a race and not an experiment (F4 "
                   "constraint 18).",
                   "  bash m5_ver3/m5v3.sh stop",
                   "  bash m5_ver3/m5v3.sh start --headless --monitor")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session = "monitor-{}".format(stamp)
    path = os.path.join(_common.REPO, cfg.s("evidence.dir"), session)
    os.makedirs(path)
    print("session    {}".format(path))

    rclpy.init(args=None)
    node = Node("m5v3_monitor_demo")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    qos = QoSProfile(depth=50)
    captured = collections.OrderedDict((name, []) for name in STREAMS)

    def now_s():
        return node.get_clock().now().nanoseconds * 1e-9

    def yaw_of(q):
        return math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                          1.0 - 2.0 * (q.y * q.y + q.z * q.z))

    node.create_subscription(
        Twist, cfg.s("topics.cmd_vel"),
        lambda m: captured["cmd_vel"].append(
            (now_s(), m.linear.x, m.angular.z)), qos)
    node.create_subscription(
        Twist, cfg.s("topics.cmd_vel_smoothed"),
        lambda m: captured["cmd_vel_smoothed"].append(
            (now_s(), m.linear.x, m.angular.z)), qos)
    node.create_subscription(
        Twist, cfg.s("topics.cmd_vel_monitored"),
        lambda m: captured["cmd_vel_monitored"].append(
            (now_s(), m.linear.x, m.angular.z)), qos)
    node.create_subscription(
        Float64, cfg.s("topics.steer_cmd"),
        lambda m: captured["steer_cmd"].append((now_s(), m.data)), qos)
    node.create_subscription(
        Float64, cfg.s("topics.traction_cmd"),
        lambda m: captured["traction_cmd"].append((now_s(), m.data)), qos)
    node.create_subscription(
        Odometry, cfg.s("topics.odom_ground_truth"),
        lambda m: captured["ground_truth"].append(
            (float(m.header.stamp.sec) + m.header.stamp.nanosec * 1e-9,
             m.pose.pose.position.x, m.pose.pose.position.y,
             yaw_of(m.pose.pose.orientation), m.twist.twist.linear.x)), qos)
    node.create_subscription(
        CollisionMonitorState, cfg.s("topics.collision_monitor_state"),
        lambda m: captured["state"].append(
            (now_s(), float(m.action_type),
             float(len(m.polygon_name)))), qos)
    publisher = node.create_publisher(Twist, cfg.s("topics.cmd_vel"), qos)

    wait_s = cfg.f("evidence.wait_first_s")
    deadline = time.monotonic() + wait_s
    while not captured["ground_truth"] or now_s() <= 0.0:
        if time.monotonic() > deadline:
            cfg.refuse("the plant reached this bench within {:g}s".format(
                           wait_s),
                       "{} on domain {}".format(
                           cfg.s("topics.odom_ground_truth"),
                           cfg.s("isolation.ros_domain_id")),
                       "is the stack up? 'bash m5_ver3/m5v3.sh status'")
        rclpy.spin_once(node, timeout_sec=0.05)

    # THE BOX GOES IN BEFORE ANYTHING IS COMMANDED, and that is the
    # deterministic order. Spawned mid-drive it would appear at a
    # distance nobody chose, at the mercy of the real-time factor; put
    # there first, the vehicle drives into a zone whose geometry the
    # approach table above has already predicted.
    print("obstacle   spawning {}".format(cfg.s("monitor.obstacle.name")))
    reply = spawn_box(cfg)
    if "data: true" not in reply:
        cfg.refuse("gz accepted the obstacle", "/world/{}/create".format(
                       cfg.s("world.name")),
                   "the reply was: {}".format(reply.strip() or "(nothing)"),
                   "is the world running? 'bash m5_ver3/m5v3.sh status'")
    settle_s = cfg.f("monitor.demo.settle_s")
    end = now_s() + settle_s
    while now_s() < end:
        rclpy.spin_once(node, timeout_sec=0.05)

    for name in captured:
        captured[name] = []
    t0 = now_s()
    speed = cfg.f("monitor.demo.speed_mps")
    approach_s = cfg.f("monitor.demo.approach_s")
    release_s = cfg.f("monitor.demo.release_s")
    period = 1.0 / cfg.f("monitor.demo.rate_hz")
    twist = Twist()
    # FORKS-FIRST IS NEGATIVE. nav2's forward is this truck's reverse
    # and config.yaml's monitor.demo.speed_mps is written as a SPEED, so
    # the sign is added here, once, exactly as drive_goal.pose_yaw()
    # adds the half turn.
    twist.linear.x = -abs(speed)

    print("drive      {:+.3f} m/s for {:g} s, then the box is REMOVED and "
          "the same".format(twist.linear.x, approach_s))
    print("           command runs {:g} s more. This bench is the ONLY "
          "publisher on {}".format(release_s, cfg.s("topics.cmd_vel")))
    t_removed = None
    while now_s() < t0 + approach_s + release_s:
        if t_removed is None and now_s() >= t0 + approach_s:
            print("obstacle   removing it at t = {:.3f} s".format(now_s()))
            t_removed = now_s()
            reply = remove_box(cfg)
            if "data: true" not in reply:
                print("           gz did not accept the removal: {}".format(
                    reply.strip()))
        publisher.publish(twist)
        end = now_s() + period
        while now_s() < end:
            rclpy.spin_once(node, timeout_sec=0.01)

    # THE STANDING ZERO, which is drive_twist.py's own way out: the last
    # command a profile leaves is the one the converter ramps to and the
    # plant holds.
    print("stop       one standing zero, then {:g} s of settle".format(
        settle_s))
    zero = Twist()
    t_zero = now_s()
    end = now_s() + settle_s
    while now_s() < end:
        publisher.publish(zero)
        inner = now_s() + period
        while now_s() < inner:
            rclpy.spin_once(node, timeout_sec=0.01)

    # AND THE BOX IS REMOVED AGAIN ON THE WAY OUT, unconditionally. It
    # has already gone above on a run that got that far; a run that did
    # not would leave an obstacle standing in the north ring leg, where
    # it would silently change every driven goal taken on this rig
    # afterwards.
    remove_box(cfg)

    for stream, columns in STREAMS.items():
        with open(os.path.join(path, stream + ".csv"), "w",
                  encoding="utf-8", newline="") as out:
            out.write(",".join(columns) + "\n")
            for row in captured[stream]:
                out.write(",".join("{:.9f}".format(v) for v in row) + "\n")
    with open(os.path.join(path, "session.txt"), "w",
              encoding="utf-8") as out:
        out.write("kind=monitor\n")
        out.write("t0_s={:.9f}\n".format(t0))
        out.write("t_removed_s={:.9f}\n".format(
            t_removed if t_removed is not None else -1.0))
        out.write("t_zero_s={:.9f}\n".format(t_zero))
        out.write("commanded_mps={:.9f}\n".format(twist.linear.x))
        out.write("obstacle_x_m={:.9f}\n".format(
            cfg.f("monitor.obstacle.x_m")))
        out.write("obstacle_y_m={:.9f}\n".format(
            cfg.f("monitor.obstacle.y_m")))
        out.write("obstacle_size_x_m={:.9f}\n".format(
            cfg.f("monitor.obstacle.size_x_m")))
        out.write("obstacle_size_y_m={:.9f}\n".format(
            cfg.f("monitor.obstacle.size_y_m")))
        for key, value in stack.items():
            out.write("{}={}\n".format(key, value))
        out.write("recorded={}\n".format(datetime.datetime.now().isoformat()))
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("")
    for stream in STREAMS:
        print("  {:<20} {} rows".format(stream, len(captured[stream])))
    print("")
    print("analyse it:  python3 m5_ver3/tools/monitor_demo.py analyse {}"
          .format(session))
    return 0


# ----------------------------------------------------------------------
# analyse
# ----------------------------------------------------------------------

def sessions_in(cfg):
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    if not os.path.isdir(root):
        return []
    return sorted(name for name in os.listdir(root)
                  if name.startswith("monitor-")
                  and os.path.isfile(os.path.join(root, name, "session.txt")))


def analyse(cfg, names):
    found = names or sessions_in(cfg)
    if not found:
        cfg.refuse("there is a recorded monitor session to analyse",
                   os.path.join(_common.REPO, cfg.s("evidence.dir")),
                   "nothing there begins with `monitor-`.",
                   "record one: python3 m5_ver3/tools/monitor_demo.py record")
    for name in found:
        analyse_session(cfg, name)
    return 0


def analyse_session(cfg, session):
    path = os.path.join(_common.REPO, cfg.s("evidence.dir"), session)
    tables = {s: ec.read_csv(os.path.join(path, s + ".csv"),
                             allow_empty=s in ALLOW_EMPTY)
              for s in STREAMS}
    with open(os.path.join(path, "session.txt"), encoding="utf-8") as handle:
        fields = ec.parse_state_file(handle.read())

    def rows(stream, columns):
        cols = [tables[stream].column(c) for c in columns]
        return list(zip(*cols)) if cols and cols[0] else []

    d = polygon_depths(cfg)
    t0 = float(fields["t0_s"])
    t_removed = float(fields["t_removed_s"])
    commanded = float(fields["commanded_mps"])
    box_x = float(fields["obstacle_x_m"])
    box_y = float(fields["obstacle_y_m"])
    box_sx = float(fields["obstacle_size_x_m"])
    box_sy = float(fields["obstacle_size_y_m"])

    cmd_in = rows("cmd_vel_smoothed", ("t_s", "v_mps"))
    cmd_out = rows("cmd_vel_monitored", ("t_s", "v_mps"))
    truth = rows("ground_truth", ("t_s", "x", "y", "yaw", "vx"))
    state = rows("state", ("t_s", "action", "polygon_id"))
    traction = rows("traction_cmd", ("t_s", "wheel_radps"))

    print("")
    print("=== {} ===".format(session))
    print("monitor   {}".format(fields.get("monitor", "UNLABELLED")))
    print("stack     traction {}  arm {}  loc {}  nav {}".format(
        fields.get("traction", "?"), fields.get("arm", "?"),
        fields.get("loc", "?"), fields.get("nav", "?")))
    print("commanded {:+.4f} m/s, constant, published by this bench alone"
          .format(commanded))
    print("")
    print("THIS IS NOT A SAFETY MEASUREMENT. nav2's own words for the node")
    print("under test: it \"does not provide hard real-time safety")
    print("certifications\". It does not replace a safety-rated PLC.")
    print("")

    if not state:
        print("STATE     the monitor published NO state at all. On this "
              "arm that is a")
        print("          node that never processed a twist - read "
              "m5_ver3/logs/monitor.log.")
        return 1

    print("PHASES    what the monitor said it was doing, in order")
    print("          action        from      to      n     out/in over "
          "the phase")
    for code, t_first, t_last, n in phases(state):
        ratio = ratio_at(cmd_in, cmd_out, t_first, max(t_last - t_first, 0.05))
        print("          {:<12} t+{:6.2f}  t+{:6.2f}  {:>4}   {}".format(
            ACTIONS.get(code, str(code)), t_first - t0, t_last - t0, n,
            "{:.4f}".format(ratio) if ratio is not None else "-"))
    print("          out/in is topics.cmd_vel_monitored over "
          "topics.cmd_vel_smoothed:")
    print("          1.0 is a relay, {:.4f} is the configured slowdown, "
          "0.0 is a stop.".format(cfg.f("monitor.slowdown_ratio")))

    # WHERE THE VEHICLE WAS WHEN EACH HANDOVER HAPPENED, against the
    # polygon depth that is supposed to have caused it. This is the row
    # the whole design is checked by.
    def truth_at(t):
        best = None
        for row in truth:
            if row[0] <= t:
                best = row
            else:
                break
        return best

    print("")
    print("GEOMETRY  the gap from the FORK TIPS to the box's near face at "
          "each handover,")
    print("          against the zone depth that is supposed to have "
          "caused it")
    print("          action        gap      zone depth   difference")
    seen = set()
    for code, t_first, _t_last, _n in phases(state):
        if code in seen or code == 0:
            continue
        seen.add(code)
        row = truth_at(t_first)
        if row is None:
            continue
        gap = gap_to_obstacle(row[1], row[2], row[3], box_x, box_y,
                              box_sx, box_sy, d["fork_tip"])
        depth = (d["stop_cruise"] if code == 1 else d["slowdown_cruise"])
        print("          {:<12} {:6.3f} m  {:6.3f} m    {:+.3f} m".format(
            ACTIONS.get(code, str(code)), gap, depth, gap - depth))
    print("          THE ZONE IS THE CRUISE ONE ON BOTH ROWS AND THAT IS "
          "THE FINDING.")
    print("          nav2's VelocityPolygon selects on the INCOMING "
          "command, which this")
    print("          bench holds at {:+.3f} m/s throughout - so the "
          "monitor's own".format(commanded))
    print("          slowdown does NOT shrink its own zone. Only a "
          "COMMANDER that asks")
    print("          for less does that.")

    # WHERE IT ACTUALLY STOPPED, which is the number a reader wants.
    still = [row for row in truth if abs(row[4]) < 0.01
             and row[0] > t0 + 1.0 and (t_removed < 0 or row[0] < t_removed)]
    print("")
    if still:
        row = still[0]
        gap = gap_to_obstacle(row[1], row[2], row[3], box_x, box_y,
                              box_sx, box_sy, d["fork_tip"])
        print("STOPPED   at t+{:.2f} s, fork tips {:.3f} m from the box's "
              "near face".format(row[0] - t0, gap))
        print("          world ({:+.3f}, {:+.3f}), |vx| < 0.010 m/s"
              .format(row[1], row[2]))
        print("          the STOP zone is {:.3f} m deep and the measured "
              "stopping distance".format(d["stop_cruise"]))
        print("          from the transit ceiling is 0.208 m "
              "(EVIDENCE_NAV_V3.md 8)")
    else:
        print("STOPPED   THE VEHICLE NEVER CAME TO REST while the box "
              "stood. That is a")
        print("          finding and not a reader fault - read the "
              "PHASES table above.")

    if t_removed > 0:
        after = [row for row in truth if row[0] > t_removed]
        moving = [row for row in after if abs(row[4]) > 0.05]
        print("")
        if moving:
            print("RELEASED  the box was removed at t+{:.2f} s and the "
                  "truck was moving again".format(t_removed - t0))
            print("          at t+{:.2f} s - {:.2f} s later, {:.4f} m/s"
                  .format(moving[0][0] - t0, moving[0][0] - t_removed,
                          moving[0][4]))
            top = max(abs(row[4]) for row in after)
            print("          and reached {:.4f} m/s against a commanded "
                  "{:.4f}".format(top, abs(commanded)))
        else:
            print("RELEASED  the box was removed at t+{:.2f} s and the "
                  "truck NEVER MOVED".format(t_removed - t0))
            print("          again. A guard that cannot be released is "
                  "worse than none.")

    print("")
    print("TERMINAL  what the traction terminal carried, which is the "
          "only place this")
    print("          demonstration is real - every hop above is a topic")
    if traction:
        values = [abs(row[1]) for row in traction]
        zeros = sum(1 for v in values if v < 1e-6)
        print("          {} samples, max {:.4f} rad/s, {} of them exactly "
              "zero".format(len(values), max(values), zeros))
    else:
        print("          NOTHING. The converter published no command at "
              "all.")
    print("")
    print("RELAY     with no obstacle in any zone the monitor is a RELAY, "
          "and this is")
    print("          the identity check: out over in, over the phase "
          "before the box")
    print("          was ever in range.")
    clear = [p for p in phases(state) if p[0] == 0]
    if clear:
        ratio = ratio_at(cmd_in, cmd_out, clear[0][1],
                         max(clear[0][2] - clear[0][1], 0.05))
        print("          {:.6f}".format(ratio) if ratio is not None
              else "          (no overlapping samples)")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="monitor_demo.py", description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    sub.add_parser("record")
    # THE BOX ON ITS OWN, FOR THE RUN THIS BENCH CANNOT DRIVE. `record`
    # refuses a `nav=on` stack, because a controller and a bench on one
    # /cmd_vel is a race - so the CLOSED-loop demonstration is
    # tools/drive_goal.py's, with the obstacle placed and removed from
    # outside it. Same two gz service calls, same config.yaml row, so
    # the two demonstrations cannot disagree about where the box is.
    obs = sub.add_parser("obstacle")
    obs.add_argument("what", choices=("place", "remove"))
    ana = sub.add_parser("analyse")
    ana.add_argument("sessions", nargs="*")
    args = parser.parse_args(argv)
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    if args.cmd == "describe":
        return describe(cfg)
    if args.cmd == "obstacle":
        reply = (spawn_box(cfg) if args.what == "place" else remove_box(cfg))
        print("{} {}: {}".format(args.what, cfg.s("monitor.obstacle.name"),
                                 reply.strip() or "(no reply)"))
        return 0 if "data: true" in reply else 1
    if args.cmd == "record":
        return record(cfg)
    if args.cmd == "analyse":
        return analyse(cfg, args.sessions)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
