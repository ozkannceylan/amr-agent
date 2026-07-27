# Report m3-21 — bridge connect conformance to the commissioned server

```
brief:               docs/briefs/m3-21-bridge-connect-conformance.md
status:              done
invariants_touched:  none
```

## files_changed

| File | Change |
|---|---|
| `bridge/config/bridge.yaml` | `opcua.namespace_uri` → `opcua.namespace_uris` (both URIs of §3.1); `nodes.root` → `nodes.interface_path`, a list whose elements each name their own namespace; `session_timeout_ms` → `requested_session_timeout_ms`. No index anywhere, no new key that could carry logic |
| `bridge/amr_bridge/config.py` | schema updated; `browse_path()` now returns `(namespace key, BrowseName)` pairs; new guards reject the pre-commissioning shape, a missing second URI, an index written where a URI belongs, a BrowseName carrying an index, and an `interface_path` whose last element is not the interface namespace |
| `bridge/amr_bridge/opcua_side.py` | both indices resolved by URI at every session establishment (`NamespaceNotFound` on a missing URI, no fallback, no scanning); every path element qualified with its own index; granted session timeout and secure-channel lifetime read back on every connect and logged next to the requested values; keep-alive derived as granted / 3 and run as a gated idle-session exchange; `auto_reconnect=False` set explicitly so only `_connect` can create a session; a connect that fails after `CreateSession` now closes the half-open session before retrying |
| `bridge/amr_bridge/instrumentation.py` | two counters: `keepalive_probes`, `keepalive_failures` |
| `bridge/test_double/plc_test_double.py` | serves the Siemens-shaped path (`Objects` → `ServerInterfaces` in the vendor namespace → `DemoCell` in `http://DemoCell`); three filler namespaces put its indices at 5 and 6, unlike PLCSIM's; `--min/--max-session-timeout-ms` (default `[5000, 8000]`) make it revise the client's request in either direction |
| `bridge/tools/check_connect_conformance.py` | **new.** Drives the bridge's own `_connect`; 22 checks over §3.1 N1–N6 and §3.2 S1–S6, including an idle window longer than the grant that *measures* the keep-alive cadence |
| `bridge/tools/check_write_allowlist.py` | resolves through the two-namespace path (it would otherwise fail against the new double) |
| `bridge/EVIDENCE_CONNECT.md`, `bridge/evidence/connect-conformance-2026-07-27.csv` | **new.** The recorded runs and their raw rows |
| `bridge/README.md`, `bridge/test_double/README.md` | startup log lines, the two namespace URIs, the double's index shift and grant window, how to run the new check |
| `bridge/EVIDENCE_LATENCY.md`, `bridge/EVIDENCE_SIGNAL_LOSS.md` | the statements that named m3-21 as the blocker are closed in place; §B.0.3 item 2 restated (the grant may land either side of the request) and a ninth owner-run capture item added |

Nothing outside `bridge/` was touched. Nothing was committed.

## Recorded evidence (WSL2, test double, 2026-07-27)

| Run | Result |
|---|---|
| Conformance harness, double granting **8000 ms** for a 10 000 ms request | PASS, 22/22. Indices 5 and 6 resolved by URI; the pre-m3-21 paths all return `BadNoMatch`; keep-alive 2.667 s = granted/3; measured exchange spacing 2.668 s, excluding the 3.333 s the request would have implied; both wrong-URI cases raise `NamespaceNotFound` |
| Same harness, double granting **30 000 ms** (above the request, as the CPU did) | PASS. Keep-alive 10.000 s, measured spacing 10.003 s — the number the owner's PLCSIM run should log if the CPU grants 30 000 ms |
| `run_bridge.py`, unmodified config | Logs both namespaces, the resolved `Objects/5:ServerInterfaces/6:DemoCell`, requested vs granted timeout, and the derived keep-alive |
| Full loop (headless cell + stimulus + bridge, 40 s) | 800 cycles at 20.0 Hz, 792 heartbeat writes, 0 write/read errors, 0 reconnects, `keepalive_probes = 0` — the keep-alive adds no traffic to a healthy run |
| Double bounced under a live bridge | New session re-resolves both indices and all 15 NodeIds, re-reads the grant and re-derives the keep-alive (§8.1, §3.2 S4) |
| Config loader guards | 5/5 — a stale or index-bearing config cannot start the bridge |

## No logic was added

The keep-alive is the one timer, permitted by the brief and by §3.2 as connection
housekeeping: it reads the standard `ServerStatus/State` node, applies it to
nothing, and cannot delay or suppress a transported value. It skips its exchange
when the cycle has already touched the session within the period — a comparison
of two monotonic readings, with no process value involved. No threshold,
tolerance, latch, sequence or interlock was added, and the config still rejects a
key for any of those.

## open_questions

1. **`docs/interfaces/bridge-design.md` §12 open item 9** says "Open, owned by
   m3-21". It is now closed by this work, and §9.4's evidence table does not yet
   list `bridge/EVIDENCE_CONNECT.md`. Both edits belong to the interface agent —
   requested, not made.
2. **Root `.gitattributes`** carries the inventory comment "Tracked shebang files
   today: 1 `*.sh`, 7 `*.py`". `bridge/tools/check_connect_conformance.py` makes
   it 8. The rule itself (`*.py text eol=lf`) already covers the new file, so only
   the comment is stale; the file is outside `bridge/`.
3. **`asyncua`'s own health probe** still runs at its library default of 1 s, on
   top of the bridge's derived keep-alive. It is not configured by this project
   and cannot be slower than the derivation requires, so it is harmless — but it
   is why `EVIDENCE_CONNECT.md` proves S3 by *measuring the cadence* of the
   bridge's own exchanges rather than by the session merely surviving.
4. **The library logs a misleading line**: `Requested session timeout to be
   3600000ms, got 8000ms instead` prints its secure-channel default, not the
   requested session timeout. Recorded in the evidence file so the owner does not
   read it as the bridge's request.

## next_suggested

`EVIDENCE_LATENCY.md` Section B (PLCSIM Advanced, owner-run) is no longer blocked
on a client change; the connect checklist for that run is at the end of
`bridge/EVIDENCE_CONNECT.md`.
