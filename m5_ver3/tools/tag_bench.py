#!/usr/bin/env python3
"""tag_bench.py - AprilTag detections vs the furniture marker. --selftest

    python3 m5_ver3/tools/tag_bench.py describe
    python3 m5_ver3/tools/tag_bench.py record
    python3 m5_ver3/tools/tag_bench.py analyse [session]

WHAT THIS SCORES. furniture.py places tag36h11_0 at tag_core's marker
pose (WORLD). apriltag_ros publishes detections; record() looks up
each tag TF in frames.map and writes detections.csv. analyse() is
detection_error() on those rows against the SAME pose carried through
the committed registration (MapFrame), and needs no ROS.

A CSV whose poses are still in the camera frame is refused: that would
be a range in the optical frame sitting next to a world pose.
A CSV in map scored against the world xy is refused by construction:
that is the hall origin offset (~31 m on warehouse_v3), not PnP.
"""
import argparse
import datetime
import math
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_IPC = os.path.normpath(os.path.join(_HERE, os.pardir, os.pardir, "m6", "ipc"))
if _IPC not in sys.path:
    sys.path.insert(0, _IPC)

import _common                                        # noqa: E402
import evidence_core as ec                            # noqa: E402
import tag_core as tc                                 # noqa: E402
import stations                                       # noqa: E402
import map_register                                   # noqa: E402

TOOL = "tag_bench"

REQUIRED_KEYS = (
    "dock.station", "dock.marker_ahead_m", "dock.fork_reach_m",
    "dock.tip_standoff_m", "dock.staging_run_in_m", "dock.marker_z_m",
    "dock.tag_id",
    "topics.apriltag_detections", "frames.map",
    "apriltag.record_s", "apriltag.prefix", "apriltag.deb_prefix",
    "apriltag.lib", "apriltag.tag_frame",
    "map.dir", "map.name", "map.registration.file",
    "evidence.dir", "evidence.wait_first_s", "evidence.min_samples",
    "paths.traction_file",
)


def expected_marker_xyz(station, dock):
    geo = tc.station_geometry(
        float(station["x"]), float(station["y"]), float(station["yaw"]),
        marker_ahead_m=float(dock["marker_ahead_m"]),
        fork_reach_m=float(dock["fork_reach_m"]),
        tip_standoff_m=float(dock["tip_standoff_m"]),
        staging_run_in_m=float(dock["staging_run_in_m"]))
    return (geo["marker"][0], geo["marker"][1], float(dock["marker_z_m"]))


def expected_marker_in_map(world_xyz, frame):
    """The furniture pose in frames.map, through MapFrame.

    furniture.py places the marker in the WORLD. apriltag_ros broadcasts
    TF in the map tree. A CSV of map-frame detections scored against the
    world xy is the hall's own origin offset (~31 m on warehouse_v3),
    not a PnP error.
    """
    mx, my = frame.to_map(world_xyz[0], world_xyz[1])
    return (float(mx), float(my), float(world_xyz[2]))


def message_has_tag(msg, want_id):
    """True only when this array carries the configured id.

    apriltag_ros publishes an AprilTagDetectionArray on every camera
    frame, including frames with detections=[] . Those are not a
    detection.
    """
    want = int(want_id)
    for det in msg.detections:
        if int(det.id) == want:
            return True
    return False


def transform_xyz(translation, quaternion_xyzw, xyz):
    """Apply a geometry_msgs Transform to a point: rotate, then translate."""
    x, y, z, w = [float(c) for c in quaternion_xyzw]
    vx, vy, vz = [float(c) for c in xyz]
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    rx = vx + w * tx + (y * tz - z * ty)
    ry = vy + w * ty + (z * tx - x * tz)
    rz = vz + w * tz + (x * ty - y * tx)
    return (float(translation[0]) + rx,
            float(translation[1]) + ry,
            float(translation[2]) + rz)


def summarise(rows, expected):
    if not rows:
        raise ValueError("no detections")
    dists = []
    for row in rows:
        if str(row["frame"]) != "map":
            raise ValueError(
                "detection poses must be in the map frame, not {}".format(
                    row["frame"]))
        dists.append(tc.detection_error(
            expected, (row["x"], row["y"], row["z"]))["dist_m"])
    return {
        "n": len(dists),
        "min_dist_m": min(dists),
        "max_dist_m": max(dists),
        "mean_dist_m": sum(dists) / float(len(dists)),
        "rms_dist_m": math.sqrt(sum(d * d for d in dists) / float(len(dists))),
    }


