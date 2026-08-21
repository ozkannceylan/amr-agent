# M6.2 VDA 5050 Vehicle Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** each step6 vehicle gains a VDA 5050 2.1.0 client (`ipc/vda_agent.py`) so full-route orders arrive over MQTT and drive the truck through the existing autopilot machinery.

**Architecture:** a new nav seam (`NavCore.on_route` + `AUTO_ROUTE_TOPIC`) accepts externally supplied polylines; two pure modules (`vda_orders.py`, `vda_messages.py`) carry all protocol decisions; the agent node is thin wiring between paho-mqtt and rclpy; mosquitto runs user-space (no sudo) and is spawned by `step6.sh`. Spec: `docs/superpowers/specs/2026-08-21-m6-2-vda-vehicle-agent-design.md`; message contract: `docs/interfaces/vda5050-subset.md` (M1) — read both before starting.

**Tech Stack:** Python 3 (plain files), rclpy (WSL), paho-mqtt (pip --user), mosquitto 2.0.18 (user-space extract), pytest.

## Global Constraints

- Only `m5_ver2/step6/` changes (plus nothing else — not even .gitignore this time).
- Steps 1-5 frozen; `agv/` sources untouched; the safety chain, writer, mux, gate untouched.
- Vehicle ids `f1`/`f2`; env `VEHICLE` flow as in M6.1; every new per-vehicle name lives in `status_contract`.
- MQTT: topic root `uagv/v2/amragent/<vid>/{order,instantActions,state,connection,factsheet}`; JSON UTF-8; enums UPPERCASE; timestamps `YYYY-MM-DDTHH:MM:SS.mmmZ`; QoS/retain per M1 §2 (connection QoS 1 retained; factsheet retained; order/instantActions/state QoS 0).
- The factsheet declares ONLY implemented actions (cancelOrder, stateRequest, factsheetRequest) — recorded deviation from M1's eight.
- safetyState is reporting only; no safety function may depend on MQTT — restate in the agent docstring.
- Commit style `step6: ...` lowercase, no attribution, no Claude mention.
- Suites: step6 WSL baseline **245 passed**, step5 220 — neither may regress. WSL runs need `source /opt/ros/jazzy/setup.bash`.
- Facts you rely on: `route.plan_route(pose_xy, sid)` returns `[pose_xy, node, ..., station]` (pure); `NavCore.on_goal` installs `self.route` as a plain point list and `follower` consumes it; `MODE_TOPIC` QoS is TRANSIENT_LOCAL depth 1; `nav_node` publishes `/​<vid>/auto/state` JSON with `state/goal/route/pose/...`; `field_eval`'s fields JSON carries per-device `"pf"`/`"wf"` booleans; stations own `arrive_m` (0.25 or 0.80).

---

### Task 1: The broker — user-space mosquitto under step6.sh

**Files:**
- Create: `m5_ver2/step6/tools/install_broker.sh`
- Modify: `m5_ver2/step6/step6.sh` (broker spawn, port guard, PATTERNS, names)

**Interfaces:**
- Produces: `~/.local/mosquitto-vendored/usr/sbin/mosquitto` in WSL; `step6.sh start` brings the broker up on localhost:1883 as the FIRST spawn and `stop` sweeps it. `BROKER_BIN` resolution lives in step6.sh.

- [ ] **Step 1: The install script**

`m5_ver2/step6/tools/install_broker.sh`:

```bash
#!/usr/bin/env bash
# install_broker.sh - mosquitto without root. `apt-get download` fetches
# the Ubuntu package to the working dir and `dpkg-deb -x` unpacks it
# into the user's home; no sudo at any point, nothing system-wide, and
# the binary is NOT committed - this script is how it reproduces.
# mosquitto 2.x run with no config listens on localhost only and allows
# anonymous local clients, which is exactly the M6.2 posture (the
# broker moves to the fleet side in M6.3).
set -euo pipefail
DEST="$HOME/.local/mosquitto-vendored"
BIN="$DEST/usr/sbin/mosquitto"
if [ -x "$BIN" ]; then
    echo "already installed: $BIN"; "$BIN" -h 2>&1 | head -1; exit 0
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
( cd "$TMP" && apt-get download mosquitto libmosquitto1 2>/dev/null || \
      apt-get download mosquitto )
mkdir -p "$DEST"
for deb in "$TMP"/*.deb; do dpkg-deb -x "$deb" "$DEST"; done
[ -x "$BIN" ] || { echo "extract failed - no $BIN"; exit 1; }
echo "installed: $BIN"
"$BIN" -h 2>&1 | head -1
```

Run it in WSL; if the binary refuses to start on a missing shared library, `ldd` it, extract the missing lib the same way, and record what was needed. Then `pip3 install --user paho-mqtt` and record the version.

- [ ] **Step 2: step6.sh**

Following the file's own idioms exactly (read the surrounding code first):
1. Near the config block: `BROKER_BIN="$HOME/.local/mosquitto-vendored/usr/sbin/mosquitto"`.
2. Port guard: add a 1883 check to the existing pipe-free `case` chain (same `$'\n'`/`[!0-9]` shape), message naming the broker and `tools/install_broker.sh`. Also refuse in `start` when `BROKER_BIN` is missing, naming the script.
3. First spawn, before the world: `spawn broker - "$BROKER_BIN" -v` (mosquitto logs to stderr; `spawn` already redirects to `$LOGDIR/broker.log`; no VEHICLE). A comment records the M6.3 relocation intent.
4. `PATTERNS`: add `"mosquitto-vendored"` (the path substring nominates the broker; `ours()` still decides — the broker inherits GZ_PARTITION from the spawn).
5. The names list is built by `SPAWNED+=` since M6.1 — no hand edit needed; confirm the startup check now expects 18 entries (broker + world + 8×2) and the final echo mentions the broker.

- [ ] **Step 3: Smoke**

WSL: `bash tools/install_broker.sh` (idempotent twice); `./step6.sh deploy && ./step6.sh start --headless` → 18 pids, `broker.log` shows "mosquitto version ... running"; `ss -tln | grep 1883` bound; a `mosquitto-vendored`-path `mosquitto_pub`/`sub` roundtrip if the clients extracted, else `python3 -c` paho roundtrip; `./step6.sh stop` → swept, 1883 free. Suite still 245.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/tools/install_broker.sh m5_ver2/step6/step6.sh
git commit -m "step6: a user-space broker - mosquitto joins the stack, no sudo"
```

---

### Task 2: The nav seam — externally supplied routes

**Files:**
- Modify: `m5_ver2/step6/ipc/status_contract.py` (one name), `ipc/nav_core.py` (one method), `ipc/nav_node.py` (one subscription)
- Test: extend `m5_ver2/step6/tests/test_nav_node.py` (or the file that tests NavCore — find it; the tests below name `nav_core`)

**Interfaces:**
- Produces: `AUTO_ROUTE_TOPIC` (`/<vid>/auto/route`, contract key `auto_route_topic`); `NavCore.on_route(points, arrive_m, label)`; wire format `{"points": [[x,y],...], "arrive_m": float, "label": str}`.

- [ ] **Step 1: Failing tests**

Append (adapting the import style you find):

```python
def test_on_route_installs_an_external_polyline():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode("auto")
    core.on_route([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]], 0.3, "order-1")
    assert core.state == nav_core.EN_ROUTE
    assert core.goal == "order-1"
    assert core.route == [(0.0, 0.0), (1.0, 0.0), (2.0, 0.0)]
    assert core.arrive_m == 0.3


