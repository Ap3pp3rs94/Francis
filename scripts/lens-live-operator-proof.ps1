[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 20,

  [string]$DataDir = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PythonPath {
  $WindowsVenv = Join-Path $RepoRoot '.venv\Scripts\python.exe'
  if (Test-Path -LiteralPath $WindowsVenv -PathType Leaf) {
    & $WindowsVenv --version *> $null
    if ($LASTEXITCODE -eq 0) {
      return $WindowsVenv
    }
  }

  $UnixVenv = Join-Path $RepoRoot '.venv/bin/python'
  if (Test-Path -LiteralPath $UnixVenv -PathType Leaf) {
    & $UnixVenv --version *> $null
    if ($LASTEXITCODE -eq 0) {
      return $UnixVenv
    }
  }

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -ne $Python) {
    return [string]$Python.Source
  }
  return ''
}

function Get-FreeTcpPort {
  $Address = [System.Net.IPAddress]::Parse('127.0.0.1')
  $Listener = [System.Net.Sockets.TcpListener]::new($Address, 0)
  try {
    $Listener.Start()
    return [int]$Listener.LocalEndpoint.Port
  } finally {
    $Listener.Stop()
  }
}

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  if ($Payload -is [System.Collections.IDictionary]) {
    if ($Payload.Contains($Name) -and $null -ne $Payload[$Name]) {
      return $Payload[$Name]
    }
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function Get-NestedPropertyValue {
  param(
    [object]$Payload,
    [string[]]$Path,
    [object]$Default = $null
  )

  $Current = $Payload
  foreach ($Name in $Path) {
    $Current = Get-PropertyValue -Payload $Current -Name $Name -Default $null
    if ($null -eq $Current) {
      return $Default
    }
  }
  return $Current
}

function ConvertTo-StringArray {
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence = '',
    [string]$Reason = ''
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = $Passed
    evidence = $Evidence
    reason = $Reason
  }
}

function Invoke-HttpJson {
  param([string]$Uri)

  try {
    $Payload = Invoke-RestMethod -Uri $Uri -Method Get -TimeoutSec 3
    return [ordered]@{
      ok = $true
      payload = $Payload
      error = ''
    }
  } catch {
    return [ordered]@{
      ok = $false
      payload = $null
      error = [string]$_.Exception.Message
    }
  }
}

function Wait-ForLensStatus {
  param(
    [System.Diagnostics.Process]$Process,
    [string]$Uri,
    [int]$TimeoutSeconds
  )

  $Deadline = (Get-Date).AddSeconds($TimeoutSeconds)
  $LastResult = [ordered]@{
    ok = $false
    payload = $null
    error = 'api_startup_timeout'
  }
  while ((Get-Date) -lt $Deadline) {
    if ($null -ne $Process -and $Process.HasExited) {
      return [ordered]@{
        ok = $false
        payload = $null
        error = 'api_process_exited_before_status_readback'
      }
    }
    $LastResult = Invoke-HttpJson -Uri $Uri
    if ([bool](Get-PropertyValue -Payload $LastResult -Name 'ok' -Default $false)) {
      $Payload = Get-PropertyValue -Payload $LastResult -Name 'payload'
      if ([string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '') -eq 'lens.status') {
        return $LastResult
      }
    }
    Start-Sleep -Milliseconds 250
  }
  return $LastResult
}

if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-live-operator-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)
$ProofRuntimeRoot = Join-Path $ProofDataRoot 'runtime\lens-live-operator-proof'
New-Item -ItemType Directory -Force -Path $ProofRuntimeRoot | Out-Null

$PythonPath = Get-PythonPath
$Port = Get-FreeTcpPort
$BaseUrl = "http://127.0.0.1:$Port"
$StatusUri = "$BaseUrl/lens/status?limit=5"
$StdoutPath = Join-Path $ProofRuntimeRoot 'api-stdout.log'
$StderrPath = Join-Path $ProofRuntimeRoot 'api-stderr.log'

$ApiProcess = $null
$Started = $false
$StatusResult = [ordered]@{
  ok = $false
  payload = $null
  error = 'api_not_started'
}
$ApiExitCode = $null
$ApiStdout = ''
$ApiStderr = ''

