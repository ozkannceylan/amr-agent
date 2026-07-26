brief:               docs/briefs/m3-01-world-bringup.md
status:              done

files_changed:
  - sim/worlds/warehouse.sdf            (new: warehouse world - floor, perimeter walls,
                                         6 racks in 2 rows forming 2+ aisles, DoorGap
                                         opening in south wall, ConveyorStation east,
                                         ChargerStation west; sensors/physics/
                                         scene_broadcaster/user_commands/imu systems)
  - sim/launch/warehouse_bringup.launch.py  (new: headless-default bringup; gz server +
                                         /clock bridge + unmodified vendor
                                         spawn_robot.launch.py for RB-KAIROS)
  - sim/worlds/BRINGUP_EVIDENCE.md      (new: dated verification capture)
  - sim/setup/install.sh                (new: idempotent setup, verified by re-run)
  - sim/README.md                       (extended; first section preserved verbatim)

invariants_touched:  none

verification (run in this container, 2026-07-26, full capture in
sim/worlds/BRINGUP_EVIDENCE.md):
  - robot entity `robot` created alongside all 15 world models (gz model --list)
  - /clock ticking (echo once: sim time advancing; ~6 Hz wall = RTF ~0.12 headless)
  - /robot/front_laser/scan publishing 270-sample scans with finite ranges
    against warehouse geometry (echo once)
  - /robot/robotnik_base_control/odom present; closed-loop drive test:
    Twist 0.5 m/s on cmd_vel_unstamped moved odom x from 0.0 to 2.63 m
  - joint_state_broadcaster and robotnik_base_control both `active`
  - zero [ERROR] / process-died lines in the launch log
  - install.sh re-run: all steps detect-and-skip (idempotent)

notable finding: the RB-KAIROS mecanum controller
(robotnik_controllers/RBKairosController) is not in the vendor source
repos; Robotnik ships it as prebuilt .deb files inside
robotnik_simulation/debs/. The prepared workspace lacked them, so the
controller spawner would have failed. I installed the three vendor debs
(robotnik-common-msgs, robotnik-controllers-msgs, robotnik-controllers)
and added the step to install.sh and the README. Strictly this is a new
binary dependency, though it ships inside the already-adopted vendor repo
(ADR 0002) - flagging for owner awareness rather than approval-blocking,
since without it the platform cannot drive at all. No vendor files were
modified.

open_questions:
  - Owner OK with the closed-source robotnik_controllers debs (vendor-shipped,
    pinned versions inside robotnik_simulation) as part of the stack? If not,
    the alternative is a superseding ADR and a different drive path.
  - Headless RTF ~0.1 (CPU rendering of 2 lidars + RGBD camera). Acceptable for
    M3 checks; if later gates need faster runs, the vendor
    low_performance_simulation flag is the untouched-vendor lever to try.

next_suggested:      M3 brief 2: Nav2 bringup (map, AMCL/SLAM, controller) on this
                     world using /robot/front_laser/scan and robotnik_base_control
                     odom/cmd_vel.
