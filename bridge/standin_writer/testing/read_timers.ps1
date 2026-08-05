# TEST SCAFFOLDING -- read-only. Reads every IEC timer instance in a DB with
# ALL FOUR members together: IN, PT, ET, Q.
#
# WHY ALL FOUR. `plc/forklift/TIA-BUILD-PROCEDURE.md` records an open check:
# two `ForkliftControl_DB` timer `PT`s read `T#0MS` in force while a third read
# its specified `T#500MS`. A `PT` read alone cannot distinguish a stale build
# (LESSONS 2026-07-28) from a timer whose `IN` has never been TRUE, so `PT` is
# never read here without the `IN` beside it.
#
# TIME is a 32-bit signed millisecond count on S7; the API exposes it through
# ReadInt32 and there is no ReadTime (discovered from `$inst | Get-Member Read*`).
#
# IT WRITES NOTHING.

param(
  [Parameter(Mandatory = $true)][string]$Instance,
  [string]$Block = 'ForkliftControl_DB',
  [string]$Dll = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll"
)

$ErrorActionPreference = 'Stop'
Add-Type -Path $Dll
$inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface($Instance)
$inst.UpdateTagList()

function T([int]$ms) { if ($ms -eq 0) { 'T#0MS' } else { "T#{0}MS" -f $ms } }

"# READ-ONLY. instance=$Instance  state=$($inst.OperatingState)  db=$Block"
"# TIME read through ReadInt32 (milliseconds); there is no ReadTime on this API."
""
"{0,-34} {1,-6} {2,-12} {3,-12} {4}" -f 'timer', 'IN', 'PT in force', 'ET', 'Q'
"{0,-34} {1,-6} {2,-12} {3,-12} {4}" -f ('-' * 34), '------', '------------', '------------', '-----'

$timers = $inst.TagInfos |
  Where-Object { $_.Name -like "$Block.*.PT" } |
  ForEach-Object { $_.Name -replace '\.PT$', '' } |
  Sort-Object

foreach ($t in $timers) {
  "{0,-34} {1,-6} {2,-12} {3,-12} {4}" -f ($t -replace "^$([regex]::Escape($Block))\.", ''),
    $inst.ReadBool("$t.IN"),
    (T $inst.ReadInt32("$t.PT")),
    (T $inst.ReadInt32("$t.ET")),
    $inst.ReadBool("$t.Q")
}

$inst.Dispose()
"# done"
