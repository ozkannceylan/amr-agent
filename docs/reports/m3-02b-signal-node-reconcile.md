brief:               docs/briefs/m3-02b-signal-node-reconcile.md

status:              done

files_changed:
  - docs/interfaces/opcua-nodes.md (section 9 reconciled; new 9.9 "Reconciliation
    with the sim signal table"; sections 1-8 still untouched)
  - docs/reports/m3-02b-signal-node-reconcile.md (this report)

invariants_touched:  none

what changed, and why:
  The m3-01 cell is analog where my draft assumed bits. Four of the seven PLC
  signals are Real, not Bool, so the node set changed materially:

  removed  ProductPresentAtSensor from the input image (the cell publishes a
           range, not a bit)
  removed  ConveyorMotorRunningFeedback (superseded by a real measured signal)
  removed  ConveyorRunCommand (the cell accepts a signed velocity, not a run bit)
  added    ConveyorBeltPosition, ConveyorBeltSpeed, ProductSensorRange (Real/Float)
  added    ConveyorSpeedCommand (Real/Float) as the single output
  renamed  PanelEmergencyStopCircuitClosed -> PanelProcessStopCircuitClosed
  moved    ProductPresentAtSensor to DemoCell/Status/ as the PLC's derived verdict

  Final set: 6 input nodes, 1 output node, 5 status nodes, 2 link nodes.

brief items, one by one:

  1. One node per signal. Section 9.9 is the two-way check: a table mapping all
     seven PLC signals to exactly one node each, plus a table of the seven nodes
     that have no cell signal with the reason each is legitimate (5 PLC-derived
     Status nodes, 2 Link nodes). No orphans in either direction. The sim's
     proposed names are superseded by the BrowseNames, which m3-01 open question 4
     assigned to this document.

  2. Photo-eye conversion: RAW RANGE GOES TO THE PLC; the PLC thresholds it. The
     bridge holds no threshold. Reasoning recorded in 9.3: the distance below
     which a product counts as present depends on product geometry, beam
     alignment and the hysteresis the process wants, which makes it a process
     decision rather than a unit conversion, and ADR 0004 puts process decisions
     in the PLC. A threshold constant in bridge config would also become a second
     owner of "product present" (invariant 10). Stated interface expectation for
     the PLC program: named constant at 1.00 m, midway between the measured
     1.440 m clear and 0.540 m blocked levels (~0.45 m margin either side),
     present when below; hysteresis and filter time are PLC content. The bridge's
     only numeric conversion anywhere is float64 -> S7 Real narrowing, units
     unchanged.

  3. Belt encoder decimation, stated in 9.2 as an interface expectation on the
     bridge, not on the cell: ~500 Hz source -> 20 Hz (50 ms) cyclic write, by
     LATEST-SAMPLE decimation only. No averaging, interpolation or min/max hold
     (a filter changes meaning), and nothing may be derived from the discarded
     samples (no edge counting, no travel integration). Photo-eye 30 Hz decimates
     the same way; panel contacts are on-change; ConveyorSpeedCommand is read at
     the same 20 Hz. Rationale for 20 Hz: roughly twice the intended PLC scan and
     far below the source rate, so M3's measured latency is dominated by the OPC
     UA path rather than by decimation. m3-04 may revise it with measurement.

  4. /cell/product_box/pose is excluded and now appears in 9.8 with m3-01's own
     reasoning (a real conveyor has no product-position transducer; modelling one
     would let the program cheat the demonstration). /clock is excluded with it.

  5. Process-stop naming aligned. The node is PanelProcessStopCircuitClosed; the
     word "emergency" now appears nowhere in section 9's tags, node names or
     headings (the 9.6 heading is "The red mushroom is a PROCESS stop"). NC
     polarity kept as accepted, and it matches the cell, which already publishes
     both stop contacts as NC contact state. 9.6 adds a Naming row recording that
     m3-01 open question 1 is confirmed: the ADR wording governs, the topic stays
     /cell/panel/process_stop, and no ADR revisit is needed.

  6. My open question 3 resolved: the sim DOES provide drive feedback, as
     ConveyorBeltSpeed (velocity[0], the measured read-back of the command).
     ConveyorMotorRunningFeedback is dropped in its favour. ConveyorDriveFault is
     kept and restated as the PLC's verdict on disagreement between
     ConveyorSpeedCommand and ConveyorBeltSpeed - both operands now exist as
     nodes, so it is derivable; tolerance and delay stay PLC content.

  also closed from m3-01: open question 5 (belt travel limits). No home or limit
  signal is added - the cell has no such transducer. ConveyorBeltPosition carries
  the raw travel and the +-2.50 m stop is a constant in the PLC program. Recorded
  in 9.3 and in the 9.8 absent list. Open question 2 (no retained initial value)
  is referenced in 9.2 as an m3-04 startup decision, not a node property.

open_questions:
  1. ConveyorSpeedCommand is a Real velocity, so the PLC's "cycle-running flag
     separate from actuator output" pattern (CLAUDE.md section 9, and the m3-05
     brief) now means the flag gates a setpoint rather than a coil. That is
     ordinary practice but m3-05 should state it explicitly, since a reader
     expecting a Bool output will look for a coil that does not exist.
  2. Node count grew to 14. If the owner wants the M3 watch table smaller, the
     candidates to drop are ConveyorDriveFault and CellResetRequired - both are
     PLC-derived and neither is needed to close any of ADR 0004's four items. I
     kept them because the gate's signal-loss item is easier to evidence with
     them present.
  3. S7 Real is 32-bit; ROS publishes float64. The narrowing is harmless at
     millimetre scale on a +-2.5 m axis, but if m3-04's latency instrumentation
     wants to timestamp or difference these values it should do so on the ROS
     side, before narrowing.
  4. sim/README.md's stale heading "Navigation scenario (M3)" (m3-01 open
     question 6) is still uncorrected. It is sim/'s file, not mine.

next_suggested:      m3-03 bridge design, whose signal map is now a direct derivation of section 9.9; it should also fix the startup values left open by m3-01 question 2.
