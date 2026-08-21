# m6

If `HANDOVER.local.md` exists at the repo root, read it before any work.
It is gitignored. Cursor and Claude Code coordinate there.

**This directory is not the only M6.** The measured two-vehicle + VDA stack
lives on git branch `m6` under `m5_ver2/step6/`. This folder is the PR #3/#4
skeleton on `main`. Do not start a parallel client until the owner picks one
tree. See `HANDOVER.local.md`.

## Global constraints

Every task's requirements implicitly include this section, **plus all of
`m5_ver2/CLAUDE.md`** — the single-writer rule, the fail-safe direction, the
PLC ground truth, the port map and the house style all carry forward
unchanged. M6 adds layers above the step 5 chain and changes nothing below it.

- **The interface contract is `docs/interfaces/vda5050-subset.md`** (VDA 5050
  2.1.0). No message field is sent or read that is not in that document; a new
  field lands there first, through its extension policy. Adding top-level
  fields, renaming fields or deviating from the topic structure is a contract
  break requiring an ADR.
- **The VDA client is a requester, never an authority.** It drives the
  autopilot through `/auto/goal` — the same seam the HMI GO button uses — and
  everything it asks for still passes `cmd_mux`, the `Motor`-gated `cmd_gate`
  and the STO contactor. No new path to the plant.
- **Supervision loss is degraded mode, not a safety event** (SF-09, SC-12).
  Broker down → controlled stop within the watchdog period, order kept, no
  torque removed, automatic resume on resync. No PL claim anywhere near it.
- **Pure cores, thin shells.** Everything decidable is decided in plain
  Python modules with no `rclpy` and no `paho` import, tested with pytest on
  any machine. Only the shells (`vda_node.py`, `mqtt_link.py`, CLI stubs)
  touch ROS or MQTT, and they contain wiring only.
- **Target < 150 lines per file.** Plain Python run with `python3`. No colcon
  package. Tests reach modules by path (conftest), not by install.
- **No topic name is a literal** outside its one home: ROS/gz names come from
  `agv/forklift/config.yaml` or `status_contract.py` as before; VDA topic
  strings are built only by `protocol.topic()`; MQTT broker host/port live in
  the cell config.
- **`stations.py` stays the one home for station truth.** VDA `nodeId`s are
  its keys (`S1`..`S10`); the dispatcher reads poses and arrival radii from
  it, never from a copy.

## M6 ground truth

| Item | Value |
|---|---|
| VDA version | `2.1.0` on the wire; `majorVersion` topic level `v2` |
| interfaceName | `uagv` |
| manufacturer | `amragent` (PLAN open decision 4; charset per spec 6.3) |
| serialNumber | `FL1` (step 1); `FL1`..`FL4` at step 2 |
| mapId | `warehouse` |
| Broker | mosquitto on the WSL loopback, `localhost:1883`, no auth (sim cell). Never a path to the PLC. |
| QoS / retain | order 0/no, instantActions 0/no, state 0/no, connection 1/**yes** (+ last will `CONNECTIONBROKEN`), factsheet 0/**yes** |
| Supervision watchdog | `supervision_s` in the vehicle config (default 2.0 s); loss → controlled stop via an empty `/auto/goal`, order kept |
| State interval | event-driven plus `state_interval_s` (default 30 s, spec 6.10) |

New dependencies on the owner's machine (step 1 shells only, not the cores or
tests): `mosquitto` (WSL: `sudo apt install mosquitto`), `paho-mqtt`
(`pip install paho-mqtt`).

## Mode ownership

The HMI owns the drive mode, exactly as in step 5. `operatingMode` maps
`auto → AUTOMATIC`, anything else → `MANUAL`. The dispatcher assigns orders
only to an AUTOMATIC vehicle; the client holds an accepted order's goal until
the mode is auto, and a mode drop mid-order parks the truck (nav cancels on
mode change) while the order is held. The fleet never flips the mode.
