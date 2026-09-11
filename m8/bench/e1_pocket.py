#!/usr/bin/env python3
"""e1_pocket.py - score C1 (classical pocket pose) against gz pallet truth.

    python3 m8/bench/e1_pocket.py                  # live plant, default sweep
    python3 m8/bench/e1_pocket.py --frames 30 --ranges staging,1.5,1.0

NOT_RUN without the m5-ver3 plant: this file prints so, exits 2 and
invents no rms (m8/tests/test_benches_not_run.py holds that).

WHAT IT SCORES. The truck is teleported, heading-aligned on the S5 spur,
to the tag bar's own staging xy (camera 2.245 m from the pallet face)
and to two approach ranges inside C1's last-two-metres regime. At each
pose N depth frames are taken; `m8_core.pocket.observe` (the SAME code
the shadow node runs, on the SAME 640x480 frames) is run per frame and
its outputs are read as the pocket-pair point the node would propose:

    range   = face_z                       (plane intercept on the axis)
    lateral = (pocket_u - cx) / fx * face_z
    yaw     = atan(face_a)                 (dtheta in propose())

Each is scored against the pallet's pocket-pair centre carried into the
optical frame through vehicle.cam_mount / cam_optical from the gz pose
of the truck and the pallet (bench/geom.py, bench/plant.static_truth).
That is a CAMERA-FRAME perception error with no localiser in it.

A second column carries the SAME point through the live TF tree
(map -> pallet_cam_optical at the frame stamp) against the pocket
centre through the committed registration - the tag bar's instrument
(tag_bench.py), with AMCL seeded at the pose as it was for the bar.

Standing cautions: ground truth is a score, not a command; the
instrument floor (registration rms 0.0291 m, MAX 0.1179 m) bounds the
map column; no PL / SIL / PFH claims; frames never leave the rig.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

BAR = "tag rms 0.0706 m / 211 samples at staging (R1). Not a number this script produced."

DEFAULT_RANGES = "staging,1.5,1.0"
DEFAULT_FRAMES = 30
SETTLE_S = 3.0
SEED_HOLD_S = 2.0
CAPTURE_TIMEOUT_S = 30.0

CSV_FIELDS = (
    "pose", "k", "stamp", "observed",
    "tru_lat_m", "tru_range_m", "tru_height_m", "tru_yaw_rad",
    "est_lat_m", "est_range_m", "est_yaw_rad",
    "e_lat_m", "e_range_m", "e_2d_m", "e_yaw_rad",
    "tf", "map_est_x", "map_est_y", "map_tru_x", "map_tru_y", "e_map_xy_m",
    "pocket_u", "pocket_v", "face_a", "face_b", "inliers", "valid",
    "face_u0", "face_u1", "face_v0", "face_v1", "face_frac_plane_roi",
    "face_frac_band_roi", "depth_at_pocket_px_m", "chain_check_m",
    "plane_a", "plane_b", "plane_c_m", "plane_n", "plane_c_err_m",
    "t_decode_s", "t_observe_s",
)


def _not_run(why=""):
    print("NOT_RUN: E1 needs the m5-ver3 plant")
    print("  required: gz-sim 8.11, forklift_ver3, warehouse_ver3,")
    print("            pallet_cam D455 depth, GPU preflight, mix refusals")
    if why:
        print("  why: " + why)
    print("  bar (quoted, not scored here):", BAR)
    print("  this process did not synthesize a pocket pose or an rms")
    return 2


def _fmt(v, nd=4):
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return "{:.{}f}".format(v, nd)
    return str(v)


def _map_point(map_optical, p_opt):
    from bench import geom
    r = geom.rot_quat(*map_optical["q"])
    return geom.add(geom.mat_vec(r, p_opt), map_optical["t"])


def score_frame(plant, frame, truth, pose_label, k):
    """One row of frames.csv. Runs the shadow node's C1 on the frame."""
    from bench import geom, plant as P
    from m8_core.pocket import fit_face_plane, observe

    t0 = time.perf_counter()
    depths = P.decode(frame)
    df = P.depth_frame(frame, depths)
    t1 = time.perf_counter()
    obs = observe(df)
    t2 = time.perf_counter()
    # Diagnostic, outside the timed call: the plane C1 fitted whether or
    # not a pocket pair followed. Names what the "face" was.
    plane = fit_face_plane(df)

    info = frame["info"]
    fx, fy, cx, cy = info["fx"], info["fy"], info["cx"], info["cy"]
    tru_lat, tru_h, tru_range = truth["pocket_opt"]
    row = {
        "pose": pose_label, "k": k, "stamp": frame["stamp"],
        "observed": 1 if obs is not None else 0,
        "tru_lat_m": tru_lat, "tru_range_m": tru_range, "tru_height_m": tru_h,
        "tru_yaw_rad": truth["face_yaw_opt"],
        "tf": 1 if frame.get("map_optical") else 0,
        "t_decode_s": t1 - t0, "t_observe_s": t2 - t1,
        "face_frac_plane_roi": truth["face_frac_of_plane_roi"],
        "face_frac_band_roi": truth["face_frac_of_band_roi"],
    }
    bb = truth.get("face_bbox_px")
    if bb:
        row.update(face_u0=bb[0], face_u1=bb[1], face_v0=bb[2], face_v1=bb[3])
    ppx = truth.get("pocket_px")
    if ppx:
        z_px = P.depth_at(depths, frame["width"], frame["height"], ppx[0], ppx[1], 1)
        row["depth_at_pocket_px_m"] = z_px
        if z_px is not None:
            row["chain_check_m"] = z_px - tru_range
    mtx, mty = plant.map_frame.to_map(truth["pocket_world"][0], truth["pocket_world"][1])
    row["map_tru_x"], row["map_tru_y"] = mtx, mty
    if plane is not None:
        row.update(plane_a=plane[0], plane_b=plane[1], plane_c_m=plane[2],
                   plane_n=plane[3], plane_c_err_m=plane[2] - tru_range)

    if obs is not None:
        est_range = obs.face_z
        est_lat = (obs.pocket_u - cx) / fx * obs.face_z
        est_yaw = math.atan(obs.face_a)
        row.update(
            est_lat_m=est_lat, est_range_m=est_range, est_yaw_rad=est_yaw,
            e_lat_m=est_lat - tru_lat, e_range_m=est_range - tru_range,
            e_2d_m=math.hypot(est_lat - tru_lat, est_range - tru_range),
            e_yaw_rad=geom.wrap(est_yaw - truth["face_yaw_opt"]),
            pocket_u=obs.pocket_u, pocket_v=obs.pocket_v,
            face_a=obs.face_a, face_b=obs.face_b,
            inliers=obs.inliers, valid=obs.valid)
        if frame.get("map_optical"):
            est_h = (obs.pocket_v - cy) / fy * obs.face_z
            mp = _map_point(frame["map_optical"], (est_lat, est_h, est_range))
            row["map_est_x"], row["map_est_y"] = mp[0], mp[1]
            row["e_map_xy_m"] = math.hypot(mp[0] - mtx, mp[1] - mty)
    return row


