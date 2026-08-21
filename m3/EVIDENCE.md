# M3 evidence — the gate re-run against the virtual PLC, 2026-08-21/22

The 2026-07-28 gate evidence (watch-table captures, the latency measurement,
the signal-loss log) lives untouched at `plc/demo-cell/evidence/` and is
cited from `plc/demo-cell/SPEC.md` §9/§11. This file records the **new**
thing: the M3 loop running again on 2026-08-21, after the PLCSIM trial
expired, with the virtual PLC in the CPU seat.

## What ran

- CPU: `m5/m5_ver1/virtual_plc/virtual_plc.py` (extended this day with
  `demo_cell_program.py` — FB_DemoCellControl transliterated from
  `plc/demo-cell/SPEC.md` §7, parts 2–8; the link half keeps its M5-era
  home in `standard_program.py`'s companion fragment).
- Linux side: `m3/run_cell.sh start` — `sim/launch/cell_bringup.launch.py`
  (headless), `bridge/run_bridge.py` with the cell group rendered from
  `m3/bridge.cell.virtual.yaml`, `cell_stimulus.py` at rest. The bridge's
  startup rule R3 closed.
- Exercise: `m3/verify_cell.py`.

## Unit tests

`python -m pytest m5/m5_ver1/virtual_plc/test_demo_cell.py` — **14/14
pass**: boot polarity, reset held across link-up refused, link loss
mid-run, full cycle, start refused with a latch standing, re-home branch,
stuck-start-at-boot, process-stop latch and override, reset refused while
the cause stands, NaN range fault, belt-feedback fault as its own latch,
stalled drive vs. healthy start, freeze-window re-arm catching a
mid-motion freeze (the m3-26 defect's regression pin), soft-limit abort.

The pre-existing suites still pass unchanged against the extended process:
`test_virtual_plc.py` 22/22, and `smoke_test.py` 9/9 over the wire.

## The gate exercise, fresh CPU (first run of the night)

Console log of `verify_cell.py` against a freshly started virtual PLC —
**16/16 PASS**, exit 0:

```
PASS namespaces and browse paths resolve
PASS BridgeLinkOk TRUE -- the bridge's heartbeat moves (R3 closed)
PASS boot: CellResetRequired TRUE -- the boot link-loss latch stands (SPEC 6.1)
PASS boot: CellProcessStopActive FALSE -- no process stop from DB start values
PASS monitored reset clears the boot latch
PASS start edge: transport begins -- CellCycleRunning TRUE, command 0.150 m/s
PASS the beam breaks: ProductPresentAtSensor TRUE -- product travelled 1.38 m
PASS the belt really carried the product -- 1.38 m of ground-truth travel
PASS dwell at the beam: command 0.0 while running -- ~2 s stand-in transfer
PASS dwell done: return stroke at -0.15 m/s
PASS cycle completes at home -- belt position 0.042 m, command 0.000
PASS the belt is home -- |0.042| <= HOME_WINDOW
PASS process stop latches and overrides -- command zeroed, cycle down
PASS healing the contact resumes nothing -- the latch stands
PASS the monitored reset clears the latch
PASS no automatic resume -- starting again is the OTHER button (SPEC 6.4)
```

Time series: `evidence/m3-verify-20260821T225355Z.csv`. The bridge's own
per-session latency capture for the same run:
`evidence/latency-session-20260821T225342Z-pid61050.csv`.

## Warm-CPU re-run (robustness proof)

A second run against the same, un-restarted CPU (final state:
`evidence/m3-verify-20260821T230024Z.csv`, exit 0): the two boot lines
print SKIP (a warm CPU has no boot window), the exercise finds the belt
parked at 0.58 m from the previous run's process-stop test, drives the
SPEC §5 re-home branch to home (0.034 m) and then completes the full
measured cycle — including 1.34 m of ground-truth product travel.

Two defects were found and fixed in the exercise script itself during
bring-up (neither in the PLC model): a poll-for-idle that returned before
the start edge propagated, and panel presses that did not confirm the PLC
had seen the level (ROS discovery can eat the first publish). Both fixes
are in the committed `verify_cell.py`; the intermediate failing logs are
quoted in the session record, not here.

## What is NOT re-evidenced

The 46.163 ms latency figure and the four signal-loss cases remain
2026-07-28 measurements against PLCSIM Advanced (`plc/demo-cell/evidence/`,
`bridge/EVIDENCE_LATENCY.md`, `bridge/EVIDENCE_SIGNAL_LOSS.md`). Tonight's
path re-proves the **logic and the loop**, not the timing budget.
