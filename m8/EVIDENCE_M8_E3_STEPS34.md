# EVIDENCE_M8_E3_STEPS34 — the occluder, the footprint, and the corridor

Status: **RUN 2026-09-18 on the m5-ver3 plant, this rig.** Branch
`m8/c2-steps-3-4-unwired`, cut from `92422ea` (the tip of
`m5-ver3-close`, PR #12 merged). Steps 3 and 4 of the E3 false-abort
brief, which `EVIDENCE_M8_E3_WORDS.md` recorded as NOT DONE.

**THE INTERIM BAR IS MET WIRED AND IS NOT MET UNWIRED.** On the live
bar population, paired against the parent classifier on the same rig
the same afternoon: unwired **0.322 → 0.143**, wired **0.105 →
0.093**. The bar is < 0.10. Wired clears it; unwired does not, and
every remaining false abort is inside 1.2 m.

| session | what it is |
|---|---|
| `words-20260918-120852` | offline, 29 rendered cases x 5 seeds. Not a plant result. |
| `e3-20260918-121233` | plant static grid, 540 frames, this branch. |
| `e3-20260918-122007` | plant live, 2 cycles. **It measured a defect in this branch's own corridor test and it is kept because that is what it measured.** |
| `e3-20260918-122540` | plant live, 2 cycles, corridor corrected. |
| `e3-20260918-122922` | plant live, 4 cycles, corridor corrected. This is the live number. |
| `e3-20260918-123209` | **CONTROL**: live, 4 cycles, classifier at `92422ea`, same bringup, minutes later. |
| `e3-20260918-124737` | **CONTROL**: static grid, 540 frames, classifier at `92422ea`, cold rig. |

**No baseline was overwritten and no existing result folder was
touched.** `EVIDENCE_M8_E3.md`, `EVIDENCE_M8_E3_WORDS.md`,
`EVIDENCE_M8_E1.md` and `EVIDENCE_M8_C1C2_FIX.md` stand as they were,
and every `e3-2026091[12]-*`, `e1-*`, `scene-*` and
`words-20260912-190835` folder is intact. The two control folders each
carry a `CONTROL.md` naming the commit they were produced by.

## Standing cautions

Ground truth is a score, not a command. No PL / SIL / PFH claims. The
Nav2 collision monitor is not a safety function. The F-PLC never
receives M8 input (R4). Frames never leave the truck (R3). `proceed`
is never an M8 output, is not a reason, and is not counted anywhere
below — where this file says a frame reads `none`, the shadow node
publishes NOTHING, which is not an endorsement of the dock.

**PHASE B (abort live) STAYS ON HOLD.** Nothing here asks for it.

## WHY EVERY LIVE FIGURE HERE IS PAIRED, AND THE ONE THAT IS NOT

`EVIDENCE_M8_E3_WORDS.md` measured unwired **0.184** and wired
**0.011** on 87 frames of two docks on 2026-09-12. Those numbers are
not this file's baseline, and the control run is why. **The same
classifier, at the same commit, reads 0.322 unwired and 0.105 wired on
today's docks** (`e3-20260918-123209`, 152 frames of four docks). The
live rate is dominated by the close band, the close band is whatever
the approach geometry was, and a dock is not repeatable across a week.

So every live comparison below is against `e3-20260918-123209`: the
parent classifier, run from a detached worktree against the SAME
running plant (`run-20260918-122358`), on the same four-cycle protocol,
minutes apart. It is not the same four docks — that is the one thing a
paired plant run cannot buy — but it is the same rig, the same
bringup, the same day and the same protocol.

The static grid is teleported to fixed poses and is far more
repeatable, and it is paired too (`e3-20260918-124737`, cold rig).

## THE BAR — live cycles, `e3-20260918-122922` against the control

Bar population: **`num_retries == 0` joined from the dock session's
`feedback.csv`, on a frame whose pallet was read back within 0.02 m of
where the cycle started, AT THAT FRAME.** Retries and moved-pallet
frames are reported separately and never folded in.

| | control `92422ea` | **this branch** | bar |
|---|---|---|---|
| countable frames | 152 of 901 | 140 of 203 | |
| **unwired false-abort** | 49 / 152 = **0.322** | 20 / 140 = **0.143** | **NOT met** |
| **wired false-abort** | 16 / 152 = **0.105** | 13 / 140 = **0.093** | **MET** |
| staging (>= 2.0 m) | 0 / 40 | **0 / 42** | |
| approach (1.2-2.0 m) | 2 / 58 = 0.034 | **0 / 57 = 0.000** | |
| close (< 1.2 m) | 47 / 54 = 0.870 | **20 / 41 = 0.488** | |

Excluded and reported separately, this branch: on a retry 0, retry
count unjoined 39, pallet moved or unread 24. Control: on a retry 487,
unjoined 32, moved or unread 230 — the control's four docks retried and
this branch's did not, which is a difference in the DOCKS and not in
the classifier: nothing in M8 reaches a controller (R4, and the veto
gate still refuses every proposal).

**Every remaining false abort on this branch is inside 1.2 m.** The
staging and approach bands are now silent on clean docks — 99 frames,
0 aborts, against the control's 2 of 98.

## The twenty, by name

Every one of the 20 unwired false aborts, from
`e3-20260918-122922/cycles.csv`, with the columns this branch added to
the instrument:

| n | word | what the frame actually shows |
|---|---|---|
| 5 | `pallet_rotated` | one skewed approach (cycle 1). The measured face yaw walks smoothly from -0.104 rad at 1.15 m to -0.223 at 0.79 m while the pallet readback says it moved 0.00000 m. **The pallet is not rotated; the TRUCK is**, and `face_yaw` is a RELATIVE angle. C2 takes no vehicle pose by design, so it cannot separate the two. The plugin finished that dock `success=True error=0 retries=0`. |
| 10 | `pallet_absent` | inside 0.94 m the segmentation collapses. Six of the ten refuse `face_width_not_pallet_sized` at a measured width of **0.528 to 0.566 m**, against `PALLET_FACE_WIDTH_M[0] = 0.60` — TOO NARROW, on a blob whose deck was cut at 0.88 to 0.97 m above the floor, from 2869 to 3289 points. Four refuse `candidate_falls_away_like_a_floor` on fragments of 46 to 150 points. |
| 4 | `pocket_blocked` | 0.98 to 1.15 m, face segmented cleanly (width 1.174 to 1.184 m against a true 1.200), truck yawed -0.104 to -0.132 rad. The face is beyond the tines' reach so the pocket claim is allowed, and one pocket is foreshortened away. |
| 1 | `stringer_in_path` | 0.759 m, on a frame whose face segmented at 0.614 m wide — half a pallet. The corridor is measured against a face that is itself wrong. |

**What the too-narrow reading is, is not established.** It is a
standing object about a metre tall and about 0.55 m wide, 0.6 to 0.9 m
from a camera that is 1.10 m up and pitched 0.5236 rad down, and the
truck's own mast and carriage are NOT it — `forklift_ver3/model.sdf`
puts the carriage at base x -0.85...-0.75 and the mast at
-0.83...-0.73, which through `d = -0.900 - x_base` is 0.05 m in front
of the camera at most, at or behind its own image plane. Naming it
needs a frame dump and this run did not take one (R3: frames do not
leave the truck, so that is a rig-side artefact and a separate task).

**That the reading is too NARROW and not too wide is itself new.**
`e3-20260912-190415` had 13 of its 16 unwired aborts refusing
`face_width_not_pallet_sized` and no column that could say which side
of the window it fell on — `seg_width_m` is only written when a frame
segments. The `refused_width_m`, `refused_height_m` and
`refused_deck_cut_m` columns added here are that join, and they are
what turned "13 aborts, cause unknown" into the row above.

## THE STATIC GRID — `e3-20260918-121233` against `e3-20260918-124737`

Both 540 frames, 6 conditions x 3 poses x 30, same rig, both from a
cold start. Cells are `aborts / frames [reason-exact]`.

| condition | control `92422ea` | **this branch** |
|---|---|---|
| `clean` | **0 / 90** false aborts | **0 / 90** |
| `pallet_absent` | 90/90 [90] | 90/90 [90] |
| `pallet_rotated` | 90/90 [**60**] | 90/90 [**89**] |
| `pallet_shifted` | **1**/90 [0] | **0**/90 [0] |
| `pocket_blocked` | 90/90 [6] | 90/90 [7] |
| `stringer_in_path` | **30**/90 [**0**] | **60**/90 [**60**] |
| reason-exact, total | **156** | **246** |
| frames the segmentation resolved | 246 | **366** |

Named refusals behind those words:

| | control | this branch |
|---|---|---|
| `(segmented)` | 246 | **366** |
| `face_width_not_pallet_sized` | 209 | 174 |
| `candidate_falls_away_like_a_floor` | 41 | **0** |
| `too_few_face_inliers` | 44 | **0** |

`clean` holds at 0 of 90 with 120 more frames resolved, which is the
only way that number means anything.

### `stringer_in_path`: 0/90 exact to 60/90 exact, and what it cost

`EVIDENCE_M8_E3_WORDS.md` open item 1. The control aborts 30 of 90 and
gets the word right **0 times**: all 30 are at the 1.0 m pose and all
30 say `pallet_absent`. This branch aborts 60 of 90 and every one of
the 60 names the fault — staging 30/30 and 1.5 m 30/30.

**The 1.0 m pose is 0/30 on this branch and that is a lost fail-safe
abort, stated plainly.** It is also not recoverable by any search: the
staged ridge sits 0.60 m in front of the pallet, so at the 1.0 m pose
it is 0.40 m from a camera 1.10 m above the floor. The ray to it is
**69 degrees below horizontal** and this frame stops at **65** —
atan(120/168.68) = 35.4 deg of half-angle about an axis pitched 30 deg
down. The ridge is under the field of view. The control's 30 aborts
there were the right ALARM with the wrong WORD, arrived at through a
refusal that had nothing to do with the ridge, and they are gone.

The trade, stated as a ledger: **60 correctly named aborts gained, 30
wrongly named aborts lost.**

## What changed, in four parts

No threshold in `m8_core` moved. `ABSENT_VALID_FRAC`,
`ROTATED_ABS_RAD`, `STRINGER_NEAR_M`, `STRINGER_NEAR_FRAC`,
`SHIFTED_LATERAL_M`, `FACE_INLIER_FRAC_MIN`, `PALLET_FACE_WIDTH_M`,
`PALLET_FACE_HEIGHT_M`, `POCKET_SPAN_M`, `POCKET_WIDTH_M`,
`DOCK_ENVELOPE_M`, `TAG_WINDOW_M`, `FORK_BAND_M`, `OBJECT_CLEARANCE_M`,
`MIN_BLOB_CELLS`, `FACE_SEED_BAND_M` and `DECK_CUT_M` are all unchanged
from `92422ea`.

**3. The occluder-aware share.** The share gate asks whether the fitted
face is a large share of what COULD HAVE BEEN the face. A point
standing nearer than the seeded surface was never a candidate for being
part of it, so it neither judges it nor may be trimmed into it.
Measured on the rendered close poses with the tines reaching at the
pallet: at 1.0 m the face holds the seed mode — 109 points in its
0.02 m bin — while the tines spread 635 points as a ramp across every
bin in front of it, so the face reads 25 % of the blob and the gate
refuses `face_is_too_small_a_share`. With the occluder out of the
denominator the face holds 95 % and is segmented.

The rule is `FACE_SEED_BAND_M`, which already defines what the seeded
surface is, so no number was added. An occluder INSIDE that band is not
reached: open item 2's box stands 0.06 m in front of a face with a
0.06 m band, and it stays open, with a test that says so.

**3b. The forks are never unknown — `selfmask.tine_footprint`.** A
caller with no `mast_joint` reading still runs on a truck whose tines
are bolted where they are. `TINE_LATERAL_M` is where they are across
the truck and `TINE_REACH_M` is how far they stick out; only the TOP
rides the mast. The footprint is those two columns at ANY height, it
needs no reading, and it is therefore never stale. `classify` uses it
when the caller supplies nothing.

It is strictly worse than the joint-derived mask and it says so: it
takes the column whole, pockets included. So the one word it costs is
withheld by name — once the face is inside the tines' own reach, the
pocket runs went with the mask and `pocket_blocked` is not claimed.

Closer than about 0.90 m the occluder rule runs out on its own: the
tines are no longer in front of the pallet but INSIDE it, and the part
near the tip sits at the face's own distance, inside the seed band.
Lateral is the only thing that still separates them, which is exactly
what the footprint is.

**"UNWIRED" NOW MEANS something slightly different, and it is said
here rather than buried.** It is the classifier with no joint reading
and no tag. It is not a classifier that has never heard of a fork.

**3c. A deck-cut height is a lower bound, like a clipped one.** The
deck cut drops the top of every standing blob by construction, so a
face height measured after one is always short of the face. Rendered at
0.80 m with the tines in view, a 0.144 m pallet face reads **0.0498 m**
against `PALLET_FACE_HEIGHT_M[0] = 0.05`. "Too short through a deck
cut" is not evidence of an empty bay; "too tall" still is, which is the
asymmetry the clipping rule already turns on.

**4. The fork corridor.** `corridor_obstruction` asks whether a
standing object OTHER than the pallet is in the path in front of the
face, within the face's own lateral span and in the fork band. It adds
no standing test of its own: `seg.blobs` is every candidate
`_blob_candidates` found, `seg.blob` is the one the face came from, and
this only asks where the others are. The truck's own forks are excluded
by whatever fork knowledge the caller has, which is why the corridor
refuses to run with none.

## THE CORRIDOR'S FIRST VERSION WAS WRONG AND THE PLANT IS WHAT SAID SO

`e3-20260918-122007` is kept for this. The first `corridor_obstruction`
scanned pixels itself and decided "standing" by HEIGHT above the floor
plane instead of by the depth STEP along the ray that
`_blob_candidates` uses.

It was green everywhere that was not a moving truck:

| | first version |
|---|---|
| offline, clean frames, 5 seeds x 3 poses | 0 to 4 scattered cells |
| plant STATIC grid, `clean` | 1 to 4 cells |
| plant STATIC grid, staged ridge | 131 to 147 cells |
| **plant LIVE dock, clean frames** | **6 to 73 cells, growing as the truck braked in** |

A floor plane fitted to a floor the camera is pitching over stops being
the floor, and a height band above it then fills with contiguous floor.
It cost **13 false aborts of 74 countable frames** and drove unwired
live false-abort to **0.216** — worse than the 0.184 it was meant to
fix.

Over the same frames the depth step did not move: blob candidates
stayed at **2 to 6 per frame live**, the same 2 to 4 the static clean
captures read. That is why the corridor now asks the blob candidates
and nothing else.

**The bar of `MIN_BLOB_CELLS` was never the problem and was not
touched.** The measurement changed; the threshold did not.

## Offline — `words-20260918-120852`, 29 cases x 5 seeds

Rendered depth (`m8_core.scene`), no plant, no ROS. Necessary, never
sufficient — and this run is the clearest case of it yet: the offline
suite was green on a corridor the plant then broke.

| | 2026-09-12 | this branch |
|---|---|---|
| false aborts on frames expected clean | 0 of 40 | **0 of 55** |
| reason-exact | 85 of 110 | 125 of 145 |
| reason-exact, joint mask | 85 of 110 | 113 of 145 |
| frames the segmentation resolved | 70 | 89 (98 masked) |
| every frame with a STALE mask | `none` 110/110 | `none` **145/145** |

The close band the live cycles actually run in is now rendered —
`forks` and `forks_empty` at 0.9, 0.8 and 0.711 m. `forks` reads `none`
5/5 at every one of them and `forks_empty` reads `pallet_absent` 5/5 at
every one of them: **the silence is not bought with the empty bay**,
and the discriminator is physical rather than fitted. With the bay
empty the tines are the nearest thing in the frame, nothing stands in
front of the seed, and the denominator is the one the gate always had.

No word on any of the previous 110 frames regressed. Two moved:
`ridge@1.500` from `none` to `stringer_in_path`, and
`blocked_by_box@2.245` from `pallet_absent` to `stringer_in_path` — not
reason-exact, but a fault word on a staged fault rather than a claim
that a full bay is empty.

**The renderer cannot hold the 1.5 m ridge pose.** Its ridge is an
exact box whose depth step into the floor behind it lands on
`OBJECT_CLEARANCE_M`, so offline `_blob_candidates` finds ONE standing
object there. The plant resolves the same staged ridge at the same pose
— 6 candidates against a clean frame's 3, over 30 frames — and the
offline test names which of the two is being trusted.

## THE PLANT COULD NOT BE BROUGHT UP ON THIS BASE AT ALL

`m5v3.sh start` refused at `the map on disk is the map the registration
was fitted to`. Commit `9c52aa6` ("pre-commit hygiene — trailing
whitespace and final newlines") ran `end-of-file-fixer` across the tree
and added the missing final newline to
`m5_ver3/maps/warehouse_v3/warehouse_v3.yaml`, **136 bytes to 137**,
which changed its md5 from `a3c76218755a9ffe97c0d9f71fb1b19e` to
`1a35bb792067e2deafcca97713b3980f` while `registration.yaml` still
names the first. Pure formatting is not pure when the bytes ARE the
artifact.

The bytes are restored and `m5_ver3/maps/**` is marked `-text` in
`.gitattributes` so no text hook sees them again. **Nothing was
re-derived**: the .pgm is untouched and still hashes `735cdbc6`, which
is the label every localisation figure on this rig carries.

Two more findings from the same commit, neither acted on here:

1. It also rewrote three committed E1 evidence `summary.txt` files
   (`e1-20260911-125543`, `e1-20260912-000119`, `e1-20260912-000726`),
   whose md5s are quoted in `EVIDENCE_M8_E1.md`. Those are baselines
   and this branch does not touch them.
2. `registration.yaml`'s `world_md5` names `9157227a` for
   `m6/gazebo/warehouse_ver3.sdf`, which currently hashes `f3724586`.
   That drift is older than this branch — it is identical at `35ed6aa`,
   where the 2026-09-12 runs succeeded — and it is not gated at
   bringup. Recorded, not touched.

## Named lost coverage

1. **`stringer_in_path` at the 1.0 m pose: 30/30 aborts to 0/30.** The
   control's 30 were `pallet_absent` — the right alarm with the wrong
   word — and the ridge is under the field of view at that pose. 60
   correctly named aborts gained against 30 wrongly named lost.
2. **`pocket_blocked` is not claimed inside the tines' reach when the
   only fork knowledge is the footprint**, because the footprint
   deletes the pocket columns whole. Beyond that reach the word stands,
   which keeps it at every pose the fault is staged at.
3. **"Too short" is no longer evidence of an empty bay** when the
   reading came through a deck cut. "Too tall", "too wide" and "this is
   a floor" all still are.
4. **`pocket_blocked` exact is 7 of 90**, essentially unchanged, and
   open item 2 is still open by design.
5. **Domain gap.** gz depth is not a real D455. Inherited, unchanged.

## Open, by name

1. **The unwired bar is not met: 0.143 against < 0.10.** All 20 are
   inside 1.2 m and all 20 are named above.
2. **The too-narrow candidate inside 0.94 m is not identified.** About
   a metre tall, about 0.55 m wide, 0.6 to 0.9 m out; the truck's own
   mast and carriage are ruled out by geometry. Needs a rig-side frame
   dump, which R3 keeps out of this bench.
3. **`pallet_rotated` is a RELATIVE angle.** A truck still turning into
   the pallet reads as a rotated pallet, measured here walking to
   -0.223 rad on a dock the plugin finished clean with the pallet
   provably unmoved. Separating the two needs a vehicle pose that C2
   takes by design.
4. **The countable test checks the pallet's POSITION and not its
   yaw.** A pallet being pushed rotates before it translates 0.02 m.
5. **Wired, inside 0.9 m, a clean dock can read `pocket_blocked`** —
   offline `forks@0.900` and `forks@0.711`, 5/5 masked. New, offline
   only, not touched here.
6. **Open item 2 (`blocked_by_box` reads `pallet_absent`) is
   unchanged** and deliberately so: the fix named for it is a threshold
   move.
7. **The 0.0325 m tag residual** is unexplained, unchanged.
8. **`pallet_shifted` 0.30 m is still not caught**, unchanged.
9. **THE RIG DROPPED `gz set_pose` AGAIN**, once in six runs today
   (`e3-20260918-124330`, refused at "gz set_pose reseated the pallet",
   `no data: true`, with every process alive). A plant stop,
   `wsl --shutdown` and a cold start cleared it, as before. Still not
   diagnosed. Open item 5 of `EVIDENCE_M8_E3_WORDS.md` stands.
10. **E4 and E5 remain NOT_RUN.**
11. **Phase B stays on HOLD.** 0.093 wired on 140 frames of four docks
    is not a number a gate opens on, and this file does not ask for
    one.

## Environment

Same rig and same labels as every baseline: `traction=nominal`
`arm=wheel+imu` `loc=amcl@735cdbc6` `nav=on@7f57e6cf` `dock=on@1676eac0`
`docking=on@a462315f` `monitor=off` `partition=m5v3`, CameraInfo
fx = fy = 337.357 on 640x480. Bringups `run-20260918-121042` (sessions
121233, 122007), `run-20260918-122358` (122540, 122922, 123209) and
`run-20260918-124603` (124737), GPU `D3D12 (NVIDIA GeForce RTX 4050
Laptop GPU)`, Gazebo Sim 8.11.0, ROS 2 Jazzy.

`classify` median 0.074 s, max 0.119 s over 203 live frames (control
0.080 / 0.135 over 901). The as-wired pass is a second classification
of the same buffer and is timed separately; neither is an RTF claim,
which is E5's and still NOT_RUN.

Suite: **212 passed**, `python -m pytest m8/tests`, on a machine that
has never sourced ROS (187 at `92422ea`).

Rig conditions for the next run, unchanged and re-confirmed today: LF
working tree, a COLD `wsl --shutdown` before bringup,
`GZ_PARTITION=m5v3 ROS_DOMAIN_ID=97`, Jazzy sourced,
`python3 m8/bench/plant.py probe` as the smoke test, and the static
grid and the live cycles as two separate invocations — `--cycles 0`
then `--ranges ""`.

## Files

Every result file of every session above, control runs included.

| file | md5 |
|---|---|
| `e3-20260918-121233/cycles.csv` (0 rows) | `6ee1ae42ad885d888e3cac1f1e8f1a08` |
| `e3-20260918-121233/frames.csv` (540 rows) | `1c0da6db0a3f0ad499d53137a79ab078` |
| `e3-20260918-121233/session.json` | `9bac0aef3f07fb7f2aa9696f6ff0f7b0` |
| `e3-20260918-121233/summary.json` | `1444527d1def99e513ff3f1160de6688` |
| `e3-20260918-121233/summary.txt` | `17fd0d3f3b40a6c5d01dc5a62c7bc6cb` |
| `e3-20260918-122007/cycles.csv` (131 rows) | `4758029aba606d2eab4c4e8884a8c712` |
| `e3-20260918-122007/frames.csv` (0 rows) | `fe5ccc534134bff21b897d983f0312a5` |
| `e3-20260918-122007/session.json` | `31bfc03233ae560becdb2cae2c9cdf60` |
| `e3-20260918-122007/summary.json` | `1b84b66ff87f6fb1f290ce63af552042` |
| `e3-20260918-122007/summary.txt` | `16dd24b5bef88ebb0f641fb88599cf59` |
| `e3-20260918-122540/cycles.csv` (417 rows) | `0b082f05d5678d3f6ebcfbcc61b597ea` |
| `e3-20260918-122540/frames.csv` (0 rows) | `fe5ccc534134bff21b897d983f0312a5` |
| `e3-20260918-122540/session.json` | `44c39024517613adfb549a0a8e48b278` |
| `e3-20260918-122540/summary.json` | `a4a17041a4f08474f881e67c60ed7bf5` |
| `e3-20260918-122540/summary.txt` | `3299d27c97ee134140eb6344ef043539` |
| `e3-20260918-122922/cycles.csv` (203 rows) | `17342396e12562662386ac2c6b56c98c` |
| `e3-20260918-122922/frames.csv` (0 rows) | `fe5ccc534134bff21b897d983f0312a5` |
| `e3-20260918-122922/session.json` | `04e2b7313934a889f5b87e7516ad1c1c` |
| `e3-20260918-122922/summary.json` | `263a551424129e5c05915b2e9cd20e17` |
| `e3-20260918-122922/summary.txt` | `c85af176a472c4d0a25091589d20adb2` |
| `e3-20260918-123209/cycles.csv` (901 rows) | `fea11cd900a22b0691f6c617ef7b2d9b` |
| `e3-20260918-123209/frames.csv` (0 rows) | `6e53dbc7671e7c0c02c588bee5e6d08d` |
| `e3-20260918-123209/session.json` | `b336b30a52cf5902c739a22befc30d82` |
| `e3-20260918-123209/summary.json` | `f7583edb7d1f0348a96b3da47b20288b` |
| `e3-20260918-123209/summary.txt` | `63ea6d75ccc78a55a01a5d12d28c0275` |
| `e3-20260918-124737/cycles.csv` (0 rows) | `2f12ba54ea3edd8c5586a57d9a7a9ead` |
| `e3-20260918-124737/frames.csv` (540 rows) | `ce09eb7a16c059f37845f3eb75e83b1a` |
| `e3-20260918-124737/session.json` | `b7d695f69b3700ac7e747579784246a1` |
| `e3-20260918-124737/summary.json` | `676bf60bf8a3f4852dfb0360e8ca9162` |
| `e3-20260918-124737/summary.txt` | `b4be91a8bf667b8628a0725fdf21fecc` |
| `words-20260918-120852/frames.csv` (145 rows) | `71271357baba196315d022b7543882ba` |
| `words-20260918-120852/summary.json` | `24a7ff44e582b4a7e9ea40646152b665` |
| `words-20260918-120852/summary.txt` | `09dae3bb6724c2aff1129610054389d9` |
