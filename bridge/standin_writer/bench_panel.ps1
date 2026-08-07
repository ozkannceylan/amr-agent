# =====================================================================
#  SAFETY INPUT CHANNELS -- ENGINEERING STAND-IN  |  BENCH PANEL
#  NOT A SAFETY DEVICE
# =====================================================================
#  This is a BENCH panel, not a vehicle panel. It imitates no real
#  device and claims none exists. It presents the three safety-input
#  channels the stand-in writer stands in for -- the WIRING -- so they
#  can be driven by hand instead of by typing commands into a console.
#  The vehicle e-stop is deferred to M6 and docs/safety/SRS.md B4 states
#  the cell e-stop stops no vehicle, so nothing here is labelled as the
#  vehicle's: a panel that said so would imply a function this gate does
#  not have.
#
#  It carries no Category, no Performance Level, no SIL, no PFH, no
#  channel count and no diagnostic coverage, and nothing in it claims
#  otherwise (plc/forklift-safety/SPEC.md section 1.2 N2-N4).
#
#  WHAT IT IS, MECHANICALLY. It is an INPUT DEVICE for the writer's
#  existing operator channel and a DISPLAY of the writer's existing log.
#  It is not a second writer and it is not a service:
#
#    * it writes NOTHING to the CPU. It never loads the PLCSIM Advanced
#      API, never opens an OPC UA session and holds no tag. Every action
#      it takes is one line appended to the writer's -CommandFile, which
#      the writer executes through the SAME Invoke-Command2 the console
#      feeds -- same grammar, same refusals, same log lines (m5-58);
#    * it opens NO socket, listens on NO port and offers NO service. The
#      only two things it touches are two files beside the writer on this
#      host: the command file it appends to, and the writer's session log
#      it follows;
#    * every state it shows is READ OUT OF THE WRITER'S LOG, never
#      assumed from the button that was pressed. A control that has no
#      effect therefore shows no effect.
#
#  THE THREE THINGS IT DELIBERATELY CANNOT DO.
#
#    1. It cannot drive a link-driven channel. There is no control for a
#       speed reading, for the motion observation or for the warning
#       field -- those arrive from a source on the writer's two links or
#       they are missing, and a human setting one would be inventing a
#       measurement. They appear here as DISPLAYS, by construction: the
#       panel has no code path that emits such a command, and the writer
#       would refuse it if it had.
#    2. It cannot pretend to own the zone channel. While a field link is
#       up the zone belongs to the field, so the zone control is disabled
#       and says why, rather than appearing to work and doing nothing.
#    3. It cannot make the reset a one-click action. The reset is a
#       PRESS AND HOLD on the mouse -- press on mouse-down, release on
#       mouse-up -- and the F-program judges the hold. The panel shows
#       the hold as it runs and judges nothing: it never shortens a hold,
#       never extends one, and never releases one for you.
#
#  Usage, from Windows PowerShell 5.1 on the host running PLCSIM
#  Advanced:
#
#    # start the writer and the panel together
#    powershell -ExecutionPolicy Bypass -File bridge\standin_writer\bench_panel.ps1 -Instance <name>
#
#    # or attach the panel to a writer already started with -CommandFile
#    powershell -ExecutionPolicy Bypass -File bridge\standin_writer\bench_panel.ps1 -CommandFile <path>
#
#  -Instance is a tool-derived value: read it back from the PLCSIM
#  Advanced control panel. Never assume it.
# =====================================================================

