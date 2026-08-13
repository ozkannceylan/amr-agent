# Brief m5r-08 — docs/interfaces/ gate-reference reconciliation per ADR 0010

```
gate:                restructure round
agent:               interface
goal:                the few live gate references in docs/interfaces/ name
                     their ADR 0010 gates; bridge-design's open items that
                     tracked the stale sim/README heading are updated against
                     the m5r-07 fix.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      docs/interfaces/bridge-design.md (§1 table, items 8 and
                      15 near lines 869/876), docs/interfaces/opcua-nodes.md
                      (§11 status prose), docs/reports/m5r-07-sim-docs-sweep.md
                      (for the corrected sim/README heading text),
                      the mapping block below]
deliverable:         docs/interfaces/ (gate references and the two open-item
                     entries only)
done_when:           bridge-design items 8 and 15 no longer assert "the
                     vehicle gate is M6" — they cite ADR 0010 (vehicle work
                     is M5, on the forklift) and item 15's status reflects
                     whether m5r-07 fixed the sim/README heading; opcua-nodes
                     §11's "M5 early" status prose is reconciled once with
                     ADR 0010's widened M5 (the early opening is now M5's own
                     opening wave; "nothing here closes M5" stays true and
                     stays written); all M4 references are untouched; no node,
                     access rule or design statement changes in substance; a
                     whitespace-normalised sweep for M5-M12 tokens and gate
                     names confirms no live stale reference remains in
                     docs/interfaces/.
forbidden:           [changing any node definition, access rule or design
                      ruling; editing files outside docs/interfaces/;
                      committing (the orchestrator commits); treating the
                      location list as exhaustive]
```

## Mapping (ADR 0010, owner-approved 2026-07-30)

M0-M4 keep their numbers. Old meaning → new gate: vehicle/navigation → **M5**
(on the forklift); safety layer → **M5**; VDA 5050 client → **M6**; fleet
manager → **M6**; PLC integration → **M6**; demonstration → **M7**; arm →
removed; Hermes/LLM → **M7**. The carried TODO note that "the M6 fleet-facing
interface name is a contract decision" now reads M6 under ADR 0010 as well
(old M9 → new M6) — no edit needed there, TODO is the orchestrator's.

Do not commit. Leave the files modified and write your report to
docs/reports/m5r-08-interface-docs-sweep.md (also uncommitted).
