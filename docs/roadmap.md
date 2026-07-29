# Roadmap

Current gate: M4 — Forklift commissioning cell (ADR 0008).

M4 remains the current gate with its criteria unchanged. M5's cell-scope
functions (SF-01, SF-08, SF-07 pattern) are opened early on the forklift twin
per ADR 0009 (docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md,
accepted), under its fallback rule.

M5, the safety layer, keeps the entry condition ADR 0007 set for it: its first
brief settles F-CPU-on-PLCSIM feasibility in the tool before any safety logic is
written.

Gate order follows ADR 0008
(docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md), which inserts the
forklift commissioning cell ahead of the safety layer and shifts every gate
above M3 by one. It does not supersede ADR 0007
(docs/adr/0007-safety-first-gate-order.md), whose order it extends and which in
turn supersedes the gate order of ADR 0004
(docs/adr/0004-gate-reordering-plc-loop-first.md): the fixed-equipment
Gazebo-to-PLC signal loop is proven first, then the same cell gains a
teleoperated forklift plant, then the safety layer on that cell, before any
mobile robot, broker or fleet work. Arm integration comes last and the Hermes
command path is parked.

M0 closed 2026-07-26, verified in docs/reports/m0-04-verify.md.
M1 closed 2026-07-26, verified in docs/reports/m1-04-verify.md.
M2 closed 2026-07-26, verified in docs/reports/m2-02-verify.md.
M3 closed 2026-07-28, verified in docs/reports/m3-37-gate-verification.md (pass-with-findings).

| Gate | Deliverable | Closes when |
|---|---|---|
| M0 | Repo skeleton, ADR 0001 recording the invariants | Structure exists, invariants committed |
| M1 | Interface contracts | VDA 5050 subset and OPC UA node model documented and reviewed |
| M2 | Safety requirements spec | Every safety function has a trigger, a reaction and an acceptance test |
| M3 | Fixed equipment I/O loop | All four are demonstrated and recorded: (a) Gazebo sensor state is visible as PLC input bits in a TIA watch table, (b) PLC output bits drive the Gazebo actuator, verified visually, (c) latency and update rate are measured and written down, (d) signal-loss behaviour is defined and tested — what the PLC sees when the bridge stops, and what the equipment does |
| M4 | Forklift commissioning cell | An operator drives the in-house forklift model in Gazebo from the commissioning HMI, every command passing HMI → PLC standard program → bridge → simulation and every state report returning simulation → bridge → PLC: (a) teleoperated drive with the PLC forming all motion setpoints, (b) the fork raised to a commanded height and stopped by the PLC's soft travel limits, (c) traction speed capped by the PLC while the fork is above its height threshold, (d) an obstacle entering the lidar stop zone latching a PLC process stop that overrides teleop, cleared only by the edge-triggered monitored reset after the zone clears, (e) loss of the HMI heartbeat zeroing all motion setpoints within the watchdog period; and a **recorded commissioning showcase** demonstrates (a)–(e), naming each reaction as standard-program process logic, not a safety function |
| M5 | Safety layer on the fixed cell (F-CPU) | AT-01, AT-07 and AT-08 of docs/safety/SRS.md pass on PLCSIM Advanced, each including its standard-program-in-STOP sub-case (B3); the same three reactions execute with the bridge stopped and the OPC UA session down, making invariant 1 observable rather than asserted; the `Safety/` mirrors are read-only and no client write can create, prevent or clear a safety reaction; and a **recorded cell + safety showcase** shows the cell running a transfer, an e-stop trip with its monitored reset, and a zone trip with its monitored reset, naming in the recording which reactions are F-CPU safety functions and which are process behaviour |
| M6 | Simulated vehicle | Gazebo AGV localizes and navigates a warehouse world with Nav2, **and** AT-02, AT-03 and AT-04 pass with the inhibit demonstrably acting below the navigation stack |
| M7 | VDA 5050 client | A stub publisher sends an order, the vehicle executes it and reports state, **and** AT-09 passes: broker killed, controlled stop within the watchdog period, order kept, and SF-03 still acting during the outage (B1, B2) |
| M8 | Fleet manager | Real service assigns orders to two vehicles, traffic conflicts avoided |
| M9 | PLC integration | PLC serves OPC UA, fleet manager subscribes, station handshake works end to end; the door and charger fixed equipment now exist, so AT-05 and AT-06 pass including their B3 sub-cases, and AT-07's coupled Gazebo scenario runs with a vehicle in the monitored zone; and a **recorded fleet showcase** shows orders, traffic and the station handshake in one run |
| M10 | Demonstration | Recorded end-to-end run, validation report, README with architecture narrative; the run shows B4 with both chains live (the cell e-stop does not stop a vehicle, the vehicle chain does not depend on the cell) and the cell operating normally with the fleet layer and all remote access unreachable |
| M11 | Arm integration | Arm motion is gated by a base-stationary interlock, arm work is carried as a VDA 5050 action, and the safety zone model distinguishes base and arm (SF-20…29) |
| M12 | Command path from Hermes — **parked, no priority** | Entry condition: the ten owner decisions in docs/reports/m4-00-hermes-survey.md are ruled, including the operator/HMI layer ADR that the §3 topology needs. Closes when a Telegram-triggered command reaches the PLC by the path those decisions choose, the commanded action is observed in Gazebo, Hermes never writes actuator outputs and never bypasses PLC interlocks, and the cell is shown operating normally with Hermes and its transport unreachable |

A gate closes only when its criterion is observable behavior, not written code.

Four recordings are embedded in gate criteria rather than deferred to the end:
the commissioning showcase at M4, the cell + safety showcase at M5, the fleet
showcase at M9, the end-to-end demonstration at M10. A phase gate does not close
on an unrecorded run, and M10 remains a gate in its own right rather than a
compilation of the earlier three.

The safety layer is not complete at M5. M5 delivers the cell-scope functions
the demonstration cell's equipment can carry (SF-01, SF-07, SF-08); SF-05 and
SF-06 complete at M9 and the vehicle chain at M6 and M7. ADR 0007 §2 holds the
per-function split and the boundary-statement landing points, each one gate
number higher under the shift below.

Renumbering, two rounds. From the ADR 0004 order, ADR 0007 moved four rows:
old M9 safety → M4, old M10 demonstration → M9, old M11 arm → M10, old M4
Hermes → M11; M5 to M8 kept their numbers and contents. ADR 0008 then inserted
the forklift commissioning cell as a new M4 and moved every gate above M3 by
one: safety → M5, simulated vehicle → M6, VDA 5050 client → M7, fleet manager →
M8, PLC integration → M9, demonstration → M10, arm → M11, Hermes → M12, still
parked and still last. M0 to M3 are unchanged in both rounds.

Existing brief and report filenames are kept as written, so a filename's number
names the round it was written under rather than the gate it now serves:
m4-00-hermes-survey.* belongs to what is now M12, the m4r-* files belong to the
ADR 0007 round, the m4r2-* and m4f-* files belong to the new M4, and the older
m3-* sim files — the warehouse world, the headless bringup and the navigation
scenario — belong to M6.
