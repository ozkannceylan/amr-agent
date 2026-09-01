# EVIDENCE_FILM.md — the F5 film: one cycle, four cameras, four takes

`EVIDENCE_DOCKING_V3.md` §5 closed F5 with a residual list, and one
line of it reads:

```
- film of the dock (TODO named it; no film tool in `m5_ver3/`)
```

**This file pays that line.** The list stays exactly as written — it was
true on 2026-08-29 — and what follows is the payment, not an erasure.
There is now a film tool in `m5_ver3/`, four takes on the rig behind it,
and one film.

Everything below was taken on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050) **headless**, `traction=nominal`, on the
full autonomous stack: `m5v3.sh start --headless --localize amcl --nav
--dock`. The filmed cycle is `pallet_cycle.py run`, **the same tool
EVIDENCE_DOCKING_V3.md §4.4 measured, unmodified** — `film_run.py`
starts it, reads its stdout and timestamps what it prints. Nothing the
film does moves the truck.

---

## 0. The answer, before the working

| | |
|---|---|
| **the film** | `logs/film/film-20260901-093823/m5v3-film.mp4` — 1280×720 h264, **2 188 827 bytes**, 4573 encoded frames at 15 fps |
| **its length** | printed `film … (304.80 s)`, `ffprobe` **304.867 s**. One frame at 15 fps. |
| **what is in it** | one whole pallet cycle: transit, stage, dock, attach, lift, undock, carry, stage, dock, lower, detach, undock — **12 legs in the shot table's order**, `outcome done (cycle rc=0)` |
| **what drove it** | AMCL over the frozen map, Nav2 (`SmacPlannerHybrid` REEDS_SHEPP + MPPI), `opennav_docking` on the AprilTag, the `DetachableJoint` pallet. The cycle's own seeding, its `no_progress` recovery and its refusals are what §4.4 measured; this tool only watched. |
| **cameras** | four — the follow camera at 7.0 m moved onto the truck through `set_pose` at 2 Hz, the fixed 45° dock camera over the S5 bay, the 22 m wide camera, and the truck's own D455 as the picture-in-picture |
| **the clocks** | `4659 / 4659 / 4660 / 4642` frames, **sim 0.762 – 0.763 × wall**. Every cut bound goes through that ratio. |
| **the lead** | `lead 3.05 s of footage from the planned 4.0 s before the cycle` — 4.0 wall seconds seen through a 0.763 clock, **not** a clamp: 10.38 s of wall existed before the first leg |
| **frames sampled** | **10 of 10** match the label the cut plan gives their second |
| **takes** | **four**, three of them defective. Every defect was found by a **refusal or by sampling a frame** — none by watching the film and hoping. |
| **the stack** | 22 children alive, 0 dead, throughout the ship take; stopped clean |
| **suite** | **1056 → 1090** over the close. `test_film_core.py` is 64 of them; `film_core.py --selftest` green at every take. |

---

## 1. The instrument

### 1.1 `record`, in order

`film_run.py record`, on a stack that is already up (it refuses one that
is not — `paths.traction_file`):

1. **Places three cameras into the RUNNING world** through
   `/world/warehouse/create`. `warehouse_ver3.sdf` is not edited —
   constraint 21, the same rule the AprilTag and the pallet obey.
2. **Bridges them.** The film cameras publish on gz transport and the
   recorders subscribe on ROS. One `ros_gz_image image_bridge`, three
   topics, started **before** the recorders. §2 is what that line cost
   to learn.
3. **Starts `film_record.py` per camera** — four, the three placed plus
   the truck's own. Each leaves three one-number sidecars beside its
   mp4: `.t0` the first frame's wall time, `.t1` the last frame's, `.n`
   the frames written.
4. **Refuses a silent camera by name** at `film.camera_warmup_s` = 45 s.
5. **Holds `2 × film.lead_s` = 8.0 s of wall** before the cycle, so the
   establishing shot is footage rather than luck. The factor is not a
   knob but a units argument, and it is written in the source: *"lead_s
   is footage and this hold is wall time, the cameras publish on the sim
   clock, and this rig measures 0.66–0.77 × wall and has not been seen
   under 0.5 — so twice the wall is at least the lead."*
6. **Runs `pallet_cycle.py run --repeat 1` under observation**: stdout
   line by line, every `leg c1-<name>` stamped with the wall clock into
   `timeline.json`.
7. **Holds `film.tail_s + 1` = 5.0 s past `done`**, because the cut
   plans the last segment past `cycle_end` and those seconds have to
   exist on disk.
