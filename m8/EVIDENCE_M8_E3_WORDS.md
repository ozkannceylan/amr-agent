# EVIDENCE_M8_E3_WORDS — the word a frame deserves, and the truck in its own camera

Status: **RUN 2026-09-12 on the m5-ver3 plant, this rig.** Branch
`m8/c2-words-and-selfmask`, cut from `35ed6aa` (PR #11 head
`m8/c1c2-plane-roi-fix`, which stays open and unmerged). Three plant
sessions and one offline session, all new folders:

| session | what it is |
|---|---|
| `e3-20260912-181548` | the first run. Full static + live. It found a defect in this branch's own tag wiring, and it is kept because that is what it measured. |
| `e3-20260912-184020` | static grid, 540 frames, corrected wiring. Its LIVE half is degraded by an instrument fault named below and is not quoted as a rate. |
| `e3-20260912-190415` | live cycles only, 87 countable frames, corrected wiring and threaded pallet watch. This is the live number. |
| `words-20260912-190835` | offline, 22 rendered cases x 5 seeds. Not a plant result. |

**No baseline was overwritten and no existing result folder was
touched.** `EVIDENCE_M8_E3.md` (A1), `EVIDENCE_M8_E1.md` and
`EVIDENCE_M8_C1C2_FIX.md` stand as they were; `e3-20260911-125645`,
`e3-20260912-000826`, `e1-20260912-000726` and `a288a4e` are all intact.

## Standing cautions

Ground truth is a score, not a command. No PL / SIL / PFH claims. The
Nav2 collision monitor is not a safety function. The F-PLC never
receives M8 input. Frames never leave the truck. `proceed` is never an
M8 output, is not a reason, and is not counted anywhere below — where
this file says a frame reads `none`, the shadow node publishes NOTHING,
which is not an endorsement of the dock.

**PHASE B (abort live) STAYS ON HOLD.** Nothing here asks for it.

## The bar, and whether it is met

The interim bar set for this work: **live false-abort < 0.10, on clean
cycles only — `num_retries == 0` AND a valid pallet readback.** Retries
and moved-pallet frames are reported separately and never folded in.

Population, `e3-20260912-190415`: **87 frames** — every classified frame
of two docks `opennav_docking` finished `success=True error=0
retries=0`, each frame carrying a pallet readback taken within one
second of it. 0 frames were excluded for a retry, 0 for an unjoined
retry count, 0 for a moved or unread pallet.

| classifier | aborts / 87 | false-abort | bar |
|---|---|---|---|
| C2 as this branch changed it, no mask, no tag | 16 | **0.184** | NOT met |
| C2 **as the shadow nodes now run it** — fork self-mask + tag | **1** | **0.011** | **MET** |

Against the baseline this branch was measured against
(`e3-20260912-000826`, 948 aborts of 1073): **0.884 → 0.011.**

The two rows are the SAME 87 depth buffers, classified twice. That is
why the difference is attributable to the wiring and not to the weather.

## What changed, in five steps

No threshold in `m8_core` moved. `ABSENT_VALID_FRAC`, `ROTATED_ABS_RAD`,
`STRINGER_NEAR_M`, `STRINGER_NEAR_FRAC`, `SHIFTED_LATERAL_M`,
`FACE_INLIER_FRAC_MIN`, `PALLET_FACE_WIDTH_M`, `PALLET_FACE_HEIGHT_M`,
`POCKET_SPAN_M`, `POCKET_WIDTH_M`, `DOCK_ENVELOPE_M`, `TAG_WINDOW_M` and
`FORK_BAND_M` are all unchanged from `35ed6aa`.

**0. The instrument.** `e3-20260912-000826` reported 0.884 over 1073
frames and held no column that could say what the 948 aborts were. Four
joins were added with no classifier change: the range band a frame was
taken in; the NAMED refusal `segment` raised for it; `num_retries` and
the docking state at the frame's own sim stamp, joined from the dock
session's `feedback.csv`; and the pallet's gz pose, read back on a timer
DURING the cycle.

**1. The word policy.** `pallet_absent` answered "no segmented face"
whatever the reason, and inside 1.2 m the reason is that the truck's own
forks are continuous with the pallet. `pallet_absent` now needs
evidence: a candidate that was measured and found not to be a pallet.
One "could still be the pallet" refusal outvotes any number of others,
and a refusal name nobody classified says nothing. Separately, an object
that runs off the edge of the image is measured on a PART, so it
supports no word about the whole pallet — but clipping only undermines a
LOWER bound, so "too wide", "too tall" and "this is a floor" survive it,
and `stringer_in_path` survives it too.

