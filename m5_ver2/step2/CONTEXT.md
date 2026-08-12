# Step 2 context

## What Step 2 adds

- Three SICK microScan3 safety scanners on `forklift_ver2` — Back at the drive
  end, Left and Right at the fork-end corners — each a `gpu_lidar` reaching
  8.0 m.
- Field evaluation ported from `m5-plc-debug/microscan3.py`, unchanged: three
  scans in, three `(pf, wf)` verdicts out, selected by the PLC's monitoring case.
- Three HMI lamps, one per scanner, so which device is in demand is visible.
- The **Back** sensor drives the real PLC's `PF_OSSD` and `WF_Clear`. What the
  e-stop button did before, a sensed obstacle does here.

## The field logic, verbatim

From `m5-plc-debug/microscan3.py`, already validated against the PLC by the
owner. Reproduce it; do not improve it.

```python
FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3                                               # consecutive scans

def field(d, clear, cnt, th):
    raw = d > (th if clear else th + 0.2)                 # +0.2 m hysteresis
    cnt = cnt + 1 if raw != clear else 0
    return (raw, 0) if cnt >= N_SCAN else (clear, cnt)
```

The hysteresis is asymmetric on purpose: a field that is currently **clear**
re-tests against the bare threshold `th`, and a field that is currently
**violated** must beat `th + 0.2` before it may clear again. A verdict only
changes after `N_SCAN = 3` consecutive scans agree against it, and the counter
resets the moment a scan agrees with the standing verdict.

Three properties are load-bearing and must survive the port:

- **TRUE means CLEAR.** `pf` and `wf` are True when the field is clear, matching
  the PLC tags `PF_OSSD` ("True = protective field clear, OSSD high") and
  `WF_Clear`. Getting this polarity backwards inverts the safety function.
- **No measurement means violated.** On timeout the script sets `pf = wf =
  False`. Silence is not "clear".
- **An unknown monitoring case selects case 3**, the largest field. Case 3 is
  therefore not an optional extra: it is the value the system falls into when
  the case bits are unreadable, so it is the fail-safe path and must work. This
  is why the scanners reach 8.0 m and not the 5.5 m the old pair used — capped
  at 5.5, case 3's 6.0 m warning field could never pass `d > 6.0` and would read
  as permanently violated in exactly the case the system falls back to.

## The port map

| Port | Direction | Payload |
|---|---|---|
| 5100 | Windows -> WSL | estop_healthy, motor, case, ts |
| 5101 | WSL -> Windows | back sensor pf, wf, ts |
