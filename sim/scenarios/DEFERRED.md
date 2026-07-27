# Deferred: mobile robot navigation scenario

Status: **unverified work in progress, parked.**

This directory holds the Nav2 navigation scenario for the RB-KAIROS
(map, Nav2 parameters, scenario launch and run script). Work stopped
part-way through its first full headless verification run, so nothing
here has been demonstrated end to end and no evidence file exists.

It was parked by an owner scope correction on 2026-07-27: the project's
core claim is the Gazebo-to-PLC closed loop, so fixed equipment under
PLC control moves ahead of the mobile robot. Mobile robot work resumes
at the gate now numbered M5 (see docs/roadmap.md and ADR 0004).

Nothing here is deleted. When M5 opens, resume from the m3-02 brief,
now docs/briefs/m5-*, and treat every file in this directory as
unverified until a run produces EVIDENCE_NAV.md with a SUCCESS result.

The warehouse world and headless bringup in sim/worlds and sim/launch
ARE verified (see sim/worlds/BRINGUP_EVIDENCE.md) and stay in place.
