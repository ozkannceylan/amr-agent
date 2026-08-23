"""record_overhead.py - the overhead camera into an mp4. WSL side.

WHY NOT gz sim's OWN RECORDER: it lives in the GUI, and the GUI costs
0.137 of integrated real-time factor (measured 2026-08-23) on a rig
where the floor of that number is what decides whether sixteen
gpu_lidars keep delivering. The main take therefore runs --headless and
this script is its camera operator.

IT WRITES WHAT IT WAS GIVEN AND NOTHING ELSE. No overlay, no timestamp
burn-in, no re-scaling: an artefact in this file is an artefact nobody
can tell from an artefact in the simulation. The frame that arrives is
the frame that lands in the file.

A DROPPED FRAME IS NOT SMOOTHED OVER. ffmpeg is fed at the rate frames
arrive and the output is stamped at the sensor's own 20 Hz, so a run
whose real-time factor collapsed produces a SHORTER video, not a
smooth one. That is the honest direction: the recording should look
like what the rig did.

Usage (after sourcing /opt/ros/jazzy/setup.bash):
  python3 m6/tools/record_overhead.py --out /tmp/m6-fleet.mp4 --seconds 620
"""
import argparse
import subprocess
import sys

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image

TOPIC = "/overhead/image"
FPS = 20


def ffmpeg(path, width, height, fps=FPS):
    """A raw-frame sink. -y because a re-take overwrites its own take."""
    return subprocess.Popen(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "rawvideo", "-pixel_format", "rgb24",
         "-video_size", "{}x{}".format(width, height),
         "-framerate", str(fps), "-i", "-",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
         "-pix_fmt", "yuv420p", path],
        stdin=subprocess.PIPE)


class Recorder(Node):

    def __init__(self, path, seconds):
        super().__init__("record_overhead")
        self._path, self._seconds = path, seconds
        self._sink = None
        self._frames = 0
        self._t0 = None
        self.create_subscription(Image, TOPIC, self._frame, 10)

    def _frame(self, msg):
        if msg.encoding != "rgb8":
            self.get_logger().error(
                "expected rgb8, got {!r} - the camera's <format> and this "
                "script disagree".format(msg.encoding))
            raise SystemExit(2)
        if self._sink is None:
            self._sink = ffmpeg(self._path, msg.width, msg.height)
            self._t0 = self.get_clock().now()
            self.get_logger().info(
                "recording {}x{} to {}".format(
                    msg.width, msg.height, self._path))
        try:
            self._sink.stdin.write(bytes(msg.data))
        except BrokenPipeError:
            self.get_logger().error("ffmpeg went away")
            raise SystemExit(3)
        self._frames += 1
        elapsed = (self.get_clock().now() - self._t0).nanoseconds / 1e9
        if elapsed >= self._seconds:
            raise SystemExit(0)

    def close(self):
        if self._sink is not None:
            self._sink.stdin.close()
            self._sink.wait()
        print("wrote {} frames ({:.1f} s at {} fps) to {}".format(
            self._frames, self._frames / float(FPS), FPS, self._path))


def main():
    ap = argparse.ArgumentParser(description="the overhead camera to mp4")
    ap.add_argument("--out", required=True)
    ap.add_argument("--seconds", type=float, default=620.0)
    args = ap.parse_args()
    rclpy.init()
    node = Recorder(args.out, args.seconds)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node.close()
        node.destroy_node()
        rclpy.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
