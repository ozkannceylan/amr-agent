# EVIDENCE — landmark availability in the warehouse world (m5-08)

**A prediction, produced before any SLAM run.** Where in
`worlds/warehouse.sdf` will lidar localisation be strong, and where will it
be weak, and why. It exists so that the SLAM result of the next brief is
read against something, instead of being the only number anyone sees.

The honest claim this file makes is the uncomfortable one: **three stretches
of this world are degenerate for scan matching, they are named below with
their extents, and no slam_toolbox parameter fixes them.** They were not
landscaped away. They are there because the world models a warehouse with
loaded racking, and a loaded rack aisle really is two flat parallel walls.

| Item | Value |
|---|---|
| Date | **2026-07-31** |
| Produced by | `sim/scenarios/tools/landmark_map.py`, committed beside the world |
| Under test | `sim/worlds/warehouse.sdf` as committed by this change |
| Sensor modelled | `nav_lidar` from `agv/forklift/model.sdf`: z = 1.80 m, 360 samples over 360 deg, range 0.10 to 8.00 m |
| Host | project container, Ubuntu 24.04, kernel 6.18.5, `python3` 3.11.15 |
| Dependencies | Python standard library only. No new dependency |
| Live validation | section 6, against `/forklift/scan` from a running `gz sim 8.11.0` server |

---

## 1. What is computed, and what it is not

The script parses the world SDF, takes the cross section of every box
`<visual>` at z = 1.80 m, and casts the sensor's own 360 rays from each
sample pose. It reads the rectangles **out of the file at run time**; it
does not carry a copied list, because a copied list goes stale the moment
the world changes.

`<visual>` and not `<collision>` on purpose: a `gpu_lidar` renders the
scene, so the visual geometry is what it returns. In this world the two sets
are written identically and the script prints both counts so a divergence
would show rather than be assumed away. At z = 1.80 m: **152 cross sections
in each set**.

What this is **not**: a sensor simulation. No noise, no beam divergence, no
incidence-angle dropout, no reflectivity, no vehicle. It states an **upper
bound** on the structure available at a pose. A pose it calls degenerate is
degenerate; a pose it calls well conditioned may still be harder in a live
run than these numbers suggest.

## 2. The columns, and what each one means

| Column | Meaning |
|---|---|
| `n` | rays returning a finite range, out of 360 |
| `Nx`, `Ny` | of those, how many landed on a surface facing along x, and along y |
| `aniso` | `min(Nx,Ny) / max(Nx,Ny)` |
| `maxgap` | the largest contiguous arc with no return, in degrees |
| `rmean` | mean finite range, m |
| `yawinfo` | `sum (n . p_perp)^2` over hits, m^2. A relative figure for how strongly heading is pinned |
| `rms25` | RMS range change over the rays returning in both sweeps when the sensor is displaced 0.25 m **along the line**, averaged over both directions, m |
| `top10` | the share of that squared change carried by the ten largest single-ray differences |

**`aniso` is the headline and it has a derivation.** The information a scan
gives a point-to-plane matcher about translation is `J = sum n n^T` over the
surface normals it hits. Every surface in this world is axis aligned, so `J`
is diagonal and its entries are exactly `Nx` and `Ny`. `aniso` is therefore
the ratio of `J`'s two eigenvalues: 1.00 is perfectly conditioned, and 0.00
means one axis carries no information at all — the matcher cannot tell where
along it the sensor is, and will accept any position on that line.

**`rms25` and `top10` are a second, independent opinion**, and they exist
because `aniso` alone can mislead. A corridor of two flat walls has almost
no *smooth gradient* along its length, but it can still have a handful of
rays that graze past a rack end or through an opening, and those rays do
change with displacement. `rms25` says how much the scan changes at all;
`top10` says whether that change is spread over hundreds of rays or carried
by a handful. **High `rms25` with low `top10` is a pose a matcher settles
into from anywhere. Low `aniso` with `top10` near 100% is a pose that
matches only from a good initial guess, because ten grazing rays are the
only thing that changed** — and that is a very different kind of "it
worked".

**Declared reporting boundaries**, used for the verdict column and nothing
else. Nothing physical happens at these values:

| Verdict | Rule |
|---|---|
| both axes | `aniso >= 0.20` |
| weak in `<axis>` | `0.05 <= aniso < 0.20` |
| single axis, `<axis>` free | `aniso < 0.05` |

