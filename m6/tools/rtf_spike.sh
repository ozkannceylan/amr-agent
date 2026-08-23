#!/usr/bin/env bash
# rtf_spike.sh - how many forklifts can this machine's Gazebo carry?
# Server-only, no ROS stack, no writers: the world plus the derived
# models, real-time factor sampled off the world statistics topic. Run
# inside WSL.
#
#   bash m6/tools/rtf_spike.sh              # every id in VEHICLES
#   bash m6/tools/rtf_spike.sh f1 f2 f3 f4  # exactly these, in order
#
# It measures ONCE PER VEHICLE on ONE server process: the first truck
# alone for SOLO_S, then each further truck joins and the whole fleet so
# far is sampled for PHASE_S. Only the last phase is gated; the earlier
# ones are what turn a pass or fail into a scaling picture - the
# marginal cost of the Nth truck - and taking them from the same server
# makes the series a clean A/B: same load order, same page cache, same
# render context.
#
# AN UNSUBSCRIBED gpu_lidar IS NOT RENDERED, AND THAT IS THE WHOLE TRAP
#   gz-sim's Sensors system renders a camera or lidar only while some
#   connection exists on its topic. A spike that spawns four trucks and
#   subscribes to nothing therefore measures PHYSICS AND NOTHING ELSE:
#   measured on this machine 2026-08-22, four trucks with no consumer
#   run at RTF 0.995 on 1.0 cores of CPU, and the same four with all
#   sixteen lidars subscribed run at 0.195 on 2.8. Same world, same
#   models, same minute - the difference is only whether anyone is
#   listening. So this script HOLDS A SUBSCRIBER on every gpu_lidar of
#   every truck it spawns (RTF_CONSUME_LIDARS=1, the default) and counts
#   the scans it was actually delivered, because the stack this sizes
#   for has a bridge on every one of those topics. RTF_CONSUME_LIDARS=0
#   reproduces the physics-only shape M6.1's gate 1 measured, and is
#   kept only so the two numbers can be put side by side.
#
# WHY THE GATE IS AN ARGUMENT AND NOT A CONSTANT
#   The threshold belongs to the spec that asks the question, and the
#   two that have asked differ by more than rounding: M6.1 gated TWO
#   vehicles at 0.90, M6.5 gates FOUR at 0.30 (every loop in this tree
#   is wall-clock timed, so what a low RTF costs is simulated seconds
#   per wall second, not a missed deadline). One baked-in number would
#   have to be wrong for one of them, so it is env RTF_GATE and the
#   verdict line prints the fleet size it was applied to.
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
#   ambiguous once a second world exists. Its rate SAGS with the RTF -
#   60 s yields ~592 messages at 1.0 and ~400 at 0.24 - so the sample
#   count is itself a reading and is printed with every mean.
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
#   A vehicle the table does not yet own can still be spiked - that is
#   how a fleet is sized BEFORE the table grows - but only by naming its
#   pose in env RTF_POSE_<vid>="x y z yaw", never by guessing one.
set -euo pipefail

M6="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORLD="$M6/gazebo/warehouse_ver3.sdf"
WORLD_NAME=warehouse                 # the name INSIDE warehouse_ver3.sdf
STATS_TOPIC="/world/$WORLD_NAME/stats"
GATE="${RTF_GATE:-0.90}"             # M6.1's two-vehicle gate by default
LOAD_S="${RTF_LOAD_S:-8}"            # server up and world loaded
SETTLE_S="${RTF_SETTLE_S:-5}"        # spawned model settled on its wheels
SOLO_S="${RTF_SOLO_S:-30}"           # the first truck alone
PHASE_S="${RTF_PHASE_S:-60}"         # every phase after it
CONSUME="${RTF_CONSUME_LIDARS:-1}"   # 0 = physics only, M6.1's shape
LOGDIR="${RTF_LOGDIR:-${TMPDIR:-/tmp}}"

# The partition scopes every gz call below - the server, every spawn,
# every lidar subscriber and the sampler - so a concurrent step5 or m6
# stack neither answers this script's service calls nor contributes to
# its statistics.
export GZ_PARTITION=m6-rtf-spike

# ROS is sourced for gz itself (gz_tools_vendor lives under /opt/ros),
# not for any ROS node: this spike starts none. `set -u` is lifted
# across the source because the ament setup chain reads variables it has
# not yet defined.
set +u
# shellcheck disable=SC1091
source /opt/ros/jazzy/setup.bash
set -u

if [ "$#" -gt 0 ]; then
    VIDS=("$@")
