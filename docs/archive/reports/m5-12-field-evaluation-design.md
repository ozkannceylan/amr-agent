# Report — m5-12 protective and warning field evaluation: the design

    brief:               docs/briefs/m5-12-field-evaluation-design.md
    status:              done
    files_changed:
      - agv/forklift/FIELD-EVALUATION.md   (new — the design document)
      - docs/reports/m5-12-field-evaluation-design.md   (this report)
    invariants_touched:  none
    open_questions:
      - The brief's phase-1 phrase "puts a real intrusion verdict on a topic"
        conflicts with the m5-06 owner ruling in agv/forklift/config.yaml
        ("the safe channel has no topic on either transport, ever"). The
        design follows the repository rule: the protective verdict crosses
        only the SPEC §7.2 TCP link; the warning verdict (non-safe, SF-04)
        may be a topic. Confirm this reading.
      - The consumer of the warning verdict (who enforces creep in the twin)
        is unassigned — envelope chain, a vehicle-side limiter, or deferred
        to the modelled SF-10. Owner/interface call, needed before phase 2.
      - ISO 13855 / ISO 3691-4 texts are not accessible to the project. The
        depth derivation is framed on their documented general form
        (S = K·T + DDS + Z, clause 5 per secondary sources, read 2026-08-05)
        and is marked PROVISIONAL in the document. If the owner can obtain
        either text, the Kp term's applicability to a vehicle-carried field
        is the one question to settle — it decides the fork-first ceiling
        (0.59 m/s with the term, 0.97 m/s without).
      - Fork-first (reverse) speed cap 0.55 m/s lands as one nav2.yaml value
        in the build brief; whether Nav2 ever commands reverse travel in the
        warehouse world is measurement #6 in the design's §11.
      - Whether the writer accepts a ZONE line immediately on (re)connect as
        "a transition from unknown" should be confirmed against the writer
        implementation when it exists (SPEC §7.2 names transitions + PING
        only); the design sends one and argues it is a transition.
    next_suggested:      Build phase 1 (field_evaluation.py + rear-channel
                         bridge + config block) — it is the piece that
                         unblocks the stand-in writer and criterion (a).

## Summary

The design derives, rather than chooses, every field boundary. The total
response time is summed per stage with sources — scan 100 ms, evaluation
budget 30 ms, link budget 10 ms, writer cycle 50 ms, F-OB 100 ms = 290 ms
demand formation; plus standard-scan budget 20 ms, bridge 50 ms, gate budget
100 ms = 460 ms before the measured 0.50 m/s² ramp begins. Depth
D(v) = 0.46v + v² + 0.05 (+0.74 m provisional intruder-advance term).
At full speed the geometry **fits drive-first at every reachable speed**
(closes at ≈1.49 m/s against the 4.0 m detection floor) and **does not fit
fork-first at the 1.00 m/s ceiling**; the honest answer taken is a
**speed-dependent field set** — drive-first 2.25 m at ≤1.00 m/s, fork-first
1.35 m at ≤0.55 m/s (geometry closes at 0.59), muted case at ≤0.30 m/s with
the load sector excluded (SC-13). Fields are clipped by each device's
measured self-return contour (R8), R1's 0.17 m patch is named an accepted
residual, and gz's out-of-range folding of sub-range_min strikes (R4) is
named the stand-in's blind ring. The OSSD equivalent is an antivalent pair
in one atomic record, zero discrepancy tolerance, union aggregation, with a
per-session transition log as criterion-(a) evidence. Failure behaviour is
per failure with affirmative validity: dead, stale, single-device and
out-of-window all read intrusion; an empty horizon reads **clear** because a
beyond-range return is a measurement (LESSONS 2026-07-29). The output suits
the writer's 50 ms republish with no change to SPEC §7. All PL/Category
references are PLr targets only (ADR 0011 D5).
