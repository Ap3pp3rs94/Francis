param(
  [string]$HudUrl = "http://127.0.0.1:8767",
  [switch]$DisableManagedHud
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

if (Test-HudReachable -Url $HudUrl) {
  Write-Host "[francis-overlay] HUD server is already reachable. Launching overlay..."
} else {
  Write-Host "[francis-overlay] HUD server is not reachable." -ForegroundColor Yellow
  if ($DisableManagedHud) {
    Write-Host "[francis-overlay] Managed HUD startup is disabled, so the overlay cannot recover this automatically." -ForegroundColor Yellow
    exit 1
  }
  Write-Host "[francis-overlay] The Electron shell will attempt to start the HUD locally." -ForegroundColor Yellow
}

$env:FRANCIS_HUD_URL = $HudUrl
$env:FRANCIS_OVERLAY_MANAGE_HUD = if ($DisableManagedHud) { "0" } else { "1" }
npm run overlay:start
