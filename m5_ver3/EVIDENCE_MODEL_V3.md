# EVIDENCE — m5-ver3 sensor model (F1 Task 2)

Every number below was measured on this rig on **2026-08-25**, and the
instrument that produced it is named beside it. Where a figure is a
*datasheet* value it is labelled datasheet and is not a measurement of
anything; where it is *configured* it is what `model.sdf` asks for; where
it is *measured* it came off this plant through a named tool. The three
columns are never mixed.

**The rig.** WSL2 on Windows 11 · Ubuntu 24.04.4 LTS · 13th Gen Intel
Core i9-13900H, 20 threads · NVIDIA GeForce RTX 4050 Laptop GPU ·
gz-sim **8.11.0** · ROS 2 **Jazzy** · SDF version declared by the model
**1.8**. Repository at `/mnt/c/Users/ozkan/projects/amr-agent`, branch
`m5-ver3`. `~/.gz/rendering/ogre2.log` for the runs below reads
`GL_RENDERER = D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`; every run was
`./m5_ver3/m5v3.sh start --headless` unless it says otherwise, and the
GPU preflight passed on each (`gpu: D3D12 (NVIDIA GeForce RTX 4050 Laptop
GPU)`).

**The instruments.**

| Tool | What it answers |
|---|---|
| `m5_ver3/tools/rtf_probe.sh` | real-time factor of the running world, 30 s sample |
| `m5_ver3/tools/noise_probe.sh` | is the configured noise on the wire, and how big |
| `m5_ver3/tools/slip_bench.sh` | slip at steady cruise, forward and astern |
| `gz topic -f -t <topic> -d 20` | gz-side delivered rate |
| `ros2 topic hz <topic>` | ROS-side delivered rate |
| `gz topic -e --json-output` | the message itself, for geometry checks |

`noise_probe.sh` and `slip_bench.sh` are new in this task. Both source
`tools/_common.sh`, both read every constant from `config.yaml`, and both
attach to a stack `m5v3.sh` started rather than starting one.

---

## 1. The sensor set: datasheet, configured, delivered

Six rendering sensors and one IMU. The **datasheet** column is the device
class the profile models; the **configured** column is `model.sdf`; the
**delivered** column is measured, and its two halves are section 2.

| Sensor | Device class | Datasheet | Configured | Delivered (gz) | Delivered (ROS) |
|---|---|---|---|---|---|
| `nav_lidar` | SICK TiM571-2050101 | 15 Hz, 270°, 0.33°, 0.05–25 m, syst. ±60 mm, stat. <20 mm | 15 Hz, 811 rays over 270°, 0.05–25.0 m, gaussian σ 0.02 + bias σ 0.02 | **15.113 Hz** | **15.145 Hz** |
| `safety_scanner_back` | SICK nanoScan3 class | — (frozen, see §9) | 10 Hz, 275 rays over 275°, 0.10–8.0 m, gaussian σ 0.02 | **9.765 Hz** | not bridged |
| `safety_scanner_left` | ″ | ″ | ″ | **9.793 Hz** | not bridged |
| `safety_scanner_right` | ″ | ″ | ″ | **9.814 Hz** | not bridged |
| `nav_lidar_3d` | Ouster OS0-32 | 10 Hz, 360°×90°, 1024×32, 0.3–50 m, range precision 15–30 mm | 10 Hz, 1024×32, 0.3–50.0 m, gaussian σ 0.025 | **9.745 Hz** | not bridged (F2) |
| `pallet_cam` depth | Intel RealSense D455 | 640×480, 87° HFOV, 0.6–6 m, ~1 % error at 1 m | 15 Hz, 640×480, `horizontal_fov` 1.518, clip 0.6–6.0, gaussian σ 0.008 | **15.093 Hz** | **13.080 Hz** |
| `pallet_cam` camera_info | ″ | ″ | ″ | **15.143 Hz** | **15.143 Hz** |
| `imu` | Bosch BMI088 | 100 Hz, 0.1 °/s rms @47 Hz BW, 160/190 µg/√Hz | 100 Hz, per-axis gaussian, **no orientation** | **100.522 Hz** | **100.000 Hz** |

The IMU's noise numbers are m5_ver2's, derived there from BST-BMI088-
DS000-19 rev 1.9, and F1 did not touch them. What F1 did to the IMU was
**check the orientation claim** — §5.4.

Every datasheet figure traces to `docs/reports/m5v3-03` §1 and §4 and its
pinned sources 5 (TiM571), 6 (nanoScan3) and 9 (D455 depth accuracy); the
OS0 class figures to §4's Balyo/Ouster note.

---

## 2. Delivered rates, both sides

**Instrument:** `gz topic -f -t <topic> -d 20` (rolling 10-interval
windows, averaged over the 20 s) and `ros2 topic hz <topic>` for ~20 s.
Taken on the final model, one topic at a time, stack otherwise idle.

### gz side

| Topic | Configured | gz measured | windows |
|---|---|---|---|
| `/forklift/gz/scan_nav` | 15 | **15.1134** | 32 |
| `/forklift/gz/imu` | 100 | **100.5224** | 216 |
| `/forklift/gz/cam/depth_image` | 15 | **15.0933** | 32 |
| `/forklift/gz/cam/camera_info` | 15 | **15.1425** | 32 |
| `/forklift/gz/cam/image` | 15 | **15.0128** | 32 |
| `/forklift/gz/cam/points` | 15 | **15.1433** | 32 |
| `/forklift/gz/safety_scanner_back/measurement` | 10 | **9.7648** | 21 |
| `/forklift/gz/safety_scanner_left/measurement` | 10 | **9.7933** | 21 |
| `/forklift/gz/safety_scanner_right/measurement` | 10 | **9.8140** | 21 |
| `/forklift/gz/points3d` | 10 | **9.7449** | 21 |
| `/forklift/gz/points3d/points` | 10 | **9.7523** | 21 |

