# Report m4f-01e — the cap is a scale, ruled at its origin

```
brief:               docs/briefs/m4f-01e-cap-scale-clause.md
status:              done
files_changed:
  - docs/interfaces/opcua-nodes.md   (edited) §10.6, the
                                     `ForkliftTractionSpeedRef` meaning cell —
                                     one line, one clause
  - docs/reports/m4f-01e-cap-scale-clause.md   (new) this report
invariants_touched:  none
open_questions:      two, listed below
next_suggested:      Authorize the second half of m4f-04e's request 1 — §10.7's
                     "in force" versus "biting" wording — as its own clause, or
                     rule it deliberately unchanged.
```

## The clause

§10.6's `ForkliftTractionSpeedRef` row said the setpoint was "formed inside the PLC from
`HmiTractionRequest` **scaled by `TRACTION_SPEED_MAX`, reduced by the fork-height speed cap when it
applies**". *Reduced* is the ambiguity: it reads either as the scale factor swapping — what
`plc/forklift/SPEC.md` §7 builds in one multiplication, `#tractionDemand * #speedCap` — or as the
product being clamped afterwards, which is the reading the T5 pass line inherited. It now reads as
**one multiplication**: `HmiTractionRequest` times the full-scale speed **in force**, which is
`TRACTION_SPEED_MAX` normally and the fork-height cap while the carriage is raised. **The cap is a
scale, not a ceiling**: what it changes is the multiplier, never a limit applied to the product
afterwards. A request of `0.20` under the raised cap — `0.30` m/s, attributed to
`plc/forklift/SPEC.md` §3.3 as a process decision this document does not set, keeping §10.12 item 4's
stance intact — commands `0.060` m/s, never `0.20`, and the operator keeps proportional control inside
the reduced range.

The arithmetic form stays a `plc/` decision, as m4f-04e said; what changes here is that the interface
row no longer admits the other one. **One line changed in the whole document**: no constant, node,
type, unit, range, count, start value or access right moved.

*Interpretation recorded, since the two lines could be read against each other:* the sentence the
`done_when` names exists only inside a node row's meaning cell, so "changing node rows" on the
forbidden list was read as the node **definition** columns — BrowseName, S7 type, OPC UA type, unit,
range — none of which was touched. Under any other reading the brief would not be executable.

## Sweep

Subject sweep across the whole of §10 over `cap`, `scale`, `limit`, `reduc*`, `clamp*`, `ceiling`,
`multipl*` and the three numbers `0.20`, `0.30`, `0.060`, against a whitespace-normalised rebuild so a
subject wrapped across a line break still matches (LESSONS 2026-07-27), read by subject rather than by
the phrasing m4f-04e quoted (LESSONS 2026-07-29). 114 context hits; the ones that bear on the reading:

| Site | Verdict |
|---|---|
| §10.6 `ForkliftTractionSpeedRef` | **The target.** Fixed |
| §10.7 `ForkliftSpeedLimitActive` — "the traction setpoint is being limited below what the operator asked for" | **Left, and it is safe.** The same sentence ends "Informational — **the reduction itself happens in the setpoint (§10.6)**", so the row makes no independent arithmetic claim and defers the mechanism by explicit cross-reference to the row just fixed. It is also *true* under a scale, at every non-zero demand. What it still admits is the narrower "biting" reading of the flag — a different question, see open question 1 |
| §10.4 `HmiTractionRequest` — "demand as a fraction of `TRACTION_SPEED_MAX`… **the PLC scales**, interlocks and gates it" | **Left, and it is safe.** This is a *unit* claim — what `1.00` means at full scale — not a claim about the arithmetic form; its own verb is already *scales*; and it never mentions the cap, so the clamp reading could only be assembled by pairing it with the old §10.6 wording. §10.6 now names `TRACTION_SPEED_MAX` as the value in force *normally*, which is exactly the case this row describes |
| §10.6 `ForkliftSteerAngleRef` — "**clamped** in the PLC to the plant's mechanical range" | **Correct as written, and must not be "fixed" to match.** The steer path genuinely clamps; the traction path genuinely scales. After this change the document uses three different words for three different mechanisms — *scale* (traction cap), *clamp* (steer range), *abort in the offending direction* (fork soft limits) — and they now discriminate rather than blur |
| §10.6 `ForkliftForkSpeedRef` — "scaled by `FORK_SPEED_MAX`" | Correct: one scale, no second cap on that path |
| §10.5 `ForkliftLinearSpeed` — "not a process cap: the cap is `TRACTION_SPEED_MAX`" | Different subject: the transducer's plausibility window against the process cap |
| §10.7 interface expectations — "the fork-height speed cap's **height and reduced speed**" | Consistent with a scale: the reduced speed *is* the swapped full-scale value |
| §10.12 item 4 — "bounds the cap at 1.00 m/s", "raising the cap re-derives the window", "the vehicle layer's own 1.50 m/s **clamp**" | Different subject throughout: *cap* there means the full-scale speed, as `plc/forklift/SPEC.md` §3.3 uses it, and the 1.50 m/s clamp is the vehicle layer's last-ditch limit |
| §10.1 "the fork-height speed cap … process interlocks"; §10.4 "an implausible request is a fault, not a value to clamp" | Classification and plausibility. Neither is an arithmetic claim |

**No statement in §10 now admits the clamp reading**, and the one number the document states —
`0.20 × 0.30 = 0.060` — agrees with `plc/forklift/SPEC.md` §6.5, §7's single multiplication, §9's
Group 3 row (`demand × 0.30`) and §11 step 5.3.4 as m4f-04e corrected them.

## Open questions

1. **The second half of m4f-04e's request 1 was not authorized by this brief and is not done.** That
   report asked for "the same disambiguation on §10.7's `ForkliftSpeedLimitActive` description", whose
   "the carriage is raised **and** the setpoint is being limited" reads as the narrow *biting* verdict
   while the program implements the wider *in force* one — `TRUE` whenever teleop is active and the
   carriage is raised, deliberately, so the lamp does not flicker as the control crosses centre
   (`plc/forklift/SPEC.md` §6.5). This brief's `done_when` is about the clamp reading and its
   `forbidden` list bars node rows, so the row was left. It is one clause when someone authorizes it.
2. **m4f-04e's other two requests are not this layer's.** Its request 2 (`plc/forklift/double/`'s
   legacy check name over a correct computation, which needs a re-run rather than an edited
   transcript) and request 3 (`sim/scenarios/forklift_commissioning.md` §11 recording that its
   findings closed) both sit outside `docs/interfaces/`. Recorded here so the trail is complete; a
   concurrent `plc` agent and the `sim` owner hold those.
