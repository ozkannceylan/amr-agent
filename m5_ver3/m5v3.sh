#!/usr/bin/env bash
# m5v3.sh - bring the m5-ver3 plant up and down: ONE world, ONE truck,
# ONE bridge, ONE estimator, and a GPU the run has proved it is using.
#   start [--headless] [--slippery] | stop | status
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
# does not make. There is no MAP and no localisation here - the EKF's
# world frame is the odom frame, so it publishes odom -> base_link and
# never map -> odom, and that edge is F3's. Nothing here touches PLCSIM
# Advanced or anything on the Windows side.
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

# THIS SCRIPT'S OWN REQUIRED KEYS, on top of the isolation and ROS ones
# _common.sh checks for every script on this track. Each is refused by its
# DOTTED name if the file has been reorganised under it.
# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS=(
    gpu.gallium_driver gpu.d3d12_adapter_name gpu.required_renderer
    world.file world.name
    vehicle.model vehicle.name
    vehicle.spawn.x vehicle.spawn.y vehicle.spawn.z vehicle.spawn.yaw
    vehicle.imu_mount.x vehicle.imu_mount.y vehicle.imu_mount.z
    topics.clock topics.odom_ground_truth topics.scan_nav
    topics.safety_scan_back
    topics.imu topics.cam_depth topics.cam_info topics.points3d
    topics.joint_state topics.drive_speed_read_a topics.wheel_odom
    topics.odometry_filtered
    frames.odom frames.base_link frames.imu frames.map
    ekf.params_file ekf.node_name ekf.frequency_hz
    slippery.slip_compliance_lateral slippery.slip_compliance_longitudinal
    slippery.service_timeout_ms
    paths.log_dir paths.pidfile paths.traction_file
    timing.world_load_s timing.settle_s timing.startup_check_s
    timing.stop_grace_s timing.gui_gate_poll_s timing.gui_gate_settle_s
    timing.spawn_service_timeout_ms timing.pid_wait_tries timing.pid_wait_s
)

