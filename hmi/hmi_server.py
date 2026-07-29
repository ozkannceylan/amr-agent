#!/usr/bin/env python3
"""amr-agent commissioning HMI — backend.

One process. It is an **OPC UA client** of the S7-1500 and a **local HTTP
server for one operator's browser**, and it is nothing else.

    operator's browser  --HTTP/loopback-->  this process  --OPC UA client-->  PLC
                        <--   /state    --                <-- reads status --

What it does, and the whole of what it does:

* streams the five `Forklift/Hmi/` **requests** and `Forklift/Link/HmiHeartbeat`
  into the server, **all six every cycle regardless of change**
  (`docs/interfaces/opcua-nodes.md` §10.4, §10.8 H1);
* reads `Forklift/Input/`, `Forklift/Output/`, `Forklift/Status/` and
  `Forklift/Link/HmiLinkOk` for the operator's display, and applies them to
  nothing;
* serves one static page and two small JSON endpoints on loopback.

What it does **not** do, per `hmi/README.md` and ADR 0008 D2/D3 — no interlock,
no latch, no timer over a process value, no sequencing, no actuator output, no
verdict the PLC also computes. Teleop routing, the fork-height speed cap, the
fork soft travel limits and the lidar obstacle stop are process logic in the
standard program. **Nothing here is a safety device**: loss of this process is a
degraded mode with a controlled stop owned by the PLC, never a safety event
(invariants 1, 2).

Two timers exist in this file and both are the client's rule about **its own
cycle**, never about a process value:

* the 10 Hz write cadence, and
* the 5 Hz contractual floor of §10.8 H2 — "below the floor the HMI is not a
  supervision source and must stop writing rather than write slowly".

The heartbeat obligation is one-sided. This process makes the counter change
every cycle and that is all it owes. The verdict is the PLC's, compared for
inequality only, never subtracted, never assumed monotonic, wrap-safe, and
`FALSE` until the counter has been seen to change at least once (§10.8 P1–P2).

Dependencies: `asyncua` and the Python standard library. Nothing else, in
particular no ROS 2, no `gz`, no MQTT, no web framework, and nothing imported
from `bridge/` or `fleet/`.

Run:
    ~/amr-hmi-venv/bin/python hmi/hmi_server.py --config hmi/config-double.yaml
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import math
import os
import signal
import statistics
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from asyncua import Client, ua

LOG = logging.getLogger("hmi")

HERE = Path(__file__).resolve().parent
STATIC_DIR = HERE / "static"

# --------------------------------------------------------------------------- #
# The write allowlist, in code.
#
# ADR 0008 D2.5 and `opcua-nodes.md` §10.3: per-TAG writability is enforced by
# the CPU, per-CLIENT scoping is NOT — the commissioned CPU runs with access
# control disabled and security `None`. "Only the HMI writes the Hmi group" is
# therefore policy honoured by this client, exactly as the bridge's allowlist is
# policy honoured by that one. So the allowlist lives here, in code, and the
# config file cannot widen it: a `write:` table naming anything but these six
# paths refuses to start the process.
# --------------------------------------------------------------------------- #

#: The five requests of §10.4 plus the heartbeat of §10.8. BrowseName -> browse
#: path below the `DemoCell` interface node. This is the complete set of nodes
#: this process may write, on this server or any other.
HMI_WRITABLE_PATHS: dict[str, tuple[str, ...]] = {
    "HmiTractionRequest": ("Forklift", "Hmi", "HmiTractionRequest"),
    "HmiSteerRequest": ("Forklift", "Hmi", "HmiSteerRequest"),
    "HmiForkRequest": ("Forklift", "Hmi", "HmiForkRequest"),
    "HmiTeleopRequest": ("Forklift", "Hmi", "HmiTeleopRequest"),
    "HmiResetRequest": ("Forklift", "Hmi", "HmiResetRequest"),
    "HmiHeartbeat": ("Forklift", "Link", "HmiHeartbeat"),
}

#: The five requests, in the order they are written, as one batched call.
REQUEST_ORDER: tuple[str, ...] = (
    "HmiTractionRequest",
    "HmiSteerRequest",
    "HmiForkRequest",
    "HmiTeleopRequest",
    "HmiResetRequest",
)

#: OPC UA variant type per written node — §10.4 and §10.8. Writing a Python
#: float without this would send a Double to a Float tag.
WRITE_VARIANT: dict[str, ua.VariantType] = {
    "HmiTractionRequest": ua.VariantType.Float,
    "HmiSteerRequest": ua.VariantType.Float,
    "HmiForkRequest": ua.VariantType.Float,
    "HmiTeleopRequest": ua.VariantType.Boolean,
    "HmiResetRequest": ua.VariantType.Boolean,
    "HmiHeartbeat": ua.VariantType.UInt16,
}

#: Folders this process may READ. `Forklift/Hmi/` is deliberately absent: the
#: requests are this client's own output and reading them back would invite
#: treating the server's copy as state (§10.1, invariant 10).
READABLE_FOLDERS: frozenset[tuple[str, ...]] = frozenset({
    ("Forklift", "Input"),
    ("Forklift", "Output"),
    ("Forklift", "Status"),
    ("Forklift", "Link"),
})

#: `HmiHeartbeat` is a UInt16 and it WRAPS. The PLC compares for inequality
#: only and never subtracts (§10.8 P1), so the wrap is not an event here either.
HEARTBEAT_MODULUS = 65536

#: `HmiSteerRequest`'s engineering range, `opcua-nodes.md` §10.4: −1.31 … +1.31
#: rad, "the plant's mechanical steer range". An INTERFACE FACT, not a process
#: threshold and not a clamp: the joystick's normalised X axis is expressed in
#: the unit the node declares, and the PLC clamps to the mechanical range
#: regardless (§10.6). It is a named constant beside its citation rather than a
#: config key precisely so it cannot be retuned as if it were a setting.
STEER_REQUEST_MAX_RAD = 1.31

#: Tolerance on an axis arriving from the browser. Anything outside [-1, 1]
#: beyond this is a broken client and is REFUSED, not clamped: §10.4's rule is
#: that an implausible request is a fault rather than a value to clamp, and
#: silently clamping would hide exactly the defect the rule exists to catch.
AXIS_TOLERANCE = 1e-6


class ConfigError(Exception):
    """The configuration file is not one this process will run."""


class WriteRefused(Exception):
    """A write was attempted against a node outside the HMI-writable group."""


class BackendFault(Exception):
    """The backend cannot keep its side of the contract and must stop writing."""


# --------------------------------------------------------------------------- #
# Configuration — a strict subset of YAML, no third-party parser.
# --------------------------------------------------------------------------- #

def load_config(path: Path) -> dict:
    """Parse the subset of YAML `config.yaml` is written in.

    Supported, and nothing else: `#` comments, `key: value`, block nesting by
    indent, block lists of scalars (`- item`), JSON-style inline lists
    (`["a", "b"]`), and the scalars `true`/`false`/`null`/int/float/string.
    Anything else raises `ConfigError` naming the line, because a configuration
    that half-parses is worse than one that refuses.
    """
    root: dict = {}
    # (indent, container) — the innermost container is the last entry.
    stack: list[tuple[int, Any]] = [(-1, root)]
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ConfigError(f"{path}:{lineno}: indentation does not close any block")
        container = stack[-1][1]
        if body.startswith("- "):
            if isinstance(container, dict) and not container:
                # A key opened a block that turns out to be a list: replace the
                # empty dict the key created with a list, in place.
                container = _promote_to_list(stack, root)
            if not isinstance(container, list):
                raise ConfigError(f"{path}:{lineno}: list item inside a mapping")
            container.append(_scalar(body[2:].strip(), path, lineno))
            continue
        if not isinstance(container, dict):
            raise ConfigError(f"{path}:{lineno}: mapping key inside a list")
        key, sep, value = body.partition(":")
        if not sep:
            raise ConfigError(f"{path}:{lineno}: not `key: value` and not `- item`")
        key = key.strip()
        value = value.strip()
        if value:
            container[key] = _scalar(value, path, lineno)
        else:
            child: dict = {}
            container[key] = child
            stack.append((indent, child))
    return root


def _promote_to_list(stack: list[tuple[int, Any]], root: dict) -> list:
    """The block a key opened holds `- items`, so it is a list, not a mapping."""
    indent, empty = stack.pop()
    parent = stack[-1][1]
    for key, value in list(parent.items()):
        if value is empty:
            replacement: list = []
            parent[key] = replacement
            stack.append((indent, replacement))
            return replacement
    raise ConfigError("internal: could not promote a block to a list")


def _strip_comment(line: str) -> str:
    """Drop a `#` comment that is not inside a quoted string."""
    out, quote = [], ""
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            break
        out.append(char)
    return "".join(out)


def _scalar(text: str, path: Path, lineno: int):
    if text.startswith("[") or text.startswith("{") or text.startswith('"'):
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"{path}:{lineno}: {exc}") from exc
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        return text[1:-1]
    lowered = text.lower()
    if lowered in ("true", "false"):
        return lowered == "true"
    if lowered in ("null", "~", ""):
        return None
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text


def validate_config(cfg: dict, path: Path) -> None:
    """Refuse a configuration that would widen the write set or the read set.

    The allowlist is `HMI_WRITABLE_PATHS`, in code. This is the check that keeps
    a config edit from becoming a new write permission.
    """
    nodes = cfg.get("nodes") or {}
    write = dict(nodes.get("write") or {})
    write.update(nodes.get("heartbeat") or {})
    if set(write) != set(HMI_WRITABLE_PATHS):
        raise ConfigError(
            f"{path}: the write set must be exactly the six HMI-writable nodes "
            f"({', '.join(sorted(HMI_WRITABLE_PATHS))}); this file names "
            f"{', '.join(sorted(write)) or '(none)'}"
        )
    for name, browse_path in write.items():
        if tuple(browse_path) != HMI_WRITABLE_PATHS[name]:
            raise ConfigError(
                f"{path}: {name} must be at {'/'.join(HMI_WRITABLE_PATHS[name])}, "
                f"not {'/'.join(browse_path)}"
            )
    for name, browse_path in (nodes.get("read") or {}).items():
        folder = tuple(browse_path[:-1])
        if folder not in READABLE_FOLDERS:
            raise ConfigError(
                f"{path}: {name} reads {'/'.join(browse_path)}, which is outside the "
                f"readable folders {sorted('/'.join(f) for f in READABLE_FOLDERS)} — "
                f"the HMI reads plant state, setpoints and verdicts, nothing else"
            )
    if not (cfg.get("opcua") or {}).get("endpoint"):
        raise ConfigError(f"{path}: opcua.endpoint is required")


# --------------------------------------------------------------------------- #
# The operator's controls — the only mutable state the browser owns.
# --------------------------------------------------------------------------- #

class Controls:
    """The operator's current control positions, shared between the HTTP thread
    and the asyncio write cycle under one lock.

    These are **requests**. Nothing here is an actuator command, and nothing
    here is combined with a plant value: the PLC forms every setpoint from them
    and owns the outcome (ADR 0008 D2.2).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.traction = 0.0        # fraction, §10.4
        self.steer_axis = 0.0      # normalised joystick X; scaled to rad on write
        self.fork = 0.0            # fraction, §10.4
        self.teleop = False        # a LEVEL, §10.4
        self._reset_pulse = False  # one write cycle at TRUE, then FALSE
        self.updated_monotonic = time.monotonic()

    def apply(self, traction: float, steer_axis: float, fork: float,
              teleop: bool, reset: bool) -> None:
        with self._lock:
            self.traction = traction
            self.steer_axis = steer_axis
            self.fork = fork
            self.teleop = teleop
            if reset:
                self._reset_pulse = True
            self.updated_monotonic = time.monotonic()

    def zero(self, reason: str) -> None:
        """The deadman. Release the controls and drop the enable.

        Called when the operator lets go and on the fault path below. It moves
        this client's own control positions to their rest state; it commands no
        actuator and it stops no machine — stopping the machine is the PLC's
        decision (§10.6).
        """
        with self._lock:
            self.traction = 0.0
            self.steer_axis = 0.0
            self.fork = 0.0
            self.teleop = False
            self._reset_pulse = False
            self.updated_monotonic = time.monotonic()
        LOG.info("controls returned to rest (%s)", reason)

    def take_cycle_values(self) -> dict[str, Any]:
        """The five request values for one write cycle.

        The reset request is momentary: it reads `TRUE` in exactly one cycle and
        `FALSE` in every other. The PLC acts on the RISING EDGE and arms that
        edge per link session (§10.4, §10.8 P6) — the edge, the arming and the
        hold are program content, never this client's.
        """
        with self._lock:
            reset = self._reset_pulse
            self._reset_pulse = False
            return {
                "HmiTractionRequest": self.traction,
                "HmiSteerRequest": self.steer_axis * STEER_REQUEST_MAX_RAD,
                "HmiForkRequest": self.fork,
                "HmiTeleopRequest": self.teleop,
                "HmiResetRequest": reset,
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "HmiTractionRequest": self.traction,
                "HmiSteerRequest": self.steer_axis * STEER_REQUEST_MAX_RAD,
                "HmiForkRequest": self.fork,
                "HmiTeleopRequest": self.teleop,
                "HmiResetRequest": False,
            }


