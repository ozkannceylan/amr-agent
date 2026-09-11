# EVIDENCE_M8_E3 — abort classifier vs staged faults

Status: **RUN 2026-09-11** on the m5-ver3 plant, this rig. Session
`m8/bench/results/e3-20260911-125645/` (`frames.csv` 540 static rows,
`cycles.csv` 252 live rows, `summary.json`, `session.json`; every
number below is in them).

SUPERSEDED AS A BASELINE, NOT AS A RESULT (added 2026-09-11): the C1/C2 rework this file asked for is measured offline in `EVIDENCE_M8_C1C2_FIX.md` on branch `m8/c1c2-plane-roi-fix`. E3 WAS RE-RUN on 2026-09-12 (session `e3-20260912-000826`): clean static false-abort went from 90/90 to 0/30 at staging and 0/30 at 1.5 m, live-dock false-abort from 1.000 to 0.884, and Phase B stays on HOLD. Every number below is what A1 measured and is unchanged. Nothing here was edited and no result folder was overwritten.

**Verdict: the A1 classical C2 aborts on every frame it saw.** 540 of
540 static frames — the 90 clean ones included — and 252 of 252 frames
across two clean live dock approaches that `opennav_docking` completed
with `error 0`. Recall on the staged faults is therefore 100 % and
means nothing; the **false-abort rate is 100 %** on clean static frames
and **100 %** on clean cycles. The reason word depends on range, not on
the fault: `stringer_in_path` beyond ~1.6 m, `pallet_rotated` inside
~1.5 m. Two cells of the 18-cell grid are named correctly, both for
the wrong reason. The cause is E1's: the plane the classifier calls
the pallet face is the floor. No threshold was tuned to produce or
improve this.

## Standing cautions

Ground truth is a score, not a command. The instrument floor
(registration rms 0.0291 m, MAX 0.1179 m) does not enter this file:
E3 scores words against world state, not poses. No PL / SIL / PFH
claims. The Nav2 collision monitor is not a safety function. The F-PLC
never receives M8 input. Frames never leave the truck. `proceed` is
never an M8 output and is not counted anywhere below.

## Bar

ARCHITECTURE.md §3 C2: recall on a staged fault set and false-abort
rate on clean cycles, **both stated**. No numeric bar was set before
this run; this file sets the baseline the next candidate is measured
against.

## Environment

Same bringup as `EVIDENCE_M8_E1.md` (`run-20260911-124107`, 22 alive,
`GL_RENDERER = D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`, Gazebo Sim
8.11.0, ROS 2 Jazzy, `traction=nominal arm=wheel+imu loc=amcl@735cdbc6
nav=on@7f57e6cf dock=on@1676eac0 docking=on@a462315f`). Bench:
`python3 m8/bench/e3_abort.py --frames 30 --ranges staging,1.5,1.0
--cycles 2`, 6 min 42 s wall.

**Fault set as staged** (`bench/faults/inject.py`; gz readback in
`session.json` per condition; pallet design pose (7.000, 3.030, 0.072)
yaw +1.5708, +X face at y = 3.430):

| condition | world state, read back from gz |
|---|---|
| `clean` | pallet at design pose, no box |
| `pallet_absent` | pallet teleported to (−17.000, 10.000), the truck's spawn floor, 25 m away |
| `pallet_rotated` | pallet yaw 1.9208 (+0.35 rad) at the design xy |
| `pallet_shifted` | pallet at (6.700, 3.030): 0.30 m along its own +Y = **west**, which is toward the camera's 0.40 m lateral offset — the pocket pair moves from optical X −0.40 m to −0.10 m |
| `pocket_blocked` | static box 0.10 × 0.72 × 0.10 m (`m8_pocket_block`) at (7.000, 3.490, 0.060): across both openings, 0.06 m in front of the face |
| `stringer_in_path` | static box 0.08 × 1.00 × 0.06 m (`m8_stringer`) at (7.000, 4.030, 0.030): a ridge on the floor 0.60 m in front of the face |

