#!/usr/bin/env python3
"""film_record.py - write a ROS Image topic to an mp4 until SIGINT.

    python3 m5_ver3/tools/film_record.py --topic /film/overhead --out out.mp4
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
        self.writer.write(frame)
        self.frames += 1
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
    print("frames    {}".format(node.frames))
    print("wrote     {}".format(args.out))
    node.destroy_node()
    rclpy.shutdown()
    return 0 if node.frames else 1


if __name__ == "__main__":
    raise SystemExit(main())
