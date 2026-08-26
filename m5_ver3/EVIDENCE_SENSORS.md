# EVIDENCE — m5-ver3 sensors and wheel odometry, as delivered (F1 Task 4)

Every number below was measured on this rig on **2026-08-25**, and the
instrument that produced it is named beside it. A *datasheet* figure is
labelled datasheet and is not a measurement of anything; a *configured*
figure is what `gazebo/forklift_ver3/model.sdf` asks for; a *measured*
figure came off this plant through a named tool, in a named session. The
three columns are never mixed.

**The rig.** WSL2 on Windows 11 · Ubuntu 24.04.4 LTS · 13th Gen Intel
Core i9-13900H, 20 threads · NVIDIA GeForce RTX 4050 Laptop GPU ·
gz-sim **8.11.0** · ROS 2 **Jazzy**. Repository at
`/mnt/c/Users/ozkan/projects/amr-agent`, branch `m5-ver3`. Every session
below was taken under `./m5_ver3/m5v3.sh start --headless` with the GPU
preflight passed (`gpu: D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`) and
nothing else running on the machine.

**The instruments.**

| Tool | What it answers | New here |
|---|---|---|
| `tools/sensor_evidence.py record` | captures one run off the live plant into CSVs | ● |
| `tools/sensor_evidence.py analyse` | every table below, from those CSVs, **with no ROS** | ● |
| `tools/evidence_core.py` | the arithmetic underneath, `--selftest`, 49 unit tests | ● |
| `tools/rtf_probe.sh` | real-time factor of the running world, 30 s sample | |
| `tools/noise_probe.sh` | Task 2's static-noise probe — cited, not re-run | |
| `gz topic -f -t <topic>` | gz-side delivered rate | |
| `ros2 topic hz <topic>` | ROS-side delivered rate **— and see §7.5** | |

**The configured column is read out of the model, not out of
`config.yaml`.** `analyse` parses `model.sdf` for every stddev, bias,
update rate and range limit it compares against, so the configured column
cannot drift away from the plant it describes. `config.yaml`'s `sensors:`
block repeats the rates for the shells, which cannot read XML; `analyse`
diffs the two on every run and printed **no disagreement** on any session
here.

**The sessions.** Eight, all under `m5_ver3/logs/evidence/` and all
untracked (§9 names their md5s).

| Session | What it is | Sim time |
|---|---|---|
| `static-rest-20260825-230717` | vehicle at rest, 9 ROS streams + 2 gz phases | 60 s |
| `drive-straight-20260825-231657` | `straight`, run 1 of 3 | 40.2 s |
| `drive-straight-20260825-231845` | `straight`, run 2 of 3 | 40.2 s |
| `drive-straight-20260825-231945` | `straight`, run 3 of 3 | 40.2 s |
| `drive-square-20260825-232051` | `square` | 63.0 s |
| `drive-aisle-20260825-232216` | `aisle` | 85.6 s |
| `drive-corner_creep-20260825-232401` | `corner_creep` — **new profile**, run 1 of 2 | 31.1 s |
| `drive-corner_creep-20260825-234231` | `corner_creep`, run 2 of 2 | 31.7 s |

**The stack was stopped and restarted before every drive**, so each run
begins from the spawn pose. `analyse` refuses a drive session whose first
ground-truth sample is more than 0.05 m or 0.02 rad from `vehicle.spawn`
— all seven read **exactly** `(-17.000000, 10.000000) yaw 3.141590`,
0.0000 m and 0.00000 rad off.

---

## 1. The sensor set: datasheet, configured, delivered

| Sensor | Datasheet (device class) | Configured (`model.sdf`) | Measured σ (temporal, at rest) | Delivered gz | Delivered ROS |
|---|---|---|---|---|---|
| `nav_lidar` | SICK TiM571: 15 Hz, 270°, 0.33°, 0.05–25 m, stat. <20 mm | 15 Hz, 811 rays, 0.05–25.0 m, gaussian σ **0.020**, bias σ 0.02 | **0.019979** (×0.999) | **15.1987** Hz | **15.1515** Hz |
| `safety_scanner_back` | SICK nanoScan3 class (frozen, GC 6) | 10 Hz, 275 rays, 0.10–8.0 m, gaussian σ **0.020** | **0.019564** (×0.978) | **9.7751** Hz | not bridged |
| `nav_lidar_3d` | Ouster OS0-32: 10 Hz, 1024×32, 0.3–50 m | 10 Hz, 1024×32, gaussian σ 0.025 | 0.024315 — Task 2, `noise_probe.sh` | **9.7498** Hz | not bridged (F2) |
| `pallet_cam` depth | Intel RealSense D455: 640×480, 87° HFOV, 0.6–6 m | 15 Hz, 640×480, gaussian σ **0.008** | **0.008029** (×1.004) | **15.1547** Hz | **15.1515** Hz |
| `pallet_cam` camera_info | ″ | 15 Hz | — (no reading to spread) | **15.1728** Hz | **15.1515** Hz |
| `imu` gyro, per axis | Bosch BMI088: 0.1 °/s rms @47 Hz BW | 100 Hz, gaussian σ **0.001745** rad/s | **0.001713–0.001759** (×0.98–1.01) | **100.0093** Hz | **100.0000** Hz |
| `imu` accel x, y | ″ 160 µg/√Hz | gaussian σ **0.010760** m/s² | **0.010728–0.010729** (×0.997) | ″ | ″ |
| `imu` accel z | ″ 190 µg/√Hz | gaussian σ **0.012780** m/s² | **0.012845** (×1.005) | ″ | ″ |
| ground truth `odom` | — (an instrument, not a device) | 20 Hz `OdometryPublisher` | — | not sampled | **20.0000** Hz |
| `/clock` | — | 500 Hz (world step 0.002 s) | — | — | **500.0000** Hz |
| `joint_state`, `drive_speed/read_a` | — | once per physics iteration | — | — | **500.0000** Hz each |
| `/m5v3/wheel_odom` | — (the estimate) | once per `read_a` sample | — | — | **500.0000** Hz |