else
    mapfile -t VIDS < <(PYTHONPATH="$M6/ipc" python3 -c 'import status_contract
for vid in sorted(status_contract.VEHICLES):
    print(vid)')
fi
[ "${#VIDS[@]}" -gt 0 ] || { echo "rtf_spike: no vehicles to spike"; exit 1; }

for vid in "${VIDS[@]}"; do
    [ -f "$M6/vehicles/$vid/model.sdf" ] || {
        echo "missing $M6/vehicles/$vid/model.sdf" \
             "- run tools/instantiate_vehicle.py --all"; exit 1; }
done

mkdir -p "$LOGDIR"
rm -f "$LOGDIR"/m6_rtf_scans_*.log

echo "=== m6 RTF spike ==="
echo "date        $(date -Is)"
echo "gz sim      $(gz sim --versions | head -1)"
echo "partition   $GZ_PARTITION"
echo "world       $WORLD"
echo "vehicles    ${VIDS[*]}  (${#VIDS[@]})"
echo "lidars      $([ "$CONSUME" = 1 ] && echo 'subscribed, so rendered' \
                                      || echo 'NOT subscribed - physics only')"
echo "gate        $GATE, on the ${#VIDS[@]}-vehicle phase"
echo "logs        $LOGDIR"
echo "cpu         $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | xargs), $(nproc) threads"
echo "kernel      $(uname -r)"

gz sim -s -r --headless-rendering -v 1 "$WORLD" &
SIM=$!
SUBS=()
cleanup() {
    [ "${#SUBS[@]}" -gt 0 ] && kill "${SUBS[@]}" 2>/dev/null
    kill $SIM 2>/dev/null
    wait $SIM 2>/dev/null
    true
}
trap cleanup EXIT
sleep "$LOAD_S"

pose() {  # pose <vid> -> "x y z yaw", from the one table that owns it
    local vid="$1" var="RTF_POSE_$1"
    if [ -n "${!var:-}" ]; then
        printf '%s\n' "${!var}"
        return 0
    fi
    PYTHONPATH="$M6/ipc" python3 -c 'import sys, status_contract
vid = sys.argv[1]
v = status_contract.VEHICLES.get(vid)
if v is None:
    sys.exit("rtf_spike: {0!r} is not in status_contract.VEHICLES - give "
             "its pose in env RTF_POSE_{0}=\"x y z yaw\"".format(vid))
s = v["spawn"]
print(s["x"], s["y"], s["z"], s["yaw"])' "$vid"
}

lidar_topics() {  # lidar_topics <vid>: every gpu_lidar topic the model has
    # Read out of the model that publishes them rather than listed here:
    # a fifth sensor, or a renamed one, has to change the load this script
    # measures without anyone remembering to change this script.
    awk '/<sensor[^>]*type="gpu_lidar"/ { s = 1 }
         s && match($0, /<topic>[^<]+<\/topic>/) {
             print substr($0, RSTART + 7, RLENGTH - 15); s = 0 }' \
        "$M6/vehicles/$1/model.sdf"
}

scanners() {  # scanners <vid>: each lidar's closest return, at rest
    # A truck can rest level and still be UNDRIVEABLE - a pose tucked into
    # racking puts geometry inside the fields before anything moves - so
    # every lidar is asked for one scan and its closest return printed.
    #
    # THIS IS NOT A PROTECTIVE VERDICT AND MUST NOT BE READ AS ONE. The
    # verdict is scripts/field_evaluation.py's: a field polygon over range
    # AND angle, which needs the ROS stack this spike deliberately does not
    # start. A raw minimum is also dominated by the truck's own structure -
    # f1, at the pose M6.1 validated in an empty aisle, reads 0.111-0.122 m
    # off its own forks and mast. What the number IS good for is the A/B
    # this script exists to make: run against a validated vehicle in the
    # same server, a new pose that sits in clutter shows up as a closest
    # return unlike the others'.
    local vid="$1" topic closest
    for topic in $(lidar_topics "$vid"); do
        closest="$(timeout 15 gz topic -e -n 1 -t "$topic" 2>/dev/null \
                   | awk '$1 == "ranges:" && $2 + 0 == $2 {
                              if (n++ == 0 || $2 < m) m = $2 }
                          END { if (n) printf "%.3f m", m
                                else printf "NO SCAN" }')"
        printf '    %-42s closest %s\n' "$topic" "$closest"
    done
}

