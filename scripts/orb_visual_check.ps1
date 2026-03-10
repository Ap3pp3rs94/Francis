param(
    [string]$Url = "http://127.0.0.1:8767",
    [string]$Output = "output/playwright/orb-check.png",
    [switch]$Headed
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$playwright = Join-Path $PSScriptRoot "playwright.ps1"
$resolvedOutput = Join-Path $repoRoot $Output
$outputDir = Split-Path -Parent $resolvedOutput

New-Item -ItemType Directory -Force $outputDir | Out-Null

$openArgs = @("open", $Url)
if ($Headed) {
    $openArgs += "--headed"
}

try {
    & $playwright @openArgs
    Start-Sleep -Milliseconds 1200
    & $playwright screenshot --filename $resolvedOutput
}
finally {
    & $playwright close | Out-Null
}