**Instruments, cell by cell.** The measured-σ column is
`sensor_evidence.py analyse` over `static-rest-20260825-230717`, except
`nav_lidar_3d`, which is not bridged and whose figure is Task 2's
(`EVIDENCE_MODEL_V3.md` §5.1) — this task did not re-render it, because
subscribing to it costs 0.13 of mean RTF and it has no consumer until F2.
The **Delivered gz** column is `gz topic -f` for 20 s per topic, run by
`record --static`'s second phase. The **Delivered ROS** column is the
recorder's own capture, computed from the **plant's own sim-time stamps**
— which is why the figures are exact.

**Every noise channel is inside the ×1.25 band `config.yaml`
(`evidence.analyse.noise_factor`) states the acceptance in.** The worst
is the safety scanner at ×0.978 and the best the nav lidar at ×0.999.
Nothing here needed diagnosing.

### 1.1 Why the ROS column is exact and the gz column is not

`hz_sim` is computed from the stamp the plant put on the message, and
those stamps land on the world's own 0.002 s grid: 900 nav-lidar frames
over 60 s of sim time with **every** interval exactly 0.066 s, `dt_med` =
`dt_max` = 0.06600. So the ROS column is not a rate that happened to
average out — it is the sensor's own cadence, with no missing frame
anywhere in any session.

**15.1515 Hz and not 15 Hz**, and Task 2 found the mechanism: 0.066 s is
**33 steps of `max_step_size` 0.002**, not the 0.0666667 s a 15 Hz period
asks for, so the 15 Hz sensors land on a 33-step grid and run **1.0 %
fast**. The 10 Hz sensors have no such error (0.1 s is 50 steps) and nor
does the IMU (0.01 s is 5 steps). Confirmed here to seven figures:
`15.1515 = 1/0.066` exactly.

The gz column is a wall-clock instrument sampling ten-interval windows,
so it carries the real-time factor and its own sampling spread — hence
15.1987 against the sim-exact 15.1515.

### 1.2 The rate table as `analyse` prints it (static session)

```
  stream             samples     hz_sim    hz_wall  of conf     dt_med     dt_max     rtf
  clock                30021   500.0000   499.9114             0.00200    0.00200  0.9998
  odom_truth            1200    20.0000    19.9810             0.05000    0.05000  0.9991
  wheel_odom           30001   500.0000   499.6095             0.00200    0.00200  0.9992
  scan_nav               909    15.1515    15.1380   101.0%    0.06600    0.06600  0.9991
  imu                   6000   100.0000    99.9150   100.0%    0.01000    0.01000  0.9991
  depth                  909    15.1515    15.1405   101.0%    0.06600    0.06600  0.9993
  cam_info               909    15.1515    15.1372   101.0%    0.06600    0.06600  0.9991
  joint_state          29998   500.0000   499.6055             0.00200    0.00200  0.9992
  drive_read_a         29997   500.0000   499.6144             0.00200    0.00200  0.9992
```

`dt_max` = `dt_med` on every row is the claim that matters: **not one
message was lost on any of the nine streams**, including the three that
arrive at 500 Hz, over 60 s. The `rtf` column is the same messages
counted twice — sim stamps against arrival — and it agrees with
`rtf_probe.sh` (§6) without being the same instrument.

---

## 2. The IMU at rest: the white noise, and the bias underneath it

**Instrument:** `analyse` over the static session, 6000 samples per axis.
The spread is scored **after each axis's own run mean is removed**, and
that mean is reported separately as the bias. gz draws a bias once per
sensor at load and adds it to every reading for the life of the run, so
it lives entirely in the mean and not in the spread. Adding the two
together and calling the total "noise" would be the dishonest reading.

| Axis | Configured σ | **Measured σ** (mean removed) | ratio | Configured bias | **Measured mean** |
|---|---|---|---|---|---|
| gyro x | 0.001745 | **0.001755** | 1.006 | ±0.002618 | **−0.002606** |
| gyro y | 0.001745 | **0.001759** | 1.008 | ±0.002618 | **−0.002633** |
| gyro z | 0.001745 | **0.001713** | 0.981 | ±0.002618 | **+0.002621** |
| accel x | 0.010760 | **0.010729** | 0.997 | ±0.019610 | **−0.019669** |
| accel y | 0.010760 | **0.010728** | 0.997 | ±0.019610 | **+0.019748** |
| accel z | 0.012780 | **0.012845** | 1.005 | ±0.019610 | **+9.819400** |

**The bias magnitude is the model's and the SIGN is drawn per run, and
this table is the measurement of that.** `model.sdf` sets
`bias_stddev 0`, and its own comment says what that buys: *"bias_stddev 0
fixes the MAGNITUDE across runs; gz still draws the SIGN at random."*
Five of the six axes read the configured magnitude to within 0.7 %, and
they do not agree on the sign: −, −, + on the gyro and −, +, + on the
accelerometer, from one draw at one model load. A consumer may **not**
assume the sign of this bias, and an F2 EKF that estimates it must
estimate it per run.

**The sixth axis carries gravity, and the reference is the world's own.**
`az` reads +9.819400 m/s². `m6/gazebo/warehouse_ver3.sdf` declares
`<gravity>0 0 -9.8</gravity>`, so the residual is **+0.019400** against a
configured bias magnitude of 0.019610 — a 1.1 % match, and the sign is
positive on this draw.
  **This is a trap and `analyse` reads the world file to avoid it.**
  `forklift_ver3`'s own mass derivation uses standard gravity 9.80665
  (`EVIDENCE_MODEL_V3.md` §7.1), the world runs 9.8, and the difference
  between them is 0.00665 — **a third of the accelerometer bias being
  checked against them.** Assuming 9.80665 would have turned a bias that
  matches the model to 1 % into one that misses it by 34 %.

---

## 3. Wheel-odometry drift, per profile

