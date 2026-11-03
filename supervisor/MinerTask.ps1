<#
.SYNOPSIS
    Sets up, manages and health-checks the Twitch miner supervisor.

.DESCRIPTION
    -Action Install   : (admin) finds your miner folder, offers to stop a hand-started miner, converts a
                        ZIP download into a git checkout (after a backup), finds Python, checks
                        requirements / run.py / login cookie, sets up Pushover, registers three tasks
                        (the supervisor, a 30-minute health check, a daily points summary) and starts them.
    -Action Health    : HEALTHY / WARNING / DOWN report. Exit code 0 / 1 / 2. No admin needed.
                        With -Notify, sends a Pushover alert when the verdict changes
                        (used by the health-check task; repeats DOWN every 6 h).
    -Action Status    : same as Health.
    -Action Summary   : points earned per streamer, bets and uptime for the last -SummaryHours (default 24).
                        With -Notify, also sends it as a quiet Pushover message (used by the daily task).
    -Action TestAlert : sends a test Pushover notification.
    -Action Start     : (admin) starts the supervisor task now.
    -Action Stop      : (admin) stops the supervisor task and shuts the miner down cleanly.
    -Action Uninstall : (admin) stops everything and removes all three tasks (leaves your miner folder alone).

    Keep this file next to MinerSupervisor.ps1 and miner_wrapper.py (they ship together in the repo's supervisor\ folder).
    Pushover keys live in miner-alerts.json next to the scripts:
        { "pushoverToken": "<APP_TOKEN>", "pushoverUser": "<USER_KEY>", "device": "", "downPriority": 2 }
    downPriority: 2 = emergency (repeats every 5 min until acknowledged, up to 1 h), 1 = high.

    Logon modes (-LogonMode):
      Password (default) - runs at boot whether or not you're signed in; asks for your Windows password
                           once and Task Scheduler stores it. Re-run Install if you change that password.
      S4U                - same, without storing a password; may not work with Microsoft accounts.
      AtLogon            - starts when you sign in, runs in your session.

.EXAMPLE
    .\MinerTask.ps1                    # Install
.EXAMPLE
    .\MinerTask.ps1 -Action Health
.EXAMPLE
    .\MinerTask.ps1 -Action Summary -SummaryHours 168     # last 7 days (the miner keeps 7 days of logs)
#>
[CmdletBinding()]
param(
    [ValidateSet('Install', 'Health', 'Status', 'Summary', 'TestAlert', 'Start', 'Stop', 'Uninstall')]
    [string]$Action = 'Install',
    [string]$MinerDir  = (Split-Path -Parent $PSScriptRoot),   # default: the repo this supervisor\ folder is in
    [string]$PythonExe = '',            # leave empty to auto-detect (venv\, .venv\, env\, py, python)
    [ValidateSet('Password', 'S4U', 'AtLogon')]
    [string]$LogonMode = 'Password',
    [string]$TaskName  = 'Twitch Miner Supervisor',
    [string]$HealthTaskName = 'Twitch Miner Health Check',
    [ValidateRange(5, 1440)] [int]$HealthEveryMinutes = 30,
    [string]$SummaryTaskName = 'Twitch Miner Daily Summary',
    [string]$SummaryTime = '8:57am',
    [ValidateRange(1, 200)] [int]$SummaryHours = 24,
    [string]$RepoUrl   = 'https://github.com/rdavydov/Twitch-Channel-Points-Miner-v2.git',
    [string]$Branch    = 'master',
    [string]$WatchdogTime = '3:00am',   # daily trigger: starts the supervisor if it isn't running (no-op otherwise)
    [switch]$Notify                     # Health/Summary: send via Pushover
)

$ErrorActionPreference = 'Stop'
$Supervisor  = Join-Path $PSScriptRoot 'MinerSupervisor.ps1'
$AlertConfig = Join-Path $PSScriptRoot 'miner-alerts.json'
$Wrapper     = Join-Path $PSScriptRoot 'miner_wrapper.py'

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if ($Action -in @('Install', 'Start', 'Stop', 'Uninstall') -and -not $isAdmin) {
    throw "-Action $Action needs an Administrator PowerShell."
}

# ---------------------------------------------------------------- helpers
function Test-MinerDir([string]$Dir) {
    $Dir -and (Test-Path -LiteralPath (Join-Path $Dir 'TwitchChannelPointsMiner')) -and
              (Test-Path -LiteralPath (Join-Path $Dir 'requirements.txt'))
}

# Uses -MinerDir if it holds the miner; otherwise reads it from the existing task; otherwise searches.
function Resolve-MinerDir {
    if (Test-MinerDir $MinerDir) { return [IO.Path]::GetFullPath($MinerDir) }

    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t -and $t.Actions[0].Arguments -match '-MinerDir "([^"]+)"' -and (Test-MinerDir $Matches[1])) { return $Matches[1] }

    if ($Action -ne 'Install') { throw "Miner not found in $MinerDir. Pass -MinerDir." }

    $roots = @("$env:USERPROFILE\Desktop", "$env:USERPROFILE\Downloads",
               "$env:USERPROFILE\Documents", "$env:USERPROFILE\OneDrive") | Where-Object { Test-Path -LiteralPath $_ }
    Write-Host "No miner in $MinerDir - searching $($roots -join ', ') ..."
    $found = foreach ($r in $roots) {
        Get-ChildItem -LiteralPath $r -Directory -Recurse -Depth 4 -Filter 'TwitchChannelPointsMiner' -ErrorAction SilentlyContinue |
            ForEach-Object { $_.Parent.FullName } |
            Where-Object { (Test-MinerDir $_) -and $_ -notmatch '\.backup-\d' }
    }
    $hits = @($found | Select-Object -Unique)

    if ($hits.Count -eq 0) { throw 'Could not find the miner folder (one containing TwitchChannelPointsMiner\ and requirements.txt). Pass -MinerDir "C:\path\to\it".' }
    if ($hits.Count -eq 1) {
        $ans = Read-Host "Found miner at: $($hits[0])`nUse this folder? (Y/n)"
        if ($ans -match '^[Nn]') { throw 'Cancelled. Pass -MinerDir with the right folder.' }
        return $hits[0]
    }
    Write-Host 'Found more than one copy:'
    for ($i = 0; $i -lt $hits.Count; $i++) { Write-Host "  [$($i + 1)] $($hits[$i])" }
    $n = [int](Read-Host 'Which one runs your miner? Enter number')
    if ($n -lt 1 -or $n -gt $hits.Count) { throw 'Invalid choice.' }
    return $hits[$n - 1]
}

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

