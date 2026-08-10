# RUNBOOK - the teleoperation and safety demonstration

One page, in the order you actually do things. Two commands: `./demo.sh up`
and `./demo.sh down`.

Nothing below claims or implies an achieved Performance Level, Category, SIL
or PFH. The onboard inhibit and the writer are engineering stand-ins.

---

## 1. Start what is yours (Windows, by hand)

**a. PLCSIM Advanced, CPU in RUN.** From TIA Portal, as you always do. Note
the **instance name** off the PLCSIM Advanced control panel - `demo.sh`
assumes `safecell3`; if yours differs, `export AMR_PLCSIM_INSTANCE=<name>`
before running it.

**b. The stand-in writer and its bench panel, one command.** From the
repository, on Windows:

    powershell -ExecutionPolicy Bypass -File bridge\standin_writer\bench_panel.ps1 -Instance safecell3

This starts the writer in its own PowerShell window **and** opens the panel
beside it - *Safety input channels, engineering stand-in*. **Leave the writer
window open**: it is still your second keyboard and its log is still the
record.

**What "it is working" looks like**, three things on the panel, in order:

| | |
|---|---|
| the strip under the red banner | **IN FORCE**, in green, naming the instance. Red means nothing you press reaches the CPU, and it says which of the reasons it is |
| right-hand column | **Stand-in heartbeat** *advancing at 20 Hz*, **PLCSIM API session** *connected* |
| E-STOP CIRCUIT | **OPEN**. That is the correct boot state - see section 3 |

The writer window itself prints `all eleven members of SPEC 11.3 are present`
and then a `CYCLE` line every 50 ms. If it refuses on the mutex, an old writer
is still running - run `./demo.sh down` first. To put a panel on a writer that
is already up, start that writer with `-CommandFile <path>` and give the panel
the same `-CommandFile <path>`.

> If you forget this, `./demo.sh up` will stop and print the command for you,
> then wait for the writer to appear. It will not start the Linux half against
> no writer, because that produces a vehicle that will not move.

---

## 2. Bring the stack up (WSL, one command)

    cd /mnt/c/Users/ozkan/projects/amr-agent
    ./demo.sh up            # add --headless for no Gazebo window,
                            # --monitor for the HMI map pane (monitor on 8089)

**What "ready" looks like.** Five numbered steps each ending in `ok`, the
controller's own state read back over OPC UA, then `READY.` Every `ok` names
what was observed - a topic that carried a message, a log line, the HMI
answering. Nothing here is a timer.

If a check fails the script names **which component** and **what was
expected**, leaves everything running with its logs in `/tmp/amr-agent-demo`,
and stops.

---

## 3. The first thing to do: the monitored reset

**The vehicle boots deaf. `TorqueOffDemand` is TRUE at every CPU start**, and
`up` prints exactly that, read from the CPU, at the moment it matters. This is
intended, not a fault. Until you do the monitored reset, nothing you do on the
HMI will move anything.

**Three facts cost a live session on 2026-08-07. None of them is a fault:**

1. **The e-stop circuit boots OPEN.** Fail-safe and correct, and **nothing
   closes it until a human does** - not the HMI, not a link, not a restart.
   Close it at the panel, or type `estop close`.
2. **The HMI's RESET is the PROCESS reset** (`HmiResetRequest`) and cannot
   reach an F-latch. The **F-side** reset is the panel's press-and-hold button,
   or `reset pulse` at the writer, and nothing else (SPEC section 137).
3. **A mode selection refused while a demand stands is consumed, not held.**
   Holding a mode request through a latch is not a re-entry.

The reset needs **both hands at once**, and all three preconditions, or it is
refused:

