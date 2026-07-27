gate:                M3
agent:               sim
goal:                A Gazebo world of fixed equipment only, exposing conveyor, product sensor and operator panel as ROS 2 topics.
invariants_touched:  none
inputs:              [docs/adr/0004, docs/adr/0003, sim/worlds/warehouse.sdf (style reference), CLAUDE.md invariant 12]
deliverable:         sim/worlds/cell.sdf + sim/launch/cell_bringup.launch.py + evidence capture
done_when:           Headless in this container: the world spawns; a conveyor actuator accepts a ROS 2 command and visibly moves product; a product sensor publishes a boolean-equivalent state that changes when product is present; start/stop/e-stop panel inputs are publishable ROS 2 topics; all I/O is listed in a signal table in sim/README with topic, type and direction; evidence file records real captured output.
forbidden:           [any control logic, sequencing, interlocks or timers in the world or launch files, AMR models, MuJoCo, OPC UA client code (that is the bridge), editing directories other than sim/ and the report]