function Invoke-Git {
    # git writes progress to stderr; don't let PowerShell treat that as an error.
    $old = $ErrorActionPreference; $ErrorActionPreference = 'Continue'
    try { & git -C $script:Dir @args 2>&1 | ForEach-Object { "$_" } }
    finally { $ErrorActionPreference = $old }
    if ($LASTEXITCODE -ne 0) { throw "git $($args -join ' ') failed (exit $LASTEXITCODE)." }
}

function Kill-Tree([int]$ProcId) {
    & "$env:SystemRoot\System32\taskkill.exe" /PID $ProcId /T /F 2>&1 | Out-Null
}

# Miners started by the supervisor (full path to run.py on the command line).
function Get-SupervisedMiner {
    $escaped = [regex]::Escape((Join-Path $script:Dir 'run.py'))
    @(Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match $escaped })
}

# -Graceful: ask the miner to shut down like Ctrl+C (final report, clean exit) via the wrapper's stop
# flag, wait up to 120 s, then force-kill whatever is left.
function Stop-SupervisedMiner([switch]$Graceful) {
    $procs = Get-SupervisedMiner
    if ($procs.Count -eq 0) { return }
    if ($Graceful -and @($procs | Where-Object { $_.CommandLine -match 'miner_wrapper\.py' }).Count) {
        $flag = Join-Path $script:Dir 'supervisor-logs\stop.flag'
        Set-Content -LiteralPath $flag -Value 'stop'
        Write-Host 'Asking the miner to shut down cleanly (up to 2 min)...' -NoNewline
        $deadline = (Get-Date).AddSeconds(120)
        while ((Get-SupervisedMiner).Count -and (Get-Date) -lt $deadline) { Start-Sleep -Seconds 3; Write-Host '.' -NoNewline }
        Write-Host ''
        Remove-Item -LiteralPath $flag -Force -ErrorAction SilentlyContinue
        $procs = Get-SupervisedMiner
        if ($procs.Count -eq 0) { Write-Host 'Miner shut down cleanly.'; return }
        Write-Host 'Still running - forcing it.'
    }
    $procs | ForEach-Object { Write-Host "Killing miner PID $($_.ProcessId)"; Kill-Tree $_.ProcessId }
}

# Any python running a run.py (e.g. started by hand as ".\run.py"). Asks before killing.
function Stop-ManualMiners {
    $supervised = [regex]::Escape((Join-Path $script:Dir 'run.py'))
    $procs = @(Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -and $_.CommandLine -match '(^|[\s"\\/])run\.py"?\s*$' -and $_.CommandLine -notmatch $supervised })
    if ($procs.Count -eq 0) { return }
    Write-Host "`nThese look like a miner that's already running:"
    $procs | ForEach-Object { Write-Host "  PID $($_.ProcessId): $($_.CommandLine)" }
    $ans = Read-Host 'Stop them so the scheduled task can take over? Two miners on one account will clash. (Y/n)'
    if ($ans -match '^[Nn]') { Write-Warning 'Left running. Close it yourself before the task starts the miner.'; return }
    $procs | Sort-Object { $_.CommandLine -notmatch 'WindowsApps' } | ForEach-Object {
        if (Get-Process -Id $_.ProcessId -ErrorAction SilentlyContinue) { Write-Host "Stopping PID $($_.ProcessId)"; Kill-Tree $_.ProcessId }
    }
}

