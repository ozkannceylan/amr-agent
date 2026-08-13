# Report m5-04b — the rear scanner's self-occlusion band

```
brief:               docs/briefs/m5-04b-rear-scanner-self-occlusion.md
status:              done
files_changed:       agv/forklift/EVIDENCE_SENSOR_COVERAGE.md
                     agv/forklift/scripts/sensor_coverage.py
                     agv/forklift/README.md
                     docs/reports/m5-04b-rear-scanner-self-occlusion.md
                     (agv/forklift/model.sdf is deliberately UNCHANGED)
invariants_touched:  none
open_questions:      five, below
next_suggested:      m5-12 draws the rear protective field bounded inside the
                     R8 self-return contour, travel-dependent per §13.8
```

## The verdict, first

**(c) — an accepted residual, measured and mitigated. R8 is now in the
evidence in the same voice as R1–R7. No pose, yaw or aperture change is
warranted, and `model.sdf` was not touched.**

## What the band is

Measured live, headless, Gazebo 8.11.0, `GZ_PARTITION=m504b_selfocc` and
`ROS_DOMAIN_ID=91`, on the committed model, read on the gz side because the
rear measurement channel has no ROS name and no consumer.

| | |
|---|---|
| Sector | sensor frame **−131.5° to −72.3°**, indices 6–65 of 275; vehicle bearings **93.5° to 152.7°** |
| Size | 60 rays computed, 61 measured; **21.8 % of the aperture** |
| Surfaces | `mast/mast_rail_left` (1 ray), `carriage/visual` (44), `mast/mast_rail_right` (15) |
| Distances | **0.090 to 0.780 m**; 11 rays fall inside the 0.10 m `range_min` and report `inf` |
| Arithmetic of the finding | 57 rays under 0.5 m, minus the 11 out of range, = **46 of 93 finite**, m5-07's figure reproduced to the ray |

Ray-by-ray agreement with the prediction from `model.sdf`: mean 0.0017 m,
maximum 0.0133 m, 47 of 49 within 0.010 m. One extra measured ray (index 5,
0.780 m) grazes a mast-rail corner that an idealised line misses.

Body-fixed proof: the vehicle was moved 9.2 m and rotated 60° and re-measured —
**identical index set, maximum difference 0.000004 m**, while the world returns
around it changed from 43 to 34.

Against carriage travel, from the device's own side: 50 reported at rest,
**82 reported and out to 1.022 m inside the R2 window (0.0738 m of travel)**,
48 reported with the carriage clear of the plane. The mast rails never leave —
they span z 0.05–2.05 and lift with nothing.

## Reconciliation with R1 and R2

**Same geometry, different measure, and that is the whole of the magnitude
difference.** R1 is a *union* residual: 5.0° at 2 m that neither scanner
reaches. R8 is a *single-device* statistic. The sight line producing R1 at
origin-bearing 172° leaves the rear mount at sensor bearing ≈150°, which is
index 63 of the measured band — R1 is the sliver of the band the front scanner
also cannot reach. R2 likewise: §6 measured the tines as a union gap widening
5.0° → 20.2°, §13.5 measures the same event as 22 extra rays and a far edge
moving 0.780 → 1.022 m.

**The geometric analysis did not miss it; it did not name it.** §4 already
printed the rear scanner's own coverage (146.1/181.9/192.6° at 1/2/3 m against
a 274.9° aperture) and this band is the loss inside those numbers. What was
missing was a residual stated **per device** rather than per pair.

## Why no mount change is warranted

The blind sector is one contiguous 85° arc. The vehicle subtends **129.75°**
from the rear mount, in three groups, so at least 44.75° of vehicle is inside
the aperture at any yaw — the yaw only chooses *which* group. A rear-only yaw
sweep over ±90° (new `--self-return` mode) shows the best candidate, δ = +65°,
removes six rays and pays for them: the far edge moves **out** 0.706 → 0.823 m,
the raised-carriage case worsens 47 → 53 rays (and raised is the normal
travelling posture), and the load half's double coverage at 2 m goes to zero.
δ = 0 is the only row that keeps any. Union coverage, the R1 gap and the
0.30/0.50 m perimeter figures are flat from −10° to +65°, so **the band costs
no coverage** — the front scanner covers that sector, and the 0.50 m offset
perimeter stays 100 %.

