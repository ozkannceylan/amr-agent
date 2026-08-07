#!/usr/bin/env bash
#
# demo.sh - one command up, one command down, for the M5 teleoperation and
# safety demonstration.
#
#   ./demo.sh up      bring the whole demonstration up and report ready
#   ./demo.sh down    take it down and VERIFY nothing is left behind
#   ./demo.sh status  what is up right now
#   ./demo.sh check   the pre-flight only: does the Windows side exist yet
#
# ===========================================================================
# WHAT THIS IS, AND WHAT IT IS NOT
# ===========================================================================
#
# It starts existing processes with their existing configuration files. It
# adds no data path, no logic, no threshold and no default. It never edits a
# config. Every command still reaches the plant as
# HMI -> PLC -> bridge -> Gazebo (ADR 0008 D1), and the safety chain is
# onboard and hardwired and appears in no launch file (invariant 1).
#
# It is NOT stack.sh's replacement. stack.sh brings up the M4 commissioning
# cell: the arena world, five components, no safety chain. This file brings up
# the M5 composition - the warehouse world, the two safety scanners, the field
# evaluation, the speed channels and their carrier, the envelope gate, the
# bridge and the HMI. The two are different demonstrations and stack.sh is the
# M4 gate's own artefact, so it is left alone. What IS inherited from it, on
# purpose, is every mechanism that was paid for in a rehearsal: setsid process
# groups with one PID file each, the token check that makes a recycled PID read
# as down, the zombie-aware liveness test, bounded waits with deadlines, and
# the survivor sweep filtered by this run's GZ_PARTITION out of
# /proc/<pid>/environ. SURVIVOR_PATTERNS below is stack.sh's list EXTENDED,
# never replaced - the M5 processes are added to it, none is removed.
#
# ===========================================================================
# THE SEAM, WHICH IS THE WHOLE DIFFICULTY
# ===========================================================================
#
# This demonstration spans two operating systems:
#
#   WSL      Gazebo, the vehicle stack, the field evaluation, the speed
#            channels, the bridge, the HMI.  <- this script owns all of it
#   Windows  PLCSIM Advanced with the CPU in RUN, and the STAND-IN WRITER,
#            which is PowerShell and reaches the CPU through the PLCSIM
#            Advanced API rather than over OPC UA.  <- the owner's, by hand
#
# The Windows half is the owner's for two independent reasons and neither is
# negotiable here. PLCSIM Advanced and TIA Portal are not this script's to
# start, stop or change. And the stand-in writer needs a REAL CONSOLE: `estop
# open`, `estop close` and `reset pulse 2000` are typed at its window, and a
# writer started from a script logs "operator console = UNAVAILABLE" and can
# drive none of the three channels (bridge/STANDIN-WRITER-DESIGN.md section
# 4.1). Starting it from here would produce a demonstration in which no safety
# function can be made to act.
#
# So the seam is handled by CHECKING it, not by ignoring it. `up` refuses to
# begin until it has OBSERVED, on the Windows side:
#
#   1. the PLCSIM Advanced runtime instance process, and
#   2. the stand-in writer, by its named mutex Global\amr-standin-writer and
#      by its two listeners on 45015 and 45016.
#
# A stack whose WSL half starts against no writer looks like it worked and
# produces a vehicle that will not move. If the Windows checks cannot be run
# at all - no powershell.exe reachable from this WSL - `up` refuses rather
# than declaring a half-stack ready.
#
# ===========================================================================
# READINESS IS AN OBSERVABLE, NEVER A DURATION
# ===========================================================================
#
# docs/TODO.md records that stack.sh's readiness timeouts were never
# calibrated. m5-69 then measured what a fixed wait costs: under load,
# bring-up stretches up to 6.1x - Nav2 advertised /plan in 15-18 s idle and
# 74-97 s loaded - and a procedure that waits a fixed interval and then acts
# reports "the server had gone" when it had simply not arrived.
#
# So every wait here is a wait on a CONDITION with a deadline, and the
# deadlines are generous rather than tuned:
#
#   plant      a message actually CARRIED on each of six topics, one per
#              process that has to be alive for the demonstration to mean
#              anything. Not `ros2 topic list`: a ros_gz_bridge entry for a
#              gz topic nobody publishes logs "Creating GZ->ROS Bridge"
#              exactly as a working one does.
#   envelope   a message carried on /forklift/mode/applied
#   bridge     its own two log lines, in order: "session established", then
#              "startup rule R3 satisfied", which is the bridge saying that
#              all seven of its configured inputs carry a real plant sample
#   HMI        GET /state answering with session CONNECTED *and* metrics
#              present - a blank panel is not a boot reading
#
# When a wait expires this script says WHICH component and WHAT was expected,
# leaves everything running with its logs intact, and stops. A stack that
# half-starts silently is worse than one that refuses.
#
# And a log tail is never a verdict here. m5-69 established that every
# navigation log ends with "user interrupted with ctrl-c (SIGINT)" and "exit
# code -2" INCLUDING runs verified alive in the same second: a deliberate
# teardown and a crash write the identical log. Liveness in this file is a
# live process with the right token in its command line, or a message on a
# topic. Never an exit code, never the last line of a log.
#
# ===========================================================================
# EXIT CODES
#   0  the command did what it says
#   1  environment or pre-flight guard failed, or down did not reach clean
#   2  up refused because the demonstration is already running
#   3  status found some but not all components up
#   4  up spawned everything but a readiness check timed out
# ===========================================================================

set -uo pipefail

REPO="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# --------------------------------------------------------------------------- #
# Isolation. ROS_DOMAIN_ID does not isolate Gazebo, because gz transport does
# not use DDS. GZ_PARTITION does. Both are exported to every component, and
# the partition is what the survivor sweep filters on at teardown.
# --------------------------------------------------------------------------- #
export GZ_PARTITION="${GZ_PARTITION:-m5demo}"
export ROS_DOMAIN_ID="${ROS_DOMAIN_ID:-64}"

# Runtime state lives outside the repository: a demonstration must not make
# git status dirty, and on a /mnt/c checkout the Linux filesystem is the
# faster place for logs anyway.
RUN_DIR="${AMR_DEMO_RUN_DIR:-/tmp/amr-agent-demo}"

ROS_SETUP="${AMR_ROS_SETUP:-/opt/ros/jazzy/setup.bash}"

BRIDGE_VENV="${AMR_BRIDGE_VENV:-}"
HMI_VENV="${AMR_HMI_VENV:-}"

BRIDGE_CONFIG="${AMR_BRIDGE_CONFIG:-$REPO/bridge/config/bridge.yaml}"
HMI_CONFIG="${AMR_HMI_CONFIG:-$REPO/hmi/config.yaml}"
VEHICLE_CONFIG="${AMR_VEHICLE_CONFIG:-$REPO/agv/forklift/config.yaml}"
VEHICLE_MODEL="$REPO/agv/forklift/model.sdf"
VEHICLE_LAUNCH="$REPO/agv/forklift/launch/vehicle.launch.py"
WAREHOUSE_BRINGUP="$REPO/sim/launch/warehouse_bringup.launch.py"
WORLD="${AMR_DEMO_WORLD:-$REPO/sim/worlds/warehouse.sdf}"

