# PLAN

## Current gate: M2 — Safety requirements spec (in progress)

Exit criterion: every safety function has a trigger, a reaction and an
acceptance test (CLAUDE.md section 6), consistent with invariants 1, 2,
7 and the section 9 conventions; verifier pass.

## Briefs to close M2

1. m2-01 safety-spec — docs/safety/SRS.md.
2. m2-02 verifier — read-only review.

M0 closed 2026-07-26 (reports m0-04, m0-07, m0-09).
M1 closed 2026-07-26 (report m1-04).
Session mode: owner-approved autonomous run; only TIA Portal
implementation remains with the owner at the end. M3 feasibility is
proven in-container (ROS 2 Jazzy + Gazebo Harmonic + Robotnik stack
build and run headless).
