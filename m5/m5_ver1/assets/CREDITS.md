# assets — provenance

Every image in this directory was produced from this repository or from
permissively licensed sources. No vendor marketing material is used.

| File | Origin |
|---|---|
| `m5-forklift/*.png` | Gazebo Harmonic GUI screen captures of `sim/worlds/forklift_arena.sdf` with `agv/forklift/model.sdf` spawned (2026-07-30), taken through `gz sim -g` under `xvfb-run` on a software (llvmpipe) renderer. Camera placed via the `/gui/move_to/pose` service, frames written by the `/gui/screenshot` service. The beams are drawn by the world's own `VisualizeLidar` GUI plugin — no substitute renderer, no post-processing. Both models are this repository's own work. |
| `hmi/*.png` | Screenshots of the first build's HMI (`hmi/hmi_server.py`), 2026-08-05/06 — staged scenarios (v2a) and live against the real service (v2b). |
| `demo_m5.mp4` | The first build's 4 min 9 s demonstration recording (local only, gitignored; published at https://youtu.be/wl1rgWyX66s). |

The M3-era cell captures (`demo-cell.png`, `plc-drives-cell.gif`) moved to
[`../../../m3/assets/`](../../../m3/) and the M4 teleop showcase to
[`../../../m4/assets/`](../../../m4/) when the milestone archives were
created (2026-08-22); their provenance entries moved with them.
