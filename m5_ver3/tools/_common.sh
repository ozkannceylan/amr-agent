# _common.sh - the three things every m5-ver3 script does before it can do
# anything of its own: refuse in one voice, read config.yaml, and source
# ROS. SOURCED, never executed - it has no subcommand and no main, and it
# is deliberately not marked executable.
#
#   TOOL=m5v3 . "$M5V3/tools/_common.sh"
#
# WHY IT EXISTS. m5v3.sh and tools/rtf_probe.sh each had their own copy of
# the nine-line YAML walk, their own refuse() and their own spelling of
# /opt/ros/jazzy/setup.bash. Two copies of a MECHANISM drift the same way
# two copies of a VALUE do - the first one to be fixed is the one that is
# right - and the ROS path was a behavioural constant living inline in a
# script, which is exactly what config.yaml's own header disclaims. All
# three now live once: the mechanism here, the path in config.yaml.
#
# IT SETS $REPO, $M5V3 and $CONFIG from its OWN location, so a caller
# cannot point it at a config.yaml belonging to another tree by getting
# its own path arithmetic wrong. BASH_SOURCE[0] inside a sourced file is
# that file, whatever sourced it.
M5V3="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO="$(cd "$M5V3/.." && pwd)"
CONFIG="$M5V3/config.yaml"
# The name the refusals speak under. A caller that forgets it gets one
# here rather than an unbound-variable abort in the middle of a refusal,
# which would be the worst possible moment to lose the message.
TOOL="${TOOL:-m5v3}"

