# Brief m4f-01 — forklift commissioning node group and signal table

```
gate:                M4
agent:               interface
goal:                The OPC UA node model carries the forklift commissioning node
                     group: every signal named, typed, bounded, owned and mapped.
invariants_touched:  none
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      docs/interfaces/opcua-nodes.md,
                      plc/demo-cell/SPEC.md sections 4.2-4.3 (add-node procedure),
                      docs/reports/m4-00-hermes-survey.md (command-node section),
                      docs/interfaces/bridge-design.md,
                      the starting table below]
deliverable:         docs/interfaces/opcua-nodes.md — new section 10, "Forklift
                     commissioning nodes"
done_when:           every node has BrowseName, DB home, data type, unit, range or
                     plausibility window, exactly one writer (invariant 10), its
                     readers, and per-tag Accessible/Writable-from-HMI/OPC-UA flags;
                     the server-interface decision (extend DemoCell vs a second
                     interface) is ruled with its ADR 0006 justification and the TIA
                     click-path stated in the SPEC 4.2/4.3 pattern including
                     read-the-derived-URI-back; the HMI heartbeat watchdog semantics
                     are specified including boot polarity (link is FALSE until the
                     heartbeat has been seen to change — LESSONS 2026-07-28) and the
                     stale window as a named constant; a node-to-ROS-topic mapping
                     table covers every bridged node; deviations from the starting
                     table are listed explicitly in the report.
forbidden:           [renaming the DemoCell server interface (ADR 0006), value types
                      beyond Real/Bool/UInt16 (bridge constraint), writing code,
                      editing bridge/ or plc/ or agv/ files, inventing SF references,
                      mentioning any deadline]
```

## Starting table (orchestrator contract — finalize names per CLAUDE.md §9, report deviations)

HMI-written (writer: hmi layer only; PLC consumes):
| HmiDriveCommand | Real | – | −1.00…1.00, fraction of TRACTION_SPEED_MAX |
| HmiSteerCommand | Real | rad | −1.31…1.31 |
| HmiForkCommand | Real | – | −1.00…1.00, fraction of FORK_SPEED_MAX |
| HmiTeleopEnable | Bool | – | – |
| HmiResetRequest | Bool | – | edge-evaluated by the PLC |
| HmiHeartbeat | UInt16 | – | increments at ≥5 Hz, wraps |

Vehicle inputs (writer: bridge, from ROS):
| ForkliftForkHeight | Real | m | plausibility −0.05…1.70 |
| ForkliftLinearSpeed | Real | m/s | plausibility −2.0…2.0 |
| ForkliftObstacleInStopZone | Bool | – | TRUE also when the scan is invalid or stale (fail-safe polarity) |
| ForkliftObstacleMinDistance | Real | m | plausibility 0.0…8.0 |

PLC outputs (writer: PLC; bridge publishes to ROS):
| ForkliftTractionSpeedRef | Real | m/s | interlock-clamped, gated to zero in ELSE |
| ForkliftSteerAngleRef | Real | rad | −1.31…1.31 |
| ForkliftForkSpeedRef | Real | m/s | −0.15…0.15 |

PLC status (writer: PLC; bridge and HMI read):
| ForkliftTeleopActive | Bool |
| ForkliftObstacleStopActive | Bool | latch, monitored reset |
| ForkliftSpeedLimitActive | Bool |
| ForkliftResetRequired | Bool |

ROS topic mapping (fixed contract with m4f-02/03): /forklift/cmd/traction_speed,
/forklift/cmd/steer_angle, /forklift/cmd/fork_speed (Float64, PLC→ROS);
/forklift/fork_height, /forklift/linear_speed (Float64), /forklift/obstacle/in_stop_zone
(Bool), /forklift/obstacle/min_distance (Float64) (ROS→PLC).

Recommendation to rule on: extend the existing DemoCell server interface with a
Forklift subtree so one bridge session, one bridge heartbeat and one link verdict
serve both FBs — the link verdict stays owned by FB_DemoCellControl and the forklift
FB consumes the shared DB bit (invariant 10). The HMI heartbeat is a second,
independent watchdog (different client), specified here.

Git: repo-local owner identity; pathspec-scoped commit of exactly the interface doc
plus your report docs/reports/m4f-01-forklift-node-group.md; message style
`docs(interfaces): add the forklift commissioning node group`.
