# Report m3-37 — M3 gate verification

brief:               docs/briefs/m3-37-gate-verification.md
status:              done
files_changed:       docs/reports/m3-37-gate-verification.md (this file only) — not committed
invariants_touched:  none
open_questions:      findings 1, 2 and 9 name readings that are owed; none blocks M3
next_suggested:      advisory only — the orchestrator writes the roadmap sentence of §6, then opens M4

---

## VERDICT: **pass-with-findings**

M3's four exit criteria, **as written in docs/roadmap.md**, are all met. Twelve
findings are recorded below; none of them unmeets an exit item, and three of them
(1, 2, 9) name readings that belong at the head of M4's owner queue because M4
performs CPU restarts anyway.

The gate does **not** close on `plc/demo-cell/SPEC.md` §11's step list, and it was
not asked to. §11 T4 is **not** a 14/14 pass and no document claims it is.

---

## 1. The two questions kept separate

The brief's central instruction, discharged explicitly.

**The roadmap criterion** is four properties of the cell: (a) Gazebo sensor state
visible as PLC input bits in a TIA watch table, (b) PLC output bits driving the
Gazebo actuator, verified visually, (c) latency and update rate measured and
written down, (d) signal-loss behaviour defined and tested.

**§11 is a procedure** someone chose for demonstrating those four. It is stricter
than the criterion in three places that matter here:

| §11 asks for | The criterion asks for | Consequence |
|---|---|---|
| T1: all seven Group 1 rows, six steps, screenshots | (a) "sensor state visible as PLC input bits in a TIA watch table" | one input in a watch table satisfies the criterion; six of seven missing is a §11 shortfall (finding 1) |
| T2: Group 2 `ConveyorSpeedCommand` in the watch table, eight steps | (b) "verified **visually**" — the watch table is not named | Group 2's zero watch-table coverage is a §11 shortfall, **not** an unmet exit item (finding 2) |
| T4: fourteen steps, four of which never ran | (d) "defined and tested" | four never-run steps do not unmeet (d) (findings 8, 9, 10) |

And §11 is **weaker** than the criterion nowhere. So: **a never-run §11 step does
not automatically unmeet an exit item, and a passed §11 step does not automatically
meet one.** Item (a) is the one place where the criterion itself names the
instrument, which is why the captures had to be opened rather than counted.

---

## 2. Per-item rulings

### (a) Gazebo sensor state visible as PLC input bits in a TIA watch table — **MET**

**Establishing artifact: `plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 135105.png`.**
Opened and read pixel by pixel. A running **Gazebo Sim** window (entity tree:
Conveyor, ProductBox, ProductSensor, SensorReflector, OperatorPanel; the cell
rendered; RTF 99.61 %) sits beside a TIA Portal *Watch table_1* in Monitor mode on
`PLC_1 [CPU 1513-1 PN]`, CPU in **RUN**, monitoring
`"DemoCellInput".ProductSensorRange` = **1.440088**. One frame, both ends of the
loop, the cell's own beam-clear value standing in the PLC's process image.

**The provenance of that value is proved by a second pair, not assumed.**
`Screenshot 2026-07-28 171656.png` (CPU RUN, bridge down since 17:14:07) shows the
same **1.440088** still standing, and `Screenshot 2026-07-28 171727.png` — the same
16-row table after a CPU STOP → RUN — shows the same tag at **0.0**, the DB start
value of SPEC §3.1. A value that reverts to 0.0 on reinitialisation and reads
1.440088 with the CPU running can only have been written from the cell. Together
these three captures are a watch-table reading of Gazebo sensor state as a PLC
input, with its provenance closed.

Corroborating watch-table captures of the same tag at the same value, all opened:
`170920.png` (with `BridgeLinkOk` **TRUE**, i.e. link live), `173247.png`,
`173615.png`, `140737.png`, `142838.png`, `143014.png`, `140306.png`.

**What is established off the watch table, for all seven inputs**, and is not the
instrument the criterion names but is the substance behind it:
`EVIDENCE_LATENCY.md` §B2.4 (count/min/median/p95/max for each of the seven),
§B2.6 (`sessionB`'s R3 ladder, the withheld list shrinking one input per publish
over 20.84 s), and §B3.1 4.8 — the seven written one at a time at 4.25 s spacing
with the first heartbeat **158 µs** after the seventh write.

