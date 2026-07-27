# WSL environment for the M3 toolchain

## 1. Purpose and scope

This document records what happened when the M3 toolchain was rebuilt from
`sim/setup/install.sh` inside **WSL2 Ubuntu 24.04 on this machine**, on
2026-07-27. It documents the WSL path **only**. It does not supersede the
container path in `sim/README.md`, which remains the reference recipe and the
environment all committed M3 evidence (`sim/worlds/CELL_EVIDENCE.md`,
`bridge/EVIDENCE_LATENCY.md`, `bridge/EVIDENCE_SIGNAL_LOSS.md`) was captured
in. Every command below was executed by the author and its real output is
quoted. The toolchain needed for the M3 demonstration cell — ROS 2 Jazzy,
Gazebo Harmonic and asyncua 2.0.1 — is installed and verified here. The
ros2_control and Nav2 packages from `install.sh` are still absent; they belong
to the deferred M5 vehicle work and the cell does not use them (§3.1).

## 2. Verified environment table

| Component | Expected (container) | Observed (WSL) | Status |
|---|---|---|---|
| Distro | Ubuntu 24.04 noble | `Ubuntu 24.04.4 LTS (noble)` | match |
| Kernel | container kernel | `5.15.167.4-microsoft-standard-WSL2` | WSL2 |
| python3 | 3.12.3 | `Python 3.12.3` | match |
| `/usr/bin/python3` target | python3.12 (via update-alternatives) | `/usr/bin/python3.12` | already correct, no alternatives step needed |
| ROS 2 | Jazzy | `/opt/ros/jazzy`, `ros-jazzy-ros-base 0.11.0-1noble.20260126.203129` | present |
| RMW | rmw_fastrtps_cpp | `middleware name    : rmw_fastrtps_cpp` | match |
| Gazebo | Harmonic (gz sim 8) via `ros-jazzy-gz-sim-vendor` | `Gazebo Sim, version 8.11.0` | match |
| `gz` binary location | system-wide `/usr/bin/gz` | `/opt/ros/jazzy/opt/gz_tools_vendor/bin/gz` | **deviation, see §4.1** |
| `ros-jazzy-gz-sim-vendor` | installed | `0.0.10-1noble.20260604.111001` | match |
| `ros-jazzy-ros-gz` | installed | `1.0.22-1noble.20260616.074726` | match |
| Render backend | ogre2 on llvmpipe (container) | ogre2 on `llvmpipe (LLVM 20.1.2, 256 bits)` | match, see §4.7 |
| Headless RTF (cell) | ~1.0 | `0.99984`, `0.99994` | match |
| ros2_control stack | installed | **MISSING** | not needed for the M3 cell (M5 work) |
| Nav2 | installed | **MISSING** | not needed for the M3 cell (M5 work) |
| asyncua | 2.0.1 | `2.0.1` | match |
| cryptography | 49.0.0 | `49.0.0` | match |
| pyOpenSSL | 26.3.0 | `26.3.0` | match |
| venv | `/opt/amr-bridge-venv` | `/home/ozkan/amr-bridge-venv` | **deviation, see §3.2** |
| CPU / RAM | — | 20 cores, 15 GiB | — |
| `/dev/shm` | — | 7.8 G, tmpfs, writable | ok |

Package survey against the `ROS_PKGS` list in `install.sh`:

```
OK   ros-jazzy-ros-base  0.11.0-1noble.20260126.203129
OK   ros-jazzy-xacro  2.1.1-1noble.20260519.011123
OK   ros-jazzy-robot-state-publisher  3.3.3-3noble.20260126.180730
MISS ros-jazzy-joint-state-publisher
OK   ros-jazzy-gz-sim-vendor  0.0.10-1noble.20260604.111001
OK   ros-jazzy-ros-gz  1.0.22-1noble.20260616.074726
MISS ros-jazzy-ros2-control
MISS ros-jazzy-gz-ros2-control
MISS ros-jazzy-controller-manager
MISS ros-jazzy-joint-state-broadcaster
MISS ros-jazzy-joint-trajectory-controller
MISS ros-jazzy-navigation2
MISS ros-jazzy-nav2-bringup
OK   python3-colcon-common-extensions  0.3.0-100
OK   python3-rosdep  0.26.0-1
MISS python3-vcstool
OK   git  1:2.43.0-1ubuntu7.3
OK   python3.12-venv  3.12.3-1ubuntu0.15
OK   python3-yaml  6.0.1-2build2
```

