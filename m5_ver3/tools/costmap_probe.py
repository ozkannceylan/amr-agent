#!/usr/bin/env python3
"""costmap_probe.py - read a nav2 costmap OFF THE RUNNING STACK and diff two.

    python3 m5_ver3/tools/costmap_probe.py describe                 # nothing
    python3 m5_ver3/tools/costmap_probe.py record --tag static_only # ROS
    python3 m5_ver3/tools/costmap_probe.py compare A B              # nothing

WHY IT EXISTS. F5 Task 1 adds an `obstacle_layer` to `global_costmap`,
which EVIDENCE_NAV_V3.md 19.9 handed on with three reasons attached. The
second of them - "it changes what the PLANNER plans through on every
goal on every arm" - is a claim about a GRID, and the honest instrument
for a claim about a grid is the grid. `nav2.yaml`'s own header makes a
PREDICTION off `combination_method: 1`: on a floor whose obstacles are
all in the frozen map, the layer can only ADD cells the map already has,
so the two costmaps should agree. This is what says whether they do.

IT IS A READER AND IT COMMANDS NOTHING. One subscription, one message,
one file. No goal, no twist, no service call, no lifecycle transition -
the vehicle does not move and the stack does not change. That is the
same line `tools/nav_health.py` draws and for the same reason: an
instrument that perturbs the thing it measures produces a figure about
the perturbation.

WHAT IT WRITES, AND WHY IT IS BYTES RATHER THAN A NUMBER. A 1712 x 1196
costmap is 2 047 552 cells and every summary of it is a choice made
before anybody knows what the difference will look like. `record` writes
the OccupancyGrid's own `data` array verbatim beside a header of its
geometry and the stack's label, so `compare` - and anything written
after it - reads the measurement rather than somebody's summary of it.
The captures live under `logs/evidence/`, which is a SIBLING of the run
directories and outside the prune (config.yaml paths.log_keep_runs).

THE LABEL CHAIN APPLIES HERE TOO, AND IT IS NOT DECORATION. Two grids
differ because a costmap parameter moved, or because the localiser did,
or because one of them was taken on a different map. `record` copies the
whole state file into the capture and REFUSES a stack that cannot say
what it is, exactly as tools/sensor_evidence.py does; `compare` prints
both labels and REFUSES a pair whose `loc=` differs, because two grids
localised in two different artifacts are not a difference about a
costmap layer.

`compare` NEEDS NO ROS. It runs on the Windows python the owner runs
pytest under, which is this track's split everywhere: the recording
needs the rig, the arithmetic does not.
"""
import argparse
import datetime
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import _common                                        # noqa: E402
import evidence_core as ec                            # noqa: E402
import map_register                                   # noqa: E402

TOOL = "costmap_probe"

# MAINTENANCE OBLIGATION: a key read below is a key listed here.
REQUIRED_KEYS = (
    "isolation.ros_domain_id",
    "paths.log_dir", "paths.traction_file",
    "map.dir", "map.name", "map.registration.file",
    "evidence.dir", "evidence.wait_first_s",
    "nav.costmap_probe.topics", "nav.costmap_probe.settle_s",
)

# nav2's own cell values, and they are three DIFFERENT facts rather than
# a scale. An OccupancyGrid carries -1 for NO_INFORMATION, 0..100 for a
# probability, and nav2's Costmap2DPublisher maps its 0..255 costmap
# onto that: 254 (LETHAL) and 253 (INSCRIBED_INFLATED) both come out as
# 100, everything between as its scaled cost, and 255 as -1.
UNKNOWN = -1
LETHAL = 100


def session_root(cfg):
    return os.path.join(_common.REPO, cfg.s("evidence.dir"))


