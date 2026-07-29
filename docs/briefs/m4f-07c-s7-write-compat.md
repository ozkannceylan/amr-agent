# Brief m4f-07c — S7-compatible writes from the HMI

```
gate:                M4
agent:               hmi
goal:                The HMI's OPC UA writes are accepted by a real S7-1500
                     server, not only by the python test doubles.
invariants_touched:  none
inputs:              [hmi/hmi_server.py, the live failure below,
                      bridge/amr_bridge/opcua_side.py (read-only reference —
                      the bridge has written to this server since M3, its
                      DataValue construction is the proven pattern; do not
                      import bridge code, mirror the pattern),
                      docs/interfaces/bridge-design.md (any S7 write-rule note)]
deliverable:         hmi/hmi_server.py — the write path, and EVIDENCE_HMI.md
                     appended
done_when:           every DataValue the backend writes carries the Variant
                     value only — SourceTimestamp and ServerTimestamp None,
                     no StatusCode — so the S7 rule is met; the change is in
                     ONE helper through which all six writes already pass;
                     both existing kernel harnesses re-run green against the
                     double (which accepts both forms, so green there plus
                     the S7 rule satisfied is the full claim); the evidence
                     appends the live failure signature (BadWriteNotSupported,
                     2026-07-29, first contact with the real CPU) and the fix,
                     quoted as printed; nothing else in the backend changes.
forbidden:           [connecting to the live PLCSIM endpoint (the orchestrator
                      runs the live verification), touching the UI page or any
                      other behaviour, new dependencies, mentioning any
                      deadline]
```

Live failure, verbatim from the first real-CPU contact:
`BadWriteNotSupported: The server does not support writing the combination of
value, status and timestamps provided.` — session established (6 writable, 12
read-only resolved), first write refused, deadman fired correctly, reconnect
loop correct.

Git: repo-local owner identity; pathspec-scoped commit of exactly the two hmi/
files plus your report docs/reports/m4f-07c-s7-write-compat.md; message style
`fix(hmi): write S7-compatible DataValues`.
