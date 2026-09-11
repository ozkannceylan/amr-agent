# EVIDENCE_M8_E1 — pocket pose vs tag bar

Status: **RUN 2026-09-11** on the m5-ver3 plant, this rig. Session
`m8/bench/results/e1-20260911-125543/` (every number below is in its
`frames.csv` / `summary.json`; nothing here is typed from memory).

**Verdict: the A1 classical C1 baseline does not locate the pocket pair
on the plant.** At the tag bar's own staging range and at 1.5 m it
returns no pose at all (0 of 30 frames each); at 1.0 m it returns a
pose on every frame that is **0.92 m** off the truth. The bar (rms
0.0706 m) is not met at any range. The cause is measured, not guessed:
the plane C1 fits is the **floor**, because the pallet face is 3–7 % of
the fit's ROI. PLAN.md's risk line ("the classical pocket baseline may
be worse than the tag — that is a result, not a failure") is now a
number. No parameter was tuned to produce or improve it.

## Standing cautions

Ground truth is a score, not a command. The instrument floor
(registration rms 0.0291 m, MAX 0.1179 m) bounds the map-chain column.
No PL / SIL / PFH claims. The Nav2 collision monitor is not a safety
function. The F-PLC never receives M8 input. Frames never leave the
truck: the bench keeps depth in memory and writes numbers.

## Bar (quoted)

Tag chain at staging: rms **0.0706 m** over 211 samples
(`m5_ver3/EVIDENCE_DOCKING_V3.md` §2.4, `tag-s5-20260828-155745`) —
`map` → `tag36h11_0` through TF against the marker through the
committed registration, AMCL re-seeded at heading-aligned staging. R1:
tagged pallets first. C1 reads depth only, so the tag's presence does
not change its input; the "tagged" bar is the chain it is compared to.

## Environment

| Item | Value |
|---|---|
| Host | `ozkannotebook`, WSL2 Ubuntu 24.04, kernel 5.15.167.4-microsoft-standard-WSL2 |
| GPU | NVIDIA GeForce RTX 4050 Laptop GPU, driver 572.16; `GL_RENDERER = D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)` (ogre2.log, this bringup) |
| Sim / ROS | Gazebo Sim 8.11.0, ROS 2 Jazzy, Python 3.12.3 |
| Stack | `./m5_ver3/m5v3.sh start --headless --localize amcl --nav --dock`, 22 alive / 0 dead, `run-20260911-124107` |
| Labels | `traction=nominal` `arm=wheel+imu` `loc=amcl@735cdbc6` `nav=on@7f57e6cf` `dock=on@1676eac0` `docking=on@a462315f` `monitor=off` `partition=m5v3` |
| Registration | `m5_ver3/maps/warehouse_v3/registration.yaml` θ −3.138328 rad, t (−17.111857, 9.798692) m, residual rms 0.029052 / MAX 0.117891 m |
| Camera | `pallet_cam` 640×480, CameraInfo fx = fy = 337.357, cx 320, cy 240 (= SDF hfov 1.518 rad); depth noise stddev 0.008 m (model.sdf) |
| Pallet | `pallet_s5` gz readback (7.000, 3.030, 0.072) yaw +1.5708; +X face at y = 3.430; pocket pair centre z = 0.061 |
| Bench | `python3 m8/bench/e1_pocket.py --frames 30 --ranges staging,1.5,1.0`, 48 s wall |

## Method

1. World restored by `bench/faults/inject.restore` (pallet reseated by
   `set_pose`, no boxes). Truck teleported by `gz set_pose`,
   heading-aligned (`pose_yaw` +π/2, forks south), to three bases on
   the S5 spur; AMCL seeded on `/initialpose` at the registered map
   pose of each (the `dock_bench.py stage` mechanism), 2 s hold, 3 s
   settle, then 30 depth frames.
2. **Estimate.** `m8_core.pocket.observe` — the code the shadow node
   runs, unmodified, on the 640×480 frame it would receive — read as
   the point `propose()` would emit: range = `face_z`, lateral =
   `(pocket_u − cx)/fx · face_z`, yaw = `atan(face_a)`.
3. **Truth.** The pocket-pair centre (pallet +X face, y = 0, pocket
   mid-height) from the gz pose of the pallet and the gz 6-DoF pose of
   the truck, through `vehicle.cam_mount` (−0.90, 0.40, 1.10; pitch
   0.5236, yaw π) and `vehicle.cam_optical` (REP-103), in the optical
   frame (`bench/geom.py`, pinned by `tests/test_bench_geom.py` against
   hand-derived staging numbers).
4. **Chain check, every frame.** The depth image is sampled at the
   pixel the truth projects to and compared with the truth range. This
   is the instrument checking itself against the sensor, before it
   scores anything.
5. **Map column.** The same estimated point carried through live TF
   (`map` → `pallet_cam_optical` at the frame stamp) against the truth
   through the committed registration — the bar's own chain.

## Result

| pose | base (x, y) | camera→face | truth (lat, height, range) opt. | face in image (u, v) | face % of plane ROI | face % of pocket band | observed |
|---|---|---|---|---|---|---|---|
| staging | (7.000, 6.575) | **2.245 m** | (−0.400, −0.223, 2.464) | u 181–348, v 199–217 | **2.9 %** | 2.9 % | **0 / 30** |
| approach 1.5 m | (7.000, 5.830) | 1.500 m | (−0.400, +0.150, 1.819) | u 130–358, v 255–277 | **4.9 %** | 4.9 % | **0 / 30** |
| approach 1.0 m | (7.000, 5.330) | 1.000 m | (−0.400, +0.400, 1.386) | u 69–370, v 322–348 | **6.6 %** | **0.0 %** | **30 / 30** |

Plane ROI is `fit_face_plane`'s (cols 106–533, rows 120–360); the
pocket band is `find_pockets`' (rows 160–320). At 1.0 m the face lies
entirely **below** the band that looks for pockets.

**Chain check (depth at the truth pixel − truth range), n = 30 per pose:**

| pose | mean | rms | max abs |
|---|---|---|---|
| staging | +0.0005 m | 0.0035 m | 0.0082 m |
| approach 1.5 m | −0.0007 m | 0.0036 m | 0.0075 m |
| approach 1.0 m | +0.0008 m | 0.0033 m | 0.0077 m |

The truth chain agrees with the depth sensor to its own noise
(stddev 0.008 m). The errors below are C1's, not the instrument's.

**Score, where C1 returned a pose (approach 1.0 m only, 30 frames):**

| quantity | C1 estimate (mean) | truth | error rms | error min–max |
|---|---|---|---|---|
| lateral | +0.208 m | −0.400 m | **0.608 m** | 0.6080–0.6081 |
| range | 2.079 m | 1.386 m | **0.694 m** | 0.6932–0.6937 |
| 2-D (lateral, range) | — | — | **0.9223 m** | 0.9220–0.9225 |
| yaw (optical) | +0.382 rad | 0.000 rad | **0.3823 rad** | 0.3815–0.3830 |
| map chain xy (TF 30/30) | — | — | **1.0342 m** | 1.0333–1.0364 |

Frame-to-frame spread is under a millimetre: this is a deterministic
wrong answer, not noise. Against the bar: 1.03 m vs 0.0706 m on the
same chain. **Not met.**

## What C1 actually fitted

`fit_face_plane` succeeded on all 90 frames. Its plane, `z = a·x + b·y
+ c` in normalised optical coordinates:

| pose | c (range on axis) | truth range | c − truth | a (horizontal slope) | b (vertical slope) | points |
|---|---|---|---|---|---|---|
| staging | 2.267 m | 2.464 m | −0.197 m | +0.060 | **−4.04** | 60 951 |
| approach 1.5 m | 2.194 m | 1.819 m | +0.375 m | +0.188 | **−3.50** | 58 634 |
| approach 1.0 m | 2.079 m | 1.386 m | +0.694 m | +0.402 | **−2.56** | 61 193 |

A vertical face square to the spur has |a| ≈ 0 and a small |b|; a plane
whose depth falls by 2.6–4.0 m per unit of normalised image height is
the **floor**, seen 30° down. The face is 2.9–6.6 % of the ~60 000
points in the fit; least squares follows the other 93–97 %, and the
second pass (drop points deeper than plane + 0.05 m) cannot recover a
face it never fitted. At staging and 1.5 m `find_pockets` then finds no
two clusters deeper than that plane and `observe` returns None; at
1.0 m it finds two spurious clusters (the face itself, now below the
pockets band, reads "deeper" than the floor plane at its rows) and
reports them as pockets with the floor's range and slope — hence
+0.38 rad of "face yaw" on a pallet that is square.

## Latency (inside the bench process, pure Python)

`observe` median 0.071 / 0.069 / 0.078 s per frame (max 0.086 s);
32FC1 decode median 0.011 s. These are per-call timings on this rig,
not the node's RTF cost — that is E5, still NOT_RUN.

## What this does and does not claim

- It claims the A1 classical C1, with its committed ROI, does not see
  the pallet on this plant at 2.245, 1.5 or 1.0 m, and why.
- It does **not** propose a fix and none was applied. A pallet-sized
  ROI, a floor-plane rejection or a learned candidate (Phase F) are the
  obvious next candidates; each is a separate ticket with this file as
  its baseline.
- PLAN.md Phase C says "delta box fixed from E1". **No box can be
  fixed from these numbers**; that item stays open by name.
- Tagless pallets: unchanged, no bar, no claim (R1).
- Domain gap: gz depth is not a real D455. Named leftover.

## Files

| file | md5 |
|---|---|
| `m8/bench/results/e1-20260911-125543/frames.csv` (90 rows) | `47e887c0b3a139a2b0a0cd65604df698` |
| `m8/bench/results/e1-20260911-125543/summary.json` | `62d3a05eb70f06d7b50dbbe8e6536ed6` |
| `m8/bench/results/e1-20260911-125543/session.json` | `c6e362e2698de20b9a391439c45c4cdd` |
| `m8/bench/results/e1-20260911-125543/summary.txt` | `fd6f0a855755462eae3b8f4448a914fa` |

Bench: `m8/bench/e1_pocket.py` (scoring), `m8/bench/plant.py` (plant
as instrument), `m8/bench/geom.py` (+ `m8/tests/test_bench_geom.py`, 9
tests). Without the plant the bench still prints `NOT_RUN` and exits 2
(`m8/tests/test_benches_not_run.py`).
