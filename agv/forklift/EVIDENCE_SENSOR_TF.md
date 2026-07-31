# EVIDENCE — sensor frames, and the measurement channel the process stop reads

What this file records, in one sentence: the three sensor frames exist in
TF and agree with `model.sdf`, and the M4 process obstacle stop now reads
the **front safety scanner's non-safe measurement channel**, checked in a
running simulation rather than asserted.

**Every block below is quoted from the output of the command named above
it.** No number in this file was computed by hand, and no figure appears
that no tool printed (LESSONS 2026-07-27).

| Item | Value |
|---|---|
| Date | **2026-07-30**, 21:52 UTC |
| Environment | **Session container**, not the owner's WSL host: Ubuntu 24.04.4, ROS 2 Jazzy, Gazebo Sim 8.11.0, `/usr/bin/python3` 3.12.3, headless, software rasteriser. The toolchain and its versions are `sim/setup/CONTAINER_TOOLCHAIN.md` |
| Isolation | `GZ_PARTITION=m506tf3`, `ROS_DOMAIN_ID=85`, `QT_QPA_PLATFORM=offscreen`. Both transports, because `ROS_DOMAIN_ID` does not isolate gz |
| Repository state | `HEAD c14efac`, plus this brief's uncommitted working tree |
| World | `sim/worlds/forklift_arena.sdf`, unmodified and not owned here |
| Under test | `model.sdf`, `config.yaml`, `scripts/sensor_tf.py`, `scripts/obstacle_zone.py`, `scripts/check_sensor_frames.py`, `scripts/obstacle_matrix.py`, `launch/vehicle.launch.py` as this brief leaves them |

**This is container evidence.** The owner's WSL host is a separate
environment with its own record and has never run this configuration.
Nothing here is evidence about it.

---

## 1. The agreement check, with no simulator running

`/usr/bin/python3 agv/forklift/scripts/check_sensor_frames.py`

```
== 1. model.sdf supports a static sensor transform =========================
ok    sensor_tf.read_model accepts the model                     3 frame(s), parent forklift/base_link

parent                       child                           x [m]    y [m]    z [m]  roll [d] pitch [d]   yaw [d]
forklift/base_link           nav_lidar_link                 0.5500  -0.4000   1.8000    0.0000    0.0000    0.0000
forklift/base_link           safety_scanner_front_link      0.7000   0.4500   0.1500    0.0000    0.0000   45.0000
forklift/base_link           safety_scanner_rear_link      -0.7000  -0.4500   0.1500    0.0000    0.0000 -135.0000

== 2. README.md scanner table vs model.sdf =================================
ok    README declares one row per SDF sensor                     README ['nav_lidar', 'safety_scanner_front', 'safety_scanner_rear'] / SDF ['nav_lidar', 'safety_scanner_front', 'safety_scanner_rear']
ok    README frame name for nav_lidar                            nav_lidar_link vs nav_lidar_link
ok    README pose for nav_lidar                                  dx 0.00e+00 dy 0.00e+00 dz 0.00e+00 m, dyaw 0.00e+00 rad
ok    README frame name for safety_scanner_front                 safety_scanner_front_link vs safety_scanner_front_link
ok    README pose for safety_scanner_front                       dx 0.00e+00 dy 0.00e+00 dz 0.00e+00 m, dyaw 3.66e-08 rad
ok    README frame name for safety_scanner_rear                  safety_scanner_rear_link vs safety_scanner_rear_link
ok    README pose for safety_scanner_rear                        dx 0.00e+00 dy 0.00e+00 dz 0.00e+00 m, dyaw 9.81e-09 rad

== 3. config.yaml frames: block vs model.sdf ===============================
ok    config frames.base == SDF <robot_base_frame>               forklift/base_link vs forklift/base_link
ok    config frames.nav_lidar == SDF link/gz_frame_id            nav_lidar_link vs nav_lidar_link
ok    config frames.safety_scanner_front == SDF link/gz_frame_id safety_scanner_front_link vs safety_scanner_front_link
ok    config frames.safety_scanner_rear == SDF link/gz_frame_id  safety_scanner_rear_link vs safety_scanner_rear_link

== 4. topic contract and the channel-naming rule ===========================
ok    every SDF topic is declared in config.yaml                 missing: []
ok    every config gz_ topic exists in model.sdf                 extra: []
ok    every reachable safety-scanner channel is named a measurement one /forklift/gz/safety_scanner_front/measurement; /forklift/gz/safety_scanner_rear/measurement
ok    no safe channel appears as a topic on either transport     

== 5. the process consumer reads a sector that is straight ahead ===========
ok    the consumed ROS topic is the front measurement channel    /forklift/safety_scanner_front/measurement <- /forklift/gz/safety_scanner_front/measurement
ok    sector_centre_rad == -(mount yaw of safety_scanner_front)  centre -0.7853982 + yaw 0.7853982 = 0.00e+00 rad
ok    the sector lies inside that sensor's aperture              sector [-75.0, -15.0] deg in aperture [-137.5, 137.5] deg
      in the vehicle frame that is [-30.0, +30.0] deg about the driving direction
      clear-horizon value this consumer will publish is the scan's own range_max = 5.50 m

RESULT: PASS (19 check(s), 0 failing)
```

