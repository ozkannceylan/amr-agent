# Report m4f-01d — section 10 consistency after the HMI wave

```
brief:               docs/briefs/m4f-01d-section10-consistency.md
status:              done
files_changed:
  - docs/interfaces/opcua-nodes.md   (edited) §10.1 client-logic row amended;
                                     §10.1 timing-class row qualified (delta,
                                     reasoned below); §10.4 steer row given a
                                     forward pointer; §10.6 gained the steer
                                     range ownership statement
  - docs/reports/m4f-01d-section10-consistency.md   (new) this report
invariants_touched:  none — invariant 10 is applied, not changed
open_questions:      three, listed below
next_suggested:      Verifier on the m4f-01c/01d pair, then the two agent
                     definitions named in open question 1.
```

## Ruling 1 — what "no logic in either client" forbids

§10.1's row no longer reads "no timer". It now forbids what a client must never carry — **interlock,
latch, sequencing, setpoint formation, reaction to plant state, and any verdict the PLC also
computes** — and states that the line is not the word *timer*, because this model **requires three
client timers by name**: the bridge's 20 Hz cycle (`bridge-design.md` §5), the HMI's 10 Hz write cycle
with the 5 Hz floor it holds itself to (§10.8 H2), and the HMI's window over its operator's page
(§10.8 H6). What no client may time is a **process value** — a debounce, a fault delay, a dwell, a
stale window over a plant signal, "write only if stable for X ms" — because the threshold and the
delay are process decisions. The test is stated so it survives being read in a hurry: **what does the
timer watch — its own cycle or its own input channel, never the plant, and never a verdict the PLC also
computes.**

## Ruling 2 — who owns ±1.31

Read `hmi/config.yaml` first, as the brief instructed. It is already explicit from the other side: no
threshold, limit, scale, clamp, offset or debounce lives in that file, and it names the steer range as
an interface fact held in `hmi_server.py` as a named constant beside its citation *precisely so it
cannot be retuned as a deployment setting*. Nothing in the HMI's configuration had to be dislodged.

The ruling separates two questions that were being answered as one, and gives each exactly one answer:

| Question | Answer |
|---|---|
| Who owns the **value**? | The plant. It is the `steer_joint` mechanical stop in `agv/forklift/model.sdf`, surfaced by the vehicle layer as `steer_limit_rad` (`agv/forklift/config.yaml`). A mechanical fact, not a process decision — which is what makes it unlike `TRACTION_SPEED_MAX`, a process cap the PLC owns (§10.12 item 4) |
| Who is **authoritative over what the plant is commanded**? | The PLC's clamp in §10.6. `ForkliftSteerAngleRef` is formed from `HmiSteerRequest` clamped inside the PLC, and nothing reaches the plant except through that assignment. One enforcement point in the command path; the HMI has none, and no client has one |

The chain already agreed and nothing had to be corrected: `plc/forklift/SPEC.md` §3.3's
`STEER_ANGLE_MAX` cites `agv/forklift/config.yaml` as its source, and the vehicle layer's own README
names `model.sdf` as authoritative where its two files could disagree.

**The HMI's copy is scaling, not authority, and the document now says so plainly.** It converts a
dimensionless joystick position into the rad the node declares — it decides what the operator's stick
*means*, never what the machine does — and **it cannot apply a value the PLC would not**: set too large
it does not widen the machine's travel, because a request between `1.31` and `1.35` is clamped by the
PLC and one past `1.35` leaves §10.4's plausibility window and is read as a broken client rather than a
demand; set too small it only means the operator cannot reach full lock. The plant's own joint limit
clamps too, and that is a last-ditch mechanical stop in another layer rather than a second authority —
the same reading §10.12 item 4 already gives the vehicle layer's traction clamp.

Two consequences are written out. **Every derived copy names §10.6 as its source**, and nobody
re-derives the number from anything — each copy restates the published value and cites where it comes
from, which is what keeps one owner under invariant 10. **A test double or a harness may hold its own
copy**, and two do (`plc/forklift/double/logic.py`, `hmi/tools/check_hmi_writes.py`): an instrument
that imported the value it is checking would check nothing.

