# ADR 0016: Per-vehicle compute — one DDS domain per forklift, one vehicle image, and the named crossings

Status:        proposed (2026-08-05, brief m5-22). Awaiting owner ruling.

What this ADR does, stated before anything else:

- It decides **what the software boundary of "the vehicle's computer" is** in
  this simulation-substrate project, so that adding a forklift at M6 means
  adding a machine and not another process in a shared graph.
- **Invariants 1–13 are untouched.** The walk is tabulated below rather than
  asserted. Safety stays onboard and off the network (1), supervision loss
  stays a degraded mode (2), VDA 5050 stays the fleet seam (3), the OPC UA
  direction is unchanged (4), and the control loop still closes onboard
  (ADR 0014 D1).
- It changes **no gate criterion** and edits no accepted ADR. It lands one
  constraint on `agv/` and `sim/` implementation work (D4: per-instance gz
  topic prefixes) and requests, without making, one `bridge/` change (D3b)
  and one monitoring-mechanism ruling (D3c, due at m5-13).
- The phased implementation plan is in
  `docs/reports/m5-22-vehicle-compute-deployment-research.md`; this ADR rules
  the mechanism, not the schedule.

---

Context:

**The owner's ask (2026-08-04, m5-22 brief §1):** the autonomy stack should be
built and run as if each forklift carried its own industrial PC and we were
deploying to it. Every additional forklift is **another machine**, not another
process that happens to share a namespace. The simulation stays the substrate,
but the boundary must be real rather than notional.

**Why now.** M6 puts four forklifts against ten stations. Today the whole
vehicle runs in one ROS 2 graph whose names are fixed at n = 1: every topic
carries the literal prefix `/forklift/`, `model.sdf` states its gz topics
explicitly *"so they survive the model being spawned under another name"*
(`agv/forklift/README.md`) — which means a second spawn would share them — and
there is exactly one `/tf` tree. None of this was wrong at n = 1; all of it
collides at n = 2. This is the last cheap moment: no name minted for M6 yet
depends on the answer.

**External facts.** Verified **2026-08-05**, graded as ADR 0014 grades them:
**[fetched]** (page retrieved, statement taken from it) or **[snippet]**
(statement from a search excerpt of the named page).

