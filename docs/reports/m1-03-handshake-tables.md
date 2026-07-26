brief:               docs/briefs/m1-03-handshake-tables.md
status:              done
files_changed:       [docs/interfaces/handshake-tables.md]
invariants_touched:  none
open_questions:
  - Door sequence assumes PLC-side doorway clearance detection; m1-02 defines
    no such sensor or node. Listed as addition 1 in the deliverable's section 7
    (recommend read-only DoorwayClear status node). Needs an m1-02 revision or
    an explicit "PLC-internal, not exposed" statement before M6/M7 build on it.
  - Optional ChargerVehicleDocked status node (addition 2) — diagnostic only,
    owner's call whether to add it to m1-02.
  - Timeout values in the tables are proposed defaults; concrete constants are
    fleet-layer configuration and should be confirmed when the fleet manager
    is specified (M5).
next_suggested:      Revise m1-02 to resolve addition 1 (door clearance), then M1 review of all three interface documents together.

revision 1 (2026-07-26, per M1 review):
  - §6 map: added rows for Door/DoorwayClear and Charger/ChargerVehicleDocked
    (owner PLC, consumer fleet manager, diagnostic/status), now that m1-02
    defines both; removed the superseded "PLC-internal, not exposed" docking
    row so no item appears twice.
  - §6 map: added explicit rows for VDA state.operatingMode and state.errors[]
    (owner AGV, consumer fleet manager).
  - §7 items 1 and 2 marked resolved against the revised m1-02.
  - Door table step 8 now references DoorwayClear directly.
  - First two open_questions above are thereby closed; the timeout-constants
    question remains open for M5.
