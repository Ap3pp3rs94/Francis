[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [ValidateRange(1, 50)]
  [int]$Limit = 5,

  [string]$DataDir = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

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

function ConvertTo-StringArray {
  param(
    [AllowNull()]
    [object]$Value
  )

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

function Invoke-LensRuntimeLoopReadbacks {
  param([int]$ReadbackLimit)

  $Python = Get-Command python -ErrorAction SilentlyContinue
  if ($null -eq $Python) {
    throw 'Python is required to read Lens runtime-loop readiness.'
  }

  $PreviousPythonPath = $env:PYTHONPATH
  $PreviousDataDir = $env:FRANCIS_DATA_DIR
  $SrcPath = Join-Path $RepoRoot 'src'
  if ([string]::IsNullOrWhiteSpace($PreviousPythonPath)) {
    $env:PYTHONPATH = $SrcPath
  } elseif ($PreviousPythonPath -notlike "*$SrcPath*") {
    $env:PYTHONPATH = "$SrcPath;$PreviousPythonPath"
  }
  if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
    $env:FRANCIS_DATA_DIR = $DataDir
  }

  $PythonCode = @"
import json
from francis.lens.activation import lens_host_supervision_authority_readiness_audit
from francis.lens.host_runtime_plan import lens_host_runtime_loop_readiness_audit

print(json.dumps({
    "runtime_loop_readiness": lens_host_runtime_loop_readiness_audit(limit=$ReadbackLimit),
    "supervision_authority_readiness": lens_host_supervision_authority_readiness_audit(limit=$ReadbackLimit),
}))
"@

  $TempPythonPath = [System.IO.Path]::ChangeExtension([System.IO.Path]::GetTempFileName(), '.py')
  try {
    Set-Content -LiteralPath $TempPythonPath -Value $PythonCode -Encoding UTF8
    $PreviousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
      $Output = & $Python.Source $TempPythonPath 2>&1
      $ExitCode = $LASTEXITCODE
    } finally {
      $ErrorActionPreference = $PreviousErrorActionPreference
    }
  } finally {
    Remove-Item -LiteralPath $TempPythonPath -Force -ErrorAction SilentlyContinue
    $env:PYTHONPATH = $PreviousPythonPath
    if ($null -eq $PreviousDataDir) {
      Remove-Item Env:\FRANCIS_DATA_DIR -ErrorAction SilentlyContinue
    } else {
      $env:FRANCIS_DATA_DIR = $PreviousDataDir
    }
  }

  $Text = ($Output | ForEach-Object { [string]$_ }) -join "`n"
  if ($ExitCode -ne 0) {
    throw "Lens runtime-loop readiness readback failed with exit code $ExitCode. $Text"
  }

  return $Text | ConvertFrom-Json -ErrorAction Stop
}

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$Readbacks = Invoke-LensRuntimeLoopReadbacks -ReadbackLimit $Limit
$RuntimeLoopReadiness = Get-PropertyValue -Payload $Readbacks -Name 'runtime_loop_readiness'
$SupervisionAuthorityReadiness = Get-PropertyValue -Payload $Readbacks -Name 'supervision_authority_readiness'

$RuntimeLoopHandoff = Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'first_blocked_requirement_handoff' -Default ([ordered]@{})
$SupervisionAuthorityHandoff = Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'first_blocked_requirement_handoff' -Default ([ordered]@{})
$RuntimeLoopGovernance = Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'governance' -Default ([ordered]@{})
$SupervisionAuthorityGovernance = Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'governance' -Default ([ordered]@{})
$RuntimeLoopBlockedRequirements = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'blocked_requirements')
$SupervisionAuthorityBlockedRequirements = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'blocked_requirements'
)
$RuntimeLoopBlockers = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'blockers')
$SupervisionAuthorityBlockers = ConvertTo-StringArray -Value (
  Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'blockers'
)

