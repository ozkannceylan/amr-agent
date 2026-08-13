gate:                M1
agent:               interface
goal:                Document the station handshake sequences and the single-owner map for every shared data item.
invariants_touched:  none
inputs:              [docs/interfaces/vda5050-subset.md, docs/interfaces/opcua-nodes.md, CLAUDE.md sections 2 (invariant 10), 9]
deliverable:         docs/interfaces/handshake-tables.md
done_when:           Conveyor transfer, door passage and charger docking each have a step-by-step handshake table (who sets what, over which interface, timeout and fault branch); a data-ownership table assigns exactly one owner to every shared item across VDA 5050 and OPC UA; no item is computed in two places.
forbidden:           [writing code, introducing new signals absent from m1-01/m1-02 without listing them as additions to those docs, editing other directories]
