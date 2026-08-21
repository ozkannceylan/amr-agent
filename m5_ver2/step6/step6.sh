#!/usr/bin/env bash
# step6.sh - bring the Step 6 vehicle side up and down: ONE broker, ONE
# world, TWO forklifts, and one full set of vehicle nodes per forklift.
#   start [--headless] | stop
#
# start opens the Gazebo GUI client, because this script is the HUMAN entry
# point and the point of Step 6 is watching the trucks stop. The launch file's
# own default is the other way round (gui:=false), so nothing automated that
# calls ros2 launch directly gains a window. --headless restores that here,
# and a run being TIMED should use it: rendering here is llvmpipe software
# rasterisation (sim/setup/WSL_ENVIRONMENT.md 4.7), and the window costs not
# so much average speed as regularity - measured over 60 samples, real-time
# factor mean 0.998 headless against 0.806 with the window, but the WINDOW's
# floor is 0.127 against 0.926. The median stays 0.997. It stalls and catches
# up, so an interval measured with it open is worth less than one without.
#
# It does NOT touch PLCSIM Advanced or step6.py. Those are the owner's, on
# the Windows side, and the single-writer rule is the reason this script has
# no way to start them.
#
# GZ_PARTITION and ROS_DOMAIN_ID are set on every child so a concurrent M5
# demo cannot be joined by accident: a shared graph would put the old stack's
# publishers on this one's topics. They also decide what stop may kill.
# ROS_DOMAIN_ID does NOT isolate Gazebo - gz transport is not DDS
# (stack.sh:52-53) - so GZ_PARTITION is the one that scopes the sweep.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STEP6="$REPO/m5_ver2/step6"
PIDFILE="$STEP6/.step6_pids"
LOGDIR="$STEP6/logs"
DEPLOY="$STEP6/deploy"
ROS_SETUP="/opt/ros/jazzy/setup.bash"
# THE BROKER IS VENDORED INTO THE USER'S HOME RATHER THAN INSTALLED: this
# WSL has no usable sudo, so tools/install_broker.sh `apt-get download`s
# mosquitto and unpacks it under ~/.local. The binary is deliberately not
# committed and that script is how it reproduces.
# BROKER_LIB IS NOT OPTIONAL. Those .debs put libwrap, libdlt and
# libwebsockets somewhere the loader does not look, so the broker child is
# handed LD_LIBRARY_PATH on its spawn line - and only that child, because
# a vendored libwebsockets on gz sim's loader path is a debugging session
# nobody asked for. MAINTENANCE OBLIGATION: install_broker.sh spells the
# same two paths; a move there has to move here.
BROKER_BIN="$HOME/.local/mosquitto-vendored/usr/sbin/mosquitto"
BROKER_LIB="$HOME/.local/mosquitto-vendored/usr/lib/x86_64-linux-gnu"

export GZ_PARTITION="${GZ_PARTITION:-step6}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-96}"
GUI=true   # start's default; --headless sets it false. See the header.
# THE VEHICLES THIS SCRIPT STARTS, in the order it starts them. The one home
# for every per-vehicle difference is the VEHICLES table in
# ipc/status_contract.py - ports, topics, spawn poses and the derived
# vehicles/<vid>/ pair all come from there, and nothing but the ID LIST is
# repeated here, because start, home and the writer hint are three shell
# loops and a shell cannot import Python without making `stop` depend on it.
# MAINTENANCE OBLIGATION: a vehicle added to that table must be added here
# too, or it is simply never started - and the ports at the two case patterns
# in start() are that table's plc_port values (see the note there).
VEHICLES=(f1 f2)
# The stack as command-line patterns. gz sim is FIRST on purpose (see the
# shutdown-order note in stop()); a pattern only NOMINATES, ours() decides.
# MAINTENANCE OBLIGATION: anything added to the stack must be added here too,
# or stop orphans it and still prints "down."
# A SECOND VEHICLE NEEDS NO ENTRY OF ITS OWN, by construction: both instances
# of a node are the SAME script under two environments, so one basename
# nominates both pids and ours() decides on each. A new NODE still has to be
# added here; a new VEHICLE does not.
# THE GUI CLIENT NEEDS NO ENTRY OF ITS OWN, and that was checked rather than
# assumed: `gz sim -g` is ONE process whose command line begins with those two
# words, so "gz sim" nominates the client and the server alike - measured,
# `pgrep -af "gz sim"` returns both. If the client is ever started through
# ros_gz_sim's gz_sim.launch.py instead, it becomes `sh -c ruby .../gz sim -g`
# plus a child and this line has to be revisited.
# THE BROKER IS NOMINATED BY ITS PATH AND IT IS LAST HERE ON PURPOSE.
# The pattern is the vendored PATH and not the basename, because
# `mosquitto` alone would nominate any broker on the machine - a system
# one included - and a pattern that nominates a stranger leans the whole
# weight of the sweep on ours(). Last, because this list is the shutdown
# order and every vehicle's MQTT client is a client OF it: taking the
# broker down first would only fill the vehicle logs with reconnect noise
# on the way out.
PATTERNS=("gz sim" "step6_world.launch.py" "parameter_bridge" \
          "sto_contactor.py" "forklift_io.py" "plc_link.py" "cmd_gate.py" \
          "cmd_mux.py" "hmi_node.py" "field_eval.py" "sensor_link.py" \
          "encoder_link.py" "nav_node.py" "mosquitto-vendored")

