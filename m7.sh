#!/usr/bin/env bash
# m7.sh — start / stop the gated console against the m6 broker.
#
#   ./m7.sh start   # one process: gateway MQTT + console
#   ./m7.sh stop
#
# Gateway and console share one process so there is one pending set.
# approve.py talks to the same broker (python3 m7/console/approve.py).
# Does not start the fleet, Gazebo, or a vehicle. The broker is the
# one m6.sh already started (VDA_MQTT_PORT). M7 is not a safety
# function. The console cannot reach a vehicle topic.
set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
M7="$REPO/m7"
PIDFILE="$M7/.m7_pids"
LOGDIR="$M7/logs"
HOST="${MQTT_HOST:-127.0.0.1}"
PORT="${VDA_MQTT_PORT:-1883}"

usage() {
    echo "usage: $0 start | stop" >&2
    return 2
}

start() {
    mkdir -p "$LOGDIR"
    if [ -f "$PIDFILE" ]; then
        while read -r pid; do
            if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
                echo "already running (pid $pid, see $PIDFILE). Run '$0 stop' first."
                return 1
            fi
        done < "$PIDFILE"
        rm -f "$PIDFILE"
    fi
    extra=(--mqtt-only)
    if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
        extra=()
        echo "m7: live model loop (budget from m7/console/client.yaml)"
    else
        echo "m7: gateway only (no ${ANTHROPIC_API_KEY+ANTHROPIC_API_KEY}; tests use a scripted client)"
    fi
    python3 "$M7/console/client.py" --serve "${extra[@]}" \
        --host "$HOST" --port "$PORT" \
        >> "$LOGDIR/console.log" 2>&1 &
    echo $! > "$PIDFILE"
    echo "m7: gateway+console pid $! on $HOST:$PORT"
    echo "operator: python3 $M7/console/approve.py list|approve|reject"
}

stop() {
    if [ ! -f "$PIDFILE" ]; then
        echo "m7 already down"
        return 0
    fi
    while read -r pid; do
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
        fi
    done < "$PIDFILE"
    rm -f "$PIDFILE"
    echo "m7 down"
}

cmd="${1:-}"
case "$cmd" in
    start) start ;;
    stop) stop ;;
    *) usage ;;
esac
