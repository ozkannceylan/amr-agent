# m5-56 — the WSL-side speed-source client

    brief:               issued in-session (no file under docs/briefs/), against
                         plc/forklift-safety/SPEC.md §11.2 and the m5-49 report's
                         request 2 ("agv/: the WSL-side SPD/MOT/PING client")
    status:              done
    invariants_touched:  none

## files_changed

| File | What |
|---|---|
| `agv/forklift/scripts/safe_speed_link.py` | **New — the deliverable.** The carrier: subscribes to the two channel topics and the two motion topics, dials the writer's §11.2 listener on 45016 over one non-blocking TCP connection, and emits `SPD A/B <int mm/s>`, `MOT <p> <v>` and a 1 Hz `PING`. Scaling `round(v × 1000)` signed; **never scales and never sends** a non-finite value or one outside the S7 Int wire range. Consume-once slots, so the never-repeat property is a property of the class rather than of its callers' discipline. Every window on a **steady** clock, message age taken at arrival. `--selftest`: 29 checks, no ROS, no network |
| `agv/forklift/scripts/speed_link_rig.py` | **New — the local proving rig, explicitly not the stand-in writer.** `sink` models the writer half of §11.2 and writes to no PLC; `plant` stimulates the producer's two gz reads and a scan so the chain runs with no Gazebo and can go **silent** the way a dead source does; `inject` publishes values the producer cannot emit, each with a positive control |
| `agv/forklift/EVIDENCE_SPEED_LINK.md` | **New.** Environment, which half is proven and which is not, and seven measured runs (A, B, B2, B3, C, D1/D2, E/E2) plus the launch-condition evaluation |
| `agv/forklift/evidence/speed-link/` | **New.** Eight sink CSVs, and one session log per process per run, unique name per start |
| `agv/forklift/config.yaml` | New `safe_speed.link:` block — host (read-back, `auto`), port 45016, 1 Hz keepalive, reconnect and connect-deadline, the two freshness windows and the Int wire bounds, each with its derivation on the row |
| `agv/forklift/launch/vehicle.launch.py` | New `safe_speed_link` argument (default `true`), the carrier action, and an explicit two-term condition so it runs only when `safe_speed` is also on |
| `agv/forklift/README.md` | Two rows in the scripts table. The ROS contract table is unchanged — the carrier publishes no topic |

Nothing outside `agv/` (plus this report) was written. **`plc/` and `bridge/`
were read and never touched.** Nothing committed, no branch created, no
dependency added.

## What was proven, and against what

All runs in **WSL 2 / ROS 2 Jazzy**, `ROS_DOMAIN_ID=71`,
`GZ_PARTITION=m5-56-speed-link`, no Gazebo process started.

1. **The readings and the motion observation reach the link at the seam's
   rate.** 30 s run: 451 `SPD A`, 452 `SPD B`, 498 `MOT`, 0 malformed as
   parsed by an independent reader of §11.2. On the consumer side the
   freshness sequence advanced every 0.055 s on average and — the number that
   matters — **was never frozen for longer than 0.052 s**, against a
   `SPEED_STALE_MAX` of 500 ms.
2. **The producer stops and the client stops with it**, three ways, each with
   the positive control inside the same run: source silent (11.6 s frozen at
   `SeqA 213`, reading held at 292 mm/s, **no zero ever written**), producer
   `SIGKILL`ed while moving (11.05 s frozen), and producer killed **at rest**
   — the case that matters, where `MotionPresent` had been FALSE for 225
   cycles and the consumer drove it TRUE 0.253 s after the last `MOT`.
3. **Reconnection behaves, and the refusal is survivable.** A second carrier
   was refused five times by the listener and retried at 1 Hz without wedging
   or sending a non-reading; the first carrier survived a sink outage — EOF,
   seven logged failures, reconnect on attempt 8 — and **replayed nothing**
   across the gap.
4. **Both refusals exercised at the ROS seam**, `NaN` (151 refused) and 40 m/s
   (152 refused), each followed by a finite positive control on the same
   topic: the sink saw **only** the control value, never a zero, a held value
   or a wrapped integer.
