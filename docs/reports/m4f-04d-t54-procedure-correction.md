# Report m4f-04d — T5.4 procedure correction from the double's finding

```
brief:               docs/briefs/m4f-04d-t54-procedure-correction.md
status:              done
files_changed:       [plc/forklift/SPEC.md,
                      docs/reports/m4f-04d-t54-procedure-correction.md]
invariants_touched:  none
open_questions:      none — one SECOND defect was found in the same table while
                     correcting the first, and is corrected here; see below
next_suggested:      the rehearsal run; T5.4 is now executable at a watch table
                     as written
```

Prose and step tables only. Verified the way m4f-04b was: **SCL statement lines
118 before, 118 after, identical**, and the whole §7 fence is byte-identical
*including its comments*. §3.1 tags, §3.2 statics, §3.3 constants and the §9
watch table are byte-identical. T5.1, T5.2, T5.3, T5.5 and T5.6 are
byte-identical. Three hunks: the six T5.4 rows, one explanatory note, and §12
item 4. All six scenario pass counts re-derive from their own tables; T5.4 is
still ten rows and still reads "all ten".

## The correction, in the K4 form

| Step | Was | Is |
|---|---|---|
| 5.4.4 | "assert **and release** the reset control" | "assert the reset control and **leave it asserted — do not release it until 5.4.8**" |
| 5.4.5 | "release and re-assert the enable" | Unchanged in substance; now says explicitly *the enable, not the reset, which stays asserted*, and *leave the enable asserted — 5.4.8 reads it* |
| 5.4.6 | "Clear the zone by removing the obstacle" | "**Clear the zone with the reset control still asserted** … without touching either control". Pass line now carries **two properties in one observation**: the field clearing does not release the latch, and the still-asserted reset supplies no edge |
| 5.4.7 | "assert the reset control and leave it asserted" | "**keep** the reset control asserted for a further 10 s with the zone now clear" |
| 5.4.8 | "Release the reset control, then assert it again" | Same, plus *confirm `HmiResetRequest` reads `FALSE`* between the two, and the pass line now reads the no-auto-resume property off the enable |
| 5.4.9 | "Assert the enable (a fresh edge)" | "**Release** the enable, confirm `HmiTeleopRequest` reads `FALSE`, then assert it again" |

A note under the table records why 5.4.4's hold is deliberate, so nobody
"helpfully" releases the button and reintroduces the defect.

## A second defect in the same table, found while correcting the first

**The enable path had exactly the same shape as the reset path**, and it would
have failed at the CPU for exactly the same reason.

Step 5.4.5 leaves `HmiTeleopRequest` **asserted** (it says "release and re-assert
the enable"). Step 5.4.9 then said "Assert the enable (a fresh edge)" — but it is
already asserted, so there is no edge, `teleopRise` is `FALSE`, and teleop would
**not** return. The step would have failed against a correct program, in the same
way 5.4.7 did.

It is corrected in the same pass: 5.4.9 now says *release the enable, confirm it
reads `FALSE`, then assert it again*. And the pre-existing hole turned out to be
worth something once opened — 5.4.8's pass line now **reads the no-auto-resume
property off that very fact**: the latches clear on the fresh reset edge while
`ForkliftTeleopActive` stays `FALSE`, *because the enable has been asserted since
5.4.5 and a level that never fell produces no edge*. That is §6.7's conflation
demonstrated rather than argued, and it costs no extra step.

So the table now proves three things it previously only claimed: the reset is
refused while the cause stands, a hold across the cause clearing supplies no
edge, and an enable held across a reset does not restart the machine.

§6.7's existing sentence "demonstrated at 5.4.8 and 5.4.9" was checked and is
**more** accurate after the change than before it; no edit was needed there.
§12's creep-out row cites step 5.4.5, which keeps its number.

## §12 item 4

Now cross-references **`opcua-nodes.md` §10.12 item 7** by name, records that the
`HmiStartRequest` request was received and ruled an **owner decision, post-gate**,
and states why: a sixth request node moves the node count, the `ForkliftHmi` DB,
a start value (§10.9), the HMI's every-cycle write set (§10.8 H1) and this
program's enable edge together. It also now points at §11 steps 5.4.8 and 5.4.9
as where the conflation is demonstrated. This closes the cosmetic staleness I
flagged as the open question in the m4f-04b report.

## Note

The double was not touched, per the brief. Its K4 kernel already runs the
corrected order, so `plc/forklift/double/EVIDENCE_DOUBLE.md` is the executed
evidence that the corrected T5.4 sequence produces the results the table now
claims — on the double, which is a rehearsal stand-in and not the plant. The
owner's run against the CPU remains what closes the criterion.
