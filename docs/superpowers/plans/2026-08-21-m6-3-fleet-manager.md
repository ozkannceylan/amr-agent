# M6.3 Fleet Manager Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** a paho-only fleet manager in `m5_ver2/step6/fleet/` that turns A→B transport tasks into two-leg VDA 5050 orders, assigns them nearest-idle, and survives rejection, vehicle loss and its own restart.

**Architecture:** pure decisions in `fleet_core.py` (registry, FIFO queue with requeue-to-head, task state machine, nearest-idle via the vehicle's own route graph); `order_builder.py` makes the orders; `fleet_manager.py` is thin paho wiring; `fleet_cli.py` is the operator. Spec: `docs/superpowers/specs/2026-08-21-m6-3-fleet-manager-design.md` — read it first; its Loss/Restart paragraphs are normative and subtle (auto-resume race; adopt-by-waiting).

**Tech Stack:** plain Python 3, paho-mqtt 2.1.0 (API 2.x: `mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=...)`, 5-arg callbacks), pytest. NO rclpy anywhere in fleet/ — the fleet layer never touches ROS (standing invariant).

## Global Constraints

- Only `m5_ver2/step6/` changes. Steps 1-5, step5, `agv/`, the safety chain, `ipc/vda_orders.py`, `ipc/vda_messages.py`, `ipc/nav_*` untouched (exceptions named per task: `ipc/vda_agent.py` gets ONE bounded-reconnect edit in Task 1; `tests/conftest.py` one line).
- The graph's single home stays `ipc/route.py` + `ipc/stations.py`; fleet imports them (sys.path the ipc dir), never copies them.
- Fleet orders carry orderId prefix `ft-`; every order must pass `ipc/vda_orders.validate_order` before publish.
- MQTT: vehicles at `uagv/v2/amragent/<vid>/...`; admin at `fleet/task/submit` (QoS 1) and `fleet/status` (QoS 1, **retained**). Broker localhost:1883, `VDA_MQTT_PORT` env override honored everywhere for tests.
- Suites: WSL step6 baseline **302**, step5 **220** — no regressions. Windows: fleet unit tests must run (paho present? NO — Windows lacks paho: importorskip pattern from test_send_order.py; report which env ran what).
- Commit style `step6: ...` lowercase, no attribution, no Claude mention.
- Known rig facts: vendored broker needs `LD_LIBRARY_PATH` (step6.sh `BROKER_LIB`); agent auto-resumes kept orders on reconnect (gate scripts must expect the race); stack is 20 pids before this plan, 21 after.

---

### Task 1: Carry-in hygiene

**Files:** Modify `m5_ver2/step6/ipc/vda_agent.py` (reconnect bound), `m5_ver2/step6/tests/conftest.py` (DDS fence), `m5_ver2/step6/tools/send_order.py` (superseded header).

- [ ] In `VdaAgent.__init__`, after the callbacks are set and before `connect_async`: `self.mq.reconnect_delay_set(min_delay=1, max_delay=8)` with a comment citing Gate 4's measured 28.1 s unbounded reconnect. paho 2.x logs retries itself at WARNING when `enable_logger()` is on — instead of relying on that, add one line in `_on_disconnect`'s failure branch: `self.get_logger().warn("broker link down - retrying inside 1-8 s")`.
- [ ] `tests/conftest.py`: after the VEHICLE setdefault, `os.environ["ROS_DOMAIN_ID"] = "89"` (explicit set) with the comment: the live stack runs 96 and PROOF's runbooks export 96 in the operator's shell; the suite must never join it.
- [ ] `tools/send_order.py` docstring gains a first line: `SUPERSEDED by fleet/fleet_cli.py + fleet/fleet_manager.py (M6.3) - kept as a low-level debug probe.`
- [ ] Verify: WSL suite 302 (no count change); grep confirms the fence line; commit `step6: m6.2 debts paid - bounded reconnect, fenced suite, superseded probe`.

---

### Task 2: fleet_core — the pure decisions

**Files:** Create `m5_ver2/step6/fleet/__init__.py` (empty), `m5_ver2/step6/fleet/fleet_core.py`; Test `m5_ver2/step6/tests/test_fleet_core.py`.

**Interfaces (normative):**

```python
# vehicles: dict serial -> Vehicle (plain dict is fine):
#   {"connection": "ONLINE"|"OFFLINE"|"CONNECTIONBROKEN"|None,
#    "operating_mode": str|None, "position": (x, y)|None,
#    "executing_order": str|None (orderId from last state, "" -> None),
#    "state_age_s": float|None, "lost": bool,
#    "not_eligible": bool}   # set by the manager after a rejection or
#                            # a loss-return; idle_confirmed refuses it;
#                            # the manager clears it on the first state
#                            # satisfying every OTHER idle clause
# tasks: list of Task dicts, index 0 = queue head:
#   {"task_id": str, "from": str, "to": str,
#    "state": "QUEUED"|"ASSIGNED_LEG1"|"DWELL"|"ASSIGNED_LEG2"|"DONE",
#    "assignee": str|None, "history": [str, ...]}

IDLE_FRESH_S = 3.0   # a state older than this cannot confirm idleness

def idle_confirmed(vehicle) -> bool
    # ONLINE, AUTOMATIC, executing_order None, state_age_s is not None
    # and <= IDLE_FRESH_S, and not lost. Every clause is a test.

def nearest_idle(vehicles, pickup_station, distance_fn) -> str | None
    # distance_fn(position_xy, station_id) -> float|None (None = no route).
    # Only idle_confirmed vehicles compete; ties break by serial sort;
    # a vehicle with no position or no route never wins.

def next_assignment(vehicles, tasks, distance_fn) -> (task, serial) | None
    # The queue HEAD only (FIFO is a promise, not a hint): if the head
    # task is QUEUED and someone idle can take it -> that pair; if the
    # head is QUEUED and nobody idle -> None (never skip the head).

def requeue_to_head(tasks, task_id, why) -> None
    # Task back to state QUEUED at index 0, assignee cleared, why
    # appended to history. Position: BEFORE every other QUEUED task.

def advance(task, event) -> str
    # The task state machine. Events: "leg1_sent", "leg1_arrived",
    # "dwell_done", "leg2_sent", "leg2_arrived". Illegal event for the
    # current state -> ValueError naming both. Returns the new state.
    # QUEUED -leg1_sent-> ASSIGNED_LEG1 -leg1_arrived-> DWELL
    #        -dwell_done-> (leg2 is sent by the caller) ... the caller
    # calls advance(task, "leg2_sent") -> ASSIGNED_LEG2
    #        -leg2_arrived-> DONE
```

- [ ] TDD: write `tests/test_fleet_core.py` first — the matrix IS the spec:

```python
"""fleet_core - assignment, queue and state machine. Pure."""
import pytest

from fleet_core import (IDLE_FRESH_S, advance, idle_confirmed,
                        nearest_idle, next_assignment, requeue_to_head)


def veh(**over):
    v = {"connection": "ONLINE", "operating_mode": "AUTOMATIC",
         "position": (0.0, 0.0), "executing_order": None,
         "state_age_s": 1.0, "lost": False, "not_eligible": False}
    v.update(over)
    return v


def task(tid="t1", state="QUEUED", **over):
    t = {"task_id": tid, "from": "S1", "to": "S4",
         "state": state, "assignee": None, "history": []}
    t.update(over)
    return t


@pytest.mark.parametrize("breaker", [
    {"connection": "CONNECTIONBROKEN"}, {"connection": "OFFLINE"},
    {"connection": None}, {"operating_mode": "MANUAL"},
    {"operating_mode": None}, {"executing_order": "ft-x"},
    {"state_age_s": IDLE_FRESH_S + 0.1}, {"state_age_s": None},
    {"lost": True}, {"not_eligible": True}])
def test_every_idle_clause_bites(breaker):
    assert idle_confirmed(veh()) is True
    assert idle_confirmed(veh(**breaker)) is False


def test_nearest_idle_picks_the_shorter_route_not_the_crow_flies():
    vehicles = {"f1": veh(position=(1.0, 0.0)),
                "f2": veh(position=(2.0, 0.0))}
    fn = lambda pos, sid: 10.0 if pos == (1.0, 0.0) else 3.0
    assert nearest_idle(vehicles, "S4", fn) == "f2"


def test_nearest_idle_tie_breaks_by_serial():
    vehicles = {"f2": veh(), "f1": veh()}
    assert nearest_idle(vehicles, "S4", lambda p, s: 5.0) == "f1"


def test_no_route_and_no_position_never_win():
    vehicles = {"f1": veh(position=None), "f2": veh()}
    assert nearest_idle(vehicles, "S4", lambda p, s: None) is None
    assert nearest_idle(vehicles, "S4",
                        lambda p, s: 5.0) == "f2"   # f1 has no position


def test_fifo_head_is_never_skipped():
    vehicles = {"f1": veh(executing_order="ft-busy")}
    tasks = [task("t1"), task("t2")]
    assert next_assignment(vehicles, tasks, lambda p, s: 1.0) is None
    vehicles["f1"] = veh()
    got = next_assignment(vehicles, tasks, lambda p, s: 1.0)
    assert got == (tasks[0], "f1")


def test_head_that_is_not_queued_yields_the_next_queued():
    # An ASSIGNED head is in flight, not skippable-vs-waiting: the next
    # QUEUED task behind it may be assigned to another idle vehicle.
    vehicles = {"f2": veh()}
    tasks = [task("t1", state="ASSIGNED_LEG1", assignee="f1"), task("t2")]
    got = next_assignment(vehicles, tasks, lambda p, s: 1.0)
    assert got == (tasks[1], "f2")


def test_requeue_to_head_goes_in_front_of_other_queued():
    tasks = [task("t1", state="ASSIGNED_LEG1", assignee="f1"),
             task("t2"), task("t3")]
    requeue_to_head(tasks, "t1", "vehicle lost")
    assert [t["task_id"] for t in tasks][0] == "t1"
    head = tasks[0]
    assert head["state"] == "QUEUED" and head["assignee"] is None
    assert "vehicle lost" in head["history"][-1]


def test_state_machine_happy_path_and_illegal_moves():
    t = task()
    for event, want in (("leg1_sent", "ASSIGNED_LEG1"),
                        ("leg1_arrived", "DWELL"),
                        ("leg2_sent", "ASSIGNED_LEG2"),
                        ("leg2_arrived", "DONE")):
        t["state"] = advance(t, event)
        assert t["state"] == want
    with pytest.raises(ValueError):
        advance(t, "leg1_sent")          # DONE accepts nothing
    with pytest.raises(ValueError):
        advance(task(), "leg2_arrived")  # QUEUED can't finish
```

- [ ] Implement `fleet_core.py` to the matrix (< 150 lines is achievable here — this module has no excuse). Docstring: the fleet layer's three standing invariants (no ROS; MQTT-only to vehicles; degrade-never-endanger) and the owner rulings (two-leg, requeue-to-head).
- [ ] WSL suite 302 → 302 + collected items (report actuals); Windows: this file is pure — must pass there too.
- [ ] Commit `step6: fleet_core - who drives what, decided pure`.

---

### Task 3: order_builder

**Files:** Create `m5_ver2/step6/fleet/order_builder.py`; Test `m5_ver2/step6/tests/test_order_builder.py`.

**Interfaces:** `build_leg_order(order_id, start_xy, station_id) -> dict | None` — plans via `route.plan_route(start_xy, station_id)` (import from the ipc dir, sys.path pattern from `tools/send_order.py`), drops the pose point (`poly[1:]`), builds the M1 order exactly as `send_order.build_order` does (wp ids, interleaved sequenceIds, all released, station last with its `arrive_m` from `stations.py`), returns None when no route. `leg2_start(pickup_station_id) -> (x, y)` — the pickup station's coordinates (leg 2 is planned from where leg 1 ends, not from live pose: the truck is standing there by definition; one comment says so).

- [ ] TDD — tests: a built leg order passes `vda_orders.validate_order` and `released_route` round-trips; order_id prefix preserved verbatim (caller owns `ft-`); leg-2 order for (S4→S7) starts its polyline at S4's coordinates (assert first node == plan_route's first post-pose node when planned from S4's (x, y)); unknown station → None; every (station, station) pair from a sweep over all 10×9 ordered pairs validates (the send_order sweep pattern, now fleet-side).
- [ ] Commit `step6: order_builder - the fleet's own order factory`.

---

### Task 4: fleet_manager + integration test

**Files:** Create `m5_ver2/step6/fleet/fleet_manager.py`; Test `m5_ver2/step6/tests/test_fleet_manager_mqtt.py` (WSL-only; the private-broker fixture pattern from `test_vda_agent_mqtt.py` INCLUDING `LD_LIBRARY_PATH` and port 18884 — not 18883, so both integration files can never collide).

**Normative shape** (~200 lines; deviations reported, not silent):

- paho 2.x client `fleet-manager`; will NOT set (the fleet's death is not a vehicle protocol event; status retained goes stale and that is the signal — one comment). Subscribes `uagv/v2/amragent/+/connection|state|factsheet` + `fleet/task/submit`. All callbacks ENQUEUE into a `queue.Queue`; the main loop drains at 10 Hz (plain `time.sleep` loop — no ROS executor here), does all work single-threaded, publishes status on change and every 2 s.
- Registry updates: connection payloads set `connection` (+ `lost=True` on CONNECTIONBROKEN when the vehicle held an active task → `requeue_to_head` + the task's orderId remembered as stale-on-that-vehicle); state payloads set mode/position (`agvPosition` x,y)/`executing_order` (`orderId` or None when "")/`state_age` (stamp receipt time; age computed at status build). A LOST vehicle returning ONLINE with a remembered stale `ft-` order → publish `cancelOrder` instantAction (uuid actionId) to it once, log the race honestly (agent may drive until it lands); it stays ineligible until `idle_confirmed`.
- Assignment loop each drain: `next_assignment(...)` with `distance_fn` = route length via `route.plan_route` (sum of segment lengths; None when no route) → `build_leg_order("ft-<hex8>", vehicle.position, task.from)` → validate → publish to the vehicle's order topic → `advance(task, "leg1_sent")`, record assignee + orderId.
- ARRIVED detection: a state from the assignee whose `orderId` matches the leg's order and `nodeStates == []` → leg 1: `advance("leg1_arrived")`, stamp dwell start; a drain pass with dwell elapsed (`DWELL_S = 3.0`) → build leg-2 from `leg2_start(task.from)` → publish → `advance("leg2_sent")`; leg 2 arrival → `advance("leg2_arrived")` → DONE.
- Rejection: a state carrying an `orderError` whose reference names our in-flight orderId → `requeue_to_head`, and the manager sets that vehicle's `not_eligible=True` (Task 2's tenth idle clause), clearing it on the first state that satisfies every OTHER idle clause.
- Restart re-sync: on start, nothing special — retained connection arrives on subscribe; states flow within 2 s; `idle_confirmed` requires fresh state so no assignment can fire early; a vehicle executing an `ft-` order is simply not idle (adopt-by-waiting falls out of the rules — one comment says so; NO cancelOrder path at startup).
- Status document (`fleet/status`, retained, QoS 1): `{"ts", "vehicles": {serial: {connection, operating_mode, position, executing_order, state_age_s, lost/not_eligible}}, "tasks": [task dicts verbatim], "queue_len"}`. The age is computed at build time — a dead feed shows a growing age, never a frozen "driving" (Gate 6 carry-in; say it in the docstring).
- Admin: `fleet/task/submit` payload `{"taskId","from","to"}` — validated (stations exist, from != to, taskId non-empty unique); refusals recorded in the status document under `"refused": [{taskId, why}]` (bounded to last 10).
- `main()`: argparse `--host/--port` (VDA_MQTT_PORT default), clean shutdown publishes a final status with `"manager": "OFFLINE"` field then disconnects.

**Integration test** (private broker 18884, fake vehicles — pure paho scripted state machines, no rclpy): (1) submit two tasks with two idle fakes → each receives a leg-1 order (validate them), fakes walk ARRIVED → dwell → leg-2 → DONE appears in retained status; (2) a fake rejects with orderError → task requeued to head → other fake gets it; (3) fake's CONNECTIONBROKEN (will) mid-leg → requeue + reassignment, returning fake receives cancelOrder; (4) manager restart mid-executing-fake → no new order to that fake until it reports idle, no cancelOrder observed at startup, queue empty and honest. Fakes publish plausible state payloads (reuse `vda_messages.build_state` + `Counters` — imported from ipc, they are pure).

- [ ] Commit `step6: fleet_manager - master control, degrade-never-endanger`.

---

### Task 5: fleet_cli + stack + docs

**Files:** Create `m5_ver2/step6/fleet/fleet_cli.py`; Modify `m5_ver2/step6/step6.sh`, `README_step6.md`, `CONTEXT.md`; Test `m5_ver2/step6/tests/test_fleet_cli.py` (pure parts: submit payload build, status rendering from a fixture document).

- `fleet_cli.py` signature is `submit FROM TO` — the operator names stations, never vehicles; the fleet picks the vehicle. `python3 fleet/fleet_cli.py submit S1 S4 [--task-id ...]` publishes QoS 1, prints the generated `ft-` taskId, exits 0; `status [--watch]` reads retained `fleet/status`, renders a fixed-width table (vehicles then tasks, ages in s, one line per row), `--watch` re-renders each retained update until Ctrl-C. paho 2.x, VDA_MQTT_PORT honored, errors named (no broker, no retained status yet).
- `step6.sh`: `spawn fleet - python3 "$STEP6/fleet/fleet_manager.py"` AFTER both vehicle loops (comment: the manager assigns nothing until fresh states anyway, but late spawn keeps startup ordering legible); PATTERNS += `"fleet_manager.py"`; 21-pid prose sweep (non-decaying style); deploy() ships `fleet/` (`cp -r "$STEP6/fleet" "$DEPLOY/m5_ver2/step6/fleet"` + stale_check mapping + MANIFEST count update); final echo: submit via `python3 fleet/fleet_cli.py submit S1 S4`.
- README: "Fleet manager" section (what it is, CLI usage, status document location, the no-journal restart honesty); CONTEXT: header extension (M6.3 exists, rulings, the loss-race, adopt-by-waiting, M6.4 takes traffic).
- Verify: `bash -n`; deploy + start --headless → **21 pids**, manager log shows subscribe + first retained status; `fleet_cli.py status` renders from retained doc with no vehicles driving; stop clean; suites (step6 302+new, step5 220).
- [ ] Commit `step6: the fleet joins the stack - and the operator gets a truthful screen`.

---

### Task 6: The six live gates

**Files:** Modify `m5_ver2/step6/PROOF.md` only (helper scripts in the scratchpad, uncommitted).

Method library: PROOF.md's M6.1/M6.2 gate sections (rig rules, scripted writers ctl 5910/5920, mode publish QoS, recorder discipline, teardown). Run the spec's six gates; per gate: commands verbatim, folded captures, numbers, the machine-run label, date. Also record the manager's assignment DISTANCES in Gate 1 (the nearest-idle evidence: both vehicles' route lengths to the pickup, who won, why). Gate 4 must measure the auto-resume race window (return → cancelOrder landing → stop). If a gate fails: record measured-and-failed, don't tick, BLOCKED. Teardown + suites at the end.

- [ ] Commit `step6: the fleet gates - six measured, tasks flow, trucks survive us`.
