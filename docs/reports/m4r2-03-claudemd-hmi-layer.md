# Report m4r2-03 — CLAUDE.md contract entries and hmi/ bootstrap

brief:               docs/briefs/m4r2-03-claudemd-hmi-layer.md
status:              done
files_changed:       CLAUDE.md (§3 topology, §3 legend clause, §4 layout, §5 roster — 6 insertions, 1 deletion, nothing else), hmi/README.md (new), .claude/agents/hmi.md (new), docs/reports/m4r2-03-claudemd-hmi-layer.md (this file). Committed as one pathspec-scoped commit of exactly these four paths; docs/roadmap.md and docs/interfaces/opcua-nodes.md were dirty from concurrent agents and were not staged, added or committed.
invariants_touched:  none. §2 is byte-identical, and so is the §6 gate table — the gate order stays with docs/roadmap.md per the ADR 0004/0007 precedent. The additions execute ADR 0008's accepted consequence ("CLAUDE.md no longer describes the repository … requested here as a follow-up"). Invariant 4 is restated rather than bent: the edge is drawn HMI to PLC, labelled "OPC UA client to server", so the server role stays with the PLC. Invariants 1, 2, 6, 7, 10 and 11 are unaffected in substance; the new boundary README states each of them as a prohibition rather than an exception.

## What landed

**§3 topology.** One node, `HMI["Commissioning HMI<br/>teleop setpoints and
status<br/>process data only"]`, declared outside the three existing subgraphs
because it is its own layer, and one edge, `HMI -->|OPC UA client to server|
PLC`. The safety edges (`SAFE ==>`, `FCPU -.->`) are untouched, as are all four
process edges that were already there. The legend gained the one clause the
brief allowed — "including the commissioning HMI edge, which carries process
setpoints only (ADR 0008)" — so the "process setpoints only" labelling of
`done_when` is carried explicitly and not only by the node text.

**§4 layout.** `hmi/  commissioning HMI, OPC UA client of the PLC, process data
only`, placed after `bridge/` and before `sim/`, at the same description column
(27) as every other layout line.

**§5 roster.** Row `| hmi | Commissioning HMI backend and UI | hmi/ |`, placed
after `bridge` and before `sim` so the roster order continues to track the §4
layout order. No other roster row was edited.

**hmi/README.md.** First section titled "This layer must not access", per the
§4 convention. Twelve prohibitions: the five the brief named (ROS 2 in any
form, Gazebo and `gz` transport, `bridge/` internals, fleet manager internals,
any PLC node outside the HMI-writable group) plus the six ADR 0008's
consequences set as a minimum (forming or writing any actuator output; any
interlock, latch, timer or sequencing logic; VDA 5050/MQTT/order/traffic/zone
concepts, folded into the fleet item; any safety function or safety path) and
four that fall out of the invariants at this boundary (the OPC UA server role,
remote transport and the tailnet, hard real-time work, secrets). The second
section states what the layer is: a local operator HMI streaming drive/steer/
fork setpoints, an enable, a reset request whose edge is evaluated in the
standard program, and a `UInt16` heartbeat; the PLC owning every actuator
setpoint and watchdogging the heartbeat with the mandatory-`ELSE` gating of
`plc/demo-cell/SPEC.md` §6.4; and the flat statement that this HMI is not a
safety device. ADR 0008 is cited throughout, by decision (D1, D2.1, D2.2, D2.4,
D2.5, D2.7, D3).

**.claude/agents/hmi.md.** Same shape as `.claude/agents/bridge.md`:
frontmatter (name, description, model), roster sentence, three-step startup,
Scope, Hard rules, the closing report obligation. Its layer-specific rules are
the no-logic rule (stop and report if a brief seems to need logic in the HMI,
mirroring the bridge agent's), client-only OPC UA, the write allowlist, the
one-sided heartbeat obligation with the FALSE-until-seen-to-change verdict, the
not-a-safety-device rule, and the no-ROS-2/no-Gazebo/no-broker/local-only
boundary.

## Decisions taken inside the brief's latitude

- **The HMI node sits outside all three subgraphs.** Wrapping one node in a
  fourth subgraph would have implied a multi-component layer that ADR 0008 does
  not describe. Note that `bridge/` is a §4 layer with no §3 node at all, so
  the diagram is a layer-adjacency picture rather than a directory listing.
- **No gate number appears in hmi/README.md.** It names "the forklift
  commissioning gate of ADR 0008 D1, whose live number is carried by
  docs/roadmap.md". m4r2-02 owns the renumbering and was still uncommitted
  while this ran; a hard number here would have been a second place to keep in
  step for no gain.
- **The reset request is described as carried as a level and edge-evaluated in
  the standard program.** ADR 0008 D2.2 says "edge-triggered" without saying
  which side detects the edge; the M3 rule (`bridge/README.md`, the reset
  contact carried as a level with no edge detection, hold timer or latch in the
  client) settles it in the direction that keeps logic out of this layer. That
  is a boundary statement about `hmi/`, not an interface decision — the node's
  name, type and access rights remain open in `docs/interfaces/`.

## open_questions

- **The HMI-writable node group is undefined.** ADR 0008 leaves its names,
  folder and access rights to `docs/interfaces/`. Until that exists, the
  README's fifth prohibition is enforceable only in the negative ("nothing
  outside the group"), and the agent definition's allowlist rule has no list to
  check against. An `interface` brief is the prerequisite for any `hmi` code
  brief.
- **Two writing clients, per-client scoping unenforced.** Recorded in the
  README as ADR 0008 D2.5 states it, not solved. Closing it means configuring
  OPC UA access control on the CPU, which is owner tool time and nobody's brief
  yet.
- **`docs/roadmap.md` and CLAUDE.md §6 now describe different gate sets** — as
  they did before this brief, and by design here, since the §6 table has stayed
  the ADR 0004/0007 boundary all along. Worth confirming the verifier reads §6
  as the static definition and the roadmap as the live order, because a reader
  who does not will file it as a contradiction.

next_suggested:      an `interface` brief defining the HMI-writable node group (names, folder, data types, access rights) in docs/interfaces/opcua-nodes.md, since both the README's write boundary and any hmi/ implementation depend on it.
