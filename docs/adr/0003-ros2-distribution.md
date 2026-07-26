# ADR 0003: ROS 2 distribution — Jazzy with Gazebo Harmonic

Status:        accepted

Context:       ADR 0002 fixed the vehicle platform as the Robotnik RB-KAIROS.
The vendor's active development line for that platform is jazzy-devel, while
humble-devel is maintenance-tier, and Humble itself is near end of life.
Pinning a new project to a maintenance-tier distribution is technical debt
from day one.

Acceptance of this ADR was gated by the owner on verifying that the
RB-KAIROS packages' Jazzy branches actually exist and are current.

Verification record (2026-07-26):
- RobotnikAutomation/robotnik_description — default branch jazzy-devel,
  HEAD 4bc7342 (2026-07-17), RB-Kairos / RB-Kairos+ in the supported-robots
  list.
- RobotnikAutomation/robotnik_simulation — default branch jazzy-devel,
  HEAD 8273bc9 (2026-07-16), rbkairos and rbkairos_plus in the
  supported-robots table.
- Both branches actively developed in July 2026; no sign of abandonment.

If a future re-check finds the Jazzy line abandoned, this ADR must be
superseded, not edited.

Decision:      The project targets ROS 2 Jazzy with Gazebo Harmonic for the
RB-KAIROS simulation and integration stack.

Consequences:
- Gazebo Harmonic (modern gz sim) is the simulation runtime, consistent with
  invariant 12.
- Humble-only tutorials and the legacy ROS 1 rbkairos_sim repository are out
  of scope.
- Distribution upgrades (e.g. to a future LTS) require a superseding ADR.

Alternatives:
- ROS 2 Humble — rejected: maintenance-tier vendor branch, near EOL, would
  force superseding this ADR within weeks.
- ROS 2 Rolling — rejected: no vendor branch, unstable target.
