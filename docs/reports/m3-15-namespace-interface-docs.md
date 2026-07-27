# m3-15 — namespace URI correction in the interface documents

brief:               docs/briefs/m3-15-namespace-interface-docs.md
status:              done
files_changed:       docs/interfaces/opcua-nodes.md, docs/interfaces/bridge-design.md
invariants_touched:  none
open_questions:      none
next_suggested:      Verify m3-16 (bridge) and m3-17 (PLC spec) land the same URI, so config, test double and TIA instructions agree with these two documents.

## What changed

Four live occurrences, verified by whitespace-normalised search over both files
(not by the brief's enumeration). No wrapped occurrence existed. All four now
read `http://DemoCell` and cite ADR 0006.

| # | Location | Before | After |
|---|---|---|---|
| 1 | `opcua-nodes.md` §2, namespace declaration | `urn:amr-agent:cell:plc` | `http://DemoCell`, plus a new paragraph: TIA derives the URI as `http://<interface name>`, the field is not editable, one namespace per server interface (ADR 0006) |
| 2 | `opcua-nodes.md` §9 preamble | "Both live on the same server under the same namespace URI `urn:amr-agent:cell:plc`" | The §9 nodes live on the `DemoCell` interface, URI `http://DemoCell`; a fleet-facing interface is a separate server interface with its own derived URI; the sets remain unmerged (ADR 0006) |
| 3 | `bridge-design.md` §3, Namespace row | browse for `urn:amr-agent:cell:plc` | browse for `http://DemoCell`; rule unchanged, value only; TIA-derived and not editable (ADR 0006) |
| 4 | `bridge-design.md` §10, test double | "exposing namespace `urn:amr-agent:cell:plc`" | "exposing namespace `http://DemoCell`" (ADR 0006), with the note that the double matches the URI so browse-by-URI resolves identically against it and against PLCSIM |

Brief location note: the brief placed the second bridge-design occurrence at
"§4 namespace row"; the search found it at §3 (*Session and address-space rules*).
The count of two was correct.

## Deliberately not touched

URN occurrences that are history, per the brief:

| File | Why |
|---|---|
| `bridge/EVIDENCE_LATENCY.md` (3 occurrences, incl. two captured log lines) | Record of runs against the double as it then was |
| `docs/reports/m3-06-verify.md` (1) | Quotes a past run's log line |
| `docs/LESSONS.md` (1) | The correction entry itself |
| `docs/briefs/m3-14/15/16/17` | Brief text stating the finding |

Live URN occurrences outside this brief's scope, owned by the parallel briefs
and out of this agent's write access: `bridge/config/bridge.yaml`,
`bridge/test_double/plc_test_double.py`, `bridge/test_double/README.md`,
`bridge/tools/check_write_allowlist.py` (m3-16); `plc/demo-cell/SPEC.md`
§7 and §10 step 6 (m3-17).

## Unchanged by design

- Browse-by-URI at session establishment; the index is still never hardcoded.
  Only the URI value changed.
- Every BrowseName, folder path, type, access level, cadence and measured number.
- Section structure in both documents.

## lessons_candidates

- The `DemoCell/` folder name and the server interface name are now the same
  string for a reason that is no longer cosmetic: the interface name *is* the
  namespace URI. Renaming the TIA server interface silently changes the URI the
  bridge browses for, and the failure is a clean "namespace not found" at every
  connect. Candidate rule: treat the server interface name as a contract value
  under the same change discipline as a BrowseName.
- A brief that cites a section number for an occurrence should cite it as a hint
  only. Here §4 was cited and the occurrence was in §3; the whitespace-normalised
  search found it regardless, which is the existing LESSONS rule working.
