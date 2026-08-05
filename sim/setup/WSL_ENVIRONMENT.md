# WSL environment — the owner's machine, as it is

Two parts, written at two dates, both still describing this one machine.

- **Part I (sections 1 to 5)** is the M3 toolchain record of 2026-07-27.
  Its WSL findings are still true and are the reason it is kept: where `gz`
  lives (§4.1), the clock (§4.5), the `/mnt/c` DrvFs cost (§4.6), that WSLg
  buys no GPU (§4.7), the line-ending trap (§4.8).
- **Part II (sections 6 to 13)** is the autonomy stack, installed
  2026-08-05 under brief m5-21. **It supersedes §2's two `MISSING` rows for
  Nav2 and `robot_localization`**, which are now installed system packages,
  and it is where the Fast-CDR collision that installing them exposed is
  written down.

---

# Part I — the M3 toolchain, 2026-07-27

## 1. Purpose and scope

This document records what happened when the M3 toolchain was rebuilt from
`sim/setup/install.sh` inside **WSL2 Ubuntu 24.04 on this machine**, on
2026-07-27. It documents the WSL path **only**. It does not supersede the
container path in `sim/README.md`, which remains the reference recipe and the
environment all committed M3 evidence (`sim/worlds/CELL_EVIDENCE.md`,
`bridge/EVIDENCE_LATENCY.md`, `bridge/EVIDENCE_SIGNAL_LOSS.md`) was captured
in. Every command below was executed by the author and its real output is
quoted. The toolchain needed for the M3 demonstration cell — ROS 2 Jazzy,
Gazebo Harmonic and asyncua 2.0.1 — is installed and verified here.

**As written on 2026-07-27**, the ros2_control and Nav2 packages from
`install.sh` were still absent; they belonged to the parked navigation
scenario and the cell does not use them (§3.1). Navigation work resumed at
M5 on the in-house forklift (`docs/roadmap.md`, ADR 0010), and **Part II
settles it: Nav2, `slam_toolbox` and `robot_localization` were installed on
2026-08-05.** The ros2_control five stayed out. Read every "not needed"
verdict below as a statement about the M3 cell on its own date.

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
| ros2_control stack | installed | **MISSING** | not needed for the M3 cell; retired with the M5 platform (`install.sh` note, ADR 0010 D1). The interface libraries Nav2's controllers depend on arrived with Part II; the five packages themselves are still absent |
| Nav2 | installed | **MISSING as of 2026-07-27; INSTALLED 2026-08-05** | `ros-jazzy-nav2-bringup` / `navigation2` **1.3.12**, see **Part II §10.1**. This row is superseded |
| `robot_localization` | (not surveyed) | **MISSING as of 2026-07-27; INSTALLED 2026-08-05** | **3.8.3**, see **Part II §10.1**. This row is superseded |
| asyncua | 2.0.1 | `2.0.1` | match |
| cryptography | 49.0.0 | `49.0.0` | match |
| pyOpenSSL | 26.3.0 | `26.3.0` | match |
| venv | `--system-site-packages` venv, container uses `/opt/amr-bridge-venv` | `/home/ozkan/amr-bridge-venv` | supported per-machine location, see §3.2 |
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
MISS ros-jazzy-navigation2                 <- INSTALLED 2026-08-05, Part II
MISS ros-jazzy-nav2-bringup                <- INSTALLED 2026-08-05, Part II
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

The owner ran the elevated install. For the **M3 demonstration cell only**, no
workspace beyond `/opt/ros/jazzy` is required — `sim/README.md` states the cell
needs only `/opt/ros/jazzy`, and
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
uninstalled. That is deliberate: they belong to the parked navigation scenario
(`sim/scenarios/DEFERRED.md`), and nothing in the M3 cell loads them. The M4
forklift arena does not load them either.

Under ADR 0010 that scenario's platform is retired: navigation work resumes at
**M5 on the in-house forklift**, with SLAM and Nav2 on that vehicle. The "not
needed" verdicts above are therefore statements about the M3 cell only.

**Settled 2026-08-05 (Part II).** Nav2, `slam_toolbox` and
`robot_localization` were installed; the five ros2_control packages were
not, because the forklift drives through gz joint-controller plugins and a
vehicle node rather than through `ros2_control` (`install.sh`, ADR 0010 D1).
The elevated route used was `wsl.exe -u root`, not `sudo` (§7).

### 3.2 Python venv and asyncua — COMPLETED

`/opt` is not writable without sudo:

```
touch: cannot touch '/opt/.writetest': Permission denied
/opt NOT writable by ozkan
```

