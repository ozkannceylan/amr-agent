# Report m5-17 — OPC UA nodes for the motion envelope, the drive mode and the emergency request

```
brief:               docs/briefs/m5-17-envelope-mode-nodes.md
status:              done
files_changed:       [docs/interfaces/opcua-nodes.md (new §12, and two
                      sentences added inside §12 that name §10.3's and §11.8's
                      now-stale interface totals)]
invariants_touched:  none. Invariants 1, 4, 5, 6, 9, 10 and 11 all constrain
                     the section and are cited in it; none is amended and no
                     ADR proposal is raised.
open_questions:      see the list below and §12.13 items 1-8
next_suggested:      m5-16 (PLC standard program spec) can be written directly
                     from §12; the two interface follow-ups (bridge-design.md
                     signal group, §10/§11 pointers) are independent of it.
```

---

## What was written

`docs/interfaces/opcua-nodes.md` **§12 — The autonomy envelope, the drive mode and the operator's
process stop (M5)**, in the §10 pattern: preamble, direction rules, folder/DB/access layout, one
subsection per node group, start-value rule, ROS 2 topic map, TIA click path, a deliberately-absent
table and an open-items table.

**Nine nodes, four new folders under `Forklift/`, four new global DBs (one per folder).** No existing
DB gains a member, for §10.3's and §11.3's reason: the M3, M4 and §11 groups stay byte-identical, so
no offset that current watch tables and evidence depend on moves.

| Node (`Forklift/…`) | Direction | Type | Writer | Start value |
|---|---|---|---|---|
| `Mode/HmiDriveModeRequest` | HMI → PLC | UInt / UInt16 | HMI (client write) | `0` = None |
| `Mode/ForkliftDriveModeActive` | PLC → HMI **and** PLC → vehicle | UInt / UInt16 | PLC | `0` = None |
| `Envelope/ForkliftMotionEnable` | PLC → vehicle | Bool | PLC | `FALSE` |
| `Envelope/ForkliftSpeedCeiling` | PLC → vehicle | Real / Float | PLC | `0.0` |
| `Envelope/ForkliftEquipmentPermit` | PLC → vehicle | Bool | PLC | `FALSE` |
| `Vehicle/ForkliftVehicleModeApplied` | vehicle → PLC | UInt / UInt16 | bridge (value owner: `agv/`) | `0` = None |
| `Vehicle/ForkliftVehicleHeartbeat` | vehicle → PLC | UInt / UInt16 | bridge (value owner: `agv/`) | `0` |
| `ProcessStop/HmiProcessStopRequest` | HMI → PLC | Bool | HMI (client write) | **`TRUE`** |
| `ProcessStop/ForkliftProcessStopActive` | PLC → HMI | Bool | PLC | **`TRUE`** |

Every start value is the **non-permissive** one and says so **in its own row**, not in a preamble, so
a later edit that moves a row cannot lose it. Seven of the nine happen to be the type's zero; the two
`ProcessStop/` values are `TRUE` deliberately, in the standing of §10.9's `ForkliftObstacleInStopZone`
and §11.6's three `TRUE` mirrors.

---

## For the m5-16 PLC brief — exactly what the standard program must declare

**Four new global DBs**, per-tag *Accessible from HMI/OPC UA* ✔ throughout, *Writable from HMI/OPC UA*
as marked. Names are contract identifiers and are written correctly the first time — no DB is renamed
once the server interface binds it (LESSONS 2026-07-30).

| DB | Members (S7 type) | *Writable* |
|---|---|---|
| `ForkliftMode` | `HmiDriveModeRequest` (UInt), `ForkliftDriveModeActive` (UInt) | ✔ on the first only |
| `ForkliftEnvelope` | `ForkliftMotionEnable` (Bool), `ForkliftSpeedCeiling` (Real), `ForkliftEquipmentPermit` (Bool) | ✘ on all three |
| `ForkliftVehicle` | `ForkliftVehicleModeApplied` (UInt), `ForkliftVehicleHeartbeat` (UInt) | ✔ on both (the bridge writes them) |
| `ForkliftProcessStop` | `HmiProcessStopRequest` (Bool), `ForkliftProcessStopActive` (Bool) | ✔ on the first only |

**Four new interface folders** under `Forklift`, beside `Hmi`, `Input`, `Output`, `Status`, `Link`
and `Safety`: `Mode`, `Envelope`, `Vehicle`, `ProcessStop`. Leaf names are the BrowseNames above,
unchanged, so the document, the TIA export and the SPEC tag list diff three ways (CLAUDE.md §9).

