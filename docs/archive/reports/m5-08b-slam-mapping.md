# Report m5-08b — the warehouse map, built by SLAM against real odometry

```
brief:               docs/briefs/m5-08b-slam-mapping.md
status:              done
files_changed:       sim/launch/warehouse_bringup.launch.py
                     sim/launch/forklift_bringup.launch.py
                     sim/launch/warehouse_slam.launch.py           (new)
                     sim/config/slam_toolbox_warehouse.yaml        (new)
                     sim/scenarios/warehouse_mapping_route.py      (new)
                     sim/scenarios/tools/mapping_evidence.py       (new)
                     sim/maps/warehouse/warehouse.pgm              (new, artifact)
                     sim/maps/warehouse/warehouse.yaml             (new, artifact)
                     sim/maps/warehouse/warehouse.posegraph        (new, artifact)
                     sim/maps/warehouse/warehouse.data             (new, artifact)
                     sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md         (new)
                     sim/scenarios/maps/map.pgm                    (DELETED)
                     sim/scenarios/maps/map.yaml                   (DELETED)
                     sim/scenarios/tools/make_map.py
                     sim/scenarios/DEFERRED.md
                     sim/worlds/WAREHOUSE_EVIDENCE.md
                     sim/setup/install.sh
                     sim/setup/CONTAINER_TOOLCHAIN.md
                     sim/README.md
                     docs/reports/m5-08b-slam-mapping.md
invariants_touched:  none. Invariant 10 shaped two rulings: the EKF is the
                     sole publisher of odom -> base_link and no sim/ launch
                     file can add a second (captured, not asserted); and the
                     stale sim/scenarios/maps/ was deleted rather than kept
                     beside a map that now has an owner
open_questions:      seven, below. Two are requests outside sim/ (one of
                     them a .gitattributes rule), one is a size decision for
                     the owner, the rest are for the localisation and Nav2
                     briefs
next_suggested:      the localisation brief can start against a committed
                     map; it inherits a measured 5 m dead-reckoning budget
                     in the east half and no graph to fall back on
```

## The result

**SLAM: 0.185 m rms and 0.014 m final position error over a 107.5 m closed
circuit, against an EKF that drifted 4.295 m and +23.64° over the same
drive.** Ten loop closures. Both artifacts saved and both checked — the
grid measured against the world file, the pose graph loaded back.

Full evidence: `sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md`. Container
evidence only; the owner's WSL host has never had slam_toolbox.

## The prediction, answered by name

`WAREHOUSE_LANDMARKS.md` §5 named three degenerate stretches. All three
were driven; East B twice. Along-aisle error growth **across** each:

| stretch | worst `aniso` predicted | along-x growth, SLAM | along-x growth, EKF alone |
|---|---|---|---|
| **East dock** | 0.041 | −0.091 m | +0.008 m |
| **East B**, pass 1 | 0.031 | +0.003 m | +0.014 m |
| **East B**, pass 2 | 0.031 | −0.039 m | +0.217 m |
| **East A** | 0.034 | **+0.018 m** | −0.130 m |

The prediction was right about the geometry and right about the mechanism.
It was not a prediction of failure, and this run is the case its own §9.4
told the next brief to look for: **odometry carried the vehicle through**.
A degenerate stretch is 4.0 to 5.5 m long and was crossed in 5 to 7 s at
0.80 m/s; the 17° the brief warned about is accumulated over 106 m, not
over 5 m, and SLAM had already removed it at every aisle mouth where
structure existed. East A, the worst pose in the world, gave the *smallest*
along-aisle growth and the smallest across-aisle error — which is the
prediction's other half working exactly as stated: two flat parallel walls
pin the sensor across the aisle perfectly.

**Loop closure did not rescue them, because they did not need rescuing.**
East dock (t ≈ 22–27 s) and East A (t ≈ 106–112 s) were both crossed
*before the first closure of the run at t = 126 s*. Only East B's second
pass had one inside it, and it had entered that pass already at 0.030 m.
Where the closures did come from: five in the east end aisle at
t ≈ 126–129 s, closing leg 7 against leg 2's chain from 90 m earlier; one
inside East B at (+4.85, +0.69) closing pass 2 against pass 1; four at the
cross-aisle/dock-aisle mouth at t ≈ 162–163 s, closing the circuit onto
leg 1.

So the honest finding is narrower and more useful than "it worked":

> **Along-aisle position in the east half is carried by dead reckoning over
> the length of one degenerate stretch. That is a 5 m odometry budget, not
> a scan-matching result, and it is sufficient for a single traverse at
> 0.80 m/s. The condition that breaks it is dwell — stopping, reversing or
> manoeuvring inside the stretch — and nothing measured here bounds that.**

That is the number the reflector/fiducial decision should be taken
against.

## The route

