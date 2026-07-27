# m3-06 — M3 verification

brief:               docs/briefs/m3-06-verify.md
status:              done
files_changed:       [docs/reports/m3-06-verify.md (this report)]
invariants_touched:  none
open_questions:
  - "opcua-nodes.md §9.3 'the PLC forms the rising edge and **times the hold**' is stale
     (m3-12 flagged it). The same superseded hold-time mechanism survives in four further
     places the TODO entry does not name: opcua-nodes.md §9.5 (`CellResetRequired` row),
     bridge-design.md §5 signal map row 5, and sim/README.md twice (§ signal table row
     `PanelResetContact`, and the closing design note). SPEC.md §6.7 implements a pure
     rising edge and times nothing. The queued interface sweep should be scoped to all
     five, and sim/README.md is a second agent's file — see LESSONS 2026-07-27 on briefs
     that enumerate occurrences."
  - "PLAN.md and TODO.md are behind the committed state. m3-07, m3-12 and m3-13 all have
     `status: done` reports and landed commits, but TODO still lists m3-07 as 'in progress'
     and m3-08 as 'blocked on m3-07'; PLAN's brief list carries no close date for m3-12 and
     does not mention m3-13, m3-03d or m3-03e at all. TODO's two 'infra (small)' items are
     both closed on disk (`5c6107d`, `d586e84`). This is exactly LESSONS 2026-07-27 entry
     on PLAN and TODO drifting apart; roadmap.md itself is consistent (M3 in progress)."
  - "The PLAN.md brief list still shows an m3-08 that no longer describes unclaimed work:
     m3-13 delivered the WSL loop re-run as EVIDENCE_LATENCY.md Section C, but scoped it to
     the reset node only and explicitly left the four signal-loss cases and the full
     statistics table to m3-08. This verification run has now produced both against the
     seven-node image under WSL; whether that retires m3-08 or m3-08 still owes a committed
     evidence section is the orchestrator's call, not mine."
next_suggested:      Fold the five hold-time phrases into one interface+sim sweep, then reconcile PLAN/TODO before the owner's PLCSIM run.

---

## How this was verified

The brief predates the platform move, so its "container-side loop" was executed as the
stronger check: the loop was re-run **on the owner's machine under WSL2 Ubuntu 24.04**,
from the committed instructions in `bridge/README.md`, against the committed
`bridge/config/bridge.yaml` with **one** field changed (`opcua.endpoint` port 4840 → 4841,
to isolate the run). Both transports were isolated (`ROS_DOMAIN_ID=91`,
`GZ_PARTITION=m306verify`), no stray `gz`/`ros2` process existed before or after, and
`git status` is clean — no run artefact reached the repository.

Three phases in one foreground run, driven to completion:
a 70 s measured run ending in a clean shutdown (case B), a SIGKILL of the bridge (case A),
and a SIGKILL of the test double under a live bridge (case C). Plus two negative tests.

## Verdicts

