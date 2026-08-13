# Report m4f-01 — forklift commissioning node group

brief:               docs/briefs/m4f-01-forklift-node-group.md
status:              done
files_changed:       docs/interfaces/opcua-nodes.md (new §10, plus five scope
                     reconciliations inside §2.1, §9.1, §9.7 and §9.8 — see below);
                     docs/reports/m4f-01-forklift-node-group.md (this file)
invariants_touched:  none. Invariant 4 holds for both clients (PLC server, bridge and
                     HMI clients); invariant 6's discipline is kept by making every
                     HMI-written node a request and every actuator setpoint PLC-formed;
                     invariant 10 is satisfied per tag in §10.3; invariant 11 is
                     untouched because the forklift is plant, not a fleet vehicle
                     (ADR 0008 D5). ADR 0008 supplies the HMI-layer decision; no ADR
                     proposal is raised.
open_questions:      six, listed under "Open questions" below (they are §10.12 of the
                     document, restated for the orchestrator)
next_suggested:      A bridge-design.md brief extending §3, §4 and startup rule R3 to
                     the forklift signal set, before any bridge work on this gate.

---

## What landed

`docs/interfaces/opcua-nodes.md` §10, "Forklift commissioning nodes (M4)", in twelve
subsections: direction rules for two clients on one server; the server-interface ruling
with its TIA click path; folder/DB layout with per-tag rights; the four node groups; the
HMI watchdog; start values; the ROS 2 topic map; a deliberately-absent table; and open
items.

**18 nodes** — 5 `Forklift/Hmi/`, 4 `Forklift/Input/`, 3 `Forklift/Output/`,
4 `Forklift/Status/`, 2 `Forklift/Link/`. Every node carries BrowseName, DB home, S7 and
OPC UA type, unit, engineering range and plausibility window where it has one, exactly
one writer, its readers, and per-tag *Accessible* / *Writable from HMI/OPC UA* flags.
Value types are Real, Bool and UInt16 only.

**Server-interface ruling: extend `DemoCell`, do not create a second interface** (§10.2).
The name and the derived URI `http://DemoCell` are unchanged, which is what makes it
safe: adding folders and tags does not touch the interface name, so ADR 0006's derived
URI does not move and every existing browse path keeps working. The honest consequence is
stated in the document — `DemoCell` is now an identifier, not a description. The click
path follows the SPEC §4.2–§4.3 pattern, including reading the derived URI back rather
than entering it, and §10.2 records that **if** a later gate creates a second interface,
its name is a contract decision taken in a document and never in the tool. Every value in
§10 is marked a design value until read back out of TIA.

**HMI watchdog** (§10.8): `HmiHeartbeat` UInt16, all six HMI nodes written every cycle
(never on change, so a CPU restart cannot leave a stale HMI level), heartbeat written
last, inequality comparison only. `HmiLinkOk := HmiSeenAlive AND NOT HmiStaleTimer.Q` —
**FALSE from the first scan until the heartbeat has been seen to change**, with the
"not yet proven stale is not alive" reasoning spelled out. Stale window is the named
constant `HMI_STALE_TIME = T#600ms`, stated as the rule (three worst-case write periods)
rather than as a number, and deliberately not shared with `HEARTBEAT_STALE_TIME`. The
reset edge is armed **per link session**, which is the relocated form of the M3 defect.

## Deviations from the brief's starting table

