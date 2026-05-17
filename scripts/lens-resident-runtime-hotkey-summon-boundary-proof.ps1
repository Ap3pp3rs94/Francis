param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$DataDir = '',

  [string]$CachedAuthorityBlockersProofPath = '',

  [string]$CachedTrayPresenceBoundaryProofPath = '',

  [string]$CachedSummonPreflightProofPath = ''
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

function Read-CachedJsonScriptResult {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return $null
  }
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = ''
      error = 'cached_payload_missing'
      timed_out = $false
      cached = $true
    }
  }

  $Text = Get-Content -LiteralPath $Path -Raw
  $Payload = $null
  try {
    $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return [ordered]@{
      exit_code = 1
      payload = $null
      output = $Text
      error = 'cached_payload_json_invalid'
      timed_out = $false
      cached = $true
    }
  }

  return [ordered]@{
    exit_code = 0
    payload = $Payload
    output = $Text
    error = ''
    timed_out = $false
    cached = $true
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

$AuthorityBlockersScript = Join-Path $PSScriptRoot 'lens-resident-runtime-authority-blockers-proof.ps1'
if (-not (Test-Path -LiteralPath $AuthorityBlockersScript -PathType Leaf)) {
  throw "Resident runtime authority blockers proof script is missing: $AuthorityBlockersScript"
}

$TrayPresenceBoundaryScript = Join-Path $PSScriptRoot 'lens-resident-runtime-tray-presence-boundary-proof.ps1'
if (-not (Test-Path -LiteralPath $TrayPresenceBoundaryScript -PathType Leaf)) {
  throw "Resident runtime tray-presence boundary proof script is missing: $TrayPresenceBoundaryScript"
}

$SummonPreflightScript = Join-Path $PSScriptRoot 'lens-summon-preflight.ps1'
if (-not (Test-Path -LiteralPath $SummonPreflightScript -PathType Leaf)) {
  throw "Lens summon preflight script is missing: $SummonPreflightScript"
}

$PowerShell = Get-Command pwsh -ErrorAction SilentlyContinue
if ($null -eq $PowerShell) {
  $PowerShell = Get-Command powershell -ErrorAction Stop
}

$AuthorityBlockersArgs = @('-Mode', $Mode)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $AuthorityBlockersArgs += @('-DataDir', $DataDir)
}

$AuthorityBlockersProofCached = $false
$CachedAuthorityBlockersResult = Read-CachedJsonScriptResult -Path $CachedAuthorityBlockersProofPath
if ($null -ne $CachedAuthorityBlockersResult) {
  $AuthorityBlockersExitCode = [int](Get-PropertyValue -Payload $CachedAuthorityBlockersResult -Name 'exit_code' -Default 1)
  $AuthorityBlockersText = [string](Get-PropertyValue -Payload $CachedAuthorityBlockersResult -Name 'output' -Default '')
  $AuthorityBlockersPayload = Get-PropertyValue -Payload $CachedAuthorityBlockersResult -Name 'payload'
  $AuthorityBlockersProofCached = [bool](Get-PropertyValue -Payload $CachedAuthorityBlockersResult -Name 'cached' -Default $false)
} else {
  $AuthorityBlockersOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $AuthorityBlockersScript @AuthorityBlockersArgs 2>&1
  $AuthorityBlockersExitCode = $LASTEXITCODE
  $AuthorityBlockersText = ($AuthorityBlockersOutput | ForEach-Object { [string]$_ }) -join "`n"
  $AuthorityBlockersPayload = $null
  try {
    $AuthorityBlockersPayload = $AuthorityBlockersText | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $AuthorityBlockersPayload = $null
  }
}

$TrayPresenceArgs = @('-Mode', $Mode)
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $TrayPresenceArgs += @('-DataDir', $DataDir)
}

$TrayPresenceProofCached = $false
$CachedTrayPresenceResult = Read-CachedJsonScriptResult -Path $CachedTrayPresenceBoundaryProofPath
if ($null -ne $CachedTrayPresenceResult) {
  $TrayPresenceExitCode = [int](Get-PropertyValue -Payload $CachedTrayPresenceResult -Name 'exit_code' -Default 1)
  $TrayPresenceText = [string](Get-PropertyValue -Payload $CachedTrayPresenceResult -Name 'output' -Default '')
  $TrayPresencePayload = Get-PropertyValue -Payload $CachedTrayPresenceResult -Name 'payload'
  $TrayPresenceProofCached = [bool](Get-PropertyValue -Payload $CachedTrayPresenceResult -Name 'cached' -Default $false)
} else {
  $TrayPresenceOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $TrayPresenceBoundaryScript @TrayPresenceArgs 2>&1
  $TrayPresenceExitCode = $LASTEXITCODE
  $TrayPresenceText = ($TrayPresenceOutput | ForEach-Object { [string]$_ }) -join "`n"
  $TrayPresencePayload = $null
  try {
    $TrayPresencePayload = $TrayPresenceText | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $TrayPresencePayload = $null
  }
}

