#!/usr/bin/env python3
"""pallet_bench.py - attach, lift, detach, the F5 Task 3 cycle.

    python3 m5_ver3/tools/pallet_bench.py describe
    python3 m5_ver3/tools/pallet_bench.py status
    python3 m5_ver3/tools/pallet_bench.py attach
    python3 m5_ver3/tools/pallet_bench.py lift
    python3 m5_ver3/tools/pallet_bench.py lower
    python3 m5_ver3/tools/pallet_bench.py detach

CONSTRAINT 23. attach() publishes gz.msgs.Empty on topics.pallet_attach
only after pallet_core.attach_ok. It does not listen to contact.
"""
import argparse
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
import pallet_core as pc                              # noqa: E402
import pallet_place as pp                             # noqa: E402
import tag_core as tc                                 # noqa: E402
import stations                                       # noqa: E402

TOOL = "pallet_bench"

REQUIRED_KEYS = (
    "pallet.name", "pallet.fork_spacing_m", "pallet.tine_width_m",
    "pallet.pocket_clearance_y_m", "pallet.depth_m", "pallet.height_m",
    "pallet.deck_thickness_m", "pallet.yaw_max_rad", "pallet.height_max_m",
    "pallet.lift_m", "pallet.wall_clearance_m",
    "dock.station", "dock.marker_ahead_m", "dock.fork_reach_m",
    "dock.tip_standoff_m", "dock.staging_run_in_m", "dock.tag_thickness_m",
    "topics.pallet_attach", "topics.pallet_detach", "topics.fork_cmd",
    "topics.odom_ground_truth", "world.name", "vehicle.name",
    "vehicle.spawn.z", "timing.spawn_service_timeout_ms",
)

CYCLE = (
    "transit", "stage", "dock", "attach", "lift", "undock",
    "carry", "stage", "dock", "lower", "detach", "undock",
)


def empty_pub(topic):
    return ["gz", "topic", "-t", topic, "-m", "gz.msgs.Empty",
            "-p", "unused: true"]


def double_pub(topic, value):
    return ["gz", "topic", "-t", topic, "-m", "gz.msgs.Double",
            "-p", "data: {}".format(float(value))]


def quat_yaw(x, y, z, w):
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _pockets(cfg):
    opening = pc.pocket_opening_m(
        cfg.f("pallet.tine_width_m"), cfg.f("pallet.pocket_clearance_y_m"))
    z_min, z_max = pc.pocket_z(
        cfg.f("pallet.height_m"), cfg.f("pallet.deck_thickness_m"))
    return [
        pc.pocket_aabb(y, opening, cfg.f("pallet.depth_m"), z_min, z_max)
        for y in pc.pocket_centres_y(cfg.f("pallet.fork_spacing_m"))
    ]


def predicate(cfg, truck, pallet):
    """truck/pallet are dicts with x,y,z,yaw. Tips at lowered tine z."""
    tine_z = 0.075
    pockets = _pockets(cfg)
    z_min, z_max = pc.pocket_z(
        cfg.f("pallet.height_m"), cfg.f("pallet.deck_thickness_m"))
    tips = []
    for y in pc.pocket_centres_y(cfg.f("pallet.fork_spacing_m")):
        world = pc.fork_tip_world(
            truck["x"], truck["y"], truck["yaw"],
            cfg.f("dock.fork_reach_m"), y, tine_z)
        tips.append(pc.world_to_local(
            (pallet["x"], pallet["y"], pallet["z"]), pallet["yaw"], world))
    yaw_err = pc.wrap_angle(truck["yaw"] - pallet["yaw"])
    height_err = tine_z - (pallet["z"] + (z_min + z_max) / 2.0)
    ok = pc.attach_ok(
        tips, pockets, yaw_err, height_err,
        cfg.f("pallet.yaw_max_rad"), cfg.f("pallet.height_max_m"))
    return ok, {"yaw_err": yaw_err, "height_err": height_err, "tips": tips}


