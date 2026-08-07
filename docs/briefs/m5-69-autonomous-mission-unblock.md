# m5-69 — make an autonomous mission run

    gate:                M5
    agent:               agv-ros2
    scope grant:         agv/, plus the spawn pose wherever it is defined (sim/launch/ if that is where it lives) — owner-approved, this brief only, and named in the report
    goal:                Get a Nav2 mission to plan and drive, so items 2 and 5 of the re-validation can be measured and the autonomous drive can be recorded.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-68-revalidation.md — items 2 and 5, and the diagnosis
      - docs/VALIDATION-M5.md — what is now proven on the safety side, and what is not
      - agv/forklift/EVIDENCE_NAV2.md — especially §0's environment qualifier and §8.6's ruling on which committed figures still stand
      - agv/forklift/nav2.yaml, agv/forklift/launch/, sim/launch/forklift_bringup.launch.py
      - docs/TODO.md — the Nav2 route diagnosis of 2026-08-05 (m5-31) and the autonomy backlog
      - docs/LESSONS.md
    deliverable:         the fix, and a dated section in agv/forklift/EVIDENCE_NAV2.md
    done_when:           A mission is issued, planned, and driven to completion on the showcase platform, repeated enough times to state a success rate rather than a single draw.
    forbidden:
      - loosening a safety-relevant setting to make the route work. In particular allow_unknown stays false unless you can show the change is correct rather than convenient
      - touching TIA, the F-program, or anything under plc/
      - editing bridge/ or hmi/
      - claiming or implying an achieved PL, Category, SIL or PFH
      - reporting a single successful run as a success rate

---

## 1. The diagnosis you are starting from

m5-68 found that items 2 and 5 fail for a reason **off the safety layer**: the
committed spawn pose sits at the **corner of the committed grid**, so
`SmacPlannerHybrid` with `allow_unknown false` published **0 plans in 100 s**,
with no safety demand forming at all — the vehicle never moved, so there was
nothing for safety to act on.

A second attempt from a map-interior pose could not be issued: **the action
server had died under load.**

Two problems, then, and the second may be the harder one.

## 2. The first is a geometry problem, so fix it as one

Do not start by changing planner parameters. Start by establishing where the map
actually covers and where the vehicle actually starts, and show the two against
each other. If the spawn pose is outside or on the boundary of the known region,
that is the defect, and moving the vehicle into the map is the honest fix.

**`allow_unknown` stays `false`** unless you can demonstrate the change is
correct rather than convenient. A planner permitted to route through unknown
space on a vehicle carrying safety claims is a decision, not a tuning step — if
you believe it is right, argue it and let the owner rule.

## 3. The second is a robustness problem and it is real

The action server dying under load is not incidental — it is what stopped the
recovery attempt, and a showcase recording cannot survive it. Find out what
died and why. If the cause is resource contention on this machine, say so with
numbers; ADR 0016's phase-4 measurement work is the place that question already
lives.

## 4. What "done" means here, and it is not one green run

This project has been burned precisely here. `EVIDENCE_NAV2.md` §8.6 records
that the committed 13.40 s figure was **one draw from a distribution straddling
the acceptance criterion** — five repeats gave 1 clean traverse, 2 completions
after 69–94 s of recovery, and 2 timeouts. The container's own history was
1 success in 4 at identical parameters.

So: **repeat, and state the rate.** A single completion is an illustration. If
the rate is poor, that is the result — the owner has ruled autonomy a prototype
and a stated backlog is acceptable; a fabricated success rate is not.

## 5. Remember what this unblocks

Item 5 — safety acting during an autonomous run — has **never been observed**.
It is the last unmeasured item of the owner's original five, and it needs a
mission that actually drives. Get the mission working; the safety measurement
is a separate run and not yours.

## 6. Working discipline

- Read `docs/LESSONS.md` first, and `EVIDENCE_NAV2.md` §0 before quoting any
  existing figure — several are platform-qualified and do not transfer.
- Write the evidence as it lands. Every figure states its n.
- **Do not commit.** The orchestrator commits by pathspec.
