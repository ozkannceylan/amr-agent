# ADR 0017: CI as the integration gate

Status:        accepted

Context:       Until this ADR the cell's quality signal was a pytest
count pasted into `m6/PROOF.md` after a measured run on the owner's
WSL2 rig. That is the right place for a gate that needs Gazebo, a GPU
and four virtual F-PLCs. It is the wrong place for a regression that a
pull request can introduce in a pure function - `vda_orders.validate_order`,
`traffic.reserve`, `VirtualFPLC`'s ESTOP1 chain - because those modules
do not need the rig, and waiting for the rig means the regression lands
on `main` first.

A sister portfolio (`robotics_cicd`: ROS 2 Humble + MuJoCo, colcon,
headless SIL, GHCR release) showed the pipeline shape: protected `main`,
required checks, localhost DDS, JUnit artifacts, a versioned image.
This repo cannot copy that pipeline. It is not a colcon workspace
(invariant 12 pins Gazebo, not MuJoCo; `m5_ver2/CLAUDE.md` forbids a
package layout), the live cell is ROS 2 Jazzy (ADR 0003), and the
expensive tests are a 39-process Gazebo fleet plus a Windows writer.
What transfers is the *discipline*: the check that gates a merge is
the check that runs on every PR, against the tree that will actually
land, and it produces an artifact a human can read when it fails.

Decision:      Pull requests against `main` are gated by GitHub Actions
on four jobs, in this order of cost:

1. **pre-commit** - hygiene only (whitespace, YAML, merge-conflict
   markers, line endings, no newly added large binaries). Formatters
   that would rewrite the historical trees are out of scope.
2. **invariants** - mechanical restatements of ADR 0001 that a grep
   can fail: the fleet tree does not import `rclpy`, `ros_optional`,
   or any vehicle ROS node; `vda_orders.py` stays stdlib-only. A check
   that needs judgement stays with the verifier agent and is not this
   job.
3. **pytest-m6** - `python3 -m pytest m6/tests/` on Ubuntu 24.04 /
   Python 3.12, with `paho-mqtt`, `python3-tk` and the vendored
   mosquitto from `m6/tools/install_broker.sh`. ROS is **not** a
   dependency of this job. IPC/HMI nodes import ROS types through
   `m6/ipc/ros_optional.py`, so their pure-function tests collect
   without `/opt/ros`. The job fails if pytest reports failures or
   errors, or if fewer than 550 tests pass (measured 2026-08-28:
   569 passed, 1 skipped - the skip is `test_vda_agent_mqtt.py`,
   which needs a live rclpy context).
4. **pytest-ros** - the same suite inside `ros:jazzy-ros-base`, with
   the FastDDS loopback profile and `ROS_AUTOMATIC_DISCOVERY_RANGE=
   LOCALHOST`. This is the job that runs `test_vda_agent_mqtt.py`.
   Floor: 570 passed.

Later jobs - a headless Gazebo SIL, a GHCR image - are sequenced in
[`docs/superpowers/plans/2026-08-28-ci-cd-integration.md`](../superpowers/plans/2026-08-28-ci-cd-integration.md)
and each becomes a required check only after it has been green on
`main` for a stretch. GitHub's merge queue is adopted once these jobs
are required; it is a repository setting, not a file.

What this ADR does **not** decide:

- Invariants 1-13 are untouched. CI enforces a subset; it does not
  replace them.
- The F-program, PLCSIM Advanced and the Windows writer stay off the
  runner. `VirtualFPLC` is the stand-in this job is allowed (ADR 0011's
  stand-in posture, Linux loopback).
- Simulation stays Gazebo (invariant 12). There is no MuJoCo job.
- Evidence that is a recorded run still lives in `PROOF.md`. CI does
  not close an M-gate.

Consequences:

Harder:
- A PR that breaks a pure function cannot hide behind "I'll run the
  cell later". The pytest job is the merge door.
- The required check is *weaker* than the owner's rig until a
  headless Gazebo job lands. `pytest-ros` covers the VDA agent
  against a real broker and a real rclpy context; it does not start
  the 39-process cell.
- Branch protection and the merge queue are owner actions in the
  GitHub UI; the workflow file cannot turn them on by itself.

Easier:
- Every PR gets the same 569 tests natively, the VDA-agent MQTT
  suite in the Jazzy job, the same invariant grep and the same
  hygiene hooks, with JUnit on the run.
- The fleet/ROS boundary becomes a failing check instead of a README
  sentence.
- Nodes import ROS through one module (`ros_optional.py`), so a
  missing overlay is a skipped integration test, not a collection
  error.

Alternatives:

- Copy `robotics_cicd`'s Humble + colcon + MuJoCo pipeline onto this
  tree. Rejected: invariant 12, ADR 0003, and the "plain Python, no
  colcon package" working agreement. The sister repo is the source of
  the *discipline*, not of the Dockerfile.
- Make the required check a headless `m6.sh start`. Rejected for the
  first gate: no GitHub-hosted runner has the GPU, the 39 processes
  and the Windows writer, and a red check that cannot go green is not
  a gate. It is a later phase, on a self-hosted or larger runner, with
  its own flake budget.
- Lazy-import `rclpy` in every IPC node so the native job collects
  all 38 test modules. Landed as `m6/ipc/ros_optional.py`: the
  overlay is optional at import, required at `main()`.
