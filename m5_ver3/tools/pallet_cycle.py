#!/usr/bin/env python3
"""pallet_cycle.py - F5 Task 3's dry full cycle, scored by existing benches.

    python3 m5_ver3/tools/pallet_cycle.py describe
    python3 m5_ver3/tools/pallet_cycle.py run

transit → stage → dock → attach → lift → undock → carry (one aisle) →
stage → dock → lower → detach → undock. Repeat DEFAULT_REPEAT.

Undock is a cmd_vel burst on topics.cmd_vel (constraint 22). It is not
the undock action T2 named 905 and not a seated teleport (T3 pickup).
"""
import argparse
import datetime
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import dock_bench as db                               # noqa: E402
import pallet_bench as pb                             # noqa: E402

TOOL = "pallet_cycle"
DEFAULT_REPEAT = 3

REQUIRED_KEYS = (
    "isolation.ros_domain_id", "isolation.gz_partition",
    "topics.cmd_vel", "dock.v_linear_min", "dock.staging_run_in_m",
    "nav.goals.ring_s5_junction.y", "nav.goals.station_s5_staging.y",
    "pallet.lift_m", "pallet.mast_limit_mps",
    "evidence.dir", "evidence.wait_first_s",
    "paths.traction_file",
)


def plan_cycle():
    """One dry cycle. Live `run` executes these argv lists in order."""
    return [
        {"leg": "transit", "tool": "drive_goal.py",
         "argv": ["record", "--goal", "spine_north"]},
        {"leg": "stage", "tool": "drive_goal.py",
         "argv": ["record", "--case", "stage_s5"]},
        {"leg": "dock", "tool": "dock_bench.py",
         "argv": ["record", "--from-staging"]},
        {"leg": "attach", "tool": "pallet_bench.py", "argv": ["attach"]},
        {"leg": "lift", "tool": "pallet_bench.py", "argv": ["lift"]},
        {"leg": "undock", "tool": "burst", "argv": []},
        {"leg": "carry", "tool": "burst", "argv": ["carry"]},
        {"leg": "stage", "tool": "burst", "argv": ["return"]},
        {"leg": "dock", "tool": "burst", "argv": ["return-dock"]},
        {"leg": "lower", "tool": "pallet_bench.py", "argv": ["lower"]},
        {"leg": "detach", "tool": "pallet_bench.py", "argv": ["detach"]},
        {"leg": "undock", "tool": "burst", "argv": []},
    ]


def describe(_cfg):
    print("=== m5v3 pallet cycle ===")
    print("repeat    {}".format(DEFAULT_REPEAT))
    print("cycle     {}".format(" -> ".join(pb.CYCLE)))
    for i, step in enumerate(plan_cycle(), 1):
        extra = " ".join(step["argv"]) if step["argv"] else "cmd_vel +x"
        print("  {:2d}. {:<8} {} {}".format(i, step["leg"], step["tool"], extra))
    return 0


