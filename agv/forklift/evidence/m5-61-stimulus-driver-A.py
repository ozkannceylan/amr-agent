#!/usr/bin/env python3
"""m5-61 stimulus driver. Creates ONE box in the running world and moves it.

Every reposition is READ BACK before the run continues: gz set_pose returns
data: true for a well-formed CALL, not for a moved ENTITY (LESSONS
2026-08-06), so a mismatch ABORTS the run rather than repairing it.
"""
import re, subprocess, sys, time
from datetime import datetime, timezone

WORLD = "forklift_arena"
NAME = "intruder"
TOL = 0.02

def stamp():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") +         "{:03d}Z".format(datetime.now(timezone.utc).microsecond // 1000)

def say(cls, detail):
    print("{} | {} | {}".format(stamp(), cls, detail), flush=True)

def run(args, timeout=15):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

def create(x, y):
    sdf = (
        "sdf: \x27<?xml version=\"1.0\" ?><sdf version=\"1.6\">"
        "<model name=\"{}\"><static>true</static><link name=\"link\">"
        "<collision name=\"c\"><geometry><box><size>0.3 0.3 0.6</size>"
        "</box></geometry></collision><visual name=\"v\"><geometry><box>"
        "<size>0.3 0.3 0.6</size></box></geometry></visual></link>"
        "</model></sdf>\x27 pose: {{ position: {{ x: {} y: {} z: 0.3 }} }}"
    ).format(NAME, x, y)
    r = run(["gz", "service", "-s", "/world/{}/create".format(WORLD),
             "--reqtype", "gz.msgs.EntityFactory",
             "--reptype", "gz.msgs.Boolean", "--timeout", "5000",
             "--req", sdf])
    say("CREATE", "box 0.30x0.30x0.60 at ({}, {}): {}".format(
        x, y, r.stdout.strip() or r.stderr.strip()))

def read_pose():
    r = run(["gz", "model", "-m", NAME, "-p"])
    txt = r.stdout
    m = re.search(r"\[(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\]", txt)
    ident = re.search(r"model:\s*\[(\d+)\]", txt) or re.search(r"\[(\d+)\]", txt)
    if not m:
        say("ABORT", "could not read the pose back: " + txt.strip()[:300])
        sys.exit(2)
    return (float(m.group(1)), float(m.group(2)), float(m.group(3)),
            int(ident.group(1)) if ident else None)

def move(eid, x, y, label):
    req = ("name: \x27{}\x27 id: {} position: {{ x: {} y: {} z: 0.3 }} "
           "orientation: {{ w: 1 }}").format(NAME, eid, x, y)
    t0 = stamp()
    r = run(["gz", "service", "-s", "/world/{}/set_pose".format(WORLD),
             "--reqtype", "gz.msgs.Pose", "--reptype", "gz.msgs.Boolean",
             "--timeout", "5000", "--req", req])
    say("STIMULUS", "{}: set_pose -> ({}, {}) returned {} at {}".format(
        label, x, y, r.stdout.strip().replace("\n", " "), t0))
    time.sleep(0.5)
    px, py, pz, _ = read_pose()
    if abs(px - x) > TOL or abs(py - y) > TOL:
        say("ABORT", "read-back ({:.3f}, {:.3f}) does not match the "
            "commanded ({}, {}): the run is DISCARDED, not repaired"
            .format(px, py, x, y))
        sys.exit(3)
    say("READBACK", "{}: pose read back ({:.3f}, {:.3f}, {:.3f}) - "
        "within {} m of the command".format(label, px, py, pz, TOL))

SEQ = [
    (10.0, 6.0, "C1 CONTROL A - plainly visible, 1.45 m OUTSIDE the corridor", 10),
    (10.0, 4.0, "W1 WARNING ONLY - near face 9.85, outside protective 9.21, inside warning 11.21", 9),
    (10.0, 6.0, "R1 release", 9),
    (11.6, 4.0, "C2 CONTROL B - IN the corridor, in the driving direction, 0.24 m OUTSIDE the warning boundary", 12),
    (10.0, 4.0, "W2 WARNING ONLY (repeat)", 9),
    (11.6, 4.0, "C3 CONTROL B (repeat)", 11),
    (2.70, 4.0, "W3 WARNING ONLY, REAR device - far face 2.85, outside protective 3.775, inside warning 1.775", 9),
    (10.0, 6.0, "C4 CONTROL A (repeat) - both fields clear", 12),
]

say("START", "m5-61 stimulus: a real object in the running simulator. "
    "Vehicle at (7.0, 4.0) yaw 0, standing, never driven. Protective "
    "corridor x 3.775..9.210, warning corridor x 1.775..11.210, y 3.45..4.55")
create(10.0, 6.0)
time.sleep(1.5)
px, py, pz, eid = read_pose()
say("READBACK", "created at ({:.3f}, {:.3f}, {:.3f}), entity id {} - resolved "
    "from the read-back, not assumed".format(px, py, pz, eid))
if eid is None:
    say("ABORT", "no entity id could be resolved; set_pose without one is a "
        "silent no-op that still reports success")
    sys.exit(4)
for x, y, label, hold in SEQ:
    move(eid, x, y, label)
    say("HOLD", "{}: holding {} s".format(label, hold))
    time.sleep(hold)
say("EXIT", "stimulus sequence complete; the box is left outside both fields")
