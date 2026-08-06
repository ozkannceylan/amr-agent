# EVIDENCE — the speed-source link, vehicle side

What this file records: the WSL-side carrier that puts the two drive-shaft
speed readings and the motion-present observation on the wire to the stand-in
writer, proven against a **local sink** that speaks the writer half of
`plc/forklift-safety/SPEC.md` §11.2.

## 0. Environment, and which half is proven

| | |
|---|---|
| Host | The owner's Windows 11 machine; every run below executed **in WSL 2** (Ubuntu, ROS 2 **Jazzy**), from the `/mnt/c` checkout |
| Isolation | `ROS_DOMAIN_ID=71`, `GZ_PARTITION=m5-56-speed-link` for every run. No Gazebo process was started by any run in this file |
| Under test | `agv/forklift/scripts/safe_speed_link.py` — the carrier |
| Producer | `agv/forklift/scripts/safe_speed_channels.py` — unmodified, the real node |
| Consumer | `agv/forklift/scripts/speed_link_rig.py sink` — a **local model** of the writer half, **not** the stand-in writer |
| Plant | `speed_link_rig.py plant` — a **stimulus** for the producer's two gz read topics and the navigation scan. It is not a vehicle simulation and nothing in this file is a vehicle measurement |

**WHICH HALF IS PROVEN, STATED BEFORE ANY RESULT.** This file proves the
**vehicle side only**: what the carrier emits, when it emits it, and when it
falls silent. It does **not** prove:

- **the writer's 45016 extension**, which does not exist yet (`bridge/`, request
  1 of the m5-49 report). Everything below ran against a sink written from the
  same §11.2 paragraph as the client, so the sink's agreement is weaker
  evidence than it looks: two readings of one paragraph can agree and both be
  wrong about the writer.
- **the F-program's speed networks**, which are not built and not downloaded.
  No line below shows a channel becoming invalid, a demand latching, an SS1
  sequence running or a reset clearing a latch. Where this file says "the
  F-program reads this as a demand" it is quoting §11.5's rule, not reporting
  an observation.
- **the real transport geometry** in runs A–D: the sink ran on `127.0.0.1`
  inside WSL. §5 runs the same client against a listener on the **Windows**
  host, which is the geometry the writer will have.

The joint run that closes both gaps is owed and is named in the report.

**No integrity claim.** Nothing here carries a Category, Performance Level,
SIL, PFH or diagnostic-coverage figure, and nothing downstream of it does
either (ADR 0011 D5). The readings arrive at the safety program as **standard
data** over a stand-in path.

## 1. The unit checks — `--selftest`, no ROS, no network, no simulator

```
$ python3 agv/forklift/scripts/safe_speed_link.py --selftest
...
29/29 checks passed
```

