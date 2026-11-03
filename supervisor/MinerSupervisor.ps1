<#
.SYNOPSIS
    Supervisor for rdavydov/Twitch-Channel-Points-Miner-v2 on Windows.

.DESCRIPTION
    Runs forever (launched by Task Scheduler at boot) and:
      - Checks GitHub for updates every -UpdateHours (default 24) and fast-forwards the checkout;
        reinstalls requirements.txt only when it changed.
      - Rolls back a bad update: if a commit that has never run 30 min cleanly crashes 3 times
        within 30 min, it resets to the last good commit and skips the bad one until upstream moves on.
      - Starts run.py through miner_wrapper.py (hidden, output captured to log files).
      - Restarts every -RestartHours (default 24) gracefully (the miner's own Ctrl+C shutdown,
        final report included), force-killing only if it takes longer than -GracefulSeconds.
      - Restarts on crash with backoff (30s doubling up to 15 min).
      - Restarts a frozen miner: if its log (DEBUG file level) stops growing for -StallMinutes.
      - Twitch login: when the saved login is rejected (ERR_BADAUTH) it moves the cookie aside and
        restarts; when the miner asks for a twitch.tv/activate code it pushes the code to your phone,
        and gets a fresh code when it expires (3 tries, then every 6 h).
      - Writes supervisor-logs\status.json every minute for MinerTask.ps1 -Action Health.
      - Sends Pushover alerts if miner-alerts.json exists next to this script.
      - Refuses to run twice (named mutex). Uses wall-clock time, so it survives sleep/hibernate.

    Compatible with Windows PowerShell 5.1 and PowerShell 7.
#>
[CmdletBinding()]
param(
    [string]$MinerDir = (Split-Path -Parent $PSScriptRoot),   # default: the repo this supervisor\ folder is in
    [string]$PythonExe = '',
    [string]$Entry = 'run.py',
    [ValidateRange(1, 500)]  [int]$RestartHours = 24,
    [ValidateRange(1, 500)]  [int]$UpdateHours = 24,
    [ValidateRange(5, 1440)] [int]$StallMinutes = 20,
    [ValidateRange(10, 600)] [int]$GracefulSeconds = 120,
    [string]$Branch = 'master'
)

$ErrorActionPreference = 'Stop'

# Finds a usable python.exe: repo venv first, then system Python. Returns the real path or $null.
function Find-Python {
    param([string]$Dir)
    foreach ($v in @('venv', '.venv', 'env')) {
        $p = Join-Path $Dir "$v\Scripts\python.exe"
        if (Test-Path -LiteralPath $p) { return $p }
    }
    $candidates = @(
        @{ Exe = 'py.exe';     Pre = @('-3') },
        @{ Exe = 'python.exe'; Pre = @() }
    )
    foreach ($c in $candidates) {
        $cmd = Get-Command $c.Exe -ErrorAction SilentlyContinue
        if (-not $cmd) { continue }
        $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
        try {
            $argList = @($c.Pre) + @('-c', 'import sys; print(sys.executable)')
            $out = & $cmd.Source @argList 2>$null
            if ($LASTEXITCODE -eq 0 -and $out) {
                $path = "$(@($out)[-1])".Trim()
                if (Test-Path -LiteralPath $path) { return $path }
            }
        } catch { } finally { $ErrorActionPreference = $old }
    }
    return $null
}

# ---------------------------------------------------------------- paths / logging
$MinerDir        = (Resolve-Path -LiteralPath $MinerDir).Path
$Python          = if ($PythonExe) { $PythonExe } else { Find-Python $MinerDir }
$EntryPath       = Join-Path $MinerDir $Entry
$ReqFile         = Join-Path $MinerDir 'requirements.txt'
$CookieDir       = Join-Path $MinerDir 'cookies'
$MinerLogDir     = Join-Path $MinerDir 'logs'
$LogDir          = Join-Path $MinerDir 'supervisor-logs'
$LogFile         = Join-Path $LogDir 'supervisor.log'
$OutLog          = Join-Path $LogDir 'miner-stdout.log'
$ErrLog          = Join-Path $LogDir 'miner-stderr.log'
$StatusFile      = Join-Path $LogDir 'status.json'
$UpdateStateFile = Join-Path $LogDir 'update-state.json'
$StopFlag        = Join-Path $LogDir 'stop.flag'
$Wrapper         = Join-Path $PSScriptRoot 'miner_wrapper.py'
$AlertConfig     = Join-Path $PSScriptRoot 'miner-alerts.json'   # {"pushoverToken":"...","pushoverUser":"...","device":""}
New-Item -ItemType Directory -Path $LogDir -Force | Out-Null

