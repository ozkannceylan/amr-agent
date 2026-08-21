#!/usr/bin/env bash
#
# run_commissioning.sh - start, stop and inspect the Linux side of the M4
# forklift commissioning cell, against the virtual PLC instead of PLCSIM
# Advanced.
#
# The composition is .archive/stack.sh's (the M4 launcher's own table,
# quoted from sim/scenarios/forklift_commissioning.md section 1), minus row
# 1 - the CPU - which today is m5/m5_ver1/virtual_plc/ on the Windows side,
# started by the operator, never by this script:
#
#   1. sim            sim/launch/forklift_bringup.launch.py  (arena + spawn +
#                                                          ros_gz_bridge)
#   2. forklift_io    agv/forklift/scripts/forklift_io.py
#   3. obstacle_zone  agv/forklift/scripts/obstacle_zone.py
#   4. warning-clear  ros2 topic pub /forklift/warning_field/occupied false
#                     (the M5-era input the M4 cell predates - see
#                     m4/bridge.forklift.virtual.yaml's header)
#   5. bridge         bridge/run_bridge.py --config <rendered>
#   6. hmi            hmi/hmi_server.py --config <rendered>
#
# USAGE
#   ./run_commissioning.sh start
#   ./run_commissioning.sh stop
#   ./run_commissioning.sh status
#
# After start, run the gate exercise from Windows:
#   python m4\verify_commissioning.py --command-file C:\Temp\m4_cmds

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(dirname "$HERE")"
RUN_DIR="$HERE/runtime"
EV_DIR="$HERE/evidence"
mkdir -p "$RUN_DIR" "$EV_DIR"

RENDERED_BRIDGE="$RUN_DIR/bridge.rendered.yaml"
RENDERED_HMI="$RUN_DIR/hmi.rendered.yaml"

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

start_comp() {  # name pidfile logfile command...
    local name="$1" pidf="$2" logf="$3"; shift 3
    if is_up "$pidf"; then
        info "$name already running (pid $(cat "$pidf"))"
    else
        info "starting $name"
        setsid nohup "$@" >"$logf" 2>&1 &
        echo $! > "$pidf"
    fi
}

