"""record_operator.py - the floor and the screen, from the same instant.

WHY THIS IS ONE TOOL AND NOT TWO. The obvious way to show an operator's
view beside the plant is to record two videos and stack them afterwards,
and it does not work: the overhead camera delivers frames at the PLANT's
rate, which on this rig is about half real time and varies, while a
console recorder writes at wall-clock. Ten minutes of run gives two
files of different lengths and no honest way to line them up - and a
side-by-side that drifts is worse than no side-by-side, because it shows
a truck arriving before the screen says it was assigned.

So the camera frame is the clock. Every time an image arrives, the
CURRENT retained status document is rendered beside it and the pair goes
out as one frame. What you see on the right is what the fleet was
saying at the moment the picture on the left was taken.

WHAT THE RIGHT-HAND PANEL IS. fleet_cli.render, the same function
`fleet_cli.py status --watch` prints to a terminal - not a second
rendering that could disagree with it. An operator watching the real
screen sees these characters in this order.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m6/tools/record_operator.py --out run.mp4 --seconds 640
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "fleet")))

import fleet_cli                                     # noqa: E402

TOPIC = "/overhead/image"
STATUS_TOPIC = "fleet/status"
# THE OUTPUT RATE IS AN ARGUMENT BECAUSE THE INPUT RATE IS NOT 10.
# The camera is declared at 10 Hz in SIMULATED time and this rig runs at
# about half real time, so it delivers about four frames a wall second -
# measured 2026-08-24, 403 frames over 100 s. Stamping the file at 10
# makes it play two and a half times too fast, which is fine for a
# fly-past of the floor and useless for a screen somebody has to READ.
# Match --fps to the delivered rate and the video plays at wall-clock.
FPS = 4
# How long a silent camera is tolerated before the take is ended. Ten
# seconds is a hundred frames at FPS: long enough that a slow rig is not
# mistaken for a dead one, short enough that nobody waits on a recorder
# that is never going to write another frame.
STALL_S = 10.0
PANEL_W = 900
FONT_PX = 12
LINE_PX = 15
MARGIN_PX = 10
BG = (18, 20, 24)
FG = (222, 226, 232)
DIM = (120, 128, 140)


def _font():
    """A monospace face, or a refusal that names the problem.

    The panel is a TABLE - fixed-width columns built by fleet_cli's own
    _cell() - and a proportional face turns it into a smear. Better to
    stop than to ship a screen nobody can read.
    """
    from PIL import ImageFont
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                 "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, FONT_PX)
    raise SystemExit(
        "record_operator: no monospace font found. The status panel is a "
        "fixed-width table and a proportional face makes it unreadable.")


def _ffmpeg_binary():
    """Where ffmpeg is, or a refusal that names the problem. This rig
    keeps it in ~/bin, which a login shell has on PATH and a plain
    `bash script.sh` does not - measured 2026-08-23, and it cost a
    ten-minute take that failed silently."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    local = os.path.expanduser("~/bin/ffmpeg")
    if os.path.exists(local):
        return local
    raise SystemExit(
        "record_operator: no ffmpeg on PATH and none at {}.".format(local))


def panel(doc, height, font):
    """The operator's screen as an image, `height` tall.

    DRAWN ONLY WHEN THE DOCUMENT CHANGES - see the cache in Recorder.
    Laying out sixty lines of text with PIL costs more than every other
    thing this tool does per frame put together, and the fleet
    republishes on change and on a 2 s tick, so at 10 fps the same
    picture was being drawn about twenty times over. Measured
    2026-08-24: with it drawn every frame the overhead camera stopped
    delivering 59 s into a 600 s take.
    """
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (PANEL_W, height), BG)
    draw = ImageDraw.Draw(img)
    if doc is None:
        draw.text((MARGIN_PX, MARGIN_PX),
                  "waiting for a retained fleet/status ...", font=font,
                  fill=DIM)
        return img
    rows = int((height - 2 * MARGIN_PX) / LINE_PX)
    lines = fleet_cli.render(doc).split("\n")
    if len(lines) > rows:
        # TRUNCATED AT THE BOTTOM AND IT SAYS SO. Silently dropping the
        # tail would hide exactly the section an operator is looking for
        # - REFUSED and NOT MOVING are last on that screen.
        lines = lines[:rows - 1] + [
            "  ... {} more line(s) - the screen is taller than this "
            "panel".format(len(lines) - rows + 1)]
    for index, line in enumerate(lines):
        draw.text((MARGIN_PX, MARGIN_PX + index * LINE_PX), line,
                  font=font, fill=FG)
    return img


