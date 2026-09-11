# EVIDENCE_M8_C1C2_FIX — the classical rework of C1 and C2

Status: **OFFLINE MEASURED 2026-09-11**, plant re-run **NOT_RUN**.
Session `m8/bench/results/scene-20260911-200542/`. Branch
`m8/c1c2-plane-roi-fix`, cut from `m5-ver3-close`.

This is the ticket `EVIDENCE_M8_E1.md` and `EVIDENCE_M8_E3.md` asked
for: "a C1/C2 rework (pallet-sized ROI, floor rejection) ... measured
against these two files." It is the classical option. Phase F (a
learned candidate) was not opened and nothing here is learned.

**Neither baseline file was touched, and no result folder under
`m8/bench/results/` was overwritten.** The H1 sessions
`e1-20260911-125543` and `e3-20260911-*` stand as the before.

## What this file claims, and what it does not

- It claims the defect both baselines named — the fitted plane is the
  floor — is gone **on rendered depth**, with the numbers below.
- It does **not** claim a plant rms. E1 and E3 have not been re-run.
  Until they are, the plant bars (tag rms 0.0706 m; 90/90 clean frames
  aborted) stand unanswered on the rig itself.
- The renderer and the estimator share assumptions — flat floor, flat
  face, pinhole camera, Gaussian noise. A mistake inside that shared
  assumption cannot show up here. That is why the offline bench is
  named `offline_scene.py` and prints "not a plant result" in its own
  header.
- No localiser, no TF, no AMCL. E1's map-chain column has no
  counterpart offline.
- Ground truth is a score, not a command. No PL / SIL / PFH claims.
  The F-PLC never receives M8 input. Frames never leave the truck.

## The two causes, and what replaced each

`EVIDENCE_M8_E1.md` measured C1's plane at `c` = 2.267 / 2.194 / 2.079 m
with `b` = −4.04 / −3.50 / −2.56, against truth ranges of 2.464 / 1.819
/ 1.386 m, and named the cause: the pallet face is 2.9–6.6 % of the
fixed ROI, so least squares followed the other 93–97 %.

**1. The model was not the equation of a plane.** For a 3-D plane
n·P = D with P = (x·Z, y·Z, Z), `1/Z = (n_x·x + n_y·y + n_z)/D`. A
plane is linear in **inverse** depth and never in depth. A1 fitted
`z = a·x + b·y + c`. Refitting A1's model over A1's band on a
plant-faithful 640x480 frame gives a = +0.027, b = −4.956, c = 2.544 m
over 102 480 points with a residual rms of **0.426 m** — the model does
not describe the surface it was fitted to, so its intercept was a
fitted constant of the wrong equation. (The slope is steeper than the
plant's measured −4.04 because the rendered band has a different mix of
valid pixels; the sign, the magnitude and the residual are the claim,
not the third decimal.) Locked by
`tests/test_pocket.py::test_a1s_fixed_band_and_depth_model_still_land_on_the_floor`.

**2. The ROI was fixed.** It is now derived per frame:

| step | what it does | refusal it can raise |
|---|---|---|
| `dominant_plane` | trimmed LS in inverse depth over a stride-4 grid; on this rig it lands on the floor, and that is now the point | no plane at all |
| `_blob_bbox` | largest 4-connected blob of cells nearer than that plane by > 0.06 m | nothing stands above the floor |
| deck cut | drops the top 0.03 m of the blob's height range — the deck top is horizontal, is not the face, and is 2.4:1 (staging) to 4.2:1 (1.0 m) bigger than the face | — |
| mode seed | seeds the fit on the **mode** of horizontal distance, then trims on **perpendicular** distance | — |
| size gate | face must be 0.60–1.90 m wide and 0.05–0.60 m tall **in metres** | not pallet-sized |
| `FACE_MIN_DZ_DY` | the floor falls away downward (−3.8 here); a standing face does not | the candidate is a floor |
| `find_pocket_pair` | two runs ≥ 3 columns deeper than the face, centres 0.35–0.80 m apart, each 0.04–0.45 m wide | no validated pair |

