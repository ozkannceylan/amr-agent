# m5-66 — reconcile PLAN.md with the report directory

    brief:               issued in-session by the orchestrator (no brief file)
    status:              done
    invariants_touched:  none

## The stale safety claim — what it said, what it says now

PLAN.md's layer table asserted, flatly:

> Torque-off (`agv/`) | Real at the plant: after the demand the vehicle is deaf
> to commands

`docs/VALIDATION-M5.md` §6.2 measured the opposite on the controller in force:
with `SpeedMonitorDemand`, `Ss1Demand` and `TorqueOffDemand` all standing, the
vehicle carried on — 2.4 s and 1.2 m at 0.500 m/s in `at11r1`, and 19 s at
1.000 m/s in the window before it — because the demand had no path to the
vehicle at all (no mirror node, no publisher, no permissive conjunct).

The row now states that, and states the two halves of the repair separately:

- the **bridge half is built** (m5-62 — read slot, publisher, SD1–SD10
  implemented), and its evidence is **double-only and marked so** in
  `bridge/EVIDENCE_TORQUE_OFF_SLOT.md` §0 and §1;
- the **CPU half is chunks AD–AF** of the owner's TIA session;
- **until that session runs and §6.2 is re-measured on the CPU**, no claim of
  deafness after a demand may be made.

It also separates `agv/forklift/EVIDENCE_STO.md`'s surviving claim — the
contactor driven *directly* does make the plant deaf — from the claim that was
wrong, which is about the path from the F-program to it.

Three facts were carried in as given and are recorded rather than re-derived:
the `50573CD9` signature signs every figure in `docs/VALIDATION-M5.md` and the
session spends that run identity (`TIA-FIX-PROCEDURE.md` names what must be
re-run); `TorqueOffDemand` starts `TRUE` by ruling, so every CPU start is
torque-off until a monitored reset, intended and not a defect; and F2 is why no
autonomous mission completes, Nav2 leaving rest at 25 mm/s inside a band that
diagnoses a healthy vehicle as a failed shaft.

## The state of the world, brought current

The section was written before m5-58 ran. It now carries, in one screen:

- the validation's verdicts — V1-stops, V2 e-stop and V5 drive-at-a-wall
  **proven** with their n; V1-slows **not as asked**; V3 **not achieved**; V4
  **not run**; AT-10 proven on the CPU, AT-11 not runnable yet;
- the four findings with their TIA/agent split (m5-59's triage), and which agent
  halves have **landed** overnight — m5-60 node rows and SD1–SD10, m5-61 the
  `WARN` sender (`WarningFieldClear` `True` for the first time), m5-62 the bridge
  slot, m5-63 `bridge-design.md` and the bridge-liveness ruling;
- the layer table corrected in four rows besides torque-off: the writer's 45016
  speed link is no longer "INCOMPLETE (wip)" (m5-57, m5-58), the speed-link
  client's joint run is no longer OWED, the bridge carries four groups, and the
  scanner sends `WARN`;
- what tomorrow's session changes (six values, no acceptance testing) and what
  it does not;
- the sequencing constraints on the acceptance run — the 5 Hz keepalive brief
  before the 1.000 m/s re-record, and the live phases 1–4 with the harness
  console archived;
- the three things M5 still needs, and the two carried `plc/` document debts.

No PL, Category, SIL or PFH is claimed or implied; the stand-in labelling of the
safety input path is preserved. `docs/roadmap.md`'s criteria are neither
restated nor contradicted — PLAN.md continues to point at the M5 row for the
criterion.

## files_changed

| File | What |
|---|---|
| `docs/PLAN.md` | The `STATE OF THE WORLD` section rewritten; the torque-off layer row corrected |
| `docs/reports/m5-66-plan-reconcile.md` | This report |

Nothing else was written. Nothing committed, no branch, no dependency added.
`docs/TODO.md` was not touched.

## What `docs/TODO.md` must say (yours, not mine)

m5-64 finding 8 names TODO's half of the same drift, and two reports ask for it
by name:

1. TODO's lead item still reads m5-58 **"BRIEF WRITTEN, dispatches next"** — it
   ran and produced `docs/VALIDATION-M5.md`.
2. None of m5-59 … m5-64 appears at all.
3. **m5-60 request 5** — the interface half of F1 is closed. **m5-62 request 5**
   — the bridge half of F1 is closed. Both were unactioned.
4. The **m5-11 §12 residue** (four unspecified reactions) is explicitly **not**
   closed by either; `opcua-nodes.md` §11.2b is the pattern it should be closed
   in.
5. Open agent-side items that have no home in PLAN.md and belong in a queue:
   the **5 Hz keepalive brief** with its protective-path re-observation in the
   same run (m5-59 request 2, m5-61 request 2 — `plc/` rules
   `FIELD_LINK_STALE_MAX`, then `agv/` sets the rate); the two `plc/` document
   debts (§11's `0.40 s`, §7.2's keepalive rule); **m5-60 requests 3 and 4**
   (`plc/forklift/SPEC.md`'s four-mirror sentences are now six; the
   `plc/forklift-safety/SPEC.md` §6.4/§11.8 pointer); **m5-62 request 4**
   (`check_forklift_slots.py`'s fixed workdir); and the optional `hmi/` lamp on
   the warning node, bound by SD8/SD9 if taken.
6. **m5-65 is dispatched and has not reported.** Its deliverables are
   `docs/VALIDATION-M5.md`'s superseded band figures and step 38's fallback.

## open_questions

1. **The seam-(a) ADR clarification is still the owner's** (m5-60 §11.8 item 8,
   m5-64 finding 7): a modelled safety reaction is stimulated across the process
   network because the plant has no wire to carry it. `opcua-nodes.md` states the
   fact and its labelling (SD9, SD10) and asks whether it should also be an ADR
   clarification. Nothing waits on it, and it should not silently age out. If the
   owner wants it written, it is an arch-docs brief and I did not take it
   unasked.
2. **`docs/VALIDATION-M5.md` has no roster owner.** m5-65 reaches it by an
   explicit owner-approved scope grant to `plc/`. If the document is going to
   keep receiving corrections after every run, it wants a standing owner rather
   than a grant per brief.
3. **PLAN.md's M4 section still reads "CLOSING"** on the owner's formal showcase
   recording. It is not contradicted by anything I read, but it predates the M5
   validation and I did not touch it; if M4's showcase is now folded into the M5
   one, that section wants a ruling.

## next_suggested

Reconcile `docs/TODO.md` against the six items above before the verifier is asked
about the gate, then run the TIA session.