**Ruling: met.** The criterion's words are satisfied by a committed capture whose
content I verified. Finding 1 records the shortfall against §11 T1.

### (b) PLC output bits drive the Gazebo actuator, verified visually — **MET**

**Establishing artifact: `assets/plc-drives-cell.gif`, committed, and verified by
me rather than accepted.** Reopened with Pillow: **820×471, 406 frames**, matching
`docs/reports/m3-26-live-loop-run.md` exactly. Frames 120 and 150 were extracted
and viewed: the conveyor slab and the product box are in **visibly different
positions**, the Gazebo RTF readout differs (89.98 % vs 91.21 %), and the scene is
the demonstration cell (belt, product box, two sensor posts, panel pedestal). The
actuator moves, on a recorded artifact, not in prose.

**The causal chain from PLC output to that motion is closed by three independent
readings**, so "the belt moved" is attributable to the program and not to anything
else:

1. `EVIDENCE_LATENCY.md` §B2.5 — six `PanelStartPressed` writes answered by
   `ConveyorSpeedCommand` `0.0 → ±0.150`, L7 median 46.163 ms;
2. §B2.6a — one full clean cycle traced as position: **0.0414 m → 1.3743 m →
   0.0393 m**, forward stroke 8.899 s, dwell 2.050 s, return 8.899 s, and L6
   `cmd_speed → belt velocity ≥ 50 %` at 2–4 ms on seven command changes (§B2.4);
3. `Screenshot 2026-07-27 212116.png`, opened: the `DemoCell` server interface
   with `Output/ConveyorSpeedCommand` at access level **RD** while the seven
   `Input/` nodes are RD/WR. **No OPC UA client can write that node.** The belt
   could only have been commanded by the program — which is also invariant 6 read
   off the tool rather than asserted.

**Ruling: met.** (b) names a visual verification and does not name the watch table;
the visual verification exists and reproduces. Finding 2 records that SPEC §9
Group 2 has zero watch-table coverage, and finding 3 records that the recording is
build A.

### (c) Latency and update rate measured and written down — **MET**

Measured three times on three servers, each qualified by its environment
(LESSONS 2026-07-27): Section A (test double, container), Section B part 1 (PLCSIM,
m3-05 build, four sessions / 502 s), Section B part 2 (PLCSIM, build F, one session
/ 712.255 s).

The last measured set, §B2.3 and §B2.4:

* **14 244 cycles at 20.00 Hz**, period 40.095 / 50.003 / 50.978 / 61.394 ms,
  **one** overrun, sized (3.93 ms past deadline), 0 read errors, 0 write errors,
  0 reconnects;
* count / min / median / p95 / max for **all seven inputs** on L1, L2, L3, plus L5,
  L6, L7, R1, R2 and the OPC UA read round trip. Never a bare mean;
* L7 = the closed loop, **count 6, min 45.447, median 46.163, max 47.690 ms**,
  stated as an **upper bound** because it contains the bridge's own 0–50 ms poll
  phase — the caveat is in the document, not left to a reader;
* the three ~5.0 s L1 maxima are correctly identified as signal-loss case D
  measured by accident, with the arithmetic (freeze 4.981 s vs L1 max 4 998.110 ms)
  shown;
* **CPU cycle time 1.004 / 1.023 / 2.556 ms** — `Screenshot 2026-07-28 174127.png`,
  opened and read: *Shortest 1.004 ms, Current/last 1.023 ms, Longest 2.556 ms*,
  axis 1.023 → 150. §B2.9's two limits on over-reading it (the panel does not name
  the OB30 period; the 150 is an unlabelled axis limit) are both correct;
* environment and network path: TIA V21, PLCSIM Advanced V7.0, CPU 1513-1 PN
  FW V3.1, `opc.tcp://192.168.53.1:4840`, and **invariant 8 held by routing table**
  (§B.9: `Get-NetRoute` shows the only route to 192.168.53.0/24 is on-link on
  Ethernet 2; Tailscale carries none and holds an APIPA address). The host adapter
  configuration is independently visible in `Screenshot 2026-07-27 205945.png`
  (192.168.53.241/24).

