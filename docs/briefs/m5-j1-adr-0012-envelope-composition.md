# Brief m5-j1 — ADR 0012: envelope composition, and the D1 disclosures

```
gate:                M5
agent:               arch-docs
goal:                ADR 0012 refines ADR 0011 D3's envelope so it cannot
                     collide with the fleet manager's ownership at M6, and
                     lands the D1 disclosures the judge found missing.
invariants_touched:  none changed. The ADR exists precisely to KEEP
                     invariants 5 and 10 intact — it removes a datum the PLC
                     was about to co-own with the fleet manager.
inputs:              [docs/adr/0011-sensored-autonomy-architecture.md (D1, D3
                      — read, never edit),
                      docs/reports/m5-judge-architecture-review.md findings 3
                      and 4, CLAUDE.md invariants 5, 6 and 10,
                      docs/roadmap.md rows M5 and M6,
                      the rulings block below]
deliverable:         docs/adr/0012-envelope-composition.md, plus the D1
                     disclosure sentences in docs/roadmap.md and docs/PLAN.md
done_when:           the ADR states the two decisions below with context,
                     consequences and rejected alternatives; it is explicit
                     that it REFINES ADR 0011 D3 rather than superseding
                     ADR 0011 as a whole, and names exactly which clause it
                     replaces; the two M6-scaling facts named in decision 2
                     are recorded as UNVERIFIED with what would settle them;
                     roadmap.md and PLAN.md each carry the D1 simulation-
                     artifact disclosure in one sentence; status reads
                     accepted with the owner-approval date 2026-07-30.
forbidden:           [editing ADR 0011 or any other accepted ADR; editing
                      TODO.md, CLAUDE.md or README.md; deciding the F-I/O
                      fallback question (deliberately open pending m5-03);
                      claiming any achieved PL, SIL or PFH; committing (the
                      orchestrator commits)]
```

## Decisions to record (owner-approved 2026-07-30, on the judge review)

1. **The envelope's third element is a station permit, not a zone permit.**
   ADR 0011 D3 composed the autonomy envelope as "a motion enable, a speed
   ceiling and a zone permit". The third element is replaced by a **fixed
   equipment / station permit** — the PLC's statement that the equipment it
   owns is ready for the vehicle to act on it (door open, conveyor ready,
   charging bay clear, station handshake satisfied). Rationale: invariant 5
   gives zone reservation and traffic to the fleet manager, so a PLC-issued
   zone permit would create a second owner for one datum at M6 and break
   invariant 10. The PLC keeps what is genuinely its own — the state of the
   fixed equipment and its interlocks (invariants 5 and 6 unchanged) — and
   traffic-level permission stays with the fleet manager where M6 will put
   it. The enable and the speed ceiling are unchanged.
   Record the consequence: at M6 a vehicle's motion is bounded by BOTH a
   PLC station permit and a fleet-manager zone reservation, which are
   different data with different owners, and no document may conflate them.

2. **The D1 disclosures.** ADR 0011 D1 declared the forklift's F-runtime
   group to be the vehicle's onboard safety controller, with the single
   hosting 1513F-1 named a simulation artifact to be disclosed. The judge
   found that disclosure present in the ADR but absent from roadmap.md and
   PLAN.md. Land one sentence in each. Record additionally, as an explicit
   consequence rather than a claim: because one simulated CPU hosts what the
   architecture calls per-vehicle safety, the cell and the vehicle chains
   share an execution substrate in simulation, which the B4 property
   ("the vehicle chain does not depend on the cell") does not hold at in the
   simulation's execution layer even though it holds architecturally.
   And record as **UNVERIFIED**, with what would settle each: (a) how many
   F-runtime groups an S7-1500 F-CPU supports, which bounds how many vehicle
   safety instances one simulated CPU can carry, and (b) the PLCSIM Advanced
   instance budget available to this project. Both are M6-scaling facts the
   ADR 0011 evidence table did not pin, and the four-forklift claim rests on
   them.

## Alternatives to record as rejected

- Leaving "zone permit" in place and separating the two owners at M6: the
  collision is cheap to resolve now and expensive once the fleet manager,
  the VDA 5050 subset and the station handshake all reference a term that
  means two things.
- Dropping the envelope's third element entirely: the PLC's legitimate say
  over its own fixed equipment would vanish from the envelope and would have
  to be reintroduced at M6 anyway.
- Editing ADR 0011 in place: accepted ADRs are never edited in this project.

## Git

Repo-local owner identity is set. Pathspec-scoped commits. Report to
docs/reports/m5-j1-adr-0012-envelope-composition.md.
Do not commit — the orchestrator commits.
