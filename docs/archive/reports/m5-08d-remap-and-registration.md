# Report m5-08d — rebuild the map, register it to the world, score absolutely

```
brief:               docs/briefs/m5-08d-remap-and-registration.md
status:              done
files_changed:       sim/maps/warehouse/register_map.py
                     sim/maps/warehouse/warehouse_registration.yaml   (new)
                     sim/maps/warehouse/warehouse.pgm                 (rebuilt)
                     sim/maps/warehouse/warehouse.yaml                (rebuilt)
                     sim/maps/warehouse/warehouse.posegraph           (rebuilt)
                     sim/maps/warehouse/warehouse.data                (rebuilt)
                     sim/scenarios/tools/mapping_evidence.py
                     sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md
                     sim/worlds/evidence/m5-08d-run.csv               (new)
                     sim/worlds/evidence/m5-08d-legs.csv              (new)
                     sim/README.md
                     docs/reports/m5-08d-remap-and-registration.md
                     (sim/launch/warehouse_bringup.launch.py verified,
                      NOT edited — the cbbb680 version is correct)
invariants_touched:  none. Invariant 10 shaped the result: T(world -> map)
                     has exactly one owner and one file, it is derived
                     rather than asserted, and consumers reach it through
                     the module that derived it rather than parsing a copy
open_questions:      seven, in §9. The load-bearing ones: the rebuilt map
                     is 0.45 deg off the building rather than square; the
                     registration residual of 0.141 m is a hard floor under
                     any AMCL number; and the IMU gate leaks 0.24-0.61
                     deg/min during a long idle AFTER a drive, a case
                     m5-07d did not test (a request to agv/, not a change)
next_suggested:      the AMCL brief, written against --score absolute, with
                     the 0.141 m floor in its criterion and a named
                     dwell-and-reverse case inside one degenerate stretch
```

---

## 1. The robust-fit verdict — worse than "never called"

**Confirmed, and then some.** At `cbbb680`, `fit_line_robust` was defined at
`register_map.py:304` and called from nowhere; `cmd_derive` fitted each wall
with the raw `fit_line` and then solved the transform over the raw,
untrimmed point sets. The trimming rule existed only as a docstring.

Run as committed, on the committed grid
(`derive_oldmap_untrimmed.txt`, reproducible with the file at `cbbb680`):

| wall | points | fit rms | own rotation |
|---|---|---|---|
| west | 297 | 0.035 m | **+1.7693°** |
| south | 400 | 0.161 m | **+1.4325°** |
| north | 435 | **0.304 m** | **−1.3214°** |
| east | 400 | 0.016 m | **+1.8146°** |

theta **+0.8178°**, residual rms **0.3031 m**, residual **max 0.8006 m**,
"shear" **3.1361°**. The north wall's rotation comes out with the *opposite
sign* to the other three. That reproduces the `cbbb680` commit message's
0.30 m rms exactly.

**But wiring the function in as written would have been worse than leaving
it out**, and this is the finding that mattered. `fit_line_robust` seeded its
trim with a least-squares fit. Least squares is dragged towards the
contaminating surface, and the trim then converges onto *that* surface and
reports a tight fit to it. Measured on the same north wall, LS-seeded, at
four tolerances (`probe_trim_oldmap.txt`):

| trim tolerance | LS-seeded angle | LS-seeded rms | kept |
|---|---|---|---|
| 2 cells | **−1.6099°** | 0.0295 m | 69 |
| 3 cells | **−1.7995°** | 0.0500 m | 110 |
| 4 cells | **−1.4284°** | 0.0974 m | 155 |
| 6 cells | **−1.3204°** | 0.1231 m | 230 |

An rms of **0.0295 m** — twelve times better than the untrimmed 0.304 m —
against a line whose angle has the wrong sign. It is a tight fit to rack row
A. A small residual against the wrong surface is the worst failure available
in this tool, because it looks like success and would have been quoted as
one. The unused function was not an unfinished feature; it was a trap.

## 2. The bringup, captured