**Why the two `dyaw` residuals are not zero, and why the tolerance is
what it is.** `model.sdf` writes the front scanner's yaw as `0.7853982`
— seven decimals of a radian — while README.md writes the same angle as
`+45°`. The two differ by `3.66e-08` rad **by construction**, and no
edit of either document removes it: one of them would have to stop being
readable. The tolerance is `1e-6` rad, which is above that rounding and
below anything physical — 0.2 arcsec is 5.5 µm of lateral error at the
5.50 m end of this sensor's range.

---

## 2. The same check against a running graph

`check_sensor_frames.py --live --timeout 25`, sections 1–5 identical to
above and omitted here; section 6 is the new part:

```
== 6. the running graph ====================================================
ok    /tf_static carries every sensor frame                      received: ['nav_lidar_link', 'safety_scanner_front_link', 'safety_scanner_rear_link']
ok    published transform for nav_lidar_link matches model.sdf   parent forklift/base_link d_xyz 0.00e+00 m d_quat 0.00e+00
ok    published transform for safety_scanner_front_link matches model.sdf parent forklift/base_link d_xyz 0.00e+00 m d_quat 0.00e+00
ok    published transform for safety_scanner_rear_link matches model.sdf parent forklift/base_link d_xyz 0.00e+00 m d_quat 0.00e+00
ok    tf2 resolves forklift/base_link -> nav_lidar_link          
ok    tf2 resolves forklift/base_link -> safety_scanner_front_link 
ok    tf2 resolves forklift/base_link -> safety_scanner_rear_link 
ok    /forklift/safety_scanner_front/measurement header.frame_id is the published frame safety_scanner_front_link vs safety_scanner_front_link
      /forklift/safety_scanner_front/measurement: 275 samples, [-137.5, +137.5] deg, range [0.10, 5.50] m
ok    /forklift/scan header.frame_id is the published frame      nav_lidar_link vs nav_lidar_link
      /forklift/scan: 360 samples, [-180.0, +180.0] deg, range [0.10, 8.00] m

RESULT: PASS (28 check(s), 0 failing)
```

The three checks that matter beyond "a transform was published" are the
frame-id ones: **the frame TF publishes is the frame the scan itself
names**, so a consumer that looks up a scan's own `header.frame_id`
resolves it. That is the failure this whole section exists to exclude.

`ros2 run tf2_ros tf2_echo forklift/base_link safety_scanner_front_link`,
which reads the tree the same way Nav2 will:

```
At time 0.0
- Translation: [0.700, 0.450, 0.150]
- Rotation: in Quaternion (xyzw) [0.000, 0.000, 0.383, 0.924]
- Rotation: in RPY (radian) [0.000, -0.000, 0.785]
- Rotation: in RPY (degree) [0.000, -0.000, 45.000]
- Matrix:
  0.707 -0.707  0.000  0.700
  0.707  0.707  0.000  0.450
  0.000  0.000  1.000  0.150
  0.000  0.000  0.000  1.000
```

**One finding that belongs to every future consumer of these frames.**
The first version of the live check asked `tf2` for the transform the
instant its own `/tf_static` subscription was satisfied, and failed all
three lookups on one run and passed all three on the next. The
publisher was identical in both. A `TransformListener` holds its **own**
subscription and its buffer fills independently, so "the transform was
published" and "the buffer can answer" are different moments. The check
now waits for the buffer, bounded, and the run above is with that fix.
`tf2_echo` shows the same thing in its first line — `Invalid frame ID
"forklift/base_link" ... frame does not exist`, once, before it resolves.
**A consumer of these frames waits for the transform; it does not assume
one at start-up.**

---

## 3. Rates, and what is on the graph

`ros2 topic list`, in the launched stack:

```
/clock
/forklift/cmd/fork_speed
/forklift/cmd/steer_angle
/forklift/cmd/traction_speed
/forklift/fork_height
/forklift/gz/fork_cmd
/forklift/gz/steer_cmd
/forklift/gz/traction_cmd
/forklift/joint_states
/forklift/linear_speed
/forklift/obstacle/in_stop_zone
/forklift/obstacle/min_distance
/forklift/odom
/forklift/safety_scanner_front/measurement
/forklift/scan
/parameter_events
/rosout
/tf_static
```

