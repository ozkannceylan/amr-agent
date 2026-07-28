# Report m3-34 — link boot polarity, the reset guard, and the 4.11 procedure

brief:               docs/briefs/m3-34-link-polarity-spec.md
status:              done
files_changed:       plc/demo-cell/SPEC.md (+303 / −69, one logical change; not committed)
invariants_touched:  none

---

## What changed, and why each site had to change

### 1. The verdict (§6.1, §7 part 1, §3.2, §3.3)

`BridgeLinkOk := HeartbeatSeenAlive AND NOT HeartbeatStaleTimer.Q`, where
`HeartbeatSeenAlive` is a new FB static (Bool, start value `FALSE`, non-retain)
latched by the first observed heartbeat change. `NOT staleTimer.Q` alone reads
"not *yet* proven stale", which is `TRUE` for the first `HEARTBEAT_STALE_TIME` of
every CPU run — the boot window. §6.1 now names the three things that window let
through (the guard cleared on the first scan from a start value; the held reset's
edge at link-up; and the part-4 stop latch formed from start-value contacts), and
states that the correction belongs in the verdict because the last two are one
defect reached by two consumers.

Two smaller consequences are now stated where they will be read:
`HEARTBEAT_STALE_TIME` no longer sets the length of any window in which the
program trusts start values (§3.3, so open item 1 is a pure staleness question);
and a first heartbeat write that happens to equal the start value `0` delays the
verdict by one bridge cycle without ever reversing it.

### 2. The reset guard (§6.7, §7 part 6, §3.2)

`ResetDeviceFault` is no longer cleared "permanently, for this program run". It
is a **level verdict about the current link session**: set `TRUE` whenever
`BridgeLinkOk` is `FALSE`, cleared only while the link is OK and
`PanelResetPressed` reads `FALSE`.

The boot-polarity fix alone does **not** close T4.9b. It closes it at CPU start,
and moves it to bridge restart: during an outage the reset image freezes at
`FALSE`, so `ResetEdgeMemory` sits at `FALSE` and the first attributable `TRUE` is
a genuine rising edge — which a run-long guard, legitimately cleared hours
earlier, would admit. That is exactly the recorded failure with a different
trigger, and it is why the guard had to be re-derived rather than left to inherit
the new polarity. §6.7 also records that the re-arm is free in normal operation
(startup rule R3 delivers all seven inputs before the heartbeat, so the guard
clears within one OB call of link-up and T4.3 still needs one press pair), and
that its guarantee is conditional on the input image being truthful — a
conditionality the PLC cannot remove, now carried as open item 7.

### 3. The cold-start narrative (§6.1, §3.1, §6.2.2, §6.3, §8 case A and C, §9)

The deliberate side effect: with the verdict pessimistic at boot, §7 part 4 no
longer latches a process stop from start-value contacts. §6.1 carries an old-build
/ corrected table for the cold-start signature. The changed cell is
`CellProcessStopActive`: **`TRUE` → `FALSE`**. Nothing is weakened —
C1, C2 and C3 all still read `FALSE`, `LinkLostLatch` still sets at the first
scan, `CellResetRequired` is still `TRUE`, a monitored reset is still required —
and the reason the program gives is now the true one.

This voids half of a recorded observation, so it is written out rather than left
to collide: the owner's 2026-07-27 cold-start reading, which m3-26's first read
reproduced exactly, had `CellProcessStopActive TRUE` as a property of the
boot-`TRUE` build. §8 case C and §11 T4.5 / T4.8 are rewritten to the corrected
signature.

Three further statements were corrected because they depended on the old polarity
or on the old restart story, and were not named in the brief:

- §3.1's "the start values only apply at a **cold** restart" — the one restart
  actually recorded (2026-07-28, CPU STOP → RUN under a live session) reverted all
  seven inputs, so the hedge is not what was observed.
- §6.2.2's "the window is not what holds a freshly started CPU — `BridgeLinkOk`
  is" — true only from the 500th millisecond under the old build; now qualified
  "from the first scan".
- §6.7's "a reset cannot be honoured from a frozen or start-value input image" —
  this was decoration for the first 500 ms of every CPU run, because `CauseGone`
  carried a `BridgeLinkOk` that was `TRUE`. It became true when the verdict did.

