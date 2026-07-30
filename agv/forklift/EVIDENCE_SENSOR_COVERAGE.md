# EVIDENCE — scanner coverage of the forklift model (m5-04)

What the three scanners declared in `model.sdf` can and cannot see, measured
against the vehicle's own geometry, with every residual sector named, caused
and mitigated.

**Every figure in this file is COMPUTED FROM GEOMETRY. Nothing here was
observed in a running simulation.** Gazebo does not run in the container this
was produced in (`gz` and `ros2` are both absent; a parallel brief is
installing the toolchain), and geometric coverage does not need it: a scan
plane is a plane and an occluder is a polygon. What a live run adds is
confirmation that gz renders what this computation says it will, and that is
a separate brief. Section 12 lists exactly what is owed to it.

**This is not a safety claim, in whole or in part.** A computed sight line is
not a protective field. There is no integrity, no OSSD, no fault reaction, no
response time, no stopping distance and no protective-field length anywhere in
this document (invariant 1, and the ADR 0011 claim boundary). The two sensors
named `safety_scanner_*` model a device class. They are not one.

| Item | Value |
|---|---|
| Date | **2026-07-30** |
| Produced by | `agv/forklift/scripts/sensor_coverage.py --step 0.1`, committed beside this file |
| Under test | `agv/forklift/model.sdf` as committed by this change |
| Host | container, Ubuntu 24.04.4 LTS, kernel `6.18.5`, `python3 3.11.15` |
| Gazebo | **not installed and not run** (`which gz` empty) |
| ROS 2 | **not installed and not run** (`which ros2` empty) |
| Dependencies | Python standard library only. No new dependency is introduced |
| Quantisation | bearings swept at 0.1°; every arc below is quantised to that step |

---

## 1. What the layout is, and what each number was derived from

Three planar `gpu_lidar` sensors replace the single 180° scanner that sat at
`(0.72, 0, 0.25)` and covered only the drive end.

| Sensor | Link and frame | Pose (x, y, z, yaw) | Aperture | Samples, rate | Range |
|---|---|---|---|---|---|
| `safety_scanner_front` | `safety_scanner_front_link` | 0.700, 0.450, 0.150, +45° | 275° | 275, 10 Hz | 0.10–5.50 m |
| `safety_scanner_rear` | `safety_scanner_rear_link` | −0.700, −0.450, 0.150, −135° | 275° | 275, 10 Hz | 0.10–5.50 m |
| `nav_lidar` | `nav_lidar_link` | 0.550, −0.400, 1.800, 0° | 360° | 360, 10 Hz | 0.10–8.00 m |

Each number and the geometry that forced it:

**Scan plane z = 0.150 m (both safety scanners).** The free window at the fork
end is bounded below by the top of the lowered tines — `fork_left`/`fork_right`
sit at z = 0.075 with a 0.05 m section, so their top face is **z = 0.100** —
and above by the underside of the chassis box, centred 0.45 with a 0.50 m
height, so **z = 0.200**. 0.150 is the midpoint of that window: 50 mm of
clearance over the tines and 50 mm under the body. The brief's envelope said
"~150 mm"; the model's own geometry puts the optimum at exactly 150 mm, which
is a coincidence worth stating rather than hiding.

**Corners (0.700, 0.450) and (−0.700, −0.450).** These are the corners of the
chassis footprint itself (1.40 × 0.90 → half extents 0.70 and 0.45), not an
envelope. Note that the chassis box does **not** cross the scan plane, so the
mount is a corner bracket in free space under the body shell, and the vehicle's
true plan extremes are elsewhere: the counterweight reaches x = +0.86 and the
tines reach x = −1.875. Section 4 measures the perimeter against that real
outline, not against the chassis box.

**Which diagonal: free, and stated as free.** Every element of this model that
crosses z = 0.150 — both mast rails, the mast body, the steer yoke, the drive
wheel, both rear wheels, the carriage, both tines — is mirror-symmetric about
y = 0. Occlusion therefore cannot choose the diagonal. Front-left with
rear-right is a convention; mirroring both poses gives an exactly equivalent
layout with every residual mirrored to the other side of the fork axis. What
the choice *does* decide is which side the residual of section 4 lands on.

