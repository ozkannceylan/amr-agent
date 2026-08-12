# Step 2 — three microScan3 scanners, end to end

Run **2026-08-12**. PLCSIM Advanced `PLC_2` in RUN, vehicle side from
`step2.sh start` (partition `step2`, domain 92), `step2.py` on Windows 64-bit
Python. Every number below was measured in these runs.

**No level is asserted from a screenshot.** Each one is read from
`/forklift/safety/fields`, which is the same value the HMI lamp renders, and
each PLC state is read from `step2.py`'s own status line.

| # | Step | Input | Expected | Measured |
|---|---|---|---|---|
| 1 | Three scanners placed | `forklift_ver2/model.sdf` | back centred on the rear face, left and right at the fork-end corners | `back 0.72 0 0.15 yaw 0` · `left -0.68 -0.46 0.15 yaw -135°` · `right -0.68 0.46 0.15 yaw +135°`. Rear view shows the back housing centred under the counterweight; fork-end view shows left and right at the chassis corners. **PASS** |
| 2 | Datasheet-faithful scans | live `LaserScan` | 275 rays, 275°, 10 Hz, 8.0 m | all three: **275 rays, 275.0°, range max 8.0 m**. Fan outlines follow the real rack geometry. **PASS** |
| 3 | Fields visible | scan plot in vehicle coordinates | three fans, blind sectors into the vehicle | `assets/m5-step2-sensors/step2-scan-fans-2026-08-12.png`. See §2 on why this and not a GUI capture. **PASS** |
| 4 | Levels transition | monitoring case changed under a parked truck | thresholds move, levels follow | case 3 (PF 4.5) → all three **PROTECTIVE**; case 1 (PF 1.0) → all three **WARNING**. Distances unchanged at back 1.75 m, left 1.21 m, right 1.29 m — only the thresholds moved. **PASS** |
| 5 | Back scanner drives the PLC | obstacle into the protective field | `Motor` drops | see the transition table below. **PASS** |

## Step 5, in full

`step2.py`'s status line, one run, its own clock:

```
 1.435  E-Stop=True  Motor=False PF=False WF=False case=1     no sensor data yet
 6.104  E-Stop=True  Motor=False PF=True  WF=False case=1     link live, field clear
 6.327  E-Stop=True  Motor=True  PF=True  WF=False case=1     'a' -> Motor ON
28.168  E-Stop=True  Motor=False PF=False WF=False case=1     intruder in the field
51.018  E-Stop=True  Motor=False PF=False WF=False case=1     still latched at quit
```

A 0.35 × 0.60 × 0.90 m box was spawned 0.65 m behind the back scanner at
t ≈ 28 s. `PF_OSSD` and `Motor` fell in the **same sample**. `Motor` did not
recover when the field stayed occupied — the ESTOP1 latch, the same one the
e-stop button demonstrated in Step 1.

Field report with the intruder in place:

```json
{"case": 3, "pf_th": 4.5, "wf_th": 6.0,
 "back":  {"pf": false, "wf": false, "d": 0.475, "level": "PROTECTIVE"},
 "left":  {"pf": false, "wf": false, "d": 1.212, "level": "PROTECTIVE"},
 "right": {"pf": false, "wf": false, "d": 1.290, "level": "PROTECTIVE"}}
```

`d = 0.475` is the box: 0.65 m to its centre, 0.175 m of half-depth, and the
scanner's own mount offset.

**`case=1` came from the PLC.** Step 1 left `CASE_B0`/`CASE_B1` unconsumed;
`step2.py` now decodes them and `field_eval` picks its `(PF, WF)` pair from
the result. With PF 1.0 m the parked truck at 1.75 m is clear, which is why
`a` could enable `Motor` at all.

## 1. The one real defect found, and how

All three devices held `PROTECTIVE` on a clear aisle, reading 0.11–0.12 m —
the range minimum. Measured rather than guessed, taking every ray under 1.2 m
on the spawn pose:

| Device | Self-return sector | What it is |
|---|---|---|
| back | idx 0–2 and 272–274 (±135.5° to ±137.5°) | the drive wheel, at the fan's edges |
| left | idx 7–65 (−130.5° to −72.3°) | the mast and carriage, inboard-forward |
| right | idx 209–267 (+72.3° to +130.5°) | the exact mirror of left |

This is not a modelling error. The owner's reference drawing shows the left
and right fans notched where the body blocks them, and a real microScan3 has
the same geometry — it does not have the problem because its configured field
is a **contour** shaped around the vehicle. Step 2 evaluates a radius (design
§4.1), so the equivalent is done in the evaluator: `SELF_MUTE` blanks the
sectors that are structure rather than surroundings, which is what an
integrator does when muting a sector at commissioning.

**The cost, stated:** an obstacle inside a muted sector is invisible to that
device. The sectors point at the vehicle's own structure so nothing can reach
them, but this is the one place in Step 2 where a real object could be
ignored, and it is why they are listed explicitly rather than derived at
runtime from whatever happens to look close.

## 2. Why the evidence is data and not a GUI screenshot

The Gazebo GUI's 3D viewport does not render reliably under WSLg on this
machine, and `/gui/screenshot` returns success while writing no file. Time
was lost to it. The method that works, and the one every later step should
use:

- spawn a camera model into the running world and read its image topic, or
- plot the scan data directly.

Both are deterministic and neither depends on a window being mapped or
focused. `<visualize>true</visualize>` is set on all three sensors, so the
rays do appear in the GUI for a human sitting at the machine — that is a
convenience, not the evidence.

## 3. State left behind

- `intruder` model still in the world; remove it with
  `gz service -s /world/warehouse/remove --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --req 'name: "intruder", type: MODEL'`
- `PLC_2` in RUN, **tripped fail-safe**: `step2.py` exited through `q`, writing
  `E-Stop`, `PF_OSSD` and `WF_Clear` False. The next run needs one `a`.
- 81 tests passing (`python3 -m pytest m5_ver2/step2/tests/ -q`).

## 4. Not done

- Left and right scanners do not reach the PLC. The F-PLC has one sensor input
  configured; they are HMI-only, which is the owner's constraint.
- The HMI's three lamps were verified from `/forklift/safety/fields`, which is
  the value they render, rather than from a photograph of the window.
- Step 1's whole-branch review is still deferred, with ~35 minors in its ledger.
