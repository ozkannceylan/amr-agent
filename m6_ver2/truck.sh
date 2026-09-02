#!/usr/bin/env bash
# truck.sh - ONE truck's ROS stack, in a world somebody else owns.
#   bash m6_ver2/truck.sh <vid> start [--monitor] | stop | status
#
# WHAT THIS IS. m5_ver3/m5v3.sh brings up a plant AND a stack: a gz
# server, a bridge, a map_server, one truck's estimator, localiser and
# navigator, all in a partition of its own. m6-ver2 splits that in two
# along the line SPEC_NAMESPACING.md 4 draws. The PLANT has one owner -
# m6_ver2/world.launch.py, driven by m6_ver2/m6v2.sh: the server, the
# four model spawns, ONE union bridge, ONE shared map_server and the
# fleet's per-truck io/contactor pair. This script owns the other half,
# four times over: the ROS stack that sits on top of one truck.
#
# SO IT STARTS NO SIMULATOR, NO BRIDGE AND NO MAP SERVER, and it
# REFUSES BY NAME when they are not already there (check_world). A
# per-truck bridge would be a second publisher on /clock and on this
# truck's gz topics; a per-truck map_server would be a second latched
# copy of one frozen grid that could only differ by mistake.
#
# ---- THE THREE THINGS THAT MAKE FOUR OF THESE COEXIST ----
#
# 1. EVERY CHILD IS NAMESPACED. `--ros-args -r __ns:=/<vid>` goes on
#    every spawn line, uniformly, and it is the only mechanism that
#    renames nav2's COSTMAP SUB-NODES - which have no command line at
#    all, so `-r __node:=` cannot reach them. Four un-namespaced
#    controller servers would create four nodes named
#    /local_costmap/local_costmap (SPEC_NAMESPACING.md 1).
# 2. THE FRAMES CARRY THE TRUCK AND THE TREE IS SHARED. `-r tf:=/tf
#    -r tf_static:=/tf_static` rides beside the namespace on every line,
#    because a namespaced node publishes on /<vid>/tf otherwise and the
#    four trees would never meet. The frames are `<vid>/odom`,
#    `<vid>/base_link`, `<vid>/<sensor>_link` and ONE shared `map`, so
#    four AMCLs own four DISJOINT edges under one parent
#    (SPEC_NAMESPACING.md 2, AMR-DEC-006).
# 3. THE REMAP MATCH SIDES ARE RELATIVE. m5v3.sh writes
#    `-r /cmd_vel:=...`, `-r /cmd_vel_smoothed:=...`,
#    `-r /odometry/filtered:=...` - absolute match sides, which under a
#    namespace MATCH NOTHING AND FIRE NEVER. The node then keeps its
#    default topic and the failure is silent: a smoother subscribed to
#    /f1/cmd_vel by luck, a controller publishing where nobody listens.
#    Every match side below is relative for that reason and
#    tests/test_truck_sh.py pins it against this file's own source.
#
# ---- WHAT DOES NOT PORT: navcmd (AMR-DEC-006) ----
# m5v3's nodes/cmd_vel_tricycle.py publishes the gz actuator terminals
# DIRECTLY, which bypasses cmd_mux, cmd_gate and sto_contactor - the
# thing m6 forbids. Its ARITHMETIC ports, as an import, into
# nav2_adapter/nav2_cmd.py; its SHELL does not port at all. The chain is
#   nav2 controller -> /<vid>/cmd_vel -> smoother -> /<vid>/cmd_vel_smoothed
#     -> nav2_adapter_node -> /<vid>/auto/cmd_vel -> cmd_mux -> cmd_gate
#       -> forklift_io -> sto_contactor -> the terminals
# and the single-writer rule stays where the contactor is.
#
# IT ORCHESTRATES PROCESSES AND HOLDS NO LOGIC OF ITS OWN. Every
# constant it obeys is in m6_ver2/vehicles/<vid>/config.yaml - a counted
# rewrite of m5_ver3/config.yaml, built by tools/instantiate_truck.py -
# and every child writes its own log under paths.log_dir, by name, so a
# bringup that goes wrong is READ rather than guessed at.
set -uo pipefail

# ---------------------------- THE ARGUMENTS ----------------------------
# THE VID COMES FIRST AND IT IS NOT A FLAG. Four copies of this script
# run at once and every refusal, every log path and every swept pid is
# scoped by it, so it is read before anything else is - including the
# refusal voice, which speaks under this truck's name.
VID="${1:-}"
CMD="${2:-}"
shift 2 2>/dev/null || true

USAGE="usage: bash m6_ver2/truck.sh <vid> start [--monitor] | stop | status
  <vid>       f1 | f2 | f3 | f4 - the fleet table's own ids
              (m6/ipc/status_contract.py VEHICLES)
  start       this truck's ROS stack, in a world that is ALREADY UP:
              the two static mounts, the wheel odometry, the EKF, the
              velocity smoother, the self-mask scan filter, AMCL, the
              four nav2 servers with their lifecycle manager, and the
              nav2 adapter that presents m6's /auto contract on top.
              It refuses by name if the world, the bridge or /map are
              not there - m6_ver2/m6v2.sh owns those.
  --monitor   ARM nav2_collision_monitor between the smoother and the
              adapter. Not a safety function (nav2's own words) and not
              a replacement for the F-PLC; it is a guard, and it changes
              what is being measured, so it is labelled in the state
              file and reported by 'status'.
  stop        this truck ONLY. The world stays up and so do the other
              three trucks - the sweep requires BOTH this partition and
              this truck's id in a candidate's environment.
  status      what is up, under which arm, with which log directory."

case "$CMD" in
    start|stop|status) ;;
    *) echo "$USAGE" >&2; exit 2 ;;
esac
case "$VID" in
    f[1-9]|f[1-9][0-9]) ;;
    *) echo "truck.sh: '$VID' is not a vehicle id." >&2
       echo "$USAGE" >&2; exit 2 ;;
esac

MONITOR=false
for arg in "$@"; do
    case "$arg" in
        --monitor) MONITOR=true ;;
        *) echo "truck.sh: unknown option '$arg'" >&2
           echo "$USAGE" >&2; exit 2 ;;
    esac
done

# THE REFUSAL VOICE CARRIES THE TRUCK. With four of these running, a
# refusal that said only "m6v2" would leave the operator reading four
# terminals to find out which one said no.
TOOL="truck.sh:$VID"
_HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
. "$_HERE/tools/_truck_common.sh"

# ------------------------ EVERY KEY THIS READS ------------------------
# MAINTENANCE OBLIGATION, m5_ver3/tools/_common.sh's: a key read below
# is a key listed here, or a reorganised config reaches the first spawn
# with an empty string on its command line instead of being refused by
# its dotted name before anything starts.
REQUIRED_KEYS=(
    vehicle.imu_mount.x vehicle.imu_mount.y vehicle.imu_mount.z
    vehicle.nav_lidar_mount.x vehicle.nav_lidar_mount.y
    vehicle.nav_lidar_mount.z
    frames.map frames.odom frames.base_link frames.imu frames.nav_lidar
    topics.clock topics.scan_nav topics.imu topics.joint_state
    topics.drive_speed_read_a topics.wheel_odom topics.odometry_filtered
    topics.cmd_vel topics.cmd_vel_smoothed topics.cmd_vel_monitored
    topics.collision_monitor_state topics.speed_limit
    topics.map topics.tf topics.tf_static
    ekf.params_file ekf.node_name ekf.frequency_hz
    smoother.package smoother.executable smoother.node_name
    smoother.params_file smoother.active_timeout_s
    monitor.package monitor.executable monitor.node_name
    monitor.params_file monitor.active_timeout_s
    localization.amcl.params_file localization.amcl.package
    localization.amcl.executable localization.amcl.node_name
    localization.lifecycle_timeout_s
    nav.params_file nav.bt_xml nav.bt_xml_rpp nav.bt_xml_station
    nav.costmap_sections
    nav.planner.package nav.planner.executable nav.planner.node_name
    nav.controller.package nav.controller.executable
    nav.controller.node_name
    nav.behavior.package nav.behavior.executable nav.behavior.node_name
    nav.bt.package nav.bt.executable nav.bt.node_name
    nav.lifecycle.package nav.lifecycle.executable
    nav.lifecycle.node_name nav.health.timeout_s
    bt_direction.workspace bt_direction.package bt_direction.library
    bt_direction.source_dir
    paths.log_dir paths.pidfile paths.traction_file
    timing.world_load_s timing.startup_check_s
    timing.stop_grace_s timing.pid_wait_tries timing.pid_wait_s
)

