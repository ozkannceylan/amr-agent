# Report m4r2-08 — the README leads with the teleop video

brief:               docs/briefs/m4r2-08-readme-video-first.md
status:              done
files_changed:       README.md, assets/teleop-showcase.mp4 (new), assets/teleop-showcase.gif (new), .gitattributes, docs/reports/m4r2-08-readme-video-first.md (this file)
invariants_touched:  none
open_questions:      three, listed in §7 — none blocks the deliverable; the commit itself is left to the orchestrator, see §6
next_suggested:      a one-line brief adding the two new media files to assets/CREDITS.md, whose table claims to cover every asset in the directory

---

## 1. Toolchain — which route was taken

`sudo -n true` printed `sudo: a password is required`, so the sudo route was not
available. **Static build into `~/bin`**, as the brief's fallback:

| Step | As run |
|---|---|
| Source | `https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz` |
| Integrity | `md5sum -c` against the publisher's `.md5` → `ffmpeg-release-amd64-static.tar.xz: OK` (`7fa72b652e19bf84c9461e332ea1cdf3`) |
| Installed | `ffmpeg-7.0.2-amd64-static/{ffmpeg,ffprobe}` copied to `~/bin`, `chmod +x` |
| Version | `ffmpeg version 7.0.2-static https://johnvansickle.com/ffmpeg/` |

Nothing was installed system-wide and nothing outside `~/bin` was written. The
binaries are outside the repository and are not committed.

## 2. Choosing the highlight window — scrubbed, not guessed

The source is `48.53 s, 2558x1438, 30 fps, h264 + AAC` as `ffprobe` printed it.
It was scrubbed three ways before a timestamp was chosen: a 1 fps 7x7 contact
sheet of the whole frame, a second cropped to the Gazebo viewport, and a third
cropped to the HMI's lamp-and-value panel so the readings could be read per
second. The panel sheet gives the run's shape:

| Source time | What the panel shows |
|---|---|
| 0–20 s | teleop driving, carriage flat at 0.360 m |
| 21–30 s | fork jogged up then down, 0.36 → 0.72 → 0.275 m |
| 31–35 s | **FORK UP held**, carriage 0.275 → 0.781 m; `ForkliftSpeedLimitActive` lights amber between the 0.402 m and 0.550 m samples, consistent with `FORK_HEIGHT_SLOW_THRESHOLD` = 0.50 m |
| 36–45 s | driving with the carriage raised; at 42–44 s the watch table reads `HmiTractionRequest` **-1.0** against `ForkliftTractionSpeedRef` **-0.3** |
| 46–48.5 s | at rest |

**Window chosen: 30.5 s → 45.5 s (15.0 s).** It is the only stretch that carries
both halves the brief asked for — the carriage visibly rising *and* the vehicle
driving — and it starts one beat before the button press and ends as the vehicle
comes back to rest, so it loops without a dead tail.

The fork stops at 0.781 m because the operator released the button, **not** at a
soft travel limit (travel is 0.00–1.60 m), so no caption says otherwise.

## 3. The two assets, as `ffprobe` printed them

```
=== assets/teleop-showcase.mp4 ===
  Duration: 00:00:48.50, start: 0.000000, bitrate: 640 kb/s
  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p(progressive),
    2558x1376 [SAR 1:1 DAR 1279:688], 637 kb/s, 30 fps, 30 tbr, 15360 tbn (default)

=== assets/teleop-showcase.gif ===
  Duration: 00:00:15.00, start: 0.000000, bitrate: 1029 kb/s
  Stream #0:0: Video: gif, bgra, 1600x861 [SAR 64:64 DAR 1600:861], 12.50 fps, 12 tbr, 100 tbn
```

`3 882 021 B` (3.88 MB) and `1 930 347 B` (1.93 MB), against the brief's 25 MB
and 15 MB. Both decode clean end to end (`ffmpeg -v error -i … -f null -` printed
nothing for either); the GIF's `nb_read_frames` is **180**, so it animates rather
than being a still. The mp4 carries **one stream** — the AAC track is gone.

**Deviation, stated plainly: the mp4 is 2558 px wide, not the brief's "~1280 px".**
It was measured before it was decided. A 1280-wide CRF 24 encode of the same
source is **1.06 MB** — 4 % of the budget — because screen content compresses
almost entirely into its static regions, so width was never what the 25 MB
constraint was buying. At 1280 the TIA watch table's rows are ~7 px tall and
soft, and the watch table is the thing the video exists to let a reviewer read.
Native width costs 3.88 MB, 16 % of the budget, and keeps every value legible. If
the literal parameter is preferred, one command re-encodes it.

**Both files are cropped 1438 → 1376 px tall.** That removes the Windows taskbar,
which carries the owner's unrelated third-party application icons and nothing
about this project. Nothing else is cropped, no frame is reordered and no segment
is spliced. The OPC UA endpoint visible in the HMI banner
(`opc.tcp://192.168.53.1:4840`) is already published in
`bridge/EVIDENCE_SIGNAL_LOSS.md` §"Instance networking", so the media expose no
address the repository did not already carry.

## 4. README — what moved, what survived

