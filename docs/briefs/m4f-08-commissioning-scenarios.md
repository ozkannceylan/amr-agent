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
                      hmi/EVIDENCE_HMI.md, bridge/EVIDENCE_CONNECT.md patterns]
deliverable:         sim/scenarios/forklift_commissioning.md (procedure + evidence
                     checklist), plus any stimulus helper script under
                     sim/scenarios/ it needs
done_when:           each roadmap criterion (a)-(e) has a scenario with: exact
                     process start order (PLCSIM, bridge, sim bringup, vehicle
                     nodes, hmi — with GZ_PARTITION/ROS_DOMAIN_ID values), operator
                     steps at the HMI, the observable that proves it (which node,
                     which topic, which watch-table row), and the evidence artifact
                     to capture (per-session bridge CSV, watch-table PNG, screen
                     recording segment); stimulus fallbacks avoid --once publishes
                     (LESSONS delivery entry); a dry rehearsal of whatever runs
                     without PLCSIM (sim + vehicle nodes + a scripted command
                     sequence) is recorded in the file with figures as printed;
                     owner-executed steps are marked owner explicitly.
forbidden:           [running against live PLCSIM (owner-run), editing agv/ bridge/
                      hmi/ plc/ files, redefining any gate criterion, mentioning
                      any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly your sim/ files
plus your report docs/reports/m4f-08-commissioning-scenarios.md; message style
`feat(sim): add the forklift commissioning scenarios`.
