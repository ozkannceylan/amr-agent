# docs

## This layer must not access

- Secrets of any kind: credentials, certificates, tailnet keys, broker passwords. These live outside version control (invariant 13).
- Application code. Documents here describe contracts and decisions; implementations live in plc/, fleet/, agv/, sim/.
- Custom fleet interface schemas. Interface documents describe the VDA 5050 subset and its documented extension points only (invariant 3).
- Topology shortcuts. No diagram or interface table may show Tailscale as a cell data path, the PLC as an OPC UA client, or the fleet manager talking directly to ROS 2 or actuators (invariants 4, 6, 8, 11).

Owns: ADRs, safety spec, interface contracts, briefs, reports, roadmap and session tracking files — the single source of truth for every shared data item.
