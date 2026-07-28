# Report m3-29 — case D detection that works mid-motion

brief:               docs/briefs/m3-29-case-d-rearm.md
status:              done
files_changed:       [plc/demo-cell/SPEC.md, docs/reports/m3-29-case-d-rearm.md]  (nothing committed)
invariants_touched:  none
open_questions:
  - `bridge/EVIDENCE_LATENCY.md` §B must gain **outstanding rows**, not a larger
    denominator, for T4.6 (re-run required — the recorded run failed it), T4.6b
    (new), T4.7 (its pass condition has changed) and T4.11 (m3-28 finding 2,
    still absent from both the as-run record and the outstanding list). That
    file is outside `plc/` and is requested, not edited.
  - The rebuild baseline is still unrecorded (m3-28 open question). The owner
    should state which SPEC revision the downloaded program was built to when
    the F2 fix is downloaded, so the next run's evidence has a baseline.
  - F1 (the presence verdict never forming) is untouched by this brief and still
    blocks T2.2–2.4. T4.6 as revised does not depend on it: the freeze is
    injected mid-transport, before the beam.
  - `POSITION_WINDOW_TIME` is introduced as its own constant at the same value
    `DRIVE_FAULT_DELAY` had. If the owner prefers one fewer constant, collapsing
    them is a one-line change — but §3.3 states why they are separate, and the
    argument is `BELT_FAULT_DELAY`'s (invariant 10).
next_suggested:      Owner TIA session implementing the delta below, then re-run T4.6/4.6b/4.7 against PLCSIM and record the measured freeze-to-latch time as a number.

---

## What was wrong, restated as the fix had to address it

§6.6 armed `PositionRef` **once per motion segment**, on the rising edge of
motion, and never re-armed while motion continued. Travel was therefore measured
from the start of the stroke, so the comparison against a 0.005 m band could only
be satisfied inside the first ≈33 ms of motion. D1 was blind in parallel, because
a mid-motion freeze holds a plausible ≈0.15 m/s. The m3-26 run went **26.3 s
undetected** with `ConveyorDriveFault` `FALSE` in all 3 907 observer rows.

Equally important, per LESSONS 2026-07-28 (59): the capture §6.6 generalised from
(cmd 0.05, speed 3.2e-28) was a belt **parked on its mechanical stop**. It models
a freeze at rest, not a freeze during transport, and the document now says so in
those words rather than presenting it as the case-D capture.

## The fix chosen, and why

