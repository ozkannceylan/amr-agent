"""G3 — approval is operator-only.

Architecture hygiene, not a safety function: M7 is not one. A decision
published by any client id other than the approve command's is ignored
and audited as IGNORED_UNAUTHORISED. The pending proposal does not move.
"""
import io
import json
import sys

import paho.mqtt.client as mqtt
import pytest
from jsonschema import Draft202012Validator

from console import approve
from gate.audit import AuditLog
from gate.policy import load_policy
from gate.proposal import (
    APPROVED,
    IGNORED_UNAUTHORISED,
    PENDING,
    REJECTED_HUMAN,
    Gate,
    load_schema,
)
from gateway.server import DECISION_TOPIC, SUBMIT_TOPIC, Gateway


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
    gw.accept_status(json.dumps({"ts": now, "manager": "ONLINE"}))
    return gw


def _pending(gw, key="k-g3"):
    result = gw.propose_transport("S1", "S4", "move a pallet", key)
    assert result["verdict"] == PENDING
    return result


def test_approve_command_id_is_the_policy_authorised_decider():
    policy = load_policy()
    assert approve.DECIDER_ID == "m7-approve"
    assert approve.authorised_decider_id(policy) == approve.DECIDER_ID
    assert approve.DECIDER_ID in policy.authorised_deciders


def test_build_decision_matches_schema_and_cannot_omit_the_command_id():
    body = approve.build_decision("pr-abc", "approve", ts=1.5)
    Draft202012Validator(load_schema("decision.schema.json")).validate(body)
    assert body["decided_by"] == approve.DECIDER_ID
    assert body["decision"] == "approve"
    assert body["proposal_id"] == "pr-abc"
    rejected = approve.build_decision("pr-abc", "reject", ts=1.5)
    assert rejected["decision"] == "reject"
    assert rejected["decided_by"] == approve.DECIDER_ID


def test_approve_publishes_only_the_decision_topic():
    assert approve.PUBLISH_TOPICS == (approve.DECISION_TOPIC,)
    assert approve.SUBSCRIBE_TOPICS == (approve.PROPOSALS_TOPIC,)
    assert approve.DECISION_TOPIC == DECISION_TOPIC
    assert all("uagv" not in topic for topic in approve.PUBLISH_TOPICS)
    assert all("uagv" not in topic for topic in approve.SUBSCRIBE_TOPICS)
    client = FakeClient()
    info, body = approve.publish_decision(client, "pr-1", "approve", ts=9.0)
    assert info.is_published()
    assert len(client.pubs) == 1
    item = client.pubs[0]
    assert item["topic"] == DECISION_TOPIC
    assert item["retain"] is False
    assert item["qos"] == 1
    assert json.loads(item["payload"]) == body
    assert body["decided_by"] == approve.DECIDER_ID
    assert SUBMIT_TOPIC not in [p["topic"] for p in client.pubs]


@pytest.mark.parametrize("other_id", [
    "m7-console",
    "fleet-cli",
    "someone-else",
    "m7-approve-extra",
    "admin",
])
def test_g3_other_client_id_is_ignored_and_audited(tmp_path, other_id):
    gw = _gateway(tmp_path)
    pending = _pending(gw)
    pid = pending["proposal_id"]
    forged = approve.build_decision(
        pid, "approve", ts=gw.now(), decided_by=other_id)
    handled = gw.handle_decision(forged)
    assert handled["applied"] is False
    assert handled["verdict"] == IGNORED_UNAUTHORISED
    assert gw.gate.get(pid).state == PENDING
    rows = gw.gate.audit.rows()
    ignored = [row for row in rows if row["verdict"] == IGNORED_UNAUTHORISED]
    assert len(ignored) == 1
    assert ignored[0]["decided_by"] == other_id
    assert ignored[0]["client_id"] == other_id
    assert ignored[0]["arguments"]["decision"] == "approve"
    assert ignored[0]["proposal_id"] == pid
    assert SUBMIT_TOPIC not in [
        item["topic"] for item in getattr(gw.mq, "pubs", [])]


