# Brief m5-04b — the rear scanner's self-occlusion band

```
gate:                M5
agent:               agv-ros2
goal:                the rear safety scanner's near-field return band is
                     explained, and either corrected or documented as a
                     derived property of the vehicle's own geometry.
invariants_touched:  none
inputs:              [docs/reports/m5-07-autonomy-toolchain.md (the finding),
                      agv/forklift/EVIDENCE_SENSOR_COVERAGE.md residuals R1
                      and R2, agv/forklift/model.sdf, scripts/sensor_coverage.py]
deliverable:         agv/ — the coverage evidence updated, and the model only
                     if the analysis shows a pose or aperture correction is
                     warranted
done_when:           the band is measured in the running simulation — which
                     angular sector, which surfaces return it, at what
                     distances — and attributed to named geometry; the result
                     is reconciled with the R1 and R2 residuals already in the
                     evidence, stating whether it is the same phenomenon at a
                     larger magnitude than predicted or a different one the
                     geometric analysis missed; and the verdict is one of:
                     (a) a pose or yaw correction that reduces it, with the
                     new coverage re-measured and the trade named, (b) an
                     aperture or mount change, or (c) an accepted residual
                     with its mitigation, in which case the evidence says so
                     in the same voice as R1-R7 and the protective-field
                     design in m5-12 inherits it as a constraint.
forbidden:           [changing the front scanner or the navigation lidar
                      unless the analysis forces it, and then only with the
                      full coverage set re-measured; claiming a fix that is
                      not re-measured; masking the band by filtering samples
                      in software (a real scanner sees what it sees — the
                      answer is geometry or an accepted residual, not a
                      filter); editing sim/, plc/, hmi/ or bridge/;
                      committing (the orchestrator commits)]
```

## The finding

m5-07's verification run, on the committed model, captured this on
`/forklift/gz/scan_safety_rear`: **46 of 93 finite returns sit under 0.5 m in
one contiguous band**, while neither other scanner has any such band. The
signature is self-occlusion — the vehicle's own structure inside the scanner's
aperture.

m5-04's geometric analysis already predicted two related residuals: R1, the
carriage shadow at 169.4-174.4°, and R2, the tines crossing the scan plane in
the 0.05-0.10 m lift window. The rear scanner sits at (−0.700, −0.450, 0.150),
the fork end, so mast and tine structure are the obvious candidates. What is
not yet established is whether the measured band's *magnitude* — half the
finite returns — is consistent with those residuals or exceeds them.

This matters beyond tidiness. A protective field cannot be drawn through a
sector the scanner cannot see, and the field evaluation in m5-12 will inherit
whatever this brief concludes. A real forklift has exactly this problem on its
load side, so an accepted, measured, mitigated residual is a legitimate and
even instructive outcome — what is not legitimate is leaving it unexplained or
hiding it behind a software filter.

Gazebo and ROS 2 are installed and working in this container (m5-07), so
measure rather than reason alone. Isolate with both `GZ_PARTITION` and
`ROS_DOMAIN_ID`; other agents may be running the arena.

Do not commit. Leave files modified and write your report to
docs/reports/m5-04b-rear-scanner-self-occlusion.md.