# WHY OWNERSHIP IS DECIDED BY THE ENVIRONMENT, NOT BY THE COMMAND LINE
#   vehicle.launch.py:738-754 starts sto_contactor.py and forklift_io.py with
#   a command line BYTE-IDENTICAL to step6_world.launch.py's - same absolute
#   script path, same --config - and both stacks run gz sim on the same
#   warehouse.sdf, so `pkill -f forklift_io.py` would kill a live M5 demo.
#   What separates them is GZ_PARTITION, which IS the definition of "this
#   graph" and is inherited by every child through ros2 launch. Unreadable
#   environ = left alone, the safe direction. Accepted exposure: what the
#   owner started with GZ_PARTITION=step6 is by that act IN this graph.
#   demo.sh:1046 and stack.sh:46-50 scope sweeps the same way; the old
#   stack's is m5demo (demo.sh:121). setsid does not affect this: the check
#   reads each candidate's OWN environ and never walks a process tree.
# 2>/dev/null PRECEDES the input redirect on purpose. Bash applies
# redirections left to right, so with it last the shell's own "No such file"
# for a pid that exited between nomination and check still reaches the
# terminal - measured: one such line per normal stop, once stop began calling
# ours() on pids sweep TERM had just killed.
ours() {
    tr '\0' '\n' 2>/dev/null < "/proc/$1/environ" \
        | grep -qxF "GZ_PARTITION=$GZ_PARTITION"
}

# THE PID FILE IS THE INPUT ours() DOES NOT GUARD, so it gets its own check.
#   Only stop deletes the file, so a reboot, a `wsl --shutdown` or a closed
#   terminal - the very case setsid was added to survive - leaves it on disk,
#   and Linux recycles pids back through the 17xxx-18xxx range this stack
#   lands in within minutes of a boot. A recorded number can therefore name a
#   STRANGER, and every use of that number has to say so first. Seventeen of
#   the eighteen recorded command lines contain m5_ver2/step6 and no foreign
#   one does, so that token is the identity test. It is deliberately the
#   literal and not "$STEP6": if REPO ever resolves differently between the
#   start and the stop, the looser token still matches and the partition
#   read-back below still works, which is the failure that read-back exists
#   to prevent.
#   THE BROKER IS THE EIGHTEENTH, and its command line is a path in the
#   user's HOME - a vendored binary is not under m5_ver2/step6 and never
#   will be - so it needs a token of its own, or every start would report it
#   as having exited and call the stack incomplete. mosquitto-vendored is
#   the directory install_broker.sh unpacks into and nothing else writes.
#   The exposure is the same shape as above and no larger: a recycled pid
#   landing on another copy of THIS vendored broker reads as ours, and what
#   that would be is a second step6 stack's broker.
recorded() {
    grep -qaF -e "m5_ver2/step6" -e "mosquitto-vendored" \
        "/proc/$1/cmdline" 2>/dev/null
}

sweep() {  # sweep <signal>
    local sig="$1" pat pid cmd
    for pat in "${PATTERNS[@]}"; do
        while read -r pid cmd; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            [ "$pid" = "$$" ] && continue
            # A sweep matching its own command line proves nothing
            # (demo.sh:1037, LESSONS 2026-08-06): these scripts quote the
            # patterns in their own text AND can carry the partition.
            case "$cmd" in *step6.sh*|*demo.sh*|*stack.sh*) continue ;; esac
            ours "$pid" || continue
            kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid ($pat)"
        done < <(pgrep -af "$pat" 2>/dev/null)
    done
}