def test_on_route_refused_outside_auto():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode("teleop")
    core.on_route([[0.0, 0.0], [1.0, 0.0]], 0.3, "order-1")
    assert core.state == nav_core.IDLE and "auto" in core.note


def test_on_route_refuses_a_degenerate_polyline():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode("auto")
    core.on_route([[0.0, 0.0]], 0.3, "order-1")
    assert core.state == nav_core.IDLE and core.route is None


def test_empty_goal_still_cancels_an_external_route():
    core = nav_core.NavCore(plan=lambda xy, sid: None)
    core.on_mode("auto")
    core.on_route([[0.0, 0.0], [1.0, 0.0]], 0.3, "order-1")
    core.on_goal("", (0.0, 0.0))
    assert core.state == nav_core.IDLE and core.route is None
```

- [ ] **Step 2: RED**, then implement:

`status_contract.py`: add `"auto_route_topic": "/{}/auto/route".format(vid)` to `contract()` and `AUTO_ROUTE_TOPIC = _C["auto_route_topic"]` to the guarded block (comment: the agent's full-route door, M6.2).

`nav_core.py`, next to `on_goal`:

```python
    def on_route(self, points, arrive_m, label):
        """An externally planned polyline - the VDA agent's door (M6.2).

        Same rules as on_goal after planning: auto mode only, the empty
        goal stays the one cancel door, and everything downstream
        (follower, guards, ARRIVED, SAFETY-STOP holding the route) is
        the same machinery. This file still plans nothing here: the
        route arrives finished, and a malformed one is refused, not
        repaired.
        """
        if self.mode != MODE_AUTO:
            self.note = "route refused: not in auto mode"
            return
        try:
            poly = [(float(p[0]), float(p[1])) for p in points]
        except (TypeError, ValueError, IndexError):
            self.note = "route refused: malformed points"
            return
        if len(poly) < 2:
            self.note = "route refused: fewer than two points"
            return
        self.goal, self.route, self.state = str(label), poly, EN_ROUTE
        self.note, self.reversing = "", False
        self.arrive_m = float(arrive_m) if arrive_m else follower.ARRIVE_M
```

`nav_node.py`: import `AUTO_ROUTE_TOPIC`, add after the goal subscription:

```python
        self.create_subscription(
            String, AUTO_ROUTE_TOPIC, self.cb_route, 10)
```

and the callback next to `cb_goal`:

```python
    def cb_route(self, msg):
        if self.pose is None:
            self.core.note = "route refused: no pose yet"
            return
        try:
            req = json.loads(msg.data)
            self.core.on_route(
                req["points"], req.get("arrive_m"), req.get("label", ""))
        except (ValueError, KeyError, TypeError):
            self.core.note = "route refused: unreadable request"
```

(`import json` joins nav_node's imports.)

- [ ] **Step 3: GREEN + suite**

New tests pass; whole step6 WSL suite 245 + 4 = **249**.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/ipc m5_ver2/step6/tests
git commit -m "step6: nav accepts a finished route - the vda agent's door"
```

---

### Task 3: vda_orders.py — validation, acceptance, progress (pure)

**Files:**
- Create: `m5_ver2/step6/ipc/vda_orders.py`
- Test: `m5_ver2/step6/tests/test_vda_orders.py`

**Interfaces:**
- Produces: `validate_order(msg) -> str` ("" = valid); `accept_order(msg, current_order_id, current_update_id, executing, operating_mode) -> (verdict, reason)` with verdict in `{"accept","ignore","reject"}`; `released_route(msg) -> (points, arrive_m, released_nodes, horizon_nodes)`; `class Progress(released_nodes)` with `.update(xy) -> bool changed`, `.complete()`, `.last_node() -> (nodeId, sequenceId)`, `.reached`; `DEFAULT_DEV_M = 0.8`.

- [ ] **Step 1: Failing tests** — `tests/test_vda_orders.py`:

```python
"""Order validation, acceptance and progress - the M1 section-4 rules."""
import pytest

import vda_orders as vo


def order(nodes=None, edges=None, **over):
    """A minimal valid two-node order; override to break it."""
    if nodes is None:
        nodes = [
            {"nodeId": "wp0", "sequenceId": 0, "released": True,
             "actions": [],
             "nodePosition": {"x": 0.0, "y": 0.0, "mapId": "warehouse"}},
            {"nodeId": "S4", "sequenceId": 2, "released": True,
             "actions": [],
             "nodePosition": {"x": 6.0, "y": -8.0, "mapId": "warehouse",
                              "allowedDeviationXY": 0.25}},
        ]
    if edges is None:
        edges = [{"edgeId": "e0", "sequenceId": 1, "released": True,
                  "startNodeId": "wp0", "endNodeId": "S4", "actions": []}]
    msg = {"orderId": "o1", "orderUpdateId": 0,
           "nodes": nodes, "edges": edges}
    msg.update(over)
    return msg


def test_a_valid_order_validates():
    assert vo.validate_order(order()) == ""


@pytest.mark.parametrize("missing", ["orderId", "orderUpdateId",
                                     "nodes", "edges"])
def test_missing_top_level_fields_are_named(missing):
    msg = order()
    del msg[missing]
    assert missing in vo.validate_order(msg)


def test_edges_must_join_the_nodes():
    bad = order()
    bad["edges"][0]["endNodeId"] = "S5"
    assert "join" in vo.validate_order(bad)


def test_sequence_ids_are_the_interleaved_rule():
    bad = order()
    bad["nodes"][1]["sequenceId"] = 3
    assert "sequenceId" in vo.validate_order(bad)


def test_node_position_is_mandatory_for_us():
    bad = order()
    del bad["nodes"][1]["nodePosition"]
    assert "nodePosition" in vo.validate_order(bad)


def test_released_after_horizon_is_refused():
    n = order()["nodes"]
    n[0]["released"] = False
    assert "horizon" in vo.validate_order(order(nodes=n)) \
        or "base" in vo.validate_order(order(nodes=n))


def test_node_actions_are_not_supported_yet():
    bad = order()
    bad["nodes"][0]["actions"] = [{"actionType": "pick"}]
    assert "unsupported" in vo.validate_order(bad)


def test_accept_matrix():
    ok = order()
    assert vo.accept_order(ok, "", 0, False, "AUTOMATIC")[0] == "accept"
    assert vo.accept_order(ok, "", 0, False, "MANUAL")[0] == "reject"
    assert vo.accept_order(ok, "other", 0, True, "AUTOMATIC")[0] == "reject"
    assert vo.accept_order(ok, "o1", 0, True, "AUTOMATIC")[0] == "ignore"
    upd = order(orderUpdateId=1)
    assert vo.accept_order(upd, "", 0, False, "AUTOMATIC")[0] == "reject"


def test_released_route_splits_base_and_horizon():
    n = order()["nodes"] + [
        {"nodeId": "S5", "sequenceId": 4, "released": False, "actions": [],
         "nodePosition": {"x": 8.0, "y": -8.0, "mapId": "warehouse"}}]
    e = order()["edges"] + [
        {"edgeId": "e1", "sequenceId": 3, "released": False,
         "startNodeId": "S4", "endNodeId": "S5", "actions": []}]
    pts, arrive, rel, hor = vo.released_route(order(nodes=n, edges=e))
    assert pts == [(0.0, 0.0), (6.0, -8.0)]
    assert arrive == 0.25
    assert [x["nodeId"] for x in rel] == ["wp0", "S4"]
    assert [x["nodeId"] for x in hor] == ["S5"]


def test_progress_is_monotone_and_skips():
    _, _, rel, _ = vo.released_route(order())
    p = vo.Progress(rel)
    assert p.last_node() == ("", 0)
    assert p.update((6.0, -8.0)) is True      # jumped to the last node
    assert p.reached == 2
    assert p.last_node() == ("S4", 2)
    assert p.update((0.0, 0.0)) is False      # never backwards


def test_progress_complete_marks_everything():
    _, _, rel, _ = vo.released_route(order())
    p = vo.Progress(rel)
    p.complete()
    assert p.reached == 2 and p.last_node() == ("S4", 2)
```

