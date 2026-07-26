# ADR 0002: Vehicle platform — Robotnik RB-KAIROS

Status:        accepted

Context:       The project needs a credible industrial AMR rather than an
educational base, with an official ROS 2 description and Gazebo model
maintained by the manufacturer. Verified from vendor sources (2026-07-26):
Robotnik maintains the ROS 2 description in
https://github.com/RobotnikAutomation/robotnik_description, which lists
RB-Kairos / RB-Kairos+ among its supported robots and provides an `arm_type`
argument selecting a Universal Robots e-Series arm on the RB-Kairos+
mobile-manipulator variant. Robotnik maintains the ROS 2 simulation in
https://github.com/RobotnikAutomation/robotnik_simulation, using modern
Gazebo (gz sim), not Gazebo Classic. Active vendor branches are jazzy-devel
(default) and humble-devel; ROS 2 support does not come from the legacy
ROS 1-only rbkairos_sim repository. The project's ROS 2 distribution is not
decided here.

Decision:      Robotnik RB-KAIROS is the vehicle platform for simulation and
for the ROS 2 integration target.

Consequences:  The platform is a mobile manipulator, so arm capability exists
in the model from the start while remaining out of scope until a later gate.
The arm will raise three architectural questions when that gate opens:

1. A base-stationary interlock as a precondition for arm motion.
2. Separate safety zones for base and arm.
3. Arm work expressed as a VDA 5050 action rather than a new protocol.

Alternatives:
- Neobotix MP-500 — considered viable, but with a narrower ecosystem.
- TurtleBot — rejected as not representative of industrial hardware.
- Custom reach truck model — rejected because modelling cost would dominate
  the project without adding architectural value.
