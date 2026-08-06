# =====================================================================
#  ENGINEERING STAND-IN WRITER  --  NOT A SAFETY DEVICE
# =====================================================================
#  This process is the simulation's stand-in for the WIRING of three
#  safety-rated devices that do not exist in this project. It carries no
#  Category, no Performance Level, no SIL, no PFH, no channel count and no
#  diagnostic coverage, and nothing here claims otherwise
#  (plc/forklift-safety/SPEC.md section 1.2 N2-N4).
#
#  Authority: plc/forklift-safety/SPEC.md section 7 says WHAT this does;
#  bridge/STANDIN-WRITER-DESIGN.md says HOW it is realised. Where the two
#  disagree, SPEC section 7 wins.
#
#  It writes exactly eleven tags of the standard DB "SafetyInputStandIn"
#  through the S7-PLCSIM Advanced API by tag name, at 50 ms, republishing
#  every LEVEL every cycle. It reads nothing from the CPU but
#  OperatingState and the tag list. It applies no process decision of any
#  kind: no threshold, no debounce of a plant signal, no latch, no
#  interlock, no verdict the PLC also computes. Its only four timers are
#  its own cycle, the staleness of its own two input links, and the
#  operator-commanded pulse width, all fixed by SPEC sections 7 and 11.2.
#
#  THE ONE PROPERTY EVERYTHING ELSE SERVES: the sources go silent rather
#  than repeat. A missing speed reading reaches the safety program as a
#  DEMAND, never as zero and never as the last value. So the two speed
#  readings are the ONE thing this writer does not republish: their
#  freshness sequences advance only in a cycle that received fresh source
#  data, and a frozen sequence is what the F-program reads as missing
#  (SPEC section 11.2). Smoothing a gap here would erase the failure the
#  whole chain exists to detect.
#
#  Usage, from Windows PowerShell 5.1 on the host running PLCSIM Advanced:
#
#    powershell -ExecutionPolicy Bypass -File bridge\standin_writer\standin_writer.ps1 -Instance <name>
#
#  -Instance is MANDATORY and is a tool-derived value: read it back from
#  the PLCSIM Advanced control panel. Never assume it.
# =====================================================================