**Ruling: met.** Finding 4 records that build G carries no statistics set.

### (d) Signal-loss behaviour defined and tested — **MET**

**Defined:** `plc/demo-cell/SPEC.md` §8, four cases, each with the PLC's view and
the equipment's reaction.

**Tested against a CPU running a program**, `EVIDENCE_SIGNAL_LOSS.md`'s PLCSIM
repeat, with both halves of the criterion answered separately:

*What the PLC sees when the bridge stops* — case A (`kill -9`): heartbeat freezes,
`BridgeLinkOk → False` in **0.50 s** (run 1) / **0.60 s** (run 2); case B
(`SIGTERM`): identical at the program, the only difference being at the session
layer (20.10 s vs ≤ 0.2 s of session hold), which the program neither sees nor
should. `HEARTBEAT_STALE_TIME` = 500 ms confirmed three times independently, so
SPEC §12 open item 1 closes at 500 ms on measurement.

*What the equipment does* — cycle drops, `ConveyorSpeedCommand → 0.0`,
`CellResetRequired` latches, and **no auto-resume**: tested three times in run 1
(+36.0 / +39.0 / +8.9 s of stillness), again in run 2 (36.97 s), and again on
build G (§B3.1 4.2: the diagnostics dictionary byte-identical for **38.140 s**, and
the CSV showing **no** panel write for 38.251 s). Recovery always takes two
deliberate actions on two different buttons (§B3.1 4.3, in full).

*The two hard cases, both now covered:*

* **case C, server restart under a surviving session** — the program was correct
  and the **bridge** was defective (F5: 4 min 31.1 s of a stale image). Fixed and
  measured on build G: restart detected, **7 of 7** slots rewritten, **10 ms** on
  the log's clock / **9.704 ms** on the CSV's, inside one 50.789 ms cycle, on slots
  whose last ROS-side change was up to 177.473 s earlier. The corrected signature
  holds: `CellProcessStopActive` **FALSE** in all 1 196 observer rows and every
  1 Hz poll, while `CellResetRequired` still latched. §B2.7c is the only Group 4
  reading of a restart and I verified both captures against it (§3 below).
* **case D mid-motion** — the one the heartbeat cannot see. Was a failure on the
  m3-05 build (26.3 s undetected, F2); after m3-29's re-arm it is **2.301 s**,
  inside the specified [2.1 s, 3.2 s], derived from named CSV rows and corroborated
  by the 5 Hz observer (2.207 s) and the 1 Hz bracket. D (i) at rest fires on D1
  one `DRIVE_FAULT_DELAY` after the setpoint goes non-zero. Reset refused for
  **35.0 s** while the dead cell still claims motion, honoured after the revive —
  the inverted T4.7, passed.
* **a reset held from before link-up** was refused for **28.202 s** across a
  link-up on build G, and only a fresh rising edge cleared the latches — the
  reversal of F3, on a reading.

**Ruling: met.** Findings 8, 9 and 10 name the four §11 T4 steps that never ran.

---

## 3. The owner captures as instruments — verified, not counted

The only Group 4 instrument in this gate is the watch-table set. I opened
**21 of the 23 captures dated 2026-07-28** and a sample of the 2026-07-27 set, and
checked every claim the evidence makes off a capture. **Every content claim holds.**

`171656` / `171712` / `171727` against §B2.7c's table — all three are the same
16-row table, and every changing cell matches:

| Tag | 171656 (RUN, before) | 171712 (STOP) | 171727 (RUN, after) |
|---|---|---|---|
| `ProductSensorRange` | 1.440088 ✓ | 1.440088 ✓ | **0.0** ✓ |
| `PresenceOnTimer.PT` | T#100MS ✓ | T#100MS ✓ | **T#0MS** ✓ |
| `BridgeLinkOk` | FALSE ✓ | FALSE ✓ | FALSE ✓ |
| `ProcessStopLatch` | FALSE ✓ | FALSE ✓ | **TRUE** ✓ |
| `LinkLostLatch` | TRUE ✓ | TRUE ✓ | TRUE ✓ |
| `SensorFaultLatch` | FALSE ✓ | FALSE ✓ | **TRUE** ✓ |
| `PositionRef` | 0.1995 ✓ | 0.1995 ✓ | **0.0** ✓ |
| `SeqStep` / `ResetDeviceFault` / `PositionFrozen` | 0 / FALSE / FALSE ✓ | ✓ | ✓ |
| CPU operator panel | RUN/STOP **green** ✓ | **yellow** ✓ | **green** ✓ |