def _station_dock(cfg):
    name = cfg.s("dock.station")
    table = stations.STATIONS
    if name not in table:
        cfg.refuse("dock.station is a key of m6/ipc/stations.py",
                   _common.CONFIG + " (dock.station)",
                   "it reads {!r}".format(name))
    dock = {
        "marker_ahead_m": cfg.s("dock.marker_ahead_m"),
        "fork_reach_m": cfg.s("dock.fork_reach_m"),
        "tip_standoff_m": cfg.s("dock.tip_standoff_m"),
        "staging_run_in_m": cfg.s("dock.staging_run_in_m"),
        "marker_z_m": cfg.s("dock.marker_z_m"),
    }
    return table[name], dock


def _map_frame(cfg):
    path = os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                        cfg.s("map.registration.file"))
    try:
        record = map_register.load_registration(path)
        return ec.MapFrame.from_registration(record)
    except Exception as exc:
        cfg.refuse("the committed registration belongs to the grid on disk",
                   path, str(exc))


def _vendor_on_sys_path(cfg):
    """apriltag_msgs lives in the no-sudo prefix, not in /opt/ros.

    The detector child gets AMENT_PREFIX_PATH from m5v3.sh; this bench
    is a separate python and has to find the same messages itself.
    """
    import glob
    prefix = os.path.expanduser(cfg.s("apriltag.prefix"))
    ros = os.path.join(prefix, cfg.s("apriltag.deb_prefix").replace("/", os.sep))
    for site in sorted(glob.glob(os.path.join(ros, "lib", "python3.*",
                                              "site-packages"))):
        if site not in sys.path:
            sys.path.insert(0, site)
    lib = os.path.join(ros, "lib")
    multi = os.path.join(ros, os.path.dirname(
        cfg.s("apriltag.lib").replace("/", os.sep)))
    bits = [lib, multi]
    current = os.environ.get("LD_LIBRARY_PATH", "")
    if current:
        bits.append(current)
    os.environ["LD_LIBRARY_PATH"] = os.pathsep.join(bits)
    ament = os.environ.get("AMENT_PREFIX_PATH", "")
    os.environ["AMENT_PREFIX_PATH"] = ros + ((":" + ament) if ament else "")


def describe(cfg):
    st, dock = _station_dock(cfg)
    xyz = expected_marker_xyz(st, dock)
    frame = _map_frame(cfg)
    mapped = expected_marker_in_map(xyz, frame)
    print("=== m5v3 tag bench ===")
    print("station   {}".format(cfg.s("dock.station")))
    print("marker    ({:.3f}, {:.3f}, {:.3f}) in world".format(*xyz))
    print("          ({:.3f}, {:.3f}, {:.3f}) in {}".format(
        mapped[0], mapped[1], mapped[2], cfg.s("frames.map")))
    print("          {}".format(frame.floor()))
    print("topic     {}".format(cfg.s("topics.apriltag_detections")))
    print("record_s  {}".format(cfg.s("apriltag.record_s")))
    return 0


