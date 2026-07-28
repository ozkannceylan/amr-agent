# ADR 0007: Gate reordering — safety layer directly after the cell, Hermes parked

Status:        accepted (2026-07-28). Supersedes the gate order of ADR 0004
(`docs/adr/0004-gate-reordering-plc-loop-first.md`) and its M4 gate. ADR 0004 is
**not edited** — CLAUDE.md §8 forbids editing an accepted ADR — so the forward
pointer lives here and in `docs/roadmap.md`, which remains the live order.

Context:       ADR 0004 did its job: the Gazebo-to-PLC loop is the current gate
(M3, in progress) instead of the last one. Two things have changed since it was
accepted.

**The owner re-prioritised the remaining work on 2026-07-28.** The priorities, in
order: the system working properly; safety standards integrated and demonstrated
through showcases; F-PLC integration. Arm integration and the Hermes assistant
come last, and Hermes has no priority at all and is parked. Two points were ruled
by direct question: (a) the safety layer comes **directly after the cell and
before the fleet chain** — once M3 closes, the F-CPU is integrated on the fixed
cell, and SRS functions that need a vehicle to exist are completed later, in the
phase that has vehicles; (b) demonstration is **not one final gate only** — each
major phase's closing criterion includes a recorded showcase, and a final
demonstration gate is kept.

**ADR 0004's M4 premise is false.** It reads "A Hermes agent running on the same
server sends a command to the PLC over OPC UA". The m4-00 survey
(`docs/reports/m4-00-hermes-survey.md` §3, §5) found Hermes deployed on a Hetzner
VPS in Falkenstein while the PLC runs on the owner's machine, so the gate as
written could not be executed without first deciding an operator/HMI layer, an
invariant-8 reading and a transport shape — ten owner decisions, none ruled. This
ADR closes decision 2 of that list by superseding the premise rather than changing
the deployment to match it. It rules none of the other nine.

**Why safety belongs at M4 and not at the tail.** The project's claim after the
signal loop is separation of concerns, and the SRS's strongest evidence for it —
boundary statement B3, every F-CPU reaction reaching its safe state with the
standard program in STOP — needs no vehicle, no broker and no fleet manager. Five
of the nine SRS functions are verified by forcing F-I/O in PLCSIM Advanced. Put at
the end, that claim would be demonstrated last, on the largest stack, after the
network layers whose absence is the whole point of it. Put at M4, it is
demonstrated on the smallest system that can carry it, on the same TIA project and
cell that M3 has just proved.

Decision:

### 1. Gate order

| Gate | Deliverable | Closes when |
|---|---|---|
| M0 | Repo skeleton, ADR 0001 recording the invariants | Closed 2026-07-26 |
| M1 | Interface contracts | Closed 2026-07-26 |
| M2 | Safety requirements spec | Closed 2026-07-26 |
| M3 | Fixed equipment I/O loop | Unchanged from ADR 0004: all four demonstrated and recorded — (a) Gazebo sensor state visible as PLC input bits in a TIA watch table, (b) PLC output bits driving the Gazebo actuator, verified visually, (c) latency and update rate measured and written down, (d) signal-loss behaviour defined and tested |
| M4 | Safety layer on the fixed cell (F-CPU) | AT-01, AT-07 and AT-08 of `docs/safety/SRS.md` pass on PLCSIM Advanced, each including its standard-program-in-STOP sub-case (B3); the same three reactions execute with the bridge stopped and the OPC UA session down, making invariant 1 observable rather than asserted; the `Safety/` mirrors are read-only and no client write can create, prevent or clear a safety reaction; and a **recorded cell + safety showcase** shows the cell running a transfer, an e-stop trip with its monitored reset, and a zone trip with its monitored reset, naming in the recording which reactions are F-CPU safety functions and which are process behaviour |
| M5 | Simulated vehicle | Gazebo AGV localizes and navigates a warehouse world with Nav2, **and** AT-02, AT-03 and AT-04 pass with the inhibit demonstrably acting below the navigation stack |
| M6 | VDA 5050 client | A stub publisher sends an order, the vehicle executes it and reports state, **and** AT-09 passes: broker killed, controlled stop within the watchdog period, order kept, and SF-03 still acting during the outage (B1, B2) |
| M7 | Fleet manager | Real service assigns orders to two vehicles, traffic conflicts avoided |
| M8 | PLC integration | PLC serves OPC UA, fleet manager subscribes, station handshake works end to end; the door and charger fixed equipment now exist, so AT-05 and AT-06 pass including their B3 sub-cases, and AT-07's coupled Gazebo scenario runs with a vehicle in the monitored zone; and a **recorded fleet showcase** shows orders, traffic and the station handshake in one run |
| M9 | Demonstration | Recorded end-to-end run, validation report, README with architecture narrative; the run shows B4 with both chains live (the cell e-stop does not stop a vehicle, the vehicle chain does not depend on the cell) and the cell operating normally with the fleet layer and all remote access unreachable |
| M10 | Arm integration | Arm motion is gated by a base-stationary interlock, arm work is carried as a VDA 5050 action, and the safety zone model distinguishes base and arm (SF-20…29) |
| M11 | Command path from Hermes — **parked, no priority** | Entry condition: the ten owner decisions in `docs/reports/m4-00-hermes-survey.md` are ruled, including the operator/HMI layer ADR that the §3 topology needs. Closes when a Telegram-triggered command reaches the PLC by the path those decisions choose, the commanded action is observed in Gazebo, Hermes never writes actuator outputs and never bypasses PLC interlocks, and the cell is shown operating normally with Hermes and its transport unreachable |

