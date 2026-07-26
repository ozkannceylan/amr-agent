brief:               docs/briefs/m1-04-verify.md
status:              done
verdict:             PASS (after one remediation round)
files_changed:       none (verifier is read only; filed by the orchestrator)
invariants_touched:  none

summary:
- Round 1: criteria 1, 2, 3, 5, 6 PASS; criterion 4 (cross-document
  consistency) FAIL — the m1-02 revision (DoorwayClear,
  ChargerVehicleDocked) was not reflected in handshake-tables.md §6/§7,
  and state.operatingMode / state.errors[] lacked owner rows.
- Remediation: commit a2d571d added the four §6 rows, marked §7 items
  resolved, re-anchored door step 8 to DoorwayClear; commit 72640db
  synced roadmap/TODO/LESSONS.
- Round 2: criterion 4 PASS — all 49 OPC nodes covered in the ownership
  map, 0 unresolved identifiers, no double ownership; tracking files
  consistent; git hygiene clean on both commits.

highlights of round 1 evidence:
- VDA 5050 doc pinned to tag 2.1.0 (commit 511d01d), verified live;
  30+ fields spot-checked against the official schemas, all traceable;
  omitted fields all real; connection loss mapped to degraded mode
  (invariant 2), never a safety path (invariant 1).
- OPC UA doc: 49 nodes, single owner each; exactly 11 fleet-writable
  request/handshake bits, zero actuator commands (invariant 6); PLC
  serves, fleet client (invariant 4); no fleet data on PLC (invariant 5).
- Handshakes: 35 step rows, no PLC↔AGV direct path (invariant 11);
  monitored restart, no auto-resume; levels not edges.

open_questions:
- Handshake timeouts are proposed defaults — confirm in M5.
- M6 PLC implementation must keep station tokens opaque (never parsed)
  or invariant 5 erodes in code. Carried to the M6 brief.

next_suggested:      Close M1, open M2 (safety requirements spec).