The ROS 2 apt source and key are already in place, so `install.sh` §2 is a
no-op here:

```
/etc/apt/sources.list.d/ros2.list:deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main
-rw-r--r-- 1 root root 1167 Feb 26 20:42 /usr/share/keyrings/ros-archive-keyring.gpg
```

The remaining packages are all available from that source.

## 3. Step-by-step setup

### 3.0 Line endings — fixed, no operator action needed

Historically the first thing a WSL operator hit: the working tree was checked
out CRLF and `install.sh` would not run. That is now fixed in the repository by
a root `.gitattributes` (commit `7d3ee4c`). Verified here:

```
$ file -b sim/setup/install.sh
Bourne-Again shell script, ASCII text executable
$ grep -c $'\r' sim/setup/install.sh
0
$ bash -n sim/setup/install.sh && echo "SYNTAX OK"
SYNTAX OK
$ ./sim/setup/install.sh
Run as root (sudo).
```

WSL-side `git status` is clean again — the phantom whole-tree modification is
gone:

```
$ git status --porcelain | grep -c '^ M'
1
```

(the one remaining entry is unrelated in-flight work by another agent). The
full diagnosis is kept in §4.8 because the failure mode is worth recognising if
it ever recurs on a fresh clone.

The script's own preconditions pass on this system:

```
readlink -f /usr/bin/python3 : /usr/bin/python3.12
python3.12 present          : /usr/bin/python3.12
VERSION_CODENAME            : noble
```

so the `update-alternatives` block in `install.sh` §1 is a no-op — the
python3.11-default quirk is a container artifact and does not exist in WSL.

### 3.1 The apt step — COMPLETED by the owner

`apt` needs elevation, and this environment has no passwordless sudo:

```
$ sudo -n true
sudo: a password is required
```

The owner ran the elevated install. For the **M3 demonstration cell only**, the
Robotnik workspace (`install.sh` §4–§6) is not required — `sim/README.md`
states the cell needs only `/opt/ros/jazzy`, and
`sim/launch/cell_bringup.launch.py` references only `ros_gz_sim` and
`ros_gz_bridge`:

```
101:        get_package_share_directory('ros_gz_sim'), 'launch', 'gz_sim.launch.py')
125:        package='ros_gz_bridge',
126:        executable='parameter_bridge',
```

so the minimum elevated command for the cell is:

```
sudo apt-get update && sudo apt-get install -y ros-jazzy-gz-sim-vendor ros-jazzy-ros-gz
```

The ros2_control and Nav2 entries in the `install.sh` package list remain
uninstalled. That is deliberate: they belong to the deferred M5 vehicle work
(`sim/scenarios/DEFERRED.md`), and nothing in the M3 cell loads them.

### 3.2 Python venv and asyncua — COMPLETED

`/opt` is not writable without sudo:

```
touch: cannot touch '/opt/.writetest': Permission denied
/opt NOT writable by ozkan
```

so the venv was created at `$HOME/amr-bridge-venv` instead of the documented
`/opt/amr-bridge-venv`. **This is a deviation**: it is a stand-in that proves
the dependency set resolves on this machine, not a replacement for the
documented path. When the owner runs the elevated step, the venv should be
recreated at `/opt/amr-bridge-venv` so `bridge/README.md` stays literally true.

```
$ python3 -m venv --system-site-packages $HOME/amr-bridge-venv
$ $HOME/amr-bridge-venv/bin/python --version
Python 3.12.3
$ $HOME/amr-bridge-venv/bin/pip --version
pip 24.0 from /home/ozkan/amr-bridge-venv/lib/python3.12/site-packages/pip (python 3.12)
$ $HOME/amr-bridge-venv/bin/pip install -r bridge/requirements.txt
  Attempting uninstall: cryptography
    Found existing installation: cryptography 41.0.7
    Not uninstalling cryptography at /usr/lib/python3/dist-packages, outside environment /home/ozkan/amr-bridge-venv
    Can't uninstall 'cryptography'. No files were found to uninstall.
Successfully installed aiosqlite-0.22.1 anyio-4.14.2 asyncua-2.0.1 cffi-2.1.0 cryptography-49.0.0 pycparser-3.0 pyopenssl-26.3.0 sortedcontainers-2.4.0
```

