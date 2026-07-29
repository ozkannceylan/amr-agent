# Report m4f-02b — record the ±45° scan dropout in the vehicle contract

```
brief:               docs/briefs/m4f-02b-scan-dropout-contract.md
status:              done
files_changed:       agv/forklift/README.md
                     docs/reports/m4f-02b-scan-dropout-contract.md
invariants_touched:  none
open_questions:      one, below
next_suggested:      leave the dropout as a documented sensor property unless a
                     consumer is written that cannot absorb a missing ray
```

## What changed

One row. `agv/forklift/README.md`, the `/forklift/scan` row of the ROS
contract table, now states four things and the file changes nowhere else
(`git diff --numstat`: `1 1 agv/forklift/README.md`):

1. The gz `gpu_lidar` drops the single sample at exactly `+-45 deg`.
2. It is the sensor, not the bridge, and the reasons are given rather than
   asserted: the `inf` is already in the raw gz message, it appears in the
   middle of an object returned continuously either side of it, it
   reproduces against a flat wall, and it follows vehicle orientation
   rather than sitting at a fixed index (m4f-03 evidence).
3. A consumer must not assume every sample in this scan is finite.
4. `obstacle_zone.py` already treats it correctly.

## Why point 4 is true rather than convenient

`obstacle_zone.py` was written to judge each sample on its own merits, and
that is what absorbs a dropped ray. Two properties do the work:

- Validity is **affirmative and per sample** — `math.isfinite(sample) and
  range_min <= sample and sample <= range_max`. An `inf` fails the test and
  is skipped. The scan is not condemned for containing it.
- The verdict is the **minimum of the samples that survive**. A missing
  sample can only make the reported distance longer, never shorter, and
  the obstacle-present branch is only reached when *no* sample in the
  sector is valid.

Both are already evidenced. `agv/forklift/EVIDENCE_MODEL.md` §6 includes
the case `one valid among NaN`, which returns `False` at `2.000` — 180 bad
samples and one good one, and the good one is what is reported. The
inverse case, `all samples +inf`, returns `True` at `0.000`. A single
dropped ray is the first case with the ratio reversed.

Two facts that bound the exposure today, both checked rather than
remembered: the stop-zone sector is `sector_half_angle_rad: 0.5236` in
`config.yaml`, which is `+-30 deg`, so the `+-45 deg` seam falls outside
the sector the evaluator reads at all; and the scan carries 181 samples at
one per degree, so the seam costs at most two of them.

## Open question

**The dropout was not reproduced in this task.** It is recorded on m4f-03's
evidence, which is a different world, a different run and another agent's
report. Nothing here re-measured it, and the brief did not ask for that —
but the contract table now carries a claim whose evidence lives outside
`agv/`. If it matters that the vehicle's own evidence file stands alone,
`EVIDENCE_MODEL.md` should gain a dump of all 181 samples against a flat
wall. That is a change to an evidence file the brief's `forbidden` list
does not cover, but it is also not what was asked, so it was not made.

## Notes

- Nothing outside `agv/forklift/README.md` and this report was touched:
  `model.sdf`, both scripts, `config.yaml`, `launch/` and `sim/` were read
  where needed and left alone, as the brief requires.
- No dependency, no code change, no behaviour change. The vehicle software
  is byte-identical to the m4f-02 commit; only its documented contract is
  more honest.
