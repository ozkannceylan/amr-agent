# Report m4f-05b — bridge-design §1.1 steer-gating reason

```
brief:               docs/briefs/m4f-05b-bridge-design-steer-reason.md
status:              done (deliverable) — done_when clause 2 is UNMET, see below
files_changed:       [docs/interfaces/bridge-design.md,
                      docs/reports/m4f-05b-bridge-design-steer-reason.md]
invariants_touched:  none
open_questions:      1 — the sweep found two MORE false statements in this file,
                     both outside the deliverable and on this brief's forbidden
                     list. Drop-in text below; they need one more brief
next_suggested:      m4f-05c: bridge-design.md §4.7 row 15 and §8 rule N4, the
                     same one-clause correction, same reason
```

## Done

`docs/interfaces/bridge-design.md` §1.1, forklift no-logic table, the
`ForkliftSteerAngleRef` row. Verdict and owner column **unchanged** — the bridge
still does neither the clamp nor the centring, owner still PLC. Only the middle
cell's reason changed, to the drop-in text from m4f-01b:

> Both are process decisions the PLC makes and states: the clamp is the PLC's, and
> so is the centring — **all three setpoints, the steer angle included, are driven
> to `0.0` in the mandatory `ELSE` when the interlocks fail** (§10.6), which is
> precisely why the transport must not do it (§10.7)

One clause, one row, one table. Nothing else in §1.1 was touched.

## The sweep — clause 2 of done_when is not met

Whitespace-normalised over the whole file, twelve patterns including a bare
`[Ss]teer` over every occurrence of the node name. **Two more statements depend on
the withdrawn exemption, and both are outside this brief's deliverable and
explicitly on its forbidden list ("any other bridge-design.md change"). I did not
edit them.** Both make a factual claim about PLC behaviour that ae93667 reverses,
and the second cites §10.6 by name:

**1. §4.7, forklift signal map, row 15** — Conversion cell currently reads
"widening, rad unchanged. **No clamp** — the PLC clamps to the mechanical range,
and deliberately does *not* centre the steer on a stop". Drop-in:

> widening, rad unchanged. **No clamp and no centring** — both are the PLC's: it
> clamps to the mechanical range and drives the angle to `0.0` in the
> interlock-failed `ELSE`, like the other two setpoints (§10.6)

**2. §8, reconnect rule N4** — currently ends "Note that `ForkliftSteerAngleRef`
is deliberately *not* driven to zero by the PLC on a stop (`opcua-nodes.md`
§10.6): the bridge carries whatever angle it reads, and that too is the PLC's
decision". N4's argument survives intact; only its example inverts. Drop-in:

> Note that `ForkliftSteerAngleRef` **is** driven to `0.0` on a stop like the other
> two (`opcua-nodes.md` §10.6), so a reconnect into a stopped machine carries a
> centred steer: the bridge publishes whatever angle it reads, and that too is the
> PLC's decision

Until these land, this file contradicts `opcua-nodes.md` §10.6 in two places while
agreeing with it in a third — the same two-same-gate-documents-disagree shape that
failed a gate on 2026-07-26.

Not a dependency, checked and left alone: §7.4's "drive **every motion setpoint**
to `0.0` in the mandatory `ELSE` of §10.6" is true as written and cites no
exemption; it merely wants "all three setpoints" for the reason §10.8 P5 was
retightened. Cosmetic, and forbidden here.

## The lesson this cost

**My own m4f-01b sweep named §1.1 and only §1.1, and this brief's `done_when` was
written from that enumeration.** It missed these two because I swept for the
*phrasings I remembered from the deleted row* ("steer setpoint is a position",
"forcing it to centre", "steering is deliberately") and these two rows say
"does *not* centre the steer on a stop" and "*not* driven to zero by the PLC". The
patterns that caught them were the bare node name over the normalised file.

The rule that follows, offered for LESSONS.md: **sweep by subject, not by
remembered phrasing** — enumerate every occurrence of the node, tag or value name
first, then read each one for dependency. A withdrawn statement is re-stated in the
words of whoever quoted it, not in the words it was deleted in. This is LESSONS
2026-07-27 ("never let an enumerated list read as exhaustive") repeating one layer
up: the enumeration that read as exhaustive this time was **in a report**, and it
propagated into a brief's `done_when`.

## Open questions

1. **§4.7 row 15 and §8 N4 need a brief.** Both are inside `docs/interfaces/` and
   inside my write access, forbidden only by this brief. The drop-in text above is
   ready to apply as-is; it is two cells and no structural change.