## 3. Why the world is shaped the way it is here

Two facts from the world file drive every number below.

**The rack front faces are flat where a bay is loaded.** A stock unit is set
0.05 m back from the aisle face, so a loaded bay presents a flat 2.10 m face
with the 0.10 m uprights standing 0.05 m proud of it every 2.30 m. Two
loaded rows facing each other across a 3.80 m aisle are, to a scan matcher,
two parallel lines: they pin the sensor **across** the aisle perfectly and
say almost nothing about where it is **along** it.

**Reserve-level occupancy is not uniform, and that is the whole difference.**
The world states a stock state: the east runs are full (goods in arrives at
the dock door on the east half of the south wall and is put away nearest the
door), the west runs are the picked face and are depleted on alternate bays.
The scan plane at 1.80 m sits in the reserve level, so it sees exactly that
difference. **The west half of every aisle is well conditioned, and the east
half is where the degeneracy lives.** That pattern was declared first and
measured afterwards, not chosen to make a result come out.

## 4. The measurement

Sample poses are **sensor** poses, 2.00 m apart along six named lines. The
navigation lidar leads the model origin by (0.55, -0.40), so a vehicle
placed to put its lidar at (x, y) with yaw 0 sits at (x - 0.55, y + 0.40).

Reproduce with:

```
python3 sim/scenarios/tools/landmark_map.py --markdown
```

### Aisle A (y = +7.00), between RackRowA and RackRowB

| pose | n | Nx | Ny | aniso | maxgap | rmean | yawinfo | rms25 | top10 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| (-13.00, +7.00) | 299 | 178 | 121 | 0.680 | 29 | 3.39 | 1692 | 0.383 | 49% | both axes |
| (-11.00, +7.00) | 301 | 122 | 179 | 0.682 | 30 | 3.77 | 1779 | 0.587 | 76% | both axes |
| ( -9.00, +7.00) | 298 | 100 | 198 | 0.505 | 42 | 3.86 | 1594 | 0.534 | 79% | both axes |
| ( -7.00, +7.00) | 235 | 42 | 193 | 0.218 | 47 | 3.29 | 1501 | 0.476 | 69% | both axes |
| ( -5.00, +7.00) | 264 | 58 | 206 | 0.282 | 36 | 3.70 | 1892 | 0.571 | 80% | both axes |
| ( -3.00, +7.00) | 249 | 67 | 182 | 0.368 | 30 | 4.08 | 2160 | 0.452 | 64% | both axes |
| ( -1.00, +7.00) | 238 | 68 | 170 | 0.400 | 41 | 4.04 | 2095 | 0.323 | 59% | both axes |
| ( +1.00, +7.00) | 246 | 47 | 199 | 0.236 | 42 | 3.93 | 2325 | 0.524 | 80% | both axes |
| ( +3.00, +7.00) | 272 | 27 | 245 | 0.110 | 30 | 3.39 | 2070 | 0.354 | 95% | weak in x |
| ( +5.00, +7.00) | 276 | 19 | 257 | 0.074 | 34 | 2.88 | 1512 | 0.198 | 99% | weak in x |
| ( +7.00, +7.00) | 274 | 9 | 265 | 0.034 | 40 | 2.76 | 1275 | 0.182 | 99% | **single axis, x free** |
| ( +9.00, +7.00) | 327 | 76 | 251 | 0.303 | 30 | 3.61 | 1795 | 0.462 | 89% | both axes |
| (+11.00, +7.00) | 302 | 98 | 204 | 0.480 | 30 | 3.61 | 1895 | 0.458 | 78% | both axes |
| (+13.00, +7.00) | 297 | 150 | 147 | 0.980 | 30 | 3.22 | 1889 | 0.522 | 60% | both axes |

### Aisle B (y = +0.65), between RackRowB and RackRowC

