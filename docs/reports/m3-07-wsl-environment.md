brief:               docs/briefs/m3-07-wsl-environment.md
status:              done
files_changed:       [sim/setup/WSL_ENVIRONMENT.md, docs/reports/m3-07-wsl-environment.md]
invariants_touched:  none
open_questions:
  - RESOLVED in `994a929` — venv path. `bridge/README.md` and
    `requirements.txt` now document the location as a per-machine choice
    (container `/opt/amr-bridge-venv`, WSL `$HOME/amr-bridge-venv`); the
    binding requirement is the `--system-site-packages` mechanism, not the
    path. Verified against the committed files.
  - RESOLVED in `994a929` — `evidence.csv_path`. The committed default is now
    the machine-neutral `evidence/latency-latest.csv`, anchored to `bridge/`,
    with `~`/`$VARS` expanded and absolute paths honoured. Verified resolving
    live here to
    `/mnt/c/Users/ozkan/projects/amr-agent/bridge/evidence/latency-latest.csv`
    with the parent directory present.
  - OPEN, mitigated — clock. After the owner's resync plus `wsl --shutdown`,
    guest/host skew is down from 3.7-4.6 s to inside a ~250 ms measurement
    bracket. But the mechanism persists, only ~220x smaller: `systemd-timesyncd`
    still steps `CLOCK_REALTIME` every ~30 s, now by ~12 ms (measured
    +0.024466 s over 70 s). And `w32time` is **still `Stopped`**, so the resync
    was one-shot, not maintained — at ~350 ppm the skew re-accumulates to tens
    of seconds per day. Re-measure immediately before any run whose evidence
    correlates bridge and PLCSIM timestamps. Intra-process latency is
    unaffected regardless, because the bridge uses `time.monotonic_ns()`.
  - OPEN — DDS was proven only between two `ros2` CLI processes. The full
    runtime topology (gz server + `ros_gz_bridge` + bridge) belongs to m3-08.
next_suggested:      m3-08 can proceed; re-measure guest/host clock skew first if its evidence will correlate bridge and PLCSIM timestamps, and consider starting w32time so the fix is durable.

## Investigations 1 and 7 — now answered

**1. Gazebo Harmonic.** Verified independently, not taken on report:

```
$ gz sim --version
Gazebo Sim, version 8.11.0
```

The coordinator's PATH note is confirmed and is a real trap. Because Harmonic
comes from the ROS vendor packages, there is **no `/usr/bin/gz`**, no
`gz-harmonic` deb, and no osrfoundation apt source. `gz` does not exist until
`/opt/ros/jazzy/setup.bash` is sourced:

```
=== BEFORE sourcing ROS 2 ===   gz NOT on PATH before sourcing
=== AFTER sourcing ===          which gz : /opt/ros/jazzy/opt/gz_tools_vendor/bin/gz
```

Consequence recorded in the document: a bare `gz` in a systemd unit, cron job
or non-login shell fails with "command not found", not with a Gazebo error.

**7. Headless graphics.** `gz sim -s -r -v 4 sim/worlds/cell.sdf` was run for
30 s under five configurations.

- **Headless genuinely works and the `gpu_lidar` renders** — a real scan with
  `frame_id = ProductSensor::post::beam` was received in every non-crashing
  case.
- **Real-time factor ~1.0** (`0.99984`, `0.99994`), matching the container.
- **WSLg does NOT give a GPU path.** OGRE enumerates and binds `/dev/dri/card0`
  via EGL and creates a GL 4.5 context on it, but Mesa then falls back:
  `libEGL warning: NEEDS EXTENSION: falling back to kms_swrast`, and
  `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)` in **all five** runs. The
  container's llvmpipe path is effectively reproduced. No future performance
  difference should be explained by "WSL has a GPU" — measured, it does not.
- **What DISPLAY changes** is only which windowing path OGRE tries first. With
  DISPLAY set it takes GLX via WSLg; unset, it throws `Couldn't open X display`
  and Gazebo logs `Trying to run in headless mode`. Identical RTF. So an X
  exception in a headless log here is normal and not a fault to chase.
