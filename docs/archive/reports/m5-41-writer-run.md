# m5-41 — run the stand-in writer against the live CPU

    brief:               docs/briefs/m5-41-writer-run.md
    status:              done
    files_changed:
      - bridge/standin_writer/EVIDENCE_BUILD.md                      (§3 run B written as each observation landed; §3.1 deferral table closed; §3.2 timers; §3.3 F3; §5 stale warning marked; §6.1 state left)
      - bridge/standin_writer/testing/observe_consumer.ps1           (four read-only columns added: StandInStaleTimer.Q and the three validated channels)
      - bridge/standin_writer/testing/opcua_witness.py               (new — TEST SCAFFOLDING, the independent witness on the §11.2 browse path)
      - bridge/standin_writer/testing/read_timers.ps1                (new — TEST SCAFFOLDING, reads IN/PT/ET/Q of every timer instance in a block)
      - bridge/standin_writer/evidence/                              (new — 16 capture files, listed in EVIDENCE_BUILD §B0.0)
      - docs/reports/m5-41-writer-run.md
    invariants_touched:  none
    open_questions:      see below
    next_suggested:      brief the bridge's forklift-group repoint against the live CPU — it is the one prerequisite left for the two ForkliftControl_DB timer PTs and for the M4 teleop loop on this build

---

## The observation the brief called the most important

**`HeartbeatSeen` and `StandInValid` were observed TRUE.** Instance
`safecell3`, `OperatingState = Run`, 199 tags,
`SafetyInputStandIn.StandInHeartbeat` present. Read in the consumer's view by
a separate process, 4,385.5 ms into the observer window, 385 ms after the
writer was launched:

```
        33.3  00000000011101110   0 0       baseline
     4,385.5  00000011111101110   3 3       CHANGE     HeartbeatChanged, HeartbeatSeen,
                                                       StandInValid -> TRUE; demands stay 1,1,1
```

The heartbeat advanced 3 → 718 over the next 40 s. Both demands stayed
latched, which is the correct half of it: belief is not motion. It was
reproduced twice more, at B5 and B7.

**And the fail-safe direction, observed twice.** Heartbeat frozen →
`StandInValid` FALSE → both demands latch, in **1,024.7 ms** (B4) and
**1,010.2 ms** (B6) against `StandInStaleTimer.PT` = `T#1S` read in force.
In both, the raw channels read closed (`1,1`) while the validated channels read
`0,0` — the S015 check visibly doing its work, which
`plc/forklift/TIA-BUILD-PROCEDURE.md` step 187 says cannot be seen until a
writer exists.

Also observed, each with the command that produced it and each written into
`bridge/standin_writer/EVIDENCE_BUILD.md` §3 as it landed: closing both
circuits clears no demand; the monitored reset clears both **on release**
(25.8 ms, hold 1,156.7 ms) and not on press; reopening the E-stop re-asserts
**only** `EStopDemand` and closing it again does not clear the latch; six keys
typed at one per second over 6.1 s do not starve the heartbeat; a restart
restores belief and not the latches; and `quit` writes all three channels FALSE
**while the writer still lives**, so the demands latch on channels already open.

## The witness — the brief was right to make me check

The m5-03b witness read the mirror as `ns=3;s="ForkliftSafetyMirror"…`, and
`DataBlocksGlobal` is no longer published. Three things were established before
anything was trusted:

1. The `opcua-nodes.md` §11.2 browse path
   `Objects/ServerInterfaces/DemoCell/Forklift/Safety/` **serves the four
   mirrors** and is the witness used throughout.
2. The old `ns=3` NodeId form **still resolves** — unbrowsable is not
   unaddressable for a string NodeId. The old witness would still have worked.
3. The F-side absence is stronger than its browse sweep proved: read by
   **direct NodeId**, `SafetyInputStandIn.*` and `InstF_Forklift_Safety.*`
   return **`BadNodeIdUnknown`**, not `BadNotReadable`.

**Consequence, stated rather than papered over: there is no OPC UA witness for
`HeartbeatSeen` or `StandInValid`, and none was invented.** They were read
where the brief directs — the F-block's own instance data, by
`testing/observe_consumer.ps1`, a separate process, a different memory location
from the four members the writer writes. The writer's own read-back was never
substituted; it has none by construction. The OPC UA witness ran beside it on
the consequence (the four `ForkliftSafetyMirror` values) and confirmed every
demand transition and non-transition independently.

## The two timers — answered, but not the way the brief expected

