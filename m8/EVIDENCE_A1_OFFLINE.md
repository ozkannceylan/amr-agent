# EVIDENCE_A1_OFFLINE — shadow nodes and refuse-all gate, no plant

Gate for the A1 work that can run without Gazebo: `pytest m8/tests`
green on a machine that has never sourced ROS and has no gz plant.
This is **not** H1. H1 needs E1/E3/E4/E5 on m5-ver3.

## Standing cautions

Ground truth is a score, not a command. No PL / SIL / PFH claims. The
collision monitor is not a safety function. The F-PLC never receives M8
input. Frames never leave the truck. M8 → M7 is VDA state only.

The instrument floor (rms 0.0291 m, MAX 0.1179 m) and the tag bar
(rms 0.0706 m / 211 samples) are quoted only. This file scores no pose.

## Environment

| Item | Value |
|---|---|
| Host | cloud agent, Ubuntu, Python 3.12.3 |
| Command | `python3 -m pytest m8/tests -v --tb=no` |
| ROS | not sourced, not imported (rclpy lives inside `main()`) |
| Gazebo | not running; benches exit 2 |
| Branch | `cursor/m8-phase-a0-d3a5` off `m5-ver3-close` |
| Date | 2026-09-06 |

pytest 9.1.1 / PyYAML were installed for this run
(`python3 -m pip install pytest pyyaml`). They are not a repo pin.

## Result

**79 passed, 0 failed, 0 skipped, 0.25 s.**

H0's 49 still hold. The added 30 are A1 wiring, synthetic C1/C2/C3,
shadow launch text, and bench stubs.

```
m8/tests/test_abort.py ........
m8/tests/test_benches_not_run.py ....
m8/tests/test_contract.py ...............
m8/tests/test_gate.py ............
m8/tests/test_msgs.py ...
m8/tests/test_no_frames_leave.py ......
m8/tests/test_nodes.py .....
m8/tests/test_pipeline.py ....
m8/tests/test_plc_isolation.py ......
m8/tests/test_pocket.py ....
m8/tests/test_shadow_launch.py ..
m8/tests/test_slot.py ..
m8/tests/test_vda_map.py .......
```

What that holds (offline only):

* C1 plane fit + two-pocket split on synthetic depth; two-pass drop of
  deeper residuals so pockets do not pull the face intercept.
* C2 names the five abort reasons on synthetic faults; a clean
  two-pocket face is silent; `proceed` is never returned.
* C3 emits `S5-L/C/R` with empty / occupied / blocked on painted thirds.
* `shadow_tick` and the veto-gate helper refuse every Proposal; with no
  E1 box the reason is `phase_a_shadow`, not `outside_delta_box`.
* Five A1 shells import rclpy only inside `main()`; they publish
  `/m8/proposal|verdict|health|log` (JSON) and subscribe on-truck depth
  by name. Colour is not subscribed. No `cmd_vel`, no opcua.
* `m8_shadow.launch.py` names those five files and does not start the
  plant, a dock consumer, or the speed arbiter.
* E1/E3/E4/E5 stubs print `NOT_RUN` and exit 2. Isolation scans still
  hold (R3/R4).

## Plant-blocked (H1, not this file)

| Bench | Status | Why |
|---|---|---|
| E1 pocket vs tag | NOT_RUN | needs gz `pallet_cam` depth + tag chain |
| E3 abort recall / false-abort | NOT_RUN | needs `bench/faults/` on live frames |
| E4 slot confusion | NOT_RUN | needs world-state occupancy on the plant |
| E5 RTF / latency | NOT_RUN | needs the m5-ver3 rig and mix refusals |

Templates: `m8/EVIDENCE_M8_E{1,3,4,5}.md`. They invent no numbers.

## What this is not

Not H1. Not a dock number. Not a live consumer. Phase B (abort live)
has not started.
