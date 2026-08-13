# m5-57 — the stand-in writer's 45016 speed link

    brief:               issued in-session (no file under docs/briefs/), against
                         plc/forklift-safety/SPEC.md §11.2 and the m5-49 report's
                         request 1 ("bridge/: the writer's 45016 listener, the
                         seven new members, WARN, the MOT silence rule")
    status:              done
    invariants_touched:  none

## The one-line answer

**The link is proven live.** The vehicle's two speed channels reached
`SafetyInputStandIn`'s speed members and stood valid in the F-program's own
consumer view, against the finished safety program (signature `50573CD9`), and
the source going silent reached the same view as a **missing reading and a
latched demand** — never as a zero and never as the last value. **AT-10 and
AT-11 are runnable as far as this seam is concerned.**

## files_changed

| File | What |
|---|---|
| `bridge/standin_writer/standin_writer.ps1` | **The deliverable.** Second TCP listener on **45016** speaking `SPD A/B <int mm/s>`, `MOT <p> <v>`, `PING`; the seven §11.3 members added to the allowlist (four → eleven); per-channel freshness sequences; the `MOTION_SILENCE_MAX` = 250 ms rule; `WARN 0/1` added to the existing 45015 vocabulary with a field-link loss driving zone **and** warning open together; a member probe at every connect so a half-built controller leaves a group inert rather than failing every cycle; and end-of-stream detection on both links |
| `bridge/STANDIN-WRITER-DESIGN.md` | §1.1 write set (eleven tags, group gating), §2 (which members are republished and which are deliberately not), §2 timers (four, each named against the channel it watches), new §3.1 speed link and §3.2 end-of-stream, §3 warning vocabulary, §5.4 terminal write, §6, §7 log classes, §8 five new acceptance checks |
| `bridge/standin_writer/EVIDENCE_BUILD.md` | New **§7**, ten subsections: the build read back, every run, the joint run in full, the two defects found, the re-run of the three proven properties, cadence with eleven tags, an operating note, and the state the machine was left in |
| `bridge/standin_writer/testing/speed_feed.ps1` | **New scaffolding.** A 45016 line feeder with per-channel silence windows, a mid-run step, and arbitrary line injection for the refusal paths. Explicitly not the speed source |
| `bridge/standin_writer/testing/field_feed.ps1` | Gained `-PingHz` (see finding 2) and a fixed keepalive schedule |
| `bridge/standin_writer/testing/observe_consumer.ps1` | 29 new read-only columns: the seven stand-in members and the F-side speed/SS1 statics, both new outputs, and the sequences on both sides. Absent members are still dropped, not faked |
| `bridge/tools/check_forklift_slots.py` | **Fixed**, was crashing before its first check |
| `bridge/tools/check_write_allowlist.py` | **Fixed**, was failing 1 of 39 |
| `bridge/standin_writer/evidence/m5-57-*` | Nine consumer captures, three writer session logs (`CYCLE` stripped), and 400 whole cycles of the joint run |
| `bridge/evidence/m5-57-check-*.log` | The two harness runs, as printed |

Nothing outside `bridge/` and this report was written. **`plc/`, `agv/`, `hmi/`
and `viz/` were read and never touched.** Nothing was downloaded, compiled or
changed in TIA; no project was opened. Nothing committed, no branch created, no
dependency added.

## The property that had to survive, and how it was proven

*The sources go silent rather than repeat, and the writer must not smooth the
gap.* Three independent observations, all in the consumer's view:

1. **One channel silent, the other alive** (run C3). `SpeedSeqA` froze at 234
   while `SpeedSeqB` advanced 247 → 313; `SpeedAValid` fell, `SpeedStaleNow`
   rose, and `SpeedMonitorDemand` went 0 → 1 **and stayed 1 after the reading
   returned**. The frozen channel's *value* was never rewritten — not to zero,
   not to itself.
2. **The whole source gone** (run J1, the joint run). Both sequences stopped
   within one writer cycle of the client's hang-up. `SpeedReadingA`/`B` still
   read 300/300 in the CPU afterwards, meaning nothing to the monitor, which is
   the design: *the value is not the signal, the sequence is.*
3. **The terminal write** (runs C4, G). On `quit` the writer writes every level
   in the demand direction and writes **neither reading and neither sequence** —
   a terminal zero would be a speed the writer invented.

The heartbeat kept advancing through all of it: **18 304 cycles across the two
long sessions, 19 overruns (0.10 %), zero write failures**, with eleven writes
per cycle instead of four. Those are two samples on one machine, not bounds.

## What is proven live, and what is not

**Proven live, against the finished program:**

- the joint run — `agv/`'s committed carrier `safe_speed_link.py` dialling this
  writer on 45016 across the WSL/Windows seam, 686 reading-carrying cycles, both
  channels valid within one F-cycle of the second reading, `SpeedDiff` inside
  ±22 mm/s against a 31 mm/s threshold;
- silence reaching the F-program as a demand, three ways;
- `WARN` reaching `WarningFieldClear` and the F-block's `WarningFieldClearValid`
  in both directions, and a field-link loss driving zone and warning open
  together;
- the motion channel failing toward *moving* on silence and on link loss;
- both refusal paths (malformed, out-of-Int) advancing nothing;
- the three m5-41 properties: double start refused (exit 3, no log file
  created), the terminal write before falling silent, and the console not
  starving the heartbeat.

**Not proven, stated plainly:**

- **The republish that repairs a controller restart was not re-run.** The code
  path is unchanged and now covers eight members, and it ran 10 962 cycles
  without a failure — but stopping the CPU was out of scope and the restart form
  was not reproduced. It is owed a run. Note the new shape: the speed members
  deliberately do **not** participate, and the reasoning for why that is safe is
  in the design doc §2, not in an observation.
- **No integrity claim of any kind.** No Category, Performance Level, SIL or PFH
  appears in anything written here, for the writer or for anything downstream.
  The readings arrive at the safety program as **standard data over a stand-in
  path**.
- Runs C–G ran against a program the owner was still building; only J1 ran
  against `50573CD9`. Every run says which build it ran against.
- **T7 was not run** — it is m5-58's. Run F did incidentally show one monitored
  reset clearing all three latches and a fresh discrepancy re-forming the
  demand, but that was a by-product of proving the writer and is labelled as
  such.

## Two defects found

**1. The writer never noticed a peer hanging up — found and fixed here.**
`NetworkStream.DataAvailable` is FALSE at end of stream, so a read loop guarded
by it never sees the zero-length read. A source that closed cleanly left the
client object held, and the next connection was refused as a "second
connection" for ever. The data path was never wrong, but **the link could never
be re-established**, which would have made the joint run impossible. Fixed with
a `Poll(SelectRead)`/`Available == 0` test on both links, applied after the
buffered lines are parsed. Re-proven twice. The field link had been surviving
this only because its staleness reaper eventually freed the object — a bug
masked by a timeout, which is the shape worth remembering.

**2. A 1 Hz keepalive against a 1 s stale window has no margin — NOT fixed,
because the value is `plc/`'s.** SPEC §7.2 sets `FIELD_LINK_STALE_MAX` = 1 s and
names the keepalive at 1 Hz. Measured: the field link was reaped as stale after
three keepalives, **10 ms before the fourth arrived**, because a sender's
interval drifts a few milliseconds past 1.000 s and the test is `> 1000 ms`. The
failure direction is safe — the link reads as intrusion *and* warning-occupied —
so this is a nuisance trip, not a hazard, but it now costs the warning verdict
too, and the real field evaluation will trip on it continuously. The writer
implements the spec's value unchanged; the test feeder gained a rate knob so a
vocabulary check is not silently a margin check. **Requested of `plc/`:** either
raise `FIELD_LINK_STALE_MAX` to a small multiple of the keepalive period, or
raise the keepalive rate, and say which in §7.2.

## The two broken harnesses, fixed and shown running

Both broke on the `config.py` shape change in `1842c42`, in different ways.

- **`check_forklift_slots.py`** crashed before its first check: `SignalGroup`
  outputs became `(node key, topic key, kind)` triples and one unpack still
  expected pairs. Fixed, and the site now **refuses loudly** a non-`REAL` output
  kind rather than subscribing `Float64` to a topic nobody publishes on — a
  harness that cannot apply its stimulus must fail, not quietly measure nothing
  (LESSONS 2026-08-06). Run: **46 checks, 46 passed, RESULT: PASS**
  (`bridge/evidence/m5-57-check-forklift-slots.log`).
- **`check_write_allowlist.py`** failed 1 of 39 for a subtler reason: it asserted
  the *cell* shape against `bridge.yaml`, and `1842c42` had repointed that file
  at the forklift and envelope groups. The stale row was the check's model of
  the world, not a code defect. Fixed by naming **every committed
  configuration** with the groups it actually declares, plus a sweep asserting
  the table covers `bridge/config/` — so a configuration added or repointed
  later fails visibly instead of escaping. Run: **42 checks, 42 passed,
  RESULT: PASS** (`bridge/evidence/m5-57-check-write-allowlist.log`).

## How to leave the machine — for m5-58

**The writer is stopped and the machine is clean.** Read back after the last
`quit` (EVIDENCE_BUILD §7.9 has the full listing):

- no writer process running — the `Global\amr-standin-writer` mutex was
  acquired fresh and released to prove it;
- **nothing listening on 45015 or 45016**; no vehicle-side process alive in WSL;
- CPU `safecell3` in `Run`, 269 tags, all three circuits open, both demands and
  the two new demands latched, `SafetyResetRequired` TRUE — the documented
  post-session state.

Four things m5-58's agent must know before driving the same chain:

1. **Start the writer first and let it own the ports.** It refuses a second
   instance by mutex (exit 3), and both listeners are its own. Do not run
   `m5-25-standin-stimulus-repeat.ps1` beside it — that one writes.
   `testing/observe_consumer.ps1` is read-only and is safe beside it; it now
   carries the speed and SS1 columns.
2. **`SpeedChainSeen` is TRUE and stays TRUE.** It is a one-shot armed by the
   first reading ever seen, and only a CPU STOP → RUN clears it — the same
   property m5-41 recorded for `HeartbeatSeen`. A run that wants to observe the
   arming edge needs a cold start.
3. **With no field source running, `WarningFieldClear` is FALSE and the reduced
   limit is in force.** A vehicle fed at 300 mm/s is legitimately over it, and
   **no monitored reset can be accepted** while it is — observed twice, in
   `m5-57-R1/R2-reset-refusal-consumer.log`. Any procedure needing the latches
   to clear must run a field source saying `WARN 1` (`testing/field_feed.ps1
   -Script "0:ZONE 1,0.5:WARN 1" -PingHz 5`) or drive below the limit in force.
   This is correct behaviour at both ends, not a defect, and it will cost a run
   if it is not planned for.
4. **The vehicle side is three processes**: `speed_link_rig.py plant` (or
   Gazebo), `safe_speed_channels.py`, `safe_speed_link.py`. The carrier reads
   the Windows host from the WSL default route by itself. `safe_speed` still
   defaults `false` in `vehicle.launch.py`, so the chain must be switched on.

## open_questions

1. **`FIELD_LINK_STALE_MAX` against the 1 Hz keepalive** — defect 2 above, for
   `plc/` to rule in SPEC §7.2. The single most likely cause of a spurious stop
   in any run that uses a real field source.
2. **The motion budget is 0.40 s, not 0.25 s.** `agv/`'s carrier stops
   forwarding `MOT` after its own 0.15 s window and this writer waits a further
   250 ms. Bounded, on the safe transition, and agreed between both halves —
   but §11.2 should state the sum rather than leave it to be added up. This
   restates m5-56 open question 2 from the other side of the seam.
3. **Sequence wrap is `30000 → 0`**, matching the heartbeat's, and is now
   written down (m5-56 open question 4 asked `bridge/` to state it). The F-side
   `CMP <>` against a memory is indifferent to the wrap; the one degenerate
   cycle is named in the design doc §2.
4. **The CPU-restart republish is owed a run**, in its new shape: the levels
   repair, the speed members deliberately do not.
5. **`bridge-design.md` still does not carry the stand-in writer at all**, nor
   the envelope group (already requested in the m5-44 report). The writer is
   specified by SPEC §7/§11.2 and `bridge/STANDIN-WRITER-DESIGN.md`, so nothing
   is undocumented — but the layer's own design document does not mention a
   second process in its directory. An `interface` brief, not a `bridge` one.
6. **`bridge.yaml`'s repurposing was never recorded anywhere.** It went from the
   cell-only commissioned config to forklift+envelope in `1842c42` and only the
   allowlist check noticed, by failing. Worth a line in `bridge/README.md`
   saying which file is the commissioned one.

## next_suggested

m5-58 runs T7 and the AT-10/AT-11 pair; this seam is no longer what blocks them.
