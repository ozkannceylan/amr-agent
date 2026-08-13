# Brief mv-01 — Beckhoff/TwinCAT portability: research and architecture design

```
gate:                cross-cutting (owner request 2026-07-30); gate placement
                     is decided AFTER this research, not in it
agent:               research (fable), then arch-docs and specialists
goal:                establish what a second, Beckhoff/TwinCAT implementation
                     of this project's PLC layer can honestly be, and design
                     how it joins the existing architecture.
invariants_touched:  none may be changed by this document. Invariant 4 (the
                     PLC is the OPC UA server) and invariant 10 (one owner per
                     data item) are the two the design must satisfy explicitly
                     and must NOT quietly reinterpret.
inputs:              [CLAUDE.md sections 2, 3, 4, 9;
                      docs/interfaces/opcua-nodes.md (the node model — the
                      candidate contract);
                      docs/interfaces/handshake-tables.md;
                      docs/adr/0006-tia-derived-namespace-uri.md (a
                      tool-derived identifier that constrains the contract);
                      plc/demo-cell/SPEC.md, plc/forklift/SPEC.md,
                      plc/forklift-safety/SPEC.md (what would have to be
                      mirrored);
                      plc/forklift-safety/FIO-FEASIBILITY.md (the Siemens-side
                      question still open);
                      bridge/README.md and hmi/README.md (the OPC UA clients
                      that would have to work against both)]
deliverable:         docs/reports/mv-01-beckhoff-portability-research.md —
                     a research report AND an architecture proposal
done_when:           every question in sections A-F below is answered with
                     sources and verification dates, or explicitly marked
                     unverified with what would settle it; the proposal names
                     what "identical" can and cannot honestly mean; the owner
                     decisions it needs are listed as decisions, not resolved;
                     and the estimated size of each implementation stage is
                     stated so the owner can place it in the gate order.
forbidden:           [editing any file outside your own report; changing any
                      invariant or proposing that one be changed without
                      writing it as an explicit ADR-proposal-needed item;
                      claiming any product behaviour without a source;
                      assuming the two toolchains coexist on one machine
                      without researching it; presenting a licence as free or
                      unlimited without citing the actual terms; writing
                      implementation code]
```

## The thesis to test, not to assume

The tempting claim is "identical tags and addresses on both PLCs". Test it
against how the two systems actually work, and expect it to be false in its
literal form: Siemens organises data in DBs with a server interface that maps
symbols to OPC UA nodes, while TwinCAT exposes PLC symbols through ADS and its
OPC UA server. Physical addressing models differ at the root.

The stronger and probably honest claim is:

> The **contract** is identical — the same OPC UA browse paths, the same
> BrowseNames, the same data types, the same access rights, the same handshake
> semantics — so the **same bridge and the same HMI, unmodified, drive either
> vendor's controller, and the same scenario procedures pass against both.**

If that is right, vendor portability is demonstrated by the client stack and
the acceptance runs, not by a diff of two projects' addresses. Say plainly
whether the research supports this framing, a stronger one, or a weaker one.

## A. TwinCAT 3 without Beckhoff hardware

Can a full TwinCAT 3 PLC project run on an ordinary Windows PC with no
EtherCAT hardware at all — the equivalent of what PLCSIM Advanced does for
Siemens? Cover: the XAR runtime on the engineering PC; what happens to I/O
that has no terminals behind it; the Simulation Manager and whatever the
current mechanism is for simulated I/O; whether a project can run "free
running" with unmapped variables. Give the concrete steps a person would take.

**Licensing, precisely.** What does the 7-day trial licence actually permit,
how is it renewed, is renewal indefinite, and which functions need separate
licences — in particular the OPC UA server. State the terms as the vendor
states them, including any non-commercial or evaluation restriction, because
this project is a public portfolio and must not misrepresent a licence.

**Platform.** Does TwinCAT need its own real-time kernel extension, and what
does that mean for a machine that also runs TIA Portal and PLCSIM Advanced?
PLCSIM Advanced uses a virtual network adapter and interacts with Hyper-V.
Research whether TwinCAT's real-time layer and that arrangement conflict, and
whether Hyper-V being enabled or disabled forces a choice between the two
toolchains. **This is the single most likely practical blocker and the owner
has one Windows machine.** If they cannot coexist, say so and describe the
options: dual boot, a second machine, a VM, TwinCAT/BSD, or running them at
different times.

