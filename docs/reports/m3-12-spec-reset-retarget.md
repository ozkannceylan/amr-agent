brief:               docs/briefs/m3-12-spec-reset-retarget.md
status:              done
files_changed:
  - plc/demo-cell/SPEC.md   (§ Authority; §1; §3.1 heading, table, new polarity note;
                             §3.2 internal tags; §3.3 constants; §4.2; §4.3; §6.1;
                             §6.7 rewritten; §7 temp list + part 6; §9 groups 1 and 4;
                             §10 steps 7 and 9; §11 preconditions, T1, T2, T4; §12 open items)
invariants_touched:  none
open_questions:
  - "The bridge must carry the reset node and topic for any of §11's reset steps to run.
     A concurrent agent (m3-13) appears to be adding it — bridge/config/bridge.yaml in the
     working tree already has PanelResetPressed and /cell/panel/reset, uncommitted. I wrote
     the spec's dependency tense-neutrally ('confirm it before T1') rather than asserting
     the file's current state, since bridge/ is outside my write access and in flux."
  - "docs/interfaces/opcua-nodes.md §9.3's PanelResetPressed row still says the PLC 'forms
     the rising edge and times the hold'. The hold no longer exists in the program. The
     clause is not wrong about ownership, only stale about the mechanism; docs/interfaces/
     is not mine to edit. One phrase, next interface sweep."
  - "docs/interfaces/bridge-design.md's 'six nodes the bridge writes' is now seven in five
     places. m3-11 already logged this and it has a queued sweep; untouched here."
  - "plc/README.md needed no change: it references neither the reset nor a node count."
next_suggested:      bridge — add the reset contact to bridge.yaml and cell_stimulus.py, so §11's T1.1b and T2.7 are executable.

---

## Locations changed, found by independent search

m3-11's report named five. Searching the file for `\b14\b`, `six`, `three-button`,
`hold`, `gesture`, `falling`, `PanelStartPressed`, `StartEdgeMemory` and
`ResetDeviceFault` found **fourteen**, in eleven sections:

| # | Location | Change |
|---|---|---|
| 1 | Authority table | "The 14 nodes" → 15 |
| 2 | §1 | "three-button panel" → four-button, named; the reset bullet now says a different button |
| 3 | §3.1 heading | "exactly the 14 nodes" → 15 |
| 4 | §3.1 table | `PanelResetPressed` inserted as row 5 (node-model order), rows renumbered to 15 |
| 5 | §3.1, new | Row-order note + a block quote on fail state `FALSE` **at the point of use** |
| 6 | §3.2 | `ResetHoldTimer` and `ResetHoldValid` deleted; `ResetEdgeMemory` added; `StartEdgeMemory` and `ResetDeviceFault` redefined |
| 7 | §3.3 | `RESET_HOLD_MIN` / `RESET_HOLD_MAX` row deleted — no orphan constant remains |
| 8 | §4.2 | DB tag ranges 1–6 / 7 / 8–12 → 1–7 / 8 / 9–13 |
| 9 | §4.3 | `PanelResetPressed` added to the server-interface folder tree |
| 10 | §6.1 | "the six input values" → seven |
| 11 | §6.7 | Rewritten against the real contact (below) |
| 12 | §7 | Temp list `#startFall` → `#resetRise`; part 6 rewritten |
| 13 | §9 | Group 1 gains a `PanelResetPressed` row with its polarity; Group 4 gains `.ResetEdgeMemory` and a note on reading `ResetDeviceFault` |
| 14 | §10, §11, §12 | Step 7 "six inputs" → seven; step 9 "confirm 14 nodes … N must be 14" → 15; §11 precondition box, T1.1b, T1 pass count, T2.7/2.8, T4.3, T4.8, T4.9 rewritten + T4.9b, T4 pass count; §12 open item 1 closed and the list renumbered, new item 5 for the bridge |

The count reads **15 everywhere it is stated**: Authority, §3.1 heading, the
§3.1 table's last row, and §10 step 9 (both occurrences in that cell). The only
surviving `14` in the file is the row number of `BridgeHeartbeat`.

### Two "six" occurrences deliberately left

§8's case A ("the six inputs froze at their last written values") and case C
("refreshed all six inputs within ~200 ms") are quotations of the measured
2026-07-27 run against the test double, which had six inputs. Changing them would
falsify evidence (LESSONS: evidence is qualified by the environment that produced
it). Every *design* statement of the input count now reads seven.

## No gesture logic remains, and how that was checked

