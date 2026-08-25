#!/usr/bin/env bash
# rtf_probe.sh - what real-time factor is the RUNNING m5-ver3 world
# holding? A fixed-length sample off the world statistics topic, reported
# as mean, median and floor.
#
#   bash m5_ver3/tools/rtf_probe.sh            # config.yaml's sample_s
#   RTF_SAMPLE_S=60 bash m5_ver3/tools/rtf_probe.sh
#
# IT PROBES, IT DOES NOT STAGE. m6's tools/rtf_spike.sh answers a
# different question - "how many trucks can this machine carry" - and to
# answer it, it starts a server of its own and spawns the fleet into it
# phase by phase. This track has ONE truck and the thing worth measuring
# is the stack the operator actually brought up, GUI, bridge, subscribers
# and all. So this attaches to the world m5v3.sh started, in m5v3.sh's
# partition, and starts nothing.
#   The consequence, stated because it is the whole meaning of the number:
#   WHAT THIS MEASURES IS WHATEVER WAS RUNNING WHEN IT WAS RUN. gz-sim
#   renders a gpu_lidar only while something is subscribed to its topic
#   (measured in m6: four trucks with no consumer run at RTF 0.995, the
#   same four with every lidar subscribed at 0.195), so an RTF taken while
#   the bridge is up is a different figure from one taken beside it. The
#   header printed below names the stack it found, and the evidence file
#   quotes both together or neither.
#
# WHY IT SAMPLES A TOPIC AND NOT `gz stats`
#   `gz stats` is Gazebo CLASSIC's verb. gz-tools for Harmonic (this tree
#   runs gz-sim 8.11.0) has no stats verb at all: it prints the general
#   help and exits 0, so a probe built on it would report NO SAMPLES on a
#   perfectly healthy sim, or worse, average an empty set. The real source
#   is gz.msgs.WorldStatistics on /world/<name>/stats, published at 10 Hz
#   and printed by `gz topic -e` as protobuf debug text with one
#   `real_time_factor:` line per message.
#
# WHY stdbuf -oL
#   `gz topic -e` block-buffers when its stdout is a file, and timeout
#   ends it with SIGTERM, so the last unflushed block - up to ~30 samples
#   - would be lost. Line buffering costs nothing at 10 Hz and makes the
#   sample count the honest one.
#
# THE CONSTANTS ARE config.yaml's, and this file reads them ITSELF rather
# than being handed them, so it can be pointed at a stack this shell did
# not start. It is a second READER of that file, never a second copy of
# any value in it - and since the fix round it is not a second copy of the
# READER either: refuse(), the parse and the ROS source are _common.sh's,
# shared with m5v3.sh.
set -uo pipefail

# _common.sh sets $REPO, $M5V3 and $CONFIG from its own location, checks
# and exports the isolation keys, and gives this script the voice its
# refusals speak in.
#   THE PARTITION IT EXPORTS IS WHAT MAKES THIS PROBE ASK THE RIGHT WORLD.
#   A concurrent m6 stack publishes statistics for its own four-truck
#   world on a topic of exactly the same name, and without it the sampler
#   would take whichever answered - a figure about somebody else's
#   simulation, printed under this track's name.
TOOL=rtf_probe
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
load_config world.name rtf_probe.sample_s

stack_line() {  # every process in THIS partition that the sweep would own
    local pid cmd out=""
    while read -r pid cmd; do
        case "$pid" in ''|*[!0-9]*) continue ;; esac
        tr '\0' '\n' 2>/dev/null < "/proc/$pid/environ" \
            | grep -qxF "GZ_PARTITION=$GZ_PARTITION" || continue
        out="$out${out:+ | }${cmd:0:36}"
    done < <(pgrep -af 'gz sim|parameter_bridge|image_bridge' 2>/dev/null)
    printf '%s\n' "${out:-<nothing in this partition - is the stack up?>}"
}

STATS_TOPIC="/world/$CFG_WORLD_NAME/stats"
SAMPLE_S="${RTF_SAMPLE_S:-$CFG_RTF_PROBE_SAMPLE_S}"
LOG="${TMPDIR:-/tmp}/m5v3_rtf_$(date +%Y%m%d-%H%M%S).log"

# ROS is sourced for gz itself and for no ROS node: this probe starts
# none. The path, the existence check and the `set -u` dance are
# _common.sh's.
source_ros

echo "=== m5v3 RTF probe ==="
echo "date       $(date -Is)"
echo "gz sim     $(gz sim --versions | head -1)"
echo "partition  $GZ_PARTITION"
echo "topic      $STATS_TOPIC"
echo "sample     ${SAMPLE_S}s"
echo "log        $LOG"
echo "cpu        $(grep -m1 'model name' /proc/cpuinfo | cut -d: -f2- | xargs), $(nproc) threads"
# THE STACK THIS FIGURE BELONGS TO, PRINTED WITH IT. See the header: what
# is subscribed decides what is rendered, so an RTF without its stack is
# not a reading. The test is the same environment test m5v3.sh sweeps by,
# so a concurrent m6 process is named by the pattern and then dropped.
echo "stack      $(stack_line)"

echo "sampling..."
timeout "$SAMPLE_S" stdbuf -oL gz topic -e -t "$STATS_TOPIC" > "$LOG" || true

# One awk over the samples: count, mean, floor, ceiling. The MEDIAN is the
# figure a stack with a window on it needs - m6 measured mean 0.806 with
# the GUI open against a median of 0.997, because it stalls and catches up
# - so the values are sorted and the middle one taken rather than inferred
# from the mean. No pipe with an early reader in it anywhere: under
# `set -o pipefail` a `head`-style exit would hand this pipeline the
# writer's SIGPIPE status and the verdict would read a failure as a pass.
SUMMARY="$(awk '/real_time_factor:/ { v[n++] = $2 + 0 }
    END {
        if (n == 0) exit 1
        for (i = 0; i < n; i++) { sum += v[i] }
        for (i = 1; i < n; i++) {
            key = v[i]
            for (j = i - 1; j >= 0 && v[j] > key; j--) { v[j + 1] = v[j] }
            v[j + 1] = key
        }
        med = (n % 2) ? v[int(n / 2)] : (v[n / 2 - 1] + v[n / 2]) / 2
        printf "%d %.4f %.4f %.4f %.4f", n, sum / n, med, v[0], v[n - 1]
    }' "$LOG")" || refuse "the world published statistics" "$LOG" \
    "no 'real_time_factor:' line arrived in ${SAMPLE_S}s." \
    "is the stack up in partition $GZ_PARTITION ('m5_ver3/m5v3.sh status')?"

read -r N MEAN MEDIAN FLOOR CEILING <<<"$SUMMARY"
echo ""
printf 'samples  %d over %ss (%.1f Hz - the topic publishes at 10 Hz and its rate sags with the RTF)\n' \
    "$N" "$SAMPLE_S" "$(awk "BEGIN{printf \"%.1f\", $N / $SAMPLE_S}")"
printf 'mean     %s\n'   "$MEAN"
printf 'median   %s\n'   "$MEDIAN"
printf 'floor    %s\n'   "$FLOOR"
printf 'ceiling  %s\n'   "$CEILING"
