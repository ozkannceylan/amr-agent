#!/usr/bin/env python3
"""forklift_stimulus.py - the stimulus and observation tool for the M4
forklift commissioning scenarios (sim/scenarios/forklift_commissioning.md).

WHAT THIS TOOL IS
  Four small jobs that a commissioning run needs and that no other layer
  owns:

    hold      hold a set of operator controls at the commissioning HMI, by
              re-posting to its own /control endpoint faster than the HMI's
              write cycle. This is how a control is HELD rather than tapped.
    obstacle  move the arena's aisle crate, and put it back, through the
              Gazebo set_pose service. This is the T5.4 stimulus.
    watch     poll the HMI's /state endpoint and print one line per CHANGE,
              so a run leaves a transition transcript rather than a wall of
              samples.
    plant     drive the vehicle's raw command topics directly, by repeated
              publish. A PLANT SMOKE CHECK ONLY - see the warning on it.

WHAT THIS TOOL IS NOT
  It holds no logic. It computes no verdict, applies no threshold, latches
  nothing and decides nothing about the machine. Every decision in these
  scenarios is formed by the PLC standard program (invariants 5, 6, 9), and
  this file only presses what an operator would press and reads back what
  the operator's own screen shows.

  Nothing here is a safety device or a safety stimulus. The obstacle props
  are process furniture; the protective stop, the e-stop chain and safe
  torque off are onboard and hardwired and are reachable from no command in
  this file (invariant 1).

  It imports nothing from hmi/, bridge/, plc/ or agv/. The HMI is driven
  over the same loopback HTTP endpoint the operator's browser posts to, and
  the world is driven over the same gz service the Gazebo GUI uses.

NO --once PUBLISHES ANYWHERE IN THIS FILE. A single publish exits on the
first matching subscriber and races every other one, and one lost start
press cost a day of misread refusals (docs/LESSONS.md, 2026-07-28). Every
stimulus here is either a repeated publish at a stated rate or a service
call that returns a reply.

WHY "hold" EXISTS AT ALL, WHICH IS WORTH READING BEFORE T5.4
  The HMI's reset control is momentary by construction: one click posts one
  request and the backend writes HmiResetRequest TRUE for exactly one write
  cycle. plc/forklift/SPEC.md section 11 step 5.4.4 needs the reset ASSERTED
  AND HELD from 5.4.4 through 5.4.8, spanning the moment the obstacle
  clears, because the property under test is that the edge happened BEFORE
  the cause went away. A browser click cannot produce that hold. Posting the
  same control set at a rate above the HMI's write rate can: every write
  cycle then finds the request standing and the node reads TRUE
  continuously, which is what the program sees and what the step needs.

USAGE (after sourcing /opt/ros/jazzy/setup.bash, which is where gz comes
from, and with both transports isolated as usual)

  export GZ_PARTITION=<run> ROS_DOMAIN_ID=<n>

  python3 sim/scenarios/forklift_stimulus.py hold --teleop --traction 0.6 --seconds 8
  python3 sim/scenarios/forklift_stimulus.py hold --teleop --traction 0.6 --reset --seconds 6
  python3 sim/scenarios/forklift_stimulus.py obstacle --to-x 8.0
  python3 sim/scenarios/forklift_stimulus.py obstacle --home
  python3 sim/scenarios/forklift_stimulus.py watch --seconds 60
  python3 sim/scenarios/forklift_stimulus.py plant --topic traction --value 0.3 --seconds 4
"""

import argparse
import json
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request

# --------------------------------------------------------------------------- #
# Addresses and named values. Every one of them is quoted from a file that
# owns it, and none is a process decision taken here.
# --------------------------------------------------------------------------- #

#: The commissioning HMI's loopback address. hmi/config-logic-double.yaml uses
#: 8090 for the rehearsal stand-in and hmi/config.yaml is the owner's.
DEFAULT_HMI = "http://127.0.0.1:8090"

#: The arena world element, sim/worlds/forklift_arena.sdf.
DEFAULT_WORLD = "forklift_arena"

#: The obstacle prop and its home pose, quoted from that world file. It sits ON
#: the aisle centreline so a vehicle driving straight up the aisle meets it head
#: on; the world file's header derives why an off-centre placement can never
#: trip the zone.
OBSTACLE_MODEL = "AisleCrate"
OBSTACLE_HOME = (2.00, 0.00, 0.45)

