# M6 Step 1 — the VDA 5050 seam at n = 1

One forklift, exactly as step 5 left it, gains a **VDA 5050 client**: a
vehicle-side node speaking `order` / `state` / `instantActions` /
`connection` / `factsheet` (subset 2.1.0, docs/interfaces/vda5050-subset.md)
over a local mosquitto broker, driving the existing autopilot through the
same `/auto/goal` seam the HMI GO button uses. A command-line **dispatcher
stub** plays master control.

**The client is a requester one level further out.** It cannot enable the
drive, cannot clear a latch, and everything it asks for still passes
`cmd_mux`, the `Motor`-gated `cmd_gate` and the STO contactor. Nothing below
the goal seam changed; the chain under this step is the chain step 5 proved.

## Layout

| Where | What |
|---|---|
| `vda/protocol.py` | wire basics: identity, topics, headers, timestamps — the ONE home for VDA topic strings |
| `vda/order_core.py` | order acceptance and the station walk (pure) |
| `vda/actions_core.py` | the eight instant actions → effects (pure) |
| `vda/state_core.py` | state message assembly from step 5 snapshots (pure) |
| `vda/factsheet_core.py` | the vehicle's self-description (pure) |
| `vda/client_core.py` | the glue: events in, effects out; owns the one goal decision (pure) |
| `vda/mqtt_link.py` | paho shell: last will, subscriptions, queueing |
| `vda_node.py` | rclpy shell: step 5 topics ↔ client_core ↔ mqtt_link |
| `fleet/dispatch_core.py` | master control's order builders and bookkeeping (pure) |
| `fleet/fleet_stub.py` | CLI dispatcher: `watch`, `send`, `pause`, `resume`, `cancel` |
| `cell.yaml`, `vehicles/FL1.yaml` | the cell facts and the per-vehicle identity (ADR 0016 D2) |
| `tests/` | 57 pure-Python tests; no ROS, no MQTT, no broker needed |

Pure cores, thin shells: everything decidable is decided in modules with no
`rclpy` and no `paho` import, so `pytest` runs on any machine:

```bash
python3 -m pytest m6/step1/tests/ -q
```

## Run order (owner machine)

Steps 1–8 are exactly step 5's run order (m5_ver2/step5/README_step5.md).
Then:

| # | Where | Do this |
|---|---|---|
| 9 | WSL, once | `sudo apt install mosquitto && pip install paho-mqtt`; make sure mosquitto listens on 1883 (`sudo service mosquitto start`) |
| 10 | WSL | `source /opt/ros/jazzy/setup.bash; export GZ_PARTITION=step5 ROS_DOMAIN_ID=95; python3 m6/step1/vda_node.py` |
| 11 | HMI | click **Auto** — the fleet only assigns to an AUTOMATIC vehicle, and the HMI owns the mode |
| 12 | WSL | `python3 m6/step1/fleet/fleet_stub.py watch` — see `[connection FL1] ONLINE` and state lines |
| 13 | WSL | `python3 m6/step1/fleet/fleet_stub.py send FL1 S7 S3` — the truck drives S7 then S3, `lastNodeId` walking behind it |

The client imports `stations.py` and `status_contract.py` from the
**deployed** step 5 image (`vehicles/FL1.yaml: step5_ipc`), like every other
vehicle node — run `./m5_ver2/step5/step5.sh deploy` first.

## The AT-09 rehearsal (SC-12, SF-09)

1. `send FL1 S7` and let the truck drive.
2. `sudo service mosquitto stop` mid-leg. Within the supervision budget
   (`supervision_s`, 3.0 s = 1.5 × the 2 s keepalive) the client publishes an
   empty goal: **controlled stop**, order kept, torque untouched. The broker
   being dead, its last will (`CONNECTIONBROKEN`, retained) is what a
   reconnecting dispatcher reads.
3. **During the outage, trip a protective field** (walk the truck's back
   scanner zone in Gazebo or use the panel's e-stop). The PLC chain acts
   exactly as in step 5 — it never knew a broker existed. This observation
   is what the scenario exists for.
4. `sudo service mosquitto start`. The client reconnects, publishes ONLINE,
   re-issues the same station goal: the truck **resumes without an operator
   reset** — permitted precisely because this never was a safety stop. (If a
   field trip latched ESTOP1 in step 3, that latch still takes its monitored
   RESET on the panel — the safety chain's rule, not this layer's.)

SF-09 carries no PL claim. Supervision loss is degraded mode, not a safety
event (invariant 2; docs/safety/PL-SCENARIOS.md SC-12).

## What `state` says and why

- `operatingMode`: `auto` → AUTOMATIC, everything else MANUAL. The HMI owns
  the mode; the dispatcher's `assignable()` refuses MANUAL vehicles.
- `safetyState.eStop` = MANUAL whenever `Motor` is False — every latched
  demand on this vehicle clears only through the panel's monitored reset,
  and the dispatcher does not need to know which demand latched, only to
  stop assigning. A silent `/plc/status` reads as MANUAL, the failsafe
  direction every step 5 consumer takes.
- `safetyState.fieldViolation` is True on a silent fields report — a chain
  that has said nothing must not be reported clear.
- `batteryState` is **modeled** (a required field, not a measurement):
  charge is a config constant, `charging` follows start/stopCharging.
- `initPosition` is accepted and does nothing, and says so in its
  actionState: pose is simulator ground truth on this vehicle.

## Evidence

PROOF.md lands with the live transcripts from the owner's machine: the
ordered drive, the AT-09 rehearsal, and the measured stop latency against
`supervision_s`. Nothing is ticked here until then.
