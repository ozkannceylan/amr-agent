# m5-44 — the bridge repoint, and the envelope across the real seam

    brief:               m5-44 (issued in-session; no file in docs/briefs/)
    status:              done — both stages ran against the live CPU. A
                         PLC-formed envelope crossed the committed bridge to
                         the vehicle's gate, held and released the vehicle, and
                         the link-loss direction was observed too. One
                         interface deliverable is a REQUEST, not a blocker to
                         what was run: bridge-design.md does not yet carry the
                         §12 group (opcua-nodes.md §12.13 item 1).
    files_changed:
      - bridge/config/bridge.yaml                     (repointed: cell group replaced by forklift + envelope)
      - bridge/amr_bridge/config.py                   (UINT16 kind; per-slot write cadence; the envelope group definition)
      - bridge/amr_bridge/opcua_side.py               (typed writes/reads by kind; cyclic vs on-change by cadence, not by type)
      - bridge/amr_bridge/ros_side.py                 (UInt16 subscriber and typed publishers)
      - bridge/tools/probe_server_paths.py            (new — read-only server probe, advertised vs addressable)
      - bridge/tools/observe_envelope_chain.py        (new — subscriber-only vehicle-side witness)
      - bridge/EVIDENCE_ENVELOPE_BRIDGE.md            (new — the capture, written as each observation landed)
      - bridge/evidence/                              (new — 2 bridge CSVs, 4 witness CSVs, 8 run logs, all gzipped after their writers had exited)
      - docs/reports/m5-44-bridge-forklift-repoint.md
    invariants_touched:  none. Nothing was added to the bridge that decides
                         anything: no threshold, no latch, no interlock, no
                         timer over a plant signal. The two new cadence
                         constants are transcriptions of the node model's own
                         cadence column, per signal. No velocity, speed value
                         or motion command crosses the OPC UA seam in either
                         direction (ADR 0014): the envelope is enable, ceiling
                         and permit, and the loop closed onboard throughout.
    open_questions:      below
    next_suggested:      the interface round for opcua-nodes.md §12.13 item 1 —
                         bridge-design.md must carry the envelope group before
                         the next brief builds on it

---

## What was proven

**Stage 1, the deferred repoint.** `bridge/config/bridge.yaml` — the committed
gate config, not a hand-edited copy — resolved 13 nodes on the live CPU, matched
every DataType, satisfied R3 on the four forklift inputs and ran 352 s. Witnessed
from a second process on the Windows host: the bridge's heartbeat advancing and
`ForkliftObstacleMinDistance` reading `5.1458` m from the warehouse world.

**Stage 2, the envelope.** With the §12 group added: 20 nodes, R3 counting six,
a 7-key allowlist, 947 s in one session with no reconnect. Then, formed entirely
in the standard program and carried unchanged:

* `mode_in_force 0→2`, `motion_enable 0→1`, `speed_ceiling 0.0→0.600` arrived on
  the vehicle **within 1.8 ms of each other**; the gate adopted the law 44.5 ms
  later and the bridge carried that readback **back** to the CPU, where
  `ForkliftVehicleModeApplied` read `2`. ADR 0014 D5.3's round trip, closed for
  the first time.
* The vehicle drove. Then its own protective field tripped, and the PLC — not
  the bridge, not the vehicle — withdrew the envelope: **41.6 ms** from the
  bridge's write of the field bit being acknowledged to the bridge reading
  `ForkliftMotionEnable` `FALSE`. On the vehicle, `/cmd_vel_gated` reached exactly
  zero **162.5 ms** later and the vehicle was at standstill at **+221.3 ms**.
* The operator's process stop then withdrew `equipment_permit` for a **different
  cause** on the same six slots, and nothing resumed by itself: with the field
  clear the latch stood, and recovery took reset **plus** leaving and re-selecting
  the mode, exactly as CLAUDE.md §9 and §12.3 require.
* **The failure direction.** `SIGTERM` to the bridge with a *permissive* envelope
  frozen on the wire: the gate closed on `envelope stale` **519.7 ms** after the
  signal, against its own 0.500 s window, and held an explicit zero. Invariant
  2's degraded mode, observed rather than asserted.

Full capture, with what each figure is and is not:
`bridge/EVIDENCE_ENVELOPE_BRIDGE.md`.

## The finding that changed the shape of the work

**The cell group cannot be carried against this CPU.** The `DemoCell` interface
on project `safe_amr` publishes `Forklift/` and `Link/BridgeHeartbeat` and
nothing else; `Input/ConveyorBeltPosition`, `Output/ConveyorSpeedCommand`,
`Status/CellCycleRunning` and `Link/BridgeLinkOk` each answer `BadNoMatch` when
**addressed directly**, which is the strong form of the claim rather than a
failed browse. So the deferred TODO item is a **replacement**, not an addition,
and the cell group's tables left the file with the group. This is why the brief's
instruction to establish what the server publishes before assuming any path was
the right instruction: the previously committed configuration would have failed
at connect.

