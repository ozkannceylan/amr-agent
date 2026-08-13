# Brief m4f-09 — M4 gate verification

```
gate:                M4
agent:               verifier
goal:                An independent ruling on whether the M4 gate criteria are
                     demonstrated by committed evidence, and whether the new layers
                     respect the contract.
invariants_touched:  none
inputs:              [docs/roadmap.md M4 row, docs/adr/0008-*.md, all m4f-* and
                      m4r2-* reports, docs/interfaces/opcua-nodes.md section 10,
                      docs/interfaces/bridge-design.md, plc/forklift/SPEC.md,
                      agv/forklift/, sim/, hmi/, bridge/ evidence files,
                      docs/PLAN.md, docs/TODO.md, docs/LESSONS.md]
deliverable:         docs/reports/m4f-09-verify-m4-gate.md
done_when:           each criterion (a)-(e) has a verdict citing the committed
                     artifact that shows it; the recording criterion is checked
                     including the naming discipline (process logic, not safety
                     functions); layer boundaries are checked (hmi writes only
                     HMI nodes; bridge never touches HMI nodes; single writer per
                     node per invariant 10; PLC remains the only OPC UA server per
                     invariant 4); tracking files are reconciled against the full
                     report directory (LESSONS reconcile-in-bursts entry); the
                     verdict is pass, pass-with-findings, or fail with the failing
                     criterion named.
forbidden:           [writing anything except the report, re-running live PLCSIM
                      evidence (double re-runs allowed), mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly your report;
message style `docs(infra): verify the M4 gate`.
