gate:                M3
agent:               plc
goal:                A TIA Portal implementation specification the owner can execute directly.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md, docs/interfaces/bridge-design.md, docs/safety/SRS.md, CLAUDE.md section 9]
deliverable:         plc/README.md + plc/demo-cell/SPEC.md
done_when:           The spec gives: PLC tag table matching the OPC UA BrowseNames exactly; DB layout and which tags are server-visible; the conveyor control logic in words and a ladder/SCL sketch (cycle-running flag separate from actuator output, interlocks combined at the output, wire NC / program NO, monitored edge-triggered reset, no auto-resume); the bridge-liveness reaction (what the program does when the liveness signal stops); the watch table contents that demonstrate items (a) and (b) of the gate; step-by-step PLCSIM Advanced + OPC UA server enablement notes; and the four closure items expressed as an owner-executable test procedure.
forbidden:           [claiming any function is a safety function (the demonstration e-stop is a process stop, per ADR 0004), inventing tags absent from the OPC UA model, generating TIA project binaries, editing directories other than plc/ and the report]
