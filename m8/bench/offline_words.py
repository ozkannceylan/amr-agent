#!/usr/bin/env python3
"""offline_words.py - which WORD C2 says, and what the self-mask changes.

    python3 m8/bench/offline_words.py
    python3 m8/bench/offline_words.py --seeds 5 --out m8/bench/results

READ THIS BEFORE QUOTING A NUMBER FROM IT. No plant, no ROS, no gz. It
renders depth from ray/plane intersections (`m8_core.scene`) and scores
`m8_core.abort.classify` against the geometry it rendered from. Same
standing caution as `offline_scene.py`: the renderer and the estimator
share their assumptions - flat floor, flat face, pinhole camera,
Gaussian noise - so a mistake inside that shared assumption cannot show
up here. E3 on the m5-ver3 rig is the score.

WHAT IT IS FOR. `EVIDENCE_M8_C1C2_FIX.md` measured a 0.884 live
false-abort rate and named three causes it did not fix:

  open 1  C1 sees nothing inside ~1.2 m - the truck's own forks are
          continuous with the pallet at that range
  open 3  `pocket_blocked` aborts with the WRONG WORD, 84 times in 90,
          cause not established
  open 4  `stringer_in_path` cannot widen its search past the pallet's
          own footprint without a fork self-mask

None of the three had a fixture. Every offline scene was a pallet on a
floor, so a classifier could be green here and wrong on the rig - which
is exactly what happened. The six families below put the rig's own
findings in front of the classifier:

  clean           a square pallet, pockets open
  forks           the same pallet WITH the truck's tines reaching at it
  forks_empty     the tines with no pallet - the bay really is empty
  blocked_by_box  the plant's m8_pocket_block across both openings
  ridge           the plant's m8_stringer, a separate component 0.60 m out
  clipped         a pallet running off the edge of the image

Each case is classified THREE times on the SAME depth buffer: with no
self-mask, with a fresh one, and with a stale one. Three words on one
frame is the only way to attribute a difference to the mask.

`proceed` is not a word here and is not an output of anything.
Every run writes a new session folder. It never edits an old one.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core import selfmask                                   # noqa: E402
from m8_core.abort import classify                             # noqa: E402
from m8_core.pocket import blob_touches_border, segment        # noqa: E402
from m8_core.scene import make_scene_depth                     # noqa: E402

W, H = 320, 240
STAGING_M, APPROACH_M, CLOSE_M = 2.245, 1.5, 1.0
STAMP = 1.0

# The tines, off `m8_core.selfmask`, which took them off model.sdf. The
# renderer is told the same geometry the mask is told, so a disagreement
# between them is a bug in one of the two and not a modelling choice.
TINES = tuple((lo, hi, selfmask.TINE_TOP_M, 0.0, selfmask.TINE_REACH_M)
              for lo, hi in selfmask.TINE_LATERAL_M)

# name, distance, expected word (None = clean), scene kwargs, note
CASES = (
    ("clean", STAGING_M, None, {}, ""),
    ("clean", APPROACH_M, None, {}, ""),
    ("clean", CLOSE_M, None, {}, ""),
    ("forks", STAGING_M, None, {"slabs": TINES}, "tines and pallet separate"),
    ("forks", APPROACH_M, None, {"slabs": TINES}, "tines and pallet separate"),
    ("forks", CLOSE_M, None, {"slabs": TINES},
     "open 1: one surface to this camera"),
    ("forks_empty", STAGING_M, "pallet_absent",
     {"slabs": TINES, "pallet": False}, ""),
    ("forks_empty", APPROACH_M, "pallet_absent",
     {"slabs": TINES, "pallet": False}, ""),
    ("forks_empty", CLOSE_M, "pallet_absent",
     {"slabs": TINES, "pallet": False}, ""),
    ("empty_bay", APPROACH_M, "pallet_absent", {"pallet": False}, ""),
    ("blocked_by_box", STAGING_M, "pocket_blocked", {"box": True},
     "open 3: wrong word 84 of 90 on the plant"),
    ("blocked_by_box", APPROACH_M, "pocket_blocked", {"box": True},
     "open 3"),
    ("blocked_by_box", CLOSE_M, "pocket_blocked", {"box": True}, "open 3"),
    ("ridge", APPROACH_M, "stringer_in_path", {"ridge": True},
     "open 4: a separate component, never entered"),
    ("ridge", CLOSE_M, "stringer_in_path", {"ridge": True}, "open 4"),
    ("clipped", APPROACH_M, None, {"lateral": 1.45}, "runs off the image"),
    ("clipped", CLOSE_M, None, {"lateral": 0.95}, "runs off the image"),
    ("rotated_pos", APPROACH_M, "pallet_rotated", {"yaw": 0.25}, ""),
    ("rotated_neg", APPROACH_M, "pallet_rotated", {"yaw": -0.25}, ""),
    ("shifted", APPROACH_M, "pallet_shifted", {"lateral": 0.75}, ""),
    ("pockets_filled", APPROACH_M, "pocket_blocked", {"pockets": False}, ""),
    ("stringer_at_face", CLOSE_M, "stringer_in_path", {"bar": True},
     "a bar 0.08 m in front of the face"),
)

FIELDS = ("case", "range_m", "seed", "expected", "reason", "exact",
          "false_abort", "seg_ok", "refused", "clipped",
          "reason_masked", "exact_masked", "seg_ok_masked", "refused_masked",
          "reason_stale_mask", "t_classify_s", "t_classify_masked_s")


def _render(distance, seed, kw):
    kw = dict(kw)
    if kw.pop("box", False):
        # m8_pocket_block: 0.10 x 0.72 x 0.10 m across both openings,
        # 0.06 m in front of the face (bench/faults/inject.py).
        kw["obstacles"] = ((-0.76, -0.04, 0.0, 0.10, distance - 0.06),)
    if kw.pop("ridge", False):
        # m8_stringer: 0.08 x 1.00 x 0.06 m on the floor, 0.60 m out.
        kw["obstacles"] = ((-0.90, 0.10, 0.0, 0.06, distance - 0.60),)
    if kw.pop("bar", False):
        kw["obstacles"] = ((-0.55, -0.25, 0.0, 0.13, distance - 0.08),)
    return make_scene_depth(width=W, height=H, face_distance=distance,
                            seed=seed, sim_stamp=STAMP, **kw)


def run(seeds):
    fresh = selfmask.from_mast_joint(0.0, stamp=STAMP)
    stale = selfmask.from_mast_joint(0.0, stamp=STAMP - 10.0)
    rows = []
    for name, distance, expected, kw, _note in CASES:
        for seed in range(seeds):
            frame, _scene = _render(distance, seed, kw)
            trace = {}
            t0 = time.perf_counter()
            reason = classify(frame)
            t1 = time.perf_counter()
            seg = segment(frame, trace=trace)
            reason_m = classify(frame, self_mask=fresh)
            t2 = time.perf_counter()
            mtrace = {}
            seg_m = segment(frame, trace=mtrace, self_mask=fresh)
            rows.append({
                "case": name, "range_m": distance, "seed": seed,
                "expected": expected or "none",
                "reason": reason or "none",
                "exact": 1 if reason == expected else 0,
                "false_abort": 1 if (expected is None and reason) else 0,
                "seg_ok": 1 if seg else 0,
                "refused": "" if seg else str(trace.get("refused") or "-"),
                "clipped": (1 if (seg and seg.floor is not None
                                  and blob_touches_border(frame, seg.blob))
                            else 0),
                "reason_masked": reason_m or "none",
                "exact_masked": 1 if reason_m == expected else 0,
                "seg_ok_masked": 1 if seg_m else 0,
                "refused_masked": ("" if seg_m
                                   else str(mtrace.get("refused") or "-")),
                "reason_stale_mask": classify(frame, self_mask=stale) or "none",
                "t_classify_s": t1 - t0,
                "t_classify_masked_s": t2 - t1,
            })
    return rows


def summarise(rows):
    per_case = {}
    for name, distance, expected, _kw, note in CASES:
        sub = [r for r in rows if r["case"] == name
               and r["range_m"] == distance]
        if not sub:
            continue
        key = "{}@{:.3f}".format(name, distance)
        words = {}
        words_m = {}
        for r in sub:
            words[r["reason"]] = words.get(r["reason"], 0) + 1
            words_m[r["reason_masked"]] = words_m.get(r["reason_masked"], 0) + 1
        per_case[key] = {
            "expected": expected or "none", "n": len(sub),
            "exact": sum(r["exact"] for r in sub),
            "exact_masked": sum(r["exact_masked"] for r in sub),
            "false_abort": sum(r["false_abort"] for r in sub),
            "words": words, "words_masked": words_m,
            "segmented": sum(r["seg_ok"] for r in sub),
            "segmented_masked": sum(r["seg_ok_masked"] for r in sub),
            "refusals": sorted({r["refused"] for r in sub if r["refused"]}),
            "note": note,
        }
    clean = [r for r in rows if r["expected"] == "none"]
    stale_words = {}
    for r in rows:
        stale_words[r["reason_stale_mask"]] = stale_words.get(
            r["reason_stale_mask"], 0) + 1
    return {
        "per_case": per_case,
        "n_frames": len(rows),
        "clean_frames": len(clean),
        "false_aborts": sum(r["false_abort"] for r in rows),
        "exact": sum(r["exact"] for r in rows),
        "exact_masked": sum(r["exact_masked"] for r in rows),
        "segmented": sum(r["seg_ok"] for r in rows),
        "segmented_masked": sum(r["seg_ok_masked"] for r in rows),
        "stale_mask_words": stale_words,
        "not_a_plant_result": True,
    }


def render_text(summary):
    out = ["OFFLINE WORD BENCH - rendered depth, no plant, no ROS.",
           "Not a plant result. E3 on the m5-ver3 rig is the score.",
           ""]
    out.append("{:<26} {:<17} {:>7} {:>7} {:>7} {:>7}  {}".format(
        "case", "expected", "exact", "+mask", "seg", "+mask", "words"))
    for key, cell in summary["per_case"].items():
        out.append("{:<26} {:<17} {:>3}/{:<3} {:>3}/{:<3} {:>3}/{:<3} "
                   "{:>3}/{:<3}  {}".format(
                       key, cell["expected"], cell["exact"], cell["n"],
                       cell["exact_masked"], cell["n"],
                       cell["segmented"], cell["n"],
                       cell["segmented_masked"], cell["n"],
                       json.dumps(cell["words"], sort_keys=True)))
        if cell["words_masked"] != cell["words"]:
            out.append("{:<26} {:<17} {:>31}  masked: {}".format(
                "", "", "", json.dumps(cell["words_masked"], sort_keys=True)))
        if cell["refusals"]:
            out.append("{:<26} refused: {}".format("", cell["refusals"]))
    out.append("")
    out.append("false aborts on frames expected clean: {} of {}".format(
        summary["false_aborts"], summary["clean_frames"]))
    out.append("reason-exact: {} of {} unmasked, {} masked".format(
        summary["exact"], summary["n_frames"], summary["exact_masked"]))
    out.append("segmented:    {} of {} unmasked, {} masked".format(
        summary["segmented"], summary["n_frames"],
        summary["segmented_masked"]))
    out.append("with a STALE mask every frame must read `none`: {}".format(
        json.dumps(summary["stale_mask_words"], sort_keys=True)))
    return "\n".join(out) + "\n"


def _md5(path):
    with open(path, "rb") as handle:
        return hashlib.md5(handle.read()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="offline_words.py")
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--out", default=os.path.join(_HERE, "results"))
    args = parser.parse_args(argv)

    started = time.time()
    rows = run(args.seeds)
    summary = summarise(rows)
    summary["seeds"] = args.seeds
    summary["wall_s"] = time.time() - started
    summary["algorithm"] = "m8_core.abort.classify + m8_core.selfmask"
    summary["renderer"] = "m8_core.scene.make_scene_depth"

    session = time.strftime("words-%Y%m%d-%H%M%S")
    folder = os.path.join(args.out, session)
    os.makedirs(folder)
    with open(os.path.join(folder, "frames.csv"), "w", encoding="utf-8",
              newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS,
                                lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in FIELDS})
    text = render_text(summary)
    with open(os.path.join(folder, "summary.json"), "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    with open(os.path.join(folder, "summary.txt"), "w", encoding="utf-8",
              newline="\n") as handle:
        handle.write(text)
    print(text)
    print("session " + folder)
    for name in sorted(os.listdir(folder)):
        print("  {}  {}".format(_md5(os.path.join(folder, name)), name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
