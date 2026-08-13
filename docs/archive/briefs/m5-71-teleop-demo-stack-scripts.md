# m5-71 — one command up, one command down, for the teleop + safety demo

    gate:                M5
    agent:               infra (owner-approved: repo-root scripts, both sides of the WSL/Windows seam)
    goal:                Give the owner a single command that brings the whole teleoperation demonstration up, and a single command that takes it down cleanly — so they can watch teleop and safety working together before recording anything.
    invariants_touched:  none. The scripts start existing components; they implement no behaviour.
    inputs:
      - stack.sh — the M4-era script this succeeds or extends; read it before writing anything
      - sim/launch/forklift_bringup.launch.py, agv/forklift/launch/vehicle.launch.py
      - bridge/standin_writer/standin_writer.ps1 and bridge/STANDIN-WRITER-DESIGN.md — the Windows-side half
      - bridge/config/bridge.yaml, hmi/config.yaml, viz/
      - docs/reports/m5-68-revalidation.md — the run order that actually worked, end to end, against the live CPU
      - docs/reports/m5-61-warn-sender.md and m5-57 — the three startup hazards named in §3
      - docs/TODO.md — the m4f-10 note that stack.sh's readiness timeouts were never calibrated
      - docs/LESSONS.md
    deliverable:         the up and down scripts, plus a short RUNBOOK the owner reads once
    done_when:           From a cold machine, one command brings the stack up and reports ready; the owner can drive from the HMI and see the safety functions act; and one command takes it down leaving no writer, no port and no gz sim behind — demonstrated, not asserted.
    forbidden:
      - starting or stopping anything in TIA, or changing the CPU. PLCSIM is the owner's to run
      - inventing a new bringup path. Compose what exists; if a launch file cannot do the job, report that rather than writing a parallel one
      - hiding a failure behind a sleep. A readiness check waits for a condition, not for a duration
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. What the owner asked for

Scripts like M4's: **bring the whole stack up — HMI, Gazebo, the PLC connection
— and take it down.** So they can see with their own eyes that **teleoperation
and safety work together**, and only then record the showcase.

This is not a new capability. Every piece ran together three days running. What
is missing is that bringing it up currently takes an expert who knows the order,
and the owner should not have to be that expert at 9 a.m. on a presentation day.

## 2. The seam is the hard part, and it is why this brief exists

This stack spans two machines' worth of process:

- **WSL** — Gazebo, the ROS 2 vehicle stack, the field evaluation, the bridge,
  the monitoring service, the HMI
- **Windows** — PLCSIM Advanced (the owner's, do not touch) and the
  **stand-in writer**, which is PowerShell and reaches the CPU through the
  PLCSIM API rather than OPC UA

A script that brings up only the WSL half looks like it worked and produces a
vehicle that will not move. Handle both sides, or state clearly which side the
owner starts by hand and check for it before declaring ready.

## 3. Three startup hazards that have each cost a run

These are measured, not theoretical. Each has cost an agent a full run:

1. **With the writer running and no field source, `WarningFieldClear` is FALSE**,
   the reduced limit is in force, and **no monitored reset is accepted** while
   the vehicle is above it. The field evaluation must be up before it matters.
2. **`SpeedChainSeen` is TRUE and only a cold start clears it.**
3. **`TorqueOffDemand` boots TRUE**, so at every CPU start the vehicle is
   torque-off until a monitored reset. **This is intended, not a fault** — and
   it is exactly what will make the owner think the stack is broken thirty
   seconds after starting it.

**The script must tell the owner about number 3 in its own output**, at the
moment it matters, in one line. Not in a document they read last week.

## 4. Readiness, not sleeping

`docs/TODO.md` records that `stack.sh`'s readiness timeouts were never
calibrated because no bringup ever ran in the container. Do not inherit that.

Each component is ready when an **observable** says so — a node present, a topic
publishing, a port answering, a node resolved on the server. Wait for the
condition. If it does not arrive, **say which component and what was expected**,
and stop. A stack that half-starts silently is worse than one that refuses.

## 5. The down script matters as much as the up

Every session so far has ended with a hand-written cleanup, and the evidence
files record what gets left behind: writers still holding a mutex, ports 45015
and 45016 still listening, `gz sim` still running, vehicle-side processes
outliving their launch. The next run then starts dirty and its first measurement
is wrong.

**Down means down**, and the script verifies it rather than assuming: no writer,
no listener on either port, no `gz sim`, no orphaned node. Report what it
checked.

Note the existing `SURVIVOR_PATTERNS` mechanism in `stack.sh` — it exists
because processes were being missed. Extend it; do not replace it blindly.

## 6. The RUNBOOK

One page, written for the owner on presentation morning, in the order they will
actually do things:

- what to start by hand first (PLCSIM, and anything else that is theirs)
- the up command, and **what "ready" looks like**
- **the first thing to do: the monitored reset**, and why the vehicle is deaf
  until then
- how to drive, and what to look at while driving — the HMI, and where the
  safety state is visible
- **what to do to see each safety function act**: the warning slowdown, the
  protective stop, the e-stop, and the reset that recovers each
- the down command, and how to tell it worked

Keep it to one page. If it needs two, the scripts are doing too little.

## 7. Working discipline

- Read `docs/LESSONS.md` first.
- **Demonstrate the scripts, do not assert them.** Cold start, up, drive,
  safety acting, down, verified clean — and record what you observed.
- If the machine is busy when you start, wait for it rather than working around
  it. Another run may be in flight.
- **Do not commit.** The orchestrator commits by pathspec.
