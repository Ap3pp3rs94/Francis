# Starts the local Francis MCP endpoint for a ChatGPT developer-mode connector.
# This does not expose Francis to the public internet. Use an explicit HTTPS
# tunnel separately when you are ready to connect ChatGPT web/mobile.

[CmdletBinding(PositionalBinding = $false)]
param(
  [string]$HostAddress = '127.0.0.1',
  [int]$Port = 8787,
  [string]$Path = '/mcp',
  [switch]$StatusOnly
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$srcPath = Join-Path $repoRoot 'src'
$venvPy = Join-Path $repoRoot '.venv\Scripts\python.exe'

function Test-VenvPython([string]$PathValue) {
  if (-not (Test-Path -LiteralPath $PathValue)) { return $false }
  & $PathValue --version *> $null
  return ($LASTEXITCODE -eq 0)
}

$python = if (Test-VenvPython $venvPy) { $venvPy } else { 'python' }
$endpoint = "http://$HostAddress`:$Port$Path"

Write-Host "Francis ChatGPT voice MCP endpoint: $endpoint"
Write-Host "ChatGPT requires an HTTPS URL ending in $Path. Expose this local endpoint with a tunnel only when intended."

if ($StatusOnly) {
  $listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Select-Object -First 1 LocalAddress,LocalPort,OwningProcess
  if ($listener) {
    $listener | Format-List
    exit 0
  }
  Write-Host "No listener is active on port $Port."
  exit 1
}

$prevPythonPath = $env:PYTHONPATH
$prevActorScopes = $env:FRANCIS_API_ACTOR_SCOPES
try {
  if ($prevPythonPath) {
    $env:PYTHONPATH = "$srcPath;$prevPythonPath"
  } else {
    $env:PYTHONPATH = $srcPath
  }
  $env:FRANCIS_API_ACTOR_SCOPES = '{"chatgpt.voice":["chatgpt.voice.bridge.read","chatgpt.voice.bridge.write","chat.write"]}'

  Push-Location $repoRoot
  try {
    & $python -m francis.mcp_gateway.server --transport streamable-http --host $HostAddress --port $Port --path $Path
    exit $LASTEXITCODE
  } finally {
    Pop-Location
  }
} finally {
  $env:PYTHONPATH = $prevPythonPath
  $env:FRANCIS_API_ACTOR_SCOPES = $prevActorScopes
}
