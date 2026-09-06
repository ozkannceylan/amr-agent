"""server.py — MCP contract gateway; paho on the two fleet topics.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function. G1 is architecture hygiene, not a
safety property: this process holds no vehicle-topic subscription and
publishes on exactly two fleet topics.

THE FLEET MANAGER IS UNTOUCHED. An approved submit body is the same
shape `fleet_cli.build_submission` produces. The manager cannot tell
an approved M7 submission from an operator's.

MCP stays in this file. The gate (schema → policy → hold → audit)
does not import it, so a library swap cannot move the verdict.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

_HERE = Path(__file__).resolve().parent
_M7 = _HERE.parent
if str(_M7) not in sys.path:
    sys.path.insert(0, str(_M7))

from gate.audit import AuditLog                          # noqa: E402
from gate.policy import load_policy                      # noqa: E402
from gate.proposal import (                              # noqa: E402
    APPROVED,
    PENDING,
    Gate,
    load_schema,
)
from gateway.tools import TOOLS, dispatch                # noqa: E402

MQTT_HOST = "127.0.0.1"
MQTT_PORT = int(os.environ.get("VDA_MQTT_PORT", "1883"))
CLIENT_ID = os.environ.get("M7_CLIENT_ID", "m7-console")

STATUS_TOPIC = "fleet/status"
DECISION_TOPIC = "fleet/proposal/decision"
SUBMIT_TOPIC = "fleet/task/submit"
PROPOSALS_TOPIC = "fleet/proposals"

SUBSCRIBE_TOPICS = (STATUS_TOPIC, DECISION_TOPIC)
PUBLISH_TOPICS = (SUBMIT_TOPIC, PROPOSALS_TOPIC)

QOS = 1
PUBLISH_WAIT_S = 5.0
DEFAULT_CLIENT_MQTT_ID = "m7-gateway"


class Gateway:
    """Deterministic tool handler plus the two-topic paho client."""

    def __init__(self, gate: Gate | None = None, *,
                 client_id: str = CLIENT_ID,
                 host: str = MQTT_HOST,
                 port: int = MQTT_PORT,
                 clock=None,
                 mqtt_client=None):
        self.gate = gate if gate is not None else Gate()
        self.client_id = client_id
        self.host = host
        self.port = port
        self._clock = clock or self.gate.now
        self._status_doc = None
        self._status_payload_ts = None
        self._decision_schema = load_schema("decision.schema.json")
        self.mq = mqtt_client
        self.connected = False
        self._last_submit_rc = None

    def subscribe_topics(self):
        return SUBSCRIBE_TOPICS

    def publish_topics(self):
        return PUBLISH_TOPICS

    def now(self) -> float:
        return float(self._clock())

    def status_ts(self):
        if not isinstance(self._status_doc, dict):
            return None
        ts = self._status_doc.get("ts")
        if not isinstance(ts, (int, float)) or isinstance(ts, bool):
            return None
        return float(ts)

    def status_age(self, now=None):
        ts = self.status_ts()
        if ts is None:
            return None
        return (self.now() if now is None else now) - ts

    def get_fleet_status(self) -> dict:
        now = self.now()
        age = self.status_age(now)
        stale_after = self.gate.policy.stale_after_s
        stale = age is None or age > stale_after
        return {
            "status": self._status_doc,
            "age_s": age,
            "stale": stale,
            "stale_after_s": stale_after,
        }

    def list_stations(self) -> dict:
        stations = [
            {"id": sid, "name": name}
            for sid, name in self.gate.policy.stations.items()
        ]
        return {"stations": stations}

    def propose_transport(self, from_station, to_station, reason,
                          idempotency_key) -> dict:
        self.gate.expire_due(self.now())
        result = self.gate.propose(
            from_station=from_station,
            to_station=to_station,
            reason=reason,
            idempotency_key=idempotency_key,
            client_id=self.client_id,
            status_ts=self.status_ts(),
            now=self.now(),
        )
        if result.proposal is not None and result.verdict == PENDING:
            self._publish_proposals()
        return _proposal_payload(result)

    def get_proposal(self, proposal_id) -> dict:
        self.gate.expire_due(self.now())
        if not proposal_id:
            return {"found": False, "proposal": None}
        proposal = self.gate.get(str(proposal_id))
        if proposal is None:
            return {"found": False, "proposal": None}
        return {"found": True, "proposal": proposal.to_record()}

    def handle_decision(self, body: dict) -> dict:
        """Apply one fleet/proposal/decision payload, or ignore it."""
        from jsonschema import Draft202012Validator
        errors = list(Draft202012Validator(self._decision_schema).iter_errors(body))
        if errors:
            return {"applied": False, "verdict": "REJECTED_SCHEMA"}
        result = self.gate.apply_decision(
            body["proposal_id"],
            body["decision"],
            body["decided_by"],
            now=self.now(),
        )
        if result.ignored:
            return {"applied": False, "verdict": result.verdict}
        if result.verdict == APPROVED:
            self._forward(result.proposal)
        self._publish_proposals()
        verdict = (result.proposal.state
                   if result.proposal is not None else result.verdict)
        return {"applied": True, "verdict": verdict,
                "proposal": result.proposal.to_record()
                if result.proposal is not None else None}

    def accept_status(self, payload) -> None:
        doc = _parse_json(payload)
        self._status_doc = doc if isinstance(doc, dict) else None
        self._status_payload_ts = self.now()

    def accept_mqtt(self, topic: str, payload) -> None:
        if topic == STATUS_TOPIC:
            self.accept_status(payload)
            return
        if topic == DECISION_TOPIC:
            body = _parse_json(payload)
            if isinstance(body, dict):
                try:
                    self.handle_decision(body)
                except ValueError:
                    return

    def bind_mqtt(self, client) -> None:
        """Subscribe the two topics. Used by G1 without a live broker."""
        self.mq = client
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        for topic in SUBSCRIBE_TOPICS:
            client.subscribe(topic, qos=QOS)

    def start_mqtt(self):
        client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id="{}-{}".format(DEFAULT_CLIENT_MQTT_ID, os.getpid()),
        )
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        client.reconnect_delay_set(min_delay=1, max_delay=8)
        client.connect_async(self.host, self.port)
        client.loop_start()
        self.mq = client
        return client

    def stop_mqtt(self):
        if self.mq is None:
            return
        try:
            self.mq.disconnect()
        except Exception:
            pass
        try:
            self.mq.loop_stop()
        except Exception:
            pass

    def proposals_document(self) -> dict:
        return {
            "ts": self.now(),
            "proposals": [p.to_record() for p in self.gate.pending()],
        }

    def _forward(self, proposal) -> None:
        age = self.status_age()
        if age is None or age > self.gate.policy.stale_after_s:
            self.gate.complete_forward(
                proposal.proposal_id, False, forward_rc="stale_status",
                now=self.now())
            return
        body = {
            "taskId": proposal.task_id,
            "from": proposal.from_station,
            "to": proposal.to_station,
        }
        rc = self._publish(SUBMIT_TOPIC, body, retain=False)
        self._last_submit_rc = rc
        ok = rc == mqtt.MQTT_ERR_SUCCESS
        self.gate.complete_forward(
            proposal.proposal_id, ok,
            forward_rc=rc if rc is not None else "no_ack",
            now=self.now())

    def _publish_proposals(self) -> None:
        self._publish(PROPOSALS_TOPIC, self.proposals_document(), retain=True)

    def _publish(self, topic: str, body: dict, *, retain: bool):
        if topic not in PUBLISH_TOPICS:
            raise ValueError("refusing to publish on {}".format(topic))
        if self.mq is None:
            return mqtt.MQTT_ERR_NO_CONN
        payload = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        info = self.mq.publish(topic, payload, qos=QOS, retain=retain)
        try:
            info.wait_for_publish(timeout=PUBLISH_WAIT_S)
        except (RuntimeError, ValueError, AttributeError):
            pass
        rc = getattr(info, "rc", None)
        if rc is None:
            published = getattr(info, "is_published", lambda: False)()
            return (mqtt.MQTT_ERR_SUCCESS if published
                    else mqtt.MQTT_ERR_NO_CONN)
        return rc

    def _on_connect(self, client, userdata, flags, reason_code,
                    properties=None):
        self.connected = True
        for topic in SUBSCRIBE_TOPICS:
            client.subscribe(topic, qos=QOS)
        self._publish_proposals()

    def _on_message(self, client, userdata, msg):
        self.accept_mqtt(msg.topic, msg.payload)


def _proposal_payload(result) -> dict:
    proposal = result.proposal
    return {
        "proposal_id": None if proposal is None else proposal.proposal_id,
        "state": None if proposal is None else proposal.state,
        "verdict": result.verdict,
        "duplicate": result.duplicate,
        "policy_rule": result.policy_rule,
        "task_id": None if proposal is None else proposal.task_id,
        "proposal": None if proposal is None else proposal.to_record(),
    }


def _parse_json(payload):
    if payload is None:
        return None
    if isinstance(payload, dict):
        return payload
    try:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        doc = json.loads(payload)
    except (ValueError, UnicodeDecodeError, TypeError):
        return None
    return doc if isinstance(doc, dict) else None


def build_mcp(gateway: Gateway):
    """Wrap the official MCP server library. Only this function imports it.

    `from` is a reserved word in Python, so propose_transport is registered
    with an explicit argument model whose JSON name is still `from` — the
    name ARCHITECTURE.md §3 gives the tool.
    """
    from mcp.server import MCPServer
    from mcp.server.mcpserver.utilities.func_metadata import ArgModelBase
    from pydantic import Field, create_model

    from gateway.tools import PROPOSE_INPUT

    mcp = MCPServer("m7-gateway")

    def get_fleet_status() -> dict:
        return dispatch(gateway, "get_fleet_status", {})

    def list_stations() -> dict:
        return dispatch(gateway, "list_stations", {})

    def propose_transport(**arguments) -> dict:
        return dispatch(gateway, "propose_transport", arguments)

    def get_proposal(proposal_id: str) -> dict:
        return dispatch(gateway, "get_proposal", {
            "proposal_id": proposal_id,
        })

    mcp.add_tool(get_fleet_status, description=TOOLS[0]["description"])
    mcp.add_tool(list_stations, description=TOOLS[1]["description"])
    mcp.add_tool(propose_transport, description=TOOLS[2]["description"])
    mcp.add_tool(get_proposal, description=TOOLS[3]["description"])

    tool = mcp._tool_manager._tools["propose_transport"]
    propose_args = create_model(
        "ProposeTransportArguments",
        __base__=ArgModelBase,
        **{
            "from": (str, Field(description="Pickup station id")),
            "to": (str, Field(description="Drop-off station id")),
            "reason": (str, Field(
                description="Model text; stored, never parsed by the gate")),
            "idempotency_key": (str, Field(description="Idempotency key")),
        },
    )
    tool.fn_metadata.arg_model = propose_args
    tool.parameters = PROPOSE_INPUT
    return mcp


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    host = MQTT_HOST
    port = MQTT_PORT
    mqtt_only = "--mqtt-only" in argv
    if "--host" in argv:
        host = argv[argv.index("--host") + 1]
    if "--port" in argv:
        port = int(argv[argv.index("--port") + 1])
    audit_dir = _M7 / "audit"
    gate = Gate(
        policy=load_policy(),
        audit=AuditLog(audit_dir=audit_dir),
        clock=time.time,
    )
    gateway = Gateway(gate, host=host, port=port)
    gateway.start_mqtt()
    try:
        if mqtt_only:
            while True:
                time.sleep(1.0)
        build_mcp(gateway).run()
    except KeyboardInterrupt:
        return 0
    finally:
        gateway.stop_mqtt()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
