#!/usr/bin/env bash
# noise_probe.sh - is the noise this model CONFIGURES actually on the
# wire, and how big is it? A fixed number of frames off one topic, held
# still, reported as the temporal spread of each reading about its own
# mean.
#
#   bash m5_ver3/tools/noise_probe.sh scan  /forklift/gz/scan_nav
#   bash m5_ver3/tools/noise_probe.sh depth /forklift/gz/cam/depth_image
#
# WHY TEMPORAL AND NOT SPATIAL. A stationary scan of a warehouse has an
# enormous spread ACROSS beams and it says nothing at all: that spread is
# the room. What a noise block adds is spread across TIME at a FIXED
# beam, on a vehicle that is not moving, against a scene that is not
# moving. So every reading is followed frame by frame and the statistic
# is its own standard deviation. THE VEHICLE MUST BE AT REST while this
# runs, or the number produced is the room going past.
#
# WHAT IT ANSWERS, in the order the evidence file asks:
#
#   1. is there noise at all           per-reading temporal stddev > 0
#   2. is it the configured size       compared against the SDF's stddev
#   3. is it QUANTIZED                 a gaussian_quantized noise with
#                                      <precision> p leaves every value
#                                      an exact multiple of p. The probe
#                                      reports the residual r/p - round
#                                      (r/p): a quantized channel gives
#                                      ~0, an unquantized one gives a
#                                      uniform spread over +-0.5.
#                                      p is config.yaml's
#                                      noise_probe.quantization_grid_m,
#                                      which carries the reason this
#                                      model's lidars cannot declare it.
#
# IT DOES NOT ANSWER THE BIAS QUESTION and cannot. gz draws a
# <bias_mean>/<bias_stddev> ONCE per sensor at load and adds the same
# offset to every reading for the life of the run, so it is invisible to
# any statistic taken WITHIN one run - a constant offset shifts the mean
# and leaves the spread alone. Detecting it needs a reading whose true
# value is known independently, which is geometry and not statistics;
# EVIDENCE_MODEL_V3.md 5 does that against the warehouse walls by hand.
#
# IT ATTACHES, IT DOES NOT START. m5v3.sh owns bringup - this is
# tools/rtf_probe.sh's rule and for the same reason.
#
# SUBSCRIBING IS NOT FREE AND THE FIGURE SAYS SO. gz renders a sensor
# only while something is subscribed to it, so probing an UNBRIDGED
# sensor (the safety scanners, the 3D lidar) makes the simulator render
# it for the length of the probe. That is the intended cost of asking;
# it is also why an RTF reading taken beside this one is not the RTF of
# the stack on its own.
set -uo pipefail

TOOL=noise_probe
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
# MAINTENANCE OBLIGATION: a key read below is a key listed here.
load_config noise_probe.scan_samples noise_probe.depth_samples \
    noise_probe.capture_timeout_s noise_probe.quantization_grid_m \
    evidence.depth.patch_half

MODE="${1:-}"
TOPIC="${2:-}"
case "$MODE" in
    scan)  SAMPLES="$CFG_NOISE_PROBE_SCAN_SAMPLES" ;;
    depth) SAMPLES="$CFG_NOISE_PROBE_DEPTH_SAMPLES" ;;
    *) echo "usage: $0 scan|depth <gz topic>"; exit 2 ;;
esac
[ -n "$TOPIC" ] || { echo "usage: $0 scan|depth <gz topic>"; exit 2; }

source_ros

CAP="${TMPDIR:-/tmp}/m5v3_noise_$(date +%Y%m%d-%H%M%S).json"
echo "=== m5v3 noise probe ==="
echo "date       $(date -Is)"
echo "partition  $GZ_PARTITION"
echo "mode       $MODE"
echo "topic      $TOPIC"
echo "samples    $SAMPLES"
echo "capture    $CAP"
echo "capturing..."
# -n RATHER THAN -d: the statistic is over a COUNT of frames, and a
# duration would make the sample size depend on the real-time factor,
# which is the one thing a noise figure must not depend on.
#   AND THEREFORE A DEADLINE AROUND IT. `gz topic -e -n N` waits for its
#   N messages FOR EVER, so a misspelt topic, or a stack that is not up,
#   or a sensor nothing else is subscribed to and which therefore never
#   renders, would hang this probe silently instead of refusing. The
#   count is the sample; the timeout is only the bound on waiting for it,
#   and a capture that hits the bound is refused rather than analysed
#   short (a short sample would still produce a plausible-looking
#   standard deviation, which is the worse failure).
timeout "$CFG_NOISE_PROBE_CAPTURE_TIMEOUT_S" \
    gz topic -e -t "$TOPIC" --json-output -n "$SAMPLES" > "$CAP" 2>/dev/null
GOT="$(grep -c '^{' "$CAP" 2>/dev/null || true)"
[ "${GOT:-0}" -ge "$SAMPLES" ] || refuse \
    "$TOPIC delivered $SAMPLES frames inside ${CFG_NOISE_PROBE_CAPTURE_TIMEOUT_S}s" \
    "$CONFIG (noise_probe.capture_timeout_s) and $TOPIC" \
    "$GOT of $SAMPLES frames arrived in partition $GZ_PARTITION." \
    "check the spelling of the topic against 'gz topic -l', and that the" \
    "stack is up ('m5_ver3/m5v3.sh status'). Partial capture left at $CAP."

