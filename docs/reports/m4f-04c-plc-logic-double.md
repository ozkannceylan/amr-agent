# Report m4f-04c — PLC logic double for the forklift program

```
brief:               docs/briefs/m4f-04c-plc-logic-double.md
status:              done
files_changed:       [plc/forklift/double/logic.py,
                      plc/forklift/double/server.py,
                      plc/forklift/double/config.yaml,
                      plc/forklift/double/check_kernels.py,
                      plc/forklift/double/README.md,
                      plc/forklift/double/EVIDENCE_DOUBLE.md,
                      docs/reports/m4f-04c-plc-logic-double.md]
invariants_touched:  none — the double is a test artifact of the plc layer and
                     the TIA build remains the plant
open_questions:      one FINDING against plc/forklift/SPEC.md §11, below, which
                     I did not fix because the brief forbids it
next_suggested:      the rehearsal run (m4f-06b's bridge against this double on
                     4850); §11's T5.4 correction wants a plc brief of its own
```

`plc/forklift/double/` serves the §10 forklift surface on port 4850 and runs
`SPEC.md` §7 in a 20 ms loop. **48 checks, 0 failures, exit 0**, reproduced twice
from a fresh boot. Scan loop measured mean 20.6–20.7 ms, max 22.3–22.5 ms.
`asyncua` pinned to **2.0.1** from `/home/ozkan/amr-bridge-venv` — the bridge's
venv, matching `bridge/requirements.txt`; no new dependency. Ports 4840 and
4842–4846 were never bound and `server.py` refuses to start on any of them.
PLCSIM was never contacted.

## FINDING — SPEC §11 steps 5.4.4–5.4.7 cannot demonstrate the stuck reset

**Reported, not fixed.** The logic is correct; the **test procedure** is wrong.
The first kernel run followed §11's step order literally and failed at exactly
the step that claims a held reset can never clear a latch.

| Step, as §11 writes it | What actually happens |
|---|---|
| 5.4.4 attempt a reset while occupied: *"assert **and release** the reset control"* | Refused, correctly. But the control ends **released**, so `ResetEdgeMemory` ends `FALSE` |
| 5.4.6 clear the zone | `causeGone` becomes `TRUE`. Latch correctly stays |
| 5.4.7 *"**Stuck reset**: assert the reset control and leave it asserted"* → *"The latch **never** clears"* | An assertion after a release **is a fresh rising edge**, and the cause is now gone, so `resetRise AND NOT ResetDeviceFault AND latchPending AND causeGone` is satisfied and the latch **clears** |

So 5.4.7 measures nothing, and 5.4.8 is left with nothing to clear.

**Why it matters more than a wording nit.** An owner running T5.4 against the CPU
as written would watch the latch clear at 5.4.7, conclude the edge-triggered
reset was broken, and go hunting for a defect in a program that does not have
one. That is precisely the class of thing the brief wanted surfaced here rather
than in TIA.

**The property §6.7 actually claims is sound and is demonstrated.** §6.7 says *"a
reset held down across a later stop cannot clear that stop's latch either,
because the edge happened before the latch did"*. That needs the control **held
continuously across the moment the cause clears**, with no intervening release —
which is what kernel K4 does instead: assert while occupied, hold, clear the zone
*with the control still held*, and confirm after 1.2 s that nothing cleared. It
passes, and it tests two properties in one hold: the field clearing does not
release the latch, and a held control supplies no edge.

**Suggested correction to §11** (a `plc/` prose change, not logic — the brief
forbids me touching SPEC.md here): make 5.4.4 *assert and hold*, fold today's
5.4.6 into it as "clear the zone with the reset still held", and let 5.4.7 be the
1.2 s observation that nothing cleared. Step count and pass line move with it.

## The transliteration

`logic.py` is §7 statement for statement — same identifiers, same order, same
constants to the digit, no improvement. Where a statement looked redundant it was
transliterated anyway. Two things worth the orchestrator's attention:

**1. The double had to supply `BridgeLinkOk`, which §7 consumes and never
writes.** That tag is owned by `FB_DemoCellControl`, which this double does not
implement. Left unproduced, a bridge would advance `BridgeHeartbeat` forever with
the verdict stuck `FALSE` and no loop could be rehearsed. So `logic.py` carries a
**clearly fenced companion fragment** — the heartbeat half of
`plc/demo-cell/SPEC.md` §7 part 1, transliterated from *that* document with *its*
constant (`HEARTBEAT_STALE_TIME` = `T#500ms`) — and nothing else of the M3 cell:
no conveyor, no panel, no sequence, no `LinkLostLatch`. It is labelled in the
file, the README and the evidence as not being part of §7. The alternative was a
client-settable `BridgeLinkOk` node, which would have invented a node the
interface does not have.

**2. The TONs accumulate the *measured* scan period, not the nominal 20 ms.**
That is what an S7 TON does — it times against the CPU clock, not an assumed
cycle — so a loop that overruns stretches its timers honestly instead of silently
running them slow. Stated because it is the one place the double could have
quietly diverged.

Nothing else in §7 was ambiguous under transliteration. In particular the parts
that have bitten this project before all came through clean: every timer is
called unconditionally at top level with an explicit `PT`, each of the three
setpoints is one `IF`/`ELSE` with the `ELSE` driving `0.0`, `latchPending` is
computed once ahead of both edges, and no latch appears in its own clearing
condition.

## What the kernels established

| Kernel | Established |
|---|---|
| K0 | Namespace array and browse path **read back from the running server**: `Objects → 2:ServerInterfaces → 3:DemoCell → 3:Forklift → …`, with ns 2 = `http://www.siemens.com/simatic-s7-opcua` and ns 3 = `http://DemoCell`, both resolved **by URI** and neither index hardcoded. 20 nodes (the 18 of §10 plus the two shared `DemoCell/Link/` tags). `Output/` and `Status/` refused a client write with **`BadUserAccessDenied`** — §10.3's access rights enforced by the server, proven by attempting the write rather than by reading a flag |
| K1 | Boot polarity: both link verdicts `FALSE` from the first scan, both link latches formed, `ForkliftResetRequired` `TRUE` from power-up — and **`ForkliftObstacleStopActive` `FALSE` even though the field bit's start value really is `TRUE`**, which is the `bridgeLinkOk` conjunct in part 3 doing its job. A link coming up energizes nothing |
| K2 (T5.3) | Cap engages at the fork threshold **with the operator's control untouched**: 1.00 → 0.30 m/s. At a 0.2 demand the setpoint is 0.06, so the cap limits rather than commands, and `ForkliftSpeedLimitActive` stays `TRUE` |
| K3 (T5.2) | Both soft limits abort **in the offending direction only**; the carriage is never stranded; nothing latches |
| K4 (T5.4) | The latch **overrides a live command** — all three setpoints `0.0` while the traction request still stands at 1.0. Reset refused while occupied; field clearing does not release; a held control clears nothing; a fresh edge clears and **energizes nothing**; teleop returns only on a fresh enable edge |
| K5 (T5.5) | All three setpoints reach `0.0` **642 ms** (643 ms on the re-run) after the last advancing heartbeat, inside `HMI_STALE_TIME` + one scan. The loss latches, and a returning heartbeat restores nothing |

## Notes

- **The double is not evidence about the plant.** A kernel passing says the
  specification is self-consistent and executable; the TIA build is verified by
  the owner's own §11 run against the CPU. The README says this in its first
  lines, and states that any divergence resolves toward TIA + SPEC.
- **No plant model.** The four `Forklift/Input/` values are whatever a client
  writes; nothing integrates the fork or moves the machine.
- **The plausibility latches were not demonstrated** and their absence is not a
  pass. They are reachable here — a client can write an out-of-window value,
  unlike the real plant — but they are not among the four briefed kernels, and
  the double is not the place to close `SPEC.md` §12 item 6, which asks for
  injection at the bridge.
- One defect was found and fixed **in my own harness**, not in the double:
  `asyncua` 2.0.1 exposes `UaStatusCodeError.code` as an `int`, not an object
  with `.name`.
- `bridge/`, `hmi/`, `sim/`, `agv/` and `docs/interfaces/` were not read for code
  and not touched. The namespace layout was built from `opcua-nodes.md` §2.1 and
  §10.3 as the coordinator directed, not from the bridge's test-double sources.