m3-28's **recommendation 1, the re-armed reference** — not the accumulator. It
reuses the statics that exist, adds one Bool and one constant, and does not
re-derive at 50 Hz a verdict consumed once a second. The one property it gives up
(net displacement cannot tell "did not move" from "moved out and back inside one
window") is written into §6.6.2 together with the reason it cannot arise here:
the program's only direction reversal is step 20 → 30, and step 20 commands `0.0`
and holds the belt below `SPEED_TOLERANCE` for the whole dwell, which disarms the
window. A future step that reverses without a stationary dwell must move to the
accumulator form, and that instruction is in the document.

Two design points that were not in the recommendation and are load-bearing:

1. **The verdict had to become a level, not a pulse.** Re-arming alone would have
   made `#d2` true for one OB call per window, and `DriveFaultTimer` is a TON —
   it would have been reset every window and could never have reached
   `DRIVE_FAULT_DELAY`. `PositionFrozen` is therefore a static level verdict, set
   at each expiry and cleared when motion is no longer claimed. This is
   CLAUDE.md §9's "level captures conditions"; it is not Retain and survives no
   restart.
2. **Restarting the TON needs `IN` to drop.** `PosWindowArmed` is cleared for
   exactly one OB call at each expiry, which is what makes the timer restart while
   its enabling condition has not gone away. The call site stays unconditional and
   outside every branch, so this is the opposite of LESSONS 54/55, not a variant
   of them — §6.5 now says so explicitly, so the form is not mistaken for the
   forbidden one at build time. The one release call is why the window period is
   `POSITION_WINDOW_TIME` + 2 OB calls = 1.04 s, not 1.00 s.

## The detection bound

From the instant the input image stops being refreshed to `ConveyorDriveFault :=
TRUE`, with `POSITION_WINDOW_TIME` = `DRIVE_FAULT_DELAY` = `T#1s` and OB30 at
20 ms:

| Contribution | Worst case |
|---|---|
| The window in progress, which may report *travel* because the belt was moving for part of it | ≤ 1.04 s |
| The next window, referenced to the frozen position, measuring 0.0000 m | 1.04 s |
| `DriveFaultTimer` on the now-steady verdict | 1.00 s |
| One bridge cycle (50 ms) plus OB30 quantisation on two expiries (2 × 20 ms) | ≤ 0.09 s |
| **Bound** | **≤ 3.2 s**, and never sooner than **≈2.1 s** |

Against the recorded failure (image frozen at position 0.9273 m / speed
0.1500 m/s under a `+0.15` command at t = 363.41 s): the window re-samples
0.9273, measures 0.0000 m, sets `PositionFrozen`, and the fault latches by
**t ≈ 366.6 s at the latest** — against 26.3 s of nothing. The blind spot is
closed rather than narrowed: there is no longer any part of a stroke in which the
freeze escapes, including the first window.

The heartbeat is untouched and §6.6.3 restates its role: case D is exactly the
case in which the heartbeat is *correct*, so D1/D2 supplement it and replace
nothing, and both remain suspended while `BridgeLinkOk` is false.

## Behaviour change the owner will see, beyond the detection

D2 carries only the feedback, so **zeroing the setpoint does not clear it**. After
a mid-motion case D the read-back still claims 0.15 m/s, `CauseGone` stays false,
and the **monitored reset is refused** until the simulation is live again. This
is correct — the cause of a stale-data fault is the stale data, not the command —
but it inverts what T4.7 previously promised ("the fault re-latches within 1 s"),
so §6.3, §8 and T4.7 were all rewritten in this edit rather than left to
contradict each other (LESSONS 2026-07-26, update the requesting document in the
same commit). After the **at-rest** variant the reset is still honoured
immediately, because D1 clears with the setpoint; both paths are now written out
separately.

## The owner's implementation delta, precisely

Everything else in the program is unchanged: `DriveFaultTimer`, the
`ConveyorDriveFault` latch, `RunPermissive`, the `CauseGone` *definition*, the
monitored reset, §6.4's setpoint gate, the sequence and the presence network are
all untouched.

1. **New static** in `FB_DemoCellControl` / `"DemoCellControl_DB"`:
   `PositionFrozen` : `Bool`, start value `FALSE`.
2. **New constant** in the FB constant block: `POSITION_WINDOW_TIME` : `Time` :=
   `T#1s`.
3. **New Temps**: `windowRunning`, `windowExpired`, both `Bool`.
4. **`PositionWindowTimer`'s `PT` changes** from `DRIVE_FAULT_DELAY` to
   `POSITION_WINDOW_TIME`, and its `IN` becomes
   `#linkOk AND #beltMoving AND #PosWindowArmed` — the added `PosWindowArmed`
   conjunct is the re-arm mechanism.
5. **Replace the whole `PositionWindowTimer` / `PosWindowArmed` / `#d2` block**
   of §7 part 3 with the new form: verdict formed once at expiry into
   `PositionFrozen`; `PosWindowArmed` cleared at expiry and re-armed with a fresh
   `PositionRef` on the following call; **both** statics cleared in the `ELSE`
   (no motion claimed, or link stale).
6. **`#d2` becomes `#beltMoving AND #PositionFrozen`** — the position comparison
   no longer appears in the `#d2` expression at all; it happens at the expiry.
7. **Watch table Group 4 gains** `.PositionRef`, `.PositionFrozen`,
   `.PositionWindowTimer.ET`. During normal transport `PositionRef` must **step
   about once a second** and `ET` must sawtooth 0 → 1000 ms. A `PositionRef` that
   sits still while the belt moves is the old defect, visible at a glance.
8. **Do not add `PositionFrozen` to the reset's clear list.** It is a level
   verdict, not a latch; clearing it on reset would hand back exactly the
   auto-clear this fix removes.

## Document sections changed

§3.2 (three statics reworded, `PositionFrozen` added) · §3.3
(`POSITION_WINDOW_TIME` added, `POSITION_FREEZE_BAND` basis re-derived against the
1.04 s window) · §6.3 (`CauseGone` row; how D1 and D2 clear differently) · §6.5
(the deliberate one-call release is not the forbidden timer form) · §6.6 (D1/D2
table rewritten, new §6.6.1 mechanism, §6.6.2 bound, §6.6.3 limits) · §7 preamble
and part 3 (SCL) · §8 (case D split into D (i) at rest, D (ii) mid-motion, D (iii)
idle, with the degenerate capture labelled as such) · §9 Group 4 · §11 T4.6
rewritten, T4.6b added, T4.7 rewritten, count and the pass-count caveat · §12
m3-25 coverage row for D2.
