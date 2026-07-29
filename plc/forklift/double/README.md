# Forklift PLC logic double

**This is a rehearsal stand-in, derived from `plc/forklift/SPEC.md` §7.**

**The TIA Portal build described by that specification is the plant.** This
process is not the PLC, is not a second implementation, and is not a reference.
It exists so the teleop loop — HMI → PLC → bridge → simulation and back — can be
rehearsed end to end before the owner has built the program in TIA.

**Any divergence between this double and TIA + SPEC resolves toward TIA + SPEC,
never toward the double.** If the double and the CPU disagree, the double is
wrong. If the double and `SPEC.md` §7 disagree, the double is wrong. The double's
only claim on anyone's attention is that it is a faithful transliteration, and a
divergence is a bug in `logic.py` until proven otherwise.

**Nothing here is a safety function.** The obstacle stop, the fork-height speed
cap and the fork soft travel limits are standard-program process interlocks
implementing no function of `docs/safety/SRS.md` — not SF-02, not SF-03, not
SF-04, not SF-07, not SF-09 — and carry no SIL or PL claim (ADR 0008 D3). This
plant has no F-CPU and no onboard safety layer.

---

## What it is

| File | What it is |
|---|---|
| `logic.py` | `FB_ForkliftTeleop`, transliterated **statement for statement** from `SPEC.md` §7 — same identifiers, same order, same constants. No OPC UA in it, so it can be read side by side with §7. Also holds the §3.2 statics and §3.3 constants with their start values |
| `server.py` | The `asyncua` server: the §10 address space, the input/output image, and the 20 ms scan loop that calls the logic |
| `config.yaml` | Transport and scheduling only — port, host, scan period. **No behavioural constant lives here**: a process decision that can be edited in a config file has left the PLC layer |
| `check_kernels.py` | A direct `asyncua` client that demonstrates the T5.2, T5.3, T5.4 and T5.5 kernels plus the boot polarity. Imports nothing from another layer |
| `EVIDENCE_DOUBLE.md` | The run, its transcript, the read-back namespace table, and one finding against `SPEC.md` §11 |

## The transliteration rules

These are the point of the artifact. The double is worth having only if it is
what the specification says, so:

- **Same identifiers.** SCL `#hmiLinkOk` is `hmiLinkOk`; `"ForkliftHmi".X` is
  `db.ForkliftHmi.X`; `#HMI_STALE_TIME` is `K.HMI_STALE_TIME`.
- **Same order.** The seven numbered parts appear in §7's order and every
  statement keeps its position. Nothing is hoisted, merged or reordered.
- **Same constants**, to the digit, from §3.3.
- **No improvement.** A statement that looks redundant is transliterated anyway.
  A statement that looks wrong is transliterated anyway **and reported** — the
  first run of the kernels found exactly one such thing, and it is in
  `EVIDENCE_DOUBLE.md` and the m4f-04c report rather than quietly patched here.

## What it serves

Per `docs/interfaces/opcua-nodes.md` §10.3 and §2.1, with §10.3's data types and
per-tag access rights:

```
Objects                                  standard OPC UA namespace
  ServerInterfaces                       ns http://www.siemens.com/simatic-s7-opcua
    DemoCell                             ns http://DemoCell
      Link/    BridgeHeartbeat (w)  BridgeLinkOk (r)      the shared M3 link surface
      Forklift/
        Hmi/     5 request tags                  client-writable
        Input/   4 plant-state tags              client-writable
        Output/  3 setpoint tags                 read-only
        Status/  4 verdict tags                  read-only
        Link/    HmiHeartbeat (w)  HmiLinkOk (r)
```

20 nodes: the 18 of §10, plus the two `DemoCell/Link/` tags. A client resolves
**both** namespaces by URI and hardcodes neither index (ADR 0006 D4). Naming the
interface node `DemoCell` is what derives `http://DemoCell` — on the CPU that
field is not editable, and it is matched here so a client written against the CPU
browses the double unchanged. A misnamed interface presents as
`NamespaceNotFound` at connect, which is the intended fail-loud behaviour.

**The M3 demonstration cell is not implemented.** Only `DemoCell/Link/` of it is
served, because §7 consumes `"DemoCellLink".BridgeLinkOk` and never writes it:
that tag is owned by `FB_DemoCellControl`. Something must produce it or a bridge
would advance the heartbeat forever with the verdict stuck `FALSE`, so `logic.py`
carries a clearly-fenced **companion fragment** — the heartbeat half of
`plc/demo-cell/SPEC.md` §7 part 1, with *its* constant
(`HEARTBEAT_STALE_TIME` = `T#500ms`) — and nothing else of the M3 cell: no
conveyor, no panel, no sequence, no `LinkLostLatch`.

## Running it

Uses the bridge venv's `asyncua`, pinned at **2.0.1** (`bridge/requirements.txt`).
No new dependency.

```bash
V=/home/ozkan/amr-bridge-venv/bin/python

# serve on 4850
$V plc/forklift/double/server.py

# in another shell: demonstrate the kernels
$V plc/forklift/double/check_kernels.py
```

**Ports.** 4850 by default. `server.py` **refuses to start** on 4840 (PLCSIM
Advanced) or 4842–4846 (the bridge's own test doubles), because a double
answering on a port something else expects is worse than a double that will not
start.

**Never run this against PLCSIM.** The double is a server; PLCSIM is a server.
They do not talk to each other, and a client pointed at the wrong one produces
evidence that names the wrong system. Every recorded number must state which
server produced it.

## Timers

The IEC TONs accumulate the **measured** scan period, not the nominal 20 ms,
which is what an S7 TON does — it times against the CPU clock rather than an
assumed cycle. A loop that overruns therefore stretches its timers honestly
instead of silently running them slow. The measured period is logged every 500
scans; the recorded run held mean 20.6 ms, max 22.3 ms.

## What it does not do

- It is **not** the M3 demonstration cell.
- It runs **no plant model**. The four `Forklift/Input/` values are whatever a
  client writes; nothing integrates the fork or moves the machine. Physics is
  Gazebo's job, and the rehearsal run is where the two meet.
- It enforces **no per-client scoping**. Both writable groups are writable by any
  client, exactly as the commissioned CPU is today (`opcua-nodes.md` §10.12
  item 6) — which is why `check_kernels.py` can play both clients at once.
- It proves **nothing about the TIA build**. A kernel passing here says the
  specification is self-consistent and executable. The plant is verified by the
  owner's own run of `SPEC.md` §11 against the CPU.