# The shared read, plus the paths and the one address only this script
# derives from it.
configure() {
    truck_config "$VID" "${REQUIRED_KEYS[@]}"
    PIDFILE="$M6V2_REPO/$CFG_PATHS_PIDFILE"
    STATEFILE="$M6V2_REPO/$CFG_PATHS_TRACTION_FILE"
    LOGROOT="$M6V2_REPO/$CFG_PATHS_LOG_DIR"
    LOGDIR="$LOGROOT"
    EKF_PARAMS="$M6V2_REPO/$CFG_EKF_PARAMS_FILE"
    SMOOTHER_PARAMS="$M6V2_REPO/$CFG_SMOOTHER_PARAMS_FILE"
    MONITOR_PARAMS="$M6V2_REPO/$CFG_MONITOR_PARAMS_FILE"
    LOC_PARAMS="$M6V2_REPO/$CFG_LOCALIZATION_AMCL_PARAMS_FILE"
    NAV_PARAMS="$M6V2_REPO/$CFG_NAV_PARAMS_FILE"
    # THE TREES ARE ABSOLUTE PATHS AND THAT IS NOT COSMETIC (m5v3.sh's
    # note): bt_navigator resolves `default_nav_to_pose_bt_xml` against
    # the PROCESS's working directory, and a tree it cannot open is a
    # navigator that silently falls back to nav2's own - which has Spin
    # and BackUp in it.
    NAV_BT="$M6V2_REPO/$CFG_NAV_BT_XML"
    NAV_BT_RPP="$M6V2_REPO/$CFG_NAV_BT_XML_RPP"
    # THE THIRD TREE, AND THIS SCRIPT NEVER PASSES IT ANYWHERE. It is
    # the RPP tree with its FollowPath naming the 0.25 m
    # `station_goal_checker` instead of the 0.60 m one, and it is
    # reached ONLY through the `behavior_tree` field of a
    # NavigateToPose goal - which the adapter fills from
    # nav2_legs.CLASS_TREE. It is checked for HERE because a missing
    # tree is a goal bt_navigator cannot open forty metres into a
    # drive, reported to the operator as a nav fault.
    NAV_BT_STATION="$M6V2_REPO/$CFG_NAV_BT_XML_STATION"
    # THE SIX SECTIONS nav2.yaml HAS TO BE ADDRESSED TO. Four are the
    # servers this script starts; two are the costmap SUB-NODES those
    # servers construct, which have no process, are never named by
    # `status` and are never swept - and which come up on the package
    # defaults, in silence, if their block is addressed to nobody.
    NAV_SECTIONS="$CFG_NAV_PLANNER_NODE_NAME $CFG_NAV_CONTROLLER_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_BEHAVIOR_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_BT_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_LIFECYCLE_NODE_NAME"
    NAV_SECTIONS="$NAV_SECTIONS $CFG_NAV_COSTMAP_SECTIONS"
    # THE SIX LIFECYCLE NODES THE NAV GATE WAITS FOR. The two costmaps
    # are lifecycle nodes of their own INSIDE their servers, so a nav
    # arm can have four ACTIVE processes and two costmaps that never
    # transitioned.
    NAV_LIFECYCLE_NODES="$CFG_NAV_PLANNER_NODE_NAME"
    NAV_LIFECYCLE_NODES="$NAV_LIFECYCLE_NODES $CFG_NAV_CONTROLLER_NODE_NAME"
    NAV_LIFECYCLE_NODES="$NAV_LIFECYCLE_NODES $CFG_NAV_BEHAVIOR_NODE_NAME"
    NAV_LIFECYCLE_NODES="$NAV_LIFECYCLE_NODES $CFG_NAV_BT_NODE_NAME"
    NAV_LIFECYCLE_NODES="$NAV_LIFECYCLE_NODES local_costmap/local_costmap"
    NAV_LIFECYCLE_NODES="$NAV_LIFECYCLE_NODES global_costmap/global_costmap"
    # THE DSP PLUGIN'S BUILD TREE, WHICH IS THE ONE PATH OUTSIDE THE
    # REPOSITORY. bt_navigator resolves nav2.yaml's
    # `m5v3_direction_stable_bt_node` with BT::SharedLibrary - a plain
    # dlopen off the LOADER PATH with no ament index in it - so
    # tools/install_bt_direction.sh's workspace has to be on that ONE
    # child's LD_LIBRARY_PATH. The three lines are m5_ver3/tools/
    # _common.sh's btdir_paths()/btdir_env(), and they are CALLED there
    # rather than copied: _truck_common.sh sources that file.
    #   THE .so IS SHARED READ-ONLY BY ALL FOUR TRUCKS and is neither
    #   copied nor rewritten - four bt_navigators dlopen one library
    #   (SPEC_NAMESPACING.md 3).
    btdir_paths
    # THE ONE ADDRESS THAT IS NOT IN config.yaml, AND IT IS ASKED FOR
    # RATHER THAN SPELLED. Both costmaps' obstacle layers read the
    # MASKED scan (SPEC_ADAPTER.md A-T2) and that address is a FILE
    # literal in nav2.yaml, written by the derivation - costmaps are
    # sub-nodes, so no `-p` can reach them. tools/instantiate_truck.py
    # is the one place it is spelled; this asks that module for it and
    # check_address() below proves the derived file agrees. A second
    # copy here would be the copy that kept working after the first
    # one changed.
    MASKED_SCAN="$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
import instantiate_truck
print(instantiate_truck.masked_scan_topic(sys.argv[2]))' \
        "$M6V2/tools" "$VID" 2>/dev/null)"
    [ -n "$MASKED_SCAN" ] || refuse \
        "the derivation tool names the masked scan topic" \
        "m6_ver2/tools/instantiate_truck.py (masked_scan_topic)" \
        "python3 could not be asked, or the function is gone." \
        "That address is the ONE thing the costmaps, AMCL and the mask" \
        "node have to agree about, and it has no home in config.yaml:" \
        "nav2's costmaps are SUB-NODES with no command line." \
        "NOTHING WAS STARTED."
    # THE FRAME THE ESTIMATE IS STAMPED WITH, AND IT IS PASSED RATHER
    # THAN DEFAULTED. nav2_pose.odometry_rows refuses to invent a frame
    # name - "the world frame's name is a deployment fact" - and this
    # script is the deployment. The name is model.sdf's own
    # <odom_frame>, rewritten per truck by the derivation
    # (SPEC_NAMESPACING.md 2's table, model.sdf:2226), so the ESTIMATE
    # on /<vid>/est/odom and the ground truth on /<vid>/gz/odom carry
    # the same frame - which is what lets a reader put them in one plot
    # without asking whether they are in one frame.
    #   IT IS NOT ON /tf AND IT IS NOT SUPPOSED TO BE. m6 world
    #   coordinates are the fleet layer's, not tf2's; nothing looks this
    #   frame up, and a consumer that did would be reaching for a
    #   transform this branch deliberately does not publish.
    WORLD_FRAME="$VID/forklift/odom"
    # THE THREE REMAPS EVERY CHILD GETS, in one array so no spawn line
    # can be written without them. See this file's header, points 1-2.
    NS=(--ros-args -r "__ns:=/$VID"
        -r "tf:=$CFG_TOPICS_TF" -r "tf_static:=$CFG_TOPICS_TF_STATIC")
}

