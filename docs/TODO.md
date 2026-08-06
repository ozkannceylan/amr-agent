# TODO

Open items only. M5 (sensored autonomous forklift, ADR 0010 D2) is the open
gate; M4 (forklift commissioning, ADR 0008) is closing, on the owner's
recorded commissioning showcase and the m4f-09 gate verification. The m5r
restructure round (ADR 0010) is closed; the brief queue lives in
docs/PLAN.md.

## m5-12b — the intrusion now originates in Gazebo (2026-08-06)
`agv/forklift/EVIDENCE_FIELD_EVALUATION.md`, report m5-12b. A box moved into
the contour drove `ZoneDeviceCircuitClosed` with **no `OPERATOR` line anywhere
in the writer's session** — four transitions, all sourced `FIELD`. The control
case is what makes it mean something: an object 2.85 m away and plainly visible,
but outside the 1.35 m contour, produced **no verdict**.

- **CRITERION (a) IS NOT CLOSED, and this is the remaining step.** The chain is
  proven Gazebo → `ZoneDeviceCircuitClosed`. It is **not** shown through to
  `ZoneStopDemand`, which needs a **watch table under activated safety mode** —
  **owner work at the tool.** No gate criterion may claim the demand until then.
- **DESIGN DEFECT, correct before the next field brief:** `FIELD-EVALUATION.md`
  §6's rear clip band reads `-72.3°`, which rounds the measured `-72.26°`
  (`EVIDENCE_SENSOR_COVERAGE` §13.2) **the wrong way** and leaves indices 5 and
  65 — self-returns at 0.780 m and 0.164 m against boundaries of 1.001 m and
  2.183 m — **inside the field, holding the verdict at INTRUSION for ever.**
  m5-12b used the measured index set instead and requested the fix rather than
  editing another brief's deliverable. Done when §6 carries the measured set.
- **TOOL BROKEN, needs its own brief:** `agv/forklift/scripts/sensor_coverage.py`
  no longer runs against `model.sdf` — `load_model` reads
  `lidar/scan/horizontal` for every `<sensor>` and the IMU has none, so it dies
  with an `AttributeError` before printing a line. **This is the tool that
  produced all of `EVIDENCE_SENSOR_COVERAGE.md`**, so that evidence is currently
  unreproducible.
- **`nav2.yaml`'s reverse cap moved −0.60 → −0.55** as FIELD-EVALUATION §5/§12
  require. That **invalidates every reverse-travel figure in
  `EVIDENCE_NAV2.md`** — which now compounds with m5-40's finding that the
  reverse defect is real and un-masked. Both belong in the same reverse brief.

## Deferred by the owner 2026-08-06 — do not block the presentation
Three design decisions from m5-50, ruled deferred because none affects what the
showcase demonstrates. Recorded so a later reader does not rediscover them as
defects.

- **Silence on the torque-off demand link is NOT torque-off.** Deliberate, and
  the opposite of the field topic's rule. The envelope's own staleness already
  stops the vehicle in ~520 ms; making silence trigger torque-off would demand a
  safety reset after every network hiccup. **If asked at the presentation:** the
  link dying stops the vehicle through the envelope; torque removal needs an
  explicit demand.
- **The fork does not settle under torque removal.** This is correct behaviour,
  not a gap — a raised fork that dropped on torque loss would be a hazard.
- **The holding brake has no slip torque.** Ideal brake, holds indefinitely. Only
  matters on a gradient with load, which no demonstration uses.

## PLC — M5 BUILD LANDED 2026-08-05 (merge c9a4c77, local only, not pushed)
Built in one owner-driven TIA session on `safe_amr` (CPU 1513F-1 PN, PLCSIM
instance `safecell3`). The authoritative account is
`plc/forklift/TIA-BUILD-PROCEDURE.md`'s progress block and record table — read
it before trusting any summary, including this one.

**True now that was not:** the §12 node set is on the CPU and was read back by a
third-party client, with the write on `Forklift/Envelope/ForkliftMotionEnable`
**refused by the server** (`BadNotWritable`); the §14 delta runs and its §14.9
cold-start signature was observed in full; **HMI v2a connected to the live CPU
for the first time** (8 writable + 23 read-only, no browse failure) and drove
`HmiProcessStopRequest` TRUE → FALSE → TRUE end to end; the m5-03b stand-in
proof now stands on `safe_amr` rather than the deleted probe copy, with two
independent witnesses agreeing on every transition and every non-transition;
and the §4.5 F-delta is in the CPU — collective F-signature `AA735E2A` →
`2BC94038`, the S015 disclosure naming exactly the four `SafetyInputStandIn`
members and nothing else, the cross-reference showing four reads and zero
writes, and an external client proving the F-side and the stand-in DB are
**absent from the server's address space** (`DataBlocksGlobal` is not published
at all). `safe_amr_FIOPROBE` and the undocumented `Tag_1` are gone.

**MAY NOT BE CLAIMED until the writer has actually run:** that `StandInValid`
ever becomes TRUE, any T6 step, the re-arming of the stale timer, and the whole
reset path on this build. **No gate criterion may cite them.** The stand-in path
is a standard DB throughout and establishes no safety-integrity claim (ADR 0011
D5 untouched).

- **m5-41 IN FLIGHT** — run the writer (`bridge/`, built 640e71e). Closes
  forklift-safety SPEC §4.5 step 13 and T6. Carries the witness question: the
  old OPC UA proof read `DataBlocksGlobal`, which is **no longer published**, so
  the witness path has to be re-established before any reading is trusted.
- **Re-read** `"ForkliftControl_DB".ModeDisagreeTimer.PT` and
  `.StandstillTimer.PT` **with the bridge running**. Both read `T#0MS` today
  because their `IN` was FALSE — an open check, not a defect. Folded into m5-41.
- Deferred by the owner 2026-08-05, off the agenda, blocks nothing: renaming
  the session's screenshots. They sit in the owner's OneDrive Screenshots folder
  as `Screenshot 2026-08-05 HHMMSS.png`. They were deliberately **not**
  auto-mapped by timestamp, because a mislabelled evidence file is worse than a
  missing one — so this waits for the owner and is done with them or not at all.
