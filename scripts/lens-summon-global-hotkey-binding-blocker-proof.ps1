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

function Get-HandoffById {
  param(
    [AllowNull()]
    [object]$Handoffs,
    [string]$Id
  )

  foreach ($Handoff in @($Handoffs)) {
    if ([string](Get-PropertyValue -Payload $Handoff -Name 'id' -Default '') -eq $Id) {
      return $Handoff
    }
  }
  return $null
}

function Invoke-JsonScript {
  param(
    [Parameter(Mandatory = $true)]
    [string]$PowerShellPath,

    [Parameter(Mandatory = $true)]
    [string]$ScriptPath,

    [string[]]$ScriptArgs = @(),

    [string]$DataRoot = ''
  )

  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
    }
  }

  $HadPreviousDataRoot = Test-Path Env:\FRANCIS_DATA_DIR
  $PreviousDataRoot = [string]$env:FRANCIS_DATA_DIR
  try {
    if (-not [string]::IsNullOrWhiteSpace($DataRoot)) {
      $env:FRANCIS_DATA_DIR = [System.IO.Path]::GetFullPath($DataRoot)
    }
    $Output = & $PowerShellPath -NoProfile -ExecutionPolicy Bypass -File $ScriptPath @ScriptArgs 2>&1
    $ExitCode = $LASTEXITCODE
  } finally {
    if ($HadPreviousDataRoot) {
      $env:FRANCIS_DATA_DIR = $PreviousDataRoot
    } else {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
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

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$SummonBlockersScript = Join-Path $PSScriptRoot 'lens-summon-anywhere-blockers-proof.ps1'
$HotkeySummonBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-hotkey-summon-boundary-proof.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $HotkeySummonBoundaryScript)) {
  if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw "Required Lens proof script is missing: $ScriptPath"
  }
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}
$ChildDataRoot = ''
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $ChildDataRoot = [System.IO.Path]::GetFullPath($DataDir)
}

$SummonResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $SummonBlockersScript -ScriptArgs @('-Mode', 'Status') -DataRoot $ChildDataRoot
$SummonPayload = $SummonResult.payload
$SummonBlockerGroups = Get-PropertyValue -Payload $SummonPayload -Name 'blocker_groups'
$SummonBlockedFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPayload -Name 'blocked_families' -Default @()
)
$SummonFamilyHandoffs = Get-PropertyValue -Payload $SummonPayload -Name 'blocked_family_handoffs' -Default @()
$OverlayWindowFamilyHandoff = Get-HandoffById -Handoffs $SummonFamilyHandoffs -Id 'overlay_window'
$AuthorityFamilyHandoff = Get-HandoffById -Handoffs $SummonFamilyHandoffs -Id 'authority'
$OverlayWindowFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'blockers' -Default @()
)
$AuthorityFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'blockers' -Default @()
)
$SummonGlobalHotkeyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'global_hotkey_binding' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'
$SurfaceRuntimeReadbackObserved = Get-PropertyValue -Payload $SummonPayload -Name 'surface_runtime_readback_observed' -Default ([ordered]@{})
$SummonBindingRuntimeObserved = [bool](Get-PropertyValue -Payload $SurfaceRuntimeReadbackObserved -Name 'summon_binding' -Default $false)
$OverlayWindowFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'overlay_window')
$GlobalHotkeyFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'global_hotkey_binding')
$AuthorityFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'authority')
$SummonBindingResolvedToAuthority = (
  $SummonBindingRuntimeObserved -and
  $AuthorityFamilyIndex -eq ($GlobalHotkeyFamilyIndex + 1) -and
  [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'id' -Default '') -eq 'authority'
)

$HotkeyBoundaryArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $HotkeyBoundaryArgs += @('-DataDir', $DataDir)
}
$HotkeyBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $HotkeySummonBoundaryScript -ScriptArgs $HotkeyBoundaryArgs -DataRoot $ChildDataRoot
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
  $OverlayWindowFamilyIndex -ge 0 -and
  $GlobalHotkeyFamilyIndex -eq ($OverlayWindowFamilyIndex + 1) -and
  $SummonGlobalHotkeyBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonGlobalHotkeyBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonGlobalHotkeyBlockers -contains 'hotkey_registration_authority_not_granted'
)
$OverlayWindowContractReadbackObserved = (
  [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'id' -Default '') -eq 'overlay_window' -and
  [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'next_step' -Default '') -eq 'run_overlay_window_blocker_proof' -and
  [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_global_hotkey_binding_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'authority_required' -Default '') -eq 'overlay_control_authority' -and
  -not [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'would_mutate' -Default $true) -and
  $OverlayWindowFamilyBlockers -contains 'overlay_window_missing'
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
  $OverlayWindowContractReadbackObserved -and
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
  $OverlayWindowContractReadbackObserved -and
  [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeyBoundaryGovernance -Name 'mutation_authority_granted' -Default $true)
)

$NextSummonBlockerFamily = if ($SummonBindingResolvedToAuthority) { 'authority' } else { 'summon_binding' }
$NextSmallestTruthfulGap = if ($SummonBindingResolvedToAuthority) {
  [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'next_smallest_truthful_gap' -Default 'stage6_lens_completion_audit')
} else {
  'summon_binding_blocker_boundary'
}
$RecommendedHandoffSource = if ($SummonBindingResolvedToAuthority) {
  'summon_authority_handoff_after_summon_binding_runtime_readback'
} else {
  'summon_global_hotkey_binding_handoff'
}
$RecommendedNextSlice = if ($SummonBindingResolvedToAuthority) {
  [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'next_step' -Default 'run_summon_authority_blocker_proof')
} else {
  'run_summon_binding_blocker_proof'
}
$RecommendedProofScript = if ($SummonBindingResolvedToAuthority) {
  [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'proof_script' -Default 'scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status')
} else {
  'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status'
}
$RecommendedAuthorityRequired = if ($SummonBindingResolvedToAuthority) {
  [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'authority_required' -Default 'summon_hotkey_overlay_and_process_authority')
} else {
  'summon_authority'
}
$RecommendedHandoff = if ($SummonBindingResolvedToAuthority) {
  [ordered]@{
    id = 'authority'
    status = [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'status' -Default 'blocked')
    previous_summon_blocker_family = 'global_hotkey_binding'
    next_summon_blocker_family = 'authority'
    next_smallest_truthful_gap = $NextSmallestTruthfulGap
    next_step = $RecommendedNextSlice
    proof_script = $RecommendedProofScript
    route = [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'route' -Default '/lens/summon')
    readiness_route = [string](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'readiness_route' -Default '/lens/summon/readiness')
    acceptance_criterion = 'summon_anywhere'
    blocker_family = 'authority'
    authority_required = $RecommendedAuthorityRequired
    authority_granted = $false
    read_only_contract = [bool](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'read_only_contract' -Default $true)
    diagnostic_only = [bool](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'diagnostic_only' -Default $true)
    would_execute = [bool](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'would_execute' -Default $false)
    would_mutate = [bool](Get-PropertyValue -Payload $AuthorityFamilyHandoff -Name 'would_mutate' -Default $false)
    blockers = [string[]]@($AuthorityFamilyBlockers)
  }
} else {
  [ordered]@{
    id = 'summon_binding'
    status = 'blocked'
    previous_summon_blocker_family = 'global_hotkey_binding'
    next_summon_blocker_family = 'summon_binding'
    next_smallest_truthful_gap = 'summon_binding_blocker_boundary'
    next_step = 'run_summon_binding_blocker_proof'
    proof_script = 'scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status'
    route = '/lens/summon'
    readiness_route = '/lens/summon/readiness'
    acceptance_criterion = 'summon_anywhere'
    blocker_family = 'summon_binding'
    authority_required = 'summon_authority'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
}

$Checks = @(
  (New-Check -Id 'summon_global_hotkey_binding_family' -Status $(if ($SummonGlobalHotkeyFamilyObserved) { 'fourth_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonGlobalHotkeyFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep global_hotkey_binding as the fourth blocked acceptance family after overlay_window.'),
  (New-Check -Id 'previous_overlay_window_contract' -Status $(if ($OverlayWindowContractReadbackObserved) { 'previous_family_contract_observed' } else { 'missing_or_unexpected' }) -Passed $OverlayWindowContractReadbackObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[overlay_window]' -Reason 'The global-hotkey handoff should consume the overlay-window family contract before moving to the fourth blocker family.'),
  (New-Check -Id 'previous_overlay_window_contract_readback' -Status $(if ($OverlayWindowContractReadbackObserved) { 'previous_contract_readback_observed' } else { 'missing_or_unexpected' }) -Passed $OverlayWindowContractReadbackObserved -Evidence 'summon_anywhere_blockers.blocked_family_handoffs[overlay_window]' -Reason 'The global-hotkey proof must preserve the bounded overlay-window contract without rerunning the slower overlay bridge proof.'),
  (New-Check -Id 'resident_runtime_hotkey_summon_boundary' -Status $(if ($HotkeySummonBoundaryObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $HotkeySummonBoundaryObserved -Evidence 'scripts/lens-resident-runtime-hotkey-summon-boundary-proof.ps1 -Mode Status' -Reason 'The resident-runtime hotkey-summon boundary proof must remain blocked and read-only.'),
  (New-Check -Id 'summon_binding_runtime_readback' -Status $(if ($SummonBindingResolvedToAuthority) { 'resolved_to_authority_handoff' } elseif ($SummonBindingRuntimeObserved) { 'readback_present_without_authority_handoff' } else { 'not_present' }) -Passed $true -Evidence 'summon_anywhere_blockers.surface_runtime_readback_observed.summon_binding' -Reason 'If the aggregate proof already observed summon binding runtime, global-hotkey must hand forward to authority instead of a resolved surface family.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon global_hotkey_binding blocker group + resident-runtime hotkey-summon boundary proof' -Reason 'The summon global_hotkey_binding blocker must map to direct summon preflight and resident-runtime hotkey-summon boundary without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, overlay family contract, and hotkey-summon boundary governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no summon, hotkey, overlay, tray, process, service, memory, approval-decision, or resident-claim authority.')
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
  next_summon_blocker_family = $NextSummonBlockerFamily
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  resident_runtime_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $HotkeyBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
  recommended_handoff_source = $RecommendedHandoffSource
  recommended_next_slice = $RecommendedNextSlice
  recommended_proof_script = $RecommendedProofScript
  recommended_route = '/lens/summon'
  recommended_readiness_route = '/lens/summon/readiness'
  authority_required = $RecommendedAuthorityRequired
  authority_granted = $false
  recommended_handoff = $RecommendedHandoff
  summon_binding_runtime_readback_observed = $SummonBindingRuntimeObserved
  summon_binding_resolved_to_authority_handoff = $SummonBindingResolvedToAuthority
  summon_global_hotkey_family_observed = $SummonGlobalHotkeyFamilyObserved
  previous_overlay_window_contract_observed = $OverlayWindowContractReadbackObserved
  previous_overlay_window_contract_readback_observed = $OverlayWindowContractReadbackObserved
  previous_overlay_handoff = [ordered]@{
    source = 'summon_anywhere_blockers.blocked_family_handoffs'
    status = 'contract_projected'
    contract_status = [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'status' -Default 'missing')
    proof_script = [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'proof_script' -Default '')
    previous_summon_blocker_family = 'tray_presence'
    summon_overlay_window_blocker_family = [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'id' -Default '')
    next_summon_blocker_family = 'global_hotkey_binding'
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'authority_required' -Default '')
    authority_granted = [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'authority_granted' -Default $false)
    read_only_contract = [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'read_only_contract' -Default $false)
    diagnostic_only = [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'diagnostic_only' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'would_execute' -Default $false)
    would_mutate = [bool](Get-PropertyValue -Payload $OverlayWindowFamilyHandoff -Name 'would_mutate' -Default $false)
    handoff_aligned = $OverlayWindowContractReadbackObserved
    side_effects_denied = $OverlayWindowContractReadbackObserved
    blockers = [string[]]@($OverlayWindowFamilyBlockers)
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
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[overlay_window]',
    'scripts/lens-resident-runtime-hotkey-summon-boundary-proof.ps1 -Mode Status',
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    '/lens/summon'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_overlay_window_blocker_proof = $false
    uses_overlay_window_family_contract_readback = $OverlayWindowContractReadbackObserved
    overlay_window_contract_readback = $OverlayWindowContractReadbackObserved
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
