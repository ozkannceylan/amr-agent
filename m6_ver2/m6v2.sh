#!/usr/bin/env bash
# m6v2.sh - the ONE operator door to the m6v2 cell: one broker, one
# world, one shared map, and for every truck named a full m6 fleet set
# plus a full m5_ver3 autonomy stack, with one fleet manager over the
# lot.
#   start [--vids "f1 f2"] [--gui] | status | stop
#
# WHAT THIS CELL IS. Four m5_ver3 stacks - EKF, AMCL, four Nav2 servers,
# smoother, collision monitor, and the Nav2 adapter that replaces
# nav_node - running namespaced under /f1../f4 in ONE gz world beside
# the untouched m6 fleet layer (SPEC_NAMESPACING.md, SPEC_ADAPTER.md,
# both amended by AMR-DEC-006).
#
# THE DIVISION OF LABOUR, AND IT IS THE WHOLE DESIGN.
#   world.launch.py owns everything SHARED: the gz server, the four
#   model spawns, ONE parameter_bridge, ONE map_server, and the fleet's
#   two plant-side nodes per truck.
#   truck.sh owns ONE truck's autonomy stack and nothing else.
#   THIS FILE owns the ORDER, the environment, the fleet-layer children
#   and the ledger - and it starts no autonomy child of its own. Every
#   per-truck stack goes up and comes down through `truck.sh <vid>`,
#   which is why a truck can be debugged alone without this script and
#   why this script does not have to know what a bt_navigator is.
#
# GZ_PARTITION AND ROS_DOMAIN_ID ARE SET ON EVERY CHILD, so a concurrent
# m5v3 demo cannot be joined by accident, and they decide what `stop`
# may kill. But partition alone is NOT enough here and that is new:
# m6.sh uses the SAME partition (m6) for the plain m6 cell, so a sweep
# keyed on it would take a live m6 fleet down with this one. Every child
# of this script therefore also carries M6V2 in its environment and
# `ours()` requires BOTH. The exposure runs one way only: m6.sh's own
# sweep is partition-keyed and WILL nominate this cell. That is named in
# SPEC_NAMESPACING.md 9.3 and it is the reason `start` refuses when a
# plain m6 world is already up.
#
# THE VEHICLE CHILDREN RUN FROM m6/ SOURCE AND NOT FROM m6/deploy, AND
# THAT IS A NAMED LEFTOVER. m6.sh runs them from a frozen image, which
# is the deliverable of its milestone: editing a source file mid-run
# changes nothing until someone ships it. On this branch the vehicle set
# is still MOVING - the adapter is replacing nav_node under it - so a
# deploy would freeze a shape that is not yet a shape, and every debug
# cycle would carry a re-freeze it learned nothing from. The deploy
# discipline RETURNS the day the vehicle set stabilises; until then this
# script reads from source and says so here rather than quietly.
#
# It does NOT touch PLCSIM Advanced or m6.py. Those are the owner's, on
# the Windows side, and the single-writer rule is the reason this script
# has no way to start them.
set -uo pipefail

TOOL="m6v2.sh"
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
M6V2="$REPO/m6_ver2"
M6="$REPO/m6"
PIDFILE="$M6V2/.m6v2_pids"
VIDFILE="$M6V2/.m6v2_vids"
LOGDIR="$M6V2/logs"
TRUCK="$M6V2/truck.sh"
WORLD_LAUNCH="$M6V2/world.launch.py"
DERIVE="$M6V2/tools/instantiate_truck.py"
# The FLEET side's derivation and its one override. See start().
FIREWALL="$M6V2/tools/fleet_odom_firewall.py"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
# The broker is vendored into the user's home rather than installed -
# this WSL has no usable sudo - and BROKER_LIB is not optional: those
# .debs put libwrap, libdlt and libwebsockets somewhere the loader does
# not look. Both paths are m6.sh's and m6/tools/install_broker.sh's;
# a move there has to move here. ONE broker serves this machine, and
# this cell borrows m6's rather than vendoring a second copy.
BROKER_BIN="$HOME/.local/mosquitto-vendored/usr/sbin/mosquitto"
BROKER_LIB="$HOME/.local/mosquitto-vendored/usr/lib/x86_64-linux-gnu"

# THE ISOLATION PAIR IS WRITTEN HERE AS LITERALS AND CHECKED AGAINST THE
# DERIVED CONFIGS IN start(). It has two homes and that is deliberate:
# `stop` is the command an operator runs when things have already gone
# wrong, and it must not depend on a python3, a yaml parse and four
# build products being readable to find out which graph to sweep. So the
# literal is the floor, check_isolation() is the ceiling, and a
# disagreement between them is a refusal rather than a silent pick.
export GZ_PARTITION="${GZ_PARTITION:-m6}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-96}"
# DDS WITHOUT MULTICAST. Mid-session 2026-08-25 this rig's WSL multicast
# path died and FastDDS discovery went with it; the profile pins every
# participant to unicast discovery on 127.0.0.1, where all of them live
# anyway. It is m6's file, read-only, and it is not copied: two copies of
# one measurement is how the measurement stops being one.
export FASTRTPS_DEFAULT_PROFILES_FILE="${FASTRTPS_DEFAULT_PROFILES_FILE:-$M6/tools/fastdds_loopback.xml}"
# THE MARKER. Everything this script spawns inherits it, and truck.sh
# stamps M6V2_VID=<vid> on every child of its own, so a `^M6V2` line in
# a process's environ is the definition of "in this cell" - see ours().
export M6V2=1