- [ ] **Step 2: RED**, then implement `ipc/vda_orders.py`:

```python
"""vda_orders.py - VDA 5050 order rules, pure. No ROS, no MQTT.

The M1 subset's section 4 as executable checks. Validation names what
is wrong instead of repairing it; acceptance is a three-way verdict so
a duplicate delivery is silence, not an error; progress is monotone and
skip-tolerant, because the pursuit cuts corners and the polyline's
ARRIVED (nav-side) is what finally closes an order, not this counter.

Deliberate M6.2 boundaries (spec): orderUpdateId > 0 and node actions
are rejected - stitching and station actions land with M6.3.
"""
import math

DEFAULT_DEV_M = 0.8   # intermediate waypoint pass radius; the pursuit
                      # cuts corners, and ARRIVED closes what this misses


def validate_order(msg):
    """'' when valid, else the reason - which names the missing thing."""
    if not isinstance(msg, dict):
        return "not an object"
    for key in ("orderId", "orderUpdateId", "nodes", "edges"):
        if key not in msg:
            return "missing {}".format(key)
    if not isinstance(msg["orderId"], str) or not msg["orderId"]:
        return "orderId must be a non-empty string"
    upd = msg["orderUpdateId"]
    if not isinstance(upd, int) or isinstance(upd, bool) or upd < 0:
        return "orderUpdateId must be an integer >= 0"
    nodes, edges = msg["nodes"], msg["edges"]
    if not isinstance(nodes, list) or not nodes:
        return "nodes must be a non-empty array"
    if not isinstance(edges, list) or len(edges) != len(nodes) - 1:
        return "edges must join the nodes (len(nodes)-1 of them)"
    for i, n in enumerate(nodes):
        for key in ("nodeId", "sequenceId", "released", "actions"):
            if key not in n:
                return "node {} missing {}".format(i, key)
        if n["sequenceId"] != 2 * i:
            return "node {} sequenceId must be {} (interleaved rule)".format(
                i, 2 * i)
        pos = n.get("nodePosition")
        if not isinstance(pos, dict) or not {"x", "y", "mapId"} <= set(pos):
            return "node {} missing nodePosition (mandatory for us)".format(i)
        if n["actions"]:
            return "node {} actions unsupported until M6.3".format(i)
    for i, e in enumerate(edges):
        for key in ("edgeId", "sequenceId", "released",
                    "startNodeId", "endNodeId", "actions"):
            if key not in e:
                return "edge {} missing {}".format(i, key)
        if e["sequenceId"] != 2 * i + 1:
            return "edge {} sequenceId must be {} (interleaved rule)".format(
                i, 2 * i + 1)
        if (e["startNodeId"] != nodes[i]["nodeId"]
                or e["endNodeId"] != nodes[i + 1]["nodeId"]):
            return "edge {} does not join its neighbour nodes".format(i)
    if not nodes[0]["released"]:
        return "no released base - the first node is horizon"
    seen_horizon = False
    for n in nodes:
        if seen_horizon and n["released"]:
            return "released node after a horizon node"
        seen_horizon = seen_horizon or not n["released"]
    for e, end in zip(edges, nodes[1:]):
        if bool(e["released"]) != bool(end["released"]):
            return "edge released must match its end node"
    return ""


def accept_order(msg, current_order_id, current_update_id, executing,
                 operating_mode):
    """('accept'|'ignore'|'reject', reason)."""
    reason = validate_order(msg)
    if reason:
        return ("reject", reason)
    if (msg["orderId"] == current_order_id
            and msg["orderUpdateId"] == current_update_id):
        return ("ignore", "duplicate delivery")
    if msg["orderUpdateId"] != 0:
        return ("reject",
                "order updates land with M6.3 - cancelOrder, then send "
                "a fresh order")
    if operating_mode != "AUTOMATIC":
        return ("reject", "vehicle not in AUTOMATIC")
    if executing:
        return ("reject", "an order is executing - cancelOrder first")
    return ("accept", "")


def released_route(msg):
    """(points, arrive_m, released_nodes, horizon_nodes)."""
    released = [n for n in msg["nodes"] if n["released"]]
    horizon = [n for n in msg["nodes"] if not n["released"]]
    points = [(float(n["nodePosition"]["x"]), float(n["nodePosition"]["y"]))
              for n in released]
    last = released[-1]["nodePosition"]
    arrive_m = float(last.get("allowedDeviationXY", 0.25))
    return points, arrive_m, released, horizon


class Progress:
    """Which released nodes the truck has passed. Monotone, skips."""

    def __init__(self, released_nodes):
        self.nodes = released_nodes
        self.reached = 0

    def update(self, xy):
        """Mark the furthest node whose deviation circle contains xy,
        and everything before it. True when the count advanced."""
        before = self.reached
        for j in range(len(self.nodes) - 1, self.reached - 1, -1):
            pos = self.nodes[j]["nodePosition"]
            dev = float(pos.get("allowedDeviationXY", DEFAULT_DEV_M))
            if math.hypot(xy[0] - pos["x"], xy[1] - pos["y"]) <= dev:
                self.reached = j + 1
                break
        return self.reached != before

    def complete(self):
        self.reached = len(self.nodes)

    def last_node(self):
        if self.reached == 0:
            return ("", 0)
        node = self.nodes[self.reached - 1]
        return (node["nodeId"], node["sequenceId"])
```

- [ ] **Step 3: GREEN** — 12 tests; suite 249 + 12 = **261**.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/ipc/vda_orders.py m5_ver2/step6/tests/test_vda_orders.py
git commit -m "step6: vda order rules - validate, accept, track, pure"
```

---

### Task 4: vda_messages.py — headers, state, factsheet, safety mapping (pure)

**Files:**
- Create: `m5_ver2/step6/ipc/vda_messages.py`
- Test: `m5_ver2/step6/tests/test_vda_messages.py`

**Interfaces:**
- Produces: `MANUFACTURER = "amragent"`, `VERSION = "2.1.0"`; `topic(vid, name) -> str`; `class Counters` (`.header(topic_name, vid) -> dict` — per-topic headerId starting 1, ISO-8601-Z timestamp); `errors_and_safety(motor, estop_healthy, any_pf_false) -> (errors, safetyState)`; `any_pf_false(obj) -> bool` (recursive over parsed JSON); `build_state(header, order_ctx, pose, driving, operating_mode, errors, safety, action_states) -> dict`; `build_factsheet(header, cfg) -> dict`; `connection_payload(header, state) -> dict`.

- [ ] **Step 1: Failing tests** — `tests/test_vda_messages.py`:

```python
"""The wire builders - M1 sections 3, 5, 7, 8 as assertions."""
import re

