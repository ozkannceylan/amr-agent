#!/usr/bin/env python3
"""e3_abort.py - recall / false-abort of C2 on the staged fault set.

    python3 m8/bench/e3_abort.py                       # live plant
    python3 m8/bench/e3_abort.py --frames 30 --ranges staging,1.5,1.0 --cycles 2

NOT_RUN without the m5-ver3 plant: prints so, exits 2, invents no rate
(m8/tests/test_benches_not_run.py holds that).

WHAT IT SCORES. `m8_core.abort.classify` - the SAME code the shadow
abort node runs, unmodified - on live 640x480 depth frames, under
world states staged by bench/faults/inject.py:

  STATIC   at each heading-aligned pose (staging = the tag bar's xy,
           plus approach ranges): clean and the five named faults, N
           frames each. Recall = frames with ANY abort / frames on a
           fault; reason-exact = frames whose reason names THAT fault.
           False-abort (static) = frames with an abort / clean frames.
  CYCLES   clean live dock approaches (dock_bench.py stage, then
           record --from-staging) with the classifier streaming on the
           camera the whole way in. False-abort (cycle) = classified
           frames with an abort / classified frames, per cycle, with
           the plugin's own outcome beside it.

The label is the WORLD STATE (gz readback), never the classifier's
word. `proceed` is not an output and is not counted. Nothing here
commands the vehicle: dock_bench.py is the m5-ver3 instrument that does,
and it is run as it is.

Standing cautions: ground truth is a score, not a command; no PL / SIL
/ PFH claims; the collision monitor is not a safety function; frames
never leave the rig; the F-PLC never receives M8 input.
"""
from __future__ import annotations

