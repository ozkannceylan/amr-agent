#!/usr/bin/env bash
#
# run_cell.sh - start, stop and inspect the Linux side of the M3 demonstration
# cell, against the virtual PLC instead of PLCSIM Advanced.
#
# The composition is the M3 gate's own (plc/demo-cell/SPEC.md section 11):
#
#   1. cell world     sim/launch/cell_bringup.launch.py  (gz server + ros_gz_bridge)
#   2. bridge         bridge/run_bridge.py --config <rendered>  (OPC UA client)
#   3. panel at rest  bridge/tools/cell_stimulus.py (default script) - the
#                     operator's hands off the panel: both stop circuits
#                     closed, both NO buttons released, republished at 1 Hz.
#                     Without it the bridge's R3 never closes (its heartbeat
#                     waits for all seven inputs, four of which are panel
#                     contacts). m3/verify_cell.py stops this process and
#                     takes the panel over when it runs the gate exercise.
#
# Row 0 - the CPU - is NOT started here and never was (the M3 runbook's row 1
# was PLCSIM Advanced on the owner's Windows machine; today it is the virtual
# PLC, m5/m5_ver1/virtual_plc/, started by the operator on Windows). This
# script probes for its listener before bringing anything up.
#
# The bridge config is rendered from m3/bridge.cell.virtual.yaml into the
# runtime dir with the Windows host address read from the default route -
# never assumed - and the virtual PLC's port 4841. No committed file is
# edited.
#
# USAGE
#   ./run_cell.sh start
#   ./run_cell.sh stop
#   ./run_cell.sh status
#
# After "start" reports the bridge's startup rule R3 satisfied, the cell is
# live and the operator's panel is yours: drive it with
# bridge/tools/cell_stimulus.py, or run the whole gate exercise with
# m3/verify_cell.py.

# No `set -u`: /opt/ros/jazzy/setup.bash references unbound variables of its
# own, and this script sources it.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
RUN_DIR="$HERE/runtime"
EV_DIR="$HERE/evidence"
mkdir -p "$RUN_DIR" "$EV_DIR"

CELL_PID="$RUN_DIR/cell_world.pid"
BRIDGE_PID="$RUN_DIR/bridge.pid"
STIM_PID="$RUN_DIR/panel_rest.pid"
CELL_LOG="$RUN_DIR/cell_world.log"
BRIDGE_LOG="$RUN_DIR/bridge.log"
STIM_LOG="$RUN_DIR/panel_rest.log"
RENDERED="$RUN_DIR/bridge.cell.rendered.yaml"

die()  { echo "FAIL  $*" >&2; exit 1; }
ok()   { echo "  ok  $*"; }
info() { echo "  ..  $*"; }

is_up() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }

host_endpoint() {
    local win_host
    win_host="$(ip route show default 2>/dev/null | awk '{print $3; exit}')"
    [ -n "$win_host" ] || die "could not read the Windows host address from the default route"
    echo "opc.tcp://$win_host:4841"
}

