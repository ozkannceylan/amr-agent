# Report m5-08 — the warehouse world as the M5 autonomy environment

```
brief:               docs/briefs/m5-08-warehouse-for-autonomy.md
status:              done
files_changed:       [sim/worlds/warehouse.sdf,
                      sim/worlds/WAREHOUSE_EVIDENCE.md (new),
                      sim/worlds/WAREHOUSE_LANDMARKS.md (new),
                      sim/worlds/BRINGUP_EVIDENCE.md,
                      sim/launch/warehouse_bringup.launch.py,
                      sim/scenarios/tools/landmark_map.py (new),
                      sim/scenarios/tools/make_map.py,
                      sim/scenarios/DEFERRED.md,
                      sim/README.md]
invariants_touched:  none
open_questions:      see below
next_suggested:      m5-10 writes the forklift's Nav2 and slam_toolbox
                     configuration against this world, and reads
                     WAREHOUSE_LANDMARKS.md sections 5 and 9 before tuning
                     anything.
```

## What the deliverable is

`sim/worlds/warehouse.sdf` is rewritten as the M5 autonomy world: a 30 x 20 m
hall with three rack rows cut by a central cross aisle, an end aisle at each
end, building columns, a dock door frame, a transfer station, two charging
bays and the arena's safety zone marking pattern. It spawns the forklift
through `warehouse_bringup.launch.py` and bridges its topics, proved by
captured `ros2 topic hz` (9.98 Hz on `/forklift/scan`, 19.97 Hz on
`/forklift/odom`) in `worlds/WAREHOUSE_EVIDENCE.md`.

`worlds/WAREHOUSE_LANDMARKS.md` is the measured landmark-availability map,
produced from geometry **before** any SLAM run, and it names three
degenerate stretches instead of removing them.

## The structure added, and the warehouse reason for each

| Structure | Why a warehouse has it |
|---|---|
| Rack uprights, 0.10 x 0.08, on a 2.30 m bay pitch, in five-frame runs | racking is a frame, not a wall. Uprights are what a lidar actually sees between loads, and they are what makes a rack see-through where a bay is empty |
| Back-to-back row pairs with a 0.30 m flue | how rows are set out when a building is wide enough for it, and the flue is where the column grid hides |
| Rack runs stopping 4.00 m short of each side wall, and a 3.60 m central cross aisle | egress and cross traffic. It is also what puts a rack END, not an unbroken wall, at every aisle mouth |
| Floor-level stock in every bay; reserve-level stock full in the east runs, alternate bays empty in the west runs | a warehouse is not uniformly full. Goods in arrives at the dock door on the east half of the south wall and is put away nearest it; the west runs are the picked face and are depleted |
| Building columns, 0.25 m, at x = +-4.60 and +-13.40 on three lines in y | every building has a column grid. Two lines fall in the rack flues, which is how a real layout reconciles a grid with racking; the apron line is exposed. No column stands in the cross aisle or the door approach, because the grid was set out that way |
| Dock door frame: two posts and a lintel at the 4.00 m opening | the opening in the south wall needs a frame, and the PLC-controlled door acts there at M6 |
| Transfer station guard frame: two 0.15 m posts and a header | the conveyor deck at 0.80 m is below the navigation plane. A pallet transfer station at a vehicle interface has guarding and photo-eye masts, and that frame is what the navigation lidar sees of the station |
| Two charging bays, painted outlines plus red cabinets | a warehouse has a charging area (owner instruction of 2026-07-31; see below) |
| Safety zone marking, 3.00 m square, on the apron where the cross aisle lands | the arena's pattern, so M5's safety and autonomy demonstrations can be recorded in ONE world. It is paint, watched by nothing in the file |

**Nothing was scattered into an aisle.** The honesty rule held: the only
thing added anywhere near an aisle floor is paint, and the loaded/empty
pattern that decides how featureless an aisle is was declared as a stock
state first and measured afterwards.

Two omissions, both deliberate and both written into the file: rack **beams**
are not modelled (they sit wholly below 1.45 m and above 2.75 m, are never
contacted, and would add ~160 visual primitives to a software-rasterised
scene without changing one measured number), and the physics step is the
arena's 2 ms at 500 Hz rather than the 20 ms this file used to carry, so the
M4 steer, traction and fork figures stay comparable.

