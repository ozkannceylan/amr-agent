# Report m3-24 — evidence and config wording corrections from m3-23

```
brief:               docs/briefs/m3-24-evidence-wording-corrections.md
status:              done
files_changed:       bridge/EVIDENCE_LATENCY.md
                     bridge/EVIDENCE_SIGNAL_LOSS.md
                     bridge/config/bridge.yaml
                     docs/reports/m3-24-evidence-wording-corrections.md (this file)
invariants_touched:  none
```

Wording only. No measured figure, no log excerpt and no line of code was
changed: `git diff --numstat` over `bridge/` is `1/1`, `7/4`, `5/0` and matches
`git diff --ignore-cr-at-eol --numstat` exactly, so every changed line is real
content and not a line-ending artefact. Nothing under `bridge/evidence/` was
touched.

---

## 1. Independent sweep before editing

Whitespace-normalised search (`\s+` collapsed before matching, per LESSONS
2026-07-27) over every tracked file under `bridge/`, for `clamp`, `clamps`,
`ceiling`, `caps`, `capped`, `maximum session`, `limits it`, `30 000 ms`,
`30000 ms`, `22/22`, `22 / 22`, `checks` and `check count`. The brief's
enumeration proved exact: **three** survivals of the one-directional framing,
all three in the two evidence files, all three now corrected.

Every other `clamp` hit is correct as written and was left alone:

| Location | Why it stays |
|---|---|
| `amr_bridge/opcua_side.py:213` `"clamped BELOW the request"` | a runtime verdict string, one of three branches (`below` / `above` / `as requested`); code behaviour is out of scope and it is already two-directional |
| `amr_bridge/ros_side.py`, `amr_bridge/__init__.py`, `config/bridge.yaml:12` | the *no-clamp* prohibitions of the no-logic rule, not claims about the server |
| `evidence/connect-conformance-2026-07-27.csv` (3 rows) | recorded tool output — forbidden to change, and true of that run |
| `EVIDENCE_CONNECT.md` §1 heading and the §3/§5 log excerpts | that run's actual direction; §2 "grant raised ABOVE the request" carries the other, and the "What this does not establish" table already says PLCSIM's grant "may land either side of it" |
| `README.md:217-222`, `test_double/README.md` row 2, `test_double/plc_test_double.py:110-114, 313-317` | the double's own configured grant window; each already names `--min-session-timeout-ms 30000` as the way to reproduce the other direction |

## 2. F3 — `EVIDENCE_SIGNAL_LOSS.md`, Case A prose

*"This server **clamps** session timeout to 30 000 ms and the bridge requests
10 000 ms"* implied a 30 000 ms ceiling that a 10 000 ms request passes
untouched. Replaced with the two-directional statement, modelled on
`EVIDENCE_LATENCY.md` §B.0.3 item 2 as the brief directs: the server **revises**
rather than caps, it granted 30 000 ms for a 3 600 000 ms request, the grant for
the bridge's 10 000 ms request may land either side of that request and is not
known until the run reads it back, and the session hold time after a kill is
bounded by the **granted** value. Both cross-references (`Section B item 7`,
plus `§B.0.3`) are now on the sentence.

## 3. F4 — the "the server clamps it" facts-table row, both files

The row appears identically in `EVIDENCE_LATENCY.md` §B.0 and
`EVIDENCE_SIGNAL_LOSS.md`. Both now read:

> requested **3 600 000 ms**, granted **30 000 ms** — the server **revises** the
> request; a revision downwards in this instance, and the grant for the bridge's
> own request may land either side of it

with the direction reference pointing at `§B.0.3` in `EVIDENCE_LATENCY.md` and at
`` `EVIDENCE_LATENCY.md` §B.0.3 `` in `EVIDENCE_SIGNAL_LOSS.md`. The two figures
are untouched; only the property claimed from them changed. This now matches
`bridge-design.md` §3.2 ("a clamp downwards there, but the rules below hold in
whichever direction") and removes the disagreement m3-23 F3 found between the
two files.

## 4. F5 — the check count

**No count exists anywhere in `bridge/`**, so nothing was removed. The sweep for
`22/22`, `22 / 22`, `N checks` and `check count` returns zero prose hits across
all tracked `bridge/` files; `EVIDENCE_CONNECT.md` claims no count, and
`Checks.result()` prints only `RESULT: PASS` (on failure, `FAIL (<failures>)` —
a failure count, never a total).

Confirmed by running the harness read-only rather than by reading the code
alone. WSL2 Ubuntu, venv `/home/ozkan/amr-bridge-venv` (`asyncua 2.0.1`),
isolated with `ROS_DOMAIN_ID=94` and `GZ_PARTITION=m324wording` on loopback port
**4846**, evidence redirected to `/tmp/m324_conf.csv` so no repository file was
written. Only the double this run started was killed. Output ends:

```
   ok   a wrong interface URI raises NamespaceNotFound — namespace 'http://NoSuchNamespace' (interface) is not published by opc

RESULT: PASS
EXIT=0
```

The run also reproduces the committed §1 capture value for value — indices 5/6,
15 nodes, four `BadNoMatch` paths, requested 10000 / granted 8000, keep-alive
2.667 s, measured spacing `['2.668', '2.668', '2.670']` s — which additionally
confirms `bridge.yaml` still loads after the comment edit of §5. The printed
`ok` lines number **18**, matching m3-23's static count; that figure is stated
here as this run's output and deliberately **not** written into any `bridge/`
file.

## 5. F6 — the endpoint comment in `bridge.yaml`

The `opcua.endpoint` key now carries, at the point of edit, the commissioned
value the owner swaps in:

```yaml
  # The bridge connects OUT to this endpoint. It never listens (invariant 4).
  # The value below is the test double. For the PLCSIM run, swap it for the
  # commissioned endpoint  opc.tcp://192.168.53.1:4840  (commissioning phase 0,
  # EVIDENCE_LATENCY.md §B.0) — that swap is the only edit this file needs
  # between the double and PLCSIM, and the double must not be running on the
  # same endpoint (bridge-design.md §10).
  endpoint: "opc.tcp://127.0.0.1:4840/amr-agent/celldouble/"
```

Five comment lines, no key added, no value changed, no new key for the loader to
reject. The `bridge-design.md` §10 rule is repeated here because it is the rule
that is broken *by* getting this line wrong.

---

## open_questions

None. Two notes, neither blocking and neither mine to act on:

1. `EVIDENCE_LATENCY.md` §B.0.3 item 2 — the brief's designated reference, and
   therefore untouched — says the server "revises in the *upward* direction
   too". That is true relative to the bridge's configured **10 000 ms** request
   (30 000 > 10 000) but reads oddly next to the observed 3 600 000 → 30 000
   revision on the same line, which is downwards. The paragraph's conclusion
   ("the grant … may land either side") is correct either way. Flagged for the
   next brief that has §B.0.3 in scope rather than edited here.
2. `docs/PLAN.md` item 18 and `docs/reports/m3-21` still carry the "22/22
   checks" figure of F5. Out of my write scope and explicitly assigned to the
   orchestrator by this brief's `forbidden` list.

## next_suggested

The three files the owner reads immediately before the PLCSIM run are now
consistent with each other and with `bridge-design.md` §3.2; M3 waits only on
owner-executed work and the PLAN correction.
