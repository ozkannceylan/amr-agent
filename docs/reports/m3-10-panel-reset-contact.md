brief:               docs/briefs/m3-10-panel-reset-contact.md
status:              done
files_changed:
  - sim/worlds/cell.sdf          (reset button visual on the panel; header and panel comments)
  - sim/launch/cell_bringup.launch.py  (the contact itself: one bridge entry; header comment)
  - sim/README.md                (signal table row, polarity section, initial-value note,
                                  drive commands, expected evidence, design note)
  - sim/worlds/CELL_EVIDENCE.md  (scope note on the container capture + Appendix A, the
                                  verified WSL run of the reset contact)
invariants_touched:  none
open_questions:
  - "The bridge does not know about this contact yet. bridge/config/bridge.yaml has no
     reset entry and bridge/tools/cell_stimulus.py drives three panel contacts, not four.
     Both are bridge/ files, outside this agent's write access. REQUESTED, not created.
     The bridge's pre-first-publish default for this contact must be FALSE (not pressed);
     defaulting it TRUE would clear a latch the instant the bridge started."
  - "plc/demo-cell/SPEC.md still implements the monitored reset on PanelStartPressed,
     because that was the only device available when m3-05 was written. Now that a real
     reset exists, the conflation in SPEC §5-§7 should be replaced by the dedicated
     contact. That is plc/'s work and needs the OPC UA node from m3-11 first."
  - "Appendix A's evidence is WSL, not the container. Per LESSONS 2026-07-27 (evidence is
     qualified by the environment that produced it) it is recorded alongside the container
     capture rather than replacing it. The container has never run a cell with a reset."
next_suggested:      m3-11 interface — add the OPC UA node mirroring this contact; the semantics it must mirror are stated below.

---

## What the interface agent needs for m3-11

The signal, exactly as the cell now publishes it:

| Property | Value |
|---|---|
| ROS 2 topic | `/cell/panel/reset` |
| Message type | `std_msgs/msg/Bool`, field `data` |
| Proposed sim signal name | `PanelResetContact` (`sim/README.md` signal table) |
| Direction | cell → PLC (PLC **input**) |
| gz side | `gz.msgs.Boolean`, bridged ROS → gz exactly like the other three panel contacts |
| Polarity | **Normally open.** `true` = contact closed = button held. `false` = released, **or broken wire, or nothing publishing** |
| Timing | Momentary level. The cell publishes the level while the button is held and never latches, stretches, debounces or edge-detects it |
| Safe value before the first publish | `false` (not pressed) |
| Side effects in the cell | **None.** It drives no actuator, clears no simulated fault and does not touch belt, encoder or photo-eye state |

Semantics the OPC UA node has to mirror, stated as the node model's own
§9.3 rows state the others:

- It is a **level, not an event**. The PLC forms the rising edge and times
  the hold; the bridge writes each publish through unchanged, on change,
  refreshed on reconnect — the same "Panel contacts" row that already
  governs start, stop and process stop in `opcua-nodes.md` §7.
- It is **R/W on the server** for the same reason the other three inputs
  are: the bridge writes it. Nothing else may.
- Its **fail state is `false`**. This is the opposite of `PanelStopCircuitClosed`
  and `PanelProcessStopCircuitClosed`, and the difference must be written
  into the node's description rather than left to be inferred, because a
  reader who has just read those two rows will otherwise assume NC. A stop
  fails to *stopped*; a reset fails to *not reset*.
- Suggested BrowseName: `PanelResetPressed`, under `DemoCell/Input/`. This
  is the name `m3-05` requested and it parallels `PanelStartPressed`, whose
  `...Pressed` suffix already encodes NO polarity in exactly this way. The
  interface agent owns the final name.
- It is **not** a safety function, carries no safety integrity, and must not
  be described as one. It resets process latches in the standard program.
  The safety chain is hardwired to the F-CPU and never crosses the network.

## The polarity decision, written out

`CLAUDE.md` §9 says "wire NC, program NO", and that rule governs **stop and
safety devices**: they are wired closed so a broken wire drops the signal
and stops the machine. Applying it to a reset inverts its failure
direction. An NC reset would read "pressed" when the wire is cut, when the
contact welds closed, and — in this simulation — whenever nothing is
publishing, which is the state the cell is in at every startup. Each of
those would clear a latch with no operator present, which is precisely the
automatic resume §9 forbids after a stop.

The contact is therefore **normally open**: `true` only while a hand is on
it. This is confirmed in the run below, where the level is `None` before
any publish, `true` only while `true` is published, and back to `false` on
release.

## What was verified, and where

