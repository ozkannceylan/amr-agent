# Brief m4f-02c — beyond-range returns mean clear, not absent

```
gate:                M4
agent:               agv-ros2
goal:                Open space ahead no longer reads as an obstacle: a
                     beyond-range lidar return is a measurement (clear to
                     range_max), not missing data.
invariants_touched:  none
inputs:              [agv/forklift/scripts/obstacle_zone.py,
                      agv/forklift/config.yaml, agv/forklift/EVIDENCE_MODEL.md
                      (the §6 bounding cases), agv/forklift/README.md,
                      the live observation below]
deliverable:         agv/forklift/ — obstacle_zone.py semantics, EVIDENCE_MODEL.md
                     appended run, README contract row
done_when:           the validity rule distinguishes three classes: a sample
                     that is +inf or >= range_max is CLEAR evidence at
                     range_max (valid, contributes "no obstacle", never
                     triggers fail-safe); a finite sample inside
                     [range_min, range_max) is a distance; NaN or below
                     range_min stays invalid; the fail-safe (in_stop_zone TRUE,
                     min_distance 0.0) fires only on a stale scan (>0.5 s) or a
                     sector with no sample in either valid class — a dead or
                     garbage sensor still stops the machine, an open horizon
                     does not; with the whole sector clear-beyond-range,
                     min_distance publishes range_max (8.0, inside the §10.4
                     plausibility window); the fault matrix is re-run with the
                     all-inf case now expecting FALSE at 8.0, a mixed case
                     (inf rays plus one finite 2.0 → FALSE at 2.0) added, and
                     the NaN/stale/below-min cases still TRUE at 0.0; the new
                     dated run is APPENDED to EVIDENCE_MODEL.md §6 with the old
                     transcript intact and a sentence recording why the old
                     bounding case's expectation changed (the live false stop
                     of 2026-07-29: healthy 10 Hz scan, all-inf forward sector,
                     fail-safe latched the process stop in open space); the
                     README /forklift/obstacle rows state the three classes.
forbidden:           [touching model.sdf or forklift_io.py or sim/ or
                      thresholds (sector angle, 1.2 m, stale window) beyond
                      the validity semantics, editing docs/interfaces/,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly your
agv/forklift/ files plus your report docs/reports/m4f-02c-inf-means-clear.md;
message style `fix(agv): treat beyond-range returns as clear`.
