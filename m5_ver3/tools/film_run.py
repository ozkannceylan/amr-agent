#!/usr/bin/env python3
"""film_run.py - the F5 film, recorded around a cycle it does not touch.

    python3 m5_ver3/tools/film_run.py describe
    python3 m5_ver3/tools/film_run.py record
    python3 m5_ver3/tools/film_run.py cut [--session <dir>]

`record` places the three film cameras into the RUNNING world through
gz's own /create (the world file is never edited), starts
film_follow.py and one film_record.py per camera, holds a pre-roll so
the establishing shot is footage rather than luck, and then runs
pallet_cycle.py's own `run` UNDER OBSERVATION - stdout line by line,
each `leg c1-<name>` stamped with the wall clock into timeline.json,
and every RECOVERY INTERVENTION the cycle prints stamped there by
name beside them. The cycle is not modified, wrapped or
re-implemented: its seeding, its recovery and its refusals stay
exactly what EVIDENCE_DOCKING_V3 §4 measured, and this tool only
watches - it records the recovery, it does not prevent it.

`cut` turns that timeline plus the four recordings into one film
(film_core.plan_segments + ffmpeg_argv): the wide establishing shot -
film.lead_s of it, or as much as the wide recording holds and says so
- then every leg on the camera the shot table names, with the vehicle
camera inset over the approach legs - the tag growing in frame is the
proof the dock run is tag-driven.
  The timeline is stamped on the WALL clock and the cameras publish on
the SIM clock, so every bound crosses through film_core.clock: each
recording's own t0/t1/n sidecars measure how fast its clock ran, and
a segment that would need footage past the end of its file is refused
by name rather than clamped there by ffmpeg.
  A timeline holding a recovery intervention is refused BY NAME before
any of that (AMR-DEC-004): the film of a cycle that needed a recovery
is not the film of autonomy, and there is no flag that says otherwise.

Needs ROS, gz and ffmpeg; the stack must already be up
(`m5v3.sh start --localize amcl --nav --dock`).
"""
import argparse
import datetime
import json
import math
import os
import signal
import subprocess
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import film_core as fc                                # noqa: E402

TOOL = "film_run"
REPO = _common.REPO

REQUIRED_KEYS = (
    "isolation.ros_domain_id", "isolation.gz_partition",
    "world.name", "timing.spawn_service_timeout_ms",
    "vehicle.spawn.x", "vehicle.spawn.y",
    "film.dir", "film.cycle_tool", "film.cycle_repeat",
    "film.record_budget_s", "film.rate_hz", "film.camera_warmup_s",
    "film.follow_model", "film.follow_sdf", "film.follow_topic",
    "film.follow_height_m",
    "film.dock_model", "film.dock_sdf", "film.dock_topic",
    "film.dock_pose",
    "film.wide_model", "film.wide_sdf", "film.wide_topic",
    "film.vehicle_topic",
    "film.lead_s", "film.tail_s", "film.eof_tolerance_s",
    "film.pip_scale", "film.pip_margin_px",
    "paths.traction_file",
)

# The pre-roll record holds before the cycle, as a multiple of
# film.lead_s. It is not a config knob but a property of that key's
# UNITS: lead_s is footage and this hold is wall time, the cameras
# publish on the sim clock, and this rig measures 0.66-0.77 x wall and
# has not been seen under 0.5 - so twice the wall is at least the lead,
# and one number lives in one place.
PRE_ROLL_X_LEAD = 2.0

# What record starts, in this order, and what cut expects beside the
# mp4s. The mp4 name is the key; film_record.py leaves three
# one-number sidecars by each - <name>.mp4.t0, .t1 and .n - and cut
# needs all three to place that recording on the film's clock.
RECORDINGS = (
    ("follow", "film.follow_topic"),
    ("dock", "film.dock_topic"),
    ("wide", "film.wide_topic"),
    ("vehicle", "film.vehicle_topic"),
)


