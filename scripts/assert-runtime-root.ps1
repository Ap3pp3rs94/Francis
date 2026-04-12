[CmdletBinding()]
param(
  [Parameter(Mandatory = $false)]
  [string]$Root = ""
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

if (-not $Root) {
  $Root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
}

$markerPath = Join-Path $Root '.francis-mirror'
if (Test-Path -LiteralPath $markerPath) {
  $message = @"
This checkout is marked mirror-only and must not be used for runtime operations.
Primary runtime repo: C:\Francis
Current checkout: $Root
Marker: $markerPath
Remove the marker only if you intentionally promote this checkout.
"@
  Write-Error $message
  exit 64
}
