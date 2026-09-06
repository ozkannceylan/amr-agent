"""approve.py — operator list / approve / reject. Standalone Phase 2a.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function. G3 is architecture hygiene, not a
safety property: a decision from any client id other than this
command's is ignored and audited as IGNORED_UNAUTHORISED.

IT PUBLISHES ONE TOPIC. `approve` and `reject` are one QoS 1 publish
to fleet/proposal/decision, not retained, with decided_by set to
this command's client id. The screen is the retained fleet/proposals
document, read the same way fleet_cli status reads fleet/status —
same helpers, imported, not copied.

Phase 2b will register these commands on fleet_cli; this file stays
the implementation. It is not a second master and it does not
publish fleet/task/submit.
"""
from __future__ import annotations

import argparse
import json
import queue
import sys
import time
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]
_FLEET = _REPO / "m6" / "fleet"
_M7 = Path(__file__).resolve().parents[1]
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))
if str(_M7) not in sys.path:
    sys.path.insert(0, str(_M7))

import fleet_cli                                         # noqa: E402

from gate.policy import load_policy                      # noqa: E402
from gate.proposal import load_schema                    # noqa: E402
from jsonschema import Draft202012Validator              # noqa: E402

DECISION_TOPIC = "fleet/proposal/decision"
PROPOSALS_TOPIC = "fleet/proposals"
DECIDER_ID = "m7-approve"

SUBSCRIBE_TOPICS = (PROPOSALS_TOPIC,)
PUBLISH_TOPICS = (DECISION_TOPIC,)

_DECISION_SCHEMA = load_schema("decision.schema.json")
_DECISION_VALIDATOR = Draft202012Validator(_DECISION_SCHEMA)


def authorised_decider_id(policy=None) -> str:
    """The one client id G3 accepts. Must match policy.yaml."""
    loaded = policy if policy is not None else load_policy()
    if DECIDER_ID not in loaded.authorised_deciders:
        raise ValueError(
            "DECIDER_ID {!r} is not in policy authorised_deciders"
            .format(DECIDER_ID))
    return DECIDER_ID


def build_decision(proposal_id, decision, *, ts=None,
                   decided_by=None) -> dict:
    """The fleet/proposal/decision body, or ValueError naming what is wrong.

    decided_by defaults to this command's client id and is not a CLI
    flag: an operator cannot impersonate another id from here.
    """
    if decision not in ("approve", "reject"):
        raise ValueError("decision must be approve or reject")
    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise ValueError("proposal id must be a non-empty string")
    body = {
        "proposal_id": proposal_id.strip(),
        "decision": decision,
        "decided_by": decided_by or DECIDER_ID,
        "ts": time.time() if ts is None else float(ts),
    }
    errors = sorted(
        _DECISION_VALIDATOR.iter_errors(body), key=lambda e: list(e.path))
    if errors:
        raise ValueError("decision body fails schema: {}".format(
            "; ".join(e.message for e in errors)))
    return body


def pending_ids(doc) -> list[str]:
    block = []
    if not isinstance(doc, dict):
        return block
    rows = doc.get("proposals")
    if not isinstance(rows, list):
        return block
    for item in rows:
        if isinstance(item, dict) and isinstance(item.get("proposal_id"), str):
            block.append(item["proposal_id"])
    return block


def proposals_liveness(payload, now):
    """What is wrong with the gateway behind this retained document, or
    None when nothing is. Same age bound fleet_cli uses for fleet/status.
    """
    if payload is None:
        return ("no retained fleet/proposals - no M7 gateway has ever "
                "published on this broker. Pending proposals do not "
                "survive a gateway restart.")
    if isinstance(payload, dict):
        doc = payload
    else:
        doc = fleet_cli._parse(payload)
    if doc is None:
        return "the retained fleet/proposals is not a readable JSON object"
    ts = doc.get("ts")
    age = (now - ts) if isinstance(ts, (int, float)) else None
    if age is None:
        return "the retained fleet/proposals carries no timestamp"
    if age > fleet_cli.STALE_AFTER_S:
        return ("the retained fleet/proposals is {:.1f} s old - the "
                "gateway republishes like fleet/status, so it is not "
                "running. Pending proposals were lost."
                .format(age))
    return None


