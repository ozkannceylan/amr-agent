#!/usr/bin/env bash
# m5v3.sh - bring the m5-ver3 plant up and down: ONE world, ONE truck,
# ONE bridge, ONE estimator, and a GPU the run has proved it is using.
#   start [--headless] [--slippery] [--rf2o|--fuse]
#         [--localize [amcl|slam]] [--nav] [--monitor] [--dock] | stop | status
#
# WHAT THIS TRACK IS. m5-ver3 is the sensor-fusion rebuild of the SHOWCASE
# vehicle (vault AMR-DEC-003): one forklift, real instrument profiles, a
# fusion estimate scored against ground truth. It forks m6's fleet plant
# back down to a single truck and shares its floor. See CONTEXT.md.
#
# WHAT IT IS NOT. There is no broker, no fleet manager, no HMI and no PLC
# link here, and their absence is the phase rather than an omission: what
# is up is the plant, its sensors, the node that estimates the vehicle's
# motion from them and the filter that fuses that estimate with the IMU.
# A process started for the shape of the thing would be a claim this run
# does not make. Nothing here touches PLCSIM Advanced or anything on the
# Windows side.
#
# THE MAP AND THE ABSOLUTE POSE ARE F3's AND THEY ARE OPTIONAL. The
# default stack has NO localisation in it at all: the estimator's world
# frame is the odom frame, so it publishes odom -> base_link and never
# map -> odom. `--localize` is what adds that edge, and it adds exactly
# that one - the ACTIVE localiser owns it and the estimator keeps its
# own. Since F3 Task 3 there are two localisers to choose between and
# `--localize [amcl|slam]` is how; they are never alive together.
#
# IT ORCHESTRATES PROCESSES AND HOLDS NO LOGIC OF ITS OWN. Every constant
# it obeys is in config.yaml and every child it starts writes its own log
# under logs/, by name, so a bringup that goes wrong is read rather than
# guessed at. `status` names the same children back.
#
# start OPENS THE GAZEBO WINDOW, because this script is the HUMAN entry
# point to a track whose subject is what the sensors see. --headless is
# for a run being MEASURED: with the GPU under it the window is cheap, but
# it is not free, and every figure in EVIDENCE_BRINGUP.md was taken
# headless so the next one can be compared with it.
#
# --slippery BRINGS UP A DIFFERENT PLANT FROM THE SAME MODEL FILE, and it
# is the one flag here that changes what is being measured rather than how
# much of it is drawn. It overrides every wheel's slip compliance through
# gz-sim's own wheel_slip service after the spawn (F2 Task 2; config.yaml
# slippery:), so the tyre creeps and the wheel odometry's distance goes
# long by an order of magnitude more than the believed radius does on its
# own. THE COMMITTED model.sdf IS NOT EDITED and no variant of it is
# generated. What the plant ended up on is written to
# paths.traction_file, reported by `status`, and copied into every
# evidence session recorded against it - because a slippery run that
# reaches the no-slip tables unlabelled is the one failure this whole
# mechanism is shaped to prevent.
#
# --rf2o ADDS A SECOND ESTIMATOR TO THE SAME PLANT, which is the mirror
# image of what --slippery does and is labelled by the same mechanism for
# the same reason. Three more children go up - the nav lidar's static
# transform, rf2o_laser_odometry_node matching consecutive scans, and the
# relay that puts a MEASURED covariance on its twist (it publishes none)
# and corrects the lever arm between the scanner and base_link (it
# corrects none) - and the filter is handed a second --params-file that
# gives it an odom1. Without the flag none of that is reached, ekf.yaml is
# the whole of the filter's configuration, and this is the six-child stack
# EVIDENCE_FUSION.md 9.3's figures were taken on. The package is built
# from source into the user's own home by tools/install_rf2o.sh, without
# root; `start --rf2o` refuses by name if that has not been run.
#
# --fuse REPLACES THE ESTIMATOR ENTIRELY, which is the one thing neither
# other flag does. `fuse`'s fixed-lag smoother goes up in ekf_node's
# place - the `ekf` child is NOT SPAWNED - fusing the same two topics,
# the same three wheel-odometry channels and the same one gyro channel,
# and publishing its own odom -> base_link. It is a FACTOR GRAPH rather
# than a Kalman filter: every measurement inside a 0.5 s window is kept
# as a factor and the whole window is re-solved, and re-linearised, on
# every optimisation pass. EVIDENCE_FUSION.md 11 is the A/B against
# EVIDENCE_FUSION.md 9.3's baseline and the recommendation it produced.
#   IT IS MUTUALLY EXCLUSIVE WITH --rf2o AND THE COMBINATION IS REFUSED
#   BY NAME. Two reasons, either sufficient: the rf2o arm's second
#   parameter file is a robot_localization parameter file that this node
#   cannot read, and a three-way arm is not a thing any table in
#   EVIDENCE_FUSION.md has a column for.
#   IT IS VENDORED, NOT BUILT. Every package it needs is in the Jazzy
#   archive; what this rig has no permission to do is install one. So
#   tools/install_fuse.sh is m6/tools/install_broker.sh's shape -
#   apt-get download, dpkg-deb -x into $HOME - and `start --fuse`
#   refuses by name if it has not been run.
#
# --localize ADDS A LAYER RATHER THAN CHANGING ONE, which is what makes
# it different in kind from all three flags above: --slippery changes the
# PLANT, --rf2o adds a SENSOR, --fuse swaps the ESTIMATOR, and this one
# puts something ABOVE the estimator that knows where the vehicle IS.
# Whatever is chosen publishes map -> odom - the one edge F3 adds
# (constraint 15) - on top of the odom -> base_link the estimator already
# owns. The artifacts that arm opens are md5-checked BEFORE anything
# starts, every lifecycle node is transitioned by this script, and a gate
# refuses a localiser that came up merely alive. Its answer is written to
# the state file as loc=, so every instrument downstream can say whether
# a figure is absolute; it combines with all three other flags.
#   AND SINCE F3 TASK 3 IT TAKES AN ARGUMENT, BECAUSE THERE ARE TWO.
#   `--localize amcl` (the default) is nav2's map_server serving the
#   frozen GRID with nav2_amcl localising in it; `--localize slam` is
#   slam_toolbox's localisation node deserialising the frozen POSE GRAPH
#   and localising in that, with no map_server at all. They are
#   ALTERNATIVES and never layers - two publishers of one tf edge is a
#   coin toss, not a localiser - so the exclusion is structural and each
#   arm carries its own loc= label. EVIDENCE_LOCALIZATION_V3.md 13 is
#   the A/B between them and the recommendation it produced.
#
# --nav STACKS ON TOP OF --localize AND IS REFUSED WITHOUT IT, which is
# the first flag here that depends on another. It is the same shape
# --localize already has over the estimator: --slippery changes the
# PLANT, --rf2o adds a SENSOR, --fuse swaps the ESTIMATOR, --localize
# adds a LAYER that knows where the vehicle IS, and this one adds the
# layer that decides where it GOES. Five more children - nav2's planner,
# controller, behaviour and BT-navigator servers plus ONE lifecycle
# manager for the four of them - reading m5_ver3/nav2.yaml and
# m5_ver3/behavior_trees/navigate_to_pose_tricycle_v3.xml.
#   THE DEPENDENCY IS STRUCTURAL AND NOT A CONVENIENCE. The global
#   costmap's frame is `map`, and Costmap2DROS::on_activate BLOCKS until
#   it can transform map -> base_link. Without a localiser nothing
#   publishes map -> odom at all, so that transition never completes and
#   every process sits ALIVE for ever. It is refused BY NAME instead,
#   before anything is started.
#   THE COMMAND PATH IS ALREADY THERE AND IS NOT PART OF THIS ARM. F4
#   Task 1's smoother and converter go up on EVERY bringup (F4
#   constraint 18: one line, no bypass), so --nav adds a publisher to
#   the top of a path that already exists and has already been measured
#   end to end with no Nav2 in the room.
#   IT GOES UP LAST, AFTER THE LOCALISER IS ACTIVE, and that ordering is
#   the on_activate block above rather than tidiness.
#   ITS LABEL IS nav= AND IT IS A FOURTH LINE ON THE STATE FILE, for the
#   loc= line's reason one layer further up: a session recorded with a
#   planner in the room is a different measurement from one recorded
#   without, and nothing else in the CSVs says which.
#
# --dock SPAWNS THE STATION FURNITURE AND THE DETECTOR, F5 Task 1, and
# it is OFF unless the command line says otherwise. Constraint 21: the
# AprilTag marker is a gz create, never a world-file edit. The child is
# vendored apriltag_node on the colour stream. IT REQUIRES --nav AND IS
# REFUSED WITHOUT IT BY NAME: detection accuracy is a staging-range
# figure, and staging is a Nav2 goal. ITS LABEL IS ITS OWN LINE (dock=)
# carrying apriltag.yaml's md5, for monitor='s reason one layer over.
#
# THE PARTITION IS NOT OVERRIDABLE FROM THE ENVIRONMENT, unlike m6.sh's.
# It is read from config.yaml by start, by stop and by status alike, so
# the three cannot disagree about which graph this is - and ours() reads
# it back out of a candidate process's own environment before the sweep is
# allowed to touch that process. m6 (partition m6, domain 96) and step5
# (m5demo) may be up on this machine at the same time as this stack; they
# are not this stack's to kill and this stack cannot reach them.
set -uo pipefail

# refuse(), the config.yaml reader and the ROS source are SHARED with
# tools/rtf_probe.sh and live in one file, because two copies of a
# mechanism drift exactly the way two copies of a value do. _common.sh
# also sets $REPO, $M5V3 and $CONFIG from its OWN location, and $TOOL is
# the name its refusals speak under.
TOOL=m5v3
# shellcheck source=tools/_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/tools/_common.sh"

GUI=true   # start's default; --headless sets it false. See the header.
# THE PLANT'S TRACTION, and it is the one thing about this stack that the
# COMMAND LINE decides rather than config.yaml. --slippery overrides the
# three wheels' slip compliances after the truck is spawned, so the same
# committed model.sdf brings up two measurably different plants. Every
# figure taken off one of them has to say which, which is what
# $TRACTIONFILE is for - see write_traction().
SLIPPERY=false
# THE OPTIONAL LASER-ODOMETRY ARM, F2 Task 3, and it is OFF unless the
# command line says otherwise. --rf2o adds three children - the nav
# lidar's static transform, rf2o_laser_odometry_node and the twist relay
# that puts a measured covariance on its output - and one extra
# --params-file on the filter. Without the flag not one line of any of
# that is reached and the stack is the six children EVIDENCE_FUSION.md
# 9.3's figures were taken on. Like --slippery, the answer is written to
# the state file so that every instrument downstream can say WHICH
# ESTIMATOR a figure came off; unlike --slippery it changes the
# ESTIMATE and not the PLANT, which is why the two labels are separate
# lines and not one.
RF2O=false
# THE OPTIONAL FACTOR-GRAPH ARM, F2 Task 4, and it is OFF unless the
# command line says otherwise. --fuse REPLACES ekf_node with fuse's
# fixed-lag smoother rather than adding a child beside it, which is what
# makes it different in kind from the two flags above: --slippery changes
# the PLANT, --rf2o adds a SENSOR, and this one changes the ESTIMATOR.
# The child count is therefore the same six, with `fuse` where `ekf` was.
# Like both of them the answer is written to the state file, so every
# instrument downstream can say which estimator a figure came off; and
# like --rf2o it is an ESTIMATOR label, so the two share the arm= line
# and cannot both be on.
FUSE=false
# THE OPTIONAL LOCALISATION ARM, F3 Task 2, and it is OFF unless the
# command line says otherwise. --localize puts nav2's map_server and
# nav2_amcl up over the FROZEN map in maps/warehouse_v3 and gives this
# stack its first ABSOLUTE pose: AMCL becomes the sole publisher of
# map -> odom, on top of the odom -> base_link the estimator already
# owns. It is different in kind from all three flags above - --slippery
# changes the PLANT, --rf2o adds a SENSOR, --fuse swaps the ESTIMATOR,
# and this one adds a LAYER - so it is a label of its own (loc=) rather
# than a third value on the arm= line, and it combines with every one of
# them.
LOCALIZE=false
# AND WHICH LOCALISER, F3 Task 3, because now there are two. `--localize`
# and `--localize amcl` are the same command - nav2's map_server over the
# frozen GRID with nav2_amcl localising in it - and `--localize slam` is
# slam_toolbox's localisation node over the frozen POSE GRAPH, alone.
# Empty until the command line or config.yaml's localization.default_arm
# says otherwise; configure() resolves it and refuses a value that names
# no arm, by name, listing the ones that do.
#   THE TWO ARE NEVER ALIVE TOGETHER AND THE EXCLUSION IS STRUCTURAL.
#   Both publish map -> odom and tf2 has no notion of two authorities for
#   one edge (F3 global constraint 15), so this is a `case` with two
#   branches and not two flags that could both be set - which is --fuse's
#   shape (an else-branch of the `ekf` child) rather than --rf2o's (a
#   flag that is refused beside another).
LOCALIZER=""
# THE OPTIONAL NAV ARM, F4 Task 2, and it is OFF unless the command line
# says otherwise. --nav puts nav2's planner, controller, behaviour and
# BT-navigator servers up over the localised stack, with one lifecycle
# manager driving the four of them, and gives this track its first
# closed loop: a goal in, a path out, and a twist down the command path
# F4 Task 1 already built and measured.
#   IT REQUIRES --localize AND IS REFUSED WITHOUT IT BY NAME. See the
#   header: the global costmap's frame is `map` and its activation
#   blocks until map -> base_link resolves, which nothing publishes
#   without a localiser.
#   ITS LABEL IS ITS OWN LINE (nav=) for the same reason loc= is: it is
#   an independent question, all the combinations are legitimate runs,
#   and a session that cannot say whether a planner was in the room is a
#   row that would sit in the wrong table looking exactly like one of
#   them.
NAV=false

# --monitor: THE COLLISION MONITOR, F4 TASK 3, AND IT IS THE COMMAND
# PATH'S OPTIONAL ARM RATHER THAN THE NAV ARM'S. It subscribes a Twist
# and a LaserScan and publishes a Twist: no planner, no costmap, no goal
# and no map are in it, so tying it to --nav would be a dependency claim
# that is not true - and it would make the honest open-loop
# demonstration impossible, because that one wants the command path with
# NO Nav2 in the room, which is F4 Task 1's own rule.
#   IT IS OFF BY DEFAULT AND THE REASON IS THE EVIDENCE'S.
#   EVIDENCE_NAV_V3.md 16.5's acceptance set and 17's driving cases go
#   through a command path with nothing inserted in it; a monitor that
#   went up on every --nav bringup would put a fourth node in that path
#   and every arrival figure on this track would become a figure about a
#   different line. --rf2o and --fuse are the precedent: an optional
#   arm, off, with the measurement that says why.
#   ITS LABEL IS ITS OWN LINE (monitor=) for nav='s reason one layer
#   down: it is an independent question, both answers are legitimate
#   runs, and a session that cannot say whether a guard was in the
#   command path is a row that would sit in the wrong table.
#   NOTHING HERE IS A SAFETY FUNCTION. nav2's own words for this node,
#   verbatim: it "does not provide hard real-time safety
#   certifications". It does not replace a safety-rated PLC. It
#   complements the F-PLC; it is not the F-PLC.
MONITOR=false
# --dock: F5 TASK 1's DETECTOR AND STATION FURNITURE, and it is OFF
# unless the command line says otherwise. It spawns the marker via
# furniture.py place (constraint 21) and apriltag_node on the colour
# stream. IT REQUIRES --nav: staging is a Nav2 goal and the camera at
# spawn cannot see S5. ITS LABEL IS dock=, apriltag.yaml's md5, so a
# detection table cannot sit beside a run that never started the node.
DOCK=false

# THIS SCRIPT'S OWN REQUIRED KEYS, on top of the isolation and ROS ones
# _common.sh checks for every script on this track. Each is refused by its
# DOTTED name if the file has been reorganised under it.
# MAINTENANCE OBLIGATION: a key read below is a key listed here - AND
# THE CONVERSE, which is the half that rots quietly. A key listed and
# never read is a claim about THIS script that is not true, and it
# survives every test: the load succeeds, the run is correct, and the
# list has become a wish. topics.amcl_pose and topics.slam_pose were
# exactly that until F3's phase-end sweep - this script passes no
# override for either pose topic (they are the two localiser nodes'
# OWN advertised names, config.yaml's topics: block argues why they
# are left unnamespaced) and the three programs that DO subscribe them
# list them in their own REQUIRED_KEYS.
REQUIRED_KEYS=(
    gpu.gallium_driver gpu.d3d12_adapter_name gpu.required_renderer
    world.file world.name
    vehicle.model vehicle.name
    vehicle.spawn.x vehicle.spawn.y vehicle.spawn.z vehicle.spawn.yaw
    vehicle.imu_mount.x vehicle.imu_mount.y vehicle.imu_mount.z
    vehicle.cam_mount.x vehicle.cam_mount.y vehicle.cam_mount.z
    vehicle.cam_mount.roll vehicle.cam_mount.pitch vehicle.cam_mount.yaw
    vehicle.cam_optical.x vehicle.cam_optical.y vehicle.cam_optical.z
    vehicle.cam_optical.roll vehicle.cam_optical.pitch vehicle.cam_optical.yaw
    vehicle.nav_lidar_mount.x vehicle.nav_lidar_mount.y
    vehicle.nav_lidar_mount.z
    topics.clock topics.odom_ground_truth topics.scan_nav
    topics.safety_scan_back
    topics.imu topics.cam_depth topics.cam_info topics.cam_image topics.points3d
    topics.joint_state topics.drive_speed_read_a topics.wheel_odom
    topics.odometry_filtered topics.rf2o_odom_raw topics.rf2o_odom
    topics.fuse_odometry_filtered
    topics.initialpose topics.map
    topics.steer_cmd topics.traction_cmd
    topics.cmd_vel topics.cmd_vel_smoothed topics.speed_limit
    topics.cmd_vel_monitored topics.collision_monitor_state
    topics.navcmd_status
    vehicle.steer_limit_rad vehicle.steer_rate_limit_radps
    navcmd.accel_mps2 navcmd.steer_command_limit_rad
    frames.odom frames.base_link frames.imu frames.map
    frames.nav_lidar frames.rf2o_odom frames.pallet_cam frames.pallet_cam_optical
    map.dir map.name map.registration.file map.build_file
    localization.default_arm
    localization.map_server.package localization.map_server.executable
    localization.map_server.node_name
    localization.amcl.label localization.amcl.params_file
    localization.amcl.package localization.amcl.executable
    localization.amcl.node_name
    localization.slam.label localization.slam.params_file
    localization.slam.required_mode
    localization.slam.package localization.slam.executable
    localization.slam.node_name
    localization.lifecycle_timeout_s
    ekf.params_file ekf.rf2o_params_file ekf.node_name ekf.frequency_hz
    rf2o.workspace rf2o.package rf2o.executable rf2o.freq_hz rf2o.commit
    fuse.prefix fuse.deb_prefix fuse.package fuse.executable
    fuse.node_name fuse.params_file fuse.lag_duration_s
    fuse.optimization_frequency_hz fuse.transaction_timeout_s
    smoother.package smoother.executable smoother.node_name
    smoother.params_file smoother.active_timeout_s
    monitor.package monitor.executable monitor.node_name
    monitor.params_file monitor.active_timeout_s
    monitor.transform_check_s
    apriltag.prefix apriltag.deb_prefix apriltag.package
    apriltag.executable apriltag.lib apriltag.node_name
    apriltag.params_file
    dock.family dock.tag_id dock.model_dir
    topics.apriltag_detections topics.detected_dock_pose
    topics.dock_robot topics.undock_robot
    docking.package docking.executable docking.node_name
    docking.params_file docking.database_file
    docking.plugin_name docking.plugin_type docking.dock_id
    docking.lifecycle.package docking.lifecycle.executable
    docking.lifecycle.node_name
    docking.detected_node_name docking.detected_rate_hz
    docking.lifecycle_timeout_s
    nav.params_file nav.bt_xml nav.costmap_sections
    nav.planner.package nav.planner.executable nav.planner.node_name
    nav.controller.package nav.controller.executable
    nav.controller.node_name
    nav.behavior.package nav.behavior.executable nav.behavior.node_name
    nav.bt.package nav.bt.executable nav.bt.node_name
    nav.lifecycle.package nav.lifecycle.executable
    nav.lifecycle.node_name nav.default_goal
    slippery.slip_compliance_lateral slippery.slip_compliance_longitudinal
    slippery.service_timeout_ms
    paths.log_dir paths.log_keep_runs paths.pidfile paths.traction_file
    timing.world_load_s timing.settle_s timing.startup_check_s
    timing.stop_grace_s timing.gui_gate_poll_s timing.gui_gate_settle_s
    timing.spawn_service_timeout_ms timing.pid_wait_tries timing.pid_wait_s
)

# The shared read, plus the four paths only this script derives from it.
configure() {
    load_config "${REQUIRED_KEYS[@]}"
    PIDFILE="$REPO/$CFG_PATHS_PIDFILE"
    TRACTIONFILE="$REPO/$CFG_PATHS_TRACTION_FILE"
    # THE ROOT, AND `LOGDIR` IS THE ONE BRINGUP'S OWN DIRECTORY INSIDE
    # IT. Every refusal, every `status` line and every check in this
    # script names "$LOGDIR/<child>.log", so the two variables are all
    # that has to move: `start` points LOGDIR at a new subdirectory and
    # records it, and `status` and `stop` read that record back. With no
    # record - a crash, or a `status` after `stop` - LOGDIR stays the
    # root, which is where a pre-wave stack's logs are and is never
    # wrong, only older.
    LOGROOT="$REPO/$CFG_PATHS_LOG_DIR"
    LOGDIR="$LOGROOT"
    WORLD="$REPO/$CFG_WORLD_FILE"
    MODEL="$REPO/$CFG_VEHICLE_MODEL"
    EKF_PARAMS="$REPO/$CFG_EKF_PARAMS_FILE"
    EKF_RF2O_PARAMS="$REPO/$CFG_EKF_RF2O_PARAMS_FILE"
    # F4 TASK 1's, and it is derived unconditionally like the rest: the
    # command path is not an arm and there is no branch on which this
    # variable does not exist.
    SMOOTHER_PARAMS="$REPO/$CFG_SMOOTHER_PARAMS_FILE"
    # F4 TASK 3's, derived unconditionally for the same reason and READ
    # only on --monitor. The collision monitor is the smoother's sibling
    # rather than a nav child: it subscribes a Twist and a LaserScan and
    # publishes a Twist, and there is no planner, no costmap and no goal
    # in it - which is why it is a flag of its own and not part of --nav
    # (config.yaml monitor:).
    MONITOR_PARAMS="$REPO/$CFG_MONITOR_PARAMS_FILE"
    # F5 TASK 1's, derived unconditionally for set -u's reason on every
    # other optional arm: READ only on --dock. The SDF path is the same
    # construction tag_model.py write / furniture.py place use, so a
    # missing file is refused by the path the spawner will ask for.
    APRILTAG_PARAMS="$REPO/$CFG_APRILTAG_PARAMS_FILE"
    TAG_SDF="$REPO/$CFG_DOCK_MODEL_DIR/${CFG_DOCK_FAMILY}_${CFG_DOCK_TAG_ID}.sdf"
    # F5 TASK 2's TWO, derived unconditionally for set -u's reason.
    # READ only on --dock. The binary lives under the ROS prefix, which
    # is the directory of paths.ros_setup, not a third spelling of
    # /opt/ros/jazzy.
    DOCKING_PARAMS="$REPO/$CFG_DOCKING_PARAMS_FILE"
    DOCK_DB="$REPO/$CFG_DOCKING_DATABASE_FILE"
    DOCKING_BIN="$(dirname "$CFG_PATHS_ROS_SETUP")/lib/$CFG_DOCKING_PACKAGE/$CFG_DOCKING_EXECUTABLE"
    # F4 TASK 2's TWO, DERIVED UNCONDITIONALLY for RF2O_WS's reason: a
    # variable that exists only on one branch is a variable `set -u`
    # aborts on from the other. Neither is READ unless --nav was given.
    #   THE TREE IS AN ABSOLUTE PATH AND THAT IS NOT COSMETIC.
    #   bt_navigator resolves `default_nav_to_pose_bt_xml` against the
    #   PROCESS's working directory, and this script may be run from
    #   anywhere; a relative name would be a file bt_navigator looks for
    #   wherever the operator's shell happened to be standing, and a
    #   tree it cannot open is a navigator that falls back to nav2's own
    #   - which has Spin and BackUp in it.
    NAV_PARAMS="$REPO/$CFG_NAV_PARAMS_FILE"
    NAV_BT="$REPO/$CFG_NAV_BT_XML"
    # THE SIX SECTIONS nav2.yaml HAS TO BE ADDRESSED TO, in one string
    # because check_nav_params() takes them as arguments. FOUR are the
    # servers this script starts; TWO are the costmap SUB-NODES those
    # servers construct, which have no process, are never named by
    # `status` and are never swept - and which come up on the package
    # defaults, in silence, if their block is addressed to nobody.
    NAV_SECTIONS="$CFG_NAV_PLANNER_NODE_NAME $CFG_NAV_CONTROLLER_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_BEHAVIOR_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_BT_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_LIFECYCLE_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_COSTMAP_SECTIONS"
    # THE ONE PATH ON THIS TRACK THAT IS NOT UNDER $REPO. The rf2o build
    # tree is the USER's - tools/install_rf2o.sh's argument, and F2
    # constraint 14's - so config.yaml writes it with a leading ~/ and
    # both readers expand it against $HOME the same way. Derived
    # unconditionally: it costs a string, and a variable that exists only
    # on one branch is a variable `set -u` aborts on from the other.
    RF2O_WS="${CFG_RF2O_WORKSPACE/#\~/$HOME}"
    RF2O_BIN="$RF2O_WS/install/$CFG_RF2O_PACKAGE/lib/$CFG_RF2O_PACKAGE/$CFG_RF2O_EXECUTABLE"
    FUSE_PARAMS="$REPO/$CFG_FUSE_PARAMS_FILE"
    # F3 TASK 2's, AND THEY ARE DERIVED UNCONDITIONALLY for RF2O_WS's
    # reason: a variable that exists only on one branch is a variable
    # `set -u` aborts on from the other. Nothing here is READ unless
    # --localize was given.
    MAP_DIR="$REPO/$CFG_MAP_DIR/$CFG_MAP_NAME"
    MAP_YAML="$MAP_DIR/$CFG_MAP_NAME.yaml"
    MAP_BUILD="$MAP_DIR/$CFG_MAP_BUILD_FILE"
    # THE POSE GRAPH, AND slam_toolbox WANTS IT WITHOUT ITS SUFFIX. Its
    # deserialiser appends `.posegraph` and `.data` itself, so what
    # `map_file_name` is given is the STEM - and the two full paths
    # beside it are what this script hashes against the build manifest.
    MAP_GRAPH="$MAP_DIR/$CFG_MAP_NAME"
    # ---- AND F3 TASK 3's: WHICH LOCALISER, RESOLVED ONCE ----
    # The command line may name one, config.yaml names the default, and
    # everything downstream reads the LOC_* variables rather than asking
    # again. A value that names no arm is refused HERE - before the GPU
    # preflight, before ROS is sourced and before any child - because the
    # alternative is a bringup that starts nine children and then cannot
    # say what it started.
    LOCALIZER="${LOCALIZER:-$CFG_LOCALIZATION_DEFAULT_ARM}"
    case "$LOCALIZER" in
        "$CFG_LOCALIZATION_AMCL_LABEL")
            LOC_LABEL="$CFG_LOCALIZATION_AMCL_LABEL"
            LOC_PARAMS="$REPO/$CFG_LOCALIZATION_AMCL_PARAMS_FILE"
            LOC_PACKAGE="$CFG_LOCALIZATION_AMCL_PACKAGE"
            LOC_EXECUTABLE="$CFG_LOCALIZATION_AMCL_EXECUTABLE"
            LOC_NODE="$CFG_LOCALIZATION_AMCL_NODE_NAME"
            # THE LIFECYCLE NODES THIS ARM STARTS, IN THE ORDER THEY MUST
            # BE DRIVEN - and the same list is what LOC_PARAMS has to be
            # addressed to, because rclcpp applies nothing from a block
            # addressed to a node that is not running. map_server FIRST:
            # amcl's on_activate waits for a map on the latched topic and
            # an INACTIVE map_server never publishes one.
            LOC_NODES="$CFG_LOCALIZATION_MAP_SERVER_NODE_NAME $LOC_NODE" ;;
        "$CFG_LOCALIZATION_SLAM_LABEL")
            LOC_LABEL="$CFG_LOCALIZATION_SLAM_LABEL"
            LOC_PARAMS="$REPO/$CFG_LOCALIZATION_SLAM_PARAMS_FILE"
            LOC_PACKAGE="$CFG_LOCALIZATION_SLAM_PACKAGE"
            LOC_EXECUTABLE="$CFG_LOCALIZATION_SLAM_EXECUTABLE"
            LOC_NODE="$CFG_LOCALIZATION_SLAM_NODE_NAME"
            # ONE NODE ON THIS ARM, AND THAT IS THE ARM. slam_toolbox's
            # localisation node deserialises the pose graph itself and
            # rasters its own occupancy grid onto topics.map, so a
            # map_server here would be a SECOND publisher of that topic
            # serving a different rendering of the same building.
            LOC_NODES="$LOC_NODE" ;;
        *)
            refuse "--localize names a localiser this script has" \
                "$0 (the start flags) and $CONFIG (localization:)" \
                "'$LOCALIZER' is not one of them. The arms are:" \
                "  $CFG_LOCALIZATION_AMCL_LABEL  $CFG_LOCALIZATION_MAP_SERVER_PACKAGE serves the GRID on $CFG_TOPICS_MAP and $CFG_LOCALIZATION_AMCL_PACKAGE localises in it" \
                "  $CFG_LOCALIZATION_SLAM_LABEL  $CFG_LOCALIZATION_SLAM_PACKAGE's $CFG_LOCALIZATION_SLAM_EXECUTABLE deserialises the POSE GRAPH and localises in that" \
                "BOTH publish $CFG_FRAMES_MAP -> $CFG_FRAMES_ODOM, so they are ALTERNATIVES and never layers:" \
                "tf2 would carry whichever arrived last (F3 constraint 15)." \
                "NOTHING WAS STARTED. Pick one:" \
                "  $0 start --headless --localize        # the default, which is $CFG_LOCALIZATION_DEFAULT_ARM" \
                "  $0 start --headless --localize $CFG_LOCALIZATION_SLAM_LABEL" ;;
    esac
    # THE SECOND PATH THAT IS NOT UNDER $REPO, AND ITS ARITHMETIC IS
    # _common.sh's RATHER THAN A SECOND COPY OF IT. fuse_paths() sets
    # FUSE_PREFIX, FUSE_ROS_PREFIX, FUSE_BIN and FUSE_MANIFEST off the
    # same four config keys tools/install_fuse.sh reads them off, so the
    # unpacker and the launcher cannot disagree about where the tree is.
    # (The rf2o line above is the older habit - two scripts, two copies -
    # and is left alone rather than churned by this task.)
    #   CALLED UNCONDITIONALLY, for RF2O_WS's reason: it costs four
    #   string operations, and a variable that exists only on one branch
    #   is a variable `set -u` aborts on from the other.
    fuse_paths
    apriltag_paths
}

