[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 60)]
  [int]$StartupTimeoutSeconds = 30,

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 20,

  [string]$DataDir = '',

  [string]$ApprovalId = '',

  [string]$Actor = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-PowerShellPath {
  try {
    $Current = Get-Process -Id $PID -ErrorAction Stop
    if (-not [string]::IsNullOrWhiteSpace([string]$Current.Path)) {
      return [string]$Current.Path
    }
  } catch {
  }

  $Pwsh = Get-Command pwsh -ErrorAction SilentlyContinue
  if ($null -ne $Pwsh) {
    return [string]$Pwsh.Source
  }
  $WindowsPowerShell = Get-Command powershell -ErrorAction SilentlyContinue
  if ($null -ne $WindowsPowerShell) {
    return [string]$WindowsPowerShell.Source
  }
  return ''
}

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

function Invoke-JsonScript {
  param(
    [string]$PowerShellPath,
    [string]$ScriptPath,
    [string[]]$ScriptArgs = @()
  )

  if ([string]::IsNullOrWhiteSpace($PowerShellPath) -or -not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
  $ExitCode = $LASTEXITCODE
  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $ExitCode
    payload = $Payload
    output = $Text
  }
}

function Invoke-ActivationBoundary {
  param(
    [string]$PythonPath,
    [string]$ProofDataRoot,
    [string]$SelectedApprovalId,
    [string]$SelectedActor
  )

  if ([string]::IsNullOrWhiteSpace($PythonPath)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $Source = @'
import json
import sys

from francis.lens.activation import lens_resident_surface_activation_boundary

approval_id = sys.argv[1] if len(sys.argv) > 1 else ""
actor = sys.argv[2] if len(sys.argv) > 2 else ""
print(json.dumps(lens_resident_surface_activation_boundary(approval_id=approval_id, actor=actor, limit=5)))
'@

  $PreviousDataDir = [string]$env:FRANCIS_DATA_DIR
  $TempSourcePath = ''
  try {
    if (-not [string]::IsNullOrWhiteSpace($ProofDataRoot)) {
      $env:FRANCIS_DATA_DIR = $ProofDataRoot
    }
    $TempSourcePath = [System.IO.Path]::GetTempFileName()
    Set-Content -LiteralPath $TempSourcePath -Value $Source -Encoding ASCII
    $Output = & $PythonPath $TempSourcePath $SelectedApprovalId $SelectedActor 2>&1
    $ExitCode = $LASTEXITCODE
  } finally {
    if (-not [string]::IsNullOrWhiteSpace($TempSourcePath) -and (Test-Path -LiteralPath $TempSourcePath -PathType Leaf)) {
      Remove-Item -LiteralPath $TempSourcePath -ErrorAction SilentlyContinue
    }
    if ([string]::IsNullOrWhiteSpace($PreviousDataDir)) {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    } else {
      $env:FRANCIS_DATA_DIR = $PreviousDataDir
    }
  }

  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $ExitCode
    payload = $Payload
    output = $Text
  }
}

function New-Check {
  param(
    [string]$Id,
    [string]$Status,
    [bool]$Passed,
    [string]$Evidence,
    [string]$Reason
  )

  return [ordered]@{
    id = $Id
    status = $Status
    passed = $Passed
    evidence = $Evidence
    reason = $Reason
  }
}

