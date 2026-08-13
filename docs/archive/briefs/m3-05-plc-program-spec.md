gate:                M3
agent:               plc
goal:                A TIA Portal implementation specification the owner can execute directly.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md, docs/interfaces/bridge-design.md, docs/safety/SRS.md, CLAUDE.md section 9]
deliverable:         plc/README.md + plc/demo-cell/SPEC.md
done_when:           The spec gives: PLC tag table matching the OPC UA BrowseNames exactly; DB layout and which tags are server-visible; the conveyor control logic in words and a ladder/SCL sketch (cycle-running flag separate from actuator output, interlocks combined at the output, wire NC / program NO, monitored edge-triggered reset, no auto-resume); the bridge-liveness reaction (what the program does when the liveness signal stops); the watch table contents that demonstrate items (a) and (b) of the gate; step-by-step PLCSIM Advanced + OPC UA server enablement notes; and the four closure items expressed as an owner-executable test procedure.
forbidden:           [claiming any function is a safety function (the demonstration e-stop is a process stop, per ADR 0004), inventing tags absent from the OPC UA model, generating TIA project binaries, editing directories other than plc/ and the report]

---

## Amendment, 2026-07-27 (orchestrator)

Issued before delegation. Three points the original `done_when` left implicit
and one sequencing note.

1. **`ConveyorSpeedCommand` is a Real setpoint, not a coil.** The spec must
   not describe it as a boolean output driven by a contact. The domain rule in
   CLAUDE.md section 9 ("actuator outputs are formed from the cycle-running
   flag combined with interlocks") still applies, but for an analogue value
   the mechanism is *gating a setpoint*, not energising an output: when the
   cycle-running flag is false or an interlock is broken, the commanded speed
   is driven to zero rather than the tag simply being left alone. Write this
   distinction out explicitly — a reader who implements it as a coil has
   implemented it wrongly.

2. **Signal-loss case D is caught by drive-fault.** The four signal-loss cases
   A–D are already exercised in `bridge/EVIDENCE_SIGNAL_LOSS.md`. The spec
   must state which PLC-side mechanism detects case D and what the program
   does about it, expressed as a drive-fault reaction. Cases A–C must each be
   named with their PLC-side reaction too, even where that reaction is
   "no action required, and here is why".

3. **Restart after any of the above is the monitored, edge-triggered reset**
   of CLAUDE.md section 9. No auto-resume. Say so per case rather than once
   in general terms.

4. **Sequencing.** `docs/interfaces/bridge-design.md` is an input to this
   brief and is being corrected under `m3-03c` in the same session. Do not
   start until the orchestrator confirms `m3-03c` has landed, and read the
   corrected version. The component directory is `bridge/`, never
   `fleet/bridge/` (ADR 0005).
