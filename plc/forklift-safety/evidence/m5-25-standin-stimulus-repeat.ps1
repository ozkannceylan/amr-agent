# m5-25 chunk H: the m5-03b criterion (a) proof run, repeated on the WORKING
# project. Same sequence as m5-03b-standin-stimulus-proof.ps1, with two
# differences and no third:
#
#   1. the PLCSIM Advanced instance name is a PARAMETER, because the working
#      project's instance name is a tool-derived value that is read back from
#      the PLCSIM Advanced control panel, never assumed from the probe run
#      (the probe ran on instance FIOPROBE, which is not this one), and
#   2. it prints the two link one-shots first, so the run records that no
#      bridge and no HMI were competing with the writes.
#
# It verifies the write in the CONSUMER's view - the F-block's own instance
# data and the standard-side mirror - never in the writer's (LESSONS
# 2026-08-04: the m5-03 probe's API view read True for 60 s while the watch
# table read FALSE for the same 60 s).
#
# It writes STANDARD DB tags only. Nothing here Modifies a fail-safe tag from
# the engineering connection: TIA refuses that outright in permanent safety
# mode (2206:000002, LESSONS 2026-08-04), which is why this path exists.
#
# Usage, from Windows PowerShell 5.1, redirecting to a UNIQUE log per run
# (LESSONS 2026-07-28: never share one evidence file across two runs):
#
#   .\m5-25-standin-stimulus-repeat.ps1 -Instance <name> `
#       | Tee-Object plc\forklift-safety\evidence\m5-25-standin-repeat-<date>.log

param(
  [Parameter(Mandatory = $true)][string]$Instance,
  [string]$Dll = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
)

$ErrorActionPreference = 'Stop'
Add-Type -Path $Dll
$inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface($Instance)
$inst.UpdateTagList()

"# instance: $Instance"
"# operating state: " + $inst.OperatingState
"# BridgeSeenAlive = " + $inst.ReadBool('ForkliftControl_DB.BridgeSeenAlive') + `
"  HmiSeenAlive = " + $inst.ReadBool('ForkliftControl_DB.HmiSeenAlive') + `
"   (both FALSE means nothing competed with these writes)"

$IN  = @('SafetyInputStandIn.EStopCircuitClosed','SafetyInputStandIn.ZoneDeviceCircuitClosed','SafetyInputStandIn.ResetButtonPressed')
$CON = @('InstF_Forklift_Safety.EStopCircuitClosed','InstF_Forklift_Safety.ZoneDeviceCircuitClosed','InstF_Forklift_Safety.ResetButtonPressed')
$OUT = @('InstF_Forklift_Safety.EStopDemand','InstF_Forklift_Safety.ZoneStopDemand','InstF_Forklift_Safety.SafetyResetRequired','InstF_Forklift_Safety.SafetyResetFault')
$MIR = @('ForkliftSafetyMirror.EStopDemand','ForkliftSafetyMirror.ZoneStopDemand','ForkliftSafetyMirror.SafetyResetRequired','ForkliftSafetyMirror.SafetyResetFault')
$ALL = $IN + $CON + $OUT + $MIR

$sw = [System.Diagnostics.Stopwatch]::StartNew()
function Sample { $r = @{}; foreach ($t in $ALL) { $r[$t] = $inst.ReadBool($t) }; $r['t_ms'] = [math]::Round($sw.Elapsed.TotalMilliseconds,1); return $r }
function Row($tag, $s) { "{0,9:N1}  {1}" -f $s['t_ms'], (($ALL | ForEach-Object { if ($s[$_]) { '1' } else { '0' } }) -join '') + "   $tag" }

"# columns, in order:"
$i = 0; foreach ($t in $ALL) { "#  [{0,2}] {1}" -f $i, $t; $i++ }
"#"
"#  IN = stand-in DB (what the API writes) | CON = F-block instance (the CONSUMER's view)"
"#  OUT = F-program outputs | MIR = standard-side mirror of those outputs"
""
"     t_ms  " + ($ALL | ForEach-Object { '.' }) -join '' + "   event"