**Link yaw +45° and −135°.** The 275° aperture is symmetric about the sensor's
x axis, so the 85° blind sector is centred on the sensor's −x axis. Yaw +45°
at the front corner therefore points the blind sector at bearing 225°, along
the corner diagonal into the vehicle. Section 9 measures what a different mount
angle would buy: nothing.

**The rotation is in the LINK pose, and the sensor pose is identity.** This is
a correctness point, not a style one. `<gz_frame_id>` names the link, and a
consumer measures the scan's angles in the frame the message names. If the
aperture rotation lived in the `<sensor><pose>` instead, the frame named and
the frame the angles are measured in would differ by the mount angle with
nothing in the message to say so.

**Navigation lidar at z = 1.800, (0.55, −0.40).** Forced by the 360° aperture,
measured in section 8. The lateral offset is the largest that keeps the 0.06 m
mounting post inside the 1.24 × 0.88 guard roof plate, and it stands over the
front-right guard post at (0.55, −0.38), the stiffest point of that plate. At
y = −0.40 the straight-astern ray passes 0.04 m outside the mast body
(|y| ≤ 0.36) and 0.055 m outside the near mast rail.

**Sample counts.** 275 samples over 275° and 360 over 360° are both 1.00°/ray,
the standard resolution for this class of sensor, and the navigation lidar sits
at the **bottom** of the sanctioned 360–540 band because it is the 360° one and
therefore the expensive one to render. Total 910 rays per 100 ms against 181
before. See section 11 for what is not known about that cost.

**Range max 8.00 m on the navigation lidar is coupled, and deliberately
unchanged.** `obstacle_zone.py` reports the scan's own `range_max` as its clear
value, and `docs/interfaces/opcua-nodes.md` §10.5 gives the consuming
plausibility window as 0.05–8.10 m. Raising this past 8.10 would make a clear
horizon read at the PLC as a transducer fault. The arena is 24 × 16 m, so a
longer range would suit it better; that is a cross-layer change and it is
raised in the report, not taken here.

## 2. Method, and the one modelling decision inside it

`scripts/sensor_coverage.py` reads `model.sdf`, resolves each link and geometry
pose, cuts every solid with the horizontal plane of interest, and ray-casts
from each sensor to sample points. A point counts as seen when it is inside the
aperture, inside the range window, and no polygon lies on the segment.

**The occluder set is the VISUAL set, and that is a finding in itself.** A gz
`gpu_lidar` is a rendering sensor: it sees what the renderer draws, which is
`<visual>` geometry. A shape declared only as `<collision>` is invisible to it.
This model has exactly such a shape — the mast's 0.10 × 0.72 × 2.00 collision
box, whose visual counterpart is two 0.09 rails and a crossmember. So every
coverage figure is computed twice:

* **visual set** — what the simulated sensor will report;
* **physical set** — visual plus collision, what the vehicle's body actually
  blocks.

**Every coverage claim below is made on the physical set, because it is the
smaller one.** The divergence is largest for the navigation lidar, where the
simulated shadow is 8.9° and the physical one 29.0°. A live run will reproduce
the 8.9°; the vehicle would obstruct 29.0°. Reconciling the two is an open
question in the report, not something this brief settled.

## 3. Aperture and coplanarity

```
scan planes: front z = 0.150 m, rear z = 0.150 m -> COPLANAR
safety_scanner_front   mounted ( 0.700,  0.450), boresight   45.0 deg: covers [267.5, 182.5) deg, blind [182.5, 267.5) deg
safety_scanner_rear    mounted (-0.700, -0.450), boresight  225.0 deg: covers [ 87.5,   2.5) deg, blind [  2.5,  87.5) deg
(vehicle bearings: 0 deg is +x, the drive end; 180 deg is the fork direction; 90 deg is +y, left)

APERTURE ONLY, occlusion ignored (direction, not sight line):
  front covers  275.0 deg   rear covers  274.9 deg
  union         360.0 deg   overlap      189.9 deg
  union gaps   : none
  overlap arcs : [  87.6,  182.6)  95.0 deg, [ 267.6,    2.5)  94.9 deg
```

By direction alone the pair covers the full circle with 190° of double
coverage, in two 95° lobes — one straddling the left-rear quarter, one
straddling the right-front quarter. 275 + 275 = 550 = 360 + 190 is the
arithmetic, and the measurement reproduces it. **This is aperture only. It is
not coverage**, and the difference between this section and the next one is the
whole point of the document.

