"""Shared path + depth-frame builder. No rclpy.

The shells call `frame_from_buffer` after they have unpacked a
sensor_msgs/Image. Tests call it with a tuple of floats.
"""
from __future__ import annotations

import os
import sys
from typing import Optional, Sequence

_HERE = os.path.dirname(os.path.abspath(__file__))
_M8 = os.path.normpath(os.path.join(_HERE, os.pardir))
if _M8 not in sys.path:
    sys.path.insert(0, _M8)

from m8_core.pocket import DEFAULT_FX, DEFAULT_FY, DepthFrame  # noqa: E402


def frame_from_buffer(depths: Sequence[float],
                      width: int,
                      height: int,
                      sim_stamp: float,
                      frame_id: str = "pallet_cam_optical",
                      fx: float = DEFAULT_FX,
                      fy: float = DEFAULT_FY,
                      cx: Optional[float] = None,
                      cy: Optional[float] = None) -> DepthFrame:
    buf = tuple(float(z) for z in depths)
    if len(buf) != width * height:
        raise ValueError("depth length {} != {}x{}".format(
            len(buf), width, height))
    return DepthFrame(
        width=width, height=height, depths=buf,
        fx=float(fx), fy=float(fy),
        cx=float(cx if cx is not None else width / 2.0),
        cy=float(cy if cy is not None else height / 2.0),
        frame_id=str(frame_id),
        sim_stamp=float(sim_stamp))
