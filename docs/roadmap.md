# Roadmap

Current gate: M4 — Forklift commissioning cell (ADR 0008), **closing**. The
gate's criteria are unchanged and the agent-side work is complete; what remains
is the owner's recorded commissioning showcase and the m4f-09 gate verification.

Gate order follows ADR 0010
(docs/adr/0010-milestone-restructure-forklift-first.md), which supersedes the
gate order above M3 set by ADR 0008 D1
(docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md), which extended
ADR 0007 (docs/adr/0007-safety-first-gate-order.md), which in turn superseded
the order of ADR 0004 (docs/adr/0004-gate-reordering-plc-loop-first.md). The
order it sets: the fixed-equipment Gazebo-to-PLC signal loop is proven first,
then the same cell gains a teleoperated forklift plant, then sensors, safety and
autonomy land **on that forklift**, then the fleet at scale, then the LLM
operations layer, which carries the final demonstration as its closure. ADR 0010
also supersedes the platform selection of ADR 0002
(docs/adr/0002-vehicle-platform.md) — RB-KAIROS is retired and the in-house
forklift is the vehicle platform from M5 onward — and removes the arm gate. The
rest of ADR 0008 (D2 the commissioning-HMI layer, D3 the process-logic ruling,
D4 in-house model sourcing) stays binding, and ADR 0007's showcase rule is
unchanged.

ADR 0009 (docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md,
accepted) is **extended, not superseded**. Its early opening of the cell-scope
functions (SF-01, SF-08, the SF-07 pattern) on the forklift twin, built under
its fallback rule while M4 is still the current gate, becomes the new M5's own
subject matter; its D1 scope boundaries, D3 coupling architecture and D5 wording
discipline carry into M5 word for word, and its fallback rule retires once M4
closes.

The feasibility checkpoint ADR 0007 attached to the safety layer — whether
PLCSIM Advanced can execute an F-CPU safety program — is **substantially
closed** by the tool observations of 2026-07-29 recorded in ADR 0009's context:
the project compiled with its F-runtime group, the CPU reached RUN with that
group executing, and the F-logic latched and demanded a reset end to end. What
stays open is the **formal acceptance procedure** — the AT sub-cases, the
standard-program-in-STOP sub-case (B3), and the reactions executing with the
bridge stopped and the OPC UA session down — and that is M5 work.

M0 closed 2026-07-26, verified in docs/reports/m0-04-verify.md.
M1 closed 2026-07-26, verified in docs/reports/m1-04-verify.md.
M2 closed 2026-07-26, verified in docs/reports/m2-02-verify.md.
M3 closed 2026-07-28, verified in docs/reports/m3-37-gate-verification.md (pass-with-findings).

| Gate | Deliverable | Closes when |
|---|---|---|
| M0 | Repo skeleton, ADR 0001 recording the invariants | Structure exists, invariants committed |
| M1 | Interface contracts | VDA 5050 subset and OPC UA node model documented and reviewed |
| M2 | Safety requirements spec | Every safety function has a trigger, a reaction and an acceptance test |
| M3 | Fixed equipment I/O loop | All four are demonstrated and recorded: (a) Gazebo sensor state is visible as PLC input bits in a TIA watch table, (b) PLC output bits drive the Gazebo actuator, verified visually, (c) latency and update rate are measured and written down, (d) signal-loss behaviour is defined and tested — what the PLC sees when the bridge stops, and what the equipment does |
| M4 | Forklift commissioning cell | An operator drives the in-house forklift model in Gazebo from the commissioning HMI, every command passing HMI → PLC standard program → bridge → simulation and every state report returning simulation → bridge → PLC: (a) teleoperated drive with the PLC forming all motion setpoints, (b) the fork raised to a commanded height and stopped by the PLC's soft travel limits, (c) traction speed capped by the PLC while the fork is above its height threshold, (d) an obstacle entering the lidar stop zone latching a PLC process stop that overrides teleop, cleared only by the edge-triggered monitored reset after the zone clears, (e) loss of the HMI heartbeat zeroing all motion setpoints within the watchdog period; and a **recorded commissioning showcase** demonstrates (a)–(e), naming each reaction as standard-program process logic, not a safety function |
| M5 | Sensored autonomous forklift | On the M4 forklift twin: (a) a safety laser scanner is added to the model and its signals reach the F-CPU safety program's F-blocks, a protective-field intrusion tripping an F-latched stop that overrides teleop and autonomous motion, cleared only by the edge-triggered monitored reset after the field clears; (b) the SRS cell-scope functions SF-01, SF-07 and SF-08 pass their acceptance tests AT-01, AT-07 and AT-08 on PLCSIM Advanced including the standard-program-in-STOP sub-case, the reactions execute with the bridge stopped and the OPC UA session down, and the `Safety/` mirrors remain read-only; (c) a navigation lidar is added, each sensor's data is verified correct as its own step before anything builds on it, and the sensor beams are visible in the Gazebo GUI; (d) SLAM builds a map of the arena and Nav2 drives the forklift autonomously to commanded goals, with AT-02, AT-03 and AT-04 passing and the inhibit demonstrably acting below the navigation stack; (e) the HMI, inherited from M4 and visually reduced, selects the drive mode (teleop / autonomous), shows a real-time map with live obstacles, and carries an emergency button that issues a process stop and displays F-layer state — never a safety function over the network (invariant 1, ADR 0010 D6(b)); and a **recorded safety + autonomy showcase** demonstrates (a)–(e), naming which reactions are F-CPU safety functions and which are process behaviour. The map-view data path is decided by its own ADR at M5 briefing (ADR 0010 D6(a)) |
| M6 | VDA 5050 fleet at scale | An enlarged warehouse world with five loading stations, five unloading stations and four forklifts: the fleet manager assigns transport orders over VDA 5050 / MQTT and traffic conflicts are avoided; the PLC owns the stations' fixed equipment and serves OPC UA, the fleet manager subscribes, and the station handshake works end to end; AT-05, AT-06 and AT-09 pass (broker killed: controlled stop within the watchdog period, order kept, SF-03 still acting during the outage), and the fixed-equipment F-I/O behind SF-05 and SF-06 lands with the stations; and a **recorded fleet showcase** shows orders, traffic and the station handshake in one run. Entry condition: an owner-ruled deep-research brief precedes any implementation (ADR 0010 D3, D6(d)) |
| M7 | LLM operations layer and final demonstration | An LLM agent supervises the running cell in real time, takes safe actions through the fleet layer only and alerts the operator; it never writes actuator outputs, never bypasses PLC interlocks, and the system operates normally with the LLM and its transport unreachable; the gate closes with the **recorded end-to-end demonstration**, the validation report and the README architecture narrative, the run showing B4 with both chains live (the cell e-stop does not stop a vehicle, the vehicle chain does not depend on the cell) and the cell operating normally with the fleet layer and all remote access unreachable. Entry condition: the owner decisions in docs/reports/m4-00-hermes-survey.md §6 are ruled (ADR 0010 D4, D6(c)) |

