# Brief m4f-07 — commissioning HMI backend and UI

```
gate:                M4
agent:               hmi (executed by the ad-hoc infra agent until the roster
                     definition is picked up; write scope is exactly hmi/)
goal:                A local operator HMI drives the PLC's HMI nodes: virtual
                     joystick, fork jog, enable, reset, status lamps, heartbeat.
invariants_touched:  none
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      hmi/README.md (boundary), docs/interfaces/opcua-nodes.md
                      section 10 (authoritative node names and writability),
                      bridge/ test double docs (for the test target only — do not
                      import bridge code)]
deliverable:         hmi/ — hmi_server.py, static/index.html, config.yaml,
                     EVIDENCE_HMI.md (README exists from m4r2-03)
done_when:           hmi_server.py (stdlib http.server + asyncua only, one file)
                     serves the UI and writes the six HMI nodes: joystick maps to
                     HmiDriveCommand/HmiSteerCommand with return-to-center-on-release
                     (deadman: release ⇒ zeros written immediately); fork up/down
                     hold buttons map to HmiForkCommand; enable toggle; reset
                     momentary (backend writes TRUE for one write cycle then FALSE —
                     the PLC edge-detects); HmiHeartbeat increments at 10 Hz and
                     STOPS on any backend fault or OPC UA disconnect after one final
                     zeros write attempt; status lamps poll the four status nodes at
                     5 Hz; endpoint and namespace URI come from config.yaml, nodes
                     resolved by browse path per the interface doc; a recorded run
                     against the bridge test double shows every write landing and
                     the heartbeat stopping on kill, transcribed into
                     EVIDENCE_HMI.md with figures quoted as printed; the venv recipe
                     (python3 -m venv ~/amr-hmi-venv && pip install asyncua==<the
                     version the bridge venv uses, read it there>) is recorded in
                     EVIDENCE_HMI.md's environment table.
forbidden:           [any pip package beyond asyncua, any web framework, rclpy or
                      ROS imports, gz anything, reading or writing any PLC node
                      outside the HMI-written group plus read-only status
                      (invariant 6 discipline), importing bridge/ code, connecting
                      to the live PLCSIM endpoint in this brief (double only —
                      the live connection is owner-run later), editing files
                      outside hmi/ except your report, mentioning any deadline]
```

UI notes: single static HTML+JS page, no external assets (offline), pointer-event
joystick (mouse and touch), large stop-state banner when ForkliftObstacleStopActive
or ForkliftResetRequired is TRUE, lamp for ForkliftSpeedLimitActive, link state
shown from the backend's own OPC UA session health. Visual style: plain, high
contrast, industrial — no framework.

Git: repo-local owner identity; pathspec-scoped commit of exactly your hmi/ files
plus your report docs/reports/m4f-07-hmi-backend-ui.md; message style
`feat(hmi): add the commissioning HMI backend and UI`.
