# m5-63 — the bridge-design repairs, and the bridge-liveness ruling

    brief:               docs/briefs/m5-63-bridge-design-repairs.md
    status:              done
    invariants_touched:  none

## The ruling first, because it was the reason for the timing

**`Link/BridgeLinkOk` is not an unbuilt node and not naming drift. It is a scope
reading, nothing needs to ride along in the TIA session, and saying so costs
nothing.** Every document involved already agreed; none of them said it in the
place a reader hits when the probe returns `BadNoMatch`.

- `BridgeLinkOk` is a **§9 cell-group node**, published by the M3 demonstration
  cell's standard program (`plc/demo-cell/SPEC.md` §6.1, §7). It is one of the §9
  nodes `bridge-design.md` §2.1 already records as unreachable on the `safe_amr`
  CPU — the same `BadNoMatch` every other cell node returns, for the same reason.
- The **forklift program forms the same verdict and publishes it nowhere by
  design**: `#bridgeLinkOk` is a Temp inside `FB_ForkliftTeleop`, marked *"Temp,
  no node"* at its own call site (`plc/forklift/SPEC.md` §7), and
  `opcua-nodes.md` §10.11 refuses *"a second bridge heartbeat or a second
  bridge-link verdict"* **by name**, already recording that on this build the
  verdict is published on no node at all. §11.7 refuses one for the mirror group.

So it is **not a `plc/` item**: creating such a node would first require reversing
§10.11's refusal, which is an interface decision taken in a document, not a leaf
added under time pressure at the tool.

**What the ruling therefore owes, and pays: the raw counter is the instrument, and
a counter is not a verdict until someone says what to do with it.** New
`bridge-design.md` **§7.5**, rules **B1–B7**, binding every client that reads
`Link/BridgeHeartbeat` — `hmi/`, the monitoring service, any diagnostic tool:

| | |
|---|---|
| **B1** | The datum is the counter; the verdict is the reader's own. **No client may present its verdict as the PLC's** — no lamp captioned *"PLC: link OK"*. The PLC's verdict still acts and is visible only through its consequences (`ForkliftResetRequired`, `BridgeLinkLostLatch` in the watch table) |
| **B2** | Change detection only — inequality against the last value this reader saw. Never subtract, never `+1`, never assume ordering across the wrap or a bridge restart |
| **B3** | The verdict is **`FALSE` until the counter has been seen to change** in this reader's session. *Not yet proven stale* is not *alive* (LESSONS 2026-07-28), and the latch is cleared when the session ends, never carried across one |
| **B4** | The stale window is the reader's **own named constant** — at least three of its own poll periods — **never shared** with `HEARTBEAT_STALE_TIME` or `HMI_STALE_TIME` (the §10.8 P4 precedent) |
| **B5** | **Render the age, never the value.** A stale reading renders as stale, not as the last verdict |
| **B6** | It qualifies attributability and **gates nothing** — and in particular is **never wired into the torque-off consumer**: a silent link is not torque-off (SD5) |
| **B7** | An advancing counter says the bridge wrote recently and **nothing about the plant**: §7.3 cases D and E are undetectable from it by any client |

## The two repairs

1. **Line 34's count.** `four` → **eleven**, verified independently against
   `bridge/STANDIN-WRITER-DESIGN.md` §1.1 and `plc/forklift-safety/SPEC.md` §7
   (eleven distinct `SafetyInputStandIn` members), with §1.1 named as the
   authority so the number has one home. **The same sweep found the stale scope
   the string search would have missed** (LESSONS 2026-07-27): the sentence above
   it called the writer the stand-in for *"three simulated safety-input
   channels"*, which the same m5-49 delta voided. Both are repaired in one edit.

2. **The read slot exists, with SD5 written on its row** — new **§4.12**, row
   **24**: `Forklift/Safety/TorqueOffDemand` → `/forklift/safety/torque_off_demand`,
   `std_msgs/Bool`, no inversion, polled in row 8's phase. It landed as its own
   subsection rather than inside §4.11, because §4.11 is the envelope group's and
   §11 is a different node-model section — one section, one group. The row's rule
   block states that stale, silent or never-resolved is **not** torque-off, gives
   the three non-interchangeable reasons, and says outright that **a later reader
   deleting the asymmetry would be re-introducing a defect, not tidying one**.
   §4.12 also carries what m5-62 built and the document should own: **no inputs,
   so the derived allowlist gains zero keys — MR1 by construction**; the leaf
   **optional**, the one node in the document a connect may survive missing, with
   the tolerance bounded three ways; `SpeedMonitorDemand` given **no slot at all**
   (SD1); and the positive-control rule the pair makes necessary.

