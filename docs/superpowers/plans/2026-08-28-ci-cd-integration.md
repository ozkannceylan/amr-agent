# CI/CD integration - implementation plan

Companion to
[`docs/superpowers/specs/2026-08-28-ci-cd-integration-design.md`](../specs/2026-08-28-ci-cd-integration-design.md)
and [ADR 0017](../../adr/0017-ci-as-the-integration-gate.md).

## Phase 1 (this change)

| Path | What |
|---|---|
| [docs/adr/0017-ci-as-the-integration-gate.md](../../adr/0017-ci-as-the-integration-gate.md) | The decision |
| `.github/workflows/ci.yml` | three jobs: pre-commit, invariants, pytest-m6 |
| `.github/PULL_REQUEST_TEMPLATE.md` | evidence checklist against this repo, not colcon |
| `.github/CODEOWNERS` | `@ozkannceylan` on `/` , `.github/`, `m6/`, `docs/adr/` |
| `.pre-commit-config.yaml` | hygiene hooks; archives excluded |
| `m6/requirements-ci.txt` | pinned pytest + paho-mqtt |
| `m6/tests/conftest.py` | omit ROS-bound test modules when `rclpy` is missing |
| `m6/tools/check_layer_boundaries.py` | fleet must not import ROS; `vda_orders.py` stdlib-only |
| root README | CI badge + one CI paragraph |

Owner follow-up, not in git: Settings → Branches → protect `main`,
tick the three jobs as required checks. Merge queue after that.

## Phase 2 (next PR, after Phase 1 is required)

Pick 2a, 2b, or both:

- 2a. Move `import rclpy` in `m6/ipc/{cmd_gate,cmd_mux,encoder_link,field_eval,plc_link,sensor_link,nav_node,vda_agent}.py` and `m6/hmi/hmi_node.py` to inside `main()` / the node class. Re-run `m6.sh start` on the rig. Drop the nine-file `collect_ignore` list.
- 2b. Add `pytest-ros` job: `container: ros:jazzy-ros-base`, install `python3-pytest python3-paho-mqtt python3-tk ros-jazzy-rclpy` + message packages, `source /opt/ros/jazzy/setup.bash`, full suite including `test_vda_agent_mqtt.py`. Timeout 15 minutes.

## Phase 3+

See the spec. Do not start a Dockerfile until Phase 2 has a container
worth caching. Do not start a Gazebo job until a runner exists that
can hold 39 processes without starving the scans.

## Done-when for this PR

- The three jobs exist and the local equivalent is green:
  `pre-commit run --all-files`,
  `python3 m6/tools/check_layer_boundaries.py`,
  `python3 -m pytest m6/tests/ -q` ≥ 400 passed, 0 failed, 0 errors.
- A deliberately illegal `import rclpy` in `m6/fleet/` is caught by
  the checker (proven once, then reverted).
