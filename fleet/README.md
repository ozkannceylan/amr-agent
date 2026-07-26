# fleet

## This layer must not access

- Actuators, directly or indirectly. The fleet manager issues orders and reads state; it never commands a conveyor, door, charger or vehicle motor (invariant 6).
- ROS 2 internals: no topics, services, actions or Nav2 APIs. The only path to a vehicle is VDA 5050 over the MQTT broker (invariants 3, 11).
- The PLC as anything but an OPC UA server. The fleet manager is the OPC UA client; that direction is never inverted, and no custom PLC protocol is added (invariant 4).
- Safety functions. E-stop, protective stop and STO are onboard and in the F-CPU; the fleet layer carries process commands only, and losing this layer must only degrade, never endanger (invariants 1, 2).
- Custom message schemas replacing VDA 5050. Extensions live only in the standard's documented extension points (invariant 3).
- Hard real-time responsibilities. Deterministic timing stays in PLC logic or vehicle firmware, not in this Python service (invariant 9).
- Tailscale as a data path to the PLC or vehicles (invariant 8).

Owns: transport order assignment, traffic management, zone reservation, and the MQTT and OPC UA client connections.
