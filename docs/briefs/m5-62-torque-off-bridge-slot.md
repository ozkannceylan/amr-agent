# m5-62 — carry TorqueOffDemand to the vehicle

    gate:                M5
    agent:               bridge
    goal:                Give TorqueOffDemand its read slot and its publisher, so the F-program's SS1 demand finally reaches the vehicle — the orphaned half of finding F1.
    invariants_touched:  none
    inputs:
      - docs/interfaces/opcua-nodes.md §11.2b — rules SD1 to SD10, the ruling this brief implements
      - docs/reports/m5-60-safety-demand-node-rows.md — the ruling's reasoning and its three requests
      - docs/reports/m5-59-validation-fix-triage.md — finding F1 and the TIA/agent split
      - docs/VALIDATION-M5.md — the run that measured the demand going nowhere
      - bridge/config/bridge.yaml, bridge/EVIDENCE_ENVELOPE_BRIDGE.md, bridge/EVIDENCE_WARNING_SLOT.md
      - agv/forklift/scripts/sto_contactor.py — the subscriber that already exists and has never had a publisher
    deliverable:         the slot and publisher in bridge/, with a dated evidence section
    done_when:           A TorqueOffDemand transition on the CPU reaches sto_contactor's topic and is observed there, with a positive control in the same run proving the vehicle moves when the demand is absent.
    forbidden:
      - editing outside bridge/
      - giving SpeedMonitorDemand a slot, a topic or a consumer. SD1 rules it has none — its reaction is the PLC's permissive and it reaches the vehicle as consequence
      - carrying any speed, limit, margin or exceeded reading across the seam (SD7, ADR 0014)
      - claiming or implying an achieved PL, Category, SIL or PFH, or publishing a stopping figure

---

## 1. What is broken

The validation measured the vehicle driving **19 s at 1.000 m/s** with
`SpeedMonitorDemand`, `Ss1Demand` and `TorqueOffDemand` all standing. Measured
on the vehicle side: `publisher count 0` on
`/forklift/safety/torque_off_demand`, against one subscriber — `sto_contactor`,
which has been waiting for a publisher that was never built.

The owner lands the CPU half tomorrow morning. This is the half that meets it.

## 2. Implement the ruling, do not re-derive it

`opcua-nodes.md` §11.2b states the reactions in its own voice precisely so no
consumer reads them conservatively on its own. Implement SD1–SD10 as written.
Three that shape the code:

- **SD5 — stale, silent or never-resolved is NOT torque-off.** This is the
  deliberate opposite of the warning slot's silence-implies-`TRUE` rule, and the
  ruling names itself so the asymmetry cannot read as an oversight. Do not
  "improve" it into symmetry. If the code looks wrong to a later reader, the
  comment must carry the reason, not the code carry the other behaviour.
- **`TorqueOffDemand` starts `TRUE`** — its source's boot truth. So at every CPU
  start the vehicle is torque-off until a monitored reset. That is intended and
  must survive your implementation.
- **An *observed* `TRUE` latches; authority returns only on an observed `FALSE`
  plus a fresh command.** Observed, in both directions — not inferred, not
  defaulted.

## 3. Two documentation repairs the ruling asked for

Both are inside `bridge/` and belong to this brief:

- `bridge-design.md:35` still says the writer carries **four tags**. It has been
  **eleven** since m5-49.
- the `bridge-design.md` read slot the interface brief deliberately reserved to
  you.

## 4. Evidence

A real transition on the real CPU reaching the real subscriber. And the rule
this project keeps relearning: **stillness is not evidence** — a stopped
contactor and a genuine torque-off produce the identical observation. The
positive control belongs in the same run: the same command moving the vehicle
when the demand is absent. State the n.

If the CPU half is not on the CPU yet when you run — the owner's session is
tomorrow — say so plainly and prove what you can against the double, marking
exactly which claims are double-only. Do not present a double run as a live one.

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- Write the evidence as it lands.
- **Do not commit.** The orchestrator commits by pathspec.
