# Container toolchain for the M5 autonomy stack

## 1. Purpose and scope

This document records the installation and verification of the M5 autonomy
toolchain — ROS 2 Jazzy, Gazebo Harmonic, `ros_gz`, Nav2 and `slam_toolbox` —
inside the **session container**, on 2026-07-30, from brief
`docs/briefs/m5-07-autonomy-toolchain.md`.

**This is CONTAINER evidence.** It is not evidence about the owner's machine.
The owner's WSL2 host is a separate environment with its own record in
`sim/setup/WSL_ENVIRONMENT.md`, and at the time that file was written it had
ROS 2 Jazzy and Gazebo Harmonic but **no** Nav2 and **no** `slam_toolbox`.
Nothing here changes that. Both sets are kept; neither replaces the other, and
the WSL host must be re-verified on its own terms before any M5 demonstration
runs there (LESSONS 2026-07-27, "evidence is qualified by the environment that
produced it").

Every version and measurement below is quoted from the output of the command
named beside it. No number in this file was computed by hand.

## 2. Host

| Item | Observed |
|---|---|
| Distro | `Ubuntu 24.04.4 LTS` (noble), amd64 |
| Kernel | `Linux 6.18.5 x86_64` |
| CPU / RAM | `nproc` = 4, `free -g` total = 15 GiB |
| Disk before install | `/dev/vda 252G 7.3G 30G 20% /` |
| Disk after install | `/dev/vda 252G 11G 27G 30% /` |
| ROS tree footprint | `du -sh /opt/ros/jazzy` -> `643M` |
| apt download | 690063936 bytes (0.64 GB), summed from `apt-get install --print-uris` |
| `ros-jazzy-*` packages installed | `dpkg -l \| grep -c '^ii  ros-jazzy'` -> `336` |

The container had **no ROS at all** at the start of the brief: `/opt/ros` did
not exist and `dpkg -l | grep -c ros-jazzy` returned `0`.

## 3. Versions, exactly as the tools printed them

### 3.1 Simulator

`gz sim --versions` (after `source /opt/ros/jazzy/setup.bash`):

```
8.11.0
```

That is Gazebo Harmonic. The `gz` binary is **not** in `/usr/bin`; `which gz`
returns `/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz`, so it reaches PATH only
after sourcing ROS — the same deviation already recorded for WSL in
`WSL_ENVIRONMENT.md` §4.1.

### 3.2 Package versions

From `dpkg-query -W -f='${Version}'`:

| Package | Version |
|---|---|
| `ros-jazzy-ros-base` | `0.11.0-1noble.20260616.084325` |
| `ros-jazzy-ros-core` | `0.11.0-1noble.20260615.174419` |
| `ros-jazzy-rclcpp` | `28.1.21-1noble.20260615.133124` |
| `ros-jazzy-rclpy` | `7.1.11-1noble.20260615.133206` |
| `ros-jazzy-rmw-fastrtps-cpp` | `8.4.4-1noble.20260615.124621` |
| `ros-jazzy-gz-sim-vendor` | `0.0.10-1noble.20260604.111001` |
| `ros-jazzy-gz-tools-vendor` | `0.0.7-1noble.20260225.231255` |
| `ros-jazzy-gz-ogre-next-vendor` | `0.0.5-1noble.20260225.232146` |
| `ros-jazzy-ros-gz` | `1.0.22-1noble.20260616.074726` |
| `ros-jazzy-ros-gz-sim` | `1.0.22-1noble.20260615.173223` |
| `ros-jazzy-ros-gz-bridge` | `1.0.22-1noble.20260615.142443` |
| `ros-jazzy-ros-gz-interfaces` | `1.0.22-1noble.20260615.112415` |
| `ros-jazzy-ros-gz-image` | `1.0.22-1noble.20260615.145009` |
| `ros-jazzy-navigation2` | `1.3.12-1noble.20260615.181551` |
| `ros-jazzy-nav2-bringup` | `1.3.12-1noble.20260616.082701` |
| `ros-jazzy-slam-toolbox` | `2.8.5-1noble.20260615.161600` |
| `ros-jazzy-xacro` | `2.1.1-1noble.20260519.011123` |
| `ros-jazzy-robot-state-publisher` | `3.3.4-1noble.20260615.150609` |
| `ros-jazzy-joint-state-publisher` | `2.4.1-1noble.20260615.140100` |
| `python3-colcon-common-extensions` | `0.3.0-100` |
| `python3-rosdep` | `0.26.0-1` |
| `python3-vcstool` | `0.3.0-1` |

Nothing on the brief's list was unavailable. `ros-jazzy-slam-toolbox` and the
two Nav2 packages, which `install.sh` listed but which had never been
installed anywhere in this project, all resolved from
`packages.ros.org/ros2/ubuntu noble main` and installed without incident.

`ros2 doctor --report`, MIDDLEWARE section:

```
middleware name    : rmw_fastrtps_cpp
```

### 3.3 Python

`python3 --version` via `/usr/bin/python3` -> `Python 3.12.3`.

The container ships `python3.11` as the selected `python3` alternative;
`install.sh` step 1 switches the alternative to 3.12, which succeeded.

There is a second, separate shadow that step 1 does not address and now warns
about: **`/usr/local/bin/python3` is a symlink to `/usr/bin/python3.11`** and
comes earlier on PATH than `/usr/bin`. So `python3 -c 'import rclpy'` in an
interactive shell fails with

```
ModuleNotFoundError: No module named 'rclpy._rclpy_pybind11'
The C extension '/opt/ros/jazzy/lib/python3.12/site-packages/_rclpy_pybind11.cpython-311-x86_64-linux-gnu.so' isn't present on the system.
```

while `/usr/bin/python3 -c 'import rclpy'` prints `rclpy import OK on 3.12.3`.

This does **not** affect ROS 2 itself. Every console script ROS installs
carries an absolute shebang — `head -1 /opt/ros/jazzy/bin/ros2` is
`#!/usr/bin/python3` — so `ros2`, `ros2 launch` and every launch file resolve
3.12 regardless of PATH. `ros2 pkg list` returned 327 packages and the whole
verification run below executed through those scripts.

`install.sh` warns rather than repointing `/usr/local/bin/python3`: that path
is not this project's to own, and other tooling in the image may depend on
3.11. **Rule for M5 Python work in this container: invoke `/usr/bin/python3`
explicitly, or run through `ros2 run` / `ros2 launch`.**

## 4. Verification run

### 4.1 What was run

> **Two topic names in section 4 no longer exist, and section 4 is not
> rewritten to hide it.** This run was taken on 2026-07-30 against the model as
> brief m5-04 left it. Brief m5-06 then split the safety scanners' measurement
> channel and renamed both topics:
>
> | as recorded in §4.1, §4.4, §4.5, §7 | the name since m5-06 |
> |---|---|
> | `/forklift/gz/scan_safety_front` | `/forklift/gz/safety_scanner_front/measurement` |
> | `/forklift/gz/scan_safety_rear` | `/forklift/gz/safety_scanner_rear/measurement` |
>
> `/forklift/gz/scan_nav` is unchanged. The commands below are kept verbatim
> because they are the record of what produced the figures; **do not copy them
> as a recipe** — §6.2 and §8 carry commands that work against the current
> model. The contract is `agv/forklift/README.md` in every case.

```
export GZ_PARTITION=m507evidence ROS_DOMAIN_ID=77 QT_QPA_PLATFORM=offscreen
gz sim -s -r sim/worlds/forklift_arena.sdf                     # headless
ros2 run ros_gz_sim create -world forklift_arena \
    -file agv/forklift/model.sdf -name Forklift \
    -x -6.00 -y 0.00 -z 0.05 -Y 0.0 -allow_renaming false
ros2 run ros_gz_bridge parameter_bridge \
    /clock@rosgraph_msgs/msg/Clock[gz.msgs.Clock \
    /forklift/gz/scan_nav@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan \
    /forklift/gz/scan_safety_front@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan \
    /forklift/gz/scan_safety_rear@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan
```

Both transports are isolated, not one: `ROS_DOMAIN_ID` does not isolate gz,
because gz transport is not DDS (LESSONS 2026-07-27). `GZ_PARTITION` is the
one that does, and both were set for every run in this document.

The scan topics were **discovered from the running server** with `gz topic -l`
rather than assumed, and the bridge argument list was generated from that
output. This matters: the run below is not against the topic names in
`sim/launch/forklift_bringup.launch.py`, which at the time of this run were
still the M4 single-scanner names (see §6.1; §6.2 records the fix and its
verification).

`sim/launch/forklift_bringup.launch.py` was not edited for this run and no
file owned by another agent was touched.

### 4.2 Fixed inputs of the recorded run

| Input | Value |
|---|---|
| Run window (UTC) | `2026-07-30T21:26:16Z` to `2026-07-30T21:29:25Z` |
| `sim/worlds/forklift_arena.sdf` | md5 `1e3d8d41a3481c20d71b1468a14b5c88` |
| `agv/forklift/model.sdf` | md5 `42e99e0847af67a39ccfd94bcb06329e` |
| model.sdf provenance | identical to the blob at commit `4b623c1`, "feat(agv): add the diagonal safety scanner pair and the navigation lidar" |
| model.sdf md5 at end of run | `42e99e0847af67a39ccfd94bcb06329e` (unchanged) |

The model was under concurrent edit by brief m5-04 during this work; §7
records the timing. The run above is the one taken after that edit landed and
was committed, with the file verified byte-identical at the start and the end
of the run.

### 4.3 Result: the arena runs headless

`gz sim -s -r` started and reached a live server 2 s after launch. Real time
factor from `gz topic -e -t /stats`:

```
sim_time { sec: 96 nsec: 46000000 }
real_time { sec: 100 nsec: 257040928 }
iterations: 48023
real_time_factor: 1.0004482007939557
step_size { nsec: 2000000 }
```

Real time at the world's 2 ms fixed step, with three `gpu_lidar` sensors
rendering, on four cores and software rasterisation.

### 4.4 Result: the scans reach ROS 2

`ros2 topic list` with the bridge running:

```
/clock
/forklift/gz/scan_nav
/forklift/gz/scan_safety_front
/forklift/gz/scan_safety_rear
/parameter_events
/rosout
```

`ros2 topic hz`, first reported window of each:

| Topic | `average rate` | min / max | window |
|---|---|---|---|
| `/forklift/gz/scan_nav` | `10.009` | `0.097s` / `0.103s` | 11 |
| `/forklift/gz/scan_safety_front` | `10.004` | `0.099s` / `0.102s` | 12 |
| `/forklift/gz/scan_safety_rear` | `9.983` | `0.098s` / `0.101s` | 11 |
| `/clock` | `500.517` | — | — |

All three scanners are declared at `<update_rate>10</update_rate>` in the
model and all three arrive at 10 Hz through the bridge. `/clock` arrives at
the world's 500 Hz physics rate.

### 4.5 Captured `ros2 topic echo` sample

`ros2 topic echo /forklift/gz/scan_safety_front --once --full-length`, header
and the first returns:

```
header:
  stamp:
    sec: 76
    nanosec: 400000000
  frame_id: safety_scanner_front_link
angle_min: -2.399827718734741
angle_max: 2.399827718734741
angle_increment: 0.01751699112355709
time_increment: 0.0
scan_time: 0.0
range_min: 0.10000000149011612
range_max: 5.5
ranges:
- .inf
...
```

Full-message shape of all three, counted from the untruncated captures:

| Topic | `frame_id` | ranges | intensities | finite returns | `range_max` |
|---|---|---|---|---|---|
| `/forklift/gz/scan_nav` | `nav_lidar_link` | 360 | 360 | 14 | `8.0` |
| `/forklift/gz/scan_safety_front` | `safety_scanner_front_link` | 275 | 275 | 46 | `5.5` |
| `/forklift/gz/scan_safety_rear` | `safety_scanner_rear_link` | 275 | 275 | 93 | `5.5` |

The `ranges` counts match the `<samples>` values in `model.sdf` (360, 275,
275). No sensor sample count was changed by this brief.

**`ros2 topic echo` truncates arrays at 128 elements by default**, printing
`- '...'` as element 129. A capture taken without `--full-length` therefore
shows 129 entries for a 181- or 275-ray scan and looks like a wrong sample
count. Every array figure in the table above comes from a `--full-length`
capture; the truncation flag was checked programmatically and is `no` for all
three.

### 4.6 GL_RENDERER, read from the ogre2 log

Read from `/root/.gz/rendering/ogre2.log`, which was deleted before the run so
the lines below belong to it and to no earlier one:

```
21:26:21: GL_VERSION = 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2
21:26:21: GL_VENDOR = Mesa
21:26:21: GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)
```

**`llvmpipe` — software rasterisation, no GPU.** This is read from the log,
not inferred (LESSONS 2026-07-27: the presence of a DRI node proves nothing).
It matches the owner's WSL host, which also reports `llvmpipe (LLVM 20.1.2,
256 bits)` (`WSL_ENVIRONMENT.md` §4.7), so the two environments are on the
same rendering path and the arena's deliberate cheapness — primitives only, no
mesh, no texture, no shadow — remains the right constraint.

The same log records two `Couldn't open X display` OGRE exceptions before the
GL context is created. They are expected under a headless run with no
`DISPLAY`; OGRE falls through to a 1x1 pbuffer window and continues, and the
run above achieved real time afterwards.

