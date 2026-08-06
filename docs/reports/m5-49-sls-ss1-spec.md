# m5-49 — the F-program SLS and SS1 specification

    brief:               docs/superpowers/plans/2026-08-06-m5-closure.md, TASK 3
                         (issued in-session; no file under docs/briefs/), against
                         docs/superpowers/specs/2026-08-06-sls-ss1-fplc-design.md
    status:              done
    invariants_touched:  none

## files_changed

| File | What |
|---|---|
| `plc/forklift-safety/SPEC.md` | **New §11, the second F-delta**: the speed monitor (SF-10 pattern) and the SS1 sequencer (SF-11 logic) as typeable F-FBD — 27 new networks for 49 in all, 7 new stand-in members (SD2), FB2 interface 10/6/43/17, 14 new constants each with its derivation on the row, the §11.5 re-point table (exactly two pins: `CauseGone` +1, `SafetyResetRequired` +1), watch Group 5, feasibility check F8, and the §11.9 click-path Q1–Q17 in §4.5's shape with a verification per step. Header revision note plus seven pointer notes at the §1–§10 statements the delta makes stale (SD2, interface counts, network count, §6.1/§6.3 read set, §7.1 writer row, §8 group count) |
| `plc/forklift/SPEC.md` | **New §14.16 in the §14 body**: the warning field's consumer — the standard program lowers the envelope ceiling to `WARNING_SPEED_CEILING` = 0.20 m/s while occupied, one temp + one modified part-8 statement (still one unconditional assignment with the mandatory `ELSE` to 0.0), the requested node `Forklift/Warning/ForkliftWarningFieldOccupied` (start `TRUE`, new DB, no existing DB gains a member), the stale rule at every layer, watch rows, cold-start row, verification, three open items. Pointer added at the §14.5 ceiling row |
| `plc/forklift/TIA-BUILD-PROCEDURE.md` | **Chunk Q stub with an honest step count of zero**: names the two click-paths in force, the ordering constraints (F-side depends only on chunk O and types today; standard side waits on the interface ruling), and that the numbered expansion is a later brief starting at step 192. Three new chunk-P rows (writer extension, WSL client, warning node/slot); step-index row Q |
| `docs/reports/m5-49-sls-ss1-spec.md` | this report |

Nothing outside plc/ (plus this report) was written. Nothing committed, no
branch created, no dependency added.

## The four things the task named, settled

1. **Transport.** The stand-in writer carries the readings — OPC UA would put
   the demand's formation on the client seam (the 2026-07-29
   disqualification) and a motion value on ADR 0014's seam. §11.2 is the
   contract: a second TCP link (WSL client → writer listener, port 45016,
   `SPD A/B <int mm/s>`, `MOT <p> <v>`, `PING`), the seam in **Int mm/s**
   because `Real` is not expected in the F instruction set (check F8 reads it
   back; the Int decision stands either way on quantisation grounds — 1 mm/s
   against a measured σ of 5.4), and the warning selector rides the existing
   45015 field link as `WARN 0/1` with the existing 1 s stale rule extended
   to it. Seven new `SafetyInputStandIn` members, per-channel freshness
   sequences included.
2. **The stale rule, as F-code.** The sources go silent, the writer freezes
   the channel's sequence, and networks SL1–SL8 convert a frozen sequence
   into an invalid channel within `SPEED_STALE_MAX` = 500 ms (five F-cycles,
   the §4.3 sampling rule satisfied by construction) and an invalid channel
   on an armed chain into a latched demand in the same F-cycle — a missing
   reading is a demand, never a zero and never the last value. Eight failure
   walkthroughs in §11.6, including the writer dying, one source dying, and
   the byzantine-writer case named as outside the stand-in's threat model.
3. **The warning field's consumer** is §14.16: ceiling to **0.20 m/s** —
   derived, not chosen: below the F-monitor's 300 mm/s by 100 mm/s, of which
   22 is 4σ read noise, 1 quantisation, 77 the unmeasured vehicle tracking
   overshoot (requested); and it reaches ≤ 0.30 m/s at the same point on the
   same ramp the 3.35 m field derivation requires, so the field's sizing is
   preserved. No safety credit; the F-monitor is what catches the ceiling
   failing to fall.