### ROS side

| Topic | Configured | ROS measured |
|---|---|---|
| `/clock` | 500 | **499.735** |
| `/forklift/gz/odom` | 20 | **19.989** |
| `/forklift/gz/scan_nav` | 15 | **15.145** |
| `/forklift/gz/imu` | 100 | **100.000** |
| `/forklift/gz/cam/depth_image` | 15 | **13.080** |
| `/forklift/gz/cam/camera_info` | 15 | **15.143** |

**Three readings in those tables need saying out loud.**

**(a) 15 Hz is delivered as ~15.15 Hz, and it is the world's step that
does it.** `ros2 topic hz` on `scan_nav` reports `min 0.062s max 0.071s`
around a mean of 0.066 s — and 0.066 s is exactly **33 steps of the
world's `max_step_size` 0.002 s**, not the 0.0666667 s a 15 Hz period
asks for. So the 15 Hz sensors land on a 33-step grid and run 1.0 % fast.
The 10 Hz sensors have no such error (0.1 s is 50 steps exactly) and nor
does the IMU (0.01 s is 5 steps). The mechanism inside gz was not chased
further; the figure is reported as measured and the configured value is
left at the device's own 15 Hz, because that is what the device is.

**(b) the unbridged sensors read below their 10 Hz, and asking is what
costs them.** gz renders a sensor only while something is subscribed, so
a `gz topic -f` on `points3d` or a safety scanner is what makes that
sensor render at all. The 9.74–9.81 Hz above is therefore the rate under
a real-time factor that the probe's own subscription depressed — §6 has
that RTF. Bridged sensors show no such sag because they are already
rendering.

**(c) the image bridge loses frames, and it is the only channel that
does.** Depth arrives gz-side at 15.093 Hz and ROS-side at 13.080 Hz —
**87 %**, with `ros2 topic hz` reporting a max interval of 0.199 s
against a 0.066 s mean, which is three frames missed at a stroke. An
earlier pass on the same sensor configuration measured 14.20–14.25 Hz
against 15.148, i.e. 94 %. So the loss is real, varies between 87 % and
94 %, and is confined to `ros_gz_image`'s `image_bridge`: `camera_info`,
which crosses on the *parameter* bridge from the same sensor at the same
instant, arrives at 15.143 Hz against 15.143 Hz — **100 %**. That is the
shape ros_gz issue #368 describes (the bridge delivering ~60 % of a
62 Hz target); at 15 Hz on one truck it is much milder but it is present,
and an F2 consumer that needs frame-accurate depth must not assume the
image and its info arrive together.

> **SEE §9.5's CORRECTION.** F1 Task 4 measured this channel with an
> rclpy subscriber instead of `ros2 topic hz` and found **no loss at
> all**, and the depth image and its `camera_info` frame-aligned to the
> nanosecond. The figures in this paragraph stand as readings of
> `ros2 topic hz`; they are not readings of the channel.
> `EVIDENCE_SENSORS.md` §7.5 carries the three-way measurement.

---

## 3. Everything advertises, and the four children come up

**Instrument:** `./m5_ver3/m5v3.sh start --headless`, `status`, `gz topic
-l`, `ros2 topic list`.

```
up. one truck, one world, two bridges.
  world      ALIVE   pid 36625   .../m5_ver3/logs/world.log
  bridge     ALIVE   pid 36710   .../m5_ver3/logs/bridge.log
  imgbridge  ALIVE   pid 36718   .../m5_ver3/logs/imgbridge.log
3 alive, 0 dead.
```

gz side, the eleven topics this model now carries (plus the four command
and state topics it always did):

```
/forklift/gz/cam/camera_info          /forklift/gz/points3d
/forklift/gz/cam/depth_image          /forklift/gz/points3d/points
/forklift/gz/cam/image                /forklift/gz/safety_scanner_back/measurement
/forklift/gz/cam/points               /forklift/gz/safety_scanner_left/measurement
/forklift/gz/imu                      /forklift/gz/safety_scanner_right/measurement
/forklift/gz/scan_nav
```

ROS side, on domain 97, exactly the six that are bridged and nothing
else: `/clock`, `/forklift/gz/odom`, `/forklift/gz/scan_nav`,
`/forklift/gz/imu`, `/forklift/gz/cam/depth_image` (with its four
`image_transport` variants) and `/forklift/gz/cam/camera_info`.
`points3d`, both point clouds and the colour image stay on the gz side.

**The GUI gate still closes.** Global Constraint 6 froze
`/forklift/gz/safety_scanner_back/measurement`, which is what `m5v3.sh`'s
GUI child waits on, so the gate should be unaffected — checked rather
than assumed. `./m5_ver3/m5v3.sh start` (window, no `--headless`) reached
**4 alive, 0 dead**, and `pgrep -af "gz sim -g"` returned pid 38063,
which is the pid `status` recorded for the `gui` child: the gated wrapper
saw the topic and `exec`'d the client.

---

## 4. The navigation lidar's 270° window

The device sees 270° and is blind over 90°, and where the blind sector
points is a mounting decision. `nav_lidar_link` carries no rotation, so
bearing 0 in the message is model **+x** — the counterweight end. This
vehicle's travel direction is model **−x** (`m6/ipc/follower.py` header:
model yaw 0 points the forks at world −x, travel heading is yaw + π,
forward traction is negative). The window is therefore centred on bearing
**π**:

```
min_angle = pi - 2.3561945 = 0.7853982
max_angle = pi + 2.3561945 = 5.4977871
```

**The rejected alternative** is the symmetric `-2.3561945 .. 2.3561945`.
It is the obvious spelling and it is wrong here: it centres the aperture
on model +x and puts the blind 90° squarely on the direction of travel,
which is the one bearing a navigation lidar may not lose. The F3
consumers are SLAM and AMCL and they want the widest stable window ahead
of the vehicle, not behind it.

**`min_angle > 0` with `max_angle > π` is legal SDF but nobody writes it,
so it was checked against known geometry rather than trusted.**

**Instrument:** `gz topic -e -t /forklift/gz/scan_nav --json-output`, one
sweep, truck at rest at the config spawn pose. What the message says:

```
angleMin 0.7853982   angleMax 5.4977871   angleStep 0.005817764074074074
count 811            verticalCount 1      rangeMin 0.05   rangeMax 25
frame  nav_lidar_link
```

811 rays over 4.7123889 rad is 0.3333° per ray — the TiM571's own angular
resolution, to four figures.

**The geometry.** Ground truth from `/forklift/gz/odom`: the truck rests
at `x -17.000000  y 10.000000  yaw 3.141590`. The lidar sits at model
`(0.55, −0.40, 1.80)`, so in the world it is at
`(−17.549999, 10.400001, 1.80)`. World bearing of ray *i* is
`0.7853982 + i·0.005817764 + yaw`. The warehouse's inner wall faces are
`WallWest x = −24.000`, `WallNorth y = 14.000`, `WallEast x = +24.000`
(all `pose ± half-size` from `m6/gazebo/warehouse_ver3.sdf`).

| Beam | World bearing | Expected | Measured | Error |
|---|---|---|---|---|
| 675 | 89.9998° (+y, WallNorth) | 3.599999 m | **3.600011 m** | +0.012 mm |
| 405 | 359.9998° (+x, WallEast at 41.55 m) | beyond `rangeMax` 25.0 | **Infinity** | — |
| 0 | 224.9999° (WallWest) | 9.121655 m | **9.130580 m** | +8.9 mm |
| 810 | 134.9998° (WallNorth) | 5.091153 m | **5.086187 m** | −5.0 mm |

The window is where it says it is. The residuals on beams 0 and 810 are
not the window; they are gz's own gpu_lidar accuracy at long range and
shallow incidence, characterised in §9.1. This capture was taken while
the noise block was producing nothing (§5.1), so it is a *noise-free*
reference and the errors above are the renderer's, not a draw.

---

## 5. Noise: is it on the wire?

**Instrument:** `m5_ver3/tools/noise_probe.sh`, vehicle at rest, 60 scans
(40 depth frames), per-reading standard deviation about that reading's
own mean across the frames. A stationary scan's spread *across* beams is
the room and says nothing; the spread across *time* at a fixed beam is
the noise.

### 5.1 The measured result, and one sensor that had to be changed to get it

| Sensor | Configured σ | Measured temporal σ (mean) | (median) | Readings | Frames |
|---|---|---|---|---|---|
| `nav_lidar` | 0.020 | **0.019789** | 0.019826 | 710 beams | 60 |
| `safety_scanner_back` | 0.020 | **0.019836** | 0.019734 | 195 beams | 60 |
| `nav_lidar_3d` | 0.025 | **0.024315** | 0.024590 | 20087 beams | 60 |
| `pallet_cam` depth | 0.008 | **0.007988** | 0.007986 | 256 pixels | 40 |

Not one reading in any of those four had a temporal σ of zero.

**But the nav lidar as the brief specified it produced no noise at all.**
Configured exactly as `docs/reports/m5v3-03` §1 gives it —
`gaussian_quantized`, σ 0.02, bias σ 0.02, `precision` 0.001 — the probe
returned:

```
beams finite in every frame  710 of 811
temporal stddev [m]   mean 0.000000  median 0.000000  min 0.000000  max 0.000000
readings with stddev 0 710 of 710
```

and five consecutive sweeps compared byte-for-byte were **identical**.
Zero noise, not small noise. The only change made was the noise **type**,
`gaussian_quantized` → `gaussian`, with `precision` removed because it
belongs to the type that was dropped; σ and the two bias elements were
left exactly as they were. The same probe then returned σ 0.019950. This
is Global Constraint 7's case and the ruling for it: measured truth beats
schema optimism. §9.2 is the defect writeup.

### 5.2 The quantization is not modelled, and that is stated rather than omitted

The TiM571 reports range in millimetres and nothing it produces is finer
than 1 mm. That is **not** modelled. `precision` only exists on the noise
type this sensor can no longer use, so the probe's quantization test
comes back uniform on every channel:

The test is the residual of every reading against a 1 mm grid,
`abs(v/p − round(v/p))` with `p = 0.001`:

| Channel | Mean residual | Max residual | Reading |
|---|---|---|---|
| `nav_lidar` | 0.250619 | 0.499990 | unquantized |
| `safety_scanner_back` | 0.246883 | 0.499996 | unquantized |
| `nav_lidar_3d` | 0.243117 | 0.500000 | unquantized |
| `pallet_cam` depth | 0.249312 | 0.499960 | unquantized |

A quantized channel would give ~0 here; an unquantized one is uniform on
[0, 0.5] with a mean near 0.25, which is what all four are. The modelled
lidar is therefore *finer* than the device, by 1 mm, in a channel whose
noise is 20 mm. Nothing downstream needs it and no artefact claims it.

