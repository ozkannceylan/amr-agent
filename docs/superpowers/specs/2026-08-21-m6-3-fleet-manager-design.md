---
title: M6.3 — Fleet manager (master control)
date: 2026-08-21
status: approved
---

# M6.3: the fleet manager — transport tasks become VDA 5050 orders

## Where this sits

Third of M6's five sub-projects (AMR-DEC-002). M6.2 gave each vehicle a
VDA 5050 client; M6.3 gives the cell its master control: a fleet manager
that owns transport-task assignment over the ten stations and generates
the full-route orders the vehicles drive. Traffic (M6.4) and scale to
four (M6.5) build on it.

**Owner rulings 2026-08-21:** tasks are **A→B two-leg transports**
(order to the pickup station, configurable dwell simulating the fork
cycle, order to the dropoff); on vehicle loss mid-task the task
**returns to the queue head** and the other vehicle may take it — the
lost vehicle gets nothing until it is idle-confirmed again.

## Non-goals

- No traffic logic, no zone/edge reservation, no multi-vehicle
  deconfliction (M6.4). Routes may cross; the onboard guards and the
  safety chain are what prevents contact, exactly as in M6.1's Gate 3.
- No third/fourth vehicle (M6.5).
- No persistence beyond MQTT retained messages: a restarted manager
  re-syncs from the wire (see Restart), it does not journal to disk.
- No load handling, no charging, no pause actions.
- No web UI: the operator's window is a CLI + the manager's retained
  status document.
- No change to the vehicle agent's contract beyond the named carry-in
  fixes; steps 1-5 and step5 frozen; the safety chain untouched.

## Architecture

All fleet code lives in `m5_ver2/step6/fleet/` — the current system's
home; M6.5 scales it there. The fleet layer's standing invariants (the
top-level `fleet/README.md`, claude-supervised era) still bind where
they apply: **no ROS** — the manager is paho-only; the ONLY path to a
vehicle is VDA 5050 over MQTT; the fleet layer carries process commands
only, and losing it must only degrade, never endanger.

**1. `fleet/fleet_core.py` — pure decisions.** Vehicle registry
(serial → {connection, operatingMode, position, executing orderId,
errors}), task queue (FIFO), task state machine
(`QUEUED → ASSIGNED_LEG1 → DWELL → ASSIGNED_LEG2 → DONE`, plus
`QUEUED` again on loss/rejection), and the assignment rule:
**nearest idle** — graph shortest-path distance (the vehicle's own
`route.plan_route` length, imported from `ipc/`; the graph's single
home stays `ipc/route.py` + `ipc/stations.py`) from the vehicle's last
reported position to the task's pickup. Ties break by serial. No ROS,
no MQTT, no clock of its own — everything injected, unit-tested hard.

**2. `fleet/order_builder.py` — the master-control order factory.**
Builds full-route VDA orders from a start pose and a target station via
`route.plan_route` — the lineage of `send_order.build_order`, now owned
fleet-side. `tools/send_order.py` stays as a frozen low-level debug
probe with a superseded-by-fleet header; docs stop teaching it.

**3. `fleet/fleet_manager.py` — the service.** paho-only process (no
VEHICLE env, no rclpy), spawned by `step6.sh` (`spawn fleet - ...`).
Subscribes `uagv/v2/amragent/+/{connection,state,factsheet}` and the
admin topic; publishes orders and instantActions to vehicles, and its
own retained status document.

- **Admin wire:** `fleet/task/submit` (CLI → manager): JSON
  `{"taskId", "from", "to"}` — station ids validated against
  `stations.py`. `fleet/status` (manager → world, **retained**, QoS 1):
  one JSON document — per-vehicle rows (connection, mode, position,
  current order, last state age) and the task table (id, state, legs,
  assignee, history). Republished on every change and every 2 s.
- **Assignment loop:** when a vehicle is idle-confirmed (ONLINE +
  AUTOMATIC + no executing order + last state fresh) and the queue is
  non-empty → nearest-idle assignment → leg-1 order. On the vehicle's
  ARRIVED state for leg 1 → `DWELL_S` (default 3.0) → leg-2 order. On
  ARRIVED leg 2 → DONE with completion timestamps.
- **Rejection handling:** an `orderError` referencing the manager's
  orderId → the task returns to the queue head, the vehicle is marked
  not-eligible until its next clean idle state (covers teleop mode,
  executing collisions, validation surprises).
