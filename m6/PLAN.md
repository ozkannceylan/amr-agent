# M6 — VDA 5050 fleet operations, built on m5_ver2 step 5

The gate, from the roadmap (docs/archive/roadmap.md M6 row): an enlarged
warehouse world with five loading stations, five unloading stations and four
forklifts; the fleet manager assigns transport orders over VDA 5050 / MQTT and
traffic conflicts are avoided; the station handshake works end to end; AT-05,
AT-06 and AT-09 pass; and a recorded fleet showcase shows orders, traffic and
the handshake in one run.

The base it is built on is **m5_ver2/step5** — the running system: one
forklift, ten stations, an onboard autopilot that is a requester and never an
authority, every command through `mux → gate → contactor → plant`, and the
S7-1516F F-program (`PLC_2`) holding the enable and the speed ceiling over all
of it. M6 adds layers **above** that chain and changes nothing below it.

The interface contract is **docs/interfaces/vda5050-subset.md** (VDA 5050
2.1.0), written at M1 and unchanged: topics, header, the order/state/
instantActions/connection/factsheet subsets, and the extension policy. Any
field this milestone sends or reads exists in that document first.

## Staging — five steps, the m5_ver2 way

Each step is a working system, verified before the next builds on it. A step
lands with its own README, tests and PROOF evidence measured live on the
owner's machine.

### Step 1 — the VDA 5050 seam at n = 1  *(in progress)*

One forklift, exactly as step 5 left it, gains a **VDA 5050 client**: a new
vehicle-side node that speaks `order` / `state` / `instantActions` /
`connection` / `factsheet` over a local mosquitto broker, and drives the
existing autopilot through the same `/auto/goal` seam the HMI GO button uses.
A minimal **dispatcher stub** plays master control from the command line.

The client is a requester one level further out: it cannot enable the drive,
cannot clear a latch, and everything it asks for still passes the mux, the
`Motor`-gated `cmd_gate` and the STO contactor.

Acceptance (measured, PROOF.md):

- A transport order sent over MQTT drives the truck station to station under
  the live safety chain; `state` reports the walk (lastNodeId, nodeStates,
  driving) and `connection` behaves per spec §6.14 (last will, ONLINE/OFFLINE).
- **AT-09 shape** (SC-12, SF-09): broker killed mid-order → the vehicle
  performs a controlled stop within the watchdog period and **keeps its
  order**; a protective-field trip **during the outage** still stops the truck
  (the PLC chain never knew a broker existed); broker restored → the vehicle
  resumes **without an operator reset**. SF-09 is a degraded-mode behaviour,
  not a safety function; no PL claim.
- Unit tests green (pure cores, no ROS or MQTT needed to run them).

### Step 2 — four trucks in the world

ADR 0016 executed: **one ROS 2 domain per vehicle**, one vehicle image,
identity injected by one per-vehicle config whose root datum is the VDA 5050
serialNumber (`FL1`..`FL4`); Gazebo stays one world, one `GZ_PARTITION`, and
gz topic prefixes become per-instance values set at spawn. The enlarged world
keeps the ten stations (five loading `S6`..`S10`-side, five unloading — final
role table in the step brief) and spawns four forklifts.

**Open owner decision (safety at n = 4).** `PLC_2` carries one tag set — one
vehicle's chain. Default proposal: `PLC_2` remains the safety controller of
FL1, and FL2..FL4 run the byte-identical vehicle software against a **modeled
PLC stand-in** (same wire format, same latching ESTOP1 semantics, Python).
The claim stays honest per ADR 0011 D5: F-logic executes on FL1's chain only;
the stand-ins demonstrate architecture, not safety integrity. Alternatives —
owner replicates tags ×4 in TIA, or four PLCSIM instances — are owner-cost
decisions and stay open until ruled.

### Step 3 — the fleet manager

Order dispatch and traffic, per the `fleet/` layer contract (orders and state
only, no actuator, no ROS internals, MQTT is the only path to a vehicle):

- Transport orders (load station → unload station), vehicle selection by
  availability and distance, order lifecycle over the VDA state machine.
- **Traffic**: zone reservation over the shared aisle graph (the same
  centreline graph `route.py` drives). Single-lane aisles and the three
  connectors are reserved ahead of the vehicle via the released-base /
  horizon mechanism and `startPause`/`stopPause` holds; deadlock avoided by
  ordered acquisition. Traffic is fleet-internal (no VDA zone sets, per the
  subset doc).
- AT-09 re-run at n = 4: the outage degrades, never endangers.

### Step 4 — stations with fixed equipment: the handshake

The station handshake end to end per the M6 criterion: the PLC owns the
stations' fixed equipment (dock door, chargers, conveyor), serves OPC UA
(invariant 4), the fleet manager subscribes, and the fixed-equipment
F-functions land: **SF-05** (door interlock, stopping and inhibiting duties)
and **SF-06** (charger interlock) with **AT-05 / AT-06**.

**Entry condition**: TIA-side work is the owner's; whether M6 closes as one
gate or stages the handshake separately is the owner's ruling under
ADR 0010 D6(d), taken on this plan.

### Step 5 — gate evidence and the fleet showcase

AT-05, AT-06, AT-09 recorded as validation evidence; VALIDATION-M6; the
**recorded fleet showcase** — orders, traffic and the station handshake in one
run — and the README/roadmap rows updated.

## What M6 never does

- No safety function over MQTT or OPC UA. `safetyState` reports after the
  fact; `cancelOrder`/`startPause` are process commands (invariants 1, 2).
- No custom message schema beside VDA 5050; extensions only in the standard's
  documented extension points, documented in the subset doc first
  (invariant 3).
- No fleet write to an actuator, no ROS topic into a vehicle from outside its
  domain (invariants 6, 11; ADR 0016 D3).
- No change to the PLC program, the step5 command path, or the deploy
  discipline. The vehicle image grows by one node; the chain under it is the
  chain step 5 proved.

## Open owner decisions

| # | Decision | Default proposal | Falls due |
|---|---|---|---|
| 1 | Safety chain ownership at n = 4 | `PLC_2` = FL1; modeled stand-in chains for FL2..FL4, claims stated honestly | before step 2 build |
| 2 | One gate or staged (ADR 0010 D6(d)) | stage the handshake: steps 1–3 close as "fleet", step 4 as "handshake" | on this plan |
| 3 | Load/unload role table for the ten stations | charge (S2, S3) and HOME/buffer (S1) excluded; loading S6..S9 + S10, unloading S4, S5 + three of the remaining | before step 3 |
| 4 | Manufacturer / serial format | `amragent`, `FL1`..`FL4` (charset per spec) | step 1 (defaulted, revisable until step 2) |
