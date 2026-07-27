# Report m3-23 — verification of the commissioning-correction chain

```
brief:               docs/briefs/m3-23-verify-commissioning.md
status:              done
files_changed:       docs/reports/m3-23-verify-commissioning.md (this file only)
invariants_touched:  none
```

**Overall verdict: pass-with-findings.** All seven checks pass on substance.
Nine findings, none blocking: seven are wording or tracking accuracy, two are
corrections to the owner-executed list at the end of this report. Nothing in the
m3-18 → m3-22 chain was found wrong about the commissioned system.

| # | Check | Verdict |
|---|---|---|
| 1 | Cross-document consistency, `opcua-nodes.md` §2.1 vs `bridge-design.md` §3.1 | **pass** |
| 2 | No surviving stale claims across `docs/interfaces/` and `bridge/` | **pass-with-findings** |
| 3 | Conformance evidence re-run from committed instructions | **pass** |
| 4 | `bridge.yaml` against the commissioned facts | **pass-with-findings** |
| 5 | Tracking coherence (PLAN, TODO, roadmap, report directory) | **pass-with-findings** |
| 6 | Attribution | **pass** |
| 7 | Layer boundaries and no-logic rule | **pass** |

Environment of this verification: Windows checkout at
`C:\Users\ozkan\projects\amr-agent` at `1e3eb08`; the re-run executed in WSL2
Ubuntu, venv `/home/ozkan/amr-bridge-venv`, isolated with `ROS_DOMAIN_ID=93`
and `GZ_PARTITION=m323verify` on loopback ports 4844/4845 so nothing could
collide with a concurrent agent. The live endpoint `192.168.53.1` was not
contacted (owner-executed). Working tree after the run is byte-identical to
before it — `git status --porcelain` reports only the owner's two untracked
scratch files.

---

## 1. Cross-document consistency — pass

`opcua-nodes.md` §2.1 (m3-18) and `bridge-design.md` §3.1 (m3-19) were written
concurrently from the same brief text. Diffed clause by clause:

| Claim | `opcua-nodes.md` §2.1 | `bridge-design.md` §3.1 | Agree |
|---|---|---|---|
| Tree shape | `Objects` → `ServerInterfaces` → `DemoCell` → `Input/ Output/ Status/ Link/` | identical | yes |
| Siemens URI | `http://www.siemens.com/simatic-s7-opcua` | identical string | yes |
| Interface URI | `http://DemoCell` | identical string | yes |
| Resolution rule | both indices by URI at connect, neither hardcoded | N2, same | yes |
| Per-element qualification | reusing the interface index for `ServerInterfaces` fails to browse | N3, stated as a positive rule | yes, N3 is the stronger form |
| Path shorthand | every tree in the document starts at the interface node | table row "Path shorthand" + N1 | yes |
| Failure mode | "namespace not found" at every connect, now two lookups can fail that way | N4, connect-or-fail, no scan, no fallback | yes |
| Second interface | sibling in the same folder, own derived URI | not stated (out of scope for the bridge) | no contradiction |

No contradiction on path, URI or qualification rule. Two observations, neither a
disagreement:

- **F1 (observation).** `bridge-design.md` N3 and
  `tools/check_connect_conformance.py` both cite the phase-0 observation that
  PLCSIM published `ServerInterfaces` at index **3**; `opcua-nodes.md` §9.10, the
  environment record and the document that wins on disagreement, does not record
  that number. The harness asserts against it (`PLCSIM_SERVER_INTERFACES_INDEX =
  3`), so the datum is load-bearing in code while absent from the contract.
  Correctly framed as evidence-that-indices-differ rather than a value to
  configure in both places, so this is a completeness note, not an error.
- **F2 (already tracked).** `opcua-nodes.md` §2 still heads the *fleet-facing*
  folder tree with `http://DemoCell`. m3-18 open question 1 raised it, TODO
  carries it under `interface (M6)`, and it is correctly deferred to the brief
  that names the M6 server interface (ADR 0006 D3 makes that name a contract
  decision). Confirmed still open, correctly parked.

## 2. No surviving stale claims — pass-with-findings

