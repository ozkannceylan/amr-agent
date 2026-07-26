# ADR 0001: Architecture invariants

Status:        accepted

Context:       This project is a multi-layer safety-critical system — safety, PLC control, fleet management and vehicle autonomy — built as an engineering portfolio project. In such a system the expensive failure mode is not a bug in one layer but a misplaced responsibility across layers: fleet logic drifting into the PLC, safety depending on the network, a convenience call cutting across a boundary. Once code exists, boundaries erode silently. The layer boundaries therefore had to be locked before any code was written, in a form that every session and every agent reads first and that can only change through an explicit, owner-approved decision.

Decision:      The following thirteen invariants are locked. Changing any of them requires a new ADR authored and approved by the owner before any code changes.

1. Safety never traverses the network. Emergency stop, protective stop and safe torque off are implemented onboard the vehicle and in the F-CPU. MQTT, OPC UA and VPN carry process commands only.
2. Loss of network is not a safety event. It is a degraded mode. Each vehicle runs a watchdog and performs a controlled stop when supervision is lost.
3. The fleet interface contract is VDA 5050. No custom schema replaces it. Extensions are allowed only as documented additions inside the standard's extension points.
4. The PLC is an OPC UA server. The fleet manager is the client. This direction is never inverted.
5. The PLC does not manage the fleet. It owns fixed equipment, interlocks and handshakes. Order assignment, traffic and zone reservation belong to the fleet manager.
6. The fleet manager never commands actuators directly. It issues orders and reads state.
7. Standard program and safety program are independent. The safety program must remain correct if the standard program halts or misbehaves.
8. Tailscale is engineering access only. It is not a data path for cell traffic. It is never placed between the PLC and the fleet manager in a diagram or a config.
9. Hard real time work stays out of Python. Anything with a deterministic timing requirement lives in PLC logic or vehicle firmware.
10. Single source of truth per data item. Every shared value has exactly one owner, documented in docs/interfaces/. Consumers never recompute it locally.
11. Layers talk only to adjacent layers as drawn in the topology in CLAUDE.md section 3. No shortcuts, no direct calls from the fleet manager into ROS 2 internals.
12. Simulation is Gazebo. MuJoCo is not used in this project.
13. No secrets in the repository. Credentials, certificates and tailnet keys live outside version control.

Consequences:

Harder:
- Convenience shortcuts between layers are ruled out, even when they would save a sprint: no fleet logic in the PLC, no safety signals over MQTT or OPC UA, no fleet manager reaching into ROS 2 internals.
- Every boundary change costs an ADR and owner approval; there is no fast path.
- Each shared value must have a documented single owner before it is used, which front-loads interface work.
- Timing-sensitive features cannot be prototyped in Python; they must go to the PLC or firmware from the start.

Easier:
- Each layer is testable in isolation, because its dependencies are limited to adjacent layers over documented interfaces.
- The safety argument stands on its own: it never depends on network behavior, the standard program or the fleet manager.
- Standard interfaces (VDA 5050, OPC UA) make components replaceable — a different fleet manager or vehicle can be swapped in without renegotiating the contract.
- Reviews and verification are cheap: an agent checks a change against thirteen written rules instead of reconstructing intent.

Alternatives:

- MuJoCo instead of Gazebo. Rejected: the project targets the ROS 2 / Nav2 ecosystem, where Gazebo is the integrated, demonstrable path; a second simulator adds surface without adding to the architecture argument (invariant 12).
- A custom fleet schema instead of VDA 5050. Rejected: a custom schema would be easier to bend to the code but would make the fleet interface non-standard and the components non-replaceable; VDA 5050 is the industry contract and its extension points cover legitimate additions (invariant 3).
- PLC as OPC UA client, fleet manager as server. Rejected: it inverts ownership — the PLC would depend on the availability of a supervisory service, and the fixed-equipment layer must not depend on the fleet layer (invariant 4).
- PLC-managed fleet dispatch. Rejected: it mixes deterministic equipment control with scheduling and traffic logic in one program, making both harder to change and impossible to test in isolation (invariant 5).
- Treating network loss as a safety event, or carrying safety functions over the network. Rejected: it would make the safety case depend on network availability and latency; safety must be onboard and in the F-CPU, with network loss handled as a supervised degraded mode (invariants 1 and 2).
- Tailscale as a cell data path. Rejected: it would place an engineering-access overlay in the process data path between PLC and fleet manager, coupling cell operation to a remote-access tool (invariant 8).