so the venv was created at `$HOME/amr-bridge-venv` instead of the
`/opt/amr-bridge-venv` used in the container. This was originally recorded here
as a deviation to be reconciled; `994a929` reconciled it the other way, by
making the location explicitly per-machine in `bridge/README.md` and
`requirements.txt`. **The binding requirement is the mechanism, not the path**:
a venv created with `--system-site-packages`, in a directory the operator can
write, with `/opt/ros/jazzy/setup.bash` sourced in every shell that uses it.

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
   the 104x small-file penalty is exactly what a build hits. Put it on a
   native ext4 path. (When this was written, `install.sh` provisioned a vendor
   workspace at `/opt/m3-feasibility/ws`, native ext4, and was correct on that
   count; m5-09 removed that step with the retired platform, so no workspace
   location is set by the script any more and this is a rule for the next one.)
2. If m3-08 wants the tightest possible latency distribution, pointing
   `evidence.csv_path` at a native path (e.g. `~/amr-evidence/`) and copying
   the CSV into the repo afterwards removes the 4.25 ms flush spikes entirely.
   This is an option, not a necessity. Since `994a929` the config expands `~`
   and `$VARS` and honours an absolute path as written, so this needs no code
   change — only a different value.

When this section was first written the configured evidence path was a
container path that did not exist here. That was fixed in `994a929`: the
committed default is now the machine-neutral `evidence/latency-latest.csv`,
anchored to the `bridge/` directory, and it resolves on this machine
(§5 item 2).

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

1. **Venv location (RESOLVED, `994a929`).** As observed: the venv is at
   `/home/ozkan/amr-bridge-venv`, not the `/opt/amr-bridge-venv` every other
   document named, because `/opt` needs root. Resolved not by moving the venv
   but by correcting the documents: `bridge/README.md` and `requirements.txt`
   now record the location as a per-machine choice, with the container
   `/opt/amr-bridge-venv` and this machine's `$HOME/amr-bridge-venv` as the two
   worked examples. The requirement that survives is the *mechanism*, not the
   path — a `--system-site-packages` venv in a directory the operator can write.
2. **Evidence CSV path (RESOLVED, `994a929`).** As observed, the configured
   path was a container path that did not exist here:

   ```
   bridge/config/bridge.yaml:95:  csv_path: "/home/user/amr-agent/bridge/evidence/latency-2026-07-27.csv"
   $ ls -l /home/user/amr-agent/bridge/evidence/
   ls: cannot access '/home/user/amr-agent/bridge/evidence/': No such file or directory
   ```

   The committed default is now the machine-neutral
   `evidence/latency-latest.csv`, expanded for `~` and `$VARS`, absolute paths
   honoured as written, and anything still relative anchored to the `bridge/`
   directory. No `--evidence-csv` override is needed. Confirmed resolving on
   this machine:

   ```
   evidence_csv_path : /mnt/c/Users/ozkan/projects/amr-agent/bridge/evidence/latency-latest.csv
   parent exists     : True
   ```
3. **Clock: mitigated, not fixed — re-check before the PLCSIM run.** The
   original diagnosis stands (§4.5): the guest wall clock stepped ~2.73 s every
   ~30 s. After an owner resync plus `wsl --shutdown`, the guest/host skew is
   down to a few hundred milliseconds — in three bracketed samples the WSL
   timestamp now lands *inside* the Windows bracket, where before it sat 3.7–4.6 s
   outside it.

   **The mechanism has not gone away, only shrunk.** `systemd-timesyncd` still
   steps `CLOCK_REALTIME` on its 32 s poll; the step is simply ~220x smaller:

   ```
   t= 0s  drift +0.000000 s
   t=30s  drift +0.012166 s
   t=60s  drift +0.024465 s
   total drift over 70 s: +0.024466 s
   ```

   ~12 ms per step instead of ~2.73 s. And the underlying cause is untreated —
   `w32time` is **still `Stopped`**, so the resync was one-shot, not maintained:

   ```
   $ (Get-Service w32time).Status
   Stopped
   $ w32tm /query /source
   The following error occurred: The service has not been started. (0x80070426)
   ```

   At the observed ~350 ppm the skew re-accumulates to tens of seconds per day,
   so this must be re-measured immediately before any run whose evidence
   correlates bridge and PLCSIM timestamps. Intra-process latency remains
   unaffected either way, because the bridge timestamps with
   `time.monotonic_ns()`.
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

---

# Part II — the autonomy stack, installed 2026-08-05 (m5-21)

Part I above is the M3 record and is kept because its WSL findings (§4.1
`gz` on PATH, §4.5 the clock, §4.6 DrvFs, §4.7 llvmpipe, §4.8 line endings)
are still true of this machine. **What changed on 2026-08-05 is §2's two
`MISSING` rows: Nav2 and the estimator are now installed as system
packages.** Sections 6 to 10 are the record of that, written as each step
landed, not afterwards.