The `cbbb680` launch edit was **verified, not trusted**. It is correct: it
adds `imu_gate.py` as a fourth estimator process, ties it to the `estimator`
argument so the four start together or not at all, and passes
`use_sim_time:=true`. Both `imu_gate.py` and `wheel_odometry.py` use
`parse_known_args`, so the `--config ... --ros-args -p use_sim_time:=true`
invocation the launch builds is valid — checked in the scripts, then
observed running.

The IMU **bridge** was already present in the M4 bringup this file extends;
it needed nothing added. What was missing was the gate, and that is what the
edit supplied.

Brought up headless, `GZ_PARTITION=m508d_map`, `ROS_DOMAIN_ID=71`, both
transports isolated:

```
$ ros2 node list
/forklift_arena_bridge      /forklift_ekf      /imu_gate
/sensor_tf                  /wheel_odometry    /transform_listener_impl_...
```

`mapping_evidence.py publishers --seconds 12` — **this is done_when (a)**:

```
/tf
  Publisher count: 1
    Node name: forklift_ekf   Node namespace: /   Topic type: tf2_msgs/msg/TFMessage
  Edges observed over 12 s, parent -> child : messages
    forklift/odom -> forklift/base_link : 470
/tf_static
  Publisher count: 1
    Node name: sensor_tf
VERDICT: 1 publisher(s) on /tf: forklift_ekf
```

One publisher, one dynamic edge, and the ground-truth TF bridge absent —
it has no argument in this file and no process appeared for it.

**The gate is live, not merely started.** Parked, `/forklift/imu` runs at
100.038 Hz and `/forklift/imu_gated` publishes *nothing at all*
(`ros2 topic hz` never leaves "does not appear to be published yet");
`/forklift/wheel_standstill` is `true` at 50.012 Hz. Across a 60 s idle in
this bringup the fused orientation is **bit-identical**:

```
t0      04:52:43Z   z: 0.0005849960834777662   w: 0.9999998288897766
t0+60   04:53:45Z   z: 0.0005849960834777662   w: 0.9999998288897766
```

That residual z is a yaw of 0.067°, and it is the 0.50 s of ungated gyro
the gate costs at every stop by design (m5-07d open question 3: 0.13 °/s ×
0.5 s = 0.065°). It is acquired once at bringup and then frozen. The
m5-08b map's 2.0° came from ~20 s of idle at that rate; this stack's idle
now costs 0.067° no matter how long it is.

## 3. The rebuilt map and its squareness

Same route, unchanged — `warehouse_mapping_route.py` was not edited. Same
seed discipline as m5-08b: **no `--seed`**, so the gyro bias sign is drawn
fresh, exactly as it was for the map being replaced. Route completed in
**178.9 s of simulation time over 9 legs** against m5-08b's 179 s: the same
drive.

Squareness measured independently of the run, by fitting the walls of the
committed grid with the tool of §4 — no run figure enters it:

| | m5-08b grid | **rebuilt grid** |
|---|---|---|
| rotation from the building | +1.8343° | **−0.4535°** |
| internal shear (spread of the four wall angles) | 0.4244° | **0.3250°** |
| west / south / north / east wall angle | +1.81 / +2.11 / +1.69 / +1.81° | **−0.58 / −0.26 / −0.55 / −0.46°** |
| grid | 614 × 421 | 606 × 410 |
| md5 | `8c48cc4e…` | `a6631630…` |

**The rebuild is 4.0× squarer and it is not square.** 1.83° → 0.45°. The
judge's ~2.0° is gone and the sign flipped, which is the fresh bias draw.
Reporting the number rather than the hoped-for zero: **the map is 0.45° off
the building**, and over the 30 m hall that is 0.24 m of position error at
the far wall for anything that assumes otherwise. It is registered, so
nothing downstream needs to assume otherwise — but it is not zero and this
report does not round it there.

