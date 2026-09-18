# EVIDENCE_M8_E3_FLOOR — the floor is the farthest surface, not the biggest

Status: **RUN 2026-09-18 on the m5-ver3 plant, this rig.** Branch
`m8/c2-steps-3-4-unwired` (PR #13), continued from `eed3ce2`. This file
is the second half of that PR: `EVIDENCE_M8_E3_STEPS34.md` left the
unwired bar at **0.143 against < 0.10** with the cause of the close-band
aborts named but the object unidentified. It is identified here, and
the bar is met.

**BOTH BARS ARE NOW MET.** Paired against the classifier at `92422ea`
on the same bringup:

| | control `92422ea` | this branch | bar |
|---|---|---|---|
| **unwired false-abort** | 36/113 = **0.319** | 8/132 = **0.061** | **MET** |
| **wired false-abort** | 14/113 = **0.124** | 13/132 = **0.098** | **MET** |

A second, independent session of this branch on a different bringup
read **unwired 5/123 = 0.041, wired 9/123 = 0.073**.

**The wired margin is thin and this file will not dress it up.** 13 of
132 is 0.0985; one more abort would be 0.106 and would fail. The
unwired margin is real (0.041 and 0.061 across two sessions); the wired
one is not, and the wired-only aborts are named below.

| session | what it is |
|---|---|
| `e3-20260918-141014` | plant static, close band 1.0/0.9/0.8/0.7 m, **before** the floor fix. The diagnostic. |
| `e3-20260918-142146` | the same grid **after** it, same bringup. |
| `e3-20260918-143231` | plant static, the standard staging/1.5/1.0 grid, after. |
| `e3-20260918-144016` | plant live, 4 cycles, after. First of two. |
| `e3-20260918-144640` | plant live, 4 cycles, after. Second, and the one paired below. |
| `e3-20260918-145122` | **CONTROL**: live, 4 cycles, classifier at `92422ea`, same bringup as 144640. |
| `words-20260918-145637` | offline, 29 cases x 5 seeds. Not a plant result. |

**No baseline was overwritten and no existing result folder was
touched.** Every session named in `EVIDENCE_M8_E3.md`,
`EVIDENCE_M8_E1.md`, `EVIDENCE_M8_C1C2_FIX.md`,
`EVIDENCE_M8_E3_WORDS.md` and `EVIDENCE_M8_E3_STEPS34.md` is intact.

## Standing cautions

Ground truth is a score, not a command. No PL / SIL / PFH claims. The
Nav2 collision monitor is not a safety function. The F-PLC never
receives M8 input (R4). Frames never leave the truck (R3). `proceed` is
never an M8 output and is not counted anywhere below — where this file
says a frame reads `none`, the shadow node publishes NOTHING.

**PHASE B (abort live) STAYS ON HOLD.** Nothing here asks for it.

## THE DIAGNOSIS, AND THE COLUMN THAT HAD NEVER BEEN WRITTEN DOWN

`EVIDENCE_M8_E3_STEPS34.md` left this open: *"It is a standing object
about a metre tall and about 0.55 m wide, 0.6 to 0.9 m from the camera
... naming it needs a frame dump."* It did not. It needed three numbers
`segment` has traced since it was written and no bench had ever logged:
`floor_dz_dy`, `floor_depth_on_axis_m`, `floor_points`.

With them logged, `e3-20260918-141014` — a static grid extended to the
close band the live docks actually run in, `clean` against
`pallet_absent` at the same four teleported poses:

| pose | `clean` dz/dy | empty bay dz/dy | `clean` axis depth | empty bay |
|---|---|---|---|---|
| 1.00 m | −3.723 | −3.797 | 2.180 m | 2.195 m |
| 0.90 m | −3.553 | −3.790 | 2.146 m | 2.194 m |
| 0.80 m | **−2.599** | −3.789 | **1.942 m** | 2.194 m |
| 0.70 m | **−2.334** | −3.783 | **1.860 m** | 2.193 m |

`pocket.py` states this rig's floor reads about −3.8 and a standing
face +0.7…+1.5. **With the bay EMPTY the fit finds the floor at every
pose. With a pallet in it, from 0.90 m in, it does not.** The pallet's
own deck top — 0.8 m deep, 1.2 m wide, and a growing share of the image
as the truck closes — drags the majority fit up onto itself, 0.25 m
short on the optical axis by the 0.80 m pose.

**EVERY HEIGHT IN `m8_core` IS A RESIDUAL AGAINST THAT PLANE.** The
deck cut, the fork band, the blob's own "stands above the floor" test,
the self-mask's placement. A plane that is not the floor mismeasures
all of them at once, and nothing downstream can tell. On that grid
`clean` false aborts were **28 of 80**, all of them at 0.80 and 0.70 m.

### And the mystery object was the empty bay all along

The candidate that beat the pallet refused `face_width_not_pallet_sized`
at 0.548 m with its deck cut at 0.862 m, from a blob at
(164, 296, 56, 180). The `pallet_absent` condition — the bay with the
pallet teleported out — shows **the same candidate at every pose**:
0.549–0.562 m wide, deck cut 0.998–1.002 m, blob (156–180, 292–300, 56,
168–184).

It is the bay's own back structure, which is there whether or not the
pallet is, and which is exactly what SHOULD make an empty bay read
`pallet_absent`. With a mismeasured floor it out-ranks the pallet
standing in front of it. It was never a mystery object; it was the
right object winning for the wrong reason.

## The fix

`dominant_plane`'s docstring said "the plane most of the frame lies on.
On the plant that is the floor." The measurement above is where that
stops being true.

**THE FLOOR IS WHAT EVERYTHING ELSE STANDS ON.** It is opaque and the
world rests on top of it, so along any ray there is nothing behind it:
a plane with a surface BEHIND it is not the ground, it is something
standing on the ground. `dominant_plane` now fits the majority surface
as before, then steps back onto whatever lies deeper than it, and
chooses among the candidates the one with the least still under it —
ties going to the best-supported, so a good fit is never traded for a
far scrap.

**No new number.**

| what | which existing constant | why it is the right one |
|---|---|---|
| "behind" margin | `OBJECT_CLEARANCE_M` | already "nearer than the dominant plane by this much means it stands on it"; its mirror is a point the plane says is BELOW the ground |
| population bar | `MIN_PLANE_POINTS` | the solver's own minimum |
| step count | `DOMINANT_TRIM_PASSES` | the trim's own bound |
| where it is scored | `DOCK_ENVELOPE_M` | see below |

**The comparison happens inside the dock envelope and the fit does
not.** The fit is in INVERSE depth, so a residual read in metres grows
with range for a fixed error in the quantity actually fitted: at 6 m
the far floor sits "under" its own plane by more than
`OBJECT_CLEARANCE_M` on noise alone. Scored over the whole frame the
test rejected every correct floor and collapsed an 8009-point fit onto
a 40-point far sliver — measured offline before it ever reached the
rig. The PLANE still comes from the whole frame, because a floor is
fitted best over as much floor as there is.

## Static grid — close band, same bringup, before and after

20 frames x 6 conditions x 4 poses (1.00, 0.90, 0.80, 0.70 m).

| condition | `e3-20260918-141014` before | `e3-20260918-142146` after |
|---|---|---|
| `clean` | **28 / 80** false aborts | **0 / 80** |
| `pallet_absent` | 80/80 [80] | 80/80 [**80**] |
| `pallet_rotated` | 80/80 [**40**] | 80/80 [**80**] |
| `pallet_shifted` | 0/80 | 0/80 |
| `pocket_blocked` | 80/80 [0] | 80/80 [0] |
| `stringer_in_path` | 28/80 [0] | 0/80 [0] |

Refusals behind those words:

| | before | after |
|---|---|---|
| `(segmented)` | 179 | **340** |
| `face_width_not_pallet_sized` | 180 | 140 |
| `candidate_falls_away_like_a_floor` | 98 | **0** |
| `too_few_points_in_window` | 23 | **0** |

`clean` goes to zero **while the empty bay keeps every one of its 80
exact calls** — the silence is not bought with the bay. The staged
ridge is under the field of view at all four of these poses (see
`EVIDENCE_M8_E3_STEPS34.md`), which is why `stringer_in_path` is 0/80
on both sides.

## Static grid — the standard three poses

`e3-20260918-143231`, 30 frames x 6 conditions x 3 poses, cold rig.
Against `EVIDENCE_M8_E3_STEPS34.md`'s two columns:

| condition | control `92422ea` | steps 3+4 | **+ the floor** |
|---|---|---|---|
| `clean` | 0/90 | 0/90 | **0/90** |
| `pallet_absent` | 90/90 [90] | 90/90 [90] | 90/90 [90] |
| `pallet_rotated` | 90/90 [60] | 90/90 [89] | 90/90 [89] |
| `pallet_shifted` | 1/90 | 0/90 | 0/90 |
| `pocket_blocked` | 90/90 [6] | 90/90 [7] | 90/90 [**9**] |
| `stringer_in_path` | 30/90 [0] | 60/90 [60] | 60/90 [60] |
| frames resolved | 246 | 366 | **398** |

The control column is `e3-20260918-124737`, taken cold on an earlier
bringup the same afternoon; the other two are cold as well. Static
poses are teleports, which is why this table is comparable across
bringups and the live one is not.

30 of the `pocket_blocked` frames now read `stringer_in_path`: the
staged box IS a separate standing object in the fork path, so that is a
fault word on a staged fault rather than a claim the bay is empty. It
is still not reason-exact and open item 2 is still open.

## THE BAR — live cycles, paired on bringup `run-20260918-144513`

| | control `92422ea` (145122) | **this branch** (144640) |
|---|---|---|
| countable frames | 113 of 505 | 132 of 514 |
| **unwired false-abort** | 36 / 113 = **0.319** | 8 / 132 = **0.061** |
| **wired false-abort** | 14 / 113 = **0.124** | 13 / 132 = **0.098** |
| staging (>= 2.0 m) | 0 / 31 | 0 / 36 |
| approach (1.2-2.0 m) | 1 / 43 | **0 / 52** |
| close (< 1.2 m) | 35 / 39 = 0.897 | **8 / 44 = 0.182** |
| refusals behind the words | `(segmented)` 74, `face_width_not_pallet_sized` 20, `candidate_falls_away_like_a_floor` 14, `too_few_points_in_window` 5 | **`(segmented)` 132** |

**Every countable frame on this branch segments.** There is no refusal
left in the bar population at all — the 8 aborts are words said about a
face that was found, not words said because none was.

The second session, `e3-20260918-144016` on bringup
`run-20260918-143058`: **unwired 5/123 = 0.041, wired 9/123 = 0.073**,
bands 0/35 staging, 0/53 approach, 5/35 close.

## The eight, by name

From `e3-20260918-144640/cycles.csv`:

- **7 `pallet_rotated`, all in cycle 2, all one skewed approach.** The
  measured face yaw walks from −0.158 rad at 0.98 m to −0.350 at
  0.79 m. This is open item 3 of `EVIDENCE_M8_E3_STEPS34.md` unchanged:
  `face_yaw` is a RELATIVE angle and a truck still turning into the
  pallet reads as a rotated pallet. Cycles 0, 1 and 3 contributed
  **zero** unwired aborts between them.
- **1 `pocket_blocked`** at 1.046 m, face segmented at 1.175 m wide,
  truck yawed −0.132 rad — one pocket foreshortened away.

### The wired-only aborts, which are the thin margin

Wired adds five aborts the unwired path does not make: `pocket_blocked`
x5 and `stringer_in_path` x3, against `pallet_rotated -> none` x3 and
`pallet_rotated -> pallet_absent` x2. Every one of them has
`corridor_component` 0, so **none of them is the fork corridor**: they
come from the joint mask changing `find_pocket_pair` and
`fork_path_fraction`, which is behaviour this branch did not touch. The
unwired path withholds `pocket_blocked` inside the tines' reach by
design (`_pockets_were_masked_away`); the joint mask knows its own
height and is allowed the claim, and here it is wrong five times.

**That is the wired number's whole margin and it is not this branch's
gain to spend.** Named as open item 2.

## Offline — `words-20260918-145637`, 29 cases x 5 seeds

| | steps 3+4 | + the floor |
|---|---|---|
| false aborts on frames expected clean | 0 of 55 | **0 of 55** |
| reason-exact | 125 of 145 | 120 of 145 |
| reason-exact, joint mask | 113 of 145 | 108 of 145 |
| frames resolved | 89 (98 masked) | 89 (98 masked) |
| every frame with a STALE mask | `none` 145/145 | `none` **145/145** |

**Exactly one case moved and it is not the floor change.**
`ridge@1.500` went from `stringer_in_path` to `none`. That is the
corridor rewrite already recorded in `EVIDENCE_M8_E3_STEPS34.md` and
held by `test_the_renderer_does_not_resolve_the_ridge_at_1_5_m`: the
renderer's ridge is an exact box whose depth step into the floor behind
it lands on `OBJECT_CLEARANCE_M`, so offline `_blob_candidates` finds
ONE standing object at that pose. The `words-20260918-120852` run
predates the rewrite. **The plant resolves the same staged ridge at the
same pose and aborts on it 30/30** (`e3-20260918-143231`).

**THE RENDERER DOES NOT REPRODUCE THE FLOOR DRIFT AT ALL** — it reads
−3.79 at 1.0, 0.9, 0.8 and 0.7 m, where the plant read −3.72 to −2.33.
So the tests added for this change pin the INVARIANT and not the
regime: the plane a full bay fits is the plane an empty one fits, and a
bigger nearer surface does not become the floor. Offline agreement here
is necessary and is not close to sufficient.

Adding a back wall to the renderer DOES break its floor fit (dz/dy
−0.27 to −0.96 at these poses, both before and after this change), but
a wall filling the upper frame is not this bay's back panel and the
fixture is not committed as a claim about the rig.

## Named lost coverage

1. **30 of 90 `pocket_blocked` frames now read `stringer_in_path`** on
   the standard grid. A fault word on a staged fault, not reason-exact.
2. Everything named in `EVIDENCE_M8_E3_STEPS34.md` stands: the 1.0 m
   `stringer_in_path` pose, the pocket claim inside the tines' reach,
   "too short" through a deck cut, open item 2.

## Open, by name

1. **`pallet_rotated` is a RELATIVE angle** and is now the whole of the
   unwired number: 7 of 8. A truck still turning into the pallet reads
   as a rotated pallet. Separating the two needs a vehicle pose that C2
   takes by design. **This is the next thing worth doing.**
2. **The wired margin is one frame wide.** 0.098 on the paired session,
   0.073 on the other. Five wired-only `pocket_blocked` and three
   wired-only `stringer_in_path` come from the joint mask, not from
   anything this branch added.
3. **The countable test checks the pallet's POSITION and not its yaw.**
4. **Open item 2 (`blocked_by_box` reads `pallet_absent`) unchanged**,
   the tag residual unchanged, `pallet_shifted` 0.30 m unchanged.
5. **THE RIG DROPPED gz SERVICES TWICE MORE TODAY** — `set_pose`
   (`e3-20260918-124330`) and `create` (`e3-20260918-144356`), both
   with every process alive, both cleared by a stop, `wsl --shutdown`
   and a cold start. Open item 5 of `EVIDENCE_M8_E3_WORDS.md` stands
   and is now four occurrences.
6. **E4 and E5 remain NOT_RUN.**
7. **Phase B stays on HOLD.** Two sessions of four docks are not a
   number a gate opens on, and this file does not ask for one.

## Environment

Same rig and same labels as every baseline: `traction=nominal`
`arm=wheel+imu` `loc=amcl@735cdbc6` `nav=on@7f57e6cf` `dock=on@1676eac0`
`docking=on@a462315f` `monitor=off` `partition=m5v3`, CameraInfo
fx = fy = 337.357 on 640x480. Bringups `run-20260918-140844` (sessions
141014, 142146), `run-20260918-143058` (143231, 144016) and
`run-20260918-144513` (144640, 145122), GPU `D3D12 (NVIDIA GeForce RTX
4050 Laptop GPU)`, Gazebo Sim 8.11.0, ROS 2 Jazzy.

`classify` median 0.109 s, max 0.237 s over 514 live frames on the
paired session (control 0.073 / 0.102 over 505); the extra cost is the
floor's step-back passes and it is not an RTF claim, which is E5's and
still NOT_RUN.

Suite: **220 passed**, `python -m pytest m8/tests`, on a machine that
has never sourced ROS (187 at `92422ea`, 212 at `eed3ce2`).

## Files

Every result file of every session above, the control included.

| file | md5 |
|---|---|
| `e3-20260918-141014/cycles.csv` (0 rows) | `4d1a6fe4e00a53d18c24192becab9dfc` |
| `e3-20260918-141014/frames.csv` (480 rows) | `9099fa5194fcce6530f615e95831fd3b` |
| `e3-20260918-141014/session.json` | `17d7e59c58ecec519aa98b7544b9baed` |
| `e3-20260918-141014/summary.json` | `1f2be575ec97095a7c7b7313b321bec9` |
| `e3-20260918-141014/summary.txt` | `e9d6fe52483ae5c9b7010f8074b3f3b4` |
| `e3-20260918-142146/cycles.csv` (0 rows) | `4d1a6fe4e00a53d18c24192becab9dfc` |
| `e3-20260918-142146/frames.csv` (480 rows) | `a57f697b09a634928fb33a1d29acc7a8` |
| `e3-20260918-142146/session.json` | `b0a1b12acc826c75dd219c282895df7e` |
| `e3-20260918-142146/summary.json` | `298b6687d7d0f9f767ac4a93ebcab463` |
| `e3-20260918-142146/summary.txt` | `3c451a1f044f5b779088363b3114e65a` |
| `e3-20260918-143231/cycles.csv` (0 rows) | `4d1a6fe4e00a53d18c24192becab9dfc` |
| `e3-20260918-143231/frames.csv` (540 rows) | `b47245cc7500501aafc52dbbd68fea1f` |
| `e3-20260918-143231/session.json` | `16024c31233881253fd001a5c5434942` |
| `e3-20260918-143231/summary.json` | `d71cfe4b0f5a18543741614e50b50ad8` |
| `e3-20260918-143231/summary.txt` | `288092d35953547479ee7c4316857537` |
| `e3-20260918-144016/cycles.csv` (211 rows) | `0a56cee226ee8dc8171656789c3d8030` |
| `e3-20260918-144016/frames.csv` (0 rows) | `8dca7545196fa483c0cf1dc98ffd5bae` |
| `e3-20260918-144016/session.json` | `352da8d31a2abe250c231b2d2a4557e8` |
| `e3-20260918-144016/summary.json` | `a88cf8b012895972f8f92650e0b78219` |
| `e3-20260918-144016/summary.txt` | `499ed959fc4cdd55adb6bd9712c6b5ee` |
| `e3-20260918-144640/cycles.csv` (514 rows) | `0a66400c5794aafb18bbf1373a8afeef` |
| `e3-20260918-144640/frames.csv` (0 rows) | `8dca7545196fa483c0cf1dc98ffd5bae` |
| `e3-20260918-144640/session.json` | `009032971a7731d49634211774f0cef0` |
| `e3-20260918-144640/summary.json` | `bb91a2ac963556eb218b4e4812e611b0` |
| `e3-20260918-144640/summary.txt` | `777b13bd5afbdc403d895c2d67038a99` |
| `e3-20260918-145122/cycles.csv` (505 rows) | `acff921a44624013fa1a713794c16d49` |
| `e3-20260918-145122/frames.csv` (0 rows) | `6e53dbc7671e7c0c02c588bee5e6d08d` |
| `e3-20260918-145122/session.json` | `0524a6132ad42aaccbf667bc6131b89f` |
| `e3-20260918-145122/summary.json` | `62f28f758d3d5c74ad15592081d7954f` |
| `e3-20260918-145122/summary.txt` | `0f15e56accb032f594f051dd8d680dbc` |
| `words-20260918-145637/frames.csv` (145 rows) | `455892d747180bc19a5e572e5465736e` |
| `words-20260918-145637/summary.json` | `a9887957ba17269366d349b52073b739` |
| `words-20260918-145637/summary.txt` | `aeca93209b8a990f838079ca14fa33b8` |
