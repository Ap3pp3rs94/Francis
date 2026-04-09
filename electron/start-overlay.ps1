param(
  [switch]$Wait
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$electronExe = Join-Path $repoRoot "node_modules\electron\dist\electron.exe"

if (-not (Test-Path -LiteralPath $electronExe)) {
  throw "Electron runtime not found at '$electronExe'. Run 'npm install' from the repo root first."
}

$startInfo = @{
  FilePath         = $electronExe
  ArgumentList     = @(".")
  WorkingDirectory = $repoRoot
  WindowStyle      = "Hidden"
  PassThru         = $true
}

$process = Start-Process @startInfo

if (-not $process) {
  throw "Failed to launch the Francis overlay shell."
}

if ($Wait) {
  Wait-Process -Id $process.Id
} else {
  Write-Output "Francis overlay launched without a console host (PID $($process.Id))."
}
