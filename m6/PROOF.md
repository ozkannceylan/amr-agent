> **Relocated 2026-08-21:** measured under `m5_ver2/step6/`; now `/m6`.
> Every capture below quotes the old paths and names — they are thetrue 
> record. When RUNNING any runbook, substitute `m6/` for `m5_ver2/step6/`
> and `m6.sh`/`windows/m6.py` for their step6 names.

# Step 6 — proof ledger

The inherited system's evidence lives in `m5_ver2/step5/PROOF.md` and is
step5's, not step6's. This file fills as step6's own gates run (see the
M6.1 spec's proof gates).

```
[x] Gate 1 — two vehicles fit inside real time on this machine
[x] Gate 2 — cross-isolation, both directions             MEASURED
[x] Gate 3 — simultaneous autonomy                        MEASURED
[x] Gate 4 — per-vehicle stale-link: silence half AND driving half
[x] Gate 5 — clean lifecycle, twice
[x] Gate 6 — the gate debt proven closed on the floor     MEASURED
              (the driving half; the DISPLAY half is open -> M6.3,
               which owns the operator-facing view: M6.2's six gates
               are the vehicle's own wire to a fleet manager, and not
               one of them puts anything on a screen)

M6.2, the VDA 5050 gates (numbered VDA 1..6 so they cannot be
confused with the six above), all measured 2026-08-21 18:31-18:49:

[x] VDA 1 — MQTT-only drive, both vehicles, distinct stations   MEASURED
[x] VDA 2 — rejections: teleop/unset, and mid-drive             MEASURED
[x] VDA 3 — cancelOrder mid-drive                               MEASURED
[x] VDA 4 — supervision loss mid-drive                          MEASURED
[x] VDA 5 — connection lifecycle: ONLINE / OFFLINE / will       MEASURED
[x] VDA 6 — state honesty under a protective-field trip         MEASURED

M6.3, the fleet gates (numbered FLEET 1..6), measured 2026-08-22
00:16-01:14 by the scripted driver + the fleet CLI, with Gate 4 re-run
01:36-01:44 after the defect it found was fixed:

[x] FLEET 1 - two transports, two vehicles, nearest idle        MEASURED
[x] FLEET 2 - queueing: three tasks, two vehicles, FIFO         MEASURED
[x] FLEET 3 - rejection recovery: teleop, requeue, re-earn      MEASURED
[x] FLEET 4 - vehicle loss mid-task        FAILED, FIXED, RE-RUN
              (run 1 failed and is kept: the cancelOrder was FINISHED
               in 132 ms and did not stop the truck, which drove
               37.09 s / 6.743 m driverless because its empty goal left
               a publisher DDS had not matched. Fixed in e3c0ddd - the
               cancel is now republished until nav confirms - and
               re-run: 3.838 s / 1.359 m, confirmed in 0.23 s over 5
               publishes, and the other vehicle completed the task.)
[x] FLEET 5 - manager restart mid-operation                     MEASURED
[x] FLEET 6 - operator truth on a lost vehicle                  MEASURED

M6.4, the traffic gates (numbered TRAFFIC 1..6), measured 2026-08-22
10:56-12:09 by the scripted driver + the fleet CLI:

[x] TRAFFIC 1 - head-on, resolved        FAILED, FIXED, RE-RUN
              (the --no-traffic control ran first and reproduced the
               jam: the two trucks closed to 3.836 m, f2's right warning
               field went at 2.295 m while it was doing 689 mm/s against
               a limit that had just become 300, and the F-model latched
               it for 203.4 s until a human pressed acknowledge. With
               traffic ON, run 1 held f2 correctly and then could not
               let it go - the vehicle refused 1,873 base extensions
               with "no order is executing - nothing to extend", because
               it read nav's ARRIVED at the end of its base as the end
               of the order. Fixed in 11bb499 and re-run: one hold of
               59.78 s, one orderUpdateId 0->1, both trucks arrived
               inside 0.25 m, 0 motor-false.)
[ ] TRAFFIC 2 - station contention                    BLOCKED
              (four runs. The WAIT is measured three times and no truck
               ever entered an occupied spur; the HANDOVER is measured
               none. A spur station cannot be handed over at all - the
               occupant releases its junction on arrival and the queued
               truck takes it three seconds before the dwell ends, which
               is a swap deadlock and is structural. The two aisle
               stations that have no junction were defeated by the
               pre-existing minimum-turning-radius orbit. Run D measured
               the release half on its own: held 18.96 s, extended,
               arrived 0.2387 m from S1.)
[x] TRAFFIC 3 - base extension is stitching, not restarting     MEASURED
[x] TRAFFIC 4 - deadlock: the NAMED REFUSAL                     MEASURED
              (no yield, and none was expected: a truck parked at the
               end of its base holds only the node under its own body,
               so the younger yielding frees nothing. The fleet named
               the swap, requeued the younger task and put it in three
               places on the operator's screen.)
[x] TRAFFIC 5 - loss with holds                       MEASURED on run 2
[x] TRAFFIC 6 - traffic never touches safety                    MEASURED

M6.5, scale to four. Its gate 1 is a STOP gate on the machine itself
and it was run first, 2026-08-22 13:02-13:45:

[ ] M6.5 GATE 1 - RTF at four                          STOP, 0.190-0.230
              (four trucks with their sixteen lidars rendering hold
               0.190/0.230/0.230 against a gate of 0.30; two trucks hold
               0.957-0.970 and the cliff is at the third. The same four
               with nothing subscribed run 0.998 - gz-sim does not
               render a lidar nobody listens to, which is also what
               M6.1's gate 1 was unknowingly measuring. Gates 2-6 are
               not started.)
              RE-RUN ON THE GPU 16:03-16:21, same matrix, WSLg d3d12 on
              the RTX 4050: four trucks hold 0.583/0.687/0.670 printed
              and 0.903/0.899/0.712 integrated -> GO, and the twelfth
              lidar's cliff is gone. The re-run also found that the
              PRINTED statistic (the mean of instantaneous factors, this
              file's convention since M6.1) is biased low on a bursty
              run: integrated over the same captures, llvmpipe's four
              trucks delivered 0.579, not 0.190. The gate is cleared in
              both configurations; the ruling that stands is about the
              renderer, not the arithmetic.

M6.5's five live gates, measured 2026-08-22 18:56-20:05 by the scripted
driver + the fleet CLI on the GPU renderer, four trucks, thirty-nine
pids. TWO PASSED AND THREE DID NOT; the three that did not are written
up at the same length as the two that did:

[x] M6.5 GATE 2 - station handover at a spur                    MEASURED
              (third staging. M6.4's blocked gate is closed: ownership
               of the entry node (-8.0,5.7) goes FREE -> f3 -> f1 ->
               FREE with the f3->f1 step atomic - it is never free
               between the two vehicles. The queued truck waited
               106.18 s, arrived 0.7990 m from S6, and both transports
               completed. 0 motor-false of 4,460 samples on all four.
               Runs A and B are kept: A measured the wait and lost the
               arrival to the S4 turning-radius orbit; B measured a
               deadlock the ledger cannot see, because the blocked truck
               was held by nav's obstacle guard and not by the ledger.)
[ ] M6.5 GATE 3 - four-vehicle traffic                 FAILED, 0 of 4
              (four crossing transports, one per truck, assigned inside
               900 ms. The fleet declared one deadlock UNRESOLVABLE in
               its own words - each truck standing on the floor the
               other needs - and live-locked on the second, 3,180 yield
               lines at 10 Hz that never drained, because wait-die frees
               the floor AHEAD of a vehicle and not the floor UNDER it.
               0 motor-false on all four; closest approach 2.513 m.)
[ ] M6.5 GATE 4 - the acceptance run                   FAILED, 1 of 8
              (eight transports over the ten stations, no intervention.
               Eight seconds in, f3 latched its protective field turning
               SOUTH OUT OF ITS OWN SPAWN POSE - 0.971 m from the west
               wall it ships 2.5 m from - and its hulk held the west
               cross-aisle for the rest of the run. Throughput 0.096
               transports/min; 1,072.9 vehicle-seconds of waiting in
               624 s; arrival errors 0.0001-0.7986 m, all inside their
               station's arrive_m; 0 motor-false on the other three.
               THE FULL-STACK RTF IS THE ONE FIGURE THAT CAME OUT WELL:
               0.575-0.580 integrated over six consecutive 60 s windows,
               four trucks, sixteen lidars rendering, against 0.30.)
[ ] M6.5 GATE 5 - degradation under loss      THREE CLAUSES OF FOUR
              (own run, not mid-acceptance, and the reason is named
               there. Requeue + reassignment to another truck 132 ms
               after the kill; the dead truck never offered work again;
               the floor not left locked. But nav drove the dead truck
               8.48 m across a junction while the ledger's pin stayed
               7.2 m behind it, and the survivor stopped 2.41 m short of
               a body the ledger could not see. M6.4 measured the same
               defect at 2.93 m.)
[x] M6.5 GATE 6 - safety untouched at four                      MEASURED
              (nine Motor drops in 67 minutes, every one named at its
               sample: four startup acknowledges and five scanners - a
               conveyor, a rack face, a wall, another truck's parked
               body, and a truck whose own agent was dead. 0 of the
               session's 157 order/instantAction publishes inside any
               of the nine +/-2 s windows. 12,720 samples per truck on
               all four at once with the ledger fully live and not one
               drop.)

M6.5 fix-up, measured 2026-08-22 21:53-23:18 over four stacks after the
owner ruled fix-and-re-run. Two of the three unticked gates were fixed
at the level they failed at; the run they were fixed for stopped on
something else entirely.

[x] POSES clear their own fields                                MEASURED
              (all four wf true at rest and V_Limit 1500, against the
               old table's T/F/F and 300 on two of them. f3 and f4 read
               2.840 m against 2.840 computed. f3's first-move turn -
               the one that latched it at the old pose - now worst-case
               2.790 m. A third guard rule, off the world SDF's own
               collision boxes, that predicts the old latch to 0.108 m.)
[x] STEP-ASIDE clears a swap deadlock                           MEASURED
              (fired twice unprompted in two live Gate 3 runs: detection
               to cancelOrder 2 ms, to the one-node ft- order 104 ms,
               the vehicle's own door accepted it, and the blocked truck
               drove the floor that freed. Two bounds want re-cutting -
               ASIDE_S 60 s against a 199 s move, and a distance BOUND
               instead of a distance preference.)
[ ] M6.5 GATE 3 - four-vehicle traffic                 FAILED, 0 of 4
              (run twice. THREE OF FOUR TRUCKS DROPPED MOTOR NOT ONCE
               in nine minutes of driving - 0/11183, 0/11184, 0/11185 -
               which no four-vehicle run had ever managed. Stopped by a
               main-aisle head-on where neither truck ever reached the
               end of its base, so the resolver correctly never fired.)
[ ] M6.5 GATE 4 - the acceptance run                   FAILED, 0 of 8
              (31 s in, ALL FOUR trucks latched inside 0.56 s, every one
               of them on a scanner reporting d = 0.000 - field_eval's
               "a broken device is not an empty room". 3 to 7 such
               samples per truck out of 7,417, all in one second, on
               eight devices at once. RTF integrated 0.445-0.523 with an
               instantaneous FLOOR of 0.010. The rig, not the cell.)
[ ] M6.5 GATE 5 - degradation under loss              NOT RE-RUN
              (Gate 4 ended with four latched trucks; a kill measured
               against a stopped fleet is worth nothing. The M6.5 result
               above stands.)
[x] A 0.000 NAMES ITS OWN BRANCH                                 ADDED
              (five: empty, muted, nan with a ray count, below-min with
               one, and stale. Carried on the existing 10 Hz fields
               message, diagnosis only, verdict proven byte-identical
               against a transcription of the code before it.)
[ ] M6.5 GATE 3 - four-vehicle traffic, COLD MACHINE      2 of 4
              (two transports completed, which has never happened at
               four; two of the four trucks drove the whole gate without
               dropping Motor once; the step-aside took the NEAR node
               this time. The other two stopped on a real body at
               0.927 m - fault empty, honest geometry.)
[ ] M6.5 GATE 4 - the acceptance run, COLD MACHINE        3 of 8
              (0.176 transports/min over 1024 s, 144.2 m travelled in
               boxes eleven to thirteen metres on a side, all seven
               arrivals inside their own arrive_m, one Motor onset per
               truck. RTF integrated 0.468-0.549 with a floor of
               0.020-0.033. Four onsets, four named causes: two real
               bodies and two stale scans - and not one nan, empty,
               muted or below-min.)
[ ] RE-RUN ON A THINNED INSTRUMENT              STOPPED ON THE FLOOR
              (owner ruling: cut the recorders, measure the floor first,
               stop if it is still ~0.01. 28 subs -> 20 and the MQTT
               wildcard -> four named topics; measured before a single
               transport with all four trucks STANDING STILL, integrated
               0.343-0.345 with a floor of 0.008 - worse than the 0.010
               the acceptance run died at. Same stack with the recorders
               OFF: 0.480, floor 0.019, against 0.578 four hours
               earlier. The recorder costs 0.137 of RTF and is still not
               the binding constraint: gz sim is server-bound at 2.2 of
               twenty cores rendering sixteen gpu_lidars. No instrumented
               configuration on this machine keeps the floor above the
               value at which the scans stop arriving.)
[x] STEP-ASIDE BOUNDS corrected to the measured ones             FIXED
              (ASIDE_S 60 s against a 199 s move, and a distance BOUND
               of 5.00 m - the longest aisle edge - where there had been
               only a distance preference that sent a truck 11.15 m down
               a connector as a single node.)
[x] TWO SPEED-POLICY DEFECTS found and fixed                    MEASURED
              (the guard band was read at the nav lidar, 1.23 m behind
               the scanners that evaluate the field, so 3.0 m at the
               lidar was 1.77 m at the fork corners - inside the field
               it existed to stay out of. And nothing guarded abeam at
               all: f3 tripped a warning field at 2.307 m with the
               encoders at -700/-700 and Motor went false 8 ms later,
               latched, while the wheels needed 300 ms to comply.)
```

**Method, per gate — M6.1 and M6.2 only** (M6.3's method is under its
own heading, M6.4's under its own): 1, 4 (silence) and 5 were measured
WSL-side with no writer attached. **2, 3, 6 and Gate 4's driving half
were measured on 2026-08-21 by the scripted driver plus the ROS CLI —
no panel, no human**, and every number in them is a capture off this machine. **The
six VDA gates were measured the same way on the same day**, with two
instruments instead of one: the ROS recorder, and a paho subscriber on
`uagv/v2/amragent/+/#` that records what a fleet manager would have
seen. No order in that run was ever sent from an HMI.

**The panels were never opened.** `windows/step6.py`'s Tk panel is still
the owner's tool and nothing in this build has clicked it; what changed
is that its four inputs — E-Stop, RESET, the encoder fault mode and the
lamp — now also arrive over a UDP command socket, through
`tools/scripted_writer.py` (commit `4f7526b`), which imports `step6` and
runs the same `step6.control_loop` on the same sockets to the same PLC
model. The operator is synthetic; the production path under test is not.
The HMI's own three clicks — Auto, a station dot, GO — were published on
the two topics `hmi/hmi_node.py` publishes, at the QoS it declares.

**One genuinely human item is left in this tree, and it is inherited:**
step5's joystick-drag minute — a hand on the HMI knob, which no topic
substitutes for because `/fN/hmi/cmd_vel` is already published at 20 Hz
by the running window. Every gate in THIS file is machine-measured. The
numbered runbooks at the foot of the file are kept, unchanged, for the
owner's hands-on re-run.

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

---

## Full-stack RTF — recorded beside Gate 1, gated by nothing

Gate 1's numbers are **server-only**: `gz sim -s` and two models, no ROS.
The sentence above ends by naming what that leaves unmeasured, so it was
measured. On 2026-08-21, with the whole 17-pid stack up headless (the run
recorded under Gate 5 below), `/world/warehouse/stats` was sampled twice
for 60 s each, by the same method `tools/rtf_spike.sh` uses — `stdbuf -oL
gz topic -e -t /world/warehouse/stats` under `GZ_PARTITION=step6`, summing
the `real_time_factor:` field:

| Sample | Start | Samples | Mean RTF | Min | Max |
|---|---|---|---|---|---|
| A | 08:32:51+02:00 | 577 | **0.755** | 0.030 | 1.872 |
| B | 08:34:01+02:00 | 574 | **0.734** | 0.034 | 1.886 |

Per-10 s, the two runs:

```
A   0.815, 0.799, 0.592, 0.681, 0.818, 0.845
B   0.795, 0.754, 0.553, 0.783, 0.777, 0.742
```

**This is evidence, not a verdict.** Gate 1 is a spike gate on the
simulator and it passed on its own terms; nothing in the spec gates the
number above, and no design decision is being taken from it here.

What it says: **the ROS stack costs roughly a quarter of real time.**
Server-only ran 0.934-0.995 across three runs; the same world under two
bridged vehicles, fourteen vehicle nodes, two HMIs and one bridge process
runs 0.73-0.76 — consistent across both samples and across all twelve
10-second buckets (0.553 worst, 0.845 best), so this is a LOAD FLOOR and
not the scheduling noise Gate 1 diagnosed in its own spread.

Two things follow, and both are for M6.2 rather than for this copy:

- **A 0.75 RTF does not break the 20 ms loops** — every loop in the tree
  is wall-clock timed (`rclpy` timers, `time.monotonic()` staleness), so
  they run at their real rates regardless; what stretches is *simulated*
  time per wall second. It does mean a demo run takes ~33 % longer than
  the sim clock suggests, and that any future gate written in sim seconds
  has to say which clock it means.
- **The margin to a third vehicle is now the interesting number.** Gate 1
  measured the simulator's headroom; this measures the machine's. Nothing
  here was run with the two Windows writers attached, which add two more
  processes and two UDP streams at 50 Hz.

No writer was running for either sample. Both were taken on the machine
Gate 1 names above.

---

## The live stack, 2026-08-21 — what came up

Everything below (Gate 4's silence half, Gate 5, the full-stack RTF) was
measured on this one stack, WSL-side only, **no Windows writers**. That is
not a shortcut and not a limitation either: the no-writer state IS what
the fail-safe gates need — a vehicle that has never been told anything by
a PLC must sit inhibited, and only a stack with no writer can show it.
The four gates that DO need a writer got one later the same day, from
`tools/scripted_writer.py` rather than from the panel; see "The machine
run" below.

```
$ ./step6.sh deploy
instantiated /mnt/c/.../m5_ver2/step6/vehicles/f1
instantiated /mnt/c/.../m5_ver2/step6/vehicles/f2
deployed 17 files to /mnt/c/.../m5_ver2/step6/deploy

$ ./step6.sh start --headless
starting the Step 6 vehicle side (partition step6, domain 96, gui false)
  world pid 18299
  plc_link_f1 pid 18673      plc_link_f2 pid 18910
  cmd_gate_f1 pid 18679      cmd_gate_f2 pid 18925
  cmd_mux_f1 pid 18687       cmd_mux_f2 pid 18971
  field_eval_f1 pid 18733    field_eval_f2 pid 19001
  encoder_link_f1 pid 18763  encoder_link_f2 pid 19047
  sensor_link_f1 pid 18780   sensor_link_f2 pid 19078
  nav_node_f1 pid 18828      nav_node_f2 pid 19103
  hmi_f1 pid 18855           hmi_f2 pid 19132

up. On Windows, one writer per vehicle:
  python m5_ver2\step6\windows\step6.py --vehicle f1 --virtual
  python m5_ver2\step6\windows\step6.py --vehicle f2 --virtual
```

(The two columns are one column in the real output, f1's eight then f2's
eight; they are folded here to fit.) **Seventeen pids, one world and two
full vehicle sets.** No `WARNING: <name> exited during startup`, no `THE
STACK IS INCOMPLETE.` — and those lines are not decorative: `start`
re-reads every recorded pid a second after the last spawn and prints one
per dead child. Seventeen silent lines is seventeen live processes.

### Two namespaces, mirrored, and no `/forklift/` anything

`ros2 topic list` under `ROS_DOMAIN_ID=96` returns **65** names: 31 under
`/f1/`, the same 31 under `/f2/`, and `/clock`, `/parameter_events`,
`/rosout`.

```
/f1/auto/cmd_vel                          /f2/auto/cmd_vel
/f1/auto/goal                             /f2/auto/goal
/f1/auto/state                            /f2/auto/state
/f1/cmd/fork_speed                        /f2/cmd/fork_speed
/f1/cmd/steer_angle                       /f2/cmd/steer_angle
/f1/cmd/traction_speed                    /f2/cmd/traction_speed
/f1/fork_height                           /f2/fork_height
/f1/gz/actuator/fork_cmd                  /f2/gz/actuator/fork_cmd
/f1/gz/actuator/steer_cmd                 /f2/gz/actuator/steer_cmd
/f1/gz/actuator/traction_cmd              /f2/gz/actuator/traction_cmd
/f1/gz/drive_speed/read_a                 /f2/gz/drive_speed/read_a
/f1/gz/drive_speed/read_b                 /f2/gz/drive_speed/read_b
/f1/gz/fork_cmd                           /f2/gz/fork_cmd
/f1/gz/odom                               /f2/gz/odom
/f1/gz/safety_scanner_back/measurement    /f2/gz/safety_scanner_back/measurement
/f1/gz/safety_scanner_left/measurement    /f2/gz/safety_scanner_left/measurement
/f1/gz/safety_scanner_right/measurement   /f2/gz/safety_scanner_right/measurement
/f1/gz/scan_nav                           /f2/gz/scan_nav
/f1/gz/steer_cmd                          /f2/gz/steer_cmd
/f1/gz/traction_cmd                       /f2/gz/traction_cmd
/f1/hmi/cmd_vel                           /f2/hmi/cmd_vel
/f1/hmi/mode                              /f2/hmi/mode
/f1/joint_states                          /f2/joint_states
/f1/linear_speed                          /f2/linear_speed
/f1/odom                                  /f2/odom
/f1/plc/status                            /f2/plc/status
/f1/safety/encoders                       /f2/safety/encoders
/f1/safety/fields                         /f2/safety/fields
/f1/safety/torque_off_applied             /f2/safety/torque_off_applied
/f1/safety/torque_off_demand              /f2/safety/torque_off_demand
/f1/vehicle/cmd_vel                       /f2/vehicle/cmd_vel
```

```
$ ros2 topic list | grep -E '^/forklift/'
(none)
```

The step5 spellings are gone from the wire, not merely unused: the whole
`/forklift/...` family returns nothing.

> **First list is not the list.** The `ros2` daemon answered the first two
> queries with 10 topics, then 4 — partial discovery, mid-fill. `ros2
> daemon stop && ros2 daemon start`, eight seconds, then the 65 above,
> stable. Anyone reading a short topic list as a missing vehicle is
> reading the daemon's cache, not the stack.

### Each vehicle bound its own PLC port

```
$ grep bound logs/plc_link_f1.log logs/plc_link_f2.log
logs/plc_link_f1.log:[INFO] [plc_link]: bound 0.0.0.0:5110, publishing /f1/plc/status and /f1/safety/torque_off_demand
logs/plc_link_f2.log:[INFO] [plc_link]: bound 0.0.0.0:5120, publishing /f2/plc/status and /f2/safety/torque_off_demand

$ ss -uln | grep -E ':(5110|5120)'
UNCONN 0 0  0.0.0.0:5110  0.0.0.0:*
UNCONN 0 0  0.0.0.0:5120  0.0.0.0:*
```

5110 and 5120 are the `VEHICLES` table's `plc_port` values. Two processes,
two ports, no EADDRINUSE: the port pair really is per vehicle and not per
project.

### Expected noise, on the record so nobody debugs it

- `forklift_io_f1` / `forklift_io_f2` log `waiting for source data:
  joint_states=False, odom=False` every ~5 s, 150 times over this run.
  **Inherited from step5 and documented in
  `gazebo/step6_world.launch.py`**: joint states are deliberately not
  bridged (no consumer), and `forklift_io` subscribes `topics.odom`
  (`/<vid>/odom`, publisher count 0) while the bridge publishes
  `topics.gz_odom` (`/<vid>/gz/odom`, which `nav_node` and the HMI sketch
  do consume). It gates two derived state scalars and the fork-target
  seed, never traction or steer.
- `sto_contactor_f1` and `sto_contactor_f2` each log `TORQUE OFF: latch
  OPEN` once at startup. That is the correct answer to a PLC that has said
  nothing — see Gate 4 below.
- `gz_server` warns `XML Element[gz_frame_id] ... not defined in SDF` five
  times per model. Inherited SDF noise, both vehicles alike.

---

## [x] Gate 4 — per-vehicle stale-link: the SILENCE half

**Spec:** *silencing one vehicle's 5111-family link fails that vehicle
safe (fields False, 0/3000) and leaves the other driving.*

**Measured here: the fail-safe half, on both vehicles at once.** With no
writer on either port, neither vehicle has ever received a PLC status, and
`is_stale` reads never-received as stale — so both must sit inhibited:

```
$ ros2 topic echo /f1/plc/status std_msgs/msg/String --once
data: '{"estop_healthy": false, "motor": false, "case": 3, "v_limit": 300, "ts": 0.0}'
---
$ ros2 topic echo /f2/plc/status std_msgs/msg/String --once
data: '{"estop_healthy": false, "motor": false, "case": 3, "v_limit": 300, "ts": 0.0}'
```

Byte-identical, and every field is the safe one: `motor: false` (no
drive), `case: 3` (the most restrictive monitoring case), `v_limit: 300`
(creep), `estop_healthy: false`, `ts: 0.0` (nothing was ever timestamped
because nothing ever arrived). Repeated on the second lifecycle (pids
21060/21259) with the same two payloads.

The chain below it agrees, per vehicle:

```
[sto_contactor_f1] TORQUE OFF: latch OPEN. Traction terminal driven to
0.000 rad/s and held ... Every command is now refused, including a
permissive envelope. Only the demand falling closes this latch.
[sto_contactor_f2] TORQUE OFF: latch OPEN. ... (same)
```

Two contactors, two independent latches, from two independent
`/fN/safety/torque_off_demand` streams.

**The driving half** — one vehicle's link silenced while the OTHER keeps
driving — was measured on 2026-08-21 by the scripted driver, and has its
own section under "The machine run" below: `sensor_link_f1` killed with
both trucks EN-ROUTE, f1's six field inputs False on the wire **0.4236 s**
later against a 0.42 s budget, and f2 driving on to its station with
**0 of 250** motor-false samples over the same window.

**What already covers the writer's side of it:**
`tests/test_step6_virtual_loop.py::test_a_silent_sensor_link_fails_safe`
runs the real `step6.control_loop` against `VirtualFPLC` over real UDP
sockets, parameterised `[f1]` and `[f2]`, and asserts no status payload
reports Motor True once the sensor stream stops. That is loop-level
evidence on both port pairs; it is not a floor run and does not claim to
be.

---

## [x] Gate 5 — clean lifecycle, twice

**Spec:** *`step6.sh start`/`stop` twice in a row: no port squatters, no
orphans, `stop` names everything it killed.*

### Cycle 1 — stop

```
$ ./step6.sh stop
  swept 18306 (gz sim)                 swept 18299 (step6_world.launch.py)
  swept 18307 (parameter_bridge)       swept 18309 (sto_contactor.py)
  swept 18312 (sto_contactor.py)       swept 18310 (forklift_io.py)
  swept 18313 (forklift_io.py)         swept 18673 (plc_link.py)
  swept 18910 (plc_link.py)            swept 18679 (cmd_gate.py)
  swept 18925 (cmd_gate.py)            swept 18687 (cmd_mux.py)
  swept 18971 (cmd_mux.py)             swept 18855 (hmi_node.py)
  swept 19132 (hmi_node.py)            swept 18733 (field_eval.py)
  swept 19001 (field_eval.py)          swept 18780 (sensor_link.py)
  swept 19078 (sensor_link.py)         swept 18763 (encoder_link.py)
  swept 19047 (encoder_link.py)        swept 18828 (nav_node.py)
  swept 19103 (nav_node.py)
  killed 18673 ... killed 19132        (all 16 vehicle-node pids, in
                                        pidfile order)
down.
```

(Folded two per line to fit; the real output is one per line, and the
`killed` block is sixteen consecutive lines, not an elision in the tool.)

**23 swept, 16 killed, and the arithmetic is the point.** 17 pids were
recorded; `stop` swept 23, because the world launch owns six children the
pidfile never saw — `gz sim`, `parameter_bridge`, two `sto_contactor.py`
and two `forklift_io.py`. `PATTERNS` nominates them, `ours()` confirms
each one's `GZ_PARTITION`, and every single one is named on its way out.
Nothing is killed silently and nothing is left behind.

After it:

```
$ ss -uln | grep -E ':(5110|5120)'
(both free)
$ pgrep -f 'gz sim|plc_link.py|...|forklift_io.py'
(none)
$ test -f .step6_pids
removed
```

### Cycle 2 — start, refuse, stop

`start --headless` again, immediately: **17 pids** (world 20686 through
`hmi_f2` 21536), no startup warnings, `bound 0.0.0.0:5110` and `bound
0.0.0.0:5120` again in the fresh logs, both ports in `ss`, 17 lines in the
pidfile. Both `/plc/status` payloads FAILSAFE again, identical to cycle 1.

A third `start` on top of the live stack was refused, which is the
squatter check from the other side:

```
$ ./step6.sh start --headless
already running (pid 20686, see .../m5_ver2/step6/.step6_pids). Run './step6.sh stop' first.
exit=1
```

`stop` again: the same 23 swept, the same 16 killed — and then one more
line after the two-second grace:

```
  swept 21241 (hmi_node.py)
down.
```

**That trailing line is the design working, not a leak.** `stop` sends
TERM, waits 2 s, then sweeps KILL, because "past the grace nothing exits
on its own". `hmi_f1` sat in Tk's mainloop and ignored TERM; the KILL pass
took it and *named it*. A `stop` that had printed "down." over a live HMI
is exactly the failure this second pass exists to prevent.

Final state, after the second stop:

```
$ ss -uln | grep -E ':(5110|5120)'
(both free)
$ pgrep -af 'gz sim|plc_link.py|cmd_gate.py|cmd_mux.py|field_eval.py|encoder_link.py|sensor_link.py|nav_node.py|hmi_node.py|step6_world|parameter_bridge|sto_contactor.py|forklift_io.py'
(nothing but the grep's own shell)
$ test -f .step6_pids
removed
```

**Two full cycles, zero orphans, zero held ports, every kill named.**

A third cycle was run afterwards, timed: **`start --headless` takes 8.8 s** to seventeen live pids with zero warning lines, and its `stop` ended with the same trailing `swept ... (hmi_node.py)` KILL-pass line, both ports free and the pidfile gone. The trailing line is reproducible, which is what makes it a property of Tk's mainloop rather than an event.

---

# The machine run, 2026-08-21 10:26–11:00

Gates 2, 3, 6 and Gate 4's driving half, **measured by the scripted
driver + CLI — no panel, no human; the runbooks below remain for the
owner's hands-on re-run.** Each gate keeps its runbook's pass criteria
unchanged; only the operator is substituted, action for action:

| Runbook action | What the machine did instead |
|---|---|
| Click **RESET** on `fN`'s panel | `{"ack": true}` to 127.0.0.1:5910 (f1) / :5920 (f2) |
| Read the panel lamp | `{"status": true}` → the writer's own `motor` + status line |
| Click **Auto** | publish `/fN/hmi/mode` `auto`, TRANSIENT_LOCAL depth 1 |
| Click a station dot, press **GO** | publish `/fN/auto/goal` with a `stations.py` id |
| Drive `fN` into a rack (Gate 2) | spawn a 0.4 m static box 0.70 m off its BACK scanner |
| `ros2 topic echo … > file` | one recorder process, one line per sample, timestamped |

## Setup, verbatim

```
$ ./step6.sh deploy
instantiated .../m5_ver2/step6/vehicles/f1
instantiated .../m5_ver2/step6/vehicles/f2
deployed 17 files to .../m5_ver2/step6/deploy

$ ./step6.sh start --headless
starting the Step 6 vehicle side (partition step6, domain 96, gui false)
  world pid 25981
  plc_link_f1 26355    cmd_gate_f1 26361     cmd_mux_f1 26369
  field_eval_f1 26396  encoder_link_f1 26421 sensor_link_f1 26462
  nav_node_f1 26482    hmi_f1 26540
  plc_link_f2 26544    cmd_gate_f2 26599     cmd_mux_f2 26655
  field_eval_f2 26702  encoder_link_f2 26743 sensor_link_f2 26779
  nav_node_f2 26806    hmi_f2 26851
```

Seventeen pids, no `exited during startup`. (The pid lines are folded
three to a row here; the real output is one per line.) Then, on Windows,
one **scripted** writer per vehicle instead of one panel per vehicle:

```
> python m5_ver2\step6\tools\scripted_writer.py --vehicle f1 --virtual --ctl-port 5910
> python m5_ver2\step6\tools\scripted_writer.py --vehicle f2 --virtual --ctl-port 5920
```

started detached with `Start-Process … -RedirectStandardOutput
logs\scripted_writer_f1.log` (and `_f2.log`). The first four lines of
each, side by side:

```
logs/scripted_writer_f1.log                 logs/scripted_writer_f2.log
streaming PLC state to 172.19.180.72:5110   streaming PLC state to 172.19.180.72:5120
VIRTUAL F-PLC (model) - PLCSIM Advanced     VIRTUAL F-PLC (model) - PLCSIM Advanced
  is not in this loop                         is not in this loop
listening for the back scanner              listening for the back scanner
  on 0.0.0.0:5111                             on 0.0.0.0:5121
control channel on 127.0.0.1:5910           control channel on 127.0.0.1:5920
```

Both writers were reading their sensor port before anything was
acknowledged — their own status lines already said `PF b/r/l=T/T/T  WF
b/r/l=T/T/T`, which is a live WSL→Windows 5111/5121 link and not a
default. RESET, twice, and the lamp read back:

```
10:26:20  ->127.0.0.1:5910  {"ack":true}
10:26:20  ->127.0.0.1:5920  {"ack":true}
10:26:22  ->127.0.0.1:5910  {"status":true}
reply {"motor": true, "line": "E-Stop=True   Motor=True   ack=False |
       PF b/r/l=T/T/T  WF b/r/l=T/T/T | case=1  V_Limit=1500   enc=0/0 ok"}
10:26:22  ->127.0.0.1:5920  {"status":true}
reply {"motor": true, ... identical ...}
```

and the same fact off the wire, one subscriber at a time:

```
$ timeout 3 ros2 topic echo /f1/plc/status std_msgs/msg/String --truncate-length 3000
data: '{"estop_healthy": true, "motor": true, "case": 1, "v_limit": 1500, "ts": 347956.8550606}'
$ timeout 3 ros2 topic echo /f2/plc/status std_msgs/msg/String --truncate-length 3000
data: '{"estop_healthy": true, "motor": true, "case": 1, "v_limit": 1500, "ts": 347961.0543038}'
```

**Two trucks enabled, from two independent PLC models, over two
independent port pairs.** Both statements — the driver's lamp and the ROS
topic — say the same thing, which is why both were taken.

## The instrument, and why it is ONE process

Every capture below is one line per sample, `<epoch> <hh:mm:ss.mmm>
<payload>`, and a `std_msgs/String`'s payload is the string itself — byte
for byte what `ros2 topic echo` prints after `data: ` — so the runbooks'
`grep -c '"motor": false'` counts apply to these files unchanged. What is
*not* the runbook is that one process holds every subscription and every
publisher a gate needs, all created before the gate starts:

```
python3 gate_rec.py <seconds> <outdir> \
    [ <tag>=<topic>=<Type> | pub=<delay_s>=<topic>=<payload>=<durability> ] ...
```

It is a scratch file, outside the repo, because it is instrumentation and
not vehicle software. Gate 2 ran it with subscriptions only; gates 3, 4
and 6 ran it with the publisher half as well, and it prints every publish
with the matched-subscriber count, so a goal that reached nobody cannot
be mistaken for a goal that was refused. Two things were still done from
outside it during a run — a UDP datagram to a writer, and `kill <pid>` —
and neither starts a ROS node. That distinction is the whole of the next
section.

**Between gates**, two things were done and both are the tree's own:
`./step6.sh home` put each truck back on the pose `status_contract`'s
VEHICLES table declares — it moves the PLANT and says so ("the PLC
latches are untouched — reset from the panel") — and, before Gate 3's
third attempt, `mode teleop` was published to both to cancel the goals
their nav still held. Neither is inside any gate's measurement window.

## The 5101 link is the fragile thing on this rig, and it cost two runs

`CONTEXT.md` already warns that more than one subscriber has stalled the
5101 link long enough to latch ESTOP1. This session measured the shape of
that warning three times, and it belongs in the record because it is a
property of the RIG, not a defect in the vehicle:

| When | What was started | Result | Link silent for |
|---|---|---|---|
| 10:26:22–10:26:59 | `ros2 daemon stop && start`, then one echo | **f1** latched | — |
| 10:37:46.879 | the recorder process (4 subscriptions) | **f2** latched, 2.6 s after START | 1 sample |
| 10:42:03.379 | two `ros2 topic pub -1` nodes, at GO | **f1** latched | 34 samples, **1.65 s** |
| 10:42:03.586 | the same two nodes | **f2** latched, 0.2 s later | 40 samples, **1.94 s** |

Every one of those latches has the same signature in the capture: a run
of `/fN/plc/status` samples carrying `"v_limit": 300` — the cycles in
which `step6.control_loop`'s `SENSOR_STALE_S` (0.40 s) had expired and it
was writing all six field inputs False — and then `"motor": false`
continuing with `v_limit` back at 1500 and every field healthy again.
f2, attempt 2, verbatim, with the two elisions marked:

```
10:41:58.429  {"estop_healthy": true, "motor": true,  "case": 1, "v_limit": 1500, ...}
10:42:03.532  {"estop_healthy": true, "motor": true,  "case": 1, "v_limit": 1500, ...}
10:42:03.586  {"estop_healthy": true, "motor": false, "case": 1, "v_limit": 300,  ...}
   ... 38 more of v_limit 300; 40 in all, spanning 1.943 s ...
10:42:05.529  {"estop_healthy": true, "motor": false, "case": 1, "v_limit": 300,  ...}
10:42:05.589  {"estop_healthy": true, "motor": false, "case": 1, "v_limit": 1500, ...}
```

The last line is the one that matters: the fields healed and the truck
stayed down. The 1.65 s and 1.94 s are how long two node start-ups held
`sensor_link` off the wire — four and five times the writer's whole
budget.

**That is the safety chain being right.** A silent safety link is a
demand, the demand latches, and the heal does not release it. What was
wrong was the measurement: starting a ROS node on this 20-thread machine,
against a graph of 65 topics and 17 nodes, starves `sensor_link` past the
writer's budget. So after 10:42 no node is started while a truck can
move, and the RESET moves to the last moment before GO — after every
process the gate needs is up and settled.

---

## [x] Gate 2 — cross-isolation, both directions

**Date:** 2026-08-21. **Verdict: PASS, both directions.** Measured by the
scripted driver + CLI — no panel, no human; the runbook below remains for
the owner's hands-on re-run.

**Spec:** *one vehicle's protective-field trip latches that vehicle's
Motor while the other's Motor, fields and encoders are untouched over the
same window; then mirrored.*

### The trip, and why a box instead of a rack

The runbook drives the target truck into the nearest rack face. A script
cannot drive it there, and driving it there would put a second variable —
the pursuit — inside a gate about isolation. So the obstacle comes to the
truck instead: a 0.4 m static box, spawned through
`/world/warehouse/create` at a pose computed from the truck's live pose.

```
$ gz model -m forklift_f1 --pose        # and forklift_f2
  - Pose [ XYZ (m) ] [ RPY (rad) ]:  [-3.000000 -5.500000 -0.000001] [0 0 0.000000]
  - Pose [ XYZ (m) ] [ RPY (rad) ]:  [ 3.000000 -5.500000 -0.000001] [0 0 3.141590]

$ gz service -s /world/warehouse/create --reqtype gz.msgs.EntityFactory \
    --reptype gz.msgs.Boolean --timeout 5000 \
    --req 'sdf_filename: "/tmp/gate2_box.sdf", name: "gate2_box",
           pose: {position: {x: -1.58, y: -5.50, z: 0.20}}'
data: true

$ gz service -s /world/warehouse/remove --reqtype gz.msgs.Entity \
    --reptype gz.msgs.Boolean --timeout 5000 \
    --req 'name: "gate2_box", type: MODEL'
data: true
```

`model.sdf` puts `safety_scanner_back` at body (0.72, 0.00) with link yaw
0, so f1's back scanner sits at world (−2.28, −5.50) pointing +x and f2's
at (+2.28, −5.50) pointing −x. A box centre 0.70 m out puts its near face
**0.50 m** from that scanner — inside the case-1 protective field (1.0 m)
— and its far face **3.66 m** from the other truck's back scanner, past
even that device's 2.5 m warning field.

**None of that geometry is asserted here; all of it is read back off the
two `/fN/safety/fields` streams.** Every `d` value either device reported
in the 39 s window, counted:

```
direction A, f1 (the tripped truck)   direction B, f2 (the tripped truck)
   308  d 4.49  SAFE                     316  d 4.49  SAFE
     2  d 4.49  PROTECTIVE                 2  d 4.49  PROTECTIVE
     2  d 0.50  SAFE                        2  d 0.50  SAFE
    89  d 0.50  PROTECTIVE                 88  d 0.50  PROTECTIVE

direction A, f2 (the bystander)       direction B, f1 (the bystander)
   323  d 4.49  SAFE                     306  d 4.49  SAFE
    90  d 3.66  SAFE                      90  d 3.66  SAFE
```

Three numbers, and every one of them is the arithmetic above: **0.50** is
the near face at the tripped truck, **3.66** the far face at the
bystander, **4.49** the other forklift when the box is not there, and the
two-sample `SAFE` at 0.50 and `PROTECTIVE` at 4.49 rows are `N_SCAN = 3`
straddling each edge. **The bystander SAW the box** — it is right there in
its scan at 3.66 m, in both directions, for 90 reports each — and called
it clear, because 3.66 m is outside a 2.5 m warning field and a 1.0 m
protective one. That is a stronger statement than not seeing it: the
isolation is not blindness.

### Direction A — f1 trips, f2 is watched

One recorder process, 42 s requested, `START 10:32:27.742` to
`END 10:33:09.747`. What each of the four files actually holds — and
these spans, not the event, are what every count in this section is taken
over:

```
direction A                       first sample   last sample     samples
  /f1/plc/status                  10:32:29.725   10:33:09.728        804
  /f2/plc/status                  10:32:30.740   10:33:09.729        783
  /f1/safety/fields               10:32:29.863   10:33:09.747        401
  /f2/safety/fields               10:32:28.615   10:33:09.719        413
direction B                       first sample   last sample     samples
  /f1/plc/status                  10:33:56.732   10:34:36.230        793
  /f2/plc/status                  10:33:54.758   10:34:36.230        833
  /f1/safety/fields               10:33:56.886   10:34:36.250        396
  /f2/safety/fields               10:33:55.620   10:34:36.220        408
```

**Every count below is file-wide**, i.e. over 39.0-41.1 s per file
depending on when that subscription matched. That OVER-covers the event
in both directions — the box exists for about 9 s of it — so a bystander zero
counted this way is a stronger statement than one counted over the trip
window alone, not a weaker one.
The whole event, merged from those four files by timestamp. The field
lines are FOLDED — the report's own `ts` and its `left` and `right`
devices are cut, and both of those read SAFE throughout — and the status
lines drop `case` (1 everywhere) and `ts`:

```
10:32:33.558  create reply data: true
10:32:33.748  f1 fields  back {"pf": true,  "wf": true,  "d": 0.5,  "level": "SAFE"}
10:32:33.847  f1 fields  back {"pf": true,  "wf": true,  "d": 0.5,  "level": "SAFE"}
10:32:33.928  f1 status  {"estop_healthy": true, "motor": true,  "v_limit": 1500, ...}
10:32:33.947  f1 fields  back {"pf": false, "wf": false, "d": 0.5,  "level": "PROTECTIVE"}
10:32:33.978  f1 status  {"estop_healthy": true, "motor": false, "v_limit": 300,  ...}
      ...
10:32:42.631  remove reply data: true
10:32:42.948  f1 fields  back {"pf": false, "wf": false, "d": 4.49, "level": "PROTECTIVE"}
10:32:43.048  f1 fields  back {"pf": true,  "wf": true,  "d": 4.49, "level": "SAFE"}
10:32:50.628  f1 status  {"estop_healthy": true, "motor": false, "v_limit": 1500, ...}
10:32:50.633  ->127.0.0.1:5910  {"ack":true}
10:32:50.678  f1 status  {"estop_healthy": true, "motor": true,  "v_limit": 1500, ...}
```

Four numbers fall out of that column:

- **`d` sits at 0.5 for two scans before the level changes.** That is
  `field_eval.N_SCAN = 3` made visible: three consecutive violated scans
  decide, not one. The re-clear does the same in reverse at `d` 4.49.
- **31 ms** from the field verdict on `/f1/safety/fields` to
  `"motor": false` on `/f1/plc/status`. That 31 ms is the entire loop —
  `sensor_link` → UDP 5111 → the writer's cycle → the F-model → UDP 5110
  → `plc_link` → the topic.
- **7.58 s of healed-but-latched**, 10:32:43.048 to 10:32:50.628: the
  back device reads SAFE at 4.49 m, `v_limit` is back to 1500, and
  `motor` is still false for **152 consecutive samples**. Nothing but the
  Acknowledge closes it.
- **45 ms** from the RESET datagram to `"motor": true`.

The driver's own lamp names which device tripped, and it is only one:

```
trip  f1 driver: motor=False | E-Stop=True Motor=False | PF b/r/l=F/T/T  WF b/r/l=F/T/T | case=1 V_Limit=300
heal  f1 driver: motor=False | E-Stop=True Motor=False | PF b/r/l=T/T/T  WF b/r/l=T/T/T | case=1 V_Limit=1500
ackd  f1 driver: motor=True  | E-Stop=True Motor=True  | PF b/r/l=T/T/T  WF b/r/l=T/T/T | case=1 V_Limit=1500
```

**And f2, over its whole file (10:32:30.740 – 10:33:09.729, 38.99 s, which
contains the entire 9.1 s the box was in the world):**

```
$ grep -c '"motor": false' f2_status.txt   ->   0        (of 783 samples)
$ grep -c '"motor": true'  f2_status.txt   ->   783
$ grep -c '"pf": false'    f2_fields.txt   ->   0        (of 413 reports)
```

f2's driver line was read at the trip, at the heal and after f1's reset,
and said `PF b/r/l=T/T/T  WF b/r/l=T/T/T`, `V_Limit=1500`, `enc=0/0 ok`
**every time**. Its own field capture is unanimous — `grep -o '"level":
"[A-Z]*"' f2_fields.txt | sort | uniq -c` returns **one line, `1239
"level": "SAFE"`**, which is 413 reports times three devices with nothing
else in it. A representative sample:

```
1787301148.615321 10:32:28.615 {"case": 1, "pf_th": 1.0, "wf_th": 2.5, "ts": 347143.270085061,
"back": {"pf": true, "wf": true, "d": 4.49, "level": "SAFE"}, "left": {"pf": true, "wf": true,
"d": 4.912, "level": "SAFE"}, "right": {"pf": true, "wf": true, "d": 3.996, "level": "SAFE"}}
```

(One capture line, wrapped over three here; nothing is cut.)

### Direction B — f2 trips, f1 is watched

The same script with the vehicles swapped and the box at (+1.58, −5.50):

| | Direction A (f1 tripped) | Direction B (f2 tripped) |
|---|---|---|
| box pose | (−1.58, −5.50, 0.20) | (+1.58, −5.50, 0.20) |
| field verdict → `"motor": false` | 31 ms | 58 ms |
| healed-but-latched | 7.58 s, 152 samples | 7.66 s, 154 samples |
| RESET → `"motor": true` | 45 ms | 49 ms |
| tripped truck's samples | 334 false / 470 true | 333 false / 500 true |
| **bystander `"motor": false`** | **0 of 783** | **0 of 793** |
| **bystander `"pf": false`** | **0 of 413** | **0 of 396** |
| bystander back device saw the box at | 3.66 m, SAFE, 90 reports | 3.66 m, SAFE, 90 reports |
| bystander device-levels, all three | **1239 SAFE, nothing else** | **1188 SAFE, nothing else** |
| bystander driver line | `T/T/T`, `enc=0/0 ok` | `T/T/T`, `enc=0/0 ok` |

**Both directions: 0 and 0. Gate 2 passes.** Two trucks, two PLC models,
two port pairs, and a protective field on one of them is invisible to the
other — not by convention, but because there is no shared object between
them able to carry it.

---

## [x] Gate 3 — simultaneous autonomy

**Date:** 2026-08-21. **Verdict: PASS on the third attempt. The first two
were destroyed by the instrument and are recorded below rather than
discarded.** Measured by the scripted driver + CLI — no panel, no human;
the runbook below remains for the owner's hands-on re-run.

**Spec:** *two independent station-to-station runs with overlapping drive
time, 0 motor-false samples each, arrival radii at step5's bar.*

### The two goals, and why these two

Picked from `stations.py` and put through `route.plan_route` before
anything moved, because "non-crossing" has to be a fact about the graph
and not a hope:

```
$ PYTHONPATH=ipc python3 -c 'import route; ...'
S10 [(-3.0, -5.5), (-3.0, -5.5), (-6.0, -5.5), (-6.0, -2.5)] len 6.00 m
S4  [( 3.0, -5.5), ( 3.0, -5.5), ( 6.0, -5.5), ( 6.0, -8.0)] len 5.50 m
```

f1 → **S10 PICK-B-S**, f2 → **S4 DOCK-DOOR**. The polylines share no node
and no corridor: f1 works `x ∈ [−6, −3], y ∈ [−5.5, −2.5]`, f2 works
`x ∈ [3, 6], y ∈ [−8, −5.5]`, and the two are 6.00 m apart at their
closest point, which is the start. Every WEST station on the main aisle
was rejected for the opposite reason — Dijkstra routes them through the
`x = 0` connector (23.0 m against 26.0 m the west way), which is also
f2's shortest way north, and two trucks down one corridor is a traffic
gate, not this one. Both stations declare `arrive_m` **0.25**, the tight
end of `stations.py`'s range, so this gate is not graded on a short spur
that excuses itself.

### Attempts 1 and 2, recorded because they happened

**Attempt 1** (goals at 10:37:59): f2's ESTOP1 latched at
**10:37:46.879**, 2.6 s after the recorder started and twelve seconds
*before* the goal was published. Its nav therefore sat in `SAFETY-STOP`
at (3.000, −5.500) for the whole run — 1355 samples of it — and never
moved. f1's leg is untainted and is a result in its own right: ARRIVED at
(−5.928, −2.738), **0 of 2995** `"motor": false` samples. But a gate about
two trucks driving at once is not passed by one.

**Attempt 2** (goals at 10:42:05): **both** trucks latched, f1 at
10:42:03.379 and f2 at 10:42:03.586, while the two `ros2 topic pub -1`
processes were starting. Neither truck moved under its new goal. One
extra thing was learned here and is worth the space: acknowledging f2
while its nav still held the *previous* route resumed that route
immediately — `nav_core`'s documented "SAFETY-STOP HOLDS THE ROUTE"
behaviour, working exactly as written — and it drove 1.155 m before
latching again. The re-run therefore cancels both goals (`mode teleop`)
and homes both trucks first.

### Attempt 3, the measurement

Every publisher lives inside the recorder process and is matched before
it speaks:

```
recording 150.0 s -> /tmp/g3
will publish 'auto' on /f1/hmi/mode at +8.0 s
will publish 'auto' on /f2/hmi/mode at +8.0 s
will publish 'S10' on /f1/auto/goal at +22.0 s
will publish 'S4'  on /f2/auto/goal at +22.0 s
START 10:47:13.767
PUB 10:47:21.770 /f1/hmi/mode  <- 'auto' (2 matched subscribers)
PUB 10:47:21.770 /f2/hmi/mode  <- 'auto' (2 matched subscribers)
PUB 10:47:35.771 /f1/auto/goal <- 'S10' (1 matched subscribers)
PUB 10:47:35.771 /f2/auto/goal <- 'S4'  (1 matched subscribers)
END   10:49:43.770
f1_status  /f1/plc/status  2982 samples     f1_auto  /f1/auto/state  1475
f2_status  /f2/plc/status  2962 samples     f2_auto  /f2/auto/state  1471
```

The mode QoS is `hmi_node.py`'s and not a guess: TRANSIENT_LOCAL depth 1.
The `2 matched subscribers` are `cmd_mux` and `nav_node`, both of which
subscribe TRANSIENT_LOCAL and would have received **nothing** from a
VOLATILE publisher — the silent failure Task 6 already paid for once.
RESET went out at 10:47:26.5 as two UDP datagrams, after the node was up
and before the goals; both trucks read `motor=True` at 10:47:28.

**The two legs:**

| | f1 → S10 PICK-B-S | f2 → S4 DOCK-DOOR |
|---|---|---|
| route length | 6.00 m | 5.50 m |
| EN-ROUTE from | 10:47:35.785 | 10:47:35.870 |
| ARRIVED at | 10:47:59.285 | 10:47:57.870 |
| drive time | 23.50 s | 22.00 s |
| ARRIVED pose | (−5.9294, −2.7378) | (6.2236, −7.8889) |
| station | (−6.00, −2.50) | (6.00, −8.00) |
| **arrival error** | **0.2481 m** | **0.2497 m** |
| `arrive_m` | 0.25 | 0.25 |
| **`"motor": false` over its drive** | **0 of 470** | **0 of 440** |
| HOLD samples | 0 | 0 |
| SAFETY-STOP samples | 0 | 0 |
| state histogram | 235 EN-ROUTE / 1045 ARRIVED / 195 IDLE | 220 / 1060 / 191 |

**The overlap is the gate, and it is 21.90 s** — 10:47:35.870 to
10:47:57.770, from the later of the two EN-ROUTE starts to the last
EN-ROUTE sample before the earlier of the two arrivals. That is 21.90 s
of f2's 22.00 s drive and 93 % of f1's 23.50 s. Over exactly that
interval:

```
f1_status.txt  in [10:47:35.869 .. 10:47:57.769]: 438 samples, 0 contain '"motor": false'
f2_status.txt  in [10:47:35.869 .. 10:47:57.769]: 438 samples, 0 contain '"motor": false'
```

**876 status samples across two trucks driving at the same time, and not
one of them reports a stopped motor.** Both arrivals are inside the
0.25 m radius the station declares — step5's tight bar, which recorded
0.216 m and 0.245 m at this same S10 — and not the 0.80 m short-spur
allowance. Neither truck entered HOLD or SAFETY-STOP at any point.

The `"motor": false` counts over the whole 150 s files are 237 (f1) and
217 (f2), and every one of them precedes the RESET at 10:47:26.5: the
trucks began the recording latched from the previous gate, which is the
state a RESET exists for. The drive-window counts above are the gate's.

---

## [x] Gate 4 — the DRIVING half

**Date:** 2026-08-21. **Verdict: PASS.** Measured by the scripted driver +
CLI — no panel, no human; the runbook below remains for the owner's
hands-on re-run. (The silence half is measured further up this file. The
two halves sit in different sections because they were measured on
different days; each stands alone.)

**Spec:** *one vehicle's sensor link silenced while the OTHER is driving,
the other unaffected.*

Both trucks were sent to the Gate 3 stations again, so the corridors are
still disjoint and the routes still known. The pid came from the line the
runbook names and was **verified before the signal**:

```
$ sed -n '7p' .step6_pids
26462
$ xargs -0 echo < /proc/26462/cmdline
python3 .../m5_ver2/step6/deploy/m5_ver2/step6/ipc/sensor_link.py
$ xargs -0 -n1 echo < /proc/26462/environ | grep '^VEHICLE='
VEHICLE=f1
```

Goals published 10:52:49.170, both trucks EN-ROUTE. Ten and a half
seconds in, with f1 mid-corner and f2 mid-aisle:

```
$ date +%s.%N; kill 26462; echo rc=$?; date +%s.%N
1787302379.805225432
rc=0
1787302379.806394598
```

### f1: the timeline, from two independent captures

```
kill                                       10:52:59.805225
/f1/plc/status   last "motor": true        10:53:00.178769  (v_limit 1500)
/f1/plc/status   first "motor": false      10:53:00.228854  (v_limit 300)
/f1/gz/odom      still 0.2398 m/s at       kill + 0.424 s
/f1/gz/odom      0.0902 m/s at             kill + 0.478 s
/f1/gz/odom      standstill at             kill + 0.599 s
```

- **Kill → `"motor": false` on `/f1/plc/status`: 0.4236 s**, end to end,
  and that is an UPPER bound on the trip, not a decomposition of it. The
  runbook's writer-side budget is `SENSOR_STALE_S` 0.40 + `CYCLE_S` 0.02
  = **≤ 0.42 s** to writing the six field inputs False, and `/f1/plc/status`
  is sampled at 20 Hz, so up to **50 ms** of the 0.4236 s is nothing but
  the grain of the topic the answer arrived on. Two quantities this
  capture does not contain: the phase of the last 10 Hz sensor datagram
  before the kill (which decides where inside the 0.40 s window the
  writer's clock actually started) and where inside a publish period the
  first False landed. **So the chain's internal split cannot be derived
  from this run** — what can be said is that the whole of it, writer
  budget and publish grain included, completed in 0.4236 s against a
  runbook that allows "about a second".
- **The truck kept its last command for that window and no longer.** It was doing 0.2395 m/s at the kill (mid-corner, where the
  pursuit's own corner band and not the PLC sets the speed), held ~0.24
  m/s through kill+0.424, and was stopped at kill+0.599: **0.0666 m of
  travel from the kill to standstill.**
- The writer's own lamp afterwards names every input it tripped:

```
post f1 driver: motor=False | E-Stop=True Motor=False |
                PF b/r/l=F/F/F  WF b/r/l=F/F/F | case=1 V_Limit=300 enc=0/3000
```

  `F/F/F` on all six field inputs and `enc=0/3000` — `ENC_STALE_A/B`, the
  deliberately implausible pair. Six inputs and the encoder cross-check,
  all driven to the demanding side by one dead link.

### f2: still driving, over the same window

```
f2_status.txt  total 2384  span 10:52:28.090 .. 10:54:27.129
   "motor": false         0
   "motor": true          2384
f2_status.txt  in [10:52:59.805 .. 10:53:12.299]: 250 samples, 0 contain '"motor": false'
```

That second window runs from the kill to 1.3 s past f2's ARRIVED, so it
covers every sample between the two events. **0 of 2384 over the whole
run, and 0 of 250 from the kill through the arrival.** f2 went EN-ROUTE at 10:52:49.271 and ARRIVED at 10:53:10.971 —
21.7 s, of which **11.2 s were after f1's link died** — at
(6.2147, −7.8751), **0.2484 m** from S4 against `arrive_m` 0.25. It did
not notice, and there is no mechanism by which it could have.

f1 stays down, as the runbook says it must: **1739 `"motor": false`**
against 611 true over the file, every one of the 1739 also carrying
`"v_limit": 300` — 86.9 s unbroken, which is the permanent form of the
1.65 s transient in the rig note above. Nothing heals a killed node.

---

## [x] Gate 6 — the gate debt proven closed on the floor

**Date:** 2026-08-21. **Verdict: PASS.** Measured by the scripted driver +
CLI — no panel, no human; the runbook below remains for the owner's
hands-on re-run.

**Spec:** *`cmd_mux` killed under Motor True: the plant sees zeros inside
`CMD_STALE_S`, no repeat of step4's 14.8 m class.*

**Run on f2, and here is why.** Gate 4 killed `sensor_link_f1`, and a
killed node cannot be restored without bouncing the whole stack. Both
routes were open — a stack bounce between gates is fine, and each gate's
evidence stands alone — and the cheaper one was to run the mux kill on
the truck that was still whole. Both trucks had been put back on their
spawn poses by `./step6.sh home` before this gate; f2 was enabled and
healthy there, and f1 stood beside it with its six field inputs False and
no `sensor_link` to change them.

The pid, verified the same way:

```
$ sed -n '12p' .step6_pids        # 1 world, 2-9 f1, 10-17 f2
26655
$ xargs -0 echo < /proc/26655/cmdline
python3 .../m5_ver2/step6/deploy/m5_ver2/step6/ipc/cmd_mux.py
$ xargs -0 -n1 echo < /proc/26655/environ | grep '^VEHICLE='
VEHICLE=f2
```

**The kill lands at cruise, decided by the odometry and not by a
stopwatch.** `/f2/auto/goal` ← `S4` at 10:57:25.879; the driver polled
`/f2/gz/odom` and fired the moment it read `follower.CRUISE_MPS`:

```
odometry says 0.7000 m/s - killing cmd_mux_f2 (pid 26655)
$ date +%s.%N; kill 26655; echo rc=$?; date +%s.%N
1787302646.551050401
rc=0
1787302646.551797832
```

### The coast, sample by sample

```
  t_kill-0.687  (3.0000, -5.5000)  |v| 0.0000   <- /f2/auto/goal <- 'S4'
  t_kill-0.533  (3.0110, -5.5000)  |v| 0.2433
  t_kill-0.426  (3.0565, -5.4999)  |v| 0.5956
  t_kill-0.352  (3.0908, -5.4999)  |v| 0.7000
  t_kill-0.036  (3.2308, -5.4997)  |v| 0.7000   <- last sample before the kill
  t_kill+0.014  (3.2658, -5.4997)  |v| 0.7000
  t_kill+0.097  (3.3008, -5.4997)  |v| 0.7000
  t_kill+0.147  (3.3358, -5.4997)  |v| 0.7000
  t_kill+0.204  (3.3708, -5.4996)  |v| 0.7000
  t_kill+0.255  (3.4058, -5.4996)  |v| 0.7000   <- last full-speed sample
  t_kill+0.394  (3.4369, -5.4996)  |v| 0.5693
  t_kill+0.478  (3.4592, -5.4996)  |v| 0.3927
  t_kill+0.631  (3.4726, -5.4996)  |v| 0.2161
  t_kill+0.705  (3.4773, -5.4996)  |v| 0.0397
  t_kill+0.846  (3.4773, -5.4996)  |v| 0.0000   <- standstill, and it stays
```

**0.2465 m from the kill to standstill, in 0.846 s, from 0.700 m/s** —
measured from the **last odometry sample before the kill**, which is
36 ms early. Extrapolating that sample forward at its own 0.7000 m/s to
the kill instant gives **0.221 m**, and the true figure is between the
two. Both are quoted; neither changes any verdict below.

The split inside that number is the gate itself. The truck ran at a full
0.7000 m/s until **kill + 0.255 s** and covered **0.175 m** doing it —
0.250 s × 0.700 m/s to three figures, which is `CMD_STALE_S` **0.25 s**
measured on the plant rather than read out of the source. The remaining
**0.0715 m** is the drive ramping down through 0.57, 0.39, 0.22, 0.04 to
zero.

**The runbook's bound has to be evaluated at the speed actually driven,
not at a ceiling this vehicle never reaches.** The runbook's formula is
`CMD_STALE_S` plus a tick, i.e. 0.35 s of travel; at the 700 mm/s the
follower actually cruises that allows **0.245 m**, and the measured
stale-window travel is **0.175 m** — inside it. The other **0.0715 m** is
the drive's braking ramp, which the formula does not model at all, so the
total 0.2465 m is not the quantity the formula bounds and is not compared
to it here. (The runbook's own ceiling arithmetic is wrong in passing:
0.35 s × 2.8 m/s is **0.98 m**, not "under 0.8 m". Corrected in step 14
below. Nothing measured here was ever compared against that line.)

Against the class this gate exists to kill — **step4's 14.8 m** — 0.2465 m
is **60× smaller**, and it is that class, and only that class, this
measurement retires.

### Motor STAYED TRUE, and that is the debt's exact signature

```
f2_status.txt  in [10:57:26.551 .. 10:58:53.900]: 1747 samples, 0 contain '"motor": false'
```

Six driver probes at three-second intervals over the 18 s after the kill,
all identical:

```
f2 driver: motor=True | E-Stop=True Motor=True ack=False |
           PF b/r/l=T/T/T  WF b/r/l=T/T/T | case=1 V_Limit=1500 enc=0/0 ok
```

**The chain was never asked to trip.** This is a command-path stop:
`cmd_gate` substituted zeros because its command input went silent, and
deliberately did *not* drop the enable — "the truck stops, the operator's
e-stop lamp does not lie about why", as that file says. E-Stop healthy,
all six fields clear, `V_Limit` 1500, encoders plausible, `Motor` true —
and the truck standing still. That is the fix working, and a
`"motor": false` here would have been the wrong answer to the right
event.

**One thing the fix does not do, recorded because it is still true.** The
autopilot kept publishing `EN-ROUTE` for the rest of the run — **873
samples** on `/f2/auto/state` after the kill — because `nav_node` sits
upstream of the dead mux and has no way to learn that its commands now
stop at a corpse. The debt note predicted exactly this pairing ("the
plant holds its last setpoint … while the HMI still shows a live
EN-ROUTE"). Step 6 closed the half that moves 14.8 m of forklift; the
half that misinforms a screen is still open, is one layer above this
gate, and is not what this gate was written to close.

---

## Teardown

```
> {"quit":true} -> 127.0.0.1:5910          > {"quit":true} -> 127.0.0.1:5920
shutting down: writing the trip values     shutting down: writing the trip values
writer for f1 is down                      writer for f2 is down
```

Both writers left through `control_loop`'s own `finally` — exactly as
closing the panel window would, and the same path `{"quit": true}` was
built to take. `shutting down: writing the trip values` is that `finally`
announcing itself: E-Stop and all six scanner inputs go False on the way
out, whatever the last status line said. No python process belonging to
this session survived — `Get-CimInstance Win32_Process` afterwards
returns only three VS Code language servers.

```
$ ./step6.sh stop
  swept 25988 (gz sim)   ... 21 swept lines ...   swept 26806 (nav_node.py)
  killed 26355  ...  killed 26851                 (14 killed lines)
  swept 25988 (gz sim)
down.
$ ss -uln | grep -E ':(5110|5120)'                    ->  (both free)
$ pgrep -af 'gz sim|plc_link.py|...|forklift_io.py'   ->  (nothing but the grep's own shell)
$ test -f .step6_pids                                 ->  removed
```

**21 swept and 14 killed, against Gate 5's 23 and 16 — and the arithmetic
is the point again.** Exactly two nodes are missing from each list, and
they are exactly the two these gates killed: `sensor_link.py` appears
once in the sweep (26779, f2's) and `cmd_mux.py` once (26369, f1's).
`stop` tripped over neither absence, did not print `down.` over a
survivor, and the trailing KILL-pass line is there as always.

```
$ python3 -m pytest m5_ver2/step6/tests/ -q
245 passed in 4.39s
```

---

# The VDA 5050 machine run, 2026-08-21 18:31–18:49

The M6.2 spec's six proof gates, **measured by the scripted driver + CLI
— no panel, no human**, on the live twenty-pid stack. They are numbered
here as **VDA 1..6** so they cannot be confused with the M6.1 gates
above, which keep their own numbers and their own verdicts.

```
[x] VDA 1 — MQTT-only drive, both vehicles, distinct stations   MEASURED
[x] VDA 2 — rejections: teleop/unset, and mid-drive             MEASURED
[x] VDA 3 — cancelOrder mid-drive                               MEASURED
[x] VDA 4 — supervision loss mid-drive                          MEASURED
[x] VDA 5 — connection lifecycle: ONLINE / OFFLINE / will       MEASURED
[x] VDA 6 — state honesty under a protective-field trip         MEASURED
```

The operator substitution is M6.1's, unchanged, plus two rows the VDA
gates add:

| Runbook action | What the machine did instead |
|---|---|
| Click **RESET** on `fN`'s panel | `{"ack": true}` to 127.0.0.1:5910 (f1) / :5920 (f2) |
| Read the panel lamp | `{"status": true}` → the writer's own `motor` + status line |
| Click **Auto** | publish `/fN/hmi/mode` `auto`, TRANSIENT_LOCAL depth 1 |
| Click a station dot, press **GO** | **nothing — an order over MQTT is the whole point** |
| Master control sends an order | `tools/send_order.py fN <station>` (paho, no ROS node) |
| Master control cancels | one `instantActions` publish (paho, no ROS node) |
| `ros2 topic echo … > file` | one recorder process, one line per sample, timestamped |
| Watch the fleet's side | one paho subscriber on `uagv/v2/amragent/+/#`, JSONL |

## Setup, verbatim

```
$ ./step6.sh deploy
instantiated .../m5_ver2/step6/vehicles/f1
instantiated .../m5_ver2/step6/vehicles/f2
deployed 20 files to .../m5_ver2/step6/deploy

$ ./step6.sh start --headless
starting the Step 6 vehicle side (partition step6, domain 96, gui false)
  broker pid 41859           world pid 41865
  plc_link_f1 42239    cmd_gate_f1 42245     cmd_mux_f1 42253
  field_eval_f1 42299  encoder_link_f1 42335 sensor_link_f1 42346
  nav_node_f1 42385    vda_agent_f1 42424    hmi_f1 42479
  plc_link_f2 42485    cmd_gate_f2 42520     cmd_mux_f2 42569
  field_eval_f2 42573  encoder_link_f2 42612 sensor_link_f2 42660
  nav_node_f2 42694    vda_agent_f2 42741    hmi_f2 42779
```

**Twenty pids**, no `exited during startup`. (Folded two and three to a
row here; the real output is one per line.) Then, on Windows, one
scripted writer per vehicle:

```
> python m5_ver2\step6\tools\scripted_writer.py --vehicle f1 --virtual --ctl-port 5910
> python m5_ver2\step6\tools\scripted_writer.py --vehicle f2 --virtual --ctl-port 5920
```

started detached with `Start-Process … -RedirectStandardOutput
logs\scripted_writer_f1.log`. Both were reading their sensor port before
anything was acknowledged — `PF b/r/l=T/T/T  WF b/r/l=T/T/T` on the
first cycle, which is a live WSL→Windows 5111/5121 link and not a
default — and both reported `Motor=False`, which is the startup
acknowledge the F-program demands.

RESET went out at the last moment before the first order, after every
process the gates needed was up and settled (the M6.1 rig rule, below):

```
18:34:18.334  ->127.0.0.1:5910  {"ack":true}
18:34:18.415  ->127.0.0.1:5920  {"ack":true}
18:34:20.557  ->127.0.0.1:5910  {"status":true}
reply {"motor": true, "line": "E-Stop=True   Motor=True   ack=False |
       PF b/r/l=T/T/T  WF b/r/l=T/T/T | case=1  V_Limit=1500  enc=0/0 ok"}
18:34:20.632  ->127.0.0.1:5920  {"status":true}
reply {"motor": true, ... identical ...}
```

## The two instruments, and what each is allowed to be

**ROS side: ONE recorder process**, M6.1's `gate_rec.py` with a UDP
control socket bolted on, because an M6.2 gate is not on a schedule — an
order goes out over MQTT and the truck answers when it answers. Twelve
subscriptions and two publishers, all created before the first RESET:

```
python3 rec2.py 7200 /tmp/m62/cap 5930 \
  f1_status=/f1/plc/status=String   f2_status=/f2/plc/status=String \
  f1_fields=/f1/safety/fields=String f2_fields=/f2/safety/fields=String \
  f1_nav=/f1/auto/state=String      f2_nav=/f2/auto/state=String \
  f1_goal=/f1/auto/goal=String      f2_goal=/f2/auto/goal=String \
  f1_route=/f1/auto/route=String    f2_route=/f2/auto/route=String \
  f1_odom=/f1/gz/odom=Odometry      f2_odom=/f2/gz/odom=Odometry \
  pub=mode1=/f1/hmi/mode=transient_local \
  pub=mode2=/f2/hmi/mode=transient_local
```

Its whole session, printed at the end:

```
f1_status  /f1/plc/status   18693 samples   f1_odom  /f1/gz/odom  16992
f2_status  /f2/plc/status   18719 samples   f2_odom  /f2/gz/odom  16992
f1_fields  /f1/safety/fields 9341           f1_nav   /f1/auto/state 9366
f2_fields  /f2/safety/fields 9355           f2_nav   /f2/auto/state 9347
f1_route   /f1/auto/route       5           f1_goal  /f1/auto/goal     1
f2_route   /f2/auto/route       3           f2_goal  /f2/auto/goal     1
```

**There is no goal publisher in that command line**, and that is VDA
Gate 1's central claim made structural rather than promised: the
instrument could not have published an HMI goal if it had wanted to. The
two `/fN/auto/goal` samples in the whole eighteen minutes are the
AGENT's own empty goal — one at the cancelOrder, one at the supervision
loss — and both are timestamped inside the gate that asked for them.

**MQTT side: one paho subscriber** on `uagv/v2/amragent/+/#`, one JSONL
line per message with the retain flag kept, started before the stack's
first gate and left running across the broker kill and the stack stop.
It is **not a ROS node**, so the rig rule below does not bite it, and it
is the only reader that can say what the fleet would have seen.

Two things were done from outside both instruments and neither starts a
ROS node: a UDP datagram to a writer, and `kill`. `send_order.py` and
the instantAction publisher are paho clients — by design, `send_order`'s
own docstring says so: it reads the vehicle's pose off the vehicle's own
MQTT state rather than subscribing to odom.

**Instrument noise, on the record.** PowerShell strips the double quotes
out of a native command's argument, so the first four RESET datagrams
reached the writers as `{ack:true}` and `{status:true}`. Each cost one
stderr line and nothing else — `logs/scripted_writer_f1.err` in full:

```
ignored b'{ack:true}': Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
ignored b'{status:true}': Expecting property name enclosed in double quotes: line 1 column 2 (char 1)
```

which is `serve()`'s guard doing exactly what its docstring promises.
The buttons were then driven by name through a wrapper that builds the
JSON itself, and the RESET above is that wrapper's output.

## The rig rule held: no starvation, not once

M6.1 measured 1.65 s and 1.94 s of `sensor_link` silence when ROS nodes
were started while a truck could move, and both latched ESTOP1. This run
started every ROS process before the RESET and none afterwards. The
audit is the whole session's `"motor": false` samples, grouped into runs:

```
f1: 3839 samples in 3 runs      f2: 2848 samples in 2 runs
  18:32:16.007 .. 18:34:18.297    18:32:14.397 .. 18:34:18.417
      the startup acknowledge, cleared by the RESET at 18:34:18
  18:40:48.797 .. 18:41:39.647    (none)
      VDA Gate 6's box, cleared by that gate's ack at 18:41:39.648
  18:47:31.947 .. 18:47:50.147    18:47:32.017 .. 18:47:50.167
      the writers' own trip values on {"quit": true}, at teardown
```

**Every motor-false sample in eighteen minutes belongs to a run this
file names, and none of them is an instrument.** The protective-field
audit says the same from the other side: `"pf": false` appears 596 times
on f1's back device and 179–180 times on every other device of both
trucks; 180 of f1's back count and all of the others are the first
17.9 s after start, when `field_eval`'s fail-safe direction reads "no
scan yet" as violated, and the remaining 416 are Gate 6's box and its
three-scan clearing straddle.

---

## [x] VDA Gate 1 — MQTT-only drive, both vehicles

**Date:** 2026-08-21. **Verdict: PASS.** Measured by the scripted driver
+ CLI — no panel, no human.

**Spec:** *both vehicles complete full-route orders (distinct stations)
sent over MQTT with NO HMI goal involvement — ARRIVED both, 0
motor-false each, state streams captured showing nodeStates draining and
lastNodeId advancing.*

The stations are M6.1 Gate 3's pair and for its reason: `route.plan_route`
puts f1 → **S10 PICK-B-S** on `x ∈ [−6, −3], y ∈ [−5.5, −2.5]` and f2 →
**S4 DOCK-DOOR** on `x ∈ [3, 6], y ∈ [−8, −5.5]`, sharing no node and no
corridor, 6.00 m apart at their closest point. Both declare `arrive_m`
**0.25**, the tight end of `stations.py`'s range.

```
$ python3 m5_ver2/step6/tools/send_order.py f1 S10
sent o-5336e4a5 to f1 -> S10 (3 nodes, arrive 0.25 m)
$ python3 m5_ver2/step6/tools/send_order.py f2 S4
sent o-03c71ba8 to f2 -> S4 (3 nodes, arrive 0.25 m)
```

| | f1 → S10 PICK-B-S | f2 → S4 DOCK-DOOR |
|---|---|---|
| order | `o-5336e4a5` | `o-03c71ba8` |
| route length | 6.00 m | 5.50 m |
| EN-ROUTE from | 18:34:31.078 | 18:34:32.914 |
| ARRIVED at | 18:34:53.177 | 18:34:53.514 |
| drive time | 22.099 s | 20.600 s |
| ARRIVED pose | (−5.9177, −2.7299) | (6.2144, −7.8801) |
| station | (−6.00, −2.50) | (6.00, −8.00) |
| **arrival error** | **0.2442 m** | **0.2456 m** |
| `arrive_m` | 0.25 | 0.25 |
| `"motor": false` over its own drive | **0 of 442** | **0 of 412** |
| HOLD / SAFETY-STOP samples | 0 / 0 | 0 / 0 |

**The overlap is 20.263 s** — 18:34:32.914 to 18:34:53.177, from the
later EN-ROUTE to the earlier ARRIVED. That is 98.4 % of f2's drive and
91.7 % of f1's. Over exactly that interval:

```
f1  405 status samples, 0 contain '"motor": false'
f2  406 status samples, 0 contain '"motor": false'
```

**The state stream, both trucks, drained** — one row per change, read
off the MQTT recorder:

```
   f1                                        f2
   18:34:28.847  ''          rem 0           18:34:28.707  ''          rem 0
   18:34:31.047  o-5336e4a5  rem 3           18:34:32.907  o-03c71ba8  rem 3
   18:34:31.065  o-5336e4a5  rem 2  wp1      18:34:32.951  o-03c71ba8  rem 2  wp1
   18:34:33.146  o-5336e4a5  rem 2  wp1  D   18:34:35.006  o-03c71ba8  rem 2  wp1  D
   18:34:35.063  o-5336e4a5  rem 1  wp2  D   18:34:36.868  o-03c71ba8  rem 1  wp2  D
   18:34:53.124  o-5336e4a5  rem 0  S10  D   18:34:53.428  o-03c71ba8  rem 0  S4   D
   18:34:55.246  o-5336e4a5  rem 0  S10      18:34:55.606  o-03c71ba8  rem 0  S4
```

`rem` is `len(nodeStates)`, the third column is `lastNodeId`, `D` is
`driving: true`. **`nodeStates` drains 3 → 2 → 1 → 0 and `lastNodeId`
advances wp1 → wp2 → the station**, and the order id stays on the state
after arrival, which is what `send_order --watch` reads as its finish
line. `rem` drops to 2 within 18 ms of the order: `wp1` is the truck's
own start point (`send_order` sends `poly[1:]`, and `plan_route` starts
the polyline under the truck), so `Progress` marks it on the first odom
sample.

**No HMI goal was published, by either truck, at any point in the
session:** `/f1/auto/goal` and `/f2/auto/goal` carry **one sample each
over eighteen minutes**, at 18:38:00.846 and 18:44:11.025, and both are
the agent's own empty-string goal in VDA Gates 3 and 4. `/fN/auto/route`
carries 5 (f1) and 3 (f2): f1's five are its five ACCEPTED orders, f2's
three are its two accepted orders plus VDA Gate 4's re-issue. **Not one
rejected order produced a route** — nothing below reached nav.

---

## [x] VDA Gate 2 — the two rejections

**Date:** 2026-08-21. **Verdict: PASS, both halves.** Measured by the
scripted driver + CLI — no panel, no human.

**Spec:** *an order in teleop mode and an order while one executes are
both rejected with the errors[] entry, and the vehicle's current drive
is undisturbed.*

### (a) Not in AUTOMATIC — twice, from both directions

First with the mode **never published at all** (`self.mode is None`,
which `operating_mode()` reads as `MANUAL`), before any RESET:

```
18:33:03.932  order in   uagv/v2/amragent/f1/order  o-9c6fd083
18:33:03.965  state      f1  operatingMode=MANUAL driving=False pos=(-3.0, -5.5)
   {"errorType": "orderError", "errorLevel": "WARNING",
    "errorDescription": "vehicle not in AUTOMATIC",
    "errorReferences": [{"referenceKey": "orderId",
                         "referenceValue": "o-9c6fd083"}]}
18:33:04.327  order in   uagv/v2/amragent/f2/order  o-f81c7bbc
18:33:04.424  state      f2  ... identical, referenceValue "o-f81c7bbc"
```

**33 ms and 97 ms from the order to the refusal on the wire.** Then with
`teleop` explicitly in force — the mode published on the topic and at
the QoS `hmi_node.py` declares:

```
PUB 18:33:27.022 /f2/hmi/mode <- 'teleop' (3 matched subscribers)
18:33:31.216  order in   uagv/v2/amragent/f2/order  o-5765d3a8
18:33:31.324  state      f2  operatingMode=MANUAL driving=False orderId=''
   {"errorType": "orderError", "errorLevel": "WARNING",
    "errorDescription": "vehicle not in AUTOMATIC",
    "errorReferences": [{"referenceKey": "orderId",
                         "referenceValue": "o-5765d3a8"}]}
```

The `3 matched subscribers` are `cmd_mux`, `nav_node` and `vda_agent`,
all three TRANSIENT_LOCAL — a VOLATILE publisher would have reached
none of them, which is the silent failure M6.1's Task 6 paid for once.

**Nothing moved.** `agvPosition` on every state through both refusals is
(−3.0, −5.5) and (3.0, −5.5), the spawn poses to four decimals, and
`/fN/auto/route` gained no sample.

### (b) A second order while one executes

f1 was driving `o-d6a52377` (S10 → S2 CHARGE-1, 7.90 m) when a second
order went out:

```
18:36:03.335  order in   o-d6a52377   4 nodes     (accepted)
18:36:16.723  order in   o-39c73c51   3 nodes     (S3 CHARGE-2)
18:36:16.766  state      f1  order=o-d6a52377 rem=3 last=wp1 driving=True
   {"errorType": "orderError", "errorLevel": "WARNING",
    "errorDescription": "an order is executing - cancelOrder first",
    "errorReferences": [{"referenceKey": "orderId",
                         "referenceValue": "o-39c73c51"}]}
```

**The refusal and the undisturbed drive are in the SAME state message:**
`orderId` is still `o-d6a52377`, `nodeStates` is still 3 long,
`lastNodeId` is still `wp1`, `driving` is still true, and the
`errorReferences` name the order that was turned away, not the one
running. f1 then reached S2 at **18:36:57.177**, pose
(−10.5098, −6.2402) against the station's (−9.80, −6.60) — **0.7958 m**
inside that station's declared `arrive_m` of 0.80 — with **0 of 1076**
`"motor": false` samples across the whole 53.8 s drive.

---

## [x] VDA Gate 3 — cancelOrder mid-drive

**Date:** 2026-08-21. **Verdict: PASS.** Measured by the scripted driver
+ CLI — no panel, no human.

**Spec:** *controlled stop through the normal chain, order cleared,
actionState FINISHED, truck restartable by a new order.*

> **Read forward before quoting the 97 ms below.** This gate measures
> the agent as it was on 2026-08-21: `cancelOrder` published the empty
> goal once and reported FINISHED immediately. M6.3's Fleet Gate 4
> found what that costs when the goal reaches nobody, and `e3c0ddd`
> changed the semantics - FINISHED now means nav confirmed the stop,
> and the number to compare against is that gate's 0.23 s over five
> publishes. Nothing measured here was re-run; it is a true record of
> the older contract.

f1 was driving `o-5f204f99` (S2 → S1 HOME, 7.90 m) at 0.288 m/s. The
instantAction is one paho publish — a scratch helper, not a repo file:

```
18:38:00.750  PUB uagv/v2/amragent/f1/instantActions <-
  {"headerId": 1, "timestamp": "2026-08-21T16:38:00.000Z",
   "version": "2.1.0", "manufacturer": "amragent", "serialNumber": "f1",
   "actions": [{"actionId": "cancel-g3-1", "actionType": "cancelOrder",
                "blockingType": "HARD", "actionParameters": []}]}
```

**The chain, in order, from three independent captures:**

```
18:38:00.750  the instantAction leaves the publisher
18:38:00.846  /f1/auto/goal  <- ''      (the agent's empty goal)
18:38:00.847  state: orderId '', nodeStates [], actionStates
              [{"actionId": "cancel-g3-1", "actionType": "cancelOrder",
                "actionStatus": "FINISHED"}]
18:38:00.877  /f1/auto/state: IDLE, goal null, note "cancelled"
18:38:01.126  /f1/gz/odom: |v| = 0.0000
```

**The stop is a controlled one and the number says which kind.** Odom,
every sample, around the empty goal:

```
18:38:00.817  x=-8.9665 y=-6.5937  |v|=0.2873
18:38:00.867  x=-8.9605 y=-6.5807  |v|=0.2869      <- goal published
18:38:00.917  x=-8.9552 y=-6.5695  |v|=0.2062
18:38:00.966  x=-8.9526 y=-6.5647  |v|=0.0894
18:38:01.020  x=-8.9506 y=-6.5617  |v|=0.0655
18:38:01.070  x=-8.9492 y=-6.5598  |v|=0.0340
18:38:01.126  x=-8.9492 y=-6.5598  |v|=0.0000      <- at rest
```

**0.280 s and 0.038 m** from the empty goal to standing still, against
the 14.8 m step4 class a coast with no publisher produces. **`Motor`
never dropped: 0 of 627** `"motor": false` samples over the cancel
window (18:37:48.677 → 18:38:20), and `errors[]` on every state through
the cancel is empty — no `safetyStop` entry, because this was never a
safety path.

**A fresh order restarts the truck.** `send_order.py f1 S1` at
18:38:40.355 → EN-ROUTE 18:38:42.277 → **ARRIVED 18:39:13.978** at
(−3.2347, −5.4711), **0.2365 m** from S1's (−3.00, −5.50), inside its
0.25 m radius, with **0 of 634** motor-false over that drive.

---

## [x] VDA Gate 4 — supervision loss mid-drive

**Date:** 2026-08-21. **Verdict: PASS.** Measured by the scripted driver
+ CLI — no panel, no human.

**Spec:** *broker (or link) down → controlled stop with order kept;
broker back → resume from current pose → ARRIVED. Motor never drops
(this is not a safety path — prove it).*

The link was dropped by **killing the broker process, `kill -9`**, and
the pid was verified twice — once out of `.step6_pids`, once again
immediately before the signal:

```
$ head -1 .step6_pids
41859
$ tr '\0' ' ' < /proc/41859/cmdline
/home/ozkan/.local/mosquitto-vendored/usr/sbin/mosquitto -v
$ tr '\0' '\n' < /proc/41859/environ | grep GZ_PARTITION
GZ_PARTITION=step6
18:44:10.922  kill -9 41859
$ ls /proc/41859        ->  No such file or directory
$ ss -ltn | grep 1883   ->  (nothing listening)
```

f2 was driving `o-dcf3e202` (S4 → S10, 17.5 m, six released nodes) at
0.213 m/s. **The loss, in order:**

```
18:44:10.922  kill -9 the broker
18:44:10.923  the MQTT recorder's own on_disconnect fires
18:44:10.966  vda_agent_f1 log: "broker lost - controlled stop, order kept"
18:44:11.024  vda_agent_f2 log: the same line, 0.102 s after the kill
18:44:11.025  /f2/auto/goal <- ''
18:44:11.114  /f2/auto/state: IDLE, goal null, note "cancelled"
18:44:11.666  /f2/gz/odom: |v| = 0.0000
```

Odom across the stop, folded to the samples that change:

```
18:44:11.020  x=7.0213 y=-7.0494  |v|=0.2125      <- goal published
18:44:11.105  x=7.0144 y=-7.0529  |v|=0.1009
18:44:11.155  x=7.0115 y=-7.0536  |v|=0.0554
18:44:11.323  x=7.0064 y=-7.0512  |v|=0.0264
18:44:11.666  x=7.0125 y=-7.0491  |v|=0.0000      <- at rest
```

**0.64 s, 0.009 m of net displacement**, again the empty goal through
the ordinary chain and not a safety path — the last three samples
include the pursuit's small settle back onto the line.

**Motor never dropped, and the count covers the WHOLE gate**, order to
arrival, both trucks:

```
f2  18:43:56.914 .. 18:46:06.013   motor-false 0 of 2582
f1  18:43:56.914 .. 18:46:06.013   motor-false 0 of 2582
```

f1 was parked with no order and its agent still logged the loss, which
is the same code path answering for a truck with nothing to stop.

**The order was kept and the broker came back.** Respawned with
`step6.sh`'s own spawn shape, `LD_LIBRARY_PATH` from `BROKER_LIB`, under
`GZ_PARTITION=step6` so `stop` can still sweep it, pid appended to
`.step6_pids`:

```
18:44:45.840  setsid bash -c 'echo $$ >> "$1"; shift; exec "$@"' _ .step6_pids \
                env LD_LIBRARY_PATH="$BROKER_LIB" "$BROKER_BIN" -v >> logs/broker.log 2>&1 &
              new broker pid 43889
$ tr '\0' ' ' < /proc/43889/cmdline
/home/ozkan/.local/mosquitto-vendored/usr/sbin/mosquitto -v
$ ss -ltn | grep 1883
LISTEN 0  100  127.0.0.1:1883   0.0.0.0:*
```

```
18:44:45.932  the MQTT recorder is back on the broker
18:45:13.977  vda_agent_f1: "broker connected - ONLINE published"
18:45:14.013  vda_agent_f2: the same
18:45:14.083  vda_agent_f2: "supervision back - route re-issued"
```

**The re-issued route starts from the pose the truck is standing on, not
from where the order started** — `/f2/auto/route`, the two publishes
side by side:

```
18:43:56.906  {"points": [[6.224398, -7.870343], [6.0,-5.5], [3.0,-5.5],
               [0.0,-5.5], [-3.0,-5.5], [-6.0,-5.5], [-6.0,-2.5]], ...
               "label": "o-dcf3e202"}
18:45:14.062  {"points": [[7.012486, -7.049058], [6.0,-5.5], [3.0,-5.5],
               [0.0,-5.5], [-3.0,-5.5], [-6.0,-5.5], [-6.0,-2.5]], ...
               "label": "o-dcf3e202"}
```

Same label, same six remaining nodes — `Progress.reached` was still 0,
because the truck stopped **1.85 m** short of `wp1`, and 1.85 m is well
outside the 0.8 m default deviation. That distance is the two
coordinates above and nothing else:
`hypot(7.012486 − 6.0, −7.049058 − (−5.5)) = hypot(1.0125, −1.5491) =
1.8506 m`. The first point differs, and it is the current pose. The
state stream across the outage, one row per change:

```
18:43:56.907  order=o-dcf3e202  rem=6  last=      driving=False
18:43:59.006  order=o-dcf3e202  rem=6  last=      driving=True
      ... 75.1 s with no state on the wire: 34.9 s of it with no
          broker at all, the rest waiting on the agent's reconnect ...
18:45:14.116  order=o-dcf3e202  rem=6  last=      driving=False
18:45:16.106  order=o-dcf3e202  rem=6  last=      driving=True
18:45:23.024  order=o-dcf3e202  rem=5  last=wp1   driving=True
18:45:33.484  order=o-dcf3e202  rem=4  last=wp2   driving=True
18:45:38.080  order=o-dcf3e202  rem=3  last=wp3   driving=True
18:45:42.582  order=o-dcf3e202  rem=2  last=wp4   driving=True
18:45:48.132  order=o-dcf3e202  rem=1  last=wp5   driving=True
18:46:06.003  order=o-dcf3e202  rem=0  last=S10   driving=True
18:46:08.106  order=o-dcf3e202  rem=0  last=S10   driving=False
```

**Same orderId on both sides of a 75-second silence.** ARRIVED at
18:46:06.013 at (−5.9241, −2.7381), **0.2499 m** from S10's
(−6.00, −2.50) — inside the 0.25 m the station declares, by one
millimetre.

**Measured beside the gate and not part of it: the agents took 28.1 s to
reconnect** (broker listening 18:44:45.840, agents on at
18:45:13.977/14.013) while the recorder took 0.09 s. The recorder calls
`reconnect_delay_set(1, 2)`; `vda_agent` does not, so it takes paho's
default exponential backoff, which after a 34.9 s outage had already
grown its retry interval. Nothing in the spec bounds reconnect time and
no gate is failed by it, but a fleet that counts a vehicle as lost after
N seconds would want that bound stated — **carried to M6.3**.

---

## [x] VDA Gate 5 — connection lifecycle

**Date:** 2026-08-21. **Verdict: PASS, all three states.** Measured by
the scripted driver + CLI — no panel, no human.

**Spec:** *ONLINE retained on connect; OFFLINE on clean shutdown; kill -9
the agent → subscribers receive the broker's CONNECTIONBROKEN last will.*

### ONLINE, retained, seen by a subscriber that was not there

A brand-new client id on a clean session, subscribing 42 s after the
agents connected, is handed both trucks' connection state by the BROKER:

```
$ python3 mq.py snap 2.5 connection
18:31:47.371  fresh subscriber connected (Success)
18:31:47.424  retain=True  uagv/v2/amragent/f1/connection
              {"headerId": 2, "timestamp": "2026-08-21T16:31:05.245Z",
               "serialNumber": "f1", "connectionState": "ONLINE"}
18:31:47.424  retain=True  uagv/v2/amragent/f2/connection
              {"headerId": 2, ... "serialNumber": "f2",
               "connectionState": "ONLINE"}
--- 2 message(s) in 2.5s
```

`retain=True` is the whole proof: those two were published 42 s earlier
and replayed out of the broker's retained store. **`headerId` is 2, not
1**, on every ONLINE this file records, and that is the will being
built: `VdaAgent.__init__` calls `Counters.header("connection", …)` for
`will_set` before it ever connects, so the will owns headerId 1 for the
life of the process.

### OFFLINE on a clean stop

The writers were closed the way the panel window closes, then the stack
was stopped:

```
18:47:31.628  ->127.0.0.1:5910  {"quit":true}
18:47:31.719  ->127.0.0.1:5920  {"quit":true}
shutting down: writing the trip values        (both writers)
writer for f1 is down                          writer for f2 is down
18:47:50.075  ./step6.sh stop
```

The recorder, still attached, saw both:

```
18:47:50.302  uagv/v2/amragent/f1/connection  OFFLINE  headerId 4
18:47:50.306  uagv/v2/amragent/f2/connection  OFFLINE  headerId 4
18:47:50.409  the recorder's own on_disconnect (the broker is gone)
```

and `logs/broker.log` shows the whole handshake, retained and
acknowledged, before the broker itself exits:

```
1787330870: Received PUBLISH from vda-f1 (d0, q1, r1, m515, 'uagv/v2/amragent/f1/connection', ... (156 bytes))
1787330870: Sending PUBACK to vda-f1 (m515, rc0)
1787330870: Received DISCONNECT from vda-f1
1787330870: Client vda-f1 disconnected.
1787330870: Received PUBLISH from vda-f2 (d0, q1, r1, m509, 'uagv/v2/amragent/f2/connection', ...)
1787330870: Sending PUBACK to vda-f2 (m509, rc0)
1787330870: Received DISCONNECT from vda-f2
1787330870: Client vda-f2 disconnected.
1787330870: mosquitto version 2.0.18 terminating
```

`r1` is the retain flag, `q1` the QoS, and the PUBACK is the broker
saying it took it — **0.23 s from `stop` starting to both OFFLINEs
acknowledged**, and the agents then leave through `disconnect()` rather
than being cut off. `close()` runs from `main()`'s `finally`: SIGTERM
reaches rclpy's own handler, `spin()` raises `ExternalShutdownException`,
the `finally` publishes OFFLINE, and only then does the exception
propagate. **Each agent log therefore ends in an
`ExternalShutdownException` traceback and that is the shutdown working**,
not failing — the OFFLINE above went out before it.

### kill -9 → the broker publishes the will

The stack was restarted (no writers needed; this gate never moves a
truck) and the agent to be killed was identified before the signal:

```
$ AP=$(sed -n '10p' .step6_pids); echo $AP
44854
$ tr '\0' ' ' < /proc/44854/cmdline
python3 .../m5_ver2/step6/deploy/m5_ver2/step6/ipc/vda_agent.py
$ tr '\0' '\n' < /proc/44854/environ | grep -E '^(VEHICLE|GZ_PARTITION)='
GZ_PARTITION=step6
VEHICLE=f1
```

A fresh subscriber before, and a fresh subscriber after:

```
18:49:03.524  retain=True  .../f1/connection  ONLINE  headerId 2
18:49:03.524  retain=True  .../f2/connection  ONLINE  headerId 2

18:49:15.287  kill -9 44854

18:49:18.686  retain=True  .../f1/connection  CONNECTIONBROKEN  headerId 1
18:49:18.686  retain=True  .../f2/connection  ONLINE            headerId 2
```

**headerId 1 is the will**, built at construction and never touched
since, which is how you can tell this message came out of the broker's
will store and not out of a process that no longer exists. The recorder
saw it live 4 ms after the kill (18:49:15.291), and `logs/broker.log`
records `Client vda-f1 closed its connection.` at the same second.
**f2's retained ONLINE is untouched** — one vehicle died and the fleet's
view of the other did not move.

---

## [x] VDA Gate 6 — state honesty

**Date:** 2026-08-21. **Verdict: PASS.** Measured by the scripted driver
+ CLI — no panel, no human.

**Spec:** *trip a protective field mid-drive (Gate-2 box) → state shows
`fieldViolation: true`, a FATAL error, `driving: false`; heal + ack →
error clears. The MQTT stream never CAUSES any of it.*

f1 was driving `o-dd515189` (S1 → S2 CHARGE-1) down the dock aisle. M6.1
Gate 2's box comes to the truck, but this truck is moving, so the pose
is read live off its own odom and the box is put **4.0 m ahead along its
heading**:

```
18:40:39.784  truck (-3.220, -5.468) th 3.123 |v| 0.241  ->  box (-7.220, -5.396)
$ gz service -s /world/warehouse/create --reqtype gz.msgs.EntityFactory \
    --reptype gz.msgs.Boolean --timeout 5000 \
    --req 'sdf_filename: "/tmp/gate6_box.sdf", name: "gate6_box",
           pose: {position: {x: -7.220, y: -5.396, z: 0.20}}'
data: true
```

**The approach is a ramp and every metre of it is the device's own
reading**, not geometry asserted here — every `d` f1's back scanner
reported between the spawn and the removal, counted:

```
   2.87 .. 2.47 m   SAFE          17 values, one sample each
   2.44 .. 0.97 m   WARNING       61 values, one or two samples each
   0.94, 0.92 m     PROTECTIVE     2
   0.90 m           PROTECTIVE   411   (standing still against the box)
   4.03 m           PROTECTIVE     3   (the N_SCAN = 3 clearing straddle)
   4.03 m           SAFE          17   (the box is gone)
```

The truck's own odom 75 ms before the first PROTECTIVE puts its back
scanner — `model.sdf`'s (0.72, 0.00) on `base_link`, yaw 0 — at
(−6.0774, −5.4121), which is **0.943 m off the box's near face**; the
device said 0.903 m at the trip. **The 40 mm between them is sampling
skew and not disagreement:** the truck was closing at 0.250 m/s, so
40 mm is 160 ms of travel, and the two numbers come off two different
pipelines — bridged odom on one, a bridged scan through `field_eval` on
the other — read at two different instants. (An earlier draft blamed the
ray angle across the cube. That is backwards: an oblique return is
LONGER than the perpendicular one, so a ray angle would push the
device's number UP, not down.) Both numbers are inside the case-1
protective field's **1.0 m**, which is the only claim the gate makes.

**The trip, in causal order, from three separate captures:**

```
18:40:48.743  /f1/safety/fields  back {"pf": false, "wf": false,
                                       "d": 0.903, "level": "PROTECTIVE"}
18:40:48.797  /f1/plc/status     {"estop_healthy": true, "motor": false,
                                  "case": 1, "v_limit": 300}
18:40:48.798  MQTT state         safetyState {"eStop": "MANUAL",
                                              "fieldViolation": true}
                                 errors [safetyStop / FATAL]
18:40:48.877  /f1/auto/state     SAFETY-STOP
18:40:50.846  MQTT state         driving: false
```

and the state stream around it, one row per change:

```
18:40:46.947  driving=True   {"eStop":"NONE","fieldViolation":false}   errs []
18:40:48.050  driving=True   {"eStop":"NONE","fieldViolation":false}   errs []
18:40:48.798  driving=True   {"eStop":"MANUAL","fieldViolation":true}  errs [safetyStop FATAL]
18:40:50.846  driving=False  {"eStop":"MANUAL","fieldViolation":true}  errs [safetyStop FATAL]
```

**`driving` is still true on the first tripped state and that is
honest** — the state is published 1 ms after the status sample that
dropped Motor, and the last odom sample before it (18:40:48.767) reads
`|v| = 0.2500`, which is `DRIVING_MPS` (0.02) many times over. The truck
came to rest at **18:40:48.936**, 0.139 s and **0.015 m** later, at
(−5.3971, −5.4255). The next state, 2 s after the trip, says false.

### Heal, then acknowledge — and the order survives both

```
18:41:29      gz service -s /world/warehouse/remove ... 'name: "gate6_box"'  ->  data: true
18:41:31.946  state: fieldViolation FALSE, errors STILL [safetyStop FATAL]
18:41:39.648  ->127.0.0.1:5910  {"ack":true}
18:41:39.698  state: {"eStop":"NONE","fieldViolation":false}  errs []
18:41:41.746  state: driving=True, rem=3, last=wp1
18:41:45.404  state: rem=2  last=wp2
18:41:56.245  state: rem=1  last=wp3
18:42:16.577  /f1/auto/state ARRIVED at (-9.0296, -6.3874)
```

**The eight seconds between 18:41:31.946 and 18:41:39.648 are the whole
point of an ESTOP1.** The field was clear and the state said so —
`fieldViolation` went false the moment the box left — and the FATAL
`safetyStop` stayed, because the demand had LATCHED and only the
acknowledge releases it. A state that had cleared the error with the
field would have been a lie about a truck that still could not move.
After the ack the order kept draining: 0.7992 m from S2's (−9.80, −6.60)
against its 0.80 m radius.

### The MQTT stream caused none of it, and here is how that is known

Three independent statements, all from the captures:

1. **Nothing arrived.** Every message on every `uagv/v2/amragent/#`
   topic between the order and the trip, by topic:
   `f1/order` **1**, `f1/state` 8, `f2/state` 6. **The two state topics
   are the vehicles TALKING** — outbound, and an outbound message
   commands nothing. **The one INBOUND message is the order**, and it
   landed at 18:40:38.570, **10.2 s before** Motor dropped. No
   `instantActions`, no second order, nothing else addressed to f1 in
   those 10.2 s.
2. **The wire is the last link, not the first.** `fields` said
   PROTECTIVE at 18:40:48.743, `plc/status` said `motor: false` 54 ms
   later, and the MQTT state carried the news 1 ms after that. The
   order — scanner → `field_eval` → `sensor_link` → the writer → the
   F-model → `plc_link` → the agent — is the physical chain, and the
   agent is at the far end of it.
3. **The agent has nowhere to push.** Its only two ROS publishers are
   `/auto/route` and `/auto/goal`; `/f1/auto/route` gained no sample
   between the order and the trip, and `/f1/auto/goal` gained none in
   the entire gate. It cannot reach the safety chain because it has no
   publisher that touches it — which is the M1 invariant, holding.

---

## Full-stack RTF with twenty pids, under load — evidence, not a gate

`/world/warehouse/stats` was sampled the way `tools/rtf_spike.sh` samples
it (`stdbuf -oL gz topic -e -t /world/warehouse/stats` under
`GZ_PARTITION=step6`), for 400 s spanning VDA Gates 1 and 2, with every
sample stamped:

| Window | Samples | Mean RTF | Min | Max |
|---|---|---|---|---|
| whole 400 s, 18:32:38–18:39:18 | 3752 | **0.458** | 0.025 | 1.644 |
| 60 s containing VDA 1's 20.263 s overlap (22.4 s driving) | 573 | **0.471** | 0.030 | 1.574 |
| 60 s containing 53.8 s of VDA 2b's single-truck drive | 574 | **0.497** | 0.029 | 1.644 |
| **VDA 1's 20.263 s both-driving overlap, alone** | 192 | **0.616** | 0.047 | 1.574 |
| **the same window's 37.6 s of parked trucks, alone** | 342 | **0.393** | 0.030 | 1.246 |
| **VDA 2b's 53.8 s single-truck drive, alone** | 497 | **0.495** | 0.029 | 1.644 |

The last three rows are the same 400 s capture cut on the drive
boundaries this file already prints; nothing was re-run. `gz topic -e`
was stamped to the WHOLE SECOND, so each cut is bracketed rather than
claimed exact — the row is the *inner* cut (buckets wholly inside the
drive) and the *outer* cut (any bucket touching it) is **0.605** (n 211),
**0.592** (n 221 over the two legs' union) and **0.504** (n 516). The
brackets are within 0.011 of their rows, which is the whole of the
timing exposure.

Per-10 s over the two 60 s windows:

```
VDA 1 window   0.424, 0.596, 0.525, 0.434, 0.368, 0.478
VDA 2b window  0.370, 0.469, 0.555, 0.514, 0.564, 0.514
```

**Both 60 s rows are WALL CLOCK, not driving, and the first one is
mostly parked.** VDA 1's two legs occupy 22.4 s of its window —
18:34:31.078 to 18:34:53.514, the union of the two — of which 20.263 s
is the overlap; the other 37.6 s is two standing trucks.

**An earlier draft said "idle is the cheap half, so 0.471 is diluted
upward and the true both-driving figure is at or below it." That was an
unmeasured premise and the measurement contradicts it.** Cut on the
drive boundaries, the both-driving overlap runs at **0.616** and the
parked remainder of the very same minute at **0.393** — the driving
seconds were the FASTER ones, the dilution was DOWNWARD, and the true
both-driving figure is **above** 0.471, not below it. The single-truck
row needs no correction of that kind and is the arithmetic check on the
method: its window was already 90 % drive, and cutting it to the drive
alone moves 0.497 to 0.495.

**Why the parked seconds were the slow ones is inference and is marked
as such.** This sampler measures the MACHINE, not the trucks, and the
seconds in which the forklifts stood still are exactly the seconds in
which this session's own tooling ran — `send_order.py` connecting and
disconnecting, the capture readers walking twenty megabytes, a
`wsl.exe` process spawn per command. Nothing here measured that, so it
is offered as the likely reading and not as a result. What IS measured
is the ordering: **0.616 driving, 0.471 over the minute containing it,
0.393 parked.**

The two driving rows are also not each other's control — 0.616 is two
trucks and 0.495 is one, taken ninety seconds apart under whatever else
the machine was doing — so the pair bounds the figure rather than
ranking two-truck against one-truck load.

**This is not comparable to the 0.734–0.755 recorded further up this
file, and the difference is load, not a regression.** That figure was
seventeen pids, idle, with **no writer running**. This one is twenty
pids — the broker and two VDA agents were added — plus two Windows
writers streaming at 50 Hz over two UDP port pairs, a twelve-subscription
ROS recorder, a paho recorder, and one or two trucks actually driving.
M6.1 named exactly this as the open question ("the margin to a third
vehicle is now the interesting number"; "nothing here was run with the
two Windows writers attached"). **The measured answer is that a working
two-vehicle rig holds 0.46–0.50 of real time across a minute that
contains a drive, and 0.50–0.62 across the drive itself** — 0.616 over
VDA 1's two-truck overlap, 0.495 over VDA 2b's single-truck leg. The
low end of any of these is a machine busy with something other than the
simulator, which is what the parked 0.393 says.
Every loop in the tree is wall-clock timed, so nothing missed its rate —
what stretches is simulated time per wall second, and it is why a 6.00 m
route took 22 s. A third vehicle needs a bigger machine, and that is a
M6.3 input rather than a verdict here.

## Teardown

```
> {"quit":true} -> 127.0.0.1:5910          > {"quit":true} -> 127.0.0.1:5920
shutting down: writing the trip values     shutting down: writing the trip values
writer for f1 is down                      writer for f2 is down
```

`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` afterwards
returns three VS Code language servers and nothing else.

```
$ ./step6.sh stop
  swept 41872 (gz sim) ... 26 swept lines ... swept 43889 (mosquitto-vendored)
  killed 42239 ... killed 42779                (19 killed lines)
down.
```

**26 swept and 19 killed, against the twenty pids started, and the
arithmetic is the point again.** Swept: the twenty recorded processes,
plus `gz sim` itself, `parameter_bridge` and two each of
`sto_contactor.py` and `forklift_io.py`, which the world launch starts
and the pidfile never sees — 26. Killed: the pidfile now holds
twenty-one lines, the twentieth-first being the broker VDA Gate 4
respawned; **41859** (the broker that gate killed) no longer exists and
**41865** (the world's launch process) had just gone with the sweep, so
19 of the 21 were still there to kill. The broker in the swept list is
**43889**, the respawned one — which is the check that Gate 4's restart
put it back inside this stack's partition and not beside it.

After the second stack (the will half of VDA Gate 5), which ran with one
agent already `kill -9`ed:

```
$ ss -uln | grep -E ':(5110|5111|5120|5121)'  ->  (all four free)
$ ss -ltn | grep ':1883'                      ->  (free)
$ pgrep -af 'gz sim|plc_link.py|...|mosquitto-vendored'  ->  (nothing)
$ test -f .step6_pids                          ->  removed
```

```
$ python3 -m pytest m5_ver2/step6/tests/ -q
302 passed in 36.36s
$ python3 -m pytest m5_ver2/step5/tests/ -q
220 passed in 2.87s
```

---

---

# M6.3 — the fleet manager's six gates

**Date: 2026-08-22, 00:16–01:14. Measured by the scripted driver + CLI —
no panel, no human.** One WSL session, one stack, one broker, twenty-one
pids including the fleet manager. Every order in this section was
generated by `fleet/fleet_manager.py` from a transport submitted with
`fleet/fleet_cli.py`; `tools/send_order.py` was not used once.

Five of the six gates passed on the first measurement. **Fleet Gate 4
failed, on two real defects.** One of them was fixed (`e3c0ddd`) and
that gate was re-run on 2026-08-22 at 01:36–01:44; both runs are below,
because the failed one is the evidence that found the bug. The second
defect — a stopped vehicle is an obstacle its replacement cannot pass —
is M6.4's, is not fixed, and is not hidden behind the tick.

## Setup, verbatim

```
$ cd /mnt/c/Users/ozkan/projects/amr-agent/m6
$ ./m6.sh deploy
instantiated .../m6/vehicles/f1
instantiated .../m6/vehicles/f2
deployed 25 files to .../m6/deploy

$ ./m6.sh start --headless
starting the Step 6 vehicle side (partition m6, domain 96, gui false)
  broker 57994          world 58000
  plc_link_f1 58374     cmd_gate_f1 58380     cmd_mux_f1 58388
  field_eval_f1 58434   encoder_link_f1 58473 sensor_link_f1 58493
  nav_node_f1 58529     vda_agent_f1 58566    hmi_f1 58617
  plc_link_f2 58631     cmd_gate_f2 58672     cmd_mux_f2 58699
  field_eval_f2 58773   encoder_link_f2 58815 sensor_link_f2 58834
  nav_node_f2 58838     vda_agent_f2 58883    hmi_f2 58913
  fleet 58947
```

**Twenty-one pids**, no `exited during startup` — twenty from M6.2 plus
`fleet`, which `m6.sh` spawns last and with no `VEHICLE` (folded two and
three to a row here; the real output is one per line). Then, on Windows,
one scripted writer per vehicle, started detached with `Start-Process …
-RedirectStandardOutput logs\scripted_writer_fN.log`:

```
> python m6\tools\scripted_writer.py --vehicle f1 --virtual --ctl-port 5910
> python m6\tools\scripted_writer.py --vehicle f2 --virtual --ctl-port 5920
streaming PLC state to 172.19.180.72:5110   (f2: …:5120)
VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop
listening for the back scanner on 0.0.0.0:5111   (f2: …:5121)
control channel on 127.0.0.1:5910                (f2: …5920)
E-Stop=True  Motor=False  ack=False | PF b/r/l=T/T/T  WF b/r/l=T/T/T
```

Both were reading their sensor port before anything was acknowledged —
`PF/WF` all `T` on the first cycle is a live WSL→Windows 5111/5121 link
and not a default — and both reported `Motor=False`, the startup
acknowledge the F-program demands. The mode went out through the
recorder's own transient-local publishers, **before** the RESET, so no
ROS node was started after a truck could move:

```
00:16:43.714  PUB /f1/hmi/mode <- 'auto' (3 matched subscribers)
00:16:43.764  PUB /f2/hmi/mode <- 'auto' (3 matched subscribers)
00:16:53.587  ->127.0.0.1:5910  {"ack": true}
00:16:55.667  ->127.0.0.1:5920  {"ack": true}
00:16:59.841  ->127.0.0.1:5910  {"status": true}
reply {"motor": true, "line": "E-Stop=True  Motor=True  ack=False |
       PF b/r/l=T/T/T  WF b/r/l=T/T/T | case=1  V_Limit=1500  enc=0/0 ok"}
00:16:59.921  ->127.0.0.1:5920  {"status": true}   reply … identical …
```

The `3 matched subscribers` are `cmd_mux`, `nav_node` and `vda_agent`,
all three TRANSIENT_LOCAL. The manager's own screen was live before any
of it: `first status published on fleet/status, retained - the
operator's screen is live`, 00:15:52.801.

**PowerShell strips the double quotes out of a native command's
argument** (M6.2 recorded that, twice), so every writer command in this
session went through a wrapper that builds the JSON itself. The four
buttons are still the panel's four and nothing more.

## The two instruments

**ROS side: ONE recorder process** — M6.1's `gate_rec` lineage with a
UDP control socket, twelve subscriptions and the two `/fN/hmi/mode`
publishers, all created before the first RESET:

```
python3 rec3.py 10800 /tmp/m63/cap 5940 \
  f1_status=/f1/plc/status=String   f2_status=/f2/plc/status=String \
  f1_fields=/f1/safety/fields=String f2_fields=/f2/safety/fields=String \
  f1_nav=/f1/auto/state=String      f2_nav=/f2/auto/state=String \
  f1_goal=/f1/auto/goal=String      f2_goal=/f2/auto/goal=String \
  f1_route=/f1/auto/route=String    f2_route=/f2/auto/route=String \
  f1_odom=/f1/gz/odom=Odometry      f2_odom=/f2/gz/odom=Odometry \
  pub=mode1=/f1/hmi/mode=transient_local \
  pub=mode2=/f2/hmi/mode=transient_local
```

Its whole session, printed at the end:

```
f1_status 69193  f2_status 69161   f1_odom  55701  f2_odom  55701
f1_fields 34591  f2_fields 34602   f1_nav   34577  f2_nav   34602
f1_route     14  f2_route     10   f1_goal      2  f2_goal      4
```

**There is no goal publisher in that command line**, and the arithmetic
is the claim: `/f1/auto/goal` carries **two** samples in fifty-eight
minutes and `/f2/auto/goal` four — every one of them the AGENT's own
empty goal answering a `cancelOrder`, at 01:04:54.934 and 01:08:49.471
(f1) and 00:23:31.814, 00:53:01.414, 01:00:25.414, 01:08:49.617 (f2).
**No HMI goal was published by anything, at any point.** Those six
timestamps are also the evidence for Fleet Gate 4's first defect, below.

**MQTT side: one paho subscriber**, M6.2's recorder widened to
`uagv/v2/amragent/+/#` **and `fleet/#`** — because in M6.3 the admin
wire and the retained status document are half the evidence. One JSONL
line per message, the retain flag kept, `reconnect_delay_set(1, 2)`, up
at 00:16:18.570 and left running across three manager restarts. It is
not a ROS node, so the rig rule does not bite it.

## The rig rule held; the safe-speed link did not

No ROS process was started after the RESET, and no gate below was
starved. **Every `"motor": false` sample in the session belongs to a run
this file names:**

```
f1  14510 samples in 5 runs        f2  17127 samples in 4 runs
  00:16:30.295 .. 00:16:53.584       00:16:31.758 .. 00:16:55.647
      the startup acknowledge, cleared by the RESET
  00:31:40.684 .. 00:39:00.684       00:42:02.647 .. 00:53:16.097
      SAFE-SPEED LATCH (defect 3)        SAFE-SPEED LATCH (defect 3)
  01:01:33.484 .. 01:03:16.534       (none)
      SAFE-SPEED LATCH (defect 3)
  01:06:41.884 .. 01:09:01.634       01:06:41.947 .. 01:09:03.797
      Fleet Gate 4's mutual latch        Fleet Gate 4's mutual latch
  01:13:50.734 .. 01:14:09.484       01:13:52.797 .. 01:14:09.498
      the writers' own trip values on {"quit": true}, at teardown
```

**Fleet Gates 1, 2 (the queueing measurement) and 5 contain none of
these, and Gate 6's Gate-1 half does not either.** Gate 6's other half
is honest about the overlap rather than fenced off from it: its 70 s
OFFLINE window (01:08:51-01:10:00) begins inside f1's mutual-latch run
by about ten seconds, which is the point of that half - the document
told the truth about a vehicle that was both latched and unreachable.
The latches are the third defect below; they are the reason
this session spent four RESETs and two `./m6.sh home`s on housekeeping,
and every one of those is recorded where it happened.

## [x] Fleet Gate 1 — two transports, two vehicles

**Verdict: PASS on run 2.** *Submit two A→B tasks → nearest-idle
assignment (the measured distances recorded), both vehicles drive leg 1,
dwell, leg 2, DONE; 0 motor-false; the status document's task table
telling the story truthfully throughout.*

### Run 1, recorded because it happened: S5 cannot be reached from the east connector

The first pair was `S4 → S5` and `S2 → S10`. Assignment, dwell and leg
sequencing were exactly as run 2 below; f1 completed `S2 → S10` at
00:19:01.014. **f2 could not finish at S5.** `route.plan_route` reaches
S5 (11.60, 5.65) up the x = 12 connector and then west along 0.40 m of
main aisle — a 90° turn with 0.40 m to straighten out, against a
measured minimum turning radius of about 0.69 m. The truck settled into
the orbit `stations.py`'s own module note describes for S7:

```
first sample within 1.00 m   00:19:30.140   d = 1.000 m
3615 samples, 00:19:30.140 .. 00:22:52.406
  min d 0.4952   max d 0.9996   mean d 0.6884   |v| 0.1295 .. 0.2188
  angle swept 2226.6 deg = 6.18 complete laps
S5's declared arrive_m = 0.25
```

S5 declares `arrive_m` 0.25 because it "sits ON the main aisle and needs
no turn at all" — **true from the west, false from the x = 12
connector.** This is cell geometry, not fleet code: `order_builder`
built a valid order and stamped the station's own radius on it. It is
named here as carried debt for M6.4/M6.5 and the orbit was stopped by a
scratch `cancelOrder` at 00:23:31.777. Run 2 uses S9 (`arrive_m` 0.80,
whose spur the rule does cover) and is the measurement.

### Run 2 — the measurement

Both trucks homed, the manager restarted with `m6.sh`'s own spawn shape
(`setsid`, pid appended to `.m6_pids`, `GZ_PARTITION=m6`), both idle at
their spawn poses. Two route-disjoint transports, submitted 2 s apart:

```
$ python3 m6/fleet/fleet_cli.py submit S4 S9
ft-96b26e99  submitted: S4 -> S9
$ python3 m6/fleet/fleet_cli.py submit S2 S10
ft-e596bcc3  submitted: S2 -> S10
```

**The assignment evidence is the manager's own line, and it carries both
vehicles' route lengths:**

```
00:24:59,455 queued ft-96b26e99: S4 -> S9
00:24:59,456 assigned ft-96b26e99 to f2
             (nearest idle to S4: f1 11.50 m, f2 5.50 m <-- chosen)
00:25:01,662 queued ft-e596bcc3: S2 -> S10
00:25:01,662 assigned ft-e596bcc3 to f1
             (nearest idle to S2: f1 7.90 m <-- chosen)
```

**f2 is the higher serial and it won on distance** — 5.50 m against
11.50 m — so the first line is not the tie-break rule wearing a
disguise. By the second submission f1 was the only idle vehicle, which
is why only one distance is printed: the line reports who was ELIGIBLE
at the moment of choosing, not who exists. Route-disjoint: f2's nodes
are all x ≥ 6 (then up the x = 12 connector), f1's all x ≤ −3.

| | f2: S4 → S9 | f1: S2 → S10 |
|---|---|---|
| task | `ft-96b26e99` | `ft-e596bcc3` |
| leg 1 order | `ft-211a6dde` | `ft-8716659d` |
| leg 1 length | 5.50 m | 7.91 m |
| leg 1 EN-ROUTE | 00:25:01.614 | 00:25:03.836 |
| leg 1 ARRIVED | 00:25:20.958 | 00:25:22.216 |
| leg 1 drive | 19.344 s | 18.380 s |
| ARRIVED pose | (6.2296, −7.9023) | (−10.3526, −6.0256) |
| **arrival error** | **0.2496 m** (arrive_m 0.25) | **0.7971 m** (0.80) |
| **dwell** | 00:25:21.007 → 00:25:24.015 = **3.008 s** | 00:25:22.311 → 00:25:25.318 = **3.007 s** |
| leg 2 order | `ft-feeea20c` | `ft-9d7b9b3d` |
| leg 2 length | 24.50 m | 7.90 m |
| leg 2 drive | 103.378 s | 48.340 s |
| DONE | 00:27:07.563 at S9 | 00:26:15.837 at S10 |
| ARRIVED pose | (7.9155, 5.5934) | (−6.0947, −2.7286) |
| **arrival error** | **0.7979 m** (arrive_m 0.80) | **0.2474 m** (0.25) |

Both dwells are `DWELL_S = 3.0` to eight milliseconds, measured from the
manager's own arrival line to its own leg-2 line.

**0 motor-false, both trucks, across the whole gate:**

```
00:24:59.289 .. 00:27:07.563
  f1  motor-false 0 of 2565      f2  motor-false 0 of 2566
```

**The state streams drained.** One row per change, off the MQTT
recorder (f1, leg 1 then leg 2; `rem` is `len(nodeStates)`, `D` is
`driving: true`):

```
00:25:01.758  ft-8716659d  rem 5  last -          (-3.0000, -5.5000)
00:25:01.758  ft-8716659d  rem 4  last wp1        (-3.0000, -5.5000)
00:25:03.836  ft-8716659d  rem 4  last wp1   D    (-4.1912, -5.5000)
00:25:05.596  ft-8716659d  rem 3  last wp2   D    (-5.2062, -5.5000)
00:25:07.849  ft-8716659d  rem 2  last wp3   D    (-6.6062, -5.5001)
00:25:12.059  ft-8716659d  rem 1  last wp4   D    (-9.0082, -5.4454)
00:25:22.216  ft-8716659d  rem 0  last S2    D   (-10.3526, -6.0256)
00:25:25.336  ft-9d7b9b3d  rem 5  last -        (-10.3535, -6.0342)
00:25:25.355  ft-9d7b9b3d  rem 3  last wp2      (-10.3535, -6.0342)
00:25:52.782  ft-9d7b9b3d  rem 2  last wp3   D   (-7.8357, -4.8575)
00:25:55.919  ft-9d7b9b3d  rem 1  last wp4   D   (-6.7888, -5.4222)
00:26:15.775  ft-9d7b9b3d  rem 0  last S10   D   (-6.0947, -2.7286)
```

`nodeStates` drains to zero, `lastNodeId` advances to the station, and
the leg-2 order is a **new orderId planned from the pickup station, not
from the live pose** — `order_builder.leg2_start`'s whole point.

**The retained status document told the story truthfully throughout.**
Four snapshots off the MQTT recorder, unedited:

```
[00:25:09.682] both driving leg 1     queue 0  done 0
  f1 ONLINE AUTOMATIC pos [-6.606, -5.5]   order ft-8716659d  age 1.8
  f2 ONLINE AUTOMATIC pos [5.934, -5.41]   order ft-211a6dde  age 1.9
  task ft-96b26e99 ASSIGNED_LEG1 S4->S9  f2  ft-211a6dde
  task ft-e596bcc3 ASSIGNED_LEG1 S2->S10 f1  ft-8716659d

[00:25:22.312] both dwelling          queue 0  done 0
  task ft-96b26e99 DWELL S4->S9  f2 | task ft-e596bcc3 DWELL S2->S10 f1

[00:26:19.855] f1 done, f2 on leg 2   queue 0  done 1
  f1 ONLINE AUTOMATIC pos [-6.11, -2.676]  order -            age 0.0
  f2 ONLINE AUTOMATIC pos [11.919, -2.292] order ft-feeea20c  age 1.1
  task ft-96b26e99 ASSIGNED_LEG2 S4->S9  f2  ft-feeea20c
  task ft-e596bcc3 DONE          S2->S10 f1  ft-9d7b9b3d

[00:27:09.569] both DONE              queue 0  done 2
  f1 ONLINE AUTOMATIC pos [-6.11, -2.676]  order -  age 0.1
  f2 ONLINE AUTOMATIC pos [7.909, 5.59]    order -  age 1.9
```

State ages stay between 0.0 and 1.9 s throughout — `STATE_PERIOD_S` is
2.0 — and the `executing_order` column empties exactly when the task
reaches DONE, never before.

## [x] Fleet Gate 2 — queueing

**Verdict: PASS.** *Three tasks, two vehicles — the third waits QUEUED
and is assigned to the first vehicle that frees; FIFO order preserved.*

Three submissions inside 0.6 s, from the trucks' Gate-1 finishing poses:

```
$ fleet_cli.py submit S2 S3    ft-3cfc8abd
$ fleet_cli.py submit S4 S1    ft-910249bc
$ fleet_cli.py submit S2 S10   ft-ad47398e

00:29:19,363 queued ft-3cfc8abd: S2 -> S3
00:29:19,364 assigned ft-3cfc8abd to f1
             (nearest idle to S2: f1 7.73 m <-- chosen, f2 29.97 m)
00:29:19,665 queued ft-910249bc: S4 -> S1
00:29:19,666 assigned ft-910249bc to f2
             (nearest idle to S4: f2 23.75 m <-- chosen)
00:29:19,867 queued ft-ad47398e: S2 -> S10
             <- and NOTHING follows it. No vehicle was idle.
```

The retained document, 2.0 s later, with the queue as its own field:

```
[00:29:21.873]  queue 1  done 2
  f1 ONLINE AUTOMATIC pos [-6.143, -3.106]  order ft-90a3fd82  age 0.3
  f2 ONLINE AUTOMATIC pos [8.055, 5.879]    order ft-98ac777f  age 0.0
  task ft-3cfc8abd ASSIGNED_LEG1 S2->S3   f1  ft-90a3fd82
  task ft-910249bc ASSIGNED_LEG1 S4->S1   f2  ft-98ac777f
  task ft-ad47398e QUEUED        S2->S10  -   -
  task ft-e596bcc3 DONE          S2->S10  f1  ft-9d7b9b3d
  task ft-96b26e99 DONE          S4->S9   f2  ft-feeea20c
```

**The third task waited 91.1 s and was assigned in the same millisecond
the first vehicle freed:**

```
00:30:11,189 f1 arrived at S2 with ft-90a3fd82 - dwelling
00:30:14,197 dwell done - f1 drives ft-3cfc8abd to S3 as ft-c517264c
00:30:50,981 f1 completed ft-3cfc8abd at S3
00:30:50,982 assigned ft-ad47398e to f1
             (nearest idle to S3: f1 4.30 m <-- chosen)
```

**1 ms.** FIFO is visible in the table's own order and in the fact that
the queued task went to f1 rather than waiting for f2, which was still
driving `ft-910249bc` and did not free until 00:31:54.135. The third
task's assignment distance (4.30 m) is measured from where f1 actually
was — at S3, having just delivered — not from where it started.

**The tail of this gate cost a RESET, and it is defect 3.** f1's leg 2
(`S2 → S10`, issued 00:31:25.767) latched at 00:31:40.684 while leaving
S2's spur. The manager did exactly what its own comment promises — *a
task is not requeued because a truck is stopped* — and held the task on
f1 with the vehicle row honest and the position frozen. After the
operator's RESET at 00:39:00.711 the truck resumed the same order and
`f1 completed ft-ad47398e at S10` at 00:39:38.525. **The queueing claim
above was fully measured before the latch and does not depend on it.**

## [x] Fleet Gate 3 — rejection recovery

**Verdict: PASS.** *One vehicle dropped to teleop → its assignment is
rejected on the wire → task requeued to head → assigned to the other
vehicle; the teleop vehicle re-earns eligibility only after a clean
AUTOMATIC idle state.*

**The race had to be staged, and the staging is named.** The manager
learns a mode change about 7 ms after the truck does, so left alone it
would never assign to a teleop vehicle — the refusal would happen inside
`fleet_core.idle_confirmed` and `_check_rejection` would never run. So
f1's agent was **frozen with SIGSTOP for the length of the assignment**:
the manager kept acting on its last AUTOMATIC idle state (still inside
`IDLE_FRESH_S` = 3 s), the mode went to teleop on ROS where the frozen
agent could not answer it, the order was published into the frozen
agent's socket, and SIGCONT let the truck read both. **The delay is the
instrument; the refusal is the vehicle's own code, unchanged.**

```
00:41:57.760  SIGSTOP 58566          (vda_agent_f1, cmdline verified)
00:41:57.760  mode1 <- teleop
00:41:57.761  submitted ft-50fb4ccf  S3 -> S2   (fleet_cli's own payload)
00:41:59.262  SIGCONT 58566
```

```
00:41:57,857 assigned ft-50fb4ccf to f1
             (nearest idle to S3: f1 5.33 m <-- chosen, f2 5.78 m)
00:41:59,360 WARNING f1 rejected ft-5c3d5890: vehicle not in AUTOMATIC
00:41:59,361 assigned ft-50fb4ccf to f2
             (nearest idle to S3: f2 5.78 m <-- chosen)
```

**The refusal is on the wire and the requeue-and-reassign took 1 ms.**
The task's own history, read out of the retained document, is the whole
narrative in four lines:

```
"history": [
  "submitted S3 -> S2",
  "leg1 -> S3 as ft-5c3d5890 on f1",
  "requeued to head: rejected by f1: vehicle not in AUTOMATIC",
  "leg1 -> S3 as ft-a9f5a54f on f2"
]
```

**The not_eligible flag, flipping.** After the rejection (rendered as
`standby` in the CLI's FLAGS column):

```
[00:42:09.387]  f1 ONLINE MANUAL    pos [-6.119, -2.675] order -
                   age 1.8  lost=False  not_eligible=True
```

f1 stayed refused for 25 s while it was MANUAL — a stationary,
connected, idle truck that the manager would not touch. The mode came
back and the flag cleared on the first state that satisfied every other
clause:

```
00:42:24.932  PUB /f1/hmi/mode <- 'auto'
00:42:25,029 f1 re-earned eligibility          <- 97 ms
[00:42:25.031]  f1 ONLINE AUTOMATIC pos [-6.119, -2.675] order -
                   age 0.0  lost=False  not_eligible=False
```

**The task f2 took did not finish, and the reason is defect 3 again.**
f2 latched a safe-speed trip at 00:42:02.647, 2.6 s after taking the
job, as it passed f1 parked at S10 — the numbers are in defect 3 below.
Every claim this gate makes was measured between 00:41:57 and
00:42:25; the transport itself was abandoned at 00:53:01.412 and the
manager restarted to clear its book.

## [x] Fleet Gate 4 — vehicle loss mid-task

**Verdict: FAILED on the first run, PASS on the re-run after the defect
it found was fixed.** *Kill one agent mid-leg → CONNECTIONBROKEN → task
to queue head → other vehicle completes it; the lost vehicle returns,
gets cancelOrder for its stale order, re-earns eligibility.*

Both runs are below. **The failed one is kept because it is the
evidence** — it is what found the bug, and the fixed run means nothing
without the measurement it is being compared against.

### Run 1, 2026-08-22 01:06 — FAILED, and here is what it found

The task was `S3 → S2`, submitted with f1 parked on the S10 spur and f2
at its spawn pose:

```
01:06:00,858 assigned ft-e4537407 to f1
             (nearest idle to S3: f1 5.22 m <-- chosen, f2 11.50 m)
```

The kill was armed on odom and the cmdline was read before anything was
signalled:

```
$ tr '\0' ' ' < /proc/58566/cmdline
python3 .../m6/deploy/m6/ipc/vda_agent.py
$ tr '\0' '\n' < /proc/58566/environ | grep -E 'VEHICLE|GZ_PARTITION|ROS_DOMAIN'
GZ_PARTITION=m6   ROS_DOMAIN_ID=96   VEHICLE=f1

trigger at 01:06:02.952  x=-5.3485  y=-3.2017   (driving, 0.25 m/s)
01:06:02.971  kill -9 58566
              /proc/58566 is gone
```

**The fleet reacted in 92 ms and reassigned in one more:**

```
01:06:03,063 WARNING f1 is gone (CONNECTIONBROKEN) mid-ASSIGNED_LEG1
01:06:03,064 assigned ft-e4537407 to f2
             (nearest idle to S3: f2 11.50 m <-- chosen)
```

The 92 ms is the broker publishing f1's will. The requeue-to-head and
the reassignment are the owner's loss ruling working exactly as written.
The agent was put back with `m6.sh`'s own spawn shape — `setsid`, the
pid appended to `.m6_pids`, `env VEHICLE=f1`, from `deploy/`, under
`GZ_PARTITION=m6` so `stop` still sweeps it — and the manager saw it:

```
01:06:05.186  respawned vda_agent_f1 as pid 62225
01:06:06,272 WARNING f1 returned holding ft-caec9405 - cancelOrder sent.
```

#### The defect: the cancelOrder reached the agent and did not stop the truck

**The cancel was received, acknowledged and had no effect.** From the
MQTT capture, the instantAction and the actionState it produced:

```
01:06:06.273  uagv/v2/amragent/f1/instantActions
              [{"actionId": "ad0d0cb8…", "actionType": "cancelOrder", …}]
01:06:06.405  state  order=''  rem=0  actionStates=
              [{"actionId": "ad0d0cb8…", "actionType": "cancelOrder",
                "actionStatus": "FINISHED"}]
```

**132 ms, FINISHED.** `_on_actions` published the empty goal on
`/f1/auto/goal` on that path — and **the topic gained no sample.**
`/f1/auto/goal` carried exactly two samples in the whole session,
01:04:54.934 and 01:08:49.471, both scratch cancels sent to a
**long-running** agent. The one at 01:06:06 is missing, and the reason
is that the publisher was **1.1 s old**: a freshly spawned rclpy node
publishes into a discovery window where `nav_node` has not matched it
yet, and a VOLATILE publisher with no subscriber writes to nobody.

The truck answered accordingly — the state stream says it was driving
with no order at all:

```
01:06:06.356  order=''  rem=0  driving=False
01:06:07.696  order=''  rem=0  driving=True     <- no order, moving
01:06:09.320  order=''  rem=0  driving=True
…  every 2 s to 01:06:19.473 and beyond …
```

**Measured:** the truck drove **37.09 s** (01:06:02.971 → 01:06:40.065),
**6.743 m of path** (3.203 m straight line), from (−5.3453, −3.2138) to
(−6.8493, −6.0421), and nav reported **ARRIVED** 0.7839 m from S3 — it
completed the leg of a task that had belonged to another vehicle for
37 s, and the fleet's only lever had already been pulled.

This is not the race the design predicted. The design expected the
returning agent to **resume** its kept order and drive for the seconds
the cancel takes to land. What actually happens is worse and simpler:
**a killed agent restarts with no order at all** (`self.order` is
process memory), while `nav_node` still holds the goal and keeps
driving; the cancelOrder is the one thing that could clear that goal,
and it arrived into an unmatched publisher.

f2 then took the task and could not finish it either: it stopped
2.262 m behind the parked f1 in SAFETY-STOP and both trucks latched
motor-false at 01:06:41.9. **Run 1 failed on both halves.**

### The fix — `m6: cancel is a conversation, not a shout` (`e3c0ddd`)

A single publish of the empty goal is not a stop; it is a request that
may reach nobody. So it is not fire-and-forget any more:

- `vda_agent._begin_cancel` / `_pump_cancel`: the empty goal is
  **republished every drain (10 Hz)** until `cb_nav` shows nav is no
  longer driving our route. The cancelOrder actionState stays
  **RUNNING** until that is SEEN, and goes **FAILED** with a
  `cancelUnconfirmed` entry in `errors[]` after `CANCEL_CONFIRM_S`
  (5.0 s) rather than claiming a stop nobody watched. Silence is not
  confirmation: `nav_state` has to be something nav actually published,
  because a just-restarted agent has heard nothing at all. The
  supervision-loss stop goes through the same loop, minus the
  actionStates nobody asked for.
- A publisher nav has not matched yet is **named once in the log**
  before the retries start — the retry already covers it, but run 1
  spent 37 s inside that window with nothing anywhere to say so.
- `fleet_manager` keeps the other half: a `cancelled` map remembers
  what each returning vehicle was told to drop, every state that still
  shows that order executing past a grace earns one more cancelOrder
  (throttled to the vehicle's own cadence, capped at four), and a truck
  that never lets go is written into the refusal list the operator
  reads. The chase ends on the **vehicle's** state, never on our own
  publish.
- Six new tests: the cancel that keeps asking until nav says IDLE, the
  deadline that reports FAILED, the supervision-loss stop through the
  same loop, the unmatched-publisher log, and the manager chasing and
  then giving up.

### Run 2, 2026-08-22 01:40 — PASS

**Same task, same kill trigger, same restart delay.** Fresh stack
(`./m6.sh deploy` shipped the fixed agent — `grep -c _pump_cancel
deploy/m6/ipc/vda_agent.py` → 7 — then twenty-one pids, both writers,
both recorders, mode `auto` at 01:36:26.641 with 3 matched subscribers,
RESET at 01:36:34.363 / 01:36:36.434, `Motor=True` on both).

**The pre-positioning run paid for itself.** `submit S3 S10` put f1 back
on the S10 spur, and on the way it produced a **second, independent
capture of the S10 orbit** — 0.693 to 0.710 m around a station
declaring `arrive_m` 0.25, the same minimum-turning-radius circle S5
drew in Fleet Gate 1. The scratch cancel that ended it is also the
fix's first live measurement, on a long-running agent where run 1's bug
could not bite:

```
01:39:26.635  cancelOrder -> uagv/v2/amragent/f1/instantActions
[INFO] [vda_agent]: cancel confirmed by nav after 2 publish(es), 0.10 s
```

Then the gate, from a manager restarted with an empty book:

```
01:40:01,942 assigned ft-ee4b580c to f1
             (nearest idle to S3: f1 6.15 m <-- chosen, f2 11.50 m)

$ tr '\0' ' ' < /proc/68840/cmdline
python3 .../m6/deploy/m6/ipc/vda_agent.py
$ tr '\0' '\n' < /proc/68840/environ | grep -E 'VEHICLE|GZ_PARTITION|ROS_DOMAIN'
GZ_PARTITION=m6   ROS_DOMAIN_ID=96   VEHICLE=f1

trigger at 01:40:08.796  x=-6.5235  y=-3.2015
01:40:08.821  kill -9 68840
              /proc/68840 is gone
01:40:08,859 WARNING f1 is gone (CONNECTIONBROKEN) mid-ASSIGNED_LEG1
01:40:08,860 assigned ft-ee4b580c to f2
             (nearest idle to S3: f2 11.50 m <-- chosen)
01:40:10.974  respawned vda_agent_f1 as pid 69695
              GZ_PARTITION=m6   VEHICLE=f1
01:40:11,968 WARNING f1 returned holding ft-4c37d99b - cancelOrder sent.
```

**And this time the cancel was a conversation.** The agent's own log,
the two lines that are the whole fix:

```
01:40:12.131 [WARN] nav has not matched /f1/auto/goal yet - this empty
             goal reaches nobody; retrying at 10 Hz until nav says it
             stopped
01:40:12.362 [INFO] cancel confirmed by nav after 5 publish(es), 0.23 s
```

**The first publish reached nobody — exactly as in run 1 — and the
other four did.** The warning is run 1's 37 seconds, named in the log
the moment it starts instead of discovered a day later in an odom file.
**THE STOP'S TWO WITNESSES ARE NAV AND ODOM, AND NOTHING ELSE.** nav
said IDLE at 01:40:12.362 and the wheels were at rest at 01:40:12.659;
those are the numbers this gate turns on.

The manager's own line is NOT a third witness and must not be read as
one:

```
01:40:12,169 f1 let go of ft-4c37d99b - the cancel landed
01:40:14,475 f1 re-earned eligibility
```

That first line fired **0.49 s BEFORE the truck stopped**, and it fired
on the restarted agent's AMNESIA rather than on any stop: a respawned
process has no order in memory, so its very first state reports
`orderId ''`, the chase entry sees an order the vehicle is no longer
executing, and it clears. **It would have printed identically in run 1**,
where the truck then drove for another thirty-five seconds. Read it as
what it is - the moment the manager stopped chasing - and not as
evidence of a stop.

The chase machinery is therefore not what fixed this gate; the agent's
confirm loop is. What the chase protects is the OTHER shape of the same
flow - a vehicle whose agent stayed alive across a broker bounce and
came back still holding its order - where the state does keep showing
the stale `ft-` order and a second cancelOrder is worth sending. That
case is covered by its own tests and is not what run 2 measured.

**The race window, measured the same way run 1 was:**

| | run 1 (fire-and-forget) | run 2 (closed loop) |
|---|---|---|
| kill | 01:06:02.971 | 01:40:08.821 |
| CONNECTIONBROKEN | +0.092 s | **+0.038 s** |
| task reassigned | +0.001 s | +0.001 s |
| agent respawned | +2.215 s | +2.153 s |
| cancelOrder on the wire | +3.301 s | +3.147 s |
| **truck at rest** | **+37.094 s** | **+3.838 s** |
| **driverless path** | **6.743 m** | **1.359 m** |
| cancel confirmed by nav | never | **0.23 s, 5 publishes** |
| actionState | FINISHED (a lie) | RUNNING → FINISHED on the stop |
| where it stopped | at S3, the pickup | 1.026 m off the aisle |

**9.7× less time and 5.0× less distance**, and the difference is
entirely the four republished goals. The rows below are worse for the
bug than "it carried on at the speed it had": the truck was doing
0.298 m/s when its agent died and **it accelerated to 0.692 m/s** with
nobody driving it - the follower chasing a lookahead on a route no
supervisor owned any more - before the cancel bit at 12.109 and took it
to rest in half a second.

```
01:40:08.845  x=-6.5188 y=-3.2156  v=0.2980   <- kill + 24 ms
01:40:10.437  x=-6.3107 y=-3.7234  v=0.6920
01:40:11.635  x=-6.0736 y=-4.2897  v=0.6718
01:40:12.109  x=-6.0274 y=-4.4227  v=0.2739   <- the cancel biting
01:40:12.536  x=-6.0107 y=-4.4688  v=0.0979
01:40:12.659  x=-6.0099 y=-4.4742  v=0.0000   <- at rest
```

**And the other vehicle completed the task.** f2, holding it since
01:40:08.860, drove west, and this is the honest middle of the gate:

```
f2 HOLD at (-3.57, -5.50), 2.65 m behind f1, which had come to rest
1.026 m north of the dock-aisle centreline. Motor TRUE on both -
nav's own forward guard, not the safety chain, and not a latch.
```

**Defect 2 is unchanged and unfixed: there is no traffic logic, so a
stopped vehicle is an obstacle.** What the fix bought is that f1 was
stopped, idle and eligible within six seconds — so the operator could
simply give it work that moved it out of the way, which is what an
operator would do:

```
01:42:25,159 queued ft-6afd0715: S10 -> S4
01:42:25,159 assigned ft-6afd0715 to f1
             (nearest idle to S10: f1 1.97 m <-- chosen)
                 ^ the only eligible vehicle: f2 was executing
```

f1 climbed its own spur, f2's HOLD cleared and it went back to EN-ROUTE,
and f1 was parked clear at (−6.35, −2.01) — **3.49 m** north of the
aisle — with a scratch cancel that confirmed in the ordinary way. Then:

```
01:43:02,842 f2 arrived at S3 with ft-80862442 - dwelling
01:43:05,850 dwell done - f2 drives ft-ee4b580c to S2 as ft-f341c004
01:43:37,325 f2 completed ft-ee4b580c at S2
```

ARRIVED at (−10.2871, −5.9714), **0.7952 m** from S2 against that
station's `arrive_m` of 0.80. Dwell 3.008 s.

**0 motor-false, both trucks, across the whole gate** — no latch
anywhere in the re-run, where run 1 ended with both trucks latched:

```
01:39:59.775 .. 01:43:37.325
  f1  motor-false 0 of 4351      f2  motor-false 0 of 4351
```

**Ticked.** The lost vehicle's loss is seen in 38 ms, its task is
somebody else's in 39, its stop is confirmed rather than assumed, it
re-earns eligibility in under six seconds, and the replacement finishes
the transport. What still needs M6.4 is the two-metre gap between them.

## [x] Fleet Gate 5 — manager restart mid-operation

**Verdict: PASS.** *Kill and restart the manager while a vehicle drives
→ re-sync from retained topics, no double assignment, the driving
vehicle finishes its leg and the manager is honest about the empty
queue; the operator resubmits and life continues.*

```
01:10:26,838 assigned ft-f43d32b0 to f1
             (nearest idle to S2: f1 7.91 m <-- chosen, f2 13.91 m)

$ tr '\0' ' ' < /proc/64609/cmdline
python3 .../m6/fleet/fleet_manager.py
$ tr '\0' '\n' < /proc/64609/environ | grep GZ_PARTITION
GZ_PARTITION=m6

01:10:41.828  f1 at (-9.4543, -5.3592)  |v| = 0.1716   <- mid-leg-1
01:10:41.850  kill 64609
01:10:42.855  f1 at (-9.5892, -5.3730)  |v| = 0.1890   <- still driving
01:10:53.709  f1 at (-10.2874, -5.8959) |v| = 0.1680   <- still driving
```

**Losing the fleet degraded and did not endanger:** the truck kept its
order and kept driving for the whole 12.19 s with no master control on
the machine. The manager went back up with `m6.sh`'s spawn shape:

```
01:10:54,041 fleet manager up - broker 127.0.0.1:1883, dwell 3.0s
01:10:54,142 subscribed - vehicles and the admin wire
01:10:54,243 first status published on fleet/status, retained
             new manager pid 66017
```

**It cancelled nothing.** Counted straight off the MQTT capture:

```
instantActions messages on the wire since the manager was killed: 0
```

**It adopted the driving truck by waiting.** Its own first useful
document, 0.5 s after startup, shows a vehicle executing an `ft-` order
it has no record of — and an empty queue and an empty task table:

```
[01:10:54.747]  queue 0  tasks 0
  f1 ONLINE AUTOMATIC pos [-10.332, -5.988]  order ft-0bded6d3  age 0.0
```

**No double assignment**: assignment requires idle-confirmed, and
`executing_order` was not None. f1's state stream is continuous across
the whole outage — same orderId on both sides of 12 s with no fleet —
and it finished its leg 0.95 s after the new manager came up:

```
01:10:40.288  ft-0bded6d3  rem 1  driving=True  (-9.252, -5.375)
01:10:42.386  ft-0bded6d3  rem 1  driving=True  (-9.524, -5.364)
   …  the manager is dead for these six rows  …
01:10:52.588  ft-0bded6d3  rem 1  driving=True  (-10.228, -5.802)
01:10:54.686  ft-0bded6d3  rem 1  driving=True  (-10.332, -5.988)
01:10:54.994  ft-0bded6d3  rem 0  driving=True  (-10.346, -6.020)
01:10:57.087  ft-0bded6d3  rem 0  driving=False (-10.345, -6.066)
```

**And it was honest about what it had lost**, in the operator's own
screen rather than in a log nobody reads:

```
TASKS (0 shown, 0 done)
  (none - the fleet has no work. A restarted manager has no tasks: resubmit.)
```

**The operator resubmitted and life continued:**

```
01:11:27,865 assigned ft-f98ae3e9 to f1
             (nearest idle to S3: f1 4.29 m <-- chosen, f2 11.51 m)
01:12:20,445 f1 arrived at S3 with ft-2534cfd8 - dwelling
01:12:23,455 dwell done - f1 drives ft-f98ae3e9 to S1 as ft-9376dcf7
01:13:03,346 f1 completed ft-f98ae3e9 at S1
```

Dwell 3.010 s. **0 motor-false across the whole gate**, 01:10:26 to
01:13:03 — it is one of the four windows in the session's audit that
contains no latch at all.

## [x] Fleet Gate 6 — operator truth

**Verdict: PASS.** *During Gates 1 and 4, the status document never
shows a dead or lost vehicle as driving; state age visibly grows on the
lost vehicle.*

**Gate 1 (both trucks alive and driving):** every row above carries an
age between 0.0 and 1.9 s against a 2.0 s publish period, the position
tracks the odom, and `executing_order` empties exactly at DONE.

**Gate 4 (f1 killed at 01:06:02.971):** the rows, unedited —

```
01:06:00.925  conn ONLINE           pos [-5.443, -2.842] order ft-caec9405 age 0.5  lost=False
01:06:02.864  conn ONLINE           pos [-5.443, -2.842] order ft-caec9405 age 1.9  lost=False
01:06:03.106  conn CONNECTIONBROKEN pos [-5.443, -2.842] order ft-caec9405 age 2.1  lost=True
01:06:05.070  conn CONNECTIONBROKEN pos [-5.443, -2.842] order ft-caec9405 age 4.1  lost=True
01:06:06.306  conn ONLINE           pos [-5.443, -2.842] order ft-caec9405 age 5.3  lost=False not_eligible=True
```

**The vehicle was moving through every one of those rows** — it drove
6.743 m after the kill — and the document never once said so. It froze
the last position it was told, grew the age, and flew CONNECTIONBROKEN
and `lost`. `state_age_s` is computed at render time, not stamped on
arrival, which is why a dead feed cannot present as a live one.

**The longer window is the better proof.** Later in the session an
operator slip (below) left f1's agent down for 70 s. The age is
monotonic and the position never moves:

```
01:08:51.677  OFFLINE  pos [-6.849, -6.042]  age  0.2  lost=True
01:09:01.722  OFFLINE  pos [-6.849, -6.042]  age 10.2  lost=True
01:09:11.763  OFFLINE  pos [-6.849, -6.042]  age 20.3  lost=True
01:09:21.810  OFFLINE  pos [-6.849, -6.042]  age 30.3  lost=True
01:09:31.848  OFFLINE  pos [-6.849, -6.042]  age 40.4  lost=True
01:09:37.868  OFFLINE  pos [-6.849, -6.042]  age 46.4  lost=True
```

**And the document caught the operator's own mistake.** Interleaved with
those rows, every second row read `conn OFFLINE  mode None  pos None
age None` — because a slip in the recovery script (`tail -1 .m6_pids`
had been shifted by the Gate-4 agent respawn) killed an agent instead of
the manager and left **two fleet managers** alive, both publishing the
same retained topic. Nothing in the design prevents that: there is no
lock, no client-id collision (the manager sets `client_id`
"fleet-manager", and a second connection with the same id disconnects
the first — which is what made the two documents alternate rather than
race), and no "who is master" field in the document. **Named as a
finding for M6.5:** two managers on one broker is one command away, and
the screen showed it as a flicker rather than as an error.

## The three defects this session found

1. **A restarted agent's cancelOrder could not stop its truck** —
   FOUND AND FIXED (Fleet Gate 4, `e3c0ddd`). The action was received
   and FINISHED in 132 ms; the empty goal it published reached nobody
   because the rclpy publisher was ~1 s old and `nav_node` had not
   matched it. Measured cost: 37.09 s and 6.743 m of a driverless truck
   completing a leg that belonged to another vehicle. The cancel is now
   republished at 10 Hz until nav confirms the stop, the actionState
   stays RUNNING until then and goes FAILED with an errors[] entry if
   it never comes, and the manager re-sends to a vehicle whose states
   still show the order. Re-run measured 3.838 s and 1.359 m, with the
   confirmation arriving after five publishes — **the first of which
   still reached nobody**, which is the bug caught in the act and
   logged instead of driven through.
2. **A stopped vehicle blocks its replacement** (Fleet Gate 4). 2.262 m
   centre-to-centre was enough for a protective stop and a mutual
   latch. Requeue-to-head is sound; on this floor it needs M6.4's
   traffic layer to be useful.
3. **The safe-speed link latches on a step change in V_Limit.** Three
   times today, on both trucks: the warning field trips, `V_Limit`
   steps 1500 → 300 mm/s in one scan, and the truck is already faster
   than 300 — so the F-CPU drops the motor and latches. The clearest
   capture is f2 at 00:42:02, passing f1 parked at S10:

   ```
   00:42:01.930  WF b/r/l T/T/T   V_Limit 1500  enc -300/-300  Motor True
   00:42:02.449  odom |v| = 0.6726 m/s
   00:42:02.647  WF b/r/l T/F/T   V_Limit  300  enc 0/0        Motor False
   ```

   The right warning field saw the parked truck at 2.30 m (2.5 m
   threshold), the limit stepped, and the monitor compared it against a
   truck already moving — with no deceleration window. The other two
   were f1 leaving S2 (00:31:40, |v| 0.3825 against a limit of 300) and
   f1 leaving S3 (01:01:33). **The chain is doing its job**; what is
   missing is a ramp, and it is what makes two vehicles on one aisle
   expensive. Vehicle-side debt, not fleet-side, and it belongs with
   M6.4.

   A fourth, smaller one is recorded above: **S5 cannot be reached from
   the x = 12 connector** (6.18 laps at a mean radius of 0.6884 m
   against `arrive_m` 0.25), and **a restarted agent adopts whichever
   latched `/fN/hmi/mode` publisher reaches it first.**

## Carried to M6.5 — three things this session found and did not fix

Beside the two-managers finding in Gate 6, the Gate 4 re-run left two
gaps that are wiring, not measurement, and both belong with the fleet
layer's next pass:

1. **The manager's cancel-chase cannot engage for a RESTARTED agent.**
   `_chase_cancel` ends the moment the vehicle's state stops showing
   the cancelled order - and a respawned agent's FIRST state already
   says `orderId ''`, because the order lived in the dead process's
   memory. So the retry that exists for the resume case is structurally
   unreachable in the restart case, which is the one Gate 4 measures.
   Measured proof: the chase cleared at 01:40:12.169, 0.49 s before the
   truck came to rest, and it would have cleared just as fast in the
   failed run.

2. **Nothing carries the agent's own failure to the operator.** The
   agent now reports a cancel it could not confirm as an actionState
   `FAILED` plus a `cancelUnconfirmed` entry in `errors[]`, and the
   manager reads neither: `_check_rejection` only looks for
   `orderError`, and the status document renders no action or error
   column at all. In the corner where a restarted agent ALSO never
   gets its stop confirmed, the screen would stay quiet - the two gaps
   compound, and the second is what makes the first invisible.

3. **The refusal list's `taskId` field carries an ORDER id on the
   chase-give-up path.** `_chase_cancel` passes `entry["order_id"]` to
   `_note_refusal`, whose column the CLI renders as TASK. Both wear the
   `ft-` prefix, so an operator reading that row cannot tell which one
   they are looking at - and it is the row that says a truck ignored
   four cancelOrders, which is the last row that should be ambiguous.

## Teardown

```
> {"quit":true} -> 127.0.0.1:5910         > {"quit":true} -> 127.0.0.1:5920
shutting down: writing the trip values    shutting down: writing the trip values
writer for f1 is down                     writer for f2 is down
```

`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` afterwards
returns three VS Code language servers and nothing else. Both recorders
were stopped next, the ROS one printing its session counts (above).

```
$ ./m6.sh stop
  … swept 58374 (plc_link.py) … swept 66017 (fleet_manager.py)
  … swept 58883 (vda_agent.py) … swept 65016 (vda_agent.py)
  … swept 57994 (mosquitto-vendored)
  killed 57994 … killed 65016                 (17 killed lines)
down.
```

The pidfile held **29** lines against the twenty-one started: the extra
eight are this session's three manager restarts, two agent respawns and
the recovery spawns, every one of them appended by the same
`setsid … echo $$ >> "$1"` shape `m6.sh` uses, which is why `stop` swept
them all. Seventeen of the twenty-nine were still alive to kill.

```
$ ss -uln | grep -E ':(5110|5111|5120|5121)'  ->  all four free
$ ss -ltn | grep ':1883'                      ->  free
$ pgrep -af 'gz sim|plc_link.py|…|fleet_manager.py|mosquitto-vendored'
                                              ->  none
$ test -f .m6_pids                            ->  removed
```

```
$ python3 -m pytest m6/tests/ -q
370 passed in 58.26s
$ python3 -m pytest m5_ver2/step5/tests/ -q
220 passed in 3.53s
```

### And again after Gate 4's re-run, 01:44

The second stack came down the same way. Writers first:

```
> {"quit":true} -> 127.0.0.1:5910         > {"quit":true} -> 127.0.0.1:5920
shutting down: writing the trip values    shutting down: writing the trip values
writer for f1 is down                     writer for f2 is down
```

`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` returns
three VS Code language servers and nothing else. The ROS recorder's
session, printed on `{"quit": true}`:

```
f1_status 10124  f2_status 10097   f1_odom 9096  f2_odom 9096
f1_fields  5054  f2_fields  5042   f1_nav  5048  f2_nav  5039
f1_route      4  f2_route      2   f1_goal    4  f2_goal    0
```

**`/f1/auto/goal` carries four samples and `/f2/auto/goal` none**, and
that is the fix's own shape: two from the orbit cancel at 01:39:26 (the
long-running agent, confirmed after 2 publishes) and two from the
respawned agent's five at 01:40:12 — **the recorder, a subscriber that
had been up for four minutes, still missed three of them**, which is
the discovery window that ate run 1 seen from a third angle. nav got
them, and nav is the one that had to.

```
$ ./m6.sh stop                     (23 pidfile lines)
  … killed 69212 … killed 69695
down.
$ ss -uln | grep -E ':(5110|5111|5120|5121)'  ->  all four free
$ ss -ltn | grep ':1883'                      ->  free
$ pgrep -af 'gz sim|…|fleet_manager.py|mosquitto-vendored'  ->  none
$ test -f .m6_pids                            ->  removed
```

```
$ python3 -m pytest m6/tests/ -q
376 passed in 78.02s          (370 + the six the fix brought)
$ python3 -m pytest m5_ver2/step5/tests/ -q
220 passed in 2.86s
```


# M6.4 — the traffic gates

**Date: 2026-08-22, 10:56–12:09. Measured by the scripted driver + CLI —
no panel, no human.** One WSL session, two stacks (the second carries a
fix this session found), one broker, twenty-one pids each time. Every
order below was generated by `fleet/fleet_manager.py` from a transport
submitted with `fleet/fleet_cli.py`; `tools/send_order.py` was not used
once.

**Four of the six gates passed. Gate 1 failed on its first traffic run,
on a real defect, and both runs are kept** — the failed one is the
evidence that found the bug. **Gate 2 is BLOCKED and is not ticked:** its
wait was measured three times over and its handover not once, for two
named reasons, one of them structural and owed to M6.5.

## Setup, verbatim

```
$ cd /mnt/c/Users/ozkan/projects/amr-agent/m6
$ ./m6.sh deploy
instantiated .../m6/vehicles/f1
instantiated .../m6/vehicles/f2
deployed 26 files to .../m6/deploy
$ head -2 deploy/MANIFEST
# m6 deploy - generated, do not edit
# source-git: aa8c1e6

$ ./m6.sh start --headless
starting the Step 6 vehicle side (partition m6, domain 96, gui false)
  broker 80246          world 80252
  plc_link_f1 80626     cmd_gate_f1 80632     cmd_mux_f1 80640
  field_eval_f1 80686   encoder_link_f1 80725 sensor_link_f1 80735
  nav_node_f1 80784     vda_agent_f1 80811    hmi_f1 80881
  plc_link_f2 80897     cmd_gate_f2 80927     cmd_mux_f2 80956
  field_eval_f2 81026   encoder_link_f2 81055 sensor_link_f2 81074
  nav_node_f2 81137     vda_agent_f2 81164    hmi_f2 81219
  fleet 81254
```

**Twenty-one pids**, no `exited during startup` (folded two and three to
a row here; the real output is one per line). **The deploy tree was
REGENERATED before a truck moved**, and that mattered more than usual:
its MANIFEST still pinned `source-git: e3c0ddd`, which is M6.3's agent —
the trucks would have run pre-stitch code under green tests, and every
base extension in this file would have been refused by a vehicle that
had never heard of one. Twenty-six files now, not twenty-five:
`fleet/traffic.py` is new.

Then, on Windows, one scripted writer per vehicle, started detached with
`Start-Process … -RedirectStandardOutput logs\scripted_writer_fN.log`:

```
> python m6\tools\scripted_writer.py --vehicle f1 --virtual --ctl-port 5910
> python m6\tools\scripted_writer.py --vehicle f2 --virtual --ctl-port 5920
streaming PLC state to 172.19.180.72:5110   (f2: …:5120)
VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop
listening for the back scanner on 0.0.0.0:5111   (f2: …:5121)
control channel on 127.0.0.1:5910                (f2: …5920)
E-Stop=True  Motor=False  ack=False | PF b/r/l=T/T/T  WF b/r/l=T/T/T
```

`PF/WF` all `T` on the first cycle is a live WSL→Windows 5111/5121 link
and not a default, and `Motor=False` is the startup acknowledge the
F-program demands. The mode went out through the recorder's own
transient-local publishers, **before** the RESET, so no ROS node was
started after a truck could move:

```
10:57:21.050  PUB /f1/hmi/mode <- 'auto' (3 matched subscribers)
10:57:21.100  PUB /f2/hmi/mode <- 'auto' (3 matched subscribers)
10:57:32.167  ->127.0.0.1:5910  {"ack": true}
10:57:32.257  ->127.0.0.1:5920  {"ack": true}
10:57:35.418  reply {"motor": true, "line": "E-Stop=True  Motor=True
              ack=False | PF b/r/l=T/T/T  WF b/r/l=T/T/T |
              case=1  V_Limit=1500  enc=0/0 ok"}      (f2 identical)
```

**PowerShell strips the double quotes out of a native command's
argument** (M6.2 recorded that, twice; M6.3 again), so every writer
command in this session went through a wrapper that builds the JSON
itself from `key=value` words. The four buttons are still the panel's
four and nothing more.

The fleet manager is the one process this session restarted often —
seven times, for `--no-traffic` and to clear the task book between
staged runs. Each restart used `m6.sh`'s own spawn shape (`setsid`, pid
appended to `.m6_pids`), which is why `stop` swept every one of them.

## The two instruments

**ROS side: ONE recorder process** — M6.1's `gate_rec` lineage, M6.3's
`rec3.py` unchanged, with a UDP control socket, twelve subscriptions and
the two `/fN/hmi/mode` publishers, all created before the first RESET
and **kept running across the mid-session stack restart**, so nothing was
started while a truck could move at either end of it:

```
python3 rec3.py 14400 /tmp/m64/cap 5940 \
  f1_status=/f1/plc/status=String   f2_status=/f2/plc/status=String \
  f1_fields=/f1/safety/fields=String f2_fields=/f2/safety/fields=String \
  f1_nav=/f1/auto/state=String      f2_nav=/f2/auto/state=String \
  f1_goal=/f1/auto/goal=String      f2_goal=/f2/auto/goal=String \
  f1_route=/f1/auto/route=String    f2_route=/f2/auto/route=String \
  f1_odom=/f1/gz/odom=Odometry      f2_odom=/f2/gz/odom=Odometry \
  pub=mode1=/f1/hmi/mode=transient_local \
  pub=mode2=/f2/hmi/mode=transient_local
```

Its whole session, printed on `{"quit": true}`:

```
f1_status 87654  f2_status 87649   f1_odom  78477  f2_odom  78477
f1_fields 43849  f2_fields 43817   f1_nav   43812  f2_nav   43784
f1_route     26  f2_route     20   f1_goal     18  f2_goal      8
```

**There is no goal publisher in that command line.** The eighteen
samples on `/f1/auto/goal` and eight on `/f2/auto/goal` are the AGENTS'
own empty goals answering `cancelOrder` — eight scratch cancels this
session sent by hand to clear staged runs, two the manager sent on
Gate 5's returning trucks, and their retries. **No HMI goal was
published by anything, at any point.**

**MQTT side: one paho subscriber** on `uagv/v2/amragent/+/#` **and
`fleet/#`**, one JSONL line per message with the retain flag kept, up at
10:56:17.348 and left running across the stack restart and all seven
manager restarts (`disconnected` at 11:27:08.258, `connected -
subscribed` at 11:27:17.264 — the broker went down with the stack and it
came back on its own). It is not a ROS node, so the rig rule does not
bite it, and it is the only reader that can say what the fleet saw.

## The rig rule held; the safe-speed link still does not

No ROS node was started between a RESET and the end of a run, and no
gate below was starved. `vda_agent_f1` and `vda_agent_f2` were each
respawned once, in Gate 5, which is that gate's own subject.

**Every `motor: false` sample in the session belongs to a run this file
names.** Eight onsets in 85,644 samples on f1 and 85,640 on f2.

**Those denominators are smaller than the recorder's own session totals
above (87,654 / 87,649) and the gap is the sweep's, not the capture's:**
it was run while the rig was still up, roughly a hundred seconds before
the recorder was stopped, so the last ~2,010 samples per truck are
outside it. What is in that tail is one more `motor: false` run per
truck — 12:09:36.511..12:09:50.761 on f1 (286 samples) and
12:09:36.617..12:09:50.767 on f2 (284) — **the writers' own trip values
on `{"quit": true}`, at teardown**, which M6.3 recorded in the same
place for the same reason. No gate is inside that tail, and re-swept
over the finished files the counts are 4,388 of 87,654 and 10,332 of
87,649, which is the eight below plus those two.

```
f1  4102 samples in 3 runs        f2  10048 samples in 5 runs
  10:56:32.675 .. 10:57:32.157      10:56:31.448 .. 10:57:32.242
      the startup acknowledge, cleared by the first RESET
  (none)                            10:59:40.041 .. 11:01:32.142
                                        SAFE-SPEED LATCH, warm-up, no traffic
  (none)                            11:04:52.142 .. 11:08:15.541
                                        SAFE-SPEED LATCH - GATE 1's CONTROL RUN
                                        (this one is a measurement, not noise)
  11:27:23.264 .. 11:27:42.211      11:27:25.381 .. 11:27:42.317
      the restarted stack's startup acknowledge, cleared by its RESET
  11:53:26.561 .. 11:55:32.961      11:56:31.367 .. 11:58:19.867
      SAFE-SPEED LATCH, Gate 5 run 1 (both named under Gate 6)
```

**Gate 1's traffic run, Gate 2's four runs, Gate 3, Gate 4 and Gate 5's
run 2 contain none of these** — 32,260 samples per truck with the
reservation ledger live and not one Motor drop. That is Gate 6's
measurement and it is set out there properly, causation and all.

The latch itself is M6.3's third defect, unchanged and not M6.4's:
`virtual_fplc._healthy()` demands `max(|ENC_A|,|ENC_B|) <= V_Limit`, and
`V_Limit` drops from 1500 to 300 mm/s the instant ANY warning field is
violated (ruling 2026-08-20). Nothing in nav slows the truck to
0.3 m/s when that happens, so a truck doing 0.7 m/s that sees anything
inside 2.5 m latches its speed instance and needs an operator's RESET.
**Which is exactly what two trucks meeting each other does, and it is
why Gate 1's control run is worth the space below.**

## [x] Gate 1 — head-on, resolved

*Two vehicles ordered toward each other down one corridor. Without
traffic reproduce the jam and measure the standoff; with traffic one
holds at a node, the other passes, the held one continues, both arrive.
Hold/release timeline, base extensions, 0 motor-false.*

**One scenario, run three times.** Both runs use the same two transports
and the same two spawn poses, so the only variable is the ledger:

```
submit S3 S5   --task-id …-a   ->  f1 (nearest to S3: 5.50 m)
submit S4 S10  --task-id …-b   ->  f2 (nearest to S4: 5.50 m)
```

f1 fetches at S3 in the west dock and drives EAST along the dock aisle
before turning north at the x=0 connector; f2 fetches at S4 in the east
and drives WEST along the same aisle to the S10 spur. They are head to
head on `(-6.0,-5.5) … (0.0,-5.5)`, and their destinations are not each
other's floor — which is what makes this a head-on that CAN resolve
rather than the swap Gate 4 measures.

### The control run — `--no-traffic`, 11:03:51

The manager was restarted with the flag and said so, and so did the
operator's screen:

```
10:58:22,284 fleet manager up - broker 127.0.0.1:1883, dwell 3.0s,
             traffic OFF (--no-traffic: every route granted whole)

TRAFFIC (OFF - --no-traffic: every route is granted whole, which is the
         M6.3 behaviour)
```

Both trucks were sent their whole routes. They closed at a combined
0.91 m/s and this is the encounter, sample by sample, from f2's own
field and status streams:

```
11:04:51.813  right SAFE     2.511 m   v_limit 1500   f2 v = 0.699
11:04:52.014  right SAFE     2.372 m   v_limit 1500   f2 v = 0.694
11:04:52.114  right WARNING  2.295 m   <- the field goes
11:04:52.142  motor FALSE               v_limit  300   f2 v = 0.689
11:04:52.396  x=3.7241 y=-5.2024 v=0.0000
```

**The standoff: 3.836 m centre to centre** (f1 at `(-0.0422,-5.5515)`,
f2 at `(3.7751,-5.1774)` at 11:04:52.154), 2.295 m from f2's forward
right scanner to f1's body. f2 was doing **689 mm/s against a limit that
had just become 300** — 2.30× — so the F-model's speed instance latched,
STO opened, and the truck came to rest in **0.242 s over 0.057 m**.

**The same encounter did not latch f1, and the reason is the whole
rule:** f1's own right field went to WARNING at 2.281 m one sample
later and its `v_limit` dropped to 300 too — but f1 was doing
**0.2185 m/s**, under the reduced limit, so nothing was demanded. One
truck was fast and one was slow, and the fast one stopped itself.

What that cost, measured:

```
f2 latched            11:04:52.142
operator RESET        11:08:15.509      <- 203.4 s of a truck no fleet
                                           action could move
f2 arrived S10        11:08:49.867      pose (-5.9328,-2.7370)
                                        error 0.2464 m
```

**4069 samples of `motor: false`, and the only thing that cleared them
was a human pressing acknowledge.** f1, unlatched, drove on and finished
its own transport. So with traffic off the head-on does not merely jam —
it ends in a latched safety stop on one of the two trucks, and the
transport waits for a person. (The warm-up run before this one, same
manager, produced the same signature: f2's right field at 2.294 m,
0.6809 m/s, 2243 samples latched at 10:59:40.)

### The traffic run, first attempt, 11:10:06 — FAILED

Traffic did its half correctly on the first try. f2's leg 2 came out
split, and the screen said so:

```
TRAFFIC (on)
  f1  holds  (0.0,-5.5) (0.0,-5.5)-(0.0,5.7) (0.0,5.7) … +1 more
  f2  holds  (3.0,-5.5)
  f2  WAITS  (0.0,-5.5)
  g1-a  base 9 released + 0 horizon
  g1-b  base 3 released + 4 horizon
```

f2 drove to the end of its base and stopped there on its own, with no
pause action, and reported it:

```
11:11:08.901  f2 state  last wp3 seq 4  rel 0/4  newBaseRequest TRUE
11:11:11.577  /f2/auto/state  ARRIVED  goal ft-582a…  (nav's own word)
```

Then f1 passed, the floor came free, the fleet published
`orderUpdateId 1` — **and the vehicle refused it, 1,873 times:**

```
11:11:31.896  ORDER f2 ft-965ba9c1 upd 1  base wp1..S10  horizon -
11:11:31.896  f2 state errors: [{"errorType": "orderError",
              "errorDescription": "no order is executing - nothing to
              extend", "errorReferences":[{"orderId":"ft-965ba9c1"}]}]
              … 1873 publishes, 1873 refusals, 11:11:31.896..11:15:09.223
REFUSED  ft-965ba9c1  f2 refused 5 base extensions in a row - the truck
                      is stopped at the end of its base
```

**f1 completed** (S5 at 11:12:03.162, pose `(11.3578,5.6503)`, error
0.2422 m against `arrive_m` 0.25). **f2 never did.** 0 motor-false on
both trucks, 6460 samples each — traffic kept them apart perfectly and
then could not let the held one go.

The defect is one clause in the vehicle, and it is written up under "The
defect this session found", below. Fixed in `11bb499`, redeployed
(`source-git: 11bb499`, 26 files), stack restarted, and the gate re-run
on the identical scenario.

### The traffic run, 11:27:56 — PASS

```
11:28:21.665  ORDER f2 ft-582a00b3 upd 0
              base wp1,wp2,wp3   horizon wp4,wp5,wp6,S10
11:28:21.722  f2 WAITS (0.0,-5.5)          g1r2-b base [3, 4]
11:29:03.509  f2 at rest at (3.2075,-5.3945)
11:29:21.442  ORDER f2 ft-582a00b3 upd 1
              base wp1,wp2,wp3,wp4,wp5,wp6,S10   horizon -
11:29:21.543  g1r2-b base [7, 0]
11:29:53.267  ARRIVED f1 at S5   pose (11.3585, 5.6504)  error 0.2415 m
11:29:57.559  ARRIVED f2 at S10  pose (-5.9273,-2.7376)  error 0.2484 m
```

**The hold, timed: 59.78 s** from the split order to the extension, of
which **17.93 s** was the truck sitting still at the end of its base;
the rest was the drive to the base end. The release is 77 ms behind the
cause — f1's ledger entry lost `(0.0,-5.5)` at 11:29:21.466 as it
reached the connector's north end, and f2's base grew at 11:29:21.543.

**Base extensions: exactly one, `orderUpdateId 0 → 1`.** One truck held
at a node, the other passed, the held one continued, both arrived.

**0 motor-false, both trucks, whole gate:**

```
11:27:56 .. 11:29:58   f1  motor-false 0 of 2440
   (122 s at 20 Hz)    f2  motor-false 0 of 2440
```

The denominator is checkable: `/fN/plc/status` runs at 20 Hz, the window
is 122 s, and 122 x 20 = 2,440. It is the same window and the same count
Gate 6's table below carries, and the 32,260 there is built from it.

and the trucks were not merely far apart — **closest approach 2.947 m at
11:29:03.337**, closer than the 3.836 m at which the control run
latched. The difference is speed, not distance: both `v_limit`s did drop
to 300 mm/s as the warning fields overlapped, and inside those windows
the fastest either truck went was 0.2512 m/s (f2) and 0.3013 m/s (f1, on
odom, which is not the encoder the F-model reads), against the control's
0.6713 m/s. Traffic did not keep the trucks out of each other's warning
fields. **It kept the one that had to wait STOPPED while they overlapped,
and a stopped truck cannot violate a speed limit.**

**Ticked.**

## [ ] Gate 2 — station contention: BLOCKED

*Both tasks to the same station; the second waits, then arrives. No
two-in-a-spur.*

**Measured and not passed. Four runs. The WAIT is measured three times
over and the "no two-in-a-spur" clause holds in every one of them; the
HANDOVER — the second vehicle arriving at the contended station — is not
measured once, and the two reasons are different.**

### Run A, 11:34:01 — a spur station, and the junction deadlocks

`submit S4 S5` (f2, nearest 5.50 m) and `submit S4 S3` (f1, 11.50 m):
one pickup, S4, at the end of a 2.5 m spur off `(6.0,-5.5)`.

```
11:34:02,061 f1 gets 2 of 5 nodes to S4 as base and 3 as horizon -
             the rest of the corridor is taken
11:34:06,074 ft-0d1a496a: base extended to 3 released + 2 horizon
             as orderUpdateId 1 on f1
11:34:23,223 f2 arrived at S4 with ft-76ed5a59 - dwelling
11:34:23,223 ft-0d1a496a: base extended to 4 released + 1 horizon
             as orderUpdateId 2 on f1
11:34:26,233 f2 gets 1 of 6 nodes to S5 as base and 5 as horizon -
             the rest of the corridor is taken
```

Read those last three lines together, because they are the finding. **At
the instant f2 arrived at S4 it released the junction behind it — and in
the same millisecond the fleet handed that junction to the truck queued
for the same station.** Three seconds later f2's dwell ended and it
asked for its own way out, and the way out was gone. That is Gate 4's
deadlock, and it is measured there.

The gate's own clause held perfectly: **f1 came to rest at
`(5.7705,-5.4990)`, 2.436 m short, and never entered the spur.** No
two-in-a-spur. But the second truck never arrived, and it could not
have: on this graph a spur station has exactly one junction, the waiting
vehicle's route always contains it, and the occupant always releases it
on arrival — three seconds before it needs it back. **A spur station
cannot be handed from one vehicle to another under this policy.** That
is an M6.5 item and it is on the carry list with a shape for the fix.

### Runs B and C — aisle stations, and the trucks could not arrive

S1 and S5 are the two stations that sit ON their aisle and have no spur
(`stations.py`), so they have no junction to lose. Both were staged with
both tasks on the same station.

```
run B, 11:38:43  submit S5 S4 (f2)   submit S5 S6 (f1)
  11:42:13.107  f1 at rest at (7.7694, 5.6519)
                f1 WAITS (11.6,5.7)   g2b-b base 4 released + 1 horizon
  f2 orbited S5 at 0.660 .. 0.721 m over 3217 samples, against that
  station's arrive_m of 0.25, and never arrived.

run C, 11:46:09  submit S1 S2 (f1)   submit S1 S4 (f2)
  11:46:34       f2 at rest at (0.2300,-5.4930)
                f2 WAITS (-3.0,-5.5)  g2c-b base 2 released + 1 horizon
  f1 orbited S1 at 0.318 .. 0.805 m and never arrived.
```

**Both holds are exactly right and both occupants failed to arrive for a
reason that predates M6.4:** the minimum-turning-radius circle
`stations.py` documents and M6.3's Fleet Gate 1 measured at S10 and S5
(0.693–0.710 m there, 0.660–0.721 m here). A vehicle cannot reach a
point inside its own turning circle, and an `arrive_m` of 0.25 at the
end of a short straight run is inside it. Nothing about traffic is
implicated: the truck that orbited was the one holding the station, with
its whole route granted.

### Run D, 11:50:58 — the release half, measured

Since the handover could not be staged through a dwell, it was staged
through the operator: f1 idle **on** S1, f2 ordered to it, and f1 then
given work that takes it west.

```
11:50:58.442  ORDER f2 ft-fb1b8a6f upd 0  base wp1   horizon S1
11:50:58.495  f2 WAITS (-3.0,-5.5)        g2d-wait base [1, 1]
              (f1 holds (-3.0,-5.5) - the node its body is on)
11:51:17.401  ORDER f2 ft-fb1b8a6f upd 1  base wp1,S1   horizon -
11:51:31.000  ARRIVED f2 at S1  pose (-2.7619,-5.4834)  error 0.2387 m
11:51:34.049  ORDER f2 ft-26655b40 upd 0  (leg 2, after a 3.0 s dwell)
11:52:04.973  ARRIVED f2 at S4  pose (6.2296,-7.9021)   error 0.2496 m
```

**Held 18.96 s, released 56 ms after f1's ledger entry let go of the
node, arrived 13.6 s later, and completed.** That is the mechanism
working end to end; what it is not is two tasks contending for one
station, which is what the gate asks for.

**Not ticked.** 0 motor-false across all four runs (0 of 3100, 6260,
5300 and 1540 samples per truck).

## [x] Gate 3 — base extension is stitching, not restarting

*Capture the `orderUpdateId` sequence and prove the vehicle never
re-drives a passed node — `lastNodeId` monotone across the update.*

**Every base extension a vehicle ACCEPTED in this session, from the
vehicles' own state streams** (the 1,873 the vehicle refused in Gate 1's
first traffic run never became a state change, and are that gate's
evidence, not this one's), with the last node each truck had passed
on either side of the stitch:

```
f2 11:29:21.465  ft-582a00b3  upd 0 -> 1   lastNodeSequenceId 4 -> 4
f1 11:34:06.101  ft-0d1a496a  upd 0 -> 1   lastNodeSequenceId 0 -> 0
f1 11:34:23.302  ft-0d1a496a  upd 1 -> 2   lastNodeSequenceId 2 -> 2
f2 11:51:17.465  ft-fb1b8a6f  upd 0 -> 1   lastNodeSequenceId 0 -> 0
f1 12:06:13.392  ft-83ee60b2  upd 0 -> 1   lastNodeSequenceId 6 -> 6

5 base extensions observed on the wire, 0 backwards steps
```

The sequence id does not move ACROSS a stitch — that is the point, the
truck is standing where it was — and it never moves backwards WITHIN an
order either; the sweep above checks both. Gate 1's own stream, whole:

```
11:28:21.841  ft-582a00b3 upd 0  last wp1  seq 0   rel 2/6  (6.227,-7.868)
11:28:44.823  ft-582a00b3 upd 0  last wp2  seq 2   rel 1/5  (5.519,-6.114)
11:29:00.887  ft-582a00b3 upd 0  last wp3  seq 4   rel 0/4  (3.719,-5.161)
11:29:21.465  ft-582a00b3 upd 1  last wp3  seq 4   rel 4/4  (3.207,-5.394)
11:29:28.985  ft-582a00b3 upd 1  last wp4  seq 6   rel 3/3  (0.791,-5.553)
11:29:33.975  ft-582a00b3 upd 1  last wp5  seq 8   rel 2/2  (-2.231,-5.508)
11:29:39.395  ft-582a00b3 upd 1  last wp6  seq 10  rel 1/1  (-5.208,-5.547)
11:29:57.559  ft-582a00b3 upd 1  last S10  seq 12  rel 0/0  (-5.927,-2.738)
```

`upd 0 → 1` at 11:29:21.465 changes the count of released nodes left to
drive from 0 to 4 and changes nothing else: same `orderId`, same
`lastNodeId`, same sequence id, no `cancelOrder` actionState, no empty
goal on `/f2/auto/goal` — the recorder caught **zero** samples on either
vehicle's goal topic across the whole of Gate 1's traffic run, and an
empty goal is how this stack stops a truck.

**The odom is the independent witness, and it is the one that would
catch a restart.** While f2 was held its centre stayed between
x = 3.2075 and x = 3.7081 over 373 samples, at rest from 11:29:03.509;
**after the extension its x never rose above 3.2075 again** — it drove
west monotonically from where it stood to (-5.927,-2.738). wp3 sits at
x = 3.0. The truck did not re-drive it, did not re-drive anything east
of it, and was never sent back over floor it had crossed.

**Ticked.**

## [x] Gate 4 — deadlock: the NAMED REFUSAL, and it is the honest answer

*Contrive a mutual wait. Expect the named refusal rather than a yield —
wait-die is near a no-op through this manager by design, because a
stopped truck holds only the ground under it.*

**It did not need contriving.** Gate 2's run A produced it on its own:
two trucks queued for one spur station, the occupant inside it and the
waiter standing on the junction it has to leave by. That is a swap, and
the fleet said so — 12.94 s after the occupant's leg 2 went out, once
both trucks had actually parked at their base ends:

```
11:34:39,173 fleet ERROR UNRESOLVABLE: swap deadlock f1 <-> f2 - each
             truck stands on the floor the other needs, so the youngest
             yielding frees nothing and wait-die cannot break it. A
             vehicle has to be moved (f1 was the youngest)
```

The operator's screen, `fleet_cli.py status`, at that moment:

```
TASK       STATE     FROM  TO   ASSIGNEE  LAST
g2-b       QUEUED    S4    S3   -         requeued to head: swap deadlock…
g2-a       ASSIGNED_LEG2  S4  S5  f2      leg2 -> S5 as ft-72764c6d on f2

TRAFFIC (on)
  f1  holds  (6.0,-5.5)
  f2  holds  (6.0,-8.0)
  f2  WAITS  (6.0,-5.5)
  g2-a  base 1 released + 5 horizon
  ** BLOCKED: swap deadlock f1 <-> f2 - each truck stands on the floor
     the other needs, so the youngest yielding frees nothing and
     wait-die cannot break it. A vehicle has to be moved **

REFUSED (1, most recent last)
  g2-b   swap deadlock f1 <-> f2 - …
```

**No yield was recorded and nothing claimed a fix.** The younger task was
requeued to the head, named in `traffic.blocked`, and named again in the
operator's refusal list — three places, one sentence, and the sentence
says what a human has to do. `traffic.yields` stayed empty, which is
what Task 4's analysis predicted: by the time both trucks are parked at
their base ends each holds exactly one element, the node under its own
body, so the younger one yielding would free nothing at all.

Measured with it:

```
both at rest, 2.436 m apart   f1 (5.7705,-5.4990)  f2 (6.2055,-7.8961)
motor-false                   f1 0 of 2907   f2 0 of 2908
```

**Nobody was hurt by the deadlock and nobody was moved by it.** Recovery
took two scratch `cancelOrder`s and a `./m6.sh home` — the fleet cannot
get out of this on its own, and the message is the only reason an
operator would know that within the second rather than after ten minutes
of watching two stopped trucks.

**Ticked** — as a refusal, which is what the gate asks for. What it costs
is on the carry list.

## [x] Gate 5 — loss with holds

*Kill a vehicle mid-route: its holds free, its task requeues and
completes on the other, and nothing is routed through the parked hulk —
the occupied node stays held.*

### Run 1, 11:53 — recorded because it found something

Staged the obvious way and it failed for a rig reason worth keeping. The
kill worked exactly as designed:

```
11:55:42,871 f1 is gone (CONNECTIONBROKEN) mid-ASSIGNED_LEG1
11:55:42,871 f1 is holding (-7.4,-5.5) where it stopped - nothing is
             routed through a parked hulk until it reports a fresh idle
             state
11:55:42,872 assigned g5 to f2 (nearest idle to S10: f2 17.46 m <- chosen)
```

**But the respawn took 19 s** — my own hand, not the fleet — and with no
agent alive nothing could publish an empty goal, so nav drove the truck
2.93 m to the end of its route and parked it on S10: **the node the
manager had already granted its replacement**. When f1 finally reported
in, `hold()` asked for the ground under its own body and was refused,
because f2 owned it. The lesson is not the manager's: **a parked hulk is
only parked where the ledger last saw it, and a hulk that keeps rolling
invalidates its own reservation.** It goes on the carry list.

### Run 2, 12:01:42 — PASS

Same shape, staged so the replacement approaches the pickup from the
far side of the hulk: f1 parked at S2 in the west, `submit S1 S2` taken
by f2 from the east (6.00 m against f1's 7.31 m), and f2 killed as it
crossed x = 1.2 westbound. The kill and the respawn were issued from one
script, 5 ms apart, with ROS already sourced.

```
trigger 12:01:54.282   x=0.5676 y=-5.5014 v=0.2500
12:01:54.284  kill -9 85141          /proc/85141 is gone
12:01:54.289  respawn issued
12:01:54.312  f2 is gone (CONNECTIONBROKEN) mid-ASSIGNED_LEG1     +28 ms
12:01:54.312  f2 is holding (0.0,-5.5) where it stopped - nothing is
              routed through a parked hulk until it reports a fresh
              idle state
12:01:54.313  assigned g5r2 to f1 (nearest idle to S1: f1 7.31 m)   +29 ms
12:01:55.317  f2 returned holding ft-40e89ddc - cancelOrder sent
12:01:55.518  f2 let go of ft-40e89ddc - the cancel landed
12:01:55.907  x=0.2455 y=-5.5016 v=0.0000        AT REST, +1.623 s
12:01:57.224  f2 stood up again - (0.0,-5.5) is the vehicle's own node
              once more
12:01:57.224  f2 re-earned eligibility                             +2.94 s
```

**Driverless path 0.322 m in 1.623 s**, against M6.3 Fleet Gate 4's
1.359 m / 3.838 s — the difference is a 5 ms respawn rather than a 2.2 s
one, and the closed cancel loop `e3c0ddd` added is what stopped it in
both.

**The replacement finished the transport, and it never touched the
hulk's floor:**

```
12:02:30.816  ARRIVED f1 at S1  pose (-3.2304,-5.5885)  error 0.2468 m
12:03:00.921  f1 completed g5r2 at S2  pose (-9.0366,-6.8053)
              error 0.7905 m against that station's arrive_m of 0.80
```

f1's route from S2 to S1 runs `(-9.8,-5.5) (-7.4,-5.5) (-6.0,-5.5)
(-3.0,-5.5)` and does not contain `(0.0,-5.5)`; the hulk's node stayed
held the whole time.

**Then it was probed directly**, because "nothing is routed through it"
deserves a truck that actually wants the floor. `submit S3 S4` went to
f1, whose leg 2 must cross `(0.0,-5.5)`:

```
12:05:22  TRAFFIC (on)
  f1  holds  (-7.4,-5.5) … (-6.0,-5.5)-(-3.0,-5.5) (-3.0,-5.5)
  f2  holds  (0.0,-5.5)
  f1  WAITS  (0.0,-5.5)
  g5p  base 4 released + 4 horizon
```

**f1 was given four of eight nodes and stopped**, with the node under the
other truck's body as the first thing it was not allowed. f2 was then
given work of its own; it moved off, f1's base grew to
`orderUpdateId 1` at 12:06:13.392, and f1 completed at S4.

**0 motor-false across the whole of run 2 and the probe** — 0 of 7160
samples on each truck.

**Ticked.**

## [x] Gate 6 — traffic never touches safety

*Across all gates, no reservation event correlates with a Motor drop —
and say HOW you know, not just that you looked (M6.2 Gate 6's rule).*

**How this is known, in three steps.**

**1. Where a Motor drop can come from at all.** `virtual_fplc` has five
instances — `estop`, `pf`, `pf_right`, `pf_left`, `speed` — and Motor is
the AND of them all being unlatched. Every one is driven by a hardware
input the fleet has no wire to: the E-Stop bool, three OSSD bools from
the scanners, and the two encoder channels against the live `V_Limit`.
**The fleet manager's only path to a truck is the VDA 5050 order topic,
and no byte of it reaches any of those five.** That is the structure; the
rest is measurement, because structure is a claim and this file does not
take claims.

**2. Every drop in the session, named at the sample it happened.** Eight
onsets. For each, what the safety streams said at that instant:

```
f1 10:56:32.675  estop_healthy=False  wheels 0.0000   back+left+right
                 PROTECTIVE at spawn      -> the startup acknowledge
f2 10:56:31.448  estop_healthy=False  wheels 0.0000   -> ditto
f1 11:27:23.264  estop_healthy=True   wheels 0.0000   left 1.939 WARNING
                 right 1.944 WARNING      -> the restarted stack's
                                             acknowledge, truck at rest
f2 11:27:25.381  estop_healthy=True   wheels 0.0000   all PROTECTIVE
                                             -> ditto
f2 10:59:40.041  estop_healthy=True   wheels 0.6809   right 2.294 WARNING
                 -> SAFE-SPEED, warm-up, traffic OFF
f2 11:04:52.142  estop_healthy=True   wheels 0.6893   right 2.295 WARNING
                 -> SAFE-SPEED, Gate 1's CONTROL run, traffic OFF
f1 11:53:26.561  estop_healthy=True   wheels 0.2988   back 1.697 WARNING
                 right 2.443 WARNING  -> SAFE-SPEED leaving the S2 spur:
                                         the wall behind it, not a truck
f2 11:56:31.367  estop_healthy=True   wheels 0.6994   right 2.384 WARNING
                 -> SAFE-SPEED approaching f1's ROLLED hulk on S10,
                    Gate 5 run 1 (the run that is written up as failed)
```

Four are the startup acknowledge, with the wheels at rest and no order
anywhere near. Four are the safe-speed instance, and each one carries a
WARNING-level field reading and a wheel speed on the same sample. **Not
one of them is a reservation. Two of the four happened with the ledger
switched OFF; one is a static wall; the fourth is a truck that rolled
onto floor after the fleet had granted it, which is Gate 5 run 1's own
finding.**

**3. The correlation test, run over the whole capture.** For each of the
eight onsets, every order and every base extension published on
`uagv/v2/amragent/+/order` within ±2 s:

```
8 motor-false onsets examined
0 order publishes inside any of the eight +/- 2 s windows
```

Zero. The manager's retained status document does land inside those
windows — it is republished on change and at least every 2 s, so it lands
inside any window one cares to draw, and it is not a message a truck ever
reads. **The messages a truck DOES read were not on the wire within two
seconds of any Motor drop in this session.**

**And the reverse direction, which is the one that matters for a traffic
milestone:** across every window in which the ledger was live —

```
Gate 1 traffic run 1   f1 0 of 6460    f2 0 of 6460
Gate 1 traffic run 2   f1 0 of 2440    f2 0 of 2440
Gate 2 run A / Gate 4  f1 0 of 3100    f2 0 of 3100
Gate 2 run B           f1 0 of 6260    f2 0 of 6260
Gate 2 run C           f1 0 of 5300    f2 0 of 5300
Gate 2 run D           f1 0 of 1540    f2 0 of 1540
Gate 5 run 2 + probe   f1 0 of 7160    f2 0 of 7160
                       ------------    ------------
                       0 of 32,260     0 of 32,260
```

**Thirty-two thousand samples per truck with the floor being reserved,
granted, released, extended and once refused by name, and not one Motor
drop.** The scanners and the F-model remained the only stoppers; the two
times they did stop a truck with traffic on are Gate 5 run 1's, named
above, and neither has a reservation within two seconds of it.

**Ticked.**

## The defect this session found — `11bb499`

**`m6: the end of a base is a wait, not an arrival`**, path-scoped over
`m6/ipc/vda_agent.py` and `m6/tests/test_vda_agent_mqtt.py`.

A horizon-held truck drives its base and stops. nav — which was handed
the released nodes and nothing else — reports `ARRIVED`, and the agent
read that as the end of the ORDER: it cleared `executing`, and
`vda_orders.accept_order` then refused every extension by name.

```
[WARN] [vda_agent]: order rejected: no order is executing - nothing to
                    extend            x 1873, over 3 m 37 s
```

One clause was missing. `arrived_now` now also requires
`not self.horizon`:

```python
arrived_now = (state == "ARRIVED" and self.nav_state != "ARRIVED"
               and self.executing and not self.horizon
               and goal == self.order["orderId"])
```

Everything else was already right and is why one clause was enough: the
state keeps its horizon and its `newBaseRequest`, nav sits in `ARRIVED`
with the goal still set so `refused_now` cannot fire either, and
`_extend` re-sends the route from the pose.

**Why the tests did not have it.** M6.4's own extension test
(`test_an_extension_drives_only_what_is_left`) drives the truck to the
end of its base with ODOM alone and never publishes nav's `ARRIVED`, so
the branch was never entered. The regression that replaces that gap,
`test_navs_arrival_at_the_end_of_a_base_does_not_end_the_order`,
publishes it and then asserts both halves — that `executing` survives,
and that the extension the fleet has been waiting to send actually
lands. It fails on the old clause and passes on the new one; both were
run.

## Five things this session found and did not fix

1. **A spur station cannot be handed between two vehicles.** Gate 2 run
   A, measured: the occupant releases the junction the instant it
   arrives, the queued vehicle takes it inside one 100 ms pass, and
   three seconds later the occupant's leg 2 asks for it back and gets a
   swap deadlock. It is structural, not a race that a wider margin
   fixes — the waiting vehicle's route always contains the junction. The
   shape of the fix is to keep a dwelling vehicle's ENTRY node reserved
   through the dwell, or to build leg 2 at arrival rather than at dwell
   expiry; either makes the occupant's exit its own floor. **M6.5.**
2. **A parked hulk is only parked where the ledger last saw it.** Gate 5
   run 1: with no agent alive nothing can publish an empty goal, so nav
   drove a dead truck 2.93 m onto a node the fleet had already granted
   to its replacement, and the hulk's own re-hold was then refused. The
   ledger has no way to follow a vehicle that is not reporting. Bounded
   today by how fast an agent comes back; unbounded if it does not.
3. **The minimum-turning-radius orbit still eats arrivals at `arrive_m`
   0.25 stations reached down a short straight run.** Measured twice
   here (S5 at 0.660–0.721 m, S1 at 0.318–0.805 m) and twice in M6.3.
   It is `stations.py`'s documented geometry meeting a follower that
   cannot converge inside its own turning circle, it predates M6.4, and
   it is what blocked Gate 2's handover on both aisle stations.
4. **`arrived_now` still has one nav-state period of race left in it.**
   `11bb499` reads `self.horizon`, and an extension that empties the
   horizon can be processed in the same period the truck reaches the end
   of the base it is still driving — in which case the ARRIVED that
   belongs to the OLD base would complete the order early. Not reachable
   in this session's captures (every extension arrived while the truck
   was already at rest), and the close is one line: anchor the test on
   `progress.reached == len(progress.nodes)` — has the truck passed the
   last released node — rather than on the horizon being empty. **M6.5.**
5. **The mirror of it: an update that only SHRINKS a horizon**, arriving
   after the truck has stopped at its base end, would leave `executing`
   true with nothing in front to drive and no arrival ever reported.
   Unreachable through this fleet — `order_builder` only ever grows a
   released prefix, and `_base_kept` refuses anything that moves it — so
   it is a property of the agent read alone, not of the system. **Pin it
   with a test in M6.5** rather than leaving it to be discovered.

## Teardown

Writers first:

```
> {"quit":true} -> 127.0.0.1:5910         > {"quit":true} -> 127.0.0.1:5920
shutting down: writing the trip values    shutting down: writing the trip values
writer for f1 is down                     writer for f2 is down
```

`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` afterwards
returns three VS Code language servers and nothing else. Both recorders
were stopped next, the ROS one printing its session counts (above).

```
$ ./m6.sh stop
  … killed 85081 … killed 85117 … killed 99519 … killed 99880
  … swept 84290 (sto_contactor.py)
down.
```

The pidfile held **27** lines against the twenty-one started: the extra
six are this session's manager restarts and Gate 5's two agent respawns,
every one of them appended by the same `setsid … echo $$ >> "$1"` shape
`m6.sh` uses, which is why `stop` swept them all.

```
$ ss -uln | grep -E ':(5110|5111|5120|5121)'  ->  all four free
$ ss -ltn | grep ':1883'                      ->  free
$ pgrep -af 'gz sim|plc_link|vda_agent|fleet_manager|mosquitto-vendored|
             rec3|mqtt_rec3'                  ->  none
$ test -f .m6_pids                            ->  removed
```

```
$ python3 -m pytest m6/tests/ -q
439 passed in 125.15s     (437 + the leg-2 `stuck` regression
                           + the base-end regression 11bb499 brought)
$ python3 -m pytest m5_ver2/step5/tests/ -q
220 passed in 2.90s
```

---

# M6.5 — sizing the machine for four

## [x] Gate 1 — RTF at four: STOP on llvmpipe, GO on the GPU

*Read both halves. The llvmpipe half below produced the STOP ruling and
every number in it stands as measured; the GPU half at the end of the
section re-runs the same matrix on d3d12, clears the gate at four, and
corrects the STATISTIC the STOP was computed with. Neither half is a
correction of the other's data.*

**Date:** 2026-08-22. **Verdict: STOP.** Four forklifts with their
sixteen lidars actually running hold mean RTF **0.190 / 0.230 / 0.230**
over three 60 s runs, against a gate of **0.30**. The same four trucks
with nothing subscribed to those lidars run at **0.998**, and that
second number is the one M6.1's gate 1 measured — it is a measurement of
physics with the sensors switched off. Two vehicles are still fine
(0.957-0.970 with everything rendering). **The cliff is between the
second truck and the third**, and it is a software renderer that stops
scaling, not the twenty threads and not the physics.

### The machine

```
kernel      5.15.167.4-microsoft-standard-WSL2
cpu         13th Gen Intel(R) Core(TM) i9-13900H, 20 threads
memory      15 GiB
gz sim      8.11.0
renderer    llvmpipe (LLVM 20.1.2, 256 bits), Mesa 25.2.8, Accelerated: no
```

Unchanged from M6.1's gate 1, which named the same rig; every lidar is
rasterised on the CPU.

### What was run

`tools/rtf_spike.sh`, now taking the vehicle ids as arguments. Server
only: `gz sim -s -r --headless-rendering` on `gazebo/warehouse_ver2.sdf`
under `GZ_PARTITION=m6-rtf-spike`, no ROS stack, no bridge, no writers,
no broker, no GUI. It spawns the trucks one at a time and samples
`real_time_factor` off `/world/warehouse/stats` for 30 s after the first
and 60 s after each of the others, so one process yields the whole
1 / 2 / 3 / 4 series under one load order and one page cache.

```
wsl -e bash -lc "cd /mnt/c/Users/ozkan/projects/amr-agent && \
  RTF_GATE=0.30 RTF_LOGDIR=/tmp/m6_rtf_lidar1 \
  RTF_POSE_f3='-8.0 5.65 0.05 0' RTF_POSE_f4='8.0 5.65 0.05 3.14159' \
  bash m6/tools/rtf_spike.sh f1 f2 f3 f4"
```

`RTF_POSE_f3/f4` exist because **Task 4 has not grown the VEHICLES table
yet**: `status_contract.VEHICLES` owns f1 and f2 only, so the two new
trucks are named to the spike explicitly rather than guessed at inside
it. Their models were derived TEMPORARILY, by a scratch script that is
not committed, applying the rule `tools/instantiate_vehicle.py` applies
— a counted prefix rewrite of f1's derived pair, 37 occurrences in
`model.sdf` and 62 in `config.yaml`, asserted equal both ways. Task 4
teaches the tool f3/f4 for real.

### AN UNSUBSCRIBED gpu_lidar IS NOT RENDERED

This is the finding that decides the gate, and it also re-reads M6.1's.

gz-sim's `Sensors` system renders a camera or lidar only while a
connection exists on its topic. A server-only spike that spawns four
trucks and subscribes to nothing is therefore measuring **physics and
nothing else** — the sixteen `gpu_lidar` sensors named in M6.1's gate 1
("eight in the two-vehicle case, all rendered in software") were never
rendered while that gate was being measured.

The A/B, in ONE server process, four trucks spawned once:

| Window (60 s, 60 s, 30 s) | Samples | Mean RTF | Min | Max |
|---|---|---|---|---|
| four trucks, nothing subscribed | 592 | **0.996** | 0.522 | 1.257 |
| the same four, all 16 lidars subscribed | 402 | **0.237** | 0.015 | 1.281 |
| the same four again, subscribers killed | 296 | **0.995** | 0.519 | 1.277 |

Same world, same models, same minute, nothing moved and nothing was
reloaded: the only variable is whether anyone is listening, and it costs
a factor of four. The recovery in the third row is what makes it a
switch and not a drift.

`rtf_spike.sh` now holds a subscriber on every `gpu_lidar` of every
truck it spawns (`RTF_CONSUME_LIDARS=1`, the default) and counts the
scans it is delivered, because the stack this sizing is for runs a
bridge on every one of those topics. `RTF_CONSUME_LIDARS=0` reproduces
the old physics-only shape and prints `scans 0`, which is the same
finding stated as a number.

### The two tables

**Lidars subscribed — the gate.** Three runs, three 4-vehicle phases:

| Run | 1 vehicle, 30 s | 2 vehicles, 60 s | 3 vehicles, 60 s | 4 vehicles, 60 s |
|---|---|---|---|---|
| 13:28:57 | 0.999 (296) | 0.962 (591) | 0.155 (482) | **0.190** (392) |
| 13:33:36 | 1.000 (296) | 0.970 (590) | 0.140 (479) | **0.230** (399) |
| 13:38:11 | 0.999 (296) | 0.957 (589) | 0.179 (482) | **0.230** (402) |

**Nothing subscribed — the same script, the same machine, the same
hour.** Runs 1-3 were taken before `RTF_CONSUME_LIDARS` existed (same
sampler, same spawns, same poses); the last row is the finished tool
told explicitly not to subscribe:

| Run | 1 vehicle | 2 vehicles | 3 vehicles | 4 vehicles |
|---|---|---|---|---|
| 13:02:31 | 0.998 (296) | 0.998 (592) | 0.998 (593) | **1.000** (592) |
| 13:07:02 | 1.000 (296) | 0.999 (593) | 0.998 (593) | **0.997** (592) |
| 13:11:14 | 0.999 (296) | 0.999 (593) | 0.999 (593) | **0.997** (592) |
| 13:44:23 `RTF_CONSUME_LIDARS=0` | 0.999 (296) | 0.999 (592) | 1.001 (593) | **0.998** (592) |

The two-vehicle column of the second table (0.998-0.999) is directly
comparable with M6.1's gate 1 (worst 0.934, best 0.995) and reproduces
it. **The physics of four trucks is free on this machine.** Everything
that follows is the renderer.

### Run 1 of the gated three, verbatim

SDF `gz_frame_id` warnings and the `libEGL ... kms_swrast` lines are
elided (five and six per spawn, identical to M6.1's, and quoted there);
nothing else is cut.

```
=== m6 RTF spike ===
date        2026-08-22T13:28:57+02:00
gz sim      8.11.0
partition   m6-rtf-spike
world       /mnt/c/Users/ozkan/projects/amr-agent/m6/gazebo/warehouse_ver2.sdf
vehicles    f1 f2 f3 f4  (4)
lidars      subscribed, so rendered
gate        0.30, on the 4-vehicle phase
logs        /tmp/m6_rtf_lidar1
cpu         13th Gen Intel(R) Core(TM) i9-13900H, 20 threads
kernel      5.15.167.4-microsoft-standard-WSL2
spawning f1 at (-3.00, -5.50, 0.05) yaw 0.0  [table]
  f1 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [-3.000000 -5.500000 -0.000001]
    [0.000000 0.000000 0.000000]
    /f1/gz/safety_scanner_back/measurement     closest 0.122 m
    /f1/gz/safety_scanner_left/measurement     closest 0.111 m
    /f1/gz/safety_scanner_right/measurement    closest 0.111 m
    /f1/gz/scan_nav                            closest 1.287 m
  f1: 4 lidars subscribed (4 total)
sampling /world/warehouse/stats for 30s (1-vehicle)...
1-vehicle    samples   296  mean RTF 0.999  min 0.965  max 1.015  scans   1200 (40.0 Hz)
spawning f2 at (3.00, -5.50, 0.05) yaw 3.14159  [table]
  f2 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [3.000000 -5.500000 -0.000001]
    [0.000000 0.000000 3.141590]
    /f2/gz/safety_scanner_back/measurement     closest 0.122 m
    /f2/gz/safety_scanner_left/measurement     closest 0.111 m
    /f2/gz/safety_scanner_right/measurement    closest 0.111 m
    /f2/gz/scan_nav                            closest 1.287 m
  f2: 4 lidars subscribed (8 total)
sampling /world/warehouse/stats for 60s (2-vehicle)...
2-vehicle    samples   591  mean RTF 0.962  min 0.047  max 1.067  scans   4748 (79.1 Hz)
spawning f3 at (-8.0, 5.65, 0.05) yaw 0  [env RTF_POSE_f3]
  f3 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [-8.000000 5.650000 -0.000001]
    [0.000000 0.000000 0.000000]
    /f3/gz/safety_scanner_back/measurement     closest 0.122 m
    /f3/gz/safety_scanner_left/measurement     closest 0.111 m
    /f3/gz/safety_scanner_right/measurement    closest 0.111 m
    /f3/gz/scan_nav                            closest 1.287 m
  f3: 4 lidars subscribed (12 total)
sampling /world/warehouse/stats for 60s (3-vehicle)...
3-vehicle    samples   482  mean RTF 0.155  min 0.022  max 1.535  scans   5602 (93.4 Hz)
spawning f4 at (8.0, 5.65, 0.05) yaw 3.14159  [env RTF_POSE_f4]
  f4 rests at:
  - Pose [ XYZ (m) ] [ RPY (rad) ]:
    [8.000000 5.650000 -0.000001]
    [0.000000 0.000000 3.141590]
    /f4/gz/safety_scanner_back/measurement     closest 0.122 m
    /f4/gz/safety_scanner_left/measurement     closest 0.111 m
    /f4/gz/safety_scanner_right/measurement    closest 0.111 m
    /f4/gz/scan_nav                            closest 1.287 m
  f4: 4 lidars subscribed (16 total)
sampling /world/warehouse/stats for 60s (4-vehicle)...
4-vehicle    samples   392  mean RTF 0.190  min 0.014  max 1.258  scans   5558 (92.6 Hz)
--- gate: 4-vehicle mean RTF vs 0.30 ---
 1 vehicle(s)  mean RTF 0.999
 2 vehicle(s)  mean RTF 0.962
 3 vehicle(s)  mean RTF 0.155
 4 vehicle(s)  mean RTF 0.190
VERDICT: STOP (0.190 < 0.30 at 4 vehicles)
```

The script exits 2 on STOP; that is the exit status the three gated runs
returned.

### It is a floor, not a dip

M6.1's gate 1 diagnosed its own spread as host scheduling noise, and
proved it by finding a two-vehicle mean ABOVE the one-vehicle mean.
Nothing of the kind happens here. Run 1's windows, cut into sixths:

```
2 vehicles  0.923, 0.997, 0.956, 0.980, 0.956, 0.958   4 % of samples < 0.30
3 vehicles  0.130, 0.131, 0.132, 0.169, 0.174, 0.199  91 % of samples < 0.30
4 vehicles  0.319, 0.160, 0.089, 0.179, 0.228, 0.173  83 % of samples < 0.30
```

Every sixth of the three- and four-vehicle windows is on the floor. The
4-vehicle mean coming out ABOVE the 3-vehicle mean (0.190 vs 0.155,
0.230 vs 0.140, 0.230 vs 0.179 — in all three runs) is the signature of
a saturated pipeline, not of a fourth truck that is cheaper than the
third: past the cliff the renderer is delivering all it can and the
extra demand simply queues.

### Where the time goes

A second instrument, one server, four trucks spawned once, then their
lidars switched on ONE TRUCK AT A TIME by attaching subscribers, with
the server's own CPU read out of `/proc/<pid>/stat` (utime+stime deltas
over each 60 s window) separately from the subscribers':

| Window | Mean RTF | Server CPU | Subscriber CPU | Scans delivered |
|---|---|---|---|---|
| 4 trucks, 0 lidars on | 0.995 | 1.0 cores | 0.0 | 0 |
| 4 trucks, f1's 4 on | 0.995 | 2.0 cores | 0.1 | 43.1 /s |
| 4 trucks, f1+f2's 8 on | 0.981 | 3.0 cores | 0.2 | 84.8 /s |
| 4 trucks, 12 on | **0.274** | 3.0 cores | 0.3 | 99.3 /s |
| 4 trucks, 16 on | **0.195** | 2.8 cores | 0.4 | 100.7 /s |

Three things are measured here and they agree with the gate runs:

- **The marginal cost of a truck is entirely its four lidars.** Physics
  for four is 1.0 core and 0.998 RTF. The first truck's lidars cost a
  core, the second's another, and the third's cost the simulation.
- **The renderer never gets past ~3 of 20 threads.** The server's CPU
  stops rising exactly where the RTF collapses, which is what a
  serialised render path looks like: llvmpipe is rasterising every lidar
  in turn and the other seventeen threads have nothing to do with it.
  Adding hardware threads would not have helped; a GPU would.
- **The delivered scan rate ceilings at ~93-101 scans/s.** Each truck
  asks for 40 (four lidars at 10 Hz), so two trucks ask 80 and get 79,
  three ask 120 and get 93, four ask 160 and get 93. The gap IS the RTF
  drop: sim time is being stretched until the renderer can keep up.

The subscriber column is this instrument's own cost and it is 0.4 cores
at sixteen topics — the load is the server's, not the watcher's.

### Both new trucks are where they were put, and clear

| Vehicle | Pose asked for | Resting pose (XYZ / RPY) | Closest lidar returns |
|---|---|---|---|
| f1 | table: (-3.00, -5.50, 0.05) yaw 0.0 | (-3.000000, -5.500000, -0.000001) / (0, 0, 0.000000) | 0.122 / 0.111 / 0.111 / 1.287 |
| f2 | table: (3.00, -5.50, 0.05) yaw 3.14159 | (3.000000, -5.500000, -0.000001) / (0, 0, 3.141590) | 0.122 / 0.111 / 0.111 / 1.287 |
| f3 | spike: (-8.0, 5.65, 0.05) yaw 0 | (-8.000000, 5.650000, -0.000001) / (0, 0, 0.000000) | 0.122 / 0.111 / 0.111 / 1.287 |
| f4 | spike: (8.0, 5.65, 0.05) yaw 3.14159 | (8.000000, 5.650000, -0.000001) / (0, 0, 3.141590) | 0.122 / 0.111 / 0.111 / 1.287 |

Nothing tipped, nothing sank, no spawn was refused, and **no pose had to
move**. The four closest-return rows are identical to three decimals
because what each scanner sees at rest is the truck's own forks and mast
— which is exactly why that column is not a protective verdict and is
not offered as one (the verdict is `field_evaluation.py`'s, over a field
polygon, with the ROS stack up). What it is good for is the comparison
printed above: f3 and f4, in the main aisle, see the world the same way
f1 and f2 do at the poses M6.1 validated. Task 4 can take these two
poses into the table as they stand.

### Verdict

**STOP: 0.190 / 0.230 / 0.230 < 0.30.** This machine carries TWO
forklifts with their sensors rendering (0.957-0.970) and does not carry
three (0.140-0.179) or four (0.190-0.230). Task 2 is not started, the
world was not lightened and no sensor rate was touched — those are the
owner's calls and they are what this gate exists to ask for.

Three consequences to weigh with them, the first measured and the other
two marked as the inferences they are:

- **Measured.** An acceptance run at 0.21 RTF takes about five times its
  sim-clock duration in wall time. M6.1's note stands and gets worse:
  every loop in this tree is wall-clock timed, so nothing misses a
  deadline — what stretches is simulated seconds per wall second.
- **Inference.** The per-lidar delivered rate at four trucks is
  92.6 / 16 = **5.8 Hz**, a mean gap of 0.17 s against the writer's
  `SENSOR_STALE_S` budget of 0.40 s. The mean holds, but the minimum RTF
  in these windows is 0.014, and a stall that deep is a scan gap far past
  0.40 s. M6.4's rig rule already names the failure mode (starve
  `sensor_link` and the F-model latches ESTOP1). Whether the safety chain
  survives four trucks is a full-stack question this server-only spike
  cannot settle.
- **Inference.** These numbers have NO ROS stack in them. The M6.4-era
  two-vehicle stack (21 pids, writers attached) ran 0.46-0.62 against a
  server-only 0.93-1.00, and the four-vehicle stack is 39 pids. Whatever
  the fleet number becomes, the stack subtracts from it.

The options, none of them taken here: drop the safety scanners'
update rate (halving it halves the demand, and re-opens the timing
argument in FIELD-EVALUATION.md); run some vehicles with no lidar
consumer at all — traffic that moves but cannot see, which the renderer
gives away for free (0.998 at four); keep four trucks but drive fewer at
once; or move the world to a machine with a real GPU, which is the only
option that removes the wall rather than working around it.

### The same measurement on the GPU (d3d12), 2026-08-22

Everything above ran on llvmpipe. WSLg can hand Mesa to the laptop's
discrete GPU through D3D12, and the finding above was that the ceiling is
the SERIAL SOFTWARE RENDER PATH — so the owner asked for the same matrix
on the GPU. Nothing above is deleted: the llvmpipe numbers are what that
configuration does, and the comparison is the point.

#### The driver is actually taken, and gz took it too

```
$ glxinfo -B                                    # the default, for contrast
    Device: llvmpipe (LLVM 20.1.2, 256 bits) (0xffffffff)
    Accelerated: no
OpenGL renderer string: llvmpipe (LLVM 20.1.2, 256 bits)

$ GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA glxinfo -B
    Device: D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU) (0xffffffff)
    Accelerated: yes
    Video memory: 22118MB
    Unified memory: no
OpenGL vendor string: Microsoft Corporation
OpenGL renderer string: D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
```

`glxinfo` proves the env var reaches Mesa; it does not prove the SERVER
took the same path, so gz's own rendering log was read after the first
run (`~/.gz/rendering/ogre2.log`, moved aside beforehand so the lines
below could not be a stale llvmpipe session's):

```
16:03:50: GL_VERSION  = 4.6 (Core Profile) Mesa 25.2.8-0ubuntu0.24.04.2
16:03:50: GL_VENDOR   = Microsoft Corporation
16:03:50: GL_RENDERER = D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
```

#### The command

Identical to the llvmpipe runs, same script, same poses, same windows,
same subscribed lidars — two env vars added and nothing else:

```
wsl -e bash -lc "cd /mnt/c/Users/ozkan/projects/amr-agent && \
  GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
  RTF_GATE=0.30 RTF_LOGDIR=/tmp/m6_gpu1 \
  RTF_POSE_f3='-8.0 5.65 0.05 0' RTF_POSE_f4='8.0 5.65 0.05 3.14159' \
  bash m6/tools/rtf_spike.sh f1 f2 f3 f4"
```

#### THE STATISTIC WAS WRONG, AND IT WAS WRONG IN BOTH DIRECTIONS OF THE COMPARISON

Reading the GPU captures turned up something that has to come before any
of the numbers, because it re-reads the llvmpipe ones too.

`rtf_spike.sh` reports the ARITHMETIC MEAN OF THE INSTANTANEOUS
`real_time_factor` samples — the statistic M6.1's gate 1 defined and
every RTF figure in this file inherits. That mean is a fair estimate
while the simulator runs smoothly and a badly biased one when it runs in
bursts, because the samples are not evenly spaced in wall time: a stall
publishes a cluster of near-zero factors and the catch-up that follows
publishes very few high ones.

The unbiased quantity is in the same messages and needs no new run: every
`gz.msgs.WorldStatistics` carries `sim_time` and `real_time`, so the
honest ratio is **(sim_time last − first) / (real_time last − first)** —
simulated seconds delivered per wall second, integrated over the window,
which is what "real-time factor" is supposed to mean.

| Window (4 trucks, 16 lidars subscribed) | Mean of samples | INTEGRATED Δsim/Δreal |
|---|---|---|
| llvmpipe, run 1 / 2 / 3 | 0.190 / 0.230 / 0.230 | **0.579 / 0.580 / 0.579** |
| llvmpipe, 3 vehicles | 0.155 / 0.140 / 0.179 | **0.778 / 0.781 / 0.775** |
| d3d12, run 1 / 2 / 3 | 0.583 / 0.687 / 0.670 | **0.903 / 0.899 / 0.712** |

**The delivered scan counts are an independent instrument and they
confirm the integrated column, not the mean.** Each lidar is scheduled at
10 Hz of SIM time, so scans delivered ÷ 10 = simulated seconds elapsed:

- llvmpipe, four trucks: 5,558 scans ÷ 16 lidars = 347.4 per lidar →
  **34.7 s** of sim time. The integrated ratio says 34.6 s in 59.8 s
  (0.579). The mean-of-samples would have required 11.4 s.
- d3d12, four trucks: 8,672 ÷ 16 = 542.0 → **54.2 s** of sim time. The
  integrated ratio says 54.0 s in 59.8 s (0.903).

Two instruments, agreeing to a fraction of a second, in both
configurations. The mean-of-samples agrees with neither once the run is
bursty.

The same correction explains the anomaly recorded above under "It is a
floor, not a dip" — the four-vehicle mean coming out ABOVE the
three-vehicle mean in all three llvmpipe runs. Integrated, the series is
monotone in load exactly as physics demands: **1.000 → 0.989 → 0.778 →
0.579**. There was no saturation paradox; there was a biased estimator.

**What this does to the STOP above: it withdraws its arithmetic and
keeps its physics.** Against a gate of 0.30 in simulated seconds per wall
second, llvmpipe at four vehicles delivers **0.579**, which is over the
gate. The gate reading of 0.190 was the statistic, not the machine. What
survives from that section unchanged is everything measured about the
renderer: the unsubscribed-lidar finding, the ~93 scans/s CPU ceiling,
the 3-of-20-threads serial path, and the tail — llvmpipe's instantaneous
factor still bottoms out at 0.014 and its per-lidar delivery still runs
at 5.8 Hz against the GPU's 9.0 Hz.

#### The three GPU runs

Mean-of-samples first because it is what the script prints, integrated
second because it is what the number means:

| Run | 1 vehicle, 30 s | 2 vehicles, 60 s | 3 vehicles, 60 s | 4 vehicles, 60 s |
|---|---|---|---|---|
| 16:03:50 | 1.002 / 1.000 (296) | 0.996 / 0.995 (592) | 0.993 / 0.995 (592) | **0.583 / 0.903** (570) |
| 16:10:41 | 0.999 / 1.000 (295) | 0.998 / 1.000 (593) | 0.984 / 0.995 (592) | **0.687 / 0.899** (573) |
| 16:15:33 | 0.999 / 1.000 (296) | 0.997 / 0.999 (593) | 0.805 / 0.811 (584) | **0.670 / 0.712** (565) |

Run 3 is the noisy one — its third and fourth phases both sag, and its
scan rate sags with them (97.4/s where runs 1 and 2 delivered 119.4/s at
three trucks), which is the signature of something else on the machine
rather than of the fourth truck.

Delivered scans, GPU against CPU, at the same fleet sizes:

| Subscribed lidars | Demand | llvmpipe delivered | d3d12 delivered |
|---|---|---|---|
| 4 (1 truck) | 40 /s | 40.0 /s | 40.0 /s |
| 8 (2 trucks) | 80 /s | 79.1 /s | 79.7-80.1 /s |
| 12 (3 trucks) | 120 /s | **93.4 /s** | 119.4 /s (97.4 in run 3) |
| 16 (4 trucks) | 160 /s | **92.6 /s** | 143.9-144.5 /s |

#### The ladder, re-run on the GPU

Same instrument as above — four trucks spawned once, lidars switched on
one truck at a time, server CPU from `/proc/<pid>/stat` deltas:

| Window | Mean | Integrated | Server CPU | Scans | llvmpipe mean, for contrast |
|---|---|---|---|---|---|
| 4 trucks, 0 lidars on | 0.893 | 0.887 | 1.4 cores | 0 | 0.995 (1.0 cores) |
| 4 trucks, 4 on | 0.952 | 0.953 | 1.7 | 40.7 /s | 0.995 (2.0) |
| 4 trucks, 8 on | 0.941 | 0.946 | 2.1 | 82.3 /s | 0.981 (3.0) |
| 4 trucks, 12 on | 0.786 | 0.791 | 2.7 | 102.5 /s | **0.274** (3.0) |
| 4 trucks, 16 on | 0.686 | 0.866 | 2.5 | 148.7 /s | **0.195** (2.8) |

**The cliff is gone.** On llvmpipe the twelfth lidar took the simulation
from 0.981 to 0.274; on the GPU the same step costs 0.15 and the
sixteenth costs a little more. The delivered scan rate keeps climbing to
148.7/s instead of stopping dead at ~93-100/s, which is the same
statement from the other side: the CPU renderer had a throughput ceiling
below the fleet's demand and the GPU's ceiling is above it. Server CPU
goes DOWN where the load goes up (2.5-2.7 cores against llvmpipe's 3.0)
because the rasterising left the CPU.

The llvmpipe ladder's raw captures were overwritten by this run, so its
integrated column cannot be recomputed; its delivered-scan rate implies
0.83 at twelve lidars and 0.63 at sixteen, consistent with the 0.775 and
0.579 measured directly in the spike runs.

#### Verdict on the GPU

**GO. Four vehicles, sixteen lidars subscribed and rendering, three runs:
0.583 / 0.687 / 0.670 by the printed mean and 0.903 / 0.899 / 0.712
integrated — every one of the six figures is above the 0.30 gate**, the
worst by a factor of 1.9 and the typical by a factor of 3.
Two vehicles run at 0.995-1.000 and three at 0.811-0.995.

This retires the two-driver compromise as a *simulation* constraint. The
decision is the owner's; what is measured is that the machine renders
four trucks' safety scanners at 90 % of real time when the GPU does the
rasterising, and at 58 % when the CPU does.

Three things this does NOT retire:

- **The stack is still not in the number.** No ROS, no bridge, no
  writers, no broker: 39 pids at four vehicles. The M6.4-era two-vehicle
  stack cost about a third of real time on top of the server-only figure.
- **The tail.** The instantaneous minimum in the GPU's four-vehicle
  windows is 0.023-0.043, so deep stalls still happen; they are shorter
  and rarer than llvmpipe's but `SENSOR_STALE_S` is 0.40 s and only a
  full-stack run can say whether the safety chain rides them out.
- **The earlier RTF figures in this file stay valid as records and must
  be labelled by their renderer where they are quoted.** M6.1's 0.934,
  the 0.734-0.755 full-stack pair, M6.3's and M6.4's numbers and the
  whole llvmpipe half of this gate were all measured with **llvmpipe**
  and, additionally, with the mean-of-samples statistic. They describe
  what that configuration did. The *ceiling* they imply is a
  software-render ceiling, not this machine's.

#### Making it permanent, and why it is not wired in yet

The two variables have to be in the environment of whatever starts the gz
**server** — `m6.sh start` spawns the world, so the setting has to be in
place before that, not inside a subshell that only runs the CLI. The
minimal operator change, one file, no repo edit:

```
# ~/.bashrc of the WSL user (Ubuntu's ~/.profile sources it, and every
# `wsl -e bash -lc` is a login shell, so m6.sh inherits both)
export GALLIUM_DRIVER=d3d12
export MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA
```

Verify with `GALLIUM_DRIVER= glxinfo -B | grep Device` in a fresh shell
(should read `D3D12 (NVIDIA ...)`) and, after a run, with `grep
GL_RENDERER ~/.gz/rendering/ogre2.log`, which is the only line that
proves the SERVER took it. The Windows-side writer needs nothing: it
renders nothing.

**Nothing was wired into `m6.sh`.** Two exports at the top of that script
would make every m6 run depend on a GPU being present, which is a
portability decision and an owner's call — and this measurement is not
the place to take it.

#### One defect, recorded because it is real

Under d3d12 the spike's EXIT STATUS is not trustworthy: all three
four-vehicle runs and a one-vehicle probe printed their verdict and then
exited **139** (SIGSEGV) instead of 0. It is a teardown crash after the
measurement, and it needs a render context to have drawn: a server
started under d3d12 and killed WITHOUT ever rendering exits 0, one that
has been rendering lidars does not. No window and no sample is affected —
every phase printed, and the per-topic scan counts are equal within each
vehicle to the last scan, so no subscriber died early. Until the tool
handles it, **read the VERDICT line, not `$?`, on this driver**; the
llvmpipe runs' exit statuses (0 for GO, 2 for STOP) were correct.

---

# M6.5 — the five live gates and the acceptance run

**Date: 2026-08-22, 18:56–20:05. Measured by the scripted driver + CLI —
no panel, no human.** One WSL session, one stack, thirty-nine pids, one
broker, four scripted writers. Every one of the twenty-three transports
below was submitted with `fleet/fleet_cli.py` and turned into orders by
`fleet/fleet_manager.py`; `tools/send_order.py` was not used once.

**Two of the five gates passed. Three did not, and they are written up at
the same length as the two that did**, because what stopped them is the
same three things every time and none of them is the fleet layer: a
spawn pose inside its own warning field, a minimum turning radius wider
than the floor it is asked to turn on, and a ledger that deconflicts
processes and has never claimed to see a body.

| Gate | | |
|---|---|---|
| 2 | station handover at a spur | **[x]** ticked on the third staging |
| 3 | four-vehicle traffic | **[ ]** 0 of 4 completed — two deadlocks, one named UNRESOLVABLE by the fleet itself |
| 4 | the acceptance run | **[ ]** 1 of 8 in 10.4 minutes |
| 5 | degradation under loss | **[ ]** three clauses of four |
| 6 | safety untouched at four | **[x]** nine drops, every one a scanner, zero correlation |

## The GPU condition, verified before anything moved

The two variables are **not** in this machine's `~/.bashrc` — `grep`
finds nothing in `~/.bashrc` or `~/.profile`, and a login shell prints
`GALLIUM_DRIVER=[]`. They were exported by hand in every shell that
touched the stack, and the renderer was read back twice: once from the
shell before `start`, and once from the server's own log after it.

```
$ GALLIUM_DRIVER= glxinfo -B | grep -i Device
    Device: llvmpipe (LLVM 20.1.2, 256 bits) (0xffffffff)
$ GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA \
      glxinfo -B | grep -i Device
    Device: D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU) (0xffffffff)

$ grep GL_RENDERER ~/.gz/rendering/ogre2.log | tail -1
18:56:34: GL_RENDERER = D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)
```

The second line is the one that matters: it is the **server's** answer,
written by the process that renders the sixteen lidars, eleven seconds
after `start`. Every number in this section is conditional on it, and a
run started from a shell without those two exports would measure a
different machine and not say so.

## Setup, verbatim

```
$ ./m6.sh deploy
instantiated .../m6/vehicles/f1 .. f2 .. f3 .. f4
deployed 31 files to .../m6/deploy
$ head -3 deploy/MANIFEST
# m6 deploy - generated, do not edit
# source-git: ba903df
# date: 2026-08-22T18:56:23+02:00
$ git rev-parse --short HEAD
ba903df
```

The deploy tree was regenerated before a truck moved and its MANIFEST
matches HEAD — M6.4 lost a whole gate run to a tree that did not, and
that is why this check is the first line of the section.

```
$ ./m6.sh start --headless
  broker 134100   world 134106
  plc_link_f1 134543 … hmi_f1 134813        (f1's nine)
  plc_link_f2 134839 … hmi_f2 135117        (f2's nine)
  plc_link_f3 135185 … hmi_f3 135444        (f3's nine)
  plc_link_f4 135495 … hmi_f4 135802        (f4's nine)
  fleet 135854
```

**Thirty-nine pid lines, thirty-nine in `.m6_pids`, thirty-nine alive a
second later**, no `exited during startup`, no `THE STACK IS
INCOMPLETE.` — broker + world + fleet + 9x4, which is the arithmetic
`m6.sh` now prints in its own header. All four agents connected:
`logs/vda_agent_f<n>.log` each says `broker connected - ONLINE
published`, and the broker log carries `vda-f1` … `vda-f4` plus
`fleet-manager`.

## The two instruments

**ROS side: ONE recorder process** — M6.1's `gate_rec` lineage,
M6.3/M6.4's `rec3.py` unchanged, widened from twelve subscriptions to
**twenty-four** and from two mode publishers to four, all created at
18:57:11 — **before the first writer existed** and long before the first
RESET, so no ROS node was started while a truck could move:

```
python3 rec3.py 14400 /tmp/m65/cap 5950 \
  f1_status=/f1/plc/status=String   … f4_status=…      (4)
  f1_fields=/f1/safety/fields=String … f4_fields=…     (4)
  f1_nav=/f1/auto/state=String      … f4_nav=…         (4)
  f1_goal=/f1/auto/goal=String      … f4_goal=…        (4)
  f1_route=/f1/auto/route=String    … f4_route=…       (4)
  f1_odom=/f1/gz/odom=Odometry      … f4_odom=…        (4)
  pub=mode1=/f1/hmi/mode=transient_local … pub=mode4=… (4)
rec3 up: 24 subs, 4 pubs
```

Its whole session, printed on `{"quit": true}`:

```
f1_status 80891  f2_status 80856  f3_status 80886  f4_status 80858
f1_fields 40438  f2_fields 40416  f3_fields 40438  f4_fields 40421
f1_nav    40434  f2_nav    40441  f3_nav    40430  f4_nav    40411
f1_odom   46840  f2_odom   46840  f3_odom   46840  f4_odom   46840
f1_route     11  f2_route      9  f3_route     10  f4_route     12
f1_goal       4  f2_goal       8  f3_goal       6  f4_goal      10
```

**There is no goal publisher in that command line.** The twenty-eight
samples on `/fN/auto/goal` are the agents' own empty goals answering the
`cancelOrder`s this session sent by hand to clear staged runs. No HMI
goal was published by anything, at any point.

**MQTT side: one paho subscriber** on `uagv/v2/amragent/+/#` **and
`fleet/#`**, one JSONL line per message with the retain flag kept, up at
18:57:12.384. It logged exactly one `connected - subscribed` and **no
disconnect for the whole session** — one connection, 10,188 lines,
15.2 MB. It is not a ROS node, so the rig rule does not bite it, and it
is the only reader that can say what the fleet saw.

Then, on Windows, four scripted writers started detached, one per
vehicle, on the ctl ports the table's port families imply:

```
> python m6\tools\scripted_writer.py --vehicle f1 --virtual --ctl-port 5910
> … f2 … 5920      > … f3 … 5930      > … f4 … 5940
streaming PLC state to 172.19.180.72:5110  (f2 …5120, f3 …5130, f4 …5140)
VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop
listening for the back scanner on 0.0.0.0:5111  (…5121, …5131, …5141)
control channel on 127.0.0.1:5910                (…5920, …5930, …5940)
```

`PF/WF` live on every truck's first cycle, which is a working
WSL→Windows link on all four odd ports and not a default. **PowerShell
strips the double quotes out of a native command's argument** (M6.2
recorded it twice, M6.3 again, M6.4 wrapped around it), so every writer
command in this session went through a wrapper that builds the JSON
itself from `key=value` words. The command set is still the panel's four
buttons, the lamp and the window close, and nothing more.

The mode went out through the recorder's own transient-local
publishers, **before** the RESET:

```
18:59:35.428  PUB /f1/hmi/mode <- 'auto' (3 matched subscribers)
18:59:35.828  PUB /f2/hmi/mode <- 'auto' (3 matched subscribers)
18:59:36.278  PUB /f3/hmi/mode <- 'auto' (3 matched subscribers)
18:59:36.728  PUB /f4/hmi/mode <- 'auto' (3 matched subscribers)
18:59:44.098..44.417  {"ack": true} -> 5910 / 5920 / 5930 / 5940
18:59:48  all four reply  {"motor": true, …}
```

The fleet manager is the one process this session restarted, five times,
to clear the task book between staged runs. Each restart used `m6.sh`'s
own spawn shape (`setsid`, pid appended to `.m6_pids`), which is why
`stop` swept every one of them.

## What the bring-up measured before any gate ran

`fleet_cli.py status` rendered four rows, all ONLINE and AUTOMATIC, at
their table poses. But the four writers did not print the same line:

```
f1  E-Stop=True  Motor=True  | PF b/r/l=T/T/T  WF b/r/l=T/T/T | V_Limit=1500
f2  E-Stop=True  Motor=True  | PF b/r/l=T/T/T  WF b/r/l=T/T/T | V_Limit=1500
f3  E-Stop=True  Motor=True  | PF b/r/l=T/T/T  WF b/r/l=T/F/F | V_Limit=300
f4  E-Stop=True  Motor=True  | PF b/r/l=T/T/T  WF b/r/l=T/F/F | V_Limit=300
```

**f3 and f4 ship parked inside their own warning fields**, and the field
evaluator says by how much:

```
f3  left {d 1.82 WARNING}   right {d 1.82 WARNING}   back {d 3.717 SAFE}
f4  left {d 2.32 WARNING}   right {d 2.32 WARNING}   back {d 4.500 SAFE}
```

Measured, not argued. The left and right scanners are mounted at the
**fork-end corners** — `model.sdf`, `<pose>-0.68 -0.46 0.15 0 0
-2.3561945</pose>`, with the note that the yaw points the sensor out
along the corner diagonal. f3 stands at `(-12.50, 5.65)` facing the west
wall at x = -15.0, so its fork corner is `15.0 - 12.5 - 0.68 = 1.82 m`
from it. f4 stands at `(12.00, -5.50)` facing the east wall at x = 15.0:
`15.0 - 12.0 - 0.68 = 2.32 m`. Both inside the 2.5 m warning threshold,
to the centimetre, from the table.

The consequence is not cosmetic. `cmd_gate` clamps every command to
`min(speed_max, v_limit / 1000)`, so with `V_Limit` at 300 those two
trucks **crawl at 0.30 m/s** until their own warning clears. Measured on
the wire during the warm-up: `enc=-250/-250` and `enc=-300/-300` on f3
and f4 while f1 and f2 run 0.69–0.70 m/s.

**Why Task 4's rest check did not catch it, and what to check instead.**
That check read the RAW closest lidar return on each scanner — 0.122 /
0.111 / 0.111 / 1.287 m — and those four numbers are identical on all
four trucks, because they are the truck's own forks and mast. What it
did not read is `field_eval`'s answer, which is the only one the F-model
sees. **A pose can pass a range check and fail a field check**, and the
field check is a one-line read of `/fN/safety/fields` that costs
nothing.

## The warm-up — the first time the two new trucks ever drove

`submit S6 S3` (f3, nearest at 5.35 m) and `submit S7 S4` (f4, 16.00 m),
19:02:44.

**f3 completed its first transport**: arrived S6, dwelled, arrived S3,
DONE. Nothing to report and that is the point — the west truck works.

**f4 did not.** At 19:05:43.508 its Motor dropped, and the sample says
exactly what happened:

```
odom   19:05:43.545  x=12.4665  y=5.3688  v=0.1772
fields 19:05:43.543  back  {pf true,  d 1.62  WARNING}
                     left  {pf FALSE, d 0.993 PROTECTIVE}
                     right {pf true,  d 1.914 WARNING}
status 19:05:43.508  {"estop_healthy": true, "motor": false, "v_limit": 300}
nav    19:05:43.535  SAFETY-STOP, route … (11.6,5.65) (12.0,5.65) (12.0,-5.5) …
```

It was turning south at the `(12.0, 5.65)` junction — the east
cross-aisle corner — and the turn carried it to x = 12.47. The
`Conveyor` obstacle in `stations.py` is `(14.00, 14.90, 3.50, 6.50)`, so
the node itself is **2.00 m** from the conveyor face and clears the 1.0 m
protective threshold with a metre to spare. The truck's swing does not:
its fork-corner scanner reached **0.993 m**, seven millimetres inside
the threshold. The track through the corner, one sample in six:

```
19:05:36.263  x=11.6323 y=5.8074 v=0.2102     19:05:40.662 x=12.1854 y=5.6642
19:05:37.680  x=11.8238 y=5.8078 v=0.2051     19:05:41.618 x=12.2961 y=5.5809
19:05:39.185  x=12.0058 y=5.7581 v=0.2173     19:05:42.580 x=12.3885 y=5.4822
19:05:39.669  x=12.0651 y=5.7311 v=0.2175     19:05:43.545 x=12.4665 y=5.3688
```

**How structural is that corner?** Measured against the graph, not
guessed: of the 90 station-to-station routes, **six** touch
`(12.0, 5.65)`, and all six involve S4 — three in the fatal east→south
direction (`S5→S4`, `S7→S4`, `S9→S4`) and three in the harmless
south→west one. Its only neighbours are `(11.6, 5.65)` and
`(12.0, -5.5)`, so a truck arriving from the west has **0.40 m** of
run-up before a 90-degree right turn beside a conveyor. f4's own leg 1
took the same junction in the other direction, from eleven metres of
straight corridor, and made it without a flicker.

Recovery was `cancelOrder`, `./m6.sh home`, RESET on all four, and a
manager restart to clear the task book. Nothing below shares state with
this run.

## [x] Gate 2 — station handover at a spur, fixed

*Two trucks to one station: the second waits for the dwell to end and
the occupant to leave, then arrives. No swap deadlock, no
two-in-a-spur.*

**It took three stagings and the first two are kept, because each one
measured a different thing and only the third isolated the gate's actual
subject.** M6.4's Gate 2 was blocked partly because it was staged where
arrival itself could not happen; repeating that mistake would have
produced the same non-answer.

**A SPUR station is the only staging that asks the question.** S1 and S5
sit ON their aisles — `floor.spur_entry` reads that off the graph, not
off a list — so they have no entry node to hand over and no answer to
give. Every run below is at a spur.

### Run A, 19:13:13 — S4, and the arrival is the confounder again

`submit S4 S2` → f2 (5.50 m) and `submit S4 S10` → f4 (8.50 m).

```
19:13:46.871  ARRIVED f2 at S4  pose (6.2163, -7.8761)  error 0.2493 m
19:13:46.877  ft-637c377f -> DWELL
19:13:49.921  dwell done - f2 drives ft-637c377f to S2      (3.04 s)
              f4 WAITS (6.0,-5.5) holding (8.0,-5.5)
19:14:45.524  the entry node passes f2 -> f4, and f4 drives into the spur
```

**The handover itself worked, and the ownership trace says so the same
way run C's does** — `(6.0, -5.5)` went `FREE -> f2` at 19:13:13.542 and
`f2 -> f4` at 19:14:45.524, **never free in between**, 55.6 s after the
occupant's leg 2 went out and it had cleared the 2.5 m spur. What the
queued truck then did was orbit S4 at a radius of roughly 0.7 m for four minutes,
against that station's `arrive_m` of 0.25, and never arrive:

```
19:18:18.451 x=5.2853 y=-7.9277   19:18:32.341 x=5.9972 y=-8.6864
19:18:23.737 x=5.3795 y=-8.3540   19:18:39.436 x=6.5133 y=-8.4273
19:18:27.433 x=5.5799 y=-8.5624   19:18:44.259 x=6.6676 y=-8.0210
```

That is M6.4's residual 3 — the minimum-turning-radius orbit — measured
at **S4**, which M6.4's own note called a spur that "aligns in". It
aligns in from the west, where f2 came from; it does not from the east,
where f4 came from.

**And the run measured something else, which is why it is kept.** On its
way west to S2, f2's Motor dropped at 19:14:53.654:

```
odom   19:14:53.621  x=0.6245 y=-5.5053 v=0.6933
fields 19:14:53.641  left {pf true, d 2.36 WARNING}   right SAFE  back SAFE
status 19:14:53.654  {"estop_healthy": true, "motor": false, "v_limit": 300}
```

A safe-speed latch: the warning went violated, `V_Limit` fell 1500 → 300
in the same cycle, the wheels were at 693 mm/s, and the `speed` instance
latched 13 ms later. **What f2 saw at 2.36 m was f1's parked body on
S1**, which the idle-hold timeout had given back to the floor thirty
seconds after bring-up. The status document says so in its own words,
and it is the most honest line the fleet prints:

```
idle timeout: f1 gave back 1 element(s) at (-3.0,-5.5) - it is still standing
there … THE TRUCK IS STILL THERE: this gives up the fleet's promise not to
route through it, not a claim that the floor is clear, and the scanners
remain what stop anybody sent that way
```

f2 came to rest **3.62 m short of f1** and nothing touched anything. The
ledger deconflicted two processes; the scanners stopped the truck. Not
ticked.

### Run B, 19:20:41 — S7, and a deadlock the ledger cannot see

Staged at a 0.85 m spur with `arrive_m` 0.80 so that arrival could not
be the confounder. `submit S7 S9` → f4 (16.00 m), `submit S7 S6` → f3
(21.37 m).

```
19:22:34.152  ARRIVED f4 at S7  pose (7.6217, 5.7954)  error 0.7997 m
19:23:15.303  ARRIVED f4 at S9  pose (8.7494, 5.0715)  error 0.7971 m  DONE
              f3 WAITS (8.0,5.7) throughout, then takes the entry + station
```

**The occupant completed both legs, the queued truck got the floor — and
still could not arrive.** f3 stopped at `(5.95, 5.65)` in nav **HOLD**
with `guard_min 1.12 m`. f4's arrival at S9 had left its body at
`(8.75, 5.07)`, **0.95 m off the junction f3 had to turn at**.
`arrive_m` 0.80 is a tolerance, and a truck is entitled to spend all of
it standing in the aisle.

Sending f4 away with fleet work (`submit S9 S5`, taken at 0.80 m over
f1/f2 at 23.00 m) made it worse and made it clear:

```
f3 holds (8.0,5.7) …   f4 WAITS (8.0,5.7)   f4 yielded, retrying every pass
19:26:38  f4 gets 1 of 3 nodes to S5 as base and 2 as horizon -
          the rest of the corridor is taken
```

f3 cannot move because f4's **body** is 1.12 m in front of it; f4 cannot
move because f3 owns the **floor** it needs. **The deadlock resolver
never sees it**, and it is right not to: f3 is not waiting on the ledger,
it is waiting on nav's obstacle guard, and the resolver reads ledger
waits. Not ticked.

### Run C, 19:29:57 — S6, and the fix on the wire

Same shape, one variable changed: the occupant's leg 2 leaves **west and
away**, so its body does not end up in the junction. `submit S6 S3` → f3
(5.35 m, chosen over f1 23.00, f2 23.00, f4 32.04), `submit S6 S8` → f1.

```
19:29:58,088  f1 gets 3 of 5 nodes to S6 as base and 2 as horizon -
              the rest of the corridor is taken
19:29:58.162  f1 WAITS (-8.0,5.7)
19:30:57,401  f3 arrived at S6 - dwelling   pose (-8.7878, 6.5716) err 0.7911
19:30:57.404  f3 holds (-8.0,5.7) (-8.0,5.7)-(-8.0,6.5) (-8.0,6.5)
                                 ^^^^^^^^^^ THE ENTRY, THROUGH THE DWELL
19:31:00,414  dwell done - f3 drives ft-4b69421a to S3       (3.01 s)
19:31:44,290  ft-271bee61: base extended to 5 released + 0 horizon (upd 1)
19:31:44.340  f1 holds (-8.0,5.7) … (-8.0,6.5)
19:32:10,680  f1 arrived at S6 - dwelling   pose (-8.2537, 5.7424) err 0.7990
19:32:13,691  dwell done - f1 drives ft-1e8b6b37 to S8       (3.01 s)
19:32:54,249  f1 completed ft-1e8b6b37 at S8   pose (-7.2438, 5.0453) err 0.7950
19:33:33,482  f3 completed ft-4b69421a at S3   pose (-6.8795, -5.9939) err 0.7990
```

**The whole of the M6.5 fix is one line, and it is this one.** Ownership
of the entry node `(-8.0, 5.7)` across the entire run, read off the
retained `fleet/status` rather than re-derived:

```
19:29:57.901   FREE -> f3
19:31:44.340   f3   -> f1        <-- the handover
19:32:54.252   f1   -> FREE
```

**It is never FREE between the two vehicles.** M6.4's run A measured the
opposite — the occupant released the junction in the millisecond it
arrived, the queued truck took it inside one 100 ms pass, and three
seconds later the occupant's leg 2 asked for its only way out and got a
swap deadlock. Here the entry stays held through the dwell and moves
into leg 2's hold with nothing freed in between, exactly as
`_dwell_entry` and `_release_to` were written to make it.

f1 waited **106.18 s** (19:29:58.162 → 19:31:44.340) — the dwell is 3 s
and the rest is the occupant clearing 4.5 m of spur and corridor, which
is the ruling's accepted price and is visible here as a number rather
than a paragraph.

**Both transports completed. No swap deadlock at any point, no BLOCKED
entry, and never two vehicles holding the spur. 0 motor-false on all
four: 0 of 4,460 samples each.**

**Ticked.**

## [ ] Gate 3 — four-vehicle traffic: FAILED, twice over, in one run

*Four transports with deliberately crossing routes, all four trucks
driving; every one completes; holds, extensions and waits recorded;
0 motor-false; no deadlock refusal — or, if one occurs, name it
honestly.*

19:35:11. Four transports, submitted back-to-back, assigned one per
truck inside **900 ms**, each with the manager's own nearest-idle
evidence:

```
19:35:11,792  assigned ft-a3644e79 to f1 (nearest idle to S8: f1 0.79 m
              <-- chosen, f2 23.00 m, f3 22.34 m, f4 32.04 m)
19:35:12,095  assigned ft-738f6727 to f3 (… f2 11.50 m, f3 0.77 m <-- chosen,
              f4 20.54 m)
19:35:12,298  assigned ft-199f702a to f2 (… f2 6.00 m <-- chosen, f4 15.04 m)
19:35:12,500  assigned ft-1efbc18e to f4 (… f4 16.04 m <-- chosen)
```

The crossings were deliberate: f1 west→east on the main aisle, f4
east→west on the same aisle head-on, f3 west→east on the dock aisle and
then north, f2 east→west on the dock aisle head-on.

**The fleet named the first failure itself, and the message is better
than anything this file could write:**

```
19:36:01,912 fleet ERROR UNRESOLVABLE: swap deadlock f2 <-> f3 - each truck
stands on the floor the other needs, so the youngest yielding frees nothing
and wait-die cannot break it. A vehicle has to be moved (f2 was the youngest)
```

`ft-199f702a` was requeued to the head of the queue — and never picked
up again for the rest of the gate, because **f2 went on executing the
order the manager had taken away from it**, and `_idle_floor` explicitly
does not age a vehicle that is executing an order the fleet does not own
(that exemption exists for a restarted manager's adopted truck). So f2's
hold on `(-3.0, -5.5)` never timed out, and f3 waited on it until the
gate ended.

**The second failure is the same shape with a different resolver
outcome.** f1 and f4 met head-on on the main aisle, each standing on the
node the other's route needed. Wait-die worked exactly as designed —
f4 carried the youngest task and yielded — and it changed nothing:

```
19:37:05..19:42:04  3,180 x  "deadlock f1 -> f4 - f4 carries the youngest task
and yields 4 element(s). It keeps its task and its route and holds again the
moment the corridor drains"
```

at 10 Hz, for five minutes, until the run was cancelled. **Yielding frees
the floor AHEAD of a vehicle; what f1 needed was the floor UNDER f4.**
The corridor never drained because nothing in the policy can make a
truck reverse.

Everything the gate asked to be *recorded* was recorded — holds,
extensions, waits, the yield, the refusal — and the safety half is
clean:

```
transports completed          0 of 4
motor-false                   f1 0/8260  f2 0/8260  f3 0/8260  f4 0/8260
closest approach, any pair    2.513 m  (f2/f3 at 19:40:41)
travelled                     f1 14.6 m  f2 5.8 m  f3 34.2 m  f4 17.4 m
```

**Not ticked.** Two deadlocks, one declared UNRESOLVABLE by the fleet
and one live-locked in the resolver, and no transport finished.

## [ ] Gate 4 — the acceptance run: FAILED, 1 of 8

*Eight transports submitted back-to-back across the ten stations, all
four trucks, no operator intervention once it starts.*

19:43:06.796 → 19:43:08.813, two seconds, eight submissions, all ten
stations: `S1→S6`, `S4→S7`, `S2→S8`, `S5→S9`, `S6→S3`, `S7→S10`,
`S8→S5`, `S9→S4`. Four trucks at their table poses, Motor True,
AUTOMATIC, task book empty. **No operator touched anything from that
moment until 19:53:48.**

**Eight seconds in, f3's Motor dropped, and it never moved again.**

```
odom   19:43:15.078  x=-13.2687 y=5.7846 v=0.1999
fields 19:43:15.078  back  {pf true,  d 2.160 WARNING}
                     left  {pf true,  d 2.006 WARNING}
                     right {pf FALSE, d 0.971 PROTECTIVE}
status 19:43:15.143  {"estop_healthy": true, "motor": false, "v_limit": 300}
nav    19:43:15.150  SAFETY-STOP  route [(-12.5,5.65) (-12.5,-5.5) (-9.8,-5.5)
                                         (-9.8,-6.6)]
```

Its transport was `S2→S8`, whose leg 1 turns **south** out of the pose
f3 ships in. The track shows the whole thing in seven seconds — the
truck crept west at the 0.30 m/s its own warning field had already
imposed, swinging into the turn, and put its fork corner 0.971 m from
the wall it was parked 2.5 m from:

```
19:43:08.005 x=-12.5326  19:43:11.104 x=-12.8217  19:43:14.081 x=-13.1743
19:43:09.396 x=-12.6537  19:43:12.439 x=-12.9815  19:43:14.864 x=-13.2499
19:43:10.404 x=-12.7482  19:43:13.435 x=-13.0979  19:43:15.299 v=0.0000
```

**f3 cannot turn south out of the pose it ships in.** It can go east —
it did so in the warm-up and twice in Gate 2 — because east is away from
the wall. The southbound turn is the one its own spawn coordinates
forbid, and it is the first move of any task that sends f3 to the
dock aisle.

Its hulk then held the west cross-aisle for the rest of the run, and
what the other three did with what was left is the measurement.

### The headline, measured over 624 s (19:43:06 → 19:53:30)

| | |
|---|---|
| transports completed | **1 of 8** — `S1→S6` on f1, completed 19:45:17,572 |
| **throughput** | **0.096 transports/min** — one every 10.4 minutes |
| per-vehicle utilisation | f1 **99.0 %**, f2 **16.0 %**, f3 **1.2 %**, f4 **99.7 %** |
| distance travelled | f1 70.1 m, f2 16.9 m, f3 0.8 m, f4 58.7 m |
| **total waiting time** | **1,072.9 vehicle-seconds** in 624 s of run (f1 488.0 s, f2 584.9 s) |
| arrival errors | 0.0001 m (S1), 0.7986 and 0.7948 m (S6), 0.2487 m (S4) — every one inside its station's `arrive_m` |
| motor-false | f1 **0**, f2 **0**, f4 **0** of 12,480 samples each; f3 **12,299 of 12,480**, one onset |
| **full-stack RTF** | six consecutive 60 s windows — printed mean **0.552–0.583**, **integrated 0.575–0.580**, floor 0.021–0.035 |

**Read the utilisation column with the bounding boxes or it will lie to
you.** f1's 99.0 % and seventy metres were spent inside a
**1.57 x 1.95 m** box for eight minutes; f4's 99.7 % and fifty-nine
metres inside **1.46 x 5.48 m**. Both were orbiting — f1 the mouth of
the S6 spur, f4 the east corner. *Moving* is not *productive*, and at
four vehicles the gap between those two words is the entire number. A
utilisation figure quoted without the box it was measured in would have
called this run 74 % busy.

**The waiting figure is the honest one.** 1,072.9 vehicle-seconds of
declared waiting against 2,496 vehicle-seconds of capacity — 43 % of the
fleet's time spent holding station for floor it never got.

### The RTF, which is the one figure that came out well

```
accept-w1  576 samples  printed 0.552  min 0.035  max 1.000  integrated 0.577
accept-w2  579          printed 0.583  min 0.029  max 1.103  integrated 0.578
accept-w3  577          printed 0.573  min 0.027  max 1.100  integrated 0.575
accept-w4  576          printed 0.572  min 0.026  max 1.061  integrated 0.580
accept-w5  574          printed 0.562  min 0.031  max 1.118  integrated 0.577
accept-w6  574          printed 0.568  min 0.021  max 1.056  integrated 0.575
```

**The full 39-pid stack, four trucks, sixteen lidars subscribed and
rendering, D3D12/NVIDIA: 0.575–0.580 of real time, held to within
0.005 across ten continuous minutes, against the 0.30 gate.** That is
the shipping configuration measured under load, which is what M6.5's
Gate 1 said was still owed, and it is nearly double the gate. Two things
must travel with it: it is **conditional on the two GPU exports** quoted
at the top of this section, and the instantaneous floor is still
0.021–0.035, so the deep stalls M6.1 named have not gone away — they are
simply short enough that `SENSOR_STALE_S` at 0.40 s rode every one of
them out, with zero stale-link events on any truck in the whole session.

**Not ticked.** One of eight is not an acceptance run. What it is, is a
measurement of what four trucks do on this floor when one of them cannot
leave its own parking space.

## [ ] Gate 5 — degradation under loss: three clauses of four

*Kill one vehicle mid-acceptance: its task requeues, the survivors
finish everything, the fleet never assigns to the dead truck, and the
floor is not left locked.*

**Run in its own window, not inside the acceptance run, and the reason
is Gate 4's.** That run had already lost a truck to a protective latch
eight seconds in; killing a second one inside it would have measured two
losses of different kinds at once and told us about neither. Its own run
is the cleaner instrument, and this is the choice, named.

19:54:53. Two transports: `S3→S2` → f1 (5.50 m), `S7→S9` → f4
(16.00 m). f4 was killed in the x = 12 corridor deliberately — only six
of the ninety routes use it, so the hulk would sit where it inconvenienced
the fewest.

```
19:55:51.716  f4 at (12.019, 2.080) doing 0.300 m/s   $ kill 135784
19:55:51,847  f4 is gone (OFFLINE) mid-ASSIGNED_LEG1                  131 ms
19:55:51,847  f4 is holding (12.0,-5.5) where it stopped - nothing is routed
              through a parked hulk until it reports a fresh idle state
19:55:51,848  assigned ft-2416cf33 to f3 (nearest idle to S7: f2 23.00 m,
              f3 21.37 m <-- chosen)                                  132 ms
19:56:18,765  f1 completed ft-424f7262 at S2   (errors 0.7965 at S3, 0.7976 at S2)
```

**Three clauses hold, cleanly.** The task requeued and was reassigned
**132 ms** after the kill, with no QUEUED interval at all. **f4 appears
in no `nearest idle` list from that moment to the end of the session.**
The floor was not locked: the ledger released f4's whole route hold and
kept exactly one element, shown in the operator's own view as
`parked:f4 holds (12.0,-5.5)`.

**The fourth does not, and it is worse at four vehicles than M6.4
measured it at two.** With no agent alive, nothing can publish an empty
goal — so `nav_node` went on following the last one it was given:

```
f4 after the kill: 1141 samples  19:55:51.716 -> 19:57:29.997
  from (12.019, 2.080) to (7.635, 5.792)
  path length 8.48 m   straight line 5.74 m
  last motion at 19:56:47.244  v=0.058
```

**A dead truck drove 8.48 m in 55.5 s** — up the corridor, **around the
(12.0, 5.65) junction**, and west along the main aisle into the mouth of
the S7 spur — before its own safe-speed instance latched at 19:56:46.359
(right warning 2.429 m, `V_Limit` 1500 → 300, wheels at 250 mm/s and
climbing on the turn). Meanwhile the fleet's position for f4 stayed
frozen at `(12.03, 1.74)` — the last state the dead agent published —
and the ledger's pin stayed at `(12.0, -5.5)`, **7.2 m from where the
body actually came to rest**.

f3, holding the entire main aisle the ledger had granted it, drove east
and stopped at `(5.223, 5.655)` in nav **HOLD**, `guard_min 1.465 m`,
**2.41 m short of the hulk**, and stayed there. The survivors did not
finish everything, and the reason is not the fleet's arithmetic — it is
that the fleet's arithmetic was about a truck that was no longer where
the arithmetic said.

M6.4 measured this at 2.93 m and called it "bounded today by how fast an
agent comes back". At four vehicles, with longer routes, **it is 8.48 m
and it crosses a junction**. Not ticked.

## [x] Gate 6 — safety untouched at four

*Every Motor drop named at its sample, no correlation with any fleet
event, across the whole session — and say HOW you know, not that you
looked.*

**How this is known, in three steps.**

**1. Where a Motor drop can come from at all.** `virtual_fplc` has five
instances — `estop`, `pf`, `pf_right`, `pf_left`, `speed` — and Motor is
the AND of all five being unlatched. Every one is driven by a hardware
input the fleet has no wire to: the E-Stop bool, three OSSD bools from
the scanners, and the two encoder channels against the live `V_Limit`.
**The fleet manager's only path to a truck is the VDA 5050 order topic,
and no byte of it reaches any of those five.** That is the structure;
the rest is measurement, because structure is a claim and this file does
not take claims.

**2. Every drop in the session, named at the sample it happened.** Nine
onsets across 79,361–79,396 samples per truck:

```
f1 18:57:12.108  wheels 0.0000, PROTECTIVE at spawn  -> startup acknowledge
f3 18:57:12.202  wheels 0.0000                       -> ditto
f2 18:57:14.048  wheels 0.0000                       -> ditto
f4 18:57:14.048  wheels 0.0000                       -> ditto
     all four cleared by the first RESET at 18:59:44

f4 19:05:43.508  estop_healthy=True  wheels 0.1772  left 0.993 PROTECTIVE
                 -> the CONVEYOR at the (12.0,5.65) junction, 2.00 m from
                    the node, on the turn.  A static structure.
f2 19:14:53.654  estop_healthy=True  wheels 0.6933  left 2.36 WARNING
                 -> SAFE-SPEED: f1's PARKED BODY on S1, 3.62 m ahead
f4 19:27:10.658  estop_healthy=True  wheels 0.0011  back 1.000 PROTECTIVE
                 -> RackB_E, manoeuvring inside the 0.85 m S9 spur.  Static.
f3 19:43:15.092  estop_healthy=True  wheels 0.1999  right 0.971 PROTECTIVE
                 -> the WEST WALL, turning south out of its own spawn pose
f4 19:56:46.359  estop_healthy=True  wheels 0.1654  right 2.429 WARNING
                 -> SAFE-SPEED on the turn into S7, with no agent alive
```

Four are the startup acknowledge, with the wheels at rest and no order
anywhere near. Five are a scanner reading a distance, and **every one of
those five carries a field reading and a wheel speed on the same
sample**: three are a truck against a static structure (a conveyor, a
rack face, a wall), one is a truck against another truck's parked body,
and one is a truck whose own agent was dead. **Not one of them is a
reservation.**

**3. The correlation test, run over the whole capture.** For each of the
nine onsets, every message a **truck reads** — `uagv/v2/amragent/+/order`
and `+/instantActions` — published within ±2 s:

```
9 motor-false onsets examined
0 order/instantAction publishes inside any of the nine +/- 2 s windows
(the session carried 157 of them)
```

Zero. `fleet/status` is deliberately excluded and the reason is M6.4's:
it is republished on change and at least every 2 s, so it lands inside
any window one cares to draw, and it is not a message a truck ever
reads. **The messages a truck DOES read were not on the wire within two
seconds of any Motor drop in this session.**

**And the reverse direction, which is the one that matters for a fleet
milestone** — every window in which the ledger was live, holding,
granting, extending, refusing, yielding and once declaring itself
UNRESOLVABLE:

```
Gate 2 run C   f1 0 of 4,460   f2 0 of 4,460   f3 0 of 4,460   f4 0 of 4,460
Gate 3         f1 0 of 8,260   f2 0 of 8,260   f3 0 of 8,260   f4 0 of 8,260
                               -------------
                               0 of 12,720 per truck, all four
Gate 4         f1 0 of 12,480  f2 0 of 12,480  f4 0 of 12,480
                               (f3 is the west wall, named above)
Gate 5         f1 0 of 10,140  f2 0 of 10,140  f3 0 of 10,140
                               (f4 is the dead truck, named above)
```

**Twelve thousand seven hundred and twenty samples per truck, on all
four trucks at once, with the floor being reserved, granted, released,
extended, refused, yielded and deadlocked — and not one Motor drop.**
Across the acceptance run and the loss run, the only two drops on any
truck are the two the list above names, and both are a scanner reading a
distance to something solid.

The safe-speed latch itself remains M6.3's third defect, unchanged and
not M6.5's: `_healthy()` demands `max(|ENC_A|,|ENC_B|) <= V_Limit`, and
`V_Limit` drops 1500 → 300 the instant any warning field is violated
(ruling 2026-08-20). `cmd_gate` does clamp to the new limit — measured
here, `enc=-250/-250` on a truck whose `V_Limit` had already fallen —
but a truck already doing 0.69 m/s cannot decelerate inside one scan
cycle, so the instance latches on the way down. Both safe-speed drops in
this session are that transient and neither is a traffic event.

**Ticked.**

## Teardown

Writers first, all four:

```
> {"quit":true} -> 5910 / 5920 / 5930 / 5940
shutting down: writing the trip values
writer for f1 is down     (f2, f3, f4 identical)
```

`Get-CimInstance Win32_Process -Filter "Name='python.exe'"` afterwards
returns three VS Code language servers and nothing else. Both recorders
were stopped next, the ROS one printing the session counts quoted above.

```
$ ./m6.sh stop
  … swept 135250 (cmd_mux.py) … 135305 … 135628 … 135659 … 135745
down.
$ ss -uln | grep -E ':(5110|5111|5120|5121|5130|5131|5140|5141)'  -> all free
$ ss -ltn | grep ':1883 '                                          -> free
$ pgrep -af 'gz sim|plc_link|vda_agent|fleet_manager|…|rec3|mqtt_rec3'
                                                                   -> none
$ test -f .m6_pids                                                 -> removed
```

The pidfile held **44** lines against the thirty-nine started: the extra
five are this session's manager restarts, each appended by the same
`setsid … echo $$ >> "$1"` shape `m6.sh` uses, which is why `stop` swept
them all.

**One process survives and it is not this stack's:** `mosquitto -p
18883`, pid 112546, started 15:39 — a leaked private fixture from an
earlier session's `test_vda_agent_mqtt.py`. It holds no port this stack
wants (1883 was free before and after) and it is named here for the same
reason Task 4 named it: it is somebody else's orphan, not this run's.

```
$ source /opt/ros/jazzy/setup.bash
$ python3 -m pytest m6/tests/ -q            466 passed in 150.07s
$ python3 -m pytest m5_ver2/step5/tests/ -q 220 passed in 2.48s
```

**Source ROS first.** Without `setup.bash` both suites abort with seven
collection errors before a single test runs — the conftest imports
`rclpy`. That is not a regression and it is not new; it is worth one
line here because a clean-shell run of either suite looks like a
catastrophic failure and is nothing of the kind.

---

# M6.5 fix-up - the poses, the step-aside, and the run that stopped for a reason nobody had instrumented

**Date: 2026-08-22, 21:53-23:18. Four stacks, four teardowns, one
milestone still open.** The M6.5 gate run above ended with three gates
measured and not ticked, and the owner ruled *fix and re-run*. Two fixes
were named in that ruling; four more were bought at full price on the
floor tonight; and the acceptance run stopped 31 seconds in, all four
trucks at once, on something none of the previous sessions had an
instrument for.

**Everything below was measured, and none of it is a smoothed number.**

| | |
|---|---|
| GPU renderer | `glxinfo -B` gives `D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`; the server's own `~/.gz/rendering/ogre2.log` at 22:52:49 gives `GL_RENDERER = D3D12 (NVIDIA ...)`. Still **not** in `~/.bashrc`; exported by hand in every shell |
| deploy | `./m6.sh deploy` gave 31 files, `MANIFEST source-git: 77e7294` = HEAD, before the last stack started |
| stack | `start --headless` gave 39 pid lines, 39 in `.m6_pids`, 39 alive, four agents ONLINE |
| ROS recorder | `rec3.py`, **28 subs + 4 mode pubs** - the previous 24 plus `/fN/safety/encoders`, which is the stream this session was missing and the one that settled two arguments |
| MQTT recorder | `uagv/v2/amragent/+/#` and `fleet/#`, one `connected`, no disconnect |
| four writers | ctl 5910/5920/5930/5940, PF/WF live on the first cycle, all four AUTOMATIC and Motor True at 22:53:45 |
| suites after | m6 **480 passed**, step5 **220 passed** |

## [x] The poses clear their own fields, and the guard test says why

M6.5's Gate 4 lost the acceptance run eight seconds in because f3 shipped
1.82 m from the west wall - inside its own 2.5 m warning field - and its
first southbound turn put the same scanner 0.971 m from that wall.
`tests/test_vehicles_table.py` gained a third rule, measured off the
**world SDF's own collision boxes at the safety scan plane** rather than
off `stations.OBSTACLES` (documented as the SDF's shadow, tested against
nothing):

* **at rest** every scanner, at the pose's own yaw, further than
  `WF + hysteresis` (2.70 m) from any solid - the other three parked
  trucks included, their contour read from the vehicle SDF at that plane;
* **leaving** the pose itself further than
  `PF + hysteresis + scanner ring (0.821 m) + LOOKAHEAD_M/2 (0.60 m)`
  = **2.62 m**.

The rule predicts the run it was written from: f3's old pose scores
`2.500 - 0.821 - 0.600 = 1.079 m` through the turn against the 1.20 m it
needs, and the truck measured **0.971 m** at the latch - 0.108 m out.

**Read back off the running world at rest, 22:53:** every device `wf`
true and `V_Limit` **1500** on all four, against the old table's `T/F/F`
and 300 on two of them.

```
f1  back 4.490  left 4.040  right 4.960     all SAFE
f2  back 4.490  left 4.912  right 3.996     all SAFE
f3  back 3.344  left 2.840  right 2.840     all SAFE
f4  back 3.344  left 2.840  right 2.840     all SAFE
```

f3 and f4 measured 2.840 against **2.840 computed**. The arithmetic and
the scanners agree to the millimetre.

**And the first-move turn, live (21:56, the first stack).** f3 was sent
east out of its new pose - the reverse-direction move that latched it at
the old one - and drove 4.4 m with `y` drifting 0.0010 m. Worst field
reading of the whole move **2.790 m**, against 2.70 to clear and 1.20 to
latch. **0 motor-false and 0 PROTECTIVE on all four trucks** from the
RESET to the end of that run.

**Two more pose rules were bought on the floor and cannot be tested.**
f4 first went to `(8.0, -5.5)` - 6 of the 90 routes, the quietest clear
node on this plan - and could not reach S4, its own nearest station at
4.50 m, at either yaw:

```
yaw pi  travel heading EAST, so going west is a straight REVERSE; the
        follower leaves the reverse phase only when the next target is
        within REVERSE_EXIT_RAD (75 deg) of its heading, and turning
        south into a spur is 94 deg. It reversed 2.18 m, passed the
        junction by 0.18 m, and stopped for good at 21:57:07 with nav's
        obstacle guard 1.477 m off PARKED f2 (GUARD_HOLD_M 1.5)
yaw 0   drove up forwards at 0.70 m/s, decelerated into the corner and
        STALLED in it - steer joint -0.926 rad against a -2.5 rad/s
        traction command, drive-wheel velocity 8e-5 rad/s, nav still
        EN-ROUTE with the guard clear at 2.975 m - for seven minutes
```

2.00 m is what that node leaves between a parked truck and the S4 spur
junction. So: **every yaw points the truck at the floor it will be sent
to**, and **a parked truck must have room to turn into the stations it is
nearest to**. f4 moved to `(3.0, 5.65)`, 36 of 90 routes instead of 6,
and the four poses became a division of the floor - f1 nearest to
S1/S3/S10/S2, f2 to S4, f3 to S6/S8, f4 to S5/S7/S9, every station within
8.60 m of a truck.

## [x] The step-aside works, on the wire, in a live deadlock

M6.5's Gate 3 measured two deadlocks wait-die could not break and named
both honestly; nothing moved, and 0 of 4 transports finished. The fleet
now moves a truck. **It fired twice tonight, in two separate live Gate 3
runs, unprompted:**

```
22:54:10,523  swap deadlock f1 <-> f2 - each truck stands on the floor
              the other needs, so wait-die frees nothing that helps. f2
              carries the youngest task and is asked to step aside from
              (0.0,-5.5) to (0.0,5.7), which clears f1
22:54:10,525  f2 is cancelled on ft-d263cb8c - ... It is eligible again
              the moment its own state stops showing that order
22:54:10,627  f2 is being moved aside to (0.0,5.7) as ft-cf94fd3a - one
              node, no task, and it is eligible again the moment it gets
              there
```

Two milliseconds from the detection to the cancel, 104 ms to the
one-node order. f1's route east cleared and f1 drove it. The order is an
`ft-` order built by `order_builder.build_step_aside_order`, validated by
`vda_orders.validate_order` - the vehicle's own door - and published
through the same funnel a leg goes through; the vehicle accepted it.

**And the run found the bound that was set wrong.** `ASIDE_S` was 60 s,
written against "11.15 m at the worst edge at 0.30 m/s is 37 s". The
move took **199 s** - the truck creeps, and the connector is the longest
edge on the graph - so the fleet gave up on its own clock at 22:55:10
and said so, and the truck arrived at 22:57 anyway. The bound worked,
the number was wrong, and the number is a one-line change nobody should
make without re-measuring the creep.

**The second thing it found is worse and is a design point, not a
constant.** `step_aside_target` ranks free neighbours by
`(on their route, is a spur junction, distance)` - distance third - so it
chose an **11.15 m** connector over a 3.00 m aisle node that was on f1's
route. Eleven metres driven as a single node with no route is not a step
aside: f2 arced into the cross-aisle rack corner and its left scanner
reached 1.109 m and falling. **The choice needs a distance BOUND, not a
distance preference**, and with one the honest answer here would have
been the named refusal.

## [ ] Gate 3 - four-vehicle traffic: 0 of 4, twice

Four transports with crossing routes, one per truck, assigned inside
3.0 s with the nearest-idle evidence on each: `S1 S4` to f1 (0.00 m),
`S10 S1` to f2 (12.00 m), `S6 S9` to f3 (5.85 m), `S7 S8` to f4
(5.85 m). Run twice, 22:39 and 22:53.

```
transports completed   0 of 4          (both runs)
travelled              f1 44.7 m  f2 14.4 m  f3 14.5 m  f4 46.1 m
motor-false (run 2)    f1 0/11183   f3 0/11184   f4 0/11185
                       f2 8656/11184
```

**Three of the four trucks never dropped Motor once in nine minutes of
driving**, which is the first time that has been true of a four-vehicle
traffic run, and it is what the two speed-policy fixes below bought.
What stopped it: f3 and f4 met head-on on the main aisle, each holding
the floor the other's route needed, and **neither ever reached the end of
its base**, so `_resolve` correctly refused to yield floor a truck is
still driving and the step-aside never got its turn. f3 sat at
`(-2.24, 5.69)` with `traction_cmd -2.5`, `steer_cmd -0.061` - straight
ahead, not saturated - and did not move. Not ticked.

## [ ] Gate 4 - the acceptance run: 0 of 8, and the reason is new

23:05:46.844 to 23:05:49.296: eight transports over the ten stations,
`S1 S6`, `S4 S7`, `S2 S8`, `S5 S9`, `S6 S3`, `S7 S10`, `S8 S5`, `S9 S4`,
in **2.45 s**. Four assigned one per truck inside a second, four queued.
Four trucks at their table poses, Motor True, AUTOMATIC, every field
clear. **No operator touched anything from that moment until 23:17:18.**

**Thirty-one seconds in, all four trucks latched inside 0.56 s of each
other**, and the recorder that was added this session says exactly why:

```
f3  motor false 23:06:17.930   enc -300/-300 for the whole second before
    fields  23:06:17.806  SAFE SAFE SAFE   3.299 2.798 2.790
            23:06:17.903  SAFE SAFE PROT   3.298 2.801 0.000
f4  motor false 23:06:18.116   enc -300/-300
            23:06:18.081  SAFE PROT SAFE   3.295 0.000 2.794
f2  motor false 23:06:18.263   enc -250/-250
            23:06:18.200  PROT PROT PROT   0.000 0.000 0.000
f1  motor false 23:06:18.491   enc -300/-300 then -100 then -55
            23:06:18.440  SAFE PROT PROT   4.482 0.000 0.000
```

**Every one of those is `d = 0.000`, and 0.000 is not a distance.** It is
what `field_eval.min_range` returns for an empty ranges array, a scan
that is entirely muted, or a `-inf`/`nan` return - *"a broken device is
not an empty room"*, written into that function in Step 2 and doing
precisely its job here. Eight devices across four trucks reported it
inside 0.56 s. That is not eight obstacles.

```
field reports carrying a 0.000 device, per truck, over the whole run
  f1 3 of 7417   f2 6 of 7416   f3 7 of 7418   f4 6 of 7417
```

**Three to seven samples out of seven thousand four hundred, all inside
one second, cost the entire run** - because a protective demand LATCHES
and only a panel RESET clears it, and the acceptance run has no operator
in it by definition.

### The headline, measured over 692 s (23:05:46 to 23:17:18)

| | |
|---|---|
| transports completed | **0 of 8** |
| throughput | **0.00 transports/min** |
| distance travelled | f1 3.3 m, f2 4.7 m, f3 4.3 m, f4 4.2 m - **16.5 m in 11.5 minutes** |
| per-vehicle utilisation | 4.5 % of the run before the latch; 0 % after |
| total waiting time | not meaningful: no truck was ever waiting on the ledger, all four were waiting on a RESET |
| arrival errors | **none - no leg completed** |
| motor-false | f1 14,186 of 14,835; f2 14,191 of 14,836; f3 14,198 of 14,837; f4 14,195 of 14,838. **One onset each, all four inside 0.56 s** |
| **full-stack RTF** | printed **0.425-0.537**, integrated **0.445-0.523**, **floor 0.010-0.025**, six consecutive 60 s windows |

**The RTF is the other half of the sentence.** The M6.5 gate session
measured integrated 0.575-0.580 with a floor of 0.021; this one measured
0.445-0.523 with a floor of **0.010**, twice as deep. The extra load is
this session's own: four more recorder subscriptions at 20 Hz, and a
speed policy that keeps every main-aisle truck at 0.30 m/s so every run
lasts longer. **Sixteen gpu_lidars rendering on a stack whose
instantaneous real-time factor touches 0.010 do not all deliver their
scans**, the field evaluators correctly call an undelivered scan a
violated field, and the safety layer stops four trucks that were doing
nothing wrong.

**Not ticked, and this is the first time the reason has been the rig
rather than the cell.** Nothing in the fleet layer, the poses or the
traffic ledger appears anywhere in this failure. The instrument to carry
forward is the one that found it: `/fN/safety/encoders` recorded
alongside `/fN/safety/fields`, which is what makes "the wheels were at
300 and V_Limit was 300" distinguishable from "the scanner reported
0.000".

## [ ] Gate 5 - degradation under loss: NOT RE-RUN

Gate 4 ended with four latched trucks and no operator budget left in the
session. Killing a vehicle in that state would have measured a loss
against a fleet that was already stopped, which is worth nothing. M6.5's
own Gate 5 result stands unchanged: three clauses of four, the fourth
failing because with no agent alive nothing publishes an empty goal and
nav drove a dead truck 8.48 m across a junction.

## The two speed-policy defects this session found, and fixed

Both were bought at full price and both are in the vehicle layer, not
the fleet's. They are here because they are the reason three of four
trucks ran a nine-minute traffic gate without a single Motor drop, and
because the first one had been hiding behind a pose bug for two
milestones.

**1. The guard band was measured at the wrong sensor.** `follower.py`'s
header has always stated the rule: the lidar must have the truck at the
creep ceiling *before* a warning field can drop `V_Limit` under wheels
still doing 0.7 m/s, because the F-program's speed monitor demands a stop
the instant either encoder channel reads above `V_Limit` and that demand
LATCHES. `GUARD_SLOW_M` was 3.0 m against a 2.5 m field and read as if it
kept that rule. It did not: the field is evaluated at the **fork-corner
scanners** (model `-0.68, +-0.46`) and the guard at the **nav lidar**
(`0.55, -0.40`), **1.23 m further back**, so 3.0 m at the lidar is 1.77 m
at the scanners - three quarters of a metre inside the field.

```
22:19:20  f2 westbound on the dock aisle, 0.699 m/s, nav guard 5.2 m and
          clear; fork corners reach 2.33 m off f1 PARKED on S1; both
          warning fields drop; V_Limit 1500 to 300 with the wheels at
          700 mm/s; the speed monitor latches. RESET, resume, and it did
          it again at the same place.
```

`GUARD_SLOW_M` becomes **4.3 m** = 2.50 field + 0.20 hysteresis + 1.23
mount offset + 0.35 to slow down.

**2. The nav lidar cannot see abeam, and the field can.** The band above
keeps the truck out of a field it drives *into*; nothing kept it out of
one it drives *past*. The guard is a +-35 deg cone about the travel
heading and a rack face 2.75 m off the shoulder is nowhere near it:

```
22:40:28.215  f3 westbound on the main aisle, forward cone clear
              right scanner 2.307 m off rack A -> WARNING
              V_Limit 1500 -> 300
     .215     encoders -700 / -700 on that same 20 Hz sample
22:40:28.223  Motor false, and it stays false
     .335     -509      .485  -162      .635  0
```

**Eight milliseconds**, and the wheels needed 300 ms to comply. The floor
is why this is not a tuning problem: the main aisle gives a fork-corner
scanner **2.79 m** of lateral clearance (3.25 m centreline to rack face,
0.46 m mount offset) against a **2.70 m** re-clear threshold. **Nine
centimetres.** No pursuit holds a line that well.

So the speed policy gained a fourth band read at the devices that
actually evaluate the field: `nav_node` subscribes to
`/fN/safety/fields`, takes the closest of the three, and `target_speed`
caps at the creep ceiling inside `FIELD_SLOW_M` = **3.3 m**. It reads the
DISTANCE and not the verdict, because by the time the verdict flips
`V_Limit` has flipped with it. There is no HOLD counterpart and there
must not be: a protective stop is the F-program's to demand.

**THE COST, STATED, AND IT IS LARGE.** Every main-aisle transit now runs
at 0.30 m/s instead of 0.70, because every main-aisle transit is inside
that band for its whole length. The dock aisle (4.04 m to the nearest
solid) is unaffected. That trade is the owner's to keep or reject; what
it replaced was a latched truck every time an aisle was driven at speed.

## The re-run the owner ruled, and the number that stopped it

**Owner ruling after the run above: cut the instrumentation load and run
the acceptance once more; measure the floor first, and if it is still
~0.01, say so and STOP.** It is 0.008. This section is that measurement
and nothing else, because driving trucks into it would only have
produced a fifth capture of the same latch.

### What was dropped, and what each surviving channel is for

The ROS recorder went from **28 subscriptions to 20**, and the fleet-side
one from `uagv/v2/amragent/+/#` to four named topics:

| kept | what no gate can be named without it |
|---|---|
| `/fN/plc/status` | the Motor-false counts and their onsets - the causation spine of every gate in this file |
| `/fN/auto/state` | ARRIVED / HOLD / EN-ROUTE, and `guard_min` |
| `/fN/gz/odom` | distance, utilisation, and the coast/stop numbers |
| `/fN/safety/fields` | Gate 6's naming of every onset at its own sample |
| `/fN/safety/encoders` | the stream that distinguishes "the wheels were at 700 and V_Limit was 300" from "the scanner reported 0.000" - added this session, and it is what named the failure above |
| `fleet/#` | the retained status document and the admin wire |
| `+/state`, `+/connection` | the fleet's view of each truck, and the loss gate's own event |
| `+/order`, `+/instantActions` | **kept deliberately**: Gate 6 claims no order publish falls inside any Motor onset window, and that claim cannot be made from a capture that did not record them |

**Dropped: `/fN/auto/goal`, `/fN/auto/route`, and the MQTT `factsheet` and
`visualization` topics.** goal and route are low-rate and every fact they
carry is also in the fleet log and in `auto/state`'s own `route` field;
factsheet and visualization have never been read by a gate in this file.

**THIS RUN IS INSTRUMENTED MORE THINLY THAN M6.1-M6.4, AND WHAT THAT
LIMITS IS WRITTEN HERE RATHER THAN DISCOVERED LATER.** With `auto/goal`
gone, a claim of the form *"no HMI goal was published by anything at any
point"* - which M6.5's Gate 2 and Gate 6 both made - cannot be made from
this capture. With `auto/route` gone, the route a truck was given can be
read from `auto/state` and from the fleet log but not from an
independent third record. No other claim in this file loses anything.

### The floor, measured twice before a single transport

Four stacks up, four writers streaming, all four trucks **standing
still**, the reduced recorder set running:

```
floor-1   537 samples   printed mean 0.341   min 0.013   integrated 0.345
floor-2   539 samples   printed mean 0.354   min 0.008   integrated 0.343
```

**0.008.** The acceptance run above died at a floor of 0.010, with the
trucks driving and eight more subscriptions. This is worse, with nothing
moving.

### And the recorder is not the reason, which is the finding

Both recorders were then stopped and the same window taken again on the
same stack:

```
no-recorders   567 samples   printed mean 0.477   min 0.019   integrated 0.480
```

| | integrated | floor |
|---|---|---|
| no recorder at all | **0.480** | 0.019 |
| the reduced set the gates need | **0.343** | **0.008** |
| M6.5's gate session, 24 subs, four trucks **driving** | 0.575-0.580 | 0.021 |

Reading those three rows together: **the recorder costs 0.137 of
real-time factor and roughly halves the instantaneous floor** - it is a
real load and cutting it was worth doing - **and it is still not the
binding constraint.** Even with no instrument at all this machine now
gives 0.480 where it gave 0.578 four hours ago, with the trucks idle
instead of driving.

```
$ ps -eo pcpu,etime,args --sort=-pcpu | head -2
 221   05:11   gz sim -s -r --headless-rendering -v 2 ... warehouse_ver2.sdf
$ getconf _NPROCESSORS_ONLN ; cat /proc/loadavg
20
12.98 9.83 7.51
```

**Twenty cores, load 13, and the simulation server pinned at 2.2 of
them.** `gz sim` is not core-starved; it is server-bound, rendering
sixteen gpu_lidars through one pipeline. Adding trucks added lidars
faster than this machine can draw them, and the recorder's 0.137 is the
margin between "slow" and "the scans stop arriving".

**So there is no configuration on this machine tonight that both
instruments the gates and keeps the instantaneous floor above the value
at which the lidars stop delivering.** That is the finding, it is a
number and not an opinion, and it is why Gates 3, 4 and 5 were not
re-run a third time. What it costs to fix is a rig decision - fewer
lidar samples, a lower lidar update rate, a machine with a faster GPU
pipeline, or accepting that a four-truck gate is measured in slow motion
- and every one of those changes a figure already in this file, so none
of them is a thing to do at midnight without the owner.

## The cold machine, and the run it bought

**Owner ruling: the drift you measured is machine state, not our code -
try a cold one.** `wsl --shutdown`, twelve seconds, back up: **load 0.49,
11.4 GB free, uptime 0 min**, and the stray mosquitto from an earlier
session gone with it. Then the same deploy (`source-git: 0c66518`), the
same 39 pids, the same D3D12/NVIDIA renderer read off the server's own
log, and the same reduced recorder set.

### The floor, again, before a single transport

```
cold-floor-1   537 samples   printed mean 0.443   min 0.014   integrated 0.440
cold-floor-2   569 samples   printed mean 0.510   min 0.017   integrated 0.496
```

| | integrated | floor |
|---|---|---|
| warm machine, thinned recorders | 0.343-0.345 | **0.008** |
| warm machine, no recorder at all | 0.480 | 0.019 |
| **cold machine, thinned recorders** | **0.440-0.496** | **0.014-0.017** |
| M6.5's gate session, 24 subs, four trucks driving | 0.575-0.580 | 0.021 |

**A shutdown and twelve seconds bought +0.13 of integrated real-time
factor and doubled the floor.** That is machine state and nothing else -
same code, same stack, same subscriptions. It did not come all the way
back to the band the successful session ran in, which is the middle case
the ruling left to judgement. **The judgement, and why:** the floor is
0.014-0.017 against 0.010 where the last acceptance run died and 0.021
where the last successful one ran; Gate 3 is the shortest gate and has
never been run at four; so Gate 3 first, on the reasoning that if the
rendering was still going to fail it would fail there for four minutes
instead of for twelve.

## [ ] Gate 3 - four-vehicle traffic: 2 of 4, and the first ever completed

Same four crossing transports, same assignment evidence.

```
transports completed   2 of 4      (both by f3: S6->S9 and S7->S8)
travelled              f1 2.9 m   f2 3.7 m   f3 43.7 m   f4 17.6 m
motor-false, AFTER the RESET
                       f3 NONE    f4 NONE
                       f1 and f2 one onset each at 00:03:02
scan faults, whole session
                       every one of them "why": "stale", all at startup
                       before the first scan arrived. ZERO nan, ZERO
                       empty, ZERO muted, ZERO below-min.
```

**Two transports completed in a four-vehicle traffic gate, which has
never happened before**, and **two of the four trucks drove the whole
gate without dropping Motor once**. The step-aside fired again and this
time took the NEAR node - f2 from `(0.0,-5.5)` to `(3.0,-5.5)`, 3.00 m,
which is what ASIDE_MAX_M is for; the eleven-metre connector was
correctly not a candidate.

What stopped the other two is honest and is not a rig fault: f1 drove up
behind f2 on the dock aisle and its **back scanner read 0.927 m** -
`fault` empty, a real body at a real distance - so the protective field
demanded a stop and got one. **Not ticked** (2 of 4 is not 4 of 4), and
the reason is now geometry rather than instrumentation.

## [ ] Gate 4 - the acceptance run: 3 of 8

00:11:56.323 -> 00:11:58.519: eight transports over the ten stations, in
**2.20 s**. Four trucks at their table poses, Motor True, AUTOMATIC,
every field clear. **No operator touched anything from that moment until
00:29:00.**

### The headline, measured over 1024 s (00:11:56 -> 00:29:00)

| | |
|---|---|
| transports completed | **3 of 8** - `S1->S6` (f1), `S5->S9` (f4), `S2->S8` (f3) |
| **throughput** | **0.176 transports/min** - one every 5.7 minutes |
| per-vehicle utilisation | f1 **25.4 %**, f2 **19.8 %**, f3 **44.4 %**, f4 **11.8 %** of samples moving |
| distance travelled | f1 37.7 m, f2 31.0 m, f3 60.6 m, f4 14.9 m - **144.2 m** |
| bounding boxes | f1 11.32 x 12.91 m, f2 9.52 x 14.29 m, f3 13.02 x 13.47 m, f4 8.37 x 1.41 m |
| **total stopped time** | **3,057.7 vehicle-seconds** of 4,096 capacity (75 %) |
| arrival errors | 0.0000 (S1), 0.2481 (S4), 0.2450 (S5), 0.7893 (S9), 0.7972 (S6), 0.7996 (S2), 0.7982 (S8) - **every one inside its station's own `arrive_m`** |
| motor-false | f1 10,509/20,468; f2 16,443/20,467; f3 9,206/20,468; f4 17,983/20,422. **One onset each** |
| **full-stack RTF** | printed **0.472-0.542**, integrated **0.468-0.549**, **floor 0.020-0.033**, six consecutive 60 s windows |

**Read the utilisation with the boxes this time, and it says something
different from last time.** The M6.5 gate run's 99 % was seventy metres
inside a 1.57 x 1.95 m box - orbiting. These boxes are eleven to
thirteen metres on a side: f1, f2 and f3 crossed the hall. Only f4's
1.41 m in `y` is a truck that went out and came back on one aisle. The
travel is real.

**The RTF is the number that changed everything.** 0.468-0.549
integrated with a floor of **0.020-0.033**, against 0.445-0.523 and a
floor of 0.010 on the warm machine four hours earlier. That floor is the
whole difference between this run and the last one.

### The four Motor onsets, each named - and this is what the new branch bought

```
f1 00:20:14.582  WARN SAFE PROT   1.425  2.812  0.000   enc 0/0
                 fault: right {"why": "stale"}
f2 00:15:17.888  SAFE PROT WARN   2.960  0.979  1.607   enc -157/-157
                 fault: none - a real body at 0.979 m
f3 00:21:19.718  PROT PROT WARN   0.000  0.000  1.706   enc 0/0
                 fault: back and left {"why": "stale"}
f4 00:14:01.094  WARN WARN SAFE   1.911  1.948  3.007   enc 0/0
                 fault: none - two warning fields, the speed monitor
```

**Two honest protective stops on real geometry, and two scans that never
arrived inside `SCAN_STALE_S`.** Before this session all four would have
read as `d: 0.000` and been indistinguishable. **Not one of them is
`nan`, `empty`, `muted` or `below-min`** - which is the branch the mass
latch of the previous run fired on. A dropped scan and a half-rendered
buffer are different faults with different fixes, and this fleet can now
tell them apart on the wire, at 10 Hz, with no new topic and no new
subscription.

**Not ticked.** Three of eight is not an acceptance run. What it is, is
the first four-vehicle run in this ledger where every truck did real
work, every arrival landed inside its own radius, and every stop has a
name.

## [ ] Gate 5 - degradation under loss: NOT RE-RUN

The acceptance run ended with three trucks stopped on protective demands
and no operator budget left in the session. A kill measured against a
fleet that is already stopped is worth nothing. M6.5's own Gate 5 result
stands: three clauses of four.

## Teardown

Writers first (four `{"quit": true}`), then the ROS recorder printing its
session counts - **30,429 encoder samples and 15,216 field reports on f1
alone** - then the MQTT recorder, then `./m6.sh stop`: all eight vehicle
ports and 1883 free, no orphan, `.m6_pids` removed. `Get-Process python`
afterwards returns three VS Code language servers from two days ago and
nothing else. Suites after teardown: m6 **480 passed**, step5 **220
passed**.

Four stacks were started and stopped tonight, each with its own deploy at
its own HEAD; every figure above names the one it came from.

---

# What Milestone 6 claims, and what it does not

**Rewritten 2026-08-23 after the fix-up sessions.** Every claim below
points at the gate that measured it by name. Every claim withheld points
at the run where it failed. Three acceptance-run attempts are in this
file and all three are kept: 1 of 8, 0 of 8, and 3 of 8.

**FIRST, THE INSTRUMENT.** The last two runs were recorded on a REDUCED
recorder set - 20 ROS subscriptions instead of 28, and four named MQTT
topics instead of `uagv/v2/amragent/+/#` - because the recorder costs
0.137 of real-time factor and this rig had none to spare. `/fN/auto/goal`
and `/fN/auto/route` are gone, and with them **one claim M6.5 could make
and this file no longer can: that no HMI goal was published by anything
at any point.** The fleet log and `auto/state`'s own `route` field carry
everything else those two topics did. Every other claim below is
unaffected, and where a claim rests on a topic that was dropped it is
not made.

## What it claims

1. **Four simulated forklifts, each with its own complete safety chain,
   run concurrently on one machine at about half of real time.**
   Thirty-nine processes, sixteen safety lidars subscribed and
   rendering. The best measurement is M6.5 Gate 4's - integrated
   **0.575-0.580** over six consecutive 60 s windows, within 0.005 of
   each other. The 2026-08-23 acceptance run measured **0.468-0.549** on
   the same stack with a lighter recorder, and a warm machine four hours
   earlier measured **0.343**. **The spread is machine state, not
   code**, and the number to quote is a band and not a point.
   **Conditional on `GALLIUM_DRIVER=d3d12` and
   `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA` in the shell that starts the
   world** - see the first residual.

2. **A VDA 5050 fleet manager assigns, sequences and completes
   transports over ten stations with no operator in the loop.** Every
   transport in this file was submitted through `fleet_cli.py` and
   turned into orders by `fleet_manager.py`; `tools/send_order.py` was
   not used once. *M6.3 Gates 1-6, M6.5 Gate 2, and the 2026-08-23
   acceptance run, where eight transports were submitted in 2.20 s and
   three completed with no operator input for seventeen minutes.*

3. **Arrival is inside the radius the station itself declares.** Seven
   arrivals in the 2026-08-23 run: 0.0000, 0.2481, 0.2450, 0.7893,
   0.7972, 0.7996, 0.7982 m - **every one inside its own station's
   `arrive_m`**, and the four at 0.79 are the short-spur stations that
   declare 0.80 for the reason `stations.py` gives.

4. **Edge/node reservation hands a spur station from one vehicle to
   another without the floor ever going free between them.** *M6.5 Gate
   2: `FREE -> f3`, `f3 -> f1`, `f1 -> FREE` on the retained
   `fleet/status`, never free between the two vehicles.*

5. **A truck that cannot yield is moved, and the deadlock clears.**
   Wait-die frees the floor AHEAD of a vehicle; where the contested
   element is the ground UNDER one, the fleet cancels the younger truck,
   requeues its task and sends it a one-node `ft-` order to a free
   neighbour - through the same builder, the same validation and the
   same publish funnel as any leg. *Fired unprompted in three separate
   live runs; 2 ms from detection to `cancelOrder`, 104 ms to the order,
   accepted through the vehicle's own door.*

6. **The safety chain is untouched by anything the fleet does.** *M6.5
   Gate 6: nine Motor onsets in 67 minutes, every one named at its own
   sample, and 0 of the session's 157 order/`instantActions` publishes
   inside any of the nine +/-2 s windows.* The 2026-08-23 run adds four
   more onsets, each named, and none correlated with an order.

7. **A lost vehicle costs its task and nothing else, within 132 ms.**
   *M6.5 Gate 5: detection 131 ms, reassignment 132 ms, no QUEUED
   interval, and the dead truck never appears in a `nearest idle` list
   again.*

8. **A 0.000 on a safety scanner says which of five faults produced
   it.** empty array, all-muted, `nan` with a ray count, `-inf` with a
   ray count, or no scan at all inside `SCAN_STALE_S` - carried on the
   existing 10 Hz `/fN/safety/fields` message, diagnosis only, with the
   verdict proven byte-identical against a transcription of the code
   that stood before it. *The 2026-08-23 run's four onsets separate into
   two real bodies and two stale scans on that field alone.*

9. **The code was already N-generic and M6.5 proved it rather than
   claiming it.** Four vehicles came from one table entry each.

## What it does not claim

1. **It does not claim four trucks can work this floor together.** The
   best acceptance run in this file is **3 of 8**, at 0.176
   transports/min, with 75 % of fleet capacity spent stopped. Gate 3 is
   2 of 4 at best. **An unticked gate is not a passed one**, and three
   attempts are written up here rather than one.

2. **It does not claim the reservation ledger prevents collisions, and
   it never has.** RESERVATION IS PROCESS DECONFLICTION AND NEVER A
   COLLISION CLAIM. Nothing in `fleet/` stops a truck. The scanners, the
   F-model and the on-board guards are the only things that do, exactly
   as before traffic existed; what the ledger buys is that the fleet
   never ASKS two vehicles onto one piece of floor. Every stop in the
   2026-08-23 run was a scanner's, not the ledger's - which is that
   division of labour working, and also the proof that the ledger is not
   the thing keeping the trucks apart.

3. **It does not claim a throughput number worth planning against.**
   0.176 transports/min is one floor, one route set, one afternoon, and
   the fleet spent three quarters of it stopped.

4. **It does not claim the vehicle software is safety software.** No
   Category, no Performance Level, no SIL, no PFH. One process per
   evaluation, one scan source per device, no redundancy, no test
   pulses.

5. **f2, f3 and f4 have never run against a real PLC program.** There is
   one PLCSIM Advanced licence and no instance for this rig, so all four
   trucks in every four-vehicle run here ran `--virtual`, against
   `virtual_fplc.py`. **Only f1 has ever been driven against the real
   validated F-program**, in step5 and M6.1. The virtual model
   reproduces measured behaviour and owner rulings and claims no safety
   integrity; a four-truck figure is a figure about the model.

## The open residuals, and where each was measured

1. **The four-truck figures depend on a GPU that is not configured.**
   `GALLIUM_DRIVER=d3d12` and `MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`
   are **still not in `~/.bashrc`** - checked at 18:55, at 22:00 and
   again at 23:56. Every RTF number here was produced by exporting them
   by hand, and a run started from a shell without them measures a
   different machine and does not say so. **Fifth session in which this
   is true.**

2. **The rig is now the binding constraint and it is quantified.** The
   recorder costs **0.137** of integrated real-time factor; a warm
   machine costs another **0.13** on top; `gz sim` sits at 221 % of
   twenty cores, server-bound, rendering sixteen gpu_lidars through one
   pipeline. At a floor of 0.010 the scans stop arriving and every field
   evaluator correctly fails safe at once - **that is what ended the
   0-of-8 run**. At 0.020-0.033 they arrive. The fix is a rig decision
   and every option moves a figure already in this file.

3. **f1 parks ON S1, which 42 of the 90 routes touch.** It costs a
   latch: a truck approaching S1 at cruise puts its fork corners 2.33 m
   off f1's parked body, the warning field drops, and the speed monitor
   demands a stop. The pose is kept because moving it invalidates every
   step5 and M6.1-M6.4 figure measured from it. **This is an owner call
   and it is named, not changed.**

4. **The main aisle runs at 0.30 m/s, not 0.70.** The aisle gives a
   fork-corner scanner **2.79 m** of lateral clearance against a 2.70 m
   re-clear threshold - nine centimetres - so the speed policy holds the
   truck at the creep ceiling for the whole of every main-aisle transit
   rather than let the field take `V_Limit` away under wheels doing
   0.7 m/s. **Owner call, named not changed.** The real fix is the
   floor.

5. **A restarted manager adopts a driving truck by waiting, and does
   not reserve the base that truck is already on.** *M6.3 Gate 5.* The
   floor under an adopted vehicle is its standing node and nothing more.

6. **The minimum-turning-radius orbit still eats arrivals.** A vehicle
   cannot reach a point inside its own turning circle; the short-spur
   stations declare 0.80 m for that reason, and the 2026-08-23 run's
   four 0.79 m arrivals are that number being spent in full.

7. **Two drive-wheel stalls have no explanation.** f4 at the S4 corner
   with the steer joint at -0.926 rad, and f3 on the main aisle with the
   steer at -0.061 - straight ahead - both with traction commanded at
   -2.5 rad/s and a drive-wheel velocity of 8e-5. The joint-state stream
   was sampled by hand, not recorded, and that is what the next attempt
   needs.

8. **A parked hulk is only parked where the ledger last saw it.** With
   no agent alive nothing publishes an empty goal, so nav drove a dead
   truck **8.48 m across a junction** while the ledger's pin stayed
   7.2 m behind it. *M6.5 Gate 5.*

9. **Wait-die cannot free the floor UNDER a vehicle**, which is why the
   step-aside exists. Where no free neighbour is within `ASIDE_MAX_M`
   the answer is still a named refusal and a person with a panel, and
   that is the honest floor.

10. **A protective demand latches, and the fleet cannot clear it.** Only
    a panel RESET does. An acceptance run has no operator in it by
    definition, so one latch costs a truck for the rest of the run - and
    in the 0-of-8 run, four latches inside 0.56 s cost all of it.

11. **The deadlock a physical body causes is invisible to the ledger**,
    by construction. A truck held by nav's obstacle guard holds no
    reservation and appears in no wait-for cycle; the fleet cannot see
    it and does not pretend to.


# The owner's runbook

Every gate in this file is now measured, so nothing below is owed. The
runbooks are kept because a machine run is not a hands-on run: the owner
re-proving any of these on the real panels, with a real joystick, is
still worth doing, and this is how.

Each gate below is a numbered list. **One action per step.** Do them in
order, do not skip the setup, and write the numbers you record straight
into the gate's section above.

**CORRECTED 2026-08-23, and the correction is itself the lesson.** These
steps were written against `m5_ver2/step6` when the fleet was two trucks
and the stack was seventeen processes. The tree is now `m6/` and the
fleet is four, so every path, every script name and every count below
was stale — and two steps were worse than stale. Gate 4 said "run
`sed -n '7p' .step6_pids`, that line is `sensor_link_f1`", and Gate 6
said line 4 is `cmd_mux_f1`. Both counted lines in a pidfile laid out for
two vehicles. Followed today, on a pidfile laid out for four, they hand
you **a pid belonging to a different node** — and the very next
instruction is `kill`. A line number in a pidfile is not an identity. It
is gone from this runbook: every process below is found by asking the
process itself which vehicle it belongs to.

The lookup is written the way it is for a reason worth one sentence.
`pgrep -f sensor_link.py` alone **also matches the shell you typed it
into**, because that pattern is sitting in that shell's own command line
— measured 2026-08-23, it returned a third pid with no vehicle at all.
So the pattern anchors on `python3.*` and the loop prints only processes
that actually carry a `VEHICLE`, which drops both the self-match and the
fleet manager (which has no vehicle by design).

**GPU FIRST.** Every real-time-factor figure in this file was measured
with these two variables set, and they are still not in `~/.bashrc`.
Export them in the shell you start the world from, or you are measuring a
different machine than the one this file describes:
`export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`.

**The gates below are M6.1's, and they are two-truck gates.** The floor
now starts four. f3 and f4 sit at their table poses, enabled and idle,
and take no part — that is expected, not a fault. Leave them running.

## Setup — do this once, before any gate

1. Open a WSL terminal.
2. Run `export GALLIUM_DRIVER=d3d12 MESA_D3D12_DEFAULT_ADAPTER_NAME=NVIDIA`.
3. Run `cd /mnt/c/Users/ozkan/projects/amr-agent/m6`.
4. Run `./m6.sh deploy`. It must print `deployed 31 files`.
5. Run `./m6.sh start`. (Leave off `--headless`: you want the Gazebo window for gates 2 and 3.)
6. Count the pid lines it printed. There must be **39**.
7. Check no line says `exited during startup`. If one does, open that log in `logs/` and stop here.
8. Look at the screen: **four HMI windows**, titled `Forklift HMI - f1` through `Forklift HMI - f4`.
9. Open a Windows terminal (cmd or PowerShell).
10. Run `cd C:\Users\ozkan\projects\amr-agent`.
11. Run `python m6\windows\m6.py --vehicle f1 --virtual`.
12. Check its console prints `VIRTUAL F-PLC (model) - PLCSIM Advanced is not in this loop`, then `streaming PLC state to <wsl-ip>:5110` and `listening for the back scanner on 0.0.0.0:5111`.
13. Leave that window open. Open a **second** Windows terminal, `cd` to the same place, and run the same command with `--vehicle f2`. Its two ports must read **5120** and **5121**.
14. Open a **third** Windows terminal and run it with `--vehicle f3`. Ports **5130** and **5131**.
15. Open a **fourth** Windows terminal and run it with `--vehicle f4`. Ports **5140** and **5141**.
16. Look at the four panels, each titled `Forklift fN PLC Control Panel - VIRTUAL F-PLC (model)`.
17. Click **RESET** once on each of the four panels. Every lamp must read `MOTOR ENABLED`.
18. Check all four HMI lamps are neutral and every one reads `Drive enable: ON`.

**All four trucks are now enabled.** Every gate below starts from here
and uses f1 and f2 only.

### Teardown — do this at the end of every session

1. Close all four panel windows.
2. In the WSL terminal run `./m6.sh stop`.
3. Check the last line is `down.`

## Gate 2 — cross-isolation, both directions

Run the setup first. This gate is run twice: once F1→F2, then mirrored.

1. Open a third WSL terminal.
2. Run `source /opt/ros/jazzy/setup.bash`.
3. Run `export ROS_DOMAIN_ID=96`.
4. Run `ros2 topic echo /f2/plc/status std_msgs/msg/String > /tmp/g2_f2_status.txt` and leave it running.
5. Open a fourth WSL terminal.
6. Run `source /opt/ros/jazzy/setup.bash`.
7. Run `export ROS_DOMAIN_ID=96`.
8. Run `ros2 topic echo /f2/safety/fields std_msgs/msg/String > /tmp/g2_f2_fields.txt` and leave it running.
9. On **f1's** HMI, drag the joystick forward so f1 drives toward the nearest rack face.
10. Watch f1's panel lamp. When it flips to `MOTOR STOPPED`, f1's protective field has tripped.
11. Release f1's joystick (let it spring back to centre).
12. Wait five seconds.
13. Press Ctrl-C in the third WSL terminal.
14. Press Ctrl-C in the fourth WSL terminal.
15. Run `grep -c '"motor": false' /tmp/g2_f2_status.txt`. **Record this number. The gate wants 0.**
16. Run `grep -c '"motor": true' /tmp/g2_f2_status.txt`. Record it — this is the sample count the zero above is out of.
17. Run `grep -c '"pf": false' /tmp/g2_f2_fields.txt`. **Record this number. The gate wants 0** — `pf` is the protective field and `false` means tripped, so a zero says f2's three scanners never saw f1's obstacle.
18. Look at f1's HMI: lamp red, `Drive enable: OFF`. Record that it latched.
19. Click **RESET** once on f1's panel to heal it.
20. Now mirror the whole thing: repeat steps 1-19 with `f1` and `f2` swapped everywhere (echo `/f1/...`, drive **f2** into a rack).
21. Write both directions' numbers into the Gate 2 section above.
22. Tick Gate 2 only if **both** directions recorded 0 and 0.

## Gate 3 — simultaneous autonomy

Run the setup first. Start the recording BEFORE you press GO.

1. Open a third WSL terminal.
2. Run `source /opt/ros/jazzy/setup.bash`.
3. Run `export ROS_DOMAIN_ID=96`.
4. Run `ros2 topic echo /f1/plc/status std_msgs/msg/String > /tmp/g3_f1.txt` and leave it running.
5. Open a fourth WSL terminal.
6. Run `source /opt/ros/jazzy/setup.bash`.
7. Run `export ROS_DOMAIN_ID=96`.
8. Run `ros2 topic echo /f2/plc/status std_msgs/msg/String > /tmp/g3_f2.txt` and leave it running.
9. On **f1's** HMI, click the `Auto` radio button.
10. On f1's warehouse sketch, click a station dot on the far side of the map. It turns orange.
11. Press **GO** on f1's HMI. A dashed route appears and f1 starts driving.
12. Immediately go to **f2's** HMI and click its `Auto` radio button.
13. On f2's sketch, click a **different** station dot.
14. Press **GO** on f2's HMI.
15. Look at the Gazebo window and confirm **both trucks are moving at the same time**. That overlap is the gate; if f1 already arrived, stop and rerun with a longer route for f1.
16. Wait until f1's HMI state line reads `ARRIVED`. Record the arrival error it prints, in metres.
17. Wait until f2's HMI state line reads `ARRIVED`. Record its arrival error too.
18. Press Ctrl-C in the third WSL terminal.
19. Press Ctrl-C in the fourth WSL terminal.
20. Run `grep -c '"motor": false' /tmp/g3_f1.txt`. **Record it. The gate wants 0.**
21. Run `grep -c '"motor": false' /tmp/g3_f2.txt`. **Record it. The gate wants 0.**
22. Compare both arrival errors against step5's bar in `m5_ver2/step5/PROOF.md`.
23. Write all four numbers into the Gate 3 section above.

## Gate 4, driving half — one link dies, the other truck drives on

Run the setup first. This kills f1's `sensor_link` while f2 is driving.

1. In the WSL terminal, run `for p in $(pgrep -f "python3.*sensor_link\.py"); do v=$(tr '\0' '\n' < /proc/$p/environ | sed -n 's/^VEHICLE=//p'); [ -n "$v" ] && echo "$p $v"; done`. It prints four lines, one per truck, each `pid vehicle`.
2. Write down the pid on the line that ends in **`f1`**. Read it off the vehicle name, never off a line number — see the correction at the top of this runbook.
3. Open a third WSL terminal.
4. Run `source /opt/ros/jazzy/setup.bash`.
5. Run `export ROS_DOMAIN_ID=96`.
6. Run `ros2 topic echo /f2/plc/status std_msgs/msg/String > /tmp/g4_f2.txt` and leave it running.
7. On **f2's** HMI, drag the joystick forward and hold it. f2 drives.
8. While f2 is still driving, run `kill <the pid from step 2>` in the WSL terminal.
9. Watch f1's panel lamp: it must flip to `MOTOR STOPPED` within about a second. The writer's own timeout is `SENSOR_STALE_S` 0.40 s + `CYCLE_S` 0.02 to writing the six field inputs False, and the F-program's chain (< 0.45 s from the demand) runs AFTER that one, not beside it.
10. Watch f1's HMI: it must go red, `Drive enable: OFF`.
11. Check f2 is **still driving** under your joystick. That is the gate.
12. Release f2's joystick.
13. Press Ctrl-C in the third WSL terminal.
14. Run `grep -c '"motor": false' /tmp/g4_f2.txt`. **Record it. The gate wants 0.**
15. Record how long f1 took to drop (a stopwatch is enough). The writer's half of that budget is `SENSOR_STALE_S` 0.40 + `CYCLE_S` 0.02 < 0.42 s to writing the inputs False; the F-program's chain is the other half.
16. Note that f1 stays down: `kill` removed the node, so nothing will heal it. Run `./m6.sh stop`, then the setup again, before any further gate.
17. Write the numbers into the Gate 4 section above.

## Gate 6 — kill the mux under Motor True

Run the setup first. This is the step4 14.8 m class, tested on purpose.

1. In the WSL terminal, run `for p in $(pgrep -f "python3.*cmd_mux\.py"); do v=$(tr '\0' '\n' < /proc/$p/environ | sed -n 's/^VEHICLE=//p'); [ -n "$v" ] && echo "$p $v"; done`. It prints four lines, one per truck, each `pid vehicle`.
2. Write down the pid on the line that ends in **`f1`**.
3. Open a third WSL terminal.
4. Run `source /opt/ros/jazzy/setup.bash`.
5. Run `export ROS_DOMAIN_ID=96`.
6. Run `ros2 topic echo /f1/gz/odom > /tmp/g6_odom.txt` and leave it running.
7. On **f1's** HMI, drag the joystick forward and hold it so f1 is driving at a steady speed.
8. While f1 is still driving, run `kill <the pid from step 2>` in the WSL terminal.
9. Watch f1 in the Gazebo window. It must stop.
10. Release f1's joystick.
11. Press Ctrl-C in the third WSL terminal.
12. Run `grep -A2 'position:' /tmp/g6_odom.txt | grep -E '^ +(x|y):' | paste - - | cat -n > /tmp/g6_xy.txt` — one numbered `x  y` pair per odometry sample, 20 per simulated second.
13. Open `/tmp/g6_xy.txt`. Find the last pair before the numbers stop changing (that is where f1 came to rest) and the pair from the moment you killed the mux, and record the straight-line distance between them.
14. **The gate wants that distance to be a `CMD_STALE_S`-sized coast: 0.25 s of travel plus a tick, so 0.35 s.** At the 300 mm/s creep limit that is 0.105 m; at the 2800 mm/s ceiling, **0.98 m** (this line read "under 0.8 m" until 2026-08-21, which was an arithmetic slip and is corrected here). The formula counts the stale window only — the drive's braking ramp is on top of it. Anything in step4's 14.8 m class is a FAIL.
15. Check f2's HMI: it must be unaffected, still `Drive enable: ON`.
16. Run `./m6.sh stop` — f1's mux is gone and the stack is now incomplete.
17. Write the distance into the Gate 6 section above.

---

# M6.6 — the floor rebuilt, and the four things it took to find out why

**Date:** 2026-08-23. **Verdict: the gate is 2 of 6 and is NOT ticked.**
Every number below is a capture off this machine, and the two criteria
that pass are stated no more loudly than the four that do not.

## The run

`fleet_cli.py demo --duration 600 --in-flight 4 --seed 7`, four trucks,
`m6.sh start --headless`, four `scripted_writer --auto-reset` on the
Windows side, `tools/record_overhead.py` on the camera and
`tools/score_run.py` on the four `/fN/gz/odom` topics. No panel was
opened and no station was clicked; the three HMI actions were published
on the topics `hmi_node.py` publishes, at the QoS it declares.

## The six criteria, measured

| # | Criterion | Measured | |
|---|---|---|---|
| 1 | fleet distance ≥ 800 m in 10 min | **404.4 m over 630 s** | [ ] |
| 2 | ≥ 12 transports completed | **4 done, 9 submitted** | [ ] |
| 3 | every truck moves in every 2-min window | **all four, all six windows** | [x] |
| 4 | every arrival inside its own `arrive_m` | **9 arrivals, no station approached twice** | [x] |
| 5 | integrated RTF ≥ 0.40, floor ≥ 0.020 | **0.578 / 0.021 server-only; live scan rate 5.03 Hz, worst gap 0.528 s** | [ ] |
| 6 | auto-RESET recoveries ≤ 4 | **15 — f1 3, f2 6, f3 2, f4 4** | [ ] |

Per truck: f1 115.4 m, f2 88.5 m, f3 104.7 m, f4 95.8 m.

**Criterion 1 is a fail and it is still the headline.** The M6.5
acceptance run moved 144.2 m in 1024 s; this one moved 404.4 m in 630 s,
which is **2.8x the distance per second**. The 800 m bar was written
against a rig running at real time and this one runs at about half, so
the bar was wrong rather than the floor. It is left as written and
failed rather than moved, because a criterion edited after the run is
not a criterion.

**Criterion 5's live half is the honest worry.** `field_eval` calls a
scan older than `SCAN_STALE_S` (0.50 s) a violated field, and the worst
gap measured on this run was 0.528 s. That is why criterion 6 reads 15:
most of those recoveries are a scan that arrived 28 ms late, not a truck
that drove into something.

## The four defects the floor had, and how each was found

None of these came from reading the code. All four came from running it
and reading what the plant said.

**1. The overhead camera filmed a quarter turn.** A gz camera looks down
its own +X with image-right at -Y, so pitch alone put image-right on
world -Y and image-up on world +X — and because `horizontal_fov` sizes
the WIDTH, the hall's 48 m X extent was squeezed into the 36 m the short
axis covers. Both ends of the floor were cropped and trucks drove out of
frame. Yaw = +pi/2. The pose came from the M6.6 plan, so the plan was
wrong the same way.

**2. Dressing the floor cost the scanners their rate.** RTF is the wrong
instrument for it: gz sim renders the whole scene once PER SENSOR, so
scene complexity is multiplied by sixteen gpu_lidars.

    bare world      62 models   4.22 Hz per scanner, worst gap 0.316 s
    dressed        340 models   0.76 Hz per scanner, worst gap 2.556 s

All four trucks went into a permanent protective stop inside a minute
and stood at their spawn poses for 245 s with orders, reservations and
no motion — and nothing in any log said anything was wrong, because
nothing was. The decoration is now spent to a model budget: 33 models,
5.03 Hz.

**3. A pocket is not a place to park this vehicle.** The pick bays faced
the 5.00 m pick aisle and a tricycle with a 1.29 m minimum turning
radius could not line one up: f1 stopped at (-13.35, 3.59) and f2 at
(6.65, 3.60), each inside its own bay with the BACK protective field
violated and neither recoverable. Turning the bays to face the 8.00 m
ring was not enough — the next run had f2 and f3 stopped at their
stations reading **back 0.980, left 1.698, right 1.548**, identical to
three decimals because the bays are identical and the pursuit is
deterministic. The lateral fit was fine. The truck is about 2.80 m long
and needs 1.20 m clear ahead, so a pocket must be over 4.00 m deep and a
3.50 m rack row cannot give one. **There is no depth that works.** The
gap is cut right through the row instead, ring to pick aisle, and the
station sits in the middle of an open CROSS-AISLE.

**4. And the cross-aisle was three centimetres too narrow.** With the
protective stops gone, f2 and f3 still stood still — Motor TRUE, every
field clear, wheels at zero:

    f3  state HOLD  guard_min 1.4722 m  reversing True
    f2  state HOLD  guard_min 1.4846 m  reversing True

`follower.GUARD_HOLD_M` is 1.500. The nav lidar sits 0.40 m off centre,
so reversing out of a 4.00 m gap it reads the wall just inside the band
and the autopilot holds, exactly as it should. **A follower constant may
not move for a floor.** It would have been one character to make it 1.4.
The gaps are 5.00 m: 2.10 m at the nav lidar, 2.04 m at a safety
scanner.

## What the recording shows

`assets/m6-fleet/m6-fleet-05-cross-aisle-floor-2026-08-23.mp4` — 154 s
of overhead video from a 630 s run (the camera delivers at the plant's
rate, so a slow rig makes a shorter film rather than a smoother one).
Four trucks working a 48 x 32 m floor: a closed ring at 0.70 m/s, a
spine through the middle, one creep aisle, twelve stations in open
cross-aisles, and a dock annex with four bays.

## Still open after this

* **The 800 m bar and the 12-transport bar are rig-bound, not
  floor-bound.** At an RTF of about 0.5 and a longest leg of 60.65 m a
  transport costs three to four wall minutes, so ten minutes of wall
  clock cannot hold twelve of them at four trucks.
* **The worst scan gap is 0.528 s against a 0.500 s rule.** Every
  auto-RESET in criterion 6 traces to that. The rig is still the binding
  constraint and it is the same residual M6.5 closed with.
* **The hall reads emptier than the dressed version did.** Widening the
  cross-aisles to 5.00 m shrank the rack segments to 0.50-1.00 m
  slivers, and the loads on top of them shrank with them. The owner's
  first note on the M6 recording was that the hall looks empty; it is
  better than it was and it is not fixed.
* **No GUI take was recorded.** The plan asked for a second, shorter
  take with the Gazebo window open on the same seed. It is not here.

---

# M6.7 — a truck that can get itself out, and a fleet that notices

**Date:** 2026-08-23. **Verdict: the gate is 4 of 5 and is NOT ticked.**
The one that fails is the one this work was least about, and it is
written down as measured.

## The run

`fleet_cli.py demo --duration 600 --in-flight 4 --seed 7`, four trucks,
headless, four `scripted_writer --auto-reset`, the overhead camera and
`tools/score_run.py` on the four odometry topics. Video:
`assets/m6-fleet/m6-fleet-06-recovery-2026-08-23.mp4`.

## The five criteria, measured

| # | Criterion | Measured | |
|---|---|---|---|
| 1 | no truck stands still past `STALL_GIVE_UP_S` without the fleet naming it | **held** — the one long stop was a ledger wait and was correctly not named | [x] |
| 2 | every stall ends: self-cleared or requeued, no transport lost | **held** — six give-ups in the blocker experiment, every task reassigned | [x] |
| 3 | `recover(body)` and `recover(starvation)` reported separately | **3 body, 0 starvation** (M6.6: 15, undifferentiated) | [x] |
| 4 | more than four transports complete | **4** — the same as M6.6 | [ ] |
| 5 | suite green, 0 skipped | **552 passed** | [x] |

Distance 365.3 m over 630 s, against M6.6's 404.4. Per truck: f1 103.1,
f2 88.5, f3 88.8, f4 84.9. Every truck moved in every two-minute window.

**Criterion 4 fails and it is the one this work was not about.** The rig
runs at about half real time and the longest leg is 60.65 m, so a
transport costs three to four wall minutes; ten minutes at four trucks
cannot hold twelve of them. The bar is left where M6.6 wrote it.

## What the watchdog did, and what it deliberately did not

**IT STAYED QUIET THROUGH A 250-SECOND STOP, AND THAT IS THE RESULT.**
f4 stood still from 23:34:49 to 23:38:59. The fleet log says why:

    23:34:49  f4 gets 4 of 13 nodes to S9 as base and 9 as horizon -
              the rest of the corridor is taken
    23:38:59  base extended to 6 released as orderUpdateId 1
    23:39:02  base extended to 13 released as orderUpdateId 2
    23:41:22  f4 completed ft-1f8078cb at S9

`floor.waiting_on("f4")` was set for all of it, so `_stall_pass`
excluded the truck and wrote nothing. A watchdog that named that stop
would put a word on the operator's screen every time traffic worked, and
a screen that cries wolf is a screen nobody reads.

**AND IT FIRED SIX TIMES WHEN A BODY WAS PUT IN AN AISLE.** With a
1.00 x 1.00 x 1.20 m obstacle spawned into the north ring leg at runtime:

    23:50:25  f1 is not moving - under 0.50 m in 90 s while executing
              ft-06d1d574. The task goes back to the queue and the truck
              stands down until its own state says it is idle
    23:50:25  f1 is cancelled on ft-c15604a3
    23:51:55  assigned ft-06d1d574 to f2 (nearest idle to S4)

The task was taken back, the order cancelled on the wire and the
transport given to another truck. On the M6.6 build the same jam showed
as `ASSIGNED_LEG2` for as long as anyone watched.

**RETRO-SCORED AGAINST M6.6's OWN RUN**, `score_run`'s new column says
f2 stood still for 107.0 s and f4 for 106.2 - both past
`STALL_GIVE_UP_S`, both while the per-window table read "every truck
moved in every window". That table was true and useless; this one is
not.

## The escalation was not exercised, and the honest reason

`HOLD -> AVOID -> NUDGE -> BLOCKED` is implemented and has eleven unit
tests on it. **In 630 s of driving it never fired.** The states sampled
off `/fN/auto/state` were 12 EN-ROUTE, 7 ARRIVED and 1 SAFETY-STOP -
not one HOLD. The M6.6 floor no longer produces the stall the escalation
was written for, which is the right outcome and is not evidence that the
escalation works.

The blocker experiment did not close that gap either. Two obstacles were
spawned; the first was placed on a corridor no truck then drove, and the
second was 0.80 m off the centreline, which put it inside the guard's
slow band (the truck read 2.56 m and slowed) but outside its hold band.
The one HOLD recorded all evening came with `guard=0.0` - a stale scan,
not a body.

**So the escalation's field behaviour is UNMEASURED.** What the
experiment did prove is the watchdog, and it proved it by accident: the
body is invisible to the traffic ledger (`PROOF.md` residual 11, which
M6.7's spec put explicitly out of scope), so the fleet went on routing
trucks into a node they could not pass, and the watchdog is the only
reason the cell did not silently stop.

## Two defects the tests found before the rig did

**A nudge measured only in metres never ends.** A wedged truck never
covers `NUDGE_M`, so it stays in `NUDGE` for ever - the state machine
growing exactly the dead end it was built to remove. `NUDGE_TIMEOUT_S`
closes it, and a nudge that ran out of time still counts against
`NUDGE_MAX`: a truck that cannot execute the move is the truck that
should stop being asked to.

**A dwelling truck is not moving either**, and it is doing precisely
what it was told. The fork cycle is 3.0 s against a 30.0 s window so it
cannot trip the watchdog - but that is arithmetic between two files, and
there is now a test on it. Lengthen the dwell past the window and every
fork cycle in the cell becomes a name on the screen.

## Still open

* **The escalation needs a rig test that actually reaches a truck.** The
  obstacle has to be inside `GUARD_HOLD_M` (1.50 m) of the nav lidar's
  travel cone, which means on the centreline and not beside it, with
  free floor to one side. Both of tonight's placements missed.
* **A physical body is still invisible to the ledger.** Residual 11,
  unchanged and now demonstrated: the fleet routed three trucks into a
  node a box was standing on, and only the watchdog stopped that from
  being permanent.
* **Four transports again.** Rig-bound, not floor-bound and not
  autonomy-bound.