def summarise_pose(rows):
    from bench import geom
    obs = [r for r in rows if r["observed"]]
    out = {
        "n_frames": len(rows), "n_observed": len(obs),
        "observed_frac": (len(obs) / len(rows)) if rows else float("nan"),
        "tf_frames": sum(1 for r in rows if r["tf"]),
        "face_frac_plane_roi": geom.mean([r["face_frac_plane_roi"] for r in rows]),
        "face_frac_band_roi": geom.mean([r["face_frac_band_roi"] for r in rows]),
        "chain_check": geom.summarise([r["chain_check_m"] for r in rows
                                       if r.get("chain_check_m") is not None]),
        "t_observe_s": geom.summarise([r["t_observe_s"] for r in rows]),
        "t_decode_s": geom.summarise([r["t_decode_s"] for r in rows]),
        "plane_fitted": sum(1 for r in rows if r.get("plane_c_m") is not None),
        "plane_c_m": geom.summarise([r["plane_c_m"] for r in rows
                                     if r.get("plane_c_m") is not None]),
        "plane_c_err_m": geom.summarise([r["plane_c_err_m"] for r in rows
                                         if r.get("plane_c_err_m") is not None]),
        "plane_a": geom.summarise([r["plane_a"] for r in rows if r.get("plane_a") is not None]),
        "plane_b": geom.summarise([r["plane_b"] for r in rows if r.get("plane_b") is not None]),
        "plane_n": geom.summarise([r["plane_n"] for r in rows if r.get("plane_n") is not None]),
        "tru_lat_m": rows[0]["tru_lat_m"] if rows else None,
        "tru_range_m": rows[0]["tru_range_m"] if rows else None,
        "tru_yaw_rad": rows[0]["tru_yaw_rad"] if rows else None,
    }
    for key in ("e_lat_m", "e_range_m", "e_2d_m", "e_yaw_rad", "e_map_xy_m",
                "est_lat_m", "est_range_m", "est_yaw_rad"):
        out[key] = geom.summarise([r[key] for r in obs if r.get(key) is not None])
    return out


