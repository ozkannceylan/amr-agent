#!/usr/bin/env python3
"""film_record.py - write a ROS Image topic to an mp4 until SIGINT.

    python3 m5_ver3/tools/film_record.py --topic /film/overhead --out out.mp4

THREE ONE-NUMBER SIDECARS GO BESIDE THE MP4, and the cut cannot place
this file on the film's timeline without all three:

    <out>.t0   the FIRST frame's wall time
    <out>.t1   the LAST frame's wall time
    <out>.n    the frames written

Every received frame is written into a container fixed at `fps`, and
the film cameras publish on the SIM clock - so n frames are n/fps of
video however long the wall took, and (n - 1)/fps over (t1 - t0) is
this recording's own sim-per-wall rate. film_core.clock turns those
three into the mapping every trim goes through; without them a wall
bound would be trimmed as if the rig had kept up with the wall.
"""
import argparse
import os
import signal
import time

import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


def sidecar(path, text):
    """One number beside the mp4, one file, newline-terminated."""
    with open(path, "w", encoding="utf-8") as side:
        side.write(text + "\n")


def to_bgr(msg):
    n = np.frombuffer(msg.data, dtype=np.uint8)
    if msg.encoding.startswith("rgb"):
        img = n.reshape(msg.height, msg.width, 3)
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if msg.encoding.startswith("bgr"):
        return n.reshape(msg.height, msg.width, 3)
    raise RuntimeError("unsupported encoding {}".format(msg.encoding))


class Recorder(Node):
    def __init__(self, topic, path, seconds):
        super().__init__("m5v3_film_record")
        self.set_parameters([rclpy.parameter.Parameter(
            "use_sim_time", rclpy.Parameter.Type.BOOL, True)])
        self.writer = None
        self.path = path
        self.frames = 0
        self.last_wall = None
        self.deadline = None if seconds is None else time.time() + seconds
        self.stop = False
        self.create_subscription(Image, topic, self._on, 10)

    def _on(self, msg):
        if self.stop:
            return
        frame = to_bgr(msg)
        if self.writer is None:
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            self.writer = cv2.VideoWriter(self.path, fourcc, 15.0, (w, h))
            # First-frame wall time, beside the mp4: the four film
            # cameras start at four different times, and the cut lands
            # a wall-clock segment bound in this file by measuring
            # from exactly this number. Written HERE rather than at
            # close because film_run.py's warmup watches for it to
            # know the camera is alive.
            sidecar(self.path + ".t0", "{:.6f}".format(time.time()))
            print("first frame {:.3f} ({:d}x{:d})".format(
                time.time(), w, h))
        self.writer.write(frame)
        self.frames += 1
        self.last_wall = time.time()
        if self.deadline is not None and time.time() >= self.deadline:
            self.stop = True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--seconds", type=float, default=0.0)
    args = parser.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".",
                exist_ok=True)
    rclpy.init()
    node = Recorder(args.topic, args.out,
                    None if args.seconds <= 0 else args.seconds)

    def _sig(_signum, _frame):
        node.stop = True

    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)
    while rclpy.ok() and not node.stop:
        rclpy.spin_once(node, timeout_sec=0.1)
    if node.writer is not None:
        node.writer.release()
        # The other two, at close, because only now are they known:
        # the last frame's wall time and how many frames the container
        # holds. t0 alone says WHEN this file starts; with t1 and n it
        # also says how fast its clock ran and how much footage there
        # is, which is what the cut needs to refuse a bound past the
        # end instead of letting ffmpeg clamp it.
        sidecar(args.out + ".t1", "{:.6f}".format(node.last_wall))
        sidecar(args.out + ".n", "{:d}".format(node.frames))
    print("frames    {}".format(node.frames))
    print("wrote     {}".format(args.out))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if node.frames else 1


if __name__ == "__main__":
    raise SystemExit(main())