| # | Fact | Source | Grade |
|---|---|---|---|
| F1 | DDS maps each domain ID to its own UDP port block; safe IDs are **0–101 inclusive**; roughly **120 ROS 2 processes fit in one domain on one machine** (each takes two ports), dropping to ~54 at domain 101 against the Linux ephemeral range 32768–60999 | ROS 2 Jazzy docs, *About-Domain-ID* (read via the Vulcanexus mirror of the same page; docs.ros.org refused the fetch) | [fetched] |
| F2 | Nav2's namespace-native multirobot overhaul (*"Revamped multirobot bringup and config files to use namespaces"*) is listed in the **Jazzy → Kilted** migration guide — i.e. it ships in Kilted, not in the Jazzy line this machine runs (`nav2_bringup` **1.3.12**, m5-21). How to handle namespaced TF on Jazzy is an open upstream question (nav2 issue #5449, closed as a question without documented guidance) | docs.nav2.org *Migration/Jazzy*; github.com/ros-navigation/navigation2 issue 5449 | [fetched] |
| F3 | Fast DDS **partitions** gate DataWriter/DataReader **matching** inside one domain and are runtime-modifiable; participants in different partitions still share the domain and its discovery. Configuration is vendor XML, not a ROS 2 surface | Fast DDS docs 3.6.2, *Partitions* | [snippet] |
| F4 | `domain_bridge` (ros2/domain_bridge, released for Jazzy) forwards an explicitly named topic set from one domain to another, preserving QoS | github.com/ros2/domain_bridge design doc | [snippet] |
| F5 | VDA 5050 2.0 MQTT topics are `interfaceName/majorVersion/manufacturer/serialNumber/topic`; **serialNumber is the vehicle identity**; QoS 0 for order/state/instantActions, QoS 1 for connection | VDA 5050 V2.0.0 (and this repo's own `docs/interfaces/vda5050-subset.md`, which already pins the scheme) | [snippet] + repo |
| F6 | The machine class that runs a lidar-Nav2 AMR stack is a **fanless DC-input box PC** (typ. 9–36 V to ride battery sag, Intel Core class, no GPU for lidar-only navigation, shock/vibration-rated, no spinning disk) | CNX-Software 2026-02-06 (ASUS IoT PE1000U, AMR-targeted, 9–36 VDC); Premio and Syslogic AMR application pages | [snippet] |
| F7 | Production ROS 2 bringup on such a PC is a **systemd unit** (the robot_upstart pattern): starts at power-on, `Restart=on-failure`, environment and config from files | Clearpath Robotics docs, *Services*; robot_upstart | [snippet] |

**Repo facts this decision stands on:** `ROS_DOMAIN_ID` does not isolate
Gazebo — `GZ_PARTITION` does (LESSONS 2026-07-27, measured); the envelope gate
already implements stale-envelope → controlled stop onboard (m5-11, measured);
the supervision seam is rate-insensitive by contract (`opcua-nodes.md` §12.4
E1), so no crossing chosen here sits in a control loop.

**The measurement** (m5-22 report §3; owner's WSL machine, 2026-08-05, run
alone, headless): one vehicle's full M5 stack — gz bridge, EKF, AMCL + map
server, full Nav2, envelope gate; 18 processes, all nodes active, no goal
executing — costs **≈ 2.8 CPU cores and 1.17 GB RSS**; Gazebo with the world
and one vehicle model costs **≈ 1.1 cores and 0.6 GB**. Four stacks project to
**≈ 11–12 of this machine's 20 logical cores and ≈ 5.5 of 15 GiB** — they fit,
with the two named unknowns (driving load, four-model rendering) re-measured
before M6 builds on them (report §3.3).

---

Decision:

### D1 — The vehicle boundary is **one ROS 2 domain per vehicle**

Each forklift's entire ROS 2 graph — sensors-in, Nav2, EKF, AMCL, the envelope
gate, its `/tf` — lives in **its own DDS domain** (`ROS_DOMAIN_ID`, allocated
from the safe 0–101 range, F1). Nothing outside the vehicle joins that domain
except the named crossings of D3. A process outside the domain cannot see,
publish into, or accidentally subscribe to the vehicle's graph: the boundary
fails **closed**, like a separate machine's, not open like a naming
convention.

Consequences by construction, none needing per-node discipline:

- **The TF trap is eliminated, not managed.** Each vehicle owns its own `/tf`
  and `/tf_static`; frame names stay exactly as they are (`forklift/odom`,
  `forklift/base_link`, the unprefixed sensor frames) on **every** vehicle,
  which is what a real fleet of identical machines looks like. No frame
  prefixing, no `/tf` remapping, no Jazzy namespace gymnastics (F2).
- **Node names, topic names and parameter services repeat freely** across
  vehicles, because repetition across domains is not a collision.
- **The software is one image.** No per-vehicle string is compiled into any
  node; identity is injected (D2).

Capacity check against F1: a vehicle stack is ~20 processes against a ~120
per-domain budget, and four domains plus an operator domain use five of 102
safe IDs. No limit is approached.

### D2 — One **vehicle image**, identity injected by one per-vehicle config

The vehicle's software is identical per instance: **one entry point** (the
vehicle-side launcher) reading **one per-vehicle configuration file** whose
root datum is the VDA 5050 **serialNumber** (F5) — the same identity the fleet
layer will address the vehicle by at M6 — carrying beside it the vehicle's
domain ID, spawn pose, and any per-vehicle calibration. Invariant 10: that
file is the **single owner of the vehicle's identity**; the fleet manager
learns it from the VDA 5050 connection topic, never from a second list. The
serial → domain allocation table is one sim-side file with one owner (the
launcher that spawns the fleet).

### D3 — Exactly four things cross the boundary, each already contractual

| Crossing | Mechanism | Standing |
|---|---|---|
| (a) **Orders and state** — fleet ↔ vehicle | **VDA 5050 over MQTT** (invariant 3): the vehicle's client node opens a TCP connection to the broker. MQTT does not ride DDS, so the domain boundary does not touch it — this is the standard's own machine-boundary crossing, unchanged | ADR 0014 seam (c); M6 |
| (b) **Supervision** — PLC envelope down, applied-mode and heartbeat up | The bridge's **vehicle-facing endpoint runs per vehicle, inside that vehicle's domain** — the simulation analogue of the vehicle's own supervision client. One bridge endpoint per vehicle is what "another machine" means on this seam. The `bridge/` change is **requested, not made** (report §5) | ADR 0014 seam (a) |
| (c) **Monitoring** — map, pose, obstacles to the operator, read-only | The monitoring service reaches into each vehicle domain **subscribe-only**: either one process holding one ROS context per vehicle domain, or a `domain_bridge` (F4) forwarding the named read-only set into an operator domain. **Which, is ruled at m5-13** — `domain_bridge` would be a new dependency and is proposed-and-waiting, not adopted. Either way "no write endpoint, no publisher (in any vehicle domain)" must survive the mechanism | ADR 0011 D4 |
| (d) **Simulated time** | Each vehicle's own gz bridge carries `/clock` from the simulator into that vehicle's domain — the same seam its sensors use (D4) | sim substrate |

