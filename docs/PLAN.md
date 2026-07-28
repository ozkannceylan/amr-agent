# PLAN

## M3 — Fixed equipment I/O loop: CLOSED 2026-07-28

Verified in `docs/reports/m3-37-gate-verification.md`, **pass-with-findings**.
All four exit criteria met as `docs/roadmap.md` writes them. Twelve findings
recorded; none unmeets an exit item. The gate did **not** close on
`plc/demo-cell/SPEC.md` §11's step list and was not asked to: §11 T4 is not a
14/14 pass, and no document claims it is.

What the gate rests on:

| Item | Met by |
|---|---|
| (a) Gazebo sensor state visible as PLC input bits in a TIA watch table | `plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 135105.png`, provenance closed by the `171656`/`171727` pair |
| (b) PLC output bits drive the Gazebo actuator, verified visually | `assets/plc-drives-cell.gif`, with causality from §B2.5/§B2.6a and `ConveyorSpeedCommand` at access level RD (no client can write it) |
| (c) Latency and update rate measured and written down | `bridge/EVIDENCE_LATENCY.md` Sections A–C; 14 244 cycles at 20.00 Hz, one sized overrun, full statistics for all seven inputs, CPU cycle 1.004/1.023/2.556 ms |
| (d) Signal-loss behaviour defined and tested | `bridge/EVIDENCE_SIGNAL_LOSS.md` with §8 as the definition; cases A, B, C in both bridge states, D(i) and D(ii) at 2.301 s inside the specified [2.1, 3.2] s, no-auto-resume proven four times |

The gate was demonstrated across several program builds in one day and the
verifier ruled that assembly legitimate: every figure names its build, no
figure was amended, and all five steps the §6.8 correction affected were
**re-run** against the corrected build rather than reasoned across.

## M4 — Safety layer on the fixed cell (F-CPU): NOT OPENED

The owner is continuing M4 in a later session. **No M4 brief has been issued
and none should be inferred from this file.** Its criterion is the M4 row of
`docs/roadmap.md`; ADR 0007 §2 holds the per-function cell/vehicle split
(SF-01, SF-07, SF-08 at M4; SF-05 and SF-06 at M8; the vehicle chain at M5/M6).

Entry work, in order:

1. **The tool question, ADR 0007's own precondition** — does this install run
   an F-CPU on PLCSIM Advanced V7? STEP 7 Safety Advanced V21 licence, a
   1513F-1 PN addable from the catalogue, an empty F-project reaching RUN with
   its F-runtime group executing, and what F-I/O the catalogue offers. Owner
   work in TIA; the answers are the input to the first brief, not something a
   document may assume (the phase-0 lesson).
2. Only then the first M4 brief.

Three verifier findings (1, 2, 9) name watch-table readings that belong at the
head of M4's owner queue, because M4 performs CPU restarts anyway: **one
capture at a CPU cold start with the bridge down**, showing all seven Group 1
inputs at their DB start values, closes findings 1, 2, 8 and 9 at once.

## Carried out of M3, none blocking

- `plc/demo-cell/SPEC.md` §11 T4.11 needs its reaction path re-recorded with a
  per-session CSV (the facility now exists), and **T4.11b is blocked** on the
  bridge fault-injection facility of §12 item 6, which does not exist. Both
  concern belt-feedback plausibility — a defence added during the gate, absent
  from all four exit criteria.
- §11 4.9b's CPU-cold-start form has not run. Its bridge-restart form — the
  form item (d)'s own sentence names — passed with 28.202 s of refusal.
- The remaining queue is `docs/TODO.md`.

M0 closed 2026-07-26 (m0-04/07/09), M1 2026-07-26 (m1-04), M2 2026-07-26
(m2-02), M3 2026-07-28 (m3-37). Brief and report filenames are kept as
written: `m4-00-hermes-survey.*` belongs to what is now M11, and the older
`m3-*` sim files belong to M5.