# THE STACK AS COMMAND-LINE PATTERNS, AND THE LIST IS _common.sh's.
# rtf_probe.sh asks the same question - which processes on this machine
# belong to this stack - and it used to ask it with a copy of its own,
# which is how it came to print a stack with no estimator in it after
# F1 Task 3 added one here. The list, the ordering and the maintenance
# obligation are all in that file now; this is the only line here.
PATTERNS=("${M5V3_PATTERNS[@]}")

# WHY OWNERSHIP IS DECIDED BY THE ENVIRONMENT AND NOT BY THE COMMAND LINE.
# This stack's command lines are not distinctive: the world server's names
# a file under m6/ (the floor is m6's, by reference), and the bridge's is
# nothing but topic names. What separates this stack from m6's, from
# step5's and from a stranger is GZ_PARTITION, which IS the definition of
# "this graph" and is inherited by every child. It is also why a recycled
# pid is safe here: a pid that has come round to name somebody else does
# not carry m5v3 in its environment. Unreadable environ = left alone, the
# safe direction.
# 2>/dev/null PRECEDES the input redirect on purpose: bash applies
# redirections left to right, so with it last the shell's own "No such
# file" for a pid that exited between nomination and check still reaches
# the terminal (m6.sh:143, measured there).
ours() {
    tr '\0' '\n' 2>/dev/null < "/proc/$1/environ" \
        | grep -qxF "GZ_PARTITION=$GZ_PARTITION"
}

sweep() {  # sweep <signal>
    local sig="$1" pat pid cmd
    for pat in "${PATTERNS[@]}"; do
        while read -r pid cmd; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            [ "$pid" = "$$" ] && continue
            # A sweep matching its own command line proves nothing: these
            # scripts quote the patterns in their own text and can carry
            # the partition (demo.sh:1037, LESSONS 2026-08-06).
            case "$cmd" in *m5v3.sh*|*m6.sh*|*demo.sh*|*stack.sh*) continue ;; esac
            ours "$pid" || continue
            kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid ($pat)"
        done < <(pgrep -af "$pat" 2>/dev/null)
    done
}

# A ROS PARAMETER FILE HAS TO BE ADDRESSED TO THE NODE THIS SCRIPT
# STARTS, and since F2 Task 3 there can be TWO of them - ekf.yaml always,
# ekf_rf2o.yaml with --rf2o - so the check is a function rather than two
# copies of one grep (tools/_common.sh's rule, applied inside this file).
#
# WHY IT IS CHECKED AND NOT WRITTEN DOWN. A parameter file is keyed by
# the node's name, and rclcpp does NOT complain about a block addressed
# to somebody else - it applies nothing and starts. That failure is worse
# than a missing file, because the `-p` overrides below still land: the
# topics, the frames and the rate are all set, so ekf_node comes up on
# its PACKAGE DEFAULTS, subscribes nothing, fuses nothing, and publishes
# 50 Hz of a pose that never moves and an identity transform. `status`
# says ALIVE, the topic is there at its configured rate, the evidence
# recorder's stream arrives - EVERY instrument this track named would
# report a healthy stack. A misspelt key INSIDE the file is the same
# failure by another route, and rclcpp is equally silent about it.
#   ekf.yaml's header carried this as a MAINTENANCE OBLIGATION in prose,
#   which is the one form of guarantee this track accepts nowhere else:
#   the imu_mount copy is diffed against the model that decides it, every
#   config key is checked by its dotted name, the child list lives in one
#   file. This is that idiom, one grep, before anything starts.
#   AND THE OVERLAY IS THE EASIER ONE TO GET WRONG, which is why it gets
#   the same check rather than a lighter one: it is read SECOND, so a
#   block addressed to nobody would leave the filter correctly configured
#   for the shipping arm with an odom1 topic on its command line and no
#   odom1_config anywhere - an rf2o run that fused no rf2o, reported by
#   nothing.
check_ekf_params() {  # check_ekf_params <file> <the config key naming it>
    local file="$1" key="$2"
    grep -q "^${CFG_EKF_NODE_NAME}:" "$file" || refuse \
        "the EKF parameter file is addressed to $CFG_EKF_NODE_NAME" \
        "$file and $CONFIG (ekf.node_name, $key)" \
        "there is no top-level '$CFG_EKF_NODE_NAME:' key in that file, so" \
        "every parameter in it belongs to a node that is never started." \
        "ekf_node would come up on its PACKAGE DEFAULTS with the topic," \
        "frame and rate overrides still applied: 50 Hz of a pose that" \
        "never moves, an identity transform, and 'status' ALIVE." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')"
}

# AND THE SMOOTHER'S, F4 TASK 1, FOR check_ekf_params()'s REASON IN A
# DIFFERENT CURRENCY. nav2_velocity_smoother is a rclcpp lifecycle node,
# so a parameter file addressed to somebody else applies NOTHING and it
# does not complain: the node comes up on its PACKAGE DEFAULTS -
# 0.5 m/s, 2.5 rad/s, OPEN_LOOP feedback, scale_velocities FALSE - and
# every one of those is wrong here in a way nothing downstream can see.
# The vehicle would still drive: slower than commanded, on a curvature
# corrupted by two axes limited independently, ramping against this
# node's own last command rather than against the vehicle's measured
# twist. `status` would read ALIVE, /cmd_vel_smoothed would be at rate,
# and the converter would faithfully convert the wrong twist.
check_smoother_params() {  # check_smoother_params <file>
    local file="$1"
    grep -q "^${CFG_SMOOTHER_NODE_NAME}:" "$file" || refuse \
        "the smoother parameter file is addressed to $CFG_SMOOTHER_NODE_NAME" \
        "$file and $CONFIG (smoother.node_name, smoother.params_file)" \
        "there is no top-level '$CFG_SMOOTHER_NODE_NAME:' key in that" \
        "file, so every parameter in it belongs to a node that is never" \
        "started - and nav2_velocity_smoother would come up on its" \
        "PACKAGE DEFAULTS: 0.5 m/s, 2.5 rad/s, OPEN_LOOP, and vx and wz" \
        "limited INDEPENDENTLY, which on a nonholonomic vehicle silently" \
        "changes the commanded arc." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')"
}

# AND THE COLLISION MONITOR'S, F4 Task 3. Same check, and the package
# defaults it guards against are worse here than the smoother's: a
# collision_monitor that never received this file comes up with NO
# polygons and NO observation sources at all - a node that relays every
# twist untouched, publishes a state topic saying DO_NOTHING for ever,
# and looks from the outside exactly like a monitor watching an empty
# floor.
#   IT ALSO CHECKS THE TWO POLYGON SETS BY NAME, because a `polygons:`
# list naming a block that does not exist is one nav2 warning and a node
# that comes up anyway. The two names are collision_monitor.yaml's own
# and they are checked HERE rather than only in a test for the reason
# every check in this script exists: a test says the file on disk is
# right, and this says the file being USED is.
check_monitor_params() {  # check_monitor_params <file>
    local file="$1" want
    grep -q "^${CFG_MONITOR_NODE_NAME}:" "$file" || refuse \
        "the monitor parameter file is addressed to $CFG_MONITOR_NODE_NAME" \
        "$file and $CONFIG (monitor.node_name, monitor.params_file)" \
        "there is no top-level '$CFG_MONITOR_NODE_NAME:' key in that" \
        "file, so every parameter in it belongs to a node that is never" \
        "started - and nav2_collision_monitor would come up with NO" \
        "polygons and NO observation sources: a node that relays every" \
        "twist untouched and reports DO_NOTHING for ever, which looks" \
        "exactly like a monitor watching an empty floor." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')"
    for want in MonitorStop MonitorSlowdown; do
        grep -q "^ *${want}:" "$file" || refuse \
            "collision_monitor.yaml defines the polygon set '$want'" \
            "$file" \
            "its 'polygons:' list names $want and there is no block by" \
            "that name in the file. nav2 warns once and comes up" \
            "without it, so the stop zone or the slowdown zone would" \
            "simply not exist and nothing downstream would say so."
    done
}

# F5 TASK 1's DETECTOR FILE. Same node-name check as the monitor: a
# file addressed to a node this script never starts is a file of
# dead parameters, and apriltag_ros would come up on family tag36h11
# at 0.16 m - a detector looking for a marker this stack did not print.
check_apriltag_params() {  # check_apriltag_params <file>
    local file="$1"
    grep -q "^${CFG_APRILTAG_NODE_NAME}:" "$file" || refuse \
        "the apriltag parameter file is addressed to $CFG_APRILTAG_NODE_NAME" \
        "$file and $CONFIG (apriltag.node_name, apriltag.params_file)" \
        "there is no top-level '$CFG_APRILTAG_NODE_NAME:' key in that" \
        "file, so every parameter in it belongs to a node that is never" \
        "started." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')"
}

check_docking_params() {  # check_docking_params <file>
    local file="$1"
    grep -q "^${CFG_DOCKING_NODE_NAME}:" "$file" || refuse \
        "the docking parameter file is addressed to $CFG_DOCKING_NODE_NAME" \
        "$file and $CONFIG (docking.node_name, docking.params_file)" \
        "there is no top-level '$CFG_DOCKING_NODE_NAME:' key in that" \
        "file, so every parameter in it belongs to a node that is never" \
        "started."
    grep -q "^${CFG_DOCKING_LIFECYCLE_NODE_NAME}:" "$file" || refuse \
        "the docking parameter file is addressed to $CFG_DOCKING_LIFECYCLE_NODE_NAME" \
        "$file and $CONFIG (docking.lifecycle.node_name)" \
        "there is no top-level '$CFG_DOCKING_LIFECYCLE_NODE_NAME:' key."
}

# THE FACTOR GRAPH'S PARAMETER FILE, CHECKED THE SAME WAY AND THEN ONCE
# MORE - because on that arm one of the two things that must be true is
# said by an ABSENCE, and an absence is not a mechanism.
#
# THE FIRST HALF IS check_ekf_params()'s, IN THIS NODE'S CURRENCY. A ROS
# parameter file is keyed by the node's name; a file addressed to
# somebody else applies nothing. This node is EXACTLY AS QUIET ABOUT IT
# as ekf_node, which was measured rather than assumed and went the other
# way from the first guess: pointed at fuse.yaml under a different node
# name it starts, prints "No ignition sensors were specified.
# Optimization will begin immediately.", and then does NOTHING - no
# sensor models, no motion model, no publisher, no topic advertised, and
# `status` ALIVE. There is no required parameter to miss because there
# is no sensor declared to require it. EVIDENCE_FUSION.md 11.2(a).
#
# THE SECOND HALF IS F2 GLOBAL CONSTRAINT 13, HELD BY A CHECK.
# robot_localization refuses a pose with six `false` entries in an array
# that is always fifteen long, so ekf.yaml can SAY the refusal. fuse's
# sensor models take LISTS OF DIMENSION NAMES, and the way to fuse no
# position and no orientation is for the key not to exist: an empty YAML
# list is not a substitute, because rclcpp cannot infer a type for `[]`
# and the node aborts with `parameter_value_from failed ... No parameter
# value set` (measured, EVIDENCE_FUSION.md 11.2). So the refusal is an
# absence, and a refusal that is an absence is one careless line away
# from being reversed by somebody who thinks they are adding a feature.
#   THE THREE KEYS IT REFUSES, AND WHY EACH ONE IS THERE:
#     position_dimensions / orientation_dimensions - the POSE. Fusing a
#       dead-reckoned pose means scoring an estimator against its own
#       input; the wheel odometry publishes 1000.0 on all six pose axes
#       as a do-not-fuse flag and this is the second, independent
#       refusal that ekf.yaml gets from its six false flags.
#     linear_acceleration_dimensions - the ACCELEROMETER. F2 Task 2
#       measured that channel diverging the other arm's filter at
#       startup and reversed the ruling that fused it
#       (EVIDENCE_FUSION.md 9); the lever arm this vehicle has would
#       land on exactly that axis. It is the entry a future editor is
#       most likely to add back, because it looks like free information.
#   IT IS A GREP OVER THE WHOLE FILE AND NOT A YAML QUERY, deliberately:
#   a shell cannot parse YAML, and a key that appears anywhere in this
#   file - under any sensor, commented back in, spelled in a block this
#   check does not understand - is a thing whose author has to come and
#   argue with this refusal. Every mention of the three inside fuse.yaml
#   is therefore in PROSE that does not begin a key, which is what the
#   pattern below tests for.
check_fuse_params() {  # check_fuse_params <file>
    local file="$1" hit
    grep -q "^${CFG_FUSE_NODE_NAME}:" "$file" || refuse \
        "the fuse parameter file is addressed to $CFG_FUSE_NODE_NAME" \
        "$file and $CONFIG (fuse.node_name, fuse.params_file)" \
        "there is no top-level '$CFG_FUSE_NODE_NAME:' key in that file, so" \
        "every parameter in it belongs to a node that is never started." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')"
    local refused='position_dimensions\|orientation_dimensions'
    refused="$refused\|linear_acceleration_dimensions"
    hit="$(grep -n "^[[:space:]]*\($refused\)[[:space:]]*:" "$file" || true)"
    [ -z "$hit" ] || refuse \
        "the factor graph fuses no pose and no acceleration" \
        "$file (F2 global constraint 13, and EVIDENCE_FUSION.md 9 for ax)" \
        "one of the three dimension lists this arm REFUSES is set here:" \
        "$hit" \
        "on this node a refusal is an ABSENCE - fuse takes lists of" \
        "dimension names and an empty YAML list will not load at all -" \
        "so the key being present IS the channel being fused." \
        "the POSE is refused because a dead-reckoned pose has unbounded" \
        "error and fusing it scores an estimator against its own input;" \
        "the ACCELERATION because F2 Task 2 measured that channel" \
        "diverging the other arm at startup and reversed the ruling that" \
        "fused it, and because the IMU's 0.50 m lever arm lands on it." \
        "NOTHING WAS STARTED. If this is deliberate it is a RULING, and" \
        "a ruling on this track arrives with a measurement and an edit to" \
        "this check - not with a line in a parameter file."
}

# THE LOCALISER'S PARAMETER FILE HAS TO BE ADDRESSED TO **BOTH** NODES
# THIS ARM STARTS, and that is check_ekf_params()'s argument with one
# more thing to go wrong. amcl.yaml carries a `map_server:` block and an
# `amcl:` block; rclcpp applies NOTHING from a block addressed to
# somebody else and says nothing about it, so a misspelt top-level key
# would leave that node on its PACKAGE DEFAULTS with the `-p` overrides
# still landing.
#
# WHAT EACH ONE WOULD LOOK LIKE, WHICH IS WHY BOTH ARE CHECKED. A
# map_server on its defaults still serves the grid (its `yaml_filename`
# is an override) and would differ only in its bond - quiet, and nearly
# harmless. An AMCL on its defaults is the dangerous one: it would run
# the OMNI-capable defaults this file argues against on every count -
# alphas of 0.2 (45 % of every distance), 60 beams instead of 271,
# sigma_hit 0.2 instead of the measured 0.029, z_rand 0.5 instead of the
# measured 0.074 - and it would publish map -> odom the whole time,
# looking exactly like a localiser. Every figure taken off it would be a
# figure about nav2's defaults wearing this file's name.
#
# AND ON THE slam ARM IT IS THE SAME CHECK WITH MORE AT STAKE, WHICH IS
# WHY THE NODE LIST IS AN ARGUMENT AND NOT A CONSTANT. m5_ver3/
# slam_loc.yaml is addressed to `slam_loc:` and that block is where
# `mode: localization` lives - the mapper that built the frozen map has
# its own file (slam.yaml, `slam_toolbox:`) and this arm never reads it.
# A localiser that missed its block
# would come up in the package default MODE, which is MAPPING: it would
# deserialise nothing, start an EMPTY graph, build a new map of whatever
# it could see and publish map -> odom out of it. Nothing would look
# wrong from any other angle, and every absolute figure would be a pose
# in a map that was made up as the truck drove, scored through a
# registration belonging to one it never opened.
# AND ON THE slam ARM, THE ONE LINE THAT MAKES THAT FILE A LOCALISER'S.
# check_loc_params() above proves the parameter file is ADDRESSED to the
# node this arm starts; this proves it says the one thing that node
# cannot come up without. They are two different failures and the first
# cannot see the second: a `slam_loc:` block that parses and applies but
# carries no `mode:` leaves slam_toolbox on its PACKAGE DEFAULT, which is
# MAPPING - it would deserialise nothing, start an EMPTY graph, build a
# new map of whatever it could see and publish map -> odom out of it.
# Alive, at rate, ALL of the other localisation checks green, and every
# absolute figure a pose in a map that was invented as the truck drove.
#   THE EXPECTED VALUE IS config.yaml's AND THE ACTUAL IS THE FILE's,
#   which is the whole point of a read-back: two copies that are COMPARED
#   cannot drift silently, where one copy passed as a `-p` override
#   cannot be wrong and cannot be checked either - and would make
#   slam_loc.yaml describe a node this stack does not run. It is
#   tools/build_map.sh's occupied_thresh / free_thresh idiom - "these are
#   not passed, they are CHECKED" - one arm over.
#   THE GREP TOLERATES YAML SPACING AND NOTHING ELSE. Leading indent and
#   any run of spaces after the colon are fine, and a trailing comment is
#   fine; `mode: localization_extra` is NOT, which is what the
#   end-of-token bound is for.
check_slam_mode() {
    grep -qE "^[[:space:]]*mode:[[:space:]]+$CFG_LOCALIZATION_SLAM_REQUIRED_MODE([[:space:]]|$)" \
        "$LOC_PARAMS" || refuse \
        "the localiser's parameter file says mode: $CFG_LOCALIZATION_SLAM_REQUIRED_MODE" \
        "$LOC_PARAMS and $CONFIG (localization.slam.required_mode)" \
        "no such line is in it. What that file says instead:" \
        "$(grep -nE '^[[:space:]]*mode:' "$LOC_PARAMS" || echo '(no mode: line at all)')" \
        "$CFG_LOCALIZATION_SLAM_PACKAGE's DEFAULT MODE IS MAPPING. Without" \
        "this line $CFG_LOCALIZATION_SLAM_EXECUTABLE deserialises NOTHING," \
        "starts an EMPTY graph, builds a new map of whatever it can see and" \
        "publishes $CFG_FRAMES_MAP -> $CFG_FRAMES_ODOM out of it - alive, at" \
        "rate, every other check on this arm green, and every absolute" \
        "figure a pose in a map invented as the truck drove." \
        "NOTHING WAS STARTED."
}

check_loc_params() {  # check_loc_params <file> <node>...
    local file="$1" node
    shift
    for node in "$@"; do
        grep -q "^${node}:" "$file" || refuse \
            "the localiser's parameter file is addressed to $node" \
            "$file and $CONFIG (localization.$LOCALIZER.params_file,"\
"localization.*.node_name)" \
            "there is no top-level '$node:' key in that file, so every" \
            "parameter meant for that node belongs to one that is never" \
            "started. rclcpp applies nothing and reports nothing: the" \
            "node comes up on its PACKAGE DEFAULTS with the topic and" \
            "frame overrides still applied, publishes map -> odom, and" \
            "looks exactly like a localiser." \
            "the top-level keys that file does define:" \
            "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')"
    done
}

# THE NAV ARM'S PARAMETER FILE HAS TO BE ADDRESSED TO **SIX** NODES,
# AND TWO OF THEM ARE NOT PROCESSES. That is check_loc_params()'s
# argument with the stakes raised twice over.
#
# THE FOUR SERVERS ARE check_ekf_params()'s CASE, FOUR TIMES. rclcpp
# applies NOTHING from a block addressed to somebody else and says
# nothing about it, so a misspelt top-level key leaves that server on its
# PACKAGE DEFAULTS with the `-p` overrides still landing. A
# controller_server on nav2's defaults runs a DiffDrive MPPI at 0.5 m/s
# with no Ackermann constraint at all - it would command curvatures this
# vehicle cannot steer and the converter would clamp every one of them.
# A planner_server on its defaults is DUBIN rather than REEDS_SHEPP, a
# 0.4 m turning radius and `allow_unknown: true`: forward-only paths, at
# a radius the plant cannot deliver, straight through unsurveyed floor.
#
# AND THE TWO COSTMAPS ARE WORSE, BECAUSE NOTHING ELSE ON THIS STACK CAN
# SEE THEM AT ALL. `local_costmap` and `global_costmap` are
# nav2_costmap_2d SUB-NODES constructed inside those servers, in
# namespaces of their own: they have no process, `status` never names
# them and the sweep never nominates them. On the package defaults a
# costmap is a 3 x 3 m window with a CIRCULAR footprint of radius 0.10 m
# - a fifth of this vehicle's inscribed radius and a nineteenth of its
# circumscribed one - and it would report every path through every rack
# as clear. Every process ALIVE, every lifecycle node ACTIVE, and the
# planner planning happily through the building.
#
# THE THREE ADDRESSES ARE READ BACK, AND THAT IS BECAUSE A `-p` CANNOT
# REACH A SUB-NODE. Every other parameter file on this track is handed
# its topics and frames on a command line so that config.yaml stays the
# one home for them; the costmaps have no command line, so nav2.yaml
# holds those three strings and this compares them with config.yaml's
# before anything starts. It is tools/build_map.sh's own idiom - "these
# are not passed, they are CHECKED" - and the failure it prevents is
# silent at every other level: a static layer subscribed to a map topic
# nobody publishes stays empty for ever, and with `allow_unknown: false`
# the planner then refuses every goal after max_planning_time, once,
# into its own log.
#   THE PER-SECTION FRAME CHECKS ARE tests/test_nav2_params.py's, and
#   the split is by what each tool can do. A shell cannot parse YAML, so
#   it cannot tell local_costmap's `global_frame: odom` from
#   global_costmap's `global_frame: map`; pytest loads the file and
#   checks each section by name. What is HERE is what has to run before
#   a process starts.
check_nav_params() {  # check_nav_params <file> <section>...
    local file="$1" node
    shift
    for node in "$@"; do
        grep -q "^${node}:" "$file" || refuse \
            "the nav parameter file is addressed to $node" \
            "$file and $CONFIG (nav.*.node_name, nav.costmap_sections)" \
            "there is no top-level '$node:' key in that file, so every" \
            "parameter meant for it belongs to a node that is never" \
            "configured. rclcpp applies nothing and reports nothing." \
            "ON A SERVER that means nav2's own defaults with this" \
            "script's overrides still applied - a DiffDrive controller" \
            "on a tricycle, or a DUBIN planner at a 0.4 m radius" \
            "through unsurveyed floor." \
            "ON A COSTMAP it is worse: they are SUB-NODES with no" \
            "process, so 'status' never names them and nothing else" \
            "here can see them. The default is a 3 x 3 m window and a" \
            "CIRCULAR footprint of radius 0.10 m, which reports every" \
            "path through every rack as clear." \
            "the top-level keys that file does define:" \
            "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')" \
            "NOTHING WAS STARTED."
    done
    check_address "$file" map_topic "$CFG_TOPICS_MAP" \
        "topics.map" \
        "global_costmap's static layer subscribes there. Wrong, it" \
        "waits for a latched message that has already been published" \
        "and the costmap stays wall-to-wall NO_INFORMATION - which" \
        "with allow_unknown: false refuses every goal." \
        "IT IS IN THAT FILE AT ALL only because nav2's costmaps are" \
        "SUB-NODES with no command line, so a '-p' override cannot" \
        "reach them."
    check_address "$file" topic "$CFG_TOPICS_SCAN_NAV" \
        "topics.scan_nav" \
        "local_costmap's obstacle layer marks and clears from there." \
        "Wrong, the layer is empty and the rolling costmap carries no" \
        "live perception at all - which looks exactly like a floor" \
        "with nothing on it." \
        "IT IS IN THAT FILE AT ALL only because nav2's costmaps are" \
        "SUB-NODES with no command line, so a '-p' override cannot" \
        "reach them."
    check_address "$file" robot_base_frame "$CFG_FRAMES_BASE_LINK" \
        "frames.base_link" \
        "every costmap and both navigators place the vehicle by that" \
        "frame. Wrong, they find no transform and report it as a tf" \
        "timeout - and Costmap2DROS::on_activate BLOCKS on it, so the" \
        "lifecycle transition never returns."
}

# ONE ADDRESS IN A PARAMETER FILE, COMPARED WITH config.yaml's. Every
# line carrying <key> must name <want>, and at least one must exist: a
# key that is absent is a package default silently in force, and a key
# present twice with two values is worse than either.
#
# IT IS ARM-AGNOSTIC ON PURPOSE. What it knows is "config.yaml owns
# every address on this track, and this file has a copy" - which is a
# fact about the SPLIT rather than about any one arm. The reason a copy
# exists at all is the CALLER's to state, and every call above states
# it.
check_address() {  # check_address <file> <key> <want> <cfgkey> <line>...
    local file="$1" key="$2" want="$3" cfgkey="$4" found other
    shift 4
    found="$(grep -nE "^[[:space:]]*${key}:[[:space:]]" "$file" || true)"
    [ -n "$found" ] || refuse \
        "$(basename "$file") sets $key" "$file and $CONFIG ($cfgkey)" \
        "there is no '$key:' line in that file at all, so the package" \
        "default is in force and nothing downstream would say so." \
        "$@" \
        "NOTHING WAS STARTED."
    other="$(printf '%s\n' "$found" \
             | grep -vE ":[[:space:]]*${key}:[[:space:]]+\"?${want}\"?[[:space:]]*(#.*)?$" \
             || true)"
    [ -z "$other" ] || refuse \
        "$(basename "$file")'s $key is $CONFIG's $cfgkey" \
        "$file ($key) and $CONFIG ($cfgkey)" \
        "config.yaml says '$want' and these lines say something else:" \
        "$other" \
        "$@" \
        "config.yaml IS THE ONE HOME FOR EVERY ADDRESS ON THIS TRACK," \
        "and a copy that cannot say when it has gone stale is a copy" \
        "that will." \
        "NOTHING WAS STARTED."
}

