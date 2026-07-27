brief:               docs/briefs/m3-03-bridge-design.md

status:              done

files_changed:
  - docs/interfaces/bridge-design.md   (new) bridge design, 12 sections
  - docs/reports/m3-03-bridge-design.md (this report)

invariants_touched:  none

what the document decides:

  1. Scope (§1). The bridge is one process that is an OPC UA client (invariant 4)
     and a ROS 2 node, and nothing else. It never listens on a socket, in any
     configuration including the test-double one. §1.1 is the NO-LOGIC RULE with
     17 concrete violations named for THIS cell and the owner of each decision:
     thresholding the photo-eye, latching a stop, meaning-changing debounce,
     sequencing the belt, any signal-gating timer, deriving product-present or
     drive-fault, counting edges or integrating travel from discarded encoder
     samples, clamping/ramping/zeroing the speed command, inverting the NC
     contacts, substituting a default for a missing sample, re-issuing a command
     after an outage. Permitted operations are exhaustive: float64 -> S7 Real
     narrowing (units unchanged), field addressing, bool marshalling, and the
     bridge's own heartbeat increment.

  2. Signal map (§4), derived one-to-one from opcua-nodes.md §9.9: 6 input nodes
     written, 1 output node read and republished, 1 heartbeat, plus Status/* and
     BridgeLinkOk read at 1 Hz for logging only and applied to nothing. Cadence
     per §9.2: analogs cyclic 20 Hz latest-sample, contacts on-change plus full
     refresh on every connect, ConveyorSpeedCommand polled 20 Hz. Latest-sample
     decimation is implemented as depth-1 slots, never queues, so no sample can
     accumulate and nothing can be derived from what is discarded (§2, §4.6).

  3. Update model (§5). Writes cyclic/on-change; the output path is POLLED, not
     subscribed, and the reason is measurement honesty: a monitored item's
     notification time is the sum of server sampling phase, publish interval,
     queue occupancy and network, none of which a client can separate, so the
     "latency" it yields is mostly a measurement of the server's configuration.
     Polling also gives one cadence, one ordering guarantee, and independence
     from the S7's monitored-item limits. The cost is stated rather than hidden:
     0-50 ms of poll phase, reported as its own component.

  4. Startup (§6) — closes m3-01 open question 2. The bridge writes NO input node
     before it has a real sample for that signal, and writes NO heartbeat until
     all six inputs have been written from real samples and acknowledged. The
     rule the PLC can rely on, in one sentence: while BridgeHeartbeat is not
     advancing the input values are not attributable to the cell; once it has
     advanced once, every input has carried a real sample. sim/README.md's "safe
     choice - contacts read as pressed, command zero" is honoured, but as the
     PLC input-image DB START VALUES (§6.3, an interface expectation for m3-05),
     not as values the bridge invents. No new node was needed for this.

  5. Liveness (§7). BridgeHeartbeat is a UInt16 monotonic counter at 20 Hz,
     wrapping at ~54.6 min, written AFTER the cycle's input writes are
     acknowledged - so an advanced heartbeat implies that cycle's inputs landed
     (ordering, not atomicity). Counter chosen over timestamp because a timestamp
     needs the bridge host and PLC to agree on an epoch and adds clock skew and
     NTP as failure modes of a liveness signal, in a cell that already has three
     time bases. The PLC must test for CHANGE, never subtract. All four failure
     modes are tabulated: crash, clean shutdown, OPC UA loss, and sim-stopped-
     while-bridge-alive. The first three are indistinguishable to the PLC (only
     how fast the session disappears differs, and a program that behaves
     differently for crash vs clean shutdown is wrong). The fourth is the honest
     limitation: the input image LOOKS LIVE. Three fixes for it were considered
     and rejected as bridge logic; the recommendation to m3-05 is that
     ConveyorDriveFault already covers it. Reaction is stated throughout as PLC
     content; the document specifies only what the PLC can observe.

  6. Reconnect (§8). NodeIds and namespace index re-resolved every session, full
     input refresh, heartbeat resumed only under the §6 rule. Five explicit
     no-resume rules: the bridge publishes only what it read in the current
     cycle, never replays a pre-outage value, publishes nothing while
     disconnected, and holds no command state that could resume anything. §8.4
     states the residual honestly: while the bridge is down no command can reach
     the cell and gz's JointController holds the last velocity, so the belt keeps
     running until the bridge returns with the PLC's CURRENT command. That is the
     cell's property by m3-01's design; the bridge must not "fix" it by
     publishing zero, because a transport that stops equipment is a controller.

  7. Measurement (§9), gate exit item (c). Seven intervals defined (L1 input hold
     / L2 input write / L3 sum / L4 poll phase, explicitly NOT measurable / L5
     output apply / L6 cell actuation in sim time / L7 closed loop including one
     PLC scan) plus achieved cycle rate, per-node rate and decimation ratio.
     Clock rules: every interval differences one clock; CLOCK_MONOTONIC on the
     bridge, sim time only for cell-side actuation with RTF recorded, header
     stamps never differenced against monotonic, the PLC clock in no interval.
     Reported as count, duration, min, median, p95, max - never a mean alone -
     with overruns, errors, reconnects and NaN counts. Instrumentation is always
     on, so the measured path is the production path. Evidence lands in
     fleet/bridge/EVIDENCE_LATENCY.md with raw CSV alongside, split into a
     test-double section (agent-run) and a PLCSIM section (owner-run). §9.5 is
     the honesty section: what cannot be measured without the real PLC (scan
     contribution, S7 server behaviour, PLCSIM fidelity, absolute L4, network
     path, PLC reaction time) versus what the double genuinely establishes.

  8. Test double (§10). An OPC UA server mirroring the §9 address space, purpose
     stated as automated in-container verification of the BRIDGE. Limits stated
     plainly: no scan cycle, no process image, no interlocks, no program - it
     proves nothing about plc/demo-cell/SPEC.md, and ADR 0004's rejection of
     "prove the loop against a mock only" stands. Invariant 4 preserved: the
     server role is the PLC's, played by the double; the bridge is a client with
     no code-path difference between the two. Any echo or driver behaviour in
     the double is labelled test scaffolding in code and in the evidence file.

open_questions:

  1. DEPENDENCY APPROVAL REQUIRED - asyncua. This is the only new dependency and
     nothing in m3-04 can proceed without a decision.

       asyncua        NEW, needs approval. Python OPC UA stack, pure Python,
                      async, LGPL-3.0. Provides BOTH the client (the bridge) and
                      the server (the test double), so the double adds no second
                      dependency. Transitively pulls cryptography for secure
                      channels. Verified in this container: there is no apt
                      candidate for python3-asyncua, so the install path is
                      "pip install asyncua==<pinned>" through the proxy, pinned
                      in a requirements file under fleet/bridge/. pip 24.0 is
                      present.

       rclpy, std_msgs, sensor_msgs, rosgraph_msgs   NOT new, from
                      ros-jazzy-ros-base, already installed by sim/setup/install.sh.
       python3-yaml   NOT new, already a ROS 2 dependency, used for the config file.
       stdlib asyncio, time, statistics, csv, logging, dataclasses, threading
                      NOT new. statistics.quantiles covers p95, so numpy is
                      deliberately NOT requested.

     Alternatives considered and not recommended: python-opcua/opcua (the
     deprecated predecessor of asyncua) and open62541 bindings (a C toolchain
     dependency for an eight-node address space). If asyncua is declined, the
     bridge cannot be implemented as designed and m3-04 must be re-briefed.

  2. fleet/README.md needs one line, and it is not my file. Its "This layer must
     not access" section forbids ROS 2 topics, services and actions - correctly,
     for the fleet MANAGER. m3-04 places the bridge at fleet/bridge/, and the
     bridge is by definition a ROS 2 node, so a verifier reading only that README
     will flag it. Requested addition: a stated exception that fleet/bridge/ is a
     separate process which shares no code, state or configuration with the fleet
     manager, per ADR 0004's rejection of folding the bridge into it. Alternative
     if the owner prefers no exception: move the bridge out of fleet/ to a
     top-level bridge/ directory, which would change the m3-04 brief and the
     repository layout in CLAUDE.md section 4. I did not choose between these.

  3. For m3-05 (PLC program spec), three items this design hands over:
     (a) the input-image DB start values of §6.3, and the requirement that the
         program qualify inputs with the heartbeat predicate rather than with
         start values, since a WARM restart leaves the previous session's values
         in place;
     (b) NaN handling on ProductSensorRange - the bridge writes it through
         unchanged by design, and a NaN makes "range < 1.00" false, i.e. reads as
         "no product", which the program must handle explicitly;
     (c) §7.3 case D - sim stopped with the bridge alive leaves a live-looking
         input image; ConveyorDriveFault is the existing node that can catch it.

  4. The 20 Hz cycle period is inherited from opcua-nodes.md §9.2 as an
     expectation. If m3-04's measurements justify a different number, §9.2 and
     bridge-design.md §5 must be updated in the SAME commit, per the LESSONS.md
     rule about same-gate documents contradicting each other.

next_suggested:      m3-04 bridge implementation, but only after the asyncua decision and the fleet/README.md scope question are settled; both block the implementation brief rather than the design.
