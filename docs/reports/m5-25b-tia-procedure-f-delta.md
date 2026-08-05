# m5-25b — the TIA build procedure extended with the F-delta

    brief:               this task prompt (no file in docs/briefs/)
    status:              done
    files_changed:
      - plc/forklift/TIA-BUILD-PROCEDURE.md (chunks J–P, steps 117–191;
        header, preconditions, record table and step index updated)
      - plc/forklift-safety/evidence/m5-25b-f-absence-verify.py (new)
      - docs/reports/m5-25b-tia-procedure-f-delta.md (this file)
    invariants_touched:  none
    open_questions:      see below
    next_suggested:      the owner ruling on the stand-in writer's
                         implementation home (SPEC §10 open item 8) is what
                         step 189 waits on; nothing else in chunks J–O does

---

## What was delivered

`plc/forklift/TIA-BUILD-PROCEDURE.md` grew from **116 steps to 191**. The old
chunk J — "no step in this document builds the safety program, m5-15 does not
exist yet" — is replaced by six build chunks and one blocked-work table, in the
same one-action-per-step form as chunks 0–I: numbered step, one physical action,
one observable result, one question, a verification and a named screenshot per
chunk.

| Chunk | Steps | Built from | Ends with |
|---|---|---|---|
| J | 117–125 | SPEC §2 F0/F6/F7, §4.3, §4.5 step 1 | licence, safety mode, pre-delta signature, F-OB cycle, the F7 instruction check, and one decision |
| K | 126–142 | §4.5 steps 2–3, §3.1, §3.3 | `StandInHeartbeat`, eight statics, the constant, interface read back as 4 / 4 / 18 / 3 |
| L | 143–152 | §5.4 V1–V7 | seven validity networks ahead of `CauseGone` |
| M | 153–167 | §5.4 re-point table + M2 | thirteen pins re-pointed, 22 networks, `HeartbeatMemory` last |
| N | 168–180 | §4.5 steps 7–12 | changed collective signature, 4 reads / 0 writes, absence proven from outside TIA |
| O | 181–191 | §4.5 steps 13–14, §8 | three `PT`s in force, the invalid-boot signature |
| P | — | §10 open items | what is missing, whose it is, what it blocks |

**Nothing was re-derived.** §4.5's fourteen verified steps and §5.4's eight
networks were expanded into single actions, not rewritten; every name, type,
value, pin and negation is quoted from `plc/forklift-safety/SPEC.md` §3–§5.

### Verification the session can run itself

New instrument: **`plc/forklift-safety/evidence/m5-25b-f-absence-verify.py`**,
run at step 179 with the endpoint read back at step 4. It replaces "browse
UaExpert and read the tree aloud" with a `RESULT:` line, and it **writes
nothing** — the claim is that the datum is unreachable, so a write probe would
assert the reachability it exists to deny (the opposite design from
`m5-25-node-verify.py`, whose whole point is a refused write).

It runs a **positive control before the absence check** and aborts if the
control fails: the four `Forklift/Safety/` mirrors of `opcua-nodes.md` §11.2
must browse and read first, because an absence proven by a browse that never
reached the server is not an absence. Then it sweeps the whole `Objects`
subtree for `SafetyInputStandIn`, `StandInHeartbeat`, `InstF_Forklift_Safety`,
`F_Forklift_Safety` and `Main_Safety_RTG1`, lists what `DataBlocksGlobal`
actually holds, and sweeps every visited BrowseName for `_1` suffixes.

Elsewhere the chunks prefer a tool read-back over a judgement: the collective
signature before (119) and after (176), the interface counts read off the table
(130, 141), the re-point verified by **search** rather than re-reading thirteen
pins (164), the cross-reference count (178), and the three `PT`s in force (186).

### One ordering constraint found while writing, and it is load-bearing

**Chunk H must run before chunk J and cannot be re-run after it.**
`m5-25-standin-stimulus-repeat.ps1` writes the three Bool channels and **no
heartbeat**. After the S015 delta a frozen heartbeat means `StandInValid`
`FALSE`, which forces all three validated channels to open/unpressed — so the
script would be driving a program that has correctly stopped believing it, and
its phases (b), (c) and (d) could not pass. §2 F3 is therefore closed **before**
the delta or not at all. This is stated in the document header, in the chunk J
preamble and at step 121, which stops if the chunk H log is missing.

### The traps sit inside the steps that they bite

Green diff circles before any reading (175); no DB renamed once an interface
binds it (129's read-back, and the FB/DB rename ban carried from step 50);
`_1` swept by eye on the statics (177) and by machine on the browse names
(179); timer values read in force from the watch table, never from interface
defaults (186, and 174's re-initialisation which is why they should be right);
no step anywhere plans to *Modify* a fail-safe tag (118 says so, 182 says the
table is a reading instrument); and the namespace URI stays a read-back value —
the absence script resolves `http://DemoCell` from the server's own namespace
array and types it into nothing.

## What is marked BLOCKED rather than invented

No value, tag or path was created to fill a gap. Four gaps are marked in place
and gathered in chunk P:

1. **The stand-in writer has no implementation home** — an owner ruling, not
   made (SPEC §10 item 8). This is **step 189**, which states plainly that
   §4.5 step 13 cannot run, what is proven without it (the delta compiles,
   downloads with a changed signature, is client-unreachable, holds its `PT`s,
   and fails in the stopping direction with the stand-in dead), and what stays
   unproven and may not be cited by any gate criterion (validity ever becoming
   `TRUE`, every T6 step, the whole reset path on this build). Step 125 makes
   the same consequence a **decision** before the delta is built, in the shape
   of chunk D: the F-program is deliberately inert afterwards.
2. **m5-12's field-evaluation transition log does not exist** — the zone
   channel's criterion-(a) form is unavailable; named in chunk P.
3. **`sim/scenarios/forklift_commissioning.md` §13** still describes
   watch-table *Modify*; named in chunk P as contradicting SPEC §9.1 for anyone
   reading both.
4. **Two safety-spec rulings are open** — the `RESET_HOLD_MIN` sampling
   deviation and AT-08 (b)'s scope. Step 120 names the deviation where the
   F-OB cycle is read, steps 158 and 159 forbid touching either `PT` at the
   keyboard, and chunk P records that every evidence record from this build
   carries one line naming the deviation.

## Open questions

1. **Does a watch table named `Forklift F gate` already exist?** SPEC §8
   specifies it; whether the 2026-07-30 build created it is recorded nowhere.
   Step 181 asks the owner instead of assuming either way, and step 182 creates
   it if not.
2. **§2 F7 is a genuine unknown** — whether this safety instruction set offers
   an Int `<>` and `MOVE`. Steps 122–123 check it before a single network is
   built and **stop** if either is missing, because the fallback (a Bool toggle
   with a period of at least three writer cycles) is a specification change,
   not a keyboard substitution.
3. **The absence script has not been run against a live CPU.** It parses and
   follows `m5-25-node-verify.py`'s proven structure, but like every other
   tool-facing artefact in this project it is a design value until step 179
   produces its first `RESULT:` line.
4. **A new LESSONS entry is warranted** and is the orchestrator's to append:
   an instrument built for a program's earlier form can be invalidated by the
   delta it precedes — the repeat script writes no heartbeat, so the S015 check
   retires it as a stimulus the moment it lands. That is not a defect in either
   artefact; it is an ordering constraint that only appears when the two are
   read together.