# IS THE MAP ON DISK THE MAP THE COMMITTED REGISTRATION WAS FITTED TO?
# F3 constraint 16 says the map is FROZEN once scored, and a freeze is a
# MECHANISM rather than a promise - so this is the mechanism, at the
# bringup, before a single process is started.
#
# WHAT IT PREVENTS. Every absolute figure this arm produces is a map pose
# carried into the building by maps/<name>/registration.yaml, and that
# transform belongs to ONE grid: a rebuilt map has its own rotation from
# the building, off by whatever the two builds differ by, and NOTHING
# downstream would notice. The registration carries the md5 of the .pgm
# it was fitted to for exactly this, and tools/map_register.py's
# load_registration() refuses a mismatch on the ANALYSIS side - but that
# is an hour after the run, and by then the recording exists and looks
# like every other recording.
#
# WHY IT IS HERE AND NOT ONLY THERE. This is the only place that can say
# "NOTHING WAS STARTED". It is also the only place that can catch the
# other half of the pair: `map_yaml_md5`, which map_server READS (the
# resolution, the origin and the two thresholds all come out of it) and
# which no consumer of the registration ever hashes.
#   THE GRID IS HASHED ON BOTH ARMS AND THE POSE GRAPH ON ONE, AND EACH
#   OF THOSE IS A DECISION RATHER THAN AN ECONOMY. Every absolute figure
#   from EITHER arm is carried into the building by registration.yaml,
#   which was fitted to the .pgm and reads the .yaml's resolution and
#   origin - so both arms check both. The .posegraph and .data are
#   62.5 MB and only the `slam` arm opens them; on the `amcl` arm they
#   are read by nothing, so hashing them there would be a fifth of a
#   second of md5 per bringup answering a question that arm never asks.
#   AND THEIR HASH COMES OUT OF A DIFFERENT FILE, WHICH IS THE POINT.
#   registration.yaml states the md5 of what it was FITTED to and
#   nothing else; build.txt is what tools/build_map.sh wrote when it
#   saved all four artifacts out of one run, and it is the only place
#   that says the grid and the graph came from the same build. So the
#   slam arm's check binds the graph to the manifest, the manifest binds
#   it to the grid, and the grid is bound to the registration by the two
#   checks above - one chain, three links, and a rebuild breaks it at
#   the first.
check_frozen_map() {
    local reg="$MAP_DIR/$CFG_MAP_REGISTRATION_FILE" file key want got
    [ -d "$MAP_DIR" ] || refuse "the frozen map is on disk" \
        "$CONFIG (map.dir, map.name)" \
        "there is no directory at $MAP_DIR" \
        "it is COMMITTED - grid, pose graph, build.txt and the" \
        "registration - and this arm consumes it read-only." \
        "NOTHING WAS STARTED."
    for file in "$MAP_YAML" "$MAP_DIR/$CFG_MAP_NAME.pgm" "$reg"; do
        [ -f "$file" ] || refuse "the frozen map is complete" "$MAP_DIR" \
            "$file is missing." \
            "EVIDENCE_MAP_V3.md 8 lists what a map artifact is; a" \
            "directory with a hole in it is not one." \
            "NOTHING WAS STARTED."
    done
    command -v md5sum >/dev/null 2>&1 || refuse \
        "md5sum is installed" "$0 (check_frozen_map)" \
        "without it this bringup cannot check that the grid on disk is" \
        "the grid the committed registration was fitted to, and a" \
        "localisation run against an unverified map is a run whose" \
        "every absolute figure is unattributable: apt install coreutils"
    for key in map_md5:pgm map_yaml_md5:yaml; do
        want="$(sed -n "s/^${key%%:*}: *//p" "$reg" | head -1)"
        file="$MAP_DIR/$CFG_MAP_NAME.${key##*:}"
        [ -n "$want" ] || refuse \
            "the committed registration states ${key%%:*}" "$reg" \
            "there is no '${key%%:*}:' line in it, so it is not a" \
            "registration tools/map_register.py wrote - or it is a" \
            "truncated one. Re-derive it:" \
            "  python3 $M5V3/tools/map_register.py derive --write" \
            "NOTHING WAS STARTED."
        got="$(md5sum "$file" | cut -d' ' -f1)"
        [ "$got" = "$want" ] || refuse \
            "the map on disk is the map the registration was fitted to" \
            "$reg (${key%%:*}) and $file" \
            "that file hashes to $got and the registration names $want." \
            "A REBUILT MAP HAS ITS OWN ROTATION FROM THE BUILDING. Every" \
            "absolute figure this arm produces is a map pose carried" \
            "through that registration, so a run against this grid would" \
            "be off by whatever the two builds differ by and nothing" \
            "downstream would notice." \
            "A rebuild is a NEW artifact under a new map.name with its" \
            "own registration (F3 constraint 16), never an overwrite:" \
            "  python3 $M5V3/tools/map_register.py derive --write" \
            "NOTHING WAS STARTED."
    done
    # AND THE POSE GRAPH, ON THE ARM THAT DESERIALISES IT. Two more
    # files, hashed against the manifest tools/build_map.sh wrote beside
    # them - see this function's header for why they are checked here and
    # not on both arms, and why the answer comes out of build.txt rather
    # than out of the registration.
    [ "$LOCALIZER" = "$CFG_LOCALIZATION_SLAM_LABEL" ] || return 0
    [ -f "$MAP_BUILD" ] || refuse "the build manifest is beside the map" \
        "$MAP_DIR and $CONFIG (map.build_file)" \
        "there is no file at $MAP_BUILD." \
        "It is what tools/build_map.sh wrote when it saved all four" \
        "artifacts out of one run, and it is the ONLY place the pose" \
        "graph's md5 is committed - the registration states the grid's" \
        "and says nothing at all about the graph." \
        "NOTHING WAS STARTED."
    for key in posegraph data; do
        file="$MAP_GRAPH.$key"
        [ -f "$file" ] || refuse "the frozen pose graph is complete" \
            "$MAP_DIR" \
            "$file is missing." \
            "$CFG_LOCALIZATION_SLAM_EXECUTABLE deserialises BOTH - the" \
            "graph and the scans behind it - and slam_toolbox's reader" \
            "appends the two suffixes to $MAP_GRAPH itself." \
            "NOTHING WAS STARTED."
        want="$(sed -n "s/^md5_$CFG_MAP_NAME[.]$key: *//p" "$MAP_BUILD" \
                | head -1)"
        [ -n "$want" ] || refuse \
            "the build manifest states md5_$CFG_MAP_NAME.$key" \
            "$MAP_BUILD" \
            "there is no such line in it, so it is not a manifest" \
            "tools/build_map.sh wrote - or it predates the four md5" \
            "lines that script has written since F3 Task 1." \
            "THE GRAPH CANNOT BE VERIFIED AND THIS ARM READS NOTHING" \
            "ELSE: nav2_amcl localises in the grid, and this one does" \
            "not open the grid at all." \
            "NOTHING WAS STARTED."
        got="$(md5sum "$file" | cut -d' ' -f1)"
        [ "$got" = "$want" ] || refuse \
            "the pose graph on disk is the one this map was built with" \
            "$MAP_BUILD (md5_$CFG_MAP_NAME.$key) and $file" \
            "that file hashes to $got and the manifest names $want." \
            "THE GRAPH AND THE GRID ARE TWO FILES OUT OF ONE BUILD, and" \
            "this arm localises in the GRAPH while every figure it" \
            "produces is carried into the building by a registration" \
            "fitted to the GRID. A graph that is not that build's would" \
            "be scored through somebody else's rotation, and nothing" \
            "downstream would notice." \
            "A rebuild is a NEW artifact under a new map.name with its" \
            "own build.txt and its own registration (F3 constraint 16)," \
            "never an overwrite." \
            "NOTHING WAS STARTED."
    done
}

# DID THE SCAN MATCHER FIND OUT WHERE IT IS BOLTED? A refusal, not a
# warning, and it is asked of the child's own log because that is the
# only place the answer exists.
#
# WHAT IT IS ASKING. rf2o looks up base_link <- the scan's frame ONCE,
# in the handler for its first scan. On a failure it logs the tf2
# exception and CARRIES ON with a default-constructed transform, so
# the scanner is taken to be at base_link and every pose it publishes
# afterwards is the LASER's. Nothing else on the stack changes: the
# process is alive, the topic is at rate, the relay is forwarding, the
# filter is fusing, `status` reads 9 alive - and the arm is quietly
# describing a scanner 0.55 m and 0.40 m from where it is. Measured on
# this rig 2026-08-26 before the arm was moved ahead of the bridges,
# EVIDENCE_FUSION.md 10.1.
#   THE INSTRUMENT IS THE ERROR LEVEL AND NOT THE MESSAGE TEXT.
#   rf2o_laser_odometry contains exactly ONE RCLCPP_ERROR in the whole
#   package (src/CLaserOdometry2DNode.cpp:125, at the pinned commit)
#   and it is inside that catch block - so an ERROR line in this
#   child's log IS that lookup having failed, whatever tf2's wording
#   for the particular failure was. Grepping the text would tie this
#   check to one of tf2's several exception strings.
#   THE TWIST WOULD SURVIVE IT AND THAT IS NOT A REASON TO LET IT PASS.
#   rf2o's lin_speed and ang_speed are both computed from the
#   scan-to-scan increment and are independent of the mount, so THIS
#   phase - which fuses twist only - would not measurably notice.
#   A stack that publishes a wrong thing nobody currently reads is a
#   trap set for whoever reads it next.
# AND THE COLLISION MONITOR'S, WHICH IS THE SAME GATE FOR A FAILURE THAT
# ARRIVES TEN SECONDS LATE. F4 Task 3, and it exists because the failure
# below was measured on this rig before the check was written.
#
# WHAT HAPPENS WITHOUT THE `lasertf` CHILD. nav2_collision_monitor
# transforms every scan point into base_link before it tests a polygon,
# and the nav lidar's scan is stamped `nav_lidar_link`. With no such
# frame the node logs
#     [ERROR] [getTransform]: Failed to get "nav_lidar_link"->"base_link"
# three times a second and PUBLISHES NOTHING AT ALL on its cmd_vel_out -
# which, on an arm where the converter reads that topic, is a CUT
# COMMAND PATH with every child ALIVE and every parameter correct.
#
# AND WHY THE STARTUP GATE CANNOT CATCH IT. Measured 2026-08-27: the
# node activated at t+0.02 s and the first transform error arrived at
# t+9.9 s, because until the first scan reaches it there is nothing to
# fail on and it relays every twist. tools/navcmd_health.py ran inside
# that window and passed - TRUTHFULLY, the path was a line when it was
# asked - and the same gate re-run three minutes later refused. A gate
# that runs once cannot see a failure that has not happened yet; the
# ERROR line is what it leaves behind, so that is what is read.
#
# SO IT IS A WATCH AND NOT A LOOK, WHICH IS THE ONE THING THIS GATE HAS
# THAT check_rf2o_transform() DOES NOT NEED. rf2o's lookup happens on its
# FIRST scan and its ERROR is therefore already on disk by the time
# anything asks; this node's arrives when the first scan reaches it,
# which was 9.9 s after activation on the run that measured it. So the
# check spends config.yaml monitor.transform_check_s watching the log
# rather than reading it once - the only bringup cost this arm carries,
# and it buys the difference between a refusal and a stack that comes up
# "healthy" with its command path cut.
check_monitor_transform() {
    local log="$LOGDIR/monitor.log" deadline
    deadline=$(( $(date +%s) + CFG_MONITOR_TRANSFORM_CHECK_S ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        grep -q "^\[ERROR\]" "$log" 2>/dev/null && break
        sleep 1
    done
    grep -q "^\[ERROR\]" "$log" 2>/dev/null || return 0
    refuse "the collision monitor can transform the scan it reads" \
        "$log and $0 (the lasertf child)" \
        "its log carries an ERROR. What it printed:" \
        "$(grep -m1 "^\[ERROR\]" "$log")" \
        "IT DID NOT STOP AND IT DID NOT STAY A RELAY. On a failed" \
        "transform this node publishes NOTHING on" \
        "$CFG_TOPICS_CMD_VEL_MONITORED - and on this arm that is the" \
        "topic nodes/cmd_vel_tricycle.py subscribes to, so the command" \
        "path is CUT four hops from anything that would say so: the" \
        "truck does not move, every child is ALIVE, and every parameter" \
        "reads back correctly." \
        "AND THIS IS NOT A SAFETY REFUSAL. nav2's own words for this" \
        "node are that it 'does not provide hard real-time safety" \
        "certifications'; what is broken here is a command path, not a" \
        "guard." \
        "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
        "'$0 stop', then start again."
}

check_rf2o_transform() {
    local log="$LOGDIR/rf2o.log"
    # The log is created by spawn's own redirection, so it exists by this
    # line whatever the child did; 2>/dev/null is for the one case where
    # it does not - a spawn that never ran at all - which the dead-child
    # check above has already refused with a better message.
    grep -q "^\[ERROR\]" "$log" 2>/dev/null || return 0
    refuse "rf2o found the transform for $CFG_FRAMES_NAV_LIDAR" \
        "$log and $0 (the lasertf child)" \
        "its log carries an ERROR, and this package logs one in exactly" \
        "one place: the base_link <- scan-frame lookup it makes once, on" \
        "its first scan. What it printed:" \
        "$(grep -m1 "^\[ERROR\]" "$log")" \
        "IT DID NOT STOP. rf2o carries on with a default-constructed" \
        "transform, so the scanner is taken to be AT base_link and every" \
        "pose it publishes is the LASER's. Nothing else looks wrong -" \
        "the child is alive, the topic is at rate, the filter is fusing." \
        "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
        "'$0 stop', then start again - the lookup is a race this script" \
        "wins by starting the arm before the bridge that carries the scan."
}

# THE TWO LIFECYCLE NODES, DRIVEN, IN THE ORDER THAT WORKS.
#
# WHY THIS SCRIPT DRIVES THEM. Both are nav2 lifecycle nodes: started,
# they sit UNCONFIGURED - amcl subscribes to no scan, advertises no
# amcl_pose and publishes no transform - and log nothing that looks
# wrong. `status` reads ALIVE. tools/build_map.sh drives slam_toolbox's
# two transitions the same way and for the same reason: one process, one
# log, one refusal that names it.
#
# WHY NOT A nav2 lifecycle_manager. Its bond is a heartbeat with a
# deadline, and a deadline starves at the real-time factors a simulation
# reaches - a manager that declares a healthy node dead is worse than no
# manager (sim/launch/warehouse_slam.launch.py measured it on the older
# rig, and agv/forklift/launch/localization.launch.py made the same call
# for these two nodes). amcl.yaml switches the bond off at both ends.
#
# THE WAIT IS ON THE NODE APPEARING AND NOT ON A SLEEP, and each
# transition is checked. A `ros2 lifecycle set` against a node that is
# not on the graph yet fails immediately with "Node not found", which
# under a sleep-and-hope would be a bringup that reported success over
# an unconfigured localiser.
localize_lifecycle() {
    local deadline node state
    # shellcheck disable=SC2086
    for node in $LOC_NODES; do
        deadline=$(( $(date +%s) + CFG_LOCALIZATION_LIFECYCLE_TIMEOUT_S ))
        until ros2 node list 2>/dev/null | grep -q "^/$node$"; do
            [ "$(date +%s)" -lt "$deadline" ] || refuse \
                "/$node appeared inside ${CFG_LOCALIZATION_LIFECYCLE_TIMEOUT_S}s" \
                "$LOGDIR/$node.log (config.yaml localization.lifecycle_timeout_s)" \
                "nothing by that name is on domain $ROS_DOMAIN_ID." \
                "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
            sleep 1
        done
    done
    # map_server ALL THE WAY UP FIRST, then amcl. amcl's on_activate
    # waits for a map on the latched topic and an INACTIVE map_server
    # never publishes one, so the wrong order leaves amcl blocked in a
    # transition with no error at all. $LOC_NODES carries that order and
    # configure() is where it is written down; on the slam arm the list
    # is one node and the ordering question does not arise.
    # shellcheck disable=SC2086
    for node in $LOC_NODES; do
        deadline=$(( $(date +%s) + CFG_LOCALIZATION_LIFECYCLE_TIMEOUT_S ))
        state=""
        # THE TARGET IS A STATE AND NOT A SEQUENCE OF COMMANDS, AND THE
        # DIFFERENCE COST A BRINGUP. This loop used to fire `configure`
        # and then `activate` and refuse on either one's EXIT CODE, which
        # assumes the node is UNCONFIGURED when the script arrives.
        # Measured on this rig 2026-08-27, on the third localisation
        # bringup of the session:
        #     [WARN] [rcl_lifecycle]: No transition matching configure
        #                             found for current state active
        #     Transitioning failed
        # - a refusal, a stack left half up, and a localiser that was
        # already exactly where the script was trying to put it. What put
        # it there was not established and DOES NOT NEED TO BE, which is
        # the whole argument for the shape below: a request to CONFIGURE
        # is a claim about the current state, and a request to be ACTIVE
        # is not.
        #   SO IT DRIVES WHAT IT FINDS. UNCONFIGURED gets a configure,
        #   INACTIVE gets an activate, ACTIVE is done, and a transition
        #   in progress is waited out. It is idempotent, it cannot race
        #   whatever else may have moved the node, and it still refuses a
        #   node that never arrives - by its LAST STATE, which is the
        #   thing an operator needs and an exit code never carried.
        #   (`ros2 run slam_toolbox localization_slam_toolbox_node` on
        #   its own does NOT self-transition: measured bare on domain 99,
        #   24 s, `unconfigured [1]` throughout. So the node is not the
        #   explanation, and the loop is written not to need one.)
        until [ "$state" = active ]; do
            state="$(ros2 lifecycle get "/$node" 2>/dev/null \
                     | cut -d' ' -f1)"
            case "$state" in
                unconfigured) ros2 lifecycle set "/$node" configure \
                                  >> "$LOGDIR/$node.log" 2>&1 || true ;;
                inactive)     ros2 lifecycle set "/$node" activate \
                                  >> "$LOGDIR/$node.log" 2>&1 || true ;;
                active)       break ;;
                *)            ;;
            esac
            [ "$(date +%s)" -lt "$deadline" ] || refuse \
                "$node reached ACTIVE inside ${CFG_LOCALIZATION_LIFECYCLE_TIMEOUT_S}s" \
                "$LOGDIR/$node.log (config.yaml localization.lifecycle_timeout_s)" \
                "it is in state '${state:-unreadable}' and this script" \
                "has been driving it towards active for the whole" \
                "budget." \
                "EVERY LOCALISATION NODE HERE IS A LIFECYCLE NODE. Left" \
                "short of ACTIVE one subscribes to no scan, advertises" \
                "no pose and publishes no transform, while logging" \
                "nothing that looks wrong - and 'status' reads ALIVE." \
                "On the $CFG_LOCALIZATION_SLAM_LABEL arm CONFIGURE is" \
                "also where the pose graph is READ, so a node that never" \
                "configured has not merely not started: it has not" \
                "opened the map." \
                "A node stuck in 'configuring' or 'activating' is a" \
                "transition that BLOCKED - amcl's on_activate waits for" \
                "a map on the latched topic, and an INACTIVE map_server" \
                "never publishes one." \
                "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
            sleep 1
        done
        echo "  $node active"
    done
}

# THE SMOOTHER REACHES ACTIVE ON ITS OWN, AND THIS ONLY ASKS WHETHER IT
# DID. F4 Task 1, and it is deliberately NOT localize_lifecycle() a
# second time: that function DRIVES transitions because nav2_amcl,
# nav2_map_server and slam_toolbox's localiser all sit in UNCONFIGURED
# for ever unless something moves them. nav2_velocity_smoother takes
# `autostart_node`, and smoother.yaml sets it - MEASURED on this rig
# 2026-08-27, the node logs "Auto-starting node", "Configuring",
# "Activating" and `ros2 lifecycle get` reads `active [3]` with nothing
# external touching it.
#   SO THE MECHANISM IS A POLL AND NOT A DRIVE, which is a different
#   thing rather than a copy of one. What it still has to catch is the
#   failure every lifecycle node on this stack shares: left short of
#   ACTIVE it subscribes to nothing, publishes nothing and logs nothing
#   that reads as an error, and `status` says ALIVE. On this node that
#   would be a command path with no smoother in it - every twist a step,
#   and no dead-man at all.
#   AND IT TAKES ITS NODE, BECAUSE F4 TASK 3 ASKS THE SAME QUESTION OF A
#   SECOND ONE. nav2_collision_monitor is a nav2_util::LifecycleNode too
#   and collision_monitor.yaml sets the same `autostart_node`; what
#   differs between the two callers is only WHAT IS MISSING from the
#   command path when the answer is no, so that is what is passed in and
#   everything else is one copy. Two copies of a mechanism drift exactly
#   the way two copies of a value do (tools/_common.sh's own rule).
autostart_active() {
    local node="$1" budget="$2" log="$3" params="$4" key="$5"
    shift 5
    local deadline state=""
    deadline=$(( $(date +%s) + budget ))
    until [ "$state" = active ]; do
        state="$(ros2 lifecycle get "/$node" 2>/dev/null \
                 | cut -d' ' -f1)"
        [ "$state" = active ] && break
        [ "$(date +%s)" -lt "$deadline" ] || refuse \
            "$node reached ACTIVE on its own inside ${budget}s" \
            "$log (config.yaml $key)" \
            "it is in state '${state:-unreadable}' and NOTHING IS DRIVING" \
            "IT - $params sets autostart_node and this" \
            "script only watches. A state of 'unconfigured' therefore" \
            "means that parameter did not reach the node, which is what" \
            "a --params-file addressed to the wrong node name looks" \
            "like from the outside." \
            "$@" \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
        sleep 1
    done
    echo "  $node active"
}

smoother_active() {
    autostart_active "$CFG_SMOOTHER_NODE_NAME" \
        "$CFG_SMOOTHER_ACTIVE_TIMEOUT_S" "$LOGDIR/smoother.log" \
        "$CFG_SMOOTHER_PARAMS_FILE" "smoother.active_timeout_s" \
        "LEFT SHORT OF ACTIVE IT SUBSCRIBES TO NOTHING AND PUBLISHES" \
        "NOTHING, while logging nothing that reads as an error - so" \
        "the command path would have no smoother in it at all: every" \
        "twist a step at a terminal with no ramp, and no dead-man."
}

# AND THE COLLISION MONITOR'S OWN, F4 Task 3. Same mechanism, and the
# consequence of a `no` is the one that matters most here: this node is
# IN the command path on this arm - the converter is remapped to its
# output - so a monitor that never reached ACTIVE is not a guard that is
# missing, it is a COMMAND PATH THAT IS CUT. The converter would sit
# subscribed to a topic nobody publishes and the truck would not move at
# all, which is a failure that looks like a planner problem from every
# angle except this one.
monitor_active() {
    autostart_active "$CFG_MONITOR_NODE_NAME" \
        "$CFG_MONITOR_ACTIVE_TIMEOUT_S" "$LOGDIR/monitor.log" \
        "$CFG_MONITOR_PARAMS_FILE" "monitor.active_timeout_s" \
        "AND ON THIS ARM IT IS IN THE COMMAND PATH RATHER THAN BESIDE" \
        "IT. --monitor remaps the converter's input to this node's" \
        "output, so a monitor short of ACTIVE publishes nothing at all" \
        "and the converter waits for ever on a topic with no publisher:" \
        "the truck does not move, and nothing in any log says why." \
        "IT IS NOT A SAFETY FUNCTION AND THIS IS NOT A SAFETY REFUSAL." \
        "nav2's own words for this node are that it 'does not provide" \
        "hard real-time safety certifications'."
}

# EVERY CHILD IN THE PIDFILE, STILL RUNNING - OR A REFUSAL NAMING THE
# ONES THAT ARE NOT.
#
# A DEAD CHILD IS A REFUSAL AND NOT A WARNING. This used to print "THE
# STACK IS INCOMPLETE" and then fall through to "up." and exit 0, so an
# operator's `start && ...` - and any script reading the exit status -
# saw a successful bringup over a stack that was missing a process.
# Whatever survived is STILL RUNNING and the message says so, because
# the operator's next command is stop and not start.
#
# IT IS A FUNCTION BECAUSE F4 TASK 2 ASKS IT TWICE. The nav arm's five
# children go up AFTER the localiser has been driven to ACTIVE - which
# is after the first call - because a global costmap in the `map` frame
# blocks its own activation until map -> base_link resolves. A second
# copy of this block would be the copy that stops being edited.
assert_children_alive() {
    local pid name dead="" logs="" n
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        ours "$pid" || dead="$dead${dead:+ }$name"
    done < "$PIDFILE"
    [ -n "$dead" ] || return 0
    for n in $dead; do logs="$logs${logs:+, }$LOGDIR/$n.log"; done
    refuse "every child is alive ${CFG_TIMING_STARTUP_CHECK_S}s after the last spawn" \
        "$logs" \
        "these children exited during startup: $dead" \
        "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
        "read the log named above, then '$0 stop' before trying again."
}

