#!/usr/bin/env bash
# build_map.sh - the map of warehouse_ver3, built OFFLINE from a recorded
# session by slam_toolbox, and frozen.
#
#   bash m5_ver3/tools/build_map.sh m5_ver3/logs/evidence/drive-mapping-...
#   bash m5_ver3/tools/build_map.sh <session> --name warehouse_v3_b
#
# IT STARTS NO PLANT AND ATTACHES TO NONE. Everything it runs reads a
# rosbag2 that tools/sensor_evidence.py's `record --bag` wrote: the
# world is not running, the truck is not moving, and the same session
# replayed tomorrow produces the same map. That is the whole reason the
# map is built this way rather than by driving with a live mapper -
# docs/reports/m5v3-01 (a) ranks offline sync first for it, and
# EVIDENCE_MAP_V3.md checks the claim by building the map twice and
# comparing the md5s.
#
# IT RUNS ON ITS OWN ROS DOMAIN AND THAT IS A SAFETY PROPERTY, NOT
# TIDINESS. The bag CARRIES /tf, which is the EKF's odom -> base_link.
# Replayed onto the live stack's domain there would be two publishers of
# one transform and tf2 would carry whichever arrived last - the failure
# F2's whole one-authority-per-edge rule exists to prevent, with no
# refusal anywhere to catch it. config.yaml's isolation.map_ros_domain_id
# is where the replay lives; this script refuses if it equals the live
# one.
#
# WHAT IT PUTS ON THE WIRE, AND WHERE EACH THING COMES FROM:
#
#   /clock, /forklift/gz/scan_nav, /tf, /tf_static   the BAG
#   base_link -> nav_lidar_link                      THIS SCRIPT
#   map -> odom                                      slam_toolbox
#
# THE SECOND LINE IS THE ONLY THING HERE THAT IS NOT IN THE RECORDING,
# and it is the one seam this run has. The default arm does not publish
# the nav lidar's mount: `m5v3.sh start --rf2o` spawns a `lasertf` child
# for it because rf2o needs it, and the default six-child stack has no
# consumer for it and therefore no publisher. F3 constraint 17 says
# baselines are taken on the DEFAULT arm, so the recording was made
# there and this transform is published HERE, in the offline graph, from
# config.yaml's vehicle.nav_lidar_mount - the same three numbers the
# `lasertf` child reads, checked against model.sdf by
# nodes/rf2o_twist.py's mount_from_model(). Nothing about the live stack
# changes, and F3 constraint 15 holds: this task adds no runtime TF.
#
# THE MAP IS FROZEN ONCE IT IS BUILT (F3 constraint 16). This script
# REFUSES an output directory that already exists. A rebuild is a new
# artifact under a new --name, so the committed grid, the pose graph and
# the registration derived from them can never be quietly replaced by a
# different map wearing the same md5-less name.
set -euo pipefail

TOOL=build_map
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

usage() {
    cat <<EOF
usage: bash m5_ver3/tools/build_map.sh <session-dir> [--name NAME]

  <session-dir>  a session written by
                 tools/sensor_evidence.py record --drive PROFILE --bag
  --name NAME    the artifact's name (default: config.yaml map.name).
                 The output directory must not already exist.
EOF
    exit 2
}

SESSION=""
NAME=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --name) [ "$#" -ge 2 ] || usage; NAME="$2"; shift 2 ;;
        -h|--help) usage ;;
        -*) usage ;;
        *) [ -z "$SESSION" ] || usage; SESSION="$1"; shift ;;
    esac
done
[ -n "$SESSION" ] || usage