def render_proposals(doc, now, stale_after_s=None) -> str:
    bound = (fleet_cli.STALE_AFTER_S if stale_after_s is None
             else stale_after_s)
    rows = []
    if isinstance(doc, dict) and isinstance(doc.get("proposals"), list):
        rows = [item for item in doc["proposals"] if isinstance(item, dict)]
    ts = doc.get("ts") if isinstance(doc, dict) else None
    age = (now - ts) if isinstance(ts, (int, float)) else None
    lines = [
        "fleet/proposals   pending {}   document age {} s".format(
            len(rows),
            "{:.1f}".format(age) if age is not None else "-"),
    ]
    if age is not None and age > bound:
        lines.append(
            "  ** STALE: this document is {:.1f} s old and the gateway "
            "that holds pending proposals is not running. A restart "
            "loses the pending set.".format(age))
    if not rows:
        lines.append("(none pending)")
        lines.append(
            "  the gateway has no persistence across restart — "
            "unapproved proposals are gone if it is not running")
        return "\n".join(lines)
    for item in rows:
        created = item.get("created_ts")
        item_age = ((now - created)
                    if isinstance(created, (int, float)) else None)
        reason = item.get("reason") or ""
        lines.append("{}  {} -> {}  age {} s  {}".format(
            item.get("proposal_id") or "-",
            item.get("from") or "-",
            item.get("to") or "-",
            "{:.1f}".format(item_age) if item_age is not None else "-",
            reason).rstrip())
    return "\n".join(lines)


def _proposals_reader(host, port, role="approve"):
    """(client, inbox) subscribed to retained fleet/proposals.

    Same shape as fleet_cli._status_reader: subscribe inside on_connect
    so it cannot race the CONNACK. The helpers are fleet_cli's.
    """
    inbox = queue.Queue()
    client = fleet_cli._client(role)
    client.on_connect = lambda c, u, f, rc, props=None: \
        c.subscribe(PROPOSALS_TOPIC, qos=1)
    client.on_message = lambda c, u, msg: inbox.put(msg.payload)
    if not fleet_cli._connect(client, host, port):
        return None, None
    client.loop_start()
    return client, inbox


def publish_decision(client, proposal_id, decision, *, ts=None):
    """QoS 1, not retained. Returns the paho publish info."""
    body = build_decision(proposal_id, decision, ts=ts)
    payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
    return client.publish(DECISION_TOPIC, payload, qos=1, retain=False), body


def cmd_list(args) -> int:
    client, inbox = _proposals_reader(args.host, args.port, role="list")
    if client is None:
        return 1
    payload = fleet_cli._await(inbox, fleet_cli.STATUS_WAIT_S)
    try:
        now = time.time()
        trouble = proposals_liveness(payload, now)
        if payload is None:
            return fleet_cli._die(trouble, 1)
        doc = fleet_cli._parse(payload)
        if doc is None:
            return fleet_cli._die(
                trouble or "unreadable fleet/proposals payload", 1)
        sys.stdout.write(render_proposals(doc, now) + "\n")
        return 0
    finally:
        fleet_cli._close(client)


def cmd_decide(args, decision: str) -> int:
    client, inbox = _proposals_reader(args.host, args.port, role=decision)
    if client is None:
        return 1
    payload = fleet_cli._await(inbox, fleet_cli.STATUS_WAIT_S)
    now = time.time()
    try:
        trouble = proposals_liveness(payload, now)
        doc = fleet_cli._parse(payload) if payload is not None else None
        if doc is None:
            return fleet_cli._die(
                trouble or "no retained fleet/proposals to decide against", 1)
        if args.proposal_id not in pending_ids(doc):
            return fleet_cli._die(
                "{} is not in the pending set".format(args.proposal_id), 2)
        info, body = publish_decision(
            client, args.proposal_id, decision, ts=now)
        try:
            info.wait_for_publish(timeout=fleet_cli.PUBLISH_WAIT_S)
        except (RuntimeError, ValueError, AttributeError):
            pass
        if not info.is_published():
            return fleet_cli._die(
                "the broker at {}:{} did not acknowledge the decision "
                "within {:.0f} s - nothing was decided".format(
                    args.host, args.port, fleet_cli.PUBLISH_WAIT_S))
        print("{}  {}".format(
            body["proposal_id"],
            "approved" if decision == "approve" else "rejected"))
        if trouble:
            sys.stderr.write(
                "WARNING: {}.\n         A decision is not retained - if "
                "no gateway is running this verdict is gone, not waiting.\n"
                .format(trouble))
        return 0
    finally:
        fleet_cli._close(client)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="approve or reject an M7 transport proposal")
    parser.add_argument("--host", default=fleet_cli.MQTT_HOST)
    parser.add_argument("--port", type=int, default=fleet_cli.MQTT_PORT)
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("list", help="render the retained pending set")
    approve = commands.add_parser(
        "approve", help="publish an approve decision for a proposal id")
    approve.add_argument("proposal_id", metavar="ID")
    reject = commands.add_parser(
        "reject", help="publish a reject decision for a proposal id")
    reject.add_argument("proposal_id", metavar="ID")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2
    authorised_decider_id()
    if args.command == "list":
        return cmd_list(args)
    if args.command == "approve":
        return cmd_decide(args, "approve")
    return cmd_decide(args, "reject")


if __name__ == "__main__":
    raise SystemExit(main())
