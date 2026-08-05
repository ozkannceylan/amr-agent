# m5-35 — build ARRIVAL-GEOMETRY.md §9, and measure it

    brief:               the m5-35 dispatch prompt (no file in docs/briefs/)
    status:              done — built exactly as §9 specifies, measured over
                         five repeats, and the done-condition is NOT MET on
                         two of its three criteria. Reported as measured.
    files_changed:
      - agv/forklift/config.yaml                    (creep_speed_mps 0.02 -> 0.005,
                                                     the window derivation written in
                                                     as a formula)
      - agv/forklift/scripts/nav2_run.py            (the §9.5 miss detector; the §9.3
                                                     staging-stop heading instrumented)
      - agv/forklift/scripts/cmd_vel_to_tricycle.py (one docstring example that quoted
                                                     the old band)
      - agv/forklift/EVIDENCE_NAV2.md               (new section 10; sections 0-9
                                                     byte-identical, git diff --numstat
                                                     = 446 added / 0 deleted)
      - agv/forklift/evidence/m5-35-a_straight-r{1..5}-*   (new) the five repeats
      - agv/forklift/evidence/m5-35-creep-bench.txt        (new) the pre-run bench
      - docs/reports/m5-35-heading-forcing-build.md        (this file)
    invariants_touched:  none. Every change is inside agv/, below the
                         smoother, in the process command chain. No safety
                         path, no tolerance, no layer boundary, no
                         dependency. plc/ was not touched.
    open_questions:      four, listed below
    next_suggested:      one brief that MEASURES the cross-track rate on a
                         straight leg (understeer at small steer angles) —
                         not a tuning brief, and not another arrival-geometry
                         brief

---

## 1. The result, in one paragraph

§9 was built as written — the derived creep value, the 4.5 m leg, the miss
detector, the staging-heading column — and the five repeats say the design
**fixed what it derived and missed what it predicted**. The terminal stall is
gone by derivation and by measurement (**0 of 5** runs stalled, against 1 of
5), the shuffle regime is gone (**0 of 5**), and the miss detector fired
three times without costing a single clean run. But clean traverses went
**3 of 5 down to 2 of 5**, and localization max went 0.1186 m up to
**0.4565 m**, so two of the three done-conditions are **NOT MET**. The
mechanism is new and it is measured, not inferred: the failing runs neither
stall nor shuffle nor start badly aligned — **they drive out of the
corridor**, holding a few degrees of heading offset for the whole leg, so the
lateral error accumulates at about 0.10 m per metre travelled. That makes
`d` the wrong lever: **4.5 m buys 50 % more cross-track than 3.0 m did**, and
terminal cross-track above the 0.25 m tolerance separates clean from
not-clean **10 times out of 10 across both sets**.

## 2. The deadlock — checked, not assumed, and the check is the deliverable's spine

The brief required an explicit statement that no pair of floors was left in
the deadlock relation. **The whole chain was read stage by stage** and the
table is in `EVIDENCE_NAV2.md` §10.0 (b). The only deadband that zeroes
traction is the converter's creep, now **0.005 m/s**, and it sits below the
smallest command the layer above it can form from rest,
`a_w·Δt / κ_max = 0.02381 / 3.569 = 0.00667 m/s`; the refusal threshold
(0.002) sits below that again; `forklift_io.py` has a symmetric clamp and no
deadband; the gz joint controller has none; the envelope gate's only
threshold lives inside its stop ramp and the gate is not in this chain.
**No pair of floors stands in the deadlock relation after this build.** The
one floor left unmeasured is the plant's own breakaway, which is not a
parameter of ours, and the instrument for it is falsifier 2 read in its
discriminating form.

Two independent confirmations, both in the evidence:

- **The bench, before any simulator** (`m5-35-creep-bench.txt`): the real
  converter node fed the smoother's own from-rest output at r1's recorded
  steer of 1.072 rad. Predicted 0.0136 m/s, measured **0.01362 m/s**;
  committed deadband publishes **+0.00000 m/s** of traction, changed deadband
  **+0.02847 m/s**, refusal counter 0 in both.
- **The recordings, m5-33 against m5-35**: under the committed deadband r1
  commanded **857 samples** into the 0.005-0.02 m/s band and **not one**
  reached the plant, with truth frozen for 19.8 s and three further windows;
  under the changed deadband, across all five runs, **not one freeze of ≥ 5 s
  occurs** and the band's samples produce traction.

One correction to §9.7 worth recording: **falsifier 2 as literally worded**
("truth frozen ≥ 5 s with nonzero `cmd_v`") **fires on the m5-33 recording it
was written from**, because in the deadlock `cmd_v` was nonzero and the
traction was zero. The form that discriminates has the *converter's output*
in it, and both are reported side by side rather than quietly substituted.

## 3. The predictions, scored — including the ones that failed

Full table in `EVIDENCE_NAV2.md` §10.5.

| §9.7 registered | verdict |
|---|---|
| 5 of 5 first-approach clean | **WRONG** (2 of 5) |
| r4-analogue clean at ≈ +7 deg — the settling model's own test | **WRONG**; three runs entered at +17.12, +27.46, +33.37 deg |
| r1-analogue: no stall anywhere | **RIGHT**, 5 of 5 |
| a miss aborts immediately and completes via one go-around | **HALF RIGHT**: every abort fired at the first in-circle sample; no go-around ever produced a clean arrival |
| localization ≈ 0.12 m | **WRONG**: 0.114-0.457 m, three runs breach the criterion |