try {
  if (-not [string]::IsNullOrWhiteSpace($PythonPath)) {
    $StartInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $StartInfo.FileName = $PythonPath
    $StartInfo.Arguments = "-m francis api --host 127.0.0.1 --port $Port"
    $StartInfo.WorkingDirectory = $RepoRoot
    $StartInfo.UseShellExecute = $false
    $StartInfo.CreateNoWindow = $true
    $StartInfo.RedirectStandardOutput = $true
    $StartInfo.RedirectStandardError = $true
    $SrcPath = Join-Path $RepoRoot 'src'
    $PreviousPythonPath = [string]$env:PYTHONPATH
    if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
      $StartInfo.EnvironmentVariables['PYTHONPATH'] = $SrcPath
    } else {
      $StartInfo.EnvironmentVariables['PYTHONPATH'] = "$SrcPath$([System.IO.Path]::PathSeparator)$PreviousPythonPath"
    }
    $StartInfo.EnvironmentVariables['FRANCIS_DATA_DIR'] = $ProofDataRoot

    $ApiProcess = [System.Diagnostics.Process]::new()
    $ApiProcess.StartInfo = $StartInfo
    $Started = $ApiProcess.Start()
    $StatusResult = Wait-ForLensStatus -Process $ApiProcess -Uri $StatusUri -TimeoutSeconds $StartupTimeoutSeconds
  }
} finally {
  if ($null -ne $ApiProcess) {
    if (-not $ApiProcess.HasExited) {
      try {
        $ApiProcess.Kill()
      } catch {
      }
      $ApiProcess.WaitForExit(5000) | Out-Null
    }
    try {
      $ApiExitCode = $ApiProcess.ExitCode
    } catch {
      $ApiExitCode = $null
    }
    try {
      $ApiStdout = $ApiProcess.StandardOutput.ReadToEnd()
    } catch {
      $ApiStdout = ''
    }
    try {
      $ApiStderr = $ApiProcess.StandardError.ReadToEnd()
    } catch {
      $ApiStderr = ''
    }
    Set-Content -LiteralPath $StdoutPath -Value $ApiStdout -Encoding UTF8
    Set-Content -LiteralPath $StderrPath -Value $ApiStderr -Encoding UTF8
  }
}

$StatusPayload = Get-PropertyValue -Payload $StatusResult -Name 'payload'
$Hud = Get-PropertyValue -Payload $StatusPayload -Name 'hud'
$HudRuntime = Get-PropertyValue -Payload $Hud -Name 'runtime'
$CommandPalette = Get-PropertyValue -Payload $StatusPayload -Name 'command_palette'
$ModeSelector = Get-PropertyValue -Payload $StatusPayload -Name 'mode_selector'
$ApprovalsView = Get-PropertyValue -Payload $StatusPayload -Name 'approvals_view'
$IncidentView = Get-PropertyValue -Payload $StatusPayload -Name 'incident_view'
$MissionFeed = Get-PropertyValue -Payload $StatusPayload -Name 'mission_feed'
$Receipts = Get-PropertyValue -Payload $StatusPayload -Name 'receipts'
$PilotIndicator = Get-PropertyValue -Payload $StatusPayload -Name 'pilot_indicator'
$ResidentHost = Get-PropertyValue -Payload $StatusPayload -Name 'resident_host'
$ResidentSurface = Get-PropertyValue -Payload $StatusPayload -Name 'resident_surface'
$ResidentSurfaceActivation = Get-PropertyValue -Payload $StatusPayload -Name 'resident_surface_activation'
$ResidentSurfaceGovernance = Get-PropertyValue -Payload $ResidentSurface -Name 'governance'
$Governance = Get-PropertyValue -Payload $StatusPayload -Name 'governance'

