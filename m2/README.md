# m2/ — Milestone 2: the safety requirements spec

**Closed 2026-07-26, verified PASS (all 8 criteria) in
[`docs/archive/reports/m2-02-verify.md`](../docs/archive/reports/m2-02-verify.md).**

M2 is the milestone that decided what "safe" means for everything built
after it — before any safety code existed. Its deliverables are **live
documents**: the M5 F-programs (both the [first build's](../m5/m5_ver1/PLC-PROGRAM.md)
and the [hand-rebuilt one](../m5_ver2/)) are implementations of this spec,
and every acceptance test cited at later gates traces back here.

| Document | Where | What it is |
|---|---|---|
| Safety requirements spec | [`docs/safety/SRS.md`](../docs/safety/SRS.md) | Nine safety functions **SF-01…SF-09**, each with an ID, a trigger, a quantified reaction, a safe state, a reset behaviour and an acceptance test **AT-01…AT-09** with an explicit pass line |
| ISO 13849 scenarios | [`docs/safety/PL-SCENARIOS.md`](../docs/safety/PL-SCENARIOS.md) | The PL r reasoning per function |
| Standards basis | [`docs/safety/SLS-STANDARDS-BASIS.md`](../docs/safety/SLS-STANDARDS-BASIS.md) | Which standards clauses each function claims descent from |
| Twin/demo map | [`docs/safety/TWIN-DEMO-MAP.md`](../docs/safety/TWIN-DEMO-MAP.md) | How each function is demonstrated on the simulated plant |

## The honesty boundary this gate set

The SRS separates **design intent** (PL d / Cat 3 targets derived from
the documented risk assessment) from **certified claims** (none — the
project is hardware-free). That boundary, later quoted as ADR 0011 D5,
is why every showcase narration names which reactions are safety
functions and which are process behaviour.

Conventions pinned here and never renegotiated: wire NC / program NO,
monitored edge-triggered reset with stuck-button detection, **no
auto-resume**, sensor re-read after reset. Safe state must be reachable
with the standard CPU stopped — four acceptance tests execute exactly
that case.

## Media

None — a paper milestone by design. The first safety hardware behaviour
on recording is [M5's](../m5/).
