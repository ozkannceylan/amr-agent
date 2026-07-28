# Report m3-28 — independent review of T1-T4 as specified versus as run

brief:               docs/briefs/m3-28-t-scenario-review.md
status:              done
files_changed:       [docs/reports/m3-28-t-scenario-review.md]  (this report only; nothing else touched, nothing committed)
invariants_touched:  none
open_questions:
  - Which SPEC revision the program in RUN during m3-26 was built to is not
    recorded anywhere (finding 2). It does not change either root cause, but
    the owner should state it when fixing F1/F2 so the rebuild baseline is known.
next_suggested:      One plc brief revising SPEC.md §6.6/§7 part 3 (F2, finding 4) and one owner TIA session with the §9 watch table open on the presence group (F1, finding 3); F1 needs no document change first.

**Overall verdict: pass-with-findings** on the scenario chain and the evidence;
**fail** recorded against two specific artifacts: SPEC.md §6.6/§7 part 3 +
§8-case-D + §11 T4.6 (a spec defect, agent-fixable — F2) and the presence
network of the program as built in TIA (a program defect, owner-fixable — F1).

Method note. Every figure below was re-derived from the committed CSVs
(`bridge/evidence/*plcsim*.csv.gz`, commit `cc43369`), not quoted from prose.
The observer CSV (`plc-observe-2026-07-27-plcsim-main.csv.gz`, 3 907 rows,
394.0 s, 10 Hz) is the ground truth for what the server published; the four
`latency-*` session CSVs are the ground truth for what the bridge did. All
observer times below are `t_mono_s` of that file.

---

## Finding 1 — T1-T4 as specified. Verdict: **pass-with-findings**

Coverage of the four M3 exit criteria (roadmap.md M3 row) is intact after
m3-25 and m3-27: T1→(a), T2→(b), T3→(c), T4→(d), and m3-27's new fault path
(C5) got its own step, T4.11, with a correct warning to narrow the *speed*
constant, not the position constant. The m3-25 dwell-timer form and the m3-27
C5 addition are internally consistent with T2 and T4 as revised.

**One internal contradiction, and it is F2 wearing its specification hat.**
§11 T4.6 requires, *"with the belt transporting"*, that `ConveyorDriveFault`
latches within `DRIVE_FAULT_DELAY`. The §6.6/§7 logic cannot deliver that:

- D1 requires `ABS(ConveyorBeltSpeed) ≤ SPEED_TOLERANCE` (0.02 m/s), but a
  mid-transport freeze holds the last real sample, ≈0.15 m/s. D1 is blind by
  construction — §8's own case D row concedes this in its D1 cell.
- D2 requires `ABS(ConveyorBeltPosition − PositionRef) < POSITION_FREEZE_BAND`
  (0.005 m), but §7 part 3 arms `PositionRef` once, at the start of motion,
  and never again while motion continues (see finding 4). At `TRANSPORT_SPEED`
  the comparison is satisfiable only if the freeze lands within
  0.005/0.15 ≈ **33 ms** of motion start.

§8's case D row deepens the contradiction: it nominates D1 with "the captured
values (cmd 0.05, speed 3.2e-28)" — but that container capture
(`EVIDENCE_SIGNAL_LOSS.md` case D) froze with **BeltPos 2.5**, a belt sitting
on its mechanical stop, i.e. nearly stationary. Generalising it to "the frozen
input image reads speed ≈ 0" is false for the transporting belt T4.6
stipulates. T4.7's "the fault re-latches within 1 s" inherits the same
assumption: after a reset+start against a mid-motion-frozen image (speed
0.15), neither term fires, so it would *not* re-latch. So T4.6/T4.7 assume a
detection §6.6/§7 never guaranteed — not one the m3-25/m3-27 revisions
removed; m3-27's conjuncts (`#beltFeedbackValid` in `#beltMoving` and `#d1`)
change nothing here because the frozen values are plausible.

No other scenario assumes anything the revised §6/§7 fails to guarantee: T2.3's
repeatable dwell is now guaranteed precisely *by* m3-25's unconditional timer
call site; T4.11's recovery reasoning matches §6.3's C5-versus-soft-limit
distinction; the cold-start plausibility of the belt start values (0.0 inside
both windows) is stated in §6.2.2 and holds.

