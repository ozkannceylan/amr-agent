# m5-24 — Phase 1: one vehicle behind a real wall

    gate:                M5 (supporting; ADR 0016 Phase 1)
    agent:               agv-ros2   (writes agv/; sim/ changes are REQUESTED, see §5)
    goal:                The vehicle's autonomy stack starts as one "vehicle image" from one per-vehicle config inside its own DDS domain, so a second forklift would be a second machine rather than a second process in the same graph.
    invariants_touched:  none — ADR 0016 tabulates the walk and no invariant moves
    inputs:
      - docs/adr/0016-per-vehicle-compute-and-deployment.md (the decision; especially D2, D3, D4)
      - docs/reports/m5-22-vehicle-compute-deployment-research.md §4 Phase 1 (the scope, verbatim)
      - agv/forklift/README.md (the contract table)
      - agv/forklift/launch/ (all of it), agv/forklift/config.yaml
      - agv/forklift/EVIDENCE_ENVELOPE.md §7 (the observation you must re-run)
      - sim/launch/warehouse_bringup.launch.py
      - sim/setup/WSL_ENVIRONMENT.md §12.5 (the verified bringup recipe)
      - docs/LESSONS.md
    deliverable:         the split launch tree, the per-vehicle config, the allocation file of §3, and agv/forklift/EVIDENCE_VEHICLE_IMAGE.md
    done_when:           With the sim side up and one vehicle image started as serial `F001` in its own domain: `ros2 topic list` from a DIFFERENT domain shows no `/forklift` topic; from inside the vehicle's domain the full README contract appears; a Nav2 goal is ACCEPTED; and the m5-11 §7 pass-through observation re-runs with residual `0.000e+00`. One recorded run, in the evidence file, with the commands that produced it.
    forbidden:
      - editing `agv/forklift/model.sdf` — the gz topic prefix work is Phase 2 and doing it here silently merges two phases
      - spawning a second vehicle, adding containers, or touching `bridge/`, `fleet/`, `hmi/` or any document in `docs/interfaces/`
      - writing outside `agv/` except your report — `sim/` changes are REQUESTED in the report (§5)
      - breaking the existing recipes: `gate:=false cmd_topic:=/cmd_vel_smoothed` (the m5-10 chain) and the m5-11 envelope chain must both still run, and you must show they do
      - changing any Nav2, AMCL, EKF or smoother tuning value — this brief moves where things start, not how they behave
      - adding a Python or system dependency without proposing it in the report first
      - re-deriving the measured numbers in docs/TODO.md §"Measured numbers a later session should not re-derive"

---

## 1. The idea in one paragraph

Today one launch file starts the simulator and the vehicle together, in one
ROS 2 graph. After this brief there are two entry points: a **sim side** (Gazebo
and the world, no ROS vehicle nodes) and a **vehicle image** (everything the
vehicle's own computer would run), and the vehicle image runs inside **its own
DDS domain**. Nothing else changes. The point is that the boundary becomes real
— and a real boundary is one you can demonstrate by failing to see across it.

## 2. What the vehicle image owns

Everything ADR 0016 assigns to the vehicle: its own gz bridges **including
`/clock`**, sensor TF, wheel odometry, the IMU gate, the EKF, map server and
AMCL, the full Nav2 stack, the Twist→tricycle converter, `forklift_io`, and the
envelope gate. It takes its identity from one per-vehicle config: **serial
number, domain ID, spawn pose**.

Read ADR 0016 D2 and D3 before you design this. If the ADR and this brief
disagree, the ADR wins and you say so in the report.

## 3. One ruling, so you do not have to ask

The research left the domain-ID allocation table's home open (its open question
3). **It is ruled here: exactly one file owns the serial → domain-ID mapping,
and no other file restates a domain ID** (invariant 10). Put it at
`agv/forklift/vehicles/allocation.yaml` unless the ADR names somewhere better,
name it in `agv/forklift/README.md`, and reserve **10 for the operator /
monitoring side and 51–54 for vehicles**, F001 taking 51. A per-vehicle config
file may reference its serial; it must not carry a second copy of the number.

If you find a reason this layout is wrong, say so in the report and implement
the constraint (one owner for the mapping) rather than the layout.

## 4. Proving the wall — this is the deliverable

A boundary claimed is worth nothing. Show it:

1. From a **different domain**, `ros2 topic list` shows no `/forklift` topic.
   Give the command, the domain, and the actual output.
2. From **inside** the vehicle's domain, the full README contract table
   appears. Diff it against the table rather than eyeballing it.
3. A Nav2 goal is **ACCEPTED** (it need not complete — acceptance proves the
   stack is wired; a completed goal is better if it is cheap).
4. The m5-11 §7 pass-through observation re-runs with residual **`0.000e+00`**.
   Note that §7 now carries a correction: the **residual** is a design property
   and must reproduce exactly; the **latency** figures were a sample, not a
   bound, and are expected to move. Report the latency you see and do not treat
   a difference as a regression.
5. Both compatibility recipes still run. Show each starting.

## 5. sim/ is not yours — request it

Phase 1 needs the simulator entry point separated from the vehicle nodes, and
`sim/launch/` belongs to the sim agent. Do whichever of these is true:

- if you can achieve the split entirely from `agv/` (for example, a vehicle-image
  launch that no longer relies on `warehouse_bringup` starting vehicle nodes),
  do that and **state in the report exactly what `sim/` should change** to make
  the separation clean rather than merely worked around;
- if you cannot, stop at the boundary, report what is needed, and deliver
  everything that does not depend on it.

Either way the report names the `sim/` edits precisely enough to become a brief.

## 6. Working discipline

- **Write results into `EVIDENCE_VEHICLE_IMAGE.md` as they land.** Create it
  with its headings before your first run.
- The machine now has Nav2 and `robot_localization` as **system packages** (m5-21,
  2026-08-05); the `.deb` overlay is retired. Use `sim/setup/WSL_ENVIRONMENT.md`
  §12.5's verified recipe.
- **Measure alone.** Another agent may be running; check before a timed run and
  say when you ran (LESSONS 2026-07-30).
- `GZ_PARTITION` isolates gz transport and `ROS_DOMAIN_ID` isolates DDS — they
  are different transports and one does not do the other's job (LESSONS
  2026-07-27).
- **Do not commit.** The orchestrator commits by pathspec.
- Write `docs/reports/m5-24-vehicle-image-phase1.md` in the CLAUDE.md §5 format.
- Read `docs/LESSONS.md` first.
