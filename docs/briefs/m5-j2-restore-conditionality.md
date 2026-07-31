# Brief m5-j2 — restore the F-I/O conditionality, and correct the authority file

```
gate:                M5
agent:               agv-ros2
goal:                no document in agv/ states the unproven F-I/O path as
                     settled fact, and model.sdf stops describing a sensor
                     wiring that changed under it.
invariants_touched:  none
inputs:              [docs/reports/m5-judge-architecture-review.md findings 2
                      and 5, docs/adr/0011-sensored-autonomy-architecture.md
                      D2 (the feasibility condition and its fallback),
                      plc/forklift-safety/FIO-FEASIBILITY.md,
                      agv/forklift/model.sdf, agv/forklift/README.md,
                      agv/forklift/EVIDENCE_SENSOR_COVERAGE.md]
deliverable:         agv/ — the conditional restored, the stale sentence
                     corrected
done_when:           every statement in agv/ that describes the scanner
                     reaching the F-program through configured F-DI driven by
                     the PLCSIM Advanced API carries the condition ADR 0011 D2
                     attaches to it — the path is the DESIGN INTENT, unproven
                     until m5-03 is run by the owner, with a named fallback;
                     `model.sdf`'s sensor documentation no longer says the
                     obstacle evaluator reads the navigation lidar or that the
                     safety scanners have no consumer, both of which became
                     false in commit 6068b31 when the measurement channel
                     ruling landed; and a whitespace-normalised sweep of agv/
                     for the F-DI, PLCSIM, API and OSSD subjects confirms no
                     remaining unconditional statement.
forbidden:           [weakening or restating the ADR 0011 D2 decision itself —
                      you are marking it unproven, not reopening it; editing
                      plc/, sim/, hmi/ or docs/ outside your report; changing
                      any measured figure; deciding the fallback question
                      (deliberately open pending m5-03); committing (the
                      orchestrator commits)]
```

## Why this matters, in this project's own terms

LESSONS carries the rule already: *spec values authored without the tool that
realises them are design values, not facts*. The F-DI-plus-API path has never
been run — `plc/forklift-safety/FIO-FEASIBILITY.md` exists precisely to settle
it and its verdict section is blank. Four documents nonetheless describe it in
the indicative, and the conditional survives only in `docs/roadmap.md`. That is
the same failure mode as the namespace URI in 2026-07-27: a design value
propagating as fact until something forces a correction.

The second half is a plain staleness bug and it sits in the file the project
names as the authority for the model. `model.sdf` around lines 240-245 still
tells the reader that the obstacle evaluator consumes the navigation lidar and
that the safety scanners have no consumer. Since 6068b31 the process obstacle
stop reads the FRONT SAFETY SCANNER's non-safe measurement channel and the
navigation lidar is the SLAM input. Correct it, and while you are there check
the surrounding sensor commentary for anything else the measurement-channel
ruling invalidated — sweep by subject, not by the two line numbers.

One guard worth writing once, from judge finding 5: the measurement channel
and the future safe channel are derived from the SAME ray cast. That is honest
device modelling — a real scanner derives its OSSD from its own measurement —
but it is not redundancy and no document may let a reader infer two
independent channels. R7 makes the point concrete: the mast reads 8.75°
simulated against 29.0° physical, and a ray error of that kind reaches both
channels identically.

Do not commit. Leave files modified and write your report to
docs/reports/m5-j2-restore-conditionality.md.