Whitespace-normalised sweep (`\s+` collapsed before matching, per LESSONS
2026-07-27) over every `.md`, `.py`, `.yaml` and `.csv` under
`docs/interfaces/` and `bridge/`, for the four target claims.

**(a) DemoCell directly under `Objects` — clean.** Nine hits across seven files;
every one is either the corrected path, an explicit negation ("does not hang
directly under"), a config-loader error message, or a harness assertion that the
old path returns `BadNoMatch`. No statement asserts the old layout.

**(b) A requested session parameter treated as granted — clean.**
`opcua-nodes.md` §2.2 labels the 100 ms sampling and 250 ms publish intervals as
*requested* and makes read-back of the granted value normative — which also
closes m3-19's open question 4. `bridge.yaml` labels
`requested_session_timeout_ms` a request; `opcua_side.py` assigns it and reads
the grant back. The old keys `namespace_uri`, `nodes.root` and
`session_timeout_ms` survive only inside past-tense accounts (§12 item 9,
`EVIDENCE_CONNECT.md` §7's rejection messages, and the m3-16/m3-19/m3-20
reports, which are history and correctly untouched).

**(c) "exactly 15 nodes" unscoped — clean.** Every occurrence is scoped:
`opcua-nodes.md` §9.8 opens with the scope paragraph and states the
`DataBlocksGlobal` exposure; `bridge-design.md` says "the fifteen-node
`DemoCell/` address space"; the evidence files say "15 `DemoCell` nodes"; the
harness says "resolved through Objects/ServerInterfaces/DemoCell". The three
formerly server-wide headers (§8, §9.8, §9.1 writability) are interface-scoped.

**(d) "clamp" where the revision can go both ways — three survivals in
`bridge/`.** m3-22 corrected `bridge-design.md` §3.2, §9.5 and §10 to "revises"
and to a double that moves the grant in either direction. The equivalent
statements in the evidence files were not in any brief's scope and are still
one-directional:

- **F3.** `bridge/EVIDENCE_SIGNAL_LOSS.md` line 63: *"This server clamps session
  timeout to 30 000 ms and the bridge requests 10 000 ms, so how long the
  S7-1500 holds a session after a bridge kill is a property of this stack."* A
  reader concludes the 10 000 ms request passes a 30 000 ms ceiling unchanged.
  `EVIDENCE_LATENCY.md` §B.0.3 item 2 says the opposite and is right: the CPU
  granted **above** a request once already, so the grant for 10 000 ms may land
  either side. These two files disagree; §B.0.3 is the correct one.
- **F4.** The facts table row *"Session timeout | requested 3 600 000 ms, granted
  30 000 ms — **the server clamps it**"* appears in both
  `EVIDENCE_LATENCY.md` §B.0 and `EVIDENCE_SIGNAL_LOSS.md`. As a description of
  the one observed instance it is true; as a property of the server it is the
  claim m3-22 removed from the design. "revises it (clamped down in this
  instance)" would match §3.2.

Neither affects the bridge's behaviour — the code computes the verdict at
runtime with all three branches (`clamped BELOW` / `raised ABOVE` / `granted as
requested`) — but both are read by the owner immediately before the PLCSIM run.

## 3. Conformance evidence re-run — pass

Re-run from the committed instructions in `bridge/README.md` and the harness
docstring, against the test double only, on isolated ports. Both recorded runs
reproduce, value for value.

| Committed claim (`EVIDENCE_CONNECT.md`) | Re-run, 2026-07-27, WSL2 |
|---|---|
| Both URIs resolved by URI, `ServerInterfaces → 5`, `DemoCell → 6` | identical |
| Indices differ from PLCSIM's phase-0 index 3 | identical |
| 15 nodes resolved through `Objects/5:ServerInterfaces/6:DemoCell` | identical |
| Four pre-m3-21 paths all `BadNoMatch` | identical |
| Grant **below** request: requested 10000, granted 8000, keep-alive **2.667 s** | identical |
| Measured idle spacing `['2.668','2.668','2.668']` s (committed: `2.668, 2.668, 2.669`) | reproduces within 1 ms |
| Request-derived 3.333 s excluded by measurement | identical |
| Grant **above** request: granted 30000, keep-alive **10.000 s** | identical |
| Measured spacing `['10.005','10.003','10.002']` s (committed: `10.003, 10.002, 10.003`) | reproduces within 3 ms |
| Both wrong-URI cases raise `NamespaceNotFound` | identical |
| `RESULT: PASS` in both directions | identical, exit 0 |