8. **Removes the three cameras in a `finally`.** §2 is what that cost
   too.

### 1.2 The sidecar clock — the one line the cut is honest by

The timeline is stamped on the **wall** clock. The cameras record on the
**sim** clock. `film_core.clock` measures the ratio from the sidecars
and every bound goes through it:

```
rate      = ((n - 1) / fps) / (t1 - t0)
video_time(wall_t) = (wall_t - t0) * rate
length_s  = n / fps          # the footage that EXISTS
```

`read_clock` **raises** rather than assuming `rate = 1.0` for a
recording that has no `.t1` and no `.n` — *"without all three this
file's sim clock is unmeasured and every trim into it would be a
guess."* §3 is the take that guessed.

### 1.3 What `cut` refuses, by name

- a cycle that did not finish;
- a timeline whose legs are not the shot table's, in order;
- a `follow` or `dock` recording that cannot be placed on the clock
  (`wide` and `vehicle` are cut around, with a printed line saying so);
- **a segment reaching past the end of its own footage** by more than
  `film.eof_tolerance_s` = 0.5 s — *"ffmpeg clamps such a trim at
  end-of-file without a word, and a leg clamped away is a leg the film
  claims to hold and does not"*;
- **a segment starting before the recording's first frame** by the same
  tolerance — *"ffmpeg clamps that one at 0 just as quietly, and every
  segment after it then sits that far from the printed plan."*

Two things are planned rather than refused, and both print what they
did: the **lead** is planned from the footage the wide recording
actually holds, and the **PiP** stream is trimmed to its last window.

### 1.4 The shot table

`config.yaml film.shots`, one row per leg of `plan_cycle()` in order;
`tests/test_film_core.py` locks the names to that function, so a changed
cycle is a changed film and not a silent half-film.

| legs | camera | why |
|---|---|---|
| `transit`, `stage`, `dock` (approach), `carry`, `stage` | **follow** | the film is called an autonomous *driving* film |
| `attach`, `lift`, `undock`, `dock` (return), `lower`, `detach`, `undock` | **dock**, 45° | a lift is a z-motion: overhead it is occlusion, in profile it is the shot |
| `stage`, `dock`, `attach` | **+ PiP** | the tag growing in the vehicle camera is the proof the dock run is tag-driven |

---

## 2. Take 0 — three cameras nobody could hear, and three nobody removed

`film-20260831-151708`, before this close.

| recorder | frames |
|---|---|
| `follow` | **0** |
| `dock` | **0** |
| `wide` | **0** |
| `vehicle` | 220 |

**Mechanism.** The three placed cameras publish on **gz transport**;
`film_record.py` subscribes on **ROS**. The vehicle camera already
crossed on the `imgbridge` child `m5v3.sh` starts, so it recorded; the
three new ones had no bridge at all and every recorder waited for a
first frame that could never arrive. The warmup refusal fired and named
them. **The take was lost to a refusal, not to a blank film** — which is
the only reason this is a paragraph and not a discovery made in an
editor.

**A second defect in the same take.** `_remove_model` sent
`gz.msgs.Entity` with a name and **no type**. gz-sim resolves such an
entity to `kNullEntity`, so the remove is a **silent no-op**, and the
next `/create` with `allow_renaming: false` is then refused for a name
that is still taken. Worse, the removal sat **outside** the `try`, so
the refusal above skipped it entirely and left `film_follow`,
`film_dock` and `film_overhead` standing in the world. Take 1 cost a
full stack restart.

**Fixes, both in `film_run.py`.** `'name: "{}", type: MODEL'` — the same
body `furniture.py` and `pallet_place.py` spell — and the three removals
moved into a `finally` that runs on the refusal path as well as the
happy one.

---

## 3. Take 1 — wall seconds planned onto sim-clock footage

`film-20260901-081119`. The bridge was live and the recording worked:
frames **3941 / 3941 / 3940 / 3930**, cycle `done`, rc 0, 12 legs.

**Mechanism.** The timeline is wall time; the footage is sim time; the
cut subtracted one from the other and handed the difference to ffmpeg.

| | |
|---|---|
| RTF that take | **0.754** |
| cycle, on the wall | 348.5 s |
| footage that existed | **262.7 s** |
| the cut's printed plan | `349 s of film`, `plan lead 4.0 s on wide, 12 legs, 3 pip windows` |
| of that plan, past end-of-file | **84.8 s** |
| what ffmpeg did about it | clamped every such trim at EOF, **silently** |
| the encode | **262.8 s** — the satisfiable segments, to the byte |