start() {
    local pid name
    # A LIVE STACK IS NOT STARTED OVER. ours() is the liveness test rather
    # than kill -0, which cannot tell a zombie from a running child and
    # cannot tell a recycled pid from ours.
    if [ -f "$PIDFILE" ]; then
        while read -r pid name; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            if ours "$pid"; then
                echo "already running ($name, pid $pid, see $PIDFILE)."
                echo "run '$0 stop' first."
                return 1
            fi
        done < "$PIDFILE"
        # None of them is ours any more: a crashed run left the file
        # behind. The return above is what keeps start off a LIVE stack.
        rm -f "$PIDFILE"
    fi
    [ -f "$WORLD" ] || refuse "the world file exists" "$CONFIG" \
        "world.file resolves to $WORLD" \
        "it belongs to m6 and is used BY REFERENCE - do not copy it here"
    [ -f "$MODEL" ] || refuse "the vehicle model exists" "$CONFIG" \
        "vehicle.model resolves to $MODEL"
    # THE FILTER'S PARAMETER FILE IS CHECKED HERE AND NOT BY ekf_node.
    # A --params-file that does not exist is a hard error from rclcpp,
    # which is the good case; the case this check is for is the file
    # being MOVED, because then ekf_node starts on its own defaults - a
    # filter that fuses nothing, publishes a transform that never moves,
    # and says nothing about either. Refusing before anything is started
    # is cheaper than reading that.
    [ -f "$EKF_PARAMS" ] || refuse "the EKF parameter file exists" \
        "$CONFIG" "ekf.params_file resolves to $EKF_PARAMS" \
        "without it ekf_node would start on its own defaults, fuse" \
        "nothing at all, and report nothing about it."
    # AND THE FILE HAS TO BE ADDRESSED TO THE NODE THIS SCRIPT STARTS -
    # see check_ekf_params() above, which is where that argument lives
    # now that TWO files have to pass it.
    check_ekf_params "$EKF_PARAMS" "ekf.params_file"
    # AND THE SMOOTHER'S, ON THE SAME TERMS AND UNCONDITIONALLY - the
    # command path is not an arm. F4 constraint 18: there is one command
    # line from the controller to the terminals and no bypass, so the
    # two children that make it up go up with the stack and are checked
    # with it. See check_smoother_params() for what a file addressed to
    # the wrong node costs here.
    [ -f "$SMOOTHER_PARAMS" ] || refuse \
        "the velocity smoother's parameter file exists" \
        "$CONFIG (smoother.params_file)" \
        "it resolves to $SMOOTHER_PARAMS" \
        "a --params-file that does not exist IS a hard error from" \
        "rclcpp, which is the good case; the case this check is for is" \
        "the file being MOVED, because then the smoother comes up on" \
        "its PACKAGE DEFAULTS and limits vx and wz INDEPENDENTLY -" \
        "which on a nonholonomic vehicle changes the commanded arc" \
        "without changing anything an instrument can see."
    check_smoother_params "$SMOOTHER_PARAMS"
    # AND THE MONITOR'S, ONLY WHEN THE FLAG WAS GIVEN. It is the
    # optional arms' rule and not the command path's: the default stack
    # never opens this file and never starts this node, so an
    # unconditional check would refuse a bringup that does not need it.
    if [ "$MONITOR" = true ]; then
        [ -f "$MONITOR_PARAMS" ] || refuse             "the collision monitor's parameter file exists"             "$CONFIG (monitor.params_file)"             "it resolves to $MONITOR_PARAMS"             "NOTHING WAS STARTED. Drop --monitor to bring up the"             "command path EVIDENCE_NAV_V3.md 3-10 measured, which is"             "this one with nothing inserted in it."
        check_monitor_params "$MONITOR_PARAMS"
    fi
    # THE OPTIONAL ARM'S OWN THREE CHECKS, AND THEY ARE ONLY MADE WHEN
    # THE FLAG WAS GIVEN. Every one of them is about a file or a binary
    # that the default stack neither reads nor starts, so making them
    # unconditionally would let a rig that has never run
    # tools/install_rf2o.sh refuse a bringup that does not need it.
    if [ "$RF2O" = true ]; then
        [ -x "$RF2O_BIN" ] || refuse \
            "rf2o_laser_odometry is built" \
            "$CONFIG (rf2o.workspace) and $M5V3/tools/install_rf2o.sh" \
            "there is no executable at $RF2O_BIN" \
            "it is built FROM SOURCE, in your own home, without sudo -" \
            "the package is not in the Jazzy archive for any distro:" \
            "  bash $M5V3/tools/install_rf2o.sh" \
            "NOTHING WAS STARTED. Drop --rf2o to bring up the stack" \
            "EVIDENCE_FUSION.md 9.3 was measured on."
        [ -f "$EKF_RF2O_PARAMS" ] || refuse \
            "the optional arm's EKF overlay exists" \
            "$CONFIG (ekf.rf2o_params_file)" \
            "it resolves to $EKF_RF2O_PARAMS" \
            "without it ekf_node would start with odom1 named on its" \
            "command line and NO odom1_config to say what to fuse from" \
            "it - which robot_localization reads as 'fuse nothing from" \
            "that sensor' and reports as nothing at all."
        check_ekf_params "$EKF_RF2O_PARAMS" "ekf.rf2o_params_file"
    fi
    # AND THE FACTOR-GRAPH ARM'S TWO, ON THE SAME TERMS. Only when the
    # flag was given, for the block above's reason: a rig that has never
    # run tools/install_fuse.sh must still be able to bring up the stack
    # EVIDENCE_FUSION.md 9.3 was measured on.
    if [ "$FUSE" = true ]; then
        [ -x "$FUSE_BIN" ] || refuse \
            "the fuse packages are vendored" \
            "$CONFIG (fuse.prefix, fuse.packages) and" \
            "$M5V3/tools/install_fuse.sh" \
            "there is no executable at $FUSE_BIN" \
            "the packages ARE in the Jazzy archive - what this rig has no" \
            "permission to do is install one (F2 constraint 14), so they" \
            "are fetched and unpacked into your own home instead:" \
            "  bash $M5V3/tools/install_fuse.sh" \
            "NOTHING WAS STARTED. Drop --fuse to bring up the stack" \
            "EVIDENCE_FUSION.md 9.3 was measured on."
        [ -f "$FUSE_PARAMS" ] || refuse \
            "the factor graph's parameter file exists" \
            "$CONFIG (fuse.params_file)" \
            "it resolves to $FUSE_PARAMS" \
            "a --params-file that does not exist IS a hard error from" \
            "rclcpp, which is the good case; the case this check is for" \
            "is the file being MOVED, because then the node comes up" \
            "with NO sensor models, NO publisher and NO topic advertised" \
            "and reports ALIVE the whole time - measured," \
            "EVIDENCE_FUSION.md 11.2(a). Refusing before anything is" \
            "started is cheaper than reading that."
        check_fuse_params "$FUSE_PARAMS"
    fi
    # AND THE LOCALISATION ARM'S THREE, ON THE SAME TERMS AND FOR THE
    # SAME REASON: a rig with no frozen map must still be able to bring
    # up the stack EVIDENCE_FUSION.md 9.3 was measured on.
    if [ "$LOCALIZE" = true ]; then
        [ -f "$LOC_PARAMS" ] || refuse \
            "the localiser's parameter file exists" \
            "$CONFIG (localization.$LOCALIZER.params_file)" \
            "it resolves to $LOC_PARAMS" \
            "a --params-file that does not exist IS a hard error from" \
            "rclcpp, which is the good case; the case this check is for" \
            "is the file being MOVED, because then the localiser comes" \
            "up on its own PACKAGE DEFAULTS - nav2_amcl with alphas of" \
            "0.2, 60 beams and sigma_hit 0.2, or slam_toolbox in MAPPING" \
            "mode with an empty graph - and either of them publishes" \
            "$CFG_FRAMES_MAP -> $CFG_FRAMES_ODOM looking exactly like a" \
            "localiser." \
            "NOTHING WAS STARTED."
        # shellcheck disable=SC2086
        check_loc_params "$LOC_PARAMS" $LOC_NODES
        # AND THE MODE, ON THE ONE ARM THAT HAS A MODE. The guard is HERE
        # and not inside the function, which is the opposite of
        # check_frozen_map()'s early return and is the difference between
        # the two: that one does work for BOTH arms and then adds the
        # graph's hashes, so its guard can only be mid-function. This one
        # is arm-specific from its first line to its last, and a function
        # whose NAME says slam should not be reachable on the other arm
        # at all - the reader of this block sees which checks each arm
        # gets, in the block where the arms are chosen.
        #   nav2_amcl HAS NO MODE CONCEPT and amcl.yaml carries no
        #   `mode:` line, so the check is not merely redundant there: it
        #   REFUSES. Called unconditionally it refused every
        #   `--localize $CFG_LOCALIZATION_AMCL_LABEL` bringup - the
        #   shipping default - with "no mode: line at all", and nothing
        #   started. What is guarded is slam_toolbox's own enum, whose
        #   default is MAPPING.
        if [ "$LOCALIZER" = "$CFG_LOCALIZATION_SLAM_LABEL" ]; then
            check_slam_mode
        fi
        # THE FREEZE, ENFORCED BEFORE ANYTHING IS STARTED. See
        # check_frozen_map(): this is the only place that can still say
        # nothing has begun.
        check_frozen_map
    fi
    # AND THE NAV ARM'S THREE, ON THE SAME TERMS AND FOR THE SAME REASON
    # AS EVERY OPTIONAL ARM ABOVE: a rig that never intends to run a
    # planner must still be able to bring up the stack every earlier
    # phase's figures were measured on.
    if [ "$NAV" = true ]; then
        # THE DEPENDENCY FIRST, BECAUSE IT IS THE ONE AN OPERATOR IS
        # MOST LIKELY TO HIT AND THE ONE THAT NEEDS NO FILE ON DISK.
        [ "$LOCALIZE" = true ] || refuse \
            "--nav was given with a localiser" \
            "$0 (the start flags)" \
            "--nav puts a planner and a controller over a stack that" \
            "does not know where it is. THIS IS NOT A PREFERENCE." \
            "The global costmap's frame is $CFG_FRAMES_MAP, and" \
            "Costmap2DROS::on_activate BLOCKS until it can transform" \
            "$CFG_FRAMES_MAP -> $CFG_FRAMES_BASE_LINK. Without a" \
            "localiser NOTHING publishes $CFG_FRAMES_MAP ->" \
            "$CFG_FRAMES_ODOM at all, so that transition never returns:" \
            "five children ALIVE for ever, one of them wedged in a" \
            "lifecycle transition, and no log line that reads as an" \
            "error." \
            "NOTHING WAS STARTED. Add a localiser:" \
            "  $0 start --headless --localize --nav" \
            "  $0 start --headless --localize $CFG_LOCALIZATION_SLAM_LABEL --nav"
        [ -f "$NAV_PARAMS" ] || refuse \
            "the nav parameter file exists" "$CONFIG (nav.params_file)" \
            "it resolves to $NAV_PARAMS" \
            "a --params-file that does not exist IS a hard error from" \
            "rclcpp, which is the good case; the case this check is for" \
            "is the file being MOVED, because then all four servers" \
            "come up on nav2's own PACKAGE DEFAULTS - a DiffDrive MPPI" \
            "on a tricycle, a DUBIN planner at a 0.4 m radius, and two" \
            "3 x 3 m costmaps carrying a CIRCULAR footprint of radius" \
            "0.10 m." \
            "NOTHING WAS STARTED."
        [ -f "$NAV_BT" ] || refuse \
            "the behaviour tree exists" "$CONFIG (nav.bt_xml)" \
            "it resolves to $NAV_BT" \
            "without it bt_navigator falls back to nav2's OWN tree," \
            "which ends its recovery round robin with Spin and BackUp." \
            "This vehicle cannot rotate in place -" \
            "nodes/cmd_vel_tricycle_core.py REFUSES a yaw rate at a" \
            "standstill by name - so a Spin recovery would stand still" \
            "for the whole behaviour and then report SUCCESS." \
            "NOTHING WAS STARTED."
        # shellcheck disable=SC2086
        check_nav_params "$NAV_PARAMS" $NAV_SECTIONS
    fi
    # F5 TASK 1's THREE, AND ONLY WHEN --dock WAS GIVEN. A rig that
    # never intends to detect a marker must still bring up the stack
    # every earlier phase's figures were measured on.
    if [ "$DOCK" = true ]; then
        [ "$NAV" = true ] || refuse \
            "--dock was given with --nav" \
            "$0 (the start flags)" \
            "--dock places the S5 marker and starts apriltag_node." \
            "Detection accuracy is a STAGING-RANGE figure, and staging" \
            "is a Nav2 goal. The camera at spawn cannot see the board." \
            "NOTHING WAS STARTED. Add the planner:" \
            "  $0 start --headless --localize --nav --dock"
        [ -x "$APRILTAG_BIN" ] || refuse \
            "apriltag_ros is vendored" \
            "$CONFIG (apriltag.prefix) and $M5V3/tools/install_apriltag.sh" \
            "there is no executable at $APRILTAG_BIN" \
            "  bash $M5V3/tools/install_apriltag.sh" \
            "NOTHING WAS STARTED. Drop --dock to bring up the stack" \
            "EVIDENCE_NAV_V3.md was measured on."
        [ -f "$APRILTAG_PARAMS" ] || refuse \
            "the apriltag parameter file exists" \
            "$CONFIG (apriltag.params_file)" \
            "it resolves to $APRILTAG_PARAMS" \
            "NOTHING WAS STARTED."
        [ -f "$TAG_SDF" ] || refuse \
            "the marker SDF is on disk" \
            "$CONFIG (dock.model_dir) -> $TAG_SDF" \
            "python3 $M5V3/tools/tag_model.py write" \
            "NOTHING WAS STARTED. Constraint 21: the marker is spawned," \
            "never written into warehouse_ver3.sdf."
        check_apriltag_params "$APRILTAG_PARAMS"
        [ -f "$DOCKING_PARAMS" ] || refuse \
            "the docking parameter file exists" \
            "$CONFIG (docking.params_file)" \
            "it resolves to $DOCKING_PARAMS" \
            "NOTHING WAS STARTED."
        [ -f "$DOCK_DB" ] || refuse \
            "the dock database exists" \
            "$CONFIG (docking.database_file)" \
            "it resolves to $DOCK_DB" \
            "NOTHING WAS STARTED."
        [ -x "$DOCKING_BIN" ] || refuse \
            "opennav_docking is installed" \
            "$CONFIG (docking.package, docking.executable) and $DOCKING_BIN" \
            "ros-jazzy-opennav-docking 1.3.12 is the package Task 2 verified." \
            "NOTHING WAS STARTED."
        check_docking_params "$DOCKING_PARAMS"
    fi
    # Unchecked, an unwritable log dir fails every redirection this stack
    # opens and start would sleep its way to "up." over a stack that never
    # began. Since F4's closing wave this also PICKS the directory: one
    # per bringup, so a log can still be quoted after the next start.
    open_run_log_dir

    gpu_preflight

    : > "$PIDFILE" || refuse "the pid file is writable" "$CONFIG" \
        "paths.pidfile resolves to $PIDFILE"
    # ROS IS SOURCED AFTER THE GPU PREFLIGHT AND NOT BEFORE IT, so the
    # renderer glxinfo reports is the one this shell had when the two
    # exports went on: sourcing ROS rewrites LD_LIBRARY_PATH, and a gate
    # measured through a different loader path is a different gate. The
    # refusal for a missing ROS therefore lands here rather than at the
    # top of start(). Nothing has been STARTED by this line either way,
    # which is the property that matters.
    source_ros

    echo "starting the m5-ver3 plant (partition $GZ_PARTITION, domain $ROS_DOMAIN_ID, gui $GUI)"
    # THE WORLD FIRST, and its load budget is the plant's.
    #   -s IS SERVER-ONLY and the GUI is a second process; -r starts the
    #   simulation running. --headless-rendering is ABSENT rather than
    #   false when the window is wanted, because -s alone still opens a
    #   GLX connection when DISPLAY is set (sim/setup/WSL_ENVIRONMENT.md
    #   4.7) - it is the honest flag for a run that claims to be headless.
    if [ "$GUI" = true ]; then
        spawn world gz sim -s -r -v 2 "$WORLD"
    else
        spawn world gz sim -s -r --headless-rendering -v 2 "$WORLD"
    fi
    sleep "$CFG_TIMING_WORLD_LOAD_S"

    # THE TRUCK IS SPAWNED BY THIS SCRIPT AND NOT BY THE WORLD FILE.
    # warehouse_ver3.sdf carries no vehicle include - that is what lets m6
    # put four trucks on this floor and this track put one - so the create
    # service is where a vehicle enters it. Not a child: the service call
    # returns and the truck belongs to the server.
    spawn_truck
    sleep "$CFG_TIMING_SETTLE_S"

    # CONSTRAINT 21: the marker is a create-service call, never a world
    # edit. furniture.py place is spawn_truck's idiom applied to the
    # tag SDF tag_model.py write already put on disk.
    if [ "$DOCK" = true ]; then
        python3 "$M5V3/tools/furniture.py" place \
            || refuse "station furniture was spawned" \
                "$M5V3/tools/furniture.py place" \
                "the create service did not accept the marker." \
                "THE WORLD IS STILL UP. '$0 stop' before trying again."
    fi

    # THE FLOOR, AFTER THE TRUCK IS STANDING ON IT. --slippery is the
    # only thing on this stack that changes the PLANT, and it changes it
    # here: after the settle, so the wheels are loaded and the model
    # entity certainly exists, and before any bridge is opened, so no
    # consumer can ever see a message from the un-overridden plant.
    # Whichever way it went, the answer is written down before anything
    # that MEASURES this stack is started.
    if [ "$SLIPPERY" = true ]; then
        apply_slippery
    fi
    write_traction

    # ------------------ THE OPTIONAL LASER-ODOMETRY ARM ------------------
    # THREE CHILDREN, AND NOT ONE OF THEM EXISTS WITHOUT --rf2o. The
    # whole block is skipped by the default stack, which is the claim
    # EVIDENCE_FUSION.md 10.3 has to be able to make: `start` without
    # the flag spawns the same six processes, hands the filter the same
    # one parameter file, and publishes nothing on either rf2o topic.
    #
    # AND IT GOES HERE, BEFORE THE BRIDGES, WHICH IS A MEASURED
    # ORDERING AND NOT A TIDY ONE. rf2o looks up base_link <- the
    # scan's own frame EXACTLY ONCE, in the handler for its FIRST
    # scan, and on a failed lookup it logs the exception and then uses
    # the default-constructed transform anyway - so the scanner is
    # silently taken to be AT base_link and every pose it publishes
    # for the rest of the run is the LASER's rather than the
    # vehicle's. There is no retry.
    #   MEASURED ON THIS RIG 2026-08-26 with this block sitting after
    #   the bridges: rf2o came up at a moment when scans were already
    #   flowing, its first scan arrived 106 ms later, and the latched
    #   /tf_static message had not reached its listener yet -
    #   `"base_link" passed to lookupTransform argument target_frame
    #   does not exist`, once, and thereafter `Laser odom` and
    #   `Robot-base odom` printed IDENTICAL numbers for the whole
    #   session, which is what an identity mount looks like.
    #   EVIDENCE_FUSION.md 10.1.
    #   STARTED HERE THERE IS NO SCAN YET. The parameter bridge that
    #   carries the nav lidar is not up, so rf2o sits in `Waiting for
    #   laser_scans` through the bridge, the image bridge, the wheel
    #   odometry and the IMU transform - ten seconds of real work, not
    #   a sleep - and the static transform is long since in its buffer
    #   when the first scan finally arrives. A jump in /clock does not
    #   undo it: tf2 stores static transforms in a cache whose
    #   clearList() is a no-op, which is why they answer for any query
    #   time in the first place.
    #   AND IT IS CHECKED ANYWAY, AFTER THE STARTUP GATE. An ordering
    #   with a large margin is still an ordering with a margin;
    #   check_rf2o_transform() below reads the child's own log for the
    #   one ERROR this package can emit and refuses the bringup.
    # WHERE THE SCANNER IS BOLTED, ON /tf_static, AND IT IS THE IMU
    # TRANSFORM'S ARGUMENT A SECOND TIME. This edge is where a SENSOR
    # is, which a robot_state_publisher would own if this track carried a
    # URDF; where the VEHICLE is is a different claim and a different
    # process. No use_sim_time on it, for imutf's reason: tf2 answers a
    # static transform for any query time, so the stamp is never
    # consulted and a clock this process does not have cannot go wrong.
    #   THREE ARMS NEED IT AND THERE IS ONE OF IT. --rf2o needs it because
    #   its scan matcher looks the mount up once and carries on with a
    #   garbage transform if the lookup fails; --localize needs it
    #   because AMCL's scan is stamped `nav_lidar_link` and its tf2
    #   MessageFilter will not release a single message until the chain
    #   odom -> base_link -> nav_lidar_link closes. MEASURED, 2026-08-26,
    #   with this child absent: amcl logs "Message Filter dropping
    #   message: frame 'nav_lidar_link' ... queue is full" every few
    #   seconds, processes NO scan, publishes NO pose and broadcasts NO
    #   transform - and `status` reads every child ALIVE.
    #   AND SINCE F4 TASK 3 --monitor NEEDS IT TOO, WHICH COST A WHOLE
    #   DEMONSTRATION RUN TO LEARN. nav2_collision_monitor transforms
    #   every scan point into `base_frame_id` before it tests a polygon,
    #   and the scan is stamped `nav_lidar_link`. With this child absent
    #   the node logs, three times a second and for ever:
    #       [ERROR] [getTransform]: Failed to get "nav_lidar_link"->
    #       "base_link" frame transform: "nav_lidar_link" passed to
    #       lookupTransform argument source_frame does not exist.
    #   - and then publishes NOTHING AT ALL on its cmd_vel_out. On this
    #   arm that node is IN the command path, so the converter waits for
    #   ever on a topic with no publisher and the truck does not move.
    #   MEASURED 2026-08-27, `--monitor` alone: 703 twists into the
    #   monitor, 0 out, 0 at either terminal, 0 state messages, and
    #   every child ALIVE. The gate that would have caught it does not
    #   exist - `monitor_active` asks about the LIFECYCLE state and this
    #   node reaches ACTIVE perfectly well without a transform.
    #   IT IS SPAWNED HERE, BEFORE THE BRIDGES, WHICH IS A MEASURED
    #   ORDERING AND NOT A TIDY ONE - see the rf2o block below for the
    #   session that measured it.
    if [ "$RF2O" = true ] || [ "$LOCALIZE" = true ] \
       || [ "$MONITOR" = true ]; then
        spawn lasertf ros2 run tf2_ros static_transform_publisher \
            --x "$CFG_VEHICLE_NAV_LIDAR_MOUNT_X" \
            --y "$CFG_VEHICLE_NAV_LIDAR_MOUNT_Y" \
            --z "$CFG_VEHICLE_NAV_LIDAR_MOUNT_Z" \
            --frame-id "$CFG_FRAMES_BASE_LINK" \
            --child-frame-id "$CFG_FRAMES_NAV_LIDAR"
    fi

    if [ "$RF2O" = true ]; then
        # THE SCAN MATCHER. Built from source into the user's own home
        # by tools/install_rf2o.sh and executed by ABSOLUTE PATH rather
        # than through `ros2 run`: the package installs exactly one
        # executable, it links no library of its own (the one CMake
        # builds beside it is neither installed nor linked), and every
        # shared object it needs is already on the loader path from
        # source_ros() above. So there is no second workspace to source
        # and no wrapper shell between this script and the child.
        #   FOUR OF ITS SEVEN PARAMETERS ARE NOT DEFAULTS, AND EACH IS
        #   A REFUSAL OF SOMETHING THIS TRACK WILL NOT HAVE:
        #     publish_tf false - it defaults TRUE and would broadcast
        #       odom -> base_link. That edge has exactly one owner on
        #       this stack (ekf_node), and a second publisher of it is
        #       the failure the whole two-phase odometry plan exists to
        #       prevent (ver2 invariant 10).
        #     init_pose_from_topic empty - it defaults to
        #       /base_pose_ground_truth. Left alone, an ESTIMATOR on
        #       this stack would subscribe to a ground-truth pose, and
        #       that is F2 global constraint 13 broken by a default. It
        #       is spelled as YAML's empty string because rcl cannot
        #       parse a bare `-p key:=` at all - measured, it aborts.
        #     odom_frame_id - frames.rf2o_odom and NOT frames.odom, so
        #       a second opinion about the vehicle's pose cannot wear
        #       the name of the edge the filter owns, even in a header.
        #     freq - config.yaml rf2o.freq_hz, twice the nav lidar's
        #       rate, because this node's main loop consumes at most
        #       one buffered scan per pass. The argument is there.
        spawn rf2o "$RF2O_BIN" --ros-args \
            -p use_sim_time:=true \
            -p laser_scan_topic:="$CFG_TOPICS_SCAN_NAV" \
            -p odom_topic:="$CFG_TOPICS_RF2O_ODOM_RAW" \
            -p base_frame_id:="$CFG_FRAMES_BASE_LINK" \
            -p odom_frame_id:="$CFG_FRAMES_RF2O_ODOM" \
            -p publish_tf:=false \
            -p 'init_pose_from_topic:=""' \
            -p freq:="$CFG_RF2O_FREQ_HZ"

        # AND THE ONE THING BETWEEN IT AND THE FILTER. rf2o publishes a
        # twist covariance of 36 zeros - never assigned, and no
        # parameter to set it - and a `linear.x` that is the SCANNER's
        # forward speed stamped with base_link's name.
        # robot_localization does not ignore a zero variance on a
        # channel it is fusing; it substitutes a very small one. So
        # without this child the arm would arrive trusted orders of
        # magnitude above the wheel odometry it exists to be checked
        # against, carrying 0.107 m/s of lever-arm error through every
        # corner. nodes/rf2o_twist.py's header is the whole argument
        # and nodes/rf2o_twist_core.py is where the arithmetic is
        # tested. python3 and not `ros2 run`, for wheel_odometry.py's
        # reason: this track is deliberately not a colcon package.
        spawn rf2ocov python3 "$M5V3/nodes/rf2o_twist.py"
    fi

    # THE BRIDGES AFTER THE TRUCK, because all but one of their topics are
    # the truck's and a bridge opened over topics that do not exist yet
    # spends its first seconds advertising nothing.
    #   WHAT IS CARRIED AND WHAT IS NOT. The clock, the ground-truth
    #   odometry (a measurement reference, never an input), the nav lidar,
    #   the IMU, the pallet camera's depth image plus its camera_info, and
    #   the drive shaft's reading channel A plus the joint state.
    #   NOT the 3D lidar and NOT either point cloud: their ROS consumers
    #   arrive in F2, and gz renders a sensor only while something
    #   subscribes to it, so bridging early would cost the RTF every
    #   figure on this track is measured against and buy nothing
    #   (docs/reports/m5v3-03 5, ros_gz issue #368).
    #   THE TWO JOINT CHANNELS ARE F1 TASK 3's ADDITION, and they are
    #   the only ones on this bridge that carry the world's own rate:
    #   gz's JointStatePublisher has no update_rate and publishes once
    #   per physics iteration (model.sdf says an <update_rate> child was
    #   tried and measured to change nothing), so each is about 493 Hz on
    #   this 500 Hz world. They are carried because nodes/
    #   wheel_odometry.py consumes both - the drive shaft's reading
    #   channel A for the count grid, the joint state for the STEER angle
    #   - and a tricycle's kinematics needs both or neither.
    #     gz.msgs.Model IS THE JOINT-STATE TYPE ON THE GZ SIDE and
    #     sensor_msgs/msg/JointState is what ros_gz maps it to;
    #     agv/forklift/launch/vehicle.launch.py spells the same pair.
    #     READ_B IS NOT CARRIED. It is the same shaft read a second time,
    #     the cross-comparison of the two is the PLC's function and lives
    #     in m6, and this track has no consumer for it - so bridging it
    #     would be a claim this run does not make.
    spawn bridge ros2 run ros_gz_bridge parameter_bridge \
        "$CFG_TOPICS_CLOCK@rosgraph_msgs/msg/Clock[gz.msgs.Clock" \
        "$CFG_TOPICS_ODOM_GROUND_TRUTH@nav_msgs/msg/Odometry[gz.msgs.Odometry" \
        "$CFG_TOPICS_SCAN_NAV@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" \
        "$CFG_TOPICS_IMU@sensor_msgs/msg/Imu[gz.msgs.IMU" \
        "$CFG_TOPICS_CAM_INFO@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo" \
        "$CFG_TOPICS_JOINT_STATE@sensor_msgs/msg/JointState[gz.msgs.Model" \
        "$CFG_TOPICS_DRIVE_SPEED_READ_A@sensor_msgs/msg/JointState[gz.msgs.Model" \
        "$CFG_TOPICS_STEER_CMD@std_msgs/msg/Float64]gz.msgs.Double" \
        "$CFG_TOPICS_TRACTION_CMD@std_msgs/msg/Float64]gz.msgs.Double"

    # THE LAST TWO LINES ABOVE ARE THE ONLY ONES ON THIS BRIDGE THAT RUN
    # THE OTHER WAY, and F4 Task 1 added them. `]` is ROS -> gz where `[`
    # is gz -> ROS, and what they carry is model.sdf's own two MOTOR
    # TERMINALS: the steer angle in rad and the drive shaft's rate in
    # rad/s. Without them nodes/cmd_vel_tricycle.py would have nowhere
    # to publish - a python process cannot speak gz transport - and the
    # command path would end one hop short of the plant.
    #   THEY COST NOTHING WHEN NOTHING IS COMMANDING. A ROS -> gz bridge
    #   line is a subscription on the ROS side and a publisher on the gz
    #   side; with no publisher on the ROS topic it carries no traffic at
    #   all, which is why they are on the DEFAULT bridge rather than
    #   behind a flag.
    #   AND tools/drive_route.py AND tools/slip_bench.sh STILL WORK. They
    #   address the gz side of these same two topics directly, and gz
    #   transport takes the last write - so what keeps the two from
    #   fighting is not the bridge, it is that the converter publishes
    #   NOTHING until a twist arrives (config.yaml navcmd:, engagement).
    #   THE ROS AND GZ NAMES ARE THE SAME NAME. ros_gz maps a topic to
    #   itself unless told otherwise, so config.yaml's topics.steer_cmd
    #   is the address on both sides and there is no second spelling of
    #   a terminal to keep in step.

    # THE DEPTH IMAGE AND THE COLOUR IMAGE GO THROUGH A SECOND, DIFFERENT
    # BRIDGE, and that is ros_gz's design rather than this script's
    # choice: parameter_bridge carries an Image as a plain topic,
    # image_bridge carries it through image_transport, which is what
    # every ROS image consumer expects to find. camera_info stays on the
    # parameter bridge above because image_bridge does not carry it.
    #   TWO ARGUMENTS, ONE PROCESS. Depth was the only consumer through
    #   F4; F5's AprilTag detector reads the colour stream, so both
    #   images share this child. The point cloud stays unbridged.
    spawn imgbridge ros2 run ros_gz_image image_bridge "$CFG_TOPICS_CAM_DEPTH" "$CFG_TOPICS_CAM_IMAGE"

    # F5 TASK 1's DETECTOR, AND NOT ONE LINE OF IT EXISTS WITHOUT --dock.
    # image_rect is remapped onto the RAW colour stream: this sim camera
    # has no distortion model. camera_info stays the parameter-bridge
    # topic. detections are remapped onto topics.apriltag_detections so
    # the bench never carries a topic literal.
    if [ "$DOCK" = true ]; then
        spawn camtf ros2 run tf2_ros static_transform_publisher \
            --x "$CFG_VEHICLE_CAM_MOUNT_X" \
            --y "$CFG_VEHICLE_CAM_MOUNT_Y" \
            --z "$CFG_VEHICLE_CAM_MOUNT_Z" \
            --roll "$CFG_VEHICLE_CAM_MOUNT_ROLL" \
            --pitch "$CFG_VEHICLE_CAM_MOUNT_PITCH" \
            --yaw "$CFG_VEHICLE_CAM_MOUNT_YAW" \
            --frame-id "$CFG_FRAMES_BASE_LINK" \
            --child-frame-id "$CFG_FRAMES_PALLET_CAM"
        spawn camopt ros2 run tf2_ros static_transform_publisher \
            --x "$CFG_VEHICLE_CAM_OPTICAL_X" \
            --y "$CFG_VEHICLE_CAM_OPTICAL_Y" \
            --z "$CFG_VEHICLE_CAM_OPTICAL_Z" \
            --roll "$CFG_VEHICLE_CAM_OPTICAL_ROLL" \
            --pitch "$CFG_VEHICLE_CAM_OPTICAL_PITCH" \
            --yaw "$CFG_VEHICLE_CAM_OPTICAL_YAW" \
            --frame-id "$CFG_FRAMES_PALLET_CAM" \
            --child-frame-id "$CFG_FRAMES_PALLET_CAM_OPTICAL"
        apriltag_env
        spawn apriltag env "AMENT_PREFIX_PATH=$APRILTAG_AMENT_PREFIX_PATH" \
            "LD_LIBRARY_PATH=$APRILTAG_LD_LIBRARY_PATH" \
            "$APRILTAG_BIN" --ros-args \
            -r __node:="$CFG_APRILTAG_NODE_NAME" \
            --params-file "$APRILTAG_PARAMS" \
            -p use_sim_time:=true \
            -r image_rect:="$CFG_TOPICS_CAM_IMAGE" \
            -r camera_info:="$CFG_TOPICS_CAM_INFO" \
            -r detections:="$CFG_TOPICS_APRILTAG_DETECTIONS"
    fi

    # THE WHEEL ODOMETRY, AFTER THE BRIDGE THAT FEEDS IT. It is the first
    # process on this track that is neither the plant nor a pipe to it:
    # it CONSUMES the bridged joint channels and publishes an estimate of
    # the vehicle's own motion on $CFG_TOPICS_WHEEL_ODOM.
    #   IT IS A STACK CHILD RATHER THAN A BENCH, and that is the whole
    #   difference between it and tools/slip_bench.sh: a bench is a thing
    #   an operator runs at a plant, and an estimator is part of the
    #   vehicle. It goes up with the truck, it is named by `status`, and
    #   `stop` takes it down with everything else.
    #   IT READS NO GROUND TRUTH. $CFG_TOPICS_ODOM_GROUND_TRUTH is on the
    #   bridge above as a measurement REFERENCE and this node has never
    #   heard of it - an estimator that reads ground truth is not an
    #   estimator. The node's own header carries the rule.
    #   python3 AND NOT `ros2 run`: this track is deliberately not a
    #   colcon package (CONTEXT.md), so its nodes are plain files. ROS is
    #   already sourced in this shell by source_ros() above, so the child
    #   inherits an environment that can import rclpy.
    spawn odom python3 "$M5V3/nodes/wheel_odometry.py"

    # THE VEHICLE'S OWN GEOMETRY, ON /tf_static, AND IT IS NOT THE EKF.
    # The IMU stamps its messages with model.sdf's <gz_frame_id>,
    # imu_link, and robot_localization transforms every sample into
    # base_link before it will fuse it. With no base_link -> imu_link
    # transform on the graph it drops the ENTIRE SENSOR and logs nothing
    # at all - measured on this rig 2026-08-26, EVIDENCE_FUSION.md 2.2:
    # the filter runs, publishes, and its yaw never leaves zero.
    #   IT IS A CHILD OF ITS OWN BECAUSE IT IS A DIFFERENT CLAIM. This
    #   edge is where a sensor is BOLTED, which a robot_state_publisher
    #   would own if this track carried a URDF; the EKF's edge is where
    #   the vehicle IS, which is an estimate. One process per claim, one
    #   log per process.
    #   NO use_sim_time ON IT, DELIBERATELY. tf2 stores a static
    #   transform in a cache that answers for ANY query time, so the
    #   stamp is never consulted and a clock this process does not have
    #   cannot go wrong. It publishes once, latched (transient local), so
    #   the EKF may start before or after it.
    spawn imutf ros2 run tf2_ros static_transform_publisher \
        --x "$CFG_VEHICLE_IMU_MOUNT_X" \
        --y "$CFG_VEHICLE_IMU_MOUNT_Y" \
        --z "$CFG_VEHICLE_IMU_MOUNT_Z" \
        --frame-id "$CFG_FRAMES_BASE_LINK" \
        --child-frame-id "$CFG_FRAMES_IMU"

    # THE FILTER, AND IT IS THE FIRST THING ON THIS TRACK THAT PUBLISHES
    # A POSE ANYTHING COULD NAVIGATE ON. robot_localization 3.8.3's
    # ekf_node fuses the wheel odometry's TWIST with the IMU's yaw rate
    # and owns odom -> base_link. The IMU's ACCELERATION is not fused:
    # F2 Task 2 measured that channel diverging the filter at startup
    # and the ruling that fused it was reversed (EVIDENCE_FUSION.md 9).
    #   WHAT IS ON THIS COMMAND LINE AND WHAT IS IN THE FILE. Everything
    #   here is a name or a rate that is already written down elsewhere
    #   on this track - the topics, the frames, the output rate - and is
    #   passed as a `-p` override so that ekf.yaml cannot hold a second
    #   copy of it. ekf.yaml holds what is fused and what is refused, and
    #   the argument for each. config.yaml's ekf: block states the split.
    #   use_sim_time IS NOT OPTIONAL. Every message on this stack is
    #   stamped from the plant's own clock, and a filter comparing those
    #   stamps against a wall clock would reject all of them as
    #   impossibly old. It is not in ekf.yaml because it is a fact about
    #   THIS STACK - there is a bridged /clock - and not about the
    #   filter.
    #   THE OUTPUT TOPIC IS A REMAP because ekf_node's publisher is named
    #   `odometry/filtered` in its own source and the package offers no
    #   parameter to rename it.
    #   AND THE OPTIONAL ARM IS TWO EXTRA ARGUMENTS AND NOTHING ELSE.
    #   With --rf2o the filter is handed a SECOND --params-file and one
    #   more `-p odomN:=`; without it neither string is built and the
    #   command line below is character for character the one
    #   EVIDENCE_FUSION.md 9.3's eight sessions were recorded under. An
    #   ARRAY rather than two copies of a twelve-argument invocation in
    #   an if/else, because the copy that is edited is the one that is
    #   right and the other one is the bug.
    #     THE OVERLAY GOES AFTER ekf.yaml, which is how rclcpp merges
    #     parameter files: later ones win per key, and this one defines
    #     only keys the first does not.
    #     AN EMPTY ARRAY EXPANDS TO NOTHING under `set -u` because it is
    #     quoted as "${ekf_arm[@]}"; unquoted, or under bash 4.3, an
    #     empty array is an unbound variable and the whole bringup would
    #     abort on the OFF path - which is the path that must not change.
    #   AND ON THE --fuse ARM THIS WHOLE CHILD IS SOMEBODY ELSE. F2 Task
    #   4's factor graph goes up in ekf_node's PLACE, not beside it:
    #   both publish odom -> base_link, tf2 has no notion of two
    #   authorities for one edge, and two of them would produce a coin
    #   toss at 50 Hz rather than a comparison. Everything the two arms
    #   have in common is passed to both from the same config keys - the
    #   two input topics, the three frames, the output rate - so the
    #   A/B's controlled variables are controlled HERE, on these two
    #   command lines, and not by two parameter files agreeing.
    if [ "$FUSE" = true ]; then
        # THE TWO SEARCH PATHS, BUILT NOW AND PLACED ON ONE COMMAND LINE.
        # fuse_env() prepends the vendored prefix to what source_ros()
        # exported; it is called here rather than beside fuse_paths()
        # because before that line AMENT_PREFIX_PATH has no ROS in it.
        #   THROUGH `env` AND NOT THROUGH export, DELIBERATELY. An export
        #   at this point in start() would land on every child spawned
        #   after it - here, the gz GUI client - and this arm's business
        #   is with exactly one process. `env` execs the binary in place,
        #   so the pid spawn() records is still the node's own.
        fuse_env
        # THE TWO SENSORS' TARGET FRAME IS base_link ON BOTH, and it is
        # bound to a local so the two `-p` lines below fit a line. It is
        # where the EKF arm's hard dependency on `imutf` shows up on this
        # one: the IMU stamps its messages imu_link, this node transforms
        # every twist into the target frame before it will fuse it, and
        # without the static transform the samples are dropped
        # (EVIDENCE_FUSION.md 2.2 is the same failure on the other arm).
        local base="$CFG_FRAMES_BASE_LINK"
        # WHERE THE FUSED ESTIMATE COMES OUT ON THIS ARM, bound here
        # because it is what the smoother below is handed as its
        # `odom_topic`. The two arms publish at two addresses
        # (config.yaml topics.fuse_odometry_filtered argues why) and a
        # parameter file cannot know which is up. It is the shell's half
        # of tools/evidence_core.py's fused_topic_key(), which is where
        # every INSTRUMENT on this track asks the same question.
        #   THE SHIPPING SMOOTHER DOES NOT READ IT. smoother.yaml is
        #   feedback: OPEN_LOOP since the A/B in EVIDENCE_NAV_V3.md 6.3.
        #   It is passed anyway so the arm cannot drift away from the
        #   address while that ruling is revisitable - and so that the
        #   ONE thing it may never be, the ground truth, is decided here
        #   rather than in a parameter file.
        FUSED_TOPIC="$CFG_TOPICS_FUSE_ODOMETRY_FILTERED"
        # WHY THE BINARY IS NAMED BY ABSOLUTE PATH rather than run
        # through `ros2 run`: `ros2 run` would find it now that
        # AMENT_PREFIX_PATH names the prefix, and it FORKS - the pid this
        # script records would be a python wrapper and the process doing
        # the work would be its child, which is exactly the complication
        # EVIDENCE_FUSION.md 10.4 had to work around to measure the EKF's
        # CPU. install_rf2o.sh's arm is spawned the same way.
        #   AND ITS OUTPUT RATE IS ekf.frequency_hz, WHICH IS NOT A
        #   BORROWED KEY - IT IS THE A/B's CONTROLLED VARIABLE. There is
        #   ONE output rate on this track and both estimators publish at
        #   it. A second key would be a second copy of 50.0 that could
        #   drift, and an arm publishing at a different rate from the one
        #   it is compared with would move the latency and the
        #   delivered-rate rows for a reason that is not the estimator.
        #   config.yaml's ekf.frequency_hz carries the argument for the
        #   number itself, and it is about the CONSUMERS rather than
        #   about robot_localization.
        spawn fuse env "AMENT_PREFIX_PATH=$FUSE_AMENT_PREFIX_PATH" \
            "LD_LIBRARY_PATH=$FUSE_LD_LIBRARY_PATH" \
            "$FUSE_BIN" --ros-args \
            -r __node:="$CFG_FUSE_NODE_NAME" \
            --params-file "$FUSE_PARAMS" \
            -p use_sim_time:=true \
            -p optimization_frequency:="$CFG_FUSE_OPTIMIZATION_FREQUENCY_HZ" \
            -p lag_duration:="$CFG_FUSE_LAG_DURATION_S" \
            -p transaction_timeout:="$CFG_FUSE_TRANSACTION_TIMEOUT_S" \
            -p wheel_odometry_sensor.topic:="$CFG_TOPICS_WHEEL_ODOM" \
            -p wheel_odometry_sensor.twist_target_frame:="$base" \
            -p imu_sensor.topic:="$CFG_TOPICS_IMU" \
            -p imu_sensor.twist_target_frame:="$base" \
            -p filtered_publisher.topic:="$CFG_TOPICS_FUSE_ODOMETRY_FILTERED" \
            -p filtered_publisher.publish_frequency:="$CFG_EKF_FREQUENCY_HZ" \
            -p filtered_publisher.map_frame_id:="$CFG_FRAMES_MAP" \
            -p filtered_publisher.odom_frame_id:="$CFG_FRAMES_ODOM" \
            -p filtered_publisher.base_link_frame_id:="$base" \
            -p filtered_publisher.base_link_output_frame_id:="$base" \
            -p filtered_publisher.world_frame_id:="$CFG_FRAMES_ODOM"
    else
        # THE SHIPPING FILTER'S ADDRESS, and the smoother's feedback
        # follows it exactly as it follows the other arm's. See the
        # --fuse branch above for the whole argument.
        FUSED_TOPIC="$CFG_TOPICS_ODOMETRY_FILTERED"
        local ekf_arm=()
        if [ "$RF2O" = true ]; then
            ekf_arm=(--params-file "$EKF_RF2O_PARAMS"
                     -p odom1:="$CFG_TOPICS_RF2O_ODOM")
        fi
        spawn ekf ros2 run robot_localization ekf_node --ros-args \
            -r __node:="$CFG_EKF_NODE_NAME" \
            --params-file "$EKF_PARAMS" \
            ${ekf_arm[@]+"${ekf_arm[@]}"} \
            -p use_sim_time:=true \
            -p frequency:="$CFG_EKF_FREQUENCY_HZ" \
            -p map_frame:="$CFG_FRAMES_MAP" \
            -p odom_frame:="$CFG_FRAMES_ODOM" \
            -p base_link_frame:="$CFG_FRAMES_BASE_LINK" \
            -p world_frame:="$CFG_FRAMES_ODOM" \
            -p odom0:="$CFG_TOPICS_WHEEL_ODOM" \
            -p imu0:="$CFG_TOPICS_IMU" \
            -r /odometry/filtered:="$CFG_TOPICS_ODOMETRY_FILTERED"
    fi

    # ---------------------- THE COMMAND PATH, F4 ----------------------
    # TWO CHILDREN, AND NEITHER IS BEHIND A FLAG. F4 constraint 18: the
    # command path is ONE LINE with no bypass -
    #
    #   Nav2's controller (F4 Task 2) -> $CFG_TOPICS_CMD_VEL
    #     -> velocity_smoother        -> $CFG_TOPICS_CMD_VEL_SMOOTHED
    #       -> nodes/cmd_vel_tricycle.py
    #         -> $CFG_TOPICS_STEER_CMD + $CFG_TOPICS_TRACTION_CMD
    #
    # - and a line that exists on some arms and not others is not one
    # line. There is no `--nav` gate on THESE two for three reasons:
    #   THE PATH HAS TO BE VERIFIABLE WITHOUT NAV2. F4 Task 1's whole
    #   evidence is an OPEN-LOOP drive - a scripted twist profile through
    #   the smoother and the converter, scored against ground truth -
    #   and a converter that only exists on the arm that also brings up a
    #   planner cannot be measured apart from one.
    #   F4 TASK 2's ARM ASSUMES IT. `--nav` adds the planner, the
    #   controller and the BT navigator ON TOP of a path that is already
    #   there, which is the same shape --localize has over the estimator.
    #   AND IT COSTS NOTHING IDLE. The smoother publishes nothing with
    #   nothing commanding (measured, config.yaml smoother:) and the
    #   converter publishes nothing until it is engaged (config.yaml
    #   navcmd:), so the default stack's two gz-side benches keep the
    #   terminals to themselves and EVIDENCE_NAV_V3.md carries the CPU
    #   and RTF this pair actually costs.
    #
    # THE SMOOTHER FIRST, AND IT IS AFTER THE ESTIMATOR ON PURPOSE. It is
    # handed the fused estimate as its `odom_topic` - whichever arm is
    # up, which is what $FUSED_TOPIC carries - and a subscriber started
    # before its publisher only spends its first moments limiting
    # against nothing. It NEVER subscribes the ground truth: F2
    # constraint 13 and F4 constraint 18, and the address it is given
    # here is the one thing that could break that.
    #   AND ON THE SHIPPING RULING IT DOES NOT SUBSCRIBE AT ALL.
    #   smoother.yaml is feedback: OPEN_LOOP - the crib specifies
    #   CLOSED_LOOP and EVIDENCE_NAV_V3.md 6.3 is the A/B that reversed
    #   it on this vehicle, whose estimate is deliberately a bad
    #   instrument for a limiter to close on.
    #   EVERYTHING ON THIS COMMAND LINE IS AN ADDRESS OR A LIFECYCLE
    #   FACT. What is LIMITED and to what is smoother.yaml's, checked
    #   above for the node name it is addressed to; use_sim_time is a
    #   fact about THIS STACK (there is a bridged /clock) and not about
    #   the smoother, which is ekf_node's own split.
    spawn smoother ros2 run "$CFG_SMOOTHER_PACKAGE" \
        "$CFG_SMOOTHER_EXECUTABLE" --ros-args \
        -r __node:="$CFG_SMOOTHER_NODE_NAME" \
        --params-file "$SMOOTHER_PARAMS" \
        -p use_sim_time:=true \
        -p odom_topic:="$FUSED_TOPIC" \
        -r /cmd_vel:="$CFG_TOPICS_CMD_VEL" \
        -r /cmd_vel_smoothed:="$CFG_TOPICS_CMD_VEL_SMOOTHED"

    # AND THE CONVERTER, WHICH IS THE LAST THING BEFORE THE PLANT. It
    # turns a base_link twist into the steer angle and wheel rate
    # model.sdf's two terminals carry, ramps both at the plant's own
    # actuator limits, and is the one place on this stack that enforces
    # the MEASURED curvature ceiling. nodes/cmd_vel_tricycle_core.py is
    # the arithmetic and is the INVERSE of what nodes/wheel_odom_core.py
    # integrates - the same sign discipline, cited in its header.
    #   python3 AND NOT `ros2 run`, for wheel_odometry.py's reason: this
    #   track is deliberately not a colcon package.
    #   IT READS NO GROUND TRUTH AND NO POSE. It measures nothing and
    #   corrects nothing; the same twist twice gives the same pair twice.
    #
    # -------------- AND ON --monitor, ONE LINK IN BETWEEN --------------
    # F4 TASK 3. nav2_collision_monitor goes up HERE - after the
    # smoother, before the converter - and the converter's INPUT is
    # remapped onto its output. Both halves of that sentence are choices
    # and both are argued.
    #   WHY BETWEEN THE SMOOTHER AND THE CONVERTER, AND NOT ANYWHERE
    #   ELSE. This node subscribes a Twist and publishes a Twist. After
    #   the converter there is no Twist at all - the two terminals carry
    #   Float64 in wheel-domain units - so "between the converter and
    #   the plant" is not a place this node can stand. Before the
    #   smoother it would be re-ramped: a stop the monitor asked for
    #   would be handed to a limiter that softens it back into a 0.35
    #   m/s^2 ramp, which is the one thing a guard must not have done to
    #   it. So it is last but one, which is also nav2's own
    #   recommendation for it.
    #   WHY THE CONVERTER IS REMAPPED RATHER THAN THE SMOOTHER'S OUTPUT
    #   RE-POINTED. Either would insert the node. Re-pointing the
    #   smoother would leave a topic called $CFG_TOPICS_CMD_VEL_SMOOTHED
    #   that the smoother does not publish, and an address whose name is
    #   a lie is the thing this track spends most of its checks
    #   preventing. Remapping the LAST node keeps every existing address
    #   meaning exactly what it says and adds one new name.
    #   F4 CONSTRAINT 18 STILL HOLDS AND THE LINE IS ONE LINK LONGER.
    #   There is one path from the controller to the terminals, no
    #   bypass, and no ground truth in it - the monitor subscribes a
    #   twist and a scan and nothing else. What changed is that on this
    #   arm the path has four nodes in it instead of three, and every
    #   session recorded on it is labelled monitor=on@<md5> so that no
    #   figure taken through the longer path can sit in a table with one
    #   taken through the shorter.
    #   AND IT IS NOT A SAFETY FUNCTION. nav2's own words, verbatim:
    #   it "does not provide hard real-time safety certifications". It
    #   does not replace a safety-rated PLC. It complements the F-PLC;
    #   it is not the F-PLC.
    local navcmd_in="$CFG_TOPICS_CMD_VEL_SMOOTHED"
    if [ "$MONITOR" = true ]; then
        spawn monitor ros2 run "$CFG_MONITOR_PACKAGE"             "$CFG_MONITOR_EXECUTABLE" --ros-args             -r __node:="$CFG_MONITOR_NODE_NAME"             --params-file "$MONITOR_PARAMS"             -p cmd_vel_in_topic:="$CFG_TOPICS_CMD_VEL_SMOOTHED"             -p cmd_vel_out_topic:="$CFG_TOPICS_CMD_VEL_MONITORED"             -p state_topic:="$CFG_TOPICS_COLLISION_MONITOR_STATE"             -p scan.topic:="$CFG_TOPICS_SCAN_NAV"
        navcmd_in="$CFG_TOPICS_CMD_VEL_MONITORED"
    fi
    # THE REMAP IS A ROS REMAP AND NOT A SECOND CONFIG KEY, which is the
    # smoother's and the controller's own idiom one node further down:
    # the address a node reads is decided on the command line by the
    # thing that knows which arm this is, and config.yaml keeps both
    # names. With no --monitor the two strings are equal and the remap
    # is an identity, which is why it is written unconditionally rather
    # than inside the branch - a command line that differs between arms
    # is a command line two arms cannot be compared through.
    spawn navcmd python3 "$M5V3/nodes/cmd_vel_tricycle.py" --ros-args         -r "$CFG_TOPICS_CMD_VEL_SMOOTHED":="$navcmd_in"

    # ------------------- THE OPTIONAL LOCALISATION ARM -------------------
    # TWO MORE CHILDREN, AND NEITHER EXISTS WITHOUT --localize. The whole
    # block is skipped by the default stack, which is the claim
    # EVIDENCE_LOCALIZATION_V3.md has to be able to make: `start` without
    # the flag spawns the same six processes, hands the estimator the
    # same parameter files, and publishes nothing on `map` -> `odom` or
    # on either amcl topic.
    #
    # AND THEY GO **AFTER** THE ESTIMATOR, WHICH IS THE OPPOSITE OF THE
    # rf2o ARM'S ORDERING AND FOR THE OPPOSITE REASON. rf2o has one
    # unretried TF lookup and has to be started before there is anything
    # to trigger it; AMCL's scan subscription is a tf2 MessageFilter,
    # which QUEUES what it cannot yet transform and releases it when the
    # chain closes - so starting it before `odom` -> `base_link` exists
    # costs nothing but a few dropped scans, and starting it after costs
    # nothing at all. What decides the order is the OTHER end: map_server
    # reads a 1712 x 1196 grid on its configure transition and AMCL
    # blocks in on_activate waiting for that map, so the two transitions
    # below are the slow part of this arm and they belong last, where
    # the rest of the stack is already up and can be reported on.
    if [ "$LOCALIZE" = true ] \
       && [ "$LOCALIZER" = "$CFG_LOCALIZATION_AMCL_LABEL" ]; then
        # THE FROZEN GRID, SERVED. Everything on this command line is an
        # ADDRESS config.yaml already owns - the artifact's path, the
        # topic and the frame - passed as `-p` overrides so amcl.yaml
        # cannot hold a second copy of any of them (that file's header
        # carries the split). The grid's md5 was checked against the
        # committed registration before this function started anything.
        spawn "$CFG_LOCALIZATION_MAP_SERVER_NODE_NAME" \
            ros2 run "$CFG_LOCALIZATION_MAP_SERVER_PACKAGE" \
            "$CFG_LOCALIZATION_MAP_SERVER_EXECUTABLE" --ros-args \
            -r __node:="$CFG_LOCALIZATION_MAP_SERVER_NODE_NAME" \
            --params-file "$LOC_PARAMS" \
            -p use_sim_time:=true \
            -p yaml_filename:="$MAP_YAML" \
            -p topic_name:="$CFG_TOPICS_MAP" \
            -p frame_id:="$CFG_FRAMES_MAP"

        # AND THE LOCALISER. Same split: the scan topic, the map topic
        # and the three frames are config.yaml's and arrive as
        # overrides; what is FUSED - the motion model, the sensor model,
        # the particle counts and the argument for every one of them -
        # is amcl.yaml's and is not repeated here.
        #   THE THREE FRAMES ARE THE WHOLE OF F3 CONSTRAINT 15 ON ONE
        #   COMMAND LINE. global_frame_id is `map` and odom_frame_id is
        #   `odom`, so the edge this node publishes is map -> odom and
        #   nothing else; base_link_frame is where it thinks the vehicle
        #   is. The estimator's own world_frame is the ODOM frame
        #   (ekf.yaml), so the two publishers own two disjoint edges and
        #   neither can become the other.
        spawn "$LOC_NODE" \
            ros2 run "$LOC_PACKAGE" "$LOC_EXECUTABLE" --ros-args \
            -r __node:="$LOC_NODE" \
            --params-file "$LOC_PARAMS" \
            -p use_sim_time:=true \
            -p scan_topic:="$CFG_TOPICS_SCAN_NAV" \
            -p map_topic:="$CFG_TOPICS_MAP" \
            -p base_frame_id:="$CFG_FRAMES_BASE_LINK" \
            -p odom_frame_id:="$CFG_FRAMES_ODOM" \
            -p global_frame_id:="$CFG_FRAMES_MAP"

    elif [ "$LOCALIZE" = true ]; then
        # ---- THE OTHER LOCALISER, F3 Task 3, AND IT IS ONE CHILD ----
        #
        # AN elif AND NOT A SECOND if, WHICH IS --fuse's SHAPE AND ITS
        # ARGUMENT. Both arms publish map -> odom and tf2 has no notion
        # of two authorities for one edge, so the exclusion has to be
        # STRUCTURAL: there is no command line, no config edit and no
        # ordering accident that can put both branches up, because a
        # shell does not run both branches of one `if`.
        #
        # NO map_server ON THIS ARM. This node deserialises the pose
        # graph on its own configure transition and rasters an occupancy
        # grid from it onto topics.map, which is exactly what map_server
        # does for the other arm - so a map_server here would be a second
        # publisher of that topic serving a different rendering of the
        # same building. EIGHT children instead of nine.
        #
        # THE SEED IS ON THIS COMMAND LINE AND THAT IS THE ARM'S OWN
        # SEMANTICS. slam_toolbox's localisation node reads
        # `map_start_pose` in loadPoseGraphByParams() on the CONFIGURE
        # transition; with neither it nor `map_start_at_dock` it logs
        # "Map starting pose not specified" and starts at the graph's own
        # origin - which is where the MAPPING drive began. So where the
        # amcl arm is seeded by a MESSAGE that tools/localization_health.py
        # publishes, this arm is seeded by a PARAMETER: the same three
        # numbers, from the same vehicle.spawn, through the same
        # committed registration, derived by the one piece of arithmetic
        # that owns them (map_register.seed_pose, which that gate calls
        # too - so the pose this node is STARTED at and the pose the gate
        # compares its answer against cannot disagree).
        #   THE DERIVATION IS A SUBPROCESS AND ITS FAILURE IS A REFUSAL.
        #   `map_register.py seed` verifies the registration against the
        #   grid on disk on its way past; if it refuses, its own message
        #   is on this terminal and there is nothing to start.
        local seed
        seed="$(python3 "$M5V3/tools/map_register.py" seed)" || refuse \
            "the seed pose could be derived from the registration" \
            "$M5V3/tools/map_register.py seed (its refusal is above)" \
            "this arm is told where it starts by a PARAMETER read on its" \
            "configure transition, and without one it would start at the" \
            "pose graph's own origin - which is where the MAPPING drive" \
            "began, not where this run does." \
            "NOTHING WAS STARTED."
        spawn "$LOC_NODE" \
            ros2 run "$LOC_PACKAGE" "$LOC_EXECUTABLE" --ros-args \
            -r __node:="$LOC_NODE" \
            --params-file "$LOC_PARAMS" \
            -p use_sim_time:=true \
            -p scan_topic:="$CFG_TOPICS_SCAN_NAV" \
            -p map_name:="$CFG_TOPICS_MAP" \
            -p base_frame:="$CFG_FRAMES_BASE_LINK" \
            -p odom_frame:="$CFG_FRAMES_ODOM" \
            -p map_frame:="$CFG_FRAMES_MAP" \
            -p map_file_name:="$MAP_GRAPH" \
            -p map_start_pose:="[$(echo "$seed" | tr ' ' ',')]"
    fi

    # THE GUI CLIENT LAST AND GATED, or the lidar fans anchor at the world
    # origin for the life of the window. Measured in m6 on gz-sim 8.11.0:
    # GuiRunner discards every world-state message that arrives before its
    # initial snapshot is processed, and the SensorTopic components the
    # VisualizeLidar plugin anchors on are created a beat AFTER the spawn.
    # Waiting for a scanner topic to be advertised on the gz side puts
    # those components inside the snapshot a late client receives in full.
    # config.yaml's topics.safety_scan_back is that topic and is
    # deliberately NOT bridged: the gate is a gz-side question. The key is
    # named for the SENSOR because F1 Task 4's evidence recorder captures
    # the same channel for its noise figure - see the comment there.
    if [ "$GUI" = true ]; then
        spawn gui bash -c "until gz topic -l 2>/dev/null \
            | grep -qF '$CFG_TOPICS_SAFETY_SCAN_BACK'; \
            do sleep $CFG_TIMING_GUI_GATE_POLL_S; done; \
            sleep $CFG_TIMING_GUI_GATE_SETTLE_S; exec gz sim -g -v 2"
    fi

    # "A process that dies in its first fraction of a second has not
    # started, and saying 'started' about it sends the operator to the
    # wrong log" (stack.sh:243-244). By this line the youngest child is a
    # second old and the world is a dozen.
    sleep "$CFG_TIMING_STARTUP_CHECK_S"
    assert_children_alive

    # AND ON THE rf2o ARM, ONE MORE THING THAT IS ALIVE-BUT-WRONG.
    # Same shape as the filter's gate below and for the same reason:
    # every check above is green over a scan matcher that never found
    # out where it is mounted. See check_rf2o_transform().
    if [ "$RF2O" = true ]; then
        check_rf2o_transform
    fi


    # AND THE ESTIMATOR IS ASKED WHETHER IT IS STILL ONE - WHICHEVER
    # ESTIMATOR IT IS. tools/ekf_health.py reads the arm off the state
    # file write_traction() has already written by this line and picks
    # the topic from it, so the ONE gate covers both arms and neither has
    # a copy of the other's arithmetic (tools/evidence_core.py's
    # fused_topic_key(), tested there without ROS). The ceiling it
    # compares against is ekf.startup_check.covariance_max on both arms,
    # and config.yaml's fuse: block argues why there is not a second one.
    # Every child is
    # alive by this line, which on this stack is NOT the same as every
    # child working: ekf_node can diverge during its first cycles -
    # covariance to 1e84 in a single 20 ms step - and stay up, at rate,
    # saying nothing, so that every other check here is green over a
    # filter that has stopped being one (EVIDENCE_FUSION.md 8.6, 9).
    # One read of one message, bounded, with the truck still standing
    # where it was spawned. The logic and the parse are
    # tools/ekf_health.py and evidence_core, where a test reaches them
    # without a simulator; this line is the orchestration.
    if ! python3 "$M5V3/tools/ekf_health.py"; then
        refuse "the filter came up sane, and not merely alive" \
            "$M5V3/tools/ekf_health.py (its refusal is printed above)" \
            "the covariance check above is what said no, and it is the" \
            "ONLY check on this stack that can: the process is running," \
            "the topic is at its configured rate and every other test" \
            "here has passed." \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
            "'$0 stop', then start again - this does not recur every time."
    fi

    # AND THE COMMAND PATH IS ASKED WHETHER IT IS ONE. F4 Task 1, and it
    # is two questions rather than one, because the path has two ways of
    # being alive and broken at the same time.
    #   FIRST: DID THE SMOOTHER REACH ACTIVE? Nothing drives it - it
    #   self-transitions off smoother.yaml's autostart_node - so a node
    #   sitting in UNCONFIGURED here is a parameter that did not land,
    #   and the symptom is a command path with no smoother in it.
    smoother_active
    #   AND ON --monitor, THE SAME QUESTION OF THE NODE BETWEEN THEM.
    #   It is asked BEFORE the line is tested below, because on this arm
    #   a monitor short of ACTIVE is not a missing guard - it is a CUT
    #   COMMAND PATH, and navcmd_health.py's zero twist would then time
    #   out on a symptom four hops from its cause.
    if [ "$MONITOR" = true ]; then monitor_active; fi
    #   SECOND: DOES A COMMAND ACTUALLY REACH THE TERMINALS? Every check
    #   above is satisfied by three processes that have never spoken to
    #   each other: the smoother ACTIVE with nothing subscribed to its
    #   output, a converter ALIVE with a misspelt subscription, a bridge
    #   line pointing the wrong way. tools/navcmd_health.py publishes ONE
    #   twist - a ZERO twist, the only command that cannot move this
    #   vehicle - and reads the answer back off the two terminals. It is
    #   the smallest possible demonstration that the line is a line.
    if ! python3 "$M5V3/tools/navcmd_health.py"; then
        refuse "one command reached the plant's own terminals" \
            "$M5V3/tools/navcmd_health.py (its refusal is printed above)" \
            "every other check on this stack has passed: both command" \
            "path children are ALIVE, the smoother is ACTIVE and the" \
            "estimator underneath is sane." \
            "WHAT THAT LEAVES is three processes that have never spoken" \
            "to each other - and nothing else on this stack can tell" \
            "that apart from a working command path, because at rest a" \
            "working one publishes nothing either." \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
            "'$0 stop', then read $LOGDIR/smoother.log and $LOGDIR/navcmd.log."
    fi

    #   AND ON --monitor, THIRD: THE ONE FAILURE THAT ARRIVES AFTER THE
    #   GATE ABOVE HAS ALREADY PASSED. It is LAST rather than beside
    #   monitor_active for a measured reason - the collision monitor
    #   relays every twist until the first scan it cannot transform
    #   reaches it, which was 9.9 s after activation on the run that
    #   found this, and the zero-twist gate above ran inside that window
    #   and passed truthfully over a path that was cut ten seconds
    #   later. check_monitor_transform() therefore WATCHES rather than
    #   looks, and it is placed here so its watch overlaps the twists
    #   the gate above has just finished publishing.
    if [ "$MONITOR" = true ]; then
        check_monitor_transform
    fi

    # AND ON THE LOCALISATION ARM, THE TWO LIFECYCLE TRANSITIONS AND THE
    # GATE BEHIND THEM. Both nodes are ALIVE by this line and neither has
    # done anything at all: a nav2 lifecycle node that is started and
    # left UNCONFIGURED subscribes to nothing, advertises nothing and
    # publishes no transform, while logging nothing that reads as an
    # error. That is the failure sim/launch/warehouse_slam.launch.py
    # recorded for slam_toolbox and agv/forklift/launch/
    # localization.launch.py recorded for these two, and it is why they
    # are driven here rather than by a nav2 lifecycle_manager (whose bond
    # starves at simulation real-time factors - config.yaml's
    # localization: block and amcl.yaml's bond note carry the argument).
    #   THE ORDER IS MEASURED. map_server is configured AND ACTIVATED
    #   before amcl is configured, because amcl's on_activate waits for a
    #   map on the latched topic and an inactive map_server never
    #   publishes one - configure amcl first and it blocks in a
    #   transition with no error.
    if [ "$LOCALIZE" = true ]; then
        localize_lifecycle
        # AND THEN THE ONE QUESTION THAT IS LEFT: is this a localiser, or
        # a node that is merely running? tools/localization_health.py
        # subscribes to the pose topic, publishes the initial pose the
        # bringup knows, and reads back the filter's own first answer -
        # in that order, because with the truck standing still AMCL
        # publishes exactly ONE pose per seed and a reader that arrived
        # late would wait for a second one that never comes. It checks
        # the covariance against a ceiling and the pose against the seed,
        # and it refuses by name. The arithmetic is evidence_core's,
        # where tests reach it without a simulator.
        if ! python3 "$M5V3/tools/localization_health.py"; then
            refuse "the localiser came up localised, and not merely alive" \
                "$M5V3/tools/localization_health.py (its refusal is printed above)" \
                "every other check on this stack has passed: every" \
                "localisation node is ALIVE, every lifecycle transition" \
                "returned success, and the estimator underneath is sane." \
                "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
                "'$0 stop', then read $LOGDIR/$LOC_NODE.log."
        fi
    fi

    # ------------------------ THE NAV ARM, F4 TASK 2 --------------------
    # FIVE MORE CHILDREN, AND NOT ONE OF THEM EXISTS WITHOUT --nav.
    #
    # AND THEY GO UP **HERE**, AFTER THE LOCALISER HAS REACHED ACTIVE,
    # WHICH IS THE LAST THING IN THIS FUNCTION AND IS NOT TIDINESS.
    # nav2_costmap_2d's Costmap2DROS::on_activate BLOCKS in a
    # canTransform() loop until it can resolve its own global_frame ->
    # robot_base_frame. For `global_costmap` that is map -> base_link,
    # and map -> odom does not exist until the localiser is ACTIVE - so
    # a nav arm started earlier would sit wedged in a lifecycle
    # transition with five ALIVE processes and nothing in any log that
    # reads as an error. That is the same class of failure the
    # map_server-before-amcl ordering above exists for, one layer up.
    #   IT IS ALSO WHY assert_children_alive IS A FUNCTION. These five
    #   are spawned after the first startup check has already run, so
    #   the same question has to be asked a second time.
    #   THE MANAGER IS SPAWNED LAST OF THE FIVE. It looks up each
    #   server's change_state service and starts transitioning as soon
    #   as it can; started first it would spend its whole
    #   wait_for_service budget on nodes that do not exist yet.
    if [ "$NAV" = true ]; then
        # THE PLANNER. Everything on this command line is an ADDRESS or
        # a lifecycle fact; what is PLANNED - the motion model, the
        # turning radius, the penalties, the costmap layers - is
        # nav2.yaml's and is not repeated here. use_sim_time is in that
        # file rather than here, which is the opposite of every other
        # node on this stack and is argued in its header: two of the six
        # sections it addresses are SUB-NODES with no command line, so
        # the stack fact is written once in one place instead of four
        # times here and twice there.
        spawn "$CFG_NAV_PLANNER_NODE_NAME" \
            ros2 run "$CFG_NAV_PLANNER_PACKAGE" \
            "$CFG_NAV_PLANNER_EXECUTABLE" --ros-args \
            -r __node:="$CFG_NAV_PLANNER_NODE_NAME" \
            --params-file "$NAV_PARAMS"

        # THE CONTROLLER, AND THE ONE OVERRIDE IT NEEDS IS THE ESTIMATOR
        # ARM'S ADDRESS. $FUSED_TOPIC is whichever estimator went up -
        # the shell's half of tools/evidence_core.py's fused_topic_key()
        # - and a parameter file cannot know which. It is passed HERE
        # for the smoother's reason: the one thing this topic may never
        # be is the GROUND TRUTH (F2 constraint 13, F4 constraint 18),
        # and that is decided on this line rather than in a file
        # somebody could edit.
        #   THE CONTROLLER PUBLISHES INTO THE TOP OF F4 TASK 1's LINE.
        #   /cmd_vel is remapped to config.yaml's topics.cmd_vel, which
        #   is where the velocity smoother is already listening - the
        #   path below it is unchanged and was measured end to end with
        #   no Nav2 in the room (EVIDENCE_NAV_V3.md 4).
        #   AND IT SUBSCRIBES THE SAME SPEED LIMIT THE CONVERTER DOES.
        #   Two ceilings on one quantity is a min(), which is
        #   idempotent: the controller clamps the speed it PLANS at and
        #   the converter clamps the speed it DELIVERS, last, where no
        #   upstream publisher can get round it (EVIDENCE_NAV_V3.md 9).
        spawn "$CFG_NAV_CONTROLLER_NODE_NAME" \
            ros2 run "$CFG_NAV_CONTROLLER_PACKAGE" \
            "$CFG_NAV_CONTROLLER_EXECUTABLE" --ros-args \
            -r __node:="$CFG_NAV_CONTROLLER_NODE_NAME" \
            --params-file "$NAV_PARAMS" \
            -p odom_topic:="$FUSED_TOPIC" \
            -p speed_limit_topic:="$CFG_TOPICS_SPEED_LIMIT" \
            -r /cmd_vel:="$CFG_TOPICS_CMD_VEL"

        # THE BEHAVIOUR SERVER, which on this vehicle runs exactly one
        # behaviour and it does not move the truck. nav2.yaml's
        # behavior_server section carries the whole argument for why
        # `spin`, `backup` and `drive_on_heading` are all absent.
        #   ITS /cmd_vel IS REMAPPED ANYWAY. `wait` publishes nothing,
        #   so the remap carries no traffic - but a behaviour server
        #   left on nav2's default topic name would be a SECOND
        #   publisher on an address the whole command path is built
        #   around, and an address that is only right because nothing
        #   uses it is not right.
        spawn "$CFG_NAV_BEHAVIOR_NODE_NAME" \
            ros2 run "$CFG_NAV_BEHAVIOR_PACKAGE" \
            "$CFG_NAV_BEHAVIOR_EXECUTABLE" --ros-args \
            -r __node:="$CFG_NAV_BEHAVIOR_NODE_NAME" \
            --params-file "$NAV_PARAMS" \
            -r /cmd_vel:="$CFG_TOPICS_CMD_VEL"

        # THE BT NAVIGATOR, and the TREE is the thing it must not get
        # wrong. `default_nav_to_pose_bt_xml` is resolved against the
        # PROCESS's working directory, so it is passed as an ABSOLUTE
        # path built from $REPO - a relative name would be a file this
        # node looks for wherever the operator's shell was standing,
        # and a tree it cannot open is a navigator that falls back to
        # nav2's own, which has Spin and BackUp in it.
        spawn "$CFG_NAV_BT_NODE_NAME" \
            ros2 run "$CFG_NAV_BT_PACKAGE" \
            "$CFG_NAV_BT_EXECUTABLE" --ros-args \
            -r __node:="$CFG_NAV_BT_NODE_NAME" \
            --params-file "$NAV_PARAMS" \
            -p odom_topic:="$FUSED_TOPIC" \
            -p default_nav_to_pose_bt_xml:="$NAV_BT"

        # AND THE ONE LIFECYCLE MANAGER, WHICH IS THE ONLY ONE ON THIS
        # TRACK. localize_lifecycle() drives amcl and map_server by hand
        # because a manager's BOND is a heartbeat with a deadline and a
        # deadline starves at the real-time factors a simulation
        # reaches. That argument is about the BOND and not about the
        # manager: nav2.yaml switches it off at this end
        # (`bond_timeout: 0.0`) and every server above carries
        # nav2.yaml's own defaults at theirs. What is left is what a
        # manager is actually for here - SIX lifecycle nodes behind FOUR
        # names, transitioned in a fixed order by one process instead of
        # by four more shell loops.
        #   THE VELOCITY SMOOTHER IS NOT IN ITS LIST. It is part of the
        #   COMMAND PATH and not of this arm (F4 constraint 18): it goes
        #   up on every bringup and drives itself to ACTIVE off
        #   smoother.yaml's autostart_node. A manager that owned it
        #   would own a node that exists on arms the manager does not.
        spawn "$CFG_NAV_LIFECYCLE_NODE_NAME" \
            ros2 run "$CFG_NAV_LIFECYCLE_PACKAGE" \
            "$CFG_NAV_LIFECYCLE_EXECUTABLE" --ros-args \
            -r __node:="$CFG_NAV_LIFECYCLE_NODE_NAME" \
            --params-file "$NAV_PARAMS"

        sleep "$CFG_TIMING_STARTUP_CHECK_S"
        assert_children_alive

        # AND THE ONE QUESTION THAT IS LEFT: can it PLAN? Every check
        # above is satisfied by five processes that have never spoken to
        # each other, and the failure they hide is specific and silent -
        # a global costmap whose static layer never received the frozen
        # grid is wall-to-wall NO_INFORMATION, and with
        # `allow_unknown: false` the planner then refuses every goal
        # after max_planning_time, once, into its own log. Every node
        # ACTIVE, every log clean, and the first anybody hears of it is
        # a goal that times out several minutes into a measured run.
        # tools/nav_health.py waits for all SIX lifecycle nodes - the
        # two costmaps are lifecycle nodes of their own inside their
        # servers - and then computes ONE trivial path. It commands no
        # motion: compute_path_to_pose is the PLANNER's action and never
        # reaches the controller.
        if ! python3 "$M5V3/tools/nav_health.py"; then
            refuse "the nav arm came up able to PLAN, and not merely active" \
                "$M5V3/tools/nav_health.py (its refusal is printed above)" \
                "every other check on this stack has passed: all five" \
                "nav children are ALIVE, the localiser underneath is" \
                "healthy, the estimator is sane and the command path is" \
                "one line." \
                "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
                "'$0 stop', then read $LOGDIR/$CFG_NAV_PLANNER_NODE_NAME.log" \
                "and $LOGDIR/$CFG_NAV_LIFECYCLE_NODE_NAME.log."
        fi
    fi

    # F5 TASK 2's SERVER, AFTER THE NAV ARM, AND ONLY UNDER --dock.
    # local_costmap/costmap_raw is a sub-node of controller_server; a
    # docking controller that came up before that topic existed would
    # sit with use_collision_detection true and an empty costmap.
    # Constraint 22: cmd_vel is remapped onto topics.cmd_vel, the same
    # address the controller_server already uses. One goal at a time -
    # dock_bench.py cancels NavigateToPose before DockRobot.
    if [ "$DOCK" = true ]; then
        spawn detdock python3 "$M5V3/nodes/detected_dock.py" --ros-args \
            -p use_sim_time:=true
        spawn docking ros2 run "$CFG_DOCKING_PACKAGE" \
            "$CFG_DOCKING_EXECUTABLE" --ros-args \
            -r __node:="$CFG_DOCKING_NODE_NAME" \
            --params-file "$DOCKING_PARAMS" \
            -p use_sim_time:=true \
            -p dock_database:="$DOCK_DB" \
            -p base_frame:="$CFG_FRAMES_BASE_LINK" \
            -p fixed_frame:="$CFG_FRAMES_ODOM" \
            -r cmd_vel:="$CFG_TOPICS_CMD_VEL" \
            -r detected_dock_pose:="$CFG_TOPICS_DETECTED_DOCK_POSE"

        spawn docklife ros2 run "$CFG_DOCKING_LIFECYCLE_PACKAGE" \
            "$CFG_DOCKING_LIFECYCLE_EXECUTABLE" --ros-args \
            -r __node:="$CFG_DOCKING_LIFECYCLE_NODE_NAME" \
            --params-file "$DOCKING_PARAMS" \
            -p use_sim_time:=true
        sleep "$CFG_TIMING_STARTUP_CHECK_S"
        assert_children_alive
    fi

    echo ""
    if [ "$RF2O" = true ]; then
        echo "up. one truck, one world, two bridges, TWO estimators,"
        echo "    one filter."
    elif [ "$FUSE" = true ]; then
        echo "up. one truck, one world, two bridges, one estimator,"
        echo "    one FACTOR GRAPH - and no ekf_node."
    else
        echo "up. one truck, one world, two bridges, one estimator, one filter."
    fi
    if [ "$LOCALIZE" = true ]; then
        echo "    AND A MAP: this stack knows where it is."
    fi
    if [ "$NAV" = true ]; then
        echo "    AND A PLANNER: this stack decides where it goes."
    fi
    if [ "$SLIPPERY" = true ]; then
        echo "THIS IS THE SLIPPERY PLANT." \
             "slip compliance $CFG_SLIPPERY_SLIP_COMPLIANCE_LATERAL /" \
             "$CFG_SLIPPERY_SLIP_COMPLIANCE_LONGITUDINAL on every wheel,"
        echo "         applied through gz's own wheel_slip service -" \
             "$CFG_VEHICLE_MODEL is untouched."
        echo "         Every session recorded against it is LABELLED" \
             "slippery and must not be"
        echo "         tabled beside a nominal run. EVIDENCE_FUSION.md 8."
    fi
    echo "bridged: $CFG_TOPICS_CLOCK, $CFG_TOPICS_ODOM_GROUND_TRUTH" \
         "(measurement reference ONLY), $CFG_TOPICS_SCAN_NAV," \
         "$CFG_TOPICS_IMU, $CFG_TOPICS_CAM_DEPTH, $CFG_TOPICS_CAM_IMAGE," \
         "$CFG_TOPICS_CAM_INFO," \
         "$CFG_TOPICS_JOINT_STATE, $CFG_TOPICS_DRIVE_SPEED_READ_A"
    echo "gz only: $CFG_TOPICS_POINTS3D and both point clouds - no ROS"
    echo "         consumer yet, and gz renders what is subscribed."
    echo "odom:    $CFG_TOPICS_WHEEL_ODOM - an ESTIMATE, quantised and"
    echo "         1.5 % long by design. It will NOT match the ground"
    echo "         truth and a run where it does is a bug."
    if [ "$FUSE" = true ]; then
        echo "fuse:    THE FACTOR-GRAPH ARM IS ON AND ekf_node IS NOT" \
             "RUNNING."
        echo "         $CFG_TOPICS_FUSE_ODOMETRY_FILTERED at" \
             "${CFG_EKF_FREQUENCY_HZ} Hz, plus the"
        echo "         $CFG_FRAMES_ODOM -> $CFG_FRAMES_BASE_LINK" \
             "transform - which on this arm it OWNS,"
        echo "         because the filter that usually owns it was" \
             "never spawned."
        echo "         The SAME channels the EKF fuses: wheel TWIST" \
             "(vx, vy, vyaw) + IMU"
        echo "         (yaw rate only), off the same two topics." \
             "$CFG_FUSE_PARAMS_FILE says so."
        echo "         A ${CFG_FUSE_LAG_DURATION_S} s window," \
             "re-solved at ${CFG_FUSE_OPTIMIZATION_FREQUENCY_HZ} Hz."
        echo "         NOTHING is published on" \
             "$CFG_TOPICS_ODOMETRY_FILTERED on this arm."
        echo "         THIS IS NOT THE STACK EVIDENCE_FUSION.md 9.3 MEASURED:"
        echo "         every session recorded on it is LABELLED fuse:wheel+imu"
        echo "         and must not be tabled beside a wheel+imu run -"
        echo "         analyse refuses to."
    else
        echo "ekf:     $CFG_TOPICS_ODOMETRY_FILTERED at" \
             "${CFG_EKF_FREQUENCY_HZ} Hz, plus the"
        echo "         $CFG_FRAMES_ODOM -> $CFG_FRAMES_BASE_LINK transform." \
             "Wheel TWIST (vx, vy, vyaw)"
        echo "         + IMU (yaw rate only - the acceleration channel is"
        echo "         refused, EVIDENCE_FUSION.md 9). It reads no pose and"
        echo "         no ground truth. ekf_node is SILENT about an input"
        echo "         that never arrives - check the topic, not the log."
    fi
    if [ "$RF2O" = true ]; then
        echo "rf2o:    THE OPTIONAL LASER-ODOMETRY ARM IS ON." \
             "$CFG_TOPICS_SCAN_NAV ->"
        echo "         $CFG_TOPICS_RF2O_ODOM_RAW -> $CFG_TOPICS_RF2O_ODOM -> the filter's odom1."
        echo "         rf2o publishes NO covariance and a scanner-frame vx;"
        echo "         nodes/rf2o_twist.py puts config.yaml rf2o.covariance on it"
        echo "         and corrects the lever arm. vx and vyaw only - its vy is a"
        echo "         hard-coded 0.0 upstream. $CFG_EKF_RF2O_PARAMS_FILE says so."
        echo "         THIS IS NOT THE STACK EVIDENCE_FUSION.md 9.3 MEASURED:"
        echo "         every session recorded on it is LABELLED wheel+imu+rf2o and"
        echo "         must not be tabled beside a wheel+imu run. analyse refuses to."
    fi
    if [ "$LOCALIZE" = true ]; then
        echo "loc:     THE LOCALISATION ARM IS ON, ON THE" \
             "$(echo "$LOCALIZER" | tr '[:lower:]' '[:upper:]') SIDE."
        if [ "$LOCALIZER" = "$CFG_LOCALIZATION_SLAM_LABEL" ]; then
            echo "         $LOC_NODE ($LOC_PACKAGE $LOC_EXECUTABLE)" \
                 "deserialised the FROZEN POSE"
            echo "         GRAPH" \
                 "$CFG_MAP_DIR/$CFG_MAP_NAME/$CFG_MAP_NAME.posegraph" \
                 "and localises in it, rastering"
            echo "         its own grid onto $CFG_TOPICS_MAP - so there" \
                 "is NO map_server on this arm"
            echo "         and there are EIGHT children, not nine."
            echo "         The graph's and the data's md5s were checked" \
                 "against $CFG_MAP_BUILD_FILE and"
            echo "         the grid's against" \
                 "$CFG_MAP_REGISTRATION_FILE, before anything started."
            echo "         The start pose was passed as the" \
                 "map_start_pose PARAMETER - vehicle.spawn"
            echo "         through that registration. NOTHING was" \
                 "published on $CFG_TOPICS_INITIALPOSE."
        else
            echo "         $CFG_MAP_DIR/$CFG_MAP_NAME served on" \
                 "$CFG_TOPICS_MAP, $LOC_NODE localising in it."
            echo "         The grid's md5 was checked against" \
                 "$CFG_MAP_REGISTRATION_FILE before anything"
            echo "         started. The initial pose was PUBLISHED on" \
                 "$CFG_TOPICS_INITIALPOSE: it is"
            echo "         vehicle.spawn carried through that" \
                 "registration - the measurement harness"
            echo "         standing in for an operator."
        fi
        echo "         Either way it publishes $CFG_FRAMES_MAP ->" \
             "$CFG_FRAMES_ODOM - the ONE edge this"
        echo "         phase adds - and the estimator keeps" \
             "$CFG_FRAMES_ODOM -> $CFG_FRAMES_BASE_LINK."
        echo "         Neither is the other's, and the two localisers" \
             "are NEVER up together."
        echo "         NOT a kidnapped-robot recovery, which neither" \
             "arm does and neither claims."
        echo "         Every session recorded on it is LABELLED" \
             "loc=$LOC_LABEL@... and must not be"
        echo "         tabled beside an unlocalised run OR beside the" \
             "other localiser's -"
        echo "         analyse refuses both."
    fi
    if [ "$NAV" = true ]; then
        echo "nav:     THE NAV ARM IS ON. $CFG_NAV_PLANNER_NODE_NAME" \
             "(SmacPlannerHybrid, REEDS_SHEPP,"
        echo "         a 1.25 m turning radius DERIVED from the plant's" \
             "own worst measured"
        echo "         corner), $CFG_NAV_CONTROLLER_NODE_NAME (MPPI with" \
             "AckermannConstraints),"
        echo "         $CFG_NAV_BT_NODE_NAME on" \
             "$CFG_NAV_BT_XML - a tricycle tree with"
        echo "         NO Spin and NO BackUp - and" \
             "$CFG_NAV_BEHAVIOR_NODE_NAME running only 'wait'."
        echo "         One $CFG_NAV_LIFECYCLE_NODE_NAME drives all four," \
             "with its BOND SWITCHED OFF."
        echo "         Costmaps: global = the FROZEN grid on" \
             "$CFG_TOPICS_MAP, local = a rolling"
        echo "         window on $CFG_TOPICS_SCAN_NAV. Both carry the" \
             "REAL footprint polygon"
        echo "         with the forks, GROWN PER AXIS: +0.54 m along" \
             "track and +0.11 m across"
        echo "         it, which is F3's own measured anisotropy and" \
             "not one number twice."
        echo "         NAV2's FORWARD IS THIS TRUCK's REVERSE (the forks" \
             "are at model -x), and"
        echo "         $CFG_NAV_PARAMS_FILE says so where it reaches a" \
             "parameter."
        echo "         Every session recorded on it is LABELLED nav=on" \
             "and must not be tabled"
        echo "         beside a run with no planner in the room."
        echo "         Send it a goal: python3" \
             "$M5V3/tools/drive_goal.py record --goal $CFG_NAV_DEFAULT_GOAL"
    fi
    echo "navcmd: THE COMMAND PATH IS UP AND IDLE." \
         "$CFG_TOPICS_CMD_VEL -> velocity_smoother"
    if [ "$MONITOR" = true ]; then
    echo "         -> $CFG_TOPICS_CMD_VEL_SMOOTHED ->" \
         "$CFG_MONITOR_NODE_NAME ->"
    echo "         $CFG_TOPICS_CMD_VEL_MONITORED ->" \
         "nodes/cmd_vel_tricycle.py -> the two"
    else
    echo "         -> $CFG_TOPICS_CMD_VEL_SMOOTHED ->" \
         "nodes/cmd_vel_tricycle.py -> the two"
    fi
    echo "         motor terminals, over the bridge. ONE LINE, no bypass," \
         "and no ground"
    echo "         truth in it - the smoother closes its loop on" \
         "$FUSED_TOPIC."
    echo "         NOTHING IS PUBLISHED until a twist arrives, so" \
         "drive_route.py and"
    echo "         slip_bench.sh still own the gz side of those" \
         "terminals. Steer is"
    echo "         ramped at ${CFG_VEHICLE_STEER_RATE_LIMIT_RADPS} rad/s" \
         "and tread at ${CFG_NAVCMD_ACCEL_MPS2} m/s^2;"
    echo "         the curvature ceiling is" \
         "${CFG_NAVCMD_STEER_COMMAND_LIMIT_RAD} rad of steer, MEASURED," \
         "inside the"
    echo "         ${CFG_VEHICLE_STEER_LIMIT_RAD} rad mechanical stop." \
         "Counters: $CFG_TOPICS_NAVCMD_STATUS."
    if [ "$MONITOR" = true ]; then
    echo "guard:  THE COLLISION MONITOR IS IN THAT LINE, and it is NOT a" \
         "safety function."
    echo "         nav2's own words for this node, verbatim: it 'does" \
         "not provide hard"
    echo "         real-time safety certifications'. It does not" \
         "replace a safety-rated"
    echo "         PLC. It complements the F-PLC; it is not the F-PLC." \
         "Protective stop,"
    echo "         e-stop and safe torque off are onboard and hardwired" \
         "in the plant this"
    echo "         models, and nothing on this path can trigger or" \
         "release one."
    echo "         Two velocity-polygon sets - a STOP and a SLOWDOWN -" \
         "off the REAL"
    echo "         footprint hull and the MEASURED stopping distances," \
         "shrinking with the"
    echo "         commanded speed. It sees ONE sensor, the nav lidar at" \
         "z = 1.80 m, so a"
    echo "         pallet, a dropped load and a person are INVISIBLE to" \
         "it. State:"
        echo "         $CFG_TOPICS_COLLISION_MONITOR_STATE. Config:" \
             "$CFG_MONITOR_PARAMS_FILE."
    fi
    if [ "$DOCK" = true ]; then
        echo "dock:    THE DETECTOR IS ON. $CFG_APRILTAG_NODE_NAME on" \
             "$CFG_TOPICS_CAM_IMAGE,"
        echo "         detections on $CFG_TOPICS_APRILTAG_DETECTIONS." \
             "Marker spawned by"
        echo "         furniture.py place, never a world edit." \
             "Score it:"
        echo "         python3 $M5V3/tools/tag_bench.py record"
        echo "         THE DOCKING SERVER IS ON. $CFG_DOCKING_NODE_NAME"
        echo "         publishes into $CFG_TOPICS_CMD_VEL (constraint 22)."
        echo "         Score it: python3 $M5V3/tools/dock_bench.py record"
    fi
    echo "limit:  $CFG_TOPICS_SPEED_LIMIT (nav2_msgs/SpeedLimit) is" \
         "WIRED and DEMONSTRATED."
    echo "         It is an INTERFACE and not a safety claim - the PLC" \
         "that will drive"
    echo "         it arrives in a later phase, nothing on this path" \
         "inhibits motion,"
    echo "         and the collision monitor 'does not provide hard" \
         "real-time safety"
    echo "         certifications' and does not replace a safety-rated" \
         "PLC."
    echo "check:  $0 status"
    echo "rtf:    bash $M5V3/tools/rtf_probe.sh"
    echo "drive:  python3 $M5V3/tools/drive_route.py straight|square|aisle"
    echo "twist:  python3 $M5V3/tools/drive_twist.py record --profile straight"
    echo "logs:   $LOGDIR"
}