import vda_messages as vm


def test_topic_root_is_the_m1_shape():
    assert vm.topic("f1", "order") == "uagv/v2/amragent/f1/order"


def test_headers_count_per_topic_and_stamp_utc_z():
    c = vm.Counters()
    h1 = c.header("state", "f2")
    h2 = c.header("state", "f2")
    h3 = c.header("connection", "f2")
    assert (h1["headerId"], h2["headerId"], h3["headerId"]) == (1, 2, 1)
    assert h1["version"] == "2.1.0"
    assert h1["manufacturer"] == "amragent"
    assert h1["serialNumber"] == "f2"
    assert re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z", h1["timestamp"])


def test_errors_and_safety_mapping():
    errors, safety = vm.errors_and_safety(True, True, False)
    assert errors == [] and safety == {"eStop": "NONE",
                                       "fieldViolation": False}
    errors, safety = vm.errors_and_safety(False, True, True)
    assert errors[0]["errorLevel"] == "FATAL"
    assert safety["eStop"] == "MANUAL" and safety["fieldViolation"] is True


def test_any_pf_false_walks_nested_reports():
    report = {"ts": 1.0,
              "back": {"pf": True, "wf": False},
              "left": {"pf": False, "wf": True}}
    assert vm.any_pf_false(report) is True
    report["left"]["pf"] = True
    assert vm.any_pf_false(report) is False


def test_state_carries_every_required_field():
    c = vm.Counters()
    ctx = {"orderId": "o1", "orderUpdateId": 0,
           "lastNodeId": "wp0", "lastNodeSequenceId": 0,
           "nodeStates": [{"nodeId": "S4", "sequenceId": 2,
                           "released": True}],
           "edgeStates": [], "newBaseRequest": False}
    state = vm.build_state(
        c.header("state", "f1"), ctx, (1.0, 2.0, 0.5), True, "AUTOMATIC",
        [], {"eStop": "NONE", "fieldViolation": False}, [])
    for key in ("headerId", "timestamp", "version", "manufacturer",
                "serialNumber", "orderId", "orderUpdateId", "lastNodeId",
                "lastNodeSequenceId", "nodeStates", "edgeStates", "driving",
                "paused", "newBaseRequest", "agvPosition", "batteryState",
                "operatingMode", "errors", "actionStates", "safetyState"):
        assert key in state, key
    assert state["agvPosition"] == {
        "x": 1.0, "y": 2.0, "theta": 0.5, "mapId": "warehouse",
        "positionInitialized": True}
    assert state["batteryState"] == {"batteryCharge": 100.0,
                                     "charging": False}


def test_factsheet_is_truthful_and_minimal():
    c = vm.Counters()
    cfg = {"limits": {"traction_speed_max_mps": 1.5},
           "model": {"steer_limit_rad": 1.31}}
    fs = vm.build_factsheet(c.header("factsheet", "f1"), cfg)
    ts = fs["typeSpecification"]
    assert ts["agvClass"] == "FORKLIFT"
    assert ts["agvKinematic"] == "THREEWHEEL"
    assert ts["navigationTypes"] == ["AUTONOMOUS"]
    assert fs["physicalParameters"]["speedMax"] == 1.5
    acts = {a["actionType"] for a in fs["protocolFeatures"]["agvActions"]}
    assert acts == {"cancelOrder", "stateRequest", "factsheetRequest"}


def test_connection_payload():
    c = vm.Counters()
    p = vm.connection_payload(c.header("connection", "f1"), "ONLINE")
    assert p["connectionState"] == "ONLINE"
```

- [ ] **Step 2: RED**, then implement `ipc/vda_messages.py`:

```python
"""vda_messages.py - the VDA 5050 wire builders, pure. No ROS, no MQTT.

Every field below is traceable to docs/interfaces/vda5050-subset.md
(M1); nothing is invented. The factsheet declares only the implemented
actions - the machine-readable statement must not advertise what would
FAIL (spec, recorded deviation from the M1 table's eight).

batteryState is an honest stub: the sim has no battery, the schema
requires the object, so it reports full-and-not-charging rather than a
number that pretends to drain.
"""
import time

MANUFACTURER = "amragent"
VERSION = "2.1.0"


def topic(vid, name):
    return "uagv/v2/{}/{}/{}".format(MANUFACTURER, vid, name)


def _stamp(now=None):
    t = time.time() if now is None else now
    ms = int((t - int(t)) * 1000)
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(t)) \
        + ".{:03d}Z".format(ms)


class Counters:
    """headerId is a per-topic counter, +1 per sent message (M1 s.3)."""

    def __init__(self):
        self._n = {}

    def header(self, topic_name, vid, now=None):
        self._n[topic_name] = self._n.get(topic_name, 0) + 1
        return {"headerId": self._n[topic_name], "timestamp": _stamp(now),
                "version": VERSION, "manufacturer": MANUFACTURER,
                "serialNumber": vid}


def errors_and_safety(motor, estop_healthy, pf_violated):
    """M1 s.5: errors[] + safetyState, from what the PLC already did.

    Reporting only - by the time this runs the F-model has long since
    dropped Motor. eStop=MANUAL means an acknowledge is pending, which
    is what a latched demand or an unhealthy chain both mean here.
    """
    errors = []
    if not motor:
        errors.append({
            "errorType": "safetyStop", "errorLevel": "FATAL",
            "errorDescription": "drive enable is down - latched safety "
                                "demand or startup acknowledge pending",
            "errorReferences": []})
    safety = {"eStop": "NONE" if (motor and estop_healthy) else "MANUAL",
              "fieldViolation": bool(pf_violated)}
    return errors, safety


def any_pf_false(obj):
    """True when any 'pf' key anywhere in the parsed report is False."""
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == "pf" and value is False:
                return True
            if any_pf_false(value):
                return True
    elif isinstance(obj, list):
        return any(any_pf_false(v) for v in obj)
    return False


def build_state(header, order_ctx, pose, driving, operating_mode,
                errors, safety, action_states):
    state = dict(header)
    state.update({
        "orderId": order_ctx.get("orderId", ""),
        "orderUpdateId": order_ctx.get("orderUpdateId", 0),
        "lastNodeId": order_ctx.get("lastNodeId", ""),
        "lastNodeSequenceId": order_ctx.get("lastNodeSequenceId", 0),
        "nodeStates": order_ctx.get("nodeStates", []),
        "edgeStates": order_ctx.get("edgeStates", []),
        "driving": bool(driving),
        "paused": False,
        "newBaseRequest": bool(order_ctx.get("newBaseRequest", False)),
        "agvPosition": {"x": pose[0], "y": pose[1], "theta": pose[2],
                        "mapId": "warehouse",
                        "positionInitialized": True},
        "batteryState": {"batteryCharge": 100.0, "charging": False},
        "operatingMode": operating_mode,
        "errors": errors,
        "actionStates": action_states,
        "safetyState": safety})
    return state