Where the 0.45° comes from, as far as this run establishes it: **not from
the idle.** §2 measured the idle contribution in this bringup at 0.067° and
showed it frozen, so at most 15 % of the 0.45° can be pre-drive. The rest is
heading error accumulated *while driving* — m5-07d measured −12.88° of it
over this route and explicitly declined to correct it — most of which the
pose graph absorbs through loop closure, leaving this residual. That is a
statement about what the mapping does with in-motion drift, and this run
does not decompose it further.

**The shear barely moved: 0.42° → 0.33°.** It survived a fix that removed
three quarters of the rotation, so the shear is not caused by idle drift.
It is a property of the mapping — a grid built by a scan matcher is not
exactly rigid — and it is what a rigid transform cannot absorb, so it is
what the residual in §5 mostly is. Per the brief, this is a finding about
the mapping, not a failure of the rebuild, and no slam_toolbox parameter was
touched to chase it.

## 4. The trimming rule, stated

> **A wall is a line.** Take the extreme occupied cell of every grid row
> (east/west) or column (north/south) with no pre-filter at all. Seed the
> line with a **repeated-median fit** — Siegel's estimator, 50 % breakdown.
> Drop every extreme further than `--trim-cells` (default **3 cells =
> 0.15 m**) from the current line, refit by least squares, repeat to
> convergence. Solve the transform over the **kept** points only. One rule,
> one tolerance, one seed, applied to all four walls identically; no wall is
> special-cased and no point is removed by hand. A wall whose survivors fall
> under `--min-points` (default 100) is **refused**, not fitted.

Three things this replaces, each for a measured reason.

**The seed is a repeated median, not least squares.** §1 is the measurement.
50 % breakdown is the property being bought: the seed returns the line the
majority of extremes lie on even when 44 % of them lie on a different
surface, which is the north wall's actual contamination rate (272 of 614).

**The `--band` pre-filter is deleted, not widened.** It kept extremes within
±0.60 m of the *median* extreme — an axis-aligned band. These walls are
rotated ~1.8° from the grid axes, so across the 30 m hall the wall itself
moves 1.05 m, more than the band's full width. It was clipping genuine wall,
and clipping it at the two **ends**, which are the points that determine the
angle best. Measured (`probe_band.txt`): the band cost 82 of 343 real
north-wall points and 42 of 404 south-wall points. Widening it is not
available — a band wide enough to hold a tilted wall is wide enough to hold
the racking standing in front of it. With the band removed the results are
byte-identical to running it at 1.5 m and at infinity: the trimming rule is
now doing all of the selection, and nothing else is.

**The tolerance is chosen against two measured quantities, not tuned.** It
must sit above the wall's own scatter (~0.02 m rms), so a converged fit is
not cut off by its own threshold, and below the standoff of the nearest
non-wall surface (rack row A stands 0.35–0.55 m off the north wall). That
window is 2–6 cells, and **across the whole window the fitted angle moves by
less than 0.01°**. The default sits in the middle of it. The tolerance is
therefore not load-bearing; the seed is, and the file says so.

### The rule validated against an independent measurement

Re-run on the **same old grid**, changing only the fitting:

| | as committed at `cbbb680` | with the trimming rule |
|---|---|---|
| north wall rotation | −1.3214° | **+1.6885°** |
| north wall fit rms | 0.304 m | **0.0237 m** |
| apparent shear | 3.1361° | **0.4244°** |
| theta(world→map) | +0.8178° | **+1.8343°** |
| residual rms | 0.3031 m | **0.0439 m** |
| residual max | 0.8006 m | **0.1584 m** |

The two right-hand figures in bold are the check. `m5-08c` measured this
artifact independently — different code, different method, written before
this tool existed — and reported the grid rotated **≈ 2.0°** from the
building with **~0.4°** of internal shear. The trimmed fit returns **1.83°**
and **0.42°**. The untrimmed fit returned 0.82° and 3.14°, which agrees with
nothing. The rule is not merely self-consistent; it recovers a number
somebody else measured.

## 5. T(world → map) with its residual

Committed at `sim/maps/warehouse/warehouse_registration.yaml`, derived by
`sim/maps/warehouse/register_map.py derive --write` from the committed grid
and the committed world file. Nothing in it is asserted and no figure from
any run enters the calculation.