# ---------------------------- THE CHECKS ----------------------------
#
# ONE ADDRESS IN A PARAMETER FILE, COMPARED WITH THE ONE THIS SCRIPT
# PASSES. Ported from m5v3.sh's check_address() with its argument
# unchanged - "config.yaml owns every address on this track and this
# file has a copy" - and it is ported rather than sourced because it
# lives in m5v3.sh, which is a program and not a library. Provenance:
# m5_ver3/m5v3.sh check_address().
check_address() {  # check_address <file> <key> <want> <owner> <line>...
    local file="$1" key="$2" want="$3" owner="$4" found other
    shift 4
    found="$(grep -nE "^[[:space:]]*${key}:[[:space:]]" "$file" || true)"
    [ -n "$found" ] || refuse \
        "$(basename "$file") sets $key" "$file and $owner" \
        "there is no '$key:' line in that file at all, so the package" \
        "default is in force and nothing downstream would say so." \
        "$@" \
        "NOTHING WAS STARTED."
    other="$(printf '%s\n' "$found" \
             | grep -vE ":[[:space:]]*${key}:[[:space:]]+\"?${want}\"?[[:space:]]*(#.*)?$" \
             || true)"
    [ -z "$other" ] || refuse \
        "$(basename "$file")'s $key is the address this script passes" \
        "$file ($key) and $owner" \
        "this script says '$want' and these lines say something else:" \
        "$other" \
        "$@" \
        "A DERIVED FILE THAT HAS GONE STALE LOOKS EXACTLY LIKE A FRESH" \
        "ONE. Re-derive it:" \
        "  python3 m6_ver2/tools/instantiate_truck.py --vid $VID" \
        "NOTHING WAS STARTED."
}

# A WRAPPED PARAMETER FILE IS ADDRESSED TO <vid>: AND THEN TO ITS NODES,
# AND BOTH HALVES HAVE TO BE TRUE.
#
# WHY IT IS CHECKED AND NOT WRITTEN DOWN (m5v3.sh's check_ekf_params,
# generalised). rclcpp does NOT complain about a block addressed to
# somebody else: it applies nothing and starts. On this branch the
# failure has a SECOND door, and it is the one the namespacing opened.
# A bare top-level `controller_server:` key addresses only the
# ROOT-NAMESPACE node; handed to /f1/controller_server it contributes
# nothing and the server comes up on nav2's PACKAGE DEFAULTS with this
# script's `-p` overrides still applied - a DiffDrive controller on a
# tricycle, or a costmap with a 0.10 m circular footprint that reports
# every path through every rack as clear. That is why the derivation
# indents each file under `<vid>:` (nav2's own RewrittenYaml root_key
# transform), and this is the check that it did.
check_wrapped_params() {  # check_wrapped_params <file> <what> <node>...
    local file="$1" what="$2" node
    shift 2
    grep -q "^${VID}:" "$file" || refuse \
        "$(basename "$file") is wrapped under '$VID:'" \
        "$file and m6_ver2/tools/instantiate_truck.py (SPEC_NAMESPACING.md 1)" \
        "there is no top-level '$VID:' key, so every block in that file" \
        "is addressed to a ROOT-NAMESPACE node - and every node this" \
        "script starts lives under /$VID. rclcpp applies nothing and" \
        "reports nothing: $what would come up on PACKAGE DEFAULTS with" \
        "this script's -p overrides still applied." \
        "the top-level keys that file does define:" \
        "$(grep '^[A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')" \
        "re-derive it: python3 m6_ver2/tools/instantiate_truck.py --vid $VID" \
        "NOTHING WAS STARTED."
    for node in "$@"; do
        grep -q "^  ${node}:" "$file" || refuse \
            "$(basename "$file") is addressed to $node" \
            "$file and $CONFIG" \
            "there is a '$VID:' wrap but no '  $node:' key under it, so" \
            "/$VID/$node is configured by nobody." \
            "the second-level keys that file does define:" \
            "$(grep '^  [A-Za-z_][A-Za-z0-9_]*:' "$file" || echo '(none)')" \
            "NOTHING WAS STARTED."
    done
}

# HOW MANY PUBLISHERS A TOPIC HAS, or 0. `ros2 topic info` is used
# rather than `ros2 topic list` because a NAME on the graph is not a
# publication: a subscriber alone puts the name in the list, and the
# whole question here is whether somebody is FEEDING this truck.
topic_publishers() {  # topic_publishers <topic>
    ros2 topic info "$1" 2>/dev/null \
        | sed -n 's/^Publisher count: //p' | head -1
}

# ---- THE WORLD IS SOMEBODY ELSE'S AND IT HAS TO BE THERE ALREADY ----
#
# THE FAILURE THIS PREVENTS IS SLOW AND SILENT, WHICH IS WHY IT IS A
# GATE AND NOT A WARNING. With no /map latched, AMCL's on_activate
# BLOCKS - it waits for a map on the transient-local topic - and the
# lifecycle drive below spends its whole budget on a node that is
# perfectly alive. With no bridge, the wheel odometry subscribes a topic
# nobody publishes and the EKF has no odom0 at all: every child ALIVE,
# every log clean, and the first anybody hears of it is a filter that
# never moves. So this asks, by name, before anything is started.
check_world() {
    local topic n deadline started=false
    deadline=$(( $(date +%s) + CFG_TIMING_WORLD_LOAD_S ))
    for topic in "$CFG_TOPICS_CLOCK" "$CFG_TOPICS_MAP" \
                 "$CFG_TOPICS_SCAN_NAV" "$CFG_TOPICS_IMU" \
                 "$CFG_TOPICS_JOINT_STATE" "$CFG_TOPICS_DRIVE_SPEED_READ_A"; do
        n="$(topic_publishers "$topic")"
        while [ -z "$n" ] || [ "$n" = "0" ]; do
            [ "$(date +%s)" -lt "$deadline" ] || refuse \
                "the world this truck runs in is already up" \
                "m6_ver2/m6v2.sh and m6_ver2/world.launch.py (SPEC_NAMESPACING.md 4)" \
                "$topic has no publisher on domain $ROS_DOMAIN_ID after" \
                "${CFG_TIMING_WORLD_LOAD_S}s (config.yaml timing.world_load_s)." \
                "THE PLANT HAS ONE OWNER AND IT IS NOT THIS SCRIPT: the" \
                "gz server, the four model spawns, the ONE union bridge" \
                "and the ONE shared map_server are the world launch's," \
                "because a per-truck bridge is a second publisher on" \
                "/clock and a per-truck map_server is a second copy of" \
                "one frozen grid." \
                "  bash m6_ver2/m6v2.sh start      # then this script" \
                "NOTHING WAS STARTED."
            sleep 1
            n="$(topic_publishers "$topic")"
            started=true
        done
    done
    [ "$started" = true ] && echo "  world: waited for the plant"
    echo "  world: /map and this truck's five bridged channels are live"
}