**The two planes are coplanar**, both at 0.150 m, so where the apertures
overlap the two scanners measure the same plane and their ranges are directly
comparable — a point seen by both is seen at the same height by both. Two
things follow that are worth writing down once:

* In simulation this is free. A `gpu_lidar` is a depth render, so two scanners
  facing each other across the same plane cannot interfere.
* On real hardware it is not. Coplanar opposed safety scanners are a
  cross-talk case, and the real mitigations are a small vertical offset between
  the planes or the manufacturer's multi-scanner synchronisation. The model
  keeps them coplanar because the geometry is then exact and because the
  simulation cannot reproduce the effect anyway; a hardware build would offset
  one plane and re-measure.

## 4. Measured coverage — sight lines, physical occluder set

Occluders crossing the 0.150 m plane, read out of the model rather than listed
by hand:

```
-- occluders crossing z = 0.15 m, physical set (visual + collision), lift = 0.00 m
   mast/mast_rail_left                x [-0.825, -0.735]  y [ 0.255,  0.345]
   mast/mast_rail_right               x [-0.825, -0.735]  y [-0.345, -0.255]
   mast/mast_collision                x [-0.830, -0.730]  y [-0.360,  0.360]
   steer_link/steer_yoke_visual       x [ 0.470,  0.630]  y [-0.090,  0.090]
   drive_wheel/visual                 x [ 0.434,  0.666]  y [-0.050,  0.050]
   drive_wheel/collision              x [ 0.434,  0.666]  y [-0.050,  0.050]
   rear_wheel_left/visual             x [-0.616, -0.384]  y [ 0.310,  0.410]
   rear_wheel_left/collision          x [-0.616, -0.384]  y [ 0.310,  0.410]
   rear_wheel_right/visual            x [-0.616, -0.384]  y [-0.410, -0.310]
   rear_wheel_right/collision         x [-0.616, -0.384]  y [-0.410, -0.310]
   carriage/visual                    x [-0.850, -0.750]  y [-0.375,  0.375]
   carriage/collision                 x [-0.850, -0.750]  y [-0.375,  0.375]
```

Coverage of the bearings around the model origin, at radius. The indented lines
are the measured reason each scanner missed each uncovered bearing:

```
  radius     front      rear    either      both   uncovered arcs
   1.0 m    206.0d    146.1d    317.2d     34.9d   [ 156.4,  199.2)  42.8 deg
        safety_scanner_front   in the blind sector                 41.4 deg
        safety_scanner_rear    occluded by mast/mast_rail_right    36.3 deg
        safety_scanner_rear    occluded by carriage/visual          3.6 deg
        safety_scanner_rear    occluded by mast/mast_collision      2.9 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   1.4 deg
   2.0 m    242.0d    181.9d    355.0d     68.9d   [ 169.4,  174.4)   5.0 deg
        safety_scanner_rear    occluded by carriage/visual          5.0 deg
        safety_scanner_front   in the blind sector                  3.9 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   1.1 deg
   3.0 m    253.0d    192.6d    360.0d     85.6d   none
   4.0 m    258.3d    197.9d    360.0d     96.2d   none
   5.0 m    240.6d    179.3d    354.3d     65.6d   [ 156.0,  161.7)   5.7 deg
        safety_scanner_front   beyond range                         5.7 deg
        safety_scanner_rear    occluded by carriage/visual          5.7 deg
   5.5 m    171.3d    137.4d    308.7d      0.0d   [ 118.4,  161.0)  42.6 deg, [ 298.4,  307.1)   8.7 deg
        safety_scanner_front   beyond range                        51.3 deg
        safety_scanner_rear    occluded by mast/mast_rail_right    21.2 deg
        safety_scanner_rear    beyond range                        17.4 deg
        safety_scanner_rear    occluded by carriage/visual          7.6 deg
        safety_scanner_rear    occluded by mast/mast_collision      5.1 deg
```

Read it in this order:

* **At 3.0 and 4.0 m the coverage is 360.0° with no gap.** That is the headline
  and it is a measurement, not a claim about blind spots.
* **At 2.0 m one 5.0° arc is missing, at bearings 169.4–174.4°** — just to the
  left of the fork axis. Both scanners miss it: the rear one because the
  carriage stands between it and that bearing, the front one because 3.9° of it
  is past the edge of its aperture and the remaining 1.1° is behind the left
  rear wheel. This is the layout's structural residual, R1 in section 11, and
  it is on the +y side *because* the chosen diagonal puts the rear scanner on
  the −y side. The mirrored layout mirrors it.