def build_factsheet(header, cfg):
    """Truthful for THIS vehicle; numeric values from config.yaml where
    it has them, labeled sim stubs where it does not."""
    limits = cfg.get("limits", {})
    fs = dict(header)
    fs.update({
        "typeSpecification": {
            "seriesName": "forklift_ver2",
            "agvKinematic": "THREEWHEEL",
            "agvClass": "FORKLIFT",
            "maxLoadMass": 1000.0,          # sim stub, no load model
            "localizationTypes": ["NATURAL"],
            "navigationTypes": ["AUTONOMOUS"]},
        "physicalParameters": {
            "speedMin": 0.0,
            "speedMax": float(limits.get("traction_speed_max_mps", 1.5)),
            "accelerationMax": 1.0,          # sim stub
            "decelerationMax": 1.0,          # sim stub
            "heightMax": 2.4, "width": 1.4, "length": 2.6},
        "protocolLimits": {
            "maxStringLens": {}, "maxArrayLens": {},
            "timing": {"minOrderInterval": 1.0, "minStateInterval": 0.5}},
        "protocolFeatures": {
            "optionalParameters": [
                {"parameter": "order.edge.maxSpeed",
                 "support": "NOT_SUPPORTED"}],
            "agvActions": [
                {"actionType": name, "actionScopes": ["INSTANT"]}
                for name in ("cancelOrder", "stateRequest",
                             "factsheetRequest")]},
        "agvGeometry": {},
        "loadSpecification": {"loadSets": []}})
    return fs


def connection_payload(header, state):
    payload = dict(header)
    payload["connectionState"] = state
    return payload
```

- [ ] **Step 3: GREEN** — 7 tests; suite 261 + 7 = **268**.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/ipc/vda_messages.py m5_ver2/step6/tests/test_vda_messages.py
git commit -m "step6: vda wire builders - headers, state, factsheet, pure"
```

---

### Task 5: The agent node + integration test

**Files:**
- Create: `m5_ver2/step6/ipc/vda_agent.py`
- Test: `m5_ver2/step6/tests/test_vda_agent_mqtt.py` (WSL-only; skips without paho or the vendored mosquitto)

**Interfaces:**
- Consumes: everything Tasks 2-4 produced; `AUTO_ROUTE_TOPIC`, `AUTO_GOAL_TOPIC`, `MODE_TOPIC` (TRANSIENT_LOCAL), `STATUS_TOPIC`, `FIELDS_TOPIC`, `AUTO_STATE_TOPIC`, odom from config `gz_odom`.
- Produces: the running agent; env override `VDA_MQTT_PORT` (default 1883) so tests use a private broker.

- [ ] **Step 1: Write the agent** — `ipc/vda_agent.py` (~190 lines; the shape below is normative, fill nothing differently without reporting it):