| # | Check | Verdict | Observed evidence |
|---|---|---|---|
| 1 | Loop runs from committed instructions | **pass** | `namespace urn:amr-agent:cell:plc resolved to index 2` / `all node DataTypes match opcua-nodes.md §9` / `session established, 15 nodes resolved`. 15 is exactly what SPEC.md §10 step 9 requires ("N must be 15") |
| 2 | Cell → PLC, real values at the server | **pass** | Double's own 5 Hz observation log: `pos=0.472000 vel=0.000000000 rng=1.4401`, and `rng=0.5400` when the product stood in the beam — the 1.440 / 0.540 m levels of `sim/worlds/CELL_EVIDENCE.md`, carried as a raw range with no threshold applied |
| 3 | PLC → cell, the actuator moves | **pass** | Commands 0.0 → 0.15 → −0.15 → 0.0 driven only on the double. Pose log: `box_x` tracks `belt_pos` with a constant −1.000 m offset for the whole run (`-0.4673/0.5334`, `0.1327/1.1334`, `1.3327/2.3334`) — the product is carried, not teleported. Belt reached the +2.50 m mechanical stop and reversed |
| 4 | **Reset contact end to end** | **pass** | `/cell/panel/reset` → `DemoCell/Input/PanelResetPressed` at the double: `mono 10789.351 reset True` → `mono 10791.384 reset False`, a 2.03 s level matching the 25 s/27 s stimulus. R3 decimation 66 received / **3 written** — written on change only, never latched or stretched |
| 5 | Startup rule now waits for seven | **pass** | `heartbeat withheld: no real sample yet for … PanelResetPressed …` then `startup rule satisfied: all 7 DemoCell/Input nodes carry a real cell sample; heartbeat begins advancing at 1`. Reproduced identically in all three bridge starts |
| 6 | Update rate consistent with committed claims | **pass** | **19.98 Hz achieved** (1399 cycles in 70.0 s), median cycle period 49.974 ms, **0 cycle overruns**, 0 write/read errors, 0 reconnects. Committed Section A: 19.99 Hz, 0 overruns |
| 7 | Latency consistent with committed claims | **pass (better)** | L2 median 0.33–0.49 ms (§A.4: 0.85–1.0 ms); L3 belt median 1.54/1.71 ms (§A.4: 2.46/2.04 ms); L3 photo-eye median 16.53 ms, p95 31.7 ms (§A.4: 18.05 / 33.4 ms); L5 publish 0.073 ms median. Every figure is at or below the committed container number, so the committed claims are not overstated on this platform |
| 8 | L1cs negative-value disclosure honoured | **pass** | `L1cs ConveyorBeltSpeed min −6.434 ms` appears in the summary, unclipped, exactly as §A.5 says it must |
| 9 | Signal loss **A** — bridge SIGKILL | **pass** | Heartbeat froze at an arbitrary **370**; over 15 s of `sessions=0` the input image had **exactly one distinct value tuple** (`pos=1.424400 vel=0.050000001 rng=0.5400 F F T T`) — bit-identical, and `ConveyorBeltSpeed` frozen at a plausible 0.05 m/s forever, as A.2 states. Session dropped within one 0.2 s observation interval, confirming the A.4 deviation (immediate, not on timeout) even more sharply than the container's ~2 s. Belt kept running (pos 1.359 → 2.224 with no bridge alive) — the A.3 residual |
| 10 | Signal loss **B** — clean shutdown | **pass** | `session closed (clean shutdown); no farewell value written, nothing zeroed`. Heartbeat froze at 1387, input image unchanged across the transition, `cmd` untouched. **Indistinguishable from A in the input image**, as §7.3 requires |
| 11 | Signal loss **C** — server killed, bridge alive | **pass** | `session broken: read ConveyorSpeedCommand: client is disconnected — degraded mode, no signal invented` in the same cycle; retry 1 → 2 → 4 → 5 → 5 → 5 s, capped, forever. `ros2 topic hz /cell/conveyor/cmd_speed` for 8 s during the outage produced a **0-byte** file — nothing published, not the last value, not zero (N3) |
| 12 | Heartbeat not reset by reconnect | **pass** | Counter is per process: a fresh bridge starts at 1 (`heartbeat begins advancing at 1` after each restart), and within a process the reconnect path leaves `self._heartbeat` untouched (`opcua_side.py` §8.1 comment and code) |
| 13 | **Invariant 4** — client/server direction | **pass** | `amr_bridge/` imports `asyncua.Client` only; no `Server`, `bind(`, `listen` or `serve_forever` anywhere in the production package. The double is the server (its `active_sessions` counter is what rose 0→1). Verified by both code scan and behaviour |
| 14 | **Invariants 5, 6** — no control logic in the bridge | **pass** | The only numeric operation is the `float64 ↔ Float` narrowing/widening in `_input_path`/`_output_path`. No threshold, latch, timer, debounce, edge, hysteresis, clamp, ramp or interlock exists outside comments asserting their absence. Slots are depth-1 with no history (`slots.py`), so no discarded sample can contribute to anything |
| 15 | Invariant 6 enforced, not merely asserted | **pass** | Live `tools/check_write_allowlist.py`: client-side, `PlcClient._write` raised `WriteNotPermitted` for `ConveyorSpeedCommand`, `CellCycleRunning`, `ProductPresentAtSensor`, `ConveyorDriveFault`, `BridgeLinkOk`; server-side, all five returned `BadUserAccessDenied`. `RESULT: PASS`. Allowlist = the 7 `Input/` nodes + `BridgeHeartbeat` = 8 |
| 16 | Logic cannot be smuggled in by configuration | **pass** | Adding `product_present_threshold_m: 1.0` to `cycle:` was rejected: `ConfigError: unknown key(s) in [cycle]: ['product_present_threshold_m']. The bridge carries no thresholds, tolerances or timers…` |
| 17 | **Invariant 1** — no safety function over OPC UA | **pass** | Every occurrence of the red mushroom is labelled a **process** stop, in all six places it appears: `opcua-nodes.md` §9.3/§9.6, `bridge/README.md`, `sim/README.md`, `sim/worlds/cell.sdf`, `sim/launch/cell_bringup.launch.py`, `plc/demo-cell/SPEC.md` §2 and §12. Every `e-stop` string in the repo is a disclaimer, never a claim. No safety node exists (§9.8 refusal table) |
| 18 | **Invariant 12** — Gazebo only | **pass** | Every `mujoco` string in the repo is a prohibition (CLAUDE.md, ADR 0001, `sim/README.md`, two briefs, `install.sh` comment). The run used `gz sim -r -s` via `ros_gz_sim` |
| 19 | **Invariant 3** — no VDA 5050/MQTT in the bridge | **pass** | No `paho`, `mqtt` or `vda5050` reference of any kind under `bridge/` |
| 20 | Layer boundaries vs what the code does | **pass** | All five top-level READMEs open with "This layer must not access". `bridge/` imports nothing from `fleet/` or `agv/` (both still README-only). `plc/README.md` correctly forbids the PLC calling out to the bridge (ADR 0005) |
| 21 | **Four-way agreement on the reset chain** | **pass** | SPEC.md §3.1 node 5 `DemoCell/Input/PanelResetPressed` (15 tags) = opcua-nodes.md §9.3 row 5 and §9.9 map row = `bridge.yaml` `PanelResetPressed: ["Input","PanelResetPressed"]` / `panel_reset: "/cell/panel/reset"` = the live `ros2 topic list` (`/cell/panel/reset` present). Polarity agrees in all four: NO contact, fail state FALSE |
| 22 | m3-12's flagged residual | **confirmed, and wider** | opcua-nodes.md:229 does still read "the PLC forms the rising edge and **times the hold**", while SPEC.md §6.7 times nothing (`#resetRise := PanelResetPressed AND NOT #ResetEdgeMemory`). Four further occurrences listed in `open_questions` |
| 23 | Git hygiene, `705482f`..HEAD (21 commits) | **pass** | All 21 authored `Ozkan Ceylan <ozkannceylan@gmail.com>`. All conventional, imperative, scope in the valid area set (`infra`, `interfaces`, `plc`, `bridge`, `sim`, `safety`). No `Co-Authored-By`, no generated-with footer, no mention of tooling — the only "claude" strings are the literal path `.claude/settings.local.json` in a commit body describing that file. One logical change each |
| 24 | Run artefact discipline | **pass** | `git check-ignore -v bridge/evidence/latency-latest.csv` → `.gitignore:9:bridge/evidence/*-latest.csv`, a repo rule; the committed `latency-2026-07-27.csv.gz` stays tracked. `git status` clean before and after this verification |
| 25 | Write-access discipline in the reports | **pass** | Exemplary. m3-05, m3-10, m3-11, m3-12 and m3-03e each name the out-of-scope file they needed and mark it **"REQUESTED, not created"** rather than reaching outside their directory. No report's `files_changed` leaves its agent's scope |
| 26 | PLAN / TODO / LESSONS vs roadmap.md | **fail** | roadmap.md is correct (M3 in progress, gate table matches ADR 0004). PLAN.md and TODO.md are stale against three delivered reports — detail in `open_questions` |