$HttpStatusReadback = (
  [bool](Get-PropertyValue -Payload $StatusResult -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $StatusPayload -Name 'kind' -Default '') -eq 'lens.status' -and
  [bool](Get-PropertyValue -Payload $StatusPayload -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $StatusPayload -Name 'read_only' -Default $false)
)
$HudReadback = (
  [bool](Get-PropertyValue -Payload $Hud -Name 'readback_ready' -Default $false) -and
  [string](Get-PropertyValue -Payload $HudRuntime -Name 'claim' -Default '') -eq 'chat_ui_hud_readback_only' -and
  -not [bool](Get-PropertyValue -Payload $HudRuntime -Name 'resident_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HudRuntime -Name 'always_on_top' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HudRuntime -Name 'global_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HudRuntime -Name 'tray_presence' -Default $true)
)
$PaletteReadback = (
  [string](Get-PropertyValue -Payload $CommandPalette -Name 'status' -Default '') -eq 'readback_ready' -and
  [string](Get-PropertyValue -Payload $CommandPalette -Name 'availability' -Default '') -eq 'chat_ui_only' -and
  [int](Get-PropertyValue -Payload $CommandPalette -Name 'command_total' -Default 0) -gt 0 -and
  -not [bool](Get-PropertyValue -Payload $CommandPalette -Name 'summon_anywhere' -Default $true)
)
$ModePilotReadback = (
  [string](Get-PropertyValue -Payload $ModeSelector -Name 'status' -Default '') -eq 'readback_ready' -and
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $ModeSelector -Name 'active_mode' -Default '')) -and
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $PilotIndicator -Name 'status' -Default ''))
)
$OperatorViewsReadback = (
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $ApprovalsView -Name 'status' -Default '')) -and
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $IncidentView -Name 'status' -Default '')) -and
  -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Payload $MissionFeed -Name 'headline' -Default '')) -and
  [string](Get-PropertyValue -Payload $Receipts -Name 'status' -Default '') -eq 'readback_ready'
)
$ResidentClaimBlocked = (
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'kind' -Default '') -eq 'lens.resident_surface.readback' -and
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $ResidentSurface -Name 'contract_status' -Default '') -eq 'readback_ready' -and
  [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'content_contract_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'resident_overlay_runtime' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'resident_claim_authority' -Default $true) -and
  [bool](Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'boundary_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'activation_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHost -Name 'resident' -Default $true)
)
$AuthorityBoundary = (
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $Governance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $CommandPalette -Path @('governance', 'mutation_authority_granted') -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $ResidentSurfaceActivation -Path @('governance', 'execution_authority') -Default $true) -and
  -not [bool](Get-NestedPropertyValue -Payload $HudRuntime -Path @('governance', 'overlay_control_authority') -Default $true)
)
$NotNoisyBoundary = (
  $HudReadback -and
  $PaletteReadback -and
  $AuthorityBoundary -and
  -not [bool](Get-PropertyValue -Payload $HudRuntime -Name 'os_level' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'operator_experience_proof' -Default $true)
)
$ProofPassed = (
  $Started -and
  $HttpStatusReadback -and
  $HudReadback -and
  $PaletteReadback -and
  $ModePilotReadback -and
  $OperatorViewsReadback -and
  $ResidentClaimBlocked -and
  $AuthorityBoundary -and
  $NotNoisyBoundary
)

