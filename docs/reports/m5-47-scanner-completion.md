# Report — m5-47 scanner completion: the corrected clip band and the warning field

    brief:               docs/superpowers/plans/2026-08-06-m5-closure.md,
                         TASK 1 (issued in-session; no file in docs/briefs/)
    status:              done
    files_changed:
      - agv/forklift/FIELD-EVALUATION.md                 (section 6 clip band
                                                          CORRECTED + rounding
                                                          rule; new section 3
                                                          warning chain; new
                                                          section 6.1 warning
                                                          derivation; section 8
                                                          release discipline;
                                                          section 11
                                                          measurements 8-11;
                                                          section 12 phase 2)
      - agv/forklift/scripts/field_evaluation.py         (phase 2: second
                                                          contour, warning
                                                          verdict, SF-04 hold,
                                                          one Bool publisher)
      - agv/forklift/config.yaml                         (warning_depth_m,
                                                          warning_clear_hold_s,
                                                          topics.warning_field_
                                                          occupied; clip
                                                          comment re-based on
                                                          the corrected design)
      - agv/forklift/launch/vehicle.launch.py            (field_evaluation
                                                          argument description
                                                          only; no node,
                                                          default or check
                                                          changed)
      - agv/forklift/README.md                           (three statements the
                                                          build made stale)
      - agv/forklift/EVIDENCE_FIELD_EVALUATION.md        (APPENDED sections
                                                          10-17, dated
                                                          2026-08-06; existing
                                                          content byte-identical
                                                          - verified by
                                                          comparing the first
                                                          32769 bytes before and
                                                          after)
      - agv/forklift/evidence/field_evaluation/*.log     (2 new session
                                                          transition logs)
      - docs/reports/m5-47-scanner-completion.md         (this report)
    invariants_touched:  none
    open_questions:
      - REQUEST, and phase 2 does nothing without it. The warning verdict is
        published on /forklift/warning_field/occupied and NOTHING CONSUMES IT.
        The path the design assumes is: this topic -> a ROS-to-OPC-UA carrier
        (bridge/'s) -> a node in the model (docs/interfaces/'s) -> the STANDARD
        program lowers the envelope ceiling -> the F-program only verifies and
        demands. None of the three exists and none is this directory's to
        create. Stages w3-w6 of T_w are therefore budgets against a designed
        path, not a built one, and the warning field trips nothing today.
      - REQUEST that travels with the topic and must not be dropped. The level
        is published at the 20 Hz evaluation tick and NOT on transitions,
        precisely so that its ABSENCE is visible. A consumer that republishes
        the last value it saw would turn this node's death into a standing
        order to keep driving fast (LESSONS 2026-08-04, twice). Every consumer
        owes a stale rule of its own: no message inside its window means
        OCCUPIED, never clear. That obligation is stated in config.yaml,
        README.md, the node and FIELD-EVALUATION.md section 12, and it belongs
        in the interface document when the node is specified.
      - THE FORK-DIRECTION WARNING BOUNDARY IS OUTSIDE THE DETECTION-CAPABILITY
        FLOOR BY 0.62 m. The derived 3.35 m puts the worst rear corner 4.63 m
        from the rear device, where the 1.00365 deg/ray spacing has opened to
        81 mm against the 70 mm criterion. Named in section 6.1 and section 11
        of the evidence, not smoothed and not resized away: resizing down to
        4.01 m would silently deliver less speed reduction than the derivation
        requires. It is acceptable only because SF-04 carries NO PL claim and
        is backed unconditionally by SF-03, whose field is inside the floor
        everywhere. If the owner wants the warning field inside the floor, the
        lever is the speed regime, not the depth.
      - MEASUREMENT 11 IS THE ONE THAT CAN FALSIFY 3.35 m and it is untaken:
        drive the vehicle into a warning-field entry and measure whether it is
        actually at or below the creep ceiling by the protective boundary. The
        vehicle never moved in this session. Four of T_w's six stages are
        budgets, exactly as three of T's eight are.
      - CRITERION (a) IS STILL NOT CLOSED, and this session went backwards on
        the consumer's view rather than forwards: no stand-in writer, no
        PLCSIM instance and no PLC ran. The protective verdict's receipt was
        recorded by a THROWAWAY TCP SINK on the WSL side, which proves the
        ZONE lines left the node and proves nothing about
        ZoneDeviceCircuitClosed. The 2026-08-05 section 4.3 remains the only
        consumer-view record.
      - scripts/sensor_coverage.py STILL DOES NOT RUN against model.sdf (m5-12b
        raised it; nothing here fixed it). EVIDENCE_SENSOR_COVERAGE.md section
        13 is the authority for both clip bands corrected in this brief and it
        is currently unreproducible. The m5 closure plan marks this "fix this
        one"; it is outside this deliverable and still needs a brief.
      - Offered, not added, for the second time. The 21-case validity ladder
        now exercises BOTH fields and the SF-04 hold, ran from scratch and is
        quoted verbatim in the evidence. It is the regression guard for the
        defect this project has made once and nearly made twice. Say the word
        and it lands as scripts/check_field_evaluation.py.
      - The rear device's LAST ingested scan read 4.00 % invalid samples
        against 0.00 % for the front, under the 5 % device-fault threshold so
        no fault was raised. It is the scan that arrived as the bridge was
        being killed. Recorded in the evidence and not explained.
      - No new dependency was added and none is proposed.
    next_suggested:      m5-48, the encoder. The warning field the SLS work
                         keys on now exists and has a boundary that survives
                         being quoted.

## Summary

**The §6 defect is corrected at the source, and the rule that produced it
is now written down.** The withdrawn band −131.5°…−72.3° took a measured
−131.48°…−72.26° and rounded it **outward at one end and inward at the
other**, leaving index 5 (self-return 0.780 m against a 1.001 m boundary)
and index 65 (0.164 m against 2.183 m) inside the field — either one alone
a permanent INTRUSION. Two defects sat in it, not one: the rounding
direction, and the fact that an **angle** was quoted where the **index
set** is the measurement (`EVIDENCE_SENSOR_COVERAGE.md` §13.2's index set
is 5..65, while −131.48° is the bearing of index 6). The band in force is
**−133.0°…−71.8°**, placed between rays from the aperture's own arithmetic
(1.00365°/ray: index 4 at −133.48°, index 66 at −71.26°), so it catches
5..65 inclusive and nothing else. The front device's band gained its
sensor-frame form, **+136.4°…+137.6°**, for the same reason. The rule now
binds every boundary in the document and is repeated in `config.yaml`:
**round a geometric boundary in the direction that excludes, never for
readability.**

**The warning field is derived, and the arithmetic is on the page.** The
requirement it answers is one sentence — an intruder standing on the
warning boundary must not reach the protective boundary before the vehicle
has finished slowing to the creep ceiling — and the accounting is §4's,
with the ramp ending at v_c instead of at zero:
`W(v) = D + v·T_w + (v² − v_c²)/2a + Kp·[T_w + (v − v_c)/a]`. **T_w = 0.35 s
is itself derived per stage**, in a new §3 table, and is shorter than the
protective T = 0.46 s by exactly the two stages the warning path does not
contain — the writer's 50 ms cycle and the F-OB's 100 ms — because the
warning path is process data end to end and the **standard** program is
what lowers the ceiling. At the speed in force, 0.60 m/s from `nav2.yaml`:
**W = 1.35 + 0.210 + 0.270 + 1.520 = 3.350 m**, read back out of the
running node rather than retyped into it. Where it does not fit is stated
rather than smoothed: the fork-direction corner lands 0.62 m outside the
70 mm detection-capability floor, and it is acceptable only because SF-04
carries no claim and SF-03 backs it unconditionally.

**Both fields were proven with real Gazebo intrusions and both have a
control case.** Nine repositions of a spawned box, every one read back
before the run was allowed to continue — `set_pose` returns `data: true`
for a well-formed *call*, not for a moved *entity*, so the entity id was
resolved from the read-back and sent beside the name, and all nine matched
to within 0.02 m. The warning-only case (box outside the protective 9.21 m
boundary, inside the warning 11.21 m) reported **9 rays inside the warning
contour, nearest 2.173 m, 103 ms after the call returned, with no
`AGGREGATE` line at all** — AT-04's first observation, protective verdict
untouched. Driving the box in to 8.5 m added the protective INTRUSION 40 ms
after the call; pulling it back out cleared the **stop** in 276 ms and
**held the speed reduction**, which is the case neither field has on its
own and the reason they are two fields rather than one with two names.
The rear device did the same pair on its own. **Two controls carried the
run**: a box 2.77 m from the front device but 1.45 m outside the corridor,
and a box in the corridor, in the driving direction, 3.75 m from the
device and **0.24 m outside the warning boundary** — neither produced a
verdict of any kind. SF-04's 2 s clear-hold was measured live three times
at 2.028, 2.029 and 2.038 s on the node's own steady clock.

**The per-failure behaviour survived the second field intact, and was
re-tested rather than assumed.** The 21-case ladder now reads both
verdicts from the same scan: the **empty horizon reads CLEAR on both
fields** — a `+inf` return is a measurement, clear to `range_max`, and the
2026-07-29 defect did not re-open one field over — while NaN, `−inf`,
finite below `range_min`, finite above `range_max`, frozen stamps and an
incomplete debounce all read demanding on both. Nesting held in every row
and the node checks it at contour build (`0 ray(s) where the warning
boundary is inside the protective one`). Killing the scan bridge put both
verdicts demanding in 282 ms on the **steady-clock** rule — `/clock` froze
with the scans, so the design's own freshness rule read *fresh* for ever,
exactly as on 2026-08-06 — and the node went on publishing `occupied` at
20.0 msg/s while blind, because a blind node reports the demanding level
rather than falling silent.

**Two things this brief did not do.** It did not reach a consumer: no
writer, no PLCSIM, no PLC, so criterion (a) is no closer and the warning
verdict trips nothing. And it did not measure whether 3.35 m actually
delivers the reduction it is sized for — the vehicle stood still for the
whole session, and that measurement is named in the design as the one that
can falsify the depth.
