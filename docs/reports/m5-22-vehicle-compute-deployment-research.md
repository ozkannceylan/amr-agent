# m5-22 — per-vehicle compute and deployment: research, decision, plan

    brief:               docs/briefs/m5-22-vehicle-compute-deployment-research.md
    status:              done

    files_changed:
      - docs/adr/0016-per-vehicle-compute-and-deployment.md   (new, status `proposed`)
      - docs/reports/m5-22-vehicle-compute-deployment-research.md   (this file)

    invariants_touched:  none — the walk is tabulated in ADR 0016. The design
                         presses on invariants 1, 2 and ADR 0014 exactly where
                         the brief predicted, and none needed to move: every
                         crossing is an existing contractual seam.

## 1. The decision, in one paragraph

**One DDS domain per vehicle; one vehicle image with identity injected from
one per-vehicle config file rooted in the VDA 5050 serialNumber; exactly four
crossings of the boundary (VDA 5050/MQTT, the per-vehicle bridge supervision
endpoint, the read-only monitoring plane, and /clock through the vehicle's own
gz bridge); one shared Gazebo world on one GZ_PARTITION with per-instance gz
topic prefixes as each vehicle's wiring loom; systemd-unit deployment as the
real-PC story, containers compatible but deliberately not adopted.** Full
reasoning, graded sources (verified 2026-08-05) and rejected alternatives:
`docs/adr/0016-per-vehicle-compute-and-deployment.md`.

## 2. Research findings not restated in the ADR

- **The one collision the current tree hides**: `model.sdf` fixes its gz topic
  names deliberately (README: "so they survive the model being spawned under
  another name") — correct at n = 1, a shared-topic collision at n = 2. Found
  by reading the contract, and it is Phase 2's whole subject.
- **Nav2 Jazzy**: the namespace-native multirobot overhaul is a Kilted change
  (docs.nav2.org migration page, [fetched] 2026-08-05); one search result
  suggested a Jazzy backport but is [snippet]-grade and unconfirmed. **The
  plan does not rest on it either way** — the chosen mechanism uses no
  namespaces.
- **The fleet still sees everything it needs**: MQTT is TCP, not DDS, so
  domain isolation cannot hide a vehicle from the broker; the monitoring
  plane needs an explicit reach-in (ADR 0016 D3c, mechanism ruled at m5-13).
  Isolation-as-a-wall, the brief's stated failure mode, does not arise.

## 3. The resource question — measured, 2026-08-05, alone

Run on the owner's WSL machine (i9-13900H, 20 logical CPUs and 15 GiB visible
to WSL, of 31.6 GB Windows RAM) on **2026-08-05, ~06:20–06:28 UTC, with no
other agent, simulation or bridge running** (orphan check printed `clean`
before each run; LESSONS 2026-07-30 contention rule observed). Launch chain =
the one m5-21 verified: `warehouse_bringup` → `localization.launch.py` →
`navigation.launch.py`, headless, `GZ_PARTITION=m5_22_probe`,
`ROS_DOMAIN_ID=42`. Nav2 reached its "Nav2 active" line; teardown verified
`CLEAN` by pgrep both runs. CPU sampled as /proc utime+stime deltas over 15 s
across the explicit PID set; memory from /proc VmRSS and `free`.

| Group | Processes | CPU (cores) | RSS |
|---|---|---|---|
| Gazebo server, warehouse world, 1 vehicle model (910 rays) | 2 | **1.12** | 597 MB |
| One vehicle's full stack: gz bridges, sensor TF, wheel odom, IMU gate, EKF, map_server + AMCL, full Nav2, converter, forklift_io, envelope gate (all active, **no goal executing**) | 18 | **2.70 / 2.86** (two samples) | 1 165 MB |
| Whole machine at full single-vehicle stack | — | — | used 2.5 GiB, avail 13.3 GiB |

