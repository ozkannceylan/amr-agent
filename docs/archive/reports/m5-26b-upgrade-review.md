# m5-26b — adversarial review of the dist-upgrade: what was not checked

    brief:               (orchestrator dispatch, verifier; reviews docs/reports/m5-26-dist-upgrade.md)
    status:              done
    files_changed:
      - docs/reports/m5-26b-upgrade-review.md   (this file, only change)
    invariants_touched:  none
    open_questions:      see findings 4 and 7
    next_suggested:      none required by this review; the m5-26 report's own
                         next_suggested stands unchanged

## Verdict: pass-with-findings

**The upgrade broke nothing this review could find, including in the layers
the m5-26 verification never looked at.** The three reported verifications
were taken as done (per the review posture) and nothing found here casts doubt
on them. Every additional probe run today — the bridge venv, the joint
asyncua+rclpy import, a live OPC UA session to the running PLC, the HMI venv
and server import, the Python interpreter versions, the Gazebo delivery
packages, a windowed (non-headless) render run, and the tracking files —
passed. The findings below are two document inaccuracies and two
report-strength notes, none of them a broken machine.

## What was probed, and what each probe showed

All probes were cheap and read-only against the repo; the only processes
started were one 45 s windowed Gazebo run of `cell.sdf` (torn down to
pgrep-zero, `GZ_PARTITION` isolated) and one 10 s-timeout OPC UA browse. No
password was requested, handled or stored; nothing needed root.

| # | Probe | Result |
|---|---|---|
| 1 | Bridge venv location and interpreter | `/home/ozkan/amr-bridge-venv` (this machine's documented location; `/opt` is the container's), Python **3.12.3**, matching `pyvenv.cfg` and the system python3 |
| 2 | Joint import, ROS sourced, in the bridge venv | `import asyncua, rclpy` OK; asyncua **2.0.1** (the pinned version); `rclpy.init()` / node create / shutdown OK against the upgraded rclpy tree |
| 3 | **Live OPC UA session to the PLC** from the bridge venv | `opc.tcp://192.168.53.1:4840` — session established, Objects browsed: `Server, DeviceSet, 1513F-1 PN, ServerInterfaces`. The bridge's whole dependency path (venv → asyncua → network → CPU) works post-upgrade |
| 4 | HMI venv | `/home/ozkan/amr-hmi-venv`, plain venv as documented, Python 3.12.3, asyncua 2.0.1; `hmi_server` imports clean under it |
| 5 | Python itself | `python3.12` **3.12.3-1ubuntu0.15 before and after** — the upgrade did not move the interpreter at all, so no venv on the machine was invalidated |
| 6 | System cryptography under the `--system-site-packages` bridge venv | Moot: the venv carries its **own** `cryptography` 49.0.0 wheel inside the venv, shadowing the system 41.0.7; the 2026-07-27 LESSONS concern cannot bite |
| 7 | Gazebo delivery | All four `ros-jazzy-gz-*-vendor` packages byte-identical before/after (checked against `~/m5-26-snapshot/all-versions.txt`); `gz-sim` GUI is 8.11.0. "Gazebo packages changed: 0" is confirmed |
| 8 | **Windowed render configuration** (see finding 1) | `gz sim -r` (server + GUI) on `cell.sdf`, 45 s under WSLg: GUI came up, MinimalScene/3D View loaded, `GL_RENDERER = llvmpipe (LLVM 20.1.2, 256 bits)` in a truncated-first ogre2.log, no crash, teardown to zero |
| 9 | Archive currency today | `apt list --upgradable` → **0**; still no holds |
| 10 | Tracking files vs the report | Consistent. TODO's "(i) DONE by m5-26" block matches the report; the `install.sh` guard TODO records as dropped landed as its own sim commit (`927feb1`) after the report, so the report's OQ1 ("not made, separate deliverable") and TODO's closure are both true in sequence |

## Findings, ranked

**None of these means the upgrade broke something the owner needs back.**

