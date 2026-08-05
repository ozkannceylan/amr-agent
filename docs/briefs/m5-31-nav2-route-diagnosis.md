# m5-31 — why the Nav2 route does not complete on the showcase machine

    gate:                M5 (criterion (d) rests on this)
    agent:               agv-ros2
    goal:                Name the cause of the m5-10 straight route failing on the WSL machine, and say which committed M5 figures still stand on the platform the showcase will run on.
    invariants_touched:  none
    inputs:
      - agv/forklift/EVIDENCE_NAV2.md — **read §0 first**; it states its own environment
      - agv/forklift/EVIDENCE_LOCALIZATION.md, EVIDENCE_ODOMETRY.md
      - agv/forklift/nav2.yaml, launch/navigation.launch.py, scripts/cmd_vel_to_tricycle.py, scripts/nav2_run.py
      - agv/forklift/EVIDENCE_VEHICLE_IMAGE.md (m5-24's run, where the failure was seen)
      - sim/setup/WSL_ENVIRONMENT.md §12.5 and its new Part III
      - docs/reports/m5-24-vehicle-image-phase1.md, m5-26-dist-upgrade.md
      - docs/TODO.md — the blocker entry, and the measured numbers section
      - docs/LESSONS.md
    deliverable:         the diagnosis in agv/forklift/EVIDENCE_NAV2.md (a new dated section, existing content untouched) and docs/reports/m5-31-nav2-route-diagnosis.md
    done_when:           The cause is named and demonstrated, not hypothesised; and each committed Nav2 and localization figure is marked as still standing, superseded by a new measurement, or unverified on this platform.
    forbidden:
      - tuning anything to make the route pass before the cause is named — a green run with an unknown cause is worse than a red one, because it will come back at the showcase
      - editing the committed sections of any EVIDENCE file; add a dated section, never overwrite a measurement
      - running while another agent holds the machine (LESSONS 2026-07-30) — check, and say what you checked
      - claiming a figure still stands because it is plausible; either it was re-measured here or it is marked unverified

---

## 1. The facts, and the one that should shape the hypothesis

| | committed (m5-10) | 2026-08-05 (m5-24) |
|---|---|---|
| outcome | **SUCCEEDED in 13.40 s** | **TIMEOUT at 90 s** |
| final | 0.183 m absolute | 0.628 m |
| host | project session container, **4 cores**, headless | WSL, **20 cores** |
| nav2 | 1.3.12 | 1.3.12 |

**This was first written up as a regression and it is not one.** `EVIDENCE_NAV2.md`
§0 says in its own environment block that nothing in it had been reproduced on
the WSL machine. So 2026-08-05 is the **first attempt on the showcase platform**,
and it failed. The package hypothesis is dead beside it: the Nav2 version is the
same on both sides.

**The clue worth starting from**: the machine that *succeeded* had **fewer**
cores. This is unlikely to be a compute shortage, which makes timing, rates and
the simulator's real-time factor the first places to look, not the last.

Note the machine changed again on 2026-08-05 (m5-26 brought it current with the
archive), so **re-measure the current failure before diagnosing it** — you are
not debugging m5-24's run, you are debugging today's.

## 2. How to work this

Load the `superpowers:systematic-debugging` skill and follow it. In particular,
form the hypothesis before the fix and make each experiment able to **falsify**
something.

Candidate directions, offered so you do not start cold — not a list to work
through, and not exhaustive:

- **real-time factor and controller rate.** If the simulator runs at a different
  RTF than it did, the controller's wall-clock period no longer matches its
  simulated one. Measure the RTF and the controller's actual iteration rate,
  not its configured one.
- **the route itself.** Does the planner produce a plan at all, and the same
  plan? Is it the controller failing to follow, or the planner failing to plan?
  Those have nothing to do with each other and the answer splits the search in
  half at one step.
- **the tricycle conversion.** LESSONS 2026-08-04: a motion check that does not
  retrace its segments cannot tell a followed arc from a blocked one. Whatever
  you measure, carry a speed-achievement column.
- **localization.** Is AMCL converged and staying converged, or is the route
  failing because the vehicle does not know where it is?
- **the goal checker and the tolerance.** TODO records that goal tolerance
  0.25 m sits below the vehicle's own manoeuvring granularity, and that one
  attempt in four already shuffled 240 s at 0.335 m out — **on the platform that
  passed**. A shuffle that used to resolve may now not.

## 3. The second half of the deliverable

Once the cause is named, go through the committed figures and rule on each:

- the m5-10 Nav2 figures (the four cases, the reverse divergence, the refusal);
- the m5-08e localization figures (rms 0.124 m, max 0.263 m, the 0.141 m floor);
- anything else criterion (d) would cite.

For each: **still stands on WSL** (re-measured — give the number), **superseded**
(give both), or **unverified on this platform** (say so plainly). Criterion (d)
currently rests on container evidence the showcase platform contradicts, and
this list is what replaces that situation with a known one.

If the honest answer is that the route cannot be made to work without a change
that is out of this brief's scope, say that. Naming the fix is as valuable as
making it, and a fix applied without the cause understood is not a fix.

## 4. Working discipline

- **Write into the evidence as each measurement lands.** Create the dated section
  with its headings before your first run.
- **Measure alone**, and record when you ran.
- **Do not commit.** The orchestrator commits by pathspec.
- Read `docs/LESSONS.md` first.
