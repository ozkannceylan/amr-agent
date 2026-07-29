# Report m4f-05 — bridge design addendum: forklift signal groups

brief:               docs/briefs/m4f-05-bridge-design-forklift.md
status:              done
files_changed:       docs/interfaces/bridge-design.md (revised);
                     docs/interfaces/opcua-nodes.md (§10.10 closing paragraph and
                     §10.12 item 2 — the requesting statements, updated in the same
                     change per LESSONS 2026-07-26);
                     docs/reports/m4f-05-bridge-design-forklift.md (this file)
invariants_touched:  none. Invariant 4 holds for both clients; invariant 6 is
                     strengthened, not weakened, by §4.10's rule that the bridge
                     never touches the HMI request group; invariant 10 is the
                     argument for the write allowlist and for not duplicating
                     §10.9's start values here; invariant 9's best-effort standing
                     is unchanged. No ADR proposal is raised.
open_questions:      five, listed below
next_suggested:      m4f-06 (bridge implementation) can proceed; §12 items 11 and
                     13 are its inbox.

---

## What landed in `bridge-design.md`

The document was M3-scope. It now carries two signal groups over one process and one
session, with every count scoped rather than deleted.

**The organising idea is §2.1, "the configured signal set".** The config declares which
groups a run carries; their union is the set every per-signal rule counts. Five rules
(G1–G5): an unconfigured group contributes nothing at all; every per-signal rule applies to
the configured set and to no other; groups are not a runtime mode; a group adds slots, not
kinds; and there is one heartbeat for the process, never one per group. The three
configurations and their counts are tabulated once and referred back to everywhere else —
cell only 7/1/6, forklift only 4/3/5, both 11/4/11, touching 15, 13 and 27 nodes of the
interface's 33.

**The three additions the coordinator asked for, all in scope as bridge-design content:**

1. **R3 is now "every input in the *configured* signal set"** (§6.1), with R4, R5, §6.2's
   predicate and §7.4 scoped the same way. The rationale is written out: the literal "all
   seven" was correct for exactly one configuration and silently wrong for every other — a
   forklift-only run would have stalled the heartbeat forever waiting for conveyor topics
   it was never configured to carry. The tightening R3 exists for is unchanged; only the
   definition of "every" moved from a literal to the config.
2. **The carried §8.1 restart row** — in fact three rows: *Restart detection* (read the
   bridge's own `BridgeHeartbeat` back once per cycle, exact inequality against what this
   session last wrote, because a wrap is not a restart), *Restart repair* (invalidate the
   per-session write cache, rewrite every configured slot carrying a real sample in the
   same cycle, R1 untouched), and *Restart residual* (a revert landing on the last written
   value is invisible — one value in 65536 — stated rather than patched). Supported by a
   new **§7.3 case E** (server restart that does *not* drop the session: healthy session,
   reverted input image, "the dangerous one: nothing looks wrong"), **§4.3 row 9r**, and
   **§9.2 RB** so the step's cost is measured rather than asserted. The bridge's log line
   citing "§8.1" now resolves to a rule that exists.
   A point that only arises now there are two clients: the heartbeat is a valid witness
   *because* it is in the bridge's writable set and in no other's — the HMI's counter is
   `Forklift/Link/HmiHeartbeat`, which the bridge never touches. A witness both clients
   could write would prove nothing.