load_config \
    map.dir map.name map.slam.params_file map.slam.package \
    map.slam.executable map.slam.node_name map.slam.play_rate \
    map.slam.lifecycle_timeout_s map.slam.settle_s \
    map.slam.serialize_timeout_s map.slam.save_timeout_s \
    map.slam.save_map_timeout_s \
    map.slam.occupied_thresh map.slam.free_thresh \
    topics.scan_nav frames.base_link frames.nav_lidar frames.odom \
    frames.map vehicle.nav_lidar_mount.x vehicle.nav_lidar_mount.y \
    vehicle.nav_lidar_mount.z evidence.bag.dir evidence.bag.storage \
    paths.log_dir isolation.map_ros_domain_id timing.stop_grace_s

NAME="${NAME:-$CFG_MAP_NAME}"

# THE REPLAY'S OWN GRAPH. load_config exported the LIVE domain, as it
# does for every tool on this track; this is the one script that must not
# be on it, and it says so here rather than anywhere a reader could miss.
if [ "$CFG_ISOLATION_MAP_ROS_DOMAIN_ID" = "$CFG_ISOLATION_ROS_DOMAIN_ID" ]; then
    refuse "the offline replay has a domain of its own" "$CONFIG" \
        "isolation.map_ros_domain_id and isolation.ros_domain_id both read" \
        "$CFG_ISOLATION_ROS_DOMAIN_ID. The bag carries /tf, so replaying it" \
        "onto the live stack's domain would put a SECOND publisher of" \
        "odom -> base_link beside the EKF and tf2 would carry whichever" \
        "arrived last."
fi
export ROS_DOMAIN_ID="$CFG_ISOLATION_MAP_ROS_DOMAIN_ID"
# GZ_PARTITION is exported by load_config and there is no simulator here;
# it is unset so nothing in this graph can address the live plant at all.
unset GZ_PARTITION

# ---------------------------------------------------------------- input
SESSION="$(cd "$SESSION" 2>/dev/null && pwd || echo "$SESSION")"
[ -d "$SESSION" ] || refuse "the session directory exists" "$SESSION" \
    "it is written by tools/sensor_evidence.py record --drive P --bag"
SESSION_FILE="$SESSION/session.txt"
[ -f "$SESSION_FILE" ] || refuse "the session carries a session.txt" \
    "$SESSION" \
    "a directory without one is not a session that tool produced."

field() {  # field <key>
    sed -n "s/^$1=//p" "$SESSION_FILE" | head -1
}

BAG="$SESSION/$CFG_EVIDENCE_BAG_DIR"
[ -f "$BAG/metadata.yaml" ] || refuse \
    "the session carries a FINALISED rosbag2" "$BAG" \
    "there is no metadata.yaml, so either the run was recorded without" \
    "--bag or the recorder could not close it (session.txt bag_files=)." \
    "\`ros2 bag play\` refuses a bag without one and so does this."

# ---- THE TWO LABELS, AND THEY ARE REFUSALS HERE FOR THE SAME REASON
#      THEY ARE REFUSALS IN THE RECORDER ----
# F3 constraint 17: baselines are taken on the DEFAULT arm. A map is the
# most reusable artifact this track produces - everything localised
# against it inherits whatever it was built on - so a map built from a
# --slippery run or from the --fuse arm's odometry, unlabelled, would be
# a wrong foundation that nothing downstream could detect.
TRACTION="$(field traction)"
ARM="$(field arm)"
PROFILE="$(field profile)"
[ "$TRACTION" = "nominal" ] || refuse \
    "the recording was made on the NOMINAL plant" "$SESSION_FILE" \
    "it says traction=${TRACTION:-<blank>}. A map carries whatever it was" \
    "built on into everything that localises against it, and F3's" \
    "baselines are on the plant EVIDENCE_FUSION 9.3 measured."
[ "$ARM" = "wheel+imu" ] || refuse \
    "the recording was made on the DEFAULT estimator arm" "$SESSION_FILE" \
    "it says arm=${ARM:-<blank>}. The odometry in that bag is what the" \
    "mapper corrects, so a map built on --rf2o or --fuse is a map of a" \
    "stack that is not the one that ships (F3 constraint 17)."

