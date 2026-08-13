# m5-62 — carry TorqueOffDemand to the vehicle

    brief:               docs/briefs/m5-62-torque-off-bridge-slot.md
    status:              done
    invariants_touched:  none

## The one-line answer

**The demand now reaches the plant, and it was measured against its own positive
control in the same run: n=20 commands / 0 at the traction terminal with the
demand standing, n=20 / 20 with the same value on the same path with it absent —
twice, r1 and r2, 25 checks each, 50/50 passed.** The subscriber that had waited
since m5-50 sees `publisher count 1`.

**Against the test double. Not against the CPU, and this is not a hedge:** the
leaf does not exist on the controller yet. Probed read-only at 2026-08-06T21:58Z,
`Forklift/Safety/` advertises **four** mirrors — `EStopDemand`,
`SafetyResetFault`, `SafetyResetRequired`, `ZoneStopDemand`. `TorqueOffDemand`
and `SpeedMonitorDemand` are chunks AD–AF, the owner's session tomorrow. **Every
figure in `bridge/EVIDENCE_TORQUE_OFF_SLOT.md` is double-only and the file says
so in its §0 and §1.** Nothing was written to the CPU.

## What that made me build differently, and it is the part to read

§11.6 rules that **no client's connect may fail over this group**, and that a
bridge which cannot resolve the leaf *"logs the absence and publishes nothing
rather than synthesising either polarity"*. So the group is in the committed
`bridge/config/bridge.yaml` **today**, with the leaf marked optional in
`SAFETY_GROUP.optional_nodes`:

* against today's CPU the run connects, logs the absence once by name, resolves
  21 nodes instead of 22 and publishes **no message at all** — and no message is
  not torque-off (SD5). Measured, phase 6, both runs;
* when the owner applies AD–AF, **the next session resolves the leaf and carries
  it, with no edit to any file** and nothing to remember at the tool.

The tolerance is bounded three ways so it cannot hide a defect: only keys a group
declares optional (exactly one exists), only `BadNoMatch` / `BadNodeIdUnknown` /
`BadNotFound` (any other failure is still a connect failure), and it is re-tested
at every session establishment rather than remembered.

## The ruling, implemented rather than re-derived

| Rule | How it is in the code |
|---|---|
| **SD1** | `SpeedMonitorDemand` has no slot, no node table entry, no topic, no consumer. Checked in the harness, and observed on the server: 0 transitions all run |
| **SD2** | one output slot, read every cycle in the output phase and republished unchanged. The latch is the consumer's; nothing is held, stretched or re-timed here |
| **SD4** | release, then 1.5 s with nobody commanding → **0** forwarded; a fresh command then moves 20/20 |
| **SD5** | **no `StaleAssert`, no window, no synthesised value.** The bridge was killed mid-run with the demand absent: publisher count 0, and 20/20 commands still reached the terminal. The reason lives in a block comment at `SAFETY_GROUP`; the other behaviour is in no line of the package |
| **SD6** | the start value `TRUE` survives: phase 1 is the vehicle booting deaf, 0 of 20 commands through, terminal *driven* to the brake rather than quiet |
| **SD7** | one Bool crosses the seam. No speed, limit, margin or reading appears in any table |
| **SD9** | the evidence file's §0 and the harness's own banner state the stand-in. **No PL, Category, SIL or PFH anywhere; no stopping figure measured, derived or quoted** |
| **MR1** | the group declares **no inputs**, and the allowlist is derived from inputs — so it adds **zero** writable keys. `check_write_allowlist.py` now also attempts four `Forklift/Safety/` writes: refused `WriteNotPermitted` by the bridge and `BadUserAccessDenied` by the server, independently. 50/50 |

## Evidence, and what it cannot say

`bridge/EVIDENCE_TORQUE_OFF_SLOT.md`, written as each run landed. **No simulator
ran** (a second session held domain 61 and was running Gazebo; this session used
domain 93 and started nothing). What is measured is **delivery to the plant's
terminal topics**, not wheel rotation, and no sentence claims the vehicle moved.