function Write-Log {
    param([string]$Msg, [string]$Level = 'INFO')
    $line = '{0} [{1}] {2}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $Level, $Msg
    Add-Content -LiteralPath $LogFile -Value $line -Encoding UTF8
    if ((Get-Item -LiteralPath $LogFile).Length -gt 5MB) {
        Move-Item -LiteralPath $LogFile -Destination "$LogFile.1" -Force
    }
}

# Runs a native exe without PowerShell 5.1 turning stderr output into terminating errors.
function Invoke-Native {
    param([string]$FilePath, [string[]]$ArgList)
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & $FilePath @ArgList 2>&1 | ForEach-Object { "$_" }
        [pscustomobject]@{ ExitCode = $LASTEXITCODE; Output = (($out -join "`n").Trim()) }
    } finally {
        $ErrorActionPreference = $old
    }
}

# ---------------------------------------------------------------- single instance
$mutex = New-Object System.Threading.Mutex($false, 'Global\TwitchMinerSupervisor')
$haveMutex = $false
try { $haveMutex = $mutex.WaitOne(0) }
catch [System.Threading.AbandonedMutexException] { $haveMutex = $true }   # previous supervisor was killed
if (-not $haveMutex) { exit 0 }   # another supervisor is already running

# ---------------------------------------------------------------- preflight
$Git = (Get-Command git.exe -ErrorAction SilentlyContinue).Source
if (-not $Git) {
    foreach ($p in @("$env:ProgramFiles\Git\cmd\git.exe", "${env:ProgramFiles(x86)}\Git\cmd\git.exe", "$env:LOCALAPPDATA\Programs\Git\cmd\git.exe")) {
        if ($p -and (Test-Path -LiteralPath $p)) { $Git = $p; break }
    }
}
if (-not $Git) { Write-Log 'git.exe not found - update checks disabled.' 'WARN' }
elseif (-not (Test-Path -LiteralPath (Join-Path $MinerDir '.git'))) {
    Write-Log 'Folder is not a git checkout (ZIP download?) - update checks disabled. Run MinerTask.ps1 -Action Install to convert it.' 'WARN'
    $Git = $null
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) { Write-Log "Python not found (tried venv\, .venv\, env\, py, python). Pass -PythonExe." 'ERROR'; exit 1 }
Write-Log "Using Python: $Python"
if (-not (Test-Path -LiteralPath $EntryPath)) { Write-Log "Entry script not found: $EntryPath" 'ERROR'; exit 1 }
$UseWrapper = Test-Path -LiteralPath $Wrapper
if (-not $UseWrapper) { Write-Log "miner_wrapper.py not found next to the supervisor - restarts will be hard kills." 'WARN' }

# Emoji/UTF-8 safe output when stdout is redirected; unbuffered so logs are live.
$env:PYTHONUTF8       = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUNBUFFERED = '1'

# ---------------------------------------------------------------- status + alerts
$script:State = [ordered]@{
    supervisorPid     = $PID
    supervisorStarted = (Get-Date).ToString('o')
    heartbeat         = $null
    pythonExe         = $Python
    minerDir          = $MinerDir
    gracefulStop      = $UseWrapper
    minerPid          = $null
    minerStarted      = $null
    minerState        = 'starting'      # running | restarting | crashed-waiting | stopped
    lastLogActivity   = $null           # last time the miner's log file grew
    logIsDebug        = $null           # DEBUG file logging -> freeze detection active
    loginNeeded       = $null           # set while waiting for a twitch.tv/activate code
    version           = $null
    goodCommit        = $null
    lastUpdateCheck   = $null
    lastUpdateResult  = $null
    lastRollback      = $null
    scheduledRestarts = 0
    stallRestarts     = 0
    lastExitCode      = $null
    lastExitTime      = $null
    crashes           = @()             # last 20: @{ time; exitCode; ranMinutes; commit }
}