## 6. What was missing, and the overlay that stood in for it

`m5-11` needed `nav2_velocity_smoother` and `robot_localization` and this
machine had neither. Under a brief that forbade adding dependencies, it
fetched `.deb` files with `apt-get download` and extracted them into a
**user prefix** at `~/ros-overlay/prefix` — no system package installed,
nothing written outside `$HOME`. The archive's `fastcdr` / `fastrtps` had
to come with them (typesupport ABI), and `nav2_smac_planner` /
`nav2_map_server` dragged in `libompl.so.18` and GraphicsMagick.

```
$ du -sh ~/ros-overlay
245M    /home/ozkan/ros-overlay
$ ls ~/ros-overlay/prefix/opt/ros/jazzy/share | wc -l
36
```

**Every figure in `agv/forklift/EVIDENCE_ENVELOPE.md` was measured against
that overlay**, and that qualifier belongs on those figures (LESSONS
2026-07-27: evidence is qualified by the environment that produced it).
Section 10 below re-runs one of them on the installed stack and reports
whether the two agree.

## 7. Privilege on this machine — a fact, with no credential in it

`sudo` here requires a password (Part I §3.1, still true). The route that
works without one is WSL's own root user, invoked from the Windows side:

```
PS> wsl.exe -u root -e bash -lc '<command>'
```

```
$ wsl.exe -u root -e bash -lc 'id'
uid=0(root) gid=0(root) groups=0(root)
```

That is a property of the WSL distro's default-user configuration, not a
stored secret. **No password was requested, handled or stored at any point
in this work, and none appears in this repository** (invariant 13).

The ROS 2 apt source was already in place and needed no change:

```
/etc/apt/sources.list.d/ros2.list:deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu noble main
```

## 8. The snapshot, taken before anything was installed

This is the rollback record. It exists on the machine at
`/root/m5-21-snapshot`, copied readable to `~/m5-21-snapshot`:

| File | What it holds | Size |
|---|---|---|
| `dpkg-selections.txt` | `dpkg --get-selections`, the whole system | **2095 lines** |
| `ros-jazzy-versions.txt` | `dpkg-query -W -f='${Package} ${Version}\n' 'ros-jazzy-*'` | **327 packages** |
| `apt-history-tail.txt` | tail of `/var/log/apt/history.log` | last 30 lines |

The last three apt transactions before this work were all
`unattended-upgrade` (`distro-info-data`, `openssl`, `tzdata`, on
2026-08-04). Nothing had touched the ROS tree.

**The machine is well behind the archive**, which is the risk this brief
was written around:

```
$ apt list --upgradable | wc -l
347                 # includes the "Listing..." header, so 346 packages
$ apt list --upgradable | grep -c '^ros-jazzy-'
292
```

Baseline, before the install, with the overlay **not** sourced:

```
$ source /opt/ros/jazzy/setup.bash
$ ros2 pkg prefix nav2_bringup ; ros2 pkg prefix robot_localization
Package not found
Package not found
```

## 9. The apt plan, simulated before it was executed

Two candidate package sets were simulated. **They produce an identical
plan** — `ros-jazzy-nav2-bringup` already pulls `ros-jazzy-navigation2` —
so the narrower command was the one executed:

```
$ apt-get -s install ros-jazzy-nav2-bringup ros-jazzy-robot-localization
0 upgraded, 137 newly installed, 0 to remove and 346 not upgraded.
$ grep -c '^Remv' sim-plan-narrow.txt
0
```

**Nothing is upgraded and nothing is removed.** The feared outcome — an
`apt install` dragging the whole 292-package ROS tree forward and breaking
a working stack — does not happen: apt satisfies every dependency of the
new packages against the versions already installed. The 346 packages
behind the archive stay behind it.