`grep -inE 'gesture|ResetHold|RESET_HOLD|startFall|falling edge|held long|hold [0-9]|hold time|three-button|conflat'`
over the whole file returns three hits, all of them prose that asserts the
mechanism's *absence*: §6.7's opening ("told apart by which contact closed and by
nothing else" — the word "gesture" is gone from it after a second pass), §6.7's
`CellResetRequired` justification, and §12's closure paragraph. Concretely:

- the hold timer (`ResetHoldTimer`) and its constants are deleted from §3.2 and §3.3;
- the "held long enough" latch (`ResetHoldValid`) is deleted, and with it the TON
  hazard that produced a LESSONS entry — nothing reads a `.ET` anywhere near the reset;
- the falling edge is deleted: `#startFall` is gone from the temp list and from
  part 6, and the reset acts on `#resetRise`;
- the watch table has no row for any deleted tag;
- no constant, no watch-table row and no test step mentions holding a button, and
  the one test that did (old T2.7, "press and hold start 1 s") is now a reset press.

## What survives, unweakened

- **Edge triggered.** `#resetRise` only. `ResetEdgeMemory` starts `TRUE`, so a
  contact closed at the first scan yields no edge ever; a reset held across a
  later stop cannot clear that stop's latch, because its edge preceded the latch.
- **Monitoring is now a device check, not a time window.** `ResetDeviceFault`
  survives with an inverted start value: it starts `TRUE` ("the contact has not
  been observed open") and clears permanently on the first `FALSE` sample taken
  while `BridgeLinkOk` is true. It costs no timer and no constant, replaces two
  statics with one, keeps the watch-table row, and turns a welded reset from a
  silent no-op into a visible one. It blocks only the reset — never start, which
  is a different device now.
- **The reset energizes nothing.** Its branch assigns latches and nothing else:
  no cycle flag, no step, no setpoint. Start is a separate rising edge on a
  separate contact.
- **Two deliberate actions cannot collapse into one.** `latchPending` is computed
  once, ahead of both branches, so a start edge in the *same* OB call as the
  clearing reset still sees the latch and is refused. §6.7 states this.
- **No auto-resume, per signal-loss case**, unchanged in §8.
- **Fail state `FALSE` documented at the point of use** — a block quote directly
  under the §3.1 table, plus the Group 1 watch-table row, both saying it is the
  opposite polarity to the two stop inputs and why (cut wire, welded-open contact
  or absent publisher all read "not reset").
- Nothing describes the reset as a safety function or safety-rated. §2's boundary
  statement is untouched.

## The `CellResetRequired` start gate: kept, with the reason written down

**Checked before deleting, and it must stay.** `RunPermissive` contains only
`ConveyorDriveFault`, `SensorFaultLatch` and `SequenceFaultLatch`; it does **not**
contain `ProcessStopLatch` or `LinkLostLatch`, whose live conditions clear as soon
as the button is released or the heartbeat returns. Drop `NOT latchPending` from
the start edge and releasing a process stop then pressing start would run the cell
with the stop still latched and no reset ever given — the automatic resume
CLAUDE.md §9 forbids. The gate was doing two jobs; only the button-separation job
was a consequence of the conflation. §6.7 now carries this argument under its own
heading, and states its agreement with `opcua-nodes.md` §9.5 (no *client* may
clear `CellResetRequired` by writing a node).

The parts that existed *only* to separate the two roles are the ones deleted: the
falling-edge clear, the hold window, and `ResetDeviceFault` blocking start.

## Verification status

**Unchanged and still none.** The status block at the top of the spec still says
no part of the document has been executed in TIA Portal or PLCSIM Advanced, and
that remains true: I cannot run either, nothing was compiled, and no PLCSIM run
exists. The reset logic added here is specification text. The only thing verified
about the reset anywhere is m3-10's live cell run showing the contact energizes
nothing, which is a `sim/` fact, not a PLC one. Nothing was committed.

---

## lessons_candidates

2026-07-27 | Retargeted a spec from a conflated device onto a real one and expected the deletions to be the whole job | One term of the deleted mechanism, `CellResetRequired` gating the start edge, was load-bearing for a second, independent reason (`ProcessStopLatch` and `LinkLostLatch` are absent from `RunPermissive`), and deleting it would have allowed a start after a released process stop with no reset | When removing a workaround, list what each of its terms does and re-derive each one from the new design; a term that survives for a different reason must be re-justified in place, not carried silently

2026-07-27 | Deleted a monitored-reset hold timer whose only job was gesture separation, and nearly deleted the device-fault bit with it | The stuck-contact diagnostic was worth keeping, but only if it cost no timer; expressing it as a Bool with start value TRUE ("not yet observed open"), cleared on the first observed open, kept the property with one static and no constant | A device-plausibility check does not need a timer if the plausible state is one the device must visit; encode "not yet proven" as the start value and clear it on the first proof
