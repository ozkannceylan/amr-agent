# m5-27 — HMI v2a: the design, before any code

    gate:                M5 (criterion (e), first half)
    agent:               hmi   (design only; the build is m5-28)
    goal:                A design for HMI v2a — visually reduced, mode selection, emergency button, safety lamps — settled on paper before a line of it is written, with the one dangerous ambiguity in it named and resolved.
    invariants_touched:  none expected — invariant 1 is the one this design presses on, see §2
    inputs:
      - docs/roadmap.md, the M5 row criterion (e)
      - docs/adr/0010-milestone-restructure-forklift-first.md, **D6(b)** — the emergency button decision
      - docs/adr/0011-sensored-autonomy-architecture.md (D4, D5), docs/adr/0012, docs/adr/0014
      - docs/interfaces/opcua-nodes.md **§12** — the envelope, mode and process-stop nodes, especially §12.8's boot values
      - plc/forklift/SPEC.md §14 — mode arbitration and envelope formation, the program this HMI drives
      - hmi/ — all of it: the v1 backend, UI, config and EVIDENCE_HMI.md
      - docs/reports/m5-23-judge-review.md Part B step 6
      - docs/LESSONS.md
    deliverable:         hmi/V2A-DESIGN.md and docs/reports/m5-27-hmi-v2a-design.md
    done_when:           The design names every control and every indicator, says which OPC UA node each reads or writes, resolves §2's ambiguity explicitly, and states what v2a does NOT do. A coding agent can build from it without a second decision.
    forbidden:
      - writing code, templates, CSS or configuration — this brief produces a design document
      - designing the live map, the monitoring plane or anything that needs m5-13 — that is v2b
      - proposing any write path that is not already a node in `opcua-nodes.md` §12; a node the design needs but §12 lacks is a REQUEST in the report, never an invention
      - any control that writes a safety function, bypasses an interlock, or sends a velocity across the seam (invariants 1 and 6, ADR 0014)
      - restating a measured figure from docs/TODO.md §"Measured numbers…"

---

## 1. What v2a is

Criterion (e), first half: the M4 HMI, **visually reduced**, gaining

- **mode selection** — teleop / autonomous,
- an **emergency button**,
- **safety lamps** showing F-layer state.

The live map is **v2b** and needs the monitoring service (m5-13). Do not design
it here; do say what v2a must not foreclose.

## 2. The dangerous ambiguity — resolve it, do not soften it

**An operator who sees a big red button on a screen believes it stops the
machine.** In this architecture it does not, and cannot: invariant 1 says safety
never traverses the network, and ADR 0010 D6(b) governs what this button
actually is — a **process stop** issued over OPC UA, plus a **display** of
F-layer state that the HMI only reads.

Read D6(b) and design to it. The design must state, concretely:

- what the button does, in one sentence an operator would understand;
- **how the interface makes clear it is not the safety e-stop** — wording,
  labelling, placement, and what it must NOT look like. Borrowing the visual
  language of a real e-stop for a process control is the failure mode here;
- what the operator is supposed to reach for when they need the real thing;
- how a **stale or dead link** appears, since a button whose effect cannot
  arrive must not look armed. Invariant 2: link loss is a degraded mode, and the
  vehicle's own watchdog handles the vehicle — say what the *screen* shows.

If you conclude D6(b) cannot be satisfied without weakening invariant 1, stop
and write that instead. That is a real possible outcome and it is more valuable
than a design that papers over it.

## 3. Mode selection — the trap is already documented

LESSONS 2026-07-31: a term comparing a **commanded** state with a **reported**
one must be written against the **adopt window**, not the steady state. The
mode-arbitration spec's obvious live form disarmed the enable one call after
entry and made autonomous mode permanently unreachable — found by a throwaway
executable double, not by review.

So the design says what the operator sees **while a mode change is in flight**,
not only in the two settled states: requested, in force, disagreeing, and how
long a disagreement may last before it is shown as a fault. `SPEC.md` §14 owns
the arbitration; the HMI displays it and must not reimplement it (invariant 10).

## 4. The boot problem, which is why v2a exists at all

`opcua-nodes.md` §12.8: every §12 value boots **non-permissive**, and
`HmiProcessStopRequest` starts TRUE. **The §14 program is inert until an HMI can
clear those.** That is precisely why HMI v2a is a hard prerequisite for the PLC
delta to do anything (m5-23 Part B step 6).

The design therefore says what the operator does on a cold start, step by step,
and what each step changes — including what must be true before the machine will
move at all. A cold-start sequence the operator cannot follow is a defect.

## 5. It must be buildable before the CPU has the nodes

The running CPU serves six Forklift DBs and **no envelope, mode or process-stop
node**; those arrive in the owner's TIA session
(`plc/forklift/TIA-BUILD-PROCEDURE.md`). So v2a is developed against a **double
that serves §12**, and the design says what that double must serve, so the build
does not stall waiting for hardware. Note the project already has doubles in
`bridge/config/` — reuse the pattern rather than inventing one.

## 6. Safety lamps

They **read** F-layer state and never write it. Say which node each lamp reads,
what each state looks like, and — the part usually skipped — what a lamp shows
when the value is **stale or unavailable**. A lamp that looks healthy when it
has no data is worse than no lamp.

## 7. What the report must carry

- every node the design reads or writes, checked against §12 by name;
- anything §12 lacks, as a **request** to the interface agent;
- what v2a explicitly does not do;
- open questions that are genuinely the owner's, marked as such.

## 8. Working discipline

- Read `docs/LESSONS.md` first.
- **Write the design as it settles**, not in one pass at the end.
- **Do not commit.** The orchestrator commits by pathspec.
- Prefer a short document and a diagram over prose (CLAUDE.md §10).
