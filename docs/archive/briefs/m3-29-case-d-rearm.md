# Brief m3-29 — case D detection that works mid-motion

gate:                M3
agent:               plc
goal:                SPEC.md's signal-loss case D detection catches a frozen read-back at any point during motion, not only in the first sampling window
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md (§6.6, §7 part 3, §8 case-D row, §11 T4.6/T4.7), docs/reports/m3-28-t-scenario-review.md (F2 finding and recommendation), docs/reports/m3-26-live-loop-run.md, docs/LESSONS.md]
deliverable:         plc/demo-cell/SPEC.md
done_when:           the revised §6.6 detects the recorded failure (read-back frozen at position 0.9273 / speed 0.1500 while the command is non-zero) within a stated, justified time bound; §8's case-D row and §11 T4.6/T4.7 promise exactly what the revised logic guarantees, including a mid-motion freeze test, not only a freeze at motion start; and the report states what the owner must change in the running program
forbidden:           [editing files outside plc/, moving any detection logic into the bridge, weakening the heartbeat's role as the supervision backstop, redefining the M3 exit criterion, writing code for TIA, adding dependencies]

## The defect (m3-28, F2 — a spec defect faithfully implemented)

§6.6 specifies a one-shot D2 window: on the rising edge of motion, sample
PositionRef; on expiry, compare against a 0.005 m freeze band. Never
re-armed. A freeze later in motion is compared against the full
accumulated travel and can never fire; D1 is blinded whenever the frozen
speed read-back is non-zero. The live run confirmed it: 26.3 s undetected,
ConveyorDriveFault never True in 394 s. The capture §6.6 generalised from
(cmd 0.05, speed 3.2e-28) was a belt parked on its mechanical stop — a
degenerate state, not a model of mid-motion freezes.

## Constraints on the fix

m3-28 recommends a re-armed periodic reference; a rate-of-change test was
named as the alternative. Choose within §6.6 and justify against §9
conventions — level for conditions, no edge for state that survives a
restart, and the verdict gated like every other input-derived verdict.
Remember what case D is for: the bridge process is alive but the data is
stale, which the heartbeat cannot see. The detection bound you state must
be honest about the 20 ms OB30 cycle and the 50 ms bridge cycle, and the
fault reaction stays the drive-fault latch cleared only by the monitored
reset. The owner rebuilds from this document — state the delta precisely.