### 5.3 The bias IS applied, and it is drawn once per run

`bias_mean` and `bias_stddev` are **not in the SDF schema for a lidar's
noise element** (§9.3), so whether they do anything had to be measured.
Method: the noise-free capture of §4 is per-beam geometric truth for this
exact pose; a run *with* noise gives a per-beam 60-frame mean; the
difference, if a bias exists, is the *same* number on every beam. Three
consecutive `stop` / `start --headless` cycles, nothing else changed:

| Run | Temporal σ (mean) | Common offset across 710 beams (mean) | (median) |
|---|---|---|---|
| 1 | 0.019950 | **+0.019292 m** | +0.019366 |
| 2 | 0.019871 | **+0.007216 m** | +0.007165 |
| 3 | 0.019964 | **+0.003233 m** | +0.003402 |

The white noise is the same every run; the offset is a different number
every run. That is a per-run draw, which is what `bias_stddev 0.02` asks
for, and all three draws are inside 1σ of it. Run 1's per-beam spread of
that offset was `min 0.011651  max 0.026718` about a mean of 0.019292 —
±0.0077, which is ±3× the 0.02/√60 = 0.00258 sampling error of a
60-frame mean, exactly. So the offset is common-mode and the spread
around it is only the finite sample. The truck's resting pose was
verified identical (`x −17.000000  y 10.000000`) before each capture, so
the geometry being differenced is the same geometry.

### 5.4 The IMU emits no oracle orientation — and does not say so the way the model claimed

`<enable_orientation>false</enable_orientation>` was already in the model
and is **honoured**. What is *not* true is the sentence the model's own
comment used to carry, that the message would then set
`orientation_covariance[0] = -1`. Measured on gz-sim 8.11.0 with ros_gz
on Jazzy:

```
gz .....  gz.msgs.IMU has NO orientation field (protobuf omits it) and
          orientationCovariance is {0,0,0,0,0,0,0,0,0}
ROS ....  sensor_msgs/Imu carries orientation (0.0, 0.0, 0.0, 0.0) - the
          default-constructed quaternion, not a rotation - and
          orientation_covariance is nine zeros. NOT -1.
```

So the refusal is real (there is no ground-truth heading on this topic)
but it is **not self-announcing**: a consumer that reads the field
without checking gets a zero quaternion rather than a documented refusal.
The model comment has been corrected to say this, and the consequence is
recorded there: `ekf.yaml`'s three false entries in `imu0_config` are the
only one of the two refusals a careless consumer cannot walk past.

The IMU noise itself is live: at rest the angular-velocity channels read
`(0.00182, −0.00367, 0.00239)` rad/s against a configured white σ of
0.001745 and a bias magnitude of 0.002618, and `linearAcceleration.z`
reads 9.8079 m/s².

---

## 6. Real-time factor, against the Task 1 baseline

**Instrument:** `m5_ver3/tools/rtf_probe.sh`, 30 s off
`/world/warehouse/stats`, GPU on, headless, nothing else on the machine.

**What is subscribed decides what is rendered**, so each row names its
stack. Rows 3–4 are the stack `m5v3.sh` actually starts.

| # | Configuration | Samples | Mean | Median | Floor | Ceiling |
|---|---|---|---|---|---|---|
| 1 | **Task 1 baseline** — ver3 model unmodified, bridge on clock + odom + scan_nav | 296 | 0.9985 | 0.9999 | 0.9429 | 1.0399 |
| 2 | ″ (second pass) | 296 | 0.9996 | 0.9999 | 0.9408 | 1.0706 |
| 3 | **F1 model, stack as started** — six sensors present, bridge on clock + odom + scan_nav + imu + cam depth + cam info | 296 | **0.9997** | **0.9999** | **0.9577** | 1.2190 |
| 4 | ″ (second pass) | 296 | **0.9995** | **0.9999** | **0.9574** | 1.0660 |
| 5 | as row 3, **+ a subscriber on `points3d`** (`gz topic -e`, printing) | 293 | 0.8395 | 0.9998 | 0.1003 | 2.8089 |
| 6 | as row 3, **+ a subscriber on `points3d`** (`gz topic -f`, not printing) | 294 | 0.8861 | 0.9998 | 0.1127 | 2.6256 |
| 7 | ″ (second pass) | 292 | 0.8512 | 0.9998 | 0.1120 | 3.1320 |
| 8 | **every sensor subscribed** — three safety scanners, `points3d`, colour image, plus row 3's bridge | 288 | 0.8334 | 0.9999 | 0.0608 | 1.5023 |
| 9 | ″ (second pass) | 286 | 0.8009 | 0.9999 | 0.0410 | 1.0124 |

**Rows 3 and 4 are the headline: the full sensor set costs nothing
measurable.** Mean 0.9995–0.9997 against the baseline's 0.9985–0.9996,
median identical at 0.9999, and the floor is *better* (0.9574–0.9577
against 0.9408–0.9429). Two earlier passes on an intermediate model gave
0.9991 and 0.9997, so the figure is stable across four passes. The nav
lidar going from 360 rays at 10 Hz to 811 at 15 Hz, an RGB-D camera at
15 Hz and a 32768-ray lidar being *present* are together inside the
noise of this measurement — because a gz sensor that nothing subscribes
to is not rendered, and because the two that are rendered (nav lidar,
camera) are cheap at one truck.