# ---- EVERY CHILD IN THE PIDFILE, STILL RUNNING ----
# A DEAD CHILD IS A REFUSAL AND NOT A WARNING (m5v3.sh's rule): a
# `start && ...` that saw exit 0 over a stack missing a process is worse
# than a stop. It is a function because the nav arm's five children go
# up after the first call and the same question has to be asked again.
#   IT ASKS child_alive AND NOT truck_ours, and the two are different
#   questions - see _truck_common.sh's note over child_alive for the
#   torn /proc environ read that made the ownership predicate answer
#   "no" about four running children on the four-truck bringup this
#   check exists to protect.
assert_children_alive() {
    local pid name dead="" logs="" n
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        child_alive "$pid" || dead="$dead${dead:+ }$name"
    done < "$PIDFILE"
    [ -n "$dead" ] || return 0
    for n in $dead; do logs="$logs${logs:+, }$LOGDIR/$n.log"; done
    refuse "every child is alive ${CFG_TIMING_STARTUP_CHECK_S}s after the last spawn" \
        "$logs" \
        "these children of truck $VID exited during startup: $dead" \
        "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
        "read the log named above, then 'bash $0 $VID stop'."
}

# ---- DRIVING A LIFECYCLE NODE TO ACTIVE, NAMESPACED ----
# Ported from m5v3.sh's localize_lifecycle() with its argument intact:
# THE TARGET IS A STATE AND NOT A SEQUENCE OF COMMANDS. A request to
# CONFIGURE is a claim about the current state and a request to be
# ACTIVE is not, so this drives what it finds - UNCONFIGURED gets a
# configure, INACTIVE gets an activate, ACTIVE is done - and refuses by
# the node's LAST STATE, which is the thing an operator needs and an
# exit code never carried.
#   THE ADDRESS IS `/<vid>/<node>` AND THAT IS THE WHOLE NAMESPACING
#   CHANGE. `ros2 lifecycle get /amcl` on this branch names nobody, and
#   a loop that polled it would time out against a node that reached
#   ACTIVE ten seconds in.
drive_lifecycle() {  # drive_lifecycle <node> <budget> <log> <line>...
    local node="$1" budget="$2" log="$3" deadline state=""
    shift 3
    deadline=$(( $(date +%s) + budget ))
    until ros2 node list 2>/dev/null | grep -q "^/$VID/$node$"; do
        [ "$(date +%s)" -lt "$deadline" ] || refuse \
            "/$VID/$node appeared inside ${budget}s" "$log" \
            "nothing by that name is on domain $ROS_DOMAIN_ID." \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
        sleep 1
    done
    until [ "$state" = active ]; do
        state="$(ros2 lifecycle get "/$VID/$node" 2>/dev/null | cut -d' ' -f1)"
        case "$state" in
            unconfigured) ros2 lifecycle set "/$VID/$node" configure \
                              >> "$log" 2>&1 || true ;;
            inactive)     ros2 lifecycle set "/$VID/$node" activate \
                              >> "$log" 2>&1 || true ;;
            active)       break ;;
            *)            ;;
        esac
        [ "$(date +%s)" -lt "$deadline" ] || refuse \
            "/$VID/$node reached ACTIVE inside ${budget}s" "$log" \
            "it is in state '${state:-unreadable}' and this script has" \
            "been driving it towards active for the whole budget." \
            "LEFT SHORT OF ACTIVE A NAV2 LIFECYCLE NODE SUBSCRIBES TO" \
            "NOTHING, ADVERTISES NOTHING AND PUBLISHES NO TRANSFORM," \
            "while logging nothing that reads as an error - and" \
            "'status' reads ALIVE." \
            "$@" \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
        sleep 1
    done
    echo "  /$VID/$node active"
}

# ---- A NODE THAT REACHES ACTIVE ON ITS OWN, WATCHED ----
# m5v3.sh's autostart_active(), namespaced. It is a POLL and not a
# DRIVE, which is a different thing rather than a copy of one: the
# smoother and the collision monitor take `autostart_node` and their
# params files set it, so a node sitting in UNCONFIGURED here means that
# parameter DID NOT REACH IT - which on this branch is what a params
# file that lost its `<vid>:` wrap looks like from the outside.
autostart_active() {  # autostart_active <node> <budget> <log> <params> <line>...
    local node="$1" budget="$2" log="$3" params="$4" deadline state=""
    shift 4
    deadline=$(( $(date +%s) + budget ))
    until [ "$state" = active ]; do
        state="$(ros2 lifecycle get "/$VID/$node" 2>/dev/null | cut -d' ' -f1)"
        [ "$state" = active ] && break
        [ "$(date +%s)" -lt "$deadline" ] || refuse \
            "/$VID/$node reached ACTIVE on its own inside ${budget}s" \
            "$log and $params" \
            "it is in state '${state:-unreadable}' and NOTHING IS" \
            "DRIVING IT - that file sets autostart_node and this script" \
            "only watches. A state of 'unconfigured' therefore means the" \
            "parameter did not reach the node, which is what a" \
            "--params-file addressed to the wrong node - or wrapped" \
            "under the wrong vid - looks like from the outside." \
            "$@" \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
        sleep 1
    done
    echo "  /$VID/$node active"
}

# ---- CAN THE NAV ARM ANSWER, OR IS IT MERELY ACTIVE? ----
#
# SIX LIFECYCLE NODES AND ONE ACTION SERVER. Four of the six are the
# servers this script started; TWO are the costmaps INSIDE them, which
# have no process at all - so five ALIVE processes and a `status` that
# says so is satisfied by a nav arm whose global costmap never
# transitioned.
#   AND IT IS STILL NOT THE WHOLE QUESTION. Six ACTIVE nodes and an
#   advertised action say nothing about whether the planner has a
#   COSTMAP to plan in: a global costmap whose static layer never
#   received the frozen grid is wall-to-wall NO_INFORMATION, and with
#   allow_unknown:false it refuses every goal, once, into its own log.
#   nav_can_plan() below asks that, and it asks it AFTER this - an
#   action that is not advertised yet would make a plan gate time out
#   over a stack that was merely slow.
nav_can_answer() {
    local node deadline action="/$VID/navigate_to_pose"
    for node in $NAV_LIFECYCLE_NODES; do
        deadline=$(( $(date +%s) + CFG_NAV_HEALTH_TIMEOUT_S ))
        until [ "$(ros2 lifecycle get "/$VID/$node" 2>/dev/null \
                   | cut -d' ' -f1)" = active ]; do
            [ "$(date +%s)" -lt "$deadline" ] || refuse \
                "/$VID/$node is ACTIVE" \
                "$LOGDIR/$CFG_NAV_LIFECYCLE_NODE_NAME.log (config.yaml nav.health.timeout_s)" \
                "the lifecycle manager has had ${CFG_NAV_HEALTH_TIMEOUT_S}s" \
                "and this node is not active." \
                "THE TWO COSTMAPS ARE LIFECYCLE NODES INSIDE THEIR" \
                "SERVERS: they have no process, 'status' never names" \
                "them, and Costmap2DROS::on_activate BLOCKS in a" \
                "canTransform() loop until it can resolve its own" \
                "global_frame -> robot_base_frame. For global_costmap" \
                "that is map -> $VID/base_link, which does not exist" \
                "until AMCL is ACTIVE and seeded." \
                "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
            sleep 2
        done
    done
    deadline=$(( $(date +%s) + CFG_NAV_HEALTH_TIMEOUT_S ))
    until ros2 action list 2>/dev/null | grep -q "^$action$"; do
        [ "$(date +%s)" -lt "$deadline" ] || refuse \
            "$action is on the graph" \
            "$LOGDIR/$CFG_NAV_BT_NODE_NAME.log" \
            "every nav lifecycle node is ACTIVE and the action the" \
            "adapter sends every goal to is not advertised." \
            "IF IT IS ADVERTISED UNNAMESPACED (/navigate_to_pose) the" \
            "bt_navigator lost its __ns remap, and four trucks would" \
            "then share one action server." \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
        sleep 2
    done
    echo "  $action answering, six lifecycle nodes active"
}