### 2. Cell scope versus vehicle scope, function by function

Read from `docs/safety/SRS.md` §3 and §4. "Vehicle" means the acceptance test
cannot be executed without a moving simulated vehicle. "Cell equipment" means
fixed process equipment the demonstration cell does not have: `sim/worlds/cell.sdf`
and the `DemoCell` interface (`docs/interfaces/opcua-nodes.md` §9) carry a
conveyor, a product photo-eye and an operator panel — no door, no charger bay.

| SF | Function | Needs a vehicle | Needs cell equipment that does not exist | Lands at |
|---|---|---|---|---|
| SF-01 | Cell e-stop chain | No — AT-01 forces one channel and its safe state explicitly does not stop vehicles (B4) | A two-channel e-stop on F-I/O. The cell's existing red mushroom is a **process** stop (`opcua-nodes.md` §9.6) and may be neither reused nor relabelled | **M4** |
| SF-05 | Door interlock | No — AT-05 forces the door safety position switch | A door drive, a two-channel door safety switch and a conveyor transfer enable behind it | **M8**, where the passage handshake gives the door its process purpose |
| SF-06 | Charger interlock | No — AT-06 forces the docked-position input and the charge command | A charger bay, a charge contactor and a safety-relevant docked-position switch on F-I/O | **M8**, where the charge handshake gives the bay its process purpose |
| SF-07 | Zone monitoring, transfer station | No for AT-07 (a)–(d): forced zone input acting on the conveyor, which exists | A safety-rated zone device (light curtain or scanner field) on F-I/O | **M4**; the coupled Gazebo scenario the SRS names for it waits for **M8** |
| SF-08 | Monitored reset — **cell instance** | No — AT-08 is entirely PLCSIM | A reset device on F-I/O at the F-CPU panel, distinct from `DemoCell/Input/PanelResetPressed`, which is a process contact clearing standard-program latches only | **M4** |
| SF-02 | Vehicle e-stop | Yes — AT-02 asserts the input while the vehicle drives a Nav2 path | — | **M5** |
| SF-03 | Protective field stop | Yes — AT-03 spawns an obstacle in front of a moving vehicle | — | **M5** |
| SF-04 | Warning field speed reduction | Yes — AT-04 measures commanded and actual speed | — | **M5**, and no gate criterion may present it as safety-rated: the SRS claims no PL for it |
| SF-08 | Monitored reset — **vehicle instance** | Yes — exercised by AT-02 and AT-03's bumper latch | — | **M5** |
| SF-09 | Supervision watchdog *(not a safety function, no PL claim)* | Yes — AT-09 needs the vehicle, the VDA client and a broker | — | **M6** |
| SF-20…29 | Arm safety, reserved | Yes | Arm powered, which every SRS scenario currently forbids | **M10** |

The four boundary statements land accordingly: **B1** at M4 (reactions with the
bridge stopped) and again at M6; **B2** at M6; **B3** at M4 for SF-01/07/08 and at
M8 for SF-05/06; **B4** at M9, because it is the one statement that needs both
chains alive at once.

### 3. Showcases

Three recordings, embedded in gate criteria rather than deferred: the cell +
safety showcase at M4, the fleet showcase at M8, the end-to-end demonstration at
M9. A phase gate does not close on an unrecorded run, and M9 remains a gate in its
own right rather than a compilation of the earlier two.

### 4. What ADR 0004 still governs

Superseded: only its gate order and its M4 (Command path from Hermes). Unchanged
and still binding — the M3 definition and its four exit items; invariant 4's
direction (the PLC is the OPC UA server, the bridge and any assistant are
clients); the bridge as a signal translator with no sequencing, interlocks, timers
or latching; no safety function over OPC UA, and a demonstration stop button being
a **process** stop labelled as such in every document, tag name and recording;
the bridge as a first class component (ADR 0005); and the parked navigation
scenario under `sim/scenarios/` with its DEFERRED.md.

Consequences:

- **The renumbering is small.** M5–M8 keep their ADR 0004 numbers and contents, so
  every brief, report and TODO line that refers to M5, M6, M7 or M8 stays valid.
  Only four rows move: old M9 safety → **M4**, old M10 demonstration → **M9**, old
  M11 arm → **M10**, old M4 Hermes → **M11**.
- Existing brief and report filenames are kept as written, per the ADR 0004
  precedent. `m4-00-hermes-survey.*` belongs to what is now M11; the older `m3-*`
  sim files belong to M5.