```python
"""vda_agent.py - the vehicle's VDA 5050 client. Wiring only.

Decisions live in vda_orders.py / vda_messages.py (pure); this file
moves bytes: paho-mqtt on one side, rclpy on the other. The paho
network thread only ENQUEUES; a 10 Hz rclpy timer drains the queue and
does all work in the ROS thread, so no lock guards any state.

SAFETY: this channel is reporting and process command only (M1
invariant). safetyState narrates what the F-model already did; a lost
broker is degraded mode -> controlled stop through the NORMAL chain
(the empty goal), never a safety path. If this agent dies the truck
keeps driving its current route - the panel and the chain own stopping.

Supervision loss (M1 s.7): on disconnect publish the empty goal, KEEP
the order; on reconnect re-issue the remaining released nodes as a
fresh route from the current pose.
"""
import json
import math
import os
import queue
import time

import rclpy
import yaml
from nav_msgs.msg import Odometry
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile
from std_msgs.msg import String

import paho.mqtt.client as mqtt

import vda_messages as vm
import vda_orders as vo
from status_contract import (
    AUTO_GOAL_TOPIC, AUTO_ROUTE_TOPIC, AUTO_STATE_TOPIC, CONFIG_PATH,
    FIELDS_TOPIC, MODE_TOPIC, STATUS_TOPIC, VID, MODE_AUTO,
    STATUS_STALE_S, is_stale, parse_status)

# ----------------------------- CONFIG -----------------------------
MQTT_HOST = "127.0.0.1"
MQTT_PORT = int(os.environ.get("VDA_MQTT_PORT", "1883"))
DRAIN_HZ = 10.0
STATE_PERIOD_S = 2.0
DRIVING_MPS = 0.02
# ------------------------------------------------------------------


class VdaAgent(Node):

    def __init__(self):
        super().__init__("vda_agent")
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            topics = yaml.safe_load(handle)["topics"]
        self.counters = vm.Counters()
        self.inbox = queue.Queue()
        # vehicle-side truth
        self.pose = (0.0, 0.0, 0.0)
        self.speed = 0.0
        self.mode = None
        self.motor = False
        self.estop_healthy = False
        self.status_rx = None
        self.pf_violated = True     # unknown reads as violated
        self.nav_state = ""
        self.nav_goal = ""
        # order context
        self.order = None            # the accepted order message
        self.progress = None
        self.horizon = []
        self.executing = False
        self.action_states = []
        self.last_state_pub = 0.0
        self.last_snapshot = None

        self.pub_route = self.create_publisher(String, AUTO_ROUTE_TOPIC, 10)
        self.pub_goal = self.create_publisher(String, AUTO_GOAL_TOPIC, 10)
        latched = QoSProfile(
            depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
        self.create_subscription(String, MODE_TOPIC, self.cb_mode, latched)
        self.create_subscription(String, STATUS_TOPIC, self.cb_status, 10)
        self.create_subscription(String, FIELDS_TOPIC, self.cb_fields, 10)
        self.create_subscription(String, AUTO_STATE_TOPIC, self.cb_nav, 10)
        self.create_subscription(
            Odometry, topics["gz_odom"], self.cb_odom, 10)
        self.create_timer(1.0 / DRAIN_HZ, self.drain)

        self.mq = mqtt.Client(client_id="vda-{}".format(VID))
        self.mq.will_set(vm.topic(VID, "connection"), json.dumps(
            vm.connection_payload(
                self.counters.header("connection", VID),
                "CONNECTIONBROKEN")), qos=1, retain=True)
        self.mq.on_connect = self._on_connect
        self.mq.on_disconnect = self._on_disconnect
        self.mq.on_message = self._on_message
        self.mq.connect_async(MQTT_HOST, MQTT_PORT)
        self.mq.loop_start()

    # ---- paho thread: enqueue only ----
    def _on_connect(self, client, userdata, flags, rc):
        self.inbox.put(("connected", None))

    def _on_disconnect(self, client, userdata, rc):
        if rc != 0:
            self.inbox.put(("lost", None))

    def _on_message(self, client, userdata, msg):
        self.inbox.put((msg.topic, msg.payload))

    # ---- ROS thread: everything else ----
    def cb_mode(self, msg):
        self.mode = msg.data
        self.publish_state("mode change")

    def cb_status(self, msg):
        state = parse_status(msg.data.encode())
        self.status_rx = time.monotonic()
        motor = bool(state["motor"]) if state else False
        healthy = bool(state["estop_healthy"]) if state else False
        changed = (motor, healthy) != (self.motor, self.estop_healthy)
        self.motor, self.estop_healthy = motor, healthy
        if changed:
            self.publish_state("safety change")

    def cb_fields(self, msg):
        try:
            self.pf_violated = vm.any_pf_false(json.loads(msg.data))
        except ValueError:
            self.pf_violated = True

    def cb_nav(self, msg):
        try:
            nav = json.loads(msg.data)
        except ValueError:
            return
        state, goal = nav.get("state", ""), nav.get("goal", "")
        arrived_now = (state == "ARRIVED" and self.nav_state != "ARRIVED"
                       and self.executing
                       and goal == self.order["orderId"])
        self.nav_state, self.nav_goal = state, goal
        if arrived_now:
            self.progress.complete()
            self.executing = False
            self.publish_state("arrived")

    def cb_odom(self, msg):
        p, q = msg.pose.pose.position, msg.pose.pose.orientation
        self.pose = (p.x, p.y, 2.0 * math.atan2(q.z, q.w))
        v = msg.twist.twist.linear
        self.speed = math.hypot(v.x, v.y)
        if self.executing and self.progress.update(self.pose[:2]):
            self.publish_state("node reached")

    def drain(self):
        while True:
            try:
                kind, payload = self.inbox.get_nowait()
            except queue.Empty:
                break
            if kind == "connected":
                self._announce()
            elif kind == "lost":
                self._supervision_lost()
            elif kind.endswith("/order"):
                self._on_order(payload)
            elif kind.endswith("/instantActions"):
                self._on_actions(payload)
        if time.monotonic() - self.last_state_pub >= STATE_PERIOD_S:
            self.publish_state("periodic")

    def _announce(self):
        self.mq.subscribe([(vm.topic(VID, "order"), 0),
                           (vm.topic(VID, "instantActions"), 0)])
        self.mq.publish(vm.topic(VID, "connection"), json.dumps(
            vm.connection_payload(
                self.counters.header("connection", VID), "ONLINE")),
            qos=1, retain=True)
        self.publish_factsheet()
        if self.order is not None and not self.executing \
                and self.progress.reached < len(self.progress.nodes):
            self._resume()
        self.publish_state("connected")

    def _supervision_lost(self):
        self.get_logger().warn("broker lost - controlled stop, order kept")
        if self.executing:
            self.pub_goal.publish(String(data=""))
            self.executing = False

    def _resume(self):
        remaining = self.progress.nodes[self.progress.reached:]
        points = [list(self.pose[:2])] + [
            [n["nodePosition"]["x"], n["nodePosition"]["y"]]
            for n in remaining]
        _, arrive_m, _, _ = vo.released_route(self.order)
        self.pub_route.publish(String(data=json.dumps(
            {"points": points, "arrive_m": arrive_m,
             "label": self.order["orderId"]})))
        self.executing = True
        self.get_logger().info("supervision back - route re-issued")

    def operating_mode(self):
        return "AUTOMATIC" if self.mode == MODE_AUTO else "MANUAL"

    def _on_order(self, payload):
        try:
            msg = json.loads(payload.decode())
        except (ValueError, UnicodeDecodeError):
            self.get_logger().warn("unreadable order dropped")
            return
        verdict, reason = vo.accept_order(
            msg, self.order["orderId"] if self.order else "",
            self.order["orderUpdateId"] if self.order else 0,
            self.executing, self.operating_mode())
        if verdict == "ignore":
            return
        if verdict == "reject":
            self.get_logger().warn("order rejected: {}".format(reason))
            self.publish_state("order rejected", extra_error={
                "errorType": "orderError", "errorLevel": "WARNING",
                "errorDescription": reason,
                "errorReferences": [{"referenceKey": "orderId",
                                     "referenceValue": str(
                                         msg.get("orderId", "?"))}]})
            return
        points, arrive_m, released, horizon = vo.released_route(msg)
        self.order, self.horizon = msg, horizon
        self.progress = vo.Progress(released)
        route = [list(self.pose[:2])] + [list(p) for p in points]
        self.pub_route.publish(String(data=json.dumps(
            {"points": route, "arrive_m": arrive_m,
             "label": msg["orderId"]})))
        self.executing = True
        self.publish_state("order accepted")

    def _on_actions(self, payload):
        try:
            actions = json.loads(payload.decode()).get("actions", [])
        except (ValueError, UnicodeDecodeError, AttributeError):
            return
        for act in actions:
            aid = str(act.get("actionId", "?"))
            kind = act.get("actionType", "")
            if kind == "cancelOrder":
                self.pub_goal.publish(String(data=""))
                self.order, self.progress = None, None
                self.horizon, self.executing = [], False
                self._set_action(aid, kind, "FINISHED")
            elif kind == "stateRequest":
                self._set_action(aid, kind, "FINISHED")
            elif kind == "factsheetRequest":
                self.publish_factsheet()
                self._set_action(aid, kind, "FINISHED")
            else:
                self._set_action(aid, kind, "FAILED")
        self.publish_state("actions handled")

    def _set_action(self, aid, kind, status):
        self.action_states = [a for a in self.action_states
                              if a["actionId"] != aid]
        self.action_states.append({"actionId": aid, "actionType": kind,
                                   "actionStatus": status})

    def order_ctx(self):
        if self.order is None:
            return {}
        last_id, last_seq = self.progress.last_node()
        remaining = self.progress.nodes[self.progress.reached:]
        node_states = [{"nodeId": n["nodeId"],
                        "sequenceId": n["sequenceId"], "released": True}
                       for n in remaining]
        node_states += [{"nodeId": n["nodeId"],
                         "sequenceId": n["sequenceId"], "released": False}
                        for n in self.horizon]
        return {"orderId": self.order["orderId"],
                "orderUpdateId": self.order["orderUpdateId"],
                "lastNodeId": last_id, "lastNodeSequenceId": last_seq,
                "nodeStates": node_states,
                "edgeStates": [],
                "newBaseRequest": bool(self.horizon) and not remaining}

    def publish_state(self, why, extra_error=None):
        now = time.monotonic()
        motor = self.motor and not is_stale(
            self.status_rx, now, STATUS_STALE_S)
        errors, safety = vm.errors_and_safety(
            motor, self.estop_healthy, self.pf_violated)
        if extra_error:
            errors = errors + [extra_error]
        state = vm.build_state(
            self.counters.header("state", VID), self.order_ctx(),
            self.pose, self.speed > DRIVING_MPS, self.operating_mode(),
            errors, safety, list(self.action_states))
        self.mq.publish(vm.topic(VID, "state"), json.dumps(state), qos=0)
        self.last_state_pub = now

    def publish_factsheet(self):
        with open(CONFIG_PATH, "r", encoding="utf-8") as handle:
            cfg = yaml.safe_load(handle)
        self.mq.publish(vm.topic(VID, "factsheet"), json.dumps(
            vm.build_factsheet(
                self.counters.header("factsheet", VID), cfg)),
            qos=0, retain=True)


def main():
    rclpy.init()
    node = VdaAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            node.mq.publish(vm.topic(VID, "connection"), json.dumps(
                vm.connection_payload(
                    node.counters.header("connection", VID), "OFFLINE")),
                qos=1, retain=True).wait_for_publish(timeout=2.0)
            node.mq.disconnect()
            node.mq.loop_stop()
        except Exception:
            pass
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()
```

Note the deliberate choices you must keep: unknown fields read as violated/False-motor (fail toward reporting trouble); the paho callbacks never touch state; the empty goal is the only stop this file ever commands. Check paho's installed major version: if paho-mqtt 2.x, the `mqtt.Client(...)` constructor needs `mqtt.CallbackAPIVersion.VERSION1` as first argument — adapt and record which you found.

- [ ] **Step 2: Integration test** — `tests/test_vda_agent_mqtt.py`, WSL-only, private broker on port 18883:

