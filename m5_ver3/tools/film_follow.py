#!/usr/bin/env python3
"""film_follow.py - hold the follow camera over the truck.

    python3 m5_ver3/tools/film_follow.py

Subscribes to topics.odom_ground_truth (the MEASUREMENT REFERENCE
channel, read here the way every bench reads it - as an instrument,
never as an input to anything that moves the truck) and, every
1/film.follow_update_hz seconds, moves film.follow_model to the
truck's x/y at film.follow_height_m through /world/<world>/set_pose -
the same service pallet_bench.py seats the truck with, so the channel
is measured, not new.

The camera position is SMOOTHED (film_core.follow_step): a pose step
every 0.5 s would otherwise be a jump in 15 Hz footage, and the
smoothing spreads it. A set_pose that fails is counted, named and
tolerated to film.follow_fail_max IN A ROW - one dropped call is
latency, ten is a dead service, and the refusal is by name so the
operator knows the footage stopped tracking before the cut finds out.

Started and stopped by tools/film_run.py; needs ROS, gz and a stack
that is already up.
"""
import os
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import film_core as fc                                # noqa: E402

TOOL = "film_follow"

REQUIRED_KEYS = (
    "isolation.ros_domain_id", "isolation.gz_partition",
    "world.name", "topics.odom_ground_truth",
    "timing.spawn_service_timeout_ms",
    "film.follow_model", "film.follow_height_m",
    "film.follow_update_hz", "film.follow_smooth", "film.follow_fail_max",
)


def _set_pose(cfg, request):
    cmd = [
        "gz", "service", "-s", "/world/{}/set_pose".format(
            cfg.s("world.name")),
        "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
        "--timeout", str(cfg.s("timing.spawn_service_timeout_ms")),
        "--req", request,
    ]
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=30).stdout
    except Exception as exc:                          # pragma: no cover
        return "gz service failed: {}".format(exc)


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    os.environ["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    os.environ["GZ_PARTITION"] = cfg.s("isolation.gz_partition")

    try:
        import rclpy
        from nav_msgs.msg import Odometry
        from rclpy.node import Node
    except ImportError as exc:
        cfg.refuse("rclpy is importable",
                   _common.CONFIG + " (paths.ros_setup)", str(exc))

    model = cfg.s("film.follow_model")
    height = cfg.f("film.follow_height_m")
    period = 1.0 / cfg.f("film.follow_update_hz")
    alpha = cfg.f("film.follow_smooth")
    fail_max = cfg.i("film.follow_fail_max")

    truck = {"x": None, "y": None}
    cam = {"x": None, "y": None}
    fails = 0
    moves = 0

    rclpy.init(args=None)
    node = Node("m5v3_film_follow")

    def on_odom(msg):
        truck["x"] = msg.pose.pose.position.x
        truck["y"] = msg.pose.pose.position.y

    node.create_subscription(Odometry, cfg.s("topics.odom_ground_truth"),
                             on_odom, 10)

    print("follow   {} on {} at {:.1f} m, {:.2f} s period".format(
        model, cfg.s("topics.odom_ground_truth"), height, period))
    next_move = time.time()
    next_report = time.time() + 10.0
    try:
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.05)
            now = time.time()
            if now >= next_report:
                print("follow   move {} at ({:.2f}, {:.2f})".format(
                    moves, cam["x"] if cam["x"] is not None else 0.0,
                    cam["y"] if cam["y"] is not None else 0.0))
                next_report = now + 10.0
            if now < next_move:
                continue
            next_move = now + period
            if truck["x"] is None:
                continue
            if cam["x"] is None:
                cam["x"], cam["y"] = truck["x"], truck["y"]
            cam["x"], cam["y"] = fc.follow_step(
                cam["x"], cam["y"], truck["x"], truck["y"], alpha)
            reply = _set_pose(cfg, fc.pose_request(
                model, cam["x"], cam["y"], height, fc._Q_DOWN))
            if "data: true" in reply:
                fails = 0
                moves += 1
            else:
                fails += 1
                print("follow   set_pose refused ({}/{}): {}".format(
                    fails, fail_max, (reply or "<empty>").strip()[:120]))
                if fails >= fail_max:
                    node.destroy_node()
                    try:
                        rclpy.shutdown()
                    except Exception:
                        pass
                    cfg.refuse(
                        "the follow camera could be moved",
                        "/world/{}/set_pose".format(cfg.s("world.name")),
                        "{} refusals in a row; the last reply was {!r}"
                        .format(fail_max, (reply or "<empty>")[:200]))
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("follow   end")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())