Stated in advance and constant in `sim/scenarios/warehouse_mapping_route.py`
(`--print-route`): dock aisle W→E, east end aisle S→N, aisle B E→W, west
end aisle S→N, aisle A W→E, east end aisle N→S, aisle B E→W again, cross
aisle N→S, dock aisle back to the start. 109.40 m stated, 107.54 m driven,
8 × 90° turns, closed circuit.

**Driven by a scripted stimulus, not the teleop path**, and the controller
closes its loop on ground truth — it stands in for the human at the tiller,
who sees the aisle rather than the odometry. **No ground truth reaches any
estimator or the map**: the script publishes two raw joint commands and
nothing else. It bypasses the PLC, so **this run is not evidence about the
M4 command path**.

## Rulings and findings

1. **`sim/scenarios/maps/` — DELETED.** Its source of truth was gone (the
   world was rewritten at m5-08), its only consumers are the two parked
   scripts of the retired platform whose Nav2 parameter file m5-09 had
   already deleted, and it is regenerable in seconds by `make_map.py`,
   which survives. The generator is the artifact; its output was not. With
   `sim/maps/warehouse/` now holding a map that has an owner, a second one
   that is nobody's is a datum with two answers. `make_map.py`,
   `DEFERRED.md` and `sim/README.md` all say so; the two parked scripts
   keep their now-dangling references deliberately, because rewriting them
   would make a parked file look maintained.

2. **`async_slam_toolbox_node` is a lifecycle node and does nothing at all
   until transitioned.** As a plain `Node` it logs one line, subscribes to
   no scan, advertises no `/map` and publishes no transform — no warning,
   no error. `CONTAINER_TOOLCHAIN.md` §4.7 had recorded exactly that state
   without naming the cause. Cost one dead run to find.

3. **The EKF integrates ~0.0023 rad/s of heading on a stationary vehicle**
   — 8°/minute — measured twice per run on the parked segments either side
   of the drive, agreeing to 3%. m5-07c open question 5 as a number. The
   consequence is concrete: the map frame is anchored to the vehicle's
   *heading estimate* at the first scan, so **an earlier attempt that idled
   four minutes before driving produced a map rotated ~20° from the
   building**. The recorded procedure starts the drive as soon as SLAM is
   active; that map came out −2.82° off, and the sign is random per run.

4. **Scoring a SLAM pose against a world-frame truth requires anchoring**,
   and getting this wrong the first time inverted the whole result: the
   unanchored numbers said 8.3 m of SLAM error where the anchored ones say
   0.185 m rms. Neither `odom` nor `map` is the world frame and neither
   claims to be. `mapping_evidence.py analyse` anchors both at the drive's
   first sample and reports drift.

5. **The end aisles are not drivable at x = ±13.00** — four building
   columns at x = ±13.400 sit in them. The first rehearsal stalled with the
   vehicle's corner in one and spent 400 s driving a stationary machine
   with nothing complaining; the route driver now aborts on a stall. The
   route runs at ±11.90. `WAREHOUSE_LANDMARKS.md` samples ±13.00 because it
   samples *sensor* poses, which is not a claim that a vehicle fits.

6. **`/slam_toolbox/save_map` races the map publisher** and returns
   `result=255` with `Failed to spin map subscription` roughly half the
   time: the nav2 map saver it spawns waits 2 s for a `/map` message and
   `map_update_interval` is the shipped 5.0 s. The committed run succeeded
   on the second attempt. **`map_update_interval` was deliberately not
   lowered** — changing mapping behaviour to work around a client-side
   timeout is the kind of tuning the brief forbids. Check the result and
   retry.

7. **Six non-default slam_toolbox parameters**, each argued in
   `sim/config/slam_toolbox_warehouse.yaml` from a measured property:
   `min_laser_range` 0.10 and `max_laser_range` 8.00 (the sensor's own
   limits — the shipped 20.0 ray-traces 12 m of invented free space per ray
   through the racking); `minimum_time_interval` 0.20 (the shipped 0.5 s
   silently overrides the travel gates and couples node spacing to speed);
   `minimum_travel_distance` 0.30 and `minimum_travel_heading` 0.20 (from
   the basin width `WAREHOUSE_LANDMARKS.md` §5 measured, and from eight 90°
   turns); `scan_buffer_size` 30 (10 nodes is 3.0 m of history against an
   8.0 m sensor horizon). Every correlation, penalty and response threshold
   is left at the shipped default — those are the knobs a map is most
   easily flattered with. `loop_search_maximum_distance` 6.0 was raised on
   the argument that a 3.0 m radius is smaller than the 5.21 m error the
   closure exists to remove; **in this run it bought nothing**, because
   SLAM's own error never exceeded 0.358 m, and the report says so.

