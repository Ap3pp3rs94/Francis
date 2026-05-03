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
if (-not (Test-Path -LiteralPath $SummonBlockersScript -PathType Leaf)) {
  throw "Lens summon-anywhere blockers proof script is missing: $SummonBlockersScript"
}

$ResidentHostBridgeScript = Join-Path $PSScriptRoot 'lens-summon-resident-host-blocker-proof.ps1'
if (-not (Test-Path -LiteralPath $ResidentHostBridgeScript -PathType Leaf)) {
  throw "Lens summon resident-host blocker proof script is missing: $ResidentHostBridgeScript"
}

$TrayBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-tray-presence-boundary-proof.ps1'
if (-not (Test-Path -LiteralPath $TrayBoundaryScript -PathType Leaf)) {
  throw "Lens resident runtime tray-presence boundary proof script is missing: $TrayBoundaryScript"
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
$SummonTrayPresenceBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonBlockerGroups -Name 'tray_presence' -Default @()
)
$SummonGovernance = Get-PropertyValue -Payload $SummonPayload -Name 'governance'

$ResidentHostBridgeResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $ResidentHostBridgeScript -ScriptArgs @('-Mode', 'Status')
$ResidentHostBridgePayload = $ResidentHostBridgeResult.payload
$ResidentHostBridgeGovernance = Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'governance'

$TrayBoundaryArgs = @('-Mode', 'Status')
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $TrayBoundaryArgs += @('-DataDir', $DataDir)
}
$TrayBoundaryResult = Invoke-JsonScript -PowerShellPath $PowerShell.Source -ScriptPath $TrayBoundaryScript -ScriptArgs $TrayBoundaryArgs
$TrayBoundaryPayload = $TrayBoundaryResult.payload
$TrayBoundaryGovernance = Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'governance'
$TrayPresence = Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_presence'
$TrayPreflight = Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_preflight'
$TrayBoundaryBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'blockers' -Default @()
)

$SummonTrayFamilyObserved = (
  [int]$SummonResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'kind' -Default '') -eq 'lens.summon_anywhere_blockers.proof' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'acceptance_criterion' -Default '') -eq 'summon_anywhere' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers' -and
  @($SummonBlockedFamilies).Count -ge 2 -and
  [string]$SummonBlockedFamilies[0] -eq 'resident_host' -and
  [string]$SummonBlockedFamilies[1] -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $SummonPayload -Name 'first_blocker_family' -Default '') -eq 'resident_host' -and
  $SummonTrayPresenceBlockers -contains 'tray_host_missing'
)
$ResidentHostBridgeObserved = (
  [int]$ResidentHostBridgeResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'kind' -Default '') -eq 'lens.summon_resident_host_blocker.proof' -and
  [string](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'summon_first_family_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'resident_host_lifecycle_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'handoff_aligned' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'side_effects_denied' -Default $false) -and
  [string](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'first_summon_blocker_family' -Default '') -eq 'resident_host' -and
  [string](Get-PropertyValue -Payload $ResidentHostBridgePayload -Name 'summon_next_smallest_truthful_gap' -Default '') -eq 'summon_anywhere_blockers'
)
$TrayBoundaryObserved = (
  [int]$TrayBoundaryResult.exit_code -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.tray_presence_boundary.proof' -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'authority_family' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'next_authority_family' -Default '') -eq 'hotkey_summon' -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_presence_boundary_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_preflight_observed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'side_effects_denied' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'third_authority_family_consumed' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayPresence -Name 'route' -Default '') -eq '/lens/tray' -and
  $TrayBoundaryBlockers -contains 'tray_registration_authority_not_granted' -and
  $TrayBoundaryBlockers -contains 'tray_icon_authority_not_granted' -and
  $TrayBoundaryBlockers -contains 'notification_authority_not_granted' -and
  $TrayBoundaryBlockers -contains 'tray_host_disabled'
)
$HandoffAligned = (
  $SummonTrayFamilyObserved -and
  $ResidentHostBridgeObserved -and
  $TrayBoundaryObserved -and
  $SummonTrayPresenceBlockers -contains 'tray_host_missing' -and
  $TrayBoundaryBlockers -contains 'tray_host_missing' -and
  [string](Get-PropertyValue -Payload $TrayPreflight -Name 'presence_name' -Default '') -eq 'Francis Lens Tray Presence' -and
  [string](Get-PropertyValue -Payload $TrayPreflight -Name 'config_path' -Default '') -eq 'config/runtime/lens/tray.json'
)
$SideEffectsDenied = (
  [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'diagnostic_only' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'notification_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ResidentHostBridgeGovernance -Name 'mutation_authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'mutation_authority_granted' -Default $true)
)