* **At 1.0 m the gap grows to 42.8°**, but that circle passes through the fork
  envelope: at radius 1.0 m the bearings 156–199° are points among and between
  the tines, which reach x = −1.875. Coverage of the actual perimeter is
  measured in section 5 and does not degrade like this.
* **At 5.0 and 5.5 m the limit is the range window, not the geometry.** The
  5.50 m range is measured *from the sensor*, and both sensors sit 0.83 m from
  the origin, so a circle of that radius about the origin leaves the far
  scanner's window.

The radius that is covered all the way round, swept properly:

```
DETECTION RADIUS ABOUT THE ORIGIN. The 5.50 m range is measured
from the sensor, and both sensors sit 0.83 m off the origin, so
the radius guaranteed all the way round is smaller. Swept at
1.0 deg bearing steps and 0.05 m radius steps, physical set:
  smallest all-round radius : 4.95 m, at bearing 156.0 deg
  largest                   : 5.50 m
  mean over bearings        : 5.46 m
```

**4.95 m is the number to quote** for what the pair reaches in every direction,
against the 5.50 m the datasheet class would suggest.

The visual set differs from the physical set only in which shape gets the
blame — the arcs are the same to within 0.1° at every radius — because at this
plane the mast's collision box is hidden behind its own rails from both corner
positions. The full visual-set table is in the script output.

## 5. Perimeter coverage, measured on the real outline

The circle measure of section 4 is the wrong instrument in the near field,
because a circle small enough to be near the body is inside it. So the same
computation is run against the vehicle's plan outline grown by a distance:

```
plan outline (convex hull of every visual and collision shape):
  x [-1.875,  0.860]  y [-0.450,  0.450]  8 vertices

  offset    points     front      rear    either
  0.10 m       408     63.0%     50.0%     93.9%
  0.30 m       408     65.4%     52.7%     99.0%
  0.50 m       408     65.4%     53.7%    100.0%
  1.00 m       408     65.7%     54.2%    100.0%
  2.00 m       408     66.4%     54.4%    100.0%

  uncovered at offset 0.10 m: 25 of the sampled points,
    x [-1.975,  0.725]  y [-0.550,  0.550]
    safety_scanner_front   in the blind sector                  14 points
    safety_scanner_rear    occluded by carriage/visual          11 points
    safety_scanner_front   inside range_min                      8 points
    safety_scanner_rear    in the blind sector                   8 points
    safety_scanner_rear    inside range_min                      6 points
    safety_scanner_front   occluded by rear_wheel_left/visual    3 points

  uncovered at offset 0.30 m: 4 of the sampled points,
    x [-2.175, -2.175]  y [ 0.289,  0.340]
    safety_scanner_rear    occluded by carriage/visual           4 points
    safety_scanner_front   in the blind sector                   3 points
    safety_scanner_front   occluded by rear_wheel_left/visual    1 points
```

**From 0.50 m outward the whole perimeter is covered.** At 0.30 m, 1.0% of it
is not, and the uncovered points are all at one place — 0.30 m past the tine
tips on the +y side, the same residual R1 seen from the other measure. At
0.10 m, 6.1% is not, and two of the causes there are the 0.10 m `range_min`
dead zone of the scanners' own housings (R4) and the blind sectors seen at
grazing distance.

## 6. What the vehicle's own motion does to the plane

```
  lift m    steer    either uncovered arcs                         what crosses the plane
   0.000     0.00    355.0d [ 169.4,  174.4)   5.0 deg             carriage
   0.040     0.00    355.0d [ 169.4,  174.4)   5.0 deg             carriage
   0.050     0.00    339.8d [ 169.4,  189.6)  20.2 deg             carriage, fork_left, fork_right
   0.075     0.00    339.8d [ 169.4,  189.6)  20.2 deg             fork_left, fork_right
   0.100     0.00    339.8d [ 169.4,  189.6)  20.2 deg             fork_left, fork_right
   0.110     0.00    360.0d none                                   no lifted part
   0.200     0.00    360.0d none                                   no lifted part
   0.800     0.00    360.0d none                                   no lifted part
   1.600     0.00    360.0d none                                   no lifted part
   0.000     1.31    355.0d [ 169.4,  174.4)   5.0 deg             carriage
   0.000    -1.31    355.0d [ 169.4,  174.4)   5.0 deg             carriage
```

