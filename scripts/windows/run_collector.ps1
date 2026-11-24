# Always-on Moonwalking collector and local app server (Windows).
#
# Run by the "Moonwalking Collector" scheduled task at logon (see
# docs/developer/ALWAYS_ON_COLLECTOR.md). It must not depend on any chat or
# coding-agent session: a backend started from a session dies when that
# session ends, which is how collection silently stopped on 2026-10-05.
#
# Every store is pinned to %USERPROFILE%\.moonwalking\data so collection never
# splits across worktrees, and the built frontend is served from the same port.

param(
    [int]$Port = 5003
)

$ErrorActionPreference = 'Stop'

# Repo root = two levels up from scripts\windows.
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$MwRoot   = Join-Path $env:USERPROFILE '.moonwalking'
$DataDir  = Join-Path $MwRoot 'data'
$LogDir   = Join-Path $MwRoot 'logs'
$Python   = Join-Path $MwRoot 'venv\Scripts\python.exe'

New-Item -ItemType Directory -Force -Path $DataDir, $LogDir | Out-Null
if (-not (Test-Path $Python)) { throw "Runtime Python not found at $Python" }

$env:WATCHLIST_DB_PATH        = Join-Path $DataDir 'watchlists.sqlite'
$env:MW_SIGNAL_OUTCOMES_DB    = Join-Path $DataDir 'signal_outcomes.sqlite'
$env:MW_BOARD_OUTCOMES_DB     = Join-Path $DataDir 'signal_outcomes.sqlite'  # same file by design
$env:MW_CONTROL_DRY_RUN_DB    = Join-Path $DataDir 'control_dry_run.sqlite'
$env:MW_SELL_PLAN_OUTCOMES_DB = Join-Path $DataDir 'sell_plan_outcomes.sqlite'
$env:MW_VOLUME_1H_DB          = Join-Path $DataDir 'volume_1h.sqlite'
$env:MOONWALKING_PRICE_DB     = Join-Path $DataDir 'price_snapshots.db'
$env:MW_AGENT_OBSERVATIONS_DB = Join-Path $DataDir 'agent_observations.sqlite'
$env:LOG_DIR                  = $LogDir
$env:SERVE_FRONTEND_DIST      = '1'

$Events = Join-Path $LogDir 'collector-events.log'
function Note($msg) { "[$(Get-Date -Format o)] $msg" | Out-File -Append -Encoding utf8 $Events }

# One collector at a time. If an earlier one is still alive (e.g. the
# launcher died or the task was stopped but its Python child kept running),
# adopt it: wait for it to exit, then supervise as usual, instead of starting
# a second copy that would fall back to a different port.
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.ExecutablePath -like "$MwRoot\venv\*" -and $_.CommandLine -match 'backend[\\/]app\.py' }
if ($existing) {
    $ids = ($existing | ForEach-Object { $_.ProcessId }) -join ', '
    Note "collector already running (pid $ids); adopting it"
    $existing | ForEach-Object { Wait-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
    Note "adopted collector exited"
}

# Supervise Python here rather than relying on Task Scheduler's
# restart-on-failure, which does not fire for a non-zero exit code. The
# task's repeating trigger only matters if this launcher itself dies.
#
# Console output: one pair of files per run, previous run kept for crash
# forensics. server.log in $LogDir is the rotating main log.
# Python is launched with Start-Process and file redirection, NOT through
# PowerShell's stream operators: Windows PowerShell 5.1 turns a native
# program's stderr into error records, and under ErrorActionPreference=Stop
# the backend's first log line killed the launcher about a second after start.
$Out = Join-Path $LogDir 'collector-stdout.log'
$Err = Join-Path $LogDir 'collector-stderr.log'
$delay = 5
while ($true) {
    foreach ($f in $Out, $Err) { if (Test-Path $f) { Move-Item -Force $f "$f.prev" } }
    Note "starting collector on port $Port from $RepoRoot"
    $started = Get-Date
    # --auto-port: if a dev backend already holds $Port, collect on the next
    # free port rather than fail (or double-bind) and stop collecting.
    $proc = Start-Process -FilePath $Python -ArgumentList @('backend/app.py', '--port', "$Port", '--auto-port') `
        -WorkingDirectory $RepoRoot -RedirectStandardOutput $Out -RedirectStandardError $Err `
        -WindowStyle Hidden -PassThru
    $null = $proc.Handle  # without a cached handle ExitCode is empty after exit
    $proc.WaitForExit()
    $ran = [int]((Get-Date) - $started).TotalSeconds
    # A run that crashed quickly backs off (up to 5 min) so a broken checkout
    # doesn't spin; a run that lasted restarts promptly.
    if ($ran -lt 120) { $delay = [Math]::Min($delay * 2, 300) } else { $delay = 5 }
    Note "collector exited with code $($proc.ExitCode) after ${ran}s; restarting in ${delay}s"
    Start-Sleep -Seconds $delay
}