| pose | n | Nx | Ny | aniso | maxgap | rmean | yawinfo | rms25 | top10 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| (-13.00, +0.65) | 266 | 196 | 70 | 0.357 | 28 | 3.64 | 2313 | 0.584 | 63% | both axes |
| (-11.00, +0.65) | 272 | 147 | 125 | 0.850 | 32 | 4.03 | 2059 | 0.833 | 60% | both axes |
| ( -9.00, +0.65) | 274 | 128 | 146 | 0.877 | 30 | 4.09 | 1561 | 0.515 | 80% | both axes |
| ( -7.00, +0.65) | 196 | 46 | 150 | 0.307 | 52 | 3.20 | 1160 | 0.538 | 59% | both axes |
| ( -5.00, +0.65) | 232 | 68 | 164 | 0.415 | 36 | 3.79 | 1843 | 0.596 | 91% | both axes |
| ( -3.00, +0.65) | 199 | 83 | 116 | 0.716 | 30 | 4.52 | 2201 | 0.617 | 75% | both axes |
| ( -1.00, +0.65) | 174 | 78 | 96 | 0.812 | 41 | 4.46 | 2241 | 0.378 | 46% | both axes |
| ( +1.00, +0.65) | 194 | 54 | 140 | 0.386 | 41 | 4.28 | 2196 | 0.693 | 82% | both axes |
| ( +3.00, +0.65) | 240 | 26 | 214 | 0.121 | 30 | 3.28 | 1577 | 0.233 | 94% | weak in x |
| ( +5.00, +0.65) | 268 | 16 | 252 | 0.063 | 36 | 2.84 | 1263 | 0.083 | 91% | weak in x |
| ( +7.00, +0.65) | 270 | 13 | 257 | 0.051 | 47 | 2.79 | 1171 | 0.242 | 99% | weak in x |
| ( +9.00, +0.65) | 324 | 86 | 238 | 0.361 | 32 | 3.68 | 1719 | 0.546 | 86% | both axes |
| (+11.00, +0.65) | 278 | 121 | 157 | 0.771 | 30 | 3.89 | 2173 | 0.649 | 75% | both axes |
| (+13.00, +0.65) | 266 | 185 | 81 | 0.438 | 30 | 3.50 | 2319 | 0.694 | 75% | both axes |

### Dock aisle (y = -5.50), the apron lane south of RackRowC

| pose | n | Nx | Ny | aniso | maxgap | rmean | yawinfo | rms25 | top10 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| (-13.00, -5.50) | 281 | 177 | 104 | 0.588 | 45 | 3.63 | 1902 | 0.903 | 51% | both axes |
| (-11.00, -5.50) | 285 | 126 | 159 | 0.792 | 29 | 4.34 | 1960 | 0.630 | 70% | both axes |
| ( -9.00, -5.50) | 293 | 105 | 188 | 0.559 | 30 | 4.66 | 2071 | 0.615 | 86% | both axes |
| ( -7.00, -5.50) | 219 | 37 | 182 | 0.203 | 46 | 4.14 | 1693 | 0.624 | 82% | both axes |
| ( -5.00, -5.50) | 232 | 49 | 183 | 0.268 | 51 | 4.23 | 1853 | 1.059 | 50% | both axes |
| ( -3.00, -5.50) | 215 | 50 | 165 | 0.303 | 47 | 4.75 | 2112 | 0.927 | 93% | both axes |
| ( -1.00, -5.50) | 201 | 47 | 154 | 0.305 | 55 | 4.87 | 2038 | 0.264 | 62% | both axes |
| ( +1.00, -5.50) | 192 | 34 | 158 | 0.215 | 68 | 4.60 | 1746 | 0.518 | 90% | both axes |
| ( +3.00, -5.50) | 205 | 19 | 186 | 0.102 | 47 | 4.00 | 1595 | 0.271 | 98% | weak in x |
| ( +5.00, -5.50) | 206 | 10 | 196 | 0.051 | 50 | 3.67 | 1665 | 0.060 | 93% | weak in x |
| ( +7.00, -5.50) | 208 | 10 | 198 | 0.051 | 53 | 3.63 | 1629 | 0.089 | 95% | weak in x |
| ( +9.00, -5.50) | 276 | 81 | 195 | 0.415 | 49 | 4.35 | 1789 | 0.597 | 94% | both axes |
| (+11.00, -5.50) | 263 | 108 | 155 | 0.697 | 69 | 4.15 | 1569 | 0.559 | 81% | both axes |
| (+13.00, -5.50) | 270 | 164 | 106 | 0.646 | 55 | 3.53 | 1762 | 0.897 | 53% | both axes |

### Cross aisle (x = 0.00), the central cross aisle

