gate:                M3
agent:               sim
goal:                Give the demonstration cell a physical reset device, so the monitored reset that CLAUDE.md §9 requires runs on its own contact instead of being conflated onto the start button.
invariants_touched:  none
inputs:              [sim/worlds/cell.sdf, sim/README.md, docs/reports/m3-05-plc-program-spec.md, docs/interfaces/opcua-nodes.md]
deliverable:         a /cell/panel/reset contact published by the demonstration cell, wired like the existing panel contacts
done_when:           The cell publishes /cell/panel/reset alongside the existing panel topics, it is actuable in a headless run the same way the existing panel contacts are, its type and topic name match the conventions already used by the start and stop contacts, and sim/README.md documents it in the same place the other panel signals are documented.
forbidden:           [editing docs/interfaces/ (the OPC UA node is brief m3-11's, and the interface agent owns it), editing plc/ or bridge/, adding a reset to the safety chain or describing it as a safety function, inventing a new topic naming convention, changing any existing panel contact's name or type, adding dependencies]

## Why

`m3-05` had to specify the cell's monitored reset on `PanelStartPressed`,
distinguished only by gesture and by state, because the panel has Start, Stop
and process stop and no reset device at all. The owner ruled on 2026-07-27 that
the cell gets a real reset contact rather than accepting the conflation.

## Constraints that decide correctness

- **Normally open.** CLAUDE.md §9's "wire NC, program NO" governs *safety and
  stop* devices, which are wired normally closed so a broken wire stops the
  machine. A reset is not a stop device: it must be **normally open**, so a
  broken or stuck-closed reset cannot spontaneously clear a latch. The owner's
  decision preview states NO explicitly. Getting this backwards would create
  precisely the auto-resume that §9 forbids.
- **The reset energizes nothing.** It is an input only. It must not drive an
  actuator, clear a fault in the simulation, or change belt state. All reset
  logic belongs in the PLC program.
- **Match the existing contacts.** Read how `/cell/panel/*` start and stop are
  declared and published today, and follow that pattern exactly — message type,
  naming, latching or momentary behaviour, and however the cell exposes them for
  actuation in a headless run. Do not introduce a second convention.
- **Momentary, not latching**, unless the existing contacts prove otherwise. The
  PLC does the edge detection; the sim provides a button, not a state.

## Environment note

Gazebo Harmonic is **not yet installed** on this machine — `apt` needs owner
elevation and that is pending. You therefore may not be able to run the cell.
If you cannot, say so plainly: deliver the change, state exactly what you could
and could not verify, and list the command that would verify it. **Do not claim
a headless run you did not perform.** An honest "unverified, here is the
command" is a pass for this brief; a fabricated run is a failure.

Check whether Gazebo has appeared before assuming it has not.

## Reporting

`docs/reports/m3-10-panel-reset-contact.md` in the CLAUDE.md report shape. State
the exact topic name and message type you used, and confirm the contact is
normally open and drives nothing. End with `lessons_candidates` (may be "none").

Your report must also state, for the interface agent's benefit in m3-11, the
precise signal semantics the OPC UA node will have to mirror.
