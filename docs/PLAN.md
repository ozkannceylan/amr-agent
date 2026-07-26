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

M0 addendum (platform decision) closed 2026-07-26: ADR 0002 records
RB-KAIROS, roadmap carries gate M9; verified in
docs/reports/m0-07-verify-platform.md. Open owner decision queued in
TODO.md: pin the ROS 2 distribution before M3.
