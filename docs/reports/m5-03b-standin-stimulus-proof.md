# m5-03b — the automated stand-in stimulus, proven in the consumer's view

    brief:               owner ruling 2026-08-04 on roadmap M5 criterion (a) (docs/TODO.md); no separate brief file
    status:              done
    files_changed:
      - plc/forklift-safety/evidence/m5-03b-standin-stimulus-proof.log
      - plc/forklift-safety/evidence/m5-03b-standin-stimulus-proof.ps1
      - docs/reports/m5-03b-standin-stimulus-proof.md
    invariants_touched:  none
    open_questions:      see below
    next_suggested:      the ADR amending criterion (a) may now be written against a proven path, not a plausible one; and the run repeats on the working project `safe_amr` before the gate cites it

---

## What was asked

The owner's 2026-08-04 ruling made the criterion (a) remedy two-part, and part
one was a proof: an API write to the standard-DB stand-in must be shown to stand
**in the consumer's view**, not in the writer's. That qualifier is LESSONS
2026-08-04 — the m5-03 probe's F-DI write returned success and read `True` back
through the API for 60 s while the TIA watch table read `FALSE` for the same
60 s, because the API writes a process image the F-driver overwrites.

## Environment — this qualifies every figure below

TIA project **`safe_amr_FIOPROBE`**, the m5-03 probe copy, running as PLCSIM
Advanced instance **`FIOPROBE`**, CPU 1513F, `OperatingState = Run`. API
**7.0**, `SimulationRuntimeManager` version `458752`, loaded into Windows
PowerShell 5.1. A second instance `safecell3` is registered but `Off`.
**No bridge and no HMI were connected** (`BridgeSeenAlive` and `HmiSeenAlive`
both FALSE at the time), so nothing competed with the writes.

**This is the probe copy, not the working project** — see open question 1.

## Method

The tag list carries all four layers by name, so the chain can be watched end to
end without a watch table:

| Layer | Tags |
|---|---|
| stand-in DB, what the API writes | `SafetyInputStandIn.EStopCircuitClosed` / `.ZoneDeviceCircuitClosed` / `.ResetButtonPressed` |
| **the consumer's view** | `InstF_Forklift_Safety.EStopCircuitClosed` / `.ZoneDeviceCircuitClosed` / `.ResetButtonPressed` |
| F-program outputs | `InstF_Forklift_Safety.EStopDemand` / `.ZoneStopDemand` / `.SafetyResetRequired` / `.SafetyResetFault` |
| standard-side mirror | `ForkliftSafetyMirror.*` |

The consumer layer is the **F-block's own instance data**, which the API never
writes — only the F-program does, by copying the stand-in inside the F-runtime
group. A value appearing there is the F-program having read it.

## Result — PASS, and the F-logic ran on it

Raw sample table: `plc/forklift-safety/evidence/m5-03b-standin-stimulus-proof.log`.

1. **The write reaches the F-program.** `WriteBool` returned in **4.4 ms**;
   `InstF_Forklift_Safety.EStopCircuitClosed` followed **80.4 ms** later —
   inside one F-OB cycle, `FOB_RTG1` being OB123 at 100 ms.
2. **No auto-resume.** With both circuits closed, `EStopDemand`, `ZoneStopDemand`
   and `SafetyResetRequired` all stayed TRUE. Closing a circuit does not clear a
   demand, which is CLAUDE.md §9's restart rule behaving correctly.
3. **The monitored reset ran on API-written data.** `ResetButtonPressed` held
   1000 ms — inside the in-force window, `ResetHoldMinTimer.PT` = **200 ms**,
   `ResetHoldMaxTimer.PT` = **3000 ms**, both read from the running CPU — then
   released. `SafetyResetRequired` and both demands cleared **37.0 ms after
   release**, and the mirror followed. The reset is edge-triggered on release,
   as specified.
4. **Reopening re-asserts.** Opening the E-stop circuit re-raised `EStopDemand`
   **79.1 ms** later, again within one F-cycle, with `ZoneStopDemand` correctly
   staying clear because the zone circuit was still closed.
5. **The CPU was left exactly as found.** The restore sample is byte-identical
   to the baseline sample.

**Why this is not the m5-03 failure repeating.** There, the API's view and the
consumer's view disagreed. Here they agree, and more than that: the F-program
ran multi-step edge-triggered logic on the written values, with correct
no-auto-resume semantics and correct per-circuit discrimination. That behaviour
cannot be an echo of the write.

