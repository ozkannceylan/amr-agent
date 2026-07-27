# Brief m3-27 — plausibility windows for the belt feedback signals

gate:                M3
agent:               plc
goal:                a NaN or out-of-range belt feedback value cannot disarm the soft-limit aborts
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md (§12 open item 5 and the affected-comparison table recorded by m3-25), docs/interfaces/opcua-nodes.md (read only, for the physical ranges), docs/LESSONS.md]
deliverable:         plc/demo-cell/SPEC.md
done_when:           ConveyorBeltPosition and ConveyorBeltSpeed each carry a plausibility window stated in the affirmative form §6.2 now requires, an implausible value on either drives a fault reaction rather than being consumed as a value, every comparison in the m3-25 table is covered, and §12 open item 5 is closed
forbidden:           [editing files outside plc/, changing any control behaviour beyond what this defect requires, re-specifying the soft limits themselves, writing code for TIA, adding dependencies]

## Context

m3-25 corrected the two defects the owner reported and, sweeping for more
of the same, found a third the owner has not seen: `ConveyorBeltPosition`
and `ConveyorBeltSpeed` have no plausibility window at all. Because every
comparison against NaN returns false, a NaN position makes both soft-limit
aborts fail to fire — the abort path disarms itself exactly when the
feedback is broken. m3-25 recorded it as §12 open item 5 with a table of
every affected comparison and its direction, and could not fix it because
its brief forbade adding an interlock. This brief authorises that.

## Constraints on the fix

The reaction to an implausible belt feedback is a fault, latched like the
other faults and cleared by the monitored reset — not a permissive, and
not a silent substitution of a last-known-good value. Invariant 10 holds:
the window constants have one owner and are stated once. Follow §6.2's
affirmative form; a negated out-of-window test reintroduces the defect.

The owner has already built a program from this document, so the report
must state plainly and specifically what the owner has to change in the
running program — this is a behaviour change to an existing build, not a
documentation tidy.