def write_summary_txt(path, session, poses_out, plant, args):
    lines = []
    lines.append("E1 pocket pose vs gz truth - session {}".format(session))
    lines.append("bar (quoted): {}".format(BAR))
    lines.append("labels: {}".format(plant.labels()))
    lines.append("frames per pose: {}  ranges: {}".format(args.frames, args.ranges))
    lines.append("")
    lines.append("{:<16} {:>4} {:>4} {:>7} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
        "pose", "n", "obs", "cam_m", "face%roi", "rms_lat", "rms_rng", "rms_2d",
        "rms_yaw", "rms_map"))
    for label, s in poses_out:
        lines.append("{:<16} {:>4} {:>4} {:>7} {:>8} {:>8} {:>8} {:>8} {:>8} {:>8}".format(
            label, s["n_frames"], s["n_observed"], _fmt(s["cam_range_m"], 3),
            _fmt(100.0 * s["face_frac_plane_roi"], 1),
            _fmt(s["e_lat_m"]["rms"]), _fmt(s["e_range_m"]["rms"]),
            _fmt(s["e_2d_m"]["rms"]), _fmt(s["e_yaw_rad"]["rms"]),
            _fmt(s["e_map_xy_m"]["rms"])))
    lines.append("")
    for label, s in poses_out:
        cc = s["chain_check"]
        lines.append("[{}] truth lateral {} range {} yaw {} | chain check (depth at pocket px - "
                     "truth range) mean {} max|.| {} n {} | observe median {} s".format(
                         label, _fmt(s["tru_lat_m"]), _fmt(s["tru_range_m"]),
                         _fmt(s["tru_yaw_rad"]), _fmt(cc["mean"]),
                         _fmt(max(abs(cc["min"]), abs(cc["max"])) if cc["n"] else None),
                         cc["n"], _fmt(s["t_observe_s"]["median"], 3)))
        lines.append("      plane C1 fitted on {}/{} frames: c (range on axis) mean {} m vs truth {} "
                     "(err mean {}), slope a mean {} b mean {}, points n median {}".format(
                         s["plane_fitted"], s["n_frames"], _fmt(s["plane_c_m"]["mean"]),
                         _fmt(s["tru_range_m"]), _fmt(s["plane_c_err_m"]["mean"]),
                         _fmt(s["plane_a"]["mean"]), _fmt(s["plane_b"]["mean"]),
                         _fmt(s["plane_n"]["median"], 0) if "plane_n" in s else ""))
        if s["n_observed"]:
            lines.append("      est lateral mean {} range mean {} yaw mean {} | errors: lat mean {} "
                         "range mean {} 2d max {} yaw max|.| {}".format(
                             _fmt(s["est_lat_m"]["mean"]), _fmt(s["est_range_m"]["mean"]),
                             _fmt(s["est_yaw_rad"]["mean"]), _fmt(s["e_lat_m"]["mean"]),
                             _fmt(s["e_range_m"]["mean"]), _fmt(s["e_2d_m"]["max"]),
                             _fmt(max(abs(s["e_yaw_rad"]["min"]), abs(s["e_yaw_rad"]["max"])))))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return lines


