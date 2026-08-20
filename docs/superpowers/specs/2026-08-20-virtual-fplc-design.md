---
title: Virtual F-PLC — step5 --virtual mode
date: 2026-08-20
status: approved
---

# Virtual F-PLC: `--virtual` runs step5 without PLCSIM Advanced

## Purpose

The S7-PLCSIM Advanced trial has expired. Step 5 — the repo's current final
system — must keep running with the safety chain active so M6 can proceed on
this rig. `--virtual` on the sole writer replaces the PLCSIM Advanced API with
an in-process behavioural model of the validated F-PLC program. Without the
flag, behaviour is byte-identical to today.

This is a **behavioural model, not the F-program**. It reproduces the
responses measured live and recorded in `m5_ver2/CLAUDE.md` §3.2 and the step
PROOFs. Every artefact it touches says so.

## Non-goals

- No change to the TIA project, its archive, tags or addresses.
- No change to steps 1–4 (frozen copies), the WSL side, or the 5100/5101
  payloads. The WSL side must be unable to tell the difference.
- No claim of safety integrity. The model is a test rig.

## Architecture

| File | Change |
|---|---|
| `m5_ver2/step5/windows/virtual_fplc.py` | **New.** `VirtualFPLC` class duck-typing the five API methods used: `WriteBool`, `WriteInt16`, `ReadBool`, `ReadInt16`, plus no-op `UpdateTagList`. Under 150 lines. |
| `m5_ver2/step5/windows/step5.py` | `--virtual` in `sys.argv` → `connect_plc()` returns `VirtualFPLC()` and never touches the Siemens DLL. Panel title gains `VIRTUAL F-PLC (model)`. No other line of the loop, panel or fail-safe `finally` changes. |
| `m5_ver2/step5/tests/test_virtual_fplc.py` | **New.** Unit tests for the model (list below). |
| `m5_ver2/step5/README_step5.md` | `--virtual` usage line. |
| `m5_ver2/step5/CONTEXT.md` | Short note so a Step 6 reader knows the rig exists and what it is. |

The single-writer rule holds: the model lives inside the sole writer's
process; nothing else gains PLC access.

## Model semantics

Input tags store what is written; reading an input returns the stored value
(the process image, as in PLCSIM). Outputs are computed from the model state.

**Five ESTOP1 instances** — e-stop button, back PF, right PF, left PF
(right/left PF latching `Motor` is measured, step5 PROOF rounds 2–3), and the
encoder/speed monitor. Semantics per instance:

- A demand (input unhealthy) **latches**. The input returning healthy does
  not re-enable.
- Re-enable requires a rising edge on `Acknowledge` while the input is
  healthy. One edge clears every latch whose input is currently healthy
  (measured: one ack cleared all latches after a stack bounce).
- `ACK_NEC=true`: all instances start latched; one ack after startup is
  required before `Motor` can ever be True.
- `Motor` = AND of the five enables.

**Encoder/speed monitor demand** when any of:

- `|ENC_A − ENC_B| > 50` (cross-check, measured),
- either channel's magnitude `> 2800` mm/s (ceiling, documented),
- either channel's magnitude `> V_Limit` (the step3-measured chain: WF drops → 300 →
  driving above 300 demands a stop).

The dead-link write `0/3000` therefore trips by two routes, as live.

**`V_Limit`** — owner ruling 2026-08-20: `300` if **any** of the three
`WF_Clear*` inputs is False, else `1500`. The live composition with the
right/left warning fields is contradictory and unresolved TIA-side (step5
PROOF item 4); the model takes the conservative envelope so any model error
is toward slower. Recorded here as a ruling, not a measurement.

**Case bits** — fixed at monitoring case 1 (`CASE_B0=True`, `CASE_B1=False`),
matching every live step5 run. The vehicle's unknown-case→case-3 fallback is
vehicle-side and already proven; the model does not exercise it.

**Timing** — the model responds synchronously within the writer's 20 ms
cycle: faster than the real F-cycle, inside every measured budget, and any
error is in the safe direction (earlier trip).

## Error handling

`--virtual` skips `CreateInterface`, so the error `-4` exit path never
applies. Every other failure — exception, window close — leaves through the
unchanged `finally`, which writes E-Stop and all six scanner inputs False
against the model exactly as against PLCSIM.

## Testing

`test_virtual_fplc.py`, pure Python, runs on WSL or Windows:

1. Startup: all latched, `Motor` False until first ack with healthy inputs.
2. Each of the five demand paths trips `Motor` and stays tripped after the
   input heals.
3. One `Acknowledge` edge clears all healthy latches; an unhealthy input's
   latch survives the ack.
4. Encoder: cross-check `>50`, ceiling `>2800`, over-`V_Limit`, and the
   `0/3000` dead-link picture.
5. `V_Limit` any-WF rule and the fixed case bits.

Existing `tests/test_step5.py` (pure functions) is untouched and must still
pass. Live check: `step5.py --virtual` against the running WSL stack —
Motor enable after ack, a scanner trip, and an autonomous leg.

## Fidelity ledger

| Behaviour | Basis |
|---|---|
| Latching, single-ack-clears-all, startup ack | Measured (PROOFs, CLAUDE.md §3.2) |
| Right/left PF latch Motor | Measured (step5 PROOF rounds 2–3) |
| Back-WF 1500/300, speed-monitor stop above V_Limit | Measured (step3 PROOF) |
| Cross-check 50, ceiling 2800 | Documented (CLAUDE.md §3.2) |
| Either-channel comparison shape | Inferred (conservative) |
| Any-WF → 300 composition | Owner ruling 2026-08-20 (conservative; live data contradictory) |
| Fixed case 1 | Owner default 2026-08-20 (matches every live run) |
