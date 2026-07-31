# Deferred: warehouse navigation scenario

Status: **unverified work in progress, parked.**

This directory holds a Nav2 navigation scenario for the warehouse world
(map, scenario launch and run script). Work stopped part-way through its
first full headless verification run, so nothing here has been demonstrated
end to end and no evidence file exists.

It was parked by an owner scope correction on 2026-07-27: the project's
core claim is the Gazebo-to-PLC closed loop, so fixed equipment under
PLC control moves ahead of the mobile robot. Navigation work resumes at
M5 (see docs/roadmap.md and ADR 0010, which supersedes the gate order
ADR 0004 set).

**The vehicle changed while this scenario was parked.** ADR 0010 D1 retires
the platform this scenario was written against and makes the in-house
forklift (agv/forklift/) the vehicle platform from M5 onward, and ADR 0010
D2 puts SLAM, a navigation lidar and Nav2 on that forklift. So M5 does not
resume this scenario as written.

## What m5-09 removed, and what that means

`config/nav2_params.yaml` was deleted (m5-09, ADR 0010 D1). The owner ruled
it is **not a migration candidate**: it was entirely shaped by the retired
vehicle — omni motion model, that vehicle's scan, odometry and command
topics, its frame tree and its footprint. The forklift's Nav2 configuration
is written **from scratch** at m5-10 (tricycle kinematics, one navigation
lidar, its own frame tree). The deletion is therefore not a gap: nothing was
lost that m5-10 would have started from.

The consequence for the two files left here:

- `nav_scenario.launch.py` has no parameter file to default to. `params_file`
  is now a required argument, and no file in this repository satisfies it.
- `run_scenario.py` still names the retired vehicle's odometry topic.

Both are kept as the record of the parked scenario, not as this project's
interface. Neither can be run: `sim/setup/install.sh` no longer provisions
the vendor workspace their bringup needed (m5-09). Whether either file
survives migration is **m5-10 briefing work, decided at briefing**.

## What is no longer parked (m5-08, 2026-07-31)

**The world and its bringup left this list.** The owner ruled on 2026-07-30
that M5 autonomy runs in the warehouse world, so:

- `worlds/warehouse.sdf` was rewritten as the M5 autonomy world and its
  landmark availability measured (`worlds/WAREHOUSE_LANDMARKS.md`);
- `launch/warehouse_bringup.launch.py` now spawns the forklift and was
  verified headless (`worlds/WAREHOUSE_EVIDENCE.md`);
- `worlds/BRINGUP_EVIDENCE.md` is marked as the retired platform's
  historical record and describes nothing that still exists.

The question "is the warehouse world reused or replaced" is therefore
**answered**, and it is not m5-10's to decide: it is reused, and M6 enlarges
it to ten stations.

`maps/` did NOT survive that rewrite. It is rasterized from the world's
static geometry, and the geometry changed, so the committed grid is **stale**
until it is regenerated. `tools/make_map.py` now reads its rectangles from
the SDF at run time and requires an explicit `--z`, because which scan plane
a static map represents is a Nav2 decision that belongs to m5-10.

Nothing else here is deleted. Treat every file in this directory as
unverified until a run produces EVIDENCE_NAV.md with a SUCCESS result.