**Rows 5–7 are the 3D lidar's price, and it is the render, not the
subscriber.** Rows 5 and 6 differ only in whether the subscriber prints
32768 ranges as text or counts them, and they agree — 0.8395 against
0.8861/0.8512. So subscribing to `points3d` costs about **0.13 of mean
RTF**. The median stays at 0.9998 while the floor collapses to 0.11: the
simulator is not running slow, it is **stalling and catching up**, once
per sweep. This is why `points3d` is not bridged until F2 has a consumer
for it — and it is a figure a four-truck fleet would have to multiply.

**Rows 8–9 are the worst case:** every sensor on this vehicle rendering
at once, mean 0.80–0.83, floor 0.04–0.06.

---

## 7. WheelSlip tuning

> **CORRECTED BY MEASUREMENT 2026-08-26 (phase F1.5) —
> `EVIDENCE_LATERAL_TUNE.md`. Not one figure below is rewritten and every
> one of them still repeats on the rig.** Three things in this section
> read differently after the corner was measured, and each is marked
> again where it appears:
>
> 1. **The plant this table was measured on had the wheel-slip system on
>    ONE wheel of three.** The two rear wheels now carry it too, at the
>    same 7.0 and at their own normal force, because with them rigid the
>    truck delivered 0.410 of its kinematic yaw at creep and 99.5 % of
>    that deficit was the steered wheel sliding to overcome them. The
>    accepted longitudinal slip is unchanged by the addition: **0.95603 %
>    against this section's 0.96037 %**, re-measured with the same bench.
> 2. **The two elements' effects are swapped relative to their names.**
>    Every row of the table below moved `slip_compliance_lateral` and
>    `slip_compliance_longitudinal` together, so it could not tell them
>    apart; moved separately, it is the element named *lateral* that
>    carries the whole of this figure. `EVIDENCE_LATERAL_TUNE.md` §3.1
>    has the five-row measurement, and its 1.0 and 0.1 rows land on
>    **0.10688 %** and **0.01070 %** — this table's own values.
> 3. **"It costs nothing on a straight run" is the one inference here
>    that was wrong.** The measurement under it — two micrometres of
>    lateral wander over 21 m — is right and reproduces. See the marked
>    paragraph at the foot of this section.

**Instrument:** `m5_ver3/tools/slip_bench.sh`. It commands the traction
terminal directly (`/forklift/gz/actuator/traction_cmd`, the motor
terminal, since m5-ver3 runs no vehicle stack yet), discards a 5 s
settling window, then measures ground-truth displacement over 10 s —
forward (model −x, negative ω) and astern. Slip is

```
(commanded tread speed - ground truth speed) / commanded tread speed
```

at the 0.7 m/s cruise `m6/ipc/follower.py` drives. The bench also samples
the drive joint's **achieved** rate, so a controller shortfall could be
told apart from slip at the tyre. Target band: **0.5–2 %**.

| `slip_compliance_*` | Forward | Astern | Mean slip vs command | Mean slip vs achieved joint rate | Verdict |
|---|---|---|---|---|---|
| **no plugin** (Task 1 model) | 0.00621 % | 0.00001 % | **0.00311 %** | 0.00310 % | baseline — the contact is rigid |
| 0.01 | 0.00108 % | 0.00108 % | **0.00108 %** | 0.00107 % | rejected: 500× under the band |
| 0.1 | 0.01070 % | 0.01070 % | **0.01070 %** | 0.01070 % | rejected: 50× under |
| 1.0 | 0.10687 % | 0.10687 % | **0.10687 %** | 0.10687 % | rejected: 5× under |
| 5.0 | 0.56320 % | 0.56321 % | **0.56321 %** | 0.56320 % | inside the band, but on its floor |
| **7.0** | 0.95859 % | 0.96215 % | **0.96037 %** | 0.96037 % | **accepted** |
| 10.0 | 2.08405 % | 2.09261 % | **2.08833 %** | 2.08833 % | rejected: above the band |

Each row is a full `stop` / edit / `start --headless` / bench cycle on
the same rig with nothing else running.

**Reproducibility.** 7.0 was run again after `wheel_normal_force` was
corrected from 4537.6 N to 4537.4 N (§7.1): **0.95956 %** forward
0.95901, astern 0.96010 — 0.0008 percentage points from the tuning row.
An intermediate confirmation at 4537.6 N gave 0.96241 %. So the figure
repeats to about ±0.002 pp and the 0.2 N correction to the normal force
moved it by less than that.

**Why 7.0 and not 5.0 or 10.0.** 10.0 is outside the band. 5.0 sits at
0.56 %, four hundredths above the floor of it, which leaves no room for
the band to be approached from either side by anything that changes the
load. 7.0 lands at 0.96 %, near the middle of 0.5–2 % on a log scale and
close to what a polyurethane tyre on concrete actually does at cruise.

**`slip_cmd` and `slip_joint` are equal to five decimal places in every
row.** The drive joint reached 5.83333300 rad/s — the commanded
5.833333 — in every single segment of every run. So none of the
shortfall is the JointController failing against its 500 N·m effort
limit; all of it is the contact patch. That is the reading the bench
exists to make possible.

**Lateral compliance was set equal and not tuned, and it costs nothing on
a straight run.** After the confirmation run's 21 m out-and-back the
truck's ground-truth `y` had moved from `10.000000` to `10.000002` — two
micrometres. A lateral compliance of 7.0 does not make this vehicle
wander in a straight line. What it does in a *turn* is unmeasured, and
the model comment says so: the phase that measures a turn is the phase
that gets to change it.

