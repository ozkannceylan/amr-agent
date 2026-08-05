# Report — m5-12b protective-field evaluation, phase 1 build

    brief:               m5-12b (issued in-session; no file in docs/briefs/)
    status:              done
    files_changed:
      - agv/forklift/scripts/field_evaluation.py        (new - the node)
      - agv/forklift/config.yaml                        (new `field:` block; rear
                                                         measurement topic named)
      - agv/forklift/launch/vehicle.launch.py           (rear channel bridged;
                                                         field_evaluation argument)
      - agv/forklift/nav2.yaml                          (min_velocity -0.60 -> -0.55)
      - agv/forklift/README.md                          (four statements the build
                                                         made stale)
      - agv/forklift/EVIDENCE_FIELD_EVALUATION.md       (new - the evidence)
      - agv/forklift/evidence/field_evaluation/*.log    (12 session transition logs)
      - docs/reports/m5-12b-field-evaluation-build.md   (this report)
    invariants_touched:  none
    open_questions:
      - "A verdict on a topic" could not be built as the brief phrased it.
        config.yaml carries an owner ruling (m5-06) that the safe channel has
        NO topic on either transport, check_sensor_frames.py section 4 checks
        it by machine, and FIELD-EVALUATION.md section 2 reads the phrase as
        "on the link". The design was followed. The recorded evidence is the
        transition log correlated with the writer's session log, which is what
        SPEC section 7.6 actually requires of criterion (a) and is stronger
        than a topic echo because it names the SOURCE of each write. Confirm
        this reading; the m5-12 report raised the same conflict.
      - CORRECTION REQUESTED to FIELD-EVALUATION.md section 6. Its rear
        self-return clip band, -131.5..-72.3 deg, is EVIDENCE_SENSOR_COVERAGE
        section 13.2's measured -131.48..-72.26 rounded outward at one end and
        INWARD at the other. Applied verbatim it leaves index 5 (self-return
        0.780 m against a 1.001 m boundary) and index 65 (0.164 m against
        2.183 m) inside the field, and either alone holds the verdict at
        INTRUSION for ever. The band in force is -133.0..-71.8, placed between
        rays so it excludes exactly the measured index set 5..65. That is
        agv/'s own file and I could have edited it; I did not, because it is
        another brief's deliverable and the authority I was told to build
        against.
      - scripts/sensor_coverage.py NO LONGER RUNS against model.sdf.
        load_model reads lidar/scan/horizontal for every <sensor>, the IMU has
        no <lidar>, and it dies with AttributeError before printing anything.
        That is the tool the whole of EVIDENCE_SENSOR_COVERAGE.md was produced
        with. Out of this deliverable, not fixed, and it needs a brief.
      - nav2.yaml's reverse cap moved from -0.60 to -0.55, which
        FIELD-EVALUATION.md section 5 derives and section 12 requires for
        phase 1. Every committed figure in EVIDENCE_NAV2.md was measured at
        -0.60; a route that commands reverse travel must be re-measured before
        its numbers are quoted again. Whether Nav2 in the warehouse world ever
        commands reverse at all is measurement 6 of section 11 and is
        unanswered.
      - Offering, not adding: the 20-case deterministic check that exercises
        the empty horizon and the whole validity ladder ran from scratch and
        is quoted verbatim in the evidence. It is the regression guard for the
        defect this project has now made once and nearly made twice. It is not
        committed because the brief scoped phase 1 to the node, the config
        block and the bridge line. Say the word and it lands as
        scripts/check_field_evaluation.py.
      - No new dependency was added and none is proposed.
    next_suggested:      Close criterion (a) by carrying one field-driven
                         ZONE 0 through to ZoneStopDemand in the consumer's
                         view - the half this brief could not reach.

## Summary

Phase 1 of `FIELD-EVALUATION.md` is built and a real intrusion in Gazebo
now drives the stand-in channel with no hand anywhere in the chain. A
0.30 m box was **spawned into the running world and moved** with
`gz service set_pose`: at 22:19:34.011 the front device reported
`INTRUSION on one scan: 24 ray(s) inside the contour, nearest 0.721 m`,
`ZONE 0` went out at .053, and the writer's own log recorded
`FIELD | ZONE 0 -> ZoneDeviceCircuitClosed := False` at .089. Four
transitions, both devices — the drive corridor for the front, the fork
corridor for the rear — every one with source **`FIELD`** and **no
`OPERATOR` line anywhere in the writer's session**. The control case
matters as much: an object 2.85 m away and plainly visible to the
scanner, but outside the 1.35 m contour, produced no verdict at all.
**Criterion (a) is not closed** — the chain is shown to
`ZoneDeviceCircuitClosed`, not through to `ZoneStopDemand`, because that
needs a watch table under activated safety mode and none was opened.

The failure behaviour was built first and tested hardest, and it is where
this run earned its keep. A per-device death (one scanner's channel
SIGKILLed, the other healthy) reads intrusion in **221 ms**, with the
surviving device's verdict still computed and logged so the evidence
names *which* one failed. The evaluation's own death is converted by the
consumer in 0.66–0.99 s, four draws. The empty horizon reads **CLEAR** on
both devices, proven by construction because a 24×16 m walled arena
cannot make an all-`inf` scan — and every other way a ray can fail (NaN,
`-inf`, finite below `range_min`, finite above `range_max`) reads
INTRUSION, with a single NaN on a live ray enough on its own. R8 is
respected as **field geometry and not a filter**: the rear device's own
carriage still returns at 0.101 m and the front's rear wheel at 1.084 m,
both measured, both logged, neither deleted, with the boundary drawn
inside them. R3 was proven rather than asserted — a load placed on the
tines put 24 of the vehicle's own rays inside its own field, which is
exactly why the design excludes the fork sector under a load instead of
trying to watch through it.

Three defects were found and two of them are mine. The design's §6 clip
band, applied as written, leaves the vehicle permanently inside its own
field (above). My first link code used a blocking connect and stalled the
node's own executor, so the node reported **its own** freshness rule
violated at 0.84–1.00 s while an independent probe measured 0.016 s on
the same topics in the same run. And the one that matters: **the
evaluation tick ran on the simulation clock**, which `/clock` publishes
from the same `ros_gz_bridge` that carries both scanners — so stopping
the scans stopped the watchdog meant to detect it, and the node sat in
`futex_wait_queue_me` with its CPU time frozen, silent, three times.
`obstacle_zone.py` survived the identical event and that is what
attributed it: the stack was fine, the bug was mine. Fixed with a steady
clock and re-proven at **260 ms**. Two things go on the record with it.
The rule — *a watchdog whose tick runs on the clock of the thing it
watches is not a watchdog*, `obstacle_zone.py`'s own docstring rule one
level up. And the fact that through all three wedged runs the vehicle was
still covered, because the consumer's stale rule opened the channel in
under a second — the architecture catching the defect before it could
matter, which is a reason to trust the design and no reason at all to be
relaxed about the node.