# Pushover priority: -1 quiet (no sound), 0 normal, 1 high (bypasses quiet hours).
function Get-AlertConfig {
    if (-not (Test-Path -LiteralPath $AlertConfig)) { return $null }
    try { return Get-Content -LiteralPath $AlertConfig -Raw | ConvertFrom-Json } catch { return $null }
}

# Priority 2 (emergency) repeats every 5 min for up to 1 h until acknowledged in the Pushover app.
function Send-Pushover {
    param([string]$Msg, [int]$Priority = 0, [string]$Title = 'Twitch miner', [switch]$Mono)
    $cfg = Get-AlertConfig
    if ($cfg -and ($cfg.appriseUrls -or $cfg.appriseUrgentUrls)) {
        # Apprise (Discord, Telegram, Matrix, ntfy, Pushover, ...) via notify.py; message body on stdin.
        $py = if ($PythonExe) { $PythonExe } else { Find-Python $script:Dir }
        if (-not $py) { throw 'Python not found - needed to send Apprise alerts.' }
        $ErrorActionPreference = 'Continue'
        $OutputEncoding = New-Object System.Text.UTF8Encoding($false)
        $a = @((Join-Path $PSScriptRoot 'notify.py'), '--title', $Title, '--priority', "$Priority")
        if ($Mono) { $a += '--mono' }
        $out = $Msg | & $py @a 2>&1 | ForEach-Object { "$_" }
        if ($LASTEXITCODE -eq 0) { return $true }
        if ($LASTEXITCODE -eq 3) { return $false }
        throw "Apprise send failed: $($out -join ' ')"
    }
    if (-not $cfg -or -not $cfg.pushoverToken -or -not $cfg.pushoverUser) { return $false }
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    if ($Msg.Length -gt 1000) { $Msg = $Msg.Substring(0, 1000) + '...' }
    $body = @{ token = $cfg.pushoverToken; user = $cfg.pushoverUser; title = "$Title ($env:COMPUTERNAME)"; message = $Msg; priority = $Priority }
    if ($Priority -ge 2) { $body.retry = 300; $body.expire = 3600 }
    if ($cfg.device) { $body.device = $cfg.device }
    if ($Mono)       { $body.monospace = 1 }
    Invoke-RestMethod -Uri 'https://api.pushover.net/1/messages.json' -Method Post -Body $body -TimeoutSec 15 | Out-Null
    return $true
}

function Format-Age([datetime]$Since) {
    $s = (Get-Date) - $Since
    if ($s.TotalDays -ge 1)  { return '{0}d {1}h' -f [int][Math]::Floor($s.TotalDays), $s.Hours }
    if ($s.TotalHours -ge 1) { return '{0}h {1}m' -f [int][Math]::Floor($s.TotalHours), $s.Minutes }
    return '{0}m {1}s' -f [int][Math]::Floor($s.TotalMinutes), $s.Seconds
}

