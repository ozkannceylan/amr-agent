# Report m4f-04e — T5 pass-line corrections from the rehearsal

```
brief:               docs/briefs/m4f-04e-t5-pass-line-corrections.md
status:              done
files_changed:       [plc/forklift/SPEC.md,
                      docs/reports/m4f-04e-t5-pass-line-corrections.md]
invariants_touched:  none
open_questions:      three, all requests on other layers' files — the node
                     model's own wording, the double's legacy label, and the
                     rehearsal record that raised both findings
next_suggested:      close findings 1 and 2 in
                     sim/scenarios/forklift_commissioning.md §11, which is the
                     document that requested this revision
```

Prose, two step rows and one watch-table row. Verified the way m4f-04b and
m4f-04d were: **SCL statement lines 118 before, 118 after**, and the whole §7
fence byte-identical *including its comments* (`sha256/16` `c46abb76835666b8`
both sides). §3.1 tags, §3.2 statics and §3.3 constants byte-identical. Of the
**43 step rows in §11, 41 are byte-identical** and the two that changed are
5.1.1 and 5.3.4. All six scenario pass counts re-derive from their own tables
and none moved: 9, 8, 5, 10, 6, 5.

## Finding 1 — the cap is a scale, and the pass line said clamp

§7 forms the traction setpoint in one multiplication,
`#tractionDemand * #speedCap`, and raising the carriage swaps `#speedCap` from
`TRACTION_SPEED_MAX` to `TRACTION_SPEED_CAP_RAISED`. A 0.2 demand under a raised
carriage is therefore `0.2 × 0.30 = 0.060` m/s. §9's Group 3 row already said
`demand × 0.30`. **The pass line was the only statement of the clamp**, and the
rehearsal's `+0.060` was the program being right.

**Why it survived four revisions of the table.** At full demand a scale and a
clamp give the same answer — 1.0 × 0.30, and a clamp of 1.00 down to 0.30, are
both `+0.30` m/s — so 5.3.1, 5.3.2 and 5.3.3 cannot tell them apart. 5.3.4 is
the only step in the section that can, which is what made its number the wrong
one to leave stale. That reasoning is now a note under T5.3, so nobody
"corrects" it back.

| Site | Was | Is |
|---|---|---|
| §11 5.3.4 | "Ref = ≈`+0.20` m/s — **the cap limits, it does not command**" | "Ref = ≈`+0.060` m/s — **the cap is a scale, not a ceiling**", with the arithmetic, the §9 Group 3 agreement, and `≈+0.20` named as the reading a clamp would give |
| §6.5 | "**The cap limits; it does not command.** With the fork raised and a demand of 0.2, the setpoint is 0.20 m/s, not 0.30 m/s" | The scale stated as the mechanism — the full-scale value swaps, the operator keeps proportional control inside the reduced range, `0.060` and neither `0.20` nor `0.30` — plus the full-demand coincidence that hides the difference |
| §6.5 | The narrower `ForkliftSpeedLimitActive` alternative, "one conjunct: `AND (ABS(tractionDemand) * TRACTION_SPEED_MAX > TRACTION_SPEED_CAP_RAISED)`" | That conjunct asks whether the **uncapped** setpoint would have exceeded the cap value, which is a clamp's question. Under a scale `demand × 0.30` is below `demand × 1.00` for every non-zero demand, so the narrow flag is `AND (ABS(tractionDemand) > 0.0)` — and it would drop out each time the control crossed centre, which is a *stronger* argument for the wide reading than the one it replaces. The clamp form is now written out as the thing not to write |

The last row is the one the brief's sweep was for: it is not a sentence about
the cap, it is an expression that is only correct under one, and a plain search
for the pass line's wording would not have reached it.

### The sweep, and what it deliberately left alone

Subject sweep over `cap`, `caps`, `capped`, `capping`, `clamp*`, `limit*`,
`0.20`, `0.30`, `0.060`, `reduc*`, `scale*` and `demand` across §6, §9 and §11,
run against a **whitespace-normalised** rebuild of the document so a subject
wrapped across a line break still matches (LESSONS 2026-07-27) and read by
subject rather than by the phrasing the rehearsal quoted (LESSONS 2026-07-29).
Three sites implied clamp semantics; all three are in the table above. The
remaining hits are correct and were left:

- **§9 Group 3** already states `demand × 1.00` uncapped and `demand × 0.30`
  raised. It is the row the correction agrees with, not one to change.
- **§11 5.2.3** — a 0.4 fork demand giving `≈+0.06` m/s — is the same scale on
  the fork path and was already right.
- **§3.3** `TRACTION_SPEED_MAX`, and §12 open item 1, use "cap" for the
  full-scale speed and for the vehicle layer's own 1.50 m/s clamp. Different
  subjects, and constants are outside this brief in any case.
- **§7's comment** "the cap is IN FORCE, not the cap is biting" is a label for
  `ForkliftSpeedLimitActive`, not an arithmetic claim, and §7 is byte-identical.

**One watch-table row moved**, and it is the only edit outside §6.5 and the two
steps. §9 Group 4's `ForkliftSpeedLimitActive` row said "whether or not the cap
is biting", which is true under a scale (at zero demand nothing is reduced) but
has no defined referent unless the reader knows which form the cap takes. It now
carries "and the cap is a **scale**, so it bites at every non-zero demand
(§6.5)". **No expected value in §9 changed**; Groups 1, 2, 3 and 5 and the
section preamble are byte-identical.