# EVERY REFUSAL NAMES THE CHECK AND THE FILE THAT OWNS IT. An operator who
# is refused needs two things - which test said no, and where the answer it
# tested against is written - and a bare exit gives neither. The
# continuation lines are indented under the tool's own name so a refusal
# reads as one block however it is spelled.
refuse() {  # refuse <check> <owning file> [line...]
    local check="$1" owner="$2" pad
    shift 2
    pad="$(printf '%*s' "$(( ${#TOOL} + 2 ))" '')"
    echo "$TOOL: REFUSED at check '$check'"
    echo "${pad}owned by: $owner"
    [ "$#" -gt 0 ] && printf "${pad}%s\n" "$@"
    exit 1
}

# THE ONE READER OF config.yaml, and the shape is m6.sh's vehicle_table():
# a shell cannot import, so the table is read by a subprocess and eval'd.
# Every scalar comes back as CFG_<DOTTED_KEY_UPPERCASED>, shell-quoted, so
# a value with a space in it cannot become two words.
config_env() {
    python3 -c 'import shlex, sys, yaml
def walk(node, path):
    if isinstance(node, dict):
        for key, value in node.items():
            walk(value, path + [str(key)])
    else:
        print("CFG_{}={}".format("_".join(path).upper(), shlex.quote(str(node))))
with open(sys.argv[1], "r", encoding="utf-8") as handle:
    walk(yaml.safe_load(handle), [])' "$CONFIG" 2>/dev/null
}

# THE STACK AS COMMAND-LINE PATTERNS, and it lives here because TWO
# scripts ask the question. m5v3.sh sweeps by this list and rtf_probe.sh
# prints the stack a figure was taken under by it; they carried a copy
# each until F1 Task 3 added the odometry node to one of them and the
# probe went on reporting a stack with no estimator in it. That is what a
# duplicated mechanism costs when the duplicate is a LIST: nothing breaks,
# it just quietly says something that is not true.
#   A PATTERN ONLY NOMINATES - the caller's ours() decides - and `gz sim`
#   is FIRST because that is where the motion lives (m5v3.sh's stop()).
#   `gz sim` NOMINATES THE CLIENT AND THE SERVER ALIKE: both command
#   lines begin with those two words, and the gated wrapper that becomes
#   the client carries them in its -c string until it execs.
#   image_bridge IS A SEPARATE PATTERN and not covered by the one before
#   it: ros_gz's depth-image bridge is its own executable with its own
#   name, and `parameter_bridge` does not match it.
#   wheel_odometry.py IS ITS OWN PATTERN because it is a plain python3
#   process: its command line begins with the interpreter, so nothing
#   else here nominates it. The pattern is the SCRIPT NAME rather than
#   "python3", which would nominate every python on the machine and lean
#   the whole safety of the sweep on ours() alone.
#   ekf_node AND static_transform_publisher ARE F2 TASK 1's, and each is
#   its own pattern for wheel_odometry.py's reason: both are started
#   through `ros2 run`, so the surviving process is the EXECUTABLE and
#   its command line begins with the path to it. Neither is nominated by
#   anything above.
#     static_transform_publisher NOMINATES BOTH OF THEM since F2 Task 3:
#     the IMU's mount and - with --rf2o - the nav lidar's are two
#     processes of the same executable, and one pattern finds both.
#   THE LAST TWO ARE F2 TASK 3's OPTIONAL ARM and they are listed
#   UNCONDITIONALLY, which is the safe direction: a pattern that
#   nominates nothing costs one pgrep, and a pattern that is missing
#   when the flag WAS given orphans a live child. rf2o's executable
#   lives under the user's $HOME (config.yaml rf2o.workspace) so its
#   command line begins with that path; rf2o_twist.py is a plain python3
#   process and is named by its SCRIPT, exactly as wheel_odometry.py is.
# MAINTENANCE OBLIGATION: a process added to m5v3.sh's start() is added
# HERE, or stop orphans it and still prints "down."
M5V3_PATTERNS=("gz sim" "parameter_bridge" "image_bridge" "wheel_odometry.py"
               "static_transform_publisher" "ekf_node"
               "rf2o_laser_odometry_node" "rf2o_twist.py")

# The same list as one pgrep alternation, for the callers that want a
# single pattern rather than a loop.
patterns_re() {
    local IFS='|'
    printf '%s\n' "${M5V3_PATTERNS[*]}"
}

# THE KEYS EVERY m5-ver3 SCRIPT NEEDS, checked and exported here so no two
# of them can disagree about which graph this is or where ROS lives. A
# caller adds its own required keys as arguments.
#   GZ_PARTITION IS THE ONE THAT SCOPES GAZEBO - gz transport is not DDS,
#   so ROS_DOMAIN_ID isolates only the ROS side - and it is what ours()
#   reads back out of a candidate process to decide the sweep may kill it.
#   Neither is overridable from the environment: start, stop, status and
#   the probe all read the same file, so the four cannot drift apart.
_COMMON_KEYS=(isolation.gz_partition isolation.ros_domain_id paths.ros_setup)

# EVERY KEY A SCRIPT READS, CHECKED BY NAME AFTER THE PARSE. A config.yaml
# that parses but has been reorganised would otherwise reach the sweep with
# an empty partition - and an empty partition matches the environment of
# nothing at all, which is a stop that silently spares a live stack. Under
# `set -u` a missing key aborts with bash's own message about a variable
# nobody but this file has heard of; checked here it is refused by its
# DOTTED name, which is what the operator has to go and edit.
load_config() {  # load_config <extra required dotted key>...
    local env key var
    env="$(config_env)"
    [ -n "$env" ] || refuse "config.yaml is readable" "$CONFIG" \
        "read it by hand: python3 -c 'import yaml; yaml.safe_load(open(\"$CONFIG\"))'"
    # No `local` on the CFG_* names, so they land as globals for the
    # caller - that is the whole point of eval'ing them here.
    eval "$env"
    for key in "${_COMMON_KEYS[@]}" "$@"; do
        var="CFG_$(printf '%s' "$key" | tr 'a-z.' 'A-Z_')"
        [ -n "${!var:-}" ] || refuse "config.yaml defines $key" "$CONFIG" \
            "the parse succeeded, so the key is missing or renamed, not unreadable"
    done
    export GZ_PARTITION="$CFG_ISOLATION_GZ_PARTITION"
    export ROS_DOMAIN_ID="$CFG_ISOLATION_ROS_DOMAIN_ID"
    ROS_SETUP="$CFG_PATHS_ROS_SETUP"
}

# ROS IS SOURCED FOR gz ITSELF, not only for ROS nodes: gz_tools_vendor
# lives under /opt/ros, so `gz sim`, `gz service` and `gz topic` all need
# it. `set -u` stands down across the source because ament's hook reads
# AMENT_TRACE_SETUP_FILES before setting it, and the caller's own `set -u`
# would die on that line.
source_ros() {
    [ -f "$ROS_SETUP" ] || refuse "ROS 2 Jazzy is installed" "$CONFIG" \
        "paths.ros_setup resolves to $ROS_SETUP" \
        "this stack runs inside WSL - see CONTEXT.md"
    set +u
    # shellcheck disable=SC1090
    . "$ROS_SETUP"
    set -u
}