def state_text(cfg):
    """The running stack's own state file, or a refusal.

    THE SAME RULE tools/sensor_evidence.py's `record` KEEPS. A capture
    that cannot say which plant, which estimator, which localiser and
    which nav2.yaml it was taken behind is a capture that will end up in
    a table it does not belong to, and it will not look like a failure -
    it will look like a row.
    """
    path = os.path.join(_common.REPO, cfg.s("paths.traction_file"))
    if not os.path.isfile(path):
        cfg.refuse("the stack wrote a state file", path,
                   "nothing here is running, or it was started by a "
                   "script older than the label chain.",
                   "'bash m5_ver3/m5v3.sh status'")
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    state = ec.parse_state_file(text)
    for key in ("traction", "arm", "loc", "nav"):
        if key not in state:
            cfg.refuse("the state file carries a '{}=' line".format(key),
                       path,
                       "it reads:", text.strip(),
                       "a capture with no label is a capture that will "
                       "be tabled beside one it does not belong with.")
    if state.get("nav") in (None, "off"):
        cfg.refuse("the nav arm is up", path,
                   "the state file says nav={}".format(state.get("nav")),
                   "there is no costmap without a costmap server.",
                   "'bash m5_ver3/m5v3.sh start --localize --nav'")
    return text, state


def describe(cfg):
    print("=== m5v3 costmap probe ===")
    print("topics    {}".format(cfg.s("nav.costmap_probe.topics")))
    print("settle    {:g} s after the subscription before the message is "
          "kept".format(cfg.f("nav.costmap_probe.settle_s")))
    print("writes    {}".format(session_root(cfg)))
    print("")
    print("IT COMMANDS NOTHING. One subscription, one message, one file.")
    print("The vehicle does not move and the stack is not changed.")
    return 0


