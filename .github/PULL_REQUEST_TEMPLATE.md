<!-- Title: what changed, in the repo's prose style. Conventional-commit
     prefixes are welcome, not required. -->

## What & why

<!-- One or two sentences. What does this PR change, and why now? -->

## Test evidence

CI parity before merge. Paste the relevant output.

- [ ] `pre-commit run --all-files` clean (or the `pre-commit` job is green)
- [ ] `python3 m6/tools/check_layer_boundaries.py` exits 0
- [ ] `python3 -m pytest m6/tests/ -q` — at least 550 passed, 0 failed
      (the `pytest-m6` job). ROS is not required for this number.
- [ ] (if the change touches the VDA agent or DDS) the `pytest-ros`
      job is green

If the change needs the rig (Gazebo, the Windows writer, a recorded
run), say so here and point at the `m6/PROOF.md` section rather than
claiming CI covered it.

- [ ] (if applicable) measured run / recording:

## Safety / regression checklist

- [ ] No `rclpy` (or other ROS import) added under `m6/fleet/`
- [ ] `m6/ipc/vda_orders.py` stays stdlib-only — it is the vehicle's
      door, used by both ends
- [ ] No secrets, certificates or broker passwords (ADR 0001 inv. 13)
- [ ] No new binaries / files over 1 MB
- [ ] Safety never traverses the network; the fleet still cannot reach
      a safety function (ADR 0001 inv. 1, 11)