function Get-Health {
    $down = New-Object System.Collections.Generic.List[string]   # it's not working
    $warn = New-Object System.Collections.Generic.List[string]   # working, but needs a look
    $note = New-Object System.Collections.Generic.List[string]   # FYI (doesn't change the verdict)
    $info = New-Object System.Collections.Generic.List[string]
    $logDir = Join-Path $script:Dir 'supervisor-logs'

    Write-Verbose 'Health: checking scheduled task'
    # Scheduled task
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) { $down.Add("Scheduled task '$TaskName' not found.") }
    elseif ($t.State -eq 'Disabled') { $down.Add('Supervisor task is disabled.') }
    elseif ($t.State -ne 'Running') {
        $res = '?'
        try { $res = '0x{0:X}' -f ($t | Get-ScheduledTaskInfo).LastTaskResult } catch { }
        $down.Add("Supervisor task is not running (state $($t.State), last result $res).")
    }

    Write-Verbose 'Health: reading status.json'
    # Supervisor status file
    $st = $null
    $sf = Join-Path $logDir 'status.json'
    if (Test-Path -LiteralPath $sf) { try { $st = Get-Content -LiteralPath $sf -Raw | ConvertFrom-Json } catch { } }
    if (-not $st) {
        $down.Add('No status.json - supervisor has not written health data (restart it after updating the scripts).')
    } else {
        $hb = [datetime]$st.heartbeat
        if (((Get-Date) - $hb).TotalMinutes -gt 3) { $down.Add("Supervisor heartbeat is stale (last $(Format-Age $hb) ago) - hung or dead.") }
        elseif (-not (Get-Process -Id $st.supervisorPid -ErrorAction SilentlyContinue)) { $down.Add("Supervisor PID $($st.supervisorPid) is gone.") }
        $info.Add("Supervisor: PID $($st.supervisorPid), up $(Format-Age ([datetime]$st.supervisorStarted)), heartbeat $(Format-Age $hb) ago")

        switch ($st.minerState) {
            'running' {
                $mp = if ($st.minerPid) { Get-Process -Id $st.minerPid -ErrorAction SilentlyContinue }
                if ($mp) { $info.Add("Miner: running, PID $($st.minerPid), up $(Format-Age ([datetime]$st.minerStarted)), RAM $([int]($mp.WorkingSet64 / 1MB)) MB") }
                else { $down.Add("Miner PID $($st.minerPid) is not running.") }
            }
            'crashed-waiting' {
                $since = [datetime]$st.lastExitTime
                $msg = "Miner crashed (exit $($st.lastExitCode)) $(Format-Age $since) ago, waiting to restart."
                if (((Get-Date) - $since).TotalMinutes -gt 20) { $down.Add($msg) } else { $warn.Add($msg) }
            }
            'restarting' { $info.Add('Miner: in its scheduled restart.') }
            default      { $down.Add("Miner state: $($st.minerState).") }
        }

        $recent = @($st.crashes | Where-Object { $_ -and ([datetime]$_.time) -gt (Get-Date).AddHours(-24) })
        if ($recent.Count -gt 0) {
            $last = $recent[-1]
            $line = "$($recent.Count) crash(es) in the last 24 h - last: exit $($last.exitCode) after $($last.ranMinutes) min, $(Format-Age ([datetime]$last.time)) ago."
            if ($recent.Count -ge 3) { $warn.Add($line) } else { $note.Add($line) }
        }

        if ($st.lastUpdateCheck) {
            $uc = [datetime]$st.lastUpdateCheck
            $info.Add("Last update check: $(Format-Age $uc) ago - $($st.lastUpdateResult)")
            if ($st.lastUpdateResult -match 'failed|error|disabled|skipping') { $warn.Add("Update problem: $($st.lastUpdateResult)") }
            if (((Get-Date) - $uc).TotalHours -gt 26) { $warn.Add("No update check for $(Format-Age $uc).") }
        }
        if ($st.lastRollback) {
            $rbTime, $rbWhat = "$($st.lastRollback)" -split '\|', 2
            if (([datetime]$rbTime) -gt (Get-Date).AddHours(-24)) { $warn.Add("Bad update rolled back $(Format-Age ([datetime]$rbTime)) ago ($rbWhat).") }
        }
        if ($st.loginNeeded) { $warn.Add("Twitch login: $($st.loginNeeded)") }

        if ($st.lastLogActivity) {
            $la = [datetime]$st.lastLogActivity
            $dbg = if ($st.logIsDebug -eq $true) { 'DEBUG level, freeze auto-restart on' } elseif ($st.logIsDebug -eq $false) { 'INFO level, freeze auto-restart off' } else { 'level not checked yet' }
            $info.Add("Miner log last grew $(Format-Age $la) ago ($dbg)")
            if (((Get-Date) - $la).TotalHours -gt 2 -and $st.minerState -eq 'running' -and -not $st.loginNeeded) { $warn.Add("Miner log hasn't grown for $(Format-Age $la) - it may be frozen.") }
        }
        $info.Add("Version: $($st.version) (good: $($st.goodCommit)) | Restarts: $($st.scheduledRestarts) scheduled, $($st.stallRestarts) freeze | Graceful stop: $($st.gracefulStop)")
        $info.Add("Python: $($st.pythonExe)")
    }

    Write-Verbose 'Health: scanning miner-stderr.log'
    # Errors printed by the miner this run (Python logs to stderr).
    $errLog = Join-Path $logDir 'miner-stderr.log'
    if (Test-Path -LiteralPath $errLog) {
        $errLines = @(Get-Content -LiteralPath $errLog -Tail 500 -ErrorAction SilentlyContinue |
            Where-Object { $_ -cmatch 'Traceback \(most recent call last\)|^\s*[\w.]+(Error|Exception)\b|\b(ERROR|CRITICAL)\b' })
        if ($errLines.Count) { $note.Add("miner-stderr.log: $($errLines.Count) error line(s) this run. Latest: $($errLines[-1].Trim())") }
    }

    Write-Verbose 'Health: scanning miner log file'
    # The miner's current log file: recent ERROR lines.
    $latest = Get-ChildItem -LiteralPath (Join-Path $script:Dir 'logs') -File -Filter '*.log' -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        $logErr = @(Get-Content -LiteralPath $latest.FullName -Tail 1000 -ErrorAction SilentlyContinue | Where-Object { $_ -cmatch ' - (ERROR|CRITICAL) - ' })
        if ($logErr.Count) { $note.Add("$($latest.Name): $($logErr.Count) ERROR line(s) in the last 1000. Latest: $($logErr[-1].Trim())") }
    }

    Write-Verbose 'Health: done'
    $verdict = if ($down.Count) { 'DOWN' } elseif ($warn.Count) { 'WARNING' } else { 'HEALTHY' }
    [pscustomobject]@{ Verdict = $verdict; Down = $down; Warn = $warn; Note = $note; Info = $info }
}

