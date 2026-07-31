# Brief m5-05 — lidar beams visible in the Gazebo GUI, with a measured cost

```
gate:                M5
agent:               sim
goal:                the three lidar beam sets are visible in the Gazebo GUI,
                     and the render cost of the new sensor set is measured
                     rather than assumed.
invariants_touched:  none
inputs:              [sim/worlds/forklift_arena.sdf,
                      sim/setup/CONTAINER_TOOLCHAIN.md,
                      agv/forklift/model.sdf and its EVIDENCE_SENSOR_* files
                      (read only — agv/ is not yours),
                      docs/roadmap.md row M5 item (c)]
deliverable:         sim/worlds/forklift_arena.sdf and a render-budget section
                     in the sim evidence
done_when:           the arena world carries the `VisualizeLidar` GUI plugin in
                     its `<gui>` block so beams can actually be drawn; a
                     screenshot or an equivalent captured artifact shows the
                     beams for at least the navigation lidar; and the render
                     budget is MEASURED at the new 910-ray sensor set —
                     headless RTF, GUI RTF, and the delta with beam
                     visualisation on versus off — with the numbers quoted as
                     the tools printed them.
forbidden:           [editing agv/ or the model's sensor definitions; changing
                      sensor sample counts or update rates; editing
                      sim/launch/ (a parallel brief owns it) or sim/setup/
                      install.sh; committing (the orchestrator commits);
                      reporting a figure no tool printed]
```

## The trap this brief exists to avoid

In Gazebo Harmonic, `<visualize>true</visualize>` on the sensor is **necessary
but not sufficient**: the `VisualizeLidar` GUI plugin is not part of the
default GUI config, it never reads the sensor's `<visualize>` flag, and it
auto-discovers topics advertising `gz.msgs.LaserScan` for the user to select.
Every Gazebo-Classic tutorial says otherwise and is wrong here. Canonical
reference: gz-sim's own `examples/worlds/visualize_lidar.sdf`. Display modes
are ray lines, points and triangle strips; ray lines cost N line segments per
scan per frame, so say which mode the captured artifact used.

Rendering here is llvmpipe software rasterisation — confirmed, `GL_RENDERER =
llvmpipe (LLVM 20.1.2, 256 bits)` — and the headless run already measured
RTF 1.0004 with all three sensors publishing at ~10 Hz. The open question is
what the GUI and the beam drawing add on top. If the GUI is too slow to be
usable here, that is a finding to report with its numbers, not a failure:
the showcase recording happens on the owner's machine.

The `--` inside XML comments hazard applies to this file: it is forbidden by
the spec and ElementTree enforces it. `forklift_arena.sdf:326` is already
known to carry one; if your edit lands near it, note it rather than silently
fixing an unrelated defect.

Do not commit. Leave files modified/untracked and write your report to
docs/reports/m5-05-beam-visualization.md.
