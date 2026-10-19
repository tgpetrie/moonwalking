# Installs the point-in-time watcher and registers the "Moonwalking PIT Watch"
# scheduled task. Safe to re-run: it refreshes the copied code and replaces
# the task definition, leaving the log database alone.
#
# The watcher runs from a stable copy in %USERPROFILE%\.moonwalking\pit, not
# from this checkout, so removing or switching a worktree cannot stop it.
# It does not touch the "Moonwalking Collector" task. See docs/developer/PIT_LOG.md.

$ErrorActionPreference = 'Stop'

$TaskName = 'Moonwalking PIT Watch'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$PitDir   = Join-Path (Join-Path $env:USERPROFILE '.moonwalking') 'pit'

New-Item -ItemType Directory -Force -Path $PitDir | Out-Null
Copy-Item -Force (Join-Path $RepoRoot 'backend\pit_log.py')   $PitDir
Copy-Item -Force (Join-Path $RepoRoot 'backend\pit_watch.py') $PitDir
Copy-Item -Force (Join-Path $PSScriptRoot 'run_pit_watch.ps1') $PitDir
$commit = (git -C $RepoRoot rev-parse --short HEAD) 2>$null
"installed $(Get-Date -Format o) from $RepoRoot at $commit" | Out-File -Encoding utf8 (Join-Path $PitDir 'INSTALLED.txt')

$Script = Join-Path $PitDir 'run_pit_watch.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory $PitDir

# Same shape as the collector task: start at logon, 5-minute backstop repeat,
# IgnoreNew so a tick is a no-op while the launcher runs.
$triggers = @(
    (New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"),
    (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5))
)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) -MultipleInstances IgnoreNew
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings `
    -Principal $principal -Force `
    -Description 'Point-in-time log of Coinbase product status and status-page incidents (pit_context.sqlite). See docs/developer/PIT_LOG.md.' |
    Out-Null

Write-Output "Installed watcher to $PitDir ($commit) and registered '$TaskName'"
Write-Output "Start it now with: Start-ScheduledTask -TaskName '$TaskName'"
