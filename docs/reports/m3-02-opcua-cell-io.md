brief:               docs/briefs/m3-02-opcua-cell-io.md

status:              done

files_changed:
  - docs/interfaces/opcua-nodes.md (new section 9, "Demonstration cell I/O (M3)"; sections 1-8 untouched)
  - docs/reports/m3-02-opcua-cell-io.md (this report)

invariants_touched:  none

summary:
  Section 9 adds the M3 demonstration cell under a new `DemoCell/` folder on the
  existing server and namespace URI, kept strictly separate from the M1 cell model
  in sections 3-7 (no node shared, no renumbering, no edit to existing tables).

  9.1  Direction rule restated for the bridge: PLC is the server, the bridge is a
       client (invariant 4); the bridge writes ONLY `DemoCell/Input/` nodes and
       `DemoCell/Link/BridgeHeartbeat`, never an actuator output (invariant 6);
       single owner per bit (invariant 10); no logic in the bridge (ADR 0004).
  9.3  Cell -> PLC input image, 5 nodes: ProductPresentAtSensor,
       ConveyorMotorRunningFeedback, PanelStartPressed, PanelStopCircuitClosed,
       PanelEmergencyStopCircuitClosed.
  9.4  PLC -> cell output, 1 node: ConveyorRunCommand, client-read-only.
  9.5  PLC status read-only: CellCycleRunning, CellProcessStopActive,
       CellResetRequired, ConveyorDriveFault.
  9.6  The demonstration E-stop is labelled a PROCESS stop in the standard
       program, explicitly not a safety function, with a note that SRS SF-01 is
       unaffected and never travels over OPC UA.
  9.7  Liveness pair: BridgeHeartbeat (bridge-written) and BridgeLinkOk
       (PLC-owned verdict). Node meaning only - the staleness criterion and the
       equipment reaction are stated as PLC program content for plc/demo-cell/SPEC.md.
  9.8  Deliberately absent list for the demo cell.

  No logic, sequencing, latching or timer appears in the node model. No node in
  the section is client-writable except the input image and the heartbeat.

open_questions:
  1. The m3-01 sim signal table does not exist yet - sim/README.md still describes
     the warehouse/nav work and has no cell I/O table, and there is no report for
     m3-01-fixed-equipment-world. The node set in section 9 was therefore designed
     from the equipment description in ADR 0004 and the m3-01 brief. It MUST be
     diffed against the sim signal table once m3-01 lands; a follow-up brief (or a
     verifier check) should confirm one node per sim signal and no orphans.
  2. Stop-device naming deviates from the names suggested in the brief. The brief
     proposed PanelStopPressed / PanelEmergencyStopPressed; the section uses
     PanelStopCircuitClosed / PanelEmergencyStopCircuitClosed because CLAUDE.md
     section 9 ("wire NC, program NO") is binding and a "...Pressed" polarity makes
     an absent or dead signal read as healthy. If the owner prefers the "Pressed"
     names, that is a naming decision with a polarity consequence and needs an
     explicit call, because plc/demo-cell/SPEC.md and the bridge must mirror
     whichever is chosen exactly.
  3. ConveyorMotorRunningFeedback is conditional: it is specified as omitted rather
     than synthesized if the m3-01 world publishes no drive feedback. Confirm with
     m3-01 which is the case, since ConveyorDriveFault (9.5) depends on it.
  4. Section 2's folder-layout block was deliberately not edited (it is an M1
     section). The DemoCell folders are listed in 9.2 instead. If the owner would
     rather have one consolidated layout block, that is a small edit to section 2
     that I did not take on my own.

next_suggested:      Issue m3-01 (sim) if not already running, then diff its signal table against section 9 before m3-03 (bridge design) consumes either.