Of the 137 new packages, **73 are `ros-jazzy-*`** (the Nav2 set,
`robot_localization`, `slam_toolbox`, `behaviortree_cpp`, `bond`/`bondcpp`,
`ompl`, the `ros2_control` interface libraries Nav2's controllers pull in)
and 64 are Ubuntu libraries — the ones the overlay had had to work around
by hand: `libgeographiclib26`, GraphicsMagick, `libceres`/SuiteSparse,
`libomp`. No package outside `noble`, `noble-updates`,
`noble-security` and `packages.ros.org/ros2/ubuntu noble` appears in the
plan.

## 10. What the install actually did

Executed, and recorded from the log rather than from the plan:

```
$ wsl.exe -u root -e bash -lc 'DEBIAN_FRONTEND=noninteractive apt-get install -y \
      ros-jazzy-nav2-bringup ros-jazzy-robot-localization'
Need to get 88.4 MB of archives.
After this operation, 549 MB of additional disk space will be used.
...
Setting up ros-jazzy-robot-localization (3.8.3-1noble.20260615.152020) ...
Setting up ros-jazzy-nav2-bringup (1.3.12-1noble.20260616.082701) ...
exit=0
```

`/var/log/apt/history.log`, the transaction as apt recorded it:

```
Start-Date: 2026-08-05  07:40:36
Commandline: apt-get install -y ros-jazzy-nav2-bringup ros-jazzy-robot-localization
Install: ... (137 packages, all "automatic" except the two named)
End-Date: 2026-08-05  07:41:01
```

**There is no `Upgrade:` line and no `Remove:` line in that transaction.**
The outcome matched the simulation exactly:

| | Simulated | Actual |
|---|---|---|
| `ros-jazzy-*` installed, before → after | 327 → 400 | **327 → 400** (+73) |
| upgraded | 0 | **0** |
| removed | 0 | **0** |
| `ros-jazzy-*` still behind the archive | 292 | **292**, unchanged |
| errors in the log | — | **0** |

25 seconds, 88.4 MB fetched, 549 MB on disk.

### 10.1 The versions that matter

Recorded so this environment is reproducible from this document alone:

| Package | Version |
|---|---|
| `ros-jazzy-nav2-bringup` | `1.3.12-1noble.20260616.082701` |
| `ros-jazzy-navigation2` | `1.3.12-1noble.20260615.181551` |
| `ros-jazzy-robot-localization` | **`3.8.3-1noble.20260615.152020`** |
| `ros-jazzy-nav2-velocity-smoother` | **`1.3.12-1noble.20260615.153210`** |
| `ros-jazzy-nav2-amcl` | `1.3.12-1noble.20260615.153115` |
| `ros-jazzy-nav2-map-server` | `1.3.12-1noble.20260615.153120` |
| `ros-jazzy-nav2-controller` | `1.3.12-1noble.20260615.165600` |
| `ros-jazzy-nav2-planner` | `1.3.12-1noble.20260615.170058` |
| `ros-jazzy-nav2-bt-navigator` | `1.3.12-1noble.20260615.165211` |
| `ros-jazzy-nav2-behaviors` | `1.3.12-1noble.20260615.170333` |
| `ros-jazzy-nav2-lifecycle-manager` | `1.3.12-1noble.20260615.152740` |
| `ros-jazzy-slam-toolbox` | `2.8.5-1noble.20260615.161600` |
| `ros-jazzy-behaviortree-cpp` | `4.9.0-1noble.20260615.161133` |
| `ros-jazzy-ompl` | `1.7.0-2noble.20260225.055751` |

**The two versions in bold are the two `EVIDENCE_ENVELOPE.md` §0 names**
— `nav2_velocity_smoother` 1.3.12 and `robot_localization` 3.8.3. The
system packages are the **same upstream versions** the overlay carried,
which is why §12's comparison is a comparison of packaging and not of
software.

## 11. The overlay is retired

Nothing in the repository ever *sourced* it — the only references are
prose:

```
$ grep -rl 'ros-overlay' .
./agv/forklift/EVIDENCE_ENVELOPE.md      (prose, §0 and §11 item 7)
./docs/reports/m5-11-envelope-gate-node.md
./docs/TODO.md
./docs/briefs/m5-21-wsl-ros-stack-install.md
```

No launch file, no script, no `~/.bashrc` line. `~/.bashrc` sources
`/opt/ros/jazzy/setup.bash` and nothing else.

It was moved aside **before** the verification runs below, so no run in
§12 can have touched it:

```
$ mv ~/ros-overlay ~/ros-overlay.retired-m5-21
$ ls -d ~/ros-overlay/prefix
ls: cannot access '/home/ozkan/ros-overlay/prefix': No such file or directory
```

245 MB, kept under the `.retired-m5-21` name rather than deleted, so the
environment m5-11 measured in can be restored if a figure ever has to be
re-read against it. **It is not on any search path** and can be deleted
once this work is committed.

Resolution, with the overlay gone and only `/opt/ros/jazzy` sourced:

```
$ source /opt/ros/jazzy/setup.bash
$ echo $AMENT_PREFIX_PATH
/opt/ros/jazzy
$ ros2 pkg prefix nav2_bringup            ->  /opt/ros/jazzy
$ ros2 pkg prefix robot_localization      ->  /opt/ros/jazzy
$ ros2 pkg prefix nav2_velocity_smoother  ->  /opt/ros/jazzy
$ ros2 pkg prefix nav2_amcl               ->  /opt/ros/jazzy
$ ros2 pkg prefix slam_toolbox            ->  /opt/ros/jazzy
```

## 12. The verification runs, and the one collision they found

### 12.1 First run — the vehicle stack and the smoother came up

`GZ_PARTITION=m521verify`, `ROS_DOMAIN_ID=58`, both, always (LESSONS
2026-07-27). Warehouse bringup, then the m5-11 envelope stack:

```
$ ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
$ ros2 launch agv/forklift/launch/envelope.launch.py feedback:=CLOSED_LOOP
/cmd_vel_to_tricycle  /envelope_gate  /forklift_arena_bridge  /forklift_ekf
/imu_gate  /sensor_tf  /velocity_smoother  /wheel_odometry
```

`/forklift_ekf` is `robot_localization`'s `ekf_node` and
`/velocity_smoother` is `nav2_velocity_smoother`, both now from
`/opt/ros/jazzy`. **No fatal error and no process death in either log.**

### 12.2 Second run — AMCL and `controller_server` died, exit 127

The full stack (`localization.launch.py` + `navigation.launch.py`) was
started next, and two of the newly installed nodes died:

```
[amcl-2] /opt/ros/jazzy/lib/nav2_amcl/amcl: symbol lookup error:
  /opt/ros/jazzy/lib/libnav2_msgs__rosidl_typesupport_fastrtps_cpp.so:
  undefined symbol: _ZN8eprosima7fastcdr3Cdr9serializeEj
[ERROR] [amcl-2]: process has died [pid 28648, exit code 127, ...]
[ERROR] [controller_server-2]: process has died [pid 28720, exit code 127, ...]
```

`ldd` reports **no** missing library for either binary, and
`/opt/ros/jazzy/lib/nav2_amcl/amcl --help` starts cleanly on its own — the
fault is a *symbol*, not a file:

```
$ ldd /opt/ros/jazzy/lib/nav2_amcl/amcl | grep -i 'not found'
(nothing)
```

**This is precisely the collision `EVIDENCE_ENVELOPE.md` §11 item 7
predicted.** `libnav2_msgs__rosidl_typesupport_fastrtps_cpp.so` came from
today's archive and was built against a newer Fast-CDR than the one this
machine has:

```
ros-jazzy-fastcdr    installed 2.2.5-1noble.20260121.175748   candidate 2.2.7-1noble.20260225.051855
ros-jazzy-fastrtps   installed 2.14.5-2noble.20260121.180353  candidate 2.14.6-1noble.20260303.233638
```

`Cdr::serialize(unsigned int)` is exported by 2.2.7 and not by 2.2.5. The
overlay solved it by carrying the archive's `fastcdr`/`fastrtps` beside
the system's; a system install has to reconcile them instead.

### 12.3 Upgrading `fastcdr` alone broke the entire ROS installation

Simulated first, and the plan was as narrow as a plan gets:

```
$ apt-get -s install ros-jazzy-fastcdr
1 upgraded, 0 newly installed, 0 to remove and 345 not upgraded.
```

`libfastcdr.so.2.2.5` was copied to `/root/m5-21-snapshot/` before the
upgrade, which is the only reason this is recoverable — **the 2.2.5
package is no longer in the archive at all**:

```
$ apt-cache madison ros-jazzy-fastcdr
ros-jazzy-fastcdr | 2.2.7-1noble.20260225.051855 | packages.ros.org/ros2/ubuntu noble/main
```

The upgrade installed cleanly, the missing symbol appeared, and **every
ROS 2 process on the machine then died** — not just Nav2. The Gazebo
bridge, `sensor_tf`, `wheel_odometry`, `imu_gate` and `ekf_node` all
aborted, and both Nav2 launch files threw a Fast-CDR exception before
starting anything:

```
[ERROR] [parameter_bridge-3]: process has died ... exit code -6
[ERROR] [ekf_node-7]:         process has died ... exit code -6
[ERROR] [sensor_tf-4]:        process has died ... exit code 1
[ERROR] [launch]: Caught exception in launch: This member is not been selected
```

So `fastcdr` 2.2.5 -> 2.2.7 is **not** a drop-in despite an unchanged
soname (`libfastcdr.so.2`): the installed `fastrtps` 2.14.5 does not work
against it.

**Restoring the 2.2.5 file restored the machine**, which is what confirms
the attribution rather than making it plausible (LESSONS 2026-07-27):

```
$ cp -a /root/m5-21-snapshot/libfastcdr.so.2.2.5 /opt/ros/jazzy/lib/
$ ln -sfn libfastcdr.so.2.2.5 /opt/ros/jazzy/lib/libfastcdr.so.2
$ ros2 run demo_nodes_cpp talker
[INFO] [talker]: Publishing: 'Hello World: 1'
$ python3 -c 'import rclpy; ...'
rclpy publish OK
```

### 12.4 The two coherent ways forward, both simulated

```
$ apt-get -s install ros-jazzy-fastcdr ros-jazzy-fastrtps \
                     ros-jazzy-rmw-fastrtps-cpp ros-jazzy-rmw-fastrtps-shared-cpp
3 upgraded, 0 newly installed, 0 to remove and 342 not upgraded.

$ apt-get -s dist-upgrade
345 upgraded, 7 newly installed, 1 to remove and 0 not upgraded.
Remv libglapi-mesa [24.2.8-1ubuntu1~24.04.1]
```

**The full `dist-upgrade` removes a package** — `libglapi-mesa`, dropped
by a Mesa upgrade — and Mesa is what renders every Gazebo run on this
machine (§4.7, llvmpipe). Under this brief's rule a removal is a
stop-and-report, and it is not taken. The narrow DDS set removes nothing
and is the one that was executed; §12.5 is its result.

### 12.5 The DDS set moved together, and the whole stack came up

```
$ wsl.exe -u root -e bash -lc 'apt-get install -y ros-jazzy-fastcdr \
      ros-jazzy-fastrtps ros-jazzy-rmw-fastrtps-cpp ros-jazzy-rmw-fastrtps-shared-cpp'
3 upgraded, 0 newly installed, 0 to remove and 342 not upgraded.
Setting up ros-jazzy-fastrtps (2.14.6-1noble.20260303.233638) ...
Setting up ros-jazzy-rmw-fastrtps-shared-cpp (8.4.4-1noble.20260615.124045) ...
Setting up ros-jazzy-rmw-fastrtps-cpp (8.4.4-1noble.20260615.124621) ...
exit=0
```

Base ROS 2 first, because §12.3 is the reason not to trust a Nav2 launch as
the first test after a DDS change:

```
$ ros2 run demo_nodes_cpp talker      ->  Publishing: 'Hello World: 1'
$ python3 -c 'import rclpy; ...'      ->  rclpy publish OK
$ /opt/ros/jazzy/lib/nav2_amcl/amcl   ->  amcl lifecycle node launched.
```

Then the **full M5 vehicle stack** — warehouse bringup, then
`localization.launch.py` with `EVIDENCE_LOCALIZATION.md`'s initial pose,
then `navigation.launch.py`:

```
/amcl  /behavior_server  /bt_navigator  /bt_navigator_navigate_to_pose_rclcpp_node
/controller_server  /planner_server  /map_server  /velocity_smoother
/global_costmap/global_costmap  /local_costmap/local_costmap
/cmd_vel_to_tricycle  /envelope_gate  /forklift_arena_bridge  /forklift_ekf
/forklift_io  /imu_gate  /sensor_tf  /wheel_odometry
```

**That list is from a run started on a clean machine** — see §12.7, which
is the reason the first attempt's list is not the one quoted here.
`smoother_server` and `waypoint_follower` do not appear because
`navigation.launch.py` does not start them; that is the project's node set,
not a missing package.

Lifecycle state of every managed node, read rather than assumed:

| Node | State |
|---|---|
| `/map_server` | **active [3]** |
| `/amcl` | **active [3]** |
| `/controller_server` | **active [3]** |
| `/planner_server` | **active [3]** |
| `/behavior_server` | **active [3]** |
| `/bt_navigator` | **active [3]** |
| `/velocity_smoother` | **active [3]** |

```
fatal=0  process-died=0     in all three launch logs
```

The `[ERROR]` lines that remain are **not** install failures and are worth
naming so they are not chased: the costmap inflation-radius advisories that
Nav2 logs at ERROR severity for this vehicle's footprint (a `nav2.yaml`
tuning matter, present before this work), and `map -> forklift/base_link`
TF extrapolation messages from `planner_server` polling while no goal is
active and AMCL is still settling. No process died and no node left
`active`.

