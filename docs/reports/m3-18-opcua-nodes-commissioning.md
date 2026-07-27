# Report m3-18 — opcua-nodes.md commissioning corrections

brief:               docs/briefs/m3-18-opcua-nodes-commissioning.md
status:              done
files_changed:       docs/interfaces/opcua-nodes.md
invariants_touched:  none
open_questions:
  1. §2 still states the namespace URI `http://DemoCell` at the head of a
     section whose folder tree (§2.2: `Cell/`, `Safety/`, `Conveyor/`,
     `Door/`, `Charger/`) belongs to the **fleet-facing** interface, which
     under ADR 0006 D3 carries its own derived URI from its own, not yet
     chosen, name. I scoped the browse-path rules around this (§2.1 last
     row: a second interface is a sibling with its own URI) but did not
     re-scope the §2 URI line, because naming the M6 interface is a
     contract decision for the owner at briefing (LESSONS 2026-07-27), not
     an interface-agent choice, and it is outside this brief. Suggest one
     brief that names the M6 server interface and re-scopes §2 in one pass.
  2. §2.2's `- **A requested session parameter…**` bullet points at
     `docs/interfaces/bridge-design.md` (m3-19) as the place the observed
     granted session-timeout values are recorded. m3-19 was running
     concurrently; the pointer dangles until it lands. I deliberately did
     not copy the clamp values here — they are not in this brief, and the
     connect sequence is the single owner of them (invariant 10).
  3. The §9.8 open item ("suppress DB-level exposure via per-DB *Accessible
     from HMI/OPC UA*") is written as belonging to "the gate that creates
     the fleet-facing interface and configures access control", without
     naming a gate number. If the owner wants it tracked, it needs a
     docs/TODO.md line — outside my write scope.
next_suggested:      Add the §9.8 DB-visibility suppression to docs/TODO.md against the gate that hardens the server, and decide the M6 fleet-facing interface name so §2's URI line can be scoped to it.

---

## What changed, per brief item

### 1. Browse path — new §2.1

`## 2` is retitled *Namespace, browse path and folder layout* and split: the
new **§2.1 "Browse path — a server interface is not a child of Objects"**
carries the commissioned tree

```
Objects                        standard OPC UA namespace
  ServerInterfaces             namespace http://www.siemens.com/simatic-s7-opcua
    DemoCell                   namespace http://DemoCell
```

plus a four-row rule table binding on every client: resolve **both**
namespaces by URI at connect (never an index); the parent folder does **not**
share the interface namespace and reusing the interface index for
`ServerInterfaces` fails to browse; every folder tree in this document is
relative to the interface node, so `DemoCell/Input/X` is shorthand for
`Objects/ServerInterfaces/DemoCell/Input/X`; and a second interface is a
sibling in the same folder with its own derived URI, so resolving one never
yields the other. The pre-existing folder tree became **§2.2**.

The path is restated where a reader could still infer a direct-under-Objects
layout: the §9 preamble ("reached at `Objects/ServerInterfaces/DemoCell`
— the interface is not a child of `Objects`") and after §9.2's tree ("this
tree starts at the interface node, whose full browse path is …").

### 2. Node-count claim — §9.8 scoped, open item recorded

§9.8 now opens with an explicit scope paragraph: the interface carries
**exactly 15 nodes** (7 `Input/`, 1 `Output/`, 5 `Status/`, 2 `Link/`), and
it is *not* true that the server exposes only those 15 — Siemens
auto-publishes every global DB under `Objects/DataBlocksGlobal` in its own
namespace, so the backing DBs are reachable by a second, uncontracted path.
Three consequences are tabulated: node-count checks are interface-scoped (a
client browsing from `Objects` legitimately sees more than 15, and both the
§9.10 independent verification and the bridge's `session established, N nodes
resolved` log count `DemoCell` nodes only); the interface is the contract and
the DB path is not; and every "deliberately absent" row is an interface
statement that a `DataBlocksGlobal`-visible DB member does not contradict.
The open item follows: clear the per-DB *Accessible from HMI/OPC UA*
attribute at a later gate, so the read-only access levels of §9.4/§9.5/§9.7
cannot be circumvented through the DB path.

Two column headers that read as server-wide claims were scoped: §8's and
§9.8's `Not on the server` → `Not on this interface` / `Not on the DemoCell
interface`, with a one-paragraph pointer from §8 to §9.8's scoping. §9.1's
`Nothing else on the server is client-writable` now reads "nothing else **on
the `DemoCell` interface**", records that the bridge writes nothing under
`DataBlocksGlobal`, and states plainly that at the commissioned access
settings the server does not enforce this — it is the bridge's contract.

### 3. Verified environment record — new §9.10

*Commissioned environment — phase 0, 2026-07-27*, a 13-row table: TIA Portal
V21; PLCSIM Advanced V7.0 with V3.0 removed (broken virtual adapter service,
unsupported with TIA V21); CPU 1513-1 PN firmware V3.1; OPC UA runtime
license "large" (compiler demanded large after the firmware change); TCP/IP
Single Adapter `<Local>`, instance 192.168.53.1/24, host virtual adapter
192.168.53.241/24; endpoint `opc.tcp://192.168.53.1:4840`, security None;
anonymous access via CPU-level *Disable access control* (V3.x firmware has no
guest-authentication checkbox, and disabling access control grants Anonymous
full rights including OPC UA); the browse path; and the independent
verification — an `asyncua` client on Windows read all 15 `DemoCell` nodes at
start values, **bridge not involved**.

Two closing paragraphs bound what the record licenses: phase 0 proves
endpoint, security/authentication configuration, browse path and node
exposure with data types, and proves **no** PLC program behaviour and nothing
about the bridge; and security None + anonymous full rights + default DB
visibility are demonstration settings, with hardening carried to the gate
that configures the server for a real client.

Every value is marked owner-verified in the tool and read back rather than
chosen, per the LESSONS rule on tool-derived identifiers.

### 4. Residual "times the hold" — none surviving

Verified clean rather than fixed. A whitespace-normalised sweep of the whole
document (regex over `\s+`-collapsed text, per LESSONS 2026-07-27) for
`times the hold`, `hold time`, `holds? the` and `timer` finds the reset rows
already carrying the m3-11 correction: §9.3 `PanelResetPressed` reads "the
PLC acts on its **rising edge** — no hold time, no timer", and §9.5
`CellResetRequired` reads "the rising edge the PLC acts on and which latches
clear are PLC program content". The only `hold time` occurrence in the
document is inside that negation. No edit was needed for this item.

## Verification

Whitespace-normalised sweep over the finished document for `Objects`,
`on the server`, `honou?red`, `[Rr]equested`, `15 `, `fifteen`, `session`,
`index`, `only`, `times the hold`, `hold time`:

- No statement places `DemoCell` directly under `Objects`. Every `Objects`
  occurrence is either the corrected path or the §2.1 rule that denies the
  direct-child layout.
- No statement treats a requested session parameter as granted. The two
  interval figures in §2.2 are labelled *Requested*, and the new bullet makes
  read-back of the granted value normative.
- No statement claims the server exposes only the interface nodes. The three
  formerly server-wide claims (§8 header, §9.8 header, §9.1 writability) are
  interface-scoped, and §9.8 states the `DataBlocksGlobal` exposure
  explicitly.
- `git diff --numstat`: `101 7 docs/interfaces/opcua-nodes.md` and nothing
  else of mine. (`bridge/EVIDENCE_*.md` and `docs/interfaces/bridge-design.md`
  were dirty in the tree from concurrent m3-19/m3-20 work; I touched neither.)

No node, name, type, direction, owner or access level changed. No logic,
threshold, timer or sequencing was added. Nothing was committed.