A1 accepted **any** two clusters deeper than its plane. That is exactly
how, at 1.0 m, it reported the pallet face itself as a pocket pair.

**A third defect was found and fixed while measuring, not inherited
from the baseline files:** `stringer_in_path` searched only the face
box. A bar in front of the face is *nearer*, so it projects *below* the
face, and at 1.0 m it left the box entirely — the first bench run read
`none` on 6 of 6 close-range stringer frames. `near_face_fraction` now
searches the whole standing object, floor and deck excluded by the same
two tests the fit uses. Held by
`test_a_bar_in_front_of_the_face_is_stringer_in_path[1.0]`.

## The instrument

`m8_core/scene.py` renders ray/plane intersections for the floor, the
pallet face, the deck top, optional obstructions and an optional far
wall, plus Gaussian range noise at the plant's quoted 0.008 m. It is
pinned to the plant by construction — the pocket-pair centre it reports
matches `EVIDENCE_M8_E1.md`'s truth column to the millimetre at all
three poses:

| pose | scene `pocket_centre()` (lat, height, range) | E1 truth |
|---|---|---|
| staging | (−0.400, −0.2227, 2.4637) | (−0.400, −0.223, 2.464) |
| approach 1.5 m | (−0.400, +0.1498, 1.8185) | (−0.400, +0.150, 1.819) |
| approach 1.0 m | (−0.400, +0.3998, 1.3855) | (−0.400, +0.400, 1.386) |

Geometry: camera 1.10 m up, pitched 0.5236 rad down, 640×480,
fx = fy = 337.357; pallet face 1.200 m × 0.144 m, two 0.160 m pockets
0.560 m between centres, deck 0.800 m deep
(`m5_ver3/gazebo/pallets/pallet_s5.sdf`).

Named approximations: a pocket is rendered as a hole through to the
floor behind rather than onto the pocket ceiling; the deck top is one
rectangle; the noise is Gaussian and range-independent.

## Result — C1 (150 frames: 3 poses × 5 yaws × 10 seeds)

| pose | observed | rms 2-D | max 2-D | rms yaw | derived ROI rows |
|---|---|---|---|---|---|
| staging 2.245 m | **50 / 50** | **0.0062 m** | 0.0096 m | 0.0008 rad | 202–215 |
| approach 1.5 m | **50 / 50** | **0.0078 m** | 0.0100 m | 0.0007 rad | 258–275 |
| approach 1.0 m | **45 / 50** | **0.0127 m** | 0.0279 m | 0.0005 rad | 324–343 |

Square pallet only (yaw 0, 10 seeds per pose), split by axis:

| pose | rms lateral | rms range | rms 2-D | observed |
|---|---|---|---|---|
| staging | 0.0007 m | 0.0060 m | 0.0060 m | 10 / 10 |
| approach 1.5 m | 0.0004 m | 0.0088 m | 0.0088 m | 10 / 10 |
| approach 1.0 m | 0.0013 m | 0.0097 m | 0.0098 m | 10 / 10 |

**0 of 145 poses at or over the bar.** The error is almost entirely in
range, and it is a **consistent under-read of 6–10 mm** — the residual
of the deck cut and the noise, not spread. Named, not tuned away.

Pocket span recovered: 0.5525–0.5587 m mean (geometry 0.560 m).

**Yaw.** `face_yaw` is now an angle about the floor's normal: rms error
0.0005–0.0008 rad over ±0.10 rad of pallet yaw. A1 reported
`atan(dz/dx)`, which is that angle times D / cos²(mount pitch); on the
same frames its rms error is **0.1138 rad at staging**, 0.0771 at 1.5 m,
0.0492 at 1.0 m — it scales with range, which is the giveaway. The
bench and `propose()` both read `face_yaw` now; `face_a` stays as a
diagnostic column.

**Latency**, pure Python on this laptop: `observe` mean 0.056 / 0.062 /
0.069 s. A1 measured 0.071 / 0.069 / 0.078 s median on the plant for
the same 640×480 frames, so the derived ROI is not slower — it fits a
strided grid and then only the pallet. Not an RTF claim; that is E5.

## Result — C2 (210 frames: 7 cases × 3 ranges × 10 seeds)

