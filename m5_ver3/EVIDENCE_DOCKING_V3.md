# EVIDENCE_DOCKING_V3.md — precise docking (F5)

**§1 is F5 Task 1 live: THE LABEL BUY-BACK.** `nav2.yaml`'s global
costmap now carries an `obstacle_layer` (F4 §19.9 / §20.6 handed that
on). Adding it moves a VALUE, so `nav_params_md5` leaves `53a33d67` —
the eight bytes that made §16.5's eleven runs and §17's eight one
measured set. This section re-drives the headline goal on the new tree
and says which F4 conclusions that re-bases and which it does not.

Everything below was measured on **this rig** (WSL Ubuntu 24.04, ROS 2
Jazzy, gz-sim 8.11.0, RTX 4050 Laptop GPU, `GALLIUM_DRIVER=d3d12`) on
**2026-08-28**, **headless**, `traction=nominal`, `arm=wheel+imu`,
`loc=amcl@735cdbc6`, `nav=on@3ed626ce` / `nav_config_md5=9063bec9`,
`monitor=off`. GPU line from `m5v3.sh start`: `D3D12 (NVIDIA GeForce RTX
4050 Laptop GPU)`. Isolation `GZ_PARTITION=m5v3`, `ROS_DOMAIN_ID=97`.

Nothing here is a safety claim. Docking has not run yet. The 0.25 m
station class is F5's later sections; this one is still the 0.60 m
position-only checker §16.5 shipped.

---

## 0. The answer, before the working