**The estimator's settings, stated once and unchanged across every run
below** (`config.yaml`, `wheel_odom:`): encoder **1024 counts/rev** (line
grid, 0.7363 mm of tread per count), believed wheel radius **0.12 ×
1.015** = 0.1218 m (a deliberate +1.5 % scale error), steer bias
**+0.005 rad** added to the reading, no slip term (the physics engine
produces the slip). The node reads no ground truth and broadcasts no
transform.

> **TOOL-PRINTED AS OF 2026-08-26.** The paragraph above was a HAND COPY
> of `config.yaml`'s `wheel_odom:` block — a settings line nothing
> re-checked, over a table of figures that are only about those settings.
> `sensor_evidence.py analyse` now reads the five keys itself and prints
> them ahead of every session it scores, so a `config.yaml` retuned since
> these CSVs were recorded shows up as a disagreement with this file
> rather than scoring an old run under new numbers. Its output against
> `drive-corner_creep-20260825-232401`: vehicle `forklift_ver3`,
> **1024 counts/rev** (one count `6.13592e-03` rad of shaft, **0.7363 mm**
> of tread at the plant's 0.120 m wheel, 0.7474 mm as the estimator steps
> it), believed radius **0.1218 m** = `0.120 × 1.0150`, steer bias
> **+0.0050 rad**. Not one figure above moved; this note records where
> they now come from.

**The frame, and it is where this measurement is won or lost.** The
ground truth is the model's `OdometryPublisher` and it publishes the
**world** pose; the estimate is in an odom frame that starts at the
vehicle, at the origin, yaw 0. Scoring one against the other is *not* a
subtraction: the spawn pose comes off the world pose and the spawn yaw is
rotated out of the remainder,
`p' = R(-ψ₀)·(p - p₀)`, `ψ' = ψ - ψ₀`. This vehicle's ψ₀ is **π**, where
that rotation is its own inverse — so a sign error leaves every magnitude
exactly right and puts the whole trajectory on the wrong side of the
origin. `evidence_core.SpawnFrame` is the only place it is spelled and
`tests/test_evidence_core.py` tests π and a quarter turn together.

**Every score is ABSOLUTE.** No initial offset is removed, no per-run
constant is fitted, and a unit test locks that (an estimate 0.40 m out at
its first sample and never worse scores 0.40 m, not 0).

| Profile | Runs | Truth path | Estimate path | Path error | **End error** | RMS over run | **Worst** | End heading error |
|---|---|---|---|---|---|---|---|---|
| `straight` | 3 | 11.5935 / 11.5884 / 11.5905 m | 12.0839 / 12.0786 / 12.0801 m | **+4.23 / +4.23 / +4.22 %** | **0.5800 / 0.5798 / 0.5792 m** | 0.5241 / 0.5240 / 0.5231 m | 0.8016 / 0.8024 / 0.8006 m | −0.0575 rad (all three) |
| `square` | 1 | 8.2985 m | 10.2723 m | **+23.79 %** | **1.8707 m** | 1.7670 m | 3.1144 m | −1.9807 rad |
| `aisle` | 1 | 38.1178 m | 39.4361 m | **+3.46 %** | **0.0399 m** | 0.6506 m | **1.2276 m** | −0.0087 rad |
| `corner_creep` | 2 | 3.7701 / 3.7694 m | 4.2707 / 4.2705 m | **+13.28 / +13.29 %** | **1.8140 / 1.8177 m** | 0.9648 / 0.9572 m | 1.8140 / 1.8177 m | +1.7310 / +1.7326 rad |

> **THE PLANT UNDER THIS TABLE CHANGED ON 2026-08-26 (phase F1.5) —
> `EVIDENCE_LATERAL_TUNE.md`. Every row above is kept and none is
> rewritten: they are what this estimator scored on the plant F1
> measured, and that is the plant `EVIDENCE_MODEL_V3.md` describes.**
> The two rear wheels now carry the wheel-slip system, so the vehicle
> takes very nearly the yaw its steer angle promises, and the two rows
> with corners in them move a long way while the two straight ones do
> not. Re-measured, same instrument, one run each:
>
> | Profile | Truth path | Path error | End error | End heading error |
> |---|---|---|---|---|
> | `straight` | 11.5479 m | +4.23 % | **0.5778 m** | −0.0574 rad |
> | `square` (re-tabled, 6.145 s corners) | 7.5242 m | +9.78 % | **0.6712 m** | +0.5291 rad |
> | `corner_creep` | 3.9700 m | +7.65 % | **0.1945 m** | +0.0156 rad |
>
> `aisle` was not re-driven (it is dead straight both ways).
> **`corner_creep`'s end error falls from 1.8172 m to 0.1945 m and its
> heading error from +1.7326 rad to +0.0156 rad**, which is the sharpest
> reading in this file about what §4 was measuring: the estimator did not
> improve and not one of its settings moved — the VEHICLE stopped
> scrubbing, and dead reckoning is only blind to a scrub that is there.
> §3.1(c)'s argument survives it intact and is marked in place.

**Repeatability, `straight` × 3.** End error **0.5800, 0.5798, 0.5792 m**
— a spread of **0.8 mm**, 0.14 % of the figure. The ground truth itself
repeats to 5.1 mm over 11.59 m (0.04 %). This plant and this estimator
are deterministic to a part in seven hundred, which is what makes a
single run of the other profiles worth quoting. `corner_creep` was run
**twice** and repeats as tightly (end error 1.8140 against 1.8177 m,
0.2 %); `square` and `aisle` are **one run each** and that is stated
rather than implied.

### 3.1 Three readings in that table that need saying out loud

**(a) The worst error is not at the end, and on `straight` it is 38 %
bigger than the end error.** The error peaks at **0.8016 m** at t+25.35 s
and falls back to 0.5800 m by the time the truck stops. The shape:

```
  t+12.0  err 0.1946   truth 0.812 m travelled, estimate 1.007 m
  t+16.0  err 0.5898
  t+20.0  err 0.6934
  t+24.0  err 0.7721   (deceleration ramp begins)
  t+25.35 err 0.8016   <- worst
  t+32.0  err 0.5800   (stopped)
```

