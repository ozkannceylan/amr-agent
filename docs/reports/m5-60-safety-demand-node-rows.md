# m5-60 — the two SLS/SS1 demand leaves, ruled

    brief:               docs/briefs/m5-60-safety-demand-node-rows.md
    status:              done
    invariants_touched:  none. See "the one thing the owner should look at" below —
                         it is an ADR *clarification* request, not an invariant change,
                         and nothing waits on it.

## The ruling, in the form step 7 asks for it

`docs/interfaces/opcua-nodes.md` §11 is now **six nodes**. Step 7 of
`plc/forklift/TIA-FIX-PROCEDURE.md` reads back:

| Leaf (`DemoCell/Forklift/Safety/…`) | S7 / OPC UA type | *Accessible* | *Writable* | Start value |
|---|---|---|---|---|
| `SpeedMonitorDemand` | Bool / `Boolean` | ✔ | **✘** | **`FALSE`** |
| `TorqueOffDemand` | Bool / `Boolean` | ✔ | **✘** | **`TRUE`** |

Leaf name = the F-side tag name exactly, no prefix, in `ForkliftSafetyMirror`
(CLAUDE.md §9; the §11.2 ruling extended, not re-argued). **The requested names in
the fix procedure and the ruled names agree character for character**, so nothing
in chunks AD–AF changes and step 7 is unblocked as written.

