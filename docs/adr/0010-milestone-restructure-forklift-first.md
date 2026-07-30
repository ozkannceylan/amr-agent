# ADR 0010: Milestone restructure — the forklift is the program

Status:        accepted (2026-07-30). Owner-approved on that date; the seven
decisions below are the owner's rulings, recorded here.

What this ADR changes, stated before anything else:

- It **supersedes the platform selection of ADR 0002**
  (`docs/adr/0002-vehicle-platform.md`). RB-KAIROS is retired as the navigation
  platform; the in-house forklift of ADR 0008 D4 is the vehicle platform from M5
  onward (D1). ADR 0002's reasoning stands as history and is not re-argued.
- It **supersedes the gate order above M3** set by ADR 0008 D1
  (`docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md`), which in turn
  extended ADR 0007 (`docs/adr/0007-safety-first-gate-order.md`). M0–M4 keep
  their numbers and criteria; old M5–M12 collapse into new M5–M7 (D2, D3, D4),
  and the arm gate is removed (D5).
- It **extends ADR 0009**
  (`docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md`), which is not
  superseded. Its early cell-scope opening on the forklift twin becomes the gate
  proper: D1's scope table, D3's coupling architecture and D5's wording
  discipline all carry into the new M5 unchanged.
- The rest of ADR 0008 is **unchanged and still binding**: D2's commissioning-HMI
  layer and its watchdog pattern, D3's ruling that teleop routing and the lidar
  stop are standard-program process logic implementing no SRS function, and D4's
  in-house model sourcing with its reference-only finding. Only D5, which kept
  RB-KAIROS "unless a later ADR rules otherwise" and forbade the forklift
  acquiring a navigation stack without an ADR saying so, is overtaken — this is
  that ADR.
- ADR 0007's showcase rule (§3) is **unchanged**; its per-function cell/vehicle
  split (§2) is unchanged in substance and its landing points move with the gates
  they name (D7).

No accepted ADR is edited — CLAUDE.md §8 forbids it — so the forward pointers
live here and in `docs/roadmap.md`, which remains the live order.

**Invariants 1–13 are untouched.** Gate order is not an invariant. Two
invariant-sensitive readings are *recorded* below and neither is altered: the
HMI emergency button under invariant 1, and the HMI map view's missing data path
under invariant 11 (D6).

Context:

**The owner restructured the remaining program on 2026-07-30**, in session. The
owner's own README commits of the same day — `46caa95`, `0007b16`, `2a62d77` —
are corroborating intent, not the ruling; the ruling is the seven decisions
below.

**M4 changed what the project owns.** ADR 0002 rejected a custom vehicle model
because modelling cost would dominate the project without adding architectural
value, and ADR 0008 D5 accepted a fraction of that cost for a plant carrying no
navigation claim. M4 then built the thing: a vehicle-shaped machine with steered
drive and a controlled fork, wired through a real S7-1500 program, a bridge, a
commissioning HMI and — under ADR 0009 — an executing F-runtime group. The
modelling investment ADR 0002 declined has been made. Keeping RB-KAIROS beside it
would mean two plant models, two sets of joints and two sets of evidence, with
the safety layer, the HMI and the PLC loop all attached to the one the project
built and none of them attached to the one it downloaded.

**Six gates described three showable systems.** Old M5 (safety) and M6 (vehicle)
were the same machine seen twice — a twin that stops safely, and a twin that
drives itself. Old M7 (VDA 5050 client), M8 (fleet manager) and M9 (PLC
integration) could not be demonstrated apart: a station handshake without a
fleet demonstrates the handshake against nothing, and a fleet without stations
has nothing to hand over to. Old M10 (demonstration) was a compilation of runs
whose parts were already recorded. Merging them is not compression of work; it is
one gate per system a viewer can watch.

Decision:

### D1 — The forklift is the program

All gates after M4 build on the in-house M4 forklift. The in-house model of
ADR 0008 D4 is the **vehicle platform** from M5 onward, and it acquires a
navigation stack — which ADR 0008 D5 reserved to a later ADR, this one.