| | |
|---|---|
| the panel, or the writer window | close the e-stop: **TWIST TO RELEASE**, or type `estop close` |
| HMI page (http://127.0.0.1:8088/) | release **PROCESS STOP**; it boots engaged |
| the field must be clear | `up` warns you if it is not |
| then, together | **press and hold the panel's RESET for about 2 s** (the F-program accepts 200-3000 ms and the panel draws the window and your hold as it runs; `reset pulse 2000` at the writer does the same thing) **and** hold the HMI **RESET** across the same two seconds |

The latches clear on the **release**, about 2.1 s after you start, and only
with the cause gone. Watch `SafetyResetRequired` go FALSE on the page.

**Then give the drive mode a fresh edge:** select **None**, then **Teleop**
again - fact 3 above. Measured 2026-08-07: with a standing request, teleop
never became active; with the None -> Teleop edge it became active in 0.6 s.

---

## 4. Drive, and what to watch

Hold **traction** on the HMI. Every setpoint is formed by the PLC - the page
requests, the standard program decides, the bridge carries it to the plant.

Watch three numbers on the page while you drive:

- **speed** and **traction reference** - they should track each other
- the **safety lamps** - e-stop, zone stop, reset required, torque off
- **teleop active** - it drops the instant any demand latches

---

## 5. Making each safety function act, and recovering from it

| Function | How to make it act | What you see | How to recover |
|---|---|---|---|
| **Warning-field slowdown** | drive toward anything - a rack, a wall, an object you moved into the aisle | the reference falls to 0.20 x your command in the same 50 ms sample; the vehicle complies and keeps driving. **At full command that is 0.20 m/s** - a clip that says "it drops to 0.20" must be a full-command clip | nothing to do - it releases itself when the field is clear again |
| **Protective stop** | keep driving toward it | reference to 0.0, vehicle stops with your command still held, `ZoneStopDemand` latches, `TeleopActive` drops. About 0.8 s later `TorqueOffDemand` forms - that is SS1's second stage | monitored reset **with the field clear** (section 3) |
| **E-stop** | the panel's **PRESS**, or `estop open` | `EStopDemand` latches in well under 100 ms, the setpoint is withdrawn in the same sample, the vehicle comes to standstill. **`TorqueOffDemand` does NOT form on an e-stop** - that is the specification, not a fault | `estop close`, **then** the monitored reset. Closing the circuit alone is not a reset |
| **Torque off reaching the plant** | it comes with the protective stop above | the contactor opens and refuses every command at the traction terminal, including a permissive one | monitored reset |

**If the reset is refused, the cause is still standing.** The commonest case
on stage: the vehicle has stopped in front of an obstacle, the field is still
occupied, and it is torque-off so it cannot reverse out. Move the obstacle, or
put the vehicle back with one command:

    ./demo.sh home                  # moves the model to its spawn, reads the
                                    # pose back, and clears NO latch - it says so

Then do the monitored reset. The manual form, if you want a pose of your own:

    gz model -m Forklift -p                     # read the pose and the entity id
    gz service -s /world/warehouse/set_pose --reqtype gz.msgs.Pose \
        --reptype gz.msgs.Boolean --timeout 3000 \
        --req 'name: "Forklift", id: <ID>, position: {x: -3.0, y: -5.5, z: 0.05}, orientation: {w: 1}'
    gz model -m Forklift -p                     # READ IT BACK

Without the entity id `set_pose` returns `true` and does nothing. Always read
it back. Then the reset is accepted.

---

## 6. Take it down

    ./demo.sh down                  # add --keep-writer to keep the writer for a second take

**How to tell it worked.** The last block must read:

    DOWN, AND VERIFIED CLEAN: no component, no survivor in the partition,
    no listener on the HMI or monitor port, ros2 daemon stopped,
    /dev/shm swept.
    No stand-in writer, and both writer ports free.

**Close the panel window too** - it holds nothing, but one left open beside a
dead writer reads *NOT IN FORCE*.

Each of those is checked, not assumed - the survivors are found by process
identity and filtered by this run's Gazebo partition, the ports by `ss` and by
`netstat` on the Windows side, and the writer by its own named mutex. If any
of them fails, the script says so and exits non-zero: **do not start the next
run until it is clean**, because a dirty start makes the first measurement of
the next run wrong.

`down` never touches PLCSIM Advanced or TIA Portal. The CPU keeps running,
which is what you want between takes. **A cold CPU start is the only thing
that clears `SpeedChainSeen`** - if a demand will not clear no matter what you
do, that is the one thing only you can do, from PLCSIM.

---

## 7. If something is wrong

| Symptom | Look here |
|---|---|
| a protective stop with nothing near the vehicle | the scan-freshness rule firing in the demanding direction: a simulator hitch longer than `scan_fresh_max_s` (0.30 s) latches a stop with the field clear — measured ~1 per 3 min with the GUI attached on the software renderer (m5-72 §4), deliberately not retuned. Recover with the monitored reset; `--headless` and the d3d12 renderer reduce the hitches |
| any component | `/tmp/amr-agent-demo/<component>.log` |
| the vehicle will not move at all | did you do the monitored reset, and the None -> Teleop edge after it |
| `up` stops at the bridge | is the CPU in RUN; `bridge.log` says whether the endpoint answered |
| `up` stops at R3 | `bridge.log` names each input still missing - that names the vehicle process that is not publishing |
| `up` stops at a topic | that topic's publisher is the process that did not come up; its output is in `plant.log` |

Never read an exit code as a diagnosis here. Every ROS launch teardown writes
`exit code -2` and `user interrupted with ctrl-c (SIGINT)`, including runs that
were alive and serving in the same second.
