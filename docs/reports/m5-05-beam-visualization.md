# Report m5-05 — lidar beams visible in the Gazebo GUI, with a measured cost

```
brief:               docs/briefs/m5-05-beam-visualization.md
status:              done
files_changed:       [sim/worlds/forklift_arena.sdf,
                      sim/worlds/FORKLIFT_ARENA_EVIDENCE.md,
                      sim/worlds/evidence/m5-05-gui-no-beams.png,
                      sim/worlds/evidence/m5-05-beams-safety-scanner-front-strips.png,
                      sim/worlds/evidence/m5-05-beams-nav-lidar-strips.png,
                      sim/worlds/evidence/m5-05-beams-nav-lidar-rays.png,
                      sim/worlds/evidence/m5-05-beams-nav-lidar-3dview-service.png,
                      sim/worlds/evidence/m5-05-beams-nav-lidar-launch-guitrue.png,
                      sim/worlds/cell.sdf,
                      sim/worlds/warehouse.sdf]
invariants_touched:  none
open_questions:      see below
next_suggested:      re-capture section 9's figures on the owner's WSL host before the M5 showcase is recorded; they are container evidence and do not transfer.
```

## What was already done, and by whom

The `<gui>` block in `sim/worlds/forklift_arena.sdf` was authored by the agent
lost to the container suspension and committed as `9d532ab` **without a single
line of it having been run**. This report is the verification it never got, plus
the evidence section its own comments already pointed at, plus corrections to
four claims in it that the run disproved.

| Part | Authored by | Verified live |
|---|---|---|
| the `<gui>` block, nine plugins | lost agent, `9d532ab` | yes — loads, all nine present, world still `Valid` under `gz sdf -k` |
| that the beams can be drawn at all | claimed, untested | yes — see below |
| the render-budget figures | promised as "section 9", section 9 did not exist | measured here |
| the beam screenshots | promised, none taken | taken here, six files |
| four factual claims inside the block's comments | untested | **three wrong, corrected here** |

## Verified live

**The plugin loads and the beams draw.** Under `Xvfb :99` in this container,
`GZ_PARTITION=m505_render` / `ROS_DOMAIN_ID=82`,
`GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)` read from a freshly deleted
`ogre2.log`. Six captures are committed under `sim/worlds/evidence/`; the one
the gate asks for is `m5-05-beams-nav-lidar-rays.png` — the navigation lidar's
360-ray sweep, `Visual Type: Rays`, panel showing `/forklift/gz/scan_nav`,
`Min. Range 0.100000`, `Max. Range 8.000000`.

The instrument for "drawing" is not the picture. `VisualizeLidar` subscribes to
exactly the gz topic its combo box has selected, so `gz topic -i` is a
non-visual proof of the same fact, and it was taken at every step
(`FORKLIFT_ARENA_EVIDENCE.md` §9.2).

**The render budget, measured, quoted as the tool printed it** (§9.3). Every
figure is Δsim/Δreal between two `/stats` messages 60 s of wall clock apart,
both kept verbatim, because `real_time_factor` on `/stats` is published **once
per physics iteration** here — 500 Hz — and is an instantaneous value that
ranged `0.4803` to `3.3703` inside one 60-sample capture. A single reading of it
would have been a fabricated number.

| Configuration | RTF over the window |
|---|---|
| headless, server only, 910 rays | `0.9980` |
| GUI attached, plugin loaded, no topic selected | `0.9165` |
| GUI, beams **on**, navigation lidar, Triangle Strips | `0.8923` |
| GUI, beams **off** (checkbox), subscription held | `0.9174` |
| GUI, beams **on**, navigation lidar, **Rays** | `0.8893` |
| GUI, beams **off** again (drift bracket) | `0.9137` |

- **Headless is still real time at 910 rays**: `0.9980`, against `0.99984` for
  the M4 181-ray set.
- **The GUI costs ~8 points of RTF; the beams cost ~2.5.** The GUI is roughly
  three times the cost of the thing it was added to show.
- **Rays and Triangle Strips cost the same here**, `0.8893` vs `0.8923`, inside
  the drift bracket the two beams-off readings define. Points was not measured.
- **Is the GUI usable here? Yes**, at 1200x1000 with beams on: responsive to
  clicks, beams updating, `0.89` of real time. That is a container finding.

A second, earlier session (front safety scanner selected before the navigation
lidar) gave `0.8221` Rays / `0.8371` Strips / `0.8397` beams-off — the same
within-session ordering, about 0.08 lower at every state. Both sets are in §9.3.
The deltas above are all taken *within* a session and never across the two.

**The launch file's own `gui:=true` path** was exercised separately (§9.6): one
command, 8 bridge lines, 0 ERROR lines, beams on screen, and two subscribers on
`/forklift/gz/scan_nav` (the bridge and the plugin). It costs the bridged scan
rate: `average rate: 9.995` headless against `average rate: 8.488` with the GUI,
on a sensor declared at 10 Hz.

