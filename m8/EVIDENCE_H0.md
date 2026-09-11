# EVIDENCE_H0 — m8_core contract tests, no ROS

Gate H0: `pytest m8/tests` green on a machine that has never sourced ROS.

## Standing cautions

Ground truth is a score, not a command. No PL / SIL / PFH claims. The
collision monitor is not a safety function. The F-PLC never receives M8
input. Frames never leave the truck. M8 → M7 is VDA state only.

The instrument floor (rms 0.0291 m, MAX 0.1179 m) is not used here:
H0 scores no pose.

## Environment

| Item | Value |
|---|---|
| Host | cloud agent, Ubuntu, Python 3.12.3 |
| Command | `python3 -m pytest m8/tests -v --tb=no` |
| ROS | not sourced, not imported |
| Branch | `cursor/m8-phase-a0-d3a5` off `m5-ver3-close` |
| Date | 2026-09-06 |

pytest 9.1.1 was installed for this run (`python3 -m pip install pytest
pyyaml`). It is not a repo pin.

## Result

**49 passed, 0 failed, 0 skipped, 0.19 s.**

```
m8/tests/test_contract.py ...............
m8/tests/test_gate.py ...........
m8/tests/test_msgs.py ...
m8/tests/test_no_frames_leave.py .....
m8/tests/test_plc_isolation.py ......
m8/tests/test_vda_map.py ......
```

What that holds:

* A well-formed Proposal validates; `proceed` is not a kind or a reason.
* Sensor name is `pallet_cam` only (R2). SPEED_REDUCE needs `leg_id` and
  a ceiling > 0 (R5: zero is a stop).
* TTL expires at the boundary; remaining ms never go negative.
* Monotone: smaller refine / lower ceiling / abort only; abort is terminal.
* Phase A refuses every kind, including a perfect in-box refine, and
  appends one log row per `evaluate`.
* Stale TTL, stale frame, missing/failed health, outside delta box and
  monotone violations are named reasons, not silent accepts.
* `m8.dockAbort` is `errors[]` WARNING; `m8.slotState` is `information[]`
  INFO. Field names are the subset's (`errorType`, `errorLevel`,
  `infoType`, `infoLevel`, `referenceKey` / `referenceValue`).
* Bridge configs (`bridge/config/*.yaml` and the M3/M4 virtual siblings)
  carry no image topic (R3). PLC link configs and `plc_link.py` carry no
  M8 name (R4). `m8_core` imports neither rclpy nor opcua.

## What this is not

Not E1–E6. Not a dock number. Not a live consumer. Phase A1 nodes and
benches are the next ticket.
