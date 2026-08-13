# Brief m5-17 — OPC UA nodes for the motion envelope, the drive mode and the emergency request

```
gate:                M5
agent:               interface
goal:                docs/interfaces/opcua-nodes.md specifies every node the
                     autonomous mode needs, so the vehicle-side gate node and
                     HMI v2 can both be built against a contract instead of
                     against each other.
invariants_touched:  none. Invariant 4 (PLC is the server), invariant 6 (the
                     fleet manager never commands actuators — not engaged
                     here, but the envelope must not become a back door for
                     it later) and invariant 10 (one owner per datum) all
                     constrain this design and the document should show it.
inputs:              [docs/interfaces/opcua-nodes.md sections 10 and 11 (the
                      pattern to follow and extend),
                      docs/adr/0011-sensored-autonomy-architecture.md D3,
                      docs/adr/0012-envelope-composition.md D1 (the third
                      element is a station permit, NOT a zone permit),
                      docs/adr/0010-milestone-restructure-forklift-first.md
                      D6(b) (the HMI emergency button's reading),
                      plc/forklift/SPEC.md sections 7 and 13,
                      docs/interfaces/bridge-design.md]
deliverable:         docs/interfaces/opcua-nodes.md (a new section, in the
                      §10 pattern)
done_when:           every node carries a BrowseName, a data type, an access
                     right, a start value, an owner and a plausibility or
                     range statement where the type admits one, exactly as
                     §10 does; the three envelope elements are specified —
                     motion enable, speed ceiling, station permit — with the
                     station permit's meaning written so it cannot later be
                     read as a traffic or zone reservation (ADR 0012 D1);
                     drive-mode selection and its READBACK are separate nodes
                     with the direction of each stated; the HMI emergency
                     request is specified as a process-stop request with its
                     latch and monitored-reset behaviour named, and the
                     document says in one sentence what it is NOT (it is not
                     a safety function and does not reach the F-layer over
                     the network — invariant 1); the vehicle-side state the
                     PLC needs back is specified; every start value is chosen
                     so that a cold start is the SAFE, non-permissive state
                     and the document says so per node; and nothing in the
                     section presumes the m5-03 F-I/O verdict.
forbidden:           [specifying any node inside the Safety/ mirror group
                      (that group is settled — §11); designing PLC logic
                      (m5-16's), vehicle logic (m5-11's) or HMI layout
                      (m5-14's); inventing a controller-selection node (the
                      vendor gate is a later gate and its selection is a
                      startup datum, not a runtime node); coining names for
                      the safe scanner channel (that waits on m5-03);
                      committing (the orchestrator commits)]
```

## Design constraints worth stating in the document

**The envelope is the PLC's, and it is low rate.** ADR 0011 D3 puts the ~20 Hz
navigation loop onboard the vehicle and gives the PLC an envelope it publishes
at its own cycle. So these nodes are not a velocity channel and must not be
shaped like one — no per-sample setpoint, no node whose semantics only make
sense if read at 20 Hz. If a reader could mistake the speed ceiling for a
speed setpoint, the naming is wrong.

**The station permit is not a zone permit.** ADR 0012 D1 replaced that word
deliberately: zone reservation and traffic belong to the fleet manager under
invariant 5, and at M6 a vehicle's motion will be bounded by BOTH a PLC
station permit and a fleet-manager zone reservation — different data, different
owners. Write the station permit's definition so that the M6 reader cannot
conflate them, and note the coexistence explicitly.

**Cold start is non-permissive.** This project's domain conventions require it
and the demo cell already works this way. Every start value in this section
should make the vehicle stationary and un-enabled until something affirmatively
permits motion, and the document should say that per node rather than once in
a preamble — a per-node statement survives a later edit that moves a row.

**The mode is one datum with one owner.** Requesting a mode and being in a
mode are different things and belong in different nodes with different
directions. Say which component owns the authoritative answer to "what mode is
the machine in", and make it impossible for the HMI and the vehicle to hold
two different beliefs about it without one of them being visibly stale.

## Notes

Follow §10's table shape exactly — this section will be diffed against the
PLC's tag list and read beside it, and a different shape costs a reader real
effort. Where a node's name must mirror a PLC tag (CLAUDE.md §9: OPC UA node
names mirror PLC tag names exactly), say so, and remember ADR 0006: an
interface name is a contract decision taken at briefing, never discovered in
the tool.

The report should list, for the m5-16 PLC brief that follows, exactly which
tags the standard program must declare — that brief will be written from your
section, so anything you leave implicit becomes a question later.

Do not commit. Leave the file modified and write your report to
docs/reports/m5-17-envelope-mode-nodes.md.
