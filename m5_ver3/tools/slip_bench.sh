#!/usr/bin/env bash
# slip_bench.sh - how much of a commanded wheel revolution does this truck
# NOT turn into ground? One straight segment forward, one astern, and the
# three numbers each of them needs to be read honestly.
#
#   bash m5_ver3/tools/slip_bench.sh            # config.yaml's cruise
#   SLIP_LABEL="compliance 0.05" bash m5_ver3/tools/slip_bench.sh
#
# WHAT IT MEASURES, IN THE WORDS OF THE THING BEING TUNED. Slip at steady
# cruise is
#
#     (commanded tread speed - ground truth speed) / commanded tread speed
#
# with the commanded tread speed being omega_cmd x wheel_radius. That is
# the definition the WheelSlip compliance in model.sdf is tuned against
# and the one EVIDENCE_MODEL_V3.md section 7 tabulates.
#
# AND WHY IT ALSO PRINTS THE ACHIEVED JOINT RATE. There are TWO ways for
# the ground to fall short of the command and they are not the same
# defect: the tyre can slip, or the JointController can simply fail to
# reach the commanded rate against its 500 N m effort limit. A bench that
# reported only the first would blame the tyre for the controller's
# shortfall, and the compliance would then be tuned to cancel a fault it
# has nothing to do with. So the drive joint's own rate is sampled beside
# the ground truth and the table carries both:
#
#     slip_cmd    against the COMMANDED rate  - the tuning target
#     slip_joint  against the ACHIEVED rate   - the tyre on its own
#
# When the controller is doing its job the two agree, and the run where
# they do not is the run that needed a different fix.
#
# TWO SEGMENTS, FORWARD THEN ASTERN, and the vehicle ends roughly where it
# began - the shape of agv/forklift/scripts/safe_speed_bench.py's profile,
# for its reason: a long profile that only ever drives one way walks into
# the racking. Forward is the TRAVEL direction, model -x, which is
# NEGATIVE omega at this joint (m6/ipc/follower.py: model yaw 0 points the
# forks at world -x, so travel heading is yaw + pi and forward traction is
# negative). Two segments also cost nothing and catch a sign error that
# one segment would hide.
#
# IT DRIVES A LIVE PLANT AND IT DOES NOT START ONE. m5v3.sh owns bringup;
# this attaches to whatever is up in this partition, exactly as
# tools/rtf_probe.sh does. It leaves the traction terminal at a standing
# zero, which on this model is a holding brake and not a silence
# (model.sdf, WHAT TORQUE REMOVAL IS AT THIS PLANT).
#
# IT READS THE GROUND TRUTH ON THE GZ SIDE, not through the ROS bridge.
# The bridge is a second process with a queue in it, and a bench that
# measures displacement over a window would be measuring that queue's
# behaviour as much as the plant's. gz topic --json-output is the shorter
# path to the same OdometryPublisher message.
set -uo pipefail

# _common.sh sets $REPO, $M5V3 and $CONFIG from its own location, checks
# and exports the isolation keys, and gives this script the voice its
# refusals speak in. THE PARTITION IS WHAT MAKES THIS BENCH DRIVE THE
# RIGHT TRUCK: a concurrent m6 stack carries a traction terminal of
# exactly the same name.
TOOL=slip_bench
# shellcheck source=_common.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
load_config \
    topics.odom_ground_truth topics.traction_cmd topics.joint_state \
    vehicle.wheel_radius_m wheel_odom.drive_joint_name \
    wheel_slip.bench.cruise_mps wheel_slip.bench.settle_s \
    wheel_slip.bench.sample_s wheel_slip.bench.rest_s

source_ros

