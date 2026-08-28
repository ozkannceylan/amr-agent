#!/usr/bin/env python3
"""tag_model.py - write a Gazebo SDF for one AprilTag. F5 Task 1.

    python3 m5_ver3/tools/tag_model.py describe
    python3 m5_ver3/tools/tag_model.py write [--out DIR]

WHAT THIS FILE IS. tag_core.py is the arithmetic (bitmap, poses, the
trap-zone margin). This file is the THING IN THE WORLD: a static SDF
model whose black squares are tag_core.cells() of a family definition,
plus a white backing board with a collision so the global obstacle layer
has something to mark.

IT DOES NOT COPY A CODE TABLE. The tag36h11 codeword comes from
libapriltag's own tag36h11_create(), through ctypes, so a marker this
repository prints and a marker apriltag_ros decodes are the same object
by construction. `write` refuses if the library is not loadable rather
than falling back to a handwritten id.

THE TOY FAMILY IS FOR TESTS. test_tag_model.py drives sdf_from_bitmap
with the 4-bit family tag_core's selftest uses, so the SDF writer is
pinned without libapriltag. The shipped S5 marker is tag36h11 id 0 and
that path goes through the library.

THE FLOOR IS NOT EDITED. warehouse_ver3.sdf stays referenced, never
copied (CONTEXT.md). These models are spawned into the running world
the same way monitor_demo.py's box is, under a later flag. `write`
only puts files on disk.
"""
import argparse
import ctypes
import ctypes.util
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import tag_core as tc                                 # noqa: E402

TOOL = "tag_model"

REQUIRED_KEYS = (
    "dock.family", "dock.tag_id", "dock.size_m",
    "dock.width_at_border", "dock.total_width",
    "dock.station", "dock.marker_ahead_m", "dock.fork_reach_m",
    "dock.tip_standoff_m", "dock.staging_run_in_m",
    "dock.marker_z_m", "dock.tag_thickness_m",
    "apriltag.prefix", "apriltag.deb_prefix", "apriltag.lib",
)

WHITE = (1.0, 1.0, 1.0, 1.0)
BLACK = (0.05, 0.05, 0.05, 1.0)


class Family(object):
    """One AprilTag family, as the five numbers the bitmap needs."""

    def __init__(self, name, nbits, bit_x, bit_y, width_at_border,
                 total_width, codes):
        self.name = name
        self.nbits = int(nbits)
        self.bit_x = list(bit_x)
        self.bit_y = list(bit_y)
        self.width_at_border = int(width_at_border)
        self.total_width = int(total_width)
        self.codes = list(codes)

    def bitmap(self, tag_id):
        if tag_id < 0 or tag_id >= len(self.codes):
            raise ValueError(
                "tag id {} is outside 0..{} for {}".format(
                    tag_id, len(self.codes) - 1, self.name))
        return tc.bitmap(
            self.nbits, self.bit_x, self.bit_y,
            self.width_at_border, self.total_width, self.codes[tag_id])


def _apriltag_family_t():
    """apriltag_family_t from AprilTag 3.3 apriltag.h.

    ncodes, codes, width_at_border, total_width, reversed_border,
    nbits, bit_x, bit_y, h, name, impl. A layout mismatch shows up as
    garbage nbits and is refused in load_family.
    """
    class FamilyT(ctypes.Structure):
        _fields_ = [
            ("ncodes", ctypes.c_uint32),
            ("codes", ctypes.POINTER(ctypes.c_uint64)),
            ("width_at_border", ctypes.c_int),
            ("total_width", ctypes.c_int),
            ("reversed_border", ctypes.c_bool),
            ("nbits", ctypes.c_uint32),
            ("bit_x", ctypes.POINTER(ctypes.c_uint32)),
            ("bit_y", ctypes.POINTER(ctypes.c_uint32)),
            ("h", ctypes.c_uint32),
            ("name", ctypes.c_char_p),
            ("impl", ctypes.c_void_p),
        ]
    return FamilyT


