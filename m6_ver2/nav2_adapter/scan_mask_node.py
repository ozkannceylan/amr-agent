#!/usr/bin/env python3
"""scan_mask_node.py - the vehicle's own mast, taken out of its own scan.

    python3 m6_ver2/nav2_adapter/scan_mask_node.py \\
        --in-topic /f1/gz/scan_nav --out-topic /f1/scan_nav_masked \\
        --ros-args -r __ns:=/f1 -r tf:=/tf -r tf_static:=/tf_static

A THIN SHELL AND NOTHING ELSE. The filter is scan_mask.mask_ranges,
which is pure and tested without a simulator; this file subscribes one
LaserScan, hands its three fields to that function, and republishes the
SAME message with the filtered ranges in it.

WHY IT EXISTS (SPEC_ADAPTER.md A-T2). The nav lidar sits at
(0.55, -0.40, 1.80) on a truck whose mast stands in its beam: the
ver2-lineage contour returns at 1.29-1.48 m, in two angular windows,
every single scan (m6/ipc/follower.py SELF_MASK). Handed to an
ObstacleLayer those returns mark LETHAL CELLS ON THE ROBOT ITSELF, and a
planner asked to start from a lethal cell refuses with 205
START_OCCUPIED - on every plan, for ever, with nothing in any log that
says the obstacle is the truck. Handed to AMCL they are beams the map
cannot explain, in the same two windows on every scan, which is a
systematic bias rather than noise.
  m5v3 GOT AWAY WITHOUT ONE because its local costmap runs
  `footprint_clearing_enabled: true` and its three self-returns land
  INSIDE the footprint polygon (nav2.yaml 14.4). That is a repair after
  the fact and it does not cover the GLOBAL costmap's start cell or
  AMCL's beam model, which is why the filter is a node here and not a
  parameter.

BOTH ADDRESSES COME FROM THE COMMAND LINE AND NEITHER HAS A DEFAULT.
The input is config.yaml's bridged raw scan; the OUTPUT has no home in
config.yaml at all, because the thing that has to agree with it is a
FILE literal inside nav2.yaml's two obstacle layers - costmaps are
sub-nodes with no command line, so no `-p` can reach them. One spelling
exists, in tools/instantiate_truck.masked_scan_topic(), and
m6_ver2/truck.sh asks that module for it and passes it here and to
AMCL. A default in this file would be a second spelling, and the day
they disagreed the costmaps would mark a mast nobody was filtering.

THE COUNT IS THE OBSERVABLE SEAM. `n_masked` is logged on a throttle: a
filter whose effect nobody can count is a filter nobody can tell has
stopped working, and "0 masked" on a truck that is standing still is the
one number that says the contour has drifted off the hardware.
"""
import argparse
import sys

import _donors                                            # noqa: F401

import scan_mask                                          # noqa: E402
from nav2_adapter_node import own_args                    # noqa: E402

TOOL = "scan_mask"

#: How often the masked count is written to the child log. Seconds of
#: WALL clock, not of scans: the scan rate is the plant's and this is a
#: heartbeat for an operator reading a log.
LOG_EVERY_S = 10.0


def _parser():
    parser = argparse.ArgumentParser(
        description="republish a LaserScan with the vehicle's own mast "
                    "returns removed, for AMCL and both costmaps.")
    parser.add_argument("--in-topic",
                        help="the bridged raw scan (config.yaml "
                             "topics.scan_nav)")
    parser.add_argument("--out-topic",
                        help="where the masked scan goes. No default: "
                             "nav2.yaml's two obstacle layers carry this "
                             "name as a file literal and "
                             "tools/instantiate_truck.masked_scan_topic() "
                             "is the one place it is spelled.")
    parser.add_argument("--selftest", action="store_true",
                        help="the contour, its windows and the filter, "
                             "on a synthetic scan. No ROS.")
    return parser


