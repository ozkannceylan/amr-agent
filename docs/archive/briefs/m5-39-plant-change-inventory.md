# m5-39 — the plant change: inventory before the edit

    gate:                M5 (criterion (d)) and M4 (its recorded showcase)
    agent:               agv-ros2   (inventory and plan; the change follows)
    goal:                Know exactly which committed figures the steer-gain change invalidates, before the gain is changed — and separate what an agent can re-measure from what only the owner can.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-38-cross-track-diagnosis.md — the diagnosis and its §5, the three options
      - agv/forklift/model.sdf — the plant, line 1002 and the comment that records the scrub as measured
      - agv/forklift/EVIDENCE_*.md — **all of them**
      - sim/ — its evidence and scenario files
      - plc/forklift/SPEC.md §11 and sim/scenarios/forklift_commissioning.md — the M4 procedures
      - docs/roadmap.md — criteria (d) and (e), and the M4 row
      - docs/TODO.md §"Measured numbers a later session should not re-derive"
      - docs/LESSONS.md
    deliverable:         agv/forklift/PLANT-CHANGE-INVENTORY.md and docs/reports/m5-39-plant-change-inventory.md
    done_when:           Every committed motion figure in the repository is classified, the re-measurement is ordered by what a gate criterion actually cites, and the figures that cannot be re-measured by an agent are named as the owner's with what each needs.
    forbidden:
      - changing `model.sdf` — this brief inventories, it does not edit. The change is the next brief
      - running the simulator for measurements — this is a reading task; if a figure's dependence on the plant is genuinely unclear, say so rather than measuring
      - guessing whether a figure is affected; if you cannot tell from the evidence file, that is a finding
      - touching `plc/` or `bridge/` — both carry live work
      - re-deriving the measured numbers in TODO; quote and classify them

---

## 1. The ruling

The owner ruled **option (i)**: apply the steer-gain change and re-measure the
affected evidence. Your job is the "affected" — before anything moves.

The change is `model.sdf`'s steer `p_gain` 6000 → 60000, which moves the angle
below which the steer axis cannot overcome the tyre scrub from **3.8° to 0.38°**.
Anything whose value depends on how the vehicle steers is in scope. Anything
that does not is not, and saying so confidently is as useful as finding one that
is.

## 2. Classify every figure into exactly one of four

1. **Unaffected** — and say why. A sensor coverage angle measured on a stationary
   model does not depend on steer authority; say that rather than leaving it
   unclassified.
2. **Agent re-measurable** — a harness exists, or one can be written, and the
   figure can be retaken headless. Give the command.
3. **Owner-only** — chiefly the **recorded M4 commissioning showcase**. A video
   cannot be re-measured; it is either re-recorded or it is qualified as having
   been made on the prior plant. Say which figures are in this class and what
   each would need.
4. **Unclear** — you cannot tell from the evidence file whether the figure
   depends on the plant. This is a finding about the evidence file, not a
   failure; name it and say what would settle it.

## 3. Order the re-measurement by what a criterion cites

Not by directory, and not by how easy each is. A figure that roadmap criterion
(d) or (e) cites comes before one that appears only in a supporting document.
Say for each: which criterion, which clause.

Note that m5-38 already re-measured the arrival distribution **on the new
plant** — 5 of 5 clean, localization max 0.1523 m. Those figures are already in
hand; the inventory should say so rather than scheduling them again.

## 4. The honest edge

Applying this change means **the recorded M4 showcase no longer matches the
tree**. M4 is closing on that recording. Say plainly what that does to the M4
gate, and what the least-cost honest resolution is — re-record, or qualify the
recording with the plant it was made on. This is the owner's ruling, but they
need the options stated with their costs, not discovered later.

## 5. Two findings from m5-38 that belong to `sim/`

Carry them into your report as requests, since `sim/` is not yours:

- the **arena floor gives the drive wheel no traction** — 5.000 rad/s commanded
  against 0.005 m/s achieved;
- `model.sdf`'s documented claim that the scrub **disappears once the vehicle
  rolls** is falsified by m5-38's bench.

## 6. Working discipline

- Read `docs/LESSONS.md` first. Directly yours: evidence is qualified by the
  environment that produced it, and a sweep is bounded by its subject across the
  corpus rather than by the file the phrasing was first found in.
- **Write the inventory as it fills**, not in one pass.
- **Do not commit.** The orchestrator commits by pathspec.
