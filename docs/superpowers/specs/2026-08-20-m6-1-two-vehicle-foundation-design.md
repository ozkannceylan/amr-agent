---
title: M6.1 — Two-vehicle foundation (step6)
date: 2026-08-20
status: approved
---

# M6.1: Two forklifts, one world — the multi-vehicle foundation

## Where this sits

M6 (VDA 5050 fleet at scale: 4 forklifts, 10 stations, traffic avoidance)
is decomposed into five sub-projects, each with its own spec → plan →
implementation cycle. This is the first:

1. **M6.1 (this spec)** — two vehicles in one world, full per-vehicle
   isolation, both safety chains live, known debt closed.
2. M6.2 — VDA 5050 vehicle agent (MQTT: state/connection/factsheet out,
   order in, mapped to the autopilot goal interface).
3. M6.3 — fleet manager (order assignment over the 10 stations).
4. M6.4 — traffic avoidance (edge/zone reservation in the fleet manager).
5. M6.5 — scale to 4, acceptance scenarios, measured PROOF.

M6.1 exists to burn down the two foundation risks first: whether this
machine's Gazebo carries multiple forklifts (4 gpu_lidar sensors each),
and whether the step5 stack multiplies cleanly. Everything runs on the
virtual F-PLC rig (`--virtual`, owner smoke passed 2026-08-20).

## Owner rulings (2026-08-20)

- **Per-vehicle writer process.** Each vehicle gets its own `step6.py`
  instance, its own `VirtualFPLC`, its own panel — mirroring the real
  topology (one PLCSIM instance, one writer, per PLC). Two windows at two
  vehicles is accepted; headless mode is deferred to M6.5.
- Sub-project order M6.1-first approved; two vehicles in this sub-project.

## Non-goals

- No MQTT, no VDA 5050 message, no fleet logic, no traffic logic.
- No third or fourth vehicle.
- No change to `agv/forklift/model.sdf`, `config.yaml`,
  `forklift_io.py`, `sto_contactor.py` — sources are used in place,
  unmodified, as both older stacks require.
- No headless writer, no fleet HMI.
- steps 1–5 stay frozen; step5 remains runnable as-is.

## Architecture

**Tree.** `m5_ver2/step6/` is a copy of `m5_ver2/step5/` (the owner's
step-copy ruling), then modified as below. Isolation: `GZ_PARTITION=step6`,
`ROS_DOMAIN_ID=96`. Vehicle identities are `f1` and `f2` — chosen short
because VDA 5050 `serialNumber` will ride on them in M6.2.

**One code path, vehicle as data.** Every per-vehicle difference lives in
one table in step6's `ipc/status_contract.py`:

```python
VEHICLES = {
    "f1": {"plc_port": 5110, "sensor_port": 5111},
    "f2": {"plc_port": 5120, "sensor_port": 5121},
}
```

ROS topic names come from the same module, namespaced per vehicle
(`/f1/plc/status`, `/f1/hmi/cmd_vel`, …): the step5 ruling stands —
`status_contract.py` is the ONE home for every ROS name `config.yaml`
has never heard of, now keyed by vehicle id. Every WSL node reads its
vehicle id from env `VEHICLE` (stamped by `step6.sh` on every spawn) and
resolves names through the table; the Windows writer takes `--vehicle`. The Windows writer reads the SAME module for its port pair —
port knowledge lives in exactly one file.

The 5100/5101 family is left to step5 on purpose: an accidentally
side-by-side step5 stack collides with nothing; the fail-closed port
pre-flight guard from `step5.sh` is carried into `step6.sh` for the new
families.

**Vehicle instantiation (sources untouched).** `model.sdf` writes every gz
topic explicitly and absolutely (`/forklift/gz/...`), so two spawns of the
source file would share topics. `step6/tools/instantiate_vehicle.py`
generates per-vehicle derived artifacts into `step6/vehicles/<vid>/`:

- `model.sdf`: every occurrence of the gz topic prefix `/forklift/` is
  rewritten to `/<vid>/`; the entity name `Forklift` becomes
  `Forklift_<vid>`. Nothing else changes; the tool asserts the rewrite
  count matches the count found in the source, so a source edit that adds
  a topic cannot slip through silently.
- `config.yaml`: the same prefix rewrite applied to the `topics:` block
  (gz names — config.yaml owns those; ROS names are status_contract's).

Generation runs at `step6.sh start` (idempotent, cheap); derived files are
git-ignored build products. `forklift_io.py` and `sto_contactor.py` are
pointed at the derived config via their existing `--config` flag.

**World and launch.** One world file; the launch spawns both derived
models at their start poses. Existing single-vehicle launch logic is
parameterized over the VEHICLES table, not duplicated.

**Windows writers.** `step6/windows/step6.py --vehicle f1 --virtual`:
reads its port pair from the shared table, owns its `VirtualFPLC`, panel
titled `Forklift f1 PLC Control Panel - VIRTUAL F-PLC (model)`. The
single-writer rule holds per PLC: one writer process per vehicle. The
non-virtual path (PLCSIM instance per vehicle) keeps working in shape —
instance name per vehicle is a constant next to the table, unused until a
license returns.

**HMI.** One commissioning HMI instance per vehicle (copy behaviour),
window titled per vehicle. Joystick, RESET, warehouse sketch — unchanged
otherwise.

## Known debt closed in this copy

1. **The gate's fail-open silence path.** `cmd_gate` gains a
   `STATUS_STALE_S`-class staleness window on its command input: enabled
   and silent → publish zeros, symmetric with the mux's own auto-source
   rule. (Named by the 2026-08-13 final review; the one silence path in
   the tree that fails open.)
2. Stale prose in `step6.sh` and the launch copy (step-number and count
   statements) swept.
3. `step6.sh`'s name list and `PATTERNS` cover the doubled node set —
   nothing orphaned on `stop`.

## Error handling

Per-vehicle fail-safe is step5's, unchanged: each writer's `finally`
trips its own model; each vehicle's WSL side fails safe on its own link
silence. Vehicles share nothing but the Gazebo world — no cross-vehicle
channel exists in M6.1, so no cross-vehicle failure path is designed, only
proven absent (gate 2 below).

## Proof gates

1. **RTF first.** Before any wiring: both derived models spawned in the
   step6 world, real-time factor measured and recorded. If RTF makes the
   20 ms loops unmeetable, STOP and return to design (sensor rates and
   world simplification are the levers, and they need an owner ruling).
2. **Cross-isolation, both directions.** F1's PF trip latches F1's Motor;
   F2's Motor, fields and encoders unaffected over the same window —
   measured, then mirrored F2→F1.
3. **Simultaneous autonomy.** Both vehicles complete independent
   station-to-station runs with overlapping drive time, 0 motor-false
   samples each, arrival radii per step5's bar.
4. **Per-vehicle stale-link.** Silencing one vehicle's 5111-family link
   fails that vehicle safe (fields False, 0/3000) and leaves the other
   driving.
5. **Clean lifecycle.** `step6.sh start`/`stop` twice in a row: no port
   squatters, no orphans, `stop` names everything it killed.
6. **The gate debt is proven closed.** Kill `cmd_mux` with Motor True:
   the plant sees zeros within the staleness window (the step4 14.8 m
   class does not recur).

## Testing

- Unit: instantiation tool (rewrite counts, idempotence, unknown-vehicle
  refusal); VEHICLES table resolution; the cmd_gate staleness window.
- Loop-level: step5's `test_step5_virtual_loop.py` pattern parameterized
  over the two port pairs.
- The proof gates above are live runs recorded in `step6/PROOF.md`,
  step5-style: measured numbers, not claims.

## Out of scope, recorded

- Headless writer mode (M6.5, when four panels stop being funny).
- VDA serial/manufacturer strings (M6.2 rides on `f1`/`f2`).
- Any shared-resource arbitration between vehicles (M6.4's whole job).