$SummonPreflightProofCached = $false
$CachedSummonPreflightResult = Read-CachedJsonScriptResult -Path $CachedSummonPreflightProofPath
if ($null -ne $CachedSummonPreflightResult) {
  $SummonPreflightExitCode = [int](Get-PropertyValue -Payload $CachedSummonPreflightResult -Name 'exit_code' -Default 1)
  $SummonPreflightText = [string](Get-PropertyValue -Payload $CachedSummonPreflightResult -Name 'output' -Default '')
  $SummonPreflightPayload = Get-PropertyValue -Payload $CachedSummonPreflightResult -Name 'payload'
  $SummonPreflightProofCached = [bool](Get-PropertyValue -Payload $CachedSummonPreflightResult -Name 'cached' -Default $false)
} else {
  $SummonPreflightOutput = & $PowerShell.Source -NoProfile -ExecutionPolicy Bypass -File $SummonPreflightScript -Mode Status 2>&1
  $SummonPreflightExitCode = $LASTEXITCODE
  $SummonPreflightText = ($SummonPreflightOutput | ForEach-Object { [string]$_ }) -join "`n"
  $SummonPreflightPayload = $null
  try {
    $SummonPreflightPayload = $SummonPreflightText | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $SummonPreflightPayload = $null
  }
}

$AuthorityBlockerGroups = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'authority_blocker_groups'
$HotkeySummonGroup = Get-PropertyValue -Payload $AuthorityBlockerGroups -Name 'hotkey_summon'
$HotkeySummonBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HotkeySummonGroup -Name 'blockers' -Default @()
)
$HotkeySummonRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $HotkeySummonGroup -Name 'required_before' -Default @()
)
$SummonPreflightBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'blockers' -Default @()
)
$SummonPreflightRequiredBeforeEnable = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SummonPreflightPayload -Name 'required_before_enable' -Default @()
)
$RemainingFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'remaining_authority_families' -Default @()
)
$RemainingFamiliesAfterThisBoundary = [string[]]@(
  $RemainingFamilies | Where-Object {
    $_ -ne 'process_supervision' -and $_ -ne 'service_control' -and $_ -ne 'tray_presence' -and $_ -ne 'hotkey_summon'
  }
)
$AuthorityBlockersSummary = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'summary'
$AuthorityBlockersGovernance = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'governance'
$AuthorityBlockersBoundaryProof = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'boundary_proof'
$SummonPreflightGovernance = Get-PropertyValue -Payload $SummonPreflightPayload -Name 'governance'

