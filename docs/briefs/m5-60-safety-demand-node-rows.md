# m5-60 — rule the two new safety demand leaves

    gate:                M5
    agent:               interface
    goal:                Rule the node rows for the two SLS/SS1 demand leaves the F-program already produces but nothing publishes, so the owner's TIA step 7 is unblocked.
    invariants_touched:  none. Invariant 10 is the point of this brief — each datum gets exactly one owner.
    inputs:
      - docs/reports/m5-59-validation-fix-triage.md — finding F1 and the TIA split
      - plc/forklift/TIA-FIX-PROCEDURE.md — step 7 is a hard gate on this ruling
      - docs/VALIDATION-M5.md — finding F1 and the run behind it
      - docs/interfaces/opcua-nodes.md §12 and §13
      - docs/interfaces/bridge-design.md §4.11
      - docs/adr/0014 — no velocity value crosses the OPC UA seam
    deliverable:         docs/interfaces/opcua-nodes.md, updated
    done_when:           Both leaves have a node row with name, type, access, owner and the consumer's required reaction stated — and the reaction is specified, not left to the consumer to choose.
    forbidden:
      - writing code, or editing outside docs/interfaces/
      - specifying anything that carries a speed value across the seam (ADR 0014)
      - inventing a name that does not mirror the PLC tag exactly (CLAUDE.md §9)

---

## 1. Why this is urgent and small

The validation measured the vehicle driving **19 s at 1.000 m/s** with
`SpeedMonitorDemand`, `Ss1Demand` and `TorqueOffDemand` all standing. The
F-program is right; the demands simply have nowhere to go. `Forklift/Safety/`
publishes four leaves where six are needed.

The owner has one TIA session tomorrow, and **step 7 of the fix procedure is a
hard gate on this ruling** — they cannot create a server-interface leaf whose
name and type nobody has decided. This is the one item worth landing tonight.

## 2. What to rule

For each of the two leaves:

- the **name**, mirroring the PLC tag exactly so the two documents diff
- the **type** and **access** — read-only to the client, as every mirror is
- the **owner**, which is the F-program, and the single consumer
- **the consumer's required reaction, stated in §12's own voice.** This is the
  part that matters. m5-11 left four reactions unspecified and the vehicle
  implemented four conservative readings of its own; that residue is still open
  in `docs/TODO.md`. Do not repeat it — say what the vehicle must do on each
  demand, and on a demand that is stale or absent.

## 3. Two constraints the ruling must respect

- **ADR 0014**: a demand crosses the seam, never a speed. If a row is tempted
  toward "the limit that was exceeded", it is the wrong row.
- **The stand-in labelling**: the whole safety input path is a standard DB and
  establishes no integrity claim. Wherever these rows describe the path, they
  say so. No PL, Category, SIL or PFH — targets only.

## 4. Working discipline

- Read `docs/LESSONS.md` first.
- If the ruling forces a change in `bridge-design.md`, request it in the report
  rather than making it — a separate brief owns the bridge half.
- **Do not commit.** The orchestrator commits by pathspec.
