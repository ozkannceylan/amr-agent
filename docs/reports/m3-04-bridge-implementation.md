brief:               docs/briefs/m3-04-bridge-implementation.md
status:              done

files_changed:
  - bridge/README.md                     (layer README; first section "This layer must not access")
  - bridge/requirements.txt              (asyncua==2.0.1, pinned; install path recorded)
  - bridge/.gitignore
  - bridge/run_bridge.py                 (launcher)
  - bridge/amr_bridge/__init__.py        (no-logic rule stated as the package contract)
  - bridge/amr_bridge/config.py          (loader; rejects unknown keys, WRITE_ALLOWLIST)
  - bridge/amr_bridge/slots.py           (depth-1 latest-value slots, never queues)
  - bridge/amr_bridge/ros_side.py        (subscriptions, one publisher, field addressing)
  - bridge/amr_bridge/opcua_side.py      (client session, node resolution, type check,
                                          50 ms cycle, write allowlist, reconnect)
  - bridge/amr_bridge/instrumentation.py (per-event CSV recorder, L6 actuation probe)
  - bridge/amr_bridge/main.py            (entry point, rclpy thread + asyncio loop)
  - bridge/config/bridge.yaml            (addresses, cadence, housekeeping only)
  - bridge/test_double/plc_test_double.py (TEST SCAFFOLDING OPC UA server, §9 address space)
  - bridge/test_double/README.md
  - bridge/tools/summarize_latency.py    (post-run statistics, count/min/median/p95/max)
  - bridge/tools/cell_stimulus.py        (TEST SCAFFOLDING panel stimulus + pose observer)
  - bridge/tools/check_write_allowlist.py (client-side and server-side write refusal check)
  - bridge/EVIDENCE_LATENCY.md           (dated 2026-07-27; Section A agent-run,
                                          Section B owner-run PLCSIM placeholder)
  - bridge/EVIDENCE_SIGNAL_LOSS.md       (dated 2026-07-27; §7.3 cases A-D)
  - bridge/evidence/latency-2026-07-27.csv (raw per-event rows, 76 191 rows, 6.8 MB)
  - docs/reports/m3-04-bridge-implementation.md (this file)

invariants_touched:  none

verified_in_this_container (2026-07-27):
  - Cell (cell_bringup.launch.py, RTF 0.998) + test double + bridge, 200 s measurement run,
    4000 cycles, 0 cycle overruns, 0 write errors, 0 read errors, 0 reconnects.
  - cell -> double: all six DemoCell/Input nodes carried real sampled values that changed
    with the cell. Photo-eye 1.4400883913 m clear / 0.5400331616 m blocked, four full
    block/clear traverses; belt position/speed continuous at 20 Hz; all three panel
    contacts toggled and observed server side.
  - double -> cell: ConveyorSpeedCommand set on the double (0.15 / 0.0 / -0.15) ran the
    belt and moved the product; box_x tracked belt_pos with a constant -1.000 m offset
    from -1.000 m to +1.4999 m and back to -0.744 m.
  - Startup rule: heartbeat withheld for 58 cycles, advanced from 0 to 1 in the same
    200 ms window in which the last two inputs first carried real samples.
  - Signal loss, all four §7.3 cases exercised and recorded server-side (heartbeat,
    session count, whole input image): A kill -9, B SIGTERM, C double stopped and
    restarted (reconnect, refresh, heartbeat continued at 293, no auto-resume),
    D sim killed (heartbeat kept advancing 326 -> 929, input image frozen).
  - Write allowlist refused all five non-writable nodes on the client side
    (WriteNotPermitted) and on the server side (BadUserAccessDenied).

open_questions:
  1. STALE PATHS IN docs/interfaces/bridge-design.md (not my file to edit). §9.4 still
     names fleet/bridge/EVIDENCE_LATENCY.md and fleet/bridge/evidence/, §1 and §10 still
     say fleet/bridge/, and §12 open item 1 still asks for an exception line in
     fleet/README.md. ADR 0005 D1 superseded all of that: the deliverables are at
     bridge/, and fleet/README.md needs NO exception. Item 2 of that list should be
     marked resolved-by-ADR-0005.
  2. MEASUREMENT DEFINITION, L1. §9.2 defines L1 as ending at "the start of the cycle
     that writes it". With the ROS callbacks on their own thread a sample can arrive
     after the cycle start and still be the one written, which makes that interval
     negative (observed down to -45.9 ms). The bridge records BOTH: L1 ending at the
     instant the cycle takes the sample out of its slot (the true hold time, reported in
     the table) and L1cs ending at the cycle start (the literal wording, in the raw CSV,
     unclipped). Recommend amending §9.2 to the slot-take wording.
  3. SESSION BEHAVIOUR ON SIGKILL. §7.3 A predicts the server holds the session until
     timeout. Over loopback the double saw the session drop within 2 s, because SIGKILL
     closes the socket at OS level. The design's expectation holds for host/network loss,
     not process death on a live host. It does not change the conclusion (heartbeat is
     the indicator; A and B stay indistinguishable). Must be re-checked against the real
     S7-1500 server (EVIDENCE_LATENCY.md Section B item 7).
  4. L7 (closed loop) NOT MEASURED. It needs a server that responds to a nominated input;
     against the double it would be a transport floor, not a loop time (§9.5), and the
     brief scoped the run to L1/L2/L3/L5/L6. The hook exists and is verified working
     (test double --echo-input, labelled S3 scaffolding). Owner or a later brief takes it.
  5. RAW EVIDENCE FILE SIZE. evidence/latency-2026-07-27.csv is 6.8 MB / 76 191 rows.
     It is the raw file the design requires; if the owner prefers it compressed or
     truncated in version control, say so and it will be regenerated accordingly.
  6. CLAUDE.md FOLLOW-UP (already noted in ADR 0005, restated because it is now real):
     section 4 needs a bridge/ entry and section 5 a bridge agent owning bridge/.
     CLAUDE.md is the owner's file.
  7. ENVIRONMENT NOTE. asyncua could not be installed system-wide: pip 24.0 refuses to
     replace the Debian-packaged cryptography 41.0.7 (no RECORD file). Installed instead
     into /opt/amr-bridge-venv, created with --system-site-packages so the same
     interpreter imports rclpy from the sourced ROS 2 installation. Recorded in
     requirements.txt. The venv lives outside the repository.
  8. NOT PROVEN, AND SAID SO EVERYWHERE: the PLC program. The double has no scan cycle,
     no process image and no program, so DemoCell/Status/* and BridgeLinkOk stayed False
     for every run. The gate closes on the owner's PLCSIM run (Section B).

next_suggested:      m3-05 writes plc/demo-cell/SPEC.md against §7.4 and the case D
                     drive-fault observation recorded in EVIDENCE_SIGNAL_LOSS.md.