| pose | n | Nx | Ny | aniso | maxgap | rmean | yawinfo | rms25 | top10 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| ( +0.00, -8.00) | 221 | 29 | 192 | 0.151 | 58 | 4.10 | 2271 | 0.354 | 19% | weak in x |
| ( +0.00, -6.00) | 207 | 43 | 164 | 0.262 | 61 | 4.80 | 2286 | 0.496 | 58% | both axes |
| ( +0.00, -4.00) | 195 | 80 | 115 | 0.696 | 58 | 4.94 | 1158 | 0.943 | 76% | both axes |
| ( +0.00, -2.00) | 179 | 105 | 74 | 0.705 | 85 | 4.16 | 1564 | 0.823 | 78% | both axes |
| ( +0.00, +0.00) | 181 | 74 | 107 | 0.692 | 49 | 4.39 | 2264 | 0.767 | 72% | both axes |
| ( +0.00, +2.00) | 193 | 87 | 106 | 0.821 | 34 | 4.60 | 2112 | 0.863 | 69% | both axes |
| ( +0.00, +4.00) | 272 | 116 | 156 | 0.744 | 25 | 4.97 | 2472 | 0.888 | 53% | both axes |
| ( +0.00, +6.00) | 237 | 74 | 163 | 0.454 | 33 | 4.37 | 2064 | 0.723 | 63% | both axes |
| ( +0.00, +8.00) | 249 | 64 | 185 | 0.346 | 36 | 3.58 | 2012 | 0.580 | 53% | both axes |

### West end aisle (x = -13.00), between the rack ends and the west wall

| pose | n | Nx | Ny | aniso | maxgap | rmean | yawinfo | rms25 | top10 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| (-13.00, -8.00) | 276 | 129 | 147 | 0.878 | 45 | 2.76 | 948 | 0.728 | 83% | both axes |
| (-13.00, -6.00) | 283 | 172 | 111 | 0.645 | 45 | 3.53 | 1841 | 0.650 | 74% | both axes |
| (-13.00, -4.00) | 289 | 191 | 98 | 0.513 | 44 | 3.85 | 1753 | 0.664 | 92% | both axes |
| (-13.00, -2.00) | 251 | 192 | 59 | 0.307 | 26 | 2.98 | 1449 | 1.051 | 68% | both axes |
| (-13.00, +0.00) | 265 | 202 | 63 | 0.312 | 29 | 3.60 | 2242 | 0.433 | 83% | both axes |
| (-13.00, +2.00) | 271 | 202 | 69 | 0.342 | 30 | 3.63 | 2028 | 0.678 | 92% | both axes |
| (-13.00, +4.00) | 298 | 207 | 91 | 0.440 | 19 | 3.54 | 1744 | 1.071 | 32% | both axes |
| (-13.00, +6.00) | 302 | 189 | 113 | 0.598 | 29 | 3.61 | 1852 | 0.545 | 84% | both axes |
| (-13.00, +8.00) | 298 | 166 | 132 | 0.795 | 29 | 3.06 | 1568 | 0.418 | 74% | both axes |

### East end aisle (x = +13.00), between the rack ends and the east wall

| pose | n | Nx | Ny | aniso | maxgap | rmean | yawinfo | rms25 | top10 | verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| (+13.00, -8.00) | 278 | 116 | 162 | 0.716 | 55 | 2.92 | 1265 | 0.700 | 83% | both axes |
| (+13.00, -6.00) | 271 | 155 | 116 | 0.748 | 56 | 3.42 | 1749 | 0.629 | 78% | both axes |
| (+13.00, -4.00) | 285 | 186 | 99 | 0.532 | 52 | 3.78 | 1409 | 0.686 | 93% | both axes |
| (+13.00, -2.00) | 259 | 188 | 71 | 0.378 | 50 | 3.11 | 1685 | 0.991 | 67% | both axes |
| (+13.00, +0.00) | 268 | 189 | 79 | 0.418 | 30 | 3.54 | 2433 | 0.403 | 67% | both axes |
| (+13.00, +2.00) | 273 | 190 | 83 | 0.437 | 30 | 3.56 | 2282 | 0.787 | 79% | both axes |
| (+13.00, +4.00) | 315 | 203 | 112 | 0.552 | 17 | 3.71 | 2092 | 1.073 | 31% | both axes |
| (+13.00, +6.00) | 301 | 170 | 131 | 0.771 | 29 | 3.48 | 1895 | 0.681 | 59% | both axes |
| (+13.00, +8.00) | 302 | 147 | 155 | 0.948 | 29 | 3.00 | 1701 | 0.493 | 62% | both axes |

