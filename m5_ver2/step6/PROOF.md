# Step 6 — proof ledger

The inherited system's evidence lives in `m5_ver2/step5/PROOF.md` and is
step5's, not step6's. This file fills as step6's own gates run (see the
M6.1 spec's proof gates).

```
[x] Gate 1 — two vehicles fit inside real time on this machine
```

---

## [x] Gate 1 — RTF with two vehicles

**Date:** 2026-08-20. **Verdict: GO** — worst measured two-vehicle mean
RTF **0.934**, best **0.995**, gate **0.90**.

### What was measured

`m5_ver2/step6/tools/rtf_spike.sh`, server-only: `gz sim -s -r
--headless-rendering` on `gazebo/warehouse_ver2.sdf`, no ROS stack, no
bridge, no writers, no GUI. It spawns `vehicles/f1/model.sdf` through
`/world/warehouse/create`, samples the real-time factor for 30 s, then
spawns `vehicles/f2/model.sdf` and samples for 60 s. Both models are the
Task 3 derivations, each carrying **three microScan3 safety scanners plus
one nav lidar** — four `gpu_lidar` sensors at 10 Hz per vehicle, eight in
the two-vehicle case, all rendered in software.

Both phases run on ONE server process, so the pair is a clean A/B: same
load order, same page cache, same render context. The physics step is the
world's 2 ms at 500 Hz.

```
wsl -e bash -lc "bash /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6/tools/rtf_spike.sh"
```

### Machine

```
kernel      5.15.167.4-microsoft-standard-WSL2
cpu         13th Gen Intel(R) Core(TM) i9-13900H, 20 threads
memory      15 GiB
gz sim      8.11.0
renderer    llvmpipe (LLVM 20.1.2, 256 bits), Mesa 25.2.8, Accelerated: no
```

The renderer is the point: `glxinfo -B` reports `Device: llvmpipe (LLVM
20.1.2, 256 bits)` / `Accelerated: no`, gz's own `~/.gz/rendering/ogre2.log`
reports `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)`, and every headless
server run prints `libEGL warning: NEEDS EXTENSION: falling back to
kms_swrast`. Eight `gpu_lidar` sensors are being rasterised on the CPU.

### The three runs, verbatim

Run 3 (2026-08-20T23:26:15+02:00), the cleanest, in full:

```
=== step6 RTF spike ===
date        2026-08-20T23:26:15+02:00
gz sim      8.11.0
partition   step6-rtf-spike
world       /mnt/c/Users/ozkan/projects/amr-agent/m5_ver2/step6/gazebo/warehouse_ver2.sdf
cpu         13th Gen Intel(R) Core(TM) i9-13900H, 20 threads
kernel      5.15.167.4-microsoft-standard-WSL2
spawning f1 at (-3.00, -5.50, 0.05) yaw 0.0
  f1 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [-3.000000 -5.500000 -0.000001]
    [0.000000 0.000000 0.000000]
sampling /world/warehouse/stats for 30s (one-vehicle)...
one-vehicle samples  296  mean RTF 0.999  min 0.944  max 1.061
spawning f2 at (3.00, -5.50, 0.05) yaw 3.14159
  f2 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [3.000000 -5.500000 -0.000001]
    [0.000000 0.000000 3.141590]
sampling /world/warehouse/stats for 60s (two-vehicle)...
two-vehicle samples  592  mean RTF 0.995  min 0.201  max 1.830
--- gate 1: two-vehicle mean RTF vs 0.90 ---
one vehicle  0.999
two vehicles 0.995
VERDICT: GO (0.995 >= 0.90)
```

Runs 1 and 2, same script, same machine, same day:

```
run 1  23:20:15  one-vehicle samples  295  mean RTF 0.994  min 0.207  max 1.249
run 1  23:20:15  two-vehicle samples  591  mean RTF 0.934  min 0.176  max 2.064
run 1            VERDICT: GO (0.934 >= 0.90)
run 2  23:22:33  one-vehicle samples  295  mean RTF 0.976  min 0.089  max 1.726
run 2  23:22:33  two-vehicle samples  592  mean RTF 0.983  min 0.254  max 1.403
run 2            VERDICT: GO (0.983 >= 0.90)
```