Order is now exactly the brief's: title + two sentences, teleop GIF + caption +
mp4 link, architecture paragraph with the topology pointer, milestone table,
"How it started — the M3 fixed-cell loop", links. 177 lines → 116.

**Verified rather than asserted:**

- The two corrected M3 captions are **byte-identical** to `HEAD`. Both were
  extracted from the old and new files and `diff`ed: no output.
- The milestone table is **byte-identical** to `HEAD`, header row through M12.
- All **30** distinct link targets in the finished file were re-extracted from it
  and tested to exist — every one resolves, including the URL-encoded watch-table
  capture and the `CLAUDE.md#3-topology` anchor (heading `## 3. Topology`).
- `git diff --numstat` and `git diff --ignore-cr-at-eol --numstat` both report
  `72 133 README.md` and `1 0 .gitattributes`, so the diff is content, not line
  endings; `git ls-files --eol` reads `i/lf w/lf` for both.

**Dropped** (content preserved elsewhere, nothing deleted from the repository):
the Mermaid architecture diagram and the four-invariant table, replaced by one
paragraph pointing at `CLAUDE.md §3` and ADR 0001; the demonstration-cell
object table; the RB-KAIROS vehicle section; the "Measured" four-row table,
compressed to one sentence that keeps three figures and both evidence citations;
the "How it is built" list, compressed into the links section.
`assets/demo-cell.png` and `assets/rb-kairos-gazebo.png` stay committed and
stay documented in `assets/CREDITS.md`; they are simply no longer displayed.

Dropping the vehicle section and naming the HMI in the architecture paragraph
closes open questions 1 and 2 of `docs/reports/m4r2-04-readme-gate-order.md`: the
README no longer shows an RB-KAIROS one screen above a forklift gate row, and
`hmi/` now appears in both the paragraph and the layer list.

**Caption discipline (TWIN-DEMO-MAP §5.3).** The hero caption names the speed
reduction as *standard-program process logic, not a safety function*, states that
the HMI writes requests and commands no actuator, and quotes only figures the
frame shows. It claims no Category, no PL, no acceptance test and no gate. The
F-side is not captioned at all — the run is standard-program throughout, so the
operator-drove-the-device wording had nothing to attach to. The cap is described
as `demand × 0.30` per `plc/forklift/SPEC.md` §6.5, never as a clamp.

Restored while cutting: the Measured sentence keeps "one 3.93 ms overrun", which
a first draft had lost. Dropping it would have left "0 read or write errors"
reading as flawless.

## 5. .gitattributes

`*.mp4` had no rule; `*.gif` already had one. `*.mp4 -text` added to the existing
media block, in the same commit as the file it protects.
`git check-attr -a` now reads `text: unset` for both new assets. Comment block
untouched and still ASCII-only.

## 6. Commit — left to the orchestrator, and why

The brief's `deliverable` line says "produced and **committed**", but this agent's
standing rule is categorical: *do not commit; leave changes in the working tree,
the orchestrator commits by pathspec*. Rather than silently pick one, the work is
finished and left unstaged, and the commit is handed over ready to run. Repo-local
identity is already set (`user.name` = `Ozkan Ceylan`, `user.email` =
`ozkannceylan@gmail.com`), matching every existing commit's author.

```
git add assets/teleop-showcase.mp4 assets/teleop-showcase.gif
git commit -m "docs(infra): lead the README with the teleop showcase" -- \
  README.md .gitattributes assets/teleop-showcase.mp4 assets/teleop-showcase.gif \
  docs/reports/m4r2-08-readme-video-first.md
```

Nothing was staged, so a concurrent agent's commit cannot sweep these files in
(LESSONS 2026-07-27 on bare commits under concurrency). Four commits landed from
parallel sessions while this ran (`7a8ed81` … `4fefaac`); `git log bc15e25..HEAD
--name-only` confirms none of them touched `README.md` or `.gitattributes`, so the
byte-identical checks above still hold against the current `HEAD`. `hmi/evidence/`
holds nine untracked files from another agent; none is in the pathspec and none
was touched.

No trailer is added to the message. CLAUDE.md §7 forbids generated-with footers
and any mention of tooling in a commit message, and that is the contract.

## 7. Open questions

1. **`assets/CREDITS.md` is now incomplete.** It opens "Every image in this
   directory was produced from this repository or from permissively licensed
   sources" and carries a per-file table; the two new media files have no row.
   The brief's pathspec is "exactly README.md, the two asset files and your
   report", so it was left alone rather than silently widened. Both are own
   screen captures of this repository's own simulation, HMI and PLC project —
   no third-party asset is visible — so the row is bookkeeping, not a licence
   matter.
2. **`assets/CREDITS.md` still says the vehicle "enters the demonstration at
   M5".** Under the ADR 0008 renumbering that is M6. Same pathspec reason; same
   one-line fix, and it can ride with item 1.
3. **The recording is not a gate claim.** It shows M4 items (a), (b) and (c);
   (d) the obstacle stop and (e) the heartbeat watchdog are not in this run. The
   README says nothing about M4 being met and the table still reads `next`, but
   a reader could infer more from a hero video than it demonstrates. If that is
   a concern, the fix is a clause in the caption naming what the run does not
   show, not a change to the milestone table.
