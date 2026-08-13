# Brief m5-02b — roadmap records ADR 0011 and closes D6(a)

```
gate:                M5
agent:               arch-docs
goal:                docs/roadmap.md reflects ADR 0011: the M5 row's open
                     map-data-path decision is closed, and the gate's settled
                     architecture is stated in one short paragraph.
invariants_touched:  none
inputs:              [docs/adr/0011-sensored-autonomy-architecture.md,
                      docs/adr/0010-milestone-restructure-forklift-first.md,
                      docs/roadmap.md]
deliverable:         docs/roadmap.md (revised)
done_when:           the M5 row's sentence deferring the map-view data path to
                     an ADR at M5 briefing is replaced by a citation of
                     ADR 0011 D4 (read-only monitoring plane); the current-gate
                     line reads M5 with M4 noted as closing on its recording
                     and the m4f-09 verification; one short paragraph states
                     the four settled rulings (onboard safety controller,
                     F-DI via the PLCSIM Advanced API under its feasibility
                     condition, motion envelope in autonomous mode, monitoring
                     plane) and the claim boundary (PLr targets only, no
                     achieved PL/SIL/PFH); the ADR 0010 D6 items that REMAIN
                     open — (b) anything beyond the emergency-button reading,
                     (c) the LLM attachment point, (d) M6's internal structure
                     — are still shown as open; nothing else changes.
forbidden:           [editing ADRs, PLAN.md, TODO.md, CLAUDE.md or README.md;
                      resolving any still-open D6 item; restating the M5 row's
                      criteria (a)-(e) in new words; claiming any achieved PL,
                      SIL or PFH; committing (the orchestrator commits)]
```

Do not commit. Leave docs/roadmap.md modified and write your report to
docs/reports/m5-02b-roadmap-adr-0011-note.md.