- **To force headless**: `gz sim -s --headless-rendering` (preferred), or
  `env -u DISPLAY -u WAYLAND_DISPLAY`. `-s` alone is not sufficient to avoid
  touching the X server.
- **Do not set `LIBGL_ALWAYS_SOFTWARE=1`** — with DISPLAY unset Mesa refuses
  the already-selected EGL device and Gazebo **segfaults**. Crash attribution
  was confirmed by per-case log inspection, not inferred. The variable is
  pointless anyway since rendering is already software.

## Contention with the concurrent sim agent

No contention occurred. Before launching, I checked and found **no live
`gz`/`ruby`/`ros2` process** — only 12 stale `fastrtps` shm segments from a
finished run, which I deliberately left in place rather than deleting another
agent's artifacts. I then **isolated anyway**, on both transports:
`ROS_DOMAIN_ID=77` for ROS 2 and `GZ_PARTITION=m307probe` for Gazebo transport
(gz does not use DDS or `ROS_DOMAIN_ID`, so the ROS variable alone would not
have isolated the simulation). All five runs were bounded by `timeout` and
driven to completion in the foreground; I verified no leftover `gz` processes at
the end.

One process-hygiene miss worth recording: my first attempt used a `pkill`
pattern (`gz sim -s -r`) that did not match the actual command line
(`gz sim -r -s`), leaving two `gz` processes running between steps. I caught it
in the same turn and killed them before continuing.

## Also resolved

The CRLF fix was verified independently rather than assumed: `.gitattributes`
present, commit `7d3ee4c`, `install.sh` has 0 CR, `bash -n` passes, the script
runs and reaches `Run as root (sudo).`, and WSL-side `git status` now shows 1
modified file instead of 108.

Known-unresolved item 6 from the previous revision is closed: Gazebo loaded
`cell.sdf` five times without complaint, so the `--`-in-XML-comment issue is
confirmed to affect only strict parsers like `xml.etree`, not libsdformat.

## lessons_candidates

Note: the CRLF lesson from the previous revision was already appended by the
orchestrator in `10ba8c7` and is deliberately not repeated here.

2026-07-27 | Assumed WSL2's NAT'd adapter would need DDS tuning, as is generally reported | Default discovery worked in all four tested configurations; the tuning would have been cargo-cult configuration masking nothing | Measure discovery on the actual machine before adding `ROS_LOCALHOST_ONLY` or an XML profile; note `ROS_LOCALHOST_ONLY` is deprecated in Jazzy and logs a warning

2026-07-27 | Benchmarked DrvFs with a per-row flushed CSV and nearly reported a 154x penalty as a blocker | The bridge does not write that way — `instrumentation.py` batches rows and flushes every 2 s, making the real cost ~0.2 % of wall time | Benchmark the access pattern the code actually uses, not a plausible-looking proxy; read the implementation before quantifying its cost

2026-07-27 | Treated a wall-clock anomaly as a WSL quirk to note in passing | The host's Windows Time service was stopped, making the guest clock step ~2.73 s every 30 s; had the bridge used `time.time()` this would have silently corrupted every latency figure | Before trusting timestamp-derived evidence on a new machine, verify which clock the code samples and that host and guest clocks are synchronised

2026-07-27 | Reported `cell.sdf` failing to parse as a possible CRLF casualty | It was actually `--` inside an XML comment, which the spec forbids and ElementTree enforces; CRLF was irrelevant, and Gazebo's TinyXML2 accepts the file | Confirm the mechanism of a failure with a minimal reproduction before attributing it to the environment under investigation

2026-07-27 | Assumed WSLg's `/dev/dri` meant Gazebo would render on the GPU | OGRE binds `/dev/dri/card0` via EGL and creates a GL 4.5 context, but Mesa falls back to `kms_swrast`; `GL_RENDERER` is llvmpipe in every configuration | Read `GL_RENDERER` from the ogre2 log before claiming hardware acceleration; the presence of a DRI node proves nothing

2026-07-27 | Killed a test Gazebo server with `pkill -f "gz sim -s -r"` | The real command line was `gz sim -r -s`, so the pattern never matched and two servers stayed alive between test cases | Match `pkill` patterns against observed `pgrep -af` output, and re-check for leftovers before declaring a run finished
