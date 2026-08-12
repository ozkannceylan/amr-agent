# m5_ver2 Step 3 — the safe-speed reading channels

Design, 2026-08-12. Approved by the owner before implementation.

## 1. Goal

Feed the F-PLC's `ENC_A` and `ENC_B` from the simulated forklift's drive
shaft, add an encoder-health lamp to the HMI, and make the third ESTOP1
instance — the speed/encoder monitor — demonstrable end to end.

Step 3 is Step 1 plus Step 2 plus the encoders. With it, the whole
`m5-plc-debug` system runs against the real F-PLC in Gazebo.

## 2. What the debug script does, and what changes

`m5-plc-debug/encoder.py`:

| | |
|---|---|
| Input | speed `v` in m/s from UDP 5007 |
| Conversion | `v_mm = int(v * 1000)` |
| Channels | `a = v_mm + rand(-5, 5)`, `b = v_mm + rand(-5, 5)` |
| Fault modes | `ok` · `fa` (channel A frozen) · `oa` (channel A offset +400) |
| Output | `{a, b}` → `ENC_A` / `ENC_B` |

**The synthetic noise goes away.** `forklift_ver2/model.sdf` already publishes
two reading channels on the drive shaft — `/forklift/gz/drive_speed/read_a`
and `read_b`, two `JointStatePublisher` systems on `drive_wheel_joint`. Two
independent renders of the same physical quantity produce their own small
differences, which is what the `rand(-5, 5)` was standing in for. Step 3 reads
the plant instead of inventing the disagreement.

**The fault modes stay**, because the owner needs to see the unhealthy lamp,
and an encoder that never fails cannot demonstrate the monitor.

### 2.1 The honest name for this arrangement

`agv/forklift/model.sdf` and `config.yaml` already settle it and Step 3 keeps
their language: **a single-channel tested system, never a two-channel one.**
One shaft, one measured quantity, two readings of it. Both readings die with
the shaft they read. That is what a real safe encoder is; calling it
two-channel would claim a redundancy that does not exist.

No Category, no Performance Level, no SIL, no PFH is claimed anywhere in
Step 3.

## 3. What the safety program does with them

From `m5_ver2/CLAUDE.md` §3.2, unchanged and not ours to alter:

- Cross-check: `|ENC_A − ENC_B| > 50` → fault.
- Ceiling: 2800 mm/s.
- The encoder monitor is one of three ESTOP1 instances; `Motor` is their AND.
- A demand **latches**. Clearing the fault does not re-enable; an
  `Acknowledge` edge does.

So `oa` (+400 mm/s offset) trips the cross-check immediately, and `fa` (frozen
channel A) trips it as soon as the vehicle moves. Both then require `a`.

## 4. Architecture

```
gz: /forklift/gz/drive_speed/read_a ─┐   JointState, drive_wheel_joint
    /forklift/gz/drive_speed/read_b ─┤   two readings, one shaft
                                     ▼
                           encoder_link.py
                             omega [rad/s] x wheel_radius x 1000 -> mm/s
                             per channel, independently
                                     │  /forklift/safety/encoders
                                     ├──────────────────► hmi_node.py (lamp)
                                     ▼
                           sensor_link.py   merges with the field verdict
                                     │  UDP 5101
                                     ▼
                              step3.py     ← THE FAULT MODE IS INJECTED HERE
                                     ▼
                     plc.WriteInt16("ENC_A", a) / ("ENC_B", b)
                                     ▼
                 F-program: cross-check and ceiling -> Motor
```

### 4.1 Decision: the fault is injected on the Windows side

`step3.py` already plays the field devices — the PLCSIM API *is* the wiring,
and a broken encoder is a field fault, not a vehicle-software fault. Putting
the modes there also keeps every operator command in one terminal beside
`es0` / `es1` / `a`, rather than splitting them across two machines.

The vehicle therefore sends the **true** measured channels and never lies.
`step3.py` corrupts one on its way to the PLC, which is exactly where a real
broken encoder would corrupt it.

### 4.2 Decision: one wire, not a new port