> **CORRECTED BY MEASUREMENT 2026-08-26 (F1.5), and the two micrometres
> are not what is corrected.** `EVIDENCE_LATERAL_TUNE.md` §3.1. Held at
> 7.0 while `slip_compliance_longitudinal` alone was taken to 1.0 and to
> 0.1, this bench reads 0.95842 % and 0.96140 % — unchanged. Held at 7.0
> while `slip_compliance_lateral` alone was taken to 1.0 and to 0.1, it
> reads **0.10688 %** and **0.01070 %**. So lateral compliance does not
> cost this vehicle sideways wander, exactly as measured above, and it
> costs the straight run **the whole of its 0.96 % of longitudinal
> slip** — which is the sentence's inference and not its measurement.
> The phase that measured the turn was F1.5 and it left the value at
> 7.0: the corner selects it too, and every setting that made the two
> unequal brought back the heading dependence of
> `EVIDENCE_SENSORS.md` §4.2.

### 7.1 `wheel_normal_force`, derived from the model's own numbers

> **QUESTIONED BY MEASUREMENT 2026-08-26 (F1.5) AND NOT CHANGED —
> `EVIDENCE_LATERAL_TUNE.md` §7.** `base_link` and `mast` each carry an
> `<inertial><pose>` that repeats their own `<link><pose>`, and SDFormat
> composes those two rather than replacing one with the other. The sum
> below is over the link poses alone, so if the composition is what gz
> uses then `sum(m x)` is −100.751 kg·m, the centre of mass is at
> x = −0.086411 m, and `N_drive` is **4503.8 N** rather than 4537.4 —
> 0.74 % away, which is 0.74 % of a compliance and 0.007 points of the
> slip figure above. The constant is left alone: the masses and inertial
> poses are outside F1.5's scope, and this whole table was measured
> against 4537.4 N, so correcting it means re-driving the table and not
> editing its rows. The rear pair added in F1.5 is derived by the SAME
> method as below, from the same numbers, so the three normal forces are
> one opinion about one vehicle.

Read out of `model.sdf` by script and checked against the file:

```
links 16   total mass 1165.95 kg   sum(m x) -97.151 kg m   com x -0.083323 m
W       = 1165.95 x 9.80665                      = 11434.06 N
N_drive = W x (-0.083323 - (-0.50)) / (0.55 - (-0.50))
        = 11434.06 x 0.396835                    =  4537.4 N
```

The drive contact is at model `x = +0.55`, the rear axle at `x = −0.50`,
a 1.05 m wheelbase. Treating the 50 kg of wheel and steer yoke as
unsprung and carrying it straight to the ground instead — body mass
1115.95 kg, body CoM `x = −0.092881`, giving 4243.2 N through the beam
plus 294.2 N unsprung — gives **4537.4 N as well**. The two models agree
to 0.01 N, so the beam is used and the distinction is not drawn. 39 % of
the vehicle on one wheel, which is what a counterbalance truck with its
load end empty does.

`wheel_radius` is 0.12 m, the `drive_wheel` collision cylinder's radius.
It is not a parameter; it is a fact about the wheel.

---

## 8. The 3D lidar's view of its own vehicle

A 360°×90° lidar on a roof sees the roof. That is not a defect and it is
not masked here — this file is geometry and sensing, and deciding which
returns are the vehicle is the consumer's job. It is measured and written
down so the F2 consumer does not discover it as a bug.

**Instrument:** `gz topic -e -t /forklift/gz/points3d --json-output
-n 1`, truck at rest. 32 rows 2.903° apart from −45.00° to +45.00°, 1024
bearings each. 20087 of 32768 rays returned a finite range.

| Row | Elevation | Finite | < 1.5 m | min | max | at exactly 0.300 |
|---|---|---|---|---|---|---|
| 0 | −45.00° | 1024 | 136 | 0.844 | 1.210 | 0 |
| 1 | −42.10° | 1024 | 153 | 0.793 | 1.165 | 0 |
| 2 | −39.19° | 1024 | 149 | 0.759 | 1.251 | 0 |
| 3 | −36.29° | 474 | 106 | 0.730 | 1.235 | 0 |
| 4 | −33.39° | 228 | 44 | 0.715 | 0.823 | 0 |
| 5 | −30.48° | 46 | 0 | — | — | 0 |
| 6 | −27.58° | 1024 | **1024** | 0.300 | 0.390 | **475** |
| 7 | −24.68° | 1024 | **1024** | 0.300 | 0.411 | **87** |
| 8 | −21.77° | 1024 | **1024** | 0.304 | 0.464 | 0 |
| 9 | −18.87° | 1024 | **1024** | 0.351 | 0.513 | 0 |
| 10 | −15.97° | 1024 | 720 | 0.433 | 0.584 | 0 |
| 11 | −13.06° | 1024 | 528 | 0.546 | 0.713 | 0 |
| 12–20 | −10.16° … +13.06° | 1024 (falling to 793) | 44–144 | 0.590 | 0.915 | 0 |
| 21–26 | +15.97° … +30.48° | 524 → 18 | 0 | — | — | 0 |
| 27–31 | +33.39° … +45.00° | **0** | 0 | — | — | 0 |

**Reading it.** Rows 6–9 are the **overhead guard roof**, a full
1024-bearing ring at 0.300–0.513 m — the plate is 0.14 m below the
optical origin, so slant = 0.14/sin(elevation). Rows 10 and 11 are the
same plate seen more shallowly: 720 and 528 bearings of 1024, because the
plate is 1.24 × 0.88 and a shallow beam still reaches it fore and aft
while missing it abeam. Row 5 is where the roof falls inside the 0.3 m
minimum (0.14/sin 30.48° = 0.276 m) and 978 of 1024 bearings return
nothing. Rows 0–4 and 12–20 are the four **overhead-guard posts**, the
**mast rails** at (−0.78, ±0.30) rising to z 2.05 and the **crossmember**
above them, at 0.59–1.25 m. Rows 27–31 see nothing at all: this warehouse
has no ceiling.

