# PLANT-CHANGE-INVENTORY — what the steer-gain change re-qualifies (m5-39)

The owner ruled option (i) on m5-38 §5: apply `model.sdf`'s steer
`p_gain` 6000 → 60000 and re-measure the affected evidence. This file is
the inventory that ruling requires, taken **before** the edit:
`model.sdf` line 1002 still reads `<p_gain>6000.0</p_gain>` and no
simulator was run for this document.

**What the change moves, physically.** The steer axis's proportional
authority is `p_gain · e` N·m against a contact scrub `model.sdf`'s own
comment records as roughly 400 N·m. At 6000 the axis cannot overcome the
scrub below `400/6000 = 3.8°`; at 60000 that knee moves to **0.38°**,
below every command RPP forms on a straight leg. So the change alters
**how the vehicle steers at small angles under load** — and nothing
else: no geometry, no sensor, no mass, no topic, no rate.

**The classification rule used throughout.** A figure is *affected* iff
its value depends on the steer axis executing commands, directly or
through the trajectory the vehicle followed while the figure was taken.
A figure taken on a stationary vehicle, a figure about a non-steer
joint, a static geometry/TF/contract check, and a figure whose motion
was straight-line traction with zero steer command are *unaffected*.
Where a file does not state enough to decide, the entry says
**unclear** and names what would settle it — per the brief, that is a
finding about the evidence file, not a guess.

Classes: **U** unaffected (with reason) · **A** agent re-measurable
(with command) · **O** owner-only (with what it needs) · **?** unclear.

---

## 1. `agv/forklift/` evidence files

### 1.1 EVIDENCE_MODEL.md (m4f-02, dated capture 2026-07-29, WSL)

The file declares itself a dated capture "left exactly as it was run",
already carrying two supersession notes (sensor layout, evaluator
source). Per-figure:

| Figure | Class | Reason / what it needs |
|---|---|---|
| §2.1 steer step responses (0.60 rad → 0.553 in 3 s "asymptotic by design"; −1.31 stop reached in 4 s) | **A** | Directly the deadband under measurement: the "asymptotic approach … integral has to build against the scrub" narrative is the exact mechanism the gain change removes. Re-measurable by `agv/forklift/scripts/steer_bench.py` (m5-38's harness) in the warehouse world; command in §4. But see the note below the table — re-measurement may not be owed at all. |
| §2.2 traction unit chain (4.0 rad/s → 0.48 m/s) | U | Drive-wheel `JointController`, not the steer PID; steer joint stayed at zero throughout. |
| §2.2 steer-stays-still under traction (0.0016 rad residual) | U | A *tighter* hold is the only possible direction at 10× the gain; the figure bounds a disturbance the change shrinks. The d_gain-hunting defect note is history, not a current figure. |
| §2.3 / §3 fork rise, rate limit, gravity hold | U | Mast joint controller; untouched by the steer gain. |
| §4 node rates (10 Hz, 20 Hz, 496.785 Hz) | U | Publication rates; no dependence on steering. |
| §5 straight drive at the wall (0.300000 m/s, zone crossing at 1.20 m, 3.18 m wall range) | U | Straight-line traction with zero steer command; speed, range and threshold figures do not pass through steer authority. |
| §6/§6.1 obstacle fault matrices | U | Driven with no Gazebo running (synthetic scans) or with a stationary vehicle. |
| §7 config/model agreement | U | Static file comparison — though the check itself re-runs in seconds after the edit and should, since it reads `model.sdf`. |

**Note on §2.1:** the file's own header rule is that it is a dated
capture. The least-cost honest treatment is a third dated supersession
note in the same style as the two it already carries ("the steer gain
was retuned by m5-40; §2.1's settle behaviour describes the prior
plant, see EVIDENCE_NAV2.md §11 for the new axis characterisation"),
rather than a re-run of a superseded configuration. m5-38's bench
figures (§11) already characterise the new axis. Recommended: **note,
not re-measurement**; the A-class command stands if the owner wants the
figure retaken instead.

### 1.2 EVIDENCE_SENSOR_TF.md (m5-06, container, 2026-07-30)

**U — entire file.** Its own §6 item 6: "every reading above is from a
stationary forklift". Sensor frames, TF, channel naming, the evaluator
matrix (synthetic scans), and the 0.850 m crate range against a spawned,
unmoving vehicle. No figure passes through steer authority.

### 1.3 EVIDENCE_SENSOR_COVERAGE.md (m5-04/m5-04b)

**U — entire file.** Sections 1–12 are computed from geometry with no
simulator ("Gazebo not installed and not run"); §13 is measured but from
four static vehicle poses with the model spawned and not driven. Its own
§6 even records that "steering to either mechanical stop changes nothing
measurable" — a statement about occlusion geometry at a held angle, not
about how the angle is reached. No figure passes through steer dynamics.

### 1.4 EVIDENCE_ODOM_TF.md (m5-07b, container, 2026-07-31)

**U — entire file, with one distinction worth writing down.** The file's
claims are transport/identity properties: one publisher on `/tf`, rate
20.000 Hz, residual transform-vs-odometry `0.000e+00` (both sides the
same simulator pose), frame names, the EKF seam switch. None depends on
steer authority. §3's drive did command steer +0.30 rad (17.2°, far
above even the old 3.8° knee, so it executed), but the file itself
states every check is "against measured motion, never against an
expected distance" — the path length 3.989 m and the +0.076 m slip line
are illustrations of the property, not plant claims (the LESSONS
2026-08-05 property-vs-draw distinction). If desired,
`check_odom_tf.py --live --drive` re-verifies for free after the edit;
nothing is owed.

### 1.5 EVIDENCE_ODOMETRY.md (m5-07c/d/e, container)

Split verdict, and the file itself supplies the evidence for both halves.

**§§1–12 (drift figures, idle hold): U.** The manoeuvre set commands
steer only at 0.000 and ±0.350 rad (±20.1°) — entirely inside the regime
m5-38 measured at `ach/cmd = 1.00` — and the file's own closed-form
reconciliations show the figures are properties of the *error model and
the gyro bias*, not of the trajectory's fine shape: §4.1's error model
alone predicts 8.843° and the live run measures 8.836°; §7's
`bias × duration` predicts −17.89° against −17.18° measured. The
headline "5.2 m / 17.2° over 106.49 m" (quoted in TODO's
measured-numbers block) survives the plant change. §12's idle holds are
pre-drive, at rest, encoder-count-bounded — no steer dynamics involved.

**§13 (the post-drive idle): A — affected.** The figures here are
measurements of the *steer axis's own post-drive relaxation against the
tyre contact*: a 4.1 s transient then one count every ~11 s, a 2.373°
sweep over 220 s, and the derived per-stop dwell cost of **−0.331°
worst case / 0.000° after 16 s** (the figure TODO carries with its n=1
caveat, LESSONS 2026-08-04). That relaxation is the joint settling where
the PID hold balances the relaxing scrub moment — exactly the mechanism
whose stiffness the gain change multiplies by ten. The *rule* (trailing
rate window, drive exact / steer ≤1 count) is plant-independent design
and stands; the *measured creep magnitude, transient length and per-stop
cost* do not necessarily reproduce. Direction of change unknown — a
stiffer hold plausibly creeps less, but that is prediction, not
measurement. Re-measure with the file's own §13.11 recipe:

```
ros2 launch agv/forklift/launch/vehicle.launch.py world:=/tmp/flat.sdf \
    world_name:=odometry_flat seed:=1 &
/usr/bin/python3 agv/forklift/scripts/check_odometry.py --phase postidle \
    --idle 220 --truth --csv agv/forklift/evidence/postidle-<date>.csv
```

Priority: low — no roadmap criterion cites the number; it qualifies the
AMCL dwell interpretation (EVIDENCE_LOCALIZATION) and the TODO entry.
The n=1 caveat those already carry covers the interim.

### 1.6 EVIDENCE_LOCALIZATION.md (m5-08e, container, 2026-08-04)

Mixed, per case, and the file states the facts that decide each:

| Figure | Class | Reason |
|---|---|---|
| The **0.141 m floor** (registration residual) | U | A property of the committed grid and its rigid registration; no motion in it. |
| **(a) route steady state — rms 0.124 m, max 0.263 m** | **A** | The route driver closes its loop on ground truth, which bounds the *path* but not the transient dynamics at the corners — and both extremes (0.263 m, 4.52°) are at corners. The figure is one draw per §10 item 4 anyway. It matters beyond itself: **`footprint_padding: 0.27` is derived from the 0.263 m max** (TODO measured-numbers block). Direction argument: a plant that executes small corrections can only track the commanded route the same or tighter, so a padding derived from the old max is conservative on the new plant — qualification is honest, re-measurement is better. Command: the file's own §9 recipe with `--profile`/route case `a_route`. |
| **(b) convergence — ≤ floor after 13.81 m, final 0.007 m** | **A** | The converge driver "subscribes to nothing: it plays a timed profile and has no feedback path of any kind" — the executed trajectory is therefore **open-loop through the plant by construction**, and its weave commands 0.12 rad (6.9°), a regime the old plant executed with the measured lag (ach/cmd 0.82 at 3.1°, ~1.0 well above). A new plant draws a different trajectory and a different convergence-vs-distance curve. §9 recipe, `--profile converge`. |
| **(c) dwell — growth −0.007 m over 128.7 s; AMCL 0 corrections at rest** | U (the dwell claim itself) | Measured with ground truth frozen at 0.00000 m; a stationary vehicle has no steer execution in the loop. The *entry* error 0.289 m depends on the approach drive and inherits (b)'s open-loop caveat. |
| **(c) the EKF handover +0.539° / second stop +0.548°** | **A** | Same mechanism as EVIDENCE_ODOMETRY §13 — the steer axis's post-drive relaxation feeding the estimator — measured on the old plant. Already flagged by this file's own §10 item 2 as "restate as a range over stops, or re-derive"; the re-derivation should happen **on the new plant**, once, rather than twice. |
| **(d) reverse — every figure at the floor; "no measurable penalty"** | U (the claim), qualify the runs | The claim is bounded by the instrument's resolution and by the named bias-draw confound; both bounds are plant-independent. The runs themselves are old-plant runs and get the blanket qualifier (§3 below). |

Note for the schedule: m5-38 §11's five new-plant arrival runs already
carry localization figures on the new plant — max 0.1523 m worst of
five, all under the 0.263 m acceptance — so criterion-(d)-facing
localization performance on the new plant is **already in hand** (see
§4). What is not in hand is the mapping-route case (a) and the
convergence case (b) on the new plant.

### 1.7 EVIDENCE_ENVELOPE.md (m5-11, owner's WSL, 2026-08-04)

**U — every figure**, with the reason per class of figure:

- The **gate-law observations** (§3 enable drop, §4 stale, §5 clamp, §6
  release lurch, §7 pass-through, §8 permit) all run a straight cruise
  with `w = 0` — the file says so per scenario — so no figure passes
  through the steer axis. The stop distances (0.1738 / 0.3715 / 0.2187 m)
  are traction-ramp arithmetic; the pass-through residual `0.000e+00` is
  a design property (its latency half is already marked one-draw by the
  m5-21 correction note).
- §10's Nav2-goal run is an old-plant drive, but its measured figures
  (stop distance, decel, the code-105 abort) are gate figures, not
  steering figures, and its four-stop table is consistent to 1.9 mm
  across contexts.
- The file already carries one open environment debt (m5-26: needs the
  post-dist-upgrade qualifier, TODO) — unrelated to the plant change but
  the same edit visit could carry both notes.

### 1.8 EVIDENCE_VEHICLE_IMAGE.md (m5-24, owner's WSL, 2026-08-05)

- Proofs 1, 2, 5 (domain isolation, contract visibility, compatibility
  recipes) and proof 4 (pass-through residual): **U** — graph/interface
  properties and a design-property re-run.
- **Proof 3's drive outcome** (goal ABORTED 104, 72.42 s, absolute error
  2.5362 m, tracking rms 0.9001 m, 3 rotation refusals): **A —
  affected, and in substance superseded.** This is one draw of exactly
  the arrival distribution m5-38 diagnosed; the file itself already
  refuses to treat it as a characterisation. On the new plant, m5-38
  §11.6's five repeats went 5/5 clean with zero go-arounds. What proof 3
  still owes is one confirmation **inside the vehicle image** (domain 51,
  gated chain) on the new plant — the composition, not the distribution,
  is what that proof is about. Command: the file's §9 recipe (proof 3
  block) re-run once after the edit.
