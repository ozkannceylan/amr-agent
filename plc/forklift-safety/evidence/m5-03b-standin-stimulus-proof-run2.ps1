# The write half of the two-witness proof. Timestamps are wall clock so they
# correlate with the OPC UA witness running in a separate process.
$ErrorActionPreference = 'Stop'
$dll = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
Add-Type -Path $dll
$inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface("FIOPROBE")
$inst.UpdateTagList()
function Now { (Get-Date).ToString("HH:mm:ss.fff") }
function Say($m) { "{0}  {1}" -f (Now), $m }
function W($t, $v) { $inst.WriteBool($t, $v); Say ("WRITE  {0,-46} := {1}" -f $t, $v) }

Say "sequence begins; CPU state as found"
Start-Sleep -Milliseconds 1500

W 'SafetyInputStandIn.EStopCircuitClosed' $true
Start-Sleep -Milliseconds 2500
W 'SafetyInputStandIn.ZoneDeviceCircuitClosed' $true
Start-Sleep -Milliseconds 2500

W 'SafetyInputStandIn.ResetButtonPressed' $true
Start-Sleep -Milliseconds 1000
W 'SafetyInputStandIn.ResetButtonPressed' $false
Say "reset released - demands should clear now"
Start-Sleep -Milliseconds 3000

W 'SafetyInputStandIn.EStopCircuitClosed' $false
Say "E-stop circuit reopened - demand should re-assert, zone demand must NOT"
Start-Sleep -Milliseconds 3000

foreach ($t in 'SafetyInputStandIn.EStopCircuitClosed','SafetyInputStandIn.ZoneDeviceCircuitClosed','SafetyInputStandIn.ResetButtonPressed') { $inst.WriteBool($t, $false) }
Say "RESTORED all three stand-in inputs to FALSE (as found)"
Start-Sleep -Milliseconds 1500
$inst.Dispose()
Say "done"
