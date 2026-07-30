#!/usr/bin/env bash
#
# stack.sh - start, stop and inspect the Linux side of the M4 forklift
# commissioning stack.
#
# The composition and the start order are quoted from
# sim/scenarios/forklift_commissioning.md section 1 ("The loop, and the order it
# is started in"). That table has five rows; row 1 is PLCSIM Advanced on the
# owner's Windows machine and is NOT started here. This script owns rows 2-5,
# which is every Linux-side process of the stack:
#
#   1. bridge          bridge/run_bridge.py            (OPC UA client)
#   2. sim             sim/launch/forklift_bringup.launch.py  (arena + spawn +
#                                                       ros_gz_bridge)
#   3. forklift_io     agv/forklift/scripts/forklift_io.py
#   4. obstacle_zone   agv/forklift/scripts/obstacle_zone.py
#   5. hmi             hmi/hmi_server.py               (OPC UA client + page)
#
# Rows 3 and 4 are section 1's single "vehicle nodes" step. They are two
# processes, so they get two PID files. agv/forklift/launch/vehicle.launch.py is
# a standalone rig that brings its own world, spawn and transport bridge; in the
# composed stack the two scripts run directly against the arena sim/ already
# started, which is what section 1 and agv/forklift/README.md both say.
#
# WHY THE ORDER IS THIS ORDER (section 1, restated, not reinvented):
#   - the OPC UA server comes first, because both clients browse it by namespace
#     URI at connect, so a missing endpoint is a connect failure and not a wait;
#   - the bridge comes before the plant, because its startup rule R3 withholds
#     the heartbeat until every configured input carries a real sample, so
#     "startup rule R3 satisfied" in its log is the signal that the plant is
#     actually publishing;
#   - the HMI comes last, because HmiLinkOk is FALSE until its counter has been
#     seen to change and starting it before there is a server only produces a
#     reconnect loop.
#
# WHAT THIS SCRIPT IS NOT. It starts existing processes with their existing
# configuration files and adds no data path and no logic. It never edits a
# config, never passes a threshold, never overrides an evidence path, and adds
# no route to the plant: every command still reaches the simulation as
# HMI -> PLC -> bridge -> Gazebo (ADR 0008 D1). It also starts no PLC test
# double: the double is a rehearsal fixture, not part of the owner's run.
#
# LIFECYCLE. Each component is started with setsid, so it leads its own process
# group, and its group leader PID is written to one file under the runtime
# directory. stop signals exactly those groups - SIGTERM, a bounded wait, then
# SIGKILL - and then sweeps for survivors by pgrep AND by this run's
# GZ_PARTITION in /proc/<pid>/environ, because signalling ros2 launch does not
# bring its group down. There is no blanket pkill anywhere in this file: a
# process is signalled only if it is in a PID file this script wrote, or it
# carries this run's partition in its own environment.
#
# ISOLATION. ROS_DOMAIN_ID does not isolate Gazebo, because gz transport does
# not use DDS. GZ_PARTITION does. Both are exported to every component.
#
# USAGE
#   ./stack.sh start [--headless]
#   ./stack.sh stop
#   ./stack.sh status
#   ./stack.sh --help
#
# EXIT CODES
#   0  the command did what it says
#   1  environment guard failed, or status found nothing running
#   2  start refused because the stack is already up
#   3  status found some but not all components up
#   4  start spawned everything but a readiness check timed out

set -uo pipefail

# --------------------------------------------------------------------------- #
# Where things are. Every default is quoted from the document that owns it, and
# every one can be overridden from the environment without editing this file.
# --------------------------------------------------------------------------- #

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Isolation values. sim/scenarios/forklift_commissioning.md section 1 uses this
# pair for the gate run; pick a fresh pair per run if anything else on the
# machine may be running a simulation.
export GZ_PARTITION="${GZ_PARTITION:-m4f4gate}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-60}"

# Runtime state lives outside the repository on purpose: a gate run must not
# make git status dirty, and on a /mnt/c checkout under WSL the Linux filesystem
# is the faster place for log files anyway.
RUN_DIR="${AMR_STACK_RUN_DIR:-/tmp/amr-agent-stack}"

ROS_SETUP="${AMR_ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