import argparse
import csv
import math
import os
import re
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
_REPO = os.path.normpath(os.path.join(_M8, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

DEFAULT_RANGES = "staging,1.5,1.0"
DEFAULT_FRAMES = 30
DEFAULT_CYCLES = 2
SETTLE_S = 2.0
SEED_HOLD_S = 2.0
CAPTURE_TIMEOUT_S = 30.0
CYCLE_TIMEOUT_S = 420.0
REASONS = ("pallet_absent", "pallet_rotated", "pallet_shifted",
           "pocket_blocked", "stringer_in_path")

STATIC_FIELDS = (
    "pose", "condition", "k", "stamp", "reason", "abort", "exact",
    "cam_range_m", "tru_lat_m", "tru_range_m", "face_u0", "face_u1",
    "face_v0", "face_v1", "face_frac_plane_roi", "valid_frac",
    "t_decode_s", "t_classify_s",
)
CYCLE_FIELDS = (
    "cycle", "k", "stamp", "wall", "reason", "abort", "truth_x", "truth_y",
    "truth_yaw", "cam_range_m", "valid_frac", "t_classify_s",
)


def _not_run(why=""):
    print("NOT_RUN: E3 needs the m5-ver3 plant and bench/faults/ staging")
    print("  required: gz-sim, forklift_ver3, pallet_cam, world-state labels")
    if why:
        print("  why: " + why)
    print("  this process did not compute recall or a false-abort rate")
    print("  proceed is never an M8 output (enforced in m8_core, not here)")
    return 2


def _fmt(v, nd=4):
    if v is None:
        return ""
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        return "{:.{}f}".format(v, nd)
    return str(v)


def classify_frame(frame):
    """(reason or None, valid_frac, t_decode, t_classify) via m8_core.abort."""
    from bench import plant as P
    from m8_core.abort import classify
    t0 = time.perf_counter()
    depths = P.decode(frame)
    df = P.depth_frame(frame, depths)
    t1 = time.perf_counter()
    reason = classify(df)
    t2 = time.perf_counter()
    valid = sum(1 for z in depths if math.isfinite(z) and z > 0.0)
    return reason, valid / float(len(depths)), t1 - t0, t2 - t1


def run_static(plant, cap, args, inject, P):
    rows = []
    manifest = []
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
    for label, base in ranges:
        print("--- {} base ({:.3f}, {:.3f}) yaw {:+.4f}".format(label, *base))
        plant.teleport_truck(base)
        seed = cap.seed_amcl(base, SEED_HOLD_S)
        cap.spin_wall(1.0)
        truck6 = plant.gz_model_pose(plant.truck)
        for condition in inject.CONDITIONS:
            inject.restore(plant)
            staged = inject.inject(plant, condition)
            cap.spin_wall(SETTLE_S)
            world = inject.readback(plant)
            pallet6 = world["pallet"]
            frames = cap.capture(args.frames, CAPTURE_TIMEOUT_S)
            if not frames:
                plant.cfg.refuse("depth frames arrive on {}".format(cap.depth_topic),
                                 cap.depth_topic, "none within {:g} s".format(CAPTURE_TIMEOUT_S))
            info = frames[0]["info"] or cap.info
            truth = P.static_truth(plant, truck6, pallet6, info) if pallet6 else None
            cam_range = plant.camera_range_of((truck6[0], truck6[1]))
            hits = 0
            exact = 0
            for k, frame in enumerate(frames):
                if frame.get("info") is None:
                    frame["info"] = info
                reason, valid_frac, t_dec, t_cls = classify_frame(frame)
                row = {
                    "pose": label, "condition": condition, "k": k,
                    "stamp": frame["stamp"], "reason": reason or "none",
                    "abort": 1 if reason else 0,
                    "exact": 1 if (reason == condition) else 0,
                    "cam_range_m": cam_range, "valid_frac": valid_frac,
                    "t_decode_s": t_dec, "t_classify_s": t_cls,
                }
                if truth is not None:
                    row["tru_lat_m"] = truth["pocket_opt"][0]
                    row["tru_range_m"] = truth["pocket_opt"][2]
                    row["face_frac_plane_roi"] = truth["face_frac_of_plane_roi"]
                    bb = truth.get("face_bbox_px")
                    if bb:
                        row.update(face_u0=bb[0], face_u1=bb[1], face_v0=bb[2], face_v1=bb[3])
                hits += row["abort"]
                exact += row["exact"]
                rows.append(row)
            manifest.append({"pose": label, "condition": condition, "base": base,
                             "seed_map": seed, "truck6": truck6, "staged": staged,
                             "world": world, "n_frames": len(frames)})
            print("    {:<18} frames {:>3} abort {:>3} exact {:>3}  reasons {}".format(
                condition, len(frames), hits, exact,
                _reason_counts([r for r in rows if r["pose"] == label
                                and r["condition"] == condition])))
    inject.restore(plant)
    return rows, manifest


def _reason_counts(rows):
    counts = {}
    for r in rows:
        counts[r["reason"]] = counts.get(r["reason"], 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def run_cycles(plant, cap, args, inject, P, dest):
    """Clean live approaches with the classifier streaming."""
    tools = os.path.join(_REPO, "m5_ver3", "tools")
    rows = []
    outcomes = []
    for c in range(args.cycles):
        inject.restore(plant)
        print("--- cycle {} stage".format(c))
        stage = subprocess.run([sys.executable, os.path.join(tools, "dock_bench.py"), "stage"],
                               capture_output=True, text=True, timeout=120)
        with open(os.path.join(dest, "cycle-{}-stage.log".format(c)), "w",
                  encoding="utf-8") as handle:
            handle.write(stage.stdout + "\n" + stage.stderr)
        if stage.returncode != 0:
            outcomes.append({"cycle": c, "stage_rc": stage.returncode,
                             "record_rc": None, "success": None, "error": None,
                             "classified": 0, "aborts": 0})
            print("    stage refused rc={}".format(stage.returncode))
            continue
        cap.spin_wall(1.0)
        log_path = os.path.join(dest, "cycle-{}-record.log".format(c))
        log = open(log_path, "w", encoding="utf-8")
        proc = subprocess.Popen(
            [sys.executable, os.path.join(tools, "dock_bench.py"), "record", "--from-staging"],
            stdout=log, stderr=subprocess.STDOUT, text=True)
        t_start = time.time()
        crow = []

        def on_frame(frame, _c=c, _rows=crow):
            reason, valid_frac, _t_dec, t_cls = classify_frame(frame)
            tr = frame.get("truth")
            row = {"cycle": _c, "k": len(_rows), "stamp": frame["stamp"],
                   "wall": frame["wall"] - t_start, "reason": reason or "none",
                   "abort": 1 if reason else 0, "valid_frac": valid_frac,
                   "t_classify_s": t_cls}
            if tr:
                from bench import geom
                row["truth_x"], row["truth_y"] = tr[1][0], tr[1][1]
                row["truth_yaw"] = geom.yaw_of_quat(*tr[2])
                row["cam_range_m"] = plant.camera_range_of((tr[1][0], tr[1][1]))
            _rows.append(row)

        def until(_p=proc, _t0=t_start):
            return _p.poll() is not None or (time.time() - _t0) > CYCLE_TIMEOUT_S

        cap.stream(on_frame, until)
        if proc.poll() is None:
            proc.kill()
        rc = proc.wait()
        log.close()
        with open(log_path, encoding="utf-8") as handle:
            text = handle.read()
        m_ok = re.search(r"success\s+(True|False)", text)
        m_err = re.search(r"error(?:_code)?\s+(\d+)", text)
        m_session = re.search(r"session\s+(\S+)", text)
        m_truth = re.search(r"truth\s+([\d.]+)\s*m", text)
        aborts = sum(r["abort"] for r in crow)
        outcome = {"cycle": c, "stage_rc": 0, "record_rc": rc,
                   "success": (m_ok.group(1) == "True") if m_ok else None,
                   "error": int(m_err.group(1)) if m_err else None,
                   "dock_session": m_session.group(1) if m_session else None,
                   "truth_m": float(m_truth.group(1)) if m_truth else None,
                   "classified": len(crow), "aborts": aborts,
                   "false_abort_rate": (aborts / len(crow)) if crow else None,
                   "wall_s": time.time() - t_start,
                   "reasons": _reason_counts(crow)}
        outcomes.append(outcome)
        rows.extend(crow)
        print("    record rc={} success={} error={} classified={} aborts={} reasons={}".format(
            rc, outcome["success"], outcome["error"], len(crow), aborts, outcome["reasons"]))
    inject.restore(plant)
    return rows, outcomes


def summarise(static_rows, cycle_rows, outcomes, inject):
    from bench import geom
    poses = []
    for r in static_rows:
        if r["pose"] not in poses:
            poses.append(r["pose"])
    table = {}
    for pose in poses:
        table[pose] = {}
        for cond in inject.CONDITIONS:
            sub = [r for r in static_rows if r["pose"] == pose and r["condition"] == cond]
            n = len(sub)
            hits = sum(r["abort"] for r in sub)
            exact = sum(r["exact"] for r in sub)
            table[pose][cond] = {
                "n": n, "abort": hits, "exact": exact,
                "rate": (hits / n) if n else None,
                "exact_rate": (exact / n) if n else None,
                "reasons": _reason_counts(sub),
                "cam_range_m": sub[0]["cam_range_m"] if sub else None,
                "face_frac_plane_roi": sub[0].get("face_frac_plane_roi") if sub else None,
            }
    overall = {}
    for cond in inject.CONDITIONS:
        sub = [r for r in static_rows if r["condition"] == cond]
        n = len(sub)
        hits = sum(r["abort"] for r in sub)
        exact = sum(r["exact"] for r in sub)
        overall[cond] = {"n": n, "abort": hits, "exact": exact,
                         "rate": (hits / n) if n else None,
                         "exact_rate": (exact / n) if n else None,
                         "reasons": _reason_counts(sub)}
    confusion = {}
    for cond in inject.CONDITIONS:
        confusion[cond] = {k: 0 for k in ("none",) + REASONS}
        for r in static_rows:
            if r["condition"] == cond:
                confusion[cond][r["reason"]] = confusion[cond].get(r["reason"], 0) + 1
    cyc_n = len(cycle_rows)
    cyc_aborts = sum(r["abort"] for r in cycle_rows)
    return {
        "static_by_pose": table, "static_overall": overall, "confusion": confusion,
        "cycles": outcomes,
        "cycle_overall": {"classified": cyc_n, "aborts": cyc_aborts,
                          "false_abort_rate": (cyc_aborts / cyc_n) if cyc_n else None,
                          "reasons": _reason_counts(cycle_rows)},
        "t_classify_s": geom.summarise([r["t_classify_s"] for r in static_rows + cycle_rows]),
    }


def write_summary_txt(path, session, summ, plant, args, inject):
    lines = ["E3 abort classifier vs staged faults - session {}".format(session),
             "labels: {}".format(plant.labels()),
             "frames per condition: {}  ranges: {}  cycles: {}".format(
                 args.frames, args.ranges, args.cycles),
             "fault set: {}".format(inject.describe()), ""]
    poses = list(summ["static_by_pose"])
    head = "{:<18}".format("condition") + "".join("{:>18}".format(p) for p in poses) + "{:>12}".format("overall")
    lines.append("abort rate (any reason) = aborts/frames; [exact] = reason names the staged fault")
    lines.append(head)
    for cond in inject.CONDITIONS:
        cells = []
        for p in poses:
            c = summ["static_by_pose"][p][cond]
            cells.append("{:>3}/{:<3}[{:>3}]".format(c["abort"], c["n"], c["exact"]))
        o = summ["static_overall"][cond]
        lines.append("{:<18}".format(cond) + "".join("{:>18}".format(x) for x in cells)
                     + "{:>12}".format("{}/{}".format(o["abort"], o["n"])))
    lines.append("")
    lines.append("camera range per pose: " + ", ".join(
        "{} {} m".format(p, _fmt(summ["static_by_pose"][p]["clean"]["cam_range_m"], 3))
        for p in poses))
    lines.append("")
    lines.append("confusion (rows: staged condition; cols: classifier word)")
    cols = ("none",) + REASONS
    lines.append("{:<18}".format("") + "".join("{:>17}".format(c) for c in cols))
    for cond in inject.CONDITIONS:
        lines.append("{:<18}".format(cond) + "".join(
            "{:>17}".format(summ["confusion"][cond].get(c, 0)) for c in cols))
    lines.append("")
    lines.append("clean live cycles (dock_bench.py record --from-staging):")
    for o in summ["cycles"]:
        lines.append("  cycle {} plugin success={} error={} truth={} m | classified {} aborts {} "
                     "false-abort {} | reasons {}".format(
                         o["cycle"], o.get("success"), o.get("error"), _fmt(o.get("truth_m")),
                         o.get("classified"), o.get("aborts"),
                         _fmt(o.get("false_abort_rate"), 3), o.get("reasons")))
    co = summ["cycle_overall"]
    lines.append("  overall classified {} aborts {} false-abort {}".format(
        co["classified"], co["aborts"], _fmt(co["false_abort_rate"], 3)))
    lines.append("")
    t = summ["t_classify_s"]
    lines.append("classify latency s: median {} max {} n {}".format(
        _fmt(t["median"], 3), _fmt(t["max"], 3), t["n"]))
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    return lines


def run(args) -> int:
    from bench import plant as P
    from bench.faults import inject

    plant = P.Plant("e3_abort")
    session, dest = plant.session_dir("e3")
    print("session   {}".format(session))
    print("labels    {}".format(plant.labels()))
    cap = P.Capture(plant, "m8_e3_capture")
    if not cap.wait_ready(20.0):
        cap.close()
        plant.cfg.refuse("CameraInfo and ground truth arrive", cap.info_topic,
                         "nothing within 20 s on {} / {}".format(cap.info_topic, cap.truth_topic))
    try:
        static_rows, manifest = run_static(plant, cap, args, inject, P)
        cycle_rows, outcomes = ([], [])
        if args.cycles > 0:
            cycle_rows, outcomes = run_cycles(plant, cap, args, inject, P, dest)
    finally:
        cap.close()

    def _dump(path, fields, rows):
        with open(path, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore",
                                    lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({k: _fmt(row.get(k), 6) if isinstance(row.get(k), float)
                                 else ("" if row.get(k) is None else row.get(k))
                                 for k in fields})

    _dump(os.path.join(dest, "frames.csv"), STATIC_FIELDS, static_rows)
    _dump(os.path.join(dest, "cycles.csv"), CYCLE_FIELDS, cycle_rows)
    summ = summarise(static_rows, cycle_rows, outcomes, inject)
    P.write_json(os.path.join(dest, "summary.json"), {
        "bench": "e3_abort", "session": session, "frames_per_condition": args.frames,
        "ranges": args.ranges, "cycles": args.cycles, "settle_s": SETTLE_S,
        "summary": summ})
    P.write_json(os.path.join(dest, "session.json"), {
        "bench": "e3_abort", "session": session, "environment": plant.environment(),
        "fault_set": inject.describe(), "conditions": manifest,
        "pallet_design": plant.pallet_design, "pallet_dims": plant.pallet_dims,
        "cam_mount": plant.cam_mount,
        "algorithm": "m8_core.abort.classify (classical thresholds), unmodified"})
    lines = write_summary_txt(os.path.join(dest, "summary.txt"), session, summ, plant, args, inject)
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
    parser = argparse.ArgumentParser(prog="e3_abort.py")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    parser.add_argument("--ranges", default=DEFAULT_RANGES)
    parser.add_argument("--cycles", type=int, default=DEFAULT_CYCLES)
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
