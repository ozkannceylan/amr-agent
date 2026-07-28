# Brief m4f-06 — bridge implementation: forklift slots

```
gate:                M4
agent:               bridge
goal:                The bridge translates the forklift signal groups both ways,
                     proven against the test double with the cell conformance
                     unbroken.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md (revised — authoritative),
                      docs/interfaces/opcua-nodes.md section 10,
                      bridge/ sources, docs/LESSONS.md]
deliverable:         bridge/ — config schema, opcua side, ros side, test double and
                     conformance extended per the design
done_when:           a recorded double run proves: every forklift vehicle-input
                     slot carries a ROS value into its node; every output slot
                     (conveyor's plus the three forklift refs) publishes node
                     changes to its ROS topic; the write allowlist rejects any
                     write to an HMI-written node (negative test present); the
                     rewrite-on-restart pass covers ALL input slots including the
                     new ones with the count derived from the log; the existing
                     cell conformance harness still passes unchanged; per-session
                     evidence naming still holds; bridge/EVIDENCE_CONNECT.md gains
                     a dated section for this run with figures quoted as printed.
forbidden:           [connecting to the live PLCSIM endpoint (an owner session may
                      be live — the double only), changing cell slot behaviour,
                      new dependencies, editing docs/interfaces/ (request changes
                      in your report instead), touching agv/ sim/ plc/ hmi/,
                      mentioning any deadline]
```

Concurrency warning: an owner-side run_bridge process with a live PLCSIM session may
be running in WSL. Never pkill by broad pattern; match your own pgrep -af output
only; use a fresh ROS_DOMAIN_ID for double runs.

Git: repo-local owner identity; pathspec-scoped commit of exactly your bridge/ files
plus your report docs/reports/m4f-06-bridge-forklift-slots.md; message style
`feat(bridge): translate the forklift signal groups`.