# ---- AND CAN IT PLAN, OR IS IT MERELY ANSWERING? ----
#
# ONE TRIVIAL PATH, 2.00 m ahead of the seed. It is the only check that
# can see an ACTIVE nav arm with an EMPTY costmap, and on this branch
# the map is SHARED - one un-namespaced map_server, latched ONCE for
# four late-joining AMCLs and four static layers - so the failure can
# take one truck or all four and looks identical either way.
#   IT COMMANDS NO MOTION. compute_path_to_pose is the PLANNER's action
# and never reaches the controller, so nothing is published on this
# truck's command path and the vehicle does not move.
nav_can_plan() {
    if ! python3 "$M6V2/tools/nav_plan_health.py" --vid "$VID" \
            "${NS[@]}" -r __node:=nav_plan_health; then
        refuse "this truck's planner returns a PATH and not just a status" \
            "$M6V2/tools/nav_plan_health.py (its refusal is printed above)" \
            "every lifecycle node is ACTIVE, the navigate action is on" \
            "the graph, and the planner cannot produce two poses over" \
            "two metres of open aisle." \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP."
    fi
}

# ---------------------------- THE SPAWNER ----------------------------
# EVERY CHILD IN ITS OWN SESSION AND ITS OWN LOG. m5v3.sh's spawn(),
# unchanged in mechanism: setsid so the stack outlives the terminal, the
# LEADER writes its own pid (setsid execs in place or forks depending on
# its caller, so $! is not reliably the leader), and the NAME is written
# beside it so `status` can report a child by the name its log is under.
spawn() {  # spawn <name> <cmd...>
    local name="$1" pid="" want=$(( $(wc -l < "$PIDFILE") + 1 ))
    shift
    setsid bash -c 'echo "$$ $1" >> "$2"; shift 2; exec "$@"' \
        _ "$name" "$PIDFILE" "$@" > "$LOGDIR/$name.log" 2>&1 &
    local tries=0
    while [ "$tries" -lt "$CFG_TIMING_PID_WAIT_TRIES" ]; do
        pid="$(sed -n "${want}s/ .*//p" "$PIDFILE")"
        [ -n "$pid" ] && break
        sleep "$CFG_TIMING_PID_WAIT_S"
        tries=$(( tries + 1 ))
    done
    echo "  $name pid ${pid:-UNKNOWN, see $LOGDIR/$name.log}"
}

# THE RUN'S OWN LOG DIRECTORY. paths.log_dir is already per-truck, so
# this is the second separation and it is the one m5v3.sh added for a
# measured reason: without it the NEXT bringup truncates the logs that
# say why the last one failed. The directory is recorded in the state
# file, and `status`/`stop` read it back; with no record - a crash, or a
# `status` after `stop` - LOGDIR stays the root, which is never wrong,
# only older.
open_run_log_dir() {
    LOGDIR="$LOGROOT/$(date +%Y%m%d-%H%M%S)"
    mkdir -p "$LOGDIR" || refuse "the log directory is writable" \
        "$CONFIG (paths.log_dir)" "$LOGDIR could not be created."
}

adopt_run_log_dir() {
    local recorded
    [ -f "$STATEFILE" ] || return 0
    recorded="$(sed -n 's/^log_dir=//p' "$STATEFILE")"
    [ -n "$recorded" ] && [ -d "$recorded" ] && LOGDIR="$recorded"
    return 0
}

# WHAT THIS BRINGUP IS, WRITTEN DOWN. m5v3.sh's write_traction, and the
# reason is the same one: an arm that changes what is being measured has
# to be readable off the running stack, not remembered. `monitor=` is
# the arm here - the collision monitor stands IN the command path when
# it is armed - and `masked_scan=` is the address the costmaps and AMCL
# were actually pointed at.
write_state() {
    { echo "vid=$VID"
      echo "partition=$GZ_PARTITION"
      echo "domain=$ROS_DOMAIN_ID"
      echo "monitor=$MONITOR"
      echo "masked_scan=$MASKED_SCAN"
      echo "log_dir=$LOGDIR"
      echo "started=$(date -Is)"; } > "$STATEFILE" \
        || refuse "the state file is writable" "$CONFIG" \
            "paths.traction_file resolves to $STATEFILE" \
            "without it 'status' cannot say which arm is up and 'stop'" \
            "cannot find this bringup's logs."
}