# THE GATE THIS TRACK OPENS WITH, AND IT RUNS BEFORE ANYTHING IS STARTED.
# The two exports select Mesa's d3d12 gallium driver and pin it to the
# NVIDIA adapter; without them this WSL renders on llvmpipe and says so.
# The check is not "did the exports get set" - that always succeeds - but
# "does the GL stack now name the GPU", which is the only question worth
# asking, and it is asked with glxinfo because that is the instrument that
# answers it. The whole reply is kept in a log of its own: the renderer
# string is a figure the evidence file quotes.
#
# WHAT glxinfo DOES NOT ANSWER, AND WHY THERE IS NO SECOND GATE HERE.
# glxinfo asks the GLX path. gz renders its sensors through OGRE-Next on
# EGL, and world.log carries two alarming lines on this rig either way -
# "libEGL warning: egl: failed to create dri2 screen" and "NEEDS
# EXTENSION: falling back to kms_swrast". They are a FIRST PROBE failing,
# not the path taken: the engine's own report, GL_RENDERER in
# ~/.gz/rendering/ogre2.log, reads "D3D12 (NVIDIA GeForce RTX 4050 Laptop
# GPU)" for this stack with AND without --headless-rendering (measured,
# EVIDENCE_BRINGUP.md 2). That log is the stronger instrument and it is
# deliberately NOT gated on: it is ONE shared file under $HOME that every
# gz process on the machine truncates and rewrites, so a concurrent m6
# stack would make this check answer about somebody else's renderer. A
# gate that can quietly be about the wrong process is worse than no gate;
# the evidence file reads it by hand, beside a start with nothing else up.
gpu_preflight() {
    export GALLIUM_DRIVER="$CFG_GPU_GALLIUM_DRIVER"
    export MESA_D3D12_DEFAULT_ADAPTER_NAME="$CFG_GPU_D3D12_ADAPTER_NAME"
    command -v glxinfo >/dev/null 2>&1 || refuse \
        "glxinfo is installed" "$0 (gpu_preflight)" \
        "without it there is no way to ask what the GL stack resolved to," \
        "and a run that cannot ask must not assume: apt install mesa-utils"
    # Captured whole and matched afterwards rather than piped into a
    # `grep -q`: an early reader exit turns the writer's SIGPIPE into this
    # pipeline's status under `set -o pipefail`, and a test that fails OPEN
    # is worse here than no test (m6.sh:227-240, measured).
    local info renderer
    info="$(glxinfo -B 2>&1)"
    renderer="$(printf '%s\n' "$info" | sed -n 's/^OpenGL renderer string: //p')"
    { echo "# m5v3 GPU preflight, $(date -Is)"
      echo "# GALLIUM_DRIVER=$GALLIUM_DRIVER"
      echo "# MESA_D3D12_DEFAULT_ADAPTER_NAME=$MESA_D3D12_DEFAULT_ADAPTER_NAME"
      echo "# required renderer substring: $CFG_GPU_REQUIRED_RENDERER"
      echo "# renderer: ${renderer:-<none reported>}"
      echo ""
      printf '%s\n' "$info"; } > "$LOGDIR/gpu_preflight.log"
    [ -n "$renderer" ] || refuse \
        "glxinfo reports a renderer" "$LOGDIR/gpu_preflight.log" \
        "glxinfo -B printed no 'OpenGL renderer string:' line at all;" \
        "the whole reply is in that log - DISPLAY is ${DISPLAY:-unset}"
    case "$renderer" in
        *"$CFG_GPU_REQUIRED_RENDERER"*)
            echo "gpu: $renderer" ;;
        *)
            refuse "the renderer names $CFG_GPU_REQUIRED_RENDERER" \
                "$CONFIG (gpu.required_renderer)" \
                "renderer is: $renderer" \
                "the two exports this check makes are" \
                "  GALLIUM_DRIVER=$CFG_GPU_GALLIUM_DRIVER" \
                "  MESA_D3D12_DEFAULT_ADAPTER_NAME=$CFG_GPU_D3D12_ADAPTER_NAME" \
                "and with them this rig reports D3D12 (NVIDIA ...)." \
                "NOTHING WAS STARTED. Do not work around this by rendering" \
                "on the CPU: llvmpipe measures a different machine." \
                "full glxinfo reply: $LOGDIR/gpu_preflight.log" ;;
    esac
}

