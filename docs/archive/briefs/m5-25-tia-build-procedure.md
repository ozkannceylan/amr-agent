# m5-25 — the TIA build procedure, written for one session at the tool

    gate:                M5 (supporting)
    agent:               plc
    goal:                A step-by-step procedure the owner executes in TIA Portal, one action at a time, that builds what M5 needs on the CPU and proves each piece before the next.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-23-judge-review.md — **Part B especially**, the ordered end-to-end sequence and its owner/agent split
      - docs/TIA-SESSION-PROMPT.md — the session that will read your document; it gives ONE step per message
      - plc/forklift/SPEC.md §14 (mode arbitration and envelope formation — m5-16, closed)
      - docs/interfaces/opcua-nodes.md §12 (the nodes to add — m5-17, closed)
      - plc/forklift-safety/FIO-FEASIBILITY.md, docs/adr/0015-criterion-a-standin-stimulus.md
      - docs/reports/m5-03b-standin-stimulus-proof.md (the run to repeat on `safe_amr`)
      - plc/forklift-safety/evidence/m5-03b-standin-stimulus-proof.ps1 (the script that did it)
      - docs/LESSONS.md — the TIA traps
    deliverable:         plc/forklift/TIA-BUILD-PROCEDURE.md
    done_when:           Every step is one physical action with one observable result; the document carries a progress section a session can update and resume from; and each chunk ends with a verification and a named screenshot.
    forbidden:
      - specifying any part of the F-program that m5-15 has not written — see §2, this is the one way this document can do real harm
      - inventing a tag, node, block or value: every name comes from SPEC §14 or opcua-nodes §12, quoted
      - writing outside plc/ except your report
      - bundling two actions into one step because they are "obviously together"
      - instructing entry into a field TIA derives rather than accepts (LESSONS 2026-07-27, the namespace URI)

---

## 1. Scope — what this procedure builds

From the judge's Part B, the single TIA session covers:

1. **The §14 standard-program delta** — mode arbitration and envelope formation
   (`plc/forklift/SPEC.md` §14, specified and closed).
2. **The §12 OPC UA nodes** — envelope, mode and process stop
   (`opcua-nodes.md` §12, specified and closed). Today the CPU publishes six
   Forklift DBs and **no envelope, mode or permit node**; that is the gap.
3. **The m5-03b stand-in proof repeated on the working project `safe_amr`** —
   it has only ever run on the probe copy, and the gate cannot cite it until it
   runs on the real one. The script exists; the procedure says how to run it.
4. **Deleting the probe copy `safe_amr_FIOPROBE`** (FIO-FEASIBILITY §0.1 rule 3).

## 2. The one thing that would do real harm

**Do not write F-program build steps.** The F-program specification is m5-15 and
it does not exist yet. A procedure that tells the owner to build fail-safe logic
from an unwritten spec would produce a safety program nobody specified.

State plainly, in the document, that the F-program half is **pending m5-15**, and
end the procedure where the specified work ends. Say what the F-session will
need so the owner can see it coming — do not describe how to build it.

## 3. Shape — this document is read one step at a time

`docs/TIA-SESSION-PROMPT.md` will drive a session that gives the owner exactly
one step per message and waits. Write for that:

- **Number every step.** The session says `[step N of M]`, so M must be real.
- **One physical action per step.** Name the pane, the tab, the button, the
  field. "In the project tree, right-click X → Y" beats "add a Z".
- **One observable result per step** — what the owner should see, so the session
  has something to ask about.
- **Chunks.** Group steps into chunks that each end somewhere safe to stop, with
  a verification and a named screenshot (`plc/forklift/evidence/m5-25-<slug>.png`).
- **A progress section** the session updates: chunk, last completed step, what
  is verified. Resuming must cost nothing.
- Where the owner must decide rather than type, mark the step **DECISION** and
  say what depends on the answer.

## 4. The traps that must be built in, not appended

From LESSONS — each belongs inside the step where it bites, not in a preamble:

- After **every** download, check the block diff circles are solid green before
  testing; a stale build shows as monitoring-error icons and an in-force timer
  value that contradicts the call site.
- **Never rename a DB** once a server interface binds it — the rename drags every
  interface reference and the repair introduces silent browse-name breakage.
- After every download, **sweep browse names for TIA's `_1` collision suffixes**;
  it appends them without asking, in DB statics and interface rows both.
- Read timer values **in force from the watch table**, never from interface
  defaults; an interface default governs nothing once the instance DB exists.
- **Fail-safe tags cannot be modified from the engineering connection** in
  permanent safety mode (`2206:000002`) — so no step may plan to.
- A server interface's **name is its namespace URI** (ADR 0006); it is chosen
  deliberately, never discovered in the tool.

## 5. Verification, per chunk

Each chunk ends with something checkable, and where possible checkable **without
the owner reading a value aloud** — the OPC UA server is browsable from outside
TIA, and the m5-03b evidence shows how (`plc/forklift-safety/evidence/
m5-03b-opcua-witness.py`). Prefer a verification the session can run itself over
one the owner must transcribe.

## 6. Working discipline

- **Write the document as it takes shape**, not in one pass at the end.
- **Do not commit.** The orchestrator commits.
- Write `docs/reports/m5-25-tia-build-procedure.md` in the CLAUDE.md §5 format.
- Read `docs/LESSONS.md` first.