The encoder values ride the existing UDP 5101 payload beside the field
verdict, rather than taking port 5102. One process sends the vehicle's safety
inputs, and `step3.py` has **one** staleness rule covering both. Two links
would mean two timeouts and a state where one is fresh and the other is not.

Wire format on 5101 becomes:

```json
{"pf": bool, "wf": bool, "enc_a": int, "enc_b": int, "ts": float}
```

`enc_a` and `enc_b` are mm/s integers, matching the PLC's `Int` tags.

### 4.3 Fail-safe directions

| Condition | Result |
|---|---|
| No 5101 datagram within `SENSOR_STALE_S` | `PF_OSSD`/`WF_Clear` False **and** `ENC_A`/`ENC_B` written to a value the monitor faults on |
| No joint state within `ENC_STALE_S` | `encoder_link` reports the channels as unhealthy; the last speed is not held |
| A non-integer or missing encoder field | the datagram is rejected whole, as now |

**The stale-encoder value is a decision, not a detail.** Writing 0/0 on a dead
link would read as "stopped and healthy" — the most dangerous possible lie,
because the vehicle may be moving. Step 3 writes `ENC_A = 0` and
`ENC_B = 3000`: they disagree by far more than 50, so the cross-check faults,
and 3000 also exceeds the 2800 ceiling. A dead encoder link is a demanded
stop, by two independent routes in the F-program.

## 5. The HMI

A fourth lamp under the three scanner lamps:

| Condition | Colour | Text |
|---|---|---|
| `\|a − b\| ≤ 50` and link fresh | green | `Encoder : Healthy` |
| `\|a − b\| > 50`, or stale, or never received | red | `Encoder : Fault` |

Same rule as every other indicator in this project: a display that has lost
its source shows the safe state, not the last comfortable one.

The lamp reads `/forklift/safety/encoders`, which carries the **true**
channels. So with a fault injected on the Windows side the lamp reads Healthy
while the PLC faults — and that disagreement is correct and worth seeing: it
says the vehicle believes its encoders while the field wiring is broken. The
README must say so, or it reads as a bug.

## 6. Files

`m5_ver2/step3/` is a copy of `m5_ver2/step2/`, per the owner's standing
ruling that each step runs on its own. Partition `step3`, domain **93**.

| File | Change |
|---|---|
| `ros2/encoder_link.py` | **new** — two JointState topics → mm/s → `/forklift/safety/encoders` |
| `ros2/sensor_link.py` | merges the encoder values into the 5101 payload |
| `ros2/hmi_node.py` | the fourth lamp |
| `windows/step3.py` | fault modes; writes `ENC_A`/`ENC_B` |
| `gazebo/step3_world.launch.py` | bridges the two drive-speed topics |
| `step3.sh` | starts `encoder_link` |

`ENC_A = 0, ENC_B = 0` disappears from the write loop — it was Step 1's
placeholder for exactly this.

## 7. Terminal commands on `step3.py`

| Command | Effect |
|---|---|
| `es0` / `es1` / `a` / `q` | as Steps 1 and 2 |
| `ok` | encoders passed through as measured |
| `fa` | channel A frozen at its last value |
| `oa` | channel A offset by +400 mm/s |

Same three names as `encoder.py`, so the owner's muscle memory carries over.

## 8. Acceptance

| # | What | Evidence |
|---|---|---|
| 1 | Both channels read the real shaft | live `/forklift/safety/encoders` while driving, mm/s tracking commanded speed |
| 2 | Healthy operation | `\|a − b\|` small, lamp green, `Motor` stays on while driving |
| 3 | `oa` faults the monitor | `Motor` drops, lamp behaviour as §5 |
| 4 | `fa` faults once moving | `Motor` drops after the vehicle starts |
| 5 | `a` recovers after `ok` | latch cleared, driving resumes |
| 6 | Dead link is a stop | kill `sensor_link`, `Motor` drops |

Stops are asserted the way Steps 1 and 2 asserted them: the actuator terminal
value, `torque_off_applied` with the contactor alive, and a pose sampled
before and after. Never from stillness alone.

## 9. Out of scope

`V_Limit` enforcement, SLS ramp monitoring, the standard program in the
command path, VDA 5050, the fleet. Left and right scanners still do not reach
the PLC.
