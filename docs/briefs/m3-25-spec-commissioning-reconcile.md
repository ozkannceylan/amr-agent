# Brief m3-25 — reconcile SPEC.md with the commissioned implementation

gate:                M3
agent:               plc
goal:                plc/demo-cell/SPEC.md matches the program that was built and verified running on PLCSIM, with the dwell-timer defect corrected at its source
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md, docs/LESSONS.md (the two 2026-07-27 entries on the step TON and on affirmative plausibility), the owner's commissioning feedback below]
deliverable:         plc/demo-cell/SPEC.md
done_when:           §7's dwell timer is specified with a released IN so a second cycle dwells as the first did; §6.2 open item 1 is closed with the affirmative-form condition stated explicitly rather than merely dropped; and an independent whitespace-normalised sweep of the document finds no other timer specified with a literal TRUE input and no other plausibility or fault test written as a negated out-of-window comparison
forbidden:           [editing files outside plc/, changing any control behaviour beyond the two items below, writing code for TIA, restating the owner's PLCSIM observations as spec text, adding dependencies]

## Owner commissioning feedback (2026-07-27, program running on PLCSIM)

FB_DemoCellControl (SCL) is called from OB30 at a 20 ms cyclic interrupt
with instance DB DemoCellControl_DB. It compiles clean, is downloaded, and
the CPU is in RUN. Two deviations from this spec were reported.

1. **SPEC DEFECT — §7 dwell timer.** The spec calls the dwell TON with
   `IN := TRUE` and never releases it. `DwellTimer.Q` therefore stays set
   after the first cycle and every later cycle skips the dwell. The
   implementation adds `IN := FALSE` on leaving step 20. Correct the spec
   at its source: a step's dwell timer is driven by that step's own
   activity and released on step exit. Check whether the same pattern
   appears in any other timer in the document.

2. **§6.2 open item 1 — IS_VALID omitted, accepted with a condition.** The
   implementation omits the explicit IS_VALID call because every comparison
   against NaN returns false, so NaN and inf are rejected by the two range
   comparisons alone. This is correct *only* while validity is written
   affirmatively — `valid := (low < x) AND (x < high)` with the fault in
   the ELSE. Under a negated out-of-window test the same omission would let
   NaN read as plausible and pass a broken sensor through as a value, which
   is the failure LESSONS records twice. Close the open item by stating the
   required affirmative form and the ELSE-is-fault rule as normative, not
   by simply deleting the IS_VALID requirement.

Do not restate the owner's cold-start observations (BridgeLinkOk False,
CellProcessStopActive True, CellResetRequired True, ConveyorSpeedCommand
0.0) as specification text — they are evidence of the spec, and they belong
to the gate evidence, not to the document that predicts them.
