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
$OverlayBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-overlay-window-boundary-proof.ps1'
foreach ($ScriptPath in @($SummonBlockersScript, $OverlayBoundaryScript)) {
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
$TrayPresenceFamilyHandoff = Get-HandoffById -Handoffs $SummonFamilyHandoffs -Id 'tray_presence'
$TrayPresenceFamilyBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'blockers' -Default @()
)
$SummonOverlayBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'overlay_window' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'
$TrayPresenceFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'tray_presence')
$OverlayWindowFamilyIndex = [array]::IndexOf([string[]]@($SummonBlockedFamilies), 'overlay_window')

$OverlayBoundaryArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $OverlayBoundaryArgs += @('-DataDir', (Join-Path $DataDir 'proofs\resident-runtime-overlay-window-boundary\data'))
}
$OverlayBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $OverlayBoundaryScript -ScriptArgs $OverlayBoundaryArgs -DataRoot $ChildDataRoot
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
  $TrayPresenceFamilyIndex -ge 0 -and
  $OverlayWindowFamilyIndex -eq ($TrayPresenceFamilyIndex + 1) -and
  $SummonOverlayBlockers -contains 'overlay_window_missing'
)
$TrayPresenceContractReadbackObserved = (
  [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'id' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'proof_script' -Default '') -eq 'scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status' -and
  [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'next_step' -Default '') -eq 'run_tray_presence_blocker_proof' -and
  [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_overlay_window_blocker_boundary' -and
  [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'authority_required' -Default '') -eq 'tray_registration_authority' -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'authority_granted' -Default $true) -and
  [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'read_only_contract' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'would_mutate' -Default $true) -and
  $TrayPresenceFamilyBlockers -contains 'tray_host_missing'
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
  $TrayPresenceContractReadbackObserved -and
  $OverlayBoundaryObserved -and
  $SummonOverlayBlockers -contains 'overlay_window_missing' -and
  [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'overlay_name' -Default '') -eq 'Francis Lens Overlay' -and
  [string](Get-PropertyValue -Payload $OverlayPreflight -Name 'config_path' -Default '') -eq 'config/runtime/lens/overlay.json'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  $TrayPresenceContractReadbackObserved -and
  [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
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
  -not [bool](Get-PropertyValue -Payload $OverlayBoundaryGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_overlay_window_family' -Status $(if ($SummonOverlayFamilyObserved) { 'third_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonOverlayFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep overlay_window as the third blocked acceptance family after tray_presence.'),
  (New-Check -Id 'previous_tray_presence_contract' -Status $(if ($TrayPresenceContractReadbackObserved) { 'previous_family_contract_observed' } else { 'missing_or_unexpected' }) -Passed $TrayPresenceContractReadbackObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[tray_presence]' -Reason 'The overlay-window handoff should consume the tray-presence family contract before moving to the third blocker family.'),
  (New-Check -Id 'previous_tray_presence_contract_readback' -Status $(if ($TrayPresenceContractReadbackObserved) { 'previous_contract_readback_observed' } else { 'missing_or_unexpected' }) -Passed $TrayPresenceContractReadbackObserved -Evidence 'summon_anywhere_blockers.blocked_family_handoffs[tray_presence]' -Reason 'The overlay-window proof must preserve the bounded tray-presence contract without rerunning the slower tray bridge proof.'),
  (New-Check -Id 'overlay_window_boundary' -Status $(if ($OverlayBoundaryObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $OverlayBoundaryObserved -Evidence 'scripts/lens-resident-runtime-overlay-window-boundary-proof.ps1 -Mode Status' -Reason 'The resident-runtime overlay-window boundary proof must remain blocked and read-only.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon overlay_window blocker group + resident runtime overlay boundary proof' -Reason 'The summon overlay_window blocker must map to direct overlay preflight and resident-runtime overlay boundary without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, tray-presence family contract, and overlay boundary governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no overlay, capture, sensing, summon, hotkey, tray, process, service, memory, approval-decision, or resident-claim authority.')
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
  recommended_handoff_source = 'summon_overlay_window_handoff'
  recommended_next_slice = 'run_global_hotkey_binding_blocker_proof'
  recommended_proof_script = 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status'
  recommended_route = '/lens/summon'
  recommended_readiness_route = '/lens/summon/readiness'
  authority_required = 'hotkey_registration_authority'
  authority_granted = $false
  recommended_handoff = [ordered]@{
    id = 'global_hotkey_binding'
    status = 'blocked'
    previous_summon_blocker_family = 'overlay_window'
    next_summon_blocker_family = 'global_hotkey_binding'
    next_smallest_truthful_gap = 'summon_global_hotkey_binding_blocker_boundary'
    next_step = 'run_global_hotkey_binding_blocker_proof'
    proof_script = 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status'
    route = '/lens/summon'
    readiness_route = '/lens/summon/readiness'
    acceptance_criterion = 'summon_anywhere'
    blocker_family = 'global_hotkey_binding'
    authority_required = 'hotkey_registration_authority'
    authority_granted = $false
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }
  summon_overlay_family_observed = $SummonOverlayFamilyObserved
  previous_tray_presence_contract_observed = $TrayPresenceContractReadbackObserved
  previous_tray_presence_contract_readback_observed = $TrayPresenceContractReadbackObserved
  previous_tray_presence_contract = [ordered]@{
    source = 'summon_anywhere_blockers.blocked_family_handoffs'
    status = 'contract_projected'
    contract_status = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'status' -Default 'missing')
    proof_script = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'proof_script' -Default '')
    previous_summon_blocker_family = 'resident_host'
    summon_tray_presence_blocker_family = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'id' -Default '')
    next_summon_blocker_family = 'overlay_window'
    summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
    next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'next_smallest_truthful_gap' -Default '')
    route = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'route' -Default '')
    readiness_route = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'readiness_route' -Default '')
    authority_required = [string](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'authority_required' -Default '')
    authority_granted = [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'authority_granted' -Default $false)
    read_only_contract = [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'read_only_contract' -Default $false)
    diagnostic_only = [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'diagnostic_only' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'would_execute' -Default $false)
    would_mutate = [bool](Get-PropertyValue -Payload $TrayPresenceFamilyHandoff -Name 'would_mutate' -Default $false)
    handoff_aligned = $TrayPresenceContractReadbackObserved
    side_effects_denied = $TrayPresenceContractReadbackObserved
    blockers = [string[]]@($TrayPresenceFamilyBlockers)
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
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status blocked_family_handoffs[tray_presence]',
    'scripts/lens-resident-runtime-overlay-window-boundary-proof.ps1 -Mode Status',
    'scripts/lens-overlay-preflight.ps1 -Mode Status',
    '/lens/overlay'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_tray_presence_blocker_proof = $false
    uses_tray_presence_family_contract_readback = $TrayPresenceContractReadbackObserved
    tray_presence_contract_readback = $TrayPresenceContractReadbackObserved
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
