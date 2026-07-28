# PLAN

## Current gate: M3 — Fixed equipment I/O loop (in progress)

Gate order follows ADR 0007, which supersedes ADR 0004's order (safety layer
moved to M4, demonstration to M9, arm to M10, Hermes to M11 and parked; M5 to
M8 unchanged). A Gazebo world of fixed equipment only
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
    2026-07-27, evidenced in bridge/EVIDENCE_CONNECT.md (grants below and
    above the request, 800-cycle loop at 20.0 Hz).
19. m3-22 interface — bridge-design.md sync (§12 item 9, §9.4 evidence
    table). Closed 2026-07-27.
20. m3-23 verifier — commissioning-chain verification. Closed 2026-07-27,
    pass-with-findings; the harness re-run reproduced the committed
    evidence value for value.
21. m3-24 bridge — wording corrections from the m3-23 findings (clamp
    described one-directionally in the evidence files, bridge.yaml endpoint
    comment, non-reproducible check count). Closed 2026-07-27.

22. m3-25 plc — SPEC.md reconciled with the commissioned implementation
    (§7 dwell-timer defect, §6.2 open item 1). Closed 2026-07-27; found a
    third defect, recorded as §12 open item 5.
23. m3-26 bridge — live loop against the commissioned PLC. Closed
    2026-07-27: end to end over 502 s, 20 Hz, 0 overruns; Section B filled
    for what a bridge can measure; found program defects F1 (product
    detection never asserts) and F2 (signal-loss case D blind mid-motion).
25. m3-28 verifier — independent review of T1-T4 as specified vs as run.
    Closed 2026-07-28: F1 is a program defect (SPEC exonerated, one
    watch-table observation discriminates), F2 is a spec defect (§6.6's
    one-shot D2 window, generalised from a parked-belt capture).
26. m3-29 plc — case-D detection re-specified to work mid-motion (re-armed
    freeze window, ≤3.2 s bound). Closed 2026-07-28.
27. m3-30 bridge — Section B accounting corrections. Closed 2026-07-28;
    found three more unproven figures and fixed them in the same pass.
28. m3-31 plc — §11 pass-string accounting. Closed 2026-07-28; every pass
    count now derives from its own step table and every caveat terminates
    in F1, the owner-side presence defect.
29. m3-32 bridge — outstanding rows for the re-specified case-D tests.
    Closed 2026-07-28; noted T4.6b additionally depends on the F1 fix.
24. m3-27 plc — plausibility windows for the belt feedback signals, from
    m3-25's finding. Closed 2026-07-27; recorded §12 open item 6, a
    fault-injection request against bridge/.

30. m3-33 bridge — the 2026-07-28 owner session written into the evidence
    (Section B part 2, signal-loss PLCSIM section, 4.6 = 2.301 s from the
    20 Hz CSV). Closed 2026-07-28.
31. m3-34 plc — link boot polarity, per-link-session reset guard, T4.11b
    split (T4 denominator 14). Closed 2026-07-28; owner delta is SPEC §6.8.
32. m3-35 bridge — session-lifecycle conformance (reconnect, rewrite-on-
    restart, per-session CSVs). Issued.
33. pub-01/pub-02 — publication audit and public README (owner-directed,
    not gate work). Issued.

34. m3-35 bridge — session-lifecycle conformance. Closed 2026-07-28: all
    three behaviours proven against the double (in-flight reconnect,
    7-of-7 slot rewrite on server restart, per-session evidence files).
35. m3-36 bridge — the §6.8 rebuild re-runs written into the evidence.
    Issued 2026-07-28, interrupted by an API session limit and resumed.

The owner's §6.8 rebuild landed 2026-07-28 and all five re-runs passed
against it: 4.8 (R3 input by input), 4.2 (30 s hands-off, no resume), 4.3
(reset moves nothing, separate start runs), 4.9b **in its bridge-restart
form** — the form m3-34 predicted the defect would relocate to — where a
reset held from before link-up no longer clears any latch, and 4.5 where the
bridge detected a restart under a live session and rewrote 7 of 7 inputs in
milliseconds against build C's 4 min 31 s, with `CellProcessStopActive`
staying FALSE as the corrected signature requires.

Remaining to close M3, in order:
1. m3-36 lands (in flight).
2. The gate verifier runs. It has not run against this state and the gate is
   NOT closed until it does — including its ruling on the two items that
   stay outstanding: T4.11's reaction re-record with a per-session CSV, and
   T4.11b, which needs the fault-injection facility of SPEC §12 item 6.
3. Only then may M4 open (ADR 0007), whose first brief must settle the
   F-CPU-on-PLCSIM question in the tool.

The PLC program was built and verified running on PLCSIM on 2026-07-27:
FB_DemoCellControl from OB30 at 20 ms, CPU in RUN, cold-start state read
independently and matching the specification. The gate's remaining
demonstration is T1 to T4 end to end.

Container evidence (briefs 3 and 4) is retained beside the WSL evidence, not
replaced by it.

Owner phase 0 closed 2026-07-27: TIA Portal V21 + PLCSIM Advanced V7.0,
CPU 1513-1 PN FW V3.1, endpoint opc.tcp://192.168.53.1:4840 verified by an
independent asyncua client reading all 15 DemoCell nodes. Phase 0 proves
endpoint and node exposure only, no program logic.

Remaining before the gate can close: the owner's OB30
program build per plc/demo-cell/SPEC.md (tags §3.2, logic §6.1 onward) and
the PLCSIM run with the bridge on the verified endpoint — exit items 1 and
2 plus EVIDENCE_LATENCY.md Section B in full (item 5 covers all seven
inputs; item 6 is the signal-loss repeat against the seven-node image —
EVIDENCE_SIGNAL_LOSS.md has no separate PLCSIM section, per m3-23) — then
verification of the owner evidence.

The TIA Portal implementation and the PLCSIM Advanced run are owner-executed.
The four exit items are therefore demonstrated by the owner against the
delivered artifacts, not by an agent.

Filename note: existing brief and report filenames are kept as written. The
older m3-* sim briefs and reports (warehouse world, headless bringup,
navigation scenario) belong to what is now M5 — Simulated vehicle, despite
their m3 prefix. m4-00-hermes-survey.* belongs to what is now M11, the parked
Hermes gate, not to M4.

## Next gate: M4 — Safety layer on the fixed cell (F-CPU)

Not open. It opens when M3 is verified closed. Its exit criterion is the M4 row
of docs/roadmap.md: AT-01, AT-07 and AT-08 passing on PLCSIM Advanced with
their standard-program-in-STOP sub-cases, the same reactions with the bridge
stopped and the OPC UA session down, read-only `Safety/` mirrors, and a
recorded cell + safety showcase. Brief list to be written when the gate opens;
per ADR 0007 the first brief settles in TIA Portal and PLCSIM Advanced whether
an F-CPU safety program can be executed with simulated F-I/O and PROFIsafe,
before any safety logic is written. M4 delivers cell-scope functions only —
SF-05 and SF-06 land at M8 and the vehicle chain at M5 and M6.

M0–M2 closed 2026-07-26 (reports m0-04/07/09, m1-04, m2-02).
Session mode: owner-approved autonomous run; TIA Portal implementation and
the PLCSIM run remain with the owner.