## The landmark map, and the degenerate stretches

`scenarios/tools/landmark_map.py` parses the world SDF at run time (it does
not carry a copied rectangle list), takes the cross section of every box
`<visual>` at z = 1.80 m — visuals, because a `gpu_lidar` renders the scene
— and casts the sensor's own 360 rays from each sample pose. 69 poses on six
named lines. Reported per pose: finite returns, the largest arc with no
return, and the translation information matrix `J = sum n n^T`, whose two
eigenvalues in this axis-aligned world are exactly the counts of returns on
x-facing and y-facing surfaces. Their ratio is the headline: 0.00 means one
axis carries no information at all.

A second, independent metric guards against the first one misleading: the
RMS range change under a 0.25 m displacement along the line, and the share
of that change carried by the ten largest single-ray differences. High
change spread over hundreds of rays is a pose a matcher settles into from
anywhere; low anisotropy with the change concentrated in ten grazing rays is
a pose that matches only from a good initial guess.

**The three degenerate stretches, named:**

| Name | Line | Extent (aniso < 0.20) | Worst pose | Worst aniso |
|---|---|---|---|---|
| **East A** | Aisle A, y = +7.00 | x in [+2.0, +7.0] | (+7.00, +7.00) | **0.034** |
| **East B** | Aisle B, y = +0.65 | x in [+3.0, +7.0] | (+6.00, +0.65) | **0.031** |
| **East dock** | dock aisle, y = -5.50 | x in [+1.5, +7.0] | (+4.50, -5.50) | **0.041** |

All three are in the fully-loaded east half, all three end at x = +7.0, and
all three recover at x = +9 where the rack ends at x = +11.00 and the east
wall at x = +15.00 come inside the lidar's 8.00 m range. Across the whole
east half the ten-ray share sits above 90%: the only along-aisle information
in those scans is carried by ten rays or fewer. The west halves, the cross
aisle and both end aisles are well conditioned (0.30 to 0.98).

**Aliasing was looked for and not found.** The 2.30 m bay pitch produces no
secondary residual minimum within +-3.00 m, because a rack run is 9.20 m
long with an end rather than an infinite corridor. What is real is that the
along-track gradient in East A is two to three times weaker than in the west
half at every displacement.

**The prediction was validated against the simulator**, not left as
arithmetic: three sensor poses, live `/forklift/scan` compared ray by ray
against the same 360 predicted ranges. Median agreement 3 to 5 mm, p95 under
0.05 m, and every disagreement above 0.10 m is a single grazing or
range-limit ray. The live message also confirmed `angle_increment` is
`2*pi/359`, not `2*pi/360`.

One number worth the orchestrator's attention: including the vehicle's own
mast rails in the count would have raised East A's worst anisotropy from
0.034 to 0.065. Those nine returns are fixed in the sensor frame and say
nothing about where the vehicle is, so the landmark tables are computed from
the world alone. It is exactly the kind of figure that would have made a
degenerate corridor look survivable.

## The charging bays (owner instruction, 2026-07-31)

Delivered as geometry plus names and nothing else: no docking behaviour, no
approach logic, no charging state, no PLC or fleet interaction.
`ChargeBay1Marking` / `ChargeBay1Cabinet` at (-9.80, -7.70) and
`ChargeBay2Marking` / `ChargeBay2Cabinet` at (-7.40, -7.70), both in the
dock apron against the south wall, west of the door approach. Poses,
extents, sizing arithmetic and per-plane appearance are recorded in
`worlds/WAREHOUSE_EVIDENCE.md` **section 5**, which is the document a later
fleet brief cites instead of re-measuring the SDF.

The outline is 3.20 x 1.80, sized from the vehicle's **real plan envelope**
of 2.735 x 1.040 m (tines at x = -1.875 to counterweight at x = +0.860,
scanner bracket to scanner bracket in y) and not from the 1.40 x 0.90
chassis box, which would have understated the length by 1.335 m. The bay's
long axis is y, so a vehicle parks along y; a swept envelope check confirms
it fits both bays with no collision.

The cabinet is 0.90 x 0.65 x 2.00, a physical box the forklift can see and
would hit. Being full height it presents the same footprint at both scan
planes; what differs is that at 1.80 m it is one of only a handful of
free-standing things in the apron, while at 0.15 m it stands in front of a
wall the safety scanner sees anyway.

