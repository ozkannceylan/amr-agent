# Report m5-j2 — restore the F-I/O conditionality, correct the authority file

```
brief:               docs/briefs/m5-j2-restore-conditionality.md
status:              done
files_changed:       [agv/forklift/model.sdf,
                      agv/forklift/README.md,
                      agv/forklift/config.yaml,
                      agv/forklift/launch/vehicle.launch.py,
                      agv/forklift/EVIDENCE_SENSOR_COVERAGE.md,
                      docs/reports/m5-j2-restore-conditionality.md]
invariants_touched:  none — ADR 0011 D2's decision is restated nowhere; only
                     its feasibility condition, which the ADR already carries,
                     is propagated into agv/
open_questions:      four, below
next_suggested:      m5-12's brief needs the same conditional and the R7
                     sequencing sentence; both are docs/ and outside this scope
```

## What was done

### 1. The conditional restored — five sites, not the three the review named

Judge finding 2 named three `agv/` locations. A whitespace-normalised sweep of
the whole directory for the `F-DI`, `F-I/O`, `PLCSIM`, `API` and `OSSD`
subjects found **five** statements of the unproven mechanism. Each now carries
the condition ADR 0011 D2 attaches to it: the path is **design intent, has
never been run**, is settled in the tool by `plc/forklift-safety/FIO-FEASIBILITY.md`
under brief m5-03 whose verdict section is blank, and has a **named fallback**
(the standard-DB stand-in of `plc/forklift-safety/SPEC.md`, labelled a stand-in
wherever it appears). Each site also states what does **not** depend on the
verdict, so a "no" answer does not require re-editing these files.

| # | Site | Named by the review? |
|---|---|---|
| 1 | `model.sdf` header, two-channel block | yes (`:100-101`) |
| 2 | `README.md` two-channel table + new note | yes (`:87`) |
| 3 | `EVIDENCE_SENSOR_COVERAGE.md` §10 item c | yes (`:531-533`) |
| 4 | `config.yaml` `topics:` channel commentary | **no — found by the sweep** |
| 5 | `launch/vehicle.launch.py` bridge-list commentary | **no — found by the sweep** |

The two `README.md` scanner-table rows reading *"Safe channel → the F-program,
off-network"* were left as claims (both hold under either verdict) but now
point at the note, so the table cannot be read alone as the settled mechanism.

The fallback question itself is **not** decided here (forbidden, and it is
judge finding 1's, pending m5-03).

### 2. `model.sdf` corrected — and the sweep found a third stale claim

Both sentences the brief named are gone. The block now states the consumer of
every channel as it actually stands since `6068b31`: front measurement channel
bridged and read by `obstacle_zone.py`; rear measurement channel unconsumed and
unbridged; neither safe channel a topic on any transport; navigation lidar the
SLAM/AMCL/costmap input.

Sweeping the surrounding sensor commentary by subject rather than by the two
line numbers turned up **two more statements the same ruling invalidated**:

* **`model.sdf` nav-lidar comment (was `:362-366`).** *"Range max is 8.0 m and
  that number is COUPLED: it is what obstacle_zone reports as the clear
  value."* False since the ruling — the evaluator reports the **front
  scanner's** 5.50 m. Corrected, and the coupling was **moved to the sensor it
  now belongs to**: the front scanner's `<sensor>` comment carries it, the rear
  scanner's says explicitly that it has no consumer and no coupled window.
* **`model.sdf` header (was `:18-20`).** *"What the two safety scanners give
  this project is the GEOMETRY of a real installation … **and nothing else**."*
  Since the ruling the front device also gives the project the measurement
  channel a process function reads. Corrected without weakening the
  not-a-safety-device statement around it.

No measured figure was changed. `scripts/check_sensor_frames.py` still passes
19/19, `model.sdf` still parses, `config.yaml` still loads, both Python files
still compile.

### 3. The common-cause guard, written once

`README.md`, section *"Two channels per safety scanner"*, one paragraph: both
channels come out of the **same `gpu_lidar` render**; that is honest device
modelling, because a real scanner derives its safe output from its own
measurement core too; it is **not redundancy**, the two share every failure of
the rays, and the split buys naming hygiene and consumer separation only. **R7**
is cited as the live instance (8.9° simulated mast shadow against 29.0°
physical, blinding process stop and field evaluation identically on the same
scan) and **R8** as its converse. The adjacent claim *"two paths that never
meet"* was scoped to **downstream of the sensor**, which is where it is true.

The guard is stated once. `model.sdf`, `config.yaml` and
`launch/vehicle.launch.py` carry a one-clause pointer to it rather than a
second copy, because those files already say the safe channel is *derived from*
the measurement scan and a reader there must not infer independence.

## Verification

Two whitespace-normalised sweeps of `agv/`, both scripted rather than by eye
(LESSONS 2026-07-27: a line break sits inside any phrase worth searching for):

1. Every occurrence of `PLCSIM` / `F-DI` / `F-I/O` / `Advanced API`, each hit
   tested for a conditionality marker within its paragraph:
   **28 occurrences, 0 bare.**
2. The two stale subjects — the evaluator co-occurring with the navigation
   lidar in one sentence, and any "scanner … no consumer" claim:
   **0 hits remaining in `agv/`.**

Observed and deliberately left: `EVIDENCE_SENSOR_COVERAGE.md:108` still opens
*"Range max 8.00 m on the navigation lidar is coupled"* — but that is a dated
evidence claim whose correcting note (*"the mechanism of that coupling has
changed, the conclusion has not"*) sits eight lines below it, which is this
project's own in-place correction discipline. Rewriting the original claim
would rewrite a dated record.

## Open questions

1. **The fallback's cost is still unwritten, and it is not `agv/`'s to write.**
   ADR 0011 D2 says the fallback "requires building nothing and removing
   nothing". After this change that is true of `agv/` — all five sites state
   what survives either verdict. It is not yet true of `docs/PLAN.md:21-23`,
   which judge finding 2 names and which no agent has been briefed to correct.
2. **m5-12's brief needs the same two sentences**, and cannot get them from
   here: the conditional (its deliverable is "OSSD-equivalent channel pairs",
   pair-shaped for an F-DI that exists only on the primary path — finding 2's
   undocumented dependency), and the R7 sequencing (no field may be computed
   over rays that pass through a body the vehicle would collide with).
   `docs/` is outside this write scope.
3. **R7 remains open and now has a second consumer.** Reconciling the mast's
   `<visual>` and `<collision>` representations was already an open question
   for coverage figures; the common-cause guard makes it an input to the field
   design too. Whether it is resolved by adding a visual slab or by narrowing
   the collision box is a model decision this brief did not take.
4. **No new dependency was proposed or added**; the two sweep scripts were
   scratch and are not in the tree.
