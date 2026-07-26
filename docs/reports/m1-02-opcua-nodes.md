brief:               docs/briefs/m1-02-opcua-nodes.md
status:              done
files_changed:       [docs/interfaces/opcua-nodes.md, docs/reports/m1-02-opcua-nodes.md]
invariants_touched:  none
open_questions:
  - Token type chosen as S7 String[16] / OPC UA String, opaque to the PLC. If the PLC agent prefers a numeric token (UDInt) for cheaper compare-and-echo, that is a one-line change in both this document and m1-03.
  - Door handshake uses PassageRequest (passage semantics) rather than DoorOpenRequest, to keep the client away from actuator vocabulary. Confirm the m1-03 sequence spec adopts the same wording.
  - Suggested sampling/publish intervals (100/250 ms) are advisory; final values belong to the PLC and fleet agents.
next_suggested:      m1-03 handshake sequence tables, using the Request/Ready/Busy/Done/Fault + token + Seq node set defined here.
