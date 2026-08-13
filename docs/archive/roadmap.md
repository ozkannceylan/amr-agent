> **ARCHIVED 2026-08-13.** Historical record of the claude-supervised
> era (M0-M5 as originally planned). It is not maintained. Current
> status and the roadmap live in the root [README](../../README.md).

# Roadmap

Current gate: M5 — Sensored autonomous forklift (ADR 0010 D2, architecture ruled
by ADR 0011). M4 — Forklift commissioning cell (ADR 0008) — is **closing**: its
criteria are unchanged and the agent-side work is complete, and it closes on the
owner's recorded commissioning showcase and the m4f-09 gate verification.

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
its fallback rule ahead of M4's closure, becomes the new M5's own
subject matter; its D1 scope boundaries, D3 coupling architecture and D5 wording
discipline carry into M5 word for word, and its fallback rule retires once M4
closes.

ADR 0011 (docs/adr/0011-sensored-autonomy-architecture.md, accepted 2026-07-30)
extends ADR 0009, renumbers nothing, and settles the architecture inside M5
without changing the gate's criteria. Four rulings: the forklift's F-runtime
group is the **vehicle's own onboard safety controller**, so the
scanner-to-stop chain is internal to the vehicle (D1); the scanner reaches the
F-program through a **configured F-DI stimulated by the PLCSIM Advanced API by
tag name**, conditional on this tool's safety system version supporting F-I/O
simulation and on the API writing those channel values — settled in the tool by
the first M5 brief, with the labelled standard-DB stand-in as the named
fallback (D2; **settled 2026-08-04: the probe answered no**, and ADR 0015 below
records the resolution — the automated stand-in stimulus and the amended
criterion (a)); in autonomous mode the PLC forms and owns a **motion envelope** —
motion enable, speed ceiling, zone permit — while the navigation loop closes
onboard at its own rate, the M4 teleop phrasing standing unchanged (D3); and map,
pose and obstacle data reach the operator over a **read-only monitoring plane**
that has no write endpoint and no publisher and carries no command in either
direction, the process plane HMI → PLC → bridge → vehicle remaining the only
command path (D4). The claim boundary is D5: M5 states **PLr targets derived
from the documented risk assessment and claims no achieved PL, Category, SIL or
PFH**, and claims no safety acceptance test and no program signature, for as
long as the project is hardware-free. The single 1513F-1 PN hosting that onboard
safety controller is a **simulation artifact**, disclosed as one wherever the
twin is described and never an architectural claim that one F-CPU guards a
fleet: one simulated CPU carries what the architecture calls per-vehicle safety,
so the cell and vehicle chains share an execution substrate in simulation — the
M7 statement B4 holds architecturally but not at that execution layer (ADR 0011
D1, ADR 0012 D2).

ADR 0012 (docs/adr/0012-envelope-composition.md, accepted 2026-07-31) refines
ADR 0011 D3 in one clause and supersedes nothing: the envelope's third element
is a **fixed-equipment / station permit** — the PLC's statement that the
equipment it owns is ready for the vehicle to act on it — and not a zone permit,
because zone reservation belongs to the fleet manager under invariant 5 and one
datum has one owner under invariant 10.

ADR 0013 (docs/adr/0013-vendor-portability-gate.md, accepted 2026-07-31) adds a
gate and supersedes nothing: a second, **Beckhoff/TwinCAT implementation of the
PLC layer**, placed **after the main line** rather than inside it. It takes the
number **M8** here, because this document is the single source for gate
numbering and ADR 0013 D1 assigned none; M0–M7 keep their numbers and no
existing criterion is changed, so this is an addition and not a renumber. The
placement is the decision it makes. The safety half of the mirror depends on the
TwinSAFE logic simulator **TE9100**, which is at product-announcement status
with its release date *"on request"* (verified 2026-07-31, mv-01 §B.2), and a
gate placed between M5 and M6 would put a vendor's unannounced schedule in front
of the fleet gate, the LLM gate and the recorded end-to-end demonstration behind
them; after the main line, waiting costs the project nothing. Two properties of
the M8 row below come from the ADR rather than from its criterion list: the
**stage-0 owner probe is a hard precondition** — nothing in the design is built
before an installed TwinCAT states its own namespace URI, BrowseNames, runtime
form and licence demands, on the ADR 0006 discipline (D5.1) — and the **drift
check** between the two implementations and docs/interfaces/opcua-nodes.md is a
**deliverable of the gate**, not a review habit, because M6's station handshakes
land in the node model before the mirror is built (D5.2). Whether M8
additionally carries a showcase recording in ADR 0007's sense is not ruled here;
its criterion closes on committed evidence.

