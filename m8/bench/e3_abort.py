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

WHAT THE INSTRUMENT RECORDS, AND WHY IT HAD TO GROW. The 2026-09-12 run
(`e3-20260912-000826`) measured a live false-abort rate of 0.884 and
could not say what the 948 aborts WERE. One word - `pallet_absent` -
covers both "the bay is empty" and "C1 refused and the caller had no
other word", and the session held no column that told them apart. Four
joins were missing and are added here, with NO change to the classifier:

  REGIME    which range band the frame was taken in, so a rate can be
            read per band instead of averaged over an approach that
            crosses three of them.
  REFUSED   the NAMED refusal `m8_core.pocket.segment` raised for this
            frame (`face_is_too_small_a_share`,
            `face_width_not_pallet_sized`, ...), recomputed outside the
            timed call. "no pose" and "no pose BECAUSE the face was 23 %
            of the blob" are not the same finding.
  RETRIES   `num_retries` and the docking state at the frame's own sim
            stamp, joined from the dock session's `feedback.csv`. A frame
            taken during a retry is a different population from one taken
            on a first, uninterrupted approach.
  READBACK  the pallet's gz pose before and after each cycle. A cycle
            that ended with the pallet shoved 0.2 m is not a clean cycle
            and must not be averaged into one.

The regime edges and the moved-pallet tolerance below are BENCH constants
for slicing a table. They are not thresholds in the classifier and
nothing in `m8_core` reads them.

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

# Range bands, camera -> design face, in metres. The edges are where
# this rig's behaviour is already known to change: staging is 2.245 m,
# and EVIDENCE_M8_C1C2_FIX measured C1 refusing inside ~1.2 m because
# the truck's own forks are continuous with the pallet there. SLICING
# ONLY - no gate in m8_core reads these.
REGIMES = (("staging", 2.0, float("inf")),
           ("approach", 1.2, 2.0),
           ("close", 0.0, 1.2))
# A cycle whose pallet moved further than this is not a clean cycle. The
# gz readback jitter is millimetres; 0.02 m is an order over it and well
# under the 0.16 m pocket it would take to matter.
PALLET_MOVED_TOL_M = 0.02

