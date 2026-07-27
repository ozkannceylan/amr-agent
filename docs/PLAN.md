# PLAN

## Current gate: M3 — Fixed equipment I/O loop (in progress)

Gate order follows ADR 0004. A Gazebo world of fixed equipment only
(conveyor, product sensor, operator panel equivalent), a bridge process
translating between Gazebo (ROS 2) and the PLC as an OPC UA client to the
S7-1500 OPC UA server on PLCSIM Advanced, and all control logic in the TIA
Portal program.

Exit criterion — all four demonstrated and recorded:

1. Gazebo sensor state visible as PLC input bits in a TIA watch table.
2. PLC output bits driving the Gazebo actuator, verified visually.
3. Latency and update rate measured and written down.
4. Signal-loss behaviour defined and tested: what the PLC sees when the
   bridge stops, and what the equipment does.

## Briefs to close M3

1. m3-01 sim — fixed-equipment Gazebo world (conveyor, product sensor,
   operator panel equivalent), no vehicle.
2. m3-02 interface — OPC UA node model extension for the demonstration
   cell's fixed-equipment I/O nodes.
3. m3-03 fleet — bridge design document, written and reviewed before any
   bridge code.
4. m3-04 fleet — bridge implementation against that design.
5. m3-05 plc — PLC program specification for the owner's TIA Portal
   implementation.
6. m3-06 verifier — verification scenario covering the four exit items.

The TIA Portal implementation and the PLCSIM Advanced run are owner-executed.
The four exit items are therefore demonstrated by the owner against the
delivered artifacts, not by an agent.

Filename note: existing brief and report filenames are kept as written. The
older m3-* sim briefs and reports (warehouse world, headless bringup,
navigation scenario) belong to what is now M5 — Simulated vehicle, despite
their m3 prefix.

M0–M2 closed 2026-07-26 (reports m0-04/07/09, m1-04, m2-02).
Session mode: owner-approved autonomous run; TIA Portal implementation and
the PLCSIM run remain with the owner.
