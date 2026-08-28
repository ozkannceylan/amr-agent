# CI/CD integration for amr-agent (design)

**Status:** Phase 1 lands with this spec. Later phases are sequenced,
not scheduled.

This is the translation of the sister portfolio
[`robotics_cicd`](https://github.com/ozkanceylan-dev/robotics_cicd)
(OtoNav: ROS 2 Humble + MuJoCo SIL, colcon, merge queue, GHCR) onto
this tree. The sister repo is a deliberately small robot wrapped in a
production pipeline. This repo is a production-shaped cell (safety PLC,
four forklifts, VDA 5050) with no pipeline. The work is to give the
cell the pipeline, not to give the pipeline a second robot.

## What transfers, and what does not

| OtoNav practice | Transfers? | Why |
|---|---|---|
| Protected `main`, PR-only, required checks | yes | The integration-engineer problem is identical |
| Native merge queue | yes, later | Needs a required check that is already green |
| pre-commit (hygiene, not a formatter war) | yes | 5 live files; archives excluded |
| `colcon build` + ament lint + gtest | **no** | Not a colcon workspace; plain Python (`m5_ver2/CLAUDE.md`) |
| Humble container | **no** | ADR 0003 pins Jazzy |
| MuJoCo cached SDK + `gui:=false` SIL | **no** | Invariant 12: simulation is Gazebo |
| FastDDS localhost / loopback profile | already here | `m6/tools/fastdds_loopback.xml`; CI does not start DDS in Phase 1 |
| JUnit upload + rosbag-on-failure | JUnit yes; rosbag later | No launch_testing scenario yet |
| Multi-stage Dockerfile, GHCR on tag | later | No shippable image; the cell is a WSL+Windows rig |
| Sim-time, no `sleep()` in tests | partial | MQTT integration tests still poll on wall clocks; they pass, they are slow (~35 s). Do not rewrite them in Phase 1 |
| CODEOWNERS + PR template | yes | Adapted to pytest / invariants / PROOF, not colcon |
| Conventional-commit titles as a gate | **no** | Current era uses prose subjects (`m6: ...`). Enforcing the archived template would fail every recent commit |

## The test pyramid, measured 2026-08-28

A clean Ubuntu 24.04 / Python 3.12 with `pytest`, `paho-mqtt`,
`python3-tk` and the vendored mosquitto, **without** `/opt/ros`:

| Outcome | Count | What |
|---|---|---|
| passed | **423** | Pure logic + stub MQTT + live mosquitto on :18884 + VirtualFPLC on loopback UDP |
| skipped | 1 | `test_vda_agent_mqtt.py` (`importorskip("rclpy")`) |
| collection errors | 9 files | Import `rclpy` at module level: `cmd_gate`, `cmd_mux`, `encoder_link`, `field_eval`, `follower` (via `field_eval`), `hmi_node`, `plc_link`, `sensor_link`, `vehicles_table` (via `field_eval`) |
| wall time | ~41 s | Dominated by `test_fleet_manager_mqtt.py` (9 tests, ~35 s, 3 consecutive green runs, no flake) |
| Gazebo tests | **0** | No test starts `gz sim` |
| Windows / PLCSIM tests | **0** | `test_m6_virtual_loop.py` is the stand-in, and it is in the 423 |

`m6.sh deploy` also runs without ROS and is **deterministic** across two
back-to-back runs (same `MANIFEST` hash once the date header is
ignored; the file hashes themselves match). `m6.sh start` is the rig
and is not a CI job in Phase 1.

## Phases (priority order)

The order is cost × diagnostic value, not calendar. Each phase is a
required check only after it has been green.

### Phase 1 - the door (this change)

Native GitHub-hosted runner, no ROS, no Gazebo, no Docker.

- `.github/workflows/ci.yml`: `pre-commit`, `invariants`, `pytest-m6`
- `m6/tests/conftest.py` omits the 9 ROS-bound files when `rclpy`
  cannot be imported
- `m6/tools/check_layer_boundaries.py` fails the PR if `m6/fleet/`
  grows an `rclpy` import or if `vda_orders.py` grows a third-party
  import
- pre-commit hygiene, CODEOWNERS, PR template, CI badge
- floor: pytest must pass at least 400 tests (measured 423)

Done when a PR that breaks `vda_orders.validate_order` is red, and a
PR that only edits `m6/PROOF.md` is green.

### Phase 2 - the omitted files

Two independent options; both are allowed, either is enough:

- **2a.** Lazy-import `rclpy` inside `main()` of the eight IPC/HMI
  modules so their pure functions collect on a native runner. Must be
  proven against `m6.sh start` on the owner's rig (import side-effects
  are how several nodes currently bind DDS).
- **2b.** A `ros:jazzy-ros-base` container job that sources
  `/opt/ros/jazzy/setup.bash` and runs the full suite, including
  `test_vda_agent_mqtt.py`. Needs `rclpy` + message packages in the
  image. No Gazebo in this job.

Done when the 9 omitted files and the VDA agent MQTT test are a
required check.

### Phase 3 - the image (optional, after 2)

A Jazzy + pytest + mosquitto image on GHCR, tagged on `v*.*.*`, so
the job that ran in CI is the environment someone can `docker run`
locally. This is OtoNav ADR-5 adapted: the image is a **test
environment**, not a vehicle image. Vehicle deploy remains
`m6.sh deploy` (ADR 0016).

Do not start this before Phase 2 has a reason to cache an image.
Building Gazebo Harmonic into GitHub-hosted storage is a cost decision
of its own.

### Phase 4 - headless SIL

A launch-style scenario that does **not** close an M-gate:

- `m6.sh deploy && m6.sh start --headless` on a runner that can hold
  39 processes (self-hosted, or a larger GitHub runner)
- `tools/preflight.sh` as the pass/fail (topic hz, not a video)
- RTF reported, never gated above the 0.30 floor
  (`docs/superpowers/specs/2026-08-25-rig-independent-criteria.md`)
- on failure: upload `m6/logs/` as an artifact (OtoNav's rosbag analogue)

The Windows writer is still the owner's. Scripted UDP
(`tools/scripted_writer.py` + `VirtualFPLC`) can stand in on Linux
for the PLC half of a SIL, the same way `test_m6_virtual_loop.py`
already does.

This phase is last because it is the first one that can flake on the
host, and a flaky required check is worse than no check.

### Phase 5 - merge queue + branch protection

Owner actions in the GitHub UI, after Phase 1 has been green:

- `main` protected: no direct push, required reviewers, required
  checks = the three Phase 1 jobs
- native merge queue so a PR is re-tested against the `main` it will
  actually land on (OtoNav ADR-6)

## Explicitly out of scope

- Closing M7 / M8. CI is not a milestone gate.
- Enforcing the archived conventional-commit template on new commits.
- Running TIA Portal, PLCSIM Advanced, or TwinCAT in CI.
- Reformatting 294 Python files.
- Putting secrets, broker passwords or tailnet keys in Actions
  (invariant 13). The vendored mosquitto is local and anonymous, which
  is the M6 posture.

## Acceptance for Phase 1

1. `python3 -m pytest m6/tests/ -q` on a machine without ROS reports
   no failures, no collection errors, and at least 400 passed.
2. `python3 m6/tools/check_layer_boundaries.py` exits 0 on `main` and
   exits 1 if `import rclpy` is added to `m6/fleet/fleet_manager.py`.
3. The workflow file is the only runner definition; versions of
   pytest / paho are pinned in `m6/requirements-ci.txt`.
4. Historical trees (`docs/archive/`, `m1/`-`m5/`, `PROOF.md`) are
   excluded from pre-commit rewrites.
