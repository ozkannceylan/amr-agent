"""One shadow tick: proposers → gate → verdicts. No ROS.

A1 behaviour: every produced Proposal is evaluated; Phase A refuses
all; every pair is a log row. Used by veto_gate_node and by the
offline wiring tests.
"""
from __future__ import annotations

from typing import List, Optional, Sequence

from . import abort as abort_core
from . import pocket as pocket_core
from . import slot as slot_core
from .contract import Proposal
from .gate import Gate, Health, Verdict, healthy
from .pocket import DepthFrame


def propose_all(frame: DepthFrame) -> List[Proposal]:
    """C1 + C2 + C3 on one frame. Missing proposers yield nothing."""
    out: List[Proposal] = []
    refine = pocket_core.propose(frame)
    if refine is not None:
        out.append(refine)
    abort = abort_core.propose(frame)
    if abort is not None:
        out.append(abort)
    out.append(slot_core.propose(frame))
    return out


def shadow_tick(frame: DepthFrame,
                gate: Optional[Gate] = None,
                health: Optional[Health] = None,
                now_s: Optional[float] = None) -> List[Verdict]:
    """Run proposers and the Phase A gate. Always refuse, always log."""
    g = gate if gate is not None else Gate()
    snap = health if health is not None else healthy()
    now = float(frame.sim_stamp if now_s is None else now_s)
    return [g.evaluate(p, now, snap) for p in propose_all(frame)]


def all_refused(verdicts: Sequence[Verdict]) -> bool:
    return all(not v.accepted for v in verdicts)
