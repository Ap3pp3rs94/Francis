param(
  [string]$HudUrl = "http://127.0.0.1:8767"
)

$ErrorActionPreference = "Stop"

function Test-HudReachable {
  param(
    [Parameter(Mandatory = $true)]
    [string]$Url
  )

  try {
    $null = Invoke-WebRequest -Uri $Url -Method Head -TimeoutSec 3 -UseBasicParsing
    return $true
  } catch {
    try {
      $null = Invoke-WebRequest -Uri $Url -TimeoutSec 3 -UseBasicParsing
      return $true
    } catch {
      return $false
    }
  }
}

Write-Host "[francis-overlay] Checking HUD server at $HudUrl"

if (-not (Test-HudReachable -Url $HudUrl)) {
  Write-Host "[francis-overlay] HUD server is not reachable." -ForegroundColor Yellow
  Write-Host "[francis-overlay] Start the HUD server first, then rerun this script." -ForegroundColor Yellow
  exit 1
}

Write-Host "[francis-overlay] HUD server is reachable. Launching Electron overlay..."
$env:FRANCIS_HUD_URL = $HudUrl
npm run overlay:start
