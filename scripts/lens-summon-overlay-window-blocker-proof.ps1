param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = ''
)

$ErrorActionPreference = 'Stop'

function ConvertTo-StringArray {
  param(
    [AllowNull()]
    [object]$Value
  )

  if ($null -eq $Value) {
    return @()
  }

  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
  }

  $Single = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Single)) {
    return @()
  }
  return @($Single)
}

function Get-PropertyValue {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [AllowNull()]
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

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @()
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$SummonBlockersScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
$TrayPresenceBridgeScript = Join-Path $PSScriptRoot 'lens-summon-tray-presence-blocker-proof.ps1'
$OverlayBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-overlay-window-boundary-proof.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $TrayPresenceBridgeScript, $OverlayBoundaryScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Required Lens proof script is missing: $ScriptPath"
  }
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs @('-Mode', 'Status')
$SummonPayload = $SummonResult.payload
$SummonBlockerGroups = Get-PropertyValue -Payload $SummonPayload -Name 'blocker_groups'
$SummonBlockedFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @()
)
$SummonOverlayBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'overlay_window' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$TrayBridgeArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $TrayBridgeArgs += @('-DataDir', (Join-Path $DataDir 'proofs\summon-tray-presence-bridge\data'))
}
$TrayBridgeResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $TrayPresenceBridgeScript -ScriptArgs $TrayBridgeArgs
$TrayBridgePayload = $TrayBridgeResult.payload
$TrayBridgeGovernance = Get-PropertyValue -Payload $TrayBridgePayload -Name 'governance'
$TrayBridgePreviousResidentHostBridge = Get-PropertyValue -Payload $TrayBridgePayload -Name 'previous_resident_host_bridge'
$TrayBridgePreviousResidentHostProcessHandoff = Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'process_supervision_handoff'
$TrayBridgePreviousResidentHostProcessRecommendedHandoff = Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'recommended_handoff'

$OverlayBoundaryArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $OverlayBoundaryArgs += @('-DataDir', (Join-Path $DataDir 'proofs\resident-runtime-overlay-window-boundary\data'))
}
$OverlayBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $OverlayBoundaryScript -ScriptArgs $OverlayBoundaryArgs
$OverlayBoundaryPayload = $OverlayBoundaryResult.payload
$OverlayBoundaryGovernance = Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'governance'
$OverlayWindow = Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'overlay_window'
$OverlayPreflight = Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'overlay_preflight'
$OverlayBoundaryBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'blockers' -Default @()
)

$SummonOverlayFamilyObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  @($SummonBlockedFamilies).Count -ge 3 -and
  [string]$SummonBlockedFamilies[1] -eq 'tray_presence' -and
  [string]$SummonBlockedFamilies[2] -eq 'overlay_window' -and
  $SummonOverlayBlockers -contains 'overlay_window_missing'
)
$TrayBridgePreviousResidentHostReadbackObserved = (
  [bool](Get-PropertyValue -Payload $TrayBridgePayload -Name 'previous_resident_host_bridge_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'first_summon_blocker_family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'process_supervision_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_granted' -Default $true)
)
$TrayPresenceBridgeObserved = (
  [int]$TrayBridgeResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'kind' -Default '') -eq 'lens.summon_tray_presence_blocker.proof' -and
  [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $TrayBridgePayload -Name 'summon_tray_family_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBridgePayload -Name 'tray_presence_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBridgePayload -Name 'handoff_aligned' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBridgePayload -Name 'side_effects_denied' -Default $false) -and
  $TrayBridgePreviousResidentHostReadbackObserved -and
  [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'next_summon_blocker_family' -Default '') -eq 'overlay_window' -and
  [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_overlay_window_blocker_boundary'
)
$OverlayBoundaryObserved = (
  [int]$OverlayBoundaryResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.overlay_window_boundary.proof' -and
  [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'authority_family' -Default '') -eq 'overlay_window' -and
  [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'next_authority_family' -Default '') -eq 'resident_claim' -and
  [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'overlay_window_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'overlay_preflight_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'side_effects_denied' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'fifth_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $OverlayWindow -Name 'route' -Default '') -eq '/lens/overlay' -and
  $OverlayBoundaryBlockers -contains 'overlay_window_missing' -and
  $OverlayBoundaryBlockers -contains 'overlay_window_disabled' -and
  $OverlayBoundaryBlockers -contains 'overlay_control_authority_not_granted' -and
  $OverlayBoundaryBlockers -contains 'window_management_authority_not_granted' -and
  $OverlayBoundaryBlockers -contains 'capture_authority_not_granted'
)
$HandoffAligned = (
  $SummonOverlayFamilyObserved -and
  $TrayPresenceBridgeObserved -and
  $OverlayBoundaryObserved -and
  $SummonOverlayBlockers -contains 'overlay_window_missing' -and
  [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'overlay_name' -Default '') -eq 'Francis Lens Overlay' -and
  [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'config_path' -Default '') -eq 'config/runtime/lens/overlay.json'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'window_management_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'capture_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'new_sensing_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBridgeGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_overlay_window_family' -Status $(if ($SummonOverlayFamilyObserved) { 'third_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonOverlayFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep overlay_window as the third blocked acceptance family after tray_presence.'),
  (New-Check -Id 'previous_tray_presence_bridge' -Status $(if ($TrayPresenceBridgeObserved) { 'previous_family_observed' } else { 'missing_or_unexpected' }) -Passed $TrayPresenceBridgeObserved -Evidence 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status' -Reason 'The overlay-window handoff should preserve the previous tray-presence bridge context before moving to the third blocker family.'),
  (New-Check -Id 'previous_tray_presence_resident_host_readback' -Status $(if ($TrayBridgePreviousResidentHostReadbackObserved) { 'previous_handoff_observed' } else { 'missing_or_unexpected' }) -Passed $TrayBridgePreviousResidentHostReadbackObserved -Evidence 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status' -Reason 'The overlay-window handoff must preserve the tray-presence bridge resident-host process-supervision readback before moving to the overlay-window family.'),
  (New-Check -Id 'overlay_window_boundary' -Status $(if ($OverlayBoundaryObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $OverlayBoundaryObserved -Evidence 'scripts/lens-resident-runtime-overlay-window-boundary-proof.ps1 -Mode Status' -Reason 'The resident-runtime overlay-window boundary proof must remain blocked and read-only.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon overlay_window blocker group + resident runtime overlay boundary proof' -Reason 'The summon overlay_window blocker must map to direct overlay preflight and resident-runtime overlay boundary without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, tray bridge, and overlay boundary governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no overlay, capture, sensing, summon, hotkey, tray, process, service, memory, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_overlay_window_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_summon_blocker_family = 'tray_presence'
  summon_overlay_window_blocker_family = 'overlay_window'
  third_summon_blocker_family = 'overlay_window'
  next_summon_blocker_family = 'global_hotkey_binding'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  resident_runtime_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'summon_global_hotkey_binding_blocker_boundary'
  summon_overlay_family_observed = $SummonOverlayFamilyObserved
  previous_tray_presence_bridge_observed = $TrayPresenceBridgeObserved
  previous_tray_presence_bridge_resident_host_readback_observed = $TrayBridgePreviousResidentHostReadbackObserved
  previous_tray_presence_bridge = [ordered]@{
    status = [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'status' -Default 'missing')
    next_summon_blocker_family = [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'next_summon_blocker_family' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayBridgePayload -Name 'next_smallest_truthful_gap' -Default '')
    previous_resident_host_bridge_observed = [bool](Get-PropertyValue -Payload $TrayBridgePayload -Name 'previous_resident_host_bridge_observed' -Default $false)
    previous_resident_host_bridge = [ordered]@{
      status = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'status' -Default 'missing')
      first_summon_blocker_family = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'first_summon_blocker_family' -Default '')
      summon_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'summon_next_smallest_truthful_gap' -Default '')
      next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'next_smallest_truthful_gap' -Default '')
      authority_required = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'authority_required' -Default '')
      authority_granted = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'authority_granted' -Default $false)
      process_supervision_handoff_observed = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostBridge -Name 'process_supervision_handoff_observed' -Default $false)
      process_supervision_handoff = [ordered]@{
        status = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'status' -Default '')
        next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'next_smallest_truthful_gap' -Default '')
        authority_required = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'authority_required' -Default '')
        authority_granted = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessHandoff -Name 'authority_granted' -Default $false)
        recommended_handoff = [ordered]@{
          authority_required = [string](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_required' -Default '')
          authority_granted = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_granted' -Default $false)
          read_only_contract = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'read_only_contract' -Default $false)
          diagnostic_only = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'diagnostic_only' -Default $false)
          would_execute = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_execute' -Default $false)
          would_mutate = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_mutate' -Default $false)
          would_supervise_process = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_supervise_process' -Default $false)
          would_restart_process = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_restart_process' -Default $false)
          would_install_service = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_install_service' -Default $false)
          would_start_service = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_start_service' -Default $false)
          would_claim_resident = [bool](Get-PropertyValue -Payload $TrayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_claim_resident' -Default $false)
        }
      }
    }
  }
  overlay_window_boundary_observed = $OverlayBoundaryObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_overlay_window_blockers = [string[]]@($SummonOverlayBlockers)
  resident_runtime_overlay_window_blockers = [string[]]@($OverlayBoundaryBlockers)
  overlay_window_boundary = [ordered]@{
    status = [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'status' -Default 'missing')
    authority_family = [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'authority_family' -Default '')
    previous_authority_family = [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'previous_authority_family' -Default '')
    next_authority_family = [string](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'next_authority_family' -Default '')
    overlay_window_boundary_observed = [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'overlay_window_boundary_observed' -Default $false)
    overlay_preflight_observed = [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'overlay_preflight_observed' -Default $false)
    side_effects_denied = [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'side_effects_denied' -Default $false)
    fifth_authority_family_consumed = [bool](Get-PropertyValue -Payload $OverlayBoundaryPayload -Name 'fifth_authority_family_consumed' -Default $false)
    route = [string](Get-PropertyValue -Payload $OverlayWindow -Name 'route' -Default '')
    overlay_preflight_status = [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'status' -Default '')
    overlay_preflight_name = [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'overlay_name' -Default '')
    overlay_preflight_config_path = [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'config_path' -Default '')
    blockers = [string[]]@($OverlayBoundaryBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status',
    'scripts/lens-resident-runtime-overlay-window-boundary-proof.ps1 -Mode Status',
    'scripts/lens-overlay-preflight.ps1 -Mode Status',
    '/lens/overlay'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_tray_presence_blocker_proof = $true
    tray_presence_previous_resident_host_bridge_readback = $TrayBridgePreviousResidentHostReadbackObserved
    wraps_resident_runtime_overlay_window_boundary_proof = $true
    overlay_preflight_readback = [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'overlay_preflight_readback' -Default $false)
    read_only_contract = $true
    approval_request_write = $false
    resident_runtime_execution_authority = $false
    product_execution_authority = $false
    execution_authority = $false
    approval_decision_authority = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    tray_registration_authority = $false
    tray_icon_authority = $false
    notification_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    window_management_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The Stage 6 summon-anywhere third blocker family is overlay_window, and this handoff consumes the existing resident-runtime overlay-window boundary proof without granting overlay, capture, sensing, summon, hotkey, tray, process, service, memory, approval-decision, or resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
