# Brief m5r-05 — docs/safety/ gate-reference reconciliation per ADR 0010

```
gate:                restructure round
agent:               safety-spec
goal:                every gate reference in docs/safety/ names the ADR 0010
                     gate that now carries the work, and SF-20..29 are marked
                     out of scope per the arm removal.
invariants_touched:  none
inputs:              [docs/adr/0010-milestone-restructure-forklift-first.md,
                      docs/safety/SRS.md, docs/safety/PL-SCENARIOS.md,
                      docs/safety/TWIN-DEMO-MAP.md, the mapping block below]
deliverable:         docs/safety/ (SRS.md, PL-SCENARIOS.md, TWIN-DEMO-MAP.md,
                     gate references and the arm scope marking only)
done_when:           every gate number in the three files names the gate that
                     ADR 0010 assigns to that sentence's SUBJECT (map by
                     meaning, never by arithmetic on the stale number — SRS
                     numbers predate two renumber rounds); SF-20..29 and SRS
                     §1.3 read "out of scope — arm integration removed from
                     the roadmap (ADR 0010 D5)", keeping the SF ids reserved
                     so nothing is silently lost; PL-SCENARIOS' self-declared
                     numbering note and TWIN-DEMO-MAP's gate-number note are
                     rewritten as prose against ADR 0010, not token-swapped;
                     no acceptance criterion, PL derivation, trigger or
                     reaction changes in substance; a whitespace-normalised
                     sweep for M4-M12 tokens and the gate names confirms no
                     live stale reference remains in docs/safety/.
forbidden:           [changing any safety function's trigger, reaction,
                      acceptance test or PL claim; deleting SF-20..29 rows;
                      editing files outside docs/safety/; committing (the
                      orchestrator commits); treating the location list below
                      as exhaustive]
```

## Mapping (ADR 0010, owner-approved 2026-07-30)

M0-M4 keep their numbers; M4 is the current gate, closing. Old meaning → new
gate: safety layer (old M5, on the fixed cell) → **M5** (on the forklift twin,
merged with autonomy); simulated vehicle / vehicle chain (old M6) → **M5**;
VDA 5050 client (old M7) → **M6**; fleet manager (old M8) → **M6**; PLC
integration / station handshake / SF-05, SF-06 / AT-05, AT-06 (old M9) →
**M6**; demonstration (old M10) → folded into **M7**; arm (old M11) →
**removed, out of scope**; Hermes/LLM (old M12) → **M7**. AT-09 (broker loss)
→ **M6**. AT-02/03/04 (vehicle chain) → **M5**.

## Known locations (a starting point — verify by independent search, per LESSONS)

- SRS.md: 6-7 (M7/M3-M4), 34/38/40 (arm "until M9"), 64 (AT-01 "M7"),
  109/121 (AT-05/06 "M7" → M6), 132 (AT-07 "M7; coupled at M8" → M5; coupled
  at M6), 143 (AT-08 "M7" → M5), 154 (AT-09 "M4" → M6), 164-173 (§4
  verified-at column, whole remap; SF-02 "M3 sim, M7 review" → M5; SF-03/04
  "M3" → M5 vehicle chain... map each row by its SF's landing gate),
  172 (SF-09 "M4" → M7? No: SF-09 supervision watchdog is the vehicle
  supervision boundary — its VDA-client half lands at M6; rule it by the
  SF's subject and say so in the report if ambiguous).
- PL-SCENARIOS.md: 28-32 (the numbering note — rewrite against ADR 0010).
- TWIN-DEMO-MAP.md: 15/17-20 (M5 row + numbering note — M5 stays M5 but the
  note must cite ADR 0010 and the widened M5 meaning), 58 ("M5 proper" — now
  the forklift F-I/O half of M5), 81 (NC-1 "They land at M6" → M5), 86, 134,
  148, 162, 172 (M5 refs — the number survives; check each sentence still
  means what it says now that M5 includes autonomy, and adjust prose where
  the widened meaning breaks it).

Where a sentence's ruling is genuinely ambiguous under the new structure
(e.g. SF-09's landing), place it in the report's open_questions instead of
guessing.

Do not commit. Leave the files modified and write your report to
docs/reports/m5r-05-safety-docs-sweep.md (also uncommitted).
