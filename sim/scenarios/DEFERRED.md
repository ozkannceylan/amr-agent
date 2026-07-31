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
survives migration — and whether the warehouse world is reused or replaced
by the enlarged M6 warehouse world — is **m5-10 briefing work, decided at
briefing**. None of it is decided here.

`maps/` and `tools/make_map.py` are vehicle-independent: the map is
rasterized from the static geometry of `worlds/warehouse.sdf`, so it
survives the platform change and needs re-generating only if that world
changes.

Nothing else here is deleted. Treat every file in this directory as
unverified until a run produces EVIDENCE_NAV.md with a SUCCESS result.

The warehouse world and headless bringup in sim/worlds and sim/launch are
still the retired vehicle's bringup; they were verified against it (see
sim/worlds/BRINGUP_EVIDENCE.md) and are left in place pending the same
m5-10 briefing decision.