**Four-vehicle projection**: 4 × ~2.8 ≈ 11.2 cores of vehicle stacks + Gazebo
≥ 1.1 → **≈ 12–14 of 20 logical cores; RAM ≈ 5.5 of 15 GiB. Four fit on this
machine**, with headroom, headless.

**What is NOT measured, stated as the risk rather than hidden in the
projection**: (a) the stack was idle-active — a vehicle *driving* adds
controller/costmap work, magnitude unmeasured; (b) Gazebo with four models is
3 640 rays, not 910 — the render-budget evidence (TODO: 910 rays cost nothing
measurable headless, RTF 1.0004) suggests sublinear cost but four models are
unmeasured; (c) the GUI costs ~8 RTF points (TODO) — a four-vehicle *recorded*
showcase may need headless capture or a measured GUI budget. Phase 4 exists to
convert this projection into a measurement **before** M6 design work builds on
it. If it fails there, the named give is: headless recording, then controller
frequency reduction, then staggered goal execution — in that order, each a
demo-quality cost, none an architecture change.

The two probe scripts were session instruments in the agent scratchpad, not
repository files (the brief forbids code); the raw outputs are quoted above
and the recipe is fully stated, so Phase 4 can reproduce it.

## 4. The phased implementation plan

Sequencing rule inherited from PLAN: each phase is verified before the next
builds on it. Every phase leaves `gate:=false cmd_topic:=/cmd_vel_smoothed`
(the m5-10 chain) and the m5-11 envelope chain runnable.

### Phase 1 — one vehicle behind a real wall (agv + sim)
- **Do**: split the launch tree into a **sim-side** entry point (Gazebo +
  world only, no ROS vehicle nodes) and a **vehicle image** entry point — one
  command that reads one per-vehicle config file (serialNumber, domain ID,
  spawn pose) and starts everything the vehicle owns (its gz bridges incl.
  `/clock`, sensor TF, odometry, EKF, localization, Nav2, envelope gate)
  inside that domain. Keep a compatibility path so today's single-vehicle
  recipes in the evidence files still run.
- **Done-condition (observable)**: with the sim side up and one vehicle image
  started as serial `F001` in its own domain: `ros2 topic list` in any *other*
  domain shows **no** `/forklift` topic; in the vehicle's domain the full
  README contract appears; a Nav2 goal is ACCEPTED and the m5-11 §7
  pass-through observation re-runs with residual 0.000e+00. One run, recorded
  in the evidence.
- **Touches**: `agv/forklift/launch/`, `agv/forklift/config.yaml` (plus one
  new per-vehicle config beside it), `agv/forklift/README.md`,
  `sim/launch/`, evidence files of both layers.
- **Does NOT**: touch `model.sdf`, spawn a second vehicle, add containers,
  touch `bridge/`, `fleet/`, `hmi/`, or any interface document.

### Phase 2 — instance-parameterised model, two vehicles (agv + sim)
- **Do**: make the gz topic prefix and model name per-instance values set at
  spawn from the Phase-1 config (ADR 0016 D4); update the checkers that parse
  the fixed names (`check_sensor_frames.py`, `sensor_coverage.py`,
  `sensor_tf.py`) and the README contract table. Spawn **two** vehicles into
  one world, each image in its own domain.
- **Done-condition**: both vehicles reach Nav2 active and complete
  simultaneous goals; in each vehicle's domain `ros2 topic list` shows only
  its own graph and `ros2 topic info /tf --verbose` reports publisher count 1.
- **Touches**: `agv/forklift/model.sdf`, `agv/forklift/scripts/` (checkers
  only), `agv/forklift/launch/`, `sim/launch/`, both layers' evidence.
- **Does NOT**: monitoring, fleet, bridge, four vehicles, any Nav2 tuning
  change (the sweep is names, not behaviour — LESSONS 2026-07-29: sweep by
  subject).

