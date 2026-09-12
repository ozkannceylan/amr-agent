# EVIDENCE_M8_C1C2_FIX — the classical rework of C1 and C2

Status: **OFFLINE MEASURED 2026-09-11; E1 AND E3 RE-RUN ON THE PLANT
2026-09-12** - see "On the plant" below, which supersedes the offline
numbers wherever the two disagree. E4/E5 remain NOT_RUN. Phase B stays
on HOLD: the live-dock false-abort rate does not support enabling it.
Offline session `m8/bench/results/scene-20260911-235921/`. Branch
`m8/c1c2-plane-roi-fix`, cut from `m5-ver3-close`.

FORWARD POINTER, added 2026-09-12, nothing else in this file edited and
no number changed: the four "Next" items and open items 1, 3, 4 and 7
are answered or advanced in `EVIDENCE_M8_E3_WORDS.md` on branch
`m8/c2-words-and-selfmask`. Static clean false-abort 30/90 -> 0/90 and
the live figure below, 0.884, -> 0.011 on 87 retry-free
pallet-readback-checked frames with the shadow nodes wired as they now
run. Phase B still HOLD. The sessions here were not overwritten.

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

## On the plant - E1 and E3 re-run, 2026-09-12

Same rig, same labels as the H1 baseline run: `traction=nominal`
`arm=wheel+imu` `loc=amcl@735cdbc6` `nav=on@7f57e6cf` `dock=on@1676eac0`
`docking=on@a462315f` `monitor=off` `partition=m5v3`, bringup
`run-20260911-235938`, 22 alive / 0 dead, GPU
`D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)`, CameraInfo fx = fy =
337.357. Nothing was tuned between the offline bench and these runs
except the two plant findings below, each of which was measured first.

### E1 - pocket pose, session `e1-20260912-000726`, 30 frames per pose

| pose | observed | rms lat | rms range | **rms 2-D** | rms yaw | **rms map chain** |
|---|---|---|---|---|---|---|
| staging 2.245 m | **30 / 30** | 0.0018 | 0.0064 | **0.0067 m** | 0.0012 rad | **0.0564 m** |
| approach 1.5 m | **30 / 30** | 0.0036 | 0.0070 | **0.0079 m** | 0.0015 rad | 0.0922 m |
| approach 1.0 m | **0 / 30** | - | - | - | - | - |

**The bar is the tag chain AT STAGING: rms 0.0706 m over 211 samples.
At staging, on the bar's own chain and the bar's own pose, C1 now reads
0.0564 m. THE BAR IS MET.** A1 read 0/30 there.

The 1.5 m map-chain figure, 0.0922 m, is above 0.0706 m and is **not a
comparison the bar supports** - the bar was measured at staging and has
no 1.5 m counterpart. Both map figures carry the localiser: the
registration instrument floor alone is rms 0.0291 / MAX 0.1179 m, and
the camera-frame column, which has no localiser in it, is 0.0067 and
0.0079 m.

Against the baseline, same three poses, same instrument:

| | A1 (`e1-20260911-125543`) | now |
|---|---|---|
| staging | 0 / 30 | 30 / 30 at 0.0067 m |
| 1.5 m | 0 / 30 | 30 / 30 at 0.0079 m |
| 1.0 m | 30 / 30 at **0.9223 m** (map 1.0342 m) | 0 / 30, refused by name |
| yaw on a square pallet | +0.3823 rad | 0.0012-0.0015 rad |

The derived ROI on the plant matches what the renderer predicted, which
is the cross-check that the offline instrument was worth having: staging
rows 202-213 cols 182-347 (offline 202-215 / 182-347), face width
1.2028 m (offline 1.203), pocket span 0.5567 m (offline 0.561, geometry
0.560). `observe` ran 0.044-0.049 s mean against A1's 0.071-0.078 s
median.

### Two plant findings, both named by the code

`m8/bench/diag_segment.py` is new and exists because `observed 0/30` is
not a diagnosis. Every refusal in `pocket` now carries a name.

**1. At staging the largest standing object was a WALL.** The pallet is
2.9 % of the frame at 2.245 m; a warehouse wall behind it is not.
Taking only the largest component above the floor picked a surface
0.807 m wide and 1.3555 m tall at 2.6432 m,
`face_height_not_pallet_sized` - a refusal with a pallet in plain view.
The segmentation now tries every candidate, best first, through the
whole gate set. Nothing was loosened. This is what turned staging from
0/30 into 30/30.