## What this does and does not establish

**Establishes.** The stimulus can be automated. No human types a value, the
signal reaches the F-program's F-blocks, and F-logic executes on it — which is
the substance the judge review found the watch-table fallback could not deliver,
and it is a materially stronger position than the one ADR 0011 D2 assumed.

**Does not establish.** Any safety integrity claim. The path is a **standard DB**,
and ADR 0011 F6 is unchanged: standard tags are unsafe, TIA's S015 requires a
process-specific validity check per F-runtime group, and TIA's mechanism is
disclosure, not protection. The stand-in stays labelled a stand-in everywhere
(FIO-FEASIBILITY §6 consequence 1), the S015 check is still owed visibly in the
F-code (consequence 2), and ADR 0011 D5's claim boundary — PLr targets only,
never an achieved PL, SIL or PFH — is untouched.

## Open questions

1. **The run is on the probe copy `safe_amr_FIOPROBE`, which is slated for
   deletion** (FIO-FEASIBILITY §0.1 rule 3). Evidence is qualified by the
   environment that produced it (LESSONS 2026-07-27), so the sequence repeats on
   the working project `safe_amr` before the gate cites it. The probe copy also
   should not be worked in meanwhile, or the two projects diverge silently.
2. **CLOSED by the second witness below.** ~~Every reading here came through the
   API.~~ The run was repeated against an independent OPC UA witness.
3. **`RESET_HOLD_MIN` = 200 ms is confirmed in force**, against the five F-OB
   cycles (500 ms) the M4 handover item asks for. The deviation recorded in
   docs/TODO.md is real and unchanged by this run.

---

## Second witness — the CPU's own OPC UA server, 2026-08-04

Open question 2 asked for a reading that did not come through the writer's API.
A TIA watch table was the obvious candidate and could not be reached: adding
rows is an offline edit, and GUI automation of the running project was attempted
and abandoned after three failed clicks rather than persisted with unattended on
a live safety project.

**The OPC UA server is the better witness anyway**, and it was available. It is a
different protocol on a different stack, served by the CPU itself, and it is the
project's actual production data path under invariant 4.

**The decisive detail: `SafetyInputStandIn` is not exposed on that server at
all.** A browse of `opc.tcp://192.168.53.1:4840` finds `ForkliftSafetyMirror`,
`ForkliftStatus`, `ForkliftInput` and `ForkliftOutput` under
`DataBlocksGlobal`, and no stand-in DB. So nothing this witness sees can be an
echo of the writer's process image — the only route from an API write to a
mirror change runs **through the F-program**.

Evidence: `evidence/m5-03b-opcua-witness.log` (the witness, 52 505 polls over
30 s, a ~0.57 ms sampling interval, so the latencies below are behaviour and not
polling artefacts), `evidence/m5-03b-standin-stimulus-proof-run2.log` (the API
writes, wall-clock stamped for correlation), and the two scripts beside them.

| Event | API view (F-block instance) | OPC UA view (mirror) |
|---|---|---|
| circuit closes | demands unchanged | **unchanged** — no auto-resume, confirmed twice |
| reset released → demands clear | 37.0 ms | **41 ms** |
| circuit reopens → demand re-asserts | 79.1 ms | **114 ms** |
| `ZoneStopDemand` while only the E-stop circuit is open | stays clear | **stays clear** |
| restore → demands return | — | **94 ms** |

The two views agree on every transition and on every non-transition. The mirror's
larger figures are expected: it is a standard-side copy written in OB30 at 20 ms
and then published by the server, so it sits one copy and one publish downstream
of the F-block data the API reads.

`ForkliftStatus.ForkliftResetRequired` stayed TRUE throughout, correctly — it is
held by the link latches with no bridge and no HMI connected, which is the same
state `plc/forklift/evidence/m4-cold-start-bridge-down.png` records.

**What this changes.** The proof no longer rests on a single tool's view. The
m5-03 failure mode — writer and consumer disagreeing — is excluded by two
independent consumers agreeing, one of which cannot see the written datum at all.

**Housekeeping from this run.** TIA was left with the *Program info* tab open
rather than the *Forklift M4 gate* watch table, a side effect of the abandoned
GUI attempt. Nothing was modified in the project; the CPU was restored to its
as-found state and the restore sample matches the baseline.
