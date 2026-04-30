[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(3, 30)]
  [int]$SupervisorRunSeconds = 10,

  [string]$DataDir = ''
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
$ResidentSurfaceProofPath = Join-Path $PSScriptRoot 'lens-resident-surface-proof.ps1'
$SupervisorObservationProofPath = Join-Path $PSScriptRoot 'lens-host-supervisor-observation-proof.ps1'

$ResidentSurfaceResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $ResidentSurfaceProofPath -ScriptArgs @('-Mode', 'Status')
$SupervisorArgs = @('-Mode', 'Status', '-RunSeconds', [string]$SupervisorRunSeconds)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $SupervisorArgs += @('-DataDir', $DataDir)
}
$SupervisorResult = Invoke-JsonScript -PowerShellPath $PowerShellPath -ScriptPath $SupervisorObservationProofPath -ScriptArgs $SupervisorArgs

$ResidentSurfacePayload = Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'payload'
$SupervisorPayload = Get-PropertyValue -Payload $SupervisorResult -Name 'payload'
$ResidentSurfaceProof = Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'proof'
$SupervisorProof = Get-PropertyValue -Payload $SupervisorPayload -Name 'proof'
$ResidentSurfaceGovernance = Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'governance'
$SupervisorGovernance = Get-PropertyValue -Payload $SupervisorPayload -Name 'governance'