def _selftest():
    """The contour and the filter, with no graph under them."""
    fails = []
    windows = scan_mask.SELF_MASK
    print("scan_mask shell selftest")
    print("  contour: {} window(s) from follower.SELF_MASK".format(
        len(windows)))
    for lo, hi, ceiling in windows:
        print("    {:+6.1f} to {:+6.1f} deg, out to {:.2f} m".format(
            lo, hi, ceiling))
    # A scan whose every ray reads 1.40 m - inside both windows' ceilings
    # - so the masked count is exactly the number of rays that fall in
    # the two angular windows and nothing else.
    import math
    n = 720
    increment = 2.0 * math.pi / n
    ranges = [1.40] * n
    masked = scan_mask.mask_ranges(ranges, -math.pi, increment)
    if masked.n_masked <= 0:
        fails.append("the filter masked nothing on a 1.40 m sphere")
        print("  FAIL the filter masked nothing at all")
    if masked.n_masked >= n:
        fails.append("the filter masked the whole scan")
        print("  FAIL the filter masked every ray")
    if ranges != [1.40] * n:
        fails.append("the input list was mutated")
        print("  FAIL mask_ranges mutated its input")
    print("  pass  {} of {} rays masked on a uniform 1.40 m scan".format(
        masked.n_masked, n))
    print("  in/out addresses: BOTH from the command line, no defaults "
          "- see this file's header")
    print("{} problems".format(len(fails)))
    return 1 if fails else 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    args = parser.parse_args(own_args(argv))
    if args.selftest:
        return _selftest()
    if not args.in_topic or not args.out_topic:
        parser.error(
            "--in-topic and --out-topic are both required and neither "
            "has a default: the output name has to match a FILE literal "
            "in this truck's derived nav2.yaml, and a default here "
            "would be a second spelling of it")

    try:
        import rclpy
        from rclpy.executors import ExternalShutdownException
        from rclpy.qos import QoSProfile
        from sensor_msgs.msg import LaserScan
    except ImportError as exc:
        sys.stderr.write(
            "{}: REFUSED at check 'rclpy is importable'\n"
            "  python3 could not import ROS 2: {}\n"
            "  this node runs INSIDE WSL with /opt/ros/jazzy sourced -\n"
            "  m6_ver2/truck.sh sources it before it spawns this child.\n"
            .format(TOOL, exc))
        return 1

    rclpy.init(args=sys.argv)
    # use_sim_time arrives as a `-p` from m6_ver2/truck.sh, as it does
    # for every other child on this stack.
    node = rclpy.create_node("scan_mask")
    # DEPTH 10 AND THE DEFAULT RELIABILITY, both ends, which is what the
    # bridged scan is already carried on and measured under in m6
    # (ipc/nav_node.py subscribes the same topic the same way). A
    # RELIABLE publisher also satisfies the BEST_EFFORT subscriptions
    # nav2's costmap layers and AMCL use by default, so one profile
    # serves every consumer.
    publisher = node.create_publisher(LaserScan, args.out_topic,
                                      QoSProfile(depth=10))
    counters = {"scans": 0, "masked": 0, "last_log": 0.0}

    def on_scan(msg):
        result = scan_mask.mask_ranges(msg.ranges, msg.angle_min,
                                       msg.angle_increment)
        # THE SAME MESSAGE, WITH ITS RANGES REPLACED. The header, the
        # stamp, the angles and the intensities travel untouched: a
        # consumer that re-derives a bearing off angle_min must get the
        # same bearing this filter used, and a costmap that read a
        # re-stamped scan would place the returns at the wrong pose.
        msg.ranges = [float(value) for value in result.ranges]
        publisher.publish(msg)
        counters["scans"] += 1
        counters["masked"] += result.n_masked
        now = node.get_clock().now().nanoseconds / 1e9
        if now - counters["last_log"] >= LOG_EVERY_S:
            counters["last_log"] = now
            node.get_logger().info(
                "{} -> {}: {} scans, {} returns masked ({:.1f}/scan)".format(
                    args.in_topic, args.out_topic, counters["scans"],
                    counters["masked"],
                    counters["masked"] / float(counters["scans"])))

    node.create_subscription(LaserScan, args.in_topic, on_scan,
                             QoSProfile(depth=10))
    node.get_logger().info(
        "scan mask up: {} -> {}, {} contour window(s) from "
        "follower.SELF_MASK".format(args.in_topic, args.out_topic,
                                    len(scan_mask.SELF_MASK)))
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
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