# ---------------------------------------------------------------- output
OUT="$REPO/$CFG_MAP_DIR/$NAME"
if [ -e "$OUT" ]; then
    refuse "the output artifact does not already exist" "$OUT" \
        "A MAP IS FROZEN ONCE IT IS SCORED (F3 constraint 16): its grid," \
        "its pose graph and the registration derived from them are" \
        "committed together with their md5s, and overwriting the grid" \
        "would leave a registration that silently belongs to a different" \
        "map. A rebuild is a NEW artifact:" \
        "  bash m5_ver3/tools/build_map.sh $SESSION --name ${NAME}_b"
fi
mkdir -p "$OUT"
LOGS="$REPO/$CFG_PATHS_LOG_DIR"
mkdir -p "$LOGS"

source_ros

command -v ros2 >/dev/null 2>&1 || refuse "ros2 is on PATH" \
    "$CONFIG (paths.ros_setup)" "sourcing $ROS_SETUP did not provide it"
ros2 pkg prefix "$CFG_MAP_SLAM_PACKAGE" >/dev/null 2>&1 || refuse \
    "$CFG_MAP_SLAM_PACKAGE is installed" "the rig" \
    "\`ros2 pkg prefix $CFG_MAP_SLAM_PACKAGE\` found nothing." \
    "This gate does not build it: it is an apt package on this rig."
ros2 pkg prefix nav2_map_server >/dev/null 2>&1 || refuse \
    "nav2_map_server is installed" "the rig" \
    "map_saver_cli is the ONE map exporter this track uses."

# ---------------------------------------------------------------- children
PIDS=()
NAMES=()

spawn() {  # spawn <name> <command...>
    local child="$1"; shift
    local log="$LOGS/map_$child.log"
    setsid "$@" > "$log" 2>&1 &
    local pid=$!
    PIDS+=("$pid"); NAMES+=("$child")
    echo "  $child pid $pid   $log"
}

