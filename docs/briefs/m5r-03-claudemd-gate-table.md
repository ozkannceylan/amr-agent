# Brief m5r-03 — CLAUDE.md section 6 gate table per ADR 0010

```
gate:                restructure round
agent:               infra
goal:                CLAUDE.md section 6 carries the ADR 0010 gate table
                     instead of the pre-ADR-0004 original it still shows.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      CLAUDE.md section 6, docs/roadmap.md (as revised by
                      m5r-02, or the m5r-02 brief's rows if not yet landed)]
deliverable:         CLAUDE.md (section 6 only)
done_when:           the section 6 table lists M0-M7 per ADR 0010 with short
                     one-line "closes when" summaries (full criteria live in
                     docs/roadmap.md); M4 reads as the current gate; no arm or
                     Hermes row exists (Hermes is absorbed by M7); the
                     number-free sentences around the table ("Work proceeds
                     gate by gate...", "Current gate is tracked in
                     docs/roadmap.md...") are kept verbatim; nothing outside
                     section 6 changes.
forbidden:           [editing any other CLAUDE.md section (the section 5
                      roster, section 3 topology and section 4 layout stay
                      as they are — any drift there is a separate owner
                      conversation), editing any other file, committing (the
                      orchestrator commits), mentioning any deadline]
```

## Short rows to use (summaries, not the roadmap's full criteria)

| M0 | Repo skeleton, ADR 0001 recording the invariants | Structure exists, invariants committed |
| M1 | Interface contracts | VDA 5050 subset and OPC UA node model documented and reviewed |
| M2 | Safety requirements spec | Every safety function has a trigger, a reaction and an acceptance test |
| M3 | Fixed equipment I/O loop | Gazebo-to-PLC signal loop demonstrated both ways, latency measured, signal-loss behaviour tested |
| M4 | Forklift commissioning cell | Teleoperated forklift driven from the HMI with the PLC forming every setpoint; recorded commissioning showcase |
| M5 | Sensored autonomous forklift | Safety laser scanner into the F-blocks, lidar SLAM and Nav2 autonomy on the forklift, HMI v2 with mode selection; recorded safety + autonomy showcase |
| M6 | VDA 5050 fleet at scale | Four forklifts serve five loading and five unloading stations over VDA 5050, PLC-owned station handshake end to end; recorded fleet showcase |
| M7 | LLM operations layer | An LLM supervises operations safely (no actuator writes, no interlock bypass, unreachable-safe); closes with the recorded end-to-end demonstration |

Do not commit. Leave CLAUDE.md modified and write your report to
docs/reports/m5r-03-claudemd-gate-table.md (also uncommitted).