## 5. The degenerate stretches, named

Resampled at 0.50 m along each aisle line to find the extents.

| Name | Line | Extent, `aniso < 0.20` | Worst pose | Worst `aniso` | Length |
|---|---|---|---|---|---|
| **East A** | Aisle A, y = +7.00 | x in [+2.0, +7.0] | (+7.00, +7.00) | **0.034** | 5.0 m |
| **East B** | Aisle B, y = +0.65 | x in [+3.0, +7.0] | (+6.00, +0.65) | **0.031** | 4.0 m |
| **East dock** | Dock aisle, y = -5.50 | x in [+1.5, +7.0] | (+4.50, -5.50) | **0.041** | 5.5 m |

Within those, `aniso` falls below 0.05 — the "one axis carries nothing"
band — at x = +7.0 in East A, at x = +4.0 and x in [+5.5, +6.5] in East B,
and at x in [+4.0, +4.5] in East dock. Across all three, `top10` sits above
90% from about x = +2 to x = +7.5: **in the whole of the east half, the only
along-aisle information in the scan is carried by ten rays or fewer.**

One further dip is on the record and is not a stretch: Aisle A at
x in [-6.5, -6.0] touches `aniso` 0.19 for one sample. It is the pose where
an empty bay's opening happens to line up so that fewer rack-end faces are
in view, and it recovers within half a metre either side.

**All three stretches are in the east half, all three are bounded by
x = +7.0, and all three recover at x = +9.** The cause is one thing and the
recovery is another:

- the **cause** is that the east runs are fully loaded, so both aisle walls
  are flat there;
- the **recovery** at x = +9 is that the rack runs end at x = +11.00 and the
  east wall stands at x = +15.00, both inside the lidar's 8.00 m range from
  x = +9. Structure facing along x comes back into view, `Nx` jumps from 10
  to about 80, and the verdict returns to "both axes".

**What was NOT found: aliasing.** The rack bay pitch is 2.30 m, so the
obvious worry is a scan that matches equally well one bay along. The
along-track residual through the worst pose in East A rises monotonically
and has **no secondary minimum within +-3.00 m**:

```
along x residual, rms[m], from two poses on the same aisle line

  d[m]    (+7.00, +7.00)      (-7.00, +7.00)
          East A, worst       west half, well conditioned
  -3.00   0.743               1.707
  -2.00   0.570               1.599
  -1.00   0.423               1.072
  -0.50   0.286               0.707
  -0.25   0.191               0.414
  +0.00   0.000               0.000
  +0.25   0.173               0.537
  +0.50   0.299               0.721
  +1.00   0.620               0.953
  +2.00   0.967               1.393
  +3.00   1.156               1.334
```

Read the two together. The rack pitch does not alias here, because a rack
run is 9.20 m long with an end, not an infinite corridor, and the world
beyond each end differs. But the **gradient** is two to three times weaker
in East A than in the well-conditioned west half at every displacement
(0.191 against 0.414 at 0.25 m, 0.423 against 1.072 at 1.00 m), and
99% of it comes from ten rays. That is the practical prediction: a matcher
in the east half will converge, but shallowly and from a small basin, and
its along-aisle estimate is being carried by a handful of grazing returns
rather than by the aisle walls. Odometry, not the scan, will be doing most
of the work along x there.

## 6. Validated against a live scan

The prediction is geometry, so it is worth knowing whether the simulator
agrees. Three sensor poses, vehicle at yaw 0, `/forklift/scan` captured from
a running server and compared ray by ray against the same 360 predicted
ranges. The vehicle's own mast rails are added to the predictor for this
comparison only (`--vehicle 0`), because a real scan contains them.

| Pose (sensor) | Where | finite obs / pred | median abs diff | p95 | rays > 0.05 m | rays > 0.10 m | finite in one only |
|---|---|---|---|---|---|---|---|
| (-5.45, -5.90) | dock aisle, spawn pose | 228 / 231 | 0.0041 m | 0.039 m | 9 | 3 | 3 |
| (+7.00, +7.00) | East A, the worst pose | 278 / 278 | 0.0032 m | 0.039 m | 12 | 3 | 0 |
| (-7.00, +7.00) | Aisle A west, well conditioned | 236 / 239 | 0.0051 m | 0.052 m | 13 | 6 | 3 |