Three results:

1. **The tines cross the scan plane in a 50 mm window of travel, 0.05 to
   0.10 m**, and while they do the gap at the fork end widens from 5.0° to
   20.2° (residual R2). Above 0.10 m of travel they are clear of it.
2. **Above 0.11 m of travel the coverage is 360.0°** — *better* than at rest,
   because the carriage, whose visual spans z = 0.10 to 0.60 at travel zero,
   has left the plane and taken residual R1 with it. The worst case for the
   safety plane is therefore the forks fully lowered, which is also the normal
   travelling posture.
3. **Steering to either mechanical stop changes nothing measurable.** The drive
   wheel and the steer yoke rotate about (0.55, 0) and stay inside the arc they
   already occupy, in a sector the front scanner does not need.

## 7. Load occlusion

The load is modelled on the arena's own `Pallet`: 1.20 m along x, 1.00 m along
y, deck 0.16 m tall, placed with its inboard face against the carriage
(x ∈ [−2.05, −0.85], y ∈ [−0.50, 0.50]).

```
case                             lift crosses z    either   uncovered arcs
pallet on the floor, entering    0.00       yes    320.1d   [ 164.5,  204.4)  39.9 deg
        safety_scanner_front   in the blind sector                 33.9 deg
        safety_scanner_rear    occluded by load/pallet             30.0 deg
        safety_scanner_rear    occluded by carriage/visual          6.5 deg
        safety_scanner_front   occluded by load/pallet              4.9 deg
        safety_scanner_rear    occluded by mast/mast_collision      3.4 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   1.1 deg
pallet on the tines              0.00       yes    320.1d   [ 164.5,  204.4)  39.9 deg
        (same six causes as the row above)
pallet on the tines              0.05       yes    320.1d   [ 164.5,  204.4)  39.9 deg
        safety_scanner_front   in the blind sector                 33.9 deg
        safety_scanner_rear    occluded by fork_right/visual       15.2 deg
        safety_scanner_rear    occluded by load/pallet             14.8 deg
        safety_scanner_rear    occluded by carriage/visual          6.5 deg
        safety_scanner_front   occluded by load/pallet              4.9 deg
        safety_scanner_rear    occluded by mast/mast_collision      3.4 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   1.1 deg
pallet on the tines              0.10        no    339.8d   [ 169.4,  189.6)  20.2 deg
        safety_scanner_front   in the blind sector                 19.1 deg
        safety_scanner_rear    occluded by fork_right/visual       17.6 deg
        safety_scanner_rear    occluded by fork_left/visual         2.6 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   1.1 deg
pallet on the tines              0.30        no    360.0d   none
pallet on the tines              1.60        no    360.0d   none
```

(One elision, marked: the second row's cause list is identical to the first's
and is not repeated.)

**A pallet in the load direction costs 39.9° of the plane**, centred on the
fork axis, and the arc straddles it asymmetrically (164.5–204.4°) because the
front scanner's aperture edge cuts one side of it.

The honest caveat, and it cuts against the model rather than for it: a 2D scan
plane is occluded only by what intersects it, and this model's pallet is a
rectangular deck that clears the 0.150 m plane once the tines are 0.06 m up.
That is why the table shows the occlusion vanishing at 0.30 m of travel. A real
load is not a rectangle: it overhangs the tines, sags, is strapped, and may
carry film that hangs below the deck. **Load occlusion is a residual of the
installation, not an artefact that a lift command clears** — ISO 3691-4 treats
it as something handled by field switching and speed, and section 11 records it
that way (R3).

## 8. Navigation lidar — shadow, and why it is where it is

```
-- visual set
   lift 0.00 m: shadow   8.9 deg, fork axis (180 deg) clear, arcs [ 149.9,  154.6)   4.7 deg, [ 173.6,  177.8)   4.2 deg
                width of each shadow at 5 m range: 0.41 m, 0.37 m
   lift 1.40 m: shadow  29.8 deg, fork axis (180 deg) clear, arcs [ 149.2,  179.0)  29.8 deg
                width of each shadow at 5 m range: 2.57 m

-- physical set
   lift 0.00 m: shadow  29.0 deg, fork axis (180 deg) clear, arcs [ 149.4,  178.4)  29.0 deg
                width of each shadow at 5 m range: 2.50 m
   lift 1.40 m: shadow  29.8 deg, fork axis (180 deg) clear, arcs [ 149.2,  179.0)  29.8 deg
                width of each shadow at 5 m range: 2.57 m
```