# The Windows-side writer script, as the owner types it. Named here so the
# message this script prints and the RUNBOOK cannot drift apart.
WRITER_SCRIPT_WIN='bridge\standin_writer\standin_writer.ps1'
WRITER_MUTEX='Global\amr-standin-writer'
WRITER_FIELD_PORT=45015
WRITER_SPEED_PORT=45016

# The PLCSIM Advanced instance name is TOOL-DERIVED: it is read back from the
# PLCSIM Advanced control panel and never assumed (ADR 0006's discipline,
# applied to an instance name). This script never passes it to anything - it
# only quotes it back to the owner in the command they have to run - so a
# stale value here misleads and cannot misconfigure. Override per session.
WRITER_INSTANCE="${AMR_PLCSIM_INSTANCE:-safecell3}"

# Bounded waits, in seconds. Deliberately generous: m5-69 measured bring-up
# stretching up to 6.1x under load, and a deadline that is too short turns a
# slow start into a false diagnosis. Nothing here waits WITHOUT a deadline and
# nothing sleeps INSTEAD of observing.
WAIT_WRITER="${AMR_WAIT_WRITER:-300}"
WAIT_PLANT="${AMR_WAIT_PLANT:-300}"
WAIT_ENVELOPE="${AMR_WAIT_ENVELOPE:-120}"
WAIT_BRIDGE="${AMR_WAIT_BRIDGE:-180}"
WAIT_R3="${AMR_WAIT_R3:-180}"
WAIT_HMI="${AMR_WAIT_HMI:-120}"
TERM_GRACE="${AMR_TERM_GRACE:-15}"
KILL_GRACE="${AMR_KILL_GRACE:-5}"

# Components, in start order.
COMPONENTS=(plant envelope bridge monitor hmi)

declare -A COMPONENT_TOKEN=(
    [plant]="vehicle.launch.py"
    [envelope]="envelope_gate.py"
    [bridge]="run_bridge.py"
    [monitor]="viz/monitor/service.py"
    [hmi]="hmi_server.py"
)

# ---------------------------------------------------------------------------
# SURVIVOR SWEEP PATTERNS.
#
# This is stack.sh's SURVIVOR_PATTERNS *extended*, not replaced. That list
# exists because signalling `ros2 launch` does not bring its children down -
# measured by m4f-03 and in every rehearsal since - and because
# sto_contactor.py was found missing from it by m5-50b. Its eight entries are
# reproduced verbatim below, then the M5 processes are added: this
# composition's launch file, the four estimator processes, the field
# evaluation, the two safe-speed processes and the safe-speed gz bridge, the
# envelope gate, the smoother, the converter and the monitoring service.
#
# The converter and the smoother are in the list although this composition
# does not start them (see START ORDER below): a run that started
# envelope.launch.py by hand beside this one would otherwise leave them, and a
# teardown pattern list is cheap while a missed process costs the next run's
# first measurement.
#
# Nothing here is ever signalled on a name alone. Every match is filtered by
# this run's GZ_PARTITION read out of /proc/<pid>/environ, so a process
# belonging to another run or another user is seen and left alone. There is no
# blanket pkill anywhere in this file.
# ---------------------------------------------------------------------------
SURVIVOR_PATTERNS="gz sim|parameter_bridge|forklift_bringup.launch.py|run_bridge.py|forklift_io.py|obstacle_zone.py|hmi_server.py|sto_contactor.py"
SURVIVOR_PATTERNS="$SURVIVOR_PATTERNS|vehicle.launch.py|warehouse_bringup.launch.py"
SURVIVOR_PATTERNS="$SURVIVOR_PATTERNS|sensor_tf.py|wheel_odometry.py|imu_gate.py|ekf_node"
SURVIVOR_PATTERNS="$SURVIVOR_PATTERNS|field_evaluation.py|safe_speed_channels.py|safe_speed_link.py"
SURVIVOR_PATTERNS="$SURVIVOR_PATTERNS|envelope_gate.py|cmd_vel_to_tricycle.py|velocity_smoother"
SURVIVOR_PATTERNS="$SURVIVOR_PATTERNS|viz/monitor/service.py"

GUI="true"        # showcase default; --headless makes it false
MONITOR="false"   # the read-only map pane; --monitor turns it on
WAIT_FOR_WRITER="true"

PYTHON3=""
BRIDGE_PY=""
HMI_PY=""
HMI_PORT=""
MONITOR_PORT="${AMR_MONITOR_PORT:-8089}"
POWERSHELL=""
SPAWN_X=""; SPAWN_Y=""; SPAWN_Z=""; SPAWN_YAW=""

# --------------------------------------------------------------------------- #
# Output helpers. Plain ASCII, no colour: this output ends up in evidence.
# --------------------------------------------------------------------------- #

note() { printf '%s\n' "$*"; }
info() { printf '  %s\n' "$*"; }
ok()   { printf '  ok    %s\n' "$*"; }
warn() { printf '  WARN  %s\n' "$*" >&2; }
fail() { printf '  FAIL  %s\n' "$*" >&2; }
die()  { printf 'demo.sh: %s\n' "$*" >&2; exit 1; }
rule() { printf '%s\n' "---------------------------------------------------------------------"; }