$AuthorityBlockersObserved = (
  [int]$AuthorityBlockersExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.authority_blockers_proof' -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersSummary -Name 'combined_gap_split' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_runtime_process_supervision_authority_boundary'
)
$TrayPresenceFamilyObserved = (
  [int]$TrayPresenceExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.tray_presence_boundary.proof' -and
  [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'ok' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'authority_family' -Default '') -eq 'tray_presence' -and
  [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'next_authority_family' -Default '') -eq 'hotkey_summon' -and
  [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'third_authority_family_consumed' -Default $false) -and
  [bool](Get-PropertyValue -Payload $TrayPresencePayload -Name 'side_effects_denied' -Default $false) -and
  [string](Get-PropertyValue -Payload $TrayPresencePayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_runtime_hotkey_summon_authority_boundary'
)
$SummonPreflightObserved = (
  [int]$SummonPreflightExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'kind' -Default '') -eq 'lens.summon.preflight' -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $true) -and
  [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '') -ne '' -and
  $SummonPreflightBlockers -contains 'global_hotkey_binding_disabled' -and
  $SummonPreflightBlockers -contains 'global_hotkey_registration_disabled' -and
  $SummonPreflightBlockers -contains 'summon_authority_not_granted' -and
  $SummonPreflightBlockers -contains 'hotkey_registration_authority_not_granted' -and
  [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'read_only_contract' -Default $false) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'summon_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'hotkey_registration_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'local_process_launch_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SummonPreflightGovernance -Name 'overlay_control_authority' -Default $true)
)
$HotkeySummonFamilyObserved = (
  $AuthorityBlockersObserved -and
  $TrayPresenceFamilyObserved -and
  $SummonPreflightObserved -and
  [string](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'id' -Default '') -eq 'hotkey_summon' -and
  [string](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'would_execute' -Default $true) -and
  [string](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'route' -Default '') -eq '/lens/summon' -and
  $HotkeySummonBlockers -contains 'global_hotkey_binding_disabled' -and
  $HotkeySummonBlockers -contains 'global_hotkey_registration_disabled' -and
  $HotkeySummonBlockers -contains 'hotkey_registration_authority_not_granted' -and
  $HotkeySummonBlockers -contains 'summon_authority_not_granted'
)
$BoundaryDenied = (
  $HotkeySummonFamilyObserved -and
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
  (New-Check -Id 'resident_runtime_authority_blockers_proof' -Status $(if ($AuthorityBlockersObserved) { 'proof_observed' } else { 'missing_or_failed' }) -Passed $AuthorityBlockersObserved -Evidence 'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status' -Reason 'The resident runtime authority blocker split proof must be observable before the hotkey-summon family can be consumed.')
  (New-Check -Id 'previous_tray_presence_family' -Status $(if ($TrayPresenceFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $TrayPresenceFamilyObserved -Evidence 'scripts/lens-resident-runtime-tray-presence-boundary-proof.ps1 -Mode Status' -Reason 'The previous tray-presence family must remain blocked before hotkey summon is treated as the next boundary.')
  (New-Check -Id 'summon_preflight_readback' -Status $(if ($SummonPreflightObserved) { 'blocked_readback_ready' } else { 'missing_or_unexpected' }) -Passed $SummonPreflightObserved -Evidence 'scripts/lens-summon-preflight.ps1 -Mode Status' -Reason 'The direct summon preflight must remain read-only and blocked.')
  (New-Check -Id 'hotkey_summon_family' -Status $(if ($HotkeySummonFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $HotkeySummonFamilyObserved -Evidence '/lens/summon' -Reason 'The fourth resident runtime authority family must be global hotkey and summon-anywhere authority, and it must remain blocked.')
  (New-Check -Id 'hotkey_summon_side_effects_denied' -Status $(if ($BoundaryDenied) { 'denied_no_hotkey_summon' } else { 'unexpected_side_effect' }) -Passed $BoundaryDenied -Evidence 'resident_runtime_boundary_proof.would_*' -Reason 'The proof must not register hotkeys, summon, launch overlay, control tray/services, write memory, or claim resident status.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'resident_runtime_authority_blockers.governance + summon.preflight.governance' -Reason 'This resident-runtime hotkey-summon proof must not grant product execution, process launch, process supervision, restart, service, tray, hotkey, overlay, memory, approval-decision, notification, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_runtime.hotkey_summon_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  authority_family = 'hotkey_summon'
  previous_authority_family = 'tray_presence'
  next_authority_family = 'overlay_window'
  authority_required = 'hotkey_registration_and_summon_authority'
  authority_granted = $false
  hotkey_summon_boundary_observed = $HotkeySummonFamilyObserved
  previous_tray_presence_family_observed = $TrayPresenceFamilyObserved
  summon_preflight_observed = $SummonPreflightObserved
  authority_blockers_proof_observed = $AuthorityBlockersObserved
  cached_authority_blockers_proof = $AuthorityBlockersProofCached
  cached_tray_presence_boundary_proof = $TrayPresenceProofCached
  cached_summon_preflight = $SummonPreflightProofCached
  side_effects_denied = $BoundaryDenied
  fourth_authority_family_consumed = $HotkeySummonFamilyObserved
  resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
  local_process_launch_authority = $false
  process_supervision_authority = $false
  process_restart_authority = $false
  service_install_authority = $false
  service_control_authority = $false
  tray_registration_authority = $false
  tray_icon_authority = $false
  notification_authority = $false
  summon_authority = $false
  hotkey_registration_authority = $false
  overlay_control_authority = $false
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
  hotkey_summon = [ordered]@{
    status = [string](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'ready' -Default $false)
    authority_granted = [bool](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'authority_granted' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'would_execute' -Default $false)
    route = [string](Get-PropertyValue -Payload $HotkeySummonGroup -Name 'route' -Default '')
    evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $HotkeySummonGroup -Name 'evidence' -Default @()))
    required_before = [string[]]@($HotkeySummonRequiredBefore)
    blockers = [string[]]@($HotkeySummonBlockers)
  }
  summon_preflight = [ordered]@{
    status = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'ready' -Default $false)
    summon_name = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'summon_name' -Default '')
    config_path = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'config_path' -Default '')
    global_hotkey = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'global_hotkey' -Default '')
    binding_scope = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'binding_scope' -Default '')
    palette_route = [string](Get-PropertyValue -Payload $SummonPreflightPayload -Name 'palette_route' -Default '')
    required_before_enable = [string[]]@($SummonPreflightRequiredBeforeEnable)
    blockers = [string[]]@($SummonPreflightBlockers)
  }
  checks = @($Checks)
  blockers = [string[]]@($HotkeySummonBlockers)
  remaining_authority_families = [string[]]@($RemainingFamilies)
  remaining_authority_families_after_this_boundary = [string[]]@($RemainingFamiliesAfterThisBoundary)
  next_smallest_truthful_gap = 'resident_runtime_overlay_window_authority_boundary'
  evidence = @(
    'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status',
    'scripts/lens-resident-runtime-tray-presence-boundary-proof.ps1 -Mode Status',
    'scripts/lens-summon-preflight.ps1 -Mode Status',
    '/lens/summon',
    '/lens/resident-runtime/execute'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_existing_authority_blockers_proof = $true
    tray_presence_boundary_readback = $true
    summon_preflight_readback = $true
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
    summon_authority = $false
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The resident runtime hotkey-summon authority family is consumed as a readback boundary: global hotkey binding, hotkey registration, and summon-anywhere authority remain blocked and no summon, hotkey, overlay, tray, service, process, memory, approval-decision, or resident-claim side effect is produced.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
