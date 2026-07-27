gate:                M3
agent:               fleet
goal:                The bridge process implementing the approved design.
invariants_touched:  none
inputs:              [docs/interfaces/bridge-design.md, docs/interfaces/opcua-nodes.md, sim/ from m3-01]
deliverable:         fleet/bridge/ package (ROS 2 node + OPC UA client) with configuration file and README
done_when:           The bridge runs in this container against the m3-01 world and a local OPC UA server test double that mirrors the m3-02 address space (test double clearly labelled as a stand-in for PLCSIM, used for automated verification only); signals traverse both directions; latency and update rate are measured by the bridge's own instrumentation and written to an evidence file; stopping the bridge produces the liveness behaviour the design specifies.
forbidden:           [control logic, sequencing, interlocks, timers that alter behaviour, writing to nodes not marked client-writable, inverting server/client direction, editing directories other than fleet/ and the report]