# ---- Phase 0: baseline
Row 'PHASE0 baseline' (Sample)

# ---- Phase 1: close the E-stop circuit via the API, watch the consumer follow
$t0 = $sw.Elapsed.TotalMilliseconds
$inst.WriteBool('SafetyInputStandIn.EStopCircuitClosed', $true)
$tw = $sw.Elapsed.TotalMilliseconds
"# write EStopCircuitClosed:=TRUE returned in {0:N1} ms" -f ($tw - $t0)
$latch = $null
while ($sw.Elapsed.TotalMilliseconds -lt $tw + 2000) {
  $s = Sample
  if ($null -eq $latch -and $s['InstF_Forklift_Safety.EStopCircuitClosed']) { $latch = $s['t_ms'] - $tw; Row 'PHASE1 consumer FOLLOWED' $s }
}
if ($null -eq $latch) { Row 'PHASE1 consumer NEVER followed (2000 ms)' (Sample) } else { "# consumer-view latency: {0:N1} ms (read the F-OB period back before comparing)" -f $latch }
Row 'PHASE1 end' (Sample)

# ---- Phase 2: close the zone circuit too
$inst.WriteBool('SafetyInputStandIn.ZoneDeviceCircuitClosed', $true)
$tw = $sw.Elapsed.TotalMilliseconds
while ($sw.Elapsed.TotalMilliseconds -lt $tw + 800) { $null = Sample }
Row 'PHASE2 both circuits closed' (Sample)

# ---- Phase 3: monitored reset. Hold between the in-force RESET_HOLD_MIN and
# RESET_HOLD_MAX; read both PTs off the watch table before trusting this hold.
$inst.WriteBool('SafetyInputStandIn.ResetButtonPressed', $true)
$tp = $sw.Elapsed.TotalMilliseconds
while ($sw.Elapsed.TotalMilliseconds -lt $tp + 1000) { $null = Sample }
Row 'PHASE3 reset held 1000 ms, about to release' (Sample)
$inst.WriteBool('SafetyInputStandIn.ResetButtonPressed', $false)
$tr = $sw.Elapsed.TotalMilliseconds
$cleared = $null
while ($sw.Elapsed.TotalMilliseconds -lt $tr + 2000) {
  $s = Sample
  if ($null -eq $cleared -and -not $s['InstF_Forklift_Safety.SafetyResetRequired']) { $cleared = $s['t_ms'] - $tr; Row 'PHASE3 SafetyResetRequired CLEARED' $s }
}
if ($null -eq $cleared) { "# SafetyResetRequired did NOT clear within 2000 ms of release" } else { "# cleared {0:N1} ms after release" -f $cleared }
Row 'PHASE3 end' (Sample)

# ---- Phase 4: reopen the E-stop circuit, demand must return with no reset
$inst.WriteBool('SafetyInputStandIn.EStopCircuitClosed', $false)
$tw = $sw.Elapsed.TotalMilliseconds
$dem = $null
while ($sw.Elapsed.TotalMilliseconds -lt $tw + 2000) {
  $s = Sample
  if ($null -eq $dem -and $s['InstF_Forklift_Safety.EStopDemand']) { $dem = $s['t_ms'] - $tw; Row 'PHASE4 EStopDemand RE-ASSERTED' $s }
}
if ($null -eq $dem) { "# EStopDemand did NOT re-assert within 2000 ms" } else { "# demand re-asserted {0:N1} ms after the circuit opened" -f $dem }

# ---- restore: leave the CPU exactly as found (all three FALSE)
foreach ($t in $IN) { $inst.WriteBool($t, $false) }
$tw = $sw.Elapsed.TotalMilliseconds
while ($sw.Elapsed.TotalMilliseconds -lt $tw + 800) { $null = Sample }
Row 'RESTORED to as-found' (Sample)
$inst.Dispose()
"# done"
