# PLAN

## M3 — Fixed equipment I/O loop: CLOSED 2026-07-28

Verified in docs/reports/m3-37-gate-verification.md, pass-with-findings: all
four exit criteria met as roadmap.md writes them; twelve findings, none
unmeeting an exit item; §11 T4 is not a 14/14 pass and no document claims it is.
The carried residue (T4.11/T4.11b, 4.9b's cold-start form, the findings
queue) lives in docs/TODO.md.

## Current gate: M4 — Forklift commissioning cell (ADR 0008)

Opened 2026-07-28. Criterion: the M4 row of docs/roadmap.md — five observable
behaviours through HMI → PLC standard program → bridge → Gazebo, plus the
recorded commissioning showcase naming every reaction as process logic. TIA
Portal and PLCSIM work is owner-executed; agents deliver everything up to the
live loop, including a full-loop rehearsal against a PLC logic double. No SRS
function is implemented at this gate (ADR 0008 D3).

## Briefs

Contract wave, all closed: m4r2-01 ADR 0008 (ccd867e); m4r2-02 roadmap
renumber (3b86b1c); m4r2-03 CLAUDE.md + hmi bootstrap (2e6bf48); m4r2-04
public README (9f7754c); m4r2-05 hmi area (577ca9a); m4r2-06 bridge and adr
areas (91ffe36).

Implementation wave:

1. m4f-01 interface — node group + signal table. Closed (d341fa8), with
   m4f-01b steer ruling (ae93667) and m4f-01c HMI shutdown/liveness rules
   (in flight).
2. m4f-02 agv — forklift SDF + vehicle nodes. Closed (03aa9e7), with m4f-02b
   scan-dropout contract note (bb7ce41).
3. m4f-03 sim — commissioning arena + bringup. Closed (48302a7).
4. m4f-04 plc — plc/forklift/SPEC.md. Closed (9c158ce), with m4f-04b prose
   alignment (4d5df6d), m4f-04c logic double (ceb8565) and m4f-04d T5.4
   procedure correction (6ff866c).
5. m4f-05 interface — bridge-design addendum. Closed (fc2e545), with m4f-05b
   (5797e17), m4f-05c (44e5fc3) and m4f-05d restart-residual sizing (8642228).
6. m4f-06 bridge — forklift slots proven on the double. Closed (71d3b76),
   with m4f-06b rehearsal config (22af207).
7. m4f-07 hmi — backend + UI. Closed (4804f5a): 40 checks against the bridge
   double, 33 against the PLC logic double, banner and metrics panel live.
8. m4f-08 sim — scenario procedure + full-loop rehearsal. In flight.
9. m4f-09 verifier — gate verification, last, after the owner evidence.

Two defects were caught by building the logic double rather than by review,
both in the owner's test procedure rather than in the program: T5.4 released
an edge-triggered reset and re-asserted it after the cause cleared (a fresh
edge the program correctly honours, so the step measured nothing), and the
same shape in the enable path at 5.4.9. Both corrected in 6ff866c before any
CPU run.

Owner queue for this gate: docs/TODO.md "owner — M4 queue", starting with the
m3-37 finding-9 cold-start capture at the first PLCSIM session.

## M5 — Safety layer on the fixed cell: NOT OPENED

Entry work carried unchanged from ADR 0007, re-attached by m4r2-02: the
F-CPU-on-PLCSIM tool question is owner work in TIA and feeds M5's first
brief. No M5 brief until it is answered.

M0 closed 2026-07-26 (m0-04/07/09), M1 2026-07-26 (m1-04), M2 2026-07-26
(m2-02), M3 2026-07-28 (m3-37). Filenames are kept as written:
m4-00-hermes-survey.* belongs to M12, m4r-* to the ADR 0007 round,
m4r2-*/m4f-* to this gate, the older m3-* sim files to M6.