| case | expected | exact | words returned |
|---|---|---|---|
| clean | none | **30 / 30** | `none` ×30 |
| empty bay | pallet_absent | 30 / 30 | `pallet_absent` ×30 |
| rotated +0.25 | pallet_rotated | 30 / 30 | `pallet_rotated` ×30 |
| rotated −0.25 | pallet_rotated | 30 / 30 | `pallet_rotated` ×30 |
| pockets filled | pocket_blocked | 30 / 30 | `pocket_blocked` ×30 |
| bar in fork path | stringer_in_path | 30 / 30 | `stringer_in_path` ×30 |
| shifted 0.75 m | pallet_shifted | 30 / 30 | `pallet_shifted` ×30 |

**False aborts on clean frames: 0 of 30**, at all three ranges. The
word no longer depends on range. `classify` mean 0.085 s, max 0.288 s.

`proceed` is still not a reason and not a kind.

## Open, by name

1. **The plant has not been re-run.** E1 and E3 are the score and they
   are NOT_RUN on this branch. Every number above is rendered.
2. **C1 refuses 5 of 50 frames at 1.0 m when the pallet is yawed
   ±0.10 rad** (3 at −0.10, 2 at +0.10). All five are refusals — no
   pose emitted — not wrong poses. At 1.0 m the face fills the frame,
   a 0.10 rad yaw spreads it 0.12 m in horizontal distance, and the
   validated pocket pair does not always survive. Square pallets at
   1.0 m: 10 / 10.
3. **`pallet_shifted` without a `target_u` is a gross test only.** The
   pallet camera is mounted 0.40 m off the centreline, so a correctly
   staged pallet is always 0.40 m off-axis and the threshold has to be
   0.70 m. A shift small enough to miss a 0.16 m pocket will not be
   caught. `classify(frame, target_u=...)` exists and the node has the
   tag-derived target; wiring it is not done here.
4. **A load on the pallet is untested.** The height gate tops out at
   0.60 m; a boxed pallet would exceed it and read `pallet_absent`.
5. **Domain gap.** Rendered depth is not a gz GPU depth camera and
   neither is a real D455. Inherited from E1, unchanged.
6. **`find_pockets(frame, face_z)` was removed** from `m8_core.pocket`
   and replaced by `find_pocket_pair(frame, seg)`. It took a scalar
   face depth, which no longer exists as an input. Nothing outside
   `m8_core` and the tests called it.

## Files

| file | md5 |
|---|---|
| `m8/bench/results/scene-20260911-200542/c1_frames.csv` (150 rows) | `daa3b00274fe2f54881a44bd8148b9e0` |
| `m8/bench/results/scene-20260911-200542/c2_frames.csv` (210 rows) | `bd9b12742c4d9427912d81c1b6ec8191` |
| `m8/bench/results/scene-20260911-200542/summary.json` | `8e6c930c6a32c5b559053d584811f620` |
| `m8/bench/results/scene-20260911-200542/summary.txt` | `95e41a40739a0d2407c1824cc1c626d2` |

Code: `m8/m8_core/pocket.py` (rewritten), `m8/m8_core/abort.py`
(rewritten), `m8/m8_core/scene.py` (new), `m8/bench/offline_scene.py`
(new), `m8/tests/scenes.py` (new). Benches `e1_pocket.py` and
`e3_abort.py` log the derived ROI and read `face_yaw`; both still print
NOT_RUN and exit 2 without the plant
(`m8/tests/test_benches_not_run.py`).

Suite: **109 passed** (A1 offline: 79), `python -m pytest m8/tests`,
2.6 s, on a machine that has never sourced ROS.

## Next

Re-run E1 and E3 on the m5-ver3 plant from this branch and write the
result into new `m8/bench/results/` sessions. Per
`m8-h1-plant-run-2026-09-11`: do not re-run them to "confirm" the
baseline — run them after this change, which is what they are for.
Rig conditions: LF working tree (CRLF breaks the map md5 gate),
`GZ_PARTITION=m5v3 ROS_DOMAIN_ID=97`, Jazzy sourced,
`python3 m8/bench/plant.py probe` as the smoke test.