def _run(cmd, timeout=10):
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout)
        return (proc.stdout or "") + (proc.stderr or "")
    except Exception as exc:
        return str(exc)


def parse_named_pose(text, name):
    needle = 'name: "{}"'.format(name)
    i = text.find(needle)
    if i < 0:
        return None
    chunk = text[i:i + 1200]
    def grab(key):
        token = key + ":"
        if token not in chunk:
            return None
        raw = chunk.split(token, 1)[1].split()[0].rstrip(",")
        return float(raw)
    x, y, z = grab("x"), grab("y"), grab("z")
    qx, qy, qz, qw = grab("x"), grab("y"), grab("z"), grab("w")
    # First x/y/z are position; re-read orientation from the orientation block.
    ori = chunk.split("orientation", 1)
    if len(ori) < 2 or x is None:
        return None
    o = ori[1]
    def ograb(key):
        token = key + ":"
        if token not in o:
            return None
        return float(o.split(token, 1)[1].split()[0].rstrip(","))
    qx, qy, qz, qw = ograb("x"), ograb("y"), ograb("z"), ograb("w")
    if None in (x, y, z, qx, qy, qz, qw):
        return None
    return {"x": x, "y": y, "z": z, "yaw": quat_yaw(qx, qy, qz, qw)}


def live_poses(cfg):
    topic = "/world/{}/dynamic_pose/info".format(cfg.s("world.name"))
    text = _run(["gz", "topic", "-e", "-t", topic, "-n", "1"], timeout=8)
    truck = parse_named_pose(text, cfg.s("vehicle.name"))
    pallet = parse_named_pose(text, cfg.s("pallet.name"))
    return truck, pallet, text


def describe(cfg):
    print("=== m5v3 pallet bench ===")
    print("cycle     {}".format(" -> ".join(CYCLE)))
    print("attach    {}".format(cfg.s("topics.pallet_attach")))
    print("detach    {}".format(cfg.s("topics.pallet_detach")))
    print("mast      {}  lift {} m".format(
        cfg.s("topics.fork_cmd"), cfg.s("pallet.lift_m")))
    print("predicate pallet_core.attach_ok  yaw_max {} rad  z_max {} m"
          .format(cfg.s("pallet.yaw_max_rad"), cfg.s("pallet.height_max_m")))
    return 0


def status(cfg):
    st = stations.STATIONS[cfg.s("dock.station")]
    geo = tc.station_geometry(
        st["x"], st["y"], st["yaw"],
        marker_ahead_m=cfg.f("dock.marker_ahead_m"),
        fork_reach_m=cfg.f("dock.fork_reach_m"),
        tip_standoff_m=cfg.f("dock.tip_standoff_m"),
        staging_run_in_m=cfg.f("dock.staging_run_in_m"))
    docked = dc.docked_world(st, {
        "marker_ahead_m": cfg.s("dock.marker_ahead_m"),
        "fork_reach_m": cfg.s("dock.fork_reach_m"),
        "tip_standoff_m": cfg.s("dock.tip_standoff_m"),
        "staging_run_in_m": cfg.s("dock.staging_run_in_m")})
    pallet = pp._pose(cfg)
    truck = {"x": docked["x"], "y": docked["y"], "z": 0.0,
             "yaw": docked["pose_yaw"]}
    ok, detail = predicate(cfg, truck, pallet)
    print("=== m5v3 pallet status (docked arithmetic, not live pose) ===")
    print("truck     ({:.3f}, {:.3f}) yaw {:.4f}".format(
        truck["x"], truck["y"], truck["yaw"]))
    print("pallet    ({:.3f}, {:.3f}, {:.3f}) yaw {:.4f}".format(
        pallet["x"], pallet["y"], pallet["z"], pallet["yaw"]))
    print("attach_ok {}  yaw_err {:.4f}  height_err {:.4f}".format(
        ok, detail["yaw_err"], detail["height_err"]))
    print("marker    ({:.3f}, {:.3f})".format(*geo["marker"]))
    return 0 if ok else 1


