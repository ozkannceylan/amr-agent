#!/usr/bin/env bash
# rtf_spike.sh - spec gate 1: can this machine's Gazebo carry two
# forklifts? Server-only, no ROS stack, no writers: the world plus the
# derived models, real-time factor sampled off the world statistics
# topic. Run inside WSL.
#
# It measures TWICE on ONE server process: f1 alone for 30 s, then f2
# joins and both are sampled for 60 s. The second number is the gate;
# the first is what turns it into a scaling picture rather than a bare
# pass or fail, and taking it from the same server makes the pair a
# clean A/B - same load order, same page cache, same render context.
#
# WHY IT SAMPLES A TOPIC AND NOT `gz stats`
#   `gz stats` is Gazebo CLASSIC's command. gz-tools for Harmonic (this
#   tree runs gz-sim 8.11.0) has no `stats` verb at all: it prints the
#   general help, exits 0, and an awk looking for its "Factor[0.99]"
#   lines finds nothing. A spike that trusted it would report NO SAMPLES
#   on a perfectly healthy sim - or worse, average an empty set. The
#   real source is gz.msgs.WorldStatistics on /world/<name>/stats,
#   published at 10 Hz, printed by `gz topic -e` as protobuf debug text
#   with one `real_time_factor: 0.99857503342729925` line per message.
#   That line is what the awk below sums. /stats carries the same
#   messages; the world-scoped name is used because it cannot be
#   ambiguous once a second world exists.
#
# WHY stdbuf -oL
#   `gz topic -e` block-buffers when its stdout is a file, and timeout
#   ends it with SIGTERM, so the last unflushed block - up to ~30
#   samples - would be lost. Line buffering costs nothing at 10 Hz and
#   makes the sample count the honest one.
#
# WHY THE POSES ARE NOT SPELLED OUT HERE
#   ipc/status_contract.py's VEHICLES table is the one home for every
#   per-vehicle difference, spawn poses included. A copy here would be a
#   second opinion about where a truck starts, and the first pose that
#   had to move to clear geometry would move in one of the two places.
set -euo pipefail

STEP6="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORLD="$STEP6/gazebo/warehouse_ver2.sdf"
WORLD_NAME=warehouse                 # the name INSIDE warehouse_ver2.sdf
STATS_TOPIC="/world/$WORLD_NAME/stats"
GATE=0.90                            # spec proof gate 1
LOAD_S=8                             # server up and world loaded
SETTLE_S=5                           # spawned model settled on its wheels
SOLO_S=30                            # f1 alone
BOTH_S=60                            # f1 and f2
LOGDIR="${TMPDIR:-/tmp}"

# The partition scopes every gz call below - the server, both spawns and
# the sampler - so a concurrent step5 or step6 stack neither answers this
# script's service calls nor contributes to its statistics.
export GZ_PARTITION=step6-rtf-spike

# ROS is sourced for gz itself (gz_tools_vendor lives under /opt/ros),
# not for any ROS node: this spike starts none. `set -u` is lifted
# across the source because the ament setup chain reads variables it has
# not yet defined.
set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
set -u

for vid in f1 f2; do
    [ -f "$STEP6/vehicles/$vid/model.sdf" ] || {
        echo "missing $STEP6/vehicles/$vid/model.sdf" \
             "- run tools/instantiate_vehicle.py --all"; exit 1; }
done

echo "=== step6 RTF spike ==="
echo "date        $(date -Is)"
echo "gz sim      $(gz sim --versions | head -1)"
echo "partition   $GZ_PARTITION"
echo "world       $WORLD"
echo "cpu         $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | xargs), $(nproc) threads"
echo "kernel      $(uname -r)"

gz sim -s -r --headless-rendering -v 1 "$WORLD" &
SIM=$!
trap 'kill $SIM 2>/dev/null; wait $SIM 2>/dev/null' EXIT
sleep "$LOAD_S"

pose() {  # pose <vid> -> "x y z yaw", from the one table that owns it
    PYTHONPATH="$STEP6/ipc" python3 -c 'import sys, status_contract
s = status_contract.VEHICLES[sys.argv[1]]["spawn"]
print(s["x"], s["y"], s["z"], s["yaw"])' "$1"
}

spawn() {  # spawn <vid>
    local vid="$1" x y z yaw qw qz
    read -r x y z yaw <<<"$(pose "$vid")"
    qw="$(awk "BEGIN{printf \"%.6f\", cos($yaw/2)}")"
    qz="$(awk "BEGIN{printf \"%.6f\", sin($yaw/2)}")"
    echo "spawning $vid at ($x, $y, $z) yaw $yaw"
    gz service -s "/world/$WORLD_NAME/create" \
        --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
        --timeout 10000 \
        --req "sdf_filename: \"$STEP6/vehicles/$vid/model.sdf\", name: \"forklift_$vid\", pose: {position: {x: $x, y: $y, z: $z}, orientation: {w: $qw, z: $qz}}" \
        | grep -q "data: true" || { echo "spawn $vid refused"; exit 1; }
    sleep "$SETTLE_S"
    # THE RESTING POSE, READ BACK RATHER THAN ASSUMED. `data: true` says
    # the factory accepted the request, not that the truck is upright
    # where the table put it: a pose that lands inside racking gets the
    # same reply and then tips, sinks or is shoved out, and the RTF
    # measured around it would be a measurement of a fight. Two lines of
    # `gz model` turn "it spawned" into "it is at (x, y, ~0) level".
    echo "  $vid rests at:"
    gz model -m "forklift_$vid" --pose | sed -n '/Pose \[/,$p'
}

MEAN=""
measure() {  # measure <label> <seconds>; prints one line, sets MEAN
    # Two statements, not one: bash expands every word of a `local`
    # before any of its assignments take effect, so a log= that read
    # $label on the same line would be an unbound-variable abort.
    local label="$1" secs="$2"
    local log="$LOGDIR/step6_rtf_$label.log" s n min max
    echo "sampling $STATS_TOPIC for ${secs}s ($label)..."
    timeout "$secs" stdbuf -oL gz topic -e -t "$STATS_TOPIC" > "$log" || true
    s="$(awk '/real_time_factor:/ { v = $2; sum += v; n++
                                    if (n == 1 || v < min) min = v
                                    if (n == 1 || v > max) max = v }
              END { if (n == 0) exit 1
                    printf "%d %.3f %.3f %.3f", n, sum / n, min, max }' \
         "$log")" || {
        echo "$label: NO SAMPLES in $log - is $STATS_TOPIC alive in" \
             "partition $GZ_PARTITION?"; exit 1; }
    read -r n MEAN min max <<<"$s"
    printf '%-10s samples %4d  mean RTF %s  min %s  max %s\n' \
           "$label" "$n" "$MEAN" "$min" "$max"
}

spawn f1
measure one-vehicle "$SOLO_S"
SOLO_MEAN="$MEAN"

spawn f2
measure two-vehicle "$BOTH_S"

echo "--- gate 1: two-vehicle mean RTF vs $GATE ---"
echo "one vehicle  $SOLO_MEAN"
echo "two vehicles $MEAN"
if awk "BEGIN{exit !($MEAN >= $GATE)}"; then
    echo "VERDICT: GO ($MEAN >= $GATE)"
else
    echo "VERDICT: STOP ($MEAN < $GATE)"
    exit 2
fi