`hmi_server.py` cites **§10.4**, not §10.6, so §10.4's steer row now carries a forward pointer to the
ruling. The existing citation therefore lands on it in one hop and **no HMI code change is required** —
no request against `hmi/` was manufactured for this.

## Sweep

Subject sweep over *timer*, *timers*, *no timer*, *steer range*, *steer_limit*, `STEER_ANGLE_MAX`,
`STEER_REQUEST_MAX_RAD` and the value `1.31`, whitespace-normalised across the repository, each hit
read for dependency rather than counted (LESSONS 2026-07-29). Verdicts:

| Statement | Verdict |
|---|---|
| §10.1 **timing class** row: "every timing decision that matters — the stale windows…— is a PLC timer" | **The one real contradiction.** H6's window *is* a stale window, one row below the row I was sent to fix. **Amended** — it now reads "every timing decision the cell's behaviour depends on", names the **two link** stale windows, and states that a client's own cadence and input-channel window are best effort with no plant behaviour resting on them. This is a delta beyond the deliverable's literal wording, taken because leaving it would have reinstated the same defect one row down; invariant 9's force is preserved, not weakened |
| §9.1 "no sequencing, interlocks, timers, latching or debounce **that changes meaning**" | Consistent — the qualifier governs the list, and the bridge's cycle changes no meaning. Left |
| §9.7 and `bridge-design.md` §7.2, "No timer, threshold or reaction exists in the bridge" | Consistent **in context**: both sentences follow one naming the staleness triple, and "it" is that machinery. Read out of context the phrasing is flat. Left — outside this deliverable; see open question 2 |
| `bridge-design.md` §2 config row, "no thresholds, no limits, no tolerances, no timers" | **Supports the ruling** — it is about config *keys*, and the same row admits `cycle period` |
| §9.3 `PanelResetPressed` "no hold time, no timer"; `bridge-design.md` row 5 | Consistent — process-value timers, exactly what the amended row forbids |
| §9.8 / §10.11 "Timers, step numbers, latch state… exposed for a client" | Different subject: exposing PLC timers as nodes |
| `handshake-tables.md` "must not mark a node reached from pose or timers" | Different subject: fleet-side inference |
| `1.31` in `agv/forklift/{model.sdf, config.yaml, README.md}`, `plc/forklift/SPEC.md` §3.3, `plc/forklift/double/logic.py`, `hmi/hmi_server.py`, `hmi/tools/check_hmi_writes.py` | All consistent with the ruling as written; the two instrument copies are covered explicitly |
| `docs/briefs/m4f-01`'s `HmiSteerCommand … −1.31…1.31` | A brief, superseded by the `HmiSteerRequest` naming decision. Not a contract, no action |

## Open questions

1. **Two agent definitions now under-describe the contract, and one of them directs the layer that must
   implement H6.** `.claude/agents/hmi.md` hard rules read "No interlock, latch, **timer**, sequencing
   or actuator output here", and `.claude/agents/bridge.md` reads "No thresholds, latches, **timers**,
   sequencing or interlocks" — both flat, in the exact phrasing §10.1 has just stopped using. An HMI
   agent briefed to implement H6 would read its own hard rules as forbidding it. `.claude/` is in no
   roster agent's write scope, so this is the orchestrator's to fix.
2. **§9.7 and `bridge-design.md` §7.2 share a sentence that reads flat out of context.** Judged
   consistent and left unedited because both sit outside this brief's deliverable. A one-clause
   qualification ("no timer over the heartbeat, no threshold and no reaction…") would remove the flat
   reading if the owner wants the sweep to come back clean on the string as well as on the meaning.
3. **ADRs 0004, 0005 and 0007 each restate "no timers" for the bridge.** Accepted ADRs are never edited
   (CLAUDE.md §8) and the binding statement is `bridge-design.md` §1.1, which is precise ("any timer
   that **gates a signal**"). Recorded so the discrepancy is not rediscovered as a defect; no action
   available or needed.
