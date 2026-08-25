#!/usr/bin/env bash
# m5v3.sh - bring the m5-ver3 plant up and down: ONE world, ONE truck,
# ONE bridge, and a GPU the run has proved it is using.
#   start [--headless] | stop | status
#
# WHAT THIS TRACK IS. m5-ver3 is the sensor-fusion rebuild of the SHOWCASE
# vehicle (vault AMR-DEC-003): one forklift, real instrument profiles, a
# fusion estimate scored against ground truth. It forks m6's fleet plant
# back down to a single truck and shares its floor. See CONTEXT.md.
#
# WHAT IT IS NOT. There is no broker, no fleet manager, no HMI and no PLC
# link here, and their absence is the phase rather than an omission: Task 1
# is plant plus sensors, and a process started for the shape of the thing
# would be a claim this run does not make. Nothing here touches PLCSIM
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

# THIS SCRIPT'S OWN REQUIRED KEYS, on top of the isolation and ROS ones
# _common.sh checks for every script on this track. Each is refused by its
# DOTTED name if the file has been reorganised under it.
# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS=(
    gpu.gallium_driver gpu.d3d12_adapter_name gpu.required_renderer
    world.file world.name
    vehicle.model vehicle.name
    vehicle.spawn.x vehicle.spawn.y vehicle.spawn.z vehicle.spawn.yaw
    topics.clock topics.odom_ground_truth topics.scan_nav topics.gui_gate
    topics.imu topics.cam_depth topics.cam_info topics.points3d
    paths.log_dir paths.pidfile
    timing.world_load_s timing.settle_s timing.startup_check_s
    timing.stop_grace_s timing.gui_gate_poll_s timing.gui_gate_settle_s
    timing.spawn_service_timeout_ms timing.pid_wait_tries timing.pid_wait_s
)

# The shared read, plus the four paths only this script derives from it.
configure() {
    load_config "${REQUIRED_KEYS[@]}"
    PIDFILE="$REPO/$CFG_PATHS_PIDFILE"
    LOGDIR="$REPO/$CFG_PATHS_LOG_DIR"
    WORLD="$REPO/$CFG_WORLD_FILE"
    MODEL="$REPO/$CFG_VEHICLE_MODEL"
}

# The stack as command-line patterns, and the list is short because the
# stack is: the server, the GUI client and the two bridges. A pattern only
# NOMINATES - ours() decides - and `gz sim` is FIRST because that is where
# the motion lives (see stop()).
#   `gz sim` NOMINATES THE CLIENT AND THE SERVER ALIKE: both command lines
#   begin with those two words, and the gated wrapper that becomes the
#   client carries them in its -c string until it execs.
#   image_bridge IS A SEPARATE PATTERN and not covered by the one above
#   it: ros_gz's depth-image bridge is its own executable with its own
#   name, and `parameter_bridge` does not match it.
#   MAINTENANCE OBLIGATION: a process added to start() must be added here,
#   or stop orphans it and still prints "down."
PATTERNS=("gz sim" "parameter_bridge" "image_bridge")

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

    # THE BRIDGES AFTER THE TRUCK, because all but one of their topics are
    # the truck's and a bridge opened over topics that do not exist yet
    # spends its first seconds advertising nothing.
    #   WHAT IS CARRIED AND WHAT IS NOT. The clock, the ground-truth
    #   odometry (a measurement reference, never an input), the nav lidar,
    #   the IMU and the pallet camera's depth image plus its camera_info.
    #   NOT the 3D lidar and NOT either point cloud: their ROS consumers
    #   arrive in F2, and gz renders a sensor only while something
    #   subscribes to it, so bridging early would cost the RTF every
    #   figure on this track is measured against and buy nothing
    #   (docs/reports/m5v3-03 5, ros_gz issue #368).
    spawn bridge ros2 run ros_gz_bridge parameter_bridge \
        "$CFG_TOPICS_CLOCK@rosgraph_msgs/msg/Clock[gz.msgs.Clock" \
        "$CFG_TOPICS_ODOM_GROUND_TRUTH@nav_msgs/msg/Odometry[gz.msgs.Odometry" \
        "$CFG_TOPICS_SCAN_NAV@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan" \
        "$CFG_TOPICS_IMU@sensor_msgs/msg/Imu[gz.msgs.IMU" \
        "$CFG_TOPICS_CAM_INFO@sensor_msgs/msg/CameraInfo[gz.msgs.CameraInfo"

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

    # THE GUI CLIENT LAST AND GATED, or the lidar fans anchor at the world
    # origin for the life of the window. Measured in m6 on gz-sim 8.11.0:
    # GuiRunner discards every world-state message that arrives before its
    # initial snapshot is processed, and the SensorTopic components the
    # VisualizeLidar plugin anchors on are created a beat AFTER the spawn.
    # Waiting for a scanner topic to be advertised on the gz side puts
    # those components inside the snapshot a late client receives in full.
    # config.yaml's topics.gui_gate is that topic and is deliberately NOT
    # bridged: the gate is a gz-side question.
    if [ "$GUI" = true ]; then
        spawn gui bash -c "until gz topic -l 2>/dev/null \
            | grep -qF '$CFG_TOPICS_GUI_GATE'; \
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
    echo "up. one truck, one world, two bridges."
    echo "bridged: $CFG_TOPICS_CLOCK, $CFG_TOPICS_ODOM_GROUND_TRUTH" \
         "(measurement reference ONLY), $CFG_TOPICS_SCAN_NAV," \
         "$CFG_TOPICS_IMU, $CFG_TOPICS_CAM_DEPTH, $CFG_TOPICS_CAM_INFO"
    echo "gz only: $CFG_TOPICS_POINTS3D and both point clouds - no ROS"
    echo "         consumer until F2, and gz renders what is subscribed."
    echo "check:  $0 status"
    echo "rtf:    bash $M5V3/tools/rtf_probe.sh"
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
    # Past the grace, nothing is exiting on its own.
    sleep "$CFG_TIMING_STOP_GRACE_S"
    sweep KILL
    echo "down."
}

USAGE="usage: $0 start [--headless] | stop | status
  start       GPU preflight, then warehouse_ver3 + one forklift_ver3 in a
              Gazebo window, plus TWO ros_gz bridges: the parameter bridge
              for the clock, the ground-truth odometry (a measurement
              reference, never an input), the nav lidar, the IMU and the
              pallet camera's camera_info, and the image bridge for that
              camera's depth image. Four processes.
              The 3D lidar and both point clouds stay on the gz side.
              It refuses outright if the renderer is not the NVIDIA GPU.
  --headless  no Gazebo window. Use it for anything being MEASURED.
  status      every child by name, ALIVE or DEAD, with its log
  stop        end this partition's stack and nothing else"
case "${1:-}" in
    start|--start)
        case "${2:-}" in
            --headless) GUI=false ;;
            # An unrecognised second word is a REFUSAL and not a shrug: the
            # one it will be is a misspelt --headless, and silently opening
            # a window for someone who asked for none is what this branch
            # exists to prevent.
            "") ;;
            *) echo "$USAGE"; exit 2 ;;
        esac
        configure; start ;;
    stop|--stop)     configure; stop ;;
    status|--status) configure; status ;;
    *) echo "$USAGE"; exit 2 ;;
esac
