#!/usr/bin/env bash
# step1.sh - bring the Step 1 vehicle side up and down.  start | stop
#
# It does NOT touch PLCSIM Advanced or step1.py. Those are the owner's, on
# the Windows side, and the single-writer rule is the reason this script has
# no way to start them.
#
# GZ_PARTITION and ROS_DOMAIN_ID are set on every child so a concurrent M5
# demo cannot be joined by accident: a shared graph would put the old stack's
# publishers on this one's topics. They also decide what stop may kill.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STEP1="$REPO/m5_ver2/step1"
PIDFILE="$STEP1/.step1_pids"
LOGDIR="$STEP1/logs"
ROS_SETUP="/opt/ros/jazzy/setup.bash"

export GZ_PARTITION="${GZ_PARTITION:-step1}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-91}"
# The stack as command-line patterns. gz sim is FIRST on purpose (see the
# shutdown-order note in stop()); a pattern only NOMINATES, ours() decides.
PATTERNS=("gz sim" "step1_world.launch.py" "parameter_bridge" \
          "sto_contactor.py" "forklift_io.py" "plc_link.py" "cmd_gate.py" "hmi_node.py")

# WHY OWNERSHIP IS DECIDED BY THE ENVIRONMENT, NOT BY THE COMMAND LINE
#   vehicle.launch.py:738-754 starts sto_contactor.py and forklift_io.py with
#   a command line BYTE-IDENTICAL to step1_world.launch.py's - same absolute
#   script path, same --config - and both stacks run gz sim on the same
#   warehouse.sdf, so `pkill -f forklift_io.py` would kill a live M5 demo.
#   What separates them is GZ_PARTITION, which IS the definition of "this
#   graph" and is inherited by every child through ros2 launch. Unreadable
#   environ = left alone, the safe direction. Accepted exposure: what the
#   owner started with GZ_PARTITION=step1 is by that act IN this graph.
#   demo.sh:1046 and stack.sh:46-50 scope sweeps the same way; the old
#   stack's is m5demo (demo.sh:121). setsid does not affect this: the check
#   reads each candidate's OWN environ and never walks a process tree.
ours() {
    tr '\0' '\n' < "/proc/$1/environ" 2>/dev/null \
        | grep -qxF "GZ_PARTITION=$GZ_PARTITION"
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
            case "$cmd" in *step1.sh*|*demo.sh*|*stack.sh*) continue ;; esac
            ours "$pid" || continue
            kill "-$sig" "$pid" 2>/dev/null && echo "  swept $pid ($pat)"
        done < <(pgrep -af "$pat" 2>/dev/null)
    done
}

start() {
    local pid
    if [ -f "$PIDFILE" ]; then
        while read -r pid; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "already running (pid $pid, see $PIDFILE). Run '$0 stop' first."
                return 1
            fi
        done < "$PIDFILE"
        # All dead: a crashed run left it. The return above is what keeps
        # start from ever writing to a LIVE stack.
        rm -f "$PIDFILE"
    fi
    [ -f "$ROS_SETUP" ] || { echo "no $ROS_SETUP"; return 1; }
    mkdir -p "$LOGDIR"
    : > "$PIDFILE"
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
    echo "starting the Step 1 vehicle side (partition $GZ_PARTITION, domain $ROS_DOMAIN_ID)"
    spawn world  ros2 launch "$STEP1/gazebo/step1_world.launch.py"
    sleep 5
    spawn plc_link python3 "$STEP1/ros2/plc_link.py"
    spawn cmd_gate python3 "$STEP1/ros2/cmd_gate.py"
    spawn hmi      python3 "$STEP1/ros2/hmi_node.py"

    echo ""
    echo "up. Now start PLCSIM Advanced instance PLC_2, then on Windows:"
    echo "  python m5_ver2\\step1\\windows\\step1.py"
    echo "logs: $LOGDIR"
}
stop() {
    local pid p
    # THE PARTITION SWEPT IS THE RUNNING STACK'S, NOT THIS SHELL'S: a stop
    # where GZ_PARTITION differs from the start would sweep nothing and
    # print "down." over a live stack. Read it back off a pid we recorded.
    if [ -f "$PIDFILE" ]; then
        p="$(while read -r pid; do
                 tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null
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
        while read -r pid; do
            [ -n "$pid" ] && kill "$pid" 2>/dev/null && echo "  killed $pid"
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
case "${1:-}" in
    start|--start) start ;;
    stop|--stop)   stop ;;
    *) echo "usage: $0 start|stop"; exit 2 ;;
esac
