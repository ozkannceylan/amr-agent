# ADR 0005: The bridge is a top level layer, and asyncua is its OPC UA stack

Status:        accepted

Context:       ADR 0004 declared the Gazebo-to-PLC bridge a first class
component and rejected folding it into the fleet manager. The design that
followed, `docs/interfaces/bridge-design.md`, specified it fully but left two
questions open (report `docs/reports/m3-03-bridge-design.md`, open questions 1
and 2). This ADR closes both.

1. Where the bridge lives. The design provisionally placed it at
   `fleet/bridge/`. But `fleet/README.md`'s "This layer must not access"
   section forbids ROS 2 topics, services and actions — correctly, for the
   fleet manager (invariants 3, 11). The bridge is by definition a ROS 2 node,
   so keeping it under `fleet/` would require carving an exception into the
   boundary statement of another layer. This project is judged on the clarity
   of its layer discipline; a boundary statement with an exception in it is
   weaker than one without.

2. Which OPC UA library. The bridge is an OPC UA client (invariant 4) and
   needs a Python OPC UA stack. Its test double (bridge-design.md §10) needs an
   OPC UA server. Verified in the container: there is no apt candidate for
   `python3-asyncua`; `pip 24.0` is present, so the install path is a pinned
   `pip install` recorded in a requirements file.

Decision:

**D1 — The bridge is its own top level directory, `bridge/`.**

It is not a subdirectory of `fleet/`, `sim/` or `agv/`. It carries its own
`README.md` whose first section is titled "This layer must not access", per the
repository layout convention, listing at minimum:

- Fleet manager code, state or configuration.
- VDA 5050 messages and MQTT, in any form.
- Order, traffic and zone-reservation concepts (invariants 5, 6).
- PLC program logic — sequencing, interlocks, timers, latching.
- Any control decision whatsoever: the no-logic rule of
  `docs/interfaces/bridge-design.md` §1.1 is the binding statement.
- Any safety function or safety path (invariant 1).

**D2 — `asyncua` is the OPC UA library, and provides the test double server.**

It is pinned to an exact version in `bridge/requirements.txt` and used
unmodified as an imported library. The same package supplies both the client
(the bridge) and the server (the test double), so the double adds no second
dependency. It transitively pulls `cryptography`. The exact pinned version
lives in the requirements file, not in this ADR, so a version bump does not
require superseding this decision.

Consequences:

- `CLAUDE.md` section 4 gains a `bridge/` entry, and the agent roster in
  section 5 gains a `bridge` agent owning `bridge/`. **Required follow-up by
  the orchestrator** — `CLAUDE.md` is the owner's file and is not editable by
  the agent that authored this ADR.
- The bridge's adjacency becomes explicit and testable: it talks to the cell
  over ROS 2 and to the PLC over OPC UA as a client, and to nothing else
  (invariant 11). A boundary violation is visible as an import that crosses a
  top level directory, rather than being hidden inside a sibling of the fleet
  manager.
- `fleet/README.md` stays absolute. No exception line is added, and the fleet
  manager's ban on ROS 2 internals remains unqualified.
- The bridge is independently testable and independently deployable; it does
  not inherit the fleet manager's dependencies, configuration or lifecycle.
- Paths written under the provisional location must be corrected where they are
  still authoritative: `fleet/bridge/`, `fleet/bridge/EVIDENCE_LATENCY.md` and
  `fleet/bridge/evidence/` become `bridge/`, `bridge/EVIDENCE_LATENCY.md` and
  `bridge/evidence/`. The m3-04 implementation brief is written against
  `bridge/`.
- One new runtime dependency enters the project, scoped to the bridge layer
  only. No other layer gains it.
- The test double and the production client share one stack, so the bridge's
  client code path is identical against the double and against PLCSIM
  Advanced. This keeps the double honest **about the bridge**; it proves
  nothing about the PLC program, which has no scan cycle, process image or
  interlocks in the double (bridge-design.md §10, ADR 0004).
- `asyncua` is licensed LGPL-3.0. It is imported unmodified as a library, not
  linked statically and not vendored into this repository, which is the usual
  and unproblematic use of an LGPL library. This is a statement of how the
  dependency is used, not legal advice.

Alternatives:

- `fleet/bridge/` with an exception line in `fleet/README.md` — rejected: it
  weakens the boundary statement of a layer to accommodate a component that is
  not part of that layer. The exception would have to be re-read and re-honoured
  by every future agent and verifier touching `fleet/`.
- `sim/bridge/` — rejected: the bridge is not a simulation asset. It must
  survive replacing the simulated cell with real equipment unchanged except for
  configuration; placing it in `sim/` would imply it is disposable with the
  simulation.
- Fold the bridge into the fleet manager — already rejected by ADR 0004
  (invariants 6 and 10). Recorded here only to note that this ADR does not
  reopen it.
- `python-opcua` / `opcua` — rejected: the deprecated predecessor of `asyncua`,
  not recommended for new work by its own maintainers.
- `open62541` via Python bindings — rejected: a C toolchain and build
  dependency for an eight node address space, with no benefit at that scale.
- Write a minimal OPC UA client — rejected: re-implementing a protocol stack is
  not this project's contribution, and a hand-rolled client would make every
  measured number in the M3 evidence a measurement of that client's defects.
