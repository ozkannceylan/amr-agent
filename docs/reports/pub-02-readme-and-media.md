# Report pub-02 — public README and media

brief:               docs/briefs/pub-02-readme-and-media.md
status:              done
files_changed:
  - README.md (rewritten; was a single `# amr-agent` line)
  - assets/plc-drives-cell.gif (hero, copied from the scratchpad)
  - assets/demo-cell.png (copied from the scratchpad `cell.png`)
  - assets/rb-kairos-gazebo.png (new — own Gazebo render, see below)
  - assets/CREDITS.md (new — provenance and the vendor BSD-3-Clause notice)
invariants_touched:  none
open_questions:
  - `.gitattributes` has no explicit rule for `*.png` / `*.gif`. All three new
    assets are correctly detected as binary today (first NUL at byte 8, 8 and
    11 respectively, well inside the 8000-byte heuristic window), so this is
    not a blocker and nothing is at risk right now. But LESSONS 2026-07-27
    ("mark generated binaries `-text` explicitly rather than trusting
    detection") applies, and `.gitattributes` is outside this brief's write
    scope. Requesting two lines beside the existing `*.pgm -text` / `*.gz -text`:
    `*.png -text` and `*.gif -text`.
  - The AMR render is honest but unflattering: the vendor's chassis material is
    `Gazebo/Black`, so under llvmpipe the base reads as a near-black mass with
    the mecanum wheels carrying the shape. It is recognisably an RB-Kairos and
    it is the project's own render, which is what the brief required. If a
    better image is wanted later, the fix is a lighter scene material override,
    which would no longer be the vendor model unmodified — an explicit
    trade-off rather than something to do silently.
next_suggested:      Commit by pathspec (`README.md assets/`), then decide the two `.gitattributes` lines above as a separate one-line change.

---

## What was delivered

A visual-first README: hero GIF, simplified mermaid topology, the cell image
with the equipment table, the PLC-side watch table referenced in place, four
measured figures, the milestone table, and a short "how it is built" section.
1134 words, 169 lines, four figures, five tables.

The equipment table states plainly, in the line directly above it, that the
visuals are deliberately minimal because the subject is the control
architecture, and each row maps a visual object to the control equipment it
stands for and to its authoritative OPC UA node names (taken from
`docs/interfaces/opcua-nodes.md` §9, not from `sim/README.md`'s proposed
names). The red mushroom's row says it is a process stop with no safety
integrity and that the e-stop chain arrives at M4 and never crosses the
network.

## Figures — each traced to a committed file

| Figure in README | Source of the claim |
|---|---|
| 20.00 Hz, 14 244 cycles, 1 overrun of 3.93 ms, 0 read/write errors | `bridge/EVIDENCE_LATENCY.md` §B2.3 |
| Closed-loop median 46.8 ms, stated as an upper bound quantised by the 50 ms poll | `bridge/EVIDENCE_LATENCY.md` §B.6 |
| 2.301 s freeze-to-reaction, inside the specified [2.1, 3.2] s window | `bridge/EVIDENCE_SIGNAL_LOSS.md`, `EVIDENCE_LATENCY.md` §B2.7a |
| CPU cycle 1.004 / 1.023 / 2.556 ms | `plc/demo-cell/evidence/watch-table/Screenshot 2026-07-28 174127.png` |

Two figures were deliberately not written as the brief phrased them, because
the evidence does not support the phrasing:

- **"20 Hz / 0 overruns"** is true of part 1 (§B.3, four sessions) but the
  latest run, §B2.3, records **one** overrun of 3.93 ms in 14 244 cycles. The
  README quotes the later run with its overrun and its size rather than the
  cleaner earlier one.
- **"CPU cycle ~1 ms on a 20 ms OB30"** — §B2.9 says explicitly that the
  capture is TIA's *CPU cycle-time* panel and does not itself name the OB30
  period; the 20 ms is `SPEC.md` §3.3's configured value. The README says
  "against the program's configured 20 ms OB30 period".

The closed-loop cell also notes that §B2.5 finds the same cluster on a later
build, rather than implying §B2.5 produced 46.8 ms itself (its own median is
46.163 ms).

Milestone table: gate numbers and deliverable names are copied verbatim from
`docs/roadmap.md`, all twelve rows M0–M11, with a status column reading
M0–M2 **done**, M3 **closing**, M4 next, M5–M10 planned, M11 parked. All 29
relative links in the README were checked to resolve against the working tree.

## The AMR render — it made it in

Time-boxed attempt succeeded. Sequence, so it is reproducible:

1. Platform from ADR 0002: Robotnik RB-KAIROS, vendor ROS 2 description at
   `jazzy-devel`. Cloned **outside the repo** (scratchpad, then a WSL-native
   working dir for render speed), never vendored.
   `robotnik_description` at `4bc7342`, `robotnik_sensors` at `fe92315`.
2. **Licence verified before any mesh was used**: both packages carry a
   BSD-3-Clause `LICENSE` (`package.xml` declares `BSD-3-Clause` and `BSD`
   respectively). The notice is reproduced in `assets/CREDITS.md` as that
   licence requires for redistribution. No vendor marketing image was used or
   considered.
3. `robots/rbkairos/rbkairos.urdf.xacro` expanded with `xacro` against a
   minimal ament-index overlay; `robotnik_sensors` is a separate repo and is
   required (the xacro includes `all_sensors.urdf.xacro`). All eight mesh
   references resolve inside the two BSD packages.
4. `gz sdf -p` to SDF, embedded unmodified into a purpose-built showcase world
   (ground plane, three directional lights, light background). Gazebo Harmonic
   8.11.0 under WSL, `GZ_PARTITION=kairos_shot`, `ROS_DOMAIN_ID=93`,
   `GL_RENDERER = llvmpipe` as expected (LESSONS 2026-07-27 — no hardware
   acceleration claimed).
5. Capture: Windows-side `CopyFromScreen`, cropped to the viewport, 1100x800.

Three capture dead ends worth recording, all cheap:

- `grab.ps1`'s default `-TitleMatch "Gazebo Sim"` **substring-matches an
  unrelated Chrome tab** whose title contained "Gazebo Simulation", and it
  silently screenshotted the browser. The match must be the exact title
  `Gazebo Sim (Ubuntu)`.
- Even with the right window, `SetForegroundWindow` is refused when another
  app owns the foreground, so the capture returned whatever was on top —
  a second wrong screenshot. `WScript.Shell.AppActivate($pid)` before the grab
  is what made it reliable.
- Two attempts to avoid the owner's screen entirely both failed and were
  abandoned: a server-side camera sensor with `<save enabled="true">` wrote no
  frames, and the GUI `/gui/screenshot` service returned `data: true` and
  wrote no file anywhere on the filesystem.

Cleanup: no Gazebo processes left running, and the 412 MB WSL clone was
removed (the pinned commits in `assets/CREDITS.md` make the render
reproducible from scratch). The generation scripts remain in the session
scratchpad.
