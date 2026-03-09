param(
    [string]$Target = "."
)

$ErrorActionPreference = "Stop"
Write-Host "Running: python -m ruff check $Target"
& python -m ruff check $Target
exit $LASTEXITCODE
