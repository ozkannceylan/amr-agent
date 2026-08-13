# m5-41 — run the stand-in writer against the live CPU

    gate:                M5 (criterion (a)); closes forklift-safety SPEC §4.5 step 13 and T6
    agent:               bridge
    goal:                The heartbeat advances, StandInValid goes TRUE, the F-program runs on written data, and stopping the writer drops validity and latches both demands — all observed, none asserted.
    invariants_touched:  none
    inputs:
      - plc/forklift/TIA-BUILD-PROCEDURE.md — **read its progress block and record table FIRST.** It is the authoritative account of what the owner proved and what they did not
      - bridge/standin_writer/standin_writer.ps1 and bridge/STANDIN-WRITER-DESIGN.md
      - bridge/standin_writer/EVIDENCE_BUILD.md §3 — the checks listed as unrun; they are what you are running
      - docs/reports/m5-37-standin-writer-build.md
      - plc/forklift-safety/SPEC.md §4.5 (step 13) and §9 (T6)
      - plc/forklift-safety/evidence/m5-25-opcua-witness-2026-08-05.log and m5-25b-f-absence-2026-08-05.log
      - docs/LESSONS.md
    deliverable:         bridge/standin_writer/EVIDENCE_BUILD.md filled in, and docs/reports/m5-41-writer-run.md
    done_when:           `HeartbeatSeen` and `StandInValid` are observed TRUE, the reset path is observed working on this build, and stopping the writer is observed dropping validity and latching both demands — each with the command that produced it.
    forbidden:
      - downloading, compiling, or changing anything in TIA — the owner's build is finished and this brief only writes tag values and reads them back
      - editing `plc/` — you may READ everything there
      - claiming any T6 step that you did not observe
      - claiming or implying an achieved PL, Category, SIL or PFH — the path is a standard DB throughout (ADR 0011 D5)

---

## 1. What changed since the writer was built

The writer was blocked on one thing: `SafetyInputStandIn.StandInHeartbeat` did
not exist. **It exists now** — created and downloaded in the owner's session of
2026-08-05. Everything else in `EVIDENCE_BUILD.md` §3's unrun list should now be
runnable.

**Step 189 of the build procedure says the writer does not exist. That sentence
is stale**, and the procedure says so itself. Note it in your report; do not edit
`plc/`.

## 2. One thing that probably broke your witness — find out before you rely on it

The m5-03b proof read `ForkliftSafetyMirror` through **`DataBlocksGlobal`**. The
owner's session established that **`DataBlocksGlobal` is not published at all**
any more, and an external client proved the F-side and the stand-in DB are absent
from the server's address space. That was deliberate and it is a good property.

So **the old witness path may be gone.** Before you trust any OPC UA reading,
establish what the server actually publishes now — the §12 node set exists under
`Forklift/`, and the mirror may be reachable there instead. If no independent
witness is reachable, say so and fall back to the F-block's own instance data,
which is still a different memory location from what you write. Do not quietly
substitute the writer's own read-back; that is the failure this whole path was
built to avoid.

## 3. The run

1. Start the writer against instance **`safecell3`**.
2. Observe **`HeartbeatSeen`** and **`StandInValid`** go TRUE. This is the single
   most important observation in the brief — everything since the S015 delta
   landed has been waiting on it.
3. Drive the three channels and observe the F-program react: circuits closing
   without clearing a demand, the monitored reset clearing them on release, and
   a circuit reopening re-asserting. Report the latencies as observations.
4. **Stop the writer** and observe validity drop and both demands latch. That is
   the fail-safe direction and it is as important as step 2.
5. Work through `EVIDENCE_BUILD.md` §3's unrun list and mark each one run or
   still unrun with the reason.

## 4. Then the two timers

`"ForkliftControl_DB".ModeDisagreeTimer.PT` and `.StandstillTimer.PT` both read
`T#0MS` in the owner's session **because their `IN` was FALSE** — the procedure
records this as an open check, not a defect. It looks exactly like the stale-PT
trap of LESSONS 2026-07-28 and is not the same thing.

Re-read both **with the bridge running**, so `IN` can be TRUE, and report the
in-force values. If they still read `T#0MS` with `IN` TRUE, that is a finding.

## 5. Working discipline

- **Write into the evidence as each observation lands.** A session limit
  destroyed an agent's unwritten work yesterday.
- **Leave the CPU as you found it.** Restore the three channels and stop the
  writer cleanly; the owner's build is finished work.
- **Do not commit.** The orchestrator commits by pathspec.
- Read `docs/LESSONS.md` first. Directly yours: an API write is verified in the
  consumer's view, and a polled log line is evidence only together with its age.
