# Deferred: mobile robot navigation scenario

Status: **unverified work in progress, parked.**

This directory holds the Nav2 navigation scenario for the RB-KAIROS
(map, Nav2 parameters, scenario launch and run script). Work stopped
part-way through its first full headless verification run, so nothing
here has been demonstrated end to end and no evidence file exists.

It was parked by an owner scope correction on 2026-07-27: the project's
core claim is the Gazebo-to-PLC closed loop, so fixed equipment under
PLC control moves ahead of the mobile robot. Navigation work resumes at
M5 (see docs/roadmap.md and ADR 0010, which supersedes the gate order
ADR 0004 set).

**The platform changed while this scenario was parked.** ADR 0010 D1
retires RB-KAIROS and makes the in-house forklift (agv/forklift/) the
vehicle platform from M5 onward, and ADR 0010 D2 puts SLAM, a navigation
lidar and Nav2 on that forklift. So M5 does not resume this scenario as
written: migrating it to the forklift — which of these files survive, what
replaces the RB-KAIROS controller and frame assumptions, and whether the
warehouse world is reused or replaced by the enlarged M6 warehouse world —
is **M5-briefing work, decided at briefing**. None of it is decided here,
and nothing in this directory has been rewritten for the new platform.

Nothing here is deleted. When M5 opens, resume from the m3-02 brief (the
resuming brief's name is assigned at briefing), and treat every file in
this directory as unverified until a run produces EVIDENCE_NAV.md with a
SUCCESS result.

The warehouse world and headless bringup in sim/worlds and sim/launch
ARE verified (see sim/worlds/BRINGUP_EVIDENCE.md) and stay in place.
