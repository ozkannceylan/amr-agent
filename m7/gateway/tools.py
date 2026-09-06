"""tools.py — Phase 1 MCP tool surface and their input schemas.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function.

THE FOUR TOOLS ARE THE ONES IN ARCHITECTURE.md §3. cancel, vehicle
addressing, and pause/charge are not tools in Phase 1.
"""
from __future__ import annotations

TOOL_NAMES = (
    "get_fleet_status",
    "list_stations",
    "propose_transport",
    "get_proposal",
)

EMPTY_OBJECT = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}

PROPOSE_INPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["from", "to", "reason", "idempotency_key"],
    "properties": {
        "from": {"type": "string", "description": "Pickup station id"},
        "to": {"type": "string", "description": "Drop-off station id"},
        "reason": {
            "type": "string",
            "description": "Model text; stored, never parsed by the gate",
        },
        "idempotency_key": {"type": "string", "minLength": 1},
    },
}

GET_PROPOSAL_INPUT = {
    "type": "object",
    "additionalProperties": False,
    "required": ["proposal_id"],
    "properties": {
        "proposal_id": {"type": "string", "minLength": 1},
    },
}

TOOLS = (
    {
        "name": "get_fleet_status",
        "description": (
            "Read the retained fleet/status document the manager "
            "publishes, plus the document age. No gate."
        ),
        "inputSchema": EMPTY_OBJECT,
    },
    {
        "name": "list_stations",
        "description": (
            "Station table the fleet already uses (the Phase 1 "
            "allowlist). No gate."
        ),
        "inputSchema": EMPTY_OBJECT,
    },
    {
        "name": "propose_transport",
        "description": (
            "Propose one FROM→TO transport. Schema and policy run "
            "first; a human must approve before fleet/task/submit "
            "is published."
        ),
        "inputSchema": PROPOSE_INPUT,
    },
    {
        "name": "get_proposal",
        "description": (
            "Read one proposal from the gateway's pending / decided "
            "set. No gate."
        ),
        "inputSchema": GET_PROPOSAL_INPUT,
    },
)


def dispatch(gateway, name: str, arguments: dict | None):
    """Call one of the four tools. Unknown names raise ValueError."""
    args = arguments or {}
    if name == "get_fleet_status":
        return gateway.get_fleet_status()
    if name == "list_stations":
        return gateway.list_stations()
    if name == "propose_transport":
        return gateway.propose_transport(
            from_station=args.get("from"),
            to_station=args.get("to"),
            reason=args.get("reason"),
            idempotency_key=args.get("idempotency_key"),
        )
    if name == "get_proposal":
        return gateway.get_proposal(args.get("proposal_id"))
    raise ValueError("unknown tool {!r} — Phase 1 tools are: {}".format(
        name, ", ".join(TOOL_NAMES)))