1. **(Report strength, now closed by measurement) The NVIDIA-580 EGL finding
   was closed on one configuration; the showcase configuration was not it.**
   The m5-26 reading — and its pre-upgrade baseline — were both taken with
   `gz sim -s --headless-rendering`, the EGL-surfaceless path. Showcase
   recordings run the GUI through WSLg's display path, where vendor selection
   is a different mechanism, so "the post-upgrade reading was taken with the
   new vendor in place and still says llvmpipe" was, as written, a claim about
   the headless configuration only. Probe 8 closed the gap: the windowed run
   also lands on llvmpipe with the 580 vendor installed, and the GUI survives.
   One honesty caveat on my own probe: server and GUI share one
   `~/.gz/rendering/ogre2.log` and exactly one `GL_RENDERER` line landed, so
   that line cannot be attributed to server-vs-GUI process with certainty —
   what is certain is that the windowed session as a whole ran 45 s on
   llvmpipe without a fault.
2. **(Low, document) `WSL_ENVIRONMENT.md` §18.1 states "Harmonic comes from
   `packages.osrfoundation.org`, which was already current." That is false on
   this machine.** No osrfoundation apt source exists (`/etc/apt/sources.list*`
   grep: nothing), and §17's own origins list does not include it — the
   statement contradicts the section four paragraphs above it. Gazebo arrives
   via the `ros-jazzy-gz-*-vendor` packages from packages.ros.org, under
   `/opt/ros/jazzy/opt/`, which is also why `gz` is only on PATH after
   sourcing ROS (install.sh's closing lines say this correctly). The
   conclusion the sentence supports — Gazebo unchanged at 8.11.0 — is verified
   true (probe 7); only the mechanism is wrong. A rebuild-from-this-document
   reader would go looking for an apt source that does not exist. One-line fix
   for the `sim` agent's next touch.
3. **(Low, report strength) Open question 3 overstates which evidence files
   the upgrade invalidated.** It says the upgrade "moved 288 ROS packages
   under" four EVIDENCE files including `EVIDENCE_NAV2.md` and
   `EVIDENCE_LOCALIZATION.md` — but those two are container-qualified by their
   own §0 blocks (the very point LESSONS 2026-08-05 makes), and a WSL upgrade
   does not touch the container environment their figures are qualified by.
   TODO already narrows the qualifier request to the two WSL-measured files
   (`EVIDENCE_ENVELOPE.md`, `EVIDENCE_VEHICLE_IMAGE.md`), which is the correct
   scope. No action beyond following TODO's version.
4. **(Info, for the record) The venv location differs from the LESSONS phrasing
   and from this review's own dispatch.** LESSONS 2026-07-27 and the dispatch
   both say `/opt/amr-bridge-venv`; on this machine both venvs live under
   `$HOME`. This is already handled — `stack.sh` probes both paths,
   `bridge/README.md` and `WSL_ENVIRONMENT.md` §3.2 document the split — so it
   is a reader's trap, not a defect. Anyone scripting against the LESSONS line
   verbatim on this machine gets "No such file or directory", as this review
   did on its first probe.
5. **(Pass, stated plainly) Everything else examined is fine.** The bridge's
   full path to the live PLC works (probe 3 — the one integration m5-26 never
   exercised). The HMI stack imports. Python did not move, so no venv was
   invalidated — the "silent minor-version bump" risk did not materialize.
   The machine is still 0 behind the archive a day later. The tracking files
   agree with the report and with the repository. Node.js is absent in WSL as
   before (the capture tooling runs Windows-side) and the upgrade could not
   have touched it.

## The claims of the m5-26 report, judged

The report is unusually careful — timing quoted as a draw not a confirmation,
the AMCL-yaw parsing flaw self-declared, the un-re-run observations listed.
Two claims were stronger than their evidence: the NVIDIA/EGL closure (finding
1 — true, but for one configuration; now measured in the second) and the OQ3
file list (finding 3 — overbroad; TODO's narrowing is right). No claim was
found false about the machine's working state.

## Verdict for the owner, in one paragraph

**No — the upgrade did not break anything.** The vehicle stack was verified
by the upgrade run itself, and this review checked what that run did not: the
bridge's Python environment still imports its OPC UA and ROS libraries
together and holds a live session to the running PLC; the HMI environment is
intact; Python itself did not move, so nothing built against it was
invalidated; Gazebo's packages are byte-identical and the simulator renders
correctly in the windowed configuration the showcases use, not only the
headless one that was tested. What should be done next is unchanged from the
m5-26 report's own list — re-run the five remaining envelope observations and
add the environment pointer to the two WSL-measured evidence files — plus one
one-line documentation fix: `WSL_ENVIRONMENT.md` §18.1 names a package source
(osrfoundation) that does not exist on this machine; Gazebo comes from the ROS
vendor packages.
