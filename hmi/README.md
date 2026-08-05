# hmi

## This layer must not access

Per ADR 0008 D2 and its consequences. Every item is a hard boundary, not a
preference.

- **ROS 2, in any form.** No `rclpy`, no DDS, no topic, service, action,
  message type or launch file. The HMI has no path to the vehicle software and
  no path to the plant except through the PLC (invariant 11).
- **Gazebo and `gz` transport.** No `gz-sim`, no partition, no world, model,
  link or joint name. What the plant looks like is not this layer's concern
  (invariant 11).
- **`bridge/` internals.** Nothing under `bridge/` is imported here and no
  state is shared with it. The bridge and the HMI are two independent OPC UA
  clients of the same server that call no code of each other's (ADR 0005,
  ADR 0008 D1).
- **Fleet manager internals.** Nothing under `fleet/` is imported, and no
  VDA 5050, MQTT, order, traffic or zone-reservation concept appears here
  (invariants 3, 5, 6). Homing the HMI inside `fleet/` was rejected in
  ADR 0008 precisely because it would have needed an exception carved into that
  layer's boundary statement.
- **Any PLC node outside the HMI-writable group.** The HMI writes the
  HMI-writable nodes and reads status nodes. `DemoCell/Input/*`,
  `DemoCell/Link/BridgeHeartbeat` and everything under the auto-published
  `DataBlocksGlobal` folder belong to other owners and are never written from
  here (invariant 10). The group's names, folder and access rights are an
  interface question that ADR 0008 leaves open; until `docs/interfaces/`
  settles them, the rule is still that nothing outside the group is touched.
- **Forming or writing any actuator output.** What this layer streams are
  *requests*. The PLC standard program forms every actuator setpoint from them
  and owns the outcome (invariants 5, 6; ADR 0008 D2.2).
- **Any interlock, latch, sequencing or setpoint formation.** Teleop routing,
  the fork-height speed cap, the fork soft travel limits and the lidar obstacle
  stop are process interlocks in the standard program (ADR 0008 D3). No verdict
  the PLC also computes is recomputed here (invariant 10). **The line is not "no
  timer"**: this process owns three, and every one of them watches *itself* —
  the 10 Hz write cadence, the 5 Hz contractual floor it holds itself to
  (`opcua-nodes.md` §10.8 H2), and the window over its own operator's page
  (§10.8 H6). What no client may do is time a **process value** — a debounce, a
  fault delay, a dwell, a stale window over a plant signal, "write only if
  stable for X ms" — because the threshold and the delay are process decisions
  and they belong to the PLC (§10.1). The test is what the timer watches.
- **Any safety function or safety path.** Nothing here is a safety device and
  nothing here carries safety integrity. The teleop interlocks implement no SRS
  function — not SF-02, SF-03, SF-04, SF-07, SF-09 (ADR 0008 D3) — and loss of
  this process is a degraded mode, never a safety event (invariants 1, 2).
- **The OPC UA server role.** The PLC is the server, this process is the
  client, and that direction is never inverted. The HMI holds no server and
  exposes no endpoint, in any configuration (invariant 4, ADR 0008 D2.1).
- **Remote transport of any kind.** ADR 0008 rules the *local* case only: same
  machine, same cell network. Tailscale is engineering access and never a data
  path (invariant 8), and the remote or assistant-originated operator path
  stays parked and unruled (ADR 0008 D2.7). Nothing here is precedent for it.
- **Hard real-time responsibilities.** Deterministic timing lives in PLC logic
  or vehicle firmware, never in this process (invariant 9).
- **Secrets.** Endpoint credentials, certificates and keys live outside this
  repository and are referenced by absolute path (invariant 13).

Owns: the operator-side setpoint stream for the forklift commissioning cell —
the OPC UA client session that writes the HMI-writable nodes, the heartbeat
that session carries, and the operator interface that produces both.

---

## What it is

A **local commissioning HMI**: one process that is an **OPC UA client** of the
S7-1500 and nothing else, driven by an operator standing at the same machine.
It streams into the HMI-writable node group:

- drive, steer and fork jog **setpoints**;
- an **enable**;
- a **reset request**, carried as a level and edge-evaluated in the standard
  program rather than here — the M3 rule that the edge and the hold belong to
  the program, never to the client. The button is **press-and-hold**: the level
  is `TRUE` for as long as the operator holds it, which is what
  `plc/forklift/SPEC.md` §11 T5.4 needs, and a press shorter than one write
  cycle still lands exactly one `TRUE` cycle so no operator action is dropped;
