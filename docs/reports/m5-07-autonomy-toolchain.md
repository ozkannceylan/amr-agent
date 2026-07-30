# Report m5-07 — ROS 2 / Gazebo / autonomy toolchain in the session container

```
brief:               docs/briefs/m5-07-autonomy-toolchain.md
status:              done
files_changed:       [sim/setup/install.sh,
                      sim/setup/CONTAINER_TOOLCHAIN.md (new)]
invariants_touched:  none
open_questions:      see below
next_suggested:      a sim brief to re-point sim/launch/forklift_bringup.launch.py
                     at the three-scanner topic set, once agv/forklift/README.md
                     has settled the contract
```

## Result

The container had no ROS at all (`/opt/ros` absent, zero `ros-jazzy` packages).
It now runs the M5 stack. Versions, all quoted from the command that printed
them, are in `sim/setup/CONTAINER_TOOLCHAIN.md` §3; the headline ones:

- `gz sim --versions` -> `8.11.0` (Gazebo Harmonic)
- `ros-jazzy-ros-base 0.11.0-1noble.20260616.084325`
- `ros-jazzy-gz-sim-vendor 0.0.10-1noble.20260604.111001`
- `ros-jazzy-ros-gz 1.0.22-1noble.20260616.074726`
- `ros-jazzy-navigation2 1.3.12-1noble.20260615.181551`
- `ros-jazzy-nav2-bringup 1.3.12-1noble.20260616.082701`
- `ros-jazzy-slam-toolbox 2.8.5-1noble.20260615.161600`
- `rmw_fastrtps_cpp`, `/usr/bin/python3` -> `Python 3.12.3`

Nothing was unavailable and nothing is blocked. Footprint: 0.64 GB downloaded,
`du -sh /opt/ros/jazzy` -> `643M`, disk `7.3G` used before to `11G` after.
`ros-jazzy-ros-base` was used rather than `desktop-full`.

Verification run, against `sim/worlds/forklift_arena.sdf` and
`agv/forklift/model.sdf` at md5 `42e99e0847af67a39ccfd94bcb06329e` (the blob
committed as `4b623c1`), with `GZ_PARTITION` and `ROS_DOMAIN_ID` both set:

- `gz sim -s -r` ran the arena headless at `real_time_factor:
  1.0004482007939557`
- all three scan topics reached ROS 2 through `ros_gz_bridge` at `average
  rate:` `10.009`, `10.004`, `9.983`; `/clock` at `500.517`
- `ros2 topic echo --full-length` captured complete messages: 360, 275 and 275
  ranges, matching the model's `<samples>`. No sample count was changed.
- `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, read from
  `/root/.gz/rendering/ogre2.log`, which was deleted before the run. Software
  rasterisation, as expected and as on the owner's WSL host.
- `slam_toolbox`, `controller_server`, `amcl` and `planner_server` all start
  and register; `slam_toolbox` was additionally confirmed with `ros2 node info`.

`sim/setup/CONTAINER_TOOLCHAIN.md` states in its first section that this is
CONTAINER evidence, that the owner's WSL host is a separate environment to be
re-verified on its own terms, and that both sets are kept.

## install.sh changes

Updated where it disagreed with what actually worked (detail in
`CONTAINER_TOOLCHAIN.md` §5):

1. `ros-jazzy-slam-toolbox` added to `ROS_PKGS`.
2. The RB-KAIROS steps 4-6 (Robotnik clone, closed-source controller debs,
   colcon build) are now opt-in behind `ROBOTNIK=1`, off by default. That
   platform was retired by ADR 0010 D1 and none of it was installed here.
3. The five `ros2_control` packages moved to the same opt-in block, with a
   note to add them back to `ROS_PKGS` and re-verify if a later gate needs
   them rather than switching the flag on.
4. A warning for a `python3` shadow (below).
5. The header's "what M5 needs is decided at briefing" replaced by a pointer
   to the evidence file; the proxy note records both hops re-verified.

Re-run after editing: still idempotent, installs nothing on a second pass,
LF endings, pure ASCII.

## Open questions

1. **`sim/launch/forklift_bringup.launch.py` is stale and fails silently.** It
   bridges `/forklift/gz/scan`, the M4 single-scanner name. m5-04 replaced
   that sensor with `scan_safety_front`, `scan_safety_rear` and `scan_nav`, so
   the launch file now spawns cleanly, creates every bridge, logs no error and
   carries no scan data. I did not fix it: the topic contract lives in
   `agv/forklift/README.md`, which m5-04 owns, and the brief forbids editing
   `agv/`. This needs a sim brief once that contract is settled. Verified both
   ways — the same launch file carried `/forklift/scan` at `average rate:
   9.997` against the pre-m5-04 model.
2. **`/usr/local/bin/python3` -> `/usr/bin/python3.11` shadows the 3.12
   alternative.** ROS is unaffected (its console scripts carry an absolute
   `#!/usr/bin/python3`), but a bare `python3 -c 'import rclpy'` fails with a
   misleading missing-C-extension error. `install.sh` now warns rather than
   repointing, because `/usr/local/bin` is not this project's to own and other
   tooling in the image may want 3.11. Should the project claim that symlink?
   That is a container-policy call, not a sim one.
3. **Rear scanner may be looking into the vehicle.** On
   `/forklift/gz/scan_safety_rear`, 46 of 93 finite returns are under 0.5 m in
   one contiguous band (indices 9 to 65, `0.427` down to `0.164` m); neither
   other scanner has a single return under 0.5 m. That is the signature of
   self-occlusion. It may be correct for the mounting. Passed to `agv/`,
   not acted on.
4. **Nothing installed for `ros2_control`.** If M5 routes Nav2 `cmd_vel` into
   the forklift through `gz_ros2_control` rather than the existing gz joint
   controller plugins and vehicle node, four packages need adding to
   `ROS_PKGS` and the toolchain re-verified.

## Concurrency note

`agv/forklift/model.sdf` was rewritten by m5-04 four times during this work
and committed as `4b623c1` mid-run. I did not edit it. The recorded run is the
one taken after the commit, with the file verified byte-identical at the start
and the end of the run; the earlier runs are kept in `CONTAINER_TOOLCHAIN.md`
§7 because they are what established open question 1. Nothing was committed by
this brief.