### 4.7 Autonomy nodes start

Each was run for 20 s under `timeout` against the live graph. Exit status
`124` means the process was still alive when the timeout fired, which is the
pass condition for a node with nothing to do.

| Command | Exit | First log line |
|---|---|---|
| `ros2 run slam_toolbox async_slam_toolbox_node` | 124 | (silent until SIGINT; node registration checked separately) |
| `ros2 run nav2_controller controller_server` | 124 | `controller_server lifecycle node launched.` |
| `ros2 run nav2_amcl amcl` | 124 | `amcl lifecycle node launched.` |
| `ros2 run nav2_planner planner_server` | 124 | `planner_server lifecycle node launched.` |

`slam_toolbox` logs nothing before activation, so staying alive is weak
evidence on its own. It was checked again in isolation: with the node running,
`ros2 node list` returned `/slam_toolbox` and `ros2 node info /slam_toolbox`
showed the lifecycle service set, including
`/slam_toolbox/change_state: lifecycle_msgs/srv/ChangeState` and
`/slam_toolbox/transition_event`. The node is real and unconfigured, which is
the correct state for a node nobody has transitioned.

None of these were configured or activated. This section proves the binaries
run and register on this box; it makes no claim about mapping or navigation
behaviour, which is later M5 work.

### 4.8 Teardown