param(
  [Parameter(Mandatory = $true)][string]$Instance,
  [string]$Dll      = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll",
  [int]$Port        = 45015,
  [int]$SpeedPort   = 45016,
  # THE OPERATOR'S SECOND KEYBOARD, AND IT IS NOTHING MORE THAN THAT
  # (m5-58). Lines appended to this file are fed to the SAME
  # Invoke-Command2 the console feeds, in the same order, with the same
  # refusals and the same log lines - the only difference is which device
  # the operator's fingers were on. It exists because an unattended
  # validation run cannot type: [Console]::KeyAvailable needs a real
  # console, and a writer started from a script has none, which would have
  # left `estop`, `zone` and `reset` undrivable for the whole of a run
  # whose whole subject is those three channels.
  #
  # It adds NO command and NO capability: there is still no way to set a
  # speed, a motion flag or the warning field, because those come from a
  # source or they are missing (see the `default` arm of Invoke-Command2).
  # Empty (the default) polls nothing and opens no file.
  [string]$CommandFile = ''
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------
# Constants. None of these is a parameter: the cycle is settled by SPEC
# section 7.1 and a knob would invite drift.
# ---------------------------------------------------------------------
$CYCLE_MS               = 50      # SPEC 7.1
$FIELD_LINK_STALE_MAX_MS= 1000    # SPEC 7.2
$MOTION_SILENCE_MAX_MS  = 250     # SPEC 11.2, writer design value: the motion
                                  # source's own five-interval window at 20 Hz
$HB_WRAP                = 30000   # wraps 30000 -> 0, inside positive Int16
$SEQ_WRAP               = 30000   # the freshness sequences wrap the same way
$INT16_MIN              = -32768
$INT16_MAX              = 32767
$RECONNECT_INTERVAL_MS  = 1000
$PULSE_MIN_MS           = 1
$PULSE_MAX_MS           = 60000
$MUTEX_NAME             = 'Global\amr-standin-writer'

# The write set, exact and closed. Every write goes through Write-Tag,
# which takes its tag name from this list and refuses anything else.
$TAG_ESTOP = 'SafetyInputStandIn.EStopCircuitClosed'
$TAG_ZONE  = 'SafetyInputStandIn.ZoneDeviceCircuitClosed'
$TAG_RESET = 'SafetyInputStandIn.ResetButtonPressed'
$TAG_HB    = 'SafetyInputStandIn.StandInHeartbeat'
# The SPEC 11.3 members. Three groups, because a half-built controller must
# not be half-written: each group is written only if EVERY member of it is in
# the CPU's tag list (Probe-Members), and a group whose members are absent is
# inert for the session and says so at start-up.
$TAG_SPD_A = 'SafetyInputStandIn.SpeedReadingA'
$TAG_SPD_B = 'SafetyInputStandIn.SpeedReadingB'
$TAG_SEQ_A = 'SafetyInputStandIn.SpeedSeqA'
$TAG_SEQ_B = 'SafetyInputStandIn.SpeedSeqB'
$TAG_MOT   = 'SafetyInputStandIn.MotionPresent'
$TAG_MOTV  = 'SafetyInputStandIn.MotionObservationValid'
$TAG_WARN  = 'SafetyInputStandIn.WarningFieldClear'

$GROUP_CORE   = @($TAG_ESTOP, $TAG_ZONE, $TAG_RESET, $TAG_HB)
$GROUP_SPEED  = @($TAG_SPD_A, $TAG_SPD_B, $TAG_SEQ_A, $TAG_SEQ_B)
$GROUP_MOTION = @($TAG_MOT, $TAG_MOTV)
$GROUP_WARN   = @($TAG_WARN)
$ALLOWLIST    = $GROUP_CORE + $GROUP_SPEED + $GROUP_MOTION + $GROUP_WARN

# Which of the eleven are written with the API's signed-16-bit call. The DB
# member's type is never changed to fit the API (design 1.1).
$INT_TAGS = @($TAG_HB, $TAG_SPD_A, $TAG_SPD_B, $TAG_SEQ_A, $TAG_SEQ_B)

# ---------------------------------------------------------------------
# 5.3  Started twice: the named mutex, before the log, before Add-Type,
#      before any API contact.
# ---------------------------------------------------------------------
$script:MutexCreated = $false
try {
  $script:Mutex = New-Object System.Threading.Mutex($true, $MUTEX_NAME, [ref]$script:MutexCreated)
} catch {
  Write-Host ("STAND-IN WRITER refused to start: could not acquire the mutex {0} ({1})" -f $MUTEX_NAME, $_.Exception.Message)
  exit 2
}
if (-not $script:MutexCreated) {
  Write-Host ("STAND-IN WRITER refused to start: the mutex {0} is already held, so a stand-in writer is already running on this host. Two writers on one DB would be a second writer of every tag and would keep the heartbeat alive across the first writer's death. Nothing was touched: no log file, no API contact." -f $MUTEX_NAME)
  exit 3
}

# ---------------------------------------------------------------------
# The session log. One file per session, unique per start, CreateNew so a
# collision is refused rather than overwritten (LESSONS 2026-07-28).
# ---------------------------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$logDir    = Join-Path $scriptDir 'logs'
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logName = "standin-writer-{0}-pid{1}.log" -f ([DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')), $PID
$logPath = Join-Path $logDir $logName
$fs  = New-Object System.IO.FileStream($logPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::Read)
$log = New-Object System.IO.StreamWriter($fs, (New-Object System.Text.UTF8Encoding($false)))
$log.AutoFlush = $true

function Format-LogLine([string]$class, [string]$detail) {
  return ("{0} | {1} | {2}" -f ([DateTime]::UtcNow.ToString('yyyy-MM-ddTHH:mm:ss.fff') + 'Z'), $class, $detail)
}
function Write-Log([string]$class, [string]$detail) {
  # Log only. CYCLE and OVERRUN lines go here and never to the console.
  $log.WriteLine((Format-LogLine $class $detail))
}
function Say([string]$class, [string]$detail) {
  # Log it AND put it on the operator's console.
  $line = Format-LogLine $class $detail
  $log.WriteLine($line)
  Write-Host $line
}

# ---------------------------------------------------------------------
# Writer state. These levels ARE the writer's state; the CPU sees them at
# the next 50 ms republish.
# ---------------------------------------------------------------------
$st = @{
  estop        = $false   # EStopCircuitClosed   -- boot FALSE = open  = demand direction
  zone         = $false   # ZoneDeviceCircuitClosed -- boot FALSE = open
  reset        = $false   # ResetButtonPressed   -- boot FALSE = unpressed
  hb           = 0        # StandInHeartbeat
  connected    = $false
  pulseEndMs   = $null    # deadline of an active reset pulse, ms on $sw
  linkUp       = $false
  linkSeenZone = $false
  linkLastMs   = 0.0
  cycles       = 0
  overruns     = 0
  writeFails   = 0

  # --- SPEC 11.2: the warning field's channel, on the SAME field link ------
  # FALSE at start and whenever the field source is silent; TRUE only on a
  # live 'WARN 1'. There is deliberately NO operator command for it: an
  # operator declaring the warning field clear would be a human vouching for
  # a field verdict, which is what the wire-NC discipline refuses.
  warn         = $false
  linkSeenWarn = $false

  # --- SPEC 11.2: the speed-source link, port 45016 ------------------------
  spdLinkUp    = $false
  # Per channel: the latest value received SINCE THE PREVIOUS CYCLE, and
  # whether one arrived at all. `fresh` is cleared at the end of every loop
  # iteration, so it can only ever mean "this cycle".
  spdAVal      = 0
  spdAFresh    = $false
  spdASeq      = 0        # the writer-owned freshness sequence, channel A
  spdASeen     = $false   # has channel A ever been written this session
  spdBVal      = 0
  spdBFresh    = $false
  spdBSeq      = 0
  spdBSeen     = $false
  spdCyclesA   = 0        # cycles in which channel A advanced
  spdCyclesB   = 0
  # The motion-present observation. Boot TRUE: every uncertainty resolves to
  # MOVING, because a false 'still' is what corroborates a lying encoder
  # (SPEC 11.3, N11).
  motPresent   = $true
  motValid     = $false
  motLastMs    = -1.0     # -1 = no MOT line has ever arrived this session
  motSilent    = $true    # currently driven TRUE by silence, not by observation
}

$inst     = $null
$listener = $null
$client   = $null
$stream   = $null
$rxBuf    = ''
$spdListener = $null
$spdClient   = $null
$spdStream   = $null
$spdRxBuf    = ''
# Which SPEC 11.3 groups this CPU actually carries. Nothing is assumed: the
# answer is read from the instance's tag list at every connect (Probe-Members).
$haveSpeed  = $false
$haveMotion = $false
$haveWarn   = $false
$lineBuf  = ''
$consoleOk= $true
$running  = $true
$exitWhy  = 'unset'
$sw       = [System.Diagnostics.Stopwatch]::StartNew()
$nextReconnectMs = 0.0

# ---------------------------------------------------------------------
# The API
# ---------------------------------------------------------------------
Add-Type -Path $Dll
$apiVer = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::Version

function Probe-Members {
  # Read which of the SPEC 11.3 members this CPU carries, from its OWN tag
  # list. Not a process decision: it is a question about the address space,
  # asked because the owner may still be building the DB. Re-asked at every
  # connect, because a download can change the answer under a running writer.
  #
  # Group gating, not per-member gating: a reading written without its
  # freshness sequence would hand the F-program a value with no way to tell
  # whether it is current, which is precisely the failure 11.2 exists to
  # prevent. All four, or none.
  $names = @{}
  try {
    foreach ($t in $script:inst.TagInfos) { $names[$t.Name] = $true }
  } catch {
    Say 'API' ("could not read the tag list ({0}); the SPEC 11.3 groups are treated as ABSENT for now and re-probed at the next connect" -f $_.Exception.Message)
    $script:haveSpeed = $false; $script:haveMotion = $false; $script:haveWarn = $false
    return
  }
  $missing = @()
  foreach ($group in @(
      @{ n = 'speed';   tags = $GROUP_SPEED  },
      @{ n = 'motion';  tags = $GROUP_MOTION },
      @{ n = 'warning'; tags = $GROUP_WARN   })) {
    $absent = @($group.tags | Where-Object { -not $names.ContainsKey($_) })
    $present = ($absent.Count -eq 0)
    switch ($group.n) {
      'speed'   { $script:haveSpeed  = $present }
      'motion'  { $script:haveMotion = $present }
      'warning' { $script:haveWarn   = $present }
    }
    if ($present) {
      Say 'MEMBERS' ("{0} group present: {1}" -f $group.n, ($group.tags -join ', '))
    } else {
      $missing += $group.n
      Say 'MEMBERS' ("{0} group ABSENT and therefore INERT this session -- not in the CPU's tag list: {1}. The writer runs without it; every member of the group is left untouched rather than written in part" -f $group.n, ($absent -join ', '))
    }
  }
  foreach ($t in $GROUP_CORE) {
    if (-not $names.ContainsKey($t)) {
      Say 'MEMBERS' ("CORE member {0} is NOT in the CPU's tag list; its write will fail every cycle and the heartbeat will not advance -- this is the delta not being in the CPU, not a writer defect" -f $t)
    }
  }
  if ($missing.Count -eq 0) {
    Say 'MEMBERS' 'all eleven members of SPEC 11.3 are present; the speed chain has a source'
  }
}

function Connect-Instance {
  # Returns $true on success. Never throws to the caller.
  try {
    $script:inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface($Instance)
    $script:inst.UpdateTagList()
    $os = $script:inst.OperatingState
    $st.connected = $true
    Say 'API' ("connected to instance '{0}', OperatingState = {1}" -f $Instance, $os)
    Probe-Members
    return $true
  } catch {
    $st.connected = $false
    if ($null -ne $script:inst) { try { $script:inst.Dispose() } catch {} ; $script:inst = $null }
    Say 'API' ("connect attempt failed: {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
    return $false
  }
}

function Disconnect-Instance([string]$why) {
  $st.connected = $false
  if ($null -ne $script:inst) { try { $script:inst.Dispose() } catch {} ; $script:inst = $null }
  Say 'API' ("session dropped ({0}); no writes are issued and the heartbeat does not advance while disconnected -- at the CPU this is writer death, which is the safe direction" -f $why)
}

function Write-Tag([string]$tag, $value) {
  # The one write helper. Its tag argument comes from $ALLOWLIST only.
  if ($ALLOWLIST -notcontains $tag) { throw "write refused: '$tag' is not in the eleven-tag allowlist" }
  if ($INT_TAGS -contains $tag) { $script:inst.WriteInt16($tag, [int16]$value) }
  else                          { $script:inst.WriteBool($tag, [bool]$value) }
}

# ---------------------------------------------------------------------
# The field link (SPEC 7.2). One TCP listener, one client at a time.
# The digit of ZONE is the CIRCUIT LEVEL: ZONE 1 = field clear = closed,
# ZONE 0 = intrusion (or the evaluation's own fault verdict) = open.
# ---------------------------------------------------------------------
function Close-Link([string]$why) {
  if ($null -ne $script:stream) { try { $script:stream.Close() } catch {} ; $script:stream = $null }
  if ($null -ne $script:client) { try { $script:client.Close() } catch {} ; $script:client = $null }
  $script:rxBuf = ''
  if ($st.linkUp) {
    $st.linkUp = $false
    $st.linkSeenZone = $false
    $st.linkSeenWarn = $false
    $st.zone = $false
    $st.warn = $false
    Say 'LINK' ("down ({0}); ZoneDeviceCircuitClosed driven FALSE (open) AND WarningFieldClear driven FALSE -- loss of the field source reads as intrusion and as warning-occupied, never as a clear field (SPEC 11.2). Ownership of the zone channel returns to the operator, who must issue a deliberate 'zone close'; the warning channel has no operator owner and stays FALSE until a live 'WARN 1'" -f $why)
  }
}

function Service-Link {
  # Accept
  try {
    while ($script:listener.Pending()) {
      $c = $script:listener.AcceptTcpClient()
      if ($null -ne $script:client) {
        try { $c.Close() } catch {}
        Say 'LINK' 'refused a second connection: one field-evaluation client at a time'
      } else {
        $script:client = $c
        $script:client.NoDelay = $true
        $script:stream = $script:client.GetStream()
        $script:rxBuf = ''
        $st.linkUp = $true
        $st.linkSeenZone = $false
        $st.linkSeenWarn = $false
        $st.zone = $false
        $st.warn = $false
        $st.linkLastMs = $sw.Elapsed.TotalMilliseconds
        Say 'LINK' ("up: field-evaluation client {0} connected; the zone channel now belongs to the field and is held FALSE until its first ZONE line -- a link with no verdict yet is not a clear field" -f $script:client.Client.RemoteEndPoint)
      }
    }
  } catch {
    Say 'LINK' ("accept error: {0}" -f $_.Exception.Message)
  }

  # Read whatever is available, without ever blocking
  if ($null -ne $script:stream) {
    try {
      $buf = New-Object byte[] 4096
      while ($script:stream.DataAvailable) {
        $n = $script:stream.Read($buf, 0, $buf.Length)
        if ($n -le 0) { Close-Link 'EOF'; break }
        $script:rxBuf += [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
      }
    } catch {
      Close-Link ("socket error: " + $_.Exception.Message)
    }
  }
  # Parse complete lines
  while ($script:rxBuf.Contains("`n")) {
    $i = $script:rxBuf.IndexOf("`n")
    $line = $script:rxBuf.Substring(0, $i).Trim()
    $script:rxBuf = $script:rxBuf.Substring($i + 1)
    if ($line -match '^(?i)ZONE\s+([01])$') {
      $lvl = ($matches[1] -eq '1')
      $st.linkLastMs = $sw.Elapsed.TotalMilliseconds
      $st.linkSeenZone = $true
      $st.zone = $lvl
      Say 'FIELD' ("ZONE {0} -> ZoneDeviceCircuitClosed := {1} ({2})" -f $matches[1], $lvl, $(if ($lvl) { 'field clear, circuit closed' } else { 'intrusion or evaluation fault, circuit open' }))
    } elseif ($line -match '^(?i)WARN\s+([01])$') {
      # SPEC 11.2: same polarity convention as ZONE. The digit is the
      # channel level: WARN 1 = warning field clear, WARN 0 = occupied.
      $lvl = ($matches[1] -eq '1')
      $st.linkLastMs = $sw.Elapsed.TotalMilliseconds
      $st.linkSeenWarn = $true
      $st.warn = $lvl
      Say 'FIELD' ("WARN {0} -> WarningFieldClear := {1} ({2})" -f $matches[1], $lvl, $(if ($lvl) { 'warning field clear' } else { 'warning field occupied -- the limit is selected' }))
    } elseif ($line -match '^(?i)PING$') {
      $st.linkLastMs = $sw.Elapsed.TotalMilliseconds
    } elseif ($line.Length -gt 0) {
      Say 'REFUSED' ("field link: malformed line '{0}' -- it refreshes nothing; bytes are not proof of a live verdict" -f $line)
    }
  }

  # The peer hung up. Tested AFTER the buffered lines are parsed, so a
  # verdict sent immediately before the close is still applied. The 1 s
  # staleness reaper below would have caught this eventually; noticing the
  # hang-up is faster, and it is why the reaper does not have to be the
  # thing that frees the client object.
  if ($null -ne $script:client -and (Test-PeerClosed $script:client)) {
    Close-Link 'the field evaluation closed the connection'
  }

  # Staleness of the writer's OWN input channel (not a plant signal)
  if ($st.linkUp) {
    if (($sw.Elapsed.TotalMilliseconds - $st.linkLastMs) -gt $FIELD_LINK_STALE_MAX_MS) {
      Close-Link ("stale: no well-formed line for {0} ms" -f $FIELD_LINK_STALE_MAX_MS)
    }
  }
}

# ---------------------------------------------------------------------
# The speed-source link (SPEC 11.2), port 45016. A second TCP listener of
# exactly the same shape as the field link's, carrying:
#
#   SPD A <int>   signed drive-wheel tread speed, mm/s, channel A
#   SPD B <int>   the same, channel B
#   MOT <p> <v>   p = 1 motion present, v = 1 observation valid
#   PING          1 Hz keepalive, for this log only
#
# The scaling round(v * 1000) is applied at the SOURCE, so the wire, this
# log and the DB member all carry the same integer and can be diffed. A
# non-finite reading is never sent, so it never arrives here: the channel
# simply goes quiet and the sequence freezes.
#
# THERE IS NO STALENESS TIMER ON THIS LINK, deliberately. It needs none for
# the DATA: every consequence of silence already runs in the demand direction
# -- the speed sequences freeze the moment a cycle passes with no line, and
# the motion channel is driven TRUE by MOTION_SILENCE_MAX. What it does need,
# and what the field link only got by accident from its 1 s staleness reaper,
# is a way to notice that the peer has HUNG UP. NetworkStream.DataAvailable
# is FALSE at end of stream, so a read loop guarded by it never runs and
# never sees the zero-length read: measured on 2026-08-06, a source that
# closed cleanly left the client object held, and the next connection was
# refused as a "second connection" for ever. Test-PeerClosed is the
# non-blocking end-of-stream test, and it is socket state, not a timer.
# ---------------------------------------------------------------------
function Test-PeerClosed($tcp) {
  # Poll(SelectRead) is TRUE when there is data to read OR the connection has
  # been closed/reset. With nothing Available, it is the second.
  if ($null -eq $tcp) { return $false }
  try {
    return ($tcp.Client.Poll(0, [System.Net.Sockets.SelectMode]::SelectRead) -and $tcp.Available -eq 0)
  } catch { return $true }
}

function Close-SpeedLink([string]$why) {
  if ($null -ne $script:spdStream) { try { $script:spdStream.Close() } catch {} ; $script:spdStream = $null }
  if ($null -ne $script:spdClient) { try { $script:spdClient.Close() } catch {} ; $script:spdClient = $null }
  $script:spdRxBuf = ''
  if ($st.spdLinkUp) {
    $st.spdLinkUp = $false
    $st.spdAFresh = $false
    $st.spdBFresh = $false
    Say 'SPEEDLINK' ("down ({0}); both freshness sequences stop advancing from this cycle on -- the F-program reads a frozen sequence as a MISSING reading, which is a demand. No zero and no last value is written in their place" -f $why)
    Set-MotionUnobservable 'the 45016 link is down'
  }
}

function Set-MotionUnobservable([string]$why) {
  # SPEC 11.2: an unobservable vehicle is MOVING, never still.
  if (-not $st.motSilent -or $st.motPresent -ne $true -or $st.motValid) {
    Say 'SPEED' ("motion observation unavailable ({0}) -> MotionPresent := TRUE, MotionObservationValid := FALSE. An unobservable vehicle is moving; a false 'still' is what would corroborate a lying encoder" -f $why)
  }
  $st.motPresent = $true
  $st.motValid   = $false
  $st.motSilent  = $true
}

function Service-SpeedLink {
  # Accept
  try {
    while ($script:spdListener.Pending()) {
      $c = $script:spdListener.AcceptTcpClient()
      if ($null -ne $script:spdClient) {
        try { $c.Close() } catch {}
        Say 'SPEEDLINK' 'refused a second connection: one speed-source client at a time'
      } else {
        $script:spdClient = $c
        $script:spdClient.NoDelay = $true
        $script:spdStream = $script:spdClient.GetStream()
        $script:spdRxBuf = ''
        $st.spdLinkUp = $true
        Say 'SPEEDLINK' ("up: speed-source client {0} connected. Until its first SPD line each sequence stays frozen, and until its first MOT line MotionPresent stays TRUE -- a link with no reading yet is not a speed" -f $script:spdClient.Client.RemoteEndPoint)
      }
    }
  } catch {
    Say 'SPEEDLINK' ("accept error: {0}" -f $_.Exception.Message)
  }

  # Read whatever is available, without ever blocking
  if ($null -ne $script:spdStream) {
    try {
      $buf = New-Object byte[] 4096
      while ($script:spdStream.DataAvailable) {
        $n = $script:spdStream.Read($buf, 0, $buf.Length)
        if ($n -le 0) { Close-SpeedLink 'EOF'; break }
        $script:spdRxBuf += [System.Text.Encoding]::ASCII.GetString($buf, 0, $n)
      }
    } catch {
      Close-SpeedLink ("socket error: " + $_.Exception.Message)
    }
  }
  # Parse complete lines. Several SPD lines for one channel may arrive inside
  # one 50 ms cycle; the LATEST wins and the sequence advances once.
  while ($script:spdRxBuf.Contains("`n")) {
    $i = $script:spdRxBuf.IndexOf("`n")
    $line = $script:spdRxBuf.Substring(0, $i).Trim()
    $script:spdRxBuf = $script:spdRxBuf.Substring($i + 1)
    if ($line.Length -eq 0) { continue }

    if ($line -match '^(?i)SPD\s+([AB])\s+(-?\d+)$') {
      $ch = $matches[1].ToUpper()
      $v  = 0
      if (-not [int]::TryParse($matches[2], [ref]$v)) {
        Say 'REFUSED' ("speed link: '{0}' does not carry an integer; nothing is written and the sequence does not advance" -f $line)
        continue
      }
      if ($v -lt $INT16_MIN -or $v -gt $INT16_MAX) {
        # Representability, NOT plausibility. The writer applies no physical
        # window to a reading -- that window is the F-program's (SPEC 11.5
        # SL6/SL7) and a second copy here would be a process decision in the
        # bridge. This refusal is only "this integer does not fit the Int the
        # DB member is", and its effect is the safe one: no write, sequence
        # frozen, the channel reads as missing.
        Say 'REFUSED' ("speed link: '{0}' is outside the Int the DB member is ({1}..{2} mm/s); nothing is written and the sequence does not advance" -f $line, $INT16_MIN, $INT16_MAX)
        continue
      }
      if ($ch -eq 'A') { $st.spdAVal = $v; $st.spdAFresh = $true }
      else             { $st.spdBVal = $v; $st.spdBFresh = $true }

    } elseif ($line -match '^(?i)MOT\s+([01])\s+([01])$') {
      $p = ($matches[1] -eq '1')
      $v = ($matches[2] -eq '1')
      $st.motLastMs = $sw.Elapsed.TotalMilliseconds
      if ($st.motSilent -or $st.motPresent -ne $p -or $st.motValid -ne $v) {
        Say 'SPEED' ("MOT {0} {1} -> MotionPresent := {2}, MotionObservationValid := {3}" -f $matches[1], $matches[2], $p, $v)
      }
      # `p` already folds the source's own fail direction: the source
      # publishes motion-present TRUE for an invalid observation. It is
      # carried UNCHANGED -- the writer neither re-derives it nor overrides
      # it, because the verdict has exactly one owner.
      $st.motPresent = $p
      $st.motValid   = $v
      $st.motSilent  = $false

    } elseif ($line -match '^(?i)PING$') {
      # Keepalive, for this log only. It refreshes no channel: a PING is not
      # a reading, and letting it hold a speed alive would be exactly the
      # repetition the whole design refuses.

    } else {
      Say 'REFUSED' ("speed link: malformed line '{0}' -- it refreshes nothing; bytes are not proof of a live reading" -f $line)
    }
  }

  # The peer hung up: DataAvailable never reports it, so the socket is asked
  # directly. Tested after the buffered lines are parsed.
  if ($null -ne $script:spdClient -and (Test-PeerClosed $script:spdClient)) {
    Close-SpeedLink 'the source closed the connection'
  }

  # The motion channel's own silence window. This times the writer's OWN
  # input channel, never the plant: it asks "has my source spoken", not
  # "is the vehicle moving". The threshold that judges a speed lives in the
  # F-program and nowhere else.
  if ($st.motLastMs -lt 0) {
    if (-not $st.motSilent) { Set-MotionUnobservable 'no MOT line has arrived yet this session' }
  } elseif ((-not $st.motSilent) -and
            (($sw.Elapsed.TotalMilliseconds - $st.motLastMs) -gt $MOTION_SILENCE_MAX_MS)) {
    Set-MotionUnobservable ("no MOT line for {0} ms" -f $MOTION_SILENCE_MAX_MS)
  }
}

# ---------------------------------------------------------------------
# The operator console (SPEC 7.2 command set). Read PER KEY and
# NON-BLOCKING, executed on Enter. [Console]::ReadLine() is never called:
# it would block the loop while the operator types, freezing the
# heartbeat and latching both demands within STANDIN_STALE_MAX.
# ---------------------------------------------------------------------
function Show-Status {
  $msg = ("levels: estop={0} zone={1} reset={2} | heartbeat={3} | field link {4} | API {5} | cycles={6} overruns={7} write-failures={8}" -f `
    $(if ($st.estop) { 'closed' } else { 'OPEN' }), `
    $(if ($st.zone)  { 'closed' } else { 'OPEN' }), `
    $(if ($st.reset) { 'PRESSED' } else { 'released' }), `
    $st.hb, `
    $(if ($st.linkUp) { 'UP (owns the zone channel)' } else { 'down (operator owns the zone channel)' }), `
    $(if ($st.connected) { 'connected' } else { 'DISCONNECTED' }), `
    $st.cycles, $st.overruns, $st.writeFails)
  Say 'OPERATOR' ("status -- " + $msg)
  $speed = ("speed link {0} | groups present: speed={1} motion={2} warning={3} | WarningFieldClear={4} | MotionPresent={5} ({6}) | A {7} seq={8} | B {9} seq={10} | advancing cycles A={11} B={12}" -f `
    $(if ($st.spdLinkUp) { 'UP' } else { 'down' }), `
    $haveSpeed, $haveMotion, $haveWarn, `
    $(if ($st.warn) { 'TRUE (clear)' } else { 'FALSE (occupied/silent -- the limit is selected)' }), `
    $st.motPresent, $(if ($st.motSilent) { 'unobservable, so MOVING' } elseif ($st.motValid) { 'observed, valid' } else { 'observed, INVALID -- the source already failed it to moving' }), `
    $(if ($st.spdASeen) { "$($st.spdAVal) mm/s" } else { 'never written' }), $st.spdASeq, `
    $(if ($st.spdBSeen) { "$($st.spdBVal) mm/s" } else { 'never written' }), $st.spdBSeq, `
    $st.spdCyclesA, $st.spdCyclesB)
  Say 'OPERATOR' ("status -- " + $speed)
}

function Invoke-Command2([string]$raw) {
  $cmd = ($raw -replace '\s+', ' ').Trim()
  if ($cmd.Length -eq 0) { return }
  switch -regex ($cmd) {
    '^(?i)estop\s+(open|close)$' {
      $v = ($matches[1].ToLower() -eq 'close')
      $st.estop = $v
      Say 'OPERATOR' ("estop {0} -> EStopCircuitClosed := {1}" -f $matches[1].ToLower(), $v)
      return
    }
    '^(?i)zone\s+(open|close)$' {
      if ($st.linkUp) {
        Say 'REFUSED' ("'{0}': the field-evaluation link is up and owns the zone channel; one channel, one source at any moment" -f $cmd)
        return
      }
      $v = ($matches[1].ToLower() -eq 'close')
      $st.zone = $v
      Say 'OPERATOR' ("zone {0} -> ZoneDeviceCircuitClosed := {1}" -f $matches[1].ToLower(), $v)
      return
    }
    '^(?i)reset\s+press$' {
      $st.reset = $true
      $st.pulseEndMs = $null
      Say 'OPERATOR' 'reset press -> ResetButtonPressed := True (held until countermanded)'
      return
    }
    '^(?i)reset\s+release$' {
      $st.reset = $false
      $st.pulseEndMs = $null
      Say 'OPERATOR' 'reset release -> ResetButtonPressed := False'
      return
    }
    '^(?i)reset\s+pulse\s+(\S+)$' {
      $arg = $matches[1]
      $ms  = 0
      if (-not [int]::TryParse($arg, [ref]$ms)) {
        Say 'REFUSED' ("'{0}': the pulse width must be an integer number of milliseconds" -f $cmd)
        return
      }
      if ($ms -lt $PULSE_MIN_MS -or $ms -gt $PULSE_MAX_MS) {
        Say 'REFUSED' ("'{0}': the pulse width must be {1}..{2} ms" -f $cmd, $PULSE_MIN_MS, $PULSE_MAX_MS)
        return
      }
      if ($st.reset) {
        Say 'REFUSED' ("'{0}': ResetButtonPressed is already held; a second actuation needs the first to end" -f $cmd)
        return
      }
      $st.reset = $true
      $st.pulseEndMs = $sw.Elapsed.TotalMilliseconds + $ms
      Say 'OPERATOR' ("reset pulse {0} -> ResetButtonPressed := True now, False after {0} ms (the F-program judges the hold)" -f $ms)
      return
    }
    '^(?i)status$' { Show-Status; return }
    '^(?i)quit$'   { $script:running = $false; $script:exitWhy = 'quit'; Say 'OPERATOR' 'quit'; return }
    default {
      Say 'REFUSED' ("'{0}': unrecognised command. Known: estop open|close, zone open|close, reset press|release, reset pulse <ms>, status, quit. There is deliberately no operator command for the speed readings, the motion observation or the warning field: those come from a source or they are missing, and a human typing one would be inventing a measurement" -f $cmd)
      return
    }
  }
}

# ---------------------------------------------------------------------
# The command file (m5-58). Polled once per cycle, non-blocking, and it
# NEVER blocks the loop: only whole lines already on disk are consumed,
# a partial trailing line is left for the next cycle, and any IO error is
# logged once and swallowed. The heartbeat outranks the operator.
# ---------------------------------------------------------------------
$script:cmdFileOffset = 0
$script:cmdFilePartial = ''
$script:cmdFileWarned = $false
function Service-CommandFile {
  if ([string]::IsNullOrEmpty($CommandFile)) { return }
  try {
    if (-not (Test-Path -LiteralPath $CommandFile)) { return }
    $fs2 = New-Object System.IO.FileStream(
      $CommandFile, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read,
      ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete))
    try {
      if ($fs2.Length -lt $script:cmdFileOffset) {
        # Truncated or replaced under us. Start again from the top rather
        # than reading a value out of the middle of a line.
        $script:cmdFileOffset = 0
        $script:cmdFilePartial = ''
      }
      if ($fs2.Length -le $script:cmdFileOffset) { return }
      $count = [int]($fs2.Length - $script:cmdFileOffset)
      $null  = $fs2.Seek($script:cmdFileOffset, [System.IO.SeekOrigin]::Begin)
      $buf   = New-Object byte[] $count
      $read  = $fs2.Read($buf, 0, $count)
      $script:cmdFileOffset += $read
      $text = [System.Text.Encoding]::UTF8.GetString($buf, 0, $read)
      $text = $script:cmdFilePartial + $text
      $parts = $text -split "`n"
      $script:cmdFilePartial = $parts[$parts.Length - 1]
      for ($i = 0; $i -lt $parts.Length - 1; $i++) {
        $line = $parts[$i].TrimEnd("`r")
        if ($line.Trim().Length -eq 0) { continue }
        Say 'OPERATOR' ("command file: {0}" -f $line)
        Invoke-Command2 $line
        if (-not $script:running) { return }
      }
    } finally { $fs2.Dispose() }
  } catch {
    if (-not $script:cmdFileWarned) {
      $script:cmdFileWarned = $true
      Say 'REFUSED' ("command file {0} unreadable ({1}); the writer keeps its cycle and its links, and the console is unaffected" -f $CommandFile, $_.Exception.Message)
    }
  }
}

function Service-Console {
  if (-not $script:consoleOk) { return }
  try {
    while ([Console]::KeyAvailable) {
      $k = [Console]::ReadKey($true)
      if ($k.Modifiers -band [ConsoleModifiers]::Control) {
        if ($k.Key -eq [ConsoleKey]::C) {
          Write-Host ''
          $script:running = $false
          $script:exitWhy = 'Ctrl+C'
          Say 'OPERATOR' 'Ctrl+C taken as quit; the terminal write is issued before the process falls silent'
          return
        }
      }
      switch ($k.Key) {
        ([ConsoleKey]::Enter) {
          Write-Host ''
          $cmd = $script:lineBuf
          $script:lineBuf = ''
          Invoke-Command2 $cmd
          if (-not $script:running) { return }
        }
        ([ConsoleKey]::Backspace) {
          if ($script:lineBuf.Length -gt 0) {
            $script:lineBuf = $script:lineBuf.Substring(0, $script:lineBuf.Length - 1)
            Write-Host "`b `b" -NoNewline
          }
        }
        default {
          if ($k.KeyChar -ne "`0" -and -not [char]::IsControl($k.KeyChar)) {
            $script:lineBuf += $k.KeyChar
            Write-Host $k.KeyChar -NoNewline
          }
        }
      }
    }
  } catch {
    # No interactive console (input redirected, or no console at all).
    # The loop must not die for it: the heartbeat is the whole point.
    $script:consoleOk = $false
    Say 'REFUSED' ("operator console unavailable ({0}); the writer keeps its cycle, its field link and its republish, but NO operator command can be entered in this session" -f $_.Exception.Message)
  }
}

# ---------------------------------------------------------------------
# The terminal write (5.4). Where a consumer holds levels, silence is not
# an absence: a state whose purpose is to stop publishing publishes its
# terminal value FIRST and only then falls silent (LESSONS 2026-08-04).
# ---------------------------------------------------------------------
$script:terminalDone = $false
function Write-Terminal {
  if ($script:terminalDone) { return }
  $script:terminalDone = $true
  $st.estop = $false; $st.zone = $false; $st.reset = $false
  $st.warn = $false; $st.motPresent = $true; $st.motValid = $false
  if (-not $st.connected) {
    Say 'TERMINAL' 'FAILED: no API session at exit, so the terminal write could not be issued. Death-by-staleness covers it: the heartbeat is already frozen and StandInValid falls within STANDIN_STALE_MAX.'
    return
  }
  try {
    Write-Tag $TAG_ESTOP $false
    Write-Tag $TAG_ZONE  $false
    Write-Tag $TAG_RESET $false
    if ($haveWarn)   { Write-Tag $TAG_WARN $false }
    if ($haveMotion) { Write-Tag $TAG_MOT $true; Write-Tag $TAG_MOTV $false }
    # The speed readings and their sequences are written by NOTHING here, on
    # purpose. A terminal zero would be a speed the writer invented, and a
    # terminal repeat would be the last value outliving its source. Leaving
    # both sequences frozen is the honest terminal statement: from this
    # instant the readings are missing, and missing is a demand.
    Say 'TERMINAL' ("levels written in the demand direction before falling silent: the three circuits FALSE (open, open, unpressed), WarningFieldClear FALSE, MotionPresent TRUE with MotionObservationValid FALSE. The two speed readings and both sequences are deliberately left UNWRITTEN and FROZEN at SpeedSeqA={0} SpeedSeqB={1} -- a terminal zero would be an invented speed. The heartbeat now freezes and the demands latch on channels already open" -f $st.spdASeq, $st.spdBSeq)
  } catch {
    Say 'TERMINAL' ("FAILED: {0}: {1}. Death-by-staleness covers it." -f $_.Exception.GetType().Name, $_.Exception.Message)
  }
}

# ---------------------------------------------------------------------
# Start
# ---------------------------------------------------------------------
try { [Console]::TreatControlCAsInput = $true } catch { $consoleOk = $false }

Write-Host ''
Write-Host '  =============================================================='
Write-Host '   ENGINEERING STAND-IN WRITER -- NOT A SAFETY DEVICE'
Write-Host '   Stand-in for the WIRING of three simulated safety-input'
Write-Host '   channels. No Category, no PL, no SIL, no PFH, no claim.'
Write-Host '  =============================================================='
Write-Host ''

Say 'START' 'ENGINEERING STAND-IN WRITER -- not a safety device, not a safety path; it stands in for the WIRING of three simulated safety-input channels and carries no Category, no PL, no SIL and no PFH'
Say 'START' ("instance = {0}" -f $Instance)
Say 'START' ("dll = {0}" -f $Dll)
Say 'START' ("api version = 0x{0:X} ({1}.{2})" -f $apiVer, ($apiVer -shr 16), ($apiVer -band 0xFFFF))
Say 'START' ("cycle = {0} ms" -f $CYCLE_MS)
Say 'START' ("field-link listener port = {0} (zone + warning), FIELD_LINK_STALE_MAX = {1} ms" -f $Port, $FIELD_LINK_STALE_MAX_MS)
Say 'START' ("speed-source listener port = {0}, MOTION_SILENCE_MAX = {1} ms" -f $SpeedPort, $MOTION_SILENCE_MAX_MS)
Say 'START' ("write set (exact and closed): {0}" -f ($ALLOWLIST -join ', '))
Say 'START' ("log = {0}" -f $logPath)
Say 'START' ("operator console = {0}" -f $(if ($consoleOk) { 'interactive' } else { 'UNAVAILABLE (no interactive console; commands cannot be entered this session)' }))
Say 'START' ("operator command file = {0}" -f $(if ([string]::IsNullOrEmpty($CommandFile)) { 'none (console only)' } else { $CommandFile + ' -- appended lines are executed as typed commands, with the same vocabulary and the same refusals' }))
Say 'START' ("boot levels: EStopCircuitClosed=False ZoneDeviceCircuitClosed=False ResetButtonPressed=False -- open, open, unpressed: the fail-safe pre-connection state")
Say 'START' ("boot levels, SPEC 11.3 members: WarningFieldClear=False (the limit is in force until a source says otherwise), MotionPresent=True MotionObservationValid=False (an unobservable vehicle is moving), both speed sequences FROZEN until a live SPD line -- the writer never invents a speed and never repeats one")

$null = Connect-Instance
$nextReconnectMs = $sw.Elapsed.TotalMilliseconds + $RECONNECT_INTERVAL_MS

try {
  $listener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $Port)
  $listener.Start()
  Say 'LINK' ("listening on 0.0.0.0:{0} for the field evaluation; none is required -- the writer serves the cell with no field link ever arriving, and while none is up the zone channel belongs to the operator" -f $Port)
} catch {
  $listener = $null
  Say 'LINK' ("could not listen on port {0}: {1}. The writer continues; the zone channel stays with the operator." -f $Port, $_.Exception.Message)
}

try {
  $spdListener = New-Object System.Net.Sockets.TcpListener([System.Net.IPAddress]::Any, $SpeedPort)
  $spdListener.Start()
  Say 'SPEEDLINK' ("listening on 0.0.0.0:{0} for the speed source; none is required -- the writer serves the cell with no speed source ever arriving, and while none is up both sequences stay frozen and the motion channel reads MOVING" -f $SpeedPort)
} catch {
  $spdListener = $null
  Say 'SPEEDLINK' ("could not listen on port {0}: {1}. The writer continues; both sequences stay frozen, which the F-program reads as missing readings." -f $SpeedPort, $_.Exception.Message)
}

Write-Host ''
Write-Host '  Commands: estop open|close  zone open|close  reset press|release'
Write-Host '            reset pulse <ms>  status  quit        (Ctrl+C = quit)'
Write-Host '  No command sets a speed, a motion flag or the warning field: those'
Write-Host '  arrive from a source on the two links, or they are missing.'
Write-Host ''

# ---------------------------------------------------------------------
# The one loop. Single threaded by construction: anything that stalls it
# stalls the heartbeat, and the F-program converts that into a latched
# demand within STANDIN_STALE_MAX. A second thread keeping the heartbeat
# alive past a wedged main loop would defeat SPEC 7.3 row 1.
# ---------------------------------------------------------------------
$t0 = $sw.Elapsed.TotalMilliseconds
$n  = 0

try {
  while ($running) {
    $n++

    # 1. console -- per key, non-blocking -- then the command file, which
    #    is the same operator through a different keyboard
    Service-Console
    if (-not $running) { break }
    Service-CommandFile
    if (-not $running) { break }

    # 2. field link (zone + warning), then the speed-source link
    if ($null -ne $listener)    { Service-Link }
    if ($null -ne $spdListener) { Service-SpeedLink }

    # 3. pulse expiry -- the one writer-generated actuation SPEC 7.2 allows
    if ($null -ne $st.pulseEndMs -and $sw.Elapsed.TotalMilliseconds -ge $st.pulseEndMs) {
      $st.pulseEndMs = $null
      $st.reset = $false
      Say 'OPERATOR' 'reset pulse elapsed -> ResetButtonPressed := False (the shaped release)'
    }

    # 4. write -- all four members, every cycle, never write-on-change
    if ($st.connected) {
      $next = $st.hb + 1
      if ($next -gt $HB_WRAP) { $next = 0 }
      try {
        Write-Tag $TAG_ESTOP $st.estop
        Write-Tag $TAG_ZONE  $st.zone
        Write-Tag $TAG_RESET $st.reset

        # The warning channel is a LEVEL and is republished every cycle,
        # exactly like the three circuits: a CPU restart reverts it and only
        # a republish repairs it.
        if ($haveWarn)   { Write-Tag $TAG_WARN $st.warn }

        # So is the motion observation. Its fail direction is TRUE, so the
        # republish repairs it toward 'moving' after a restart, which is the
        # direction that cannot manufacture a standstill.
        if ($haveMotion) {
          Write-Tag $TAG_MOT  $st.motPresent
          Write-Tag $TAG_MOTV $st.motValid
        }

        # THE TWO SPEED READINGS ARE THE EXCEPTION, AND IT IS THE POINT.
        # They are NOT republished. A channel writes its value and advances
        # its sequence only in a cycle that received fresh source data; in
        # every other cycle NEITHER is written, the sequence freezes where it
        # stands, and the F-program reads that as a missing reading -- which
        # is a demand, never a zero and never the last value. Republishing
        # here would smooth exactly the gap the chain exists to see.
        $spdALog = '-'
        $spdBLog = '-'
        if ($haveSpeed) {
          if ($st.spdAFresh) {
            $seq = $st.spdASeq + 1
            if ($seq -gt $SEQ_WRAP) { $seq = 0 }
            Write-Tag $TAG_SPD_A $st.spdAVal
            Write-Tag $TAG_SEQ_A $seq
            $st.spdASeq = $seq
            $st.spdCyclesA++
            if (-not $st.spdASeen) {
              $st.spdASeen = $true
              Say 'SPEED' ("channel A alive: first reading written, SpeedReadingA = {0} mm/s, SpeedSeqA = {1}" -f $st.spdAVal, $seq)
            }
            $spdALog = ("{0}@{1}" -f $st.spdAVal, $seq)
          }
          if ($st.spdBFresh) {
            $seq = $st.spdBSeq + 1
            if ($seq -gt $SEQ_WRAP) { $seq = 0 }
            Write-Tag $TAG_SPD_B $st.spdBVal
            Write-Tag $TAG_SEQ_B $seq
            $st.spdBSeq = $seq
            $st.spdCyclesB++
            if (-not $st.spdBSeen) {
              $st.spdBSeen = $true
              Say 'SPEED' ("channel B alive: first reading written, SpeedReadingB = {0} mm/s, SpeedSeqB = {1}" -f $st.spdBVal, $seq)
            }
            $spdBLog = ("{0}@{1}" -f $st.spdBVal, $seq)
          }
        }

        Write-Tag $TAG_HB    $next
        $st.hb = $next          # advanced ONLY on a fully successful write cycle
        $st.cycles++
        Write-Log 'CYCLE' ("hb={0} estop={1} zone={2} reset={3} warn={4} mot={5}/{6} spdA={7} spdB={8}" -f `
          $st.hb, [int]$st.estop, [int]$st.zone, [int]$st.reset, `
          $(if ($haveWarn) { [int]$st.warn } else { '-' }), `
          $(if ($haveMotion) { [int]$st.motPresent } else { '-' }), `
          $(if ($haveMotion) { [int]$st.motValid } else { '-' }), `
          $spdALog, $spdBLog)
      } catch {
        $st.writeFails++
        Say 'API' ("write failed: {0}: {1}" -f $_.Exception.GetType().Name, $_.Exception.Message)
        Disconnect-Instance 'write failure'
        $nextReconnectMs = $sw.Elapsed.TotalMilliseconds + $RECONNECT_INTERVAL_MS
      }
    } else {
      if ($sw.Elapsed.TotalMilliseconds -ge $nextReconnectMs) {
        $nextReconnectMs = $sw.Elapsed.TotalMilliseconds + $RECONNECT_INTERVAL_MS
        Say 'API' 'reconnect attempt'
        if (Connect-Instance) {
          Say 'API' 'reconnected; the next republish repairs all four members within one cycle, as a level -- it latches nothing and fires nothing'
        }
      }
    }

    # 4b. Freshness is per cycle and nothing carries it forward. Cleared
    #     unconditionally, including on a failed or disconnected cycle: a
    #     reading whose write was lost must NOT advance a sequence later, or
    #     a stale value would arrive wearing a fresh sequence.
    $st.spdAFresh = $false
    $st.spdBFresh = $false

    # 5. sleep to the deadline. Overruns are logged and counted, never
    #    compensated: no catch-up burst, no skipped-cycle logic.
    $due  = $t0 + ($n * $CYCLE_MS)
    $rem  = $due - $sw.Elapsed.TotalMilliseconds
    if ($rem -gt 0) {
      [System.Threading.Thread]::Sleep([int][math]::Ceiling($rem))
    } else {
      $st.overruns++
      Write-Log 'OVERRUN' ("cycle {0} missed its deadline by {1:N1} ms" -f $n, (-$rem))
    }
  }
} finally {
  Write-Terminal
  if ($null -ne $client)      { try { $client.Close() } catch {} }
  if ($null -ne $listener)    { try { $listener.Stop() } catch {} }
  if ($null -ne $spdClient)   { try { $spdClient.Close() } catch {} }
  if ($null -ne $spdListener) { try { $spdListener.Stop() } catch {} }
  if ($null -ne $inst)        { try { $inst.Dispose() } catch {} }
  Say 'EXIT' ("reason={0} cycles={1} overruns={2} write-failures={3} final heartbeat={4} speed cycles A={5} B={6} final sequences A={7} B={8}" -f $exitWhy, $st.cycles, $st.overruns, $st.writeFails, $st.hb, $st.spdCyclesA, $st.spdCyclesB, $st.spdASeq, $st.spdBSeq)
  try { $log.Flush(); $log.Close() } catch {}
  if ($script:MutexCreated) { try { $script:Mutex.ReleaseMutex() } catch {} ; try { $script:Mutex.Dispose() } catch {} }
}
