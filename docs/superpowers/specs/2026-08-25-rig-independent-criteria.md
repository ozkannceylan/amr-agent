# Rig-independent criteria for the next fleet gate (M6 review item 5d)

**Status:** derivation only - no gate is edited retroactively. M6.6's
800 m / 12-transport bars stay failed as written, exactly as its PROOF
section says; this note is where the NEXT milestone's bars come from.

## The defect in the old bars

Both were written in WALL minutes against a rig assumed to run at real
time. This rig runs at 0.55-0.65 integrated RTF on the GPU renderer
(measured M6.5 through 2026-08-25), so ten wall minutes are five to six
plant minutes, and the bars silently demanded a fleet twice as fast as
the plant they run in. A criterion that moves when the host machine
does is a criterion about the host machine.

## The fix: measure in SIM seconds, judge against a measured baseline

Every run already records sim time (the camera stamps it; score_run
samples odometry against it). Normalizing the three measured runs:

| run | wall s | RTF (integ.) | sim s | distance m | m per SIM s | transports | per 600 SIM s |
|---|---|---|---|---|---|---|---|
| M6.6 demo (2026-08-23) | 630 | ~0.55-0.58 | ~360 | 404.4 | 1.12 | 4 | ~6.6 |
| M6.7 demo (2026-08-23) | 630 | ~0.55 | ~350 | 365.3 | 1.04 | 4 | ~6.9 |
| review take (2026-08-25, box on floor 4 min) | 701 | ~0.60 | ~420 | 309.1 | 0.74 | 1+ | - |

So the floor's demonstrated capability is **~1.0-1.1 m of fleet travel
per sim second** and **~6-7 transports per 600 sim seconds** at four
trucks with the 3 s dwell stub. The gap from ~7 to the old bar's 12 is
NOT rig: it is leg-1 deadhead (every transport drives empty to its
pickup), the dwell, and corridor waits - all cell properties with named
levers (pick/drop realism will move the dwell, the head-on resolver and
node closures shrink the waits).

## Proposed bars for the next gated run (sim-time, baseline-anchored)

1. **Fleet travel >= 1.0 m per sim second**, integrated over the run -
   at or above the demonstrated baseline; a regression below it is a
   cell defect, not a rig story.
2. **Transports >= 8 per 600 sim seconds** - above baseline by the
   margin the two landed traffic fixes (head-on resolve, closure
   re-routing) are expected to buy; re-derive after the first run that
   uses them rather than defending the number.
3. **RTF is reported, never gated** above the floor that keeps scans
   arriving (0.30 integrated, floor 0.020 - M6.5's values): the rig
   constraint is stated once as a precondition, checked by
   `m6/tools/preflight.sh`, and stops leaking into every other number.

A bar is edited only BEFORE its run, in this file's successor, with the
measurement that justified it beside it - never after.