def library_candidates(extra=()):
    """Every place libapriltag might live, find_library first.

    ctypes.util.find_library asks ldconfig and does not see a tree
    unpacked under $HOME. The vendored .so from install_apriltag.sh
    is passed in `extra` so write() and the detector load the same
    object.
    """
    found = ctypes.util.find_library("apriltag")
    out = []
    if found:
        out.append(found)
    for path in extra:
        if path and path not in out:
            out.append(path)
    return out


def vendored_lib(cfg):
    prefix = os.path.expanduser(cfg.s("apriltag.prefix"))
    return os.path.normpath(os.path.join(
        prefix, cfg.s("apriltag.deb_prefix").replace("/", os.sep),
        cfg.s("apriltag.lib").replace("/", os.sep)))


def load_family(name, extra=()):
    """tag36h11 (or another shipped family) from libapriltag.

    REFUSES rather than guessing if the library is missing or the
    family constructor is absent. A handwritten code table in this
    repository would be a third copy of the marker.
    """
    last = "ctypes.util.find_library returned None"
    lib = None
    for soname in library_candidates(extra):
        try:
            lib = ctypes.CDLL(soname)
            last = soname
            break
        except OSError as exc:
            last = "{}: {}".format(soname, exc)
            lib = None
    if lib is None:
        raise LookupError(
            "libapriltag is not on this machine ({}). "
            "Install it, or run tools/install_apriltag.sh.".format(last))
    create_name = "{}_create".format(name)
    destroy_name = "{}_destroy".format(name)
    if not hasattr(lib, create_name):
        raise LookupError(
            "libapriltag has no {} - the family {} is not in this "
            "build".format(create_name, name))
    FamilyT = _apriltag_family_t()
    getattr(lib, create_name).restype = ctypes.POINTER(FamilyT)
    ptr = getattr(lib, create_name)()
    if not ptr:
        raise LookupError("{} returned NULL".format(create_name))
    fam = ptr.contents
    nbits = int(fam.nbits)
    ncodes = int(fam.ncodes)
    if nbits < 4 or nbits > 64 or ncodes < 1:
        getattr(lib, destroy_name)(ptr)
        raise LookupError(
            "libapriltag family {} looks like a ctypes layout mismatch "
            "(nbits={}, ncodes={})".format(name, nbits, ncodes))
    bit_x = [int(fam.bit_x[i]) for i in range(nbits)]
    bit_y = [int(fam.bit_y[i]) for i in range(nbits)]
    codes = [int(fam.codes[i]) for i in range(ncodes)]
    width = int(fam.width_at_border)
    total = int(fam.total_width)
    getattr(lib, destroy_name)(ptr)
    return Family(name, nbits, bit_x, bit_y, width, total, codes)


def _colour_xml(rgba):
    r, g, b, a = rgba
    return ("{:.3f} {:.3f} {:.3f} {:.3f}".format(r, g, b, a))


def _box_xml(name, kind, x, y, z, sx, sy, sz, rgba):
    colour = _colour_xml(rgba)
    return (
        "      <{kind} name=\"{name}\">\n"
        "        <pose>{x:.9f} {y:.9f} {z:.9f} 0 0 0</pose>\n"
        "        <geometry><box><size>{sx:.9f} {sy:.9f} {sz:.9f}"
        "</size></box></geometry>\n"
        "        <material><ambient>{c}</ambient><diffuse>{c}</diffuse>"
        "</material>\n"
        "      </{kind}>\n"
    ).format(kind=kind, name=name, x=x, y=y, z=z, sx=sx, sy=sy, sz=sz,
             c=colour)


