# m5-49b — chunk Q expanded into numbered steps

    brief:               issued in-session (no file under docs/briefs/); sources
                         plc/forklift-safety/SPEC.md §11.9 + §11.5 + §11.3 and
                         plc/forklift/SPEC.md §14.16
    status:              done
    invariants_touched:  none

## files_changed

| File | What |
|---|---|
| `plc/forklift/TIA-BUILD-PROCEDURE.md` | Chunk Q's zero-step stub replaced by **chunks Q–X, steps 192–360** — 169 numbered one-action steps, each with one observable result and one question, chunked with a verification and one named screenshot per chunk. Header item 5 added; the stale "no writer exists" prohibition given a revision note that keeps exactly what it still forbids; precondition row 6; four chunk-P rows re-pointed at real step numbers; eleven new record-table rows; step index rewritten (**360 steps**, ordering constraints restated); progress block rewritten to `NEXT IS CHUNK Q, step 192` |
| `docs/reports/m5-49b-tia-procedure-chunk-q.md` | this report |

Steps 1–191 did not move. Nothing outside `plc/` (plus this report) was written,
nothing was committed, no branch created, no dependency added, and nothing in
the controller was touched.

## The shape, and where the dependencies fall

| Chunk | Steps | Ends with | Waits on |
|---|---|---|---|
| Q | 192–209 | F8 recorded as offered with its date; `SafetyInputStandIn` at eleven members | nothing |
| R | 210–220 | FB2 Input 10, Output 6 | nothing |
| S | 221–263 | interface 10 / 6 / **44** / 17 | nothing |
| T | 264–286 | SL1–SL20 between V7 and `CauseGone` | nothing |
| U | 287–301 | 49 networks, `SpeedMonitorDemand` at 40, M4 last | nothing |
| V | 302–322 | changed signature, 10 reads / 0 writes, absence re-proven | nothing |
| W | 323–337 | ten `PT`s in force with their `IN`s, the **no-source signature** | step 335 only |
| X | 338–360 | ceiling at `0.20` with the field occupied | **gated at step 338** |

**The property the brief asked to preserve is preserved: chunks Q–W type today
and prove the fail-safe signature before the carrier exists.** The whole F-side
is built and observed against a writer that still writes four members — the
seven new ones hold their start values, no sequence advances, the monitor never
arms, and step 333 reads that as `SpeedCauseGone` `TRUE` / `SpeedMonitorDemand`
`FALSE` with the limit selected and the onset budget spent. Two BLOCKED steps
are marked in place with what is provable without them: **335** (T7 rehearsal —
bridge 45016 extension + agv client) and **358**'s second half (the live
ceiling fall and return — the bridge slot); the stale direction is observable at
358 without any of it. Step 338 stops chunk X outright if the interface ruling
is absent.

**Verifications prefer what the session can run.** Step 320 re-runs
`m5-25b-f-absence-verify.py` (its DB-name sweep already covers the seven new
members and its four-mirror positive control still passes — the step says not to
edit it); step 331 runs `bridge/standin_writer/testing/read_timers.ps1 -Block
InstF_Forklift_Safety`, which reads the F-block's own instance data and prints
`IN`, `PT`, `ET`, `Q` together for all ten timers; step 354 re-runs
`m5-25-node-verify.py` after the warning node, with the "it prints two columns
and does not compare them" warning attached. Step 332 makes the comparison
explicit against a printed list rather than leaving it to a PASS line.

Every trap the brief named sits inside the step where it bites: green diff
circles (316, 353), never rename a bound DB (210, 339), the `_1` sweep after
download (318, 349, 354), in-force timer values with the two opposite
diagnoses of a `T#0MS` (332), no fail-safe Modify in permanent safety mode
(324, 335), and the start-value rule at both of its cases — an existing DB whose
start values never applied (329–330) and a new DB whose start value does (357).

## One correction the expansion had to make, and it is not cosmetic

**§11.9 step Q1 says "Run §2 F3 on `safe_amr` (the m5-25 repeat script)". On
this build that script must not be run.** It writes the three Bool channels and
**no heartbeat**; after the S015 delta a frozen heartbeat is `StandInValid`
`FALSE`, which forces all three validated channels to the demanding direction —
this document's own chunk-H rule ("chunk H must run before chunk J and cannot be
re-run after it"). F3 is in any case already answered on `safe_amr` (record
table, steps 102–106) and was superseded by m5-41, which observed `StandInValid`
`TRUE` in the consumer's view on this very build. **Step 194 records this and
names the correct instrument** — the writer, which supplies the heartbeat, with
`observe_consumer.ps1` reading the F-block's instance data.

## open_questions

1. **`plc/forklift-safety/SPEC.md` §11.9 Q1 should be corrected** to drop the
   m5-25 repeat script, per the section above. It is a spec-side edit and this
   brief did not make it.
2. **The static count is 44 in TIA and 43 in §11.3** — the step 141 counting
   rule (TIA's auto-generated `F_IEC_Timer_Instance` is a row §3.3's table does
   not count) applied one delta later. Step 247 states both and tells the owner
   not to delete a row the tool generated for itself; whether seven new `TON`s
   make TIA add further helper instances is **unknown and is asked as a
   question**, not predicted.
3. **Q3's constant plan is settled by observation, not by the spec's
   conditional:** step 210 read three constants back at chunk K, so the
   *Constant* section exists on this block and the "else literals at the pins"
   branch of §11.3 is not exercised. If the section turns out to refuse a
   negative `Int`, step 197 catches it before anything is built.
4. **Step 313 expects ten disclosed members while eleven exist.**
   `MotionObservationValid` is bound to no pin by design, so it must not appear;
   if it does, a wire is wrong. Worth a safety-spec eye, because the disclosure
   is the only place that asymmetry is visible.
5. **Chunk X's names are the requested ones.** If the interface ruling moves the
   folder or the leaf, step 338 makes the owner report it before typing, and
   §14.16 plus these steps are corrected together — the tag name and the leaf
   must stay identical (CLAUDE.md §9).

## next_suggested

Brief the bridge agent's §11.2 writer extension (45016 listener, seven members,
`WARN`, the `MOT` silence rule) — it is the single item that unblocks step 335
and, with the agv client, turns the whole speed monitor from typed to
demonstrated.