## Corrections to the block as authored

1. **"the plugin takes no topic parameter from SDF"** — not verifiable as
   stated (`VisualizeLidar::LoadConfig` does receive an `XMLElement`). Replaced
   with what was measured: with this block the combo box comes up **empty** and
   there is **no gz subscriber** on any of the three scanners until a human
   presses refresh.
2. **The auto-selection hazard was missing entirely.** Refresh selects entry
   zero of a sorted list, which is
   `/forklift/gz/safety_scanner_front/measurement`. **The first beams a viewer
   sees are a safety scanner's non-safe measurement channel, not the navigation
   lidar** (entry two). A showcase that leaves the default selection shows the
   wrong sensor under the one caption this project must never get wrong
   (invariant 1). Written into the block and into §9.2, with a capture.
3. **"Rays ... the most expensive of the three"** — not supported. Measured at
   `0.8893` against Triangle Strips' `0.8923`, i.e. equal within the spread.
   Corrected to the measured statement.
4. **"the `/gui/screenshot` service ... is how the beam capture was taken"** —
   it could not have been; nothing had been captured. The service does work,
   and it behaves unlike its request field: the `StringMsg` is a **directory**,
   the plugin names the file from the capture timestamp, and it captures the 3D
   view only (831x952, no panel). It returns `data: true` even for a request
   that writes no file. All three behaviours were tested (§9.4).
5. **The `WorldStats` comment** claimed the plugin is the instrument the budget
   is read from. It is not, for the reason above; corrected to "corroboration",
   with the observed collapse to a percentage-only strip at this window size
   recorded.

Also corrected, in the world's SENSOR SYSTEM comment: it described "the vehicle
scanner" singular and named the deleted `/forklift/gz/scan`. Now three scanners
and the current names, with the 910-ray figure and a pointer to §9.

## The pre-existing XML comment defect, fixed in all three worlds

`--` inside an XML comment is forbidden by the spec. Gazebo's parser tolerates
it; Python's `ElementTree` does not, so it blocked any Python-based SDF
validation. Before:

```
sim/worlds/forklift_arena.sdf  not well-formed (invalid token): line 509, column 49
sim/worlds/cell.sdf            not well-formed (invalid token): line 15, column 8
sim/worlds/warehouse.sdf       not well-formed (invalid token): line 16, column 20
```

Three edits, **comment text only, no semantic change**: `gz model --list`
reworded to "`gz model` ... under its list flag"; the ASCII-art rules in
`cell.sdf` and `warehouse.sdf` redrawn with `=` instead of runs of `-` (both
also contained a literal `-->` inside the art, which terminates the comment
early for a strict parser). All three files now parse under `ElementTree` **and**
report `Valid` under `gz sdf -k`, and `forklift_arena.sdf` still reports 13
models. The defect was found and fixed in `warehouse.sdf` and `cell.sdf` as
well, not only in the file this brief owns.

## Open questions

1. **The figures are container evidence and do not transfer.** The owner's WSL
   host reports the same `llvmpipe (LLVM 20.1.2, 256 bits)`, which makes them
   plausible there and not measured there. The M5 showcase recording needs its
   own capture (LESSONS 2026-07-27).
2. **A parallel session was running the same world with a GUI throughout the
   first half of this work**, `GZ_PARTITION=vizshot5150` / `ROS_DOMAIN_ID=91`,
   at 190–290 % CPU on a 4-core box, and three commits (`6d03f81`, `121f823`,
   `2cf2bce`) landed in `sim/` while this agent was editing it. No measurement
   in §9 was taken while it ran — this agent polled until the machine was clear
   — but it cost about 25 minutes and the two sessions could have collided on
   `sim/worlds/`. Two agents were briefed onto adjacent `sim/` ground at once.
3. **The between-session spread (about 0.08 RTF) is larger than the beam cost
   it brackets.** The plausible cause is a lidar visual left in the scene by the
   first topic selection; unproven. If a later gate needs a beam-cost figure to
   better than 0.03 RTF it needs a purpose-built repeat, not these runs.
4. **Nothing was measured with the vehicle moving.** Every row was taken with
   the forklift standing at its spawn pose.
5. **Verification tooling was installed into the container** — `xdotool`,
   `imagemagick`, `x11-apps` — to drive and capture a GUI with no human at the
   window. They are **not** in `sim/setup/install.sh` and this report does not
   propose adding them: they are needed to *verify* a GUI, not to *run* one. If
   a later gate wants automated GUI capture in CI, that is a dependency proposal
   of its own.
6. **`sim/README.md` gained no pointer to `sim/worlds/evidence/`.** It was being
   rewritten by the parallel session during this work and was left alone
   deliberately. The six files are enumerated in `FORKLIFT_ARENA_EVIDENCE.md`
   §9.4.