# The shared read, plus the four paths only this script derives from it.
configure() {
    load_config "${REQUIRED_KEYS[@]}"
    PIDFILE="$REPO/$CFG_PATHS_PIDFILE"
    TRACTIONFILE="$REPO/$CFG_PATHS_TRACTION_FILE"
    LOGDIR="$REPO/$CFG_PATHS_LOG_DIR"
    WORLD="$REPO/$CFG_WORLD_FILE"
    MODEL="$REPO/$CFG_VEHICLE_MODEL"
    EKF_PARAMS="$REPO/$CFG_EKF_PARAMS_FILE"
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
    # AND THE FILE HAS TO BE ADDRESSED TO THE NODE THIS SCRIPT STARTS.
    # A ROS parameter file is keyed by the node's name, and rclcpp does
    # NOT complain about a block addressed to somebody else - it applies
    # nothing and starts. That failure is worse than a missing file,
    # because the `-p` overrides below still land: the topics, the frames
    # and the rate are all set, so ekf_node comes up on its PACKAGE
    # DEFAULTS, subscribes nothing, fuses nothing, and publishes 50 Hz of
    # a pose that never moves and an identity transform. `status` says
    # ALIVE, the topic is there at its configured rate, the evidence
    # recorder's stream arrives - EVERY instrument this track named would
    # report a healthy stack. A misspelt key INSIDE the file is the same
    # failure by another route, and rclcpp is equally silent about it.
    #   SO THE COUPLING IS CHECKED AND NOT WRITTEN DOWN. ekf.yaml's header
    #   carried this as a MAINTENANCE OBLIGATION in prose, which is the
    #   one form of guarantee this track accepts nowhere else: the
    #   imu_mount copy is diffed against the model that decides it, every
    #   config key is checked by its dotted name, the child list lives in
    #   one file. This is that idiom, one grep, before anything starts.
    grep -q "^${CFG_EKF_NODE_NAME}:" "$EKF_PARAMS" || refuse \
        "the EKF parameter file is addressed to $CFG_EKF_NODE_NAME" \
        "$EKF_PARAMS and $CONFIG (ekf.node_name)" \
        "there is no top-level '$CFG_EKF_NODE_NAME:' key in that file, so" \
        "every parameter in it belongs to a node that is never started." \
        "ekf_node would come up on its PACKAGE DEFAULTS with the topic," \
        "frame and rate overrides still applied: 50 Hz of a pose that" \
        "never moves, an identity transform, and 'status' ALIVE." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$EKF_PARAMS" || echo '(none)')"
    # Unchecked, an unwritable log dir fails every redirection this stack
    # opens and start would sleep its way to "up." over a stack that never
    # began.
    mkdir -p "$LOGDIR" || refuse "the log directory is writable" "$CONFIG" \
        "paths.log_dir resolves to $LOGDIR"

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
        "$CFG_TOPICS_DRIVE_SPEED_READ_A@sensor_msgs/msg/JointState[gz.msgs.Model"

    # THE DEPTH IMAGE GOES THROUGH A SECOND, DIFFERENT BRIDGE, and that is
    # ros_gz's design rather than this script's choice: parameter_bridge
    # carries an Image as a plain topic, image_bridge carries it through
    # image_transport, which is what every ROS image consumer expects to
    # find. camera_info stays on the parameter bridge above because
    # image_bridge does not carry it.
    #   IT IS ONE PROCESS FOR ONE TOPIC, and that is the honest shape: a
    #   second image would be a second argument, and the colour image has
    #   no consumer on this track.
    spawn imgbridge ros2 run ros_gz_image image_bridge "$CFG_TOPICS_CAM_DEPTH"

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
    # and forward acceleration, and owns odom -> base_link.
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
    spawn ekf ros2 run robot_localization ekf_node --ros-args \
        -r __node:="$CFG_EKF_NODE_NAME" \
        --params-file "$EKF_PARAMS" \
        -p use_sim_time:=true \
        -p frequency:="$CFG_EKF_FREQUENCY_HZ" \
        -p map_frame:="$CFG_FRAMES_MAP" \
        -p odom_frame:="$CFG_FRAMES_ODOM" \
        -p base_link_frame:="$CFG_FRAMES_BASE_LINK" \
        -p world_frame:="$CFG_FRAMES_ODOM" \
        -p odom0:="$CFG_TOPICS_WHEEL_ODOM" \
        -p imu0:="$CFG_TOPICS_IMU" \
        -r /odometry/filtered:="$CFG_TOPICS_ODOMETRY_FILTERED"

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
    # A DEAD CHILD IS A REFUSAL AND NOT A WARNING. This block used to print
    # "THE STACK IS INCOMPLETE" and then fall through to "up." and exit 0,
    # so an operator's `start && ...` - and any script reading the status -
    # saw a successful bringup over a stack that was missing a process.
    # Whatever survived is STILL RUNNING, and the message has to say so,
    # because the operator's next command is stop and not start.
    local dead="" logs="" n
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        ours "$pid" || dead="$dead${dead:+ }$name"
    done < "$PIDFILE"
    if [ -n "$dead" ]; then
        for n in $dead; do logs="$logs${logs:+, }$LOGDIR/$n.log"; done
        refuse "every child is alive ${CFG_TIMING_STARTUP_CHECK_S}s after the last spawn" \
            "$logs" \
            "these children exited during startup: $dead" \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
            "read the log named above, then '$0 stop' before trying again."
    fi

    echo ""
    echo "up. one truck, one world, two bridges, one estimator, one filter."
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
         "$CFG_TOPICS_IMU, $CFG_TOPICS_CAM_DEPTH, $CFG_TOPICS_CAM_INFO," \
         "$CFG_TOPICS_JOINT_STATE, $CFG_TOPICS_DRIVE_SPEED_READ_A"
    echo "gz only: $CFG_TOPICS_POINTS3D and both point clouds - no ROS"
    echo "         consumer yet, and gz renders what is subscribed."
    echo "odom:    $CFG_TOPICS_WHEEL_ODOM - an ESTIMATE, quantised and"
    echo "         1.5 % long by design. It will NOT match the ground"
    echo "         truth and a run where it does is a bug."
    echo "ekf:     $CFG_TOPICS_ODOMETRY_FILTERED at" \
         "${CFG_EKF_FREQUENCY_HZ} Hz, plus the"
    echo "         $CFG_FRAMES_ODOM -> $CFG_FRAMES_BASE_LINK transform." \
         "Wheel TWIST (vx, vy, vyaw)"
    echo "         + IMU (yaw rate, ax). It reads no pose and no ground"
    echo "         truth. ekf_node is SILENT about an input that never"
    echo "         arrives - check the topic, not the log."
    echo "check:  $0 status"
    echo "rtf:    bash $M5V3/tools/rtf_probe.sh"
    echo "drive:  python3 $M5V3/tools/drive_route.py straight|square|aisle"
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
    local lat lon source
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
    else
        printf '  %-10s %-7s %s\n' "traction" "UNKNOWN" \
            "no $TRACTIONFILE - this stack was not started by '$0 start'"
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

stop() {
    local pid name
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
}

USAGE="usage: $0 start [--headless] [--slippery] | stop | status
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
              /m5v3/odometry/filtered and odom -> base_link.
              SEVEN processes with a window, six without.
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
  status      every child by name, ALIVE or DEAD, with its log, and which
              traction the running plant is on
  stop        end this partition's stack and nothing else"
case "${1:-}" in
    start|--start)
        shift
        # THE TWO FLAGS ARE INDEPENDENT AND MAY COME IN EITHER ORDER, and
        # an unrecognised word is a REFUSAL and not a shrug: the one it
        # will be is a misspelt --headless or --slippery, and silently
        # opening a window for someone who asked for none - or bringing
        # up the DRY plant for someone who asked for the wet one - is
        # what this loop exists to prevent.
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --headless) GUI=false ;;
                --slippery) SLIPPERY=true ;;
                *) echo "$USAGE"; exit 2 ;;
            esac
            shift
        done
        configure; start ;;
    stop|--stop)     configure; stop ;;
    status|--status) configure; status ;;
    *) echo "$USAGE"; exit 2 ;;
esac
