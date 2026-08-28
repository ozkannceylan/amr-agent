#!/usr/bin/env python3
"""dock_bench.py - send opennav_docking a DockRobot, score the pose.

    python3 m5_ver3/tools/dock_bench.py describe
    python3 m5_ver3/tools/dock_bench.py record
    python3 m5_ver3/tools/dock_bench.py analyse [session]   # no ROS

Constraint 22: this bench cancels any NavigateToPose goal, waits for
/cmd_vel to go quiet, THEN sends DockRobot. Nav2's controller and the
docking controller share topics.cmd_vel; they must not both command.
The session's authority=dock line is that handover, labeled.

WHAT IT SCORES. Last ground-truth pose against tag_core's docked pose
(WORLD). Belief (`map` → `base_link` through the registration) beside
it. Station class is dock.station_class_m (F4's 0.25 m, revisited).
error_code is named (FAILED_TO_DETECT_DOCK, …) not left as 904.
"""
import argparse
import datetime
import math
import os
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_IPC = os.path.normpath(os.path.join(_HERE, os.pardir, os.pardir, "m6", "ipc"))
if _IPC not in sys.path:
    sys.path.insert(0, _IPC)

import _common                                        # noqa: E402
import dock_core as dc                                # noqa: E402
import evidence_core as ec                            # noqa: E402
import map_register                                   # noqa: E402
import stations                                       # noqa: E402

TOOL = "dock_bench"
REQUIRED_KEYS = (
    "dock.station", "dock.marker_ahead_m", "dock.fork_reach_m",
    "dock.tip_standoff_m", "dock.staging_run_in_m",
    "dock.station_class_m", "dock.record_timeout_s",
    "docking.dock_id", "docking.params_file", "docking.database_file",
    "topics.cmd_vel", "topics.odom_ground_truth", "topics.tf",
    "topics.dock_robot", "topics.undock_robot",
    "topics.detected_dock_pose", "topics.initialpose",
    "frames.map", "frames.odom", "frames.base_link",
    "map.dir", "map.name", "map.registration.file",
    "evidence.dir", "evidence.wait_first_s",
    "paths.traction_file",
    "vehicle.name", "vehicle.spawn.z", "world.name",
    "timing.spawn_service_timeout_ms",
    "localization.initial_pose.cov_x_m2",
    "localization.initial_pose.cov_y_m2",
    "localization.initial_pose.cov_yaw_rad2",
)


def _station(cfg):
    name = cfg.s("dock.station")
    table = stations.STATIONS
    if name not in table:
        cfg.refuse("dock.station is a key of m6/ipc/stations.py",
                   _common.CONFIG + " (dock.station)",
                   "it reads {!r}".format(name))
    return table[name]


def _docked(cfg):
    return dc.docked_world(_station(cfg), {
        "marker_ahead_m": cfg.s("dock.marker_ahead_m"),
        "fork_reach_m": cfg.s("dock.fork_reach_m"),
        "tip_standoff_m": cfg.s("dock.tip_standoff_m"),
        "staging_run_in_m": cfg.s("dock.staging_run_in_m"),
    })


def _map_frame(cfg):
    path = os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                        cfg.s("map.registration.file"))
    try:
        return ec.MapFrame.from_registration(
            map_register.load_registration(path))
    except Exception as exc:
        cfg.refuse("the committed registration belongs to the grid on disk",
                   path, str(exc))


def describe(cfg):
    pose = _docked(cfg)
    frame = _map_frame(cfg)
    mx, my, myaw = frame.to_map(pose["x"], pose["y"], pose["pose_yaw"])
    print("=== m5v3 dock bench ===")
    print("station   {}".format(cfg.s("dock.station")))
    print("dock_id   {}".format(cfg.s("docking.dock_id")))
    print("docked    ({:.3f}, {:.3f}) yaw {:+.4f} world".format(
        pose["x"], pose["y"], pose["pose_yaw"]))
    print("          ({:.3f}, {:.3f}) yaw {:+.4f} {}".format(
        mx, my, myaw, cfg.s("frames.map")))
    print("class     {:g} m".format(cfg.f("dock.station_class_m")))
    print("action    {}".format(cfg.s("topics.dock_robot")))
    return 0