RADIUS="$CFG_VEHICLE_WHEEL_RADIUS_M"
CRUISE="$CFG_WHEEL_SLIP_BENCH_CRUISE_MPS"
SETTLE="$CFG_WHEEL_SLIP_BENCH_SETTLE_S"
SAMPLE="$CFG_WHEEL_SLIP_BENCH_SAMPLE_S"
REST="$CFG_WHEEL_SLIP_BENCH_REST_S"
# THE JOINT WHOSE ACHIEVED RATE IS READ, and it is nodes/wheel_odometry.py's
# own key rather than a name of this bench's. There is ONE drive joint on
# this truck, the estimator and the bench have to read the same one, and a
# name spelled here would be a second copy of that answer - the first of
# the two to be fixed would then be the right one, which is exactly what
# _common.sh's own header says a duplicate costs.
DRIVE_JOINT="$CFG_WHEEL_ODOM_DRIVE_JOINT_NAME"
# The wheel rate that asks for the cruise. awk, because the shell has no
# division (m5v3.sh's spawn_truck does the same for its quaternion).
OMEGA="$(awk "BEGIN{printf \"%.6f\", $CRUISE / $RADIUS}")"
STAMP="$(date +%Y%m%d-%H%M%S)"
RUNDIR="${TMPDIR:-/tmp}/m5v3_slip_$STAMP"
mkdir -p "$RUNDIR" || refuse "the run directory is writable" "$0" \
    "could not create $RUNDIR"

# One publish. The JointController holds its last command for ever
# (model.sdf), so this is a standing order and not a stream.
command_wheel() {  # command_wheel <rad/s>
    gz topic -t "$CFG_TOPICS_TRACTION_CMD" -m gz.msgs.Double \
        -p "data: $1" >/dev/null 2>&1 \
        || refuse "the traction terminal accepted a command" \
            "$CFG_TOPICS_TRACTION_CMD" \
            "gz topic -p failed. Is the stack up in partition $GZ_PARTITION" \
            "('m5_ver3/m5v3.sh status')?"
}

# ONE SEGMENT: command, settle, sample both streams for the window, stop
# sampling, and leave the command standing for the caller to clear.
#   stdbuf -oL for the same reason rtf_probe.sh needs it: gz topic -e
#   block-buffers into a file and timeout ends it with SIGTERM, so the
#   last unflushed block would be lost.
segment() {  # segment <name> <rad/s>
    local name="$1" omega="$2"
    echo "  $name: commanding $omega rad/s, settling ${SETTLE}s"
    command_wheel "$omega"
    sleep "$SETTLE"
    echo "  $name: sampling ${SAMPLE}s"
    timeout "$SAMPLE" stdbuf -oL gz topic -e -t "$CFG_TOPICS_ODOM_GROUND_TRUTH" \
        --json-output > "$RUNDIR/$name.odom.json" 2>/dev/null &
    local odom_pid=$!
    timeout "$SAMPLE" stdbuf -oL gz topic -e -t "$CFG_TOPICS_JOINT_STATE" \
        --json-output > "$RUNDIR/$name.joint.json" 2>/dev/null &
    local joint_pid=$!
    wait "$odom_pid" "$joint_pid" 2>/dev/null || true
    command_wheel 0.0
    echo "  $name: stopped, resting ${REST}s"
    sleep "$REST"
}

echo "=== m5v3 slip bench ==="
echo "date       $(date -Is)"
echo "partition  $GZ_PARTITION"
echo "label      ${SLIP_LABEL:-<none given - set SLIP_LABEL to name the row>}"
echo "cruise     $CRUISE m/s at wheel radius $RADIUS m => $OMEGA rad/s"
echo "windows    settle ${SETTLE}s, sample ${SAMPLE}s, rest ${REST}s"
echo "run dir    $RUNDIR"
echo ""

# The plant is left standing before the first segment for the same reason
# the settle window exists: a truck already rolling from somebody else's
# command would put its momentum in the first reading.
command_wheel 0.0
sleep "$REST"

# FORWARD IS NEGATIVE. See the header.
segment forward "-$OMEGA"
segment astern  "$OMEGA"

echo ""
# THE REPORT DECIDES WHETHER THIS RUN HAPPENED. It exits non-zero if
# either segment produced no ground truth - a bench that drove a stack
# which was not there must not print a table and return success.
if ! python3 - "$RUNDIR" "$CRUISE" "$RADIUS" "${SLIP_LABEL:-}" \
        "$DRIVE_JOINT" <<'PYTHON'
import json
import math
import os
import sys