# --------------------------------------------------------------------------- #
# Published state — what the browser sees.
# --------------------------------------------------------------------------- #

class Published:
    """A snapshot the HTTP thread reads and the asyncio cycle writes."""

    def __init__(self, endpoint: str) -> None:
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {
            "session": {
                "state": "DOWN",
                "endpoint": endpoint,
                "reason": "starting",
                "connects": 0,
                "requested_session_timeout_ms": None,
                "granted_session_timeout_ms": None,
                "last_good_write_utc": None,
            },
            "heartbeat": {"value": None, "running": False, "writes": 0},
            "write": {
                "cycles": 0, "rtt_last_ms": None, "rtt_median10_ms": None,
                "period_ms_target": None, "period_ms_measured": None,
            },
            "requests": None,
            "metrics": None,
            "limits": {"steer_request_max_rad": STEER_REQUEST_MAX_RAD},
        }
        self._last_good_write_monotonic: float | None = None
        self._metrics_monotonic: float | None = None

    def update(self, **sections: dict) -> None:
        with self._lock:
            for key, value in sections.items():
                if isinstance(value, dict) and isinstance(self._data.get(key), dict):
                    self._data[key].update(value)
                else:
                    self._data[key] = value

    def mark_good_write(self) -> None:
        with self._lock:
            self._last_good_write_monotonic = time.monotonic()
            self._data["session"]["last_good_write_utc"] = _utc_now()

    def mark_metrics(self) -> None:
        with self._lock:
            self._metrics_monotonic = time.monotonic()

    def render(self) -> dict:
        with self._lock:
            data = json.loads(json.dumps(self._data, default=_json_default))
            now = time.monotonic()
            data["session"]["since_last_good_write_ms"] = (
                None if self._last_good_write_monotonic is None
                else round((now - self._last_good_write_monotonic) * 1000.0, 1)
            )
            data["metrics_age_ms"] = (
                None if self._metrics_monotonic is None
                else round((now - self._metrics_monotonic) * 1000.0, 1)
            )
            data["server_time_utc"] = _utc_now()
            return data