$RuntimeLoopReadinessObserved = (
  [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'kind' -Default '') -eq 'lens.host.runtime_loop.readiness_audit' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'audit_status' -Default '') -eq 'complete' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'route' -Default '') -eq '/lens/host/runtime-loop/readiness' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'next_smallest_truthful_gap' -Default '') -eq 'resident_host_supervision_authority_readiness_blockers'
)
$RuntimeLoopFirstBlockerConsumed = (
  $RuntimeLoopReadinessObserved -and
  [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'first_blocked_requirement' -Default '') -eq 'resident_loop_process_supervision' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopHandoff -Name 'id' -Default '') -eq 'resident_loop_process_supervision' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopHandoff -Name 'readiness_route' -Default '') -eq '/lens/host/supervision/authority/readiness' -and
  [string](Get-PropertyValue -Payload $RuntimeLoopHandoff -Name 'next_step' -Default '') -eq 'resolve_host_supervision_authority_readiness_blockers_before_implementation' -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopHandoff -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopHandoff -Name 'would_mutate' -Default $true)
)
$SupervisionAuthorityReadinessObserved = (
  [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'kind' -Default '') -eq 'lens.host.supervision_authority.readiness_audit' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'status' -Default '') -eq 'blocked' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'audit_status' -Default '') -eq 'complete' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'route' -Default '') -eq '/lens/host/supervision/authority/readiness' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'next_smallest_truthful_gap' -Default '') -eq 'host_supervision_authority_exact_approval_request'
)
$SupervisionAuthorityFirstBlockerObserved = (
  $SupervisionAuthorityReadinessObserved -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'first_blocked_requirement' -Default '') -eq 'exact_supervision_authority_approval' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'id' -Default '') -eq 'exact_supervision_authority_approval' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'request_route' -Default '') -eq '/lens/host/supervision/authority/request' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'requests_route' -Default '') -eq '/lens/host/supervision/authority/requests' -and
  [string](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'approval_action' -Default '') -eq 'lens.host.supervision_authority' -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'authority_granted' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'would_execute' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityHandoff -Name 'would_mutate' -Default $true)
)
$SideEffectsDenied = (
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'resident_runtime_execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'receipt_write_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $RuntimeLoopGovernance -Name 'resident_claim_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'execution_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'approval_decision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'process_supervision_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'service_control_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'memory_write' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'receipt_write_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'denial_receipt_write_authority' -Default $true) -and
  -not [bool](Get-PropertyValue -Payload $SupervisionAuthorityGovernance -Name 'resident_claim_authority' -Default $true)
)

$Checks = @(
  (New-Check -Id 'runtime_loop_readiness_audit' -Status $(if ($RuntimeLoopReadinessObserved) { 'readiness_observed' } else { 'missing_or_failed' }) -Passed $RuntimeLoopReadinessObserved -Evidence '/lens/host/runtime-loop/readiness' -Reason 'The resident host runtime-loop readiness audit must be observable before the next blocker is consumed.')
  (New-Check -Id 'runtime_loop_first_blocker' -Status $(if ($RuntimeLoopFirstBlockerConsumed) { 'host_supervision_authority_handoff_ready' } else { 'missing_or_unexpected' }) -Passed $RuntimeLoopFirstBlockerConsumed -Evidence 'runtime_loop_readiness.first_blocked_requirement_handoff' -Reason 'The first blocked runtime-loop requirement must hand off to host supervision authority readiness.')
  (New-Check -Id 'host_supervision_authority_readiness' -Status $(if ($SupervisionAuthorityReadinessObserved) { 'readiness_observed' } else { 'missing_or_failed' }) -Passed $SupervisionAuthorityReadinessObserved -Evidence '/lens/host/supervision/authority/readiness' -Reason 'The host supervision authority readiness audit must be observable before any supervision implementation work.')
  (New-Check -Id 'host_supervision_authority_first_blocker' -Status $(if ($SupervisionAuthorityFirstBlockerObserved) { 'exact_approval_request_handoff_ready' } else { 'missing_or_unexpected' }) -Passed $SupervisionAuthorityFirstBlockerObserved -Evidence 'supervision_authority_readiness.first_blocked_requirement_handoff' -Reason 'The next host supervision authority blocker must be an exact approved authority request, not implicit authority.')
  (New-Check -Id 'side_effects_denied' -Status $(if ($SideEffectsDenied) { 'readback_only' } else { 'unexpected_authority' }) -Passed $SideEffectsDenied -Evidence 'runtime_loop_readiness.governance + supervision_authority_readiness.governance' -Reason 'The proof must not grant execution, process supervision, service control, receipt write, memory write, approval-decision, or resident-claim authority.')
)