home() {
    # Teleport BOTH forklifts back to their spawn poses, so a latched
    # protective field does not cost a simulator restart. gz only:
    # nothing here touches PLCSIM or the PLC program (single-writer rule),
    # so the ESTOP1 latches stay latched and the panel's 'a' is still the
    # reset - this moves the PLANT, not the safety state.
    #
    # THE POSES COME FROM THE VEHICLES TABLE, NOT FROM A COPY. They used to
    # be sed'd out of step6_world.launch.py's _SPAWN, which was then the one
    # home a single spawn pose had. Two vehicles have two poses and neither
    # belongs to the launch file: ipc/status_contract.py owns them, the
    # launch file spawns from that table and this reads the same table, so a
    # pose that moves moves for the spawn and for the home together.
    #
    # A REFUSAL FOR ONE VEHICLE DOES NOT ABANDON THE OTHER: each is homed on
    # its own and the exit status is the OR of the failures, because the
    # truck that could be recovered should be, and a half-done home has to
    # still be reported as a failure.
    #
    # THE PARTITION IS THE RUNNING STACK'S, read back off a recorded pid
    # exactly as stop() does: a home where GZ_PARTITION differs from the
    # start would time out against an empty bus and print a shrug over a
    # live simulator.
    local pid p vid x y z yaw qw qz rc=0
    if [ -f "$PIDFILE" ]; then
        p="$(while read -r pid; do
                 case "$pid" in ''|*[!0-9]*) continue ;; esac
                 recorded "$pid" && tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ"
             done < "$PIDFILE" | sed -n 's/^GZ_PARTITION=//p' | head -1)"
        [ -n "$p" ] && GZ_PARTITION="$p"
    fi
    set +u; # shellcheck disable=SC1090
    source "$ROS_SETUP"; set -u
    for vid in "${VEHICLES[@]}"; do
        # The table read is a subprocess and not an import, because a shell
        # cannot have one: PYTHONPATH points at ipc/ and status_contract is
        # read ENV-FREE, through VEHICLES, exactly as the launch file reads
        # it. No VEHICLE is exported here - this loop is about both trucks.
        read -r x y z yaw <<<"$(PYTHONPATH="$STEP6/ipc" python3 -c 'import sys
import status_contract
s = status_contract.VEHICLES[sys.argv[1]]["spawn"]
print(s["x"], s["y"], s["z"], s["yaw"])' "$vid")"
        if [ -z "$x" ] || [ -z "$y" ] || [ -z "$z" ] || [ -z "$yaw" ]; then
            echo "cannot read $vid's spawn pose from ipc/status_contract.py"
            rc=1; continue
        fi
        # Quaternion from yaw, so a spawn with a heading still homes true -
        # f2's is pi, facing f1 down the aisle. awk, because the shell has
        # no cosine.
        qw="$(awk "BEGIN{printf \"%.9f\", cos($yaw/2)}")"
        qz="$(awk "BEGIN{printf \"%.9f\", sin($yaw/2)}")"
        echo "homing forklift_$vid to ($x, $y, $z, yaw $yaw) in partition $GZ_PARTITION"
        if gz service -s /world/warehouse/set_pose \
            --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
            --req "name: \"forklift_$vid\", position: {x: $x, y: $y, z: $z}, orientation: {w: $qw, z: $qz}" \
            | grep -q "data: true"; then
            echo "  forklift_$vid home."
        else
            echo "  set_pose refused or timed out for forklift_$vid: is the stack up ('$0 start')?"
            rc=1
        fi
    done
    [ "$rc" = 0 ] && \
        echo "home. The PLC latches are untouched - reset from the panel ('a')."
    return "$rc"
}

