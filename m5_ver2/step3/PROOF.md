# Step 3 — the safe-speed reading channels

Run **2026-08-12**. PLCSIM Advanced `PLC_2` in RUN, vehicle side from
`step3.sh start` (partition `step3`, domain 93), `step3.py` on Windows 64-bit
Python. Every number below was measured in these runs.

**All six acceptance rows pass.**

| # | Step | Expected | Measured |
|---|---|---|---|
| 1 | Both channels read the real shaft | mm/s tracking the commanded speed | driving forks-first at 0.5 m/s commanded: **`enc = -282/-282`**, then `-240/-240`. Sign negative because forks-first is the model's −x. Both channels agree to 0 mm/s. **PASS** |
| 2 | Healthy operation | `\|a − b\|` inside the F-program's 50 mm/s, `Motor` on | `a − b = 0` throughout; `Motor` energised on `a` at t=6.4 with `enc = 0/0` and again at t=6.6 with the shaft turning. **PASS** |
| 3 | `oa` faults the monitor | `Motor` drops | `oa` at t=26.4 → **`enc = 400/0`** → `Motor=False` in the same sample. **PASS** |
| 4 | `fa` faults once moving | `Motor` drops | `fa` at t=22 froze channel A at 0; the wheel then turned and B read −63 mm/s. **`enc = 0/-63`** → `Motor=False` at t=26.8. `ok` + `a` at t=44.5 restored it. **PASS** |
| 5 | `a` recovers after `ok` | latch clears, driving resumes | `ok` at t=36 left `Motor` **False** — the latch. `a` at t=40.7 → `Motor=True`. **PASS** |
| 6 | Dead link is a stop | kill `sensor_link`, `Motor` drops | `kill -9` on `sensor_link` mid-run → **`enc = 0/3000`**, `PF=False`, `Motor=False` at t=29.2. **PASS** |

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

## 2. An unplanned result worth more than the row it delayed

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

## 3. The two rows that took three attempts each

Both are recorded because the failures were more instructive than the passes.

**Row 4, `fa`.** The first two attempts drove at 0.5 and 0.22 m/s and failed
for two different reasons — the first tripped the speed monitor before the
channels could diverge (§2), the second never energised `Motor` at all.

The real mistake was in the method, not the speed: **a frozen channel does
not diverge at a constant speed.** `fa` holds A at its last value while B
keeps reading, so if the speed does not change the two agree and nothing
faults. The divergence needs a speed *change* after the freeze.

The run that worked: drive, send `fa` while stationary so A froze at 0, then
let the wheel turn. B read −63 mm/s against a frozen 0, which is 63 against
the F-program's 50 mm/s limit, and `Motor` dropped.

```
 6.398  Motor=True  PF=True  enc=    0/0     ok    'a' -> Motor ON
        ---- fa ----                               channel A freezes at 0
        enc = 0/-63                          fa    the wheel turns, B follows
26.782  Motor=False PF=True  enc=    0/0     fa    cross-check fault
44.487  Motor=True  PF=True  enc=    0/0     ok    'ok' + 'a' -> restored
```

**Row 6, the dead link.** `kill -9` on `sensor_link` with `Motor` energised:

```
 6.562  Motor=True  PF=True  enc=    0/0     ok
29.213  Motor=False PF=False enc=    0/3000  ok    link dead, timeout fired
```

`step3.py`'s 0.40 s timeout wrote the stale values, and `0/3000` fails the
50 mm/s cross-check and the 2800 mm/s ceiling at once. `PF_OSSD` went False
in the same sample, so the vehicle was demanded to stop by three routes
together — which is the point of putting both inputs on one datagram with
one staleness rule.

No cross-machine interval is quoted for either row: the Windows and WSL
clocks disagree and are not synchronised, the same discipline Steps 1 and 2
kept.

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
