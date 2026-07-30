# Brief m5r-02 — roadmap restructure per ADR 0010

```
gate:                M4 (closing) / restructure round
agent:               arch-docs
goal:                docs/roadmap.md carries the ADR 0010 gate structure: M0-M4
                     unchanged, new M5-M7 rows below, arm row removed, every
                     prose cross-reference consistent.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      docs/roadmap.md, docs/adr/0008-forklift-commissioning-gate-and-hmi-layer.md,
                      docs/adr/0009-early-cell-scope-safety-on-the-forklift-twin.md]
deliverable:         docs/roadmap.md (revised)
done_when:           the table carries M0-M4 unchanged and the three new rows
                     below verbatim in substance; the M4 status line reads
                     current gate, closing (showcase recording + m4f-09
                     pending); the renumbering note gains the ADR 0010 round
                     while keeping the ADR 0004/0007/0008 rounds' history; the
                     recordings paragraph lists commissioning at M4, safety +
                     autonomy at M5, fleet at M6, end-to-end demonstration at
                     M7; the safety-completeness paragraph maps cell-scope SFs
                     and the vehicle chain to M5, SF-05/06 to M6, SF-20..29 to
                     out of scope; the filename note maps m4-00-hermes-survey.*
                     to M7, the parked m3-* navigation sim files to M5; the
                     open decisions of ADR 0010 D6 are named as open, not
                     resolved; M0-M3 closure lines are kept.
forbidden:           [editing ADRs, PLAN.md, TODO.md, CLAUDE.md or README.md;
                      resolving any ADR 0010 D6 open decision; altering M0-M4
                      rows beyond the M4 status line; committing (the
                      orchestrator commits); mentioning any deadline]
```

## New rows (substance is binding, wording may be tightened)

| M5 | Sensored autonomous forklift | On the M4 forklift twin: (a) a safety laser scanner is added to the model and its signals reach the F-CPU safety program's F-blocks, a protective-field intrusion tripping an F-latched stop that overrides teleop and autonomous motion, cleared only by the edge-triggered monitored reset after the field clears; (b) the SRS cell-scope functions (SF-01, SF-07, SF-08) pass their acceptance tests on PLCSIM Advanced including the standard-program-in-STOP sub-case, the reactions execute with the bridge stopped and the OPC UA session down, and the `Safety/` mirrors remain read-only; (c) a navigation lidar is added, each sensor's data is verified correct as its own step before anything builds on it, and the sensor beams are visible in the Gazebo GUI; (d) SLAM builds a map of the arena and Nav2 drives the forklift autonomously to commanded goals, with AT-02, AT-03 and AT-04 passing and the inhibit demonstrably acting below the navigation stack; (e) the HMI, inherited from M4 and visually reduced, selects the drive mode (teleop / autonomous), shows a real-time map with live obstacles, and carries an emergency button that issues a process stop and displays F-layer state — never a safety function over the network (invariant 1, ADR 0010 D6b); and a **recorded safety + autonomy showcase** demonstrates (a)–(e), naming which reactions are F-CPU safety functions and which are process behaviour. The map-view data path is decided by its own ADR at M5 briefing (ADR 0010 D6a). |

| M6 | VDA 5050 fleet at scale | An enlarged warehouse world with five loading stations, five unloading stations and four forklifts: the fleet manager assigns transport orders over VDA 5050/MQTT and traffic conflicts are avoided; the PLC owns the stations' fixed equipment and serves OPC UA, the fleet manager subscribes, and the station handshake works end to end; AT-05, AT-06 and AT-09 pass (broker killed: controlled stop within the watchdog period, order kept, SF-03 still acting during the outage), and the fixed-equipment F-I/O (SF-05, SF-06) lands with the stations; and a **recorded fleet showcase** shows orders, traffic and the station handshake in one run. Entry condition: an owner-ruled deep-research brief precedes any implementation (ADR 0010 D3/D6d). |

| M7 | LLM operations layer and final demonstration | An LLM agent supervises the running cell in real time, takes safe actions through the fleet layer only and alerts the operator; it never writes actuator outputs, never bypasses PLC interlocks, and the system operates normally with the LLM and its transport unreachable; the gate closes with the **recorded end-to-end demonstration**, the validation report and the README architecture narrative, the run showing B4 with both chains live and the cell operating normally with the fleet layer and all remote access unreachable. Entry condition: the owner decisions in docs/reports/m4-00-hermes-survey.md are ruled (ADR 0010 D4/D6c). |

## Notes

- The gate-order prose paragraph is rewritten around ADR 0010 (which extends
  the 0004 → 0007 → 0008 chain): fixed-equipment loop first, then the
  teleoperated forklift, then sensors + safety + autonomy on that forklift,
  then the fleet at scale, then the LLM layer with the demonstration.
- The two self-declared numbering-history paragraphs (renumber rounds,
  filename note) are prose about a mapping, not token lists — rewrite them,
  do not substitute numbers (the inventory in this round's reports flagged
  them).
- Do not commit. Leave docs/roadmap.md modified in the working tree and write
  your report to docs/reports/m5r-02-roadmap-restructure.md (also
  uncommitted).
