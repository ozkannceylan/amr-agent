# Report m5-16 — the standard program's M5 delta: modes and the envelope

```
brief:               docs/briefs/m5-16-standard-program-delta.md
status:              done
files_changed:       [plc/forklift/SPEC.md — new §14 (the M5 autonomous-mode
                      delta), plus the enumerated anchor edits in the Authority
                      table, §3.2, §3.3, §5, §6.3, §6.7, §7's preamble, §9, §11
                      and §13.6 listed under "What moved outside §14" below]
invariants_touched:  none. Invariants 4, 5, 6, 9, 10 and 11 constrain the
                      section and the check is shown in it; no ADR proposal is
                      raised.
open_questions:      six, listed below and carried as §14.15 open items 1–7
next_suggested:      a logic double for §14.8's parts before the owner types
                      them — this section's one real defect was found by a
                      throwaway one, not by review
```

---

## What was written

`plc/forklift/SPEC.md` **§14 — the M5 autonomous-mode delta: the drive mode, the
autonomy envelope and the operator's process stop**, in §13's before-and-after
shape and at §7's level of precision: declarations with start values and bases,
SCL for three new parts and five modified statements with every insertion point
named, a state machine with named transitions, a row-by-row cold-start check, watch
rows, TIA steps, a four-state fallback and open items.

**It specifies a supervisor, not a controller**, and says so where a reader cannot
miss it. ADR 0014 **D5**'s obligation is discharged twice — once in the section's
opening ruling and once at the head of §14.5, where the envelope is specified:
*the PLC forms and publishes the envelope, the gate that enforces it runs on the
vehicle, and this program can withhold permission and notice that permission was
not honoured, but it cannot stop the vehicle*. ADR 0014 **D3** is honoured in the
same paragraph: nothing in §14 makes the S7-1500 a vehicle-borne controller.

**The teleop path is unchanged and the section shows it rather than asserting it.**
The whole change to it is **two conjuncts**, both on `ForkliftTeleopActive`. §6.4's
and §7 part 7's three setpoint assignments are byte-identical — one unconditional
`IF … ELSE` each with a mandatory `ELSE` to `0.0` — which is `opcua-nodes.md` §12.9
**C2** met with no new branch and no second writer.

**Nine nodes implemented, none redefined.** §14.2 restates §12's names, types and
start values as the PLC tag list, and every §12 rule (**M1**–**M6**, **E1**–**E8**,
**Z1**–**Z4**, **V1**–**V4**, **PS1**–**PS6**, **C1**–**C4**) is met in the section
that implements it. **No node is added**, no vehicle-side logic is specified, and
**nothing presumes the m5-03 F-I/O verdict**.

---

## Mode arbitration — the state machine

Three states, the `opcua-nodes.md` §12.3 encoding unchanged: **None (0)**, **Teleop
(1)**, **Autonomous (2)**. The mode in force lives in a static `DriveModeInForce`
and is published to `ForkliftDriveModeActive` in exactly one statement. **The
decision is taken once per OB call, ahead of both command paths**, which is what
makes **M6** — the two enables never both `TRUE`, including during a transition —
true by construction rather than by inspection.

| # | Transition | From → To | Condition |
|---|---|---|---|
| **X1** | `SelectTeleop` | None → Teleop | a fresh selector transition into `Teleop`, at confirmed standstill, with the M4 permissive holding |
| **X2** | `SelectAutonomous` | None → Autonomous | the same, into `Autonomous`, **plus the vehicle answering**. This transition **is** the affirmative action that enables autonomous motion (§12.3 defines no separate enable) and is the only thing that sets the internal `AutonomousArmed` |
| **X3** | `DeselectMode` | Teleop \| Autonomous → None | the request no longer equals the mode in force. **Leaving is unconditional** |
| **X4** | `ModeUnattributable` | any → None | the HMI link verdict is `FALSE`, or the request is outside `{0,1,2}`. *Not yet told* is `None`, never a mode |
| **X5** | `EntryRefused` | None → None | a selection arrived and was **consumed** without being honoured; re-entry needs the operator to move the selector away and back |
| **X6** | `ModeHeld` | Teleop \| Autonomous → same | a latch, a safety demand or a process stop does **not** move the mode; it drops the enables and takes the envelope non-permissive |

The three cases the brief named are answered as behaviour, not as advice:

- **Mid-motion request** — X3 fires in the call the request changes: the mode goes
  to `None`, teleop drops and the setpoints zero in the same call, or the arming
  clears and enable/ceiling go `FALSE`/`0.0` in the same call and the vehicle stops
  itself on its own ramp. Entry into the newly selected mode is then **refused**
  (X5) because the machine is still moving, and the transition is consumed — a mode
  change mid-motion always costs one deliberate re-selection, and there is no path
  by which the machine swaps control laws while moving.