- **Stale gate references exist outside this ADR's write scope** and are requested,
  not fixed, here. Found by search on 2026-07-28: `docs/safety/SRS.md` lines 6–7
  (F-CPU at M7, vehicle at M3/M4), §1.3 heading and body (three arm-at-M9
  references), the AT-06/AT-07/AT-08 gate tags, and the "Verified at gate" column
  of §4; `docs/safety/PL-SCENARIOS.md` lines 28–32, whose whole gate-numbering note
  is now wrong in two of its three claims; `plc/demo-cell/SPEC.md` line 1450
  (safety at M9 → M4; line 1451's M8 is still correct); `docs/TODO.md` line 32,
  whose unissued m2-04 done_when quotes the ADR 0004 numbers, and line 39's
  "plc (M9)"; and `sim/README.md` line 237, which places the door and
  conveyor/charger handshakes at "later gates (M6/M7)" — pre-ADR-0004 numbering,
  now M8 for the handshakes and M4/M8 for the safety functions behind them.
  CLAUDE.md §6 keeps the original numbering and is owner-owned;
  `docs/roadmap.md` is the live order, exactly as under ADR 0004.
- **M4 has a feasibility question that must be settled in the tool first.**
  Whether PLCSIM Advanced can execute an F-CPU safety program with simulated F-I/O
  and PROFIsafe is not established anywhere in this project, and no vendor claim is
  made here. The first M4 brief settles it in TIA Portal and PLCSIM Advanced before
  any safety logic is written and records the substitute if it cannot. Per ADR 0006
  and the lesson behind it, a tool-derived fact is a design value until read back
  from the tool. If the answer is no, M4's criterion changes; the order does not.
- **M4 needs devices the demonstration cell does not have**: a two-channel e-stop,
  a safety-rated zone device and an F-CPU panel reset, on F-I/O, plus a PROFIsafe
  configuration. `docs/interfaces/opcua-nodes.md` §9.8 states that the
  demonstration cell "has no F-CPU and no SF" and forbids any safety node in
  `DemoCell/` — true today and void at M4. Whether the mirrors appear in the M1
  `Safety/` group or in the cell interface is an interface question, requested and
  not decided here.
- **The safety layer is not complete at M4.** M4 delivers the cell-scope functions
  the cell's equipment can carry; SF-05 and SF-06 complete at M8 and the vehicle
  chain at M5/M6. No document may describe M4 as "safety layer complete".
- Because the safety gate now precedes the fleet layer, no SF acceptance test may
  be written to depend on a fleet manager, a broker or a vehicle. The SRS already
  satisfies this for SF-01, SF-05, SF-06, SF-07 and SF-08, which is what makes the
  reordering possible at all.
- Harder: three recordings instead of one, and the F-CPU program is touched at two
  gates (M4 and M8) rather than built once.
- Easier: the separation-of-concerns claim is evidenced on the smallest system that
  can carry it, and the portfolio has a showable artifact three gates earlier.
- **Nothing in CLAUDE.md §2 is touched.** Gate order is ADR 0004's, not an
  invariant. Invariants 1, 2, 7, 8 and 11 are unaffected in substance; M4's and
  M9's criteria are written so that 1 and 7 become observable instead of asserted.
- **Parking Hermes leaves nine decisions open**, and that is the point: no
  operator/HMI layer is added to the §3 topology by this ADR, and none may be added
  until the ADR that decision 3 asks for exists. The invariant-8 reading
  (m4-00 §5) is not ruled here.

Alternatives:

- Keep ADR 0004's order, safety at M9 — rejected: it demonstrates separation of
  concerns last, on the largest stack, after building the network layers whose
  absence is what the claim is about.
- One final demonstration gate only — rejected by owner ruling: a single recording
  at the end leaves every earlier gate's evidence a private artifact and the
  project without a showable cell until the last gate.
- A separate second gate for the vehicle-side safety functions — rejected: the SRS
  already places AT-02/03/04 in the simulated-vehicle phase and AT-09 in the VDA
  client phase. A separate gate would duplicate them and let the vehicle gates
  close with their safety behaviour unverified.
- Build the door and charger at M4 so every cell-scope function lands together —
  rejected: both are fixed **process** equipment whose handshakes (`PassageRequest`,
  `ChargeRequest`) belong to M8. Building them at M4 builds them for the safety
  half only and re-opens them at M8.
- Amend ADR 0004 in place — rejected by CLAUDE.md §8: an accepted ADR is never
  edited, it is superseded.
- Drop the Hermes gate entirely — rejected: the survey is real work and the
  decision list is a genuine architecture question about an operator layer and
  invariant 8. Parking keeps it recoverable; deleting it loses the analysis.
- Change the Hermes deployment so ADR 0004's "same server" premise becomes true —
  rejected as the answer to m4-00 decision 2: it would move a working assistant to
  serve a parked gate, and it prejudges the invariant-8 reading that is still open.