cmd_start() {
    local endpoint
    endpoint="$(host_endpoint)"
    local host_port="${endpoint#opc.tcp://}"
    if ! (exec 3<>"/dev/tcp/${host_port%:*}/${host_port#*:}") 2>/dev/null; then
        die "no OPC UA listener at $endpoint. Start the virtual PLC on the Windows side:
       python m5\\m5_ver1\\virtual_plc\\virtual_plc.py --command-file C:\\Temp\\m4_cmds
     (it stands where PLCSIM Advanced stood in 2026-07; NOT a PLC, no safety integrity)"
    fi
    ok "virtual PLC answers at $endpoint"

    [ -f /opt/ros/jazzy/setup.bash ] || die "ROS 2 Jazzy not found at /opt/ros/jazzy"
    # shellcheck disable=SC1091
    source /opt/ros/jazzy/setup.bash

    BRIDGE_PY=""
    for cand in "${AMR_BRIDGE_VENV:-}" /opt/amr-bridge-venv "$HOME/amr-bridge-venv"; do
        [ -n "$cand" ] || continue
        if [ -x "$cand/bin/python" ] && "$cand/bin/python" -c 'import asyncua, rclpy' 2>/dev/null; then
            BRIDGE_PY="$cand/bin/python"; break
        fi
    done
    [ -n "$BRIDGE_PY" ] || die "bridge venv not found (set AMR_BRIDGE_VENV)"
    HMI_PY=""
    for cand in "${AMR_HMI_VENV:-}" "$HOME/amr-hmi-venv" /opt/amr-hmi-venv; do
        [ -n "$cand" ] || continue
        if [ -x "$cand/bin/python" ]; then HMI_PY="$cand/bin/python"; break; fi
    done
    [ -n "$HMI_PY" ] || die "HMI venv not found (set AMR_HMI_VENV)"

    sed "s|@VPLC_ENDPOINT@|$endpoint|" "$HERE/bridge.forklift.virtual.yaml" > "$RENDERED_BRIDGE" \
        || die "could not render $RENDERED_BRIDGE"
    sed "s|^  endpoint: \"opc.tcp://[^\"]*\"|  endpoint: \"$endpoint\"|" \
        "$REPO/hmi/config.yaml" > "$RENDERED_HMI" || die "could not render $RENDERED_HMI"
    info "rendered both configs (endpoint $endpoint)"

    start_comp "arena+spawn" "$RUN_DIR/sim.pid" "$RUN_DIR/sim.log" \
        ros2 launch "$REPO/sim/launch/forklift_bringup.launch.py"
    start_comp "forklift_io" "$RUN_DIR/forklift_io.pid" "$RUN_DIR/forklift_io.log" \
        python3 "$REPO/agv/forklift/scripts/forklift_io.py" --config "$REPO/agv/forklift/config.yaml"
    start_comp "obstacle_zone" "$RUN_DIR/obstacle_zone.pid" "$RUN_DIR/obstacle_zone.log" \
        python3 "$REPO/agv/forklift/scripts/obstacle_zone.py" --config "$REPO/agv/forklift/config.yaml"
    start_comp "warning-clear" "$RUN_DIR/warning.pid" "$RUN_DIR/warning.log" \
        ros2 topic pub -r 2 /forklift/warning_field/occupied std_msgs/msg/Bool "{data: false}"
    start_comp "bridge" "$RUN_DIR/bridge.pid" "$RUN_DIR/bridge.log" \
        "$BRIDGE_PY" "$REPO/bridge/run_bridge.py" --config "$RENDERED_BRIDGE"

    # R3 withholds the heartbeat until every configured input carries a real
    # sample; its line in the log is the proof the plant is publishing.
    info "waiting for the bridge's startup rule R3"
    local i
    for i in $(seq 1 90); do
        if grep -q "R3" "$RUN_DIR/bridge.log" 2>/dev/null \
           && grep -qi "satisfied\|complete" "$RUN_DIR/bridge.log" 2>/dev/null; then
            ok "bridge startup rule R3 satisfied"
            break
        fi
        if ! is_up "$RUN_DIR/bridge.pid"; then
            die "bridge exited during startup; last log lines:
$(tail -n 20 "$RUN_DIR/bridge.log" 2>/dev/null)"
        fi
        if [ "$i" -eq 90 ]; then die "R3 not seen within 90 s; check $RUN_DIR/bridge.log"; fi
        sleep 1
    done

    start_comp "hmi" "$RUN_DIR/hmi.pid" "$RUN_DIR/hmi.log" \
        "$HMI_PY" "$REPO/hmi/hmi_server.py" --config "$RENDERED_HMI"
    for i in $(seq 1 30); do
        if grep -qi "listening\|serving\|8088" "$RUN_DIR/hmi.log" 2>/dev/null; then
            ok "HMI up (http://127.0.0.1:8088 - WSL loopback forwards to Windows)"
            return 0
        fi
        sleep 1
    done
    info "HMI started; see $RUN_DIR/hmi.log"
}

cmd_stop() {
    local pidf name
    for pidf in "$RUN_DIR"/hmi.pid "$RUN_DIR"/bridge.pid "$RUN_DIR"/warning.pid \
                "$RUN_DIR"/obstacle_zone.pid "$RUN_DIR"/forklift_io.pid "$RUN_DIR"/sim.pid; do
        [ -f "$pidf" ] || continue
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
    local pidf
    for pidf in "$RUN_DIR"/*.pid; do
        [ -f "$pidf" ] || continue
        if is_up "$pidf"; then
            ok "$(basename "$pidf" .pid) running (pid $(cat "$pidf"))"
        else
            info "$(basename "$pidf" .pid) down"
        fi
    done
}

case "${1:-}" in
    start)  cmd_start ;;
    stop)   cmd_stop ;;
    status) cmd_status ;;
    *) echo "usage: $0 start|stop|status" >&2; exit 2 ;;
esac
