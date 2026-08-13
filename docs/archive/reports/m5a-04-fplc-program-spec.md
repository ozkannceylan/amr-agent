# Report m5a-04 — F-program specification for the forklift twin

```
brief:               docs/briefs/m5a-04-fplc-program-spec.md (as amended, f507aca)
status:              done
files_changed:       plc/forklift-safety/SPEC.md (new)
                     docs/reports/m5a-04-fplc-program-spec.md (this file)
invariants_touched:  none
```

## What it is

`plc/forklift-safety/SPEC.md` — the F-FBD implementation specification for the
cell-scope core of ADR 0009, written as **deltas to the build in RUN**, not a
fresh build. Ten sections in the house shape: §1 scope and non-claims, §2 the
feasibility checkpoint first with its abort-to-fallback rule, §3 tags and the
seven deltas, §4 the F-runtime group click path, §5 thirteen F-FBD networks
described box by box, §6 the coupling contract, §7 the stimulus strategy, §8 the
`Forklift F gate` watch table, §9 the 26-step T6 procedure, §10 what is not
specified plus seven open items.

## Rulings taken

| # | Ruling |
|---|---|
| **R-a** | **The F-input channel is not reachable on PLCSIM Advanced** (§2.1). No PROFIsafe partner exists, a configured F-DI passivates, and with wire-NC polarity a passivated channel reads permanently tripped — the demonstration would be a machine that cannot start. Stated as a **design assessment the owner is asked to falsify**, with the consequence that AT-07 (a)/(b) are logic-and-ordering only and AT-01 (c) stays deferred, so **no Category is demonstrated**. If a channel is later established, §7 is the only section that changes: the swap is three pins at one call, and nothing inside the F-block moves |
| **R-b** | **The stand-in lives in a new standard DB `SafetyInputStandIn`** (three Bools, all start `FALSE`), *Accessible from HMI/OPC UA* cleared, driven by watch-table **Modify** over the engineering connection. Four reasons in §7.1, the decisive one being that modifying F-data needs safety mode **deactivated** and fabricating a latch tests the watch table rather than the program. This satisfies map R1/R2 literally — no client can reach it on any path, including the auto-published `DataBlocksGlobal` — and the demand's formation uses neither the bridge nor the OPC UA session |
| **R-c** | **The SF-08 reset is `ResetButtonPressed` on that DB.** `HmiResetRequest` is forbidden (client write, R1) and stays the standard program's **process** reset; `DB_AGV_Drive.Sim_Reset_Button` is retired — it is a level, in a DB an OPC UA client can reach today, so it could clear a safety latch |
| **R-d** | **The reset device is wired and read NO**, not NC. A reset must be actively commanded, so a broken wire means no reset. Stated explicitly because it reads as an exception to wire-NC/program-NO and is exactly its intent |
| **R-e** | **The demand latches become `RS` (set-dominant), not `SR`.** In TIA the trailing `1` marks the dominant pin, so the build's `SR`/`R1` is **reset**-dominant and a held acknowledgement currently defeats the demand. The build note describing it as "S-dominant" is wrong for a Siemens `SR`. §5.0 note 2 tabulates the trap and asks the owner to confirm it in the instruction help |
| **R-f** | **Dual-writer resolution: the F-program's entire write set becomes `InstF_Forklift_Safety [DB3]`.** All four output pins are left unassigned at the call; `Forklift/Status/ForkliftObstacleStopActive` and `…ForkliftResetRequired` return to `FB_ForkliftTeleop` as process flags and read `FALSE` until it is built. Verified by cross-reference, not by assertion (§4.2 step 13) |
| **R-g** | **`SafetyResetRequired` becomes a plain `OR` of the two demands.** The build computes *latch set and zone clear*, which drops the flag while the cause stands — that is "a reset would be accepted now", not "a reset is required", and it contradicts three map §3 rows. "Would it be accepted?" gets its own watch-table row, `CauseGone` |
| **R-h** | **`CauseGone` contains only live-world terms**, and requires **both** circuits closed: one monitored reset clears every F-latch, and only when the whole live world is clear |

## The thing the double caught

Per the 2026-07-29 lesson, §5's thirteen networks were transliterated and the T6
procedure run against them before the spec was finished. Two findings:

1. **A real logic hole.** The rising-edge arming alone still allowed this: press
   the reset with the world clear, hold, let a cause appear **and disappear again**
   during the hold, release — and the latch cleared, because at the release the
   world was clear and the hold had been long enough. That is a held
   acknowledgement clearing a demand that formed after it began. Closed by adding
   `NOT CauseGone` to the reset pins of networks 5 and 9 — **both are needed**, and
   §5.1 explains why either alone leaves the hole open. All 27 modelled checks and
   three edge variants pass on the tightened form; it became refusal row 6 of §5.3
   and step T6.3.5.
2. **A phantom step.** T6.2.3's pass line said `ResetHoldValid` → `FALSE` at the
   3 s bound, in a press that was never armed and where the flag was never `TRUE`.
   An owner would have hunted a transition that cannot occur. Reworded to say so.

The transliteration was a scratchpad throwaway and is not in the repository.

## Requests — files outside this agent's scope

| # | Request | For |
|---|---|---|
| 1 | **`plc/README.md`**: a `forklift-safety/SPEC.md` row in the Contents table, and one sentence stating that this cell's F-program implements the **logic** of SF-01, SF-07 as a pattern and SF-08, with no achieved PL, no Category and stand-in inputs. Its boundary section currently names only the two process-stop cells | infra or a `plc` brief; carried as §10 open item 5 |
| 2 | **Name collision for the mirror group**: `opcua-nodes.md` §4 already defines `Safety/SafetyResetRequired` for the fixed cell (SF-08, M9), and the twin's F-side flag carries the same leaf name. The obvious resolution is a distinct path — the twin's mirrors under `Forklift/Safety/` — but that is an interface ruling and is not taken here. There is a second, standard-side collision with `Forklift/Status/ForkliftResetRequired`, which is the **process** flag | m5a-06 |
| 3 | **A fourth flag exists**, `SafetyResetFault`. Whether it becomes a mirror node is an interface decision; if it does not, it must still be in the watch table, or AT-08 (a)'s "reset-fault flagged" half has no observable at all | m5a-06 |

## Notes for the dependent briefs

- **m5a-05** consumes §6 verbatim: four Bools read from `"InstF_Forklift_Safety"`,
  the one affirmative permissive term, five never-do rules, and the precondition
  every scenario inherits — **both stand-in circuits start `FALSE`, so both demands
  are latched at every CPU start** and no scenario can enable the machine until the
  circuits are closed and one monitored reset is done. §6.5 also records honestly
  that the term is **runtime-inert but not compile-inert**: once the standard
  program reads the F instance DB, deleting the F-program breaks the standard
  build. The fallback that needs no edit is "do not apply the delta".
- **m5a-08** consumes §9's T6 steps and §7.1's statement that **no sensor watches
  the marking** — the owner plays the zone device at the engineering interface at
  the moment the machine crosses it.

```
open_questions:
  1. Section 2.1's F-I/O ruling is a design assessment, not a tool read-back. It is
     falsifiable in one step and the owner is asked to falsify it; if a usable F-DI
     exists, only section 7 changes.
  2. Whether TON, R_TRIG, F_TRIG and RS are all present in this version's safety
     instruction set (checkpoint F2). Substitutes are given for the edges; there is
     no substitute for a timer, and its absence is a fallback, not a simplification.
  3. Whether a watch-table Modify of a standard DB works with safety mode ACTIVATED
     (checkpoint F3). If not, there is no honest stimulus and the fallback applies.
  4. The F-runtime group's monitoring time and the F-OB's cycle time are deliberately
     not named. The rule is stated instead: RESET_HOLD_MIN must span at least five
     F-runtime-group cycles. If neither the cycle can be lowered nor the rule met,
     raising RESET_HOLD_MIN above 0.2 s makes it no longer the SRS's window, and that
     is a recorded deviation rather than a tuning.
  5. AT-08 (b) stays deferred: a hand-driven Modify cannot produce a controlled
     sub-0.2 s pulse. The logic that rejects one is built and untestable. A timed
     injection facility would move it into scope and is not a change to this program.

next_suggested: m5a-05 (the standard-side permissive delta) and m5a-06 (the mirror
node group) can both run now; m5a-06 should take the two name-collision rulings
first, since m5a-05's mirror-copy statements need the final node names.
```
