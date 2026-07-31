# M5 forklift — sensor layout and lidar beams

Gazebo Harmonic captures of the M5 vehicle: two diagonal safety scanners and
one navigation lidar on the in-house forklift, in the commissioning arena.
Provenance and method are in `../CREDITS.md`.

| Image | What it shows |
|---|---|
| `sensor-layout-diagonal.png` | The clearest layout view: camera on the perpendicular to the scanner diagonal at 1.05 m, so both safety scanner housings sit at the extremes of the silhouette with the navigation lidar on the guard roof between them. |
| `forklift-threequarter.png` | Three-quarter view from the drive end. |
| `forklift-topdown.png` | Plan view, +x right and +y up, matching the top view in `agv/forklift/model.sdf`. The safety scanners are **not** visible here: they sit at z 0.02–0.13 beneath a 1.24 × 0.88 guard roof, so only the navigation lidar head reads from directly above. That is geometry, not a capture fault. |
| `beams-safety-scanner-front.png` | The front safety scanner's measurement channel, Rays mode: the 275° aperture, the ~85° blind sector notched back into the vehicle body, the 5.5 m horizon, and the pillar's shadow. |
| `beams-nav-lidar.png` | The navigation lidar, Rays mode: the full 360° disc from the 1.80 m plane, with the mast shadow wedge and the pillar shadow. |
| `arena-context.png` | The whole 24 × 16 m hall — drive aisle, pallet zone marking, safety zone outline, pillar, crates. |
| `arena-with-beams.png` | The same hall with the scanner fan sweeping across the props. |

Two properties of the `VisualizeLidar` GUI plugin shape what these images can
show, and both are the plugin's, not the model's: it takes no topic from SDF
(the topic is chosen in its own combo box), and it draws **one topic at a
time**, so no single frame can carry all three scanners. Rays drawn in
magenta or red are non-hitting rays, drawn out to maximum range.

These are design and communication images. The gate's measured evidence —
angular coverage, residual sectors, render budget — lives with the work:
`agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` and `sim/worlds/evidence/`.
