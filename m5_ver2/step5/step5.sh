#!/usr/bin/env bash
# step5.sh - bring the Step 5 vehicle side up and down.
#   start [--headless] | stop
#
# start opens the Gazebo GUI client, because this script is the HUMAN entry
# point and the point of Step 5 is watching the truck stop. The launch file's
# own default is the other way round (gui:=false), so nothing automated that
# calls ros2 launch directly gains a window. --headless restores that here,
# and a run being TIMED should use it: rendering here is llvmpipe software
# rasterisation (sim/setup/WSL_ENVIRONMENT.md 4.7), and the window costs not
# so much average speed as regularity - measured over 60 samples, real-time
# factor mean 0.998 headless against 0.806 with the window, but the WINDOW's
# floor is 0.127 against 0.926. The median stays 0.997. It stalls and catches
# up, so an interval measured with it open is worth less than one without.
#
# It does NOT touch PLCSIM Advanced or step5.py. Those are the owner's, on
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
STEP5="$REPO/m5_ver2/step5"
PIDFILE="$STEP5/.step5_pids"
LOGDIR="$STEP5/logs"
DEPLOY="$STEP5/deploy"
ROS_SETUP="/opt/ros/jazzy/setup.bash"

export GZ_PARTITION="${GZ_PARTITION:-step5}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-95}"
GUI=true   # start's default; --headless sets it false. See the header.
# The stack as command-line patterns. gz sim is FIRST on purpose (see the
# shutdown-order note in stop()); a pattern only NOMINATES, ours() decides.
# MAINTENANCE OBLIGATION: anything added to the stack must be added here too,
# or stop orphans it and still prints "down." Port 5101 arrives in a later step.
# THE GUI CLIENT NEEDS NO ENTRY OF ITS OWN, and that was checked rather than
# assumed: `gz sim -g` is ONE process whose command line begins with those two
# words, so "gz sim" nominates the client and the server alike - measured,
# `pgrep -af "gz sim"` returns both. If the client is ever started through
# ros_gz_sim's gz_sim.launch.py instead, it becomes `sh -c ruby .../gz sim -g`
# plus a child and this line has to be revisited.
PATTERNS=("gz sim" "step5_world.launch.py" "parameter_bridge" \
          "sto_contactor.py" "forklift_io.py" "plc_link.py" "cmd_gate.py" \
          "cmd_mux.py" "hmi_node.py" "field_eval.py" "sensor_link.py" \
          "encoder_link.py" "nav_node.py")

# WHY OWNERSHIP IS DECIDED BY THE ENVIRONMENT, NOT BY THE COMMAND LINE
#   vehicle.launch.py:738-754 starts sto_contactor.py and forklift_io.py with
#   a command line BYTE-IDENTICAL to step5_world.launch.py's - same absolute
#   script path, same --config - and both stacks run gz sim on the same
#   warehouse.sdf, so `pkill -f forklift_io.py` would kill a live M5 demo.
#   What separates them is GZ_PARTITION, which IS the definition of "this
#   graph" and is inherited by every child through ros2 launch. Unreadable
#   environ = left alone, the safe direction. Accepted exposure: what the
#   owner started with GZ_PARTITION=step5 is by that act IN this graph.
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
#   STRANGER, and every use of that number has to say so first. All four
#   recorded command lines contain m5_ver2/step5 and no foreign one does, so
#   that token is the identity test. It is deliberately the literal and not
#   "$STEP5": if REPO ever resolves differently between the start and the
#   stop, the looser token still matches and the partition read-back below
#   still works, which is the failure that read-back exists to prevent.
recorded() {
    grep -qaF "m5_ver2/step5" "/proc/$1/cmdline" 2>/dev/null
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
            case "$cmd" in *step5.sh*|*demo.sh*|*stack.sh*) continue ;; esac
            ours "$pid" || continue
            kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid ($pat)"
        done < <(pgrep -af "$pat" 2>/dev/null)
    done
}

