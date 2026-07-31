# Report mv-02 — ADR 0013: vendor portability as a gate after the main line

```
brief:               docs/briefs/mv-02-adr-0013-vendor-portability-gate.md
status:              done
files_changed:       [docs/adr/0013-vendor-portability-gate.md,
                      docs/reports/mv-02-adr-0013-vendor-portability-gate.md]
invariants_touched:  none. ADR 0013 records the mv-01 §F.6 finding that all
                     thirteen were walked and none needs to change; it states
                     that finding rather than repeating the walk. Gate order is
                     not an invariant. No existing gate criterion is changed.
open_questions:      four, listed below
next_suggested:      issue the roadmap brief that numbers this gate and lands
                     its row, once M6 and M7 are settled
```

## What was written

`docs/adr/0013-vendor-portability-gate.md`, **status accepted (2026-07-31),
owner-approved on that date**, in CLAUDE.md §8 format (Status, Context, Decision,
Consequences, Alternatives) on the ADR 0010 house pattern: a "what this ADR does"
preamble, numbered decisions D1–D5, harder/easier consequences with an explicit
"does not decide" list, and rejected alternatives.

The five owner rulings of 2026-07-31 are recorded as D1 (a gate of its own, after
M6 and M7), D2 (scope and the closing criterion), D3 (the claim stated exactly),
D4 (startup selection, immutable for the session), D5 (stage-0 probe as hard
precondition, drift check as a deliverable).

**The gate is given no number**, and the ADR says so in its preamble: numbering,
the roadmap row and the final criterion wording are the separate roadmap brief's,
per LESSONS 2026-07-30 (roadmap.md is the single source for gate numbering).

`docs/reports/mv-01-beckhoff-portability-research.md` is cited as the evidence
base throughout — by section, with its verification date (2026-07-31), its
per-claim grades and the pinned TF6100 manual version (v1.4.0, 2025-09-16) — and
its findings are not restated as the ADR's own evidence. Nothing mv-01 marked
`[snippet]` or unverified is stated as fact: the host-name-coupled namespace URI,
install co-residency, the reported OPC UA types and the write-form acceptance all
appear only inside D5's table of **unread tool facts**. The trial licences are
described as **7-day trial licences for commercial products, renewable per the
vendor's licensing pages**, with an explicit rule in D5 that no artifact produced
under this gate calls them "free".

## The discipline note, discharged

The closing criterion (D2) has five items, all written over the **standard
program**: (a) both conformance runs green with byte-identical clients, (b) the
M4 forklift scenario procedures T5.1–T5.6 run against TwinCAT with both evidence
sets kept and environment-qualified, (c) startup-selected controller with the
server-reported identity visible in every recorded run, (d) the drift check
passing against `opcua-nodes.md`, (e) the Siemens-only safety asymmetry stated
publicly with the TE9100 status quoted and dated.

The named fallback — **TE9100 still unreleased when the gate opens** — is then
tested against that criterion **in the same breath**, item by item, in a table in
D2. It satisfies all five: the safety group is absent, which is already a
tolerated server state because the HMI declares it optional and greys it
(mv-01 §B.3); the safety scenarios are not criterion items; items (c)–(e) are
vendor-neutral, and (e) *is* the fallback stated in public. The consequences say
in as many words that this construction is deliberate, name the ADR 0011 D2
failure it responds to, and record what would have gone wrong had the safety
mirror been made a conditional criterion item — which is also carried as a
rejected alternative.

## Notes for the orchestrator

- `docs/roadmap.md`, `docs/PLAN.md` and `docs/TODO.md` currently contain **no
  mention** of this work (checked). They do not *disagree* with ADR 0013 — they
  predate it — but they will once the gate exists in name only here. The roadmap
  brief must land the row, and TODO should gain the stage-0 probe as a blocking
  item, in the same round.
- ADR 0013 discharges only **part** of the ADR mv-01 §F.7 required: items 3 and 4
  (safety scope, startup selection) are D2 and D4 here; items 1 and 2 (the
  TwinCAT namespace URI and the symbol layout) are tool-derived and are
  explicitly deferred to the post-probe ADR. A second vendor ADR is therefore
  still required before any vendor specification or client configuration exists.
- Nothing outside `docs/adr/` and `docs/reports/` was touched; no other ADR and
  no tracking file was edited. Not committed.

## Open questions

1. **The gate's number and row.** Assigned by the roadmap brief once M6 and M7
   are settled. Until then no gate table names this gate.
2. **Whether the gate carries a showcase recording** in ADR 0007's sense, beyond
   the committed evidence the criterion requires. Left to the roadmap brief.
3. **mv-01 §G items 2, 4 and 5 remain unruled**: the directory shape for the
   second vendor's sources, the both-endpoints-alive launcher guard, and whether
   a TE9100 release triggers a re-probe of the safety question.
4. **Which component owns the controller-selection datum** (D4 defers it to the
   gate's own briefs; invariant 10 binds whichever it is).
