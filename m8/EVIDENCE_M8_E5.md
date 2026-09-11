# EVIDENCE_M8_E5 — cost and latency of M8 on the rig

Status: **NOT_RUN**. Needs the measured m5-ver3 rig (GPU preflight, RTF
before/after, frame-age and inference histograms). This file contains
no RTF and no p95.

## Standing cautions

Ground truth is a score, not a command. The instrument floor (rms
0.0291 m, MAX 0.1179 m) bounds any absolute claim. No PL / SIL / PFH
claims. The Nav2 collision monitor is not a safety function. The F-PLC
never receives M8 input. Frames never leave the truck.

## Bar (to be fixed from this bench, not fixed here)

Health budgets in `m8_core.gate` (`DEFAULT_MAX_*`) are placeholders
until this run names them.

## Result

NOT_RUN. `m8/bench/e5_cost.py` exits 2. Precedent only (not this run):
bridging OS0 cost mean RTF 0.999 → 0.85 (R2). M8's own cost is unmeasured.

## What is green offline

Health snapshots and refuse-rather-than-limp
(`pytest m8/tests/test_gate.py`, `test_nodes.py`). Not a rig cost.