**Gazebo Harmonic appeared during this brief.** `sim/setup/WSL_ENVIRONMENT.md`
records it as absent and blocked on elevation; the owner's install landed
mid-task (`ros-jazzy-gz-sim-vendor 0.0.10`, `ros-jazzy-ros-gz 1.0.22`,
`gz sim` 8.11.0). My first check found it missing and my second found it
present, so the brief's "you may not be able to run it" no longer applies.
**The cell was run and the contact was verified for real.** The full capture
is `sim/worlds/CELL_EVIDENCE.md` Appendix A.

Verified by running the cell headless in WSL2 Ubuntu 24.04:

| Claim | How it was checked |
|---|---|
| `/cell/panel/reset` exists alongside the other panel topics | `ros2 topic list` — eight `/cell/*` topics plus `/clock` |
| Its type and direction match start and stop | `ros2 topic info` on both: `std_msgs/msg/Bool`, publishers 0, subscriptions 1 (the bridge subscribes, so it is an input) |
| It is actuable headless the same way the others are | `ros2 topic pub` on the topic, read back on the ROS side and observed on the gz side with `gz topic -e -t /cell/panel/reset` |
| The three existing contacts are unchanged | Launch log shows all four `Creating ROS->GZ Bridge` lines with identical shape; no existing name or type was touched |
| It is momentary, not latching | Level follows the publish: `true` while held, `false` on release, nothing left behind after a tap |
| It is normally open | No value on the wire before the first publish; never `true` at rest |
| **It energizes nothing** | Belt position, belt velocity and beam range identical across a hold, a release and a tap with the belt idle; with the belt running at 0.15 m/s a press neither stopped it nor changed its speed (velocity stayed 0.150, position kept advancing 0.1503 m/s through the press) |
| The world still loads | `gz model --list` unchanged: `Floor`, `Conveyor`, `ProductBox`, `ProductSensor`, `SensorReflector`, `OperatorPanel` |

Also checked statically: `cell_bringup.launch.py` imports under ROS 2 Jazzy
and `generate_launch_description()` builds; the `<sdf>` element parses with
a strict XML parser; the bridge argument list has nine entries and no
duplicates.

The commands, if the run needs reproducing:

```
source /opt/ros/jazzy/setup.bash
ros2 launch /mnt/c/Users/ozkan/projects/amr-agent/sim/launch/cell_bringup.launch.py
# second terminal
stdbuf -oL gz topic -e -t /cell/panel/reset &
ros2 topic pub -1 /cell/panel/reset std_msgs/msg/Bool "{data: true}"
ros2 topic pub -1 /cell/panel/reset std_msgs/msg/Bool "{data: false}"
ros2 topic echo /cell/conveyor/joint_state --once      # unchanged across the press
```

### What was NOT verified

- **Nothing was run in the container.** Appendix A is WSL evidence. The
  container capture in sections 1 to 7 of `CELL_EVIDENCE.md` predates the
  reset and was not re-run.
- **The OPC UA path was not exercised.** The bridge has no reset node yet
  (see open questions), so the contact was only proven as far as the gz
  side of `ros_gz_bridge`. Nothing was measured about how it reaches the
  PLC.
- **No PLC logic was tested**, because none exists for this contact yet.
  What was shown is that the cell offers the contact and does nothing with
  it, which is the deliverable.
- **`ros2 topic pub -1` was not the mechanism used** for the state-invariance
  measurements; a persistent publisher was, because a one-shot publisher can
  lose its message to discovery. Both are in the README; the one-shot form is
  fine for a human at a keyboard and is what the existing docs already show.

## Scope

Only `sim/` and this report were written. `docs/interfaces/` was not
touched — the OPC UA node is m3-11's and belongs to the interface agent.
`plc/` and `bridge/` were not touched. No existing panel contact was
renamed or retyped, no new topic naming convention was introduced, no
dependency was added, and nothing was committed. The reset is not described
anywhere as a safety function and was not added to any safety chain.

The scratch probe script used for the measurements was written outside the
repository and deleted after the run.

---

## lessons_candidates

2026-07-27 | Assumed a blocked toolchain install was still blocked, on the strength of a document written earlier the same day | The owner's `apt` install landed mid-task, so the cell was runnable and a brief written around "you probably cannot run it" would have shipped unverified work | Re-check a blocked dependency at the moment you need it, not against the last document that recorded it; environment status in a doc is a timestamp, not a fact

2026-07-27 | Applied CLAUDE.md §9's "wire NC, program NO" to a reset device | The rule is about stop and safety devices, which must fail to *stopped*; a reset must fail to *not reset*, so NC would make a cut wire, a welded contact or an absent publisher read as a continuous reset request | Fail-safe direction is per device, not per project: wire a device so its failure produces the state that is safe *for that device*, and write the reasoning next to the polarity so the next reader does not copy the neighbouring row

2026-07-27 | Added a signal to a cell whose verification record is a dated capture | The capture silently became an incomplete topic list, readable as "these are all the cell's signals" | When a signal is added after an evidence file is written, mark the old capture's scope in place and append the new evidence as its own dated, environment-qualified section rather than editing the original run