The `--system-site-packages` + venv approach behaves in WSL exactly as
`bridge/requirements.txt` records for the container: pip declines to remove
Debian's `cryptography 41.0.7` and installs 49.0.0 inside the venv instead.
The resolved transitive set matches the versions recorded in
`requirements.txt` exactly:

```
aiosqlite        0.22.1
anyio            4.14.2
asyncua          2.0.1
cffi             2.1.0
cryptography     49.0.0
pycparser        3.0
pyOpenSSL        26.3.0
sortedcontainers 2.4.0
```

### 3.3 Interpreter unification — COMPLETED

One interpreter, one command, ROS 2 sourced:

```
$ source /opt/ros/jazzy/setup.bash && $HOME/amr-bridge-venv/bin/python -c "..."
interpreter : /home/ozkan/amr-bridge-venv/bin/python
python      : 3.12.3
rclpy       : /opt/ros/jazzy/lib/python3.12/site-packages/rclpy/__init__.py
asyncua     : 2.0.1 /home/ozkan/amr-bridge-venv/lib/python3.12/site-packages/asyncua/__init__.py
cryptography: 49.0.0
std_msgs/sensor_msgs/rosgraph_msgs/geometry_msgs: OK
PyYAML      : 6.0.1
```

The bridge package itself imports from the `/mnt/c` checkout:

```
bridge package imports from /mnt/c: OK
```

Gazebo Python bindings are **not** part of this requirement: a grep over
`bridge/` and `sim/` for `import gz` returns nothing. The project uses the
`gz` CLI and `ros_gz_bridge`, never the Python bindings, so "all three import
in one interpreter" reduces to rclpy + asyncua, which is proven above.

## 4. WSL-specific findings

### 4.1 Gazebo Harmonic — INSTALLED, but `gz` is only on PATH after sourcing ROS 2

Version, observed:

```
$ gz sim --version
Gazebo Sim, version 8.11.0
Copyright (C) 2018 Open Source Robotics Foundation.
Released under the Apache 2.0 License.
```

**The WSL-specific trap is where the binary lives.** Because Harmonic comes
from the ROS vendor packages rather than from
`packages.osrfoundation.org`, there is no `/usr/bin/gz`, and `gz` does not
exist on PATH until `/opt/ros/jazzy/setup.bash` is sourced:

```
=== BEFORE sourcing ROS 2 ===
gz NOT on PATH before sourcing

=== AFTER sourcing /opt/ros/jazzy/setup.bash ===
which gz : /opt/ros/jazzy/opt/gz_tools_vendor/bin/gz
```

There is no system-wide Harmonic to fall back on:

```
$ ls -l /usr/bin/gz
(no /usr/bin/gz -> no system-wide Harmonic)
$ dpkg -s gz-harmonic
gz-harmonic deb installed? : no
$ grep -rs "packages.osrfoundation.org" /etc/apt/sources.list.d/
(no osrfoundation apt source)
```

Consequence for anyone following this document or writing a script against it:
**every shell that runs `gz` must source `/opt/ros/jazzy/setup.bash` first**, and
a bare `gz` in a systemd unit, cron job or non-login shell will fail with
"command not found" rather than with a Gazebo error. This differs from most
Gazebo Harmonic documentation, which assumes the osrfoundation packages and a
system-wide `/usr/bin/gz`.

The vendor package set backing it:

```
OK   ros-jazzy-gz-sim-vendor    0.0.10-1noble.20260604.111001
OK   ros-jazzy-gz-tools-vendor  0.0.7-1noble.20260225.231255
OK   ros-jazzy-ros-gz           1.0.22-1noble.20260616.074726
OK   ros-jazzy-ros-gz-sim       1.0.22-1noble.20260615.173223
OK   ros-jazzy-ros-gz-bridge    1.0.22-1noble.20260615.142443
```

### 4.2 Interpreter unification — RESOLVED, no WSL deviation

No WSL-specific behaviour observed. The venv path differs only because `/opt`
needs root (§3.2). asyncua resolved to the target 2.0.1.

### 4.3 DDS discovery under WSL2 — WORKS BY DEFAULT, no configuration needed

This was the finding most expected to bite, and it did not. WSL2's NAT'd
adapter did not break discovery between two processes in the same distro.

Interfaces observed:

```
lo               UNKNOWN        127.0.0.1/8 10.255.255.254/32 ::1/128
eth0             UP             172.19.180.72/20 fe80::215:5dff:fe61:1346/64
docker0          DOWN           172.17.0.1/16
```