The keep-alive derivation is proved by measured cadence, not by session
survival, exactly as the evidence file argues. The 10.000 s figure the owner
should see if PLCSIM grants 30 000 ms is confirmed independently.

- **F5.** The harness prints `RESULT: PASS` and **no count**. It contains 19
  `checks.ok(` call sites, one of which is an unreachable else-branch, so a
  passing run executes **18** checks — plus the 5 config-loader guards of
  `EVIDENCE_CONNECT.md` §7, exercised separately. The figure **"22/22"** in
  `docs/reports/m3-21`, in the m3-22 brief context and — the one that matters —
  in `docs/PLAN.md` item 18 is not reproducible and is not claimed by
  `EVIDENCE_CONNECT.md` itself, which states no count. The evidence is sound;
  the number quoted about it is not.

## 4. Config against the commissioned facts — pass-with-findings

`bridge/config/bridge.yaml`:

- `opcua.namespace_uris.server_interfaces: "http://www.siemens.com/simatic-s7-opcua"`
  — exact match to §2.1, §3.1 and §9.10. ✔
- `opcua.namespace_uris.interface: "http://DemoCell"` — exact, with the ADR 0006
  derivation and the rename consequence written beside it. ✔
- `nodes.interface_path` — a two-element list, each element naming its own
  namespace key; no index anywhere in the file, and the loader rejects an index
  in a URI slot, an index-bearing BrowseName, the pre-m3-21 shape, a missing
  second URI, and a last element outside the interface namespace. ✔
- `requested_session_timeout_ms: 10000`, keep-alive deliberately absent. ✔
- No threshold, tolerance, clamp, scale, offset, debounce or hold key. ✔

- **F6.** The endpoint is `opc.tcp://127.0.0.1:4840/amr-agent/celldouble/` — a
  loopback URL whose path segment says `celldouble`, in a file whose header says
  it is the only file that varies between the double and PLCSIM, and the
  security block below it does say *"'none' is the in-container test-double
  setting. For PLCSIM / hardware set …"*. So it is legible as a placeholder. But
  the endpoint key itself is the one place a reader stands at the moment of
  change, and its comment explains only the connection direction — it does not
  say "the commissioned endpoint is `opc.tcp://192.168.53.1:4840`". That value
  is recorded in four other files. One comment line at the point of edit would
  remove the last chance of the owner running the PLCSIM capture against the
  double.

## 5. Tracking coherence — pass-with-findings

- Every brief m3-14 … m3-22 has a report: 14, 15, 16, 17, 18, 19, 20, 21, 22 all
  present in `docs/reports/`. ✔
- m3-23 is issued in PLAN item 20 and queued under `## verifier` in TODO, with
  no report until this one. ✔
- No closed item survives in TODO. The three items TODO still carries are all
  genuinely open and each traces to a report: the `.gitattributes` shebang count
  (m3-21 OQ2 / m3-22 OQ1), the M6 interface name (m3-18 OQ1), the
  `DataBlocksGlobal` suppression (m3-18 OQ3). ✔
- `roadmap.md` says "Current gate: M3 — in progress", claims no M3 closure, and
  does not disagree with PLAN or TODO on gate state. ✔

- **F7.** `docs/PLAN.md` contradicts itself. Items 15–19 record m3-18 … m3-22 as
  *Closed 2026-07-27*, but the paragraph at the end still reads *"Remaining
  before the gate can close: **briefs m3-18 to m3-21**, then the owner's OB30
  program build …"*. This is precisely LESSONS 2026-07-27 ("an 'in progress' line
  survived its own closure"). The remainder is now owner-executed work plus this
  verification; no brief is outstanding.