function Save-Status {
    $script:State.heartbeat = (Get-Date).ToString('o')
    try {
        $tmp = "$StatusFile.tmp"
        $script:State | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $tmp -Encoding UTF8
        Move-Item -LiteralPath $tmp -Destination $StatusFile -Force
    } catch { }
}

# Pushover priority: -1 quiet (no sound), 0 normal, 1 high (bypasses quiet hours),
# 2 emergency (repeats every 5 min for up to 1 h until acknowledged).
function Send-Alert {
    param([string]$Msg, [int]$Priority = 0, [string]$Title = 'Twitch miner', [switch]$Mono, [string]$Url, [string]$UrlTitle)
    if (-not (Test-Path -LiteralPath $AlertConfig)) { return }
    try {
        $cfg = Get-Content -LiteralPath $AlertConfig -Raw | ConvertFrom-Json
        if ($cfg.appriseUrls -or $cfg.appriseUrgentUrls) {
            # Apprise (Discord, Telegram, Matrix, ntfy, Pushover, ...) via notify.py; message body on stdin.
            $ErrorActionPreference = 'Continue'
            $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
            $a = @((Join-Path $PSScriptRoot 'notify.py'), '--title', $Title, '--priority', "$Priority")
            if ($Mono) { $a += '--mono' }
            if ($Url)  { $a += @('--url', $Url); if ($UrlTitle) { $a += @('--url-title', $UrlTitle) } }
            $out = $Msg | & $Python @a 2>&1 | ForEach-Object { "$_" }
            if ($LASTEXITCODE -ne 0) { Write-Log "Apprise send failed (exit $LASTEXITCODE): $($out -join ' ')" 'WARN' }
            return
        }
        if (-not $cfg.pushoverToken -or -not $cfg.pushoverUser) { return }
        [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
        if ($Msg.Length -gt 1000) { $Msg = $Msg.Substring(0, 1000) + '...' }
        $body = @{ token = $cfg.pushoverToken; user = $cfg.pushoverUser; title = "$Title ($env:COMPUTERNAME)"; message = $Msg; priority = $Priority }
        if ($Priority -ge 2) { $body.retry = 300; $body.expire = 3600 }
        if ($cfg.device) { $body.device = $cfg.device }
        if ($Mono)       { $body.monospace = 1 }
        if ($Url)        { $body.url = $Url; if ($UrlTitle) { $body.url_title = $UrlTitle } }
        Invoke-RestMethod -Uri 'https://api.pushover.net/1/messages.json' -Method Post -Body $body -TimeoutSec 15 | Out-Null
    } catch { Write-Log "Pushover send failed: $_" 'WARN' }
}

# ---------------------------------------------------------------- git: updates, good/bad commits, rollback
$script:GoodCommit = $null
$script:BadCommits = @()
if (Test-Path -LiteralPath $UpdateStateFile) {
    try {
        $u = Get-Content -LiteralPath $UpdateStateFile -Raw | ConvertFrom-Json
        $script:GoodCommit = $u.goodCommit
        $script:BadCommits = @($u.badCommits | Where-Object { $_ })
    } catch { }
}
function Save-UpdateState {
    try { [ordered]@{ goodCommit = $script:GoodCommit; badCommits = @($script:BadCommits) } | ConvertTo-Json | Set-Content -LiteralPath $UpdateStateFile -Encoding UTF8 } catch { }
    $script:State.goodCommit = if ($script:GoodCommit) { $script:GoodCommit.Substring(0, 7) } else { $null }
}

function Get-Commit([string]$Rev = 'HEAD', [switch]$Short) {
    if (-not $Git) { return $null }
    $a = @('-C', $MinerDir, 'rev-parse')
    if ($Short) { $a += '--short' }
    $r = Invoke-Native $Git ($a + @($Rev))
    if ($r.ExitCode -eq 0) { return $r.Output } else { return $null }
}

function Set-UpdateResult([string]$Result, [string]$Level = 'INFO') {
    Write-Log $Result $Level
    $script:State.lastUpdateCheck  = (Get-Date).ToString('o')
    $script:State.lastUpdateResult = $Result
}

function Install-Requirements([string]$Why) {
    Write-Log "Running pip install -r requirements.txt ($Why)."
    $r = Invoke-Native $Python @('-m', 'pip', 'install', '--disable-pip-version-check', '-q', '-r', $ReqFile)
    if ($r.ExitCode -ne 0) { Write-Log "pip install failed: $($r.Output)" 'ERROR'; return $false }
    Write-Log 'pip install OK.'
    return $true
}

function Update-Miner {
    if (-not $Git) { Set-UpdateResult 'Update checks disabled (no git / not a git checkout).' 'WARN'; return }
    $r = Invoke-Native $Git @('-C', $MinerDir, 'fetch', '--quiet', 'origin', $Branch)
    if ($r.ExitCode -ne 0) { Set-UpdateResult "git fetch failed (offline?): $($r.Output)" 'WARN'; return }

    $oldHead = Get-Commit
    $script:State.version = Get-Commit -Short
    $behind = (Invoke-Native $Git @('-C', $MinerDir, 'rev-list', '--count', "HEAD..origin/$Branch")).Output
    if ($behind -eq '0') { Set-UpdateResult "Update check: up to date ($($script:State.version))."; return }

    $remote = Get-Commit "origin/$Branch"
    if ($script:BadCommits -contains $remote) {
        Set-UpdateResult "Update check: skipping $($remote.Substring(0, 7)) - it was rolled back after crashing. Waiting for a newer upstream commit." 'WARN'
        return
    }

    $reqBefore = if (Test-Path -LiteralPath $ReqFile) { (Get-FileHash -LiteralPath $ReqFile).Hash } else { '' }
    $r = Invoke-Native $Git @('-C', $MinerDir, 'merge', '--ff-only', "origin/$Branch")
    if ($r.ExitCode -ne 0) {
        $msg = "Update available ($behind commits) but fast-forward failed - local edits to tracked files? Staying on $($script:State.version). git: $($r.Output)"
        Set-UpdateResult $msg 'WARN'
        Send-Alert $msg -Title 'Miner update failed'
        return
    }
    $newShort = Get-Commit -Short
    $script:State.version = $newShort
    Set-UpdateResult "Updated $($oldHead.Substring(0, 7)) -> $newShort ($behind commits)."

    $reqAfter = if (Test-Path -LiteralPath $ReqFile) { (Get-FileHash -LiteralPath $ReqFile).Hash } else { '' }
    $pipNote = ''
    if ($reqAfter -and $reqAfter -ne $reqBefore -and -not (Install-Requirements 'requirements.txt changed')) {
        Set-UpdateResult "Updated to $newShort but pip install failed - check supervisor.log." 'ERROR'
        $pipNote = ' WARNING: pip install failed - check supervisor.log.'
    }
    Send-Alert "Updated $($oldHead.Substring(0, 7)) -> $newShort ($behind commits). Starting the miner on the new version. It will roll back automatically if it keeps crashing.$pipNote" -Title 'Miner updated'
}

# Called after each crash. Rolls back if the current commit has never proven itself and keeps crashing.
function Test-Rollback {
    if (-not $Git -or -not $script:GoodCommit) { return }
    $head = Get-Commit
    if (-not $head -or $head -eq $script:GoodCommit) { return }
    $bad = Get-Commit -Short
    $cutoff = (Get-Date).AddMinutes(-30)
    $fast = @($script:State.crashes | Where-Object { $_.commit -eq $bad -and ([datetime]$_.time) -gt $cutoff -and $_.ranMinutes -lt 15 })
    if ($fast.Count -lt 3) { return }

    $good = (Get-Commit $script:GoodCommit -Short)
    if (-not $good) { $good = $script:GoodCommit.Substring(0, 7) }
    Write-Log "Commit $bad crashed $($fast.Count) times in 30 min - rolling back to last good commit $good." 'WARN'
    $r = Invoke-Native $Git @('-C', $MinerDir, 'reset', '--keep', '--quiet', $script:GoodCommit)
    if ($r.ExitCode -ne 0) {
        Write-Log "Rollback failed: $($r.Output)" 'ERROR'
        Send-Alert "Commit $bad keeps crashing and the rollback to $good failed: $($r.Output)" -Title 'Miner rollback failed' -Priority 1
        return
    }
    $script:BadCommits = @(@($script:BadCommits) + $head | Select-Object -Unique | Select-Object -Last 20)
    Save-UpdateState
    $null = Install-Requirements 'rollback'
    $script:State.version = $good
    $script:State.lastRollback = "$((Get-Date).ToString('o'))|$bad -> $good"
    Set-UpdateResult "Rolled back $bad -> $good after $($fast.Count) crashes. $bad will be skipped until upstream has a newer commit." 'WARN'
    Send-Alert "Update $bad crashed $($fast.Count) times within 30 min. Rolled back to $good, which last ran cleanly. $bad will be skipped until a newer commit appears upstream." -Title 'Miner update rolled back' -Priority 1
}

# ---------------------------------------------------------------- miner process helpers
# Finds miner processes by command line (works for direct and wrapped runs) and kills each process tree.
function Stop-Miner {
    param([string]$Reason)
    $escaped = [regex]::Escape($EntryPath)
    $procs = @(Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $escaped })
    foreach ($p in $procs) {
        Write-Log "Force-stopping miner PID $($p.ProcessId) ($Reason)."
        Invoke-Native "$env:SystemRoot\System32\taskkill.exe" @('/PID', "$($p.ProcessId)", '/T', '/F') | Out-Null
    }
}