The scan plane cannot escape it either: §1 pins it inside 0.100–0.200 m, and
the carriage (from z 0.100) and the mast rails (from z 0.050) cross every
height in that window.

**No software filter was written and none exists in this directory.** The
mitigation is field geometry configured on the device, which is m5-12's, not a
node discarding samples.

## Coverage was NOT re-measured, and did not need to be

No pose, yaw or aperture changed, so §4–§9 are untouched and their figures
stand as computed. The yaw sweep in §13.7 re-computes union coverage and the
perimeter for **hypothetical** rear yaws only, to price the alternative that
was rejected. `check_sensor_frames.py` still passes, 19 checks, 0 failing.

## Also observed, in passing

* **R7 is now a measured fact.** The navigation lidar reports the mast as two
  4-ray lobes at 1.287–1.483 m — the `<visual>` rails, not the 0.72 m
  `<collision>` body. Simulated shadow 8.75°, vehicle 29.0°.
* **The front scanner spends 1 ray of 275 on the vehicle**, at 1.084 m, at the
  aperture edge. Same mounting rule, 60× the difference, because the vehicle is
  symmetric in plan and **asymmetric at the scan plane**: nothing crosses
  z = 0.150 at the drive end except the wheel and yoke, which sit inside that
  scanner's blind sector.
* Part of §12 item 2 is discharged: all three sensors advertise, publish and
  carry their link name in `frame_id`.

## What m5-12 inherits

1. The rear device's fields must be bounded **inside** the self-return contour
   over sensor frame −131.5° to −72.3°. Past 0.090 m there, a field is
   permanently violated.
2. That bound is **travel-dependent**: 0.780 m at rest, **1.022 m** between
   0.05 and 0.10 m of travel, 0.780 m above it. A lift-switched field must not
   treat the R2 window as equivalent to travel zero.
3. No coverage is owed there — the pair covers the sector.
4. The band is a candidate **reference contour** for mount-integrity
   monitoring, a real feature of this device class. Named as available, not as
   implemented.

## Open questions

1. **The brief names the topic `/forklift/gz/scan_safety_rear`**, which m5-06
   renamed to `/forklift/gz/safety_scanner_rear/measurement`. Read as the
   latter, per `config.yaml`. `sim/setup/CONTAINER_TOOLCHAIN.md` already carries
   the same correction; no further action taken.
2. **Should the rear measurement channel gain a ROS name?** It still has no
   consumer and was left unbridged, correctly. Everything in this brief was read
   on the gz side. If m5-12's field evaluation runs as a ROS node, that decision
   arrives with it, and the channel-naming rule in `config.yaml` already fixes
   the name it would take.
3. **`model.sdf` carries no pointer to R8.** A one-line comment beside the rear
   scanner would help the next reader, but the brief limits model edits to a
   pose or aperture correction, so none was made. Request: permission for a
   comment-only edit, or leave the cross-reference in the README and evidence.
4. **The R2 window is the worst case for this device and is reachable by a
   normal lift command.** Nothing currently prevents parking the carriage in
   0.05–0.10 m of travel. Whether the vehicle node should refuse to *rest*
   there is a process-layer question and belongs to whoever owns fork motion
   policy, not to a coverage document.
5. **R7 remains unreconciled.** The measurement confirms the divergence rather
   than resolving it: the mast's `<visual>` and `<collision>` representations
   still disagree by 20°, and the choice of which to correct is still open from
   the m5-04 report.

## Discipline notes

Headless throughout, no GUI, both transports isolated, one server session, four
captures, three messages each and identical to 1e−6 m. The one real-time factor
line recorded (0.99984) exists only to show the sensors were rendering at the
world's step rate — **this brief's measurement is geometric and return-based,
not a performance measurement**, and nothing in it should be read as one. No
dependency added; the script remains Python standard library only. Nothing
committed.
