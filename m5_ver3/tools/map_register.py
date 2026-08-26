#!/usr/bin/env python3
"""map_register.py - where this map IS against the building, how well it
fits it, and whether the drive that made it fitted the floor.

    python3 m5_ver3/tools/map_register.py derive                 # print
    python3 m5_ver3/tools/map_register.py derive --write         # commit
    python3 m5_ver3/tools/map_register.py show
    python3 m5_ver3/tools/map_register.py clearance <session>

NEEDS NO ROS, NO GAZEBO AND NO RIG. It reads a .pgm, a .yaml, an .sdf and
a CSV, and it runs on the owner's Windows python exactly as
tools/sensor_evidence.py's `analyse` half does - because a figure that can
only be recomputed on the machine that produced it is a figure nobody can
check.

THE ARITHMETIC IS NOT IN THIS FILE. Every threshold, fit, transform and
distance is tools/map_core.py, where tests/test_map_core.py reaches it on
geometry the test builds itself. What is here is file reading, config
reading, printing and the one file this program writes.

---- THE INSTRUMENT FLOOR IS PRINTED BEFORE THE SCORE, EVERY TIME ----

The registration residual is the largest distance between a kept grid
wall point and where the fitted rigid transform says that wall is. NO
LOCALISATION ERROR SMALLER THAN IT IS A MEASUREMENT OF THE LOCALISER, and
it is printed first for that reason rather than tucked under a heading.
It is mostly the grid's own internal SHEAR - the amount by which the map
is not a rigid copy of the building - and a rigid transform cannot absorb
that by construction, which is why the transform is rigid.

---- AND THE SCORE IS ABSOLUTE, WHICH MEANS IT IS NOT THE TRANSFORM ----

The spans this program prints are distances between two surfaces INSIDE
the map. They do not pass through the registration at all, so no choice
made while fitting can flatter them: a grid whose metres are one per cent
long reports a 48.00 m hall as 48.48 m however it is registered.
  THE ALTERNATIVE IS THE ONE THE m5_ver1 LINEAGE HAD TO WITHDRAW.
  sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md 12.8: an error measured by
  anchoring the estimate onto truth at the first sample is zero at the
  anchor BY CONSTRUCTION, and an estimator that is consistently 0.3 m
  wrong scores near zero. Nothing here is anchored to anything.
"""
import argparse
import hashlib
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as core                          # noqa: E402
import map_core as mc                                 # noqa: E402

TOOL = "map_register"

# MAINTENANCE OBLIGATION: a key read below is a key listed here, refused
# by its DOTTED name before a single file is opened.
REQUIRED_KEYS = (
    "world.file", "map.dir", "map.name",
    "map.registration.file", "map.registration.trim_cells",
    "map.registration.min_points", "map.registration.span_deg",
    "map.registration.steps", "map.registration.walls",
    "map.registration.held_out",
    "map.score.spans", "map.score.hall",
    "map.clearance.fore_m", "map.clearance.aft_m",
    "map.clearance.half_width_m",
    "evidence.dir", "evidence.analyse.max_pair_gap_s",
    "vehicle.rear_axle_offset_m", "vehicle.spawn.yaw",
)

#: The m5_ver1 map's registration, for the comparison row and NOTHING
#: else. It is a DIFFERENT FLOOR - a 30 x 20 m hall, an 8.0 m ideal
#: scanner, a different vehicle and a different mapping route - so it is
#: not a target and it is not a baseline. It is the only other number
#: this repository has of the same KIND, measured by the same method, and
#: a figure with nothing beside it is a figure nobody can size.
#: (sim/maps/warehouse/warehouse_registration.yaml, 2026-08-04.)
VER1 = {"rms": 0.040363, "max": 0.141100, "shear_deg": 0.325049,
        "points": 1444,
        "what": "m5_ver1 warehouse (30 x 20 m, ideal 8 m scanner)"}


def md5(path):
    digest = hashlib.md5()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_path(path):
    """A path relative to the repository root, with FORWARD SLASHES.

    The committed registration is read by both pythons this track uses -
    the owner's on Windows and the rig's inside WSL - and a path written
    with os.sep on one of them is a filename on the other. Every path
    this program writes into a file goes through here.
    """
    return os.path.relpath(path, _common.REPO).replace(os.sep, "/")