def _gz(cfg, service, reqtype, req):
    cmd = ["gz", "service", "-s", service,
           "--reqtype", reqtype, "--reptype", "gz.msgs.Boolean",
           "--timeout", str(cfg.s("timing.spawn_service_timeout_ms")),
           "--req", req]
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=30).stdout
    except Exception as exc:                          # pragma: no cover
        return "gz service failed: {}".format(exc)


def _remove_model(cfg, name):
    """Remove a camera from the running world, tolerating its absence.

    `type: MODEL` is not decoration: gz-sim resolves an Entity with no
    type to kNullEntity and the remove is a silent no-op, so the next
    /create with allow_renaming: false is refused for a name that is
    still taken. The same body furniture.py and pallet_place.py spell.
    """
    return _gz(cfg, "/world/{}/remove".format(cfg.s("world.name")),
               "gz.msgs.Entity", 'name: "{}", type: MODEL'.format(name))


def _create_model(cfg, name, sdf_key, pose):
    """Spawn a camera SDF at a pose. pose None -> the SDF's own pose."""
    sdf = os.path.join(REPO, cfg.s(sdf_key))
    if not os.path.isfile(sdf):
        cfg.refuse("the camera SDF exists", _common.CONFIG
                   + " ({})".format(sdf_key), sdf)
    req = fc.create_request(sdf, name, pose) if pose else (
        'sdf_filename: "{}", name: "{}", allow_renaming: false'
    ).format(sdf.replace("\\", "/"), name)
    return _gz(cfg, "/world/{}/create".format(cfg.s("world.name")),
               "gz.msgs.EntityFactory", req)


def _spawn_pose(cfg):
    """The follow camera's SPAWN pose: above the truck's rest pose."""
    return fc.parse_pose("{:.9f} {:.9f} {:.9f} 0 {:.9f} 0".format(
        cfg.f("vehicle.spawn.x"), cfg.f("vehicle.spawn.y"),
        cfg.f("film.follow_height_m"), math.pi / 2.0))


def _start_child(cfg, argv, log_path):
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(argv, stdout=log, stderr=subprocess.STDOUT,
                            cwd=REPO)
    return proc, log


def describe(cfg):
    print("=== m5v3 film ===")
    print("session   {}/film-<stamp>".format(cfg.s("film.dir")))
    print("cycle     {} run --repeat {}".format(
        cfg.s("film.cycle_tool"), cfg.s("film.cycle_repeat")))
    for cam, topic_key in RECORDINGS:
        print("{:<9} {}".format(cam, cfg.s(topic_key)))
    print("follow    {} m, moved by film_follow.py".format(
        cfg.s("film.follow_height_m")))
    print("dock      fixed at {}".format(cfg.s("film.dock_pose")))
    print("shots")
    for leg, cam, pip in fc.shot_table(cfg.raw("film.shots")):
        print("  {:<9} {:<7} pip={}".format(leg, cam, str(pip).lower()))
    print("pre-roll  {:.1f} s held before the cycle".format(
        PRE_ROLL_X_LEAD * cfg.f("film.lead_s")))
    print("cut       wide lead {:.1f} s, last leg holds {:.1f} s".format(
        cfg.f("film.lead_s"), cfg.f("film.tail_s")))
    return 0


def _latest_session(cfg):
    root = os.path.join(REPO, cfg.s("film.dir"))
    if not os.path.isdir(root):
        return None
    best, stamp = None, ""
    for name in os.listdir(root):
        if name.startswith("film-") and name > stamp:
            best, stamp = os.path.join(root, name), name
    return best


def _read_t0(path):
    with open(path, encoding="utf-8") as handle:
        return float(handle.read().strip())