The estimate is already 0.195 m ahead after 0.81 m of ground — 24 %,
against a designed scale error of 1.5 %. That is the **slip transient**:
`config.yaml`'s own `straight:` comment says the largest slip of the run
is in the first tenth of a second of traction, and the wheel turns while
the truck is still accelerating. Braking is the same effect with the
opposite sign, and it gives 0.22 m back. **An end-of-run figure alone
understates the worst case**, which is why the table carries the run
maximum beside it.

**(b) `aisle`'s end error is 0.0399 m and it means nothing.** A profile
that returns to its start returns the *estimate* to its start too: the
over-reporting on the outward leg is undone on the way back. The same run
was **1.2276 m** out at the far end of the aisle, and its RMS is 0.6506 m
— sixteen times its end error. A closure figure on an out-and-back
profile flatters a dead-reckoned estimate enormously, and this is the run
that shows by how much. (The ground truth's own closure is 1.7554 m
short of its start, dead straight — Task 3 measured 1.670 m on the same
profile, so that shortfall repeats to about 5 %.)

**(c) `square` over-rotates by 1.73×.** The plant turned **5.8506 rad**
of the 6.2832 asked (93.1 %); the estimate reported **10.1532 rad**. That
is Task 3's finding reproduced by an independent instrument on a fresh
run (it measured 5.8418 and 10.1408). Dead reckoning cannot see lateral
tyre scrub — nothing readable at the shaft or the steer axis contains it
— and this is the single strongest argument for F2's gyro.

> **RE-MEASURED 2026-08-26 (F1.5): 1.084×, and the argument is
> unchanged.** `EVIDENCE_LATERAL_TUNE.md` §4.3.3. On the tuned plant the
> re-tabled square turns **6.3124 rad** and the estimate reports
> **6.8416 rad**. The factor collapsed because the scrub did, not because
> anything in the estimator learned to see it — no term was added and no
> setting moved. What is left is still 0.53 rad of heading error over a
> 42 s square, which is not an estimate anything may navigate on, so the
> conclusion above stands with a smaller number under it.

---

## 4. Does the tricycle kinematic model hold at creep speed?

> **ANSWERED HERE, ACTED ON IN F1.5 — `EVIDENCE_LATERAL_TUNE.md`,
> 2026-08-26. This section is NOT rewritten.** It is the measurement that
> caused the tune, and a measurement that has been acted on is still the
> measurement. Everything below describes the plant as it stood at commit
> `32c8964`; the plant it describes no longer exists, and the numbers that
> replaced it are:
>
> | | this section | after F1.5 |
> |---|---|---|
> | delivered at π/4, 0.3 m/s | **0.4098 / 0.4102** | **1.0054** (three runs, identical) |
> | effective radius vs kinematic 1.0434 m | 2.5194 m | 0.9859 m |
> | in-corner wander (§4.2) | 10.2 % of the mean | **0.0 %**, sd 0.000045 rad/s |
> | four-corner spread at −1.25 rad (§4.2) | 16.6 % | 11.5 %, same 180° period |
>
> **What the tune was, in one line:** the two rear wheels had no
> wheel-slip entry, so their contact patches were rigid; two rigid patches
> cannot be yawed about their own vertical axes without sliding, and the
> steered wheel was sliding at 22° to overcome them. §4.1's own
> instrument now prints that split (`analyse`'s *where the yaw went*
> block), and on the run below it charges **99.5 % of the deficit to the
> steered wheel and 0.5 % to the rear axle** — which is the reading that
> located the repair at the wheels that were NOT sliding.
>
> **§4.2's finding is the one that half survives.** The heading dependence
> vanishes at π/4 and shrinks by a third at −1.25 rad, and the candidate
> mechanism named below — an axis-aligned friction pyramid — is what the
> shrinking is consistent with: it goes away exactly when every contact is
> made isotropic. It is still not chased.

The owner's question, 2026-08-25, and the reason `corner_creep` exists:
**a real truck's kinematics holds at 0.3 m/s** — at a crawl a
polyurethane tyre has almost no lateral force to shed — so if this plant
delivers a fraction of the yaw its steer angle promises even at creep,
that is a statement about the WheelSlip lateral compliance and not about
the speed.

**Instrument:** `analyse` over `drive-corner_creep-20260825-232401` (run
1; run 2 is quoted beside it in §4.1 and agrees to 0.1 %). The
steady window is found **in the data and not counted off the schedule**:
the longest stretch where the steer *reading* is within 0.02 rad of the
table's angle and the vehicle is moving, with the first 4 s discarded
because the steer axis has to slew. The yaw rate and the speed are the
**ground truth's**, differenced, and the speed is moved onto the **rear
axle** first — base_link carries a lateral term `d·ψ̇` the axle does not,
worth 1.7 % here on a ratio quoted to three figures.

```
  steady window   [25.324, 34.930] s of sim time, 192 truth samples
  steer commanded -0.785398 rad     held (measured) -0.788532 rad
  tread commanded -0.300 m/s        rear-axle ground speed 0.2092 m/s
  yaw rate        +0.083054 rad/s
  its steadiness  1s bins: 9 of them, +0.070823 to +0.096555, sd 0.008468 (10.2%)

  kinematic v_tread*sin(d)/L  0.202663 rad/s -> delivered 0.4098
  kinematic v_rear *tan(d)/L  0.200537 rad/s -> delivered 0.4142
  turning radius  kinematic 1.0434 m   MEASURED 2.5194 m
```

**The two kinematic spellings are one formula** — `v_tread·sin δ/L` and
`v_rear·tan δ/L` are identical because `v_rear = v_tread·cos δ` — and
both are printed because they carry different errors: the first includes
longitudinal slip *and* lateral scrub, the second only scrub. They differ
by 1 %, which is the whole of the longitudinal slip at this speed
(`EVIDENCE_MODEL_V3.md` §7 measured 0.96 % at cruise). **So essentially
all of the 59 % that goes missing is lateral scrub.**

