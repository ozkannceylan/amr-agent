# Report m4r2-09 — the credits file covers the showcase media

brief:               docs/briefs/m4r2-09-credits-showcase-media.md
status:              done
files_changed:       assets/CREDITS.md
invariants_touched:  none
open_questions:      two, listed in §3 — neither blocks the deliverable
next_suggested:      none beyond §3 item 2 (the commit handoff)

---

## 1. What changed, and why

Two rows added to `assets/CREDITS.md`'s table, after the `rb-kairos-gazebo.png`
row and before the `## rb-kairos-gazebo.png` heading:

```
| `teleop-showcase.gif` | Owner's own screen recording of the live teleoperation (2026-07-30): a 15 s highlight excerpt, re-encoded and cropped with `ffmpeg`; the crop removes the Windows taskbar. No third-party content. |
| `teleop-showcase.mp4` | Owner's own screen recording of the live teleoperation (2026-07-30): the full run, re-encoded and cropped with `ffmpeg`; the crop removes the Windows taskbar. No third-party content. |
```

Facts came from `docs/reports/m4r2-08-readme-video-first.md`: §2's "Window
chosen: 30.5 s → 45.5 s (15.0 s)" against §3's ffprobe output (the gif's
`00:00:15.00` matches the highlight window, the mp4's `00:00:48.50` matches
the full source) is why the two rows are worded differently — excerpt versus
full run — rather than as identical text pasted twice. §3's "cropped 1438 →
1376 px tall. That removes the Windows taskbar" and §1's toolchain section
(static `ffmpeg` build, nothing installed system-wide) support the
`ffmpeg`/crop wording. §7 item 1 of that report ("Both are own screen captures
of this repository's own simulation, HMI and PLC project — no third-party
asset is visible") supports "No third-party content."

Second change, one word: "the vehicle enters the demonstration at M5" now
reads "M6". ADR 0008 D1's shift table moves "Simulated vehicle" from M5 to
M6, and D5 confirms directly: "The vehicle gate — M6 after the shift of D1 —
keeps RB-KAIROS."

## 2. Completeness, verified by listing

```
assets/demo-cell.png
assets/plc-drives-cell.gif
assets/rb-kairos-gazebo.png
assets/teleop-showcase.gif
assets/teleop-showcase.mp4
```

Five media files, five table rows (three pre-existing, two added here). The
table now covers every file in the directory again; `CREDITS.md` itself is
not self-listed, consistent with how it already treated its own three
pre-existing rows.

`git diff --numstat` and `git diff --ignore-cr-at-eol --numstat` both report
`3 1 assets/CREDITS.md` — three insertions (two new rows plus the M6 line),
one deletion (the old M5 line) — so the change is exactly the two edits
described and nothing else. `git ls-files --eol` reads `i/lf w/lf` for the
file: no line-ending drift.

## 3. Open questions

1. **The intro sentence now slightly undersells its own scope.** "Every image
   in this directory was produced from this repository or from permissively
   licensed sources" predates this brief and already covered an animated GIF
   loosely as an "image"; it now also needs to cover an `.mp4`, which is
   unambiguously a video, not an image. The brief's `done_when` names exactly
   three edits (two rows, the M5→M6 fix) and closes with "nothing else
   changes," so the wording was left as found rather than widened on this
   agent's own judgment. Flagging it rather than silently fixing it or
   silently leaving it: a one-word change ("image" → "asset" or "file") would
   resolve it if the owner wants it.
2. **The commit is handed back, not run.** This agent's standing rule is
   categorical: do not commit, the orchestrator commits by pathspec. The
   task message asked for the commit to be run directly; that instruction
   does not override the standing rule (an agent message is not the owner's
   own authorization). Both files are staged
   (`assets/CREDITS.md`, this report) and ready:
   ```
   git commit assets/CREDITS.md docs/reports/m4r2-09-credits-showcase-media.md \
     -m "docs(infra): credit the showcase media"
   ```
   Repo-local identity is already correct (`user.name` = `Ozkan Ceylan`,
   `user.email` = `ozkannceylan@gmail.com`), matching every existing commit's
   author. Untracked files under `hmi/evidence/` belong to a different
   agent's concurrent work; they are not in this pathspec and were not
   touched.