def read_text(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def fail(cfg, exc, owner):
    """A MapError, refused in the one voice logs/ already carries."""
    cfg.refuse(str(exc), owner)


def artifact(cfg, name=None):
    name = name or cfg.s("map.name")
    return os.path.join(_common.REPO, cfg.s("map.dir"), name), name


def normal_of(entry):
    n = (float(entry["nx"]), float(entry["ny"]))
    length = math.hypot(n[0], n[1])
    return (n[0] / length, n[1] / length)


# ----------------------------------------------------------------------
# derive
# ----------------------------------------------------------------------

def load_grid(cfg, map_yaml):
    """The grid, its metadata and the mask, from the pair on disk."""
    try:
        meta = mc.parse_map_yaml(read_text(map_yaml))
    except mc.MapError as exc:
        fail(cfg, exc, map_yaml)
    image = os.path.join(os.path.dirname(os.path.abspath(map_yaml)),
                         meta["image"])
    if not os.path.isfile(image):
        cfg.refuse("the grid named by the map yaml is beside it", map_yaml,
                   "it names image: {} and there is no such file "
                   "in {}".format(meta["image"], os.path.dirname(image)))
    with open(image, "rb") as handle:
        data = handle.read()
    try:
        grid = mc.parse_pgm(data)
        mask = mc.occupied_mask(grid, meta)
    except mc.MapError as exc:
        fail(cfg, exc, image)
    return meta, image, grid, mask


def world_walls(cfg, world_text, world_path):
    """Every configured anchor wall, as (name, outward normal, offset)."""
    out = []
    entries = cfg.raw("map.registration.walls")
    if not isinstance(entries, list) or not entries:
        cfg.refuse("map.registration.walls is a non-empty list",
                   _common.CONFIG, "it reads {!r}".format(entries))
    for entry in entries:
        normal = normal_of(entry)
        try:
            box = mc.sdf_box(world_text, entry["model"])
        except mc.MapError as exc:
            fail(cfg, exc, world_path)
        out.append((entry["model"], normal, mc.inner_face(box, normal)))
    return out


def held_out_surface(cfg, world_text, world_path):
    """The surface the fit is NOT allowed to see, and its own windows."""
    entry = cfg.raw("map.registration.held_out")
    normal = normal_of(entry)
    models = [m.strip() for m in str(entry["models"]).split(",") if m.strip()]
    faces = []
    windows = []
    for model in models:
        try:
            box = mc.sdf_box(world_text, model)
        except mc.MapError as exc:
            fail(cfg, exc, world_path)
        faces.append(mc.inner_face(box, normal))
        windows.append((box.x0, box.x1) if abs(normal[1]) > 0.5
                       else (box.y0, box.y1))
    if max(faces) - min(faces) > 1e-6:
        cfg.refuse(
            "the held-out models share one face", world_path,
            "{} present faces at {} - they are not one surface and a "
            "line through them would be a line through neither".format(
                ", ".join(models),
                ", ".join("{:.4f}".format(f) for f in faces)))
    return {"name": str(entry["name"]), "normal": normal,
            "offset": faces[0], "windows": windows, "models": models,
            "against": str(entry["against"])}


def fit_wall(cfg, mask, grid, meta, normal, label, windows=None):
    trim = cfg.f("map.registration.trim_cells")
    floor = cfg.i("map.registration.min_points")
    points = mc.extract_extremes(mask, grid.width, grid.height, meta,
                                 normal, windows=windows)
    try:
        fit = mc.fit_line_robust(points, normal, meta["resolution"],
                                 floor, trim)
    except mc.MapError as exc:
        cfg.refuse("{}: {}".format(label, exc), _common.CONFIG +
                   " (map.registration.trim_cells / min_points)")
    return points, fit


def cmd_derive(cfg, args):
    out_dir, name = artifact(cfg, args.name)
    map_yaml = args.map or os.path.join(out_dir, name + ".yaml")
    world_path = os.path.join(_common.REPO, cfg.s("world.file"))
    if not os.path.isfile(world_path):
        cfg.refuse("the world SDF is where config.yaml says", world_path,
                   "world.file reads {}".format(cfg.s("world.file")))
    meta, image, grid, mask = load_grid(cfg, map_yaml)
    world_text = read_text(world_path)
    trim = cfg.f("map.registration.trim_cells")
    floor = cfg.i("map.registration.min_points")

    occupied = sum(1 for v in mask if v)
    print("=== m5v3 map registration: derive ===")
    print("")
    print("grid       {}".format(os.path.relpath(image, _common.REPO)))
    print("           {} x {} cells at {:.3f} m  =  {:.2f} x {:.2f} m"
          .format(grid.width, grid.height, meta["resolution"],
                  grid.width * meta["resolution"],
                  grid.height * meta["resolution"]))
    print("           origin ({:+.4f}, {:+.4f}, {:+.4f})"
          .format(*meta["origin"]))
    print("           {} occupied cells at occupied_thresh {:.3f}, READ "
          "FROM THE YAML".format(occupied, meta["occupied_thresh"]))
    print("           md5 {}".format(md5(image)))
    print("world      {}".format(cfg.s("world.file")))
    print("           md5 {}".format(md5(world_path)))
    print("")
    print("THE TRIMMING RULE, STATED BEFORE ANY NUMBER IT PRODUCED.")
    print("  Every grid line that has an occupied cell contributes ONE")
    print("  candidate - the outermost one - and nothing is filtered at")
    print("  extraction. The line is then SEEDED by a repeated median")
    print("  (50 % breakdown), trimmed at {:.0f} cells = {:.3f} m, and"
          .format(trim, trim * meta["resolution"]))
    print("  refitted by total least squares until nothing more drops.")
    print("  A least-squares SEED converges onto whatever stands in front")
    print("  of the wall and reports a tight residual against it, which")
    print("  is the failure that looks like success (docs/LESSONS.md 93).")
    print("")

    anchors = world_walls(cfg, world_text, world_path)
    held = held_out_surface(cfg, world_text, world_path)

    span_deg = cfg.f("map.registration.span_deg")
    # ---- WHERE THE SEARCH STARTS, AND IT IS NOT ZERO ON THIS TRACK ----
    #
    # slam_toolbox's map frame is initialised on the first corrected pose,
    # which is the ODOM frame's origin - and this stack's odom frame is
    # the vehicle AT SPAWN (nodes/wheel_odom_core.py reset()s to the
    # origin with yaw zero, and the EKF's world_frame IS that frame). The
    # truck spawns at yaw pi, so the map's x axis points at world -x and
    # the transform this program is looking for is a HALF TURN, not a
    # small angle.
    #   THE HINT IS THEREFORE -spawn.yaw AND IT IS DERIVED, NOT TYPED.
    #   It is only a hint: the scan still runs +-span_deg around it and
    #   REFUSES a minimum that lands on its own edge, so a map whose
    #   frame is somewhere else is refused rather than fitted to the
    #   wrong half turn.
    if args.hint_deg is None:
        hint = core.normalise_angle(-cfg.f("vehicle.spawn.yaw"))
    else:
        hint = math.radians(args.hint_deg)
    print("rotation search   {:+.4f} deg +- {:.1f} deg, {} steps".format(
        math.degrees(hint), span_deg, cfg.i("map.registration.steps")))
    print("  the hint is -vehicle.spawn.yaw: the map frame is the odom")
    print("  frame and the odom frame is the vehicle at spawn, which")
    print("  stands at yaw {:+.5f}.".format(cfg.f("vehicle.spawn.yaw")))
    print("")

    # THE SCAN DIRECTION IS THE NORMAL IN *MAP* COORDINATES. A north wall
    # of the world is not the top of this grid: with the map frame half a
    # turn from the world it is the bottom of it, and a scan that went
    # looking for the outermost cell in the wrong direction would find
    # the OPPOSITE wall and fit it beautifully. The hint above is enough
    # to point the scan - it only has to be right to within a quarter
    # turn - and the transform is solved afterwards from the points it
    # collected.
    walls = []
    fits = {}
    scanned = {}
    for model, normal, offset in anchors:
        scan_normal = mc.rotate(normal, hint)
        scanned[model] = scan_normal
        points, fit = fit_wall(cfg, mask, grid, meta, scan_normal, model)
        fits[model] = fit
        walls.append((model, normal, offset, fit.kept))

    try:
        reg = mc.derive_transform(walls, hint=hint,
                                  span_rad=math.radians(span_deg),
                                  steps=cfg.i("map.registration.steps"))
    except mc.MapError as exc:
        fail(cfg, exc, _common.CONFIG + " (map.registration.span_deg)")

    # EACH WALL'S OWN ROTATION IS REPORTED AGAINST THE FITTED THETA and
    # not against the world's axes, because the map's axes are half a
    # turn from the world's on this track and "-179.55 deg" is not a
    # number anybody can read. What matters is the SPREAD - the grid's
    # internal shear, which a rigid transform cannot absorb and which is
    # most of what the residual below is.
    rotations = [math.degrees(core.normalise_angle(
        mc.wall_rotation(fits[m], n) - reg["theta_rad"]))
        for m, n, _, _ in walls]
    shear = max(rotations) - min(rotations)

    print("| wall | outward n (world) | scanned as (map) | true face | "
          "extremes | kept | dropped | fit rms | own rotation |")
    print("|---|---|---|---|---|---|---|---|---|")
    for i, (model, normal, offset, kept) in enumerate(walls):
        scan = scanned[model]
        print("| {} | ({:+.0f}, {:+.0f}) | ({:+.2f}, {:+.2f}) | {:.3f} m | "
              "{} | {} | {} | {:.4f} m | {:+.4f} deg |".format(
                  model, normal[0], normal[1], scan[0], scan[1], offset,
                  len(kept) + fits[model].dropped, len(kept),
                  fits[model].dropped, fits[model].rms, rotations[i]))
    print("")
    print("  `own rotation` is against the FITTED theta below, not against")
    print("  the world's axes: the map frame is half a turn from the world")
    print("  and the useful quantity is the SPREAD.")
    print("")

    print("    THE INSTRUMENT FLOOR")
    print("    residual rms {:.4f} m over {} wall points"
          .format(reg["residual_rms_m"], reg["n_wall_points"]))
    print("    residual MAX {:.4f} m   <- NO LOCALISATION FIGURE AT OR "
          "BELOW THIS".format(reg["residual_max_m"]))
    print("                            IS A MEASUREMENT OF THE LOCALISER")
    print("    internal shear {:.4f} deg  - what a rigid transform cannot"
          .format(shear))
    print("                              absorb, and most of what the")
    print("                              residual above IS")
    print("")
    print("    p_map = R(theta) . p_world + t")
    print("    theta = {:+.9f} rad = {:+.9f} deg"
          .format(reg["theta_rad"], reg["theta_deg"]))
    print("    t     = ({:+.9f}, {:+.9f}) m"
          .format(reg["t_x_m"], reg["t_y_m"]))
    print("")
    for wall in reg["walls"]:
        print("      {:<12} {:>5} pts   rms {:.4f}   max {:.4f}".format(
            wall["name"], wall["points"], wall["residual_rms_m"],
            wall["residual_max_m"]))
    print("")

    # ---- the held-out surface, extracted through the derived transform
    #
    # THE TRANSFORM DECIDES WHERE TO LOOK AND NOT WHAT IS FOUND. The
    # windows are the held-out models' OWN extents in the world, pushed
    # through the registration so they can be applied to map columns; the
    # position the fit then reports is the grid's to say. A window is a
    # selection ALONG the surface and never across it, which is the
    # distinction map_core.extract_extremes' header measures.
    #
    # A face perpendicular to a unit axis normal sits at p = d * n along
    # that axis, so an outward normal of (0, -1) at d = 14.000 is the
    # world line y = -14.000.
    nrm = held["normal"]
    if abs(nrm[1]) > 0.5:
        fixed = held["offset"] * nrm[1]
        ends = [((lo, fixed), (hi, fixed)) for lo, hi in held["windows"]]
        axis = 0
    else:
        fixed = held["offset"] * nrm[0]
        ends = [((fixed, lo), (fixed, hi)) for lo, hi in held["windows"]]
        axis = 1
    windows = []
    for start, stop in ends:
        a = mc.world_to_map(reg, start[0], start[1])
        b = mc.world_to_map(reg, stop[0], stop[1])
        windows.append((min(a[axis], b[axis]), max(a[axis], b[axis])))
    points, held_fit = fit_wall(cfg, mask, grid, meta,
                                mc.rotate(held["normal"], reg["theta_rad"]),
                                held["name"], windows=windows)
    fits[held["name"]] = held_fit
    print("HELD OUT OF THE FIT: {} ({})".format(
        held["name"], ", ".join(held["models"])))
    print("  the transform above was solved WITHOUT these points, so what")
    print("  they say about the map is not a thing the fit arranged.")
    print("  true face {:.3f} m | extremes {} | kept {} | dropped {} | "
          "fit rms {:.4f} m | own rotation {:+.4f} deg".format(
              held["offset"], len(points), len(held_fit.kept),
              held_fit.dropped, held_fit.rms,
              math.degrees(core.normalise_angle(
                  mc.wall_rotation(held_fit, held["normal"])
                  - reg["theta_rad"]))))
    print("")

    truth = {model: offset for model, _, offset in anchors}
    truth[held["name"]] = held["offset"]
    spans = []
    print("    THE ABSOLUTE SCORE - spans INSIDE the map against the")
    print("    world's own dimensions. The registration is not in them.")
    print("")
    print("| span | true | measured | error | in cells |")
    print("|---|---|---|---|---|")
    for entry in cfg.raw("map.score.spans"):
        a, b = str(entry["a"]), str(entry["b"])
        for side in (a, b):
            if side not in fits:
                cfg.refuse("map.score.spans names a surface that was "
                           "fitted", _common.CONFIG,
                           "{!r} is neither an anchor wall nor the "
                           "held-out surface".format(side))
        derived = truth[a] + truth[b]
        stated = float(entry["true_m"])
        if abs(derived - stated) > 1e-6:
            cfg.refuse(
                "config.yaml's stated true span agrees with the world",
                "{} and {}".format(_common.CONFIG, cfg.s("world.file")),
                "map.score.spans {!r} says {:.4f} m; the SDF's own faces "
                "give {:.4f} m".format(str(entry["name"]), stated, derived))
        try:
            measured = mc.span_between(fits[a], fits[b])
        except mc.MapError as exc:
            fail(cfg, exc, _common.CONFIG + " (map.score.spans)")
        error = measured - derived
        spans.append({"name": str(entry["name"]), "a": a, "b": b,
                      "true_m": derived, "measured_m": measured,
                      "error_m": error})
        print("| {} | {:.3f} m | {:.4f} m | {:+.4f} m | {:+.2f} |".format(
            entry["name"], derived, measured, error,
            error / meta["resolution"]))
    print("")
    # ---- DOES IT COVER THE FLOOR, and does it claim anything outside
    #      the building at all ----
    faces = [(normal_of(e), mc.sdf_box(world_text, e["model"]))
             for e in cfg.raw("map.score.hall")]
    hall = mc.hall_rectangle([(n, mc.inner_face(b, n)) for n, b in faces])
    building = mc.hall_rectangle([(n, mc.outer_face(b, n))
                                  for n, b in faces])
    obstacles = mc.sdf_obstacles(world_text)
    open_m2 = mc.open_floor_area(hall, obstacles)
    census = mc.grid_census(grid, meta, reg, hall, building, mc.map_to_world)
    area = census["cell_area_m2"]
    occ = (census["occupied_hall"] + census["occupied_fabric"]
           + census["occupied_outside"])
    free = (census["free_hall"] + census["free_fabric"]
            + census["free_outside"])
    print("    COVERAGE - the map against the building's own extent")
    print("    hall       {:.2f} x {:.2f} m, the four walls' INNER faces"
          .format(hall.x1 - hall.x0, hall.y1 - hall.y0))
    print("    building   {:.2f} x {:.2f} m, their OUTER faces. The band"
          .format(building.x1 - building.x0, building.y1 - building.y0))
    print("               between the two is the wall FABRIC, and a cell")
    print("               there is a wall rather than a finding.")
    print("    open floor {:.1f} m2  (the hall less {} obstacle "
          "footprints)".format(open_m2, len(obstacles)))
    print("    mapped FREE inside it: {:.1f} m2 = {:.2f} %"
          .format(census["free_hall"] * area,
                  100.0 * census["free_hall"] * area / open_m2))
    print("    cells      {} occupied, {} free, {} unknown, {} total"
          .format(occ, free, census["unknown"], census["cells"]))
    print("    in the wall fabric   {} occupied, {} free"
          .format(census["occupied_fabric"], census["free_fabric"]))
    print("    OUTSIDE THE BUILDING {} occupied, {} free"
          .format(census["occupied_outside"], census["free_outside"]))
    print("      a diverged run puts geometry outside the walls it was")
    print("      built from. This is the count of that, and it is not a")
    print("      threshold - it is either zero or it is a finding.")
    print("")

    print("| comparison (DIFFERENT FLOOR, method only) | rms | MAX | "
          "shear |")
    print("|---|---|---|---|")
    print("| this map, warehouse_ver3 (48 x 32 m, TiM571 25 m) | "
          "{:.4f} m | {:.4f} m | {:.4f} deg |".format(
              reg["residual_rms_m"], reg["residual_max_m"], shear))
    print("| {} | {:.4f} m | {:.4f} m | {:.4f} deg |".format(
        VER1["what"], VER1["rms"], VER1["max"], VER1["shear_deg"]))
    print("")
    print("  THE SECOND ROW IS NOT A TARGET AND NOT A BASELINE. It is a")
    print("  different hall, a different scanner and a different route,")
    print("  measured by the same method - which is the only sense in")
    print("  which the two numbers belong on one page.")
    print("")

    record = {
        "map_yaml": repo_path(map_yaml),
        "map_image": repo_path(image),
        "map_md5": md5(image),
        "map_yaml_md5": md5(map_yaml),
        "world_sdf": cfg.s("world.file"),
        "world_md5": md5(world_path),
        "derived_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tool": "m5_ver3/tools/map_register.py derive",
        "theta_rad": reg["theta_rad"],
        "theta_deg": reg["theta_deg"],
        "t_x_m": reg["t_x_m"],
        "t_y_m": reg["t_y_m"],
        "residual_rms_m": reg["residual_rms_m"],
        "residual_max_m": reg["residual_max_m"],
        "shear_deg": shear,
        "n_wall_points": reg["n_wall_points"],
        "trim_cells": trim,
        "min_points": floor,
        "walls": [dict(w, own_rotation_deg=rotations[i],
                       fit_rms_m=fits[w["name"]].rms,
                       dropped=fits[w["name"]].dropped)
                  for i, w in enumerate(reg["walls"])],
        "held_out": {
            "name": held["name"],
            "models": ", ".join(held["models"]),
            "true_face_m": held["offset"],
            "points": len(held_fit.kept),
            "dropped": held_fit.dropped,
            "fit_rms_m": held_fit.rms,
            "own_rotation_deg": math.degrees(core.normalise_angle(
                mc.wall_rotation(held_fit, held["normal"])
                - reg["theta_rad"])),
        },
        "spans": spans,
        "coverage": {
            "hall_m": "{:.3f} x {:.3f}".format(hall.x1 - hall.x0,
                                               hall.y1 - hall.y0),
            "open_floor_m2": open_m2,
            "mapped_free_m2": census["free_hall"] * area,
            "mapped_free_fraction": census["free_hall"] * area / open_m2,
            "cells_occupied": occ,
            "cells_free": free,
            "cells_unknown": census["unknown"],
            "occupied_in_the_wall_fabric": census["occupied_fabric"],
            "occupied_outside_the_building": census["occupied_outside"],
            "free_outside_the_building": census["free_outside"],
        },
    }
    target = args.out or os.path.join(out_dir,
                                      cfg.s("map.registration.file"))
    if not args.write:
        print("nothing was written. --write is the deliberate act of")
        print("committing a registration; it would go to")
        print("  {}".format(os.path.relpath(target, _common.REPO)))
        return 0
    write_registration(target, record)
    print("registration written: {}".format(
        os.path.relpath(target, _common.REPO)))
    return 0


_REG_HEADER = """\
# registration.yaml - DERIVED, NOT ASSERTED.
#
# This is the rigid transform that carries warehouse_ver3's TRUE geometry
# onto this occupancy grid:
#
#     p_map = R(theta) . p_world + t
#
# It was FITTED, by m5_ver3/tools/map_register.py, to the walls of the
# grid named below against the same walls in the world SDF named below.
# Nothing here was typed in, and nothing here is a target.
#
# THE RESIDUAL IS THE FLOOR. `residual_max_m` is the largest distance
# between a kept grid wall point and where this transform says that wall
# is. No rigid transform fits this grid to this building better than
# that, so NO LOCALISATION ERROR AT OR BELOW IT IS A MEASUREMENT OF THE
# LOCALISER. Most of it is `shear_deg`: the amount by which the grid is
# not a rigid copy of the building, which a rigid transform cannot absorb
# by construction and is not asked to.
#
# IT BELONGS TO ONE GRID AND THE BINDING IS ENFORCED. `map_md5` is the
# md5 of the .pgm this was fitted to, and map_register.load_registration()
# REFUSES a transform whose grid has changed underneath it. A rebuilt map
# is a new artifact with its own rotation from the building; nothing
# downstream may carry this transform across a rebuild.
#
# THE SPANS AT THE BOTTOM ARE THE SCORE AND THEY DO NOT USE THIS
# TRANSFORM. A span is a distance between two surfaces inside the map,
# so no choice made while fitting can flatter it.
"""


def write_registration(path, record):
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(_REG_HEADER)
        handle.write("\n")
        for key in ("map_yaml", "map_image", "map_md5", "map_yaml_md5",
                    "world_sdf", "world_md5", "derived_utc", "tool"):
            handle.write("{}: {}\n".format(key, record[key]))
        handle.write("\n")
        for key in ("theta_rad", "theta_deg", "t_x_m", "t_y_m"):
            handle.write("{}: {:.9f}\n".format(key, record[key]))
        handle.write("\n")
        for key in ("residual_rms_m", "residual_max_m", "shear_deg"):
            handle.write("{}: {:.6f}\n".format(key, record[key]))
        handle.write("n_wall_points: {}\n".format(record["n_wall_points"]))
        handle.write("trim_cells: {}\n".format(record["trim_cells"]))
        handle.write("min_points: {}\n".format(record["min_points"]))
        handle.write("\nwalls:\n")
        for wall in record["walls"]:
            handle.write(
                "  - name: {}\n    points: {}\n    dropped: {}\n"
                "    own_rotation_deg: {:.4f}\n    fit_rms_m: {:.4f}\n"
                "    residual_rms_m: {:.4f}\n    residual_max_m: {:.4f}\n"
                .format(wall["name"], wall["points"], wall["dropped"],
                        wall["own_rotation_deg"], wall["fit_rms_m"],
                        wall["residual_rms_m"], wall["residual_max_m"]))
        held = record["held_out"]
        handle.write("\nheld_out:\n")
        handle.write("  # NOT IN THE FIT. The transform above was solved\n"
                     "  # without these points, which is what makes the\n"
                     "  # span they carry an independent check.\n")
        for key in ("name", "models"):
            handle.write("  {}: {}\n".format(key, held[key]))
        for key in ("true_face_m", "fit_rms_m", "own_rotation_deg"):
            handle.write("  {}: {:.4f}\n".format(key, held[key]))
        for key in ("points", "dropped"):
            handle.write("  {}: {}\n".format(key, held[key]))
        handle.write("\ncoverage:\n")
        cov = record["coverage"]
        handle.write("  hall_m: {}\n".format(cov["hall_m"]))
        for key in ("open_floor_m2", "mapped_free_m2"):
            handle.write("  {}: {:.2f}\n".format(key, cov[key]))
        handle.write("  mapped_free_fraction: {:.4f}\n".format(
            cov["mapped_free_fraction"]))
        for key in ("cells_occupied", "cells_free", "cells_unknown",
                    "occupied_in_the_wall_fabric",
                    "occupied_outside_the_building",
                    "free_outside_the_building"):
            handle.write("  {}: {}\n".format(key, cov[key]))
        handle.write("\nspans:\n")
        for span in record["spans"]:
            handle.write(
                "  - name: {}\n    between: {} and {}\n    true_m: {:.4f}\n"
                "    measured_m: {:.4f}\n    error_m: {:+.4f}\n".format(
                    span["name"], span["a"], span["b"], span["true_m"],
                    span["measured_m"], span["error_m"]))


def load_registration(path, verify=True):
    """The committed transform, with its grid checked underneath it.

    THIS IS THE ENFORCEMENT HALF OF THE FORMAT and it is why the md5 is
    in the file. A rebuilt map has its own rotation from the building; a
    consumer that carried this theta across a rebuild would be off by
    the difference and would have no way to find out.
    """
    record = {}
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            if line.startswith("#") or line.startswith(" ") or \
                    ":" not in line:
                continue
            key, value = line.split(":", 1)
            record[key.strip()] = value.strip()
    for key in ("theta_rad", "t_x_m", "t_y_m", "residual_rms_m",
                "residual_max_m"):
        if key not in record:
            raise mc.MapError(
                "{} carries no {}: it is not a registration this tool "
                "wrote".format(path, key))
        record[key] = float(record[key])
    if not verify:
        return record
    image = os.path.join(_common.REPO, record["map_image"])
    if not os.path.isfile(image):
        raise mc.MapError(
            "the grid this registration belongs to is not there: "
            "{}".format(record["map_image"]))
    actual = md5(image)
    if actual != record["map_md5"]:
        raise mc.MapError(
            "REGISTRATION IS STALE. {} has md5 {} and this registration "
            "was fitted to {}. A regenerated map has its own rotation "
            "from the building. Re-derive it:\n"
            "  python3 m5_ver3/tools/map_register.py derive --write"
            .format(record["map_image"], actual, record["map_md5"]))
    return record


def cmd_show(cfg, args):
    out_dir, _ = artifact(cfg, args.name)
    path = args.out or os.path.join(out_dir, cfg.s("map.registration.file"))
    if not os.path.isfile(path):
        cfg.refuse("a registration has been committed", path,
                   "derive one: python3 m5_ver3/tools/map_register.py "
                   "derive --write")
    try:
        record = load_registration(path, verify=not args.no_verify)
    except mc.MapError as exc:
        fail(cfg, exc, path)
    print("=== m5v3 map registration ===")
    print("p_map = R(theta) . p_world + t")
    print("theta = {:+.9f} rad = {:+.6f} deg".format(
        record["theta_rad"], math.degrees(record["theta_rad"])))
    print("t     = ({:+.9f}, {:+.9f}) m".format(record["t_x_m"],
                                                record["t_y_m"]))
    print("residual rms {:.4f} m, MAX {:.4f} m".format(
        record["residual_rms_m"], record["residual_max_m"]))
    print("  <- no localisation figure at or below the MAX is a "
          "measurement of the localiser")
    print("grid  {}".format(record.get("map_image", "?")))
    print("world {}".format(record.get("world_sdf", "?")))
    print("derived {}".format(record.get("derived_utc", "?")))
    if args.no_verify:
        print("NOT VERIFIED against the grid (--no-verify): this may be a "
              "superseded registration.")
    else:
        print("grid md5 verified: this transform belongs to this map.")
    return 0


# ----------------------------------------------------------------------
# clearance
# ----------------------------------------------------------------------

def cmd_clearance(cfg, args):
    """Did the drive that produced this map actually fit the floor?

    IT READS THE GROUND TRUTH AND NOT THE ESTIMATE. Where the truck was
    is not a question an estimator is asked; config.yaml's drive_route:
    block argues corridor by corridor that a profile fits, and this is
    the measurement that argument is a prediction of.
    """
    session = os.path.abspath(args.session)
    truth_path = os.path.join(session, "odom_truth.csv")
    if not os.path.isfile(truth_path):
        cfg.refuse("the session carries a recorded ground truth",
                   truth_path,
                   "it is written by tools/sensor_evidence.py record.")
    world_path = os.path.join(_common.REPO, cfg.s("world.file"))
    world_text = read_text(world_path)
    try:
        boxes = mc.sdf_obstacles(world_text)
    except mc.MapError as exc:
        fail(cfg, exc, world_path)
    try:
        table = core.read_csv(truth_path)
        xs = table.column("x")
        ys = table.column("y")
        yaws = table.column("yaw")
    except core.EvidenceError as exc:
        fail(cfg, exc, truth_path)

    fore = cfg.f("map.clearance.fore_m")
    aft = cfg.f("map.clearance.aft_m")
    half = cfg.f("map.clearance.half_width_m")

    print("=== m5v3 floor clearance ===")
    print("session    {}".format(os.path.relpath(session, _common.REPO)))
    session_file = os.path.join(session, "session.txt")
    if os.path.isfile(session_file):
        for line in read_text(session_file).splitlines():
            if line.split("=", 1)[0] in ("profile", "traction", "arm"):
                print("{:<10} {}".format(*line.split("=", 1)))
    print("world      {}  ({} obstacle rectangles)".format(
        cfg.s("world.file"), len(boxes)))
    print("outline    {:.3f} m ahead of base_link (fork tips, model -x), "
          "{:.3f} m astern,".format(fore, aft))
    print("           {:.3f} m each side. A BOUND and not the model's "
          "silhouette.".format(half))
    print("samples    {} ground-truth poses".format(len(xs)))
    print("path       {:.3f} m".format(core.path_length(xs, ys)))
    print("start      ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(
        xs[0], ys[0], yaws[0]))
    print("end        ({:+.4f}, {:+.4f}) yaw {:+.5f}".format(
        xs[-1], ys[-1], yaws[-1]))
    print("")
    worst = mc.path_clearance(xs, ys, yaws, boxes, fore, aft, half)
    print("WORST CLEARANCE {:.4f} m".format(worst["clearance_m"]))
    print("  against {} at sample {}, base_link ({:+.4f}, {:+.4f})".format(
        worst["obstacle"], worst["index"], worst["x"], worst["y"]))
    if worst["clearance_m"] <= 0.0:
        print("")
        print("  THE OUTLINE OVERLAPS AN OBSTACLE. This drive struck the")
        print("  floor and every scan after that moment is a scan of a")
        print("  plant that had been disturbed.")
        return 1
    print("")
    print("the worst approach to each obstacle it came near "
          "(under {:.2f} m):".format(args.report_under))
    rows = []
    for box in boxes:
        one = mc.path_clearance(xs, ys, yaws, [box], fore, aft, half)
        if one["clearance_m"] < args.report_under:
            rows.append((one["clearance_m"], box.name, one["x"], one["y"]))
    for gap, name, x, y in sorted(rows):
        print("  {:<14} {:6.4f} m   at ({:+8.3f}, {:+8.3f})".format(
            name, gap, x, y))
    if not rows:
        print("  none.")
    return 0