A gate closes only when its criterion is observable behavior, not written code.

Four recordings are embedded in gate criteria rather than deferred to the end:
the commissioning showcase at M4, the safety + autonomy showcase at M5, the
fleet showcase at M6, the end-to-end demonstration at M7. A phase gate does not
close on an unrecorded run. The end-to-end demonstration is no longer a gate of
its own; it is M7's closure, and the three earlier recordings stand as watchable
artifacts rather than being compiled a second time.

The safety layer is not complete at M5, and it is not confined to it either. M5
delivers the cell-scope functions the twin's equipment can carry — SF-01, SF-07
and the cell instance of SF-08 — and, on the same forklift, the vehicle chain:
SF-02, SF-03, SF-04 and the vehicle instance of SF-08. SF-09, the supervision
watchdog that is a boundary pin rather than a safety function, lands at M6, and
the fixed-equipment functions SF-05 and SF-06 complete at M6 with the stations
that give them their process purpose. SF-20…29, the reserved arm functions, are
out of scope: ADR 0010 D5 removes the arm gate and directs docs/safety/SRS.md to
mark those functions rather than delete them, so the analysis survives without a
roadmap row implying it is scheduled. ADR 0007 §2 holds the per-function split;
its boundary statements land, under the numbering below, as B1 at M5 and again
at M6, B2 at M6, B3 at M5 for SF-01/07/08 and at M6 for SF-05/06, and B4 at M7,
still the one statement that needs both chains alive at once.

Four decisions are recorded as open, not resolved (ADR 0010 D6). **(a)** The
HMI's real-time map view has no data path: the topology gives the HMI one edge,
to the PLC, and a SLAM map cannot realistically transit OPC UA process nodes;
invariant 11 is not amended by naming the gap. Ruled by the owner, by its own
ADR, at M5 briefing. **(b)** The HMI emergency button is read under invariant 1
as a process stop command plus a display of F-layer state, never a safety e-stop
over the network; anything beyond that reading is an invariant change needing
its own ADR, and that change is not being made. Ruled by the owner, if ever
wanted, by its own ADR; not scheduled. **(c)** The LLM layer's attachment point
and topology edge, per the decision list in docs/reports/m4-00-hermes-survey.md
§6. Ruled by the owner at M7 briefing. **(d)** Whether M6 is one gate or staged.
Ruled by the owner on the M6 deep-research brief's findings, at M6 briefing.

Renumbering, three rounds, none of which touched M0 to M3. The first, under
ADR 0007, moved four rows out of the ADR 0004 order: the safety layer came
forward to M4, the demonstration went to M9, arm integration to M10 and the
Hermes command path to M11, while the four gates between kept their numbers.
The second, under ADR 0008, inserted the forklift commissioning cell as a new M4
and pushed everything above M3 up by one, so the safety layer became M5, the
simulated vehicle M6, the VDA 5050 client M7, the fleet manager M8, PLC
integration M9, the demonstration M10, arm integration M11 and the Hermes
command path M12, still parked and still last. The third, under ADR 0010, is a
collapse rather than a shift: the safety layer and the simulated vehicle merge
into the new M5 and land on the forklift twin instead of the fixed cell; the
VDA 5050 client, the fleet manager and PLC integration merge into the new M6;
the demonstration ceases to be a gate and becomes the closure of the new M7,
which is the LLM operations layer — the old Hermes gate, unparked and absorbed;
and arm integration is removed from the roadmap entirely rather than parked.

Existing brief and report filenames are kept as written, so a filename's number
names the round it was written under rather than the gate it now serves.
m4-00-hermes-survey.* belongs to the LLM operations layer, now M7. The m4r-*
files belong to the ADR 0007 round and the m4r2-* and m4f-* files to M4. The
m5a-* files belong to the ADR 0009 early opening, whose content is now M5's, and
the m5r-* files to this ADR 0010 restructure round. The older m3-* sim files —
the warehouse world, the headless bringup and the navigation scenario, parked
unverified when M3's scope was corrected — belong to M5.
