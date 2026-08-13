# m5-36 — the stand-in writer: design

    gate:                M5 (criterion (a)); URGENT — the cell is inert until it ships
    agent:               bridge
    goal:                A design for the process that advances the stand-in heartbeat and drives the three safety channels, buildable tonight, working with the field evaluation absent.
    invariants_touched:  none — but see §4, the layer's boundary statement changes
    inputs:
      - plc/forklift-safety/SPEC.md **§7** — **the authority.** It specifies the writer completely; you are choosing how to realise it, not what it does
      - plc/forklift-safety/SPEC.md §5.4 (the S015 networks the writer feeds) and §10
      - docs/adr/0015-criterion-a-standin-stimulus.md
      - plc/forklift-safety/evidence/m5-03b-standin-stimulus-proof.ps1 — **the proven write path**, and m5-03b's report
      - plc/forklift-safety/evidence/m5-25b-standin-stimulus-repeat.ps1
      - bridge/ — all of it, especially README.md's boundary statement and bridge-design.md
      - agv/forklift/FIELD-EVALUATION.md — the zone channel's eventual source, **which does not exist yet**
      - docs/LESSONS.md
    deliverable:         bridge/STANDIN-WRITER-DESIGN.md and docs/reports/m5-36-standin-writer-design.md
    done_when:           A coding agent can build it tonight without a second design decision, including what it does with no field evaluation present, and the layer boundary change is written out rather than assumed.
    forbidden:
      - redesigning what SPEC §7 already specifies — rate, level republish, the four members, the failure behaviour are settled. If §7 cannot be realised as written, STOP and report
      - writing code — this brief produces a design
      - touching `plc/` — **the owner is working there right now in another session**
      - any design that needs `agv/forklift/FIELD-EVALUATION.md` to be built first; it is a design, not a running node
      - weakening the labelling: this is a **stand-in**, and it says so wherever it appears (FIO-FEASIBILITY §6 consequence 1)
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. Why this is urgent tonight

The owner has taken option A in the TIA session. When the S015 delta lands,
`StandInValid` boots FALSE and stays FALSE **until the heartbeat is seen to
change**. Nothing in the system advances that heartbeat. So both demands stay
latched, no reset is accepted, and the cell — **including the working M4 teleop
demonstration** — is inert until this process exists.

That is fail-safe and by design. It is also why this ships tonight.

## 2. What it must do on the first night

The full design in SPEC §7 has two sources: the field evaluation over a named
WSL→Windows link, and an operator console. **The field evaluation does not
exist** — m5-12 produced a design, not a node.

So the design must say exactly what the writer does when the zone source is
absent, and the answer has to be usable: a writer that refuses to run without a
field evaluation leaves the cell inert, which is the situation we are fixing.
Say what the zone channel reports in that state, why that is the safe choice,
and how an operator gets the cell moving tonight.

**Get the heartbeat right first.** Everything else is secondary to a heartbeat
that advances and a `StandInValid` that goes TRUE.

## 3. The write path is proven — use it, do not re-invent it

`m5-03b` proved the path end to end and twice: the PLCSIM Advanced API writes
`SafetyInputStandIn` by tag name, the F-program consumes it inside one F-OB
cycle, and the result was corroborated on a witness that cannot see the written
datum. Two scripts already exist that do this. **Start from them.**

Read m5-03b's report for the constraints that came with it, including which
instance name is used and that the working project's instance is **not**
`FIOPROBE`.

## 4. The layer boundary — write it out, do not assume it

The owner ruled this lives in `bridge/`, because `bridge/` is already the
simulation's stand-in for field wiring and this is that role for the safety
channel. Two things follow and both belong in the design:

- `bridge/` will hold a **Windows-side process** beside its existing WSL
  ROS 2 / asyncua one. Say how they coexist, what starts each, and whether
  anything is shared.
- this process reaches the CPU through the **PLCSIM Advanced API**, not OPC UA.
  `bridge/README.md`'s "This layer must not access" section and
  `bridge-design.md` are written against an OPC UA client. Say exactly what
  those documents must now say. **You may write them; they are yours.**

If you conclude `bridge/` is the wrong home after all, say so with the reason —
but the owner has ruled, so the bar is a fact they did not have.

## 5. Failure behaviour

SPEC §7 already specifies it: writer death converts to a latched demand within
1 s, and a writer dying mid-press cannot fire the reset. Your design says how
the implementation achieves that, not whether it should.

Add the ones §7 does not cover because they are realisation choices: the API
session dropping, the CPU going to STOP and returning, and the process being
started twice.

## 6. Working discipline

- Read `docs/LESSONS.md` first. Directly yours: an API write is verified in the
  consumer's view, not the writer's; a level that is only written on change is
  lost across a CPU restart, so republish; and a state whose purpose is to stop
  publishing must publish its terminal value first.
- **Write the design as it settles**, not in one pass.
- **Do not commit.** The orchestrator commits by pathspec.
- Keep it short. A coding agent has to build from this tonight.
