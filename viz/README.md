# viz — the read-only monitoring plane

The operator-side window into the vehicles. One process holds a
**subscribe-only** presence in every vehicle's DDS domain and serves what it
sees over HTTP GET. It is the directory ADR 0011 D4's `MON` box was drawn
for, ruled into existence by `DESIGN.md` §1 against the ADR 0005 test.

`DESIGN.md` is the authority for everything in this directory. This README
states the boundary; the design states the contract; `EVIDENCE_MONITORING.md`
is where the claims are shown rather than asserted.

## This layer must not access

- The PLC, OPC UA in any role, or the MQTT broker — this layer touches no
  process-plane or fleet-plane transport (invariants 4, 11; ADR 0011 D4).
- Any write into any vehicle domain: no publisher, no service server or
  client, no action server or client, no parameter write. Its ROS presence
  is subscriptions only, proven per §8 of DESIGN.md.
- The safety layer, in any form. Nothing here displays-and-commands;
  nothing here is a command path (invariant 1 untouched by construction).
- `hmi/` internals. The HMI page reads this service over HTTP GET; this
  service knows nothing of the HMI backend, its OPC UA client or its
  write set.
- Verdict-making on vehicle data: no localization-quality, obstacle-danger,
  stop, mode or fault verdict is computed here (invariant 10, §6).

## The claim this layer makes about itself, in its only admissible form

> **read-only by construction of the process and proven by test; not
> enforced by the middleware.**

Never the unqualified short form. Nothing in DDS stops a process from
creating a publisher, and this project does not run DDS-Security access
control (DESIGN §2 states the cost and records what would remove the
limitation). What *is* true, and is checked rather than asserted:

| Claim | Where it is proven |
|---|---|
| Every rclpy entity in `viz/` is created by one module, and that module can only create subscriptions | `tools/check_construction.py`, EVIDENCE §3 |
| A running monitor node advertises **publishers 0, services 0, actions 0** in the vehicle's own domain, while subscribing | `ros2 node info` on the live node, EVIDENCE §4 and §6 |
| The framework's own opt-out flags do **not** reach that state on Jazzy — `/parameter_events` survives them | `tools/zero_endpoint_probe.py`, EVIDENCE §4, the failing variant shown beside the passing one |
| The HTTP face answers everything except GET with 405, before any handler runs | `tools/http_probe.py`, EVIDENCE §7 |

## Files

| Path | What it is |
|---|---|
| `DESIGN.md` | The authority. Directory ruling, read-only ruling, the ADR 0016 D3(c) mechanism ruling, the endpoint contract, the five V3-PLAN §2 constraints |
| `README.md` | This file: the boundary statement CLAUDE.md §4 requires of every top-level directory |
| `EVIDENCE_MONITORING.md` | The dated runs. Every acceptance check of DESIGN §8, as its command and its actual output |
| `monitor/subscribe_only.py` | **The one entity factory.** The only module in this layer that constructs rclpy objects, and it constructs subscriptions and zero-endpoint nodes only. It also owns the forbidden-call list that `tools/check_construction.py` reads |
| `monitor/vehicle_link.py` | One vehicle: its context, its zero-endpoint node, its executor thread, its refcounted subscription manager, and the latest-value store with steady-clock ages |
| `monitor/http_face.py` | The GET-only HTTP surface of DESIGN §5, rooted in the VDA 5050 serialNumber at n = 1 as at n = 4 |
| `monitor/service.py` | The process: reads the allocation table through the vehicle layer's one code path, starts one link per served vehicle, serves HTTP |
| `tools/check_construction.py` | DESIGN §8.2 and §8.6, static: the entity-call grep and the read-only phrase sweep. No ROS |
| `tools/zero_endpoint_probe.py` | DESIGN §8.1's mechanism, isolated: two nodes in a scratch domain, one built with the constructor flags alone and one with the full recipe, held alive so `ros2 node info` can be run against both |
| `tools/http_probe.py` | DESIGN §8.3, §8.4 and §8.5 against a running service: method matrix, payload shape, staleness growth, map integrity |

## How it is started

The monitoring service reaches into vehicle domains; it does **not** live in
one. It is started from an ordinary operator shell, with no `ROS_DOMAIN_ID`
of its own — each vehicle's domain comes from `allocation.yaml` through
`agv/forklift/scripts/vehicle_identity.py`, which is the single owner of the
serial to domain mapping (invariant 10, ADR 0016 D2).

```
python3 viz/monitor/service.py                  # every vehicle in the table
python3 viz/monitor/service.py --vehicle F001   # one of them
python3 viz/monitor/service.py --self-check     # no ROS entities, no network
```

It binds `127.0.0.1:8089` by default — its **own** port, distinct from the HMI
backend's 8088, because the two are different services on different planes and
sharing a port would make the monitoring plane look like part of the process
plane. `--bind` and `--port` change it.

## What this layer deliberately does not do

- It does not join the operator domain. Its operator face is HTTP; nothing in
  `allocation.yaml`'s `operator_domain` is used by this process, which stays
  what that file says it is — a home for hand-run tools.
- It does not compute a verdict about a vehicle. Ages are the only numbers it
  originates, and they watch only itself (DESIGN §6).
- It does not read `/clock`. Every age is measured on the service's own steady
  clock, because a timeout whose purpose is to detect the failure of its data
  source must not run on a clock that source supplies
  (`docs/LESSONS.md` 2026-08-06).
- It does not serve a raster on the JSON poll, and it does not crop the map.