# ------------------------------- START -------------------------------
start() {
    configure
    if [ -f "$PIDFILE" ]; then
        local pid name live=""
        while read -r pid name; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            truck_ours "$pid" && live="$live${live:+ }$name"
        done < "$PIDFILE"
        [ -z "$live" ] || refuse "truck $VID is not already up" "$PIDFILE" \
            "these children are still running: $live" \
            "TWO STACKS FOR ONE TRUCK IS TWO PUBLISHERS OF" \
            "map -> $VID/odom, and tf2 carries whichever arrived last." \
            "  bash $0 $VID stop"
        rm -f "$PIDFILE"
    fi

    # ---- WHAT IS ON DISK, BEFORE ANYTHING IS ON THE GRAPH ----
    local file
    for file in "$EKF_PARAMS" "$SMOOTHER_PARAMS" "$LOC_PARAMS" \
                "$NAV_PARAMS" "$NAV_BT" "$NAV_BT_RPP" \
                "$NAV_BT_STATION"; do
        [ -f "$file" ] || refuse "this truck's derived artifacts exist" \
            "m6_ver2/tools/instantiate_truck.py (SPEC_NAMESPACING.md 3)" \
            "$file is not there. The per-vid tree is a gitignored BUILD" \
            "PRODUCT: derive it, do not write it by hand." \
            "  python3 m6_ver2/tools/instantiate_truck.py --vid $VID" \
            "NOTHING WAS STARTED."
    done
    [ -f "$BTDIR_SO" ] || refuse "the direction-stable BT plugin is built" \
        "$CFG_BT_DIRECTION_SOURCE_DIR and m5_ver3/tools/install_bt_direction.sh" \
        "$BTDIR_SO is not there, and nav2.yaml names" \
        "$CFG_BT_DIRECTION_LIBRARY in plugin_lib_names." \
        "bt_navigator dlopens that by BT::SharedLibrary off the loader" \
        "path; without it the tree fails to build and the navigator" \
        "falls back to nav2's own, which has Spin and BackUp in it." \
        "build it once, shared by all four trucks:" \
        "  bash m5_ver3/tools/install_bt_direction.sh" \
        "NOTHING WAS STARTED."

    check_wrapped_params "$EKF_PARAMS" "the estimator" "$CFG_EKF_NODE_NAME"
    check_wrapped_params "$SMOOTHER_PARAMS" "the velocity smoother" \
        "$CFG_SMOOTHER_NODE_NAME"
    check_wrapped_params "$LOC_PARAMS" "the localiser" \
        "$CFG_LOCALIZATION_AMCL_NODE_NAME"
    # shellcheck disable=SC2086
    check_wrapped_params "$NAV_PARAMS" "the nav servers and both costmaps" \
        $NAV_SECTIONS
    if [ "$MONITOR" = true ]; then
        check_wrapped_params "$MONITOR_PARAMS" "the collision monitor" \
            "$CFG_MONITOR_NODE_NAME"
    fi

    # ---- THE THREE ADDRESSES A `-p` CANNOT REACH ----
    # nav2's costmaps are SUB-NODES with no command line, so these three
    # live in the file and the file is the only place they can be got
    # right. Each is checked against what THIS script passes elsewhere.
    check_address "$NAV_PARAMS" map_topic "$CFG_TOPICS_MAP" \
        "$CONFIG (topics.map) and m6_ver2/world.launch.py" \
        "global_costmap's static layer subscribes there, and the shared" \
        "map_server latches it ONCE for all four trucks. Wrong, the" \
        "costmap stays wall-to-wall NO_INFORMATION - which with" \
        "allow_unknown:false refuses every goal."
    check_address "$NAV_PARAMS" topic "$MASKED_SCAN" \
        "m6_ver2/tools/instantiate_truck.py (masked_scan_topic) and SPEC_ADAPTER.md A-T2" \
        "both obstacle layers mark and clear from there, and it is the" \
        "MASKED scan rather than the bridge's raw one: this vehicle's" \
        "own mast stands in the nav lidar's beam at 1.29-1.48 m, and a" \
        "layer that marks those returns puts LETHAL CELLS ON THE ROBOT" \
        "- the 205 START_OCCUPIED class, on every plan, for ever."
    check_address "$NAV_PARAMS" robot_base_frame "$CFG_FRAMES_BASE_LINK" \
        "$CONFIG (frames.base_link)" \
        "every costmap and both navigators place the vehicle by that" \
        "frame, and on this branch it carries the truck. Wrong, they" \
        "find no transform and Costmap2DROS::on_activate BLOCKS on it," \
        "so the lifecycle transition never returns."

    source_ros
    open_run_log_dir
    : > "$PIDFILE" || refuse "the pid file is writable" "$CONFIG" \
        "paths.pidfile resolves to $PIDFILE"
    write_state
    echo "truck $VID: partition $GZ_PARTITION, domain $ROS_DOMAIN_ID"
    echo "logs:  $LOGDIR"
    check_world

    # ---- THE VEHICLE'S OWN GEOMETRY, ON THE SHARED /tf_static ----
    # TWO STATIC PUBLISHERS AND EACH GETS A NODE NAME OF ITS OWN, which
    # m5v3.sh did not need and this branch does: one truck's two mounts
    # are two processes of the same executable, and four trucks make
    # eight. Unnamed they would all be /<vid>/static_transform_publisher
    # - two per namespace, colliding by name, and `ros2 node list`
    # unreadable.
    #   NO use_sim_time ON EITHER, DELIBERATELY (m5v3.sh's note): tf2
    #   stores a static transform in a cache that answers for ANY query
    #   time, so the stamp is never consulted and a clock these
    #   processes do not have cannot go wrong.
    spawn imutf ros2 run tf2_ros static_transform_publisher \
        --x "$CFG_VEHICLE_IMU_MOUNT_X" \
        --y "$CFG_VEHICLE_IMU_MOUNT_Y" \
        --z "$CFG_VEHICLE_IMU_MOUNT_Z" \
        --frame-id "$CFG_FRAMES_BASE_LINK" \
        --child-frame-id "$CFG_FRAMES_IMU" \
        "${NS[@]}" -r __node:=imu_mount_tf
    spawn lasertf ros2 run tf2_ros static_transform_publisher \
        --x "$CFG_VEHICLE_NAV_LIDAR_MOUNT_X" \
        --y "$CFG_VEHICLE_NAV_LIDAR_MOUNT_Y" \
        --z "$CFG_VEHICLE_NAV_LIDAR_MOUNT_Z" \
        --frame-id "$CFG_FRAMES_BASE_LINK" \
        --child-frame-id "$CFG_FRAMES_NAV_LIDAR" \
        "${NS[@]}" -r __node:=nav_lidar_mount_tf

    # ---- THE WHEEL ODOMETRY, AND THE ONE CHILD THAT NEEDED A SEAM ----
    #
    # THE DONOR NODE IS RUN, NOT COPIED - AND IT HAS TO BE TOLD WHICH
    # CONFIG IT IS. m5_ver3/nodes/wheel_odometry.py declares NO ros
    # parameters: it reads every topic and both frames out of
    # config.yaml through m5_ver3/tools/_common.py, whose CONFIG is
    # bound to the DONOR file at import. Run as-is under a namespace it
    # would publish /m5v3/wheel_odom (absolute: the namespace does not
    # touch it), subscribe /forklift/gz/joint_state, and - the one that
    # cannot be repaired with a remap at all - stamp its Odometry
    # `frame_id: odom` and `child_frame_id: base_link`, the BARE
    # REP-105 names. Four trucks would publish one topic, and the EKF
    # would drop a sensor whose frame is not on the tree.
    #   SO THE SEAM IS THE MODULE CONSTANT, REBOUND BY THE CALLER before
    #   the node is imported. It is not an edit of the donor
    #   (AMR-DEC-006 freezes it) and it is not a vendored copy - a
    #   second wheel odometry in this tree would be a second estimator
    #   to maintain and the reason m6_ver2 imports rather than copies.
    #   `_common.load_config` opens `_common.CONFIG` at CALL time, so
    #   rebinding it before the import is enough, and every refusal that
    #   node prints then names THIS truck's config.
    #   The `-c` program carries the script's name, so the sweep's
    #   `wheel_odometry.py` pattern still nominates it.
    spawn odom python3 -c '
import sys
tools, nodes, config = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, tools)
sys.path.insert(0, nodes)
import _common
_common.CONFIG = config           # m6_ver2/truck.sh: this truck, not the donor
import wheel_odometry             # m5_ver3/nodes/wheel_odometry.py, unedited
sys.exit(wheel_odometry.main())
' "$M6V2_REPO/m5_ver3/tools" "$M6V2_REPO/m5_ver3/nodes" "$CONFIG" \
        "${NS[@]}" -r __node:=wheel_odometry

    # ---- THE FILTER ----
    # Everything on this command line is a NAME or a RATE that is
    # already written down in config.yaml and is passed as a `-p` so
    # ekf.yaml cannot hold a second copy of it; ekf.yaml holds what is
    # FUSED and what is refused. The frames are this truck's, so the
    # edge this node owns is <vid>/odom -> <vid>/base_link and nothing
    # else - four disjoint children under one shared tree.
    #   THE ONE REMAP WHOSE MATCH SIDE HAD TO CHANGE. m5v3.sh writes
    #   `-r /odometry/filtered:=...`; ekf_node's topic is RELATIVE, so
    #   under /<vid> the absolute match side matches nothing at all and
    #   the filter would publish /<vid>/odometry/filtered by accident
    #   rather than by instruction. Relative, it fires.
    spawn ekf ros2 run robot_localization ekf_node \
        "${NS[@]}" \
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
        -r "odometry/filtered:=$CFG_TOPICS_ODOMETRY_FILTERED"

    # ---- THE COMMAND PATH ----
    # Nav2's output steps on every replan and this plant has no ramp of
    # its own, so the smoother is not behind a flag. Both match sides
    # are relative for the reason in this file's header.
    spawn smoother ros2 run "$CFG_SMOOTHER_PACKAGE" \
        "$CFG_SMOOTHER_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_SMOOTHER_NODE_NAME" \
        --params-file "$SMOOTHER_PARAMS" \
        -p use_sim_time:=true \
        -p odom_topic:="$CFG_TOPICS_ODOMETRY_FILTERED" \
        -r "cmd_vel:=$CFG_TOPICS_CMD_VEL" \
        -r "cmd_vel_smoothed:=$CFG_TOPICS_CMD_VEL_SMOOTHED"

    # AND ON --monitor, ONE LINK IN BETWEEN. It goes after the smoother
    # and before the adapter for m5v3.sh's measured reason: before the
    # smoother a stop it asked for would be handed to a limiter that
    # softens it back into a ramp, and after the adapter there is no
    # Twist left to guard. The ADAPTER's input is remapped rather than
    # the smoother's output re-pointed, so every existing address keeps
    # meaning what it says and one new name is added.
    #   IT IS NOT A SAFETY FUNCTION. nav2's own words: it "does not
    #   provide hard real-time safety certifications". The F-PLC keeps
    #   the last word.
    local adapter_in="$CFG_TOPICS_CMD_VEL_SMOOTHED"
    if [ "$MONITOR" = true ]; then
        spawn monitor ros2 run "$CFG_MONITOR_PACKAGE" \
            "$CFG_MONITOR_EXECUTABLE" \
            "${NS[@]}" \
            -r __node:="$CFG_MONITOR_NODE_NAME" \
            --params-file "$MONITOR_PARAMS" \
            -p cmd_vel_in_topic:="$CFG_TOPICS_CMD_VEL_SMOOTHED" \
            -p cmd_vel_out_topic:="$CFG_TOPICS_CMD_VEL_MONITORED" \
            -p state_topic:="$CFG_TOPICS_COLLISION_MONITOR_STATE" \
            -p scan.topic:="$CFG_TOPICS_SCAN_NAV"
        adapter_in="$CFG_TOPICS_CMD_VEL_MONITORED"
    fi

    # ---- THE SELF-MASK, AND IT GOES UP BEFORE ITS TWO CONSUMERS ----
    # AMCL's scan subscription is a tf2 MessageFilter and the costmaps
    # simply wait, so an empty topic costs nothing but a few dropped
    # scans - but a filter started AFTER them is a filter whose absence
    # is measured as a localiser fault. Both addresses are passed on
    # this line because the shell is the thing that knows which they
    # are: the input is config.yaml's raw bridged scan, the output is
    # the derivation's masked name.
    spawn scanmask python3 "$M6V2/nav2_adapter/scan_mask_node.py" \
        --in-topic "$CFG_TOPICS_SCAN_NAV" --out-topic "$MASKED_SCAN" \
        "${NS[@]}" -r __node:=scan_mask -p use_sim_time:=true

    # ---- THE LOCALISER ----
    # THE THREE FRAMES ARE THE WHOLE OF THE SHARED-TREE DECISION ON ONE
    # COMMAND LINE. global_frame_id is the SHARED `map` and odom_frame_id
    # is THIS TRUCK's, so the edge this node publishes is
    # map -> <vid>/odom and nothing else; four AMCLs own four disjoint
    # edges under one parent (SPEC_NAMESPACING.md 2).
    #   map_topic IS ABSOLUTE AND STAYS ABSOLUTE: parameters are not
    #   remapped by __ns, and there is ONE latched grid for the world.
    #   scan_topic IS THE MASKED SCAN, for the reason check_address
    #   states above.
    spawn "$CFG_LOCALIZATION_AMCL_NODE_NAME" \
        ros2 run "$CFG_LOCALIZATION_AMCL_PACKAGE" \
        "$CFG_LOCALIZATION_AMCL_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_LOCALIZATION_AMCL_NODE_NAME" \
        --params-file "$LOC_PARAMS" \
        -p use_sim_time:=true \
        -p scan_topic:="$MASKED_SCAN" \
        -p map_topic:="$CFG_TOPICS_MAP" \
        -p base_frame_id:="$CFG_FRAMES_BASE_LINK" \
        -p odom_frame_id:="$CFG_FRAMES_ODOM" \
        -p global_frame_id:="$CFG_FRAMES_MAP"

    sleep "$CFG_TIMING_STARTUP_CHECK_S"
    assert_children_alive

    drive_lifecycle "$CFG_LOCALIZATION_AMCL_NODE_NAME" \
        "$CFG_LOCALIZATION_LIFECYCLE_TIMEOUT_S" \
        "$LOGDIR/$CFG_LOCALIZATION_AMCL_NODE_NAME.log" \
        "AND on_activate BLOCKS WAITING FOR A LATCHED MAP. The shared" \
        "map_server is the world launch's; if it is INACTIVE it never" \
        "publishes one and this node waits here for ever." \
        "read $LOGDIR/$CFG_LOCALIZATION_AMCL_NODE_NAME.log."

    smoother_active
    if [ "$MONITOR" = true ]; then monitor_active; fi

    # ---- THE ESTIMATOR IS SANE AND THE LOCALISER IS LOCALISED ----
    # ONE PROCESS FOR BOTH GATES, AND THAT IS DELIBERATE. m5v3 runs
    # ekf_health.py and localization_health.py separately because the
    # first can be a bare `ros2 topic echo`; here the seed gate has to
    # PUBLISH before it READS - with the truck standing still AMCL
    # publishes exactly ONE pose per seed - so a second process would be
    # a second discovery, a second wait and a second chance to time out
    # on a healthy stack. nav2_seed.py reads the filter first, then
    # seeds, then reads back, and refuses each by name.
    if ! python3 "$M6V2/nav2_adapter/nav2_seed.py" --vid "$VID" \
            "${NS[@]}" -r __node:=nav2_seed; then
        refuse "the filter is sane and the localiser came up localised" \
            "$M6V2/nav2_adapter/nav2_seed.py (its refusal is printed above)" \
            "every other check on this truck has passed: every child is" \
            "ALIVE, AMCL is ACTIVE and the command path's smoother has" \
            "reached ACTIVE on its own." \
            "A SEED YOU DID NOT READ BACK IS NOT A SEED (m5v3 G5)." \
            "THE STACK IS INCOMPLETE, and what is left of it is STILL UP." \
            "'bash $0 $VID stop', then read" \
            "$LOGDIR/$CFG_LOCALIZATION_AMCL_NODE_NAME.log and $LOGDIR/ekf.log."
    fi

    # ---- THE NAV ARM, AND IT GOES UP AFTER THE LOCALISER IS SEEDED ----
    # Costmap2DROS::on_activate BLOCKS in a canTransform() loop until it
    # can resolve global_frame -> robot_base_frame. For global_costmap
    # that is map -> <vid>/base_link, and map -> <vid>/odom does not
    # exist until AMCL is ACTIVE - so a nav arm started earlier sits
    # wedged in a lifecycle transition with five ALIVE processes and
    # nothing in any log that reads as an error.
    spawn "$CFG_NAV_PLANNER_NODE_NAME" \
        ros2 run "$CFG_NAV_PLANNER_PACKAGE" \
        "$CFG_NAV_PLANNER_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_NAV_PLANNER_NODE_NAME" \
        --params-file "$NAV_PARAMS"

    spawn "$CFG_NAV_CONTROLLER_NODE_NAME" \
        ros2 run "$CFG_NAV_CONTROLLER_PACKAGE" \
        "$CFG_NAV_CONTROLLER_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_NAV_CONTROLLER_NODE_NAME" \
        --params-file "$NAV_PARAMS" \
        -p odom_topic:="$CFG_TOPICS_ODOMETRY_FILTERED" \
        -p speed_limit_topic:="$CFG_TOPICS_SPEED_LIMIT" \
        -r "cmd_vel:=$CFG_TOPICS_CMD_VEL"

    # ITS /cmd_vel IS REMAPPED ANYWAY. `wait` publishes nothing, so the
    # remap carries no traffic - but a behaviour server left on nav2's
    # default name would be a SECOND publisher on the address the whole
    # command path is built around, and an address that is only right
    # because nothing uses it is not right.
    spawn "$CFG_NAV_BEHAVIOR_NODE_NAME" \
        ros2 run "$CFG_NAV_BEHAVIOR_PACKAGE" \
        "$CFG_NAV_BEHAVIOR_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_NAV_BEHAVIOR_NODE_NAME" \
        --params-file "$NAV_PARAMS" \
        -r "cmd_vel:=$CFG_TOPICS_CMD_VEL"

    # THE ONE NAV CHILD SPAWNED THROUGH `env`: nav2.yaml names the
    # direction-stable BT node in plugin_lib_names and bt_navigator
    # resolves that with BT::SharedLibrary - a plain dlopen off the
    # LOADER PATH, with no ament index in it - so the workspace has to
    # be on THIS child's LD_LIBRARY_PATH and on nothing else's.
    # btdir_env() is called here rather than beside btdir_paths()
    # because it PREPENDS to what source_ros() exported.
    btdir_env
    spawn "$CFG_NAV_BT_NODE_NAME" \
        env "LD_LIBRARY_PATH=$BTDIR_LD_LIBRARY_PATH" \
        ros2 run "$CFG_NAV_BT_PACKAGE" \
        "$CFG_NAV_BT_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_NAV_BT_NODE_NAME" \
        --params-file "$NAV_PARAMS" \
        -p odom_topic:="$CFG_TOPICS_ODOMETRY_FILTERED" \
        -p default_nav_to_pose_bt_xml:="$NAV_BT"

    # THE MANAGER IS SPAWNED LAST OF THE FIVE: it looks up each server's
    # change_state service and starts transitioning as soon as it can,
    # so started first it would spend its whole wait_for_service budget
    # on nodes that do not exist yet. Its `node_names` list is
    # nav2.yaml's and, wrapped under <vid>:, the names it drives are
    # relative to /<vid> - which is the same namespace it is in.
    spawn "$CFG_NAV_LIFECYCLE_NODE_NAME" \
        ros2 run "$CFG_NAV_LIFECYCLE_PACKAGE" \
        "$CFG_NAV_LIFECYCLE_EXECUTABLE" \
        "${NS[@]}" \
        -r __node:="$CFG_NAV_LIFECYCLE_NODE_NAME" \
        --params-file "$NAV_PARAMS"

    sleep "$CFG_TIMING_STARTUP_CHECK_S"
    assert_children_alive
    nav_can_answer
    nav_can_plan

    # ---- AND THE ADAPTER, WHICH IS WHAT m6 TALKS TO ----
    # It replaces m6/ipc/nav_node.py as the motion engine and presents
    # the byte-identical /auto contract to a fleet layer that is not
    # being modified. Its input is the last twist in the command path -
    # the smoother's, or the monitor's when that is armed - and the
    # match side is relative so the remap fires under the namespace.
    spawn adapter python3 "$M6V2/nav2_adapter/nav2_adapter_node.py" \
        --vid "$VID" --world-frame "$WORLD_FRAME" \
        "${NS[@]}" -r __node:=nav2_adapter -p use_sim_time:=true \
        -r "cmd_vel_smoothed:=$adapter_in"

    sleep "$CFG_TIMING_STARTUP_CHECK_S"
    assert_children_alive
    echo "up."
}

