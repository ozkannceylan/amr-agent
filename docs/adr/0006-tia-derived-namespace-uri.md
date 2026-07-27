# ADR 0006: The OPC UA namespace URI is tool-derived per server interface

Status:        accepted

This decision is the owner's own. It was made at the tool during commissioning
phase 0 on 2026-07-27, on the machine that will run the demonstration, and is
recorded here verbatim. The finding below is an owner observation in TIA
Portal, not an agent inference and not a reading of a vendor document.

Context:

`docs/interfaces/opcua-nodes.md` §2 specified the server's namespace URI as
`urn:amr-agent:cell:plc`, and `plc/demo-cell/SPEC.md` (§4.3 and §10 step 6)
instructed the commissioning engineer to set that URI on the server interface
in TIA Portal.

The owner's commissioning finding of 2026-07-27 is that this instruction cannot
be carried out:

1. TIA Portal **derives** a server interface's namespace URI from the interface
   name, as `http://<interface name>`.
2. The URI field is **not editable**. There is no dialog, property or project
   setting in which the derived value can be replaced by a chosen one.
3. Therefore `urn:amr-agent:cell:plc` can never exist on an S7-1500 server
   interface created in TIA Portal. It was a design value authored without the
   tool that realises it (LESSONS, 2026-07-27).
4. The M3 demonstration cell's server interface is named `DemoCell`, so its
   actual URI is `http://DemoCell`.
5. The derivation is per server interface. One server interface carries exactly
   one namespace, and a second interface on the same CPU carries its own,
   differently derived URI.

Point 5 voids an assumption written into two documents: `opcua-nodes.md` §9 and
`plc/demo-cell/SPEC.md` §4.3 both state that the M3 demonstration nodes and the
future M6 fleet-facing nodes "share the namespace URI but no node". Sharing a
URI across two interfaces is not something TIA can express.

What is **not** in question is how a client resolves the namespace.
`opcua-nodes.md` §2's rule — the namespace index is assigned at session
establishment and the client browses by URI, never hardcoding the index — is
untouched by this finding. Only the URI's value and its scope change.

Decision:

**D1 — The namespace URI of the demonstration cell's server interface is
`http://DemoCell`.**

It replaces `urn:amr-agent:cell:plc` everywhere that value is authoritative.
It is not configured; it follows from naming the server interface `DemoCell`.
The commissioning instruction becomes "name the interface `DemoCell`", and the
URI is then a consequence to be read back and confirmed, not entered.

**D2 — One namespace per server interface, derived from the interface name.**

The project rule is: for any server interface named `<name>`, the namespace URI
is `http://<name>`. No interface is given a URI by hand, because no interface
can be.

**D3 — The shared-namespace assumption for the future fleet-facing interface is
void.**

The M6 interface serving `Cell/`, `Safety/`, `Conveyor/`, `Door/` and
`Charger/` to the fleet manager will carry its own `http://<its name>` URI. The
two node sets remain unmerged, as they always were; what changes is that they
are now separated by namespace as well as by node, rather than sharing one.

**D4 — Browse-by-URI stands unchanged.**

Clients resolve the namespace index by browsing for the URI at session
establishment and never hardcode an index. This ADR changes the string that is
browsed for, not the mechanism. A wrong or absent interface still presents as
"namespace not found" at every connect, which remains the intended failure mode.

Consequences:

What becomes harder:

- There is no single shared namespace across the cell's interfaces. A client
  that consumes nodes from more than one interface must resolve one index per
  interface and keep them distinct. The fleet manager is not affected today —
  it will consume exactly one interface — but the possibility of a two-interface
  client is now a design constraint rather than a free move.
- The URI is coupled to the interface name. Renaming a server interface changes
  its namespace URI and breaks every client browsing for the old one. Interface
  names are therefore contract, and renaming one is a contract change.
- The URI is not self-describing. `http://DemoCell` carries no project,
  organisation or version, where `urn:amr-agent:cell:plc` did. It also looks
  like a resolvable HTTP address and is not one. Neither is fixable; both are
  the tool's output.
- Three documents and one running configuration were written against the old
  value and must be corrected before the M3 loop is re-proven. That work is
  briefs m3-15 (interface documents), m3-16 (bridge, test double and allowlist
  checker) and m3-17 (PLC spec), not this ADR.

What becomes easier:

- The URI is derivable by rule from the interface name, so it can never be
  configured wrongly. The class of defect where a spec, a PLC project and a
  client config each carry a hand-typed URI and one of them differs cannot
  occur.
- Commissioning loses a step. There is nothing to set, only a name to choose
  and a derived value to read back.
- Namespaces now partition along the same line the architecture already draws:
  the demonstration cell served to the bridge and the target cell served to the
  fleet manager are separate interfaces, separately named, separately resolved.
- Every tool-derived identifier in a spec is now visibly a candidate for the
  same class of error, which is the general lesson this finding produced.

Alternatives:

- **Import a companion-specification XML to obtain a chosen namespace URI** —
  rejected. TIA Portal can import a companion specification, and that path can
  carry a URI the tool did not derive, but it means authoring and maintaining a
  NodeSet2 XML for an address space of fifteen nodes, and re-authoring it on
  every node change. The toolchain cost is disproportionate and the functional
  gain is zero: the address space, the node names, the access rights and the
  client's resolution behaviour are all identical either way. Only the string
  differs.
- **Hardcode the namespace index in the client and stop browsing** — rejected,
  and rejected long ago. `opcua-nodes.md` §2 has always required
  browse-by-URI, because the index is assigned at session establishment and is
  not a stable property of the server. Recorded here only to state that this
  ADR does not reopen it; D4 restates the rule unchanged.
- **Rename the interface to make the derived URI resemble the designed URN** —
  rejected. Derivation is `http://<name>`, so no interface name yields a `urn:`
  scheme, and a name chosen to make a URI look right would stop describing the
  interface. The interface is named for what it is, and the URI follows.
- **Keep `urn:amr-agent:cell:plc` in the documents as the "intended" URI with
  the real one noted beside it** — rejected. A contract document that carries a
  value no tool can produce is a trap for the next reader, and this project has
  already paid for one such value. The designed URN is superseded, not
  annotated.
