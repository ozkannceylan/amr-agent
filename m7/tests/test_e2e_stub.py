"""G4 — end to end on the fleet_manager stub.

Console proposes (scripted client, never a live model), operator
approves, fleet/status shows the task. The forwarded submit body
matches fleet_cli.build_submission. Architecture hygiene around the
approval path; M7 is not a safety function.
"""
import json
import os
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt
import pytest
import yaml

from console import approve
from console.client import (
    WAITING,
    BudgetExceeded,
    ClientConfig,
    ConsoleClient,
    DispatchBackend,
    ModelTurn,
    NOT_RETRIED,
    ScriptedModel,
    ToolUse,
)
from gate.audit import AuditLog
from gate.policy import load_policy
from gate.proposal import FORWARDED, PENDING, Gate
from gateway.server import PROPOSALS_TOPIC, SUBMIT_TOPIC, Gateway

REPO = Path(__file__).resolve().parents[2]
CLIENT_PY = REPO / "m7" / "console" / "client.py"
CLIENT_YAML = REPO / "m7" / "console" / "client.yaml"
M7_SH = REPO / "m7.sh"

_FLEET = REPO / "m6" / "fleet"
if str(_FLEET) not in sys.path:
    sys.path.insert(0, str(_FLEET))

fleet_cli = pytest.importorskip("fleet_cli")
fm = pytest.importorskip("fleet_manager")


class FakeInfo:
    rc = mqtt.MQTT_ERR_SUCCESS

    def wait_for_publish(self, timeout=None):
        return True

    def is_published(self):
        return True


class StubInfo:
    def __init__(self, rc):
        self.rc = rc

    def is_published(self):
        return self.rc == mqtt.MQTT_ERR_SUCCESS

    def wait_for_publish(self, timeout=None):
        return None


class ManagerStub:
    """paho surface as test_fleet_manager_stub.StubClient uses it."""

    def __init__(self, *args, **kwargs):
        self.rc = mqtt.MQTT_ERR_SUCCESS
        self.published = []
        self.subscriptions = []
        self.on_connect = self.on_disconnect = self.on_message = None

    def reconnect_delay_set(self, **kwargs):
        pass

    def connect_async(self, *args, **kwargs):
        pass

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def subscribe(self, topics, qos=0):
        self.subscriptions.append(topics)

    def publish(self, topic, payload, qos=0, retain=False):
        if self.rc == mqtt.MQTT_ERR_SUCCESS:
            try:
                body = json.loads(payload)
            except (TypeError, ValueError):
                body = payload
            self.published.append((topic, body, qos, retain))
        return StubInfo(self.rc)


class Bridge:
    """Gateway MQTT: submit is handed to the stub manager, not a broker."""

    def __init__(self, manager):
        self.manager = manager
        self.subs = []
        self.pubs = []
        self.on_connect = None
        self.on_message = None

    def subscribe(self, topic, qos=0):
        self.subs.append(topic)

    def publish(self, topic, payload, qos=0, retain=False):
        raw = payload.encode() if isinstance(payload, str) else payload
        try:
            body = json.loads(raw)
        except (TypeError, ValueError, UnicodeDecodeError):
            body = raw
        self.pubs.append({
            "topic": topic, "payload": raw, "body": body,
            "qos": qos, "retain": retain,
        })
        if topic == SUBMIT_TOPIC:
            self.manager._on_submit(raw)
        return FakeInfo()


@pytest.fixture
def manager(monkeypatch):
    stub = ManagerStub()
    monkeypatch.setattr(fm.mqtt, "Client", lambda *a, **k: stub)
    mgr = fm.FleetManager()
    yield mgr, stub
    mgr.close()


def _gateway(tmp_path, manager, now=None):
    clock = {"t": time.time() if now is None else now}

    def now_fn():
        return clock["t"]

    gate = Gate(
        policy=load_policy(),
        audit=AuditLog(path=tmp_path / "audit.jsonl"),
        clock=now_fn,
    )
    gw = Gateway(gate, client_id="console-a", clock=now_fn)
    bridge = Bridge(manager)
    gw.bind_mqtt(bridge)
    doc = manager._status(time.monotonic())
    gw.accept_status(json.dumps(doc))
    return gw, bridge, clock


def _scripted_propose(from_station="S1", to_station="S4", key="g4-1"):
    return ScriptedModel([
        ModelTurn(tool_uses=[ToolUse("propose_transport", {
            "from": from_station,
            "to": to_station,
            "reason": "g4 stub transport",
            "idempotency_key": key,
        })]),
        ModelTurn(text=WAITING),
    ])


def test_client_config_is_data_and_names_the_budget():
    cfg = ClientConfig.load(CLIENT_YAML)
    raw = yaml.safe_load(CLIENT_YAML.read_text(encoding="utf-8"))
    assert cfg.model_id == raw["model_id"]
    assert cfg.base_url == raw["base_url"]
    assert cfg.max_api_calls == raw["max_api_calls"]
    assert cfg.max_api_calls >= 1


def test_client_source_has_no_broker_client():
    text = CLIENT_PY.read_text(encoding="utf-8")
    assert "paho" not in text
    assert "import paho" not in text
    assert "ScriptedModel" in text