## What was NOT done, and why

* **`bridge-design.md` was not edited.** It is `docs/interfaces/` and
  `opcua-nodes.md` §12.13 item 1 assigns that round to the interface agent by
  name. That item also says the design document must carry the group **before**
  bridge work on it. It does not, so the group definition in `config.py` is
  labelled in the code as the bridge's proposal made runnable, and the interface
  ruling may overturn it. See REQUEST 1.
* **Nothing in TIA.** Not opened, not compiled, not downloaded. Every value
  quoted from the CPU was read through a client.
* **The ceiling clamp was not re-established.** The demand never reached the
  ceiling in these runs; it is measured in `agv/forklift/EVIDENCE_ENVELOPE.md` §5
  against a double, and this file does not imply otherwise.

## REQUESTS — files outside `bridge/`

1. **`docs/interfaces/bridge-design.md`, interface agent** — carry the §12 group:
   §2.1's configured signal set (this work took the **third-group** reading, with
   the reasoning in `config.py`, so the forklift group's committed counts stay
   true), §4 signal-map rows in the §4.7–§4.9 shape, §4.6 QoS rows, the writable
   set gaining the two `Forklift/Vehicle/` nodes, and the first topic-carried
   `UInt16`. Add the observed configuration counts: forklift-only 4/3/5, 13 nodes,
   5 allowlist keys; forklift+envelope 6/7/6, 20 nodes, 7 allowlist keys. This is
   `opcua-nodes.md` §12.13 item 1 and it is now the blocking item for the next
   bridge brief.
2. **`docs/interfaces/opcua-nodes.md`, interface agent** — §12.13 item 3 can be
   closed: all nine §12 nodes were read back from outside TIA on 2026-08-06 at
   their documented types, ten `Forklift/` subfolders, no `_1` suffix anywhere.
3. **`docs/TODO.md`, orchestrator** — the deferred "point bridge.yaml at the
   Forklift groups" item is closed by this report, and its premise ("browsing
   nodes the CPU does not publish would error") has become true of the **cell**
   group instead. The "Group 1 + Group 2 running-cell capture" that was deferred
   to the same run is **not** closed: that capture is a screenshot of TIA watch
   tables and is owner work.
4. **`plc/forklift/`, plc agent or owner** — `Link/BridgeLinkOk` exists as
   `#bridgeLinkOk` inside `FB_ForkliftTeleop` but is published on no node of this
   interface, so no client can read the PLC's verdict on the bridge. Not needed
   by the bridge; worth a ruling before an AT cites it.
5. **`agv/forklift/`, agv-ros2 agent** — in run r4, with a steady 0.30 m/s on the
   gate's input and a permissive envelope, `/cmd_vel_gated` alternated 0.30/0.0 at
   about the gate's own cycle while the vehicle stood blocked. Not reproduced in
   r3 under the same command source. Data:
   `bridge/evidence/envelope-chain-2026-08-06-r4-linkloss.csv.gz` from `t ≈ 0.52`.
6. **Owner / outside the repository** — `~/amr-demo-start.sh` regenerates
   `~/amr-live-forklift.yaml` from `bridge/config/rehearsal-forklift.yaml` with the
   endpoint swapped, carrying that file's "this is the rehearsal config, it points
   at the logic double, bridge.yaml stays cell-only" comments over a file that
   points at PLCSIM. All three statements are now false. The launcher should use
   `bridge/config/bridge.yaml` directly.

## open_questions

1. **Third group or an enlarged forklift group?** Taken as a third group and
   defended in `config.py`; it is the interface agent's to rule (REQUEST 1). If
   ruled the other way, the change is one dataclass and the config's two tables —
   but every committed "forklift group = 4/3/5, 13 nodes" figure moves with it.
2. **Does the cell group still have a home?** Its tables are in git history, not
   in the file. If the M3 demonstration is to be re-run on its own project, a
   `bridge-cell.yaml` beside `bridge.yaml` is probably the honest shape, and it is
   a decision rather than a restoration.
3. **`ForkliftVehicleModeApplied` write cadence.** Written on change per §12.6,
   so a server restart under a surviving session repairs it only through §8.1's
   rewrite. That is the designed behaviour and it worked here, but the mode
   readback is now a level whose staleness the PLC times (`ModeDisagreeTimer`);
   worth one line in the design round about the interaction.
4. **The plant could not be accelerated from rest by the closed-loop smoother**
   (0.034 m/s commanded against 0.001 m/s achieved), so observation 3's command
   source was a publisher on the gate's input. This is the LESSONS 2026-08-05
   deadlock region and it is `agv/`'s, but it will shape any AT that needs the
   vehicle moving at a chosen speed.