cleanup() {
    local i pid
    for (( i=${#PIDS[@]}-1 ; i>=0 ; i-- )); do
        pid="${PIDS[$i]}"
        kill -TERM -"$pid" 2>/dev/null || true
    done
    sleep "$CFG_TIMING_STOP_GRACE_S"
    for (( i=${#PIDS[@]}-1 ; i>=0 ; i-- )); do
        pid="${PIDS[$i]}"
        kill -KILL -"$pid" 2>/dev/null || true
    done
}
trap cleanup EXIT

alive() {  # alive <index>
    kill -0 "${PIDS[$1]}" 2>/dev/null
}

echo "=== m5v3 offline map build ==="
echo "session    $SESSION"
echo "profile    ${PROFILE:-<none>}   traction $TRACTION   arm $ARM"
echo "bag        $BAG"
echo "domain     $ROS_DOMAIN_ID   (the live stack is on $CFG_ISOLATION_ROS_DOMAIN_ID)"
echo "params     $CFG_MAP_SLAM_PARAMS_FILE"
echo "artifact   $OUT"
echo ""

# 1. WHERE THE SCANNER IS BOLTED. See the header: this is the one thing
#    on the wire that is not in the recording. No use_sim_time on it, for
#    m5v3.sh's imutf reason - tf2 answers a static transform for ANY
#    query time, so the stamp is never consulted.
spawn lasertf ros2 run tf2_ros static_transform_publisher \
    --x "$CFG_VEHICLE_NAV_LIDAR_MOUNT_X" \
    --y "$CFG_VEHICLE_NAV_LIDAR_MOUNT_Y" \
    --z "$CFG_VEHICLE_NAV_LIDAR_MOUNT_Z" \
    --frame-id "$CFG_FRAMES_BASE_LINK" \
    --child-frame-id "$CFG_FRAMES_NAV_LIDAR"

# 2. THE MAPPER. Started BEFORE the bag, and configured and activated
#    before a single message is played: sync_slam_toolbox_node declares
#    its parameters in on_configure and does not subscribe until
#    on_activate, so a bag that started first would have its opening
#    seconds - which are the reference pose - go nowhere.
spawn slam ros2 run "$CFG_MAP_SLAM_PACKAGE" "$CFG_MAP_SLAM_EXECUTABLE" \
    --ros-args \
    --params-file "$REPO/$CFG_MAP_SLAM_PARAMS_FILE" \
    -p use_lifecycle_manager:=false \
    -r __node:="$CFG_MAP_SLAM_NODE_NAME"

echo ""
echo "waiting for $CFG_MAP_SLAM_NODE_NAME (bounded at ${CFG_MAP_SLAM_LIFECYCLE_TIMEOUT_S}s)..."
deadline=$(( $(date +%s) + CFG_MAP_SLAM_LIFECYCLE_TIMEOUT_S ))
until ros2 node list 2>/dev/null | grep -q "/$CFG_MAP_SLAM_NODE_NAME"; do
    alive 1 || refuse "the mapper stayed up" "$LOGS/map_slam.log" \
        "it exited before it advertised. Its log is above."
    [ "$(date +%s)" -lt "$deadline" ] || refuse \
        "$CFG_MAP_SLAM_NODE_NAME appeared inside ${CFG_MAP_SLAM_LIFECYCLE_TIMEOUT_S}s" \
        "$LOGS/map_slam.log (config.yaml map.slam.lifecycle_timeout_s)" \
        "nothing by that name is on domain $ROS_DOMAIN_ID."
    sleep 1
done
for transition in configure activate; do
    ros2 lifecycle set "/$CFG_MAP_SLAM_NODE_NAME" "$transition" \
        >> "$LOGS/map_slam.log" 2>&1 || refuse \
        "the mapper $transition transition succeeded" \
        "$LOGS/map_slam.log" \
        "sync_slam_toolbox_node is a lifecycle node and this script" \
        "drives it directly rather than through slam_toolbox's launch" \
        "file, so one process is one log and one refusal."
    echo "  $transition ok"
done

# 3. THE RECORDING. Played at config.yaml's rate; see map.slam.play_rate
#    for why it is not 1.0.
echo ""
echo "playing the bag at ${CFG_MAP_SLAM_PLAY_RATE}x..."
PLAY_LOG="$LOGS/map_play.log"
ros2 bag play "$BAG" --rate "$CFG_MAP_SLAM_PLAY_RATE" \
    --disable-keyboard-controls > "$PLAY_LOG" 2>&1 || refuse \
    "\`ros2 bag play\` finished the recording" "$PLAY_LOG" \
    "the replay ended non-zero; the map it would have produced is a map" \
    "of part of the drive."
echo "  played."

echo "settling ${CFG_MAP_SLAM_SETTLE_S}s so the last scans are processed"
echo "  and the occupancy grid is rastered once more..."
sleep "$CFG_MAP_SLAM_SETTLE_S"
alive 1 || refuse "the mapper survived the replay" "$LOGS/map_slam.log" \
    "it exited during or after the bag. Nothing was saved."

# 4. THE POSE GRAPH. Serialized first, because it is the artifact that
#    does not depend on a raster having happened at the right moment -
#    it IS the map, and the grid is a rendering of it.
echo ""
echo "serializing the pose graph..."
timeout "$CFG_MAP_SLAM_SERIALIZE_TIMEOUT_S" \
    ros2 service call "/$CFG_MAP_SLAM_NODE_NAME/serialize_map" \
    slam_toolbox/srv/SerializePoseGraph "{filename: '$OUT/$NAME'}" \
    > "$LOGS/map_serialize.log" 2>&1 || refuse \
    "serialize_map answered inside ${CFG_MAP_SLAM_SERIALIZE_TIMEOUT_S}s" \
    "$LOGS/map_serialize.log (config.yaml map.slam.serialize_timeout_s)" \
    "the service is advertised only after the activate transition."
grep -q "result=0" "$LOGS/map_serialize.log" || refuse \
    "serialize_map returned RESULT_SUCCESS" "$LOGS/map_serialize.log" \
    "SerializePoseGraph answers 255 when it cannot write the file."
[ -f "$OUT/$NAME.posegraph" ] && [ -f "$OUT/$NAME.data" ] || refuse \
    "the pose graph landed on disk" "$OUT" \
    "serialize_map said success and $NAME.posegraph/.data are not there."
echo "  $NAME.posegraph + $NAME.data"

# 5. THE OCCUPANCY GRID. nav2's map_saver_cli, with the two thresholds
#    config.yaml states, subscribing to the map slam_toolbox publishes.
#    That topic is transient-local, so the saver receives the LAST grid
#    the mapper rastered even though the mapper is now idle.
echo ""
echo "the grid on the wire, before anything tries to save it:"
timeout 30 ros2 topic echo /map --field info --once --no-daemon \
    > "$LOGS/map_topic.log" 2>&1 || refuse \
    "slam_toolbox published an occupancy grid" \
    "$LOGS/map_slam.log (config.yaml map.slam.settle_s)" \
    "nothing arrived on /map inside 30s. The mapper rasters the whole" \
    "graph every map_update_interval (m5_ver3/slam.yaml) and the topic" \
    "is transient-local, so a late subscriber gets the last one -" \
    "unless there has never been one." \
    "THE POSE GRAPH IS ALREADY SAVED in $OUT and IS the map; what is" \
    "missing is a rendering of it."
sed -n 's/^/  /p' "$LOGS/map_topic.log" | head -10

echo ""
echo "saving the occupancy grid..."
# NO use_sim_time ON THE SAVER, DELIBERATELY. The bag has ended by the
#    time it runs, so /clock has stopped: a node on sim time would have a
#    frozen clock and every bounded wait inside it would be a wait that
#    never ends. It needs no clock at all - it subscribes to a
#    transient-local topic, takes the last message and writes two files.
#  AND ITS OWN DEADLINE IS RAISED, WHICH IS A DIFFERENT NUMBER FROM THE
#    `timeout` AROUND IT. map_saver_cli declares `save_map_timeout` at
#    2.0 s and gives up on its own subscription when it expires - it
#    exits 1 in two seconds with "Failed to spin map subscription", so
#    the shell's bound never comes into it. MEASURED on this rig
#    2026-08-26: against slam_toolbox's /map at the end of a 750-node run
#    the shipped 2.0 s is not enough, and the first build of this map
#    refused at the last step with a complete pose graph already on disk.
#    THE VALUE IS SPELLED WITH A DECIMAL POINT because the parameter is a
#    double and `:=120` is parsed as an integer and REFUSED by rclcpp.
#  AND NO --occ / --free, WHICH IS THE POINT OF THE CHECK BELOW.
#    map_saver_cli advertises both in its own --help and ignores both:
#    measured on this rig, `--occ 0.77 --free 0.33` writes 0.65 and 0.196
#    into the yaml anyway. Passing a flag that does nothing would make
#    this script look as though it had decided something, so it passes
#    neither and CHECKS what landed instead.
( cd "$OUT" && timeout "$CFG_MAP_SLAM_SAVE_TIMEOUT_S" \
    ros2 run nav2_map_server map_saver_cli \
    -f "$NAME" -t map \
    --ros-args -p save_map_timeout:="$CFG_MAP_SLAM_SAVE_MAP_TIMEOUT_S" ) \
    > "$LOGS/map_save.log" 2>&1 || refuse \
    "map_saver_cli wrote the grid inside ${CFG_MAP_SLAM_SAVE_TIMEOUT_S}s" \
    "$LOGS/map_save.log (config.yaml map.slam.save_timeout_s and" \
    "map.slam.save_map_timeout_s)" \
    "the grid WAS on the wire - the check above passed - so this is the" \
    "saver's own deadline or its file write, not a missing map."
[ -f "$OUT/$NAME.pgm" ] && [ -f "$OUT/$NAME.yaml" ] || refuse \
    "the grid landed on disk" "$OUT" \
    "map_saver_cli exited 0 and $NAME.pgm/.yaml are not there."

# THE THRESHOLDS THE ARTIFACT ACTUALLY CARRIES, READ BACK OFF IT. They
# decide which cells a consumer calls wall and which it calls floor, and
# 205 - slam_toolbox's UNKNOWN - is a shade of 0.19608, a whisker above
# the 0.196 that landed. At a free threshold of 0.25 every unknown cell
# in this grid would read as open floor. config.yaml says which two
# values are expected; this refuses if the saver ever writes others.
for pair in "occupied_thresh $CFG_MAP_SLAM_OCCUPIED_THRESH" \
            "free_thresh $CFG_MAP_SLAM_FREE_THRESH"; do
    key="${pair%% *}"; want="${pair##* }"
    got="$(sed -n "s/^${key}: *//p" "$OUT/$NAME.yaml" | head -1)"
    [ "$got" = "$want" ] || refuse \
        "the saved grid carries the $key config.yaml expects" \
        "$OUT/$NAME.yaml (config.yaml map.slam.$key)" \
        "it reads '$got' and config.yaml says '$want'." \
        "map_saver_cli's --occ/--free flags do NOT set these - measured -" \
        "so a change here is a change in nav2, not in this repository."
done
echo "  $NAME.pgm + $NAME.yaml   (occupied_thresh $CFG_MAP_SLAM_OCCUPIED_THRESH, free_thresh $CFG_MAP_SLAM_FREE_THRESH, both checked)"

# 6. THE MANIFEST. What this artifact was built from, beside it, so the
#    map can be traced to a session without opening a report.
{
    echo "# built by tools/build_map.sh on $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    echo "name: $NAME"
    echo "session: ${SESSION#$REPO/}"
    echo "profile: $PROFILE"
    echo "traction: $TRACTION"
    echo "arm: $ARM"
    echo "bag_storage: $CFG_EVIDENCE_BAG_STORAGE"
    echo "slam_package: $CFG_MAP_SLAM_PACKAGE $(ros2 pkg xml "$CFG_MAP_SLAM_PACKAGE" --tag version 2>/dev/null || echo '?')"
    echo "slam_executable: $CFG_MAP_SLAM_EXECUTABLE"
    echo "slam_params: $CFG_MAP_SLAM_PARAMS_FILE"
    echo "slam_params_md5: $(md5sum "$REPO/$CFG_MAP_SLAM_PARAMS_FILE" | cut -d' ' -f1)"
    echo "play_rate: $CFG_MAP_SLAM_PLAY_RATE"
    echo "occupied_thresh: $CFG_MAP_SLAM_OCCUPIED_THRESH"
    echo "free_thresh: $CFG_MAP_SLAM_FREE_THRESH"
    echo "scan_topic: $CFG_TOPICS_SCAN_NAV"
    echo "base_frame: $CFG_FRAMES_BASE_LINK"
    echo "odom_frame: $CFG_FRAMES_ODOM"
    echo "map_frame: $CFG_FRAMES_MAP"
    echo "nav_lidar_mount: $CFG_VEHICLE_NAV_LIDAR_MOUNT_X $CFG_VEHICLE_NAV_LIDAR_MOUNT_Y $CFG_VEHICLE_NAV_LIDAR_MOUNT_Z"
    for f in "$NAME.pgm" "$NAME.yaml" "$NAME.posegraph" "$NAME.data"; do
        echo "md5_$f: $(md5sum "$OUT/$f" | cut -d' ' -f1)"
    done
} > "$OUT/build.txt"

echo ""
echo "artifact written: $OUT"
sed -n 's/^/  /p' "$OUT/build.txt"
echo ""
echo "register and score it:"
echo "  python3 m5_ver3/tools/map_register.py derive --map $CFG_MAP_DIR/$NAME/$NAME.yaml --write"