**What m5-16 must specify that this document deliberately did not** — each is a process decision, and
§12 marks each as an interface expectation rather than making it:

1. **The mode arbitration**: how `ForkliftDriveModeActive` is formed from `HmiDriveModeRequest`, the
   two link verdicts and the standing latches; the affirmative-action edge on entering `Autonomous`
   (§12.3); and **M6**, that `ForkliftTeleopActive` and `ForkliftMotionEnable` are never both `TRUE`.
2. **The envelope's formation**: the terms behind `ForkliftMotionEnable`, the value and terms behind
   `ForkliftSpeedCeiling` (bounded by `TRACTION_SPEED_MAX`, §10.12 item 4), and the equipment terms
   behind `ForkliftEquipmentPermit` — **an empty conjunction at M5, stated as such and not written as
   a literal `TRUE`** (§12.5 **Z4**).
3. **A named stale-window constant for `ForkliftVehicleHeartbeat`**, its own, never shared with
   `HMI_STALE_TIME` or `HEARTBEAT_STALE_TIME`, plus the `SeenAlive` boot-polarity latch (**V1–V4**).
4. **The mode-disagreement reaction** and its own named delay constant (§12.13 item 7); the reaction
   may never be to adopt the vehicle's reported value.
5. **The process-stop latch, its clearing condition and its reset arming** (**PS1–PS6**), including
   that `ForkliftResetRequired` gains this cause and stays the single "a reset is pending" answer.
6. **The three §10.6 setpoints are unchanged** — same three assignments, same mandatory `ELSE` to
   `0.0`, no new branch and no second writer (§12.9 **C2**).

---

## The three constraints the brief called out, and how each was met

**1 — The envelope is low rate and is not a velocity channel.** `ForkliftSpeedCeiling` is the name,
and four independent things stop it reading as a setpoint: it is a **ceiling**, not a `Ref` — **E3**
reserves the `Ref`/`Cmd` suffixes for §10.6's three actuator setpoints and no node in §12 carries
one; it is **unsigned**, bounding magnitude in either direction, while every setpoint in this model
is signed, so the distinction survives a reader who looks only at the value; **E1** states the
checkable test — *a consumer reading this group at 2 Hz and one reading it at 20 Hz must behave
identically apart from latency*, and any node for which that is false does not belong in the group;
and the row itself says a ceiling of `0.80` does not ask for `0.80` m/s. **E4** carries ADR 0011 D3's
velocity-smoother consequence to the consumer that must obey it.

**2 — Station permit, not zone permit.** The node is **`ForkliftEquipmentPermit`**, in
`Forklift/Envelope/`. It cannot be misread as traffic or reservation for four reasons, all written
into §12.5: the name says **equipment**, a thing, not space; its definition is a question —
*"is the equipment I own ready for you to act on it?"* — set beside the fleet manager's question,
*"may you be here?"*, in a two-row table of datum / owner / question taken from ADR 0012 D1; **Z1**
forbids any document, node name, message field, caption, lamp or spoken line from merging them, in
§11.4 **MR7**'s shape; and **Z3** rules the granularity as one Bool per vehicle, derived from the
PLC's **own station handshake** and never from an order, a route or a destination, so the M6 reader
cannot reach traffic through it even by accident.

