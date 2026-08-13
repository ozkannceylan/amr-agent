# Brief m5-06 — the measurement channel, the process consumer, and sensor TF

```
gate:                M5
agent:               agv-ros2
goal:                the process obstacle stop reads the front safety
                     scanner's non-safe MEASUREMENT channel, the two channels
                     of that device are named and contracted distinctly, and
                     the three new sensor frames exist in TF.
invariants_touched:  none
inputs:              [agv/forklift/model.sdf and config.yaml as landed by
                      m5-04, agv/forklift/README.md,
                      agv/forklift/scripts/obstacle_zone.py,
                      agv/forklift/EVIDENCE_SENSOR_COVERAGE.md,
                      docs/adr/0011-sensored-autonomy-architecture.md,
                      docs/reports/m5-04-sensor-layout.md open questions 1 and 6,
                      the ruling block below]
deliverable:         agv/ — topic contract, the process consumer's source, and
                     the sensor TF publisher
done_when:           the process obstacle stop consumes the FRONT SAFETY
                     SCANNER's scan, not the navigation lidar's, so M4's
                     demonstrated low-plane behaviour is preserved; the
                     contract tables in config.yaml and README name the two
                     channels of the safety scanner distinctly and carry the
                     sentence that the measurement channel is non-safe and
                     must never implement a safety function; the navigation
                     lidar is documented as the only SLAM input; TF exists for
                     `safety_scanner_front_link`, `safety_scanner_rear_link`
                     and `nav_lidar_link` with poses that agree with
                     model.sdf, and the agreement is checked rather than
                     asserted; and the obstacle evaluator's sector, stop
                     distance and fail-safe classes still behave as
                     docs/reports/m4f-04i and m4f-02b contracted them, with
                     any change forced by the new aperture stated explicitly.
forbidden:           [feeding either safety scanner into SLAM, AMCL or a
                      costmap; deriving any safety verdict in this brief (the
                      OSSD-equivalent field evaluation is m5-12's, not
                      yours); editing sim/, plc/, hmi/, bridge/ or
                      docs/interfaces/; changing the scanners' poses or
                      apertures (m5-04 derived them); committing (the
                      orchestrator commits)]
```

## Ruling (owner-approved 2026-07-30)

A real SICK microScan3 emits **two outputs from one device**: the safe OSSD
(or PROFIsafe safe bits), and a separate **non-safe measurement channel** the
datasheet provides for HMI, diagnostics and process use while stating it must
not be used for safety-related tasks. The simulation models this exactly: the
`gpu_lidar` scan **is** the measurement channel, and the OSSD-equivalent
verdict is *derived* from it by field evaluation — which is what the real
device does internally.

Consequences to implement:

- The M4 process obstacle stop is a **process** consumer, so it reads the
  measurement channel of `safety_scanner_front`. This preserves the low-plane
  behaviour M4 demonstrated; the navigation lidar at 1.80 m cannot see a
  pallet and would read clear.
- The measurement channel and the future safe channel must be **separately
  named** wherever a contract table lists topics, so no later reader can
  mistake one for the other. Choose names that survive the arrival of the
  safe channel in m5-12 and say what you chose in your report — a downstream
  brief and the bridge configuration will cite them.
- Record once, in the README, why this is not a layer violation: the process
  function consumes the device's process output, while the safety function
  consumes the device's safe output. What ADR 0011 forbids is a safety
  scanner feeding a NAVIGATION consumer — SLAM, AMCL, costmaps — and that
  prohibition is unchanged.

## Notes

Two carried items from m5-04 that are yours: open question 6 (no TF exists for
the three new sensor frames) is in scope here; open question 1 is the ruling
above. Open questions 2, 3 and 5 belong to `sim/` and 4 to
`docs/interfaces/` — do not touch them, and repeat them in your report so they
are not lost.

`gz_frame_id` was set by m5-04; TF must agree with it and with the SDF poses.
Prefer one mechanism over two — if a URDF plus `robot_state_publisher` is the
right answer, say why; if static transform publishers are, say why. Whichever
you choose, the check that TF and SDF agree is part of the deliverable, not a
claim in prose.

Gazebo may or may not be runnable in this container by the time you start (a
toolchain brief is in flight). If it runs, exercise what you can and report
what you exercised; if it does not, deliver the static agreement check and say
plainly what a live run still owes. Evidence is qualified by the environment
that produced it.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-06-measurement-channel.md.
