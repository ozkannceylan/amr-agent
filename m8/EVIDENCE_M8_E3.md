# EVIDENCE_M8_E3 — abort classifier vs staged faults

Status: **NOT_RUN** (attempt 2026-09-11: **BLOCKED**, plant absent on the execution host; see the last section). Needs the m5-ver3 plant and `bench/faults/` injection
against live `pallet_cam` frames. This file contains no recall and no
false-abort rate.

## Standing cautions

Ground truth is a score, not a command. The instrument floor (rms
0.0291 m, MAX 0.1179 m) bounds any absolute claim. No PL / SIL / PFH
claims. The Nav2 collision monitor is not a safety function. The F-PLC
never receives M8 input. Frames never leave the truck.

## Bar (to be stated, not stated here)

Recall on the staged set and false-abort rate on clean cycles, both
named. `proceed` is never an M8 output.

## Result

NOT_RUN. `m8/bench/e3_abort.py` exits 2. No confusion counts.

## What is green offline

`m8_core/abort.py` names the five C2 reasons on synthetic buffers
(`pytest m8/tests/test_abort.py`). That is not a plant recall.

## Attempt 2026-09-11 — BLOCKED (plant absent)

Status: **BLOCKED / NOT_RUN**. Owner job of 2026-09-11 (Phase A, H1
minimum: E1 then E3) was started on branch `m5-ver3-close` at commit
`e312c3a` and stopped cleanly at step 1 (confirm GPU plant). The
execution host is a remote container (`vm`, Ubuntu 24.04, 4 vCPU, no
GPU device) and none of the plant's preconditions exist on it. No
bench was run against a plant; no score exists; nothing below is a
number this attempt produced.

Exact blockers, each probed on the host:

| precondition | probe | result |
|---|---|---|
| gz-sim 8.11 | `gz sim --version` | `gz: command not found` |
| ROS 2 (rclpy, ros_gz bridges) | `ls /opt/ros`; `python3 -c "import rclpy"` | no `/opt/ros`; `ModuleNotFoundError: No module named 'rclpy'` |
| NVIDIA GPU | `nvidia-smi`; `ls /dev/nvidia* /dev/dri` | `nvidia-smi: command not found`; no `/dev/nvidia*`, no `/dev/dri` |
| GPU preflight (`m5v3.sh start` → `gpu_preflight`) | `which glxinfo` | `glxinfo: command not found`; `config.yaml` requires the renderer string to contain `NVIDIA`, which cannot be satisfied on a host with no GPU device, so `start` would refuse before sourcing ROS |
| running plant | `bash m5_ver3/m5v3.sh status` | `not running (no pid file)`, exit 1 |

The m5-ver3 refusal is respected, not worked around: no llvmpipe or
software-rendered run was attempted, because a figure taken under it
would be a figure about a different machine wearing this rig's name
(`m5_ver3/config.yaml`, `gpu:` block).

What ran on this host, for the record:

- `python3 m8/bench/e3_abort.py` → prints `NOT_RUN`, exit 2 (unchanged stub).
- `python3 -m pytest m8/tests -q` → `79 passed` (offline suite at `e312c3a`;
  pytest and numpy were pip-installed into the container for this check).
  That is the same offline result as `EVIDENCE_A1_OFFLINE.md` and is not a
  plant score.

To unblock: run this bench on the rig that carries the D3D12 NVIDIA
adapter (`m5v3.sh start --headless ...` passes `gpu_preflight`), with
`warehouse_ver3` + `forklift_ver3` + `pallet_cam`. Until then this file
carries no measured number and H1 stays open.