$Checks = @(
  (New-Check -Id 'python_runtime' -Status $(if ($PythonPath) { 'present' } else { 'missing' }) -Passed (-not [string]::IsNullOrWhiteSpace($PythonPath)) -Evidence $PythonPath -Reason 'Python is required to start the Francis API proof server.')
  (New-Check -Id 'api_process_started' -Status $(if ($Started) { 'started' } else { 'missing' }) -Passed $Started -Evidence 'python -m francis api' -Reason 'The proof must read Lens through a live local HTTP API process.')
  (New-Check -Id 'http_lens_status_readback' -Status $(if ($HttpStatusReadback) { 'readback_ready' } else { 'failed' }) -Passed $HttpStatusReadback -Evidence '/lens/status?limit=5' -Reason 'The operator surface consumes Lens through the API route, not an internal function call.')
  (New-Check -Id 'hud_runtime_readback' -Status $(if ($HudReadback) { 'readback_only' } else { 'failed' }) -Passed $HudReadback -Evidence 'hud.runtime' -Reason 'HUD state must be useful while clearly not claiming resident overlay runtime.')
  (New-Check -Id 'command_palette_readback' -Status $(if ($PaletteReadback) { 'chat_ui_only' } else { 'failed' }) -Passed $PaletteReadback -Evidence 'command_palette' -Reason 'Command palette data must be available without OS-wide summon claims.')
  (New-Check -Id 'mode_and_pilot_visibility' -Status $(if ($ModePilotReadback) { 'readback_ready' } else { 'failed' }) -Passed $ModePilotReadback -Evidence 'mode_selector,pilot_indicator' -Reason 'Mode and Pilot indicator visibility must be legible through Lens.')
  (New-Check -Id 'operator_views_readback' -Status $(if ($OperatorViewsReadback) { 'readback_ready' } else { 'failed' }) -Passed $OperatorViewsReadback -Evidence 'approvals,incidents,missions,receipts' -Reason 'Lens must surface the core operator work lanes from one status payload.')
  (New-Check -Id 'resident_claim_boundary' -Status $(if ($ResidentClaimBlocked) { 'blocked' } else { 'unexpected_claim' }) -Passed $ResidentClaimBlocked -Evidence 'resident_surface_activation' -Reason 'The proof must not turn readback into a resident Lens claim.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'blocked' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'governance' -Reason 'The live operator proof must not grant execution, approval, memory, overlay, sensing, or summon authority.')
  (New-Check -Id 'helpful_not_noisy_boundary' -Status $(if ($NotNoisyBoundary) { 'readback_ready' } else { 'failed' }) -Passed $NotNoisyBoundary -Evidence 'hud,command_palette,governance' -Reason 'The visible Lens readback is useful while avoiding overlay spam, summon claims, and hidden authority.')
)

$Blockers = @(
  'resident_surface_runtime_missing',
  'resident_host_process_missing',
  'resident_overlay_runtime_missing',
  'tray_presence_missing',
  'global_hotkey_binding_missing',
  'summon_anywhere_missing'
)
if (-not $ProofPassed) {
  $Blockers += 'operator_experience_proof_missing'
}
$Blockers = @($Blockers | Sort-Object -Unique)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.live_operator_experience.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  base_url = $BaseUrl
  status_route = '/lens/status?limit=5'
  live_http_status_readback = $HttpStatusReadback
  operator_experience_proof = $ProofPassed
  helpful_not_noisy_readback = $NotNoisyBoundary
  live_operator_experience_ready = $false
  ready_for_stage6_closure = $false
  resident_surface_ready = $false
  resident_surface_content_readback = $ResidentClaimBlocked
  resident_claim_allowed = $false
  checks = @($Checks)
  blockers = @($Blockers)
  proof = [ordered]@{
    api_pid = if ($null -ne $ApiProcess) { $ApiProcess.Id } else { 0 }
    api_exit_code = $ApiExitCode
    api_stdout_path = $StdoutPath
    api_stderr_path = $StderrPath
    status_error = [string](Get-PropertyValue -Payload $StatusResult -Name 'error' -Default '')
    lens_status = [string](Get-PropertyValue -Payload $StatusPayload -Name 'status' -Default '')
    hud_status = [string](Get-PropertyValue -Payload $Hud -Name 'status' -Default '')
    hud_runtime_status = [string](Get-PropertyValue -Payload $HudRuntime -Name 'status' -Default '')
    hud_runtime_claim = [string](Get-PropertyValue -Payload $HudRuntime -Name 'claim' -Default '')
    command_total = [int](Get-PropertyValue -Payload $CommandPalette -Name 'command_total' -Default 0)
    command_palette_availability = [string](Get-PropertyValue -Payload $CommandPalette -Name 'availability' -Default '')
    mode = [string](Get-PropertyValue -Payload $ModeSelector -Name 'active_mode' -Default '')
    pilot_status = [string](Get-PropertyValue -Payload $PilotIndicator -Name 'status' -Default '')
    approvals_status = [string](Get-PropertyValue -Payload $ApprovalsView -Name 'status' -Default '')
    incident_status = [string](Get-PropertyValue -Payload $IncidentView -Name 'status' -Default '')
    receipt_status = [string](Get-PropertyValue -Payload $Receipts -Name 'status' -Default '')
    resident_surface_status = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'status' -Default '')
    resident_surface_contract_status = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'contract_status' -Default '')
    resident_surface_activation_status = [string](Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'status' -Default '')
    resident_surface_route = [string](Get-PropertyValue -Payload $ResidentSurface -Name 'route' -Default '')
    resident_surface_content_contract_ready = [bool](Get-PropertyValue -Payload $ResidentSurface -Name 'content_contract_ready' -Default $false)
    resident_surface_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentSurfaceActivation -Name 'blockers' -Default @())
  }
  governance = [ordered]@{
    diagnostic_only = $true
    live_http_readback = $true
    temporary_api_process = $true
    temporary_runtime_state_write = $true
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    telemetry_authority = $false
    local_process_launch_authority = $false
    api_local_process_launch_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    mutation_authority_granted = $false
  }
  next_smallest_truthful_gap = 'resident_surface_runtime_missing'
  message = 'Lens operator readback is proven through a live local HTTP API process; this does not create a resident host, tray presence, hotkey, overlay, summon-anywhere behavior, telemetry, memory writes, or execution authority.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
