# Claude-supervised M5 — the layered stack, and how to run it

> **2026-08-21: this era has a new home — [`m5/m5_ver1/`](../../m5/m5_ver1/).**
> Its runbook there ([`m5/m5_ver1/RUNBOOK.md`](../../m5/m5_ver1/RUNBOOK.md))
> is the living one: the PLCSIM Advanced trial has expired, and the first
> build now runs on a **virtual PLC** (`m5/m5_ver1/virtual_plc/`) that serves
> the same address space, boot signature and writer surface. The videos and
> HMI stills moved to `m5/m5_ver1/assets/` (links below that name them are
> historical). This page is kept as the era's original entry point, frozen.

This is the runbook for the **first** M5: the milestone as it was built
under Claude supervision, layer by layer — `agv/` (vehicle), `sim/`
(worlds), `bridge/` (ROS 2 ↔ OPC UA), `hmi/` (operator HMI), `fleet/`
(fleet layer), `viz/`, with the safety F-program on S7-PLCSIM Advanced.
It predates the hand-rebuilt stack that now fronts this repo, and it is
kept **runnable**: none of its trees moved, and its two entry scripts are
preserved under [`.archive/`](../../.archive/).

[![The first safety demonstration — teleoperated forklift with the safety chain live (4 min 9 s)](https://img.youtube.com/vi/wl1rgWyX66s/maxresdefault.jpg)](https://youtu.be/wl1rgWyX66s)

*▶ [**The first build's demonstration**](https://youtu.be/wl1rgWyX66s) —
4 min 9 s, one continuous run: the scanner drops the speed ceiling at
the warning boundary, latches a stop at the protective one, and the
monitored reset is refused while the cause stands.*

How this era relates to the rest of the repo:

1. **This stack** — the full layered composition, teleoperation + safety.
2. [`m5-plc-debug/`](../../m5-plc-debug/) — the owner's hand-debug chapter:
   the safety-PLC ↔ Gazebo integration tested piece by piece until it ran.
3. [`m5_ver2/`](../../m5_ver2/) — the step-by-step reassembly of the whole
   vehicle on those debugged foundations; its final step is the repo's
   current system.

## Entry points

Both scripts live in `.archive/` and start existing processes with their
existing configs — they add no logic of their own.

| Script | Composition | Commands |
|---|---|---|
| `.archive/demo.sh` | **M5 demonstration** — warehouse world, two safety scanners, field evaluation, speed channels, envelope gate, bridge, HMI. Command path HMI → PLC → bridge → Gazebo (ADR 0008 D1). | `up` · `down` · `status` · `check` |
| `.archive/stack.sh` | **M4 commissioning cell** — arena world, five components, no safety chain. | `start` · `stop` · inspect |

Run order for the M5 demonstration:

1. **Windows:** PLCSIM Advanced instance up, TIA program downloaded, CPU
   in RUN (this era's instance naming and signatures are recorded in the
   scripts and `docs/archive/` — check `demo.sh check` first, it verifies
   the Windows side exists before starting anything).
2. **WSL:** `./.archive/demo.sh up` — brings the composition up and
   reports ready.
3. Drive from the HMI; the safety chain is onboard and appears in no
   launch file (invariant 1).
4. **WSL:** `./.archive/demo.sh down` — takes it down and verifies
   nothing is left behind.

## Where its records live

- Architecture: [`docs/adr/`](../adr/) 0001–0015 — the ADRs are this
  era's spine and remain the repo's permanent record.
- Interfaces: [`docs/interfaces/`](../interfaces/) — VDA 5050 subset,
  OPC UA node model, handshake tables.
- Safety: [`docs/safety/`](../safety/) and the root
  [`safety_summary.pdf`](../../safety_summary.pdf).
- Planning of the era, frozen as history: [`docs/archive/`](../archive/)
  (PLAN, TODO, roadmap, briefs, reports).
- Validation evidence: [`docs/VALIDATION-M5.md`](../VALIDATION-M5.md) —
  measured against F-collective signature `29FD2C52`.

## Why a second M5 exists

The layered stack proved the architecture but accumulated integration
debt faster than it could be debugged in place. The owner took over:
first isolating the PLC ↔ Gazebo safety loop in `m5-plc-debug/`, then
rebuilding the vehicle in verified steps in `m5_ver2/` — each step a
frozen copy of the last, each earning its own PROOF. The final step of
that chain is the system the root README describes. Nothing here was
deleted; this stack remains the reference for the layered architecture
that M6 will scale.
