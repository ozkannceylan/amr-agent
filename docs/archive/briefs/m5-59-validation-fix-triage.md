# m5-59 — triage the validation findings, and write the owner's TIA procedure

    gate:                M5
    agent:               plc
    goal:                Split the four m5-58 findings into what the owner must do at TIA and what an agent can do without it, and write ONE TIA procedure covering every TIA part — so the owner sits down once, not twice.
    invariants_touched:  none expected. If a fix appears to need one, stop and write an ADR proposal.
    inputs:
      - docs/VALIDATION-M5.md and docs/reports/m5-58-full-stack-validation.md — the findings, with the runs behind them
      - plc/forklift/SPEC.md §14 and §14.16, plc/forklift-safety/SPEC.md §11
      - plc/forklift/TIA-BUILD-PROCEDURE.md — the format the owner has already worked through 360 steps of; match it exactly
      - docs/interfaces/opcua-nodes.md §12 and §13
      - docs/reports/m5-57-writer-speed-link.md
      - docs/LESSONS.md
    deliverable:         plc/forklift/TIA-FIX-PROCEDURE.md, plus the triage table in docs/reports/m5-59-validation-fix-triage.md
    done_when:           Every one of the four findings has an owner (TIA or agent) with the reason stated, and every TIA part is a numbered step with one physical action and one observable.
    forbidden:
      - downloading, compiling or changing anything in TIA yourself — this brief WRITES a procedure, it does not execute one
      - editing outside plc/ (the report goes to docs/reports/, which the orchestrator will place)
      - inventing a threshold. Every number is derived and the derivation is shown
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. The four findings

From `docs/VALIDATION-M5.md`. Read the report for the runs; this is the summary.

**F1 — the F-program's SLS and SS1 demands do not reach the vehicle.**
`Forklift/Safety/` publishes four leaves where six are needed, there is no
publisher on the torque-off topic, and no permissive conjunct consumes them.
Measured: the vehicle drove **19 s at 1.000 m/s** with `SpeedMonitorDemand`,
`Ss1Demand` and `TorqueOffDemand` all standing. The e-stop and protective-field
paths *are* coupled and *do* stop it — only SLS and SS1 are orphaned.

**F2 — a threshold band nobody derived, and it is what kills autonomy.**
The motion observation calls the vehicle moving above **1.4 mm/s**; the speed
monitor calls a reading near-zero below **30.8 mm/s**. A healthy vehicle between
the two is diagnosed as a **failed shaft**. Nav2's from-rest speed of 0.025 m/s
= 25 mm/s sits inside the band, which is why **every mission latches in its
first metre**. Reproduced deliberately at a 0.02 m/s creep with the encoders
reading 15–26 mm/s.

**F3 — nothing sends the `WARN` line**, so the F-side limit selector is
permanently occupied.

**F4 — the warning-field ceiling is autonomous-mode only.** In a teleop clip the
scanner therefore **stops** the vehicle instead of slowing it — observed twice
at 1.000 m/s straight through a 3.499 m warning trip. Safe in direction, but it
is not the behaviour the owner asked for: *slow down first, then stop.*

Carried from m5-57 and belonging to you: **`FIELD_LINK_STALE_MAX` = 1 s against
a 1 Hz keepalive has zero margin** — measured, the link was reaped 10 ms before
the fourth keepalive. And the standing debt: **`plc/forklift-safety/SPEC.md` §11
should state 0.40 s**, because the client's 0.15 s motion window stacks on the
writer's 250 ms.

## 2. What this brief must decide

For **each** finding, state the owner and the reason:

- **TIA** — it changes the standard or safety program on the CPU
- **agent** — it lives in `agv/`, `bridge/` or a document

Do not guess. F2 in particular has one threshold plausibly in the F-program and
one plausibly in the vehicle's script; **read both and say which is which**. If a
fix has a TIA half and an agent half, say so and specify each half separately —
that is the normal case here, not an edge case.

**The stakes of getting this wrong are concrete:** the owner has one TIA session
tomorrow. A TIA-side change discovered afterwards costs them a second one.

## 3. F2 is a derivation, not a nudge

The band exists because two thresholds were chosen independently against
different questions. Do not close it by moving one until they touch. Derive:

- what the **motion observation** must actually distinguish, and from what noise
- what the **near-zero** threshold must actually distinguish, and from what noise
- whether a **healthy slow vehicle** can be excluded from the fault region by
  construction rather than by a lucky gap

The vehicle's real from-rest behaviour is measured and available — Nav2 leaves
rest at 0.025 m/s and the encoders read 15–26 mm/s there. Use the measurements.
State the derivation so the next reader can check it, and say plainly what the
new values do **not** cover.

## 4. F4 is a design question, so answer it as one

Ask whether the warning ceiling *should* apply in teleop. The owner's stated
want is that the operator is slowed before being stopped. The counter-argument
is that a commissioning operator with a lowered ceiling may not understand why
the vehicle is sluggish. Recommend one, give the reason, and make the procedure
implement your recommendation — do not leave the owner a choice to make at the
keyboard with TIA open.

## 5. The procedure's shape

`plc/forklift/TIA-FIX-PROCEDURE.md` matches `TIA-BUILD-PROCEDURE.md`'s format
exactly — the owner has worked through 360 steps of it and knows the rhythm:

- one numbered step, one physical action, one observable
- the **starting state** stated: which project, which CPU, what must be running
- the **F-signature before and after**, with a place to record it. Changing the
  F-program changes it, and `docs/VALIDATION-M5.md`'s figures are all against
  `50573CD9` — say which validations must be re-run afterwards
- a **record table** for what the owner reads back
- an explicit **stop point** at the end: what "done" looks like

Keep it as short as it can honestly be. The owner has ADHD and has told us so —
**one action per step, no step that bundles two things**, and no paragraph where
a table would do.

## 6. Working discipline

- Read `docs/LESSONS.md` first.
- If a finding turns out not to be a defect, say so with the evidence. A
  procedure step that fixes nothing wastes the owner's session.
- **Do not commit.** The orchestrator commits by pathspec.
