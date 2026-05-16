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

$AuthorityBlockerGroups = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'authority_blocker_groups'
$ProcessSupervisionGroup = Get-PropertyValue -Payload $AuthorityBlockerGroups -Name 'process_supervision'
$ProcessSupervisionBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'blockers' -Default @()
)
$ProcessSupervisionRequiredBefore = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'required_before' -Default @()
)
$RemainingFamilies = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'remaining_authority_families' -Default @()
)
$AuthorityBlockersSummary = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'summary'
$AuthorityBlockersGovernance = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'governance'
$AuthorityBlockersBoundaryProof = Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'boundary_proof'

$AuthorityBlockersObserved = (
  [int]$AuthorityBlockersExitCode -eq 0 -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'kind' -Default '') -eq 'lens.resident_runtime.authority_blockers_proof' -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'status' -Default '') -eq 'proof_passed' -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'ok' -Default $false) -and
  [bool](Get-PropertyValue -Payload $AuthorityBlockersSummary -Name 'combined_gap_split' -Default $false) -and
  [string](Get-PropertyValue -Payload $AuthorityBlockersPayload -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_runtime_process_supervision_authority_boundary'
)
$ProcessSupervisionFamilyObserved = (
  $AuthorityBlockersObserved -and
  [string](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'id' -Default '') -eq 'process_supervision' -and
  [string](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'status' -Default '') -eq 'blocked' -and
  -not [bool](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'ready' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'would_execute' -Default $true) -and
  [string](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'route' -Default '') -eq '/lens/host/supervision/authority/readiness' -and
  $ProcessSupervisionBlockers -contains 'local_process_launch_authority_not_granted' -and
  $ProcessSupervisionBlockers -contains 'process_supervision_authority_not_granted' -and
  $ProcessSupervisionBlockers -contains 'process_restart_authority_not_granted'
)
$BoundaryDenied = (
  $ProcessSupervisionFamilyObserved -and
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
  (New-Check -Id 'resident_runtime_authority_blockers_proof' -Status $(if ($AuthorityBlockersObserved) { 'proof_observed' } else { 'missing_or_failed' }) -Passed $AuthorityBlockersObserved -Evidence 'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status' -Reason 'The resident runtime authority blocker split proof must be observable before the first family boundary can be consumed.')
  (New-Check -Id 'process_supervision_family' -Status $(if ($ProcessSupervisionFamilyObserved) { 'blocked' } else { 'missing_or_unexpected' }) -Passed $ProcessSupervisionFamilyObserved -Evidence '/lens/host/supervision/authority/readiness' -Reason 'The first resident runtime authority family must be process launch, supervision, and restart, and it must remain blocked.')
  (New-Check -Id 'process_supervision_side_effects_denied' -Status $(if ($BoundaryDenied) { 'denied_no_process_supervision' } else { 'unexpected_side_effect' }) -Passed $BoundaryDenied -Evidence 'resident_runtime_boundary_proof.would_*' -Reason 'The proof must not launch, supervise, restart, control service/tray/hotkey/overlay, write memory, or claim resident status.')
  (New-Check -Id 'authority_boundary' -Status $(if ($AuthorityBoundary) { 'diagnostic_bounded' } else { 'unexpected_authority' }) -Passed $AuthorityBoundary -Evidence 'resident_runtime_authority_blockers.governance' -Reason 'This resident-runtime process-supervision proof must not grant product execution, process launch, process supervision, restart, service, tray, hotkey, overlay, memory, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.resident_runtime.process_supervision_boundary.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  repo_root = $RepoRoot
  authority_family = 'process_supervision'
  next_authority_family = 'service_control'
  process_supervision_boundary_observed = $ProcessSupervisionFamilyObserved
  authority_blockers_proof_observed = $AuthorityBlockersObserved
  side_effects_denied = $BoundaryDenied
  first_authority_family_consumed = $ProcessSupervisionFamilyObserved
  authority_required = 'process_supervision_authority'
  authority_granted = $false
  resident_runtime_execution_authority = [bool](Get-PropertyValue -Payload $AuthorityBlockersGovernance -Name 'resident_runtime_execution_authority' -Default $false)
  local_process_launch_authority = $false
  process_supervision_authority = $false
  process_restart_authority = $false
  service_control_authority = $false
  resident_claim_authority = $false
  would_launch_process = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_launch_process' -Default $false)
  would_supervise_process = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_supervise_process' -Default $false)
  would_restart_process = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_restart_process' -Default $false)
  would_start_service = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_start_service' -Default $false)
  would_register_tray = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_register_tray' -Default $false)
  would_register_hotkey = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_register_hotkey' -Default $false)
  would_open_overlay = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_open_overlay' -Default $false)
  would_write_memory = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_write_memory' -Default $false)
  would_claim_resident = [bool](Get-PropertyValue -Payload $AuthorityBlockersBoundaryProof -Name 'would_claim_resident' -Default $false)
  process_supervision = [ordered]@{
    status = [string](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'status' -Default 'missing')
    ready = [bool](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'ready' -Default $false)
    authority_granted = [bool](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'authority_granted' -Default $false)
    would_execute = [bool](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'would_execute' -Default $false)
    route = [string](Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'route' -Default '')
    evidence = [string[]]@(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $ProcessSupervisionGroup -Name 'evidence' -Default @()))
    required_before = [string[]]@($ProcessSupervisionRequiredBefore)
    blockers = [string[]]@($ProcessSupervisionBlockers)
  }
  checks = @($Checks)
  blockers = [string[]]@($ProcessSupervisionBlockers)
  remaining_authority_families = [string[]]@($RemainingFamilies)
  next_smallest_truthful_gap = 'resident_runtime_service_control_authority_boundary'
  evidence = @(
    'scripts/lens-resident-runtime-authority-blockers-proof.ps1 -Mode Status',
    '/lens/host/supervision/authority/readiness',
    '/lens/resident-runtime/execute'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    wraps_existing_authority_blockers_proof = $true
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
    hotkey_registration_authority = $false
    overlay_control_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The resident runtime process-supervision authority family is consumed as a readback boundary: it remains blocked and produces no process launch, supervision, restart, service, tray, hotkey, overlay, memory, approval-decision, or resident-claim authority.'
}

$Payload | ConvertTo-Json -Depth 8
exit $(if ($ProofPassed) { 0 } else { 1 })
