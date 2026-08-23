# assets — provenance

Every file in this directory was produced from this repository. No vendor
marketing material is used.

| File | Origin |
|---|---|
| `amr-agent-infographic.png` | The layer-pyramid infographic fronting the root README — this repository's own work. |
| `m5-step1-gui/*.png` | Owner's screen captures of the `m5_ver2` Step 1 GUI run (2026-08-12). |
| `m5-step2-sensors/*.png` | Owner's screen captures of the `m5_ver2` Step 2 three-scanner run (2026-08-12). |
| `m6-fleet/*.mp4` | A live four-vehicle `m6/` run recorded 2026-08-23 — see the note below. |

## The M6 fleet recording, and how it was made

Both files are the SAME run: the full 39-process `m6/` stack, four
forklifts, each with its own virtual F-PLC, scanners and encoder
cross-check, worked by the VDA 5050 fleet manager over MQTT with the
edge/node traffic ledger on. Four transports were submitted, then four
more; **four completed**, the first three inside 455 s.

**These are not screen captures.** Under WSLg every window renders into
its own Wayland surface, so an X11 grab of the root window returns black
frames. The recording is Gazebo's own output instead: a camera sensor was
spawned into the ALREADY RUNNING world through the factory service, its
frames bridged to ROS and encoded directly. Nothing in
`gazebo/warehouse_ver2.sdf` was edited and the world was never restarted,
so the cell that produced these frames is byte-identical to the one every
figure in `m6/PROOF.md` was measured on. The camera runs at 8 Hz because
at 15 Hz it cost 0.14 of real-time factor and pushed the floor to 0.006 —
under the 0.010 at which the sixteen safety lidars stop delivering scans.
At 8 Hz the run held **RTF 0.563, floor 0.014**.

| File | What it is |
|---|---|
| `m6-fleet-01-four-trucks-4x-2026-08-23.mp4` | 2:09, captioned, **4× speed** (stated on the frame). The one to show. |
| `m6-fleet-02-full-run-1x-2026-08-23.mp4` | 8:35, no captions, 1× simulation time. The raw material, for re-cutting. |

**What the second half shows is a real limit, not a glitch.** Three of the
four trucks latch a protective demand and stop for good. A latch clears
only on a panel RESET, and an unattended run has no operator — residual
10 in `m6/PROOF.md`. It was left in rather than cut.

The first build's media — the M5 demonstration recording, the teleop
showcase, the cell captures, the HMI page captures and the forklift sensor
renders — moved with its documentation to
[`m5/m5_ver1/assets/`](../m5/m5_ver1/assets/); provenance for those files is
in the CREDITS beside them.
