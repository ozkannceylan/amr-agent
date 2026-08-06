# EVIDENCE — the warning-field slot, and the silence it converts into a value

**What this file is.** The dated capture of the first runs of the bridge slot
that carries the warning-field verdict to the PLC —
`DemoCell/Forklift/Warning/ForkliftWarningFieldOccupied` (`opcua-nodes.md` §13,
`bridge-design.md` §4.11 row 23) — and of the one property that slot exists for:

> **A `FALSE` on that node is always a fresh claim by a live bridge, never a
> leftover.**

The producer publishes at its 20 Hz evaluation tick **so that its absence is
visible**; an OPC UA node holds its last written value, so the seam is by
construction the republishing layer that rule exists to defeat (LESSONS
2026-08-04). The slot answers by making the last layer that can observe the
silence **assert** it.

Written **as each observation landed**, run by run.

---

## 0. Environment, and what qualifies every figure

| Item | Value |
|---|---|
| Date | **2026-08-06**, 16:44–16:50 UTC |
| Server | **The test double**, `bridge/test_double/plc_test_double.py`, extended in this same round to serve `opcua-nodes.md` §12 and §13 (`bridge-design.md` §12 item 17). **Not a PLC and not a model of one** |
| Controller | **None. Nothing in this file was run against PLCSIM Advanced, the CPU or TIA Portal.** The node does not exist on the controller yet — `plc/forklift/TIA-BUILD-PROCEDURE.md` chunk X creates it after step 338 — and the owner was building chunk X while these runs were taken |
| Bridge host | WSL2 on the owner's Windows machine, Ubuntu 24.04, ROS 2 Jazzy, `rmw_fastrtps_cpp`; `~/amr-bridge-venv` (`asyncua==2.0.1`) |
| Isolation | `ROS_DOMAIN_ID=91` throughout — a second session held domain 51 on this machine, and the two never met. No simulator was run by this session (LESSONS 2026-07-30) |
| Machine state | `load average 0.22 0.30 0.53` at the start of w1, recorded rather than assumed |
| Producer | **`bridge/tools/warning_stimulus.py`, a scripted stand-in**, not `agv/forklift/scripts/field_evaluation.py`. It publishes the same topic at the same 20 Hz tick with the same QoS and evaluates nothing |
| Independent witness | `bridge/tools/observe_warning_node.py` — a **second OPC UA client on its own session**, polling at 20 Hz. It writes nothing. Every figure it reports is quantised by its own 50 ms poll and the runs say so |

**What no figure here is.** Not a safety figure. The warning verdict on this
seam is **process data** (`opcua-nodes.md` §13.1, ADR 0011 D5, invariant 1); the
safe copy of the same verdict rides the stand-in writer path and never touches
this server. No PL, SIL, Category or PFH is claimed for anything in this file.
And nothing here is evidence about `plc/forklift/SPEC.md` §14.16: the double
runs no program and forms no verdict.

### 0.1 The window, and where its value comes from

`opcua-nodes.md` §13.2 **W1** rules the *rule*, not a number: the window is *"the
bridge's own named constant, bounded below by the producer's 50 ms tick, never
shared with any other window"*. The constant is
`amr_bridge.config.WARNING_FIELD_STALE_MAX_S`:

| | |
|---|---|
| Rule | **ten of the producer's own ticks** (`WARNING_STALE_TICK_MULTIPLE = 10`) |
| Producer tick | 50 ms — `agv/forklift/config.yaml` `field.evaluate_hz = 20.0` |
| Value in force | **0.500 s**, derived, not typed |
| Shared with | **nothing.** It is not `HEARTBEAT_STALE_TIME` (PLC, 500 ms, ten missed *heartbeats*), not `HMI_STALE_TIME` (600 ms), not `UI_POLL_STALE_TIME` (1.0 s) and not `FIELD_LINK_STALE_MAX` (1.0 s, the stand-in writer, a different transport and the *protective* verdict) |
| Bound on the reaction | window + one bridge cycle = **0.550 s** |