| # | Starting table | Delivered | Why |
|---|---|---|---|
| 1 | `HmiDriveCommand`, `HmiSteerCommand`, `HmiForkCommand`, `HmiTeleopEnable` | `HmiTractionRequest`, `HmiSteerRequest`, `HmiForkRequest`, `HmiTeleopRequest` | This model reserves *Command* for the PLC-owned actuator output (`ConveyorSpeedCommand`) and uses *Request* for every client-written intent node (`TransferRequest`, `PassageRequest`, `ChargeRequest`, and the starting table's own `HmiResetRequest`). ADR 0008 D2.2 calls them requests in words. *Traction* rather than *Drive* because "drive" is ambiguous, and it pairs each request with the output it feeds: `HmiTractionRequest` → `ForkliftTractionSpeedRef` |
| 2 | `ForkliftObstacleMinDistance` plausibility `0.0…8.0` | `0.05 … 8.10` | `0.0` is the vehicle layer's no-data sentinel. A window whose bound *is* the sentinel makes its rejection an accident of strict-versus-loose inequality, and a window that included it would read "obstacle at 0 m" as a plausible measurement. Widening puts the sensor's real endpoints (0.10, 8.00) strictly inside and leaves the sentinel strictly outside, so it reads as a sensor fault by construction — the `BELT_POSITION_MIN/MAX` reasoning of SPEC §3.3 |
| 3 | Engineering ranges only on the three HMI Reals | Ranges **plus** plausibility windows ±1.05, ±1.35, ±1.05 | An analogue is tested against a window before use, affirmatively, with the fault in the `ELSE`; outside the window is a fault, not a value to clamp (LESSONS 2026-07-27). The window exceeds the engineering range by the `float64 → Real` narrowing margin so a legitimate ±1.0 never faults |
| 4 | 17 nodes | **18** — added `Forklift/Link/HmiLinkOk` (Bool, PLC-written) | The starting table names the HMI heartbeat but no verdict node. The done_when's boot-polarity requirement is a statement *about a verdict*, and without the node the operator cannot see what the PLC concluded. Mirrors `BridgeLinkOk` exactly, and the bridge's own link verdict is **not** duplicated for the forklift subtree |
| 5 | (unspecified) DB layout | Five **new** DBs, M3 DBs untouched | Adding members to `DemoCellInput` and siblings moves offsets that current evidence and watch tables depend on; a stale build then shows monitoring errors on exactly those rows (LESSONS 2026-07-28). Separate DBs leave the M3 cell byte-identical |
| 6 | HMI heartbeat "≥5 Hz" | 10 Hz nominal, 5 Hz contractual floor, `HMI_STALE_TIME = T#600ms` | A stale window needs a period to be derived from. The floor is kept as the contract; the constant is derived as 3× the floor's 200 ms and is re-derived from measurement if commissioning is worse |
| 7 | `ForkliftObstacleInStopZone` (`TRUE` also on invalid/stale scan) | **Kept verbatim**, with the polarity conflict written out | This is the one input whose `TRUE` is the non-permissive state, inverting §9.3's contact convention. It is not renamed because a permissive-polarity node would force the *bridge* to invert, which `bridge-design.md` §1.1 forbids. Fail-safety is carried instead by the vehicle layer's fail-to-TRUE, a `TRUE` DB start value, and the `BridgeLinkOk` qualification — and §10.5 states that renaming it later means moving the ROS topic's polarity in the same change |

Nothing was added beyond deviation 4. Where the gate looked short of a node — a traction
drive-fault verdict — it is raised as open question 2 rather than invented.

## Reconciliations inside `opcua-nodes.md`, outside §10

Required, not optional: without them the same file would contradict itself, which is the
failure mode LESSONS 2026-07-26 records. Each is a scope qualifier, no claim is weakened:

1. **§2.1 browse tree** gains the `Forklift/` line.
2. **§9.1** "nothing else *on the `DemoCell` interface* is client-writable" → "nothing
   else *in the §9 node set*".
3. **§9.7** `BridgeHeartbeat` "the sole node outside `DemoCell/Input/` the bridge may
   write" → "the sole **non-input** node", with the M4 set named. Found by independent
   whitespace-normalised search, not by the brief's list.
4. **§9.8** scope sentence, the 15-node count, the node-count row, the two table headers
   and the "deliberately absent" row → scoped to the §9 node set.
5. **§9.8's client-writable-command row** → scoped to the conveyor command path, where it
   still holds, with an explicit pointer to §10.4 as the group ADR 0008 D2 admits. §10.4
   states the same from the other side and names the per-tag *Writable* flag as the
   enforcement point. This closes the contradiction the coordinator raised.

## Open questions

1. **`bridge-design.md` is M3-scope** and does not describe the forklift path: its §3
   writable set, §4 signal map, §4.6 QoS table and startup rule **R3** all need the
   forklift signal set. R3 in particular must become "every input in the *configured*
   signal set" — as written ("all seven") a forklift-only run would stall the heartbeat
   waiting for conveyor topics. Not editable within this brief's deliverable.
2. **No `ForkliftDriveFault` node.** Case D of `bridge-design.md` §7.3 (plant stopped,
   bridge alive, input image looks live) applies to this plant unchanged, and it now has
   no PLC-visible verdict. One status node would carry it; the detection is PLC content.
   Owner decision.
3. **Lidar field ownership.** The sector and stop distance are configured in the vehicle
   layer and reach the PLC as one bit, on the argument that a scanner's field is a device
   configuration and a 181-sample geometry is not reconstructable from a scalar. If the
   owner prefers the PLC to own that threshold, `ForkliftObstacleInStopZone` is deleted
   and the verdict is formed from `ForkliftObstacleMinDistance`: a one-node change here
   plus a polarity change in the vehicle layer.
4. **`plc/demo-cell/SPEC.md` §4.3 says "Nothing else goes into the interface."** True for
   the M3 cell, scope-stale at the interface level now that §10 exists on the same
   interface. Requested of the `plc` agent — I cannot edit `plc/`. (`bridge/README.md`
   and `bridge/EVIDENCE_LIFECYCLE.md` say "the only node outside `Input/`", which stays
   defensible under the revised §9.7 wording, but a bridge brief should confirm it.)
5. **`TRACTION_SPEED_MAX` and `FORK_SPEED_MAX`** are PLC constants this document does not
   set. The interface constraint recorded is that `ForkliftLinearSpeed`'s plausibility
   window stays at least twice the traction cap; at ±2.00 m/s that bounds the cap at
   1.00 m/s, and raising the cap re-derives the window.
6. **Everything in §10 is a design value until read back out of TIA** (§10.2 step 6): the
   folder tree, the per-tag rights, the node count and the browse path. No gate criterion
   may rest on them before that verification, per the ADR 0006 discipline.