# Totals points from the miner's own log files (current + rotated; the miner keeps 7 days).
# Handles both the normal and the "less" log formats.
function Get-Summary([int]$Hours) {
    $since  = (Get-Date).AddHours(-$Hours)
    $files  = @(Get-ChildItem -LiteralPath (Join-Path $script:Dir 'logs') -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '\.log(\.\d{4}-\d{2}-\d{2})?$' } |
        Sort-Object LastWriteTime -Descending | Select-Object -First ([int][Math]::Ceiling($Hours / 24) + 2))
    $tsRe   = [regex]'^\d{2}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}'
    $gainRe = [regex]'\+(\d+) \u2192 (?:Streamer\(username=)?([^,\s(]+).*?Reason: ([A-Z_]+)'
    $betRe  = [regex]'EventPrediction(?:\(event_id=[^,]*, streamer=Streamer\(username=|: )([^,\s(]+).*Result: (WIN|LOSE|REFUND), \w+: ([+-]?[\d.]+)([kKMBT]?)'
    $mult   = @{ '' = 1; 'k' = 1e3; 'M' = 1e6; 'B' = 1e9; 'T' = 1e12 }   # keys are case-insensitive: 'k' also matches 'K'

    $earned = @{}; $betBy = @{}; $byReason = @{}
    $wins = 0; $losses = 0; $refunds = 0; $first = $null
    foreach ($f in $files) {
        try {
            $fs = [IO.File]::Open($f.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::ReadWrite)
            $sr = New-Object IO.StreamReader($fs, [Text.Encoding]::UTF8)
            try {
                while ($null -ne ($line = $sr.ReadLine())) {
                    if (-not ($line.Contains('Reason:') -or $line.Contains('Result:'))) { continue }
                    $m = $tsRe.Match($line)
                    if (-not $m.Success) { continue }
                    $t = [datetime]::MinValue
                    if (-not [datetime]::TryParseExact($m.Value, 'dd/MM/yy HH:mm:ss', [Globalization.CultureInfo]::InvariantCulture, [Globalization.DateTimeStyles]::None, [ref]$t)) { continue }
                    if ($t -lt $since) { continue }
                    if (-not $first -or $t -lt $first) { $first = $t }

                    $g = $gainRe.Match($line)
                    if ($g.Success) {
                        $pts = [int]$g.Groups[1].Value; $who = $g.Groups[2].Value; $why = $g.Groups[3].Value
                        if ($why -eq 'PREDICTION') { continue }   # bet payouts are counted from the Result lines (net of the stake)
                        $earned[$who]   = [int]$earned[$who] + $pts
                        $byReason[$why] = [int]$byReason[$why] + $pts
                        continue
                    }
                    $b = $betRe.Match($line)
                    if ($b.Success) {
                        $who = $b.Groups[1].Value
                        $net = [double]::Parse($b.Groups[3].Value, [Globalization.CultureInfo]::InvariantCulture) * $mult[$b.Groups[4].Value]
                        $betBy[$who] = [double]$betBy[$who] + $net
                        switch ($b.Groups[2].Value) { 'WIN' { $wins++ } 'LOSE' { $losses++ } 'REFUND' { $refunds++ } }
                        if (-not $earned.ContainsKey($who)) { $earned[$who] = 0 }
                    }
                }
            } finally { $sr.Dispose(); $fs.Dispose() }
        } catch { Write-Verbose "Could not read $($f.Name): $_" }
    }

    $sumEarned = 0; foreach ($v in $earned.Values) { $sumEarned += $v }
    $sumBets   = 0.0; foreach ($v in $betBy.Values) { $sumBets += $v }
    $net = $sumEarned + [int]$sumBets
    $fmt = { param($n) $s = ([Math]::Round([double]$n)).ToString('N0', [Globalization.CultureInfo]::InvariantCulture); if ($n -ge 0) { "+$s" } else { $s } }

    $out = New-Object System.Collections.Generic.List[string]
    $window = if ($first -and $first -gt $since.AddMinutes(30)) { "since $($first.ToString('ddd HH:mm')) (logs start there)" } else { "last $Hours h" }
    $out.Add("Net $(& $fmt $net) points, $window")
    $betLine = if ($wins + $losses + $refunds) { "$(& $fmt $sumBets) ($wins won, $losses lost, $refunds refunded)" } else { 'none' }
    $out.Add("Watching/claims: $(& $fmt $sumEarned)  Bets: $betLine")
    if ($earned.Count) {
        $out.Add('')
        $rows = @($earned.Keys | ForEach-Object { [pscustomobject]@{ Name = $_; Earned = [int]$earned[$_]; Bets = [double]$betBy[$_] } } |
            Sort-Object { $_.Earned + $_.Bets } -Descending)
        $w = [Math]::Min(16, ($rows | ForEach-Object { $_.Name.Length } | Measure-Object -Maximum).Maximum)
        foreach ($r in ($rows | Select-Object -First 12)) {
            $name = if ($r.Name.Length -gt $w) { $r.Name.Substring(0, $w) } else { $r.Name.PadRight($w) }
            $bets = if ($r.Bets -ne 0) { "  bets $(& $fmt $r.Bets)" } else { '' }
            $out.Add("$name $((& $fmt $r.Earned).PadLeft(8))$bets")
        }
        if ($rows.Count -gt 12) { $out.Add("... and $($rows.Count - 12) more") }
    } else { $out.Add('No points logged in this window.') }
    if ($byReason.Count) {
        $out.Add('')
        $out.Add('By type: ' + (($byReason.GetEnumerator() | Sort-Object Value -Descending | ForEach-Object { "$($_.Key) $(& $fmt $_.Value)" }) -join ', '))
    }

    $sf = Join-Path $script:Dir 'supervisor-logs\status.json'
    if (Test-Path -LiteralPath $sf) {
        try {
            $st = Get-Content -LiteralPath $sf -Raw | ConvertFrom-Json
            $crashes = @($st.crashes | Where-Object { $_ -and ([datetime]$_.time) -gt $since }).Count
            $up = if ($st.minerStarted -and $st.minerState -eq 'running') { "up $(Format-Age ([datetime]$st.minerStarted))" } else { "state $($st.minerState)" }
            $out.Add('')
            $out.Add("Miner $up | $crashes crash(es) | version $($st.version)")
        } catch { }
    }
    [pscustomobject]@{ Text = ($out -join "`n"); Net = $net }
}