- **Request under a latched process stop** — `ProcessStopLatch` is in
  `#latchPending`, so entry is refused (X5) and the transition is consumed. After
  the monitored reset the selector still reads the requested mode and **no
  transition exists**, so nothing enters: the operator must move the selector away
  and back, which is §12.3's stated sequence.
- **The losing source keeps writing** — the HMI's requests stay qualified and
  plausibility-tested but reach no output while the mode is not `Teleop`, and a held
  enable produces no edge when `Teleop` returns. A vehicle applying a mode it was
  not given is **noticed**: after `MODE_DISAGREE_DELAY` the same timer output both
  drops `#worldOk` (C8) and sets `ModeDisagreeLatch`, so everything drops and a
  monitored reset is required — and the reset is refused while the disagreement
  still stands. What the PLC cannot do is stop the vehicle, and the section says so.

---

## The equipment permit's terms

**The finding first.** The M5 warehouse world *does* carry fixed equipment as
geometry — a conveyor station, a transfer-station frame, two charge bays and a
dock-door opening (`sim/worlds/warehouse.sdf`, model list in
`sim/worlds/WAREHOUSE_EVIDENCE.md` §1) — and **this project's standard program holds
no signal from any of it**, because there is no demonstration cell in this project
at all (SPEC §3.1b). There is likewise **no station handshake to derive from**, so
no term of the M6 register can be evaluated today.

**The decision.** The register is declared with named members and its **M5
membership is two terms that are real, PLC-held and falsifiable at a watch table** —
never a literal `TRUE`:

| # | Term | Reads as | Falsified by |
|---|---|---|---|
| **EQ1** | `#bridgeLinkOk` | *I can see my own cell.* Every item of equipment this program could own reaches it through the bridge; a readiness stated while blind is the one thing a permit must never be | `kill -9` the bridge |
| **EQ2** | `NOT #ProcessStopLatch` | *My cell is not stopped* | press the process stop |

Neither is an order, a route, a destination, a zone or a reservation, and §14.5
carries a "do not write" table so no M6 term becomes one. **M6's four additions are
named** with the node group each will come from — `#dockDoorOpen`,
`#conveyorStationReady`, `#chargeBayClear` and `#stationHandshakeSatisfied`, the last
from the PLC's own handshake state (**Z3**) — so the M6 brief can be written from
that table. Granularity stays one Bool per vehicle.

---

## Cold start, checked row by row

All nine §12 rows checked in §14.9, each against what the program's **first scan
publishes** rather than against the DB start value alone. All nine agree. Two
results worth surfacing:

- `ForkliftEquipmentPermit` is **non-permissive by logic, not only by start value**:
  EQ1 is `FALSE` at the first scan. Start values are the last line, not the first.
- Exactly **one** row's agreement depends on an instance-DB value —
  `ForkliftProcessStopActive`, published from a static whose start value is `TRUE`.
  Because that static is new to a **live** `ForkliftControl_DB`, §14.13 step 7 makes
  reading all ten new statics and all three new `PT` values **out of the watch
  table** a build step, with reinitialisation if any disagrees. That is the failure
  LESSONS 2026-07-28 records, applied before it can happen again.

Every new timer states its `PT` explicitly at the call site — `VehicleStaleTimer`,
`ModeDisagreeTimer`, `StandstillTimer` — and all three are called unconditionally
outside any branch that owns a state.

---

## One real defect, found by a double rather than by review

The obvious form of the mode-disagreement term — `C8 := NOT (applied ≠ in force)`,
the **live** comparison, matching every other delayed cause in §6.3 — is **wrong**,
and it was written that way first. The live term is `FALSE` for the whole of the
vehicle's **normal adopt window**: the PLC decides the mode in one scan, the vehicle
sees it a bridge cycle later and reports it a cycle after that. A live C8 therefore
drops `#motionPermissive` in the call *after* transition X2, which clears
`AutonomousArmed`, which only X2 can re-set — and the next selection races the same
window. **`Autonomous` becomes permanently unreachable**, with a watch table showing
mode `2` and an enable that flickers `TRUE` for exactly one OB call per selection.

It was found by transliterating §14.8 into a throwaway double and running the entry
sequence with a **200 ms** adopt window instead of an instantaneous one; with an
instantaneous vehicle the sequence passes. The fix is that **C8 is the debounced
verdict, `NOT ModeDisagreeTimer.Q`**, so C8 and the latch fire in the same call and
C8's unique contribution is to `#causeGone` — the reset is refused while the
disagreement stands. §14.7 records the defect, the mechanism and the cost.

The double was throwaway and is **not committed and is not evidence**. §14.15 open
item 6 asks for the committed one, on the §7 precedent: this project has twice found
a specification defect by building an executable stand-in rather than by review.