Multicast is functional on `eth0`:

```
$ ros2 multicast send / ros2 multicast receive
Sending one UDP multicast datagram...
Waiting for UDP multicast datagram...
Received from 172.19.180.72:54678: 'Hello World!'
```

A publisher and a subscriber in two separate processes were then run under
four configurations. Each case published `/wsl_probe` at 5 Hz and read one
message with a 12 s timeout:

```
----- CASE: default (no env overrides) -----          RESULT: RECEIVED (rc=0)
----- CASE: ROS_DOMAIN_ID=42 -----                    RESULT: RECEIVED (rc=0)
----- CASE: ROS_LOCALHOST_ONLY=1 -----                RESULT: RECEIVED (rc=0)
----- CASE: ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST - RESULT: RECEIVED (rc=0)
```

Resolution: **no XML profile, no `ROS_LOCALHOST_ONLY`, no custom
`ROS_DOMAIN_ID` is required.** The environment default is already
`ROS_AUTOMATIC_DISCOVERY_RANGE=SUBNET` with `rmw_fastrtps_cpp`. Note that
`ROS_LOCALHOST_ONLY=1` still works but logs a deprecation:

```
[WARN] [rcl]: ROS_LOCALHOST_ONLY is deprecated but still honored if it is enabled.
              Use ROS_AUTOMATIC_DISCOVERY_RANGE and ROS_STATIC_PEERS instead.
```

so it should not be added to any launch or doc. Caveat: this was tested between
two plain `ros2` CLI processes. The full runtime topology — Gazebo server plus
`ros_gz_bridge` plus the bridge process — is m3-08's to exercise. Note that
Gazebo's own transport does **not** use DDS or `ROS_DOMAIN_ID`; it is isolated
with `GZ_PARTITION` instead, which is what the §4.7 runs used to stay clear of
a concurrent simulation.

### 4.4 /dev/shm — ADEQUATE, but segments are not cleaned up on exit

```
none on /dev/shm type tmpfs (rw,nosuid,nodev,noatime)
none            7.8G  8.0K  7.8G   1% /dev/shm
/dev/shm writable: yes
```

7.8 G is ample for Fast DDS shared-memory transport, and it is writable by the
unprivileged user.

Symptom worth knowing: after the four DDS cases above exited **cleanly**,
16 shared-memory objects were left behind:

```
-rw-r--r-- 1 ozkan ozkan 549408 Jul 27 11:18 fastrtps_1d6c4bda623691c8
-rw-r--r-- 1 ozkan ozkan  52400 Jul 27 11:18 fastrtps_port17915
-rw-r--r-- 1 ozkan ozkan     32 Jul 27 11:18 sem.fastrtps_port17915_mutex
... (16 objects total)
```

They are small (~1.3 MB total here) and Fast DDS reuses them, so this is
housekeeping rather than a fault. Resolution applied — safe **only when no ROS
2 process is running**:

```
$ rm -f /dev/shm/fastrtps_* /dev/shm/sem.fastrtps_*
after cleanup: 0
```

Recommendation for m3-08: clear these between measurement runs so a stale
segment from a previous run cannot influence a latency capture.

### 4.5 Clock source — MONOTONIC IS SANE, REALTIME IS NOT. This one matters.

`CLOCK_MONOTONIC` is trustworthy:

```
clocksource: tsc
available:   tsc hyperv_clocksource_tsc_page
monotonic res (ns): 1.0
2.000 s sleep -> monotonic delta 2.000069  realtime delta 2.000072
monotonic regressions over 200000 reads: 0
```

`CLOCK_REALTIME` is **not**. Sampling `CLOCK_REALTIME - CLOCK_MONOTONIC` once
a second for 100 s shows a staircase: the wall clock jumps forward ~2.728 s
every ~30 s and never comes back.

```
t=  0s  offset-drift +0.000000 s
t=  4s  offset-drift +2.727836 s
   ...
t= 34s  offset-drift +5.455645 s
   ...
t= 64s  offset-drift +8.184643 s
   ...
t= 94s  offset-drift +10.913343 s
```

Over 100 s the wall clock gained 10.91 s. Root cause, evidenced in three
places. First, two time masters are fighting. `systemd-timesyncd` is active
(WSL runs systemd here, `/etc/wsl.conf` has `systemd=true`) and polls every
32 s, and it thinks the local clock is ~5 s slow:

```
PollIntervalUSec=32s
ServerName=ntp.ubuntu.com
NTPMessage={ ... OriginateTimestamp=Mon 2026-07-27 11:22:02 CEST,
             ReceiveTimestamp=Mon 2026-07-27 11:22:07 CEST,
             TransmitTimestamp=Mon 2026-07-27 11:22:07 CEST,
             DestinationTimestamp=Mon 2026-07-27 11:22:02 CEST, ... }
```

Second, the kernel is being slewed hard — `tick` is 9166 µs against a nominal
10000, an 8.3 % rate correction:

```
adjtimex return : 0 TIME_OK
freq (ppm*65536): 2827962 -> 43.151275634765625 ppm
tick (us)       : 9166 (nominal 10000)
```

Third, and this is the actual origin: **the Windows Time service on the host
is stopped**, so the host clock the WSL guest is periodically re-synced to is
itself wrong and free-running:

```
$ w32tm /query /status
The following error occurred: The service has not been started. (0x80070426)
$ w32tm /query /source
The following error occurred: The service has not been started. (0x80070426)
```

Measured directly, the WSL guest is seconds ahead of the Windows host, and the
gap grows:

```
11:19  WIN_before=09:19:30.193Z  WSL=09:19:34.053Z  WIN_after=09:19:30.455Z   (+3.7 s)
11:24  WIN_before=09:24:46.785Z  WSL=09:24:51.542Z  WIN_after=09:24:47.047Z   (+4.6 s)
```

**What this means for m3-08's latency evidence.** The good news: the bridge
never timestamps with the wall clock. Every latency timestamp in the bridge is
`time.monotonic_ns()`:

```
bridge/amr_bridge/ros_side.py:98:        recv_ns = time.monotonic_ns()
bridge/amr_bridge/opcua_side.py:178:        start = time.monotonic_ns()
bridge/amr_bridge/opcua_side.py:184:        end = time.monotonic_ns()
bridge/amr_bridge/opcua_side.py:358:        cycle_start = time.monotonic_ns()
bridge/amr_bridge/instrumentation.py:63:        now = time.monotonic()
```

and the only non-monotonic source is ROS sim time from `/clock`
(`ros_side.py:149: now = self.get_clock().now().nanoseconds`). So
**intra-process latency figures measured in WSL are trustworthy despite this
defect.** Two things are not:

1. Any wall-clock timestamp used to *date* an evidence file will be wrong by
   seconds and drifting.
2. Any comparison of a bridge-side timestamp against a **PLCSIM Advanced**
   timestamp. PLCSIM runs on the Windows host, whose clock is currently
   several seconds off the guest's and unsynchronised. Since the M3 gate
   closes against PLCSIM Advanced, this must be fixed before that run.

Resolution: not applied — starting the Windows Time service needs
administrator rights. Recommended owner action before m3-08:
`Start-Service w32time; w32tm /resync` in an elevated Windows shell, then
confirm the guest/host gap is under a millisecond.

### 4.6 Filesystem — `/mnt/c` is usable for this workload, with one caveat

The repo is on a 9p DrvFs mount, without the `metadata` option:

```
/dev/sde on / type ext4 (rw,relatime,discard,errors=remount-ro,data=ordered)
C:\ on /mnt/c type 9p (rw,noatime,dirsync,aname=drvfs;path=C:\;uid=1000;gid=1000;
                       symlinkroot=/mnt/,mmap,access=client,msize=65536,trans=fd,rfd=5,wfd=5)
```

Measured, not assumed:

| Operation | NATIVE ext4 (`~`) | DrvFs (`/mnt/c`) | Ratio |
|---|---|---|---|
| create 500 small files | 0.0116 s | 1.2020 s | 104x slower |
| stat 500 files | 0.0069 s | 0.1815 s | 26x slower |
| delete 500 files | 0.0044 s | 0.5522 s | 125x slower |
| sequential write 256 MB + fsync | 0.157 s (1.7 GB/s) | 1.439 s (187 MB/s) | 9x slower |
| CSV append + flush **per row**, 5000 rows | 0.004 s (0.8 µs/row) | 0.617 s (123.3 µs/row) | 154x slower |
| CSV append **batched**, 20 flushes x 140 rows | 0.0014 s (0.07 ms/flush) | 0.0850 s (4.25 ms/flush) | 61x slower |