**2. The fork self-mask.** `m8_core/selfmask.py`, every number off
`forklift_ver3/model.sdf` and `config.yaml`: tine tips 0.975 m along the
optical axis, lateral spans −0.74…−0.62 and −0.18…−0.06 m, top
0.100 m + `mast_joint` above the floor. A STALE joint reading makes the
classifier say nothing rather than publish a word derived from a frame
it may have cut a hole in — at the 1.0 m pose the tips are 25 mm from
the pallet face, so a mask in the wrong place there deletes the pallet.

**3. Occluder-aware share: NOT DONE, and the measurement says why.** The
brief gated this on a plant-measured step 2, and step 2 is measured. It
is not the cause. `pocket_blocked` reads `pallet_absent` because the
surviving candidate is refused by the SHAPE gate, not the share gate:
offline, `blocked_by_box` refuses with `candidate_falls_away_like_a_floor`
at an inlier fraction of **1.0** — nothing is being crowded out. See
"Open item 3, cause established" below. Changing a denominator that the
measurement exonerates is not a fix.

**4. Fork-corridor stringer: NOT DONE.** Optional and last in the brief.
`stringer_in_path` recall is 0/90 on the staged ridge and this is the
largest remaining gap; the self-mask removes the blocker
`EVIDENCE_M8_C1C2_FIX` miss 2 named, so it is now buildable. It is not
built here and it is not measured here.

**5. The tag, wired.** `m8_nodes/tag_target.py` turns apriltag_node's own
TF broadcast into narrowing arguments. **The first plant run proved the
first version of it wrong** — see the next section, which is the most
load-bearing thing in this file.

## The defect this branch found in itself

`e3-20260912-181548` is kept because of this. The first wiring read the
tag's range straight into `expected_range`. The plant answered in one
table:

| population | `none` → `pallet_absent` |
|---|---|
| frames that had a tag | **57 of 113** |
| frames carrying only the fork self-mask | **0 of 427** |

**On this rig the AprilTag is the DOCK MARKER on the bay back panel, not
a pallet tag.** Measured over 113 frames, the tag is **0.8525 m further
from the camera than the pallet face** (per pose 0.8603 / 0.8377 /
0.8583 m; spread inside a pose 0.0005 m). The window is ±0.40 m wide, so
the offset is more than twice its half width: the window opened around
the panel and the pallet fell outside it.

Two corrections, neither fitted to that reading:

1. `FACE_AHEAD_OF_MARKER_M = 0.82`, from **config** — `pallet.depth_m`
   0.80 plus `pallet.wall_clearance_m` 0.02. The plant read 0.8525 m.
   **The 0.0325 m residual is stated and left.** It is an order inside
   the window it opens, and tuning a geometry constant onto a bench
   reading is how a number stops meaning what it says.

2. **A reference column is only a reference at one depth.** The marker
   and the pallet stand on one line in the world, but this camera is
   0.40 m off the vehicle centreline and they are 0.85 m apart in depth,
   so they project to different columns — measured **12 px apart at
   staging, 27 at 1.5 m, 57 at 1.0 m**. In METRES there is no drift at
   all: the tag read **−0.4019 / −0.3979 / −0.3994 m** at those same
   three poses, which is the mount offset and nothing else. `classify`
   therefore takes `target_lateral_m`, a reference in metres, subtracted
   where the depth is already known.

`target_u` and `target_v` are **not** passed on this rig: seeding the
candidate choice on a marker 0.73 m above the pallet ranks the marker
board first, which is the wrong object. `tag_z` is not passed to C1
either — it is the marker's depth, so a pose delta against it would read
0.85 m off on every frame.

## Result — static grid, `e3-20260912-184020`

540 frames: 6 conditions x 3 poses x 30. Cells are `aborts / frames
[reason-exact]`. Left of each pair is C2 with no mask and no tag, which
is directly comparable with the two baselines.

