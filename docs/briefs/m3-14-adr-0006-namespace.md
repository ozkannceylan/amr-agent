gate:                M3
agent:               arch-docs
goal:                An ADR recording that OPC UA namespace URIs are tool-derived per server interface, replacing the designed URN.
invariants_touched:  none (namespace model is not a §2 invariant; it is an architecture decision requiring a record)
inputs:              [docs/adr/ (numbering), docs/interfaces/opcua-nodes.md §2 and §9, plc/demo-cell/SPEC.md §10 step 6, owner commissioning finding of 2026-07-27]
deliverable:         docs/adr/0006-tia-derived-namespace-uri.md (verify 0006 is the next free number)
done_when:           The ADR records: Context — TIA Portal derives a server interface's namespace URI as http://<interface name>, the field is not editable, so the designed urn:amr-agent:cell:plc cannot exist on a TIA server interface; found at commissioning phase 0. Decision — the URI is http://DemoCell, one namespace per server interface, and the shared-namespace assumption for the future fleet-facing interface is void: each future server interface carries its own http://<name> URI. Consequences — what becomes harder (no single shared namespace across interfaces; clients resolve per-interface URIs) and easier (the URI is derivable from the interface name by rule, never configured wrongly). Alternatives — companion-specification XML import, rejected as disproportionate toolchain cost for zero functional gain; hardcoding the namespace index, rejected long ago and unchanged (§2 browse-by-URI stands).
forbidden:           [editing any other document (the corrections are m3-15/16/17), editing an accepted ADR, describing this as a safety-relevant change, marking the ADR accepted without the owner's authorship noted — the finding and decision are the owner's, dated 2026-07-27]

Status may be recorded as accepted: the decision is the owner's own, made at
the tool, and communicated verbatim. Cite the finding as the owner's
commissioning correction, not an agent inference.

Reporting: docs/reports/m3-14-adr-0006-namespace.md in the CLAUDE.md shape,
then lessons_candidates (may be none).