After each run the process table was checked with `ps -eo pid,args` for
`gz sim`, `parameter_bridge`, `slam_toolbox`, `controller_server`, `amcl` and
`planner_server`, and reported clean.

Note for anyone repeating this: **`pgrep -f <pattern>` matches its own
invoking shell** when the pattern appears in the wrapper command line, so a
cleanup check written with `pgrep -f` reports processes that do not exist.
Match on `ps -eo pid,args --no-headers | grep -F ... | grep -v 'bash -c'`, and
match kill patterns against observed output — `gz sim -s -r` and `gz sim -r -s`
are the same run with different argument order (LESSONS 2026-07-27).

## 5. What `install.sh` now says that it did not before

Changed to match what actually worked:

1. `ros-jazzy-slam-toolbox` added to `ROS_PKGS`. It was named in the brief and
   in `WSL_ENVIRONMENT.md` as missing; it is now installed and pinned.
2. The retired platform's steps (4, 5, 6 — vendor clone, closed-source
   controller debs, colcon build) are **opt-in behind `ROBOTNIK=1` and off by
   default**. The platform was retired by ADR 0010 D1, none of it was
   installed for this verification, and a default-on script that clones five
   repositories and runs a colcon build did not describe the toolchain that
   was proven.
   **Superseded 2026-07-31 by m5-09:** those steps, the flag and the
   workspace variable were removed from `install.sh` entirely. A retired
   platform gets no installation path. The toolchain this file records is
   unaffected — none of it was installed for this verification either way.