### 12.6 The re-run m5-11 measurement — what agrees and what does not

`EVIDENCE_ENVELOPE.md` §7, observation 5, pass-through fidelity: the
cheapest decisive one, because it exercises `nav2_velocity_smoother` and
`robot_localization` on a non-constant command and its result is a residual
that cannot be produced by luck.

```
$ ros2 launch sim/launch/warehouse_bringup.launch.py x:=-4.5 y:=7.0 yaw:=0.0
$ ros2 launch agv/forklift/launch/envelope.launch.py feedback:=CLOSED_LOOP
$ python3 agv/forklift/scripts/envelope_run.py run --scenario passthrough \
      --csv ~/m5-21-runs/m521-passthrough.csv
```

**Four** runs on the installed stack, against the committed overlay figure:

| | committed (overlay) | installed A | installed B | installed C | installed D |
|---|---|---|---|---|---|
| DDS stack | 2.2.5 + overlay copy | 2.2.5 | **2.2.7 / 2.14.6** | **2.2.7 / 2.14.6** | **2.2.7 / 2.14.6** |
| machine verified clear of orphans first | - | no | no | no | **yes** (§12.7) |
| matched pairs | 221 | 221 | 224 | 676 | 440 |
| `max abs(gated_v - smoothed_v)` | **0.000e+00** | **0.000e+00** | **0.000e+00** | **0.000e+00** | **0.000e+00** |
| exact matches | 221 of 221 | **221 of 221** | **224 of 224** | **676 of 676** | **440 of 440** |
| gate latency, mean | 0.0004 s | 0.0004 s | 0.0012 s | 0.0023 s | **0.0242 s** |
| gate latency, max | **0.0010 s** | 0.0014 s | 0.0465 s | 0.0122 s | **0.0713 s** |

