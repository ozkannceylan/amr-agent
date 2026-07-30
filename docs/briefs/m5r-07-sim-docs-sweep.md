# Brief m5r-07 — sim/ gate-reference reconciliation per ADR 0010

```
gate:                restructure round
agent:               sim
goal:                every gate reference in sim/ names the ADR 0010 gate that
                     now carries the work.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      sim/README.md, sim/setup/WSL_ENVIRONMENT.md,
                      sim/scenarios/DEFERRED.md,
                      sim/scenarios/forklift_commissioning.md,
                      sim/launch/forklift_bringup.launch.py,
                      sim/worlds/forklift_arena.sdf,
                      sim/worlds/FORKLIFT_ARENA_EVIDENCE.md,
                      the mapping block below]
deliverable:         sim/ (gate references only)
done_when:           every stale gate reference names its ADR 0010 gate; all
                     M4 references are untouched (M4 keeps its number); the
                     deferred navigation work is described as resuming at M5
                     ON THE FORKLIFT per ADR 0010 (the RB-KAIROS platform is
                     retired — where DEFERRED.md or README prose assumes that
                     platform, state the ADR 0010 ruling and mark the parked
                     scenario's platform migration as M5-briefing work rather
                     than silently rewriting the scenario); the coupled
                     cell-plus-vehicle scenario and door/charger handshake
                     references read M6; stale ADR 0004 citations for gate
                     order cite ADR 0010; DEFERRED.md's "docs/briefs/m5-*"
                     filename guess is removed (brief names are assigned at
                     briefing); no scenario step, evidence claim or world
                     content changes in substance; a whitespace-normalised
                     sweep for M5-M12 tokens and gate names confirms no live
                     stale reference remains in sim/.
forbidden:           [changing any scenario procedure step, world file
                      geometry or evidence text beyond the gate name it
                      cites; deciding whether the warehouse world is reused
                      at M5 or M6 (open — say "decided at briefing" where it
                      comes up); editing files outside sim/; committing (the
                      orchestrator commits); treating the location list below
                      as exhaustive]
```

## Mapping (ADR 0010, owner-approved 2026-07-30)

M0-M4 keep their numbers. Old meaning → new gate: vehicle / navigation work →
**M5** (on the forklift, with SLAM); safety layer → **M5**; VDA 5050 client →
**M6**; fleet manager → **M6**; PLC integration / door-charger handshakes /
coupled cell-plus-vehicle scenario (AT-07 coupled) → **M6**; demonstration →
**M7**; arm → removed; Hermes/LLM → **M7**.

## Known locations (a starting point — verify by independent search)

- sim/README.md: 26 ("now M5" warehouse world), 175 (heading "Navigation
  scenario (M5, deferred)" — this heading is also quoted by
  docs/interfaces/bridge-design.md items 8/15; keep the new heading's exact
  text in your report so the interface sweep can cite it), 176-178 (ADR 0004
  order prose), 248 ("later gates (M6/M7)" door/charger → M6), 259, 469
  ("roadmap M9 work (AT-07)" → M6).
- sim/setup/WSL_ENVIRONMENT.md: 15, 33, 34, 146 ("M5 vehicle work" — the
  number happens to be right again under ADR 0010, but the sentences cite
  the old structure; make them cite ADR 0010/roadmap and the forklift, and
  note ros2_control's "not needed" claims are re-examined at M5 briefing,
  not ruled here).
- sim/scenarios/DEFERRED.md: 13, 15.
- sim/scenarios/forklift_commissioning.md: M4 refs untouched; §12's
  "T6 (M5, early)" framing reconciled once with ADR 0010's widened M5
  (the early opening is now M5's own opening wave); 990-997 "M5 proper".
- Code comments: forklift_bringup.launch.py 21 (M9 → M6),
  forklift_arena.sdf 14 (M9 → M6), FORKLIFT_ARENA_EVIDENCE.md 77 (M9 → M6).

Do not commit. Leave the files modified and write your report to
docs/reports/m5r-07-sim-docs-sweep.md (also uncommitted).
