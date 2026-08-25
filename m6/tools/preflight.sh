#!/usr/bin/env bash
# preflight.sh - is this boot's bridge actually delivering?
#
# WHY THIS EXISTS (measured 2026-08-25, six stack boots in one session):
# gz-sim publishes and the ros_gz parameter_bridge SOMETIMES starves -
# per topic, arbitrarily: one boot bridged f1's back scanner but not
# f1's odom, the next bridged odom and no render sensor at all, and one
# lost a single nav lidar MID-RUN (its gz-side stamp froze at sim
# 296 s while every neighbour kept delivering). gz's own log says
# "NodeShared::Publish() Error: Interrupted system call" and nothing
# else anywhere says anything, because nothing is wrong on either side
# of the dead pipe. The failure then presents as the CELL misbehaving:
# fields evaluate stale, Motor never enables, four trucks stand at
# their spawns and the watchdog tears the tasks off them - 90 minutes
# of that diagnosis is what this two-minute check buys back.
#
# WHAT IT CHECKS is what the cell CONSUMES, ROS-side: odometry and the
# nav lidar for every vehicle in the table, one safety scanner as the
# render-thread witness, and the overhead camera the recorders read.
# A dead feed names itself; a clean pass prints one line per topic.
#
# Usage, after `m6.sh start` (any shell that can reach WSL's ROS):
#   source /opt/ros/jazzy/setup.bash && export ROS_DOMAIN_ID=96
#   bash m6/tools/preflight.sh
# Exit 0: every feed is live - proceed. Exit 1: the boot is bad; the
# only fix ever measured is stop/start again (a fresh subscriber
# connects cleanly - the wedge is per connection, not per topic), and
# a machine that refuses several boots in a row wants `wsl --shutdown`
# and, past that, a Windows reboot before any long run is worth taping.
set -u
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VIDS=$(python3 - <<'PY'
import sys
sys.path.insert(0, "m6/ipc")
import status_contract
print(" ".join(sorted(status_contract.VEHICLES)))
PY
)
cd "$REPO"
bad=0
# THE PROBES RUN IN PARALLEL WITH A LONG WINDOW, and the window is not
# padding: under the loopback-unicast DDS profile (fastdds_loopback.xml)
# a FRESH participant needs 10-20 s to walk the ~40-node discovery mesh
# before data flows - measured 2026-08-25, when a 6 s serial probe
# called a 10.3 Hz topic dead and nearly sent this rig to a Windows
# reboot it did not need. The cell's own nodes discover once at boot
# and stay connected; only one-shot probes pay this cost.
PROBE_S=25
TMPDIR="$(mktemp -d)"
trap "rm -rf $TMPDIR" EXIT
TOPICS=""
for vid in $VIDS; do
    TOPICS="$TOPICS /$vid/gz/odom /$vid/gz/scan_nav /$vid/gz/safety_scanner_back/measurement"
done
TOPICS="$TOPICS /overhead/image"
echo "preflight: the feeds the cell consumes, ROS-side (parallel, ${PROBE_S}s window)"
i=0
for topic in $TOPICS; do
    ( timeout "$PROBE_S" ros2 topic hz "$topic" 2>&1 | grep -q "average rate"         && echo "live" > "$TMPDIR/$i" || echo "DEAD" > "$TMPDIR/$i" ) &
    i=$(( i + 1 ))
done
wait
i=0
for topic in $TOPICS; do
    verdict="$(cat "$TMPDIR/$i" 2>/dev/null || echo DEAD)"
    [ "$verdict" = "live" ] || bad=1
    echo "  $verdict  $topic"
    i=$(( i + 1 ))
done
if [ "$bad" -ne 0 ]; then
    echo "preflight: FAILED - this boot's bridge is starved. Stop the"
    echo "stack and start it again; do not time, tape or gate anything"
    echo "on this boot."
    exit 1
fi
echo "preflight: OK"