**What agrees, exactly: the observation itself.** The residual is
`0.000e+00` on both components and **every matched pair is exact, in every
run, on both packagings** - 221, 224, 676 and 440 pairs of them. That is
the claim §7 makes, and it reproduces on the installed stack without
qualification.

**What disagrees, and it is stated rather than reconciled: the latency
figures.** The committed **mean 0.0004 s / max 0.0010 s** is not
reproduced. Across four runs the mean ranged **0.0004 to 0.0242 s** and the
max **0.0014 to 0.0713 s** - up to **60x** the committed mean and **71x**
the committed max. **Nothing was tuned to make them agree**, and no figure
above was discarded.

Read honestly, this is a finding about the figure rather than about either
environment, and three things say so:

1. Run **A** ran on the *old* DDS stack and landed at 0.0004 / 0.0014 s, so
   the spread is not caused by the Fast-DDS upgrade.
2. Run **D** ran on a machine verified clear of orphan processes and
   stranded shared memory (§12.7) and is the **worst** of the four, so it is
   not caused by contention from leftovers either.
3. The four runs disagree with **each other** by 60x on the mean, so
   `0.0004 s` was a sample and never a bound (LESSONS 2026-08-04).

The matched-pair count moving 221 -> 676 -> 440 is the same story from the
other side: how many commands the smoother emits in the scenario's 14 s of
simulated time is not a controlled quantity here, so neither is the worst
queueing delay among them. What the gate's design guarantees is the **zero
residual**, and that is what held.

