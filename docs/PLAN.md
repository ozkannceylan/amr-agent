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

## M0 addendum in progress (owner-directed, before M1 starts)

Platform decision: briefs m0-05 (ADR 0002, RB-KAIROS), m0-06 (roadmap
gate M9, arm integration), m0-07 (verifier). RB-KAIROS ROS 2 + Gazebo
feasibility confirmed from vendor sources before delegation.