**What that cost on screen.** The legs at the end of the cycle are the
ones that fell off the end of the footage: `dock`, `lower`, `detach`,
`undock` — **the whole put-down**. A frame sampled at t = 200 s, which
the plan labelled `undock`, showed **empty floor**. The film was 263
seconds long, played to the end, and claimed a put-down it did not hold.

**Fix.** `film_record.py` now writes `.t1` and `.n` beside `.t0`;
`film_core.clock` measures the rate between first and last frame;
`video_time` puts every bound into its own recording's seconds; and a
trim reaching past `length_s` by more than 0.5 s is a **refusal by
name** instead of a silent clamp. Take 1's session on disk still carries
only `.t0` — and `read_clock` refuses it, which is the point.

---

## 4. Take 2 — one sign, two takes of grey

`film-20260901-084414`. The clock fix was live and worked: **12
sidecars** written, a per-camera clock line printed for the first time,
`sim 0.659 x wall`, printed 255 s against an `ffprobe` of **254.40 s**.

And **every dock-camera frame was a uniform grey**, 4351 bytes of PNG.

**Mechanism.** `film.dock_pose` was `12.5 3.0 9.0 0 -0.979 3.141`, and
its own comment said "pitched down 0.98 rad at the bay". It was pitched
**up**: 0.98 rad above the horizon, filming sky. **Down is POSITIVE
pitch on this rig** — the wide camera's own SDF pose is
`-5 8 22 0 1.5708 0` (straight down) and `film_run._spawn_pose` builds
the follow camera at `+π/2`.

**The A/B, in the same live world.** `logs/_f5_dockprobe.py` spawned the
**same** `film_dock.sdf` twice on two probe topics, once at the
configured pitch and once at its negation:

| probe | pitch | PNG |
|---|---|---|
| `PROBE_asconfig.png` | −0.979 | **4 351 bytes** — uniform blank |
| `PROBE_flipped.png` | +0.979 | **106 369 bytes** — the S5 bay, in 45° profile |

**What that cost on screen.** The dock camera carries **7 of the 12
legs**. Of the take's nine sampled frames, the five on the dock camera
were all blank at 4351 – 4362 bytes; the four on follow and wide were 44
– 78 KB of warehouse.

| sampled frame | bytes |
|---|---|
| `01_lead_wide_t1.5.png` | 78 394 |
| `02_transit_follow_t40.0.png` | 44 533 |
| `03_dock_approach_follow_pip_t136.0.png` | 50 223 |
| `04_lift_dock_t152.0.png` | **4 362** |
| `05_carry_follow_t181.0.png` | 52 187 |
| `06_dock2_dock_t226.0.png` | **4 351** |
| `07_lower_dock_t234.9.png` | **4 351** |
| `08_detach_dock_t236.5.png` | **4 351** |
| `09_final_undock_hold_t252.0.png` | **4 351** |

**Fix.** `dock_pose: "12.5 3.0 9.0 0 0.979 3.141"`, with the sign
**argued** in `config.yaml`'s own comment rather than left as a value —
"down is POSITIVE pitch on this rig, like the overhead cam's +1.5708:
the -0.979 first sign filmed uniform sky-grey for two whole takes, A/B
measured 2026-09-01." One sign, two takes, seven legs.

---

## 5. Take 3 — a lead from before the first frame, and a frozen tail

`film-20260901-090500`. The dock pose fix was live and it is the take
that first held a put-down: **10 of 10** sampled frames content-correct,
**70.9 s of 333.3 s — 21.3 % of the film — recovered** from take 2's
grey.

Two defects, both at the ends of the film.

**(a) The lead was trimmed from before the footage began.** The cycle
started **1.3 s of wall** after the wide recorder's first frame; the cut
asked for `film.lead_s` = 4.0 s before it. The trim it built was
`trim=-2.099:0.979` and ffmpeg **clamped the start at 0** — as quietly
as it had clamped the ends in take 1. The lead delivered **0.979 s**
instead of 4.0, and because the film is a concatenation, **every segment
after it sat ~2.1 s against the printed plan**.

**(b) The PiP padded the encode.** The overlay's framesync ran the
inset stream to the vehicle recording's full **4984** frames, so the
encode carried **17 frames of a frozen final frame** past a 331.1 s
film.

**Fixes, four of them.**

