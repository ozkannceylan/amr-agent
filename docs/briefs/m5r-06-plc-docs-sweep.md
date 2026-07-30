# Brief m5r-06 — plc/ gate-reference reconciliation per ADR 0010

```
gate:                restructure round
agent:               plc
goal:                every gate reference in plc/ names the ADR 0010 gate that
                     now carries the work.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      plc/demo-cell/SPEC.md, plc/forklift/SPEC.md,
                      plc/forklift-safety/SPEC.md, plc/README.md,
                      the mapping block below]
deliverable:         plc/ (gate references only)
done_when:           every stale gate reference names its ADR 0010 gate,
                     mapped by the sentence's subject; all M4 references and
                     the literal watch-table name `Forklift M4 gate` are
                     UNTOUCHED (M4 keeps its number; the watch table is a TIA
                     artifact name bound to captured evidence); forklift-safety
                     SPEC's "M5 early" / "M5 proper" language is reconciled
                     with ADR 0010's widened M5 (the early opening is now the
                     opening wave of M5 itself — say that once where the SPEC
                     explains its own status, rather than re-arguing it per
                     occurrence); no program logic, test step or evidence
                     claim changes in substance; a whitespace-normalised sweep
                     for M5-M12 tokens and gate names confirms no live stale
                     reference remains in plc/.
forbidden:           [renaming the `Forklift M4 gate` watch table or any TIA
                      artifact name; changing any specified logic, test
                      procedure step or evidence text beyond the gate name it
                      cites; editing files outside plc/; committing (the
                      orchestrator commits); treating the location list below
                      as exhaustive]
```

## Mapping (ADR 0010, owner-approved 2026-07-30)

M0-M4 keep their numbers. Old meaning → new gate: safety layer → **M5** (on
the forklift twin); vehicle chain / simulated vehicle → **M5**; VDA 5050
client → **M6**; fleet manager → **M6**; PLC integration / station handshake /
SF-05, SF-06 / AT-05, AT-06 / target-cell door-charger logic → **M6**;
demonstration → **M7**; arm → removed, out of scope; Hermes/LLM → **M7**.
Fixed-cell F-I/O follows its equipment to **M6**; forklift F-I/O is **M5**.

## Known locations (a starting point — verify by independent search)

- plc/demo-cell/SPEC.md: 1683 "gate M9" (safety) → M5; 1684 "Gate M8"
  (target-cell door/charger/handshake) → M6. Also close the carried TODO
  item if trivially in reach of these lines only — otherwise leave it.
- plc/forklift-safety/SPEC.md: 93 (N7 order statement: SF-02/03/04 +
  vehicle SF-08 "at M6" → M5; SF-09 "at M7" → rule by subject, flag if
  ambiguous; SF-05/06 "at M9" → M6); 1024 (fixed-cell SF-08 "M9" → M6);
  1348 ("Real F-I/O, M5 proper" — forklift F-I/O stays M5; say which);
  plus the M5-early/M5-proper status prose (1, 29, 91, 122-123, 196, 1142,
  1322-1324) reconciled once against ADR 0010.
- plc/forklift/SPEC.md: 958/1624+ ("M5-early coupling delta" — same
  reconciliation); 1597 (SRS "gate M5" — still M5, verify meaning holds).
- plc/README.md: 19 is M4 — untouched.

Where a ruling is genuinely ambiguous, put it in the report's open_questions
instead of guessing.

Do not commit. Leave the files modified and write your report to
docs/reports/m5r-06-plc-docs-sweep.md (also uncommitted).