**What this asks for.** `agv/forklift/EVIDENCE_ENVELOPE.md` is outside this
brief's write scope. Two changes are requested in the m5-21 report: §0's
environment block should say the figures were measured **under the
`~/ros-overlay/prefix` overlay, which no longer exists**, and §7's latency
row should be re-read as a single-run observation with its n rather than as
a property of the gate, with the four figures above beside it.

### 12.7 A Fast-DDS version change strands `/dev/shm`, and killing a launch is not killing its nodes

Two housekeeping faults surfaced between the runs above and are recorded
because both are easy to misread as the install having failed.

**The stale segments.** Part I §4.4 noted that Fast DDS leaves its
`/dev/shm` objects behind after a clean exit and called it housekeeping.
After the Fast-DDS upgrade it stops being housekeeping: the new
`libfastrtps` could not take the ports the old one had left locked, and
every node logged

```
[RTPS_TRANSPORT_SHM Error] Failed init_port fastrtps_port7000:
    open_and_lock_file failed -> Function open_port_internal
```

which looks exactly like a broken install and is not one. With **no ROS 2
process running**:

```
$ ls /dev/shm | wc -l
151
$ rm -f /dev/shm/fastrtps_* /dev/shm/sem.fastrtps_*
$ ls /dev/shm | wc -l
2
```

and the same binaries started cleanly. **Clear `/dev/shm` after any
`fastcdr` / `fastrtps` / `rmw_fastrtps` change**, and only while nothing is
running.

**The orphans.** `kill`ing a `ros2 launch` process does **not** reliably
take the nodes it started. Five nodes from earlier runs — two `ekf_node`,
two `map_server`, one `amcl` — were still alive minutes after their
launches were killed, and they are what held those 151 segments. They also
put **duplicate names into `ros2 node list`** during the first full-stack
run, which is a genuinely misleading symptom: a live ghost and a new node
share a name and either may answer.

