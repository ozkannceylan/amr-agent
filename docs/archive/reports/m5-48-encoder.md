# m5-48 — the encoder: two reading channels on the drive shaft

    brief:               docs/superpowers/plans/2026-08-06-m5-closure.md, TASK 2
                         (no file exists under docs/briefs/ for this task; the
                         plan's task block is the brief this agent executed)
    status:              done
    invariants_touched:  none

## files_changed

| File | What |
|---|---|
| `agv/forklift/model.sdf` | **+2 `JointStatePublisher` instances** on `drive_wheel_joint`, on `/forklift/gz/drive_speed/read_{a,b}`, with the block that names the arrangement a single-channel tested system and the motion-present check a stand-in. Header topic table extended. Nothing else changed |
| `agv/forklift/config.yaml` | new `safe_speed:` block (the reading-head model, the observation, the two derived observation constants), four new ROS topic names and two gz ones, and the file header extended so "nothing here is a safety parameter" still reads true |
| `agv/forklift/scripts/safe_speed_channels.py` | **new.** The two reading heads, the two channel topics, the motion-present stand-in, a `--csv` measurement mode and a `--selftest` that needs no ROS (12/12) |
| `agv/forklift/scripts/safe_speed_bench.py` | **new.** `--drive` runs the speed profile with an achieved-speed column; `--analyse` prints the derivation with its arithmetic, no ROS |
| `agv/forklift/launch/vehicle.launch.py` | `safe_speed:=false` (default) starts the second bridge and the node; `safe_speed_csv:=` is the measurement facility |
| `agv/forklift/scripts/sensor_coverage.py` | **the fix**: skip a `<sensor>` with no `<lidar>` block. It had been dead since the IMU landed |
| `agv/forklift/EVIDENCE_ODOMETRY.md` | **§15 appended**, dated 2026-08-06. Existing content byte-identical, verified by prefix comparison after the append |
| `agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` | **§14 appended**, dated: the dead instrument, the fix, the re-run, and one finding (below). Existing content byte-identical |
| `agv/forklift/README.md` | contract rows for the four new ROS topics and two gz ones, two script rows, and the "One shaft, two readings" section |
| `agv/forklift/evidence/encoder/` | **new.** 3 × run CSV (gzipped, `gzip -t` verified, writer confirmed gone first), 3 × drive table, 3 × analysis, 2 × `sensor_coverage.py` output |

Nothing outside `agv/` was written. Nothing was committed; no branch was
created. No dependency was added — Python standard library plus what the
directory already imports.

## What was built

**Two reading channels on one drive shaft, each carrying independent
noise.** `model.sdf` supplies two separate reads of `drive_wheel_joint`;
`safe_speed_channels.py` puts a **reading head** on each — its own
mounting phase on the count grid, its own per-sample read jitter — and
publishes two signed drive-wheel tread speeds at 20 Hz for the F-program
to cross-compare. The plant deliberately hands both the same number,
because it is the same shaft; everything that makes the readings differ
is the head.

**Called a SINGLE-CHANNEL TESTED SYSTEM in every artefact** — model.sdf,
config.yaml, both scripts, the launch file, README and the evidence.
Every occurrence of "two-channel" in the new material is a negation
("never a two-channel one"); swept and checked.

**The motion-present check is labelled a STAND-IN** for the mechanical
fault exclusion a real system argues on the shaft coupling, in the same
set of artefacts. It is taken from the navigation lidar — off the shaft
entirely — and every uncertainty in it resolves to MOVING.

## The two derived numbers

| | Value | Derived from | n |
|---|---|---|---|
| discrepancy threshold | **0.0308 m/s** | 4 × measured σ of the channel difference | 13 200 paired samples, 660.0 s |
| discrepancy time | **200 ms** | longest measured run of excursions above it, on the F-program's 100 ms grid: **0 of 6600** | same run; reproduced in three runs |

The noise it comes from: **σ 0.005438 and 0.005464 m/s per channel,
0.007696 m/s on the difference** (run c), against **0.005410/0.005458 →
0.007740** and **0.005383/0.005474 → 0.007659** in the two earlier runs —
1 % spread across three independent draws of the head phases and jitter.
Predicted from the head parameters alone before measurement: 5.23e-3 and
7.40e-3 m/s.

Three and not four σ was rejected on the data: 3 σ still produced 11
single-sample exceedances in 6600, each of which would be a nuisance
demand under a two-cycle time. At 4 σ there were none, in all three runs.
The time is the **floor** (two cycles, so no single sample can demand
alone) because the measured longest run is zero. Lag-1 autocorrelation on
the F-grid is −0.0105, i.e. consecutive F-samples are independent draws —
measured, because the run-length derivation is invalid if they are not.

**The honest limit, stated in the evidence rather than left to be
found:** a frozen channel is visible to the comparison only above
0.0308 m/s of tread speed. Below that the motion-present stand-in is what
covers the regime. The two mechanisms are complementary and neither
substitutes for the other.

## model.sdf: the inventory ran first, and the answer is "nothing, and here is why"

Classified by `PLANT-CHANGE-INVENTORY.md`'s method **before** the edit.
`JointStatePublisher` is a read-only post-update system that writes
nothing the physics integrates, and the joint-position/velocity
components it needs are already created for that same joint by the
existing instance — so the edit does not even add a component. By the
inventory's own rule, **every figure in every evidence file in this
directory is class U**.

The one class that argument does not settle is anything derived from
machine load, so it was measured rather than argued: three alternating
60 s captures of the simulator's real-time factor, with and without the
two systems, gave **mean RTF 0.9903 both ways** (n = 613 samples per
capture). The bridge-side cost was measured too and is real: each read
publishes at **500.011 Hz**, and one `parameter_bridge` process goes from
**4.6 % to 7.6 %** of a core when the two are added. That measured cost
is why both the bridge and the node are behind `safe_speed:=true` —
**and forgetting the argument is safe**, because a missing reading reads
to the F-program as a demand.

## sensor_coverage.py — fixed, and shown running

It had been dead since the IMU landed: `load_model` read
`lidar/scan/horizontal` off every `<sensor>` and the IMU has none, so it
raised before printing a line. `EVIDENCE_SENSOR_COVERAGE.md` was
therefore unreproducible, and m5-47's rear clip-band correction rested on
it. Fixed with one guard; both modes re-run to exit 0 and committed. The
figure that matters reproduces exactly: **index 65 at −72.26°,
self-return 0.164 m**.

## Two corrections made during the work, both worth the orchestrator's attention

1. **The motion observation's first statistic was wrong, and the review
   would not have caught it.** It read the **median** of the per-ray
   range change. A wall parallel to the direction of travel returns the
   same range profile from every point along it, so in an aisle a
   majority of usable rays do not change while the vehicle drives:
   measured, the median ran at 0.072 of body speed and **1037 of 6538
   sustained-motion samples read NOT MOVING**. Worse, the robustness the
   median was chosen for optimises the wrong direction — a false MOVING
   costs a withheld standstill, a false STOPPED corroborates a lying
   encoder. Five statistics were then logged per tick and scored on
   sustained regimes; **q95** separates rest from motion by 6217× and is
   what the node reads. Onset lag ≤ 0.050 s over 50 onsets, none missed.
2. **The topics were first named `/forklift/safe_speed/*` and the
   repository's own checker refused them** —
   `check_sensor_frames.py` §4 bars `safe_`, `ossd` and `protective` from
   any topic name on either transport. The checker was right: a
   mechanical rule cannot tell a reading from a verdict. Renamed to
   `/forklift/drive_speed/*`; the checker passes (22/22), and the final
   measurement run was taken on the renamed tree.

## Requests — things this brief needs and may not write

1. **`plc/forklift-safety/SPEC.md` (plc):** the F-program's
   cross-comparison needs the two derived constants —
   **`SpeedDiscrepancyMax` = 0.0308 m/s**, **`SpeedDiscrepancyTime` =
   200 ms** — and `SafetyInputStandIn` needs members to carry the two
   readings and the two motion flags (a `Real` pair plus two `Bool`s, or
   whatever shape §3.1 prefers). Their derivation is
   `EVIDENCE_ODOMETRY.md` §15.4; do not re-derive them from this report.
2. **`plc/forklift-safety/SPEC.md` §7.2 (plc):** **no transport for these
   readings is specified anywhere.** The scanner's verdict crosses one
   TCP link with a `ZONE 0/1` vocabulary; nothing equivalent exists for a
   speed. This directory publishes ROS topics and stops there, because
   inventing a payload against an unwritten listener is how two documents
   start disagreeing. Task 3 should fix the payload and the writer's
   handling of it, including **what the writer does when a reading stops
   arriving** — the reading channels go silent rather than repeating, so
   the writer owes them the same stale rule it already owes the field
   link.
3. **`plc/forklift-safety/SPEC.md` (plc):** the F-program must treat a
   **missing** reading as a demand, not as a zero speed. The node
   publishes nothing for a channel whose plant read is stale, precisely
   so that a frozen speed can never be handed to a monitor.
4. **`agv/forklift/EVIDENCE_SENSOR_COVERAGE.md` §13.7 R8 row and §13.8
   item 1 (agv, but m5-47's subject):** both still hand m5-12 the rear
   clip band as **"−131.5° to −72.3°"**, which is §13.2's measured
   −131.48°…−72.26° rounded in the direction that **excludes** index 65 —
   the identical defect m5-47 corrected in `FIELD-EVALUATION.md` §6,
   surviving in the document that correction was argued against.
   Everything built downstream is already correct, so nothing is wrong
   today; what is wrong is that the source file still hands the next
   reader the rounded pair. Reported rather than edited, because a
   rounding rule applied by a passing brief is how a sweep loses its
   owner.

## open_questions

1. **Should the readings cross the seam at all, or should the F-program
   receive counts?** This directory publishes speeds in m/s because the
   design spec says the F-program checks speed against the SLS limit. A
   real safe evaluator receives position or counts and forms the speed
   itself. Either is defensible; the choice belongs with the F-program's
   author and changes what task 3 types.
2. **Should `safe_speed` default true once the SLS chain exists?** It is
   false today, argued from the measured bridge cost and from the fact
   that a forgotten argument fails safe. A real forklift's safe encoder
   has no off switch, and after task 6 the honest default may be true.
3. **The motion-present threshold's floor is the simulation's.** The
   navigation lidar declares no range noise, so the at-rest floor is
   exactly zero and the 0.0014 m/s threshold has 98× of margin that a
   real rangefinder would not give it. Adding declared lidar noise would
   make the figure mean something — but it is a `model.sdf` change that
   touches every consumer of `/forklift/scan`, i.e. SLAM, AMCL and the
   costmaps, and it is emphatically not additive. Named, not taken.
4. **The 0.0308 m/s detection floor for a frozen channel** is a property
   of this noise model. It is roughly a tenth of the 0.3 m/s SLS regime,
   which seems comfortable, but nothing in this brief establishes what
   the acceptable floor is — that is a safety-spec question about SF-10.

## next_suggested

Task 3 (m5-49): the F-program SLS/SS1 spec, taking §15.4's two constants
as given and settling requests 1–3 above in the same round.