- Housekeeping, low: the PLCSIM instance `FIOPROBE` is still listed in the
  control panel, switched off.
- **Out of reviewed scope, found in passing:** `SafetyInputStandIn` has **"Data
  block accessible via Web server" ticked.** That is a disclosure surface nobody
  reviewed. Done when it is either cleared or ruled deliberate and recorded.
- Stale, recorded rather than fixed: step 189 of the build procedure says the
  writer does not exist. The procedure says so itself.

## m5-03 — F-I/O probe verdict is IN (2026-08-04): ADR 0011 D2 fallback
Report: docs/reports/m5-03-fio-probe-run.md. Procedure and verdict:
plc/forklift-safety/FIO-FEASIBILITY.md §7. The configured F-DI stayed
passivated on this installation and the API's by-name write never reached the
watch table, so the standard-DB stand-in of plc/forklift-safety/SPEC.md §7
remains the input path.
- **roadmap M5 criterion (a): OWNER RULED 2026-08-04 — BOTH remedies, not one.**
  The stand-in is upgraded to an **automated API-driven standard-DB stimulus**
  carrying the Siemens S015 validity check and labelled a stand-in everywhere,
  **and** criterion (a) is **amended by ADR** to state what that stand-in can
  actually demonstrate. Two consequences the ruling rests on: the probe proved
  *Modify* is refused outright in permanent safety mode (`2206:000002`), so the
  fallback as ADR 0011 D2 names it cannot run at all and automating it is not
  optional; and the API path to a **standard** DB is **plausible but unproven** —
  the probe only ever wrote an F-channel, whose failure was the F-driver
  substituting a fail-safe value. Done when (1) a short proof run shows an API
  write to `SafetyInputStandIn` standing **in the consumer's view**, per LESSONS
  2026-08-04, (2) an ADR amends criterion (a) and the roadmap row follows it,
  and (3) m5-15 is written against the proven path. Do not let the gate proceed
  past m5-15 with any of the three open.
  - **(1) PROVEN 2026-08-04** — docs/reports/m5-03b-standin-stimulus-proof.md.
    The API write reached the F-program's consumer view in 80.4 ms (one F-OB
    cycle), the monitored reset ran on API-written data and cleared 37.0 ms
    after release, and reopening re-asserted the demand in 79.1 ms. **Caveat:
    the run is on the probe copy `safe_amr_FIOPROBE`** — repeat it on `safe_amr`
    before the gate cites it, and do not work in the probe copy meanwhile.
    **Second witness obtained the same day**: the run was repeated against the
    CPU's own OPC UA server, which does not expose `SafetyInputStandIn` at all,
    so a mirror change there can only have come through the F-program. Both
    views agree on every transition and every non-transition. The corroboration
    item is closed; no watch-table screenshot is owed.
  - **(2) DONE 2026-08-05** — **ADR 0015** (accepted on the owner's ruling; no
    invariant touched) partially supersedes ADR 0011 D2 by name: both the
    "changes no gate criterion" claim and the watch-table *Modify* mechanism.
    The M5 row's criterion (a) is rewritten and is the only criterion text any
    ADR has changed. Report: docs/reports/m5-20-criterion-a-amendment.md.
  - (3) m5-15 remains open, now written against ADR 0015 D1.
  - **Sweep residue — fourteen locations, not twelve.** The m5-23 judge found
    two the m5-20 sweep missed: **`FIO-FEASIBILITY.md` §6**, whose retired
    "driven by *Modify* … inert by construction" text the verdict section
    actively routes readers into (m5-15's rewrite takes it), and **PLAN.md's
    session-handover paragraph**, which still said the verdict was blank while
    the same file's Wave 0 recorded it — corrected 2026-08-05. The original
    twelve, listed, not edited, each owned by its layer: five agv files
    still say "verdict is blank" (`model.sdf`, `README.md`, `config.yaml`,
    `launch/vehicle.launch.py`, `EVIDENCE_SENSOR_COVERAGE.md` §10c); plc
    `forklift-safety/SPEC.md` §7 + §2 F3 + §4.2 step 8 + §9 T6 carry the
    *Modify* mechanism (m5-15 rewrites them); `sim/scenarios/
    forklift_commissioning.md` §13's T6 rows follow that rewrite;
    `docs/safety/TWIN-DEMO-MAP.md` §3 is stale **and its AT-08 (b) deferral
    condition is now triggered** — m5-03b held a commanded 1000 ms, so whether
    the sub-case enters scope is a safety-spec ruling. ADRs 0011/0012/0014 are
    never edited; the forward pointer lives in ADR 0015.
- m5-15 (F-program spec) is unblocked and is written against the stand-in path,
  carrying FIO-FEASIBILITY §6's three consequences: the stand-in labelled
  wherever it appears, the S015 validity check carried visibly in the F-code
  per F-runtime group, and D1 untouched. Done when the spec exists with those
  three visible in it.
- plc/forklift-safety/SPEC.md §10 open item 1 closes as **confirmed by
  observation** rather than as a design assessment. Done when §10 says so and
  cites the report.
- Housekeeping: delete the probe copy `safe_amr_FIOPROBE` (FIO-FEASIBILITY
  §0.1 rule 3). The working project `safe_amr` was never modified.

## owner — build COMPLETE on the CPU (2026-07-30 TIA handover, live-verified)
- FB_ForkliftTeleop (§7 + §13) in OB30; D1-D7 applied; mirrors and stand-in
  DBs served; 23/23 nodes with correct access read back; monitored reset and
  its 3 s upper bound observed live; first live teleop drive done and
  captured (owner video, Screen Recording 2026-07-30 085503.mp4 — informal
  evidence, the formal showcase recording still to be made per the scenario
  checklists).
- Handover items 1-6: DONE 2026-08-04, all six read from the tool and recorded
  in docs/reports/m5-03-fio-probe-run.md ("Faz 2 okumaları").
  One of them did not pass: **RESET_HOLD_MIN (200 ms) does not cover five F-OB
  cycles** — FOB_RTG1 is OB123 at 100 ms, so five cycles are 500 ms. Recorded
  as an open SRS-window deviation, not tuned. Done when a safety-spec brief
  either widens the window or restates the requirement, with the acceptance
  test re-read beside it.
- TIA evidence PNGs copied and committed 2026-08-04 (plc/forklift/evidence/
  m4-*.png, plc/forklift-safety/evidence/m4-*.png and m5-03-*.png).
- Run T5.1-T5.6 (plc/forklift/SPEC.md §11) and T6 (safety SPEC §9.1) per
  sim/scenarios/forklift_commissioning.md §12, then record the showcase with
  the TWIN-DEMO-MAP naming discipline (nothing early-opened presented as M4
  evidence; "the operator drove the device from the engineering interface,
  the safety program did X").

## owner — M4 queue, in order
- m3-37 finding 7: CLOSED 2026-08-04 as **not reproduced**. The downloaded
  program's tag list carries ForkliftControl_DB.ResetEdgeMemory, unsuffixed,
  matching plc/forklift/SPEC.md §3.2. The "_1" sweep over the whole instance
  tag list found one unrelated name: a stand-alone Bool `Tag_1` with no
  documented owner. Done when `Tag_1` is either named per CLAUDE.md §9 or
  deleted at the next TIA session.
- First WSL run of ./stack.sh (m4f-10): the readiness timeouts are
  uncalibrated — no bringup ever ran in the container; expect to tune, and
  report which component start lines disagree with the docs, if any.
- Cold-start capture: DONE 2026-08-04, plc/forklift/evidence/
  m4-cold-start-bridge-down.png — closes m3-37 findings 1, 2, 8 and 9 and
  carries §11 4.8's cold-start half and 4.9b form (b).
  **Still owed from the same item: the Group 1 + Group 2 capture with the cell
  running**, deferred by the owner to its own run. Done when one screenshot
  shows both groups live with the bridge and HMI up.
- Clock durability: DONE 2026-08-04 — w32time set to Automatic, started, and
  `w32tm /resync` reported success; service confirmed Running.
- Stop the still-live m3-26-era bridge session with SIGTERM before new bridge
  work: its clean shutdown prints the build-G R1/R2/R3 ratio set m3-36 wants,
  and its CSV is archived only after the process is gone (LESSONS 2026-07-28).
- After the TIA read-back: point bridge/config/bridge.yaml at the Forklift
  groups (one edit per bridge-design §2.1). The TIA read-back finished
  2026-08-04; the edit was deliberately left to the same run as the
  running-cell capture that would verify it, rather than committed blind. Until then the live config is
  deliberately cell-only — browsing nodes the CPU does not publish would
  error (m4f-06). bridge/config/rehearsal-forklift.yaml is the double-facing
  config and is not the gate config.
- Run T5 per plc/forklift/SPEC.md §11 (T5.4 corrected 2026-07-29 — hold the
  reset unbroken, now executable from the page's press-and-hold RESET) and
  the five commissioning scenarios per sim/scenarios/forklift_commissioning.md
  (H6 note in its §9: a stimulus step that posts once and waits >1 s decays
  to rest by design), then record the showcase — the recording is gate
  evidence.
- BELT_SPEED_MIN/MAX remain design values (m3-27) — measure and record when
  convenient; not gate work.


## contract — topology gap found 2026-07-30 (m5-02 open question 1)
- CLAUDE.md §3 does not draw `bridge/` at all: its only PLC-to-vehicle path
  is PLC → fleet manager → MQTT → client, while the actual M4/M5 command
  path is HMI → PLC → bridge → simulation. The layer that carries every
  command demonstrated so far is therefore outside the diagram invariant 11
  reads against, and unenforceable by it. Needs an owner-approved infra
  brief plus an arch-docs ruling on whether the bridge edge is drawn as the
  simulation's stand-in for field wiring or as a layer in its own right.
  Done when §3 draws the path the demonstrations actually use.

## M5 — judge review follow-ups (docs/reports/m5-judge-architecture-review.md)
- **BLOCKER — RULED 2026-08-04, now tracked under the m5-03 heading above.**
  The verdict came back `ADR 0011 D2 fallback`, so criterion (a) went live as
  the judge predicted, and the owner ruled **both** remedies rather than one.
  The live definition of done is the three-part one under
  "m5-03 — F-I/O probe verdict is IN"; this row stays only to record that the
  judge's finding was upheld and that ADR 0011 D2's claim that the fallback
  changes no gate criterion is now known wrong.
- M4 showcase recording: owner ruled it is made against the CURRENT tree
  (judge finding 7). Criterion (d)'s instrument changed under it — the ±90°
  scanner was deleted and the process stop plane moved 0.25 → 0.15 m — and
  m5-06 verified live that the behaviour is preserved on the front safety
  scanner's measurement channel (0.90 m crate caught at 0.85 m). Done when
  that instrument change is written into the M4 evidence and the scenario
  procedure, so the recording says which tree it certifies.
- Monitoring plane, m5-13 briefing (judge finding 6): "read-only by
  construction" is today a source-code property, not a runtime-enforced one.
  Decide whether m5-13 adds real enforcement (SROS2/DDS permissions) or
  whether the limitation is recorded as a limitation. Do not let the phrase
  stand unqualified either way.
- m5-18: PL-SCENARIOS carries "Category 3 is claimed" wording, permanent
  grep-bait against ADR 0011 D5 item 1 — sweep the verb, not the noun.

## m5-11 — closed 2026-08-04 (f02ece7), residue by owner

- **interface**: `opcua-nodes.md` §12 specifies four data without specifying the
  vehicle's reaction. Four conservative readings were implemented and named in
  the code and EVIDENCE_ENVELOPE §2; each can only make the gate more
  restrictive. The interface agent rules: (a) the equipment permit's motion
  effect, (b) a ceiling outside its window, (c) a mode outside `{0,1,2}`,
  (d) how the autonomous chain clears the teleop path (§12.9 C3). Done when §12
  states each reaction and the gate's code cites it instead of its own reading.
- **interface, invariant 10**: `envelope.ceiling_max_mps = 1.00` is a second copy
  of `TRACTION_SPEED_MAX` (plc/forklift/SPEC.md §3.3). Done when either the
  vehicle reads it from the single owner or §12.4 says consumers carry a local
  copy deliberately.
- **agv, carried**: `stale_window_s = 0.50` is a design value. ADR 0014's open
  item asks for the brief that measures PLC-write-to-topic age and jitter; the
  constant is re-derived when it lands.
- **agv, small**: `EVIDENCE_NAV2.md` §7's reproduction recipe now brings up a
  gated chain, so the vehicle correctly will not move without an envelope. Needs
  the note and the pair `gate:=false cmd_topic:=/cmd_vel_smoothed`. The m5-11
  brief forbade the edit.
- **sim: CLOSED 2026-08-05 by m5-21** — Nav2 (`ros-jazzy-nav2-bringup` 1.3.12)
  and `robot_localization` 3.8.3 are system packages; the overlay is retired to
  `~/ros-overlay.retired-m5-21`. The feared cross-tree upgrade did not happen
  (0 upgraded / 137 new / 0 removed). The EVIDENCE_ENVELOPE qualifier and the
  latency re-reading are applied. Both follow-up decisions are answered in
  docs/reports/m5-21b-install-decisions.md:
  - **(ii) CLOSED** — `install.sh` is the right home, and its `if MISSING`
    guard was dropped 2026-08-05: the guard skipped the step in exactly the
    hand-install case that caused the outage, while `--only-upgrade` is a no-op
    on a current machine.
  - **(i) DONE 2026-08-05 by m5-26** — the owner ruled catch up. `dist-upgrade`
    ran once: **342 upgraded, 7 new, 1 removed, 0 errors, 0 broken**, and the
    machine is now **0 packages behind with no hold and no pin**. All three
    verifications passed: `GL_RENDERER` still `llvmpipe (LLVM 20.1.2, 256 bits)`
    read from the ogre2 log against a pre-upgrade reading taken first; 23 nodes
    up with all seven managed nodes `active` and zero process deaths; the m5-24
    domain wall holding both directions and the pass-through residual still
    `0.000e+00`. Nothing tuned, nothing restored.
    - **The one real risk, answered by measurement:** the plan added five
      NVIDIA-580 packages, and NVIDIA is registered as an EGL vendor **ahead of
      Mesa** on this machine with `libEGL_nvidia` genuinely loaded into the
      render process. The post-upgrade renderer reading was taken with the new
      vendor in place, so the llvmpipe result is a measurement of the current
      configuration, not an inheritance.
    - **Consequence, carried:** every evidence file measured before 2026-08-05
      now describes an environment that no longer exists. m5-26 could not edit
      them. Most M5 evidence was already container-qualified; the ones that need
      the new qualifier are the WSL-measured files — `EVIDENCE_ENVELOPE.md` and
      `EVIDENCE_VEHICLE_IMAGE.md`. Done when each carries it.
  - ~~**(i) OWNER'S CALL, recommendation is CATCH UP, not pin.**~~ Superseded
    above; the reasoning is kept because it is why the decision went this way.
    The
    `libglapi-mesa` removal is verified hollow: it is a Mesa-24 stub, the
    packages that actually contain llvmpipe are already at 25.2.8 — the exact
    version the Gazebo log prints — and the only installed dependant is
    `libgl1-amber-dri`, a pre-2007 GPU driver this machine has no use for.
    Staying pinned is what CAUSED the m5-21 outage: packages.ros.org serves
    only today's builds, so every future install pairs new against stale, and
    **there is no rollback — `fastcdr` 2.2.5 is already gone from the archive
    and the machine's only copy is one saved file in `/root/m5-21-snapshot`**.
    342 packages behind. Done when an infra brief runs the dist-upgrade with a
    snapshot first, `/dev/shm` cleared after, and `done_when` carrying a Gazebo
    `GL_RENDERER` read plus the §12.5 vehicle-stack bringup. **Not run
    unattended: it mutates the environment every evidence file is qualified by,
    and 342 packages can surprise in ways no simulation shows.**
- **fleet/M6**: a goal aborted while the envelope is withheld is nobody's yet —
  Nav2 held 235 s then aborted with code 105, as ADR 0011 D3 predicts.
  Re-issuing the goal is order-level behaviour.
- **bridge**: the gate publishes its report but the bridge's signal map does not
  carry the group (`opcua-nodes.md` §12.13 item 1), so ADR 0014 D5.3's readback
  is closed on the vehicle side only. This is the report's `next_suggested`.

## ADR 0016 — per-vehicle compute, ACCEPTED 2026-08-05
docs/adr/0016-per-vehicle-compute-and-deployment.md, plan in
docs/reports/m5-22-vehicle-compute-deployment-research.md. One DDS domain per
vehicle; one vehicle image with identity from a per-vehicle config rooted in
the VDA 5050 serialNumber; four named crossings; per-instance gz topic
prefixes; systemd units as the real-PC story, containers compatible but not
adopted. **No invariant touched** — every crossing rides an existing seam.
- **Resource question measured, not projected away** (2026-08-05, alone,
  headless): one vehicle's full stack **2.70–2.86 cores / 1 165 MB**, Gazebo +
  world + one model **1.12 cores / 597 MB**. Four project to **12–14 of 20
  logical cores and ~5.5 of 15 GiB — they fit.** Unmeasured and named as risk:
  a *driving* vehicle's extra controller/costmap cost, four models at 3 640
  rays, and the GUI's ~8 RTF points for a recorded showcase. Phase 4 converts
  the projection to a measurement before M6 builds on it.
- **ACCEPTED by the owner 2026-08-05.** Phase 1 was built ahead of acceptance on
  the owner's standing instruction; it touches no invariant and leaves the
  m5-10/m5-11 chains runnable. Phases 2–4 are now open to brief.
- **Phase 3 carries two owner decisions** — fold into the m5-13 item: the
  monitoring mechanism (multi-context process vs `domain_bridge`, which is a
  **new dependency** and therefore proposed-and-waiting per CLAUDE.md §10), and
  the monitoring directory (`agv/` vs `viz/`, the standing ADR 0011 D4 /
  ADR 0005 question).
- Open, small: whether container packaging is demonstrated at all (ADR 0016 D5
  keeps it compatible, not adopted) — cheap later, costly now.
- The `bridge/` topology-gap item above should draw the bridge edge
  **per-vehicle-shaped** when its infra brief lands (ADR 0016's invariant-11
  row).
- ADR 0016's F3–F7 are `[snippet]`-graded: re-verify before any is made
  load-bearing beyond that ADR (the ADR 0014 rule).

## Nav2 route — DIAGNOSED 2026-08-05 (m5-31). Not a regression, not a platform gap.
**The route works on WSL.** Run r2 reproduced the committed result with nothing
changed: **13.21 s, 0.156 m, tracking rms 0.051 m** against 13.40 s / 0.183 m /
0.119 m. Both framings below were wrong, and the reason is the same both times:
five repeats gave 1 clean traverse, 2 completions after 69–94 s of recovery and
2 timeouts at 120 s — and **the container's own committed history was 1 success
in 4 at identical parameters.** The committed figure was always one draw from a
distribution straddling the acceptance criterion.

Both leading hypotheses were falsified with evidence, not argued away: WSL
measures **RTF 0.996–1.001** and the container's RTF is recoverable from its own
committed log — both ran at ~1.0; and the believed pose is **0.000 m / 0.00° off
truth at goal acceptance in every run on both machines**, so belief decay over
the longer dwell is dead too.

**The cause, demonstrated.** The goal checker needs `xy_goal_tolerance` 0.25 m
**and** `yaw_goal_tolerance` 0.15 rad **at the same tick**. Each is satisfied for
tens of seconds; the two are never satisfied together in any failing run — r4
spent **55.9 s** inside the position circle and **47.1 s** inside the heading
window with **0 samples inside both**. The geometry says why: this vehicle pays
**2.1–2.6 m of travel per radian** in the endgame, so correcting one yaw
tolerance costs ~0.32–0.39 m against a 0.25 m box. An intermediate hypothesis —
the `stateful` latch reset 116 times by the 1 Hz replan — was tested and killed:
at a tenth the replan rate the vehicle **parked 2.7 cm from the goal and sat
pointing 47° away for 85 s**.

- **OWNER DECISION: how is this fixed?** Two one-variable confirmations were run
  in `/tmp` copies and deliberately **not applied**: raising the yaw tolerance
  alone finishes the route on the approach twice (15.01 s, 13.71 s), and one run
  completed at a believed heading error of **8.642° — 0.048° outside the
  committed tolerance**. The constraint is `xy_tol > R × yaw_tol`, which today
  fails by ~1.5×. **The agent's recommendation is to fix it upstream** with an
  approach corridor that controls the arrival heading, because a wider checker
  hides the geometry rather than removing it.
- **Second finding, unrelated and worth its own item:** the recovery shuffle
  degrades AMCL to **0.661 m worst case**, 2.5× the 0.263 m that
  `footprint_padding: 0.27` is derived from. Done when the padding is re-derived
  or the shuffle is prevented.
- Every committed figure is now ruled in `EVIDENCE_NAV2.md` §8.6: the §5.5
  planner bench **re-measures exactly** (the planner is deterministic and was
  never the variable), the **0.141 m floor stands**, case A's single figure is
  **superseded by the distribution**, and cases B/B′/C/D as drives plus the §1
  probes are marked **unverified on this platform**.

## ~~BLOCKER-CLASS~~ — superseded by the entry above (kept for its reasoning)
**Reframed 2026-08-05 by the m5-23 judge; the first framing was wrong and the
correction matters.** This was written up as a *regression* caused by m5-21's
package install. It is not. `agv/forklift/EVIDENCE_NAV2.md` §0 states in its own
environment block that every m5-10 figure is a **project session container** run
(Ubuntu 24.04, **4 cores**, headless) and says outright *"Nothing here has been
reproduced on the owner's WSL machine, and the M5 showcase runs there."*

| | Committed (m5-10) | 2026-08-05, WSL |
|---|---|---|
| outcome | SUCCEEDED in 13.40 s | **TIMEOUT at 90 s** |
| final | 0.183 m absolute | **0.628 m** |
| host | container, 4 cores | WSL, 20 cores |
| nav2 | 1.3.12 | 1.3.12 |

So the 2026-08-05 run is not a regression — it is the **first attempt on the
showcase platform, and it failed**. The package hypothesis is dead beside it:
the Nav2 version is the same on both sides. **Roadmap criterion (d) currently
rests entirely on container evidence that the showcase platform contradicts** —
LESSONS 2026-07-27's container-as-proof mistake, recurring.

Done when the route is either made to complete on WSL and re-measured there, or
the failure is diagnosed and criterion (d)'s evidence is restated against a
platform it actually holds on. **Nothing was tuned**, correctly: m5-24 was
forbidden to, and tuning before diagnosis destroys the evidence.
Beside it: `EVIDENCE_NAV2.md` §0 already carries its qualifier honestly —
the fault was in the reader, not the file.

## ADR 0016 Phase 1 — CLOSED 2026-08-05 (m5-24), two items left
- **Allocation table: RULED 2026-08-05 — it lives SIM-SIDE**, as ADR 0016 D2
  states. m5-24 built it at `agv/forklift/vehicles/allocation.yaml` because
  `sim/` was outside its write scope, and reported the disagreement instead of
  choosing. Done when one brief moves the file to the sim side, repoints
  `scripts/vehicle_identity.py`'s single lookup path at the new location, and
  shows the m5-24 domain-wall observation still passing. The **constraint does
  not change**: exactly one file pairs a serial with a domain ID, no per-vehicle
  config carries a domain, and the launch still refuses to start when the
  environment disagrees with the file.
- **`sim/` edits requested** by m5-24 report §3 to make the split clean rather
  than worked around — precise enough to become a sim brief.

## HMI v3 — owner feedback 2026-08-05, planned at the END of M5
The owner reviewed the v2a screenshots and asked for a substantially larger
operator page in a later version. **Not M5 work** except where noted; the plan
is written now (brief m5-30) and implemented after M5 closes.
- teleop joystick shown **only** when teleop mode is selected — owner ruled
  2026-08-05 that this waits for v3 rather than being fixed in v2a
- the warehouse map with the vehicle's live position on it, **RViz-grade**
- every piece of vehicle information reachable from this one page
- selectable **live camera views** from the vehicle. Note: the forklift model
  has no camera today, so this is a model change with a render-budget cost, on
  a machine where the GUI already costs ~8 RTF points
- **Boundary ruled by the owner 2026-08-05:** the real-time map with live
  obstacles is **inside M5** — it is criterion (e) word for word, delivered as
  m5-13 plus HMI v2b. Only the beyond-criterion parts above are v3.
- Plan: `hmi/V3-PLAN.md`, five phases (report m5-30). v3 adds **zero OPC UA
  nodes and zero HMI writes**; every new datum rides the ADR 0011 D4 monitoring
  plane. It also refuses RViz's 2D-goal tool — goal commanding stays the
  standing §12.13 item 4 decision.

### TIME-CRITICAL: five constraints the m5-13 brief must carry
v3 forces v2b decisions, and m5-13 is not briefed yet, so shaping it now is free
and shaping it later is not (`hmi/V3-PLAN.md` §2):
1. a **serialNumber-rooted per-vehicle namespace even at n = 1** — retrofitting
   one at n = 4 is the expensive version
2. the **whole map**, not a crop around the vehicle
3. **no bulk pixels on the JSON poll**
4. the ADR 0016 **D3c mechanism ruling taken knowing camera load** — that
   favours a multi-context process over `domain_bridge`'s fixed forwarded set
5. **camera selection implementable as subscription lifecycle only**

Still the owner's, unassumed: the D3c mechanism and directory, and whether the
monitoring plane's read-only property gains runtime enforcement.
**Camera cost is unmeasured and unclaimable** until V3-4's four-cell probe runs —
llvmpipe software rendering, and whether Gazebo renders an unsubscribed camera
at all is itself a measurement.

## m5-15 — F-program spec DONE 2026-08-05, four items owed by others
`plc/forklift-safety/SPEC.md` is rewritten against ADR 0015. The judge's F3
stimulus gap is closed: the reset arrives as one deliberate command per shaped
press on the operator channel, with the F-program's unchanged edge / window /
stuck-fault monitoring doing the *monitored* work. §7.6 says flatly that the
F-program **cannot** check a write's origin and specifies a four-way correlated
log instead of pretending otherwise.
- **owner ruling 2026-08-05: the stand-in writer lives in `bridge/`.** Reasoning
  recorded so a later reader does not re-open it: `bridge/` is already the
  simulation's stand-in for field wiring — the role ADR 0005 made it a top-level
  layer for — and the writer is that same role for the safety channel, where a
  real cell would have F-I/O wiring. Two consequences the design must carry:
  `bridge/` now holds a **Windows-side process** beside its WSL ROS 2 / asyncua
  one, and it reaches the CPU through the **PLCSIM Advanced API** rather than
  OPC UA, so `bridge/README.md`'s boundary statement is rewritten in the same
  round. `plc/forklift-safety/SPEC.md` §10 open item 8 closes when the plc agent
  next touches that file — **not now, the owner is working in `plc/`.**
- **URGENT, 2026-08-05 night:** the owner chose option A in the TIA session, so
  the S015 delta lands and `StandInValid` boots FALSE until a heartbeat is seen
  to change. **Nothing advances that heartbeat until the writer exists**, so
  both demands stay latched, no reset is accepted, and the cell — including the
  working M4 teleop demonstration — is inert until the writer ships. It is the
  overnight priority.
- **m5-12** must publish the field-evaluation log the writer's zone channel
  consumes, over the named WSL→Windows TCP link.
- **sim**: `sim/scenarios/forklift_commissioning.md` §13's T6 rows follow SPEC
  §9's rewrite — 29 automated steps now, including a writer-death scenario.
- **safety-spec**: two rulings, plus the `RESET_HOLD_MIN` 200 ms against five
  F-OB cycles of 500 ms — recorded and handed over untouched, as briefed.

## sim + plc — the fifth consumer, found by the m5-29 review
Making the HMI's eight-node write set required broke the four M4 harnesses in
`hmi/tools/`, which was known. The review found a **fifth consumer nobody
declared**: `sim/scenarios/run_forklift_rehearsal.py:90` and
`sim/scenarios/forklift_commissioning.md`. **M8 criterion (b) depends on it** —
the M4 scenario procedures must run against a second controller. Done when both
are repointed at a double serving §12, or the dependency is restated. Not
fixable inside `hmi/`; it needs the `plc/forklift/double/` §14+§12 extension
that m5-27 already requested.

## M5 — open items
- Monitoring service directory: ADR 0011 D4 recommends `agv/` but does not
  rule it; `viz/` is the alternative and the ADR 0005 test names the
  question — done when the first monitoring brief rules it.
- F-DI order number and its parameterisation (1oo2 equivalent, discrepancy
  time, input delay) are unfixed pending the m5-03 verdict — done when the
  F-program spec carries owner-verified values.
- plc/forklift-safety/SPEC.md open item 1 is answered in direction, not in
  fact: ADR 0011 F3 gives the probable cause (TIA V18/V19 defaulting above
  the supported safety-system-version list) — done when m5-03 settles it.
- Later gates: the M6 deep-research brief (ADR 0010 D6d) and the
  m4-00-hermes-survey decisions for M7 (D6c) — each done when owner-ruled.

## sim — M5 carried
- `warehouse_slam.launch.py` carries a lifecycle emit-before-register race:
  the run dies after "Read map ... 606 X 410" with no error in any log. The
  fix pattern is proven in `agv/forklift/launch/localization.launch.py` —
  register every handler, then emit (m5-08e). Done when the race is gone and
  a clean chain is captured.
- `warehouse_bringup.launch.py` has no `seed` argument, so a seeded A/B of
  the reverse traversal is impossible; m5-10's forward control was handed 8x
  more heading drift than its reverse pass and the confound had to be named
  instead of removed (m5-08e, m5-10). Done when a seed can be passed.
- `forklift_bringup.launch.py` cannot bring the current vehicle stack up: it
  still lacks the IMU bridge, wheel odometry, EKF, `imu_gate.py` and the new
  `standstill` config key (m5-07c/d/e). The arena scenarios cannot run until
  it does. Done when the arena bringup carries the same stack the warehouse
  one does, shown by an echo.
- The arena has almost nothing at the 1.80 m navigation plane; the warehouse
  world was built for autonomy instead (owner ruling, ADR-recorded in the
  roadmap). Only relevant if an arena navigation scenario is ever wanted.
- The mast's rendered and physical bodies disagree — measured: the nav lidar
  reports the mast as two 4-ray rail lobes, 8.75 deg simulated against 29.0
  deg physical (m5-04 OQ5, quantified by m5-04b).

## sim
- Cell reskin (deferred, visual only, ARIAC licence blocker unchanged).
- `--` inside XML comments breaks ElementTree in warehouse.sdf:16,
  forklift_arena.sdf:326 and cell.sdf:15 (m5r-07 OQ5, reproduced by
  m5r-09; the LESSONS 2026-07-27 cell.sdf mechanism) — one brief, comment
  text only.
- forklift_commissioning.md §1/§10 quote HMI port 8090, which is the
  rehearsal config's; hmi/config.yaml binds 8088 — align the doc with the
  config it names (m4f-10 OQ3).
- sim/README.md:51 lists scenarios/EVIDENCE_NAV.md, which exists only once
  a run produces it (DEFERRED.md:51) — mark it "(generated by the first
  run)" with the next sim touch (m5r-07 OQ6).
- M5 carried: resume the parked navigation scenario on the forklift
  (sim/scenarios/DEFERRED.md). Nothing migrates automatically — m5-09
  deleted the scenario's Nav2 config with the retired platform and m5-10
  writes the forklift's from scratch; which of the parked files survive is
  m5-10 briefing work.
- Carried (m5-10 briefing, raised by m5-09): the parked scenario's two
  remaining code files still carry retired-platform values —
  scenarios/nav_scenario.launch.py (NavFn/DWB/spin-backup node set, the
  retired command topic, params_file now required with no file to satisfy
  it) and scenarios/run_scenario.py (the retired odometry topic). The owner
  ruled only on the Nav2 config; decide keep-or-delete for these two.
- Carried (m5-10 briefing, raised by m5-09): sim/launch/warehouse_bringup
  .launch.py spawns the retired vehicle through its vendor launch, and
  sim/worlds/BRINGUP_EVIDENCE.md is that vehicle's bringup evidence.
  m5-09 could not touch either (a concurrent agent held sim/launch/ and
  sim/worlds/). Definition of done: both are ruled on and, if kept, say so
  as record rather than as a runnable procedure.

## M5 — where the work stands (2026-08-04)

Vehicle side, CLOSED and evidenced: sensors and coverage; the measurement /
safe channel split; realistic odometry (IMU + tricycle wheel odometry + EKF,
noise from a datasheet) with the standstill gate and its post-drive leak
closed; the warehouse world with a measured landmark map; SLAM, an
adversarial judge round, a rebuilt map, a committed world->map registration
and absolute scoring; AMCL; and Nav2 for the tricycle.

Vehicle side, NOT STARTED: m5-12 protective and
warning field evaluation, m5-13 monitoring service, m5-14 HMI v2a then v2b.
(m5-11 the envelope gate node CLOSED 2026-08-04, f02ece7.)

Documents, CLOSED: opcua-nodes §12 (envelope, mode, process stop), the
standard program delta (SPEC §14), the PLr derivations and the D5 claim
boundary.

Documents, BLOCKED: m5-15 the F-program spec, on the m5-03 verdict alone.

### Measured numbers a later session should not re-derive
- Localization: steady-state rms 0.124 m, max 0.263 m, against a registration
  residual MAX of **0.141 m** — the instrument floor. Any figure at or below
  it is "at the instrument's resolution", never a smaller number. The floor
  swallows 74 % of the route run, so a criterion tighter than ~0.14 m is not
  measurable through this map.
- Odometry drift the localizer exists to correct: 106 m route with 1450 deg of
  turning gives roughly 5 m and 13-17 deg, bias sign drawn per run.
- Estimator dwell cost: 0.000 deg for a dwell beginning >16 s after the stop;
  the "at most 0.33 deg" figure for a dwell beginning at the stop was measured
  from one stop and was exceeded 1.6x by the AMCL dwell — treat it as an
  observation with n=1, not a bound.
- Nav2: straight 0.183 m absolute; short reverse tracks to rms 0.0009 m but a
  6 m reverse diverges to 50 deg at about 2.4 m (n=1) because pure pursuit is
  stable only with the steered axle leading; a goal inside racking is refused
  with the vehicle never moving; `footprint_padding: 0.27` is set from the
  measured 0.263 m.
- Render budget: three lidars at 910 rays total cost nothing measurable
  headless (RTF 1.0004); the GUI costs ~8 points and the beams ~2.5.

### Carried from m5-10, for m5-11 and later
- Goal tolerance 0.25 m sits below the vehicle's own manoeuvring granularity
  (smallest measured arc radius 1.29 m); one attempt in four shuffled 240 s
  at 0.335 m out. Revisit when docking is specified.
- Every plan on the straight route opens with a 0.092 m Reeds-Shepp reverse
  that RPP executes; `reverse_penalty` cannot remove it without wrecking
  genuine reverses (swept 2/3/5/10).
- Routes through the 2.35 m column pinches leave 0.356 m of total budget,
  which makes drivability a fleet-routing decision at M6, not a tuning one.
- The refusal error code does not carry its reason (208 driven, 207 on the
  bench).

## interface
- Carried (fold into the next interface brief): opcua-nodes.md §10.1 still
  describes the shared-project two-FB arrangement; the as-built forklift
  project runs one standard FB with both link verdicts inside it (m4f-04j).
  Add the heartbeat browse-path read-back note its report requests.
- Carried, low (fold into the next interface brief): bridge-design.md §7.2
  and opcua-nodes.md §9.7 still share the flat "No timer, threshold or
  reaction exists in the bridge" sentence that §10.1's ruling rephrased
  everywhere else — scope it the same way (own-cycle timers allowed, process
  timing forbidden); m4r2-07 report has the context.
- Carried, low: opcua-nodes.md §11.8 open item 1 is answered by m5a-06b but
  its closure mark needs a §11 edit that brief forbade — one line with the
  next interface touch.
- Carried (M6 briefing): vda5050-subset.md still defines
  typeSpecification.seriesName as RB-KAIROS per ADR 0002, with agvClass
  CARRIER and an agvKinematic that depends on the vehicle's steering model —
  redefine against the forklift (ADR 0010 D1) in its own brief; a field-value
  change, not a renumber (m5r-08 open question 1).

## hmi
- Carried, low: EVIDENCE_HMI.md §C's browser pass predates the m4f-07b change
  (7675960) and was not re-run — the endpoint pass proves the behaviour, the
  page's new DOM handlers are unexercised. The owner's live session exercises
  the page naturally; capture one screenshot of the held RESET there and the
  §D residual row closes.

## bridge
- Second witness for the masked-revert window (owner design decision,
  post-gate): a revert landing between the cycle's step-0 heartbeat read-back
  and step-4 write is erased and the restart goes undetected — measured
  median 5.255 ms of a 50.015 ms cycle, 10.5 %, with 4.0 s of exposure in the
  measuring run (m4f-05d). §8.1 requires a second witness; choosing one is
  the owner's. Consider also a bridge-side masked-revert counter so the
  property shows in production evidence, not only harness runs.
- Fault injection (SPEC §12 item 6; unblocks T4.11b): opt-in NaN/inf/
  out-of-window write that cannot be armed by accident in an evidence run.

## plc
- Fold into the next demo-cell plc brief: F6 (PresenceOnTimer.PT reads T#0MS
  after a CPU restart, likely §6.5's conditional call — diagnose, close or
  escalate); close SPEC §12 item 7 (rewrite-on-restart now delivered); T4.11
  reaction re-record with a per-session CSV; the §B2.9 "build B" three-delta
  label that three owner captures contradict (label only, no figure moves —
  shared with bridge); the demo-cell §4.3 "Nothing else goes into the
  interface." sentence, scope-stale after opcua-nodes §10.
- T4.11b stays blocked on bridge fault injection (above).
- One clause, next forklift-safety touch: plc/forklift-safety/SPEC.md §1.2
  N7 predates SF-10/SF-11 and should name them in its no-onboard-safety
  statement (m5-18 open question 1).
- Carried, low: plc/forklift/SPEC.md §12 item 7 is stale (its own item 7 —
  distinct from demo-cell's) — close with the next forklift plc touch
  (m5r-06 OQ3).
- M5/M6 carried: AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume
  of interrupted handshakes; dedicated F-I/O — forklift functions at M5,
  fixed-cell SF-05/06 with the stations at M6.

## agv
- Carried, small: agv/forklift/launch/vehicle.launch.py is the model's
  standalone test rig (own gz server and spawn). Used inside the composed
  stack it puts a second forklift into the arena — observed live 2026-07-29.
  Its file header and the README contract table should say "standalone rig;
  in the composed stack run the two scripts directly", or the launch should
  gain a no-sim argument. One small brief.
- Carried, low: wheel_radius_m, steer_limit_rad and the fork travel exist in
  both model.sdf and config.yaml (SDF cannot be read as YAML); model.sdf is
  the named authority with a mechanical agreement check in the evidence. If
  invariant 10 is ever read strictly here, generate one file from the other.
- Carried, low: EVIDENCE_MODEL.md could carry its own all-181-sample
  flat-wall dump so the ±45° scanner dropout claim stands on the vehicle's
  own evidence rather than on m4f-03's (m4f-02b note).

## verifier
- m4f-09 (queued, after the owner evidence) — done when every M4 criterion
  has a cited-artifact verdict and the tracking files reconcile against the
  full report directory.

## safety-spec
- m2-04 residue (substance only — m5r-05 carries the gate renumbering):
  SF-08 carries an architecture claim beside its PL c or states the
  inheritance; SF-03's bumper latch appears in §2's no-auto-resume list;
  AT-01 gains the at-rest sub-test SC-02 observes. One brief.
- Carried, low: SF-02's old "review" half collapsed into M5 with no later
  review point (m5r-05 OQ3) — decide at M5 briefing whether a review lands
  at M6.

## docs residue
- README architecture diagram and layer table predate the hmi/ layer
  (m4r2-04 residue) — one infra brief when convenient.
- CLAUDE.md §4's repository layout does not list stack.sh (m5r-09
  finding 4) — one line with the next contract touch, owner-approved.

## publication
- Repository is public-ready and pushed; visibility is the owner's to flip.
  Residual, low: ADR 0007 names a hosting provider and region — an accepted
  ADR is never edited, so closing it needs a superseding ADR or owner
  acceptance as-is. Local commits since the push are unpushed until the owner
  pushes.

## carried forward, by gate
- interface (M6): the fleet-facing server interface's name is a contract
  decision (ADR 0006) — chosen deliberately at briefing, never discovered in
  TIA; opcua-nodes.md §2 still heads the fleet tree with http://DemoCell.
- plc/owner (later gate): suppress DataBlocksGlobal DB-level exposure by
  clearing each DB's "Accessible from HMI/OPC UA" attribute (opcua-nodes.md
  §9.8 open item).
- fleet (M6): confirm the handshake timeout constants.