rundir, cruise, radius, label = sys.argv[1], float(sys.argv[2]), float(sys.argv[3]), sys.argv[4]
drive_joint = sys.argv[5]


def stamp(msg):
    """Sim time in seconds. Protobuf omits zero fields, so every read is
    defaulted - a message that arrives on an exact second has no nsec."""
    s = msg.get("header", {}).get("stamp", {})
    return float(s.get("sec", 0)) + float(s.get("nsec", 0)) * 1e-9


def read(path):
    out = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                # A SIGTERM'd writer can leave one truncated last line.
                continue
    return out


def ground_speed(path):
    """Displacement over the window divided by the sim time it took. The
    path is straight, so the chord IS the distance; a curved run would
    need arc length and this bench does not drive one."""
    msgs = read(path)
    if len(msgs) < 2:
        return None
    first, last = msgs[0], msgs[-1]
    p0 = first.get("pose", {}).get("position", {})
    p1 = last.get("pose", {}).get("position", {})
    dx = float(p1.get("x", 0.0)) - float(p0.get("x", 0.0))
    dy = float(p1.get("y", 0.0)) - float(p0.get("y", 0.0))
    dt = stamp(last) - stamp(first)
    if dt <= 0:
        return None
    return {"n": len(msgs), "dist": math.hypot(dx, dy), "dt": dt,
            "speed": math.hypot(dx, dy) / dt}


def joint_rate(path, name):
    """Mean |rate| of the named joint over the same window.

    The name is an ARGUMENT with no default: it arrives through argv from
    config.yaml's wheel_odom.drive_joint_name, so this bench and the
    estimator cannot end up reading different shafts.
    """
    rates = []
    for msg in read(path):
        for joint in msg.get("joint", []):
            if joint.get("name") == name:
                rates.append(abs(float(joint.get("axis1", {}).get("velocity", 0.0))))
    if not rates:
        return None
    return {"n": len(rates), "rate": sum(rates) / len(rates)}


print("label       %s" % (label or "<none>"))
print("commanded   %.4f m/s tread (%.6f rad/s x %.3f m)" % (cruise, cruise / radius, radius))
print("drive joint %s" % drive_joint)
print("")
print("%-8s %8s %9s %9s %13s %11s %12s" %
      ("segment", "samples", "dist_m", "window_s", "ground_mps", "slip_cmd_%", "slip_joint_%"))
rows = []
for name in ("forward", "astern"):
    odom = ground_speed(os.path.join(rundir, "%s.odom.json" % name))
    joint = joint_rate(os.path.join(rundir, "%s.joint.json" % name),
                       drive_joint)
    if odom is None:
        print("%-8s %8s" % (name, "NO DATA - the odometry topic said nothing"))
        continue
    slip_cmd = (cruise - odom["speed"]) / cruise * 100.0
    if joint is None or joint["rate"] <= 0.0:
        slip_joint = float("nan")
    else:
        achieved = joint["rate"] * radius
        slip_joint = (achieved - odom["speed"]) / achieved * 100.0
    rows.append((name, slip_cmd, slip_joint))
    print("%-8s %8d %9.5f %9.4f %13.8f %11.5f %12.5f" %
          (name, odom["n"], odom["dist"], odom["dt"], odom["speed"], slip_cmd, slip_joint))
    if joint is not None:
        print("%-8s %8d joint rate %.8f rad/s => %.8f m/s achieved tread" %
              ("", joint["n"], joint["rate"], joint["rate"] * radius))
if len(rows) != 2:
    raise SystemExit(1)
print("")
print("mean slip_cmd   %.5f %%" % ((rows[0][1] + rows[1][1]) / 2.0))
print("mean slip_joint %.5f %%" % ((rows[0][2] + rows[1][2]) / 2.0))
PYTHON
then
    refuse "both segments produced ground truth" \
        "$CFG_TOPICS_ODOM_GROUND_TRUTH (the captures are in $RUNDIR)" \
        "the odometry topic said nothing for at least one segment." \
        "is the stack up in partition $GZ_PARTITION" \
        "('m5_ver3/m5v3.sh status')?"
fi
