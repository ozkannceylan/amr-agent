# sim

## This layer must not access

- MuJoCo. Simulation is Gazebo only (invariant 12).
- Production logic. Worlds, launch files and scenarios exercise the stack; they must not reimplement fleet, PLC or safety behavior, and simulated safety shortcuts must not leak into agv/, fleet/ or plc/ (invariants 7, 11).
- Layer bypasses. Test scenarios drive the system through its real interfaces (VDA 5050 topics, OPC UA nodes), never by injecting state directly into another layer's internals (invariant 11).
- Secrets. Simulation configs carry no credentials, certificates or tailnet keys (invariant 13).

Owns: Gazebo warehouse worlds, launch files, and end-to-end test scenarios.
