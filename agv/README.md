# agv

## This layer must not access

- Safety commands from the network. E-stop, protective stop and STO are implemented onboard (scanner, bumper, hardwired inhibit); no MQTT, OPC UA or VPN message may trigger or release a safety function (invariant 1).
- Network liveness as a safety condition. Loss of supervision is degraded mode: the onboard watchdog performs a controlled stop; safety must not depend on the connection (invariant 2).
- The fleet manager or PLC directly. The vehicle's only fleet-facing interface is the VDA 5050 client on the MQTT broker; no OPC UA, no direct service calls (invariants 4, 11).
- Fleet-level decisions: order assignment, traffic and zone reservation belong to the fleet manager; the vehicle executes orders and reports state (invariant 5).
- Custom schemas replacing VDA 5050 on the broker interface (invariant 3).
- Hard real-time control loops in Python nodes. Deterministic timing belongs in vehicle firmware (invariant 9).

Owns: the VDA 5050 client node, supervision watchdog, and the ROS 2 / Nav2 stack for localization, planning and obstacle avoidance.
