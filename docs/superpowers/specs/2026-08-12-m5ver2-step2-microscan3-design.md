# m5_ver2 Step 2 — three SICK microScan3 sensors, field evaluation, and the PLC safety network

Design, 2026-08-12. Approved by the owner before implementation.

## 1. Goal

Put three safety laser scanners on the forklift, evaluate their protective and
warning fields the way `m5-plc-debug/microscan3.py` already does, show all three
on the HMI, and drive the **real F-PLC's** `PF_OSSD` and `WF_Clear` inputs from
the **Back** sensor.

Step 1 proved the E-Stop chain reaches the Gazebo forklift through the PLC
(`m5_ver2/step1/PROOF.md`, 8 of 8). Step 2 makes a *sensed obstacle* do what the
e-stop button did.

## 2. What Step 1 established, that this builds on

| Fact | Where |
|---|---|
| `step1.py` is the only PLCSIM API writer; UDP 5100 carries PLC state to WSL | Step 1 §7.1 |
| `plc_link` never falls silent — it publishes FAILSAFE on staleness | Step 1 §7.2 |
| `cmd_gate` zeros the command; `sto_contactor` removes torque at the plant | Step 1 §5.3 |
| `hmi_node` shows the safe state when status is stale | Step 1 §7.3 |
| Ceasing to publish is **not** stopping — the joint controllers hold the last setpoint | Step 1, Task 6, measured |
| The forks are the model's **−x**; teleop drives forks-first | commit `ab258b2` |

`CASE_B0` / `CASE_B1` were deliberately left unconsumed in Step 1. Step 2 is
where they arrive.

## 3. Verified environment

Measured 2026-08-12, before the design was fixed — the Step 1 lesson was to
prove the transport first.

| Fact | Result |
|---|---|
| UDP **WSL → Windows on 5101** | **works, no firewall block** — `GOT b'{"probe":"step2","pf":true,"wf":false}' from ('172.19.180.72', 41784)` |
| Windows host as seen from WSL | `172.19.176.1` (the NAT gateway) |
| WSL guest as seen from Windows | `172.19.180.72`, reassigned on every WSL restart |

The reverse direction (5100, Windows → WSL) was proven in Step 1. Both
directions now have evidence, so the port map is no longer aspirational.

## 4. The device, and what is being modelled

`m5-plc-debug/microscan3.py` is the behaviour under test and the owner has
already validated it against the PLC. Its logic, reproduced exactly:

```python
FIELDS = {1: (1.0, 2.5), 2: (2.2, 3.7), 3: (4.5, 6.0)}   # case: (PF, WF) [m]
N_SCAN = 3                                               # consecutive scans

def field(d, clear, cnt, th):
    raw = d > (th if clear else th + 0.2)                 # +0.2 m hysteresis
    cnt = cnt + 1 if raw != clear else 0
    return (raw, 0) if cnt >= N_SCAN else (clear, cnt)
```

Three properties of it are load-bearing and must survive the port to ROS:

- **`pf` and `wf` are TRUE when CLEAR**, matching the PLC's `PF_OSSD` ("True =
  protective field clear, OSSD high") and `WF_Clear`. Getting this polarity
  backwards inverts the safety function.
- **No measurement means violated.** On timeout the script sets `pf = wf =
  False`. Silence is not "clear".
- **An unknown monitoring case selects case 3**, the largest field. Case 3 is
  therefore not an optional extra — it is the value the system falls into when
  the case bits are unreadable, so it is the fail-safe path and must work.

### 4.1 Decision: the field test is radial, not a contour

A real microScan3 evaluates a configured *contour*. This step takes the minimum
range over the sensor's fan and compares it against a scalar threshold, exactly
as `microscan3.py` does with its single `d`.

Two reasons. The owner asked for the debug logic "as it was", and radial
thresholds are what that file implements. And the owner's own reference drawing
shows the fields as circular fans, not vehicle-shaped contours.

