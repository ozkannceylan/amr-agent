# TEST SCAFFOLDING -- a throwaway line feeder standing in for the field
# evaluation's TCP client (m5-12, which does not exist yet). It is not part
# of the writer and it is not the field evaluation: it proves the writer's
# listener, its ZONE encoding, its PING keepalive and its staleness
# behaviour, and it satisfies NOTHING in criterion (a)'s intrusion chain --
# a zone transition fed from here is an operator act wearing a field
# costume, and the writer log's own source class is what tells them apart.
#
#   .\field_feed.ps1 -Script '0:ZONE 1,3:ZONE 0,5:ZONE 1' -Duration 12
#
# -Script is <seconds>:<line> pairs, comma separated. PING is sent at 1 Hz
# throughout unless -NoPing is given (which is how the 1 s staleness drop
# is provoked).

param(
  [string]$ServerHost = '127.0.0.1',
  [int]$Port = 45015,
  [string]$Script = '',
  [double]$Duration = 10,
  [switch]$NoPing
)

$ErrorActionPreference = 'Stop'

$events = @()
if ($Script.Trim().Length -gt 0) {
  foreach ($item in $Script.Split(',')) {
    $p = $item.Split(':', 2)
    $events += @{ t = [double]$p[0]; line = $p[1] }
  }
}

$c = New-Object System.Net.Sockets.TcpClient
$c.Connect($ServerHost, $Port)
$s = $c.GetStream()
$enc = New-Object System.Text.ASCIIEncoding
function Send([string]$line) {
  $b = $enc.GetBytes($line + "`n")
  $s.Write($b, 0, $b.Length); $s.Flush()
  "{0,8:N2}s  ->  {1}" -f $sw.Elapsed.TotalSeconds, $line
}

$sw = [System.Diagnostics.Stopwatch]::StartNew()
"# connected to {0}:{1}" -f $ServerHost, $Port
$sent = @($false) * $events.Count
$nextPing = 0.0
while ($sw.Elapsed.TotalSeconds -lt $Duration) {
  for ($i = 0; $i -lt $events.Count; $i++) {
    if (-not $sent[$i] -and $sw.Elapsed.TotalSeconds -ge $events[$i].t) { Send $events[$i].line; $sent[$i] = $true }
  }
  if (-not $NoPing -and $sw.Elapsed.TotalSeconds -ge $nextPing) { Send 'PING'; $nextPing = $sw.Elapsed.TotalSeconds + 1.0 }
  Start-Sleep -Milliseconds 20
}
$s.Close(); $c.Close()
"# closed after {0:N2}s" -f $sw.Elapsed.TotalSeconds