| fix | where |
|---|---|
| `record` holds `2 × lead_s` = 8.0 s of wall before the cycle | `film_run.PRE_ROLL_X_LEAD`, argued from an RTF floor of 0.5 this rig has never been under |
| the lead is planned from **where the wide recording begins**, and the printed `lead` line says how much of the plan survived | `plan_segments(..., lead_floor=)` |
| a start-side refusal, symmetric to the EOF one and on the same 0.5 s tolerance | `film_core.ffmpeg_argv` |
| the PiP stream is trimmed to its **last window** | `film_core.ffmpeg_argv` |

**Measured after, on this same session, re-cut:** printed **331.21 s**,
encode **331.13 s**. One frame.

---

## 6. Take 4 — the ship take

`film-20260901-093823`. `film_record_run4.log` and `film_cut_run4.log`
are the whole record.

### 6.1 The pre-roll, and the clocks

```
pre-roll  8.0 s of establishing footage before the cycle
```

Measured against the files rather than the plan: the wide recorder's
first frame is at wall `1788248306.139` and the first leg is stamped
`1788248316.517` — **10.38 s of wall** before the film's first event,
where the lead needs 4.0.

```
clock     dock     4659 frames, 310.6 s of footage, sim 0.763 x wall
clock     follow   4659 frames, 310.6 s of footage, sim 0.763 x wall
clock     vehicle  4642 frames, 309.5 s of footage, sim 0.762 x wall
clock     wide     4660 frames, 310.7 s of footage, sim 0.763 x wall
lead      3.05 s of footage from the planned 4.0 s before the cycle
cut       …/m5v3-film.mp4 -> 305 s of film from a 400 s cycle
```

`3.05 = 4.0 × 0.763`. **The lead is the sim-clock image of the whole
planned 4.0 wall seconds, not a survivor of a clamp** — that is the
difference between this take and take 3, and the printed line is the
same line either way, which is why the 10.38 s above is quoted from the
sidecar and not from the log.

### 6.2 The cut plan, leg by leg

Every bound below is the timeline's own wall stamp mapped through that
camera's rate. The film's length is the running sum, and it closes on
the printed figure.

| # | leg | camera | PiP | wall, from cycle start | film time |
|---|---|---|---|---|---|
| — | lead | wide | — | −4.0 s | 0.0 – 3.1 s |
| 1 | `transit` | follow | | +0.0 s | 3.1 – 77.0 s |
| 2 | `stage` | follow | ● | +96.9 s | 77.0 – 155.7 s |
| 3 | `dock` | follow | ● | +200.2 s | 155.7 – 177.1 s |
| 4 | `attach` | dock | ● | +228.2 s | 177.1 – 184.1 s |
| 5 | `lift` | dock | | +237.5 s | 184.1 – 186.8 s |
| 6 | `undock` | dock | | +241.0 s | 186.8 – 204.7 s |
| 7 | `carry` | follow | | +264.4 s | 204.7 – 233.8 s |
| 8 | `stage` | follow | | +302.6 s | 233.8 – 262.4 s |
| 9 | `dock` | dock | | +340.2 s | 262.4 – 280.2 s |
| 10 | `lower` | dock | | +363.5 s | 280.2 – 282.9 s |
| 11 | `detach` | dock | | +367.0 s | 282.9 – 283.9 s |
| 12 | `undock` | dock | | +368.3 s | 283.9 – **304.80 s** |

```
film      …/m5v3-film.mp4 (304.80 s)
plan      12 legs, 3 pip windows
```

`ffprobe` reads **304.867 s**; the encode is **4573** frames at 15 fps.
The printed plan and the file agree to **one frame**.

### 6.3 Ten frames, ten labels

Each sample was pulled at a second of the *finished film* and checked
against the window the table above puts that second in.

| frame | film t | window it lands in | what it shows |
|---|---|---|---|
| `01_lead_wide_t1.5` | 1.5 s | lead (0.0 – 3.1) | the establishing wide, truck in the aisle |
| `02_transit_follow_t40.0` | 40.0 s | `transit` (3.1 – 77.0) | the truck driving the north leg, follow cam |
| `03_dock_approach_follow_pip_t168.0` | 168.0 s | `dock` (155.7 – 177.1) | dock approach, PiP inset with the tag |
| `04_attach_dock_pip_t181.0` | 181.0 s | `attach` (177.1 – 184.1) | forks in the pocket, 45° profile |
| `05_lift_dock_t185.5` | 185.5 s | `lift` (184.1 – 186.8) | the lift, in profile |
| `06_carry_follow_t219.0` | 219.0 s | `carry` (204.7 – 233.8) | truck carrying the pallet |
| `07_dock2_dock_t271.0` | 271.0 s | `dock` (262.4 – 280.2) | the return dock |
| `08_lower_dock_t281.5` | 281.5 s | `lower` (280.2 – 282.9) | the pallet set down |
| `09_detach_dock_t283.4` | 283.4 s | `detach` (282.9 – 283.9) | the joint released |
| `10_final_undock_hold_t302.5` | 302.5 s | `undock` (283.9 – 304.8) | the truck pulling out of the bay, pallet left behind |