home() {
    # Teleport the forklift back to the launch file's spawn pose, so a
    # latched protective field does not cost a simulator restart. gz only:
    # nothing here touches PLCSIM or the PLC program (single-writer rule),
    # so the ESTOP1 latches stay latched and the panel's 'a' is still the
    # reset - this moves the PLANT, not the safety state.
    #
    # THE POSE COMES FROM THE LAUNCH FILE, NOT FROM A COPY. _SPAWN in
    # step5_world.launch.py is the one home the spawn pose has; a literal
    # here would drift the moment someone moves the spawn.
    #
    # THE PARTITION IS THE RUNNING STACK'S, read back off a recorded pid
    # exactly as stop() does: a home where GZ_PARTITION differs from the
    # start would time out against an empty bus and print a shrug over a
    # live simulator.
    local pid p launch="$STEP5/gazebo/step5_world.launch.py"
    if [ -f "$PIDFILE" ]; then
        p="$(while read -r pid; do
                 case "$pid" in ''|*[!0-9]*) continue ;; esac
                 recorded "$pid" && tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ"
             done < "$PIDFILE" | sed -n 's/^GZ_PARTITION=//p' | head -1)"
        [ -n "$p" ] && GZ_PARTITION="$p"
    fi
    set +u; # shellcheck disable=SC1090
    source "$ROS_SETUP"; set -u
    local x y z yaw
    x="$(sed -n 's/.*"x": "\([^"]*\)".*/\1/p' "$launch" | head -1)"
    y="$(sed -n 's/.*"y": "\([^"]*\)".*/\1/p' "$launch" | head -1)"
    z="$(sed -n 's/.*"z": "\([^"]*\)".*/\1/p' "$launch" | head -1)"
    yaw="$(sed -n 's/.*"yaw": "\([^"]*\)".*/\1/p' "$launch" | head -1)"
    if [ -z "$x" ] || [ -z "$y" ] || [ -z "$z" ] || [ -z "$yaw" ]; then
        echo "cannot read _SPAWN from $launch"; return 1
    fi
    # Quaternion from yaw, so a later spawn with a heading still homes
    # true. awk, because the shell has no cosine.
    local qw qz
    qw="$(awk "BEGIN{printf \"%.9f\", cos($yaw/2)}")"
    qz="$(awk "BEGIN{printf \"%.9f\", sin($yaw/2)}")"
    echo "homing forklift to ($x, $y, $z, yaw $yaw) in partition $GZ_PARTITION"
    if gz service -s /world/warehouse/set_pose \
        --reqtype gz.msgs.Pose --reptype gz.msgs.Boolean --timeout 3000 \
        --req "name: \"forklift\", position: {x: $x, y: $y, z: $z}, orientation: {w: $qw, z: $qz}" \
        | grep -q "data: true"; then
        echo "home. The PLC latches are untouched - reset from the panel ('a')."
    else
        echo "set_pose refused or timed out: is the stack up ('$0 start')?"
        return 1
    fi
}

deploy() {
    # The "image build": a frozen copy of the vehicle software, laid out
    # at SOURCE depth so every relative path inside it still resolves -
    # deploy/m5_ver2/step5/ipc/cmd_gate.py finds config.yaml at
    # deploy/agv/forklift/config.yaml through the same ../../.. walk the
    # source tree uses. Owner ruling 2026-08-12: Docker Desktop cannot
    # pass DDS across its VM, so the deploy is simulated; the BOUNDARY
    # (what ships, what stays) is the same one a container would have.
    rm -rf "$DEPLOY"
    mkdir -p "$DEPLOY/m5_ver2/step5" "$DEPLOY/agv/forklift"
    cp -r "$STEP5/ipc" "$DEPLOY/m5_ver2/step5/ipc"
    cp "$REPO/agv/forklift/config.yaml" "$DEPLOY/agv/forklift/"
    find "$DEPLOY" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null
    ( cd "$DEPLOY" && {
        echo "# step5 deploy - generated, do not edit"
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
            ./m5_ver2/step5/ipc/*) s="$STEP5/ipc/${p#./m5_ver2/step5/ipc/}" ;;
            ./agv/*)               s="$REPO/${p#./}" ;;
            *)                     continue ;;
        esac
        [ "$(sha256sum "$s" 2>/dev/null | cut -d' ' -f1)" = "$h" ] || stale=1
    done < <(grep -v '^#' "$DEPLOY/MANIFEST")
    # A file added to source since the deploy is also a divergence.
    local src_n man_n
    src_n=$(find "$STEP5/ipc" -type f ! -path '*__pycache__*' | wc -l)
    man_n=$(grep -c 'm5_ver2/step5/ipc' "$DEPLOY/MANIFEST")
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
    # UDP :5100 IS A SINGLE-HOLDER RESOURCE, AND LOSING IT IS QUIET. plc_link
    # binds it; a step4 or step5 stack already up owns it, and the second
    # bind dies EADDRINUSE inside the first second - the stack then comes up
    # with the PLC link missing and says so in ONE warning line among nine
    # pids (hit twice while building Task 8). Refuse first, and name the
    # holder, because "already running" is the answer the operator needs.
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
    #   more - it is the non-digit, not the space, that tells :5100 from
    #   :51000. Measured: `grep ':5100 '` MISSES a line ending at the port.
    local udp_socks=""
    if command -v ss >/dev/null 2>&1; then
        udp_socks="$(ss -uln 2>/dev/null)"
    else
        # A guard that cannot run says so. Silence here would look identical
        # to a free port and hand back the Task 8 symptom with no trace.
        echo "  note: ss not found - the UDP :5100 pre-flight is SKIPPED."
    fi
    case $'\n'"$udp_socks"$'\n' in
        *:5100[!0-9]*)
            echo "UDP :5100 is already bound - another stack holds the PLC link:"
            # grep without -q reads to EOF, so this reporting pipe has no
            # SIGPIPE window of its own; its status is not tested either way.
            ss -ulpn 2>/dev/null | grep -E ':5100([^0-9]|$)'
            echo "stop that stack first, then start this one."
            return 1 ;;
    esac
    # NO DEPLOY, NO SOFTWARE. The vehicle runs the frozen tree and only that;
    # falling back to source would make the deploy decorative.
    if [ ! -f "$DEPLOY/MANIFEST" ]; then
        echo "no deploy found - the industrial PC has no software."
        echo "run '$0 deploy' first."
        return 1
    fi
    stale_check
    [ -f "$ROS_SETUP" ] || { echo "no $ROS_SETUP"; return 1; }
    # Unchecked, an unwritable log dir fails all four redirections, and start
    # would sleep its way to "up." over a stack that never began.
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
    spawn() {
        local name="$1" pid="" want=$(( $(wc -l < "$PIDFILE") + 1 )); shift
        setsid bash -c 'echo $$ >> "$1"; shift; exec "$@"' _ "$PIDFILE" "$@" \
            > "$LOGDIR/$name.log" 2>&1 &
        for _ in {1..50}; do pid="$(sed -n "${want}p" "$PIDFILE")"
            [ -n "$pid" ] && break; sleep 0.1; done
        echo "  $name pid ${pid:-UNKNOWN, see $LOGDIR/$name.log}"
    }
    echo "starting the Step 5 vehicle side (partition $GZ_PARTITION, domain $ROS_DOMAIN_ID, gui $GUI)"
    spawn world  ros2 launch "$STEP5/gazebo/step5_world.launch.py" "gui:=$GUI"
    sleep 5
    # EVERY VEHICLE NODE RUNS FROM THE DEPLOY, NOT FROM ipc/. That is the
    # whole point of deploy(): editing a source file mid-run changes nothing
    # until someone ships it. The HMI is the exception and stays in source -
    # it is the operator's panel on the commissioning laptop, not software
    # on the industrial PC, and drawing that line IS the deliverable.
    local IPC="$DEPLOY/m5_ver2/step5/ipc"
    spawn plc_link python3 "$IPC/plc_link.py"
    spawn cmd_gate python3 "$IPC/cmd_gate.py"
    spawn cmd_mux  python3 "$IPC/cmd_mux.py"
    # field_eval BEFORE sensor_link, so the link never sends a verdict from
    # a device that has not been evaluated yet.
    spawn field_eval   python3 "$IPC/field_eval.py"
    spawn encoder_link python3 "$IPC/encoder_link.py"
    spawn sensor_link  python3 "$IPC/sensor_link.py"
    spawn nav_node     python3 "$IPC/nav_node.py"
    spawn hmi          python3 "$STEP5/hmi/hmi_node.py"

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
    local i=0 bad=0 names=(world plc_link cmd_gate cmd_mux field_eval \
                           encoder_link sensor_link nav_node hmi)
    while read -r pid; do
        recorded "$pid" || { bad=1
            echo "  WARNING: ${names[$i]} exited during startup, see $LOGDIR/${names[$i]}.log"; }
        i=$(( i + 1 ))
    done < "$PIDFILE"
    [ "$bad" = 1 ] && echo "  THE STACK IS INCOMPLETE."

    echo ""
    echo "up. Now start PLCSIM Advanced instance PLC_2, then on Windows:"
    echo "  python m5_ver2\\step5\\windows\\step5.py"
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
  start       warehouse + forklift in a Gazebo window, plus the HMI
  --headless  no Gazebo window (gui:=false, the launch file's own default)
  home        teleport the forklift back to the spawn pose (stack stays up;
              PLC latches stay latched - reset from the panel)
  deploy      freeze ipc/ + config.yaml into deploy/ with a sha256 MANIFEST
              - the 'image build'. start refuses without one and warns
              loudly when the source has moved on since."
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