# Asks the miner to shut down like Ctrl+C (final report, clean websocket/chat exit); force-kills on timeout.
function Stop-MinerGracefully {
    param([System.Diagnostics.Process]$Proc, [string]$Reason)
    $script:State.minerState = 'restarting'
    Save-Status
    if ($UseWrapper -and -not $Proc.HasExited) {
        Write-Log "Stopping miner gracefully ($Reason)."
        Set-Content -LiteralPath $StopFlag -Value 'stop'
        if ($Proc.WaitForExit($GracefulSeconds * 1000)) {
            Write-Log "Miner shut down cleanly (exit $($Proc.ExitCode))."
        } else {
            Write-Log "Miner didn't shut down within $GracefulSeconds s - forcing." 'WARN'
        }
    }
    Stop-Miner -Reason $Reason
    Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
}

function Rotate-File([string]$Path) {
    if (Test-Path -LiteralPath $Path) { Move-Item -LiteralPath $Path -Destination "$Path.prev" -Force }
}

function Get-StderrTail([int]$Lines = 6) {
    try { ((Get-Content -LiteralPath $ErrLog -Tail $Lines -ErrorAction Stop) -join "`n").Trim() } catch { '' }
}

# Reads lines appended to miner-stdout.log since the last call (shared read; the miner keeps writing).
function Read-NewOutput {
    if (-not (Test-Path -LiteralPath $OutLog)) { return @() }
    try {
        $fs = [IO.File]::Open($OutLog, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try {
            if ($fs.Length -lt $script:OutPos) { $script:OutPos = 0; $script:OutRest = '' }
            $len = $fs.Length - $script:OutPos
            if ($len -le 0) { return @() }
            if ($len -gt 4MB) { $script:OutPos = $fs.Length - 4MB; $len = 4MB; $script:OutRest = '' }
            $null = $fs.Seek($script:OutPos, [IO.SeekOrigin]::Begin)
            $buf = New-Object byte[] ([int]$len)
            $read = $fs.Read($buf, 0, [int]$len)
            $script:OutPos += $read
        } finally { $fs.Dispose() }
        $text  = $script:OutRest + [Text.Encoding]::UTF8.GetString($buf, 0, $read)
        $lines = $text -split "`r?`n"
        $script:OutRest = $lines[-1]
        if ($lines.Count -le 1) { return @() }
        return $lines[0..($lines.Count - 2)]
    } catch { return @() }
}

# Size of the miner's current log file, read through a handle (directory timestamps lag for open files).
function Get-MinerLogSize {
    $log = Get-ChildItem -LiteralPath $MinerLogDir -File -Filter '*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if (-not $log) { return $null }
    try {
        $fs = [IO.File]::Open($log.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
        try { return [pscustomobject]@{ Path = $log.FullName; Length = $fs.Length } } finally { $fs.Dispose() }
    } catch { return $null }
}

# Returns a reason string if the miner looks frozen, else $null. Only active with DEBUG file logging.
function Test-Stalled([datetime]$Started) {
    $s = Get-MinerLogSize
    if (-not $s) { return $null }
    if ($s.Path -ne $script:LogPath -or $s.Length -ne $script:LogLen) {
        $script:LogPath = $s.Path; $script:LogLen = $s.Length; $script:LogGrewAt = Get-Date
        $script:State.lastLogActivity = $script:LogGrewAt.ToString('o')
    }
    if (((Get-Date) - $Started).TotalMinutes -lt 15) { return $null }   # startup grace
    if ($null -eq $script:LogIsDebug) {
        $tail = @(Get-Content -LiteralPath $s.Path -Tail 400 -ErrorAction SilentlyContinue)
        $script:LogIsDebug = [bool](@($tail | Where-Object { $_ -match ' - DEBUG - ' }).Count)
        $script:State.logIsDebug = $script:LogIsDebug
        if (-not $script:LogIsDebug) { Write-Log 'Miner file log is not at DEBUG level - freeze detection is off (health check still warns).' }
    }
    if (-not $script:LogIsDebug) { return $null }
    $quiet = ((Get-Date) - $script:LogGrewAt).TotalMinutes
    if ($quiet -ge $StallMinutes) { return "its log hasn't grown for $([int]$quiet) min" }
    return $null
}

function Get-CookieFiles { @(Get-ChildItem -LiteralPath $CookieDir -Filter '*.pkl' -File -ErrorAction SilentlyContinue) }

# ---------------------------------------------------------------- login handling
$script:CodesSent        = 0
$script:LoginPausedUntil = $null

function Watch-MinerOutput {
    foreach ($line in (Read-NewOutput)) {
        if ($line -match 'enter this code:\s*([A-Za-z0-9-]+)') {
            $script:Login = @{ Code = $Matches[1]; Issued = Get-Date; Expires = (Get-Date).AddMinutes(30); Pushed = $false }
        } elseif ($line -match 'expire in (\d+) minutes' -and $script:Login) {
            $script:Login.Expires = $script:Login.Issued.AddMinutes([int]$Matches[1])
        } elseif ($line -match 'ERR_BADAUTH') {
            $script:BadAuthCount++
        }
    }
    if ($script:Login -and -not $script:Login.Pushed) {
        $script:Login.Pushed = $true
        $script:CodesSent++
        $until = $script:Login.Expires.ToString('HH:mm')
        $script:State.loginNeeded = "Waiting for twitch.tv/activate code $($script:Login.Code) (valid until $until)"
        Save-Status
        Write-Log "Twitch login needed - activation code $($script:Login.Code), valid until $until."
        Send-Alert "Twitch needs you to log in again. Open twitch.tv/activate and enter:`n`n$($script:Login.Code)`n`nValid until $until. The miner continues on its own once you've entered it." `
            -Title 'Twitch login needed' -Priority 1 -Url 'https://www.twitch.tv/activate' -UrlTitle 'Open twitch.tv/activate'
    }
}

# Returns a restart reason when the login situation needs a restart, else $null.
function Test-Login {
    # Saved login rejected by Twitch: move the cookie aside so the miner asks for a new login.
    if (-not $script:Login -and $script:BadAuthCount -ge 3) {
        $cookies = Get-CookieFiles
        if ($cookies.Count) {
            $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
            foreach ($c in $cookies) { Rename-Item -LiteralPath $c.FullName -NewName "$($c.Name).expired-$stamp" }
            Write-Log "Twitch rejected the saved login (ERR_BADAUTH x$($script:BadAuthCount)). Moved $($cookies.Count) cookie file(s) aside." 'WARN'
            Send-Alert 'Twitch rejected the saved login (the cookie expired). Restarting the miner - you will get a login code next.' -Title 'Twitch login expired' -Priority 0
            return 'saved Twitch login expired'
        }
        $script:BadAuthCount = 0
    }
    if (-not $script:Login) { return $null }

    # Logged in: the miner saved a new cookie file after the code was issued.
    $fresh = @(Get-CookieFiles | Where-Object { $_.LastWriteTime -gt $script:Login.Issued })
    if ($fresh.Count) {
        Write-Log 'Twitch login completed - new cookie saved.'
        Send-Alert 'Logged in to Twitch again - the miner is back to work.' -Title 'Twitch login OK' -Priority -1
        $script:Login = $null; $script:CodesSent = 0; $script:LoginPausedUntil = $null
        $script:State.loginNeeded = $null
        return $null
    }

    # Code expired (the miner would wait on it forever): restart for a fresh code, 3 tries then every 6 h.
    if ((Get-Date) -gt $script:Login.Expires.AddMinutes(1)) {
        if ($script:CodesSent -lt 3) { return 'login code expired - getting a new one' }
        if (-not $script:LoginPausedUntil) {
            $script:LoginPausedUntil = (Get-Date).AddHours(6)
            $script:State.loginNeeded = "Not logged in after 3 codes - next try $($script:LoginPausedUntil.ToString('ddd HH:mm')), or run run.py by hand"
            Save-Status
            Send-Alert "Still not logged in to Twitch after 3 codes. Next code at $($script:LoginPausedUntil.ToString('ddd HH:mm')), or run run.py by hand on the PC." -Title 'Twitch login needed' -Priority 1
        } elseif ((Get-Date) -gt $script:LoginPausedUntil) {
            $script:CodesSent = 0; $script:LoginPausedUntil = $null
            return 'retrying Twitch login'
        }
    }
    return $null
}

# ---------------------------------------------------------------- main loop
if ($Git -and -not $script:GoodCommit) { $script:GoodCommit = Get-Commit }   # the version running today is the baseline
Save-UpdateState
Write-Log "Supervisor started (PID $PID). Restart every $RestartHours h, update check every $UpdateHours h, graceful stop: $UseWrapper."
Save-Status
Send-Alert 'Supervisor started (boot, task restart or reinstall). Starting miner.' -Title 'Miner supervisor started' -Priority -1

$lastUpdate        = [datetime]::MinValue
$lastCrashAlert    = [datetime]::MinValue
$crashesSinceAlert = 0
$crashed           = $false
$backoff           = 30
$restartAfter      = [TimeSpan]::FromHours($RestartHours)

try {
    while ($true) {
        $sinceUpdate = (Get-Date) - $lastUpdate
        # Daily check, plus an extra check if the miner keeps crashing (an update may fix it).
        if ($sinceUpdate.TotalHours -ge $UpdateHours -or ($crashed -and $sinceUpdate.TotalHours -ge 1)) {
            try { Update-Miner } catch { Set-UpdateResult "Update check error: $_" 'ERROR' }
            $lastUpdate = Get-Date
        }

        # Fresh run: clean up leftovers and reset per-run trackers.
        Stop-Miner -Reason 'leftover before start'
        Remove-Item -LiteralPath $StopFlag -Force -ErrorAction SilentlyContinue
        Rotate-File $OutLog
        Rotate-File $ErrLog
        $script:OutPos = 0; $script:OutRest = ''
        $script:BadAuthCount = 0; $script:Login = $null
        $script:LogPath = $null; $script:LogLen = -1; $script:LogGrewAt = Get-Date; $script:LogIsDebug = $null
        if (-not $script:LoginPausedUntil) { $script:State.loginNeeded = $null }

        $argLine = if ($UseWrapper) { "`"$Wrapper`" `"$EntryPath`" `"$StopFlag`"" } else { "`"$EntryPath`"" }
        $proc = Start-Process -FilePath $Python -ArgumentList $argLine `
            -WorkingDirectory $MinerDir -WindowStyle Hidden `
            -RedirectStandardOutput $OutLog -RedirectStandardError $ErrLog -PassThru
        $null = $proc.Handle   # keep a handle so ExitCode is readable later
        $started = Get-Date
        $commit  = Get-Commit -Short
        Write-Log "Miner started (PID $($proc.Id), commit $commit)."
        $script:State.minerPid     = $proc.Id
        $script:State.minerStarted = $started.ToString('o')
        $script:State.minerState   = 'running'
        Save-Status

        # Check once a minute against the wall clock (survives sleep/hibernate).
        $exited = $false
        $restartReason = $null
        $stalled = $false
        while (-not $exited) {
            $exited = $proc.WaitForExit(60000)
            if ($exited) { break }

            Watch-MinerOutput
            $restartReason = Test-Login
            if (-not $restartReason -and -not $script:Login) {
                $stall = Test-Stalled $started
                if ($stall) { $restartReason = "frozen - $stall"; $stalled = $true }
            }
            # A commit that has run 30 min without crashing becomes the rollback target.
            if ($Git -and ((Get-Date) - $started).TotalMinutes -ge 30) {
                $head = Get-Commit
                if ($head -and $head -ne $script:GoodCommit) { $script:GoodCommit = $head; Save-UpdateState; Write-Log "Commit $commit marked as good." }
            }
            if (-not $restartReason -and ((Get-Date) - $started) -ge $restartAfter) { $restartReason = "scheduled $RestartHours h restart" }
            Save-Status
            if ($restartReason) { break }
        }

        if (-not $exited) {
            if ($stalled) {
                $script:State.stallRestarts++
                Send-Alert "The miner looked frozen ($($restartReason -replace '^frozen - ','')). Restarting it." -Title 'Miner frozen - restarted'
            } elseif ($restartReason -like 'scheduled*') {
                $script:State.scheduledRestarts++
            }
            Stop-MinerGracefully -Proc $proc -Reason $restartReason
            $crashed = $false
            $backoff = 30
            Start-Sleep -Seconds 5
        } else {
            $ran  = (Get-Date) - $started
            $code = $proc.ExitCode
            Write-Log ("Miner exited with code {0} after {1:hh\:mm\:ss}. See miner-stderr.log. Restarting in {2}s." -f $code, $ran, $backoff) 'WARN'
            Stop-Miner -Reason 'cleanup after exit'

            $script:State.minerPid     = $null
            $script:State.minerState   = 'crashed-waiting'
            $script:State.lastExitCode = $code
            $script:State.lastExitTime = (Get-Date).ToString('o')
            $list = @($script:State.crashes) + @([ordered]@{ time = (Get-Date).ToString('o'); exitCode = $code; ranMinutes = [int]$ran.TotalMinutes; commit = $commit })
            $script:State.crashes = @($list | Select-Object -Last 20)
            Save-Status

            # Alert on the first crash, then at most once an hour while it keeps crashing.
            $crashesSinceAlert++
            if (((Get-Date) - $lastCrashAlert).TotalMinutes -ge 60) {
                $tail = Get-StderrTail
                $extra = if ($crashesSinceAlert -gt 1) { " ($crashesSinceAlert crashes since last alert)" } else { '' }
                Send-Alert "Exit $code after $([int]$ran.TotalMinutes) min on $commit$extra. Restarting in $($backoff)s.`n`n$tail" -Title 'Miner crashed' -Priority 1 -Mono
                $lastCrashAlert = Get-Date
                $crashesSinceAlert = 0
            }

            try { Test-Rollback } catch { Write-Log "Rollback check error: $_" 'ERROR' }

            if ($ran.TotalHours -ge 1) { $backoff = 30 }
            $crashed = $true
            Start-Sleep -Seconds $backoff
            $backoff = [Math]::Min($backoff * 2, 900)
        }
    }
} catch {
    Write-Log "Supervisor crashed: $_" 'ERROR'
    $script:State.minerState = 'stopped'
    Save-Status
    Send-Alert "Supervisor crashed: $_ - Task Scheduler will retry in 5 min." -Title 'Miner supervisor crashed' -Priority 1
    Stop-Miner -Reason 'supervisor crash'
    exit 1
} finally {
    if ($haveMutex) { try { $mutex.ReleaseMutex() } catch { } }
}
