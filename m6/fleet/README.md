# `fleet/` — the cell's master control

Six files, one process and one command line. `fleet_core.py` decides who
drives what, purely; `order_builder.py` turns a leg into a VDA 5050 order,
purely; `traffic.py` is the floor's ledger, also purely; `floor.py` runs the
traffic loop over that ledger — holds, extensions, deadlocks, the idle
sweep; `fleet_manager.py` is the service that owns a broker, a clock and a
queue; `fleet_cli.py` is the operator's hand and screen.

```bash
python3 fleet/fleet_manager.py                 # m6.sh start spawns this
python3 fleet/fleet_cli.py submit S1 S4        # a transport, not an order
python3 fleet/fleet_cli.py status --watch      # the retained truth
```

## The three standing invariants

Everything in this directory is written under these three, and each file's
header says which of them binds it. They are not style: two of them are why
this layer is allowed to exist at all on a machine with a safety chain on it.

**1. No ROS lives here.** No `rclpy`, no `VEHICLE`, no DDS domain, no node.
The manager is paho-only and the pure modules are not even that. The vehicle
side has a ROS graph and this side must not join it: a fleet process that
could publish a `cmd_vel` would be a second driver of every truck in the
hall, and the one-writer discipline the vehicle stack is built on would be
over. What the fleet knows about a truck, it learned from that truck's own
VDA 5050 `state`.

**2. The only path to a vehicle is VDA 5050 over MQTT.** Orders and
`instantActions`, nothing else — there is no back channel, no ssh, no shared
file, no second protocol for "just this once". So the worst thing this
process can command is a route and a cancel, and every one of them goes
through `vda_orders.validate_order` — the vehicle's own door — before it is
published. A decision this layer cannot express as an order is a decision it
does not get to make.

**3. Losing the fleet must degrade, never endanger.** Kill the manager and
every truck keeps its current order, the on-board guards keep guarding, the
F-CPU keeps the safety chain and the e-stop is still the brake. Nothing here
is in a safety function, by construction — supervision loss is not a safety
event, it is degraded mode, and the vehicle handles it as a controlled stop
through the normal chain. The honest signal of the fleet's own death is its
retained `fleet/status` document going stale, which is why the manager sets
no will and why the CLI prints the document's age in its header rather than
hiding it.

## What follows from them, and surprises people

- **No journal.** The queue is in memory and the manager re-syncs from the
  wire alone. A restarted manager has NO tasks, says so in the status
  document, and the operator resubmits. It adopts a truck still driving one
  of its `ft-` orders **by waiting** — a vehicle with something left to drive
  is not idle, so nothing is assigned to it and nothing is cancelled.
- **`cancelOrder` exists in exactly two flows, and both are one sentence:**
  the fleet has taken a task away from a truck that is still driving its
  order. A vehicle that was lost and came back holding it (the M6.2 agent
  resumes a kept order on reconnect, so that race is real and measured), and
  a vehicle requeued out of a swap deadlock. Left uncancelled the second one
  is stranded — never idle, never eligible, its node held for the rest of the
  run — which is what M6.5's Gate 3 measured.
- **A truck that cannot yield is asked to step aside.** Wait-die frees floor
  *ahead* of a vehicle, so a cycle whose contested element is the ground
  *under* one is unbreakable by yielding. The younger member is cancelled,
  requeued and sent a one-node `ft-` order to a free neighbour — same
  builder, same validation, same publish funnel as a leg. `step_aside_target`
  is the whole choice and is pure; `ASIDE_MAX`, `ASIDE_S` and "no free
  neighbour" are the three bounds, and the last of them is M6.5's named
  refusal, unchanged.
- **The operator names stations, never vehicles.** Which truck goes is the
  fleet's decision, made from the trucks' own reported positions over the
  vehicle's own route graph (`ipc/route.py`). There is deliberately no way to
  address a vehicle from `fleet_cli.py`.
- **The graph has one home** and it is the vehicle's: `ipc/route.py` and
  `ipc/stations.py`. This layer imports them and never copies them, so the
  route the fleet sends is the route the vehicle would have planned.

Design: `docs/superpowers/specs/2026-08-21-m6-3-fleet-manager-design.md`.
Evidence: `../PROOF.md`. Operator's manual: `../README_m6.md`, "Fleet
manager".
