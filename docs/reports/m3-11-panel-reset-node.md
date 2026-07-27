brief:               docs/briefs/m3-11-panel-reset-node.md
status:              done
files_changed:
  - docs/interfaces/opcua-nodes.md   (§9 intro panel list; §9.3 node row + polarity-suffix
                                      sentence; §9.5 CellResetRequired wording; §9.8
                                      "absent" row; §9.9 reconciliation row)
invariants_touched:  none
open_questions:
  - "plc/demo-cell/SPEC.md must change and I did not touch it (m3-12, plc agent). Five places:
     §3.1's heading says 'exactly the 14 nodes of opcua-nodes.md §9' and its table has 14 rows —
     both become 15; §5-§7 implement the monitored reset on PanelStartPressed and can now use the
     dedicated contact; §C's contact table lists C1/C2 only; §8's test table has no reset step;
     §9's open item 1 ('There is no reset contact in the cell') is now closed by m3-10 and this node."
  - "docs/interfaces/bridge-design.md states 'Six nodes the bridge writes' and 'refresh all six
     inputs' in five places (§5 intro, §6.1, R4, the guarantee box, §7 reconnect) — all become
     seven, and its signal map needs the reset row. Left alone: it has its own queued sweep.
     Its §6.3 pre-first-publish default for this node must be FALSE, per the node's fail state."
  - "bridge/config/bridge.yaml and bridge/tools/cell_stimulus.py still know three panel contacts.
     Already requested by m3-10; unchanged here, outside this agent's write access."
next_suggested:      m3-12 plc — consume `PanelResetPressed` and retire the start/reset conflation in SPEC §5-§7.

---

## The node, for m3-12

