gate:                M3
agent:               interface
goal:                Correct the namespace URI and record the per-interface namespace rule in the interface documents.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md, docs/interfaces/bridge-design.md, docs/briefs/m3-14-adr-0006-namespace.md (ADR 0006, being authored in parallel — cite by number)]
deliverable:         docs/interfaces/opcua-nodes.md and docs/interfaces/bridge-design.md, corrected in place
done_when:           opcua-nodes.md §2 states the URI http://DemoCell, that TIA derives it as http://<interface name> with the field not editable, and the one-namespace-per-server-interface rule; §9 (the §165 area asserting the future fleet-facing interface shares the URI) states instead that each server interface carries its own derived URI and the sets remain unmerged; bridge-design.md's two URN occurrences (§4 namespace row, §10/test-double row — verify locations by search) read http://DemoCell; and no other content changes.
forbidden:           [changing any measured number, editing bridge/ or plc/, restructuring sections, re-opening settled items, changing the browse-by-URI rule itself — resolution by URI at session establishment stands, only the URI value changes]

The owner's commissioning finding, verbatim basis: TIA Portal derives a server
interface's namespace URI as http://<interface name> and the field is not
editable. The spec value urn:amr-agent:cell:plc cannot exist on a TIA server
interface. The actual URI is http://DemoCell. One namespace per server
interface; the shared-namespace assumption for the future fleet-facing
interface is void.

Cite ADR 0006 at both correction sites. Evidence files retaining the URN are
historical records of runs against the test double as it then was — do not
touch them, and do not "fix" any document that quotes a past run.

Per LESSONS: verify the occurrence list by whitespace-normalised search over
both files rather than trusting the enumeration above.

Reporting: docs/reports/m3-15-namespace-interface-docs.md in the CLAUDE.md
shape, then lessons_candidates (may be none).
