brief:               docs/briefs/m3-03b-adr-0005-bridge-layer.md

status:              done

files_changed:
  - docs/adr/0005-bridge-layer-and-opcua-client.md   (new) accepted ADR, section 8 format
  - docs/reports/m3-03b-adr-0005-bridge-layer.md     (this report)

invariants_touched:  none. The ADR records two placement and tooling
                     decisions inside the existing invariants; it changes no
                     invariant and proposes none. Invariants 1, 4, 5, 6, 10 and
                     11 are cited as the reasons for the decisions, not altered
                     by them.

what the ADR decides:

  D1 — the bridge is a top level directory, bridge/, not fleet/bridge/.
    It carries its own README whose first section is "This layer must not
    access", listing at minimum: fleet manager code, state or configuration;
    VDA 5050 and MQTT; order, traffic and zone-reservation concepts; PLC
    program logic; any control decision (the no-logic rule of
    bridge-design.md §1.1 is named as the binding statement); any safety
    function or safety path. The deciding argument is that fleet/README.md's
    ban on ROS 2 topics, services and actions is correct for the fleet
    manager, and the bridge is by definition a ROS 2 node — so keeping it
    under fleet/ would mean writing an exception into another layer's
    boundary statement. Rejected alternatives: fleet/bridge/ plus an exception
    line (weakens a boundary to fit one component); sim/bridge/ (the bridge is
    not a simulation asset and must survive replacing the sim with real
    equipment). ADR 0004's rejection of folding the bridge into the fleet
    manager is noted as already settled and not reopened.

  D2 — asyncua is the OPC UA client library and supplies the test double
    server. Pinned to an exact version in bridge/requirements.txt, imported
    unmodified, transitively pulling cryptography. The exact version lives in
    the requirements file rather than in the ADR, so a version bump does not
    require superseding an immutable document. Licence stated plainly:
    LGPL-3.0, imported as a library rather than linked statically or vendored,
    which is the usual and unproblematic use — recorded as a description of
    use, explicitly not as legal advice. Rejected: python-opcua/opcua
    (deprecated predecessor), open62541 bindings (C toolchain for eight
    nodes), a hand-written client (re-implementing a protocol stack is not
    this project's contribution, and every M3 latency number would become a
    measurement of that client's defects).

  This closes open questions 1 and 2 of docs/reports/m3-03-bridge-design.md.
  Nothing else in that report is affected; its open questions 3 and 4 remain
  open and are m3-04's and m3-05's.

open_questions:

  1. REQUIRED FOLLOW-UP, ORCHESTRATOR, NOT MINE TO MAKE. CLAUDE.md needs two
     edits and is the owner's file:
       (a) section 4, repository layout — add a bridge/ entry between agv/ and
           sim/, described as the ROS 2 <-> OPC UA signal translator;
       (b) section 5, agent roster — add a bridge agent, single responsibility
           "Gazebo/PLC signal bridge and its test double", write access
           bridge/.
     Until (b) exists, no agent owns bridge/ and the m3-04 implementation
     brief has no valid assignee. This blocks m3-04, not this deliverable.

  2. Path corrections carried by D1, in files that are not mine. Three
     documents still name the provisional location:
       - docs/interfaces/bridge-design.md — §9.4 (fleet/bridge/EVIDENCE_LATENCY.md,
         fleet/bridge/evidence/), §10 "Location" row, §11 install path, §1
         table row 4, and §12 open item 1, which this ADR resolves and which
         should be marked resolved rather than left carried. That is the
         interface agent's file.
       - fleet/README.md — needs NO change. That is the point of D1, and it is
         worth recording so a future reader does not add the exception line
         anyway.
       - The m3-04 brief, when written, must target bridge/ and not
         fleet/bridge/.

  3. The asyncua version is not pinned yet. The ADR requires an exact pin in
     bridge/requirements.txt; choosing and recording the version is m3-04's
     first act, and the version chosen should be stated in the m3-04 report so
     the pin is traceable to a run.

next_suggested:      Orchestrator applies the CLAUDE.md layout and roster edits (open question 1), then re-briefs the interface agent for the bridge-design.md path corrections, then issues m3-04 against bridge/.
