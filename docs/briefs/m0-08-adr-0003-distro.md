gate:                M0
agent:               arch-docs
goal:                Record the ROS 2 distribution choice as an accepted ADR, gated on fresh vendor verification.
invariants_touched:  none
inputs:              [CLAUDE.md sections 8, 9, docs/adr/0002-vehicle-platform.md, vendor verification supplied in delegation]
deliverable:         docs/adr/0003-ros2-distribution.md
content:             Decision: the project targets ROS 2 Jazzy with Gazebo Harmonic. Context: ADR 0002 fixed RB-KAIROS; the vendor's active development line is jazzy-devel while humble-devel is maintenance-tier, and Humble nears EOL — pinning a new project to a maintenance-tier distro is debt from day one. Precondition (owner-imposed): the ADR is accepted only because the jazzy-devel branches of the RB-KAIROS packages were verified current on 2026-07-26; the verification record (pinned SHAs, dates) must appear in the ADR. Alternatives: Humble (rejected: maintenance-tier, near EOL, would force superseding this ADR early); Rolling (rejected: no vendor branch, unstable target).
done_when:           ADR follows the section 8 format, status accepted, and contains the dated verification record with pinned commit SHAs for both vendor repos.
forbidden:           [writing code, editing files other than the deliverable and the report, changing any invariant, citing unverified claims]
