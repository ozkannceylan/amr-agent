# Step 4 — V_Limit obeyed rather than violated

Run **2026-08-12**. PLCSIM Advanced `PLC_2` in RUN, vehicle side from
`step4.sh start` (partition `step4`, domain 94), `step4.py` on Windows.

**The claim of this step is NOT proven. Two of five rows pass, one fails,
two are blocked behind the failure.** The code is committed and 106 tests
pass; what is missing is the live demonstration, and §2 says exactly what is
unexplained.

> **Superseded later the same day: see §7.** After the fixes listed there,
> rows 3 and 4 were demonstrated live by the owner and the whole layer was
> recorded on video. §2's oscillation was not re-examined and stays open.

| # | Step | Expected | Measured |
|---|---|---|---|
| 1 | `V_Limit` reaches the vehicle | %MW100 on the 5100 wire | **`vlim=300`** and **`vlim=1500`** both observed in `step4.py`'s status line — the only two values the F-program computes. **PASS** |
| 2 | The stack comes up | seven nodes | came up; the first attempt died and `step4.sh` said so — see §3. **PASS** |
| 3 | The truck creeps in the warning field | speed clamped to 0.30 m/s, no stop | **FAIL.** Commanded −1.2 m/s, the truck accelerated through −140, −191, −258, −300, −832 mm/s and `Motor` dropped at −832. It was not clamped to 300 mm/s. |
| 4 | Full speed in open space | 1.50 m/s available | **BLOCKED** by row 3 |
| 5 | An unreadable `V_Limit` creeps | fail-safe narrows | pinned by unit test; **not run live** |

## 1. What row 3 actually showed

```
 12.517  Motor=True   PF=True  WF=False case=1 vlim=1500 enc= -191/-191
         ...                                              enc= -258/-258
         ...                                              enc= -300/-300
 20.235  Motor=False  PF=True  WF=False case=1 vlim=1500 enc= -832/-832
```

The truck reached 832 mm/s. If `cmd_gate` had been clamping to the creep
ceiling it could not have passed 300. So either the clamp did not apply, or
it applied against a `V_Limit` that was reading 1500 at the time — and the
status line says 1500 at both the enable and the drop.

`Motor` then dropped at 832 mm/s, which is well under the encoder monitor's
2800 mm/s ceiling and with the channels agreeing exactly. **I could not
determine what dropped it.** The candidates are the speed monitor catching a
`V_Limit` that had momentarily read 300, or something not yet identified.

## 2. The unexplained observation, stated rather than smoothed over

**`V_Limit` oscillates between 1500 and 300 while `WF_Clear` is written
steadily False, including with the vehicle parked.** Over one 50 s run:
132 samples read 1500, 84 read 300.

`m5_ver2/CLAUDE.md` §3.2 says the standard program computes `V_Limit = 1500`
when `WF_Clear` else `300`. With `WF_Clear` held False it should read a
steady 300.

Two hypotheses, neither tested:

- **A read/write race.** `step4.py` writes `WF_Clear` and reads `V_Limit` in
  the same 20 ms cycle. OB1 may not have run between them, so the read could
  return a value computed from an earlier input image. This would produce
  exactly this kind of flicker and would be a *measurement* artefact, not a
  PLC fault.
- **`sensor_wf` is not as steady as the status line suggests.** That line
  prints every 10th cycle. Between prints `sensor_wf` could be flipping, and
  `field_eval`'s hysteresis band (±0.20 m about 2.5 m) sits close to the
  measured 1.75 m only while the vehicle moves — but the parked run
  oscillated too, which this hypothesis does not explain.

**Until this is settled, no clamp built on `V_Limit` can be trusted**, which
is why row 3's failure is reported as a failure rather than as a tuning
problem. The next run should log `sensor_wf` and `V_Limit` every cycle rather
than every tenth, and read `V_Limit` in the cycle *after* the write.

## 3. A mechanism that earned itself

The first `step4.sh start` produced:

```
WARNING: cmd_gate exited during startup, see .../logs/cmd_gate.log
THE STACK IS INCOMPLETE.
```

`cmd_gate` uses `from status_contract import (...)`, and the V_Limit patch
was written against the `status_contract.NAME` form. It compiled, and all
105 tests passed, because nothing in the suite constructs the node.

That startup verification was added in Step 1's Task 7 against a hypothetical
and this is its first real catch. Without it the stack would have come up
looking healthy with no gate in the command path.

A guard for the class was added: import each node module and assert its
module-level names resolve. That is the cheapest form of the "no committed
test covers the wiring" finding the whole-branch review raised.

## 4. What is actually built

- `status_contract` gains `v_limit` to the 5100 contract, `V_LIMIT_FULL_MM_S`
  / `V_LIMIT_CREEP_MM_S` / `V_LIMIT_MAX_PLAUSIBLE_MM_S`, and
  `speed_limit_mm_s()`, which narrows anything implausible to the creep
  ceiling. **A fault in the reading must never widen a permission.**
- `cmd_gate` clamps to `min(vehicle limit, PLC permission)`.
- `step4.py` reads `%MW100` and prints it.
- The HMI shows the permission beside the drive-enable line rather than
  taking a sixth lamp.
- The review's "do it before the copy or pay four times" is done: the four
  topic names `config.yaml` has never heard of live in `status_contract`, the
  launch reads the scan names from there, and `encoder_link` reads the two
  drive-speed names from `config.yaml`, which owns them.

## 5. State left behind

- `PLC_2` in RUN, **tripped fail-safe**; the next run needs an `a`.
- The Step 4 stack is up. `./m5_ver2/step4/step4.sh stop`.
- The forklift is not at its spawn pose — it was moved to `(0, 0)` during
  Step 3 and driven since.
- 106 tests passing.

## 6. Also observed, unrelated to the claim

Enabling took **three** `a` pulses in the successful run and did not enable
at all in the run before it, with `E-Stop=True`, `PF_OSSD=True` and the
encoder channels agreeing at 0/0 the whole time. Steps 1 to 3 always enabled
on the first pulse. Not investigated, and it may share a cause with §2.

## 7. Later the same day — rows 3 and 4 demonstrated

Between the run above and this section, four things changed:

- The owner added the right and left scanners to the F-DI
  (`PF_OSSD_right/left`, `WF_Clear_right/left`) with their own ESTOP1
  networks, and corrected their ACK wiring to the shared `Acknowledge`
  input after the first download left it at a literal false.
- The vehicle side grew to match: the 5101 wire carries all six verdicts,
  and `step4.py` writes all six inputs every cycle and trips all six on
  exit.
- The back scanner's self-view mask was re-measured **across the steer
  sweep** — it had been measured at steer zero only, and was the source of
  PROTECTIVE latching in empty space the moment the truck steered
  (`field_eval.py` SELF_MUTE, docs/LESSONS.md 2026-08-12).
- The warehouse was relaid open (`warehouse_ver2.sdf`) and `step4.sh home`
  added, so a latched stop no longer costs a simulator restart.

Then, driven live by the owner: **in the warning field the truck creeps at
the 300 mm/s ceiling instead of accelerating through it (row 3's expected
behaviour, observed), full speed is available in open space (row 4), each
scanner's protective field latches its own stop, and the `home` +
`Acknowledge` cycle recovers without a restart.** The session is recorded
on video, linked from the root README, and that recording is the evidence
for this section — no per-cycle log was captured. A logged rerun of rows
3–5, and §2's oscillation, remain the open items.