**2. At 1.0 m the truck's own forks are continuous with the pallet.**
A vehicle-fixed structure sits 0.5-1.0 m from this camera at 0.1 m above
the floor - about 730 coarse cells with the same signature at 1.0, 1.5
and 2.245 m, which is what identifies it as the truck's own forks rather
than scenery. At 1.5 m and staging there is clean floor between it and
the pallet, so it is a separate component. At 1.0 m it abuts the pallet
with **no range discontinuity** (adjacent-cell steps p50 0.0103, p90
0.0355, p99 0.0546, max 0.0721 m, and no step at the junction), so
depth-aware connectivity cannot split them either. The merged blob
leaves the face at 23-25 % of candidates and
`face_is_too_small_a_share` refuses. **The refusal is kept.** A wrong
pose in the last metre is worse than none, that regime belongs to
`opennav_docking`, and no threshold was moved to make it pass.

### E3 - abort classifier, session `e3-20260912-000826`

540 static frames (6 conditions x 3 poses x 30) and 2 clean live docks.

| staged condition | staging | 1.5 m | 1.0 m | exact overall |
|---|---|---|---|---|
| clean | **0 / 30 abort** | **0 / 30 abort** | 30 / 30 abort | - |
| pallet_absent | 30/30 | 30/30 | 30/30 | **90 / 90** |
| pallet_rotated 0.35 rad | 30/30 | 30/30 | 30/30 | 60 / 90 |
| pallet_shifted 0.30 m | 0/30 | 0/30 | 30/30 | 0 / 90 |
| pocket_blocked | 30/30 | 30/30 | 30/30 | 6 / 90 |
| stringer_in_path | 0/30 | 0/30 | 30/30 | 0 / 90 |

**The headline result: 60 of 90 clean static frames now read `none`.
A1 aborted on 90 of 90.** At staging and 1.5 m the false-abort rate on
clean frames is **0 / 30 and 0 / 30**. `pallet_absent` is exact 90/90
and `pallet_rotated` is exact wherever C1 can see the face at all.

**Everything at 1.0 m reads `pallet_absent`**, in all six conditions,
because C1 refuses there - finding 2 above. It is conservative (it
aborts rather than proceeding) and it is still wrong: the word claims
an empty bay when the pallet is there.

**Live clean docks: false-abort 0.884 overall** (948 aborts of 1073
classified frames), against A1's 252/252 = 1.000. Cycle 0 was 0.937
(997 frames), cycle 1 was 0.184 (76 frames). Both plugin runs finished
`success=True error=0`. The cycle-to-cycle asymmetry, and why cycle 0
classified 13x more frames than cycle 1, is **not explained**.

**PHASE B (abort live) STAYS ON HOLD.** A classifier that aborts 88 %
of the frames of a dock the plugin completes cleanly is not one to put
in front of a gate, and nothing here argues otherwise.

### Three misses, each with the cause named

1. **`pallet_shifted` 0.30 m: not caught at staging or 1.5 m** (both
   read `none`). This is the limitation already documented above, now
   measured: without a `target_u` the threshold has to be
   `SHIFTED_LATERAL_M` = 0.70 m, because the pallet camera is mounted
   0.40 m off the centreline and a correctly staged pallet is already
   that far off-axis. A 0.30 m shift is inside the gross threshold by
   construction. The fix is to pass the tag-derived target; the
   argument exists and the node is not yet wired to it.
2. **`stringer_in_path`: not caught at staging or 1.5 m.** The staged
   ridge is a 0.08 x 1.00 x 0.06 m box 0.6 m in front of the pallet.
   `fork_path_fraction` searches the standing object it segmented, and
   a ridge 0.6 m in front of the pallet is a DIFFERENT component that
   never enters that region. Widening the search to the whole fork
   corridor is the obvious fix and this run says it cannot be done
   safely on this camera: at the 1.5 m pose the staged ridge sits at
   0.9 m, inside the 0.5-1.0 m band the truck's own forks occupy at
   every pose, so a corridor search would abort on every clean frame
   instead. Separating them needs a self-mask from the mast/fork joint
   state, which `m8_core` does not have. **Named and left open, not
   patched.**
3. **`pocket_blocked`: aborts 90/90 but with the wrong word** (84
   `pallet_absent`, 6 `pocket_blocked`). The 0.10 x 0.72 x 0.10 m box
   across the openings changes the segmented object enough that C1
   refuses before the pocket test is reached. Cause not established -
   this one is open with its numbers, not with an explanation.

`classify` ran median 0.073 s, max 0.959 s over 1613 frames.

## Open, by name

1. **C1 sees nothing at 1.0 m on the plant** - the truck's own forks
   are continuous with the pallet at that range. Measured, named,
   refused rather than guessed. `opennav_docking` owns that regime
   and E1's own framing is the last two metres, but this is a real
   loss of coverage against A1, which produced a pose there (a wrong
   one, at 0.9223 m).
2. **Phase B cannot open on these numbers.** 0.884 live false-abort
   on two clean docks the plugin finished with error 0.
3. **`pocket_blocked` aborts with the wrong word** 84 times in 90.
   Cause not established.
4. **`stringer_in_path` needs a fork self-mask** before its search
   can widen beyond the pallet's own footprint.