## B. The safety layer

The Siemens side has an F-CPU with an F-runtime group, F-FBD, F-I/O and
PROFIsafe. What is the Beckhoff equivalent — TwinSAFE, its logic terminals,
the Safety Editor, FSoE — and crucially: **can any of it run without hardware?**
The Siemens story already needed a feasibility probe for simulated F-I/O; the
Beckhoff story needs the same question asked before anything is promised.

Report what a software-only TwinSAFE story can and cannot be, and what the
honest equivalent of `plc/forklift-safety/SPEC.md` would look like on that
side. If the safety layer cannot be mirrored without hardware, that is a
finding, and the proposal should offer the owner a scoped alternative
(standard-program-only portability, with the safety layer named as
Siemens-only and why).

## C. The OPC UA server and the contract

How does the TwinCAT OPC UA server build its address space from PLC symbols?
What controls which symbols are exposed, what the namespace is, and what the
BrowseNames become. Then answer the decisive question: **can a TwinCAT server
be made to present the same browse paths and BrowseNames as
`docs/interfaces/opcua-nodes.md` specifies today?** Note that ADR 0006 records
a Siemens constraint — the namespace URI is derived from the server interface
name and is not editable — so identify the equivalent Beckhoff constraints
before assuming symmetry. Where the two cannot match exactly, say exactly
where and propose how the contract absorbs the difference without either
vendor's quirk leaking into the client.

## D. Addressing and symbols

Compare the two data models honestly: Siemens DBs, `%I`/`%Q`/`%M`, optimised
versus standard block access, and the server interface mapping; against
TwinCAT GVLs, program variables, `AT %I*`, ADS symbol paths. State what a
reader should understand by "the same addresses on both", and if the literal
version is not achievable, give the strongest true statement that is.

## E. Language portability

Both claim IEC 61131-3, but Siemens SCL and TwinCAT ST differ in real ways.
Take `plc/forklift/SPEC.md` §7 and `plc/demo-cell/SPEC.md` as the corpus and
report: which constructs port unchanged, which need rewriting, and which have
no equivalent. Cover at least timers and their instance handling, edge
detection, the `RS`/`SR` behaviour the safety spec relies on, data type names,
struct and array declarations, and how each vendor handles retentivity and
start values. Quantify roughly what fraction of the existing logic ports as
written.

## F. The architecture proposal

Design how a second vendor joins this repository. Address at minimum:

1. **Directory shape.** How `plc/` is organised so that vendor-specific work
   is visibly vendor-specific and the shared contract is visibly shared.
   Respect CLAUDE.md §4's rule that each top-level directory's README opens
   with what that layer must not access.
2. **The single source of truth** (invariant 10). Which document owns a tag's
   name, type and meaning, and how two implementations are kept from drifting
   from it — and from each other. Propose a mechanism, not an intention: what
   check would catch a drift, and could it run in this repository?
3. **What the clients must not learn.** The bridge and the HMI are OPC UA
   clients. State whether either needs any vendor knowledge at all, and if a
   single configuration value is unavoidable, name it and justify it.
4. **How portability is demonstrated.** Which existing scenario procedures
   would be run against the second vendor, what evidence would be produced,
   and what the honest claim on the README would be afterwards.
5. **Gate placement options**, with the size of each. Does this belong inside
   M5, as a gate of its own, or as a parallel track that lands later? Give the
   owner two or three shaped options with what each costs and what each buys —
   the placement decision is the owner's and must not be made here.
6. **The invariants.** Walk all thirteen and state, for each, whether the
   proposal leaves it untouched. Any that would need to change gets an
   explicit "this needs an ADR proposal and owner approval" flag, and the
   design should prefer not needing one.

## Method notes

Cite sources with URLs and verification dates; today is 2026-07-30. Prefer
vendor documentation (Beckhoff Information System, Siemens SIOS) over blogs.
Where a claim is version-dependent, say which version. Where you cannot verify
something, mark it unverified with what would settle it rather than filling
the gap with a plausible sentence — this project has a standing rule that a
figure appearing in no tool output does not go into a document.

Read the repository before proposing anything: the existing node model,
handshake tables and PLC specs are the thing being mirrored, and a proposal
that does not fit them is not a proposal.