#: The HMI scales the normalised joystick X by this before writing
#: HmiSteerRequest, so --steer here is the AXIS, not radians
#: (hmi/hmi_server.py, STEER_REQUEST_MAX_RAD; agv/forklift/config.yaml
#: steer_limit_rad; plc/forklift/SPEC.md section 3.3 STEER_ANGLE_MAX).
STEER_REQUEST_MAX_RAD = 1.31

#: The vehicle layer's raw command topics, from agv/forklift/README.md. Used by
#: the `plant` smoke check only.
PLANT_TOPICS = {
    "traction": ("/forklift/cmd/traction_speed", "std_msgs/msg/Float64"),
    "steer": ("/forklift/cmd/steer_angle", "std_msgs/msg/Float64"),
    "fork": ("/forklift/cmd/fork_speed", "std_msgs/msg/Float64"),
}

#: What `watch` prints a line for. The four PLC verdicts and the three
#: setpoints are the gate's observables; the four plant inputs are what the
#: PLC formed them from. Names are the BrowseNames of
#: docs/interfaces/opcua-nodes.md section 10, which are also the watch-table
#: rows of plc/forklift/SPEC.md section 9.
WATCH_KEYS = (
    "ForkliftTeleopActive", "ForkliftObstacleStopActive",
    "ForkliftSpeedLimitActive", "ForkliftResetRequired", "HmiLinkOk",
    "ForkliftTractionSpeedRef", "ForkliftSteerAngleRef", "ForkliftForkSpeedRef",
    "ForkliftForkHeight", "ForkliftLinearSpeed",
    "ForkliftObstacleInStopZone", "ForkliftObstacleMinDistance",
)

#: Reals are compared with a tolerance so a 20 Hz transcript is not one line
#: per least significant bit. Bools are compared exactly.
REAL_EPSILON = 0.005


# --------------------------------------------------------------------------- #
# The HMI's two endpoints. Nothing of hmi/ is imported: this is the same HTTP
# surface the operator's browser uses.
# --------------------------------------------------------------------------- #

