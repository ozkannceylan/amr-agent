# PLAN

## M3 — Fixed equipment I/O loop: CLOSED 2026-07-28

Verified in docs/reports/m3-37-gate-verification.md, pass-with-findings: all
four exit criteria met as roadmap.md writes them; twelve findings, none
unmeeting an item; §11 T4 is not a 14/14 pass and no document claims it is.
The carried residue (T4.11/T4.11b, 4.9b's cold-start form, the findings
queue) lives in docs/TODO.md.

## Current gate: M4 — Forklift commissioning cell (ADR 0008)

Opened 2026-07-28. Criterion: the M4 row of docs/roadmap.md — five observable
behaviours through HMI → PLC standard program → bridge → Gazebo, plus the
recorded commissioning showcase naming every reaction as process logic. TIA
Portal and PLCSIM work is owner-executed; agents deliver everything up to the
live loop. No SRS function is implemented at this gate (ADR 0008 D3).

## Briefs to close M4

Contract wave, closed 2026-07-28: m4r2-01 ADR 0008 (ccd867e); m4r2-02 roadmap
renumber (3b86b1c); m4r2-03 CLAUDE.md + hmi bootstrap (2e6bf48). m4r2-04
public README gate order + m3-37 finding-12 residue: issued.

Implementation wave, dependency-ordered:

1. m4f-01 interface — forklift node group + signal table. In flight.
2. m4f-02 agv — in-house forklift SDF + vehicle nodes. In flight.
3. m4f-03 sim — commissioning arena + bringup. Opens when m4f-02 lands.
4. m4f-04 plc — plc/forklift/SPEC.md, owner-buildable. Opens when m4f-01 lands.
5. m4f-05 interface — bridge-design addendum, plus the two carried
   bridge-design rows. Opens when m4f-01 lands.
6. m4f-06 bridge — forklift slots proven on the test double. After m4f-05.
7. m4f-07 hmi — backend + UI against the double. Opens when m4f-06's double
   serves the forklift nodes (roster prerequisite closed by m4r2-03).
8. m4f-08 sim — scenario procedure + evidence checklist. After m4f-03/04/07.
9. m4f-09 verifier — gate verification, last, after the owner evidence.

m4f-01 and m4f-02 run in parallel on an orchestrator-fixed signal contract;
deltas reconcile via their reports (LESSONS 2026-07-27 contract-document rule,
accepted knowingly).

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
