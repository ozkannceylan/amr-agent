# LESSONS

Append only. One entry per correction, dead end or surprise.
Format: date | what was attempted | what went wrong | the rule now

2026-07-26 | Planned M0 briefs against the section 5 roster | No roster agent has write access to the repo root, docs/adr/ or docs/roadmap.md, so bootstrap work had no owner | Infra deliverables go to an ad-hoc infra agent, approved by the owner per brief list
2026-07-26 | Session provisioned with branch claude/m0-gate-repo-skeleton-nu4br4 | Conflicted with the CLAUDE.md branch template | The CLAUDE.md template wins; owner confirmed docs/infra-repo-skeleton; surface the conflict instead of silently picking a branch