# start's default is HEADLESS, which is the other way round from m6.sh.
# That script opens a window because watching the trucks stop IS its
# milestone; this one carries four Nav2 stacks on a world already
# measured at 0.575 RTF, and rendering here is llvmpipe unless the GPU
# pair below resolves. --gui opts back in for a demonstration.
GUI=false
VIDS=()

refuse() {  # refuse <check> <owning file> [line...]
    local check="$1" owner="$2" pad
    shift 2
    pad="$(printf '%*s' "$(( ${#TOOL} + 2 ))" '')"
    echo "$TOOL: REFUSED at check '$check'"
    echo "${pad}owned by: $owner"
    [ "$#" -gt 0 ] && printf "${pad}%s\n" "$@"
    return 1
}

# ONE ENV-FREE READ OF THE ONE TABLE, exactly as m6.sh does it: a shell
# cannot import, so the table is read by a subprocess. It is a FUNCTION
# and not a global for m6.sh's reason - `stop` must not depend on an
# interpreter, a PYTHONPATH and a parseable table.
vehicle_table() {  # one line per vehicle: "<vid> <plc_port>", sorted
    PYTHONPATH="$M6/ipc" python3 -c 'import status_contract
for vid, v in sorted(status_contract.VEHICLES.items()):
    print(vid, v["plc_port"])' 2>/dev/null
}
no_table() {
    refuse "the VEHICLES table is readable" \
        "$M6/ipc/status_contract.py" \
        "try it by hand: PYTHONPATH=$M6/ipc python3 -c 'import status_contract'"
}

# One scalar out of one truck's DERIVED config. Every value this script
# needs that is not a path is read this way, so the derivation is the one
# home for it and this file holds no second copy.
derived_get() {  # derived_get <vid> <dotted.key>
    python3 -c 'import sys, yaml
node = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    node = node[part]
print(node)' "$M6V2/vehicles/$1/config.yaml" "$2" 2>/dev/null
}

# The stack as command-line patterns, in SHUTDOWN ORDER, top to bottom.
# It is m6.sh's list with two changes and no others:
#   - nav_node.py is GONE. AMR-DEC-006 retires it as the motion engine;
#     the Nav2 adapter takes its place and is truck.sh's child, not this
#     script's.
#   - m6_world.launch.py becomes world.launch.py.
# A pattern only NOMINATES; ours() decides. THE PER-TRUCK STACK IS
# DELIBERATELY ABSENT: truck.sh owns that list and `truck.sh <vid> stop`
# runs before any of this, and a second copy of it here would be the
# copy that kept working after the first one changed. sweep_marked()
# below is the net that catches whatever truck.sh left behind, and it
# needs no list at all.
PATTERNS=("gz sim" "world.launch.py" "parameter_bridge" \
          "sto_contactor.py" "forklift_io.py" "plc_link.py" "cmd_gate.py" \
          "cmd_mux.py" "hmi_node.py" "field_eval.py" "sensor_link.py" \
          "encoder_link.py" "fleet_manager.py" \
          "vda_agent.py" "mosquitto-vendored")

# OWNERSHIP IS DECIDED BY THE ENVIRONMENT AND NEEDS BOTH LINES.
#   GZ_PARTITION is what "this graph" means to Gazebo and is inherited by
#   every child through ros2 launch. On its own it is NOT enough here:
#   m6.sh exports GZ_PARTITION=m6 too, so partition alone would make this
#   script's stop take a live m6 fleet down - the neighbour it was built
#   to stand beside. The second line is the M6V2 marker, stamped by this
#   script on everything it spawns and by truck.sh as M6V2_VID=<vid> on
#   everything IT spawns, so `^M6V2` covers both without either file
#   knowing the other's spelling.
#   Unreadable environ = left alone, the safe direction.
ours() {
    local environ
    environ="$(tr '\0' '\n' 2>/dev/null < "/proc/$1/environ")"
    printf '%s\n' "$environ" | grep -qxF "GZ_PARTITION=$GZ_PARTITION" \
        || return 1
    printf '%s\n' "$environ" | grep -q '^M6V2'
}

# THE PID FILE IS THE INPUT ours() DOES NOT GUARD. Only stop deletes it,
# so a reboot or a closed terminal leaves it on disk and Linux recycles
# pids within minutes. A recorded number can therefore name a STRANGER.
# Every command line this script records carries m6 - the world, the
# fleet children under $M6/ipc, the truck runner under m6_ver2 - except
# the broker, whose path is in the user's HOME and which gets its own
# token, or every start would report it as having exited.
recorded() {
    grep -qaF -e "m6" -e "mosquitto-vendored" \
        "/proc/$1/cmdline" 2>/dev/null
}

sweep_named() {  # sweep_named <signal> - the patterns, in order
    local sig="$1" pat pid cmd
    for pat in "${PATTERNS[@]}"; do
        while read -r pid cmd; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            [ "$pid" = "$$" ] && continue
            # A sweep matching its own command line proves nothing: these
            # scripts quote the patterns in their own text AND carry the
            # partition and the marker.
            case "$cmd" in *m6v2.sh*|*truck.sh*|*m6.sh*|*demo.sh*|*stack.sh*|*m5v3.sh*)
                continue ;;
            esac
            ours "$pid" || continue
            kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid ($pat)"
        done < <(pgrep -af "$pat" 2>/dev/null)
    done
}

# AND THE NET THAT NEEDS NO LIST. ours() IS the definition of this cell -
# our partition AND our marker - so walking /proc and applying it
# directly catches every child of truck.sh without this file holding a
# second copy of truck.sh's pattern list. It runs AFTER sweep_named so
# the ordered shutdown still happens in order; what is left by then is
# the residue, and residue has no order worth keeping.
sweep_marked() {  # sweep_marked <signal>
    local sig="$1" pid cmd
    for pid in /proc/[0-9]*; do
        pid="${pid#/proc/}"
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        [ "$pid" = "$$" ] && continue
        cmd="$(tr '\0' ' ' 2>/dev/null < "/proc/$pid/cmdline")"
        # A KERNEL THREAD HAS AN EMPTY cmdline AND NO environ TO READ, so
        # it is skipped before ours() is asked - the check would say no
        # anyway, and asking it 200 times per stop is the cost.
        [ -n "$cmd" ] || continue
        case "$cmd" in *m6v2.sh*|*truck.sh*|*m6.sh*|*demo.sh*|*stack.sh*|*m5v3.sh*)
            continue ;;
        esac
        ours "$pid" || continue
        kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid (marked)"
    done
}

sweep() {  # sweep <signal>
    sweep_named "$1"
    sweep_marked "$1"
}

# ----------------------------------------------------------------------
# PREFLIGHT
# ----------------------------------------------------------------------

# THE ISOLATION PAIR HAS TWO HOMES AND THE DISAGREEMENT IS REFUSED.
# instantiate_truck.py rewrites isolation.gz_partition to m6 and
# isolation.ros_domain_id to 96 in every derived config, and truck.sh
# exports the pair FROM THERE on every child it spawns. This script's
# literals are the floor (see the export block); if the derivation ever
# said something else, half this cell would be on one graph and half on
# another, and the symptom would be topics that exist and carry nothing.
check_isolation() {
    local vid part dom
    for vid in "${VIDS[@]}"; do
        part="$(derived_get "$vid" isolation.gz_partition)"
        dom="$(derived_get "$vid" isolation.ros_domain_id)"
        [ "$part" = "$GZ_PARTITION" ] || { refuse \
            "the derived config and this script name one partition" \
            "m6_ver2/vehicles/$vid/config.yaml (isolation.gz_partition)" \
            "the derivation says '$part' and this script exports '$GZ_PARTITION'." \
            "truck.sh exports the pair from the DERIVATION, so half this" \
            "cell would land on a graph the other half cannot see." \
            "NOTHING WAS STARTED."; return 1; }
        [ "$dom" = "$ROS_DOMAIN_ID" ] || { refuse \
            "the derived config and this script name one ROS domain" \
            "m6_ver2/vehicles/$vid/config.yaml (isolation.ros_domain_id)" \
            "the derivation says '$dom' and this script exports '$ROS_DOMAIN_ID'." \
            "NOTHING WAS STARTED."; return 1; }
    done
}

# THE RENDERER GATE, PORTED FROM m5v3.sh's gpu_preflight. The two
# exports and the required substring come from the DERIVED config (the
# donor's gpu block, carried through the rewrite unchanged), so this
# script holds no copy of them.
#   IT IS UNCONDITIONAL, INCLUDING HEADLESS. Every lidar in this world is
#   GPU-rendered - three safety scanners and a nav lidar per truck,
#   sixteen at four - so a run that fell back to llvmpipe is not a slower
#   version of this cell, it is a different machine, and the RTF question
#   SPEC_NAMESPACING.md 9.4 leaves open cannot be answered on it.
gpu_preflight() {
    local driver adapter required info renderer
    driver="$(derived_get "${VIDS[0]}" gpu.gallium_driver)"
    adapter="$(derived_get "${VIDS[0]}" gpu.d3d12_adapter_name)"
    required="$(derived_get "${VIDS[0]}" gpu.required_renderer)"
    [ -n "$driver" ] && [ -n "$adapter" ] && [ -n "$required" ] || { refuse \
        "the derived config carries a gpu block" \
        "m6_ver2/vehicles/${VIDS[0]}/config.yaml (gpu:)" \
        "gallium_driver, d3d12_adapter_name and required_renderer are" \
        "what this gate exports and tests, and one of them did not read."
        return 1; }
    export GALLIUM_DRIVER="$driver"
    export MESA_D3D12_DEFAULT_ADAPTER_NAME="$adapter"
    command -v glxinfo >/dev/null 2>&1 || { refuse \
        "glxinfo is installed" "$TOOL (gpu_preflight)" \
        "without it there is no way to ask what the GL stack resolved to," \
        "and a run that cannot ask must not assume: apt install mesa-utils"
        return 1; }
    # Captured whole and matched afterwards rather than piped into a
    # `grep -q`: an early reader exit turns the writer's SIGPIPE into the
    # pipeline's status under `set -o pipefail`, and a gate that fails
    # OPEN is worse here than no gate (m6.sh:227-240, measured).
    info="$(glxinfo -B 2>&1)"
    renderer="$(printf '%s\n' "$info" | sed -n 's/^OpenGL renderer string: //p')"
    { echo "# m6v2 GPU preflight, $(date -Is)"
      echo "# GALLIUM_DRIVER=$GALLIUM_DRIVER"
      echo "# MESA_D3D12_DEFAULT_ADAPTER_NAME=$MESA_D3D12_DEFAULT_ADAPTER_NAME"
      echo "# required renderer substring: $required"
      echo "# renderer: ${renderer:-<none reported>}"
      echo ""
      printf '%s\n' "$info"; } > "$LOGDIR/gpu_preflight.log"
    case "$renderer" in
        *"$required"*) echo "  gpu: $renderer" ;;
        *)  refuse "the renderer names $required" \
                "m6_ver2/vehicles/${VIDS[0]}/config.yaml (gpu.required_renderer)" \
                "renderer is: ${renderer:-<none reported>}" \
                "the two exports this check makes are" \
                "  GALLIUM_DRIVER=$driver" \
                "  MESA_D3D12_DEFAULT_ADAPTER_NAME=$adapter" \
                "and with them this rig reports D3D12 (NVIDIA ...)." \
                "NOTHING WAS STARTED. Do not work around this by rendering" \
                "on the CPU: llvmpipe measures a different machine, and" \
                "four Nav2 stacks is the load this gate exists to measure." \
                "full glxinfo reply: $LOGDIR/gpu_preflight.log"
            return 1 ;;
    esac
}