§6.3 gained the C3 boot bullet, including the one narrow exception where no
`LinkLostLatch` forms (bridge already writing before the CPU's first OB call) and
the note that the edge memories, not the latch, are the guarantee in that corner.

### 4. §11 T4.9b, T4.11 and the count

- **T4.9b** is re-specified as one step with **two** ways of creating its
  precondition — (a) fresh bridge with the reset held from before link-up, which
  is the variant the 2026-07-28 run actually used and failed, and (b) CPU cold
  start with `reset` already published. The step as written said only (b), so its
  procedure and its as-run procedure had diverged. Both must hold, because the
  corrected guard treats them identically.
- **T4.11** is reduced to the reaction path (verdict, permissive drop, setpoint
  gate), read off the 20 Hz CSV rather than the watch table, with **no latch
  expected and its absence explicitly not a failure**: zeroing the setpoint
  returns the plant inside the narrowed window in ~100–150 ms, under
  `BELT_FAULT_DELAY`, so the timer is released before `Q`. The method is
  self-extinguishing — the narrowed window is escaped by the reaction it triggers.
- **T4.11b** is new: the latch, the reset refusal while the condition holds, and
  the reset that clears it afterwards, on §12 item 6's hold-until-disarmed
  injection facility. Marked **BLOCKED**, not runnable, not a pass by default.
- The T4 denominator therefore goes **thirteen → fourteen**, per the document's
  own rule 2. The note under the pass line no longer mirrors the as-run roster
  (which `EVIDENCE_LATENCY.md` §B.7 owns and a sibling agent is rewriting); it
  states only what this revision changes about it.

### 5. §12

Item 6 is corrected — the narrowed-constant test verifies the reaction path and
**cannot** reach the delay, the latch or the reset, so §6.2.2's latch is
specified and unverified — and the request now includes *holding* the injected
value until disarmed. New **item 7** carries the bridge's rewrite-on-restart
requirement, because the reset guard's guarantee and §8 case C both depend on the
input image being truthful after a server restart, and no PLC-side test
distinguishes a stale `FALSE` from a real one.

---

## The owner's implementation delta

Stated in the spec as **§6.8**, and reproduced here. One declaration and two
statements in `FB_DemoCellControl`; no new block, no new node, no interface
change, nothing bridge-side, and no change to the heartbeat mechanism:

1. Add static `HeartbeatSeenAlive : Bool := FALSE;`
2. §7 part 1, after the `LastBridgeHeartbeat` assignment:
   `IF #hbChanged THEN #HeartbeatSeenAlive := TRUE; END_IF;`
3. §7 part 1, the verdict:
   `"DemoCellLink".BridgeLinkOk := #HeartbeatSeenAlive AND NOT #HeartbeatStaleTimer.Q;`
4. §7 part 6, the guard: replace the single-branch clear with
   `IF NOT #linkOk THEN #ResetDeviceFault := TRUE; ELSIF NOT "DemoCellInput".PanelResetPressed THEN #ResetDeviceFault := FALSE; END_IF;`
5. Watch table Group 4: add `"DemoCellControl_DB".HeartbeatSeenAlive`

After the download, before any re-run: block diff circles solid green,
`HeartbeatSeenAlive TRUE` and `BridgeLinkOk TRUE` with the bridge running, and
`HeartbeatStaleTimer.PT` still `T#500ms` **in force** — a new static shifts DB
offsets, and a download without reinitialisation preserves stale instance values
(LESSONS 2026-07-28).

**Re-run list:** §11 4.2, 4.3, 4.5, 4.8, 4.9b — the steps that cross a CPU start
or a link-up. Unaffected in kind: T1, T2, T3, 4.1, 4.4, 4.6, 4.6b, 4.7, 4.9,
4.10, 4.11. Nothing in §6.2–§6.6 changes.

---

## Requests for files outside plc/

Each is a consequence of this deliverable that I am not permitted to write.

1. **`bridge/EVIDENCE_LATENCY.md` Section B** (a sibling agent is editing it now,
   so this is a request, not an edit): the specified T4 denominator is now
   **fourteen**, not thirteen; **4.11b** needs an outstanding row (blocked on the
   fault-injection facility, §12 item 6); **4.11** should be recorded as the
   reaction path demonstrated, with the latch step explicitly not covered; and
   **4.2, 4.3, 4.5, 4.8, 4.9b** need outstanding rows for re-run against the
   corrected build, since their behaviour changes with §6.8's delta.
2. **`docs/TODO.md`** line 5 records the owner's cold-start reading with
   `CellProcessStopActive True` as the specified behaviour. Under the corrected
   build the expected cold-start value is `False`; the line needs restating (the
   wire-NC/program-NO confirmation in it stands). `docs/PLAN.md` line 108 quotes
   the same "cold-start state read" and should be checked against it.
3. **`docs/reports/m3-26-live-loop-run.md`** states that its first read reproduced
   that cold-start reading exactly. It is a historical record of a real run and
   should not be rewritten; if reports are annotated at all, it needs a pointer to
   this correction rather than an edit.
4. **`docs/LESSONS.md`** — two rows this work suggests, if the orchestrator agrees:
   that a guard qualified by a link verdict must be re-armed at every link-down,
   because a verdict fix at boot only relocates the failure to the next link-up;
   and that a fault test whose stimulus is the plant's own values is extinguished
   by the reaction it triggers, so the delay it is meant to exercise can never
   elapse.
5. **`bridge/`** — open item 7 (rewrite every slot after a server restart) is
   already in `docs/TODO.md`; it is now a named dependency of §6.7's guarantee and
   of §8 case C, so it should be briefed rather than left as a note.

open_questions:
- Does the owner accept the cold-start signature change (`CellProcessStopActive`
  `TRUE` → `FALSE` with the bridge stopped)? It is the correct reading of §6.1's
  own qualification rule, but it changes what the demonstration shows at power-up
  and it contradicts a reading the owner took by hand on 2026-07-27.
- `HEARTBEAT_STALE_TIME` is now purely a staleness constant. Open item 1's
  re-check against the PLCSIM run is unblocked and no longer has a boot-window
  cost attached; worth folding into the T3 re-run rather than carrying separately.
- §12 item 4 (the bridge must carry the reset node) reads as still open, but the
  2026-07-28 run drove `/cell/panel/reset` and `ResetDeviceFault` cleared, so it
  looks closed by evidence. Out of this brief's scope; flagged rather than edited.
- Whether 4.11b should block the M3 gate. §6.2.2's latch is specified and
  unverified, and the only method that can verify it does not exist. My reading is
  that the gate's exit item (d) is satisfied by 4.11's reaction path plus the
  affirmative-form argument, and that 4.11b is an M3 debt to be discharged when
  the facility lands — but that is a gate call, not mine.

next_suggested: brief the bridge agent for §12 items 6 and 7 (hold-until-disarmed
fault injection, and rewrite-every-slot on server restart) — one is the only route
to 4.11b, the other is a named dependency of the reset guard's guarantee.