The one timing pair reported — demand observed → the consumer's applied readback,
5.0–12.9 ms, **n=8 across two runs** — is labelled as draws on a loaded machine,
not a bound, and no criterion rests on it.

## The item you handed me from m5-61 — it is NOT a bridge carrier gap

`ForkliftWarning.ForkliftWarningFieldOccupied` reading `True` with both fields
clear. **The carrier exists and this round watched it work**: with a bridge
running, the double's own server-side log shows the node going `True → False` as
the field evaluation's verdict was carried (evidence §3.2).

What was read live on the controller, twice, four seconds apart:

| | 20:14:29Z | 20:14:33Z |
|---|---|---|
| `Link/BridgeHeartbeat` | 53048 | **53048** |
| `Forklift/Warning/ForkliftWarningFieldOccupied` | `True` | `True` |
| `Forklift/Input/ForkliftObstacleInStopZone` | `True` | `True` |

and `pgrep` for `run_bridge` / `amr_bridge.main`: **nothing**. **The heartbeat is
frozen and no bridge process exists**, so no client has written any
`Input/`-class node on that CPU; every one sits at its DB start value, the
warning node's `TRUE` exactly like `ForkliftObstacleInStopZone`'s. "Not yet
written" is not "clear", which is the job §13 and §10.9 gave those start values.

**So: no node to add, no rule to write, and it is neither `bridge`'s nor
`interface`'s.** m5-61's stack — field evaluation + stand-in writer + Gazebo, all
on the 45015 link — contains no OPC UA client at all. Two owners, named
precisely:

1. **run composition (whoever composes the demonstration run)** — a session in
   which that node is expected to mean anything must include the bridge with the
   `warning` group. Not a code change;
2. **`hmi/`** — any lamp fed by it renders the **age** of what it has, never the
   value alone. The instrument that separates "no bridge ran" from "the field is
   occupied" is `Link/BridgeHeartbeat` advancing.

**One fact for tomorrow, reported and not acted on: `Link/BridgeLinkOk` is not
addressable on the controller in force — `BadNoMatch`, same probe.** That is the
PLC's own verdict on bridge liveness; without it the only bridge-liveness
instrument any client has is the raw counter. Whether the forklift build should
publish a link verdict of its own is `plc/` + `interface`'s ruling, not mine.

I did **not** touch `WarningFieldClear`, `ForkliftSpeedLimitActive` or anything
in `agv/`, and I make no claim about the reduced 300 mm/s limit's effect at the
vehicle (finding F4 is unobserved and stays that way here).

## files_changed

| File | What |
|---|---|
| `bridge/amr_bridge/config.py` | `SAFETY_GROUP` (one read-only output, no inputs, no stale rule) with the SD1/SD5/SD7 reasoning on it; `SignalGroup.optional_nodes`; `Config.optional_node_keys`; the startup description line |
| `bridge/amr_bridge/opcua_side.py` | `_ABSENT_NODE_STATUSES`; optional-node tolerance in `_resolve_nodes`; `_verify_types` over the resolved set; `_output_path` and `_poll_diagnostics` skip an absent optional node and publish nothing for it |
| `bridge/amr_bridge/instrumentation.py` | one counter, `optional_nodes_absent` |
| `bridge/config/bridge.yaml`, `bridge/config/bridge-double-m5.yaml` | the `safety` group: one node, one topic, and why the group is declared before the leaf exists |
| `bridge/test_double/plc_test_double.py` | the six §11 mirrors at §11.6's start values, **read-only to every client**, in three real shapes (`--safety-mirrors six｜four｜none`); the S1 back door reaches them; warm restart, observation columns and the node-count line follow |
| `bridge/tools/check_torque_off_slot.py` | **new** — the seven-phase harness, with the positive control in the same run |
| `bridge/tools/check_write_allowlist.py` | four `Forklift/Safety/` rows; the two M5 configuration rows updated (input count unchanged at 7 — the point) |
| `bridge/tools/probe_server_paths.py` | unchanged; it already browses the folder, which is how §1's four-mirror reading was taken |
| `bridge/EVIDENCE_TORQUE_OFF_SLOT.md` | **new** — the dated capture |
| `bridge/README.md` | the group list, a row for the M5 configuration in force, the new tool and evidence file; and one stale phrase corrected — `bridge.yaml` was still described as *"cell group only"*, three group changes out of date |
| `bridge/evidence/m562-*` | r1 and r2: witness CSVs, the double's server-side observation, the bridge's evidence CSVs and every console log, plus the allowlist and regression logs. Archived only after every process was stopped; `gzip -t` verified |