| condition | staging 2.245 m | approach 1.5 m | approach 1.0 m | overall |
|---|---|---|---|---|
| `clean` | 0/30 [0] | 0/30 [0] | **0/30 [0]** | **0/90 false aborts** |
| `pallet_absent` | 30/30 [30] | 30/30 [30] | 30/30 [30] | 90/90, exact **90** |
| `pallet_rotated` | 30/30 [30] | 30/30 [30] | 30/30 [0] | 90/90, exact 60 |
| `pallet_shifted` | 0/30 [0] | 0/30 [0] | 2/30 [0] | 2/90, exact 0 |
| `pocket_blocked` | 30/30 [4] | 30/30 [0] | 30/30 [0] | 90/90, exact 4 |
| `stringer_in_path` | 0/30 [0] | 0/30 [0] | 0/30 [0] | 0/90, exact 0 |

Against the two baselines, clean frames only:

| | A1 (`e3-20260911-125645`) | C1/C2 fix (`e3-20260912-000826`) | this branch |
|---|---|---|---|
| clean static false aborts | 90 / 90 | 30 / 90 | **0 / 90** |
| of which at 1.0 m | 30 / 30 | 30 / 30 | **0 / 30** |

**The 1.0 m column is the whole of the change.** `EVIDENCE_M8_C1C2_FIX`
recorded "everything at 1.0 m reads `pallet_absent`, in all six
conditions". It no longer does, and the bay is not claimed empty when it
is full.

### The same 540 frames, AS THE NODES NOW RUN THEM

| condition | staging | 1.5 m | 1.0 m |
|---|---|---|---|
| `clean` | 0/30 [0] | 0/30 [0] | 0/30 [0] |
| `pallet_absent` | 21/30 [21] | 29/30 [29] | 29/30 [29] |
| `pallet_rotated` | 29/30 [29] | 29/30 [29] | **29/30 [29]** |
| `pallet_shifted` | 0/30 [0] | 0/30 [0] | 0/30 [0] |
| `pocket_blocked` | 29/30 [4] | 29/30 [0] | 29/30 [0] |
| `stringer_in_path` | 0/30 [0] | 0/30 [0] | 0/30 [0] |

- clean false aborts **0 of 90**, unchanged;
- frames the segmentation could resolve at all: **244 → 364**, no losses;
- reason-exact: **154 → 170**;
- `pallet_rotated` at 1.0 m: exact **0/30 → 29/30**. That regime was
  `EVIDENCE_M8_C1C2_FIX` open item 1, and the self-mask is what returns
  it.
- **`pallet_absent` exact 90/90 → 79/90, and that is a real loss** — see
  lost coverage 2.

## Result — live cycles, `e3-20260912-190415`

Two docks, `dock_bench.py stage` then `record --from-staging`, the
m5-ver3 instrument run as it is, classifier streaming the whole way in.

| cycle | plugin | retries | pallet moved by end | classified | aborts | false-abort |
|---|---|---|---|---|---|---|
| 0 | success True, error 0 | 0 | 0.2372 m | 45 | 9 | 0.200 |
| 1 | success True, error 0 | 0 | 0.0696 m | 42 | 7 | 0.167 |

All 87 frames joined a retry count (165 and 161 feedback rows) and all
87 carry a pallet readback. **Countable: 87 of 87.**

| | baseline classifier | as wired |
|---|---|---|
| staging band (≥ 2.0 m) | 0 / 38 | 0 / 38 |
| approach band (1.2–2.0 m) | 1 / 31 | 0 / 31 |
| close band (< 1.2 m) | **15 / 18** | **1 / 18** |
| overall | 16 / 87 = **0.184** | 1 / 87 = **0.011** |

The words that moved, on the same buffers: `pallet_absent → none` 14,
`stringer_in_path → none` 1. Segmentations gained 12, lost 0.

**Every remaining false abort is in the close band**, which is the band
the forks own, and the self-mask is what empties it.

### THE PALLET MOVES DURING A CLEAN DOCK, AND THE BASELINE COULD NOT SEE IT

The dock drives the forks INTO the pallet, so a cycle the plugin calls
clean does not end with a clean world. Measured here at 0.2372 m and
0.0696 m; measured at **0.4715 m** in `e3-20260912-181548`. Read back
only at the ends of a cycle, that made every frame of it uncountable —
including the whole approach taken before anything touched anything. The
readback now runs on a 1 Hz thread and `countable` is decided per frame.
`e3-20260912-000826`'s 0.884 was measured with no readback at all.

## Offline — `words-20260912-190835`, 22 cases x 5 seeds

