# Always-on point-in-time watcher (Coinbase products + status page).
#
# Run by the "Moonwalking PIT Watch" scheduled task (see docs/developer/PIT_LOG.md).
# Runs from a stable copy in %USERPROFILE%\.moonwalking\pit (put there by
# install_pit_watch_task.ps1), so it never depends on a worktree or a chat
# session. It is separate from the collector and never touches it.

$ErrorActionPreference = 'Stop'

$MwRoot  = Join-Path $env:USERPROFILE '.moonwalking'
$PitDir  = Join-Path $MwRoot 'pit'
$DataDir = Join-Path $MwRoot 'data'
$LogDir  = Join-Path $MwRoot 'logs'
$Python  = Join-Path $MwRoot 'venv\Scripts\python.exe'
$Script  = Join-Path $PitDir 'pit_watch.py'

New-Item -ItemType Directory -Force -Path $DataDir, $LogDir | Out-Null
if (-not (Test-Path $Python)) { throw "Runtime Python not found at $Python" }
if (-not (Test-Path $Script)) { throw "Watcher not installed at $Script (run install_pit_watch_task.ps1)" }

$env:MW_PIT_LOG_DB = Join-Path $DataDir 'pit_context.sqlite'

$Events = Join-Path $LogDir 'pit-watch-events.log'
function Note($msg) { "[$(Get-Date -Format o)] $msg" | Out-File -Append -Encoding utf8 $Events }

# One watcher at a time: adopt a running one instead of starting a second.
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.ExecutablePath -like "$MwRoot\venv\*" -and $_.CommandLine -match 'pit_watch\.py' }
if ($existing) {
    $ids = ($existing | ForEach-Object { $_.ProcessId }) -join ', '
    Note "watcher already running (pid $ids); adopting it"
    $existing | ForEach-Object { Wait-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Note "adopted watcher exited"
}

# Supervise Python here (Task Scheduler's restart-on-failure does not fire on a
# non-zero exit code). Start-Process with file redirection, not stream
# operators, so stderr lines do not kill the launcher under Windows PowerShell 5.1.
$Out = Join-Path $LogDir 'pit-watch-stdout.log'
$Err = Join-Path $LogDir 'pit-watch-stderr.log'
$delay = 5
while ($true) {
    foreach ($f in $Out, $Err) { if (Test-Path $f) { Move-Item -Force $f "$f.prev" } }
    Note "starting watcher -> $env:MW_PIT_LOG_DB"
    $started = Get-Date
    $proc = Start-Process -FilePath $Python -ArgumentList @("`"$Script`"", '--loop', '--interval', '300') `
        -WorkingDirectory $PitDir -RedirectStandardOutput $Out -RedirectStandardError $Err `
        -WindowStyle Hidden -PassThru
    $null = $proc.Handle
    $proc.WaitForExit()
    $ran = [int]((Get-Date) - $started).TotalSeconds
    if ($ran -lt 120) { $delay = [Math]::Min($delay * 2, 300) } else { $delay = 5 }
    Note "watcher exited with code $($proc.ExitCode) after ${ran}s; restarting in ${delay}s"
    Start-Sleep -Seconds $delay
}