The per-row figure is the alarming one, but it is **not** the pattern the
bridge uses. `bridge/amr_bridge/instrumentation.py` buffers rows and writes
them in one batched `open`/`writerows` every 2 s:

```
32:    def __init__(self, path: str, flush_interval_s: float = 2.0) -> None:
62:    def maybe_flush(self, force: bool = False) -> None:
64:        if not force and (now - self._last_flush) < self.flush_interval_s:
71:        with open(self.path, "a", newline="", encoding="utf-8") as handle:
72:            csv.writer(handle).writerows(rows)
```

At the measured 4.25 ms per batched flush once every 2 s, evidence recording
costs about **0.2 % of wall time** on DrvFs. Against a 50 ms bridge cycle a
single 4.25 ms flush is an 8.5 % perturbation of the one cycle it lands in,
which is visible but bounded and happens once per 40 cycles.

**Conclusion: a native ext4 path is not required for m3-08.** Running the
cell and the bridge from `/mnt/c/Users/ozkan/projects/amr-agent` is
acceptable: the runtime workload is a handful of Python source files read
once, one SDF read once, and a periodic batched CSV append. Python source
imports and world loading are not metadata-heavy in the way a `colcon build`
is.

Two qualifications, offered as findings rather than changes:

1. If a future gate builds a colcon workspace, do **not** put it on `/mnt/c` —
   the 104x small-file penalty is exactly what a build hits. `install.sh`
   already places the Robotnik workspace at `/opt/m3-feasibility/ws`, which is
   native ext4, so this is already correct.
2. If m3-08 wants the tightest possible latency distribution, pointing
   `evidence.csv_path` at a native path (e.g. `~/amr-evidence/`) and copying
   the CSV into the repo afterwards removes the 4.25 ms flush spikes entirely.
   This is an option, not a necessity.

Separately, the configured evidence path is a container path that does not
exist here:

```
bridge/config/bridge.yaml:95:  csv_path: "/home/user/amr-agent/bridge/evidence/latency-2026-07-27.csv"
$ ls -l /home/user/amr-agent/bridge/evidence/
ls: cannot access '/home/user/amr-agent/bridge/evidence/': No such file or directory
```

m3-08 will need `--evidence-csv` or a config change. Flagged, not changed —
`bridge/` is outside this brief's write access.

### 4.7 Graphics — headless works, RTF ~1.0, and WSLg does NOT give you a GPU

WSLg is running, contrary to the "must run headless" assumption:

```
DISPLAY=:0  WAYLAND_DISPLAY=wayland-0
/mnt/wslg
  PulseAudioRDPSink  PulseServer  distro  doc  runtime-dir  versions.txt
/tmp/.X11-unix/:
srwxrwxrwx 1 ozkan ozkan 0 Jul 27 10:18 X0
```

A DRI device is exposed, so hardware-accelerated rendering is at least
possible here — unlike the container, which fell back to llvmpipe:

```
$ ls /dev/dri
by-path  card0  renderD128
```

`sim/launch/cell_bringup.launch.py` starts the server only, so it should not
need a display at all:

```
107:            'gz_args': ['-r -s ', world],
119:        condition=IfCondition(gui),
```

The open risk was that the cell's photo-eye is a `gpu_lidar`, which needs a
rendering context inside the *server* process even with `-s`. It was tested
directly: `gz sim -s -r -v 4 sim/worlds/cell.sdf` was run for 30 s under five
configurations, isolated from any concurrent simulation with
`ROS_DOMAIN_ID=77` and `GZ_PARTITION=m307probe`.

| Config | DISPLAY | Extra | Result | GL_RENDERER |
|---|---|---|---|---|
| A | `:0` (WSLg) | — | works | `llvmpipe (LLVM 20.1.2, 256 bits)` |
| B | unset | — | works | `llvmpipe (LLVM 20.1.2, 256 bits)` |
| C | unset | `LIBGL_ALWAYS_SOFTWARE=1` | **SEGFAULT** | — |
| D | `:0` (WSLg) | `--headless-rendering` | works | `llvmpipe (LLVM 20.1.2, 256 bits)` |
| E | unset | — | works | `llvmpipe (LLVM 20.1.2, 256 bits)` |

**Answer 1: headless genuinely works, and the `gpu_lidar` renders.** In every
non-crashing case a real scan was received:

```
photo-eye sample : RECEIVED (gpu_lidar rendered)
```

with the expected frame:

```
    key: "frame_id"
    value: "ProductSensor::post::beam"
```

**Answer 2: real-time factor is ~1.0**, matching the container and far better
than the ~0.1 the warehouse world managed there:

```
D: real_time_factor: 0.99984002559590468
E: real_time_factor: 0.99994150342204979
```

**Answer 3: WSLg's presence changes the code path but buys nothing.** Despite
`/dev/dri/card0` existing, and despite OGRE successfully enumerating and
binding it via EGL —

```
Found Num EGL Devices: 2
EGL Device: EGL_EXT_device_drm ... #0 /dev/dri/card0
Created GL 4.5 context for device EGL_EXT_device_drm ... #0 /dev/dri/card0
```

— Mesa then falls back to software rasterisation:

```
libEGL warning: egl: failed to create dri2 screen
libEGL warning: NEEDS EXTENSION: falling back to kms_swrast
GL_VERSION = 4.5 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2
GL_VENDOR = Mesa
GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)
GPU Vendor: unknown
```

So the container's llvmpipe path is effectively reproduced. **No rendering
result here should be attributed to GPU acceleration**, and no future
performance difference between this machine and the container should be
explained by "WSL has a GPU" — measured, it does not.

What DISPLAY actually changes is which windowing path OGRE tries first. With
DISPLAY set it takes GLX and attaches to WSLg's X server. With DISPLAY unset it
throws, and Gazebo catches it and proceeds:

```
OGRE EXCEPTION(3:RenderingAPIException): Couldn`t open X display  in
  GLXGLSupport::getGLDisplay at .../OgreGLXGLSupport.cpp (line 808)
[Wrn] [Ogre2RenderEngine.cc:551] Unable to open display: . Trying to run in headless mode.
```

Both end on llvmpipe with identical RTF, so this is cosmetic — but it means a
log full of X-display exceptions is *normal* for a headless run here and is not
a fault to chase.

**Answer 4: what a reader must set to force headless.** Either works:

```
# preferred — explicit, no X exceptions in the log
gz sim -s --headless-rendering -r <world>

# equivalent — what a CI/systemd context gets for free
env -u DISPLAY -u WAYLAND_DISPLAY gz sim -s -r <world>
```

`-s` alone is *not* sufficient to avoid touching the X server: config A shows
`-s` still opening a GLX connection when DISPLAY is set. It is harmless here,
but `--headless-rendering` is the honest flag.

**Do not set `LIBGL_ALWAYS_SOFTWARE=1`.** With DISPLAY unset it makes Mesa
refuse the already-selected EGL device and Gazebo dies:

```
libEGL warning: Not allowed to force software rendering when API explicitly selects a hardware device.
#8    Object ".../RenderSystem_GL3Plus.so", ... in Ogre::GL3PlusPlugin::install(...)
Segmentation fault
```

Crash attribution, confirmed by log inspection rather than by inference:

```
case A: crash-trace lines=0   'Rendering Thread initialized'=1
case B: crash-trace lines=0   'Rendering Thread initialized'=1
case C: crash-trace lines=2   'Rendering Thread initialized'=0
```

The variable is pointless anyway — rendering is already software.

### 4.8 Line endings — CRLF checkout broke shell scripts (RESOLVED, `7d3ee4c`)

Not in the brief's investigation list, but it blocked step one. Kept here
because the failure mode is easy to misdiagnose if it recurs on a fresh clone
or a machine whose Git lacks the repository's `.gitattributes`.

Symptom: `install.sh` will not parse or execute (§3.0). The cause is the
checkout, not the file. The blob in git is clean:

```
$ git show HEAD:sim/setup/install.sh | file -b -
Bourne-Again shell script, ASCII text executable
$ git show HEAD:sim/setup/install.sh | grep -c $'\r'
0
$ grep -c $'\r' sim/setup/install.sh      # working tree
160
```

Windows Git's system config forces the conversion, and the repo has no
`.gitattributes` to override it:

```
$ grep -iA1 autocrlf "/mnt/c/Program Files/Git/etc/gitconfig"
	autocrlf = true