def isolate(cfg):
    os.environ["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    os.environ["GZ_PARTITION"] = cfg.s("isolation.gz_partition")


def seed_amcl(cfg, wx, wy, yaw, label):
    """AMCL seed at a world pose. gz pose services do not write /tf."""
    import math
    frame = db._map_frame(cfg)
    mx, my, myaw = frame.to_map(wx, wy, yaw)
    (_t, rclpy, _Tw, _D, _N, _U, _O, _AC, Node,
     _PS) = db._import_ros(cfg)
    from geometry_msgs.msg import PoseWithCovarianceStamped
    rclpy.init(args=None)
    node = Node("m5v3_pallet_cycle_seed")
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
    print("seeded    {} map ({:.3f}, {:.3f}) yaw {:+.4f}".format(
        label, mx, my, myaw))
    return 0


def seed_amcl_docked(cfg):
    pose = db._docked(cfg)
    return seed_amcl(cfg, pose["x"], pose["y"], pose["pose_yaw"], "docked")


def seed_amcl_live(cfg):
    """live seed after cmd_vel so Nav2 is not 5 m off the truth."""
    truck, _pallet, raw = pb.live_poses(cfg)
    if truck is None:
        cfg.refuse("live gz pose for the truck",
                   "/world/{}/dynamic_pose/info".format(
                       cfg.s("world.name")),
                   (raw or "<empty>")[:200])
    return seed_amcl(cfg, truck["x"], truck["y"], truck["yaw"], "live")


def restore_for_attach(cfg):
    """docked pose restore. Plugin isDocked is XY; leftover heading
    fails attach_ok and the forks shove the pallet (c1-attach 0.63 rad).
    """
    py = sys.executable
    steps = (
        ("pallet_place.py", "remove"),
        ("pallet_place.py", "place"),
        ("pallet_bench.py", "detach"),
        ("pallet_bench.py", "seat"),
    )
    for tool, argv in steps:
        rc = subprocess.run(
            [py, os.path.join(_HERE, tool), argv]).returncode
        if rc != 0:
            return rc
    return seed_amcl_docked(cfg)


def burst(cfg, distance_m=None):
    """Body +x. Forks trail; aisle is +y at S5."""
    try:
        import rclpy
        from geometry_msgs.msg import Twist
        from rclpy.node import Node
    except ImportError as exc:
        cfg.refuse("rclpy is importable", _common.CONFIG + " (paths.ros_setup)",
                   str(exc))
    if distance_m is None:
        dist = cfg.f("dock.staging_run_in_m")
    else:
        dist = float(distance_m)
    speed = cfg.f("dock.v_linear_min")
    hold_s = abs(dist) / speed + 1.0
    signed = speed if dist >= 0 else -speed
    rclpy.init(args=None)
    node = Node("m5v3_pallet_cycle_burst")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    pub = node.create_publisher(Twist, cfg.s("topics.cmd_vel"), 10)
    cmd = Twist()
    cmd.linear.x = signed
    end = time.time() + hold_s
    while time.time() < end:
        pub.publish(cmd)
        rclpy.spin_once(node, timeout_sec=0.05)
    zero = Twist()
    for _ in range(10):
        pub.publish(zero)
        rclpy.spin_once(node, timeout_sec=0.05)
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("burst     {:+.3f} m/s for {:.1f} s on {}".format(
        signed, hold_s, cfg.s("topics.cmd_vel")))
    return 0


def _snapshot(cfg, log, tag):
    truck, pallet, _raw = pb.live_poses(cfg)
    line = "snapshot {} truck={} pallet={}".format(tag, truck, pallet)
    log.write(line + "\n")
    log.flush()
    print(line)
    return truck, pallet


def _latest_nav_session(cfg):
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    newest, mtime = None, 0.0
    for name in os.listdir(root):
        if not (name.startswith("goal-") or name.startswith("case-")):
            continue
        path = os.path.join(root, name, "session.txt")
        if not os.path.isfile(path):
            continue
        stamp = os.path.getmtime(path)
        if stamp > mtime:
            newest, mtime = path, stamp
    return newest


def _nav_succeeded(cfg):
    path = _latest_nav_session(cfg)
    if path is None:
        return False
    text = open(path, encoding="utf-8").read()
    return "action_status=4" in text and "error_code=0" in text


def run(cfg, repeat):
    isolate(cfg)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(_common.REPO, cfg.s("evidence.dir"),
                        "pallet-cycle-{}".format(stamp))
    os.makedirs(dest, exist_ok=True)
    log_path = os.path.join(dest, "session.txt")
    print("session   {}".format(dest))
    with open(log_path, "w", encoding="utf-8") as log:
        log.write("kind=pallet_cycle\nrepeat={}\nrecorded={}\n".format(
            repeat, datetime.datetime.now().isoformat()))
        for n in range(1, repeat + 1):
            log.write("\n# cycle {}\n".format(n))
            print("=== cycle {}/{} ===".format(n, repeat))
            for step in plan_cycle():
                tag = "c{}-{}".format(n, step["leg"])
                log.write("leg {} tool={} argv={}\n".format(
                    tag, step["tool"], step["argv"]))
                log.flush()
                print("leg       {}".format(tag))
                if step["tool"] == "dock_bench.py":
                    # heading seed: Nav2's position latch does not
                    # point the camera (T1). T2's dock_bench stage does.
                    # Not on a laden dock: a gz pose write drops the child.
                    seed = [sys.executable,
                            os.path.join(_HERE, "dock_bench.py"), "stage"]
                    seed_rc = subprocess.run(seed).returncode
                    if seed_rc != 0:
                        log.write("heading seed rc={}\n".format(seed_rc))
                        print("stopped   {} heading seed rc={}".format(
                            tag, seed_rc))
                        return 1
                    time.sleep(2.0)
                if step["leg"] == "attach":
                    rest_rc = restore_for_attach(cfg)
                    if rest_rc != 0:
                        log.write("docked pose restore rc={}\n".format(
                            rest_rc))
                        print("stopped   {} restore rc={}".format(
                            tag, rest_rc))
                        return 1
                    time.sleep(1.0)
                if step["tool"] == "burst":
                    aisle = (cfg.f("nav.goals.ring_s5_junction.y")
                             - cfg.f("nav.goals.station_s5_staging.y"))
                    argv = step["argv"]
                    if step["leg"] == "carry" or "carry" in argv:
                        rc = burst(cfg, aisle)
                    elif "return-dock" in argv:
                        rc = burst(cfg, -cfg.f("dock.staging_run_in_m"))
                    elif "return" in argv:
                        rc = burst(cfg, -aisle)
                    else:
                        rc = burst(cfg)
                    seed_amcl_live(cfg)
                else:
                    cmd = [sys.executable,
                           os.path.join(_HERE, step["tool"])] + step["argv"]
                    proc = subprocess.run(cmd)
                    rc = proc.returncode
                    if step["tool"] == "drive_goal.py" and not _nav_succeeded(cfg):
                        rc = 1
                if step["leg"] in ("lift", "lower"):
                    wait = cfg.f("pallet.lift_m") / cfg.f(
                        "pallet.mast_limit_mps") + 1.5
                    time.sleep(wait)
                _snapshot(cfg, log, tag)
                log.write("rc={}\n".format(rc))
                if rc != 0:
                    log.write("stopped at {}\n".format(tag))
                    print("stopped   {} rc={}".format(tag, rc))
                    return 1
    print("done      {} cycles -> {}".format(repeat, dest))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="pallet_cycle.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    run_p = sub.add_parser("run")
    run_p.add_argument("--repeat", type=int, default=DEFAULT_REPEAT)
    args = parser.parse_args(argv)
    if args.cmd == "run":
        return run(cfg, args.repeat)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
