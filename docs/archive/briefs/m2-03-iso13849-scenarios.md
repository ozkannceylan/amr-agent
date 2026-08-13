gate:                M2 (SRS extension; verification lands at M7 like the SRS itself)
agent:               safety-spec
goal:                A scenario document that demonstrates the ISO 13849 methodology end to end on this cell, strong enough to carry the project presentation.
invariants_touched:  none
inputs:              [docs/safety/SRS.md, docs/adr/0001-invariants.md, docs/adr/0004 (gate reordering, process-stop rule), CLAUDE.md §9, docs/interfaces/opcua-nodes.md]
deliverable:         docs/safety/PL-SCENARIOS.md
done_when:           At least 10 scenarios, each carrying: the hazard situation in one paragraph; the S/F/P risk-graph derivation to a required PLr with each parameter choice justified in one sentence; the SF from SRS.md that covers it; the category/architecture claim consistent with the SRS target line; a validation test in ISO 13849-2 style (what is stimulated, what must be observed, pass/fail); and the AT it maps to in the SRS traceability table. The owner can walk a presentation audience through any one scenario from hazard to validated reaction without leaving the document.
forbidden:           [claiming certification, validation to ISO 13849-2, SISTEMA results or certified components (the SRS honesty section is binding and this document must carry the same disclaimer); weakening or editing SRS.md itself beyond the traceability additions below; placing any safety function on the network (invariant 1); describing the demo cell's process e-stop as a safety function (ADR 0004); editing files outside docs/safety/ and the report]

## Why this exists

The owner has ruled this the centrepiece of the project presentation. The SRS
names PL d / Category 3 targets in one line and stops there, honestly. What is
missing is the demonstration of method: hazard → risk graph → PLr → function →
architecture → validation test. That chain, shown ten or more times on one
concrete cell, is what distinguishes a portfolio that understands ISO 13849
from one that name-drops it.

## Scenario design guidance

Scenarios are situations, not functions — one SF may carry several scenarios
and at least two SFs should. The 8 real SFs (SF-01..08, excluding the SF-09
pin) give the spine; reach ≥10 by covering different demand contexts, e.g.:

- e-stop demanded mid-handshake versus at rest (SF-01) — different hazard
  exposure, possibly different F parameter.
- Protective field violated at full speed versus in the warning-field-reduced
  state (SF-03/SF-04 interaction).
- Door opened while a vehicle is in the transfer zone versus while empty
  (SF-05/SF-07).
- Reset demanded with the hazard still present (SF-08) — the scenario where
  a wrong reset design kills someone; tie to wire-NC/program-NO and the
  edge-trigger rule of CLAUDE.md §9.
- A wire-break / fault-detection scenario, because Category 3 is a claim
  about single-fault behaviour and at least one scenario must exercise it.

These are suggestions, not the list. You own the set; justify its coverage in
a closing section (every SF touched at least once, every parameter of the risk
graph exercised across the set, single-fault behaviour demonstrated).

## Boundaries that hold

- The demo cell's e-stop is a process stop (ADR 0004). Scenarios live on the
  F-CPU and vehicle safety layer of the SRS, not on the M3 demonstration cell.
  Where a scenario touches equipment the demo cell also models, say explicitly
  that the safety instance is the F-CPU one.
- Safety never traverses the network (invariant 1). Any scenario whose
  reaction would require MQTT/OPC UA to act is wrongly designed — the network
  may only ever *report* the state afterwards.
- SF-09 remains not-a-safety-function. If a scenario involves supervision
  loss, its reaction is the controlled stop of invariant 2, and the document
  says so without promoting it.

## Traceability

You may extend the SRS §4 table with a Scenarios column or an additional
mapping table inside PL-SCENARIOS.md (prefer the latter — the SRS stays
untouched except for, at most, one pointer line to this document). Every
scenario ID (SC-01…) maps to exactly one SF and at least one AT.

## Reporting

`docs/reports/m2-03-iso13849-scenarios.md` in the CLAUDE.md report shape, then
`lessons_candidates` (may be "none"). State the scenario count, the SF
coverage, and any SRS inconsistency you found but did not fix.
