gate:                M3
agent:               sim
goal:                A warehouse Gazebo world in which the RB-KAIROS spawns headless from one launch file, reproducibly.
invariants_touched:  none
inputs:              [docs/adr/0002, docs/adr/0003, CLAUDE.md section 2 (invariant 12), the in-container ROS 2 Jazzy + Robotnik installation]
deliverable:         sim/ package: warehouse world (SDF), bringup launch (headless-capable), README with reproducible setup for the vendor stack
done_when:           `gz sim -s` + spawn via the launch file runs in this container with the robot entity created and /clock bridged; sim/README reproduces the environment from scratch (proxy-safe ROS repo setup, jazzy packages, Robotnik sources, python3.12 note).
forbidden:           [modifying vendor packages, MuJoCo, GUI-only launch paths, editing directories other than sim/ and the report, fleet or PLC logic]