Contour shaping is a later step's work if it is wanted. `agv/forklift/scripts/field_evaluation.py`
already does it for the old stack and is the reference if so.

**A ray that returns nothing is not an obstacle at zero.** `gz` reports a
no-return as `inf` (and can report `nan`). Those are the *clear* case and must
be treated as the range maximum before the minimum is taken — the naive
`min(ranges)` on an array containing `nan` returns `nan`, and on one containing
only `inf` returns `inf`, and neither compares usefully against a threshold. The
evaluator replaces non-finite samples with `<max>` first, then takes the
minimum. Getting this wrong makes a clear horizon read as an intrusion.

**A stale scan is a violation.** If no scan has arrived for `SCAN_STALE_S`, the
device reports both fields violated, matching `microscan3.py`'s 0.3 s socket
timeout. `SCAN_STALE_S = 0.5` — five missed scans at 10 Hz, so it cannot trip on
ordinary jitter, and deliberately not an exact multiple of the evaluation tick
(Step 1 §7.2 records why exact multiples are a trap).

**An unreadable monitoring case selects case 3.** If `/plc/status` is stale or
carries no `case`, or the value is not 1, 2 or 3, the evaluator uses case 3 —
the largest field. This is `microscan3.py:16` and `:22` and it is the fail-safe
direction: not knowing which case applies means assuming the most demanding one.

### 4.2 Decision: 1oo2 is the PLC's, not the simulation's

The owner ruled this explicitly. The simulation produces **one** boolean pair
per device. 1oo2 is a property of the fail-safe input card, and
`m5_ver2/CLAUDE.md` §3 already records that in PLCSIM those channel pairs
collapse to a single process-image bit.

The alternative — deriving two "channels" from the same rays and cross-checking
them — would look like redundancy while sharing every common-cause failure, and
`agv/forklift/model.sdf:362-365` already refuses exactly that: *"the safe
channel is not here and is not a topic. It is derived from these same rays, off
this file, and it is not a second independent channel."*

Nothing in Step 2 claims a Category, a Performance Level, a SIL or a PFH.

### 4.3 Decision: the scanner range becomes 8.0 m

`microscan3.py`'s case 3 warning field is 6.0 m. The existing scanners cap at
5.5 m. With `d` capped at 5.5, the test `d > 6.0` can never pass, so **the
warning field would read as permanently violated in case 3** — the fail-safe
case.

This did not show in the debug setup because `world_sim.py` supplied `d` by
hand with no range ceiling.

The three new sensors therefore use `<max>8.0</max>`. That is honest for the
device class — a real microScan3's warning field reaches well beyond its
protective field — it clears case 3 by 2 m, and the model's `nav_lidar` already
uses 8.0. The field values from the debug script are unchanged.

## 5. Sensor placement

From the owner's reference drawing. **Front is the fork end**, which is the
model's **−x**; the model's own `safety_scanner_front_link` sits at +0.70, the
drive end, so the existing names are the opposite of the owner's convention.

### 5.1 Decision: the old scanner pair is deleted, not kept alongside

Keeping `safety_scanner_front` (at the end the owner calls the *back*) beside a
new `safety_scanner_back` is a naming trap that would eventually wire the wrong
device to the PLC. `forklift_ver2` carries exactly three scanners, named in the
owner's frame.

### 5.2 Geometry

Chassis is a `1.40 × 0.90 × 0.50` box centred at `(0, 0, 0.45)`, so it spans
x ∈ [−0.70, +0.70], y ∈ [−0.45, +0.45]. Forks are at x = −1.35.

| Sensor | Drawing position | Model pose (x y z, yaw) | Blind sector points |
|---|---|---|---|
| `back` | rear face, centred | `+0.72  0.00  0.15`, yaw `0` | into the vehicle (180°) |
| `left` | left side, fork-end corner | `−0.68  −0.46  0.15`, yaw `−2.3561945` (−135°) | into the vehicle (+45°) |
| `right` | right side, fork-end corner | `−0.68  +0.46  0.15`, yaw `+2.3561945` (+135°) | into the vehicle (−45°) |

