---
title: M6.5 — Four vehicles, and Milestone 6's acceptance
date: 2026-08-22
status: approved
---

# M6.5: four forklifts, ten stations, and the milestone's own proof

## Where this sits

Last of M6's five sub-projects (AMR-DEC-002), and the one that answers
the milestone's own sentence: *VDA 5050 fleet at scale — 4 forklifts,
10 stations, traffic avoidance.* M6.1-M6.4 built and measured that
system at two vehicles. M6.5 makes it four, closes the debts those
gates measured, and produces the acceptance run the milestone is judged
on.

**Owner rulings 2026-08-22:**
- **Measure RTF first, then decide.** The first task is a four-vehicle
  RTF spike, before any wiring. `>= 0.30` → proceed. Below → STOP and
  report to the owner with the number and the options; do not lighten
  the world pre-emptively, because that would make the four-vehicle
  figures incomparable with the two-vehicle ones already recorded.
- **MEASURED 2026-08-22, twice, and the second measurement retired the
  first ruling.** The llvmpipe spike said 0.190-0.230 at four and the
  owner ruled two concurrent drivers. Then the owner asked for the same
  measurement on the WSLg D3D12 passthrough
  (`GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`,
  renderer confirmed `D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`,
  `Accelerated: yes`), and four vehicles with all sixteen lidars
  subscribed measured **0.583 / 0.687 / 0.670** by the file's printed
  statistic and **0.90** integrated — three runs, every one over the
  0.30 gate. The twelfth-lidar cliff (0.981 → 0.274 under llvmpipe) is
  gone.
  Two things this taught, both recorded in PROOF with no number
  deleted: **(i)** gz-sim renders a lidar only when something
  subscribes, so render cost follows SUBSCRIPTION, not motion — that
  finding stands and it is why M6.1's server-only 0.934 measured two
  trucks' physics rather than their sensors; **(ii)** the printed
  statistic (mean of instantaneous `real_time_factor`, this file's
  convention since M6.1) **understates a bursty run**. Integrated
  Δsim/Δreal from the same messages puts llvmpipe's four trucks at
  **0.579**, not 0.190 — also over the gate. The first STOP was as much
  the arithmetic as the machine.
  **Owner ruling 2026-08-22 (supersedes the two-driver ruling): all
  four vehicles drive.** No ACTIVE/PARKED roles, no concurrency cap —
  four full stacks, sixteen lidars bridged, every truck eligible for
  work. The condition is environmental and must be documented rather
  than hidden: the GPU driver variables have to be in the operator's
  shell (`~/.bashrc`), the acceptance run records the RTF it actually
  saw under the full stack, and if that falls below the gate it is
  reported as measured, not smoothed.
- **Station handover: hold the junction through the dwell.** The spur
  entry node is not released on arrival; it stays held until the dwell
  ends and leg 2 goes out. Small and local (it changes what
  `release_through` may free), and it cuts M6.4's Gate 2 swap deadlock
  at the source. The cost is accepted: a second truck bound for the
  same station waits a few seconds longer.

## Non-goals

