# PLAN

## Current gate: M3 — Fixed equipment I/O loop (in progress)

Gate order follows ADR 0004. A Gazebo world of fixed equipment only
(conveyor, product sensor, operator panel equivalent), a bridge process
translating between Gazebo (ROS 2) and the PLC as an OPC UA client to the
S7-1500 OPC UA server on PLCSIM Advanced, and all control logic in the TIA
Portal program.

Exit criterion — all four demonstrated and recorded:

1. Gazebo sensor state visible as PLC input bits in a TIA watch table.
2. PLC output bits driving the Gazebo actuator, verified visually.
3. Latency and update rate measured and written down.
4. Signal-loss behaviour defined and tested: what the PLC sees when the
   bridge stops, and what the equipment does.

## Briefs to close M3

1. m3-01 sim — fixed-equipment Gazebo world (conveyor, product sensor,
   operator panel equivalent), no vehicle.
2. m3-02 interface — OPC UA node model extension for the demonstration
   cell's fixed-equipment I/O nodes.
3. m3-03 fleet — bridge design document, written and reviewed before any
   bridge code.
4. m3-04 fleet — bridge implementation against that design.
5. m3-05 plc — PLC program specification. Closed 2026-07-27, with correction
   briefs m3-03c/d/e (bridge-design paths, residuals, staleness sweep).
6. m3-06 verifier — verification of the four exit items. Closed 2026-07-27:
   pass-with-findings, 25 of 26 checks, loop re-run live under WSL.
7. m3-07 infra — WSL toolchain rebuild and deviations. Closed 2026-07-27.
8. m3-08 infra — WSL loop re-run with evidence. Closed as satisfied
   2026-07-27 without its own brief: m3-13 delivered a dated WSL Section C in
   EVIDENCE_LATENCY.md, and the m3-06 verification re-ran the full loop live
   under WSL from committed instructions with the measurements recorded in
   its report. A separate re-run would have re-measured the same thing.
9. m3-09 infra — root .gitattributes. Closed 2026-07-27.
10. m3-10 sim — /cell/panel/reset contact. Closed 2026-07-27.
11. m3-11 interface — DemoCell/Input/PanelResetPressed. Closed 2026-07-27.
12. m3-12 plc — SPEC.md reset retargeted onto the real contact. Closed
    2026-07-27.
13. m3-13 bridge — reset bridged, machine-neutral paths. Closed 2026-07-27.

Briefs 10 to 13 exist because m3-05 found the cell had no reset device and had
to conflate the monitored reset onto the start button. The owner ruled on
2026-07-27 that the cell gets a real reset contact, which is why the sim, the
node model, the spec and the bridge each took one brief. CLAUDE.md §9 requires
a separate monitored reset; a conflated one satisfied it only in spirit.

14. m3-14 to m3-17 — ADR 0006 and the namespace correction (URN could not
    exist on a TIA server interface; live URI is http://DemoCell). Closed
    2026-07-27, with the m3-06 residual cleanups (hold-time wording, L6
    scenario-dependence note).
15. m3-18 interface — opcua-nodes.md commissioning corrections (browse path
    under ServerInterfaces, §9.8 scoped, environment record). Closed
    2026-07-27.
16. m3-19 interface — bridge-design.md commissioning corrections (dual
    namespace resolution by URI, granted session-timeout keep-alive). Closed
    2026-07-27.
17. m3-20 bridge — commissioned-environment record in both EVIDENCE files.
    Closed 2026-07-27; found that bridge.yaml still browses DemoCell from
    Objects with one namespace index, so Section B waits on m3-21.
18. m3-21 bridge — connect conformance against the test double. Closed
    2026-07-27, evidenced in bridge/EVIDENCE_CONNECT.md (both clamp
    directions, 22/22 checks, 800-cycle loop at 20.0 Hz).
19. m3-22 interface — bridge-design.md sync (§12 item 9, §9.4 evidence
    table). Issued.
20. m3-23 verifier — M3 agent-side verification pass. Queued, after m3-22.

Container evidence (briefs 3 and 4) is retained beside the WSL evidence, not
replaced by it.

Owner phase 0 closed 2026-07-27: TIA Portal V21 + PLCSIM Advanced V7.0,
CPU 1513-1 PN FW V3.1, endpoint opc.tcp://192.168.53.1:4840 verified by an
independent asyncua client reading all 15 DemoCell nodes. Phase 0 proves
endpoint and node exposure only, no program logic.

Remaining before the gate can close: briefs m3-18 to m3-21, then the owner's
OB30 program build per plc/demo-cell/SPEC.md (tags §3.2, logic §6.1 onward)
and the PLCSIM run with the bridge on the verified endpoint (exit items 1
and 2, Section B of EVIDENCE_LATENCY.md, PLCSIM section of
EVIDENCE_SIGNAL_LOSS.md), then a verifier pass.

The TIA Portal implementation and the PLCSIM Advanced run are owner-executed.
The four exit items are therefore demonstrated by the owner against the
delivered artifacts, not by an agent.

Filename note: existing brief and report filenames are kept as written. The
older m3-* sim briefs and reports (warehouse world, headless bringup,
navigation scenario) belong to what is now M5 — Simulated vehicle, despite
their m3 prefix.

M0–M2 closed 2026-07-26 (reports m0-04/07/09, m1-04, m2-02).
Session mode: owner-approved autonomous run; TIA Portal implementation and
the PLCSIM run remain with the owner.