- a `UInt16` **heartbeat**;
- **v2a (m5-28)**, the two `opcua-nodes.md` §12.1 additions, which take the
  every-cycle write set from six to **eight**: `Mode/HmiDriveModeRequest`, the
  operator's mode selection as a level, and
  `ProcessStop/HmiProcessStopRequest`, the operator's process stop. Both are
  **standing** controls rather than deadman ones — a page loss returns the five
  §10.4 requests to rest and deliberately leaves these two where the operator
  put them, because releasing an engaged stop or commanding a mode exit on a
  browser hiccup would fabricate an operator act. The stop **boots engaged**,
  matching the server's §12.8 start value, so the first `FALSE` this process
  ever writes is an operator's release on the page.

**The process stop is not an emergency stop, and the screen is built so that
cannot be misread.** ADR 0010 D6(b) rules it a process-stop request plus a
read-only display of F-layer state, and `hmi/V2A-DESIGN.md` §4 implements
exactly that: the control is labelled **PROCESS STOP**, rectangular, amber, and
the words *emergency*, *e-stop*, *not-aus* and *protective* appear nowhere on
or near it. **Red is reserved on that page for the two F-layer demand lamps**,
which are the only display of the only thing in this cell that carries the word
e-stop. And the control renders **UNAVAILABLE** — hatched, greyed, inert —
whenever its effect could not arrive: session down, write cycle failing, or
`HmiLinkOk` false or stale. A control that looks armed over a dead link is the
defect that design exists to prevent (invariant 1: safety never traverses the
network).

For display only, it also reads `Forklift/Input/`, `Forklift/Output/`,
`Forklift/Status/`, `Forklift/Link/HmiLinkOk`, the §12 groups `Forklift/Mode/`
(the authoritative `ForkliftDriveModeActive`, never its own request back —
§12.3 M2), `Forklift/Envelope/`, `Forklift/Vehicle/` and
`Forklift/ProcessStop/`, and — when the server
carries them — the four `Forklift/Safety/` F-CPU mirrors of
`docs/interfaces/opcua-nodes.md` §11: `EStopDemand`, `ZoneStopDemand`,
`SafetyResetRequired`, `SafetyResetFault`. These are read-only copies of
F-runtime state, feed no logic here (§11.3's "zero PLC readers" restated one
layer up) and are shown behind their own banner, visually distinct from the
standard-program process-stop banner and labelled as a mirror. Their absence
is graceful: a server without them is a server with an unbuilt F-layer, not an
error, and the panel greys the group rather than guessing a value (§11.6).

```
   operator                                   S7-1500 / PLCSIM (OPC UA server)
       |                                                   ^
       |  setpoints, enable, reset request, heartbeat      | client session
       v                                                   |
   +-----------------------------------------------------------------+
   |  hmi process                                                    |
   |  UI -> request values -> writes into the HMI-writable group     |
   |  reads status nodes; forms no actuator output, holds no verdict |
   +-----------------------------------------------------------------+
```

Every command reaches the plant as **HMI to PLC to bridge to Gazebo**, and
every state report returns **Gazebo to bridge to PLC** (ADR 0008 D1). No
command reaches the simulation without passing through PLC logic, and this
layer has no second path to it.

**The PLC owns the outcome.** The standard program applies the interlocks of
ADR 0008 D3 and watchdogs the heartbeat; loss of that heartbeat drives every
motion setpoint to zero in a mandatory `ELSE` branch, the gating discipline of
`plc/demo-cell/SPEC.md` §6.4 rather than a conditional write. That is
invariant 2's controlled stop applied at the operator boundary — losing the
link is a degraded mode, never a safety event. **This HMI is not a safety
device.**

**The operator's page is watched too, and the reaction is smaller.** The page's
unconditional `GET /state` doubles as a liveness beacon
(`docs/interfaces/opcua-nodes.md` §10.8 H6): if nothing arrives from the page for
`UI_POLL_STALE_TIME` — five poll periods, held as a named constant beside its
derivation in `hmi_server.py` — the backend returns all five requests to rest,
the enable included, **while the write cycle and the heartbeat keep running**.
Nothing latches and no reset is owed: the process is healthy, and what is gone is
the page. The controls are carried again as soon as the page posts, each Bool
only once that page has been seen to send it low. Stopping the counter instead
would claim the whole process had died and would buy the PLC's heavier, latching
reaction for a browser that had merely been backgrounded.

**The heartbeat obligation is one-sided.** The HMI's job is to make the counter
change every cycle. The verdict is the PLC's, under the `BridgeHeartbeat` rules
of `plc/demo-cell/SPEC.md` §6.1: compared for inequality only, never
subtracted, never assumed monotonic, wrap-safe — and FALSE until the counter
has been seen to change at least once, because "not yet proven stale" is not
"alive" (`docs/LESSONS.md`, 2026-07-28).