def run(args) -> int:
    from bench import plant as P
    from bench.faults import inject

    plant = P.Plant("e1_pocket")
    session, dest = plant.session_dir("e1")
    print("session   {}".format(session))
    print("labels    {}".format(plant.labels()))

    restored = inject.restore(plant)
    print("world     {}".format(restored))

    ranges = []
    for tok in args.ranges.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok == "staging":
            ranges.append(("staging", plant.staging_base()))
        else:
            r = float(tok)
            ranges.append(("approach_{:.2f}m".format(r), plant.base_for_camera_range(r)))

    cap = P.Capture(plant, "m8_e1_capture")
    if not cap.wait_ready(20.0):
        cap.close()
        plant.cfg.refuse("CameraInfo and ground truth arrive", cap.info_topic,
                         "nothing within 20 s on {} / {}".format(cap.info_topic, cap.truth_topic))

    all_rows = []
    poses_out = []
    manifest_poses = []
    try:
        for label, base in ranges:
            print("--- {} base ({:.3f}, {:.3f}) yaw {:+.4f}".format(label, *base))
            plant.teleport_truck(base)
            seed = cap.seed_amcl(base, SEED_HOLD_S)
            cap.spin_wall(SETTLE_S)
            truck6 = plant.gz_model_pose(plant.truck)
            pallet6 = plant.gz_model_pose(plant.pallet_name)
            if truck6 is None or pallet6 is None:
                plant.cfg.refuse("gz reports the truck and the pallet",
                                 "gz model -p", "truck {} pallet {}".format(truck6, pallet6))
            frames = cap.capture(args.frames, CAPTURE_TIMEOUT_S)
            if not frames:
                plant.cfg.refuse("depth frames arrive on {}".format(cap.depth_topic),
                                 cap.depth_topic, "none within {:g} s".format(CAPTURE_TIMEOUT_S))
            info = frames[0]["info"] or cap.info
            truth = P.static_truth(plant, truck6, pallet6, info)
            rows = []
            for k, frame in enumerate(frames):
                if frame.get("info") is None:
                    frame["info"] = info
                rows.append(score_frame(plant, frame, truth, label, k))
            s = summarise_pose(rows)
            s["cam_range_m"] = plant.camera_range_of((truck6[0], truck6[1]))
            s["base"] = base
            s["seed_map"] = seed
            s["truck6"] = truck6
            s["pallet6"] = pallet6
            s["truth"] = {k: v for k, v in truth.items()
                          if k not in ("truck6", "pallet6")}
            s["odom_truth_first"] = frames[0]["truth"]
            poses_out.append((label, s))
            manifest_poses.append({"label": label, "base": base, "truck6": truck6,
                                   "pallet6": pallet6, "seed_map": seed})
            all_rows.extend(rows)
            print("    frames {} observed {} rms_2d {} rms_map {} face%roi {} observe {} s".format(
                s["n_frames"], s["n_observed"], _fmt(s["e_2d_m"]["rms"]),
                _fmt(s["e_map_xy_m"]["rms"]), _fmt(100 * s["face_frac_plane_roi"], 1),
                _fmt(s["t_observe_s"]["median"], 3)))
    finally:
        cap.close()

    csv_path = os.path.join(dest, "frames.csv")
    with open(csv_path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: _fmt(row.get(k), 6) if isinstance(row.get(k), float)
                             else ("" if row.get(k) is None else row.get(k))
                             for k in CSV_FIELDS})
    P.write_json(os.path.join(dest, "summary.json"), {
        "bench": "e1_pocket", "session": session, "bar_quoted": BAR,
        "frames_per_pose": args.frames, "ranges": args.ranges,
        "settle_s": SETTLE_S, "seed_hold_s": SEED_HOLD_S,
        "poses": {label: s for label, s in poses_out},
    })
    P.write_json(os.path.join(dest, "session.json"), {
        "bench": "e1_pocket", "session": session,
        "environment": plant.environment(), "poses": manifest_poses,
        "pallet_design": plant.pallet_design, "pallet_dims": plant.pallet_dims,
        "cam_mount": plant.cam_mount, "world_restore": restored,
        "algorithm": "m8_core.pocket.observe (classical_plane_pockets), unmodified",
        "scored_as": {"range": "face_z", "lateral": "(pocket_u - cx)/fx * face_z",
                      "yaw": "atan(face_a)", "truth": "pocket-pair centre in optical frame "
                      "from gz truck + pallet pose through cam_mount/cam_optical"},
    })
    lines = write_summary_txt(os.path.join(dest, "summary.txt"), session, poses_out, plant, args)
    print("")
    print("\n".join(lines))
    print("")
    print("wrote     {}".format(os.path.relpath(dest, os.getcwd())))
    return 0


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    from bench import plant as P
    ok, why = P.plant_reachable()
    if not ok:
        return _not_run(why)
    parser = argparse.ArgumentParser(prog="e1_pocket.py")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    parser.add_argument("--ranges", default=DEFAULT_RANGES,
                        help="comma list: staging and/or camera->face metres")
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