- **F8.** `docs/PLAN.md` item 18 carries the unsupported "22/22 checks" of F5,
  and describes the two runs as "both clamp directions" where one of them is a
  grant *raised above* the request.

## 6. Attribution — pass

Twelve commits since `8d0ba7b`. Author and committer are `Ozkan Ceylan
<ozkannceylan@gmail.com>` on every one. Messages are conventional-commit,
imperative, one logical change each; none mentions AI, an assistant or tooling.
No `Co-Authored-By`, no generated-with footer. A diff-only grep of everything
added this session for `claude|anthropic|copilot|chatgpt|gpt|llm|co-authored|
generated with|ai assist|language model|prompt` returns hits only inside the
roster agent files, and only in the sentence *"Never mention AI assistance
anywhere in repository content"* — the prohibition itself. Two observations for
the owner, neither a breach of CLAUDE.md §7 as written:

- **F9.** `c82bc50` added `.claude/agents/*.md`, each with `model: opus`
  frontmatter. §7's rule covers commit messages, branch names, PR titles and PR
  bodies, and CLAUDE.md §7 already mandates tracking `.claude/settings.json`, so
  tracking the roster definitions is consistent with the owner's existing
  decision — but `model: opus` is the only vendor model identifier in tracked
  content, and a portfolio reader browsing `.claude/` will see it. Owner's call;
  flagged, not failed.
- **F10 (pre-existing).** Commits use the scope `bridge` (`feat(bridge)`,
  `docs(bridge)`), which is not in CLAUDE.md §7's valid-area list (plc, fleet,
  agv, sim, safety, interfaces, infra). ADR 0005 made `bridge/` a top-level layer
  and required a CLAUDE.md follow-up by the owner; §4 and the §5 roster were
  updated, §7's area list was not. The scope is right, the list is incomplete.
  CLAUDE.md is the owner's file.

## 7. Layer boundaries — pass

Per-commit file lists:

| Brief | Commit | Files |
|---|---|---|
| m3-18 | `89beeb1` | `docs/interfaces/opcua-nodes.md` + its report |
| m3-19 | `7625ceb` | `docs/interfaces/bridge-design.md` + its report |
| m3-20 | `4751d7e` | `bridge/EVIDENCE_LATENCY.md`, `bridge/EVIDENCE_SIGNAL_LOSS.md` + its report |
| m3-21 | `cac9868` | 13 files, all under `bridge/`, + its report |
| m3-22 | `b6f3de5` | `docs/interfaces/bridge-design.md` + its report |

No agent wrote outside its directory; every cross-directory need (the
`.gitattributes` comment, the TODO lines, the M6 interface name) was *requested
in a report* rather than made. ✔

**No process logic entered the bridge.** Reviewed the m3-21 diff of
`opcua_side.py`, `config.py` and `instrumentation.py` line by line:

- The keep-alive is the single timer, permitted explicitly by the brief and by
  §3.2. It reads the standard `Server/ServerStatus/State` node, applies the
  result to nothing, and skips its exchange when the cycle already touched the
  session — a comparison of two `time.monotonic_ns()` readings with no process
  value in it. Period is derived, never configured.