**A setpoint stream, not a command handshake.** What is ruled here is a
continuous stream of process setpoints under a watchdog. It is not the discrete
request/`Ready`/`Busy`/`Done`/`Fault` handshake sketched for a remote
originator in `docs/reports/m4-00-hermes-survey.md` §5. The two are different
contracts and neither substitutes for the other (ADR 0008 D2.4).

The layer existed as a boundary statement first. The implementation landed with
the forklift commissioning gate of ADR 0008 D1, whose live number is carried by
`docs/roadmap.md`:

| File | What it is |
|---|---|
| `hmi_server.py` | the whole backend — the OPC UA client session, the 10 Hz write cycle, the 5 Hz read-only poll, and a loopback HTTP server for one operator's browser. `asyncua` and the standard library, nothing else |
| `static/index.html` | the operator page. One file, offline: no framework, no CDN, no web font, no image |
| `config.yaml` | addresses and cadences for the **commissioned CPU**. Owner-run. Names the v2a eight-node write set, so it needs the §12 nodes the owner's TIA session adds |
| `config-v2a-double.yaml` | the v2a configuration, against this layer's own `tools/v2a_scenario_double.py` on 4861 |
| `config-double.yaml`, `config-logic-double.yaml`, `config-safety-mirror-double.yaml` | **M4-era configurations, superseded by v2a.** They name the six-node write set, and `hmi_server.py` refuses to start on them now that the allowlist is eight. They are kept because they are what the recorded M4 and §11 evidence runs used; restoring runnable M4 harnesses needs the `plc/forklift/double/` §14 extension requested in the m5-27 report, not an edit here |
| `tools/` | four M4 evidence harnesses — the write contract, the teleop loop, the §10.8 H6 and held-reset kernels, and the §11 mirrors — plus `safety_mirror_double.py`, a minimal OPC UA double this layer owns for the last one, and the screenshot pair `capture_screens.mjs` + `screens_plant_driver.py`, which photograph the M4 page in a real browser (`EVIDENCE_HMI.md` §H). For v2a: `v2a_scenario_double.py`, the interim scenario double of `V2A-DESIGN.md` §10 — it serves §10, §12 and (optionally) §11 and **replays scripted sequences** from `SPEC.md` §14 rather than reimplementing them — and `capture_v2a_screens.mjs`, which drives Chrome over the DevTools Protocol with **no third-party package at all**, presses the page's own DOM handlers and writes `EVIDENCE_HMI.md` §I's screenshots. Instruments, not part of the HMI; each harness refuses a non-loopback endpoint, and each polls `GET /state` like the page so H6 does not read it as a crashed browser |
| `EVIDENCE_HMI.md` | the recorded runs, with every figure quoted as it was printed |

## Known limitation, recorded rather than discovered later

Per-tag writability **is** enforced by the CPU (`plc/demo-cell/SPEC.md` §4.2),
so a tag this layer must not write is refused by the server. Per-*client*
scoping is **not**: the commissioned CPU runs with access control disabled and
security `None` as a deliberate demonstration setting
(`docs/interfaces/opcua-nodes.md` §9.10). "Only the HMI writes the HMI group"
is therefore policy honoured by the client, exactly as the bridge's allowlist
is, and two writing clients instead of one make that gap materially wider. It
is not closed by ADR 0008 (D2.5).

## Running it

The environment is a plain venv, deliberately **not** `--system-site-packages`:
this layer must not be able to import `rclpy` at all, and a plain venv makes that
a property of the environment rather than a promise in a document.

```bash
python3 -m venv ~/amr-hmi-venv
~/amr-hmi-venv/bin/pip install asyncua==2.0.1     # the pin in bridge/requirements.txt

# against the PLC logic double (a rehearsal stand-in, not a PLC)
~/amr-bridge-venv/bin/python plc/forklift/double/server.py      # port 4850
~/amr-hmi-venv/bin/python hmi/hmi_server.py --config hmi/config-logic-double.yaml

# then open http://127.0.0.1:8090/
```

`hmi/config.yaml` addresses the commissioned PLCSIM Advanced instance and is the
owner's to run. Never point this process at a server the bridge is also driving
from a test double, and never at two servers at once: every recorded number states
which server produced it.

## What this layer does not decide

- The HMI-writable node names, their folder and their access rights — an
  interface question, owned by `docs/interfaces/`.
- The implementation technology, beyond the constraints above. ADR 0008
  rejected a WinCC screen in TIA Portal on the ground that it produces no
  repository artifact a reader can inspect, diff or run.
- Anything about the remote operator path, which stays parked behind its own
  ADR.