Vehicle-left is the model's **−y**, because the owner's frame is the model's
rotated 180° about z.

Scan parameters, carried over from the existing scanners: `gpu_lidar`, 10 Hz,
275 samples, `min_angle −2.3998277` / `max_angle +2.3998277` (±137.5°, so a 275°
fan and an 85° blind sector), range `0.10` to `8.0`, resolution `0.01`. The
housing visual sits 20 mm below the scan plane so a scanner cannot see its own
mount.

## 6. Architecture

```
Gazebo: 3 x gpu_lidar          forklift_ver2/model.sdf
   │  /forklift/gz/safety_scanner_{back,left,right}/measurement
   │  (ros_gz_bridge)
   ▼
field_eval.py
   │   per sensor: min range over the fan -> (pf, wf)
   │   debounce 3 scans, +0.20 m hysteresis, no measurement = violated
   │   monitoring case read from /plc/status
   │
   ├──► /forklift/safety/fields  (std_msgs/String, JSON)  ──►  hmi_node.py
   │                                                            three lamps
   ▼
sensor_link.py          BACK SENSOR ONLY
   │  UDP 5101
   ▼
Windows: step2.py       the only PLCSIM API writer
   │  plc.WriteBool("PF_OSSD", back.pf)
   │  plc.WriteBool("WF_Clear", back.wf)
   │  plc.ReadBool("CASE_B0"), ReadBool("CASE_B1")  ──► UDP 5100 ──► plc_link
   ▼
F-PLC safety program: ESTOP1 on the protective field -> Motor drops
   -> plc_link -> cmd_gate zeros the command
   -> sto_contactor opens -> the forklift stops
```

### 6.1 The behavioural change that makes this step matter

In Step 1, `step1.py` wrote `PF_OSSD=True` and `WF_Clear=True` unconditionally
every cycle, because they were a *precondition* for `Motor` ever energising and
were not the subject of the test.

In Step 2 they are driven by the Back sensor. Two consequences:

1. An obstacle in the protective field now stops the vehicle through the same
   chain the e-stop button used, and the stop originates in Gazebo rather than
   at a console.
2. **If the sensor link dies, `PF_OSSD` goes False and `Motor` drops.** That is
   a new fail-safe path and it is deliberate — the same "say the failure out
   loud" rule `plc_link` follows in Step 1.

### 6.2 `step2.py` owns a staleness rule on 5101, and it is not optional

`sensor_link.py` sends on every evaluation, so 10 Hz. `step2.py` must **not**
simply hold the last value it received: a dead `sensor_link`, a dead
`field_eval`, or a dead Gazebo would then leave `PF_OSSD` standing at True
forever while nothing is watching the field.

This is the identical hole Step 1's review found in `cmd_gate` — a node that
trusted a topic without a timeout because the *upstream* node was designed never
to fall silent. Silence still has to be caught by the consumer.

So: no datagram on 5101 within `SENSOR_STALE_S = 0.4` and `step2.py` writes
`PF_OSSD=False`, `WF_Clear=False`. Four missed sends at 10 Hz. The budget:

| Term | Value |
|---|---|
| `SENSOR_STALE_S` | 0.40 |
| `+ step2.py cycle` | 0.02 |
| **worst case to `PF_OSSD` False** | **< 0.42 s** |

The vehicle then stops through the Step 1 chain, whose own budget (< 0.45 s from
`Motor` dropping) sits after this one. These are sequential, not parallel: a
dead sensor link costs both.

## 7. Components

All paths relative to `m5_ver2/step2/`.

