#!/usr/bin/env python3
"""offline_scene.py - score C1 and C2 on rendered scenes. NO PLANT.

    python3 m8/bench/offline_scene.py
    python3 m8/bench/offline_scene.py --seeds 10 --out m8/bench/results

READ THIS BEFORE QUOTING A NUMBER FROM IT. This bench does not touch
Gazebo, ROS or the rig. It renders depth from ray/plane intersections
(`m8_core.scene`) and scores `m8_core.pocket` / `m8_core.abort` against
the geometry it rendered from. That makes it a NECESSARY check and
never a sufficient one:

  * The renderer and the estimator share an assumption - a flat floor,
    a flat face, a pinhole camera - so a mistake in that assumption
    cannot show up here. gz renders a GPU depth camera on a mesh.
  * There is no localiser, no TF, no AMCL, no map chain. E1's map
    column has no counterpart here.
  * The noise model is Gaussian at the plant's quoted 0.008 m. Real
    depth noise is range-dependent and structured.

`EVIDENCE_M8_E1.md` and `EVIDENCE_M8_E3.md` on the plant are the score.
This file exists so a C1/C2 change can be measured BEFORE the rig is
booked, and so the defect those two files named has a fixture that
fails offline when it comes back.

Every run writes a new session folder. It never edits an old one.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core import pocket                                    # noqa: E402
from m8_core.abort import classify                            # noqa: E402
from m8_core.scene import make_scene_depth                    # noqa: E402

# EVIDENCE_M8_E1 "Bar", quoted, not produced here.
BAR_M = 0.0706
BAR_NOTE = ("tag rms 0.0706 m / 211 samples at staging (R1), "
            "measured on the plant, not by this script")

# EVIDENCE_M8_E1 "Result": the three poses it scored.
RANGES = (("staging", 2.245), ("approach_1.5", 1.5), ("approach_1.0", 1.0))
YAWS = (-0.10, -0.05, 0.0, 0.05, 0.10)

C1_FIELDS = ("case", "range_m", "yaw_rad", "seed", "observed",
             "tru_lat_m", "tru_range_m", "est_lat_m", "est_range_m",
             "e_lat_m", "e_range_m", "e_2d_m", "est_yaw_rad", "e_yaw_rad",
             "a1_proxy_yaw_rad", "roi_u0", "roi_u1", "roi_v0", "roi_v1",
             "face_width_m", "face_height_m", "pocket_span_m",
             "inliers", "floor_found", "t_observe_s")

C2_FIELDS = ("case", "expected", "reason", "exact", "range_m", "seed",
             "t_classify_s")

# name -> (expected reason or None, scene kwargs)
C2_CASES = (
    ("clean", None, {}),
    ("empty_bay", "pallet_absent", {"pallet": False}),
    ("rotated_pos", "pallet_rotated", {"yaw": 0.25}),
    ("rotated_neg", "pallet_rotated", {"yaw": -0.25}),
    ("pockets_filled", "pocket_blocked", {"pockets": False}),
    ("stringer", "stringer_in_path", {"obstacle": True}),
    ("shifted", "pallet_shifted", {"lateral": 0.75}),
)


def _summarise(values):
    vals = [v for v in values if v is not None and math.isfinite(v)]
    if not vals:
        return {"n": 0}
    n = float(len(vals))
    mean = sum(vals) / n
    return {"n": len(vals), "mean": mean,
            "rms": math.sqrt(sum(v * v for v in vals) / n),
            "min": min(vals), "max": max(vals),
            "max_abs": max(abs(v) for v in vals)}


def _scene(distance, seed, **kw):
    obstacle = kw.pop("obstacle", False)
    if obstacle:
        kw["obstacles"] = ((-0.55, -0.25, 0.0, 0.13, distance - 0.08),)
    return make_scene_depth(face_distance=distance, seed=seed, **kw)


def run_c1(seeds):
    rows = []
    for label, distance in RANGES:
        for yaw in YAWS:
            for seed in range(seeds):
                frame, scene = _scene(distance, seed, yaw=yaw)
                truth = scene.pocket_centre()
                t0 = time.perf_counter()
                obs = pocket.observe(frame)
                t1 = time.perf_counter()
                row = {"case": label, "range_m": distance, "yaw_rad": yaw,
                       "seed": seed, "observed": 1 if obs else 0,
                       "tru_lat_m": truth[0], "tru_range_m": truth[2],
                       "t_observe_s": t1 - t0}
                if obs is not None:
                    lat = (obs.pocket_u - frame.cx) / frame.fx * obs.face_z
                    row.update(
                        est_lat_m=lat, est_range_m=obs.face_z,
                        e_lat_m=lat - truth[0],
                        e_range_m=obs.face_z - truth[2],
                        e_2d_m=math.hypot(lat - truth[0],
                                          obs.face_z - truth[2]),
                        est_yaw_rad=obs.face_yaw,
                        e_yaw_rad=obs.face_yaw - yaw,
                        a1_proxy_yaw_rad=math.atan(obs.face_a),
                        roi_u0=obs.roi_u0, roi_u1=obs.roi_u1,
                        roi_v0=obs.roi_v0, roi_v1=obs.roi_v1,
                        face_width_m=obs.face_width_m,
                        face_height_m=obs.face_height_m,
                        pocket_span_m=obs.pocket_span_m,
                        inliers=obs.inliers,
                        floor_found=1 if obs.floor_found else 0)
                rows.append(row)
    return rows


def run_c2(seeds):
    rows = []
    for name, expected, kw in C2_CASES:
        for _label, distance in RANGES:
            for seed in range(seeds):
                frame, _scene_obj = _scene(distance, seed, **dict(kw))
                t0 = time.perf_counter()
                reason = classify(frame)
                t1 = time.perf_counter()
                rows.append({
                    "case": name, "expected": expected or "none",
                    "reason": reason or "none",
                    "exact": 1 if reason == expected else 0,
                    "range_m": distance, "seed": seed,
                    "t_classify_s": t1 - t0})
    return rows


def summarise(c1_rows, c2_rows):
    per_pose = {}
    for label, distance in RANGES:
        sub = [r for r in c1_rows if r["case"] == label]
        square = [r for r in sub if r["yaw_rad"] == 0.0]
        seen = [r for r in sub if r["observed"]]
        per_pose[label] = {
            "range_m": distance,
            "n_frames": len(sub), "n_observed": len(seen),
            "n_square": len(square),
            "n_square_observed": sum(r["observed"] for r in square),
            "e_2d_m": _summarise([r.get("e_2d_m") for r in seen]),
            "e_yaw_rad": _summarise([r.get("e_yaw_rad") for r in seen]),
            "a1_proxy_yaw_err": _summarise(
                [r["a1_proxy_yaw_rad"] - r["yaw_rad"]
                 for r in seen if r.get("a1_proxy_yaw_rad") is not None]),
            "pocket_span_m": _summarise(
                [r.get("pocket_span_m") for r in seen]),
            "face_width_m": _summarise([r.get("face_width_m") for r in seen]),
            "t_observe_s": _summarise([r["t_observe_s"] for r in sub]),
        }
    observed = [r for r in c1_rows if r["observed"]]
    over_bar = [r for r in observed if r["e_2d_m"] >= BAR_M]
    per_case = {}
    for name, expected, _kw in C2_CASES:
        sub = [r for r in c2_rows if r["case"] == name]
        words = {}
        for r in sub:
            words[r["reason"]] = words.get(r["reason"], 0) + 1
        per_case[name] = {"expected": expected or "none", "n": len(sub),
                          "exact": sum(r["exact"] for r in sub),
                          "words": words}
    clean = [r for r in c2_rows if r["case"] == "clean"]
    return {
        "bar_m": BAR_M, "bar": BAR_NOTE,
        "c1": {"per_pose": per_pose,
               "n_frames": len(c1_rows), "n_observed": len(observed),
               "n_over_bar": len(over_bar),
               "e_2d_m": _summarise([r["e_2d_m"] for r in observed]),
               "e_yaw_rad": _summarise([r["e_yaw_rad"] for r in observed])},
        "c2": {"per_case": per_case, "n_frames": len(c2_rows),
               "exact": sum(r["exact"] for r in c2_rows),
               "false_abort": sum(1 for r in clean if r["reason"] != "none"),
               "n_clean": len(clean),
               "t_classify_s": _summarise(
                   [r["t_classify_s"] for r in c2_rows])},
    }


def _fmt(stat, key="rms", nd=4):
    if not stat or stat.get("n", 0) == 0:
        return "-"
    return "{:.{nd}f}".format(stat[key], nd=nd)


def render_text(summary):
    out = []
    out.append("OFFLINE SCENE BENCH - rendered depth, no plant, no ROS.")
    out.append("Not a plant result. E1/E3 on the m5-ver3 rig are the score.")
    out.append("bar (quoted): " + summary["bar"])
    out.append("")
    out.append("C1 pocket pose")
    out.append("  {:<14} {:>8} {:>10} {:>10} {:>10} {:>9}".format(
        "pose", "obs/n", "rms 2d", "max 2d", "rms yaw", "observe"))
    for label, pose in summary["c1"]["per_pose"].items():
        out.append("  {:<14} {:>8} {:>10} {:>10} {:>10} {:>8} s".format(
            label, "{}/{}".format(pose["n_observed"], pose["n_frames"]),
            _fmt(pose["e_2d_m"]), _fmt(pose["e_2d_m"], "max_abs"),
            _fmt(pose["e_yaw_rad"]),
            _fmt(pose["t_observe_s"], "median" if "median" in
                 pose["t_observe_s"] else "mean", 3)))
    c1 = summary["c1"]
    out.append("  overall {}/{} observed, rms 2d {} m, {} of {} at or over "
               "the bar".format(c1["n_observed"], c1["n_frames"],
                                _fmt(c1["e_2d_m"]), c1["n_over_bar"],
                                c1["n_observed"]))
    proxy = summary["c1"]["per_pose"]["staging"]["a1_proxy_yaw_err"]
    out.append("  A1's atan(dz/dx) yaw proxy, same frames: rms error "
               "{} rad".format(_fmt(proxy)))
    out.append("")
    out.append("C2 abort classifier")
    for name, case in summary["c2"]["per_case"].items():
        out.append("  {:<16} expected {:<16} exact {}/{}  words {}".format(
            name, case["expected"], case["exact"], case["n"],
            json.dumps(case["words"], sort_keys=True)))
    c2 = summary["c2"]
    out.append("  false aborts on clean frames: {} of {}".format(
        c2["false_abort"], c2["n_clean"]))
    out.append("  classify median {} s".format(
        _fmt(c2["t_classify_s"], "mean", 3)))
    return "\n".join(out) + "\n"


def _write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields,
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in fields})


def _md5(path):
    with open(path, "rb") as handle:
        return hashlib.md5(handle.read()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="offline_scene.py")
    parser.add_argument("--seeds", type=int, default=10,
                        help="noise realisations per case")
    parser.add_argument("--out", default=os.path.join(_HERE, "results"))
    args = parser.parse_args(argv)

    started = time.time()
    c1_rows = run_c1(args.seeds)
    c2_rows = run_c2(args.seeds)
    summary = summarise(c1_rows, c2_rows)
    summary["seeds"] = args.seeds
    summary["wall_s"] = time.time() - started
    summary["algorithm"] = "m8_core.pocket (classical_floor_anchored_face)"
    summary["renderer"] = "m8_core.scene.make_scene_depth"
    summary["not_a_plant_result"] = True

    session = time.strftime("scene-%Y%m%d-%H%M%S")
    folder = os.path.join(args.out, session)
    os.makedirs(folder)
    _write_csv(os.path.join(folder, "c1_frames.csv"), C1_FIELDS, c1_rows)
    _write_csv(os.path.join(folder, "c2_frames.csv"), C2_FIELDS, c2_rows)
    text = render_text(summary)
    with open(os.path.join(folder, "summary.json"), "w",
              encoding="utf-8", newline="\n") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(folder, "summary.txt"), "w",
              encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    print(text)
    print("session " + folder)
    for name in sorted(os.listdir(folder)):
        print("  {}  {}".format(_md5(os.path.join(folder, name)), name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