Restore between conditions is `set_pose` back to the design pose plus
`remove` of the box; the two boxes are created and removed through
`/world/warehouse/create` / `remove`, never written into a world file.

## Method

Static: the truck is teleported heading-aligned to the three E1 bases
(camera → face 2.245 / 1.500 / 1.000 m), AMCL seeded, then for each of
the six conditions: restore → inject → 2 s settle → 30 depth frames →
`m8_core.abort.classify` per frame (the shadow abort node's code,
unmodified, on the 640×480 frame it would receive). A frame counts as
an abort when `classify` returns any reason; as exact when the reason
names the staged condition.

Cycles: restore, `dock_bench.py stage` (staging teleport + AMCL seed),
then `dock_bench.py record --from-staging` — the m5-ver3 dock
instrument, run as it is — with the classifier streaming on the camera
for the whole approach. Every classified frame carries the truth pose
and the camera → design-face range at that moment.

## Result — static grid

Cells are `aborts / frames [exact]`:

| condition | staging (2.245 m) | approach 1.5 m | approach 1.0 m | overall |
|---|---|---|---|---|
| `clean` | 30/30 [0] | 30/30 [0] | 30/30 [0] | **90/90 false aborts** |
| `pallet_absent` | 30/30 [0] | 30/30 [0] | 30/30 [0] | 90/90, exact 0 |
| `pallet_rotated` | 30/30 [0] | 30/30 [0] | 30/30 [**30**] | 90/90, exact 30 |
| `pallet_shifted` | 30/30 [0] | 30/30 [0] | 30/30 [0] | 90/90, exact 0 |
| `pocket_blocked` | 30/30 [0] | 30/30 [0] | 30/30 [0] | 90/90, exact 0 |
| `stringer_in_path` | 30/30 [**30**] | 30/30 [**30**] | 30/30 [0] | 90/90, exact 60 |

Recall (any reason) on the 450 fault frames: **450/450**. False-abort
on the 90 clean frames: **90/90**. A classifier that says "abort" to
everything has both numbers; neither is a capability.

**Confusion** (rows: staged condition; columns: classifier word; 90
frames per row):

| | none | pallet_absent | pallet_rotated | pallet_shifted | pocket_blocked | stringer_in_path |
|---|---|---|---|---|---|---|
| `clean` | 0 | 0 | 30 | 0 | 0 | 60 |
| `pallet_absent` | 0 | 0 | 0 | 0 | 0 | 90 |
| `pallet_rotated` | 0 | 0 | 30 | 0 | 0 | 60 |
| `pallet_shifted` | 0 | 0 | 30 | 0 | 0 | 60 |
| `pocket_blocked` | 0 | 0 | 30 | 0 | 0 | 60 |
| `stringer_in_path` | 0 | 0 | 30 | 0 | 0 | 60 |

Five of six rows are identical. `pallet_absent` and `pocket_blocked`
and `pallet_shifted` are never said. The word is a function of the
pose: every condition at staging and 1.5 m is `stringer_in_path`;
every condition at 1.0 m is `pallet_rotated`, except the empty bay,
which is `stringer_in_path` again.

## Result — clean live cycles

| cycle | `dock_bench` session | plugin | truth at rest | heading | frames classified | aborts | false-abort | words by camera range |
|---|---|---|---|---|---|---|---|---|
| 0 | `dock-s5-20260911-130258` | success True, error 0 (NONE), retries 0 | 0.2587 m | +0.0706 rad | 134 (13.6 s wall, range 2.245 → 0.507 m) | **134** | **1.000** | ≥ 2.0 m: stringer 72; 1.5 m: stringer 8 / rotated 12; ≤ 1.0 m: rotated 42 |
| 1 | `dock-s5-20260911-130321` | success True, error 0 (NONE), retries 0 | 0.2620 m | +0.0246 rad | 118 (12.3 s wall, range 2.245 → 0.677 m) | **118** | **1.000** | ≥ 2.0 m: stringer 72; 1.5 m: stringer 7 / rotated 13; ≤ 1.0 m: rotated 26 |

