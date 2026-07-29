# Brief m4f-02b — record the ±45° scan dropout in the vehicle contract

```
gate:                M4
agent:               agv-ros2
goal:                The vehicle's contract table warns consumers that the
                     scanner is not gap-free.
invariants_touched:  none
inputs:              [docs/reports/m4f-03-forklift-world-bringup.md (the
                      finding), agv/forklift/README.md]
deliverable:         agv/forklift/README.md — one contract-table amendment for
                     /forklift/scan
done_when:           the /forklift/scan row states that the gz gpu_lidar drops
                     the single sample at exactly ±45 deg (verified sensor-side
                     against a continuous object, orientation-dependent, not a
                     fixed index — m4f-03 evidence), that consumers must not
                     assume every sample finite, and that obstacle_zone.py's
                     per-sample affirmative validity already treats it
                     correctly; nothing else changes.
forbidden:           [touching model.sdf, scripts, config or sim/ files,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the README
plus your report docs/reports/m4f-02b-scan-dropout-contract.md; message style
`docs(agv): record the scan dropout in the vehicle contract`.