## Finding 2 — T1-T4 as run. Verdict: **pass-with-findings** (the record is honest; two labelling gaps)

Compared step by step against §11, from the CSVs and §B of
`bridge/EVIDENCE_LATENCY.md`:

| Step | As run | Note |
|---|---|---|
| T1.1/1.1b/1.2/1.3 | ran, followed | over OPC UA, not the watch table — (a) correctly not claimed |
| T1.4 | **failed**, first half only passed | range 1.4401→0.5400 followed; `ProductPresentAtSensor` did **not** follow — this is F1. §B files it under §B.13 but never marks T1.4 itself failed; it reads as if T1 passed entire |
| T1.5 | equivalent ran | belt values changed live in the observer |
| T2.1 | passed | belt moved, product carried, re-home branch recorded (6×, all from the positive side) |
| T2.2–2.4 | **not reachable** (F1) | correctly listed, §B.12 item 8 |
| T2.5–2.8 | passed | interlock snap to 0.0, 30 s no-auto-resume, reset moves nothing, separate start |
| T3 | substantially met | stats with count/min/median/p95/max, 20.00–20.02 Hz, 0 overruns, L7 ×6, Tailscale absence measured from the routing table; the two CPU-diagnostics obligations stay owner-outstanding |
| T4.1–4.4 | passed | A/B identical at the program; freeze values 4537 / 1352 confirmed in the CSV |
| T4.5 (C) | skipped | reason holds: requires stopping the owner's CPU/adapter, forbidden by the m3-26 brief |
| T4.6 | **failed** — F2 | confirmed in CSV, finding 4 |
| T4.7 | not executable | presupposes the latch F2 never produced; the report says so |
| T4.8, T4.9b | skipped | reason holds: cold-starting the CPU is forbidden to agents |
| T4.9 | passed exactly | 18 s held reset never cleared; the new edge did |
| T4.10 | measured | 11.79 s / 0.0 s on PLCSIM; hardware variant correctly kept open |
| T4.11 | **not run and not recorded** | see below |

Two labelling gaps, neither affecting a conclusion:

1. **T1.4 is a failed step, not merely an unclaimed one.** The OPC UA
   instrument was sufficient to *fail* it (the verdict node is server-visible
   and never asserted); only *passing* it needs the watch table.
2. **T4.11 is silently absent.** It appears neither in §B.7's as-run record
   nor in §B.12's owner-outstanding list, yet "Pass: all twelve" counts it. It
   is doubly owner-only: it needs a narrowed-constant compile/download (TIA),
   and it needs a program built to the m3-27 spec at all — §B's header says
   the program in RUN was the **m3-05** build, which predates §6.2.2/C5
   entirely. Whether the owner rebuilt to m3-25/m3-27 before the run is
   recorded nowhere; the evidence cannot distinguish (the dwell was
   unreachable and no implausible value was ever presented). §B.12 should
   carry T4.11, and the rebuild baseline should be stated when F1/F2 are fixed.

## Finding 3 — F1 root cause. Verdict: **program defect (owner-fixable in TIA); the SPEC is exonerated on this path**

What the CSVs establish. The observer saw **six** beam-blocked intervals
(range < 1.0 m), not one: 47.00–49.12, 124.55–126.67, 160.48–162.59,
184.49–186.61, 292.40–294.62, 340.53–342.64 s — each ≈2.1 s at a constant
0.5400331616401672 m, no chatter into the hysteresis band (22 consecutive
identical samples in the first). `ProductPresentAtSensor` has **exactly one
distinct value in all 3 907 rows: False**. During the first interval
`BridgeLinkOk=True`, `CellCycleRunning=True`, `ConveyorSpeedCommand=+0.15`,
`CellResetRequired=False` throughout; the command stayed +0.15 until
t=54.76 s, pos **2.4123 m** ≥ `SOFT_LIMIT` 2.40, where the cycle dropped and
latched. (§B.13's "47.10→48.92, 1.8 s" is directionally right but reproduces
from no committed CSV — see finding 6.)