3. **§2's cycle description is current**: the ASCII cycle is now `0. read own heartbeat
   back → 1. read Outputs → 2. publish → 3. write Inputs → 4. write Heartbeat, last`, with
   a paragraph on why step 0 exists.

**The HMI rule and its allowlist consequence** (§4.10, plus rows in §1, §3 and §1.1): the
bridge never reads or writes `Forklift/Hmi/*` or `Forklift/Link/HmiHeartbeat`, in any
configuration, in either direction. Stated as a design rule because *the server would allow
it* — §10.3 marks that group writable and the CPU runs with access control disabled, so the
refusal must come from the bridge. Consequences enumerated: the allowlist is **derived**
from the configured groups (never a second hand-maintained list), holds exactly 12 keys with
both groups configured, the write helper's rejection is a defect signal rather than a
skipped write, the config loader rejects an `Hmi` node in a writable position, and the
negative test is only meaningful against a server that would have accepted the write.

**Signal map**: §4.7 (rows 10–13, plant → PLC), §4.8 (rows 14–16, PLC → plant), §4.9
(forklift diagnostics), §4.10. Row numbers continue rather than restart, so existing
references such as "signal map row 5" keep their meaning, and §4.5/§4.6 stay single tables
covering both groups. Two properties are called out rather than left to be inferred: the
forklift source is *slower* than the cycle (10 Hz against 20 Hz, so nothing is decimated and
a repeated write is not a freshness claim), and row 12 is the one input whose `TRUE` is
non-permissive — carried uninverted, because inverting is a §1.1 violation.

**§1.1 gained a forklift block** of seven would-be behaviours with their correct owners:
scaling a fraction request into a speed, zeroing traction on the field bit, inverting row
12, deriving an obstacle verdict from the diagnostic distance, clamping or centring the
steer setpoint, reading an `Hmi` request at all, and republishing `0.0` when the HMI link
drops. The "permitted, and exhaustive" sentence now also admits the heartbeat read-back.

**§10 (test double)** must serve all 33 nodes including the six the bridge never touches; it
serves the `Hmi/` group **writable** (so the allowlist test is falsifiable) and
`Forklift/Output/*` **not** writable (so the server-side half of the two-enforcement
arrangement is exercised); and it can revert its input values without dropping the session,
which is the only way to test §8.1 at all. Two new rows say what it does not prove: no
forklift PLC content, and it is **not the HMI** — serving those nodes is not playing that
client.

**§2.2 lists what the forklift group does not change** — the no-logic rule, the 20 Hz cycle,
one session/heartbeat/verdict, poll-not-subscribe, slots-not-queues, reconnect and
rewrite-on-restart semantics (now covering every configured slot), no-auto-resume per slot,
per-session evidence files, client-only, dependencies, and the two-namespace browse path.

## Staleness sweep (whitespace-normalised, per LESSONS 2026-07-27)

Statements found by independent search rather than from the brief's list, and corrected in
place:

| Where | Was | Now |
|---|---|---|
| §5.1 | "The **fifteen-node** `DemoCell/` address space" | per-configuration counts, 15 / 12 + shared heartbeat / 27 |
| §6.3 | "the DB start values are **only applied at a PLC cold restart**" | corrected: the 2026-07-28 *warm* restart reverted every input, so a restart can land either way and neither is attributable to the plant — which is why §8.1 now carries a restart row |
| §9.4 | "the **four** failure modes of §7.3" | "failure modes **A–D**", since case E post-dates that capture; `bridge/EVIDENCE_LIFECYCLE.md` added to the table as the file that covers E |
| §9.4 | `evidence/latency-<YYYY-MM-DD>.csv.gz` | the per-session stem naming (LESSONS 2026-07-28), with the rule that a capture is archived only after its writer stops |
| §3.1 | tree presented wholly as owner-verified | the `Forklift/` line marked a **design value** until read back out of TIA; new N7 records that the forklift adds a level, not a namespace |
| §12 item 8 | "corrected: now reads (M5, deferred)" | re-opened — ADR 0008 D1 shifted the gate, so `sim/README.md` now names the wrong one (item 15, requested) |
| §2.1 table | forklift-only "nodes touched" 12 | **13** — the shared heartbeat is a §9 node every configuration uses; arithmetic error caught in review, and §5.1 reworded to match |

Checked and deliberately **not** changed: the "all seven" statements in `bridge/EVIDENCE_*`
and in `docs/reports/*` are as-run records of cell-only runs and remain accurate as history;
`plc/demo-cell/SPEC.md`'s "seven input values" statements are correctly scoped to the M3
cell. `handshake-tables.md` and `vda5050-subset.md` do not mention the bridge.

## Requesting documents updated in the same change

`opcua-nodes.md` §10.10 said `bridge-design.md` "is M3-scope today and does not yet describe
the forklift path", and §10.12 item 2 requested exactly this work. Both now point at the
delivered sections; item 2 is marked closed and quotes what R3 became. Without this the two
documents in the same directory would have contradicted each other — the failure LESSONS
2026-07-26 records.

## Open questions

1. **Everything in the `Forklift/` browse path is a design value** until the owner reads it
   back out of TIA (`opcua-nodes.md` §10.2 step 6). §3.1 marks it; no gate criterion may
   rest on it before then. Carried as §12 item 10.
2. **No `ForkliftDriveFault` node**, so §7.3 case D has no PLC-visible verdict on the
   forklift plant. Not the bridge's to fix — detecting a frozen plant needs a timer and a
   threshold. Mirrors §10.12 item 3; owner decision. §12 item 12.
3. **`bridge/EVIDENCE_LATENCY.md` carries a standing request** for the §8.1 row, resolved
   here. That file is outside this agent's write scope, so `bridge/` must mark its own
   request satisfied in m4f-06. §12 item 13.
4. **Two scope-stale statements outside `docs/interfaces/`**: `plc/demo-cell/SPEC.md` §4.3
   "Nothing else goes into the interface" (already in `docs/TODO.md`), and
   `bridge/README.md` / `bridge/EVIDENCE_LIFECYCLE.md` "the only node outside `Input/`",
   which stays defensible under the revised §9.7 wording but should be confirmed against
   §4.10. Requested, not edited. §12 item 14.
5. **`agv/forklift/README.md` does not exist in the tree yet** — `agv/forklift/` is present
   but untracked, presumably in flight under a concurrent brief. This document cites that
   README as the vehicle layer's topic contract because `opcua-nodes.md` §10.10 already
   does; the citation is forward-looking. The topic names in §4.7/§4.8 were taken from the
   authoritative §10.10, not from the untracked files.

## Not done, deliberately

No bridge code, config or test-double file was touched (the brief forbids it, and m4f-06
owns them). The cell slot definitions are unchanged. No value type beyond Real/Bool/UInt16
appears. §12 item 11 lists precisely what the shipped code must change to match this
document — the derived allowlist, R3's count, the reconnect and restart refresh scope, and
the log lines that still name `DemoCell/Input` — so the implementation brief inherits a
checklist rather than a reading task.