`173247` and `173615` against §B2.13 F4's table — `BeltFeedbackFaultLatch` FALSE in
both, `BridgeLinkOk` TRUE in both, `SeqStep` 0 in both, and the three-latch
difference (all FALSE at 17:32:47, all **TRUE** at 17:36:15) is exactly as stated,
including F4's own honest observation that three latches already stood 35 s before
the second press. `174127` reads as quoted, digit for digit.

**No capture was accepted on its filename timestamp.** §B2.0's rule — a filename is
a candidate for an event, never coverage of it — is the right rule and the evidence
applies it consistently: §B2.7a's admission that no capture covers the T4.6
re-measure, and §B3.5's that **no** watch table was taken during part 3 at all, are
both true against the directory.

Two things the captures settle that nothing else does, and that I found rather than
read: the read-only access level on `ConveyorSpeedCommand` (`212116`, cited under
(b) above), and the build-content contradiction of finding 5.

---

## 4. The build history — assembled across builds, and legitimately

The four items are **not** established against a single coherent build. Item (a) is
read on build C/D-era captures; (b)'s visual record is build A and its measured
traces are builds F and G; (c) is build F; (d) is spread over builds A, C, F and G.

**That assembly is legitimate for this criterion**, for reasons that are properties
of the record and not of my goodwill:

1. The criterion asks that four independent properties be *demonstrated and
   recorded*. It does not ask for one run, and a four-property criterion assembled
   from labelled runs is not the same thing as a pass count assembled from
   different denominators — which is the abuse SPEC §11 rules 1–3 exist to prevent,
   and which the evidence does not commit.
