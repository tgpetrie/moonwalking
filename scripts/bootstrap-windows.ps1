[CmdletBinding()]
param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $repoRoot

if (-not (Test-Path (Join-Path $repoRoot ".git"))) {
    throw "Run this script from a Moonwalking Git checkout."
}

$origin = (git remote get-url origin).Trim()
if ($LASTEXITCODE -ne 0 -or $origin -notmatch "tgpetrie/moonwalking(?:\.git)?$") {
    throw "This checkout is not connected to the expected Moonwalking GitHub repository."
}

Write-Host "Moonwalking checkout: $repoRoot"
Write-Host "Origin: $origin"
git fetch --all --prune
git status --short --branch
git worktree list

$requiredDocs = @(
    "AGENTS.md",
    "CLAUDE.md",
    "docs/ai/AI_INDEX.md",
    "HANDOFF.md",
    "MW_BACKLOG.md"
)

$missingDocs = $requiredDocs | Where-Object { -not (Test-Path (Join-Path $repoRoot $_)) }
if ($missingDocs) {
    throw "Missing required project guidance: $($missingDocs -join ', ')"
}

if (-not $InstallDependencies) {
    Write-Host "Repository checks passed. Re-run with -InstallDependencies for first-time dependency setup."
    exit 0
}

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js is required. Install the current project-supported Node.js version, then rerun."
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    throw "npm is required."
}

$python = Get-Command py -ErrorAction SilentlyContinue
if ($python) {
    & py -3.12 -m venv .venv
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    & python -m venv .venv
} else {
    throw "Python is required. Python 3.12 is recommended for this project."
}

& .\.venv\Scripts\python.exe -m pip install --upgrade pip setuptools wheel
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
npm --prefix frontend ci

Write-Host "Dependency setup complete. Add local environment values using the checked-in example files; never commit secrets."