**The multiple is the rule and the millisecond is derived from it** (the §10.8
P3 discipline). It is a **design value** in exactly the sense LESSONS
2026-07-27 fixes: nothing has yet measured the *real* producer's worst-case
inter-arrival under simulator load, so the multiple is owed a commissioning
measurement, and if that measurement exceeds the window the multiple is
re-derived from it rather than the tick being quietly reinterpreted. Both runs
below ran their whole live phases with **zero** false assertions, which bounds
nothing about the real producer and is stated as such.

---

## 1. Run w1 — the verdict both ways, the silence, and the bridge's own death

`m555-w1-*`, 2026-08-06 16:44:02–16:45:20 UTC. Stack: the double on
`opc.tcp://127.0.0.1:4845`, six `ros2 topic pub` fillers for the other six input
slots, the bridge on `bridge/config/bridge-double-m5.yaml`, the OPC UA witness,
the vehicle-side envelope witness, and the scripted producer.

The bridge printed its own configured set, and it is derived rather than
declared anywhere:

```
configured signal set: forklift+envelope+warning — forklift 4in/3out/5diag
  (opcua-nodes.md §10), envelope 2in/4out/1diag (opcua-nodes.md §12),
  warning 1in/0out/0diag (opcua-nodes.md §13); 7 input slots, 7 output slots,
  6 diagnostics, 21 nodes touched, write allowlist 8 keys;
  silence rule: ForkliftWarningFieldOccupied asserts True after 0.500s of
  silence (opcua-nodes.md §13.2 W1)
startup rule R3 satisfied: all 7 input nodes of the configured set
  (forklift+envelope+warning) carry a real plant sample; heartbeat begins
  advancing at 1
```

**R3 counted seven.** The warning slot is an input of the configured set like
any other, so the heartbeat was withheld until it too carried a real sample —
the rule took its "every" from the configured set and no number is written down
anywhere (§2.1 G2). The write allowlist grew by **exactly one key**, derived.

### 1.1 The easy direction, which is also the positive control

The stimulus ran `occupied:4, clear:4, silence:4, clear:4, occupied:3, clear:25`.
Every live phase reached the node, in both directions, and the double's own
server-side observation — taken by the server, not by the client that wrote it —
records the column changing exactly six times:

```
ForkliftWarningFieldOccupied  distinct-in-order: True, False, True, False, True, False
```

This is the positive control the silence phase needs (LESSONS 2026-08-06):
**the same pipeline, in the same run, is seen delivering `FALSE`**, so a node
that later reads occupied cannot be explained by a dead publisher, a wrong topic
name or a mismatched QoS. `warning_stimulus.py` refuses outright to run a script
whose `silence` phase has no live phase in front of it, and refuses to publish
at all if no subscriber appears — a stimulus that cannot apply its stimulus
fails loud rather than returning a result (LESSONS 2026-08-06):

```
STIMULUS ABORTED: a `silence` phase must be preceded by a live phase, so the run
carries its own positive control …
```

### 1.2 The direction that matters — silence becomes an explicit `TRUE`

The producer stopped publishing. Nothing else changed: the bridge, the double,
the session and the other six slots all continued.

| Reference point | Clock | Value |
|---|---|---|
| Last message published before the silence | stimulus, `CLOCK_MONOTONIC` | `295211.111968` is the phase boundary; the last message went one 50 ms tick before it |
| The bridge's asserted write completes | bridge evidence CSV, `L2` row, same clock | `295211.604639` |
| **Boundary → asserted `TRUE` on the node** | differenced against itself (§9.1 C1/C2) | **492.7 ms** |
| **Age of the last received sample at the moment of assertion** | the bridge's own `silence` row | **0.542 s** |
| Bound (window 0.500 s + one 50 ms cycle) | | **0.550 s** — met |

The bridge said so in its own words, unprompted:

```
SILENCE on ForkliftWarningFieldOccupied: no sample for 0.542 s, past the 0.500 s
  window — writing the asserted True (opcua-nodes.md §13.2 W1). A read of this
  node is never an implied clear: the silence is asserted, not held
```

and, when the producer came back:

```
ForkliftWarningFieldOccupied fresh again after 0.014 s: the slot's own value is
  carried once more
```

**The write is in the evidence as a write, and it is labelled as one that no
producer sent:**

```
L2 ForkliftWarningFieldOccupied  t_end=295211604638944  value=True
   note: asserted on silence, not a received sample (§13.2 W1)
```

**Confirmed on a second session, by a client that cannot write the node.** The
witness saw the node hold `FALSE` for **4.517 s** across a clear phase that was
**4.037 s** long — so it read `FALSE` for **0.480 s ± 0.050 s** into the silence
and then read `TRUE`, which is the same event measured by a different process
through a different session.

### 1.3 The failure the slot cannot cover, and the term that does — W2 and W5

The bridge was sent `SIGTERM` **while the producer was alive and publishing
`clear`**, so the node froze at `FALSE`: the one failure a silence rule inside
the bridge can never catch, because the layer that would assert is the layer
that died.

| | |
|---|---|
| Last change of `BridgeHeartbeat` seen by the witness | `t = 27.3608` |
| The consumer's own verdict falls (`bridgeLinkOk` → `FALSE`) | `t = 27.8747` |
| **Detection** | **0.514 s** (PLC window `HEARTBEAT_STALE_TIME` 500 ms; witness poll 50 ms) |
| Node value for the rest of the run | **`0` in all 663 remaining samples** — frozen `FALSE` for **34.6 s** |
| **`node OR NOT bridgeLinkOk`** | **`1` in all 663** |

**The node lied for 0.514 s and the consumer's term did not.** That is W2
exactly: the verdict that catches a frozen node is formed **outside** the node,
and it boots `FALSE` — the witness's model shows `linkOk = 0` from its first
sample until the counter had been *seen to change* (`t = 4.4662`), which is the
boot polarity LESSONS 2026-07-28 fixes and not "not yet proven stale".

**The residual, stated rather than hidden (W5):** between the bridge's death and
the link verdict falling, a `FALSE` on this node stands. Measured here at
**0.514 s**, bounded by the PLC's own `HEARTBEAT_STALE_TIME` plus its scan. The
process chain accepts it; the independent backstop for exactly that window is
the F-side monitor on the writer path, which demands the stop on its own
measurement whichever way this seam fails.

> **What the witness's `bridgeLinkOk` is not.** It is a **model of the PLC's
> term** written into a test instrument so this run could show the term catching
> what the node cannot. The real term is `#warningFieldOccupied := node OR NOT
> #bridgeLinkOk` in the standard program, and nothing in this file is evidence
> about that program.

### 1.4 The envelope group, re-run in the same process

The change adds a group; it must not disturb the one proven five times over
against the live CPU two tasks ago (`EVIDENCE_ENVELOPE_BRIDGE.md`). Two
independent statements:

1. **By construction.** `bridge/config/bridge.yaml` is **byte-identical** to the
   committed file (`git diff` empty), the `envelope` group definition is
   untouched, and the warning group is a *fourth* group that file does not
   declare — so a run of the committed configuration against the CPU resolves
   the same 20 nodes, writes the same 7 keys and carries the same 6 slots as
   before. Nothing in the live evidence is invalidated, and nothing in it was
   re-taken: **no client of this session touched the controller.**
2. **By observation.** In run w1 the envelope group crossed the new code, in the
   same process as the new slot, driven through the double's S1 back door:

| Element | Withdrawn → permissive | Permissive → withdrawn |
|---|---|---|
| `mode_in_force` | `t = 9.5284` → `2` | `t = 17.5788` → `0` |
| `motion_enable` | `t = 9.5287` → `1` | `t = 17.5791` → `0` |
| `speed_ceiling` | `t = 9.5291` → `0.6000000238418579` | `t = 17.5794` → `0.0` |
| `equipment_permit` | `t = 9.5294` → `1` | `t = 17.5796` → `0` |
| **Arrival spread** | **1.0 ms** | **0.8 ms** |

The four elements still arrive inside one bridge cycle and one poll phase, and
the ceiling still arrives as the **unrounded** `float64` widening of the served
`Real` 0.6 — `0.6000000238418579`, the same value the live runs carry. **This is
a double, not a PLC**: the spread is a property of the bridge's cycle and is
comparable in kind, not in value, with the live 1.2–2.2 ms.

3. **The eight nodes the bridge must never touch stayed untouched**, observed by
   the server rather than asserted: `HmiTractionRequest 0.0`,
   `HmiDriveModeRequest 0`, `HmiProcessStopRequest True`, `HmiHeartbeat 0` — each
   one distinct value for the whole run, each served *writable* so the refusal is
   the bridge's own and not the server's.

---

## 2. Run w3 — the server restart, and the repair that must not undo the assertion

`m555-w3-*`, 2026-08-06 16:48:33–16:49:34 UTC. Same shape, its own port and its
own evidence files, with the double's S5 warm-restart scaffolding armed: touching
one file reverts every node to its start value **in place, under a surviving
session** — the 2026-07-28 failure mode.

This run exists because §8.1's repair and §13.2's assertion meet here, and the
obvious implementation is wrong. A rewrite that wrote *the slot's value* would,
during a silence, take a **reverted node's correct `TRUE` and repair it back to
the dead producer's last `FALSE`** — a stale clear, written by a live bridge,
which is the exact thing this slot exists to make impossible.

| # | Event | What the bridge did |
|---|---|---|
| 1 | **Restart while the producer was ALIVE** and publishing `clear`; the node reverted to its `TRUE` start value | detected (`BridgeHeartbeat reads 0 but this session last wrote 103`), cache invalidated, **7 of 7** inputs rewritten, and the warning node written **`False`** — a *fresh* clear from a live producer, which is the correct repair |
| 2 | The producer exited and stayed gone | `SILENCE … no sample for 0.536 s, past the 0.500 s window — writing the asserted True` |
| 3 | **Restart while the producer was DEAD**; the node reverted to `TRUE` | detected (`… last wrote 365`), **7 of 7** rewritten, and the warning node written **`True`**, tagged `asserted on silence, not a received sample (§13.2 W1)` |

```
L2 ForkliftWarningFieldOccupied  t_end=295478810533687  value=False
L2 ForkliftWarningFieldOccupied  t_end=295488160425279  value=True   asserted on silence …
L2 ForkliftWarningFieldOccupied  t_end=295491912712538  value=True   asserted on silence …
```

Counters for the run: `server_restarts_detected = 2`,
`inputs_rewritten_after_restart = 14`, `silence_assertions = 1`,
`write_errors = 0`, `read_errors = 0`, `reconnects = 0`.

**The mechanism, stated so it is not re-derived by the next reader.** The value
written for this slot is recomputed from the sample's own age on **every** cycle
(`opcua_side._value_for_write`), so every write path — cyclic, on-change,
reconnect refresh and restart repair — carries the same freshness verdict, and
none of them can carry a value the producer's silence has already invalidated.

---

## 3. Run w2 — the committed harnesses, re-run, and two failures that are not this change's

The test double gained ten nodes in this round, so the harnesses that exercise
it were re-run. **Both pre-existing failures are recorded rather than repaired**,
because repairing them is a different brief and each is a judgement about m5-44's
landing, not about this slot.