def record(cfg, tag):
    try:
        import rclpy
        from nav_msgs.msg import OccupancyGrid
        from rclpy.node import Node
        from rclpy.qos import (DurabilityPolicy, HistoryPolicy, QoSProfile,
                               ReliabilityPolicy)
    except ImportError as exc:
        cfg.refuse("rclpy and nav_msgs are importable",
                   _common.CONFIG + " (paths.ros_setup)",
                   "python3 could not import what this bench needs: "
                   "{}".format(exc),
                   "it runs INSIDE WSL with /opt/ros/jazzy sourced.")
    import time

    text, state = state_text(cfg)
    topics = cfg.s("nav.costmap_probe.topics").split()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(session_root(cfg),
                       "costmap-{}-{}".format(tag, stamp))
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "state.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)

    rclpy.init(args=None)
    node = Node("m5v3_costmap_probe")
    node.set_parameters([rclpy.parameter.Parameter(
        "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
    # TRANSIENT_LOCAL, AND IT IS NOT OPTIONAL. nav2's Costmap2DPublisher
    # publishes the full grid latched; a VOLATILE subscriber joining
    # after that publication waits for the next one, which on a costmap
    # whose `always_send_full_costmap` is true is one update period away
    # and on one whose is false may never come at all.
    qos = QoSProfile(depth=1, history=HistoryPolicy.KEEP_LAST,
                     reliability=ReliabilityPolicy.RELIABLE,
                     durability=DurabilityPolicy.TRANSIENT_LOCAL)
    got = {}

    def keep(name):
        def handler(msg):
            got[name] = msg
        return handler

    for topic in topics:
        node.create_subscription(OccupancyGrid, topic, keep(topic), qos)

    # THE SETTLE IS FOR THE LAYER AND NOT FOR THE TRANSPORT. An obstacle
    # layer's first published grid can predate its first scan, so a
    # capture taken the instant the subscription matched would be a
    # measurement of a layer that had not run yet. The wait is spent
    # spinning, and the LAST message of the window is the one kept.
    deadline = time.time() + cfg.f("evidence.wait_first_s")
    while time.time() < deadline and len(got) < len(topics):
        rclpy.spin_once(node, timeout_sec=0.2)
    settle = time.time() + cfg.f("nav.costmap_probe.settle_s")
    while time.time() < settle:
        rclpy.spin_once(node, timeout_sec=0.2)

    missing = [t for t in topics if t not in got]
    node.destroy_node()
    try:
        rclpy.shutdown()
    except Exception:
        pass
    if missing:
        cfg.refuse("every costmap named in config.yaml published a grid",
                   _common.CONFIG + " (nav.costmap_probe.topics)",
                   "nothing arrived on: {}".format(" ".join(missing)),
                   "a costmap server that is ACTIVE over an EMPTY costmap "
                   "publishes nothing and says nothing about it "
                   "(tools/nav_health.py's own argument).")

    print("=== m5v3 costmap probe: record ===")
    print("session   {}".format(out))
    for topic in topics:
        msg = got[topic]
        name = topic.strip("/").replace("/", "_")
        data = bytes((int(v) & 0xFF) for v in msg.data)
        with open(os.path.join(out, name + ".bin"), "wb") as fh:
            fh.write(data)
        header = [
            "topic={}".format(topic),
            "width={}".format(msg.info.width),
            "height={}".format(msg.info.height),
            "resolution={:.9f}".format(msg.info.resolution),
            "origin_x={:.9f}".format(msg.info.origin.position.x),
            "origin_y={:.9f}".format(msg.info.origin.position.y),
            "frame_id={}".format(msg.header.frame_id),
            "cells={}".format(len(msg.data)),
            "md5={}".format(hashlib.md5(data).hexdigest()),
        ]
        with open(os.path.join(out, name + ".txt"), "w",
                  encoding="utf-8") as fh:
            fh.write("\n".join(header) + "\n")
        counts = tally(msg.data)
        print("{:<26} {}x{} at {:.3f} m  frame {}".format(
            topic, msg.info.width, msg.info.height, msg.info.resolution,
            msg.header.frame_id))
        print("{:<26} lethal(100) {}  unknown(-1) {}  free(0) {}  "
              "other {}".format("", counts["lethal"], counts["unknown"],
                                counts["free"], counts["other"]))
        print("{:<26} md5 {}".format("", header[-1].split("=")[1]))
    print("")
    print("label     {}".format(" ".join(
        "{}={}".format(k, v) for k, v in state.items())))
    return 0


def tally(data):
    lethal = unknown = free = other = 0
    for value in data:
        cell = int(value)
        if cell > 127:
            cell -= 256
        if cell == UNKNOWN:
            unknown += 1
        elif cell == 0:
            free += 1
        elif cell == LETHAL:
            lethal += 1
        else:
            other += 1
    return {"lethal": lethal, "unknown": unknown, "free": free,
            "other": other}


def read_capture(cfg, path, name):
    """One capture directory, as (header dict, signed cell list, state)."""
    if not os.path.isdir(path):
        path = os.path.join(session_root(cfg), path)
    if not os.path.isdir(path):
        cfg.refuse("the capture directory exists", path,
                   "`record` writes one per run under {}".format(
                       session_root(cfg)))
    txt = os.path.join(path, name + ".txt")
    binary = os.path.join(path, name + ".bin")
    for wanted in (txt, binary):
        if not os.path.isfile(wanted):
            cfg.refuse("the capture carries {}".format(
                os.path.basename(wanted)), path,
                "this directory holds: {}".format(
                    " ".join(sorted(os.listdir(path)))))
    header = {}
    with open(txt, encoding="utf-8") as fh:
        for line in fh:
            if "=" in line:
                key, value = line.strip().split("=", 1)
                header[key] = value
    with open(binary, "rb") as fh:
        raw = fh.read()
    cells = [v - 256 if v > 127 else v for v in raw]
    state = ""
    state_path = os.path.join(path, "state.txt")
    if os.path.isfile(state_path):
        with open(state_path, encoding="utf-8") as fh:
            state = fh.read()
    return header, cells, state


def geometry_matches(a, b):
    keys = ("width", "height", "resolution", "origin_x", "origin_y",
            "frame_id")
    return [k for k in keys if a.get(k) != b.get(k)]


def compare(cfg, before, after, name):
    header_a, cells_a, state_a = read_capture(cfg, before, name)
    header_b, cells_b, state_b = read_capture(cfg, after, name)
    differ = geometry_matches(header_a, header_b)
    if differ:
        cfg.refuse("the two captures are of the same grid",
                   "{} and {}".format(before, after),
                   "these differ: {}".format(", ".join(differ)),
                   "a cell-by-cell difference between two grids of "
                   "different geometry is arithmetic about nothing.")
    label_a = ec.parse_state_file(state_a)
    label_b = ec.parse_state_file(state_b)
    if label_a.get("loc") != label_b.get("loc"):
        cfg.refuse("both captures were localised in the same artifact",
                   "the two state.txt files",
                   "loc={} against loc={}".format(label_a.get("loc"),
                                                  label_b.get("loc")),
                   "two grids localised in two artifacts are not a "
                   "difference about a costmap layer.")

    width = int(header_a["width"])
    resolution = float(header_a["resolution"])
    ox = float(header_a["origin_x"])
    oy = float(header_a["origin_y"])
    raised = []
    lowered = []
    new_lethal = 0
    lost_lethal = 0
    known = 0
    for index, (was, now) in enumerate(zip(cells_a, cells_b)):
        if now == was:
            continue
        if was == UNKNOWN or now == UNKNOWN:
            known += 1
            continue
        if now > was:
            raised.append((index, was, now))
            if now == LETHAL and was != LETHAL:
                new_lethal += 1
        else:
            lowered.append((index, was, now))
            if was == LETHAL and now != LETHAL:
                lost_lethal += 1

    frame = None
    try:
        record = map_register.load_registration(
            os.path.join(_common.REPO, cfg.s("map.dir"), cfg.s("map.name"),
                         cfg.s("map.registration.file")))
        frame = ec.MapFrame.from_registration(record)
    except Exception:
        frame = None

    def where(index):
        col = index % width
        row = index // width
        mx = ox + (col + 0.5) * resolution
        my = oy + (row + 0.5) * resolution
        if frame is None:
            return "map ({:+.3f}, {:+.3f})".format(mx, my)
        wx, wy = frame.to_world(mx, my)[:2]
        return "world ({:+.3f}, {:+.3f})".format(wx, wy)

    print("=== m5v3 costmap probe: compare ===")
    print("grid      {} x {} at {} m, frame {}".format(
        header_a["width"], header_a["height"], header_a["resolution"],
        header_a["frame_id"]))
    print("before    {}".format(before))
    print("          {}".format(" ".join(
        "{}={}".format(k, v) for k, v in label_a.items())))
    print("after     {}".format(after))
    print("          {}".format(" ".join(
        "{}={}".format(k, v) for k, v in label_b.items())))
    print("")
    tally_a = tally([c & 0xFF for c in cells_a])
    tally_b = tally([c & 0xFF for c in cells_b])
    print("{:<12} {:>12} {:>12}".format("", "before", "after"))
    for key in ("lethal", "unknown", "free", "other"):
        print("{:<12} {:>12} {:>12}".format(key, tally_a[key], tally_b[key]))
    print("")
    print("RAISED    {} cells  (of which NEW LETHAL {})".format(
        len(raised), new_lethal))
    print("LOWERED   {} cells  (of which LETHAL LOST {})".format(
        len(lowered), lost_lethal))
    print("KNOWN/UNKNOWN CHANGED  {} cells".format(known))
    if lowered:
        print("")
        print("A LOWERED CELL IS THE ONE RESULT THIS LAYER CANNOT "
              "PRODUCE. combination_method: 1")
        print("is MAX, and nav2's updateWithMax never writes below what "
              "is already there. If")
        print("these are not zero the layer is not doing what "
              "nav2.yaml's header says it does.")
        for index, was, now in lowered[:10]:
            print("  {:<34} {} -> {}".format(where(index), was, now))
    if raised:
        print("")
        print("the first ten raised cells:")
        for index, was, now in raised[:10]:
            print("  {:<34} {} -> {}".format(where(index), was, now))
    return 0


def main(argv=None):
    cfg = _common.load_config(TOOL, REQUIRED_KEYS)
    parser = argparse.ArgumentParser(prog="costmap_probe.py")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("describe")
    rec = sub.add_parser("record")
    rec.add_argument("--tag", required=True,
                     help="what this capture is OF, e.g. static_only")
    cmp_ = sub.add_parser("compare")
    cmp_.add_argument("before")
    cmp_.add_argument("after")
    cmp_.add_argument("--costmap", default="global_costmap_costmap",
                      help="which of the captured grids to diff")
    args = parser.parse_args(argv)
    if args.cmd == "record":
        return record(cfg, args.tag)
    if args.cmd == "compare":
        return compare(cfg, args.before, args.after, args.costmap)
    return describe(cfg)


if __name__ == "__main__":
    raise SystemExit(main())