def test_scripted_client_never_imports_anthropic(tmp_path, manager):
    mgr, _ = manager
    gw, _, _ = _gateway(tmp_path, mgr)
    before = "anthropic" in sys.modules
    client = ConsoleClient(
        DispatchBackend(gw),
        _scripted_propose(),
        ClientConfig.load(CLIENT_YAML),
    )
    client.run("move a pallet from S1 to S4")
    if not before:
        assert "anthropic" not in sys.modules


def test_pending_is_rendered_as_waiting_for_operator(tmp_path, manager):
    mgr, _ = manager
    gw, _, _ = _gateway(tmp_path, mgr)
    client = ConsoleClient(
        DispatchBackend(gw), _scripted_propose(), ClientConfig.load())
    log = client.run("move a pallet from S1 to S4")
    assert WAITING in log.rendered
    assert log.tool_results[0]["verdict"] == PENDING
    assert log.tool_results[0]["message"] == WAITING


def test_rejected_proposal_is_not_retried(tmp_path, manager):
    mgr, _ = manager
    gw, _, _ = _gateway(tmp_path, mgr)
    script = ScriptedModel([
        ModelTurn(tool_uses=[ToolUse("propose_transport", {
            "from": "S99", "to": "S4",
            "reason": "bad station", "idempotency_key": "g4-bad",
        })]),
        ModelTurn(tool_uses=[ToolUse("propose_transport", {
            "from": "S99", "to": "S4",
            "reason": "retry", "idempotency_key": "g4-bad",
        })]),
        ModelTurn(text="gave up"),
    ])
    log = ConsoleClient(
        DispatchBackend(gw), script, ClientConfig.load()).run("go")
    assert log.tool_results[0]["verdict"] == "REJECTED_POLICY"
    assert log.tool_results[1]["verdict"] == NOT_RETRIED


def test_session_budget_caps_model_calls(tmp_path, manager):
    mgr, _ = manager
    gw, _, _ = _gateway(tmp_path, mgr)
    cfg = ClientConfig.load()
    cfg.max_api_calls = 1
    script = ScriptedModel([
        ModelTurn(tool_uses=[ToolUse("list_stations", {})]),
        ModelTurn(text="done"),
    ])
    with pytest.raises(BudgetExceeded):
        ConsoleClient(DispatchBackend(gw), script, cfg).run("stations")


def test_g4_propose_approve_status_and_cli_parity(tmp_path, manager):
    mgr, _stub = manager
    gw, bridge, _ = _gateway(tmp_path, mgr)
    model = _scripted_propose("S1", "S4", "g4-e2e")
    client = ConsoleClient(
        DispatchBackend(gw), model, ClientConfig.load(CLIENT_YAML))
    log = client.run("take a pallet from S1 to S4")
    assert isinstance(model, ScriptedModel)
    assert log.tool_results[0]["verdict"] == PENDING
    assert WAITING in log.rendered
    proposal = log.tool_results[0]["proposal"]
    pid = proposal["proposal_id"]
    task_id = proposal["task_id"]

    handled = gw.handle_decision(approve.build_decision(pid, "approve"))
    assert handled["applied"] is True
    assert gw.gate.get(pid).state == FORWARDED

    submits = [item for item in bridge.pubs if item["topic"] == SUBMIT_TOPIC]
    assert len(submits) == 1
    body = submits[0]["body"]
    expected = fleet_cli.build_submission("S1", "S4", task_id)
    assert body == expected
    assert set(body) == {"taskId", "from", "to"}

    status = mgr._status(time.monotonic())
    task_ids = [row["task_id"] for row in status["tasks"]]
    assert task_id in task_ids
    shown = next(row for row in status["tasks"] if row["task_id"] == task_id)
    assert (shown["from"], shown["to"]) == ("S1", "S4")
    assert shown["state"] == "QUEUED"

    assert any(item["topic"] == PROPOSALS_TOPIC for item in bridge.pubs)
    assert all("uagv" not in item["topic"] for item in bridge.pubs)
    assert all("uagv" not in topic for topic in bridge.subs)


def test_g4_rejected_proposal_never_reaches_the_manager(tmp_path, manager):
    mgr, _ = manager
    gw, bridge, _ = _gateway(tmp_path, mgr)
    model = ScriptedModel([
        ModelTurn(tool_uses=[ToolUse("propose_transport", {
            "from": "S1", "to": "S4",
            "reason": "operator will refuse",
            "idempotency_key": "g4-no",
        })]),
        ModelTurn(text=WAITING),
    ])
    log = ConsoleClient(
        DispatchBackend(gw), model, ClientConfig.load()).run("go")
    pid = log.tool_results[0]["proposal_id"]
    gw.handle_decision(approve.build_decision(pid, "reject"))
    assert not [item for item in bridge.pubs if item["topic"] == SUBMIT_TOPIC]
    status = mgr._status(time.monotonic())
    assert status["tasks"] == []


def test_m7_sh_starts_and_stops_against_the_m6_broker():
    text = M7_SH.read_text(encoding="utf-8")
    assert "start" in text and "stop" in text
    assert "VDA_MQTT_PORT" in text
    assert os.access(M7_SH, os.X_OK)
