# _truck_common.sh - what m6_ver2/truck.sh needs before it can start a
# child: the donor's refusal voice and config reader, pointed at THIS
# TRUCK's derived config, and a sweep that can tell four trucks apart.
# SOURCED, never executed - it has no subcommand and no main, and it is
# deliberately not marked executable.
#
#   VID=f1 TOOL="m6v2-truck:f1" . "$M6V2/tools/_truck_common.sh"
#
# ---- THE SEAM, AND WHY IT IS A SOURCE RATHER THAN A COPY ----
#
# m5_ver3/tools/_common.sh already owns three mechanisms this runner
# needs and must not re-spell: refuse() (name the check and the file
# that owns it), the config_env/load_config pair (the YAML walk that
# turns a config into CFG_<DOTTED_KEY> globals, checked by dotted name),
# and source_ros(). Two copies of a MECHANISM drift the way two copies
# of a VALUE do - that file's own header - so this one SOURCES it.
# AMR-DEC-006 freezes m5_ver3/ byte for byte; sourcing is reading, and
# nothing here writes to it.
#
# WHAT HAS TO BE OVERRIDDEN, AND THE HONEST WAY TO SAY SO. That file
# binds `CONFIG="$M5V3/config.yaml"` from its own location, and its
# header states the reason: a caller cannot point it at another tree's
# config by getting its own path arithmetic wrong. This runner is the
# one caller for which that is not a mistake but the whole design -
# SPEC_NAMESPACING.md 3 derives a config.yaml PER TRUCK, of the same
# schema, by a counted rewrite of that very file - so `truck_config`
# re-points CONFIG at the derived copy and then PROVES the re-point
# took, by reading back the one key the two files must differ on
# (isolation.gz_partition: the donor says m5v3, every derived config
# says m6). A silent fall-back to the donor's config would export
# GZ_PARTITION=m5v3 and put four trucks in the wrong graph, which is
# exactly the class of failure this whole track spends its checks on.
#
# NOTHING HERE STARTS ANYTHING. It reads, it exports and it nominates.

_M6V2_TOOLS="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
M6V2="$(cd "$_M6V2_TOOLS/.." && pwd)"
M6V2_REPO="$(cd "$M6V2/.." && pwd)"
_M6V2_DONOR_COMMON="$M6V2_REPO/m5_ver3/tools/_common.sh"

if [ ! -f "$_M6V2_DONOR_COMMON" ]; then
    echo "${TOOL:-m6v2-truck}: REFUSED at check 'the m5_ver3 donor stands beside m6_ver2'"
    echo "  owned by: AMR-DEC-006 (m5_ver3/ is frozen, not vendored)"
    echo "  $_M6V2_DONOR_COMMON is not there, so there is no refusal voice,"
    echo "  no config reader and no ROS setup path. m6_ver2 is not a copy"
    echo "  that runs on its own."
    exit 1
fi
# shellcheck disable=SC1090
. "$_M6V2_DONOR_COMMON"

#: The world's partition. One string, and truck_config refuses a config
#: that does not agree with it.
M6V2_PARTITION="m6"

# THIS TRUCK'S DERIVED CONFIG, AND THE PROOF THAT IT IS THE ONE BEING
# READ. Every key m5_ver3/config.yaml defines is defined here too (the
# derivation is a rewrite of values, never of keys), so `load_config`'s
# dotted-name check covers the caller's list unchanged.
truck_config() {  # truck_config <vid> <extra required dotted key>...
    local vid="$1"
    shift
    VEHICLE_DIR="$M6V2/vehicles/$vid"
    CONFIG="$VEHICLE_DIR/config.yaml"
    [ -f "$CONFIG" ] || refuse \
        "this truck's derived config exists" \
        "m6_ver2/tools/instantiate_truck.py (SPEC_NAMESPACING.md 3)" \
        "$CONFIG is not there. The per-vid tree is a BUILD PRODUCT and" \
        "is gitignored, so a fresh checkout has none of it." \
        "derive it: python3 m6_ver2/tools/instantiate_truck.py --all" \
        "NOTHING WAS STARTED."
    load_config "$@"
    # THE RE-POINT, READ BACK. If CONFIG had silently stayed the
    # donor's, every name below would be m5v3's and the truck would come
    # up in the wrong gz partition on the wrong domain, with nothing
    # saying so - the frames would be bare, the topics would collide and
    # `status` would look perfect.
    [ "$CFG_ISOLATION_GZ_PARTITION" = "$M6V2_PARTITION" ] || refuse \
        "the config this runner read is the DERIVED one" \
        "$CONFIG (isolation.gz_partition) and $_M6V2_DONOR_COMMON" \
        "isolation.gz_partition reads '$CFG_ISOLATION_GZ_PARTITION' and" \
        "this world is '$M6V2_PARTITION'. m5_ver3/config.yaml says" \
        "'m5v3'; a derived one says '$M6V2_PARTITION' (SPEC_NAMESPACING.md 3.3)." \
        "Either the derivation is stale or CONFIG was never re-pointed," \
        "and both put this truck in a graph it does not belong to." \
        "NOTHING WAS STARTED."
    # EVERY CHILD CARRIES THE VID, and it is what makes the sweep safe -
    # see truck_ours(). load_config exported the partition and the
    # domain; this is the third line of the triple.
    export M6V2_VID="$vid"
}