**`ModeDisagreeTimer.IN` and `StandstillTimer.IN` were not made TRUE, and the
reason is structural.** Both need the bridge writing `"ForkliftLink".BridgeHeartbeat`
(and, for the mode timer, `"ForkliftVehicle".ForkliftVehicleHeartbeat`).
`ForkliftLink` is a **different DB** from the M3 cell's `Link`, verified in the
live tag list; `bridge/config/bridge.yaml` is cell-only by its own statement and
maps `BridgeHeartbeat` to the cell's node, and `config/rehearsal-forklift.yaml`,
which does carry the forklift group, points at the PLC logic double and says
gate evidence does not run on it. **No committed configuration maps the forklift
group to the live CPU** — chunk P lists exactly that as the missing bridge
deliverable. Nothing was improvised to fill it.

What was done instead settles the question more strongly. All four members of
**every** timer instance in both blocks were read together:

- Every `ForkliftControl_DB` timer with `IN` TRUE holds its specified `PT`
  (`T#500MS`, `T#600MS`, `T#500MS`); **all five** with `IN` FALSE read `T#0MS`
  — not the two the procedure named. A defect at two call sites would not paint
  five.
- `PT` is **not** zeroed by `IN` falling: `ResetHoldMinTimer` reads `T#200MS`
  and `ResetHoldMaxTimer` `T#3000MS` **with `IN` FALSE**, because those two ran
  during this session's reset presses and kept what their call site wrote.
- Therefore `T#0MS` means **"this timer has never yet run on this build"**, not
  "a stale `PT` governs". It is the inverse of the LESSONS 2026-07-28 trap,
  where a non-zero wrong value ruled.

**No finding against the build**, and the narrow form of the open check should
stay open: `T#2S` and `T#500MS` remain design values until those two timers run.

## Not claimed

- **No T6 step is claimed closed.** What is claimed is a list of observations
  with the commands and captures that produced them; which of them satisfy
  `plc/forklift-safety/SPEC.md` §9 T6 and §4.5 step 13 is the verifier's ruling,
  not mine, and `EVIDENCE_BUILD.md`'s own N5 header says nothing in that file
  closes anything.
- **No PL, Category, SIL or PFH.** The path is a standard DB throughout
  (ADR 0011 D5). The writer stands in for wiring and carries no integrity claim.
- **Not run:** a CPU stop/restart repaired by the republish (it would stop a
  controller the owner has just finished building, and the design's §8 list does
  not contain it), and field-link acceptance against the real m5-12 evaluation,
  which does not exist.

## Nothing in `plc/` was touched, and one thing there is stale

`plc/` was read, never written. Nothing was downloaded, compiled, opened in TIA
or changed. **Step 189 of `plc/forklift/TIA-BUILD-PROCEDURE.md` still says no
writer implementation exists and the step is BLOCKED.** That sentence is stale
— the procedure's own progress block says so — and it is reported here rather
than fixed, because `plc/` is not this agent's to edit. Its record table row for
the three `ForkliftControl_DB` `PT`s would also read better with §3.2's
explanation attached.

## State the CPU was left in

Three channels FALSE, no writer process running (mutex acquired and released to
prove it), nothing on port 45015, `OperatingState = Run`, both demands and
`SafetyResetRequired` latched, `SafetyResetFault` clear. Two unavoidable
differences from the pre-run state, both recorded in `EVIDENCE_BUILD.md` §6.1:
`StandInHeartbeat` sits at 132 (a free-running counter, frozen — the only
property that means anything), and **`HeartbeatSeen` is TRUE**, because it is
the one-shot "life has been seen at least once" latch that this run existed to
set. Only a CPU STOP → RUN clears it, and stopping the controller was out of
scope.

## Open questions

1. **One writer process died at 21:13:35.953Z with no `TERMINAL` and no `EXIT`
   line**, mid-`CYCLE`, no `API` line, nothing in the Windows Application log,
   and the commanded kill in the same script had not yet run. The session's
   other three writer instances were unaffected, so it is not reproducible from
   this evidence and no mechanism is claimed (`EVIDENCE_BUILD.md` §3.3). It cost
   the planned shape of one test — which is why B6 re-ran the kill commanded —
   and it is itself an instance of the failure the design is built around: it
   converted to a latched demand in 1,024.7 ms with no operator action.
2. **The bridge's forklift-group repoint against the live CPU** is the one
   prerequisite for the two timer `PT`s, and it is bridge work with no brief.
   It needs an owner read-back of the `Forklift/` subtree per
   `opcua-nodes.md` §10.2 step 6 before a config may point at it.
3. **`testing/` now holds five scaffolding scripts.** They are labelled as such
   in their own headers, all read-only except `console_feed.ps1`, and separable
   from the deliverable if the verifier would rather they were not committed.
4. **m5-37's open question 2 is now observed rather than argued**: a partially
   successful write cycle leaves levels written and the heartbeat withheld, and
   the safe direction of that was visible again in run B. One clarifying line in
   `STANDIN-WRITER-DESIGN.md` §5.1 would settle it; not made, because the design
   document is the authority and this brief did not authorise amending it.
