#!/usr/bin/env python3
"""amr-agent commissioning HMI — backend.

One process. It is an **OPC UA client** of the S7-1500 and a **local HTTP
server for one operator's browser**, and it is nothing else.

    operator's browser  --HTTP/loopback-->  this process  --OPC UA client-->  PLC
                        <--   /state    --                <-- reads status --

What it does, and the whole of what it does:

* streams the five `Forklift/Hmi/` **requests**, `Forklift/Mode/
  HmiDriveModeRequest`, `Forklift/ProcessStop/HmiProcessStopRequest` and
  `Forklift/Link/HmiHeartbeat` into the server, **all eight every cycle
  regardless of change** (`docs/interfaces/opcua-nodes.md` §10.4, §12.1,
  §10.8 H1), the heartbeat last (H3);
* reads `Forklift/Input/`, `Forklift/Output/`, `Forklift/Status/`,
  `Forklift/Link/HmiLinkOk` and the §12 groups `Forklift/Mode/`,
  `Forklift/Envelope/`, `Forklift/Vehicle/` and `Forklift/ProcessStop/` for the
  operator's display, and applies them to nothing; also reads the four
  `Forklift/Safety/` F-CPU mirrors of `docs/interfaces/opcua-nodes.md` §11,
  when the server carries them — display diagnostics only, feeding no logic
  here either (§11.3), and their absence is graceful, never a connect error
  (§11.6);
* serves one static page and two small JSON endpoints on loopback.

**v2a (m5-28), built to `hmi/V2A-DESIGN.md`.** Two controls are added and both
are **standing** rather than deadman controls: the mode selector (§5.1) and the
operator's process stop (§4). Neither is returned to rest by the H6 page window
and neither is re-armed per page session — returning the selector to None would
command a mode exit no operator made, and both directions of releasing or
engaging a stop on a page loss would fabricate an operator act (V2A-DESIGN
PS-B, PS-C). The process stop **boots ENGAGED** to match the server's §12.8
start value: the first `FALSE` this process ever writes is an operator's
release on the page (PS-A). Nothing about the mode is decided here — no timer,
no debounce, no verdict; every mode rendering is a pure function of the values
read on one poll, and the only party that times a mode disagreement is the PLC
(SPEC §14.7).

What it does **not** do, per `hmi/README.md` and ADR 0008 D2/D3 — no interlock,
no latch, no timer over a process value, no sequencing, no actuator output, no
verdict the PLC also computes. Teleop routing, the fork-height speed cap, the
fork soft travel limits and the lidar obstacle stop are process logic in the
standard program. **Nothing here is a safety device**: loss of this process is a
degraded mode with a controlled stop owned by the PLC, never a safety event
(invariants 1, 2).

Three timers exist in this file and every one of them is the client's rule about
**its own cycle or its own input channel**, never about a process value:

* the 10 Hz write cadence,
* the 5 Hz contractual floor of §10.8 H2 — "below the floor the HMI is not a
  supervision source and must stop writing rather than write slowly", and
* the window over the operator's page, `UI_POLL_STALE_TIME` (§10.8 H6): the
  page's own `GET /state` is the beacon, and when it has been silent for five
  poll periods the controls go to rest **while the write cycle and the heartbeat
  continue**. Nothing latches, and each Bool is carried again only after the page
  has been seen to send it low.

The test §10.1 states is what a timer watches. All three watch this process —
its cycle and its own input channel — and none watches the plant or recomputes a
verdict the PLC also computes.

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
import urllib.error
import urllib.parse
import urllib.request
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
# config file cannot widen it: a `write:` table naming anything but these eight
# paths refuses to start the process.
# --------------------------------------------------------------------------- #

#: The five requests of §10.4, the two §12.1 additions and the heartbeat of
#: §10.8 — **eight**. BrowseName -> browse path below the `DemoCell` interface
#: node. This is the complete set of nodes this process may write, on this
#: server or any other. It grew by exactly the two §12 rows and by nothing else
#: (V2A-DESIGN §2.1); the mechanism is unchanged.
HMI_WRITABLE_PATHS: dict[str, tuple[str, ...]] = {
    "HmiTractionRequest": ("Forklift", "Hmi", "HmiTractionRequest"),
    "HmiSteerRequest": ("Forklift", "Hmi", "HmiSteerRequest"),
    "HmiForkRequest": ("Forklift", "Hmi", "HmiForkRequest"),
    "HmiTeleopRequest": ("Forklift", "Hmi", "HmiTeleopRequest"),
    "HmiResetRequest": ("Forklift", "Hmi", "HmiResetRequest"),
    "HmiDriveModeRequest": ("Forklift", "Mode", "HmiDriveModeRequest"),
    "HmiProcessStopRequest": ("Forklift", "ProcessStop", "HmiProcessStopRequest"),
    "HmiHeartbeat": ("Forklift", "Link", "HmiHeartbeat"),
}

#: The seven non-heartbeat writes, in the order they are written, as one
#: batched call. The heartbeat follows them in a second call (H3), so an
#: advanced heartbeat implies that cycle's requests landed first.
REQUEST_ORDER: tuple[str, ...] = (
    "HmiTractionRequest",
    "HmiSteerRequest",
    "HmiForkRequest",
    "HmiTeleopRequest",
    "HmiResetRequest",
    "HmiDriveModeRequest",
    "HmiProcessStopRequest",
)

#: OPC UA variant type per written node — §10.4, §10.8 and §12. Writing a
#: Python float without this would send a Double to a Float tag.
WRITE_VARIANT: dict[str, ua.VariantType] = {
    "HmiTractionRequest": ua.VariantType.Float,
    "HmiSteerRequest": ua.VariantType.Float,
    "HmiForkRequest": ua.VariantType.Float,
    "HmiTeleopRequest": ua.VariantType.Boolean,
    "HmiResetRequest": ua.VariantType.Boolean,
    "HmiDriveModeRequest": ua.VariantType.UInt16,
    "HmiProcessStopRequest": ua.VariantType.Boolean,
    "HmiHeartbeat": ua.VariantType.UInt16,
}

#: Folders this process may READ. `Forklift/Hmi/` is deliberately absent: the
#: requests are this client's own output and reading them back would invite
#: treating the server's copy as state (§10.1, invariant 10). `Forklift/Mode/`
#: IS readable, but only for `ForkliftDriveModeActive` — the config's read table
#: never names `HmiDriveModeRequest`, for the same reason and under §12.3 M2.
READABLE_FOLDERS: frozenset[tuple[str, ...]] = frozenset({
    ("Forklift", "Input"),
    ("Forklift", "Output"),
    ("Forklift", "Status"),
    ("Forklift", "Link"),
    ("Forklift", "Safety"),
    ("Forklift", "Mode"),
    ("Forklift", "Envelope"),
    ("Forklift", "Vehicle"),
    ("Forklift", "ProcessStop"),
})

#: The two nodes this client writes that it must never read back as state
#: (§12.3 **M2**: *a consumer displays or acts on the node it read, never on
#: what it sent*). A config naming either in its read table refuses to start.
NEVER_READ_BACK: frozenset[str] = frozenset({
    "HmiDriveModeRequest", "HmiProcessStopRequest",
})

#: `Forklift/Mode/` — the §12.3 encoding, defined once in the node model and
#: re-encoded nowhere. Display only: this process never decides a mode from it.
DRIVE_MODE_NAMES: dict[int, str] = {0: "None", 1: "Teleop", 2: "Autonomous"}

#: `Forklift/Safety/` — `opcua-nodes.md` §11.2. Four read-only F-CPU mirrors.
#: None of them is ever written by this process (§11.4 MR1 — no client writes
#: any of the four, and this file has no code path that tries), and none of
#: them is combined into anything here: §11.3's "zero PLC readers" restated one
#: layer up as zero HMI logic readers either. This client displays all four and
#: decides nothing from them (invariant 10).
SAFETY_MIRROR_NAMES: tuple[str, ...] = (
    "EStopDemand", "ZoneStopDemand", "SafetyResetRequired", "SafetyResetFault",
)

#: Folders whose ABSENCE at connect time is not a connect failure: the group is
#: reported to the operator as "not present" instead of causing a reconnect
#: loop (§11.6 — "an absent mirror renders as absent, never as clear"; §11.8
#: item 5 — the F-layer fallback needs no document edit, and this is the code
#: side of that). Every OTHER readable folder remains a hard requirement exactly
#: as before this group existed: its absence is a genuine connect failure.
OPTIONAL_READ_FOLDERS: frozenset[tuple[str, ...]] = frozenset({
    ("Forklift", "Safety"),
})

#: The `opcua-nodes.md` §12 folders. Their absence is a REQUIRED node missing
#: and a genuine connect failure — but against the commissioned CPU it is the
#: DESIGNED failure of `hmi/config.yaml` rather than a defect, so a browse that
#: fails inside one of them says so at the point of failure (m5-29 finding 2).
SECTION_12_FOLDERS: frozenset[str] = frozenset({
    "Mode", "Envelope", "Vehicle", "ProcessStop",
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

#: The page's unconditional `GET /state` period, `static/index.html`. Named here
#: because the window below is derived FROM it, and the two must be read
#: together: if the page's poll period changes, the window is re-derived from the
#: new period rather than the millisecond being quietly reinterpreted.
UI_POLL_PERIOD_S = 0.200

#: §10.8 H6's `UI_POLL_STALE_TIME`. **Five poll periods**, `1.0 s`. The rule is
#: the MULTIPLE, not the number: a browser honours no floor — `setInterval` is
#: best effort and a beat can be lost to the main thread, to garbage collection
#: or to the operating system — so the multiple absorbs jitter the watched side
#: cannot bound, which is why it is five here where the PLC's `HMI_STALE_TIME`
#: may use three (§10.8 P3 has H2's contractual floor to lean on; this does not).
#:
#: It is its own constant and shares nothing with `HMI_STALE_TIME`: the two watch
#: different parties across different transports, one from the PLC and one from
#: inside this process, and retuning either must not silently retune the other
#: (§10.8 P4's principle, one level up). It lives here in code, beside its
#: derivation, rather than in the config file, precisely so it cannot be retuned
#: as if it were a setting.
UI_POLL_STALE_TIME = 5.0 * UI_POLL_PERIOD_S

#: The age past which this process's OWN LAST GOOD WRITE stops counting as
#: write health, published on `/state` so the page renders the process stop
#: UNAVAILABLE without inventing a millisecond of its own (V2A-DESIGN §8: "the
#: backend publishes every window"; m5-29 finding 4). It is a window over THIS
#: process's own write channel — the same class of fact as `UI_POLL_STALE_TIME`
#: over its own page — and it is not a window over any plant value or any PLC
#: verdict (§10.1). Twenty write cycles at the 10 Hz cadence: long enough that
#: a scheduling hiccup is not a fault, short enough that a hung write surfaces
#: to the operator while the session still claims to be up.
WRITE_HEALTH_STALE_TIME = 2.0

# --------------------------------------------------------------------------- #
# v2b (m5-53) — the map pane's window onto the monitoring plane.
#
# `hmi/V2B-DESIGN.md` §2: the page reads `viz/` THROUGH this process, over
# loopback, and re-serves it under this origin. That layer sends no CORS header
# and must not be edited so the HMI can reach it, so the `MON --o HMI` edge of
# CLAUDE.md §3 is realised in this backend rather than in the browser. Both
# halves are the HMI.
#
# Nothing below is a command path. This process sends `GET` toward the
# monitoring service and nothing else, sends no request body, and no byte
# produced here enters a vehicle domain.
# --------------------------------------------------------------------------- #

#: Hard ceiling on one fetch of the monitoring service. It runs on an HTTP
#: handler thread of the already-threaded server, never on the asyncio loop that
#: owns the OPC UA session, and it is bounded so a hung monitoring service can
#: never stall a write cycle, a heartbeat or a keep-alive (LESSONS 2026-07-29:
#: a harness never blocks the event loop of the session it observes).
MONITOR_FETCH_TIMEOUT_S = 1.5

#: The map pane's own poll period, published to the page so the page invents no
#: cadence of its own. Deliberately slower than the 200 ms `/state` poll: this
#: pane's numbers are AGES read from the monitoring service and measured by it
#: at the instant it answers, so a slower poll makes nothing look fresher — it
#: only means the age shown is at most one period behind, which the page also
#: displays, separately and with its owner named.
MONITOR_POLL_PERIOD_S = 0.5

#: THE DISPLAY RAMP, and the one place in v2b where a millisecond appears.
#: `V2B-DESIGN.md` §4.2/§4.3 argue it in full; the short form:
#:
#: * the age is READ from the monitoring service, which originates it — this
#:   process runs no clock over any plant signal;
#: * no PLC node carries a pose, a pose age or a localization verdict, so there
#:   is no verdict here that the PLC also computes;
#: * nothing rides on it. It changes pixels. It gates no control, latches
#:   nothing, enters no request and is read by no other part of the page;
#: * it is not a statement about the estimate's quality — only about how old
#:   this page's information is.
#:
#: Between the two endpoints the vehicle marker fades and converts from a
#: filled marker to a hollow hatched one; past the upper endpoint it is
#: labelled a LAST KNOWN POSITION. Every step of the ramp under-claims.
#:
#: THESE TWO ARE MEASURED, and they are the only numbers in this file that are.
#: m5-53 chose 1000 / 5000 as display values because no capture of a MOVING
#: vehicle existed. m5-53b took that measurement against the real monitoring
#: service and a real forklift (EVIDENCE_HMI.md §K.4, n = 26 / 77 / 37 across
#: three driving runs) and the owner ruled the correction in on 2026-08-06.
#:
#: WHAT THE MEASUREMENT SAID. The localization is DISTANCE-TRIGGERED, not
#: periodic: `agv/forklift/amcl.yaml` sets `update_min_d: 0.25`, and every
#: measured interval covered 0.28-0.30 m of ground at every speed. So
#:
#:      pose inter-arrival  =  update_min_d / speed
#:
#: and a threshold written in milliseconds here is a COVERT STATEMENT ABOUT A
#: SPEED. The old 1000 ms meant "fade below 0.25 m/s" and sat at the MEDIAN of
#: brisk driving (831 / 910 ms measured), so the page called a vehicle that was
#: being driven normally stale about half the time. The old 5000 ms meant "call
#: it a last known position below 0.05 m/s" and was crossed outright by a
#: vehicle genuinely being driven at 0.15 m/s (p90 6010 ms, max 6446 ms).
#:
#: 2500 clears the measured maximum of the brisk population (2099 ms); 8000
#: clears the slow population's maximum (6446 ms), so LAST KNOWN POSITION now
#: means "not being driven" rather than "being driven slowly".
#:
#: THE COST, CARRIED HERE BESIDE THE NUMBERS RATHER THAN LEFT IN A REPORT.
#: Widening a ramp makes this page claim MORE. If the localization dies while
#: the vehicle keeps moving at 0.35 m/s, the marker is now drawn solid for
#: 2.5 s rather than 1.0 s — up to 0.88 m of undisclosed travel instead of
#: 0.35 m. That is the whole price of the change and it was accepted knowingly.
#: Both of the old values' failures under-claimed; this is the first choice here
#: that trades any of that margin away, which is why it needed an owner ruling
#: and not an agent's arithmetic.
#:
#: DO NOT RE-TUNE THESE BLIND. Because the inter-arrival is a function of
#: speed, NO fixed pair survives the whole range this vehicle can drive. At the
#: closed-loop smoother's from-rest floor of 0.025 m/s (LESSONS 2026-08-05
#: #124) the inter-arrival is ~10 s, past 8000 ms, so a creeping vehicle still
#: crosses the ramp — and that is correct, because the page cannot tell creeping
#: from standing and says so rather than guessing. Any future change re-derives
#: both endpoints from `update_min_d` and a NAMED SPEED, and re-measures if
#: `update_min_d` moves.
#:
#: A standing vehicle always crosses this ramp, because AMCL publishes only on a
#: filter update. That is not a defect: it is the truth about what this page
#: knows, and a marker that stayed solid while the vehicle stood still would be
#: flattering the data.
POSE_AGE_RAMP_START_MS = 2500.0
POSE_AGE_RAMP_FULL_MS = 8000.0

#: Host names the monitoring service may be addressed at. The monitoring plane
#: is local to the operator's machine; it is never a remote transport and never
#: the tailnet (invariant 8). A `monitor.base_url` outside this set refuses to
#: start the process, on the precedent of `tools/check_hmi_writes.py` refusing a
#: non-loopback endpoint outright.
LOOPBACK_HOSTS: frozenset[str] = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


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
            f"{path}: the write set must be exactly the eight HMI-writable nodes "
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
        if browse_path[-1] in NEVER_READ_BACK:
            raise ConfigError(
                f"{path}: {name} reads {'/'.join(browse_path)}, which this client "
                f"WRITES. A consumer displays the node it read, never what it sent "
                f"(opcua-nodes.md §12.3 M2) — the defect that rule prevents is "
                f"invisible precisely when the PLC has refused the request"
            )
        if folder not in READABLE_FOLDERS:
            raise ConfigError(
                f"{path}: {name} reads {'/'.join(browse_path)}, which is outside the "
                f"readable folders {sorted('/'.join(f) for f in READABLE_FOLDERS)} — "
                f"the HMI reads plant state, setpoints and verdicts, nothing else"
            )
    if not (cfg.get("opcua") or {}).get("endpoint"):
        raise ConfigError(f"{path}: opcua.endpoint is required")
    base = (cfg.get("monitor") or {}).get("base_url")
    if base:
        parsed = urllib.parse.urlsplit(str(base))
        if parsed.scheme != "http" or (parsed.hostname or "") not in LOOPBACK_HOSTS:
            raise ConfigError(
                f"{path}: monitor.base_url must be plain http on a loopback host "
                f"{sorted(LOOPBACK_HOSTS)}; this file names {base!r}. The monitoring "
                f"plane is local to the operator's machine — it is never a remote "
                f"transport and never the tailnet (invariant 8)"
            )


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
        self.reset = False         # a LEVEL too: TRUE for as long as the operator
        #                            holds the button, FALSE when it is released.
        #                            §10.4 — the PLC acts on the rising edge and
        #                            the hold is the operator's, not this client's.
        #: A press shorter than one write cycle would otherwise never reach the
        #: wire: `pointerdown` and `pointerup` can both land inside one 100 ms
        #: cycle. The flag makes a tap carry exactly one `TRUE` cycle, which is
        #: what the momentary implementation gave and what a physical button
        #: gives. It is cleared by the cycle that carried it — no timer, and no
        #: window over anything but this client's own input channel.
        self._reset_tap = False
        #: §10.8 H6's release rule, P6's per-session arming one level up. A Bool
        #: is carried again only once the page has been seen to send it LOW, so a
        #: page that thaws with the enable still asserted cannot produce a
        #: `FALSE -> TRUE` the operator never made. `True` at start: a page that
        #: has never been dropped is armed, and the PLC's own P6 guard is the
        #: independent one that covers link-up.
        self._teleop_armed = True
        self._reset_armed = True
        #: **The two STANDING controls of v2a.** Neither is a deadman control
        #: and neither is armed per page session (V2A-DESIGN PS-B, PS-C, §5.1):
        #:
        #: * `process_stop` boots **`TRUE`** (PS-A), matching the server's
        #:   §12.8 start value. A freshly connected HMI must not flip a
        #:   non-permissive server value the operator has not touched, so the
        #:   first `FALSE` this process ever writes is an operator's release on
        #:   the page. It holds its last operator-set value through a page loss:
        #:   releasing it would invent the permissive act, and engaging it on
        #:   every browser hiccup would latch a stop nobody requested. It needs
        #:   no arming because it carries no dangerous edge — the PLC latches on
        #:   LEVEL `TRUE`, a phantom engage is non-permissive, and a phantom
        #:   release clears nothing by itself.
        #: * `drive_mode` boots `0` (None) and holds its last operator-set
        #:   value too: returning it to None would command a mode exit (X3) no
        #:   operator made.
        #:
        #: Neither is touched by `_to_rest`, and that omission is the rule.
        self.process_stop = True
        self.drive_mode = 0
        self.updated_monotonic = time.monotonic()

    def apply(self, traction: float, steer_axis: float, fork: float,
              teleop: bool, reset: bool) -> None:
        with self._lock:
            self.traction = traction
            self.steer_axis = steer_axis
            self.fork = fork
            # Both Bools are STORED as the page sent them and MASKED at write
            # time by their arming flag, so /state can show the operator that a
            # control is being held down rather than silently rewriting it.
            self.teleop = teleop
            self.reset = reset
            if not teleop:
                self._teleop_armed = True     # seen low: carried again from here
            if not reset:
                self._reset_armed = True
            elif self._reset_armed:
                self._reset_tap = True        # a press this short still lands
            self.updated_monotonic = time.monotonic()

    def set_process_stop(self, engaged: bool) -> None:
        """The operator's two-state process stop — a LEVEL, standing.

        Nothing is decided here. The PLC latches on the level, and no client
        clears a latch by writing a node (§12.7 PS1). Releasing this is what
        makes the reset's live-world term true (PS3); it is not itself a reset.
        """
        with self._lock:
            self.process_stop = bool(engaged)
            self.updated_monotonic = time.monotonic()

    def set_drive_mode(self, mode: int) -> None:
        """The selector position — a LEVEL, standing, in the §12.3 encoding.

        `0` None, `1` Teleop, `2` Autonomous. Refused if it is anything else:
        §12.3's rule is that a value outside `{0, 1, 2}` is a broken writer and
        not a mode to clamp, and this client will not be that writer.
        """
        value = int(mode)
        if value not in DRIVE_MODE_NAMES:
            raise ValueError(
                f"drive_mode={mode} is outside the §12.3 encoding "
                f"{{0 None, 1 Teleop, 2 Autonomous}}")
        with self._lock:
            self.drive_mode = value
            self.updated_monotonic = time.monotonic()

    def _to_rest(self) -> None:
        """Every DEADMAN control at its rest position. Caller holds the lock.

        `process_stop` and `drive_mode` are deliberately absent: they are
        standing controls and a page loss is not an operator act (PS-B, §5.1).
        """
        self.traction = 0.0
        self.steer_axis = 0.0
        self.fork = 0.0
        self.teleop = False
        self.reset = False
        self._reset_tap = False
        self.updated_monotonic = time.monotonic()

    def zero(self, reason: str) -> None:
        """The deadman. Release the controls and drop the enable.

        Called when the operator lets go and on the fault path below. It moves
        this client's own control positions to their rest state; it commands no
        actuator and it stops no machine — stopping the machine is the PLC's
        decision (§10.6).
        """
        with self._lock:
            self._to_rest()
        LOG.info("controls returned to rest (%s)", reason)

    def release_for_page_loss(self, reason: str) -> None:
        """§10.8 H6: the same deadman, plus the release rule for the two Bools.

        The page has stopped talking, so its stream of control updates is no
        longer being carried — a RELEASE, exactly as in H5's fault path, and the
        controls go to rest. What H6 adds is the recovery rule: the three Reals
        are carried again as soon as the page posts, because they move nothing
        while `ForkliftTeleopActive` is `FALSE`, while each Bool waits until the
        page has been seen to send it low.

        Nothing latches here and nothing is demanded of the operator. This is
        invariant 2's degraded-mode pattern at the operator boundary; it is
        process behaviour and **not a safety function** (invariant 1, ADR 0008
        D3), and stopping the machine remains the PLC's.
        """
        with self._lock:
            self._to_rest()
            self._teleop_armed = False
            self._reset_armed = False
        LOG.warning("the operator's page has gone quiet (%s): all five requests to "
                    "rest, the enable included. The write cycle and the heartbeat "
                    "CONTINUE — this process is healthy, the page is not. Nothing "
                    "latches; each Bool is carried again once the page has been seen "
                    "to send it low (§10.8 H6).", reason)

    def take_cycle_values(self) -> dict[str, Any]:
        """The five request values for one write cycle.

        The reset request is a **level**: `TRUE` in every cycle for as long as
        the operator holds the button, `FALSE` from the cycle after release. The
        PLC acts on the RISING EDGE and arms that edge per link session (§10.4,
        §10.8 P6) — the edge, the arming and the hold are program content, never
        this client's, and a reset held across the moment its cause disappears is
        exactly what `plc/forklift/SPEC.md` §11 T5.4 asks an operator to produce.
        """
        with self._lock:
            reset = self._reset_armed and (self.reset or self._reset_tap)
            if reset:
                self._reset_tap = False       # this cycle carried it
            return {
                "HmiTractionRequest": self.traction,
                "HmiSteerRequest": self.steer_axis * STEER_REQUEST_MAX_RAD,
                "HmiForkRequest": self.fork,
                "HmiTeleopRequest": self.teleop and self._teleop_armed,
                "HmiResetRequest": reset,
                "HmiDriveModeRequest": self.drive_mode,
                "HmiProcessStopRequest": self.process_stop,
            }

    def arming(self) -> dict[str, bool]:
        with self._lock:
            return {"teleop": self._teleop_armed, "reset": self._reset_armed}

    def standing(self) -> dict[str, Any]:
        """What the page adopts on load (PS-D), so a reload silently engages
        and releases nothing."""
        with self._lock:
            return {
                "process_stop": self.process_stop,
                "drive_mode": self.drive_mode,
                "drive_mode_name": DRIVE_MODE_NAMES[self.drive_mode],
            }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "HmiTractionRequest": self.traction,
                "HmiSteerRequest": self.steer_axis * STEER_REQUEST_MAX_RAD,
                "HmiForkRequest": self.fork,
                "HmiTeleopRequest": self.teleop and self._teleop_armed,
                "HmiResetRequest": False,
                # The two standing controls keep their operator-set values in
                # the final write too: the deadman is not an operator act, and
                # writing a released stop here would be this process inventing
                # one on its way out (PS-B).
                "HmiDriveModeRequest": self.drive_mode,
                "HmiProcessStopRequest": self.process_stop,
            }


# --------------------------------------------------------------------------- #
# The operator's page, as a liveness beacon — §10.8 H6.
# --------------------------------------------------------------------------- #

class PageLiveness:
    """One timestamp, refreshed by **every** request the page makes on this
    process's loopback endpoint.

    What is watched is the *page*, not the operator. The page's unconditional
    `GET /state` at 5 Hz is what guarantees a request arrives while no control is
    being touched — an operator holding the reset button for ten seconds posts
    nothing at all, and the poll is what carries the "still here" in between. Any
    request refreshes it: the page load, the poll, the `POST /control`, even the
    favicon the browser asks for by itself.

    **What this proves and what it does not.** It proves the page is alive. It
    does not prove a person is in front of it: an operator who walks away from a
    live browser leaves the poll ticking, and no timer this layer can run would
    notice. What H6 closes is the crashed, frozen, closed or disconnected
    browser; the remainder is stated rather than covered.

    The timestamp starts at process start, so a backend nobody has opened a page
    against goes stale on its own after one window and holds its requests at
    rest — which is the honest reading of "no page is talking to me".
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_monotonic = time.monotonic()
        self._last_utc = _utc_now()
        self._requests = 0

    def seen(self) -> None:
        with self._lock:
            self._last_monotonic = time.monotonic()
            self._last_utc = _utc_now()
            self._requests += 1

    def age(self, now: float | None = None) -> float:
        with self._lock:
            return (time.monotonic() if now is None else now) - self._last_monotonic

    def last_utc(self) -> str:
        with self._lock:
            return self._last_utc

    def requests(self) -> int:
        with self._lock:
            return self._requests


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
                # The window the page renders the stop UNAVAILABLE past, so it
                # invents no number of its own (V2A-DESIGN §8).
                "stale_after_ms": round(WRITE_HEALTH_STALE_TIME * 1000.0, 1),
            },
            "requests": None,
            "metrics": None,
            # The two STANDING controls, as this backend holds them. The page
            # adopts these on load and changes them only on an operator action
            # (V2A-DESIGN PS-D): a reload must silently engage or release
            # nothing. `process_stop` starts `True` — PS-A.
            "controls": {
                "process_stop": True, "drive_mode": 0, "drive_mode_name": "None",
            },
            # This process's bookkeeping about ITS OWN read poll — the same
            # class of fact as `page` below, on the other transport. It is what
            # lets the page render every read-derived state as UNKNOWN when the
            # poll is failing, without inventing a number of its own and
            # without any window over a plant value (§10.1, V2A-DESIGN §8).
            "read_poll": {"period_ms": None, "stale_after_ms": None},
            # `Forklift/Safety/` — opcua-nodes.md §11.2. Read-only F-CPU mirrors,
            # on the SAME 5 Hz poll as "metrics" (§11 adds no timer of its own).
            # `present` is a STRUCTURAL fact learned at connect time: a server
            # that does not carry this optional group is not an error (§11.6,
            # §11.8 item 5) and the page greys the group rather than guessing a
            # value for it. Starts `False` — the safe, uninformative default,
            # never asserted true until a connect has actually resolved it.
            "safety": {
                "present": False,
                "EStopDemand": None, "ZoneStopDemand": None,
                "SafetyResetRequired": None, "SafetyResetFault": None,
            },
            # §10.8 H6, rendered so a page that returns learns why its controls
            # were dropped. `age_ms` is the age the WRITE CYCLE measured when it
            # last looked; a value rendered here would always read ~0 ms, because
            # serving this very request refreshed the beacon.
            "page": {
                "state": "LIVE", "age_ms": None, "last_request_utc": None,
                "requests": 0, "drops": 0, "last_drop_utc": None,
                "stale_after_ms": round(UI_POLL_STALE_TIME * 1000.0, 1),
                "poll_period_ms": round(UI_POLL_PERIOD_S * 1000.0, 1),
                "teleop_armed": True, "reset_armed": True,
            },
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