def sdf_from_bitmap(name, rows, size_m, width_at_border, thickness_m):
    """One static model: white tile, black squares on the +X face.

    Model frame: +X out of the printed face (tag_core.face_yaw points
    this at the truck), +Y = u (right as viewed from the front),
    +Z = v (up). Collision is ONE box the size of the tile - the nav
    lidar at z = 1.80 will miss a 0.80 m tag, but a later back-board
    that reaches the scan plane reuses this writer.
    """
    tile = tc.tile_size(size_m, width_at_border, len(rows))
    black = tc.cells(rows, size_m, width_at_border, colour=tc.BLACK)
    cell = tc.cell_size(size_m, width_at_border)
    ink = min(0.002, thickness_m / 4.0)
    parts = [
        '<?xml version="1.0"?>\n',
        '<sdf version="1.9">\n',
        '  <model name="{}">\n'.format(name),
        '    <static>true</static>\n',
        '    <link name="tag">\n',
        _box_xml("board", "collision", 0.0, 0.0, 0.0,
                 thickness_m, tile, tile, WHITE),
        _box_xml("backing", "visual", 0.0, 0.0, 0.0,
                 thickness_m, tile, tile, WHITE),
    ]
    for i, (u, v, edge) in enumerate(black):
        parts.append(_box_xml(
            "ink_{}".format(i), "visual",
            thickness_m / 2.0 + ink / 2.0, u, v,
            ink, edge, edge, BLACK))
    parts.extend([
        '    </link>\n',
        '  </model>\n',
        '</sdf>\n',
    ])
    return "".join(parts), {
        "name": name,
        "tile_m": tile,
        "cell_m": cell,
        "black_cells": len(black),
        "thickness_m": thickness_m,
    }


def model_name(family, tag_id):
    return "{}_{}".format(family, int(tag_id))


def spawn_pose(marker_xy, travel_yaw_rad, marker_z_m):
    """World pose of the model origin: marker face centre, facing the truck."""
    return {
        "x": float(marker_xy[0]),
        "y": float(marker_xy[1]),
        "z": float(marker_z_m),
        "roll": 0.0,
        "pitch": 0.0,
        "yaw": tc.face_yaw(travel_yaw_rad),
    }


def describe(cfg):
    print("=== m5v3 tag model ===")
    print("family    {} id {}".format(cfg.s("dock.family"),
                                      cfg.s("dock.tag_id")))
    print("size      {} m black square, tile {} x {} cells".format(
        cfg.s("dock.size_m"), cfg.s("dock.width_at_border"),
        cfg.s("dock.total_width")))
    print("station   {}".format(cfg.s("dock.station")))
    print("z         {} m  thickness {} m".format(
        cfg.s("dock.marker_z_m"), cfg.s("dock.tag_thickness_m")))
    print("")
    print("write     needs libapriltag on this machine")
    print("tests     drive sdf_from_bitmap with a toy family; no library")
    return 0


def write(cfg, out_dir):
    family_name = cfg.s("dock.family")
    tag_id = int(cfg.s("dock.tag_id"))
    try:
        family = load_family(family_name, extra=(vendored_lib(cfg),))
    except LookupError as exc:
        cfg.refuse("libapriltag provides family {}".format(family_name),
                   "tools/tag_model.py load_family()",
                   str(exc),
                   "the marker is generated from the detector's own "
                   "library so the two cannot drift. No handwritten "
                   "code table lives in this repository.")
    if (family.width_at_border != int(cfg.s("dock.width_at_border"))
            or family.total_width != int(cfg.s("dock.total_width"))):
        cfg.refuse("config.yaml dock: matches the loaded family",
                   _common.CONFIG + " (dock.width_at_border, "
                   "dock.total_width)",
                   "library: width_at_border={} total_width={}".format(
                       family.width_at_border, family.total_width),
                   "config:  width_at_border={} total_width={}".format(
                       cfg.s("dock.width_at_border"),
                       cfg.s("dock.total_width")))
    rows = family.bitmap(tag_id)
    name = model_name(family_name, tag_id)
    sdf, meta = sdf_from_bitmap(
        name, rows, cfg.f("dock.size_m"),
        family.width_at_border, cfg.f("dock.tag_thickness_m"))
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + ".sdf")
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(sdf)
    print("=== m5v3 tag model: write ===")
    print("path      {}".format(path))
    print("name      {}".format(meta["name"]))
    print("tile      {:.4f} m".format(meta["tile_m"]))
    print("black     {} cells".format(meta["black_cells"]))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="tag_model.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    wr = sub.add_parser("write")
    wr.add_argument("--out", default=os.path.join(_common.M5V3, "gazebo",
                                                    "tags"))
    args = parser.parse_args(argv)
    if args.cmd == "write":
        return write(cfg, args.out)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
