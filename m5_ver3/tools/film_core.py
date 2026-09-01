#!/usr/bin/env python3
"""film_core.py - the arithmetic behind the F5 film, and nothing else.

    python3 m5_ver3/tools/film_core.py --selftest

The things the film needs computed rather than guessed, and none of
them touches ROS, gz or ffmpeg - film_run.py owns the processes, this
owns the numbers:

  follow_step      the smoothed camera step film_follow.py takes
  pose_request     a world pose as a gz service request body
  parse_pose       config's `x y z r p y` string as a pose dict
  bare_leg         a cycle's `c<n>-<leg>` stdout tag as a bare leg
  clock            one recording's own wall -> video mapping
  read_clock       that mapping, from the sidecars beside an mp4
  video_time       a wall second as a second of one recording
  plan_segments    a recorded timeline against the shot table -> cut
  lead_span        the establishing footage that cut will actually hold
  film_length      the video seconds that cut will actually hold
  ffmpeg_argv      that plan as one ffmpeg command

THE FILM IS STAMPED ON THE WALL CLOCK AND SHOT ON THE SIM CLOCK, and
`clock` is the one place those two meet. Everything upstream of it -
the timeline, the plan, the lead and the tail - is wall seconds;
everything downstream - trims, PiP enable windows - is that
recording's own seconds.

The values those functions move come from config.yaml (film:) and
nowhere here; a number that lives in two places is two numbers.
"""
import argparse
import math
import os
import re


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


# pallet_cycle.py prints `leg c1-transit`: the leg carries the cycle
# number, the shot table and the plan hold the bare name. ANCHORED and
# digits-only on purpose - the cycle's stdout is also the stdout of
# every tool it runs, and drive_goal.py prints `leg 1 ...` down that
# same pipe.
_CYCLE_LEG = re.compile(r"^c\d+-(\S+)$")


def bare_leg(tag):
    """A cycle's `c<n>-<leg>` tag as the bare leg name, or None.

    None means the token is not a cycle leg tag at all, which is the
    only way film_run.py can tell the cycle's own legs from the `leg`
    lines its children print into the same stdout.
    """
    match = _CYCLE_LEG.match(str(tag))
    return match.group(1) if match else None


# The three one-number files film_record.py leaves beside every mp4,
# in the order clock() reads them: first-frame wall time, last-frame
# wall time, frame count.
SIDECARS = (".t0", ".t1", ".n")


def clock(t0, t1, n, fps):
    """One recording's own wall-to-video mapping, measured from itself.

    film_record.py writes every message it receives into a container
    FIXED at `fps`, and the film cameras publish on the SIM clock. So n
    frames are n/fps of video however long the wall took: first and
    last frame are (n - 1)/fps apart in the file and t1 - t0 apart on
    the wall, and that ratio is this recording's sim-per-wall rate.

    Returns {"t0", "t1", "n", "fps", "rate", "length_s"}. length_s is
    n/fps - the footage that EXISTS, which is the bound a trim may not
    run past. A rig keeping up with the wall gives rate 1.0 and
    video_time collapses to `wall - t0`.

    Raises ValueError naming what cannot be measured: a recording whose
    rate is unknowable is one no trim can be honest about.
    """
    n = int(n)
    fps = float(fps)
    if fps <= 0.0:
        raise ValueError("fps must be positive, got {!r}".format(fps))
    if n < 2:
        raise ValueError(
            "a recording of {} frame(s) spans no video: the rate is "
            "measured between the FIRST and the LAST frame".format(n))
    if t1 <= t0:
        raise ValueError(
            "the last frame is not after the first: t0={!r} t1={!r}"
            .format(t0, t1))
    return {"t0": float(t0), "t1": float(t1), "n": n, "fps": fps,
            "rate": ((n - 1) / fps) / (float(t1) - float(t0)),
            "length_s": n / fps}


def video_time(clk, wall_t):
    """A wall second as a second of that recording's own footage."""
    return (wall_t - clk["t0"]) * clk["rate"]