Rendered depth (`m8_core.scene`), no plant, no ROS. Necessary, never
sufficient: the renderer and the estimator share a flat floor, a flat
face, a pinhole camera and Gaussian noise, so a mistake inside that
shared assumption cannot appear. Six families now exist offline that did
not before — `forks`, `forks_empty`, `blocked_by_box`, `ridge`,
`clipped` — and each is a plant finding rendered, not a fixture invented.

| | |
|---|---|
| false aborts on frames expected clean | **0 of 40** |
| reason-exact | 85 of 110, unmasked and masked |
| frames the segmentation resolved | 70 → **75** with the mask |
| every frame, with a STALE mask | `none` on **110 of 110** |

`forks@1.0` is the 0.884 reproduced and then removed: refused
`face_is_too_small_a_share` with no mask, segmented 5/5 with one, and
`none` either way. `forks_empty` is `pallet_absent` 15/15 at all three
poses with the tines in view, so the silence was not bought with the
empty bay.

The renderer grew one primitive for this: a horizontal slab, which is
what a fork reaching toward a pallet is and what a fronto-parallel
obstacle could not render.

## Named lost coverage

1. **`stringer_in_path` and `pallet_shifted` at 1.0 m are now silent
   where they used to abort.** A1 and the C1/C2 fix aborted on 30/30 of
   each at that pose — with the word `pallet_absent`, exact 0. The trade
   is 60 wrong-word aborts for 60 silences, against reason-exact 156 →
   154. Fail-safe direction lost, wrong word not gained.
2. **`pallet_absent` exact 90/90 → 79/90 as wired**, and 9 of the 11 are
   at staging. The tag narrows the range window to ±0.40 m around where
   the pallet SHOULD be, and an empty bay has nothing in that window at
   all, so the frame refuses `too_few_points_in_window` — "too little to
   measure", which the word policy deliberately treats as saying
   nothing. Silence on an empty bay is the safe direction and it is
   still a loss against the number it replaces.
3. **A frame with almost no valid pixels is still `pallet_absent`.**
   That is also what a blind camera looks like. The word is kept and
   sensor health stays `m8_health`'s.
4. **`pocket_blocked` exact is 4 of 90**, unchanged by anything here.
5. **Domain gap.** gz depth is not a real D455. Inherited, unchanged.

## Open, by name

1. **`stringer_in_path` recall is 0/90.** The staged ridge is a separate
   component 0.60 m in front of the pallet and `fork_path_fraction`
   searches the pallet's own standing object. The corridor search that
   would catch it was blocked by the tines; the self-mask unblocks it;
   it is step 4 and it is NOT DONE.
2. **Open item 3, CAUSE ESTABLISHED** — it was "cause not established".
   `blocked_by_box` reads `pallet_absent` because the staged box stands
   0.06 m in front of the face and `FACE_SEED_BAND_M` is 0.06 m, so the
   box is inside the seed band by one millimetre of margin. The fit then
   spans two parallel planes 0.06 m apart with the nearer one lower in
   the image, and the resulting dz/dy of −0.63 trips the floor guard at
   `FACE_MIN_DZ_DY` = −0.5. Face width comes out 1.1993 m against a
   geometry of 1.200: the face WAS found, the plane through it was not
   vertical. Reproducible offline now. The fix is a threshold move and
   was out of scope here.
3. **The 0.0325 m residual** between the config marker offset and the
   plant reading is unexplained. It is stable to 0.0005 m within a pose
   and varies 0.023 m between poses, so it is not noise.
4. **`pallet_shifted` 0.30 m is still not caught.** The tag removes the
   0.40 m mounting bias and makes the 0.70 m test symmetric; catching
   0.30 m needs a smaller threshold and no threshold moved here.
5. **THE RIG DROPPED `gz set_pose` TWICE IN FIVE RUNS**, at 4 and 9
   minutes into a run, with every process ALIVE and `gz service -l`
   returning nothing. A plant stop, `wsl --shutdown` and a cold start
   cleared it both times. Splitting the bench into a static run and a
   cycles-only run cuts the exposure and is how the numbers above were
   taken. Not diagnosed.
6. **The live-cycle frame counts are still not explained** — 997 / 76 in
   the baseline, 45 / 42 here. The instrument now shows one contributor:
   anything blocking the spin loop starves the 5-deep depth queue. A
   `gz model -p` called from that loop cost cycle 0 all but ONE frame in
   `e3-20260912-184020`. That is a bench fault, now fixed, and it is not
   the whole of the baseline's variance.
