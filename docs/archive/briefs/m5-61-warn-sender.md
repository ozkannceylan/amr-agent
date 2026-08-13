# m5-61 — send the WARN line

    gate:                M5
    agent:               agv-ros2
    goal:                Make the vehicle's field evaluation send the WARN line to the stand-in writer, so the F-side limit selector stops being permanently occupied and the 300 mm/s limit stops being permanently enforced.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-59-validation-fix-triage.md — finding F3, and the ordering constraint that makes it urgent
      - docs/VALIDATION-M5.md — findings F3 and F4, and the runs behind them
      - docs/reports/m5-57-writer-speed-link.md — the writer's link protocol and its measured behaviour
      - bridge/STANDIN-WRITER-DESIGN.md — the receiving end, which already parses WARN on 45015
      - agv/forklift/FIELD-EVALUATION.md and agv/forklift/scripts/field_evaluation.py
      - agv/forklift/EVIDENCE_FIELD_EVALUATION.md
    deliverable:         the sender in agv/forklift/, and a dated section in agv/forklift/EVIDENCE_FIELD_EVALUATION.md
    done_when:           A real Gazebo warning-field intrusion produces a WARN line that the writer receives and turns into a SafetyInputStandIn member change, shown with a control case outside the contour producing the opposite value.
    forbidden:
      - editing outside agv/
      - changing the protective-field path, which is proven and is the presentation's centrepiece
      - inventing the protocol. The writer already defines it; read the receiving end
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. Why this is urgent

**F1 must not land without this.** The reasoning, from m5-59:

With no `WARN` sender, `WarningFieldClear` never becomes TRUE, so the reduced
**300 mm/s** limit is permanently in force. The owner's TIA session tomorrow
lands the permissive conjunct that finally couples the SLS and SS1 demands to
the vehicle. The moment it does, **any drive above 0.30 m/s refuses motion until
a monitored reset** — and the 1.000 m/s drive-at-a-wall clip, which is the
validation's most convincing result and the showcase's centrepiece, becomes
un-recordable.

So this brief is what keeps tomorrow's session from breaking a working
demonstration. It ships tonight.

## 2. What to build

The field evaluation already computes the warning verdict — the warning field
was built and proven in m5-47, and the protective field's sender already works
over the same link. This is the missing half of a mechanism that otherwise
exists.

- Send `WARN` on the existing **45015** link, in the writer's protocol
- Follow the protective path's own discipline: **an empty horizon is a
  measurement, not missing data**, and silence must not be readable as "clear".
  The writer converts silence into an explicit claim inside its window; make
  sure a clear verdict is always a **fresh** claim, never an inherited one
- Do not disturb the protective path's timing. It is measured and committed

## 3. Two hazards from the runs

- **`FIELD_LINK_STALE_MAX` is 1 s against a 1 Hz keepalive — zero margin.**
  Measured, the link was reaped 10 ms before the fourth keepalive. Adding a
  second line type to the same link changes its traffic. If your sender makes
  this worse, say so with the measurement; the constant is `plc/`'s to rule and
  you may not retune it silently.
- **With the writer running and no field source, no monitored reset can be
  accepted** while the vehicle is above the reduced limit. This cost two earlier
  agents a run each. Plan it into your startup order.

## 4. Evidence

A real Gazebo intrusion, not a synthetic line on a socket. The control case is
what makes it mean anything: an object plainly visible to the scanner but
**outside** the warning contour produces the opposite verdict. State the n.

## 5. Working discipline

- Read `docs/LESSONS.md` first.
- Write the evidence as it lands.
- **Do not commit.** The orchestrator commits by pathspec.