def read_clock(path, fps):
    """clock() from the three sidecars film_record.py leaves by an mp4.

    Raises ValueError naming the sidecar when one is absent or is not a
    number. Assuming rate 1.0 for a recording that has no t1 and no n
    is exactly the guess this mapping exists to remove, and a session
    recorded before the recorder wrote them cannot be cut honestly.
    """
    values = {}
    for suffix in SIDECARS:
        side = str(path) + suffix
        if not os.path.isfile(side):
            raise ValueError(
                "the recording {} has no {} sidecar\n"
                "  looked for: {}\n"
                "  film_record.py writes t0, t1 and n; without all "
                "three this file's sim clock is unmeasured and every "
                "trim into it would be a guess".format(
                    os.path.basename(str(path)), suffix, side))
        with open(side, encoding="utf-8") as handle:
            text = handle.read().strip()
        try:
            values[suffix] = float(text)
        except ValueError:
            raise ValueError(
                "the sidecar {} reads {!r}, not a number".format(
                    side, text))
    return clock(values[".t0"], values[".t1"], values[".n"], fps)


def plan_segments(timeline, table, lead_s, tail_s, lead_floor=None):
    """A recorded timeline against the shot table, as a cut plan.

    timeline is film_run.py record's parsed JSON: {"legs": [{"leg": s,
    "t": wall_s}...], "cycle_start": wall_s, "cycle_end": wall_s,
    "outcome": "done"}. Times are wall-clock seconds, and every time
    the plan returns is a WALL time too - converting into each camera's
    own recording clock is ffmpeg_argv's job, because the four
    recorders start at four different wall times AND run on the sim
    clock rather than this one.

    Returns {"lead": [start, end], "segments": [ {leg, cam, start, end,
    pip} ...], "pip_windows": [[start, end]...], "duration"} - where
    lead is the establishing shot on the wide camera before the cycle's
    first leg. The last segment HOLDS tail_s past the cycle's done -
    the film does not end on a mid-motion cut. Raises ValueError naming
    the mismatch when the observed legs are not the table's legs in
    order, and when the cycle did not finish.

    lead_floor is the earliest wall second the wide recording holds -
    its own first frame - and THE LEAD IS PLANNED FROM WHAT EXISTS: a
    pre-roll shorter than lead_s gives a shorter lead, never a trim
    from before the file begins. A short lead is a degraded shot, so
    the plan carries it and every printed number counts it; asking for
    footage nobody recorded is the lie, and ffmpeg_argv refuses that
    for the cycle's own segments. lead_floor None plans the full lead
    and is what a caller with no wide recording passes - there is no
    lead to cut at all then.
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
    lead_start = start - lead_s
    if lead_floor is not None:
        # min(..., start): a wide recorder that only began AFTER the
        # cycle did leads with nothing, and an empty lead is the one
        # thing both film_length and ffmpeg_argv already skip.
        lead_start = min(max(lead_start, float(lead_floor)), start)
    plan = {"lead": [lead_start, start],
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


def lead_span(plan, sources, clocks):
    """The VIDEO seconds of establishing footage the cut will hold.

    The lead the PLAN carries, on the wide recording's own clock -
    which is the lead the film opens with, and is shorter than
    film.lead_s whenever the wide recorder's first frame landed inside
    that window. Zero when `wide` was not recorded and zero when the
    plan's lead is empty: the same inclusion rule ffmpeg_argv follows,
    so the two never disagree about what is in the film.
    """
    if not sources.get("wide") or plan["lead"][1] <= plan["lead"][0]:
        return 0.0
    clk = clocks["wide"]
    return (video_time(clk, plan["lead"][1])
            - video_time(clk, plan["lead"][0]))


def film_length(plan, sources, clocks):
    """The VIDEO seconds the cut will hold, not the wall seconds it spans.

    plan["duration"] is wall: what the cycle took. What the file gets
    is each bound mapped into its own recording's clock, so on a rig
    running at 0.75 x wall a 350 s cycle is a 262 s film. The lead is
    counted as DELIVERED - lead_span, not film.lead_s - so this number
    is the encode's length and not a claim about it.
    """
    total = lead_span(plan, sources, clocks)
    for seg in plan["segments"]:
        clk = clocks[seg["cam"]]
        total += video_time(clk, seg["end"]) - video_time(clk, seg["start"])
    return total


def ffmpeg_argv(plan, sources, clocks, out_path, fps, pip_scale,
                pip_margin_px, eof_tolerance_s):
    """The cut as one ffmpeg argv.

    sources: {cam: mp4 path or None} - a None entry is a camera whose
    recording is missing. clocks: {cam: clock()} - each recording's own
    wall-to-video mapping, because the four recorders start at four
    different wall times AND the footage runs on the sim clock, so a
    wall-clock segment bound becomes a source-clock trim through that
    camera's own affine map rather than by subtraction alone. The lead
    segment comes from `wide`; the follow and dock cameras are the film
    and a segment that names one without a recording raises. The
    vehicle camera is the PiP and is simply absent from the overlay
    when its file is missing.

    A trim whose end runs more than eof_tolerance_s past the footage
    that exists RAISES, naming the segment, the bound and the length:
    ffmpeg clamps such a trim at end-of-file without a word, and a leg
    clamped away is a leg the film claims to hold and does not. The
    PiP is cut to its last window for the same reason from the other
    end: the film is exactly as long as film_length says. A trim
    that STARTS more than eof_tolerance_s before the recording's first
    frame raises for the same reason and by the same tolerance -
    ffmpeg clamps that one at 0 just as quietly, and every segment
    after it then sits that far from the printed plan. The lead does
    not come through here: plan_segments plans it from the footage the
    wide recording holds.
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

    def _trim(cam, wall_start, wall_end, what):
        """One [vN] sliced to [sK], in that source's own clock.

        Returns (label, the video seconds the slice lasts) - the film's
        own timeline is the running sum of those.
        """
        clk = clocks[cam]
        start = video_time(clk, wall_start)
        end = video_time(clk, wall_end)
        if start < -eof_tolerance_s:
            raise ValueError(
                "the cut asks for footage from before the recording "
                "began\n"
                "  segment:  {what}\n"
                "  needs to: start {start:.3f} s into {cam}\n"
                "  it holds: from 0.000 s, its first frame at wall "
                "{t0:.3f}\n"
                "  short by: {under:.3f} s, before a tolerance of "
                "{tol:.3f} s".format(
                    what=what, start=start, cam=cam, t0=clk["t0"],
                    under=-start, tol=eof_tolerance_s))
        if end > clk["length_s"] + eof_tolerance_s:
            raise ValueError(
                "the cut asks for footage the recording does not hold\n"
                "  segment:  {what}\n"
                "  needs to: {end:.3f} s of {cam}\n"
                "  it holds: {length:.3f} s ({n} frames at {fps:g} fps, "
                "sim {rate:.3f} x wall)\n"
                "  over by:  {over:.3f} s, past a tolerance of "
                "{tol:.3f} s".format(
                    what=what, end=end, cam=cam, length=clk["length_s"],
                    n=clk["n"], fps=clk["fps"], rate=clk["rate"],
                    over=end - clk["length_s"], tol=eof_tolerance_s))
        label = "s{}".format(len(parts))
        parts.append(
            "[{i}:v]trim={start:.3f}:{end:.3f},setpts=PTS-STARTPTS[{l}]"
            .format(i=labels[cam], start=start, end=end, l=label))
        return label, end - start

    lead = None
    film_len = 0.0
    if "wide" in labels and plan["lead"][1] > plan["lead"][0]:
        lead, span = _trim("wide", plan["lead"][0], plan["lead"][1],
                           "the wide lead")
        film_len += span

    seg_labels = []
    pip_windows = []
    for seg in plan["segments"]:
        cam = seg["cam"]
        if cam not in labels:
            raise ValueError(
                "segment camera {!r} has no recording".format(cam))
        label, span = _trim(cam, seg["start"], seg["end"],
                            "{} on {}".format(seg["leg"], cam))
        seg_labels.append(label)
        # The overlay's `t` runs on the CONCATENATED main timeline, so
        # a PiP window is where its segment LANDS there: the running
        # sum of the video spans already cut. plan["pip_windows"] says
        # the same thing in WALL seconds, which the concat does not
        # speak - at rate 1.0 with contiguous segments the two are the
        # same number, and off it they are not.
        if seg["pip"]:
            pip_windows.append([film_len, film_len + span])
        film_len += span

    chain = ([lead] if lead else []) + seg_labels
    parts.append("{}concat=n={}:v=1:a=0[main]".format(
        "".join("[{}]".format(l) for l in chain), len(chain)))

    if pip_windows and "vehicle" in labels:
        vi = labels["vehicle"]
        # The inset is enabled only inside its windows, so its stream
        # ENDS with the last of them. Untrimmed it is the whole vehicle
        # recording, and overlay's framesync runs until every input is
        # done: an inset outlasting the film holds the film's last
        # frame frozen on screen for the difference, and the encode is
        # then longer than any plan that printed it - 17 frozen frames
        # past a 331.1 s film on the 2026-09-01 take.
        parts.append(
            "[{i}:v]trim=0:{end:.3f},setpts=PTS-STARTPTS,"
            "scale=w=iw*{sc}:h=ih*{sc}[pip]".format(
                i=vi, end=pip_windows[-1][1], sc=pip_scale))
        windows = "+".join(
            "between(t,{:.3f},{:.3f})".format(a, b) for a, b in pip_windows)
        parts.append(
            "[main][pip]overlay=x=W-w-{mx}:y=H-h-{my}:enable=\'{en}\'[out]"
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

    # bare_leg: the cycle's tag in, the table's leg name out - and
    # None for the `leg 1 ...` a child of the cycle prints
    check("bare leg c1", bare_leg("c1-transit"), "transit")
    check("bare leg c12", bare_leg("c12-lower"), "lower")
    for token in ("1", "transit", "cx-transit", "c1-", ""):
        check("bare leg rejects {!r}".format(token), bare_leg(token), None)

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

    # the lead is planned from what the wide recording holds: a floor
    # inside the lead window shortens the shot, one before it changes
    # nothing, one past the cycle's start leaves no lead at all
    short_lead = plan_segments(timeline, table, lead_s=4.0, tail_s=4.0,
                               lead_floor=98.7)
    check("short lead", short_lead["lead"], [98.7, 100.0])
    check("full lead", plan_segments(timeline, table, 4.0, 4.0,
                                     lead_floor=92.0)["lead"],
          [96.0, 100.0])
    check("no lead", plan_segments(timeline, table, 4.0, 4.0,
                                   lead_floor=101.0)["lead"],
          [100.0, 100.0])

    # clock: a recording measures its own sim-per-wall rate, and a rig
    # keeping up with the wall degenerates to the bare t0 subtraction
    slow = clock(100.0, 500.0, 4501, 15)
    check("clock rate", round(slow["rate"], 9), 0.75)
    check("clock length", round(slow["length_s"], 6),
          round(4501 / 15.0, 6))
    check("video_time scaled", round(video_time(slow, 200.0), 6), 75.0)
    even = clock(100.0, 400.0, 4501, 15)
    check("clock at wall speed", round(even["rate"], 9), 1.0)
    check("video_time degenerate", round(video_time(even, 250.0), 6),
          150.0)
    for bad in ((100.0, 100.0, 4501), (100.0, 90.0, 4501),
                (100.0, 500.0, 1)):
        try:
            clock(bad[0], bad[1], bad[2], 15)
            failures.append("clock: {!r} was accepted".format(bad))
        except ValueError:
            pass

    # read_clock: the three sidecars, and a named refusal without them
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "follow.mp4")
        for suffix, text in ((".t0", "100.000000"), (".t1", "500.000000"),
                             (".n", "4501")):
            with open(base + suffix, "w", encoding="utf-8") as side:
                side.write(text + "\n")
        check("read_clock rate", round(read_clock(base, 15)["rate"], 9),
              0.75)
        os.remove(base + ".t1")
        try:
            read_clock(base, 15)
            failures.append("read_clock: a missing .t1 was accepted")
        except ValueError as exc:
            if ".t1" not in str(exc):
                failures.append("read_clock: refusal names the sidecar? "
                                "{!r}".format(str(exc)))

    # ffmpeg_argv: four sources, vehicle PiP, each on its own clock
    sources = {"follow": "f.mp4", "dock": "d.mp4", "wide": "w.mp4",
               "vehicle": "v.mp4"}
    firsts = {"follow": 90.0, "dock": 92.0, "wide": 90.0, "vehicle": 91.0}
    # 6000 frames at 15 fps is 400 s of footage: long enough for the
    # whole plan on either rate below
    clocks = {cam: clock(t0, t0 + (6000 - 1) / 15.0, 6000, 15)
              for cam, t0 in firsts.items()}
    argv = ffmpeg_argv(plan, sources, clocks, "out.mp4", 15, 0.25, 24, 0.5)
    check("argv is ffmpeg -y", argv[:2], ["ffmpeg", "-y"])
    check("argv input count", argv.count("-i"), 4)
    graph = argv[argv.index("-filter_complex") + 1]
    # lead on wide, source clock = wall - offset at rate 1: 96-90 .. 100-90
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
    # the inset stream stops with its last window, not with its file
    check("pip is trimmed to its last window",
          "[3:v]trim=0:108.000,setpts=PTS-STARTPTS,scale=" in graph, True)
    check("argv ends at the output", argv[-1], "out.mp4")

    # the SAME cut on a rig running at 0.75 x wall: three quarters of
    # every trim, and a PiP window measured in concatenated footage
    scaled = {cam: clock(t0, t0 + (6000 - 1) / 15.0 / 0.75, 6000, 15)
              for cam, t0 in firsts.items()}
    argv = ffmpeg_argv(plan, sources, scaled, "out.mp4", 15, 0.25, 24,
                       0.5)
    graph = argv[argv.index("-filter_complex") + 1]
    check("scaled lead trim", "trim=4.500:7.500" in graph, True)
    check("scaled seg0 trim", "trim=7.500:52.500" in graph, True)
    check("scaled seg1 trim", "trim=51.000:84.000" in graph, True)
    check("scaled pip window", "between(t,48.000,81.000)" in graph, True)

    # a bound past the footage that exists is a named refusal, not a
    # silent clamp at end-of-file
    short = dict(clocks)
    short["dock"] = clock(92.0, 92.0 + (1500 - 1) / 15.0, 1500, 15)
    try:
        ffmpeg_argv(plan, sources, short, "out.mp4", 15, 0.25, 24, 0.5)
        failures.append("ffmpeg_argv: a trim past end-of-file was built")
    except ValueError as exc:
        if "112.000" not in str(exc) or "100.000" not in str(exc):
            failures.append("ffmpeg_argv: refusal names the bound and the "
                            "source length? {!r}".format(str(exc)))

    # a bound BEFORE the footage that exists is the same refusal
    early = dict(clocks)
    early["dock"] = clock(165.0, 165.0 + (6000 - 1) / 15.0, 6000, 15)
    try:
        ffmpeg_argv(plan, sources, early, "out.mp4", 15, 0.25, 24, 0.5)
        failures.append("ffmpeg_argv: a trim before the first frame was "
                        "built")
    except ValueError as exc:
        if "-5.000" not in str(exc) or "165.000" not in str(exc):
            failures.append("ffmpeg_argv: refusal names the start and the "
                            "first frame? {!r}".format(str(exc)))

    # lead_span: the DELIVERED establishing shot, on the wide clock -
    # and a short lead is cut from where the recording begins
    check("lead span", round(lead_span(plan, sources, clocks), 6), 4.0)
    check("lead span scaled", round(lead_span(plan, sources, scaled), 6),
          3.0)
    check("lead span without wide",
          lead_span(plan, {"follow": "f.mp4"}, clocks), 0.0)
    short_sources = {"wide": "w.mp4", "follow": "f.mp4", "dock": "d.mp4"}
    short_clocks = {cam: clock(t0, t0 + (6000 - 1) / 15.0, 6000, 15)
                    for cam, t0 in (("wide", 98.7), ("follow", 90.0),
                                    ("dock", 92.0))}
    check("short lead span",
          round(lead_span(short_lead, short_sources, short_clocks), 6), 1.3)
    argv = ffmpeg_argv(short_lead, short_sources, short_clocks, "out.mp4",
                       15, 0.25, 24, 0.5)
    graph = argv[argv.index("-filter_complex") + 1]
    check("short lead trims from the file's own start",
          "trim=0.000:1.300" in graph, True)

    # film_length: wall duration at rate 1, three quarters of it at
    # 0.75 - and the lead counted only when the wide camera recorded
    check("film length at wall speed",
          round(film_length(plan, sources, clocks), 6),
          round(plan["duration"], 6))
    check("film length scaled",
          round(film_length(plan, sources, scaled), 6),
          round(plan["duration"] * 0.75, 6))
    check("film length without the lead",
          round(film_length(plan, {"follow": "f.mp4", "dock": "d.mp4"},
                            clocks), 6),
          round(plan["duration"] - 4.0, 6))

    # a missing main camera is refused
    try:
        ffmpeg_argv(plan, {"wide": "w.mp4", "vehicle": "v.mp4"},
                    clocks, "out.mp4", 15, 0.25, 24, 0.5)
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