```
$ pkill -f 'nav2_map_server|nav2_amcl|robot_localization/ekf_node|nav2_controller|...'
$ pgrep -af 'nav2_|ekf_node|gz sim|ros2 launch|forklift' | wc -l
0
```

The rule that follows, and it is the same shape as Part I §4.7's `pkill`
lesson: **tear a run down by pattern against observed `pgrep -af` output
and verify the count is zero**, then clear `/dev/shm`, before reading
anything from the next run. The §12.5 node list and the §12.6 **run D** figures
were taken after that teardown; runs A, B and C were not, which is why
§12.6 records per run whether the machine had been verified clear.


## 13. How to reproduce this environment, and what is still open

### 13.1 The recipe

On a machine whose whole ROS tree came from one archive snapshot, this is
one command and the Fast-DDS step below is a no-op:

```bash
sudo ./sim/setup/install.sh          # ROS_PKGS already names navigation2,
                                     # nav2-bringup, slam-toolbox and
                                     # robot-localization
```

On a machine like this one, whose ROS tree is months behind the archive,
the second step is **required and is now in the script** (the
`DDS_PKGS` block added by m5-21):

```bash
apt-get install -y ros-jazzy-nav2-bringup ros-jazzy-robot-localization
apt-get install --only-upgrade -y ros-jazzy-fastcdr ros-jazzy-fastrtps \
                                  ros-jazzy-rmw-fastrtps-cpp \
                                  ros-jazzy-rmw-fastrtps-shared-cpp
```

`--only-upgrade` is deliberate: it can never pull in a package that was not
already installed. `install.sh` runs it only when it actually installed
something, so a current machine is untouched.

**Then, before the first run** — because a Fast-DDS change strands the old
shared-memory segments (§12.7), and only while nothing is running:

```bash
rm -f /dev/shm/fastrtps_* /dev/shm/sem.fastrtps_*
```

**Where this differs from `install.sh` and why the script was still the
right home.** The package list was already correct — `ROS_PKGS` has named
`navigation2`, `nav2-bringup`, `slam-toolbox` and `robot-localization`
since m5-09/m5-07c. What the script did not know is that installing them
onto a stale tree needs the Fast-DDS realignment, and that is a durable
property of this install path rather than a fact about one afternoon, so it
belongs in the script and not only in this document.

### 13.2 Rollback record

`/root/m5-21-snapshot`, copied readable to `~/m5-21-snapshot`:

| File | What it is |
|---|---|
| `dpkg-selections.txt` | the whole system before any of this, 2095 lines |
| `ros-jazzy-versions.txt` | 327 `ros-jazzy-*` packages with versions, before |
| `apt-history-tail.txt` | `/var/log/apt/history.log` tail, before |
| `sim-plan.txt`, `sim-plan-narrow.txt`, `sim-plan-fastcdr.txt`, `sim-plan-dds.txt`, `sim-plan-distupgrade.txt` | the five simulated plans |
| `install.log`, `install-fastcdr.log`, `install-dds.log` | what actually ran |
| **`libfastcdr.so.2.2.5`** | **the pre-upgrade library.** Keep it: 2.2.5 is no longer in the archive, so this file is the only rollback for §12.3 |

`~/ros-overlay.retired-m5-21` (245 MB) is the m5-11 overlay, moved aside and
on no search path.

### 13.3 Open

1. **This machine is still 288 `ros-jazzy-*` packages behind the archive**
   (342 in total; 400 `ros-jazzy-*` packages are installed).
   That is deliberate: `apt-get -s dist-upgrade` proposes 345 upgrades and
   **removes `libglapi-mesa`**, and Mesa is the software rasteriser every
   Gazebo run here depends on (§4.7). A removal is a stop-and-report under
   the m5-21 brief and was not taken. **If a future package needs a newer
   ROS tree, the dist-upgrade is an owner decision with a Gazebo re-run
   attached to it**, not a step inside another brief.
2. **`agv/forklift/EVIDENCE_ENVELOPE.md` still describes the overlay as
   present.** It is outside m5-21's write scope; the report requests the
   qualifier and the latency-figure correction (§12.6).
3. **The five `EVIDENCE_ENVELOPE.md` observations other than pass-through
   have not been re-run on the installed stack.** One was re-run because
   the brief asked for one. §12.6's spread is a reason to repeat the
   enable-drop, stale, clamp, release and permit figures for their own n
   before any of them is quoted as a bound — those are stopping distances
   and reaction times, which is exactly the class of figure a 60x timing
   spread would move.
4. **Clock (§4.5 / §5 item 3) is unchanged and still untreated** —
   `w32time` was `Stopped` at the last check and nothing here touched it.
   Nothing in Part II depends on the wall clock.