7. **E4 and E5 remain NOT_RUN.**
8. **Phase B stays on HOLD.** 0.011 on 87 frames of two docks is not a
   number a gate opens on, and this file does not ask for one.

## Files

| file | md5 |
|---|---|
| `m8/bench/results/e3-20260912-181548/frames.csv` (540 rows) | `a92d863b42098c01c395b8d1ecd28fb0` |
| `m8/bench/results/e3-20260912-181548/cycles.csv` (146 rows) | `261492e32c45765ba2620a10357bcf20` |
| `m8/bench/results/e3-20260912-181548/summary.json` | `e221d3e0df7a90c627b1f6c89758cf2a` |
| `m8/bench/results/e3-20260912-181548/summary.txt` | `31481417327399770c158b2fb928232f` |
| `m8/bench/results/e3-20260912-181548/session.json` | `3504294dd885007cccaa1b3456fda4aa` |
| `m8/bench/results/e3-20260912-184020/frames.csv` (540 rows) | `bc3e038c5c860db43c8e4d6fab6adf50` |
| `m8/bench/results/e3-20260912-184020/cycles.csv` (15 rows) | `0d6099eb4627de3ee95b48d5088a3dbd` |
| `m8/bench/results/e3-20260912-184020/summary.json` | `2b4b22b734b8bdede22af721fc8fe39c` |
| `m8/bench/results/e3-20260912-184020/summary.txt` | `b4854f4ec64763f0f1d00da0748e6123` |
| `m8/bench/results/e3-20260912-184020/session.json` | `07daad6d44b46980c594347c076973a7` |
| `m8/bench/results/e3-20260912-190415/cycles.csv` (87 rows) | `57ec2479789a39f4121c8c5ef81446df` |
| `m8/bench/results/e3-20260912-190415/summary.json` | `faf645277719025c39282ed599cff0af` |
| `m8/bench/results/e3-20260912-190415/summary.txt` | `54cffd505efb3825726aca2b5bd2185a` |
| `m8/bench/results/e3-20260912-190415/session.json` | `8a67b261d4b033eba0834cfa18c10a40` |
| `m8/bench/results/words-20260912-190835/frames.csv` (110 rows) | `e6a694b5aa097ce69dc0afdb372f9455` |
| `m8/bench/results/words-20260912-190835/summary.json` | `7f120f0aea3d43c4dc04de56b76bacc1` |
| `m8/bench/results/words-20260912-190835/summary.txt` | `98d99b3b4aa790d2f5be352b9b975870` |

`e3-20260912-190415/frames.csv` is a header and no rows: that session
was run `--ranges ""`, so it measured no static grid and says so rather
than carrying a stale one.

## Environment

Same rig and same labels as both baselines: `traction=nominal`
`arm=wheel+imu` `loc=amcl@735cdbc6` `nav=on@7f57e6cf` `dock=on@1676eac0`
`docking=on@a462315f` `monitor=off` `partition=m5v3`, CameraInfo
fx = fy = 337.357 on 640x480. Bringups `run-20260912-181358` (session
181548), `run-20260912-183842` (184020) and `run-20260912-190246`
(190415), each 22 alive / 0 dead, GPU `D3D12 (NVIDIA GeForce RTX 4050
Laptop GPU)`, Gazebo Sim 8.11.0, ROS 2 Jazzy.

`classify` median 0.064 s, max 0.109 s. The as-wired pass is a second
classification of the same buffer and is timed separately; neither is an
RTF claim, which is E5's and still NOT_RUN.

Suite: **187 passed**, `python -m pytest m8/tests`, on a machine that
has never sourced ROS (`121` at `35ed6aa`).

Benches: `m8/bench/e3_abort.py` (plant), `m8/bench/offline_words.py`
(no plant). Both print `NOT_RUN` and exit 2 without their prerequisites
where that applies (`m8/tests/test_benches_not_run.py`).

Rig conditions for the next run, measured here: LF working tree, a COLD
`wsl --shutdown` before bringup, `GZ_PARTITION=m5v3 ROS_DOMAIN_ID=97`,
Jazzy sourced, `python3 m8/bench/plant.py probe` as the smoke test, and
**the static grid and the live cycles as two separate invocations** —
`--cycles 0` then `--ranges ""` — because a single run is long enough to
meet the gz service fault.
