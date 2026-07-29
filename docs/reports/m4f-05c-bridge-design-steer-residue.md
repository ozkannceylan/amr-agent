# Report m4f-05c — bridge-design steer-exemption residue

```
brief:               docs/briefs/m4f-05c-bridge-design-steer-residue.md
status:              done
files_changed:       [docs/interfaces/bridge-design.md,
                      docs/reports/m4f-05c-bridge-design-steer-residue.md]
invariants_touched:  none
open_questions:      none
next_suggested:      Verifier pass over the three steer-ruling commits (ae93667,
                     5797e17 and this one) as one change
```

## Done — two cells, both from the m4f-05b ready text

Verdict, owner and every other column untouched; no row added, moved or removed.

**§4.7 signal-map row 15**, Conversion cell:

> widening, rad unchanged. **No clamp and no centring** — both are the PLC's: it
> clamps to the mechanical range and drives the angle to `0.0` in the
> interlock-failed `ELSE`, like the other two setpoints (§10.6)

**§8 reconnect rule N4**, closing sentence. N4's argument is unchanged — the bridge
publishes what it reads and the decision is the PLC's — and only its example
inverts:

> Note that `ForkliftSteerAngleRef` **is** driven to `0.0` on a stop like the other
> two (`opcua-nodes.md` §10.6), so a reconnect into a stopped machine carries a
> centred steer: the bridge publishes whatever angle it reads, and that too is the
> PLC's decision

Diff is 2 changed lines, identical under `--ignore-cr-at-eol`, so both are real
content changes and not line-ending noise.

## The subject sweep — 10 hits, each read

Every whitespace-normalised occurrence of `[Ss]teer` across the whole file, which
subsumes all **3** occurrences of `ForkliftSteerAngleRef`. Each hit read for
dependency on the withdrawn exemption:

| # | Near line | What it is | Dependency |
|---|---|---|---|
| 1 | 8 | Scope table: "Forklift commissioning cell — traction, **steer**, fork, lidar" | None — a signal-group name |
| 2 | 78 | §1.1 row, *would-be behaviour* cell: "Clamping `ForkliftSteerAngleRef` … or centring it when the machine stops" | None — it names the temptation the bridge must resist, which the ruling does not change. Deliberately left as written |
| 3 | 78 | §1.1 row, *reason* cell | **Asserts the ruling** (corrected at 5797e17) |
| 4 | 335 | Diagnostics: "using them would let PLC state **steer** the transport" | None — the verb, not the axis. Surfaced and dismissed because a subject sweep matches the string, not the meaning |
| 5 | 359 | QoS table: `/forklift/cmd/steer_angle` publisher row | None — a topic name |
| 6 | 394 | §4.7 row 15: node name `Output/ForkliftSteerAngleRef` and topic `/forklift/cmd/steer_angle` | None — identifiers |
| 7 | 394 | §4.7 row 15, *conversion* cell | **Asserts the ruling** (corrected here) |
| 8 | 414 | Never-touched `Forklift/Hmi/` group list: `HmiSteerRequest` | None — the operator's request node, not the output setpoint. Its standing (outside read set, write allowlist and diagnostics) is unrelated to gating |
| 9 | 700 | §8 N4: node name `ForkliftSteerAngleRef` | None — identifier |
| 10 | 700 | §8 N4, closing sentence | **Asserts the ruling** (corrected here) |

**Zero remaining statements rest on the withdrawn exemption.** Confirmed a second
way, by counting the residue phrasings over the normalised file: `not gated`,
`never gated`, `deliberately *not* driven`, `does *not* centre`, `steer setpoint is
a position`, `forcing it to centre`, `hold the last angle` — **0 matches each**.
Three occurrences now assert the §10.6 ruling, three are identifiers, and four are
unrelated to the steer axis or to gating.

## Why the subject sweep was the right instrument

The phrasing sweep in m4f-01b found 1 of 3 dependent statements; this subject sweep
finds all 3 and additionally forces four unrelated hits to be read and dismissed on
the record. The two it had missed restated the exemption in their own words
("does *not* centre the steer on a stop", "deliberately *not* driven to zero by the
PLC"), which is exactly the failure the LESSONS entry now names. Cost of the
instrument: ten hits to read in one file. Cost of the alternative: two false
statements in a contract document and two extra briefs.

`bridge-design.md` and `opcua-nodes.md` §10.6 now agree in every place either
mentions the steer setpoint.
