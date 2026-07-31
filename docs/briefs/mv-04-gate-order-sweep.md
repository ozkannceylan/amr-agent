# Brief mv-04 — sweep the gate order after M8

```
gate:                cross-cutting
agent:               infra (owner-approved 2026-07-31)
goal:                every live document that states the gate set agrees with
                     docs/roadmap.md, which now runs M0 to M8.
invariants_touched:  none
inputs:              [docs/roadmap.md (the single source for gate numbering),
                      docs/adr/0013-vendor-portability-gate.md,
                      docs/reports/mv-03-roadmap-round.md (what changed),
                      CLAUDE.md section 6, README.md, docs/TODO.md,
                      docs/PLAN.md]
deliverable:         the gate set aligned wherever a live document states it
done_when:           a FRESH whole-repository inventory — not a reuse of any
                     earlier round's file list — finds every live statement of
                     the gate set or gate order and each is either consistent
                     with roadmap.md or corrected; CLAUDE.md section 6's table
                     carries the M8 row; the README milestone table carries it
                     in the owner's short-row style; docs/TODO.md's header
                     stops calling M4 the open gate and the m5r round in
                     flight, both of which contradict roadmap.md and PLAN.md;
                     and the report lists every file inspected, not only those
                     changed.
forbidden:           [editing docs/adr/**, docs/briefs/**, docs/reports/** or
                      docs/LESSONS.md (the historical record); renumbering any
                      gate — M8 is assigned and M0-M7 are unchanged; restating
                      any criterion in new words; claiming any achieved PL,
                      SIL or PFH; committing (the orchestrator commits)]
```

## Why the inventory must be fresh

A lesson from yesterday: three consecutive renumbering rounds each swept
outward from `roadmap.md` using the previous round's file list, and CLAUDE.md
section 6 was missed by all three — it was still carrying the original
pre-ADR-0004 order when it was finally read. Start from a whole-repository
search and include the contract file explicitly.

Sweep by subject with whitespace normalised: gate tokens M0 through M8 word
bounded, the gate names, and phrases that state a RANGE — "M0 to M7", "eight
gates", "the last gate", "after M7" — because a range statement goes stale
without any single number being wrong. Note that brief and report filenames
carry round numbers, not gate numbers, and are not gate references; and
CLAUDE.md's `not M12` is a PLC memory-marker example, not a gate.

## What M8 is, in one line for the tables

Vendor portability — a second, Beckhoff/TwinCAT implementation of the PLC
layer, proven by the same unmodified clients and the same scenarios running
against both controllers in separate sessions. It sits after M6 and M7 and
outside the four embedded showcase recordings. Take the wording from
`roadmap.md`; do not invent a summary of your own.

## One correction to carry

`docs/TODO.md`'s header predates two gates. It should say what is true: M5 is
the open gate, M4 is closing on the owner's recorded showcase and the m4f-09
verification, and the m5r restructure round is closed. Do not rewrite the
queues beneath it — only the header statement that is now false.

Do not commit. Leave files modified and write your report to
docs/reports/mv-04-gate-order-sweep.md.
