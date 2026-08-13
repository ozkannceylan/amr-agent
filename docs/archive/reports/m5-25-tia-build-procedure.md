# m5-25 — the TIA build procedure, written for one session at the tool

    brief:               docs/briefs/m5-25-tia-build-procedure.md
    status:              done
    files_changed:
      - plc/forklift/TIA-BUILD-PROCEDURE.md (the deliverable, 116 numbered steps
        in ten chunks plus a chunk that builds nothing)
      - plc/forklift/evidence/m5-25-node-verify.py (the §12.11 step 6 /
        §14.13 step 8 verification, runnable by the session itself)
      - plc/forklift-safety/evidence/m5-25-standin-stimulus-repeat.ps1
        (m5-03b's script with the instance name as a parameter, so the repeat
        runs on `safe_amr` and not on the probe copy's instance)
      - docs/reports/m5-25-tia-build-procedure.md (this file)
    invariants_touched:  none
    open_questions:      six, below
    next_suggested:      m5-15 (F-program spec) — chunk J lists exactly what the
                         F-session needs and the procedure stops where it stops

---

## What was built

`plc/forklift/TIA-BUILD-PROCEDURE.md`. **116 steps**, each one physical action
with one observable result and one thing to tell the session, grouped into
chunks that each end at a safe stopping point with a verification and a named
screenshot. It carries a **progress block** (chunk / last completed step /
verified / notes) and a **record table** of the eleven values only the tool can
produce, each keyed to the step that produces it.

Chunk 0 ground truth → A four global DBs → B four interface folders and nine
nodes → C download and prove the node set from outside TIA → **D one decision**
→ E FB declarations → F the SCL body → G download and read the in-force values
→ H the m5-03b repeat on `safe_amr` → I housekeeping → **J what is not built
here**.

## The F-program half is absent, deliberately

No step builds, edits or downloads any part of the safety program. The
statement appears in the document's opening block, and **chunk J** names what
m5-15 must specify — S015, the automated writer and its home, the WSL→Windows
transport, the reset-origination path, and m5-12's field evaluation — as
things to see coming, with no build steps attached.

Chunk H does run the **existing** F-program as evidence: it writes three
standard DB tags through the PLCSIM Advanced API and watches four layers
follow. It changes no F-block and types no value into a fail-safe tag, which is
also the honest reason that path exists (`2206:000002`).

## Where the traps live

Each of the brief's six sits inside the step where it bites, not in a preamble:
green diff circles at steps 44 and 83 (and again at 111, after a `Tag_1`
deletion); "never rename a DB an interface binds" in the chunk-A header and
again at step 50 for the FB and its instance DB; the `_1` sweep at step 45
(automated) and step 84 (DB statics, by eye); in-force timer values from the
watch table at steps 90–91 with the reinitialisation branch at 92; the
fail-safe *Modify* refusal in the chunk-H preamble and at step 104; and the
namespace URI as a **read-back** at step 6, with the rename prohibition stated
as its consequence.

Two more, from LESSONS rather than the brief's list, are also in place: one
evidence file per run with a unique name (steps 46, 102), and clients down
before any download (step 41).

## Verifications the session can run itself

`plc/forklift/evidence/m5-25-node-verify.py` resolves the namespace by URI,
reads the interface's URI back, **walks the whole interface and flags every
BrowseName ending in `_<n>`**, checks the four folders and nine BrowseNames
character for character with their types and values, and attempts one write to
`Forklift/Envelope/ForkliftMotionEnable` — writing back the value the node
already holds — printing the refusal's status code, or failing loudly if the
write is accepted. It prints one `RESULT: PASS|FAIL` line. The owner transcribes
nothing; it runs at step 45 and again at step 96 once the program publishes the
same nodes.

Chunk H's second witness is the CPU's own OPC UA server, which cannot see
`SafetyInputStandIn` at all — a witness that cannot see the datum written, only
its consequence.

## Open questions

1. **The working project's PLCSIM instance name is recorded nowhere in this
   repository.** `FIO-FEASIBILITY` §0.1 records the probe's (`FIOPROBE`) and
   `opcua-nodes.md` §9.10 records the IP but no instance name; m5-03b mentions
   an instance `safecell3` registered but off. **Nothing was invented** — steps
   3 and 4 read the name and the IP back from the PLCSIM control panel and both
   are record-table rows. If the orchestrator wants it recorded permanently, it
   belongs in `opcua-nodes.md` §9.10, which is the interface agent's file.
2. **Sequencing tension, surfaced as step 49 (DECISION), not resolved here.**
   SPEC §14.14 state C says *do not apply this delta before HMI v2 writes the
   two new request nodes* — with HMI v1 running, `HmiProcessStopRequest` holds
   its `TRUE` start value, C7 holds `#worldOk` `FALSE`, and the cell is inert in
   both modes. The judge's Part B orders the TIA session (5) **before** HMI v2a
   (6). The procedure therefore stops at a natural boundary: chunks A–C change
   no behaviour, and step 49 asks the owner to choose between proceeding and
   stopping with the node set built. It is an owner decision, not an ADR one.
3. **§14.3 names the eleven new Temps but not their types.** The procedure
   assigns `#modeRequest` `UInt` and the other ten `Bool`, derived
   unambiguously from their use in §14.8's statements. Recorded here rather
   than left silent, because it is the one place the document states something
   §14 does not spell out.
4. **The timer statics' type string is the tool's, not the document's.**
   §14.3 says `IEC_TIMER` (TON); step 64 has the owner read the type off an
   existing timer static in the same FB and use that, rather than typing a name
   the tool may spell differently.
5. **`Tag_1` cannot be named from this repository.** TODO offers *named per
   CLAUDE.md §9 or deleted*; nothing records what it is, so step 110 deletes it
   only if the cross-reference shows no uses, and stops for an owner ruling if
   it has any. Naming it would be inventing.
6. **`RESET_HOLD_MIN`/`MAX` in force on `safe_amr` are unread.** The repeat
   script holds the reset 1000 ms, valid only between those two; the probe
   copy read 200 ms and 3000 ms and that is the probe's reading. Step 104 sends
   the session to the in-force values before any re-run rather than assuming
   they carried over.

## What this deliberately did not touch

`docs/TODO.md`, `docs/PLAN.md` and `docs/roadmap.md` (not this agent's files);
`plc/forklift/SPEC.md` and `plc/forklift-safety/SPEC.md` (unchanged — the
procedure quotes them and corrects nothing in them); the m5-03b originals in
`plc/forklift-safety/evidence/`, which stay as the probe-copy record they are.
No commit was made.
