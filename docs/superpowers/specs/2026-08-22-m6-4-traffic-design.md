---
title: M6.4 — Traffic avoidance (edge/node reservation, horizon holds)
date: 2026-08-22
status: approved
---

# M6.4: traffic — the fleet stops trucks meeting each other

## Where this sits

Fourth of M6's five sub-projects (AMR-DEC-002). M6.3 gave assignment;
its Gate 4 measured traffic's first customer for us — a stopped truck is
an obstacle, and `f2` held 2.65 m behind `f1` with no way out but an
operator. M6.4 makes the fleet responsible for keeping two vehicles off
the same piece of floor. M6.5 then scales it to four.

**Owner rulings 2026-08-22:**
- **Edge + node reservation.** A vehicle locks the individual graph
  edges and nodes of its route and releases them as it passes.
- **Horizon holds.** A part of the route the fleet cannot reserve is
  sent `released: false`; the vehicle drives to the end of its base and
  stops there, on its own, with no pause action. When the way clears the
  fleet extends the base with `orderUpdateId + 1`.

Both rulings put the mechanism where VDA 5050 already put it: the base/
horizon split IS the standard's traffic primitive, and the vehicle side
already stops at the end of a base by construction.

## Non-goals

- No third/fourth vehicle (M6.5 — but nothing here may assume two).
- No `startPause`/`stopPause` (the rejected alternative; the factsheet
  keeps declaring only what is implemented).
- No re-planning around a blocked route: a blocked vehicle WAITS. Route
  choice stays `route.plan_route`'s shortest path.
- No physical anti-collision claim. Reservation is process-level
  deconfliction; the scanners, the F-model and the guards remain the
  only thing that stops a collision, exactly as before (restate in the
  module docstrings — this is the invariant that matters most here).
- No change to steps 1-5, the safety chain, the writer, the HMI.

## The M6.2 constraint this lifts

`vda_orders.accept_order` rejects `orderUpdateId != 0` ("order updates
land with M6.3"). Horizon holds are useless without updates, so M6.4
implements **base extension** per VDA 5050 §6.6: an update with the same
`orderId` and `orderUpdateId + 1` whose released prefix matches what the
vehicle has already been told, extending the base. Rules:

- Accept iff `orderId` matches the executing order AND
  `orderUpdateId == current + 1` AND the new order's node sequence is a
  superset-by-prefix of the current one (the already-driven part must
  not change — a differing prefix is a REJECT with `orderUpdateError`).
- A stitched update never restarts the route: the agent hands nav the
  remaining released nodes from the current pose, exactly as `_resume`
  does today.
- Everything else about updates (new orderId while executing, node
  actions) stays rejected.

## Architecture

**1. `m6/fleet/traffic.py` — pure reservation.** No MQTT, no ROS.

```
class Reservations:            # the floor's ledger
    hold(vehicle, edges, nodes) -> granted_prefix   # longest grantable
    release_through(vehicle, node_id)               # passed → freed
    release_all(vehicle)
    owner_of(element) -> vehicle | None
```

- Elements are the graph's own identities: nodes are `(x, y)` tuples as
  `route.py` yields them, edges are the ordered pair `(a, b)`
  normalized so `(a,b)` and `(b,a)` are THE SAME element (a corridor
  segment is one piece of floor whichever way you drive it — this is
  the head-on case, and normalizing is how it gets caught).
- `hold` is **prefix-granting**: it walks the requested route from the
  start and grants until it hits an element someone else owns; it never
  grants a hole. The returned prefix is what the fleet releases as base.
- **Deadlock resolution: cycle detection, oldest task wins.** Two rules
  make it tractable. (i) A vehicle only ever holds a *contiguous prefix*
  of its remaining route, starting at the node it stands on — holds are
  never scattered. (ii) A blocked vehicle records what it is waiting for
  (`waiting_on[vehicle] = element`), which makes a wait-for graph:
  vehicle → owner of the element it wants. `find_cycle()` walks it; a
  cycle is a deadlock. The resolution is **wait-die by task age**: the
  youngest task in the cycle releases every hold except the node its
  truck occupies and is marked `yielded`, which frees the element the
  oldest was waiting for and breaks the cycle by construction. A
  yielded vehicle keeps its task and its route; it just holds nothing
  ahead and retries `hold` on every subsequent pass, so it resumes as
  soon as the corridor drains. Yielding is a state, never a re-route
  and never a task loss.
- Station spurs and station nodes are reservable too — two vehicles
  cannot occupy one station.

**2. `m6/fleet/fleet_manager.py` — the traffic loop.**
- On assignment: build the full route, ask `hold` for it, send an order
  whose released nodes are the granted prefix and whose remaining nodes
  are horizon (`released: false`). Record the pending extension.
- On each state: `release_through(vehicle, lastNodeId)` — a passed node
  frees it and the edge behind it. Then, for every vehicle with horizon
  left, retry `hold`; if the prefix grew, publish
  `orderUpdateId + 1` with the longer base.
- The status document gains a `traffic` block: who holds what, who is
  waiting on whom, yields, and per-task `base/horizon` counts. The
  operator can see a jam and why.
- A LOST vehicle's holds are released (its task requeues; the floor must
  not stay locked by a truck that is gone) — but the node it physically
  occupies stays held under a `parked:<serial>` owner until the vehicle
  reports a fresh idle state, so nobody is routed through a hulk.

