# m5-50 — the plant's brake and controller disable

brief:               Task 4 of `docs/superpowers/plans/2026-08-06-m5-closure.md`
                     (m5-50), against `docs/superpowers/specs/2026-08-06-sls-ss1-fplc-design.md` §5
                     and `plc/forklift-safety/SPEC.md` §11.7's obligation table
status:              done
invariants_touched:  none. No ADR proposal.

## What was built

`model.sdf`'s three joint controllers no longer listen on the topics the
vehicle stack publishes. They listen on three **motor terminals** —
`/forklift/gz/actuator/{steer,traction,fork}_cmd` — and a new node,
`scripts/sto_contactor.py`, is the terminals' only publisher. While torque
is present it forwards the command topics to them one message for one
message. On `/forklift/safety/torque_off_demand` `TRUE` it **latches
open**: it forwards nothing, drives the traction terminal to a standing
zero (the holding brake), and holds the steer and fork terminals at their
last forwarded values.

The interlock is at the model's inputs and not inside a command node
because **five committed publishers address the plant directly**
(`forklift_io`, `localization_run`, `steer_bench`, `safe_speed_bench`,
`sim/scenarios/warehouse_mapping_route`). An interlock in any one of them
would be bypassed by the other four.

**It is a stand-in and every artefact says so.** No Category, Performance
Level, SIL or PFH is claimed for it or implied by it (ADR 0011 D5). It
forms no demand — the demand is the F-program's (invariant 10).

## Inventory first, then the plant, then the re-measurement

`PLANT-CHANGE-INVENTORY.md` §§6–10 were written **before** the edit, with
`model.sdf` at `md5 48e22f3f…` and no simulator run, in the method §§1–5
established. They classify every figure in this layer's evidence against
three affect criteria — actuator-path latency, actuator-path continuity,
and any observation that the vehicle **failed to move** — and set the
re-measurement order §§3–7 of `EVIDENCE_STO.md` then followed.

## The observable, which is the deliverable

Three runs, six steps, 3/3 clean (`EVIDENCE_STO.md` §6):

- a command sent straight at the plant after torque-off moved the vehicle
  **0.0000 m**, with **161 commands delivered to the plant boundary**;
- **the envelope reopened fully permissive** and a 0.40 m/s `Twist` was
  fed through the real chain: the converter formed **128 setpoints**, 128
  commands reached the boundary carrying **3.3333 rad/s**, and the vehicle
  moved **0.0000 m**;
- the demand fell and **the same envelope and the same `Twist`** then
  moved it **2.3723 m**.

SS1's two stages are therefore distinguishable rather than nominal.

## The trap, hunted rather than assumed

The 2026-08-05 lesson on this file is that a fix un-masks as readily as it
removes. The symmetric question here has a specific answer: **a contactor
that is not running produces a vehicle that does not move**, and every
refusal-shaped observation in this repository reads that as a pass —
`EVIDENCE_NAV2.md` §5.4's "the vehicle moved 0.000 m" above all. It was
measured rather than argued: with the contactor stopped, **0 of 3**
commands produced motion, indistinguishable from torque-off by motion
alone. What distinguishes them is the readback
`/forklift/safety/torque_off_applied`, which has no publisher at all when
the contactor is absent. **Every no-motion observation in this work
carries a positive control in the same run**, and that rule is written
into the bench, the launch file and the evidence.

## What the change cost, measured

| | Value |
|---|---|
| hop residual | **0.0**, 299 of 299 matched pairs — a design property |
| hop latency | mean **0.403 ms**, max **0.845 ms**, n = 299 — one draw, no upper bound established |
| end to end command-to-motion | baseline 6.851 ms mean (12/12) → 8.319 ms mean (12/12); the +1.5 ms is inside either column's own 16 ms spread |
| `EVIDENCE_ENVELOPE.md` §3 stop distance | committed 0.1738 / 0.1719 m, **re-run 0.1744 m** — a third draw, not a supersession |

At 0.40 m/s the worst observed hop is 0.34 mm against a figure whose own
draws span 2.5 mm, so the inventory's class-(i) figures are affected in
principle and below their own resolution in practice.

## files_changed