5. **The live-cycle frame counts are unexplained** - 997 vs 76.
6. **Offline only:** C1 refuses 5 of 50 rendered frames at 1.0 m
   when the pallet is yawed +-0.10 rad. All five are refusals, not
   wrong poses.
7. **`pallet_shifted` without a `target_u` is a gross test only.** The
   pallet camera is mounted 0.40 m off the centreline, so a correctly
   staged pallet is always 0.40 m off-axis and the threshold has to be
   0.70 m. A shift small enough to miss a 0.16 m pocket will not be
   caught. `classify(frame, target_u=...)` exists and the node has the
   tag-derived target; wiring it is not done here.
8. **A load on the pallet is untested.** The height gate tops out at
   0.60 m; a boxed pallet would exceed it and read `pallet_absent`.
9. **Domain gap.** gz depth is not a real D455. Inherited from E1,
   unchanged. The rendered instrument is now cross-checked against
   the plant - ROI, face width and pocket span agree to a few
   millimetres - which is the most that can be said for it.
10. **`find_pockets(frame, face_z)` was removed** from `m8_core.pocket`
   and replaced by `find_pocket_pair(frame, seg)`. It took a scalar
   face depth, which no longer exists as an input. Nothing outside
   `m8_core` and the tests called it.

## Files

| file | md5 |
|---|---|
| `m8/bench/results/scene-20260911-235921/c1_frames.csv` (150 rows) | `631895ea011364eeb9b14a4a5668dc23` |
| `m8/bench/results/scene-20260911-235921/c2_frames.csv` (210 rows) | `93df4432fad19498a500132185387e73` |
| `m8/bench/results/scene-20260911-235921/summary.json` | `9acd6fa737fdbe2dfcf989b25de2ab00` |
| `m8/bench/results/scene-20260911-235921/summary.txt` | `9f94dbcd140ad8620ea6f35a9f3bc598` |
| `m8/bench/results/e1-20260912-000726/frames.csv` (90 rows) | `bd52a48a36512064da2ecd8aab8d4d2d` |
| `m8/bench/results/e1-20260912-000726/summary.json` | `600b93a5ebaae355fa0f3a868a83aee4` |
| `m8/bench/results/e1-20260912-000726/summary.txt` | `33c27ff3f3fc56e732ce635452291ad3` |
| `m8/bench/results/e1-20260912-000726/session.json` | `6d565ee760a3a0a7edf313714d2f950d` |
| `m8/bench/results/e3-20260912-000826/frames.csv` (540 rows) | `54f76d9082e594c63b16c82fc112dce1` |
| `m8/bench/results/e3-20260912-000826/cycles.csv` (1073 rows) | `ebc7691b1ad7b4596ad14c700863b2ef` |
| `m8/bench/results/e3-20260912-000826/summary.json` | `501d6374d6b6e1348841bf9c611692b2` |
| `m8/bench/results/e3-20260912-000826/summary.txt` | `996fec01c8b2ec40c95ed1c548f759f7` |
| `m8/bench/results/e3-20260912-000826/session.json` | `284c79e3dca1f435ee2286b91209e315` |
| `m8/bench/results/e1-20260912-000119/` (the first E1, before the multi-candidate fix; kept because it is what named the wall) | `21cb0a7f152f3c4bb251480ad266c91a` (frames.csv) |

Code: `m8/m8_core/pocket.py` (rewritten), `m8/m8_core/abort.py`
(rewritten), `m8/m8_core/scene.py` (new), `m8/bench/offline_scene.py`
(new), `m8/tests/scenes.py` (new). Benches `e1_pocket.py` and
`e3_abort.py` log the derived ROI and read `face_yaw`; both still print
NOT_RUN and exit 2 without the plant
(`m8/tests/test_benches_not_run.py`).

Suite: **109 passed** (A1 offline: 79), `python -m pytest m8/tests`,
2.6 s, on a machine that has never sourced ROS.

## Next

E1 and E3 are RUN. What is left, in the order the numbers argue for it:

1. Wire the tag-derived target into `abort.classify(target_u=...)` and
   `pocket.observe(expected_range=...)` in the shadow nodes. It is the
   single change that answers miss 1 and narrows the window everywhere.
2. Decide what C1 should do in the last metre, given that the forks and
   the pallet are one surface to this camera. Two options are measured
   enough to choose between: hand the regime to `opennav_docking` by
   contract, or add a fork self-mask from the mast joint state.
3. Explain `pocket_blocked`'s word, and the live-cycle frame counts.
4. E4 and E5 remain NOT_RUN.

Phase B stays on HOLD until the live false-abort rate is a number a
gate could stand on. Rig conditions for the next run: LF working tree
(CRLF breaks the map md5 gate), `GZ_PARTITION=m5v3 ROS_DOMAIN_ID=97`,
Jazzy sourced, `python3 m8/bench/plant.py probe` as the smoke test, and
`python3 m8/bench/diag_segment.py` whenever a bench says `observed 0/n`.