Nothing outside `bridge/` and this report was written. Nothing committed, no
branch, no dependency added.

## Requests — the two documentation repairs, and why I did not make them

**The brief's §3 says both repairs are "inside `bridge/`". They are not.** The
only `bridge-design.md` in the repository is `docs/interfaces/bridge-design.md`,
which belongs to the `interface` agent, and my own `forbidden` list says *editing
outside `bridge/`*. So they are requested here, with the text ready:

| # | Request | Owner | Blocking |
|---|---|---|---|
| 1 | **`docs/interfaces/bridge-design.md` line 34** (the m5-36 scope note): *"the writer's **four** tags live in a DB the OPC UA server does not expose"* → **eleven** (`SafetyInputStandIn`, 4 + 7 since m5-49). The claim it supports is unaffected; only the count is wrong | `interface` | No |
| 2 | **`bridge-design.md` §2.1 and §4.11 — the read slot**, reserved to this brief by m5-60 request 1. As built: one row, `Forklift/Safety/TorqueOffDemand` → `/forklift/safety/torque_off_demand`, `std_msgs/Bool`, **no inversion**, read every cycle in the output phase, **no silence rule, no freshness window, no synthesised value — the deliberate opposite of row 23** (SD5, and the row should say so). Plus: its own group, **no inputs**, so the allowlist counts in §4.11 and §2.1 are unchanged at 8; **no slot for `SpeedMonitorDemand`** (SD1); and the §11.6 optionality — *the one node in this document a server may lack without failing the connect* | `interface` | No; AT-11 wants it |
| 3 | **`docs/interfaces/opcua-nodes.md` §11.6** could record that `BadNoMatch` is the status the S7-1500 actually returns for the unbuilt leaf — measured, not assumed | `interface` | No |
| 4 | **A small defect in a committed harness, found and not fixed here to keep this diff about the slot**: `bridge/tools/check_forklift_slots.py` defaults to the fixed workdir `/tmp/amr-forklift-slots`, so its check E (*"the evidence argument is a stem"*) fails whenever an earlier run's files survive — it counted a 17:02 file from another session today and reported **45/46**. With a fresh workdir the same commit passes **46/46** (`bridge/evidence/m562-regression-forklift-slots.log`). One-line fix: make the default workdir per-run, as `check_torque_off_slot.py` does | `bridge`, next brief | No |
| 5 | **`docs/TODO.md`**: this closes the bridge half of finding F1. The m5-11 §12 residue is untouched | orchestrator | No |

## open_questions

1. **The whole of `EVIDENCE_TORQUE_OFF_SLOT.md` is double-only.** The first live
   run belongs to the owner's session: after chunks AD–AF, start the bridge
   against the CPU and re-run `check_torque_off_slot.py`'s phases 1–4 with the
   demand driven by the F-program rather than by a hand. **No gate criterion may
   rest on the double runs**, and the file says so in two places.
2. **The demonstration will begin with a deaf vehicle**, every time, until a
   monitored reset clears the boot latches (SD6). Intended, and worth saying out
   loud before it is seen on stage rather than after.
3. **After this slot exists, a silent link leaves the vehicle drivable** (SD5).
   That is the ruling, and the layer that stops the vehicle in that case is the
   envelope gate's freshness rule, not this topic. Any narration of a link-loss
   scenario should name the envelope, not torque-off.

## next_suggested

Run the TIA session; then take the live phases 1–4 against the CPU in the same
session, while the F-program is the one moving the demand.
