gate:                M3
agent:               interface
goal:                Add the OPC UA node that mirrors the cell's new reset contact, so the PLC program can read a real monitored reset instead of a conflated start button.
invariants_touched:  none
inputs:              [docs/reports/m3-10-panel-reset-contact.md, docs/interfaces/opcua-nodes.md, sim/worlds/cell.sdf, sim/README.md, plc/demo-cell/SPEC.md]
deliverable:         docs/interfaces/opcua-nodes.md, §9.3 extended with the reset node
done_when:           §9.3 carries a node whose BrowseName the PLC spec can use verbatim, whose datatype and direction match the delivered /cell/panel/reset contact, and whose fail state is documented as false with the reason; and the node count stated anywhere in the document is updated to match.
forbidden:           [editing sim/, plc/ or bridge/, renaming or retyping any existing node, describing the reset as a safety function or as safety-rated, inventing signals the cell does not publish, restructuring §9 or any other section]

## The signal, as delivered and verified

`m3-10` added and ran the contact. Take these from its report, and confirm them
against `sim/` rather than trusting this summary:

- Topic `/cell/panel/reset`, `std_msgs/msg/Bool`, bridged ROS → gz as
  `gz.msgs.Boolean`.
- Direction cell → PLC. The bridge subscribes. `ros2 topic info` is identical
  to `/cell/panel/start`.
- **Normally open, momentary.** `true` = held. `false` = released, broken wire,
  welded-open contact, or nothing publishing at all.
- It energizes nothing in the simulation. Verified idle and at 0.15 m/s.

## The point that must not be lost

**This node's fail state is `false`, which is the opposite of the two stop
nodes sitting beside it in §9.3.** Those are normally closed, because a stop
device must assert its stop when the wire breaks. A reset is normally open,
because a broken or welded reset that asserted itself continuously would clear
latches unbidden — exactly the automatic resume CLAUDE.md §9 forbids.

Document that difference explicitly at the node. A reader scanning §9.3 will
see three panel inputs and reasonably assume one convention governs all of
them. Say why this one differs, in one sentence, at the point of use.

## Naming

`m3-10` suggests `PanelResetPressed` under `DemoCell/Input/`. Follow the naming
already used by the neighbouring panel nodes rather than that suggestion if the
two disagree — CLAUDE.md §9 requires OPC UA node names to mirror PLC tag names
exactly so the documents diff cleanly, and `plc/demo-cell/SPEC.md` §3.1 already
names 14 tags. Check what the spec would call it before choosing.

## Scope discipline

You are adding one node. You are **not**:
- amending `plc/demo-cell/SPEC.md` to use it — that is m3-12, the plc agent's;
- adding the bridge config entry — that is a bridge brief;
- revisiting `bridge-design.md`, which has its own queued sweep.

If adding the node reveals that another document must change, name the document
and the change in your report. Do not make it.

## Reporting

`docs/reports/m3-11-panel-reset-node.md` in the CLAUDE.md report shape, then
`lessons_candidates` (may be "none"). State the exact BrowseName, datatype,
access level and fail state, so the plc agent can consume it in m3-12 without
re-deriving anything.
