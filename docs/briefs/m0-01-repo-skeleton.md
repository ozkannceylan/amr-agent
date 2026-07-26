gate:                M0
agent:               infra
goal:                The repository skeleton from CLAUDE.md section 4 exists, and every top level directory carries a boundary README.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 3, 4]
deliverable:         Directories docs/adr, docs/safety, docs/interfaces, docs/briefs, docs/reports, plc, fleet, agv, sim; a README.md in each of docs/, plc/, fleet/, agv/, sim/ whose FIRST section is titled "This layer must not access" and lists that layer's forbidden dependencies explicitly, derived from the section 2 invariants and the section 3 topology; a .gitkeep in each otherwise empty directory so the tree survives commit.
done_when:           Every listed directory exists; every top level README opens with the "This layer must not access" section naming concrete forbidden dependencies (not placeholders); no other content is required in the READMEs beyond a one line statement of what the layer owns.
forbidden:           [writing application code, editing CLAUDE.md or .claude/, creating ADR or roadmap content, editing the root README.md, adding dependencies, committing to git]
