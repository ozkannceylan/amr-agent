"""Classical C3 shelf-slot state. Reporting only.

ARCHITECTURE.md §3: empty / occupied / blocked. The vehicle does not
act on this table. A1 publishes a SLOT_STATE Proposal; Phase D is when
it reaches VDA information[].
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

from .contract import (
    KIND_SLOT_STATE,
    Evidence,
    SENSOR_PALLET_CAM,
    SlotRow,
    make_proposal,
)
from .pocket import DepthFrame

DEFAULT_TTL_MS = 400
DEFAULT_SLOT_IDS = ("S5-L", "S5-C", "S5-R")


@dataclass(frozen=True)
class SlotWindow:
    slot_id: str
    u0: float   # fraction of width
    u1: float
    v0: float
    v1: float


def default_windows() -> Tuple[SlotWindow, ...]:
    """Three equal columns. Plant geometry is E4's job."""
    ids = DEFAULT_SLOT_IDS
    return tuple(
        SlotWindow(ids[i], i / 3.0, (i + 1) / 3.0, 0.25, 0.75)
        for i in range(3))


def _window_depths(frame: DepthFrame, win: SlotWindow) -> Tuple[float, ...]:
    u0 = int(win.u0 * frame.width)
    u1 = max(u0 + 1, int(win.u1 * frame.width))
    v0 = int(win.v0 * frame.height)
    v1 = max(v0 + 1, int(win.v1 * frame.height))
    vals = []
    for v in range(v0, v1):
        for u in range(u0, u1):
            z = frame.at(u, v)
            if z is not None:
                vals.append(z)
    return tuple(vals)


def classify_window(frame: DepthFrame, win: SlotWindow,
                    empty_z: float = 2.4,
                    occupied_z: float = 1.8) -> str:
    """empty = far/clear, occupied = a face in band, blocked = else."""
    vals = _window_depths(frame, win)
    need = 0.08 * (win.u1 - win.u0) * (win.v1 - win.v0) * frame.width * frame.height
    if len(vals) < max(4, need):
        return "blocked"
    ordered = sorted(vals)
    med = ordered[len(ordered) // 2]
    if med >= empty_z:
        return "empty"
    if med <= occupied_z:
        return "occupied"
    return "blocked"


def propose(frame: DepthFrame,
            windows: Sequence[SlotWindow] = (),
            ttl_ms: int = DEFAULT_TTL_MS,
            confidence: float = 0.7) -> object:
    wins = tuple(windows) if windows else default_windows()
    rows = tuple(SlotRow(w.slot_id, classify_window(frame, w)) for w in wins)
    return make_proposal(
        KIND_SLOT_STATE, rows, float(confidence),
        Evidence(frame.frame_id, frame.sim_stamp, SENSOR_PALLET_CAM),
        int(ttl_ms))