# ------------------------------- STOP -------------------------------
stop() {
    configure
    adopt_run_log_dir
    # THIS TRUCK ONLY, AND THE WORLD IS NOT THIS SCRIPT'S TO END. The
    # sweep's patterns nominate; truck_ours() decides, and it requires
    # BOTH GZ_PARTITION=$GZ_PARTITION and M6V2_VID=$VID in a candidate's
    # environment - so a neighbour truck, the m6 fleet layer and the
    # world launch are all spared, every time.
    #   stop IS NOT A BRAKE. The model's joint controllers are VELOCITY
    #   controllers that hold their last setpoint for ever (measured in
    #   m6: 14.8 m on a standing command after its publisher stopped),
    #   so killing this stack cannot slow a moving vehicle. The brake is
    #   the e-stop and the contactor.
    local pid name
    truck_sweep TERM
    if [ -f "$PIDFILE" ]; then
        while read -r pid name; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            truck_ours "$pid" && kill "$pid" 2>/dev/null \
                && echo "  killed $pid ($name)"
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    else
        echo "nothing to stop."
    fi
    rm -f "$STATEFILE"
    sleep "$CFG_TIMING_STOP_GRACE_S"
    truck_sweep KILL
    echo "down."
    if [ "$LOGDIR" != "$LOGROOT" ] && [ -d "$LOGDIR" ]; then
        echo "logs kept: $LOGDIR"
    fi
}