**What is not on that list is the point of the naming rule.** There is no
safe channel, no OSSD, no protective-field topic. The one safety-scanner
channel present says `measurement` in its own name, and the rear device's
channel is absent because nothing consumes it.

`ros2 topic hz`:

```
/forklift/safety_scanner_front/measurement
average rate: 9.940
	min: 0.097s max: 0.104s std dev: 0.00193s window: 11

/forklift/scan
average rate: 9.793
	min: 0.093s max: 0.111s std dev: 0.00538s window: 11
```

Both against the model's declared `<update_rate>10</update_rate>`. The
render cost of three scanners on this software rasteriser is **still not
measured** — that is `EVIDENCE_SENSOR_COVERAGE.md`'s open item and these
two figures do not close it.

---

## 4. The measurement channel sees what the navigation lidar cannot

This is the reason the owner's ruling exists, measured in one run rather
than argued.

The forklift is spawned at `x = 0.00, y = -0.20` in
`sim/worlds/forklift_arena.sdf`, facing `+x`. `AisleCrate` is a
**0.90 m cube centred at (2.00, 0.00)**, so its near face is at
`x = 1.55`; the front safety scanner sits at `x = 0.70` on the vehicle,
which puts the crate **0.85 m** dead ahead of it. The crate's top is
0.90 m: **above the 0.15 m safety plane and 0.90 m below the 1.80 m
navigation plane.**

Both scans read in the same session, both mapped into the **vehicle**
frame with the mount yaw from `model.sdf`, both over the same ±30°
forward sector:

```
forward sector +-30.0 deg in the VEHICLE frame

front safety scanner, MEASUREMENT channel, z = 0.15 m
  {'frame': 'safety_scanner_front_link', 'in_sector': 60, 'nearest_finite': 0.8500196933746338, 'clear_beyond_range': 17, 'invalid': 0, 'range_max': 5.5}
navigation lidar, z = 1.80 m
  {'frame': 'nav_lidar_link', 'in_sector': 60, 'nearest_finite': None, 'clear_beyond_range': 60, 'invalid': 0, 'range_max': 8.0}

obstacle_zone published: in_stop_zone=True min_distance=0.8500196933746338
```

Read that as three facts:

1. The measurement channel returns **0.850 m** — the geometry predicts
   `1.55 − 0.70 = 0.85`, and the rendered scan gives `0.8500197`.
2. The navigation lidar, **in the same sector at the same instant**, has
   `nearest_finite: None` and **60 of 60 samples clear beyond range**. A
   comfort zone computed there would have published `False` at `8.00` m
   with a crate 0.85 m in front of the vehicle. That is the regression
   `docs/reports/m5-04-sensor-layout.md` open question 1 named, and it is
   what reading the low plane repairs.
3. `obstacle_zone` published `in_stop_zone=True`, `min_distance=0.850`.

Its own log, for the reason string as well as the verdict:

```
[obstacle_zone] obstacle_zone up: source /forklift/safety_scanner_front/measurement (non-safe measurement channel), sector -0.7854 +-0.5236 rad in the scan frame, stop distance 1.20 m, scan timeout 0.50 s, rate 10.0 Hz
[obstacle_zone] in_stop_zone=True min_distance=0.000 reason=no scan received
[obstacle_zone] in_stop_zone=True min_distance=0.850 reason=obstacle in sector
[obstacle_zone] stop zone occupied: min_distance=0.850 reason=obstacle in sector
```

The first verdict is the fail-safe one, before any scan has arrived —
absence of data is an obstacle, unchanged.

**None of this is a safety claim.** The channel read here is the
device's non-safe measurement output, the verdict is Python over a
bridged topic, and no protective field, response time, stopping distance
or PL is measured, implied or claimed (ADR 0011 D5).

---

## 5. The evaluator still behaves as it was contracted to

`ROS_DOMAIN_ID=86 /usr/bin/python3 agv/forklift/scripts/obstacle_matrix.py`
— the real node, in its own process, on the repository's own
`config.yaml`, driven with synthetic scans shaped like the front
scanner's measurement channel:

```
obstacle_zone case matrix: source /forklift/safety_scanner_front/measurement
  sector -45.0 +-30.0 deg in the scan frame = -30.0 .. +30.0 deg in the vehicle frame
  stop 1.20 m, timeout 0.50 s, window [0.10, 5.50] m, 275 samples

ok   clear sector                       in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle dead ahead                in_stop_zone=True  min_distance=0.8000     (expected True / 0.800)
ok   obstacle at +10 deg                in_stop_zone=True  min_distance=1.1500     (expected True / 1.150)
ok   obstacle at -90 deg                in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle at +45 deg (scan zero)    in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   last sample inside the edge (-29.27 deg) in_stop_zone=True  min_distance=0.9000     (expected True / 0.900)
ok   first sample outside it (-30.27 deg) in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   obstacle just outside              in_stop_zone=False min_distance=1.2500     (expected False / 1.250)
ok   all samples NaN                    in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all samples +inf                   in_stop_zone=False min_distance=5.5000     (expected False / 5.500)
ok   all samples -inf                   in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all below range_min                in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   all above range_max                in_stop_zone=False min_distance=5.5000     (expected False / 5.500)
ok   empty ranges                       in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   range window NaN                   in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   range window inverted              in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   one valid among NaN                in_stop_zone=False min_distance=2.0000     (expected False / 2.000)
ok   clear again before stall           in_stop_zone=False min_distance=5.0000     (expected False / 5.000)
ok   publisher stopped 1.5 s            in_stop_zone=True  min_distance=0.0000     (expected True / 0.000)
ok   recovers when it returns           in_stop_zone=False min_distance=5.0000     (expected False / 5.000)

RESULT: PASS (0 failing case(s))
```

Against the contract as `docs/reports/m4f-02b`, `m4f-02c` and `m4f-04i`
left it:

- **Stop distance** unchanged at **1.20 m**; **timeout** unchanged at
  **0.50 s**; **sector width** unchanged at **±30°**.
- **The three sample classes are unchanged**, including the one that was
  a real defect: `all samples +inf` and `all above range_max` return
  `False` at the scan's `range_max`, an open horizon is a measurement,
  and only a missing, stale, structurally unusable scan or a sector with
  no sample in **either** valid class returns the fail-safe pair.
- **Two figures move, and both are properties of the new sensor rather
  than of the evaluator**: the clear-horizon value is now the front
  scanner's `range_max` of **5.50 m** instead of 8.00 m, and the sector
  holds **60 samples** (measured, §4 above) because this sensor's angular
  resolution is 275/274 = **1.0036°** rather than 1.0000°.
- **5.50 m is inside** `docs/interfaces/opcua-nodes.md` §10.5's
  plausibility window of 0.05 … 8.10 m, so **this consumer owes the
  interface layer no change**. The window still bounds the navigation
  lidar's 8.00 m, which is a separate open item from m5-04.

### The change the new aperture forced, stated explicitly

The sector is centred on the **vehicle's** driving direction, but scan
angles are measured in the **sensor's** frame, and this sensor is mounted
on a chassis corner at **+45°**. The evaluator therefore gained
`obstacle.sector_centre_rad = −0.7853982`, which `check_sensor_frames.py`
§5 checks against `model.sdf` rather than against arithmetic in a
comment.

The case **`obstacle at +45 deg (scan zero)`** is what makes that
non-cosmetic. An obstacle 0.50 m away at 45° off the bow sits at scan
angle **zero**. Had the centre been left at 0 — the value that was
correct while the source was a sensor at yaw 0 — that obstacle would
have been reported as **dead ahead at 0.50 m**, and an obstacle actually
dead ahead would have been ignored. The matrix run above returns `False
/ 5.000` for it and `True / 0.800` for the real one.

### One measurement artefact worth recording

The two edge cases print the bearings they **landed on**, not the ones
asked for: `-29.27°` and `-30.27°`. At 1.0036° per sample there is no ray
at exactly −30°, so the sector boundary falls **between samples**. A test
that asked for "the sample at the edge" and expected a detection would
fail against correct code — the first attempt at this matrix did exactly
that. Sector membership is a property of the rays that exist.

---

## 6. What this does not establish

1. **Nothing about safety.** No protective field, no OSSD, no response
   time, no stopping distance, no PL, no Category, no PFH. The channel
   exercised here is the device's **non-safe** output and the consumer is
   a process function (invariant 1, ADR 0011 D5).
2. **Nothing about the owner's WSL host.** Container evidence only.
3. **Nothing about SLAM or Nav2.** No map was built, no localisation ran,
   and `odom → base_link` is not published by anything in this
   directory. The frames exist; what consumes them does not yet.
4. **Nothing about the rear measurement channel on ROS.** It is not
   bridged, so it was not exercised on the ROS side in this run.
5. **No render-cost figure.** Three scanners on a software rasteriser
   still costs an unmeasured real-time factor.
6. **Nothing about a moving vehicle.** Every reading above is from a
   stationary forklift; the transforms are static and were not tested
   against a driving one, which they cannot be sensitive to but which no
   run here demonstrates.
