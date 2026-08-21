"""map_panel.py - the warehouse sketch beside the joystick.

DRAWN FROM stations.py, NOT FROM THE SDF. The sketch shows the same
rectangles the router avoids (stations.OBSTACLES) and the same station
poses the world paints; test_stations_sdf.py is what ties both to the
SDF, so the three views cannot drift apart silently.

The panel owns no ROS. hmi_node feeds it pose and /auto/state and
receives mode changes, GO and STOP through three callbacks - the same
direction of dependency the rest of the window already has.
"""
import math
import sys
import os
import tkinter as tk

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import stations                                            # noqa: E402
from status_contract import MODE_AUTO, MODE_TELEOP        # noqa: E402

# ----------------------------- CONFIG -----------------------------
SCALE = 15.0                       # px per metre: 30 x 20 m -> 450 x 300
WIDTH, HEIGHT = 450.0, 300.0
PICK_RADIUS_PX = 12.0
FLOOR, WALL = "#eceff1", "#546e7a"
RACK, STATION, PICKED = "#90a4ae", "#1565c0", "#ef6c00"
ROBOT, ROUTE = "#2e7d32", "#43a047"
# ------------------------------------------------------------------


def world_to_canvas(x, y):
    return ((x - stations.HALL[0]) * SCALE, (stations.HALL[3] - y) * SCALE)


def canvas_to_world(px, py):
    return (px / SCALE + stations.HALL[0], stations.HALL[3] - py / SCALE)


def pick_station(px, py, radius_px=PICK_RADIUS_PX):
    """Nearest station within the radius, else None."""
    best, best_d = None, radius_px
    for sid, s in stations.STATIONS.items():
        sx, sy = world_to_canvas(s["x"], s["y"])
        d = math.hypot(px - sx, py - sy)
        if d <= best_d:
            best, best_d = sid, d
    return best


class MapPanel:

    def __init__(self, parent, on_mode, on_go, on_stop):
        self.on_mode, self.on_go, self.on_stop = on_mode, on_go, on_stop
        self.selected = None
        self.frame = tk.Frame(parent)
        self.canvas = tk.Canvas(self.frame, width=WIDTH, height=HEIGHT,
                                bg=FLOOR, highlightthickness=1,
                                highlightbackground=WALL)
        self.canvas.pack(padx=6, pady=6)
        self._draw_static()
        self.canvas.bind("<Button-1>", self._on_click)

        row = tk.Frame(self.frame)
        row.pack(fill="x", padx=6)
        self.mode_var = tk.StringVar(value=MODE_TELEOP)
        for word, label in ((MODE_TELEOP, "Teleop"), (MODE_AUTO, "Auto")):
            tk.Radiobutton(row, text=label, value=word,
                           variable=self.mode_var,
                           command=self._on_mode).pack(side="left")
        tk.Button(row, text="GO", command=self._on_go).pack(
            side="left", padx=8)
        tk.Button(row, text="STOP", command=on_stop).pack(side="left")
        self.status = tk.Label(self.frame, text="mode teleop", anchor="w")
        self.status.pack(fill="x", padx=6, pady=(2, 6))

        self.robot = self.canvas.create_polygon(0, 0, 0, 0, 0, 0,
                                                fill=ROBOT, outline="")
        self.route_line = None

    def _draw_static(self):
        for _name, xmin, xmax, ymin, ymax in stations.OBSTACLES:
            x0, y0 = world_to_canvas(xmin, ymax)
            x1, y1 = world_to_canvas(xmax, ymin)
            self.canvas.create_rectangle(x0, y0, x1, y1,
                                         fill=RACK, outline="")
        # The dock door: a gap marker on the south wall, x in [4, 8].
        x0, y0 = world_to_canvas(4.0, -9.9)
        x1, y1 = world_to_canvas(8.0, -10.0)
        self.canvas.create_rectangle(x0, y0, x1, y1, fill="#ffb74d",
                                     outline="")
        self.dots, self.labels = {}, {}
        for sid, s in stations.STATIONS.items():
            px, py = world_to_canvas(s["x"], s["y"])
            self.dots[sid] = self.canvas.create_oval(
                px - 7, py - 7, px + 7, py + 7,
                fill=STATION, outline="white", width=2)
            self.labels[sid] = self.canvas.create_text(
                px, py - 14, text=sid, font=("TkDefaultFont", 8, "bold"),
                fill=STATION)

    def _on_click(self, event):
        sid = pick_station(event.x, event.y)
        if sid is None:
            return
        if self.selected in self.dots:
            self.canvas.itemconfigure(self.dots[self.selected], fill=STATION)
        self.selected = sid
        self.canvas.itemconfigure(self.dots[sid], fill=PICKED)

    def _on_mode(self):
        self.on_mode(self.mode_var.get())

    def _on_go(self):
        if self.selected is not None:
            self.on_go(self.selected)

    def update_pose(self, x, y, yaw):
        """Triangle nose = travel direction (the forks: yaw + pi)."""
        head = yaw + math.pi
        pts = []
        for ang, r in ((0.0, 10.0), (2.5, 7.0), (-2.5, 7.0)):
            wx = x + (r / SCALE) * math.cos(head + ang)
            wy = y + (r / SCALE) * math.sin(head + ang)
            pts.extend(world_to_canvas(wx, wy))
        self.canvas.coords(self.robot, *pts)

    def update_auto(self, report):
        """report: parsed /auto/state dict, or None when stale/silent."""
        if report is None:
            self.status.configure(text="auto: no data")
            self._set_route([])
            return
        words = "mode {}  {}  {}".format(
            self.mode_var.get(), report.get("state", "?"),
            report.get("goal") or "")
        note = report.get("note")
        if note:
            words += "  - " + note
        self.status.configure(text=words)
        self._set_route(report.get("route") or [])

    def _set_route(self, points):
        if self.route_line is not None:
            self.canvas.delete(self.route_line)
            self.route_line = None
        if len(points) >= 2:
            flat = []
            for x, y in points:
                flat.extend(world_to_canvas(x, y))
            self.route_line = self.canvas.create_line(
                *flat, fill=ROUTE, width=2, dash=(4, 3))
            self.canvas.tag_raise(self.robot)