**Nothing is attributable to the sensor's own post or housing.** Both
finish below z 1.84, within 0.09 m of the optical origin, and no reading
anywhere in the sweep falls below 0.300 m.

**Two gz behaviours this table pins down.** A return closer than
`<range><min>` comes back **clamped to the minimum**, not as a
no-reading: 562 readings in rows 6 and 7 are exactly 0.300. A return
closer still comes back as **a no-reading**, not as whatever lies behind
it. So near geometry is neither invisible nor honest to a gz lidar; it is
a wall of readings at the range minimum, and a consumer must treat
`range == rangeMin` as suspect.

### 8.1 The pallet camera lands where the arithmetic put it

`pallet_cam_link` is at model `(−0.90, 0.40, 1.10)` with yaw π and pitch
+0.5235988 (30° down). The optical axis should therefore meet the floor
at slant `1.10 / sin 30° = 2.200 m`. The noise probe's central 16×16
patch, which is where that axis lands, measured a mean depth of
**2.201198 m** across 40 frames (an independent run gave 2.201382 m). The
mount, the pitch and the depth channel all agree to about a millimetre —
which is an eighth of the 8 mm depth noise on the same pixels.

---

## 9. Known gz defects, with their issue numbers

Nothing in this section is worked around. Each item is what was measured,
what it means for a consumer, and where upstream it lives.

### 9.1 gpu_lidar accuracy at shallow incidence — gz-sim #2743 (open, 2025-01-29)

Measured on the **noise-free** capture of §4, so this is the renderer
alone with no draw in it. All 469 beams whose nearest wall plane is
inside range, error against the analytic plane intersection, binned by
the angle between the ray and the wall it hits:

| Grazing angle | Beams | Mean distance | Mean abs error | Max abs error |
|---|---|---|---|---|
| 0–10° | 5 | 22.255 m | **147.1 mm** | 283.8 mm |
| 10–20° | 43 | 16.425 m | 53.1 mm | 136.7 mm |
| 20–30° | 60 | 12.070 m | 23.4 mm | 74.5 mm |
| 30–45° | 90 | 8.370 m | 8.0 mm | 25.6 mm |
| 45–60° | 91 | 4.616 m | 2.4 mm | 8.9 mm |
| 60–75° | 90 | 3.912 m | 1.4 mm | 3.1 mm |
| 75–90° | 90 | 3.642 m | **0.5 mm** | 1.8 mm |

Monotone across three orders of magnitude. Near normal incidence the
renderer is accurate to half a millimetre — better than the device it
models by a factor of forty. At 10° grazing it is out by 147 mm, seven
times the modelled noise. gz sim has no CPU ray sensor to fall back to
and there is no fix upstream. **What it means:** a rack upright or a
pallet face seen obliquely at range is the case where this model is least
trustworthy, and an F3 scan-matcher's residuals on long aisle walls carry
this error, not only the noise block's.

The grazing bins are confounded with distance — a grazing beam from this
mount is also a long one — and this measurement does not separate the
two.

### 9.2 `gaussian_quantized` silently disables lidar noise — gz-sensors, no issue found

**Measured, both directions, same model, one element changed.**

| `<type>` | Other noise elements | Measured temporal σ over 710 beams |
|---|---|---|
| `gaussian_quantized` | σ 0.02, bias σ 0.02, `precision` 0.001 | **0.000000** (all 710 beams; five sweeps byte-identical) |
| `gaussian` | σ 0.02, bias σ 0.02 | **0.019789** |

A `gpu_lidar` configured `gaussian_quantized` produces **no noise at
all** — not quantized noise, not unquantized noise, nothing — and gz logs
no warning about the type. The failure is silent and it fails *open*: a
model that asks for more realism gets less, and a run that never measured
it would report a perfectly clean scan as a noisy one.

`docs/reports/m5v3-03` §1 recommends exactly this configuration, from the
SDF 1.11 `noise.sdf` schema, and the schema is real — but §9.3 shows
`lidar.sdf` never includes it. No upstream issue was found for this
specific behaviour; it is recorded here with the measurement that
produced it. **The model uses `gaussian` and states the quantization as
not-modelled** (§5.2).

### 9.3 `lidar.sdf` declares its own `<noise>` and it is not `noise.sdf`

`sdformat14`'s `1.8/lidar.sdf` — and `1.11/lidar.sdf` alike — declares an
inline `<noise>` element carrying **only** `type`, `mean` and `stddev`.
It does not `<include>` `noise.sdf`, which is where `bias_mean`,
`bias_stddev`, `dynamic_bias_stddev`, `dynamic_bias_correlation_time` and
`precision` live. So on every SDF version, not only the 1.8 this model
declares, a lidar's bias and precision elements are undeclared, and gz
says so at load:

```
Warning [Utils.cc:132] [.../sensor[@name="nav_lidar"]/lidar/noise/bias_mean:
  ...model.sdf:L824]: XML Element[bias_mean], child of element[noise],
  not defined in SDF. Copying[bias_mean] as children of [noise].
```

The warning is not fatal and the elements are **not** ignored: sdformat
copies them through and `sdf::Noise::Load` reads them, which is why §5.3
measures a real per-run bias. But nothing in the schema promises that,
the warning is indistinguishable from a typo, and it appears three times
per load in `logs/world.log`. `<gz_frame_id>` produces the identical
warning on all seven sensors and always has — it is m6's file's behaviour
too, and gz-sim reads it regardless.

