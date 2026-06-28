# Runs Francis's bounded read-only overnight explorer from source.

[CmdletBinding(PositionalBinding = $false)]
param(
  [double]$DurationHours = 8.0,
  [double]$IntervalMinutes = 20.0,
  [int]$MaxFindings = 40,
  [int]$MaxScanFiles = 900,
  [int]$MaxCycles = 200,
  [switch]$Once,
  [switch]$Stream,
  [switch]$Detached,
  [switch]$Status,
  [switch]$Stop,
  [switch]$ClearStopFlag
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$srcPath = Join-Path $repoRoot 'src'

& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $repoRoot

$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'
function Test-VenvPython([string]$Path) {
  if (-not (Test-Path -LiteralPath $Path)) { return $false }
  & $Path --version *> $null
  return ($LASTEXITCODE -eq 0)
}
$python = if (Test-VenvPython $venvPy) { $venvPy } else { 'python' }

$pythonArgs = @(
  '-m', 'francis',
  'overnight-explore',
  '--duration-hours', ([string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0}', $DurationHours)),
  '--interval-minutes', ([string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0}', $IntervalMinutes)),
  '--max-findings', ([string]$MaxFindings),
  '--max-scan-files', ([string]$MaxScanFiles),
  '--max-cycles', ([string]$MaxCycles)
)

if ($Once) { $pythonArgs += '--once' }
if ($Stream) { $pythonArgs += '--stream' }
if ($Status) { $pythonArgs += '--status' }
if ($Stop) { $pythonArgs += '--stop' }
if ($ClearStopFlag) { $pythonArgs += '--clear-stop-flag' }

$previousPythonPath = $env:PYTHONPATH
try {
  if ($previousPythonPath) {
    $env:PYTHONPATH = "$srcPath;$previousPythonPath"
  } else {
    $env:PYTHONPATH = $srcPath
  }

  if ($Detached -and -not $Status -and -not $Stop) {
    $shellCommand = Get-Command pwsh -ErrorAction SilentlyContinue
    $shell = if ($shellCommand) { $shellCommand.Source } else { 'powershell' }
    $scriptArgs = @(
      '-NoExit',
      '-NoProfile',
      '-ExecutionPolicy', 'Bypass',
      '-File', $PSCommandPath,
      '-DurationHours', ([string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0}', $DurationHours)),
      '-IntervalMinutes', ([string]::Format([Globalization.CultureInfo]::InvariantCulture, '{0}', $IntervalMinutes)),
      '-MaxFindings', ([string]$MaxFindings),
      '-MaxScanFiles', ([string]$MaxScanFiles),
      '-MaxCycles', ([string]$MaxCycles),
      '-Stream'
    )
    if ($ClearStopFlag) { $scriptArgs += '-ClearStopFlag' }

    $process = Start-Process `
      -FilePath $shell `
      -ArgumentList $scriptArgs `
      -WorkingDirectory $repoRoot `
      -WindowStyle Normal `
      -PassThru

    [ordered]@{
      ok = $true
      status = 'started_visible'
      pid = $process.Id
      command = "$shell $($scriptArgs -join ' ')"
      user_facing = $true
      stream = $true
      status_command = '.\scripts\francis-overnight-explorer.ps1 -Status'
      stop_command = '.\scripts\francis-overnight-explorer.ps1 -Stop'
    } | ConvertTo-Json -Depth 5
    exit 0
  }

  Push-Location $repoRoot
  try {
    & $python @pythonArgs
    exit $LASTEXITCODE
  } finally {
    Pop-Location
  }
} finally {
  $env:PYTHONPATH = $previousPythonPath
}
