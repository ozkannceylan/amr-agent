# m5-21b — two install decisions: the held-back archive and the Fast-DDS pin

    brief:               follow-up to docs/briefs/m5-21-wsl-ros-stack-install.md
                         (advisory; two decisions, one recommendation each)
    status:              done

    files_changed:
      - docs/reports/m5-21b-install-decisions.md   (this file, only change)

    invariants_touched:  none

## The two recommendations

**Decision 1: do not keep the machine pinned behind the archive — catch it up,
in one owner-scheduled brief with a Gazebo re-run as its exit criterion. The
`libglapi-mesa` removal that blocked this is verified harmless: nothing on the
machine that renders anything still uses that library.** **Decision 2:
`install.sh` is the right home for the Fast-DDS step and it should stay there;
the one real gap is that the step is skipped when the script has nothing to
install, and the fix is to make it unconditional (one line, `sim` agent).**

## Decision 1 — the machine should catch up, and the scary removal is hollow

Plain-language glossary for this section: the **archive** is the online package
repository; **dist-upgrade** is the apt command that brings everything current
and is allowed to remove packages while doing it; **Mesa** is the graphics
library stack, and **llvmpipe** is its CPU-only renderer, the one every Gazebo
run on this machine uses (LESSONS 2026-07-27: measured, no GPU here).

The m5-21 agent stopped because the upgrade simulation proposed removing
`libglapi-mesa` and Mesa is load-bearing. That caution was correct under its
brief. Verified today with simulation and queries only (nothing was changed):

- The Mesa that actually renders is **already current**. `libgl1-mesa-dri`,
  `libglx-mesa0`, `libegl-mesa0` and `mesa-libgallium` — the packages
  containing llvmpipe — are all at 25.2.8, the exact version §4.7's Gazebo log
  printed (`GL_RENDERER = llvmpipe ... Mesa 25.2.8`).
- `libglapi-mesa` is a **leftover stub from Mesa 24**. In Mesa 25 its contents
  moved into `mesa-libgallium`. None of the installed GL libraries declare a
  dependency on it, and `ldd` shows none of them link it.
- The only installed package still depending on it is `libgl1-amber-dri`, the
  driver for pre-2007 Intel/ATI graphics hardware — hardware this WSL machine
  does not have and llvmpipe never touches. dist-upgrade upgrades amber-dri
  and then drops the now-orphaned stub. That is the whole removal.

So "removes libglapi-mesa" is apt tidying up after a Mesa upgrade that in
practice already happened, not apt reaching for the renderer.

**Why catch up rather than stay pinned.** Staying behind is not a stable
state on this archive; it is the condition that caused the m5-21 outage:

1. **Every future install repeats the collision.** packages.ros.org serves
   only today's builds. Installing any new ROS package onto a stale tree pairs
   a new library against old ones — that is exactly the exit-127 /
   undefined-symbol death m5-21 spent a day diagnosing, and it will recur
   package by package for as long as the tree is stale.
2. **There is no rollback while stale.** The archive deletes old builds:
   `fastcdr` 2.2.5 is already gone, and the machine's only copy is one saved
   file in `/root/m5-21-snapshot`. A pinned machine that ever breaks cannot
   reinstall what it has.
3. **A mixed tree is the disease.** 342 packages are behind (~287 ROS, ~55
   Ubuntu; unattended-upgrades takes security fixes only). The one coherent
   state this archive offers is "all from today's snapshot".

**The middle path exists but is not needed as protection.** Plain
`apt-get upgrade` (which never removes anything) covers 336 of the 342 and
would leave the stub in place. Holding packages via `apt-mark hold` or apt
pinning is the wrong tool here: the Fast-DDS lesson is that these packages
must move *together and forward*, and a hold blocks exactly that. Since the
one removal is verified harmless, the simple full dist-upgrade in a single
sitting is the honest move.

**Conditions on the catch-up brief** (unchanged from m5-21's request, now
with the Mesa question answered): its own brief, snapshot first as in §13.2,
`/dev/shm` cleared after (the Fast-DDS entry, LESSONS 2026-08-05), and
`done_when` includes a Gazebo render check (`GL_RENDERER` read from the log)
plus the full vehicle-stack bringup of `WSL_ENVIRONMENT.md` §12.5. Expect the
timing figures to move — the four m5-21 re-runs already showed they are
samples, not bounds — while the zero-residual results must reproduce.

**Uncertainty, stated.** The verification above covers the renderer question
completely, but 342 packages moving at once can surprise in ways no
simulation shows (a config default changing, a launch-file deprecation). That
is why the recommendation is "one scheduled brief with a re-run attached",
not "run it tonight". Nothing found today suggests a specific second risk.

## Decision 2 — install.sh is the right home; make the step unconditional

Yes, the script is the right place. The test is the brief's own: a fresh
machine following `install.sh` end to end gets a working stack — on a
one-snapshot machine the `--only-upgrade` step is a no-op, on a stale machine
it is the step that makes Nav2 start. The constraint is a durable property of
this install path, and the script is the only artifact a future machine is
guaranteed to execute. An apt preferences/pin file would be worse: it
enforces stasis, and the requirement is coherent motion, not stasis.

Two findings, one worth a one-line change:

1. **The step is skipped exactly when the owner's machine would re-run the
   script.** The DDS block runs only `if [[ ${#MISSING[@]} -gt 0 ]]` — only
   when the script just installed something. On a machine where all ROS_PKGS
   are present but someone later hand-installs a new ROS package (the m5-21
   failure mode), re-running the script does nothing. Since `--only-upgrade`
   is already a no-op on a current machine, the guard buys nothing and costs
   this hole. Recommend the `sim` agent drop the `if`, running the DDS align
   unconditionally.
2. **Discoverability is adequate for script users, absent for hand
   installers.** Someone who types `apt install ros-jazzy-<new>` by hand never
   reads the script. That reader's path is `WSL_ENVIRONMENT.md`, which already
   carries the recipe (§13.1) and the full post-mortem (§12), and
   `docs/LESSONS.md` 2026-08-05, which carries the rule. No further file is
   needed; the catch-up under Decision 1 dissolves the hazard anyway, because
   on a current tree the collision cannot occur.

## open_questions

1. Decision 1 is a recommendation, not an execution: the dist-upgrade remains
   the owner's call and needs its own brief (it mutates the measured
   environment every evidence file is qualified by).
2. The one-line `install.sh` guard removal (Decision 2, finding 1) is outside
   this task's write scope and is requested, not made.

## next_suggested

If the owner accepts Decision 1, brief `infra` for the dist-upgrade with
snapshot + Gazebo re-run + §12.5 bringup as done_when; brief `sim` for the
one-line install.sh guard removal either way.