- `_keepalive_error` is a sticky flag, but it latches a *connection* verdict, not
  a process value: a failed exchange raises `SessionBroken` on the next cycle,
  which is exactly the detection row of `bridge-design.md` §8.1 ("a failed read
  or write, **or a session/keep-alive failure**, marks the session broken"). It
  is cleared only by a new `_connect`.
- `auto_reconnect=False` and the half-open-session close on a failed retry are
  session hygiene, not signal behaviour.
- Everything added to `config.py` is validation that *rejects* shapes; it
  computes nothing.
- No threshold, tolerance, latch on a process value, sequencer, interlock or
  hold-last-value appeared anywhere, and the loader still refuses an unknown key.

---

## open_questions

None that block. F1 and F2 are completeness items already owned elsewhere; F3,
F4, F6, F7, F8 are one-line corrections in files whose owning agents are the
bridge agent (F3, F4, F6), the infra/arch-docs agent (F7, F8); F9 and F10 are the
owner's, because CLAUDE.md and `.claude/` are the owner's files. Per my scope I
issue no follow-up work.

## next_suggested

The gate now waits only on owner-executed work. Advisory: fold F3/F4/F6 into
whatever bridge brief precedes the PLCSIM run, since the owner reads all three
files at that moment, and correct PLAN (F7, F8) before the next gate review.

---

# What remains owner-executed before M3 can close

Nothing agent-executable is outstanding. The list below is the brief's, corrected
against what this verification found.

1. **Build the OB30 program** per `plc/demo-cell/SPEC.md` — tags §3.2, then logic
   §6.1 onward — in the commissioned project: TIA Portal V21, PLCSIM Advanced
   V7.0, CPU 1513-1 PN firmware V3.1, OPC UA runtime licence *large*. Phase 0
   proves the endpoint and node exposure only; no program behaviour is evidenced
   yet by anything in this repository.

2. **Before starting the bridge, make exactly one config change**: set
   `opcua.endpoint` to `opc.tcp://192.168.53.1:4840`. Everything else stays as
   committed — `security_policy: none` with null certificate/key/username matches
   the commissioned server, `requested_session_timeout_ms: 10000` stays a
   request, both namespace URIs are already correct, and no index exists to
   change. *Added by this verification:* the endpoint key carries no comment
   naming that value (F6), and the Windows Time service is Stopped again (TODO
   "Clock") — re-run the resync, or set `w32time` to Automatic, before capturing
   anything timestamp-derived (LESSONS 2026-07-27).

3. **Run PLCSIM with the bridge and capture watch-table evidence for gate items
   (a) and (b)** — Gazebo sensor state visible as PLC input bits, and PLC output
   bits driving the Gazebo actuator, verified visually.

4. **`bridge/EVIDENCE_LATENCY.md` Section B**, all nine capture items, with these
   three qualifications:
   - **Item 1** is only partly answered by §B.0. Two elements phase 0 did not
     fix remain the owner's to confirm at measurement time: the CPU's
     **configured scan cycle**, and the **network path in use**, with the
     explicit confirmation that **Tailscale is not in it** (invariant 8).
   - **Item 5 means all *seven* inputs**, not six. The file's own scope note
     (line 23) says item 5 "should be read as 'all inputs'"; the input image has
     been seven nodes since `DemoCell/Input/PanelResetPressed` (m3-11, bridged in
     m3-13), so `BridgeHeartbeat` must be shown not advancing until all seven
     carry real samples.
   - **Item 9** is the connect capture: two `namespace … resolved to index N`
     lines with **PLCSIM's** indices, `browse path:
     Objects/<n>:ServerInterfaces/<m>:DemoCell`, `requested 10000 ms / granted
     <N> ms`, keep-alive `<N>/3` — **10.000 s if the CPU grants 30 000 ms**, a
     figure this verification reproduced independently — plus `all node DataTypes
     match opcua-nodes.md §9` and `15 nodes resolved`.

5. **`bridge/EVIDENCE_SIGNAL_LOSS.md` — correction to the brief's wording.** That
   file has **no PLCSIM measurement section** to fill. Its phase-0 subsection is
   an environment record, and the PLCSIM repeat of the four failure cases is
   tracked as **item 6 of `EVIDENCE_LATENCY.md` Section B**, including what the
   standard program *does* in each case (drop the cycle-running flag, command
   0.0, require a monitored edge-triggered reset, and never restart on a
   returning heartbeat alone). The repeat must be captured against the
   **seven-node** input image: the file's scope note assigns that to "m3-08 or
   the owner's PLCSIM run", and m3-08 was closed without its own brief (PLAN item
   8), so it is the owner's.

6. **Two rules that hold during the run.** The test double must not be running on
   the same endpoint (`bridge-design.md` §10), and
   `bridge/tools/check_connect_conformance.py` must **not** be pointed at PLCSIM
   — its idle test deliberately stops exercising the session. The owner's
   checklist is the closing section of `bridge/EVIDENCE_CONNECT.md`.

7. **A verifier pass on the captured evidence**, after which PLAN, TODO and
   `roadmap.md` close M3 together.
