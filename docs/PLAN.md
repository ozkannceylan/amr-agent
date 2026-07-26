# PLAN

## Current gate: M3 — Simulated vehicle (in progress)

Exit criterion: a Gazebo AGV localizes and navigates a warehouse world
with Nav2 — observable behavior, demonstrated headless in this
container (feasibility proven: ROS 2 Jazzy + Gazebo Harmonic +
Robotnik jazzy-devel stack builds and runs).

## Briefs to close M3

1. m3-01 sim — warehouse world, headless bringup launch, reproducible
   environment setup (sim/).
2. m3-02 sim — localization + navigation scenario with captured
   evidence of the run.
3. m3-03 verifier — re-runs the scenario and confirms the observable
   behavior.

M0–M2 closed 2026-07-26 (reports m0-04/07/09, m1-04, m2-02).
Session mode: owner-approved autonomous run; only TIA Portal
implementation remains with the owner at the end.
