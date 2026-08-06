# TEST SCAFFOLDING -- read-only observer for the stand-in writer's build
# verification. It is not part of the writer and never runs in a
# demonstration.
#
# WHY IT EXISTS. An API write is verified in the CONSUMER's view, never in
# the writer's own read-back (docs/LESSONS.md 2026-08-04: the m5-03 probe's
# API view read True for sixty seconds while the watch table read FALSE for
# the same sixty seconds). The stand-in writer has no read-back to consult
# by construction, so the observation is made here, by a separate process
# that reads:
#
#   SafetyInputStandIn.*      the writer's own process image -- shown for
#                             correlation only, NEVER as the verdict
#   InstF_Forklift_Safety.*   THE CONSUMER'S VIEW: the F-block's own
#                             instance data, what the safety program
#                             actually computed from the written channels
#   ForkliftSafetyMirror.*    the standard-side mirror of the F-outputs
#
# IT WRITES NOTHING. Unlike the m5-25 repeat script it is safe to run
# beside the writer: two processes WRITING one DB is the dual-writer
# failure this project already refused, but a reader is not a writer.
#
# The member list is discovered from the live tag list, so the same script
# works before and after the S015 delta adds StandInHeartbeat and the
# validity statics.

param(
  [Parameter(Mandatory = $true)][string]$Instance,
  [double]$Duration = 60,
  [double]$TickSeconds = 1.0,
  [string]$Dll = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
)

$ErrorActionPreference = 'Stop'
Add-Type -Path $Dll
$inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface($Instance)
$inst.UpdateTagList()

$have = @{}
foreach ($t in $inst.TagInfos) { $have[$t.Name] = $t.DataType.ToString() }

function Pick([string[]]$names) { return @($names | Where-Object { $have.ContainsKey($_) }) }

# Bools, in display order. Missing members are dropped, not faked.
$BOOLS = Pick @(
  'SafetyInputStandIn.EStopCircuitClosed',
  'SafetyInputStandIn.ZoneDeviceCircuitClosed',
  'SafetyInputStandIn.ResetButtonPressed',
  'InstF_Forklift_Safety.EStopCircuitClosed',
  'InstF_Forklift_Safety.ZoneDeviceCircuitClosed',
  'InstF_Forklift_Safety.ResetButtonPressed',
  'InstF_Forklift_Safety.HeartbeatChanged',
  'InstF_Forklift_Safety.HeartbeatSeen',
  'InstF_Forklift_Safety.StandInValid',
  'InstF_Forklift_Safety.StandInStaleTimer.Q',
  'InstF_Forklift_Safety.EStopClosedValid',
  'InstF_Forklift_Safety.ZoneClosedValid',
  'InstF_Forklift_Safety.ResetPressedValid',
  'InstF_Forklift_Safety.EStopDemand',
  'InstF_Forklift_Safety.ZoneStopDemand',
  'InstF_Forklift_Safety.SafetyResetRequired',
  'InstF_Forklift_Safety.SafetyResetFault',
  'ForkliftSafetyMirror.EStopDemand',
  'ForkliftSafetyMirror.ZoneStopDemand',
  'ForkliftSafetyMirror.SafetyResetRequired',
  'ForkliftSafetyMirror.SafetyResetFault',
  # SPEC 11 -- the speed monitor and the SS1 sequencer. Written by the
  # extended writer on the stand-in side, computed by the F-program on the
  # InstF side. Absent members are dropped, so this observer works before and
  # after the owner finishes the delta.
  'SafetyInputStandIn.MotionPresent',
  'SafetyInputStandIn.MotionObservationValid',
  'SafetyInputStandIn.WarningFieldClear',
  'InstF_Forklift_Safety.MotionPresent',
  'InstF_Forklift_Safety.WarningFieldClear',
  'InstF_Forklift_Safety.SpeedSeqAChanged',
  'InstF_Forklift_Safety.SpeedSeqBChanged',
  'InstF_Forklift_Safety.SpeedChainSeen',
  'InstF_Forklift_Safety.SpeedAValid',
  'InstF_Forklift_Safety.SpeedBValid',
  'InstF_Forklift_Safety.SpeedStaleNow',
  'InstF_Forklift_Safety.SpeedAStaleTimer.Q',
  'InstF_Forklift_Safety.SpeedBStaleTimer.Q',
  'InstF_Forklift_Safety.WarningFieldClearValid',
  'InstF_Forklift_Safety.SpeedDiscrepantNow',
  'InstF_Forklift_Safety.SpeedDiscrepancyTimer.Q',
  'InstF_Forklift_Safety.SpeedNearZero',
  'InstF_Forklift_Safety.MotionPresentValid',
  'InstF_Forklift_Safety.ShaftDoubtNow',
  'InstF_Forklift_Safety.ShaftDoubtTimer.Q',
  'InstF_Forklift_Safety.SpeedOverLimitNow',
  'InstF_Forklift_Safety.SpeedOverLimitTimer.Q',
  'InstF_Forklift_Safety.SpeedLimitOnsetTimer.Q',
  'InstF_Forklift_Safety.SpeedCauseGone',
  'InstF_Forklift_Safety.SpeedMonitorDemand',
  'InstF_Forklift_Safety.Ss1Demand',
  'InstF_Forklift_Safety.Ss1Timer.Q',
  'InstF_Forklift_Safety.VehicleStandstillNow',
  'InstF_Forklift_Safety.TorqueOffDemand'
)
$INTS = Pick @(
  'SafetyInputStandIn.StandInHeartbeat',
  'InstF_Forklift_Safety.HeartbeatMemory',
  # The freshness sequences, on BOTH sides. These are the columns that say
  # whether a reading is live: a sequence that stops advancing is a MISSING
  # reading, and missing is a demand. They are printed rather than
  # change-detected, because they change every cycle when they are healthy.
  'SafetyInputStandIn.SpeedSeqA',
  'SafetyInputStandIn.SpeedSeqB',
  'SafetyInputStandIn.SpeedReadingA',
  'SafetyInputStandIn.SpeedReadingB',
  'InstF_Forklift_Safety.SpeedSeqA',
  'InstF_Forklift_Safety.SpeedSeqB',
  'InstF_Forklift_Safety.SpeedReadingA',
  'InstF_Forklift_Safety.SpeedReadingB',
  'InstF_Forklift_Safety.SpeedDiff'
)