**One finding worth the orchestrator's attention.** The word *zone* is already spent three times in
this project on three different things — `Forklift/Safety/ZoneStopDemand` (the F-side marked zone),
`Forklift/Input/ForkliftObstacleInStopZone` (the lidar's forward stop field), and the fleet manager's
zone reservation at M6. A fourth use would have made the word meaningless in the one document a
reader consults to find out what a name means. That is recorded as **Z2** and is a second, independent
reason the ADR 0012 ruling was right.

**3 — Cold start is non-permissive, per node.** Every group table carries a **Start value** column and
every Meaning cell ends with a bolded *"Cold start … is the non-permissive value"* sentence saying why.
The start values are deliberately **not** collected into a §10.9-style table: a value that lives in
its own row travels with that row, and a value written in two places goes stale in one of them. §12.8
carries the rule and the qualification rule only, and restates no value.

---

## The other four asks

- **Drive mode request and readback are separate nodes with stated directions**, and a third node —
  the vehicle's — is a different datum again. `ForkliftDriveModeActive` is named as the single
  authoritative answer to *"what mode is the machine in"* (**M1**), read by the HMI **and** the
  vehicle from the same node; **M2** forbids a client rendering its own request as the machine's
  state; **M3** makes each consumer's copy read *unknown* when its own link verdict is false, so a
  stale belief is visibly stale; **M4** makes the vehicle's `ForkliftVehicleModeApplied` a readback,
  never a second answer, with a disagreement a fault rather than a choice.
- **The HMI emergency request is a process-stop request**, `HmiProcessStopRequest`, with its latch
  `ForkliftProcessStopActive`, cleared only by the existing `HmiResetRequest` on its rising edge under
  §10.8 **P6**'s per-link-session arming, testing the live world and never the latch itself. What it
  is **not** is one sentence: not a safety function, not an emergency stop, not a protective stop; it
  does not reach the F-layer and cannot create, prevent or clear an F-latch (invariant 1, ADR 0010
  D6(b), §11.4 MR2/MR3). The word *emergency* appears in no name. The **display half** of ADR 0010
  D6(b) needs no new node — it is the four §11 mirrors, untouched.
- **The vehicle-side state the PLC needs back** is exactly two values: the mode the gate node is
  applying, and a liveness counter for the gate node itself. §12.6 states plainly what they do not
  buy — the PLC can **notice** that its envelope is not being applied; it cannot enforce it, and no
  node in this model does. That is the judge review's finding 4(b) written as an interface fact
  rather than left as an inflation.
- **Nothing presumes the m5-03 verdict.** No node in §12 is on the F-input path whichever way that
  verdict falls, no node is written or read by the F-runtime group, and the safe scanner channel is
  **not named** — §12.12 records the absence and says the name waits on m5-03.

---

## Open questions

1. **`bridge-design.md` must carry this signal group before any bridge work on it** — the configured
   signal set (§2.1), the signal map (§4.7–§4.9 shape), QoS rows, the writable set gaining the two
   `Forklift/Vehicle/` nodes, and the first **topic-carried `UInt16`** (the bridge has generated one
   internally as its heartbeat, never carried one from a topic). Its §1.1 no-logic rule is unchanged.
   That file is in this agent's write scope but is a **second deliverable**, so it is requested as its
   own brief in the m4f-05 shape rather than taken here.
2. **Four pointer edits in §10 and §11**, tabulated in §12.13 so a follow-up brief can be written from
   the table: §10.1's two "what each client writes" rows; §10.3's folder tree, §10.8 **H1**'s "all
   six" and §10.7's `ForkliftResetRequired` cause list; and **§10.3's and §11.8's interface total of
   `37`, which is now `46`**. The set-scoped counts beside them ("18 nodes", "exactly 4") stay true
   and need no edit.
3. **How an M5 navigation goal is commanded is unanswered**, and no node here answers it. A pose
   target on the PLC would make the standard program a navigator and collides with invariant 5. This
   needs an owner decision at m5-10 / m5-11 / m5-14 — and any answer that routes a goal through the
   PLC is an invariant question, not an interface one.
4. **One enable/start request that serves both modes.** §12.3 carries a stated conflation: with no
   separate autonomous enable, the operator's selection of `Autonomous` is the affirmative action.
   §10.12 item 7 already asks for an `HmiStartRequest` for the M4 conflation; **one node should answer
   both asks**, and a second, autonomy-only enable would be the wrong answer. Owner decision — it
   moves a node count, a DB, a start value and the HMI's write set together.
5. **Everything in §12 is a design value until read back out of the tool** (§12.11 step 6), including
   one **attempted and refused write** to a `Forklift/Envelope/` node with its status code, which is
   the only evidence that "a permission is not a command" is enforced by the server rather than by
   convention.
6. `plc/forklift/SPEC.md` and `hmi/` both need to be told: the SPEC gains the tag list above and the
   items in the m5-16 section, and `hmi/`'s v1 documents describing an "all six nodes every cycle"
   write set are as-built records of v1 — **HMI v2 writes eight** (m5-14). Neither file is in this
   agent's write scope.
7. `bridge/test_double/plc_test_double.py` carries "18 nodes, of which the bridge touches 12" as a
   comment. It is the M4 double and is not wrong today; it will need the new slots when open item 1
   lands. Recorded so the bridge agent does not discover it at run time.
