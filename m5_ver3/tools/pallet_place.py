#!/usr/bin/env python3
"""pallet_place.py - spawn the S5 pallet into the running world. F5 Task 3.

    python3 m5_ver3/tools/pallet_place.py describe
    python3 m5_ver3/tools/pallet_place.py place
    python3 m5_ver3/tools/pallet_place.py remove

CONSTRAINT 21. The pallet is a create-service call, never a world-file
edit. CONSTRAINT 23. This file does not attach; attach is pallet_core
plus a gz Empty on topics.pallet_attach after the predicate holds.
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
_IPC = os.path.normpath(os.path.join(_HERE, os.pardir, os.pardir, "m6", "ipc"))
if _IPC not in sys.path:
    sys.path.insert(0, _IPC)

import _common                                        # noqa: E402
import furniture as furn                              # noqa: E402
import pallet_core as pc                              # noqa: E402
import pallet_model as pm                             # noqa: E402
import tag_core as tc                                 # noqa: E402
import stations                                       # noqa: E402

TOOL = "pallet_place"

REQUIRED_KEYS = (
    "pallet.name", "pallet.model_dir", "pallet.wall_clearance_m",
    "pallet.depth_m", "pallet.height_m",
    "dock.station", "dock.marker_ahead_m", "dock.fork_reach_m",
    "dock.tip_standoff_m", "dock.staging_run_in_m", "dock.tag_thickness_m",
    "world.name", "timing.spawn_service_timeout_ms",
)


def model_path(pallet):
    return pm.model_path(pallet)


def _station(cfg):
    name = cfg.s("dock.station")
    table = stations.STATIONS
    if name not in table:
        cfg.refuse("dock.station is a key of m6/ipc/stations.py",
                   _common.CONFIG + " (dock.station)",
                   "it reads {!r}".format(name))
    return table[name]


def _pose(cfg):
    st = _station(cfg)
    geo = tc.station_geometry(
        st["x"], st["y"], st["yaw"],
        marker_ahead_m=cfg.f("dock.marker_ahead_m"),
        fork_reach_m=cfg.f("dock.fork_reach_m"),
        tip_standoff_m=cfg.f("dock.tip_standoff_m"),
        staging_run_in_m=cfg.f("dock.staging_run_in_m"))
    return pc.spawn_pose(
        geo["marker"], st["yaw"],
        wall_clearance_m=cfg.f("pallet.wall_clearance_m"),
        depth_m=cfg.f("pallet.depth_m"),
        height_m=cfg.f("pallet.height_m"),
        tag_thickness_m=cfg.f("dock.tag_thickness_m"))


def describe(cfg):
    pose = _pose(cfg)
    name = cfg.s("pallet.name")
    print("=== m5v3 pallet ===")
    print("model     {}".format(name))
    print("path      {}".format(model_path({
        "name": name, "model_dir": cfg.s("pallet.model_dir")})))
    print("origin    ({:.3f}, {:.3f}, {:.3f}) yaw {:.4f}".format(
        pose["x"], pose["y"], pose["z"], pose["yaw"]))
    print("spawn     /world/{}/create  (sdf_filename, never a world edit)"
          .format(cfg.s("world.name")))
    return 0


def place(cfg):
    name = cfg.s("pallet.name")
    pose = _pose(cfg)
    path = model_path({"name": name, "model_dir": cfg.s("pallet.model_dir")})
    if not os.path.isfile(path):
        cfg.refuse("the pallet SDF is on disk", path,
                   "python3 m5_ver3/tools/pallet_model.py write")
    world = cfg.s("world.name")
    reply = furn._gz(cfg, "/world/{}/create".format(world),
                     "gz.msgs.EntityFactory",
                     furn.create_request(path, name, pose))
    if "data: true" not in reply:
        cfg.refuse("the create service accepted {}".format(name),
                   "gz /world/{}/create".format(world),
                   "the service replied: {}".format(reply or "<empty>"))
    print("placed {} at ({:.3f}, {:.3f}, {:.3f})".format(
        name, pose["x"], pose["y"], pose["z"]))
    return 0


def remove(cfg):
    name = cfg.s("pallet.name")
    world = cfg.s("world.name")
    reply = furn._gz(cfg, "/world/{}/remove".format(world),
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
    parser = argparse.ArgumentParser(prog="pallet_place.py")
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