| Run | 1 vehicle, 30 s | 2 vehicles, 60 s | Verdict |
|---|---|---|---|
| 1 (cold) | 0.994 (295 samples) | **0.934** (591 samples) | GO |
| 2 | 0.976 (295 samples) | 0.983 (592 samples) | GO |
| 3 | 0.999 (296 samples) | 0.995 (592 samples) | GO |

Three runs were taken because run 1 landed 0.034 above the gate and one
sample of a noisy quantity is not a measurement. It is now clear that the
spread is HOST SCHEDULING NOISE and not the cost of the second vehicle: in
run 2 the two-vehicle mean (0.983) came out ABOVE the one-vehicle mean
(0.976), which a real per-vehicle cost cannot do. Run 1's 0.934 was the
cold-cache first run of the session, and it is quoted as the floor because
it is the worst thing this gate has seen — not because it is typical.

The per-10-s breakdown of run 1's two-vehicle phase shows the same thing:
`0.985, 0.937, 0.952, 0.838, 0.985, 0.903` — a dip and a full recovery
inside one 60 s window, not a decay. Step5's single-vehicle headless
baseline of 0.998 is reproduced here at 0.999 (run 3), so the harness
measures what step5's measured.

### Both trucks are where the table put them

`data: true` from the entity factory says the request was accepted, not
that the truck is upright and clear of geometry. The script reads the
resting pose back after each spawn. Both settle from the spawn z of 0.05
to floor level with zero roll and zero pitch, at exactly the coordinates
`ipc/status_contract.py`'s VEHICLES table declares:

| Vehicle | Table spawn | Resting pose (XYZ / RPY) |
|---|---|---|
| f1 | (-3.00, -5.50, 0.05) yaw 0.0 | (-3.000000, -5.500000, -0.000001) / (0, 0, 0.000000) |
| f2 | (3.00, -5.50, 0.05) yaw 3.14159 | (3.000000, -5.500000, -0.000001) / (0, 0, 3.141590) |

No spawn was refused, nothing tipped, nothing sank, and the two trucks sit
6.00 m apart in the open south block. **The VEHICLES table needed no
change.**

### `gz stats` does not exist on this Gazebo, and that matters

The plan's spike sampled `gz stats` and averaged its `Factor[0.99]` lines.
That is Gazebo CLASSIC's command. gz-tools for Harmonic — this tree runs
gz-sim **8.11.0** — has no `stats` verb: `gz stats` prints the general help
listing `fuel gui log model msg param plugin sdf service sim topic` and
exits 0, so an awk looking for `Factor` finds nothing and the gate reports
`NO SAMPLES` against a perfectly healthy simulator.

The real source is `gz.msgs.WorldStatistics` on `/world/warehouse/stats`,
published at 10 Hz, printed by `gz topic -e` as protobuf debug text:

```
sim_time {
  sec: 8
  nsec: 74000000
}
real_time {
  sec: 9
  nsec: 753109255
}
iterations: 4037
real_time_factor: 0.99857503342729925
step_size {
  nsec: 2000000
}
```

`rtf_spike.sh` sums the `real_time_factor:` field of those messages. The
sample counts above are the arithmetic proof that it reads them: 30 s at
10 Hz is 295-296 messages and 60 s is 591-592, which is the topic's rate,
not a number anything could have invented. `stdbuf -oL` is in the pipeline
because `gz topic -e` block-buffers into a file and `timeout` ends it with
SIGTERM, which would otherwise discard the last unflushed block.

### Verdict

**GO (0.934 >= 0.90).** Two forklifts, eight software-rendered lidars,
2 ms physics: this machine carries them inside real time with the worst
observed margin at 3.8 % and the typical margin near 10 %. Task 5 may
proceed.

The margin is honest but it is not large, and everything measured here was
measured with **no ROS stack running**. The two-vehicle stack adds two
bridges, fourteen vehicle nodes and two HMIs on the same 20 threads; that
load is not in this number and is not gated by it.