2. **Every figure names its build** (§B2.9's table, §B3.0's build G) and no figure
   was amended when a later build changed behaviour. Parts 1, 2 and 3 each state
   "no figure of the earlier part is altered by this section", and the diffs bear
   that out (m3-36's report records +497 / −0 on the additive section).
3. Where a build change **invalidated** an earlier result, the record says so and
   re-ran rather than reasoning across the boundary: §6.8's *which recorded results
   survive*, §B2.12a's refusal to reconcile build C's cold-start readings to the
   corrected expectation, §B2.12 row 17, and part 3 re-running all five affected
   steps. That is the discipline the assembly needs, and it is present.
4. The one attribution that does cross a boundary by arithmetic — §B3.1 4.5's
   claim that the boot-polarity fix is doing work alongside the bridge's rewrite —
   is **labelled as an inference over a window no instrument sampled**, and the
   direct reading that would settle it is named (finding 9).

What no single build carries is the whole loop at once. M4's criterion already
requires a **recorded** cell + safety showcase, which will produce that on one
build as a by-product; it does not need to be manufactured for M3.

---

## 5. The three items ruled on by name

### T4.11's reaction re-record (§B2.12 row 15) — **does not block closure**

Belt-feedback plausibility is a defence added **during** this gate (m3-27, from
m3-25's finding), and it appears nowhere in the roadmap's four-item text. It is not
a sensor-to-input-bit question (a), not an output-to-actuator question (b), not
latency (c), and not signal loss (d) — signal loss is the loss of the link or of
the simulator, not an implausible-but-delivered sample. The reaction path was
demonstrated (transcript, twice), the instrument the step now nominates exists and
is proven in force (§B3.0's per-session CSVs), and the row is carried with a named
owner. **Not a blocker.** Findings 6 and 11 record what is untidy about it.

### T4.11b (§B2.12 row 16) — **does not block closure**

Same scope argument, plus: it is blocked on a facility that **does not exist** —
SPEC §12 item 6's hold-until-disarmed fault injection. A gate cannot be held open
by a step whose instrument has not been built, and the correct handling of such a
step is exactly what the record does: state that §6.2.2's latch is *specified and
unverified*, refuse to infer it from 4.11, and request the facility of `bridge/`.
The measured proof that the narrowed-constant method **cannot** reach the latch
(the plant recovers in ~100–150 ms, under a 200 ms delay) is in the document rather
than argued away. **Not a blocker.**

### 4.9b's partial status — **does not unmeet (d)**

4.9b is a monitored-reset property, and a monitored reset is squarely inside (d)'s
"what the equipment does". So the question is real. It resolves on **which form**
was run.

* Form **(a)**, fresh bridge with the reset held: **passed on build G**, on a
  reading — refused for 28.202 s across the link-up, cleared only by an edge that
  began after link-up, against build C's 0.655 s unbidden clear. This is *the*
  bridge-stop form, and (d)'s sentence is "what the PLC sees when the **bridge**
  stops, and what the equipment does".
* Form **(b)**, CPU start with the reset held: **did not run**. It is a CPU-restart
  property, not a bridge-stop one.

So the form that (d) actually names ran and passed, and the form that did not run
tests a boundary (d) does not name. **§11 4.9b is correctly *not* a pass as a step**
— §B3.4 row 14 says exactly that and does not round it up — and (d) is met without
it. Finding 9 carries form (b) forward with the cold-start reading it shares.

---

## 6. The sentence docs/roadmap.md should carry

Stated, not written — the orchestrator writes it.

> **Add to the closed-gate list, after the M2 line:**
> `M3 closed 2026-07-28, verified in docs/reports/m3-37-gate-verification.md (pass-with-findings).`
>
> **And change line 3 from** `Current gate: M3 — in progress.` **to**
> `Current gate: M4 — Safety layer on the fixed cell (F-CPU).`

Nothing else in roadmap.md changes; the M3 row text stays as written, because it is
the criterion that was ruled against.

---

## 7. Findings

**1. Six of the seven Group 1 inputs have no watch-table capture, and no capture
shows any input changing.** The only `DemoCellInput` tag monitored anywhere in the
70 committed captures is `ProductSensorRange`. `ConveyorBeltPosition`,
`ConveyorBeltSpeed`, `PanelStartPressed`, `PanelResetPressed`,
`PanelStopCircuitClosed` and `PanelProcessStopCircuitClosed` appear in **no**
watch table. §11 T1's pass line asks for the seven and for screenshots of the belt
moving (1.5); that was never taken. Item (a) is met on `135105` + the
`171656`/`171727` provenance pair, but the §11 procedure behind it is unsatisfied.
*One capture at M4 — the §9 Group 1 table with the cell running — closes this and
finding 2 together.*

**2. SPEC §9 Group 2 has zero watch-table coverage.**
`"DemoCellOutput".ConveyorSpeedCommand` appears in no committed capture. Item (b)
is met because the criterion says "verified visually" and does not name the watch
table — but every reading of the output in this gate is an OPC UA read, and the
§11 T2 instrument was never used. Same one-capture fix.

**3. There is no committed per-step T1 or T2 roster, and the pass counts that
circulate for them are in a tracking file only.** `docs/TODO.md` line 29 carries
"T1 6/6 rerun with the real 100 ms filter; T2 8/8". SPEC §11 rule 3 names the as-run
record as `EVIDENCE_LATENCY.md` §B.7 / §B.12 / §B.13, and parts 2 and 3 carry a
**T4** roster only — there is no T1 or T2 step table with a verdict and a build
anywhere in the evidence, and §B2.0's LIMITATION 1 states that the T1.4 re-run is
transcript-only with no committed artifact. This is LESSONS 2026-07-27 row 53
(quote counts only as the instrument produces them) recurring in a tracking file.
The *substance* of T2 is evidenced (§B2.6a's full cycle, §B3.1 4.3's full cycle);
the **counts** are not derived anywhere.

**4. Build G carries no cycle-rate or statistics set,** because both processes were
killed and no counter block was flushed (§B3.0). §B2.3/§B2.4 — build F — are the
last measured set, and the bridge's code changed after them (`c1dd3d0`: reconnect
on in-flight failure, restart detection, per-session CSVs). Item (c) is met
regardless; the note is that the committed statistics predate the shipped bridge by
one commit. §B3.2 measures the new path's own cost (repair inside one cycle, one
0.906 ms overrun), which is the part that matters.

**5. §B2.9's build table mis-attributes two of its three "build B" deltas, and the
captures prove it.** §B2.9 records build B (~13:00, transcript) as "the three-delta
build: the released dwell timer, the belt plausibility window, the re-armed case-D
window". Three committed captures contradict the last two:

* `Screenshot 2026-07-28 140451.png` — the complete Static block at 14:04:51 — has
  no `BeltFeedbackInvalidTimer` (m3-27) and no `PositionFrozen` (m3-29);
* `Screenshot 2026-07-28 141719.png` — the complete Constant block at 14:17:19,
  header to `<Add new>`, sixteen entries — has no `BELT_POSITION_MIN`/`MAX`, no
  `BELT_SPEED_MIN`/`MAX`, no `BELT_FAULT_DELAY` and no `POSITION_WINDOW_TIME`
  against SPEC §3.3's twenty-two;
* `Screenshot 2026-07-27 222908.png` confirms the same six absences on build A.

So those two deltas can only have entered with **build C (~14:38)** or later. They
were demonstrably in force by 17:16 (`BeltFeedbackFaultLatch` and `PositionFrozen`
are rows of `171656`). **No figure moves**: §B2.9 attributes nothing to build B, and
everything in the 15:01–17:14 window is already labelled build C. The correction is
to the B/C split of a transcript-sourced table. `plc/`'s or `bridge/`'s to make,
one line.

**6. `BeltFeedbackInvalidTimer`'s absence at 14:04 sharpens F4's unresolved
timestamp inconsistency rather than resolving it.** F4 already records that the
first ±0.10 press (17:30:45) predates the narrowed-constant download (~17:35) on the
transcript's own timestamps, and leaves it standing. Finding 5 shows the belt
constants did not exist at 14:17 either, so the whole ±0.10 episode sits inside a
window whose build boundaries are transcript-only. F4's disposition — the
measurement has no committed artifact, re-run on a per-session CSV with the build
recorded — is the right one and is unchanged.

**7. `ResetEdgeMemory` is declared as `ResetEdgeMemory_1` in the built program.**
`Screenshot 2026-07-27 222908.png`, the Static block. SPEC §3.2 and §9 Group 4 both
name `.ResetEdgeMemory`, so the §9 watch-table row cannot be entered as the
document writes it. No later capture shows the tag, so I cannot say whether it was
renamed. Cosmetic, but it is a spec-to-program diff on a document whose whole point
is diffability. `plc/`'s to check at the next download.

**8. Four §11 T4 steps have never been executed**, and the record says so in every
place it should: **4.8's cold-start half** (§B3.1, §B3.4 row 17), **4.9b variant
(b)** (§B3.4 row 14), **case C as an adapter break under a running program**
(§B3.4 row 19), and **4.11b** (blocked, row 16). Two further steps are partial on
Group 4 conditions no instrument in their run could see (4.2, 4.5). §11's
"Pass: all fourteen steps" is therefore not achieved and is not claimed. This does
not unmeet (d) — see §5 — but it does mean **M3 closes with §11 T4 open**, and the
orchestrator should carry that forward rather than let the closure imply otherwise.

**9. The single highest-value missing reading is one watch-table capture at a CPU
cold start with the bridge down.** §B3.5 item 4 says so and I agree, on the
evidence: it is the only direct test of §6.8's boot polarity (§B3.0's pre-run
`ProcessStopLatch FALSE` was taken *after* a link session and so does not
discriminate build G from build C, as §B3.0 itself says), it is the "after" of
§B2.12a's cheapest available before/after test, and it carries 4.8's cold-start
half and 4.9b variant (b) with it. M4 cold-starts the CPU by necessity. **Put it
first in M4's owner queue.**