STATIC_FIELDS = (
    "pose", "regime", "condition", "k", "stamp", "reason", "abort", "exact",
    "cam_range_m", "tru_lat_m", "tru_range_m", "face_u0", "face_u1",
    "face_v0", "face_v1", "face_frac_plane_roi", "valid_frac",
    "seg_ok", "refused", "candidates", "in_window", "inlier_frac",
    "roi_u0", "roi_u1", "roi_v0", "roi_v1", "seg_width_m",
    "seg_height_m", "seg_yaw_rad", "t_decode_s", "t_classify_s",
)
CYCLE_FIELDS = (
    "cycle", "k", "stamp", "wall", "regime", "reason", "abort",
    "truth_x", "truth_y", "truth_yaw", "cam_range_m", "valid_frac",
    "seg_ok", "refused", "candidates", "in_window", "inlier_frac",
    "roi_u0", "roi_u1", "roi_v0", "roi_v1", "seg_width_m",
    "seg_height_m", "seg_yaw_rad",
    "num_retries", "dock_state", "retry_joined",
    "pallet_readback_ok", "pallet_moved_m", "countable", "t_classify_s",
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


def regime_of(cam_range_m):
    """Which range band a frame was taken in. Bench slicing, not a gate."""
    if cam_range_m is None:
        return "unknown"
    try:
        r = float(cam_range_m)
    except (TypeError, ValueError):
        return "unknown"
    if math.isnan(r):
        return "unknown"
    for name, lo, hi in REGIMES:
        if lo <= r < hi:
            return name
    return "unknown"


def classify_frame(frame):
    """The classifier's word plus every column needed to read it back.

    Returns a dict. `reason` is `m8_core.abort.classify` on the frame the
    shadow node would receive, unmodified, and it is the only thing
    inside the timed section. Everything else is recomputed OUTSIDE it:

      * the derived face ROI, because a classifier that derives its own
        ROI has to log it or `pallet_absent` cannot be told apart from
        "the pallet was there and the segmentation missed it";
      * the NAMED refusal, out of the same `trace` dict
        `bench/diag_segment.py` reads, because `seg is None` is a fact
        and `face_is_too_small_a_share` is a diagnosis.

    The trace costs a second segmentation pass. That is deliberate: the
    timed number stays the node's own cost and not the bench's.
    """
    from bench import plant as P
    from m8_core.abort import classify
    from m8_core.pocket import face_yaw, segment
    t0 = time.perf_counter()
    depths = P.decode(frame)
    df = P.depth_frame(frame, depths)
    t1 = time.perf_counter()
    reason = classify(df)
    t2 = time.perf_counter()
    trace = {}
    seg = segment(df, trace=trace)
    valid = sum(1 for z in depths if math.isfinite(z) and z > 0.0)
    out = {
        "reason": reason or "none",
        "abort": 1 if reason else 0,
        "valid_frac": valid / float(len(depths)),
        "t_decode_s": t1 - t0,
        "t_classify_s": t2 - t1,
        "seg_ok": 1 if seg is not None else 0,
        "refused": "" if seg is not None else str(trace.get("refused")
                                                  or "unnamed"),
        "candidates": trace.get("candidates"),
        "in_window": trace.get("in_window"),
        "inlier_frac": trace.get("inlier_frac"),
    }
    if seg is not None:
        out.update(roi_u0=seg.u0, roi_u1=seg.u1, roi_v0=seg.v0, roi_v1=seg.v1,
                   seg_width_m=seg.width_m, seg_height_m=seg.height_m,
                   seg_yaw_rad=face_yaw(seg.face, seg.up))
    return out


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
                out = classify_frame(frame)
                row = dict(out)
                row.update({
                    "pose": label, "regime": regime_of(cam_range),
                    "condition": condition, "k": k,
                    "stamp": frame["stamp"],
                    "exact": 1 if (out["reason"] == condition) else 0,
                    "cam_range_m": cam_range,
                })
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


def _refusal_counts(rows):
    """Which named C1 refusal stood behind each word, where there was one."""
    counts = {}
    for r in rows:
        key = r.get("refused") or "(segmented)"
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _by_regime(rows):
    """Abort rate, words and refusals per range band.

    The single figure `948 / 1073` hid the whole finding: the bands do
    not behave alike and averaging them answers no question anyone asked.
    """
    out = {}
    for name, _lo, _hi in REGIMES:
        sub = [r for r in rows if r.get("regime") == name]
        if not sub:
            continue
        hits = sum(r["abort"] for r in sub)
        out[name] = {"n": len(sub), "abort": hits,
                     "rate": hits / float(len(sub)),
                     "reasons": _reason_counts(sub),
                     "refusals": _refusal_counts(sub)}
    unknown = [r for r in rows if r.get("regime") == "unknown"]
    if unknown:
        out["unknown"] = {"n": len(unknown),
                          "abort": sum(r["abort"] for r in unknown),
                          "rate": sum(r["abort"] for r in unknown)
                          / float(len(unknown)),
                          "reasons": _reason_counts(unknown),
                          "refusals": _refusal_counts(unknown)}
    return out


def _read_feedback(plant, session):
    """[(sim_t, state, num_retries)] from a dock session, or [].

    `dock_bench.py record` writes `feedback.csv` beside its own session
    under `evidence.dir`, stamped on the SAME sim clock the depth frames
    carry (both nodes run with use_sim_time true), so the join key is
    exact and needs no wall-clock correction.
    """
    if not session:
        return []
    path = os.path.join(_REPO, plant.cfg.s("evidence.dir"), session,
                        "feedback.csv")
    if not os.path.isfile(path):
        return []
    out = []
    try:
        with open(path, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                out.append((float(row["t_s"]), int(row["state"]),
                            int(row["num_retries"])))
    except (ValueError, KeyError, OSError):
        return []
    out.sort(key=lambda r: r[0])
    return out


def _join_retries(rows, feedback):
    """Stamp each frame with the retry count in force when it was taken.

    Step function, held backwards: the docking server publishes feedback
    on change, so the value at a frame's stamp is the last one published
    at or before it. Frames taken before the first feedback message are
    left blank rather than assumed to be retry 0 - the bench does not
    know, and `retry_joined` says so.
    """
    if not feedback:
        for row in rows:
            row["retry_joined"] = 0
        return 0
    idx = 0
    joined = 0
    for row in sorted(rows, key=lambda r: r["stamp"]):
        while idx + 1 < len(feedback) and feedback[idx + 1][0] <= row["stamp"]:
            idx += 1
        if feedback[idx][0] <= row["stamp"]:
            row["dock_state"] = feedback[idx][1]
            row["num_retries"] = feedback[idx][2]
            row["retry_joined"] = 1
            joined += 1
        else:
            row["retry_joined"] = 0
    return joined


def _pallet_moved_m(before, after):
    """Planar distance the pallet travelled during a cycle, or None."""
    if not before or not after:
        return None
    return math.hypot(after[0] - before[0], after[1] - before[1])


def run_cycles(plant, cap, args, inject, P, dest):
    """Clean live approaches with the classifier streaming."""
    tools = os.path.join(_REPO, "m5_ver3", "tools")
    rows = []
    outcomes = []
    for c in range(args.cycles):
        inject.restore(plant)
        pallet_before = plant.gz_model_pose(plant.pallet_name)
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
            out = classify_frame(frame)
            tr = frame.get("truth")
            row = dict(out)
            row.update({"cycle": _c, "k": len(_rows), "stamp": frame["stamp"],
                        "wall": frame["wall"] - t_start})
            if tr:
                from bench import geom
                row["truth_x"], row["truth_y"] = tr[1][0], tr[1][1]
                row["truth_yaw"] = geom.yaw_of_quat(*tr[2])
                row["cam_range_m"] = plant.camera_range_of((tr[1][0], tr[1][1]))
            row["regime"] = regime_of(row.get("cam_range_m"))
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
        m_retries = re.search(r"retries\s+(\d+)", text)
        session_name = m_session.group(1) if m_session else None
        # The joins. Neither can be taken after the next cycle restores
        # the world, so both are taken here, before inject.restore().
        pallet_after = plant.gz_model_pose(plant.pallet_name)
        moved = _pallet_moved_m(pallet_before, pallet_after)
        readback_ok = 1 if (pallet_before and pallet_after) else 0
        feedback = _read_feedback(plant, session_name)
        joined = _join_retries(crow, feedback)
        cycle_retries = int(m_retries.group(1)) if m_retries else None
        clean_cycle = (readback_ok == 1
                       and moved is not None and moved <= PALLET_MOVED_TOL_M)
        for row in crow:
            row["pallet_readback_ok"] = readback_ok
            row["pallet_moved_m"] = moved
            # COUNTABLE is the interim bar's population and nothing else:
            # a frame on a retry-free stretch of a cycle whose pallet was
            # read back and did not move. A frame the join could not
            # reach is NOT countable - unknown is not zero.
            row["countable"] = 1 if (clean_cycle
                                     and row.get("retry_joined") == 1
                                     and row.get("num_retries") == 0) else 0
        aborts = sum(r["abort"] for r in crow)
        countable = [r for r in crow if r["countable"]]
        c_aborts = sum(r["abort"] for r in countable)
        outcome = {"cycle": c, "stage_rc": 0, "record_rc": rc,
                   "success": (m_ok.group(1) == "True") if m_ok else None,
                   "error": int(m_err.group(1)) if m_err else None,
                   "dock_session": session_name,
                   "truth_m": float(m_truth.group(1)) if m_truth else None,
                   "num_retries": cycle_retries,
                   "feedback_rows": len(feedback), "retry_joined": joined,
                   "pallet_readback_ok": readback_ok,
                   "pallet_before": pallet_before, "pallet_after": pallet_after,
                   "pallet_moved_m": moved, "clean_cycle": clean_cycle,
                   "classified": len(crow), "aborts": aborts,
                   "false_abort_rate": (aborts / len(crow)) if crow else None,
                   "countable": len(countable), "countable_aborts": c_aborts,
                   "countable_false_abort_rate": (
                       (c_aborts / len(countable)) if countable else None),
                   "wall_s": time.time() - t_start,
                   "reasons": _reason_counts(crow),
                   "refusals": _refusal_counts(crow),
                   "by_regime": _by_regime(crow)}
        outcomes.append(outcome)
        rows.extend(crow)
        print("    record rc={} success={} error={} retries={} classified={} "
              "aborts={} reasons={}".format(
                  rc, outcome["success"], outcome["error"], cycle_retries,
                  len(crow), aborts, outcome["reasons"]))
        print("    pallet moved {} m readback_ok={} clean_cycle={} | countable "
              "{} aborts {} false-abort {}".format(
                  _fmt(moved, 4), readback_ok, clean_cycle, len(countable),
                  c_aborts, _fmt(outcome["countable_false_abort_rate"], 3)))
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
    # The interim bar's population, stated as a population and not as a
    # filter applied after the fact: retry-free frames of a cycle whose
    # pallet was read back and did not move. Everything else is reported
    # beside it, never folded into it.
    countable = [r for r in cycle_rows if r.get("countable")]
    cnt_aborts = sum(r["abort"] for r in countable)
    retry_rows = [r for r in cycle_rows
                  if r.get("retry_joined") == 1 and r.get("num_retries")]
    unjoined = [r for r in cycle_rows if r.get("retry_joined") != 1]
    moved_rows = [r for r in cycle_rows if r.get("countable") == 0
                  and r.get("retry_joined") == 1
                  and not r.get("num_retries")]
    return {
        "static_by_pose": table, "static_overall": overall, "confusion": confusion,
        "static_by_regime": _by_regime(
            [r for r in static_rows if r["condition"] == "clean"]),
        "static_refusals": _refusal_counts(static_rows),
        "cycles": outcomes,
        "cycle_overall": {"classified": cyc_n, "aborts": cyc_aborts,
                          "false_abort_rate": (cyc_aborts / cyc_n) if cyc_n else None,
                          "reasons": _reason_counts(cycle_rows),
                          "refusals": _refusal_counts(cycle_rows)},
        "cycle_by_regime": _by_regime(cycle_rows),
        "cycle_countable": {
            "classified": len(countable), "aborts": cnt_aborts,
            "false_abort_rate": (cnt_aborts / len(countable)) if countable else None,
            "reasons": _reason_counts(countable),
            "refusals": _refusal_counts(countable),
            "by_regime": _by_regime(countable),
            "definition": ("num_retries == 0, joined from the dock session's "
                           "feedback.csv, on a cycle whose pallet was read "
                           "back before and after and moved <= {} m".format(
                               PALLET_MOVED_TOL_M))},
        "cycle_excluded": {
            "on_a_retry": len(retry_rows),
            "retry_unjoined": len(unjoined),
            "pallet_moved_or_unread": len(moved_rows),
            "note": ("reported, never folded in: a frame whose retry count "
                     "the bench could not reach is unknown, not zero")},
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
    lines.append("named C1 refusals behind the static words: {}".format(
        summ.get("static_refusals")))
    lines.append("clean static frames by range band: {}".format(
        {k: "{}/{}".format(v["abort"], v["n"])
         for k, v in summ.get("static_by_regime", {}).items()}))
    lines.append("")
    lines.append("clean live cycles (dock_bench.py record --from-staging):")
    for o in summ["cycles"]:
        lines.append("  cycle {} plugin success={} error={} retries={} truth={} m "
                     "| classified {} aborts {} false-abort {} | reasons {}".format(
                         o["cycle"], o.get("success"), o.get("error"),
                         o.get("num_retries"), _fmt(o.get("truth_m")),
                         o.get("classified"), o.get("aborts"),
                         _fmt(o.get("false_abort_rate"), 3), o.get("reasons")))
        lines.append("           pallet readback_ok={} moved={} m clean_cycle={} "
                     "| retries joined {}/{} from {} feedback rows".format(
                         o.get("pallet_readback_ok"), _fmt(o.get("pallet_moved_m")),
                         o.get("clean_cycle"), o.get("retry_joined"),
                         o.get("classified"), o.get("feedback_rows")))
        lines.append("           countable {} aborts {} false-abort {}".format(
            o.get("countable"), o.get("countable_aborts"),
            _fmt(o.get("countable_false_abort_rate"), 3)))
    co = summ["cycle_overall"]
    lines.append("  overall classified {} aborts {} false-abort {}".format(
        co["classified"], co["aborts"], _fmt(co["false_abort_rate"], 3)))
    lines.append("  refusals behind those words: {}".format(co.get("refusals")))
    lines.append("")
    lines.append("live frames by range band (all cycles):")
    for band, cell in summ.get("cycle_by_regime", {}).items():
        lines.append("  {:<10} {:>4}/{:<4} = {}  reasons {}".format(
            band, cell["abort"], cell["n"], _fmt(cell["rate"], 3),
            cell["reasons"]))
        lines.append("  {:<10} refusals {}".format("", cell["refusals"]))
    lines.append("")
    cc = summ.get("cycle_countable", {})
    lines.append("INTERIM BAR POPULATION - {}".format(cc.get("definition")))
    lines.append("  classified {} aborts {} false-abort {}".format(
        cc.get("classified"), cc.get("aborts"),
        _fmt(cc.get("false_abort_rate"), 3)))
    lines.append("  reasons {}".format(cc.get("reasons")))
    lines.append("  refusals {}".format(cc.get("refusals")))
    lines.append("  by band {}".format(
        {k: "{}/{}".format(v["abort"], v["n"])
         for k, v in cc.get("by_regime", {}).items()}))
    ex = summ.get("cycle_excluded", {})
    lines.append("  excluded and reported separately: on a retry {}, retry "
                 "count unjoined {}, pallet moved or unread {}".format(
                     ex.get("on_a_retry"), ex.get("retry_unjoined"),
                     ex.get("pallet_moved_or_unread")))
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