def _load_last_pose(path):
    last = None
    with open(path, encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        for line in handle:
            parts = line.strip().split(",")
            rec = dict(zip(header, parts))
            last = rec
    if last is None:
        raise ValueError("ground_truth.csv is empty")
    return (float(last["x"]), float(last["y"]), float(last["yaw"]))


def analyse(cfg, session=None):
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    if session is None:
        names = sorted(
            n for n in os.listdir(root)
            if n.startswith("dock-") and os.path.isdir(os.path.join(root, n)))
        if not names:
            cfg.refuse("there is a recorded dock session to analyse",
                       root, "nothing there begins with `dock-`.")
        session = names[-1]
    folder = os.path.join(root, session)
    gt_path = os.path.join(folder, "ground_truth.csv")
    sess_path = os.path.join(folder, "session.txt")
    if not os.path.isfile(gt_path) or not os.path.isfile(sess_path):
        cfg.refuse("the session recorded ground_truth.csv and session.txt",
                   folder)
    with open(sess_path, encoding="utf-8") as handle:
        state = ec.parse_state_file(handle.read())
    if state.get("kind") != "dock":
        cfg.refuse("the session is a dock recording", sess_path,
                   "kind={!r}".format(state.get("kind")))
    target = _docked(cfg)
    try:
        end = _load_last_pose(gt_path)
    except ValueError as exc:
        cfg.refuse(str(exc), gt_path)
    dx, dy, dist, dyaw = dc.arrival(target, end)
    code = int(float(state.get("error_code", -1)))
    print("=== m5v3 dock bench / {} ===".format(session))
    print("target    ({:.3f}, {:.3f}) yaw {:+.4f}".format(
        target["x"], target["y"], target["pose_yaw"]))
    print("end       ({:.3f}, {:.3f}) yaw {:+.4f}".format(*end))
    print("truth     {:.4f} m   heading {:+.4f} rad".format(dist, dyaw))
    print("success   {}".format(state.get("success", "?")))
    print("error     {} ({})".format(code, dc.named_error(code)))
    print("retries   {}".format(state.get("num_retries", "?")))
    print("authority {}".format(state.get("authority", "?")))
    klass = cfg.f("dock.station_class_m")
    inside = dist <= klass
    print("class     {} inside {:g} m".format(
        "YES" if inside else "NO", klass))
    return 0


def stage(cfg):
    """Put the truck at T1 staging with the table heading, then seed AMCL.

    Nav2's position-only latch does not point the camera at S5 (T1).
    This is the same heading-aligned staging xy T1 used for the tag
    capture, so DockRobot's initial perception can start.
    """
    _live_state(cfg)
    pose = _docked(cfg)
    sx, sy = pose["staging"]
    yaw = pose["pose_yaw"]
    z = cfg.f("vehicle.spawn.z")
    name = cfg.s("vehicle.name")
    world = cfg.s("world.name")
    qz = math.sin(yaw / 2.0)
    qw = math.cos(yaw / 2.0)
    req = (
        'name: "{}", position: {{x: {:.9f}, y: {:.9f}, z: {:.9f}}}, '
        'orientation: {{z: {:.9f}, w: {:.9f}}}'
    ).format(name, sx, sy, z, qz, qw)
    cmd = [
        "gz", "service", "-s", "/world/{}/set_pose".format(world),
        "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
        "--timeout", str(cfg.s("timing.spawn_service_timeout_ms")),
        "--req", req,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        reply = (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:
        reply = str(exc)
    if "data: true" not in reply:
        cfg.refuse("gz set_pose put the truck at staging",
                   "/world/{}/set_pose".format(world),
                   reply or "<empty>")
    frame = _map_frame(cfg)
    mx, my, myaw = frame.to_map(sx, sy, yaw)
    (time, rclpy, _Twist, _Dock, _Nav, _Undock, _Odom, _AC, Node,
     _PoseStamped) = _import_ros(cfg)
    from geometry_msgs.msg import PoseWithCovarianceStamped
    rclpy.init(args=None)
    node = Node("m5v3_dock_stage")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    pub = node.create_publisher(
        PoseWithCovarianceStamped, cfg.s("topics.initialpose"), 1)
    msg = PoseWithCovarianceStamped()
    msg.header.frame_id = cfg.s("frames.map")
    msg.pose.pose.position.x = mx
    msg.pose.pose.position.y = my
    msg.pose.pose.orientation.z = math.sin(myaw / 2.0)
    msg.pose.pose.orientation.w = math.cos(myaw / 2.0)
    cov = [0.0] * 36
    cov[0] = cfg.f("localization.initial_pose.cov_x_m2")
    cov[7] = cfg.f("localization.initial_pose.cov_y_m2")
    cov[35] = cfg.f("localization.initial_pose.cov_yaw_rad2")
    msg.pose.covariance = cov
    end = time.time() + 2.0
    while time.time() < end:
        pub.publish(msg)
        rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("staged    world ({:.3f}, {:.3f}) yaw {:+.4f}".format(sx, sy, yaw))
    print("          map   ({:.3f}, {:.3f}) yaw {:+.4f}".format(mx, my, myaw))
    return 0


def _live_state(cfg):
    state_path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(state_path):
        cfg.refuse("the stack said which plant it is", state_path,
                   "there is no state file. m5v3.sh start writes it.")
    with open(state_path, encoding="utf-8") as handle:
        state = ec.parse_state_file(handle.read())
    if state.get("nav") == "off" or "nav" not in state:
        cfg.refuse("the running stack has a planner on it", state_path,
                   "nav={!r}".format(state.get("nav")),
                   "  bash m5_ver3/m5v3.sh start --headless "
                   "--localize --nav --dock")
    if not str(state.get("dock", "")).startswith("on@"):
        cfg.refuse("the running stack has --dock", state_path,
                   "dock={!r}".format(state.get("dock")),
                   "  bash m5_ver3/m5v3.sh start --headless "
                   "--localize --nav --dock")
    if not str(state.get("docking", "")).startswith("on@"):
        cfg.refuse("the running stack has the docking server", state_path,
                   "docking={!r}".format(state.get("docking")),
                   "a detector without opennav_docking is Task 1.")
    return state


def _import_ros(cfg):
    try:
        import time

        import rclpy
        from geometry_msgs.msg import Twist
        from nav2_msgs.action import DockRobot, NavigateToPose, UndockRobot
        from nav_msgs.msg import Odometry
        from rclpy.action import ActionClient
        from rclpy.node import Node
    except ImportError as exc:
        cfg.refuse("rclpy and nav2_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced. "
                   "`analyse` needs neither.")
    from geometry_msgs.msg import PoseStamped
    return (time, rclpy, Twist, DockRobot, NavigateToPose, UndockRobot,
            Odometry, ActionClient, Node, PoseStamped)


def _cancel_action(node, rclpy, name, wait_s):
    """Cancel every goal on an action. Jazzy ActionClient has no cancel-all."""
    from action_msgs.srv import CancelGoal
    client = node.create_client(CancelGoal, name + "/_action/cancel_goal")
    if not client.wait_for_service(timeout_sec=2.0):
        return
    future = client.call_async(CancelGoal.Request())
    rclpy.spin_until_future_complete(node, future, timeout_sec=wait_s)


def _align_for_tag(node, rclpy, Twist, PoseStamped, cfg, target_yaw,
                   captured, timeout_s):
    """Feasible arc until detected_dock_pose, or timeout.

    Constraint 22: caller has no DockRobot/Nav2 goal. v = -v_linear_min
    (forks-first) with align_omega so curvature respects the plant.
    Nav2's position-only latch is why this exists (T1 heading 0.67–1.37
    rad → 904, camera empty).
    """
    seen = {"ok": False}

    def on_det(_msg):
        seen["ok"] = True

    node.create_subscription(
        PoseStamped, cfg.s("topics.detected_dock_pose"), on_det, 10)
    pub = node.create_publisher(Twist, cfg.s("topics.cmd_vel"), 10)
    vmin = cfg.f("dock.v_linear_min")
    wmax = cfg.f("dock.v_angular_max")
    deadline = __import__("time").time() + timeout_s
    cmd = Twist()
    cmd.linear.x = -float(vmin)
    while rclpy.ok() and not seen["ok"] and __import__("time").time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if not captured["ground_truth"]:
            continue
        yaw = captured["ground_truth"][-1][3]
        cmd.angular.z = dc.align_omega(yaw, target_yaw, wmax)
        pub.publish(cmd)
    zero = Twist()
    for _ in range(10):
        pub.publish(zero)
        rclpy.spin_once(node, timeout_sec=0.05)
    return seen["ok"]


def record(cfg, dock_id=None, from_staging=False):
    (time, rclpy, Twist, DockRobot, _NavigateToPose, _UndockRobot,
     Odometry, ActionClient, Node, PoseStamped) = _import_ros(cfg)
    state = _live_state(cfg)

    wait_s = cfg.f("evidence.wait_first_s")
    budget_s = cfg.f("dock.record_timeout_s")
    want_id = dock_id or cfg.s("docking.dock_id")
    target = _docked(cfg)

    rclpy.init(args=None)
    node = Node("m5v3_dock_bench")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])

    captured = {"cmd_vel": [], "ground_truth": [], "feedback": []}
    last_motion = {"t": 0.0}

    def on_cmd(msg):
        t = node.get_clock().now().nanoseconds * 1e-9
        vx, wz = float(msg.linear.x), float(msg.angular.z)
        captured["cmd_vel"].append((t, vx, wz))
        if abs(vx) > 0.01 or abs(wz) > 0.01:
            last_motion["t"] = t

    def on_gt(msg):
        t = msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        yaw = math.atan2(2.0 * (q.w * q.z + q.x * q.y),
                         1.0 - 2.0 * (q.y * q.y + q.z * q.z))
        captured["ground_truth"].append((t, p.x, p.y, yaw))

    node.create_subscription(Twist, cfg.s("topics.cmd_vel"), on_cmd, 20)
    node.create_subscription(
        Odometry, cfg.s("topics.odom_ground_truth"), on_gt, 20)

    def spin_wall(seconds):
        end = time.time() + seconds
        while rclpy.ok() and time.time() < end:
            rclpy.spin_once(node, timeout_sec=0.05)

    _cancel_action(node, rclpy, "navigate_to_pose", wait_s)
    spin_wall(1.0)
    # Motion on cmd_vel after cancel is overlap. Standing zeros are not.
    now = node.get_clock().now().nanoseconds * 1e-9
    if last_motion["t"] and (now - last_motion["t"]) < 0.3:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse(
            "Nav2's controller is quiet before DockRobot",
            cfg.s("topics.cmd_vel"),
            "cmd_vel is still live after the NavigateToPose cancel. "
            "Constraint 22: one motion authority at a time.")

    dock = ActionClient(node, DockRobot, cfg.s("topics.dock_robot").lstrip("/"))
    if not dock.wait_for_server(timeout_sec=wait_s):
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("docking_server advertised {}".format(
                       cfg.s("topics.dock_robot")),
                   cfg.s("topics.dock_robot"),
                   "the state file says docking=on. Read "
                   "the docking_server log.")

    request = DockRobot.Goal()
    request.use_dock_id = True
    request.dock_id = want_id
    request.navigate_to_staging_pose = not from_staging
    request.max_staging_time = float(budget_s)

    def on_feedback(msg):
        fb = msg.feedback
        t = node.get_clock().now().nanoseconds * 1e-9
        captured["feedback"].append(
            (t, int(fb.state), int(fb.num_retries)))

    send = dock.send_goal_async(request, feedback_callback=on_feedback)
    rclpy.spin_until_future_complete(node, send, timeout_sec=wait_s)
    handle = send.result() if send.done() else None
    if handle is None or not handle.accepted:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("docking_server ACCEPTED DockRobot",
                   cfg.s("topics.dock_robot"),
                   "dock_id={!r} was {}.".format(
                       want_id,
                       "not answered" if handle is None else "REJECTED"))

    def wait_result(handle, budget):
        result_future = handle.get_result_async()
        deadline = time.time() + budget
        while rclpy.ok() and not result_future.done() and time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.05)
        if not result_future.done():
            handle.cancel_goal_async()
            spin_wall(2.0)
            return None
        return result_future.result().result

    result = wait_result(handle, budget_s)
    if result is None:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("DockRobot finished inside {:g}s".format(budget_s),
                   _common.CONFIG + " (dock.record_timeout_s)")

    success = bool(result.success)
    error_code = int(result.error_code)
    retries = int(result.num_retries)

    if (not success) and error_code in (904, 905):
        _align_for_tag(node, rclpy, Twist, PoseStamped, cfg,
                       target["pose_yaw"], captured, 20.0)
        spin_wall(1.5)
        now = node.get_clock().now().nanoseconds * 1e-9
        if last_motion["t"] and (now - last_motion["t"]) < 0.3:
            spin_wall(1.0)
        request.navigate_to_staging_pose = False
        send = dock.send_goal_async(request, feedback_callback=on_feedback)
        rclpy.spin_until_future_complete(node, send, timeout_sec=wait_s)
        handle = send.result() if send.done() else None
        if handle is not None and handle.accepted:
            second = wait_result(handle, min(90.0, budget_s))
            if second is not None:
                success = bool(second.success)
                error_code = int(second.error_code)
                retries = int(second.num_retries)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session = "dock-{}-{}".format(cfg.s("dock.station").lower(), stamp)
    dest = os.path.join(_common.REPO, cfg.s("evidence.dir"), session)
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "cmd_vel.csv"), "w",
              encoding="utf-8", newline="") as handle_out:
        handle_out.write("t_s,vx,wz\n")
        for row in captured["cmd_vel"]:
            handle_out.write("{:.9f},{:.9f},{:.9f}\n".format(*row))
    with open(os.path.join(dest, "ground_truth.csv"), "w",
              encoding="utf-8", newline="") as handle_out:
        handle_out.write("t_s,x,y,yaw\n")
        for row in captured["ground_truth"]:
            handle_out.write("{:.9f},{:.9f},{:.9f},{:.9f}\n".format(*row))
    with open(os.path.join(dest, "feedback.csv"), "w",
              encoding="utf-8", newline="") as handle_out:
        handle_out.write("t_s,state,num_retries\n")
        for row in captured["feedback"]:
            handle_out.write("{:.9f},{},{}\n".format(*row))
    with open(os.path.join(dest, "session.txt"), "w",
              encoding="utf-8") as handle_out:
        handle_out.write("kind=dock\n")
        handle_out.write("authority=dock\n")
        handle_out.write("dock_id={}\n".format(want_id))
        handle_out.write("success={}\n".format(success))
        handle_out.write("error_code={}\n".format(error_code))
        handle_out.write("error_name={}\n".format(dc.named_error(error_code)))
        handle_out.write("num_retries={}\n".format(retries))
        handle_out.write("target_world={:.6f} {:.6f} {:.6f}\n".format(
            target["x"], target["y"], target["pose_yaw"]))
        for key, value in state.items():
            handle_out.write("{}={}\n".format(key, value))
        handle_out.write("recorded={}\n".format(
            datetime.datetime.now().isoformat()))
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("session   {}".format(session))
    print("success   {}".format(success))
    print("error     {} ({})".format(error_code, dc.named_error(error_code)))
    print("retries   {}".format(retries))
    print("analyse:  python3 m5_ver3/tools/dock_bench.py analyse {}".format(
        session))
    return 0 if success else 1


