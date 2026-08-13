# m5-68 — re-validate the whole chain against F-signature 29FD2C52

    gate:                M5
    agent:               bridge (owns the whole-chain run; reads every layer)
    goal:                Re-measure everything the CPU change invalidated, in the owner's order, and turn docs/VALIDATION-M5.md into a document whose every figure belongs to the program now on the CPU.
    invariants_touched:  none
    inputs:
      - docs/VALIDATION-M5.md — the document you are rewriting, and the run order below is its owner's
      - docs/reports/m5-58-full-stack-validation.md — how the first run was done; repeat its discipline
      - docs/reports/m5-59-validation-fix-triage.md — the four findings and what each fix was meant to do
      - plc/forklift/TIA-FIX-PROCEDURE.md — the session that just closed, its record table and its seven stop conditions
      - docs/reports/m5-62-torque-off-bridge-slot.md — the bridge half, whose figures are double-only and must now be re-earned live
      - docs/reports/m5-61-warn-sender.md — the WARN sender and the three run-order hazards it names
      - docs/reports/m5-64-fix-round-judge.md and the vault review's F1 (see §4)
      - docs/LESSONS.md
    deliverable:         docs/VALIDATION-M5.md rewritten, and docs/reports/m5-68-revalidation.md
    done_when:           Every figure in VALIDATION-M5.md is measured against 29FD2C52, no superseded figure survives anywhere in it, and each of the nine items below has a verdict with its n.
    forbidden:
      - carrying ANY figure measured against 50573CD9 forward. The signature changed; the figures are void. Re-measure or delete
      - any double, stand-in server or harness in place of a real layer
      - touching TIA. The owner's session is closed and signed
      - claiming or implying an achieved PL, Category, SIL or PFH
      - reporting a pass you did not observe

---

## 1. What changed, and why every figure is void

The owner's session closed at **63 / 63**, all seven stop conditions met.
**F-signature `50573CD9` → `29FD2C52`**, offline equal to online, safety mode
re-activated after download. Six mirrors in Part 0, three conjuncts in
`#safetyDemandClear`, six leaves under `Forklift/Safety/` with a client write
refused (`BadNotWritable`), and no `_1` suffix anywhere.

`docs/VALIDATION-M5.md` was measured entirely against the old signature. **Every
figure in it is now a figure about a program that is not on the CPU.** None
carries forward.

## 2. The run order — it is the owner's, and it is load-bearing

Run in this order. Item 1 gates everything after it.

| # | Section | What must now be true |
|---|---|---|
| 1 | §3 shaft-doubt band | **The reproduction must now FAIL.** Same 0.02 m/s creep, encoders at 15–26 mm/s, and `ShaftDoubtNow` must not form. This is the run that opens all the others |
| 2 | §3 autonomous mission (V3) | The band stopped every mission in its first metre. A mission must now leave rest |
| 3 | §1.2 / §5 scanner slows (V5) | F4's whole reason. With the WARN sender in place, a teleoperated vehicle must fall to **0.20 m/s** on a warning trip and stop at the protective boundary. The 1.000 m/s row becomes a 0.20 m/s row |
| 4 | §6.2 demand reaches the plant | F1's whole reason. **Publisher count 1**, six leaves, and motion refused under a standing demand |
| 5 | §4 safety in autonomous (V4) | Never run — the items above are what blocked it. This is a first result, not a re-measurement |
| 6 | §0 boot state | Two mirror nodes are new, and `TorqueOffDemand` boots TRUE. Two rows |
| 7 | §2 e-stop (V2) | Same program changed underneath it. Re-measure the chain latency |
| 8 | §6.1 AT-10 / SS1 | The onset budget moved 0.80 s and the standstill window narrowed. Enforcement starts later; SS1's second stage did not change |
| 9 | §1.1 scanner stops (V1) | Behaviour must not change — **but it is a different program**, so it is re-measured, not assumed |

## 3. The rules that make this mean something

- **Stillness is not evidence.** A stopped process and a genuine inhibit are
  indistinguishable by motion. Every claim that something did not happen carries
  a **positive control in the same run**.
- **Every figure states its n.**
- **No layer may be a double.** m5-62's torque-off figures were honestly marked
  double-only; item 4 is where they are earned live or not at all.
- Check the machine is yours before each timed run and record what you checked.
- A run whose precondition was never confirmed is **discarded, not repaired**.

## 4. One narration question to answer explicitly

The vault safety review's finding **F1** says the sentence *"the operator cannot
crash the vehicle"* currently needs a **direction qualifier**: the SRS carries a
39.9° load-direction residual on SF-10's speed limit, and SF-10 reached nothing
while teleop was not slowed by the warning field. Items 3 and 4 are exactly the
couplings that were missing.

**So answer it with the run:** after this session, can that sentence be said
without the qualifier, or not? Say which, and on what evidence. The owner
narrates from this document.

## 5. Two hazards from earlier runs

- With the writer running and **no field source**, `WarningFieldClear` is FALSE,
  the reduced limit is in force, and **no monitored reset is accepted** while the
  vehicle is above it. This has cost three agents a run. Plan it into startup.
- `SpeedChainSeen` is TRUE and **only a cold start clears it.**

## 6. The document

`docs/VALIDATION-M5.md` is what the owner narrates the recorded showcase from.
Rewrite it so that a reader cannot mistake an old figure for a current one —
and state the signature it belongs to at the top. Say plainly what is proven and
what is not, and never blur them.

## 7. Working discipline

- Read `docs/LESSONS.md` first.
- **Write each result into the document as it lands.** Do not hold nine.
- **Do not commit.** The orchestrator commits by pathspec.