param(
  # Given: start a stand-in writer in its own console window, with a
  # fresh command file, and attach this panel to it. The writer keeps
  # its console, so the typed vocabulary stays available beside the
  # panel and the log is written by the same process as always.
  [string]$Instance = '',
  # Given instead: attach to a writer that is already running and was
  # started with -CommandFile <this same path>. If the running writer is
  # reading a DIFFERENT file, the panel says so in red and disables
  # every control, because a button that reaches nothing is worse than
  # no button.
  [string]$CommandFile = '',
  # Where the writer's session logs are. The panel follows the newest.
  [string]$LogDir = ''
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$scriptDir  = Split-Path -Parent $MyInvocation.MyCommand.Path
$writerPath = Join-Path $scriptDir 'standin_writer.ps1'
if ([string]::IsNullOrEmpty($LogDir)) { $LogDir = Join-Path $scriptDir 'logs' }

# ---------------------------------------------------------------------
# The command file. One per panel session, unique per start, exactly as
# the writer's logs are (LESSONS 2026-07-28): a shared name would let one
# session read another session's commands out of the middle of a file.
# ---------------------------------------------------------------------
$cmdDir = Join-Path $scriptDir 'commands'
if ([string]::IsNullOrEmpty($CommandFile)) {
  if ([string]::IsNullOrEmpty($Instance)) {
    Write-Host ''
    Write-Host '  BENCH PANEL: give -Instance <name> to start a writer and attach,'
    Write-Host '  or -CommandFile <path> to attach to a writer already running with one.'
    Write-Host ''
    exit 2
  }
  if (-not (Test-Path $cmdDir)) { New-Item -ItemType Directory -Path $cmdDir | Out-Null }
  $CommandFile = Join-Path $cmdDir ("bench-panel-{0}-pid{1}.cmds" -f ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')), $PID)
}
$CommandFile = [System.IO.Path]::GetFullPath($CommandFile)
if (-not (Test-Path -LiteralPath $CommandFile)) {
  # UTF-8 with NO BOM: the writer offers a BOM to its grammar and refuses
  # it loudly as an unrecognised command, which is correct behaviour and
  # a confusing first line (STANDIN-WRITER-DESIGN 4.1).
  [System.IO.File]::WriteAllText($CommandFile, '', (New-Object System.Text.UTF8Encoding($false)))
}

if (-not [string]::IsNullOrEmpty($Instance)) {
  Write-Host ("  starting the stand-in writer: instance {0}" -f $Instance)
  Write-Host ("  command file: {0}" -f $CommandFile)
  Start-Process -FilePath 'powershell.exe' -ArgumentList @(
    '-ExecutionPolicy', 'Bypass',
    '-File', $writerPath,
    '-Instance', $Instance,
    '-CommandFile', $CommandFile) | Out-Null
  Start-Sleep -Milliseconds 1500
}

# ---------------------------------------------------------------------
# Everything the panel knows. All of it is read out of the writer's log;
# none of it is inferred from a button press.
# ---------------------------------------------------------------------
$S = @{
  logPath      = $null
  logOffset    = 0
  logPartial   = ''
  writerCmdFile= $null      # the command file the running writer NAMED at start
  instance     = $null
  apiOk        = $false
  exited       = $false

  estop        = $null      # $null = not seen yet
  zone         = $null
  reset        = $null
  hb           = $null
  warn         = $null
  motPresent   = $null
  motValid     = $null
  spdAVal      = $null
  spdASeq      = $null
  spdBVal      = $null
  spdBSeq      = $null

  fieldLinkUp  = $false
  speedLinkUp  = $false
  haveSpeed    = $null
  haveMotion   = $null
  haveWarn     = $null

  lastCycleMs  = -1.0       # panel-side arrival of the last CYCLE line
  lastSeqAMs   = -1.0
  lastSeqBMs   = -1.0
  events       = New-Object System.Collections.ArrayList
}
$sw = [System.Diagnostics.Stopwatch]::StartNew()

# The reset hold. holdStartMs is set on mouse-down and cleared on
# mouse-up; nothing else ever touches it, and no code path anywhere in
# this file releases a hold on its own.
$hold = @{ startMs = -1.0; lastMs = -1.0 }

function Send-Command([string]$line) {
  # One line appended to the writer's command file. That is the whole
  # mechanism: no socket, no API, no shared memory, no second writer.
  try {
    $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($line + "`n")
    $fs = New-Object System.IO.FileStream($CommandFile,
      [System.IO.FileMode]::Append, [System.IO.FileAccess]::Write,
      ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    try { $fs.Write($bytes, 0, $bytes.Length); $fs.Flush() } finally { $fs.Dispose() }
  } catch {
    Add-Event ("PANEL | could not append '{0}' to the command file: {1}" -f $line, $_.Exception.Message)
  }
}

function Add-Event([string]$text) {
  $null = $S.events.Add($text)
  while ($S.events.Count -gt 9) { $S.events.RemoveAt(0) }
}

# ---------------------------------------------------------------------
# Following the writer's log. The panel reads; it never writes to it and
# never rewrites its content. The log stays the evidence it already is.
# ---------------------------------------------------------------------
function Select-NewestLog {
  try {
    if (-not (Test-Path -LiteralPath $LogDir)) { return $null }
    $f = Get-ChildItem -LiteralPath $LogDir -Filter 'standin-writer-*.log' -ErrorAction SilentlyContinue |
         Sort-Object LastWriteTimeUtc -Descending | Select-Object -First 1
    if ($null -eq $f) { return $null }
    return $f.FullName
  } catch { return $null }
}

function Read-Head([string]$path) {
  # The START block names the instance and the command file in force.
  # Read only the head, then follow the tail: these logs reach hundreds
  # of megabytes in a long session.
  try {
    $r = New-Object System.IO.StreamReader((New-Object System.IO.FileStream($path,
      [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read,
      ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))))
    try {
      for ($i = 0; $i -lt 80; $i++) {
        $line = $r.ReadLine()
        if ($null -eq $line) { break }
        Parse-Line $line
      }
    } finally { $r.Dispose() }
  } catch { }
}

$script:lastScanMs = -10000.0
function Attach-Log {
  # Scanned once a second, not once a tick: a directory listing at 20 Hz
  # would be twenty times the work for the same answer.
  if (($sw.Elapsed.TotalMilliseconds - $script:lastScanMs) -lt 1000 -and $null -ne $S.logPath) { return }
  $script:lastScanMs = $sw.Elapsed.TotalMilliseconds
  $p = Select-NewestLog
  if ($null -eq $p) { return }
  if ($p -eq $S.logPath) { return }
  $S.logPath       = $p
  $S.logOffset     = 0
  $S.logPartial    = ''
  $S.writerCmdFile = $null
  $S.exited        = $false
  Read-Head $p
  try { $S.logOffset = (Get-Item -LiteralPath $p).Length } catch { $S.logOffset = 0 }
  Add-Event ("PANEL | following {0}" -f (Split-Path -Leaf $p))
}

function Follow-Log {
  if ($null -eq $S.logPath) { return }
  try {
    $fs = New-Object System.IO.FileStream($S.logPath,
      [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read,
      ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    try {
      if ($fs.Length -lt $S.logOffset) { $S.logOffset = 0; $S.logPartial = '' }
      if ($fs.Length -le $S.logOffset) { return }
      $count = [int][Math]::Min([int64]262144, $fs.Length - $S.logOffset)
      $null  = $fs.Seek($S.logOffset, [System.IO.SeekOrigin]::Begin)
      $buf   = New-Object byte[] $count
      $read  = $fs.Read($buf, 0, $count)
      $S.logOffset += $read
      $text  = $S.logPartial + [System.Text.Encoding]::UTF8.GetString($buf, 0, $read)
      $parts = $text -split "`n"
      $S.logPartial = $parts[$parts.Length - 1]
      for ($i = 0; $i -lt $parts.Length - 1; $i++) { Parse-Line ($parts[$i].TrimEnd("`r")) }
    } finally { $fs.Dispose() }
  } catch { }
}

function Parse-Line([string]$line) {
  if ($line.Length -lt 30) { return }
  $bar1 = $line.IndexOf(' | ')
  if ($bar1 -lt 0) { return }
  $rest = $line.Substring($bar1 + 3)
  $bar2 = $rest.IndexOf(' | ')
  if ($bar2 -lt 0) { return }
  $class  = $rest.Substring(0, $bar2).Trim()
  $detail = $rest.Substring($bar2 + 3)

  switch ($class) {
    'CYCLE' {
      if ($detail -match 'hb=(\d+) estop=([01]) zone=([01]) reset=([01]) warn=(\S+) mot=(\S+)/(\S+) spdA=(\S+) spdB=(\S+)') {
        $S.hb    = [int]$matches[1]
        $S.estop = ($matches[2] -eq '1')
        $S.zone  = ($matches[3] -eq '1')
        $S.reset = ($matches[4] -eq '1')
        $S.warn  = $(if ($matches[5] -eq '-') { $null } else { $matches[5] -eq '1' })
        $S.motPresent = $(if ($matches[6] -eq '-') { $null } else { $matches[6] -eq '1' })
        $S.motValid   = $(if ($matches[7] -eq '-') { $null } else { $matches[7] -eq '1' })
        # Captured BEFORE the inner match, which overwrites $matches.
        $fA = $matches[8]
        $fB = $matches[9]
        if ($fA -ne '-' -and $fA -match '^(-?\d+)@(\d+)$') {
          $S.spdAVal = [int]$matches[1]; $S.spdASeq = [int]$matches[2]; $S.lastSeqAMs = $sw.Elapsed.TotalMilliseconds
        }
        if ($fB -ne '-' -and $fB -match '^(-?\d+)@(\d+)$') {
          $S.spdBVal = [int]$matches[1]; $S.spdBSeq = [int]$matches[2]; $S.lastSeqBMs = $sw.Elapsed.TotalMilliseconds
        }
        $S.lastCycleMs = $sw.Elapsed.TotalMilliseconds
        $S.exited = $false
      }
      return
    }
    'OVERRUN' { return }
    'START' {
      if ($detail -match '^instance = (.+)$')             { $S.instance = $matches[1].Trim() }
      if ($detail -match '^operator command file = (.+)$') {
        $v = $matches[1].Trim()
        if ($v -like 'none*') { $S.writerCmdFile = '' }
        else { $S.writerCmdFile = ($v -split ' -- ')[0].Trim() }
      }
      return
    }
    'API' {
      if ($detail -like 'connected to instance*') { $S.apiOk = $true }
      elseif ($detail -like 'session dropped*' -or $detail -like 'connect attempt failed*' -or $detail -like 'write failed*') { $S.apiOk = $false }
      Add-Event ("API | " + $detail)
      return
    }
    'LINK' {
      if     ($detail -like 'up:*')   { $S.fieldLinkUp = $true }
      elseif ($detail -like 'down*')  { $S.fieldLinkUp = $false }
      Add-Event ("LINK | " + $detail)
      return
    }
    'SPEEDLINK' {
      if     ($detail -like 'up:*')  { $S.speedLinkUp = $true }
      elseif ($detail -like 'down*') { $S.speedLinkUp = $false }
      Add-Event ("SPEEDLINK | " + $detail)
      return
    }
    'MEMBERS' {
      if ($detail -match '^(speed|motion|warning) group present') {
        switch ($matches[1]) { 'speed' { $S.haveSpeed = $true } 'motion' { $S.haveMotion = $true } 'warning' { $S.haveWarn = $true } }
      } elseif ($detail -match '^(speed|motion|warning) group ABSENT') {
        switch ($matches[1]) { 'speed' { $S.haveSpeed = $false } 'motion' { $S.haveMotion = $false } 'warning' { $S.haveWarn = $false } }
      }
      return
    }
    'TERMINAL' { $S.exited = $true; Add-Event ("TERMINAL | " + $detail); return }
    'EXIT'     { $S.exited = $true; Add-Event ("EXIT | " + $detail); return }
    default {
      # OPERATOR, REFUSED, FIELD, SPEED. These are the writer's own words
      # for what just happened, and the panel shows them verbatim rather
      # than paraphrasing: a change made from the panel is logged exactly
      # as the typed command would have logged it.
      Add-Event ("{0} | {1}" -f $class, $detail)
      return
    }
  }
}

# ---------------------------------------------------------------------
# The face of it
# ---------------------------------------------------------------------
$BG      = [System.Drawing.Color]::FromArgb(24,26,30)
$PANEL   = [System.Drawing.Color]::FromArgb(38,41,47)
$INK     = [System.Drawing.Color]::FromArgb(226,229,234)
$DIM     = [System.Drawing.Color]::FromArgb(150,156,166)
$GREEN   = [System.Drawing.Color]::FromArgb(58,190,110)
$RED     = [System.Drawing.Color]::FromArgb(226,74,66)
$AMBER   = [System.Drawing.Color]::FromArgb(232,170,60)
$STEEL   = [System.Drawing.Color]::FromArgb(70,120,190)

$fTitle  = New-Object System.Drawing.Font('Segoe UI', 14, [System.Drawing.FontStyle]::Bold)
$fHead   = New-Object System.Drawing.Font('Segoe UI', 10, [System.Drawing.FontStyle]::Bold)
$fBody   = New-Object System.Drawing.Font('Segoe UI', 9)
$fSmall  = New-Object System.Drawing.Font('Segoe UI', 8)
$fLamp   = New-Object System.Drawing.Font('Segoe UI', 12, [System.Drawing.FontStyle]::Bold)
$fBig    = New-Object System.Drawing.Font('Consolas', 20, [System.Drawing.FontStyle]::Bold)
$fMono   = New-Object System.Drawing.Font('Consolas', 8)

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Safety input channels -- engineering stand-in (bench panel) -- NOT A SAFETY DEVICE'
$form.Size = New-Object System.Drawing.Size(1000, 830)
$form.BackColor = $BG
$form.ForeColor = $INK
$form.Font = $fBody
$form.StartPosition = 'CenterScreen'
# Every position in this file is a literal, so let none of them be rescaled
# underneath: with AutoScaleMode Font a form whose font differs from its
# design font grows its controls and clips their text.
$form.AutoScaleMode = [System.Windows.Forms.AutoScaleMode]::None

function New-Label($text, $x, $y, $w, $h, $font, $color) {
  $l = New-Object System.Windows.Forms.Label
  $l.Text = $text; $l.Location = New-Object System.Drawing.Point($x, $y)
  $l.Size = New-Object System.Drawing.Size($w, $h)
  $l.Font = $font; $l.ForeColor = $color; $l.BackColor = [System.Drawing.Color]::Transparent
  return $l
}
function New-Box($x, $y, $w, $h) {
  $p = New-Object System.Windows.Forms.Panel
  $p.Location = New-Object System.Drawing.Point($x, $y)
  $p.Size = New-Object System.Drawing.Size($w, $h)
  $p.BackColor = $PANEL
  return $p
}

# --- title and the banner the terminal already carries ----------------
$form.Controls.Add((New-Label 'Safety input channels -- engineering stand-in' 16 10 700 26 $fTitle $INK))
$form.Controls.Add((New-Label 'Bench panel. It imitates no device and claims none exists: it presents the three safety-input channels the stand-in writer stands in for -- the wiring.' 16 38 940 16 $fSmall $DIM))

$banner = New-Object System.Windows.Forms.Panel
$banner.Location = New-Object System.Drawing.Point(16, 58)
$banner.Size = New-Object System.Drawing.Size(952, 46)
$banner.BackColor = [System.Drawing.Color]::FromArgb(120,26,22)
$banner.Controls.Add((New-Label 'NOT A SAFETY DEVICE' 12 4 400 22 $fHead ([System.Drawing.Color]::White)))
$banner.Controls.Add((New-Label 'No Category, no Performance Level, no SIL, no PFH, no channel count, no diagnostic coverage. A stand-in for the WIRING of three simulated safety-input channels.' 12 24 930 16 $fSmall ([System.Drawing.Color]::FromArgb(250,214,210))))
$form.Controls.Add($banner)

# --- attachment strip: is this panel actually in force? ---------------
$attach = New-Box 16 112 952 46
$lblAttach1 = New-Label '' 12 5 926 16 $fSmall $INK
$lblAttach2 = New-Label '' 12 23 926 16 $fSmall $DIM
$attach.Controls.Add($lblAttach1); $attach.Controls.Add($lblAttach2)
$form.Controls.Add($attach)

# =====================================================================
# LEFT COLUMN -- drivable: the operator channel, exactly what the
# writer's console already accepts
# =====================================================================
$form.Controls.Add((New-Label 'DRIVABLE -- the operator channel' 16 172 460 18 $fHead $INK))
$form.Controls.Add((New-Label 'Three circuits. A human is what stands in for the contact here.' 16 191 470 16 $fSmall $DIM))

# --- E-stop -----------------------------------------------------------
$boxE = New-Box 16 212 470 132
$boxE.Controls.Add((New-Label 'E-STOP CIRCUIT   SafetyInputStandIn.EStopCircuitClosed' 12 8 440 16 $fHead $DIM))
$lampE = New-Label '' 12 28 440 26 $fLamp $RED
$boxE.Controls.Add($lampE)
$btnE = New-Object System.Windows.Forms.Button
$btnE.Location = New-Object System.Drawing.Point(12, 58); $btnE.Size = New-Object System.Drawing.Size(300, 40)
$btnE.FlatStyle = 'Flat'; $btnE.Font = $fHead; $btnE.ForeColor = [System.Drawing.Color]::White
$boxE.Controls.Add($btnE)
$boxE.Controls.Add((New-Label 'It boots OPEN. That is fail-safe and correct, and nothing closes it until a human does -- not the HMI, not a link, not a restart.' 12 102 440 26 $fSmall $AMBER))
$form.Controls.Add($boxE)

# --- Zone -------------------------------------------------------------
$boxZ = New-Box 16 352 470 124
$boxZ.Controls.Add((New-Label 'ZONE DEVICE CIRCUIT   SafetyInputStandIn.ZoneDeviceCircuitClosed' 12 8 450 16 $fHead $DIM))
$lampZ = New-Label '' 12 28 440 26 $fLamp $RED
$boxZ.Controls.Add($lampZ)
$btnZopen  = New-Object System.Windows.Forms.Button
$btnZopen.Location = New-Object System.Drawing.Point(12, 58); $btnZopen.Size = New-Object System.Drawing.Size(140, 34)
$btnZopen.Text = 'OPEN (trip)'; $btnZopen.FlatStyle = 'Flat'; $btnZopen.Font = $fHead; $btnZopen.ForeColor = [System.Drawing.Color]::White
$btnZclose = New-Object System.Windows.Forms.Button
$btnZclose.Location = New-Object System.Drawing.Point(160, 58); $btnZclose.Size = New-Object System.Drawing.Size(140, 34)
$btnZclose.Text = 'CLOSE (clear)'; $btnZclose.FlatStyle = 'Flat'; $btnZclose.Font = $fHead; $btnZclose.ForeColor = [System.Drawing.Color]::White
$boxZ.Controls.Add($btnZopen); $boxZ.Controls.Add($btnZclose)
$lblZwho = New-Label '' 12 96 450 20 $fSmall $DIM
$boxZ.Controls.Add($lblZwho)
$form.Controls.Add($boxZ)

# --- Reset: press and hold, and the F-program judges it ---------------
$boxR = New-Box 16 484 470 200
$boxR.Controls.Add((New-Label 'MONITORED RESET   SafetyInputStandIn.ResetButtonPressed' 12 8 450 16 $fHead $DIM))
$lampR = New-Label '' 12 28 440 24 $fLamp $DIM
$boxR.Controls.Add($lampR)
$btnR = New-Object System.Windows.Forms.Button
$btnR.Location = New-Object System.Drawing.Point(12, 54); $btnR.Size = New-Object System.Drawing.Size(230, 56)
$btnR.Text = "PRESS AND HOLD"; $btnR.FlatStyle = 'Flat'; $btnR.Font = $fHead
$btnR.ForeColor = [System.Drawing.Color]::White; $btnR.TabStop = $false
$boxR.Controls.Add($btnR)
$lblHold = New-Label '' 252 54 210 30 $fBig $INK
$lblHoldSub = New-Label '' 252 86 210 24 $fSmall $DIM
$boxR.Controls.Add($lblHold); $boxR.Controls.Add($lblHoldSub)
$bar = New-Object System.Windows.Forms.Panel
$bar.Location = New-Object System.Drawing.Point(12, 118); $bar.Size = New-Object System.Drawing.Size(446, 30)
$bar.BackColor = [System.Drawing.Color]::FromArgb(28,30,35)
$boxR.Controls.Add($bar)
$boxR.Controls.Add((New-Label 'Hold the mouse down on the button; release it to make the edge. AIM FOR ABOUT 2000 ms -- clear of both ends of the window. Overrun it and the bar runs past 3000 and the hold is refused; the F-program judges, this panel only measures.' 12 152 450 44 $fSmall $DIM))
$form.Controls.Add($boxR)

# --- the two facts that cost a session --------------------------------
$boxF = New-Box 16 692 470 90
$boxF.Controls.Add((New-Label 'Two facts worth having on the panel' 12 6 440 16 $fHead $DIM))
$boxF.Controls.Add((New-Label "The HMI's RESET is the PROCESS reset (HmiResetRequest). It cannot reach an F-latch. The F-side reset is this button and nothing else (SPEC 1.3)." 12 24 446 30 $fSmall $INK))
$boxF.Controls.Add((New-Label 'A mode selection refused while a demand stands is consumed, not held: after clearing, make a fresh None -> Teleop edge at the HMI.' 12 56 446 30 $fSmall $INK))
$form.Controls.Add($boxF)

# =====================================================================
# RIGHT COLUMN -- read-only: everything that arrives from a link
# =====================================================================
$form.Controls.Add((New-Label 'READ-ONLY -- arrives from a link' 500 172 468 18 $fHead $INK))
$form.Controls.Add((New-Label 'No control here, by construction: setting one by hand would be inventing a measurement.' 500 191 470 16 $fSmall $DIM))

$boxD = New-Box 500 212 468 300
$rowY = 8
function New-Row([string]$caption) {
  $cap = New-Label $caption 12 $script:rowY 190 18 $fBody $DIM
  $val = New-Label '' 206 $script:rowY 250 18 $fBody $INK
  $boxD.Controls.Add($cap); $boxD.Controls.Add($val)
  $script:rowY += 22
  return $val
}
$vWarn   = New-Row 'Warning field'
$vMot    = New-Row 'Motion observation'
$vSpdA   = New-Row 'Speed reading A'
$vSpdB   = New-Row 'Speed reading B'
$vSeqA   = New-Row 'Freshness sequence A'
$vSeqB   = New-Row 'Freshness sequence B'
$vSpdLnk = New-Row 'Speed source link 45016'
$vFldLnk = New-Row 'Field link 45015'
$vHb     = New-Row 'Stand-in heartbeat'
$vApi    = New-Row 'PLCSIM API session'
$vGroups = New-Row 'Members on this CPU'
$boxD.Controls.Add((New-Label 'A frozen freshness sequence is how the F-program reads a MISSING speed.' 12 ($rowY + 8) 444 16 $fSmall $DIM))
$boxD.Controls.Add((New-Label 'The writer never repeats a reading and never invents a zero.' 12 ($rowY + 26) 444 16 $fSmall $DIM))
$form.Controls.Add($boxD)

# --- the writer's own words -------------------------------------------
$form.Controls.Add((New-Label "THE WRITER'S LOG -- unchanged, and still the evidence" 500 520 468 18 $fHead $INK))
$form.Controls.Add((New-Label 'An input device, not a replacement: a change made here is logged in the' 500 539 470 16 $fSmall $DIM))
$form.Controls.Add((New-Label 'same words the typed command would have produced.' 500 555 470 16 $fSmall $DIM))
$boxL = New-Box 500 574 468 208
$txtLog = New-Object System.Windows.Forms.TextBox
$txtLog.Location = New-Object System.Drawing.Point(8, 8); $txtLog.Size = New-Object System.Drawing.Size(452, 156)
$txtLog.Multiline = $true; $txtLog.ReadOnly = $true; $txtLog.BackColor = [System.Drawing.Color]::FromArgb(28,30,35)
$txtLog.ForeColor = $INK; $txtLog.Font = $fMono; $txtLog.BorderStyle = 'None'
$txtLog.ScrollBars = 'Vertical'
$boxL.Controls.Add($txtLog)
$btnQuit = New-Object System.Windows.Forms.Button
$btnQuit.Location = New-Object System.Drawing.Point(8, 172); $btnQuit.Size = New-Object System.Drawing.Size(200, 26)
$btnQuit.Text = 'quit the writer (terminal write)'; $btnQuit.FlatStyle = 'Flat'; $btnQuit.Font = $fSmall
$btnQuit.ForeColor = $INK; $btnQuit.BackColor = [System.Drawing.Color]::FromArgb(60,64,72)
$boxL.Controls.Add($btnQuit)
$lblLogName = New-Label '' 216 176 244 18 $fSmall $DIM
$boxL.Controls.Add($lblLogName)
$form.Controls.Add($boxL)

# ---------------------------------------------------------------------
# Actions. Every one of them is one line appended to the command file.
# ---------------------------------------------------------------------
$btnE.Add_Click({
  if ($S.estop -eq $true) { Send-Command 'estop open' } else { Send-Command 'estop close' }
})
$btnZopen.Add_Click({  Send-Command 'zone open'  })
$btnZclose.Add_Click({ Send-Command 'zone close' })

# The hold. Press on mouse-down, release on mouse-up, and nothing in
# between: the panel does not shape, shorten, extend or judge the hold.
$btnR.Add_MouseDown({
  if ($hold.startMs -ge 0) { return }
  $hold.startMs = $sw.Elapsed.TotalMilliseconds
  Send-Command 'reset press'
})
$btnR.Add_MouseUp({
  if ($hold.startMs -lt 0) { return }
  $hold.lastMs  = $sw.Elapsed.TotalMilliseconds - $hold.startMs
  $hold.startMs = -1.0
  Send-Command 'reset release'
})
$btnQuit.Add_Click({
  $r = [System.Windows.Forms.MessageBox]::Show(
    "Send 'quit' to the stand-in writer?" + [Environment]::NewLine + [Environment]::NewLine +
    "It writes its terminal values first -- the three circuits open, the warning field occupied, motion present -- and then falls silent. The heartbeat then freezes and both demands latch, which is the safe direction and will require a fresh monitored reset.",
    'quit the writer', 'YesNo', 'Warning')
  if ($r -eq 'Yes') { Send-Command 'quit' }
})

# ---------------------------------------------------------------------
# The reset band. A picture of the window the F-program judges against,
# with the live hold drawn on it. It is a DISPLAY: no edge of it is a
# threshold this panel applies to anything.
# ---------------------------------------------------------------------
$BAR_MAX_MS = 3600.0
$bar.Add_Paint({
  param($sender, $e)
  $g = $e.Graphics
  $w = $sender.ClientSize.Width; $h = $sender.ClientSize.Height
  $x1 = [int]($w * 200.0  / $BAR_MAX_MS)
  $x2 = [int]($w * 3000.0 / $BAR_MAX_MS)
  $brWin = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(40,70,50))
  $g.FillRectangle($brWin, $x1, 0, $x2 - $x1, $h)
  $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(90,96,106))
  $g.DrawLine($pen, $x1, 0, $x1, $h); $g.DrawLine($pen, $x2, 0, $x2, $h)
  $brTxt = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(150,156,166))
  $g.DrawString('200 ms', $fSmall, $brTxt, ([single]($x1 + 3)), ([single]1))
  $g.DrawString('3000 ms', $fSmall, $brTxt, ([single]($x2 - 52)), ([single]1))
  $g.DrawString('the window the F-program judges against', $fSmall, $brTxt, ([single]($x1 + 3)), ([single]($h - 15)))
  # The aim mark. It is a suggestion drawn on a scale, not a threshold this
  # panel applies: a hold anywhere is sent unchanged.
  $xa = [int]($w * 2000.0 / $BAR_MAX_MS)
  $penA = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(120,180,140))
  $penA.DashStyle = [System.Drawing.Drawing2D.DashStyle]::Dot
  $g.DrawLine($penA, $xa, 0, $xa, $h)
  $g.DrawString('aim 2000', $fSmall, $brTxt, ([single]($xa - 56)), ([single]1))
  $ms = 0.0
  if ($hold.startMs -ge 0) { $ms = $sw.Elapsed.TotalMilliseconds - $hold.startMs }
  elseif ($hold.lastMs -ge 0) { $ms = $hold.lastMs }
  if ($ms -gt 0) {
    $xm = [int]($w * [Math]::Min($ms, $BAR_MAX_MS) / $BAR_MAX_MS)
    $col = $(if ($hold.startMs -ge 0) { [System.Drawing.Color]::FromArgb(232,170,60) } else { [System.Drawing.Color]::FromArgb(226,229,234) })
    $brNow = New-Object System.Drawing.SolidBrush $col
    $g.FillRectangle($brNow, [Math]::Max(0, $xm - 2), 0, 4, $h)
  }
})

# ---------------------------------------------------------------------
# The tick. Reads the log, then paints what the log said. Nothing here
# writes anything anywhere.
# ---------------------------------------------------------------------
function Set-Lamp($label, $on, $textOn, $textOff, $colOn, $colOff) {
  if ($null -eq $on) { $label.Text = 'not yet reported by the writer'; $label.ForeColor = $DIM; return }
  if ($on) { $label.Text = $textOn;  $label.ForeColor = $colOn }
  else     { $label.Text = $textOff; $label.ForeColor = $colOff }
}

function Update-Ui {
  Attach-Log
  Follow-Log

  $ageMs = $(if ($S.lastCycleMs -lt 0) { -1 } else { $sw.Elapsed.TotalMilliseconds - $S.lastCycleMs })
  $writing = ($ageMs -ge 0 -and $ageMs -lt 1000 -and -not $S.exited)

  # --- is the panel in force? ---
  $inForce = $false
  $why = ''
  if ($null -eq $S.logPath) {
    $why = 'no writer log found in ' + $LogDir + ' -- no writer has run here'
  } elseif (-not $writing) {
    $why = 'the writer is not writing: no CYCLE line for ' + $(if ($ageMs -lt 0) { 'this whole panel session' } else { ('{0:N1} s' -f ($ageMs/1000)) }) + '. Its heartbeat is frozen at the CPU and both demands latch'
  } elseif ($null -eq $S.writerCmdFile -or $S.writerCmdFile -eq '') {
    $why = 'the running writer was started with NO command file, so it reads the console only. Nothing pressed here can reach it'
  } elseif ($S.writerCmdFile -ne $CommandFile) {
    $why = 'the running writer is reading a DIFFERENT command file (' + $S.writerCmdFile + '). Nothing pressed here can reach it'
  } else {
    $inForce = $true
  }

  if ($inForce) {
    $lblAttach1.Text = ("IN FORCE -- this panel's buttons reach the writer. Instance {0}. Commands go to {1}" -f $S.instance, (Split-Path -Leaf $CommandFile))
    $lblAttach1.ForeColor = $GREEN
    $lblAttach2.Text = ("Every press below is one line appended to that file and executed by the writer's own command path, logged in the same words a typed command would have produced. The panel writes nothing to the CPU, opens no socket and listens on no port.")
    $lblAttach2.ForeColor = $DIM
  } else {
    $lblAttach1.Text = 'NOT IN FORCE -- ' + $why
    $lblAttach1.ForeColor = $RED
    $lblAttach2.Text = 'The controls are disabled rather than left looking usable: a button that reaches nothing is worse than no button.'
    $lblAttach2.ForeColor = $AMBER
  }

  # --- e-stop ---
  Set-Lamp $lampE $S.estop 'CLOSED -- the circuit is made' 'OPEN -- the demand direction' $GREEN $RED
  if ($S.estop -eq $true) {
    $btnE.Text = 'PRESS -- open the circuit'; $btnE.BackColor = [System.Drawing.Color]::FromArgb(150,40,36)
  } else {
    $btnE.Text = 'TWIST TO RELEASE -- close the circuit'; $btnE.BackColor = [System.Drawing.Color]::FromArgb(44,110,70)
  }
  $btnE.Enabled = $inForce

  # --- zone: the field owns it while a link is up ---
  Set-Lamp $lampZ $S.zone 'CLOSED -- field clear' 'OPEN -- intrusion, fault, or no source' $GREEN $RED
  $zoneMine = ($inForce -and -not $S.fieldLinkUp)
  $btnZopen.Enabled  = $zoneMine
  $btnZclose.Enabled = $zoneMine
  $btnZopen.BackColor  = $(if ($zoneMine) { [System.Drawing.Color]::FromArgb(150,40,36) } else { [System.Drawing.Color]::FromArgb(58,60,66) })
  $btnZclose.BackColor = $(if ($zoneMine) { [System.Drawing.Color]::FromArgb(44,110,70) } else { [System.Drawing.Color]::FromArgb(58,60,66) })
  if ($S.fieldLinkUp) {
    $lblZwho.Text = 'NOT IN FORCE HERE: a field link is up and owns this channel.'
    $lblZwho.ForeColor = $AMBER
  } elseif ($inForce) {
    $lblZwho.Text = 'No field link is up: this channel belongs to you, at this panel.'
    $lblZwho.ForeColor = $DIM
  } else {
    $lblZwho.Text = ''
  }

  # --- reset ---
  Set-Lamp $lampR $S.reset 'PRESSED -- held at the CPU' 'released' $AMBER $DIM
  $btnR.Enabled = $inForce
  $btnR.BackColor = $(if (-not $inForce) { [System.Drawing.Color]::FromArgb(58,60,66) } elseif ($hold.startMs -ge 0) { [System.Drawing.Color]::FromArgb(150,110,30) } else { [System.Drawing.Color]::FromArgb(48,84,140) })
  if ($hold.startMs -ge 0) {
    $ms = $sw.Elapsed.TotalMilliseconds - $hold.startMs
    $lblHold.Text = ('{0:N0} ms' -f $ms); $lblHold.ForeColor = $AMBER
    $lblHoldSub.Text = 'holding -- release to make the edge'
  } elseif ($hold.lastMs -ge 0) {
    $lblHold.Text = ('{0:N0} ms' -f $hold.lastMs); $lblHold.ForeColor = $INK
    $lblHoldSub.Text = 'last hold, as this panel measured it'
  } else {
    $lblHold.Text = '--'; $lblHold.ForeColor = $DIM
    $lblHoldSub.Text = 'no hold yet this session'
  }
  $bar.Invalidate()

  # --- read-only column ---
  if ($null -eq $S.warn) { $vWarn.Text = 'not on this CPU (group absent)'; $vWarn.ForeColor = $DIM }
  elseif ($S.warn) { $vWarn.Text = 'CLEAR'; $vWarn.ForeColor = $GREEN }
  else { $vWarn.Text = 'OCCUPIED or silent -- the limit is selected'; $vWarn.ForeColor = $AMBER }

  if ($null -eq $S.motPresent) { $vMot.Text = 'not on this CPU (group absent)'; $vMot.ForeColor = $DIM }
  else {
    $vMot.Text = ("{0}, observation {1}" -f $(if ($S.motPresent) { 'MOTION PRESENT' } else { 'still' }), $(if ($S.motValid) { 'valid' } else { 'INVALID' }))
    $vMot.ForeColor = $(if ($S.motValid) { $INK } else { $AMBER })
  }

  foreach ($ch in @('A','B')) {
    $val = $(if ($ch -eq 'A') { $S.spdAVal } else { $S.spdBVal })
    $seq = $(if ($ch -eq 'A') { $S.spdASeq } else { $S.spdBSeq })
    $t   = $(if ($ch -eq 'A') { $S.lastSeqAMs } else { $S.lastSeqBMs })
    $lv  = $(if ($ch -eq 'A') { $vSpdA } else { $vSpdB })
    $ls  = $(if ($ch -eq 'A') { $vSeqA } else { $vSeqB })
    if ($null -eq $val) {
      $lv.Text = 'never written this session'; $lv.ForeColor = $DIM
      $ls.Text = 'frozen -- the F-program reads this as MISSING'; $ls.ForeColor = $AMBER
    } else {
      $lv.Text = ('{0} mm/s' -f $val); $lv.ForeColor = $INK
      $since = $sw.Elapsed.TotalMilliseconds - $t
      if ($since -lt 500) { $ls.Text = ('{0}  advancing' -f $seq); $ls.ForeColor = $GREEN }
      else { $ls.Text = ('{0}  FROZEN for {1:N1} s -- read as MISSING' -f $seq, ($since/1000)); $ls.ForeColor = $AMBER }
    }
  }

  $vSpdLnk.Text = $(if ($S.speedLinkUp) { 'up' } else { 'down -- no source' })
  $vSpdLnk.ForeColor = $(if ($S.speedLinkUp) { $GREEN } else { $DIM })
  $vFldLnk.Text = $(if ($S.fieldLinkUp) { 'up -- it owns the zone channel' } else { 'down -- the zone channel is the operator''s' })
  $vFldLnk.ForeColor = $(if ($S.fieldLinkUp) { $STEEL } else { $DIM })
  $vHb.Text = $(if ($null -eq $S.hb) { '--' } elseif ($writing) { ('{0}  advancing at 20 Hz' -f $S.hb) } else { ('{0}  FROZEN' -f $S.hb) })
  $vHb.ForeColor = $(if ($writing) { $GREEN } else { $RED })
  $vApi.Text = $(if ($S.apiOk) { 'connected' } else { 'DISCONNECTED -- no write is issued and the heartbeat does not advance' })
  $vApi.ForeColor = $(if ($S.apiOk) { $GREEN } else { $RED })
  $grp = @()
  foreach ($p in @(@('speed', $S.haveSpeed), @('motion', $S.haveMotion), @('warning', $S.haveWarn))) {
    if ($p[1] -eq $true) { $grp += $p[0] } elseif ($p[1] -eq $false) { $grp += ($p[0] + ' ABSENT') }
  }
  $vGroups.Text = $(if ($grp.Count -eq 0) { 'not yet reported' } else { ($grp -join ', ') })
  $vGroups.ForeColor = $DIM

  # A writer that is not writing is not reporting either. Everything above
  # came out of its log and is now history, so it is shown as history rather
  # than as the state of the cell: the panel must never say "the field link
  # is up" on the strength of a line written before the writer died.
  if (-not $writing) {
    foreach ($lb in @($vWarn, $vMot, $vSpdA, $vSpdB, $vSeqA, $vSeqB, $vSpdLnk, $vFldLnk, $vApi)) {
      $lb.Text = 'no report -- the writer is not writing'; $lb.ForeColor = $DIM
    }
    foreach ($lp in @($lampE, $lampZ, $lampR)) {
      if ($lp.Text -notlike '*last reported*') { $lp.Text = $lp.Text + '   (last reported)' }
      $lp.ForeColor = $DIM
    }
  }

  # --- the writer's own words ---
  $joined = ($S.events -join "`r`n")
  if ($txtLog.Text -ne $joined) {
    $txtLog.Text = $joined
    $txtLog.SelectionStart = $txtLog.TextLength
    $txtLog.ScrollToCaret()
  }
  $lblLogName.Text = $(if ($null -eq $S.logPath) { '' } else { (Split-Path -Leaf $S.logPath) })
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = 50
$timer.Add_Tick({ try { Update-Ui } catch { } })

$form.Add_Shown({ $timer.Start() })
$form.Add_FormClosing({
  $timer.Stop()
  # A hold that is still down when the window closes is RELEASED, because
  # leaving ResetButtonPressed held at the CPU with no panel to release it
  # would be this process outliving its own operator. It is the same
  # command the operator would have sent.
  if ($hold.startMs -ge 0) { Send-Command 'reset release' }
})

Write-Host ''
Write-Host '  =============================================================='
Write-Host '   SAFETY INPUT CHANNELS -- ENGINEERING STAND-IN  (bench panel)'
Write-Host '   NOT A SAFETY DEVICE. No Category, no PL, no SIL, no PFH.'
Write-Host '  =============================================================='
Write-Host ("   command file : {0}" -f $CommandFile)
Write-Host ("   log dir      : {0}" -f $LogDir)
Write-Host '   The panel writes nothing to the CPU. It appends operator'
Write-Host "   commands to the writer's command file and displays the"
Write-Host "   writer's own log. Close the window to leave."
Write-Host ''

[System.Windows.Forms.Application]::EnableVisualStyles()
[void]$form.ShowDialog()