$PowerShellPath = Get-PowerShellPath
$PythonPath = Get-PythonPath
$ProofDataRoot = ''
if ([string]::IsNullOrWhiteSpace($DataDir)) {
  $DataDir = Join-Path ([System.IO.Path]::GetTempPath()) ("francis-lens-overlay-activation-proof\" + [guid]::NewGuid().ToString('N') + "\data")
}
$ProofDataRoot = [System.IO.Path]::GetFullPath($DataDir)

$LiveOperatorProofPath = Join-Path $PSScriptRoot 'lens-live-operator-proof.ps1'
$ResidentOverlayRuntimeProofPath = Join-Path $PSScriptRoot 'lens-resident-overlay-runtime-proof.ps1'

$LiveArgs = @('-Mode', 'Status', '-StartupTimeoutSeconds', [string]$StartupTimeoutSeconds)
if (-not [string]::IsNullOrWhiteSpace($ProofDataRoot)) {
  $LiveArgs += @('-DataDir', $ProofDataRoot)
}
$OverlayArgs = @('-Mode', 'Status', '-SupervisorRunSeconds', [string]$SupervisorRunSeconds)
if (-not [string]::IsNullOrWhiteSpace($ProofDataRoot)) {
  $OverlayArgs += @('-DataDir', $ProofDataRoot)
}

$LiveResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $LiveOperatorProofPath -ScriptArgs $LiveArgs
$OverlayResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ResidentOverlayRuntimeProofPath -ScriptArgs $OverlayArgs
$ActivationResult = Invoke-ActivationBoundary -PythonPath $PythonPath -ProofDataRoot $ProofDataRoot -SelectedApprovalId $ApprovalId -SelectedActor $Actor

$LivePayload = Get-PropertyValue -Payload $LiveResult -Name 'payload'
$OverlayPayload = Get-PropertyValue -Payload $OverlayResult -Name 'payload'
$ActivationPayload = Get-PropertyValue -Payload $ActivationResult -Name 'payload'
$LiveGovernance = Get-PropertyValue -Payload $LivePayload -Name 'governance'
$OverlayGovernance = Get-PropertyValue -Payload $OverlayPayload -Name 'governance'
$ActivationGovernance = Get-PropertyValue -Payload $ActivationPayload -Name 'governance'
$ActivationExecution = Get-PropertyValue -Payload $ActivationPayload -Name 'execution'
$ActivationSurface = Get-PropertyValue -Payload $ActivationPayload -Name 'surface'
$ActivationApproval = Get-PropertyValue -Payload $ActivationPayload -Name 'approval'

$LiveProofPassed = (
  [int](Get-PropertyValue -Payload $LiveResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $LivePayload -Name 'kind' -Default '') -eq 'lens.live_operator_experience.proof' -and
  [string](Get-PropertyValue -Payload $LivePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $LivePayload -Name 'operator_experience_proof' -Default $false) -and
  [bool](Get-PropertyValue -Payload $LivePayload -Name 'helpful_not_noisy_readback' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $LivePayload -Name 'ready_for_stage6_closure' -Default $true)
)
$OverlayBoundaryObserved = (
  [int](Get-PropertyValue -Payload $OverlayResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $OverlayPayload -Name 'kind' -Default '') -eq 'lens.resident_overlay_runtime.proof' -and
  [string](Get-PropertyValue -Payload $OverlayPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'bounded_supervisor_observed' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'resident_overlay_runtime_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'ready_for_lens_resident_claim' -Default $true)
)
$ActivationBoundaryBlocked = (
  [int](Get-PropertyValue -Payload $ActivationResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ActivationPayload -Name 'kind' -Default '') -eq 'lens.resident_surface.activation_boundary' -and
  [string](Get-PropertyValue -Payload $ActivationPayload -Name 'status' -Default '') -eq 'blocked' -and
  [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'boundary_ready' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'activation_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'ready_for_lens_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'resident_claim_allowed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'execution_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'executed' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationPayload -Name 'applied' -Default $true)
)
$ActivationPlanDenied = (
  $ActivationBoundaryBlocked -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_launch_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_install_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_open_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationExecution -Name 'would_decide_approval' -Default $true)
)
$AuthorityBoundary = (
  [bool](Get-PropertyValue -Payload $LiveGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayGovernance -Name 'bounded_supervisor_observation' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'activation_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'receipt_write_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ActivationGovernance -Name 'denial_receipt_write_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'live_operator_readback_proof' -Status $(if ($LiveProofPassed) { 'proof_passed' } else { 'failed' }) -Passed $LiveProofPassed -Evidence 'scripts/lens-live-operator-proof.ps1 -Mode Status' -Reason 'Activation boundary proof should run after live Lens readback is observable.')
  (New-Check -Id 'resident_overlay_runtime_boundary' -Status $(if ($OverlayBoundaryObserved) { 'boundary_observed' } else { 'failed' }) -Passed $OverlayBoundaryObserved -Evidence 'scripts/lens-resident-overlay-runtime-proof.ps1 -Mode Status' -Reason 'The resident overlay runtime boundary must be observed before activation can be discussed.')
  (New-Check -Id 'activation_boundary_blocked' -Status $(if ($ActivationBoundaryBlocked) { 'blocked' } else { 'unexpected_activation' }) -Passed $ActivationBoundaryBlocked -Evidence 'lens_resident_surface_activation_boundary' -Reason 'Resident overlay activation remains blocked and cannot become a resident claim.')
  (New-Check -Id 'activation_plan_denied' -Status $(if ($ActivationPlanDenied) { 'no_activation_actions' } else { 'unexpected_plan' }) -Passed $ActivationPlanDenied -Evidence 'activation.execution' -Reason 'The activation boundary must not launch, install, start, open overlay, register hotkey, write memory, or decide approvals.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'proof.governance + activation.governance' -Reason 'The proof must not grant activation, execution, approval, service, tray, hotkey, overlay, summon, capture, receipt, or memory authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$AllBlockers = @(
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $LivePayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayPayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ActivationPayload -Name 'blockers' -Default @())) +
  @(
    'resident_overlay_activation_not_authorized',
    'resident_overlay_runtime_missing',
    'resident_host_process_not_supervised',
    'overlay_window_missing',
    'tray_presence_missing',
    'global_hotkey_binding_missing',
    'summon_anywhere_missing'
  ) | Sort-Object -Unique
)
if ($LiveProofPassed) {
  $AllBlockers = @($AllBlockers | Where-Object {
      $_ -ne 'operator_experience_proof_missing' -and $_ -ne 'live_operator_experience_proof_missing'
    })
}

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_overlay_activation_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  data_root = $ProofDataRoot
  startup_timeout_seconds = $StartupTimeoutSeconds
  supervisor_run_seconds = $SupervisorRunSeconds
  live_operator_experience_proof = $LiveProofPassed
  resident_overlay_boundary_observed = $OverlayBoundaryObserved
  activation_boundary_observed = $ActivationBoundaryBlocked
  resident_overlay_activation_ready = $false
  activation_ready = $false
  resident_surface_ready = $false
  resident_overlay_runtime_ready = $false
  ready_for_lens_resident_claim = $false
  resident_claim_allowed = $false
  execution_ready = $false
  executed = $false
  applied = $false
  would_launch_process = $false
  would_install_service = $false
  would_start_service = $false
  would_register_hotkey = $false
  would_open_overlay = $false
  would_write_memory = $false
  would_decide_approval = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  proof = [ordered]@{
    live_operator_status = [string](Get-PropertyValue -Payload $LivePayload -Name 'status' -Default '')
    live_http_status_readback = [bool](Get-PropertyValue -Payload $LivePayload -Name 'live_http_status_readback' -Default $false)
    helpful_not_noisy_readback = [bool](Get-PropertyValue -Payload $LivePayload -Name 'helpful_not_noisy_readback' -Default $false)
    overlay_runtime_status = [string](Get-PropertyValue -Payload $OverlayPayload -Name 'status' -Default '')
    bounded_supervisor_observed = [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'bounded_supervisor_observed' -Default $false)
    resident_overlay_runtime = [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'resident_overlay_runtime' -Default $false)
    overlay_window = [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'overlay_window' -Default $false)
    tray_presence = [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'tray_presence' -Default $false)
    global_hotkey_bound = [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'global_hotkey_bound' -Default $false)
    summon_anywhere = [bool](Get-PropertyValue -Payload $OverlayPayload -Name 'summon_anywhere' -Default $false)
    activation_boundary_status = [string](Get-PropertyValue -Payload $ActivationPayload -Name 'status' -Default '')
    activation_preflight_status = [string](Get-PropertyValue -Payload $ActivationExecution -Name 'preflight_status' -Default '')
    activation_plan_status = [string](Get-PropertyValue -Payload $ActivationExecution -Name 'plan_status' -Default '')
    activation_denial_status = [string](Get-PropertyValue -Payload $ActivationExecution -Name 'denial_status' -Default '')
    activation_denial_reason = [string](Get-PropertyValue -Payload $ActivationExecution -Name 'denial_reason' -Default '')
    selected_approval_status = [string](Get-PropertyValue -Payload $ActivationApproval -Name 'selected_status' -Default '')
    selected_approval_approved = [bool](Get-PropertyValue -Payload $ActivationApproval -Name 'selected_approved' -Default $false)
    surface_status = [string](Get-PropertyValue -Payload $ActivationSurface -Name 'status' -Default '')
    host_status = [string](Get-PropertyValue -Payload $ActivationSurface -Name 'host_status' -Default '')
    summon_status = [string](Get-PropertyValue -Payload $ActivationSurface -Name 'summon_status' -Default '')
    tray_status = [string](Get-PropertyValue -Payload $ActivationSurface -Name 'tray_status' -Default '')
    overlay_status = [string](Get-PropertyValue -Payload $ActivationSurface -Name 'overlay_status' -Default '')
  }
  next_smallest_truthful_gap = 'resident_overlay_activation_checkpoint_consumption_or_process_supervision_authority_boundary'
  governance = [ordered]@{
    diagnostic_only = $true
    live_http_readback = $LiveProofPassed
    temporary_api_process = $LiveProofPassed
    resident_overlay_boundary_observed = $OverlayBoundaryObserved
    activation_boundary_observed = $ActivationBoundaryBlocked
    bounded_host_launch = $OverlayBoundaryObserved
    bounded_process_launch = $OverlayBoundaryObserved
    bounded_supervisor_observation = $OverlayBoundaryObserved
    temporary_runtime_state_write = $OverlayBoundaryObserved
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    resident_overlay_activation_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    telemetry_authority = $false
    local_process_launch_authority = $OverlayBoundaryObserved
    activation_local_process_launch_authority = $false
    api_local_process_launch_authority = $false
    process_restart_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    receipt_write_authority = $false
    denial_receipt_write_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens resident overlay activation remains blocked: live Lens readback and resident overlay boundary proof are observable, but activation does not launch a process, open an overlay, register a hotkey, create tray presence, supervise a resident host, write memory, decide approvals, or claim summon-anywhere behavior.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