Nothing else crosses. In particular no vehicle's DDS reaches the PLC, the HMI,
the fleet manager or another vehicle, and the safe channel remains not a topic
on any transport (`agv/forklift/README.md`).

### D4 — The simulation substrate seam: one world, per-instance wiring looms

Gazebo remains **one process, one physical world, one `GZ_PARTITION`** — the
shared world is the analogue of the shared warehouse floor, and gz transport
is not DDS, so it is not part of any vehicle's ROS boundary (LESSONS
2026-07-27). Each vehicle's **`ros_gz` parameter_bridge is its wiring loom**:
it runs inside the vehicle's domain and is the only thing that touches both
transports, exactly as a sensor cable touches both the device and the PC.

One consequence is a **contract change inside `agv/`**: `model.sdf`'s
deliberately fixed gz topic names (`/forklift/gz/...`) collide the moment a
second instance spawns into the same partition. The gz topic prefix and model
name become **per-instance values set at spawn** from the D2 config, and the
checkers that parse the fixed names (`check_sensor_frames.py`,
`sensor_coverage.py`, `sensor_tf.py`) follow. The ROS-side names inside each
vehicle's domain stay exactly as the README contract states them — the domain
makes them private, so they need no instance prefix.

### D5 — Deployment, stated as it would really be done — and what is deliberately not adopted

On a real forklift the vehicle image of D2 is: a fanless DC-input box PC (F6)
running Ubuntu + ROS 2 Jazzy from pinned system packages (the m5-21
discipline), the vehicle stack installed as a **systemd unit** — start at
power-on, `Restart=on-failure`, identity and calibration in the D2 config file
(F7) — and **chrony** disciplining the clock against the cell's NTP source.
NTP-class sync suffices because the supervision seam is contractually
rate-insensitive (E1) and no cross-machine datum sits in a control loop
(ADR 0014 D1); this project has already paid once for an undisciplined clock
(LESSONS 2026-07-27). In simulation the per-vehicle launcher process **is**
that unit's stand-in, and simulated time replaces chrony via D3(d).

**Containers are compatible and deliberately not adopted now.** A container
per vehicle is a packaging and version-pinning mechanism, not an isolation
mechanism — DDS inside containers still needs domain or network configuration,
so the boundary would still be D1's. On this project's WSL substrate four
containers beside a host Gazebo add failure modes and a new toolchain while
buying nothing the domain does not already buy. If a later gate wants
container packaging (an M8-style portability argument), it layers **on top of**
this decision without reopening it.

### D6 — Loss behaviour across the boundary, restated concretely (invariant 2)

Nothing new is decided here; the existing law is restated against the machine
boundary so no reader derives a different one. **Supervision lost** (bridge
endpoint dead, envelope stale beyond the freshness window): the envelope gate
executes its measured controlled stop onboard — degraded mode, not a safety
event (m5-11, `opcua-nodes.md` §12.4 E5). **MQTT lost** (M6): the broker's
last-will on the QoS-1 connection topic tells the fleet; the vehicle performs
its controlled stop per the watchdog and keeps its order (roadmap M6, AT-09).
**Onboard safety** neither knows nor cares: scanner → F-program → STO is
internal to the vehicle (ADR 0011 D1) and no crossing in D3 carries it.

---

### Invariant walk