4. **SLS monitors, SS1 sequences.** D1 latches on four independently-watchable
   causes (over-limit under enforcement, cross-comparison discrepancy at the
   derived 31 mm/s / 200 ms, missing reading, shaft-doubt via the labelled
   motion stand-in); cleared only by the one monitored reset, whose
   `CauseGone` now tests the speed world too. Q1–Q4: `Ss1Demand` =
   `ZoneStopDemand OR SpeedMonitorDemand` (the cell e-stop deliberately
   excluded per SRS B4), `Ss1Timer` at the SRS's ≤ 1 s, `TorqueOffDemand` at
   standstill-confirmed-or-timeout, held for the demand's life (SF-11 holds
   no latch of its own). §11.7 tables the plant obligation for the next brief
   and lists exactly what cannot be tested until the brake and controller
   disable exist (AT-11 (a)–(c) entirely, AT-10 (a)'s torque clause).

The two derived constants were consumed as given (31 mm/s is 0.0308 rounded
**up**, the direction that preserves the measured zero-exceedance property;
200 ms unchanged) and re-derived nowhere.

## Requests — work this brief needs and may not write

1. **bridge/** — extend `standin_writer` per §11.2: the 45016 listener, the
   seven members' write behaviour (sequence increments only on fresh source
   lines; `MOT` silence ⇒ `MotionPresent := TRUE` after 250 ms), `WARN` on
   the field link with the stale rule extended, log lines for every source
   event. Also the warning node's bridge slot with its own silence-⇒-occupied
   window (§14.16).
2. **agv/** — the WSL-side `SPD`/`MOT`/`PING` client beside
   `safe_speed_channels.py` (grammar and never-send-non-finite rule in
   §11.2); and a measurement of the envelope gate's ceiling-tracking
   overshoot, which bounds `WARNING_SPEED_CEILING` from above (§14.16 open
   item 9).
3. **interface (`opcua-nodes.md`)** — two new mirror leaves under
   `Forklift/Safety/` (`SpeedMonitorDemand` start `FALSE`, `TorqueOffDemand`
   start `TRUE`, F-side facts in §11.8), and the warning node
   `Forklift/Warning/ForkliftWarningFieldOccupied` (start `TRUE`,
   bridge-written, own DB). Paths and rights are that document's rulings; the
   standard-side half of chunk Q waits on the warning ruling.
4. **plc standard-side brief** — the two mirror copy statements and the third
   permissive conjunct (`NOT SpeedMonitorDemand`), from §11.8's coupling
   rows.
5. **safety-spec** — three flags: (a) the SLS limit's **selector**: the SRS
   holds SF-10's selection to the reduced-detection monitoring case (SC-13)
   and records the warning-field coupling as open (SC-06); §11 implements the
   plan's ruling on the only selector that exists, on one stand-in channel a
   future case-selector can drive instead — the SRS/SC-06 reconciliation is
   not made here. (b) AT-10's "reduced load-direction monitoring case in
   force" wording versus the warning-field selector actually built.
   (c) Whether SF-04's creep demand should also clamp the **teleop** scale
   (§14.16 keeps it envelope-scoped).
6. **A later brief** expands chunk Q into numbered one-action steps from the
   two click-paths (TIA-BUILD-PROCEDURE chunk Q stub names the sources and
   ordering constraints).

## open_questions

- **The tread/body conservatism has an operational bite, stated in §11.6:**
  the monitor bounds tread speed (= body / cos δ); at the 0.20 ceiling the
  full creep speed is compliant only up to ≈ 48° of steer, and sharper
  warning-regime turns must be slower or the monitor correctly demands.
  Whether the vehicle's converter should bound wheel speed in the warning
  regime is a vehicle-side compliance question, named, not designed.
- **Arming-by-first-sight residual:** a run that drives autonomously with the
  speed sources never started is unmonitored (`SpeedChainSeen` never sets).
  Bounded by the launch coupling, the Q17 read-back precondition, and m5-48's
  carried question of making `safe_speed` default `true` (owner's call).
- **`SS1_TIME_MAX` sits at 10 F-cycles and `SPEED_DISCREPANCY_TIME`/
  `SPEED_OVERLIMIT_TIME` at two** — the two-cycle values are the derived
  floor from the evidence, not hold-window measurements, so §4.3's five-cycle
  rule is argued not to apply to them; if safety-spec reads that rule wider,
  the discrepancy time question lands in the same brief as open item 2.

## next_suggested

Task 4 (m5-50): the plant's brake and controller disable in `model.sdf`,
built against §11.7's obligation table, inventory-first; the chunk Q
expansion brief can run in parallel with it.
