# PLAN

## Current gate: M0 — Repo skeleton and invariants

Exit criterion: repository structure from CLAUDE.md section 4 exists, every
top level directory has a README.md whose first section is "This layer must
not access", ADR 0001 records the section 2 invariants with status accepted,
docs/roadmap.md carries the M0–M8 gate table with M0 marked current, and the
verifier has passed all of the above. `.claude/settings.json` already contains
the attribution block; the verifier confirms it, no brief needed.

## Briefs to close M0, in order

1. `docs/briefs/m0-01-repo-skeleton.md` — infra: create the directory
   skeleton with layer READMEs ("This layer must not access" first).
2. `docs/briefs/m0-02-adr-0001.md` — infra: write
   `docs/adr/0001-architecture-invariants.md`, status accepted.
3. `docs/briefs/m0-03-roadmap.md` — infra: write `docs/roadmap.md` with the
   M0–M8 gate table, M0 marked current.
4. `docs/briefs/m0-04-verify.md` — verifier, read only: check all M0
   criteria including the existing `.claude/settings.json`.

No application code is written in this gate. Briefs 1–3 run sequentially
(2 and 3 write into directories brief 1 creates); brief 4 runs last.