def test_g3_forged_mqtt_payload_is_ignored_the_same_way(tmp_path):
    gw = _gateway(tmp_path)
    client = FakeClient()
    gw.bind_mqtt(client)
    pending = _pending(gw)
    pid = pending["proposal_id"]
    forged = json.dumps({
        "proposal_id": pid,
        "decision": "reject",
        "decided_by": "not-the-operator",
        "ts": gw.now(),
    }).encode()
    gw.accept_mqtt(DECISION_TOPIC, forged)
    assert gw.gate.get(pid).state == PENDING
    assert gw.gate.audit.rows()[-1]["verdict"] == IGNORED_UNAUTHORISED
    assert gw.gate.audit.rows()[-1]["decided_by"] == "not-the-operator"
    assert not any(item["topic"] == SUBMIT_TOPIC for item in client.pubs)


def test_g3_authorised_decision_still_applies_after_a_forged_one(tmp_path):
    gw = _gateway(tmp_path)
    pending = _pending(gw)
    pid = pending["proposal_id"]
    gw.handle_decision(approve.build_decision(
        pid, "approve", ts=gw.now(), decided_by="intruder"))
    assert gw.gate.get(pid).state == PENDING
    handled = gw.handle_decision(approve.build_decision(pid, "approve",
                                                        ts=gw.now()))
    assert handled["applied"] is True
    assert gw.gate.get(pid).state in (APPROVED, "FORWARDED", "FORWARD_FAILED")
    verdicts = [row["verdict"] for row in gw.gate.audit.rows()]
    assert IGNORED_UNAUTHORISED in verdicts
    assert APPROVED in verdicts


def test_g3_authorised_reject_is_rejected_human(tmp_path):
    gw = _gateway(tmp_path)
    pending = _pending(gw)
    pid = pending["proposal_id"]
    handled = gw.handle_decision(approve.build_decision(pid, "reject",
                                                        ts=gw.now()))
    assert handled["applied"] is True
    assert handled["verdict"] == REJECTED_HUMAN
    assert gw.gate.get(pid).state == REJECTED_HUMAN


def test_list_render_names_pending_and_states_restart_loss():
    now = 100.0
    empty = approve.render_proposals({"ts": now, "proposals": []}, now)
    assert "pending 0" in empty
    assert "(none pending)" in empty
    assert "no persistence across restart" in empty
    doc = {
        "ts": now - 0.4,
        "proposals": [{
            "proposal_id": "pr-aa",
            "from": "S1",
            "to": "S4",
            "reason": "move a pallet",
            "created_ts": now - 12.0,
        }],
    }
    text = approve.render_proposals(doc, now)
    assert "pending 1" in text and "document age 0.4 s" in text
    assert "pr-aa" in text and "S1 -> S4" in text
    assert "move a pallet" in text
    stale = approve.render_proposals(
        {"ts": now - 20.0, "proposals": []}, now)
    assert "STALE" in stale


def test_proposals_liveness_uses_fleet_cli_age_bound():
    now = 50.0
    assert approve.proposals_liveness(None, now) is not None
    fresh = json.dumps({"ts": now - 0.1, "proposals": []}).encode()
    assert approve.proposals_liveness(fresh, now) is None
    stale = json.dumps({"ts": now - 20.0, "proposals": []}).encode()
    message = approve.proposals_liveness(stale, now)
    assert message is not None and "not running" in message


def test_list_uses_fleet_cli_parse_helper():
    payload = json.dumps({
        "ts": 1.0,
        "proposals": [{"proposal_id": "pr-1", "from": "S1", "to": "S4"}],
    }).encode()
    assert approve.fleet_cli._parse(payload)["proposals"][0]["proposal_id"] \
        == "pr-1"
    assert approve.pending_ids(approve.fleet_cli._parse(payload)) == ["pr-1"]


def test_parser_accepts_list_approve_reject():
    parser = approve.build_parser()
    assert parser.parse_args(["list"]).command == "list"
    approved = parser.parse_args(["approve", "pr-1"])
    assert approved.command == "approve" and approved.proposal_id == "pr-1"
    rejected = parser.parse_args(["reject", "pr-2"])
    assert rejected.command == "reject" and rejected.proposal_id == "pr-2"


def test_main_without_command_is_usage(monkeypatch):
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    assert approve.main([]) == 2