**10 of 10.** No blank frames, no frozen tail, no leg the plan claims
and the file does not hold.

### 6.4 What the cycle itself did, on film

The film is a recording of a real run, including the parts a
demonstration would rather not have. From `film_record_run4.log`:

| leg | what the log says |
|---|---|
| `transit` | `spine_north`, `result t = 152.198 s, status 4, error_code 0` |
| `stage` | **`NO PROGRESS`** — `believed distance 6.2439 m at t = 221.108 s`, `status -1`. Then `nav2 miss recovered via staging rc=0`. **It is in the film**, on the follow camera, at 77.0 – 155.7 s. |
| `dock` | `session dock-s5-20260901-094224`, `success True`, `error 0 (NONE)`, `retries 0` |
| `attach` | `attach ok  yaw_err 0.0000  height_err 0.0140`, then `attached  the plugin announced it on /forklift/gz/pallet/state` |
| `lift` | `lift 0.10 m` — pallet z `0.072 → 0.151` |
| `carry` | `burst +0.100 m/s for 35.2 s`; truck y 6.04 → 8.79, pallet 4.50 → 7.25 |
| `lower` / `detach` | pallet z `0.1717 → 0.0722 → 0.0719` |
| `undock` | truck leaves to y 6.41; the pallet stays at **(7.014, 3.259, 0.072)** |
| close | `done      1 cycles`, `holding   5.0 s of tail past done`, `outcome   done (cycle rc=0)` |

The `no_progress` on `stage_s5` is the miss class `EVIDENCE_DOCKING_V3.md`
§1.4 and §4.4 already named, and the recovery is the cycle's own. The
film neither hides it nor re-runs to avoid it.

### 6.5 The follow camera, in the field

`follow.log`: `film_follow on /forklift/gz/odom at 7.0 m, 0.50 s
period`, **492 moves**, **14 refused `set_pose` calls**, worst run of
consecutive refusals **2** against a `film.follow_fail_max` of 10. The
camera never gave up and was never left behind — degraded footage was
available as a fallback and was not needed.

---

## 7. Residuals, by name

- **RTF is not a constant, so film length is not either.** The four
  takes measured **0.659 / 0.754 / 0.763 / 0.769 × wall**. The same
  cycle came out 255 s of film on one take and 333 s on another. A film
  cut tomorrow will be a different length, and the printed `cut` line is
  the only place that says so.
- **The film plays at sim pace.** 400 s of wall cycle is 305 s of film —
  roughly **1.3× wall**. It is not re-timed to real time.
- **The lift is small on screen.** 0.10 m at the dock camera's slant
  range is ~9 px in a still; it reads as motion, and only as motion.
- **The dock composition is off-centre.** The pose clears RackNE2's 4 m
  top and holds the whole spur, which is what it was sized for; it was
  not framed.
- **The PiP is not time-shifted.** The inset is trimmed from its own
  file's zero and its windows are placed in *film* time, so the inset
  runs roughly **1 – 3 s** out of step with the main frame. It is
  evidence that the tag is in the camera, not a synchronised second
  angle.
- **One take of one cycle.** `EVIDENCE_DOCKING_V3.md` §4.4 is the ×3;
  this is one. A film is not a repeat set.
- **Dry only, one truck, markers only.** No wet floor, no fleet, and the
  learned pallet detector is still the open SOTA residual §5 named. The
  film shows a marker-driven dock because that is what ships.
- **`ffprobe` is the only external check.** The frame sampling is
  `ffmpeg` extracting stills from the finished film; the labels are the
  cut plan's own. Nobody outside this repository has watched it.

Nothing outside `m5_ver3/` was edited. `warehouse_ver3.sdf` was not
edited — the three cameras are spawned into the running world and
removed in a `finally`. PLCSIM was not opened.
