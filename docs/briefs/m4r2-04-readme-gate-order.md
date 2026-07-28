# Brief m4r2-04 — public README: gate order and finding-12 residue

```
gate:                M4
agent:               infra (owner-approved for repo-root README.md only)
goal:                The public README matches the ADR 0008 gate order and
                     carries no claim the M3 verifier contradicted.
invariants_touched:  none
inputs:              [README.md, docs/roadmap.md (authoritative order),
                      docs/reports/m3-37-gate-verification.md finding 12,
                      docs/reports/m4r2-02-roadmap-renumber.md section 3
                      (README rows), commit d717283 (what is already fixed —
                      diff it first)]
deliverable:         README.md (revised)
done_when:           the gate table matches roadmap.md M0-M12 including the M4
                     forklift commissioning row; every prose gate reference
                     m4r2-02 section 3 lists is renumbered; whichever
                     finding-12 items d717283 did not already fix are corrected
                     (check the closed-loop citation, section B.6 vs B.5);
                     every remaining caption states only what its artifact
                     shows; nothing else changes.
forbidden:           [new marketing or narrative prose, touching assets/ or any
                      other file, restating §11 pass counts the evidence does
                      not derive, mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly README.md
plus your report docs/reports/m4r2-04-readme-gate-order.md; message style
`docs(infra): align the public README with the ADR 0008 gate order`.
