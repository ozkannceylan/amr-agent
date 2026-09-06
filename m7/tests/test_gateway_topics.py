"""G1 — the gateway cannot reach a vehicle.

Architecture hygiene, not a safety function: M7 is not one. Measured
as: no vehicle-topic subscription, exactly two publish topics
(fleet/task/submit and the retained fleet/proposals document), and
the static boundary check named in HAND_OFF.
"""
import json
import subprocess
import sys
from pathlib import Path

import paho.mqtt.client as mqtt

from gate.audit import AuditLog
from gate.policy import load_policy
from gate.proposal import FORWARDED, PENDING, Gate
from gateway.server import (
    DECISION_TOPIC,
    PROPOSALS_TOPIC,
    PUBLISH_TOPICS,
    STATUS_TOPIC,
    SUBMIT_TOPIC,
    SUBSCRIBE_TOPICS,
    Gateway,
)
from gateway.tools import TOOL_NAMES, dispatch

REPO = Path(__file__).resolve().parents[2]
CHECKER = REPO / "m7" / "tools" / "check_m7_boundaries.py"


class FakeInfo:
    rc = mqtt.MQTT_ERR_SUCCESS

    def wait_for_publish(self, timeout=None):
        return True

    def is_published(self):
        return True


class FakeClient:
    def __init__(self):
        self.subs = []
        self.pubs = []
        self.on_connect = None
        self.on_message = None

    def subscribe(self, topic, qos=0):
        self.subs.append(topic)

    def publish(self, topic, payload, qos=0, retain=False):
        self.pubs.append({
            "topic": topic,
            "payload": payload,
            "qos": qos,
            "retain": retain,
        })
        return FakeInfo()


def _gateway(tmp_path, now=1000.0):
    clock = {"t": now}

    def now_fn():
        return clock["t"]

    gate = Gate(
        policy=load_policy(),
        audit=AuditLog(path=tmp_path / "audit.jsonl"),
        clock=now_fn,
    )
    gw = Gateway(gate, client_id="console-a", clock=now_fn)
    gw._clock_state = clock
    return gw


def test_g1_subscribe_list_has_no_vehicle_topic():
    assert SUBSCRIBE_TOPICS == (STATUS_TOPIC, DECISION_TOPIC)
    assert all("uagv" not in topic for topic in SUBSCRIBE_TOPICS)
    assert all(topic.startswith("fleet/") for topic in SUBSCRIBE_TOPICS)


def test_g1_exactly_two_publish_topics():
    assert len(PUBLISH_TOPICS) == 2
    assert set(PUBLISH_TOPICS) == {SUBMIT_TOPIC, PROPOSALS_TOPIC}
    assert all("uagv" not in topic for topic in PUBLISH_TOPICS)


def test_g1_bind_mqtt_subscribes_only_the_two_fleet_topics(tmp_path):
    gw = _gateway(tmp_path)
    client = FakeClient()
    gw.bind_mqtt(client)
    assert client.subs == [STATUS_TOPIC, DECISION_TOPIC]
    assert all("uagv" not in topic for topic in client.subs)


def test_g1_on_connect_does_not_add_a_vehicle_subscription(tmp_path):
    gw = _gateway(tmp_path)
    client = FakeClient()
    gw.bind_mqtt(client)
    client.subs.clear()
    gw._on_connect(client, None, None, 0)
    assert set(client.subs) == {STATUS_TOPIC, DECISION_TOPIC}


def test_g1_live_publish_uses_only_the_two_topics(tmp_path):
    gw = _gateway(tmp_path)
    client = FakeClient()
    gw.bind_mqtt(client)
    gw.accept_status(json.dumps({"ts": gw.now(), "manager": "ONLINE"}))
    result = gw.propose_transport("S1", "S4", "move", "k-g1")
    assert result["verdict"] == PENDING
    decided = gw.handle_decision({
        "proposal_id": result["proposal_id"],
        "decision": "approve",
        "decided_by": "m7-approve",
        "ts": gw.now(),
    })
    assert decided["verdict"] == FORWARDED
    topics = [item["topic"] for item in client.pubs]
    assert set(topics) <= set(PUBLISH_TOPICS)
    assert SUBMIT_TOPIC in topics
    assert PROPOSALS_TOPIC in topics
    assert all("uagv" not in topic for topic in topics)
    submit = next(item for item in client.pubs if item["topic"] == SUBMIT_TOPIC)
    body = json.loads(submit["payload"])
    assert set(body) == {"taskId", "from", "to"}
    assert (body["from"], body["to"]) == ("S1", "S4")
    assert submit["retain"] is False
    retained = next(
        item for item in client.pubs
        if item["topic"] == PROPOSALS_TOPIC and item["retain"]
    )
    assert retained["retain"] is True


def test_g1_refuses_to_publish_any_other_topic(tmp_path):
    gw = _gateway(tmp_path)
    gw.bind_mqtt(FakeClient())
    try:
        gw._publish("fleet/other", {}, retain=False)
        raise AssertionError("must refuse a third publish topic")
    except ValueError as exc:
        assert "refusing to publish" in str(exc)


def test_g1_static_boundary_check_passes():
    completed = subprocess.run(
        [sys.executable, str(CHECKER)],
        check=False, capture_output=True, text=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout


def test_phase1_tool_surface_is_exactly_the_four():
    assert TOOL_NAMES == (
        "get_fleet_status",
        "list_stations",
        "propose_transport",
        "get_proposal",
    )


def test_read_tools_do_not_need_a_broker(tmp_path):
    gw = _gateway(tmp_path)
    gw.accept_status(json.dumps({"ts": gw.now() - 0.4, "manager": "ONLINE"}))
    status = dispatch(gw, "get_fleet_status", {})
    assert status["stale"] is False
    assert abs(status["age_s"] - 0.4) < 1e-9
    stations = dispatch(gw, "list_stations", {})
    assert [row["id"] for row in stations["stations"]] == list(
        gw.gate.policy.stations)
    missing = dispatch(gw, "get_proposal", {"proposal_id": "pr-none"})
    assert missing == {"found": False, "proposal": None}
