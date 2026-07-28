# Report m3-36 — the §6.8 rebuild re-runs, written into the evidence

brief:               docs/briefs/m3-36-rebuild-rerun-evidence.md
status:              done
files_changed:       bridge/EVIDENCE_LATENCY.md (+497 / −0), bridge/EVIDENCE_SIGNAL_LOSS.md (+101 / −6), committed as `80e6cc4`; plus this session's two corrections to §B3.0 and §B3.4 (+15 / −4) and this report
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

## Re-checked against the committed artifacts, and two corrections

The writing session ended at its commit, so every load-bearing figure of part 3 was
re-derived here from the committed artifacts alone. All reproduce exactly as
printed: the log's `19:25:43,501 → ,511` (**10 ms**, 7 of 7 nodes, and it is the
file's only `WARNING` line); the CSV's **9.704 ms** detection-to-last-write and
**11.492 ms** from the read's start, its containing `R1,cycle` of **50.789 ms** and
the `overrun,cycle` row of `905524` ns; the seven `L1` ages (**177.473** /
**176.224** / **144.310** / **29.894** s and **26.850** / **3.761** / **2.644** ms);
the **158.270 µs** and **118.233 µs** heartbeat-after-seventh-write gaps; the
session row counts **37 325** / **199 851** and spans **94.959** / **498.978** s;
and the observer's **1 196** rows / **239.994** s, period min 0.2001 / median
0.2008 / max 0.2031 s, heartbeat 2 763 → 7 563 at 20.0005 counts/s, **zero**
decreasing samples, **zero** `BridgeLinkOk FALSE` samples, `CurrentSessionCount`
constant at 2, and the bracketing samples t = 36.7452 / 36.9459 (200.7 ms).

Two statements did not hold up, and both are corrected in this commit. No figure is
altered by either.

1. **§B3.0 said "both processes were killed rather than shut down".** Session 2's
   process was not killed. It was still running when its CSV was archived and was
   **still appending at 22:04 the same evening** — 2 h 41 min after it started,
   ~39 kB/s, 356 MB — into the gitignored working file, which begins **without a
   header** at the monotonic instant the archive ends (session 1, already dead,
   left no such file). The committed session-2 CSV is a snapshot of a live session;
   its span is the window it covers, not the session's length.
2. **§B3.4 row 14 said "no `PanelResetPressed` write"** in the gap containing the
   CPU restart. §B3.2's own rewrite wrote that node inside that gap, with value
   `False`. The claim now reads "no *change-driven* write", which is what the
   artifacts support and all the argument needs.

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
- **A bridge session from this run is still live.** The session-2 process has held
  an OPC UA session against PLCSIM since 19:22:41 and was still writing at 22:04,
  356 MB and growing. Nothing here stopped it — stopping it is the owner's call,
  not a `bridge/` deliverable — but the next run must not be started beside it, and
  the counter block it will flush on a clean shutdown is the only route to build G's
  R1/R2/R3 ratios.
- **The archive step needs a rule.** Compressing a live session's CSV in place
  removes the file underneath the writer, which re-creates it headerless; archive
  after the session ends, or copy first and compress the copy. That is a
  `docs/LESSONS.md` row and is not mine to write.
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
