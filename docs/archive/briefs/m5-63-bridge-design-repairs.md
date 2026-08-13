# m5-63 — the bridge-design repairs, and the bridge-liveness ruling

    gate:                M5
    agent:               interface
    goal:                Close the three document items m5-61 and m5-62 handed back, including the one that leaves the project with no addressable bridge-liveness instrument.
    invariants_touched:  none
    inputs:
      - docs/reports/m5-62-torque-off-bridge-slot.md — the three items, with the text ready for two of them
      - docs/reports/m5-61-warn-sender.md — the warning-node finding and where it was traced to
      - docs/interfaces/opcua-nodes.md §11.2b — SD1 to SD10, already ruled
      - docs/interfaces/bridge-design.md
      - bridge/EVIDENCE_TORQUE_OFF_SLOT.md
    deliverable:         docs/interfaces/bridge-design.md, and a §11.8 entry if the liveness question needs one
    done_when:           The stale count is corrected, the read slot exists with SD5 on its row, and the bridge-liveness question has a stated answer or a stated owner.
    forbidden:
      - writing code, or editing outside docs/interfaces/
      - re-deriving SD1 to SD10. They are ruled; this brief records their consequences in the bridge document
      - claiming or implying an achieved PL, Category, SIL or PFH

---

## 1. Two repairs, text already written

m5-62's brief sent it to `bridge/` for these; the only `bridge-design.md` is
yours, so they come back here. m5-62's report carries the text ready to place.

- **line 34 says the writer carries four tags.** It has been **eleven** since
  m5-49.
- **the read slot** for `Forklift/Safety/TorqueOffDemand` →
  `/forklift/safety/torque_off_demand`, with **SD5 written on the row**: stale,
  silent or never-resolved is *not* torque-off. That row is where a later
  reader will look, and SD5 is the rule most likely to be "corrected" by
  someone who has not read why it is deliberate.

Also record what m5-62 built, because it is a property the document should
carry rather than a fact buried in evidence: the group declares **no inputs**,
so the derived write allowlist gains **zero keys** — MR1 holds by construction,
not by promise. And the leaf is **optional**, so a CPU without tomorrow's delta
connects, logs the absence by name, and publishes nothing.

## 2. The ruling that matters — bridge liveness

**`Link/BridgeLinkOk` is not addressable on the controller in force**
(`BadNoMatch`, read directly). That leaves **the raw heartbeat as the project's
only bridge-liveness instrument**, and m5-62 correctly refused to rule on it.

Decide, and say which:

- the node is specified and simply not built, so the fix is a TIA step and this
  is a **`plc/` item** with a named owner and a place in the queue; or
- the specification changed under it and the heartbeat *is* the instrument, in
  which case say so and **state what a consumer must do with it** — a raw
  counter is not a liveness verdict until someone rules what "stale" means for
  it; or
- it is a naming drift and the real node is elsewhere, in which case name it.

**Do not leave this as an observation.** The owner has a TIA session tomorrow
morning; if this is a TIA item it can ride along, and if it is not, saying so
now costs nothing.

## 3. One item that is NOT yours, recorded so it is not re-opened

`ForkliftWarning.ForkliftWarningFieldOccupied` reading `True` with both fields
clear was traced by m5-62 and is **not** an interface or bridge defect: with no
bridge process running, every `Input/`-class node sits at its start value, so
the `True` means *not yet written* — exactly like `ForkliftObstacleInStopZone`.
It belongs to run composition and to `hmi/` (**render age, not value**).

If a one-line note in the document would stop the next reader rediscovering it
as a defect, add it. Do not fix it here.

## 4. Working discipline

- Read `docs/LESSONS.md` first.
- **Do not commit.** The orchestrator commits by pathspec.
