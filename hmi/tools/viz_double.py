#!/usr/bin/env python3
"""viz_double.py - a stand-in for the read-only monitoring service.

    #############################################################
    #  THIS IS AN INSTRUMENT. IT IS NOT PART OF THE HMI, AND IT  #
    #  IS NOT THE MONITORING SERVICE. IT PLAYS ONE.              #
    #############################################################

WHY A DOUBLE AND NOT THE REAL SERVICE. `viz/monitor/service.py` needs rclpy, a
vehicle image and Gazebo, and it lives in WSL; the operator page, its backend
and the browser that presses it live on Windows. More to the point, the states
this page must be photographed in are states of the VEHICLE - a pose that has
stopped arriving, a scan with no distance returns, a service that has died -
and reproducing those on a live stack means arranging a vehicle to stand still
at the right moment. A scripted double reaches every one of them
deterministically, which is the project's standing pattern for exactly this
(hmi/V2A-DESIGN.md section 10; tools/v2a_scenario_double.py beside it).

WHAT IT COPIES, AND FROM WHERE. Every payload key, header and status below is
`viz/DESIGN.md` section 5 and `viz/EVIDENCE_MONITORING.md` section 7, quoted
rather than invented: the same three GET paths, the same JSON key set, the same
`X-Map-*` headers, the same 405 for every other verb, the same raw `int8` cells
gzipped with no image encoder anywhere. The map's geometry is the one that
service actually served - 606 x 410 cells at 0.05 m, origin (-9.145, -4.778) -
so the pane is exercised at the real extent rather than a toy one.

DIVERGENCE RESOLVES TOWARD `viz/`, NEVER TOWARD THIS FILE. Nothing recorded
against this double closes any criterion.

WHAT IT DOES NOT DO. It computes no verdict, classifies no return and says
nothing about safety - it is a source of values, and the ages it reports are
its own steady-clock arithmetic exactly as the real service's are.

Run:
    python hmi/tools/viz_double.py --port 8099 --scenario live
    python hmi/tools/viz_double.py --port 8099 --scenario live \
        --freeze-pose-after 8 --drop-obstacles-after 20
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# ---------------------------------------------------------------------------
# The map. Geometry from viz/EVIDENCE_MONITORING.md section 7.4.
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 606, 410
RESOLUTION_M = 0.05
ORIGIN_X_M, ORIGIN_Y_M = -9.145, -4.778
FREE, OCCUPIED, UNKNOWN = 0, 100, 255          # 0xFF is int8 -1, "unknown"


def build_map() -> bytes:
    """A warehouse-shaped grid: hall walls, two rack rows, an apron.

    Row-major, one byte per cell, row 0 at the map origin - the occupancy-grid
    convention, so the page's own vertical flip is exercised rather than
    accidentally cancelled by a symmetric picture.
    """
    cells = bytearray([UNKNOWN]) * (WIDTH * HEIGHT)

    def fill(x0, y0, x1, y1, value):
        for y in range(max(0, y0), min(HEIGHT, y1)):
            row = y * WIDTH
            for x in range(max(0, x0), min(WIDTH, x1)):
                cells[row + x] = value

    # the hall interior, free
    fill(18, 14, WIDTH - 18, HEIGHT - 14, FREE)
    # its walls
    fill(18, 14, WIDTH - 18, 20, OCCUPIED)
    fill(18, HEIGHT - 20, WIDTH - 18, HEIGHT - 14, OCCUPIED)
    fill(18, 14, 24, HEIGHT - 14, OCCUPIED)
    fill(WIDTH - 24, 14, WIDTH - 18, HEIGHT - 14, OCCUPIED)
    # two rack rows with an aisle between them, and bay gaps
    for bay in range(9):
        x0 = 70 + bay * 52
        fill(x0, 120, x0 + 40, 150, OCCUPIED)
        fill(x0, 250, x0 + 40, 280, OCCUPIED)
    # a loading apron at the left, marked free through the wall line
    fill(24, 180, 70, 230, FREE)
    return bytes(cells)


MAP_CELLS = build_map()

MAP_META = {
    "resolution_m": RESOLUTION_M,
    "width": WIDTH,
    "height": HEIGHT,
    "origin": {"x_m": ORIGIN_X_M, "y_m": ORIGIN_Y_M, "yaw_rad": 0.0},
    "frame": "map",
}


# ---------------------------------------------------------------------------
# The vehicle this double plays.
# ---------------------------------------------------------------------------

class Vehicle:
    """One serial's values, with the ARRIVAL AGE of each, on a steady clock.

    The ages are `time.monotonic()` arithmetic, as the real service's are, and
    for the same reason: a clock supplied by the thing being watched stops when
    the watched thing stops (docs/LESSONS.md 2026-08-06).
    """

    def __init__(self, args):
        self.serial = args.serial
        self.domain_id = args.domain
        self.args = args
        self.started = time.monotonic()
        self.lock = threading.Lock()
        self.map_version = 0 if args.scenario == "nomap" else 1
        self.pose_at = None
        self.scan_at = None
        self.map_at = self.started if self.map_version else None
        self.counts = {"map": self.map_version, "pose": 0, "scan": 0, "tf": 0}
        self.pose = None
        self.scan = None
        self.tick()

    # -- the scripted plant --------------------------------------------------

    def _pose_at_time(self, t):
        """A slow lap of the aisle. The yaw published is the yaw drawn."""
        u = (t * 0.25) % (2.0 * math.pi)
        return {
            "x_m": 8.0 + 5.5 * math.cos(u),
            "y_m": 5.2 + 2.4 * math.sin(u),
            "yaw_rad": math.atan2(2.4 * math.cos(u), -5.5 * math.sin(u)),
            "frame": "map",
        }

    def _scan_at_pose(self, pose, silent):
        """Returns in the three classes the vehicle's own README rules.

        `distance` is the only class that becomes a point. `clear_beyond_range`
        is the sensor MEASURING a clear path - an empty horizon is a
        measurement, not missing data (docs/LESSONS.md 2026-08-06). `invalid`
        is a NaN, a -inf or a range below `range_min`.
        """
        total = 910
        if silent:
            # Every beam beyond range: a real, legitimate reading of an open
            # horizon, and the case that must NOT render as "no obstacles".
            return {"frame": "map", "source_frame": "nav_lidar_link", "placed": True,
                    "points": [],
                    "returns": {"distance": 0, "clear_beyond_range": total - 4,
                                "invalid": 4, "total": total}}
        if self.args.scenario == "unplaced":
            return {"frame": None, "source_frame": "nav_lidar_link", "placed": False,
                    "points": [],
                    "returns": {"distance": 412, "clear_beyond_range": 494,
                                "invalid": 4, "total": total}}
        points = []
        for i in range(-140, 141, 2):
            a = pose["yaw_rad"] + math.radians(i) * 0.75
            rng = 2.2 + 1.6 * math.sin(i * 0.11) + 0.9 * math.cos(i * 0.05)
            points.append([round(pose["x_m"] + rng * math.cos(a), 4),
                           round(pose["y_m"] + rng * math.sin(a), 4)])
        # a rack face, standing still in the world rather than with the vehicle
        for k in range(60):
            points.append([round(2.0 + k * 0.12, 4), 9.35])
        distance = len(points)
        return {"frame": "map", "source_frame": "nav_lidar_link", "placed": True,
                "points": points,
                "returns": {"distance": distance,
                            "clear_beyond_range": total - distance - 4,
                            "invalid": 4, "total": total}}

    def tick(self):
        """Advance the plant. Called by the ticker thread and once at start."""
        now = time.monotonic()
        elapsed = now - self.started
        a = self.args
        pose_frozen = (a.scenario == "standing"
                       or (a.freeze_pose_after is not None
                           and elapsed >= a.freeze_pose_after))
        scan_stopped = (a.stop_scan_after is not None and elapsed >= a.stop_scan_after)
        silent = (a.scenario == "noobstacles"
                  or (a.drop_obstacles_after is not None
                      and elapsed >= a.drop_obstacles_after))
        with self.lock:
            if not pose_frozen or self.pose is None:
                self.pose = self._pose_at_time(elapsed)
                self.pose_at = now
                self.counts["pose"] += 1
            if not scan_stopped or self.scan is None:
                self.scan = self._scan_at_pose(self.pose, silent)
                self.scan_at = now
                self.counts["scan"] += 1
            self.counts["tf"] += 3

    # -- what the face serves ------------------------------------------------

    @staticmethod
    def _age(at, now):
        return None if at is None else round((now - at) * 1000.0, 1)

    def state(self):
        now = time.monotonic()
        with self.lock:
            return {
                "serial": self.serial,
                "domain_id": self.domain_id,
                "node": "viz_monitor_{}".format(self.serial.lower()),
                "pose": self.pose,
                "pose_age_ms": self._age(self.pose_at, now),
                "obstacles": self.scan,
                "obstacles_age_ms": self._age(self.scan_at, now),
                "map_version": self.map_version,
                "map_meta": MAP_META if self.map_version else None,
                "map_age_ms": self._age(self.map_at, now),
                "map_cells": len(MAP_CELLS) if self.map_version else 0,
                "messages_received": dict(self.counts),
                "tf_frames": ["forklift/base_link", "forklift/odom",
                              "nav_lidar_link"],
                "watching_for_s": round(now - self.started, 1),
                "subscriptions": {"/map": 1, "/amcl_pose": 1, "/forklift/scan": 1,
                                  "/tf": 1, "/tf_static": 1},
            }


# ---------------------------------------------------------------------------
# The GET-only face - `viz/monitor/http_face.py`'s shape, copied.
# ---------------------------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    server_version = "amr-agent-viz-double"
    sys_version = ""
    vehicle: Vehicle = None

    def log_message(self, fmt, *args):
        return

    def __getattr__(self, name):
        # Every verb but GET resolves here and is refused before any handler
        # exists and without a byte of any request body being read.
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self):
        body = json.dumps({
            "error": "method not allowed", "allow": "GET",
            "why": "this service is read-only by construction of the process "
                   "and proven by test; not enforced by the middleware "
                   "(viz/DESIGN.md section 2). It has no write surface to "
                   "reach with any verb.",
        }).encode("utf-8")
        self.send_response(405)
        self.send_header("Allow", "GET")
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)
        self.close_connection = True

    def _send(self, code, body, content_type, extra=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, str(value))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, payload, extra=None):
        self._send(code, json.dumps(payload).encode("utf-8"),
                   "application/json", extra)

    def do_GET(self):
        path = self.path.split("?", 1)[0].rstrip("/") or "/"
        parts = [p for p in path.split("/") if p]
        v = self.vehicle
        if parts == ["vehicles"]:
            self._json(200, {
                "serials": [v.serial],
                "vehicles": [{
                    "serial": v.serial, "domain_id": v.domain_id,
                    "node": "viz_monitor_{}".format(v.serial.lower()),
                    "state": "/vehicles/{}/state".format(v.serial),
                    "map": "/vehicles/{}/map".format(v.serial),
                    "cameras": "/vehicles/{}/cameras".format(v.serial),
                }],
                "allocation_table": "(double) agv/forklift/vehicles/allocation.yaml",
            })
            return
        if len(parts) >= 2 and parts[0] == "vehicles":
            if parts[1] != v.serial:
                self._json(404, {"error": "no vehicle {!r} is served".format(parts[1]),
                                 "served": [v.serial]})
                return
            tail = parts[2:]
            if tail == ["state"]:
                self._json(200, v.state())
                return
            if tail == ["map"]:
                if not v.map_version:
                    self._json(503, {"error": "no map has been received from {} yet"
                                              .format(v.serial), "map_version": 0})
                    return
                body = gzip.compress(MAP_CELLS)
                self._send(200, body, "application/octet-stream", {
                    "Content-Encoding": "gzip",
                    "X-Map-Version": v.map_version,
                    "X-Map-Cells": len(MAP_CELLS),
                    "X-Map-Width": WIDTH, "X-Map-Height": HEIGHT,
                    "X-Map-Resolution-M": RESOLUTION_M,
                    "X-Map-Origin-X-M": ORIGIN_X_M,
                    "X-Map-Origin-Y-M": ORIGIN_Y_M,
                    "X-Map-Frame": "map",
                })
                return
            if tail == ["cameras"]:
                self._json(200, {"serial": v.serial, "cameras": []})
                return
        self._json(404, {"error": "no such path", "path": path})


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=8099)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--serial", default="F001")
    p.add_argument("--domain", type=int, default=51)
    p.add_argument("--scenario", default="live",
                   choices=["live", "standing", "noobstacles", "nomap", "unplaced"],
                   help="live: a moving vehicle. standing: the pose never "
                        "advances, which is what AMCL actually does when the "
                        "vehicle stops. noobstacles: every beam beyond range. "
                        "nomap: no map received yet. unplaced: the scan's frame "
                        "cannot be reached through TF")
    p.add_argument("--freeze-pose-after", type=float, default=None,
                   help="seconds after which the pose stops advancing, so one "
                        "run shows the marker go from fresh to last-known")
    p.add_argument("--drop-obstacles-after", type=float, default=None)
    p.add_argument("--stop-scan-after", type=float, default=None,
                   help="seconds after which the scan stops arriving at all - "
                        "the obstacle layer's age then grows without bound")
    p.add_argument("--run-seconds", type=float, default=None)
    args = p.parse_args()

    vehicle = Vehicle(args)
    Handler.vehicle = vehicle
    httpd = ThreadingHTTPServer((args.host, args.port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    print("viz double on http://{}:{}/ serial {} scenario {} - GET only"
          .format(args.host, args.port, args.serial, args.scenario), flush=True)

    deadline = None if args.run_seconds is None else time.monotonic() + args.run_seconds
    try:
        while deadline is None or time.monotonic() < deadline:
            time.sleep(0.05)
            vehicle.tick()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()


if __name__ == "__main__":
    main()