- `agv/forklift/PLANT-CHANGE-INVENTORY.md` — §§6–10 appended, pre-edit; existing content byte-identical (175 insertions, 0 deletions)
- `agv/forklift/model.sdf` — three plugin topics re-pointed to the terminals, and the command-topic comment block rewritten to explain them
- `agv/forklift/scripts/sto_contactor.py` — new; the contactor, with a no-ROS `--self-check` that asserts the latch has exactly one writer
- `agv/forklift/scripts/sto_bench.py` — new; the four measurement phases
- `agv/forklift/config.yaml` — the three terminal topics, the two safety topics, the `sto:` constants block
- `agv/forklift/launch/vehicle.launch.py` — bridges the terminals instead of the command topics; starts the contactor, on a `sto_contactor` argument defaulting true and deliberately not tied to `nodes`
- `agv/forklift/README.md` — the ROS contract table gains four rows
- `agv/forklift/EVIDENCE_STO.md` — new; the whole measurement record
- `agv/forklift/EVIDENCE_ENVELOPE.md` — dated §13 appended; existing content byte-identical
- `agv/forklift/EVIDENCE_MODEL.md` — dated third supersession note appended; existing content byte-identical
- `agv/forklift/evidence/m5-50-*.json`, `m5-50-r1-enable-drop.csv`, `m5-50-r2-enable-drop-clean.csv*` — the records

Nothing outside `agv/` and this report was written. `plc/` was read and
not touched.

## Requests — work this layer cannot do

1. **bridge/ and interface**: the demand has no carrier. Every run here
   published `/forklift/safety/torque_off_demand` from the bench, because
   `Forklift/Safety/TorqueOffDemand` has no mirror node and the bridge
   publishes no ROS topic for it. This is the same request
   `plc/forklift-safety/SPEC.md` §11.10 already carries for the two mirrors;
   what m5-50 adds is the ROS-side name, type and polarity, stated in
   `agv/forklift/README.md`'s contract table and `EVIDENCE_STO.md` §8.
2. **sim/, and this one is load-bearing today**:
   `sim/launch/forklift_bringup.launch.py` carries its own duplicate bridge
   list naming the **old** command topics and does not start the contactor.
   After this change a vehicle brought up that way receives nothing at the
   plant. It was hit for real during this work — the first §7 launch looked
   like a healthy bringup and the plant was unreachable. The fix is the two
   changes `agv/forklift/launch/vehicle.launch.py` already carries: bridge
   `/forklift/gz/actuator/*_cmd`, and start `agv/forklift/scripts/sto_contactor.py`.
3. **sim/**: `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` §5 and §6 are
   commanded-to-observed responses through the changed path. §5's
   contradiction with the m5-38 traction finding, recorded in the first
   inventory, is still open and this change does not settle it.
4. **plc/**, for a later brief and not urgent: §11.7's obligation table is
   now satisfiable, and §11.2's ownership table's `agv/` row (the
   `SPD`/`MOT`/`PING` client) is a separate outstanding item from m5-49.

## open_questions

1. **Should the contactor treat a demand link that has gone silent as
   torque-off?** It does not, and the reasoning is written into the node,
   the config and `EVIDENCE_STO.md` §2: invariant 2 makes supervision loss
   a degraded mode, the controlled stop for it already exists in the
   envelope gate's stale rule, and inferring a safety reaction from network
   silence is what invariant 1 forbids. It is a design decision with a
   defensible opposite and the owner may want to rule on it explicitly.
2. **Does the fork terminal's hold need a slip model?** The carriage is
   held by a position controller at its last commanded height, so under
   torque removal it does not descend at all. A real vehicle's mast would
   settle. Nothing in M5 tests it, and inventing a settle rate would be a
   number chosen rather than derived.
3. **The plant's brake has no torque limit.** A standing zero-velocity
   command at a `JointController` pins the shaft absolutely, so the vehicle
   holds on any slope. That is stated as a limit in `EVIDENCE_STO.md` §1
   rather than modelled; a slip torque would need a figure nothing in this
   project supplies.
4. Four class-A supporting figures (`EVIDENCE_NAV2.md` case set,
   `EVIDENCE_LOCALIZATION.md` (a)/(b), `EVIDENCE_VEHICLE_IMAGE.md` proof 3)
   are deferred with the §4.1 qualifier rather than re-run, on the plan's
   own ruling that autonomy is frozen as a prototype.

next_suggested:      Task 5 — the owner's TIA session against `plc/forklift-safety/SPEC.md` §11.9 — with request 2 above issued to sim/ in parallel, because until it lands every warehouse-bringup run has an unreachable plant.