def _json_default(value):
    if isinstance(value, (bytes, bytearray)):
        return value.decode("utf-8", "replace")
    return str(value)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


# --------------------------------------------------------------------------- #
# HTTP — one static page and two JSON endpoints, on loopback.
# --------------------------------------------------------------------------- #

class Handler(BaseHTTPRequestHandler):
    server_version = "amr-agent-hmi"
    sys_version = ""
    controls: Controls
    published: Published

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        LOG.debug("http %s", fmt % args)

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            try:
                body = (STATIC_DIR / "index.html").read_bytes()
            except OSError as exc:
                self._json(500, {"error": f"static/index.html: {exc}"})
                return
            self._send(200, body, "text/html; charset=utf-8")
        elif path == "/state":
            self._json(200, self.published.render())
        elif path == "/favicon.ico":
            # Answered, not served. The page carries no asset of any kind and a
            # 404 here would put a permanent error in the operator's console.
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
        else:
            self._json(404, {"error": "no such path"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        if self.path.split("?", 1)[0] != "/control":
            self._json(404, {"error": "no such path"})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length) or b"{}")
            traction = _axis(payload.get("traction", 0.0), "traction")
            steer = _axis(payload.get("steer", 0.0), "steer")
            fork = _axis(payload.get("fork", 0.0), "fork")
            teleop = bool(payload.get("teleop", False))
            reset = bool(payload.get("reset", False))
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            # §10.4: an implausible request is a fault, not a value to clamp.
            self._json(400, {"error": str(exc)})
            return
        self.controls.apply(traction, steer, fork, teleop, reset)
        self._json(200, {"accepted": True})


