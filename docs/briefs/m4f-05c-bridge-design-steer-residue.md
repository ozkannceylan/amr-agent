# Brief m4f-05c — bridge-design steer-exemption residue

```
gate:                M4
agent:               interface
goal:                bridge-design.md nowhere asserts the withdrawn steer
                     exemption.
invariants_touched:  none
inputs:              [docs/reports/m4f-05b-bridge-design-steer-reason.md
                      (ready-to-apply text), docs/interfaces/opcua-nodes.md
                      section 10.6]
deliverable:         docs/interfaces/bridge-design.md — section 4.7 signal-map
                     row 15 and section 8 reconnect rule N4 corrected
done_when:           both cells assert the section 10.6 ruling (all three
                     setpoints gated to zero; the wheel centres on a stop);
                     verdict and owner columns untouched; a SUBJECT sweep —
                     every whitespace-normalised occurrence of "steer" and
                     "ForkliftSteerAngleRef" across the whole file, each hit
                     read for dependency — finds zero remaining statements
                     resting on the withdrawn exemption, and the report lists
                     the hits it read.
forbidden:           [structural changes, any file other than the design doc
                      and your report, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly the design
doc plus your report docs/reports/m4f-05c-bridge-design-steer-residue.md;
message style `docs(interfaces): remove the last steer-exemption residue`.