3. The five `ros2_control` packages move to the same opt-in block. They were
   there for the vendor mecanum drive; the forklift drives through gz joint
   controller plugins and a vehicle node, and the verified container does not
   have them installed. A note says to add them back to `ROS_PKGS` and
   re-verify if a later gate needs them, rather than switching the flag on.
   **Superseded 2026-07-31 by m5-09:** the opt-in block is gone, so the five
   packages are simply absent from the script. The instruction is unchanged —
   add them to `ROS_PKGS` and re-verify if a later gate needs them.
4. A warning for the `/usr/local/bin/python3` shadow described in §3.3. It
   warns and does not repoint, because `/usr/local/bin` is not this project's
   to own.
5. The header's "what M5 needs installed is decided at M5 briefing, not by
   this script" is replaced by a pointer to this file. That question is closed.
6. The proxy note records that both hops were re-verified on 2026-07-30.

The script was re-run after editing and is still idempotent: it installs
nothing on a second pass, prints the shadow warning, and exits before step 4.

## 6. The launch file's topic names: gap found here, closed by m5-05b

### 6.1 The gap as this document first recorded it

`sim/launch/forklift_bringup.launch.py` bridged `/forklift/gz/scan`, the
single-scanner name. Brief m5-04 replaced that sensor with three, so the launch
file's bridge advertised a ROS topic that nothing published to.

