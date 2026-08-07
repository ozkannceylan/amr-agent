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

**b. The stand-in writer, in its own PowerShell window. Leave the window
open: it is your second keyboard.** From the repository, on Windows:

    powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance safecell3

It prints `all eleven members of SPEC 11.3 are present` and then a `CYCLE`
line every 50 ms. If it refuses on the mutex, an old writer is still running -
run `./demo.sh down` first.

> If you forget this, `./demo.sh up` will stop and print the command for you,
> then wait for the writer to appear. It will not start the Linux half against
> no writer, because that produces a vehicle that will not move.

---

## 2. Bring the stack up (WSL, one command)

    cd /mnt/c/Users/ozkan/projects/amr-agent
    ./demo.sh up            # add --headless for no Gazebo window

**What "ready" looks like.** Five numbered steps, each ending in `ok`, then
the controller's own state read back over OPC UA, then the word `READY.`
Every `ok` line names the thing that was observed - a topic that carried a
message, a log line, the HMI answering with a connected session and metrics.
Nothing here is a timer.

If a check fails, the script says **which component** and **what was
expected**, leaves everything running with its logs in `/tmp/amr-agent-demo`,
and stops. That is deliberate: a half-started stack that says nothing is worse
than one that refuses.

---

## 3. The first thing to do: the monitored reset

**The vehicle boots deaf. `TorqueOffDemand` is TRUE at every CPU start**, and
`up` prints exactly that, read from the CPU, at the moment it matters. This is
intended, not a fault. Until you do the monitored reset, nothing you do on the
HMI will move anything.

The reset needs **both hands at once**, and all three preconditions, or it is
refused:

| | |
|---|---|
| writer window | type `estop close` - the circuit must be closed |
| HMI page (http://127.0.0.1:8088/) | release **PROCESS STOP**; it boots engaged |
| the field must be clear | `up` warns you if it is not |
| then, together | type `reset pulse 2000` at the writer **and** hold the HMI **RESET** button across the same two seconds |

The latches clear on the **release**, about 2.1 s after you start, and only
with the cause gone. Watch `SafetyResetRequired` go FALSE on the page.

**Then give the drive mode a fresh edge.** After any latch, select
**None** and then **Teleop** again. Holding a mode request through a latch is
not a re-entry, and the vehicle will sit still with everything else looking
correct. Measured 2026-08-07: with a standing request, teleop never became
active; with the None -> Teleop edge it became active in 0.6 s.

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
| **E-stop** | writer window: `estop open` | `EStopDemand` latches in well under 100 ms, the setpoint is withdrawn in the same sample, the vehicle comes to standstill. **`TorqueOffDemand` does NOT form on an e-stop** - that is the specification, not a fault | `estop close`, **then** the monitored reset. Closing the circuit alone is not a reset |
| **Torque off reaching the plant** | it comes with the protective stop above | the contactor opens and refuses every command at the traction terminal, including a permissive one | monitored reset |

**If the reset is refused, the cause is still standing.** The commonest case
on stage: the vehicle has stopped in front of an obstacle, the field is still
occupied, and it is torque-off so it cannot reverse out. Move the obstacle, or
put the vehicle back:

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
| any component | `/tmp/amr-agent-demo/<component>.log` |
| the vehicle will not move at all | did you do the monitored reset, and the None -> Teleop edge after it |
| `up` stops at the bridge | is the CPU in RUN; `bridge.log` says whether the endpoint answered |
| `up` stops at R3 | `bridge.log` names each input still missing - that names the vehicle process that is not publishing |
| `up` stops at a topic | that topic's publisher is the process that did not come up; its output is in `plant.log` |

Never read an exit code as a diagnosis here. Every ROS launch teardown writes
`exit code -2` and `user interrupted with ctrl-c (SIGINT)`, including runs that
were alive and serving in the same second.
