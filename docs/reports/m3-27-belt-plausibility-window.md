# Report m3-27 — plausibility windows for the belt feedback signals

brief:               docs/briefs/m3-27-belt-plausibility-window.md
status:              done
files_changed:       plc/demo-cell/SPEC.md
invariants_touched:  none
open_questions:      see below (two)
next_suggested:      the owner applies the seven code edits below and re-runs T2 once to confirm a clean cycle; a bridge-side fault-injection facility (§12 open item 6) is a separate brief for the bridge agent

---

## What changed in the specification

`ConveyorBeltPosition` and `ConveyorBeltSpeed` now carry a plausibility window in
the affirmative form §6.2 requires, and an implausible value on either is a
**latched fault**, not a permissive and not a substituted last-known-good value.

- §6.2 is retitled *Analogue plausibility, and the presence verdict* and split
  into 6.2.1 (`ProductSensorRange`, unchanged behaviour), **6.2.2 (new — belt
  feedback)** and 6.2.3 (presence, unchanged). The normative affirmative-form
  block now governs both tests by name.
- **One verdict and one latch for the two belt signals.** They are `position[0]`
  and `velocity[0]` of the same `/cell/conveyor/joint_state` sample from one
  publisher through one bridge mapping; they fail together, so a second latch
  would claim a distinction the source does not offer. Which comparison failed is
  read off the two raw values already in watch-table Group 1.
- The instantaneous verdict is **C5 of `WorldOk`** (§6.3), so the cycle drops and
  the setpoint is zeroed in the *same* OB call, before the sequence or the start
  branch can read the bad number. `BeltFeedbackFaultLatch` follows 200 ms later
  and is cleared only by the monitored reset.
- §12 open item 5 is **closed**, with a coverage table mapping each of m3-25's
  five comparisons to the mechanism that now covers it. A new item 6 records that
  no genuine `NaN` can be injected from the cell and requests a bridge-side
  facility.

## What the owner must change in the running program

The program on PLCSIM was built before this defect was found. **This is a
behaviour change, not a documentation tidy.** Seven code sites plus declarations.

**Declarations in `FB_DemoCellControl`**

| Section | Add |
|---|---|
| Constant | `BELT_POSITION_MIN : Real := -2.6`, `BELT_POSITION_MAX : Real := 2.6`, `BELT_SPEED_MIN : Real := -1.0`, `BELT_SPEED_MAX : Real := 1.0`, `BELT_FAULT_DELAY : Time := T#200ms` |
| Static | `BeltFeedbackInvalidTimer : IEC_TIMER` (TON), `BeltFeedbackFaultLatch : Bool := FALSE` |
| Temp | `beltFeedbackValid : Bool` |

**Code — §7 of the specification carries the exact text**

1. **New block between part 2 and part 3** (three statements): the affirmative
   four-comparison `#beltFeedbackValid`, the `#BeltFeedbackInvalidTimer` call
   (`IN := #linkOk AND NOT #beltFeedbackValid`, unconditional, at top level), and
   `IF #BeltFeedbackInvalidTimer.Q THEN #BeltFeedbackFaultLatch := TRUE;`.
2. **Part 3, `#beltMoving`** — prepend the conjunct:
   `#beltMoving := #beltFeedbackValid AND (ABS(…ConveyorBeltSpeed) > #SPEED_TOLERANCE);`
3. **Part 3, `#d1`** — prepend the conjunct:
   `#d1 := #beltFeedbackValid AND #cmdMoving AND NOT #beltMoving;`
4. **Part 5, `#worldOk`** — add `AND #beltFeedbackValid` as C5.
5. **Part 5, `#runPermissive`** — add `AND NOT #BeltFeedbackFaultLatch`.
6. **Part 5, `#latchPending`** — add `OR #BeltFeedbackFaultLatch`.
7. **Part 6, the reset branch** — add `#BeltFeedbackFaultLatch := FALSE;`.

**Deliberately untouched:** `#d2`, every timer call, the whole `CASE`, the
setpoint gate of part 8, the soft limits, all four DBs, all 15 nodes, the server
interface and `bridge.yaml`. `#d2` needs no edit because it is already conjoined
with `#beltMoving`, which now carries the validity term. Nothing on the OPC UA
side changes, so the bridge needs no reconfiguration and no restart.

**Two practical consequences of the download**

- Adding statics to the FB **reinitialises the instance DB**. All latches and
  both edge memories return to their start values — correct, since nothing is
  Retain, but it means `ResetDeviceFault` is `TRUE` again and the reset contact
  must be seen open once (publish `reset false`) before any reset will work.
- **A healthy run looks identical.** Every real value sits well inside both
  windows, so T1–T4 should behave exactly as before. If anything faults during a
  normal cycle after this change, the window constants are wrong, not the logic —
  read the two raw values in Group 1 before adjusting anything.

**Verifying it actually works** is §11 step 4.11: temporarily set
`BELT_SPEED_MIN`/`MAX` to ±0.10, download, press start, and watch the cell drop
and latch as the read-back passes 0.10 m/s; then restore ±1.00 and re-download
before recording any gate evidence. **Use the speed constant, not the position
constant** — narrowing the position window parks the belt outside its own window
and the cell cannot be recovered until the constant is restored. That is an
artefact of the test only: the real ±2.60 m window lies beyond the ±2.50 m
mechanical stops, which is exactly what makes C5 safe as a blanket permissive.

## Open questions

1. **`BELT_SPEED_MIN`/`MAX` = ±1.00 m/s is a design value, not a measurement.**
   `sim/README.md` states no drive maximum, only the verified ±0.15 m/s. ±1.00
   was chosen as ≈6.7× the transport speed: wide enough that no legitimate
   transient reaches it, which is the correct bias for a window whose job is to
   reject `NaN`, `inf` and gross corruption rather than to police the drive. If
   the PLCSIM run shows the read-back overshooting on reversal, widen it; do not
   tighten it towards `SPEED_TOLERANCE`.
2. **`NaN` itself is not testable from the cell** and is recorded as §12 open
   item 6: a bridge-side, explicitly opt-in fault-injection mode that can write a
   nominated `DemoCell/Input/` Real as `NaN`, `inf` or out-of-window. That is
   `bridge/` work; this program must behave identically whether or not it exists,
   and §11 4.11 plus the affirmative-form argument stand in the meantime.