# ONE TRUCK, PLACED WHERE THE TABLE SAYS. The quaternion is built from the
# yaw because a pose with a heading has to spawn with it; awk, because the
# shell has no cosine (m6.sh's home() does the same).
spawn_truck() {
    local x="$CFG_VEHICLE_SPAWN_X" y="$CFG_VEHICLE_SPAWN_Y"
    local z="$CFG_VEHICLE_SPAWN_Z" yaw="$CFG_VEHICLE_SPAWN_YAW" qw qz
    qw="$(awk "BEGIN{printf \"%.9f\", cos($yaw/2)}")"
    qz="$(awk "BEGIN{printf \"%.9f\", sin($yaw/2)}")"
    echo "  spawning $CFG_VEHICLE_NAME at ($x, $y, $z) yaw $yaw"
    # THE REPLY IS CAPTURED AND MATCHED, NEVER PIPED INTO A `grep -q`. An
    # early reader exit turns the writer's SIGPIPE into the pipeline's
    # status under `set -o pipefail`, so the test would fail OPEN exactly
    # when the reply is long (m6.sh:227-240, measured). One capture, one
    # log, one match by the shell itself.
    local reply
    reply="$(gz service -s "/world/$CFG_WORLD_NAME/create" \
        --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
        --timeout "$CFG_TIMING_SPAWN_SERVICE_TIMEOUT_MS" \
        --req "sdf_filename: \"$MODEL\", name: \"$CFG_VEHICLE_NAME\", allow_renaming: false, pose: {position: {x: $x, y: $y, z: $z}, orientation: {w: $qw, z: $qz}}" \
        2>&1)"
    { echo "# $(date -Is) create $CFG_VEHICLE_NAME at ($x, $y, $z) yaw $yaw"
      printf '%s\n' "$reply"; } >> "$LOGDIR/spawn.log"
    case "$reply" in
        *"data: true"*) return 0 ;;
    esac
    refuse "the create service accepted the truck" \
        "$LOGDIR/spawn.log (the reply) and $LOGDIR/world.log (the server)" \
        "the service replied: ${reply:-<nothing, it timed out>}" \
        "the world server is STILL UP and this stack is INCOMPLETE:" \
        "run '$0 stop' before trying again."
}