deploy() {
    # The "image build": a frozen copy of the vehicle software, laid out
    # at SOURCE depth so every relative path inside it still resolves -
    # deploy/m5_ver2/step6/ipc/cmd_gate.py finds its config at
    # deploy/m5_ver2/step6/vehicles/<vid>/config.yaml through the same
    # ipc/.. walk the source tree uses. (It was ../../../agv until the
    # contract took the config path over; the layout is what makes both
    # walks land inside the image.) Owner ruling 2026-08-12: Docker
    # Desktop cannot pass DDS across its VM, so the deploy is simulated;
    # the BOUNDARY (what ships, what stays) is the same one a container
    # would have.
    #
    # THE DERIVED VEHICLES ARE PART OF THE IMAGE, AND THEY ARE REMADE FIRST.
    # Every node in the frozen tree resolves its config through
    # status_contract's config_path - ipc/../vehicles/<vid>/config.yaml -
    # so the deploy has to carry a vehicles/ of its own or that walk would
    # climb out of the image and back into the source, and the deploy would
    # be decorative for exactly the files that differ per vehicle.
    # Instantiating BEFORE the freeze is what makes the manifest honest.
    # A FAILURE HERE IS A REFUSAL, and it happens before the rm: a deploy
    # that ships yesterday's derivation is worse than no deploy at all, and
    # a tool that cannot run must not first destroy the last good image.
    ( cd "$STEP6" && python3 tools/instantiate_vehicle.py --all ) || return 1
    rm -rf "$DEPLOY"
    mkdir -p "$DEPLOY/m5_ver2/step6" "$DEPLOY/agv/forklift"
    cp -r "$STEP6/ipc" "$DEPLOY/m5_ver2/step6/ipc"
    cp -r "$STEP6/vehicles" "$DEPLOY/m5_ver2/step6/vehicles"
    # THE SOURCE config.yaml STILL SHIPS, and it is now PROVENANCE rather
    # than a file anything in the image opens: every node resolves through
    # the contract's vehicles/<vid>/config.yaml above, so this is the file
    # those two were derived FROM, frozen beside them with its own hash.
    # stale_check compares it, which is how a source edit that has not
    # been re-derived shows up as stale rather than as a surprise.
    # forklift_io and sto_contactor are not in the image at all: they take
    # their --config from the launch, which points at the SOURCE vehicles
    # dir - they are the plant's own nodes, started with the world, not
    # software on the industrial PC.
    cp "$REPO/agv/forklift/config.yaml" "$DEPLOY/agv/forklift/"
    find "$DEPLOY" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
    ( cd "$DEPLOY" && {
        echo "# step6 deploy - generated, do not edit"
        echo "# source-git: $(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
        echo "# date: $(date -Iseconds)"
        find . -type f ! -name MANIFEST -print0 | sort -z | xargs -0 sha256sum
      } > MANIFEST )
    echo "deployed $(grep -c '^[^#]' "$DEPLOY/MANIFEST") files to $DEPLOY"
}

