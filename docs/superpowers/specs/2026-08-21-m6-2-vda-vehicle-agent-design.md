---
title: M6.2 — VDA 5050 vehicle agent (full-route)
date: 2026-08-21
status: approved
---

# M6.2: the VDA 5050 vehicle agent — full-route orders over MQTT

## Where this sits

Second of M6's five sub-projects (decomposition: AMR-DEC-002). M6.1 gave
two isolated vehicles in one world. M6.2 gives each vehicle a VDA 5050
2.1.0 client so master control can drive it over MQTT — the protocol leg
M6.3's fleet manager will stand on. Normative message contract:
`docs/interfaces/vda5050-subset.md` (M1), every field decision below is
traceable to it.

**Owner ruling 2026-08-21: full-route orders from day one.** The fleet
sends `nodes` + `edges`; the vehicle drives the released nodes exactly,
in sequence — it does not re-route. (The single-node alternative was
rejected; M6.4's edge/zone reservation needs the route in the order.)

## Non-goals

- No fleet manager (M6.3) — `tools/send_order.py` is a test tool that
  builds and publishes orders; M6.3 supersedes it.
- No traffic logic, no zone reservation (M6.4).
- Actions NOT implemented in M6.2: startPause/stopPause (M6.4's
  fleet-hold pair), startCharging/stopCharging (no battery reality),
  initPosition (ground-truth pose; nothing to init). The factsheet
  declares ONLY the implemented actions — a deliberate, recorded
  deviation from the M1 table's "exactly the eight": the factsheet is
  the machine-readable truth and must not advertise what would FAIL.
- No order updates/stitching: an order carrying `orderUpdateId > 0`, or
  a new `orderId` while one is executing, is REJECTED with an `errors[]`
  entry (fleet must `cancelOrder` first). Spec 6.6 stitching lands with
  M6.3 when something exists to exercise it.
- `edge.maxSpeed` is parsed but not enforced;
  `protocolFeatures.optionalParameters` declares it unsupported. The
  follower's own speed law (corner bands, guard, V_Limit) stays the
  only authority until M6.4 needs slow zones.
- No change to the safety chain, the writer, or steps 1-5.

## Architecture

Three pieces, all step6-side:

**1. The nav seam — externally supplied routes.** `NavCore` gains
`on_route(points, arrive_m, label)`: installs a polyline exactly as
`on_goal` does after planning, but the polyline arrives from outside;
same MODE_AUTO guard, same cancel path, same follower/guard/ARRIVED
machinery untouched. `nav_node` subscribes a new contract name
`AUTO_ROUTE_TOPIC` (`/<vid>/auto/route`), JSON
`{"points": [[x,y],...], "arrive_m": float, "label": "<orderId>"}`.
The station-goal path (`AUTO_GOAL_TOPIC`) stays for the HMI; the empty
goal (`""`) remains the one cancel door and the agent reuses it.

**2. The agent — `ipc/vda_agent.py` + `ipc/vda_messages.py`, one agent
per vehicle** (env `VEHICLE`, spawned by `step6.sh`, deployed like every
node). `vda_messages.py` is pure (no ROS, no MQTT): header counters,
order validation, accept/reject decision, node-progress tracking, state
and factsheet builders — heavily unit-tested. `vda_agent.py` is wiring:
an rclpy node plus a paho-mqtt client (localhost:1883).

- Topic root `uagv/v2/amragent/<vid>/…` (manufacturer `amragent`,
  serialNumber = vehicle id).
- `connection`: QoS 1 retained; last-will `CONNECTIONBROKEN` registered
  before connect; `ONLINE` on connect; `OFFLINE` on clean shutdown
  (M1 §7 protocol, verbatim).
- `state`: QoS 0; on events (order accepted/rejected, node reached,
  ARRIVED, driving flip, error set change, mode change) and every 2 s.
  Content per M1 §5: `agvPosition` from the bridged odom (pose fields
  only — frame ids untouched, the M6.1 TF limitation is not triggered),
  `driving` from motion, `operatingMode` AUTOMATIC iff the latched mode
  is `auto` else MANUAL, `errors[]` + `safetyState` mapped from
  `/​<vid>/plc/status` and the fields verdicts (`eStop`: MANUAL when
  `estop_healthy` is False or Motor is latched away, else NONE;
  `fieldViolation`: any protective field False). `batteryState` is the
  honest stub `{batteryCharge: 100.0, charging: false}` — the sim has
  no battery; the field is schema-required.
  **safetyState is reporting only — the M1 invariant is restated in the
  agent's docstring: no safety function may depend on MQTT.**
- `factsheet`: retained, on connect and on `factsheetRequest`. Truthful
  for THIS vehicle: `agvClass` FORKLIFT, `agvKinematic` THREEWHEEL,
  `navigationTypes ["AUTONOMOUS"]`, speeds/geometry from
  `config.yaml`'s limits and model mirrors, `agvActions` = exactly the
  implemented set.
- `order`: validate per M1 §4 (required fields, `nodePosition` present,
  sequence sanity). Accept iff operatingMode is AUTOMATIC and no order
  is executing. Released nodes → polyline → `AUTO_ROUTE_TOPIC` with the
  last node's `allowedDeviationXY` (default 0.25) as `arrive_m`.
  Horizon (unreleased) nodes are stored and reported in `nodeStates`
  with `released: false`, never driven. Progress: the agent marks node
  k reached when the pose enters that node's deviation radius (monotone
  k); `lastNodeId`/`lastNodeSequenceId`/`nodeStates`/`edgeStates`
  shrink accordingly; nav's ARRIVED closes the order.