def attach(cfg):
    truck, pallet, raw = live_poses(cfg)
    if truck is None or pallet is None:
        cfg.refuse("live gz poses for the truck and the pallet",
                   "/world/{}/dynamic_pose/info".format(cfg.s("world.name")),
                   "the topic replied: {}".format((raw or "<empty>")[:300]))
    ok, detail = predicate(cfg, truck, pallet)
    if not ok:
        cfg.refuse("pallet_core.attach_ok on the live poses",
                   _common.CONFIG + " (pallet.yaw_max_rad, height_max_m)",
                   "truck ({:.3f}, {:.3f}) yaw {:.4f}".format(
                       truck["x"], truck["y"], truck["yaw"]),
                   "pallet ({:.3f}, {:.3f}, {:.3f}) yaw {:.4f}".format(
                       pallet["x"], pallet["y"], pallet["z"], pallet["yaw"]),
                   "yaw_err {:.4f} height_err {:.4f}".format(
                       detail["yaw_err"], detail["height_err"]))
    out = _run(empty_pub(cfg.s("topics.pallet_attach")))
    print("attach ok  yaw_err {:.4f}  height_err {:.4f}".format(
        detail["yaw_err"], detail["height_err"]))
    if out.strip():
        print(out.strip())
    return 0


def seat_request(cfg):
    """gz set_pose body that puts the truck at the docked pose."""
    st = stations.STATIONS[cfg.s("dock.station")]
    docked = dc.docked_world(st, {
        "marker_ahead_m": cfg.s("dock.marker_ahead_m"),
        "fork_reach_m": cfg.s("dock.fork_reach_m"),
        "tip_standoff_m": cfg.s("dock.tip_standoff_m"),
        "staging_run_in_m": cfg.s("dock.staging_run_in_m")})
    yaw = docked["pose_yaw"]
    return (
        'name: "{}", position: {{x: {:.9f}, y: {:.9f}, z: {:.9f}}}, '
        'orientation: {{z: {:.9f}, w: {:.9f}}}'
    ).format(cfg.s("vehicle.name"), docked["x"], docked["y"],
             cfg.f("vehicle.spawn.z"), math.sin(yaw / 2.0),
             math.cos(yaw / 2.0))


def seat(cfg):
    world = cfg.s("world.name")
    req = seat_request(cfg)
    cmd = [
        "gz", "service", "-s", "/world/{}/set_pose".format(world),
        "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
        "--timeout", str(cfg.s("timing.spawn_service_timeout_ms")),
        "--req", req,
    ]
    reply = _run(cmd, timeout=30)
    if "data: true" not in reply:
        cfg.refuse("gz set_pose sat the truck at the docked pose",
                   "/world/{}/set_pose".format(world), reply or "<empty>")
    print("seated {}".format(req))
    return 0


def detach(cfg):
    out = _run(empty_pub(cfg.s("topics.pallet_detach")))
    print("detach")
    if out.strip():
        print(out.strip())
    return 0


def lift(cfg):
    out = _run(double_pub(cfg.s("topics.fork_cmd"), cfg.f("pallet.lift_m")))
    print("lift {} m".format(cfg.s("pallet.lift_m")))
    if out.strip():
        print(out.strip())
    return 0


def lower(cfg):
    out = _run(double_pub(cfg.s("topics.fork_cmd"), 0.0))
    print("lower 0.0 m")
    if out.strip():
        print(out.strip())
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="pallet_bench.py")
    sub = parser.add_subparsers(dest="cmd")
    for name in ("describe", "status", "seat", "attach", "detach",
                 "lift", "lower"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    return {
        "status": status, "seat": seat, "attach": attach, "detach": detach,
        "lift": lift, "lower": lower,
    }.get(args.cmd, describe)(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
