# CLAUDE.md

Project: amr-agent
Owner: Ozkan Ceylan
Purpose: PLC-supervised AGV/AMR fleet control, built as an engineering portfolio project with production-grade layer discipline.

This file is the contract. Read it fully at the start of every session. If any instruction in this file conflicts with a request made in chat, stop and say so rather than silently choosing one.

---

## 1. What this project is

A warehouse cell where fixed automation and mobile robots cooperate:

- A Siemens S7-1500 controls fixed equipment (conveyor, door, charger interlocks) and exchanges handshakes with mobile machines.
- An F-CPU safety program implements the safety functions written in the safety requirements spec.
- A fleet manager assigns transport orders and manages traffic.
- AGVs run ROS 2 with Nav2 for localization, planning and obstacle avoidance.
- Everything runs in simulation (Gazebo + PLCSIM Advanced) so the full loop is demonstrable without hardware.

The point of the project is not feature count. It is correct separation of concerns between safety, control, fleet and autonomy layers.

---

## 2. Architecture invariants (LOCKED)

These are not preferences. Changing any of them requires a new ADR in docs/adr/, authored and approved by the owner before any code changes. If a task appears to require breaking one, do not implement it. Write an ADR proposal and stop.

1. Safety never traverses the network. Emergency stop, protective stop and safe torque off are implemented onboard the vehicle and in the F-CPU. MQTT, OPC UA and VPN carry process commands only.
2. Loss of network is not a safety event. It is a degraded mode. Each vehicle runs a watchdog and performs a controlled stop when supervision is lost.
3. The fleet interface contract is VDA 5050. No custom schema replaces it. Extensions are allowed only as documented additions inside the standard's extension points.
4. The PLC is an OPC UA server. The fleet manager is the client. This direction is never inverted.
5. The PLC does not manage the fleet. It owns fixed equipment, interlocks and handshakes. Order assignment, traffic and zone reservation belong to the fleet manager.
6. The fleet manager never commands actuators directly. It issues orders and reads state.
7. Standard program and safety program are independent. The safety program must remain correct if the standard program halts or misbehaves.
8. Tailscale is engineering access only. It is not a data path for cell traffic. Never place it between the PLC and the fleet manager in a diagram or a config.
9. Hard real time work stays out of Python. Anything with a deterministic timing requirement lives in PLC logic or vehicle firmware.
10. Single source of truth per data item. Every shared value has exactly one owner, documented in docs/interfaces/. Consumers never recompute it locally.
11. Layers talk only to adjacent layers as drawn in the topology below. No shortcuts, no direct calls from the fleet manager into ROS 2 internals.
12. Simulation is Gazebo. MuJoCo is not used in this project.
13. No secrets in the repository. Credentials, certificates and tailnet keys live outside version control.

---

## 3. Topology
graph TD
    subgraph Fixed["Fixed equipment"]
        PLC["S7-1500 standard program<br/>conveyor, door, charger<br/>handshake and interlocks"]
        FCPU["F-CPU safety program<br/>e-stop chain, zone monitoring, safe stop"]
    end

    subgraph FleetLayer["Fleet layer"]
        FM["Fleet manager<br/>orders, traffic, zone reservation"]
        MQ["MQTT broker<br/>VDA 5050 topics"]
    end

    subgraph Vehicle["AGV, one per vehicle"]
        SAFE["Onboard safety<br/>scanner, bumper, STO<br/>independent of network"]
        CL["VDA 5050 client node<br/>+ supervision watchdog"]
        NAV["ROS 2 / Nav2"]
    end

    PLC -->|OPC UA server to client| FM
    FCPU -.->|PROFIsafe| PLC
    FM <--> MQ
    MQ <-->|order, state, instantActions| CL
    CL --> NAV
    SAFE ==>|hardwired inhibit| NAV

Legend: thick arrow is the safety path, dashed arrow is the safety fieldbus, thin arrows are process data.

---