**`ChargerStation` was replaced, not duplicated.** The M3-era block was a
0.80 x 0.80 x 1.20 placeholder against the *west* wall that topped out
0.60 m **below** the navigation scan plane, so no vehicle could ever have
seen it. Keeping it beside two things also called charging bays would have
left two conflicting notions of a charger in one world. It is removed, and
the reconciliation is written out in `WAREHOUSE_EVIDENCE.md` section 5 and
in the world file header.

**Their effect on the landmark picture, measured rather than assumed.**
Re-running the computation with the two cabinets excluded: two metres away
they change almost nothing (the return count barely moves, because a cabinet
stands 0.65 m in front of a wall and mostly replaces wall returns), but
standing in a bay they matter — anisotropy 0.446 to 0.525 in bay 1 and 0.248
to 0.305 in bay 2, and in bay 2 the along-track residual stops being a
ten-ray phenomenon (82% to 55%). So: a real local improvement at the
charging area itself, and **no** effect on any of the three named degenerate
stretches, which are all on the other side of the hall.

## The two carried items

**`warehouse_bringup.launch.py`**: the RB-KAIROS vendor spawn path is gone.
The file now includes `forklift_bringup.launch.py` and overrides the world
and the spawn pose, rather than restating the bridge table. One topic
contract, one launch file that states it. Consequence worth knowing: every
topic and remap question about this launch is answered in the M4 file.

**`worlds/BRINGUP_EVIDENCE.md`**: kept and clearly marked as the retired
vehicle's historical record, with a table pointing each of its claims at the
current record and an explicit instruction not to cite a figure from it as
M5 evidence. Nine of the models it lists no longer exist under those names.

## Scope note: two files touched that the brief did not name

Both are inside `sim/` and both would have been left silently wrong.

- **`scenarios/tools/make_map.py`** carried a hand-copied rectangle list
  with a docstring promising "if the world changes, re-run this script" — a
  promise it could not keep, since re-running re-rasterised the same stale
  list. It now reads rectangles from the SDF at run time and **requires**
  `--z`, because which scan plane a static map represents is a navigation
  decision. I did **not** regenerate `scenarios/maps/`: that means choosing
  the plane, and the choice is m5-10's. The committed grid is marked stale
  in the script, in `sim/README.md` and in `DEFERRED.md`.
- **`sim/README.md` and `scenarios/DEFERRED.md`** described the world and
  its bringup as parked work belonging to the retired platform, and left
  "is the warehouse world reused or replaced" as an open m5-10 question. The
  owner's 2026-07-30 ruling answers it, so both files now say so.

## Open questions

1. **`docs/roadmap.md` row M5 item (d) still says SLAM builds a map "of the
   arena".** The owner's 2026-07-30 ruling puts M5 autonomy in the warehouse
   world. The roadmap is the live gate order and I cannot edit it; this
   needs an arch-docs brief before the gate is ruled on, or the criterion
   and the work will disagree at verification.
2. **No real-time factor for this world exists.** The bringup shared the
   machine with another agent's simulator, so no timing figure was taken
   (LESSONS 2026-07-30). This world carries substantially more geometry than
   the M4 arena that the existing RTF figures came from, and the ~0.1 figure
   still quoted for the old warehouse belonged to the retired platform with
   an RGBD camera. A measurement on an uncontended machine is owed before
   anyone plans a recording or sets Nav2 timeouts.
3. **No GUI capture of this world.** The `VisualizeLidar` block is present
   and follows the arena's pattern, but no GUI was started, so the beams
   have not been seen here. Owed to the M5 recording work.
4. **Which scan plane a static map of this world represents** is undecided
   and belongs to m5-10; at 1.80 m and at 0.15 m the world looks materially
   different, because floor-level stock fills every bay while reserve-level
   stock does not.
5. **The stock occupancy pattern is a world-file constant.** If a later
   brief wants a different one, the degenerate stretches move and
   `WAREHOUSE_LANDMARKS.md` must be re-measured in the same change. Changing
   it to make a SLAM run look better is the thing this brief's honesty rule
   forbids.
6. **M6 enlarges this world to ten stations.** The bays, the transfer
   station and the apron are placed with that in mind but nothing here
   reserves station positions; that is an M6 layout decision.