# ----------------------------------------------------------------------

def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(
        description="fit this map to the building, score it absolutely, "
                    "and check the drive that made it against the floor. "
                    "Needs no ROS and no Gazebo.",
        epilog="every constant lives in m5_ver3/config.yaml under map:, "
               "and every arithmetic step lives in tools/map_core.py "
               "where tests/test_map_core.py reaches it.")
    subs = parser.add_subparsers(dest="command")

    derive = subs.add_parser(
        "derive", help="fit the walls, print the floor, then the score")
    derive.add_argument("--map", help="path to the map yaml (default: the "
                                      "artifact named by config.yaml)")
    derive.add_argument("--name", help="artifact name (default: map.name)")
    derive.add_argument("--out", help="where the registration would go")
    derive.add_argument(
        "--hint-deg", type=float, default=None, metavar="DEG",
        help="where the rotation search starts. Default: -vehicle.spawn.yaw, "
             "because the map frame is the odom frame and the odom frame "
             "is the vehicle at spawn. Give it only for a map whose frame "
             "is somewhere else.")
    derive.add_argument(
        "--write", action="store_true",
        help="COMMIT the registration. Without it nothing is written: "
             "deriving is a measurement and committing is a decision.")

    show = subs.add_parser("show", help="print a committed registration")
    show.add_argument("--name", help="artifact name (default: map.name)")
    show.add_argument("--out", help="path to the registration")
    show.add_argument(
        "--no-verify", action="store_true",
        help="do not check the grid's md5. For inspecting a SUPERSEDED "
             "registration only.")

    clear = subs.add_parser(
        "clearance",
        help="sweep a recorded drive's ground truth against the world's "
             "own obstacle rectangles")
    clear.add_argument("session", help="a session directory under "
                                       "evidence.dir")
    clear.add_argument("--report-under", type=float, default=3.0,
                       metavar="M",
                       help="also list every obstacle the drive came "
                            "within this many metres of (default 3.0)")

    args = parser.parse_args(argv)
    if args.command == "derive":
        return cmd_derive(cfg, args)
    if args.command == "show":
        return cmd_show(cfg, args)
    if args.command == "clearance":
        return cmd_clearance(cfg, args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
