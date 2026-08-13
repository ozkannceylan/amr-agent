# m5-72 — why teleop will not enter, and where the scanner is looking

    gate:                M5
    agent:               agv-ros2
    goal:                Find out why a zone-stop demand is latched with the vehicle standing in clear space, and why the lidar visual is not on the vehicle — and determine whether they are one fault or two.
    invariants_touched:  none
    inputs:
      - the owner's two screenshots, described in §1 — this is a live observation, not a hypothesis
      - agv/forklift/model.sdf — sensor poses and frames
      - agv/forklift/scripts/field_evaluation.py, agv/forklift/FIELD-EVALUATION.md
      - agv/forklift/EVIDENCE_SENSOR_COVERAGE.md and EVIDENCE_FIELD_EVALUATION.md
      - demo.sh, RUNBOOK.md, docs/reports/m5-71-teleop-demo-stack-scripts.md — the stack the owner brought up
      - docs/LESSONS.md
    deliverable:         the diagnosis, the fix if it is inside agv/, and a dated evidence section
    done_when:           The owner can bring the stack up with demo.sh, clear the safety reset, enter TELEOP and drive — demonstrated end to end, not reasoned about.
    forbidden:
      - touching TIA, plc/ or the F-program. The CPU is signed at 29FD2C52 and the owner's session is closed
      - making the demand clearable by widening a field or lowering a threshold. If the scanner is right and the world is wrong, say so
      - claiming the fault is fixed without the owner's own path working: up, reset, TELEOP, drive
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. What the owner observed, live

Stack up via `demo.sh`, HMI connected, `data 197 ms`, PLC sees operator **yes**.

**The HMI's own answer to why teleop does nothing:**

- MODE selector on TELEOP, but `mode` reads **SELECTION NOT IN FORCE** and
  `ForkliftDriveModeActive` reads **NONE**
- Section A's condition list: process stop latched **no**, obstacle stop latched
  **no**, e-stop demand **no** — but **zone-stop demand YES** and **safety reset
  required YES**
- F-layer state: **zone-stop demand DEMAND LATCHED**, **safety reset required
  REQUIRED**, reset device fault clear
- Envelope: autonomous motion **WITHHELD**, speed ceiling **no motion permitted
  (0.00 m/s)**

**So teleop is not broken. The vehicle is under a latched protective demand and
the PLC is correctly refusing to enter any mode.** The question is why that
demand is standing with the vehicle parked in open floor.

**Second observation, and it may be the same fault:** the Gazebo lidar visual
for `/forklift/gz/safety_scanner_f` is **not on the vehicle**. The fan of rays
sits up and to the left of the forklift, at a distance, in free aisle space.

## 2. The hypothesis to test first, and to kill if wrong

If the front safety scanner's pose or frame is wrong, it observes a place the
vehicle is not — and if that place contains racking, the protective field is
**permanently occupied**, the zone-stop can never clear, and teleop can never be
entered. **One fault would explain both screens.**

Test it directly: where is the sensor mounted in the model, where is its visual
rendering, and what is the field evaluation actually reading when the vehicle
stands in open floor? Compare the sensor's own returns against the geometry
around the vehicle.

**Do not assume this hypothesis is right.** A second candidate is that the
visual is a rendering-frame artefact while the returns are correct, and the
demand is standing for an unrelated reason — a stale field link, the writer's
window, or the boot latch never having been cleared. Distinguish them by
measurement and say which it was.

## 3. There is a third possibility, and it is the cheapest

**The demand may simply be the boot state and never cleared.** `TorqueOffDemand`
boots TRUE by ruling, demands latch at start, and a **monitored reset with the
cause still standing is correctly refused**. If the field is genuinely occupied,
the reset *should* fail — and the fix is the world, not the code.

So before changing anything: bring the stack up, look at what the scanner
reports, and try the reset. If it refuses, find the cause it is refusing over.
`m5-71` proved a reset is accepted once the field is clear.

## 4. Note what else was on the screen

The monitoring plane reported **connection refused** — the `viz/` service was
not answering. That is a separate defect and it is not yours to fix inside
`agv/`, but record it: it means `demo.sh` declared ready with a component that
was not serving, which is a readiness-check gap worth reporting to `infra`.

## 5. The bar for done

Not "the demand cleared once". The owner must be able to run `./demo.sh up`,
clear the reset, select TELEOP, and **drive** — and you must have watched it
happen. If part of the path is outside `agv/`, fix your part and say precisely
what remains and whose it is.

## 6. Working discipline

- Read `docs/LESSONS.md` first.
- **A latched safety demand is evidence of a working safety layer until proven
  otherwise.** Treat "make the demand go away" as the wrong goal; the goal is
  to find what it is reporting.
- Write evidence as it lands. Every figure states its n.
- **Do not commit.** The orchestrator commits by pathspec.