$ResidentSurfaceBlocked = (
  [int](Get-PropertyValue -Payload $ResidentSurfaceResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'kind' -Default '') -eq 'lens.resident_surface.readiness_proof' -and
  [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_surface_ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'ready_for_lens_resident_claim' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'resident_claim_allowed' -Default $true)
)
$SupervisorObserved = (
  [int](Get-PropertyValue -Payload $SupervisorResult -Name 'exit_code' -Default -1) -eq 0 -and
  [string](Get-PropertyValue -Payload $SupervisorPayload -Name 'kind' -Default '') -eq 'lens.host.supervisor_observation_proof' -and
  [string](Get-PropertyValue -Payload $SupervisorPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'bounded_supervisor_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'supervisor_observed_running_state' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'supervisor_observed_stopped_state' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'ready_for_resident_claim' -Default $true)
)
$OverlayBoundary = (
  $ResidentSurfaceBlocked -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'overlay_window' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'overlay_window_enabled' -Default $true)
)
$TrayBoundary = (
  $ResidentSurfaceBlocked -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'tray_presence' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'tray_host_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'tray_icon_enabled' -Default $true)
)
$SummonBoundary = (
  $ResidentSurfaceBlocked -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'summon_anywhere' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'summon_binding_enabled' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'hotkey_registration_enabled' -Default $true)
)
$AuthorityBoundary = (
  [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'bounded_supervisor_observation' -Default $false) -and
  [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'bounded_process_launch' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'window_management_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentSurfaceGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'process_restart_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'product_execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'api_local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'service_install_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisorGovernance -Name 'memory_write' -Default $true)
)
$ResidentRuntimeClaimBlocked = (
  $ResidentSurfaceBlocked -and
  $SupervisorObserved -and
  $OverlayBoundary -and
  $TrayBoundary -and
  $SummonBoundary -and
  $AuthorityBoundary
)

$Checks = @(
  (New-Check -Id 'resident_surface_boundary' -Status $(if ($ResidentSurfaceBlocked) { 'surface_blocked_readback_ready' } else { 'failed' }) -Passed $ResidentSurfaceBlocked -Evidence 'scripts/lens-resident-surface-proof.ps1 -Mode Status' -Reason 'Resident surface readiness must remain observable and blocked.')
  (New-Check -Id 'bounded_supervisor_observation' -Status $(if ($SupervisorObserved) { 'bounded_supervisor_observed' } else { 'failed' }) -Passed $SupervisorObserved -Evidence 'scripts/lens-host-supervisor-observation-proof.ps1 -Mode Status' -Reason 'The runtime proof must observe one bounded foreground host lifecycle.')
  (New-Check -Id 'overlay_window_boundary' -Status $(if ($OverlayBoundary) { 'blocked_disabled' } else { 'unexpected_overlay' }) -Passed $OverlayBoundary -Evidence 'scripts/lens-overlay-preflight.ps1 -Mode Status' -Reason 'Overlay window remains disabled and unavailable.')
  (New-Check -Id 'tray_presence_boundary' -Status $(if ($TrayBoundary) { 'blocked_disabled' } else { 'unexpected_tray' }) -Passed $TrayBoundary -Evidence 'scripts/lens-tray-preflight.ps1 -Mode Status' -Reason 'Tray presence remains disabled and unavailable.')
  (New-Check -Id 'summon_binding_boundary' -Status $(if ($SummonBoundary) { 'blocked_disabled' } else { 'unexpected_summon' }) -Passed $SummonBoundary -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'Global hotkey and summon binding remain disabled.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'surface.governance + supervisor.governance' -Reason 'This proof must not grant resident, service, tray, hotkey, overlay, API launch, or memory-write authority.')
  (New-Check -Id 'resident_runtime_claim_boundary' -Status $(if ($ResidentRuntimeClaimBlocked) { 'blocked' } else { 'unexpected_claim' }) -Passed $ResidentRuntimeClaimBlocked -Evidence 'resident overlay runtime flags' -Reason 'A bounded observation plus blocked surface proof is still not a resident overlay runtime claim.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })
$AllBlockers = @(
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'blockers' -Default @())) +
  (ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SupervisorPayload -Name 'blockers' -Default @())) +
  @(
    'resident_overlay_runtime_missing',
    'resident_host_process_not_supervised',
    'overlay_window_missing',
    'tray_presence_missing',
    'global_hotkey_binding_missing',
    'summon_anywhere_missing'
  ) | Sort-Object -Unique
)

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_overlay_runtime.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  supervisor_run_seconds = $SupervisorRunSeconds
  resident_overlay_runtime_ready = $false
  ready_for_lens_resident_claim = $false
  resident_claim_allowed = $false
  bounded_supervisor_observed = $SupervisorObserved
  supervisor_observed_running_state = [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'supervisor_observed_running_state' -Default $false)
  supervisor_observed_stopped_state = [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'supervisor_observed_stopped_state' -Default $false)
  temporary_host_process_observed = [bool](Get-PropertyValue -Payload $SupervisorPayload -Name 'temporary_host_process_observed' -Default $false)
  resident_overlay_runtime = $false
  resident_host_process = $false
  supervised = $false
  service_managed = $false
  overlay_window = $false
  tray_presence = $false
  global_hotkey_bound = $false
  summon_anywhere = $false
  checks = @($Checks)
  blockers = @($AllBlockers)
  proof = [ordered]@{
    resident_surface_status = [string](Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'status' -Default '')
    supervisor_observation_status = [string](Get-PropertyValue -Payload $SupervisorPayload -Name 'status' -Default '')
    host_running_state_status = [string](Get-PropertyValue -Payload $SupervisorProof -Name 'running_state_status' -Default '')
    host_stopped_state_status = [string](Get-PropertyValue -Payload $SupervisorProof -Name 'stopped_state_status' -Default '')
    host_final_status_readback = [string](Get-PropertyValue -Payload $SupervisorProof -Name 'final_status_readback' -Default '')
    same_process_observed = [bool](Get-PropertyValue -Payload $SupervisorProof -Name 'same_process_observed' -Default $false)
    overlay_status = [string](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'overlay_status' -Default '')
    overlay_window_enabled = [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'overlay_window_enabled' -Default $false)
    overlay_focus_supported = [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'overlay_focus_supported' -Default $false)
    tray_status = [string](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'tray_status' -Default '')
    tray_host_enabled = [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'tray_host_enabled' -Default $false)
    tray_icon_enabled = [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'tray_icon_enabled' -Default $false)
    summon_status = [string](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'summon_status' -Default '')
    global_hotkey = [string](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'global_hotkey' -Default '')
    summon_binding_enabled = [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'summon_binding_enabled' -Default $false)
    hotkey_registration_enabled = [bool](Get-PropertyValue -Payload $ResidentSurfaceProof -Name 'hotkey_registration_enabled' -Default $false)
    surface_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ResidentSurfacePayload -Name 'blockers' -Default @())
    supervisor_blockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $SupervisorPayload -Name 'blockers' -Default @())
  }
  next_smallest_truthful_gap = 'resident_overlay_activation_or_process_supervision_authority_boundary'
  governance = [ordered]@{
    diagnostic_only = $true
    bounded_host_launch = $SupervisorObserved
    bounded_process_launch = $SupervisorObserved
    bounded_supervisor_observation = $SupervisorObserved
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
    local_process_launch_authority = $SupervisorObserved
    api_local_process_launch_authority = $false
    process_restart_authority = $false
    process_supervision_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    hotkey_registration_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Lens resident overlay runtime boundary is observable and still blocked; this proof observes one bounded diagnostic host lifecycle plus blocked surface preflights, but does not create tray presence, bind a hotkey, open an overlay, supervise a resident host, or claim summon-anywhere behavior.'
}

$Payload | ConvertTo-Json -Depth 10
if ($ProofPassed) {
  exit 0
}
exit 1
