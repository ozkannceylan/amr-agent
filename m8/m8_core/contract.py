"""Proposal contract — validation, monotone rules, TTL.

ARCHITECTURE.md §4. One proposal shape, six kinds. Three standing rules,
enforced here and re-checked in the gate:

1. Monotone-safe. A proposal may only tighten: smaller target delta,
   lower ceiling, abort. Nothing loosens.
2. Expires. Stale is refused. TTL is measured from the evidence sim
   stamp; a proposal is never re-applied after expiry.
3. Logged with its frame. Every proposal carries a frame id. The gate
   writes the log row; this module only makes the row scorable.

NO ROS. NO GROUND TRUTH AS A COMMAND. GT is a score, not an input.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Tuple, Union

# ---------------------------------------------------------------------------
# vocabulary
# ---------------------------------------------------------------------------

KIND_DOCK_TARGET_REFINE = "DOCK_TARGET_REFINE"
KIND_DOCK_ABORT = "DOCK_ABORT"
KIND_SLOT_STATE = "SLOT_STATE"
KIND_LOAD_ID = "LOAD_ID"
KIND_ANOMALY = "ANOMALY"
KIND_SPEED_REDUCE = "SPEED_REDUCE"

KINDS: Tuple[str, ...] = (
    KIND_DOCK_TARGET_REFINE,
    KIND_DOCK_ABORT,
    KIND_SLOT_STATE,
    KIND_LOAD_ID,
    KIND_ANOMALY,
    KIND_SPEED_REDUCE,
)

# Motion-tightening kinds. Reporting kinds (slot / load / anomaly) do not
# loosen or tighten a command; they are tables, not ceilings.
MOTION_KINDS: Tuple[str, ...] = (
    KIND_DOCK_TARGET_REFINE,
    KIND_DOCK_ABORT,
    KIND_SPEED_REDUCE,
)

# C2 staged-fault set (ARCHITECTURE.md §3). `proceed` is never a reason
# and never a kind — it is not an M8 output.
ABORT_REASONS: Tuple[str, ...] = (
    "pallet_absent",
    "pallet_rotated",
    "pallet_shifted",
    "pocket_blocked",
    "stringer_in_path",
)

SLOT_STATES: Tuple[str, ...] = ("empty", "occupied", "blocked")

# R2: one sensor, one evidence label.
SENSOR_PALLET_CAM = "pallet_cam"

# R5: a zero ceiling is a stop, and stopping is the PLC's. The contract
# refuses a non-positive ceiling so the arbiter (Phase E) never sees one.
SPEED_CEILING_FLOOR_MPS = 1e-6


class ContractError(ValueError):
    """A proposal that cannot be constructed or compared."""


# ---------------------------------------------------------------------------
# payload shapes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PoseDelta:
    """Dock-target refine payload: delta vs the tag-derived target."""

    dx: float
    dy: float
    dtheta: float = 0.0

    def hypot_xy(self) -> float:
        return math.hypot(float(self.dx), float(self.dy))

    def as_tuple(self) -> Tuple[float, float, float]:
        return (float(self.dx), float(self.dy), float(self.dtheta))


@dataclass(frozen=True)
class SlotRow:
    slot_id: str
    state: str


@dataclass(frozen=True)
class LoadEntry:
    load_id: str
    load_type: str = ""


@dataclass(frozen=True)
class Evidence:
    """Frame the proposal was scored on. Logged with every row (rule 3)."""

    frame_id: str
    sim_stamp: float
    sensor_name: str = SENSOR_PALLET_CAM


Payload = Union[PoseDelta, str, Tuple[SlotRow, ...], LoadEntry, float]


@dataclass(frozen=True)
class Proposal:
    """The one proposal type. Payload meaning is kind-specific (§4)."""

    kind: str
    payload: Payload
    confidence: float
    evidence: Evidence
    ttl_ms: int
    leg_id: Optional[str] = None
    extra: Mapping[str, Any] = field(default_factory=dict)

    def expiry_stamp(self) -> float:
        """Sim time at which this proposal is no longer applicable."""
        return float(self.evidence.sim_stamp) + (int(self.ttl_ms) / 1000.0)

    def pose_delta(self) -> PoseDelta:
        if not isinstance(self.payload, PoseDelta):
            raise ContractError(
                "kind {} has no pose delta".format(self.kind))
        return self.payload

    def abort_reason(self) -> str:
        if self.kind != KIND_DOCK_ABORT:
            raise ContractError("kind {} is not an abort".format(self.kind))
        return str(self.payload)

    def slot_table(self) -> Tuple[SlotRow, ...]:
        if not isinstance(self.payload, tuple):
            raise ContractError(
                "kind {} has no slot table".format(self.kind))
        return self.payload

    def ceiling_mps(self) -> float:
        if self.kind != KIND_SPEED_REDUCE:
            raise ContractError(
                "kind {} has no speed ceiling".format(self.kind))
        return float(self.payload)

    def anomaly_class(self) -> str:
        if self.kind != KIND_ANOMALY:
            raise ContractError(
                "kind {} has no anomaly class".format(self.kind))
        return str(self.payload)

    def load_entry(self) -> LoadEntry:
        if not isinstance(self.payload, LoadEntry):
            raise ContractError(
                "kind {} has no load entry".format(self.kind))
        return self.payload


# ---------------------------------------------------------------------------
# validation
# ---------------------------------------------------------------------------

def _finite(name: str, value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError("{} is not a number".format(name)) from exc
    if not math.isfinite(number):
        raise ContractError("{} is not finite".format(name))
    return number


def validate_proposal(proposal: Proposal) -> None:
    """Raise ContractError if the proposal is not well-formed."""
    if proposal.kind not in KINDS:
        raise ContractError("unknown kind {!r}".format(proposal.kind))
    if proposal.kind == "PROCEED" or str(proposal.payload).lower() == "proceed":
        raise ContractError("proceed is never an M8 output")

    confidence = _finite("confidence", proposal.confidence)
    if confidence < 0.0 or confidence > 1.0:
        raise ContractError("confidence must be in [0, 1]")

    ttl = int(proposal.ttl_ms)
    if ttl <= 0:
        raise ContractError("ttl_ms must be > 0")

    ev = proposal.evidence
    if not isinstance(ev, Evidence):
        raise ContractError("evidence is required")
    if not ev.frame_id or not str(ev.frame_id).strip():
        raise ContractError("evidence.frame_id is required")
    _finite("evidence.sim_stamp", ev.sim_stamp)
    if ev.sensor_name != SENSOR_PALLET_CAM:
        raise ContractError(
            "evidence.sensor_name must be {!r} (R2), not {!r}".format(
                SENSOR_PALLET_CAM, ev.sensor_name))

    if proposal.kind == KIND_SPEED_REDUCE:
        if not proposal.leg_id or not str(proposal.leg_id).strip():
            raise ContractError("SPEED_REDUCE requires leg_id (R5: one leg)")
        ceiling = _finite("ceiling_mps", proposal.payload)
        if ceiling <= 0.0:
            raise ContractError(
                "SPEED_REDUCE ceiling must be > 0 (R5: zero is a stop)")
        if not isinstance(proposal.payload, (int, float)):
            raise ContractError("SPEED_REDUCE payload is a ceiling in m/s")

    elif proposal.kind == KIND_DOCK_TARGET_REFINE:
        if not isinstance(proposal.payload, PoseDelta):
            raise ContractError(
                "DOCK_TARGET_REFINE payload is a PoseDelta")
        _finite("dx", proposal.payload.dx)
        _finite("dy", proposal.payload.dy)
        _finite("dtheta", proposal.payload.dtheta)

    elif proposal.kind == KIND_DOCK_ABORT:
        reason = str(proposal.payload)
        if reason not in ABORT_REASONS:
            raise ContractError(
                "unknown abort reason {!r}".format(reason))

    elif proposal.kind == KIND_SLOT_STATE:
        rows = proposal.payload
        if not isinstance(rows, tuple) or not rows:
            raise ContractError("SLOT_STATE payload is a non-empty slot table")
        seen = set()
        for row in rows:
            if not isinstance(row, SlotRow):
                raise ContractError("SLOT_STATE rows are SlotRow")
            if not row.slot_id or not str(row.slot_id).strip():
                raise ContractError("slot_id is required")
            if row.slot_id in seen:
                raise ContractError(
                    "duplicate slot_id {!r}".format(row.slot_id))
            seen.add(row.slot_id)
            if row.state not in SLOT_STATES:
                raise ContractError(
                    "unknown slot state {!r}".format(row.state))

    elif proposal.kind == KIND_LOAD_ID:
        if not isinstance(proposal.payload, LoadEntry):
            raise ContractError("LOAD_ID payload is a LoadEntry")
        if not proposal.payload.load_id:
            raise ContractError("load_id is required")

    elif proposal.kind == KIND_ANOMALY:
        if not str(proposal.payload).strip():
            raise ContractError("ANOMALY payload is a class name")

    if proposal.kind != KIND_SPEED_REDUCE and proposal.leg_id:
        # leg_id is meaningful only for the R5 ceiling. A stray id on
        # another kind is not a tightening; it is a confused contract.
        raise ContractError(
            "leg_id is only valid on SPEED_REDUCE (R5)")


def make_proposal(
        kind: str,
        payload: Payload,
        confidence: float,
        evidence: Evidence,
        ttl_ms: int,
        leg_id: Optional[str] = None,
        extra: Optional[Mapping[str, Any]] = None) -> Proposal:
    """Construct and validate. The only public builder."""
    proposal = Proposal(
        kind=kind,
        payload=payload,
        confidence=float(confidence),
        evidence=evidence,
        ttl_ms=int(ttl_ms),
        leg_id=leg_id,
        extra=dict(extra or {}))
    validate_proposal(proposal)
    return proposal


# ---------------------------------------------------------------------------
# TTL
# ---------------------------------------------------------------------------

def is_expired(proposal: Proposal, now_s: float) -> bool:
    """True when `now_s` is at or past the proposal's expiry stamp.

    Equality is expired: a proposal whose TTL has just elapsed is stale,
    not still live. Never re-applied after expiry (§4 rule 2).
    """
    now = _finite("now_s", now_s)
    return now >= proposal.expiry_stamp()


def remaining_ttl_ms(proposal: Proposal, now_s: float) -> int:
    """Milliseconds still to live. Zero once expired (never negative).

    Elapsed time is computed in milliseconds so a 1 ms remainder is not
    lost to `0.001 * 1000` floating-point noise.
    """
    if is_expired(proposal, now_s):
        return 0
    elapsed_ms = (float(now_s) - float(proposal.evidence.sim_stamp)) * 1000.0
    left = int(proposal.ttl_ms) - elapsed_ms
    if left <= 0:
        return 0
    return int(math.floor(left + 1e-9))


# ---------------------------------------------------------------------------
# monotone
# ---------------------------------------------------------------------------

def _same_leg(previous: Proposal, candidate: Proposal) -> bool:
    return (previous.leg_id or "") == (candidate.leg_id or "")


def is_monotone(previous: Optional[Proposal],
                candidate: Proposal) -> bool:
    """True when `candidate` does not loosen `previous`.

    Reporting kinds (slot / load / anomaly) are not command loosenings.
    A first proposal (previous is None) is monotone by definition.
    Different motion kinds do not compare: a SPEED_REDUCE cannot loosen
    a DOCK_TARGET_REFINE, and an abort is always a tightening.
    """
    validate_proposal(candidate)
    if previous is None:
        return True
    validate_proposal(previous)

    if candidate.kind == KIND_DOCK_ABORT:
        return True

    if candidate.kind not in MOTION_KINDS:
        return True

    if previous.kind != candidate.kind:
        # A refine after an abort would be a loosening of the abort.
        if previous.kind == KIND_DOCK_ABORT:
            return False
        return True

    if candidate.kind == KIND_DOCK_TARGET_REFINE:
        prev = previous.pose_delta()
        cand = candidate.pose_delta()
        if cand.hypot_xy() > prev.hypot_xy() + 1e-12:
            return False
        if abs(cand.dtheta) > abs(prev.dtheta) + 1e-12:
            return False
        return True

    if candidate.kind == KIND_SPEED_REDUCE:
        if not _same_leg(previous, candidate):
            # R5: one leg. A ceiling on another leg is a different
            # proposal, not a raise of this one.
            return True
        return candidate.ceiling_mps() <= previous.ceiling_mps() + 1e-12

    return True


def monotone_violations(previous: Optional[Proposal],
                        candidate: Proposal) -> Tuple[str, ...]:
    """Named reasons when `is_monotone` is false. Empty when ok."""
    if is_monotone(previous, candidate):
        return ()
    if previous is not None and previous.kind == KIND_DOCK_ABORT:
        return ("abort_is_terminal",)
    if candidate.kind == KIND_DOCK_TARGET_REFINE:
        return ("refine_delta_grew",)
    if candidate.kind == KIND_SPEED_REDUCE:
        return ("ceiling_raised",)
    return ("not_monotone",)


def proposal_log_fields(proposal: Proposal) -> dict:
    """JSON-scorable view. No frames, no images, no GT command."""
    payload: Any
    if isinstance(proposal.payload, PoseDelta):
        payload = {"dx": proposal.payload.dx,
                   "dy": proposal.payload.dy,
                   "dtheta": proposal.payload.dtheta,
                   "hypot_xy": proposal.payload.hypot_xy()}
    elif isinstance(proposal.payload, tuple):
        payload = [{"slot_id": r.slot_id, "state": r.state}
                   for r in proposal.payload]
    elif isinstance(proposal.payload, LoadEntry):
        payload = {"load_id": proposal.payload.load_id,
                   "load_type": proposal.payload.load_type}
    else:
        payload = proposal.payload
    return {
        "kind": proposal.kind,
        "payload": payload,
        "confidence": proposal.confidence,
        "ttl_ms": proposal.ttl_ms,
        "leg_id": proposal.leg_id,
        "evidence": {
            "frame_id": proposal.evidence.frame_id,
            "sim_stamp": proposal.evidence.sim_stamp,
            "sensor_name": proposal.evidence.sensor_name,
        },
    }
