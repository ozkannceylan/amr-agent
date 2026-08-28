# docs

The repo's records, in four kinds:

| Where | What | Status |
|---|---|---|
| [`adr/`](adr/) | Architecture decision records 0001–0017 — the permanent spine, every era | live |
| [`interfaces/`](interfaces/) | VDA 5050 subset, OPC UA node model, handshake tables, bridge design | live |
| [`safety/`](safety/) | Safety requirements spec and validation reports | live |
| [`VALIDATION-M5.md`](VALIDATION-M5.md) | M5 chain validation, measured against F-signature `29FD2C52` | live evidence |
| [`LESSONS.md`](LESSONS.md) | Append-only corrections/dead-ends/surprises corpus | live, append-only |
| [`claude-supervised-m5/`](claude-supervised-m5/) | The first M5's own runbook — the layered stack, still runnable | reference |
| [`superpowers/`](superpowers/) | Specs and implementation plans of the current-system build | reference |
| [`archive/`](archive/) | The claude-supervised era's PLAN, TODO, roadmap, briefs, reports — frozen history | archived |

Current status and the roadmap live in the root [README](../README.md);
how to run the current system lives in the root [RUNBOOK](../RUNBOOK.md).

## This layer must not access

- Secrets of any kind: credentials, certificates, tailnet keys, broker passwords. These live outside version control (invariant 13).
- Application code. Documents here describe contracts and decisions; implementations live in the code trees.
- Custom fleet interface schemas. Interface documents describe the VDA 5050 subset and its documented extension points only (invariant 3).
- Topology shortcuts. No diagram or interface table may show Tailscale as a cell data path, the PLC as an OPC UA client, or the fleet manager talking directly to ROS 2 or actuators (invariants 4, 6, 8, 11).
