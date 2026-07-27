brief:               docs/briefs/m3-14-adr-0006-namespace.md

status:              done

files_changed:
  - docs/adr/0006-tia-derived-namespace-uri.md   (new) accepted ADR, CLAUDE.md
                                                 section 8 format
  - docs/reports/m3-14-adr-0006-namespace.md     (this report)

invariants_touched:  none. The namespace model is not a section 2 invariant.
                     Invariant 4 (PLC is the server, fleet manager the client)
                     is unchanged and uncited as a constraint on this decision;
                     invariant 10 is unaffected, since no node's owner moves.
                     No ADR is superseded: 0001-0005 say nothing about the
                     namespace URI. No accepted ADR was edited.

numbering:           0006 verified next free. docs/adr/ contained
                     0001-architecture-invariants, 0002-vehicle-platform,
                     0003-ros2-distribution, 0004-gate-reordering-plc-loop-first,
                     0005-bridge-layer-and-opcua-client, and nothing higher.

authorship and status:

  Status is accepted, and the ADR says why in its own words before the Context
  section: the decision is the owner's own, made at the tool during
  commissioning phase 0 on 2026-07-27, and recorded verbatim. Per LESSONS
  (2026-07-26, ADR 0002 / live vendor sources; 2026-07-27, spec values authored
  without the tool), the TIA behaviour is attributed to the owner's dated
  commissioning observation and explicitly not to a vendor document, and the
  ADR states that it is an owner observation rather than an agent inference.

what the ADR decides:

  Context — TIA Portal derives a server interface's namespace URI as
    http://<interface name>; the field is not editable; therefore
    urn:amr-agent:cell:plc can never exist on an S7-1500 server interface, and
    the demonstration interface named DemoCell has the actual URI
    http://DemoCell. The derivation is per interface, which voids the assertion
    in opcua-nodes.md §9 and plc/demo-cell/SPEC.md §4.3 that the M3 and future
    M6 node sets "share the namespace URI but no node". The context closes by
    stating what is not in question: browse-by-URI resolution at session
    establishment is untouched; only the value and the scope change.

  Decision — four numbered points. D1: the URI is http://DemoCell, and it is
    not configured but follows from naming the interface, so the commissioning
    instruction becomes "name the interface DemoCell" and the URI is read back,
    not entered. D2: one namespace per server interface, by the rule
    http://<name>. D3: the shared-namespace assumption is void; the future
    fleet-facing interface carries its own derived URI, and the two node sets
    are now separated by namespace as well as by node. D4: browse-by-URI stands
    unchanged, including "namespace not found" as the intended failure mode.

  Consequences — split into harder and easier, as the brief required. Harder:
    no single shared namespace, so a two-interface client must hold one index
    per interface; the URI is coupled to the interface name, making interface
    names contract and a rename a contract change; the URI is not
    self-describing and looks like a resolvable HTTP address without being one;
    three documents and one running configuration carry the old value and are
    corrected by m3-15/16/17, named as not this ADR's work. Easier: the URI is
    derivable by rule and cannot be typed wrongly, so the three-way mismatch
    defect cannot occur; commissioning loses a step; namespaces now partition
    along the line the architecture already draws; and the general lesson about
    tool-derived identifiers is now visible.

  Alternatives — four, each with the reason. Companion-specification XML
    import: rejected as disproportionate toolchain cost for zero functional
    gain, since a NodeSet2 XML would have to be authored and re-authored on
    every node change for a fifteen-node address space in which only the string
    differs. Hardcoding the namespace index: rejected long ago and unchanged,
    recorded only to state that D4 does not reopen it. Renaming the interface
    to make the derived URI resemble the URN: rejected, since no name yields a
    urn: scheme and a name chosen for its URI stops describing the interface.
    Keeping the URN in the documents annotated with the real value: rejected,
    because a contract document carrying a value no tool can produce is a trap,
    and the project has already paid for one.

  The ADR describes a naming and addressing decision only. It contains no
  safety claim, and the demonstration cell has no F-CPU; nothing here touches
  a safety function or the safety path.

open_questions:

  1. The ADR is authoritative but the corrections are not applied. Until
     m3-15, m3-16 and m3-17 land, docs/interfaces/opcua-nodes.md §2 and §9,
     docs/interfaces/bridge-design.md, plc/demo-cell/SPEC.md §4.3 and §10
     step 6, and bridge/config/bridge.yaml still carry urn:amr-agent:cell:plc.
     ADR 0006 and those documents disagree in the interim; the ADR wins.

  2. Not mine, and not covered by m3-15/16/17: docs/TODO.md contains the old
     URI string, and historical evidence files (bridge/EVIDENCE_LATENCY.md,
     bridge/EVIDENCE_SIGNAL_LOSS.md) and closed reports (m3-02, m3-03,
     m3-03e, m3-06, m3-13) record it as run against. The evidence and reports
     are history and should stay as they are, per LESSONS on parked work;
     TODO.md is the orchestrator's and is live text, not history.

  3. D2 makes the future fleet-facing interface's name a contract decision that
     nobody has taken. Its namespace URI is whatever it is named, so the name
     should be chosen deliberately at M6 rather than discovered, and the choice
     recorded in opcua-nodes.md when §3-§7 are commissioned.

lessons_candidates:

  1. 2026-07-27 | An identifier was specified in a contract document and the
     realising tool was instructed to be set to it | TIA Portal derives the
     namespace URI from the interface name and the field is not editable, so
     the specified value was unreachable and three documents plus one running
     config had to be corrected at commissioning | An identifier that a tool
     generates is named, not configured: specify the input the tool takes (the
     interface name) and record the derived value as read back, never as set.

  2. 2026-07-27 | Two node sets on one CPU were documented as sharing a
     namespace URI while carrying no common node | Sharing a URI across two
     server interfaces is not expressible in TIA Portal, so the shared-namespace
     sentence was an assumption no tool could honour | Before writing that two
     things share a tool-managed property, confirm the tool has a scope in which
     that property can be shared.

next_suggested:      Issue or release m3-15, m3-16 and m3-17 against ADR 0006, and have the orchestrator sweep docs/TODO.md for the old URI string in the same pass.
