# Brief m4r2-08 — the README leads with the teleop video

```
gate:                M4
agent:               infra (owner-approved: README.md, assets/, and the ffmpeg
                     toolchain step below)
goal:                The public README is short and video-first: the live
                     teleoperation showcase on top, the M3 conveyor loop
                     demoted to a history section, prose cut to what the video
                     does not say.
invariants_touched:  none
inputs:              [README.md, docs/roadmap.md (gate table authority),
                      docs/safety/TWIN-DEMO-MAP.md (caption discipline),
                      the source video below]
deliverable:         README.md restructured, assets/teleop-showcase.gif and
                     assets/teleop-showcase.mp4 produced and committed
done_when:           assets/ gains (a) teleop-showcase.mp4 — the source
                     re-encoded to <=25 MB (H.264, ~1280 px wide, audio
                     dropped) and (b) teleop-showcase.gif — a 10-20 s highlight
                     of the drive (target <15 MB, readable at README width);
                     README order is: title + two-sentence summary, the GIF
                     with a caption and a link to the full mp4, a compact
                     architecture paragraph with the topology pointer, the
                     milestone table (unchanged content), then a short
                     "How it started — the M3 fixed-cell loop" section holding
                     the conveyor GIF with its existing corrected captions
                     kept verbatim, then links (docs/, ADRs); total prose is
                     cut hard — anything the video shows is not re-described;
                     every kept citation still resolves; captions follow the
                     TWIN-DEMO-MAP discipline (teleop reactions named as
                     standard-program process logic; nothing presented as a
                     safety qualification; the F-side, if captioned at all,
                     uses the operator-drove-the-device wording).
forbidden:           [removing the milestone table or the corrected M3
                      captions' factual content, claiming any safety function
                      or PL achievement in a caption, committing the 92.9 MB
                      source video, mentioning any deadline]
```

Source video (read-only, outside the repo):
`C:\Users\ozkan\Videos\Screen Recordings\Screen Recording 2026-07-30 090417.mp4`
(from WSL: `/mnt/c/Users/ozkan/Videos/Screen Recordings/...`).

Toolchain: ffmpeg is absent in WSL. Install it (`sudo apt-get install -y
ffmpeg` if sudo is passwordless; otherwise download the static build into
~/bin and use it from there) and record which route was taken in your report.
Verify the produced GIF actually animates and the mp4 plays (ffprobe duration
and stream summary quoted as printed).

Git: repo-local owner identity; pathspec-scoped commit of exactly README.md,
the two asset files and your report docs/reports/m4r2-08-readme-video-first.md;
message style `docs(infra): lead the README with the teleop showcase`.
