# Report m3-22 — bridge-design.md sync after connect conformance

```
brief:               docs/briefs/m3-22-bridge-design-conformance-sync.md
status:              done
invariants_touched:  none
```

## files_changed

| File | Change |
|---|---|
| `docs/interfaces/bridge-design.md` | §12 item 9 closed by m3-21 and cited to `bridge/EVIDENCE_CONNECT.md`; §9.4 evidence table gained the connect capture and its raw CSV; §3.1 and §3.2 each gained a one-line conformance pointer; four statements that still described the pre-m3-21 situation or the double's one-directional grant were corrected (list below) |

Nothing else was touched. Nothing was committed.

## What the done_when asked for

| Criterion | Where |
|---|---|
| §12 item 9 marked resolved by the m3-21 delivery | Item 9 now reads **Closed by m3-21**, names what the client and the double do (both URIs in config, both indices resolved by URI per session, each path element qualified by its own namespace, grant read back and keep-alive derived from it), states that the pre-commissioning shape is gone and is rejected by the config loader, and carries the one thing that genuinely remains: the owner's repetition against PLCSIM, item 9 of `EVIDENCE_LATENCY.md` Section B |
| §9.4 lists `bridge/EVIDENCE_CONNECT.md` | Added as a fourth row alongside the latency file, its CSV and the signal-loss file, plus a fifth row for `bridge/evidence/connect-conformance-<YYYY-MM-DD>.csv`. Described by what it covers (N1–N6, S1–S6, full-loop and reconnect re-runs), with no measurement restated |
| No statement still describes the single-namespace client as current | Verified by whitespace-normalised search over the whole document for `clamp`, `as if granted`, `directly under`, `one namespace`, `namespace_uri`, `nodes.root`, `session_timeout`, `pre-commission`, `open item`, `blocked`, `not yet`, `m3-21`. The only single-namespace description left is inside item 9's account of what m3-21 replaced, written in the past tense |

## Corrections made beyond the three criteria

Each one was a statement in this document that the m3-21 delivery made inaccurate.
They are corrections to the specification's own claims, not additions to it.

1. **§3.2 opening** said "The S7-1500 **clamps** the session timeout". The phase-0
   observation is a clamp downwards, but the bridge now requests 10 000 ms — less
   than the 30 000 ms the CPU granted — so the grant may land above the request.
   Now reads "revises", with the phase-0 clamp kept as the instance.
2. **§10 negotiation fidelity** and **§9.5** said the double clamps below the
   request. The delivered double revises in either direction, which is what makes
   S2/S3 falsifiable in both; both rows now say so.
3. **§3.2 library note** said `asyncua` "logs a warning when the two differ",
   implying the warning is usable. m3-21 found it prints the library's secure
   channel default as the requested value. The note now says so and points at
   `EVIDENCE_CONNECT.md` §3, which is why the bridge logs both numbers itself.
4. **§9.5's "establishable with the double alone" row** for the connect
   requirements is now marked **Established**, with the evidence file named — the
   row previously read as a forward-looking claim.

## open_questions

1. **Root `.gitattributes` inventory comment** ("Tracked shebang files today: 1
   `*.sh`, 7 `*.py`") is stale — `bridge/tools/check_connect_conformance.py` makes
   it 8. Raised by m3-21 and still open; the file is outside this agent's scope, so
   it is requested, not made. The rule itself already covers the new file.
2. **§12 is now nine items with only owner-run repetition outstanding.** Items 1–9
   are all resolved or closed. Whether the section should be pruned to the open
   residue, or kept whole as a record of what each item cost, is an editorial
   decision for the owner — not taken here, since an open-items table that quietly
   loses its closed rows is harder to audit.
3. **`EVIDENCE_CONNECT.md` is test-double evidence.** This document now cites it as
   the conformance record; the gate still closes on the PLCSIM run (§9.4, §10). No
   wording here claims otherwise, but the distinction is easy to lose in a later
   summary.

## next_suggested

Nothing in `docs/interfaces/` blocks the owner's PLCSIM capture; the checklist for
it is at the end of `bridge/EVIDENCE_CONNECT.md`.
