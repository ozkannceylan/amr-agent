# Report m3-36 — the §6.8 rebuild re-runs, written into the evidence

brief:               docs/briefs/m3-36-rebuild-rerun-evidence.md
status:              done
files_changed:       bridge/EVIDENCE_LATENCY.md (+497 / −0), bridge/EVIDENCE_SIGNAL_LOSS.md (+101 / −6) — one logical change, not committed
invariants_touched:  none

---

## What was written

**`bridge/EVIDENCE_LATENCY.md`** gains **Section B, part 3** (§B3.0–§B3.5), placed
after §B2.14 and before Section C: provenance and artifacts, the five re-runs step
by step with a verdict each, the rewrite-on-restart measurement, the observer's
blind spots, a re-disposition of §B2.12 rows 14–22, and the requests that fall
outside `bridge/`. One four-line forward pointer was added at the head of §B2.12.
**Nothing in parts 1 or 2 is edited** — the diff is **+497 / −0**, pure addition.

**`bridge/EVIDENCE_SIGNAL_LOSS.md`** gains **"The same case on the §6.8 rebuild"**
under case C, plus a pointer inside the existing F5 paragraph, a line in the
top-of-file summary, and a re-statement of the closing "what this still does not
establish" list. The six removed lines are that closing status paragraph; **no
recorded figure was altered** in either file.

## The rewrite-on-restart figure, derived rather than copied

The brief asked for the interval from the committed log's own two timestamps:

```
19:25:43,501 WARNING BridgeHeartbeat reads 0 but this session last wrote 3499 …
19:25:43,511 INFO    input image rewritten after cache invalidation: 7 of 7 nodes
```

**10 ms**, at the log's 1 ms resolution. The 20 Hz CSV measures the same interval
finer and agrees: detection read complete → last of the seven writes complete =
**9.704 ms**, inside one **50.789 ms** cycle, which the CSV states itself
(`input_image_rewritten 7/7`, `written in one cycle`), at a cost of one **0.906 ms**
overrun. F5's comparable figure was **4 min 31.1 s** of a stale image ended by a
manual force-toggle. The mechanism is proved by the `L1` ages at the rewrite:
`PanelStopCircuitClosed` had not changed on the ROS side for **177.473 s** and
`PanelProcessStopCircuitClosed` for **176.224 s** — the two slots whose start
values latched a process stop in part 2, and the two that write-on-change alone
would never have sent.

## Corrections made to the brief's own account

Each is stated in the section rather than silently applied.

1. **Build letter.** The brief calls the rebuild "build E". §B2.9 already spends
   **E** on the ±0.10 narrowed program and **F** on the ±1.00 restored one. It is
   **build G** in the evidence. Any tracking file that adopted the brief's letter
   needs correcting.
2. **"20 ms-resolution PLC reaction" does not exist in this run.** The finest
   sampler of any `Status/` node here is the **5 Hz** observer; the only other is
   the 1 Hz log. The argument for the link drop rests on `LinkLostLatch` being a
   **level** that survives to be sampled, not on resolution, and it is written that
   way.
3. **The 4.8 inputs were published ~4.25 s apart, not 3 s** — measured write
   spacing 4.249 / 4.299 / 4.250 s. The order (stop, process stop, start, reset) is
   as the brief has it.
4. **The observer's silence has a second cause the brief does not name.**
   `BridgeHeartbeat` is written by the *bridge*, so a halted CPU does not stop it
   advancing — there is no plateau to look for during a STOP, only the 9.704 ms
   revert transient inside a 200.7 ms sampling interval. Both causes are stated.
5. **The owner's pre-run reading does not discriminate the build.**
   `HeartbeatSeenAlive` read `TRUE` because the bridge had already written after the
   download, so `ProcessStopLatch FALSE` beside `BridgeLinkOk FALSE` there is
   consistent with build G but equally consistent with build C. The discriminating
   reading is inside the first `HEARTBEAT_STALE_TIME` of a CPU run with the bridge
   down, and it was not taken.
6. **4.5's no-latch result is attributed with its arithmetic, not asserted.** The
   bridge's rewrite and the §6.8 boot-polarity fix landed together. The timings
   separate them — first OB call 1.004–2.556 ms after RUN (§B2.9, build F, standing
   beside the argument rather than proving it), repair ~10–60 ms after RUN, build
   C's boot window 500 ms — so the contacts stood at start values inside build C's
   permissive window and outside build G's. It is labelled an inference over a
   window no instrument sampled.

## Disposition, as written into §B3.4

| Row | Verdict |
|---|---|
| 14 — T4.9b, two preconditions | rebuild met; **form (a) closed with a pass**; form (b) (CPU start, reset held) did not run, so the step is **not yet a pass** |
| 15 — T4.11 reaction re-record | **open** — not attempted; the per-session CSV that its remedy needed now exists and is demonstrated |
| 16 — T4.11b | **open and BLOCKED**; no fault-injection facility exists |
| 17 — 4.2 / 4.3 / 4.5 / 4.8 | **4.3 closed in full**; 4.2 and 4.5 closed on their server-visible halves; **4.8 half re-run**, its cold start not done |
| 18 — Group 4 for T4.6 / T4.6b | **open**, and the same gap recurs at 19:25:43 |
| 19 — adapter break under a running program | **open** |
| 20 — bridge repairs the image after a server restart | **CLOSED**, measured |
| 21 — one CSV per session | **rule closed**; part 2's 17:14–17:49 hole is permanent |
| 22 — `PresenceOnTimer.PT` after a restart | **open**; one coarse datum added (a clean cycle ran post-restart) |

Three of the five steps carry a `SPEC.md` §9 **Group 4** condition that no
instrument in this run can see, and **no watch-table capture was taken at all**.
Those conditions are recorded as unread, never inferred silently.

open_questions:
- `docs/interfaces/bridge-design.md` §8.1 does **not** describe restart detection —
  its *Detection* row is a failed read, write or keep-alive, and §7.3 case C
  assumes the session breaks. The implemented path cites "§8.1" in its own log
  line for a rule that is not there. The row is `docs/interfaces/`' to write.
- `plc/demo-cell/SPEC.md` §12 open item 7 is satisfied by behaviour (§B3.2) and
  should say so; §6.7's guarantee can now name the mechanism that makes the input
  image truthful; §11 4.9b's as-run status is (a) passed, (b) outstanding. `plc/`'s
  to write.
- One watch-table capture at the next CPU cold start with the bridge down is the
  single highest-value reading still missing from this file — it is 4.8's other
  half and the only direct test of the §6.8 boot polarity.
- Whether the M3 gate can close with rows 15, 16, 18, 19 and 22 open, 4.8's cold
  start untaken and 4.9b form (b) unrun, is the **verifier's ruling and the
  owner's**. This report makes no gate claim.

next_suggested: brief `bridge/` for `SPEC.md` §12 item 6 — the hold-until-disarmed
fault-injection facility — since it is the only route to T4.11b and the last
`bridge/` deliverable the T4 roster is waiting on.
