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

$AuthorityBlockersScript = Join-Path $PSScriptRoot 'lens-resident-runtime-authority-blockers-proof.ps1'
if (-not (Test-Path -LiteralPath $AuthorityBlockersScript -PathType Leaf)) {
  throw "Resident runtime authority blockers proof script is missing: $AuthorityBlockersScript"
}

$TrayPreflightScript = Join-Path $PSScriptRoot 'lens-tray-preflight.ps1'
if (-not (Test-Path -LiteralPath $TrayPreflightScript -PathType Leaf)) {
  throw "Lens tray preflight script is missing: $TrayPreflightScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$AuthorityBlockersArgs = @('-Mode', $Mode)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $AuthorityBlockersArgs += @('-DataDir', $DataDir)
}

$AuthorityBlockersOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $AuthorityBlockersScript @AuthorityBlockersArgs 2>&1
$AuthorityBlockersExitCode = $LASTEXITCODE
$AuthorityBlockersText = ($AuthorityBlockersOutput | ForEach-Object { [string]$_ }) -join "`n"
$AuthorityBlockersPayload = $null
try {
  $AuthorityBlockersPayload = $AuthorityBlockersText | ConvertFrom-Json -ErrorAction Stop
} catch {
  $AuthorityBlockersPayload = $null
}

$TrayPreflightOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $TrayPreflightScript -Mode Status 2>&1
$TrayPreflightExitCode = $LASTEXITCODE
$TrayPreflightText = ($TrayPreflightOutput | ForEach-Object { [string]$_ }) -join "`n"
$TrayPreflightPayload = $null
try {
  $TrayPreflightPayload = $TrayPreflightText | ConvertFrom-Json -ErrorAction Stop
} catch {
  $TrayPreflightPayload = $null
}

$AuthorityBlockerGroups = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'authority_blocker_groups'
$ServiceControlGroup = Get-PropertyValue -Payload $AuthorityBlockerGroups -Name 'service_control'
$TrayPresenceGroup = Get-PropertyValue -Payload $AuthorityBlockerGroups -Name 'tray_presence'
$ServiceControlBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ServiceControlGroup -Name 'blockers' -Default @()
)
$TrayPresenceBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayPresenceGroup -Name 'blockers' -Default @()
)
$TrayPresenceRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayPresenceGroup -Name 'required_before' -Default @()
)
$TrayPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $TrayPreflightPayload -Name 'blockers' -Default @()
)
$RemainingFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'remaining_authority_families' -Default @()
)
$RemainingFamiliesAfterThisBoundary = [string[]]@(
  $RemainingFamilies | Where-Object {
    $_ -ne 'process_supervision' -and $_ -ne 'service_control' -and $_ -ne 'tray_presence'
  }
)
$AuthorityBlockersSummary = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'summary'
$AuthorityBlockersGovernance = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'governance'
$AuthorityBlockersBoundaryProof = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'boundary_proof'
$TrayPreflightGovernance = Get-PropertyValue -Payload $TrayPreflightPayload -Name 'governance'