$ProofPassed = -not @($Checks | Where-Object { -not [bool]$_['passed'] })

$Payload = [ordered]@{
  ok = $ProofPassed
  kind = 'lens.host.runtime_loop_readiness.proof'
  status = if ($ProofPassed) { 'proof_passed' } else { 'proof_failed' }
  mode = $Mode.ToLowerInvariant()
  stage = 'Stage 6 / Lens MVP'
  stage_state = 'active'
  acceptance_criterion = 'system_resident_presence'
  previous_next_smallest_truthful_gap = 'resident_host_process_not_supervised'
  runtime_loop_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'next_smallest_truthful_gap' -Default '')
  next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'next_smallest_truthful_gap' -Default '')
  runtime_loop_readiness_observed = $RuntimeLoopReadinessObserved
  runtime_loop_first_blocker_consumed = $RuntimeLoopFirstBlockerConsumed
  host_supervision_authority_readiness_observed = $SupervisionAuthorityReadinessObserved
  host_supervision_authority_first_blocker_observed = $SupervisionAuthorityFirstBlockerObserved
  side_effects_denied = $SideEffectsDenied
  first_blocked_requirement = [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'first_blocked_requirement' -Default '')
  first_blocked_requirement_handoff = $RuntimeLoopHandoff
  host_supervision_authority_first_blocked_requirement = [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'first_blocked_requirement' -Default '')
  host_supervision_authority_first_blocked_requirement_handoff = $SupervisionAuthorityHandoff
  blocked_requirements = [string[]]@($RuntimeLoopBlockedRequirements)
  host_supervision_authority_blocked_requirements = [string[]]@($SupervisionAuthorityBlockedRequirements)
  blockers = [string[]]@($RuntimeLoopBlockers)
  host_supervision_authority_blockers = [string[]]@($SupervisionAuthorityBlockers)
  checks = @($Checks)
  source_readbacks = [ordered]@{
    runtime_loop_readiness_status = [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'status' -Default '')
    runtime_loop_first_blocker = [string](Get-PropertyValue -Payload $RuntimeLoopReadiness -Name 'first_blocked_requirement' -Default '')
    supervision_authority_readiness_status = [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'status' -Default '')
    supervision_authority_first_blocker = [string](Get-PropertyValue -Payload $SupervisionAuthorityReadiness -Name 'first_blocked_requirement' -Default '')
  }
  evidence = @(
    'scripts/lens-host-runtime-loop-readiness-proof.ps1 -Mode Status'
    '/lens/host/runtime-loop/readiness'
    '/lens/host/supervision/authority/readiness'
    '/lens/host/supervision/authority/request'
    '/lens/host/supervision/authority/requests'
  )
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    uses_runtime_loop_readiness_readback = $true
    uses_supervision_authority_readiness_readback = $true
    approval_request_write = $false
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
    summon_authority = $false
    memory_write = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'The resident host runtime-loop readiness proof consumes the first loop blocker as a readback-only handoff into host supervision authority readiness; no loop, process supervision, service control, approval decision, receipt write, memory write, or resident claim is performed.'
}

$Payload | ConvertTo-Json -Depth 10
exit $(if ($ProofPassed) { 0 } else { 1 })