```python
"""The agent against a real broker - order in, route out, honest wires.

Runs a private mosquitto on 18883 (no collision with a live stack) and
a real rclpy context. Skips, loudly, when paho or the vendored broker
is absent - a skip here is an environment statement, not a pass.
"""
import json
import os
import subprocess
import time

import pytest

mqtt = pytest.importorskip("paho.mqtt.client")
rclpy = pytest.importorskip("rclpy")

BROKER = os.path.expanduser(
    "~/.local/mosquitto-vendored/usr/sbin/mosquitto")
pytestmark = pytest.mark.skipif(
    not os.path.exists(BROKER),
    reason="vendored mosquitto missing - run tools/install_broker.sh")

PORT = "18883"


@pytest.fixture()
def rig():
    from std_msgs.msg import String
    broker = subprocess.Popen([BROKER, "-p", PORT],
                              stdout=subprocess.DEVNULL,
                              stderr=subprocess.DEVNULL)
    time.sleep(0.5)
    os.environ["VDA_MQTT_PORT"] = PORT
    os.environ.setdefault("VEHICLE", "f1")
    rclpy.init()
    import vda_agent
    agent = vda_agent.VdaAgent()
    caught = {"route": [], "goal": [], "mqtt": []}
    helper = rclpy.create_node("test_helper")
    from status_contract import AUTO_ROUTE_TOPIC, AUTO_GOAL_TOPIC, \
        MODE_TOPIC, AUTO_STATE_TOPIC
    from rclpy.qos import DurabilityPolicy, QoSProfile
    helper.create_subscription(
        String, AUTO_ROUTE_TOPIC,
        lambda m: caught["route"].append(json.loads(m.data)), 10)
    helper.create_subscription(
        String, AUTO_GOAL_TOPIC,
        lambda m: caught["goal"].append(m.data), 10)
    latched = QoSProfile(
        depth=1, durability=DurabilityPolicy.TRANSIENT_LOCAL)
    mode_pub = helper.create_publisher(String, MODE_TOPIC, latched)
    nav_pub = helper.create_publisher(String, AUTO_STATE_TOPIC, 10)
    probe = mqtt.Client(client_id="probe")
    probe.on_message = lambda c, u, m: caught["mqtt"].append(
        (m.topic, json.loads(m.payload.decode())))
    probe.connect("127.0.0.1", int(PORT))
    probe.subscribe("uagv/v2/amragent/f1/#", qos=1)
    probe.loop_start()
    yield agent, helper, caught, mode_pub, nav_pub, probe
    probe.loop_stop()
    agent.destroy_node()
    helper.destroy_node()
    rclpy.try_shutdown()
    broker.terminate()
    broker.wait(timeout=5)


def spin(nodes, seconds):
    from rclpy.executors import SingleThreadedExecutor
    end = time.monotonic() + seconds
    ex = SingleThreadedExecutor()
    for n in nodes:
        ex.add_node(n)
    while time.monotonic() < end:
        ex.spin_once(timeout_sec=0.05)
    for n in nodes:
        ex.remove_node(n)


def valid_order():
    return {"orderId": "o-int-1", "orderUpdateId": 0,
            "nodes": [
                {"nodeId": "wp0", "sequenceId": 0, "released": True,
                 "actions": [], "nodePosition":
                     {"x": 0.0, "y": 0.0, "mapId": "warehouse"}},
                {"nodeId": "S4", "sequenceId": 2, "released": True,
                 "actions": [], "nodePosition":
                     {"x": 6.0, "y": -8.0, "mapId": "warehouse",
                      "allowedDeviationXY": 0.25}}],
            "edges": [
                {"edgeId": "e0", "sequenceId": 1, "released": True,
                 "startNodeId": "wp0", "endNodeId": "S4", "actions": []}]}


def test_online_retained_and_order_to_route(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    assert any(t.endswith("/connection") and p["connectionState"] == "ONLINE"
               for t, p in caught["mqtt"])
    assert any(t.endswith("/factsheet") for t, p in caught["mqtt"])
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert caught["route"], "no route published for a valid order"
    req = caught["route"][0]
    assert req["label"] == "o-int-1" and req["arrive_m"] == 0.25
    assert req["points"][-1] == [6.0, -8.0]
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    assert any(s["orderId"] == "o-int-1" for s in states)


def test_teleop_order_is_rejected_on_the_wire(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="teleop"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    assert not caught["route"]
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    assert any(any(e["errorType"] == "orderError" for e in s["errors"])
               for s in states)


def test_arrival_closes_the_order(rig):
    from std_msgs.msg import String
    agent, helper, caught, mode_pub, nav_pub, probe = rig
    spin([agent, helper], 1.5)
    mode_pub.publish(String(data="auto"))
    spin([agent, helper], 0.5)
    probe.publish("uagv/v2/amragent/f1/order",
                  json.dumps(valid_order()), qos=0)
    spin([agent, helper], 1.5)
    nav_pub.publish(String(data=json.dumps(
        {"state": "ARRIVED", "goal": "o-int-1"})))
    spin([agent, helper], 1.0)
    states = [p for t, p in caught["mqtt"] if t.endswith("/state")]
    done = [s for s in states if s["orderId"] == "o-int-1"
            and s["nodeStates"] == []]
    assert done and done[-1]["lastNodeId"] == "S4"
```

- [ ] **Step 3: Run**

WSL: `python3 -m pytest tests/test_vda_agent_mqtt.py -v` → 3 passed (or a loud skip you must then fix by running Task 1's installer). Whole WSL suite: 268 + 3 = **271**. Windows suite unaffected (file skips: no rclpy).

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/ipc/vda_agent.py m5_ver2/step6/tests/test_vda_agent_mqtt.py
git commit -m "step6: the vda agent - orders in over mqtt, routes out, state told honestly"
```

---

### Task 6: tools/send_order.py — the test-side master control

**Files:**
- Create: `m5_ver2/step6/tools/send_order.py`
- Test: `m5_ver2/step6/tests/test_send_order.py`

**Interfaces:**
- Produces: `build_order(order_id, poly, station_id, arrive_m) -> dict` (pure; poly EXCLUDES the vehicle pose — nodes are `wp1..wpN-1` + final `station_id`, interleaved sequenceIds, all released, edges joining); CLI `python3 tools/send_order.py f1 S4 [--watch]` — reads the vehicle's pose from its OWN MQTT state, plans with the vehicle's `route.plan_route`, publishes the order.

- [ ] **Step 1: Tests** (pure part):

```python
"""send_order's pure order builder against the vda_orders validator."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "tools")))

import send_order as so
import vda_orders as vo


def test_built_orders_validate_and_route():
    poly = [(-3.0, -5.5), (0.0, -5.5), (0.0, 5.65), (6.0, -8.0)]
    msg = so.build_order("o-t1", poly, "S4", 0.25)
    assert vo.validate_order(msg) == ""
    pts, arrive, rel, hor = vo.released_route(msg)
    assert pts == [(-3.0, -5.5), (0.0, -5.5), (0.0, 5.65), (6.0, -8.0)]
    assert arrive == 0.25 and hor == []
    assert rel[-1]["nodeId"] == "S4"
    assert rel[0]["nodeId"] == "wp1"
```

- [ ] **Step 2: Implement** — `tools/send_order.py`:

```python
"""send_order.py - a hand for master control until M6.3 exists.

Builds a FULL-ROUTE VDA 5050 order for one vehicle and one station:
reads the vehicle's current pose from its own MQTT state (no ROS - the
rig rule about starting ROS nodes stays unbroken), plans with the same
route.plan_route the on-board HMI path uses, then publishes the order.
The route the fleet sends is therefore the route the vehicle would have
planned - full-route following is exercised without inventing a second
planner. M6.3 replaces this file.

