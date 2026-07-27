# Report m3-20 — evidence files: commissioned-target environment record

brief:               docs/briefs/m3-20-evidence-environment-record.md
status:              done
files_changed:
  - bridge/EVIDENCE_LATENCY.md    (+80 / −1)
  - bridge/EVIDENCE_SIGNAL_LOSS.md (+59 / −0)
invariants_touched:  none
open_questions:
  - Browse path vs. bridge config. `bridge/config/bridge.yaml` resolves
    `[DemoCell, Input, <name>]` from the `Objects` folder with every element
    prefixed by the single `DemoCell` namespace index
    (`amr_bridge/config.py:browse_path`, `amr_bridge/opcua_side.py:128`). The
    commissioned server nests the interface as
    `Objects/ServerInterfaces/DemoCell`, and `ServerInterfaces` belongs to the
    Siemens namespace, so that path cannot resolve. This is already owned by
    brief m3-21; recorded in `§B.0.3` item 3 as a fact, with no code or config
    change made here. Consequence worth surfacing: **Section B cannot be
    captured until m3-21 lands**, which contradicts Section B's standing
    sentence that only `opcua.endpoint` and the security fields change. That
    sentence is inside the existing Section B prose and this brief forbade
    editing it, so `§B.0.3` qualifies it instead of rewriting it.
  - `bridge/config/bridge.yaml` still carries the test double's loopback
    endpoint (`opc.tcp://127.0.0.1:4840/amr-agent/celldouble/`). Editing config
    was forbidden here; whoever prepares the PLCSIM run needs
    `opc.tcp://192.168.53.1:4840`. The security fields need no change (server is
    `None` + anonymous), and `session_timeout_ms: 10000` sits below the server's
    observed 30 000 ms clamp ceiling.
  - Section B item 1 remains partly outstanding after this record: phase 0 did
    not fix the CPU's configured scan cycle, nor the network path in use at
    measurement time with its invariant-8 confirmation. Both are named in
    `§B.0` as the owner's to confirm rather than silently claimed.
next_suggested:      m3-21 (client resolves both namespaces under ServerInterfaces) before any Section B capture is attempted.

## What was written

`EVIDENCE_LATENCY.md` gained **§B.0 Commissioned target environment —
commissioning phase 0, owner-verified in tool 2026-07-27**, placed as the first
subsection of Section B, ahead of the owner's untouched capture list:

- a facts table (TIA V21; PLCSIM Advanced V7.0 with V3.0 removed and why; CPU
  1513-1 PN firmware V3.1; OPC UA runtime licence *large* and why small was
  refused; TCP/IP Single Adapter `<Local>`, 192.168.53.1/24 instance and
  192.168.53.241/24 host adapter; endpoint `opc.tcp://192.168.53.1:4840`;
  security None with CPU-level *Disable access control*; the two-namespace
  browse path; session timeout requested 3 600 000 ms, granted 30 000 ms);
- `§B.0.1` the independent 2026-07-27 verification — 15 nodes read with an
  `asyncua` client from Windows, all at start values, bridge not involved — with
  the cross-check that 15 is exactly the set `bridge.yaml` resolves today
  (7 `Input/`, `BridgeHeartbeat`, `ConveyorSpeedCommand`, 5 `Status/`,
  `BridgeLinkOk`) against the 14 the pre-reset runs log;
- `§B.0.2` what it does not establish, distinguishing "at start value because
  nothing ran" from "formed by a program";
- `§B.0.3` three consequences stated as facts: security fields correct as
  configured, requested session timeout inside the clamp, and the browse-path
  mismatch above.

`EVIDENCE_SIGNAL_LOSS.md` gained a matching dated subsection immediately after
its environment/scope header, carrying the same facts table, the independent
verification, and two items that bear on the cases below: case A's session
timing is the one container result known not to transfer (now measurable against
a server that clamps to 30 000 ms), and case C's "server restarted with start
values" becomes a different event once a program is running. It also records the
m3-21 precondition so the repeat is not attempted too early.

Both subsections state plainly that phase 0 proves the endpoint and the node
exposure only, that no PLC program logic ran, and that the bridge was not
involved.

## Constraints observed

- No measured figure changed. `git diff --numstat` is +80/−1 and +59/−0; the
  single deleted line is the LATENCY navigation sentence "…by m3-13.", extended
  to point at §B.0. No table, log excerpt or statistic in Sections A, C or in
  the four failure cases was touched.
- Section B's capture list, and every PLCSIM measurement item in it, is
  unfilled. `§B.0` is labelled an environment record, not a measurement.
- No bridge code, no bridge config, no file outside `bridge/` (plus this
  report). No dependency added. Nothing committed — the changes are in the
  working tree for the orchestrator to commit by pathspec.
- Sources read only for cross-checking: `bridge/config/bridge.yaml`,
  `bridge/amr_bridge/config.py`, `bridge/amr_bridge/opcua_side.py`,
  `docs/interfaces/opcua-nodes.md` §2.1/§9.
