gate:                M3
agent:               interface
goal:                Extend the OPC UA node model with the demonstration cell's fixed-equipment I/O nodes.
invariants_touched:  none
inputs:              [docs/interfaces/opcua-nodes.md, sim/README signal table from m3-01, docs/adr/0004, docs/safety/SRS.md]
deliverable:         docs/interfaces/opcua-nodes.md, new section for the demonstration cell I/O
done_when:           Every signal in the m3-01 table has a node with BrowseName mirroring the intended PLC tag (PascalCase, physical thing + meaning), S7 and OPC UA data type, direction from the client's view, update semantics and single owner; input bits (from Gazebo) and output bits (to Gazebo) are separated; the demonstration e-stop is labelled a PROCESS stop in the standard program, not a safety function; nothing in the section grants a client write access to an actuator output.
forbidden:           [inverting server/client direction, putting logic or sequencing in the node model, labelling any node a safety function, editing directories other than docs/interfaces/ and the report]
