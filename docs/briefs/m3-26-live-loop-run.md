# Brief m3-26 — live loop against the commissioned PLC

gate:                M3
agent:               bridge
goal:                the Gazebo cell, the bridge and the running PLCSIM program are exercised as one loop and the measurable part of Section B is captured from that run
invariants_touched:  none
inputs:              [bridge/README.md, bridge/EVIDENCE_LATENCY.md (Section B), bridge/EVIDENCE_CONNECT.md, bridge/config/bridge.yaml, plc/demo-cell/SPEC.md (read only, for T1-T4 and the expected reactions), docs/interfaces/opcua-nodes.md (read only)]
deliverable:         bridge/EVIDENCE_LATENCY.md Section B, filled with what this run measures
done_when:           either the loop ran and Section B carries dated measurements with the owner-outstanding items named explicitly, or the run was blocked and the report states precisely where and why, with the diagnostic evidence
forbidden:           [driving TIA Portal, downloading to the CPU, modifying the TIA project, claiming gate items (a) or (b) as met, redefining any gate criterion, editing files outside bridge/, changing code behaviour to make a test pass, adding dependencies]

## The owner authorised this run

PLCSIM Advanced is running now with FB_DemoCellControl from OB30 at 20 ms,
CPU in RUN, endpoint `opc.tcp://192.168.53.1:4840`, security None,
anonymous. The owner asked for this loop to be run for them. Connecting to
192.168.53.1 is therefore authorised for this brief, superseding the
prohibition in earlier briefs. You still never download, never modify the
TIA project and never write outside the DemoCell input nodes the bridge
owns.

## Step 0, before anything else — connectivity

The bridge must run in WSL for ROS 2, while the PLCSIM adapter is a
Windows-side virtual adapter (host 192.168.53.241/24, instance
192.168.53.1/24). Whether WSL2's NAT reaches that adapter is unknown and
is the first thing to measure, not assume. Test in this order and record
each result: ping 192.168.53.1 from WSL; a TCP connect to port 4840 from
WSL; an asyncua connect-and-read of one node from WSL. If WSL cannot
reach the endpoint, stop and report — with the ping, route and ipconfig
evidence and the options you see. Do not spend the run improvising a
network workaround; an honest blocked report is the deliverable in that
case.

## The run

Take T1 to T4 from plc/demo-cell/SPEC.md. Expect the cell to start
latched: the owner read BridgeLinkOk False, CellProcessStopActive True,
CellResetRequired True, ConveyorSpeedCommand 0.0 before any bridge
existed, which is the specified cold start. Clearing those latches through
the panel reset contact is part of the scenario, not a workaround.

Capture, from this run: the connect log with both namespaces resolved and
the granted session timeout with the derived keep-alive (expected 10.000 s
against a 30 000 ms grant — report the actual value); cycle rate and
overrun count; the latency figures Section B asks for across all seven
inputs; the signal-loss repeat that Section B item 6 names; and at least
one Gazebo screenshot showing the conveyor driven by the PLC. Isolate the
simulation with a unique GZ_PARTITION and ROS_DOMAIN_ID and kill only the
processes you started.

## What you must not claim

Gate items (a) and (b) require a TIA watch table, which is a GUI artifact
you cannot produce. Measure and report the OPC UA-side equivalent, state
plainly that it is not the watch table, and leave those two items marked
owner-outstanding. Section B items you cannot measure — the CPU's
configured scan cycle and the invariant-8 confirmation of the measurement
network path — stay owner-outstanding too, named as such.