def main():
    ap = argparse.ArgumentParser(
        description="the floor and the operator's screen, side by side")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=640.0)
    ap.add_argument("--fps", type=int, default=FPS,
                    help="output frame rate; match it to the rate the "
                         "camera actually delivers (default {})"
                         .format(FPS))
    ap.add_argument("--host", default=fleet_cli.MQTT_HOST)
    ap.add_argument("--port", type=int, default=fleet_cli.MQTT_PORT)
    args = ap.parse_args()

    import time

    import paho.mqtt.client as mqtt
    import rclpy
    from PIL import Image
    from rclpy.node import Node
    from sensor_msgs.msg import Image as ImageMsg

    font = _font()
    latest = {"doc": None}

    def on_message(_client, _userdata, msg):
        try:
            latest["doc"] = json.loads(msg.payload.decode())
        except ValueError:
            pass

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,
                         client_id="record-operator")
    client.on_message = on_message
    client.connect(args.host, args.port)
    client.subscribe(STATUS_TOPIC, qos=1)
    client.loop_start()

    class Recorder(Node):

        def __init__(self):
            super().__init__("record_operator")
            self._sink = None
            self._frames = 0
            self._panel = None       # the last drawn screen
            self._panel_key = None   # what it was drawn from
            self._t0 = time.monotonic()
            self._last_frame = self._t0
            self.create_subscription(ImageMsg, TOPIC, self._frame, 10)
            # THE DEADLINE NEEDS ITS OWN CLOCK, NOT THE FRAME CALLBACK'S.
            # Checking `--seconds` only when an image arrives means a
            # recorder whose camera goes quiet never checks it again and
            # hangs for ever. Measured 2026-08-24: the overhead camera
            # stopped delivering 59 s into a 600 s take and this process
            # was still sitting there forty minutes later. STALL_S then
            # ends the take rather than writing a file that pretends the
            # run was a minute long - a short video that SAYS it was cut
            # short beats one that quietly claims to be the whole run.
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
                self.get_logger().error(
                    "expected rgb8, got {!r}".format(msg.encoding))
                raise SystemExit(2)
            left = Image.frombytes(
                "RGB", (msg.width, msg.height), bytes(msg.data))
            doc = latest["doc"]
            # THE DOCUMENT'S OWN TIMESTAMP IS THE CACHE KEY. The manager
            # stamps `ts` when it builds the screen, so two documents
            # with one `ts` are one screen and re-drawing is waste.
            key = None if doc is None else doc.get("ts")
            if self._panel is None or key != self._panel_key:
                self._panel = panel(doc, msg.height, font)
                self._panel_key = key
            right = self._panel
            frame = Image.new(
                "RGB", (msg.width + PANEL_W, msg.height), BG)
            frame.paste(left, (0, 0))
            frame.paste(right, (msg.width, 0))
            if self._sink is None:
                self._sink = subprocess.Popen(
                    [_ffmpeg_binary(), "-y", "-loglevel", "error",
                     "-f", "rawvideo", "-pixel_format", "rgb24",
                     "-video_size", "{}x{}".format(*frame.size),
                     "-framerate", str(args.fps), "-i", "-",
                     "-c:v", "libx264", "-preset", "veryfast",
                     "-crf", "23", "-pix_fmt", "yuv420p", args.out],
                    stdin=subprocess.PIPE)
                self.get_logger().info(
                    "recording {}x{} to {}".format(
                        frame.size[0], frame.size[1], args.out))
            try:
                self._sink.stdin.write(frame.tobytes())
            except BrokenPipeError:
                self.get_logger().error("ffmpeg went away")
                raise SystemExit(3)
            self._frames += 1
            self._last_frame = time.monotonic()
            if self._last_frame - self._t0 >= args.seconds:
                raise SystemExit(0)

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