(Elided and marked: the rows for lift 0.80, 1.18 and 1.20 m are identical to
the lift 0.00 m row of the same set, and the lift 1.60 m row is identical to
the 1.40 m row. The threshold is the carriage crossing z = 1.80, which starts
at 1.20 m of travel and shows in the measurement from 1.21 m up.)

* **The mast shadow is 29.0° of the 360°, or 2.50 m wide at 5 m range**, on the
  physical set. The simulated sensor will show 8.9° in two lobes, because only
  the two 0.09 m rails are drawn. That divergence is the single largest one in
  this document.
* **The fork axis itself is clear in every case**, which is what the lateral
  offset bought: the straight-astern ray passes outside the mast body. On the
  centreline the same computation gives 31.5° and the shadow straddles the fork
  axis. The offset is worth 2.5° of shadow and, more usefully, the sight line
  the vehicle uses to see the rack it is reversing into.
* **A raised carriage adds to it above 1.20 m of travel** (residual R5): the
  carriage crosses z = 1.80 for travel between 1.20 and 1.60 m, merging the two
  visual lobes into one 29.8° wedge.

Why the mount is elevated at all — same computation, candidate positions:

```
candidate mount                                shadow     usable
ahead of the counterweight  (0.90, 0.00, 0.55)    168.5 d    191.5 d
beside the chassis          (0.00, 0.50, 0.55)    171.9 d    188.1 d
inside the chassis band     (0.00, 0.00, 0.45) mount is inside base_link/chassis_visual
on the guard deck           (0.30, -0.40, 0.75)     66.9 d    293.1 d
under the guard roof        (0.30, -0.40, 1.20)     66.9 d    293.1 d
on the guard roof, centred  (0.55, 0.00, 1.80)     31.5 d    328.5 d
on the guard roof, aft      (-0.50, -0.40, 1.80)     66.2 d    293.8 d
AS DECLARED                 (0.55, -0.40, 1.80)     29.0 d    331.0 d
```

A 360° aperture is only worth its render cost where the sensor clears the body.
Any mounting inside the chassis height band loses **168 to 172°** of it — a
360° sensor behaving like a 190° one. On the guard deck, under the roof, the
four guard posts and the mast cost 66.9°. Above the roof the cost is 29.0°.
**The elevated mount is forced by the aperture decision, not chosen for
convenience** — and it has a consequence of its own, in section 10.

## 9. Mount angle sensitivity — the 45° orientation is already optimal

The design fixes the blind sector on the corner diagonal. This measures what
rotating both scanners together would buy, so that the choice is an informed
one (δ is added to both mount yaws; coverage is the union, physical set):

```
   delta   at 1.5 m   at 2.0 m   at 3.0 m gap at 2 m
  -10.0d     329.6d     342.6d     354.9d   [ 157.0,  174.4)  17.4 deg
   -7.5d     333.2d     345.9d     358.0d   [ 160.3,  174.4)  14.1 deg
   -5.0d     336.9d     349.3d     360.0d   [ 163.7,  174.4)  10.7 deg
   -2.5d     340.6d     352.6d     360.0d   [ 167.0,  174.4)   7.4 deg
    0.0d     343.2d     355.0d     360.0d   [ 169.4,  174.4)   5.0 deg
        safety_scanner_rear    occluded by carriage/visual          5.0 deg
        safety_scanner_front   in the blind sector                  3.9 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   1.1 deg
    2.5d     343.2d     355.0d     360.0d   [ 169.4,  174.4)   5.0 deg
    5.0d     343.2d     355.0d     360.0d   [ 169.4,  174.4)   5.0 deg
        safety_scanner_rear    occluded by carriage/visual          5.0 deg
        safety_scanner_front   occluded by rear_wheel_left/visual   2.2 deg
        safety_scanner_front   occluded by mast/mast_rail_left      2.0 deg
        safety_scanner_front   occluded by mast/mast_collision      0.8 deg
    7.5d     343.2d     355.0d     360.0d   [ 169.4,  174.4)   5.0 deg
   10.0d     343.2d     355.0d     360.0d   [ 169.4,  174.4)   5.0 deg
```