def record(cfg):
    state = os.path.join(REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(state):
        cfg.refuse("a stack is up (paths.traction_file exists)",
                   cfg.s("paths.traction_file"),
                   "bring up `m5v3.sh start --localize amcl --nav --dock` "
                   "first; a film needs the world, Nav2, the marker and "
                   "the dock arm to be running")

    os.environ["ROS_DOMAIN_ID"] = cfg.s("isolation.ros_domain_id")
    os.environ["GZ_PARTITION"] = cfg.s("isolation.gz_partition")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    session = os.path.join(REPO, cfg.s("film.dir"), "film-" + stamp)
    os.makedirs(session, exist_ok=True)
    timeline = {"session": session, "recordings": {}, "legs": [],
                "interventions": []}
    print("session   {}".format(session))

    # ---- the cameras, placed and named before anything records ----
    _remove_model(cfg, cfg.s("film.follow_model"))
    _remove_model(cfg, cfg.s("film.dock_model"))
    _remove_model(cfg, cfg.s("film.wide_model"))
    for name, sdf_key, pose in (
            (cfg.s("film.follow_model"), "film.follow_sdf",
             _spawn_pose(cfg)),
            (cfg.s("film.dock_model"), "film.dock_sdf",
             fc.parse_pose(cfg.s("film.dock_pose"))),
            (cfg.s("film.wide_model"), "film.wide_sdf", None)):
        reply = _create_model(cfg, name, sdf_key, pose)
        if "data: true" not in reply:
            cfg.refuse("the camera {} was placed".format(name),
                       "gz /world/{}/create".format(cfg.s("world.name")),
                       (reply or "<empty>")[:200])
        print("placed    {}".format(name))

    children = []
    cycle_rc = None
    try:
        # ---- THE BRIDGE FIRST: the film cameras publish on gz and the
        # recorders subscribe on ROS. The vehicle camera already
        # crosses on the imgbridge the stack runs; the three film
        # cameras need their own image_bridge or every recorder waits
        # for a first frame that never arrives - the refusal below is
        # named for exactly that silence. One process, three topics,
        # the same ros_gz_image image_bridge m5v3.sh measured.
        bridge_argv = ["ros2", "run", "ros_gz_image", "image_bridge",
                       cfg.s("film.follow_topic"),
                       cfg.s("film.dock_topic"),
                       cfg.s("film.wide_topic")]
        bridge_proc, bridge_log = _start_child(
            cfg, bridge_argv, os.path.join(session, "filmbridge.log"))
        children.append((bridge_proc, bridge_log))
        print("bridge    {}".format(" ".join(bridge_argv[3:])))

        # ---- film_follow.py, before the recorders so the first frame
        # is already over the truck ----
        follow_proc, follow_log = _start_child(
            cfg, [sys.executable,
                  os.path.join(_HERE, "film_follow.py")],
            os.path.join(session, "follow.log"))
        children.append((follow_proc, follow_log))

        # ---- one recorder per camera ----
        for cam, topic_key in RECORDINGS:
            out = os.path.join(session, cam + ".mp4")
            proc, log = _start_child(
                cfg, [sys.executable,
                      os.path.join(_HERE, "film_record.py"),
                      "--topic", cfg.s(topic_key), "--out", out,
                      "--seconds", cfg.s("film.record_budget_s")],
                os.path.join(session, "rec-{}.log".format(cam)))
            children.append((proc, log))
            timeline["recordings"][cam] = out
            print("recording {} -> {}".format(cam, out))

        # ---- first frames, or a camera named for its silence ----
        deadline = time.time() + cfg.f("film.camera_warmup_s")
        waiting = dict(RECORDINGS)
        while waiting and time.time() < deadline:
            for cam in list(waiting):
                t0_path = timeline["recordings"][cam] + ".t0"
                if os.path.isfile(t0_path):
                    timeline["recordings"][cam + "_t0"] = _read_t0(t0_path)
                    del waiting[cam]
            time.sleep(0.5)
        if waiting:
            for cam in waiting:
                print("silent    {}".format(cam))
            cfg.refuse("every camera published a first frame",
                       "config.yaml (film.camera_warmup_s)",
                       "{} stayed silent for {} s: {}".format(
                           " ".join(sorted(waiting)),
                           cfg.s("film.camera_warmup_s"),
                           "; ".join("{} on {}".format(
                               cam, cfg.s(topic_key))
                               for cam, topic_key in RECORDINGS
                               if cam in waiting)))

        # ---- the establishing pre-roll, before the cycle ----
        # The cut opens on film.lead_s of wide footage from BEFORE the
        # first leg, and it can only trim what the wide recorder
        # already holds; without this hold the cycle starts a second or
        # two after the first frame and the lead is whatever happened
        # to exist. PRE_ROLL_X_LEAD carries the units argument.
        pre_roll = PRE_ROLL_X_LEAD * cfg.f("film.lead_s")
        print("pre-roll  {:.1f} s of establishing footage before the "
              "cycle".format(pre_roll))
        time.sleep(pre_roll)

        # ---- the cycle, under observation ----
        print("cycle     {} run --repeat {}".format(
            cfg.s("film.cycle_tool"), cfg.s("film.cycle_repeat")))
        cycle_log = open(os.path.join(session, "cycle.log"), "w",
                         encoding="utf-8")
        children.append((None, cycle_log))
        cycle = subprocess.Popen(
            [sys.executable, "-u",
             os.path.join(_HERE, cfg.s("film.cycle_tool")),
             "run", "--repeat", cfg.s("film.cycle_repeat")],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            cwd=REPO, text=True, bufsize=1)
        timeline["cycle_start"] = None
        timeline["cycle_end"] = None
        outcome = "stopped"
        for line in cycle.stdout:
            now = time.time()
            cycle_log.write("{:.3f} {}\n".format(now, line.rstrip()))
            cycle_log.flush()
            stripped = line.strip()
            print("  " + stripped)
            # A RECOVERY INTERVENTION IS STAMPED WHEREVER IT FALLS, and
            # on its own `if`: the cycle prints it between two legs and
            # it is not one, so it never competes with the leg chain
            # below. AMR-DEC-004: the film of a cycle that needed a
            # recovery is not the film of autonomy, and cut refuses the
            # timeline that holds one. This tool still only WATCHES -
            # the cycle is not steered away from its own recovery.
            recovery = fc.intervention(stripped)
            if recovery is not None:
                timeline["interventions"].append(
                    {"name": recovery, "t": now, "line": stripped})
            if stripped.startswith("=== cycle"):
                if timeline["cycle_start"] is None:
                    timeline["cycle_start"] = now
            elif stripped.startswith("leg "):
                # `leg c1-transit` -> the table's own leg name,
                # `transit`. Anything else on this pipe is not the
                # cycle talking: drive_goal.py prints `leg 1 ...` into
                # the same stdout, and a timeline holding `1` would be
                # refused by a cut of a run that was perfect.
                fields = stripped.split()
                leg = fc.bare_leg(fields[1]) if len(fields) > 1 else None
                if leg is not None:
                    timeline["legs"].append({"leg": leg, "t": now})
            elif stripped.startswith("done "):
                outcome = "done"
                timeline["cycle_end"] = now
            elif stripped.startswith("stopped"):
                timeline["cycle_end"] = now
        cycle_rc = cycle.wait()
        cycle_log.close()
        timeline["outcome"] = outcome
        timeline["cycle_rc"] = cycle_rc
        if outcome == "done":
            # film_core plans the last segment film.tail_s PAST
            # cycle_end, so those seconds have to exist on disk: stop
            # the recorders at `done` and the cut REFUSES a last trim
            # it cannot satisfy. Wall seconds are the right unit for
            # this hold whatever the sim clock is doing - the bound and
            # the footage scale by the same rate - and the extra second
            # is the recorder's own last write.
            hold = cfg.f("film.tail_s") + 1.0
            print("holding   {:.1f} s of tail past done".format(hold))
            time.sleep(hold)
    finally:
        # ---- teardown: recorders by SIGINT (their own clean exit),
        # film_follow by SIGTERM ----
        for proc, log in children:
            if proc is None:
                if log is not None and not log.closed:
                    log.close()
                continue
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
        time.sleep(2.0)
        for proc, log in children:
            if proc is not None and proc.poll() is None:
                proc.terminate()
        for proc, log in children:
            if log is not None and not log.closed:
                log.close()
        # The three cameras come out HERE, after the recorders that
        # read them are gone: a refusal above raises SystemExit, and
        # a take that left film_follow, film_dock and film_overhead
        # standing in the world costs the next take its /create - and
        # then the whole stack a restart.
        _remove_model(cfg, cfg.s("film.follow_model"))
        _remove_model(cfg, cfg.s("film.dock_model"))
        _remove_model(cfg, cfg.s("film.wide_model"))

    with open(os.path.join(session, "timeline.json"), "w",
              encoding="utf-8") as out:
        json.dump(timeline, out, indent=2)

    print("outcome   {} (cycle rc={})".format(outcome, cycle_rc))
    print("timeline  {}".format(os.path.join(session, "timeline.json")))
    if outcome != "done":
        print("the cycle did not finish; there is no film to cut "
              "from this session")
        return 1
    if timeline["interventions"]:
        # The same answer cut gives, given here rather than eight
        # minutes later: a take that needed a recovery is a take to
        # record again, and an operator learns that now.
        print("recovery  {} intervention(s) recorded".format(
            len(timeline["interventions"])))
        for text in fc.intervention_lines(timeline):
            print(text)
        print("the cycle recovered rather than drove; there is no film "
              "to cut from this session")
        return 1
    print("cut with  film_run.py cut --session {}".format(session))
    return 0


def cut(cfg, session):
    if session is None:
        session = _latest_session(cfg)
        if session is None:
            cfg.refuse("a filmed session exists", cfg.s("film.dir"),
                       "no film-<stamp> directory under it; record first")
    timeline_path = os.path.join(session, "timeline.json")
    if not os.path.isfile(timeline_path):
        cfg.refuse("the session has a timeline", timeline_path,
                   "record writes it; this session has none")
    with open(timeline_path, encoding="utf-8") as handle:
        timeline = json.load(handle)

    # ---- A FILM MAY NOT SILENTLY CONTAIN A RECOVERY ----
    # AMR-DEC-004 consequence 2. The cycle recovers a Nav2 miss by
    # teleporting the truck to staging and prints it; the shipped E2E
    # take held one and nothing downstream said a word. This gate is
    # FIRST - before the recordings are read, before the plan, before
    # ffmpeg - because it is not a fact about footage, and there is no
    # override flag: the owner watches films, not flags. A timeline
    # with no `interventions` key at all was recorded before this check
    # existed and cuts exactly as it did.
    if fc.interventions(timeline):
        cfg.refuse(
            "the filmed cycle needed no recovery intervention",
            timeline_path,
            *(["the film of a cycle that needed a recovery is not the "
               "film of autonomy:"]
              + fc.intervention_lines(timeline)
              + ["record another take; a recovered cycle has no film "
                 "in it"]))

    # Each recording is placed on the film's clock from its OWN
    # sidecars rather than from the t0 the timeline also carries: one
    # source for all three numbers, and a file whose recorder never
    # closed cleanly is caught here instead of trimmed as a guess.
    fps = cfg.i("film.rate_hz")
    sources = {}
    clocks = {}
    missing = []
    for cam, _topic_key in RECORDINGS:
        path = timeline.get("recordings", {}).get(cam)
        if not (path and os.path.isfile(path)):
            missing.append((cam, "no recording on disk"))
            continue
        try:
            clocks[cam] = fc.read_clock(path, fps)
        except ValueError as exc:
            missing.append((cam, str(exc)))
            continue
        sources[cam] = path
    for cam, why in missing:
        # follow and dock ARE the film; wide and vehicle are cut
        # around with a printed line, and the line says why.
        if cam in ("follow", "dock"):
            cfg.refuse(
                "the {} recording can be placed on the film's "
                "clock".format(cam),
                os.path.join(session, cam + ".mp4"),
                *why.split("\n"))
        print("absent    {} ({}); cut continues without it".format(
            cam, why.splitlines()[0]))

    table = fc.shot_table(cfg.raw("film.shots"))
    # The lead is planned from the footage that EXISTS: the wide
    # recording's own first frame is the earliest second the film may
    # open on, so a recorder that started late costs a short
    # establishing shot instead of a trim from before the file - which
    # ffmpeg would clamp at 0 without a word, shifting every segment
    # after it away from the printed plan.
    lead_floor = clocks["wide"]["t0"] if "wide" in clocks else None
    try:
        plan = fc.plan_segments(timeline, table, cfg.f("film.lead_s"),
                                cfg.f("film.tail_s"),
                                lead_floor=lead_floor)
    except ValueError as exc:
        cfg.refuse("the timeline cuts against the shot table",
                   "config.yaml (film.shots)", str(exc))

    out = os.path.join(session, "m5v3-film.mp4")
    try:
        argv = fc.ffmpeg_argv(plan, sources, clocks, out, fps,
                              cfg.f("film.pip_scale"),
                              cfg.i("film.pip_margin_px"),
                              cfg.f("film.eof_tolerance_s"))
    except ValueError as exc:
        cfg.refuse("every segment fits inside its own recording",
                   "config.yaml (film.eof_tolerance_s)",
                   *str(exc).split("\n"))
    for cam in sorted(clocks):
        clk = clocks[cam]
        print("clock     {:<8} {} frames, {:.1f} s of footage, "
              "sim {:.3f} x wall".format(
                  cam, clk["n"], clk["length_s"], clk["rate"]))
    lead_s = cfg.f("film.lead_s")
    if sources.get("wide"):
        if plan["lead"][1] - plan["lead"][0] < lead_s - 1e-6:
            print("lead      {:.2f} s of a planned {:.1f} s - the wide "
                  "recording begins there".format(
                      fc.lead_span(plan, sources, clocks), lead_s))
        else:
            print("lead      {:.2f} s of footage from the planned "
                  "{:.1f} s before the cycle".format(
                      fc.lead_span(plan, sources, clocks), lead_s))
    length = fc.film_length(plan, sources, clocks)
    print("cut       {} -> {:.0f} s of film from a {:.0f} s cycle".format(
        out, length, plan["duration"]))
    try:
        proc = subprocess.run(argv, cwd=REPO)
    except OSError as exc:
        cfg.refuse("ffmpeg is on the PATH", "the shell this tool runs in",
                   "could not run `{}`: {}".format(argv[0], exc),
                   "on this rig ffmpeg is /home/ozkan/bin/ffmpeg, which "
                   "only a LOGIN shell has: cut through",
                   "  wsl -e bash -lc '... film_run.py cut'")
    if proc.returncode != 0:
        cfg.refuse("ffmpeg cut the film", " ".join(argv[:2]),
                   "exit {}; see the command above".format(
                       proc.returncode))
    # Two decimals because this number is a claim about the encode:
    # ffprobe's own duration is what it has to match.
    print("film      {} ({:.2f} s)".format(out, length))
    print("plan      {} legs, {} pip {}".format(
        len(plan["segments"]), len(plan["pip_windows"]),
        "window" + ("s" if len(plan["pip_windows"]) != 1 else "")))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="film_run.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    rec = sub.add_parser("record")
    cut_p = sub.add_parser("cut")
    cut_p.add_argument("--session", default=None)
    args = parser.parse_args(argv)
    if args.cmd == "record":
        return record(cfg)
    if args.cmd == "cut":
        return cut(cfg, args.session)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())