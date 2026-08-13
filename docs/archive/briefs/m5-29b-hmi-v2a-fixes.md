# m5-29b — apply the v2a review fixes

    gate:                M5 (criterion (e); blocking the rest of M5)
    agent:               hmi
    goal:                The second-tab release is gone, the designed connect failure is legible, and the three minor design departures are closed — so the rest of M5 can be built on this screen.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-29-hmi-v2a-review.md — **the authority.** F1's fix is specified there and is decision-free; build it as written
      - hmi/V2A-DESIGN.md — especially **PS-D**, the clause the build departed from
      - hmi/ — hmi_server.py, static/index.html, tools/capture_v2a_screens.mjs, EVIDENCE_HMI.md
      - docs/reports/m5-28-hmi-v2a-build.md
      - docs/LESSONS.md
    deliverable:         the fixes in hmi/, re-captured screenshots, EVIDENCE_HMI.md updated
    done_when:           A second tab can no longer release an engaged process stop or fire a mode-select rise, shown by a capture that reproduces the old failure path and observes it not happening; F2 and F4 are closed; and the three new capture checks pass.
    forbidden:
      - re-designing anything — F1's fix is specified in the review; if it cannot be built as written, STOP and report
      - answering the design's two owner open questions
      - building the live map, the monitoring plane, or any v3 item — the joystick stays visible in all modes by owner ruling
      - inventing an OPC UA node
      - writing outside hmi/ except your report — **another agent holds plc/ right now; do not touch it**

---

## 1. F1 — the blocking one

The design (PS-D) has the page render the stop from the backend's published
state. The build instead renders from a **local copy adopted once**, and
re-asserts both standing values in **every** post — the 50 ms dirty loop, the
deadman, `blur`, `visibilitychange`.

One tab and one reload are safe, and that evidence is genuine. The failure is a
**second tab**: it holds a stale copy, posts when it is backgrounded, and that
post can **release an engaged process stop** — making the live-world reset term
true while the operator's own screen still reads ENGAGED — or fire a fresh
mode-select rise at the PLC, including the affirmative autonomous enable.

An operator who opens a second tab is not doing anything unusual. Read the
review's F1 section and build exactly what it specifies: render both controls
from the backend's published state each poll, send the standing keys only in the
click's own post, refresh the published `controls` in `do_POST`, and add the
three capture checks it names.

**Prove it by reproducing the failure.** A capture that opens a second tab,
backgrounds it, and shows the engaged stop still engaged is worth more than any
amount of reasoning about why it now cannot happen. Show the old path being
walked and not producing the old result.

## 2. F2 — the designed failure that looks like a defect

`hmi/config.yaml` is meant to fail at connect against today's CPU, because the
§12 nodes do not exist until the owner's TIA session. That is correct. But it
surfaces as a bare `BadNoMatch` retry loop, so the next person to hit it will
debug a working system.

Make it legible: say which node was not found, that this is expected until the
§12 nodes are downloaded, and where the procedure that adds them lives.

## 3. F4 — the three minor departures

Two page-invented millisecond constants, a missing selector caption, and the chip
tone. Close them against the design. Where the design is silent and the build had
to choose, say so in the report rather than backfilling the design.

## 4. F3 is NOT yours

The fifth undeclared consumer of the broken M4 harness path
(`sim/scenarios/run_forklift_rehearsal.py` and `forklift_commissioning.md`, which
a later gate criterion depends on) belongs to sim and plc. The orchestrator has
it. Do not touch those files.

## 5. Working discipline

- **Re-capture the screenshots your changes affect** into
  `hmi/evidence/screenshots/` and update the manifest and EVIDENCE_HMI.md §I.3.
  Do not leave the record describing a page that no longer exists.
- **Do not commit.** The orchestrator commits by pathspec.
- Write `docs/reports/m5-29b-hmi-v2a-fixes.md` in the CLAUDE.md §5 format.
- Read `docs/LESSONS.md` first.