"# READ-ONLY observer. It writes nothing. The verdict is the CONSUMER's view."
"# instance: $Instance   operating state: " + $inst.OperatingState
"# columns, in order:"
$i = 0; foreach ($t in $BOOLS) { "#  [{0,2}] {1}" -f $i, $t; $i++ }
foreach ($t in $INTS) { "#   int  {0}" -f $t }
foreach ($t in @('SafetyInputStandIn.StandInHeartbeat','InstF_Forklift_Safety.StandInValid','InstF_Forklift_Safety.HeartbeatSeen')) {
  if (-not $have.ContainsKey($t)) { "# ABSENT from the live tag list: $t  (the S015 delta has not landed in this build)" }
}
""
"        t_ms  " + (($BOOLS | ForEach-Object { '.' }) -join '') + "   hb        note"

$sw = [System.Diagnostics.Stopwatch]::StartNew()
function Sample {
  $b = @()
  foreach ($t in $BOOLS) { $b += [bool]$inst.ReadBool($t) }
  $n = @{}
  foreach ($t in $INTS) { $n[$t] = $inst.ReadInt16($t) }
  return @{ bits = (($b | ForEach-Object { if ($_) { '1' } else { '0' } }) -join ''); ints = $n; t = $sw.Elapsed.TotalMilliseconds }
}
function Row($s, $note) {
  $hb = ''
  foreach ($t in $INTS) { $hb += ("{0} " -f $s.ints[$t]) }
  "{0,12:N1}  {1}   {2,-9} {3}" -f $s.t, $s.bits, $hb.Trim(), $note
}

$prev = $null
$nextTick = 0.0
$endMs = $Duration * 1000.0
while ($sw.Elapsed.TotalMilliseconds -lt $endMs) {
  $s = Sample
  if ($null -eq $prev) { Row $s 'baseline'; $prev = $s.bits }
  elseif ($s.bits -ne $prev) { Row $s 'CHANGE'; $prev = $s.bits }
  elseif ($s.t -ge $nextTick) { Row $s 'tick'; $nextTick = $s.t + ($TickSeconds * 1000.0) }
}
Row (Sample) 'final'
$inst.Dispose()
"# done"
