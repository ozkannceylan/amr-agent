# Brief m4f-01b — steer-gating ruling and §10.12 closures

```
gate:                M4
agent:               interface
goal:                opcua-nodes.md §10 agrees with itself on the steer setpoint
                     and its open items reflect what m4f-04 closed.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md section 10,
                      plc/forklift/SPEC.md (sections 3.3, 6.4, 8),
                      docs/reports/m4f-04-plc-forklift-spec.md,
                      docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md D2.3]
deliverable:         docs/interfaces/opcua-nodes.md section 10 (corrected)
done_when:           section 10.6 carries one consistent rule — all three
                     setpoints, steer included, drive to 0.0 in the
                     interlock-failed ELSE (ruling adopted from the SPEC's
                     implemented behaviour and 10.6's own gating paragraph); the
                     contradicting table row is gone; the visible consequence
                     (the steered wheel centres while the machine stops) is
                     stated; 10.12 item 4 is marked resolved by the SPEC's
                     TRACTION_SPEED_MAX = 1.00 m/s with the window-at-least-
                     twice-the-cap relation shown; 10.12 item 3 records the open
                     request for a ForkliftDriveFault node (until it exists,
                     case D has no verdict on this plant — SPEC section 8 case
                     P); the SPEC's HmiStartRequest request is recorded as a new
                     10.12 open item, post-gate, with the M4 conflation
                     (HmiTeleopRequest release-and-reassert after a reset)
                     stated where 10.7 describes teleop; a whitespace-normalised
                     sweep finds no statement still depending on the removed
                     row.
forbidden:           [renaming anything, adding nodes, editing plc/ files or
                      bridge-design.md, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the interface
doc plus your report docs/reports/m4f-01b-steer-gating-correction.md; message
style `docs(interfaces): rule the steer setpoint gating and close two open items`.