## One measurement divergence, reported not smoothed

`L6` (`cmd_speed → belt velocity ≥ 50 %`, sim time) is a **simulator** property, and the
committed §A.4 records `4.000 ms in all four command changes`. This run recorded two L6
events: **2.000 ms** (one physics step) for the 0.15 m/s command from rest mid-travel, and
**1384.000 ms** for the −0.15 m/s command issued while the belt was pressed against its
+2.50 m mechanical stop (pose log: `sim 52.8 belt_pos 2.5 belt_vel 0.0`). Nothing in the
bridge changed between the two; the difference is the `JointController` unwinding against a
joint limit. The committed figure is therefore correct for its scenario and is **not a
general property of the cell**. Neither number is a bridge latency and neither belongs in a
gate claim without its starting state stated. No document currently says this; it is a
candidate note for §A.5 rather than a defect.

Two cosmetic residuals, both defensible as written, listed so they are not re-discovered:
`SPEC.md` §8 rows A and C say "the six inputs froze" — a citation of the six-node container
evidence, in a column headed by what was observed, while §6.1/§7/§11 correctly say seven.
`bridge-design.md` §2's diagram label `7 /cell/* topics` (m3-03e open question 1) is now
exactly right read as topics: the bridge touches six subscriptions plus `cmd_speed`.

