# Brief m5-04 — safety scanner pair and navigation lidar, with measured coverage

```
gate:                M5
agent:               agv-ros2
goal:                the forklift model carries two diagonal safety scanners
                     and one navigation lidar, with coverage MEASURED and its
                     residual blind sectors named.
invariants_touched:  none
inputs:              [agv/forklift/model.sdf, agv/forklift/config.yaml,
                      agv/forklift/README.md, agv/forklift/EVIDENCE_MODEL.md,
                      docs/briefs/m5-01-adr-0011-sensored-autonomy-architecture.md
                      (facts block, scanner class),
                      docs/reports/m4f-02b-scan-dropout-contract.md,
                      the design block below]
deliverable:         agv/forklift/model.sdf, agv/forklift/config.yaml, the
                     README contract table, and a NEW coverage evidence file
                     under agv/forklift/
done_when:           the model carries three ray sensors as specified below,
                     each with a computed pose justified against the model's
                     real geometry; the coverage evidence file reports
                     MEASURED angular coverage around the vehicle, the overlap
                     sectors between the two safety scanners, and every
                     residual sector named with its cause and its mitigation;
                     the config.yaml/README contract tables list the new
                     topics; and no coverage statement appears anywhere that
                     the evidence does not measure.
forbidden:           [raising sample counts or update rates beyond the design
                      block without measuring the cost and recording it
                      (model.sdf's own rule); adding a 3D/multi-row lidar;
                      feeding the safety scanners into any navigation
                      consumer; editing sim/, plc/, hmi/ or bridge/; claiming
                      "no blind spots"; committing (the orchestrator commits)]
```

## Design block (owner-approved 2026-07-30)

**Two safety scanners, diagonal.** Modelled class: SICK microScan3 Pro,
**275° aperture**. Mounted at diagonally opposite chassis corners so each
covers two adjacent faces and its ~85° blind sector points into the vehicle
body, which is occluded regardless. Together they cover the full 360°
perimeter. Scan plane **~150 mm** above the floor — low enough to detect a
person's legs and to pass over lowered fork tines. Compute the exact mount
poses from the model's real geometry (chassis footprint, wheel positions,
mast and fork extents) and state each pose's justification; do not copy the
numbers below as if they were derived — they are the envelope:

- Chassis footprint is x ∈ [−0.70, +0.70], y ∈ [−0.45, +0.45] with +x the
  drive/steer end and the forks at −x. One scanner belongs at a +x corner and
  one at the diagonally opposite −x corner. Which diagonal (front-left with
  rear-right, or front-right with rear-left) is yours to choose from the
  geometry — say why.
- Sensor names `safety_scanner_front`, `safety_scanner_rear`; topics
  `/forklift/gz/scan_safety_front`, `.../scan_safety_rear`.
- Aperture 275°, oriented so the blind sector faces the body diagonal.
  **Budget: ~275 samples at 10 Hz each** (research of 2026-07-30 for llvmpipe:
  a ≤275° scanner costs far fewer cubemap render passes than a 360° one).
  Range max 5.5 m, min 0.10 m, matching the modelled variant.

**One navigation lidar.** `nav_lidar`, 360°, topic
`/forklift/gz/scan_nav`, **360-540 samples at 10 Hz**, range to suit the
arena and the warehouse world. Mounted elevated on a dedicated link, laterally
offset from the mast centreline to narrow the mast's shadow. This sensor and
only this sensor feeds SLAM.

**All three sensors:** `type="gpu_lidar"` (gz-sim has no CPU ray sensor),
`<visualize>true</visualize>`, and `<gz_frame_id>` set to the sensor's own
link name — without it gz-sim emits scoped `model/link/sensor` frame ids and
downstream TF lookups fail. The existing `safety_scanner` at (0.72, 0, 0.25)
with ±90° is REPLACED, not extended: it covers only the drive end and leaves
the whole fork half blind.

## The coverage evidence file — the real deliverable

Compute and report, from the sensor poses and apertures plus the chassis and
mast geometry:

1. Angular coverage of the vehicle's perimeter, per scanner and combined,
   with the overlap sectors stated.
2. Every residual sector, named, with cause and mitigation. Two are known in
   advance and must appear if the geometry produces them:
   - **Load occlusion** — a pallet on the forks physically blocks a sector of
     the fork-direction protective field. No mounting fixes it; the real-world
     mitigation is a reduced field plus creep speed in the load direction
     (ISO 3691-4 caps muted personnel detection at 0.3 m/s). State it as a
     residual with a mitigation, never as solved.
   - **Mast shadow** — the mast structure occludes a wedge of the navigation
     lidar. Narrowed by lateral offset, not eliminated. Measure the wedge.
   - If the geometry produces others (fork tines at lift height crossing a
     scan plane, the overhead guard, the steer wheel at lock), report them too.
3. Whether the two safety scanners' planes are coplanar and what happens where
   they overlap.

Derive these numerically — a short analysis script committed beside the
evidence is welcome — and say plainly which figures are computed from geometry
and which, if any, were observed in a running simulation. If Gazebo is not
available to you, that is fine and the evidence says so: geometric coverage is
a computation, and a separate brief will confirm it in the running simulation.

## Notes

The safety scanners exist to feed the safety chain. They must not appear in
any navigation consumer — not SLAM, not the global costmap. Reasons to record
once in the README: at 150 mm they see a different world (pallet feet, floor
returns); partial apertures give degenerate scan-match constraints; the load
occludes them; and architecturally their measurement channel is a safety
device's, not a process sensor's.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-04-sensor-layout.md.
