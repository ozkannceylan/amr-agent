# Roadmap

Current gate: M1 — not started.

M0 closed 2026-07-26, verified in docs/reports/m0-04-verify.md.

| Gate | Deliverable | Closes when |
|---|---|---|
| M0 | Repo skeleton, ADR 0001 recording the invariants | Structure exists, invariants committed |
| M1 | Interface contracts | VDA 5050 subset and OPC UA node model documented and reviewed |
| M2 | Safety requirements spec | Every safety function has a trigger, a reaction and an acceptance test |
| M3 | Simulated vehicle | Gazebo AGV localizes and navigates a warehouse world with Nav2 |
| M4 | VDA 5050 client | A stub publisher sends an order, the vehicle executes it and reports state |
| M5 | Fleet manager | Real service assigns orders to two vehicles, traffic conflicts avoided |
| M6 | PLC integration | PLC serves OPC UA, fleet manager subscribes, station handshake works end to end |
| M7 | Safety layer | F-CPU implements the spec, e-stop chain and zone monitoring verified against acceptance tests |
| M8 | Demonstration | Recorded end to end run, validation report, README with architecture narrative |

A gate closes only when its criterion is observable behavior, not written code.
