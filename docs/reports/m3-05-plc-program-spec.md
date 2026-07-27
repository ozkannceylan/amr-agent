brief:               docs/briefs/m3-05-plc-program-spec.md
status:              done
files_changed:       [plc/demo-cell/SPEC.md (new), plc/README.md]
invariants_touched:  none
open_questions:
  - "No reset device exists in the cell. The demonstration panel has Start, Stop
     and process stop only, and opcua-nodes.md §9.3 has no reset node. The spec
     therefore uses PanelStartPressed as both the reset and the start device,
     distinguished by gesture (press held 0.2-3 s, latch released on the falling
     edge) and by state (a start rising edge is only honoured when
     CellResetRequired is FALSE), so a reset and a start are always two separate
     deliberate presses and the reset energizes nothing. This is implementable
     today with the 14 existing nodes and no tag was invented. A dedicated reset
     contact would be better practice: it needs one topic in sim/ (/cell/panel/reset,
     NO contact) and one node in opcua-nodes.md §9.3 (PanelResetPressed), which are
     the sim and interface agents' to add. REQUESTED, not created."
  - "The reaction to a stopped simulation while the program is commanding 0.0 is
     'none, and here is why' (SPEC §8, D idle sub-case). A frozen input image under
     a zero command is indistinguishable from a genuinely idle cell, and every
     detector for it would put a timer that gates a signal into the wrong layer
     (bridge-design.md §7.3). Recorded as an accepted limit, not a gap to close."
  - "IS_VALID (TIA: Comparator operations > 'OK - Check validity') is recommended
     for the NaN/inf guard on ProductSensorRange but could not be checked against a
     TIA version. The spec states the two plausibility comparisons alone are
     sufficient if the mnemonic differs or is absent."
  - "OPC UA runtime licence: the spec tells the owner where the setting lives
     (CPU properties > Runtime licences > OPC UA, banded small/medium/large by CPU)
     and flags that whether PLCSIM Advanced enforces it at runtime is
     version-dependent. Unverifiable from here; the owner records what he observes
     as step 4 of SPEC §10."
  - "Three constants are commissioning values that the owner's PLCSIM run should
     confirm or revise with evidence: HEARTBEAT_STALE_TIME 500 ms (derived from the
     in-container 20 Hz heartbeat and its 79 ms worst-case cycle), the OB30 period
     of 20 ms (assumes the bridge's 50 ms cadence), and SPEED_TOLERANCE 0.02 m/s."
  - "Evidence for the four exit items lands in bridge/EVIDENCE_LATENCY.md Section B
     and a new PLCSIM section of bridge/EVIDENCE_SIGNAL_LOSS.md. Both are bridge/
     files, outside this agent's write access. SPEC §11 is written as the owner's
     procedure and points at them; the appends are the owner's or the bridge
     agent's to make."
next_suggested:      m3-06 verifier — check the spec against the four M3 exit items, ADR 0004's process-stop rule and the 14 BrowseNames before the owner starts building in TIA Portal.

---

## What was delivered

`plc/demo-cell/SPEC.md` — the TIA Portal implementation specification, covering
every item of the brief's `done_when`:

| done_when item | Section |
|---|---|
| Tag table matching the OPC UA BrowseNames exactly | §3.1 (14 server-visible), §3.2 (internals), §3.3 (constants) |
| DB layout and which tags are server-visible | §4.2, §4.3 |
| Conveyor control logic in words plus a ladder/SCL sketch | §5, §6, §7 (SCL) |
| Bridge-liveness reaction | §6.1, §8 |
| Watch table demonstrating gate items (a) and (b) | §9, groups 1 and 2 |
| PLCSIM Advanced + OPC UA server enablement, step by step | §10, ten steps |
| The four closure items as an owner-executable test procedure | §11, T1–T4 |

Plus the amendment's four points: the Real setpoint gating written out
explicitly with the wrong implementations named (§6.4); the four signal-loss
cases each with a named PLC-side detection mechanism and reaction, case D as a
drive fault (§8); no auto-resume stated per case, in the table's own column
(§8); and `bridge-design.md` read in its corrected post-ADR-0005 form, with
`bridge/` paths throughout.

`plc/README.md` — added a Contents table pointing at the spec, a process-stop
boundary statement, and extended two lines of the existing "This layer must not
access" list to name the bridge and Gazebo explicitly. The forbidden list was
not weakened.

## Tag discipline

Every one of the 14 server-visible tags is a `DemoCell/` BrowseName from
`opcua-nodes.md` §9, leaf name for leaf name. **No interface tag was invented.**
The internal tags of §3.2 (edge memories, timers, latches, `SeqStep`,
`LastBridgeHeartbeat`, `SpeedRequest`) are FB statics that §9.8 of the node model
explicitly keeps *off* the server; the spec states they are not exported and
shows them only in watch-table group 4.

The DB name is a container, not part of the BrowseName — the server interface of
§4.3 places each tag under `DemoCell/Input|Output|Status|Link`, so the client
still sees the exact path while the PLC symbol reads `"DemoCellInput".<Name>`.
This is stated in §3.1 so it is not mistaken for a deviation.

## The one enforcement worth flagging

§4.2 makes `ConveyorSpeedCommand` and every `Status`/`BridgeLinkOk` tag *not*
writable from HMI/OPC UA, so invariant 6 is enforced by the CPU rather than by
convention — a bridge defect that tried to write an actuator output would be
rejected server-side. The bridge already enforces the same allowlist on its side.

## Discipline

Nothing in the deliverable is claimed as verified. Its status line says so, no
TIA project binary or export XML was generated, no function is described as a
safety function, no OPC UA-reachable item is described as SIL/PL-rated, and the
word "emergency" appears in no tag, node or heading. Nothing outside `plc/` and
this report was edited, and nothing was committed.

---

## lessons_candidates

2026-07-27 | Specified a monitored, edge-triggered reset for the demonstration cell | The cell's panel has Start, Stop and process stop and no reset device, and no reset node exists in opcua-nodes.md §9.3, so the domain rule had no device to run on | A gate that mandates a CLAUDE.md §9 behaviour must have the device for it in the signal table; when it does not, implement the behaviour on an existing device with the conflation written out explicitly, and request the missing device rather than inventing a tag

2026-07-27 | Applied "actuator outputs are formed from the cycle-running flag combined with interlocks" to a Real setpoint | The rule reads as a coil-and-contact rule, and the natural translation — a conditional write with no ELSE — leaves the Real holding its last value, so the belt runs on after the stop | Gating an analogue output means driving it to zero in a mandatory ELSE branch, assigned unconditionally in exactly one statement; a conditional write is not a gate

2026-07-27 | Wrote the reset condition as "latches clear when the run permissive is satisfied" | The run permissive contains the latches, so each latch became its own precondition for clearing and no reset could ever fire | Split the interlock set in two: a live-world set that a reset tests, and a permissive set that adds the latches and gates running. A latch is never a term in its own clearing condition

2026-07-27 | Read an IEC TON's elapsed time at the falling edge of the button it was timing | A TON returns ET to 0 in the same call in which IN goes false, so a reset that acts on release always measured 0 and never fired | Latch the "held long enough" verdict while the contact is still held; re-arm it on the next rising edge

2026-07-27 | Made "belt inside its soft travel limits" a run permissive | A belt sitting on the limit could never move off it: returning requires running, and running was blocked by the limit | A limit that can only be escaped by moving is a step-level abort in the offending direction, not a blanket permissive; recovery is a re-home branch chosen by re-reading the position at start

2026-07-27 | Wrote a NaN guard for ProductSensorRange as `range < threshold` | A NaN makes every comparison false, so "no product" is returned — the permissive direction — for a broken sensor | Test an analogue input for plausibility against its physical window before using it in any process comparison, and treat outside-window as a fault rather than as a value