## Finding 2 — 5.1.1 read a race as a guarantee

`ForkliftObstacleStopActive` `FALSE` at the first reading was stated as a
certainty. It is not one, and the program is correct either way.

- The field bit's **`TRUE` start value** is not the exposure. §6.7's
  `bridgeLinkOk` conjunct keeps it out of the boot window, and the bridge's R3
  withholds the heartbeat until every configured input has carried a real
  sample, so by the time the conjunct lifts the slot holds a written value.
- The exposure is the **vehicle layer's no-data sentinel**, which stands until
  the first scan arrives. If it is still standing when the heartbeat begins, the
  field bit is `TRUE` with the link up and the latch forms on level with no
  delay — **correctly**. If the first true scan wins, no latch forms. The
  rehearsal observed both, and a third run observed the bound: R3 held the
  heartbeat through a 6.29 s sentinel and nothing was evaluated.

5.1.1 now (a) takes the reading **after both link verdicts read `TRUE` and one
further OB call**, so every verdict in the row is formed from an attributable
image rather than measured mid-link-up; (b) reads Group 2's
`ForkliftObstacleInStopZone` and `ForkliftObstacleMinDistance` **before** judging
the latch, as the rehearsal asked; and (c) states both outcomes as passing.

**It is still a check, not a blanket "anything passes".** The discriminator is
the pair, not the value: with the field bit reading `FALSE` and the distance
inside 0.05 … 8.10, `ForkliftObstacleStopActive` must **hold** — set stays set,
because a clearing field releases no latch, and clear stays clear. A `FALSE` →
`TRUE` transition under those two readings is named as the one defect signature.
`ForkliftResetRequired`'s parenthetical widened from "both link latches" to "at
least both link latches" for the same reason.

**5.1.2 and 5.1.3 needed no change and got none.** 5.1.2's refused enable holds
whichever latches are pending. 5.1.3's reset clears an obstacle latch alongside
the link latches, because `CauseGone` is `WorldOk` and by then the real scan is
in — so its "within two OB calls" still stands, and 5.1.1 now says so rather
than leaving the owner to work it out.

## Open questions — three requests, no file touched outside `plc/`

1. **`docs/interfaces/opcua-nodes.md` §10.6 admits both readings, and that is
   where this defect came from.** The `ForkliftTractionSpeedRef` row says the
   setpoint is "formed inside the PLC from `HmiTractionRequest` **scaled by
   `TRACTION_SPEED_MAX`, reduced by the fork-height speed cap when it applies**".
   *Reduced* can be read as the scale factor swapping (what §7 builds) or as the
   product being clamped (what the pass line said). The interface document does
   **not** rule here — §10.12 item 4 states these are PLC constants it does not
   set — so this specification is not in conflict with its contract, and the
   arithmetic form stays a `plc/` decision. **Requested of `interface`:** one
   clause on that row, "the scale factor is what changes, not a ceiling applied
   afterwards", and the same disambiguation on §10.7's `ForkliftSpeedLimitActive`
   description, whose "being limited below what the operator asked for" is true
   at every non-zero demand under a scale.
2. **`plc/forklift/double/EVIDENCE_DOUBLE.md` carries the legacy label over a
   correct computation.** Kernel K2 asserts `demand x TRACTION_SPEED_CAP_RAISED`
   and prints `0.2 x 0.30 = 0.06` — the scale, and right — but the check is named
   "the cap LIMITS, it does not command" in `check_kernels.py` and the K2 summary
   row repeats it. **Not edited here**: the printed line is a harness transcript
   and a transcript is quoted as the harness printed it, never edited in place
   (LESSONS 2026-07-27). Renaming the check means re-running the double and
   replacing the transcript, which is its own brief and its own deliverable.
3. **The document that requested this revision should record that it closed.**
   `sim/scenarios/forklift_commissioning.md` §11 findings 1 and 2 are both
   answered by this commit. Editing `sim/` is on this brief's forbidden list, so
   the rows are left standing rather than half-fixed — but a revision that
   resolves another document's request updates that document in the same commit
   (LESSONS 2026-07-26), and this one cannot. **Requested of `sim`**, naming this
   report.

## Scope notes

- Nothing outside `plc/forklift/SPEC.md` and this report was written.
  `docs/interfaces/opcua-nodes.md`, `sim/scenarios/forklift_commissioning.md`,
  `plc/forklift/double/` and `hmi/` were read as inputs and not edited; the two
  `hmi/` files dirty in the tree belong to a concurrent agent and were not
  staged, read for this work, or touched.
- **No constant, tag, node, start value, access right or pass count moved.** The
  numbers `0.060` and `0.30` are arithmetic on `TRACTION_SPEED_CAP_RAISED`
  = `0.30` m/s, which is unchanged.
- **`0.060` is not evidence.** It is what §7 computes, confirmed by the logic
  double, which is a transliteration of §7 and not the CPU. The gate's number is
  the one the owner reads off the watch table against PLCSIM, and this document
  remains specification rather than verification.
