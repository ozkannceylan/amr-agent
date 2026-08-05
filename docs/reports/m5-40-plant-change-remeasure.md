# m5-40 — the steer-gain change applied, and what it re-measures

    brief:               the m5-40 dispatch prompt (no file in docs/briefs/);
                         agv/forklift/PLANT-CHANGE-INVENTORY.md is the authority
                         for what is re-measured and in what order
    status:              done — the change is applied with its comment rewritten,
                         and every item the brief named is measured, in the
                         inventory's order. Two items below that list
                         (EVIDENCE_LOCALIZATION cases a/b, EVIDENCE_VEHICLE_IMAGE
                         proof 3) are NOT done and are named below.
    files_changed:
      - agv/forklift/model.sdf                    steer p_gain 6000 -> 60000
                                                  and the comment block rewritten
                                                  (56 added / 12 deleted; exactly
                                                  one changed XML element)
      - agv/forklift/scripts/nav2_run.py          one restored import (8 / 0);
                                                  `goal` had raised NameError at
                                                  every invocation since m5-33
      - agv/forklift/EVIDENCE_NAV2.md             new section 12 (append-only,
                                                  588 added / 0 deleted, one hunk)
      - agv/forklift/EVIDENCE_ODOMETRY.md         new section 14 (append-only,
                                                  220 added / 0 deleted, one hunk)
      - agv/forklift/EVIDENCE_MODEL.md            third supersession note in the
                                                  file's own style (22 / 0)
      - agv/forklift/evidence/m5-40-*             11 runs' artefacts (CSV, plan
                                                  JSON, run and analyse text);
                                                  the two 220 s idle recordings
                                                  gzipped after their writers were
                                                  confirmed gone
      - docs/reports/m5-40-plant-change-remeasure.md   (this)
    invariants_touched:  none. Everything measured or written is inside agv/,
                         below the smoother, in the process command chain. No
                         safety path, no tolerance widened, no layer boundary,
                         no dependency. plc/, bridge/ and sim/ were not touched.
    open_questions:      seven, listed in section 6
    next_suggested:      one brief for RPP's missing reverse reference point —
                         the plant change un-masked it and it is now the binding
                         defect for any M6 route that reverses

---

## 1. The change, and the comment

`model.sdf` steer `p_gain` **6000.0 -> 60000.0**. `git diff -U0` shows
exactly one changed XML element; `i_gain`, `d_gain`, `i_max`, `i_min`,
`cmd_max`, `cmd_min`, joint damping, geometry, masses, sensors and every
topic name are untouched, and the mast joint already ran 60000 so the
model's gains stay in one family. The file still parses and holds no
non-ASCII byte.

**The comment block was rewritten, not only the number**, as the inventory
required. It now states `e* = M_scrub / p_gain = 400 / 60000 = 0.38 deg`
as the smallest promptly executable steer correction, says why 60000 with
the measurement cited, carries two honest limits (no upper bracket was
swept; the residual below 0.5 deg is settling, not a dead region), names
the falsified claim **as falsified** — the scrub does not disappear when
the vehicle rolls, the variable is grip — and says what `i_max` now
carries, since its 800 N·m sizing was argued against a gain the file no
longer has.

## 2. What was re-measured, in the inventory's order

Eleven simulator runs, each on a machine verified empty before it started
and empty after teardown, both transports isolated per run.

| # | item | result |
|---|---|---|
| 0 | **committed-tree stamp** | REACHED clean, 0 go-arounds, no shuffle, localization max **0.1083 m**, cross-track rate **+0.0007 m/m** — inside the band of m5-38's five on every column. Section 11.6 no longer rests on a `model:=` override. |
| 2 | **case B-prime**, 6 m astern, run first | **The conclusion moves, and not the way the brief guessed.** New plant: SUCCEEDED, 57.59 s. Old plant, same machine, same tree, one variable: **ABORTED 104**, reproducing section 5.2's container result including its onset distance. |
| 2 | **case B**, 2 m astern | Both plants SUCCEED. Tracking rms **0.0010 m old / 0.0206 m new** — 20x worse on the new plant. |
| 2 | **case C**, degenerate stretch | SUCCEEDED 11.41 s, tracking rms 0.0423 m against the committed 0.0730 m; arrival 0.2009 m against 0.1503 m, both within the instrument. |
| 2 | **case D**, the refusal | ABORTED **207** after 59.84 s; **the vehicle never moves** — 597 samples, 0.000 m, final pose the spawn pose to six decimals. |
| 3 | **`footprint_padding` re-derivation** | Pooled new-plant localization max **0.2056 m** over 2413 samples, nine drives -> 0.21 m by section 4's own rule. **The committed 0.27 stands and is not changed.** |
| 4 | **convcheck** | Worst understeer **23.00 % -> 14.43 %**. `nav2.yaml`'s steer reserve re-derives to **25.8 deg** against the file's claimed 30. |
| 5 | **post-drive steer relaxation** | Steer sweep over a 220 s idle **2.3730 deg -> 0.1758 deg**; gate openings 9 -> 1; estimator error while the wheel is parked **-0.382 deg -> -0.001 deg**, a factor of 308. |