consume() {  # consume <vid>: hold a subscriber on each of its lidars
    # The subscription is the point (see the header): it is what makes
    # gz-sim render the sensor at all. The grep keeps one short line per
    # delivered scan instead of the ~7 kB of protobuf debug text, so the
    # count below is exact and the log stays in the tens of kilobytes;
    # the writer is the process substitution's, and the pid held in SUBS
    # is `gz topic`'s, so killing it ends the pipeline from the source.
    local vid="$1" topic name
    [ "$CONSUME" = 1 ] || return 0
    for topic in $(lidar_topics "$vid"); do
        name="$(echo "$topic" | tr / _)"
        gz topic -e -t "$topic" \
            > >(grep --line-buffered '^frame:' \
                > "$LOGDIR/m6_rtf_scans$name.log") 2>/dev/null &
        SUBS+=($!)
    done
    echo "  $vid: $(lidar_topics "$vid" | wc -l) lidars subscribed" \
         "(${#SUBS[@]} total)"
}

scans_so_far() {
    # Every delivered scan so far, counted file by file. NOT `cat ... |
    # wc -l`: with RTF_CONSUME_LIDARS=0 there are no scan logs, the glob
    # stays literal, cat exits 1, and `set -o pipefail` turns a physics-
    # only run into an unexplained abort at the first measurement.
    local f total=0
    for f in "$LOGDIR"/m6_rtf_scans_*.log; do
        [ -f "$f" ] || continue
        total=$((total + $(wc -l < "$f")))
    done
    echo "$total"
}

spawn() {  # spawn <vid>
    local vid="$1" x y z yaw qw qz line var="RTF_POSE_$1" src=table
    line="$(pose "$vid")"
    if [ -n "${!var:-}" ]; then src="env $var"; fi
    read -r x y z yaw <<<"$line"
    [ -n "${yaw:-}" ] || { echo "rtf_spike: the pose for $vid is not" \
        "\"x y z yaw\": $line"; exit 1; }
    qw="$(awk "BEGIN{printf \"%.6f\", cos($yaw/2)}")"
    qz="$(awk "BEGIN{printf \"%.6f\", sin($yaw/2)}")"
    echo "spawning $vid at ($x, $y, $z) yaw $yaw  [$src]"
    gz service -s "/world/$WORLD_NAME/create" \
        --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
        --timeout 10000 \
        --req "sdf_filename: \"$M6/vehicles/$vid/model.sdf\", name: \"forklift_$vid\", pose: {position: {x: $x, y: $y, z: $z}, orientation: {w: $qw, z: $qz}}" \
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
    scanners "$vid"
    consume "$vid"
    sleep "$SETTLE_S"
}

MEAN=""
measure() {  # measure <label> <seconds>; prints one line, sets MEAN
    # Two statements, not one: bash expands every word of a `local`
    # before any of its assignments take effect, so a log= that read
    # $label on the same line would be an unbound-variable abort.
    local label="$1" secs="$2"
    local log="$LOGDIR/m6_rtf_$label.log" s n min max before after
    echo "sampling $STATS_TOPIC for ${secs}s ($label)..."
    before="$(scans_so_far)"
    timeout "$secs" stdbuf -oL gz topic -e -t "$STATS_TOPIC" > "$log" || true
    after="$(scans_so_far)"
    s="$(awk '/real_time_factor:/ { v = $2; sum += v; n++
                                    if (n == 1 || v < min) min = v
                                    if (n == 1 || v > max) max = v }
              END { if (n == 0) exit 1
                    printf "%d %.3f %.3f %.3f", n, sum / n, min, max }' \
         "$log")" || {
        echo "$label: NO SAMPLES in $log - is $STATS_TOPIC alive in" \
             "partition $GZ_PARTITION?"; exit 1; }
    read -r n MEAN min max <<<"$s"
    # The delivered scan rate beside the RTF: 10 Hz per lidar is what the
    # models ask for, and the gap between asked and delivered is where a
    # saturated renderer shows itself.
    printf '%-12s samples %5d  mean RTF %s  min %s  max %s  scans %6d (%s Hz)\n' \
           "$label" "$n" "$MEAN" "$min" "$max" "$((after - before))" \
           "$(awk "BEGIN{printf \"%.1f\", ($after - $before) / $secs}")"
}

SUMMARY=()
for i in "${!VIDS[@]}"; do
    spawn "${VIDS[$i]}"
    if [ "$i" -eq 0 ]; then
        measure "$((i + 1))-vehicle" "$SOLO_S"
    else
        measure "$((i + 1))-vehicle" "$PHASE_S"
    fi
    SUMMARY+=("$(printf '%2d vehicle(s)  mean RTF %s' "$((i + 1))" "$MEAN")")
done

echo "--- gate: ${#VIDS[@]}-vehicle mean RTF vs $GATE ---"
printf '%s\n' "${SUMMARY[@]}"
if awk "BEGIN{exit !($MEAN >= $GATE)}"; then
    echo "VERDICT: GO ($MEAN >= $GATE at ${#VIDS[@]} vehicles)"
else
    echo "VERDICT: STOP ($MEAN < $GATE at ${#VIDS[@]} vehicles)"
    exit 2
fi