# TWO SERVERS IN ONE PARTITION IS ONE WORLD WITH TWO OWNERS.
# m6.sh's cell runs `gz sim` on the same warehouse in the same partition
# m6 - so a plain m6 world already up would take this launch's four
# spawns into ITS world, and both bridges would publish every terminal.
# The test is precise rather than by name: a gz server or an m6 world
# launch that carries OUR partition and does NOT carry the M6V2 marker
# is, by definition, the other cell's.
plain_m6_cell() {  # prints "<pid> <cmdline>" and returns 0 if one is up
    local pid cmd environ
    while read -r pid cmd; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        [ "$pid" = "$$" ] && continue
        case "$cmd" in *m6v2.sh*|*truck.sh*|*m6.sh*) continue ;; esac
        environ="$(tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ")"
        printf '%s\n' "$environ" | grep -qxF "GZ_PARTITION=$GZ_PARTITION" \
            || continue
        printf '%s\n' "$environ" | grep -q '^M6V2' && continue
        echo "$pid $cmd"
        return 0
    done < <({ pgrep -af "m6_world.launch.py" 2>/dev/null
               pgrep -af "gz sim" 2>/dev/null; })
    return 1
}

# ----------------------------------------------------------------------
# START
# ----------------------------------------------------------------------
start() {
    local pid name vid port i other
    local -a TABLE=() PORTS=()
    while read -r vid port; do
        [ -n "$vid" ] || continue
        TABLE+=("$vid"); PORTS+=("$port")
    done < <(vehicle_table)
    [ "${#TABLE[@]}" -gt 0 ] || { no_table; return 1; }
    # NO --vids IS THE WHOLE TABLE. G1's gate runs one truck; the cell
    # this branch is for is four, and nothing has to be said to get it.
    [ "${#VIDS[@]}" -gt 0 ] || VIDS=("${TABLE[@]}")
    for vid in "${VIDS[@]}"; do
        case " ${TABLE[*]} " in
            *" $vid "*) ;;
            *) refuse "every named truck is in the VEHICLES table" \
                   "$M6/ipc/status_contract.py (VEHICLES)" \
                   "--vids names '$vid', which the table does not have." \
                   "The table holds: ${TABLE[*]}"; return 1 ;;
        esac
    done

    # ALREADY UP? recorded() too: a recycled pid would make start refuse
    # against a cell that is not there, and the message would send the
    # operator to a stop that then has to be right about the same pid.
    if [ -f "$PIDFILE" ]; then
        while read -r pid name; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            if kill -0 "$pid" 2>/dev/null && recorded "$pid"; then
                refuse "this cell is not already up" "$PIDFILE" \
                    "${name:-a child} is alive at pid $pid." \
                    "Run '$0 stop' first."
                return 1
            fi
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi

    other="$(plain_m6_cell)" && { refuse \
        "no plain m6 world is up in partition $GZ_PARTITION" \
        "m6/m6.sh (SPEC_NAMESPACING.md 9.3)" \
        "  $other" \
        "That process carries GZ_PARTITION=$GZ_PARTITION and no M6V2" \
        "marker, so it is m6.sh's cell and not this one. TWO SERVERS IN" \
        "ONE PARTITION IS ONE WORLD WITH TWO OWNERS: this launch's spawns" \
        "would land in that world and both bridges would publish every" \
        "terminal twice." \
        "NOTHING WAS STARTED. Take the other cell down first:" \
        "  bash $M6/m6.sh stop"; return 1; }

    # THE DERIVATION IS THE SOFTWARE HERE, and a stale one is the worst
    # failure this cell has: the world spawns a model whose frames and
    # topics no longer match the params the stack is handed, and every
    # symptom is a SILENCE - a costmap with no scan, an AMCL with no map.
    # The tool's own --check re-derives from the donor bytes and compares,
    # which is the only test that can see it. world.launch.py runs the
    # same check at import; this one is here so the refusal arrives
    # BEFORE the broker and the log dir, not after.
    for vid in "${VIDS[@]}"; do
        python3 "$DERIVE" --vid "$vid" --check || { refuse \
            "the derivation on disk is the one the tool writes" \
            "m6_ver2/tools/instantiate_truck.py" \
            "$vid is stale or missing - the tool's own reply is above." \
            "NOTHING WAS STARTED. Re-derive:" \
            "  python3 m6_ver2/tools/instantiate_truck.py --all"; return 1; }
        # m6's derived pair is this cell's too: sto_contactor.py and
        # forklift_io.py read m6's spelling of the terminals and the
        # m5v3 schema does not carry it.
        #   IT IS MADE HERE AND FIREWALLED IN THE SAME BREATH, and the
        # two are one command because doing the first without the second
        # is the silent failure. fleet_odom_firewall.py runs m6's OWN
        # tool (which owns those bytes) and then applies SPEC_ADAPTER.md
        # Decision 4's single override: topics.gz_odom - the key
        # vda_agent.py and hmi_node.py subscribe - is pointed at
        # /<vid>/est/odom, the adapter's estimate, instead of
        # /<vid>/gz/odom, the simulator's own truth. Unfirewalled, the
        # fleet counts route progress with an instrument no real truck
        # has, the world comes up, the trucks drive, and nothing says
        # so. It writes only gitignored build products.
        python3 "$FIREWALL" --vid "$vid" || { refuse \
            "the fleet's odom key reads the adapter's estimate" \
            "m6_ver2/tools/fleet_odom_firewall.py (SPEC_ADAPTER.md Decision 4)" \
            "$vid's fleet config could not be derived or firewalled;" \
            "the tool's own reply is above." \
            "The world's sto_contactor and forklift_io read that file," \
            "and so does the VDA agent that counts arrivals." \
            "NOTHING WAS STARTED."
            return 1; }
    done
    check_isolation || return 1

    [ -f "$WORLD_LAUNCH" ] || { refuse "the world launch exists" \
        "$TOOL" "no $WORLD_LAUNCH"; return 1; }
    # THE PARALLEL HALF OF THIS CELL. truck.sh is the per-truck runner and
    # this script starts no autonomy child without it; a missing one is
    # named here rather than discovered four spawns later.
    [ -f "$TRUCK" ] || { refuse "the per-truck runner exists" \
        "m6_ver2/truck.sh (SPEC_NAMESPACING.md 7-T4)" \
        "no $TRUCK - this script owns the ORDER and the fleet children," \
        "and every truck's stack goes up through that file." \
        "NOTHING WAS STARTED."; return 1; }

    # A TRUCK'S UDP PORT IS A SINGLE-HOLDER RESOURCE AND LOSING IT IS
    # QUIET: the second bind dies EADDRINUSE inside the first second and
    # that truck comes up with its PLC link missing, saying so in ONE
    # warning line among the dozens this cell prints. Refuse first, and
    # name the truck whose port is held.
    #   THE TEST HAS NO PIPE IN IT, and that is the whole point: under
    #   `set -o pipefail` any `writer | grep -q` can fail OPEN when the
    #   socket table is long enough to still be streaming when the match
    #   lands (m6.sh:227-240, measured over a 200k-line table). This one
    #   is matched by the shell itself. The $'\n' sentinels are there
    #   because $( ) eats the trailing newline, and [!0-9] rather than a
    #   space because it is the non-digit that tells :5110 from :51100.
    local udp_socks="" tcp_socks=""
    if command -v ss >/dev/null 2>&1; then
        udp_socks="$(ss -uln 2>/dev/null)"
        tcp_socks="$(ss -tln 2>/dev/null)"
    else
        echo "  note: ss not found - the per-truck UDP PLC port and TCP"
        echo "        :1883 pre-flights are SKIPPED."
    fi
    for i in "${!TABLE[@]}"; do
        vid="${TABLE[$i]}"; port="${PORTS[$i]}"
        case " ${VIDS[*]} " in *" $vid "*) ;; *) continue ;; esac
        case $'\n'"$udp_socks"$'\n' in
            *:"$port"[!0-9]*)
                refuse "UDP :$port is free for $vid's PLC link" \
                    "$M6/ipc/status_contract.py (VEHICLES.$vid.plc_port)" \
                    "another stack holds it:"
                ss -ulpn 2>/dev/null | grep -E ":$port([^0-9]|\$)"
                echo "  stop that stack first, then start this one."
                return 1 ;;
        esac
    done
    case $'\n'"$tcp_socks"$'\n' in
        *:1883[!0-9]*)
            refuse "TCP :1883 is free for the broker" "$TOOL" \
                "something already brokers MQTT here:"
            ss -tlpn 2>/dev/null | grep -E ':1883([^0-9]|$)'
            echo "  stop that stack first, then start this one."
            return 1 ;;
    esac
    if [ ! -x "$BROKER_BIN" ]; then
        refuse "the vendored MQTT broker is installed" "$BROKER_BIN" \
            "no broker there, and no broker means no VDA link at all." \
            "run 'bash $M6/tools/install_broker.sh' first - it needs no sudo."
        return 1
    fi
    [ -f "$ROS_SETUP" ] || { refuse "ROS is installed where config says" \
        "$ROS_SETUP" "no such file."; return 1; }
    # Unchecked, an unwritable log dir fails every redirection this cell
    # opens and start would sleep its way to "up." over nothing.
    mkdir -p "$LOGDIR" || { refuse "the log directory is writable" \
        "$LOGDIR" "cannot create it."; return 1; }
    gpu_preflight || return 1
    : > "$PIDFILE" || { refuse "the pid ledger is writable" "$PIDFILE" \
        "cannot write it."; return 1; }
    printf '%s\n' "${VIDS[*]}" > "$VIDFILE"

    # ament's hook reads AMENT_TRACE_SETUP_FILES before setting it, so
    # `set -u` stands down for the source.
    set +u
    # shellcheck disable=SC1090
    source "$ROS_SETUP"
    set -u

    # THE LEDGER IS TWO COLUMNS, "<pid> <name>", and the child writes its
    # own line. m6.sh keeps the names in a shell array, which is enough
    # for a script with no `status`: this one has one, and a name that
    # only exists inside the process that spawned it is a name `status`
    # and `stop` cannot print. setsid puts each child in its own SESSION
    # so the cell outlives its terminal; the LEADER writes the pid,
    # because setsid execs in place or FORKS depending on whether its
    # caller already leads a process group, so $! is not reliably it.
    #   THE TRUCK ID IS STAMPED ON THE CHILD'S ENVIRONMENT, because that
    #   is where every m6 node looks for it: status_contract binds a
    #   node's ports, topics and config path from env VEHICLE and refuses
    #   loudly without it. `env` EXECS IN PLACE, so the pid the leader
    #   wrote is still the node's own.
    #   '-' IS THE CELL'S OWN - the world, the broker, the fleet manager -
    #   and it must carry no VEHICLE at all: the launch serves every
    #   truck from one process and reads the table env-free.
    spawn() {  # spawn <name> <vid|-> <cmd...>
        local name="$1" vid="$2" pid="" want
        want=$(( $(wc -l < "$PIDFILE") + 1 ))
        shift 2
        [ "$vid" = "-" ] && vid=""
        setsid bash -c 'echo "$$ $2" >> "$1"; shift 2; exec "$@"' \
            _ "$PIDFILE" "$name" \
            env ${vid:+VEHICLE=$vid} "$@" \
            > "$LOGDIR/$name.log" 2>&1 &
        for _ in {1..50}; do
            pid="$(sed -n "${want}p" "$PIDFILE" | cut -d' ' -f1)"
            [ -n "$pid" ] && break; sleep 0.1
        done
        echo "  $name pid ${pid:-UNKNOWN, see $LOGDIR/$name.log}"
    }

    echo "starting the m6v2 cell: trucks ${VIDS[*]}, partition $GZ_PARTITION,"
    echo "domain $ROS_DOMAIN_ID, gui $GUI"
    # THE BROKER GOES UP FIRST and it is the one process here that is not
    # ROS. Every truck's VDA client dials 127.0.0.1:1883, so it has to be
    # listening before they start; mosquitto binds in milliseconds and
    # the world's head start covers that many times over. -v is the LOG
    # LEVEL, not a version flag. The loader path rides the `env` the
    # spawn already execs, so it costs no extra process and reaches
    # nothing but this child.
    spawn broker - LD_LIBRARY_PATH="$BROKER_LIB" "$BROKER_BIN" -v
    # ONE WORLD FOR EVERY TRUCK. M6V2_VIDS is how the launch learns which
    # subset to spawn and bridge - it is resolved at IMPORT there, so it
    # has to be in the environment and cannot be a launch substitution
    # (world.launch.py's resolve_vids header carries the argument).
    #   IT RIDES THE `env` THE SPAWN ALREADY EXECS, exactly as the
    #   broker's loader path does above: a leading NAME=value is env's
    #   own syntax, so it costs no extra process and reaches the ONE
    #   child that reads it. An `export` here would have put the cell's
    #   truck list in the environment of every node in it, which is a
    #   second answer to a question only the launch asks.
    spawn world - M6V2_VIDS="${VIDS[*]}" \
        ros2 launch "$WORLD_LAUNCH" "gui:=$GUI"
    sleep 5

    # ONE FULL FLEET SET PER TRUCK, FROM m6/ SOURCE. The order WITHIN a
    # set is m6.sh's and is load-bearing: field_eval before sensor_link,
    # so the link never sends a verdict from a device that has not been
    # evaluated yet. What is missing from that list is nav_node.py, and
    # its absence IS this branch (AMR-DEC-006): the Nav2 adapter under
    # truck.sh is the motion engine now.
    #   THE AGENT'S POSITION MOVED WITH IT. m6.sh puts vda_agent after
    #   nav_node so the route it publishes has a subscriber. Here the
    #   subscriber comes up in the truck loop BELOW this one, so the
    #   window is closed at the other end instead: fleet_manager is the
    #   only thing that can hand a truck work from outside this machine
    #   and it is the LAST process this script starts.
    local IPC="$M6/ipc"
    for vid in "${VIDS[@]}"; do
        spawn "plc_link_$vid"     "$vid" python3 "$IPC/plc_link.py"
        spawn "cmd_gate_$vid"     "$vid" python3 "$IPC/cmd_gate.py"
        spawn "cmd_mux_$vid"      "$vid" python3 "$IPC/cmd_mux.py"
        spawn "field_eval_$vid"   "$vid" python3 "$IPC/field_eval.py"
        spawn "encoder_link_$vid" "$vid" python3 "$IPC/encoder_link.py"
        spawn "sensor_link_$vid"  "$vid" python3 "$IPC/sensor_link.py"
        spawn "vda_agent_$vid"    "$vid" python3 "$IPC/vda_agent.py"
        spawn "hmi_$vid"          "$vid" python3 "$M6/hmi/hmi_node.py"
    done

    # AND THE AUTONOMY, ONE TRUCK AT A TIME, THROUGH ITS OWN RUNNER.
    # truck.sh keeps its own pids and its own logs and drives its own
    # lifecycle waits, so these calls are FOREGROUND and each returns
    # when that truck is up or has refused.
    #   A REFUSAL FOR ONE TRUCK DOES NOT ABANDON THE REST - m6.sh's
    #   `home` rule - but a half-done cell is still reported as a
    #   failure, at the end, by name and with a non-zero exit.
    local -a FAILED=()
    for vid in "${VIDS[@]}"; do
        echo "  truck $vid: bringing up its stack (truck.sh $vid start)"
        bash "$TRUCK" "$vid" start || FAILED+=("$vid")
    done

    # MASTER CONTROL GOES UP LAST. The manager assigns nothing until it
    # has a FRESH state from a truck, so started first it would simply
    # wait; last keeps the order legible - the plant, the trucks, then
    # the thing that gives them work. NO VEHICLE ('-'): it has no ROS and
    # no DDS domain and its only path to a truck is VDA 5050 over MQTT.
    # It carries the partition and the marker like every other child,
    # because that is what ours() reads. It runs from SOURCE, as the HMI
    # does: the fleet is not a truck.
    spawn fleet - python3 "$M6/fleet/fleet_manager.py"

    # "A process that dies in its first fraction of a second has not
    # started, and saying 'started' about it sends the operator to the
    # wrong log." The check is here and not inside spawn because the
    # deaths that matter are not instant - hmi_node.py with no DISPLAY
    # takes ~0.5 s to reach tk.Tk(). recorded() is the liveness test
    # rather than kill -0, which cannot see an unreaped zombie.
    sleep 1
    local bad=0
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        recorded "$pid" || { bad=1
            echo "  WARNING: $name exited during startup, see $LOGDIR/$name.log"; }
    done < "$PIDFILE"
    if [ "${#FAILED[@]}" -gt 0 ]; then
        bad=1
        echo "  WARNING: truck.sh refused for: ${FAILED[*]}"
    fi
    [ "$bad" = 1 ] && echo "  THE CELL IS INCOMPLETE."

    echo ""
    echo "up. On Windows, one writer per truck:"
    for vid in "${VIDS[@]}"; do
        echo "  python m6\\windows\\m6.py --vehicle $vid --virtual"
    done
    echo "broker: 127.0.0.1:1883 (localhost only, anonymous - $LOGDIR/broker.log)"
    echo "work:   python3 $M6/fleet/fleet_cli.py submit S1 S4   (trucks in AUTOMATIC)"
    echo "screen: python3 $M6/fleet/fleet_cli.py status --watch"
    echo "logs:   $LOGDIR  (per-truck: see truck.sh $vid status)"
    [ "$bad" = 1 ] && return 1
    return 0
}

