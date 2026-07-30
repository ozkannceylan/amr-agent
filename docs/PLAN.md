# PLAN

## Current gate: M4 — Forklift commissioning cell (closing)

Agent-side work is complete (implementation and correction waves closed;
history in docs/reports/m4f-*). The gate closes on the owner's formal
showcase recording — T5.1-T5.6 per plc/forklift/SPEC.md §11 and the five
scenarios per sim/scenarios/forklift_commissioning.md, with T6 beside them
under the TWIN-DEMO-MAP naming discipline — followed by the m4f-09 verifier
run. Owner queue: docs/TODO.md.

## Restructure round m5r (ADR 0010, owner rulings 2026-07-30)

Gates after M4 are restructured forklift-first: M5 sensored autonomous
forklift (safety laser scanner into the F-blocks, lidar SLAM + Nav2
autonomy, HMI v2), M6 VDA 5050 fleet at scale (five loading and five
unloading stations, four forklifts, PLC-owned station handshake), M7 LLM
operations layer closing with the end-to-end demonstration. The arm gate is
removed; RB-KAIROS is retired (ADR 0002 platform selection superseded).

Open decisions (ADR 0010 D6, taken with the owner, never solo): the HMI
map-view data path (its own ADR at M5 briefing), the LLM attachment point
(M7 briefing), M6 internal structure (deep-research brief), anything beyond
the emergency-button process-stop reading.

Briefs, all closed 2026-07-30: m5r-01 ADR 0010 (166ffb3), m5r-02 roadmap
(517b0a4, AT numbers restored by ruling), m5r-03 CLAUDE.md §6 (324b5d7),
m5r-04 README + CREDITS (32ffb40, dependency-fixed CREDITS wording
accepted), m5r-05 safety docs (ae3441d, arm out of scope), m5r-06 plc docs
(a6aba59, two-gate row accepted), m5r-07 sim docs (ebd6bf6), m5r-08
interfaces docs (e864e5b). Beside the round: m4f-10 one-command stack
launcher (4d699cb, owner-requested; real bringup untested off-container).
m5r-09 verifier first ruled fail bounded to tracking reconciliation and
one brief-defect mapping (fixed-cell SF-08 briefed to M6 against ADR 0010
D7/SRS §4); after the SF-08 correction (ca767ac, 1ab9117) and the
reconciliation, the bounded re-check ruled **pass-with-findings** and the
round is closed 2026-07-30, residue queued in TODO.

## M5 — opens when M4 closes

The ADR 0009 early wave (F-program spec, safety mirrors, HMI safety lamps,
arena zone + T6 scenario — m5a-01..08, all closed) becomes M5's opening
wave. The M5 brief list is drafted with the owner after the m5r round
closes, starting from the map-data-path ADR and the per-sensor briefs.

M0 closed 2026-07-26, M1 2026-07-26, M2 2026-07-26, M3 2026-07-28.
Filename convention stands: a file's number names its round — the parked
m3-* navigation sim files now serve M5, m4-00-hermes-survey.* serves M7.