def undock(cfg):
    (time, rclpy, Twist, _DockRobot, _NavigateToPose, UndockRobot,
     _Odometry, ActionClient, Node, _PoseStamped) = _import_ros(cfg)
    _live_state(cfg)
    wait_s = cfg.f("evidence.wait_first_s")
    budget_s = cfg.f("dock.record_timeout_s")

    rclpy.init(args=None)
    node = Node("m5v3_undock_bench")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    last_motion = {"t": 0.0}

    def on_cmd(msg):
        t = node.get_clock().now().nanoseconds * 1e-9
        if abs(float(msg.linear.x)) > 0.01 or abs(float(msg.angular.z)) > 0.01:
            last_motion["t"] = t

    node.create_subscription(Twist, cfg.s("topics.cmd_vel"), on_cmd, 20)

    def spin_wall(seconds):
        end = time.time() + seconds
        while rclpy.ok() and time.time() < end:
            rclpy.spin_once(node, timeout_sec=0.05)

    _cancel_action(node, rclpy, "navigate_to_pose", wait_s)
    spin_wall(1.0)
    now = node.get_clock().now().nanoseconds * 1e-9
    if last_motion["t"] and (now - last_motion["t"]) < 0.3:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse(
            "Nav2's controller is quiet before UndockRobot",
            cfg.s("topics.cmd_vel"),
            "cmd_vel is still live after the NavigateToPose cancel. "
            "Constraint 22.")

    client = ActionClient(
        node, UndockRobot, cfg.s("topics.undock_robot").lstrip("/"))
    if not client.wait_for_server(timeout_sec=wait_s):
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("docking_server advertised {}".format(
                       cfg.s("topics.undock_robot")),
                   cfg.s("topics.undock_robot"))

    request = UndockRobot.Goal()
    if hasattr(request, "dock_type"):
        request.dock_type = cfg.s("docking.plugin_name")
    if hasattr(request, "max_undocking_time"):
        request.max_undocking_time = float(budget_s)
    send = client.send_goal_async(request)
    rclpy.spin_until_future_complete(node, send, timeout_sec=wait_s)
    handle = send.result() if send.done() else None
    if handle is None or not handle.accepted:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("docking_server ACCEPTED UndockRobot",
                   cfg.s("topics.undock_robot"),
                   "not answered" if handle is None else "REJECTED")

    result_future = handle.get_result_async()
    deadline = time.time() + budget_s
    while rclpy.ok() and not result_future.done() and time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if not result_future.done():
        handle.cancel_goal_async()
        spin_wall(2.0)
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("UndockRobot finished inside {:g}s".format(budget_s),
                   _common.CONFIG + " (dock.record_timeout_s)")
    result = result_future.result().result
    success = bool(result.success)
    error_code = int(result.error_code)
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("undock    {}".format(success))
    print("error     {} ({})".format(error_code, dc.named_error(error_code)))
    return 0 if success else 1


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dock_bench.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    rec = sub.add_parser("record")
    rec.add_argument("--dock-id", default=None)
    rec.add_argument("--from-staging", action="store_true")
    sub.add_parser("stage")
    sub.add_parser("undock")
    ana = sub.add_parser("analyse")
    ana.add_argument("session", nargs="?")
    args = parser.parse_args(argv)
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    if args.cmd == "record":
        return record(cfg, args.dock_id, args.from_staging)
    if args.cmd == "stage":
        return stage(cfg)
    if args.cmd == "undock":
        return undock(cfg)
    if args.cmd == "analyse":
        return analyse(cfg, args.session)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