ADR 0014 (docs/adr/0014-motion-control-locus.md, accepted 2026-07-31) confirms
ADR 0011 D3 as refined by ADR 0012 D1 and supersedes nothing: motion control
**closes onboard the vehicle**, and **no motion value at any granularity crosses
the OPC UA seam** — the vehicle receives the envelope and the mode in force and
returns its applied mode and a heartbeat. It records the rejection of the
incremental-work alternative with the argument that decided it, so the question
is reopened only on new evidence; and it **bounds how ADR 0011 D1's word
"onboard" is read**: that word covers the F-runtime group `F_Forklift_Safety`
and nothing else, because the **standard program is the cell's PLC** — the owner
of the fixed equipment, the OPC UA server of invariant 4, and at M6 one box
serving four vehicles. ADR 0011 is not edited. No gate criterion is changed; the
D5 narration obligation carried in the M5 row below is a statement the showcase
must make.

ADR 0015 (docs/adr/0015-criterion-a-standin-stimulus.md, accepted on the
owner ruling of 2026-08-04) partially supersedes ADR 0011 D2 and **amends the
M5 row's criterion (a)** — the only criterion text any ADR has changed. The
m5-03 probe (docs/reports/m5-03-fio-probe-run.md;
plc/forklift-safety/FIO-FEASIBILITY.md §7) settled D2's condition in the tool,
and the answer was no twice over: the configured F-DI never leaves passivation
on this installation (`QBAD` = `PASS_OUT` = 1 throughout, with no fault
declared anywhere a diagnostic reader would look), and D2's named fallback —
the stand-in driven by watch-table *Modify* — could not have run as written,
because the tool refuses fail-safe *Modify* outright in permanent safety mode
(`2206:000002`). The owner ruled both remedies: the stimulus is **automated**
— the API writes the labelled standard-DB stand-in by tag name with no human
in the loop, proven in the consumer's view and against an independent OPC UA
witness (docs/reports/m5-03b-standin-stimulus-proof.md, to be repeated on the
working project before the gate cites it) — **and** criterion (a) is amended
to name that path honestly. What is superseded in ADR 0011 D2 is its
"changes no gate criterion" claim and the fallback's *Modify* mechanism;
D2's "the fallback does not reopen D1" clause holds, and the path buys **no
safety integrity**: it is a standard DB under ADR 0011 F6 and D5's claim
boundary, carrying the S015 validity check visibly in the F-code.

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
| M5 | Sensored autonomous forklift | On the M4 forklift twin: (a) a safety laser scanner is added to the model and its simulated signal reaches the F-CPU safety program's F-blocks through the **labelled standard-DB stand-in** `SafetyInputStandIn`, written **by the S7-PLCSIM Advanced API by tag name with no human in the loop** — configured F-I/O is not used, because the m5-03 probe proved the simulated F-DI stays passivated on this installation (ADR 0015) — and F-logic demonstrably executes on it: a protective-field intrusion in Gazebo trips an F-latched stop that overrides teleop and autonomous motion **with no hand at a watch table anywhere in the chain**, the demand and its clearance are read in the **consumer's view** (the F-block instance data) and corroborated on an **independent witness that does not expose the stand-in DB** (the CPU's own OPC UA `Safety/` mirrors), and the stop is cleared only by the edge-triggered monitored reset after the field clears; the stand-in carries the **S015 validity check visibly in the F-code**, is **named a stand-in in the showcase narration wherever the path is described**, and demonstrates **F-logic execution only — no safety integrity, no PL, Category, SIL or PFH** (ADR 0011 D5, F6); (b) the SRS cell-scope functions SF-01, SF-07 and SF-08 pass their acceptance tests AT-01, AT-07 and AT-08 on PLCSIM Advanced including the standard-program-in-STOP sub-case, the reactions execute with the bridge stopped and the OPC UA session down, and the `Safety/` mirrors remain read-only; (c) a navigation lidar is added, each sensor's data is verified correct as its own step before anything builds on it, and the sensor beams are visible in the Gazebo GUI; (d) SLAM builds a map of the **warehouse world** — the M5 autonomy environment by owner ruling, because autonomy needs aisles and racks to be meaningful and M6 enlarges that same world to ten stations, so the map and the Nav2 tuning carry forward; the commissioning arena keeps its M4 role — and Nav2 drives the forklift autonomously to commanded goals, with AT-02, AT-03 and AT-04 passing and the inhibit demonstrably acting below the navigation stack; (e) the HMI, inherited from M4 and visually reduced, selects the drive mode (teleop / autonomous), shows a real-time map with live obstacles, and carries an emergency button that issues a process stop and displays F-layer state — never a safety function over the network (invariant 1, ADR 0010 D6(b)); and a **recorded safety + autonomy showcase** demonstrates (a)–(e), naming which reactions are F-CPU safety functions and which are process behaviour, and stating that in autonomous mode the PLC's authority over motion is **permissive and checked, not compelled** — the PLC forms the envelope and does not enforce it, the enforcing gate runs on the vehicle, and the compelling backstop is the safety layer, which in this project is modelled rather than real (ADR 0014 D5); the narration says so where the autonomy is shown rather than leaving it implicit. The map-view data path is the read-only monitoring plane of ADR 0011 D4, which closes ADR 0010 D6(a) |
| M6 | VDA 5050 fleet at scale | An enlarged warehouse world with five loading stations, five unloading stations and four forklifts: the fleet manager assigns transport orders over VDA 5050 / MQTT and traffic conflicts are avoided; the PLC owns the stations' fixed equipment and serves OPC UA, the fleet manager subscribes, and the station handshake works end to end; AT-05, AT-06 and AT-09 pass (broker killed: controlled stop within the watchdog period, order kept, SF-03 still acting during the outage), and the fixed-equipment F-I/O behind SF-05 and SF-06 lands with the stations; and a **recorded fleet showcase** shows orders, traffic and the station handshake in one run. Entry condition: an owner-ruled deep-research brief precedes any implementation (ADR 0010 D3, D6(d)) |
| M7 | LLM operations layer and final demonstration | An LLM agent supervises the running cell in real time, takes safe actions through the fleet layer only and alerts the operator; it never writes actuator outputs, never bypasses PLC interlocks, and the system operates normally with the LLM and its transport unreachable; the gate closes with the **recorded end-to-end demonstration**, the validation report and the README architecture narrative, the run showing B4 with both chains live (the cell e-stop does not stop a vehicle, the vehicle chain does not depend on the cell) and the cell operating normally with the fleet layer and all remote access unreachable. Entry condition: the owner decisions in docs/reports/m4-00-hermes-survey.md §6 are ruled (ADR 0010 D4, D6(c)) |
| M8 | Vendor portability: a second, Beckhoff/TwinCAT implementation of the PLC layer | Placed after M6 and M7 by ADR 0013 D1, so no gate on the main line waits on a vendor's release date. Entry condition: the **stage-0 owner probe** has run in an installed TwinCAT and its tool-derived facts are recorded in their own ADR — nothing in the design is built before it (ADR 0013 D5.1). The criterion is written entirely over the **standard program**, and the gate closes when all five are demonstrated and captured in committed evidence: (a) the same **byte-identical bridge and commissioning HMI** establish sessions against both controllers, differing only in the configuration values those clients already hold as data — endpoint, namespace URIs, browse path to the interface node — and the existing connect-conformance instrument passes against **each** server, one evidence file per vendor; (b) the M4 forklift scenario procedures plc/forklift/SPEC.md §11 T5.1–T5.6 run to their recorded outcome against the TwinCAT controller in its **own session**, the Siemens evidence kept beside the new set and each file stating the environment that produced it, including the qualifier "user-mode runtime, no real time" on the TwinCAT session; (c) the controller in force is selected at **system startup and immutable for the session**, and the **server-reported** controller identity is visible throughout every recorded run; (d) the **drift check** between the two implementations and docs/interfaces/opcua-nodes.md runs and passes, reading the node model as its reference — a deliverable of this gate (ADR 0013 D5.2); (e) the public claim landed in the repository states the **asymmetry** — the F-safety layer exists on the Siemens controller only — with the TE9100 status quoted and dated. If TE9100 has shipped when the gate opens, the safety mirror **widens the demonstration** and conditions no criterion item; if it has not, every item above stands unchanged (ADR 0013 D2) |

A gate closes only when its criterion is observable behavior, not written code.

Four recordings are embedded in gate criteria rather than deferred to the end:
the commissioning showcase at M4, the safety + autonomy showcase at M5, the
fleet showcase at M6, the end-to-end demonstration at M7. A phase gate does not
close on an unrecorded run. M8 sits outside that count: its criterion closes on
committed evidence, and whether it additionally carries a showcase recording in
ADR 0007's sense is open (ADR 0013). The end-to-end demonstration is no longer a gate of
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

Of the four decisions ADR 0010 D6 recorded as open, one is closed and three
remain open. **(a)** The HMI's real-time map view had no data path: the topology
gave the HMI one edge, to the PLC, and a SLAM map cannot realistically transit
OPC UA process nodes. **Closed by ADR 0011 D4** at M5 briefing — the read-only
monitoring plane above — which amends the CLAUDE.md §3 topology by one edge
drawn in a third style and leaves invariant 11 unchanged. Still open:
**(b)** The HMI emergency button is read under invariant 1
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
