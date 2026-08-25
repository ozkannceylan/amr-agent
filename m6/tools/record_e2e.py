"""record_e2e.py - one film that explains the cell: the floor, the
operator's screen, and the VDA 5050 wire, side by side.

WHY A THIRD RECORDER. record_overhead shows trucks and record_operator
shows the screen beside them - but neither shows the PROTOCOL, and the
protocol is the point of M6: a task typed at the operator console
becomes an order on uagv/v2/..., the truck answers with states, the
pick and the drop report themselves, and leg 2 follows the report. This
tool puts that conversation ON the frame, as one readable line per
event, so a viewer who has never seen the repo can watch a transport
happen end to end.

THE WIRE PANE IS A STORY, NOT A LOG. Four trucks publish state at 2 s
periods - forty lines a minute of "still driving" would scroll the one
line that matters off the screen. So the tap is edge-triggered: a line
is written when an order or instantAction goes out, when a truck's
orderId changes, when it arrives (nodeStates empties), when a pick or
drop changes status, when errors[] carries something, and when a
connection state lands. Silence in between IS the story - the truck is
driving.

Same skeleton as record_operator (the camera frame is the clock; the
panels are cached and redrawn only when their content changes - drawing
sixty PIL lines per frame is what once cost the camera its delivery).

Usage (after sourcing ROS and with the stack up):
  python3 m6/tools/record_e2e.py --out e2e.mp4 --seconds 560
"""
import argparse
import collections
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import fleet_cli                                     # noqa: E402
from record_operator import (BG, DIM, FG, LINE_PX, MARGIN_PX,
                             PANEL_W, RateClock, _ffmpeg_binary,
                             _font, panel)           # noqa: E402

TOPIC = "/overhead/image"
STATUS_TOPIC = "fleet/status"
SUBMIT_TOPIC = "fleet/task/submit"
VDA_WILDCARD = "uagv/v2/+/+/#"
FPS = 4
STALL_S = 10.0
WIRE_ROWS = 16           # the bottom pane; a header plus this many lines
TITLE_S = 9.0            # how long the opening card stays up
STATUS_H = 452           # top pane height; the rest is the wire's


def wire_line(topic, body, clock=""):
    """One readable sentence for one MQTT message, or None to stay
    quiet. Pure - (topic, parsed payload) in, string out - so the story
    the film tells is testable without a broker or a camera."""
    parts = topic.split("/")
    if topic == SUBMIT_TOPIC and isinstance(body, dict):
        return "{} >> TASK {}  {} -> {}   (operator console)".format(
            clock, body.get("taskId", "?"), body.get("from", "?"),
            body.get("to", "?"))
    if len(parts) != 5 or not isinstance(body, dict):
        return None
    vid, name = parts[3], parts[4]
    if name == "order":
        nodes = body.get("nodes") or []
        base = sum(1 for n in nodes if isinstance(n, dict)
                   and n.get("released"))
        act = ""
        if nodes and isinstance(nodes[-1], dict):
            acts = nodes[-1].get("actions") or []
            if acts and isinstance(acts[0], dict):
                act = " +" + str(acts[0].get("actionType", ""))
        upd = body.get("orderUpdateId", 0)
        head = "ORDER {}".format(str(body.get("orderId", "?"))[:11]) \
            if not upd else "EXTEND upd {}".format(upd)
        return "{} >> {}  {}  {} nodes ({} base){}".format(
            clock, vid, head, len(nodes), base, act)
    if name == "instantActions":
        kinds = [a.get("actionType", "?")
                 for a in body.get("actions", []) if isinstance(a, dict)]
        return "{} >> {}  {}".format(clock, vid,
                                     ", ".join(kinds).upper() or "?")
    if name == "connection":
        return "{} << {}  {}".format(
            clock, vid, body.get("connectionState", "?"))
    return None      # plain states are StateTap's business, not this one


