brief:               docs/briefs/m3-01-fixed-equipment-world.md

status:              done

files_changed:
  - sim/worlds/cell.sdf              (new) fixed-equipment cell world
  - sim/launch/cell_bringup.launch.py (new) headless bringup + ros_gz bridge
  - sim/worlds/CELL_EVIDENCE.md      (new) dated capture of a real run
  - sim/README.md                    (edited) added "Demonstration cell (M3)"
                                     with the signal table; the
                                     "This layer must not access" section and
                                     all warehouse/M5 content are untouched

invariants_touched:  none

what was built:
  A Gazebo Harmonic world with no vehicle in it: a conveyor whose belt is a
  prismatic joint driven by gz JointController from a ROS 2 velocity
  command, a 0.3 m product box carried by belt friction, a retro-reflective
  photo-eye modelled as a single-beam gpu_lidar firing across the belt to a
  reflector post, and an operator panel pedestal whose three contacts are
  ROS topics created by the bridge. One launch file starts the world
  headless and bridges every signal. Eight topics total: one PLC output,
  five PLC inputs, two diagnostics.

verification (headless, this container, 2026-07-27, full capture in
sim/worlds/CELL_EVIDENCE.md):
  - World spawns: 6 models, 0 error lines, 0 warning lines in the launch log.
  - Conveyor: publishing std_msgs/Float64 0.15 on /cell/conveyor/cmd_speed
    moved the product from x = -1.000 m to +0.654 m; the box tracked the
    belt joint with a constant -1.00 m offset for the whole run, so it is
    transported by friction, not teleported. 0.0 stopped it, -0.15 reversed
    it. Verified both from a persistent publisher and from a bare
    "ros2 topic pub -1".
  - Product sensor: 1.440 m clear, 0.540 m blocked. Both the entering and
    the leaving transition were captured on the forward run, plus a third
    transition on the reverse run.
  - Panel: all three contacts toggled true/false, read back on the ROS side
    and observed crossing into Gazebo with "gz topic -e".
  - Real time factor 1.0 at a 2 ms fixed step, unlike warehouse.sdf's ~0.1,
    so M3 latency measurements will not be distorted by the simulator.

no logic in this layer:
  The world and the launch file contain no sequencing, interlock, timer,
  latch, debounce or threshold. The belt turns whenever a velocity is
  commanded, including while the process-stop contact reads pressed, and
  the photo-eye publishes a raw distance rather than a present/absent bit.
  Both are deliberate: refusing a command or thresholding a range would put
  process decisions in the simulation layer.

open_questions:
  1. DEVIATION FROM THE BRIEF'S WORDING, please confirm. The brief asks for
     a "Start, Stop and E-stop" panel. ADR 0004 requires that a
     demonstration stop button be labelled a PROCESS stop "in every
     document, tag name and recording", so the topic is
     /cell/panel/process_stop, not /cell/panel/estop, and the README says
     in as many words that it is not a safety function. If the owner wants
     the literal name "estop" the ADR has to be revisited first.
  2. No initial value. ROS topics are not retained, so before the first
     publish the three panel contacts and the conveyor command have no
     value at all. Which value the PLC sees at bridge startup is an m3-04
     decision; the safe choice is contacts read as pressed and belt
     command reads as zero, but the cell cannot make that choice for it.
  3. Belt encoder rate. /cell/conveyor/joint_state publishes at the physics
     rate (~500 Hz) because gz's JointStatePublisher has no rate parameter.
     m3-04 needs a stated decimation to the PLC scan rate; adding a rate
     filter in the world would have been a policy decision in the wrong
     layer.
  4. Naming authority. The signal names in the README table
     (ConveyorSpeedCmd, ProductSensorRange, PanelStartContact, ...) are
     proposals in the project's PascalCase style. m3-02 owns the
     authoritative PLC tag and OPC UA node names.
  5. Belt travel is finite, +-2.50 m mechanical stops. A repeated demo
     cycle needs the belt returned towards home between runs. Whether the
     cell should also expose a home/limit signal is an interface question
     for m3-02, not a simulation one; nothing was added speculatively.
  6. Stale heading, not fixed because it is outside this brief. The
     pre-existing section "Navigation scenario (M3)" in sim/README.md is
     now M5 work under ADR 0004. sim/scenarios/DEFERRED.md already records
     the deferral correctly; only that one README heading still says M3.
     The Contents block now labels warehouse.sdf as M5, so the file is not
     misleading, but the heading should be corrected by whoever next holds
     a brief for it.
  7. /cell/product_box/pose is ground truth and is marked in the table as
     NOT a PLC signal. It must not become an OPC UA node: a real conveyor
     has no product-position transducer, and modelling one would give the
     PLC information the real cell cannot provide.

lesson worth recording:
  rclpy's Node already owns the attribute self._clock, so a subscriber
  callback named _clock is silently shadowed and rclpy then rejects it with
  a misleading "callback should be callable with one argument" error. Name
  ROS callbacks cb_* in this project.

next_suggested:
  m3-02 OPC UA node model, using the signal table in sim/README.md as its
  input list; the boolean thresholds for the photo-eye and the polarity
  handling of the two NC contacts are the first two decisions it has to
  make.
