"""client.py — thin LLM console. Tools only; no broker.

Bound by the fleet/ invariants (no ROS here; the only path to a vehicle
is VDA 5050, and this file is not on that path; losing the fleet
degrades, never endangers) and by ADR 0001 invariants 1, 2, 3, 11.
M7 is not a safety function.

THE CLIENT CANNOT REACH THE BROKER. It calls the four MCP tools
through a backend the caller injects. PENDING is rendered as
"waiting for operator approval". A rejected proposal is not retried
on its own. Model id and endpoint are config. The session budget is
config. Tests use ScriptedModel and never a live model call.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

_HERE = Path(__file__).resolve().parent
_M7 = _HERE.parent
if str(_M7) not in sys.path:
    sys.path.insert(0, str(_M7))

from gateway.tools import TOOLS, dispatch              # noqa: E402

CONFIG_PATH = _HERE / "client.yaml"

WAITING = "waiting for operator approval"
NOT_RETRIED = "NOT_RETRIED"
REJECTED_VERDICTS = frozenset({
    "REJECTED_SCHEMA",
    "REJECTED_POLICY",
    "REJECTED_HUMAN",
})


class BudgetExceeded(RuntimeError):
    """The per-session API-call cap in client.yaml was reached."""


@dataclass
class ClientConfig:
    model_id: str = "claude-sonnet-4-20250514"
    base_url: str = "https://api.anthropic.com"
    max_api_calls: int = 8
    max_turns: int = 8
    max_tokens: int = 1024
    api_key_env: str = "ANTHROPIC_API_KEY"

    @classmethod
    def load(cls, path: Path | None = None) -> "ClientConfig":
        raw = {}
        target = path or CONFIG_PATH
        if target.exists():
            loaded = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        cfg = cls(
            model_id=str(os.environ.get("M7_MODEL_ID") or raw.get(
                "model_id", cls.model_id)),
            base_url=str(os.environ.get("ANTHROPIC_BASE_URL") or raw.get(
                "base_url", cls.base_url)),
            max_api_calls=int(raw.get("max_api_calls", cls.max_api_calls)),
            max_turns=int(raw.get("max_turns", cls.max_turns)),
            max_tokens=int(raw.get("max_tokens", cls.max_tokens)),
        )
        return cfg


@dataclass
class ToolUse:
    name: str
    arguments: dict
    id: str = "tool-0"


@dataclass
class ModelTurn:
    text: str = ""
    tool_uses: list[ToolUse] = field(default_factory=list)


@dataclass
class SessionLog:
    turns: list[ModelTurn] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)
    rendered: list[str] = field(default_factory=list)
    stopped: str = ""


class ScriptedModel:
    """A stand-in for the Messages API. Tests use this. Never the network."""

    def __init__(self, turns: list[ModelTurn]):
        self._turns = list(turns)
        self.calls = 0

    def complete(self, messages, tools) -> ModelTurn:
        self.calls += 1
        if not self._turns:
            return ModelTurn(text="")
        return self._turns.pop(0)


class AnthropicModel:
    """Live Messages API. Instantiated only by main(), never by tests."""

    def __init__(self, config: ClientConfig, api_key: str):
        import anthropic
        self.config = config
        self.calls = 0
        kwargs = {"api_key": api_key}
        if config.base_url:
            kwargs["base_url"] = config.base_url
        self._client = anthropic.Anthropic(**kwargs)

    def complete(self, messages, tools) -> ModelTurn:
        self.calls += 1
        response = self._client.messages.create(
            model=self.config.model_id,
            max_tokens=self.config.max_tokens,
            tools=tools,
            messages=messages,
        )
        text_parts = []
        uses = []
        for block in response.content:
            kind = getattr(block, "type", None)
            if kind == "text":
                text_parts.append(getattr(block, "text", "") or "")
            elif kind == "tool_use":
                uses.append(ToolUse(
                    name=block.name,
                    arguments=dict(block.input or {}),
                    id=getattr(block, "id", "tool-0"),
                ))
        return ModelTurn(text="".join(text_parts), tool_uses=uses)


class DispatchBackend:
    """Call the four tools on a Gateway. No MQTT of its own."""

    def __init__(self, gateway):
        self.gateway = gateway

    def call(self, name: str, arguments: dict) -> dict:
        return dispatch(self.gateway, name, arguments)


def anthropic_tools() -> list[dict]:
    return [
        {
            "name": spec["name"],
            "description": spec["description"],
            "input_schema": spec["inputSchema"],
        }
        for spec in TOOLS
    ]


def present_result(name: str, result: dict) -> dict:
    """PENDING is a wait for a human, never a cue to retry."""
    payload = dict(result)
    if name == "propose_transport" and payload.get("verdict") == "PENDING":
        payload["message"] = WAITING
    return payload


class ConsoleClient:
    """Tool-use loop. The model never sees a broker handle."""

    def __init__(self, backend, model, config: ClientConfig | None = None):
        self.backend = backend
        self.model = model
        self.config = config or ClientConfig.load()
        self._rejected_keys: set[str] = set()

    def run(self, user_text: str) -> SessionLog:
        log = SessionLog()
        messages = [{"role": "user", "content": user_text}]
        tools = anthropic_tools()
        for _ in range(self.config.max_turns):
            if getattr(self.model, "calls", 0) >= self.config.max_api_calls:
                raise BudgetExceeded(
                    "session budget exhausted (max_api_calls={})".format(
                        self.config.max_api_calls))
            turn = self.model.complete(messages, tools)
            log.turns.append(turn)
            if turn.text:
                log.rendered.append(turn.text)
            if not turn.tool_uses:
                log.stopped = "text"
                return log
            tool_content = []
            for use in turn.tool_uses:
                result = self._call_tool(use.name, use.arguments)
                log.tool_results.append(result)
                if result.get("message") == WAITING:
                    log.rendered.append(WAITING)
                tool_content.append({
                    "type": "tool_result",
                    "tool_use_id": use.id,
                    "content": json.dumps(result, default=str),
                })
            messages.append({"role": "assistant", "content": [
                {"type": "tool_use", "id": use.id, "name": use.name,
                 "input": use.arguments}
                for use in turn.tool_uses
            ]})
            messages.append({"role": "user", "content": tool_content})
        log.stopped = "max_turns"
        return log

    def _call_tool(self, name: str, arguments: dict) -> dict:
        args = arguments or {}
        if name == "propose_transport":
            key = args.get("idempotency_key")
            if isinstance(key, str) and key in self._rejected_keys:
                return {
                    "verdict": NOT_RETRIED,
                    "duplicate": False,
                    "message": "a rejected proposal is not retried by the client",
                    "idempotency_key": key,
                }
        result = present_result(name, self.backend.call(name, args))
        if name == "propose_transport":
            key = args.get("idempotency_key")
            if (isinstance(key, str)
                    and result.get("verdict") in REJECTED_VERDICTS):
                self._rejected_keys.add(key)
        return result


def serve(config: ClientConfig, model, host: str, port: int) -> int:
    """Host the gateway in this process and run the tool-use loop.

    One pending set. approve.py talks to the same broker. This function
    is the only place the console process starts MQTT, and it does it
    through the gateway, not through this module.
    """
    from gate.audit import AuditLog
    from gate.policy import load_policy
    from gate.proposal import Gate
    from gateway.server import Gateway

    _m7 = Path(__file__).resolve().parents[1]
    gate = Gate(
        policy=load_policy(),
        audit=AuditLog(audit_dir=_m7 / "audit"),
    )
    gateway = Gateway(gate, host=host, port=port)
    gateway.start_mqtt()
    try:
        if model is None:
            while True:
                __import__("time").sleep(1.0)
            return 0
        user = sys.stdin.read() if not sys.stdin.isatty() else ""
        if not user.strip():
            sys.stderr.write(
                "m7 console: gateway is up on {}:{} — type a request "
                "or pipe one on stdin\n".format(host, port))
            if sys.stdin.isatty():
                user = input("m7> ")
        if user.strip():
            log = ConsoleClient(
                DispatchBackend(gateway), model, config).run(user.strip())
            for line in log.rendered:
                print(line)
        else:
            while True:
                __import__("time").sleep(1.0)
        return 0
    except KeyboardInterrupt:
        return 0
    finally:
        gateway.stop_mqtt()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="M7 LLM console — tools only, no broker of its own")
    parser.add_argument("--config", default=str(CONFIG_PATH))
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST",
                                                         "127.0.0.1"))
    parser.add_argument("--port", type=int,
                        default=int(os.environ.get("VDA_MQTT_PORT", "1883")))
    parser.add_argument(
        "--serve", action="store_true",
        help="start the gateway MQTT client in this process and run the loop")
    parser.add_argument(
        "--mqtt-only", action="store_true",
        help="with --serve, hold the gateway up and do not call the model")
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config = ClientConfig.load(Path(args.config))
    model = None
    if not args.mqtt_only:
        key = os.environ.get(config.api_key_env, "")
        if not key:
            sys.stderr.write(
                "no ${} — starting the gateway only "
                "(scripted tests never need a key)\n".format(
                    config.api_key_env))
            args.mqtt_only = True
        else:
            model = AnthropicModel(config, key)
    if not args.serve and model is None:
        sys.stderr.write(
            "nothing to do: pass --serve to start the gateway, "
            "or set {} for a live model loop\n".format(config.api_key_env))
        return 2
    return serve(config, None if args.mqtt_only else model,
                 args.host, args.port)


if __name__ == "__main__":
    raise SystemExit(main())