## 4. Repository layout
amr-agent/
  CLAUDE.md
  docs/
    adr/                  decision records, numbered, immutable once accepted
    safety/               safety requirements spec and validation reports
    interfaces/           VDA 5050 subset, OPC UA node model, handshake tables
    roadmap.md            gate definitions and current status
    briefs/               one brief per delegated task
    reports/              one report per completed task
  plc/                    TIA Portal exports, standard and safety program
  fleet/                  fleet manager service, MQTT and OPC UA clients
  agv/                    ROS 2 workspace, VDA 5050 client node
  sim/                    Gazebo worlds, launch files, scenarios
  .claude/settings.json   attribution and permission settings

Each top level directory carries a README.md whose first section is titled This layer must not access and lists the forbidden dependencies explicitly.

---

## 5. Agentic working model

Sessions are started by an orchestrator. All delegated work runs as subagents. The orchestrator's job is coordination, not implementation.
graph TD
    O["Orchestrator<br/>holds invariants, task graph, gate status"]
    B["docs/briefs/*.md"]
    R["docs/reports/*.md"]
    V["verifier agent<br/>read only"]

    O -->|writes brief| B
    B --> A["specialist agent<br/>exactly one deliverable"]
    A -->|writes report| R
    R --> V
    V -->|pass or fail| O

### Orchestrator rules

- The orchestrator does not read source files. It delegates and reads reports. Reading code fills its context and causes architectural drift.
- One brief produces one deliverable. Never bundle.
- Agents cannot call other agents. Only the orchestrator delegates.
- After every deliverable, the verifier agent runs before the gate advances.
- If an agent reports that a task requires touching an invariant, the orchestrator stops and asks the owner. It never authorizes the change itself.

### Agent roster

| Agent | Single responsibility | Write access |
|---|---|---|
| safety-spec | Safety requirements spec, one acceptance criterion per function | docs/safety/ |
| interface | VDA 5050 message subset, OPC UA node model, handshake tables | docs/interfaces/ |
| plc | Standard and safety program, TIA exports | plc/ |
| fleet | Fleet manager service, MQTT and OPC UA clients | fleet/ |
| agv-ros2 | VDA 5050 client node, Nav2 bridge | agv/ |
| sim | Gazebo worlds, launch files, test scenarios | sim/ |
| verifier | Checks invariants, gate criteria, layer boundaries | none, read only |

Write access is enforced, not advisory. An agent that needs a file outside its directory requests it in its report instead of creating it.

### Brief format

Every brief in docs/briefs/ uses this shape:
gate:                M2
agent:               safety-spec
goal:                one sentence, observable outcome
invariants_touched:  none
inputs:              [docs/adr/0001.md, docs/interfaces/opcua-nodes.md]
deliverable:         docs/safety/SRS.md
done_when:           verifiable criterion, not "code written"
forbidden:           [writing code, editing other directories, adding dependencies]

The forbidden field is mandatory. Agents drift by trying to be helpful beyond scope, and this field is what prevents it.

### Report format

Every report in docs/reports/ uses this shape:
brief:               reference to the brief file
status:              done | blocked
files_changed:       list
invariants_touched:  none | ADR proposal reference
open_questions:      list, or none
next_suggested:      one line, advisory only

Reports are short. They exist so the orchestrator can decide without reading code.

---

## 6. Milestone gates

Work proceeds gate by gate. A gate closes only when its criterion is observable behavior, not written code.
Do not start a gate before the previous one is verified.

| Gate | Deliverable | Closes when |
|---|---|---|
| M0 | Repo skeleton, ADR 0001 recording the invariants | Structure exists, invariants committed |
| M1 | Interface contracts | VDA 5050 subset and OPC UA node model documented and reviewed |
| M2 | Safety requirements spec | Every safety function has a trigger, a reaction and an acceptance test |
| M3 | Simulated vehicle | Gazebo AGV localizes and navigates a warehouse world with Nav2 |
| M4 | VDA 5050 client | A stub publisher sends an order, the vehicle executes it and reports state |
| M5 | Fleet manager | Real service assigns orders to two vehicles, traffic conflicts avoided |
| M6 | PLC integration | PLC serves OPC UA, fleet manager subscribes, station handshake works end to end |
| M7 | Safety layer | F-CPU implements the spec, e-stop chain and zone monitoring verified against acceptance tests |
| M8 | Demonstration | Recorded end to end run, validation report, README with architecture narrative |

