# Brief m3-23 — verify the commissioning-correction chain

gate:                M3
agent:               verifier
goal:                the phase-0 commissioning corrections (m3-18 to m3-22) are independently verified and the owner-executed remainder of M3 is stated explicitly
invariants_touched:  none
inputs:              [docs/reports/m3-18* to m3-22*, docs/briefs/m3-18* to m3-22*, docs/interfaces/opcua-nodes.md, docs/interfaces/bridge-design.md, bridge/, docs/PLAN.md, docs/TODO.md, docs/LESSONS.md, docs/roadmap.md, git log since 8d0ba7b]
deliverable:         docs/reports/m3-23-verify-commissioning.md
done_when:           every check below carries an explicit pass or fail with evidence, and the report ends with a plain statement of what remains owner-executed before M3 can close
forbidden:           [modifying any file except the deliverable report, committing, connecting to the live PLCSIM endpoint at 192.168.53.1 (owner-executed), issuing follow-up work yourself]

## Checks

1. **Cross-document consistency.** opcua-nodes.md §2.1 and bridge-design.md
   §3.1 wrote the browse-path rules concurrently from the same brief text —
   diff them for contradiction (path, namespace URIs, qualification rules).
2. **No surviving stale claims.** Whitespace-normalised sweep across
   docs/interfaces/ and bridge/ for: DemoCell directly under Objects, a
   requested session parameter treated as granted, "exactly 15 nodes" not
   scoped to the interface, "clamp" where the revision can go both ways.
3. **Conformance evidence re-run.** Re-run the m3-21 connect-conformance
   harness from committed instructions (WSL, test double only) and confirm
   the committed EVIDENCE_CONNECT.md claims reproduce: both-URI resolution,
   keep-alive derived from a grant below AND above the request.
4. **Config against the commissioned facts.** bridge/config/bridge.yaml:
   both namespace URIs exact, per-element qualified interface path, the
   endpoint value clearly a test-double placeholder the owner swaps.
5. **Tracking coherence.** PLAN.md, TODO.md, roadmap.md and the report
   directory agree: every m3-14 to m3-22 brief has a report, closed items
   absent from TODO, PLAN's brief list complete, gate still open.
6. **Attribution.** Commits since 8d0ba7b: author fields, messages, and no
   AI/tooling mention anywhere in repository content added this session.
7. **Layer boundaries.** m3-18/19/22 touched only docs/interfaces/; m3-20/21
   only bridge/ (reports aside); the bridge gained no process logic
   (thresholds, latches, timers beyond connection keep-alive, sequencing).

End with: the exact owner-executed list (OB30 build, PLCSIM run, watch-table
evidence for gate items a and b, EVIDENCE_LATENCY.md Section B including the
scan-cycle and invariant-8 confirmations, EVIDENCE_SIGNAL_LOSS.md PLCSIM
section) — corrected or confirmed by what you find.
