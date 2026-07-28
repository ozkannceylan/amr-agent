# TODO

Open items only. M3 closed 2026-07-28; everything it consumed is deleted from
here and lives in `docs/reports/` and `bridge/evidence/`.

## owner — M4 entry, the tool question ADR 0007 requires first
- Does this install run an F-CPU on PLCSIM Advanced V7? Check, in TIA: STEP 7 Safety Advanced V21 licence present; 1513F-1 PN addable from the catalogue; an empty F-project compiles, downloads to a PLCSIM instance and reaches RUN with its F-runtime group executing; what F-I/O the catalogue offers and whether PLCSIM accepts it. The answers are the input to M4's first brief — the tool rules, not the spec (phase-0 lesson). **No M4 brief until these are answered.**
- One watch-table capture at a CPU cold start with the bridge down, showing all seven Group 1 inputs at their DB start values, closes verifier findings 1, 2, 8 and 9 at once. M4 performs CPU restarts anyway, so take it then.

## owner — carried, small
- Clock: not durable. w32time was resynced 2026-07-27 but the service does not stay started, and the residual ~350 ppm re-accumulates to tens of seconds per day. Before any measurement run: elevated `Set-Service w32time -StartupType Automatic; Start-Service w32time; w32tm /resync`.
- `BELT_SPEED_MIN`/`MAX` are design values at ±1.00 m/s with no measured drive maximum behind them (m3-27 open question). Confirm against the achievable cell speed and record the source.

## plc
- **F6** (§B2.12 row 22): `PresenceOnTimer.PT` reads `T#100MS` before a CPU restart and `T#0MS` after, in five captures. Likely the §6.5-blessed conditional call site — at boot `range = 0.0` is implausible, `rangeValid` is FALSE, the presence call never executes, so PT shows the DB start value until the first valid range. Diagnose against §6.5 and close or escalate.
- SPEC §12 item 7 (rewrite-on-restart) is now satisfied by delivered bridge behaviour — close the item.
- T4.11's reaction path needs re-recording with a per-session CSV (the facility now exists). **T4.11b is blocked** on the fault-injection facility below. Neither blocked M3's closure: both concern belt-feedback plausibility, a defence added during the gate and absent from the four exit criteria.

## bridge
- Fault injection (SPEC §12 item 6, blocks T4.11b): an opt-in mode that writes a nominated `DemoCell/Input` Real as NaN, inf or out-of-window, and that cannot be enabled by accident in an evidence run.

## interface (fold together)
- `bridge-design.md` §8.1 has no restart-detection row although the shipped code's log line cites it, and §2's cycle description predates the once-per-cycle heartbeat read-back.
- `opcua-nodes.md` §2 still heads the fleet-facing folder tree with `http://DemoCell`; fix it in the same brief that chooses the M6 interface name, since ADR 0006 derives the URI from that name.

## bridge or interface, from the verifier
- `EVIDENCE_LATENCY.md` §B2.9 labels "build B" as the three-delta build, which three owner captures contradict (the belt-plausibility and case-D constants and statics are absent at 14:04 and 14:17). No figure moves; the label does.

## safety-spec
- m2-04 SRS reconciliation, from m2-03's findings: SRS §4 gate references must match the **ADR 0007** order (not ADR 0004's); SF-08 carries an architecture claim beside its PL c or states the inheritance; SF-03's bumper latch appears in §2's no-auto-resume list; AT-01 gains the at-rest sub-test SC-02 observes. One brief — the four items are one document's consistency.

## sim (deferred, visual only)
- Cell reskin from harvested assets. Research (2026-07-27, session scratchpad) recommends ARIAC 2025 conveyor and break-beam visuals onto the existing joints, optionally inside Fuel `Depot` (CC-BY 4.0). The `/cell/...` topic contract and the node model must not change. **Licence blocker first**: `ariac_gz`, the package holding every mesh, declares "TODO: License declaration" and its repository has no top-level LICENSE, so clarify terms with the maintainers before any mesh enters this repository. Adopting ARIAC's own plugins is out of scope — it would add a dependency and change the signal contract, which needs an ADR.

## publication
- Repository is public-ready and pushed; visibility is the owner's to flip. MIT licensed, the third-party infrastructure detail is redacted from the working tree (earlier revisions remain in history by the owner's decision, taken while private), the full-desktop capture is removed, and the agentic working model stays as part of the portfolio story (owner's ruling). Remaining, low: `docs/adr/0007` names a hosting provider and region — an accepted ADR is never edited (CLAUDE.md §8), so closing it needs a superseding ADR or the owner accepting it as-is.

## carried forward, by gate
- plc/owner (later gate): suppress `DataBlocksGlobal` DB-level exposure by clearing each DB's "Accessible from HMI/OPC UA" attribute (`opcua-nodes.md` §9.8 open item).
- interface (M6): the fleet-facing server interface's **name** is a contract decision, since ADR 0006 derives the namespace URI from it — chosen deliberately at briefing, never discovered in TIA.
- fleet (M7): confirm the handshake timeout constants.
- sim (M5): resume the parked navigation scenario (`sim/scenarios/DEFERRED.md`).
- plc (M8/M9): AT-08 STOP sub-case, SF-03 latch-list wording, no-auto-resume of interrupted handshakes, dedicated F-I/O for SF-05/06/07.