```
p_map = R(theta) * p_world + t

theta = -0.007915259 rad = -0.453510947 deg
t     = (+6.029222691, +5.541459743) m

residual rms  0.040363 m   over 1444 wall points
residual MAX  0.141100 m   <- THE FLOOR
shear          0.325049 deg
```

bound to `warehouse.pgm` md5 `a663163036c5890937f9045bcf559e72`,
`warehouse.sdf` md5 `c3bd8f810a72a3d4846d8a202f077e3e`, derived
2026-08-04T05:00:23Z, `trim_cells: 3.0`.

**The residual is 0.141 m and it is the floor.** No rigid transform fits
this grid to this building better than that, because the grid is 0.33°
internally sheared and a rigid transform cannot absorb shear. Stated
plainly, out loud, as the brief asks: **any AMCL error smaller than 0.141 m
measured through this transform is not a measurement of AMCL.** The rms,
0.040 m, is the more representative figure for an error averaged over a
whole circuit; the max is the bound for any single pose, and the max is
what the file leads with.

**It must be re-derived for every regenerated map.** This is enforced rather
than requested. The registration records the md5 of the grid it came from
and `load_registration()` refuses a mismatch — tested by hand-editing the
md5 in a copy placed beside the real grid:

```
REGISTRATION IS STALE. ... was derived from a grid with md5
  8c48cc4e9d1771558eb3c648d9c15df8
and .../warehouse.pgm now has md5
  a663163036c5890937f9045bcf559e72
A regenerated map has its own rotation from the building. Re-derive:
    python3 sim/maps/warehouse/register_map.py derive --write
```

The reason it must be re-derived is measured, not argued: this rebuild's
rotation is **−0.45°** where the previous grid's was **+1.83°** — different
magnitude *and* different sign, from the same route, the same world and the
same code, because the gyro bias sign is drawn per run. Any figure that
carried the old angle across the rebuild would have been wrong by 2.3°.

**A sanity check that is not part of the derivation.** slam_toolbox anchors
`map` at the vehicle's pose when it processed its first scan, which is the
spawn pose (−6.009, −5.500). Carrying that through this transform gives
(−0.023, +0.089) m — within 0.09 m of the map origin, which is where an
independent argument says it should land. The transform was not fitted to
that and agrees with it anyway.

**Re-runnable, no dependency.** Standard-library Python only; no numpy, no
yaml module, no ROS. `derive` prints and writes nothing; `--write` is the
deliberate act of committing a registration. `show` prints a committed one
and verifies it against its grid. Whole run takes 0.59 s.

## 6. Absolute scoring mode

`mapping_evidence.py analyse` gains `--score`, and **`--score` has no
default**. That is the mechanism, not an oversight: the two modes answer
different questions, differ by a factor of two here, and *neither output
would look wrong to a reader who had not chosen*. A better default would
have left the trap in place. The old command line now errors:

```
$ mapping_evidence.py analyse --csv run.csv
mapping_evidence.py analyse: error: the following arguments are required: --score
```

**`--score absolute`** carries `map -> base_link` into the world frame
through the committed registration — `p_world = R(−θ)(p_map − t)` — and
performs no per-run anchoring anywhere. It prints the transform it used,
confirms the grid md5, and prints the registration's residual as an
explicit **FLOOR** before any error figure. It refuses to run against a map
that has been rebuilt since the transform was derived; tested by appending
one byte to the grid, which produced `REGISTRATION IS STALE` and a non-zero
exit rather than a plausible wrong number.

**`--score anchored-drift`** is the old behaviour, kept and now named. Its
header says in the output itself that it is drift since the start of the
drive, that a constant offset or a wrong frame is invisible in it, and that
a localisation number comes from the other mode. Its frame-relation line no
longer reads as the map's orientation — it now says it is a single-sample
relation and points at `register_map.py` for the artifact's rotation, which
is the exact confusion that produced the −2.82°.

**Four differences beyond the transform**, each for a stated reason:

1. **Absolute keeps the parked samples; anchored drops them.** Anchored
   drops them because a first-sample anchor charges the route with heading
   error the route did not produce. Absolute has no anchor and nothing to
   protect, and a localiser's error while the vehicle stands still is a
   measurement — it is exactly the dwell case m5-08c finding 3 says the
   AMCL gate must contain. Absolute reports the two parked segments as
   their own labelled rows instead of discarding them.
2. **Absolute does not score the EKF at all**, and says so in the output.
   `forklift/odom` has no *derived* registration to the world; only `map`
   does. Scoring it absolutely would mean asserting a transform from the
   spawn pose, which is the thing this mode exists to prevent. Anchored
   mode still scores both.
3. **The stretch table gained a `seconds` column**, so a dwell is readable.
   `_passes` already splits correctly — a dwell keeps samples contiguous
   and stays one pass, leaving and re-entering starts a second — but
   without a duration a 60 s dwell and a 6 s traverse looked alike. Finding
   3 is now expressible in the committed instrument.
4. **A `nan` was fixed on the way.** The parked-segment EKF heading line
   differenced `ekf_yaw` at segment ends, and the EKF has not published for
   the first samples of a recording, so it printed `+nan deg` as if it were
   a measurement. It now picks the first and last samples that carry a
   heading.

### The two modes on one CSV — the difference, measured

The same 4150-sample recording of this run, read both ways:

| | `--score anchored-drift` | `--score absolute` |
|---|---|---|
| `map -> base_link` rms | 0.138 m | **0.077 m** |
| max | 0.290 m | **0.146 m** |
| final | 0.031 m | 0.082 m |
| samples scored | 1865 (drive only) | **4150 (all)** |