- `instantActions`: `cancelOrder` (publish the empty goal, clear the
  order, actionState FINISHED — a controlled stop through the normal
  chain, never a safety stop), `stateRequest`, `factsheetRequest`.
  Anything else → actionState FAILED, error entry `unsupportedAction`.
- **Supervision loss** (M1 §7 vehicle rule): on broker disconnect the
  agent publishes the empty goal (controlled stop), KEEPS the order,
  and on reconnect re-issues the remaining released nodes as a fresh
  route from the current pose. Broker loss is degraded mode, not a
  safety event.
- Threading: paho runs its own network thread; its callbacks only
  enqueue; a 10 Hz rclpy timer drains the queue and does all work in
  the ROS thread. Publishes to MQTT go through paho's thread-safe
  `publish()`.

**3. The broker — mosquitto, user-space, no sudo.**
`tools/install_broker.sh` downloads the Ubuntu package with
`apt-get download mosquitto` and extracts it with `dpkg-deb -x` into
`~/.local/mosquitto-vendored/` (idempotent; no root; the binary is NOT
committed). `step6.sh` spawns it (`spawn broker - <path>/mosquitto -p
1883` with a minimal conf allowing localhost), pre-flights port 1883
exactly like the PLC ports, adds it to the name list; `stop` sweeps it
(PATTERNS entry). A comment records that the broker moves to the fleet
side in M6.3 — today one machine hosts both ends.

`pip3 install --user paho-mqtt` provides the client; the installed
version is recorded in README_step6.

## Error handling

- Agent dies → broker publishes the retained last-will
  `CONNECTIONBROKEN`; the vehicle itself keeps driving its current
  route (the agent is master-control plumbing, not a safety layer) —
  recorded plainly in the docstring and PROOF.
- Broker dies → supervision loss: controlled stop as above.
- Malformed order/instantAction → rejected with an `errors[]` entry in
  the next state; never a crash (parse failures logged, ignored).
- All existing fail-safe paths (gate, mux, writer, F-model) untouched.

## Proof gates (live, scripted-writer rig, recorded in PROOF.md)

1. **MQTT-only drive:** both vehicles complete full-route orders
   (distinct stations) sent over MQTT with NO HMI goal involvement —
   ARRIVED both, 0 motor-false each, state streams captured showing
   nodeStates draining and lastNodeId advancing.
2. **Rejection rules:** an order in teleop mode and an order while one
   executes are both rejected with the errors[] entry, and the vehicle's
   current drive is undisturbed.
3. **cancelOrder mid-drive:** controlled stop through the normal chain,
   order cleared, actionState FINISHED, truck restartable by a new
   order.
4. **Supervision loss mid-drive:** broker (or link) down → controlled
   stop with order kept; broker back → resume from current pose →
   ARRIVED. Motor never drops (this is not a safety path — prove it).
5. **Connection lifecycle:** ONLINE retained on connect; OFFLINE on
   clean shutdown; kill -9 the agent → subscribers receive the broker's
   CONNECTIONBROKEN last will.
6. **State honesty:** trip a protective field mid-drive (Gate-2 box) →
   state shows `fieldViolation: true`, a FATAL error, `driving: false`;
   heal + ack → error clears. The MQTT stream never CAUSES any of it.

## Testing

- Unit (pure, Windows+WSL): vda_messages — header counters per topic,
  order validation matrix (missing fields, bad sequences, update
  rejection, teleop rejection), progress tracker monotonicity, state
  builder field-by-field against M1 §5, factsheet builder.
- Unit (nav): on_route installs/mode-guards/cancels exactly like
  on_goal; existing nav tests stay green.
- Integration (WSL, real mosquitto, no Gazebo): the agent node against
  scripted ROS-side feeds — order in → route published; fake ARRIVED →
  order closed on the wire; will/ONLINE/OFFLINE observed.
- The six proof gates above.

## M6.1 carry-ins folded here

None structurally required: the agent reads odom pose fields, not frame
ids (TF limitation untriggered). Live-gate procedure inherits the rig
rule: one pre-started recorder process, RESET after settle.
