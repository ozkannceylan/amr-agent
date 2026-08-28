# CI/CD integration - implementation plan

Companion to
[`docs/superpowers/specs/2026-08-28-ci-cd-integration-design.md`](../specs/2026-08-28-ci-cd-integration-design.md)
and [ADR 0017](../../adr/0017-ci-as-the-integration-gate.md).

## Phase 1 (this change)

| Path | What |
|---|---|
| [docs/adr/0017-ci-as-the-integration-gate.md](../../adr/0017-ci-as-the-integration-gate.md) | The decision |
| `.github/workflows/ci.yml` | four jobs: pre-commit, invariants, pytest-m6, pytest-ros |
| `.github/PULL_REQUEST_TEMPLATE.md` | evidence checklist against this repo, not colcon |
| `.github/CODEOWNERS` | `@ozkannceylan` on `/` , `.github/`, `m6/`, `docs/adr/` |
| `.pre-commit-config.yaml` | hygiene hooks; archives excluded |
| `m6/requirements-ci.txt` | pinned pytest + paho-mqtt |
| `m6/ipc/ros_optional.py` | overlay optional at import; required at `main()` |
| `m6/tools/check_layer_boundaries.py` | fleet must not import ROS; `vda_orders.py` stdlib-only |
| root README | CI badge + one CI paragraph |

Owner follow-up, not in git: Settings → Branches → protect `main`,
tick the three jobs as required checks. Merge queue after that.

## Phase 2 (landed on this PR after Phase 1 went green)

Both 2a and 2b:

- 2a. `m6/ipc/ros_optional.py` — IPC/HMI nodes import ROS types
  through one module. Overlay optional at import, required at
  `main()`. Native suite: **569 passed, 1 skipped**. Floor 550.
- 2b. `pytest-ros` job: `container: ros:jazzy-ros-base`, loopback
  FastDDS, full suite including `test_vda_agent_mqtt.py`. Floor 570.

Owner follow-up, not in git: Settings → Branches → protect `main`,
tick **pre-commit**, **invariants**, **pytest-m6**, **pytest-ros**.
Merge queue after that (Phase 5).

## Phase 3+

See the spec. Do not start a Dockerfile until Phase 2 has a container
worth caching. Do not start a Gazebo job until a runner exists that
can hold 39 processes without starving the scans.

## Done-when for this PR

- Four jobs exist and the native equivalent is green:
  `pre-commit run --all-files`,
  `python3 m6/tools/check_layer_boundaries.py`,
  `python3 -m pytest m6/tests/ -q` ≥ 550 passed, 0 failed, 0 errors.
- `pytest-ros` is green on GitHub (Jazzy image; not reproducible
  in this cloud VM).
- A deliberately illegal `import rclpy` in `m6/fleet/` is caught by
  the checker (proven once, then reverted).