### 4.1 The answer, beside the two cruise-speed rows

| Steer [rad] | Speed | Kinematic [rad/s] | Measured [rad/s] | **Delivered** | Effective R | Instrument |
|---|---|---|---|---|---|---|
| −0.785398 | 0.3 m/s | 0.20203 | 0.08104 | **0.401** | 2.632 m | Task 3, throwaway gz probe |
| −1.250000 | 0.3 m/s | 0.27114 | 0.17182 | **0.634** | 0.711 m | ″ |
| **−0.785398** | **0.3 m/s** | **0.202663** | **0.083054** | **0.4098** | **2.5194 m** | **`sensor_evidence.py`, this task, run 1** |
| **−0.785398** | **0.3 m/s** | **0.202663** | **0.083127** | **0.4102** | **2.5172 m** | **″, run 2** |

**NO. The tricycle model does not hold at creep speed on this plant.** At
0.3 m/s and π/4 of steer the truck takes **41 % of the yaw its geometry
promises** and turns on a radius of 2.52 m where the kinematics says
1.04 m. A real counterbalance truck at that speed would deliver very
nearly all of it.

**This is recorded and is NOT tuned** (global constraint 7). What it
means:

- The plant's `slip_compliance_lateral 7.0` is **unrealistically soft at
  creep**. It was set equal to the longitudinal value and never tuned —
  `config.yaml` says so: *"this track measures no lateral manoeuvre yet,
  and a number tuned against nothing is a number invented."* This is the
  lateral manoeuvre. The number now has something to be measured against,
  and the phase that measures a turn is the phase that gets to change it.
- Anything downstream that plans on `v·tan δ/L` — a Nav2 controller, a
  pure-pursuit follower — will command a corner **2.4× tighter** than it
  gets on this simulator. That is F3's problem and it is now a measured
  number rather than a surprise.
  > **F1.5: 5.8 % WIDER, and the sign has flipped.** The tuned plant
  > corners at 0.9859 m where the kinematics says 1.0434 m, so a planner
  > now gets slightly *more* corner than it asks for instead of 2.4×
  > less. Still a number to design against: a tenth the size of this one,
  > and the other way round. `EVIDENCE_LATERAL_TUNE.md` §4.1.
- The figure reproduces Task 3's 0.401 to within the wander (§4.2), from
  a different run, a different instrument and a stated window. Task 3's
  came from a throwaway probe that no longer exists; this one is a
  profile in `config.yaml` and a tool in the tree.

### 4.2 The delivered yaw rate depends on the vehicle's HEADING

**The wander in that window is not noise, and the second run is what
proves it.** The yaw rate inside a single held corner, at constant speed
and constant steer angle, runs from 0.0708 to 0.0966 rad/s — ±13 % about
its own mean, sd 10.2 % — while the truck sweeps 65° of heading. Two
runs of the same profile, taken 18 minutes and one stack restart apart:

| Run | Window bins | Min | Max | sd | as % of mean |
|---|---|---|---|---|---|
| 1 | 9 × 1 s | +0.070823 | +0.096555 | 0.008468 | 10.2 % |
| 2 | 9 × 1 s | +0.070683 | +0.096428 | 0.008449 | 10.2 % |

The wander **repeats to four decimal places**. It is not measurement
noise and it is not the contact solver's randomness — it is a
deterministic function of where the truck is on its arc.

`square` shows why, because it turns four corners of 90° at the *same*
steer angle and the *same* speed at four different headings.

**Instrument:** `sensor_evidence.py analyse`, its *every held corner*
table, over `drive-square-20260825-232051/odom_truth.csv`
(md5 `f59b511b122b1a43f43afe42d7c72a79`) and that session's
`joint_state.csv`. The reduction is `evidence.corner.slew_in_s` **1.0 s**
off the start of each held corner and `evidence.corner.exit_s` **0.3 s**
off its end — the axis is inside the tolerance band for the last part of
its slew *in*, and on the way *out* the tread command changes at the same
instant, so the final fraction of a second carries a yaw rate at a
falling speed. Both constants live in `config.yaml` with that reasoning
beside them. The tool prints how many corners it **found** next to how
many it **measured**, so a dropped one cannot go missing: `corners found
4   measured 4`.

```
    #        window [s]    span  heading in   held rad   rear m/s    yaw rate  delivered
    1    22.90    30.14    7.20     -2.9837  -1.258786     0.0886   +0.149675     0.5504
    2    35.38    42.62    7.20     -1.5484  -1.257138     0.0871   +0.172101     0.6332
    3    47.86    55.10    7.20     -0.0648  -1.255925     0.0893   +0.152368     0.5609
    4    60.33    67.57    7.20     +1.3421  -1.255044     0.0875   +0.176503     0.6499
  delivered       0.5504 to 0.6499 over 4 corners, spread 16.6% of the mean
```

| Corner | Heading at entry | Rear-axle speed | Yaw rate | **Delivered** |
|---|---|---|---|---|
| 1 | −2.98 rad (≈ world −x) | 0.0886 m/s | 0.149675 | **0.5504** |
| 2 | −1.55 rad (≈ world −y) | 0.0871 m/s | 0.172101 | **0.6332** |
| 3 | −0.06 rad (≈ world +x) | 0.0893 m/s | 0.152368 | **0.5609** |
| 4 | +1.34 rad (≈ world +y) | 0.0875 m/s | 0.176503 | **0.6499** |

> **These four figures were first published here as 0.552 / 0.635 /
> 0.562 / 0.651, from a hand reduction, and they are kept beside the
> tool's.** The measured yaw rates are *identical* in both — 0.149675,
> 0.172101, 0.152368, 0.176503 — and so are the windows. What moved, by
> 0.2–0.3 %, is the divisor: the hand reduction used the kinematic rate
> at the **commanded** −1.25 rad, while the tool uses the rate at the
> steer the axis actually **held**, which the `held rad` column shows is
> −1.2550 to −1.2588. That is the position controller overshooting by
> 0.005–0.009 rad, and dividing by the angle the vehicle really had is
> the correct thing to do. The published claim is unchanged and the
> difference is an order of magnitude below it.

