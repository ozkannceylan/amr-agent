# m5-28 — build HMI v2a

    gate:                M5 (criterion (e), first half)
    agent:               hmi
    goal:                HMI v2a exists and runs against a double: visually reduced, mode selection, the process-stop control, safety lamps — built to hmi/V2A-DESIGN.md, with a screenshot of every meaningful state for the owner to review.
    invariants_touched:  none — invariant 1 is what the design exists to respect
    inputs:
      - hmi/V2A-DESIGN.md — **the authority.** Where this brief and the design disagree, the design wins and you say so in the report
      - docs/reports/m5-27-hmi-v2a-design.md — its two owner open questions
      - docs/interfaces/opcua-nodes.md §12 (the node set; §12.8's boot values)
      - plc/forklift/SPEC.md §14 (especially §14.9, the cold start)
      - hmi/ — the v1 backend, UI, config, EVIDENCE_HMI.md
      - docs/LESSONS.md
    deliverable:         HMI v2a in hmi/, the interim double the design specifies, screenshots in hmi/evidence/screenshots/, and EVIDENCE_HMI.md updated
    done_when:           The page runs against the double; every state in §3 below is captured as a screenshot and listed in EVIDENCE_HMI.md; the cold-start sequence of the design is walked end to end and recorded; and the adopt-window behaviour is exercised against an executable double, not asserted.
    forbidden:
      - inventing an OPC UA node — the design's write set is the §12.1 eight, all existing
      - any HMI-side timer, latch or verdict about mode arbitration; the PLC owns it (invariant 10) and the design says zero
      - giving the process-stop control the visual language of a real e-stop — no mushroom, no red-on-yellow, no "emergency" wording; red is reserved for the two F-demand lamps
      - designing or building the live map, the monitoring plane, or anything needing m5-13 — that is v2b
      - answering the report's two owner open questions; implement conservatively and flag
      - writing outside hmi/ except your report
      - connecting to the live PLC — the CPU has no §12 nodes yet; you build against the double

---

## 1. Build the design, not your reading of it

`hmi/V2A-DESIGN.md` settles the decisions. Build it. If something in it cannot be
built as written, **stop and report that** rather than substituting a judgement —
the design was reviewed for exactly the ambiguity you would be resolving.

The single most important property, restated so it cannot be lost in
implementation: **the process-stop control must never look armed when its effect
could not arrive.** Session down or `HmiLinkOk` false → UNAVAILABLE. A control
that looks live over a dead link is the defect this whole design exists to
prevent.

## 2. The adopt window is tested, not asserted

LESSONS 2026-07-31: the obvious steady-state form of a commanded-vs-reported
comparison made autonomous mode **permanently unreachable**, and a throwaway
executable double found it where review had not. So:

- drive the double through a mode change with a **realistic adopt delay**, not an
  instant one;
- show the in-flight rendering actually appearing, and clearing;
- show what a disagreement that never resolves looks like.

An adopt window that only ever completes in zero time has not been tested.

## 3. Screenshots — the owner reviews these before anything else

Capture into `hmi/evidence/screenshots/` (gitignored by owner ruling, so these
stay local). Name each file for the state it shows. At minimum:

1. cold start, before the operator does anything
2. each step of the cold-start sequence that changes what is on screen
3. teleop mode in force
4. autonomous mode in force
5. **a mode change in flight** — the state §2 exists to prove
6. process stop engaged
7. process stop released
8. link stale / session down — the control UNAVAILABLE
9. safety lamps: healthy, F-demand active, and **value stale or unavailable**
10. anything the design specifies that the list above misses — read it and add

`EVIDENCE_HMI.md` lists which file shows which state. **The files are local but
the record of what was captured is not** — a claim to have screenshotted
something is worth nothing without that list.

## 4. The double

The design splits this: a requested `plc/forklift/double/` §14 extension (not
yours — it is requested in the report) and an **interim hmi-owned scripted
scenario double** so this build does not stall on the owner's TIA session. Build
the interim one. It must serve the §12 set including §12.8's non-permissive boot
values, or the cold-start sequence cannot be exercised at all.

## 5. Working discipline

- **Write into the evidence as each state lands.** Create the EVIDENCE_HMI.md
  section with its headings before your first capture.
- **Do not commit.** The orchestrator commits by pathspec.
- Write `docs/reports/m5-28-hmi-v2a-build.md` in the CLAUDE.md §5 format.
- Read `docs/LESSONS.md` first. Beyond the adopt-window entry, note that a page's
  DOM handlers can pass an endpoint test while being themselves unexercised
  (the EVIDENCE_HMI §C residual) — exercise the page, not only the backend.
