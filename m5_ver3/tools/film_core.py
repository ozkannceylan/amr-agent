#!/usr/bin/env python3
"""film_core.py - the arithmetic behind the F5 film, and nothing else.

    python3 m5_ver3/tools/film_core.py --selftest

The four things the film needs computed rather than guessed, and none
of them touches ROS, gz or ffmpeg - film_run.py owns the processes,
this owns the numbers:

  follow_step      the smoothed camera step film_follow.py takes
  pose_request     a world pose as a gz service request body
  parse_pose       config's `x y z r p y` string as a pose dict
  plan_segments    a recorded timeline against the shot table -> cut
  ffmpeg_argv      that plan as one ffmpeg command

The values those functions move come from config.yaml (film:) and
nowhere here; a number that lives in two places is two numbers.
"""
import argparse
import math
import os


HERE = os.path.dirname(os.path.abspath(__file__))

# The follow camera looks straight down: SDF pose pitch pi/2, the same
# convention film_overhead.sdf measured. The quaternion for pitch alone
# is a rotation about +y - (0, sin(pi/4), 0, cos(pi/4)) - one number,
# derived not typed.
_PITCH_DOWN = math.pi / 2.0
_Q_DOWN = (0.0, math.sin(_PITCH_DOWN / 2.0), 0.0, math.cos(_PITCH_DOWN / 2.0))


def follow_step(cam_x, cam_y, truck_x, truck_y, alpha):
    """One smoothing step toward the truck. Returns (cam_x, cam_y).

    cam' = cam + alpha * (truck - cam). alpha is config's
    film.follow_smooth - 0.35 spreads a 0.5 s pose step across about
    four frames of 15 Hz footage.
    """
    if not 0.0 < alpha <= 1.0:
        raise ValueError("alpha must be in (0, 1], got {!r}".format(alpha))
    return (cam_x + alpha * (truck_x - cam_x),
            cam_y + alpha * (truck_y - cam_y))


def pose_request(name, x, y, z, quaternion):
    """A gz.msgs.Pose service request body from a pose and a quaternion."""
    qx, qy, qz, qw = quaternion
    return (
        'name: "{n}", position: {{x: {x:.9f}, y: {y:.9f}, '
        'z: {z:.9f}}}, orientation: {{x: {qx:.9f}, y: {qy:.9f}, '
        'z: {qz:.9f}, w: {qw:.9f}}}'
    ).format(n=name, x=x, y=y, z=z, qx=qx, qy=qy, qz=qz, qw=qw)


def parse_pose(text):
    """config's `x y z roll pitch yaw` string as a pose dict.

    Returns {"x", "y", "z", "qx", "qy", "qz", "qw"}. The quaternion is
    the RPY product in the same order SDF composes it.
    """
    parts = str(text).replace(",", " ").split()
    if len(parts) != 6:
        raise ValueError(
            "pose must be `x y z roll pitch yaw`, got {!r}".format(text))
    x, y, z, roll, pitch, yaw = (float(p) for p in parts)
    cr, sr = math.cos(roll / 2.0), math.sin(roll / 2.0)
    cp, sp = math.cos(pitch / 2.0), math.sin(pitch / 2.0)
    cy, sy = math.cos(yaw / 2.0), math.sin(yaw / 2.0)
    # R = Rz(yaw) * Ry(pitch) * Rx(roll) - the SDF composition.
    return {
        "x": x, "y": y, "z": z,
        "qx": sr * cp * cy - cr * sp * sy,
        "qy": cr * sp * cy + sr * cp * sy,
        "qz": cr * cp * sy - sr * sp * cy,
        "qw": cr * cp * cy + sr * sp * sy,
    }