**3. `m6/ipc/vda_orders.py` + `m6/ipc/vda_agent.py` — accept updates.**
`accept_order` grows the stitching branch above; the agent, on an
accepted update, re-issues the remaining released nodes to nav from the
current pose (the `_resume` path, reused) and keeps `Progress` across
the update (the already-reached count survives — the prefix is
unchanged by rule).

## Error handling

- A hold that grants nothing (the very first element is taken): the
  vehicle is not assigned at all if it is idle; if it is mid-route it
  stops at its current node with an empty extension — the honest wait.
- Reservation state is in-memory: a manager restart drops the ledger.
  On restart the manager rebuilds holds from the vehicles' reported
  `lastNodeId` + remaining `nodeStates` before assigning anything new,
  and refuses to assign until every ONLINE vehicle has reported one
  state (the existing idle-confirm rule already delays it; this makes
  the reason explicit).
- Everything degrades to M6.3 behaviour if traffic is disabled by
  `--no-traffic` (a flag the gates use to reproduce the old jam
  deliberately — evidence that traffic is what fixed it).

## Proof gates (live, machine-run, PROOF.md)

1. **Head-on, resolved:** two vehicles ordered toward each other down one
   corridor. Without traffic (`--no-traffic`) reproduce the jam (measure
   the standoff distance, as Gate 4 did). With traffic: one holds at a
   node, the other passes, then the held one continues and both arrive.
   Record hold/release timeline, base extensions, 0 motor-false.
2. **Station contention:** both tasks target the same station; the
   second waits for the first to leave, then arrives. No two-in-a-spur.
3. **Base extension is stitching, not restarting:** capture the
   `orderUpdateId` sequence and prove the vehicle never re-drives a
   passed node (`lastNodeId` monotone across the update).
4. **Deadlock resolution:** contrive a mutual wait (each holding what
   the other needs); the older task wins, the younger yields, both
   complete. Record who yielded and why from the status document.
5. **Loss with holds:** kill a vehicle mid-route; its holds free, its
   task requeues and completes on the other vehicle, and nothing is
   routed through the parked hulk (the occupied node stays held).
6. **Traffic never touches safety:** across all gates, no reservation
   event correlates with a Motor drop; the scanners and the F-model
   remain the only stoppers (the same causation discipline as M6.2's
   Gate 6).

## Testing

- Unit (pure): `traffic.py` — prefix granting, undirected-edge identity,
  release-through semantics, deadlock detection and the age rule,
  parked-node retention, the full-route-free case.
- Unit: `vda_orders` stitching matrix (accept correct update; reject
  wrong id, wrong increment, changed prefix, node actions).
- Integration (broker + fakes): manager grants a partial base, extends
  on release, holds a second vehicle, resolves a contrived deadlock.
- The six live gates.