def _load_rows(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        header = handle.readline().strip().split(",")
        for line in handle:
            parts = line.strip().split(",")
            rec = dict(zip(header, parts))
            rows.append({
                "x": float(rec["x"]), "y": float(rec["y"]),
                "z": float(rec["z"]), "frame": rec["frame"],
                "id": int(float(rec["id"])),
            })
    return rows


def analyse(cfg, session=None):
    root = os.path.join(_common.REPO, cfg.s("evidence.dir"))
    if session is None:
        names = sorted(
            n for n in os.listdir(root)
            if n.startswith("tag-") and os.path.isdir(os.path.join(root, n)))
        if not names:
            cfg.refuse("there is a recorded tag session to analyse",
                       root, "nothing there begins with `tag-`.")
        session = names[-1]
    path = os.path.join(root, session, "detections.csv")
    if not os.path.isfile(path):
        cfg.refuse("the session recorded detections.csv", path)
    st, dock = _station_dock(cfg)
    world = expected_marker_xyz(st, dock)
    expected = expected_marker_in_map(world, _map_frame(cfg))
    rows = _load_rows(path)
    try:
        out = summarise(rows, expected)
    except ValueError as exc:
        cfg.refuse(str(exc), path)
    if out["n"] < int(cfg.s("evidence.min_samples")):
        cfg.refuse("the capture has at least {} detections".format(
                       cfg.s("evidence.min_samples")),
                   path, "it has {}".format(out["n"]))
    print("=== m5v3 tag bench / {} ===".format(session))
    print("expected  ({:.3f}, {:.3f}, {:.3f}) in {}".format(
        expected[0], expected[1], expected[2], cfg.s("frames.map")))
    print("          world ({:.3f}, {:.3f}, {:.3f})".format(*world))
    print("n         {}".format(out["n"]))
    print("mean      {:.4f} m".format(out["mean_dist_m"]))
    print("rms       {:.4f} m".format(out["rms_dist_m"]))
    print("min/max   {:.4f} / {:.4f} m".format(
        out["min_dist_m"], out["max_dist_m"]))
    return 0


def record(cfg):
    _vendor_on_sys_path(cfg)
    # LD_LIBRARY_PATH is read at process start. Setting it in this
    # python does not help dlopen find libapriltag_msgs__rosidl_generator_py.so.
    if os.environ.get("M5V3_APRILTAG_VENDORED") != "1":
        env = os.environ.copy()
        env["M5V3_APRILTAG_VENDORED"] = "1"
        os.execvpe(sys.executable, [sys.executable] + sys.argv, env)
    try:
        import rclpy
        from rclpy.node import Node
        from rclpy.time import Time
        from tf2_ros import Buffer, TransformListener
        from apriltag_msgs.msg import AprilTagDetectionArray
    except ImportError as exc:
        cfg.refuse("rclpy, tf2_ros and apriltag_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced.")

    state_path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(state_path):
        cfg.refuse("the stack said which plant it is", state_path,
                   "there is no state file. m5v3.sh start writes it.")
    with open(state_path, encoding="utf-8") as handle:
        state = ec.parse_state_file(handle.read())
    dock_line = state.get("dock", "")
    if not str(dock_line).startswith("on@"):
        cfg.refuse("the running stack has --dock",
                   state_path,
                   "its dock= line reads {!r}, so apriltag_node is not "
                   "on this stack.".format(dock_line or "<missing>"),
                   "  bash m5_ver3/m5v3.sh start --headless "
                   "--localize --nav --dock")

    map_frame = cfg.s("frames.map")
    tag_frame = cfg.s("apriltag.tag_frame")
    topic = cfg.s("topics.apriltag_detections")
    want_id = int(cfg.s("dock.tag_id"))
    wait_s = cfg.f("evidence.wait_first_s")
    hold_s = cfg.f("apriltag.record_s")
    rows = []

    rclpy.init(args=None)
    node = Node("m5v3_tag_bench")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    buf = Buffer()
    TransformListener(buf, node)
    got = {"first": False}

    def on_msg(msg):
        if not message_has_tag(msg, want_id):
            return
        got["first"] = True
        stamp = Time.from_msg(msg.header.stamp)
        for det in msg.detections:
            if int(det.id) != want_id:
                continue
            try:
                tf = buf.lookup_transform(map_frame, tag_frame, stamp)
            except Exception:
                try:
                    tf = buf.lookup_transform(map_frame, tag_frame, Time())
                except Exception:
                    continue
            t = tf.transform.translation
            rows.append((msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                         int(det.id), t.x, t.y, t.z, map_frame))

    node.create_subscription(AprilTagDetectionArray, topic, on_msg, 10)
    # WALL TIME, NOT SIM TIME. A use_sim_time node that has not yet
    # heard /clock reads 0, then jumps to hundreds of seconds and the
    # wait expires without spinning. This bound is "did a message
    # arrive", the same job evidence.wait_first_s has on every other
    # bench.
    import time as _time
    deadline = _time.time() + wait_s
    while rclpy.ok() and not got["first"] and _time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
    if not got["first"]:
        node.destroy_node()
        try:
            rclpy.shutdown()
        except Exception:
            pass
        cfg.refuse("a detection arrived on {}".format(topic),
                   topic + " within {:g}s".format(wait_s),
                   "apriltag_node published nothing. Camera at this pose "
                   "may not see the marker (staging range is the measurement).")

    hold_end = _time.time() + hold_s
    while rclpy.ok() and _time.time() < hold_end:
        rclpy.spin_once(node, timeout_sec=0.05)

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session = "tag-{}-{}".format(cfg.s("dock.station").lower(), stamp)
    dest = os.path.join(_common.REPO, cfg.s("evidence.dir"), session)
    os.makedirs(dest, exist_ok=True)
    csv_path = os.path.join(dest, "detections.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        handle.write("t_s,id,x,y,z,frame\n")
        for row in rows:
            handle.write("{:.9f},{},{:.9f},{:.9f},{:.9f},{}\n".format(*row))
    with open(os.path.join(dest, "session.txt"), "w",
              encoding="utf-8") as handle:
        handle.write("kind=tag\n")
        for key, value in state.items():
            handle.write("{}={}\n".format(key, value))
        handle.write("n={}\n".format(len(rows)))
        handle.write("recorded={}\n".format(
            datetime.datetime.now().isoformat()))
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    print("session   {}".format(session))
    print("rows      {}".format(len(rows)))
    print("analyse:  python3 m5_ver3/tools/tag_bench.py analyse {}".format(
        session))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="tag_bench.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    sub.add_parser("record")
    ana = sub.add_parser("analyse")
    ana.add_argument("session", nargs="?")
    args = parser.parse_args(argv)
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    if args.cmd == "record":
        return record(cfg)
    if args.cmd == "analyse":
        return analyse(cfg, args.session)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
