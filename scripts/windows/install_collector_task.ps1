# Registers (or re-registers) the "Moonwalking Collector" scheduled task that
# keeps scripts\windows\run_collector.ps1 running. Safe to re-run: it replaces
# the task definition and leaves data and logs alone.
# See docs/developer/ALWAYS_ON_COLLECTOR.md.

$ErrorActionPreference = 'Stop'

$TaskName = 'Moonwalking Collector'
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$Script   = Join-Path $PSScriptRoot 'run_collector.ps1'

$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$Script`"" `
    -WorkingDirectory $RepoRoot

# Start at logon; the 5-minute repeat is a backstop that revives the launcher
# if it ever dies. MultipleInstances=IgnoreNew makes a tick a no-op while the
# launcher is running, and the launcher itself restarts Python.
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
    -Description 'Always-on Moonwalking collector and local app server (port 5003). See docs/developer/ALWAYS_ON_COLLECTOR.md.' |
    Out-Null

Write-Output "Registered '$TaskName' -> $Script"
Write-Output "Start it now with: Start-ScheduledTask -TaskName '$TaskName'"