## 3. The three findings worth more than the re-measurement

**(a) B-prime's reverse divergence is NOT a deadband artefact, and the
plant change un-masked a defect rather than fixing one.** A one-variable
A/B — same machine, same tree, `model:=` the byte-verified HEAD file —
reproduces section 5.2's `ABORTED 104` on the old plant, with divergence
onset at 2.745 m against the committed "about 2.4 m". On the new plant the
heading still runs out, and further (-51.5 deg against +44.4); what changes
is that the vehicle recovers by replanning and arrives, at 12.470 m of
travel for a 6.106 m plan. Case B says the same thing from the other side:
a 2 m straight reverse from an aligned pose is a route where doing nothing
is the correct trajectory, so a frozen steer axis **flattered** it, and the
committed 0.0009 m tracking figure is the tightest in the file for a reason
that has nothing to do with control quality. **Section 5.2's diagnosis —
RPP has no reverse reference point or lookahead on a vehicle whose steered
axle trails — is not weakened by the plant change; it is the item the plant
change makes visible, and it is now binding for M6.**

**(b) `nav2_run.py goal` has been dead since m5-33.** The first attempt
raised `NameError: name 'NavigateToPose' is not defined` before sending a
goal: the import was lost when the recorder was factored into
`_build_recorder`, `cmd_stage` kept its own copy and `cmd_goal` did not.
Every section from 8 onwards is a `stage` run, which is why nothing caught
it, and the section 5 cases were last driven before the refactor. One line
restored, at the site that uses the name. A second, softer trap in the same
path is recorded and **not** fixed: `cmd_goal`'s settle loop exits the
instant TF first appears, so the goal stamp can predate AMCL's earliest
transform and `bt_navigator` aborts in 0.2 s with "Initial robot pose is
not available".

**(c) The per-stop steer relaxation is a plant effect, measured as one.**
The old plant reproduces its own container figure on WSL to four decimals
(steer sweep 2.3730 deg both times), which retires section 13's
container-only caveat, and leaves the plant as the only variable between
the columns. The inventory called the direction unknown and refused to
predict it; it creeps less, by two orders of magnitude, and the settling
window shrinks from ~16 s to under 1 s with what remains being the
vehicle's own coast.

## 4. Discipline

**Every dated section's headings were written before the run that fills
them**, and results were appended as each run landed, before the next was
launched. **No committed measurement was overwritten**: all three evidence
edits are pure appends — `git diff -U0` gives one hunk per file with
**0 deleted lines** (`EVIDENCE_NAV2.md` +588, `EVIDENCE_ODOMETRY.md` +220,
`EVIDENCE_MODEL.md` +22 as a third supersession note in the file's own
style).

**Measured alone, enforced by the driver.** Every run refuses to start
unless the process-pattern count is zero, prints load, `/dev/shm` count and
a UTC timestamp, gates each bring-up stage on a topic appearing rather than
on a sleep, prints the committed model's `<p_gain>` lines so each artefact
records its own plant, and verifies the count after teardown. All eleven
runs started at zero and ended at zero. `GZ_PARTITION` **and**
`ROS_DOMAIN_ID` were both set, distinct per run.

**Two incidents recorded rather than tidied away**, both in `EVIDENCE_NAV2`
12.8. A `b-oldplant` launch was issued twice; the guard counted 15
processes and correctly refused the second, but the second's redirect
truncated the first's log under a live writer — the run was **discarded,
not repaired**, and re-run alone. And `pkill -f "gz sim"` from an
interactive shell kills the shell, because the shell's own command line
contains the pattern.

