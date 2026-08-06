# Report m5-55 — the bridge's warning slot, and the silence it asserts

    brief:               m5-55 (issued in-session; no file in docs/briefs/)
    status:              done — for everything that can be proven without the
                         controller. The LIVE half is explicitly NOT claimed:
                         the node does not exist on the CPU until chunk X, and
                         `plc/forklift/TIA-BUILD-PROCEDURE.md` step 358's second
                         half remains owed (see "What is still owed live").
    files_changed:
      - bridge/amr_bridge/config.py            (WARNING_GROUP as a fourth signal
                                                group; the StaleAssert record;
                                                WARNING_FIELD_STALE_MAX_S = 0.500 s
                                                derived as 10 x the producer's
                                                50 ms tick; Config.stale_asserts;
                                                the silence rule in describe())
      - bridge/amr_bridge/opcua_side.py        (_value_for_write — the freshness
                                                verdict recomputed every cycle on
                                                every write path; the transition
                                                log and its evidence row; the L2
                                                row labelled when a value was
                                                asserted rather than received)
      - bridge/amr_bridge/instrumentation.py   (silence_assertions,
                                                silence_max_age_ns counters)
      - bridge/test_double/plc_test_double.py  (the double now serves §12's nine
                                                nodes and §13's one — 43 nodes;
                                                start values, access levels, the
                                                S1 back door extended to the
                                                envelope and the mode, S2 and S5
                                                extended to the new columns)
      - bridge/config/bridge-double-m5.yaml    (NEW — forklift + envelope +
                                                warning against the double)
      - bridge/tools/warning_stimulus.py       (NEW — scripted producer stand-in;
                                                refuses to run without a
                                                subscriber and without a positive
                                                control in front of a silence)
      - bridge/tools/observe_warning_node.py   (NEW — second-session OPC UA
                                                witness; models the consumer's
                                                own bridgeLinkOk term)
      - bridge/EVIDENCE_WARNING_SLOT.md        (NEW — the dated capture)
      - bridge/evidence/m555-w1-*, m555-w2-*, m555-w3-*  (12 archives, gzip -t
                                                verified, writers gone first)
      - bridge/README.md, bridge/test_double/README.md   (counts and file tables
                                                the change made false)
      - docs/reports/m5-55-bridge-warning-slot.md (this file)
    invariants_touched:  none. Checked deliberately: invariant 4 (the bridge is a
                         client and this group adds no server behaviour),
                         invariant 10 (the field evaluation stays the single
                         owner of the verdict — the bridge writes the node and
                         never authors the value, and nothing here recomputes,
                         compares or thresholds it), invariant 2 (loss of the
                         producer, of the bridge or of the link is a degraded
                         mode that reads more restrictive, never less) and
                         invariant 1 (process data end to end; the safe copy of
                         the same verdict rides the stand-in writer path and
                         never touches this server).
    open_questions:
      - **The packaging deviates from bridge-design.md §4.11 in one respect and
        the interface agent is asked to ratify or overrule it.** §4.11 carries
        row 23 inside the envelope group's section; this implementation makes it
        a FOURTH group, `warning`. Reasons in `amr_bridge/config.py` at
        WARNING_GROUP: §2.1's own definition of a group is "one plant and one
        node-model section" and §13 is its own section, its own folder and its
        own DB; and, decisively today, the loader requires a configured group to
        name exactly its section's nodes, so folding row 23 into `envelope`
        would make the committed `bridge/config/bridge.yaml` fail at node
        resolution against the CPU that is running RIGHT NOW, until chunk X
        lands. Every derived consequence §4.11 states holds either way: the
        allowlist gains exactly one key and is still derived, never
        hand-maintained. One edit reverses it.
      - **The window's multiple is a design value.** 0.500 s = ten of the
        producer's 50 ms ticks, the rule stated as the multiple per §10.8 P3.
        Nothing has yet measured the REAL producer's worst-case inter-arrival
        under simulator load; both runs saw zero false assertions, which bounds
        nothing. A commissioning measurement above the window re-derives the
        multiple rather than reinterpreting the tick.
      - Two committed harnesses fail for reasons that predate this work and were
        found by re-running them (§3 of the evidence file):
        `tools/check_forklift_slots.py` CRASHES before its first check
        (`for _node_key, topic_key in group.outputs` — the tuple became a
        3-tuple in m5-44's commit `1842c42`), and
        `tools/check_write_allowlist.py` fails 1 of 39 because it asserts the
        committed `bridge.yaml` is cell-only, which the same commit changed.
        Recorded, not repaired: each is a judgement about that landing.
      - Whether the HMI displays the node is still `hmi/`'s (§13 item 2).
    next_suggested:      after chunk X step 349 creates the node, one two-line
                         edit to `bridge/config/bridge.yaml` (below) makes the
                         committed configuration carry the slot live, and step
                         358's second half can then run.

## What was built, in one paragraph

The bridge now carries `DemoCell/Forklift/Warning/ForkliftWarningFieldOccupied`
from `/forklift/warning_field/occupied`, uninverted, on change plus a refresh on
every (re)connect and after a detected server restart — and, the point of the
whole thing, **it converts silence on that topic into an explicit `TRUE` write
inside its own named window**. The producer publishes at its 20 Hz tick so that
its absence is visible; an OPC UA node is a held value, so the seam is by
construction the republishing layer that rule exists to defeat. The slot makes
the last layer that can see the absence assert it, so **a `FALSE` on that node
is always a fresh claim by a live bridge, never a leftover.**

The window is `WARNING_FIELD_STALE_MAX_S`, **its own constant, shared with
nothing** (§10.8 P4), derived as **ten of the producer's own 50 ms ticks =
0.500 s**; the reaction bound is window + one bridge cycle = 0.550 s. It is a
freshness window over the bridge's **own input channel** — the timer class §7.2
admits, beside the bridge's own cycle. No threshold, no debounce, no dwell over
a plant value, no latch, no verdict: the verdict is the field evaluation's and
is never recomputed, compared or interpreted anywhere in this process.

## The three proofs, with their numbers

| # | Property | Measured |
|---|---|---|
| 1 | Occupied and clear reach the node, both directions | six transitions, seen in the **double's own server-side** observation, not in the writer's echo |
| 2 | **The producer goes silent and the node goes occupied inside the window** | asserted `TRUE` **492.7 ms** after the last publish; the bridge's own row says **0.542 s** since the last received sample, against a 0.500 s window and a 0.550 s bound. Confirmed independently by a second OPC UA session, which read `FALSE` for 0.480 ± 0.050 s into the silence and then `TRUE` |
| 3 | **The bridge itself dies, and the consumer's own term catches it outside the frozen value** | `SIGTERM` with the producer **alive and publishing clear**: the node froze at `FALSE` for **34.6 s / 663 samples**, and `node OR NOT bridgeLinkOk` read `1` for every one of them, the link verdict falling **0.514 s** after the last heartbeat change |
| 4 | The restart repair cannot undo the assertion | a warm restart during a silence reverted the node to `TRUE`; the §8.1 rewrite wrote **`True`**, tagged *asserted on silence*, not the dead producer's last `FALSE`. The same restart with the producer alive correctly wrote the fresh `False` |

**The residual is reported as the ruling names it (W5):** between the bridge's
death and the link verdict falling, a frozen `FALSE` stands — measured at
0.514 s here, bounded by the PLC's own `HEARTBEAT_STALE_TIME` plus its scan. The
independent backstop for exactly that window is the F-side monitor on the writer
path.

**Positive control, in the same run** (LESSONS 2026-08-06): the silence phase is
preceded by a live `clear` phase that is seen reaching the node, so a node
reading occupied cannot be explained by a dead publisher, a wrong topic name or
a mismatched QoS. `warning_stimulus.py` **aborts** rather than running when no
subscriber exists, and **refuses** a script whose silence has no live phase in
front of it.

## The envelope group was not disturbed, and here is what was re-run

`bridge/config/bridge.yaml` is **byte-identical** to the committed file
(`git diff` empty), the `envelope` group definition is untouched, and the
warning group is a fourth group that file does not declare — so the five-times
evidence of `EVIDENCE_ENVELOPE_BRIDGE.md` is untouched *by construction*.
**Nothing in this session touched the controller, PLCSIM or TIA.** What was
re-run, against the extended double and in the same process as the new slot: the
four envelope elements arriving together (spread **1.0 ms** permissive, **0.8 ms**
withdrawn, one cycle and one poll phase), the ceiling arriving as the unrounded
`0.6000000238418579` widening, the mode readback and the vehicle heartbeat
crossing back, the derived allowlist growing by exactly one key, R3 counting
seven, and the **eight** nodes the bridge must never touch holding their start
values for the whole run under server-side observation. Those are properties of
the design, comparable in kind and not in value with the live CPU figures.

## What is still owed live, and the exact edit that closes it

The node is created by `plc/forklift/TIA-BUILD-PROCEDURE.md` chunk X. Until then
nothing about the folder, the BrowseName, the rights or the start value on the
CPU is a fact (§13.3 item 3), and **no gate criterion may rest on this
deliverable's live half.** After step 349, and after the browse names have been
swept for TIA's silent `_1` suffixes, `bridge/config/bridge.yaml` needs exactly:

```yaml
groups: ["forklift", "envelope", "warning"]
# … and, under nodes.groups:
    warning:
      inputs:
        ForkliftWarningFieldOccupied:  ["Forklift", "Warning", "ForkliftWarningFieldOccupied"]
# … and, under ros.topics:
    warning:
      warning_field_occupied:    "/forklift/warning_field/occupied"
```

That edit is deliberately **not** made here: probe the server before pointing a
client config at a build of the program that does not exist yet (LESSONS
2026-08-06). `bridge/config/bridge-double-m5.yaml` is that shape, runnable today.

## REQUESTS — outside `bridge/`, not created here

1. **`docs/interfaces/`** — ratify or overrule the fourth-group packaging above,
   and, if ratified, `bridge-design.md` §4.11's row 23 gains a line saying the
   slot is configured as its own group. §12 item 16 and item 17 are otherwise
   satisfied by this round: the double now serves the envelope group and the
   warning node.
2. **`plc/`** — nothing. Nothing in `plc/` was read for edits, and nothing was
   changed. Step 358's second half now has a slot to test against.
3. **Whoever owns the m5-44 debt** — the two harness failures above.
4. **Not this brief, recorded because the owner named it at step 335:** the
   stand-in writer's **45016 extension** is `bridge/`'s work but is a *different*
   deliverable and was not started here. Confirmed to the owner in-session:
   **no source improvisation** — no hand-written values into the seven members
   to imitate a speed source, and no T7 figure claimed from one. The warning slot
   shares no node, no transport and no group with that path.