# THE WHEELS THE OVERRIDE APPLIES TO ARE READ OUT OF THE MODEL, and they
# are not listed in config.yaml. model.sdf's WheelSlip plugin is the file
# that decides which links have a slip compliance at all, and a list
# spelled here would be a second opinion about it - the kind that does not
# break, it just quietly stops matching. `<wheel link_name="...">` is the
# plugin's own element and the only place that attribute appears in this
# model, so one sed is the whole reader.
#   ONE NAME PER <wheel> ELEMENT, AND THE TWO COUNTS ARE COMPARED. sed's
#   `.*` is greedy, so two `<wheel>` elements on ONE line would yield one
#   name and the override would quietly reach fewer wheels than the
#   plugin has - and the applied-vs-found check below could not see it,
#   because both sides would be derived from the same short list. So the
#   number of names is checked against the number of `<wheel ` openings
#   in the file, which is a different reading of it.
wheel_links() {
    sed -n 's/.*<wheel link_name="\([^"]*\)".*/\1/p' "$MODEL"
}

wheel_count() {
    grep -c '<wheel ' "$MODEL"
}

# THE SAME THREE COMPLIANCES, ON A FLOOR THAT CANNOT BE GRIPPED.
# gz-sim 8.11's UserCommands system advertises a per-model wheel-slip
# service and this is the whole of --slippery: three calls, one per wheel,
# after the spawn. model.sdf is NOT edited and no variant of it is
# generated - F2 constraint 12's first rung, and it holds.
#
# THE BLOCKING VARIANT IS THE ONE CALLED, and that is what makes the
# reply worth checking. `/world/<w>/wheel_slip` returns as soon as the
# command is QUEUED; `/world/<w>/wheel_slip/blocking` returns after it has
# run inside the simulation loop, so `data: true` means an entity of that
# name was found and its compliances were set. Measured on this rig
# (EVIDENCE_FUSION.md 8.1): a link name the model does not carry comes
# back with NO reply at all and `gz service` still exits 0 - so the test
# is the reply's text and never the exit status.
#
# THE VALUES ARE IN EFFECT SPACE. config.yaml's slippery: block says why
# both keys carry the same number and why the names lie; do not set them
# apart here or anywhere without reading EVIDENCE_LATERAL_TUNE.md 3.1.
apply_slippery() {
    local lat="$CFG_SLIPPERY_SLIP_COMPLIANCE_LATERAL"
    local lon="$CFG_SLIPPERY_SLIP_COMPLIANCE_LONGITUDINAL"
    local links link reply found=0 applied=0
    links="$(wheel_links)"
    [ -n "$links" ] || refuse "the model names the wheels to override" \
        "$MODEL" \
        "no <wheel link_name=\"...\"> element was found in it, so there" \
        "is no gz-sim-wheel-slip-system entry to override and --slippery" \
        "would bring up the NOMINAL plant while saying it was slippery."
    local named opened
    named="$(printf '%s\n' "$links" | wc -l)"
    opened="$(wheel_count)"
    [ "$named" = "$opened" ] || refuse \
        "every <wheel> element in the model yielded a link name" \
        "$MODEL" \
        "the file opens $opened <wheel> element(s) and this script read" \
        "$named link name(s) out of it. The reader takes ONE name per" \
        "LINE; a reformat that put two on one line would silently leave" \
        "a wheel on the nominal plant while 'status' said slippery."
    echo "  slippery: overriding slip compliance to $lat / $lon (EFFECT" \
         "space - config.yaml slippery:)"
    for link in $links; do
        found=$(( found + 1 ))
        reply="$(gz service -s "/world/$CFG_WORLD_NAME/wheel_slip/blocking" \
            --reqtype gz.msgs.WheelSlipParametersCmd \
            --reptype gz.msgs.Boolean \
            --timeout "$CFG_SLIPPERY_SERVICE_TIMEOUT_MS" \
            --req "entity: {name: \"$CFG_VEHICLE_NAME::$link\", type: LINK}, slip_compliance_lateral: $lat, slip_compliance_longitudinal: $lon" \
            2>&1)"
        { echo "# $(date -Is) wheel_slip $CFG_VEHICLE_NAME::$link" \
               "lateral $lat longitudinal $lon"
          printf '%s\n' "$reply"; } >> "$LOGDIR/slippery.log"
        case "$reply" in
            *"data: true"*)
                applied=$(( applied + 1 ))
                echo "    $link  applied" ;;
            *)
                refuse "the wheel_slip service applied the override to $link" \
                    "$LOGDIR/slippery.log (the reply) and $MODEL (the link)" \
                    "the service replied: ${reply:-<nothing at all>}" \
                    "an EMPTY reply is how this service reports an entity" \
                    "it could not find: the command returns false and the" \
                    "client prints no message and still exits 0." \
                    "$applied of $found wheels had been overridden when it" \
                    "failed, so the plant is now HALF slippery and no" \
                    "figure taken on it is a figure about either setting." \
                    "the stack is STILL UP: run '$0 stop' before trying again." ;;
        esac
    done
    # A COUNTED REWRITE, and the count is the model's rather than a
    # number written here: every link the plugin names got a reply that
    # said yes, or the loop above already refused.
    [ "$applied" = "$found" ] || refuse \
        "every wheel the model names was overridden" \
        "$LOGDIR/slippery.log and $MODEL" \
        "the model names $found wheel(s) and $applied were applied."
    echo "  slippery: $applied of $found wheels, from $CONFIG"
}

# WHAT PLANT THIS IS, WRITTEN DOWN WHERE AN INSTRUMENT CAN READ IT.
# After --slippery, `m5v3.sh start` can bring up two different plants from
# one committed model, and the difference does not show in the pidfile,
# the logs, the topic list or the model file. An evidence session recorded
# against the wrong one is not a failed measurement - it is a row that
# looks exactly like a good one, in a table it does not belong in. So the
# answer is written once, here, by the only thing that knows it, and
# tools/sensor_evidence.py's `record` copies it into every session it
# writes and REFUSES if this file is missing.
#   IT IS RUNTIME STATE AND stop DELETES IT, exactly as it does the
#   pidfile. A file left behind by a crash is a file `start` overwrites
#   before anything can read it, because start writes it every time -
#   nominal runs included, and a nominal run that wrote nothing would
#   leave yesterday's slippery answer standing.
#   THE NOMINAL VALUES ARE READ OUT OF THE MODEL, not out of config.yaml:
#   model.sdf's plugin is what the plant actually has when nothing has
#   overridden it, and config.yaml's wheel_slip: block is a copy of it
#   for the shells. `sort -u` collapses the three wheels' entries to the
#   distinct values, so a model that is NOT isotropic shows as two.
write_traction() {
    local lat lon source arm arm_source loc loc_source map_md5
    local nav nav_source monitor monitor_source
    # WHICH ESTIMATOR IS UP, decided before the heredoc rather than
    # inside it: an `echo "$(...)"` with a conditional in it is a line
    # nobody can read and the refusals in this file are not written that
    # way either.
    if [ "$RF2O" = true ]; then
        arm="wheel+imu+rf2o"
        arm_source="$0 --rf2o, $CFG_EKF_PARAMS_FILE +"
        arm_source="$arm_source $CFG_EKF_RF2O_PARAMS_FILE,"
        arm_source="$arm_source rf2o pinned at $CFG_RF2O_COMMIT"
    elif [ "$FUSE" = true ]; then
        # THE ESTIMATOR IS IN FRONT OF THE COLON AND THE CHANNELS ARE
        # BEHIND IT, AND THAT IS WHAT THIS LABEL IS FOR. The two labels
        # that existed before this one - `wheel+imu` and
        # `wheel+imu+rf2o` - both name a SENSOR SET on an estimator that
        # was never in question, because there was only ever one.
        # F2 Task 4 varies the other term: the same three wheel-odometry
        # channels and the same one gyro channel, through a different
        # estimator. So the label says which estimator, then which
        # channels, and `fuse:wheel+imu` beside `wheel+imu` reads as the
        # A/B it is - the same right-hand side, a different left-hand
        # one.
        #   IT IS NOT `wheel+imu+fuse`. That spelling would put the
        #   estimator in the position the other two labels reserve for a
        #   SENSOR, and would read as a stack that fuses the wheels, the
        #   IMU and a third thing called fuse - which is exactly what the
        #   rf2o label DOES mean and this one does not.
        #   NOTHING GREPS IT BY SUBSTRING BY ACCIDENT: `rf2o` does not
        #   occur in it and `fuse` does not occur in either of the other
        #   two, which is what tools/sensor_evidence.py's stream list and
        #   tools/evidence_core.py's fused_topic_key() test on.
        arm="fuse:wheel+imu"
        arm_source="$0 --fuse, $CFG_FUSE_PARAMS_FILE"
        arm_source="$arm_source ($CFG_FUSE_PACKAGE/$CFG_FUSE_EXECUTABLE"
        arm_source="$arm_source vendored at $FUSE_PREFIX),"
        arm_source="$arm_source ekf_node NOT started"
    else
        arm="wheel+imu"
        arm_source="$CFG_EKF_PARAMS_FILE alone (no --rf2o, no --fuse)"
    fi
    # WHICH ABSOLUTE LAYER IS UP, AND IT IS A THIRD LINE BECAUSE IT IS A
    # THIRD QUESTION. traction= says which PLANT, arm= says which
    # ESTIMATOR of the vehicle's own motion, and this says whether
    # anything at all knows where that vehicle IS. All the combinations
    # are legitimate runs and EVIDENCE_LOCALIZATION_V3.md's tables are
    # every one of them read apart.
    #   `none` IS WRITTEN AND NOT LEFT BLANK, which is the whole habit of
    #   this file: an ABSENT line means a stack brought up by a script
    #   that predates this arm, and a stack that ran WITHOUT the arm is a
    #   different fact. tools/sensor_evidence.py refuses to infer either
    #   from the other.
    #   AND THE MAP's md5 IS PART OF THE LABEL. Every absolute figure is
    #   a map pose carried through ONE grid's registration (F3 constraint
    #   16); a session that could not say which grid could be tabled
    #   beside one taken against a rebuild, and nothing in the numbers
    #   would say so. Eight characters, in every session file.
    if [ "$LOCALIZE" = true ]; then
        # THE md5 IS OF THE ARTIFACT **THIS ARM OPENED**, and the two
        # arms open two different files out of one build. nav2_amcl
        # localises in the GRID; slam_toolbox's node deserialises the
        # POSE GRAPH and never reads the grid at all. A label that
        # carried the grid's hash on both arms would be saying, of the
        # slam arm, that a file it never opened had not changed - a true
        # statement about the wrong thing.
        #   IT IS HASHED FROM THE FILE AND NOT COPIED OUT OF A MANIFEST,
        #   on both arms, for check_frozen_map()'s reason: what a session
        #   has to be bound to is what was on disk when it ran.
        #   tools/evidence_core.py's loc_md5_artifact() is where the
        #   ANALYSIS side learns which manifest to check each arm's eight
        #   characters against.
        if [ "$LOCALIZER" = "$CFG_LOCALIZATION_SLAM_LABEL" ]; then
            map_md5="$(md5sum "$MAP_GRAPH.posegraph" | cut -c1-8)"
        else
            map_md5="$(md5sum "$MAP_DIR/$CFG_MAP_NAME.pgm" | cut -c1-8)"
        fi
        loc="$LOC_LABEL@$map_md5"
        loc_source="$0 --localize $LOCALIZER, $LOC_PARAMS,"
        loc_source="$loc_source $CFG_MAP_DIR/$CFG_MAP_NAME"
        loc_source="$loc_source (artifacts verified at bringup),"
        loc_source="$loc_source $CFG_FRAMES_MAP -> $CFG_FRAMES_ODOM owned"
        loc_source="$loc_source by $LOC_NODE"
    else
        loc="none"
        loc_source="no --localize: nothing publishes"
        loc_source="$loc_source $CFG_FRAMES_MAP -> $CFG_FRAMES_ODOM and"
        loc_source="$loc_source this stack has no absolute pose"
    fi
    # WHETHER A PLANNER WAS IN THE ROOM, AND IT IS A FOURTH LINE BECAUSE
    # IT IS A FOURTH QUESTION. traction= says which PLANT, arm= says
    # which ESTIMATOR of the vehicle's own motion, loc= says whether
    # anything knew where that vehicle WAS - and this says whether
    # anything was DECIDING where it went. All four are independent and
    # every combination is a legitimate run.
    #   WHAT IT PREVENTS IS NOT AN ODD-LOOKING ROW. A nav run and a
    #   drive_route run on the same plant, the same estimator and the
    #   same localiser produce CSVs of identical shape off identical
    #   topics: the difference is only that in one of them the twists
    #   came from a controller closing a loop on the localiser's own
    #   output, and in the other from a table. Every figure about the
    #   ESTIMATE is a different measurement in the two cases, because
    #   the second one has a feedback path through the thing being
    #   measured.
    #   IT CARRIES THE PARAMS FILE's md5 FOR THE loc= LABEL'S REASON.
    #   nav2.yaml is where every planned arc and every followed one is
    #   decided; two runs against two versions of it are two different
    #   measurements, and eight characters is what lets an instrument
    #   downstream refuse to table them together. It is hashed off the
    #   file ON DISK at the moment it was used, which is what binds a
    #   session to what actually ran.
    if [ "$NAV" = true ]; then
        nav="on@$(md5sum "$NAV_PARAMS" | cut -c1-8)"
        nav_source="$0 --nav, $CFG_NAV_PARAMS_FILE + $CFG_NAV_BT_XML,"
        nav_source="$nav_source $CFG_NAV_PLANNER_NODE_NAME +"
        nav_source="$nav_source $CFG_NAV_CONTROLLER_NODE_NAME +"
        nav_source="$nav_source $CFG_NAV_BT_NODE_NAME +"
        nav_source="$nav_source $CFG_NAV_BEHAVIOR_NODE_NAME under"
        nav_source="$nav_source $CFG_NAV_LIFECYCLE_NODE_NAME"
    else
        nav="off"
        nav_source="no --nav: nothing plans, nothing follows a path, and"
        nav_source="$nav_source the only thing that has ever published"
        nav_source="$nav_source $CFG_TOPICS_CMD_VEL on this stack is a bench"
    fi
    # WHETHER A GUARD WAS IN THE COMMAND PATH, F4 Task 3, AND IT IS A
    # FIFTH LINE BECAUSE IT IS A FIFTH QUESTION. traction= says which
    # PLANT, arm= which ESTIMATOR, loc= whether anything knew WHERE the
    # vehicle was, nav= whether anything was DECIDING where it went -
    # and this says whether anything could TAKE THE COMMAND AWAY on the
    # way to the terminals.
    #   IT IS NOT COSMETIC AND IT IS NOT A SAFETY CLAIM EITHER. With
    #   --monitor the path from the smoother to the converter runs
    #   through a fourth node that may multiply the twist by a ratio or
    #   replace it with a zero. Two sessions either side of that are two
    #   different command paths producing CSVs of identical shape off
    #   identical topics - which is exactly the failure the other four
    #   labels exist for, one link further down.
    #   IT CARRIES collision_monitor.yaml's md5 FOR nav='s REASON: the
    #   polygons and the actions are decided there, and eight characters
    #   is what lets an instrument refuse to table two of them together.
    if [ "$MONITOR" = true ]; then
        monitor="on@$(md5sum "$MONITOR_PARAMS" | cut -c1-8)"
        monitor_source="$0 --monitor, $CFG_MONITOR_PARAMS_FILE,"
        monitor_source="$monitor_source $CFG_MONITOR_NODE_NAME between"
        monitor_source="$monitor_source $CFG_TOPICS_CMD_VEL_SMOOTHED and"
        monitor_source="$monitor_source $CFG_TOPICS_CMD_VEL_MONITORED,"
        monitor_source="$monitor_source which is what navcmd reads."
        monitor_source="$monitor_source NOT a safety function: nav2's own"
        monitor_source="$monitor_source words are that it does not provide"
        monitor_source="$monitor_source hard real-time safety certifications"
    else
        monitor="off"
        monitor_source="no --monitor: the command path is the three-node"
        monitor_source="$monitor_source line EVIDENCE_NAV_V3.md 3-10"
        monitor_source="$monitor_source measured, with nothing inserted"
        monitor_source="$monitor_source in it"
    fi
    if [ "$DOCK" = true ]; then
        dock="on@$(md5sum "$APRILTAG_PARAMS" | cut -c1-8)"
        dock_source="$0 --dock, $CFG_APRILTAG_PARAMS_FILE,"
        dock_source="$dock_source $CFG_APRILTAG_NODE_NAME on"
        dock_source="$dock_source $CFG_TOPICS_CAM_IMAGE, marker via"
        dock_source="$dock_source furniture.py place (constraint 21)"
        docking="on@$(md5sum "$DOCKING_PARAMS" | cut -c1-8)"
        docking_source="$0 --dock, $CFG_DOCKING_PARAMS_FILE,"
        docking_source="$docking_source $CFG_DOCKING_NODE_NAME on"
        docking_source="$docking_source $CFG_TOPICS_CMD_VEL (constraint 22)"
    else
        dock="off"
        dock_source="no --dock: no marker in the world and no detector"
        docking="off"
        docking_source="no --dock: no opennav_docking server"
    fi
    if [ "$SLIPPERY" = true ]; then
        lat="$CFG_SLIPPERY_SLIP_COMPLIANCE_LATERAL"
        lon="$CFG_SLIPPERY_SLIP_COMPLIANCE_LONGITUDINAL"
        source="$0 --slippery, values from $CONFIG (slippery:), applied to the running plant through gz's wheel_slip service"
    else
        lat="$(sed -n 's:.*<slip_compliance_lateral>\(.*\)</slip_compliance_lateral>.*:\1:p' "$MODEL" | sort -u | paste -sd,)"
        lon="$(sed -n 's:.*<slip_compliance_longitudinal>\(.*\)</slip_compliance_longitudinal>.*:\1:p' "$MODEL" | sort -u | paste -sd,)"
        source="$CFG_VEHICLE_MODEL (no override was applied)"
    fi
    { echo "traction=$([ "$SLIPPERY" = true ] && echo slippery || echo nominal)"
      echo "slip_compliance_lateral=$lat"
      echo "slip_compliance_longitudinal=$lon"
      echo "wheels=$(wheel_links | paste -sd' ')"
      echo "source=$source"
      # WHICH ESTIMATOR IS UP, AND IT IS THE TRACTION LABEL'S ARGUMENT
      # APPLIED TO THE OTHER HALF OF THE STACK (F2 Task 3). --slippery
      # changes the PLANT and this file already said so; --rf2o changes
      # the ESTIMATOR, and a run of one arm sitting in the other's table
      # is the identical failure - a row that looks exactly like a good
      # one. Nothing else can tell them apart afterwards: same model,
      # same floor, same profiles, same CSV columns, and even the fused
      # topic is the same address. So it is written here by the only
      # thing that knows, copied into every session by
      # tools/sensor_evidence.py's `record`, printed by `status`, and
      # `analyse` refuses a set of sessions that mixes the two.
      #   IT IS A SEPARATE LINE FROM traction= BECAUSE IT IS A SEPARATE
      #   QUESTION. The four combinations are all legitimate runs and
      #   EVIDENCE_FUSION.md 10 uses three of them.
      echo "arm=$arm"
      echo "arm_source=$arm_source"
      # F3 TASK 2's LINE. See the block above for why it is separate
      # from arm= and why it carries the map's md5.
      echo "loc=$loc"
      echo "loc_source=$loc_source"
      # F4 TASK 2's LINE. See the block above for why it is separate
      # from loc= and why it carries nav2.yaml's md5.
      echo "nav=$nav"
      echo "nav_source=$nav_source"
      # F4 TASK 3's LINE. See the block above for why it is separate
      # from nav= and why it carries collision_monitor.yaml's md5.
      echo "monitor=$monitor"
      echo "monitor_source=$monitor_source"
      echo "dock=$dock"
      echo "dock_source=$dock_source"
      echo "docking=$docking"
      echo "docking_source=$docking_source"
      # WHERE THIS BRINGUP'S LOGS ARE, so that `status` and `stop` -
      # which run in later processes and cannot know the stamp - name
      # the same files every refusal above named. It is RUNTIME STATE,
      # not configuration, and `stop` deletes it with the rest after
      # reading it.
      echo "log_dir=$LOGDIR"
      echo "partition=$GZ_PARTITION"
      echo "started=$(date -Is)"; } > "$TRACTIONFILE" \
        || refuse "the traction state file is writable" "$CONFIG" \
            "paths.traction_file resolves to $TRACTIONFILE" \
            "without it no recorded session can say which plant it was" \
            "taken on, and an unlabelled session is worse than none."
}