- **Loss handling (owner ruling):** `CONNECTIONBROKEN` on a vehicle
  with an active task → task to queue head, vehicle marked LOST; a
  LOST vehicle that returns ONLINE must show a clean idle AUTOMATIC
  state before it is eligible again. The manager sends `cancelOrder`
  to a returning vehicle whose kept order belongs to a task that was
  reassigned (the M6.2 agent keeps AND auto-resumes its order on
  reconnect — so there is an honest race: the returning vehicle may
  drive for the seconds it takes the cancel to land; Gate 4 measures
  that window instead of pretending it away).
- **Restart (re-sync, no journal):** on start the manager reads the
  retained connection topics and the first state from each vehicle. A
  vehicle executing an `ft-`-prefixed order is left to FINISH its
  current leg — the restarted manager adopts it by waiting (it assigns
  that vehicle nothing until idle-confirmed) and never cancels it;
  non-`ft-` orders are not the manager's to touch at all. Tasks are
  NOT recovered (the queue is in-memory; the operator resubmits —
  recorded plainly in status and docs). No double-assignment:
  assignment requires idle-confirmed. cancelOrder exists in exactly
  one flow: the loss-return case above.
- **Operator truth (Gate-6 DISPLAY carry-in):** the retained status
  document is the operator's honest screen — vehicle rows derive from
  the VDA state stream (driving from odom-fed `driving`, errors,
  safetyState) with the state's age shown, so a dead feed reads as
  stale, never as EN-ROUTE. The commissioning HMI's own stale-EN-ROUTE
  cosmetic remains vehicle-side debt, named in CONTEXT.

**4. `fleet/fleet_cli.py` — the operator's hand.**
`python3 fleet/fleet_cli.py submit f?A B` → publishes to
`fleet/task/submit` (taskId `ft-<hex>`), prints the id;
`... status [--watch]` → reads the retained `fleet/status` and renders
the table. paho-only.

## Carry-in fixes (M6.2's named debts, folded here)

1. `vda_agent.py`: bound the reconnect — `reconnect_delay_set(min=1,
   max=8)` plus one log line on each retry window (28.1 s unbounded was
   measured in Gate 4).
2. Suite DDS fence: step6 `tests/conftest.py` sets
   `os.environ["ROS_DOMAIN_ID"] = "89"` explicitly (the live stack runs
   96; PROOF's own runbooks export 96 in the operator's shell).
3. `tools/send_order.py`: superseded-by-fleet header, docs updated.

## Error handling

The manager crashing or the broker dying degrades only: vehicles finish
or hold their current orders per M6.2 semantics; nothing fleet-side can
command anything but orders and cancelOrder. Malformed admin
submissions are refused with a reason in the status document. Unknown
stations refused at the CLI AND at the manager.

## Proof gates (live, machine-run, PROOF.md)

1. **Two transports, two vehicles:** submit two A→B tasks → nearest-idle
   assignment (the measured distances recorded), both vehicles drive
   leg 1, dwell, leg 2, DONE; 0 motor-false; the status document's task
   table telling the story truthfully throughout.
2. **Queueing:** three tasks, two vehicles — the third waits QUEUED and
   is assigned to the first vehicle that frees; FIFO order preserved.
3. **Rejection recovery:** one vehicle dropped to teleop → its
   assignment is rejected on the wire → task requeued to head →
   assigned to the other vehicle; the teleop vehicle re-earns
   eligibility only after a clean AUTOMATIC idle state.
4. **Vehicle loss mid-task:** kill one agent mid-leg → CONNECTIONBROKEN
   → task to queue head → other vehicle completes it; the lost vehicle
   returns, gets cancelOrder for its stale order, re-earns eligibility.
5. **Manager restart mid-operation:** kill and restart the manager while
   a vehicle drives → re-sync from retained topics, no double
   assignment, the driving vehicle finishes its leg and the manager
   (having no task memory) is honest about the empty queue; the
   operator resubmits and life continues.
6. **Operator truth:** during gates 1 and 4, the status document never
   shows a dead or lost vehicle as driving; state age visibly grows on
   the lost vehicle.

## Testing

- Unit: fleet_core (assignment matrix incl. ties/no-idle/all-lost,
  queue FIFO + requeue-to-head, task state machine legality, idle
  confirmation rules); order_builder (orders pass `vda_orders.validate_order`,
  `ft-` prefix, leg-2 starts at the pickup station).
- Integration (WSL, private broker, no Gazebo): the manager against two
  fake vehicle agents (scripted state machines over paho) — assignment,
  dwell sequencing, rejection requeue, loss requeue, restart re-sync.
- The six live gates.
