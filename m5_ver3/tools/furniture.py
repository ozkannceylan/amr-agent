#!/usr/bin/env python3
"""furniture.py - spawn F5 station furniture into the running world.

    python3 m5_ver3/tools/furniture.py describe
    python3 m5_ver3/tools/furniture.py place
    python3 m5_ver3/tools/furniture.py remove

CONSTRAINT 21. AprilTag markers are separate models SPAWNED by the
stack, never written into the committed world file. The create-service
idiom is spawn_truck()'s: sdf_filename + pose, reply captured and
matched. `write` of the SDF is tag_model.py's; this file only places
what that writer already put on disk.

NO TYPED POSE. The marker xy comes from tag_core.station_geometry off
m6/ipc/stations.py and config.yaml dock:; the yaw is tag_core.face_yaw
so the printed +X looks at the oncoming forks.
"""
import argparse
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
import tag_core as tc                                 # noqa: E402
import tag_model as tm                                # noqa: E402
import stations                                       # noqa: E402

TOOL = "furniture"

REQUIRED_KEYS = (
    "dock.family", "dock.tag_id", "dock.station",
    "dock.marker_ahead_m", "dock.fork_reach_m", "dock.tip_standoff_m",
    "dock.staging_run_in_m", "dock.marker_z_m", "dock.model_dir",
    "world.name", "timing.spawn_service_timeout_ms",
)

_REPO = os.path.normpath(os.path.join(_common.M5V3, os.pardir))


def model_path(dock):
    name = tm.model_name(dock["family"], int(dock["tag_id"]))
    rel = str(dock["model_dir"]).replace("/", os.sep)
    return os.path.normpath(os.path.join(_REPO, rel, name + ".sdf"))


def create_request(sdf_filename, name, pose):
    qx, qy, qz, qw = tc.yaw_quaternion(pose["yaw"])
    path = sdf_filename.replace("\\", "/")
    return (
        'sdf_filename: "{sdf}", name: "{n}", allow_renaming: false, '
        'pose: {{position: {{x: {x}, y: {y}, z: {z}}}, '
        'orientation: {{x: {qx}, y: {qy}, z: {qz}, w: {qw}}}}}'
    ).format(sdf=path, n=name, x=pose["x"], y=pose["y"], z=pose["z"],
             qx=qx, qy=qy, qz=qz, qw=qw)


def _station(cfg):
    name = cfg.s("dock.station")
    table = stations.STATIONS
    if name not in table:
        cfg.refuse("dock.station is a key of m6/ipc/stations.py",
                   _common.CONFIG + " (dock.station)",
                   "it reads {!r}; the table holds {}".format(
                       name, ", ".join(sorted(table))))
    return table[name]


def _pose(cfg):
    st = _station(cfg)
    geo = tc.station_geometry(
        st["x"], st["y"], st["yaw"],
        marker_ahead_m=cfg.f("dock.marker_ahead_m"),
        fork_reach_m=cfg.f("dock.fork_reach_m"),
        tip_standoff_m=cfg.f("dock.tip_standoff_m"),
        staging_run_in_m=cfg.f("dock.staging_run_in_m"))
    return tm.model_name(cfg.s("dock.family"), int(cfg.s("dock.tag_id"))), \
        tm.spawn_pose(geo["marker"], st["yaw"], cfg.f("dock.marker_z_m"))


def _gz(cfg, service, reqtype, req):
    cmd = ["gz", "service", "-s", service,
           "--reqtype", reqtype, "--reptype", "gz.msgs.Boolean",
           "--timeout", str(cfg.s("timing.spawn_service_timeout_ms")),
           "--req", req]
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=30).stdout
    except Exception as exc:                          # pragma: no cover
        return "gz service failed: {}".format(exc)


def describe(cfg):
    name, pose = _pose(cfg)
    print("=== m5v3 furniture ===")
    print("model     {}".format(name))
    print("path      {}".format(model_path({
        "family": cfg.s("dock.family"), "tag_id": cfg.s("dock.tag_id"),
        "model_dir": cfg.s("dock.model_dir")})))
    print("marker    ({:.3f}, {:.3f}, {:.3f}) yaw {:.4f}".format(
        pose["x"], pose["y"], pose["z"], pose["yaw"]))
    print("spawn     /world/{}/create  (sdf_filename, never a world edit)"
          .format(cfg.s("world.name")))
    return 0


def place(cfg):
    name, pose = _pose(cfg)
    path = model_path({
        "family": cfg.s("dock.family"), "tag_id": cfg.s("dock.tag_id"),
        "model_dir": cfg.s("dock.model_dir")})
    if not os.path.isfile(path):
        cfg.refuse("the marker SDF is on disk",
                   path,
                   "python3 m5_ver3/tools/tag_model.py write",
                   "that writer needs libapriltag; see tools/install_apriltag.sh")
    world = cfg.s("world.name")
    reply = _gz(cfg, "/world/{}/create".format(world),
                "gz.msgs.EntityFactory", create_request(path, name, pose))
    if "data: true" not in reply:
        cfg.refuse("the create service accepted {}".format(name),
                   "gz /world/{}/create".format(world),
                   "the service replied: {}".format(reply or "<empty>"))
    print("placed {} at ({:.3f}, {:.3f}, {:.3f})".format(
        name, pose["x"], pose["y"], pose["z"]))
    return 0


def remove(cfg):
    name, _pose_unused = _pose(cfg)
    world = cfg.s("world.name")
    reply = _gz(cfg, "/world/{}/remove".format(world),
                "gz.msgs.Entity",
                'name: "{}", type: MODEL'.format(name))
    if "data: true" not in reply:
        cfg.refuse("the remove service accepted {}".format(name),
                   "gz /world/{}/remove".format(world),
                   "the service replied: {}".format(reply or "<empty>"))
    print("removed {}".format(name))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="furniture.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    sub.add_parser("place")
    sub.add_parser("remove")
    args = parser.parse_args(argv)
    if args.cmd == "place":
        return place(cfg)
    if args.cmd == "remove":
        return remove(cfg)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
