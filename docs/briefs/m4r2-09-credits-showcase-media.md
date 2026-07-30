# Brief m4r2-09 — the credits file covers the showcase media

```
gate:                M4
agent:               infra (owner-approved: assets/CREDITS.md only)
goal:                assets/CREDITS.md again covers every asset in the
                     directory and carries no stale gate number.
invariants_touched:  none
inputs:              [assets/CREDITS.md, docs/reports/m4r2-08-readme-video-
                      first.md (production facts), docs/adr/0008-*.md]
deliverable:         assets/CREDITS.md
done_when:           two new rows exist — teleop-showcase.gif and
                     teleop-showcase.mp4, source: the owner's own screen
                     recording of the live teleoperation (2026-07-30),
                     re-encoded/cropped with ffmpeg (the crop drops the
                     Windows taskbar), no third-party content; and the stale
                     "enters the demonstration at M5" reads M6 per ADR 0008;
                     the file's completeness claim is true again (every file
                     in assets/ has a row — verify by listing); nothing else
                     changes.
forbidden:           [editing README.md or the assets themselves, mentioning
                      any deadline]
```

Git: repo-local owner identity; pathspec-scoped commit of exactly
assets/CREDITS.md plus your report docs/reports/m4r2-09-credits-showcase-media.md;
message style `docs(infra): credit the showcase media`.
