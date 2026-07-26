# LESSONS

Append only. One entry per correction, dead end or surprise.
Format: date | what was attempted | what went wrong | the rule now

2026-07-26 | Planned M0 briefs against the section 5 roster | No roster agent has write access to the repo root, docs/adr/ or docs/roadmap.md, so bootstrap work had no owner | Infra deliverables go to an ad-hoc infra agent, approved by the owner per brief list
2026-07-26 | Session provisioned with branch claude/m0-gate-repo-skeleton-nu4br4 | Conflicted with the CLAUDE.md branch template | The CLAUDE.md template wins; owner confirmed docs/infra-repo-skeleton; surface the conflict instead of silently picking a branch
2026-07-26 | Committed M0 work with the environment's default git identity | Verifier found tooling author metadata in git log even though commit messages were clean | Author fields count as attribution; set repo-local user.name and user.email to the owner before the first commit of every session
2026-07-26 | ADR 0002 cited live vendor repos as evidence | Claims like "jazzy-devel is the default branch" will silently age with no pinned ref to re-check against | When an ADR cites external vendor sources, record the verification date and, where possible, a pinned ref or commit so the claim stays re-checkable