| Inv | Check under D1–D6 |
|---|---|
| **1** Safety never traverses the network | Holds. No D3 crossing carries a safety datum; the safe channel has no topic on either transport, unchanged |
| **2** Network loss is degraded mode | Holds and is D6's subject: both loss reactions are controlled stops by process logic, named as such |
| **3** VDA 5050 is the fleet contract | Holds; D3(a) is the standard's own topic scheme, serialNumber as the standard defines it (F5) |
| **4** PLC serves, fleet subscribes | Untouched; no vehicle becomes an OPC UA anything (the vehicle layer still never touches OPC UA) |
| **5/6** Fleet owns traffic, commands no actuator | Untouched; per-vehicle domains change who can *see* the vehicle, not who commands it |
| **9** Hard real time out of Python | Holds; nothing timing-critical is added to any crossing, and the supervision seam stays rate-insensitive |
| **10** One owner per datum | Strengthened by D2: identity has one file; the serial→domain table has one owner. The known `ceiling_max_mps` duplicate stays tracked in TODO, untouched here |
| **11** Layers talk only as drawn | The crossings ride existing edges (MQ ↔ CL; monitoring plane; PLC → bridge → vehicle). The `bridge/` edge is **already an open topology gap** (docs/TODO.md, m5-02 open question 1); D3(b) lands on that same missing edge and adds no second gap. The infra brief that draws the bridge edge should draw it once, per-vehicle-shaped |
| **12** Gazebo | One shared world, unchanged |

Invariants 7, 8, 13 are untouched (F-independence, Tailscale, secrets — the
D2 config carries no secret).

---

Consequences:

What becomes harder:

- **Every hand-run tool must pick a domain.** `ros2 topic echo` against a
  vehicle needs that vehicle's `ROS_DOMAIN_ID`; a session that forgets sees an
  empty graph and may misread it as a dead stack. The per-vehicle config file
  is the place scripts read the ID from, never a shell memory.
- **`model.sdf`'s fixed-name contract changes** (D4), and three checkers plus
  the README contract table change with it — a sweep by subject, per LESSONS
  2026-07-29.
- **The monitoring service gains a multi-domain shape** and m5-13 inherits a
  decision (D3c) it would not otherwise have had.
- **The bridge gains a per-vehicle endpoint story** at M6 (D3b), requested in
  the m5-22 report.
- **Cross-vehicle debugging is deliberately inconvenient**, exactly as it is
  with four physical machines; the monitoring plane is the intended window.

What becomes easier:

- **Four forklifts are four starts of one image** with four config files —
  the M6 statement costs no restatement of anything.
- **The whole class of multi-robot naming defects cannot occur**: no shared
  `/tf`, no node-name collisions, no namespace remap tables, no reliance on a
  Nav2 multirobot overhaul that Jazzy does not ship (F2).
- **The demo story matches deployment reality**: the same image + config +
  unit pattern a real integrator uses (F6, F7), sayable in one line.
- **Vehicle evidence stays honest**: a measurement taken inside one vehicle's
  domain provably contains no other vehicle's traffic.

What this ADR does **not** decide: the monitoring mechanism and directory
(m5-13, D3c); the bridge endpoint design (bridge brief); the serial-number
format and manufacturer string (interface agent, with the M6 VDA 5050
revision already carried in TODO); the domain allocation values; the M6
station/world design; anything about claims (ADR 0011 D5 binding beneath).

---

Alternatives:

- **Namespace per vehicle in one shared domain** — rejected as the boundary.
  It is the owner's named counter-example ("another process sharing a
  namespace"): one discovery space, one graph, and isolation that fails open —
  any node that forgets a namespace or uses an absolute name leaks silently,
  `/tf` is shared unless every producer and consumer is remapped, and Nav2 on
  the installed Jazzy line predates the namespace-native overhaul (F2), so the
  gymnastics would be against the old machinery with upstream TF guidance an
  open question. Namespaces remain fine *inside* a vehicle's own domain.
- **DDS partitions per vehicle** — rejected. Partitions gate matching, not
  presence: all vehicles would still share one domain's discovery and
  participants (F3), the configuration lives in vendor XML outside the ROS 2
  surface, `ros2` tooling does not present partition boundaries, and a QoS
  mismatch or empty-partition default leaks. It is a subscription filter
  wearing an isolation costume.
- **Container per vehicle as the isolation mechanism** — rejected as
  isolation, kept as packaging (D5). The DDS boundary inside containers must
  still be drawn with domains or per-container networks, so the container
  answers a different question (deployment), and on WSL it adds cost now for
  nothing the domain does not provide.
- **Status quo (one domain, fixed `/forklift/` names) carried into M6** —
  rejected on arithmetic: it collides at n = 2 (one `/tf`, shared gz topics,
  duplicate node names), and every M6 name minted on it would need retiring —
  the expensive moment instead of the cheap one.
- **`ROS_DOMAIN_ID` as the *simulation* isolation** — already known wrong on
  this machine's own evidence: gz transport ignores it, `GZ_PARTITION` is the
  simulator's boundary (LESSONS 2026-07-27), which is why D4 keeps the two
  seams distinct.
