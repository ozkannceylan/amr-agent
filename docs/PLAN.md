# PLAN

## Current gate: M1 — Interface contracts (in progress)

Exit criterion: VDA 5050 subset and OPC UA node model documented in
docs/interfaces/ and reviewed (verifier pass), every shared data item
with exactly one owner (invariant 10).

## Briefs to close M1

1. m1-01 interface — docs/interfaces/vda5050-subset.md (message subset
   traceable to the official VDA 5050 v2 schema).
2. m1-02 interface — docs/interfaces/opcua-nodes.md (node model
   mirroring PLC tag names).
3. m1-03 interface — docs/interfaces/handshake-tables.md (station
   handshakes + single-owner data map; depends on 01 and 02).
4. m1-04 verifier — read-only review of all three.

Session mode: owner-approved autonomous run through the gates; only
TIA Portal implementation remains with the owner at the end.
