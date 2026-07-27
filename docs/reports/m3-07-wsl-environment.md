brief:               docs/briefs/m3-07-wsl-environment.md
status:              blocked
files_changed:       [sim/setup/WSL_ENVIRONMENT.md, docs/reports/m3-07-wsl-environment.md]
invariants_touched:  none
open_questions:
  - Gazebo Harmonic is not installed and `apt` needs a sudo password this agent
    cannot supply. Investigations 1 (gz version) and 7 (headless Gazebo) are
    unanswered. Owner must run, from the repo root:
    `sudo apt-get update && sudo apt-get install -y ros-jazzy-gz-sim-vendor ros-jazzy-ros-gz`
    (that is the minimum for the M3 cell; the full `install.sh` list also
    installs the ros2_control and Nav2 stacks, which the cell does not need).
  - `install.sh` cannot run in WSL: the working tree is CRLF, so the shebang
    fails with `/usr/bin/env: 'bash\r': No such file or directory`. The git
    blob is LF-clean; Windows Git's system `autocrlf = true` causes it and the
    repo has no `.gitattributes`. I did NOT edit `install.sh` — its committed
    content is correct and editing it would fix nothing durably. Requesting a
    root `.gitattributes` (outside this brief's write access), minimally
    `* text=auto` plus `*.sh text eol=lf`. Second-order risk: WSL-side git
    reports every tracked file as modified while Windows-side git reports the
    tree clean, so a `git commit -a` from WSL would churn the whole repo.
  - The venv had to go to `/home/ozkan/amr-bridge-venv` because `/opt` needs
    root. Every other document says `/opt/amr-bridge-venv`. Needs reconciling
    when the elevated step runs, or `bridge/README.md` is wrong on this machine.
  - `bridge/config/bridge.yaml` `evidence.csv_path` points at
    `/home/user/amr-agent/...`, a container path that does not exist here.
    m3-08 needs `--evidence-csv` or a config change. Flagged, not changed —
    `bridge/` is outside this brief's write access.
  - The Windows Time service on the host is stopped (`w32tm /query /status` ->
    `0x80070426`). The WSL wall clock steps forward ~2.73 s every ~30 s and is
    several seconds ahead of the host. The bridge timestamps everything with
    `time.monotonic_ns()`, so m3-08's latency numbers are NOT invalidated — but
    any WSL-to-PLCSIM-Advanced timestamp correlation is currently meaningless.
    Owner action before the PLCSIM gate run: elevated `Start-Service w32time;
    w32tm /resync`.
  - `sim/worlds/cell.sdf` is rejected by strict XML parsers because its header
    comment contains `--`. Not a WSL issue, very likely harmless (Gazebo uses
    the permissive TinyXML2), but unverified here because Gazebo is absent.
next_suggested:      Owner runs the two elevated commands above (apt install, w32time), then re-run this brief's investigations 1 and 7 before starting m3-08.

## What was verified

- ROS 2 Jazzy present (`ros-jazzy-ros-base 0.11.0-1noble.20260126.203129`),
  `rmw_fastrtps_cpp`, python3 already 3.12.3 — the container's
  `update-alternatives` quirk does not exist in WSL.
- asyncua **2.0.1** installed with the exact transitive set recorded in
  `bridge/requirements.txt` (cryptography 49.0.0, pyOpenSSL 26.3.0, ...). The
  `--system-site-packages` venv behaves identically to the container.
- **Interpreter unification proven**: `rclpy` (from `/opt/ros/jazzy`) and
  `asyncua` 2.0.1 import in one command in one interpreter. The project uses no
  Gazebo Python bindings (grep over `bridge/` and `sim/` is empty).
- **DDS discovery works under WSL2 with no configuration.** Multicast is
  functional on `eth0`; pub/sub across two processes succeeded in all four
  cases (default, `ROS_DOMAIN_ID=42`, `ROS_LOCALHOST_ONLY=1`,
  `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`). No XML profile needed. This was
  the finding most expected to bite and it did not.
- `/dev/shm` is tmpfs, 7.8 G, writable. Fast DDS leaves ~16 segments behind
  after clean exits; recommend clearing them between m3-08 measurement runs.
- **Filesystem: `/mnt/c` is acceptable for m3-08, measured not assumed.** DrvFs
  is 104x slower on small-file creation and 61x on batched CSV appends, but the
  bridge batches its evidence writes every 2 s, costing ~0.2 % of wall time. A
  native ext4 path is NOT required. A colcon workspace must never go on
  `/mnt/c`; `install.sh` already puts it on `/opt`, which is correct.
- WSLg is present (`DISPLAY=:0`, `/dev/dri` with `card0`/`renderD128`), unlike
  the container's llvmpipe-only path.

`install.sh` was **not** modified. Its logic is sound and its preconditions all
pass on this system; only the checked-out line endings block it.

## lessons_candidates

2026-07-27 | Ran `sim/setup/install.sh` in WSL from the /mnt/c checkout | Windows Git's system `autocrlf = true` had checked the tree out as CRLF, so the shebang failed with `/usr/bin/env: 'bash\r'` and every tracked file read as modified to WSL-side git | The repo needs a root `.gitattributes` (`* text=auto`, `*.sh text eol=lf`); until it exists, run git from Windows only and pipe shell scripts through `sed 's/\r$//'` before executing them in WSL

2026-07-27 | Assumed WSL2's NAT'd adapter would need DDS tuning, as is generally reported | Default discovery worked in all four tested configurations; the tuning would have been cargo-cult configuration masking nothing | Measure discovery on the actual machine before adding `ROS_LOCALHOST_ONLY` or an XML profile; note `ROS_LOCALHOST_ONLY` is deprecated in Jazzy and logs a warning

2026-07-27 | Benchmarked DrvFs with a per-row flushed CSV and nearly reported a 154x penalty as a blocker | The bridge does not write that way — `instrumentation.py` batches rows and flushes every 2 s, making the real cost ~0.2 % of wall time | Benchmark the access pattern the code actually uses, not a plausible-looking proxy; read the implementation before quantifying its cost

2026-07-27 | Treated a wall-clock anomaly as a WSL quirk to note in passing | The host's Windows Time service was stopped, making the guest clock step ~2.73 s every 30 s; had the bridge used `time.time()` this would have silently corrupted every latency figure | Before trusting timestamp-derived evidence on a new machine, verify which clock the code samples and that host and guest clocks are synchronised

2026-07-27 | Reported `cell.sdf` failing to parse as a possible CRLF casualty | It was actually `--` inside an XML comment, which the spec forbids and ElementTree enforces; CRLF was irrelevant | Confirm the mechanism of a failure with a minimal reproduction before attributing it to the environment under investigation