stale_check() {
    # Compare the manifest against the CURRENT source. Stale is a loud
    # warning, not a refusal: running yesterday's build is exactly what
    # a real vehicle does until someone redeploys, and seeing that
    # happen is the point of the exercise.
    local stale=0 h p s
    while read -r h p; do
        case "$p" in
            ./m5_ver2/step6/ipc/*)
                s="$STEP6/ipc/${p#./m5_ver2/step6/ipc/}" ;;
            # The derived pair is source for this purpose: deploy() remakes
            # it, so a shipped vehicles/ that no longer matches the one on
            # disk means the model or config it was derived FROM has moved.
            ./m5_ver2/step6/vehicles/*)
                s="$STEP6/vehicles/${p#./m5_ver2/step6/vehicles/}" ;;
            ./agv/*)
                s="$REPO/${p#./}" ;;
            *)
                continue ;;
        esac
        [ "$(sha256sum "$s" 2>/dev/null | cut -d' ' -f1)" = "$h" ] || stale=1
    done < <(grep -v '^#' "$DEPLOY/MANIFEST")
    # A file added to source since the deploy is also a divergence - and a
    # VEHICLE added to the table is exactly that, two files of it.
    local src_n man_n
    src_n=$(find "$STEP6/ipc" "$STEP6/vehicles" -type f \
                 ! -path '*__pycache__*' 2>/dev/null | wc -l)
    man_n=$(grep -c -e 'm5_ver2/step6/ipc' -e 'm5_ver2/step6/vehicles' \
                 "$DEPLOY/MANIFEST")
    [ "$src_n" != "$man_n" ] && stale=1
    if [ "$stale" = 1 ]; then
        echo "  ================================================="
        echo "  WARNING: deploy is STALE - the vehicle will run"
        echo "  the OLD software. Rerun '$0 deploy' to ship."
        echo "  ================================================="
    fi
}

start() {
    local pid
    if [ -f "$PIDFILE" ]; then
        # recorded() too: a recycled pid would make start refuse against a
        # stack that is not there, and the message would send the operator
        # to a stop that then has to be right about the same pid.
        while read -r pid; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            if kill -0 "$pid" 2>/dev/null && recorded "$pid"; then
                echo "already running (pid $pid, see $PIDFILE). Run '$0 stop' first."
                return 1
            fi
        done < "$PIDFILE"
        # None of them is ours any more: a crashed run left the file. The
        # return above is what keeps start from writing to a LIVE stack.
        rm -f "$PIDFILE"
    fi
    # A VEHICLE'S UDP PORT IS A SINGLE-HOLDER RESOURCE, AND LOSING IT IS
    # QUIET. Each vehicle's plc_link binds its own - f1 :5110, f2 :5120 -
    # and the second bind on a held one dies EADDRINUSE inside the first
    # second; that vehicle then comes up with its PLC link missing and says
    # so in ONE warning line among seventeen pids (hit twice while building
    # Task 8). Refuse first, and name the vehicle whose port is held,
    # because "already running" is the answer the operator needs.
    #
    # WHAT REALISTICALLY HOLDS ONE: a step6 stack that is ALREADY UP - a
    # second copy of this script - and on this machine nothing else. The
    # 5100/5101 family belongs to step4 and step5 and is deliberately NOT
    # checked here: those stacks bind nothing this one wants, each has its
    # own guard on its own port, and checking theirs would refuse a start
    # that is perfectly legal beside them.
    #
    # THE SENSOR PORTS ARE UNCHECKED ON PURPOSE. 5111 and 5121 are bound on
    # the WINDOWS side - each writer's rx socket - so `ss` in WSL never sees
    # them and a guard here could only ever pass. The realistic holder is a
    # second step6 stack, and the plc_port test below refuses that first.
    #
    # MAINTENANCE OBLIGATION: 5110 and 5120 are the VEHICLES table's
    # plc_port values, spelled as literals in the two case patterns below
    # because a shell cannot import the table. A port that moves there has
    # to move here too, or this guard goes quietly blind.
    #
    # THE TEST HAS NO PIPE IN IT, AND THAT IS THE WHOLE POINT. Under this
    # file's `set -o pipefail` any `writer | grep -q` can fail OPEN: grep -q
    # exits at its FIRST match, the writer goes on writing into a closed pipe,
    # SIGPIPE kills it, pipefail hands the pipeline the writer's 141 and the
    # test takes the FALSE branch - the refusal skipped in exactly the case it
    # exists for, a socket table long enough to still be streaming when the
    # match lands. MEASURED over a 200k-line table: `ss -uln | grep -q` fails
    # open (141), and so does capture-then-`printf ... | grep -q`, because the
    # printf BUILTIN inherits the same window. Only forms with no early reader
    # exit survive. This one is matched by the shell itself, so there is no
    # writer, no pipe and no exit status to misread.
    #   $'\n' sentinels: $( ) eats the trailing newline, so a capture whose
    #   last line ends exactly at the port would have nothing after it to
    #   match. [!0-9] rather than a literal space for the same reason and one
    #   more - it is the non-digit, not the space, that tells :5110 from
    #   :51100. Measured on the :5100 this guard used to check: `grep
    #   ':5100 '` MISSES a line ending at the port.
    # ONE CAPTURE PER PROTOCOL, THREE TESTS. The UDP table is read once and
    # matched twice, so the two vehicles are judged against the same instant.
    # THE BROKER'S :1883 IS TCP AND GETS ITS OWN CAPTURE rather than folding
    # both families into one `ss -tuln`: in a single table a TCP socket on
    # :5110 would answer for f1's UDP link and refuse a start that is
    # perfectly legal. Two captures, two tables, no crosstalk.
    local udp_socks="" tcp_socks=""
    if command -v ss >/dev/null 2>&1; then
        udp_socks="$(ss -uln 2>/dev/null)"
        tcp_socks="$(ss -tln 2>/dev/null)"
    else
        # A guard that cannot run says so. Silence here would look identical
        # to a free port and hand back the Task 8 symptom with no trace.
        echo "  note: ss not found - the UDP :5110/:5120 and TCP :1883"
        echo "        pre-flights are SKIPPED."
    fi
    case $'\n'"$udp_socks"$'\n' in
        *:5110[!0-9]*)
            echo "UDP :5110 is already bound - another stack holds f1's PLC link:"
            # grep without -q reads to EOF, so this reporting pipe has no
            # SIGPIPE window of its own; its status is not tested either way.
            ss -ulpn 2>/dev/null | grep -E ':5110([^0-9]|$)'
            echo "stop that stack first, then start this one."
            return 1 ;;
    esac
    case $'\n'"$udp_socks"$'\n' in
        *:5120[!0-9]*)
            echo "UDP :5120 is already bound - another stack holds f2's PLC link:"
            ss -ulpn 2>/dev/null | grep -E ':5120([^0-9]|$)'
            echo "stop that stack first, then start this one."
            return 1 ;;
    esac
    # THE BROKER'S PORT IS THE SAME SINGLE-HOLDER RESOURCE, and losing it is
    # not quiet - mosquitto exits on EADDRINUSE - but the operator would
    # read that in broker.log only after the whole stack came up around a
    # broker that is not there. Same realistic holder as above: a step6
    # stack that is already up. 1883 is MQTT's registered port and this
    # broker takes the default, so a system mosquitto would hold it too;
    # naming the port and printing who has it is the whole answer.
    case $'\n'"$tcp_socks"$'\n' in
        *:1883[!0-9]*)
            echo "TCP :1883 is already bound - something already brokers MQTT here:"
            ss -tlpn 2>/dev/null | grep -E ':1883([^0-9]|$)'
            echo "stop that stack first, then start this one."
            return 1 ;;
    esac
    # NO BROKER, NO VDA LINK. It is vendored per-user and not committed, so
    # a fresh checkout has none, and starting anyway would bring the stack
    # up around a socket nothing is listening on.
    if [ ! -x "$BROKER_BIN" ]; then
        echo "no MQTT broker at $BROKER_BIN"
        echo "run 'bash $STEP6/tools/install_broker.sh' first - it needs no sudo."
        return 1
    fi
    # NO DEPLOY, NO SOFTWARE. The vehicle runs the frozen tree and only that;
    # falling back to source would make the deploy decorative.
    if [ ! -f "$DEPLOY/MANIFEST" ]; then
        echo "no deploy found - the industrial PC has no software."
        echo "run '$0 deploy' first."
        return 1
    fi
    stale_check
    [ -f "$ROS_SETUP" ] || { echo "no $ROS_SETUP"; return 1; }
    # Unchecked, an unwritable log dir fails all eighteen redirections, and
    # start would sleep its way to "up." over a stack that never began.
    mkdir -p "$LOGDIR" || { echo "cannot create $LOGDIR"; return 1; }
    : > "$PIDFILE"  || { echo "cannot write $PIDFILE"; return 1; }
    # ament's hook reads AMENT_TRACE_SETUP_FILES before setting it, so
    # `set -u` stands down for the source or start dies on its line 8.
    set +u
    # shellcheck disable=SC1090
    source "$ROS_SETUP"
    set -u
    # setsid puts each child in its own SESSION so the stack outlives its
    # terminal (stack.sh:220-226, the house form). Measured before it was
    # added: closing that terminal killed five of six and left gz sim alone
    # in a live simulator - the worst partial state there is, given the
    # controllers hold their last setpoint (see stop()). The LEADER writes
    # its own pid: setsid execs in place or FORKS depending on whether its
    # caller already leads a process group, so $! is not reliably the leader.
    #
    # THE VEHICLE ID IS STAMPED ON THE CHILD'S ENVIRONMENT, because that is
    # where every node looks for it: status_contract binds a node's ports,
    # topic names and config path from env VEHICLE and refuses loudly
    # without it. `env` EXECS IN PLACE, so the pid the leader wrote is still
    # the node's own and ours() still reads GZ_PARTITION out of the same
    # environ - one more word on the command line, no extra process.
    #   '-' IS THE WORLD, and it must carry no VEHICLE at all. The launch
    #   file serves both vehicles from one process and reads the table
    #   env-free; an inherited VEHICLE would be a name for "the vehicle"
    #   inside the one process that does not have one.
    #   ${vid:+...} expands to NOTHING for the world, which is why '-' is
    #   turned into the empty string first rather than passed through.
    #
    # THE NAME LIST IS BUILT HERE, NOT RESTATED BELOW. The startup check
    # walks $PIDFILE and needs a name per line; keeping that list by hand
    # made it a second spelling of the spawn order, and eighteen entries
    # is where such a list starts drifting. Appending in spawn() makes the
    # two orders the same order by construction.
    local -a SPAWNED=()
    spawn() {  # spawn <name> <vid|-> <cmd...>
        local name="$1" vid="$2" pid="" want=$(( $(wc -l < "$PIDFILE") + 1 ))
        shift 2
        [ "$vid" = "-" ] && vid=""
        setsid bash -c 'echo $$ >> "$1"; shift; exec "$@"' _ "$PIDFILE" \
            env ${vid:+VEHICLE=$vid} "$@" \
            > "$LOGDIR/$name.log" 2>&1 &
        for _ in {1..50}; do pid="$(sed -n "${want}p" "$PIDFILE")"
            [ -n "$pid" ] && break; sleep 0.1; done
        SPAWNED+=("$name")
        echo "  $name pid ${pid:-UNKNOWN, see $LOGDIR/$name.log}"
    }
    echo "starting the Step 6 vehicle side (partition $GZ_PARTITION, domain $ROS_DOMAIN_ID, gui $GUI)"
    # THE BROKER GOES UP FIRST, and it is the one process here that is not
    # ROS. Every vehicle's VDA client dials 127.0.0.1:1883, so it has to be
    # listening before they start; mosquitto binds in milliseconds and the
    # world's five seconds below cover that many times over.
    #   -v IS THE LOG LEVEL, not a version flag: with no config file
    #   mosquitto logs to stderr, and spawn already points stderr at
    #   $LOGDIR/broker.log. A config-less mosquitto 2.x also listens on
    #   LOCALHOST ONLY and allows anonymous local clients, which is the
    #   posture this milestone wants - not a default anyone leaned on.
    #   NO VEHICLE ('-'): one broker serves every truck on this machine, so
    #   there is no vehicle it could be the broker of.
    #   THE LOADER PATH RIDES THE `env` spawn ALREADY EXECS. A leading
    #   NAME=value is env's own syntax, so the vendored libraries cost no
    #   extra process and reach nothing but this child.
    # M6.3 MOVES THIS OUT. A broker belongs to the FLEET side - one for all
    # vehicles, on a machine that is not a vehicle. It is here because M6.2
    # is one machine, and it is SPAWNED rather than assumed so that start
    # and stop stay the only two commands an operator runs.
    spawn broker - LD_LIBRARY_PATH="$BROKER_LIB" "$BROKER_BIN" -v
    # ONE WORLD FOR BOTH TRUCKS: this single launch spawns both models,
    # bridges both vehicles' terminals and starts each one's contactor and
    # unit translator. Its five seconds of head start are the plant's.
    spawn world - ros2 launch "$STEP6/gazebo/step6_world.launch.py" "gui:=$GUI"
    sleep 5
    # EVERY VEHICLE NODE RUNS FROM THE DEPLOY, NOT FROM ipc/. That is the
    # whole point of deploy(): editing a source file mid-run changes nothing
    # until someone ships it. The HMI is the exception and stays in source -
    # it is the operator's panel on the commissioning laptop, not software
    # on the industrial PC, and drawing that line IS the deliverable.
    #
    # ONE FULL SET PER VEHICLE, and the sets are independent: the vehicles
    # share the world and nothing else, so f2's set could as well go first.
    # What may not change is the order WITHIN a set.
    local IPC="$DEPLOY/m5_ver2/step6/ipc"
    local vid
    for vid in "${VEHICLES[@]}"; do
        spawn "plc_link_$vid" "$vid" python3 "$IPC/plc_link.py"
        spawn "cmd_gate_$vid" "$vid" python3 "$IPC/cmd_gate.py"
        spawn "cmd_mux_$vid"  "$vid" python3 "$IPC/cmd_mux.py"
        # field_eval BEFORE sensor_link, so the link never sends a verdict
        # from a device that has not been evaluated yet.
        spawn "field_eval_$vid"   "$vid" python3 "$IPC/field_eval.py"
        spawn "encoder_link_$vid" "$vid" python3 "$IPC/encoder_link.py"
        spawn "sensor_link_$vid"  "$vid" python3 "$IPC/sensor_link.py"
        spawn "nav_node_$vid"     "$vid" python3 "$IPC/nav_node.py"
        spawn "hmi_$vid"          "$vid" python3 "$STEP6/hmi/hmi_node.py"
    done

    # "A process that dies in its first fraction of a second has not started,
    # and saying 'started' about it sends the operator to the wrong log"
    # (stack.sh:243-244). The check is HERE and not inside spawn because the
    # deaths that matter are not instant: the leader writes its pid before
    # exec, and hmi_node.py with no DISPLAY still takes ~0.5 s to import
    # rclpy and reach tk.Tk() - measured, twice, at .518 s and .494 s. A
    # per-spawn settle would have to guess that number; by this line the
    # youngest child is a second old and the oldest is six. recorded() is
    # the liveness test rather than kill -0, which cannot see that an
    # unreaped child is already a zombie.
    sleep 1
    local i=0 bad=0
    while read -r pid; do
        recorded "$pid" || { bad=1
            echo "  WARNING: ${SPAWNED[$i]} exited during startup, see $LOGDIR/${SPAWNED[$i]}.log"; }
        i=$(( i + 1 ))
    done < "$PIDFILE"
    [ "$bad" = 1 ] && echo "  THE STACK IS INCOMPLETE."

    echo ""
    # ONE WRITER PER VEHICLE, and that IS the single-writer rule rather than
    # an exception to it: the rule is one writer per PLC, and each vehicle
    # has its own. --virtual gives each writer its own virtual F-PLC in
    # process, which is what M6.1 runs (design, 2026-08-20). The real path
    # is the same shape - one PLCSIM Advanced instance per vehicle - and it
    # waits on a license, so it is not what this line tells the operator.
    echo "up. On Windows, one writer per vehicle:"
    for vid in "${VEHICLES[@]}"; do
        echo "  python m5_ver2\\step6\\windows\\step6.py --vehicle $vid --virtual"
    done
    echo "broker: 127.0.0.1:1883 (localhost only, anonymous - $LOGDIR/broker.log)"
    echo "logs: $LOGDIR"
}
stop() {
    local pid p
    # THE PARTITION SWEPT IS THE RUNNING STACK'S, NOT THIS SHELL'S: a stop
    # where GZ_PARTITION differs from the start would sweep nothing and print
    # "down." over a live stack. Read it back off a pid we recorded - but only
    # from a pid that is STILL OURS. Taking it from a recycled pid would be
    # the worst bug this script could have: if that pid now belongs to the
    # owner's live M5 demo, GZ_PARTITION becomes m5demo and the two sweeps
    # below then take that demo down, with the mechanism built to protect it.
    if [ -f "$PIDFILE" ]; then
        p="$(while read -r pid; do
                 case "$pid" in ''|*[!0-9]*) continue ;; esac
                 recorded "$pid" && tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ"
             done < "$PIDFILE" | sed -n 's/^GZ_PARTITION=//p' | head -1)"
        [ -n "$p" ] && GZ_PARTITION="$p"
    fi
    # SHUTDOWN ORDER: THE SIMULATOR GOES FIRST, AND stop IS NOT A BRAKE.
    #   Task 6 measured it: model.sdf's joint controllers are VELOCITY
    #   controllers holding the last setpoint forever, and the truck ran
    #   14.8 m on a standing command after its publisher stopped. Killing
    #   this stack therefore cannot slow a moving vehicle - sto_contactor's
    #   latch is moot once nothing publishes through it, cmd_gate's zeros
    #   never arrive - so killing either first would only leave a moving
    #   truck being integrated for the extra seconds the teardown takes.
    #   gz sim is where the motion lives, so PATTERNS puts it first: ending
    #   the simulation is the only stop this script owns, and the brake is
    #   still the e-stop.
    sweep TERM
    if [ -f "$PIDFILE" ]; then
        # ours() before kill, exactly as the sweep does at :47 - a recorded
        # pid is a number on disk, not a promise. The residual purpose of
        # this loop survives it: a recorded process that matches no PATTERN
        # (a setsid wrapper whose exec failed) still carries the partition.
        # Side effect: pids already dead from sweep TERM no longer print.
        while read -r pid; do
            case "$pid" in ''|*[!0-9]*) continue ;; esac
            ours "$pid" && kill "$pid" 2>/dev/null && echo "  killed $pid"
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    else
        echo "nothing to stop."
    fi
    # ros2 launch does not bring its children down when signalled, so the
    # survivors are swept again: past the grace nothing exits on its own.
    sleep 2
    sweep KILL
    echo "down."
}
USAGE="usage: $0 start [--headless] | stop | home | deploy
  start       warehouse + BOTH forklifts in a Gazebo window, plus one HMI
              per vehicle and the local MQTT broker on 127.0.0.1:1883
  --headless  no Gazebo window (gui:=false, the launch file's own default)
  home        teleport both forklifts back to their spawn poses (stack stays
              up; PLC latches stay latched - reset from the panel)
  deploy      derive vehicles/, then freeze ipc/ + vehicles/ + config.yaml
              into deploy/ with a sha256 MANIFEST - the 'image build'.
              start refuses without one and warns loudly when the source
              has moved on since."
case "${1:-}" in
    start|--start)
        case "${2:-}" in
            --headless) GUI=false ;;
            # An unrecognised second word is a REFUSAL and not a shrug: the
            # one it will be is a misspelt --headless, and silently starting
            # a window for someone who asked for none is the failure this
            # branch exists to prevent.
            "") ;;
            *) echo "$USAGE"; exit 2 ;;
        esac
        start ;;
    stop|--stop)   stop ;;
    home|--home)   home ;;
    deploy|--deploy) deploy ;;
    *) echo "$USAGE"; exit 2 ;;
esac
