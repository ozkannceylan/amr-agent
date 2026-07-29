# Report m4f-04 — PLC forklift teleop program specification

```
brief:               docs/briefs/m4f-04-plc-forklift-spec.md
status:              done
files_changed:       [plc/forklift/SPEC.md, docs/reports/m4f-04-plc-forklift-spec.md]
invariants_touched:  none
open_questions:      see below, 4 needing an owner or interface ruling
next_suggested:      m4f-05 (bridge-design forklift path); the interface
                     corrections below are small enough to ride with it
```

`plc/forklift/SPEC.md` specifies `FB_ForkliftTeleop` in the demo-cell §1–§12
structure. §7's SCL sketch is symbol-closed — every `#identifier` resolves to a
declared Temp, Static or constant, no declared item is unused, all 25 constants
are in §3.3, and all four timers are called unconditionally at top level with
`PT` explicit at the call site. §9 defines the watch table `Forklift M4 gate` in
five groups, §10 gives the TIA click path including the extend-`DemoCell` ruling
and the solid-green check, §11 is a T5.1–T5.6 procedure of 43 steps whose six
pass counts each derive from their own table, and §12 lists what is deliberately
not specified plus ten open items.

## Where the brief's starting table and `opcua-nodes.md` §10 disagreed

§10 won in every case. The five the orchestrator flagged, confirmed:

| # | Brief | §10, implemented |
|---|---|---|
| 1 | `HmiDriveCommand`, `HmiSteerCommand`, `HmiForkCommand`, `HmiTeleopEnable` | `HmiTractionRequest`, `HmiSteerRequest`, `HmiForkRequest`, `HmiTeleopRequest` (§10.4) |
| 2 | 17 nodes | **18** — `Link/HmiLinkOk` is a PLC-owned verdict node, so this FB writes it (§10.3) |
| 3 | `HMI_STALE_WINDOW := T#500MS` | `HMI_STALE_TIME` = **`T#600ms`**, and never shared with `HEARTBEAT_STALE_TIME` (P3, P4) |
| 4 | reset edge, no arming rule | reset edge **armed per HMI link session** (P6) — tested at 5.5.5 by ending a session, not by restarting the CPU |
| 5 | — | HMI writes all six of its nodes **every cycle**, not on change (§10.4, H1), so the M3 write-cache hole (`demo-cell/SPEC.md` §12 item 7) does not exist on the `Hmi` group. It still does on the `Input` group |

Five more the brief did not anticipate:

| # | Brief | §10, implemented |
|---|---|---|
| 6 | `TRACTION_SPEED_MAX` = 1.50 m/s | **1.00 m/s.** §10.12 item 4 requires `ForkliftLinearSpeed`'s plausibility window to stay at least twice the cap; the window is ±2.00 m/s, which bounds the cap at 1.00. The vehicle layer's own clamp is 1.50 m/s, so the PLC never asks for a speed that clamp would touch — the right relationship, but the brief's number was unbuildable without an interface change first |
| 7 | instance DB `ForkliftTeleop_DB` | **`ForkliftControl_DB`** — tabulated with its access rights in §10.3. The FB keeps the brief's name (ADR 0008 D3 leaves it to this layer), so the pair does not match the way `FB_DemoCellControl`/`DemoCellControl_DB` does. Harmless: the DB is *Accessible* ✘, so no client sees it |
| 8 | `TeleopActive := enable AND both links` | §10.7 adds **"no latch standing"**, and §10.7's `ForkliftResetRequired` ("pending before teleop may be **enabled** again") plus P5 ("a returning heartbeat never by itself restores teleop") require it to be **edge-set**, not a pure level. It is this cell's cycle-running flag |
| 9 | `ForkliftResetRequired` mirrors `ObstacleStopLatch` | §10.7 and P5: it mirrors **any** latch — obstacle, either link loss, plant-input fault, request fault |
| 10 | steer "returns to center when not permissive" | See the contradiction below |

## Open questions

**1. `opcua-nodes.md` §10.6 contradicts itself on the steer setpoint, and one of
the two statements has to go.** Its `ForkliftSteerAngleRef` table row says
"Steering is **not** gated to zero on a stop: a steer setpoint is a position, and
forcing it to centre would move the wheel of a machine that is supposed to be
stopping". The paragraph immediately below it says "each of the three setpoints
is assigned in exactly one statement … with the interlock-failed branch driving
it to `0.0`". §10.8 P5 says "every **motion** setpoint", which is careful enough
to be read either way.

I implemented **zero**, on three grounds: it is what the gating paragraph and ADR
0008 D2.3 require in the words they use; a hold needs a static carrying an
operator demand across a stop, which is the stale state CLAUDE.md §9 tells the
machine to re-read rather than resume from; and one uniform rule across three
outputs is what survives being read in a hurry. The consequence — **the steered
wheel returns to centre while the machine stops** — is stated in §6.4, in the
Group 3 watch-table row and in step 5.1.8, so it cannot surprise the recording.
If the owner rules the other way it is one branch, spelled out in §6.4 and in a
§7 comment. **Requested of `docs/interfaces/`: delete or reword one of the two.**

**2. There is no start device, so `HmiTeleopRequest` carries two jobs.** The M3
cell has a reset button *and* a separate start button; §10.4 defines five HMI
requests and none is a start. Following the LESSONS 2026-07-27 rule for exactly
this situation, I implemented the behaviour on the existing device and wrote the
conflation out: after a reset the operator must **release and re-assert the
enable**, because an enable left asserted through the reset produces no edge.
That satisfies CLAUDE.md §9 and is demonstrated at 5.4.8/5.4.9. **Requested of
`docs/interfaces/`: an `HmiStartRequest` node** would restore the two-device
separation. Not invented here.

**3. No `ForkliftDriveFault` node, so case D has no verdict on this plant.**
`ForkliftLinearSpeed` is read and qualified but feeds nothing — a frozen input
image under a live bridge is undetectable here, and §10.11/§10.12 item 3 declined
to invent the node. Recorded as §8 case P and §12 item 3 rather than papered
over. Owner decision, then a revision of this document.

**4. `plc/README.md` needs one row and one sentence** — a `forklift/SPEC.md`
entry in its Contents table, and a statement that the obstacle stop, the speed
cap and the soft limits are process interlocks implementing no safety function.
Inside my write scope but outside this brief's deliverable, so not done.

Two smaller ones, both recorded in §12 rather than raised here: the plausibility
latches are unverifiable on this plant for the same reason the M3 cell's are (no
way to inject a `NaN` or hold an out-of-window value), and OB30 now carries two
FBs, so its cycle time wants measuring after the download.

## Notes

- **Every Real is swept, none exempted** — three operator requests and three
  plant values, each with an affirmative `(LOW < x) AND (x < HIGH)` window and
  the fault in the `ELSE`. The window and the clamp are kept as separate
  decisions: inside the window but outside the engineering range is a `float64 →
  Real` narrowing artefact and is clamped; outside the window is a broken client
  and is a fault.
- **`ForkliftObstacleMinDistance` is tested for transducer health and never
  thresholded.** No comparison of it against a stop distance appears anywhere in
  the program — a second "obstacle present" verdict would give one value two
  owners.
- **`BridgeLinkOk` is consumed, never written** (§3.1b). `FB_DemoCellControl`
  stays its only owner, and `FB_ForkliftTeleop` is called after it in OB30 so the
  verdict read is from the same scan.
- Nothing in `plc/demo-cell/SPEC.md` was edited, and no M3 DB is extended — the
  five forklift DBs are new, so the M3 cell stays byte-identical and its evidence
  reproducible.