## The owner-executed remainder

I am not closing this gate, and I cannot: two of its four exit items name a TIA watch table
and a running S7-1500, and no test double substitutes for either. `bridge/test_double/README.md`
and `EVIDENCE_LATENCY.md` §A.7 already say so, correctly.

| PLAN.md exit item | Agent-side status | What is still required |
|---|---|---|
| (a) Gazebo sensor state visible as PLC input bits in a **TIA watch table** | **Not closable by an agent.** The transport is proven to the node: the double observed real belt position, belt speed, raw range and all four contacts. What is unproven is that an S7-1500 DB shows them | Owner: PLCSIM Advanced + TIA watch table screenshots of the 7 `"DemoCellInput"` tags, per SPEC.md §10 steps 7 and 9 and §11 test 4.8 |
| (b) PLC output bits drive the Gazebo actuator, **verified visually** | **Half closable.** The path `Output/ConveyorSpeedCommand → /cell/conveyor/cmd_speed → belt → product` is proven end to end here, but the value's source was the double's `--command-file` back door, i.e. a human, not a program | Owner: the same observation with `ConveyorSpeedCommand` written by the **TIA program** (§6.4 gated setpoint, including the mandatory `ELSE` to 0.0), and a visual/recorded capture of the belt |
| (c) Latency and update rate measured and written down | **Closed on the agent side, twice.** Container Section A and this WSL run agree, and the WSL numbers are equal or better | Owner: **Section B of `bridge/EVIDENCE_LATENCY.md`**, items 1–8 as written there — environment block, the §A.4 table regenerated by `tools/summarize_latency.py`, L4 as a bound plus the watch-table view, **L7** (the one true end-to-end number, only measurable once a program responds), the startup rule against real DB start values, and the note of which server produced each figure |
| (d) Signal-loss behaviour defined and tested | **Defined and tested for the bridge and the input image; untested for the reaction.** All four §7.3 cases reproduce under WSL against the seven-node image (A and C above; B as the clean shutdown; D unchanged — the double has no program, so `Status/*` stayed at start values for every run) | Owner: **the PLCSIM section of `EVIDENCE_SIGNAL_LOSS.md`** — what the *equipment* does. Specifically §B item 6: `BridgeLinkOk := FALSE`, `CellCycleRunning` dropped, setpoint driven to `0.0`, `CellResetRequired := TRUE`, and the confirmation that a **returning heartbeat alone does not restart the conveyor**; plus §B item 7, how long a real S7-1500 holds a session after a bridge SIGKILL, the one in-container result known not to transfer |

Blocking order, unchanged: SPEC.md is now retargeted onto the real reset contact
(`91ef599`), so the TODO's "do not start before m3-12 lands" condition is satisfied. The
clock item in TODO remains live — `w32time` is Stopped again and the residual drift
re-accumulates, so it must be re-run before any Section B timing capture is trusted
(LESSONS 2026-07-27, clock).

## lessons_candidates

- 2026-07-27 | Compared a re-run's L6 against the committed "4.000 ms in all four command
  changes" | The two disagreed by 350x, and the cause was the belt's starting state (against
  a mechanical stop vs mid-travel), not the bridge | A simulator-property measurement is
  quoted with the mechanical state it started from; without that, a scenario-dependent
  number reads as a stable property.
- 2026-07-27 | TODO named one stale hold-time phrase in opcua-nodes.md §9.3 | The superseded
  mechanism actually survives in five places across three files, two of them another agent's
  | Reconfirms the existing rule (LESSONS 2026-07-27, m3-03c): when a report names a stale
  phrase, the follow-up brief searches for the phrase rather than trusting the citation.