### Phase 3 — the crossings (agv or viz + bridge; carries two owner decisions)
- **Do**: (a) the monitoring service reaches into each vehicle domain
  subscribe-only and serves the operator view for n vehicles — this **is**
  m5-13, which inherits ADR 0016 D3c; (b) the bridge gains its per-vehicle
  vehicle-facing endpoint carrying the §12.10 envelope group and the two
  report nodes per vehicle — closing ADR 0014 D5.3's readback end to end,
  which m5-11 already requested.
- **Done-condition**: (a) the operator page shows two vehicles' poses while
  `ros2 node info` on the monitoring node in each vehicle domain shows
  subscriptions only, zero publishers; (b) an envelope published per vehicle
  reaches only its own vehicle, shown by stopping one endpoint and observing
  exactly one vehicle execute its stale-envelope stop.
- **Owner decisions, flagged**: monitoring mechanism (multi-context process
  vs `domain_bridge` — the latter is a **new dependency**, proposed and
  waiting per CLAUDE.md §10) and the monitoring directory (`agv/` vs `viz/`,
  the standing ADR 0011 D4 / ADR 0005-test question).
- **Does NOT**: any fleet-manager work, any OPC UA change, any new node in
  `opcua-nodes.md` (§12.13's deliberately-absent rows stand).

### Phase 4 — four vehicles, measured (sim + agv; the M6 entry evidence)
- **Do**: four vehicle images against the shared world, headless; re-run the
  §3 measurement with all four driving simultaneous goals; record CPU, RSS
  and RTF beside the §3 single-vehicle figures.
- **Done-condition**: four stacks Nav2-active with goals completing, and one
  evidence file carrying the measured four-vehicle cost and RTF — the number
  the M6 deep-research brief (roadmap entry condition) reads instead of this
  report's projection.
- **Does NOT**: stations, orders, VDA 5050 traffic, traffic management — all
  M6 proper, behind its owner-ruled entry brief.

## 5. Requested outside my write scope (not made)

1. **bridge/**: the per-vehicle vehicle-facing endpoint design (Phase 3b) —
   one endpoint per vehicle domain, config-driven; the group it must carry is
   already listed in `opcua-nodes.md` §12.10 and TODO's m5-11 residue.
2. **docs/TODO.md** (orchestrator): add the ADR 0016 ruling to the owner
   queue; fold Phase 3's two owner decisions into the existing m5-13 item;
   note that the open `bridge/` topology-gap item should draw the bridge edge
   per-vehicle-shaped when the infra brief lands (ADR 0016 invariant-11 row).
3. **docs/PLAN.md**: deliberately untouched — ADR 0016 is `proposed`, and
   PLAN records the plan in force; the phase list above enters PLAN when the
   owner accepts the ADR (CLAUDE.md §11: never update in advance of the work).
4. **docs/LESSONS.md** (orchestrator, if adopted): one candidate entry —
   *a name fixed "so it survives being spawned under another name" is a
   single-instance assumption wearing a robustness costume; a contract
   written at n = 1 is re-read at n = 2 before any gate multiplies it.*

## 6. open_questions

1. Whether the owner wants container packaging demonstrated at all (ADR 0016
   D5 keeps it compatible, not adopted). Cheap to add later; costly now.
2. Serial-number format and manufacturer string for the D2 config — interface
   agent's, naturally folded into the M6 vda5050-subset revision TODO already
   carries (RB-KAIROS → forklift).
3. Domain-ID allocation values (e.g. operator 10, vehicles 51–54) — trivial,
   but one file must own the table (ADR 0016 D2); the Phase 1 brief should
   name the file.
4. The [snippet]-graded facts in ADR 0016 (F3–F7) follow the ADR 0014 rule:
   re-verify before any of them is made load-bearing beyond that ADR.

## next_suggested

Owner rules on ADR 0016; if accepted, brief Phase 1 (agv + sim split) as the
next vehicle-side brief — it is independent of the open PLC half of M5.