class StateTap:
    """The edge detector over one vehicle's state stream: a line per
    CHANGE, silence while it simply drives."""

    def __init__(self, vid):
        self.vid = vid
        self.order_id = None
        self.had_nodes = False
        self.actions = {}

    def lines(self, body, clock=""):
        out = []
        oid = body.get("orderId") or ""
        nodes = body.get("nodeStates")
        nodes = nodes if isinstance(nodes, list) else []
        if oid and oid != self.order_id:
            self.order_id, self.had_nodes = oid, bool(nodes)
        elif oid and self.had_nodes and not nodes:
            self.had_nodes = False
            out.append("{} << {}  arrived ({})".format(
                clock, self.vid, oid[:11]))
        elif nodes:
            self.had_nodes = True
        for act in body.get("actionStates") or []:
            if not isinstance(act, dict):
                continue
            key = act.get("actionId", "?")
            status = act.get("actionStatus", "?")
            if self.actions.get(key) != status:
                self.actions[key] = status
                kind = act.get("actionType", key)
                if kind in ("pick", "drop") or status == "FAILED":
                    out.append("{} << {}  {} {}".format(
                        clock, self.vid, kind, status))
        for err in body.get("errors") or []:
            if isinstance(err, dict) and err.get("errorType"):
                out.append("{} << {}  ! {}: {}".format(
                    clock, self.vid, err["errorType"],
                    str(err.get("errorDescription", ""))[:44]))
        return out


