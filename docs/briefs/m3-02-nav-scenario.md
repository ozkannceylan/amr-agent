gate:                M3
agent:               sim
goal:                The simulated AGV localizes and navigates the warehouse world with Nav2, headless, with captured evidence.
invariants_touched:  none
inputs:              [sim/ from m3-01, vendor navigation launch assets, docs/safety/SRS.md (SF-03 context only)]
deliverable:         sim/scenarios/ navigation scenario: map, Nav2 config/launch, a scripted goal run, and captured evidence of the run (logs/topic captures) stored under sim/scenarios/
done_when:           In this container, headless: AMCL (or slam_toolbox map) localizes the robot, a NavigateToPose goal is sent programmatically, the robot reaches the goal (evidence: /amcl_pose or /odom trace + goal result SUCCESS captured to a file committed with the scenario).
forbidden:           [GUI dependencies, modifying vendor packages, editing directories other than sim/ and the report, VDA 5050 or fleet logic (that is M4/M5)]