| File | Origin | Change |
|---|---|---|
| `windows/step2.py` | copy of `step1.py` | writes `PF_OSSD`/`WF_Clear` from the Back sensor; reads `CASE_B0`/`CASE_B1`; binds UDP 5101 |
| `ros2/status_contract.py` | copy | gains the `case` field |
| `ros2/plc_link.py` | copy | republishes `case` |
| `ros2/cmd_gate.py` | copy | unchanged |
| `ros2/hmi_node.py` | copy | three sensor lamps |
| `ros2/field_eval.py` | **new** | the microScan3 model |
| `ros2/sensor_link.py` | **new** | Back sensor → UDP 5101 |
| `gazebo/forklift_ver2/model.sdf` | copy of `agv/forklift/model.sdf` | three scanners, range 8.0 |
| `gazebo/step2_world.launch.py` | copy | spawns `forklift_ver2`, bridges three scan topics |
| `step2.sh`, `tests/`, `README_step2.md` | copy | extended |

### 7.1 Decision: Step 2 copies Step 1 rather than referencing it

The owner ruled this: *"her step'in ayrı ayrı çalıştığını görmek istiyorum."*
It reverses Step 1 §5.2, which referenced `agv/` and `sim/` in place.

The accepted cost is that `model.sdf` now exists in two places and a fix to one
does not reach the other. What is bought is that each step is a complete,
independently runnable record of what worked at that point — which is what the
owner wants to be able to inspect.

`forklift_ver2/model.sdf` is a *copy* of `agv/forklift/model.sdf`, so `agv/` is
never modified.

## 8. GUI

The two Step 1 indicators stay. Three sensor lamps are added below them.

| Condition | Colour | Text |
|---|---|---|
| `pf` clear, `wf` clear | green | `Back Sensor : Safe` |
| `pf` clear, `wf` violated | orange | `Back Sensor : Warning Field` |
| `pf` violated | red | `Back Sensor : Protective Field` |

Same for `Left Sensor` and `Right Sensor`. Protective outranks warning: a
protective violation always shows red regardless of the warning state.

No measurement, or `/forklift/safety/fields` stale, shows **red** — the safe
display, matching `microscan3.py`'s timeout behaviour and the Step 1 rule that a
display which has lost its source must not show a comfortable state.

## 9. Ray visualisation

The three sensors carry `<visualize>true</visualize>` and the GUI's
**Visualize Lidar** plugin reads the real `/measurement` topics.

**No repeater node.** The previous milestone's visual clutter had a recorded
cause: `agv/forklift/launch/vehicle.launch.py:429-445` measured that the plugin
resolves its anchor from the *sensor entity behind the topic*, so real sensor
topics track the vehicle correctly while repeated `viz/*` topics — which no
sensor entity owns — draw every fan at the world origin. The repeater was the
clutter, not the rays.

## 10. Port map

| Port | Direction | Payload | Step |
|---|---|---|---|
| 5100 | Windows → WSL | `estop_healthy`, `motor`, **`case`**, `ts` | 1, extended in 2 |
| 5101 | WSL → Windows | Back sensor `pf`, `wf`, `ts` | **Step 2** |

Both directions are now measured, §3.

## 11. Out of scope

- Left and Right sensors reaching the PLC. The F-PLC has one sensor input
  configured; they are HMI-only in this step. This is the owner's constraint,
  not a simplification.
- Contour-shaped fields (§4.1), speed-dependent case switching, VDA 5050, the
  fleet, OPC UA.
- Any change to `agv/`, `sim/`, `plc/`, TIA Portal content, or Step 1.

## 12. Acceptance — the owner's five steps

| # | What | Evidence |
|---|---|---|
| 1 | Three sensors on `forklift_ver2` | Gazebo screenshot, placement matching the drawing |
| 2 | Datasheet-faithful scan configuration, reading real data | live `ros2 topic echo` of the three scans |
| 3 | Fields drawn as blue rays in Gazebo, cleanly | screenshot, and the RTF cost measured |
| 4 | Three lamps, transitioning Safe / Warning / Protective in a live drive | screenshot per state |
| 5 | Back sensor drives the PLC; the safety network reacts | `Motor` drops on a protective intrusion, measured end to end |

Each step is validated before the next begins — the owner's instruction.
