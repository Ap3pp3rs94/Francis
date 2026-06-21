param(
  [Parameter(Mandatory = $true)]
  [string]$Task,

  [Parameter(Mandatory = $true)]
  [string]$ContextPath,

  [Parameter(Mandatory = $true)]
  [string]$WorkerId,

  [string]$DroneId = 'drone-1',

  [string]$Model = '',

  [string]$StateRoot = '.francis\local-drones',

  [ValidateRange(1000, 24000)]
  [int]$MaxContextChars = 24000,

  [switch]$NoModelCall
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Resolve-LocalDronePath {
  param([string]$PathText)

  if ([System.IO.Path]::IsPathRooted($PathText)) {
    return [System.IO.Path]::GetFullPath($PathText)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $PathText))
}

$ResolvedContextPath = Resolve-LocalDronePath -PathText $ContextPath
if (-not (Test-Path -LiteralPath $ResolvedContextPath -PathType Leaf)) {
  throw "ContextPath does not exist: $ResolvedContextPath"
}

$ResolvedStateRoot = Resolve-LocalDronePath -PathText $StateRoot
$Python = Join-Path $RepoRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
  $Python = (Get-Command python -ErrorAction Stop).Source
}

$EffectiveModel = if ([string]::IsNullOrWhiteSpace($Model)) {
  if ([string]::IsNullOrWhiteSpace($env:FRANCIS_LOCAL_DRONE_MODEL)) {
    'llama3.2:3b'
  } else {
    $env:FRANCIS_LOCAL_DRONE_MODEL
  }
} else {
  $Model
}

$Args = @(
  '-m',
  'francis.workers.local_drone',
  '--task',
  $Task,
  '--context-path',
  $ResolvedContextPath,
  '--worker-id',
  $WorkerId,
  '--drone-id',
  $DroneId,
  '--state-root',
  $ResolvedStateRoot,
  '--model',
  $EffectiveModel,
  '--max-context-chars',
  ([string]$MaxContextChars)
)

if ($NoModelCall) {
  $Args += '--no-model-call'
}

& $Python @Args