---

## What moved outside §14, and why

Each edit is small, enumerated in §14.1 rows A10/A11, and made because leaving it
would have made two sections of one document disagree (LESSONS 2026-07-26).

| Where | Change |
|---|---|
| Authority table | Two rows: `opcua-nodes.md` §12 as §14's contract, ADR 0014 as binding on it |
| §3.2, §3.3 | One pointer line each: the delta's ten statics and six constant rows are declared in §14.3, and are read back from the watch table |
| §5 | One line: the delta adds no state to the teleop diagram; the mode is a second, separate state machine drawn in §14.4 |
| §6.3 | **C7** and **C8** rows added to `WorldOk`; the `latchPending` row states the two new members — seven latches, not five |
| §6.7 | The reset row says seven latches under §14; the enable row states the mode conjunct |
| §7 preamble | The fence is the M4 + §13 listing; §14 adds three parts and modifies five statements, and the fence's size and hash are **not** restated or amended |
| §9 | One line: the table gains Group 6 and eleven Group 5 rows, both in §14.11 |
| §11 | Two preconditions; **one new step row (5.1.3b)** so T5.1's specified denominator is **10**; **one re-specified step (5.5.6)** for the mode re-selection after an HMI outage |
| §13.6 | Its "43 steps, unchanged" is scoped to the §13 delta and pointed at §14's **44** — two deltas, two denominators, neither absorbing the other |

**The count discipline is honoured explicitly**: the specified denominator grows,
and the denominator of a run that already happened never grows. A T5.1 run recorded
against the 9-row table stays a 9-row run and its evidence record gains an
outstanding row (LESSONS 2026-07-28).

---

## Open questions

1. **`opcua-nodes.md` §12.5 Z4 versus §14.5's two-term register.** **Z4** says the
   permit's term set is empty at M5 and that the node is "assigned from the equipment
   terms in force, an empty conjunction today". An empty conjunction is `TRUE` by
   convention, which the brief forbids, so this document publishes a **named,
   falsifiable two-term register** instead. **If Z4 is meant to require that the
   permit read `TRUE` at M5 whenever the program is running, EQ1/EQ2 need the
   interface agent's ruling.** Nothing in the node set moves either way. This is the
   one place where this document exercises judgement inside a §12 expectation rather
   than simply implementing it, and it is flagged rather than settled.
2. **`MODE_DISAGREE_DELAY` = `T#2s` is bounded from below by a number this document
   does not hold** — the vehicle's worst-case time to adopt a new mode and report it,
   which may include its own controlled-stop ramp. That is `agv/`'s (m5-11).
   Requested rather than invented; the constant is re-derived when it lands. It is
   also, after the C8 fix, **the whole of the tolerance** for a disagreement.
3. **`ForkliftSpeedLimitActive` stays teleop-scoped.** `opcua-nodes.md` §10.7 defines
   it as `TRUE` only while teleop is active, so in autonomous mode the fork-height
   clamp is visible only as the ceiling falling from `0.60` to `0.30` m/s and not on
   that flag. Widening it is a §10.7 change and is **requested, not taken** — this
   document does not redefine a §10 node.
4. **§14 has a hard dependency on HMI v2 (m5-14).** `HmiProcessStopRequest` starts
   `TRUE`, so a v1 HMI writing only six nodes leaves it `TRUE` forever, `WorldOk`
   `FALSE` forever, and **the cell inert in both modes**. This is written as fallback
   state C and as a §11 precondition: **do not apply the delta before HMI v2 writes
   the two new request nodes.** It is the delta's single largest coupling.
5. **`FB_ForkliftTeleop` and `ForkliftControl_DB` are now misnomers** — the block
   carries the autonomous-mode supervisor too — and are **deliberately not renamed**
   (LESSONS 2026-07-30). Recorded rather than fixed.
6. **`plc/README.md` still has no `forklift/SPEC.md` row** and its boundary statement
   names only the M3 cell's process stop. It now also needs one sentence saying the
   operator's process stop of `Forklift/ProcessStop/` is a **process** stop and no
   safety function. Outside this brief's write scope; requested here (this is SPEC
   §12 open item 7, still open).

Not a question but worth the orchestrator's note: **`bridge-design.md` must carry
this signal group before any bridge work on it** (`opcua-nodes.md` §12.13 item 1,
already requested by m5-17), and it carries this project's **first topic-carried
`UInt16`**.

---

## What this section deliberately does not specify

The vehicle's envelope gate node and its arbitration (`agv/`, m5-11); the
vehicle-side freshness window **E5**; how an M5 navigation goal is commanded;
anything in the safety program (m5-15, and nothing here presumes the m5-03 verdict);
the bridge's slots; and what the HMI shows. Each is tabulated in §14.15 with its
owner.