# The venvs. bridge/README.md gives the mechanism rather than one machine's
# path: /opt/amr-bridge-venv in the development container, ~/amr-bridge-venv on
# the owner's WSL, where /opt is not writable. Both are searched, in that order,
# and AMR_BRIDGE_VENV wins over both.
BRIDGE_VENV="${AMR_BRIDGE_VENV:-}"
HMI_VENV="${AMR_HMI_VENV:-}"

# Configuration files. These are read by the processes, never by this script,
# and never modified. See the note in README.md: bridge/config/bridge.yaml is
# committed carrying the cell group alone.
BRIDGE_CONFIG="${AMR_BRIDGE_CONFIG:-$REPO/bridge/config/bridge.yaml}"
HMI_CONFIG="${AMR_HMI_CONFIG:-$REPO/hmi/config.yaml}"
VEHICLE_CONFIG="${AMR_VEHICLE_CONFIG:-$REPO/agv/forklift/config.yaml}"

# Bounded waits, in seconds. Every wait in this script has a deadline.
WAIT_BRIDGE="${AMR_WAIT_BRIDGE:-60}"
WAIT_SIM="${AMR_WAIT_SIM:-120}"
WAIT_VEHICLE="${AMR_WAIT_VEHICLE:-90}"
WAIT_HMI="${AMR_WAIT_HMI:-60}"
TERM_GRACE="${AMR_TERM_GRACE:-10}"
KILL_GRACE="${AMR_KILL_GRACE:-3}"

# Components, in start order. Each name is a PID file stem, a log file stem and
# a column in status output.
COMPONENTS=(bridge sim forklift_io obstacle_zone hmi)

# One token per component, matched against /proc/<pid>/cmdline so that a reused
# PID cannot be mistaken for a live component.
declare -A COMPONENT_TOKEN=(
    [bridge]="run_bridge.py"
    [sim]="forklift_bringup.launch.py"
    [forklift_io]="forklift_io.py"
    [obstacle_zone]="obstacle_zone.py"
    [hmi]="hmi_server.py"
)

# Survivor sweep patterns for stop. Matched by pgrep -af and then filtered by
# this run's GZ_PARTITION, so nothing outside this run is ever signalled. The
# arena's own children are here because signalling ros2 launch leaves gz sim and
# parameter_bridge running - measured by m4f-03 and in every rehearsal since.
SURVIVOR_PATTERNS="gz sim|parameter_bridge|forklift_bringup.launch.py|run_bridge.py|forklift_io.py|obstacle_zone.py|hmi_server.py"

GUI="true"   # showcase default; --headless makes it false

# Resolved by check_environment; declared here so nothing reads them unset.
PYTHON3=""
BRIDGE_PY=""
HMI_PY=""
HMI_PORT=""

# --------------------------------------------------------------------------- #
# Small output helpers. Plain ASCII, no colour: this output ends up in evidence.
# --------------------------------------------------------------------------- #

