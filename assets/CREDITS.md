# assets — provenance

Every image in this directory was produced from this repository or from
permissively licensed sources. No vendor marketing material is used.

| File | Origin |
|---|---|
| `plc-drives-cell.gif` | Screen capture of `sim/worlds/cell.sdf` in Gazebo Harmonic, driven live by the S7-1500 standard program on PLCSIM Advanced. |
| `demo-cell.png` | Screen capture of `sim/worlds/cell.sdf` in Gazebo Harmonic. |
| `teleop-showcase.gif` | Owner's own screen recording of the live teleoperation (2026-07-30): a 15 s highlight excerpt, re-encoded and cropped with `ffmpeg`; the crop removes the Windows taskbar. No third-party content. |
| `teleop-showcase.mp4` | Owner's own screen recording of the live teleoperation (2026-07-30): the full run, re-encoded and cropped with `ffmpeg`; the crop removes the Windows taskbar. No third-party content. |
| `m5-forklift/*.png` | Gazebo Harmonic GUI screen captures of `sim/worlds/forklift_arena.sdf` with `agv/forklift/model.sdf` spawned (2026-07-30), taken through `gz sim -g` under `xvfb-run` on a software (llvmpipe) renderer. Camera placed via the `/gui/move_to/pose` service, frames written by the `/gui/screenshot` service. The beams are drawn by the world's own `VisualizeLidar` GUI plugin — no substitute renderer, no post-processing. Both models are this repository's own work. |