RB-KAIROS is **retired**. ADR 0002's vendor findings of 2026-07-26 are history
and nothing here depends on them; they are not re-verified, because no gate now
rests on them. ADR 0002's consequence — that a mobile manipulator brings arm
capability into the model from the start, raising three architectural questions
at the arm gate — lapses with the platform and with D5.

### D2 — New M5: sensored autonomous forklift

One gate absorbs old M5 (safety layer) and old M6 (simulated vehicle), both
landing on the forklift twin rather than on the fixed cell or on RB-KAIROS. This
takes ADR 0009's direction to completion: what that ADR opened early as
cell-scope content on the twin is now the gate's own subject matter, so ADR 0009
is **extended, not superseded**, and its D1 boundaries — the lidar process stop
is not SF-07, the process reset is not SF-08 — hold word for word.

Content:

- **Safety laser scanner(s)** on the forklift model, their signals wired into the
  F-CPU safety program's F-blocks. This is the realism ruling: the safety sensors
  a forklift actually carries, on the F-side, not simulated at the process layer.
- **A navigation lidar**, SLAM building the map, Nav2 driving the forklift
  autonomously.
- **Stepwise module verification.** Each sensor's data is verified correct before
  anything is built on it — per-module evidence, not one end-to-end pass.
- **Beam visualisation in the Gazebo GUI**, so a viewer sees the sensor fields
  rather than being told about them.
- **HMI v2**, inheriting the M4 HMI under ADR 0008 D2 unchanged in kind: visually
  cleaner and less text-heavy, with drive-mode selection (teleop / autonomous),
  an emergency button (read as D6(b) states) and a real-time map view with live
  obstacles (whose data path is D6(a), open).
- **Exit shape**: a realistic forklift with safety sensors and autonomous
  driving, controllable from the HMI, closed by a **recorded safety + autonomy
  showcase**.

The old-M6 vehicle-chain acceptance tests land here, on the forklift: AT-02,
AT-03 and AT-04, with the inhibit demonstrably acting **below** the navigation
stack.

### D3 — New M6: VDA 5050 fleet at scale

One gate merges old M7 (VDA 5050 client), old M8 (fleet manager) and old M9 (PLC
integration): an enlarged warehouse world with **5 loading stations, 5 unloading
stations and 4 forklifts**; the fleet manager assigning transport orders over
VDA 5050 / MQTT and avoiding traffic conflicts; the PLC owning the stations'
fixed equipment and serving the station handshake over OPC UA to the fleet
manager. Closed by a **recorded fleet showcase**.

Invariants 3–6 are unchanged and are what the gate demonstrates: VDA 5050 is the
fleet contract, the PLC is the OPC UA server and the fleet manager its client,
the PLC owns fixed equipment while orders, traffic and zone reservation belong to
the fleet manager, and the fleet manager commands no actuator.

The acceptance tests of the three merged gates land here together: **AT-09** from
old M7, **AT-05 and AT-06** from old M9, with the fixed-equipment F-I/O behind
SF-05 and SF-06 arriving with the stations that give them their process purpose.

**Entry condition: a deep-research brief precedes any implementation.** Its
findings may propose splitting this gate internally; that would be a new owner
decision, recorded as open in D6(d).

### D4 — New M7: LLM operations layer, with the final demonstration

An LLM agent supervises operations in real time, takes safe actions and alerts
the user. The owner's Hermes agent is the **evaluation candidate, not a
decision**.

Three constraints carry **verbatim** from old M12, and they are the gate's
substance rather than its caveats: the LLM **never writes actuator outputs**,
**never bypasses PLC interlocks**, and **the cell operates normally with the LLM
and its transport unreachable** — the last being invariant 2's posture applied to
a supervisory layer.

**Entry condition:** the owner decisions listed in
`docs/reports/m4-00-hermes-survey.md` §6 are ruled. Of those ten, decision 2 was
closed by ADR 0007 and decision 3 was ruled by ADR 0008 D2.7 for the local
commissioning case only; the rest stay open, including the invariant-8 reading.
Old M12 (command path from Hermes, parked) is **unparked and absorbed here**.

**Old M10 folds into this gate's closure.** The recorded end-to-end run, the
validation report and the README architecture narrative are M7 exit criteria, not
a separate gate. The run keeps what old M10 carried: boundary statement B4 with
both chains live, and the cell operating normally with the fleet layer and all
remote access unreachable.