# ----------------------------------------------------------------------
# STATUS
# ----------------------------------------------------------------------
status() {
    local pid name vid rc=0
    echo "m6v2: partition $GZ_PARTITION, domain $ROS_DOMAIN_ID"
    echo "ledger: $PIDFILE"
    echo "logs:   $LOGDIR"
    if [ ! -f "$PIDFILE" ]; then
        echo "not running (no ledger)."
        return 1
    fi
    # THE WORLD AND THE FLEET CHILDREN, off the ledger this script wrote.
    # ours() as well as kill -0, because a recycled pid is a stranger and
    # printing ALIVE about a stranger is worse than printing DEAD about a
    # child: it sends the operator to a log nobody is writing.
    while read -r pid name; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        if kill -0 "$pid" 2>/dev/null && recorded "$pid" && ours "$pid"; then
            printf '  %-22s %-6s pid %s\n' "${name:-?}" "ALIVE" "$pid"
        else
            printf '  %-22s %-6s pid %s (see %s)\n' \
                "${name:-?}" "DEAD" "$pid" "$LOGDIR/${name:-?}.log"
            rc=1
        fi
    done < "$PIDFILE"
    # AND EACH TRUCK'S OWN ANSWER, FROM ITS OWN RUNNER. This script does
    # not know what a bt_navigator is and must not learn: truck.sh owns
    # that stack's names, its pid file and its health, so `status` asks
    # rather than infers.
    if [ -f "$VIDFILE" ]; then
        # shellcheck disable=SC2207
        VIDS=($(cat "$VIDFILE"))
    fi
    if [ "${#VIDS[@]}" -eq 0 ]; then
        echo "  (no truck list recorded - $VIDFILE is missing)"
        rc=1
    elif [ ! -f "$TRUCK" ]; then
        echo "  (no $TRUCK - cannot ask any truck for its status)"
        rc=1
    else
        for vid in "${VIDS[@]}"; do
            echo "--- truck $vid ---"
            bash "$TRUCK" "$vid" status || rc=1
        done
    fi
    return "$rc"
}

