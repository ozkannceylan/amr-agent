gate:                M0
agent:               interface (write scope extended to docs/adr/ by owner for this brief)
goal:                Record the AMR platform choice as an accepted ADR.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 8, owner platform decision, vendor feasibility findings in this brief's delegation]
deliverable:         docs/adr/0002-vehicle-platform.md
content:             Decision: Robotnik RB-KAIROS is the vehicle platform for simulation and for the ROS 2 integration target. Context: the project needs a credible industrial AMR rather than an educational base, with an official ROS 2 description and Gazebo model maintained by the manufacturer. Consequences: the platform is a mobile manipulator, so arm capability exists in the model from the start while remaining out of scope until a later gate; note the three architectural questions the arm will raise — base-stationary interlock as a precondition for arm motion, separate safety zones for base and arm, and arm work expressed as a VDA 5050 action rather than a new protocol. Alternatives rejected: Neobotix MP-500 (viable but narrower ecosystem), TurtleBot (not representative of industrial hardware), custom reach truck model (modelling cost would dominate without adding architectural value). Status: accepted.
done_when:           ADR follows the section 8 format and cites no claim that is not verifiable from vendor sources.
forbidden:           [writing code, adding simulation assets, editing other directories, changing any invariant]