def post_control(base, traction=0.0, steer=0.0, fork=0.0,
                 teleop=False, reset=False, timeout=2.0):
    """One operator control update. Axes are normalised to [-1, 1]."""
    body = json.dumps({
        "traction": traction, "steer": steer, "fork": fork,
        "teleop": bool(teleop), "reset": bool(reset),
    }).encode("utf-8")
    request = urllib.request.Request(
        base.rstrip("/") + "/control", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def get_state(base, timeout=2.0):
    """The operator's own screen, as JSON: what was written this cycle
    (`requests`) and what the PLC answered (`metrics`)."""
    with urllib.request.urlopen(base.rstrip("/") + "/state", timeout=timeout) as response:
        return json.load(response)


def format_state(state):
    """One transcript line: the request beside the setpoint the PLC formed
    from it. That contrast is the gate's whole claim on one line."""
    metrics = state.get("metrics") or {}
    requests = state.get("requests") or {}

    def real(name):
        value = metrics.get(name)
        return float("nan") if value is None else float(value)

    return (
        "req T={:+.2f} S={:+.3f} F={:+.2f} en={} rst={} | "
        "ref T={:+.3f} S={:+.3f} F={:+.3f} | "
        "teleop={} stop={} cap={} resetreq={} link={} | "
        "h={:.3f} v={:+.3f} d={:.3f} zone={}".format(
            float(requests.get("HmiTractionRequest") or 0.0),
            float(requests.get("HmiSteerRequest") or 0.0),
            float(requests.get("HmiForkRequest") or 0.0),
            _bit(requests.get("HmiTeleopRequest")),
            _bit(requests.get("HmiResetRequest")),
            real("ForkliftTractionSpeedRef"), real("ForkliftSteerAngleRef"),
            real("ForkliftForkSpeedRef"),
            _bit(metrics.get("ForkliftTeleopActive")),
            _bit(metrics.get("ForkliftObstacleStopActive")),
            _bit(metrics.get("ForkliftSpeedLimitActive")),
            _bit(metrics.get("ForkliftResetRequired")),
            _bit(metrics.get("HmiLinkOk")),
            real("ForkliftForkHeight"), real("ForkliftLinearSpeed"),
            real("ForkliftObstacleMinDistance"),
            _bit(metrics.get("ForkliftObstacleInStopZone")),
        )
    )


def _bit(value):
    if value is None:
        return "-"
    return "1" if value else "0"


def changed(previous, current):
    """The watched names whose value moved. Reals need a tolerance; bools do
    not, and a bool that flickers is a finding rather than noise."""
    moved = []
    for key in WATCH_KEYS:
        was, now = previous.get(key), current.get(key)
        if isinstance(now, bool) or isinstance(was, bool) or now is None or was is None:
            if was != now:
                moved.append(key)
        elif abs(float(now) - float(was)) > REAL_EPSILON:
            moved.append(key)
    return moved


# --------------------------------------------------------------------------- #
# The world. One gz service call, the same one the Gazebo GUI makes when a
# model is dragged.
# --------------------------------------------------------------------------- #

def set_model_pose(world, model, x, y, z, timeout_ms=3000,
                   env=None, ros_setup=None):
    """Move a model. Returns (ok, stdout, stderr).

    Static models move too: <static> stops the physics engine integrating the
    body, not the pose component being set.

    `gz` reaches this project through the ROS install, and gz transport is
    namespaced by GZ_PARTITION, so a caller that has neither sourced ROS nor
    exported the partition talks to nothing. `ros_setup` sources the former and
    `env` carries the latter; both are optional because a shell that ran the
    bringup already has both."""
    command = [
        "gz", "service", "-s", "/world/{}/set_pose".format(world),
        "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
        "--timeout", str(timeout_ms),
        "--req", 'name: "{}", position: {{x: {}, y: {}, z: {}}}'.format(model, x, y, z),
    ]
    if ros_setup:
        command = ["bash", "-lc", "source {} && {}".format(
            shlex.quote(ros_setup), " ".join(shlex.quote(part) for part in command))]
    finished = subprocess.run(command, capture_output=True, text=True,
                              check=False, env=env)
    ok = finished.returncode == 0 and "true" in finished.stdout.lower()
    return ok, finished.stdout.strip(), finished.stderr.strip()


# --------------------------------------------------------------------------- #
# Subcommands
# --------------------------------------------------------------------------- #

def cmd_hold(args):
    """Hold a control set for a stated duration by re-posting at a rate.

    The rate must exceed the HMI's write rate for a request to read as HELD on
    the server; the default 20 Hz is twice the HMI's nominal 10 Hz cycle."""
    deadline = time.monotonic() + args.seconds
    period = 1.0 / args.rate
    posts = 0
    print("hold: traction={:+.2f} steer-axis={:+.2f} (={:+.3f} rad) fork={:+.2f} "
          "enable={} reset={} for {:.1f} s at {:.0f} Hz".format(
              args.traction, args.steer, args.steer * STEER_REQUEST_MAX_RAD,
              args.fork, args.teleop, args.reset, args.seconds, args.rate))
    while time.monotonic() < deadline:
        post_control(args.hmi, traction=args.traction, steer=args.steer,
                     fork=args.fork, teleop=args.teleop, reset=args.reset)
        posts += 1
        time.sleep(period)
    print("hold: {} posts".format(posts))
    if args.read_back:
        print("hold: " + format_state(get_state(args.hmi)))
    return 0


def cmd_obstacle(args):
    """Move the aisle crate, or put it back where the world file has it."""
    if args.home:
        x, y, z = OBSTACLE_HOME
    else:
        x = OBSTACLE_HOME[0] if args.to_x is None else args.to_x
        y = OBSTACLE_HOME[1] if args.to_y is None else args.to_y
        z = OBSTACLE_HOME[2] if args.to_z is None else args.to_z
    ok, out, err = set_model_pose(args.world, args.model, x, y, z)
    print("obstacle: {} -> ({}, {}, {}): {}".format(
        args.model, x, y, z, "ok" if ok else "FAILED"))
    if out:
        print("obstacle: reply " + out.replace("\n", " "))
    if err:
        print("obstacle: stderr " + err.replace("\n", " "))
    return 0 if ok else 1


def cmd_watch(args):
    """Poll /state and print one line per change, plus a periodic keepalive
    line so a quiet stretch is visibly quiet rather than merely absent."""
    started = time.monotonic()
    deadline = started + args.seconds
    period = 1.0 / args.rate
    previous, last_periodic = {}, 0.0
    handle = open(args.csv, "w", encoding="utf-8") if args.csv else None
    if handle:
        handle.write("monotonic_s," + ",".join(WATCH_KEYS) + "\n")
    try:
        while time.monotonic() < deadline:
            now = time.monotonic()
            try:
                state = get_state(args.hmi)
            except (urllib.error.URLError, OSError, TimeoutError) as exc:
                print("{:8.3f}  HMI /state unreachable: {}".format(now - started, exc))
                time.sleep(period)
                continue
            metrics = dict(state.get("metrics") or {})
            moved = changed(previous, metrics)
            if moved or (now - last_periodic) >= args.periodic:
                marker = ",".join(moved) if moved else "."
                print("{:8.3f}  {}   [{}]".format(
                    now - started, format_state(state), marker))
                sys.stdout.flush()
                last_periodic = now
            if handle:
                handle.write("{:.4f},".format(now) + ",".join(
                    "" if metrics.get(k) is None else str(metrics.get(k))
                    for k in WATCH_KEYS) + "\n")
            previous = metrics
            time.sleep(period)
    finally:
        if handle:
            handle.close()
    return 0


def cmd_plant(args):
    """PLANT SMOKE CHECK. Publishes onto the vehicle's raw command topic at a
    rate, so the plant can be shown alive before anything is blamed on the PLC.

    THIS BYPASSES THE PLC AND IS NEVER GATE EVIDENCE. The M4 criterion is that
    every command passes HMI -> PLC standard program -> bridge -> simulation;
    a value published here has passed through none of it. Use it to answer
    "is the machine alive" and nothing else, and never while a scenario is
    being recorded: the bridge is publishing on the same topic and the two
    publishers would interleave.
    """
    topic, kind = PLANT_TOPICS[args.topic]
    command = ["ros2", "topic", "pub", "-r", str(args.rate), topic, kind,
               "{{data: {}}}".format(args.value)]
    print("plant: PLC BYPASSED - not gate evidence. {} at {} Hz for {:.1f} s".format(
        " ".join(command), args.rate, args.seconds))
    sys.stdout.flush()   # the warning belongs above the publisher's own output
    process = subprocess.Popen(command)
    try:
        deadline = time.monotonic() + args.seconds
        while time.monotonic() < deadline and process.poll() is None:
            time.sleep(0.1)
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
    print("plant: stopped (pid {} finished by this process)".format(process.pid))
    return 0


def build_parser():
    parser = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--hmi", default=DEFAULT_HMI,
                        help="commissioning HMI base URL (default: %(default)s)")
    sub = parser.add_subparsers(dest="command", required=True)

    hold = sub.add_parser("hold", help="hold a control set at the HMI")
    hold.add_argument("--traction", type=float, default=0.0,
                      help="traction fraction, -1..1")
    hold.add_argument("--steer", type=float, default=0.0,
                      help="steer AXIS, -1..1; the HMI scales it by "
                           "{} rad".format(STEER_REQUEST_MAX_RAD))
    hold.add_argument("--fork", type=float, default=0.0,
                      help="fork jog fraction, -1..1")
    hold.add_argument("--teleop", action="store_true", help="hold the enable")
    hold.add_argument("--reset", action="store_true", help="hold the reset")
    hold.add_argument("--seconds", type=float, default=3.0)
    hold.add_argument("--rate", type=float, default=20.0,
                      help="posts per second; must exceed the HMI write rate "
                           "for a request to read as held (default: %(default)s)")
    hold.add_argument("--read-back", action="store_true",
                      help="print one /state line when the hold ends")
    hold.set_defaults(func=cmd_hold)

    obstacle = sub.add_parser("obstacle", help="move the arena's aisle crate")
    obstacle.add_argument("--world", default=DEFAULT_WORLD)
    obstacle.add_argument("--model", default=OBSTACLE_MODEL)
    obstacle.add_argument("--to-x", type=float, default=None)
    obstacle.add_argument("--to-y", type=float, default=None)
    obstacle.add_argument("--to-z", type=float, default=None)
    obstacle.add_argument("--home", action="store_true",
                          help="put it back at {}".format(OBSTACLE_HOME))
    obstacle.set_defaults(func=cmd_obstacle)

    watch = sub.add_parser("watch", help="transition transcript from /state")
    watch.add_argument("--seconds", type=float, default=60.0)
    watch.add_argument("--rate", type=float, default=20.0)
    watch.add_argument("--periodic", type=float, default=5.0,
                       help="seconds between keepalive lines (default: %(default)s)")
    watch.add_argument("--csv", default=None, help="also write every sample here")
    watch.set_defaults(func=cmd_watch)

    plant = sub.add_parser(
        "plant", help="PLANT SMOKE CHECK - publishes past the PLC, never evidence")
    plant.add_argument("--topic", choices=sorted(PLANT_TOPICS), required=True)
    plant.add_argument("--value", type=float, required=True)
    plant.add_argument("--rate", type=float, default=5.0)
    plant.add_argument("--seconds", type=float, default=3.0)
    plant.set_defaults(func=cmd_plant)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