The pattern alternates with a period of **180°**, not 360°: the two
corners taken along the world *y* axis deliver 0.6332 and 0.6499, the two
along *x* deliver 0.5504 and 0.5609 — **16.6 % apart**, and the
faster-turning pair is also the *slower*-travelling pair, so it is not
distance. A period of π is an **axis**-dependent effect, not a
direction-dependent one.

**The reduction is worth 2 % and the heading is worth 16.6 %**, which is
how far this finding is above the way it was measured. The same
per-corner reduction run over `corner_creep`'s single corner gives
**0.4011** and **0.4015** (runs 1 and 2) against the §4.1 headline's
0.4098 and 0.4102: the sustained-corner reduction discards a 4 s settle
and averages everything left, the per-corner one discards 1.0 s and 0.3 s
and so includes the earlier, slower part of the arc. `analyse` prints
both for that profile and neither is hidden.

**Candidate mechanism, named and NOT chased:** a pyramid approximation of
the friction cone, which is what ODE-family contact solvers use and which
is axis-aligned by construction. Confirming it means reading gz's contact
solver, which is not this task's job. What is established by measurement
is the consequence, and it is the part that matters downstream:

> **One steer angle on this plant does not have one delivered fraction.**
> It has a fraction that depends on where the truck is pointing, by
> 16.6 %.
> `config.yaml`'s scrub table (0.401 at 0.785 rad, 0.634 at 1.25 rad) is
> therefore a figure *at the heading it was measured at*, and the
> `square` profile's corner time — derived from one of those rows — is
> the reason that profile closes to 0.68 m rather than to zero.

**F1.5 re-tabled that corner on the tuned plant and the square closes to
0.0670 m** (`EVIDENCE_LATERAL_TUNE.md` §4.3). The sentence above is still
right about *why* it did not close, and it is right in a second way it
did not intend: the re-tabled corner is sized from the **mean of the four
headings** with the 11.5 % spread stated beside it, because at −1.25 rad
one steer angle still does not have one delivered fraction. The 0.62 m
that came out of the closure was the plant; the 11.5 % that stayed is
this section's finding, and no corner time can remove it.

---

## 5. Real-time factor at the full sensor set

**Instrument:** `tools/rtf_probe.sh`, 30 s off `/world/warehouse/stats`,
GPU on, headless, the stack `m5v3.sh` starts (world + parameter bridge +
image bridge + wheel odometry), nothing else on the machine.

| # | Configuration | Samples | Mean | Median | Floor | Ceiling |
|---|---|---|---|---|---|---|
| 1 | Task 1 baseline — three bridged topics, no sensors | 296 | 0.9985–0.9996 | 0.9999 | 0.9408–0.9429 | — |
| 2 | Task 2 — six sensors, six bridged topics | 296 | 0.9995–0.9997 | 0.9999 | 0.9574–0.9577 | — |
| 3 | **this task, pass 1** — + two 500 Hz joint channels + the estimator | 296 | **0.9992** | **0.9999** | 0.9363 | 1.0460 |
| 4 | **this task, pass 2** | 296 | **0.9984** | **0.9998** | 0.9688 | 1.0174 |

**The full sensor set plus a 500 Hz estimator still costs nothing
measurable.** Mean 0.9984–0.9992 against a baseline of 0.9985–0.9996 and
a median that has not moved from 0.9999 across three tasks. The floor
wanders (0.936 to 0.969 here, 0.941 to 0.958 before) and is the noisiest
statistic of the four in every pass anybody has taken on this rig.

**And the recorder itself is free**, which had to be checked because
every rate in §1 was measured while it was running: the `rtf` column of
§1.2 — the same messages counted by sim stamp and by arrival — reads
**0.9991–0.9998** across all nine streams during the 60 s static capture.
Two instruments that share no code agree to a part in a thousand.

---

## 6. The estimate's own settings, confirmed on the wire

Read back off `drive-straight-20260825-231657` rather than assumed:

- The estimate opens at exactly `(0.000000, 0.000000)` yaw `0.000000` —
  an odom frame, not a world pose.
- Reported path 12.0839 m against a ground truth of 11.5935 m,
  **+4.23 %**. The two components: the plant's own ~2.6 % slip (the wheel
  turns further than the ground moves) and the estimator's designed
  +1.5 % radius scale, compounding rather than cancelling — which is what
  `config.yaml` says the sign of that scale error was chosen to do.
- Invented heading on a dead-straight run: **−0.0575 rad** in all three
  runs, against `ds·sin(δ_bias)/L = -12.084 × 0.005 / 1.05 = −0.05754`.
  The steer bias is exactly where it was put.

---

## 7. Known gz defects, observed on these runs

Nothing here is worked around. Each item says what was measured on **this
session set**, what it means for a consumer, and where upstream it lives.

### 7.1 `<bias_mean>` and `<bias_stddev>` are undeclared on a lidar — re-observed

`sdformat`'s `lidar.sdf` declares its own inline `<noise>` carrying only
`type`, `mean` and `stddev`; it never includes `noise.sdf`, where the
bias elements live. Counted in `logs/world.log` on this session's stack:

```
  1  XML Element[bias_mean]   ... not defined in SDF
  1  XML Element[bias_stddev] ... not defined in SDF
  7  XML Element[gz_frame_id] ... not defined in SDF   (one per sensor)
```

Nine warnings per load, indistinguishable from typos, and the elements
work anyway — §1's nav-lidar σ 0.019979 is produced *through* that
warning. Task 2's §9.3 stands.

### 7.2 A lidar clamps a too-near return to `range_min`, and near-clamped beams flicker

`analyse` splits beams pinned at the sensor's own `range_min` out of the
noise statistic (their spread is not a noise figure) and reports the
count. On these captures **no beam sat pinned for a whole capture** — but
the beam counts show the same thing from the other side:

