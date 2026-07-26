gate:                M1
agent:               interface
goal:                Document the VDA 5050 message subset this project uses, traceable to the official standard.
invariants_touched:  none
inputs:              [CLAUDE.md sections 2, 3, docs/adr/0001..0003, official VDA 5050 v2 spec at github.com/VDA5050/VDA5050]
deliverable:         docs/interfaces/vda5050-subset.md
done_when:           Topics (order, state, instantActions, connection, factsheet), serialization, and the exact field subset used are listed with every field traceable to the official v2 schema; extensions only in documented extension points; watchdog/connection-loss behavior mapped to invariant 2.
forbidden:           [writing code, inventing fields not in the standard, editing other directories, deciding PLC-side content]