## The item that is not mine, recorded so it is not re-opened

One paragraph in §4.11, under row 23: `ForkliftWarningFieldOccupied` reading
`True` with both fields clear is **not an interface or bridge defect** — with no
bridge running, every `Input/`-class node sits at its start value, so the `True`
means *not yet written*, exactly like `ForkliftObstacleInStopZone`'s. It names
the two owners (run composition; `hmi/`, **render age, not value**) and points at
the heartbeat as the instrument that separates the two readings. No fix attempted.

## What else the independent verification turned up, and I repaired in place

The brief's enumeration was a starting point (LESSONS 2026-07-27, 2026-07-29):

- **§2.1's configuration table was two builds stale.** It said the observed counts
  *"exclude the warning slot, which is ruled but not yet built"* — m5-58 built it
  on 2026-08-06. The table now carries the warning row and the **committed
  configuration** row, each labelled with **which server produced it** (live CPU /
  test double / derived-and-observed-one-short) and quoted as the tools printed it
  (LESSONS 2026-07-27 on counts).
- **The document called §13 part of the envelope group; the config and the bridge's
  own log never did.** Ruled explicitly: one node-model section, one group — five
  groups now (cell, forklift, envelope, warning, safety), and the opening table,
  the authority line, the §4 row index and the §5 update model all follow.
- **G5 claimed "one link verdict `BridgeLinkOk`"** as if the node existed
  everywhere. Rewritten to *one verdict per consumer formed from the one counter*,
  published as a node only where the §9 program runs.
- **The interface's node count read 47**; §13.3 says **49**. Corrected.
- **§10's test-double row and §12 items 16 and 17** described a double that does
  not serve §12, §13 or §11. It has served all three since m5-58 and m5-62, the
  mirrors in three shapes. Items closed with their evidence; **item 18** records
  this brief's ruling and **item 19** records the one thing §4.12 has never had —
  a live run, which belongs to the session that applies chunks AD–AF.
- **`opcua-nodes.md`, the requesting document, updated in the same change**
  (LESSONS 2026-07-26): §11.8 **item 4 closed** by the slot it asked for, §13
  **item 1 closed** by m5-58, §11.6 now records `BadNoMatch` as the **measured**
  status with its probe and date (m5-62's request 3), and §9.7 and §10.11 carry
  the liveness ruling with a pointer to §7.5.

SD1–SD10 were not re-derived; §4.12 records their consequences and cites them. No
PL, Category, SIL, PFH, stopping time or stopping distance is claimed or implied
anywhere in either file.

## files_changed

| File | What |
|---|---|
| `docs/interfaces/bridge-design.md` | The deliverable: scope-note count and scope, §2.1 groups and configuration counts, §3 read set, §4 row index, §4.6, §4.10, §4.11 (heading, row-23 status, the start-value note), **§4.12 new**, §5 update model, §6.2, **§7.5 new (B1–B7)**, §10, §12 items 16–19 |
| `docs/interfaces/opcua-nodes.md` | §9.7 scope paragraph, §10.11 row, §11.6 measured `BadNoMatch`, §11.8 item 4 closed, §13.3 item 1 closed |
| `docs/reports/m5-63-bridge-design-repairs.md` | This report |

Nothing outside `docs/interfaces/` and this report was written. Nothing committed,
no branch, no dependency added. No process was started and no server was contacted:
every measurement quoted here was taken by m5-44, m5-58 or m5-62 and is cited to
the evidence file that holds it.

## open_questions

1. **§4.12 has never run against the controller.** Every figure behind it is
   double-only and the evidence file says so twice. The first live run belongs to
   the session that applies chunks AD–AF, and **no gate criterion may rest on the
   double runs** until then (`bridge-design.md` §12 item 19).
2. **B4 leaves each reader to derive its own window**, deliberately — but no
   reader has one yet. `hmi/` is the first that will need it, and the derivation
   is from *its* poll period, not from the bridge's 50 ms.
3. **§4.10's never-touched count and §4.12's five unread mirrors are two rules
   with two reasons**, now stated as such. If a later brief merges them into one
   "nodes the bridge does not touch" figure, the evidence rule behind the five
   disappears into an ownership rule that does not imply it.

## next_suggested

Run the TIA session for chunks AD–AF; the interface half is now ready for it, and
nothing on the liveness question waits on that session.