This was observed directly. A run of that launch file against the new model
at 21:02 UTC came up clean, spawned the vehicle and created every bridge, and
no scan data ever arrived; the only signal was the absence of messages, with
no error from either side. Under the model as it stood before m5-04 landed,
the same launch file carried `/forklift/scan` at `average rate: 9.997`, so the
launch file itself was not broken — it was describing the previous sensor set.

The failure mode is worth stating plainly, because it is silent: a
`ros_gz_bridge` entry for a gz topic that nobody publishes logs
`Creating GZ->ROS Bridge` exactly as a working one does.

### 6.2 Closed, 2026-07-31, and verified in this container

Brief m5-05b rewrote `_BRIDGE_ARGS` against the contract table in
`agv/forklift/README.md`. The launch now bridges eight gz-side names, all of
which the running server advertises. Isolation `GZ_PARTITION=m505b_verify` /
`ROS_DOMAIN_ID=81` and `GZ_PARTITION=m505b_confirm` / `ROS_DOMAIN_ID=83`.

`ros2 topic list` with the launch running, in full:

```
/clock
/forklift/gz/fork_cmd
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd
/forklift/joint_states
/forklift/odom
/forklift/safety_scanner_front/measurement
/forklift/scan
/parameter_events
/rosout
```

`ros2 topic hz`, first reported window of each, quoted as the tool printed it:

| Topic | `average rate` | min / max | window |
|---|---|---|---|
| `/forklift/scan` | `9.995` | `0.098s` / `0.104s` | 12 |
| `/forklift/safety_scanner_front/measurement` | `10.001` | `0.098s` / `0.103s` | 11 |
| `/forklift/odom` | `19.998` | `0.049s` / `0.051s` | 22 |
| `/forklift/joint_states` | `500.055` | `0.000s` / `0.005s` | 501 |
| `/clock` | `500.191` | `0.000s` / `0.004s` | 501 |

`ros2 topic echo --once --full-length` on the two scan topics, shape counted
from the untruncated captures:

| ROS topic | `frame_id` | ranges | intensities | finite | `range_max` | `angle_min`/`angle_max` |
|---|---|---|---|---|---|---|
| `/forklift/scan` | `nav_lidar_link` | 360 | 360 | 14 | `8.0` | `-3.1415927410125732` / `3.1415927410125732` |
| `/forklift/safety_scanner_front/measurement` | `safety_scanner_front_link` | 275 | 275 | 46 | `5.5` | `-2.399827718734741` / `2.399827718734741` |

`/clock`, first message of a `ros2 topic echo /clock` capture:

```
clock:
  sec: 77
  nanosec: 294000000
---
```

The ROS-to-gz direction was checked too, because a command entry fails silently
in the same way: `ros2 topic pub -r 5 /forklift/gz/traction_cmd
std_msgs/msg/Float64 '{data: 3.0}'` produced `data: 3` on
`gz topic -e -t /forklift/gz/traction_cmd`, and `/forklift/odom` moved from
`x: -5.999999999999972` to `x: -1.6605650436960087`.

### 6.3 How the silent failure was checked for, not assumed away

Three checks, because "the topics are right now" is a claim about a running
server and not about a file:

1. **Every gz-side name in the file, cross-checked against the server.** The
   names were parsed out of `_BRIDGE_ARGS` and compared to `gz topic -l` on the
   live server, so a typo could not pass as a working entry:

   ```
   /clock                                               advertised
   /forklift/gz/steer_cmd                               advertised
   /forklift/gz/traction_cmd                            advertised
   /forklift/gz/fork_cmd                                advertised
   /forklift/gz/scan_nav                                advertised
   /forklift/gz/safety_scanner_front/measurement        advertised
   /forklift/gz/odom                                    advertised
   /forklift/gz/joint_state                             advertised
   declared: 8   not advertised: 0
   ```

2. **`ros2 topic hz` on every bridged ROS topic**, not a reading of the log.
   The launch log is not evidence: it prints `Creating GZ->ROS Bridge` for a
   dead entry exactly as for a live one.

3. **A negative control, run against the same live server.** A second
   `parameter_bridge` was started on the removed name, alone, so that its
   behaviour could be read without ambiguity:

   ```
   $ ros2 run ros_gz_bridge parameter_bridge \
       /forklift/gz/scan@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan
   [INFO] [ros_gz_bridge]: Creating GZ->ROS Bridge: [/forklift/gz/scan
     (gz.msgs.LaserScan) -> /forklift/gz/scan (sensor_msgs/msg/LaserScan)] (Lazy 0)

   $ ros2 topic hz /forklift/gz/scan
   WARNING: topic [/forklift/gz/scan] does not appear to be published yet

   $ ros2 topic echo /forklift/gz/scan --once
   (no output; exit status 124 — killed by timeout)
   ```

   Same INFO line as the eight working entries. No warning, no error, no data.
   That is the whole failure mode, reproduced deliberately beside the fix, so
   the fix is distinguishable from it rather than merely believed.