note() { printf '%s\n' "$*"; }
info() { printf '  %s\n' "$*"; }
ok()   { printf '  ok    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*" >&2; }
fail() { printf '  FAIL  %s\n' "$*" >&2; }
die()  { printf 'stack.sh: %s\n' "$*" >&2; exit 1; }

usage() {
    sed -n '2,66p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
}

# --------------------------------------------------------------------------- #
# PID file lifecycle
# --------------------------------------------------------------------------- #

pid_file() { printf '%s/%s.pid' "$RUN_DIR" "$1"; }
log_file() { printf '%s/%s.log' "$RUN_DIR" "$1"; }

# kill -0 succeeds on a ZOMBIE, and a component leader is a child of this
# script, so between its death and this shell reaping it there is a window in
# which "is it still up" answers yes about a process that has already exited.
# Reading the state field out of /proc/<pid>/stat closes that window; without
# it, stop escalates to SIGKILL against a corpse and then reports that the
# corpse survived it.
pid_alive() {
    local pid="$1" stat_line state
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    stat_line="$(cat "/proc/$pid/stat" 2>/dev/null)" || return 1
    # The comm field is parenthesised and may contain spaces, so state is the
    # first field after the last ')'.
    state="$(printf '%s' "${stat_line##*) }" | cut -d' ' -f1)"
    [ "$state" = "Z" ] && return 1
    return 0
}

read_pid() {
    local file
    file="$(pid_file "$1")"
    [ -f "$file" ] || return 1
    local pid
    pid="$(cat "$file" 2>/dev/null)"
    [ -n "$pid" ] || return 1
    case "$pid" in (*[!0-9]*) return 1 ;; esac
    printf '%s' "$pid"
}

# A component is running when its PID file names a live process whose command
# line still carries that component's token. The token check is what makes a
# recycled PID read as down rather than as somebody else's process.
is_running() {
    local name="$1" pid
    pid="$(read_pid "$name")" || return 1
    pid_alive "$pid" || return 1
    local cmdline
    cmdline="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null)" || return 1
    case "$cmdline" in
        (*"${COMPONENT_TOKEN[$name]}"*) return 0 ;;
        (*) return 1 ;;
    esac
}

running_components() {
    local name
    for name in "${COMPONENTS[@]}"; do
        is_running "$name" && printf '%s\n' "$name"
    done
    return 0
}

# --------------------------------------------------------------------------- #
# Spawning and bounded waiting
# --------------------------------------------------------------------------- #

# spawn <name> <shell command>
#
# setsid puts the child in its own SESSION, so it leads its own process group
# and stop can signal the whole tree by negating the leader's PID. The leader
# writes its OWN pid into the PID file rather than the parent recording $!,
# because setsid execs in place or forks depending on whether its caller is
# already a process group leader, so $! is not reliably the leader. Every
# component command below ends in `exec`, so the pid written here survives into
# the process that actually does the work.
spawn() {
    local name="$1" command="$2" log pidf
    log="$(log_file "$name")"
    pidf="$(pid_file "$name")"
    : > "$log"
    rm -f "$pidf"
    setsid bash -c "echo \$\$ > '$pidf'; $command" >"$log" 2>&1 &
    local deadline=$((SECONDS + 10)) pid=""
    while [ "$SECONDS" -lt "$deadline" ]; do
        pid="$(read_pid "$name")" && break
        sleep 0.1
    done
    if [ -z "$pid" ]; then
        fail "$name did not report a pid within 10s - see $log"
        return 1
    fi
    # A process that dies in its first fraction of a second has not started, and
    # saying "started" about it sends the operator to the wrong log.
    sleep 0.4
    if ! is_running "$name"; then
        fail "$name exited immediately. Last lines of $log:"
        tail -n 15 "$log" 2>/dev/null | while IFS= read -r line; do printf '        %s\n' "$line"; done
        rm -f "$pidf"
        return 1
    fi
    info "started $name pid $pid  log $log"
}

# wait_until <label> <timeout seconds> <command> [args...]
# Bounded foreground polling. Nothing in this script waits without a deadline.
wait_until() {
    local label="$1" timeout="$2"
    shift 2
    local deadline=$((SECONDS + timeout))
    while [ "$SECONDS" -lt "$deadline" ]; do
        if "$@" >/dev/null 2>&1; then
            ok "$label"
            return 0
        fi
        sleep 0.5
    done
    warn "$label - not observed within ${timeout}s"
    return 1
}

# --- the four readiness predicates ----------------------------------------- #

log_has() { grep -q -- "$2" "$(log_file "$1")" 2>/dev/null; }

ros_topic_present() {
    bash -c "source '$ROS_SETUP' && ros2 topic list" 2>/dev/null | grep -qx -- "$1"
}

# The HMI page is ready when its OPC UA session is CONNECTED *and* its read-only
# poll has landed. A panel whose metrics are still blank is not a boot reading:
# an absent value is not a zero (forklift_commissioning.md section 3).
hmi_ready() {
    "$PYTHON3" - "$1" <<'PY' 2>/dev/null
import json, sys, urllib.request
with urllib.request.urlopen("http://127.0.0.1:%s/state" % sys.argv[1], timeout=1.0) as handle:
    state = json.load(handle)
session = state.get("session") or {}
sys.exit(0 if session.get("state") == "CONNECTED" and state.get("metrics") else 1)
PY
}

# The HTTP port the HMI binds, read out of the config it was given rather than
# assumed: hmi/config.yaml binds 8088, the rehearsal config binds 8090.
hmi_http_port() {
    awk '
        /^[^[:space:]#]/ { in_http = ($0 ~ /^http:/) }
        in_http && $1 == "port:" { gsub(/[^0-9]/, "", $2); if ($2 != "") { print $2; exit } }
    ' "$HMI_CONFIG"
}

# --------------------------------------------------------------------------- #
# Environment guards. This script runs on the owner's WSL as well as in the
# development container, so every external thing it needs is named before
# anything is spawned, and a missing one is a message rather than a stack trace
# in a log file nobody is watching yet.
# --------------------------------------------------------------------------- #

find_venv_python() {
    local override="$1"; shift
    local candidate
    if [ -n "$override" ]; then
        if [ -x "$override/bin/python" ]; then printf '%s/bin/python' "$override"; return 0; fi
        if [ -x "$override" ]; then printf '%s' "$override"; return 0; fi
        return 1
    fi
    for candidate in "$@"; do
        [ -x "$candidate/bin/python" ] && { printf '%s/bin/python' "$candidate"; return 0; }
    done
    return 1
}

check_environment() {
    local problems=0

    PYTHON3="$(command -v python3 || true)"
    [ -n "$PYTHON3" ] || { fail "python3 not on PATH"; problems=$((problems + 1)); }

    local script
    for script in \
        "bridge/run_bridge.py" \
        "sim/launch/forklift_bringup.launch.py" \
        "agv/forklift/scripts/forklift_io.py" \
        "agv/forklift/scripts/obstacle_zone.py" \
        "hmi/hmi_server.py"
    do
        [ -f "$REPO/$script" ] || { fail "missing $REPO/$script"; problems=$((problems + 1)); }
    done

    local config
    for config in "$BRIDGE_CONFIG" "$HMI_CONFIG" "$VEHICLE_CONFIG"; do
        [ -f "$config" ] || { fail "missing config $config"; problems=$((problems + 1)); }
    done

    if [ ! -f "$ROS_SETUP" ]; then
        fail "ROS 2 setup not found at $ROS_SETUP (set AMR_ROS_SETUP)"
        problems=$((problems + 1))
    else
        if ! bash -c "source '$ROS_SETUP' && command -v ros2" >/dev/null 2>&1; then
            fail "ros2 not on PATH after sourcing $ROS_SETUP"
            problems=$((problems + 1))
        fi
        if ! bash -c "source '$ROS_SETUP' && ros2 pkg prefix ros_gz_sim" >/dev/null 2>&1; then
            fail "ROS 2 package ros_gz_sim not found - the arena bringup needs it"
            problems=$((problems + 1))
        fi
    fi

    command -v gz >/dev/null 2>&1 || { fail "gz not on PATH - Gazebo is the simulator (invariant 12)"; problems=$((problems + 1)); }

    BRIDGE_PY="$(find_venv_python "$BRIDGE_VENV" /opt/amr-bridge-venv "$HOME/amr-bridge-venv" || true)"
    if [ -z "$BRIDGE_PY" ]; then
        fail "bridge venv not found (looked at /opt/amr-bridge-venv and \$HOME/amr-bridge-venv; set AMR_BRIDGE_VENV). See bridge/README.md, 'The venv'."
        problems=$((problems + 1))
    fi

    HMI_PY="$(find_venv_python "$HMI_VENV" "$HOME/amr-hmi-venv" /opt/amr-hmi-venv || true)"
    if [ -z "$HMI_PY" ]; then
        fail "HMI venv not found (looked at \$HOME/amr-hmi-venv and /opt/amr-hmi-venv; set AMR_HMI_VENV). See hmi/README.md."
        problems=$((problems + 1))
    fi

    HMI_PORT="$(hmi_http_port)"
    if [ -z "$HMI_PORT" ]; then
        fail "no http.port in $HMI_CONFIG"
        problems=$((problems + 1))
    fi

    [ "$problems" -eq 0 ]
}

# Advisory only, and deliberately not a hard failure: which groups a run carries
# is a configuration decision owned by bridge/, and this script only reports what
# it sees. A cell-only config brings up a stack in which no Forklift/ node is
# read or written, which is not what the M4 procedure expects.
check_bridge_groups() {
    local groups_line
    groups_line="$(grep -m1 '^groups:' "$BRIDGE_CONFIG" 2>/dev/null)"
    if [ -z "$groups_line" ]; then
        warn "no groups: line in $BRIDGE_CONFIG"
    elif ! printf '%s' "$groups_line" | grep -q 'forklift'; then
        warn "$BRIDGE_CONFIG carries $groups_line - it does not name the forklift group,"
        warn "so no Forklift/ node will be read or written. forklift_commissioning.md"
        warn "section 1 makes a forklift-group config against the commissioned endpoint"
        warn "a prerequisite of the gate run. Point AMR_BRIDGE_CONFIG at it."
    fi
}

# --------------------------------------------------------------------------- #
# start
# --------------------------------------------------------------------------- #

# A component that will not start makes the rest of the order meaningless, so
# start stops there. Whatever did come up is left running and named, because a
# half-started stack with its logs intact is easier to diagnose than one that
# tore itself down.
start_abort() {
    fail "$1 did not start - stopping here, in the middle of the start order."
    fail "What is up is listed below. Read its log, then './stack.sh stop'."
    note ""
    cmd_status
    exit 1
}

cmd_start() {
    while [ $# -gt 0 ]; do
        case "$1" in
            (--headless) GUI="false" ;;
            (--gui) GUI="true" ;;
            (*) die "start: unknown option $1 (try --headless)" ;;
        esac
        shift
    done

    mkdir -p "$RUN_DIR" || die "cannot create runtime directory $RUN_DIR"

    # Refuse before anything else. A second start is the double-forklift failure
    # of 2026-07-29: two spawns of the same vehicle in one world.
    local up
    up="$(running_components)"
    if [ -n "$up" ]; then
        note "stack.sh: refusing to start - already running:"
        printf '%s\n' "$up" | while IFS= read -r component; do info "$component"; done
        note "Run './stack.sh stop' first, or './stack.sh status' to see the rest."
        return 2
    fi

    check_environment || die "environment guard failed; nothing was started"
    check_bridge_groups

    note "starting the Linux-side M4 stack"
    info "repo            $REPO"
    info "runtime dir     $RUN_DIR"
    info "GZ_PARTITION    $GZ_PARTITION"
    info "ROS_DOMAIN_ID   $ROS_DOMAIN_ID"
    info "bridge config   $BRIDGE_CONFIG"
    info "HMI config      $HMI_CONFIG  (page on 127.0.0.1:$HMI_PORT)"
    info "arena GUI       $GUI"
    if [ "$GUI" = "true" ] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
        warn "gui:=true with no DISPLAY or WAYLAND_DISPLAY set - use --headless if the"
        warn "GUI client fails to open. Rendering is software (llvmpipe) either way."
    fi
    note "The PLC side is NOT started here: put the CPU in RUN on PLCSIM Advanced"
    note "from TIA Portal on the Windows machine first (section 1 row 1)."

    # Record the partition this run owns, so stop can filter survivors by it
    # even from a shell that has a different one exported.
    printf '%s\n' "$GZ_PARTITION" > "$RUN_DIR/partition"
    printf '%s\n' "$ROS_DOMAIN_ID" > "$RUN_DIR/domain"

    local readiness=0

    # 1. bridge. Started before the plant on purpose: rule R3 makes it wait.
    note "1/5 bridge"
    spawn bridge "cd '$REPO' && source '$ROS_SETUP' && exec '$BRIDGE_PY' '$REPO/bridge/run_bridge.py' --config '$BRIDGE_CONFIG'" || start_abort bridge
    wait_until "bridge session established" "$WAIT_BRIDGE" \
        log_has bridge "session established" || {
        warn "the bridge has not connected. It retries on its own, so this is not"
        warn "fatal - but check that the CPU is in RUN and that the endpoint in"
        warn "$BRIDGE_CONFIG is reachable. Log: $(log_file bridge)"
        readiness=1
    }

    # 2. the arena.
    note "2/5 sim (arena, spawn, transport bridge)"
    spawn sim "cd '$REPO' && source '$ROS_SETUP' && exec ros2 launch '$REPO/sim/launch/forklift_bringup.launch.py' gui:=$GUI" || start_abort sim
    wait_until "/forklift/scan on the wire" "$WAIT_SIM" \
        ros_topic_present /forklift/scan || readiness=1

    # 3 and 4. The two vehicle nodes, run directly against the arena above.
    note "3/5 forklift_io"
    spawn forklift_io "cd '$REPO' && source '$ROS_SETUP' && exec python3 '$REPO/agv/forklift/scripts/forklift_io.py' --config '$VEHICLE_CONFIG'" || start_abort forklift_io
    note "4/5 obstacle_zone"
    spawn obstacle_zone "cd '$REPO' && source '$ROS_SETUP' && exec python3 '$REPO/agv/forklift/scripts/obstacle_zone.py' --config '$VEHICLE_CONFIG'" || start_abort obstacle_zone
    wait_until "bridge startup rule R3 satisfied (the plant is publishing)" "$WAIT_VEHICLE" \
        log_has bridge "startup rule R3 satisfied" || readiness=1

    # 5. the HMI, last.
    note "5/5 hmi"
    spawn hmi "cd '$REPO' && exec '$HMI_PY' '$REPO/hmi/hmi_server.py' --config '$HMI_CONFIG'" || start_abort hmi
    wait_until "HMI session CONNECTED with metrics on the page" "$WAIT_HMI" \
        hmi_ready "$HMI_PORT" || readiness=1

    note ""
    cmd_status
    note ""
    note "Operator page: http://127.0.0.1:$HMI_PORT/"
    note "Logs:          $RUN_DIR"
    if [ "$readiness" -ne 0 ]; then
        warn "every process was spawned, but at least one readiness check timed out."
        warn "Nothing was torn down - read the logs above, then './stack.sh stop'."
        return 4
    fi
    return 0
}

# --------------------------------------------------------------------------- #
# stop
# --------------------------------------------------------------------------- #

# stop_group <pid> <label> - SIGTERM to the process group, bounded wait, SIGKILL.
stop_group() {
    local pid="$1" label="$2"
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    local deadline=$((SECONDS + TERM_GRACE))
    while [ "$SECONDS" -lt "$deadline" ]; do
        pid_alive "$pid" || { ok "$label pid $pid stopped on SIGTERM"; return 0; }
        sleep 0.2
    done
    warn "$label pid $pid still up after ${TERM_GRACE}s - sending SIGKILL"
    kill -KILL -- "-$pid" 2>/dev/null || kill -KILL "$pid" 2>/dev/null || true
    deadline=$((SECONDS + KILL_GRACE))
    while [ "$SECONDS" -lt "$deadline" ]; do
        pid_alive "$pid" || { ok "$label pid $pid stopped on SIGKILL"; return 0; }
        sleep 0.2
    done
    fail "$label pid $pid survived SIGKILL"
    return 1
}

# Survivors of THIS run only: matched by pgrep and then filtered by the
# partition recorded at start. A pid whose /proc/<pid>/environ does not carry it
# is somebody else's process and is never signalled.
survivors() {
    local partition="$1" line pid environ
    pgrep -af "$SURVIVOR_PATTERNS" 2>/dev/null | while read -r line; do
        pid="${line%% *}"
        case "$pid" in (*[!0-9]*) continue ;; esac
        [ "$pid" = "$$" ] && continue
        # A shell whose own command line happens to quote one of the patterns -
        # this script, or the terminal that invoked it - is not a component.
        case "${line#* }" in (*stack.sh*) continue ;; esac
        environ="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null)" || continue
        printf '%s\n' "$environ" | grep -qx "GZ_PARTITION=$partition" || continue
        printf '%s %s\n' "$pid" "${line#* }"
    done
}

cmd_stop() {
    [ -d "$RUN_DIR" ] || { note "stack.sh: nothing to stop (no runtime dir $RUN_DIR)"; return 0; }

    PYTHON3="$(command -v python3 || true)"
    local problems=0 acted=0 name pid

    note "stopping the Linux-side M4 stack"
    # Reverse start order: the HMI first, the bridge last, so the loop is taken
    # apart from the operator's end rather than from the plant's.
    local i
    for (( i=${#COMPONENTS[@]}-1; i>=0; i-- )); do
        name="${COMPONENTS[$i]}"
        if is_running "$name"; then
            pid="$(read_pid "$name")"
            acted=1
            stop_group "$pid" "$name" || problems=$((problems + 1))
            rm -f "$(pid_file "$name")"
        else
            if [ -f "$(pid_file "$name")" ]; then
                info "$name not running (stale PID file removed)"
                rm -f "$(pid_file "$name")"
            else
                info "$name not running"
            fi
        fi
    done

    # Signalling ros2 launch does not bring gz sim or parameter_bridge down.
    local partition
    partition="$(cat "$RUN_DIR/partition" 2>/dev/null || printf '%s' "$GZ_PARTITION")"
    if [ -z "$partition" ]; then
        warn "no partition recorded - skipping the survivor sweep rather than"
        warn "matching processes by name alone"
    else
        local left
        left="$(survivors "$partition")"
        if [ -n "$left" ]; then
            note "survivors in partition $partition:"
            printf '%s\n' "$left" | while read -r pid rest; do info "pid $pid $rest"; done
            printf '%s\n' "$left" | while read -r pid rest; do kill -TERM "$pid" 2>/dev/null || true; done
            sleep 2
            left="$(survivors "$partition")"
            if [ -n "$left" ]; then
                printf '%s\n' "$left" | while read -r pid rest; do
                    warn "SIGKILL pid $pid $rest"
                    kill -KILL "$pid" 2>/dev/null || true
                done
                sleep 1
            fi
            left="$(survivors "$partition")"
            if [ -n "$left" ]; then
                fail "still up in partition $partition:"
                printf '%s\n' "$left" | while read -r pid rest; do fail "pid $pid $rest"; done
                problems=$((problems + 1))
            else
                ok "no survivors in partition $partition"
            fi
        else
            ok "no survivors in partition $partition"
        fi
    fi

    # A session is ended by observation, never by assumption.
    if command -v ss >/dev/null 2>&1; then
        HMI_PORT="$(hmi_http_port)"
        local listeners
        listeners="$(ss -ltn 2>/dev/null | grep -E ":(${HMI_PORT:-8088})\b" || true)"
        if [ -n "$listeners" ]; then
            warn "something is still listening on ${HMI_PORT:-8088}:"
            printf '%s\n' "$listeners" | while read -r l; do warn "$l"; done
        else
            ok "no listener on 127.0.0.1:${HMI_PORT:-8088}"
        fi
    fi

    [ "$acted" -eq 0 ] && note "(no component was running)"
    [ "$problems" -eq 0 ] || return 1
    return 0
}

# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #

cmd_status() {
    local name pid up=0 down=0 state
    printf '%-16s %-8s %s\n' "COMPONENT" "STATE" "PID / NOTE"
    for name in "${COMPONENTS[@]}"; do
        if is_running "$name"; then
            pid="$(read_pid "$name")"
            up=$((up + 1))
            printf '%-16s %-8s %s\n' "$name" "up" "$pid"
        else
            down=$((down + 1))
            state="down"
            if [ -f "$(pid_file "$name")" ]; then state="down"; pid="stale PID file"; else pid="-"; fi
            printf '%-16s %-8s %s\n' "$name" "$state" "$pid"
        fi
    done
    printf '\n'
    printf '%-16s %s\n' "runtime dir" "$RUN_DIR"
    printf '%-16s %s\n' "GZ_PARTITION" "$(cat "$RUN_DIR/partition" 2>/dev/null || printf '%s (not started)' "$GZ_PARTITION")"
    printf '%-16s %s\n' "ROS_DOMAIN_ID" "$(cat "$RUN_DIR/domain" 2>/dev/null || printf '%s (not started)' "$ROS_DOMAIN_ID")"
    printf '%-16s %s\n' "bridge config" "$BRIDGE_CONFIG"
    printf '%-16s %s\n' "HMI config" "$HMI_CONFIG"
    printf '%-16s %s\n' "PLC side" "started separately on the owner's Windows machine (TIA Portal / PLCSIM Advanced)"

    [ "$up" -eq "${#COMPONENTS[@]}" ] && return 0
    [ "$up" -eq 0 ] && return 1
    return 3
}

# --------------------------------------------------------------------------- #

main() {
    local action="${1:---help}"
    [ $# -gt 0 ] && shift
    case "$action" in
        (start)             cmd_start "$@" ;;
        (stop)              cmd_stop "$@" ;;
        (status)            cmd_status "$@" ;;
        (-h|--help|help)    usage ;;
        (*)                 die "unknown command '$action' (start | stop | status)" ;;
    esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
