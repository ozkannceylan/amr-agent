# m5-15 — the F-program specification against the automated stand-in stimulus

    brief:               docs/briefs/m5-15-f-program-spec.md
    status:              done
    files_changed:
      - plc/forklift-safety/SPEC.md
      - plc/forklift-safety/FIO-FEASIBILITY.md (§6 supersession correction, judge F4)
      - docs/reports/m5-15-f-program-spec.md (this file)
    invariants_touched:  none — ADR 0011 D1 untouched; the stand-in path stays
                         inside the simulation host and off every network path,
                         as ADR 0015 already ruled
    open_questions:      see below
    next_suggested:      the owner's F-session can now run SPEC §4.5 steps 1–14
                         (chunk J unblocked); the writer-home owner ruling
                         (open question 1) should land before anyone implements

---

## What was delivered

`plc/forklift-safety/SPEC.md` is rewritten against ADR 0015 D1 so the owner can
type the F-delta with no design decision left open:

1. **§7, whole rewrite — the automated stand-in writer.** One Windows-host
   process (PowerShell 5.1 + the proven API 7.0 assembly, no new dependency),
   writing **all four members of `SafetyInputStandIn` by tag name every 50 ms**
   — level republish, never write-on-change, so a CPU restart is repaired
   within one F-cycle (the LESSONS 2026-07-28 bridge failure, designed out).
   Two sources: the **field evaluation** (WSL → TCP port 45015 → writer; owns
   the zone channel while its link is up; link silence > 1 s drives the zone
   open) and the **operator channel** (writer console: `estop open/close`,
   `zone open/close`, `reset press/release`, `reset pulse <ms>`). One log per
   session, wall-clock stamped, source-tagged. Failure table §7.3: writer death
   → S015 validity drops → both demands latch; field-link death → zone demand;
   wedged reset → the SF-08 stuck-actuator fault. Every direction stops.

2. **The S015 validity check, visible in the F-code (§5.4).** Eight new F-FBD
   networks in the §5.1 table form (there is no F-SCL on the S7-1500, so
   typeable networks are the code): V1 heartbeat-changed (Int `<>` against a
   previous-cycle memory), V2 `HeartbeatSeen` one-shot (**boot polarity** —
   LESSONS entry 63 applied), V3 stale `TON` with **`PT = T#1s` explicit at the
   pin**, V4 affirmative `StandInValid`, V5–V7 validated channels (invalid →
   open/unpressed), M2 heartbeat memory copy, last network. Plus the exhaustive
   **re-point table** (ten networks, thirteen pins) and the walked-through
   proof that a writer dying mid-press cannot fire the reset (§5.3 gains
   case 7). §2 gains checkpoint **F7** (Int `<>` and `MOVE` offered — the
   R_TRIG lesson applied before building). §3.1–§3.3 carry the new member,
   input, eight statics and third constant with start values.

3. **The reset origin gap (judge F3 soft spot 2) closed in §7.4.** The reset
   originates at the **writer's operator channel and nowhere else** — never a
   client write (R1, enforced by reachability), never the field evaluation
   (no mapping exists, by construction), never a watch table. It is still the
   CLAUDE.md §9 monitored reset because the monitoring is the F-program's and
   is unchanged: falling-edge acting, bounded hold, stuck = flagged fault,
   cause-present = refused — all proven on API-written data in m5-03b. §7.4
   also states plainly why a human at the reset does not break "no human in
   the loop" (that clause governs the scanner chain), and what the path does
   NOT demonstrate (device ergonomics).

4. **Origin honesty (judge F3 soft spot 1) in §7.6.** The F-program can check
   liveness only; a field write and a scripted write are byte-identical at the
   CPU. The instrument is the **four-way correlated record** (field-evaluation
   transition log + writer source-tagged log + consumer's view + OPC UA
   witness); a zone transition logged `OPERATOR` is not criterion-(a) evidence.

5. **§9 T6 fully automated**: 29 steps (was 26), every stimulus a writer
   command or the field evaluation, watch tables read-only throughout; new
   T6.0.1–2 (boot-polarity observation, writer start), new **T6.7.1–2 (writer
   death and rebirth: demands latch on death, survive rebirth, clear only on
   reset)**; T6.4.2 carries both zone forms with the field form marked as the
   only criterion-(a)-capable one. §8 rewritten read-only with the validity
   rows and all three in-force `PT`s.

6. **§4.5, the delta click-path** — 14 ordered steps with a verification each,
   from the `safe_amr` F3 re-confirmation through interface extension, network
   build, re-point, download-with-reinit, `_1` sweep, cross-reference (four
   reads, zero writes), independent browse, writer start/stop rehearsal, and
   the in-force read-backs. This is what TIA-BUILD-PROCEDURE chunk J waits on.

7. **The RESET_HOLD_MIN deviation recorded, not fixed** (§4.3, §10 item 2):
   F-OB 100 ms in force, five cycles = 500 ms > the SRS's 200 ms minimum.
   Handed to safety-spec with AT-08 to be re-read beside it; both constants
   stay as the SRS states them; every T6/AT-08 record names the deviation.
   AT-08 (b)'s stimulus now exists (`reset pulse <ms>`) — the scope ruling is
   also safety-spec's (§7.5, §9.2, §10 item 3).

8. **FIO-FEASIBILITY §6 corrected (judge F4)**: a dated supersession note now
   leads the section the §7 verdict routes readers into — the mechanism in
   force stated first, D2's *Modify* description and the "inert by
   construction" claim kept only as attributed record, the three consequences
   standing unchanged.

Claim discipline: every PL/Category pairing in the touched text is verbed as a
**target**; the S015 check is stated as disclosure honesty, adding no
integrity; no achieved PL, Category, SIL or PFH appears anywhere.

## Open questions

1. **The writer's implementation home needs an owner ruling** (judge F6; SPEC
   §10 item 8). The spec is the contract; no implementation was written and
   none should be until the ruling lands.
2. **Requests to other agents, tracked in SPEC §10**: m5-12 must specify the
   field evaluation's wall-clock transition log (item 9, criterion-(a)
   instrument); the sim agent must rewrite
   `sim/scenarios/forklift_commissioning.md` §13's *Modify* rows against the
   new §9.1, sweeping by subject (item 10); arch-docs should draw the writer
   path when the bridge topology item lands (item 11).
3. **Safety-spec receives two rulings**: the RESET_HOLD_MIN window deviation
   (open item 2) and the AT-08 (b) scope decision (open item 3) — the second
   is shadowed by the first.
4. **§2 F3 must be re-confirmed on `safe_amr`** before any T6 run (m5-03b ran
   on the probe copy); `evidence/m5-25-standin-stimulus-repeat.ps1` is the
   instrument and §4.5 step 1 schedules it.
5. **§2 F7 is a genuine unknown**: whether this CPU's safety instruction set
   offers the Int comparator and `MOVE` is unverified in the tool. The spec
   names the fallback shape (aliasing-safe Bool toggle) but forbids
   substituting at the keyboard.
