# Brief m5a-01 — ADR 0009: early cell-scope opening of the safety gate

```
gate:                M5 (early, cell-scope) — via ADR
agent:               arch-docs
goal:                ADR 0009 records, as accepted, the owner ruling of
                     2026-07-29: the safety gate's cell-scope core opens early
                     on the forklift twin, fallback-safe, with M4 unchanged.
invariants_touched:  none changed — invariant 1 is honoured by construction
                     (the safety demand forms inside the F-CPU; the network
                     carries process consequences and read-only mirrors only)
inputs:              [docs/adr/0008-*.md, docs/roadmap.md M4 and M5 rows,
                      docs/safety/SRS.md sections for SF-01/SF-07/SF-08,
                      the decisions block below]
deliverable:         docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md
done_when:           the ADR states the decisions with consequences and
                     rejected alternatives; the gate-discipline exception (M5
                     partially opened before M4 is verified closed) is recorded
                     as an owner ruling with the fallback rule; the M4
                     criteria are explicitly unchanged; status accepted,
                     owner-approved 2026-07-29.
forbidden:           [editing other ADRs, roadmap.md (separate brief), code,
                      any SRS change, mentioning any deadline or presentation]
```

## Decisions to record (owner-approved 2026-07-29)

1. The owner replaced the commissioned CPU with a 1513F-1 PN
   (6ES7 513-1FM03-0AB0), owner-executed in TIA; PLCSIM Advanced
   communication verified. This answers part of the ADR 0007 tool question;
   the remaining feasibility items (Safety Advanced licence compile, F-runtime
   group reaching RUN) are the first checkpoint of this early opening and its
   abort-to-fallback trigger.
2. Scope of the early opening — cell-scope only, on the forklift twin:
   SF-01 (e-stop chain), SF-08 (monitored reset, cell instance) and the SF-07
   zone-monitoring pattern instantiated as a marked arena zone. The onboard
   vehicle chain (SF-02/03/04) stays at its own gates, stated explicitly.
3. Architecture of the coupling: the F-program forms the safety demand
   entirely inside the CPU; the standard program's teleop permissive consumes
   the F-demand (F-to-standard within one CPU); OPC UA carries process
   consequences plus a read-only Safety/ mirror group written by the standard
   program for display — no client write can create, prevent or clear a
   safety reaction; the mirrors are diagnostics, not the safety path.
4. Fallback rule: the M4 teleop demonstration stands alone if the F-layer is
   not ready; nothing of M4 depends on this opening; the early-opened work
   continues as ordinary M5 content afterwards.
5. ISO 13849 basis: the existing SRS and PL scenario derivations are the
   reference; the twin demonstrates the acceptance-test logic and names PL
   targets from those documents; simulation demonstrates logic, it does not
   claim achieved PL — the wording discipline of the M2 documents carries.

Rejected: implementing teleop process logic inside the F-program (invariant
7; ADR 0008 D3 stands); a network-carried safety input for the zone (invariant
1 — for the demonstration the F inputs are driven at the simulated F-I/O /
engineering interface, stated honestly).

Git: repo-local owner identity; pathspec-scoped commit of exactly the ADR plus
your report docs/reports/m5a-01-adr-0009-early-safety.md; message style
`docs(adr): open the cell-scope safety layer early on the forklift twin`.