The count is derived from the checks that ran, not typed beside them. What
they cover, in the order the file states them: the signed `round(v × 1000)`
scaling including the SLS limit landing exactly on 300 and reverse staying
negative; the two refusals (**non-finite** and **outside the S7 Int wire
range**) each with a **positive control** at the same call site; the
consume-once slot, including that a second take of one reading yields nothing,
that a reading past its window is discarded rather than held, and that an
empty slot polled fifty times invents nothing; the two wire line shapes; the
host read-back precedence; and five assertions against the values
`config.yaml` actually carries (port 45016, 1 Hz keepalive, the motion window
shorter than the writer's 250 ms silence budget, the reading window equal to
the producer's own, and the wire range being the S7 Int range).

## 2. Run A — the readings reach the link at the spec's rate

**Command** (`ROS_DOMAIN_ID=71`, 30 s bounded): sink → plant at 0.30 m/s →
producer (`--seed 7`) → carrier (`--host 127.0.0.1`).

**Artefacts**: `evidence/speed-link/runA-sink.csv` (one row per 50 ms sink
cycle), plus the three session logs beside it.

Carrier exit line:

```
EXIT | link attempts 1, connections 1, drops 0; sent SPD A 451, SPD B 452,
       MOT 498, PING 26; refused non-finite 0, out-of-range 0;
       silent ticks A 102, B 101, MOT 55; discarded stale A 0, B 0, MOT 0
```

Sink exit line:

```
EXIT | received SPD 903, MOT 498, PING 26, malformed 0; refused 0 extra
       connections; final SeqA 450, SeqB 451, MotionPresent True
```

Measured over the 497 sink cycles in which the link was up and a sequence
existed:

| Quantity | Channel A | Channel B |
|---|---|---|
| cycles in which the sequence advanced | 450 of 497 | 451 of 497 |
| mean interval between advances | 0.0551 s | 0.0550 s |
| **longest interval with a frozen sequence** | **0.052 s** | **0.052 s** |
| reading range on the wire | 216 … 315 mm/s | 219 … 318 mm/s |

`MotionPresent` was TRUE in 497 of 497 cycles with the observation **valid** in
497 of 497 — the plant stimulus is moving, and the observation says so from
the lidar rather than from the shaft. The longest MOT silence was 0.025 s
against the writer's 250 ms budget.

**The 47 cycles with no advance are a beat, and they are bounded.** The
producer publishes on its own 20 Hz timer and the carrier ticks on its own
20 Hz steady clock, so occasionally one tick finds no new message and the next
finds two — which the consume-once slot coalesces exactly as the writer's own
50 ms cycle would. The measurement that matters is the one in bold: **no
sequence was ever frozen for longer than a single sink cycle**, 0.052 s
against a `SPEED_STALE_MAX` of 500 ms, a factor of nearly ten. The beat cannot
reach the stale rule.

**The reading spread is the stimulus's, not the encoder model's.** ±~50 mm/s
around the commanded 300 comes from the timing jitter of a synthetic
publisher, not from the reading-head model, whose measured σ is 5.4 mm/s
(`EVIDENCE_ODOMETRY.md` §15.4). Nothing in this file re-measures that, and no
number here should be read as a channel-noise figure.

## 3. Runs B, B2, B3 — the producer stops, and the client stops with it

Three ways for the source to fail, each with the **positive control inside
the same run**: the first ten-odd seconds of every run below show the
sequences advancing every ~55 ms, so "frozen" is measured against a stream
that was demonstrably flowing a moment earlier on the same instruments. A
stopped process and a broken client look identical without that
(LESSONS 2026-08-06).

### Run B — the plant goes silent at t = 12 s (the shaft stops being read)

`runB-sink.csv`. The plant stops publishing; it does **not** publish a zero
and does not repeat its last value.

| | |
|---|---|
| plant went silent | 17:05:36.558 |
| carrier's last `SPD A` | within ~0.09 s of it (the producer stops on its next tick — it re-differences nothing) |
| last sink advance | t = 13.350 s, reading **292 mm/s**, `SeqA` **213** |
| the following 232 sink cycles | `SeqA` **213** throughout; `SpeedReadingA` **292** throughout; **no zero was ever written** |
| longest frozen interval | **11.601 s**, to the end of the run |
| `MotionPresent` | TRUE for every cycle of the run |
| `MotionObservationValid` | fell to 0 at t = 13.600 s — *moving because unobservable*, told apart from *moving because observed* exactly as §11.3 intends |

Carrier exit: `sent SPD A 213, SPD B 213 … silent ticks A 240, B 240`.

### Run B2 — the producer **node** is killed at t = 12 s

`runB2-sink.csv`. Killed with `SIGKILL` at 17:06:51.448, so there is no
orderly shutdown and no last message.

| | |
|---|---|
| last sink advance | t = 13.902 s, reading **306 mm/s**, `SeqA` **223** |
| the following 221 cycles | `SeqA` **223**, reading **306**, frozen **11.05 s** |
| `MOT` | stopped entirely — longest MOT silence **11.076 s** |

### Run B3 — the vehicle at **rest**, then the producer is killed

This is the case that matters most, and B and B2 do not cover it: both of
those were moving, so `MotionPresent` was already TRUE and the writer's
silence rule had nothing to change. Here the stimulus stands still.

| | |
|---|---|
| readings while streaming | −11 … +15 mm/s — **zero is a value and it is sent**; the spread is one count of quantisation |
| `MotionPresent` FALSE | 225 consecutive cycles, t = 2.850 → 14.052 s: a corroborated standstill |
| producer killed | 17:07:44.6 |
| last sink advance | t = 13.852 s, reading **0 mm/s**, `SeqA` **222**, frozen for the remaining **11.099 s** |
| the sink's own transition | `MotionPresent driven TRUE: no MOT line for 0.253 s - an unobservable vehicle is MOVING, never still` |

So a standstill that stops being corroborated becomes *moving* within
0.253 s of the last observation, and the two speed readings that agreed on
zero stop being believable in the same event. That is the shape §11.6 rows 2
and 5 rest on, on this side of the seam.

## 4. Run C — reconnection, and the listener refusing a second client

`runC-sink-1.csv`, `runC-sink-2.csv`, and two carrier log directories.

**A second carrier is refused, and survives being refused.** With carrier 1
streaming, carrier 2 was started. The sink logged five refusals:

```
LINK | refused a second connection from ('127.0.0.1', 35396): one speed-source
       client at a time
```

Carrier 2's own view, once per second for as long as it ran: connect →
`down (peer closed the connection (EOF) …)` → retry. It never wedged, never
spun, and never sent a reading that was not a reading — one attempt landed a
line into the closing socket and logged
`the reading is DROPPED. It is not queued and not resent`.

**Carrier 1 outlives a sink outage.** Sink session 1 ended at 17:08:48.7;
carrier 1 saw the EOF, then failed seven connect attempts at 1 Hz, each
logged with its reason (`Connection refused`), and connected again at
17:08:54.98 — **attempt 8, connection 2** — when sink session 2 started. Its
exit line: `link attempts 8, connections 2, drops 1`.

**Nothing was replayed across the gap.** Sink session 1 ended with
`SeqA 223`; session 2 began at zero and its first advance carried a reading
measured after the reconnect (307 mm/s), not the 299 that was in flight when
the link died. The carrier holds no reading across a link event, because a
reading it did not just receive is one it may not send.

## 5. Runs D1 and D2 — the two refusals at the ROS seam, with positive controls

The producer cannot emit a `NaN`: it declines to publish instead. So the
refusal path is reached by publishing straight onto the channel topic
(`speed_link_rig.py inject`), which is the same subscriber the producer feeds.
Each run publishes the impossible value for 8 s and then a **positive
control** — a finite 0.25 m/s on the same topic — for the rest.

| Run | Injected | Carrier | Sink saw |
|---|---|---|---|
| **D1** | `nan` | `refused non-finite 151`, `sent SPD A 141` | first advance at t = 10.402 s; **the only reading ever on the wire was 250 mm/s** |
| **D2** | `40.0` m/s (40 000 mm/s, past the S7 Int range) | `refused out-of-range 152`, `sent SPD A 141` | first advance at t = 10.301 s; **the only reading ever on the wire was 250 mm/s** |

In both runs the sink's channel-A sequence did not advance once during the
injection window: no zero, no last value, no wrapped integer. The positive
control then advanced it 141 times, so the silence was the refusal and not a
dead subscriber.

The refusal is logged per tick (151 lines in D1). That is deliberate — each
one is a reading that did not reach the monitor — but it is noisy, and it is
named in the report as something to revisit if a real fault ever runs for
minutes.

## 6. Runs E and E2 — the real geometry: WSL client → a listener on Windows

Runs A–D put the sink on `127.0.0.1` inside WSL, which does not exercise the
transport the writer will have. E and E2 run the same carrier against a
listener on the **Windows host**, dialled at an address the node **read back
from its own configuration** and logged:

```
LINK | writer address 172.19.176.1:45116 read back from WSL default route
       (ip route show default)
```

**The port is 45116 and not the spec's 45016, and the reason is a fact about
the machine at the time of the run: a stand-in writer session was already
listening on 45016 on this host** (another session's work, landing
concurrently). Taking that port, or connecting to it, would have interfered
with a live run that is not this brief's. The geometry proven here is
therefore WSL → Windows over TCP with the address derived the way ADR 0006
requires; **the spec's port against the real writer is part of the owed joint
run, not part of this evidence.**

**Disclosure, because it is the honest thing to record:** a single
connectivity probe from WSL did open and immediately close a connection to
`172.19.176.1:45016` at ~17:11 before the collision was understood. It sent
no bytes. It may appear in that session's writer log as a connection.

| Run | Result |
|---|---|
| **E** | Connected, streamed 14 s, 281 sequence advances, **longest gap 0.053 s** — the same figure as the loopback runs, so the boundary costs nothing measurable at this rate. The Windows sink's own bounded run then expired, and the carrier's reconnect attempts failed with `no completion within 2.0 s` rather than a refusal, because a blackholed SYN gives no RST. That is precisely the case the connect **deadline** exists for: without it the node would have blocked on each attempt |
| **E2** | The complete run. Connected 17:13:48.97 from `172.19.180.72`; **453 sequence advances**, longest gap **0.053 s**; the plant then went silent and the sink held `SeqA 453` and `SpeedReadingA 298 mm/s` for **8.801 s** across 176 further cycles with the link still up, `MotionPresent` TRUE and `MotionObservationValid` falling to 0. Windows sink exit: `received SPD 906, MOT 630, PING 30, malformed 0` |

**Not one malformed line was received in any run in this file** — the sink
counts them and every count is zero, so the grammar the carrier emits is the
grammar §11.2 states, as parsed by an independent reader of that section.

## 7. The launch coupling, evaluated rather than read

`vehicle.launch.py` starts the carrier only when **both** `safe_speed` and the
new `safe_speed_link` (default `true`) are true. The condition is an explicit
conjunction, not a nested include, because a launch configuration set by one
include is visible to the next (LESSONS 2026-08-05). All four combinations
were evaluated against the launch description that the file actually builds,
by resolving the action's condition in a `LaunchContext`:

| `safe_speed` | `safe_speed_link` | carrier started |
|---|---|---|
| true | true | **True** |
| true | false | False |
| false | true | False |
| false | false | False |

with the producer, for contrast, `True` at `safe_speed=true` and `False`
otherwise, and the resolved command pointing at
`agv/forklift/scripts/safe_speed_link.py`.

**Turning it off is not permissive.** With no readings arriving the F-program
reads both channels as missing, and missing is a demand — the same argument
the `safe_speed` argument already rests on. The residual §11.6 names, a run
that drives with the sources never started, is unchanged by this brief and is
still the owner's `safe_speed` default question.

`check_contract_topics.py --print` still parses the README's ROS contract
table unchanged: the carrier publishes no topic, so the contract gained no
row.

## 8. What is still owed

1. **The joint run against the real writer on 45016**, with the writer's
   session log beside the carrier's, showing the seven `SafetyInputStandIn`
   members moving in the CPU. Nothing in this file touches a PLC.
2. **The F-side conversion** — frozen sequence → invalid channel → latched
   demand → SS1 → reset. Every sentence in this file that names a demand is
   quoting §11.5, not reporting one.
3. **A run at the vehicle's real rate against Gazebo**, rather than the
   stimulus used here, to confirm the 0.053 s worst gap survives a loaded
   machine. That figure is one session's, on an unloaded WSL, and is a sample
   rather than a bound (LESSONS 2026-08-05).