$AuthorityBlockersObserved = (
  [int]$AuthorityBlockersExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.authority_blockers_proof' -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersSummary -Name 'combined_gap_split' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_runtime_process_supervision_authority_boundary'
)
$ServiceControlFamilyObserved = (
  $AuthorityBlockersObserved -and
  [string](Get-PropertyValue -Payload $ServiceControlGroup -Name 'id' -Default '') -eq 'service_control' -and
  [string](Get-PropertyValue -Payload $ServiceControlGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ServiceControlGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ServiceControlGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ServiceControlGroup -Name 'would_execute' -Default $true) -and
  $ServiceControlBlockers -contains 'service_install_authority_not_granted' -and
  $ServiceControlBlockers -contains 'service_control_authority_not_granted'
)
$TrayPreflightObserved = (
  [int]$TrayPreflightExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'kind' -Default '') -eq 'lens.tray.preflight' -and
  [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'ready' -Default $true) -and
  $TrayPreflightBlockers -contains 'tray_registration_authority_not_granted' -and
  $TrayPreflightBlockers -contains 'tray_icon_authority_not_granted' -and
  $TrayPreflightBlockers -contains 'notification_authority_not_granted' -and
  [bool](Get-PropertyValue -Payload $TrayPreflightGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $TrayPreflightGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayPreflightGovernance -Name 'tray_icon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayPreflightGovernance -Name 'notification_authority' -Default $true)
)
$TrayPresenceFamilyObserved = (
  $ServiceControlFamilyObserved -and
  $TrayPreflightObserved -and
  [string](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'id' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'would_execute' -Default $true) -and
  [string](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'route' -Default '') -eq '/lens/tray' -and
  $TrayPresenceBlockers -contains 'tray_registration_authority_not_granted' -and
  $TrayPresenceBlockers -contains 'tray_icon_authority_not_granted' -and
  $TrayPresenceBlockers -contains 'notification_authority_not_granted'
)
$BoundaryDenied = (
  $TrayPresenceFamilyObserved -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $true)
)
$AuthorityBoundary = (
  $BoundaryDenied -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'diagnostic_only' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'process_restart_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'tray_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'overlay_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'resident_claim_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'resident_runtime_authority_blockers_proof' -Status $(if ($AuthorityBlockersObserved) { 'proof_observed' } else { 'missing_or_failed' }) -Passed $AuthorityBlockersObserved -Evidence 'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status' -Reason 'The resident runtime authority blocker split proof must be observable before the tray-presence family can be consumed.')
  (New-Check -Id 'previous_service_control_family' -Status $(if ($ServiceControlFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $ServiceControlFamilyObserved -Evidence '/lens/host/persistent-supervision/enablement' -Reason 'The previous service-control family must remain blocked before tray presence is treated as the next boundary.')
  (New-Check -Id 'tray_preflight_readback' -Status $(if ($TrayPreflightObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $TrayPreflightObserved -Evidence 'scripts/lens-tray-preflight.ps1 -Mode Status' -Reason 'The direct tray preflight must remain read-only and blocked.')
  (New-Check -Id 'tray_presence_family' -Status $(if ($TrayPresenceFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $TrayPresenceFamilyObserved -Evidence '/lens/tray' -Reason 'The third resident runtime authority family must be tray presence and notification authority, and it must remain blocked.')
  (New-Check -Id 'tray_presence_side_effects_denied' -Status $(if ($BoundaryDenied) { 'denied_no_tray_presence' } else { 'unexpected_side_effect' }) -Passed $BoundaryDenied -Evidence 'resident_runtime_boundary_proof.would_*' -Reason 'The proof must not register tray presence, hotkeys, overlay, services, memory, or resident claims.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'resident_runtime_authority_blockers.governance + tray.preflight.governance' -Reason 'This resident-runtime tray-presence proof must not grant product execution, process launch, process supervision, restart, service, tray, hotkey, overlay, memory, approval-decision, notification, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_runtime.tray_presence_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  authority_family = 'tray_presence'
  previous_authority_family = 'service_control'
  next_authority_family = 'hotkey_summon'
  tray_presence_boundary_observed = $TrayPresenceFamilyObserved
  previous_service_control_family_observed = $ServiceControlFamilyObserved
  tray_preflight_observed = $TrayPreflightObserved
  authority_blockers_proof_observed = $AuthorityBlockersObserved
  side_effects_denied = $BoundaryDenied
  third_authority_family_consumed = $TrayPresenceFamilyObserved
  resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
  local_process_launch_authority = $false
  process_supervision_authority = $false
  process_restart_authority = $false
  service_install_authority = $false
  service_control_authority = $false
  tray_registration_authority = $false
  tray_icon_authority = $false
  notification_authority = $false
  resident_claim_authority = $false
  would_launch_process = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $false)
  would_supervise_process = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $false)
  would_restart_process = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_restart_process' -Default $false)
  would_install_service = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_install_service' -Default $false)
  would_start_service = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $false)
  would_register_tray = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $false)
  would_register_hotkey = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $false)
  would_open_overlay = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $false)
  would_write_memory = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $false)
  would_claim_resident = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $false)
  tray_presence = [ordered]@{
    status = [string](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'ready' -Default $false)
    authority_granted = [bool](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'authority_granted' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'would_execute' -Default $false)
    route = [string](Get-PropertyValue -Payload $TrayPresenceGroup -Name 'route' -Default '')
    evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $TrayPresenceGroup -Name 'evidence' -Default @()))
    required_before = [string[]]@($TrayPresenceRequiredBefore)
    blockers = [string[]]@($TrayPresenceBlockers)
  }
  tray_preflight = [ordered]@{
    status = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'ready' -Default $false)
    presence_name = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'presence_name' -Default '')
    config_path = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'config_path' -Default '')
    tray_scope = [string](Get-PropertyValue -Payload $TrayPreflightPayload -Name 'tray_scope' -Default '')
    required_before_enable = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $TrayPreflightPayload -Name 'required_before_enable' -Default @()))
    blockers = [string[]]@($TrayPreflightBlockers)
  }
  checks = @($Checks)
  blockers = [string[]]@($TrayPresenceBlockers)
  remaining_authority_families = [string[]]@($RemainingFamilies)
  remaining_authority_families_after_this_boundary = [string[]]@($RemainingFamiliesAfterThisBoundary)
  next_smallest_truthful_gap = 'resident_runtime_hotkey_summon_authority_boundary'
  evidence = @(
    'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status',
    'scripts/lens-tray-preflight.ps1 -Mode Status',
    '/lens/tray',
    '/lens/resident-runtime/execute'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_existing_authority_blockers_proof = $true
    tray_preflight_readback = $true
    approval_request_write = [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'approval_request_write' -Default $false)
    resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
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
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The resident runtime tray-presence authority family is consumed as a readback boundary: tray registration, tray icon, and notification authority remain blocked and no tray, hotkey, overlay, service, process, memory, approval-decision, or resident-claim side effect is produced.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