echo ""
# THE TWO REDUCTION CONSTANTS GO IN THROUGH argv, because a heredoc
# quoted 'PYTHON' - which is what stops the shell expanding $ inside a
# python program - also stops it expanding the ones that should be. The
# grid the quantization test measures against and the size of the depth
# patch are both behavioural, so neither may be spelled below.
python3 - "$CAP" "$MODE" "$CFG_NOISE_PROBE_QUANTIZATION_GRID_M" \
    "$CFG_EVIDENCE_DEPTH_PATCH_HALF" <<'PYTHON'
import base64
import json
import math
import struct
import sys

path, mode = sys.argv[1], sys.argv[2]
grid_m, half = float(sys.argv[3]), int(sys.argv[4])

frames = []
with open(path, "r", encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line:
            continue
        try:
            frames.append(json.loads(line))
        except json.JSONDecodeError:
            continue
if len(frames) < 2:
    print("fewer than two frames arrived - nothing to compare")
    raise SystemExit(1)


def stats(xs):
    n = len(xs)
    mean = sum(xs) / n
    if n < 2:
        return mean, 0.0
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    return mean, math.sqrt(var)


def quantile(xs, q):
    ordered = sorted(xs)
    return ordered[min(len(ordered) - 1, int(q * len(ordered)))]


def report_series(series, unit, precision):
    """series: list of per-reading time histories, all the same length."""
    sds, means = [], []
    for history in series:
        mean, sd = stats(history)
        sds.append(sd)
        means.append(mean)
    print("readings compared      %d" % len(series))
    print("frames per reading     %d" % len(series[0]))
    print("temporal stddev %s   mean %.6f  median %.6f  min %.6f  max %.6f" %
          (unit, sum(sds) / len(sds), quantile(sds, 0.5), min(sds), max(sds)))
    zero = sum(1 for sd in sds if sd == 0.0)
    print("readings with stddev 0 %d of %d" % (zero, len(sds)))
    # The quantization test. Every value in every frame, not just the
    # means: quantization is a property of the individual reading.
    residuals = []
    for history in series:
        for value in history:
            step = value / precision
            residuals.append(abs(step - round(step)))
    print("quantization to %.4f: |v/p - round(v/p)| mean %.6f  max %.6f" %
          (precision, sum(residuals) / len(residuals), max(residuals)))
    print("  (a quantized channel gives ~0; an unquantized one is uniform")
    print("   on [0, 0.5], so its mean lands near 0.25 and its max near 0.5)")


if mode == "scan":
    head = frames[0]
    print("frame id               %s" % head.get("frame", "<none>"))
    print("angle min / max / step %.7f / %.7f / %.9f rad" %
          (float(head.get("angleMin", 0)), float(head.get("angleMax", 0)),
           float(head.get("angleStep", 0))))
    print("count / vertical count %s / %s" % (head.get("count"), head.get("verticalCount")))
    print("range min / max        %s / %s m" % (head.get("rangeMin"), head.get("rangeMax")))
    print("")
    n = int(head.get("count", 0)) * int(head.get("verticalCount", 1))
    # Only beams that returned a FINITE range in every frame. A beam that
    # is out of range in one frame and not the next is the room, not the
    # noise, and averaging it would be inventing a reading.
    series = []
    finite_everywhere = 0
    for i in range(n):
        history = []
        ok = True
        for frame in frames:
            ranges = frame.get("ranges", [])
            if i >= len(ranges):
                ok = False
                break
            value = ranges[i]
            if isinstance(value, str) or value is None:   # "inf" / "NaN"
                ok = False
                break
            value = float(value)
            if not math.isfinite(value):
                ok = False
                break
            history.append(value)
        if ok:
            finite_everywhere += 1
            series.append(history)
    print("beams finite in every frame  %d of %d" % (finite_everywhere, n))
    if not series:
        print("no beam returned a finite range in every frame")
        raise SystemExit(1)
    report_series(series, "[m]", grid_m)
else:
    head = frames[0]
    width, height = int(head.get("width", 0)), int(head.get("height", 0))
    print("frame id               %s" % head.get("header", {}).get("data", [{}])[0].get("value", ["<none>"])[0])
    print("size / format          %d x %d / %s" % (width, height, head.get("pixelFormatType")))
    print("")
    # A CENTRAL PATCH, not the whole image: 640 x 480 x 40 frames is
    # 12 million floats and the statistic does not get better for it. The
    # patch is where the optical axis lands, which on this camera is the
    # floor a couple of metres ahead. HOW BIG IT IS is
    # evidence.depth.patch_half's answer and arrives in argv above -
    # sensor_evidence.py reduces the same patch of the same camera, and
    # two figures taken over two different windows are not comparable.
    xs = range(width // 2 - half, width // 2 + half)
    ys = range(height // 2 - half, height // 2 + half)
    planes = []
    for frame in frames:
        raw = base64.b64decode(frame["data"])
        planes.append(struct.unpack("<%df" % (len(raw) // 4), raw))
    series = []
    for y in ys:
        for x in xs:
            idx = y * width + x
            history = [plane[idx] for plane in planes]
            if all(math.isfinite(v) for v in history):
                series.append(history)
    print("central patch          %d x %d pixels at the image centre" % (2 * half, 2 * half))
    print("pixels finite in every frame  %d of %d" % (len(series), (2 * half) ** 2))
    if not series:
        print("no pixel in the patch carried a finite depth in every frame")
        raise SystemExit(1)
    depths = [sum(h) / len(h) for h in series]
    print("patch depth            mean %.6f m  min %.6f  max %.6f" %
          (sum(depths) / len(depths), min(depths), max(depths)))
    report_series(series, "[m]", grid_m)
PYTHON
