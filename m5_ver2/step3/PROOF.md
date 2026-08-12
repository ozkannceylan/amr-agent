# Step 3 — the safe-speed reading channels

Run **2026-08-12**. PLCSIM Advanced `PLC_2` in RUN, vehicle side from
`step3.sh start` (partition `step3`, domain 93), `step3.py` on Windows 64-bit
Python. Every number below was measured in these runs.

**Four of six acceptance rows pass. Two are not done, and §3 says why.**

| # | Step | Expected | Measured |
|---|---|---|---|
| 1 | Both channels read the real shaft | mm/s tracking the commanded speed | driving forks-first at 0.5 m/s commanded: **`enc = -282/-282`**, then `-240/-240`. Sign negative because forks-first is the model's −x. Both channels agree to 0 mm/s. **PASS** |
| 2 | Healthy operation | `\|a − b\|` inside the F-program's 50 mm/s, `Motor` on | `a − b = 0` throughout; `Motor` energised on `a` at t=6.4 with `enc = 0/0` and again at t=6.6 with the shaft turning. **PASS** |
| 3 | `oa` faults the monitor | `Motor` drops | `oa` at t=26.4 → **`enc = 400/0`** → `Motor=False` in the same sample. **PASS** |
| 4 | `fa` faults once moving | `Motor` drops | **NOT DONE** — see §3. |
| 5 | `a` recovers after `ok` | latch clears, driving resumes | `ok` at t=36 left `Motor` **False** — the latch. `a` at t=40.7 → `Motor=True`. **PASS** |
| 6 | Dead link is a stop | kill `sensor_link`, `Motor` drops | **NOT DONE** — see §3. |

## 1. The `oa` fault, in full

`step3.py`'s status line, one run, its own clock:

```
 1.492  Motor=False PF=False WF=False case=1 enc=   0/0    ok    no link yet
 6.382  Motor=True  PF=True  WF=False case=1 enc=   0/0    ok    'a' -> Motor ON
26.379  Motor=False PF=True  WF=False case=1 enc= 400/0    oa    cross-check fault
36      Motor=False                            enc=   0/0    ok    cleared, still latched
40.699  Motor=True  PF=True  WF=False case=1 enc=   0/0    ok    'a' -> Motor ON
```

`oa` offsets channel A by +400 mm/s against the F-program's 50 mm/s
cross-check. `PF_OSSD` stayed **True** throughout, so nothing but the encoder
monitor can have dropped `Motor` — the third ESTOP1 instance, demonstrated
in isolation from the other two.

Clearing the fault did not re-enable. That is the same ESTOP1 latch the
e-stop button showed in Step 1 and the protective field showed in Step 2,
now reached from a disagreeing encoder pair.

## 2. An unplanned result worth more than the row it broke

Driving at 0.5 m/s commanded, `Motor` came on at t=6.573 and dropped at
t=7.249 — 0.68 s later — with `enc = -282/-282` and then `-240/-240`. The
channels agreed, so the cross-check was not it.

`WF_Clear` was **False**: the aisle racks sit 1.75 m from the back scanner
and the warning field is 2.5 m. Per `m5_ver2/CLAUDE.md` §3.2 the standard
program then computes `V_Limit = 300` mm/s instead of 1500, and the vehicle
was accelerating toward 500 mm/s.

So the speed monitor demanded a stop for exceeding the ceiling that applies
while the warning field is occupied. **That is the third ESTOP1 instance's
other half working**, and it was not on the acceptance list. It also means
the warning field → `V_Limit` → speed monitor path is live end to end, which
Step 2 could not show because nothing was reading speed yet.

## 3. What is not done, and why

**Row 4, `fa`.** The frozen-channel fault only diverges once the shaft turns,
so it needs sustained motion. Sustained motion in this aisle trips the speed
monitor first, for the reason in §2: the warning field is permanently
occupied here, `V_Limit` is 300 mm/s, and driving slowly enough to stay under
it did not turn the shaft fast enough within the run window. Two attempts,
both recorded; neither reached a state where the frozen channel had diverged
by more than 50 mm/s while `Motor` was still on.

The fix is not a code change: park the vehicle where the warning field is
clear, so `V_Limit` is 1500 mm/s and there is room to drive. That is a
positioning problem and it is the next thing to do.

**Row 6, the dead link.** Not attempted. `step3.py` writes `ENC_A = 0` and
`ENC_B = 3000` on a stale 5101 link, which fails both the 50 mm/s
cross-check and the 2800 mm/s ceiling, and unit tests pin those constants —
but the live kill was not run.

Neither gap affects rows 1, 2, 3 or 5, which were each measured before the
gaps appeared.

## 4. What the encoders actually carry

```json
{"a": 0, "b": 0, "healthy": true, "ts": 69031.31}      at rest
enc = -282/-282                                          driving, forks-first
enc =  400/0                                             `oa` injected
```

`encoder_link` reads two `JointStatePublisher` systems on `drive_wheel_joint`
and converts each independently: `omega × 0.12 m × 1000`. The debug script's
`rand(-5, 5)` is gone — with two real renders of the same shaft, the
disagreement is the simulation's rather than a number invented to stand in
for one.

The arrangement keeps the repo's honest name: **a single-channel tested
system, never a two-channel one.** One shaft, two readings, both dying with
the shaft they read. No Category, no Performance Level, no SIL, no PFH is
claimed.

## 5. A test-method note, not a defect

`hmi_node` publishes its centred knob as zero on `/hmi/cmd_vel` at 20 Hz. A
scripted `ros2 topic pub` on the same topic interleaves with it and the gate
forwards whichever arrived last, so the terminal alternates between the
commanded value and zero. Every drive above was therefore run with
`hmi_node` paused (`SIGSTOP`) and resumed afterwards. No file was modified.

That is the cost of driving from a script instead of the window, and it is
recorded so a future run does not rediscover it as a bug.

## 6. State left behind

- `PLC_2` in RUN, **tripped fail-safe**: the last `step3.py` exited through
  `q`, writing `E-Stop`, `PF_OSSD` and `WF_Clear` False. The next run needs
  one `a`.
- The Step 3 stack is up (seven nodes). `./m5_ver2/step3/step3.sh stop`.
- 97 tests passing (`python3 -m pytest m5_ver2/step3/tests/ -q`).
- Step 1's whole-branch review is still deferred.
