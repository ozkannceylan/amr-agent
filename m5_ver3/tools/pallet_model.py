#!/usr/bin/env python3
"""pallet_model.py - write a Gazebo SDF for the S5 pallet. F5 Task 3.

    python3 m5_ver3/tools/pallet_model.py describe
    python3 m5_ver3/tools/pallet_model.py write [--out DIR]

EUR 1200 x 800 x 144 mm, two pockets on the fork spacing. The pockets
are EMPTY: no collision occupies the tine volume, so DetachableJoint
can attach without the in-contact refusal Harmonic documents.

THE FLOOR IS NOT EDITED. The committed world stays referenced. `write`
only puts a file on disk; pallet_place.py spawns it.
"""
import argparse
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import pallet_core as pc                              # noqa: E402

TOOL = "pallet_model"

REQUIRED_KEYS = (
    "pallet.name", "pallet.model_dir", "pallet.length_m", "pallet.depth_m",
    "pallet.height_m", "pallet.deck_thickness_m", "pallet.mass_kg",
    "pallet.fork_spacing_m", "pallet.tine_width_m",
    "pallet.pocket_clearance_y_m", "pallet.child_link",
)

WOOD = (0.55, 0.40, 0.22, 1.0)


def model_path(pallet):
    rel = str(pallet["model_dir"]).replace("/", os.sep)
    return os.path.normpath(os.path.join(
        _common.REPO, rel, str(pallet["name"]) + ".sdf"))


def _box_xml(name, kind, x, y, z, sx, sy, sz):
    r, g, b, a = WOOD
    colour = "{:.3f} {:.3f} {:.3f} {:.3f}".format(r, g, b, a)
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


def sdf_from_spec(pal):
    """Dynamic model. Origin at the geometric centre. Openings on +X."""
    name = str(pal["name"])
    link = str(pal["child_link"])
    length = float(pal["length_m"])
    depth = float(pal["depth_m"])
    height = float(pal["height_m"])
    deck_t = float(pal["deck_thickness_m"])
    mass = float(pal["mass_kg"])
    opening = pc.pocket_opening_m(
        float(pal["tine_width_m"]), float(pal["pocket_clearance_y_m"]))
    z_min, z_max = pc.pocket_z(height, deck_t)
    half_h = height / 2.0
    deck_z = half_h - deck_t / 2.0
    stringer_h = z_max - z_min
    stringer_z = (z_min + z_max) / 2.0
    half_open = opening / 2.0
    # Outer stringers sit outside the pocket y-range; centre fills |y|
    # between the two pockets.
    left_c, right_c = pc.pocket_centres_y(float(pal["fork_spacing_m"]))
    outer_inner = left_c + half_open          # 0.36
    outer_width = length / 2.0 - outer_inner  # 0.24
    outer_y = outer_inner + outer_width / 2.0
    centre_width = (left_c - half_open) * 2.0  # 0.40
    ixx = mass / 12.0 * (length ** 2 + height ** 2)
    iyy = mass / 12.0 * (depth ** 2 + height ** 2)
    izz = mass / 12.0 * (depth ** 2 + length ** 2)
    parts = [
        '<?xml version="1.0"?>\n',
        '<sdf version="1.9">\n',
        '  <model name="{}">\n'.format(name),
        '    <static>false</static>\n',
        '    <link name="{}">\n'.format(link),
        '      <inertial>\n',
        '        <mass>{}</mass>\n'.format(mass),
        '        <inertia>\n',
        '          <ixx>{:.6f}</ixx><ixy>0</ixy><ixz>0</ixz>\n'.format(ixx),
        '          <iyy>{:.6f}</iyy><iyz>0</iyz>\n'.format(iyy),
        '          <izz>{:.6f}</izz>\n'.format(izz),
        '        </inertia>\n',
        '      </inertial>\n',
        _box_xml("deck", "collision", 0.0, 0.0, deck_z, depth, length, deck_t),
        _box_xml("deck_vis", "visual", 0.0, 0.0, deck_z, depth, length, deck_t),
        _box_xml("centre", "collision", 0.0, 0.0, stringer_z,
                 depth, centre_width, stringer_h),
        _box_xml("centre_vis", "visual", 0.0, 0.0, stringer_z,
                 depth, centre_width, stringer_h),
        _box_xml("outer_left", "collision", 0.0, outer_y, stringer_z,
                 depth, outer_width, stringer_h),
        _box_xml("outer_left_vis", "visual", 0.0, outer_y, stringer_z,
                 depth, outer_width, stringer_h),
        _box_xml("outer_right", "collision", 0.0, -outer_y, stringer_z,
                 depth, outer_width, stringer_h),
        _box_xml("outer_right_vis", "visual", 0.0, -outer_y, stringer_z,
                 depth, outer_width, stringer_h),
        '    </link>\n',
        '  </model>\n',
        '</sdf>\n',
    ]
    return "".join(parts), {"name": name, "opening_m": opening}


def describe(cfg):
    pal = {k.split(".", 1)[1]: cfg.s(k) for k in REQUIRED_KEYS}
    print("=== m5v3 pallet model ===")
    print("name      {}".format(pal["name"]))
    print("planform  {} x {} x {} m".format(
        pal["length_m"], pal["depth_m"], pal["height_m"]))
    print("pockets   spacing {} m, opening {:.3f} m".format(
        pal["fork_spacing_m"],
        pc.pocket_opening_m(float(pal["tine_width_m"]),
                            float(cfg.s("pallet.pocket_clearance_y_m")))))
    print("path      {}".format(model_path(pal)))
    return 0


def write(cfg, out_dir):
    pal = {
        "name": cfg.s("pallet.name"),
        "child_link": cfg.s("pallet.child_link"),
        "length_m": cfg.s("pallet.length_m"),
        "depth_m": cfg.s("pallet.depth_m"),
        "height_m": cfg.s("pallet.height_m"),
        "deck_thickness_m": cfg.s("pallet.deck_thickness_m"),
        "mass_kg": cfg.s("pallet.mass_kg"),
        "fork_spacing_m": cfg.s("pallet.fork_spacing_m"),
        "tine_width_m": cfg.s("pallet.tine_width_m"),
        "pocket_clearance_y_m": cfg.s("pallet.pocket_clearance_y_m"),
        "model_dir": cfg.s("pallet.model_dir"),
    }
    sdf, meta = sdf_from_spec(pal)
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, meta["name"] + ".sdf")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(sdf)
    print("=== m5v3 pallet model: write ===")
    print("path      {}".format(path))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="pallet_model.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    wr = sub.add_parser("write")
    wr.add_argument("--out", default=os.path.join(_common.M5V3, "gazebo",
                                                    "pallets"))
    args = parser.parse_args(argv)
    if args.cmd == "write":
        return write(cfg, args.out)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