cmd_start() {
    # Row 0 first: the CPU seat. Both clients browse by namespace URI at
    # connect, so a missing endpoint is a connect failure, not a wait.
    local endpoint
    endpoint="$(host_endpoint)"
    local host_port="${endpoint#opc.tcp://}"
    if ! (exec 3<>"/dev/tcp/${host_port%:*}/${host_port#*:}") 2>/dev/null; then
        die "no OPC UA listener at $endpoint. Start the virtual PLC on the Windows side:
       python m5\\m5_ver1\\virtual_plc\\virtual_plc.py
     (it stands where PLCSIM Advanced stood in 2026-07; NOT a PLC, no safety integrity)"
    fi
    ok "virtual PLC answers at $endpoint"

    [ -f /opt/ros/jazzy/setup.bash ] || die "ROS 2 Jazzy not found at /opt/ros/jazzy"
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash

    # The bridge's interpreter must import BOTH rclpy (via the sourced
    # setup.bash) and asyncua (pinned venv) - bridge/run_bridge.py's own
    # docstring. Same discovery as m5_ver1/demo.sh's.
    BRIDGE_PY=""
    for cand in "${AMR_BRIDGE_VENV:-}" /opt/amr-bridge-venv "$HOME/amr-bridge-venv"; do
        [ -n "$cand" ] || continue
        if [ -x "$cand/bin/python" ] && "$cand/bin/python" -c 'import asyncua, rclpy' 2>/dev/null; then
            BRIDGE_PY="$cand/bin/python"
            break
        fi
    done
    [ -n "$BRIDGE_PY" ] || die "bridge venv not found (set AMR_BRIDGE_VENV). See bridge/README.md."
    ok "bridge interpreter: $BRIDGE_PY"

    sed "s|@VPLC_ENDPOINT@|$endpoint|" "$HERE/bridge.cell.virtual.yaml" > "$RENDERED" \
        || die "could not render $RENDERED"
    info "rendered $RENDERED (endpoint $endpoint)"

    if is_up "$CELL_PID"; then
        info "cell world already running (pid $(cat "$CELL_PID"))"
    else
        info "starting the cell world (headless gz + ros_gz_bridge)"
        setsid nohup ros2 launch "$REPO/sim/launch/cell_bringup.launch.py" \
            >"$CELL_LOG" 2>&1 &
        echo $! > "$CELL_PID"
    fi

    if is_up "$BRIDGE_PID"; then
        info "bridge already running (pid $(cat "$BRIDGE_PID"))"
    else
        info "starting the bridge (group: cell)"
        setsid nohup "$BRIDGE_PY" "$REPO/bridge/run_bridge.py" --config "$RENDERED" \
            >"$BRIDGE_LOG" 2>&1 &
        echo $! > "$BRIDGE_PID"
    fi

    if is_up "$STIM_PID"; then
        info "panel-at-rest already running (pid $(cat "$STIM_PID"))"
    else
        info "starting the panel at rest (cell_stimulus.py, default script)"
        setsid nohup python3 "$REPO/bridge/tools/cell_stimulus.py" --duration 86400 \
            >"$STIM_LOG" 2>&1 &
        echo $! > "$STIM_PID"
    fi

    # The bridge's startup rule R3 withholds its heartbeat until every
    # configured input carries a real sample - so R3 satisfied in the log is
    # the proof the plant is publishing and the server answered.
    info "waiting for the bridge's startup rule R3"
    local i
    for i in $(seq 1 60); do
        if grep -q "R3" "$BRIDGE_LOG" 2>/dev/null && grep -qi "satisfied\|complete" "$BRIDGE_LOG" 2>/dev/null; then
            ok "bridge startup rule R3 satisfied - the loop is closed"
            return 0
        fi
        if ! is_up "$BRIDGE_PID"; then
            die "bridge exited during startup; last log lines:
$(tail -n 20 "$BRIDGE_LOG" 2>/dev/null)"
        fi
        sleep 1
    done
    die "R3 not seen within 60 s; check $BRIDGE_LOG and $STIM_LOG"
}

cmd_stop() {
    local pidf name
    for pidf in "$STIM_PID" "$BRIDGE_PID" "$CELL_PID"; do
        name="$(basename "$pidf" .pid)"
        if is_up "$pidf"; then
            kill -TERM -"$(cat "$pidf")" 2>/dev/null
            info "sent SIGTERM to $name (group $(cat "$pidf"))"
        fi
        rm -f "$pidf"
    done
    sleep 2
    ok "stopped (the virtual PLC on Windows is yours to stop, as PLCSIM was)"
}

cmd_status() {
    if is_up "$CELL_PID"; then ok "cell world running (pid $(cat "$CELL_PID"))"; else info "cell world down"; fi
    if is_up "$BRIDGE_PID"; then ok "bridge running (pid $(cat "$BRIDGE_PID"))"; else info "bridge down"; fi
    if is_up "$STIM_PID"; then ok "panel-at-rest running (pid $(cat "$STIM_PID"))"; else info "panel-at-rest down"; fi
    local endpoint
    endpoint="$(host_endpoint)"
    local host_port="${endpoint#opc.tcp://}"
    if (exec 3<>"/dev/tcp/${host_port%:*}/${host_port#*:}") 2>/dev/null; then
        ok "virtual PLC answers at $endpoint"
    else
        info "no virtual PLC listener at $endpoint"
    fi
}

case "${1:-}" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
