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
$OverlayWindowBridgeScript = Join-Path $PSScriptRoot 'lens-summon-overlay-window-blocker-proof.ps1'
$HotkeySummonBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-hotkey-summon-boundary-proof.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $OverlayWindowBridgeScript, $HotkeySummonBoundaryScript)) {
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
$SummonGlobalHotkeyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'global_hotkey_binding' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$OverlayBridgeArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $OverlayBridgeArgs += @('-DataDir', $DataDir)
}
$OverlayBridgeResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $OverlayWindowBridgeScript -ScriptArgs $OverlayBridgeArgs
$OverlayBridgePayload = $OverlayBridgeResult.payload
$OverlayBridgeGovernance = Get-PropertyValue -Payload $OverlayBridgePayload -Name 'governance'
$OverlayBridgePreviousTrayPresenceBridge = Get-PropertyValue -Payload $OverlayBridgePayload -Name 'previous_tray_presence_bridge'
$OverlayBridgePreviousResidentHostBridge = Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'previous_resident_host_bridge'
$OverlayBridgePreviousResidentHostProcessHandoff = Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'process_supervision_handoff'
$OverlayBridgePreviousResidentHostProcessRecommendedHandoff = Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'recommended_handoff'

$HotkeyBoundaryArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $HotkeyBoundaryArgs += @('-DataDir', $DataDir)
}
$HotkeyBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $HotkeySummonBoundaryScript -ScriptArgs $HotkeyBoundaryArgs
$HotkeyBoundaryPayload = $HotkeyBoundaryResult.payload
$HotkeyBoundaryGovernance = Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'governance'
$HotkeySummon = Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'hotkey_summon'
$HotkeySummonBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'blockers' -Default @()
)
$HotkeySummonRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HotkeySummon -Name 'required_before' -Default @()
)
$SummonPreflight = Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'summon_preflight'
$SummonPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflight -Name 'blockers' -Default @()
)

$SummonGlobalHotkeyFamilyObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  @($SummonBlockedFamilies).Count -ge 4 -and
  [string]$SummonBlockedFamilies[2] -eq 'overlay_window' -and
  [string]$SummonBlockedFamilies[3] -eq 'global_hotkey_binding' -and
  $SummonGlobalHotkeyBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonGlobalHotkeyBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonGlobalHotkeyBlockers -contains 'hotkey_registration_authority_not_granted'
)
$OverlayBridgePreviousHandoffReadbackObserved = (
  [bool](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'previous_tray_presence_bridge_resident_host_readback_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'next_summon_blocker_family' -Default '') -eq 'overlay_window' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_overlay_window_blocker_boundary' -and
  [bool](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'previous_resident_host_bridge_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'first_summon_blocker_family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'next_smallest_truthful_gap' -Default '') -eq 'stage6_lens_completion_audit' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'process_supervision_handoff_observed' -Default $false) -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'authority_granted' -Default $true) -and
  [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_required' -Default '') -eq 'none_new_stage6_completion_audit' -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_granted' -Default $true)
)
$OverlayWindowBridgeObserved = (
  [int]$OverlayBridgeResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'kind' -Default '') -eq 'lens.summon_overlay_window_blocker.proof' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'summon_overlay_family_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'overlay_window_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'handoff_aligned' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'side_effects_denied' -Default $false) -and
  $OverlayBridgePreviousHandoffReadbackObserved -and
  [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'next_summon_blocker_family' -Default '') -eq 'global_hotkey_binding' -and
  [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_global_hotkey_binding_blocker_boundary'
)
$HotkeySummonBoundaryObserved = (
  [int]$HotkeyBoundaryResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.hotkey_summon_boundary.proof' -and
  [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'authority_family' -Default '') -eq 'hotkey_summon' -and
  [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'previous_authority_family' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'next_authority_family' -Default '') -eq 'overlay_window' -and
  [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'hotkey_summon_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'summon_preflight_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'side_effects_denied' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'fourth_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $HotkeySummon -Name 'route' -Default '') -eq '/lens/summon' -and
  $HotkeySummonBlockers -contains 'global_hotkey_binding_disabled' -and
  $HotkeySummonBlockers -contains 'global_hotkey_registration_disabled' -and
  $HotkeySummonBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $HotkeySummonBlockers -contains 'summon_authority_not_granted'
)
$HandoffAligned = (
  $SummonGlobalHotkeyFamilyObserved -and
  $OverlayWindowBridgeObserved -and
  $HotkeySummonBoundaryObserved -and
  $SummonGlobalHotkeyBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonGlobalHotkeyBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonGlobalHotkeyBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $HotkeySummonBlockers -contains 'global_hotkey_binding_disabled' -and
  $HotkeySummonBlockers -contains 'global_hotkey_registration_disabled' -and
  $HotkeySummonBlockers -contains 'hotkey_registration_authority_not_granted' -and
  [string](Get-PropertyValue -Payload $SummonPreflight -Name 'global_hotkey' -Default '') -eq 'Ctrl+Alt+Space' -and
  [string](Get-PropertyValue -Payload $SummonPreflight -Name 'binding_scope' -Default '') -eq 'global'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBridgeGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_global_hotkey_binding_family' -Status $(if ($SummonGlobalHotkeyFamilyObserved) { 'fourth_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonGlobalHotkeyFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep global_hotkey_binding as the fourth blocked acceptance family after overlay_window.'),
  (New-Check -Id 'previous_overlay_window_bridge' -Status $(if ($OverlayWindowBridgeObserved) { 'previous_family_observed' } else { 'missing_or_unexpected' }) -Passed $OverlayWindowBridgeObserved -Evidence 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status' -Reason 'The global-hotkey handoff should preserve the previous overlay-window bridge context before moving to the fourth blocker family.'),
  (New-Check -Id 'previous_overlay_window_bridge_handoff_readback' -Status $(if ($OverlayBridgePreviousHandoffReadbackObserved) { 'previous_handoff_observed' } else { 'missing_or_unexpected' }) -Passed $OverlayBridgePreviousHandoffReadbackObserved -Evidence 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status' -Reason 'The global-hotkey handoff must preserve the overlay-window bridge tray-presence and resident-host process-supervision readback before moving to the global-hotkey family.'),
  (New-Check -Id 'resident_runtime_hotkey_summon_boundary' -Status $(if ($HotkeySummonBoundaryObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $HotkeySummonBoundaryObserved -Evidence 'scripts/lens-resident-runtime-hotkey-summon-boundary-proof.ps1 -Mode Status' -Reason 'The resident-runtime hotkey-summon boundary proof must remain blocked and read-only.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon global_hotkey_binding blocker group + resident-runtime hotkey-summon boundary proof' -Reason 'The summon global_hotkey_binding blocker must map to direct summon preflight and resident-runtime hotkey-summon boundary without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, overlay bridge, and hotkey-summon boundary governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no summon, hotkey, overlay, tray, process, service, memory, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_global_hotkey_binding_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_summon_blocker_family = 'overlay_window'
  summon_global_hotkey_binding_blocker_family = 'global_hotkey_binding'
  fourth_summon_blocker_family = 'global_hotkey_binding'
  next_summon_blocker_family = 'summon_binding'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  resident_runtime_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'summon_binding_blocker_boundary'
  summon_global_hotkey_family_observed = $SummonGlobalHotkeyFamilyObserved
  previous_overlay_window_bridge_observed = $OverlayWindowBridgeObserved
  previous_overlay_window_bridge_handoff_readback_observed = $OverlayBridgePreviousHandoffReadbackObserved
  previous_overlay_window_bridge = [ordered]@{
    status = [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'status' -Default 'missing')
    next_summon_blocker_family = [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'next_summon_blocker_family' -Default '')
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'next_smallest_truthful_gap' -Default '')
    previous_tray_presence_bridge_resident_host_readback_observed = [bool](Get-PropertyValue -Payload $OverlayBridgePayload -Name 'previous_tray_presence_bridge_resident_host_readback_observed' -Default $false)
    previous_tray_presence_bridge = [ordered]@{
      status = [string](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'status' -Default 'missing')
      next_summon_blocker_family = [string](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'next_summon_blocker_family' -Default '')
      next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'next_smallest_truthful_gap' -Default '')
      previous_resident_host_bridge_observed = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousTrayPresenceBridge -Name 'previous_resident_host_bridge_observed' -Default $false)
      previous_resident_host_bridge = [ordered]@{
        status = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'status' -Default 'missing')
        first_summon_blocker_family = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'first_summon_blocker_family' -Default '')
        summon_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'summon_next_smallest_truthful_gap' -Default '')
        next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'next_smallest_truthful_gap' -Default '')
        authority_required = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'authority_required' -Default '')
        authority_granted = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'authority_granted' -Default $false)
        lifecycle_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'lifecycle_next_smallest_truthful_gap' -Default '')
        handoff_aligned = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'handoff_aligned' -Default $false)
        side_effects_denied = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'side_effects_denied' -Default $false)
        bounded_local_process_launch = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'bounded_local_process_launch' -Default $false)
        temporary_runtime_state_write = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'temporary_runtime_state_write' -Default $false)
        runtime_blockers = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'runtime_blockers' -Default @()))
        surface_blockers = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'surface_blockers' -Default @()))
        process_supervision_handoff_observed = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostBridge -Name 'process_supervision_handoff_observed' -Default $false)
        process_supervision_handoff = [ordered]@{
          status = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'status' -Default '')
          next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'next_smallest_truthful_gap' -Default '')
          authority_required = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'authority_required' -Default '')
          authority_granted = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessHandoff -Name 'authority_granted' -Default $false)
          recommended_handoff = [ordered]@{
            authority_required = [string](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_required' -Default '')
            authority_granted = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'authority_granted' -Default $false)
            read_only_contract = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'read_only_contract' -Default $false)
            diagnostic_only = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'diagnostic_only' -Default $false)
            would_execute = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_execute' -Default $false)
            would_mutate = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_mutate' -Default $false)
            would_supervise_process = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_supervise_process' -Default $false)
            would_restart_process = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_restart_process' -Default $false)
            would_install_service = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_install_service' -Default $false)
            would_start_service = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_start_service' -Default $false)
            would_claim_resident = [bool](Get-PropertyValue -Payload $OverlayBridgePreviousResidentHostProcessRecommendedHandoff -Name 'would_claim_resident' -Default $false)
          }
        }
      }
    }
  }
  hotkey_summon_boundary_observed = $HotkeySummonBoundaryObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_global_hotkey_binding_blockers = [string[]]@($SummonGlobalHotkeyBlockers)
  resident_runtime_hotkey_summon_blockers = [string[]]@($HotkeySummonBlockers)
  hotkey_summon_boundary = [ordered]@{
    status = [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'status' -Default 'missing')
    authority_family = [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'authority_family' -Default '')
    previous_authority_family = [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'previous_authority_family' -Default '')
    next_authority_family = [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'next_authority_family' -Default '')
    hotkey_summon_boundary_observed = [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'hotkey_summon_boundary_observed' -Default $false)
    summon_preflight_observed = [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'summon_preflight_observed' -Default $false)
    side_effects_denied = [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'side_effects_denied' -Default $false)
    fourth_authority_family_consumed = [bool](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'fourth_authority_family_consumed' -Default $false)
    route = [string](Get-PropertyValue -Payload $HotkeySummon -Name 'route' -Default '')
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPreflight -Name 'global_hotkey' -Default '')
    binding_scope = [string](Get-PropertyValue -Payload $SummonPreflight -Name 'binding_scope' -Default '')
    required_before = [string[]]@($HotkeySummonRequiredBefore)
    summon_preflight_status = [string](Get-PropertyValue -Payload $SummonPreflight -Name 'status' -Default '')
    blockers = [string[]]@($HotkeySummonBlockers)
    summon_preflight_blockers = [string[]]@($SummonPreflightBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status',
    'scripts/lens-resident-runtime-hotkey-summon-boundary-proof.ps1 -Mode Status',
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    '/lens/summon'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_overlay_window_blocker_proof = $true
    overlay_window_previous_handoff_readback = $OverlayBridgePreviousHandoffReadbackObserved
    wraps_resident_runtime_hotkey_summon_boundary_proof = $true
    summon_preflight_readback = [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'summon_preflight_readback' -Default $false)
    wrapped_resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'resident_runtime_execution_authority' -Default $false)
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
  message = 'The Stage 6 summon-anywhere fourth blocker family is global_hotkey_binding, and this handoff consumes the existing resident-runtime hotkey-summon boundary proof without granting hotkey, summon, overlay, tray, process, service, memory, approval-decision, or resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
