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
#  It writes exactly four tags of the standard DB "SafetyInputStandIn"
#  through the S7-PLCSIM Advanced API by tag name, at 50 ms, republishing
#  every level every cycle. It reads nothing from the CPU but
#  OperatingState. It applies no process decision of any kind: no
#  threshold, no debounce of a plant signal, no latch, no interlock, no
#  verdict the PLC also computes. Its only three timers are its own cycle,
#  the staleness of its own input link, and the operator-commanded pulse
#  width, all three fixed by SPEC section 7.
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
  [string]$Dll  = "C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API\7.0\Siemens.Simatic.Simulation.Runtime.Api.x64.dll",
  [int]$Port    = 45015
)

$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------
# Constants. None of these is a parameter: the cycle is settled by SPEC
# section 7.1 and a knob would invite drift.
# ---------------------------------------------------------------------
$CYCLE_MS               = 50      # SPEC 7.1
$FIELD_LINK_STALE_MAX_MS= 1000    # SPEC 7.2
$HB_WRAP                = 30000   # wraps 30000 -> 0, inside positive Int16
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
$ALLOWLIST = @($TAG_ESTOP, $TAG_ZONE, $TAG_RESET, $TAG_HB)

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
}

$inst     = $null
$listener = $null
$client   = $null
$stream   = $null
$rxBuf    = ''
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

function Connect-Instance {
  # Returns $true on success. Never throws to the caller.
  try {
    $script:inst = [Siemens.Simatic.Simulation.Runtime.SimulationRuntimeManager]::CreateInterface($Instance)
    $script:inst.UpdateTagList()
    $os = $script:inst.OperatingState
    $st.connected = $true
    Say 'API' ("connected to instance '{0}', OperatingState = {1}" -f $Instance, $os)
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
  if ($ALLOWLIST -notcontains $tag) { throw "write refused: '$tag' is not in the four-tag allowlist" }
  if ($tag -eq $TAG_HB) { $script:inst.WriteInt16($tag, [int16]$value) }
  else                  { $script:inst.WriteBool($tag, [bool]$value) }
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
    $st.zone = $false
    Say 'LINK' ("down ({0}); ZoneDeviceCircuitClosed driven FALSE (open) and ownership of the zone channel returns to the operator, who must issue a deliberate 'zone close'" -f $why)
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
        $st.zone = $false
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
    } elseif ($line -match '^(?i)PING$') {
      $st.linkLastMs = $sw.Elapsed.TotalMilliseconds
    } elseif ($line.Length -gt 0) {
      Say 'REFUSED' ("field link: malformed line '{0}' -- it refreshes nothing; bytes are not proof of a live verdict" -f $line)
    }
  }

  # Staleness of the writer's OWN input channel (not a plant signal)
  if ($st.linkUp) {
    if (($sw.Elapsed.TotalMilliseconds - $st.linkLastMs) -gt $FIELD_LINK_STALE_MAX_MS) {
      Close-Link ("stale: no well-formed line for {0} ms" -f $FIELD_LINK_STALE_MAX_MS)
    }
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
      Say 'REFUSED' ("'{0}': unrecognised command. Known: estop open|close, zone open|close, reset press|release, reset pulse <ms>, status, quit" -f $cmd)
      return
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
  if (-not $st.connected) {
    Say 'TERMINAL' 'FAILED: no API session at exit, so the terminal write could not be issued. Death-by-staleness covers it: the heartbeat is already frozen and StandInValid falls within STANDIN_STALE_MAX.'
    return
  }
  try {
    Write-Tag $TAG_ESTOP $false
    Write-Tag $TAG_ZONE  $false
    Write-Tag $TAG_RESET $false
    Say 'TERMINAL' 'all three channels written FALSE (open, unpressed, the demand direction) before falling silent; the heartbeat now freezes and both demands latch on channels already open'
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
Say 'START' ("field-link listener port = {0}, FIELD_LINK_STALE_MAX = {1} ms" -f $Port, $FIELD_LINK_STALE_MAX_MS)
Say 'START' ("write set (exact and closed): {0}" -f ($ALLOWLIST -join ', '))
Say 'START' ("log = {0}" -f $logPath)
Say 'START' ("operator console = {0}" -f $(if ($consoleOk) { 'interactive' } else { 'UNAVAILABLE (no interactive console; commands cannot be entered this session)' }))
Say 'START' ("boot levels: EStopCircuitClosed=False ZoneDeviceCircuitClosed=False ResetButtonPressed=False -- open, open, unpressed: the fail-safe pre-connection state")

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

Write-Host ''
Write-Host '  Commands: estop open|close  zone open|close  reset press|release'
Write-Host '            reset pulse <ms>  status  quit        (Ctrl+C = quit)'
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

    # 1. console -- per key, non-blocking
    Service-Console
    if (-not $running) { break }

    # 2. field link
    if ($null -ne $listener) { Service-Link }

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
        Write-Tag $TAG_HB    $next
        $st.hb = $next          # advanced ONLY on a fully successful write cycle
        $st.cycles++
        Write-Log 'CYCLE' ("hb={0} estop={1} zone={2} reset={3}" -f $st.hb, [int]$st.estop, [int]$st.zone, [int]$st.reset)
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
  if ($null -ne $client)   { try { $client.Close() } catch {} }
  if ($null -ne $listener) { try { $listener.Stop() } catch {} }
  if ($null -ne $inst)     { try { $inst.Dispose() } catch {} }
  Say 'EXIT' ("reason={0} cycles={1} overruns={2} write-failures={3} final heartbeat={4}" -f $exitWhy, $st.cycles, $st.overruns, $st.writeFails, $st.hb)
  try { $log.Flush(); $log.Close() } catch {}
  if ($script:MutexCreated) { try { $script:Mutex.ReleaseMutex() } catch {} ; try { $script:Mutex.Dispose() } catch {} }
}