Usage (WSL, broker and stack up, vehicle in auto):
  python3 m5_ver2/step6/tools/send_order.py f1 S4 [--watch]
"""
import argparse
import json
import os
import sys
import time
import uuid

import paho.mqtt.client as mqtt

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(_HERE, "..", "ipc")))
import route                                        # noqa: E402
import vda_messages as vm                           # noqa: E402
from stations import STATIONS                       # noqa: E402


def build_order(order_id, poly, station_id, arrive_m):
    """poly excludes the pose; last point IS the station."""
    nodes, edges = [], []
    for i, (x, y) in enumerate(poly):
        last = i == len(poly) - 1
        node = {"nodeId": station_id if last else "wp{}".format(i + 1),
                "sequenceId": 2 * i, "released": True, "actions": [],
                "nodePosition": {"x": x, "y": y, "mapId": "warehouse"}}
        if last:
            node["nodePosition"]["allowedDeviationXY"] = arrive_m
        nodes.append(node)
        if not last:
            edges.append({"edgeId": "e{}".format(i),
                          "sequenceId": 2 * i + 1, "released": True,
                          "startNodeId": node["nodeId"],
                          "endNodeId": "", "actions": []})
    for edge, node in zip(edges, nodes[1:]):
        edge["endNodeId"] = node["nodeId"]
    return {"orderId": order_id, "orderUpdateId": 0,
            "nodes": nodes, "edges": edges}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("vehicle")
    parser.add_argument("station")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    args = parser.parse_args()
    if args.station not in STATIONS:
        raise SystemExit("unknown station {}".format(args.station))

    got = {}

    def on_msg(client, userdata, msg):
        got["state"] = json.loads(msg.payload.decode())

    client = mqtt.Client(client_id="send-order")
    client.on_message = on_msg
    client.connect(args.host, args.port)
    client.subscribe(vm.topic(args.vehicle, "state"), qos=0)
    client.loop_start()
    deadline = time.monotonic() + 10.0
    while "state" not in got and time.monotonic() < deadline:
        time.sleep(0.1)
    if "state" not in got:
        raise SystemExit("no state from {} - agent up? broker up?"
                         .format(args.vehicle))
    pos = got["state"]["agvPosition"]
    poly = route.plan_route((pos["x"], pos["y"]), args.station)
    if poly is None:
        raise SystemExit("no route to {}".format(args.station))
    arrive_m = STATIONS[args.station].get("arrive_m", 0.25)
    order_id = "o-{}".format(uuid.uuid4().hex[:8])
    msg = build_order(order_id, poly[1:], args.station, arrive_m)
    client.publish(vm.topic(args.vehicle, "order"),
                   json.dumps(msg), qos=0)
    print("sent", order_id, "to", args.vehicle, "->", args.station,
          "({} nodes)".format(len(msg["nodes"])))
    if args.watch:
        try:
            while True:
                time.sleep(1.0)
                s = got.get("state", {})
                print("  {} last={} remaining={} driving={} errs={}".format(
                    s.get("orderId", "?"), s.get("lastNodeId", "?"),
                    len(s.get("nodeStates", [])), s.get("driving"),
                    len(s.get("errors", []))))
                if s.get("orderId") == order_id \
                        and not s.get("nodeStates"):
                    print("ARRIVED"); break
        except KeyboardInterrupt:
            pass
    client.loop_stop()


if __name__ == "__main__":
    main()
```

(Same paho 1.x/2.x constructor caveat as Task 5 — keep both files consistent.)

- [ ] **Step 3: GREEN + suite** — Windows/WSL unit passes (paho import inside main only? No — module-level; the test imports the module, so paho must be present where the test runs: mark the test `importorskip("paho.mqtt.client")` at the top if Windows lacks paho, and say so in the report). WSL suite: 271 + 1 = **272**.

- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/tools/send_order.py m5_ver2/step6/tests/test_send_order.py
git commit -m "step6: send_order - master control's hand until m6.3"
```

---

### Task 7: The agents join the stack

**Files:**
- Modify: `m5_ver2/step6/step6.sh`, `m5_ver2/step6/README_step6.md`, `m5_ver2/step6/CONTEXT.md`

- [ ] **Step 1: step6.sh** — in the per-vehicle loop, after `nav_node`: `spawn "vda_agent_$vid" "$vid" python3 "$IPC/vda_agent.py"`. `PATTERNS` += `"vda_agent.py"`. Startup expectation becomes 20 pids (broker + world + 9×2). The final echo gains one line: orders come over MQTT (`tools/send_order.py f1 S4`).
- [ ] **Step 2: Docs** — README_step6: a "VDA 5050" section (broker install one-liner, paho version, send_order usage, topic root, what the factsheet declares); CONTEXT.md: extend the step6 header — the agent exists, full-route ruling, safetyState-is-reporting-only invariant, M6.3 takes the broker and send_order's job.
- [ ] **Step 3: Verify** — `bash -n`; `./step6.sh deploy && start --headless` → 20 pids incl. two agents (their logs show ONLINE published), `stop` clean; suite unchanged **272**.
- [ ] **Step 4: Commit**

```bash
git add m5_ver2/step6/step6.sh m5_ver2/step6/README_step6.md m5_ver2/step6/CONTEXT.md
git commit -m "step6: the vda agents join the stack - mqtt is a lifecycle citizen"
```

---

### Task 8: The six live gates

**Files:**
- Modify: `m5_ver2/step6/PROOF.md`

Run the spec's six proof gates on the live rig (scripted writers on ctl 5910/5920 as in M6.1's machine-run gates; the rig rule holds — ONE pre-started recorder, RESET after settle; mode via the TRANSIENT_LOCAL CLI publish). For each gate: commands verbatim, captured output (folded where long, say so), numbers, the label "measured by the scripted driver + CLI — no panel, no human", date. The gates are the spec's, unchanged:

1. MQTT-only drive, both vehicles, distinct stations, ARRIVED + 0 motor-false + nodeStates draining in the captured state stream.
2. Rejections (teleop; second order while executing) with the errors[] entry on the wire and the current drive undisturbed.
3. cancelOrder mid-drive: controlled stop, order cleared, FINISHED actionState, new order restarts.
4. Supervision loss mid-drive (SIGSTOP the broker or drop its process — record which): controlled stop, order kept, broker back → resume → ARRIVED; Motor never drops.
5. Connection lifecycle: ONLINE retained (fresh subscriber sees it), OFFLINE on clean stop, kill -9 → CONNECTIONBROKEN last will observed.
6. State honesty: Gate-2 box trip mid-drive → fieldViolation true + FATAL error + driving false in the stream; heal + ack → clean again. The MQTT stream caused none of it.

If a gate FAILS: record it measured-and-failed, do not tick, report BLOCKED. Teardown + suites (step6 **272**, step5 220) at the end.

```bash
git add m5_ver2/step6/PROOF.md
git commit -m "step6: the vda gates - six measured, the wire tells the truth"
```
