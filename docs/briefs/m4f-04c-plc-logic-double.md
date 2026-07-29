# Brief m4f-04c — PLC logic double for the forklift program

```
gate:                M4
agent:               plc
goal:                An executable stand-in for FB_ForkliftTeleop lets the whole
                     teleop loop run and be rehearsed without TIA Portal.
invariants_touched:  none — the double is a test artifact of the plc layer, the
                     TIA build remains the plant
inputs:              [plc/forklift/SPEC.md (section 7 is the source to
                      transliterate), docs/interfaces/opcua-nodes.md section 10,
                      docs/interfaces/bridge-design.md section 2.1 (the
                      forklift-only configured surface), bridge/ venv's asyncua
                      version (pin to it)]
deliverable:         plc/forklift/double/ — an asyncua server serving the
                     forklift-only configured surface (section 10 node set, the
                     Hmi group writable, plus the shared Link heartbeat surface
                     the bridge needs) with a 20 ms logic loop implementing
                     SPEC section 7; config (default port 4850); README;
                     EVIDENCE_DOUBLE.md
done_when:           the logic is section 7 transliterated statement-for-
                     statement — same identifiers, same order, same constants,
                     no improvement and no deviation; any ambiguity or defect
                     found during transliteration STOPS the work and goes in
                     the report rather than being fixed silently (the double's
                     purpose is spec conformance, and a spec defect found here
                     is a defect the owner would otherwise type into TIA); the
                     T5.2, T5.3, T5.4 and T5.5 kernels are demonstrated against
                     it by a direct asyncua client script with transcripts in
                     the evidence — speed cap engaging at the fork-height
                     threshold, obstacle latch with edge-triggered monitored
                     reset (held button clears nothing, reset refused while the
                     zone reads occupied), heartbeat stale driving all three
                     setpoints to 0.0 within the window, and HmiLinkOk FALSE
                     from boot until the heartbeat has been seen to change; the
                     README states in its first lines that this is a rehearsal
                     stand-in derived from SPEC section 7, that the TIA build
                     is the plant, and that any divergence resolves toward
                     TIA + SPEC, never toward the double.
forbidden:           [editing SPEC.md logic or constants (report findings
                      instead), touching bridge/ hmi/ sim/ agv/ or
                      docs/interfaces/, new dependencies beyond asyncua,
                      serving on 4840 or the doubles' 4842-4846 range,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly
plc/forklift/double/ plus your report docs/reports/m4f-04c-plc-logic-double.md;
message style `feat(plc): add the forklift logic double`.
