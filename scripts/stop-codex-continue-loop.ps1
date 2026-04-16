[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$StopFile = ".tmp\codex-continue.stop",
  [string]$PidFile = ".tmp\codex-continue.pid",
  [switch]$Force
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-LoopPath([string]$Candidate) {
  if ([string]::IsNullOrWhiteSpace($Candidate)) {
    return $null
  }
  if ([System.IO.Path]::IsPathRooted($Candidate)) {
    return $Candidate
  }
  return Join-Path $repoRoot $Candidate
}

$stopPath = Resolve-LoopPath $StopFile
$pidPath = Resolve-LoopPath $PidFile

if ($stopPath) {
  $stopDir = Split-Path -Parent $stopPath
  if ($stopDir -and -not (Test-Path -LiteralPath $stopDir)) {
    New-Item -ItemType Directory -Path $stopDir -Force | Out-Null
  }
  Set-Content -LiteralPath $stopPath -Value "stop $(Get-Date -Format o)" -Encoding utf8
  Write-Host ("Stop file written: {0}" -f $stopPath)
}

if ($Force -and $pidPath -and (Test-Path -LiteralPath $pidPath)) {
  try {
    $pidValue = (Get-Content -LiteralPath $pidPath -ErrorAction Stop | Select-Object -First 1).Trim()
    if ($pidValue) {
      Stop-Process -Id ([int]$pidValue) -Force -ErrorAction Stop
      Write-Host ("Process stopped: {0}" -f $pidValue)
    }
  } catch {
    Write-Host ("Force stop skipped: {0}" -f $_.Exception.Message)
  }
}