- No new protocol surface: no pause actions, no node actions, no
  charging, no re-planning around blocked routes (a blocked vehicle
  still waits — M6.4's rule).
- No physical anti-collision claim, ever. Reservation is process
  deconfliction; the scanners, the F-model and the onboard guards are
  the only things that stop a truck. Four vehicles do not change that
  and the acceptance run must say so.
- No persisted ledger, no wire change to `nodeStates` (the restart
  residual stays open and stated).
- No fourth PLCSIM instance: f3/f4 run the virtual F-PLC like f2 (only
  f1 ever ran against a real PLC program — the acceptance record says
  which vehicle proved what).
- Steps 1-5, `m5_ver2/`, `agv/`, the safety chain and the writer are
  untouched.

## The debts this closes (M6.4's carry list)

1. **Spur handover** (Gate 2's blocker) — the owner ruling above.
2. **`arrived_now`'s residual race** — anchor arrival on
   `progress.reached == len(progress.nodes)` rather than on the
   horizon being empty, closing the one-nav-period window where a
   horizon-emptying extension could complete an order early.
3. **Horizon-shrink stuck-`executing`** — unreachable through this
   fleet's builder; pin it with a test so it stays unreachable.
4. **Idle trucks hold their node forever** — a truck parked mid-aisle
   with no task blocks it with no timeout. At four vehicles this is the
   difference between a busy floor and a jammed one: an idle vehicle's
   hold is released after `IDLE_HOLD_S` (default 30 s) unless it is the
   station spur it is parked in; the release is logged and shown.
5. **Rolling hulk** — a LOST vehicle's parked node is pinned at the
   pose where it was lost; if the truck rolls, the pin is wrong. On the
   vehicle's return the pin moves to its first reported pose before
   eligibility is re-earned (it already must report a clean idle state;
   this makes the pin follow it).
6. **`fleet_manager.py` at 1,495 lines** — split the floor out into
   `fleet/floor.py` (the traffic loop: holds, releases, extensions,
   deadlock, the traffic block of the status document), leaving the
   manager the registry, the queue, assignment and the wire. Pure
   move-and-name refactor, no behaviour change, tests unchanged.

The two open residuals stay open and stated in the acceptance record:
the restart-adopted base is unreserved, and the turning-radius orbit
(four measurements now) means short-spur stations are reached at their
declared 0.80 m radius, not tighter.

## Architecture

**Four vehicles, same code path.** `status_contract.VEHICLES` grows to
`f1..f4` with port families 5110/5111, 5120/5121, 5130/5131, 5140/5141
and spawn poses spread across the two aisles (the RTF spike validates
them; a pose that trips a scanner at rest moves in the table, as M6.1
did). `m6.sh` spawns four vehicle sets — the loop is already generic;
the pid count goes 21 → 39 (broker + world + fleet + 9×4). Windows
runs four scripted writers (ctl 5910/5920/5930/5940).

**Nothing else is per-vehicle.** The launch, the instantiation tool,
the manager, the ledger and the CLI are all N-generic already; M6.5
proves that rather than rewriting it. Where a two-vehicle assumption is
found, it is a defect to fix and name.

## Proof gates (live, machine-run, PROOF.md)

1. **RTF (the gate that ran first).** DONE on both renderers, and it is
   why all four drive: llvmpipe 0.190 printed / 0.579 integrated,
   D3D12/NVIDIA 0.583-0.687 printed / 0.90 integrated at four subscribed
   vehicles. What remains is the SHIPPING configuration under the full
   39-pid stack, sampled during the acceptance run and reported whatever
   it says.
2. **Station handover fixed.** M6.4's Gate 2 scenario, now passing: two
   trucks to one station, the second waits for the dwell to end and the
   occupant to leave, then arrives. No swap deadlock, no two-in-a-spur.
3. **Four-vehicle traffic.** Four transports over the ten stations with
   deliberately crossing routes; every vehicle completes; holds,
   extensions and waits recorded; 0 motor-false on all four; no
   deadlock refusal (or, if one occurs, it is named and honest).
4. **The acceptance run.** Eight transports submitted back-to-back
   across the ten stations, **all four trucks working**, run to
   completion with no operator intervention: measure throughput
   (transports/min), per-vehicle utilisation, total waiting time,
   arrival errors, 0 motor-false, and the RTF sampled during it. This is
   the milestone's headline number, and it is quoted with the GPU
   condition named.
5. **Degradation under loss.** Mid-acceptance, kill one vehicle: its
   task requeues, the remaining three finish everything, the fleet never
   assigns to the dead truck, and the floor is not left locked.
6. **Safety untouched at four.** Same causation discipline as M6.2's
   Gate 6 and M6.4's Gate 6: every Motor drop named at its sample, no
   correlation with any fleet event, across the whole session.

## Testing

- Unit: the four debt fixes (handover release rule; arrival anchor;
  horizon-shrink pin; idle-hold timeout; hulk pin follows the return),
  each with a test that fails against today's code.
- The floor split: the existing suite must pass unchanged — that is the
  refactor's proof.
- `VEHICLES` at four: the table test, the instantiation sweep, the
  writer's `--vehicle` choices, the CLI rendering four rows.
- Integration: the manager against four fakes — assignment spread,
  queueing, a deadlock among four, loss of one.
- The six live gates.

## What Milestone 6 claims when this closes

Four simulated forklifts, each with its own safety chain (virtual
F-PLC, scanners, encoder cross-check), driven by a VDA 5050 fleet
manager over MQTT with edge/node traffic reservation, completing
transports over ten stations without operator intervention — **all four
driving, on GPU rendering (D3D12/NVIDIA), at the RTF the acceptance run
measured** — with every claim traceable to a run in `m6/PROOF.md`, and
every unfixed thing named there too.