# THE STACK AS COMMAND-LINE PATTERNS, and this list is m5_ver3/tools/
# _common.sh's M5V3_PATTERNS with the world-owned and the dark ones
# removed and this track's three own children added.
#   WHAT CAME OUT AND WHY. `gz sim`, `parameter_bridge`, `image_bridge`
#   and `nav2_map_server` are the WORLD's (SPEC_NAMESPACING.md 4: one
#   server, one bridge, one map_server, one owner) - a truck runner that
#   swept them would take the floor out from under its three neighbours.
#   `apriltag_node`, `opennav_docking` and `detected_dock.py` are dark
#   with docking and this runner cannot start them.
#   WHAT STAYED THAT THIS RUNNER NEVER STARTS - the rf2o, fuse and slam
#   arms, and cmd_vel_tricycle.py, which DEC-006 retired - stayed for
#   the donor's stated reason: a pattern that nominates nothing costs
#   one pgrep, and a pattern that is missing when the child WAS started
#   orphans it. truck_ours() is what keeps any of them from reaching a
#   process that is not this truck's.
# MAINTENANCE OBLIGATION, inherited: a process added to truck.sh's
# start() is added HERE, or stop orphans it and still prints "down."
M6V2_PATTERNS=("wheel_odometry.py" "static_transform_publisher" "ekf_node"
               "rf2o_laser_odometry_node" "rf2o_twist.py"
               "fixed_lag_smoother_node"
               "nav2_amcl" "localization_slam_toolbox_node"
               "velocity_smoother" "cmd_vel_tricycle.py"
               "planner_server" "controller_server" "bt_navigator"
               "behavior_server" "nav2_lifecycle_manager"
               "collision_monitor"
               "scan_mask_node.py" "nav2_adapter_node.py" "nav2_seed.py")

# WHY OWNERSHIP TAKES TWO LINES HERE AND ONE IN m5v3.sh. That script
# could ask for GZ_PARTITION alone because its partition named exactly
# one stack. This one cannot: the partition is `m6`, and m6.sh's own
# fleet layer (m6.sh:48,140) and the three neighbour trucks all carry
# it. A sweep keyed on the partition would nominate the whole world.
# So every child of this runner also carries M6V2_VID and BOTH lines
# have to be in its environment before it may be killed.
#   Unreadable environ = left alone, the safe direction, and a recycled
#   pid is safe for the donor's reason: a pid that has come round to
#   name somebody else does not carry this truck in its environment.
#   2>/dev/null PRECEDES the input redirect on purpose (m6.sh:143).
truck_ours() {  # truck_ours <pid>
    local env
    env="$(tr '\0' '\n' 2>/dev/null < "/proc/$1/environ")" || return 1
    printf '%s\n' "$env" | grep -qxF "GZ_PARTITION=$GZ_PARTITION" || return 1
    printf '%s\n' "$env" | grep -qxF "M6V2_VID=$M6V2_VID" || return 1
    return 0
}

truck_sweep() {  # truck_sweep <signal>
    local sig="$1" pat pid cmd
    for pat in "${M6V2_PATTERNS[@]}"; do
        while read -r pid cmd; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            [ "$pid" = "$$" ] && continue
            # A sweep matching its own command line proves nothing:
            # these scripts quote the patterns in their own text and
            # carry the partition (demo.sh:1037, LESSONS 2026-08-06).
            case "$cmd" in
                *truck.sh*|*m6v2.sh*|*m5v3.sh*|*m6.sh*|*demo.sh*|*stack.sh*)
                    continue ;;
            esac
            truck_ours "$pid" || continue
            kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid ($pat)"
        done < <(pgrep -af "$pat" 2>/dev/null)
    done
}
