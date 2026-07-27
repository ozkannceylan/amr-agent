gate:                M3
agent:               plc
goal:                Correct the PLC spec so the next TIA reader configures the namespace the way the tool actually works.
invariants_touched:  none
inputs:              [plc/demo-cell/SPEC.md, docs/briefs/m3-14-adr-0006-namespace.md (ADR 0006, cite by number), owner commissioning finding of 2026-07-27]
deliverable:         plc/demo-cell/SPEC.md, corrected in place
done_when:           Every instruction to set the namespace URI to urn:amr-agent:cell:plc is replaced by: name the server interface DemoCell; TIA Portal derives the URI as http://DemoCell automatically and the field is not editable; the bridge browses for http://DemoCell. The known locations are the §7 area (~line 227) and §10 step 6 (~line 841) — verify by whitespace-normalised search per LESSONS. The "namespace not found" troubleshooting note survives with the corrected URI. No other content changes.
forbidden:           [editing docs/ bridge/ or sim/, changing any tag or BrowseName, changing the 15-node count, touching sections unrelated to the namespace, claiming verification in TIA Portal — the owner's phase 0 finding is the verification and is cited as such]

The correction is the owner's own commissioning finding, made at the tool.
Where the spec explains why the URI matters (mismatch presents as "namespace
not found" at every connect), keep the explanation — it just names the wrong
URI today.

If the spec anywhere implies the URI is chosen rather than derived, fix that
implication too: the interface NAME is the design decision now, the URI
follows by rule.

Reporting: docs/reports/m3-17-namespace-plc-spec.md in the CLAUDE.md shape,
then lessons_candidates (may be none).
