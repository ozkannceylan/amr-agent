# PLAN

## Current gate: M1 — Interface contracts (not started)

Exit criterion: the VDA 5050 message subset and the OPC UA node model are
documented in docs/interfaces/ and reviewed, with every shared data item
assigned exactly one owner (invariant 10), and the verifier has passed.

## Briefs to close M1

Not yet issued. To be defined with the owner at the start of the M1
session; expected shape, subject to owner approval:

1. interface — VDA 5050 message subset (order, state, instantActions).
2. interface — OPC UA node model mirroring PLC tag names.
3. interface — station handshake tables with single-owner data map.
4. verifier — read-only check of the M1 exit criterion.

M0 closed 2026-07-26; see docs/reports/m0-04-verify.md.

M0 addenda closed 2026-07-26: ADR 0002 (RB-KAIROS platform), roadmap
gate M9, ADR 0003 (ROS 2 Jazzy + Gazebo Harmonic, vendor branches
verified and SHA-pinned), arch-docs agent added to the roster. Verified
in docs/reports/m0-07 and m0-09.
