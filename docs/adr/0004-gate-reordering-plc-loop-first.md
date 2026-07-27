# ADR 0004: Gate reordering — prove the Gazebo-to-PLC loop first

Status:        accepted

Context:       The project's core claim is a closed signal loop between a
Gazebo simulation and a real S7-1500 program running on PLCSIM Advanced.
Every later layer — vehicle, VDA 5050 client, fleet manager, safety layer —
is built on top of that loop and assumes it works. The original gate order
placed three gates of mobile-robot work (simulated vehicle, VDA 5050 client,
fleet manager) ahead of the first PLC contact, so the claim on which
everything depends would have been tested last. Proving the loop first, with
no mobile robot involved, de-risks the architecture and makes every
subsequent gate a layer added to a demonstrated foundation rather than to an
assumption.

Decision:      The gates are reordered so that the fixed-equipment
Gazebo-to-PLC signal loop is proven before any mobile robot work, and the
bridge process becomes a first class component. The gate order is now:

1. M0 — Repo skeleton (closed)
2. M1 — Interface contracts (closed)
3. M2 — Safety requirements spec (closed)
4. M3 — Fixed equipment I/O loop
5. M4 — Command path from Hermes
6. M5 — Simulated vehicle
7. M6 — VDA 5050 client
8. M7 — Fleet manager
9. M8 — PLC/fleet integration
10. M9 — Safety layer
11. M10 — Demonstration
12. M11 — Arm integration (last)

M3 — Fixed equipment I/O loop. A Gazebo world containing fixed equipment
only (conveyor, product sensor, operator panel equivalent) and no vehicle,
plus a bridge process that translates between Gazebo (ROS 2) and the PLC,
acting as an OPC UA client to the S7-1500 OPC UA server on PLCSIM Advanced.
All control logic lives only in the TIA Portal program. The gate closes on
four demonstrated and recorded items: simulated sensor state visible as PLC
input bits in a TIA watch table; PLC output bits driving the Gazebo actuator;
measured end-to-end latency and update rate; and a defined, tested
signal-loss behaviour.

M4 — Command path from Hermes. A Hermes agent running on the same server
sends a command to the PLC over OPC UA, triggered from Telegram, and the
commanded action is observed in Gazebo. Hermes writes a command node and
reads state nodes. It never writes actuator outputs and never bypasses PLC
interlocks; the PLC decides whether a command is accepted.

Constraints that still hold and are unchanged by this reordering:

- Invariant 4 holds. The PLC is the OPC UA server. The bridge is a client and
  Hermes is a client. This direction is never inverted.
- The bridge is a signal translator only. No sequencing, no interlocks, no
  timers, no latching. If logic appears to be needed in the bridge, it
  belongs in the PLC (invariants 5 and 6).
- No safety function is carried over OPC UA (invariant 1). If the
  demonstration needs a stop button, it is a PROCESS stop implemented in the
  standard program, and it must be labelled as a process stop in every
  document, tag name and recording. It is not a safety function under
  docs/safety/SRS.md and must never be presented as one.

Consequences:
- Mobile robot, Nav2, VDA 5050 and fleet work are deferred to M5 onward. The
  verified warehouse world and headless bringup already produced in sim/ are
  retained; the navigation scenario is parked unverified under
  sim/scenarios/ with a DEFERRED.md stating its status.
- The bridge becomes a first class component with its own design document,
  written and reviewed before any bridge code is written.
- The M1 interface contracts remain valid. The OPC UA node model will gain
  fixed-equipment I/O nodes for the demonstration cell, added as an extension
  of the existing model rather than a replacement.
- Arm integration stays last, as ADR 0002 anticipated.
- The gate numbering in docs/roadmap.md, docs/PLAN.md and docs/TODO.md shifts;
  reports and briefs already written under the old numbering keep their
  filenames and refer to the old numbers.

Alternatives:
- Keep the original gate order — rejected: it defers the project's core claim
  behind three gates of vehicle work, so an architectural failure in the
  Gazebo-to-PLC path would surface at the point where the most work depends
  on it.
- Fold the bridge into the fleet manager — rejected: it violates the layer
  split. The fleet manager issues orders and reads state and never commands
  actuators (invariant 6); a signal-level I/O translator inside it would
  merge two responsibilities and break the single-owner rule (invariant 10).
- Prove the loop against a mocked PLC only — rejected: a mock demonstrates the
  bridge, not the claim. Scan-cycle timing, OPC UA server behaviour on the
  S7-1500 and signal-loss handling are exactly what the gate exists to
  measure, and a mock reproduces none of them.