5. **The real geometry**: WSL client → a listener on the **Windows** host, the
   address read back from the WSL default route and logged. 453 advances,
   same 0.053 s worst gap as loopback, then 8.8 s of frozen sequence after the
   source stopped with the link still up.

## What is NOT proven, stated plainly

- **The far end.** No PLC was touched, no writer member moved, no F-network
  ran. Every sentence in the evidence that names a demand quotes §11.5's rule;
  none reports one. The sink was written from the same §11.2 paragraph as the
  client, so its agreement is weaker evidence than it looks.
- **The spec's port against the real writer.** Run E used **45116**, because
  a stand-in writer was **already listening on 45016 on this host** while this
  brief ran (see concern 1).
- **No integrity claim** of any kind is made or implied. No Category,
  Performance Level, SIL or PFH appears in any file written here; the readings
  arrive at the safety program as standard data over a stand-in path.

## open_questions

1. **The writer's 45016 extension appears to already be running.** A
   connectivity probe found `standin_writer.ps1 -Instance safecell3`
   listening on **both 45015 and 45016** at 19:09 on 2026-08-06, and
   `bridge/standin_writer/testing/speed_feed.ps1` is present in the working
   tree — another session is landing the other half concurrently. **The joint
   run may be possible immediately**, and it is the next thing to schedule.
   *Disclosure:* one probe from WSL opened and closed a connection to that
   live listener at ~17:11 UTC before the collision was understood. It sent no
   bytes and may appear in that session's writer log as a connection.
2. **The vehicle-side motion window adds to the writer's budget.** §11.2
   specifies `MOTION_SILENCE_MAX` = 250 ms at the writer. The carrier stops
   forwarding `MOT` after its own `motion_fresh_max_s` = 0.15 s, so worst-case
   time from a dead observation to `MotionPresent := TRUE` is **0.40 s**, not
   0.25 s. It is latency on the *safe* transition and is bounded and
   documented, but §11 should say the number rather than inherit it.
3. **The out-of-Int-range refusal is a decision this brief made.** §11.2 names
   only the non-finite rule. A reading that will not fit the Int is refused
   (silence ⇒ missing ⇒ demand) rather than clamped, because a wrapped Int is
   a value and a wrong one. If the spec would rather clamp to the plausibility
   window, that is a one-line change here — but the refusal is the demanding
   direction.
4. **Sequence wrap.** The rig wraps its model sequence at 32768. What the real
   writer does at Int overflow is `bridge/`'s to state; the F-side `CMP <>`
   against a memory is indifferent to the wrap, but the behaviour should be
   written down rather than discovered.
5. **The `reading_fresh_max_s` window never fired in any live run** (`discarded
   stale A 0` in every session). It is covered by the selftest and by
   construction, not by an observation — it exists for a queued-behind-a-stall
   arrival, which none of these runs produced.
6. **Refusals are logged per tick** — 151 lines in 8 s in run D1. Each is a
   reading that did not reach the monitor, so none is noise in principle, but a
   fault standing for minutes would produce a large file. Worth a rate limit
   with a count, if the owner wants one.
7. **`derive_writer_host` is duplicated** from `field_evaluation.py` (which
   imports `rclpy` at module scope, so it cannot be imported by a node whose
   selftest must run with no ROS). Both follow ADR 0006's read-back rule
   today; they should be one module when `agv/` gains a place for one.
8. **The 0.052 s worst gap is one session's sample on an unloaded WSL**, not a
   bound (LESSONS 2026-08-05). It should be re-measured against Gazebo at the
   vehicle's real load before anything depends on it.
9. **The arming residual of §11.6 is unchanged** by this brief: the carrier is
   coupled to `safe_speed`, which still defaults `false`. Whether it should
   default `true` remains the owner's call (m5-48 open question 2).

## next_suggested

The joint run: carrier against the real `standin_writer` on 45016, with both
session logs and the seven `SafetyInputStandIn` members read back in the CPU —
the writer's half appears to already exist, so this is scheduling, not build.
