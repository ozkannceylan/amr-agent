# Report m3-19 — bridge-design.md commissioning corrections

brief:               docs/briefs/m3-19-bridge-design-commissioning.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md, docs/reports/m3-19-bridge-design-commissioning.md]
invariants_touched:  none

## What changed

Both phase-0 facts are now normative in the connect/reconnect section, each as a
numbered rule set so m3-21 has something to conform to and the verifier something
to check.

| Location | Change |
|---|---|
| §3 table | `Namespace` row → `Namespaces`: the browse path crosses **two** namespaces, both resolved by URI, neither hardcoded. `Node resolution` row now names the `Objects → ServerInterfaces → DemoCell` path. Two new rows: **Path shorthand** (every `DemoCell/…` name in the document is relative to the interface node, never to `Objects`) and **Session parameters** (what the bridge sends is a request; what is in force is what the server returned) |
| §3.1 new, normative | The commissioned path as a diagram plus rules **N1–N6**: DemoCell is not under `Objects`; both indices resolved by URI at every session establishment; each path element qualified with *its own* namespace index, never the parent's; missing URI = namespace-not-found at connect, retried, never browsed around and never guessed; both URIs are config values and the interface name is contract; namespace resolution is connect-or-fail and never yields a substituted value |
| §3.2 new, normative | Rules **S1–S6**: the configured timeout is a request; the bridge reads the granted (revised) value from the CreateSession response and logs both; the keep-alive is **derived from the granted value** (a fixed fraction leaving room for at least three exchanges inside the granted window, i.e. ≤ granted/3 — ≤ 10 s at the commissioned 30 s grant), never configured and never derived from the request; both re-read on every new session; the granted value bounds §7.3 case A; the same discipline applies to every negotiated parameter. Framed explicitly as connection housekeeping, not a signal gate — the same standing §8.1 already gives retry timing |
| §2 config row | "namespace URI" → **both** namespace URIs; the session timeout is marked as a *requested* value; the keep-alive is derived, never a config key (which also keeps the row's "no timers" prohibition honest) |
| §5.1 | Subscription keep-alive semantics are not only server-configured but server-*revised* (§3.2 S6) |
| §7.3 case A | "until the session/subscription timeout" → until the **granted** session timeout expires; commissioned grant 30 s; session state "may lag by up to the granted session timeout, so it is never the faster indicator". Dropped "subscription", which was wrong anyway — the bridge uses none (§5.1) |
| §8.1 | Detection ties the keep-alive to the failing session's granted timeout. On reconnect: re-resolve **both** indices by URI through the `ServerInterfaces` path, never reuse a cached index or NodeId, re-read the grant and re-derive the keep-alive, then the existing type check / input refresh / heartbeat order |
| §9.5, §10 | The double must reproduce the two-namespace shape with indices **different from PLCSIM's** (so a hardcoded index cannot pass) and must **clamp the session timeout below the request**, which is the only way the derivation is testable. §9.5's "a Python server reproduces none of them" now carries that one deliberate exception, so the two sections do not contradict each other |
| §12 | Open item 9: conformance of the running bridge and double to §3.1/§3.2 is m3-21's, with the pre-commissioning assumptions named |

Verification: a whitespace-normalised sweep of the whole document over `Objects`,
`namespace`, `browse`, `timeout`, `requested`, `granted`, `revised`, `keep-alive`
and `hardcod*` finds no surviving statement that DemoCell sits under `Objects`
and none that treats a requested session parameter as honored. Every `Objects`
occurrence is either the correct path or an explicit negation of the old
assumption.

Supporting check (read-only, no edits): `asyncua==2.0.1` on the owner's machine
already overwrites `Client.session_timeout` with `RevisedSessionTimeout` from the
CreateSession response and derives its health probe from the result, so S2/S3 do
not fight the pinned library — they forbid undoing it. Recorded in §3.2 as a
dated library note against the pin.

open_questions:

1. **The running bridge contradicts the revised design; this is m3-21's, not a
   defect in this document.** `bridge/amr_bridge/opcua_side.py` resolves a single
   namespace and browses `client.nodes.objects.get_child(path)` with one index
   per element, i.e. it looks for `DemoCell` directly under `Objects`, and it
   assigns `client.session_timeout` from config without reading the grant.
   `bridge/config/bridge.yaml` carries one `namespace_uri` and
   `session_timeout_ms: 10000`. Note the requested 10000 ms is *below* the
   observed 30000 ms grant, so m3-21 must handle a grant that moves in either
   direction, not only downward.
2. **Cross-document observation for the orchestrator, not a request.** The
   commissioned server also auto-publishes global data blocks in the Siemens
   namespace (m3-18's fact 2). The bridge is unaffected by construction: it
   resolves nothing outside the `DemoCell` interface path and its write allowlist
   is built from those resolved NodeIds, so a second path to the same value is
   unreachable from it. Stated here rather than in the design because the
   node-count scope is m3-18's deliverable.
3. **Same-gate consistency.** §3.1 and the browse-path section m3-18 is adding to
   `opcua-nodes.md` state the same commissioned facts from the same brief text.
   They were written concurrently and not diffed against each other; the verifier
   should diff them, and if they disagree the node model wins (this document's
   own preamble rule).
4. **`opcua-nodes.md` §2, M6 client, not touched by me.** It suggests a 100 ms
   sampling interval and 250 ms publish interval for the fleet manager's
   subscriptions. Those are *requested* parameters under the same clamp
   discipline as §3.2 S6, and the S7-1500 revises them too. Whether that belongs
   in m3-18's sweep or a later M6 brief is the orchestrator's call.

next_suggested:      m3-21 makes the client and the double conform to §3.1/§3.2 and records the run; the verifier diffs §3.1 against m3-18's browse-path section.