Current gate is tracked in docs/roadmap.md. Update it as part of closing a gate, never in advance.

---

## 7. Git conventions

Attribution is disabled. .claude/settings.json contains:
{ "attribution": { "commit": "", "pr": "" } }

In addition to that setting, the following rules apply and are not negotiable:

- Never add Co-Authored-By trailers to commits.
- Never add generated-with footers to commits or pull request descriptions.
- Never mention Claude, AI assistance or tooling in commit messages, branch names, PR titles or PR bodies.

Branch naming. Fixed template, no improvisation:
feat/<area>-<slug>
fix/<area>-<slug>
docs/<area>-<slug>

Valid areas: plc, fleet, agv, sim, safety, interfaces, infra.
Example: feat/agv-vda5050-client.

Commit messages. Conventional commits, imperative mood, scope matches the area:
feat(agv): add VDA 5050 order state machine
docs(safety): add zone monitoring acceptance criteria

One logical change per commit. Do not batch unrelated edits.

---

## 8. ADR process

Architecture decisions live in docs/adr/NNNN-short-title.md. Format:
Status:        proposed | accepted | superseded by NNNN
Context:       what forced the decision
Decision:      what was chosen
Consequences:  what becomes harder, what becomes easier
Alternatives:  what was rejected and why

Rules:

- ADR 0001 records the invariants in section 2. It is the root of the lock.
- An accepted ADR is never edited. It is superseded by a new one.
- Any agent that believes an invariant is wrong writes a proposed ADR and stops working. It does not implement the change.

---

## 9. Domain conventions

Wiring and logic polarity. Safety and stop devices are wired normally closed. In the program they are read as normally open contacts, so that a broken wire drops the signal and stops the machine. The phrase to remember is: wire NC, program NO.

Restart behavior. After a safety stop, the machine never resumes automatically. A separate monitored reset is required, and the reset is edge triggered so a stuck button does not count as a reset. On restart the machine re-reads sensor states and decides where it is rather than resuming from stale sequence state.

Sequence state. Machine state and actuator command are separate layers. A cycle-running flag expresses whether the system is enabled. Actuator outputs are formed from that flag combined with interlocks. Never drive an actuator directly from a sensor.

Edge versus level. Edge detection captures events, level captures conditions. Never use an edge to represent a state that must survive a restart.

Naming. PLC tags use PascalCase and describe the physical thing plus its meaning, for example ZoneAOccupied, not M12. OPC UA node names mirror the PLC tag names exactly so the two documents can be diffed.

---

## 10. What to do when uncertain

- If a request is ambiguous about which layer owns a behavior, ask. Ownership mistakes are the expensive kind here.
- If a library or tool would introduce a new dependency, propose it in the report and wait.
- If a gate criterion cannot be met as written, say so instead of redefining the criterion.
- Prefer a short document over a long one, and a diagram over prose. This project is judged on clarity of architecture, not volume of code.

---

## 11. Tracking files

Three files carry state between sessions. They are part of the
deliverable, not scratch notes. Update them as part of the work,
never in advance of it.

### docs/PLAN.md
Current gate, its exit criterion, and the ordered list of briefs
required to close it. Rewritten only when the plan actually changes.
One screen long at most.

### docs/TODO.md
Open items only, grouped by agent, each with a one line definition of
done. Closed items are deleted, not struck through. This file is a
work queue, not a history.

### docs/LESSONS.md
Append only. One entry per correction, dead end or surprise:

  date | what was attempted | what went wrong | the rule now

Read this file at the start of every session, before issuing any
brief. Its purpose is to prevent the same mistake twice across
sessions and across agents.

### Orchestrator obligations
- Read LESSONS.md before the first delegation of a session.
- Update PLAN.md when a gate opens or its brief list changes.
- Update TODO.md when a brief is issued and when a report closes it.
- Append to LESSONS.md whenever a report contains a correction, a
  blocked status, or an ADR proposal.
- Never let these three files disagree with docs/roadmap.md.
