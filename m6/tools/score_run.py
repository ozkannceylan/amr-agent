"""score_run.py - what a recording actually did, measured off odometry.

THE SIX CRITERIA IN THE M6.6 SPEC ARE NUMBERS, AND SOMETHING HAS TO
PRODUCE THEM. Four of them are about motion - how far the fleet drove,
whether every truck kept working, how long the transports took - and the
only honest source for those is the plant's own odometry, not the
fleet's opinion of itself. This subscribes the four `/fN/gz/odom`
topics, writes one line per sample, and turns the file into the table
that goes into PROOF.md.

TWO MODES, AND THE SPLIT IS THE POINT. `--record` needs ROS and a
running world; `--report` needs neither and reads a file written
earlier. So a run can be scored again, by anyone, without re-driving it
- which is the difference between a measurement and an anecdote.

A JUMP IS NOT A JOURNEY. Consecutive samples further apart than
JUMP_M are dropped from the distance sum rather than added to it: a
respawn, a dropped feed that resumes elsewhere, or a truck teleported by
a reset would otherwise be worth tens of metres of "travel" each. At
5 Hz and a 0.70 m/s ceiling a real step is 0.14 m, so 1.0 m is a
generous line and it is stated here rather than tuned quietly.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m6/tools/score_run.py --record --seconds 620 --out run.jsonl
  python3 m6/tools/score_run.py --report run.jsonl
"""
import argparse
import json
import math
import sys
import time
from collections import OrderedDict

SAMPLE_HZ = 5.0
JUMP_M = 1.0
WINDOW_S = 120.0        # the spec's "every 2-minute window"
MOVED_M = 1.0           # what counts as a truck having moved in a window
VEHICLES = ("f1", "f2", "f3", "f4")


def record(seconds, path):
    import rclpy
    from rclpy.node import Node
    from nav_msgs.msg import Odometry

    class Sampler(Node):
        def __init__(self):
            super().__init__("score_run")
            self._fh = open(path, "w", encoding="utf-8")
            self.t0 = time.monotonic()
            self.last = {}
            self.count = 0
            for vid in VEHICLES:
                self.create_subscription(
                    Odometry, "/{}/gz/odom".format(vid),
                    self._make(vid), 10)
            self.create_timer(1.0, self._tick)

        def _make(self, vid):
            def cb(msg):
                now = time.monotonic()
                if now - self.last.get(vid, 0.0) < 1.0 / SAMPLE_HZ:
                    return
                self.last[vid] = now
                p = msg.pose.pose.position
                self._fh.write(json.dumps(
                    {"t": round(now - self.t0, 3), "v": vid,
                     "x": round(p.x, 4), "y": round(p.y, 4)}) + "\n")
                self.count += 1
            return cb

        def _tick(self):
            if time.monotonic() - self.t0 >= seconds:
                raise SystemExit(0)

        def close(self):
            self._fh.close()
            print("wrote {} samples over {:.0f} s to {}".format(
                self.count, time.monotonic() - self.t0, path))

    rclpy.init()
    node = Sampler()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()


def report(path):
    rows = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if not rows:
        print("no samples in {}".format(path))
        return 1
    span = max(r["t"] for r in rows)
    per = OrderedDict((v, 0.0) for v in VEHICLES)
    windows = {}
    prev = {}
    jumps = 0
    for r in rows:
        v, xy, t = r["v"], (r["x"], r["y"]), r["t"]
        if v in prev:
            step = math.dist(prev[v], xy)
            if step > JUMP_M:
                jumps += 1
            else:
                per[v] = per.get(v, 0.0) + step
                key = (v, int(t // WINDOW_S))
                windows[key] = windows.get(key, 0.0) + step
        prev[v] = xy
    total = sum(per.values())
    n_win = int(span // WINDOW_S) + 1

    print("\n--- run scored from {} ---".format(path))
    print("span {:.0f} s, {} samples, {} jump(s) dropped (> {} m)".format(
        span, len(rows), jumps, JUMP_M))
    print("\nDISTANCE")
    for v, metres in per.items():
        print("  {}  {:8.1f} m".format(v, metres))
    print("  {}  {:8.1f} m".format("ALL", total))

    print("\nMOVEMENT PER {:.0f} s WINDOW (metres; a truck must move "
          "{:.0f} m to count)".format(WINDOW_S, MOVED_M))
    header = "  {:6}".format("window") + "".join(
        "{:>9}".format(v) for v in VEHICLES)
    print(header)
    idle = []
    for w in range(n_win):
        cells = []
        for v in VEHICLES:
            metres = windows.get((v, w), 0.0)
            cells.append("{:9.1f}".format(metres))
            if metres < MOVED_M:
                idle.append((w, v))
        print("  {:<6}".format(w) + "".join(cells))
    if idle:
        print("  STOOD STILL: " + ", ".join(
            "w{} {}".format(w, v) for w, v in idle))
    else:
        print("  every truck moved in every window")
    return 0


def main():
    ap = argparse.ArgumentParser(description="score a recorded run")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--seconds", type=float, default=620.0)
    ap.add_argument("--out", default="run.jsonl")
    ap.add_argument("--report", default=None)
    args = ap.parse_args()
    if args.report:
        return report(args.report)
    if not args.record:
        ap.error("give --record or --report")
    record(args.seconds, args.out)
    return report(args.out)


if __name__ == "__main__":
    sys.exit(main())
