param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PytestArgs
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

if (-not $PytestArgs -or $PytestArgs.Count -eq 0) {
    $PytestArgs = @("backend\tests")
}

& $Python -m pytest @PytestArgs
exit $LASTEXITCODE