# --------------------------------------------------------------------------- #
# The monitoring plane — read, over loopback, and re-served under this origin.
# --------------------------------------------------------------------------- #

class MonitorProxy:
    """A **GET-only** HTTP client of the monitoring service. Nothing else.

    THE ONE REQUEST CONSTRUCTION IN THIS LAYER. `_get` below builds exactly one
    `urllib.request.Request` and builds it with `method="GET"`, written as a
    literal at the call site. There is no other code path in `hmi/` that opens a
    socket toward `viz/`, no body is ever sent, and `tools/check_hmi_map_pane.py`
    proves both by sweeping this file and by exercising the socket. This is the
    write helper's allowlist pattern of `HMI_WRITABLE_PATHS`, applied to a second
    transport and in the opposite direction.

    `viz/DESIGN.md` §2 rules that service **read-only by construction of the
    process and proven by test; not enforced by the middleware** — that layer's
    claim about itself, quoted whole because that is the only form it has. This
    class adds nothing that could weaken it: it sends `GET`, and no byte it
    produces enters a vehicle domain.

    NOTHING IS CACHED. Every `/state` fetch is fresh, because the ages inside it
    are measured by the monitoring service at the instant it answers and a cache
    would freeze exactly the numbers the map pane exists to keep honest. The
    raster is refetched by the page only when `map_version` changes, which is the
    monitoring design's own rule (viz/DESIGN.md §5) and not a cache of values.
    """

    #: The exact upstream paths this proxy may ever request, as a template set.
    #: A serial is substituted; nothing else is. A path this table does not
    #: describe is not reachable from here.
    UPSTREAM = {
        "vehicles": "/vehicles",
        "state": "/vehicles/{serial}/state",
        "map": "/vehicles/{serial}/map",
    }

    def __init__(self, base_url: str | None, timeout: float = MONITOR_FETCH_TIMEOUT_S):
        self.base_url = (base_url or "").rstrip("/") or None
        self.timeout = timeout
        if self.base_url is not None:
            # Enforced HERE as well as in `validate_config`, because `--monitor-url`
            # would otherwise reach the socket without passing the config check.
            # One rule, both doors.
            parsed = urllib.parse.urlsplit(self.base_url)
            if parsed.scheme != "http" or (parsed.hostname or "") not in LOOPBACK_HOSTS:
                raise ConfigError(
                    f"monitor base URL {self.base_url!r} is not plain http on a "
                    f"loopback host {sorted(LOOPBACK_HOSTS)} — the monitoring plane "
                    f"is local to the operator's machine (invariant 8)")

    @property
    def configured(self) -> bool:
        return self.base_url is not None

    def _get(self, kind: str, serial: str | None = None):
        """One upstream GET. Returns (status, headers, body) or raises."""
        template = self.UPSTREAM[kind]                     # KeyError is a bug here
        path = template.format(serial=urllib.parse.quote(serial or "", safe=""))
        request = urllib.request.Request(self.base_url + path, method="GET")
        request.add_header("Accept", "*/*")
        # No body, no cookie, no credential, and no redirect following that could
        # take this off loopback: an HTTPRedirectHandler is deliberately absent
        # from the opener below.
        opener = urllib.request.build_opener(urllib.request.HTTPHandler)
        with opener.open(request, timeout=self.timeout) as response:
            return response.status, dict(response.headers), response.read()

    # -- what the page asks for ---------------------------------------------

    def envelope(self, serial: str | None) -> dict:
        """The map pane's poll: the serial list and one vehicle's values.

        The upstream payloads are passed through **verbatim** — this process
        renames no key, recomputes no age and derives nothing. The envelope it
        wraps them in carries only facts about THIS process's own channel (its
        round-trip time, whether it reached the service, why not) and the two
        display-ramp endpoints of `POSE_AGE_RAMP_*`, so the page invents no
        millisecond of its own.
        """
        meta = {
            "configured": self.configured,
            "base_url": self.base_url,
            "reachable": False,
            "reason": None,
            "fetch_ms": None,
            "fetched_utc": _utc_now(),
            "poll_period_ms": round(MONITOR_POLL_PERIOD_S * 1000.0, 1),
            "age_ramp_start_ms": POSE_AGE_RAMP_START_MS,
            "age_ramp_full_ms": POSE_AGE_RAMP_FULL_MS,
        }
        if not self.configured:
            meta["reason"] = ("no monitor.base_url in this configuration — this "
                              "backend is not reading the monitoring service")
            return {"monitor": meta, "vehicles": None, "state": None}
        started = time.monotonic()
        try:
            _, _, raw = self._get("vehicles")
            vehicles = json.loads(raw)
            serials = list(vehicles.get("serials") or [])
            chosen = serial if serial in serials else (serials[0] if serials else None)
            state = None
            if chosen is not None:
                _, _, raw_state = self._get("state", chosen)
                state = json.loads(raw_state)
            meta["reachable"] = True
            meta["serial"] = chosen
            meta["fetch_ms"] = round((time.monotonic() - started) * 1000.0, 1)
            return {"monitor": meta, "vehicles": vehicles, "state": state}
        except Exception as exc:                       # noqa: BLE001 - see below
            # EVERY upstream failure is one operator-visible fact: the monitoring
            # service is not answering. It is deliberately broad — a refused
            # connection, a timeout, a half-written body and a payload that is
            # not JSON are the same thing to the operator, and none of them is
            # allowed to reach the page as a stale value or to take this process
            # down. The process plane is untouched by all of them.
            meta["reason"] = f"{type(exc).__name__}: {exc}"
            meta["fetch_ms"] = round((time.monotonic() - started) * 1000.0, 1)
            return {"monitor": meta, "vehicles": None, "state": None}

    def raster(self, serial: str):
        """The WHOLE occupancy grid, passed through byte for byte.

        The upstream body is gzipped and is forwarded compressed, with the
        upstream `X-Map-*` headers copied unchanged, so the bytes the page paints
        are the bytes the monitoring service served — which are the bytes it
        received from the vehicle's map server. Never a crop, and never re-encoded
        here.
        """
        status, headers, body = self._get("map", serial)
        passthrough = {k: v for k, v in headers.items()
                       if k.lower().startswith("x-map-")
                       or k.lower() == "content-encoding"}
        return status, passthrough, body


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
    liveness: PageLiveness
    monitor: MonitorProxy

    #: v2b: the map pane's paths, and the ONLY paths excluded from the H6 beacon
    #: below. `V2B-DESIGN.md` §2.2 argues it: a monitoring-plane fetch proves the
    #: browser is running and proves NOTHING about the channel that carries the
    #: operator's requests, which is what the deadman exists to watch. Counting
    #: it would let a page whose `/state` poll had died keep the teleop enable
    #: armed on the strength of a map refresh. The exclusion can only make the
    #: beacon go stale SOONER — requests to rest sooner, the enable dropped
    #: sooner — which is the direction that fails safe.
    MONITOR_PATHS: frozenset[str] = frozenset({
        "/monitor/vehicles", "/monitor/state", "/monitor/map",
    })

    def _seen(self, path: str) -> None:
        """§10.8 H6: every request from the page refreshes the beacon, except §2.2's.

        Called first in both request methods, before the path is dispatched, so
        every endpoint counts and a 404 counts too — the beacon's subject is the
        page's liveness, never which endpoint it happened to reach. It is
        deliberately not hooked into `handle_one_request`, which on a persistent
        connection runs before the next request has arrived and would credit the
        page with a request it has not yet made.

        The one exclusion is the map pane's three paths, on any verb, for the
        reason written on `MONITOR_PATHS` above.
        """
        if path in self.MONITOR_PATHS:
            return
        self.liveness.seen()

    def __getattr__(self, name):
        """Every verb but GET and POST is refused before any handler exists.

        `__getattr__` runs only when normal attribute lookup fails, so the two
        defined methods are found normally and never reach here; everything else
        the stdlib dispatcher looks for — PUT, DELETE, PATCH, and any verb a
        client invents — lands on one refusal that answers **405** and returns,
        without a byte of any request body being read.

        The stdlib's own answer would be 501, which is a refusal too. 405 with an
        `Allow` header says the same thing in the form the monitoring service
        already says it (`viz/monitor/http_face.py`), so one sweep over both
        layers can assert one shape. This process's write surface remains exactly
        what it was: `POST /control`, and nothing else, anywhere.
        """
        if name.startswith("do_"):
            return self._method_not_allowed
        raise AttributeError(name)

    def _method_not_allowed(self) -> None:
        body = json.dumps({
            "error": "method not allowed", "allow": "GET, POST",
            "why": "this process serves one page, two read endpoints and one "
                   "control endpoint. It has no other write surface to reach "
                   "with any verb.",
        }).encode("utf-8")
        # The connection is closed on a refusal deliberately: an unread body
        # would otherwise be parsed as the next request on a keep-alive
        # connection, and refusing then mis-parsing is worse than either.
        self._send(405, body, "application/json",
                   {"Allow": "GET, POST", "Connection": "close"})
        self.close_connection = True

    def log_message(self, fmt, *args):  # noqa: A003 - stdlib signature
        LOG.debug("http %s", fmt % args)

    def _send(self, code: int, body: bytes, content_type: str,
              extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, str(value))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict) -> None:
        self._send(code, json.dumps(payload).encode("utf-8"), "application/json")

    def _query(self, name: str) -> str | None:
        parts = self.path.split("?", 1)
        if len(parts) < 2:
            return None
        values = urllib.parse.parse_qs(parts[1]).get(name)
        return values[0] if values else None

    def _monitor(self, path: str) -> bool:
        """The map pane's three GET paths. Returns True if this handled the path.

        Read-only in both directions: these three answer values the monitoring
        service produced, and no request that reaches them carries or accepts
        anything. They exist on `do_GET` and on no other verb.
        """
        if path == "/monitor/vehicles" or path == "/monitor/state":
            self._json(200, self.monitor.envelope(self._query("serial")))
            return True
        if path == "/monitor/map":
            serial = self._query("serial")
            if not serial:
                self._json(400, {"error": "serial is required"})
                return True
            try:
                status, headers, body = self.monitor.raster(serial)
            except Exception as exc:                   # noqa: BLE001
                # The same one operator-visible fact as the state fetch: the
                # monitoring service is not answering. The page greys the pane.
                self._json(502, {"error": f"{type(exc).__name__}: {exc}",
                                 "monitoring_service": self.monitor.base_url})
                return True
            self._send(status, body, "application/octet-stream", headers)
            return True
        return False

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        path = self.path.split("?", 1)[0]
        self._seen(path)
        if self._monitor(path):
            return
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
        path = self.path.split("?", 1)[0]
        self._seen(path)
        if path in self.MONITOR_PATHS:
            # The map pane's paths exist on GET and on no other verb. A POST at
            # one of them is refused here, before any body is read, so this
            # process has no write surface facing the monitoring plane in either
            # direction.
            self._json(405, {"error": "method not allowed", "allow": "GET",
                             "why": "the map pane is a read-only view of the "
                                    "monitoring plane; it has no write surface"})
            return
        if path != "/control":
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
            # THE TWO STANDING CONTROLS ARE OPTIONAL IN THIS PAYLOAD, and the
            # asymmetry is deliberate. For the five deadman requests a missing
            # key means REST, which is the whole of the deadman. For these two
            # a missing key means UNCHANGED: a page that has not yet adopted
            # the backend's state (PS-D) must not be able to release an engaged
            # stop or command a mode exit merely by posting.
            process_stop = payload.get("process_stop", None)
            drive_mode = payload.get("drive_mode", None)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            # §10.4: an implausible request is a fault, not a value to clamp.
            self._json(400, {"error": str(exc)})
            return
        self.controls.apply(traction, steer, fork, teleop, reset)
        try:
            if process_stop is not None:
                self.controls.set_process_stop(bool(process_stop))
            if drive_mode is not None:
                self.controls.set_drive_mode(drive_mode)
        except (ValueError, TypeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        if process_stop is not None or drive_mode is not None:
            # PUBLISH THE STANDING STATE FROM HERE, NOT ONLY FROM THE WRITE
            # CYCLE. Every page renders these two controls from this section on
            # every poll (PS-D), so a value that reaches this endpoint and is
            # not published until the next successful write cycle is a value
            # `/state` serves STALE for as long as the OPC UA session is down —
            # and a page loading in that window would draw the wrong position of
            # a standing control. The write cycle refreshes it too; this makes
            # the refresh unconditional on the session (m5-29 finding 1).
            self.published.update(controls=self.controls.standing())
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
        "HmiTeleopRequest", "HmiResetRequest", "HmiDriveModeRequest",
        "HmiProcessStopRequest", "write_rtt_ms",
        "since_last_good_write_ms", "page_state", "page_age_ms",
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
                 liveness: PageLiveness, evidence: Evidence | None,
                 inject_fault_after_s: float | None) -> None:
        self.cfg = cfg
        self.controls = controls
        self.published = published
        self.liveness = liveness
        self.evidence = evidence
        self.inject_fault_after_s = inject_fault_after_s
        self._page_stale = False
        self._page_drops = 0

        opc = cfg["opcua"]
        self.endpoint = opc["endpoint"]
        self.write_period = float(cfg["cycle"]["write_period_s"])
        self.floor_period = float(cfg["cycle"]["floor_period_s"])
        self.metrics_period = float(cfg["cycle"]["metrics_period_s"])
        self.metrics_every = max(1, round(self.metrics_period / self.write_period))
        # The window the page renders UNKNOWN past, published so the page never
        # invents a number of its own. FIVE read-poll periods, the same
        # MULTIPLE as `UI_POLL_STALE_TIME` and for the same reason: it absorbs
        # jitter the watched side cannot bound. What it watches is **this
        # process's own read poll**, its own channel — not a plant value, not a
        # PLC verdict and not anything the PLC also computes (§10.1's test).
        published.update(read_poll={
            "period_ms": round(self.metrics_period * 1000.0, 1),
            "stale_after_ms": round(5.0 * self.metrics_period * 1000.0, 1),
        })

        self.client: Client | None = None
        self._write_nodes: dict[str, Any] = {}
        self._read_nodes: dict[str, Any] = {}
        #: BrowseNames of an OPTIONAL group that failed to resolve on the most
        #: recent connect (§11.6). Populated in `_connect`, read in
        #: `_poll_metrics` to decide "present" — one fact, one place it is
        #: computed, so the log line and the published value can never disagree.
        self._optional_absent: set[str] = set()
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
                f"{name} is not one of the eight HMI-writable nodes "
                f"({', '.join(sorted(HMI_WRITABLE_PATHS))}) — refused by the HMI's "
                f"own allowlist, before the request reached the server"
            )
        node = self._write_nodes.get(name)
        if node is None:
            raise WriteRefused(f"{name} is not resolved in this session")
        return node

    async def _write(self, values: dict[str, Any]) -> None:
        """THE single write helper, together with `_writable` above: every one
        of the eight HMI-writable nodes passes through here, split into two
        calls per cycle (the five requests plus the two §12 standing
        controls, then the heartbeat).

        S7-COMPATIBLE DATAVALUES ONLY (first real-CPU contact, 2026-07-29):
        `BadWriteNotSupported: The server does not support writing the
        combination of value, status and timestamps provided.` A real
        S7-1500 refuses a write whose `DataValue` carries a timestamp.

        `Client.write_values` accepts a bare `ua.Variant` per node and hands
        each one to `asyncua`'s own `value_to_datavalue`, which — for
        anything that is not already a `ua.DataValue` — stamps
        `SourceTimestamp=datetime.now(timezone.utc)` onto it. That stamp was
        the defect: every write this backend made carried a source timestamp
        the double never objected to and the real CPU does.

        `value_to_datavalue` returns an already-built `ua.DataValue`
        UNCHANGED (`isinstance(val, ua.DataValue)` short-circuits it before
        the timestamp branch), so building the `DataValue` here — the
        `Variant` and nothing else, `SourceTimestamp`/`ServerTimestamp`
        left at their `None` default — keeps both timestamps off the wire.
        This is exactly `bridge/amr_bridge/opcua_side.py`'s `PlcClient._write`
        (`ua.DataValue(ua.Variant(value, variant_type))`, read-only reference,
        not imported), which has written to this same CPU since M3.
        """
        names = list(values)
        nodes = [self._writable(name) for name in names]
        datavalues = [ua.DataValue(ua.Variant(values[name], WRITE_VARIANT[name]))
                      for name in names]
        await self.client.write_values(nodes, datavalues)

    # -- session ------------------------------------------------------------ #

    async def _resolve(self, objects, prefix: list[str], interface_index: int,
                       name: str, path, role: str):
        """One REQUIRED browse, and a refusal that says which node was missing.

        A required node that does not resolve is a genuine connect failure and
        this client never browses around one (`bridge-design.md` §3.1 N4). What
        this wrapper adds is legibility. Against today's commissioned CPU
        `hmi/config.yaml` is MEANT to fail here — the `opcua-nodes.md` §12 nodes
        arrive in the owner's TIA session — and the bare `BadNoMatch` it used to
        raise named no browse path at all, so the next person to hit it would
        debug a working system (m5-29 finding 2).
        """
        path = tuple(path)   # the write table is a tuple, the config read table a list
        browse_path = prefix + [f"{interface_index}:{part}" for part in path]
        try:
            return await objects.get_child(browse_path)
        except Exception as exc:  # noqa: BLE001 - re-raised, richer, below
            detail = (
                f"{role} node {name} not found on this server: "
                f"no {'/'.join(path)} under the browse prefix "
                f"{'/'.join(prefix)} ({type(exc).__name__}: {exc})"
            )
            if path[:1] == ("Forklift",) and path[1:2] and path[1] in SECTION_12_FOLDERS:
                detail += (
                    " — THIS IS THE EXPECTED FAILURE against the commissioned CPU: "
                    "it does not carry the opcua-nodes.md §12 nodes "
                    "(Forklift/Mode, /Envelope, /Vehicle, /ProcessStop) until the "
                    "owner's TIA session lands them. The procedure that adds them is "
                    "plc/forklift/TIA-BUILD-PROCEDURE.md; see the header of "
                    "hmi/config.yaml. Until then run the v2a screen against "
                    "hmi/config-v2a-double.yaml, which serves §12 on loopback"
                )
            raise ConnectionError(detail) from exc

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
            self._write_nodes[name] = await self._resolve(
                objects, prefix, interface_index, name, path, "write")
        read_cfg = self.cfg["nodes"].get("read") or {}
        self._read_nodes = {}
        self._optional_absent = set()
        for name, path in read_cfg.items():
            if tuple(path[:-1]) in OPTIONAL_READ_FOLDERS:
                continue  # resolved as a group, below — not a hard requirement
            self._read_nodes[name] = await self._resolve(
                objects, prefix, interface_index, name, path, "read")

        # Optional groups (today: `Forklift/Safety/`, §11) are resolved TOGETHER,
        # after every required read above has already succeeded, so a missing
        # optional folder can never mask a real connect failure elsewhere. §11.6:
        # "an absent mirror renders as absent, never as clear" — a server that
        # does not carry this group is not an error, and no client's connect may
        # fail over it (§11.5 step 6, §11.8 item 5).
        for folder in OPTIONAL_READ_FOLDERS:
            names = [n for n, p in read_cfg.items() if tuple(p[:-1]) == folder]
            if not names:
                continue
            try:
                resolved = {}
                for name in names:
                    resolved[name] = await objects.get_child(
                        prefix + [f"{interface_index}:{part}"
                                  for part in read_cfg[name]])
                self._read_nodes.update(resolved)
            except ua.uaerrors.UaStatusCodeError as exc:
                self._optional_absent.update(names)
                LOG.info(
                    "optional group %s/ not present on this server (%s) — shown "
                    "to the operator as 'not present', never as a value; this "
                    "is not a connect failure (opcua-nodes.md §11.6)",
                    "/".join(folder), exc)

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
        """The 10 Hz write cycle. All eight nodes every cycle, heartbeat last."""
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

            self._check_page(now)
            values = self.controls.take_cycle_values()
            started = time.perf_counter()
            # H1/§10.4/§12.1: all eight every cycle, never on change. H3: the heartbeat
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
                controls=self.controls.standing(),
            )
            if self.evidence is not None:
                self.evidence.row(
                    _utc_now(), round(now, 4), self._cycle, "CONNECTED",
                    self._heartbeat, True,
                    values["HmiTractionRequest"], values["HmiSteerRequest"],
                    values["HmiForkRequest"], values["HmiTeleopRequest"],
                    values["HmiResetRequest"], values["HmiDriveModeRequest"],
                    values["HmiProcessStopRequest"], round(rtt_ms, 3),
                    self.published.render()["session"]["since_last_good_write_ms"],
                    "STALE" if self._page_stale else "LIVE",
                    round(self.liveness.age() * 1000.0, 1),
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

    def _check_page(self, now: float) -> None:
        """§10.8 H6 — the window over the operator's page, evaluated once a cycle.

        This process has two 5 Hz polls and this rule is about **one** of them:
        the browser's `GET /state` over loopback HTTP. The backend's own 5 Hz
        OPC UA read of `Forklift/Input/`, `Forklift/Output/`, `Forklift/Status/`
        and `HmiLinkOk` for the display is a different poll on a different
        transport and has no part in it.

        What happens on expiry is the deadman and **nothing else**: the write
        cycle keeps running and the heartbeat keeps advancing, because stopping
        the counter would say "the HMI is gone", which is false, and would buy
        the PLC's heavier reaction — a link loss latches `ForkliftResetRequired`
        and demands a monitored reset before teleop may return (§10.8 P5, P6). A
        page that had merely been backgrounded would then cost a reset. The two
        reactions are proportional on purpose. The PLC is told nothing new: it
        sees requests at rest under a live heartbeat, a state it already handles.

        Recovery is a **release, not a resume**, and it needs no acknowledgement:
        the next request from the page ends the condition on its own.
        """
        age = self.liveness.age(now)
        stale = age > UI_POLL_STALE_TIME
        if stale and not self._page_stale:
            self._page_stale = True
            self._page_drops += 1
            self.controls.release_for_page_loss(
                f"no request for {age * 1000.0:.0f} ms, over the "
                f"{UI_POLL_STALE_TIME * 1000.0:.0f} ms UI_POLL_STALE_TIME")
            self.published.update(page={"last_drop_utc": _utc_now()})
        elif not stale and self._page_stale:
            self._page_stale = False
            LOG.info("the page is talking again after %d drop(s); the three Reals are "
                     "carried from its next post, and each Bool once it has been seen "
                     "to send that Bool low (§10.8 H6)", self._page_drops)
        self.published.update(page={
            "state": "STALE" if stale else "LIVE",
            "age_ms": round(age * 1000.0, 1),
            "last_request_utc": self.liveness.last_utc(),
            "requests": self.liveness.requests(),
            "drops": self._page_drops,
            **{f"{name}_armed": value for name, value in self.controls.arming().items()},
        })

    async def _poll_metrics(self) -> None:
        """The 5 Hz read-only display poll. Reads only `Forklift/Input/`,
        `Forklift/Output/`, `Forklift/Status/`, `Forklift/Link/HmiLinkOk` and —
        when the server carries them — the four `Forklift/Safety/` mirrors of
        §11; applies all of it to nothing and recomputes none of it (invariant
        10)."""
        if not self._read_nodes:
            return
        names = list(self._read_nodes)
        values = await self.client.read_values([self._read_nodes[n] for n in names])
        reading = dict(zip(names, values))
        # One fact, one place it is computed (§11.6): a name is only ever in
        # `_optional_absent` because `_connect` could not resolve the whole
        # group, so "present" here can never disagree with that log line.
        safety_present = not any(n in self._optional_absent for n in SAFETY_MIRROR_NAMES)
        self.published.update(
            metrics=reading,
            safety={
                "present": safety_present,
                **{n: (reading.get(n) if safety_present else None)
                   for n in SAFETY_MIRROR_NAMES},
            },
        )
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
    liveness = PageLiveness()
    evidence = Evidence(args.evidence_csv) if args.evidence_csv else None

    Handler.controls = controls
    Handler.published = published
    Handler.liveness = liveness
    Handler.monitor = MonitorProxy(
        None if args.no_monitor
        else (args.monitor_url or (cfg.get("monitor") or {}).get("base_url")))
    host = (cfg.get("http") or {}).get("host", "127.0.0.1")
    port = int(args.http_port or (cfg.get("http") or {}).get("port", 8088))
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.daemon_threads = True
    threading.Thread(target=httpd.serve_forever, name="hmi-http", daemon=True).start()
    LOG.info("HMI UI on http://%s:%d/ — loopback only, one operator, local cell "
             "(ADR 0008 D2.7)", host, port)
    if Handler.monitor.configured:
        LOG.info("map pane reads the monitoring service at %s — GET only, over "
                 "loopback, nothing cached; the display ramp is %.0f..%.0f ms and "
                 "gates nothing (V2B-DESIGN §2, §4)", Handler.monitor.base_url,
                 POSE_AGE_RAMP_START_MS, POSE_AGE_RAMP_FULL_MS)
    else:
        LOG.info("no monitor.base_url configured — the map pane renders as "
                 "'monitoring service not configured' and nothing else changes")
    LOG.info("operator-page window UI_POLL_STALE_TIME = %.0f ms (%.0f x the page's "
             "%.0f ms GET /state); with no page talking, the five requests are held at "
             "rest and the heartbeat keeps running (§10.8 H6)",
             UI_POLL_STALE_TIME * 1000.0, UI_POLL_STALE_TIME / UI_POLL_PERIOD_S,
             UI_POLL_PERIOD_S * 1000.0)

    client = HmiClient(cfg, controls, published, liveness, evidence,
                       args.inject_fault_after_s)
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
    parser.add_argument("--monitor-url", default=None,
                        help="base URL of the read-only monitoring service "
                             "(viz/, GET only, loopback). Overrides "
                             "monitor.base_url; absent means the map pane "
                             "renders as not configured")
    parser.add_argument("--no-monitor", action="store_true",
                        help="read no monitoring service at all, whatever the "
                             "config names. The map pane then says so in words "
                             "rather than reporting an unreachable service, "
                             "because 'not configured' and 'not answering' are "
                             "two different facts about the operator's day")
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