def create_request(sdf_path, name, pose):
    """A gz.msgs.EntityFactory request body that spawns a model AT a pose.

    The same shape furniture.create_request uses for the marker: the
    pose rides in the request, so the SDF is not a second home for it.
    """
    path = str(sdf_path).replace("\\", "/")
    return (
        'sdf_filename: "{sdf}", name: "{n}", allow_renaming: false, '
        'pose: {{position: {{x: {x}, y: {y}, z: {z}}}, '
        'orientation: {{x: {qx}, y: {qy}, z: {qz}, w: {qw}}}}}'
    ).format(sdf=path, n=name, x=pose["x"], y=pose["y"], z=pose["z"],
             qx=pose["qx"], qy=pose["qy"], qz=pose["qz"], qw=pose["qw"])


def shot_table(config_shots):
    """config's film.shots list as [(leg, cam, pip)] triples."""
    table = []
    for row in config_shots:
        pip = str(row.get("pip", "false")).strip().lower() == "true"
        table.append((str(row["leg"]), str(row["cam"]), pip))
    return table


def plan_segments(timeline, table, lead_s, tail_s):
    """A recorded timeline against the shot table, as a cut plan.

    timeline is film_run.py record's parsed JSON: {"legs": [{"leg": s,
    "t": wall_s}...], "cycle_start": wall_s, "cycle_end": wall_s,
    "outcome": "done"}. Times are wall-clock seconds, and every time
    the plan returns is a WALL time too - converting into each camera's
    own recording clock is ffmpeg_argv's job, because the four
    recorders start at four different wall times.

    Returns {"lead": [start, end], "segments": [ {leg, cam, start, end,
    pip} ...], "pip_windows": [[start, end]...], "duration"} - where
    lead is the establishing shot on the wide camera before the cycle's
    first leg. The last segment HOLDS tail_s past the cycle's done -
    the film does not end on a mid-motion cut. Raises ValueError naming
    the mismatch when the observed legs are not the table's legs in
    order, and when the cycle did not finish.
    """
    legs = timeline["legs"]
    names = [leg["leg"] for leg in legs]
    want = [row[0] for row in table]
    if names != want:
        raise ValueError(
            "the filmed legs are not the shot table's legs\n"
            "  filmed: {}\n  table:  {}".format(
                " ".join(names), " ".join(want)))
    if timeline.get("outcome") != "done":
        raise ValueError(
            "the filmed cycle did not finish; outcome={!r}".format(
                timeline.get("outcome")))

    start = timeline["cycle_start"]
    end = timeline["cycle_end"]
    plan = {"lead": [start - lead_s, start],
            "segments": [], "pip_windows": []}
    bounds = [leg["t"] for leg in legs] + [end]
    for i, (leg_name, cam, pip) in enumerate(table):
        seg_start = bounds[i]
        seg_end = bounds[i + 1]
        if i == len(table) - 1:
            seg_end += tail_s
        plan["segments"].append(
            {"leg": leg_name, "cam": cam,
             "start": seg_start, "end": seg_end, "pip": pip})
        if pip:
            plan["pip_windows"].append([seg_start, seg_end])
    plan["duration"] = plan["segments"][-1]["end"] - plan["lead"][0]
    return plan


