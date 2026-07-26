# plc

## This layer must not access

- Fleet management concerns: order assignment, traffic control, zone reservation. Those belong to the fleet manager (invariant 5).
- The MQTT broker or any VDA 5050 topic. The PLC talks to the fleet layer only as an OPC UA server; it never acts as an OPC UA or MQTT client (invariants 4, 11).
- ROS 2, Nav2 or any vehicle-internal interface. Vehicle coordination happens through handshakes exposed over OPC UA, never by direct calls (invariant 11).
- The network as a safety path. Safety functions live in the F-CPU program over PROFIsafe and onboard the vehicles; no e-stop, protective stop or STO signal may depend on MQTT, OPC UA or VPN (invariants 1, 2).
- Standard-program dependencies inside the safety program. The F-CPU logic must remain correct if the standard program halts or misbehaves (invariant 7).
- Tailscale or any engineering-access tunnel as an I/O or data path (invariant 8).

Owns: fixed equipment (conveyor, door, charger), interlocks, station handshakes, and the F-CPU safety program.