usage() { sed -n '3,110p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

# --------------------------------------------------------------------------- #
# PID file lifecycle - stack.sh's, unchanged, for the reasons its comments give
# --------------------------------------------------------------------------- #

pid_file() { printf '%s/%s.pid' "$RUN_DIR" "$1"; }
log_file() { printf '%s/%s.log' "$RUN_DIR" "$1"; }

# kill -0 succeeds on a ZOMBIE. Reading the state field out of /proc/<pid>/stat
# closes the window in which "is it still up" answers yes about a corpse.
pid_alive() {
    local pid="$1" stat_line state
    [ -n "$pid" ] || return 1
    kill -0 "$pid" 2>/dev/null || return 1
    stat_line="$(cat "/proc/$pid/stat" 2>/dev/null)" || return 1
    state="$(printf '%s' "${stat_line##*) }" | cut -d' ' -f1)"
    [ "$state" = "Z" ] && return 1
    return 0
}

read_pid() {
    local file pid
    file="$(pid_file "$1")"
    [ -f "$file" ] || return 1
    pid="$(cat "$file" 2>/dev/null)"
    [ -n "$pid" ] || return 1
    case "$pid" in (*[!0-9]*) return 1 ;; esac
    printf '%s' "$pid"
}

# A component is running when its PID file names a live process whose command
# line still carries that component's token. The token is what makes a recycled
# PID read as down rather than as somebody else's process.
is_running() {
    local name="$1" pid cmdline
    pid="$(read_pid "$name")" || return 1
    pid_alive "$pid" || return 1
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

spawn() {
    local name="$1" command="$2" log pidf pid="" deadline
    log="$(log_file "$name")"
    pidf="$(pid_file "$name")"
    : > "$log"
    rm -f "$pidf"
    setsid bash -c "echo \$\$ > '$pidf'; $command" >"$log" 2>&1 &
    deadline=$((SECONDS + 10))
    while [ "$SECONDS" -lt "$deadline" ]; do
        pid="$(read_pid "$name")" && break
        sleep 0.1
    done
    if [ -z "$pid" ]; then
        fail "$name did not report a pid within 10s - see $log"
        return 1
    fi
    sleep 0.5
    if ! is_running "$name"; then
        fail "$name exited immediately. Last lines of $log:"
        tail -n 20 "$log" 2>/dev/null | while IFS= read -r line; do printf '        %s\n' "$line"; done
        rm -f "$pidf"
        return 1
    fi
    info "started $name pid $pid  log $log"
}

# wait_until <label> <timeout> <command...>
# Bounded foreground polling with a progress line, so a slow start looks slow
# rather than hung. Nothing in this script waits without a deadline.
wait_until() {
    local label="$1" timeout="$2"
    shift 2
    local start=$SECONDS deadline=$((SECONDS + timeout)) last_note=$SECONDS
    while [ "$SECONDS" -lt "$deadline" ]; do
        if "$@" >/dev/null 2>&1; then
            ok "$label  (after $((SECONDS - start))s)"
            return 0
        fi
        if [ $((SECONDS - last_note)) -ge 20 ]; then
            last_note=$SECONDS
            info "...still waiting for: $label  ($((SECONDS - start))s of ${timeout}s)"
        fi
        sleep 0.5
    done
    fail "$label - NOT OBSERVED within ${timeout}s"
    return 1
}

# --- readiness predicates --------------------------------------------------- #

log_has() { grep -q -F -- "$2" "$(log_file "$1")" 2>/dev/null; }

# A topic CARRYING a message, which is the only thing that proves the process
# behind it is alive. `ros2 topic list` does not: a ros_gz_bridge entry for a
# gz topic nobody publishes advertises exactly like a working one.
#
# BEST_EFFORT/VOLATILE on the reader matches a RELIABLE publisher as well as a
# best-effort one, so one predicate serves every topic below.
#
# THIS IS A RETRY LOOP AND NOT ONE LONG SUBSCRIPTION, AND THE REASON IS
# MEASURED. `ros2 topic echo` resolves the message type through the ros2 CLI
# DAEMON, and against a cold daemon it does not block: it prints "does not
# appear to be published yet / Could not determine the type for the passed
# topic" and exits 1 in 1.1 s - measured here on 2026-08-07 against
# /forklift/mode/applied while that topic was publishing at 20.007 Hz. A
# single-shot wait therefore reports "nothing published within 120 s" after one
# second, which is the 2026-08-05 daemon-cache lesson arriving in a new place
# and is exactly the misdiagnosis this brief exists to avoid. So each attempt
# gets a slice, the loop runs to the deadline, and the last error the tool
# actually printed is shown when the deadline is reached.
wait_topic() {
    local label="$1" timeout="$2" topic="$3"
    local start=$SECONDS deadline=$((SECONDS + timeout)) slice rc last_note=$SECONDS
    local err="$RUN_DIR/wait$(printf '%s' "$topic" | tr '/' '-').err"
    while [ "$SECONDS" -lt "$deadline" ]; do
        slice=$((deadline - SECONDS))
        [ "$slice" -gt 15 ] && slice=15
        timeout "$slice" bash -c "
            source '$ROS_SETUP' >/dev/null 2>&1
            exec ros2 topic echo --once --qos-reliability best_effort \
                 --qos-durability volatile '$topic'" >/dev/null 2>"$err"
        rc=$?
        if [ "$rc" -eq 0 ]; then
            ok "$label  ($topic carried a message after $((SECONDS - start))s)"
            return 0
        fi
        if [ $((SECONDS - last_note)) -ge 20 ]; then
            last_note=$SECONDS
            info "...still waiting for $topic  ($((SECONDS - start))s of ${timeout}s)"
        fi
        sleep 1
    done
    fail "$label - NOTHING PUBLISHED on $topic within ${timeout}s"
    if [ -s "$err" ]; then
        fail "last error from ros2 topic echo:"
        sed -n '1,4p' "$err" | while IFS= read -r line; do fail "  $line"; done
    fi
    return 1
}

hmi_ready() {
    "$PYTHON3" - "$1" <<'PY' 2>/dev/null
import json, sys, urllib.request
with urllib.request.urlopen("http://127.0.0.1:%s/state" % sys.argv[1], timeout=1.5) as handle:
    state = json.load(handle)
session = state.get("session") or {}
sys.exit(0 if session.get("state") == "CONNECTED" and state.get("metrics") else 1)
PY
}

hmi_http_port() {
    awk '
        /^[^[:space:]#]/ { in_http = ($0 ~ /^http:/) }
        in_http && $1 == "port:" { gsub(/[^0-9]/, "", $2); if ($2 != "") { print $2; exit } }
    ' "$HMI_CONFIG"
}

# The spawn pose is READ OUT OF sim/launch/warehouse_bringup.launch.py rather
# than repeated here. That file is where the pose is argued for, and m5-69
# moved it (-6.00 -> -3.00) for a measured reason; a copy in this script would
# be a second place to forget. A parse that fails is a hard stop, never a
# silent default.
read_spawn_pose() {
    local key val
    for key in _SPAWN_X _SPAWN_Y _SPAWN_Z _SPAWN_YAW; do
        val="$(sed -n "s/^${key} *= *'\([^']*\)'.*/\1/p" "$WAREHOUSE_BRINGUP" | head -n1)"
        [ -n "$val" ] || return 1
        case "$key" in
            (_SPAWN_X)   SPAWN_X="$val" ;;
            (_SPAWN_Y)   SPAWN_Y="$val" ;;
            (_SPAWN_Z)   SPAWN_Z="$val" ;;
            (_SPAWN_YAW) SPAWN_YAW="$val" ;;
        esac
    done
    SPAWN_X="${AMR_DEMO_X:-$SPAWN_X}"
    SPAWN_Y="${AMR_DEMO_Y:-$SPAWN_Y}"
    SPAWN_Z="${AMR_DEMO_Z:-$SPAWN_Z}"
    SPAWN_YAW="${AMR_DEMO_YAW:-$SPAWN_YAW}"
    return 0
}

# --------------------------------------------------------------------------- #
# THE WINDOWS SIDE. Observed, never assumed, and never started or stopped
# except for the stand-in writer at teardown (see cmd_down).
#
# PLCSIM Advanced and TIA Portal are the owner's. Nothing in this file starts,
# stops, downloads, compiles or changes anything in either.
# --------------------------------------------------------------------------- #

find_powershell() {
    local candidate
    for candidate in \
        "/mnt/c/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" \
        "$(command -v powershell.exe 2>/dev/null || true)"
    do
        [ -n "$candidate" ] && [ -x "$candidate" ] && { printf '%s' "$candidate"; return 0; }
    done
    return 1
}

# One PowerShell call answers all four Windows questions, so a poll costs one
# process rather than four. Output is four `key=value` lines.
#
# The writer is detected by its NAMED MUTEX and by its two listeners, not by
# looking for a powershell process: the mutex is what the writer itself uses to
# refuse a second instance, so it is the writer's own definition of "already
# running". TryOpenExisting opens it WITHOUT acquiring, so this probe cannot
# take the mutex away from a writer that is starting.
windows_state() {
    [ -n "$POWERSHELL" ] || return 1
    "$POWERSHELL" -NoProfile -NonInteractive -Command '
        $m = $null
        $held = [System.Threading.Mutex]::TryOpenExisting("Global\amr-standin-writer", [ref]$m)
        if ($held) { $m.Dispose() }
        Write-Output ("mutex=" + $held)
        $p = @(Get-Process -Name "Siemens.Simatic.Simulation.Runtime.Instance.x64" -ErrorAction SilentlyContinue)
        Write-Output ("plcsim=" + ($p.Count -gt 0))
        $n = @(netstat -ano | Select-String -Pattern "LISTENING" | Select-String -Pattern ":45015\s")
        Write-Output ("field=" + ($n.Count -gt 0))
        $s = @(netstat -ano | Select-String -Pattern "LISTENING" | Select-String -Pattern ":45016\s")
        Write-Output ("speed=" + ($s.Count -gt 0))
    ' 2>/dev/null | tr -d '\r'
}

windows_field() {
    printf '%s\n' "$1" | sed -n "s/^$2=//p" | head -n1
}

writer_present() {
    local state
    state="$(windows_state)" || return 1
    [ "$(windows_field "$state" mutex)" = "True" ] || return 1
    [ "$(windows_field "$state" field)" = "True" ] || return 1
    [ "$(windows_field "$state" speed)" = "True" ] || return 1
    return 0
}

print_writer_command() {
    note ""
    note "  Open a Windows PowerShell window ON THE WINDOWS SIDE, cd to the"
    note "  repository, and run this. Leave the window open - it is the"
    note "  operator keyboard for estop, zone and reset:"
    note ""
    note "    powershell -ExecutionPolicy Bypass -File $WRITER_SCRIPT_WIN -Instance $WRITER_INSTANCE"
    note ""
    note "  -Instance is tool-derived: read it back from the PLCSIM Advanced"
    note "  control panel. '$WRITER_INSTANCE' is this script's default, not a fact"
    note "  about your machine (export AMR_PLCSIM_INSTANCE to change it)."
    note ""
}

cmd_check() {
    local state m p f s problems=0
    note "pre-flight: the Windows side"
    POWERSHELL="$(find_powershell || true)"
    if [ -z "$POWERSHELL" ]; then
        fail "no powershell.exe reachable from this WSL, so the Windows half of"
        fail "this demonstration cannot be checked at all. Refusing rather than"
        fail "declaring a half-stack ready: a WSL-only bring-up looks like it"
        fail "worked and produces a vehicle that will not move."
        return 1
    fi
    ok "powershell.exe  $POWERSHELL"

    state="$(windows_state)"
    if [ -z "$state" ]; then
        fail "the Windows probe returned nothing - cannot see the Windows side"
        return 1
    fi
    m="$(windows_field "$state" mutex)"
    p="$(windows_field "$state" plcsim)"
    f="$(windows_field "$state" field)"
    s="$(windows_field "$state" speed)"

    if [ "$p" = "True" ]; then
        ok "PLCSIM Advanced runtime instance process is running"
    else
        fail "no PLCSIM Advanced runtime instance process. Start PLCSIM Advanced"
        fail "and put the CPU in RUN from TIA Portal. That is yours to do; this"
        fail "script never touches TIA or the CPU."
        problems=$((problems + 1))
    fi
    info "(the CPU being in RUN is proven later, by the bridge establishing a"
    info " session - a running process is not a running CPU)"

    if [ "$m" = "True" ] && [ "$f" = "True" ] && [ "$s" = "True" ]; then
        ok "stand-in writer up: mutex $WRITER_MUTEX held,"
        ok "  listening on $WRITER_FIELD_PORT (field) and $WRITER_SPEED_PORT (speed)"
    else
        fail "stand-in writer NOT fully up  (mutex=$m  ${WRITER_FIELD_PORT}=$f  ${WRITER_SPEED_PORT}=$s)"
        problems=$((problems + 1))
    fi

    [ "$problems" -eq 0 ]
}

# --------------------------------------------------------------------------- #
# Environment guard, WSL side
# --------------------------------------------------------------------------- #

find_venv_python() {
    local override="$1"; shift
    local candidate
    if [ -n "$override" ]; then
        [ -x "$override/bin/python" ] && { printf '%s/bin/python' "$override"; return 0; }
        [ -x "$override" ] && { printf '%s' "$override"; return 0; }
        return 1
    fi
    for candidate in "$@"; do
        [ -x "$candidate/bin/python" ] && { printf '%s/bin/python' "$candidate"; return 0; }
    done
    return 1
}

check_environment() {
    local problems=0 script config

    PYTHON3="$(command -v python3 || true)"
    [ -n "$PYTHON3" ] || { fail "python3 not on PATH"; problems=$((problems + 1)); }

    for script in \
        "$VEHICLE_LAUNCH" \
        "$WAREHOUSE_BRINGUP" \
        "$WORLD" \
        "$VEHICLE_MODEL" \
        "$REPO/agv/forklift/scripts/envelope_gate.py" \
        "$REPO/agv/forklift/scripts/field_evaluation.py" \
        "$REPO/agv/forklift/scripts/safe_speed_link.py" \
        "$REPO/bridge/run_bridge.py" \
        "$REPO/hmi/hmi_server.py"
    do
        [ -f "$script" ] || { fail "missing $script"; problems=$((problems + 1)); }
    done

    for config in "$BRIDGE_CONFIG" "$HMI_CONFIG" "$VEHICLE_CONFIG"; do
        [ -f "$config" ] || { fail "missing config $config"; problems=$((problems + 1)); }
    done

    if [ ! -f "$ROS_SETUP" ]; then
        fail "ROS 2 setup not found at $ROS_SETUP (set AMR_ROS_SETUP)"
        problems=$((problems + 1))
    else
        bash -c "source '$ROS_SETUP' && command -v ros2" >/dev/null 2>&1 || {
            fail "ros2 not on PATH after sourcing $ROS_SETUP"; problems=$((problems + 1)); }
        bash -c "source '$ROS_SETUP' && ros2 pkg prefix ros_gz_sim" >/dev/null 2>&1 || {
            fail "ROS 2 package ros_gz_sim not found - the bringup needs it"; problems=$((problems + 1)); }
    fi

    # gz is NOT on the login PATH on this machine: it ships in the ROS overlay
    # (/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz) and only exists after the
    # setup file is sourced. Checking it in the bare shell - which is what
    # stack.sh does - fails on a machine where Gazebo is present and working.
    # Every component below is started from a sourced shell, so that is the
    # shell the guard has to ask.
    bash -c "source '$ROS_SETUP' >/dev/null 2>&1 && command -v gz" >/dev/null 2>&1 || {
        fail "gz not on PATH after sourcing $ROS_SETUP - Gazebo is the simulator (invariant 12)"
        problems=$((problems + 1)); }
    command -v timeout >/dev/null 2>&1 || { fail "timeout(1) not on PATH - every wait here needs it"; problems=$((problems + 1)); }

    BRIDGE_PY="$(find_venv_python "$BRIDGE_VENV" /opt/amr-bridge-venv "$HOME/amr-bridge-venv" || true)"
    [ -n "$BRIDGE_PY" ] || { fail "bridge venv not found (set AMR_BRIDGE_VENV). See bridge/README.md."; problems=$((problems + 1)); }

    HMI_PY="$(find_venv_python "$HMI_VENV" "$HOME/amr-hmi-venv" /opt/amr-hmi-venv || true)"
    [ -n "$HMI_PY" ] || { fail "HMI venv not found (set AMR_HMI_VENV). See hmi/README.md."; problems=$((problems + 1)); }

    HMI_PORT="$(hmi_http_port)"
    [ -n "$HMI_PORT" ] || { fail "no http.port in $HMI_CONFIG"; problems=$((problems + 1)); }

    read_spawn_pose || {
        fail "could not read the spawn pose out of $WAREHOUSE_BRINGUP"
        fail "(_SPAWN_X/_SPAWN_Y/_SPAWN_Z/_SPAWN_YAW). Refusing rather than"
        fail "guessing a pose - m5-69 moved it for a measured reason."
        problems=$((problems + 1))
    }

    local groups_line
    groups_line="$(grep -m1 '^groups:' "$BRIDGE_CONFIG" 2>/dev/null)"
    case "$groups_line" in
        (*forklift*) : ;;
        (*) fail "$BRIDGE_CONFIG carries: ${groups_line:-<no groups line>}"
            fail "It does not name the forklift group, so no Forklift/ node is read"
            fail "or written and this demonstration has no path to the plant."
            problems=$((problems + 1)) ;;
    esac
    case "$groups_line" in
        (*warning*) : ;;
        (*) warn "$BRIDGE_CONFIG does not name the warning group, so the field"
            warn "evaluation's verdict will not reach the PLC over the bridge." ;;
    esac

    [ "$problems" -eq 0 ]
}

# --------------------------------------------------------------------------- #
# The boot state of the safety mirrors, READ rather than asserted.
#
# TorqueOffDemand boots TRUE. This is the single most misleading thing about a
# cold start: the vehicle is torque-off until a monitored reset, and thirty
# seconds after a clean bring-up an owner who does not know that concludes the
# stack is broken. So instead of printing a remembered claim, this reads the
# controller's own mirrors through the committed read-only instrument and
# prints what the CPU actually says.
# --------------------------------------------------------------------------- #

report_boot_state() {
    local csv="$RUN_DIR/boot-mirrors.csv" endpoint
    endpoint="$(sed -n 's/^ *endpoint: *"\(.*\)".*/\1/p' "$BRIDGE_CONFIG" | head -n1)"
    [ -n "$endpoint" ] || return 1
    "$BRIDGE_PY" "$REPO/bridge/tools/observe_safety_mirrors.py" \
        --endpoint "$endpoint" --csv "$csv" --seconds 1.0 --hz 4 \
        --label "demo.sh up: boot state" >"$RUN_DIR/boot-mirrors.log" 2>&1 || return 1
    "$PYTHON3" - "$csv" <<'PY'
import csv, sys
rows = list(csv.DictReader(open(sys.argv[1], newline="", encoding="utf-8")))
if not rows:
    sys.exit(1)
r = rows[-1]
want = ["TorqueOffDemand", "EStopDemand", "ZoneStopDemand", "SpeedMonitorDemand",
        "SafetyResetRequired", "SafetyResetFault", "MotionEnable", "SpeedCeiling",
        "WarningFieldOccupied", "ProcessStopActive", "TeleopActive", "HmiLinkOk"]
for k in want:
    if k in r:
        print("    %-22s %s" % (k, r[k]))
print("TORQUE_OFF=%s" % r.get("TorqueOffDemand", "?"))
print("WARNING_OCCUPIED=%s" % r.get("WarningFieldOccupied", "?"))
PY
}

# --------------------------------------------------------------------------- #
# up
# --------------------------------------------------------------------------- #

up_abort() {
    fail "$1 did not start - stopping here, in the middle of the start order."
    fail "What is up is listed below. Read its log, then './demo.sh down'."
    note ""
    cmd_status
    exit 1
}

cmd_up() {
    while [ $# -gt 0 ]; do
        case "$1" in
            (--headless)        GUI="false" ;;
            (--gui)             GUI="true" ;;
            (--monitor)         MONITOR="true" ;;
            (--no-wait-writer)  WAIT_FOR_WRITER="false" ;;
            (*) die "up: unknown option $1 (try --headless, --monitor, --no-wait-writer)" ;;
        esac
        shift
    done

    mkdir -p "$RUN_DIR" || die "cannot create runtime directory $RUN_DIR"

    local up
    up="$(running_components)"
    if [ -n "$up" ]; then
        note "demo.sh: refusing to start - already running:"
        printf '%s\n' "$up" | while IFS= read -r c; do info "$c"; done
        note "Run './demo.sh down' first, or './demo.sh status'."
        return 2
    fi

    check_environment || die "environment guard failed; nothing was started"

    # ---- the Windows side, before anything is spawned ---------------------- #
    rule
    if ! cmd_check; then
        if [ "$WAIT_FOR_WRITER" != "true" ]; then
            fail "the Windows side is not ready and --no-wait-writer was given."
            return 1
        fi
        print_writer_command
        note "Waiting for the stand-in writer (up to ${WAIT_WRITER}s). Ctrl-C to give up."
        wait_until "the stand-in writer is up on both listeners" "$WAIT_WRITER" \
            writer_present || {
            fail "no stand-in writer appeared. Nothing was started."
            fail "Without it the CPU receives no e-stop circuit, no zone circuit,"
            fail "no reset and no speed readings, so the vehicle cannot move and"
            fail "no safety function can be made to act."
            return 1
        }
        cmd_check || { fail "the Windows pre-flight still fails. Nothing was started."; return 1; }
    fi

    rule
    note "bringing up the M5 teleoperation and safety demonstration"
    info "repo            $REPO"
    info "runtime dir     $RUN_DIR"
    info "GZ_PARTITION    $GZ_PARTITION"
    info "ROS_DOMAIN_ID   $ROS_DOMAIN_ID"
    info "world           $WORLD"
    info "spawn           x=$SPAWN_X y=$SPAWN_Y z=$SPAWN_Z yaw=$SPAWN_YAW"
    info "                (read out of sim/launch/warehouse_bringup.launch.py)"
    info "bridge config   $BRIDGE_CONFIG"
    info "HMI config      $HMI_CONFIG  (page on 127.0.0.1:$HMI_PORT)"
    info "Gazebo GUI      $GUI"
    info "monitor pane    $MONITOR"
    if [ "$GUI" = "true" ] && [ -z "${DISPLAY:-}" ] && [ -z "${WAYLAND_DISPLAY:-}" ]; then
        warn "gui:=true with no DISPLAY or WAYLAND_DISPLAY - use --headless if the"
        warn "GUI client fails to open. Rendering is software (llvmpipe) either way."
    fi

    printf '%s\n' "$GZ_PARTITION" > "$RUN_DIR/partition"
    printf '%s\n' "$ROS_DOMAIN_ID" > "$RUN_DIR/domain"

    local readiness=0

    # ---- 1. the plant, the vehicle and the safety sources ------------------ #
    #
    # ONE launch file, and it is the committed one that DECLARES these
    # processes and REFUSES their invalid combinations:
    # agv/forklift/launch/vehicle.launch.py. The world and the spawn pose are
    # what sim/launch/warehouse_bringup.launch.py adds, and they are passed
    # here rather than copied.
    #
    # Why not warehouse_bringup.launch.py itself: it does not declare
    # field_evaluation, safe_speed or safe_speed_link, so through it the field
    # evaluation and the speed channels never start - and those two are the
    # whole safety half of this demonstration. Reaching them means passing the
    # arguments to the file that declares them, which is this one.
    #
    # nodes:=true starts forklift_io.py and obstacle_zone.py.
    # ekf/tf/wheel_odom/imu_gate:=true is the estimator, all four or none.
    # ground_truth_tf:=false leaves the EKF the sole publisher of
    #   forklift/odom -> forklift/base_link (invariant 10).
    note "1/5 plant, vehicle, field evaluation, speed channels"
    spawn plant "cd '$REPO' && source '$ROS_SETUP' && exec ros2 launch '$VEHICLE_LAUNCH' \
        world:='$WORLD' name:=Forklift \
        x:=$SPAWN_X y:=$SPAWN_Y z:=$SPAWN_Z yaw:=$SPAWN_YAW \
        gui:=$GUI server:=true sto_contactor:=true nodes:=true \
        tf:=true wheel_odom:=true imu_gate:=true ekf:=true ground_truth_tf:=false \
        field_evaluation:=true safe_speed:=true safe_speed_link:=true" || up_abort plant

    # Six topics, one per process that has to be alive. Each is a message
    # CARRIED, not a name advertised.
    wait_topic "simulation clock (gz server)"            "$WAIT_PLANT" /clock || readiness=1
    wait_topic "navigation lidar"                        60 /forklift/scan || readiness=1
    wait_topic "obstacle_zone.py"                        60 /forklift/obstacle/min_distance || readiness=1
    wait_topic "forklift_io.py"                          60 /forklift/fork_height || readiness=1
    wait_topic "field_evaluation.py (warning verdict)"   90 /forklift/warning_field/occupied || readiness=1
    wait_topic "safe_speed_channels.py (reading head A)" 60 /forklift/drive_speed/channel_a || readiness=1
    [ "$readiness" -eq 0 ] || up_abort "the plant"

    # ---- 2. the envelope gate --------------------------------------------- #
    #
    # STARTED AS ITS OWN PROCESS, NOT THROUGH envelope.launch.py, AND THE
    # REASON IS INVARIANT 10. envelope.launch.py also starts
    # cmd_vel_to_tricycle.py, which publishes /forklift/cmd/steer_angle and
    # /forklift/cmd/traction_speed - the same two topics the BRIDGE publishes
    # from the PLC's setpoints. In an autonomy run that is the whole point; in
    # a teleoperation run it would put a second publisher on the PLC's own
    # setpoints, and a converter that republishes a held command at a fixed
    # rate (LESSONS 2026-08-04) would keep issuing one after the PLC withdrew
    # it. So the gate runs alone, with the command line envelope.launch.py
    # gives it and the same config file.
    #
    # It is not optional. It publishes /forklift/mode/applied and
    # /forklift/vehicle/heartbeat, which are two of the bridge's seven
    # configured inputs, so without it the bridge's startup rule R3 never
    # completes and no bridge heartbeat ever reaches the CPU.
    note "2/5 envelope gate"
    spawn envelope "cd '$REPO' && source '$ROS_SETUP' && exec python3 \
        '$REPO/agv/forklift/scripts/envelope_gate.py' --config '$VEHICLE_CONFIG' \
        --ros-args -p use_sim_time:=true" || up_abort envelope
    wait_topic "envelope_gate.py (mode applied)" "$WAIT_ENVELOPE" /forklift/mode/applied || up_abort "the envelope gate"

    # ---- 3. the bridge ----------------------------------------------------- #
    note "3/5 bridge (OPC UA client of the CPU)"
    spawn bridge "cd '$REPO' && source '$ROS_SETUP' && exec '$BRIDGE_PY' \
        '$REPO/bridge/run_bridge.py' --config '$BRIDGE_CONFIG'" || up_abort bridge
    wait_until "bridge session established (the CPU is in RUN and reachable)" "$WAIT_BRIDGE" \
        log_has bridge "session established" || {
        fail "the bridge did not establish a session."
        fail "Expected: the line 'session established' in $(log_file bridge)."
        fail "Check that the CPU is in RUN in PLCSIM Advanced and that the"
        fail "endpoint in $BRIDGE_CONFIG answers."
        readiness=1
    }
    wait_until "bridge startup rule R3 satisfied (all 7 inputs carry a real sample)" "$WAIT_R3" \
        log_has bridge "startup rule R3 satisfied" || {
        fail "R3 never completed. The bridge names each input still missing in"
        fail "$(log_file bridge) - that names the vehicle process that is not"
        fail "publishing."
        readiness=1
    }

    # ---- 4. the monitoring service (optional) ------------------------------ #
    if [ "$MONITOR" = "true" ]; then
        note "4/5 monitoring service (read-only map pane)"
        spawn monitor "cd '$REPO' && source '$ROS_SETUP' && exec python3 \
            '$REPO/viz/monitor/service.py' --port $MONITOR_PORT" || {
            warn "the monitoring service did not start. It feeds the HMI map pane"
            warn "only; the process zones and every safety lamp are unaffected."
        }
    else
        note "4/5 monitoring service - not started (pass --monitor for the map pane)"
    fi

    # ---- 5. the HMI, last -------------------------------------------------- #
    #
    # Last because HmiLinkOk is FALSE at the PLC until its counter has been
    # SEEN to change, and starting it before there is a server only produces a
    # reconnect loop.
    note "5/5 HMI"
    spawn hmi "cd '$REPO' && exec '$HMI_PY' '$REPO/hmi/hmi_server.py' --config '$HMI_CONFIG'" || up_abort hmi
    wait_until "HMI session CONNECTED with metrics on the page" "$WAIT_HMI" \
        hmi_ready "$HMI_PORT" || {
        fail "the HMI page never reported a CONNECTED session with metrics."
        fail "A blank panel is not a boot reading. Log: $(log_file hmi)"
        readiness=1
    }

    note ""
    rule
    cmd_status

    # ---- the boot state, read from the controller -------------------------- #
    note ""
    note "The controller's own view at this moment (read over OPC UA, not asserted):"
    local boot torque warning
    boot="$(report_boot_state 2>/dev/null)"
    if [ -n "$boot" ]; then
        printf '%s\n' "$boot" | grep -v '^[A-Z_]*='
        torque="$(printf '%s\n' "$boot" | sed -n 's/^TORQUE_OFF=//p')"
        warning="$(printf '%s\n' "$boot" | sed -n 's/^WARNING_OCCUPIED=//p')"
    else
        warn "could not read the safety mirrors; the note below still applies."
        torque=""
    fi

    note ""
    rule
    if [ "$readiness" -ne 0 ]; then
        fail "EVERY PROCESS WAS SPAWNED, BUT AT LEAST ONE READINESS CHECK FAILED."
        fail "Nothing was torn down. Read the failing check above and its log in"
        fail "$RUN_DIR, then './demo.sh down'."
        rule
        return 4
    fi

    note "READY."
    note ""
    # The one line the owner needs at the moment it matters. Printed from the
    # value just read where that read succeeded, and from the specification
    # where it did not - and it says which.
    if [ "$torque" = "True" ]; then
        note "  >> TorqueOffDemand is TRUE right now, read from the CPU. THE VEHICLE IS"
        note "  >> TORQUE-OFF AND WILL NOT MOVE UNTIL YOU DO THE MONITORED RESET."
        note "  >> This is intended, not a fault: it boots TRUE at every CPU start."
    elif [ -n "$torque" ]; then
        note "  >> TorqueOffDemand reads $torque. It boots TRUE at every CPU start, so if"
        note "  >> the vehicle will not move, the monitored reset is the first thing to try."
    else
        note "  >> TorqueOffDemand boots TRUE at every CPU start, so the vehicle is"
        note "  >> TORQUE-OFF UNTIL YOU DO THE MONITORED RESET. Intended, not a fault."
    fi
    note ""
    note "  The monitored reset needs BOTH hands at once, and all three of its"
    note "  preconditions, or it is refused:"
    note "     writer window:  estop close        (the circuit must be closed)"
    note "     HMI page:       release PROCESS STOP"
    note "     then, together: type  reset pulse 2000  at the writer AND hold the"
    note "                     HMI RESET button across the same two seconds"
    note ""
    if [ "$warning" = "True" ]; then
        note "  Note: WarningFieldOccupied reads True. The reduced speed limit is in"
        note "  force and a reset is refused while the vehicle is above it. Clear the"
        note "  warning field first."
        note ""
    fi
    note "  Operator page:  http://127.0.0.1:$HMI_PORT/"
    note "  Logs:           $RUN_DIR"
    note "  Full procedure: RUNBOOK.md"
    rule
    return 0
}

# --------------------------------------------------------------------------- #
# down
# --------------------------------------------------------------------------- #

stop_group() {
    local pid="$1" label="$2" deadline
    kill -TERM -- "-$pid" 2>/dev/null || kill -TERM "$pid" 2>/dev/null || true
    deadline=$((SECONDS + TERM_GRACE))
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

# Survivors of THIS run only. Matched by pgrep, then filtered by the partition
# recorded at start: a pid whose /proc/<pid>/environ does not carry it belongs
# to somebody else and is never signalled. The sweep excludes ITSELF and any
# shell whose command line quotes one of the patterns (LESSONS 2026-08-06: a
# sweep that matches its own command line proves nothing).
survivors() {
    local partition="$1" line pid environ
    pgrep -af "$SURVIVOR_PATTERNS" 2>/dev/null | while read -r line; do
        pid="${line%% *}"
        case "$pid" in (*[!0-9]*) continue ;; esac
        [ "$pid" = "$$" ] && continue
        case "${line#* }" in (*demo.sh*|*stack.sh*) continue ;; esac
        environ="$(tr '\0' '\n' < "/proc/$pid/environ" 2>/dev/null)" || continue
        printf '%s\n' "$environ" | grep -qx "GZ_PARTITION=$partition" || continue
        printf '%s %s\n' "$pid" "${line#* }"
    done
}

listeners_on() {
    ss -ltnH 2>/dev/null | awk -v p=":$1" '$4 ~ p"$" {print}'
}

# The stand-in writer, stopped by IDENTITY: a Windows process whose command
# line actually contains standin_writer.ps1. Never by name (every one of them
# is "powershell"), never by port. Reported before it is acted on.
stop_writer() {
    local out
    [ -n "$POWERSHELL" ] || return 1
    # THE SWEEP EXCLUDES ITSELF, and here that is not a formality: this very
    # command line contains the string "standin_writer.ps1", so a match on the
    # command line alone finds THIS PowerShell as well as the writer - measured
    # on 2026-08-07, two matches where one process existed. `$PID` is the
    # exclusion (LESSONS 2026-08-06, in its Windows form).
    out="$("$POWERSHELL" -NoProfile -NonInteractive -Command '
        function Find-Writer {
            @(Get-CimInstance Win32_Process |
              Where-Object { $_.ProcessId -ne $PID -and $_.CommandLine -and
                             $_.CommandLine -match "standin_writer\.ps1" })
        }
        $procs = Find-Writer
        if ($procs.Count -eq 0) { Write-Output "none"; exit 0 }
        foreach ($p in $procs) { Write-Output ("match=" + $p.ProcessId) }
        foreach ($p in $procs) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
        Start-Sleep -Milliseconds 1200
        Write-Output ("left=" + (Find-Writer).Count)
    ' 2>/dev/null | tr -d '\r')"
    printf '%s\n' "$out"
}

cmd_down() {
    local keep_writer="false" sweep_shm="true"
    while [ $# -gt 0 ]; do
        case "$1" in
            (--keep-writer) keep_writer="true" ;;
            (--keep-shm)    sweep_shm="false" ;;
            (*) die "down: unknown option $1 (try --keep-writer, --keep-shm)" ;;
        esac
        shift
    done

    PYTHON3="$(command -v python3 || true)"
    POWERSHELL="$(find_powershell || true)"
    HMI_PORT="$(hmi_http_port 2>/dev/null)"
    local problems=0 acted=0 name pid i partition left=""

    note "taking the M5 teleoperation and safety demonstration down"

    if [ ! -d "$RUN_DIR" ]; then
        note "  (no runtime directory $RUN_DIR - nothing this script started)"
    fi

    # Reverse start order: the operator's end first, the plant last.
    for (( i=${#COMPONENTS[@]}-1; i>=0; i-- )); do
        name="${COMPONENTS[$i]}"
        if is_running "$name"; then
            pid="$(read_pid "$name")"
            acted=1
            stop_group "$pid" "$name" || problems=$((problems + 1))
            rm -f "$(pid_file "$name")"
        elif [ -f "$(pid_file "$name")" ]; then
            info "$name not running (stale PID file removed)"
            rm -f "$(pid_file "$name")"
        else
            info "$name not running"
        fi
    done

    # ---- survivors ---------------------------------------------------------- #
    partition="$(cat "$RUN_DIR/partition" 2>/dev/null || printf '%s' "$GZ_PARTITION")"
    if [ -z "$partition" ]; then
        warn "no partition recorded - skipping the survivor sweep rather than"
        warn "matching processes by name alone"
    else
        left="$(survivors "$partition")"
        if [ -n "$left" ]; then
            note "survivors in partition $partition:"
            printf '%s\n' "$left" | while read -r pid rest; do info "pid $pid $rest"; done
            printf '%s\n' "$left" | while read -r pid rest; do kill -TERM "$pid" 2>/dev/null || true; done
            sleep 3
            left="$(survivors "$partition")"
            if [ -n "$left" ]; then
                printf '%s\n' "$left" | while read -r pid rest; do
                    warn "SIGKILL pid $pid $rest"
                    kill -KILL "$pid" 2>/dev/null || true
                done
                sleep 2
            fi
            left="$(survivors "$partition")"
            if [ -n "$left" ]; then
                fail "still up in partition $partition:"
                printf '%s\n' "$left" | while read -r pid rest; do fail "pid $pid $rest"; done
                problems=$((problems + 1))
            else
                ok "no survivor process in partition $partition"
            fi
        else
            ok "no survivor process in partition $partition"
        fi
    fi

    # ---- the ros2 CLI daemon ------------------------------------------------ #
    # A cold daemon cache is not node state, and a stale one is inherited by the
    # next run (LESSONS 2026-08-05). Stopping it is part of teardown.
    if bash -c "source '$ROS_SETUP' && ros2 daemon stop" >/dev/null 2>&1; then
        ok "ros2 daemon stopped"
    else
        info "ros2 daemon was not running"
    fi

    # ---- ports -------------------------------------------------------------- #
    if command -v ss >/dev/null 2>&1; then
        local port l
        for port in "${HMI_PORT:-8088}" "$MONITOR_PORT"; do
            l="$(listeners_on "$port")"
            if [ -n "$l" ]; then
                fail "something is STILL LISTENING on 127.0.0.1:$port:"
                printf '%s\n' "$l" | while read -r line; do fail "  $line"; done
                problems=$((problems + 1))
            else
                ok "no listener on 127.0.0.1:$port"
            fi
        done
    else
        warn "ss(1) not available - the listener check was not run"
        problems=$((problems + 1))
    fi

    # ---- /dev/shm ----------------------------------------------------------- #
    # m5-69 request 5: the teardown that removes processes does not remove their
    # Fast-DDS segments, and they accumulate across runs. Swept only AFTER the
    # survivor sweep reported clean, and only over this user's own segments.
    if [ "$sweep_shm" = "true" ]; then
        local before after
        before="$(ls -1 /dev/shm 2>/dev/null | wc -l)"
        if [ -z "$left" ] && [ "$problems" -eq 0 ]; then
            find /dev/shm -maxdepth 1 -user "$(id -u)" \
                \( -name 'fastrtps_*' -o -name 'sem.fastrtps_*' \) \
                -delete 2>/dev/null || true
            after="$(ls -1 /dev/shm 2>/dev/null | wc -l)"
            ok "/dev/shm swept: $before entries -> $after"
        else
            info "/dev/shm not swept ($before entries): something is still running"
        fi
    fi

    # ---- the Windows side --------------------------------------------------- #
    rule
    note "the Windows side"
    if [ -z "$POWERSHELL" ]; then
        warn "no powershell.exe reachable - the writer and its two listeners were"
        warn "NOT checked. Down is not verified on the Windows side."
        problems=$((problems + 1))
    elif [ "$keep_writer" = "true" ]; then
        info "--keep-writer: the stand-in writer was left alone, on purpose"
        local state
        state="$(windows_state)"
        info "mutex=$(windows_field "$state" mutex) ${WRITER_FIELD_PORT}=$(windows_field "$state" field) ${WRITER_SPEED_PORT}=$(windows_field "$state" speed)"
    else
        local out state
        out="$(stop_writer)"
        if [ -z "$out" ]; then
            warn "the writer probe returned nothing"
            problems=$((problems + 1))
        elif [ "$out" = "none" ]; then
            ok "no stand-in writer process was running"
        else
            printf '%s\n' "$out" | sed -n 's/^match=/  stopped writer pid /p'
            if printf '%s\n' "$out" | grep -qx 'left=0'; then
                ok "the stand-in writer is gone"
            else
                fail "a stand-in writer process survived: $(printf '%s' "$out" | sed -n 's/^left=/count /p')"
                problems=$((problems + 1))
            fi
        fi
        # The mutex and the two listeners are the independent check: the writer
        # refuses a second instance on the mutex, so a released mutex is the
        # writer's own statement that it is gone.
        state="$(windows_state)"
        local m f s
        m="$(windows_field "$state" mutex)"
        f="$(windows_field "$state" field)"
        s="$(windows_field "$state" speed)"
        [ "$m" = "False" ] && ok "$WRITER_MUTEX is free" || { fail "$WRITER_MUTEX is STILL HELD"; problems=$((problems + 1)); }
        [ "$f" = "False" ] && ok "nothing listening on $WRITER_FIELD_PORT" || { fail "$WRITER_FIELD_PORT is STILL LISTENING"; problems=$((problems + 1)); }
        [ "$s" = "False" ] && ok "nothing listening on $WRITER_SPEED_PORT" || { fail "$WRITER_SPEED_PORT is STILL LISTENING"; problems=$((problems + 1)); }
    fi
    note ""
    note "  PLCSIM Advanced and TIA Portal were not touched. They are yours, and"
    note "  the CPU keeps running - which is what you want between takes."
    note "  A cold CPU start is the only thing that clears SpeedChainSeen."

    rule
    [ "$acted" -eq 0 ] && note "(no component of this script's was running)"
    if [ "$problems" -eq 0 ]; then
        note "DOWN, AND VERIFIED CLEAN: no component, no survivor in the partition,"
        note "no listener on the HMI or monitor port, ros2 daemon stopped,"
        note "/dev/shm swept."
        if [ "$keep_writer" = "true" ]; then
            note "The stand-in writer was KEPT (--keep-writer) and its two listeners"
            note "are still up. This is not a clean Windows side; it is a deliberate"
            note "one, for a second take without retyping the writer command."
        else
            note "No stand-in writer, and both writer ports free."
        fi
        return 0
    fi
    fail "DOWN DID NOT REACH CLEAN - $problems item(s) above. The next run will"
    fail "start dirty and its first measurement will be wrong. Fix them first."
    return 1
}

# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #

cmd_status() {
    local name pid up=0 down=0
    HMI_PORT="${HMI_PORT:-$(hmi_http_port 2>/dev/null)}"
    printf '%-12s %-8s %s\n' "COMPONENT" "STATE" "PID / NOTE"
    for name in "${COMPONENTS[@]}"; do
        if is_running "$name"; then
            pid="$(read_pid "$name")"
            up=$((up + 1))
            printf '%-12s %-8s %s\n' "$name" "up" "$pid"
        else
            down=$((down + 1))
            if [ -f "$(pid_file "$name")" ]; then pid="stale PID file"; else pid="-"; fi
            printf '%-12s %-8s %s\n' "$name" "down" "$pid"
        fi
    done
    printf '\n'
    printf '%-14s %s\n' "runtime dir"   "$RUN_DIR"
    printf '%-14s %s\n' "GZ_PARTITION"  "$(cat "$RUN_DIR/partition" 2>/dev/null || printf '%s (not started)' "$GZ_PARTITION")"
    printf '%-14s %s\n' "ROS_DOMAIN_ID" "$(cat "$RUN_DIR/domain" 2>/dev/null || printf '%s (not started)' "$ROS_DOMAIN_ID")"
    printf '%-14s %s\n' "operator page" "http://127.0.0.1:${HMI_PORT:-8088}/"
    printf '%-14s %s\n' "Windows side"  "PLCSIM Advanced and the stand-in writer - yours, started by hand"

    # monitor is optional, so "all up" is counted against the four that are not.
    local required=$((${#COMPONENTS[@]} - 1))
    is_running monitor && required=${#COMPONENTS[@]}
    [ "$up" -ge "$required" ] && return 0
    [ "$up" -eq 0 ] && return 1
    return 3
}

# --------------------------------------------------------------------------- #

main() {
    local action="${1:---help}"
    [ $# -gt 0 ] && shift
    case "$action" in
        (up)                cmd_up "$@" ;;
        (down)              cmd_down "$@" ;;
        (status)            cmd_status "$@" ;;
        (check)             POWERSHELL="$(find_powershell || true)"; cmd_check "$@" ;;
        (-h|--help|help)    usage ;;
        (*)                 die "unknown command '$action' (up | down | status | check)" ;;
    esac
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
