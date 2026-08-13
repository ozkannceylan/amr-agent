# m5-26 — bring the WSL machine up to the archive

    brief:               docs/briefs/m5-26-dist-upgrade.md
    status:              done

    files_changed:
      - sim/setup/WSL_ENVIRONMENT.md   (mod) new Part III, sections 14-20:
                                       the pre-checks, the snapshot, the
                                       independent libglapi verification, the
                                       simulated plan, the outcome and the
                                       three verification runs. Two Part I/II
                                       statements the upgrade falsified were
                                       corrected in place (§13.3 item 1,
                                       §13.1's "a machine like this one") and
                                       §2 gained a pointer to §20.2.
      - docs/reports/m5-26-dist-upgrade.md   (this file)

    invariants_touched:  none

## The outcome in one paragraph

**The machine is current with the archive and the vehicle stack still works.**
`apt-get dist-upgrade` ran once, 10:21:33-10:23:18 local, and did exactly what
the simulation predicted: **342 upgraded, 7 newly installed, 1 removed, 0
errors, 0 broken packages, 0 not upgraded**. The one removal was
`libglapi-mesa` and nothing else. The machine is now **0 packages behind the
archive**, with **no hold and no pin** — none was used, per the brief. All
three verifications passed: `GL_RENDERER` still reads
`llvmpipe (LLVM 20.1.2, 256 bits)` from the ogre2 log, character for character
the pre-upgrade reading; the §12.5 stack comes up with 23 nodes, all seven
managed nodes `active`, and **fatal = 0 / process-died = 0 in all three launch
logs**; and the m5-24 vehicle-image run repeats with the domain wall holding
both directions (**0 of 29** contract rows from domain 52, **29 of 29** from
domain 51) and the pass-through residual still **0.000e+00, 220 of 220 exact**.

## The judgement call the brief reserved for me

**The `libglapi-mesa` claim is confirmed, and the mechanism is better than the
report described.** I did not inherit it. Four checks (`WSL_ENVIRONMENT.md`
§16), of which the fourth is decisive: with the ogre2 log truncated first so
the reading provably belonged to that process, a **live Gazebo process that had
printed `GL_RENDERER = llvmpipe` mapped zero bytes of `libglapi`**. It renders
out of `libgallium-25.2.8` via `libEGL_mesa`/`libGLX_mesa`, none of which
declare or link the stub; the only ELFs on the whole system referencing
`libglapi.so.0` are four pre-2012 legacy DRI drivers.

Reading `dpkg`'s installed control fields rather than `apt-cache rdepends`
mattered: the cache lists four Mesa packages as dependants because their *older*
versions were, and dpkg shows the truth — exactly one installed dependant.

And it is **not an orphan being dropped**. The new `libgl1-amber-dri` stops
depending on Mesa's stub and ships its own private copy as a new package,
`libglapi-amber`. The file never leaves the machine; its owner changes.
**Nothing loses a library.**

## What I stopped on, and what I did not

Exactly **one** removal was proposed, so the brief's stop condition was not
met and I proceeded. But the plan also added **five NVIDIA-580 packages** on a
machine that renders in software, which I traced before accepting rather than
waving through: `libnvidia-gl-570` is itself upgraded and the new 570 *depends
on* `libnvidia-gl-580` — Ubuntu's driver-series transition. It is an addition,
not a removal, so not a stop condition, **but it was not cosmetic**: this
machine registers NVIDIA as an EGL vendor at priority 10 ahead of Mesa at 50,
and `libEGL_nvidia` is genuinely loaded into the render process. It moved:
`libEGL_nvidia.so.0` now points at **580.173.02**, was 570.211.01. The
post-upgrade `GL_RENDERER` reading was taken with the new vendor in place and
still says llvmpipe. That is the one real risk in this upgrade and it is
answered by measurement, not by argument.

## Three findings worth more than the upgrade

1. **`warehouse.sdf` alone cannot give you a renderer reading, and
   `GL_RENDERER` is not in Gazebo's console output.** gz-sim creates the render
   context lazily, only when a rendering sensor exists; the warehouse without
   the forklift spawned has none, so a 45 s run yields a log with no `GL_` line
   — which reads like a failure and is not one. The reading lives in
   `~/.gz/rendering/ogre2.log`, and `cell.sdf` (the `gpu_lidar` photo-eye) is
   the cheap standalone probe. Truncate the log first or you may be reading the
   previous run.
2. **`ros2 lifecycle get` returned "Node not found" for a node that was
   `active`,** in both runs, and always for the *first* query after a fresh CLI
   daemon. Cross-read via `ros2 service call /<node>/get_state` it was `active`
   every time. A cold daemon graph cache is not a node state. The same stale
   daemon also explains a leftover process my sim-side check counted.
   **`ros2 daemon stop` belongs in the teardown**, beside the `pkill` and the
   `/dev/shm` clear.
3. **The real coherence gain is not the count.** The four Fast-DDS packages
   m5-21 realigned did **not** move — they were already today's builds, which
   is why they collided. What moved is the *other half of the ABI pair*:
   `rosidl-typesupport-fastrtps-c/-cpp` 3.6.3 (January) -> 3.6.4 (June). §12.2's
   `undefined symbol` was a January typesupport calling a February Fast-CDR.
   m5-21 closed that gap by dragging Fast-DDS forward; this closes it by
   bringing the typesupport up to meet it. The tree is coherent in one
   direction rather than patched in two.

Also recorded: **two `MISS` lines in §2's package survey were already wrong
before this upgrade** — `joint-state-publisher` and `joint-state-broadcaster`
are in the *pre*-upgrade snapshot, so they arrived with m5-21's dependencies
and the survey was never refreshed. A pasted package survey is a measurement
with a date on it.

## Nothing was tuned, and the timing is reported not chased

No parameter, launch file, config or value was changed to make any verification
pass. The pass-through latency landed at the committed sample
(mean 0.0004 s / max 0.0011 s). **That is not a confirmation** any more than
§12.6's 60x spread was a regression — it is one more draw of a quantity already
shown to be a sample (LESSONS 2026-08-04). The residual is the half that is a
property of the design, and it has now reproduced exactly in **seven** recorded
runs across two packagings, a per-vehicle domain and a 342-package upgrade.

The costmap inflation-radius `[ERROR]` lines (3 in the §12.5 run, 4 in the
vehicle-image run) are the pre-existing advisories §12.5 already names. Same
text, same sites. Not touched.

Machine discipline: both runs were preceded by a verified-clear check, isolated
on **both** transports (`GZ_PARTITION` *and* `ROS_DOMAIN_ID` — LESSONS
2026-07-27), serialised never two simulators at once, driven to completion in
the foreground with bounded polling, and torn down to zero with `/dev/shm`
cleared. The dist-upgrade itself was detached *inside WSL* so no tool timeout
could kill apt mid-transaction, then polled to completion.

**No password was requested, handled, stored or echoed at any point**, and none
appears in the repository (invariant 13). Everything privileged ran through
`wsl.exe -u root -e bash -lc`.

## Rollback

`/root/m5-26-snapshot` (copied readable to `~/m5-26-snapshot`): selections, all
2232 versions before and 2238 after, 400 `ros-jazzy-*` before / 401 after,
holds, apt history, the simulated plan and `distupgrade.log`.
**`/root/m5-21-snapshot` is untouched**, including `libfastcdr.so.2.2.5` — still
the only copy of a build the archive has deleted. Nothing needed restoring.

Worth stating: **a rollback is no longer a one-file rescue.** On a current tree
every installed version is still in the archive, so the after-list is a
re-installable list rather than a historical record. That is the property
staying stale had removed.

## open_questions

1. **The `install.sh` one-line guard removal (m5-21b Decision 2) was NOT
   made.** It is a separate deliverable for the `sim` agent and bundling it
   here would have been two deliverables in one brief. It is now **lower
   urgency but not obsolete**: on a coherent tree the collision cannot occur,
   but the guard still means a re-run of the script skips the DDS step on a
   machine that has drifted again.
2. **Only the pass-through observation was re-run.** `WSL_ENVIRONMENT.md`
   §13.3 item 3's other five `EVIDENCE_ENVELOPE.md` observations — enable-drop,
   stale, clamp, release, permit — remain un-re-run, now against a tree that
   has moved again. They are stopping distances and reaction times, exactly the
   class of figure the 60x spread would move.
3. **Every evidence file measured before today is now qualified by an
   environment that no longer exists** (LESSONS 2026-07-27). This upgrade moved
   288 ROS packages under `EVIDENCE_VEHICLE_IMAGE.md`, `EVIDENCE_NAV2.md`,
   `EVIDENCE_ENVELOPE.md` and `EVIDENCE_LOCALIZATION.md`. Their §0 environment
   blocks name package versions that have changed. Those files are outside this
   brief's write scope; the qualifier is **requested, not made**, and the
   cheapest form is a one-line pointer from each §0 to `WSL_ENVIRONMENT.md`
   §18.1/§20.2 rather than a re-run of everything.
4. **m5-24 §5's Nav2 route abort (`error_code 104`) is untouched** and remains
   its own open question. This brief verified the stack comes up and the
   boundary and residual hold; it did not re-open route following, and nothing
   here should be read as evidence either way about it.
5. **A verification detail, stated because it is a flaw in my run and not in
   the machine:** in the §12.5 bringup my helper parsed AMCL's initial yaw as
   `0.000000` instead of `-0.007915` (the regex matched the world-frame line
   first), so that run's prior was 0.45 deg off. It does not affect what that
   run tested — node set, activation, process deaths — and the vehicle-image
   run in §19.3 takes its pose from `F001.yaml` and was correct. Recorded so
   nobody reads that run as a localization-accuracy result.

## next_suggested

Brief `sim` for the one-line `install.sh` DDS-guard removal (m5-21b Decision 2,
still open), and `agv-ros2` for the §0 environment-block pointers in the four
`agv/forklift/EVIDENCE_*.md` files plus the five un-re-run observations.