Both cycles are clean docks by the plugin's own account and by truth
(0.26 m against the bay, the F5 class boundary; strict 0.25 m class
NO on both, as 3 of F5's 5 were). Had Phase B been open, both would
have been aborted at the first frame from staging.

## Why the word is what it is

`abort.py` runs its checks in a fixed order on `fit_face_plane`'s
plane `z = a·x + b·y + c`, and E1 measured that plane to be the floor
(`b` −2.6 to −4.0, face 3–7 % of the ROI):

1. `pallet_absent` needs fewer than 15 % valid pixels. The frame is
   77 % valid with or without a pallet (floor, racks, board), so this
   is never said — not even with the bay empty.
2. `pallet_rotated` needs |a| > 0.25. With the pallet in the lower
   part of the ROI at 1.0 m the floor fit tilts to a = 0.40 (E1) and
   this fires first, on the clean pallet too. With the bay empty a
   stays small and control falls through.
3. `stringer_in_path` compares the lower third's column medians with
   `c − 0.04`, where c is the plane's depth **on the axis**, a
   constant. The floor at the bottom of the image is far nearer than
   at the centre, so nearly every column reads "near" and this fires
   at 2.245 and 1.5 m on everything.
4. The pocket-pair tests that would say `pallet_shifted` or
   `pocket_blocked` are never reached.

The thresholds `abort.py` calls "heuristic, E3 will replace them with
measured bars" are not the first problem: no threshold on a floor
plane yields a pallet classifier. The ROI is.

## Latency

`classify` median 0.079 s per frame, max 0.112 s, n = 792 (pure
Python, inside the bench process). During the cycles the stream kept
~10 of the camera's 15 Hz. E5 (RTF cost) is still NOT_RUN.

## What this does and does not claim

- It claims the A1 classical C2, as committed, cannot be put in front
  of a dock consumer: **Phase B (abort live) cannot open on it** — the
  fail-safe direction is only safe when it is also rare.
- It does not propose a fix and none was applied. The next candidate
  (classical rework with a pallet-sized ROI and floor rejection, or
  Phase F's learned classifier) is measured against these two tables.
- The staged set is five geometric faults in gz; lighting, texture and
  a real D455 are E6's and the domain gap's. Named leftovers.
- The fault set's geometry (0.35 rad, 0.30 m, box sizes) is this
  bench's, copied into `session.json`; it is not a requirement.

## Files

| file | md5 |
|---|---|
| `m8/bench/results/e3-20260911-125645/frames.csv` (540 rows) | `778e5b1ef18a38cdf4ad55b1654e5acd` |
| `m8/bench/results/e3-20260911-125645/cycles.csv` (252 rows) | `6af852cc36ec2d46be95579db7a38dc4` |
| `m8/bench/results/e3-20260911-125645/summary.json` | `0a64545a11f4f62086edb1ed59178fa2` |
| `m8/bench/results/e3-20260911-125645/session.json` | `5a9277893238b420c563fe3fe72eeb15` |
| `m8/bench/results/e3-20260911-125645/summary.txt` | `b6e77f7f6c1354cc5c3dd34c3365f944` |
| `…/cycle-{0,1}-stage.log`, `…/cycle-{0,1}-record.log` | dock_bench's own words, as printed |

The two `dock-s5-*` sessions live under `m5_ver3/logs/evidence/` on
this rig (run artefacts, not committed); their `analyse` output is
quoted above verbatim.

Bench: `m8/bench/e3_abort.py`, `m8/bench/faults/inject.py` + two
SDFs, `m8/bench/plant.py`. Without the plant the bench prints
`NOT_RUN` and exits 2 (`m8/tests/test_benches_not_run.py`, held on
Windows and in WSL beside the running plant).