# ---------------------------------------------------------------- actions
$script:Dir = Resolve-MinerDir
if ($Action -ne 'Health' -or -not $Notify) { Write-Host "Miner folder: $script:Dir" }

switch ($Action) {

    'Install' {
        if (-not (Test-Path -LiteralPath $Supervisor)) { throw "MinerSupervisor.ps1 not found next to this script ($Supervisor)." }
        if (-not (Test-Path -LiteralPath $Wrapper)) { Write-Warning "miner_wrapper.py not found next to this script - restarts will be hard kills (no clean shutdown)." }
        if (-not (Get-Command git.exe -ErrorAction SilentlyContinue)) {
            throw 'git not found. Install Git for Windows (winget install Git.Git), reopen PowerShell, and run this again.'
        }

        # 1. Stop a hand-started miner first (it would also block the ZIP conversion).
        Stop-ManualMiners

        # 2. Make sure the folder is a git checkout so daily updates work.
        if (-not (Test-Path -LiteralPath (Join-Path $script:Dir '.git'))) {
            Write-Host "`nThis folder is a ZIP download, not a git checkout."
            Write-Host 'To enable automatic updates it will be converted in place:'
            Write-Host '  - a full backup copy is made first'
            Write-Host '  - repo files are replaced with the latest version from GitHub'
            Write-Host '  - your own files (run.py, cookies\, logs\, analytics\) are left as-is'
            $ans = Read-Host 'Convert now? (Y/n)'
            if ($ans -match '^[Nn]') {
                Write-Warning 'Skipped. The miner will still run and restart, but update checks stay off.'
            } else {
                Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
                Stop-SupervisedMiner
                $backup = "$($script:Dir).backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
                Write-Host "Backing up to $backup ..."
                Copy-Item -LiteralPath $script:Dir -Destination $backup -Recurse
                Invoke-Git init --quiet
                Invoke-Git remote add origin $RepoUrl
                Invoke-Git fetch --quiet origin $Branch
                Invoke-Git checkout -f -B $Branch --track "origin/$Branch"
                Write-Host "Converted. Backup kept at: $backup"
            }
        } else {
            $remote = (& git -C $script:Dir remote get-url origin 2>$null)
            Write-Host "Git checkout found (origin: $remote)."
            if ($remote -and $remote -notmatch 'rdavydov/Twitch-Channel-Points-Miner-v2') {
                Write-Warning "origin is not rdavydov's repo - updates will come from $remote."
            }
        }

        # 3. Find Python and make sure requirements are installed (quick no-op if already satisfied).
        $py = if ($PythonExe) { $PythonExe } else { Find-Python $script:Dir }
        if (-not $py) { throw 'No Python found (checked venv\, .venv\, env\, py, python). Pass -PythonExe "C:\path\to\python.exe".' }
        Write-Host "Using Python: $py  ($(& $py --version 2>&1))"
        & $py -m pip install --disable-pip-version-check -q -r (Join-Path $script:Dir 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'pip install -r requirements.txt failed.' }

        # 4. run.py + login check
        $entry = Join-Path $script:Dir 'run.py'
        if (-not (Test-Path -LiteralPath $entry)) {
            Write-Warning "run.py not found in $($script:Dir). Copy example.py to run.py, set your username/streamers (and emoji=False), then run this again."
            return
        }
        if (-not (Get-ChildItem -Path (Join-Path $script:Dir 'cookies') -Filter *.pkl -ErrorAction SilentlyContinue)) {
            Write-Warning @"
No login cookie (cookies\*.pkl) in this folder. The task runs hidden and can't answer the Twitch login prompt.
Run it once by hand, finish the login, Ctrl+C, then run this again:
    cd "$($script:Dir)"
    & "$py" run.py
"@
            return
        }

        # 5. Pushover (optional) - stored next to the scripts, readable only by you, SYSTEM and Administrators.
        if (-not (Test-Path -LiteralPath $AlertConfig)) {
            Write-Host "`nPushover alerts (press Enter to skip). Create an application at https://pushover.net/apps/build to get a token."
            $tok = (Read-Host 'Pushover application API token').Trim()
            if ($tok) {
                $usr = (Read-Host 'Pushover user key').Trim()
                [ordered]@{ pushoverToken = $tok; pushoverUser = $usr; device = '' } | ConvertTo-Json | Set-Content -LiteralPath $AlertConfig -Encoding UTF8
                & icacls.exe $AlertConfig /inheritance:r /grant:r "$($env:USERDOMAIN)\$($env:USERNAME):F" 'SYSTEM:F' 'Administrators:F' | Out-Null
                try { if (Send-Pushover 'Alerts are set up. You will hear from me if the miner crashes or goes down.' -Title 'Miner alerts') { Write-Host 'Test notification sent - check your phone.' } }
                catch { Write-Warning "Pushover test failed: $_  (fix miner-alerts.json, then run -Action TestAlert)" }
            }
        } else { Write-Host "Pushover config found: $AlertConfig" }

        # 6. Register tasks (absolute paths so PATH differences don't matter).
        $psExe = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
        $user  = "$env:USERDOMAIN\$env:USERNAME"

        $supArg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$Supervisor`" -MinerDir `"$($script:Dir)`" -PythonExe `"$py`" -Branch $Branch"
        $supAction = New-ScheduledTaskAction -Execute $psExe -Argument $supArg -WorkingDirectory $script:Dir
        $startTrigger = if ($LogonMode -eq 'AtLogon') { New-ScheduledTaskTrigger -AtLogOn -User $user } else { New-ScheduledTaskTrigger -AtStartup }
        $startTrigger.Delay = 'PT1M'   # give networking a minute after boot/logon
        $watchdog = New-ScheduledTaskTrigger -Daily -At $WatchdogTime
        $supSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
            -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd `
            -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

        $hcArg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Action Health -Notify -MinerDir `"$($script:Dir)`" -TaskName `"$TaskName`""
        $hcAction  = New-ScheduledTaskAction -Execute $psExe -Argument $hcArg -WorkingDirectory $PSScriptRoot
        $hcTrigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(5) -RepetitionInterval (New-TimeSpan -Minutes $HealthEveryMinutes)
        $hcSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 5) -MultipleInstances IgnoreNew `
            -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

        $smArg = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" -Action Summary -Notify -MinerDir `"$($script:Dir)`""
        $smAction  = New-ScheduledTaskAction -Execute $psExe -Argument $smArg -WorkingDirectory $PSScriptRoot
        $smTrigger = New-ScheduledTaskTrigger -Daily -At $SummaryTime
        $smSettings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew `
            -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

        $tasks = @(
            @{ TaskName = $TaskName;        Action = $supAction; Trigger = @($startTrigger, $watchdog); Settings = $supSettings; Force = $true },
            @{ TaskName = $HealthTaskName;  Action = $hcAction;  Trigger = $hcTrigger;                  Settings = $hcSettings;  Force = $true },
            @{ TaskName = $SummaryTaskName; Action = $smAction;  Trigger = $smTrigger;                  Settings = $smSettings;  Force = $true }
        )
        if ($LogonMode -eq 'Password') {
            $cred = Get-Credential -UserName $user -Message "Password for $user (your Microsoft account password, not your PIN). Task Scheduler stores it so the miner runs without you signed in."
            $plain = $cred.GetNetworkCredential().Password
        }
        foreach ($t in $tasks) {
            switch ($LogonMode) {
                'Password' { Register-ScheduledTask @t -User $user -Password $plain -RunLevel Limited | Out-Null }
                'S4U'      { Register-ScheduledTask @t -Principal (New-ScheduledTaskPrincipal -UserId $user -LogonType S4U -RunLevel Limited) | Out-Null }
                'AtLogon'  { Register-ScheduledTask @t -Principal (New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited) | Out-Null }
            }
            Write-Host "Registered task '$($t.TaskName)' ($LogonMode)."
        }
        $plain = $null

        # Restart the supervisor so it runs the current version of MinerSupervisor.ps1.
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Stop-SupervisedMiner -Graceful
        Start-Sleep -Seconds 2
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'Supervisor started. Waiting 20 s for the first heartbeat...'
        Start-Sleep -Seconds 20
        & $PSCommandPath -Action Health -MinerDir $script:Dir -TaskName $TaskName
    }

    { $_ -in @('Health', 'Status') } {
        $h = Get-Health

        if ($Notify) {
            # Alert only when the verdict changes; repeat DOWN every 6 h until it recovers.
            $stateFile = Join-Path $script:Dir 'supervisor-logs\health-state.json'
            $prev = $null
            if (Test-Path -LiteralPath $stateFile) { try { $prev = Get-Content -LiteralPath $stateFile -Raw | ConvertFrom-Json } catch { } }
            $prevVerdict = if ($prev) { $prev.verdict } else { 'HEALTHY' }
            $lastSent    = if ($prev -and $prev.lastNotified) { [datetime]$prev.lastNotified } else { [datetime]::MinValue }

            $cfg = Get-AlertConfig
            $downPrio = if ($cfg -and $null -ne $cfg.downPriority) { [int]$cfg.downPriority } else { 2 }
            $send = ($h.Verdict -ne $prevVerdict) -or ($h.Verdict -eq 'DOWN' -and ((Get-Date) - $lastSent).TotalHours -ge 6)
            if ($send) {
                $lines = @($h.Down) + @($h.Warn)
                switch ($h.Verdict) {
                    'DOWN'    { $title = 'Miner DOWN';    $prio = $downPrio; $body = $lines -join "`n" }
                    'WARNING' { $title = 'Miner warning'; $prio = 0;  $body = $lines -join "`n" }
                    default   { $title = 'Miner recovered'; $prio = -1; $body = "Back to healthy (was $prevVerdict).`n" + ((@($h.Info) | Select-Object -First 2) -join "`n") }
                }
                try { if (Send-Pushover $body -Priority $prio -Title $title) { $lastSent = Get-Date } } catch { }
            }
            [ordered]@{ verdict = $h.Verdict; checked = (Get-Date).ToString('o'); lastNotified = $(if ($lastSent -gt [datetime]::MinValue) { $lastSent.ToString('o') }) } |
                ConvertTo-Json | Set-Content -LiteralPath $stateFile -Encoding UTF8
        }

        if (-not $Notify -or [Environment]::UserInteractive) {
            $color = @{ HEALTHY = 'Green'; WARNING = 'Yellow'; DOWN = 'Red' }[$h.Verdict]
            Write-Host "`nMiner health: $($h.Verdict)" -ForegroundColor $color
            $h.Down | ForEach-Object { Write-Host "  [X] $_" -ForegroundColor Red }
            $h.Warn | ForEach-Object { Write-Host "  [!] $_" -ForegroundColor Yellow }
            $h.Note | ForEach-Object { Write-Host "  [i] $_" -ForegroundColor DarkYellow }
            $h.Info | ForEach-Object { Write-Host "   -  $_" }
            $log = Join-Path $script:Dir 'supervisor-logs\supervisor.log'
            if (Test-Path -LiteralPath $log) {
                $recentIssues = @(Get-Content -LiteralPath $log -Tail 300 | Where-Object { $_ -match '\[(WARN|ERROR)\]' } | Select-Object -Last 5)
                if ($recentIssues.Count) { Write-Host "`n  Recent supervisor warnings/errors:"; $recentIssues | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkGray } }
            }
            Write-Host "`n  Logs: $($script:Dir)\supervisor-logs\   Miner logs: $($script:Dir)\logs\"
        }
        exit $(switch ($h.Verdict) { 'HEALTHY' { 0 } 'WARNING' { 1 } default { 2 } })
    }

    'Summary' {
        $sum = Get-Summary $SummaryHours
        Write-Host ''
        Write-Host $sum.Text
        if ($Notify) {
            $cfg = Get-AlertConfig
            $prio = if ($cfg -and $null -ne $cfg.summaryPriority) { [int]$cfg.summaryPriority } else { -1 }
            try { if (Send-Pushover $sum.Text -Priority $prio -Title "Miner summary ($SummaryHours h)" -Mono) { Write-Host "`nSent to Pushover." } }
            catch { Write-Warning "Pushover send failed: $_" }
        }
    }

    'TestAlert' {
        if (Send-Pushover "Test from MinerTask.ps1 at $(Get-Date -Format 'HH:mm:ss')." -Title 'Miner test') { Write-Host 'Sent.' }
        else { Write-Warning "No Pushover config. Create $AlertConfig with: { `"pushoverToken`": `"...`", `"pushoverUser`": `"...`", `"device`": `"`" }" }
    }

    'Start' {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host 'Started.'
    }

    'Stop' {
        # Ending the task kills the supervisor; the miner it launched must be killed separately.
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Stop-SupervisedMiner -Graceful
        Write-Host 'Stopped. It starts again at next boot or the daily watchdog time unless you disable the task.'
        Write-Host "Note: the health check will report DOWN - disable '$HealthTaskName' too if this is intentional."
    }

    'Uninstall' {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Stop-SupervisedMiner -Graceful
        foreach ($n in @($TaskName, $HealthTaskName, $SummaryTaskName)) { Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue }
        Write-Host "Removed '$TaskName', '$HealthTaskName' and '$SummaryTaskName'. Miner folder, cookies, logs and miner-alerts.json left in place."
    }
}
