param(
    [int]$X = 320,
    [int]$Y = 240,
    [string]$Text = "Francis Orb dry-run"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

Push-Location $RepoRoot
try {
    & $Python -m francis.input_actuator.orb_operator --mode dry_run --x $X --y $Y --text $Text
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
