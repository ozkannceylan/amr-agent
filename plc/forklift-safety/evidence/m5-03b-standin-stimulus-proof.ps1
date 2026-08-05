# criterion (a) proof run: does an API write to the standard-DB stand-in
# reach the F-program? Verified in the CONSUMER's view (the F-block's own
# instance data and the F-output mirror), never in the writer's.
$ErrorActionPreference = 'Stop'
$dll = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
Add-Type -Path $dll
$inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface("FIOPROBE")
$inst.UpdateTagList()

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
if ($null -eq $latch) { Row 'PHASE1 consumer NEVER followed (2000 ms)' (Sample) } else { "# consumer-view latency: {0:N1} ms (F-OB is 100 ms)" -f $latch }
Row 'PHASE1 end' (Sample)

# ---- Phase 2: close the zone circuit too
$inst.WriteBool('SafetyInputStandIn.ZoneDeviceCircuitClosed', $true)
$tw = $sw.Elapsed.TotalMilliseconds
while ($sw.Elapsed.TotalMilliseconds -lt $tw + 800) { $null = Sample }
Row 'PHASE2 both circuits closed' (Sample)

# ---- Phase 3: monitored reset. Hold between RESET_HOLD_MIN (200) and MAX (3000).
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
