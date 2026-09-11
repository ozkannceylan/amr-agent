# EVIDENCE_M8_E3 — abort classifier vs staged faults

Status: **NOT_RUN**. Needs the m5-ver3 plant and `bench/faults/` injection
against live `pallet_cam` frames. This file contains no recall and no
false-abort rate.

## Standing cautions

Ground truth is a score, not a command. The instrument floor (rms
0.0291 m, MAX 0.1179 m) bounds any absolute claim. No PL / SIL / PFH
claims. The Nav2 collision monitor is not a safety function. The F-PLC
never receives M8 input. Frames never leave the truck.

## Bar (to be stated, not stated here)

Recall on the staged set and false-abort rate on clean cycles, both
named. `proceed` is never an M8 output.

## Result

NOT_RUN. `m8/bench/e3_abort.py` exits 2. No confusion counts.

## What is green offline

`m8_core/abort.py` names the five C2 reasons on synthetic buffers
(`pytest m8/tests/test_abort.py`). That is not a plant recall.