8. **Small in-scope addition, because my deliverable depends on it.**
   `ros-jazzy-robot-localization` was on the box only as an *automatic*
   dependency of Nav2, so `apt autoremove` would have taken the vehicle's
   sole publisher of `odom -> base_link` silently. It is now named in
   `install.sh`'s `ROS_PKGS` and recorded in `CONTAINER_TOOLCHAIN.md` §3.2,
   with `ros-jazzy-nav2-map-server` beside it. **Nothing was installed.**
   This closes m5-07c open question 1.

## Open questions

1. **Request to whoever owns `.gitattributes` (repo root, not `sim/`): two
   lines.** `*.pgm -text` covers the grid. `.posegraph` and `.data` are not
   covered — `git check-attr text` reports `auto` for both, so they rely on
   git's heuristic. The heuristic is correct today (1495 and 1518 NUL bytes
   in the first 8000), but LESSONS 2026-07-27 is that a generated binary is
   marked, not detected. Wanted:

   ```
   # slam_toolbox's serialised pose graph, sim/maps/. Both halves are boost
   # binary archives; text=auto classifies them correctly today only because
   # a NUL falls in the first 8000 bytes.
   *.posegraph -text
   *.data -text
   ```

   No other `.posegraph` or `.data` file exists anywhere in the tree, so
   neither rule can catch anything else today. Note also that the
   justification comment already in that file names
   `sim/scenarios/maps/map.pgm`, which this brief deleted; the rule still
   applies, now to `sim/maps/warehouse/warehouse.pgm`, which is likewise
   regenerated.

2. **A size decision for the owner.** The pose graph is 12.1 MB and its
   dataset 4.2 MB — 16 MB in the working tree against a 26.8 MiB pack.
   Git's zlib gets them to about **1.9 MB and 1.7 MB**, so the real pack
   cost is ~3.6 MB, and I recommend committing as-is. Gzipping them (the
   `*.gz -text` rule already exists) would halve that again but makes the
   artifact un-loadable by slam_toolbox without a manual step, which
   defeats "resume rather than restart". Flagged rather than decided.

3. **m5-07c open question 2 is now stronger, not weaker.** `/forklift/odom`
   is ground truth and its name does not say so. This brief added **two
   more consumers** of it under that name — the route driver and the
   evidence recorder — both of which read truth deliberately and say so in
   their headers. The rename to `/forklift/odom_ground_truth` still wants
   one coordinated brief across `sim/` and `agv/`.

4. **m5-07c open question 3 is half done, deliberately.** The IMU bridge
   row is now in `forklift_bringup.launch.py`, which is the one bridge
   table for this vehicle. The **estimator** was added to
   `warehouse_bringup.launch.py` and *not* to the M4 arena bringup:
   changing what a closed gate's launch starts by default is not this
   brief's to do. If M4 rehearsals should also carry a transform tree, that
   is a one-line brief.

5. **To the localisation brief, with a number attached.** The map exists
   and the east half is fine to map through at speed. AMCL has no pose
   graph to fall back on, so in the east half it is relying on the same 5 m
   dead-reckoning budget with no closure available, and a vehicle that
   *dwells* there is the untested case. `WAREHOUSE_LANDMARKS.md` §9.2's
   reflector/fiducial question is now a decision with evidence behind it.

6. **`slam_toolbox` registers TWO publishers on `/tf` by itself.** A naive
   "publisher count must be 1" check on a running SLAM stack reads 3 and
   looks like a violation. It is not: the edge set grew by exactly one
   disjoint edge. Any later invariant-10 check on `/tf` must count edges,
   not publishers, once a mapper or a localiser is running.

7. **One run, and the gyro bias sign is drawn per run.** Nothing here is a
   repeatability claim. A second run will produce a different map-frame
   rotation and different drift figures, and the per-stretch numbers should
   be expected to move.

## Notes

- **Nothing outside `sim/` and this report was written.** `agv/` was read
  extensively and not touched: `git status` shows no change under it.
- **Both transports isolated on every run** (`GZ_PARTITION` and
  `ROS_DOMAIN_ID`, unique per run: `m508b_smoke`/91, `m508b_reh2`/92,
  `m508b_map`/93, `m508b_map2`/94, `m508b_pubs`/95). Headless throughout,
  `QT_QPA_PLATFORM=offscreen`, no GUI. Every process confirmed gone with
  `ps -eo pid,args` after each run; the machine was never shared with
  another simulator.
- **A real-time factor is quoted and it was uncontended**:
  `real_time_factor: 0.99934892417589938` for the bringup, 0.9831
  simulation seconds per wall second with slam_toolbox running. This closes
  the item `WAREHOUSE_EVIDENCE.md` §6 owed, and that table row is updated
  in the same change.
- **No dependency was installed.** Both packages added to the toolchain
  record were already present.
- Nothing committed, nothing staged, no branch created.
