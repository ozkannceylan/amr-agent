# Report m4r-01 — ADR 0007, safety-first reordering and deprioritisation

brief:               docs/briefs/m4r-01-adr-0007-reordering.md
status:              done
files_changed:       docs/adr/0007-safety-first-gate-order.md (new), docs/reports/m4r-01-adr-0007-reordering.md (this file). Nothing else touched — roadmap.md, PLAN.md, TODO.md, ADR 0004 and the SRS are unchanged, per the brief's forbidden list. Not committed.
invariants_touched:  none. Gate order is ADR 0004's, not a CLAUDE.md §2 invariant, so this is a supersession by the book and needs no invariant ADR. Invariants 1, 2, 7, 8 and 11 are unaffected in substance; M4's and M9's criteria are written so that 1 and 7 become observable rather than asserted.

## What the ADR decides

New order, twelve gates: M0 repo skeleton, M1 interface contracts, M2 SRS (all
closed) — M3 fixed equipment I/O loop (in progress, scope and criterion copied
verbatim, untouched) — **M4 safety layer on the fixed cell (F-CPU)** — M5
simulated vehicle — M6 VDA 5050 client — M7 fleet manager — M8 PLC integration —
M9 demonstration — M10 arm integration — **M11 command path from Hermes, parked**.

The renumbering is deliberately minimal: M5–M8 keep their ADR 0004 numbers and
contents, so every brief, report and TODO line referring to them stays valid. Only
four rows move — old M9 safety → M4, old M10 demonstration → M9, old M11 arm →
M10, old M4 Hermes → M11.

Owner rulings, and where each is satisfied:

1. Priority order — M4 is safety, M10/M11 are arm and Hermes, Hermes marked parked
   with no priority and the m4-00 decision list as its entry condition.
2. Safety directly after the cell, with the vehicle-scope split named function by
   function — Decision §2, a row per SF read from SRS §3/§4 (see below).
3. Showcases embedded plus a final gate — Decision §3: recorded showcase inside the
   M4 and M8 criteria, M9 kept as a demonstration gate in its own right.
4. The resulting order — the table above.

## The cell/vehicle split, as read from the SRS

Cell-scope and at **M4**: SF-01 cell e-stop chain, SF-07 zone monitoring
(AT-07 a–d only), SF-08 monitored reset cell instance. All three are forced-F-I/O
PLCSIM tests, all three include a standard-program-in-STOP sub-case (B3), and none
of their acceptance tests mentions a vehicle — SF-01's safe state explicitly does
not stop vehicles.

Cell-scope but **equipment-gated, therefore M8**: SF-05 door interlock and SF-06
charger interlock. Their acceptance tests are also vehicle-free forced-input tests,
but the demonstration cell has no door and no charger bay — `sim/worlds/cell.sdf`
and the 15-node `DemoCell` interface carry a conveyor, a product photo-eye and an
operator panel. Both are fixed **process** equipment whose handshakes
(`PassageRequest`, `ChargeRequest`) belong to M8, so building them at M4 would
build them twice. This is the one place I inferred beyond the four rulings; it is
written as a decision with its alternative rejected, and it is the item most worth
the owner's eye.

Vehicle-scope: SF-02, SF-03, SF-04 and SF-08's vehicle instance at **M5**; SF-09
(not a safety function) at **M6**; SF-20…29 arm safety at **M10**. SF-07's coupled
Gazebo scenario, which the SRS itself defers, lands at M8.

Boundary statements: B1 at M4 and again at M6, B2 at M6, B3 at M4 for SF-01/07/08
and at M8 for SF-05/06, B4 only at M9 — it is the one statement that needs both
safety chains alive at once.

## open_questions

1. **PLCSIM Advanced and the F-CPU.** Whether it can execute an F-CPU safety
   program with simulated F-I/O and PROFIsafe is not established anywhere in this
   project. No vendor claim is made in the ADR; it requires the first M4 brief to
   settle this in the tool before any safety logic is written, per ADR 0006's
   lesson. If the answer is no, M4's criterion changes, not the order.
2. **Devices M4 needs and the cell does not have** — two-channel e-stop, safety-rated
   zone device, F-CPU panel reset, on F-I/O. Requests, outside my write scope: the
   **sim** agent for the devices in `cell.sdf`; the **interface** agent for
   `opcua-nodes.md` §9.8, which states the demonstration cell "has no F-CPU and no
   SF" and forbids any safety node in `DemoCell/` — true today, void at M4, and
   whether the mirrors live in the M1 `Safety/` group or in the cell interface is an
   interface decision. Note the standing trap: the panel's process reset contact
   (`PanelResetPressed`) is not the SF-08 device and must not be conflated with it.
3. **Stale gate references, verified by search on 2026-07-28, all outside my write
   scope.** `docs/safety/SRS.md`: lines 6–7, §1.3 heading and body (three arm-at-M9
   references), the AT-06/AT-07/AT-08 gate tags, and every "Verified at gate" cell
   in §4 — the **safety-spec** agent, and the already-queued m2-04 brief is the
   natural carrier. `docs/safety/PL-SCENARIOS.md` lines 28–32: its gate-numbering
   note is now wrong in two of its three claims. `plc/demo-cell/SPEC.md` line 1450
   (safety at M9 → M4; line 1451's M8 is still correct) — the **plc** agent.
   `sim/README.md` line 237 places the door and conveyor/charger handshakes at
   "later gates (M6/M7)", pre-ADR-0004 numbering — the **sim** agent.
   `docs/TODO.md` line 32 (the unissued m2-04 done_when quotes the ADR 0004
   numbers) and line 39 ("plc (M9)") — the orchestrator owns TODO.md. Treat this
   list as a starting point and re-search before closing it.
4. **ADR 0004's status line is not edited**, because CLAUDE.md §8 forbids editing an
   accepted ADR while its status vocabulary also offers "superseded by NNNN". I
   resolved it in favour of the never-edit rule: the forward pointer lives in ADR
   0007's status line and will live in roadmap.md. If the owner prefers the status
   line updated instead, that is a one-line exception to §8 and needs their word.
5. **Nine m4-00 decisions stay open** by design (only decision 2 is closed here, by
   supersession). No operator/HMI layer is added to the §3 topology, and none may be
   until the ADR decision 3 asks for exists.

next_suggested:      the roadmap/PLAN renumbering brief (arch-docs) — roadmap.md to the M0..M11 order above with the new criteria, PLAN.md's current-gate block left on M3, and TODO.md reconciled by the orchestrator in the same commit so the three tracking files never disagree.
