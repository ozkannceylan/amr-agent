# m5-39 — plant-change inventory, before the edit

    brief:               docs/briefs/m5-39-plant-change-inventory.md
    status:              done — every committed motion figure classified,
                         re-measurement ordered by criterion, owner-only
                         items named with what each needs. model.sdf is
                         unedited (line 1002 still 6000.0) and no
                         simulator ran.
    files_changed:
      - agv/forklift/PLANT-CHANGE-INVENTORY.md   (new — the deliverable)
      - docs/reports/m5-39-plant-change-inventory.md  (this)
    invariants_touched:  none
    open_questions:      four, below
    next_suggested:      m5-40 applies the one-line change AND rewrites the
                         steer-plugin comment block (its i_max argument and
                         the falsified "scrub disappears once rolling"
                         claim are stated against the old gain), then runs
                         the committed-tree stamp run (inventory §4 row 0)

---

## 1. The headline findings, in the order they matter

1. **The brief's premise about the M4 recording is partially stale, in
   the cheap direction.** The formal M4 showcase recording **does not
   exist yet** — roadmap and PLAN both say M4 *closes on* it, and TODO
   still owes "Run T5.1–T5.6 … then record the showcase". What exists on
   the prior plant is the *informal* owner video of 2026-07-30 (outside
   the repo, named informal in TODO) plus TIA/HMI captures that carry no
   vehicle-motion figure. So the honest edge is an **ordering
   constraint, not a qualification problem**: land m5-40 before the
   owner records, and the recording certifies the tree — which is
   exactly the owner's standing ruling (TODO, judge finding 7: the
   showcase "is made against the CURRENT tree"). If the owner holds
   recorded material the repo cannot see, the options stand as the brief
   states: re-record (one owner session, procedures already exist) or
   qualify (one paragraph, but leaves gate evidence contradicting the
   current-tree ruling). Re-recording is the consistent one.

2. **The criterion-facing re-measurement is largely already in hand.**
   m5-38 §11.6's five repeats ran on an experimental model equal to the
   ruled change (one diffed line): 5/5 clean, no shuffle, localization
   max 0.1523 m, cross-track rate 0.0134 m/m. Recorded as in hand, not
   scheduled. One formality is owed: those runs used `model:=` to
   override the committed file — after the edit, one run of the
   committed tree (or an explicit diff-identity note in §11) makes them
   figures *of the tree*.

3. **Most committed figures are unaffected, and each entry says why.**
   Sensor coverage/TF (stationary or geometric), odometry drift §§1–12
   (steer commands only 0 and ±20.1°, both in the proven-executing
   regime; the file's own closed-form reconciliations show the figures
   are error-model and bias properties), the envelope gate (every
   scenario at w = 0; traction figures), the map and its 0.141 m floor
   (a frozen artifact scored in its own right), pass-through residuals
   (design properties), the planner bench (deterministic, never sees
   the plant), all PLC/HMI/bridge evidence (no plant in the loop).

4. **The genuinely affected agent-re-measurable set is short**, ordered
   in inventory §4: Nav2 cases B/B′/C/D (B′ first — its "reverse
   diverges at ~2.4 m" n=1 conclusion may be a deadband artefact, and
   TODO quotes it), the footprint_padding re-derivation (the standing
   TODO item, now unblocked because the shuffle regime vanished on the
   new plant), §3.3 convcheck (nav2.yaml's steer-reserve cites its
   23 %), EVIDENCE_ODOMETRY §13's per-stop relaxation cost (the n=1
   dwell bound TODO carries), LOCALIZATION cases (a)/(b) (the converge
   driver is open-loop through the plant by construction), and
   VEHICLE_IMAGE proof 3 (one composition run; the distribution half is
   superseded by m5-38).

5. **Exactly one figure is UNCLEAR**, and it is a finding about the
   evidence, not about the plant: `sim/worlds/FORKLIFT_ARENA_EVIDENCE.md`
   §5 measured 4.0 rad/s → **0.480 m/s** in the arena, while m5-38
   measured **5.000 rad/s → 0.005 m/s** in the same arena, twice. Two
   committed measurements of one world contradict each other and no
   reading of either file resolves it. The sim/ traction ruling must
   reconcile §5 before it rules.

## 2. Files outside my scope that this work needs — requested, not created

- **`sim/`** (carried from m5-38 per the brief, sharpened by finding 5):
  the arena-floor traction finding (5.000 rad/s commanded against
  0.005 m/s achieved) needs a ruling by the agent that owns the world —
  and that ruling must first reconcile FORKLIFT_ARENA_EVIDENCE §5's
  contradicting 0.480 m/s measurement.
- **`sim/`** (carried from m5-38): `model.sdf`'s documented claim that
  the scrub disappears once the vehicle rolls is falsified by m5-38's
  bench. The prose itself lives in `agv/` and m5-40 rewrites it; the
  sim/ half is that FORKLIFT_ARENA_EVIDENCE §6's steer-settle figures
  describe the old plant and need a supersession note or a re-run after
  m5-40 (inventory §2.1).
- **`sim/`** (carried from m5-38): `warehouse_bringup.launch.py` should
  forward a `model` argument explicitly rather than relying on the
  unscoped launch configuration m5-38 exploited.
- **`plc/` and `sim/scenarios/`**: the existing m5-06 instrument-change
  note obligation (TODO) gains a second line — the steer-gain change —
  so the M4 evidence and scenario procedure say which plant the
  recording certifies. Both files are outside agv/.
- **TODO/PLAN (orchestrator)**: the measured-numbers block quotes three
  figures this inventory touches — the 0.263 m localization max (padding
  source; superseded twice, re-derivation scheduled), the reverse
  divergence at ~2.4 m (B′, re-measure first), and the 0.33°/stop dwell
  observation (already n=1-flagged; re-measure once on the new plant).

## 3. Open questions

1. Whether the committed-tree stamp for m5-38 §11.6 is one re-run or a
   recorded diff-identity note (inventory §4 row 0). Either is honest;
   the re-run is stronger and cheap.
2. Whether the owner wants EVIDENCE_MODEL §2.1 retaken or (recommended)
   superseded by a third dated note in the file's own established style.
3. Whether p_gain 60000 gets an upper bracket sweep before the M5
   showcase (m5-38 open question 3 — the stability ceiling is inferred
   from absence of hunting, not from a sweep). Not scheduled by this
   inventory; it is a bench-only run if wanted.
4. Whether the informal 2026-07-30 owner video needs its prior-plant
   qualifier anywhere beyond TODO's citation of it (it appears nowhere
   else in the repository that a sweep by its filename finds).