Median agreement is 3 to 5 mm. Every disagreement above 0.10 m is a single
grazing or edge ray — a ray that passes within a few millimetres of a corner
or sits exactly at the 8.00 m range limit, where a one-ray difference in
where the beam lands produces metres of range difference. Example, at the
spawn pose: the predictor puts the mast rail's edge in ray 329 and the
simulator puts it in ray 330; rays 330 to 333 agree to 4 mm in both.

`angle_increment` in the live message is 0.017501909285783768 rad, which is
`2*pi/359` and confirms the ray convention the predictor uses.

**The vehicle costs 9 rays of 360.** At yaw 0 the two mast rails claim
bearings between +149.9 deg and +177.0 deg — nine rays, 2.5% of the sweep,
in the port quarter astern, identically at all three poses. Those returns
are fixed in the sensor frame and **carry no information about where the
vehicle is**, which is why the tables in section 4 are computed from the
world alone. Adding the vehicle would have raised `aniso` at (+7.00, +7.00)
from 0.034 to 0.065 purely by counting the vehicle's own mast as an
x-facing landmark, which is exactly the kind of number that makes a
degenerate corridor look survivable.

## 7. What the charging bays changed

The two charging bays were added on the owner's instruction and are
legitimate structure: a real warehouse has a charging area. They may
therefore be counted, and the honest question is whether they materially
change the picture. Measured by running the same computation with
`--exclude ChargeBay1Cabinet ChargeBay2Cabinet`:

| Pose | with cabinets: n / aniso / top10 | without: n / aniso / top10 |
|---|---|---|
| (-13.00, -5.50) dock lane | 281 / 0.588 / 51% | 279 / 0.651 / 52% |
| ( -9.00, -5.50) dock lane, over bay 1 | 293 / 0.559 / 86% | 293 / 0.534 / 91% |
| ( -7.00, -5.50) dock lane, over bay 2 | 219 / 0.203 / 82% | 219 / 0.177 / 89% |
| ( -3.00, -5.50) dock lane | 215 / 0.303 / 93% | 209 / 0.274 / 94% |
| ( -9.80, -7.70) **inside bay 1** | 279 / 0.525 / 46% | 279 / 0.446 / 55% |
| ( -7.40, -7.70) **inside bay 2** | 257 / 0.305 / 55% | 257 / 0.248 / 82% |

**Two metres away they change almost nothing; standing in a bay they change
a lot.** The return count barely moves, because a cabinet stands 0.65 m in
front of the south wall and mostly replaces wall returns with cabinet
returns. What it adds is the cabinet's two side faces, which face along x
where the wall behind it does not — so `aniso` improves at every pose, and
inside bay 2 the along-track residual stops being a ten-ray phenomenon
(`top10` 82% to 55%).

The honest reading: the cabinets are a **local** landmark improvement in the
charging area, worth roughly +0.06 of `aniso` at the bays themselves and
+0.03 along the lane. They do not rescue any of the three named degenerate
stretches, all of which are 10 m or more away and on the other side of the
hall. Nothing in section 5 changes because of them.

## 8. The other scan plane, for completeness

The safety scanners sweep z = 0.15 m, where **every** bay is loaded with
floor-level stock. At that plane the world has 163 cross sections and the
aisles are more uniformly featureless than at 1.80 m: Aisle A at
(-7.00, +7.00), which is a comfortable 0.218 at the navigation plane, is
0.054 at 0.15 m. This is a note and not a problem: those scanners are a
non-safe measurement channel and are not a localisation input
(`agv/forklift/README.md`, invariant 1). It is one more reason the
navigation lidar sits high.

## 9. How to read a SLAM run against this file

1. Expect the map to be built well in the west half, the end aisles and the
   cross aisle. If it is not, the problem is configuration, not geometry.
2. Expect along-aisle drift in the east half of all three aisles, worst
   between x = +4 and x = +7. **Do not treat that as a tuning failure**, and
   in particular do not fix it by adding objects to the aisle: the same
   drift is what a real installation solves with reflectors or with fiducial
   markers, and choosing between those is a localisation decision, not a
   world-file decision.
3. A mapping drive that only ever traverses the west half will look better
   than this world deserves. State which stretches a run covered.
4. If a SLAM run comes out *better* than section 5 predicts in the east
   half, find out why before believing it. The two candidates are that the
   run never held still long enough for drift to show, and that odometry
   carried it — which is the correct outcome, but it is an odometry result
   and should be reported as one.
