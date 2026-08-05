# m5-32 — arrival geometry: derive it, do not tune it

    brief:               docs/briefs/m5-32-arrival-geometry-research.md
    status:              done
    files_changed:
      - agv/forklift/ARRIVAL-GEOMETRY.md                (new — the deliverable)
      - docs/reports/m5-32-arrival-geometry-research.md (this file)
    invariants_touched:  none. No code, no launch file, no configuration was
                         written; no committed value was edited.
    open_questions:      three owner decisions and one interface request (below)
    next_suggested:      brief the Phase 1 implementation (staged approach with
                         go-around) against ARRIVAL-GEOMETRY.md §7 — roughly half
                         a day including the five-repeat evidence run

---

## The result in one paragraph

The satisfiability condition is `xy_tol > R × yaw_tol` (single-arc, small
angle; a necessary condition, never sufficient). Against the vehicle's
measured geometry the committed pair 0.25 m / 0.15 rad **fails it by
1.26–1.56×** at the measured endgame cost of 2.1–2.6 m/rad (margin −0.065 to
−0.140 m), and even at the tightest single arc ever demonstrated (1.291 m,
from model.sdf's L = 1.05 m and ±1.31 rad stop via 23 % measured understeer)
the +0.056 m margin is smaller than the localizer's own position rms — the
paper pass at the 0.280 m mechanical radius is exactly why the pair looked
plausible. The fix that satisfies the owner's ruling is design, not
tolerance: a **staging pose 3.0 m back along the goal heading** (d derived
from 2·√(R·e₀) + one lookahead, all committed numbers), a fresh straight
final leg checked by the untouched tight pair, and a **go-around** on any
miss — never the endgame correction the relation proves cannot terminate.
Verified locally: the committed plan already terminates at exactly the goal
heading (r2 plan artifact), so planning was never the problem; RPP simply
has no terminal-heading authority (literal mutual-exclusion string in the
installed .so). Every mechanism Phase 1 needs — `PositionGoalChecker`,
`GoalCheckerSelector`, per-goal `goal_checker_id` — is in the installed
nav2 1.3.12, and `opennav_docking` 1.3.12 (Nav2's productized form of this
exact pattern, staging + graceful approach + return-to-staging retry) is
**already installed**, so no dependency is proposed for any phase.

## The contract detail, found

`docs/interfaces/vda5050-subset.md` §4 already carries
`nodePosition.allowedDeviationXY` ("Arrival tolerance radius in m") and
`allowedDeviationTheta` ("Arrival orientation tolerance"), and the 2.1.0
spec text says the AGV decides traversal by being within both. The proposal
is fully expressible in the standard: the tolerance pair is the node's
deviation pair, the staging pose is simply the penultimate order node, and
the M6 sensor-guided finish is the predefined `finePositioning` action.
Nothing parallel is invented; M6 gets the design free.

## Predicted effect on the m5-31 distribution (1 clean / 2 recovered / 2 timeout of 5)

Phase 1 reproduces, by construction, the conditions of the two measured
clean arrivals (fresh straight leg, near-zero initial cross-track — every
measured instance of which arrived at 1.5–3.9°, inside the 8.594°
discriminator), and converts any residual miss into one bounded ~30–40 s
go-around instead of a 69–120 s shuffle. Done-when is distributional:
≥4 clean of 5, no shuffle regime in any run (localization max staying
≤ 0.263 m, which also closes m5-31's footprint-padding exposure for the
arrival case), with the arrival-heading column explaining every outcome.
Phases 2–3 move the mechanism to its contractual home and add
station-referenced sensing at M6; neither changes the reliability result.

## Open questions

1. **Owner (Phase 0):** the definition of "reached" — recommended: keep
   0.25 m / 0.15 rad on the final checker and rule that the miss branch is
   a go-around; the alternative (resize until the relation holds) needs
   xy ≥ ~0.5 m and is recommended against.
2. **Owner (Phase 3, M6):** activating `opennav_docking` as a new running
   component, and the perception source for station-local sensing.
3. **Owner/orchestrator:** whether Phase 2 (VDA 5050 deviation-field
   mapping in the client) lands in the M5 tail or waits for the M6 client
   brief; ARRIVAL-GEOMETRY.md §7 works either way.
4. **Interface request (outside agv write scope):**
   `docs/interfaces/vda5050-subset.md` §4 eventually gains one note row
   tying `allowedDeviationXY/Theta` to the vehicle's goal-checker mapping
   and the (A)-relation acceptance rule; and at M6 `finePositioning` moves
   out of the not-supported list. Requested here, not edited.

## Scope

No commit, no branch. Working tree carries exactly the two files above.
Nothing in `agv/` beyond the new document was written; no measurement was
taken beyond reading installed package metadata and committed artifacts
(one plan-terminal-heading read from `evidence/m5-31-a_straight-r2-plan.json`).
Sources are graded in ARRIVAL-GEOMETRY.md §5 with versions and verification
dates; no claim in the derivation rests below grade A (installed source or
this repository's own measurements).
