param(
    [ValidatePattern('^[A-Z0-9]{1,20}-USD$')][string]$Product = 'AMP-USD',
    [switch]$Remove
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$workerPath = Join-Path $repoRoot 'scripts\chart_worker.py'
$statePath = Join-Path $repoRoot 'frontend\.runtime\chart-worker'
$taskName = "Moonwalking-Chart-$Product"
$pythonPath = (Get-Command python.exe -ErrorAction Stop).Source
$pythonWindowless = Join-Path (Split-Path $pythonPath) 'pythonw.exe'
if (Test-Path -LiteralPath $pythonWindowless) { $pythonPath = $pythonWindowless }
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($existing) {
    $matching = $existing.Description -eq "Moonwalking local chart pilot: $repoRoot" -and
        $existing.Actions.Execute -eq $pythonPath -and $existing.Actions.Arguments.Contains($workerPath)
    if (-not $matching) { throw 'An unrelated task already owns this name; no changes made.' }
}
if ($Remove) {
    if ($existing) { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false }
    Write-Output "Removed own task $taskName. Local cache retained."
    exit
}
$arguments = '"' + $workerPath + '" --product ' + $Product + ' --state-dir "' + $statePath + '"'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $repoRoot
$nextAt = [DateTimeOffset]::UtcNow.AddHours(1)
$statusPath = Join-Path $statePath 'status.json'
if (Test-Path -LiteralPath $statusPath) {
    $status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
    if ($status.product_id -ne $Product) { throw 'Existing local cache uses another product.' }
    # PowerShell 7 can deserialize ISO strings as DateTime; avoid an implicit
    # culture string conversion that drops the UTC Kind before parsing.
    $candidate = if ($status.next_run_at -is [DateTime]) { [DateTimeOffset]::new($status.next_run_at) } else { [DateTimeOffset]::Parse($status.next_run_at) }
    if ($candidate -gt [DateTimeOffset]::UtcNow) { $nextAt = $candidate }
}
$hourly = New-ScheduledTaskTrigger -Once -At $nextAt.UtcDateTime -RepetitionInterval (New-TimeSpan -Hours 1)
# CIM normalizes boundaries using Windows' actual timezone; supply its wall time
# and offset explicitly rather than relying on the shell process timezone.
$windowsZone = [TimeZoneInfo]::FindSystemTimeZoneById((Get-TimeZone).Id)
$hourly.StartBoundary = [TimeZoneInfo]::ConvertTime($nextAt, $windowsZone).ToString('yyyy-MM-ddTHH:mm:sszzz')
$login = New-ScheduledTaskTrigger -AtLogOn -User ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name)
$principal = New-ScheduledTaskPrincipal -UserId ([System.Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
$task = New-ScheduledTask -Action $action -Trigger @($hourly,$login) -Principal $principal -Settings $settings -Description "Moonwalking local chart pilot: $repoRoot"
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null
# Register the final boundary through XML: the CIM input-object path can replace
# its offset with the service timezone without converting the wall-clock hour.
[xml]$registeredXml = Export-ScheduledTask -TaskName $taskName
$boundary = $registeredXml.SelectSingleNode("//*[local-name()='TimeTrigger']/*[local-name()='StartBoundary']")
$boundary.InnerText = $nextAt.UtcDateTime.ToString("yyyy-MM-ddTHH:mm:ss'Z'")
Register-ScheduledTask -TaskName $taskName -Xml $registeredXml.OuterXml -Force | Out-Null
$actual = (Get-ScheduledTask -TaskName $taskName).Triggers | Where-Object StartBoundary | Select-Object -First 1
if ([Math]::Abs(([DateTimeOffset]::Parse($actual.StartBoundary) - $nextAt).TotalSeconds) -gt 1) {
    throw 'Registered schedule boundary differs from planned UTC time; inspect task before relying on it.'
}
Get-ScheduledTaskInfo -TaskName $taskName | Select-Object TaskName,LastRunTime,NextRunTime,LastTaskResult
