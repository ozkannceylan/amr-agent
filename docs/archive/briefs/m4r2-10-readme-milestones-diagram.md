# Brief m4r2-10 — README milestone curation and the architecture diagram

```
gate:                M4
agent:               infra (owner-approved: README.md only)
goal:                The README's milestone table tells the owner's curated
                     story (two gates archived, the path continuing on the
                     forklift twin) and a simple mermaid diagram explains the
                     as-built architecture at a glance.
invariants_touched:  none — the README is owner-curated; the repo's roadmap
                     deliberately stays as-is until the post-demo ADR (owner
                     ruling 2026-07-30, recorded outside the repo)
inputs:              [README.md, docs/adr/0009-*.md (wording for the safety
                      path), docs/safety/TWIN-DEMO-MAP.md (caption
                      discipline)]
deliverable:         README.md
done_when:           the milestone rows "Safety layer on the fixed cell
                     (F-CPU)" and "Simulated vehicle" read status
                     **archived** (not planned); one short line under the
                     table states the path forward: the VDA 5050 client
                     builds on the forklift twin, fleet management follows
                     with multiple forklifts; a mermaid flowchart is added
                     near the architecture paragraph — SIMPLE, one screen:
                     Browser HMI -> HMI backend -> (OPC UA) -> S7-1513F
                     [standard program FB_ForkliftTeleop + F-program
                     F_Forklift_Safety with the demand formed inside the CPU]
                     -> (OPC UA) -> bridge -> ROS 2 topics -> Gazebo forklift
                     + lidar, with the return path sensors -> bridge -> PLC
                     -> HMI metrics, and one annotation that the network
                     carries process data and read-only safety mirrors only;
                     GitHub-renderable (```mermaid fence, flowchart LR or TD,
                     no exotic syntax); no safety over-claim in any label
                     (the F box says "safety demand forms here", never
                     "safety function certified"); the GIF, captions, links
                     and the rest of the structure stay untouched; the README
                     stays short.
forbidden:           [editing docs/roadmap.md or any planning file, touching
                      assets or captions, claiming PL/certification,
                      mentioning any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly README.md
plus your report docs/reports/m4r2-10-readme-milestones-diagram.md; message
style `docs(infra): curate the milestones and add the architecture diagram`.