| Harness | Result | Reading |
|---|---|---|
| `tools/check_write_allowlist.py` | **38 of 39 passed** | The one failure is `cell only: … bridge.yaml`: the harness asserts the committed `bridge.yaml` is **cell-only**, which m5-44 changed on 2026-08-06 (commit `1842c42`). Every §4.10 check still passes with the new group in the loader — the server-side refusals, the derived-allowlist identity for the two double configs, and the loader rejecting an `Hmi` node in a writable position |
| `tools/check_forklift_slots.py` | **crashes before its first check** | `for _node_key, topic_key in group.outputs` — `SignalGroup.outputs` became a 3-tuple in the same m5-44 commit. A committed harness that no recent evidence section exercises is untested code however committed it looks (LESSONS 2026-08-05); it has not run since 2026-07-29 |
| `tools/warning_stimulus.py` guard | **refused, exit 2** | A script that asserts an absence with no positive control in front of it is rejected before anything is published |

Neither failure involves the warning slot, the silence rule or the extended
double: both are `config.py` shape changes from the previous round that never
reached the two harnesses. **Requested, not fixed here.**

---

## 4. What these runs establish, and what they do not

| Established | Where |
|---|---|
| A live `occupied` and a live `clear` reach the node, both directions, six transitions, seen by the server | §1.1 |
| **Silence becomes an explicit `TRUE`**, 492.7 ms after the last publish and 0.542 s after the last received sample, inside the 0.550 s bound the window and the cycle set | §1.2 |
| The same event confirmed on an independent session by a client that cannot write the node | §1.2 |
| A dead bridge freezes the node at `FALSE`, and the consumer's own term catches it in 0.514 s and holds for all 663 remaining samples | §1.3 |
| The residual is bounded and named, not hidden | §1.3 |
| The restart repair carries the freshness verdict and cannot re-write a stale clear | §2 |
| The envelope group still crosses, in the same process, with the committed config byte-identical | §1.4 |

| **Not** established | Why |
|---|---|
| **Anything live.** The node, its folder, its DB, its rights and its start value on the CPU | It does not exist yet: `plc/forklift/TIA-BUILD-PROCEDURE.md` chunk X, after step 338. **Nothing in this file was run against the controller**, and step 358's second half is the live half of this deliverable |
| That the window is wide enough for the **real** producer | The producer here is a scripted stand-in with no simulator behind it. §0.1: the multiple is derived from the tick and is owed a measured worst-case inter-arrival at commissioning |
| Any behaviour of `plc/forklift/SPEC.md` §14.16 | The double runs no program. The `bridgeLinkOk` term in §1.3 is a model inside a test instrument |
| A safety property, PL, SIL, Category or PFH | §13.1: process data. The safe copy of this verdict rides a different path entirely |
| A repeated figure | Every timing here is **n = 1** per run: one silence in w1, one in w3, one bridge death, two restarts |

## 5. Files

| File | What it is |
|---|---|
| `bridge/evidence/m555-w1-latency-2026-08-06.csv.gz` | The bridge's own evidence CSV for w1 — the `silence` rows and the labelled `L2` writes |
| `bridge/evidence/m555-w1-warning-witness-2026-08-06.csv.gz` | The second OPC UA session's 20 Hz record of the node, the heartbeat and the modelled consumer term |
| `bridge/evidence/m555-w1-envelope-chain-2026-08-06.csv.gz` | The vehicle-side witness of the envelope group in the same run |
| `bridge/evidence/m555-w1-double-observe-2026-08-06.csv.gz` | The double's own server-side observation, including the eight untouched columns |
| `bridge/evidence/m555-w1-bridge-2026-08-06.log.gz`, `…-events-…txt.gz` | The bridge's log and the run's own event and stimulus stamps |
| `bridge/evidence/m555-w3-*` | The same set for the restart run |
| `bridge/evidence/m555-w2-harness-regression-2026-08-06.log.gz` | The two harness runs of §3, as printed |

All archives were gzipped **after** their writers had exited (`pgrep` empty,
files quiet) and every one was verified with `gzip -t` (LESSONS 2026-07-28/29).
Every file name carries the **run** that produced it (LESSONS 2026-08-06).
