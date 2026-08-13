# Claude-supervised M5 — the layered stack, and how to run it

This is the runbook for the **first** M5: the milestone as it was built
under Claude supervision, layer by layer — `agv/` (vehicle), `sim/`
(worlds), `bridge/` (ROS 2 ↔ OPC UA), `hmi/` (operator HMI), `fleet/`
(fleet layer), `viz/`, with the safety F-program on S7-PLCSIM Advanced.
It predates the hand-rebuilt stack that now fronts this repo, and it is
kept **runnable**: none of its trees moved, and its two entry scripts are
preserved under [`.archive/`](../../.archive/).

*Video: claude-supervised M5 demonstration — link pending.*

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
