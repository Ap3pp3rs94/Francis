# Thin wrapper to run Francis from source without requiring an editable install.
# - Ensures repo root is the working directory.
# - Prepends `src` to PYTHONPATH for the invoked process.
#
# Usage:
#   .\scripts\francis.ps1 doctor
#   .\scripts\francis.ps1 api --host 127.0.0.1 --port 8000
#   .\scripts\francis.ps1 supervised-exec --cmd "echo hello" --print-summary

[CmdletBinding(PositionalBinding = $false)]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Args
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$srcPath = (Join-Path $repoRoot 'src')

# Prefer repo venv if present and working; fall back to system python.
$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'
function Test-VenvPython([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $false }
  & $Path --version *> $null
  return ($LASTEXITCODE -eq 0)
}
$python = if (Test-VenvPython $venvPy) { $venvPy } else { 'python' }

$prevPythonPath = $env:PYTHONPATH
try {
  if ($prevPythonPath) {
    $env:PYTHONPATH = "$srcPath;$prevPythonPath"
  } else {
    $env:PYTHONPATH = "$srcPath"
  }

  Push-Location $repoRoot
  try {
    & $python -m francis @Args
    exit $LASTEXITCODE
  } finally {
    Pop-Location
  }
} finally {
  $env:PYTHONPATH = $prevPythonPath
}