### 9.4 Depth noise is additive only — gz-sensors #416 (open, 2024-03-09)

gz-sensors applies only an additive gaussian to depth. The real D455's
error is roughly quadratic in range: about 1 % (2.5–5 mm) at 1 m, ~4 cm
RMS at 2 m. The model configures 8 mm as a **floor** and says so in the
SDF; measured, the channel delivers 7.988 mm at a patch depth of 2.20 m,
where the device would be four to five times worse. **This camera is
optimistic at range by construction.** The quadratic σ(z) belongs to a
ROS-side refinement in a later phase and no depth realism is claimed from
the SDF alone.

### 9.5 `ros_gz_image`'s bridge drops depth frames

§2(c). 87–94 % of the gz-side rate, against 100 % for `camera_info` from
the same sensor across the parameter bridge. Same family as ros_gz #368.

> **CORRECTED BY MEASUREMENT, 2026-08-25 (F1 Task 4).** The reading above
> is real; the attribution is not. `EVIDENCE_SENSORS.md` §7.5 shows the
> frames are on the wire and `ros2 topic hz` is losing them: a plain
> rclpy subscriber takes **909 of 909** depth frames over 60 s with every
> sim-time interval exactly 0.066 s, at queue depths 1, 10 and 500 alike,
> while `ros2 topic hz` on the same topic at the same instant reads
> 8.98 Hz. `camera_info` is frame-aligned with the depth image to the
> nanosecond, all 909 of them. **The bridge does not drop frames on this
> stack; the measuring subscriber did.** §2(c)'s figures stand as
> readings of `ros2 topic hz` and not of the channel.

### 9.6 The camera cannot see the vehicle in front of it

Not a gz defect but the same class of thing, and it is stated in the SDF.
Everything of this truck ahead of the lens — the mast rails 0.13 m away,
the carriage, the bracket — lies inside the camera's 0.6 m near clip, and
a rasteriser does not occlude with geometry it has clipped: it renders
straight through. A real D455 mounted here would have the left rail
across part of its view. The modelled camera sees **more** than the
device would, and framing that as realism would be a lie. It is the same
0.6 m the device has as its minimum depth, and the honest statement is
that this camera has no opinion about anything closer than 0.6 m.

---

## 10. The safety-scanner freeze

Global Constraint 6: the three `safety_scanner_*` sensors keep their
geometry, sample counts, update rates, ranges and topics byte-identical
to `m6/gazebo/forklift_ver2/model.sdf`, and the only permitted change is
the additive gaussian noise block.

**Instrument:** each `<link name="safety_scanner_*_link"> … </link>`
block extracted from both files by the same script and diffed. All three
diffs are the same, and this is the whole of one of them:

```diff
--- v2 safety_scanner_back_link
+++ v3 safety_scanner_back_link
@@ -55,6 +55,22 @@
             <max>8.0</max>
             <resolution>0.01</resolution>
           </range>
+          <!-- THE ONLY THING F1 CHANGED ABOUT THIS SENSOR. nanoScan3-class
+               statistical error, 20 mm, as white noise on the range.
+               Everything else here - the aperture, the 275 samples, the
+               10 Hz, the 0.10 to 8.0 m and the topic - is frozen: the
+               field evaluation outside this file and the PLC's own case
+               table are written against those numbers, and a scanner
+               whose geometry moves under a committed field is a different
+               device. Plain gaussian and no bias term: what the safety
+               layer needs to see is that a range reading is not exact,
+               and a per-device systematic offset is not something any
+               artefact downstream of here has measured. -->
+          <noise>
+            <type>gaussian</type>
+            <mean>0.0</mean>
+            <stddev>0.02</stddev>
+          </noise>
         </lidar>
       </sensor>
     </link>
```

One hunk, in all three links, and it is the noise block and the comment
that explains it. Nothing else in those links differs from m6's file: not
the link pose, not the yaw, not the inertial, not the housing visual, not
`always_on`, not `update_rate`, not `visualize`, not the topic, not the
275 samples, not the 275° aperture, not the 0.10–8.0 m range.

The message on the wire confirms it from the other side — `gz topic -e`
on `/forklift/gz/safety_scanner_back/measurement` reports `angleMin
-2.3998277  angleMax 2.3998277  count 275  rangeMin 0.1  rangeMax 8`, and
the topic still exists to gate the GUI client (§3).

**No bias term on these three.** What the safety layer needs to see is
that a range reading is not exact. A per-device systematic offset is not
something any artefact downstream of this file has measured, and adding
one would put an unmeasured number into the input of a field evaluation.

---

## 11. What this task did not do

- **`points3d` is not bridged.** Its ROS consumer arrives in F2; §6 rows
  5–7 are what bridging it would cost today.
- **Neither point cloud is bridged**, and the colour image is not either.
  `docs/reports/m5v3-03` §5 and ros_gz #368 are the reason.
- **The IMU's noise was not touched.** It was already derived from a data
  sheet in m5_ver2 and there was nothing here to improve. Only the false
  claim in its comment was corrected (§5.4).
- **The ground-truth `OdometryPublisher` is still in the model** and is
  still bridged. It is this task's measurement reference — every number
  in §7 comes off it — and taking it out of the estimator is F2's job,
  which the model's own two-phase note already sets out.
- **Lateral slip compliance is set, not tuned** (§7).
- **The quadratic depth-error model is not built** (§9.4).
- **`gaussian_quantized`'s failure has no upstream issue number** because
  none was found for it; §9.2 is the measurement instead.
