gate:                M3
agent:               bridge
goal:                Point the bridge, the test double and the allowlist checker at the real namespace URI http://DemoCell, and prove the loop still closes.
invariants_touched:  none
inputs:              [bridge/config/bridge.yaml, bridge/test_double/plc_test_double.py, bridge/tools/check_write_allowlist.py, bridge/test_double/README.md, docs/briefs/m3-14-adr-0006-namespace.md (ADR 0006, cite by number)]
deliverable:         bridge/ updated to http://DemoCell throughout its live configuration and stand-ins; historical evidence untouched
done_when:           opcua.namespace_uri in bridge.yaml is http://DemoCell; the test double registers http://DemoCell; check_write_allowlist.py resolves http://DemoCell; the double's README states the URI and cites ADR 0006; a live headless run proves the bridge resolves the namespace against the double and the allowlist check passes; and no bridge logic changed.
forbidden:           [any logic change (the constants are contract representation, not logic — if a change requires touching control flow, stop and report), editing docs/interfaces/ plc/ or sim/, altering any number or line in the evidence files' recorded runs, hardcoding a namespace index anywhere]

## Scope note — recorded deviation

The owner's instruction was "config only, no code change". The orchestrator
widened it: the test double and the allowlist tool carry the URN as constants,
and a yaml-only change would break the committed loop at connect ("namespace
not found") because the double must mirror the real server. The three changes
are one contract update. Your report states this deviation and its reason in
open_questions so the owner sees it.

## Verification

One bounded headless run (cell not required — double + bridge suffices for
namespace resolution; include the cell only if the existing README procedure
makes that cheaper), both transports isolated if anything else runs, foreground,
quoting: the "namespace http://DemoCell resolved to index N" log line, the
startup rule line, and check_write_allowlist RESULT. git status must end clean
apart from your edits (latency-latest.csv is ignored).

Evidence files record runs made against urn:amr-agent:cell:plc; they are
history and stay byte-identical. If you believe a scope note is needed
anywhere, propose it in the report rather than adding it.

Reporting: docs/reports/m3-16-namespace-bridge.md in the CLAUDE.md shape, then
lessons_candidates (may be none).
