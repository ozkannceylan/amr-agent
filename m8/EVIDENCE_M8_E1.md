# EVIDENCE_M8_E1 — pocket pose vs tag bar

Status: **NOT_RUN**. Needs the m5-ver3 plant (gz-sim 8.11, `forklift_ver3`
in `warehouse_ver3`, D455 `pallet_cam`, GPU preflight, mix refusals).
This file contains no measured number.

## Standing cautions

Ground truth is a score, not a command. The instrument floor (rms
0.0291 m, MAX 0.1179 m) bounds any absolute claim. No PL / SIL / PFH
claims. The Nav2 collision monitor is not a safety function. The F-PLC
never receives M8 input. Frames never leave the truck.

## Bar (quoted, not scored here)

Tag chain at staging: rms **0.0706 m** over 211 samples (R1). E1 must
match or beat that on tagged pallets. Tagless is reported honestly with
no bar.

## Result

NOT_RUN. `m8/bench/e1_pocket.py` exits 2 and prints that. No CSV, no rms,
no confidence interval.

## What is green offline

`m8_core/pocket.py` plane-fit + pocket split on synthetic depth
(`pytest m8/tests/test_pocket.py`). That is not a plant score.