**10. Two residuals are correctly recorded as limits and not defects, and neither
touches an invariant.** While the bridge is down or the CPU is in STOP the belt
keeps running in Gazebo, because gz's `JointController` holds the last velocity and
the simulated cell has no wired enable (§A.7, §B3.3). Invariants 1 and 2 are intact:
no safety function is claimed anywhere in this gate, and loss of the link is handled
as a degraded mode with a controlled stop and a monitored reset. §B3.3 additionally
declines to read the observer's silence on `BridgeLinkOk` as evidence the link held,
and bounds the unsampled window instead — which is the correct treatment.

**11. Tracking coherence: PLAN.md contradicts itself in three places and TODO.md
carries two closed items.** This is LESSONS 2026-07-27 row 44 recurring, and it is
the same check m3-23 failed the gate on.

* `docs/PLAN.md` item 32 records m3-35 as "Issued" and item 34 records the same
  brief as "Closed 2026-07-28" — duplicate entries, contradictory status.
* `docs/PLAN.md` line 116 and line 128 record m3-36 as issued / "in flight", though
  `docs/reports/m3-36-rebuild-rerun-evidence.md` is written, `status: done`, and
  committed (`0724359`), and PLAN lines 118–125 already summarise its content.
* `docs/PLAN.md` lines 149–155 ("Remaining before the gate can close: the owner's
  OB30 program build … and the PLCSIM run") contradict PLAN's own lines 136–139 and
  118–125. Stale paragraph.
* `docs/TODO.md` line 38 still lists m3-35 as "(issued)" — closed; §11 says closed
  items are deleted. Its rider (reconcile §B2.12 rows 20–21) is also satisfied by
  §B3.4.
* `docs/TODO.md` line 20 (the infra item on `.gitattributes`' stale shebang count)
  was resolved by `952781b`, which replaced the count with a rule. Delete.
* PLAN's item numbering is broken (24 appears after 29; 32 and 34 duplicate).

`docs/roadmap.md` itself is **clean and not closed in advance** ("Current gate: M3
— in progress"), and PLAN correctly does **not** carry the m3-36 brief's wrong
"build E" letter, so §B3.5 item 3 needs no action.

**12. PLAN and the public README over-claim in four places; the evidence documents
do not.** Recorded because repository content is in scope.

* PLAN line 118: "all five re-runs passed against it" and 4.9b presented as a pass.
  §B3.1 grades them **PASS on its R3 half / PASS on its server-visible half / PASS
  in full / PASS / PASS on its server-visible half**, and §B3.4 row 14 states that
  §11 4.9b "is **not yet a pass**" as a step. PLAN drops the qualifications.
* `README.md` line 8: the GIF is captioned as the belt driven "through the four M3
  exit scenarios T1–T4". It is the m3-26 run of 2026-07-27 on build A — the run in
  which T1.4 failed, T2.2–2.4 were never reached, case D went 26.3 s undetected, and
  4.5 / 4.8 / 4.9b / 4.11 did not exist or did not run. The m3-26 report's own
  segment table calls segment 7 "the defect, on screen".
* `README.md` line 81: `171656.png` is captioned "live cell input values". The
  bridge had been down for 2 min 49 s and `BridgeLinkOk` reads **FALSE** in the same
  image; the 1.440088 is case A's frozen image. The value's *provenance* is Gazebo —
  which is why item (a) rests on it — but it is not live.
* `README.md` line 96 cites §B.6 for the closed loop; L7 is §B.5 (§B.6 is the
  startup rule).

**Not a finding, recorded as verified clean:** git author fields are the owner's on
every commit and no commit message, branch name or PR body mentions AI assistance or
tooling; the five layer READMEs all carry their "This layer must not access" section
and every file changed in this gate sits inside its own agent's directory; the
332 MB raw rerun CSV is gitignored with only its `.gz` committed; and the
publication redaction (`952781b`) **damaged no evidence chain** — the capture it
deleted (`144116.png`) is cited by content nowhere, though §B2.0's "71 files, 24 of
them from 2026-07-28" is now stale at 70 / 23 and the redaction is HEAD-only, so
both that blob and the `m4-00` infrastructure inventory survive in history at
`49a3800` and `58718d2`. `docs/TODO.md`'s publication section still presents
BLOCKER 2 (no LICENSE — `LICENSE` now exists) and BLOCKER 3 as open. Publication is
not gate work; the tracking inaccuracy is noted for the pub queue.
