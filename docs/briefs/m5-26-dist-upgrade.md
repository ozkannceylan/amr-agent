# m5-26 — bring the WSL machine up to the archive

    gate:                M5 (supporting; not a gate criterion)
    agent:               infra   (owner-approved, 2026-08-05)
    goal:                The WSL machine is current with the archive in one coherent step, and the vehicle stack is shown still working afterwards — or restored and reported broken.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-21b-install-decisions.md — the plan you are executing, especially its conditions
      - docs/reports/m5-21-wsl-ros-stack-install.md §13.2 (the snapshot recipe) and §12 (the Fast-DDS post-mortem)
      - sim/setup/WSL_ENVIRONMENT.md — especially §12.5, the verified bringup
      - agv/forklift/EVIDENCE_VEHICLE_IMAGE.md (the m5-24 run to repeat)
      - docs/LESSONS.md
    deliverable:         the upgraded machine, sim/setup/WSL_ENVIRONMENT.md updated, and the verification recorded in it
    done_when:           Gazebo's `GL_RENDERER` still reads llvmpipe from the log, the full vehicle stack of §12.5 comes up with Nav2 active and no process deaths, the m5-24 vehicle-image run repeats, and the before/after package state is recorded. If any of those fails: restore, report BLOCKED, and say exactly what broke.
    forbidden:
      - running while another agent holds the machine — check first (LESSONS 2026-07-30)
      - tuning, editing or "fixing" anything to make a verification pass
      - writing outside sim/ except your report
      - handling, requesting or storing any password (use `wsl.exe -u root -e bash -lc '...'`, verified working)
      - `apt-mark hold` or apt pinning — m5-21b rejected them: this set must move together and forward

---

## 1. Why, in one paragraph

The machine is 342 packages behind and that is not a stable resting place — it
is the condition that produced the m5-21 outage. packages.ros.org serves only
today's builds, so every future install pairs a new library against old ones,
and **there is no rollback while stale**: `fastcdr` 2.2.5 is already deleted
from the archive and this machine's only copy is one saved file in
`/root/m5-21-snapshot`. The owner ruled on 2026-08-05 to catch up.

The removal that stopped m5-21 is verified hollow (m5-21b): `libglapi-mesa` is
a Mesa-24 stub, the packages that actually contain llvmpipe are already at
25.2.8 — the version the Gazebo log prints — and the only installed dependant
is `libgl1-amber-dri`, a pre-2007 GPU driver. **Verify that claim yourself
before you rely on it**; it is a report's claim, not yours.

## 2. Order — do not vary it

1. **Check the machine is yours.** No other agent, simulation or bridge
   running. Record what you checked.
2. **Snapshot** per m5-21 §13.2: `dpkg --get-selections`, the `ros-jazzy-*`
   versions, `apt-mark showhold`, and the apt history tail. Write it into the
   evidence **before** anything changes. This is the rollback record and it is
   worth more than the upgrade.
3. **Simulate**: `apt-get -s dist-upgrade`. Record the full plan — counts, and
   every REMOVE by name. **If anything is removed beyond `libglapi-mesa` and
   packages you have shown to be equally inert, stop and report** rather than
   accepting apt's offer.
4. **Upgrade.**
5. **Clear `/dev/shm`** afterwards (the Fast-DDS entry, LESSONS 2026-08-05).
6. **Verify** — §3.
7. Record what actually happened, not what step 3 predicted.

## 3. Verification — the deliverable

1. **The renderer.** Start Gazebo and read `GL_RENDERER` **from the ogre2 log**,
   not from an assumption — LESSONS 2026-07-27 is explicit that a DRI node
   proves nothing. It must still be llvmpipe.
2. **The stack.** `sim/setup/WSL_ENVIRONMENT.md` §12.5's bringup: Nav2 nodes
   `active`, zero process deaths, zero fatals.
3. **The vehicle image.** Repeat the m5-24 run: the domain wall still holds
   (contract rows present from the vehicle's domain, absent from another) and
   the pass-through residual is still `0.000e+00`.
4. **Record versions** before and after for everything that matters, so the
   machine is reproducible from the document.

Timing figures are expected to move and are **not** a failure — they were
already shown to be samples, not bounds (m5-21). Report them; do not chase them.

**If a verification fails**: restore from the snapshot as far as you can, report
status **BLOCKED**, and state precisely what broke and what you restored. That
is a correct outcome. Leaving the machine broken and quiet is not.

## 4. Working discipline

- **Write into the evidence as you go.** The snapshot before the upgrade, the
  apt plan before you execute it.
- **Do not commit.** The orchestrator commits by pathspec.
- Write `docs/reports/m5-26-dist-upgrade.md` in the CLAUDE.md §5 format.
- Read `docs/LESSONS.md` first.
