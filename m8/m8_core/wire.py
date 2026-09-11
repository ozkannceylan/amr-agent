"""JSON wire for Proposal / Verdict / Health. Matches m8_msgs field names.

A1 publishes std_msgs/String because m8_msgs is not a built colcon
package yet. The keys are the .msg fields so a later type swap does
not invent a second contract.
"""
from __future__ import annotations

import json
from typing import Any, Mapping, Optional

from .contract import (
    KIND_ANOMALY,
    KIND_DOCK_ABORT,
    KIND_DOCK_TARGET_REFINE,
    KIND_LOAD_ID,
    KIND_SLOT_STATE,
    KIND_SPEED_REDUCE,
    Evidence,
    LoadEntry,
    PoseDelta,
    Proposal,
    SENSOR_PALLET_CAM,
    SlotRow,
    make_proposal,
    proposal_log_fields,
)
from .gate import Health, Verdict


def proposal_to_msg_dict(proposal: Proposal) -> dict:
    """Flat dict shaped like Proposal.msg."""
    row = {
        "kind": proposal.kind,
        "confidence": float(proposal.confidence),
        "frame_id": proposal.evidence.frame_id,
        "sim_stamp": float(proposal.evidence.sim_stamp),
        "sensor_name": proposal.evidence.sensor_name,
        "ttl_ms": int(proposal.ttl_ms),
        "leg_id": proposal.leg_id or "",
        "dx": 0.0,
        "dy": 0.0,
        "dtheta": 0.0,
        "reason_code": "",
        "slots": [],
        "load_id": "",
        "load_type": "",
        "anomaly_class": "",
        "ceiling_mps": 0.0,
    }
    if proposal.kind == KIND_DOCK_TARGET_REFINE:
        delta = proposal.pose_delta()
        row["dx"], row["dy"], row["dtheta"] = delta.as_tuple()
    elif proposal.kind == KIND_DOCK_ABORT:
        row["reason_code"] = proposal.abort_reason()
    elif proposal.kind == KIND_SLOT_STATE:
        row["slots"] = [{"slot_id": r.slot_id, "state": r.state}
                        for r in proposal.slot_table()]
    elif proposal.kind == KIND_LOAD_ID:
        entry = proposal.load_entry()
        row["load_id"] = entry.load_id
        row["load_type"] = entry.load_type
    elif proposal.kind == KIND_ANOMALY:
        row["anomaly_class"] = proposal.anomaly_class()
    elif proposal.kind == KIND_SPEED_REDUCE:
        row["ceiling_mps"] = proposal.ceiling_mps()
    return row


def proposal_from_msg_dict(data: Mapping[str, Any]) -> Proposal:
    kind = str(data["kind"])
    evidence = Evidence(
        frame_id=str(data["frame_id"]),
        sim_stamp=float(data["sim_stamp"]),
        sensor_name=str(data.get("sensor_name") or SENSOR_PALLET_CAM))
    payload: Any
    if kind == KIND_DOCK_TARGET_REFINE:
        payload = PoseDelta(float(data.get("dx", 0.0)),
                            float(data.get("dy", 0.0)),
                            float(data.get("dtheta", 0.0)))
    elif kind == KIND_DOCK_ABORT:
        payload = str(data.get("reason_code", ""))
    elif kind == KIND_SLOT_STATE:
        payload = tuple(SlotRow(str(r["slot_id"]), str(r["state"]))
                        for r in data.get("slots") or ())
    elif kind == KIND_LOAD_ID:
        payload = LoadEntry(str(data.get("load_id", "")),
                            str(data.get("load_type", "")))
    elif kind == KIND_ANOMALY:
        payload = str(data.get("anomaly_class", ""))
    elif kind == KIND_SPEED_REDUCE:
        payload = float(data.get("ceiling_mps", 0.0))
    else:
        payload = data.get("payload")
    leg = data.get("leg_id") or None
    if leg == "":
        leg = None
    return make_proposal(
        kind, payload, float(data["confidence"]), evidence,
        int(data["ttl_ms"]), leg_id=leg)


def dumps_proposal(proposal: Proposal) -> str:
    return json.dumps(proposal_to_msg_dict(proposal), sort_keys=True)


def loads_proposal(text: str) -> Proposal:
    return proposal_from_msg_dict(json.loads(text))


def dumps_verdict(verdict: Verdict) -> str:
    return json.dumps({
        "accepted": bool(verdict.accepted),
        "reason": verdict.reason,
        "kind": verdict.proposal.kind,
        "frame_id": verdict.proposal.evidence.frame_id,
        "now_s": float(verdict.now_s),
        "checks": dict(verdict.checks),
        "proposal": proposal_to_msg_dict(verdict.proposal),
        "log": verdict.log_row(),
    }, sort_keys=True)


def dumps_health(health: Health) -> str:
    return json.dumps({
        "model_loaded": bool(health.model_loaded),
        "model_warm": bool(health.model_warm),
        "inference_latency_p95_ms": float(health.inference_latency_p95_ms),
        "frame_age_ms": float(health.frame_age_ms),
        "rtf_cost": float(health.rtf_cost),
    }, sort_keys=True)


def loads_health(text: str) -> Health:
    data = json.loads(text)
    return Health(
        model_loaded=bool(data.get("model_loaded", False)),
        model_warm=bool(data.get("model_warm", False)),
        inference_latency_p95_ms=float(
            data.get("inference_latency_p95_ms", float("inf"))),
        frame_age_ms=float(data.get("frame_age_ms", float("inf"))),
        rtf_cost=float(data.get("rtf_cost", float("inf"))))


def scorable_proposal(proposal: Proposal) -> dict:
    """Log row without frames. Alias of the contract view."""
    return proposal_log_fields(proposal)


def decode_depth_32fc1(data: bytes, width: int, height: int,
                       step: Optional[int] = None) -> tuple:
    """Unpack a 32FC1 depth buffer to row-major metres.

    Layout is row-major float32 with an optional row stride — the same
    packing the on-truck depth image uses. rclpy shells pass msg.data
    here. Tests feed a tuple of floats and skip this helper.
    """
    import struct
    if width <= 0 or height <= 0:
        raise ValueError("empty depth image")
    row_step = int(step) if step else width * 4
    rows = []
    for v in range(height):
        off = v * row_step
        row = struct.unpack_from("<{}f".format(width), data, off)
        rows.extend(row)
    if len(rows) != width * height:
        raise ValueError("depth size mismatch")
    return tuple(rows)
