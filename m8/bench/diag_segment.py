#!/usr/bin/env python3
"""diag_segment.py - why did C1 refuse THIS frame, on the plant.

    python3 m8/bench/diag_segment.py
    python3 m8/bench/diag_segment.py --ranges staging,1.5,1.0 --frames 3

E1 reports `observed 0/30` and stops there. That is the right thing for
a scoring bench to do and the wrong thing to debug from: "no pose" and
"no pose BECAUSE the face was 4 % of what was fitted" are different
findings. This walks `m8_core.pocket.segment`'s own gate trail at the
same poses E1 uses and prints the gate that stopped each frame.

It SCORES NOTHING and writes no session. It stages the truck the way E1
does, so it needs the plant, and it prints NOT_RUN and exits 2 without
it. Ground truth is printed for reading only - the estimator is never
told it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

DEFAULT_RANGES = "staging,1.5,1.0"
DEFAULT_FRAMES = 3
SETTLE_S = 3.0
SEED_HOLD_S = 2.0
CAPTURE_TIMEOUT_S = 30.0

ORDER = ("valid_px", "window_m", "floor_dz_dy", "floor_depth_on_axis_m",
         "floor_points", "blob", "tag_seeded", "in_window", "after_deck_cut",
         "height_cut", "seed_range_m", "seed_points", "face_inliers",
         "inlier_frac", "face_box", "face_z_m", "face_dz_dy", "face_width_m",
         "face_height_m", "deeper_cols", "pocket_runs", "pocket_span_m",
         "refused")


def _not_run(why=""):
    print("NOT_RUN: diag_segment needs the m5-ver3 plant")
    if why:
        print("  why: " + why)
    print("  this process scored nothing and wrote nothing")
    return 2


def _show(trace):
    for key in ORDER:
        if key not in trace:
            continue
        value = trace[key]
        if isinstance(value, float):
            value = round(value, 4)
        elif isinstance(value, (list, tuple)):
            value = json.dumps([round(v, 4) if isinstance(v, float) else v
                                for v in value])
        print("      {:<24} {}".format(key, value))


def run(args):
    from bench import plant as P
    from bench.faults import inject
    from m8_core import pocket

    plant = P.Plant("diag_segment")
    print("labels    {}".format(plant.labels()))
    print("world     {}".format(inject.restore(plant)))

    ranges = []
    for tok in args.ranges.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok == "staging":
            ranges.append(("staging", plant.staging_base()))
        else:
            r = float(tok)
            ranges.append(("approach_{:.2f}m".format(r),
                           plant.base_for_camera_range(r)))

    cap = P.Capture(plant, "m8_diag_capture")
    if not cap.wait_ready(20.0):
        cap.close()
        return _not_run("no CameraInfo / ground truth within 20 s")
    try:
        for label, base in ranges:
            plant.teleport_truck(base)
            cap.seed_amcl(base, SEED_HOLD_S)
            cap.spin_wall(SETTLE_S)
            truck6 = plant.gz_model_pose(plant.truck)
            pallet6 = plant.gz_model_pose(plant.pallet_name)
            frames = cap.capture(args.frames, CAPTURE_TIMEOUT_S)
            if not frames:
                print("--- {}: no frames".format(label))
                continue
            info = frames[0].get("info") or cap.info
            truth = P.static_truth(plant, truck6, pallet6, info)
            tru_lat, tru_h, tru_range = truth["pocket_opt"]
            print("--- {} camera {:.3f} m | truth lat {:+.4f} range {:.4f} "
                  "| face bbox {} | face {:.1f} % of A1's band".format(
                      label, truth.get("cam_to_face_m", float("nan")),
                      tru_lat, tru_range, truth.get("face_bbox_px"),
                      100.0 * truth["face_frac_of_plane_roi"]))
            del tru_h
            for k, frame in enumerate(frames):
                if frame.get("info") is None:
                    frame["info"] = info
                depths = P.decode(frame)
                df = P.depth_frame(frame, depths)
                trace = {}
                obs = pocket.observe(df, trace=trace)
                print("    frame {}: {}".format(
                    k, "OBSERVED lat {:+.4f} range {:.4f} yaw {:+.4f}".format(
                        (obs.pocket_u - df.cx) / df.fx * obs.face_z,
                        obs.face_z, obs.face_yaw)
                    if obs is not None else "refused"))
                _show(trace)
    finally:
        cap.close()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="diag_segment.py")
    parser.add_argument("--ranges", default=DEFAULT_RANGES)
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    args = parser.parse_args(argv)
    try:
        from bench import plant as P
    except Exception as exc:                      # noqa: BLE001
        return _not_run("bench.plant did not import: {}".format(exc))
    try:
        P.Plant("diag_segment")
    except SystemExit:
        raise
    except Exception as exc:                      # noqa: BLE001
        return _not_run(str(exc))
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
