# Report m4f-01c — HMI shutdown and operator-liveness rules

```
brief:               docs/briefs/m4f-01c-hmi-shutdown-liveness-rules.md
status:              done
files_changed:
  - docs/interfaces/opcua-nodes.md          (edited) §10.8 H5 rewritten, H6 added,
                                            four prose blocks and one constants
                                            table; §10.12 item 8 added
  - docs/reports/m4f-01c-hmi-shutdown-liveness-rules.md   (new) this report
invariants_touched:  none
open_questions:      five, listed below
next_suggested:      Brief `hmi/` to implement H6 per §10.12 item 8 — one poll
                     timestamp, one named constant, the existing deadman, the
                     two-Bool re-arm. H5 needs no code.
```

## What was ruled

**H5 — the shutdown split is confirmed as the rule, with four clauses added.** The behaviour
`m4f-07` implemented is unchanged: a **clean shutdown** writes no farewell value and zeroes
nothing, so the server is left holding a live-looking demand under a stopped counter — the
property the watchdog exists to catch, and the one `EVIDENCE_HMI.md` §B.8 shows the PLC catching
650 ms later; a **backend fault or dropped session is not a shutdown** and fires the deadman
first, so the single final write carries the current state of the controls, which is rest. The
ruling adds what was previously reached by analogy:

| # | Added clause | Who satisfies it today |
|---|---|---|
| 1 | H5's "beyond the current state of its controls" was written about *reconnect*; it now scopes the fault path explicitly | wording only — no behaviour moves |
| 2 | One bounded attempt, **never retried** | `hmi/` as built (`_final_zeros_attempt`, one call under a timeout) |
| 3 | The counter stops **before** the final write, so it can never be read as a cycle — the deliberate inverse of H3 | `hmi/` as built |
| 4 | **No PLC behaviour may distinguish the two paths** — `bridge-design.md` §7.3's A/B rule at this boundary | `plc/forklift/SPEC.md` as written: it reacts to `HmiLinkOk` alone and evaluates no request while that verdict is `FALSE` |

Nothing was deleted. The branch `m4f-07` offered to remove — the fault-path write — is kept,
because what it writes is not a farewell value but the controls' actual state after a release,
which keeps this rule on the same side of the no-invented-values line the bridge is held to.

**H6 — operator liveness, new.** The browser's unconditional `GET /state` at 200 ms doubles as a
liveness beacon; any HTTP request from the page refreshes it. Stale for **`UI_POLL_STALE_TIME`,
five poll periods, `1.0 s`**, and the backend fires the **existing** deadman — all five requests
to rest, the enable included — **while the write cycle and the heartbeat continue**. The process
is healthy; what is gone is the page. Nothing latches, no reset is demanded, and the PLC is told
nothing new: it sees requests at rest under a live heartbeat, a state §10.6 already handles.
Written as process behaviour and named as not a safety function (invariant 1, ADR 0008 D3); it
is invariant 2's degraded-mode pattern one level up, at the operator boundary.

Four things the rule carries beyond the window and the reaction:

- **The derivation is the multiple, not the millisecond.** A new table sets the three stale
  windows side by side — `HEARTBEAT_STALE_TIME` `T#500ms` (≈10 missed beats),
  `HMI_STALE_TIME` `T#600ms` (3 × the floor H2 contractually honours), `UI_POLL_STALE_TIME`
  `1.0 s` (5 × the poll period) — and no two share a derivation. Five rather than three because a
  browser honours no floor: `setInterval` is best effort, so the same rule lands on a larger
  multiple from a weaker premise. Its own constant, never shared with `HMI_STALE_TIME` (P4 one
  level up).
- **The cost is stated, and stated as not a safety distance.** One second is the longest a demand
  from an absent page can stand — at `TRACTION_SPEED_MAX` `1.00` m/s, at most a metre of travel.
- **What the poll does not prove.** It proves the page is alive, not that a person is in front of
  it. H6 closes the crashed, frozen, closed or disconnected browser — `EVIDENCE_HMI.md` §D's "a
  browser that crashes with the joystick held" — and the rest is stated rather than covered.
- **Recovery is a release, not a resume.** The three Reals come back as soon as the page posts;
  each Bool only once that page has been seen to send it low, so a page that thaws with the
  enable still asserted cannot produce a `FALSE → TRUE` edge no operator made. This is P6's
  per-link-session arming applied to the HMI's own input channel, and in the ordinary case it
  costs nothing, because the page already returns everything to rest on blur, hide and unload.

**No node, no count, no start value, no P-rule moved.** §10.3's 18 nodes, §10.9's start values and
the qualification rule are untouched, which is what makes H6 takeable while the group is being
commissioned. §10.12 item 8 records the implementation request against `hmi/` and states that H5
needs no code.

## Sweep

Subject sweep over the whole repository, whitespace-normalised (LESSONS 2026-07-27, 2026-07-29),
on *farewell*, *zeroes nothing*, *shutdown*, *no timer*, *no interlock*, *status poll*, *liveness
beacon*, *browser liveness*, *H5*, *H6*, `HMI_STALE_TIME`, `UI_POLL_STALE_TIME`, and every
rule-range phrasing (*H1–H5*, *five rules*). Read for dependency, not for the string:

- `bridge-design.md`'s farewell/shutdown statements (§7.3 B, §8.3 N5, §1.1) are all about the
  **bridge**. They are now cited by §10.8 as the precedent and needed no change.
- `vda5050-subset.md` §237's graceful-shutdown `OFFLINE` publish is a different contract on a
  different transport — no dependency either way.
- `m4f-05`'s "five rules" is bridge-design's G1–G5 group rules, not §10.8's H-rules.
- No document enumerates the H-rules by count, so adding H6 broke no range reference.
- The only live tension found is §10.1's "no timer" row — open question 1.

## Open questions

1. **§10.1's "No logic in either client" row still reads "no timer", flatly.** The tension
   predates this brief: H2 already requires the HMI to time its own cycle, and `hmi_server.py`
   carries two such timers. H6 adds a third of the same kind — over the client's own input
   channel. §10.8 now states the reading explicitly and names §10.1 while doing it, so the two do
   not disagree silently, but **§10.1 itself was not edited: the brief forbids changing any other
   section 10 rule.** Proposed one-clause amendment for a future brief: *"…no timer over a process
   value — a timer over this client's own cycle or its own input channel is a different thing and
   is required by §10.8 H2 and H6…"*.
2. **`hmi/` follow-ups beyond implementing H6.** `hmi/EVIDENCE_HMI.md` §D describes the
   browser-crash gap as "carried as an open item rather than closed with an invented timeout", and
   `hmi_server.py`'s `_final_zeros_attempt` docstring frames H5 as a reconciliation it is
   performing. Both describe questions that are now ruled. A wording refresh belongs with the H6
   implementation, in that layer.
3. **The requesting document is a report, and was not edited.** `m4f-07`'s open questions 1 and 2
   are answered here. Reports are records of a completed task and `docs/reports/` is not this
   agent's write scope beyond its own report, so the trail is closed from the contract side
   instead: §10.12 item 8 cites the report and the evidence file by name.
4. **`m4f-07` open question 4 is still open.** It asked `docs/interfaces/` for a view on
   `STEER_REQUEST_MAX_RAD = 1.31` living as a named constant in HMI code rather than as a node or
   a config key. This brief did not carry it and it was not ruled here — it needs its own brief or
   an explicit no-change ruling.
5. **`docs/TODO.md` and `docs/PLAN.md` carry m4f-01c as in flight.** Neither is this agent's to
   edit; closing them is the orchestrator's, per CLAUDE.md §11.