One discovery artifact worth knowing when reading a negative: the first
`ros2 topic hz /forklift/scan` of a run printed `WARNING: topic
[/forklift/scan] does not appear to be published yet` and then reported
`average rate: 9.736` in the same invocation. A warning at the start of a
window is not the silent failure — the silent failure prints the warning and
nothing after it.

## 7. Concurrency during this work

`agv/forklift/model.sdf` was being rewritten by brief m5-04 throughout. The
timeline, from `stat` and `md5sum` at each step:

| UTC | model.sdf md5 | Event |
|---|---|---|
| 19:44 | `eaff6bc...` | checkout state, one `safety_scanner`, topic `/forklift/gz/scan` |
| 20:59 | `eaff6bc...` | first run — launch file, `/forklift/scan` at 9.997 Hz, chain proven end to end |
| 21:01 | `d459b4d...` | m5-04's first write lands mid-work; three sensors, renamed topics |
| 21:02 | `d459b4d...` | second run finds no data: the launch file's `/forklift/gz/scan` no longer exists |
| 21:09-21:12 | `b814873...` then `f9face8...` | still being written; polled until md5 held steady for 60 s |
| 21:14-21:20 | `f9face8...` | runs against the settled file; all three scans confirmed publishing on the gz side and, once the poll allowed for discovery, flowing through the bridge into ROS 2 |
| 21:21 | `42e99e0...` | m5-04's final write, committed as `4b623c1` |
| 21:26-21:29 | `42e99e0...` | **the run recorded in §4**, against the committed blob, md5 unchanged start to end |

The §4 run is the one to cite. The earlier runs are kept in this section
because they are what established that the launch file had gone stale (§6.1).
The topic names in this table are the ones in force on 2026-07-30; two of them
were renamed the same day by m5-06, per the table at the head of §4.1.

An unrelated observation from §4.5, passed on rather than acted on: on
`/forklift/gz/scan_safety_rear` — now
`/forklift/gz/safety_scanner_rear/measurement` — 46 of the 93 finite returns are under 0.5 m
in one contiguous index band (indices 9 to 65, `0.427` down to `0.164` m),
while neither other scanner has a single return under 0.5 m. That pattern is
what a scanner looking into its own vehicle structure produces. It may be
correct for the rear scanner's mounting; it is `agv/`'s call, not this
brief's, and it is recorded here only so the observation is not lost.

## 8. Reproducing this

```
sudo sim/setup/install.sh                 # steps 0-3 only, ~0.64 GB download
source /opt/ros/jazzy/setup.bash
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<n>
gz sim -s -r sim/worlds/forklift_arena.sdf &
ros2 run ros_gz_sim create -world forklift_arena \
    -file agv/forklift/model.sdf -name Forklift -x -6.00 -y 0 -z 0.05 -Y 0
gz topic -l | grep scan                   # discover, do not assume
ros2 run ros_gz_bridge parameter_bridge <topic>@sensor_msgs/msg/LaserScan[gz.msgs.LaserScan &
sleep 10                                  # ROS discovery, see below
ros2 topic hz <topic>
ros2 topic echo <topic> --once --full-length
```

The whole bringup, which is what a scenario actually runs, is one command and
needs no topic list of its own — the launch file carries the current one and
§6.2 is its verification:

```
export GZ_PARTITION=<unique> ROS_DOMAIN_ID=<n>
ros2 launch sim/launch/forklift_bringup.launch.py            # headless
ros2 launch sim/launch/forklift_bringup.launch.py gui:=true  # with the GUI
```

Under `gui:=true` the beams are still not drawn until someone presses the
`Visualize lidar` refresh button and picks a scanner, and the entry that press
selects is the front safety scanner, not the navigation lidar
(`sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` §9.2).

Two traps, both hit during this work:

- **Poll after the bridge starts, not immediately.** A check begun in the same
  second as the bridge finds no publisher and returns nothing useful; a run
  whose poll started with no delay reported no data on topics that were
  demonstrably flowing 10 s later. Allow ~10 s for ROS 2 discovery before
  believing a negative.
- **`--full-length` on any echo whose array you intend to count**, per §4.5.