- The wiring claim (ACCEPTED, all 17 processes, 0 deaths): **U**.
- Same m5-26 environment-qualifier debt as EVIDENCE_ENVELOPE (TODO).

### 1.9 EVIDENCE_NAV2.md (m5-10 §§0–7 container; §8–§11 owner's WSL)

The file already rules on itself twice: §8.6 re-qualified every §0–§7
figure against the WSL platform, and §11 (m5-38) established the plant
cause and measured the new plant experimentally. This inventory adds the
plant column on top of those rulings:

| Figure | Class | Plant-change ruling |
|---|---|---|
| §1 the five Jazzy parameter traps | U | Parameter/API facts; no motion. |
| §2 footprint hull, §2.1 lateral budget | U | Computed from committed files. But see `footprint_padding` row below. |
| §3.1/§3.2 conversion formula + round trip | U | Closed-form, no simulator. |
| **§3.3 convcheck — understeer to 23 % at the tightest arc, arc radii achieved, rotation refused** | **A** | A direct plant characterisation. Its arcs (26.57°, 45°) sit above the old deadband knee, but the transient onto each lock and the achieved-radius means pass through the steer PID, and `nav2.yaml`'s steer-reserve derivation cites the 23 %. m5-38 §11.2's static curve already characterises the new axis at small angles; the arc-level check should be retaken once: `python3 agv/forklift/scripts/nav2_run.py convcheck` (per §7's recipe) on the new plant. The rotation-refusal and sign-convention rows are design properties and will reproduce. |
| §4 `footprint_padding: 0.27`, `xy/yaw_goal_tolerance` derivations | see note | Derived constants, not measurements. Their source figures move twice: the 0.263 m max was superseded on WSL by the shuffle's 0.661 m (§8.6), and the shuffle regime itself **did not occur on the new plant** (§11.6: 0 of 5, no miss-abort). Re-derivation after the change is the standing TODO item ("padding re-derived or the shuffle prevented") — the plant change is the thing that prevents the shuffle, so the re-derivation belongs after it, on new-plant data. |
| §5.1 case A (straight route, container: 13.40 s / 0.183 m) | superseded | Already superseded twice: by §8.2's WSL distribution (old plant), then by §11.6's new-plant 5/5. Nothing to schedule; the figure stands as history with §8.6's ruling on it. |
| **§5.2 case B (2 m astern, rms 0.0009 m), B′ (reverse diverges ~50° at ~2.4 m, n=1)** | **A** | Old plant, container, already "unverified on this platform" (§8.6). Reverse pure pursuit with the steered axle trailing is exactly a small-correction regime — under the old plant those corrections did not execute, so **B′'s divergence figure may be partly a deadband artefact**, and TODO's measured-numbers block quotes it. Re-drive B and B′ on the new plant (recipe §7, cases B/B′). This is the one committed figure whose *sign of conclusion* the plant change could flip. |
| **§5.3 case C (degenerate stretch, 11.09 s, 0.150 m), §5.4 case D as a drive (refusal 208, vehicle moved 0.000 m)** | **A** | Same status: old-plant, container, platform-unverified. C is a short forward drive (low sensitivity, but a drive); D's refusal half re-measured on the bench (§8.6) and is U — only the "vehicle never moves" half is a drive observation. Re-drive with §7's recipe when the case set is retaken (§8.7 item 4 already asks for this for the showcase, independent of the plant). |
| §5.5 planner bench | U | Deterministic, no simulator, re-measured exactly on WSL (§8.6). The planner never sees the plant. |
| §8.2 WSL distribution (1/2/2), §8.3 checker geometry (R = 2.1–2.6 m/rad), §8.5 shuffle cost (0.661 m) | superseded / U | Old-plant measurements that §11 explains and §11.6 supersedes as the live distribution. The **R = metres-per-radian geometry is a kinematic property of the vehicle, not of the steer gain** — it survives and LESSONS 104's rule keeps citing it. Keep as diagnosis history; nothing to schedule. |
| §9, §10 (staging, d = 4.5) distributions and predictions | superseded | The two arrival-brief rounds the diagnosis explains (§11.4). History with the explanation attached; nothing to schedule. |
| **§11 (m5-38): static curve, bench A/B, five repeats 5/5, localization max 0.1523 m, cross-track rate 0.0134 m/m** | **in hand** | Taken **on the experimental model equal to the ruled change** (one diffed line, `evidence/m5-38-exp-model.diff`). Once model.sdf line 1002 carries 60000, these are the new plant's figures. One formality is owed: §11.6 ran with `model:=` overriding a committed file — after the edit the same runs are runs *of the committed tree*; the next brief should either re-run once to stamp that or record the diff-identity argument in §11 explicitly. |

### 1.10 model.sdf's own prose — a documented claim now falsified

`model.sdf`'s steer-plugin comment states the scrub "disappears once the
vehicle rolls". m5-38's convcheck-style bench falsified that: with grip,
small commands fail while rolling too. The comment block (lines
~967–997) is qualified by the change anyway — its `i_max` sizing
argument is stated against `p_gain 6000` — so the m5-40 edit must
rewrite the comment, not only the number, or the file will explain a
gain it no longer has. (The falsified-claim finding itself is carried to
`sim/` in the report per the brief; the comment text lives in `agv/` and
is this layer's to fix in m5-40.)

---

## 2. `sim/` evidence (not this layer's to edit — findings and requests)

### 2.1 sim/worlds/FORKLIFT_ARENA_EVIDENCE.md

| Figure | Class | Reason |
|---|---|---|
| §1–§4 bringup, wiring, rates, scanner (incl. the ±45° dropout) | U | Graph and sensor facts; no steer dynamics. |
| **§5 traction pulse — 4.0 rad/s → 0.480 m/s, coast 0.459 m** | **? unclear** | Not because of the steer gain — because it **contradicts m5-38's arena finding** (5.000 rad/s commanded against 0.005 m/s achieved, "the arena floor gives the drive wheel no traction", measured twice). Both cannot describe the same world. Either the world's friction changed between the two captures, the spawn/contact differed, or one measurement is of something other than it says. An agent cannot tell from the two files which describes the committed arena. **This is the finding the brief's §2 class 4 exists for**, and it sharpens the sim/ request: the traction ruling must reconcile §5 before it rules. |
| **§6 steer step — 0.570 rad at 5 s for a 0.60 rad request; back through 0.048 rad 5 s after zero** | **A (sim/-owned)** | Directly the old plant's steer settle, praised in the file as "the asymptotic approach m4f-02 characterised". Changes visibly under the new gain. Re-measurable by re-running the file's §6 commands; the edit is sim/'s. |
| §9 render budget (RTF figures, beam cost) | U | Rendering cost; steering does not render. |

### 2.2 sim/worlds/WAREHOUSE_SLAM_EVIDENCE.md and the committed map

**U — with the one sentence that matters.** The committed grid, its
squareness (0.33° shear), its registration (θ = −0.4535°, residual max
0.141 m) are properties of a **frozen artifact scored in its own
right**: the map is exactly as good as its registration says,
independently of the plant that drove the mapping run. The mapping
drive's own history (drift while parked, loop closures) is a dated
record of that run. Nothing obliges a re-map; the 0.141 m floor stands
(re-verified per-run by `load_registration`, EVIDENCE_NAV2 §8.6). If
the map is ever rebuilt for its own reasons (shear reduction,
m5-08d open questions), the new plant is what will drive it — but that
is not owed to this change.

### 2.3 sim/worlds/WAREHOUSE_EVIDENCE.md, BRINGUP_EVIDENCE.md, CELL_EVIDENCE.md

**U — all three.** Warehouse bringup is topics/rates/register geometry
on a spawned vehicle; BRINGUP_EVIDENCE is the retired platform's
historical record (marked so in its own title); CELL_EVIDENCE is the M3
fixed cell, which contains no forklift.

---

## 3. The M4 evidence set, and the recording

### 3.1 The fact that reorders this whole section

**The formal M4 commissioning showcase recording does not exist yet.**
The roadmap's M4 row *closes on* it, PLAN says "closes on the owner's
formal showcase recording", and TODO's owner queue still carries "Run
T5.1–T5.6 … then record the showcase — the recording is gate
evidence." What exists on the prior plant is:

- the **informal owner video** (Screen Recording 2026-07-30 085503.mp4,
  outside the repo, named informal in TODO) — made on the old plant;
- the owner's live TIA sessions and captures
  (`plc/forklift/evidence/m4-*.png`, cold-start capture, node
  read-backs) — **U**: TIA/PLC-side facts, no vehicle-motion figure;
- `hmi/evidence/` harness logs and cycle CSVs — **U**: HMI↔PLC process
  data, the plant never appears in them;
- the T5 / commissioning-scenario **as-run records: not yet produced**.

### 3.2 What this does to the "honest edge"

The edge the m5-39 brief names — "the recorded showcase no longer
matches the tree" — is therefore an **ordering constraint, not a
qualification problem**: no committed recording is invalidated, because
none is committed. And the owner has already ruled the matching rule:
TODO (judge finding 7), *"M4 showcase recording: owner ruled it is made
against the CURRENT tree."* The same TODO item already owes the M4
evidence a note for the m5-06 instrument change (scanner deletion,
stop-plane move); the steer-gain change is a **second entry for the
same note**, so the recording says which plant it certifies.

**Owner-only items, each with what it needs:**

| Item | What it needs |
|---|---|
| Formal M4 showcase recording (gate evidence) | **Record after m5-40 lands**, per the owner's own current-tree ruling. Cost: zero extra — the recording was owed anyway. The T5.1–T5.6 and commissioning-scenario runs that precede it then execute on the new plant, which is the plant the tree carries. |
| The informal 2026-07-30 video | One qualifying sentence wherever it is cited (today: TODO's owner-build item): informal, prior plant. No re-recording — it was never gate evidence. |
| M4 evidence/scenario instrument-change note | Extend the existing m5-06 note obligation with the steer-gain line. Owner or the owning agents (plc/ scenario file is plc's; sim/scenarios is sim's) — not agv's files. |
| M5 showcase recording (criterion (d)/(e) closure) | Future; records the new plant naturally. Only constraint: after m5-40, which is anyway the ruled order. |

If, contrary to the repository's record, the owner holds recorded
showcase material this inventory cannot see, the two honest options are
as the brief states: **re-record** (cost: one owner session, on
procedures that already exist) or **qualify** ("recorded on the
pre-m5-40 plant; criterion behaviours unaffected in kind" — cost: one
paragraph, but it leaves gate evidence that no longer matches the tree,
against the owner's own current-tree ruling). Re-recording is the one
consistent with the standing ruling.

### 3.3 Does the plant change alter M4 criterion behaviour?

The M4 criteria (a)–(e) are qualitative behaviours (drive, fork limit,
speed cap, stop latch, heartbeat zeroing), formed by the PLC and
carried by the bridge — none cites a steering figure. The rehearsal
figures the scenario file does carry (fork stopping height 1.5561 m —
mast joint, whose gain is already 60000 and does not move; the
638–692 ms heartbeat-stale span — process chain) are steer-free, so
the procedures survive the change as written. Teleop steer
setpoints are operator-scale (well above 0.38°). m5-38's bench saw **no
hunting at the stops** at the new gain, and the mast joint already runs
gain 60000. Risk to the M4 procedures is therefore low but *not
measured on the teleop path*: the first owner teleop session after
m5-40 is the check, and it costs nothing extra since that session is
owed anyway.

---

## 4. The re-measurement order — by what a criterion cites

m5-38 §11.6's five repeats were taken on an experimental model equal to
the ruled change (`evidence/m5-38-exp-model.diff`, one line), so the
top of this list is **already in hand**, not scheduled:

| # | What | Criterion / clause it serves | Status / command |
|---|---|---|---|
| 0 | Arrival distribution 5/5 clean, no shuffle, localization max **0.1523 m**; cross-track rate 0.0134 m/m | **M5 (d)**: "Nav2 drives the forklift autonomously to commanded goals" | **IN HAND** (EVIDENCE_NAV2 §11.6, m5-38). Owed: one run *of the committed tree* after the edit (or the recorded diff-identity note in §11) so the figures stop resting on a `model:=` override. |
| 1 | M4 (a)–(e) runs T5.1–T5.6, commissioning scenarios, then the **showcase recording** | **M4 row, whole criterion** — the gate closes on the recording | **Owner-only, and already owed.** Ordering: after m5-40. No re-measurement is created by the change; the change must simply land first. |
| 2 | Nav2 case set B, B′, C, D-as-a-drive | **M5 (d)** (AT-02/03/04 will drive these regimes; §8.7 item 4 already owes them for the showcase, platform-wise) | Agent. §7 recipe of EVIDENCE_NAV2, cases B/B′/C/D, on WSL. **B′ first** — it is the one figure whose conclusion (reverse diverges at ~2.4 m, n=1, quoted in TODO) the deadband may have produced. |
| 3 | `footprint_padding` re-derivation (and the goal-tolerance pair beside it) | **M5 (d)** via the costmaps every criterion-(d) drive runs on | Agent + interface of the standing TODO item ("padding re-derived or the shuffle prevented"). The shuffle did not occur on the new plant (0/5); re-derive from new-plant localization maxima once run 0's stamp and run 2 exist. |
| 4 | §3.3 convcheck (understeer 23 %, arc radii) | supports **M5 (d)** (nav2.yaml's steer-reserve derivation cites it) | Agent: `nav2_run.py convcheck` per EVIDENCE_NAV2 §7, new plant. |
| 5 | EVIDENCE_ODOMETRY §13 post-drive relaxation (−0.331°/stop, n=1) | supports **M5 (d)** dwell interpretation; no criterion cites it | Agent: `check_odometry.py --phase postidle --idle 220 --truth` (recipe §13.11). Folds the LOCALIZATION §10-item-2 "restate the bound" request into one new-plant measurement. |
| 6 | EVIDENCE_LOCALIZATION cases (a) route and (b) converge | supports **M5 (d)**; not criterion-cited (criterion-facing localization is in hand via run 0) | Agent: §9 recipe. Low priority; qualification acceptable meanwhile (the derived padding is conservative in the direction the change moves). |
| 7 | EVIDENCE_VEHICLE_IMAGE proof 3 inside the vehicle image | ADR 0016 phase 1 claim; no gate criterion cites the drive outcome | Agent: one §9-recipe run in domain 51 after the edit. |
| 8 | EVIDENCE_MODEL §2.1 steer settle | none — dated capture | Note-only (third supersession note), or `steer_bench.py` if the owner prefers a figure. |
| 9 | sim/ items: ARENA §6 steer step, §5-vs-m5-38 traction contradiction | none — supporting world evidence | **Requests to sim/** (see report): reconcile §5 with the m5-38 traction finding, then re-take §6 on the new plant or supersede it in place. |

**Unclear class, complete list:** exactly one figure — ARENA §5's
traction pulse (2.1 above) — could not be classified from the evidence
files because two committed measurements of the same world contradict
each other. Everything else classified cleanly.

## 5. What this inventory did not do

No simulator was run, `model.sdf` is unedited (line 1002 still
`6000.0`), no figure was re-derived, and `plc/` and `bridge/` were not
touched. Classifications rest on what the evidence files themselves
state; where a file could not settle its own dependence, the entry says
so rather than deciding.

---

# 2026-08-06 — what the brake and controller disable re-qualify (m5-50)

The second entry in this file, taken **before** the edit, by the method
sections 1-5 above established. At the moment of writing, `model.sdf` is at
`md5 48e22f3fac3baa422e22b1a2d452cd9f`, its three actuator plugins still
name `/forklift/gz/steer_cmd`, `/forklift/gz/traction_cmd` and
`/forklift/gz/fork_cmd` (lines 1052, 1066, 1097), no simulator was run
for this section, and the repository head is `232f3de`.

## 6. What the change is, physically

The obligation is `plc/forklift-safety/SPEC.md` §11.7's table and the
design spec's §5 observable: on `TorqueOffDemand` the **joint controller
is disabled and a holding brake is applied**, the vehicle is **deaf to
commands**, and it **stays deaf if the envelope reopens** — authority
returns only when the demand falls, which only the monitored reset can
cause.

**The move.** The model's three actuator plugins stop listening on the
topics the vehicle stack publishes and listen instead on three
**terminal** topics of their own:

| Plugin | Before | After |
|---|---|---|
| `JointPositionController` `steer_joint` | `/forklift/gz/steer_cmd` | `/forklift/gz/actuator/steer_cmd` |
| `JointController` `drive_wheel_joint` | `/forklift/gz/traction_cmd` | `/forklift/gz/actuator/traction_cmd` |
| `JointPositionController` `mast_joint` | `/forklift/gz/fork_cmd` | `/forklift/gz/actuator/fork_cmd` |

Nothing else in the file moves: no gain, no geometry, no mass, no
inertia, no sensor, no rate, no joint limit. The gap the rename opens is
filled by one new node, `scripts/sto_contactor.py`, which is the **only**
publisher of the three terminals and which forwards the three command
topics one-for-one while torque is present.

**So the change is not additive in effect, and this is why.** It inserts
a component into the path between every command publisher and every
actuator. Three consequences follow, and they are what section 7
classifies against:

1. **Latency.** Every actuator command now crosses one more node. The
   size of that hop is not predictable from the design — this repository
   has already measured the same class of hop at between 0.4 ms and
   24 ms on the same machine (`EVIDENCE_ENVELOPE.md` §7 and its m5-21
   correction), so it is measured here rather than argued.
2. **Continuity.** Five committed publishers today address the plant
   directly — `forklift_io.py`, `localization_run.py`, `steer_bench.py`,
   `safe_speed_bench.py` and `sim/scenarios/warehouse_mapping_route.py` —
   besides any `ros2 topic pub` in a recipe. All of them now address a
   subscriber that did not exist when they were written. A publisher that
   emits once immediately after construction can lose that message to
   discovery (LESSONS 2026-07-28, the bare `--once` entry), and after
   this change losing it means losing it at the plant.
3. **What "the vehicle did not move" now means.** Before the change,
   a stationary vehicle under a command had exactly one interesting
   cause. After it, there is a second: the contactor. That is section 8.

## 7. The classification rule, and the per-figure verdict

A figure is **affected** iff its value depends on (i) the **latency or
continuity** of the actuator command path, or (ii) the **topic name** the
model listens on, or (iii) an observation that the vehicle **failed to
move**, which the change gives a second possible cause.

A figure is **unaffected** if it is sensor-side, static geometry, TF or
contract, computed without a simulator, taken on a stationary vehicle
whose stillness is not the claim, or measured entirely upstream of
`forklift_io`'s plant publication.

Classes as section 1: **U** unaffected · **A** agent re-measurable ·
**O** owner-only · **?** unclear.

### 7.1 `agv/forklift/` evidence

| File / figure | Class | Reason |
|---|---|---|
| `EVIDENCE_ENVELOPE.md` §3 enable-drop: reaction 0.0681 s, **stop distance 0.1738 m**, standstill 0.850 s | **A** | (i) directly. The edge-to-standstill interval contains the whole command path; one added hop lengthens it by the hop's latency times the speed at the edge. At 0.40 m/s a 1 ms hop is 0.4 mm and a 24 ms hop is 9.6 mm on a 173.8 mm figure — the difference between negligible and 6 %, which is why it is measured and not argued |
| `EVIDENCE_ENVELOPE.md` §4 stale (0.3715 m) and §5 clamp (0.2187 m) stop distances | **A** | Same mechanism, same path, different trigger |
| `EVIDENCE_ENVELOPE.md` §6 release lurch (0.0852 m creep, the LESSONS 2026-08-04 terminal-value entry) | **A** | (i) and (iii): the lurch is a continuity observation of the terminal, which is now a different topic with a different publisher |
| `EVIDENCE_ENVELOPE.md` §7 pass-through residual `0.000e+00` and gate latency | **U** | Measured `/cmd_vel_smoothed` to `/cmd_vel_gated`, entirely **upstream** of the plant publication. The contactor is downstream of both |
| `EVIDENCE_ENVELOPE.md` §8 permit, §9 readback | U | Envelope-side datum observations, no actuator path in them |
| `EVIDENCE_ENVELOPE.md` §10 Nav2-goal run (stop distance, decel, code-105 abort) | **A** | A drive; its stop figures are (i) |
| `EVIDENCE_MODEL.md` §2.1 steer step, §2.2 traction chain, §2.3/§3 fork | **A**, low priority | All three are commanded-to-observed step responses through the path. The file is a dated capture already carrying supersession notes; the honest treatment is one more note plus a confirmation that the chain still executes, not a re-run of every step |
| `EVIDENCE_MODEL.md` §7 config/model agreement | **A** | A static comparison that **reads `model.sdf`**, which changed. Costs seconds |
| `EVIDENCE_MODEL.md` §4 node rates, §5 straight drive to the wall, §6 obstacle matrices | U | Rate- and sensor-side |
| `EVIDENCE_SENSOR_TF.md`, `EVIDENCE_SENSOR_COVERAGE.md`, `EVIDENCE_FIELD_EVALUATION.md` | U | Sensor geometry and scan evaluation, on a stationary or irrelevant plant. No actuator command appears in any figure |
| `EVIDENCE_ODOM_TF.md` | U | Transport and identity properties; its drive is an illustration by the file's own statement |
| `EVIDENCE_ODOMETRY.md` §§1–12 drift figures | U | Properties of the error model and the gyro bias, reconciled closed-form by the file itself. A millisecond of command latency does not enter them |
| `EVIDENCE_ODOMETRY.md` §12 idle holds, §13 post-drive idle | U | At rest, no command in flight |
| `EVIDENCE_ODOMETRY.md` §14/§15 safe-speed channel noise, sigma, the two derived constants | U | Measured on the **read** side of the shaft. `plc/forklift-safety/SPEC.md` §11.1 quotes these; nothing in the reading path moves |
| `EVIDENCE_LOCALIZATION.md` (a) route, (b) converge | **A**, low priority | (i): case (b) is open-loop through the plant by construction, so any change in the executed trajectory changes the curve |
| `EVIDENCE_LOCALIZATION.md` 0.141 m floor, (c) dwell | U | Registration, and a stationary vehicle |
| `EVIDENCE_NAV2.md` §3.3 convcheck, §5.1–§5.4 cases A–D, §11.6 five repeats | **A** | Drives — and §5.4 case D is **the (iii) case**: its result is "refusal 208, vehicle moved 0.000 m". After this change that sentence no longer distinguishes a correct refusal from an unpublished terminal |
| `EVIDENCE_NAV2.md` §1 parameter traps, §2 footprint, §3.1/§3.2 closed-form conversion, §5.5 planner bench | U | No simulator, or no plant |
| `EVIDENCE_VEHICLE_IMAGE.md` proofs 1, 2, 4, 5 and the wiring claim | U | Graph and interface properties |
| `EVIDENCE_VEHICLE_IMAGE.md` proof 3 (a drive inside the image) | **A**, low priority | (i), and the image must now also carry the contactor — a **composition** claim, which is what proof 3 is about |
| `ARRIVAL-GEOMETRY.md` derived geometry (R metres-per-radian, the tolerance product) | U | Kinematic properties of the vehicle, independent of who publishes the command |

### 7.2 Files this layer does not own — findings, not edits

| File | Class | Finding or request |
|---|---|---|
| `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md` §5 traction pulse, §6 steer step | **A (sim/-owned)** | Both are commanded-to-observed responses through the path. §5 also still carries the contradiction §2.1 of this file recorded; this change does not settle it |
| `sim/scenarios/warehouse_mapping_route.py` | **request** | Publishes `gz_traction_cmd` and `gz_steer_cmd` directly. It keeps working unchanged — the contactor forwards those topics — but the scenario now depends on the contactor running, which `vehicle.launch.py` starts by default |
| `plc/`, `bridge/`, `hmi/` evidence | U | PLC-side, HMI-to-PLC and OPC UA figures. No vehicle actuator appears in any of them |
| `bridge/` | **request** | `TorqueOffDemand`'s mirror must reach ROS as a Bool. Section 10 states the topic and the polarity the vehicle needs |

## 8. What the change might be flattering, and what it exposes

The 2026-08-05 lesson attached to this file's first entry is that a fix
un-masks as readily as it removes: restoring the steer axis's authority
made two committed reverse cases **worse**, because a dead actuator had
been flattering a route on which doing nothing was correct. The
symmetric question here has two answers, and they run in opposite
directions.

**What the change could flatter.** A contactor that opens when it should
not — or simply a contactor that is not running — produces a vehicle that
does not move, and *every refusal-shaped observation in this repository
reads that as a pass*. `EVIDENCE_NAV2.md` §5.4's "the vehicle moved
0.000 m", the rotation refusals of §3.3, the creep-deadband deadlock of
LESSONS 2026-08-05, and the whole of the SS1 observable itself all have
the shape *nothing happened, and that is correct*. After this change none
of them is self-validating.

**The rule this forces, applied to every run in section 9:** an
observation that the vehicle did not move is evidence only beside a
**positive control in the same run** — a command that does move it,
before or after, through the same path. A run without one is discarded,
not repaired.

**What the change could expose.** The reverse direction is real too. The
contactor is the first component to sit downstream of *all* the direct
plant publishers, so a figure that was quietly relying on a bench
bypassing `forklift_io` now goes through a component that records what it
forwards. Nothing is predicted from that; it is written down so that a
surprise in section 9 is attributed rather than explained away.

**What is deliberately not claimed.** The contactor and the brake are a
**stand-in** for an onboard hardwired inhibit, written in Python, on the
process side of the vehicle. No Category, Performance Level, SIL or PFH
is claimed for them or implied by them (ADR 0011 D5). The safety path
they model is hardwired and onboard in the architecture (invariant 1);
what is built here is a simulation of its effect on the plant.

## 9. The re-measurement order — by what a criterion or a design cites

Taken in this order. Every run states its n; every no-motion observation
carries its positive control; results are written into the evidence file
as they land rather than held to the end.

| # | What | Why here | Instrument |
|---|---|---|---|
| 0 | **Baseline, before the edit**: actuator-path latency and a stop observation on the unedited tree | There is no delta without a before, and section 7's whole first column turns on the size of one hop | `scripts/sto_bench.py --phase baseline` |
| 1 | **The added hop**, after the edit: forwarded-command latency and one-for-one fidelity, n stated | Decides whether the A-class stop distances need re-running or only a note | `scripts/sto_bench.py --phase passthrough` |
| 2 | **The observable** (design spec §5): a command after torque-off produces nothing; the envelope reopens and it still produces nothing; the demand falls and motion returns on a fresh command | This is the deliverable. Without it SS1's two stages are indistinguishable | `scripts/sto_bench.py --phase observable`, positive control at both ends |
| 3 | **`EVIDENCE_ENVELOPE.md` §3 stop distance**, re-run | The one A-class figure a gate-criterion path actually cites | `envelope_run.py`, scenario `enable-drop` |
| 4 | `EVIDENCE_MODEL.md` §7 config/model agreement | A static check that reads the changed file | `check_contract_topics.py` |
| 5 | `EVIDENCE_NAV2.md` case set and `EVIDENCE_LOCALIZATION.md` (a)/(b) | Supporting figures; no criterion cites them and the closure plan freezes autonomy as a prototype | Deferred with the qualifier, listed in the report |
| 6 | `sim/` ARENA §5 and §6 | Not this layer's file | Request in the report |

## 10. The vehicle-side contract this change creates

Written here so the consumer is built against a contract rather than
discovered:

| Item | Value |
|---|---|
| Demand in | `/forklift/safety/torque_off_demand`, `std_msgs/Bool`, published by the bridge from the `TorqueOffDemand` mirror |
| Latch | Opens on an observed `TRUE`; **stays open** while `TRUE` and after it, until an observed `FALSE`. The envelope has no vote |
| Absence of the demand | **Not torque-off.** Loss of supervision is a degraded mode, not a safety event (invariant 2), and the controlled stop it needs already exists in the envelope gate's stale rule. STO is **asserted, never inferred** — the alternative would put a safety reaction on the network's silence and would make every run without a bridge a dead vehicle |
| While open | The traction terminal is driven to `0.0` continuously — the holding brake. Steer and fork terminals are held at their last forwarded value: explicit standing orders, because silence is a command wherever a consumer holds (LESSONS 2026-08-04) |
| Applied state out | `/forklift/safety/torque_off_applied`, `std_msgs/Bool`, for the monitoring plane. Read-only; nothing commands from it |