### D5 — The arm gate is removed

Old M11 (arm integration) is **removed from the roadmap entirely, not parked**.

SRS functions **SF-20…29** are to be marked **out of scope** in
`docs/safety/SRS.md` by a **separate safety-spec brief**, named here as the
follow-up. This ADR does not edit the SRS and does not delete the functions: the
record stays, marked, so nothing is silently lost.

### D6 — Open decisions, recorded as open

None of these is decided here. Each names its owner and the point at which it is
ruled.

| # | Open question | Ruled by | At |
|---|---|---|---|
| (a) | **The HMI map view has no data path.** The topology gives the HMI one edge, to the PLC, and a SLAM map cannot realistically transit OPC UA process nodes. Invariant 11 is not amended by naming the gap | Owner, by its own ADR | M5 briefing |
| (b) | **The HMI emergency button** is read under invariant 1 as a **process stop command plus a display of F-layer state** — never a safety e-stop over the network. Anything more is an invariant change needing its own ADR, and that change is **not** being made here | Owner, if ever wanted, by its own ADR | not scheduled |
| (c) | **The LLM layer's attachment point and topology edge**, per the m4-00 §6 decision list | Owner | M7 briefing |
| (d) | **The internal structure of M6** — one gate or staged | Owner, on the D3 deep-research brief's findings | M6 briefing |

(b) is a *reading* of an existing invariant, recorded so a later reader does not
mistake an emergency button on a screen for a safety function. It follows the
same naming discipline ADR 0004 set for the demonstration process stop and ADR
0008 D3 and ADR 0009 D5 carried forward.

### D7 — Numbering mechanics and recordings

**M0–M4 keep their numbers and criteria.** M4 remains the current gate and closes
on its recorded commissioning showcase plus the m4f-09 verification. The owner's
README "done" mark against M4 is corrected to *closing* by the README brief; this
ADR does not edit the README.

**The shift.** Old M5–M12 collapse:

| ADR 0008 gate | Deliverable | Becomes |
|---|---|---|
| M5 | Safety layer on the fixed cell (F-CPU) | **M5**, on the forklift twin |
| M6 | Simulated vehicle | **M5** |
| M7 | VDA 5050 client | **M6** |
| M8 | Fleet manager | **M6** |
| M9 | PLC integration | **M6** |
| M10 | Demonstration | **M7**, as that gate's closure |
| M11 | Arm integration | **removed** (D5) |
| M12 | Command path from Hermes — parked | **M7**, unparked and absorbed |

ADR 0007 §2's landing points move with their gates. Under the new numbers:
SF-01, SF-07 and the cell instance of SF-08 at **M5**, on the twin; SF-02, SF-03,
SF-04 and the vehicle instance of SF-08 at **M5**; SF-09 at **M6**; SF-05 and
SF-06 at **M6**, with the stations; SF-20…29 removed. The boundary statements
follow: **B1** at M5 and again at M6, **B2** at M6, **B3** at M5 for SF-01/07/08
and at M6 for SF-05/06, **B4** at M7, still the one statement needing both chains
alive at once.

**Filenames keep their written names.** A brief or report filename's number names
the round it was written under, not the gate it now serves — the standing
convention of ADR 0004, 0007 and 0008.

**The embedded-recordings principle continues**, four recordings in gate criteria
rather than deferred: the commissioning showcase at M4, the **safety + autonomy
showcase at M5**, the **fleet showcase at M6**, the **end-to-end demonstration at
M7**. A phase gate does not close on an unrecorded run.

Consequences:

What becomes harder:

- **Three gates now carry what six carried.** Each new gate closes on a larger
  observable system, so a gate brief cannot be a single deliverable — M5 and M6
  each need an ordered brief list, and D2's stepwise module verification is what
  keeps M5 from becoming one undifferentiated end pass.
- **The forklift model must grow into a navigation platform.** Safety scanners, a
  navigation lidar, odometry good enough for SLAM and a Nav2 configuration are all
  work ADR 0002 avoided by choosing a vendor-maintained description. That cost is
  accepted here, with the M4 model and its bridge slots as the starting point.