Rotating the blind sectors *away* from the diagonal costs coverage
monotonically. Rotating them *into* it buys exactly nothing, and the cause
tally says why: at δ = 0 the front scanner misses 3.9° of the residual on
aperture, and at δ = +5° that aperture limit is gone but the mast rail, the
mast body and the left rear wheel have taken its place. **The residual is
structural, and 45° is at the optimum.**

## 10. Consequences for consumers, stated rather than left to be found

**a. `/forklift/scan` is now the navigation lidar, and its plane moved from
0.25 m to 1.80 m.** The old 180° scanner was the only source of that topic and
it is gone. The bridge in `launch/vehicle.launch.py` now carries
`/forklift/gz/scan_nav` onto it, which keeps `obstacle_zone.py` running
untouched, but the comfort zone it computes is now evaluated at 1.80 m. In
`sim/worlds/forklift_arena.sdf`, whose perimeter walls stop at 0.60 m and whose
tallest object other than one pillar is a 1.00 m crate, that sector will be
empty and the zone will read clear. **This is a functional regression of the M4
teleop comfort stop and it needs an owner decision**, carried in the report with
its options. It is stated here so that nobody discovers it as a mystery.

**b. The arena cannot map at 1.80 m.** Feature tops measured against the
navigation plane:

```
  perimeter walls  top z = 0.60 m
  AisleCrate       top z = 0.90 m
  CrateNorth       top z = 1.00 m
  LoadBox          top z = 0.86 m
  PillarSouth      top z = 2.60 m
```

Exactly one feature of the current arena reaches the navigation plane. SLAM
against a single pillar is not SLAM. `sim/` is outside this brief's write
scope, so the request — raise the perimeter walls or add tall features — is in
the report. `sim/worlds/warehouse.sdf`, whose racks are 2.0 m and whose walls
are 2.5 m, does present features at this plane.

**c. The safety scanners are not bridged into ROS, deliberately.** Their gz
topics are a contract and live in `model.sdf`, `config.yaml` and the README
table, but `vehicle.launch.py` does not carry them into the ROS graph. The
device they model emits an OSSD pair on copper, and the simulation analogue of
that path is the PLCSIM Advanced API into the F-program (ADR 0011 decision 2).
Bridging them would put a safety device's measurement channel on the process
network where any node could subscribe and quietly become a consumer.

**d. TF for three sensor frames does not exist yet.** Each scan now names its
own link — `safety_scanner_front_link`, `safety_scanner_rear_link`,
`nav_lidar_link` — and nothing in this directory publishes a transform from
`forklift/base_link` to any of them. SLAM and Nav2 will need them. The offsets
are constants and are in the table in section 1.

## 11. Residual sectors — every one, with cause and mitigation

No sector of this vehicle's surroundings is claimed to be covered by
construction. These are the ones the geometry produces.

