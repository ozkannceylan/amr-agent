# Brief m5-16 — the standard program's M5 delta: modes and the envelope

```
gate:                M5
agent:               plc
goal:                plc/forklift/SPEC.md specifies what the standard program
                     must gain for autonomous mode, so the owner can build it
                     in TIA without a design question left open.
invariants_touched:  none. Invariants 5, 6 and 10 constrain the envelope and
                     the specification should show the check.
inputs:              [plc/forklift/SPEC.md sections 7 and 13 (the M4 program
                      this extends),
                      docs/interfaces/opcua-nodes.md section 12 (the nine
                      nodes — this specification implements them, it does not
                      redefine them),
                      docs/adr/0011-sensored-autonomy-architecture.md D3,
                      docs/adr/0012-envelope-composition.md D1,
                      docs/adr/0014-motion-control-locus.md (all five
                      decisions — especially D4's three seams and D5),
                      docs/reports/m5-17-envelope-mode-nodes.md (the tag list
                      it hands you)]
deliverable:         plc/forklift/SPEC.md — a new section in the §7 pattern
done_when:           the standard program's new behaviour is specified to the
                     level §7 already reaches — declarations, networks,
                     conditions written so they can be transliterated into the
                     tool without a judgement call; mode arbitration is
                     complete, including what happens on a mode request while
                     the machine is moving, while a process stop is latched,
                     and when the requesting client stops talking; the
                     envelope's three elements are formed with the source of
                     each stated — the enable, the ceiling, and the
                     equipment permit derived from the PLC's OWN station
                     handshake and never from an order, route or destination;
                     the teleop path of §7 is shown to be UNCHANGED, with the
                     mode selector deciding only which source may write the
                     request nodes; the fork-height speed clamp remains
                     process logic and is stated to apply in BOTH modes; every
                     new timer's PT is explicit at the call site; and each
                     cold-start value matches §12's start values, checked
                     row by row rather than assumed.
forbidden:           [specifying anything in the safety program (m5-15's, and
                      blocked on the m5-03 verdict); redefining any node from
                      §12 — implement it or report a conflict; specifying
                      vehicle-side logic (the gate node is m5-11's); adding a
                      node the interface does not define; presuming the
                      m5-03 F-I/O verdict anywhere; committing (the
                      orchestrator commits)]
```

## What this program is and is not doing in autonomous mode

ADR 0014 locked it: the vehicle closes the path-following loop and writes its
own actuators; the PLC forms the envelope and does not form per-sample motion
setpoints in autonomous mode. So this section specifies a **supervisor**, not
a controller — and the specification should be written so that a reader cannot
mistake one for the other. In teleoperated mode nothing changes at all: §7
already forms every setpoint from the HMI's requests and continues to.

ADR 0014 D5 adds an honesty obligation that touches this document: the PLC's
authority in autonomous mode is permissive and **checked, not compelled** —
the enforcing gate runs on the vehicle. Say so once, plainly, where the
envelope is specified. A specification that implies the PLC compels the
vehicle would be wrong, and the M5 showcase has to narrate the truth anyway.

## Points that will otherwise become questions at the watch table

- **Mode arbitration is the risky part.** Two sources can write motion
  requests and only one may be live. Specify the arbitration as a state
  machine with its transitions named, including the ugly cases: a mode request
  arriving mid-motion, a mode request while a process stop is latched, and the
  losing source continuing to write. Do not leave "the HMI should not do that"
  as the answer — the program's behaviour when it does is the specification.
- **The equipment permit's terms are empty at M5.** §12 records this: the
  permit exists, its meaning is fixed, and the term set it is derived from
  belongs to the fixed equipment. Assign the terms from what the demonstration
  cell actually has, or state explicitly that at M5 it is derived from a named
  subset and what M6 will add. Never a literal TRUE.
- **The speed ceiling is not a setpoint.** §12 protects that reading four
  ways; this specification must not undo it by writing logic that reads like a
  velocity command path.
- **Cold start.** Every value non-permissive, matched against §12 row by row.
  The demo cell has already been bitten by a start value that governed nothing
  because an instance DB outlived an interface default.

## Notes

Write it so the owner can transliterate it. The §7 precedent is the standard:
this project has twice found a specification defect by building an executable
double rather than by review, and both defects were in test procedures, not
logic — so a specification that is precise enough to transliterate is also
precise enough to double.

Every timer's PT explicit at the call site: an in-force instance value that
contradicts the code has cost this project a debugging session before.

Do not commit. Leave the file modified and write your report to
docs/reports/m5-16-standard-program-delta.md.