| | |
|---|---|
| **headline goal, 16.5 protocol** (stop + start before every run) | **`spine_north` 3 of 4** against §16.5's **6 of 6** |
| **the three arrivals, TRUTH** | **0.4607 – 0.5226 m** against §16.5's 0.4474 – 0.5684 m |
| **the three arrivals, BELIEF** | **0.4662 – 0.4889 m** against §16.5's 0.4588 – 0.4933 m |
| **sim time / driven** | **56.76 – 57.51 s**, **16.494 – 16.582 m** against §16.5's ~57 s / ~16.4 m |
| **first plan on every protocol run** | **~17.00 m, 0 forward, all REVERSE, start yaw 0.0** — the empty-floor prediction holds for the INITIAL plan |
| **new lethals on the spine corridor** | **0** (spawn capture vs after a failed drive) |
| **the one protocol fail** | §16.4c's oscillation, now on the 17 m leg: heading swing sd **0.66 rad**, one driven cusp, watchdog `no_progress` |
| **what this does NOT buy** | a 6-of-6 claim; a heading-aware arrival; a spawned-box reroute (that is the layer's REASON, measured in a later section) |

---

## 1. The obstacle layer, the grid, and the headline goal

### 1.1 What changed in the file

`nav2.yaml` `global_costmap.plugins` is now
`static_layer → obstacle_layer → inflation_layer`. Marking 8.00 m,
clearing 12.0 m (clearing strictly further than marking),
`combination_method: 1` (MAX), `footprint_clearing_enabled: true`.
`tests/test_nav2_params.py` pins the inequalities. The FILE hashes to
`3ed626ce`; the parameters `yaml.safe_load`ed hash to `9063bec9`.
`analyse` tables on the second; `nav=on@` still prints the first
(§16.9 item 6, still open).

The only VALUE that moved against the §16.5 tree is that layer. Two
comment-only edits in the MPPI block travelled with it and do not
appear in `9063bec9`.

### 1.2 Bringup gate, because the first start died on a false refusal

`m5v3.sh start --headless --localize --nav` refused at `ekf_health`
with `ros2 topic echo --once` printing "does not appear to be
published yet / Could not determine the type" — **before nav came
up**. The filter was publishing: an 8 s `ros2 topic list` was almost
empty, a 20 s list showed `/clock`, `/m5v3/odometry/filtered`, the
scans and tf. `ekf.startup_check.timeout_s: 20` never ran, because
`--once` returns immediately on a discovery miss.

That miss is EVIDENCE_FUSION.md 11.5 (1 of 8 bringups). The old
recovery was "stop and start again". `tools/ekf_health.py` now retries
`echo --once` until `timeout_s`; `evidence_core.echo_is_undiscovered`
is the predicate; `tests/test_evidence_core.py` pins the strings. A
real silence still refuses. After the change: `ekf: healthy`,
covariance 0.10–0.14 against a ceiling of 100, 16 children, nav
lifecycle ACTIVE, trivial 2 m plan in 0.008 s. **No FastDDS unicast
profile was copied from m6** — 20 s of discovery was enough.

### 1.3 The grid, read off the running stack

Instrument: `tools/costmap_probe.py record --tag with_layer` then
`compare`. Both costmaps, 10 s settle after the first message
(`config.yaml nav.costmap_probe`).

Empty floor, truck at spawn, layer on
(`costmap-with_layer-20260828-095032`):

| | lethal(100) | unknown(−1) | free(0) | other |
|---|---|---|---|---|
| `/global_costmap/costmap` 1712×1196 @ 0.05 m, `map` | 16608 | 1429826 | 107188 | 493930 |
| `/local_costmap/costmap` 200×200 @ 0.05 m, `odom` | 758 | 0 | 15790 | 23452 |

After the first failed drive, truck resting at world (−9.48, +8.37)
(`costmap-after_fail-20260828-095406`):

| | lethal | unknown | free | other |
|---|---|---|---|---|
| global | 16678 | 1427622 | 109082 | 494170 |

`compare` of those two globals:

| | |
|---|---|
| RAISED | 11822 cells (NEW LETHAL **889**) |
| LOWERED | 16049 cells (LETHAL LOST **819**) |
| KNOWN/UNKNOWN CHANGED | 2444 |
| **NEW LETHAL in the spine corridor** (world x −18.5..+2, y 7..13) | **0** |
| **LETHAL LOST in that corridor** | **0** |

The first ten raised and lowered cells sit on the north wall
(world y ≈ +14.3, x ≈ −20), 100 ↔ 99 — inflation-boundary jitter, not
a corridor wall. The corridor band y 8.5–11.5 had 2635 cells change,
largest move 20 → 0 at (~−14, +8.53), which is inflation dropping as
nearby smear lethals cleared, **not** a mark being painted onto the
route.

**A LOWERED CELL IS THE ONE RESULT `combination_method: 1` CANNOT
PRODUCE** from the obstacle layer writing into the master
(`updateWithMax`). The 16049 lowered cells are therefore not "the
layer erasing a rack". They are the inflation layer recomputing after
smear lethals at the walls appeared and vanished, plus footprint
clearing on the master. The instrument prints that sentence on
purpose; it fired; the locations say it is not the F4 failure mode.

**WHAT THIS DOES NOT MEASURE.** There is no `static_only` capture on
this bringup. Taking one means disabling the layer, which moves
`nav_config_md5` off `9063bec9` and is a different stack than the
one the goals were driven on. The empty-floor *prediction* in
`nav2.yaml`'s header — "this layer can only ADD, so on a floor the
grid already knows the plans should be identical" — is scored below
off the **first plan of each goal**, which is the planner's own
answer, not a cell tally. A spawned-box compare (the debt 19.9
actually named) is a later section: it needs furniture in the world.

### 1.4 The headline goal, 16.5's own protocol

`tools/drive_goal.py record --goal spine_north`. Stack **stopped and
started before every protocol run**, same as §16.5. One earlier run
on a four-minute-warm stack (costmap recorded first) is kept and
labelled; it is **not** in the 3-of-4 denominator.

| session | protocol | result | sim s | driven | TRUTH | BELIEF | heading | ψ sd |
|---|---|---|---|---|---|---|---|---|
| `…095934` | fresh | **SUCCESS** | 57.51 | 16.494 m | **0.5179 m** | 0.4811 m | +0.0183 rad | 0.0239 |
| `…100218` | fresh | **SUCCESS** | 56.76 | 16.502 m | **0.5226 m** | 0.4889 m | −0.0144 rad | 0.0422 |
| `…100453` | fresh | `no_progress` | 59.79 | 10.762 m | 10.377 m | 10.284 m | +1.97 rad | **0.663** |
| `…100918` | fresh | **SUCCESS** | 56.86 | 16.582 m | **0.4607 m** | 0.4662 m | +0.1346 rad | 0.0412 |
| `…095142` | **warm, 4 min** | `no_progress` | 66.82 | 14.865 m | 9.623 m | 9.569 m | +1.83 rad | 0.622 |

`analyse` reports `spine_north 3 recorded, 3 required` — it counts
SUCCESS only. The two `no_progress` sessions are on disk and named
here.

**THE THREE ARRIVALS SIT INSIDE §16.5's BAND.** At rest, TRUTH
0.4607–0.5226 m and BELIEF 0.4662–0.4889 m against a 0.60 m box;
truth−belief 0.027–0.039 m; sim time 56.8–57.5 s; driven 16.49–16.58 m;
RTF 0.9989–0.9995; `/cmd_vel` 20.00 Hz median; **0 cusps**; forks-first
the whole way. Closest belief on the latch: 0.5936, 0.5976, 0.6082 m
(the last is 8 mm outside the 0.60 m moving box and still arrived at
rest at 0.466 m, which is `stateful` plus the stop, same geometry
§16.5 named).

**THE FIRST PLAN DID NOT CHANGE.** Protocol runs, success and fail:

| session | first plan | start map yaw |
|---|---|---|
| `…095934` SUCCESS | 171 poses, 17.001 m, 0 fwd / 170 REV | **0.0** |
| `…100218` SUCCESS | 169 poses, 16.993 m, 0 fwd / 168 REV | **0.0** |
| `…100453` FAIL | 170 poses, 16.994 m, 0 fwd / 169 REV | **0.0** |
| `…100918` SUCCESS | 171 poses, 16.992 m, 0 fwd / 170 REV | **0.0** |
| `…095142` warm FAIL | 169 poses, 17.003 m, 0 fwd / 168 REV | **−0.087** (5°, after 4 min of AMCL) |

On a floor whose obstacles are all in the frozen grid, the planner's
first answer is the same 17 m reverse it was in §16.5. The layer did
not bend the initial route.

### 1.5 The fail is §16.4c, on a shorter leg

`…100453` (and the warm `…095142`) are the unstable side of the
bimodality §16.4c measured on `ring_corner` at 37 m. Numbers that
match that residual and not a blocked corridor:

- First plan identical to the successes (yaw 0, 17 m, all reverse).
- Deviation from the standing plan stayed small (mean 0.087 m, max
  0.23 m) — the controller **followed** the plan while the plan
  followed the heading.
- Heading swing sd 0.66 rad against 0.02–0.04 on the arrivals
  (16.4c's clusters: ~0.20 lock vs ~0.55 oscillate).
- One driven cusp at t+33 s; last plan carried 2 forward segments.
- Resting pose world (−10.27, +8.53), yaw −1.17 — south of the spine,
  pointed south, 10.4 m from the goal.
- By t+8 s commanded steer was already −0.10 rad and ground-truth yaw
  −3.03; the successes at the same tick were still at yaw −3.12 with
  steer under 0.07 rad. The split is in the first seconds of MPPI, not
  in a lethal cell the layer added later.

§16.4c said the oscillation "needs about 20 m of straight leg to
develop" and that `spine_north` (17 m) had arrived six from six. On
this tree, with this layer, it developed by ~7 m of travel on 1 of 4
fresh starts. **The mechanism behind 16.4c is still not confirmed**
(§16.9 item 1: PathAlignCritic.cost_weight and the tree's 1 Hz
`RateController` were named and not pulled). It is not pulled here
either. A parameter changed on a hunch to force 4 of 4 would be
§16.2's story again.

**THE WARM FAIL IS THE SAME SIGNATURE**, plus a 5° first-plan yaw
that four minutes of AMCL had accumulated. 16.5's protocol exists for
that reason. It is not in the 3-of-4.

### 1.6 What this re-bases, and what it does not

**RE-BASED, against §16.5's `spine_north` column, on `nav_config_md5
9063bec9`:**

- When the loop locks, the truck still arrives inside the 0.60 m box
  in ~57 s, having driven ~16.5 m, at RTF 1.00, 20 Hz, no cusp.
- The empty-floor first plan is still the geometric 17 m reverse.
- The layer did not paint a phantom wall down the spine (0 new
  corridor lethals after a 15 m wander).

**NOT RE-BASED:**

- **6 of 6.** The honest figure on this tree is **3 of 4** under
  16.5's own stop/start rule. `analyse`'s "3 recorded, 3 required" is
  the three successes; the fourth protocol run is `…100453` and it is
  a named 16.4c fail.
- **§16.4c's "20 m" floor.** It fired on the 17 m leg. The residual is
  still open and it is still F4's, not a docking-controller defect.
- **A spawned obstacle in the global plan.** That is why the layer
  exists (19.9). This section drove an empty floor on purpose. Furniture
  comes with the marker.
- **Station-class heading.** The three arrivals handed +0.018, −0.014
  and +0.135 rad without being asked. The 0.25 m / heading pair is
  still docking's.

**F4 conclusions that this section does not touch:** the command path
(§3–§10), the 0.60 m checker argument (§16.6), START_OCCUPIED in a
bay (§17, §20.5 item 3), the jump budget (§18.3 / §20.5 item 6), the
collision-monitor polygons (§19). Those files did not change.

---

## 2. (F5 Task 2) AprilTag on the pallet camera — not yet

Colour image is still gz-only (`CONTEXT.md`: `/forklift/gz/cam/image`
is deliberately not bridged). Detector, marker spawn, RTF cost of
bridging colour: this section, next.