def main():
    ap = argparse.ArgumentParser(
        description="floor + screen + the VDA 5050 wire, one film")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=560.0)
    ap.add_argument("--fps", type=int, default=FPS)
    ap.add_argument("--host", default=fleet_cli.MQTT_HOST)
    ap.add_argument("--port", type=int, default=fleet_cli.MQTT_PORT)
    args = ap.parse_args()

    import queue as qmod
    import subprocess

    import paho.mqtt.client as mqtt
    import rclpy
    from PIL import Image, ImageDraw, ImageFont
    from rclpy.node import Node
    from sensor_msgs.msg import Image as ImageMsg

    font = _font()
    big = mid = None
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"):
        if os.path.exists(path):
            big = ImageFont.truetype(path, 30)
            mid = ImageFont.truetype(path, 19)
            break
    latest = {"doc": None}
    inbox = qmod.Queue()

    def on_message(_c, _u, msg):
        inbox.put((msg.topic, msg.payload))

    def on_connect(client, _u, _f, _rc, _p=None):
        # In on_connect, so a broker bounce cannot silently orphan the
        # tap - the frozen-panel lesson of 2026-08-25, applied from
        # birth this time.
        client.subscribe([(STATUS_TOPIC, 1), (SUBMIT_TOPIC, 1),
                          (VDA_WILDCARD, 0)])

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="record-e2e-{}".format(os.getpid()))
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(args.host, args.port)
    client.loop_start()

    wire = collections.deque(maxlen=WIRE_ROWS)
    taps = {}
    wire_rev = [0]

    def drain_wire():
        while True:
            try:
                topic, payload = inbox.get_nowait()
            except qmod.Empty:
                return
            try:
                body = json.loads(payload.decode())
            except (ValueError, UnicodeDecodeError):
                continue
            clock = time.strftime("%H:%M:%S")
            if topic == STATUS_TOPIC:
                latest["doc"] = body
                continue
            if topic.endswith("/state"):
                vid = topic.split("/")[3]
                tap = taps.setdefault(vid, StateTap(vid))
                for line in tap.lines(body, clock):
                    wire.append(line)
                    wire_rev[0] += 1
                continue
            line = wire_line(topic, body, clock)
            if line:
                wire.append(line)
                wire_rev[0] += 1

    def wire_panel(height):
        img = Image.new("RGB", (PANEL_W, height), BG)
        draw = ImageDraw.Draw(img)
        draw.text((MARGIN_PX, 4),
                  "VDA 5050 wire  (uagv/v2/amragent/<truck>/...)   "
                  ">> to truck   << from truck",
                  font=font, fill=DIM)
        for i, line in enumerate(wire):
            draw.text((MARGIN_PX, 4 + (i + 1) * LINE_PX), line,
                      font=font, fill=FG)
        return img

    class Recorder(Node):

        def __init__(self):
            super().__init__("record_e2e")
            self._sink = None
            self._frames = 0
            self._status_img = None
            self._status_key = None
            self._wire_img = None
            self._wire_key = None
            self._rate_clock = RateClock()
            self._t0 = time.monotonic()
            self._last_frame = self._t0
            self.create_subscription(ImageMsg, TOPIC, self._frame, 10)
            self.create_timer(1.0, self._tick)

        def _tick(self):
            now = time.monotonic()
            if now - self._t0 >= args.seconds:
                raise SystemExit(0)
            if self._frames and now - self._last_frame >= STALL_S:
                self.get_logger().error(
                    "no camera frame for {:.0f} s after {} frames - "
                    "ending the take".format(STALL_S, self._frames))
                raise SystemExit(4)

        def _frame(self, msg):
            if msg.encoding != "rgb8":
                raise SystemExit(2)
            drain_wire()
            left = Image.frombytes(
                "RGB", (msg.width, msg.height), bytes(msg.data))
            doc = latest["doc"]
            key = None if doc is None else doc.get("ts")
            if self._status_img is None or key != self._status_key:
                self._status_img = panel(doc, STATUS_H, font)
                self._status_key = key
            if self._wire_img is None or wire_rev[0] != self._wire_key:
                self._wire_img = wire_panel(msg.height - STATUS_H)
                self._wire_key = wire_rev[0]
            frame = Image.new(
                "RGB", (msg.width + PANEL_W, msg.height), BG)
            frame.paste(left, (0, 0))
            frame.paste(self._status_img, (msg.width, 0))
            frame.paste(self._wire_img, (msg.width, STATUS_H))
            draw = ImageDraw.Draw(frame)
            draw.line((msg.width, STATUS_H, msg.width + PANEL_W,
                       STATUS_H), fill=DIM)
            wall = time.time()
            self._rate_clock.note(
                msg.header.stamp.sec + msg.header.stamp.nanosec * 1e-9,
                wall)
            strip = "{} - wall {}".format(
                self._rate_clock.line(),
                time.strftime("%H:%M:%S", time.localtime(wall)))
            draw.rectangle((0, 0, 8 + 8 * len(strip), 20), fill=BG)
            draw.text((6, 3), strip, font=font, fill=FG)
            if self._frames < args.fps * TITLE_S and big is not None:
                draw.rectangle((40, msg.height - 214, 940,
                                msg.height - 56), fill=(28, 30, 36))
                draw.text((60, msg.height - 200),
                          "Milestone 6 - VDA 5050 fleet management",
                          font=big, fill=(240, 244, 250))
                draw.text((60, msg.height - 156),
                          "4 forklifts, 12 stations - tasks typed at "
                          "the operator console", font=mid, fill=FG)
                draw.text((60, msg.height - 128),
                          "orders, states and the pick/drop cycle live "
                          "on the MQTT wire (bottom right)",
                          font=mid, fill=FG)
                draw.text((60, msg.height - 100),
                          "Gazebo simulation - virtual F-PLC per truck "
                          "- plays at the warehouse's TRUE speed",
                          font=mid, fill=DIM)
            if self._sink is None:
                self._sink = subprocess.Popen(
                    [_ffmpeg_binary(), "-y", "-loglevel", "error",
                     "-f", "rawvideo", "-pixel_format", "rgb24",
                     "-video_size", "{}x{}".format(*frame.size),
                     "-framerate", str(args.fps), "-i", "-",
                     "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", "23", "-pix_fmt", "yuv420p", args.out],
                    stdin=subprocess.PIPE)
                self.get_logger().info("recording {}x{} to {}".format(
                    frame.size[0], frame.size[1], args.out))
            try:
                self._sink.stdin.write(frame.tobytes())
            except BrokenPipeError:
                raise SystemExit(3)
            self._frames += 1
            self._last_frame = time.monotonic()

        def close(self):
            if self._sink is not None:
                self._sink.stdin.close()
                self._sink.wait()
            print("wrote {} frames ({:.1f} s at {} fps) to {}".format(
                self._frames, self._frames / float(args.fps), args.fps,
                args.out))

    rclpy.init()
    node = Recorder()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()
        client.loop_stop()
        client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