Discriminating the brief's four candidates:

| Candidate | Verdict | Evidence |
|---|---|---|
| §6.2 window constants vs geometry | **excluded** | With the product present the beam reads 0.5400 m — *inside* the detect window as specified: > `RANGE_MIN` 0.05, < `PRESENT_THRESHOLD` 1.00. Absent it reads 1.4401 > `PRESENT_CLEAR` 1.10. The cell geometry (`sim/README.md` §photo-eye, `CELL_EVIDENCE.md`) matches the node values exactly. As specified, presence must assert ~100 ms into every block |
| `BridgeLinkOk` gate on the verdict | **excluded** | LinkOk was True through every blocked interval — and, stronger, the cycle *kept running at +0.15 through the beam to the soft limit*. C3 and C4 sit in `WorldOk`; had either been false for one OB call the cycle would have dropped and the command snapped to 0.0 then, not at 2.4123 m. So `#linkOk AND #rangeValid` held continuously |
| Presence-timer call-site (§6.5 note, m3-25) | **excluded as spec text** | The presence timers sit under `IF #rangeValid` (§7 part 2), and `#rangeValid` was continuously true for ≥2 s windows, so the call site executes every scan; §6.5's exemption for these timers is sound. (It survives only as a *build* suspect — the LESSONS 54/55 pattern, a hand-placed call that never executes) |
| 100 ms filter × 20 ms OB30 sampling | **excluded** | A TON with PT=100 ms needs 5 consecutive 20 ms calls with IN true; the DB value held 0.5400 constant for ≈2.1 s (bridge rewrote it cyclically at 20 Hz, same value). There is no interaction to have |

