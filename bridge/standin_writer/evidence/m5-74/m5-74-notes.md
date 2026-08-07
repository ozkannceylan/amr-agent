# m5-74 — the bench panel against the live CPU, 2026-08-07

**Nothing here claims or implies an achieved Performance Level, Category, SIL
or PFH.** The writer and its panel are engineering stand-ins for wiring.

## Environment

| | |
|---|---|
| CPU | PLCSIM Advanced instance `safecell3`, `OperatingState = Run`, API 7.0, on the Windows host |
| Writer | `bridge/standin_writer/standin_writer.ps1`, unchanged by this brief. Two sessions: `pid35904` (12:58:58Z) and `pid35800` (13:15:11Z) |
| Panel | `bridge/standin_writer/bench_panel.ps1`, Windows PowerShell 5.1 + WinForms |
| Independent witness | `testing/opcua_witness.py` over **OPC UA** to the CPU's own server — a different protocol stack from the API the writer uses, and one that cannot see `SafetyInputStandIn` at all. It reads the four `ForkliftSafetyMirror` values the standard program copies out of the F-block |
| Vehicle stack | up until 13:04:43Z (field link and speed source both connected), down after |

Timestamps in the writer log are **UTC**; the witness prints **local (UTC+2)**.

## Files

| File | What it is |
|---|---|
| `m5-74-panel-boot-estop-open-links-up-20260807T1300Z.png` | the panel at writer start with the vehicle stack up: **E-STOP CIRCUIT OPEN** at boot, the zone control **disabled** because a field link owns the channel, and the read-only column moving on its own — both freshness sequences advancing, speeds changing, warning field occupied |
| `m5-74-panel-estop-closed-from-panel-20260807T1300Z.png` | after one press on the panel: **CLOSED**, with the writer's own two log lines shown verbatim in the panel's log pane |
| `m5-74-panel-reset-hold-2013ms-running-20260807T1301Z.png` | a hold in progress — `PRESSED — held at the CPU`, **2 013 ms** counting up, the marker inside the drawn 200–3000 ms band |
| `m5-74-panel-links-down-sequences-frozen-20260807T1316Z.png` | the vehicle stack down: both sequences **frozen — read as MISSING**, speed link down, and the zone control **live again** because the channel has returned to the operator |
| `m5-74-writer-log-excerpt-20260807.log` | every `START`/`OPERATOR`/`REFUSED`/`FIELD`/`LINK`/`SPEEDLINK`/`MEMBERS`/`API` line of both sessions. The full logs are run artefacts and are not committed |
| `m5-74-opcua-witness-20260807.log` | witness, 14:58:42–15:08 local, 718 729 polls over 600 s |
| `m5-74-opcua-witness-20260807T1316Z.log` | witness, 15:15:31–15:20 local |

## What was observed

**A panel press is a writer command, in the writer's own words.** Every
`OPERATOR` line in the excerpt was produced by a press on the panel. The
writer logs the provenance and then the identical sentence a typed command
produces:

    13:00:05.614Z | OPERATOR | command file: estop close
    13:00:05.633Z | OPERATOR | estop close -> EStopCircuitClosed := True

**The zone channel changes owner both ways, and the panel follows it.** With
the field evaluation connected (12:59:00.174Z) the zone control is disabled and
labelled; when the link closed (13:04:43.900Z) the writer returned ownership to
the operator and the control became live again. Both states are in the
screenshots above.

**The read-only channels were never drivable and were seen moving on their
own.** With the speed source up, `SpeedSeqA`/`SpeedSeqB` advanced every cycle
and the panel showed *advancing*; with it down they froze and the panel showed
*frozen — the F-program reads this as MISSING*. The panel has no control for
either reading, for the motion observation or for the warning field.

**The reset is a hold, and the F-program judges it — measured.** Three holds
longer than the F-program's window were made at the panel. In each, the
independent witness saw `SafetyResetFault` rise **while the button was still
down** and fall again after the release:

| press (UTC) | fault rises (local) | press → fault | release (UTC) | fault clears |
|---|---|---|---|---|
| 13:16:23.790 | 15:16:26.961 | **3.171 s** | 13:16:27.144 | 0.132 s after release |
| 13:16:57.297 | 15:17:00.522 | **3.225 s** | 13:17:00.800 | 0.140 s after release |
| 13:17:02.152 | 15:17:05.311 | **3.159 s** | 13:17:07.390 | 0.122 s after release |

That is **n = 3**, 3.159–3.225 s from the operator's press at the panel to the
fault in the consumer's view — the 3000 ms upper end of the window plus the
panel → command file → 50 ms writer cycle → F-cycle path. It is an **observed
range, not a bound**: three holds by one operator on one machine. It does
confirm that the ceiling the panel draws at 3000 ms is the ceiling in force,
and that the program, not the panel, is what refuses a long hold.

## What was NOT demonstrated, and why

**An accepted reset — one that clears the latched demands — was not achieved
in this session.** Two attempts were made with a cause still standing and both
were correctly refused:

- 13:01:12–13:01:14 (2.2 s hold) with the **zone circuit open**: the field
  evaluation was reporting `ZONE 0`, so the demand's cause stood;
- 13:15:53–13:15:55 (2.0 s hold) with **both circuits closed but no speed
  source**: both freshness sequences were frozen, and a missing reading is
  itself a standing demand (SPEC §11.2/§11.5).

The witness shows `EStopDemand` and `ZoneStopDemand` staying `1` across both.
**Clearing them needs the vehicle stack up**, which the owner took down mid-run
and brings up themselves. Nothing on the panel's side is untested by this: the
press edge, the measured hold, the release edge and the program's judgement of
the hold were all observed end to end.