def ffmpeg_argv(plan, sources, offsets, out_path, fps, pip_scale,
                pip_margin_px):
    """The cut as one ffmpeg argv.

    sources: {cam: mp4 path or None} - a None entry is a camera whose
    recording is missing. offsets: {cam: wall seconds of that
    recording's FIRST FRAME} - every camera starts at a different wall
    time, so a wall-clock segment bound becomes a source-clock trim by
    subtracting the camera's own first-frame time. The lead segment
    comes from `wide`; the follow and dock cameras are the film and a
    segment that names one without a recording raises. The vehicle
    camera is the PiP and is simply absent from the overlay when its
    file is missing.
    """
    inputs = []
    labels = {}
    index = 0
    for cam in ("wide", "follow", "dock", "vehicle"):
        path = sources.get(cam)
        if not path:
            continue
        inputs.extend(["-i", path])
        labels[cam] = index
        index += 1

    parts = []

    def _trim(cam, wall_start, wall_end):
        """One [vN] sliced to [sK], in that source's own clock."""
        off = offsets.get(cam, 0.0)
        label = "s{}".format(len(parts))
        parts.append(
            "[{i}:v]trim={start:.3f}:{end:.3f},setpts=PTS-STARTPTS[{l}]"
            .format(i=labels[cam], start=wall_start - off,
                    end=wall_end - off, l=label))
        return label

    lead = None
    if "wide" in labels and plan["lead"][1] > plan["lead"][0]:
        lead = _trim("wide", plan["lead"][0], plan["lead"][1])

    seg_labels = []
    for seg in plan["segments"]:
        cam = seg["cam"]
        if cam not in labels:
            raise ValueError(
                "segment camera {!r} has no recording".format(cam))
        seg_labels.append(_trim(cam, seg["start"], seg["end"]))

    chain = ([lead] if lead else []) + seg_labels
    parts.append("{}concat=n={}:v=1:a=0[main]".format(
        "".join("[{}]".format(l) for l in chain), len(chain)))

    if plan["pip_windows"] and "vehicle" in labels:
        vi = labels["vehicle"]
        parts.append(
            "[{i}:v]scale=w=iw*{sc}:h=ih*{sc}[pip]".format(i=vi, sc=pip_scale))
        # The overlay's `t` runs on the CONCATENATED main timeline; the
        # windows are wall times, so shift by the same film origin the
        # main chain was cut on: the first lead frame is film t=0.
        film_t0 = plan["lead"][0]
        windows = "+".join(
            "between(t,{:.3f},{:.3f})".format(a - film_t0, b - film_t0)
            for a, b in plan["pip_windows"])
        parts.append(
            "[main][pip]overlay=x=W-w-{mx}:y=H-h-{my}:enable='{en}'[out]"
            .format(mx=pip_margin_px, my=pip_margin_px, en=windows))
        final = "[out]"
    else:
        final = "[main]"

    argv = ["ffmpeg", "-y"]
    argv.extend(inputs)
    argv.extend(["-filter_complex", ";".join(parts)])
    argv.extend(["-map", final, "-c:v", "libx264", "-pix_fmt", "yuv420p",
                 "-r", str(fps), str(out_path)])
    return argv