def _axis(value, name: str) -> float:
    """A normalised control axis, or a refusal."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} is not finite")
    if abs(number) > 1.0 + AXIS_TOLERANCE:
        raise ValueError(f"{name}={number} is outside the normalised range [-1, 1]")
    return max(-1.0, min(1.0, number))


# --------------------------------------------------------------------------- #
# Evidence — one CSV per session, never truncated (LESSONS 2026-07-28).
# --------------------------------------------------------------------------- #

class Evidence:
    COLUMNS = (
        "wall_utc", "monotonic_s", "cycle", "session_state", "hb_value",
        "hb_running", "HmiTractionRequest", "HmiSteerRequest", "HmiForkRequest",
        "HmiTeleopRequest", "HmiResetRequest", "write_rtt_ms",
        "since_last_good_write_ms",
    )

    def __init__(self, stem: str) -> None:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        base, ext = os.path.splitext(stem)
        self.path = f"{base}-{stamp}-pid{os.getpid()}{ext or '.csv'}"
        self._rows: list[list] = []
        self._last_flush = time.monotonic()
        with open(self.path, "x", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerow(self.COLUMNS)
        LOG.info("evidence CSV: %s (one file per session; never truncated)", self.path)

    def row(self, *values) -> None:
        self._rows.append(list(values))
        now = time.monotonic()
        if now - self._last_flush >= 2.0:
            self.flush()
            self._last_flush = now

    def flush(self) -> None:
        if not self._rows:
            return
        with open(self.path, "a", newline="", encoding="utf-8") as handle:
            csv.writer(handle).writerows(self._rows)
        self._rows.clear()


# --------------------------------------------------------------------------- #
# The OPC UA side.
# --------------------------------------------------------------------------- #

class HmiClient:
    """The OPC UA client session, its write cycle and its metrics poll.

    Session states published to the operator:

    ``CONNECTED``     a session is up and the last write cycle landed.
    ``RECONNECTING``  no session; the connector is retrying. The heartbeat is
                      not advancing because there is nowhere to write it, and it
                      resumes from its previous value when the session returns
                      (§10.8 H4 — the counter is not reset across a reconnect).
    ``DOWN``          this process has stopped writing for good. Restarting it
                      is the operator's action.
    """

    def __init__(self, cfg: dict, controls: Controls, published: Published,
                 evidence: Evidence | None, inject_fault_after_s: float | None) -> None:
        self.cfg = cfg
        self.controls = controls
        self.published = published
        self.evidence = evidence
        self.inject_fault_after_s = inject_fault_after_s

        opc = cfg["opcua"]
        self.endpoint = opc["endpoint"]
        self.write_period = float(cfg["cycle"]["write_period_s"])
        self.floor_period = float(cfg["cycle"]["floor_period_s"])
        self.metrics_every = max(1, round(float(cfg["cycle"]["metrics_period_s"])
                                          / self.write_period))

        self.client: Client | None = None
        self._write_nodes: dict[str, Any] = {}
        self._read_nodes: dict[str, Any] = {}
        self._heartbeat = 0
        self._heartbeat_running = False
        self._cycle = 0
        self._connects = 0
        self._rtt = deque(maxlen=10)
        self._periods = deque(maxlen=10)
        self._stop = asyncio.Event()
        #: Set when this process has stopped writing for good. The UI stays up
        #: afterwards so the banner can show DOWN and say why.
        self.terminal_reason: str | None = None
        self._started_monotonic = time.monotonic()

    # -- the one write helper ----------------------------------------------- #

    def _writable(self, name: str):
        """THE ONLY PLACE A NODE IS HANDED OUT FOR WRITING.

        Every write in this process goes through here, on the bridge's allowlist
        precedent. A name outside `HMI_WRITABLE_PATHS` is refused before any
        request reaches the server — per-client scoping is policy and this is
        where the policy is kept (ADR 0008 D2.5).
        """
        if name not in HMI_WRITABLE_PATHS:
            raise WriteRefused(
                f"{name} is not one of the six HMI-writable nodes "
                f"({', '.join(sorted(HMI_WRITABLE_PATHS))}) — refused by the HMI's "
                f"own allowlist, before the request reached the server"
            )
        node = self._write_nodes.get(name)
        if node is None:
            raise WriteRefused(f"{name} is not resolved in this session")
        return node

    async def _write(self, values: dict[str, Any]) -> None:
        names = list(values)
        nodes = [self._writable(name) for name in names]
        variants = [ua.Variant(values[name], WRITE_VARIANT[name]) for name in names]
        await self.client.write_values(nodes, variants)

    # -- session ------------------------------------------------------------ #

    async def _connect(self) -> None:
        opc = self.cfg["opcua"]
        client = Client(url=self.endpoint)
        client.name = opc.get("session_name") or "amr-agent-hmi"
        requested = float(opc.get("requested_session_timeout_ms") or 10000)
        client.session_timeout = requested
        await client.connect()
        self.client = client

        # N2/N3: both indices resolved by URI at every session establishment,
        # each path element qualified with the index of ITS namespace. Neither
        # is hardcoded and neither is derived from the other. A missing URI is a
        # connect failure and the client never browses around it (N4).
        uris = opc["namespace_uris"]
        indices = {}
        for key, uri in uris.items():
            try:
                indices[key] = await client.get_namespace_index(uri)
            except ValueError as exc:
                raise ConnectionError(f"namespace not found: {uri} ({exc})") from exc

        prefix = []
        for element in self.cfg["nodes"]["interface_path"]:
            key, _, browse_name = element.partition(":")
            if key not in indices:
                raise ConnectionError(f"interface_path names unknown namespace {key!r}")
            prefix.append(f"{indices[key]}:{browse_name}")

        interface_index = indices["interface"]
        objects = client.nodes.objects
        self._write_nodes = {}
        for name, path in HMI_WRITABLE_PATHS.items():
            self._write_nodes[name] = await objects.get_child(
                prefix + [f"{interface_index}:{part}" for part in path])
        self._read_nodes = {}
        for name, path in (self.cfg["nodes"].get("read") or {}).items():
            self._read_nodes[name] = await objects.get_child(
                prefix + [f"{interface_index}:{part}" for part in path])

        granted = float(client.session_timeout)
        self._connects += 1
        LOG.info("session established with %s — %d writable node(s), %d read-only "
                 "node(s); browse prefix %s", self.endpoint, len(self._write_nodes),
                 len(self._read_nodes), "/".join(prefix))
        LOG.info("session timeout requested %.0f ms, granted %.0f ms (the granted "
                 "value is the only one any behaviour uses)", requested, granted)
        self.published.update(session={
            "state": "CONNECTED", "reason": None, "connects": self._connects,
            "requested_session_timeout_ms": requested,
            "granted_session_timeout_ms": granted,
        })

    async def _disconnect(self) -> None:
        client, self.client = self.client, None
        self._write_nodes, self._read_nodes = {}, {}
        if client is not None:
            try:
                await client.disconnect()
            except Exception:  # noqa: BLE001 - teardown is best effort
                pass

    # -- the fault path ----------------------------------------------------- #

    async def _final_zeros_attempt(self, reason: str) -> None:
        """One attempt, no retry: the deadman fires, then the current control
        state is written once more, then the heartbeat stops.

        Reconciling the two rules that meet here. §10.8 H5 says the HMI "writes
        no farewell value, zeroes nothing on shutdown and re-publishes nothing
        on reconnect beyond the current state of its controls". This is not a
        farewell value: a backend fault or a dropped session means the browser's
        stream of control updates is no longer being carried, which is a
        RELEASE, so the deadman returns the controls to rest and what is written
        is then literally "the current state of its controls". Nothing here
        stops the machine or claims to — the PLC's watchdog does that, in a
        mandatory `ELSE`, and it is the only thing that does (§10.8 P5).

        A CLEAN SHUTDOWN takes no part in this: H5 is honoured exactly there,
        no farewell value is written, the counter simply stops and the PLC's
        watchdog is left to notice — which is the behaviour the watchdog exists
        for and the one worth demonstrating.
        """
        self.controls.zero(f"deadman: {reason}")
        self._heartbeat_running = False
        if self.client is None:
            LOG.warning("final zeros write attempt skipped, no session (%s)", reason)
            return
        try:
            await asyncio.wait_for(self._write(self.controls.snapshot()), timeout=2.0)
            LOG.warning("final zeros write attempt LANDED (%s); heartbeat stopped", reason)
        except Exception as exc:  # noqa: BLE001 - one attempt, outcome recorded
            LOG.warning("final zeros write attempt FAILED (%s): %s: %s",
                        reason, type(exc).__name__, exc)

    def _enter_down(self, reason: str) -> None:
        self.terminal_reason = reason
        self._heartbeat_running = False
        self.published.update(session={"state": "DOWN", "reason": reason},
                              heartbeat={"running": False})
        LOG.error("HMI has STOPPED WRITING: %s. The link verdict is the PLC's and it "
                  "will go FALSE; restarting this process is the operator's action. "
                  "The UI stays up so the banner can say DOWN and why.", reason)

    # -- the cycle ---------------------------------------------------------- #

    async def run(self) -> None:
        backoff = float(self.cfg["opcua"].get("reconnect_interval_s") or 1.0)
        backoff_max = float(self.cfg["opcua"].get("reconnect_backoff_max_s") or 5.0)
        delay = backoff
        while not self._stop.is_set() and self.terminal_reason is None:
            self.published.update(session={
                "state": "RECONNECTING",
                "reason": f"connecting to {self.endpoint}",
            })
            try:
                await self._connect()
            except Exception as exc:  # noqa: BLE001 - connect failures are retried
                LOG.warning("connect failed: %s: %s (retry in %.1f s)",
                            type(exc).__name__, exc, delay)
                self.published.update(session={
                    "state": "RECONNECTING",
                    "reason": f"{type(exc).__name__}: {exc}",
                })
                await self._sleep(delay)
                delay = min(delay * 2.0, backoff_max)
                continue
            delay = backoff
            try:
                await self._cycle_forever()
            except BackendFault as exc:
                await self._final_zeros_attempt(str(exc))
                await self._disconnect()
                self._enter_down(str(exc))
                return
            except Exception as exc:  # noqa: BLE001 - a dropped session
                reason = f"{type(exc).__name__}: {exc}"
                LOG.warning("session lost: %s", reason)
                await self._final_zeros_attempt(reason)
                await self._disconnect()
                self.published.update(session={"state": "RECONNECTING", "reason": reason},
                                      heartbeat={"running": False})
                await self._sleep(delay)
        await self._disconnect()

    async def _cycle_forever(self) -> None:
        """The 10 Hz write cycle. All six nodes every cycle, heartbeat last."""
        self._heartbeat_running = True
        deadline = time.monotonic()
        previous = None
        while not self._stop.is_set():
            now = time.monotonic()
            if previous is not None:
                self._periods.append(now - previous)
            previous = now

            # §10.8 H2, the contractual floor. Measured over the last ten cycles
            # so one scheduling hiccup is not a stall: below 5 Hz SUSTAINED this
            # process is not a supervision source and must stop writing rather
            # than write slowly. This is the client's rule about its own cycle.
            if len(self._periods) == self._periods.maxlen and \
                    sum(self._periods) > self.floor_period * len(self._periods):
                raise BackendFault(
                    f"write cycle below the 5 Hz contractual floor "
                    f"(§10.8 H2): mean period "
                    f"{sum(self._periods) / len(self._periods) * 1000.0:.0f} ms "
                    f"over the last {len(self._periods)} cycles"
                )
            if (self.inject_fault_after_s is not None
                    and now - self._started_monotonic >= self.inject_fault_after_s):
                raise BackendFault("injected backend fault (TEST SCAFFOLDING)")

            values = self.controls.take_cycle_values()
            started = time.perf_counter()
            # H1/§10.4: all six every cycle, never on change. H3: the heartbeat
            # is written LAST, after the five requests are acknowledged, so an
            # advanced heartbeat implies that cycle's requests landed first.
            await self._write({name: values[name] for name in REQUEST_ORDER})
            self._heartbeat = (self._heartbeat + 1) % HEARTBEAT_MODULUS
            await self._write({"HmiHeartbeat": self._heartbeat})
            rtt_ms = (time.perf_counter() - started) * 1000.0

            self._cycle += 1
            self._rtt.append(rtt_ms)
            self.published.mark_good_write()
            self.published.update(
                session={"state": "CONNECTED", "reason": None},
                heartbeat={"value": self._heartbeat, "running": True,
                           "writes": self._cycle},
                write={
                    "cycles": self._cycle,
                    "rtt_last_ms": round(rtt_ms, 3),
                    "rtt_median10_ms": round(statistics.median(self._rtt), 3),
                    "period_ms_target": round(self.write_period * 1000.0, 1),
                    "period_ms_measured": (
                        None if not self._periods
                        else round(statistics.median(self._periods) * 1000.0, 1)),
                },
                requests=values,
            )
            if self.evidence is not None:
                self.evidence.row(
                    _utc_now(), round(now, 4), self._cycle, "CONNECTED",
                    self._heartbeat, True,
                    values["HmiTractionRequest"], values["HmiSteerRequest"],
                    values["HmiForkRequest"], values["HmiTeleopRequest"],
                    values["HmiResetRequest"], round(rtt_ms, 3),
                    self.published.render()["session"]["since_last_good_write_ms"],
                )

            if self._cycle % self.metrics_every == 0:
                await self._poll_metrics()

            deadline += self.write_period
            sleep_for = deadline - time.monotonic()
            if sleep_for < -self.write_period:
                # The schedule is behind by more than a whole cycle; re-phase
                # rather than run a burst of catch-up writes.
                deadline = time.monotonic()
                sleep_for = 0.0
            await self._sleep(max(0.0, sleep_for))

    async def _poll_metrics(self) -> None:
        """The 5 Hz read-only display poll. Reads only `Forklift/Input/`,
        `Forklift/Output/`, `Forklift/Status/` and `Forklift/Link/HmiLinkOk`;
        applies them to nothing and recomputes none of them (invariant 10)."""
        if not self._read_nodes:
            return
        names = list(self._read_nodes)
        values = await self.client.read_values([self._read_nodes[n] for n in names])
        self.published.update(metrics=dict(zip(names, values)))
        self.published.mark_metrics()

    async def _sleep(self, seconds: float) -> None:
        try:
            await asyncio.wait_for(self._stop.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def request_stop(self) -> None:
        self._stop.set()

    async def wait_stopped(self) -> None:
        await self._stop.wait()


# --------------------------------------------------------------------------- #

async def amain(args: argparse.Namespace) -> int:
    config_path = Path(args.config).resolve()
    cfg = load_config(config_path)
    validate_config(cfg, config_path)
    logging.getLogger().setLevel(
        getattr(logging, str(args.log_level or (cfg.get("logging") or {}).get("level")
                             or "INFO").upper(), logging.INFO))

    controls = Controls()
    published = Published(cfg["opcua"]["endpoint"])
    evidence = Evidence(args.evidence_csv) if args.evidence_csv else None

    Handler.controls = controls
    Handler.published = published
    host = (cfg.get("http") or {}).get("host", "127.0.0.1")
    port = int(args.http_port or (cfg.get("http") or {}).get("port", 8088))
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, name="hmi-http", daemon=True).start()
    LOG.info("HMI UI on http://%s:%d/ — loopback only, one operator, local cell "
             "(ADR 0008 D2.7)", host, port)

    client = HmiClient(cfg, controls, published, evidence, args.inject_fault_after_s)
    loop = asyncio.get_running_loop()
    for signame in ("SIGINT", "SIGTERM"):
        if hasattr(signal, signame):
            try:
                loop.add_signal_handler(getattr(signal, signame), client.request_stop)
            except NotImplementedError:  # Windows
                signal.signal(getattr(signal, signame),
                              lambda *_: client.request_stop())
    if args.run_seconds:
        loop.call_later(args.run_seconds, client.request_stop)

    try:
        await client.run()
        if client.terminal_reason is not None:
            # The write cycle has stopped for good, but the operator still needs
            # to be told so. The page stays served and its banner reads DOWN with
            # the reason, until the operator stops this process.
            LOG.error("UI still served on http://%s:%d/ with the banner reading DOWN. "
                      "No node is being written; the PLC owns what the machine does "
                      "from here.", host, port)
            await client.wait_stopped()
    finally:
        if client.terminal_reason is None:
            # A clean shutdown writes NO farewell value and zeroes nothing (§10.8
            # H5). The counter stops; the PLC's watchdog notices, drives every
            # setpoint to zero in its mandatory ELSE and latches the loss. That is
            # the degraded-mode behaviour of invariant 2, and it belongs to the PLC.
            LOG.info("shutting down cleanly: no farewell value written, nothing "
                     "zeroed on the server (§10.8 H5). The heartbeat stops here and "
                     "the link verdict is the PLC's.")
        else:
            LOG.info("exiting after a stopped write cycle: %s", client.terminal_reason)
        if evidence is not None:
            evidence.flush()
        httpd.shutdown()
    return 0 if client.terminal_reason is None else 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="amr-agent commissioning HMI — OPC UA client of the PLC and a "
                    "local operator UI. Never a server of process data, never a "
                    "safety device.")
    parser.add_argument("--config", default=str(HERE / "config.yaml"))
    parser.add_argument("--http-port", type=int, default=None)
    parser.add_argument("--evidence-csv", default=None,
                        help="per-cycle record; the path is a stem and one file per "
                             "session is written, never truncated")
    parser.add_argument("--run-seconds", type=float, default=None,
                        help="stop cleanly after this many seconds (evidence runs)")
    parser.add_argument("--inject-fault-after-s", type=float, default=None,
                        help="TEST SCAFFOLDING: raise inside the write cycle after N "
                             "seconds, to exercise the backend-fault path. Never used "
                             "in a demonstration run.")
    parser.add_argument("--log-level", default=None)
    args = parser.parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s %(message)s")
    logging.getLogger("asyncua").setLevel(logging.WARNING)
    os.environ.setdefault("PYTHONUNBUFFERED", "1")
    try:
        return asyncio.run(amain(args))
    except (ConfigError, WriteRefused) as exc:
        LOG.error("%s: %s", type(exc).__name__, exc)
        return 2
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
