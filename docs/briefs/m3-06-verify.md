gate:                M3
agent:               verifier (read only on the repo; may execute the delivered scripts)
goal:                Independent verification of everything M3 can demonstrate without TIA Portal, and an explicit statement of what only the owner can close.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 6, docs/adr/0004, all M3 deliverables]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m3-06-verify.md.
done_when:           The verifier re-runs the world, the bridge and the test-double loop from the committed instructions and confirms bidirectional signal flow, measured latency/update rate and signal-loss behaviour; checks the bridge contains no control logic (invariants 5, 6), the client/server direction (invariant 4), no safety function over OPC UA (invariant 1), Gazebo-only simulation (invariant 12), layer boundaries and git hygiene; and states precisely which of the gate's four items remain owner-executed against PLCSIM and what evidence the owner must capture.
forbidden:           [editing or creating repo files, fixing defects found, declaring the gate closed on items requiring the real PLC]
