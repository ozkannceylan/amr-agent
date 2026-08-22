# M6.5 Scale to Four Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** four forklifts working ten stations under the VDA 5050 fleet manager with traffic reservation, M6.4's measured debts closed, and an acceptance run that is Milestone 6's headline evidence.

**Architecture:** the code is already N-generic — this plan proves that rather than rewriting it. Task 1 measured whether the machine can carry four (it cannot: RTF 0.19; the owner ruled two concurrent drivers). Tasks 2-3 close the five debts and split the floor out. Task 4 grows the table to four and implements the ACTIVE/PARKED roles. Task 5 runs the gates and the acceptance run.

**Task 1 is DONE, twice, and the second measurement freed Tasks 4-5.**
Under llvmpipe: 1.00 / 0.96 / 0.19 printed at one, two, four vehicles — a STOP,
and the owner ruled two concurrent drivers. The owner then asked for the same
matrix on the WSLg D3D12 passthrough (`GALLIUM_DRIVER=d3d12
MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`, renderer verified `D3D12 (NVIDIA
GeForce RTX 4050 Laptop GPU)`): four vehicles, sixteen lidars subscribed,
**0.583 / 0.687 / 0.670** printed and **0.90** integrated — three runs, all
over the gate. Two findings ride along, both in PROOF with no number deleted:
gz-sim renders a lidar only when SUBSCRIBED (so cost follows subscription, not
motion — M6.1's 0.934 measured physics, not sensors), and the printed statistic
(mean of instantaneous RTF) understates a bursty run, which puts llvmpipe's
four trucks at 0.579 integrated rather than 0.190. **Owner ruling: all four
drive** — no ACTIVE/PARKED roles, no concurrency cap. The condition is
environmental and documented, not hidden: the GPU variables live in the
operator's `~/.bashrc`, and the acceptance run reports the RTF it actually saw.

**Tech Stack:** plain Python 3, paho-mqtt 2.x, ROS 2 Jazzy (WSL), Gazebo, pytest. Tree is `/m6`.

## Global Constraints

- Only `/m6` changes (plus the spec file where a task is told to correct it). **Every commit PATH-SCOPED** (`git add <paths> && git commit -m "..." -- <paths>`): the index carries unrelated staged work from a parallel session. Never `git add -A`.
- Steps 1-5, `m5_ver2/`, `agv/`, the safety chain, the writer's PLC logic and the HMI are untouched.
- Reservation is process deconfliction and never a collision claim — restate wherever new traffic code lands.
- Suites: `cd m6 && python3 -m pytest tests/ -q` baseline **439**; step5 **220**. Neither may regress. WSL runs need `source /opt/ros/jazzy/setup.bash`.
- Commit style `m6: ...` lowercase, no attribution.
- Rig facts: broker needs `LD_LIBRARY_PATH` (`m6.sh`'s `BROKER_LIB`); the stack is 21 pids at two vehicles and becomes 39 at four (broker + world + fleet + 9×4); scripted writers on ctl 5910/5920 (+5930/5940); `./m6.sh deploy` MUST be re-run before any live gate (M6.4's gates lost a run to a stale deploy); ONE pre-started ROS recorder (starting nodes mid-run starves `sensor_link` and latches ESTOP1).

---

### Task 1: RTF at four — the STOP gate

**Files:** Modify `m6/tools/rtf_spike.sh` (parameterize the vehicle list); Modify `m6/PROOF.md` (record the measurement).

The M6.1 spike hard-codes f1/f2. Make it take the vehicle ids as arguments (default: all of `status_contract.VEHICLES`), spawn each derived model at its table pose, and sample `/world/warehouse/stats`'s `real_time_factor` as it already does (`gz stats` does not exist on this Gazebo — that finding is in PROOF; keep the working sampler).

Because Task 4 has not grown the table yet, this task derives f3/f4 models **temporarily**: run `tools/instantiate_vehicle.py` for f1/f2 as usual, then copy `vehicles/f1/model.sdf` twice with the prefix rewritten to `/f3/` and `/f4/` by the same rule the tool uses (a five-line scratch script in the scratchpad, NOT committed — the tool learns f3/f4 for real in Task 4). Spawn poses for the spike: f1/f2 at their table poses; f3 at `(-8.0, 5.65, yaw 0)` and f4 at `(8.0, 5.65, yaw 3.14159)` — main-aisle positions clear of racking; if a model rests tilted or a scanner reads PROTECTIVE at rest, move it and say so.

- [ ] **Step 1** Parameterize the script; `bash -n` clean.
- [ ] **Step 2** Measure, server-only, headless, no ROS stack: 30 s at one vehicle (control), 60 s at two (comparable to M6.1's 0.934), 60 s at four. Three runs of the four-vehicle case; report mean/min/max and the sample counts.
- [ ] **Step 3** Record in PROOF.md as `## [x] M6.5 Gate 1 — RTF at four` with the commands, the samples, the means, the machine, the date, and the verdict line against **0.30**.
- [ ] **Step 4 — THE GATE.** If the four-vehicle mean is **below 0.30**: commit the measurement, then **STOP and report BLOCKED** with the numbers and the options (sensor rate, headless-only vehicles, fewer simultaneous drivers) — do not start Task 2, do not lighten the world on your own initiative.
- [ ] **Step 5** Commit path-scoped: `m6: gate 1 at four - what this machine can carry`.

---

### Task 2: the five debts

**Files:** Modify `m6/fleet/fleet_manager.py`, `m6/fleet/traffic.py`, `m6/ipc/vda_agent.py`; Tests: extend `m6/tests/test_traffic.py`, `test_fleet_manager_stub.py`, `test_vda_agent_mqtt.py`.

Each fix needs a test that **fails against today's code** — write it first, watch it fail, then fix.

1. **Spur handover (owner ruling).** On arrival the manager must not release the spur entry node; it stays held until the dwell ends and leg 2's hold is in place. Implement where the release happens (`release_through` is called with the arrival node — the entry node is the one *before* it on the route). The cleanest shape: on `leg1_arrived`, call `release_through` for everything before the entry node, and hold the entry node + station node through the dwell; on leg-2 publish, release whatever leg 2 does not need. Add `Reservations` support only if the ledger genuinely cannot express it — prefer keeping the rule in the manager.
   Test: two tasks to the same station; the second's hold must be refused while the first dwells, and granted after leg 2 goes out; no swap deadlock is detected at any point.
2. **Arrival anchor.** `vda_agent`'s `arrived_now` currently requires `not self.horizon`; anchor it on `progress.reached == len(progress.nodes)` instead (the horizon check may stay as a cheap pre-filter if it is genuinely redundant — say which you chose and why). Test: the one-nav-period race — a horizon-emptying extension processed in the same period the truck reaches its base end must NOT complete the order.
3. **Horizon-shrink pin.** A test that an update shrinking the horizon while releasing nothing ahead leaves `executing` True and the truck driveable (it is unreachable through `order_builder`, so the test constructs the message directly — the point is that it stays unreachable).
4. **Idle-hold timeout.** `IDLE_HOLD_S = 30.0`: a vehicle with no task whose hold is older than that releases everything except a station-spur node it is parked in; logged once, shown in the traffic block. Test: an idle truck's aisle node frees after the timeout, a parked-in-spur truck's does not.
5. **Rolling hulk.** On a LOST vehicle's return, move the parked pin to its first reported pose before eligibility is re-earned. Test: a truck lost at A that returns reporting B has its pin at B, and A is free.

- [ ] All five RED first, then GREEN; whole suite 439 + additions (report actuals).
- [ ] Commit path-scoped: `m6: five debts the two-truck gates measured`.

---

### Task 3: split the floor out

**Files:** Create `m6/fleet/floor.py`; Modify `m6/fleet/fleet_manager.py`; Tests: unchanged (that is the proof).

Move the traffic loop out of the manager: holds, releases, extensions bookkeeping, deadlock resolution, the `traffic` block of the status document. `floor.py` owns a `Floor` class holding the `Reservations` ledger and the per-task traffic records; the manager keeps the registry, the queue, assignment, the wire and the dwell timer, and calls into `Floor`.

**This is a pure move-and-name refactor: no behaviour change.** The existing suite must pass **unchanged** — no test edits except imports that must follow a moved name. If a test needs a real edit, that is a behaviour change: stop and report it rather than adjusting the test.

- [ ] Verify: whole suite identical count to Task 2's end state; `fleet_manager.py` under ~900 lines and `floor.py` under ~600 (report actuals — the line budget is a direction, not a cliff).
- [ ] Commit path-scoped: `m6: the floor moves into its own room`.

---

### Task 4: four vehicles

**Files:** Modify `m6/ipc/status_contract.py` (VEHICLES), `m6/windows/m6.py` (`--vehicle` choices), `m6/m6.sh` (table-driven spawn, pid prose, port guards), `m6/fleet/fleet_cli.py` (four rows); Tests: `test_vehicles_table.py`, `test_instantiate_vehicle.py`, `test_m6_virtual_loop.py`, the manager stub, plus anything asserting two.

- `VEHICLES` gains `f3` (5130/5131) and `f4` (5140/5141) with the poses Task 1 validated as resting level and scanner-clear: f3 `(-8.0, 5.65, yaw 0)`, f4 `(8.0, 5.65, yaw 3.14159)`.
- `m6.sh`: the spawn loop is `for vid in f1 f2` today — drive it from the table so the script never hard-codes the fleet again; port guards cover all four plc ports; pid prose in the non-decaying style (report the real count); the final echo lists four writer command lines.
- The writer's `choices` tuple and the CLI follow the table (the choices-drift guard test exists and will fail until you update — that is the point).
- Hunt two-vehicle assumptions: `grep -rn "f1|f2" m6/ --include="*.py" --include="*.sh"` (extended regex); anything assuming exactly two is a defect to fix and name.
- **Document the GPU condition** where the operator will meet it: `README_m6.md` gets the two exports and one line saying what they buy (measured: four vehicles at 0.58-0.69 printed / 0.90 integrated vs 0.19/0.58 on llvmpipe) and that `m6.sh` deliberately does not set them — the shell owns the environment.

- [ ] Verify: suite green (report the count and every test you touched); `./m6.sh deploy` then `start --headless` → the pid count you document, all four agents ONLINE in the broker log, `fleet_cli.py status` renders four rows; `stop` clean, all eight vehicle ports plus 1883 free.
- [ ] Commit path-scoped: `m6: the fleet is four`.

### Task 5: the six gates and the acceptance run

**Files:** Modify `m6/PROOF.md`; optionally `m6/README_m6.md` + `m6/CONTEXT.md` (four-vehicle operating notes).

Method library: PROOF's M6.1-M6.4 gate sections. Four scripted writers, one ROS recorder, one MQTT recorder (`uagv/v2/amragent/+/#` and `fleet/#`), `./m6.sh deploy` first, teardown discipline.

Gates per the spec (2-6; Gate 1 landed in Task 1):

2. **Station handover fixed** — M6.4's Gate 2 scenario now passing.
3. **Four-vehicle traffic** — four transports with deliberately crossing routes, all four trucks driving; every one completes; holds, extensions and waits recorded; 0 motor-false on all four; no deadlock refusal (or, if one occurs, it is named and honest).
4. **The acceptance run** — eight transports back-to-back across the ten stations, all four trucks, no operator intervention. Measure and report: throughput (transports/min), per-vehicle utilisation, total waiting time, arrival errors, motor-false counts, and the full-stack RTF sampled during it (report whatever it says — if it falls under the gate, that is the finding). Quote the headline with the GPU condition named.
5. **Degradation under loss** — kill one vehicle mid-acceptance; its task requeues, the surviving three finish everything, the fleet never assigns to the dead truck, and the floor is not left locked.
6. **Safety untouched at four** — every Motor drop named at its sample, no correlation with any fleet event, across the whole session.

Then write the milestone's closing section in PROOF.md: **what Milestone 6 claims, and what it does not** — the claims traceable to gate numbers, the open residuals (the GPU environment the four-truck figures depend on; restart-adopted base unreserved; turning-radius orbit; f2-f4 never ran a real PLC program; reservation is not anti-collision), each with a pointer to where it was measured.

If a gate fails: record measured-and-failed, do not tick, report BLOCKED. Teardown; suites at the end.

- [ ] Commit path-scoped: `m6: the acceptance run - four trucks, ten stations, no hands`.