# EVERY CHILD IN ITS OWN SESSION AND ITS OWN LOG.
#   setsid, so the stack outlives the terminal that started it: measured
#   in m6 before it was added, closing that terminal killed five of six
#   children and left gz sim alone in a live simulator, which is the worst
#   partial state there is.
#   The LEADER WRITES ITS OWN PID, because setsid execs in place or FORKS
#   depending on whether its caller already leads a process group, so $!
#   is not reliably the leader.
#   THE NAME IS WRITTEN BESIDE THE PID, which is what lets `status` report
#   a child by the name its log is under instead of as a bare number. It
#   is written by the child itself for the same reason the pid is: one
#   append, one line, in the order the children were started.
spawn() {  # spawn <name> <cmd...>
    local name="$1" pid="" want=$(( $(wc -l < "$PIDFILE") + 1 ))
    shift
    setsid bash -c 'echo "$$ $1" >> "$2"; shift 2; exec "$@"' \
        _ "$name" "$PIDFILE" "$@" > "$LOGDIR/$name.log" 2>&1 &
    # A while loop and not `for _ in {1..N}`: brace expansion happens
    # before parameter expansion, so a count read from config.yaml cannot
    # be spelled that way at all.
    local tries=0
    while [ "$tries" -lt "$CFG_TIMING_PID_WAIT_TRIES" ]; do
        pid="$(sed -n "${want}s/ .*//p" "$PIDFILE")"
        [ -n "$pid" ] && break
        sleep "$CFG_TIMING_PID_WAIT_S"
        tries=$(( tries + 1 ))
    done
    echo "  $name pid ${pid:-UNKNOWN, see $LOGDIR/$name.log}"
}

status() {
    # THE RUNNING STACK'S OWN LOG DIRECTORY, so the paths this prints are
    # the files that stack is actually writing and not the previous
    # bringup's. Read off paths.traction_file, which start wrote.
    adopt_run_log_dir
    echo "m5-ver3: partition $GZ_PARTITION, domain $ROS_DOMAIN_ID"
    echo "pidfile: $PIDFILE"
    echo "logs:    $LOGDIR"
    if [ ! -f "$PIDFILE" ]; then
        echo "not running (no pid file)."
        return 1
    fi
    # WHICH PLANT IS UP, AND IT IS THE FIRST THING AN OPERATOR NEEDS.
    # The slippery stack looks identical to the nominal one from every
    # other angle: same children, same topics, same model file. It is
    # read here with the same key=value grammar
    # tools/sensor_evidence.py's `record` reads it with.
    if [ -f "$TRACTIONFILE" ]; then
        printf '  %-10s %-7s %s\n' "traction" \
            "$(sed -n 's/^traction=//p' "$TRACTIONFILE")" \
            "slip compliance $(sed -n 's/^slip_compliance_lateral=//p' "$TRACTIONFILE") / $(sed -n 's/^slip_compliance_longitudinal=//p' "$TRACTIONFILE") on $(sed -n 's/^wheels=//p' "$TRACTIONFILE")"
        # AND WHICH ESTIMATOR, for the traction line's reason: the two
        # arms are the same six or nine children with the same names, on
        # the same topics, and the fused output is at the same address.
        # An operator who cannot see the arm here would have to read
        # ekf.log to find out which filter they are looking at.
        #   A STATE FILE WRITTEN BEFORE F2 TASK 3 HAS NO arm= LINE, and
        #   it is reported as UNKNOWN rather than as wheel+imu. Every
        #   such stack WAS wheel+imu - --rf2o did not exist - and saying
        #   so here would be inferring the label from an absence, which
        #   is exactly the habit tools/sensor_evidence.py's UNLABELLED
        #   refuses on the same question.
        local arm arm_source loc loc_source nav nav_source
        local monitor monitor_source dock dock_source docking docking_source
        arm="$(sed -n 's/^arm=//p' "$TRACTIONFILE")"
        arm_source="$(sed -n 's/^arm_source=//p' "$TRACTIONFILE")"
        printf '  %-10s %-7s %s\n' "arm" "${arm:-UNKNOWN}" \
            "${arm_source:-no arm= line - this state file predates F2 Task 3}"
        # AND WHICH ABSOLUTE LAYER, for the arm line's reason one level
        # up. A localised stack looks identical to an unlocalised one
        # from every other angle in this report - the same six children
        # are alive under two more, on the same topics - and the ONE
        # difference is an edge on /tf that `status` does not read.
        loc="$(sed -n 's/^loc=//p' "$TRACTIONFILE")"
        loc_source="$(sed -n 's/^loc_source=//p' "$TRACTIONFILE")"
        printf '  %-10s %-7s %s\n' "loc" "${loc:-UNKNOWN}" \
            "${loc_source:-no loc= line - this state file predates F3 Task 2}"
        # AND WHETHER ANYTHING IS DECIDING WHERE IT GOES, for the loc
        # line's reason one layer further up. A nav stack looks
        # identical to a localised one from every other angle in this
        # report - the eleven children are alive under five more, on the
        # same topics - and the difference is a closed loop that
        # `status` cannot see.
        nav="$(sed -n 's/^nav=//p' "$TRACTIONFILE")"
        nav_source="$(sed -n 's/^nav_source=//p' "$TRACTIONFILE")"
        printf '  %-10s %-7s %s\n' "nav" "${nav:-UNKNOWN}" \
            "${nav_source:-no nav= line - this state file predates F4 Task 2}"
        # AND WHETHER ANYTHING CAN TAKE THE COMMAND AWAY, which is the
        # nav line's reason one link down the same path. A --monitor
        # stack has a FOURTH node between the smoother and the converter
        # and looks identical from every other angle in this report:
        # the same children, the same topics, the same terminals - and
        # a twist that may have been multiplied by a ratio or replaced
        # by a zero on its way through.
        monitor="$(sed -n 's/^monitor=//p' "$TRACTIONFILE")"
        monitor_source="$(sed -n 's/^monitor_source=//p' "$TRACTIONFILE")"
        printf '  %-10s %-7s %s\n' "monitor" "${monitor:-UNKNOWN}" \
            "${monitor_source:-no monitor= line - this state file predates F4 Task 3}"
        dock="$(sed -n 's/^dock=//p' "$TRACTIONFILE")"
        dock_source="$(sed -n 's/^dock_source=//p' "$TRACTIONFILE")"
        printf '  %-10s %-7s %s\n' "dock" "${dock:-UNKNOWN}" \
            "${dock_source:-no dock= line - this state file predates F5 Task 1}"
        docking="$(sed -n 's/^docking=//p' "$TRACTIONFILE")"
        docking_source="$(sed -n 's/^docking_source=//p' "$TRACTIONFILE")"
        printf '  %-10s %-7s %s\n' "docking" "${docking:-UNKNOWN}" \
            "${docking_source:-no docking= line - this state file predates F5 Task 2}"
    else
        printf '  %-10s %-7s %s\n' "traction" "UNKNOWN" \
            "no $TRACTIONFILE - this stack was not started by '$0 start'"
        printf '  %-10s %-7s %s\n' "arm" "UNKNOWN" \
            "same file, same reason"
        printf '  %-10s %-7s %s\n' "loc" "UNKNOWN" \
            "same file, same reason"
        printf '  %-10s %-7s %s\n' "nav" "UNKNOWN" \
            "same file, same reason"
        printf '  %-10s %-7s %s\n' "monitor" "UNKNOWN" \
            "same file, same reason"
        printf '  %-10s %-7s %s\n' "dock" "UNKNOWN" \
            "same file, same reason"
        printf '  %-10s %-7s %s\n' "docking" "UNKNOWN" \
            "same file, same reason"
    fi
    local pid name alive=0 dead=0
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        # ours() rather than kill -0: a pid file survives a reboot, Linux
        # recycles pids within minutes of one, and a recycled number can
        # name a stranger. A stranger does not carry this partition.
        if ours "$pid"; then
            printf '  %-10s %-7s pid %-7s %s\n' "$name" "ALIVE" "$pid" \
                "$LOGDIR/$name.log"
            alive=$(( alive + 1 ))
        else
            printf '  %-10s %-7s pid %-7s %s\n' "$name" "DEAD" "$pid" \
                "$LOGDIR/$name.log"
            dead=$(( dead + 1 ))
        fi
    done < "$PIDFILE"
    echo "$alive alive, $dead dead."
    # A stack with a dead child is not a running stack, and the exit
    # status is what a script asking this question reads.
    [ "$dead" = 0 ] && [ "$alive" -gt 0 ]
}

# THIS BRINGUP'S OWN LOG DIRECTORY, MADE AND PRUNED. F4's closing wave.
# Every bringup before this one truncated the last one's logs, and the
# cost is in EVIDENCE_NAV_V3.md 17.3 and 17.4: two runs aborted with
# `error_code 205` and the planner log that would have named the refusal
# had been overwritten before anybody read the evidence.
#   THE PRUNE IS BEFORE THE MAKE, so the count is what config.yaml says
#   AFTER this bringup has its own - `paths.log_keep_runs` minus one
#   survive alongside it. It prunes by NAME, which sorts
#   chronologically because the stamp is %Y%m%d-%H%M%S, and it touches
#   only directories matching `run-*`: `logs/evidence/` is a sibling and
#   is never a candidate, which matters because every recorded session
#   on this track lives there.
open_run_log_dir() {
    local stamp keep victim
    stamp="$(date +%Y%m%d-%H%M%S)"
    keep="$CFG_PATHS_LOG_KEEP_RUNS"
    mkdir -p "$LOGROOT" || refuse "the log directory is writable" "$CONFIG"         "paths.log_dir resolves to $LOGROOT"
    # shellcheck disable=SC2012
    ls -1d "$LOGROOT"/run-* 2>/dev/null | sort | head -n -"$(( keep - 1 ))"         | while read -r victim; do
            case "$victim" in
                "$LOGROOT"/run-*) rm -rf "$victim" ;;
            esac
        done
    LOGDIR="$LOGROOT/run-$stamp"
    mkdir -p "$LOGDIR" || refuse "this bringup's log directory is writable"         "$CONFIG (paths.log_dir)"         "it resolves to $LOGDIR"
    echo "logs:   $LOGDIR (this bringup's own; the last"          "$CFG_PATHS_LOG_KEEP_RUNS are kept)"
}

# AND THE OTHER TWO COMMANDS FIND IT THE WAY THEY FIND THE TRACTION.
# `start` records it in paths.traction_file; this reads it back. A state
# file written before this wave has no `log_dir=` line and LOGDIR stays
# the root, which is exactly where that stack's logs are - `loc=none`'s
# rule, one line over: a missing line is an older script and not a value.
adopt_run_log_dir() {
    local recorded
    [ -f "$TRACTIONFILE" ] || return 0
    recorded="$(sed -n 's/^log_dir=//p' "$TRACTIONFILE")"
    [ -n "$recorded" ] || return 0
    [ -d "$recorded" ] || return 0
    LOGDIR="$recorded"
}

stop() {
    local pid name
    # BEFORE ANYTHING IS DELETED. `stop` removes the traction file at the
    # end, and that file is the only thing that knows which bringup's
    # logs these are.
    adopt_run_log_dir
    # SHUTDOWN ORDER: THE SIMULATOR GOES FIRST, AND stop IS NOT A BRAKE.
    # The model's joint controllers are VELOCITY controllers that hold
    # their last setpoint forever - measured in m6, the truck ran 14.8 m
    # on a standing command after its publisher stopped - so killing this
    # stack cannot slow a moving vehicle. Ending the simulation is the
    # only stop this script owns; the brake is still the e-stop.
    #
    # WHAT IT MAY KILL IS EXACTLY WHAT CARRIES THIS PARTITION. A concurrent
    # m6 stack (partition m6) or step5 demo (m5demo) is nominated by the
    # same patterns and spared by ours(), every time.
    sweep TERM
    if [ -f "$PIDFILE" ]; then
        # ours() before kill, exactly as the sweep does: a recorded pid is
        # a number on disk, not a promise. The residual purpose of this
        # loop survives that check - a recorded process matching no PATTERN
        # (a setsid wrapper whose exec failed) still carries the partition.
        while read -r pid name; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            ours "$pid" && kill "$pid" 2>/dev/null && echo "  killed $pid ($name)"
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    else
        echo "nothing to stop."
    fi
    # THE TRACTION STATE GOES WITH THE STACK IT DESCRIBED. Left behind it
    # would answer for the NEXT stack, and the next stack may be the other
    # plant - so `status` would name a traction nothing is running on and
    # `record` would stamp it onto a session it has nothing to do with.
    # It is removed whether or not there was a pidfile, because a crash
    # leaves one without the other.
    rm -f "$TRACTIONFILE"
    # Past the grace, nothing is exiting on its own.
    sleep "$CFG_TIMING_STOP_GRACE_S"
    sweep KILL
    echo "down."
    # AND THE LOGS STAY, WHICH IS THE POINT OF THE DIRECTORY. `stop`
    # deletes the pidfile and the traction file and nothing else; the
    # children's logs are the record of what this bringup did and the
    # NEXT bringup no longer truncates them.
    if [ "$LOGDIR" != "$LOGROOT" ] && [ -d "$LOGDIR" ]; then
        echo "logs kept: $LOGDIR"
    fi
}

USAGE="usage: $0 start [--headless] [--slippery] [--rf2o|--fuse] [--localize [amcl|slam]] [--nav] [--monitor] [--dock] | stop | status
  start       GPU preflight, then warehouse_ver3 + one forklift_ver3 in a
              Gazebo window, plus TWO ros_gz bridges: the parameter bridge
              for the clock, the ground-truth odometry (a measurement
              reference, never an input), the nav lidar, the IMU, the
              pallet camera's camera_info and the two joint channels the
              wheel odometry consumes, and the image bridge for that
              camera's depth image. Then the wheel odometry node itself,
              publishing /m5v3/wheel_odom, the static base_link -> imu_link
              transform the filter needs before it will fuse the IMU, and
              robot_localization's ekf_node, publishing
              /m5v3/odometry/filtered and odom -> base_link. Then THE
              COMMAND PATH, which is not behind a flag and is one line
              with no bypass: nav2's velocity smoother on /cmd_vel and
              nodes/cmd_vel_tricycle.py converting its output onto the
              model's two motor terminals. Both are IDLE until something
              publishes a twist - nothing is written to either terminal
              until then, so tools/drive_route.py and tools/slip_bench.sh
              still own the gz side of them.
              NINE processes with a window, eight without.
              The 3D lidar and both point clouds stay on the gz side.
              It refuses outright if the renderer is not the NVIDIA GPU.
  --headless  no Gazebo window. Use it for anything being MEASURED.
  --slippery  THE WET PATCH. After the truck is spawned, override every
              wheel's slip compliance to config.yaml's slippery: values
              through gz-sim's own wheel_slip service - the committed
              model.sdf is not touched and no variant of it is written.
              It is a DIFFERENT PLANT: the tyre creeps, the wheel
              odometry's distance goes badly long, and 'status' and every
              recorded evidence session say so by name. Do not mix its
              runs with nominal ones in one table; 'analyse' refuses to.
  --rf2o      THE OPTIONAL LASER-ODOMETRY ARM. Three more children - the
              nav lidar's static transform, rf2o_laser_odometry_node
              matching consecutive scans, and the relay that puts a
              MEASURED covariance on its twist and corrects the lever arm
              upstream does not - and a second --params-file giving the
              filter an odom1 it fuses vx and vyaw from. It is a
              DIFFERENT ESTIMATOR on the same plant, exactly as
              --slippery is the same estimator on a different plant, and
              'status' and every recorded session say which by name;
              'analyse' refuses a set that mixes the two arms.
              Build it first: bash tools/install_rf2o.sh
              TEN processes with a window, nine without.
  --fuse      THE OPTIONAL FACTOR-GRAPH ARM, AND IT REPLACES THE FILTER.
              fuse's fixed-lag smoother goes up INSTEAD of ekf_node -
              same two input topics, same three wheel-odometry channels,
              same one gyro channel, same output rate - keeping every
              measurement in a sliding window as a factor in a graph and
              re-solving the whole window on every pass. It publishes
              its own odom -> base_link, which is why the two are never
              up together. MUTUALLY EXCLUSIVE with --rf2o, refused by
              name. Same child count as the default stack, with 'fuse'
              where 'ekf' was, and 'status' and every recorded session
              say fuse:wheel+imu by name.
              Vendor it first: bash tools/install_fuse.sh
  --localize [amcl|slam]
              THE OPTIONAL LOCALISATION ARM, AND THE FIRST THING ON THIS
              TRACK THAT KNOWS WHERE THE VEHICLE IS. Whichever localiser
              is named becomes the SOLE publisher of map -> odom on top
              of the odom -> base_link the estimator already owns -
              exactly ONE new edge - and the two are NEVER up together.
              The value is optional; config.yaml's
              localization.default_arm says which it means without one,
              and a value naming neither arm is refused by name.
                amcl  (the default) nav2's map_server serves the FROZEN
                      GRID in maps/warehouse_v3 and nav2_amcl localises
                      in it. THREE more children - the nav lidar's
                      static transform, map_server, amcl - and four
                      lifecycle transitions this script drives itself.
                      Seeded by a MESSAGE on /initialpose.
                slam  slam_toolbox's localization_slam_toolbox_node
                      deserialises the FROZEN POSE GRAPH and localises
                      in it, rastering its own grid onto /map - so there
                      is no map_server and there are TWO more children,
                      with two lifecycle transitions. Seeded by the
                      map_start_pose PARAMETER, on its command line.
              Either way the artifacts that arm opens are md5-checked
              before anything starts - the grid against the committed
              registration, the pose graph against build.txt: a rebuilt
              map is a new artifact, never an overwrite - and a gate
              refuses a localiser that came up merely alive.
              It combines with all three flags above - it adds a LAYER
              where they change the plant, the sensors or the estimator
              - and 'status' and every recorded session say
              loc=<localiser>@<artifact md5> by name; 'analyse' refuses
              a set that mixes a localised run with an unlocalised one,
              and one that mixes the two localisers.
              TEN processes with a window and nine without on the amcl
              arm, nine and eight on the slam one - and with --rf2o as
              well, three more of each.
  --nav       THE NAV ARM, AND THE FIRST THING HERE THAT DECIDES WHERE
              THE VEHICLE GOES. Five more children: nav2's planner
              (SmacPlannerHybrid, REEDS_SHEPP, a turning radius DERIVED
              from the worst corner this plant actually delivered),
              controller (MPPI with AckermannConstraints), BT navigator
              on a TRICYCLE TREE with no Spin and no BackUp, behaviour
              server running only 'wait', and ONE lifecycle manager for
              the four of them - the only one on this track, with its
              bond switched off at both ends. Costmaps: global = the
              frozen grid the --localize arm is already serving, local =
              a rolling window on the nav lidar, both carrying the REAL
              footprint polygon with the forks.
              IT REQUIRES --localize AND IS REFUSED WITHOUT IT BY NAME:
              the global costmap's frame is map, and its activation
              BLOCKS until map -> base_link resolves, which nothing
              publishes without a localiser.
              It adds a PUBLISHER to the top of the command path that is
              already there on every bringup - no node is inserted into
              that line and nothing about it changes.
              'status' and every recorded session say nav=on@<md5> by
              name; 'analyse' refuses a set that mixes a planned run
              with an unplanned one.
              SEVENTEEN processes with a window and SIXTEEN without, on
              the amcl arm.
  --monitor   THE COLLISION MONITOR, AND IT IS A LINK IN THE COMMAND
              PATH RATHER THAN A LAYER OVER IT. One more child:
              nav2_collision_monitor between the velocity smoother and
              the tricycle converter, with the converter's input
              remapped onto its output - so with the flag the line is
              smoother -> collision_monitor -> converter -> terminals,
              and without it the converter reads the smoother directly
              and NOTHING about the path changes.
              Two VELOCITY POLYGON sets, a stop and a slowdown, sized
              off the REAL footprint hull and the MEASURED stopping
              distances (1.05 m from 0.700 m/s, 0.25 m from the 0.300
              m/s transit ceiling) and switching between the two as the
              commanded speed does. It sees ONE sensor, the nav lidar at
              z = 1.80 m, so a pallet, a dropped load and a person are
              all invisible to it: its honest scope is structure above
              1.80 m.
              IT IS NOT A SAFETY FUNCTION. nav2's own words, verbatim:
              it 'does not provide hard real-time safety
              certifications'. It
              does not replace a safety-rated PLC. It complements the
              F-PLC; it is not the F-PLC. Protective stop, e-stop and
              safe torque off are onboard and hardwired, and nothing on
              this path can trigger or release one.
              It depends on no other flag and combines with all of
              them. 'status' and every recorded session say
              monitor=on@<md5> by name; a session recorded through the
              longer path must not be tabled beside one recorded
              through the shorter.
  --dock      THE DETECTOR, THE STATION MARKER AND THE DOCKING SERVER,
              F5 TASK 1+2. Spawns tag36h11_0 via furniture.py place
              (constraint 21), vendored apriltag_node on the colour
              stream, detected_dock.py (TF → PoseStamped) and
              opennav_docking with SimpleNonChargingDock. ITS cmd_vel
              IS REMAPPED onto topics.cmd_vel (constraint 22).
              IT REQUIRES --nav AND IS REFUSED WITHOUT IT BY NAME.
              'status' says dock=on@<apriltag.yaml md5> and
              docking=on@<docking.yaml md5>.
              Score detection: python3 tools/tag_bench.py record
              Score the dock:  python3 tools/dock_bench.py record
  status      every child by name, ALIVE or DEAD, with its log, which
              traction the running plant is on, which estimator arm,
              which absolute layer, whether anything is planning, and
              whether anything can take the command away
  stop        end this partition's stack and nothing else"
case "${1:-}" in
    start|--start)
        shift
        # THE FLAGS MAY COME IN ANY ORDER, and an unrecognised word is a
        # REFUSAL and not a shrug: the one it will be is a misspelt
        # --headless, --slippery, --rf2o, --fuse, --localize or --nav,
        # and silently opening a window for someone who asked for none -
        # or bringing up the DRY plant for someone who asked for the wet
        # one, the two-sensor filter for someone measuring the
        # three-sensor one, an UNLOCALISED stack for someone about to
        # record absolute figures off it, or a stack with NO PLANNER for
        # someone about to send it a goal - is what this loop exists to
        # prevent.
        #   THERE ARE SIX FLAGS AND EXACTLY TWO RELATIONS BETWEEN THEM.
        #   --headless is about drawing, --slippery is about the PLANT
        #   and --localize adds a LAYER above the estimator, so each of
        #   those combines with anything; --rf2o and --fuse are both
        #   about the ESTIMATOR ITSELF and are refused TOGETHER below;
        #   and --nav REQUIRES --localize, which is refused inside
        #   start() where config.yaml has been read and the message can
        #   name the frames.
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --headless) GUI=false ;;
                --slippery) SLIPPERY=true ;;
                --rf2o) RF2O=true ;;
                --fuse) FUSE=true ;;
                # THE ONE FLAG THAT TAKES A VALUE, AND THE VALUE IS
                # OPTIONAL. `--localize`, `--localize amcl` and
                # `--localize slam` are all legal; the first two are the
                # same command. The next word is taken ONLY if it is not
                # another flag and not the end of the line, so
                # `--localize --headless` still means the default arm
                # with no window rather than an arm called `--headless`.
                #   THE VALUE IS NOT VALIDATED HERE. configure() has to
                #   have read config.yaml before this script knows what
                #   the arms are called or which is the default, and the
                #   refusal has to be able to name both - so it lives
                #   there, still before the GPU preflight and still
                #   before any child.
                --localize)
                    LOCALIZE=true
                    case "${2:-}" in
                        ""|--*) ;;
                        *) LOCALIZER="$2"; shift ;;
                    esac ;;
                # THE ONE FLAG THAT DEPENDS ON ANOTHER. It takes no
                # value; what it needs is --localize, and that is
                # refused inside start() rather than here, for the
                # --localize value's reason: the refusal quotes
                # config.yaml's frame names and the config has to have
                # been READ before it can be spoken. Nothing has been
                # started by that line either way.
                --nav) NAV=true ;;
                # AND THE ONE THAT DEPENDS ON NOTHING. --monitor works
                # on every arm this script has, including the bare
                # stack: the node it starts needs a scan and a twist and
                # neither is behind a flag.
                --monitor) MONITOR=true ;;
                --dock) DOCK=true ;;
                *) echo "$USAGE"; exit 2 ;;
            esac
            shift
        done
        # ONE ESTIMATOR ARM AT A TIME, AND THE COMBINATION IS REFUSED BY
        # NAME RATHER THAN RESOLVED BY PRECEDENCE. Three reasons, any one
        # of them sufficient:
        #   THE TF EDGE. Both arms publish odom -> base_link and tf2 has
        #   no notion of two authorities for one edge - every listener
        #   simply reads whichever arrived last. That is not a
        #   three-sensor estimate, it is a coin toss at 50 Hz.
        #   THE OVERLAY. --rf2o's second --params-file is a
        #   robot_localization parameter file. fuse's node cannot read
        #   one, so `--rf2o --fuse` could only ever mean "start the
        #   factor graph and silently drop the laser odometry", which is
        #   a run that would record itself under a label naming a sensor
        #   it never fused.
        #   THE LABEL. There is ONE arm= line and a set of sessions has
        #   to be uniform in it. A third combination would need a third
        #   label, a column in every table in EVIDENCE_FUSION.md 10 and
        #   11, and a measurement - which is a task and not a flag.
        # IT CALLS configure() AND THEN REFUSES, and the order is on
        # purpose rather than an oversight: the refusal below quotes
        # $CONFIG and the two frame names, so the config has to have been
        # READ before it can be spoken. What has NOT happened by that
        # line is the part that matters - configure() only loads
        # config.yaml and derives paths, so no GPU preflight, no ROS
        # source, no pidfile, no state file and NO CHILD has been
        # started. The refusal is still "nothing was started"; it is not
        # "nothing was read".
        if [ "$RF2O" = true ] && [ "$FUSE" = true ]; then
            configure
            refuse "exactly one estimator arm was asked for" \
                "$0 (the start flags) and $CONFIG (fuse:, rf2o:)" \
                "--rf2o and --fuse are both ESTIMATOR flags and they are" \
                "alternatives, not layers. --rf2o adds a third SENSOR to" \
                "robot_localization's filter; --fuse replaces that filter" \
                "with a factor graph. Together they would put two" \
                "publishers on $CFG_FRAMES_ODOM -> $CFG_FRAMES_BASE_LINK," \
                "and tf2 would carry whichever arrived last." \
                "NOTHING WAS STARTED. Pick one:" \
                "  $0 start --headless --rf2o     # the laser-odometry arm" \
                "  $0 start --headless --fuse     # the factor-graph arm" \
                "(--slippery and --headless combine with either.)"
        fi
        configure; start ;;
    stop|--stop)     configure; stop ;;
    status|--status) configure; status ;;
    *) echo "$USAGE"; exit 2 ;;
esac
