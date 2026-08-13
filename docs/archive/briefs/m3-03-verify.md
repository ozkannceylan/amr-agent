gate:                M3
agent:               verifier (read only on the repo; may execute the launch files)
goal:                Independently re-run the M3 scenario and confirm the gate's observable behavior.
invariants_touched:  none
inputs:              [CLAUDE.md section 6 (M3 row), sim/, docs/briefs/m3-01..02]
deliverable:         Verdict returned to the orchestrator, filed as docs/reports/m3-03-verify.md.
done_when:           The verifier re-executes the bringup and the navigation scenario headless from the committed instructions (not from the sim agent's shell history), confirms localization + goal SUCCESS, and checks: invariant 12 (Gazebo only), no fleet/PLC logic in sim/, layer README boundaries respected, git hygiene.
forbidden:           [editing or creating repo files, fixing defects found]
