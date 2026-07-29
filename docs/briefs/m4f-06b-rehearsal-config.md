# Brief m4f-06b — committed rehearsal config for the forklift loop

```
gate:                M4
agent:               bridge
goal:                A committed bridge config lets the rehearsal loop run
                     forklift-only against the PLC logic double.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md section 2.1,
                      bridge/config/bridge.yaml (live, cell-only — untouched),
                      bridge/amr_bridge/config.py (group definitions)]
deliverable:         bridge/config/rehearsal-forklift.yaml
done_when:           the config declares the forklift group only, endpoint
                     opc.tcp://127.0.0.1:4850 (the plc logic double's default),
                     per-session evidence naming intact; the config loader
                     accepts it (validation command output quoted in the
                     report); a header comment states it is the rehearsal
                     config, that gate evidence runs on the live bridge.yaml
                     against PLCSIM, and that bridge.yaml stays cell-only until
                     the owner's TIA read-back; bridge/config/bridge.yaml is
                     byte-identical before and after.
forbidden:           [code changes, touching bridge.yaml, running against
                      PLCSIM, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the config
file plus your report docs/reports/m4f-06b-rehearsal-config.md; message style
`feat(bridge): add the forklift rehearsal config`.