**A run that measured nothing is kept as what it is.** The first convcheck,
spawned in an aisle, came back with three segments at 46-82 % of commanded
speed and the harness's own HELD warning; its 147.94 % radius error is the
arithmetic of a blocked vehicle. It is committed, labelled not a conversion
measurement, and the re-run spawns at the most open cell in the committed
grid instead of guessing again.

**Nothing was widened or tuned.** `xy_goal_tolerance: 0.25` and
`yaw_goal_tolerance: 0.15` are untouched; section 12.6 checks both against
their own derivations and changes neither. `nav2.yaml`, `amcl.yaml`,
`ekf.yaml`, `config.yaml`, the behaviour tree, both launch files,
`cmd_vel_to_tricycle.py`, `envelope_gate.py`, `forklift_io.py` and
`wheel_odometry.py` are byte-identical. No dependency was added. No commit,
no branch.

## 5. Files outside my scope this work needs — requested, not created

- **`sim/`**, unchanged from the inventory and deliberately not resolved
  here: `FORKLIFT_ARENA_EVIDENCE.md` §5's traction pulse still contradicts
  m5-38 §11.3 (b), and §6's steer step still describes the old plant.
- **`docs/LESSONS.md`** (I cannot write it), three entries earned here:
  - *2026-08-05 | A plant defect was removed and the two committed reverse
    cases were expected to improve | Case B got 20x WORSE (tracking rms
    0.0010 -> 0.0206 m) because a 2 m straight reverse from an aligned pose
    is a route where doing nothing is correct, so a dead actuator had been
    flattering it, and giving the axis authority let an unstable reverse
    pursuit loop act | A fix can un-mask a defect as easily as remove one:
    when an actuator's authority is restored, re-measure the cases where
    NOT acting was accidentally the right trajectory, because their
    committed figures are the ones that will get worse.*
  - *2026-08-05 | The `goal` subcommand of a committed harness was invoked
    to re-drive four cases and raised NameError before sending anything |
    Its import had been lost in a refactor months of sections earlier; every
    section since had used the sibling `stage` path, which kept its own copy
    at its own call site, so a dead code path sat in a committed tool with
    no test and no user | An import belongs at the site that uses the name,
    and a subcommand that no recent evidence section exercises is untested
    code however committed it looks — re-run it before a brief depends on
    it.*
  - *2026-08-05 | An old-plant A/B was launched twice because the launching
    shell reported a path error that made the first launch look dead | The
    process guard correctly refused the second, but the second's output
    redirection truncated the first's log while the first was still writing
    to it — the open-file hazard of LESSONS 2026-07-28, arriving through a
    redirect rather than a gzip | A guard that protects the machine does not
    protect the log: give every launch attempt its own log name, and treat a
    run whose log was truncated as discarded rather than repaired.*

## 6. Open questions

1. **RPP's missing reverse reference point** (finding a). This is the next
   brief, and it is not a tuning question.
2. **`cmd_goal`'s settle loop** exits one sample too early. Recorded, not
   fixed: whether it should require a minimum TF age is a design decision.
3. **`EVIDENCE_LOCALIZATION.md` cases (a) route and (b) converge are NOT
   re-measured** — inventory item 6, below the brief's named list. The
   inventory rates them low priority and says qualification is acceptable
   meanwhile; the padding derivation in 12.6 states explicitly that it does
   **not** substitute these routes' figures for that file's.
4. **`EVIDENCE_VEHICLE_IMAGE.md` proof 3 is NOT re-run** inside the vehicle
   image — inventory item 7, also below the brief's list. One §9-recipe run
   in domain 51 still owes.
5. **Whether `d` returns to 3.0** (m5-38 open question 2, §10.6 item 2).
   Everything here used 4.5 to keep the comparison one variable; nothing
   measured argues against 3.0 and nothing here tested it.
6. **Whether `p_gain` 60000 is right or merely sufficient** (m5-38 open
   question 3) is unchanged: no upper bracket was swept, and the comment now
   says so in the file.
7. **`PLANT-CHANGE-INVENTORY.md` §5 says "`model.sdf` is unedited (line
   1002 still `6000.0`)".** True of m5-39 and scoped "what this inventory
   did not do", but a reader could take it as current. It is another
   brief's committed deliverable and was left byte-identical; if the
   orchestrator wants it stamped, that is a one-line note by whoever owns
   the correction, not an edit made silently here.
