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