`SpeedMonitorDemand`'s start value is the one in this group **not** chosen for the
fail direction, and the row says why: the monitor arms on the first fresh reading
and its latch cannot be set before that, so the F-side truth at every CPU start is
`FALSE` (§11.9 Q16's no-source signature). Asserting a demand the F-program has
not made is the same defect as a false clear, in the other direction.

## The part that mattered — the required reaction, in §12's own voice

New **§11.2b**, ten rules **SD1–SD10**, in the shape §12's **M**/**E**/**V**/**PS**
and §13's **W** tables take. The reactions are stated, not left to be chosen:

- **SD1** — `SpeedMonitorDemand` has **no vehicle consumer, no topic and no bridge
  slot**. The reaction is the PLC's permissive, formed from F-data directly; what
  reaches the vehicle is the consequence (permissive drops, setpoints `0.0`,
  envelope non-permissive), through **no stop topic of its own** (§12.7 PS6 again).
- **SD2–SD4** — on an **observed `TRUE`** the vehicle's torque-off stand-in latches
  open: no further forwarded command, traction terminal driven to a standing `0.0`,
  steer and fork **held at their last forwarded values** (silence is a standing
  order — LESSONS 2026-08-04). While it stands the envelope **has no vote**;
  authority returns only on an observed `FALSE`, and motion then needs a fresh
  command.
- **SD5** — **stale, silent or never-resolved is NOT torque-off.** This is the one
  place in the document where absence is not the non-permissive reading, and it
  carries three separate reasons (invariant 2; the controlled stop already exists in
  the envelope gate's freshness rule; STO is asserted, never inferred). Stated
  explicitly as the **deliberate opposite** of §13.2 **W1**'s silence-⇒-`TRUE`
  warning slot, so the asymmetry cannot be read as an omission.
- **SD6** — SD5 does not weaken §11.6. The start value answers *what the server
  holds before the first copy*; SD5 answers *what a consumer does with a value it
  never received*. Consequence written out: **at every CPU start the vehicle is
  torque-off until a monitored reset**, which is no-auto-resume arriving at the plant.
- **SD7** — a **demand** crosses the seam, never a speed: no limit, no margin, no
  reading, no value-that-was-exceeded. §11.7 gains a refusal row naming them.
- **SD8** — no consumer recomputes, merges or infers; no display merges the two new
  latches with each other or with the two process latches.
- **SD9** — the stand-in labelling, on the rows themselves: the consumer is
  process-side Python simulating the *effect on the plant* of a hardwired onboard
  inhibit this plant does not have, over an F-input path built on a standard DB.
  **No PL, Category, SIL or PFH is claimed, achieved or implied; no stopping time or
  distance is claimed.**
- **SD10** — with the bridge down, the F-layer's reactions still execute in the CPU
  (which is what roadmap M5 item (b) is about, for SF-01/07/08); **the simulated
  plant's torque removal does not**, because the bridge is the only path to a
  hardware-free plant. No run may claim an SS1 plant reaction with the bridge down.

Plus the positive-control rule: once a consumer can make the plant deaf, *the
vehicle did not move* is evidence only beside a command that moves it in the same
run (LESSONS 2026-08-06), stated as a property of the interface, not only of a test.

## The one thing the owner should look at (not blocking)

**`TorqueOffDemand` is the first mirror any consumer acts on**, so two sentences in
§11 stopped being true and were narrowed rather than left standing: *"they feed no
logic anywhere in this project"* is now true of **five of the six**, and §11.3's
"leaf of the data flow" is now scoped to **inside the CPU**. What did not change:
no client may write any of the six (MR1), no client write can create, prevent or
clear a safety reaction (MR2, both reasons intact), and no PLC logic reads a mirror.

**ADR 0014 D4 enumerates seam (a) as the envelope plus the mode down and the
vehicle's report up.** This is a third content item on that seam. It is admitted
because it is a **demand Bool, not a motion value** — D4's own sentence is satisfied
— and because `plc/forklift-safety/SPEC.md` §11.7, SRS SF-11 and ADR 0011 D5 already
place the reaction at a labelled stand-in. What no document yet records in one place
is that **a modelled safety reaction is stimulated across the process network because
the plant has no wire to carry it**. §11 now says so (SD9, SD10) and §11.8 item 8
asks whether that should also be an ADR clarification. **It is not implemented as an
invariant change and nothing waits on it.**

## files_changed

| File | What |
|---|---|
| `docs/interfaces/opcua-nodes.md` | §11 preamble (six nodes, the stand-in paragraph); §11.2 two rows + the `Ss1Demand`-is-not-a-node ruling; **new §11.2b SD1–SD10**; §11.3 DB row, two ownership rows, the narrowed leaf-of-the-data-flow claim; §11.4 MR1/MR2/MR6; §11.5 click path; §11.6 two start values + the source-truth string; §11.7 two refusal rows; §11.8 seam text, counts, items 2 and 4 rewritten, new items 8 and 9. Swept by subject: §10.1's bridge row, §10.3's tree and total, §10.11's row, §12.2, §12.7, §12.13's record row, §13.1, §13.3 — **interface total 47 → 49** |

Nothing outside `docs/interfaces/` was written. Nothing committed, no branch, no
dependency. `plc/`, `agv/`, `bridge/`, `hmi/`, `docs/safety/` and `docs/adr/` were
read only.

## Requests — none blocks tomorrow's session

| # | Request | Owner | Blocking |
|---|---|---|---|
| 1 | **`bridge-design.md` §2.1 and §4.11**: one read slot on `Forklift/Safety/TorqueOffDemand` → `/forklift/safety/torque_off_demand` (`std_msgs/Bool`, no inversion), with **SD5 written on the row** — no silence rule, no synthesised value, no freshness window, the deliberate opposite of row 23's W1 — and **no slot for `SpeedMonitorDemand`** (SD1). Requested rather than taken: the brief reserves the bridge half | `interface`, bridge-half brief | No; blocks AT-11 |
| 2 | **`bridge-design.md` line 29–35 is stale independently of this ruling**: it says *"the writer's four tags live in a DB the OPC UA server does not expose"*. `SafetyInputStandIn` has carried **eleven** members since m5-49 (4 + 7). The claim it supports — the server does not expose the DB — is unaffected; the count is wrong | same brief | No |
| 3 | **`plc/forklift/SPEC.md`**: two present-tense statements now incomplete — *"the four mirror tags carry the fail-safe start values `TRUE`, `TRUE`, `TRUE`, `FALSE`"* (§13.5-area) and its §9 watch-table note. Six tags, `TRUE, TRUE, TRUE, FALSE, FALSE, TRUE`, §11.6's order. The §7-fence "5 SCL statements" passage reads as a dated record of that delta and needs no edit | `plc/` | No |
| 4 | **`plc/forklift-safety/SPEC.md` §6.4 / §11.8**: the pointer that document asks for — the pair is ruled, leaf = tag name, `Forklift/Safety/`, *Accessible* ✔ / *Writable* ✘, start `FALSE` / `TRUE`, and the required consumer reaction is `opcua-nodes.md` §11.2b | `plc/` | No |
| 5 | **`docs/TODO.md`**: this closes the F1 interface half. The m5-11 §12 residue (four unspecified reactions) is **not** closed by this brief — §11.2b is the pattern it should be closed in | orchestrator | No |
| 6 | **Owner / `arch-docs`**: the ADR clarification of §11.8 item 8 | owner | No |

## open_questions

1. **Does the owner want the seam-(a) content question written as an ADR
   clarification?** §11 states the fact and its labelling; an ADR would make it
   re-checkable. Nothing waits on the answer.
2. **`hmi/` inherits two display candidates.** Whether either gets a lamp is
   `hmi/`'s; SD8 and SD9 bind any display that takes them (no merged lamps, the
   stand-in named in the caption).
3. **The two leaves remain design values until read back out of the tool.** Chunk
   AE step 49 (six leaves, no `_1`) and step 59 (refused write with its status code)
   are the read-back; no gate criterion may rest on them before then.

## next_suggested

Run the TIA session front to back — step 7's gate is answered — and issue the
`bridge-design.md` half (request 1) in the same round as the bridge's `WARN`-sender
brief, since AT-11 needs both.