| Sensor | Beams | Finite in **every** frame | Lost |
|---|---|---|---|
| `nav_lidar` | 811 | 710 | 101 |
| `safety_scanner_back` | 275 | 195 | 80 |

The safety scanner loses **29 % of its beams** to flicker — it looks at
this truck's own counterweight from 0.1 m, the configured σ 0.02 is a
fifth of that distance, and a reading that lands below `range_min` comes
back as a no-reading rather than as a clamp. Task 2 measured the clamped
case (`EVIDENCE_MODEL_V3.md` §8: 562 readings of one 3D-lidar sweep
exactly at 0.300); this is the same boundary from the noisy side. **A
consumer of this scanner must treat both `range == range_min` and a
missing return near the vehicle as suspect**, and a safety function must
never infer "clear" from either.

### 7.3 Depth noise is additive only — confirmed as a floor

`analyse` measured σ **0.008029** on a patch whose mean depth is
**2.201234 m**. The real D455 at 2.2 m is four to five times worse, and
its error is roughly quadratic in range. The model configures 8 mm as a
**floor** and says so; this camera is optimistic at range by
construction, and the quadratic σ(z) belongs to a later phase.
(gz-sensors #416, open.) The patch depth also re-confirms the mount
geometry to a millimetre: 1.10 m / sin 30° = 2.200 m predicted,
2.201234 measured.

### 7.4 `gaussian_quantized` — not re-observed, because the model no longer uses it

Task 2 measured a `gpu_lidar` declared `gaussian_quantized` producing
**no noise at all**, silently, and changed the type to `gaussian`. This
task confirms the fix holds from the other end: every lidar channel
delivers its configured σ to within 2 %. The quantization the TiM571
really has (1 mm) is still **not modelled**, and that stays stated rather
than claimed.

### 7.5 `ros2 topic hz` loses depth frames. **`ros_gz_image` does not.**

**This corrects `EVIDENCE_MODEL_V3.md` §2(c) and §9.5**, which recorded
the depth image arriving ROS-side at 87–94 % of its gz-side rate and
attributed the loss to `ros_gz_image`'s bridge. The frames are on the
wire. The measuring subscriber was losing them.

**Measured three ways, this session:**

1. The recorder's own capture: **909 depth frames in 60 s**, sim-time
   intervals **exactly 0.066 s**, `dt_max` = `dt_med`. Not one frame
   missing — and if the bridge had dropped one, the *stamps* of the
   frames that did arrive would show a 0.132 s gap. They do not.
2. Queue depth is not the mechanism. A plain `rclpy` subscriber, 20 s
   each at depth **1**, **10** and **500**: 302, 303, 302 frames,
   **15.1515 Hz**, `dt_max` 0.0660, **0 gaps** in all three.
3. Side by side, same instant, same topic: the `rclpy` subscriber at
   depth 1 read **15.1515 Hz with 0 gaps** while `ros2 topic hz` on the
   same topic read **8.98 Hz with a 0.331 s worst interval**. Alone it
   reads 13.75–13.77 Hz with a 0.216 s worst interval.

`camera_info`, which crosses on the *parameter* bridge from the same
sensor at the same instant, arrives at 15.1515 Hz too — and the two
channels are frame-aligned *exactly*: **909 depth frames, 909
`camera_info` messages, and all 909 stamps identical to the
nanosecond**. The earlier reading concluded that an F2 consumer needing
frame-accurate depth must not assume the image and its info arrive
together. On this stack it may.

**What was not chased:** *what inside* `ros2 topic hz` loses them. It is
a python node that spins in one thread and prints from another, and the
loss got worse (13.8 → 9.0 Hz) when a second subscriber was added to the
machine, which points at its own scheduling rather than at the transport.
The conclusion a consumer needs does not depend on that: **a subscriber
that keeps up gets every depth frame, and `ros2 topic hz` is not a safe
instrument on this channel.**

### 7.6 gpu_lidar accuracy at shallow incidence — cited, not re-measured

Task 2 characterised it on a noise-free capture (0.5 mm at normal
incidence, 147 mm at 10° grazing; gz-sim #2743, open). This task's
captures all carry the noise block, so they cannot separate the
renderer's error from the draw and no attempt is made to. §9.1 of
`EVIDENCE_MODEL_V3.md` remains the measurement.

### 7.7 Two things about the world file, found by reading it

**`m6/gazebo/warehouse_ver3.sdf` is not well-formed XML.** Its header
comment draws the floor plan with rules made of hyphens, and `--` inside
an XML comment is illegal: python's `ElementTree` refuses the file at
line 18 while gz's own parser accepts it without a word. The file belongs
to m6 and is used **by reference** — it is not this track's to correct —
so `evidence_core.sdf_gravity` strips comments and scans for the one
element it needs, and says why in its own docstring. Anything else that
tries to parse that world with a strict XML library will fail.

**The world runs at 9.8 m/s² and the vehicle's mass derivation uses
9.80665.** Neither is wrong; the gap is 0.00665, which is a third of the
accelerometer bias measured against it (§2). Recorded so the next person
reading `az` does not subtract the wrong number.

---

## 8. What this task did not do

- **No sensor, model or estimator value was changed.** This task built
  instruments and took readings; the only files it touched that a run
  depends on are `config.yaml` (a new profile, a new `evidence:` block, a
  renamed topic key) and `m5v3.sh` (that key). The corner-fidelity
  finding of §4 is **recorded, not tuned** — global constraint 7.
- **`points3d` is still not bridged**, and its ROS-side cell in §1 stays
  "not bridged" rather than being filled by subscribing to it for the
  sake of a full table. Its gz-side rate is measured (9.7498 Hz) and
  costs 0.13 of mean RTF to take.
- **The 3D lidar's noise was not re-measured** for the same reason;
  Task 2's figure is cited with its instrument named.
- **`square` and `aisle` are one run each.** `straight` was run three
  times and `corner_creep` twice; §3 and §4.2 state the spreads they
  found.
- **The heading dependence of §4.2 is measured, not explained.** The
  friction-pyramid hypothesis is named as a candidate and was not chased
  into gz's contact solver.
- **`ros2 topic hz`'s own frame loss (§7.5) is demonstrated, not
  root-caused** inside `ros2cli`.
- **`noise_probe.sh` was not re-run and not replaced.** Task 2's evidence
  cites it; `sensor_evidence.py analyse` is this task's instrument and
  the two agree where they overlap (nav lidar 0.019789 there, 0.019979
  here, on different captures a session apart).

---

## 9. The captures, by md5

The CSVs stay in `m5_ver3/logs/evidence/` and out of the repository —
`.gitignore:67` covers `m5_ver3/logs/`, and one static session alone is
16 MiB, the seven drive sessions another 87 MiB. `analyse` prints the md5
and the size of every file in a session it reads, so a figure in this file
can be traced to the bytes it came from.

> **RECOUNTED IN PLACE, 2026-08-26.** This paragraph read “one static
> session alone is 16 MB (the seven together are 79 MB)” over a table of
> **eight** sessions, and the 79 was never re-added up. What 79 was: the
> `drive-*` directories as they stood *before* the second `corner_creep`
> run was recorded — six of them, 82 427 135 bytes, 78.6 MiB — counted
> while the listing held seven directories in all. Recounted off the
> directory as it stands: **16 744 205 bytes** static (15.97 MiB),
> **90 989 931 bytes** across the seven drive sessions (86.78 MiB),
> **107 734 136 bytes** for all eight (102.74 MiB). Not one figure in the
> table below moved; the only thing that was wrong was the sum in the
> sentence above it.

| Session | File | md5 | Bytes |
|---|---|---|---|
| `static-rest-20260825-230717` | `scan_nav.csv` | `ef9d7cbfebf26f4768a55d58b49ec0e0` | 6 431 153 |
| ″ | `imu.csv` | `0864854e3f55e13c5025af598f6ac01f` | 539 574 |
| ″ | `depth.csv` | `074e63541976d529427b1fe395364d3f` | 2 126 395 |
| ″ | `safety_scan_back.csv` | `32164ba3d5990f30666ad760eef38b69` | 128 859 |
| ″ | `cam_info.csv` | `85ac34fcf9a1eb9c5fb120f165b63502` | 50 022 |
| ″ | `clock.csv` | `94eca643028c649f665991f9a94c3857` | 990 707 |
| ″ | `joint_state.csv` | `acbf3a61ca5dccbb5043e34e104a0054` | 2 120 499 |
| ″ | `drive_read_a.csv` | `cb99e91d7e7cc64e95c3d990ff2758f0` | 1 580 450 |
| ″ | `odom_truth.csv` | `0ef10f895f299117125ee3aefbe9005a` | 75 622 |
| ″ | `wheel_odom.csv` | `d84562c6a94aad54bca1950e0e413480` | 2 700 123 |
| ″ | `gz_rates.csv` | `4b88ef108f66f3d1bb881de1841210df` | 436 |
| `drive-straight-20260825-231657` | `odom_truth.csv` | `8bc2f2d05398fa9b25b2e91f12722548` | 49 314 |
| ″ | `wheel_odom.csv` | `fe8b3083b3f88ce144543fb06c8424c8` | 1 800 911 |
| ″ | `joint_state.csv` | `12ba9429c1c474d5302d0f868fdb6eab` | 1 419 636 |
| `drive-straight-20260825-231845` | `odom_truth.csv` | `ff394a86b9158d28daf457b880d38a8b` | 48 842 |
| ″ | `wheel_odom.csv` | `442e25d7d5995e78a16550f4bd957861` | 1 798 727 |
| ″ | `joint_state.csv` | `8eb6eee87567359410e364928fe873d3` | 1 417 766 |
| `drive-straight-20260825-231945` | `odom_truth.csv` | `32cdb79e7ac5f70ea8056f90efa0df01` | 48 940 |
| ″ | `wheel_odom.csv` | `05f436332c72543927716a98733f0ca5` | 1 801 822 |
| ″ | `joint_state.csv` | `14824f297816f177e60fcf10b66ca5c8` | 1 420 347 |
| `drive-square-20260825-232051` | `odom_truth.csv` | `f59b511b122b1a43f43afe42d7c72a79` | 78 518 |
| ″ | `wheel_odom.csv` | `a875e36f8fa530906d24e7e349baadb0` | 2 806 615 |
| ″ | `joint_state.csv` | `89820776662a18b4e737dd7a3828db16` | 2 257 781 |
| `drive-aisle-20260825-232216` | `odom_truth.csv` | `0df71e1b49b2306675f351926c20d095` | 103 474 |
| ″ | `wheel_odom.csv` | `b7addb2cc3b8417f44555386d1fa39ac` | 3 830 153 |
| ″ | `joint_state.csv` | `22785bc2eca67e95a78ca4d7533fb9d8` | 3 052 139 |
| `drive-corner_creep-20260825-232401` | `odom_truth.csv` | `c4f5ed4a1049fa78a23343a5b19ef41b` | 38 941 |
| ″ | `wheel_odom.csv` | `da102488cd43602a8233fba32cc1e3ea` | 1 373 425 |
| ″ | `joint_state.csv` | `9725a3796a763e82578c286f798ca88b` | 1 101 090 |
| `drive-corner_creep-20260825-234231` | `odom_truth.csv` | `34d2c10fc2f303a819a035dcc5912236` | 39 624 |
| ″ | `wheel_odom.csv` | `4d3d794a180273e301be59d096ac4074` | 1 389 362 |
| ″ | `joint_state.csv` | `1729774c83768b900256528b514547e4` | 1 100 033 |

**To reproduce any of it**, with the stack up and nothing else running:

```bash
source /opt/ros/jazzy/setup.bash
python3 m5_ver3/tools/sensor_evidence.py record --static
python3 m5_ver3/tools/sensor_evidence.py record --drive corner_creep
python3 m5_ver3/tools/sensor_evidence.py analyse      # needs no ROS at all
```