**The absolute figure is smaller, and the reverse was expected.** Said
plainly rather than smoothed over: the anchored mode pins the whole curve
onto one sample at the start of the drive, and yaw noise in that one sample
rotates everything after it (m5-08c finding 2 put that at ~0.11 m at this
route's lever arm). Absolute has no such sample.

**And the absolute max, 0.146 m, sits at the registration floor of
0.141 m.** So what this run establishes is that SLAM's own `map ->
base_link` tracked truth to within the instrument's resolution and *nothing
finer*. That is the floor doing its job on its first use, and it is a
warning to the AMCL brief: this instrument cannot resolve a localisation
error below ~0.14 m, so a gate criterion tighter than that is not
measurable through this map.

## 7. Supersession of the old artifacts

Nothing was silently replaced.

- `sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md` gains a **supersession banner at
  the top** naming the superseded grid md5, the new one, and the three
  specific things in it that are now wrong.
- **Corrected in place**, as blockquotes beside the original text rather
  than by editing it: §5's −2.82° (now stated as a single-sample frame
  relation, with the artifact's real +1.83°) and §9's cosine correction
  (wrong angle; conclusion unchanged, and independently reproduced).
- A new **§12** records the rebuild: environment, isolation, the captured
  publishers, the run, a full superseded-vs-committed md5 table, the
  squareness comparison, the registration, both scoring modes on one CSV,
  and what it does not establish.
- §10's reproduce recipe is corrected: it called `analyse` with no
  `--score` and would now fail, and it never derived a registration.
- `sim/README.md` gains the registration file, the two scoring modes, and a
  note that the committed map was rebuilt.
- The **raw run data is committed this time**, closing m5-08c finding 7's
  gap: `sim/worlds/evidence/m5-08d-run.csv` (4150 samples, 492 KB) and
  `m5-08d-legs.csv`. Every figure in §12 is recomputable from them.

`.gitattributes` coverage was **verified, not assumed**, as the brief asked:
`git check-attr text` returns `unset` for `warehouse.pgm`,
`warehouse.posegraph` and `warehouse.data`, and `auto` for the two yaml
files, which is correct for text.

## 8. Files changed

Modified, in `sim/` only — **nothing committed, nothing staged, no branch
created**:

```
sim/maps/warehouse/register_map.py          the trimming rule wired in
sim/maps/warehouse/warehouse.pgm            REBUILT  a663163036c5890937f9045bcf559e72
sim/maps/warehouse/warehouse.yaml           REBUILT  62bfa651dbb7f93d6a873a4edcf433cf
sim/maps/warehouse/warehouse.posegraph      REBUILT  158bc494430a7da4f6ff4b4c7335c477
sim/maps/warehouse/warehouse.data           REBUILT  01177d41fb0b29d0c39a521f76db420e
sim/scenarios/tools/mapping_evidence.py     --score, absolute mode, nan fix
sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md       supersession banner, 2 in-place
                                            corrections, new section 12
sim/README.md                               registration, scoring modes, rebuild
```

New:

```
sim/maps/warehouse/warehouse_registration.yaml   T(world -> map), derived
sim/worlds/evidence/m5-08d-run.csv               the run's raw 10 Hz samples
sim/worlds/evidence/m5-08d-legs.csv              the route's leg log
docs/reports/m5-08d-remap-and-registration.md    this file
```

`sim/launch/warehouse_bringup.launch.py` was **verified and not edited** —
the `cbbb680` version is correct as it stands (§2). `agv/` was read and not
touched. `warehouse_mapping_route.py`, `slam_toolbox_warehouse.yaml` and
`warehouse_slam.launch.py` are unchanged; **no slam_toolbox acceptance
parameter was altered** and the flattering knobs remain at shipped
defaults.

## 9. Open questions

1. **The rebuilt map is 0.45° off the building, not 0°.** Reported as
   measured. It is registered, so nothing downstream needs it to be zero,
   but the number is real and 4× better rather than gone. Whether 0.45° is
   acceptable is a gate question, not this brief's.
2. **The internal shear survived the fix: 0.42° → 0.33°.** It is therefore
   not idle drift, and it is the dominant term in the 0.141 m residual.
   Reducing it means changing the mapping, which was forbidden here and
   should be a decision, not a side effect.
3. **The 0.141 m residual is a hard floor under the AMCL gate.** If the
   gate criterion is tighter than ~0.14 m it is not measurable through this
   map by this method, and the criterion or the method has to move. This
   should be settled *before* the AMCL brief is written, not after its
   first number.
4. **To `agv/` — the gate leaks during a long idle AFTER a drive**, a case
   m5-07d did not test (its 60 s and 240 s idles were both from bringup,
   the vehicle never having moved). Measured here with ground-truth
   position frozen at 0.0000 m: **+0.01° over the 26.8 s pre-drive idle**,
   but **+2.02° over the 200.4 s post-drive idle** (0.61 °/min), or
   +0.72° / 0.24 °/min excluding the first settling window. Against the
   ungated 7.71 °/min that is 92–97 % suppressed, not 100 %. Likely
   drive-encoder dither under a settled suspension re-opening the 0.50 s
   standstill window — **unconfirmed**; nothing here tested the mechanism.
   It did not affect this map (the artifacts were saved before that idle),
   but it is precisely the regime an AMCL dwell test sits in. `agv/` is
   read-only to this agent; this is a request, not a change.
5. **Container only.** Every figure here is from the project session
   container. The owner's WSL2 host has never run this stack, and this
   evidence is qualified by the environment that produced it.
6. **One run, fresh bias draw.** No `--seed` was used, matching m5-08b's
   discipline. The rotation's *sign* flipped between the two runs, so
   nothing may treat −0.45° as a property of this world — it is a property
   of this artifact, which is why the transform is bound to its md5.
7. **The recorder still pairs latest-with-latest**, not stamp-with-stamp
   (m5-08c finding 6, ~16–32 mm at 0.80 m/s). Not touched here — it is
   below the 0.141 m floor and fixing it inside this brief would have been
   scope creep. It becomes worth doing only if the floor comes down.

## 10. Next suggested

Write the AMCL brief against `--score absolute`, with the 0.141 m
registration residual stated in its criterion as the measurement floor, and
a named dwell-and-reverse case inside one degenerate stretch.
