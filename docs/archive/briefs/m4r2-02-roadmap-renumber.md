# Brief m4r2-02 — roadmap renumber per ADR 0008

```
gate:                M4 (opening)
agent:               arch-docs
goal:                docs/roadmap.md reflects ADR 0008: new M4 forklift commissioning
                     gate inserted, previous M4-M11 shifted to M5-M12, every
                     cross-reference consistent.
invariants_touched:  none
inputs:              [docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      docs/roadmap.md, docs/adr/0007-safety-first-gate-order.md]
deliverable:         docs/roadmap.md (revised)
done_when:           the table carries the new M4 row below verbatim in substance;
                     old M4-M11 rows appear as M5-M12 with their criteria text
                     unchanged except gate-number cross-references; every prose
                     cross-reference is renumbered consistently; the renumbering
                     note gains the ADR 0008 round while keeping the ADR 0004/0007
                     rounds' notes; the current-gate line reads M4; nothing else
                     changes.
forbidden:           [altering any shifted row's criterion beyond gate-number
                      references, editing ADRs or PLAN.md or TODO.md or CLAUDE.md,
                      deleting the M0-M2 closure lines, mentioning any deadline]
```

## New M4 row

| M4 | Forklift commissioning cell | An operator drives the in-house forklift model in Gazebo from the commissioning HMI, every command passing HMI → PLC standard program → bridge → simulation and every state report returning simulation → bridge → PLC: (a) teleoperated drive with the PLC forming all motion setpoints, (b) the fork raised to a commanded height and stopped by the PLC's soft travel limits, (c) traction speed capped by the PLC while the fork is above its height threshold, (d) an obstacle entering the lidar stop zone latching a PLC process stop that overrides teleop, cleared only by the edge-triggered monitored reset after the zone clears, (e) loss of the HMI heartbeat zeroing all motion setpoints within the watchdog period; and a **recorded commissioning showcase** demonstrates (a)–(e), naming each reaction as standard-program process logic, not a safety function |

## Renumbering and prose edits

- Shift: safety layer → M5, simulated vehicle → M6, VDA 5050 client → M7, fleet
  manager → M8, PLC integration → M9, demonstration → M10, arm → M11, Hermes → M12
  (parked, last).
- Recordings paragraph: four embedded recordings — commissioning showcase at M4,
  cell + safety showcase at M5, fleet showcase at M9, end-to-end demonstration at
  M10.
- Safety-completeness paragraph: cell-scope functions land at M5; SF-05 and SF-06
  complete at M9; the vehicle chain at M6 and M7; ADR 0007 §2 still holds the
  per-function split (unchanged content, shifted numbers).
- Filename note: existing brief/report filenames stay as written — m4-00-hermes-survey.*
  belongs to M12, the m4r-* round belongs to ADR 0007, the m4r2-*/m4f-* files belong
  to the new M4, the older m3-* sim files (warehouse world, headless bringup,
  navigation scenario) belong to M6.
- M3 closure line: "M3 closed 2026-07-28 by owner ruling; evidence in
  docs/reports/m3-26/m3-33/m3-35/m3-36; the gate-verifier run is deferred and
  carried in TODO with the two outstanding T4.11 items."
- Current gate line: "Current gate: M4 — Forklift commissioning cell (ADR 0008)."

## Git

Repo-local owner identity; pathspec-scoped commit of exactly docs/roadmap.md plus
your report docs/reports/m4r2-02-roadmap-renumber.md; message style
`docs(infra): renumber the roadmap for the forklift commissioning gate`.