| Property | Value |
|---|---|
| BrowseName path | `DemoCell/Input/PanelResetPressed` |
| PLC symbol | `"DemoCellInput".PanelResetPressed` |
| S7 type | `Bool` |
| OPC UA type | `Boolean` |
| Access (bridge's view) | **R/W** — the bridge is the only writer, as for the other three panel inputs |
| Update | on-change, plus full refresh of all `DemoCell/Input/` nodes on reconnect (§9.2) |
| Owner | Gazebo cell, via the bridge |
| Fail state | **`FALSE`** (0) |
| §3.1 start value | `FALSE` — same value, same reason |
| Source | `/cell/panel/reset` → `data` |

Nothing else about it is an interface property. The rising edge, the hold time and which latches
clear are PLC program content and are stated as such at the node.

## Name derivation

`m3-10` suggested `PanelResetPressed`; that is also what `plc/demo-cell/SPEC.md` §3.1's convention
produces, so the two agree and no correction was needed. The derivation, since the brief asked for
it rather than for the suggestion:

§9.3 does not use one naming convention for panel inputs — it uses a suffix that **encodes the
polarity**. NC devices are named for the circuit (`PanelStopCircuitClosed`,
`PanelProcessStopCircuitClosed`) so the tag reads true exactly when the machine may run. NO devices
are named for the button (`PanelStartPressed`) so the tag reads true only while a hand is on it.
The reset is NO and momentary, identical in shape to start, so it takes the `…Pressed` form.
`PanelResetCircuitClosed` would have been actively wrong: it would read `TRUE` at rest and invite an
NC implementation.

## How the fail-state difference is documented

Three places, smallest first:

1. **At the node**, in the sentence the brief asked for, opening the Meaning cell rather than
   trailing it: *"Its fail state is 0, the opposite of the two stop nodes below"* — then the
   reason in the same sentence (a stop must fail to *stopped*, a reset to *not reset*; a cut wire,
   a welded-open contact or nothing publishing all read 0, because a reset that asserted itself
   would clear latches with no operator present — the automatic resume CLAUDE.md §9 forbids).
2. **Row order.** The row sits between `PanelStartPressed` and the two stop nodes, so the table
   reads NO, NO, NC, NC. The cell's own order is start, stop, reset, process stop; putting the
   reset there would have wedged it between the two NC rows, which is exactly the position that
   makes a reader assume NC. §9.3 now says the rows are grouped by polarity, not panel layout.
3. **In the naming paragraph** that already follows the table, one sentence making the suffix rule
   explicit — `…CircuitClosed` fails to 0 = actuated, `…Pressed` fails to 0 = not actuated — and
   stating outright that one convention does not govern all four panel inputs.

## Verified against sim/, not taken from the brief

Per the brief's instruction and LESSONS 2026-07-27 (an enumerated list is a starting point):

| Claim | Checked in |
|---|---|
| Topic `/cell/panel/reset`, `std_msgs/msg/Bool`, field `data` | `sim/README.md` signal table row `PanelResetContact`; `sim/launch/cell_bringup.launch.py` `_BRIDGE_ARGS` |
| Bridged `]gz.msgs.Boolean`, byte-identical in shape to the other three panel contacts | `cell_bringup.launch.py:85-88` — the four contacts differ only in topic name |
| Direction cell → PLC (PLC input) | `sim/README.md` direction column; `CELL_EVIDENCE.md` Appendix A `ros2 topic info`: publishers 0, subscriptions 1, identical to `/cell/panel/start` |
| Normally open, momentary, never latched or debounced in the cell | `sim/README.md` *Polarity* section; `cell.sdf:325-332`; `CELL_EVIDENCE.md` A: `reset_rx` None before any publish, True only while held, False on release |
| Safe pre-first-publish value `false` | `sim/README.md` *There is no initial value* |
| It energizes nothing | `CELL_EVIDENCE.md` A: belt position, velocity and beam range unchanged across hold/release/tap while idle and while running at 0.15 m/s |

One correction to the brief's summary, cosmetic rather than substantive: the sim signal table names
it `PanelResetContact`, not `PanelResetPressed` — the proposed sim names are superseded by the
BrowseNames here, as §9.9 already records for the other three contacts.

## Two statements this node would otherwise have falsified

Both are in `opcua-nodes.md` itself, so I fixed them rather than reporting them:

- **§9.8** listed *"Any safety node, mirror or reset"* as deliberately absent. Read after this
  change it says the node I just added does not exist. Narrowed to *"reset of a safety function"*,
  with one clause saying `PanelResetPressed` is not an exception because it is a process device.
- **§9.5 `CellResetRequired`** said *"no node in this section can clear it"*. A reader can now point
  at a node that participates in clearing it. Reworded to the claim that is actually true and that
  invariant 6 needs: no **client** may clear it by writing a node; the reset input carries a field
  contact level, and the edge, the hold and the latch set are PLC program content.

No node was renamed or retyped, no section was restructured, no signal the cell does not publish was
invented, and the reset is described nowhere as a safety function or as safety-rated. There is no
total node count stated anywhere in `opcua-nodes.md` (the only count, "(5 nodes)" in §9.9, is the
Status folder and is unchanged), so the count obligation in `done_when` falls entirely on
`plc/demo-cell/SPEC.md` §3.1 and is requested above. Nothing was committed.

---

## lessons_candidates

2026-07-27 | Added one node to a contract document and treated the job as the new row plus the reconciliation table | The document's "deliberately absent" section (§9.8) and a neighbouring node's description both asserted the absence of what had just been added, so the file contradicted itself in two places while every changed line looked correct | Adding an item to a contract document means grepping that document for statements of its absence — the absent-by-design list and any "no node can…" clause — before the change is done

2026-07-27 | Considered listing the panel inputs in the order the cell publishes them (start, stop, reset, process stop) | That order puts the one NO-failing contact between the two NC-failing ones, which is the exact adjacency that makes a reader generalise the wrong convention | Order rows in a signal table by failure direction, not by physical panel layout, when the table mixes both; adjacency is documentation