def _selftest():
    failures = []

    def check(name, got, want):
        if got != want:
            failures.append("{}: got {!r} want {!r}".format(name, got, want))

    # follow_step converges and never overshoots
    cx, cy = follow_step(0.0, 0.0, 10.0, -4.0, 0.5)
    check("follow half step", (cx, cy), (5.0, -2.0))
    cx, cy = follow_step(5.0, -2.0, 10.0, -4.0, 0.5)
    check("follow second step", (cx, cy), (7.5, -3.0))
    try:
        follow_step(0, 0, 1, 1, 1.5)
        failures.append("follow_step: alpha 1.5 was accepted")
    except ValueError:
        pass

    # parse_pose: identity, and pure pitch pi/2 matching the follow cam
    p = parse_pose("12.5 3.0 9.0 0 -0.979 3.141")
    check("parse x", p["x"], 12.5)
    norm = p["qx"] ** 2 + p["qy"] ** 2 + p["qz"] ** 2 + p["qw"] ** 2
    check("parse quaternion normal", round(norm, 9), 1.0)
    down = parse_pose("0 0 7 0 1.5708 0")
    check("pitch-down quaternion", tuple(
        round(down[k], 4) for k in ("qx", "qy", "qz", "qw")),
        tuple(round(v, 4) for v in _Q_DOWN))
    try:
        parse_pose("1 2 3")
        failures.append("parse_pose: 3 fields were accepted")
    except ValueError:
        pass

    # pose_request: the follow body, with the pitch-down quaternion
    req = pose_request("film_follow", 1.5, -2.25, 7.0, _Q_DOWN)
    for needle in ('name: "film_follow"', "x: 1.500000000", "y: -2.250000000",
                   "z: 7.000000000", "y: 0.707106781", "w: 0.707106781"):
        if needle not in req:
            failures.append("pose_request lost {!r}".format(needle))

    # create_request carries the pose and the SDF path
    req = create_request("m5_ver3/gazebo/film_dock.sdf", "film_dock", p)
    for needle in ('sdf_filename: "m5_ver3/gazebo/film_dock.sdf"',
                   'name: "film_dock"', "x: 12.5", "y: 3.0", "z: 9.0"):
        if needle not in req:
            failures.append("create_request lost {!r}".format(needle))

    # plan_segments: a two-leg table, all times wall
    table = [("transit", "follow", False), ("dock", "dock", True)]
    timeline = {"cycle_start": 100.0, "cycle_end": 200.0,
                "outcome": "done",
                "legs": [{"leg": "transit", "t": 100.0},
                         {"leg": "dock", "t": 160.0}]}
    plan = plan_segments(timeline, table, lead_s=4.0, tail_s=4.0)
    check("lead", plan["lead"], [96.0, 100.0])
    check("seg0", (plan["segments"][0]["cam"], plan["segments"][0]["start"],
                   plan["segments"][0]["end"]), ("follow", 100.0, 160.0))
    check("seg1", (plan["segments"][1]["cam"], plan["segments"][1]["start"],
                   plan["segments"][1]["end"]), ("dock", 160.0, 204.0))
    check("pip window", plan["pip_windows"], [[160.0, 204.0]])
    check("duration", plan["duration"], 108.0)
    # a mismatched table is a named refusal
    try:
        plan_segments(timeline, [("dock", "dock", True)], 4.0, 4.0)
        failures.append("plan_segments: a wrong leg order was accepted")
    except ValueError as exc:
        if "shot table" not in str(exc):
            failures.append("plan_segments: refusal names the table? {!r}"
                            .format(str(exc)))
    # a failed cycle is a named refusal
    bad = dict(timeline)
    bad["outcome"] = "stopped"
    try:
        plan_segments(bad, table, 4.0, 4.0)
        failures.append("plan_segments: outcome=stopped was accepted")
    except ValueError as exc:
        if "outcome" not in str(exc):
            failures.append("plan_segments: refusal names the outcome? {!r}"
                            .format(str(exc)))

    # ffmpeg_argv: four sources, vehicle PiP, offsets honoured
    sources = {"follow": "f.mp4", "dock": "d.mp4", "wide": "w.mp4",
               "vehicle": "v.mp4"}
    offsets = {"follow": 90.0, "dock": 92.0, "wide": 90.0, "vehicle": 91.0}
    argv = ffmpeg_argv(plan, sources, offsets, "out.mp4", 15, 0.25, 24)
    check("argv is ffmpeg -y", argv[:2], ["ffmpeg", "-y"])
    check("argv input count", argv.count("-i"), 4)
    graph = argv[argv.index("-filter_complex") + 1]
    # lead on wide, source clock = wall - offset: 96-90 .. 100-90
    check("lead trim uses the wide offset",
          "trim=6.000:10.000" in graph, True)
    # first follow segment: 100-90 .. 160-90
    check("seg0 trim uses the follow offset",
          "trim=10.000:70.000" in graph, True)
    # dock segment: 160-92 .. 204-92
    check("seg1 trim uses the dock offset",
          "trim=68.000:112.000" in graph, True)
    check("argv has concat",
          "concat=n=3:v=1:a=0[main]" in graph, True)
    # pip window in film time: 160-96 .. 204-96
    check("pip window is film time",
          "between(t,64.000,108.000)" in graph, True)
    check("argv maps the overlay", "[out]" in argv, True)
    check("argv ends at the output", argv[-1], "out.mp4")
    # a missing main camera is refused
    try:
        ffmpeg_argv(plan, {"wide": "w.mp4", "vehicle": "v.mp4"},
                     {}, "out.mp4", 15, 0.25, 24)
        failures.append("ffmpeg_argv: a segment without its camera was built")
    except ValueError:
        pass

    if failures:
        print("SELFTEST FAIL")
        for line in failures:
            print("  " + line)
        return 1
    print("selftest film_core ok")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="film_core.py")
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args(argv)
    if args.selftest:
        return _selftest()
    parser.error("nothing to do: this module is arithmetic, "
                 "film_run.py is the tool")


if __name__ == "__main__":
    raise SystemExit(main())