# ------------------------------ STATUS ------------------------------
status() {
    configure
    adopt_run_log_dir
    echo "truck $VID: partition $GZ_PARTITION, domain $ROS_DOMAIN_ID"
    echo "pidfile: $PIDFILE"
    echo "logs:    $LOGDIR"
    if [ ! -f "$PIDFILE" ]; then
        echo "not running (no pid file)."
        return 1
    fi
    if [ -f "$STATEFILE" ]; then
        printf '  %-10s %s\n' "arm" \
            "monitor=$(sed -n 's/^monitor=//p' "$STATEFILE") scan=$(sed -n 's/^masked_scan=//p' "$STATEFILE")"
        printf '  %-10s %s\n' "started" "$(sed -n 's/^started=//p' "$STATEFILE")"
    fi
    local pid name down=0
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        if truck_ours "$pid"; then
            printf '  %-10s %-7s pid %s\n' "$name" "ALIVE" "$pid"
        else
            printf '  %-10s %-7s %s\n' "$name" "DOWN" "$LOGDIR/$name.log"
            down=$(( down + 1 ))
        fi
    done < "$PIDFILE"
    [ "$down" -eq 0 ] || return 1
    return 0
}

# ---- THE TWO POLLS THAT TAKE THEIR NODE, m5v3.sh's smoother_active
# and monitor_active with the namespace in the address ----
smoother_active() {
    autostart_active "$CFG_SMOOTHER_NODE_NAME" \
        "$CFG_SMOOTHER_ACTIVE_TIMEOUT_S" "$LOGDIR/smoother.log" \
        "$CFG_SMOOTHER_PARAMS_FILE" \
        "LEFT SHORT OF ACTIVE IT SUBSCRIBES TO NOTHING AND PUBLISHES" \
        "NOTHING - so the command path would have no smoother in it at" \
        "all: every twist a step at a terminal with no ramp."
}

monitor_active() {
    autostart_active "$CFG_MONITOR_NODE_NAME" \
        "$CFG_MONITOR_ACTIVE_TIMEOUT_S" "$LOGDIR/monitor.log" \
        "$CFG_MONITOR_PARAMS_FILE" \
        "AND ON THIS ARM IT IS IN THE COMMAND PATH RATHER THAN BESIDE" \
        "IT. --monitor remaps the ADAPTER's input to this node's" \
        "output, so a monitor short of ACTIVE publishes nothing at all" \
        "and the adapter waits for ever on a topic with no publisher:" \
        "the truck does not move, and nothing in any log says why."
}

case "$CMD" in
    start)  start ;;
    stop)   stop ;;
    status) status ;;
esac
