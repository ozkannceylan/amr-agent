# TEST SCAFFOLDING -- a throwaway line feeder standing in for the WSL-side
# speed-source client (`agv/forklift/scripts/safe_speed_channels.py` or the
# forwarder beside it). It is not part of the writer and it is not the speed
# source: it proves the writer's 45016 listener, the SPD/MOT/PING grammar,
# the per-channel freshness sequences and -- above all -- that SILENCE ON A
# CHANNEL FREEZES ITS SEQUENCE rather than being smoothed into a zero or a
# repeat. A speed fed from here satisfies NOTHING in any acceptance test: it
# is a builder's smoke test, and the writer log's own source class is what
# tells a fed reading from a measured one.
#
#   .\speed_feed.ps1 -Duration 20 -Speed 250 -SilenceA '8-12'
#
# -Speed        mm/s sent on both channels at -Rate Hz (the source scales
#               round(v * 1000) before sending; this feeder takes mm/s).
# -SkewB        mm/s added to channel B, so a discrepancy can be fed.
# -SilenceA/B   '<from>-<to>' seconds during which that channel sends NO SPD
#               line at all. This is the property under test: a real source
#               with a stale plant read publishes nothing.
# -MotionSilence '<from>-<to>' seconds during which no MOT line is sent.
# -NoPing       suppress the 1 Hz keepalive.
# -Lines        send arbitrary extra lines: '<seconds>:<line>' pairs, comma
#               separated -- used to feed malformed lines and out-of-range
#               integers at the refusal path.

param(
  [string]$ServerHost = '127.0.0.1',
  [int]$Port = 45016,
  [double]$Duration = 20,
  [int]$Speed = 0,
  [int]$SkewB = 0,
  [double]$Rate = 20,
  [string]$SilenceA = '',
  [string]$SilenceB = '',
  [string]$MotionSilence = '',
  [int]$MotionPresent = 1,
  [int]$MotionValid = 1,
  [switch]$NoPing,
  [string]$Lines = '',
  # A mid-run step, so a cause can be introduced WITHOUT dropping the link.
  # Dropping and redialling would itself be a missing-reading demand, which
  # would mask whatever the step was meant to show.
  [double]$ChangeAt = -1,
  [int]$Speed2 = 0,
  [int]$SkewB2 = 0
)

$ErrorActionPreference = 'Stop'

function Parse-Window([string]$spec) {
  if ($spec.Trim().Length -eq 0) { return $null }
  $p = $spec.Split('-', 2)
  return @{ from = [double]$p[0]; to = [double]$p[1] }
}
function In-Window($w, [double]$t) {
  if ($null -eq $w) { return $false }
  return ($t -ge $w.from -and $t -lt $w.to)
}

$winA = Parse-Window $SilenceA
$winB = Parse-Window $SilenceB
$winM = Parse-Window $MotionSilence

$events = @()
if ($Lines.Trim().Length -gt 0) {
  foreach ($item in $Lines.Split(',')) {
    $p = $item.Split(':', 2)
    $events += @{ t = [double]$p[0]; line = $p[1] }
  }
}

$c = New-Object System.Net.Sockets.TcpClient
$c.Connect($ServerHost, $Port)
$c.NoDelay = $true
$s = $c.GetStream()
$enc = New-Object System.Text.ASCIIEncoding
$sw = [System.Diagnostics.Stopwatch]::StartNew()

function Send([string]$line) {
  $b = $enc.GetBytes($line + "`n")
  $s.Write($b, 0, $b.Length); $s.Flush()
}
function Announce([string]$what) { "{0,8:N2}s  {1}" -f $sw.Elapsed.TotalSeconds, $what }

Announce ("connected to {0}:{1}; {2} mm/s at {3} Hz, B skewed by {4}" -f $ServerHost, $Port, $Speed, $Rate, $SkewB)
if ($winA) { Announce ("channel A will be SILENT from {0}s to {1}s" -f $winA.from, $winA.to) }
if ($winB) { Announce ("channel B will be SILENT from {0}s to {1}s" -f $winB.from, $winB.to) }
if ($winM) { Announce ("MOT will be SILENT from {0}s to {1}s" -f $winM.from, $winM.to) }

$period = 1.0 / $Rate
$nextTick = 0.0
$nextPing = 0.0
$sent = @($false) * $events.Count
$wasA = $true; $wasB = $true; $wasM = $true
$stepped = $false

while ($sw.Elapsed.TotalSeconds -lt $Duration) {
  $t = $sw.Elapsed.TotalSeconds

  for ($i = 0; $i -lt $events.Count; $i++) {
    if (-not $sent[$i] -and $t -ge $events[$i].t) {
      Send $events[$i].line
      Announce ("->  {0}" -f $events[$i].line)
      $sent[$i] = $true
    }
  }

  if ($t -ge $nextTick) {
    $nextTick = $t + $period
    $quietA = In-Window $winA $t
    $quietB = In-Window $winB $t
    $quietM = In-Window $winM $t
    if ($quietA -ne (-not $wasA)) { Announce ("channel A " + $(if ($quietA) { 'GOES SILENT' } else { 'resumes' })); $wasA = -not $quietA }
    if ($quietB -ne (-not $wasB)) { Announce ("channel B " + $(if ($quietB) { 'GOES SILENT' } else { 'resumes' })); $wasB = -not $quietB }
    if ($quietM -ne (-not $wasM)) { Announce ("MOT " + $(if ($quietM) { 'GOES SILENT' } else { 'resumes' })); $wasM = -not $quietM }
    $vA = $Speed; $vSkew = $SkewB
    if ($ChangeAt -ge 0 -and $t -ge $ChangeAt) {
      if (-not $stepped) { Announce ("STEP: speed {0} -> {1} mm/s, B skew {2} -> {3}" -f $Speed, $Speed2, $SkewB, $SkewB2); $stepped = $true }
      $vA = $Speed2; $vSkew = $SkewB2
    }
    if (-not $quietA) { Send ("SPD A {0}" -f $vA) }
    if (-not $quietB) { Send ("SPD B {0}" -f ($vA + $vSkew)) }
    if (-not $quietM) { Send ("MOT {0} {1}" -f $MotionPresent, $MotionValid) }
  }

  if (-not $NoPing -and $t -ge $nextPing) { Send 'PING'; $nextPing = $t + 1.0 }
  Start-Sleep -Milliseconds 5
}

$s.Close(); $c.Close()
Announce ("closed after {0:N2}s" -f $sw.Elapsed.TotalSeconds)