# ----------------------------------------------------------------------
# STOP
# ----------------------------------------------------------------------
stop() {
    local pid name p vid
    # THE PARTITION SWEPT IS THE RUNNING CELL'S, NOT THIS SHELL'S: a stop
    # where GZ_PARTITION differs from the start would sweep nothing and
    # print "down." over a live cell. Read it back off a pid we recorded -
    # but only from one that is STILL OURS, because taking it from a
    # recycled pid is the worst bug this script could have.
    if [ -f "$PIDFILE" ]; then
        p="$(while read -r pid name; do
                 case "$pid" in ''|*[!0-9]*) continue ;; esac
                 recorded "$pid" && tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ"
             done < "$PIDFILE" | sed -n 's/^GZ_PARTITION=//p' | head -1)"
        [ -n "$p" ] && GZ_PARTITION="$p"
    fi
    # THE TRUCKS GO DOWN FIRST, THROUGH THEIR OWN RUNNER. truck.sh knows
    # its children's names, its own pid file and its own state files, and
    # a stack torn down by its owner leaves nothing for the sweep to
    # guess at. The vid list is the one start recorded; the table is the
    # fallback and the marked sweep below is the real safety, so a
    # missing list costs completeness of REPORTING and never of the stop.
    if [ -f "$VIDFILE" ]; then
        # shellcheck disable=SC2207
        VIDS=($(cat "$VIDFILE"))
    fi
    if [ "${#VIDS[@]}" -eq 0 ]; then
        while read -r vid _; do
            [ -n "$vid" ] && VIDS+=("$vid")
        done < <(vehicle_table)
    fi
    if [ -f "$TRUCK" ] && [ "${#VIDS[@]}" -gt 0 ]; then
        for vid in "${VIDS[@]}"; do
            echo "stopping truck $vid"
            bash "$TRUCK" "$vid" stop || \
                echo "  truck.sh $vid stop refused - the sweep below covers it"
        done
    fi
    # SHUTDOWN ORDER: THE SIMULATOR GOES FIRST, AND stop IS NOT A BRAKE.
    #   model.sdf's joint controllers are VELOCITY controllers holding
    #   the last setpoint for ever - measured on m6, 14.8 m travelled on
    #   a standing command after the publisher stopped - so killing this
    #   cell cannot slow a moving truck. sto_contactor's latch is moot
    #   once nothing publishes through it and cmd_gate's zeros never
    #   arrive. Ending the simulation is the only stop this script owns,
    #   and the brake is still the e-stop.
    sweep TERM
    if [ -f "$PIDFILE" ]; then
        # ours() before kill, exactly as the sweep does: a recorded pid is
        # a number on disk, not a promise. The residual purpose survives -
        # a recorded process that matches no pattern (a setsid wrapper
        # whose exec failed) still carries the partition and the marker.
        while read -r pid name; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            ours "$pid" && kill "$pid" 2>/dev/null && \
                echo "  killed $pid (${name:-?})"
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    else
        echo "nothing in the ledger to stop."
    fi
    rm -f "$VIDFILE"
    # ros2 launch does not bring its children down when signalled, so the
    # survivors are swept again: past the grace nothing exits on its own.
    sleep 2
    sweep KILL
    echo "down."
}

