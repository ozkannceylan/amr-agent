#!/usr/bin/env python3
"""film_run.py - the F5 film, recorded around a cycle it does not touch.

    python3 m5_ver3/tools/film_run.py describe
    python3 m5_ver3/tools/film_run.py record
    python3 m5_ver3/tools/film_run.py cut [--session <dir>]

`record` places the three film cameras into the RUNNING world through
gz's own /create (the world file is never edited), starts
film_follow.py and one film_record.py per camera, and then runs
pallet_cycle.py's own `run` UNDER OBSERVATION - stdout line by line,
each `leg c1-<name>` stamped with the wall clock into timeline.json.
The cycle is not modified, wrapped or re-implemented: its seeding,
its recovery and its refusals stay exactly what EVIDENCE_DOCKING_V3
§4 measured, and this tool only watches.

`cut` turns that timeline plus the four recordings into one film
(film_core.plan_segments + ffmpeg_argv): the wide establishing shot,
then every leg on the camera the shot table names, with the vehicle
camera inset over the approach legs - the tag growing in frame is the
proof the dock run is tag-driven.

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
    "film.lead_s", "film.tail_s", "film.pip_scale", "film.pip_margin_px",
    "paths.traction_file",
)

# What record starts, in this order, and what cut expects beside the
# mp4s. The mp4 name is the key; the t0 sidecar is <name>.mp4.t0.
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
    """Remove a camera from the running world, tolerating its absence."""
    return _gz(cfg, "/world/{}/remove".format(cfg.s("world.name")),
               "gz.msgs.Entity", 'name: "{}"'.format(name))


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
    timeline = {"session": session, "recordings": {}, "legs": []}
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
            if stripped.startswith("=== cycle"):
                if timeline["cycle_start"] is None:
                    timeline["cycle_start"] = now
            elif stripped.startswith("leg "):
                # `leg c1-transit` -> leg name c1-transit
                timeline["legs"].append(
                    {"leg": stripped.split()[1], "t": now})
            elif stripped.startswith("done "):
                outcome = "done"
                timeline["cycle_end"] = now
            elif stripped.startswith("stopped"):
                timeline["cycle_end"] = now
        cycle_rc = cycle.wait()
        cycle_log.close()
        timeline["outcome"] = outcome
        timeline["cycle_rc"] = cycle_rc
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

    with open(os.path.join(session, "timeline.json"), "w",
              encoding="utf-8") as out:
        json.dump(timeline, out, indent=2)
    _remove_model(cfg, cfg.s("film.follow_model"))
    _remove_model(cfg, cfg.s("film.dock_model"))
    _remove_model(cfg, cfg.s("film.wide_model"))

    print("outcome   {} (cycle rc={})".format(outcome, cycle_rc))
    print("timeline  {}".format(os.path.join(session, "timeline.json")))
    if outcome != "done":
        print("the cycle did not finish; there is no film to cut "
              "from this session")
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

    sources = {}
    offsets = {}
    missing = []
    for cam, _topic_key in RECORDINGS:
        path = timeline.get("recordings", {}).get(cam)
        t0 = timeline.get("recordings", {}).get(cam + "_t0")
        if path and os.path.isfile(path) and t0 is not None:
            sources[cam] = path
            offsets[cam] = t0
        else:
            missing.append(cam)
    for cam in missing:
        print("absent    {} (cut continues without it)".format(cam))
    for cam in ("follow", "dock"):
        if cam not in sources:
            cfg.refuse("the {} recording is on disk".format(cam),
                       os.path.join(session, cam + ".mp4"),
                       "it is the film; record again")

    table = fc.shot_table(cfg.raw("film.shots"))
    try:
        plan = fc.plan_segments(timeline, table, cfg.f("film.lead_s"),
                                 cfg.f("film.tail_s"))
    except ValueError as exc:
        cfg.refuse("the timeline cuts against the shot table",
                   "config.yaml (film.shots)", str(exc))

    out = os.path.join(session, "m5v3-film.mp4")
    argv = fc.ffmpeg_argv(plan, sources, offsets, out,
                          cfg.i("film.rate_hz"), cfg.f("film.pip_scale"),
                          cfg.i("film.pip_margin_px"))
    print("cut       {} -> {:.0f} s of film".format(out, plan["duration"]))
    proc = subprocess.run(argv, cwd=REPO)
    if proc.returncode != 0:
        cfg.refuse("ffmpeg cut the film", " ".join(argv[:2]),
                   "exit {}; see the command above".format(
                       proc.returncode))
    print("film      {} ({:.0f} s)".format(out, plan["duration"]))
    print("plan      lead {:.1f} s on wide, {} legs, {} pip {}".format(
        cfg.f("film.lead_s"), len(plan["segments"]),
        len(plan["pip_windows"]),
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