$ cat .gitattributes
(no .gitattributes at repo root)
$ git config --get core.autocrlf     # WSL-side git
core.autocrlf: (unset)
```

The whole tree is affected — 1 shell script and 17 Python files:

```
CRLF: ./sim/setup/install.sh (160 lines)
CRLF: ./bridge/amr_bridge/opcua_side.py (403 lines)
CRLF: ./sim/launch/cell_bringup.launch.py (133 lines)
CRLF: ./sim/scenarios/run_scenario.py (310 lines)
... (17 .py files total)
```

What actually breaks and what does not, tested:

| Artifact | CRLF effect |
|---|---|
| `install.sh` via shebang | **BREAKS** — `/usr/bin/env: 'bash\r': No such file or directory` |
| `install.sh` via `bash -n` | **BREAKS** — `syntax error near unexpected token $'do\r'` |
| `.py` source | fine — `cell_bringup.launch.py compiles despite CRLF: OK`, `opcua_side.py compiles despite CRLF: OK` (Python universal newlines) |
| `bridge.yaml` | fine — `bridge.yaml parses despite CRLF: OK, top keys = ['opcua', 'nodes', 'ros', 'cycle', 'evidence', 'logging']` |

Second-order effect, and the more dangerous one: WSL-side git has
`core.autocrlf` unset, so from inside WSL **every tracked file reads as
modified**, while Windows-side git reports the same tree clean. Any `git`
command run from WSL risks committing a whole-repo line-ending churn.

```
$ git status --porcelain | head
 M .claude/settings.json
 M .gitignore
 M CLAUDE.md
 M agv/README.md
 M bridge/EVIDENCE_LATENCY.md
 ...
```

Resolution: **none applied, deliberately.** `install.sh` was *not* edited —
its committed content is already correct, and rewriting it would fix nothing
durably because the next checkout re-applies CRLF. The correct fix is a
`.gitattributes` at the repo root. That file now exists (commit `7d3ee4c`) and
the symptom is gone; see §3.0 for the verification.

## 5. Known-unresolved

1. **The venv is at `/home/ozkan/amr-bridge-venv`, not `/opt/amr-bridge-venv`.**
   Every other document says `/opt`, which needs root. Either recreate it at
   `/opt/amr-bridge-venv` with the elevated shell, or `bridge/README.md` is
   wrong on this machine. Unchanged — `bridge/` is outside this brief's write
   access.
2. **`bridge/config/bridge.yaml` still points at a container path** for its
   evidence file:

   ```
   bridge/config/bridge.yaml:95:  csv_path: "/home/user/amr-agent/bridge/evidence/latency-2026-07-27.csv"
   $ ls -l /home/user/amr-agent/bridge/evidence/
   ls: cannot access '/home/user/amr-agent/bridge/evidence/': No such file or directory
   ```

   m3-08 needs `--evidence-csv` or a config change. Flagged, not changed.
3. **Clock: diagnosed, not fixed.** The Windows Time service is stopped and the
   guest wall clock steps ~2.73 s every 30 s (§4.5). The bridge timestamps with
   `time.monotonic_ns()`, so intra-process latency is unaffected — but any
   WSL-to-PLCSIM-Advanced timestamp correlation is meaningless until the owner
   runs an elevated `Start-Service w32time; w32tm /resync`. This is the one
   open item that can silently corrupt M3 gate evidence.
4. **DDS was proven only between two `ros2` CLI processes** (§4.3). The full
   runtime topology — gz server, `ros_gz_bridge`, bridge process — belongs to
   m3-08.
5. **`sim/worlds/cell.sdf` is not strict-XML parseable, but Gazebo does not
   care.** Its header comment contains an ASCII-art diagram with `--`
   sequences, which XML forbids inside comments, so `xml.etree` rejects it:

   ```
   $ python3 -c "import xml.etree.ElementTree as ET; ET.parse('sim/worlds/cell.sdf')"
   xml.etree.ElementTree.ParseError: not well-formed (invalid token): line 15, column 8
   ```

   Confirmed as a comment-syntax issue with a minimal case:
   `<r><!-- a b c --><x/></r>` parses, `<r><!-- a --- b --><x/></r>` is
   `REJECTED`. **Now settled in practice**: the §4.7 runs loaded this exact
   file five times without complaint —

   ```
   [Msg] Loading SDF world file[/mnt/c/Users/ozkan/projects/amr-agent/sim/worlds/cell.sdf].
   ```

   — because libsdformat uses TinyXML2, which permits it. Recorded only so the
   `xml.etree` failure is not rediscovered and mistaken for file corruption.
   Any *tooling* the project writes that parses SDF with `xml.etree` will need
   the comment cleaned up first; nothing does today.
