# Brief m4f-08 — commissioning scenarios and evidence plan

```
gate:                M4
agent:               sim
goal:                The five gate scenarios exist as an executable, owner-runnable
                     procedure with an evidence checklist, rehearsed as far as the
                     test double allows.
invariants_touched:  none
inputs:              [docs/roadmap.md M4 row, plc/forklift/SPEC.md section 11,
                      agv/forklift/README.md, sim/launch/forklift_bringup.launch.py,
                      hmi/EVIDENCE_HMI.md, bridge/EVIDENCE_CONNECT.md patterns,
                      plc/forklift/double/ (the PLC logic double, m4f-04c),
                      bridge/config/rehearsal-forklift.yaml (m4f-06b)]
deliverable:         sim/scenarios/forklift_commissioning.md (procedure + evidence
                     checklist), plus any stimulus helper script under
                     sim/scenarios/ it needs, plus the sim/README.md section for
                     the arena and these scenarios (requested by m4f-03's report)
done_when:           each roadmap criterion (a)-(e) has a scenario with: exact
                     process start order (PLCSIM, bridge, sim bringup, vehicle
                     nodes, hmi — with GZ_PARTITION/ROS_DOMAIN_ID values), operator
                     steps at the HMI, the observable that proves it (which node,
                     which topic, which watch-table row), and the evidence artifact
                     to capture (per-session bridge CSV, watch-table PNG, screen
                     recording segment); stimulus fallbacks avoid --once publishes
                     (LESSONS delivery entry); ALL FIVE scenarios are rehearsed
                     agent-side through the full loop — HMI (m4f-07) → PLC
                     logic double (plc/forklift/double, 20 ms loop per SPEC §7)
                     → bridge with rehearsal-forklift.yaml → arena (m4f-03) and
                     back — with per-session bridge CSVs and the UI metrics
                     panel named among the observables, recorded in the file
                     with figures as printed and labelled REHEARSAL EVIDENCE
                     throughout: the gate closes on the owner's PLCSIM run and
                     recording, never on the double; owner-executed steps are
                     marked owner explicitly.
forbidden:           [running against live PLCSIM (owner-run), editing agv/ bridge/
                      hmi/ plc/ files, redefining any gate criterion, mentioning
                      any deadline]

Process notes binding on the scripts: SIGINT does not reliably bring the launch
process group down (m4f-03 measured >6 s) — every scenario script verifies with
pgrep -af and finishes by exact pid; fresh GZ_PARTITION and ROS_DOMAIN_ID per
run as always.
```

Git: repo-local owner identity; pathspec-scoped commit of exactly your sim/ files
plus your report docs/reports/m4f-08-commissioning-scenarios.md; message style
`feat(sim): add the forklift commissioning scenarios`.