Falsifiers: **1 fired** (the §9.4 settling model is falsified), **3 fired**
(r5's re-approach entered at +34.14 deg against its own first attempt's
+17.12 deg, so the §9.2 capacity argument is falsified), **2 did not fire**
(§9.1's derivation stands), **4 did not fire** (the §9.5 abort thresholds are
sound and cost no clean run).

**And the §9.3 instrumentation earned its place.** Falsifier 1 firing left the
open question "is the variance inherited at staging or generated on the
leg?", and the new column decides it: the **worst** staging heading of the
set (r3, −9.55 deg, its whole tolerance spent laterally) arrived **clean**,
and the **best** (r5, +0.56 deg, on the axis) missed by 17 deg. There is no
relation. **The variance is generated on the final leg.**

## 4. What the distribution says, and what remains

| criterion | result | verdict |
|---|---|---|
| ≥ 4 of 5 clean | **2 of 5** | **NOT MET** |
| no run in the shuffle regime | **0 of 5** | **MET** — partly by construction, as §9.5 declared in advance |
| localization max ≤ 0.263 m | **0.4565 m** (r4 0.4045, r5 0.3698 also breach) | **NOT MET** |

**It does not close, and nothing was tuned to reach it.** `xy_goal_tolerance`
0.25 and `yaw_goal_tolerance` 0.15 are byte-identical to their committed
form. What remains:

1. **The cross-track rate on a straight leg**, which is a *controller*
   question and the first one in this line of work that is. It must be
   measured (understeer at small steer angles; converter fidelity at small
   commands; RPP has no cross-track term) before anything is changed.
2. **`d` is not the lever and 4.5 m is worse than 3.0 m** — the error
   integrates along the leg, so the shorter leg should be restored unless a
   cross-track fix lands first.
3. **The go-around needs a plannable start**, not just a heading: three legs
   died on the planner's `"Start occupied"` because a miss leaves the vehicle
   in a pose the global costmap scores as occupied.

## 5. Scope and discipline

No commit, no branch; the working tree carries the changes for the
orchestrator's pathspec. **`plc/` was not touched** — the owner's files there
are untouched by this session. No dependency was added and `opennav_docking`
was not activated. `nav2.yaml` and the behaviour tree are byte-identical.
Sections 0-9 of `EVIDENCE_NAV2.md` are byte-identical (446 added / 0
deleted), the dated §10 with its headings was written **before the first run
was started**, and every run's row was appended the moment that run existed,
before the next was launched.

Every run was measured alone and the driver enforced it rather than the
operator remembering it: it refuses to start if anything matching the
simulator/Nav2 process patterns is running, records load, `/dev/shm` count
and a UTC timestamp before, gates each bring-up stage on a topic appearing,
and verifies the process count after. **All five runs started with zero
matching processes and ended with zero.** `GZ_PARTITION` and `ROS_DOMAIN_ID`
were both isolated on every run. Per-run starting load is recorded in §10.3
because it is the one between-run difference this session did not control;
it does not order the outcomes. `/dev/shm` grew from 165 to 183 orphaned
Fast-DDS segments over the session, left in place; no figure depends on them.

The pre-registered shuffle test was **not** re-tied to the new creep value.
Its deadband stays 0.02 m/s so that the definition does not move between the
runs it compares, and the cost of that choice is stated in the code and in
§10.1 rather than hidden.

## 6. Open questions

1. Whether the next brief measures the cross-track rate or first restores
   `d = 3.0`. On this evidence they are separable and the measurement should
   come first, but the ordering is the orchestrator's call.
2. The pre-existing planner warning `inflation radius (0.550000) is smaller
   than the circumscribed radius (2.230050)` is logged on every run, slows
   SE2 collision checking, and plausibly contributes to `"Start occupied"`.
   It has never been ruled on and is outside this brief.
3. Whether the miss detector should be lifted into the VDA 5050 client at M6
   as §9.5 intends, given that its abort half worked exactly as designed
   while the retry it hands off to has now failed twice for two different
   reasons.
4. `docs/LESSONS.md` (I cannot write it), two entries earned here:
   - *2026-08-05 | A staged arrival was made deterministic by lengthening the
     final leg, on a linearised pure-pursuit model in which entry-heading
     error decays with tail length | The heading may decay but the LATERAL
     error integrates: the vehicle held a few degrees of offset for the whole
     leg, so cross-track accumulated at ~0.10 m per metre and 4.5 m bought
     50 % more of it than 3.0 m did — clean traverses fell from 3 of 5 to 2 of
     5 | Before lengthening a leg to let an error settle, measure whether the
     error is a decaying transient or a rate; a rate integrates along exactly
     the distance you added.*
   - *2026-08-05 | A falsifier was registered as "ground truth frozen ≥ 5 s
     with nonzero cmd_v" | It fires on the very recording it was derived
     from, because in that deadlock cmd_v was nonzero and the traction was
     zero — the discriminating quantity was one stage further down the chain
     | A falsifier names the signal at the stage where the two hypotheses
     actually differ; write it against the consumer's view, not the
     commander's.*