Every specified mechanism, fed the recorded values, asserts the verdict. The
presence text is **byte-identical in every committed SPEC revision** (43983bf
→ 91ef599 → 5b7cb7a → 21075a3: same §6.2.3 rules, same §7 part 2 sketch, same
1.00/1.10/T#100ms constants), so no build-baseline ambiguity rescues the
program. **F1 is a divergence of the TIA build from §6.2.3/§7 part 2.**

The CSV narrows *where*. Both consumers of the verdict — the server node and
the step-10 exit (`IF "DemoCellStatus".ProductPresentAtSensor THEN #SeqStep :=
20`) — read the same global DB tag, and both behaved as if it were False
(node never True; step 10 never left). So the defect is upstream of both: the
verdict is never *formed*, not formed-but-unmapped. A swapped on/off timer
pair or an inverted comparison is also excluded — either would have made the
node read True while the beam was *clear*, i.e. most of the run.

**Top hypothesis:** the `PresenceOnTimer` input condition never becomes true
in the build — most plausibly `PRESENT_THRESHOLD` as entered in the FB
constant block is not 1.00 m (a value below 0.54, or a unit slip), or the
presence network is dead code (a call site inside a branch that does not
execute, the §6.5-forbidden form's sibling).

**Confirming observation** (owner, one watch-table session, §9 Group 1+4,
beam blocked ≥1 s with the link up): read the constant block values of
`PRESENT_THRESHOLD`/`PRESENT_CLEAR` as compiled, and watch
`PresenceOnTimer.ET`. If `ET` stays 0 with the range group showing 0.540, the
IN expression/constant/call-site is the defect (compare the entered constant
against 1.00). If `ET` runs to 100 ms and `Q` goes True while
`"DemoCellStatus".ProductPresentAtSensor` stays False, the verdict assignment
is the defect. One observation discriminates the whole remaining space. Per
the verifier's standing rule, the constants as compiled are tool-facts to be
owner-verified-in-tool, not design values to be trusted from this document.

## Finding 4 — F2 root cause. Verdict: **spec defect (agent-fixable document change), faithfully implemented**

Both blinding mechanisms confirmed, from the SPEC text and the observer CSV
(`caseD` window; the bridge-side `latency-2026-07-27-plcsim-caseD.csv.gz`
corroborates the session):

- **Timeline (observer):** motion started t≈356.86 at pos 0.0477 (speed
  read-back crossed `SPEED_TOLERANCE` between 356.86 and 356.96, pos
  0.048–0.062). The image froze at **pos 0.9273 / speed 0.1500** from
  t=363.41; heartbeat kept advancing (752 → 1268); `ConveyorDriveFault` is
  **False in every one of the 3 907 rows of the run**; the cycle finally
  dropped at t=389.74 by `LinkLostLatch` when bridge #3 was stopped —
  **26.3 s undetected** under a +0.15 command.
- **D1 blinded, per §6.6 term D1:** it needs `ABS(ConveyorBeltSpeed) ≤
  SPEED_TOLERANCE` (0.02); the frozen read-back is 0.1500. Confirmed false
  for the entire window.
- **D2 blinded, per §7 part 3:** `PosWindowArmed` is set on the first scan of
  motion and cleared only by `NOT #beltMoving`; the frozen non-zero speed
  keeps `#beltMoving` true, so `PositionRef` stays the motion-start position
  (≈0.05 m) forever. `ABS(0.9273 − ~0.05) ≈ 0.88 m` against a band of
  0.005 m: `#d2` is false by construction, permanently. §6.6's prose is the
  root, not just the sketch: *"on the rising edge of the condition, sample
  PositionRef and start PositionWindowTimer; on expiry compare"* — a
  **one-shot window per motion segment**, with no re-arm on expiry. The
  window never slides, so D2 detects a freeze only in its first
  band/speed ≈ 33 ms. (§B.13's "travelled from 0.3093" is the position ≈1.9 s
  *after* motion start, not the armed reference; the true delta is larger
  still — see finding 6. The conclusion is unaffected either way.)

Because the sketch and the prose agree, a build faithfully implementing the
SPEC cannot detect a mid-motion freeze: **the defect lives in
`plc/demo-cell/SPEC.md` §6.6 + §7 part 3, with §8's case-D row and §11
T4.6/T4.7 promising what that logic cannot deliver** (finding 1). Fixing it
is a `plc`-agent document revision followed by an owner rebuild — the correct
half of the m3-26 report's own attribution.

**Recommendation, not a decision**, for what a correct D2 would compare:

1. **Re-armed reference (minimal delta, preferred candidate).** On
   `PositionWindowTimer.Q`, evaluate the travel, then re-sample `PositionRef`
   and restart the window (clear `PosWindowArmed`, or re-sample directly), so
   the check repeats every `DRIVE_FAULT_DELAY` for as long as motion
   continues. No false positive at the boundary: the slowest speed that keeps
   `#beltMoving` true (0.02 m/s) travels 0.02 m per 1 s window, 4× the
   0.005 m band. Uses only existing statics; keeps §6.6's intent that D2 is
   the slower verdict (window + `DRIVE_FAULT_DELAY`).
2. **Travel/rate-of-change accumulator.** Sum `ABS(Δposition)` per OB call
   over a rolling window while `#beltMoving`; trips when the sum stays under
   the band. Equivalent verdict, new state, more code.
3. **Image-freshness test** (position bit-identical over N scans while
   `#beltMoving`) is *not* recommended: at 20 Hz cyclic writes a live belt at
   0.15 m/s moves 7.5 mm per write, so it would work, but it supervises the
   transport's write pattern rather than the physics, which is the boundary
   §6.6 already refuses to cross.

Whichever is chosen, §8's case-D row and T4.6/T4.7 must be rewritten in the
same commit (LESSONS 2026-07-26: update the requesting document with the
revision), and the honest-limit paragraph of §6.6 should state the remaining
blind spot precisely (a freeze under a zero command stays undetectable; a
freeze within the first window of motion is detected one window later).

## Finding 5 — interaction check. Verdict: **no masking; one beneficial interaction to record**

- **C5 (m3-27) does not mask or alter F1's soft-limit runaway.** Throughout
  the runaway the belt values stay inside the plausibility windows (max pos
  2.4123 < `BELT_POSITION_MAX` 2.60; speed 0.15 < `BELT_SPEED_MAX` 1.00), so
  `BeltFeedbackValid` holds and C5 never drops the cycle. This is by
  construction, not by luck: §3.3 sets the windows deliberately wider than
  the ±2.50 m mechanical stops, so **no physically reachable state can trip
  C5 before the §6.5 soft-limit abort at 2.40 m**. A re-run of T2 with the
  current spec and F1 unfixed reproduces exactly what m3-26 recorded.
- **C5 does not fix or mask F2 either.** The frozen image (0.9273, 0.1500) is
  plausible, so `BeltFeedbackValid` stays true and m3-27's new conjuncts in
  `#beltMoving`/`#d1` evaluate identically. F2 persists post-m3-27.
- **The m3-25 dwell-timer form is unexercised while F1 stands** (step 20 is
  never reached), so it changes nothing on a re-run today. Once F1 is fixed,
  it is what makes T2.2–2.4 pass *repeatably*: the pre-m3-25 `IN := TRUE`
  form was correct exactly once, so a single-cycle T2 pass would have masked
  it. Run T2 at least twice end-to-end when closing (b).
- `STEP_TIMEOUT` (60 s) interacts with neither: the F1 transport ran ≈18 s to
  the soft limit, well inside the watchdog.

## Finding 6 — evidence hygiene. Verdict: **pass-with-findings** (figures traceable; three nits, none load-bearing)

Reproduced exactly from the committed CSVs (commit `cc43369`): the six L7
samples (36.4 / 46.6 / 47.4 / 46.9 / 47.7 / 46.4 ms → count 6, min 36.4,
median 46.8, p95≈max 47.7) re-derived independently from the L2/read_rt rows
by §B.5's stated rule; §B.3's per-session R1 count/min/median/max and rates,
digit for digit; session #1 carrying no `disconnect` row where #2/#3/#4 carry
`clean shutdown`; the granted-10 000 ms session rows in every CSV header; the
heartbeat freezes at 4537 (t=227.66) and 1352 (t=311.47); `BridgeLinkOk`
False ≈0.4–0.5 s after each freeze (0.1 s observer quantisation); the case-D
window of finding 4; `ProductPresentAtSensor` and `ConveyorDriveFault` never
True anywhere in 394 s.

Nits, all conservative in direction:

1. **§B.13 F1's "1.4401 → 0.5400 at t=47.10 … until t=48.92 — 1.8 s"
   reproduces from no committed file under any obvious definition.** The
   observer gives 47.00→49.12 (≈2.11 s); the bridge session gives
   46.41→48.66 session-relative (≈2.25 s between crossing writes). The claim
   *understates* the block, so the conclusion (≥18× the 100 ms filter) only
   strengthens — but LESSONS 2026-07-27 (m3-21, "quote counts as the harness
   prints them") applies: a figure should name its CSV and clock.
2. **§B.13 F2's "travelled from 0.3093 to 0.9273 … ≈ 0.62 m"**: 0.3093 is the
   belt position at t=358.77, ≈1.9 s after motion start; the reference D2
   would actually have armed is the motion-start position ≈0.05 m, making the
   real delta ≈0.88 m. A fortiori, but the printed number is not the armed
   reference.
3. **The video is outside the repository** (session scratchpad), declared
   honestly in the m3-26 report; the run narrative it carries is fully backed
   by the observer CSV, so nothing gate-relevant depends on it. It will not
   survive the session; if the owner wants it as M3 evidence it must be
   regenerated or moved by someone with write access.

**§B.12's owner-outstanding list is genuine**, item by item: (1)(2) need the
TIA watch table, a GUI no agent can open; (3) CPU/OB30 cycle diagnostics live
in TIA, off the `DemoCell` interface; (4) L4 needs the watch table timestamp;
(5) case C and (6) T4.8/T4.9b require stopping or cold-starting the owner's
CPU, forbidden to agents; (7) needs hardware that does not exist here; (8) is
blocked on F1, whose fix is a TIA rebuild. **One omission:** T4.11 belongs on
that list too (finding 2) — it needs both a TIA recompile and a program built
to the m3-27 spec, and it is currently in no as-run record and no outstanding
list while "Pass: all twelve" counts it.