USAGE="usage: $0 start [--vids \"f1 f2\"] [--gui] | status | stop
  start       the whole m6v2 cell: the broker, ONE world with one
              bridge and one map_server, a full m6 fleet set per truck
              and a full m5_ver3 autonomy stack per truck through
              m6_ver2/truck.sh, then the fleet manager.
  --vids      only these trucks (default: every truck in the VEHICLES
              table). G1's gate runs one: --vids \"f1\".
  --gui       open the Gazebo window. The default is HEADLESS, which is
              the other way round from m6.sh: four Nav2 stacks on a
              0.575-RTF world is a measurement, not a demonstration.
  status      the world, the fleet children, and each truck's own answer
              from 'truck.sh <vid> status'.
  stop        every truck through its own runner, then the world, then a
              sweep keyed on GZ_PARTITION AND the M6V2 marker - so it
              can never take a plain m6 cell down with it.

  Work goes in with m6/fleet/fleet_cli.py submit FROM TO.
  A plain m6 cell may not be up at the same time (two servers, one
  partition); 'start' refuses and names it."

case "${1:-}" in
    start|--start)
        shift
        while [ "$#" -gt 0 ]; do
            case "$1" in
                --gui)  GUI=true; shift ;;
                --vids)
                    [ "$#" -ge 2 ] || { echo "$USAGE"; exit 2; }
                    # shellcheck disable=SC2206
                    VIDS=($2); shift 2 ;;
                # An unrecognised word is a REFUSAL and not a shrug: the
                # one it will be is a misspelt --gui or --vids, and
                # silently starting the whole table for someone who asked
                # for one truck is the failure this branch prevents.
                *) echo "$USAGE"; exit 2 ;;
            esac
        done
        start ;;
    status|--status) status ;;
    stop|--stop)     stop ;;
    *) echo "$USAGE"; exit 2 ;;
esac
