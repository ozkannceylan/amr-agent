# Report m4f-04b — plc/ prose alignment with the steer ruling

```
brief:               docs/briefs/m4f-04b-spec-ruled-references.md
status:              done
files_changed:       [plc/forklift/SPEC.md, plc/README.md,
                      docs/reports/m4f-04b-spec-ruled-references.md]
invariants_touched:  none
open_questions:      one, cosmetic — see below
next_suggested:      m4f-06 (bridge forklift slots) or m4f-07 (HMI); plc/ has no
                     open item left that blocks either
```

Prose only, as briefed. The ruling of `ae93667` ratifies what m4f-04 already
built, so **nothing executable moved**: the §7 SCL block is byte-identical apart
from one comment — 118 statement lines before, 118 after, identical with comments
stripped — and no constant, tag, node, start value, watch-table row or test step
changed. The owner can keep building from the document mid-edit.

## The three SPEC sites, found by search rather than by trusting the list

A whitespace-normalised sweep of `plc/` for the steer-question language
(`contradict`, `unresolved`, `not resolved`, `rules the other way`,
`SteerAngleHold`, `argues for`, `exemption`) returned **exactly the three sites
the brief named** and no fourth. The two other places that mention the centring
wheel — the §9 Group 3 watch-table row and step 5.1.8 — describe the behaviour,
not the question, and were already correct under the ruling, so both were left
alone.

| Site | Was | Is |
|---|---|---|
| §6.4 subsection | "The steer setpoint, and a contradiction in the contract document", with a three-row table of the conflicting §10.6 statements and a closing sentence saying the contradiction "is **not** resolved by this document's choice" | "The steer setpoint — ruled, and the ruling is what is built here". Cites §10.6 and P5 as rewritten by `ae93667`, quotes the withdrawal of the exemption, and states that the ruling ratifies the existing specification. The conflict table is gone; the one-branch alternative stays, reworded as "were it ever ruled back" |
| §7 SCL comment | "§10.6's table row argues for holding the last angle while its own gating paragraph … require the zero; the zero is implemented and the contradiction is documented in §6.4" | "RULED: §10.6 and P5 require all three setpoints, the steer angle included, to take `0.0` … the earlier exemption for steering is withdrawn", plus the ruling's own third ground — all three assignments run in the same call, so the wheel is re-aimed on a machine whose traction setpoint has already gone to `0.0` |
| §12 item 2 | "§10.6 contradicts itself … raised for correction in the interface document; whichever way it is ruled, one of the two statements there must go" | "**Closed by the ruling of 2026-07-29** (commit `ae93667`) … the ruling ratifies what §6.4 and §7 already build — no statement, constant, tag, start value or node moved on either side" |

`plc/README.md` gained the `forklift/SPEC.md` Contents row and one paragraph
under the existing PROCESS-stop section, stating that the obstacle stop, the
fork-height speed cap and the fork soft travel limits are standard-program
process interlocks implementing no safety function — SF-02, SF-03, SF-04, SF-07
and SF-09 named explicitly, as ADR 0008 D3 names them — with no SIL or PL claim
and no F-CPU on that plant.

## Open question

One cosmetic staleness, left alone because the brief's `done_when` says nothing
else changes and the owner may be mid-build. **SPEC §12 item 4 still reads as a
pending request**: "Requested of `docs/interfaces/`: an `HmiStartRequest` node…".
That request has since been *received and recorded* as `opcua-nodes.md` §10.12
item 7 (owner decision, post-gate, because a sixth request node moves the node
count, the `ForkliftHmi` DB, a start value and the HMI's write set together). The
sentence is still true — the node does not exist and the conflation still stands
— it merely lacks the cross-reference. One clause, whenever `plc/` is next
opened; not worth a commit of its own.

Two other §12 items were checked against the same commit and need no edit. Item 1
(`TRACTION_SPEED_MAX` = 1.00 m/s) is phrased as a live one-directional constraint
— raise the cap only by re-deriving the window first — which is exactly how
`opcua-nodes.md` §10.12 item 4 now records it as closed. Item 3 (no
`ForkliftDriveFault`) is quoted approvingly by §10.12 item 3 as the PLC-side
confirmation of the gap, and stays open on both sides.
