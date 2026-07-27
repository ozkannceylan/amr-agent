# Roadmap

Current gate: M3 — in progress.

Gate order follows ADR 0004
(docs/adr/0004-gate-reordering-plc-loop-first.md): the fixed-equipment
Gazebo-to-PLC signal loop is proven before any mobile robot work.

M0 closed 2026-07-26, verified in docs/reports/m0-04-verify.md.
M1 closed 2026-07-26, verified in docs/reports/m1-04-verify.md.
M2 closed 2026-07-26, verified in docs/reports/m2-02-verify.md.

| Gate | Deliverable | Closes when |
|---|---|---|
| M0 | Repo skeleton, ADR 0001 recording the invariants | Structure exists, invariants committed |
| M1 | Interface contracts | VDA 5050 subset and OPC UA node model documented and reviewed |
| M2 | Safety requirements spec | Every safety function has a trigger, a reaction and an acceptance test |
| M3 | Fixed equipment I/O loop | All four are demonstrated and recorded: (a) Gazebo sensor state is visible as PLC input bits in a TIA watch table, (b) PLC output bits drive the Gazebo actuator, verified visually, (c) latency and update rate are measured and written down, (d) signal-loss behaviour is defined and tested — what the PLC sees when the bridge stops, and what the equipment does |
| M4 | Command path from Hermes | A Telegram-triggered Hermes agent writes a command node over OPC UA and the commanded action is observed in Gazebo, with Hermes never writing actuator outputs and never bypassing PLC interlocks |
| M5 | Simulated vehicle | Gazebo AGV localizes and navigates a warehouse world with Nav2 |
| M6 | VDA 5050 client | A stub publisher sends an order, the vehicle executes it and reports state |
| M7 | Fleet manager | Real service assigns orders to two vehicles, traffic conflicts avoided |
| M8 | PLC/fleet integration | PLC serves OPC UA, fleet manager subscribes, station handshake works end to end |
| M9 | Safety layer | F-CPU implements the spec, e-stop chain and zone monitoring verified against acceptance tests |
| M10 | Demonstration | Recorded end to end run, validation report, README with architecture narrative |
| M11 | Arm integration | Arm motion is gated by a base-stationary interlock, arm work is carried as a VDA 5050 action, and the safety zone model distinguishes base and arm |

A gate closes only when its criterion is observable behavior, not written code.