| # | Residual | Measured | Cause | Mitigation |
|---|---|---|---|---|
| **R1** | Left of the fork axis, bearings 169.4–174.4°, at 2.0 m radius; 0.30 m past the left tine tip on the perimeter measure | 5.0° at 2.0 m, 0° at 3.0 m and beyond; 1.0% of the 0.30 m offset perimeter | The carriage (x −0.85…−0.75, y ±0.375) stands between the rear scanner and those bearings; the front scanner reaches them only at the edge of its aperture and is then behind the left rear wheel | Structural, not tunable: section 9 shows no mount angle removes it. It closes at 3.0 m, and it closes entirely once the carriage lifts above 0.11 m. Mirroring the diagonal moves it to the other side, it does not remove it. A field design must treat 169–175° at close range as unmonitored |
| **R2** | Fork end, bearings 169.4–189.6°, while the carriage travel is between 0.05 and 0.10 m | 20.2° at 2.0 m, against 5.0° at travel zero | The tines themselves cross the 0.150 m scan plane in that 50 mm window: tine top is 0.10 m at travel zero and the plane is 0.15 m | Travel through that window rather than parking in it. Above 0.11 m of travel coverage is 360.0°. A field design that switches on lift height must not treat 0.05–0.10 m as equivalent to 0 |
| **R3** | Load direction, bearings 164.5–204.4°, whenever a load intersects the plane | 39.9° at 2.0 m, 30.0° of it blamed on the pallet itself | A pallet on the tines, or a pallet on the floor being entered, physically stands in the fork-direction field. No mounting fixes this: the load is between the scanner and the space behind it | **Not solved, and never claimed as solved.** The real-world handling is a reduced protective field in the load direction plus creep speed while personnel detection is reduced — ISO 3691-4 caps a truck with muted personnel-detection means at 0.3 m/s. This model's rectangular pallet clears the plane above 0.06 m of lift; a real load with overhang or film does not, so the residual is the installation's, not the lift command's |
| **R4** | A 0.10 m annulus around each scanner housing, at the two chassis corners | 8 and 6 of 408 perimeter points at the 0.10 m offset | `range_min` of the modelled sensor class. A return closer than that is not a measurement | Inherent to the device. The corner mounting means the dead zone sits over the body corner rather than over the approach; a real installation adds mechanical protection there. Note also that `obstacle_zone.py` classes a below-`range_min` return as INVALID and can skip it — recorded already in EVIDENCE_MODEL §6.1 as an open owner question |
| **R5** | Navigation lidar, bearings 149.4–178.4° at all times, widening to 149.2–179.0° above 1.20 m of carriage travel | 29.0° physical, 2.50 m wide at 5 m; 29.8° with the carriage raised | The mast body, and above 1.20 m of travel the carriage crossing z = 1.80 | Narrowed by the lateral offset from 31.5° and moved off the fork axis, **not eliminated**. The lift component is avoided by navigating with the carriage down, which is the normal travelling posture. Localisation must tolerate a permanent 29° occlusion in the load direction — it is one sensor on a vehicle with a mast, and every forklift has this |
| **R6** | Anything outside 4.95 m of the model origin, in the worst direction | 4.95 m all-round, 5.46 m mean, against the sensor's own 5.50 m | The 5.50 m range is measured from the sensor and both sensors are 0.83 m off the origin | Quote 4.95 m, not 5.50 m, as what the pair reaches in every direction. Nothing about a protective field follows from either number |
| **R7** | Everything the simulated sensor sees *through* that the vehicle would block | Simulated shadow 8.9° against physical 29.0° at the navigation plane | A `gpu_lidar` renders `<visual>` geometry; the mast's 0.72 m wide body is `<collision>` only | Every claim in this document is made on the physical set. The divergence itself is an open question in the report: reconcile the mast's two representations, in one direction or the other, before any live coverage figure is quoted |

Two further sectors were looked for and are **not** present in this geometry,
which is worth recording so the next reader does not re-derive them: the
overhead guard does not reach either scan plane (posts z 0.70–1.65, roof
1.65–1.71, both scan planes 0.150 and 1.800 m), and the steer wheel at either
mechanical stop changes no measured arc.

## 12. What this does not establish

1. **Nothing about safety.** No protective field, no OSSD, no response time, no
   stopping distance, no PL, no Category, no PFH. A sight line computed from
   two polygons is not a safety function (invariant 1, ADR 0011 decision 5).
2. **Nothing observed.** No Gazebo, no renderer, no ROS 2, no message. The live
   brief owes: that all three sensors advertise and publish; that
   `<gz_frame_id>` puts the link name in `frame_id` rather than a scoped
   `model/link/sensor` string; that the measured shadow arcs appear in the
   ranges where this document says they will; and that a raised carriage
   produces R5.
3. **Nothing about cost.** The ray budget rises from 181 to 910 per 100 ms and
   the sensor count from one to three, on a host that renders with llvmpipe.
   The real-time factor that buys is **not measured here**, and `model.sdf`'s
   own rule — no sample count and no update rate goes up without a measurement
   — applies to the next person as much as to this change.
4. **Nothing about the world.** Only the vehicle occludes itself in this
   computation. Racking, other vehicles, people, dust and reflectivity are the
   world's business and a scenario's.
5. **Nothing about a real sensor's behaviour.** No beam divergence, no
   incidence-angle dropout, no mixed pixels at edges, no cross-talk between
   the two coplanar scanners. A rendered depth image has none of these and a
   real scanner has all of them.
6. **Nothing about the load beyond one rectangle.** R3 is measured with one
   pallet geometry taken from the arena. Overhang, film and irregular loads are
   not modelled.
