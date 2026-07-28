# Roadmap

Current gate: M4 — Safety layer on the fixed cell (F-CPU). Not yet opened: the
owner is continuing it in a later session, and ADR 0007 requires its first brief
to settle F-CPU-on-PLCSIM feasibility in the tool before any safety logic.

Gate order follows ADR 0007
(docs/adr/0007-safety-first-gate-order.md), which supersedes the gate order
of ADR 0004 (docs/adr/0004-gate-reordering-plc-loop-first.md): the
fixed-equipment Gazebo-to-PLC signal loop is proven first, then the safety
layer on that same cell, before any mobile robot, broker or fleet work. Arm
integration comes last and the Hermes command path is parked.

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
| M4 | Safety layer on the fixed cell (F-CPU) | AT-01, AT-07 and AT-08 of docs/safety/SRS.md pass on PLCSIM Advanced, each including its standard-program-in-STOP sub-case (B3); the same three reactions execute with the bridge stopped and the OPC UA session down, making invariant 1 observable rather than asserted; the `Safety/` mirrors are read-only and no client write can create, prevent or clear a safety reaction; and a **recorded cell + safety showcase** shows the cell running a transfer, an e-stop trip with its monitored reset, and a zone trip with its monitored reset, naming in the recording which reactions are F-CPU safety functions and which are process behaviour |
| M5 | Simulated vehicle | Gazebo AGV localizes and navigates a warehouse world with Nav2, **and** AT-02, AT-03 and AT-04 pass with the inhibit demonstrably acting below the navigation stack |
| M6 | VDA 5050 client | A stub publisher sends an order, the vehicle executes it and reports state, **and** AT-09 passes: broker killed, controlled stop within the watchdog period, order kept, and SF-03 still acting during the outage (B1, B2) |
| M7 | Fleet manager | Real service assigns orders to two vehicles, traffic conflicts avoided |
| M8 | PLC integration | PLC serves OPC UA, fleet manager subscribes, station handshake works end to end; the door and charger fixed equipment now exist, so AT-05 and AT-06 pass including their B3 sub-cases, and AT-07's coupled Gazebo scenario runs with a vehicle in the monitored zone; and a **recorded fleet showcase** shows orders, traffic and the station handshake in one run |
| M9 | Demonstration | Recorded end-to-end run, validation report, README with architecture narrative; the run shows B4 with both chains live (the cell e-stop does not stop a vehicle, the vehicle chain does not depend on the cell) and the cell operating normally with the fleet layer and all remote access unreachable |
| M10 | Arm integration | Arm motion is gated by a base-stationary interlock, arm work is carried as a VDA 5050 action, and the safety zone model distinguishes base and arm (SF-20…29) |
| M11 | Command path from Hermes — **parked, no priority** | Entry condition: the ten owner decisions in docs/reports/m4-00-hermes-survey.md are ruled, including the operator/HMI layer ADR that the §3 topology needs. Closes when a Telegram-triggered command reaches the PLC by the path those decisions choose, the commanded action is observed in Gazebo, Hermes never writes actuator outputs and never bypasses PLC interlocks, and the cell is shown operating normally with Hermes and its transport unreachable |

A gate closes only when its criterion is observable behavior, not written code.

Three recordings are embedded in gate criteria rather than deferred to the
end: the cell + safety showcase at M4, the fleet showcase at M8, the
end-to-end demonstration at M9. A phase gate does not close on an unrecorded
run, and M9 remains a gate in its own right rather than a compilation of the
earlier two.

The safety layer is not complete at M4. M4 delivers the cell-scope functions
the demonstration cell's equipment can carry (SF-01, SF-07, SF-08); SF-05 and
SF-06 complete at M8 and the vehicle chain at M5 and M6. ADR 0007 §2 holds the
per-function split and the boundary-statement landing points.

Renumbering from the ADR 0004 order — four rows moved: old M9 safety → M4,
old M10 demonstration → M9, old M11 arm → M10, old M4 Hermes → M11. M5 to M8
keep their numbers and contents. Existing brief and report filenames are kept
as written, so m4-00-hermes-survey.* belongs to what is now M11 and the older
m3-* sim files belong to M5.