- **The renumbering touches every gate reference above M4**, for the third time.
  The prior lists in ADR 0007 and ADR 0008 are a **starting point, not an
  inventory**: the sweep is by subject — each occurrence of a gate number,
  whitespace-normalised, each hit read for dependency — and it is verified by
  independent search before anything changes. `docs/roadmap.md`, `docs/PLAN.md`
  and `docs/TODO.md` must not disagree with each other or with this ADR, and
  each is a separate brief.
- **`docs/safety/SRS.md` gains an out-of-scope marking**, and its gate tags and
  "Verified at gate" column move again (D5, D7). Both are the safety-spec agent's,
  not this ADR's.
- **The HMI grows a second version with an open data path.** D6(a) must be settled
  before the map view is built, and the wrong answer to it is a shortcut edge that
  breaks invariant 11.
- **Two ways to say "stop" become three on one screen.** The lidar process stop,
  the F-layer safety demand (ADR 0009's warning that this is the most likely place
  for the project's central claim to be misread) and now an HMI emergency button
  that is a process stop with a safety-state display. Each needs its own name in
  every document, tag and recording.
- **M7 depends on decisions that are not ruled.** Eight of the ten m4-00 decisions
  and the invariant-8 reading stand between the roadmap and an implementable M7
  brief. Absorbing a parked gate does not unpark its entry condition.

What becomes easier:

- **One vehicle, one plant model, one evidence set.** The safety layer, the HMI,
  the PLC loop and the navigation stack all attach to the same machine, and every
  gate after M4 builds on evidence the project produced itself.
- **No vendor dependency to keep re-verifying.** Retiring RB-KAIROS retires the
  external claims of ADR 0002 with it; nothing in the remaining program ages
  against a third-party default branch.
- **Each gate is a demonstration.** The safety + autonomy showcase, the fleet
  showcase and the end-to-end run are three watchable artifacts rather than six
  gate closures and one compilation.
- **The station handshake is demonstrated against something.** Merging PLC
  integration into the fleet gate means the handshake is exercised by real orders
  at real stations on its first run.
- **ADR 0009's opening stops being an exception.** What was a bounded departure
  from gate discipline becomes the gate's own content, and its fallback rule
  retires with it once M4 closes.

What this ADR does **not** decide: the HMI map view's data path (D6(a)); anything
beyond the D6(b) reading of the emergency button; the LLM layer's attachment
point and topology edge (D6(c)); whether M6 is one gate or staged (D6(d)); the
new gates' exact roadmap criterion wording; the scanner count, geometry, fields
and SLAM approach; the warehouse world's layout beyond the counts in D3; which
LLM agent is used; and the SRS edit that D5 names as a follow-up.

Alternatives:

- **Keep RB-KAIROS as the vehicle and run two plant models** — rejected: the
  safety layer, the HMI and the PLC loop are already attached to the forklift, so
  the second model would carry the navigation claim alone while every other layer
  demonstrated against the first. Two models is two sets of joints, two bridges'
  worth of slots and two sets of evidence for one architectural claim.
- **Keep the fixed-cell safety showcase as its own gate** — rejected: the owner
  archived it. The safety layer is built on the forklift twin instead, which is
  ADR 0009's direction taken to completion; the fixed-cell F-I/O that remains
  follows its equipment to M6.
- **Keep PLC integration as a separate gate after the fleet gate** — rejected: the
  M6 stations *are* the fixed equipment, and separating their PLC from their fleet
  would demonstrate the handshake against nothing.
- **A separate final demonstration gate (old M10)** — rejected by owner ruling:
  folded into M7, whose run is the end-to-end demonstration. The embedded-showcase
  principle already gives each earlier phase its own recording, so nothing is lost
  by not compiling them a second time.
- **Park the arm instead of removing it** — rejected: the owner ruled removal. The
  SRS keeps the record through the out-of-scope marking of D5, so the analysis
  survives without a roadmap row implying it is scheduled.
- **Edit ADR 0002 or ADR 0008 in place** — rejected by CLAUDE.md §8: an accepted
  ADR is never edited, it is superseded.