$Checks = @(
  (New-Check -Id 'summon_tray_presence_family' -Status $(if ($SummonTrayFamilyObserved) { 'second_family_projected' } else { 'missing_or_unexpected' }) -Passed $SummonTrayFamilyObserved -Evidence 'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status' -Reason 'The summon-anywhere blocker proof must keep tray_presence as the second blocked acceptance family after resident_host.'),
  (New-Check -Id 'previous_resident_host_bridge' -Status $(if ($ResidentHostBridgeObserved) { 'previous_family_observed' } else { 'missing_or_unexpected' }) -Passed $ResidentHostBridgeObserved -Evidence 'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status' -Reason 'The tray-presence handoff should preserve the previous resident-host bridge context before moving to the second blocker family.'),
  (New-Check -Id 'tray_presence_boundary' -Status $(if ($TrayBoundaryObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $TrayBoundaryObserved -Evidence 'scripts/lens-resident-runtime-tray-presence-boundary-proof.ps1 -Mode Status' -Reason 'The resident-runtime tray-presence boundary proof must remain blocked and read-only.'),
  (New-Check -Id 'handoff_alignment' -Status $(if ($HandoffAligned) { 'handoff_aligned' } else { 'handoff_mismatch' }) -Passed $HandoffAligned -Evidence 'summon tray_presence blocker group + resident runtime tray boundary proof' -Reason 'The summon tray_presence blocker must map to the direct tray preflight and resident-runtime tray boundary without changing authority.'),
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'summon, resident-host bridge, and tray boundary governance payloads' -Reason 'The bridge proof must remain diagnostic/readback only and grant no tray, notification, summon, hotkey, overlay, process, service, memory, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.summon_tray_presence_blocker.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'summon_anywhere'
  previous_summon_blocker_family = 'resident_host'
  summon_tray_presence_blocker_family = 'tray_presence'
  second_summon_blocker_family = 'tray_presence'
  next_summon_blocker_family = 'overlay_window'
  summon_next_smallest_truthful_gap = 'summon_anywhere_blockers'
  resident_runtime_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = 'summon_overlay_window_blocker_boundary'
  summon_tray_family_observed = $SummonTrayFamilyObserved
  previous_resident_host_bridge_observed = $ResidentHostBridgeObserved
  tray_presence_boundary_observed = $TrayBoundaryObserved
  handoff_aligned = $HandoffAligned
  side_effects_denied = $SideEffectsDenied
  summon_tray_presence_blockers = [string[]]@($SummonTrayPresenceBlockers)
  resident_runtime_tray_presence_blockers = [string[]]@($TrayBoundaryBlockers)
  tray_presence_boundary = [ordered]@{
    status = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'status' -Default 'missing')
    authority_family = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'authority_family' -Default '')
    previous_authority_family = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'previous_authority_family' -Default '')
    next_authority_family = [string](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'next_authority_family' -Default '')
    tray_presence_boundary_observed = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_presence_boundary_observed' -Default $false)
    tray_preflight_observed = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'tray_preflight_observed' -Default $false)
    side_effects_denied = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'side_effects_denied' -Default $false)
    third_authority_family_consumed = [bool](Get-PropertyValue -Payload $TrayBoundaryPayload -Name 'third_authority_family_consumed' -Default $false)
    route = [string](Get-PropertyValue -Payload $TrayPresence -Name 'route' -Default '')
    tray_preflight_status = [string](Get-PropertyValue -Payload $TrayPreflight -Name 'status' -Default '')
    tray_preflight_presence_name = [string](Get-PropertyValue -Payload $TrayPreflight -Name 'presence_name' -Default '')
    tray_preflight_config_path = [string](Get-PropertyValue -Payload $TrayPreflight -Name 'config_path' -Default '')
    blockers = [string[]]@($TrayBoundaryBlockers)
  }
  checks = @($Checks)
  evidence = @(
    'scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status',
    'scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status',
    'scripts/lens-resident-runtime-tray-presence-boundary-proof.ps1 -Mode Status',
    'scripts/lens-tray-preflight.ps1 -Mode Status',
    '/lens/tray'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_summon_anywhere_blockers_proof = $true
    wraps_summon_resident_host_blocker_proof = $true
    wraps_resident_runtime_tray_presence_boundary_proof = $true
    tray_preflight_readback = [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'tray_preflight_readback' -Default $false)
    read_only_contract = $true
    wrapped_resident_runtime_approval_request_write = [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'approval_request_write' -Default $false)
    wrapped_resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $TrayBoundaryGovernance -Name 'resident_runtime_execution_authority' -Default $false)
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
    summon_authority = $false
    capture_authority = $false
    new_sensing_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The Stage 6 summon-anywhere second blocker family is tray_presence, and this handoff consumes the existing resident-runtime tray-presence boundary proof without granting tray, notification, summon, hotkey, overlay, process, service, memory, approval-decision, or resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
