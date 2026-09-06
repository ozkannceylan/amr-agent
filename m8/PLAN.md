# M8 development plan

Companion to `m8/ARCHITECTURE.md`. M8 lives in the vehicle's ROS 2 graph
and needs the m5-ver3 plant, so its implementation branch is cut from
the branch that carries `m5_ver3/` (`m5-ver3-close`), not from `main`.
Docs live on `main` under `m8/` so the plan is visible from the
integration branch.

## Tree

```
m8/
  ARCHITECTURE.md  PLAN.md  README.md
  m8_msgs/         Proposal.msg  Verdict.msg  SlotState.msg
  m8_core/         (pure Python, no rclpy)
                   contract.py   (Proposal validation, monotone rules, TTL)
                   gate.py       (veto logic: delta box, freshness, health)
                   arbiter.py    (speed ceiling: min of ceilings, floor, one leg, TTL)
                   vda_map.py    (Proposal/Verdict → VDA 2.1.0 state fields: loads / errors / information)
  m8_nodes/        (rclpy wrappers, thin)
                   pocket_pose_node.py   abort_node.py   slot_state_node.py
                   veto_gate_node.py     speed_arbiter_node.py   m8_health.py
  bench/           e1_pocket.py  e2_dock.py  e3_abort.py  e4_slot.py  e5_cost.py  e6_adversarial.py
                   faults/  (staged fault set: pallet absent / rotated / shifted / blocked)
  tests/           test_contract.py  test_gate.py  test_arbiter.py  test_vda_map.py  (no ROS)
                   test_no_frames_leave.py  (R3: no image topic in any bridge config)
                   test_plc_isolation.py    (R4: no M8 topic in any PLC link)
  launch/          m8_shadow.launch.py  m8_gated.launch.py
  EVIDENCE_M8_*.md (one per bench, m5-ver3 style, numbers cite files)
```

## Phases and gates

| Phase | Deliverable | Consumes anything? | Gate |
|---|---|---|---|
| A0 | `m8_core` pure modules + tests; `Proposal.msg`; `vda_map` for `errors` / `information` | no | H0: contract tests green, no ROS |
| A1 | **shadow mode**: C1 classical pocket pose + C2 abort + C3 slot state publish Proposals; gate logs and refuses everything; E1, E3, E4, E5 run | no (R1) | H1: E1 number vs tag, E3 recall/false-abort, E5 RTF cost, all written to EVIDENCE files |
| B | **abort live**: gate accepts DOCK_ABORT only (fail-safe direction); E3 re-run on the live cycle; E2 no-regression | abort only | H2: dock plugin still 5/5 on clean cycles; aborts on the fault set |
| C | **refine live**: delta box fixed from E1; DOCK_TARGET_REFINE accepted inside it; E2 full | refine inside box | H3: no regression on dock truth; strict class reported |
| D | C3 slot table flows to `state.information`, visible in `fleet/status` and the M7 console; `test_no_frames_leave`, `test_plc_isolation` | reporting only | H4: seam proven: only numbers cross, PLC link untouched |
| E | R5 speed arbiter + C5 anomaly (shadow first, then bounded) | bounded ceiling | H5: floor, one-leg, TTL each tested; converter honours min |
| F | learned candidate for C1/C2 beside the classical baseline; E1/E3 A/B; E6 | as C | H6: A/B written honestly; loser stays in the tree, named |

Phase order is fixed. A1 runs before any consumer exists, and B accepts
only the fail-safe direction. Nothing in M8 ever moves the F-PLC column
of the veto matrix off "orthogonal" (R4).

## Definition of done per phase

- Tests green under `pytest m8/tests` for `m8_core` (no ROS); benches
  run on the rig with the m5-ver3 gates (GPU preflight, health gates,
  md5, mix refusals) in front of them.
- Each EVIDENCE file names the source of every number, states the
  instrument floor, and carries the standing cautions verbatim.
- A phase that fails its gate stays open and named; it is not closed by
  narrowing the claim.

## Risks named now

- The classical pocket baseline may be worse than the tag. That is a
  result, not a failure: E1 records it and the learned candidate (Phase
  F) inherits the bar.
- RTF: the D455 colour bridge already runs for the tag; M8 inference on
  the same rig may push RTF. E5 exists to make that a number before any
  consumer depends on it.
- Domain gap: gz frames are not warehouse frames. Named leftover;
  no claim about real pallets is made from these benches.
