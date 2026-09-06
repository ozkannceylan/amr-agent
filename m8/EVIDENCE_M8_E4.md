# EVIDENCE_M8_E4 — slot table vs world-state occupancy

Status: **NOT_RUN**. Needs `warehouse_ver3` rack occupancy from the
world state and a live `pallet_cam` at station approach. This file
contains no confusion matrix.

## Standing cautions

Ground truth is a score, not a command. The instrument floor (rms
0.0291 m, MAX 0.1179 m) bounds any absolute claim. No PL / SIL / PFH
claims. The Nav2 collision monitor is not a safety function. The F-PLC
never receives M8 input. Frames never leave the truck.

## Bar (to be stated, not stated here)

Confusion matrix of empty / occupied / blocked vs world-state
occupancy, with lighting and camera-pitch variants.

## Result

NOT_RUN. `m8/bench/e4_slot.py` exits 2.

## What is green offline

`m8_core/slot.py` maps three synthetic columns
(`pytest m8/tests/test_slot.py`). That is not a plant matrix.
